#!/usr/bin/env python3
"""Render a WAV file the way rle.tap or delta.tap would record and play it.

No emulator is involved: the script follows the timing and the buffer format
of the two samplers (test.py checks the Z80 code against the same model).

    render.py music.wav                       # -> music.delta.wav
    render.py music.wav -m rle                # -> music.rle.wav
    render.py music.wav --highpass 150 --lowpass 4000             # filters before the comparator
    render.py music.wav --post-highpass 150 --post-lowpass 4000   # filters after the speaker
    render.py music.wav -s 45 -l 30           # 30 seconds from 0:45
    render.py music.wav --tap sound.tap       # also the buffer, for menu item 4

The input is mixed to mono, optionally filtered and turned into one
bit by a comparator with hysteresis - a stand-in for the EAR input.  With
--tap the recording stops when the 37744-byte buffer is full, as on the real
thing, and the rendered WAV ends there too.  Requires numpy.
"""
import argparse
import os
import struct
import sys
import wave
from functools import reduce

import numpy as np

CPU = 3500000                   # T-states per second
BUFFER = 0xF900 - 26000         # bytes from BUF to BUFTOP
# rle.asm: 8 samples 43 T apart, then 268 T to the first sample of the next byte
RLE_BIT, RLE_BYTE = 43, 7 * 43 + 268
# delta.asm: a sample every 49 T, 123 T after a level change or a 255
DELTA_SAMPLE, DELTA_LONG = 49, 123


def load(path, start, length):
    with wave.open(path) as w:
        p = w.getparams()
        w.setpos(min(int(start * p.framerate), p.nframes))
        n = p.nframes if length is None else int(length * p.framerate)
        raw = w.readframes(n)
    if p.sampwidth == 1:
        d = np.frombuffer(raw, dtype='u1').astype(float) - 128
    elif p.sampwidth == 2:
        d = np.frombuffer(raw, dtype='<i2').astype(float)
    else:
        sys.exit('%s: only 8- and 16-bit WAV files are supported' % path)
    if p.nchannels > 1:
        d = d.reshape(-1, p.nchannels).mean(axis=1)
    return d - d.mean(), p.framerate


def band(d, rate, low=None, high=None, order=8):
    """Zero-phase filter with Butterworth magnitude responses: high-pass at
    low, low-pass at high (either may be omitted)."""
    if not low and not high:
        return d
    f = np.fft.rfftfreq(len(d), 1 / rate)
    g = np.ones(len(f))
    if high:
        g /= np.sqrt(1 + (f / high) ** (2 * order))
    if low:
        g[1:] /= np.sqrt(1 + (low / f[1:]) ** (2 * order))
        g[0] = 0
    return np.fft.irfft(np.fft.rfft(d) * g, len(d))


def comparator(d, rate, hyst):
    """Return (starting level, times of the level changes in T-states)."""
    h = hyst * d.std()
    s = np.zeros(len(d), np.int8)
    s[d > h] = 1
    s[d < -h] = -1
    idx = np.flatnonzero(s)
    if not len(idx):
        return 0, np.zeros(0)
    v = s[idx]
    ch = np.flatnonzero(np.diff(v)) + 1
    return int(v[0] > 0), idx[ch] * (CPU / rate)


def rle_record(level0, changes, end, limit):
    """rle.asm: return (buffer, sample times, sample values)."""
    n = int(end // RLE_BYTE)
    t = (np.arange(n)[:, None] * RLE_BYTE + np.arange(8)[None, :] * RLE_BIT).ravel()
    bits = ((np.searchsorted(changes, t, side='right') + level0) & 1).astype(np.uint8)
    data = np.packbits(bits.reshape(-1, 8)[:, ::-1], axis=1).ravel().tolist()
    out, b, prev, prev2, ctl, used = [], 0xFF, None, None, None, 0
    for c in data:
        used += 1
        if b & 0x80:
            if c == prev and b != 0xFF:
                b += 1
                out[ctl] = b
                continue
        elif c == prev and c == prev2:
            if b == 2:
                out.pop()
            else:
                out[ctl] = b - 2
                ctl = len(out) - 2
            b = 0x83
            out[ctl] = b
            continue
        elif b != 127:
            b += 1
            out[ctl] = b
            out.append(c)
            prev2, prev = prev, c
            if limit and len(out) >= limit:
                break
            continue
        ctl, b = len(out), 1
        out += [1, c]
        prev, prev2 = c, c ^ 0xFF
        if limit and len(out) >= limit:
            break
    return bytes(out + [0]), t[:used * 8], bits[:used * 8]


def delta_record(level0, changes, end, limit):
    """delta.asm: return (buffer, times of the output changes, starting level)."""
    out, events, t, n = [level0 << 6], [], 0.0, len(changes)
    while t < end and not (limit and len(out) >= limit):
        i = np.searchsorted(changes, t, side='right')           # changes seen so far
        t1, count = t + DELTA_LONG, 1
        while True:
            j = np.searchsorted(changes, t1, side='right')
            if (j - i) & 1:                                     # the level differs at this sample
                out.append(count)
                events.append(t1)
                t = t1
                break
            # nothing changes before the next crossing: skip to the first sample after it
            steps = 255 if j >= n else max(1, int(np.ceil((changes[j] - t1) / DELTA_SAMPLE)))
            if count + steps >= 255:                            # 254 samples and still the same
                out.append(255)
                t += DELTA_LONG + 253 * DELTA_SAMPLE
                break
            count += steps
            t1 += steps * DELTA_SAMPLE
    return bytes(out + [0]), np.array(events), t


def write_wav(path, level, rate, seconds, post=(None, None), oversample=8):
    """level(times in T-states) -> 0/1; averaged over each output sample."""
    n = int(seconds * rate)
    t = np.arange(n * oversample) * (CPU / (rate * oversample))
    x = level(t).reshape(n, oversample).mean(axis=1) * 2 - 1
    if post[0] or post[1]:
        x = band(x - x.mean(), rate, *post)
        x /= max(1.0, np.abs(x).max())
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((x * 12000).astype('<i2').tobytes())


def write_tap(path, name, address, data):
    def block(flag, body):
        b = bytes([flag]) + body
        b += bytes([reduce(lambda a, c: a ^ c, b, 0)])
        return struct.pack('<H', len(b)) + b
    header = bytes([3]) + name.encode('ascii')[:10].ljust(10) + struct.pack('<HHH', len(data), address, 32768)
    with open(path, 'wb') as f:
        f.write(block(0, header) + block(255, data))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('wav')
    ap.add_argument('-m', '--mode', choices=('delta', 'rle'), default='delta')
    ap.add_argument('-o', '--output', help='output WAV (default: input name + .MODE.wav)')
    ap.add_argument('-s', '--start', type=float, default=0, help='where to start, seconds')
    ap.add_argument('-l', '--length', type=float, help='how much to take, seconds')
    ap.add_argument('--lowpass', type=float, metavar='HZ', help='low-pass filter before the comparator')
    ap.add_argument('--highpass', type=float, metavar='HZ', help='high-pass filter before the comparator')
    ap.add_argument('--post-lowpass', type=float, metavar='HZ', help='low-pass filter on the output')
    ap.add_argument('--post-highpass', type=float, metavar='HZ', help='high-pass filter on the output')
    ap.add_argument('--hyst', type=float, default=0.05,
                    help='comparator hysteresis as a fraction of the RMS level (default 0.05)')
    ap.add_argument('--rate', type=int, default=44100, help='sample rate of the output WAV')
    ap.add_argument('--tap', help='write the buffer as CODE 26000 and stop when it is full')
    args = ap.parse_args()

    d, rate = load(args.wav, args.start, args.length)
    d = band(d, rate, args.highpass, args.lowpass)
    level0, changes = comparator(d, rate, args.hyst)
    end = len(d) / rate * CPU
    limit = BUFFER if args.tap else 0

    if args.mode == 'rle':
        buf, times, bits = rle_record(level0, changes, end, limit)
        seconds = len(times) // 8 * RLE_BYTE / CPU

        def level(t):
            return bits[np.clip(np.searchsorted(times, t, side='right') - 1, 0, len(bits) - 1)]
    else:
        buf, events, stop = delta_record(level0, changes, end, limit)
        seconds = min(stop, end) / CPU

        def level(t):
            return (np.searchsorted(events, t, side='right') + level0) & 1

    out = args.output or '%s.%s.wav' % (os.path.splitext(args.wav)[0], args.mode)
    write_wav(out, level, args.rate, seconds, (args.post_highpass, args.post_lowpass))
    plain = seconds * CPU / RLE_BYTE
    print('%s: %.1f s, %.0f level changes per second' % (args.wav, len(d) / rate, len(changes) / (len(d) / rate)))
    print('%s: %.1f s recorded, %d bytes of buffer (x%.2f of the unpacked %d), %.1f s would fit in %d bytes'
          % (args.mode, seconds, len(buf), len(buf) / plain, plain, seconds * BUFFER / len(buf), BUFFER))
    print('  -> %s' % out)
    if args.tap:
        write_tap(args.tap, 'sound', 26000, buf)
        print('  -> %s (CODE 26000,%d: load it with item 4 of the menu)' % (args.tap, len(buf)))


if __name__ == '__main__':
    main()
