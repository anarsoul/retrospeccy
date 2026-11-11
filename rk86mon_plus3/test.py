#!/usr/bin/env python3
"""Check rk86mon.tap on SkoolKit's Z80 core (pip install skoolkit).

The machine is a +2A/+3 with its eight pages and both paging ports; the code
block of the tape is put at #6000 and started, as the BASIC loader does.  The
keyboard and the EAR input are functions of the T-state counter, writes to
port #FE are logged with their times.  Code running in pages 4-7 is slowed
down while the picture is drawn, as the gate array does it (a crude model:
only opcode fetches are held).  Tape timing loops do not survive that, which
is why nothing here runs from those pages.

What is checked:
  - the Monitor starts and its directives work; the picture appears on the
    Spectrum screen and no instruction is executed from pages 4-7;
  - directive O writes what the real Radio-86RK writes, with its timing
    (the reference numbers are 8080 clock cycles counted from the same ROM
    code, see rk2wav.py);
  - directive I reads recordings made by rk2wav.py, also 10% slow or fast;
  - BASIC loads, runs and reads back a program it has saved (MSAVE, MLOAD:
    the byte-level tape entries #F80C and #F806);
  - "Piton" loads from the tape and plays; RAMDOS and the memory editor start.

Usage: test.py [rk86mon.tap]
"""
import bisect
import collections
import os
import sys
import tempfile

import skoolkit.simulator

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rk2wav                                                   # noqa: E402

# SkoolKit's simulator ignores writes below #4000 (a ROM).  Here it is RAM.
_src = open(skoolkit.simulator.__file__).read().replace('> 0x3FFF', '>= 0')
_ns = {'__name__': 'skoolkit.simulator_allram'}
exec(compile(_src, 'simulator_allram', 'exec'), _ns)
Simulator = _ns['Simulator']

FRAME, CPU = 70908, 3546900
LOADER = 0x6000
VIDEO, PITCH = 0x77C2, 78
ROWS = ["\x01ZXCV", "ASDFG", "QWERT", "12345", "09876", "POIUY", "\rLKJH", " \x02MNB"]
KEY = {c: (r, b) for r, row in enumerate(ROWS) for b, c in enumerate(row)}
SYM = {',': 'N', '.': 'M', ':': 'Z', ';': 'O', '"': 'P', '+': 'K', '-': 'J', '=': 'L', '*': 'B', '/': 'V',
       '?': 'C', '(': '8', ')': '9', '<': 'R', '>': 'T', '$': '4', '!': '1', '#': '3', '%': '5'}
BASIC_PATCH = '12D0=C3EE19 19EE=9F2803CB2FC93CC9 096E=C3F619 19F6=8FB7E81E18C3D802'.split()


def tap_blocks(path):
    d, p, out = open(path, 'rb').read(), 0, []
    while p < len(d):
        n = d[p] | d[p + 1] << 8
        out.append(d[p + 3:p + 1 + n])
        p += 2 + n
    return out


class Machine:
    """A +2A/+3: eight 16K pages, ports #7FFD and #1FFD, the frame interrupt.
    The pages mapped at the moment live in self.m, the others in self.pages."""
    SPECIAL = ((0, 1, 2, 3), (4, 5, 6, 7), (4, 5, 6, 3), (4, 7, 6, 3))
    ROM = 8                             # stands for whichever ROM is paged in
    # The gate array holds the CPU on accesses to pages 4-7 while the picture is drawn.
    WAIT = (1, 0, 7, 6, 5, 4, 3, 2)
    FIRST = 14361                       # T-state of the frame the first picture byte is fetched at

    def __init__(self, tap, contention=True):
        code = tap_blocks(tap)[-1]
        self.pages = [[0] * 16384 for _ in range(9)]
        self.slots = [self.ROM, 5, 2, 0]
        self.p7ffd, self.p1ffd = 0x10, 0x04
        self.m = [0] * 65536
        self.m[LOADER:LOADER + len(code)] = list(code)
        self.sim = Simulator(self.m, {'PC': LOADER, 'SP': 0x5FF0},
                             config={'fast_djnz': False, 'fast_ldir': False, 'frame_duration': FRAME})
        self.r = self.sim.registers
        self.keys = set()               # (half-row, bit) of the keys held down
        self.ear = lambda t: 0
        self.outs = None                # list to log (T, value) written to port #FE
        self.contention = contention
        self.slow = [False] * 4         # per slot: a page the gate array contends
        self.sim.set_tracer(self)
        self.next_int = FRAME
        self.slow_ops = 0               # instructions executed from pages 4-7
        self.run(60)
        self.slow_ops = 0               # the loader runs from page 5; nothing after it should

    def remap(self):
        if self.p1ffd & 1:
            new = list(self.SPECIAL[self.p1ffd >> 1 & 3])
        else:
            new = [self.ROM, 5, 2, self.p7ffd & 7]
        for i in range(4):
            if new[i] != self.slots[i]:
                self.pages[self.slots[i]] = self.m[i << 14:(i + 1) << 14]
        for i in range(4):
            if new[i] != self.slots[i]:
                self.m[i << 14:(i + 1) << 14] = self.pages[new[i]]
        self.slots = new
        self.slow = [4 <= p <= 7 for p in new]

    def page(self, n):
        """The contents of a RAM page, wherever it is."""
        if n in self.slots:
            i = self.slots.index(n)
            return self.m[i << 14:(i + 1) << 14]
        return self.pages[n]

    def rk(self, a, b):
        """Memory of the Radio-86RK (pages 0 and 1) from address a up to b."""
        return bytes((self.page(0) + self.page(1))[a:b])

    def put(self, a, data):
        """Write into the memory of the Radio-86RK; it must be mapped."""
        assert self.slots[:2] == [0, 1]
        self.m[a:a + len(data)] = list(data)

    def read_port(self, r, port, *args):
        if port & 1:
            return 0xFF
        v = 0x1F
        for row, bit in self.keys:
            if not (port >> 8) & (1 << row):
                v &= ~(1 << bit)
        return v | 0xA0 | self.ear(r[25]) << 6

    def write_port(self, r, port, value, *args):
        if port & 1 == 0:
            if self.outs is not None:
                self.outs.append((r[25], value))
        elif port & 0xC002 == 0x4000:
            self.p7ffd = value
            self.remap()
        elif port & 0xF002 == 0x1000:
            self.p1ffd = value
            self.remap()

    def run(self, frames):
        r, m, op, sim = self.r, self.m, self.sim.opcodes, self.sim
        wait, first, contention = self.WAIT, self.FIRST, self.contention
        end = r[25] + frames * FRAME
        pc = r[24]
        while r[25] < end:
            if self.slow[pc >> 14]:
                self.slow_ops += 1
            if contention and self.slow[pc >> 14]:
                # A crude model: only the opcode fetch is held, not the other bus cycles.
                t = r[25] % FRAME - first
                if 0 <= t < 192 * 228 and t % 228 < 128:
                    r[25] += wait[t % 228 % 8]
            op[m[pc]]()
            if r[25] >= self.next_int:
                if r[25] < self.next_int + 32:
                    if r[26]:
                        sim.accept_interrupt(r, m, pc)
                else:
                    self.next_int += FRAME
            pc = r[24]

    def press(self, ch, frames=4):
        ch = '\r' if ch == '\n' else ch.upper()
        if ch in KEY:
            self.keys = {KEY[ch]}
        else:
            self.keys = {(7, 1)}        # SYMBOL SHIFT first
            self.run(2)
            self.keys = {KEY[SYM[ch]], (7, 1)}
        self.run(frames)
        self.keys = set()
        self.run(frames)

    def type(self, text, wait=20):
        for ch in text:
            self.press(ch)
        self.run(wait)

    def screen(self):
        video = self.page(1)
        rows = []
        for y in range(24):
            row = video[VIDEO - 0x4000 + y * PITCH:VIDEO - 0x4000 + y * PITCH + 64]
            rows.append(''.join(chr(c) if 32 <= c < 127 else ' ' for c in row).rstrip())
        return [r for r in rows if r]

    def pixels(self):
        """The Spectrum screen (page 5) as 192 rows of 256 bits packed in bytes."""
        scr = self.page(5)
        return [bytes(scr[((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2):][:32]) for y in range(192)]

    def play(self, signal, speed=1.0):
        """Put a recording (list of (seconds, level)) on the EAR input; return its length in frames."""
        t0, times, t = self.r[25] + 25 * FRAME, [], 0.0
        for dur, _ in signal:
            times.append(t)
            t += dur * CPU / speed
        levels = [lv for _, lv in signal]

        def ear(now):
            i = bisect.bisect_right(times, now - t0) - 1
            return levels[i] if 0 <= i < len(levels) and now - t0 < t else 0
        self.ear = ear
        return int(25 + t / FRAME + 40)

    def record(self):
        """Start logging the tape output."""
        self.outs = []

    def recorded(self):
        """The logged tape output as a list of (seconds, level)."""
        w = [(t, v >> 3 & 1) for t, v in self.outs if v in (0x00, 0x0F)]
        self.outs = None
        return [((w[i + 1][0] - w[i][0]) / CPU, w[i][1]) for i in range(len(w) - 1)] + [(0.001, w[-1][1])]



def pulses(machine):
    """The logged output as stretches of one MIC level: list of (seconds, level)."""
    out, start, level = [], None, None
    for t, v in machine.outs:
        lv = v >> 3 & 1
        if lv != level:
            if level is not None:
                out.append(((t - start) / CPU, level))
            start, level = t, lv
    machine.outs = None
    return out


def check(name, ok, detail=''):
    print('  %-58s %s %s' % (name, 'ok' if ok else 'FAILED', detail))
    return ok


def decode(signal):
    """Bytes of a recording: every second half-period is a bit."""
    bits = [lv for _, lv in signal[1::2]]
    return bytes(sum(bits[i + k] << (7 - k) for k in range(8)) for i in range(0, len(bits) - 7, 8))


def main(tap):
    ok = True
    rk = os.path.join(HERE, '..', 'rk86_plus3')

    m = Machine(tap)
    ok &= check('the Monitor starts', m.screen() == ['radio-86rk', '-->'])
    m.type('F1000,10FF,5A\n')
    m.type('M1080\n12\n.')
    m.type('S1000,10FF,12\n')
    data = bytes([0x5A] * 128 + [0x12] + [0x5A] * 127)
    ok &= check('directives F, M and S', m.rk(0x1000, 0x1100) == data and m.screen()[-2].split() == ['1080'])
    m.type('T1000,10FF,3000\n')
    m.type('D3080,3081\n')
    px = m.pixels()
    ok &= check('the Spectrum screen is drawn, from fast memory only',
                sum(1 for row in px if any(row)) > 30 and set(m.page(5)[0x1800:0x1B00]) == {0x0F} and m.slow_ops == 0)
    ok &= check('directives T and D', m.rk(0x3000, 0x3100) == data and m.screen()[-2].split() == ['3080', '12', '5A'])

    # Writing: against the format and the timing of the real machine.
    data = bytes(range(256)) + b'\x00\xff\x55\xaa'
    m.put(0x2000, data)
    m.type('O2000,2103', wait=0)
    m.record()
    m.press('\n')
    m.run(int(len(data) + 270) * 8 * 896e-6 * 50 + 60)
    sig = m.recorded()
    want = rk2wav.tape_bytes(0x2000, data, rk2wav.checksum(data))
    ok &= check('directive O: the bytes on the tape', decode(sig) == want, '(%d bytes)' % len(want))
    ref = rk2wav.levels(want)
    ok &= check('directive O: the levels', [lv for _, lv in sig] == [lv for _, lv in ref])
    data_part = slice(2 * 8 * 261, 2 * 8 * (261 + len(data)) - 1)      # past the pilot and the header
    err = [abs(a[0] / b[0] - 1) for a, b in zip(sig[data_part], ref[data_part])]
    total = sum(d for d, _ in sig[data_part]) / sum(d for d, _ in ref[data_part])
    ok &= check('directive O: timing as on the Radio-86RK', max(err) < 0.01 and abs(total - 1) < 0.005,
                '(worst half-period %.2f%%, overall %+.2f%%)' % (max(err) * 100, (total - 1) * 100))

    # Reading what rk2wav.py makes, at several tape speeds.
    start, prog, cs = rk2wav.read_rk(os.path.join(rk, 'DUMPCOR1.RK'))
    ref = rk2wav.levels(rk2wav.tape_bytes(start, prog, cs))
    window = []
    for speed in (0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30):
        m = Machine(tap)
        m.type('I', wait=0)
        frames = m.play(ref, speed)
        m.press('\n')
        m.run(frames)
        good = m.rk(start, start + len(prog)) == prog and m.screen()[-2].strip() == '%04X' % cs
        if good:
            window.append(speed)
        if speed in (0.90, 1.00, 1.10):
            ok &= check('directive I: a recording at speed %.2f' % speed, good)
    print('  %-58s    %s' % ('directive I reads at speeds', ' '.join('%.2f' % s for s in window)))
    m = Machine(tap)
    m.type('I', wait=0)
    frames = m.play([(d, lv ^ 1) for d, lv in ref])
    m.press('\n')
    m.run(frames)
    ok &= check('directive I: an inverted recording',
                m.rk(start, start + len(prog)) == prog and m.screen()[-2].strip() == '%04X' % cs)

    # The TZX file holds the same pulses.
    tzx = os.path.join(tempfile.mkdtemp(), 'x.tzx')
    rk2wav.write_tzx(tzx, ref)
    d, p, got = open(tzx, 'rb').read(), 10, []
    while p < len(d):
        if d[p] == 0x20:
            p += 3
        else:
            assert d[p] == 0x13
            got += [d[p + 2 + 2 * i] | d[p + 3 + 2 * i] << 8 for i in range(d[p + 1])]
            p += 2 + 2 * d[p + 1]
    want = [round(x * 3500000) for x in rk2wav.pulses(ref)]
    ok &= check('rk2wav.py: the TZX holds the same pulses', got == want,
                '(%d pulses, %d bytes; the WAV is %d)' % (len(got), len(d), int(sum(x for x, _ in ref) * 44100)))

    m = Machine(tap)
    m.type('I', wait=0)
    m.press('\n')
    m.run(int(m.play(rk2wav.levels(rk2wav.tape_bytes(start, prog, cs ^ 0x0100)))))
    ok &= check('directive I: a wrong checksum is reported', m.screen()[-2].strip().endswith('?'))

    # BASIC: runs, saves a program and reads it back.
    start, prog, cs = rk2wav.read_rk(os.path.join(rk, 'BASIC80.RKR'), BASIC_PATCH)
    m = Machine(tap)
    m.type('I', wait=0)
    frames = m.play(rk2wav.levels(rk2wav.tape_bytes(start, prog, cs)))
    m.press('\n')
    m.run(frames)
    ok &= check('BASIC loads', m.rk(start, start + len(prog)) == prog)
    m.type('G0\n', wait=100)
    m.type('\n', wait=40)
    m.type('PRINT 2+2*3\n', wait=40)
    ok &= check('BASIC: PRINT 2+2*3', m.screen()[-3:] == ['PRINT 2+2*3', ' 8', 'OK'])
    m.type('10 FOR I=1 TO 3\n20 PRINT I*I;\n30 NEXT\n')
    m.type('MSAVE', wait=0)
    m.record()
    m.press('\n')
    m.run(400)
    saved = m.recorded()
    m.type('NEW\n')
    m.type('LIST\n', wait=40)
    empty = m.screen()[-2:] == ['LIST', 'OK']
    m.type('MLOAD', wait=0)
    frames = m.play(saved)
    m.press('\n')
    m.run(frames)
    m.type('RUN\n', wait=60)
    slow = m.slow_ops
    ok &= check('BASIC: MSAVE, NEW, MLOAD, RUN', empty and m.screen()[-3:-1] == ['RUN', ' 1  4  9'],
                '(%.1f s on the tape)' % sum(d for d, _ in saved))
    ok &= check('BASIC: nothing ran from the slow pages', slow == 0)

    # "Piton" from the green_svema tape, patched as in ../rk86_plus3/piton.asm.
    piton = os.path.join(HERE, '..', 'green_svema', 'side_1', 'svema_26', '02_RADIO_FILE.bin')
    start, prog, cs = rk2wav.read_rk(piton, PITON_PATCH, raw=0x1100)
    m = Machine(tap)
    m.type('I', wait=0)
    frames = m.play(rk2wav.levels(rk2wav.tape_bytes(start, prog, cs)))
    m.press('\n')
    m.run(frames)
    loaded = m.rk(start, start + len(prog)) == prog
    m.type('G1100\n', wait=60)
    title = '*** piton ***' in m.screen()
    m.type('5', wait=30)
    m.type('\n', wait=150)
    rows = m.screen()
    ok &= check('"Piton" loads and plays', loaded and title
                and len(rows) == 24 and rows[0].startswith('+' * 20) and rows[5].startswith('+'))

    # Programs that only need to start: put straight into memory.
    start, prog, cs = rk2wav.read_rk(os.path.join(rk, 'RDISK1.PKI'))
    m = Machine(tap)
    m.put(start, prog)
    m.type('G3600\n', wait=100)
    m.type('D', wait=60)
    ok &= check('RAMDOS starts and lists the disk', 'RAMDOS' in m.screen()[0] and 'PRINT' in m.screen()[3])
    start, prog, cs = rk2wav.read_rk(os.path.join(rk, 'DUMPCOR1.RK'))
    m = Machine(tap)
    m.put(start, prog)
    m.type('G7400\n', wait=100)
    shown = m.screen()[1].split()[:3] == ['0000', '00', '00']
    m.type('.', wait=40)
    ok &= check('the memory editor starts and exits to the Monitor', shown and m.screen() == ['radio-86rk', '-->'])
    return ok


# The same changes as in ../rk86_plus3/piton.asm: 24 rows, 32K video memory, O P Q A instead of arrows.
PITON_PATCH = ['113E=C277', '114B=C47E', '1156=18', '115C=18', '1167=947E',
               '117E=4F', '1186=50', '118E=51', '1196=41', '11F5=E777', '1274=37']

if __name__ == '__main__':
    sys.exit(0 if main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'rk86mon.tap')) else 1)
