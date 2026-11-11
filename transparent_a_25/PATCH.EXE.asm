; PATCH.EXE - CODE 63744,117 (from transparent_a_25.tzx)
; AY-3-8912 helper (ZX Spectrum 128 ports: #FFFD = register select, #BFFD = data)
;
; In:  C = 0..2 -> set tone period of channel A/B/C to HL>>4 and enable its tone
;      C = 3    -> disable tone on channels selected by top 2 bits of H and of L
;                  (00=A, 01=B, 10/11=C); noise is disabled on all channels
; All registers preserved.

        org     #F900

AY_SEL  equ     #FFFD
                                ; data port #BFFD is reached by ld b,#BF

entry:  push    af              ; F900  F5
        push    bc              ; F901  C5
        push    de              ; F902  D5
        push    hl              ; F903  E5
        ld      a,c             ; F904  79
        cp      3               ; F905  FE 03
        jr      z,mute          ; F907  28 44
        ld      d,c             ; F909  51          D = channel 0..2
        inc     c               ; F90A  0C          C = 1..3
        cp      3               ; F90B  FE 03       BUG: tests A (old C, never 3 here),
        jr      nz,nofix        ; F90D  20 01       so always jumps; meant to turn 3 into 4
        inc     c               ; F90F  0C          (dead code)
nofix:  ld      a,c             ; F910  79
        cpl                     ; F911  2F
        ld      c,a             ; F912  4F          C = ~mask: FE, FD, FC (should be FB for ch.C)
        ld      a,(mixer)       ; F913  3A 74 F9
        and     c               ; F916  A1          clear bit -> tone enabled
        ld      (mixer),a       ; F917  32 74 F9
        ld      b,4             ; F91A  06 04
        ld      a,l             ; F91C  7D
        and     #F0             ; F91D  E6 F0       (also clears carry)
        ld      l,a             ; F91F  6F
shr4:   rr      h               ; F920  CB 1C       HL = HL >> 4 (12-bit tone period)
        rr      l               ; F922  CB 1D
        djnz    shr4            ; F924  10 FA
        ld      a,d             ; F926  7A
        rlca                    ; F927  07          A = channel*2 = fine tone register
        ld      bc,AY_SEL       ; F928  01 FD FF
        out     (c),a           ; F92B  ED 79       select R0/R2/R4
        ld      b,#BF           ; F92D  06 BF
        out     (c),l           ; F92F  ED 69       fine tone
        ld      b,#FF           ; F931  06 FF
        inc     a               ; F933  3C
        out     (c),a           ; F934  ED 79       select R1/R3/R5
        ld      b,#BF           ; F936  06 BF
        out     (c),h           ; F938  ED 61       coarse tone
wrmix:  ld      bc,AY_SEL       ; F93A  01 FD FF
        ld      a,7             ; F93D  3E 07
        out     (c),a           ; F93F  ED 79       select R7 (mixer)
        ld      b,#BF           ; F941  06 BF
        ld      a,(mixer)       ; F943  3A 74 F9
        out     (c),a           ; F946  ED 79
        pop     hl              ; F948  E1
        pop     de              ; F949  D1
        pop     bc              ; F94A  C1
        pop     af              ; F94B  F1
        ret                     ; F94C  C9

mute:   ld      a,h             ; F94D  7C
        call    chmask          ; F94E  CD 69 F9
        ld      h,a             ; F951  67
        ld      a,(mixer)       ; F952  3A 74 F9
        or      #38             ; F955  F6 38       noise off on A,B,C
        or      h               ; F957  B4          tone off on channel from H
        ld      (mixer),a       ; F958  32 74 F9
        ld      a,l             ; F95B  7D
        call    chmask          ; F95C  CD 69 F9
        ld      l,a             ; F95F  6F
        ld      a,(mixer)       ; F960  3A 74 F9
        or      l               ; F963  B5          tone off on channel from L
        ld      (mixer),a       ; F964  32 74 F9
        jr      wrmix           ; F967  18 D1

; A bits 7..6 -> mixer tone bit: 00->1 (A), 01->2 (B), 10->4 (C), 11->4 (C)
chmask: and     #C0             ; F969  E6 C0
        rlca                    ; F96B  07
        rlca                    ; F96C  07
        inc     a               ; F96D  3C
        cp      3               ; F96E  FE 03
        ret     nz              ; F970  C0
        ld      a,4             ; F971  3E 04
        ret                     ; F973  C9

mixer:  db      #FF             ; F974  shadow of AY R7 (all off initially)
