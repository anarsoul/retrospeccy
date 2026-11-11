all: rle.tap delta.tap

rle.tap: rle.asm shell.inc
	sjasmplus --nologo --msg=war rle.asm

delta.tap: delta.asm shell.inc
	sjasmplus --nologo --msg=war delta.asm

# Needs SkoolKit (pip install skoolkit): runs both tapes on its Z80 core.
test: all
	./test.py

.PHONY: all test
