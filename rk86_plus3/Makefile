all: rk86.tap piton.tap basic.tap rdisk1.tap rdisk2.tap

rk86.tap: rk86.asm ../green_svema/side_1/svema_27/12_Radio_Font.bin
	sjasmplus --nologo --msg=war rk86.asm

piton.tap: piton.asm ../green_svema/side_1/svema_26/02_RADIO_FILE.bin
	sjasmplus --nologo --msg=war piton.asm

# BASIC80 is Microsoft 8080 code that relies on the parity flag after
# arithmetic: the floating point compare returns #FF, 0 or 1 and its callers
# test the result with JPO/JPE.  A Z80 gives overflow in that flag, and PRINT
# of any number hangs.  The same thing in Altair BASIC is described in
#   https://hackaday.io/project/190345/log/219462-another-interesting-basic-to-test-the-8080-instructions
# and in the SIMH AltairZ80 notes ("will not or not properly run on a Z80.
# This is mainly due to the use of the parity flag on the 8080").
# Two places are redirected into the 18 spare zero bytes at the end of the
# interpreter:
#   #12D0  SBB A : RNZ : INR A : RET  ->  JP #19EE
#   #19EE  SBC A,A : JR Z,+3 : SRA A : RET : INC A : RET
#          (same A and carry; SRA gives #FF the even parity the 8080 had)
#   #096E  ADC A : RPE : MVI E,#18 : JMP #02D8  ->  JP #19F6
#   #19F6  ADC A,A : OR A : RET PE : LD E,#18 : JP #02D8
#          (the type check: OR A turns the flag into parity)
BASIC_PATCH = 12D0=C3EE19 19EE=9F2803CB2FC93CC9 096E=C3F619 19F6=8FB7E81E18C3D802

basic.tap: BASIC80.RKR rkr2tap.py Makefile
	./rkr2tap.py BASIC80.RKR basic.tap $(BASIC_PATCH)

# RAMDOS V2.01 with its RAM disk, as memory images: no patches needed.
rdisk%.tap: RDISK%.PKI rkr2tap.py
	./rkr2tap.py $< $@

.PHONY: all
