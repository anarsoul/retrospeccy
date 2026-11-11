#!/usr/bin/env python3
"""Make a tape recording in the Radio-86RK format from a program file.

    rk2wav.py PROGRAM.RKR [OUT.wav | OUT.tzx] [ADDR=HEXBYTES ...]
              [--raw ADDR] [--speed X] [--rate HZ]

The input is the usual RK file (.rkr, .rk, .pki, .gam): start and end address
(high byte first), the data and, optionally, zeros, the sync byte #E6 and the
checksum.  With --raw ADDR (hexadecimal) the input is just the data, to be
loaded at that address.  The output is what directive O of the Monitor writes and directive
I reads: 256 zero bytes, #E6, start, end, the data, two zero bytes, #E6 and
the checksum.  The default output is PROGRAM.wav.

Every bit is two half-periods: the inverted bit, then the bit.  Their lengths
are those of the real machine, counted in clock cycles of its 8080 (16 MHz / 9)
from the Monitor code: 767 and 826 cycles, 877 for the last bit of a byte.
That is 896 microseconds per bit, about 1116 baud.

ADDR=HEXBYTES (both hexadecimal, e.g. 12D0=C3EE19) patches the program before
it is written; the checksum is then that of the patched program.
--speed 1.1 makes the recording 10% faster.

A .tzx output holds the same signal as pulse sequences (block #13), for
emulators; it is much smaller than the WAV.
"""
import os
import struct
import sys
import wave

CLOCK = 16e6 / 9                # 8080 clock of the Radio-86RK, Hz
HALF1, HALF2, HALF2_LAST = 767, 826, 877
LEAD, TAIL = 0.5, 0.5           # silence around the recording, seconds


def checksum(data):
    """The Monitor's checksum: sum of all bytes; the high byte is the sum with
    carries of all bytes but the last."""
    hi = lo = 0
    for i, x in enumerate(data):
        lo += x
        carry, lo = lo >> 8, lo & 255
        if i < len(data) - 1:
            hi = (hi + x + carry) & 255
    return hi << 8 | lo


def read_rk(path, patches=(), raw=None):
    """Return (start address, data, checksum) of an RK file."""
    d = open(path, 'rb').read()
    if raw is not None:
        end = raw + len(d) - 1
        d = bytes([raw >> 8, raw & 255, end >> 8 & 255, end & 255]) + d
    elif d[:1] == b'\xe6':                  # some files keep the sync byte
        d = d[1:]
    start, end = d[0] << 8 | d[1], d[2] << 8 | d[3]
    n = end - start + 1
    if n <= 0 or len(d) < 4 + n:
        sys.exit('%s: not an RK file (start #%04X, end #%04X, %d bytes)' % (path, start, end, len(d)))
    data = bytearray(d[4:4 + n])
    orig = checksum(data)
    tail = d[4 + n:].lstrip(b'\0')
    if len(tail) >= 3 and tail[0] == 0xE6 and tail[1] << 8 | tail[2] != orig:
        print('warning: the file says checksum %04X, the data gives %04X' % (tail[1] << 8 | tail[2], orig))
    for p in patches:
        addr, new = p.split('=')
        addr, new = int(addr, 16) - start, bytes.fromhex(new)
        if addr < 0 or addr + len(new) > n:
            sys.exit('patch %s is outside the program' % p)
        data[addr:addr + len(new)] = new
    return start, bytes(data), checksum(data)


def tape_bytes(start, data, cs):
    """What directive O puts on the tape."""
    end = start + len(data) - 1
    w = lambda v: bytes([v >> 8 & 255, v & 255])
    return bytes(256) + b'\xe6' + w(start) + w(end) + data + b'\0\0\xe6' + w(cs)


def levels(stream, speed=1.0):
    """The signal as a list of (seconds, level): two entries per bit."""
    k = 1 / (CLOCK * speed)
    out = []
    for byte in stream:
        for bit in range(7, -1, -1):
            b = byte >> bit & 1
            out.append((HALF1 * k, b ^ 1))
            out.append(((HALF2 if bit else HALF2_LAST) * k, b))
    return out


def write_wav(path, signal, rate):
    samples, t, n = bytearray(), 0.0, int(LEAD * rate)
    samples += bytes([128]) * n
    for dur, level in signal:
        t += dur
        m = int((LEAD + t) * rate)
        samples += bytes([208 if level else 48]) * (m - n)
        n = m
    samples += bytes([128]) * int(TAIL * rate)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(rate)
        w.writeframes(bytes(samples))


def pulses(signal):
    """Lengths of the stretches between level changes, in seconds."""
    out, level, acc = [], signal[0][1], 0.0
    for dur, lv in signal:
        if lv != level:
            out.append(acc)
            acc, level = 0.0, lv
        acc += dur
    return out + [acc]


def write_tzx(path, signal):
    """Pulse sequences (block #13) in T-states of a 3.5 MHz Spectrum.  Which
    level the first pulse has depends on the emulator; the Monitor accepts a
    recording of either polarity."""
    out = bytearray(b'ZXTape!\x1a\x01\x14')
    out += b'\x20' + struct.pack('<H', int(LEAD * 1000))
    t = [min(65535, max(1, round(p * 3500000))) for p in pulses(signal)]
    for i in range(0, len(t), 255):
        chunk = t[i:i + 255]
        out += bytes([0x13, len(chunk)]) + b''.join(struct.pack('<H', p) for p in chunk)
    out += b'\x20' + struct.pack('<H', int(TAIL * 1000))
    open(path, 'wb').write(out)


def main():
    args, opts = [], {'--speed': 1.0, '--rate': 44100, '--raw': None}
    it = iter(sys.argv[1:])
    for a in it:
        if a == '--raw':
            opts[a] = int(next(it), 16)
        elif a in opts:
            opts[a] = float(next(it))
        else:
            args.append(a)
    if not args:
        sys.exit(__doc__)
    src = args[0]
    outs = [a for a in args[1:] if '=' not in a]
    out = outs[0] if outs else os.path.splitext(src)[0] + '.wav'
    start, data, cs = read_rk(src, [a for a in args[1:] if '=' in a], opts['--raw'])
    signal = levels(tape_bytes(start, data, cs), opts['--speed'])
    if out.lower().endswith('.tzx'):
        write_tzx(out, signal)
    else:
        write_wav(out, signal, int(opts['--rate']))
    print('%s: #%04X-#%04X, checksum %04X, %.0f s' % (
        out, start, start + len(data) - 1, cs, LEAD + TAIL + sum(d for d, _ in signal)))


if __name__ == '__main__':
    main()
