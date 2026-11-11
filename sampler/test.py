#!/usr/bin/env python3
"""Check rle.tap and delta.tap on SkoolKit's Z80 core (pip install skoolkit).

A test signal is fed to the EAR bit as a function of the T-state counter.
For each sampler the script records it, compares the buffer with a model of
the format written here in Python, plays the buffer back and compares every
output with the recorded sample and its time with the time of that sample.
The times must agree to the T-state: the padding in the sources depends on it.

Usage: test.py [rle.tap] [delta.tap]
"""
import bisect
import collections
import random
import sys

from skoolkit.simulator import Simulator

ORG, BUF, BUFTOP = 64000, 26000, 0xF900
KEY_HELD = 300000               # T-states the stop key stays down


def code_block(tap):
    """Body of the last block of a TAP file."""
    d, p, body = open(tap, 'rb').read(), 0, b''
    while p < len(d):
        n = d[p] | d[p + 1] << 8
        body = d[p + 3:p + 1 + n]
        p += 2 + n
    return body


class Signal:
    """EAR level as a function of time: a list of level change times."""
    def __init__(self, seed=1):
        self.rnd, self.t, self.tg = random.Random(seed), 200000, []

    def tone(self, half_period, n):
        for _ in range(n):
            self.tg.append(self.t)
            self.t += half_period
        return self

    def noise(self, n, lo, hi):
        for _ in range(n):
            self.tg.append(self.t)
            self.t += self.rnd.randint(lo, hi)
        return self

    def pause(self, t):
        self.t += t
        return self

    def level(self, t):
        return bisect.bisect_right(self.tg, t) & 1


class Ports:
    def __init__(self, signal, key):
        self.signal, self.key, self.ins, self.outs = signal, key, [], []

    def read_port(self, registers, port, *args):
        t = registers[25]
        level = self.signal.level(t)
        self.ins.append((t, level))
        value = 0xBF | level << 6
        if self.key is not None and self.key <= t < self.key + KEY_HELD:
            value &= ~1
        return value

    def write_port(self, registers, port, value, *args):
        self.outs.append((registers[25], value))


def run(code, entry, signal, key=None, memory=None):
    """Call entry; return memory, port log, T-states taken and BC."""
    if memory is None:
        memory = [0] * 65536
        memory[ORG:ORG + len(code)] = list(code)
    memory[0xFF00:0xFF02] = [0x00, 0x80]            # return address #8000
    sim = Simulator(memory, {'SP': 0xFF00, 'PC': entry},
                    config={'fast_djnz': False, 'fast_ldir': False})
    ports = Ports(signal, key)
    sim.set_tracer(ports)
    sim.run(entry, 0x8000)
    r = sim.registers
    return memory, ports, r[25], r[2] << 8 | r[3]


def samples_of(ports, key):
    """Reads made by the recording loop: not the key-release waits around it."""
    ins = ports.ins[1:]
    if key is None:
        return ins[:-1]
    return [x for x in ins if x[0] < key]


def check(name, ok, detail=''):
    print('  %-52s %s %s' % (name, 'ok' if ok else 'FAILED', detail))
    return ok


# ------------------------------------------------------------------ rle.tap

def rle_model(data):
    """The format of rle.asm, and the path the recorder takes for each byte."""
    out, paths, b, prev, prev2, ctl = [], [], 0xFF, None, None, None
    for c in data:
        if b & 0x80:
            if c == prev and b != 0xFF:
                b += 1
                out[ctl] = b
                paths.append('repeat: one more')
                continue
            path = 'repeat: new run'
        else:
            if c == prev and c == prev2:
                if b == 2:
                    out.pop()
                    paths.append('plain: all of it becomes a repeat')
                else:
                    out[ctl] = b - 2
                    ctl = len(out) - 2
                    paths.append('plain: the tail becomes a repeat')
                b = 0x83
                out[ctl] = b
                continue
            if b != 127:
                b += 1
                out[ctl] = b
                out.append(c)
                prev2, prev = prev, c
                paths.append('plain: one more')
                continue
            path = 'plain: new run'
        ctl, b = len(out), 1
        out += [1, c]
        prev, prev2 = c, c ^ 0xFF
        paths.append(path)
    return out + [0], paths


def rle_decode_paths(buf):
    paths, p = [], 0
    while buf[p]:
        c = buf[p]
        if c & 0x80:
            paths += ['new repeat'] + ['repeat'] * ((c & 127) - 1)
            p += 2
        else:
            paths += ['new plain run'] + ['plain'] * (c - 1)
            p += 1 + c
    return paths


def test_rle(tap):
    print(tap)
    code, ok = code_block(tap), True
    s = Signal().tone(1750, 400).pause(900000).noise(3000, 150, 4000).pause(6000000)
    s.tone(2000, 600).noise(12000, 40, 400).noise(3000, 300, 3000).pause(300000).noise(500, 1000, 9000)
    key = s.t + 100000
    mem, rec, t, bc = run(code, ORG, s, key)
    ins = samples_of(rec, key)
    n = len(ins) // 8
    data = [sum(ins[i * 8 + k][1] << k for k in range(8)) for i in range(n)]
    model, paths = rle_model(data)
    ok &= check('record: buffer equals the model',
                mem[BUF:BUF + len(model)] == model and bc == len(model),
                '(%d bytes of sound -> %d, %.1f s)' % (n, len(model), t / 3.5e6))
    gaps = collections.defaultdict(set)
    for i in range(n - 1):
        gaps[paths[i]].add(ins[i * 8 + 8][0] - ins[i * 8 + 7][0])
    inside = {ins[i][0] - ins[i - 1][0] for i in range(1, n * 8) if i % 8}
    rgap = set().union(*gaps.values())
    ok &= check('record: one sample period, one byte gap',
                len(inside) == 1 and len(rgap) == 1, '(%s T, %s T; %d paths)' % (inside, rgap, len(gaps)))

    mem, play, t, bc = run(code, ORG + 3, s, None, mem)
    outs = play.outs
    played = [sum((outs[i * 8 + k][1] >> 4 & 1) << k for k in range(8)) for i in range(len(outs) // 8)]
    ok &= check('play: every sample as recorded', played == data and len(outs) == n * 8)
    ok &= check('play: only the speaker bit is written', all(v & ~0x10 == 0 for _, v in outs))
    drift = {(outs[k][0] - outs[0][0]) - (ins[k][0] - ins[0][0]) for k in range(min(len(outs), n * 8))}
    kinds = set(rle_decode_paths(model))
    ok &= check('play: same timing as the recording', drift == {0}, '(%d decoder paths)' % len(kinds))

    s = Signal(2).noise(400000, 40, 400)                     # nothing to pack: the buffer fills up
    mem, rec, t, bc = run(code, ORG, s)
    ins = samples_of(rec, None)
    n = len(ins) // 8
    data = [sum(ins[i * 8 + k][1] << k for k in range(8)) for i in range(n)]
    model, paths = rle_model(data)
    ok &= check('buffer full: stops below the code',
                mem[BUF:BUF + len(model)] == model and BUFTOP <= BUF + bc <= BUFTOP + 3,
                '(%d bytes in %.1f s, worst case x%.3f)' % (bc, t / 3.5e6, bc / n))
    full = len(run(code, ORG + 3, s, None, mem)[1].outs)
    mem, play, t, bc = run(code, ORG + 3, s, 3500000, mem)
    ok &= check('play: a key stops it', len(play.outs) < full // 2 and t < 3500000 + KEY_HELD + 10000)
    mem, rec, t, bc = run(code, ORG, s, 100)
    ok &= check('key at once: empty recording', mem[BUF] == 0 and bc == 1)
    ok &= check('play: empty recording', not run(code, ORG + 3, s, None, mem)[1].outs)
    return ok


# ---------------------------------------------------------------- delta.tap

def delta_model(ins):
    """The format of delta.asm, the samples that start an interval and their kind."""
    level, count = ins[0][1], 1
    out, events, kinds = [level << 6], [ins[0]], ['start']
    for t, e in ins[1:]:
        if e != level:
            out.append(count)
            level, count = e, 1
            events.append((t, e))
            kinds.append('change')
        else:
            count += 1
            if count == 255:
                out.append(255)
                count = 1
                events.append((t, e))
                kinds.append('255')
    return out + [0], events, kinds


def test_delta(tap):
    print(tap)
    code, ok = code_block(tap), True
    s = Signal().tone(1750, 400).pause(900000).noise(3000, 150, 4000).pause(6000000)
    s.tone(49 * 254, 6).tone(49 * 255, 6).tone(49 * 253, 6).noise(12000, 40, 400)
    s.noise(3000, 300, 3000).pause(300000).noise(500, 1000, 14000)
    key = s.t + 100000
    mem, rec, t, bc = run(code, ORG, s, key)
    ins = samples_of(rec, key)
    model, events, kinds = delta_model(ins)
    ok &= check('record: buffer equals the model',
                mem[BUF:BUF + len(model)] == model and bc == len(model),
                '(%d level changes -> %d bytes, %.1f s)' % (kinds.count('change'), len(model), t / 3.5e6))
    starts = {t for t, _ in events}
    short = {ins[i][0] - ins[i - 1][0] for i in range(1, len(ins)) if ins[i - 1][0] not in starts}
    long = {ins[i][0] - ins[i - 1][0] for i in range(1, len(ins)) if ins[i - 1][0] in starts}
    ok &= check('record: one sample period, one long sample',
                len(short) == 1 and len(long) == 1, '(%s T, %s T)' % (short, long))

    mem, play, t, bc = run(code, ORG + 3, s, None, mem)
    outs = play.outs
    ok &= check('play: every level as recorded',
                [v >> 4 & 1 for _, v in outs] == [e for _, e in events])
    ok &= check('play: only the speaker bit is written', all(v & ~0x10 == 0 for _, v in outs))
    drift = {(outs[i][0] - outs[0][0]) - (events[i][0] - events[0][0]) for i in range(min(len(outs), len(events)))}
    ok &= check('play: same timing as the recording', drift == {0})

    s = Signal(2).noise(400000, 40, 400)
    mem, rec, t, bc = run(code, ORG, s)
    model, events, kinds = delta_model(samples_of(rec, None))
    ok &= check('buffer full: stops below the code',
                mem[BUF:BUF + bc - 1] == model[:bc - 1] and BUF + bc == BUFTOP + 1,
                '(%d bytes in %.1f s)' % (bc, t / 3.5e6))
    full = len(run(code, ORG + 3, s, None, mem)[1].outs)
    mem, play, t, bc = run(code, ORG + 3, s, 3500000, mem)
    ok &= check('play: a key stops it', len(play.outs) < full // 2 and t < 3500000 + KEY_HELD + 10000)
    mem, rec, t, bc = run(code, ORG, s, 100)
    ok &= check('key at once: empty recording', mem[BUF + 1] == 0 and bc == 2)
    ok &= check('play: empty recording', len(run(code, ORG + 3, s, None, mem)[1].outs) == 1)
    return ok


if __name__ == '__main__':
    taps = sys.argv[1:] or ['rle.tap', 'delta.tap']
    results = [test_delta(t) if 'delta' in t else test_rle(t) for t in taps]
    sys.exit(0 if all(results) else 1)
