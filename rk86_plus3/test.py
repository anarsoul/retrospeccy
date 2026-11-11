#!/usr/bin/env python3
"""Check rk86.tap on SkoolKit's Z80 core (pip install skoolkit).

The machine model is the one of ../rk86mon_plus3/test.py: a +2A/+3 with its
pages and paging ports, started through the loader on the tape, with code in
pages 4-7 slowed down while the picture is drawn.

What is checked: the Monitor starts and draws on the Spectrum screen, nothing
runs from the slow pages, directives F, M, S and O work, "Piton" loads from
piton.tap with directive I and plays, BASIC, RAMDOS and the memory editor
start.

Usage: test.py [rk86.tap]
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MON = os.path.join(HERE, '..', 'rk86mon_plus3')
sys.path.insert(0, MON)
import rk2wav                                                   # noqa: E402

_spec = importlib.util.spec_from_file_location('rk86mon_test', os.path.join(MON, 'test.py'))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Machine, check, pulses, tap_blocks, CPU = _mod.Machine, _mod.check, _mod.pulses, _mod.tap_blocks, _mod.CPU


def spectrum_tape(path):
    """A TAP file as the ROM saves it: list of (seconds, level)."""
    sig, level = [], 0

    def pulse(t):
        nonlocal level
        level ^= 1
        sig.append((t / 3500000, level))
    d, p = open(path, 'rb').read(), 0
    while p < len(d):
        n = d[p] | d[p + 1] << 8
        block = d[p + 2:p + 2 + n]
        p += 2 + n
        for _ in range(8063 if block[0] < 128 else 3223):
            pulse(2168)
        pulse(667)
        pulse(735)
        for byte in block:
            for bit in range(7, -1, -1):
                t = 1710 if byte >> bit & 1 else 855
                pulse(t)
                pulse(t)
        pulse(3500000)                                          # a second of silence
    return sig


def spectrum_blocks(signal):
    """Decode what SA-BYTES wrote: list of blocks (flag, data, checksum)."""
    blocks, bits, i = [], [], 0
    durs = [round(d * CPU) for d, _ in signal]
    while i < len(durs) - 1:
        if 600 < durs[i] < 780 and 650 < durs[i + 1] < 830 and i > 100:      # the sync pulses
            i += 2
            bits = []
            while i < len(durs) - 1 and durs[i] < 2100 and abs(durs[i] - durs[i + 1]) < 300:
                bits.append(1 if durs[i] > 1300 else 0)
                i += 2
            blocks.append(bytes(sum(bits[j + k] << (7 - k) for k in range(8)) for j in range(0, len(bits) - 7, 8)))
        else:
            i += 1
    return blocks


def main(tap):
    ok = True
    m = Machine(tap)
    rows = m.screen()
    px = m.pixels()
    ok &= check('the Monitor starts', len(rows) == 2 and rows[1] == '->')
    ok &= check('the Spectrum screen is drawn, from fast memory only',
                sum(1 for row in px if any(row)) > 10 and m.slow_ops == 0)
    m.type('F1000,10FF,5A\n')
    m.type('M1080\n12\n.')
    m.type('S1000,10FF\n')
    data = bytes([0x5A] * 128 + [0x12] + [0x5A] * 127)
    ok &= check('directives F, M and S', m.rk(0x1000, 0x1100) == data
                and m.screen()[-2].split() == ['1000', '10FF', '%04X' % rk2wav.checksum(data)])

    m.type('O1000,10FF', wait=0)
    m.record()
    m.press('\n')
    m.run(500)
    blocks = spectrum_blocks(pulses(m))
    ok &= check('directive O: a header and the data, as the ROM writes them',
                len(blocks) == 2 and blocks[0][:12] == b'\x00\x03RADIO FILE' and blocks[1][1:-1] == data)

    piton = os.path.join(HERE, 'piton.tap')
    prog = tap_blocks(piton)[-1]
    m = Machine(tap)
    m.type('I', wait=0)
    frames = m.play(spectrum_tape(piton))
    m.press('\n')
    m.run(frames)
    loaded = m.rk(0x1100, 0x1100 + len(prog)) == prog
    ok &= check('directive I: piton.tap', loaded and m.screen()[-2].split()[:2] == ['1100', '128E'])
    m.type('G1100\n', wait=60)
    title = '*** piton ***' in m.screen()
    m.type('5', wait=30)
    m.type('\n', wait=150)
    rows = m.screen()
    video = m.page(1)
    food = [i for i in range(0x37C2, 0x37C2 + 24 * 78) if video[i] == 0x7F]
    y, x = divmod(food[0] - 0x37C2, 78) if food else (0, 0)
    px = m.pixels()
    solid = bool(food) and all(px[y * 8 + r][x >> 1] & (0xF0 >> 4 * (x & 1)) == (0xF0 >> 4 * (x & 1)) for r in range(8))
    ok &= check('"Piton" plays; the food is a solid block', title and len(rows) == 24 and solid)
    ok &= check('nothing ran from the slow pages', m.slow_ops == 0)

    # Programs that only need to start: put straight into memory.
    basic_patch = '12D0=C3EE19 19EE=9F2803CB2FC93CC9 096E=C3F619 19F6=8FB7E81E18C3D802'.split()
    start, prog, cs = rk2wav.read_rk(os.path.join(HERE, 'BASIC80.RKR'), basic_patch)
    m = Machine(tap)
    m.put(start, prog)
    m.type('G0\n', wait=100)
    m.type('\n', wait=40)
    m.type('PRINT 2+2*3\n', wait=40)
    ok &= check('BASIC: PRINT 2+2*3', m.screen()[-3:] == ['PRINT 2+2*3', ' 8', 'OK'])
    start, prog, cs = rk2wav.read_rk(os.path.join(HERE, 'RDISK1.PKI'))
    m = Machine(tap)
    m.put(start, prog)
    m.type('G3600\n', wait=100)
    m.type('D', wait=60)
    ok &= check('RAMDOS starts and lists the disk', 'RAMDOS' in m.screen()[0] and 'PRINT' in m.screen()[3])
    start, prog, cs = rk2wav.read_rk(os.path.join(HERE, 'DUMPCOR1.RK'))
    m = Machine(tap)
    m.put(start, prog)
    m.type('G7400\n', wait=100)
    shown = m.screen()[1].split()[:3] == ['0000', '00', '00']
    m.type('.', wait=40)
    ok &= check('the memory editor starts and exits to the Monitor', shown and m.screen()[-1] == '->')
    return ok


if __name__ == '__main__':
    sys.exit(0 if main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'rk86.tap')) else 1)
