#!/usr/bin/env python3
"""Add id attributes to the headings of HTML produced by cmark-gfm.

cmark-gfm does not generate heading anchors, so links like [text](#section)
would not work in README.html.  The ids are built the same way GitHub builds
them: lower case, punctuation dropped, spaces turned into hyphens, a numeric
suffix for repeated titles.

Usage: cmark-gfm README.md | readme_ids.py > body.html
       readme_ids.py --toc README.md      # print a table of contents
"""
import html
import re
import sys


def slug(title, seen):
    s = re.sub(r'[^\w\- ]', '', title.lower(), flags=re.UNICODE).replace(' ', '-')
    n = seen.get(s, 0)
    seen[s] = n + 1
    return s if n == 0 else '%s-%d' % (s, n)


def md_title(line):
    """Heading text as rendered: no leading #, no backticks."""
    return line.lstrip('#').strip().replace('`', '')


def toc(path):
    seen, out, fence = {}, [], False
    for line in open(path, encoding='utf-8'):
        if line.startswith('```'):
            fence = not fence
        m = re.match(r'(#{1,3}) ', line)
        if fence or not m:
            continue
        level = len(m.group(1))
        anchor = slug(md_title(line), seen)
        if level >= 2 and md_title(line) != 'Оглавление':
            out.append('%s- [%s](#%s)' % ('  ' * (level - 2), line.lstrip('#').strip(), anchor))
    return '\n'.join(out)


def add_ids(text):
    seen = {}

    def repl(m):
        plain = html.unescape(re.sub(r'<[^>]+>', '', m.group(2)))
        return '<h%s id="%s">%s</h%s>' % (m.group(1), slug(plain, seen), m.group(2), m.group(1))
    return re.sub(r'<h([1-6])>(.*?)</h\1>', repl, text, flags=re.S)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--toc':
        print(toc(sys.argv[2]))
    else:
        sys.stdout.write(add_ids(sys.stdin.read()))
