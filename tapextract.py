#!/usr/bin/env python3
"""Unpack a ZX Spectrum TAP file into a directory of readable files.

For every block:  NN_name.bin (body without flag and checksum) and, depending
on what it is:
    *.bas.txt   BASIC listing
    *.src.txt   assembler source text (2-byte line number, text, CR)
    *.png       screen (6912 bytes) or font (768 bytes)
    *.skool     disassembly, if SkoolKit's sna2skool.py is found
                (in PATH or via the SNA2SKOOL environment variable)
blocks.txt lists all blocks.

Usage: tapextract.py tape.tap [outdir]      (default outdir: tape name without .tap)
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from functools import reduce

TOKENS = ['RND', 'INKEY$', 'PI', 'FN', 'POINT', 'SCREEN$', 'ATTR', 'AT', 'TAB', 'VAL$', 'CODE',
          'VAL', 'LEN', 'SIN', 'COS', 'TAN', 'ASN', 'ACS', 'ATN', 'LN', 'EXP', 'INT', 'SQR', 'SGN',
          'ABS', 'PEEK', 'IN', 'USR', 'STR$', 'CHR$', 'NOT', 'BIN', 'OR', 'AND', '<=', '>=', '<>',
          'LINE', 'THEN', 'TO', 'STEP', 'DEF FN', 'CAT', 'FORMAT', 'MOVE', 'ERASE', 'OPEN #',
          'CLOSE #', 'MERGE', 'VERIFY', 'BEEP', 'CIRCLE', 'INK', 'PAPER', 'FLASH', 'BRIGHT',
          'INVERSE', 'OVER', 'OUT', 'LPRINT', 'LLIST', 'STOP', 'READ', 'DATA', 'RESTORE', 'NEW',
          'BORDER', 'CONTINUE', 'DIM', 'REM', 'FOR', 'GO TO', 'GO SUB', 'INPUT', 'LOAD', 'LIST',
          'LET', 'PAUSE', 'NEXT', 'POKE', 'PRINT', 'PLOT', 'RUN', 'SAVE', 'RANDOMIZE', 'IF', 'CLS',
          'DRAW', 'CLEAR', 'RETURN', 'COPY']
PALETTE = [(0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205),
           (0, 205, 0), (0, 205, 205), (205, 205, 0), (205, 205, 205)]


def xor(data):
    return reduce(lambda a, c: a ^ c, data, 0)


def read_tap(path):
    d = open(path, 'rb').read()
    p, out = 0, []
    while p + 2 <= len(d):
        n = d[p] | d[p + 1] << 8
        out.append(d[p + 2:p + 2 + n])
        p += 2 + n
    return out


def basic(b):
    p, out = 0, []
    while p + 4 <= len(b):
        ln, n = b[p] << 8 | b[p + 1], b[p + 2] | b[p + 3] << 8
        if ln > 9999:
            break
        body, p = b[p + 4:p + 4 + n], p + 4 + n
        s, i = '', 0
        while i < len(body):
            c = body[i]
            i += 1
            if c == 0x0E:
                i += 5
            elif c == 0x0D:
                break
            elif c >= 0xA5:
                s += ' ' + TOKENS[c - 0xA5] + ' '
            elif 32 <= c < 127:
                s += chr(c)
            elif c == 0x7F:
                s += '(c)'
            else:
                s += '{%02X}' % c
        out.append('%4d %s' % (ln, ' '.join(s.split()) if '"' not in s else s.strip()))
    return '\n'.join(out) + '\n'


def asm_source(b):
    p, out = 0, []
    try:
        while p < len(b):
            e = b.index(13, p + 2)
            t = b[p + 2:e]
            if any((c < 32 and c != 9) or c > 126 for c in t):
                return None
            out.append('%5d %s' % (b[p] | b[p + 1] << 8, t.decode()))
            p = e + 1
    except ValueError:
        if p < len(b) - 8 or not out:
            return None
    return '\n'.join(out) + '\n' if len(out) > 2 else None


def write_png(path, w, h, px, scale=2):
    rows = []
    for y in range(h):
        r = b''.join(bytes(px[y][x]) * scale for x in range(w))
        rows += [b'\0' + r] * scale

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' +
                chunk(b'IHDR', struct.pack('>IIBBBBB', w * scale, h * scale, 8, 2, 0, 0, 0)) +
                chunk(b'IDAT', zlib.compress(b''.join(rows))) + chunk(b'IEND', b''))


def colour(i, bright):
    return tuple(255 if (c and bright) else c for c in PALETTE[i])


def screen_png(path, b):
    px = [[None] * 256 for _ in range(192)]
    for y in range(192):
        a = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
        for cx in range(32):
            v, at = b[a + cx], b[6144 + (y // 8) * 32 + cx]
            ink, pap = colour(at & 7, at & 64), colour((at >> 3) & 7, at & 64)
            for k in range(8):
                px[y][cx * 8 + k] = ink if v & (0x80 >> k) else pap
    write_png(path, 256, 192, px)


def font_png(path, b):
    n = len(b) // 8
    rows = (n + 15) // 16
    w, h = 16 * 9 + 1, rows * 9 + 1
    px = [[(60, 60, 60)] * w for _ in range(h)]
    for ch in range(n):
        x0, y0 = 1 + (ch % 16) * 9, 1 + (ch // 16) * 9
        for y in range(8):
            for k in range(8):
                px[y0 + y][x0 + k] = (255, 255, 255) if b[ch * 8 + y] & (0x80 >> k) else (0, 0, 0)
    write_png(path, w, h, px, scale=4)


def disassemble(path, org, n):
    tool = os.environ.get('SNA2SKOOL') or shutil.which('sna2skool.py')
    if not tool:
        return None
    with tempfile.NamedTemporaryFile('w', suffix='.ctl') as ctl:
        ctl.write('c %d\ni %d\n' % (org, org + n))
        ctl.flush()
        r = subprocess.run([tool, '-H', '-o', str(org), '-c', ctl.name, path],
                           capture_output=True, text=True)
    return r.stdout or None


def safe(name):
    return ''.join(c if c.isalnum() or c in '.-_$' else '_' for c in name.strip()) or 'noname'


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    tap = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(tap)[0]
    os.makedirs(out, exist_ok=True)
    report, hdr = [], None
    for n, blk in enumerate(read_tap(tap), 1):
        if len(blk) == 19 and blk[0] == 0 and xor(blk) == 0:
            w = lambda o: blk[o] | blk[o + 1] << 8
            hdr = dict(type=blk[1], name=blk[2:12].decode('latin1'), len=w(12), p1=w(14), p2=w(16))
            report.append('%02d header type=%d name=%r len=%d p1=%d p2=%d'
                          % (n, hdr['type'], hdr['name'], hdr['len'], hdr['p1'], hdr['p2']))
            continue
        ok = len(blk) > 1 and xor(blk) == 0
        body = blk[1:-1]
        base = '%02d_%s' % (n, safe(hdr['name']) if hdr else 'headerless')
        path = os.path.join(out, base)
        with open(path + '.bin', 'wb') as f:
            f.write(body)
        line = '%02d data flag=%02X len=%d %s' % (n, blk[0] if blk else 0, len(body), 'OK' if ok else 'BAD')
        kind = ''
        src = asm_source(body)
        if hdr and hdr['type'] == 0:
            open(path + '.bas.txt', 'w').write(basic(body[:hdr['p2']]))
            kind = 'BASIC'
        elif src:
            open(path + '.src.txt', 'w').write(src)
            kind = 'asm source text (%d lines)' % src.count('\n')
        elif len(body) == 6912:
            screen_png(path + '.png', body)
            kind = 'screen'
        elif len(body) in (768, 1024, 2048) and (not hdr or hdr['p1'] not in (63488,)):
            font_png(path + '.png', body)
            kind = 'font?'
        if hdr and hdr['type'] == 3 and not src and len(body) != 6912:
            sk = disassemble(path + '.bin', hdr['p1'], len(body))
            if sk:
                open(path + '.skool', 'w').write(sk)
                kind = (kind + ', ' if kind else '') + 'disasm'
        report.append(line + (' -> ' + kind if kind else ''))
        hdr = None
    with open(os.path.join(out, 'blocks.txt'), 'w') as f:
        f.write('\n'.join(report) + '\n')
    print('%s: %d blocks -> %s' % (tap, len(report), out))


if __name__ == '__main__':
    main()
