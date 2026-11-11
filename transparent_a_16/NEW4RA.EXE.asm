; NEW4RA.EXE - CODE 14446,260 (transparent_a_16.tzx)
; "Save Game Situation": NMI handler living in the unused area of the 48K ROM
; image (#386E..), which the BASIC loader copies into shadow RAM under the ROM.
; Labels are taken from NEW3RA.TXT (transparent_a_14); NEW4RA differs from
; NEW3RA.EXE only where marked with [4].
;
; Entered from #0066 (patched by the loader to DI / JP #386E) with the
; interrupted PC on the program's stack.
;
; Memory layout assumed (port #7FFD written as OUT (#FD) with A on A8-A15):
;   value 7 = the page the 48K program normally has at #C000
;   value 1 = copy of #4000-#7FFF     value 3 = copy of #8000-#BFFF
;   value 4 = copy of #C000-#FFFF     value 6 = saved registers
; Page 6: #FFFE = program SP, #FFFC = SP inside the register frame,
;         #FFE5..#FFFA = register frame (11 words).
;
; Keys: SPACE = save, B = load, C = skip to the exit prompt
;       exit prompt (green border): SYM SHIFT = return with EI, N = with DI
;       IM prompt (red border, only if I < #3F): M = IM 2

        org     #386E

PROGR:  push    af              ; 386E  AF stays on the program's stack
TESTK:  ld      a,#7F           ; 386F  row SPACE/SYM/M/N/B
        in      a,(#FE)
        bit     0,a
        jr      z,SAVE          ;       SPACE
        bit     4,a
        jr      z,LOAD          ;       B
        ld      a,#FE           ;       row CAPS/Z/X/C/V
        in      a,(#FE)
        bit     3,a
        jr      z,NORA2         ;       C
        jr      TESTK

; ---- save: registers -> page 6, memory -> pages 1,3,4
SAVE:   ld      a,6             ; 3885
        out     (#FD),a
        ld      (#FFFE),sp      ;       program SP
        ld      sp,#FFFB
        push    bc
        push    de
        push    hl
        push    ix
        push    iy
        ld      a,i             ;       (also puts IFF2 into P/V - never used)
        push    af
        ld      a,r
        push    af
        ex      af,af'
        exx
        push    af              ;       alternate set
        push    bc
        push    de
        push    hl
        ld      (#FFFC),sp      ;       = #FFE5
        ld      a,1
        out     (#FD),a
        ld      hl,#4000        ;       #4000-#7FFF (with the screen) -> page 1
        ld      de,#C000
        ld      bc,#4000
        ldir
        ld      a,3
        out     (#FD),a
        ld      hl,#8000        ;       #8000-#BFFF -> page 3
        ld      de,#C000
        ld      bc,#4000
        ldir
        ld      hl,#C000        ;       #C000-#FFFF: page 7 -> page 4,
        ld      bc,#4000        ;       one byte at a time, both sit at #C000
SL1:    ld      a,7
        out     (#FD),a
        ld      d,(hl)
        ld      a,4
        out     (#FD),a
        ld      (hl),d
        inc     hl
        dec     bc
        ld      a,b
        or      c
        jr      nz,SL1
        jr      RETURN          ;       registers are reloaded from page 6

NORA2:  jr      NORAM           ; 38DD  relay, NORAM is out of JR range

; ---- load: pages 1,3,4 -> memory
LOAD:   ld      a,1             ; 38DF
        out     (#FD),a
        ld      hl,#C000
        ld      de,#4000
        ld      bc,#4000
        ldir
        ld      a,3
        out     (#FD),a
        ld      hl,#C000
        ld      de,#8000
        ld      bc,#4000
        ldir
        ld      hl,#C000
        ld      bc,#4000
LL1:    ld      a,4
        out     (#FD),a
        ld      d,(hl)
        ld      a,7
        out     (#FD),a
        ld      (hl),d
        inc     hl
        dec     bc
        ld      a,b
        or      c
        jr      nz,LL1

; ---- common: restore registers from page 6
RETURN: ld      a,6             ; 3913
        out     (#FD),a
        ld      sp,(#FFFC)
        pop     hl              ;       alternate set (we are still swapped)
        pop     de
        pop     bc
        pop     af
        exx
        ex      af,af'
        pop     af
        ld      r,a
        pop     af
        ld      i,a
        cp      #3F
        jr      nc,NOMOD2       ;       I >= #3F: interrupt mode left alone
                                ;       BUG: condition is inverted, the prompt
                                ;       should appear for I > #3F (table in
                                ;       RAM). Fix: CP #40 / JR C,NOMOD2
                                ;       (bytes at #3928: 3F 30 -> 40 38)
        ld      a,2             ;       red border: "IM 2?"
        out     (#FE),a
INTM2:  ld      a,#7F
        in      a,(#FE)
        bit     2,a
        jr      z,SETMO2        ;       M -> IM 2
        ld      a,#FE
        in      a,(#FE)
        bit     0,a
        jr      nz,NOMOD2       ;       CAPS SHIFT *not* held -> go on at once;
        jr      INTM2           ;       the prompt only waits while CAPS is held
SETMO2: im      2
NOMOD2: pop     iy              ; 3943
        pop     ix
        pop     hl
        pop     de
        pop     bc
        ld      sp,(#FFFE)      ; 394A  [4] back to the program's stack.
                                ;       Missing in NEW3RA: there POP AF/RETN
                                ;       below run with SP=#FFFB in page 7.

; ---- exit prompt
NORAM:  ld      a,4             ; 394E  green border
        out     (#FE),a
        ld      a,7             ;       back to the program's page
        out     (#FD),a
AGAIN:  ld      a,#7F
        in      a,(#FE)
        bit     1,a
        jr      z,ENABLE        ;       SYM SHIFT
        bit     3,a
        jr      z,DISABL        ;       N
        jr      AGAIN
ENABLE: ld      a,0             ;       border black (original colour is lost)
        out     (#FE),a
        pop     af
        ei
        ret                     ; 396A  [4] RETN in NEW3RA
DISABL: ld      a,0
        out     (#FE),a
        pop     af
        di
        ret                     ; 3971  [4] RETN in NEW3RA
