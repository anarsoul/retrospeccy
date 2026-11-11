#!/usr/bin/env python3
"""Build a TAP of the Russian "Three Weeks in Paradise" that runs on a stock 48K.

The game takes its font from #3C00 (the ROM font).  On the Baltik the Russian
font T.N.R.ZNG was loaded over the ROM copy in shadow RAM; a stock machine has
real ROM there.  So the font is put into free RAM at #6000 and every reference
to #3C00 is changed to #5F00:

  * 5 instructions (LD rr,#3C00) in the print routines;
  * 11 text strings with the control code #FB,#00,#3C ("select font").

The BASIC loader also points CHARS at the new font.

Usage: build.py [T.N.R.EXE.bin [T.N.R.ZNG.bin [out.tap]]]
"""
import os
import sys
from functools import reduce

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.join(HERE, '..', 'transparent_a_21___', '01_T.N.R.EXE.bin')
FONT = os.path.join(HERE, '..', 'transparent_a_20', '01_T.N.R.ZNG.bin')
OUT = os.path.join(HERE, 'T.N.R_48k.tap')

ORG = 26490            # load address of T.N.R.EXE
START = 0xF6A6         # entry point: DI / LD SP,0 / ... / JP #BBA5
FONT_ADDR = 0x6000     # new home of the 768-byte font
CODE_REFS = (0xA82C, 0xB9A7, 0xD3E5, 0xE15C, 0xE408)   # LD rr,#3C00


def patch(game):
    game = bytearray(game)
    base = FONT_ADDR - 0x100                # address of the (virtual) character 0
    sites = []
    for a in CODE_REFS:
        o = a - ORG + 1
        assert game[o:o + 2] == b'\x00\x3c', hex(a)
        sites.append(o)
    i = game.find(b'\xfb\x00\x3c')          # font-select code inside strings
    while i >= 0:
        sites.append(i + 1)
        i = game.find(b'\xfb\x00\x3c', i + 1)
    for o in sites:
        game[o], game[o + 1] = base & 255, base >> 8
    return bytes(game), sorted(ORG + o for o in sites)


def num(n):
    """A number in a BASIC line: digits plus the hidden 5-byte integer form."""
    return str(n).encode() + bytes([0x0E, 0, 0, n & 255, n >> 8, 0])


def block(flag, data):
    b = bytes([flag]) + data
    b += bytes([reduce(lambda a, c: a ^ c, b)])
    return len(b).to_bytes(2, 'little') + b


def header(typ, name, length, p1, p2):
    w = lambda v: v.to_bytes(2, 'little')
    return block(0, bytes([typ]) + name.ljust(10).encode() + w(length) + w(p1) + w(p2))


def main():
    args = sys.argv[1:]
    game = open(args[0] if args else GAME, 'rb').read()
    font = open(args[1] if len(args) > 1 else FONT, 'rb').read()
    out = args[2] if len(args) > 2 else OUT
    assert len(font) == 768
    game, sites = patch(game)
    image = font + bytes(ORG - FONT_ADDR - len(font)) + game
    base = FONT_ADDR - 0x100
    # 10 CLEAR 24575: LOAD ""CODE: POKE 23606,lo: POKE 23607,hi: RANDOMIZE USR start
    line = (b'\xfd' + num(FONT_ADDR - 1) + b':\xef""\xaf'
            b':\xf4' + num(23606) + b',' + num(base & 255) +
            b':\xf4' + num(23607) + b',' + num(base >> 8) +
            b':\xf9\xc0' + num(START) + b'\r')
    prog = bytes([0, 10]) + len(line).to_bytes(2, 'little') + line
    tap = (header(0, 'T.N.R.', len(prog), 10, len(prog)) + block(255, prog) +
           header(3, 'T.N.R.EXE', len(image), FONT_ADDR, 32768) + block(255, image))
    with open(out, 'wb') as f:
        f.write(tap)
    print('%s: %d bytes, %d font references patched: %s'
          % (out, len(tap), len(sites), ' '.join('#%04X' % a for a in sites)))


if __name__ == '__main__':
    main()
