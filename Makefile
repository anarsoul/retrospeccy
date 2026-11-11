# Builds README.html (and index.html for GitHub Pages) from README.md with
# cmark-gfm (no pandoc needed).
# readme_ids.py gives the headings ids so that links to sections work.
CMARK ?= cmark-gfm
TITLE := РетроСПЕКтива — разбор двух кассет для ZX Spectrum: Балтик

define HEAD
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$(TITLE)</title>
<style>
body { max-width: 60em; margin: 2em auto; padding: 0 1em; font: 16px/1.5 sans-serif; color: #222; background: #fff; }
table { border-collapse: collapse; margin: 1em 0; }
th, td { border: 1px solid #bbb; padding: .3em .6em; text-align: left; vertical-align: top; }
th { background: #eee; }
code { font-family: monospace; background: #f3f3f3; padding: 0 .2em; }
img { max-width: 100%; height: auto; }
table { display: block; max-width: 100%; overflow-x: auto; }
h2 { border-bottom: 1px solid #ccc; padding-bottom: .2em; margin-top: 2em; }
@media (prefers-color-scheme: dark) {
  body { color: #ddd; background: #1b1b1b; }
  a { color: #8ab4f8; }
  a:visited { color: #c58af9; }
  th { background: #333; }
  th, td { border-color: #555; }
  code { background: #2c2c2c; }
  h2 { border-color: #555; }
}
</style>
</head>
<body>
endef
export HEAD

all: README.html index.html rk86_plus3/index.html

# GitHub Pages serves index.html; it is the same page.
index.html: README.html
	cp $< $@

define RENDER
	{ printf '%s\n' "$$HEAD"; \
	  $(CMARK) --extension table --extension autolink $< | ./readme_ids.py; \
	  printf '</body>\n</html>\n'; } > $@
endef

%.html: %.md Makefile readme_ids.py
	$(RENDER)

# The emulator's own README as a page of the site: links to rk86_plus3/ open
# it rendered both on GitHub (the directory view) and on GitHub Pages.
rk86_plus3/index.html: TITLE := Эмулятор «Радио-86РК» для ZX Spectrum +2A/+3
rk86_plus3/index.html: rk86_plus3/README.md Makefile readme_ids.py
	$(RENDER)

clean:
	rm -f README.html index.html rk86_plus3/index.html

.PHONY: all clean
