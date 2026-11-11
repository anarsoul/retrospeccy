; 1-bit sampler with run-length packing.
; A working version of the unnamed CODE 64000,104 from the green_svema tape
; (side 2, records b_48 and b_49), with a more economical buffer format.
;
;   LET n=USR 64000       record from EAR until a key is pressed or the buffer is full;
;                         returns the number of buffer bytes used
;   RANDOMIZE USR 64003   play through the speaker; any key stops
;
; A byte of the sound is eight samples, bit 0 first.  The buffer is a chain of runs:
;   #81..#FF, byte     the byte repeated 1..127 times
;   #01..#7F, bytes    that many bytes as they are
;   #00                end of the recording
; Three equal bytes in a row are enough to start a repeat.
;
; Every path through REC and through PLAY takes the same time, so samples are
; 43 T apart inside a byte and 268 T apart across a byte boundary in both.  All
; the "pad" instructions are there for that; do not remove them.

        DEVICE ZXSPECTRUM48

        ORG 64000

BUF     EQU 26000               ; #6590, as in the original
BUFTOP  EQU #F9                 ; recording stops when the pointer reaches #F900

        JP REC
        JP PLAY

; ---------------------------------------------------------------- recording
; HL next free byte, DE control byte of the current run, B its value,
; IXH previous byte, IXL the one before it, C the byte just read.
; (IXH and IXL are the halves of IX: undocumented but present on every Z80.)

RSTOP   LD (HL),0               ; end mark
        LD BC,1-BUF
        ADD HL,BC
        LD B,H
        LD C,L                  ; bytes used, for BASIC
        CALL NOKEY
        EI
        RET

REC     DI
        CALL NOKEY
        LD HL,BUF
        LD B,#FF                ; "a full repeat run": the first byte opens a new run
RLOOP   CALL IN8
        JR NZ,RSTOP
        LD A,C
        BIT 7,B
        JP Z,RLIT
        CP IXH                  ; in a repeat run
        JR NZ,RNEW1
        LD A,B
        INC A
        JR Z,RNEW2              ; 127 already
        LD B,A
        LD (DE),A               ; one more of the same
        LD A,6
        DEC A
        JR NZ,$-1               ; pad
        LD A,0                  ; pad
        JP RLOOP
RLIT    CP IXH                  ; in a run of plain bytes
        JR NZ,RAPP1
        CP IXL
        JR NZ,RAPP2
        LD A,B                  ; the third equal byte: turn the last two into a repeat
        SUB 2
        JR Z,RCONV1
        LD (DE),A               ; the run gets two bytes shorter...
        DEC HL
        DEC HL                  ; ...and the repeat goes where they were:
        LD B,#83                ; the second of them stays as the repeated byte
        LD (HL),B
        LD D,H
        LD E,L
        INC HL
        INC HL
        LD A,0                  ; pad
        JR $+2                  ; pad
        LD A,(0)                ; pad
        LD A,(0)                ; pad
        JP RLOOP
RCONV1  DEC HL                  ; the run was just these two bytes: reuse its control byte
        LD A,#83
        LD B,A
        LD (DE),A
        LD A,3
        DEC A
        JR NZ,$-1               ; pad
        LD A,0                  ; pad
        JR $+2                  ; pad
        JP RLOOP
RNEW1   NOP                     ; pad
        NOP                     ; pad
        LD A,0                  ; pad
RNEW2   JP $+3                  ; pad
        LD A,(0)                ; pad
RNEW    LD D,H                  ; open a run of plain bytes
        LD E,L
        LD B,1
        LD (HL),B
        INC HL
        LD (HL),C
        INC HL
        LD A,C
        LD IXH,A
        INC A
        LD IXL,A                ; not equal to C, so the next byte cannot look like the third equal one
        JR RTOP
RAPP1   NOP                     ; pad
        NOP                     ; pad
        LD A,0                  ; pad
RAPP2   LD A,B
        CP 127
        JR Z,RNEW
        INC A                   ; add the byte to the run
        LD B,A
        LD (DE),A
        LD (HL),C
        INC HL
        LD A,IXH
        LD IXL,A
        LD A,C
        LD IXH,A
        LD A,(0)                ; pad
        LD A,(0)                ; pad
RTOP    LD A,H
        CP BUFTOP
        JP C,RLOOP
        JP RSTOP

; Eight samples of EAR into C, 43 T apart.  NZ if a key is down.
IN8     LD C,#80                ; the set bit falls out after eight shifts
IN8L    XOR A                   ; high byte 0: all keyboard rows
        IN A,(#FE)
        RLCA
        RLCA                    ; carry = bit 6, EAR
        RR C
        JR NC,IN8L
        OR #83                  ; key bits are now in bits 2-6
        INC A
        RET

; ---------------------------------------------------------------- playback
; HL next byte of the buffer, E bytes left in the run, D = 0 in a repeat,
; C the byte being played.

PLAY    DI
        CALL NOKEY
        LD HL,BUF
PRUN    LD A,(HL)
        INC HL
        OR A
        JR Z,PDONE
        JP M,PREP
        LD E,A
        LD D,1
        LD B,5
        DJNZ $                  ; pad
        NOP                     ; pad
        NOP                     ; pad
        JP $+3                  ; pad
        JR PLIT
PREP    AND #7F
        LD E,A
        LD D,0
        LD C,(HL)
        INC HL
        LD B,6
        DJNZ $                  ; pad
        JP $+3                  ; pad
        JR POUT
PSAME   BIT 0,D
        JR Z,PSAME1
        LD B,9
        DJNZ $                  ; pad
        NOP                     ; pad
        NOP                     ; pad
        LD A,0                  ; pad
PLIT    LD C,(HL)
        INC HL
        JR POUT
PSAME1  LD B,11
        DJNZ $                  ; pad
        LD A,R                  ; pad
POUT    LD B,8
PBIT    RRC C
        SBC A,A
        AND #10                 ; the speaker bit only: border and MIC stay 0
        OUT (#FE),A
        DJNZ PBIT
        XOR A
        IN A,(#FE)
        OR #E0
        INC A
        JR NZ,PDONE             ; a key stops playback
        DEC E
        JR NZ,PSAME
        JR PRUN
PDONE   CALL NOKEY
        EI
        RET

; Wait until no key is down: the one that started us from BASIC, or stopped us.
NOKEY   XOR A
        IN A,(#FE)
        OR #E0
        INC A
        JR NZ,NOKEY
        RET
code_end

        DEFINE TITLE "1-BIT SAMPLER: RUN-LENGTH"
        DEFINE TAPNAME "rle.tap"
        INCLUDE "shell.inc"
