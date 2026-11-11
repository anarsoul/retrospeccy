; PATCH2.EXE - CODE 63768,117 (from transparent_a_26.tzx)
; Byte-identical to PATCH.EXE except relocated from #F900 to #F918
; AY-3-8912 helper (ZX Spectrum 128 ports: #FFFD = register select, #BFFD = data)
;
; In:  C = 0..2 -> set tone period of channel A/B/C to HL>>4 and enable its tone
;      C = 3    -> disable tone on channels selected by top 2 bits of H and of L
;                  (00=A, 01=B, 10/11=C); noise is disabled on all channels
; All registers preserved.

        org     #F918

AY_SEL  equ     #FFFD
                                ; data port #BFFD is reached by ld b,#BF

entry:  push    af              ; F918  F5
        push    bc              ; F919  C5
        push    de              ; F91A  D5
        push    hl              ; F91B  E5
        ld      a,c             ; F91C  79
        cp      3               ; F91D  FE 03
        jr      z,mute          ; F91F  28 44
        ld      d,c             ; F921  51          D = channel 0..2
        inc     c               ; F922  0C          C = 1..3
        cp      3               ; F923  FE 03       BUG: tests A (old C, never 3 here),
        jr      nz,nofix        ; F925  20 01       so always jumps; meant to turn 3 into 4
        inc     c               ; F927  0C          (dead code)
nofix:  ld      a,c             ; F928  79
        cpl                     ; F929  2F
        ld      c,a             ; F92A  4F          C = ~mask: FE, FD, FC (should be FB for ch.C)
        ld      a,(mixer)       ; F92B  3A 8C F9
        and     c               ; F92E  A1          clear bit -> tone enabled
        ld      (mixer),a       ; F92F  32 8C F9
        ld      b,4             ; F932  06 04
        ld      a,l             ; F934  7D
        and     #F0             ; F935  E6 F0       (also clears carry)
        ld      l,a             ; F937  6F
shr4:   rr      h               ; F938  CB 1C       HL = HL >> 4 (12-bit tone period)
        rr      l               ; F93A  CB 1D
        djnz    shr4            ; F93C  10 FA
        ld      a,d             ; F93E  7A
        rlca                    ; F93F  07          A = channel*2 = fine tone register
        ld      bc,AY_SEL       ; F940  01 FD FF
        out     (c),a           ; F943  ED 79       select R0/R2/R4
        ld      b,#BF           ; F945  06 BF
        out     (c),l           ; F947  ED 69       fine tone
        ld      b,#FF           ; F949  06 FF
        inc     a               ; F94B  3C
        out     (c),a           ; F94C  ED 79       select R1/R3/R5
        ld      b,#BF           ; F94E  06 BF
        out     (c),h           ; F950  ED 61       coarse tone
wrmix:  ld      bc,AY_SEL       ; F952  01 FD FF
        ld      a,7             ; F955  3E 07
        out     (c),a           ; F957  ED 79       select R7 (mixer)
        ld      b,#BF           ; F959  06 BF
        ld      a,(mixer)       ; F95B  3A 8C F9
        out     (c),a           ; F95E  ED 79
        pop     hl              ; F960  E1
        pop     de              ; F961  D1
        pop     bc              ; F962  C1
        pop     af              ; F963  F1
        ret                     ; F964  C9

mute:   ld      a,h             ; F965  7C
        call    chmask          ; F966  CD 81 F9
        ld      h,a             ; F969  67
        ld      a,(mixer)       ; F96A  3A 8C F9
        or      #38             ; F96D  F6 38       noise off on A,B,C
        or      h               ; F96F  B4          tone off on channel from H
        ld      (mixer),a       ; F970  32 8C F9
        ld      a,l             ; F973  7D
        call    chmask          ; F974  CD 81 F9
        ld      l,a             ; F977  6F
        ld      a,(mixer)       ; F978  3A 8C F9
        or      l               ; F97B  B5          tone off on channel from L
        ld      (mixer),a       ; F97C  32 8C F9
        jr      wrmix           ; F97F  18 D1

; A bits 7..6 -> mixer tone bit: 00->1 (A), 01->2 (B), 10->4 (C), 11->4 (C)
chmask: and     #C0             ; F981  E6 C0
        rlca                    ; F983  07
        rlca                    ; F984  07
        inc     a               ; F985  3C
        cp      3               ; F986  FE 03
        ret     nz              ; F988  C0
        ld      a,4             ; F989  3E 04
        ret                     ; F98B  C9

mixer:  db      #FF             ; F98C  shadow of AY R7 (all off initially)
