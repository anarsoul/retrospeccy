# rk86mon.tap: the Radio-86RK Monitor on a +2A/+3.  The other tapes are
# programs for it in the RK tape format, as pulse sequences: load them with
# directive I.  "make wav" gives the same recordings as WAV files.
RK = ../rk86_plus3
TAPES = piton.tzx basic.tzx rdisk1.tzx rdisk2.tzx dumpcor.tzx

all: rk86mon.tap $(TAPES)
wav: $(TAPES:.tzx=.wav)

# The 32K Monitor is made from the 16K one on the green_svema tape.
mon32.bin: mkmon.py ../green_svema/side_1/svema_31/02_MONIOK-1.bin
	./mkmon.py ../green_svema/side_1/svema_31/02_MONIOK-1.bin mon32.bin

rk86mon.tap: rk86mon.asm mon32.bin $(RK)/console.inc $(RK)/render.inc ../green_svema/side_1/svema_27/12_Radio_Font.bin
	sjasmplus --nologo --msg=war rk86mon.asm

# "Piton" from the green_svema tape (side 1, record 26) with the changes of
# $(RK)/piton.asm: 24 rows instead of 25, video memory of the 32K machine,
# O P Q A instead of the arrow keys.
PITON = ../green_svema/side_1/svema_26/02_RADIO_FILE.bin
PITON_PATCH = 113E=C277 114B=C47E 1156=18 115C=18 1167=947E 117E=4F 1186=50 118E=51 1196=41 11F5=E777 1274=37

piton.tzx piton.wav: $(PITON) rk2wav.py Makefile
	./rk2wav.py $(PITON) $@ --raw 1100 $(PITON_PATCH)

# BASIC needs the same two patches as in $(RK)/Makefile: it tests the parity
# flag after arithmetic, which is the overflow flag on a Z80.
BASIC_PATCH = 12D0=C3EE19 19EE=9F2803CB2FC93CC9 096E=C3F619 19F6=8FB7E81E18C3D802

basic.tzx basic.wav: $(RK)/BASIC80.RKR rk2wav.py Makefile
	./rk2wav.py $(RK)/BASIC80.RKR $@ $(BASIC_PATCH)

rdisk1.tzx rdisk1.wav: $(RK)/RDISK1.PKI rk2wav.py
	./rk2wav.py $(RK)/RDISK1.PKI $@

rdisk2.tzx rdisk2.wav: $(RK)/RDISK2.PKI rk2wav.py
	./rk2wav.py $(RK)/RDISK2.PKI $@

dumpcor.tzx dumpcor.wav: $(RK)/DUMPCOR1.RK rk2wav.py
	./rk2wav.py $(RK)/DUMPCOR1.RK $@

# Needs SkoolKit (pip install skoolkit).
test: rk86mon.tap
	./test.py

.PHONY: all wav test
