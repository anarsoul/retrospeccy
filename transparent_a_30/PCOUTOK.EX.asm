; PCOUTOK.EX - CODE 23296,54 (from transparent_a_30.tzx)
; Assembled form of PCOUTOK.TX (matches the source byte for byte).
; Sends DE bytes starting at HL to a PC, bit-serially (MSB first) through an
; 8255 PPI at ports 31/63/95/127 (A/B/C/control):
;   port B bit 0 (out 63) = data bit, port C bit 0 (in 95) = handshake from PC
;   (wait for 1, then wait for 0, per bit). Any key on the bottom-left
;   half-rows aborts (checked after every byte via port 254).
; PcOut.BAS patches the operands at 23301 (HL) and 23304 (DE) before calling.

        org     #5B00           ; printer buffer

        ld      a,#99           ; 5B00  3E 99       8255 mode 0: A in, B out, C in
        out     (#7F),a         ; 5B02  D3 7F
        ld      hl,30000        ; 5B04  21 30 75    patched by BASIC -> 25000
        ld      de,6912         ; 5B07  11 00 1B    patched by BASIC -> length+4
new:    ld      a,(hl)          ; 5B0A  7E
        ld      b,8             ; 5B0B  06 08
        ld      c,a             ; 5B0D  4F
again:  ld      a,c             ; 5B0E  79
        rlca                    ; 5B0F  07
        ld      c,a             ; 5B10  4F
        and     1               ; 5B11  E6 01
        out     (#3F),a         ; 5B13  D3 3F       put data bit
l1:     in      a,(#5F)         ; 5B15  DB 5F
        bit     0,a             ; 5B17  CB 47
        jr      z,l1            ; 5B19  28 FA       wait for handshake high
        ld      a,c             ; 5B1B  79
        and     1               ; 5B1C  E6 01
        out     (#3F),a         ; 5B1E  D3 3F       (same bit again)
l3:     in      a,(#5F)         ; 5B20  DB 5F
        bit     0,a             ; 5B22  CB 47
        jr      nz,l3           ; 5B24  20 FA       wait for handshake low
        djnz    again           ; 5B26  10 E6
        in      a,(#FE)         ; 5B28  DB FE
        and     #1F             ; 5B2A  E6 1F
        cp      #1F             ; 5B2C  FE 1F
        ret     nz              ; 5B2E  C0          key pressed -> abort
        inc     hl              ; 5B2F  23
        dec     de              ; 5B30  1B
        ld      a,d             ; 5B31  7A
        or      e               ; 5B32  B3
        jr      nz,new          ; 5B33  20 D5
        ret                     ; 5B35  C9
