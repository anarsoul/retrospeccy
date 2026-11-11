; HAINTMON - green_svema/side_2/svema_b_30 (BASIC loader) and svema_b_31 (code)
;
; A tiny resident memory monitor that lives in the shadow RAM under the ROM and
; is polled from the frame interrupt, so it can be popped up over any running
; program with SYMBOL SHIFT + SPACE.
;
; The tape holds two code blocks:
;   "Haintmonc$"  CODE 55000,39     copies the ROM into the shadow RAM
;   "HAINTMON"    CODE 14446,1170   image of #386E-#3CFF of that ROM copy
; and a BASIC loader:
;   1 FOR N=14592 TO 14847: POKE N,0: LOAD ""CODE :
;     FOR N=50000 TO 50006: READ A: POKE N,A: NEXT N:
;     DATA 62,57,237,71,237,94,201: RANDOMIZE USR 50000
; i.e. LD A,#39 / LD I,A / IM 2 / RET.
;
; Layout of the 1170-byte image:
;   #386E-#39FF  zeros (#3900-#39FF is the IM 2 vector table for I=#39)
;   #3A00-#3AD3  the monitor (below)
;   #3AD4-#3C6F  #FF, unused
;   #3C70-#3CCF  NMI handler that was already in this ROM, with the text
;                "COMPLETE  OLEG BOIKO     MINSK   1990" (listed at the end)
;
; As saved it does not seem to work.  The table is all zeros and the Baltik
; puts #FF on the data bus, so the IM 2 vector is read from #39FF and #3A00:
; low byte 0, high byte = the first byte of the monitor, #CD (CALL).  The
; interrupt goes to #CD00.  The same trick works in the Radio-86RK emulator
; from this tape because its handler starts with PUSH AF = #F5 and I is #F5;
; here the first byte would have to be #39, ADD HL,SP.  On a stock ROM with
; empty memory the CPU runs from #CD00 over zeros and the UDGs into #0005.

; ---------------------------------------------------------------------------
; "Haintmonc$": ROM -> shadow RAM.  The control port is written as OUT (0),A,
; i.e. port #xx00 with A on the high address byte (elsewhere on these tapes the
; same latch is written through port #7E).  Bit 7 = 1 selects RAM at 0-#3FFF.

        org     55000

        di
        ld      a,3
        out     (0),a           ; ROM visible
        ld      hl,0
        ld      de,#8000
        ld      bc,#4000
        ldir                    ; ROM -> #8000
        ld      a,#FF
        out     (0),a           ; RAM in place of the ROM
        ld      hl,#8000
        ld      de,0
        ld      bc,#4000
        ldir                    ; #8000 -> shadow RAM
        ld      a,#FC
        out     (0),a
        ei
        jp      0               ; restart, now running from RAM

; ---------------------------------------------------------------------------
; The monitor.
; Keys: SYMBOL SHIFT + SPACE  open
;       1 / 2    decrement / increment the byte at the cursor
;       3 / 4    previous / next address
;       Q / W    slow / fast key repeat
;       E        jump to the current address
;       5        close
; The top-left corner shows "AAAA,DD": address and byte, in hex.

        org     #3A00

        call    INTENT          ; 3A00  (entered here the ROM handler below
                                ;        runs twice per interrupt)
INTENT: call    #0038           ; 3A03  normal ROM interrupt: FRAMES, keyboard
        push    bc              ; 3A06
        push    hl
        push    de
        push    af
        ld      bc,#7FFE
        in      a,(c)
        bit     0,a             ;       SPACE
        jr      nz,NOMON
        bit     1,a             ;       SYMBOL SHIFT
        jr      nz,NOMON
        call    MON
NOMON:  ld      bc,#7FFE        ; 3A18
        in      a,(c)
        pop     af
        pop     de
        pop     hl
        pop     bc
        ret

MON:    di                      ; 3A24
        ld      hl,#7FFF        ;       start address
        ld      d,0             ;       0 = fast repeat
LOOP:   call    K_INC           ; 3A2A
        call    K_DEC
        call    K_NEXT
        call    K_PREV
        ld      bc,#F7FE
        in      a,(c)
        bit     4,a             ;       5 = close
        jr      nz,SHOW
        ei
        ret
SHOW:   call    K_SLOW          ; 3A41
        call    K_FAST
        call    K_RUN
        ld      a,#16           ;       AT 0,0
        rst     #10
        ld      a,0
        rst     #10
        rst     #10
        ld      a,h
        call    HEX
        ld      a,l
        call    HEX
        ld      a,","
        rst     #10
        ld      a,(hl)
        call    HEX
        call    DELAY
        jr      LOOP

K_INC:  ld      bc,#F7FE        ; 3A65
        in      a,(c)
        bit     1,a             ;       2
        ret     nz
        inc     (hl)
        ret
K_DEC:  ld      bc,#F7FE        ; 3A6F
        in      a,(c)
        bit     0,a             ;       1
        ret     nz
        dec     (hl)
        ret
K_NEXT: ld      bc,#F7FE        ; 3A79
        in      a,(c)
        bit     3,a             ;       4
        ret     nz
        inc     hl
        ret
K_PREV: ld      bc,#F7FE        ; 3A83
        in      a,(c)
        bit     2,a             ;       3
        ret     nz
        dec     hl
        ret
K_SLOW: ld      bc,#FBFE        ; 3A8D
        in      a,(c)
        bit     0,a             ;       Q
        ret     nz
        ld      d,1
        ret
K_FAST: ld      bc,#FBFE        ; 3A98
        in      a,(c)
        bit     1,a             ;       W
        ret     nz
        ld      d,0
        ret
K_RUN:  ld      bc,#FBFE        ; 3AA3
        in      a,(c)
        bit     2,a             ;       E
        ret     nz
        jp      (hl)
DELAY:  ld      a,0             ; 3AAC
        cp      d
        ret     z
        ld      bc,10000
DLY1:   dec     bc
        ld      a,b
        or      c
        jr      nz,DLY1
        ret
HEX:    push    af              ; 3AB9  print A as two hex digits
        rrca
        rrca
        rrca
        rrca
        call    HEX1
        pop     af
HEX1:   and     #0F             ; 3AC2
        add     a,#90
        daa
        adc     a,#40
        daa
        push    iy
        ld      iy,#5C3A        ;       the ROM printing needs IY
        rst     #10
        pop     iy
        ret                     ; 3AD3

; ---------------------------------------------------------------------------
; NMI handler found in the same ROM area (not part of HAINTMON).
; Keys: C = return to the program, B = break to BASIC, M = jump to #0069 with
; A=#FF (in this ROM #0066 evidently holds a JP here, so #0069 is not the
; stock Sinclair code).

        org     #3C70

NMI:    push    af
NMI1:   ld      a,6
        out     (#FE),a         ;       yellow border
        ld      a,#FE
        in      a,(#FE)
        bit     3,a             ;       C
        jr      nz,NMI2
        pop     af
        retn
NMI2:   ld      a,#7F
        in      a,(#FE)
        bit     4,a             ;       B
        jp      z,TOBAS
        bit     2,a             ;       M
        ld      a,1
        out     (#FE),a         ;       blue border
        jr      nz,NMI1
        ld      a,#FF
        jp      #0069
TOBAS:  ld      sp,(#5CB2)      ; 3C96  RAMTOP
        dec     sp
        ld      hl,#1303        ;       main loop of the BASIC ROM
        push    hl
        ld      a,#3F
        jp      #04AA
        defm    "    COMPLETE  OLEG BOIKO     MINSK   1990 "
