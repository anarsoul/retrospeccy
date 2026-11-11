#!/usr/bin/env python3
"""Redraw the hand-drawn IMC-1 schematic (DSC_1665.jpg) as a clean PNG.

The original is drawn "by labels": chips with pin numbers and net names, few
wires.  This redraw keeps that style.  Everything here was read from the
photograph; what could not be read is marked in red on the drawing.
Chip types are not written on the original - the ones given in brackets are
inferred from the pin numbers.

Usage: draw_schematic.py [out.png]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = '/usr/share/fonts/TTF/'
W, H = 3500, 2400
PITCH = 30
STUB = 46
BLACK, GREY, RED, BLUE = (0, 0, 0), (110, 110, 110), (190, 0, 0), (0, 60, 160)
GREEN = (0, 130, 40)             # reconstructed, not on the original sheet


def font(size, bold=False):
    return ImageFont.truetype(FONT_DIR + ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'), size)


F_PIN, F_NUM, F_NET = font(17), font(13), font(17)
F_NAME, F_SUB, F_HEAD, F_TITLE, F_NOTE = font(22, True), font(14), font(24, True), font(34, True), font(16)

img = Image.new('RGB', (W, H), 'white')
d = ImageDraw.Draw(img)


def tw(text, f):
    return d.textlength(text, font=f)


def chip(x, y, w, name, sub, left, right):
    """left/right: list of (pin number, pin name, net) or None for a gap."""
    rows = max(len(left), len(right))
    h = rows * PITCH + 56
    d.rectangle((x, y, x + w, y + h), outline=BLACK, width=3)
    d.text((x + w / 2 - tw(name, F_NAME) / 2, y + 6), name, font=F_NAME, fill=BLACK)
    if sub:
        d.text((x + w / 2 - tw(sub, F_SUB) / 2, y + 32), sub, font=F_SUB, fill=GREY)
    for side, pins in (('L', left), ('R', right)):
        for i, p in enumerate(pins):
            if p is None:
                continue
            num, pname, net = p[:3]
            colour = p[3] if len(p) > 3 else BLUE
            py = y + 56 + i * PITCH + PITCH // 2 - 6
            inv = pname.startswith('/')
            label = pname[1:] if inv else pname
            if side == 'L':
                x0, x1 = x - STUB, x
                d.line((x0, py, x1 - (10 if inv else 0), py), fill=BLACK, width=2)
                if inv:
                    d.ellipse((x - 10, py - 5, x, py + 5), outline=BLACK, width=2)
                d.text((x + 6, py - 11), label, font=F_PIN, fill=BLACK)
                d.text((x - 14 - tw(str(num), F_NUM), py - 17), str(num), font=F_NUM, fill=GREY)
                if net:
                    d.text((x0 - 6 - tw(net, F_NET), py - 11), net, font=F_NET, fill=colour)
            else:
                x0, x1 = x + w, x + w + STUB
                d.line((x0 + (10 if inv else 0), py, x1, py), fill=BLACK, width=2)
                if inv:
                    d.ellipse((x + w, py - 5, x + w + 10, py + 5), outline=BLACK, width=2)
                d.text((x + w - 6 - tw(label, F_PIN), py - 11), label, font=F_PIN, fill=BLACK)
                d.text((x + w + 14, py - 17), str(num), font=F_NUM, fill=GREY)
                if net:
                    d.text((x1 + 6, py - 11), net, font=F_NET, fill=colour)
    return y + h


def frame(x, y, w, h, title):
    d.rectangle((x, y, x + w, y + h), outline=GREY, width=1)
    d.rectangle((x, y, x + tw(title, F_HEAD) + 24, y + 36), fill=(235, 235, 235), outline=GREY)
    d.text((x + 12, y + 4), title, font=F_HEAD, fill=BLACK)


def res(x, y, label, length=90):
    """Horizontal resistor starting at (x, y); returns the x of its far end."""
    d.line((x, y, x + 18, y), fill=BLACK, width=2)
    d.rectangle((x + 18, y - 9, x + length - 18, y + 9), outline=BLACK, width=2)
    d.line((x + length - 18, y, x + length, y), fill=BLACK, width=2)
    d.text((x + length / 2 - tw(label, F_NUM) / 2, y - 27), label, font=F_NUM, fill=BLACK)
    return x + length


def net(x, y, text, right=False, colour=BLUE):
    d.text((x - tw(text, F_NET) - 6 if right else x + 6, y - 11), text, font=F_NET, fill=colour)


def note(x, y, lines, colour=RED):
    for i, line in enumerate(lines):
        d.text((x, y + i * 21), line, font=F_NOTE, fill=colour)


def dot(x, y):
    d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=BLACK)


BUS = ['D%d' % i for i in range(8)]
LATCH_IN = (3, 4, 7, 8, 13, 14, 17, 18)
LATCH_OUT = (2, 5, 6, 9, 12, 15, 16, 19)

d.text((60, 24), 'IMC-1 — «Intellectual Music Card»: эмулятор AY-3-8910 на втором Z80 и КР580ВИ53',
       font=F_TITLE, fill=BLACK)
d.text((2330, 78), 'Синим — цепи с листа.   ', font=F_NOTE, fill=BLUE)
d.text((2530, 78), 'Красным — не прочитано.   ', font=F_NOTE, fill=RED)
d.text((2750, 78), 'Зелёным — восстановлено по разбору, на листе этого нет.', font=F_NOTE, fill=GREEN)
note(60, 70, ['Перерисовано с фотографии рукописной схемы (IMC/DSC_1665.jpg). Связи заданы именами цепей, как в оригинале.',
              'Обозначения микросхем (BF, RG, DC, CT, SG, T, 1) — с оригинала. Регистры — ИР23 (со слов автора); остальные типы в скобках выведены по номерам выводов.'], GREY)

# ---------------------------------------------------------------- connector
frame(40, 130, 420, 830, 'Разъём к Спектруму')
y = 190
for name, n in [('D%d' % i, 'CD%d' % i) for i in range(8)] + [
        ('/BFFD WR', '/BWR'), ('/FFFD WR', '/FWR'), ('BIT', 'BIT'), ('/WAIT', '/WAIT'), ('4M', '4M'),
        ('2M', '2M'), ('/RES', '/RES'), ('+5V', '+5V'), ('GND', 'GND')]:
    d.line((170, y, 250, y), fill=GREEN if name == '/WAIT' else BLACK, width=2)
    if name in ('BIT', '/WAIT'):                    # signals going to the Spectrum
        d.polygon([(170, y), (184, y - 7), (184, y + 7)], fill=BLACK)
    elif name not in ('+5V', 'GND'):
        d.polygon([(250, y), (236, y - 7), (236, y + 7)], fill=BLACK)
    d.text((166 - tw(name, F_PIN), y - 11), name, font=F_PIN, fill=GREEN if name == '/WAIT' else BLACK)
    net(250, y, n, colour=GREEN if name == '/WAIT' else BLUE)
    y += 38
note(56, 845, ['BIT: «к любому порту ввода', 'или к входу /BFFD RD»', '(выход, флаг для Спектрума)'], GREY)
note(56, 915, ['/WAIT: на листе нет; см. «Запрос обмена».'], GREEN)

# ---------------------------------------------------------------- buffer and latches
frame(480, 130, 610, 1150, 'Буфер и входные защёлки')
chip(670, 180, 230, 'BF', '(по выводам — АП6)',
     [(18 - i, 'B%d' % i, 'CD%d' % i) for i in range(8)] + [(1, 'T', 'GND'), (19, '/CS', 'GND')],
     [(2 + i, 'A%d' % i, 'BD%d' % i) for i in range(8)])
chip(670, 560, 230, 'RG  DATA', '(ИР23, порт #BFFD)',
     [(LATCH_IN[i], 'D%d' % i, 'BD%d' % i) for i in range(8)] + [(11, 'C', '/BWR'), (1, '/OE', '/RDDAT')],
     [(LATCH_OUT[i], 'Q%d' % i, BUS[i]) for i in range(8)])
chip(670, 920, 230, 'RG  ADDR', '(ИР23, порт #FFFD)',
     [(LATCH_IN[i], 'D%d' % i, 'BD%d' % i) for i in range(8)] + [(11, 'C', '/FWR'), (1, '/OE', '/RDREG')],
     [(LATCH_OUT[i], 'Q%d' % i, BUS[i]) for i in range(8)])

# ---------------------------------------------------------------- output registers
frame(480, 1300, 610, 790, 'Выходные регистры')
chip(670, 1350, 230, 'RG  Sound enable', '(ИР23, порт 4, запись)',
     [(LATCH_IN[i], 'D%d' % i, BUS[i]) for i in range(8)] + [(11, 'C', '/WRN'), (1, '/OE', 'GND')],
     [(2, 'Q0', 'SV0'), (5, 'Q1', 'SV1'), (6, 'Q2', 'SV2'), (9, 'Q3', 'NO0'), (12, 'Q4', 'NO1'),
      (15, 'Q5', 'NO2'), (16, 'Q6', ''), (19, 'Q7', 'BIT')])
chip(670, 1710, 230, 'RG  Volume', '(ИР23, порт 8, запись)',
     [(LATCH_IN[i], 'D%d' % i, BUS[i]) for i in range(8)] + [(11, 'C', '/WRVOL'), (1, '/OE', 'GND')],
     [(LATCH_OUT[i], 'Q%d' % i, 'V%d' % i) for i in range(6)] + [(16, 'Q6', ''), (19, 'Q7', 'зачёркнуто', RED)])

# ---------------------------------------------------------------- decoders
frame(1110, 130, 640, 760, 'Дешифраторы')
chip(1290, 180, 230, 'DC', '(память; по выводам — ИД4)',
     [(15, '/2C', 'A15'), (14, '/2G', '/MREQ'), (13, 'A', 'A13'), (3, 'B', 'A14'), None,
      (2, '/1G', '/MREQ'), (1, '1C', 'A15')],
     [(9, '/2Y0', '/CSROM'), (10, '/2Y1', '/CSRAM'), (11, '/2Y2', '(CSRAM2?)', RED), (12, '/2Y3', ''), None,
      (7, '/1Y0', ''), (6, '/1Y1', ''), (5, '/1Y2', ''), (4, '/1Y3', '')])
chip(1290, 530, 230, 'DC', '(порты; по выводам — ИД4)',
     [(15, '/2C', '/RD'), (14, '/2G', '/IORQ'), (13, 'A', 'A2'), (3, 'B', 'A3'), None,
      (2, '/1G', '/IORQ'), (1, '1C', 'WR')],
     [(9, '/2Y0', '/RD53'), (10, '/2Y1', '/RDREG'), (11, '/2Y2', '/RDDAT'), (12, '/2Y3', '/TEST'), None,
      (7, '/1Y0', '/WR53'), (6, '/1Y1', '/WRN'), (5, '/1Y2', '/WRVOL'), (4, '/1Y3', '/CONTR')])

# ---------------------------------------------------------------- clocks and inverters
frame(1110, 910, 640, 560, 'Тактирование и инверторы')
chip(1290, 960, 190, '1', '(шесть инверторов)',
     [(1, '', '4M'), (3, '', '4M*'), (5, '', '2M'), (9, '', '0M125'), (11, '', '/TEST'), (13, '', '/WR')],
     [(2, '/', '4M*'), (4, '/', 'CLC'), (6, '/', 'B2M'), (8, '/', 'SCLC'), (10, '/', 'TESTH'), (12, '/', 'WR')])
note(1125, 1206, ['CLC подтянут к +5V через 360 Ом.', '4M* — промежуточная цепь, имени на оригинале нет.',
                  'TESTH — то же: управление ключом состояния.'], GREY)
chip(1290, 1290, 190, 'CT', '(по выводам — ИЕ10)',
     [(2, 'CP', 'B2M'), (1, 'CN', 'GND'), (7, 'R', 'GND')],
     [(3, 'Q0', '1M'), (4, 'Q1', '0M5'), (5, 'Q2', '0M25'), (6, 'Q3', '0M125')])

# ---------------------------------------------------------------- request logic
frame(1110, 1490, 640, 640, 'Запрос обмена')
chip(1300, 1540, 170, 'T', '(D-триггер, 1/2)',
     [(4, '/S', 'TRS'), (3, 'C', '/BWR'), (2, 'D', 'GND'), (1, '/R', '/RES')],
     [(5, 'Q', 'NMI, /WAIT', GREEN), (6, '/Q', 'NMIT')])
chip(1300, 1740, 170, 'T', '(D-триггер, 2/2)',
     [(10, '/S', 'ONE'), (11, 'C', '/CONTR'), (12, 'D', 'D7'), (13, '/R', '/RES')],
     [(8, 'Q', ''), (9, '/Q', 'TRS')])
note(1125, 1925, ['На листе подпись у вывода 5 зачёркнута, а NMI процессора',
                  'ни к чему явно не подведён. TRS подписан у инверсного',
                  'выхода, номер вывода — 9.'])
note(1125, 1995, ['Восстановлено: вывод 5 падает по окончании записи в',
                  '#BFFD и держится до сброса запроса (бит 7 в порт 12).',
                  'Это и есть NMI (срабатывает по спаду) и WAIT основного',
                  'процессора. С NMIT (вывод 6) NMI приходил бы в момент',
                  'сброса, а не записи.'], GREEN)

# ---------------------------------------------------------------- CPU
frame(1770, 130, 620, 960, 'Процессор')
data_pins = (14, 15, 12, 8, 7, 9, 10, 13)
addr_pins = (30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 1, 2, 3, 4, 5)
chip(1960, 180, 240, 'CPU', '(Z80)',
     [(data_pins[i], 'D%d' % i, BUS[i]) for i in range(8)] + [None,
      (6, 'CLK', 'CLC'), (26, '/RESET', '/RES'), (16, '/INT', 'ONE'), (17, '/NMI', 'NMI', GREEN),
      (24, '/WAIT', 'ONE'), (25, '/BUSRQ', 'ONE'), None, (11, '+5V', '+5V'), (29, 'GND', 'GND')],
     [(addr_pins[i], 'A%d' % i, 'A%d' % i) for i in range(16)] + [None,
      (19, '/MREQ', '/MREQ'), (20, '/IORQ', '/IORQ'), (21, '/RD', '/RD'), (22, '/WR', '/WR'), None,
      (27, '/M1', ''), (23, '/BUSAK', ''), (28, '/RFSH', ''), (18, '/HALT', '')])
note(1785, 1050, ['ONE — +5V через 2 кОм.'], GREY)

# ---------------------------------------------------------------- memory
frame(2410, 130, 1050, 560, 'Память')
mem_a = (8, 7, 6, 5, 4, 3, 2, 1, 23, 22, 19)
mem_d = (9, 10, 11, 13, 14, 15, 16, 17)
chip(2560, 180, 200, 'ROM', '(2 КБ, #0000–#07FF)',
     [(mem_a[i], 'A%d' % i, 'A%d' % i) for i in range(11)] + [None,
      (18, '/CS', '/CSROM'), (20, '/OE', '/RD'), (21, 'Vpp', '+5V')],
     [(mem_d[i], 'D%d' % i, BUS[i]) for i in range(8)])
chip(3060, 180, 200, 'RAM', '(2 КБ, #2000–#27FF)',
     [(mem_a[i], 'A%d' % i, 'A%d' % i) for i in range(11)] + [None,
      (18, '/CS', '/CSRAM'), (20, '/OE', '/RD'), (21, '/WE', '/WR')],
     [(mem_d[i], 'D%d' % i, BUS[i]) for i in range(8)])

# ---------------------------------------------------------------- timer
frame(2410, 710, 1050, 560, 'Таймер')
chip(2560, 760, 220, 'SG', '(КР580ВИ53)',
     [(8 - i, 'D%d' % i, BUS[i]) for i in range(8)] + [None,
      (19, 'A0', 'A0'), (20, 'A1', 'A1'), (22, '/RD', '/RD53'), (23, '/WR', '/WR53'), (21, '/CS', 'GND')],
     [(9, 'CLK0', 'SCLC'), (11, 'GATE0', 'SV0'), (10, 'OUT0', 'SO0'), None,
      (15, 'CLK1', 'SCLC'), (14, 'GATE1', 'SV1'), (13, 'OUT1', 'SO1'), None,
      (18, 'CLK2', 'SCLC'), (16, 'GATE2', 'SV2'), (17, 'OUT2', 'SO2')])
note(2990, 780, ['SCLC = 2 МГц / 16 = 125 кГц', '(инвертированные).', '',
                 'Порты сопроцессора (A3, A2):', ' 0–3   таймер', ' 4     чтение: номер регистра',
                 '        запись: Sound enable', ' 8     чтение: данные',
                 '        запись: Volume', ' 12    чтение: запрос (бит 7)',
                 '        запись: сброс запроса'], GREY)

# ---------------------------------------------------------------- mixing
frame(1770, 1110, 620, 370, 'Смешивание тона и шума (6×10K)')
for i in range(3):
    yy = 1200 + i * 95
    net(1830, yy, 'SO%d' % i, right=True)
    e = res(1830, yy, '10K')
    d.line((e, yy, e + 60, yy), fill=BLACK, width=2)
    dot(e + 30, yy)
    e2 = res(e + 60, yy, '10K')
    net(e2, yy, 'NO%d' % i)
    d.line((e + 30, yy, e + 30, yy + 36), fill=BLACK, width=2)
    net(e + 30, yy + 44, 'MIX%d' % i)

# ---------------------------------------------------------------- switches
frame(1770, 1500, 620, 860, 'Аналоговые ключи')
chip(1960, 1550, 200, 'KT', '(К561КТ3, первая)',
     [(1, 'X', 'MIX0'), (13, 'V', 'V0 (10K)'), (11, 'X', 'MIX0'), (12, 'V', 'V1 (10K)'),
      (4, 'X', 'MIX1'), (5, 'V', 'V2 (10K)'), (8, 'X', 'MIX1'), (6, 'V', 'V3 (10K)')],
     [(2, 'Y', 'K0A'), None, (10, 'Y', 'K0B'), None, (3, 'Y', 'K1A'), None, (9, 'Y', 'K1B')])
chip(1960, 1880, 200, 'KT', '(К561КТ3, вторая)',
     [(1, 'X', 'MIX2'), (13, 'V', 'V4 (10K)'), (11, 'X', 'MIX2'), (12, 'V', 'V5 (10K)'),
      (8, 'X', 'NMIT (1K)'), (6, 'V', 'TESTH (2K5?)'), (4, 'X', ''), (5, 'V', '')],
     [(2, 'Y', 'K2A'), None, (10, 'Y', 'K2B'), None, (9, 'Y', 'D7'), None, (3, 'Y', '')])
note(1785, 2210, ['Управляющие входы ключей громкости — через 10 кОм.',
                  'Седьмой ключ выдаёт NMIT на D7 при чтении порта 12.',
                  'Восьмой ключ не используется.',
                  'K0A…K2B — выходы ключей, имён на оригинале нет.',
                  'Номинал резистора в цепи TESTH читается как «?K5».'], GREY)

# ---------------------------------------------------------------- volume network and output
frame(2410, 1290, 1050, 1070, 'Громкость и выход')
for i in range(3):
    yy = 1360 + i * 150
    d.rectangle((2560, yy, 2790, yy + 118), outline=BLACK, width=3)
    for k, r in enumerate(('2K2', '4K3', '1K2')):
        d.rectangle((2620, yy + 12 + k * 34, 2730, yy + 38 + k * 34), outline=BLACK, width=2)
        d.text((2675 - tw(r, F_PIN) / 2, yy + 14 + k * 34), r, font=F_PIN, fill=BLACK)
    for k, n in enumerate(('K%dA' % i, 'K%dB' % i, 'MIX%d' % i)):
        d.line((2514, yy + 25 + k * 34, 2560, yy + 25 + k * 34), fill=BLACK, width=2)
        net(2514, yy + 25 + k * 34, n, right=True)
    d.line((2790, yy + 59, 2836, yy + 59), fill=BLACK, width=2)
    net(2836, yy + 59, 'VOL%d' % i)
note(2940, 1370, ['В каждом канале три резистора:', '2,2 кОм, 4,3 кОм и 1,2 кОм.',
                  'Как они соединены между ключами,', 'MIXn и VOLn — по фотографии', 'не читается.'])

y0 = 1900
for i, (src, dst) in enumerate((('VOL0', 'LEFT'), ('VOL1', 'LEFT'), ('VOL1', 'RIGHT'), ('VOL2', 'RIGHT'))):
    yy = y0 + i * 70
    net(2560, yy, src, right=True)
    e = res(2560, yy, '10K', 110)
    d.line((e, yy, e + 70, yy), fill=BLACK, width=2)
d.line((2740, y0, 2740, y0 + 70), fill=BLACK, width=2)
d.line((2740, y0 + 140, 2740, y0 + 210), fill=BLACK, width=2)
for yy, name in ((y0 + 35, 'LEFT'), (y0 + 175, 'RIGHT')):
    dot(2740, yy)
    d.line((2740, yy, 2900, yy), fill=BLACK, width=2)
    d.polygon([(2900, yy), (2886, yy - 7), (2886, yy + 7)], fill=BLACK)
    d.text((2912, yy - 11), name, font=F_PIN, fill=BLACK)
    # capacitor to ground
    dot(2820, yy)
    d.line((2820, yy, 2820, yy + 14), fill=BLACK, width=2)
    d.line((2804, yy + 14, 2836, yy + 14), fill=BLACK, width=3)
    d.line((2804, yy + 22, 2836, yy + 22), fill=BLACK, width=3)
    # second plate to ground
    d.line((2820, yy + 22, 2820, yy + 38), fill=BLACK, width=2)
    for k, half in enumerate((14, 9, 4)):
        d.line((2820 - half, yy + 38 + k * 6, 2820 + half, yy + 38 + k * 6), fill=BLACK, width=2)
note(3010, 1900, ['Выход «к усилителю»:', 'LEFT, RIGHT, +5V, GND.', 'A — в левый канал,', 'C — в правый,',
                  'B — в оба.'], GREY)
note(2430, 2200, ['Конденсаторы на выходах — на землю (по словам автора), без номиналов:',
                  'ФНЧ с резисторами смесителя. Разделительных конденсаторов на плате нет.'], GREY)
note(2430, 2270, ['На полях оригинала есть карандашный набросок ещё одного блока из шести',
                  'ключей с резисторами, без подписей — он не перерисован.'])

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                           'schematic_redrawn.png')
img.save(out, optimize=True)
print(out, img.size)
