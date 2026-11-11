#!/usr/bin/env python3
"""Convert a Radio-86RK program file (.rkr, .rk, .gam) into a tape for rk86.tap.

    rkr2tap.py BASIC80.RKR basic.tap [ADDR=HEXBYTES ...]

The input is the usual RK file: start and end address (high byte first), the
data and, optionally, zeros, the sync byte #E6 and the checksum.  The output
is what directive I of the emulator reads: a Spectrum CODE header named
"RADIO FILE" and a data block.  The checksum, computed the way the RK Monitor
does it, goes into the second header parameter and is printed, to compare
with what I shows after loading.

ADDR=HEXBYTES (both hexadecimal, e.g. 12D0=C3EE19) patches the program before
it is written; the checksum is then that of the patched program.
"""
import sys
from functools import reduce


def block(flag, data):
    b = bytes([flag]) + data
    return (len(b) + 1).to_bytes(2, 'little') + b + bytes([reduce(lambda a, c: a ^ c, b)])


def checksum(data):
    hi = lo = 0
    for i, x in enumerate(data):
        lo += x
        carry, lo = lo >> 8, lo & 255
        if i < len(data) - 1:
            hi = (hi + x + carry) & 255
    return hi << 8 | lo


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    d = open(sys.argv[1], 'rb').read()
    if d[:1] == b'\xe6':                    # some files keep the sync byte
        d = d[1:]
    start, end = d[0] << 8 | d[1], d[2] << 8 | d[3]
    n = end - start + 1
    if n <= 0 or len(d) < 4 + n:
        sys.exit('%s: not an RK file (start #%04X, end #%04X, %d bytes)' % (sys.argv[1], start, end, len(d)))
    data = bytearray(d[4:4 + n])
    orig = checksum(data)
    tail = d[4 + n:].lstrip(b'\0')
    stored = tail[1] << 8 | tail[2] if len(tail) >= 3 and tail[0] == 0xE6 else None
    if stored is not None and stored != orig:
        print('warning: the file says checksum %04X, the data gives %04X' % (stored, orig))
    for p in sys.argv[3:]:
        addr, new = p.split('=')
        addr, new = int(addr, 16) - start, bytes.fromhex(new)
        assert 0 <= addr and addr + len(new) <= n, 'patch %s is outside the program' % p
        data[addr:addr + len(new)] = new
    data = bytes(data)
    cs = checksum(data)
    w = lambda v: v.to_bytes(2, 'little')
    with open(sys.argv[2], 'wb') as f:
        f.write(block(0, b'\x03RADIO FILE' + w(n) + w(start) + w(cs)) + block(255, data))
    print('%s: #%04X-#%04X, checksum %04X%s' % (
        sys.argv[2], start, end, cs, '' if cs == orig else ' (%04X before patching)' % orig))


if __name__ == '__main__':
    main()
