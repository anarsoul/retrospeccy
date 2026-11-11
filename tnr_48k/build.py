#!/usr/bin/env python3
"""Build what is needed to run the Russian "Three Weeks in Paradise".

The game takes its font straight from the ROM (#3C00).  On the Baltik the
Russian font T.N.R.ZNG was loaded over the ROM copy in shadow RAM.  A stock
Spectrum has no room for the font anywhere else: the game uses all memory
below itself (#5B00-#6779) and the hidden message at its end as screen
buffers, and less than 512 bytes are left above it.  (An earlier version of
this script put the font at #6000 - it was overwritten as soon as the game
started drawing, and the text turned into garbage.)

So the game is left untouched and the font goes where it was on the Baltik -
into the ROM:

    build.py                  # T.N.R.tap and T.N.R_plus3.tap
    build.py --rom 48.rom     # also 48-tnr.rom: your ROM image with the font replaced

T.N.R.tap is a BASIC loader plus the game as it is on the tape.  Run it in an
emulator with 48-tnr.rom as the 48K ROM.  With the stock ROM the game works
too, but all text shows up as Latin transliteration.  The ROM image itself is
not part of this repository.

T.N.R_plus3.tap is for the +2A/+2B/+3, which can put RAM in place of the ROM
("special paging", port #1FFD).  Its loader does on those machines what the
Baltik did with its shadow RAM: copies the 48K BASIC ROM into RAM page 4,
writes the font over the ROM font there, loads the game and switches to the
all-RAM layout 4-5-6-3.  Load it from +3 BASIC (or the Loader), not from
48 BASIC, where paging is locked.
"""
import argparse
import os
from functools import reduce

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.join(HERE, '..', 'transparent_a_21___', '01_T.N.R.EXE.bin')
FONT = os.path.join(HERE, '..', 'transparent_a_20', '01_T.N.R.ZNG.bin')

ORG = 26490            # load address of T.N.R.EXE
START = 0xF6A6         # entry point: DI / LD SP,0 / ... / JP #BBA5
ROM_FONT = 0x3D00      # characters 32..127 of the ROM font


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


def build_tap(game):
    # 10 CLEAR 26489: LOAD ""CODE: RANDOMIZE USR 63142
    line = b'\xfd' + num(ORG - 1) + b':\xef""\xaf:\xf9\xc0' + num(START) + b'\r'
    prog = bytes([0, 10]) + len(line).to_bytes(2, 'little') + line
    return (header(0, 'T.N.R.', len(prog), 10, len(prog)) + block(255, prog) +
            header(3, 'T.N.R.EXE', len(game), ORG, 32768) + block(255, game))


# Loader for the +2A/+3, hand-assembled, runs at #6000; the font follows at #6100.
PLUS3_ORG = 0x6000
PLUS3_FONT = 0x6100
PLUS3_LOADER = bytes([
    0xF3,                    # 6000 DI
    0x31, 0x00, 0x67,        # 6001 LD SP,#6700       scratch stack below the game
    0x01, 0xFD, 0x1F,        # 6004 LD BC,#1FFD
    0x3E, 0x04,              # 6007 LD A,#04          normal paging, ROM high bit = 1
    0xED, 0x79,              # 6009 OUT (C),A
    0x01, 0xFD, 0x7F,        # 600B LD BC,#7FFD
    0x3E, 0x14,              # 600E LD A,#14          ROM 3 (48 BASIC), RAM page 4 at #C000
    0xED, 0x79,              # 6010 OUT (C),A
    0x21, 0x00, 0x00,        # 6012 LD HL,#0000
    0x11, 0x00, 0xC0,        # 6015 LD DE,#C000
    0x01, 0x00, 0x40,        # 6018 LD BC,#4000
    0xED, 0xB0,              # 601B LDIR              ROM -> page 4
    0x21, 0x00, 0x61,        # 601D LD HL,#6100
    0x11, 0x00, 0xFD,        # 6020 LD DE,#FD00       = #3D00 inside page 4
    0x01, 0x00, 0x03,        # 6023 LD BC,768
    0xED, 0xB0,              # 6026 LDIR              font over the ROM font
    0x01, 0xFD, 0x7F,        # 6028 LD BC,#7FFD
    0x3E, 0x13,              # 602B LD A,#13          RAM page 3 at #C000
    0xED, 0x79,              # 602D OUT (C),A
    0xDD, 0x21, 0x7A, 0x67,  # 602F LD IX,#677A
    0x11, 0xB6, 0x96,        # 6033 LD DE,38582
    0x3E, 0xFF,              # 6036 LD A,#FF
    0x37,                    # 6038 SCF
    0xCD, 0x56, 0x05,        # 6039 CALL #0556        LD-BYTES: game into pages 5, 2, 3
    0xF3,                    # 603C DI
    0x30, 0x1C,              # 603D JR NC,#605B       loading error
    0x01, 0xFD, 0x7F,        # 603F LD BC,#7FFD
    0x3E, 0x16,              # 6042 LD A,#16          RAM page 6 at #C000
    0xED, 0x79,              # 6044 OUT (C),A
    0x21, 0x00, 0x80,        # 6046 LD HL,#8000
    0x11, 0x00, 0xC0,        # 6049 LD DE,#C000
    0x01, 0x00, 0x40,        # 604C LD BC,#4000
    0xED, 0xB0,              # 604F LDIR              page 2 -> page 6
    0x01, 0xFD, 0x1F,        # 6051 LD BC,#1FFD
    0x3E, 0x05,              # 6054 LD A,#05          special paging: RAM 4, 5, 6, 3
    0xED, 0x79,              # 6056 OUT (C),A
    0xC3, 0xA6, 0xF6,        # 6058 JP #F6A6          start the game
    0x3E, 0x02,              # 605B LD A,2            red border, stop
    0xD3, 0xFE,              # 605D OUT (#FE),A
    0x18, 0xFE,              # 605F JR #605F
])
assert len(PLUS3_LOADER) == 0x61
assert ORG == 0x677A and START == 0xF6A6


def build_plus3_tap(game, font):
    # 10 CLEAR 24575: LOAD ""CODE: RANDOMIZE USR 24576
    line = b'\xfd' + num(PLUS3_ORG - 1) + b':\xef""\xaf:\xf9\xc0' + num(PLUS3_ORG) + b'\r'
    prog = bytes([0, 10]) + len(line).to_bytes(2, 'little') + line
    code = PLUS3_LOADER + bytes(PLUS3_FONT - PLUS3_ORG - len(PLUS3_LOADER)) + font
    return (header(0, 'T.N.R.+3', len(prog), 10, len(prog)) + block(255, prog) +
            header(3, 'loader', len(code), PLUS3_ORG, 32768) + block(255, code) +
            block(255, game))                       # the game itself: headerless


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--rom', help='a 16K ZX Spectrum 48K ROM image to patch')
    ap.add_argument('--game', default=GAME)
    ap.add_argument('--font', default=FONT)
    ap.add_argument('-o', '--outdir', default=HERE)
    args = ap.parse_args()

    game = open(args.game, 'rb').read()
    font = open(args.font, 'rb').read()
    assert len(font) == 768, 'the font must be 768 bytes'

    tap = os.path.join(args.outdir, 'T.N.R.tap')
    with open(tap, 'wb') as f:
        f.write(build_tap(game))
    print('%s: loader + %d bytes of the game, unmodified' % (tap, len(game)))

    tap3 = os.path.join(args.outdir, 'T.N.R_plus3.tap')
    with open(tap3, 'wb') as f:
        f.write(build_plus3_tap(game, font))
    print('%s: +2A/+3 loader with the font, then the game' % tap3)

    if args.rom:
        rom = bytearray(open(args.rom, 'rb').read())
        assert len(rom) == 16384, 'expected a 16384-byte ROM image'
        rom[ROM_FONT:ROM_FONT + 768] = font
        out = os.path.join(args.outdir, '48-tnr.rom')
        with open(out, 'wb') as f:
            f.write(rom)
        print('%s: font at #%04X replaced with T.N.R.ZNG' % (out, ROM_FONT))
    else:
        print('no --rom given: with the stock ROM the text will be in transliteration')


if __name__ == '__main__':
    main()
