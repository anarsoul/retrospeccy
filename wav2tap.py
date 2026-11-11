#!/usr/bin/env python3
"""Decode a ZX Spectrum tape recording (WAV) into a TAP file.

Written for worn tapes where ordinary converters lose sync: the "0" bits
(high frequency) are recorded much weaker than the "1" bits and ride on a
low-frequency wave without crossing zero.  The signal is therefore high-pass
filtered (moving average removed) and zero crossings are detected with a
hysteresis relative to the local signal level.

Usage:
    wav2tap.py tape.wav                 # list blocks, write tape.tap
    wav2tap.py tape.wav -o out.tap
    wav2tap.py tape.wav -x DIR          # also write every block body to DIR
    wav2tap.py -n *.wav                 # only list blocks
    wav2tap.py -s 2 tape.wav            # force double-speed ("turbo") decoding

Standard ROM timings are assumed, at normal or double speed (the speed is
detected automatically, or set with -s).  Requires numpy.
"""
import argparse
import os
import sys
import wave
from functools import reduce

import numpy as np

# Pulse lengths are measured in samples at 44100 Hz (other rates are scaled).
PILOT_MIN, PILOT_MAX = 19, 36      # pilot pulse is ~27 samples
BIT_MIN, BIT_MAX = 13, 64          # a bit is two pulses: "0" ~22, "1" ~44 samples
BIT_THRESHOLD = 33.5
MIN_PILOT_PULSES = 200
SYNC_MAX = 17                      # sync pulses are ~8 and ~9 samples
PILOT_PAIR_MIN = 49.5              # two pilot pulses ~54 samples, a "1" bit ~44
GLITCH_MAX = 3.5                   # shorter pulses are clicks, not signal
MIN_BLOCK = 8                      # shorter blocks are kept only if the checksum is right
PILOT_RUN = 12                     # this many in a row inside data = next pilot
SPEEDS = (1.0, 2.0)                # normal and double-speed ("turbo") recordings


def load(path):
    with wave.open(path) as w:
        p = w.getparams()
        raw = w.readframes(p.nframes)
    if p.sampwidth == 1:
        d = np.frombuffer(raw, dtype='u1').astype(float) - 128
    elif p.sampwidth == 2:
        d = np.frombuffer(raw, dtype='<i2').astype(float)
    else:
        sys.exit('%s: only 8- and 16-bit WAV files are supported' % path)
    if p.nchannels > 1:
        d = d.reshape(-1, p.nchannels).mean(axis=1)
    return d, p.framerate


def movavg(x, n):
    c = np.cumsum(np.insert(x, 0, 0.0))
    out = (c[n:] - c[:-n]) / n
    pad = n // 2
    return np.concatenate([np.full(pad, out[0]), out,
                           np.full(len(x) - len(out) - pad, out[-1])])


def find_pulses(d, rate, speed=1.0, hp=24, hyst=0.12, env=200):
    """Return [(start, length)] in samples (fractional) for every half-wave."""
    k = rate / 44100 / speed
    y = d - movavg(d, max(3, int(hp * k) | 1))      # remove low-frequency wander
    if k >= 1:
        y = movavg(y, 3)                            # and a little hiss
    level = np.sqrt(movavg(y * y, max(3, int(env * k) | 1))) + 1e-9
    yy, tt = y.tolist(), (hyst * level).tolist()
    out, state, last = [], 0, 0.0
    for i, v in enumerate(yy):
        t = tt[i]
        if v > t:
            s = 1
        elif v < -t:
            s = -1
        else:
            continue
        if s != state:
            j = i                                   # walk back to the real zero crossing
            while j > 0 and i - j < 64 and yy[j - 1] * s > 0:
                j -= 1
            x = j - yy[j] / (yy[j] - yy[j - 1]) if j > 0 and yy[j] != yy[j - 1] else float(j)
            if state:
                out.append((last, x - last))
            last, state = x, s
    return merge_glitches(out, GLITCH_MAX * k)


def merge_glitches(pl, limit):
    """A click on the tape shows up as a pulse far shorter than any real one,
    splitting the pulse it sits on.  Glue such a pulse to its neighbours."""
    out, i, n = [], 0, len(pl)
    while i < n:
        start, length = pl[i]
        while i + 2 < n and pl[i + 1][1] < limit:
            length += pl[i + 1][1] + pl[i + 2][1]
            i += 2
        out.append((start, length))
        i += 1
    return out


def find_blocks(pl, rate, speed=1.0):
    """Return [(time, data_bytes)] for every pilot + sync + data sequence."""
    k = rate / 44100 / speed
    n = len(pl)

    def length(j):
        return pl[j][1] / k

    def is_pilot(j):
        return PILOT_MIN <= length(j) <= PILOT_MAX

    res, i = [], 0
    while i < n:
        # Pilot: a long run of pilot pulses.  A stray pulse inside it (a tape
        # dropout) is not the sync unless two short pulses follow each other.
        j, count = i, 0
        while j + 2 < n:
            if is_pilot(j):
                count += 1
                j += 1
            elif (count >= MIN_PILOT_PULSES and length(j) < SYNC_MAX
                  and length(j + 1) < SYNC_MAX):
                break
            elif count >= MIN_PILOT_PULSES and is_pilot(j + 1) and is_pilot(j + 2):
                j += 1                              # glitch, the pilot goes on
            else:
                break
        if count < MIN_PILOT_PULSES or j + 2 >= n or is_pilot(j):
            i = max(j, i + 1)
            continue
        q, bits, run = j + 2, [], 0                 # skip the two sync pulses
        while q + 1 < n:
            a = length(q) + length(q + 1)
            if not BIT_MIN <= a <= BIT_MAX:
                break
            # The next block's pilot may follow without a pause; its pulses are
            # longer than a "1" bit.  Stop before it instead of reading it as data.
            run = run + 1 if a > PILOT_PAIR_MIN else 0
            if run >= PILOT_RUN:
                q -= 2 * (run - 1)
                del bits[len(bits) - (run - 1):]
                break
            bits.append(a > BIT_THRESHOLD)
            q += 2
        data = bytes(sum(bits[x + y] << (7 - y) for y in range(8))
                     for x in range(0, len(bits) - 7, 8))
        # A few stray bytes with a wrong checksum are noise (a cut-off pilot,
        # the tail of an erased recording), not a block worth keeping.
        if len(data) >= MIN_BLOCK or checksum_ok(data):
            res.append((pl[i][0] / rate, data))
        i = max(q, i + 1)
    return res


def decode(path, speed=None):
    """Decode a WAV file.  speed=None tries the known speeds and keeps the best."""
    d, rate = load(path)
    best = None
    for sp in ([speed] if speed else SPEEDS):
        blocks = find_blocks(find_pulses(d, rate, sp), rate, sp)
        score = (sum(len(b) for _, b in blocks if checksum_ok(b)),
                 sum(len(b) for _, b in blocks))
        if best is None or score > best[0]:
            best = (score, sp, blocks)
    return best[2], best[1]


def checksum_ok(data):
    return len(data) > 1 and reduce(lambda a, c: a ^ c, data) == 0


def describe(data):
    if len(data) == 19 and data[0] == 0 and checksum_ok(data):
        kind = {0: 'Program', 1: 'Number array', 2: 'Character array',
                3: 'Bytes'}.get(data[1], 'type %d' % data[1])
        w = lambda o: data[o] | data[o + 1] << 8
        return 'header: %s %r len=%d p1=%d p2=%d' % (
            kind, data[2:12].decode('latin1'), w(12), w(14), w(16))
    return 'data: flag=#%02X, %d bytes, checksum %s' % (
        data[0], len(data) - 2, 'OK' if checksum_ok(data) else 'BAD')


def safe(name):
    return ''.join(c if c.isalnum() or c in '.-_$' else '_'
                   for c in name.strip()) or 'noname'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('wav', nargs='+')
    ap.add_argument('-o', '--output', help='TAP file name (single input only)')
    ap.add_argument('-x', '--extract', metavar='DIR',
                    help='write block bodies (without flag and checksum) to DIR')
    ap.add_argument('-n', '--no-tap', action='store_true', help='only list blocks')
    ap.add_argument('-s', '--speed', type=float,
                    help='tape speed relative to the ROM routines (default: try 1 and 2)')
    args = ap.parse_args()
    if (args.output or args.extract) and len(args.wav) > 1:
        ap.error('-o and -x need a single input file')
    bad = 0
    for path in args.wav:
        blocks, speed = decode(path, args.speed)
        print('%s%s' % (path, '' if speed == 1 else '  (speed x%g)' % speed))
        name = 'noname'
        for n, (t, data) in enumerate(blocks, 1):
            print('  %02d  %7.2fs  %s' % (n, t, describe(data)))
            bad += not checksum_ok(data)
            if args.extract:
                os.makedirs(args.extract, exist_ok=True)
                if len(data) == 19 and data[0] == 0:
                    name = safe(data[2:12].decode('latin1'))
                else:
                    with open(os.path.join(args.extract, '%02d_%s.bin' % (n - 1, name)), 'wb') as f:
                        f.write(data[1:-1])
                    name = 'noname'
        if not args.no_tap:
            out = args.output or os.path.splitext(path)[0] + '.tap'
            with open(out, 'wb') as f:
                for _, data in blocks:
                    f.write(len(data).to_bytes(2, 'little') + data)
            print('  -> %s' % out)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
