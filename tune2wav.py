#!/usr/bin/env python3
"""Convert tunes of the EDIT music editors (green_svema tape) to WAV and MIDI.

Two formats are recognised by the first byte of the file:

#FF  three-channel tunes of EDIT-3 (CODE 39997,3000):
       byte 0     #FF
       bytes 1-2  number of steps
       then       3 bytes per step, one per channel
     note byte:  bits 0-2  note  0..7 = C D E F G A B C'
                 bits 3-4  octave 0..3
                 bit 6     rest
                 bit 7     sharp
                 0         nothing entered (silence)

#EE  one-channel tunes of the earlier editor (CODE 60000,2000):
       byte 0     #EE
       then       1 byte per step: signed semitones from middle C (as in
                  BEEP), #40 = rest, #29 = unused

A note lasts for as many steps as its value repeats; there are no durations.
The player routine is not on the tape, so two things are assumptions:
the step length (--step, default 0.2 s) and the octave of the three-channel
format (--base, default: octave 0 starts at C2).

Usage: tune2wav.py tune.bin [-o OUTBASE] [--step S] [--base MIDI] [--no-midi]
"""
import argparse
import os
import struct
import sys
import wave

import numpy as np

RATE = 44100
WHITE = (0, 2, 4, 5, 7, 9, 11, 12)          # C D E F G A B C'
NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')


def parse(data, base):
    """Return a list of channels; each is a list of MIDI notes or None per step."""
    if data[0] == 0xFF:
        steps = min(data[1] | data[2] << 8, (len(data) - 3) // 3)
        chans = [[], [], []]
        for i in range(steps):
            for ch in range(3):
                v = data[3 + i * 3 + ch]
                if v == 0 or v & 0x40:
                    chans[ch].append(None)
                else:
                    chans[ch].append(base + 12 * ((v >> 3) & 3) + WHITE[v & 7] + (v >> 7))
        return chans
    if data[0] == 0xEE:
        body = data[1:]
        used = max((i for i, v in enumerate(body) if v != 0x29), default=-1) + 1
        chan = []
        for v in body[:used]:
            if v in (0x40, 0x29):
                chan.append(None)
            else:
                chan.append(60 + (v - 256 if v > 127 else v))
        return [chan]
    sys.exit('unknown tune format (first byte #%02X)' % data[0])


def runs(chan):
    """Group equal consecutive steps: [(start_step, length, note)]."""
    out, i = [], 0
    while i < len(chan):
        j = i
        while j < len(chan) and chan[j] == chan[i]:
            j += 1
        if chan[i] is not None:
            out.append((i, j - i, chan[i]))
        i = j
    return out


def render(chans, step):
    n = int(max(len(c) for c in chans) * step * RATE) + RATE // 4
    mix = np.zeros(n)
    ramp = int(0.004 * RATE)
    for chan in chans:
        for start, length, note in runs(chan):
            a, m = int(start * step * RATE), int(length * step * RATE)
            freq = 440.0 * 2 ** ((note - 69) / 12)
            t = np.arange(m) / RATE
            sq = np.where((t * freq) % 1.0 < 0.5, 1.0, -1.0)     # square wave, as an AY would give
            env = np.ones(m)
            k = min(ramp, m // 2)
            env[:k] = np.linspace(0, 1, k)
            env[m - k:] = np.linspace(1, 0, k)
            mix[a:a + m] += sq * env
    return (mix / len(chans) * 0.8 * 32767).astype('<i2')


def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, 0x80 | (n & 0x7F))
        n >>= 7
    return bytes(out)


def midi(chans, step):
    ticks = 120                                   # per step; one step = one "beat"
    ev = []
    for ch, chan in enumerate(chans):
        for start, length, note in runs(chan):
            ev.append((start * ticks, 1, bytes([0x90 | ch, note, 96])))
            ev.append(((start + length) * ticks, 0, bytes([0x80 | ch, note, 0])))
    ev.sort()
    track = b'\x00\xff\x51\x03' + int(step * 1e6).to_bytes(3, 'big')
    now = 0
    for t, _, msg in ev:
        track += vlq(t - now) + msg
        now = t
    track += b'\x00\xff\x2f\x00'
    return (b'MThd' + struct.pack('>IHHH', 6, 0, 1, ticks) +
            b'MTrk' + struct.pack('>I', len(track)) + track)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('tune')
    ap.add_argument('-o', '--output', help='output name without extension')
    ap.add_argument('--step', type=float, default=0.2, help='step length in seconds')
    ap.add_argument('--base', type=int, default=36,
                    help='MIDI note of C in octave 0 of the 3-channel format')
    ap.add_argument('--no-midi', action='store_true')
    ap.add_argument('--notes', action='store_true', help='print the notes')
    args = ap.parse_args()
    chans = parse(open(args.tune, 'rb').read(), args.base)
    out = args.output or os.path.splitext(args.tune)[0]
    with wave.open(out + '.wav', 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(render(chans, args.step).tobytes())
    if not args.no_midi:
        with open(out + '.mid', 'wb') as f:
            f.write(midi(chans, args.step))
    steps = max(len(c) for c in chans)
    print('%s: %d channel(s), %d steps, %.1f s -> %s.wav' % (
        args.tune, len(chans), steps, steps * args.step, out))
    if args.notes:
        for i, chan in enumerate(chans):
            print('  ch%d: %s' % (i, ' '.join(
                '--' if n is None else NAMES[n % 12] + str(n // 12 - 1) for n in chan)))


if __name__ == '__main__':
    main()
