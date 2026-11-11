; 1-bit sampler that stores the time between level changes.
; A companion to rle.asm: the same idea as the unnamed CODE 64000,104 from the
; green_svema tape (side 2, records b_48 and b_49), but packing what a 1-bit
; signal really consists of.
;
;   LET n=USR 64000       record from EAR until a key is pressed or the buffer is full;
;                         returns the number of buffer bytes used
;   RANDOMIZE USR 64003   play through the speaker; any key stops
;
; Buffer: the first byte is the starting level (#40 or 0), then one byte per interval:
;   1..254   the level stays for that many samples, then changes
;   255      it stays for 254 samples and does not change
;   0        end of the recording
; A sample is 49 T; the first one after a level change (or after a 255) is 123 T,
; in REC and in PLAY alike.  The "pad" instructions are there for that.

        DEVICE ZXSPECTRUM48

        ORG 64000

BUF     EQU 26000               ; #6590, as in the original
BUFTOP  EQU #F9                 ; recording stops when the pointer reaches #F900

        JP REC
        JP PLAY

; HL next free byte, B samples at this level + 1, C what the port reads while
; nothing changes: the level in bit 6 and no keys in bits 0-4.

REC     DI
        CALL NOKEY
        LD HL,BUF
        XOR A                   ; high byte 0: all keyboard rows
        IN A,(#FE)
        AND #40
        LD (HL),A               ; starting level
        OR #1F
        LD C,A
        NOP                     ; pad
        LD A,0                  ; pad
        LD A,(0)                ; pad
        LD A,(0)                ; pad
        JR RNEXT
RLOOP   XOR A
        IN A,(#FE)
        AND #5F
        CP C
        JR NZ,RDIFF
        INC B
        JR NZ,RLOOP             ; 49 T per sample
        LD (HL),255             ; 254 samples and still no change
        JP $+3                  ; pad
        LD A,(0)                ; pad
        JR RNEXT
RDIFF   LD D,A
        OR #40
        CP #5F
        JR NZ,RSTOP             ; a key, not the signal
        DEC B
        LD (HL),B               ; length of the interval
        LD C,D
        NOP                     ; pad
        LD A,0                  ; pad
RNEXT   INC HL
        LD B,2
        LD A,H
        CP BUFTOP
        JP C,RLOOP
RSTOP   LD (HL),0               ; end mark
        LD BC,1-BUF
        ADD HL,BC
        LD B,H
        LD C,L                  ; bytes used, for BASIC
        CALL NOKEY
        EI
        RET

; HL next byte, C current output, D what to flip after the interval, B samples left.

PLAY    DI
        CALL NOKEY
        LD HL,BUF
        LD A,(HL)
        INC HL
        RRCA
        RRCA                    ; bit 6 to bit 4, the speaker; border and MIC stay 0
        LD C,A
        LD D,0
        JR PFLIP
PNEXT   LD A,(HL)
        INC HL
        OR A
        JR Z,PDONE
        LD D,#10
        LD B,A
        INC A
        JR NZ,PPAD
        LD B,254                ; 255: wait as long, flip nothing
        LD D,A
        LD A,0                  ; pad
        NOP                     ; pad
        NOP                     ; pad
PCNT    DEC B
        JR Z,PFLIP
PWAIT   LD A,0
        IN A,(#FE)
        OR #E0
        INC A
        JR NZ,PDONE             ; a key stops playback
        DJNZ PWAIT              ; 49 T per sample
        JP $+3                  ; pad
PFLIP   LD A,C
        XOR D
        LD C,A
        OUT (#FE),A
        JR PNEXT
PPAD    LD A,R                  ; pad
        JR PCNT
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

        DEFINE TITLE "1-BIT SAMPLER: INTERVALS"
        DEFINE TAPNAME "delta.tap"
        INCLUDE "shell.inc"
