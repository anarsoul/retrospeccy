; Эмулятор "Радио-86РК" (32К) для ZX Spectrum +2A/+2B/+3.
;
; Пересборка программы "Radio-interface" с кассеты green_svema (сторона 1,
; запись 27: Monitor co, Radio Font, INT CODE, TABLE MON., RadioBlok).
; Это не эмулятор процессора: код РК (8080) исполняется на Z80 как есть,
; подменено окружение - память, Монитор по адресам #F800..., экран и лента.
;
; Сборка:  sjasmplus rk86.asm  ->  rk86.tap
; На ленте загрузчик на BASIC и блок кода. Программы для РК - на отдельных
; лентах, их грузит директива I: piton.tap (см. piton.asm), basic.tap
; (см. rkr2tap.py).
;
; Что перенесено как было: набор директив Монитора (G F I M O S L), таблица
; переходов #F800, формат ленты (спектрумовский, заголовок "RADIO FILE"),
; процедуры ленты - копии SA-BYTES/LD-BYTES из ПЗУ, шрифт, экран 64x24 из
; видеопамяти РК с шагом 78, клавиши CAPS+ENTER, SYM+A, SYM+B, CAPS+SYM.
;
; Что сделано иначе - см. README, раздел про эту сборку. Коротко:
;   - теневое ОЗУ "Балтика" (порт #7E) заменено режимом "всё ОЗУ" +2A/+3
;     (порт #1FFD), и РК достались его родные 32К с видеопамятью в #76D0
;     (в оригинале было 16К и видеопамять в #36D0);
;   - IM 2 с таблицей из 257 одинаковых байт и своим стеком в обработчике;
;   - на экран рисует только прерывание: сравнивает видеопамять РК с теневой
;     копией и перерисовывает изменившиеся пары знаков. Печать Монитора
;     просто пишет в видеопамять.
;
; У +2A/+3 страницы 4-7 "медленные": пока луч рисует картинку, видеоконтроллер
; придерживает процессор на каждом обращении к ним. Поэтому всё, что
; исполняется, лежит в страницах 0-3 (раскладка "всё ОЗУ" номер 0):
;   #0000-#75FF  ОЗУ программы РК (страницы 0 и 1)
;   #76CF        вершина стека, как у РК
;   #76D0-#7FF3  видеопамять РК, 30 строк по 78; видимое окно с #77C2
;   #8100-#9C4A  код сравнения с теневой копией (страница 2, генерируется)
;   #9D00-#9E00  таблица векторов IM 2
;   #D000-#DFFF  два сдвинутых шрифта по линиям (страница 3, генерируются)
;   #E290-#F86E  эта программа
; Экрана Спектрума в этой раскладке нет: он бывает только в страницах 5 и 7.
; Прерывание на время записи в экран включает раскладку 4-5-6-3 - страница 3
; с кодом остаётся на месте, экран появляется в #4000 - и сразу возвращает
; прежнюю.
; Адреса портов РК ничем не заняты: #8000-#8003 и #A000-#A003 (ВВ55),
; #C000-#C001 (ВГ75), #E000-#E008 (ВТ57). Запись туда ничего не портит и
; ничего не делает.

        DEVICE ZXSPECTRUM48

VTOP    EQU #76D0               ; начало видеопамяти РК
VLEN    EQU 78*30
VIDEO   EQU #77C2               ; первый видимый знак
PITCH   EQU 78
ROWS    EQU 24
COLS    EQU 64
RKSP    EQU #76CF
SCAN    EQU #8100               ; сгенерированный код сравнения
IMTAB   EQU #9D00
IMBYTE  EQU #F7                 ; вектор #F7F7
FONTL   EQU #D000               ; 8 линий по 256 байт: знак в старшем полубайте
FONTR   EQU #D800               ; то же в младшем
SCREEN  EQU #4000               ; экран Спектрума: страница 5, когда она подключена
MAP_RUN    EQU 1                ; порт #1FFD: страницы 0-1-2-3
MAP_SCREEN EQU 5                ; страницы 4-5-6-3
BORDER  EQU 1
ATTR    EQU #0F                 ; белый по синему, как в загрузчике с ленты
LINELEN EQU 32

LOADER  EQU #6000
ENTRY   EQU #E290               ; 58000, как в оригинале

; ---------------------------------------------------------------------------
; Загрузчик: работает в обычной раскладке (ПЗУ, 5, 2, страница из #7FFD).
        ORG LOADER
loader: di
        ld a,#10                ; страницы 0 и 1 - будущая память РК: чистим
        call .clear
        ld a,#11
        call .clear
        ld a,#13                ; страница 3: эмулятор
        ld bc,#7FFD
        out (c),a
        ld hl,image
        ld de,ENTRY
        ld bc,image_end - ENTRY
        ldir
        jp start
.clear: ld bc,#7FFD
        out (c),a
        ld hl,#C000
        ld de,#C001
        ld bc,#3FFF
        ld (hl),l
        ldir
        ret

image:
        DISP ENTRY

; ---------------------------------------------------------------------------
; Холодный старт (#F800). Память программы РК не трогается: CAPS+ENTER
; возвращает сюда из любой программы.
start:  di
        ld bc,#7FFD
        ld a,#13                ; показывать обычный экран (страницу 5)
        out (c),a
        ld bc,#1FFD
        ld a,MAP_SCREEN         ; экран в #4000; мотор выключен
        out (c),a               ; было: LD A,#FC : OUT (#7E),A
        ld sp,isr_stack

        ld hl,SCREEN            ; экран: точки и цвет
        ld de,SCREEN + 1
        ld bc,#17FF
        ld (hl),l
        ldir
        inc hl
        inc de
        ld (hl),ATTR
        ld bc,#02FF
        ldir
        ld a,BORDER
        out (#FE),a

        ld bc,#1FFD
        ld a,MAP_RUN            ; дальше - только быстрая память
        out (c),a
        ld sp,RKSP

        ld hl,IMTAB             ; 257 байт: какой бы байт ни оказался на шине,
        ld (hl),IMBYTE          ; вектор читается как #F7F7
        ld de,IMTAB + 1
        ld bc,256
        ldir
        ld a,high IMTAB
        ld i,a
        im 2

        call fontinit
        call scaninit

        xor a
        ld (escst),a
        ld (scanoff),a
        ld (cur_scr + 1),a
        ld c,#1F                ; очистка видеопамяти; заодно включит прерывания
        call putc
        ld hl,t_banner
        call puts

; Тёплый старт (#F86C): приглашение и директива.
warm:   ld sp,RKSP
        ei
        ld hl,t_prompt
        call puts
        call getline
        ld hl,warm
        push hl
        ld de,linebuf
        ld a,(de)
        inc de
        cp #0D
        ret z
        push af
        call params
        pop af
        ld hl,(p3)
        ld b,h
        ld c,l
        ld de,(p2)
        ld hl,(p1)
        cp 'G'
        jr z,cmd_g
        cp 'F'
        jr z,cmd_f
        cp 'I'
        jr z,cmd_i
        cp 'M'
        jr z,cmd_m
        cp 'O'
        jr z,cmd_o
        cp 'S'
        jr z,report
        cp 'L'
        jp z,cmd_l
error:  ld c,'?'
        call putc
        jp warm

; G<адрес> - запуск. RET из программы возвращает в Монитор.
cmd_g:  jp (hl)

; F<начало>,<конец>,<байт> - заполнение, конец включительно.
cmd_f:  ld (hl),c
        call nexthl
        jr cmd_f

; I[<смещение>] - загрузка с ленты; печатает начало, конец и контрольную сумму.
cmd_i:  call tload
; S<начало>,<конец> - контрольная сумма. На выходе BC = сумма.
report: call crlf
        call hex16
        ex de,hl
        call space
        call hex16
        ex de,hl
        call space
        call chksum
        push hl
        ld h,b
        ld l,c
        call hex16
        pop hl
        ret

; O<начало>,<конец> - запись на ленту. Сумма кладётся во второй параметр
; заголовка.
cmd_o:  call report
        jp tsave

; M<адрес> - просмотр и изменение: байт и <ВК> - записать, <ВК> - дальше,
; точка - выход.
cmd_m:  call crlf
        call hex16
        call space
        ld a,(hl)
        call hexout
        call space
        push hl
        call getline
        ld de,linebuf
        ld a,(de)
        cp #0D
        jr z,.skip
        call gethex
        ld a,l
        pop hl
        ld (hl),a
        push hl
.skip:  pop hl
        inc hl
        jr cmd_m

; L<a>,<b>,<c>,<x>,<y>,<z> - заменить во всей памяти программы (#0000-#75FF)
; каждую тройку байт a b c на x y z.
cmd_l:  ld de,linebuf + 1
        ld hl,lbuf
        ld b,6
.par:   push hl
        call gethex
        ld a,l
        pop hl
        ld (hl),a
        inc hl
        djnz .par
        ld ix,0
.next:  ld a,(lbuf)
        cp (ix+0)
        jr nz,.no
        ld a,(lbuf + 1)
        cp (ix+1)
        jr nz,.no
        ld a,(lbuf + 2)
        cp (ix+2)
        jr nz,.no
        ld a,(lbuf + 3)
        ld (ix+0),a
        ld a,(lbuf + 4)
        ld (ix+1),a
        ld a,(lbuf + 5)
        ld (ix+2),a
.no:    inc ix
        ld a,ixh
        cp high (VTOP - #D0)
        jr nz,.next
        ret

; Если HL = DE - выход из вызвавшей процедуры, иначе HL + 1.
nexthl: ld a,h
        cp d
        jr nz,.inc
        ld a,l
        cp e
        jr nz,.inc
        pop af
        ret
.inc:   inc hl
        ret

; До трёх чисел через запятую из строки по адресу DE в p1, p2, p3.
params: ld hl,0
        ld (p2),hl
        ld (p3),hl
        call gethex
        ld (p1),hl
        ret c
        call gethex
        ld (p2),hl
        ret c
        call gethex
        ld (p3),hl
        ret

; Шестнадцатеричное число из строки по адресу DE в HL. Пробелы пропускаются,
; запятая заканчивает число, CF = 1 - строка кончилась.
gethex: ld hl,0
.next:  ld a,(de)
        cp #0D
        scf
        ret z
        inc de
        cp ','
        ret z
        cp ' '
        jr z,.next
        sub '0'
        jp c,error
        cp 10
        jr c,.digit
        sub 7
        cp 10
        jp c,error
        cp 16
        jp nc,error
.digit: add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        or l
        ld l,a
        jr .next

; Ввод строки в linebuf, в конце #0D. Забой - CAPS+0 или CAPS+5, точка -
; отказ от директивы.
getline:
        ld hl,linebuf
        ld b,0
.key:   call getkey
        cp #08
        jr z,.back
        cp #7F
        jr z,.back
        cp #0D
        jr z,.done
        cp '.'
        jp z,warm
        cp ' '
        jr c,.key
        ld c,a
        ld a,b
        cp LINELEN - 1
        jr z,.key
        ld (hl),c
        inc hl
        inc b
        call putc
        jr .key
.back:  ld a,b
        or a
        jr z,.key
        dec hl
        dec b
        ld c,8
        call putc
        ld c,' '
        call putc
        ld c,8
        call putc
        jr .key
.done:  ld (hl),a
        ret

crlf:   push bc
        ld c,#0D
        call putc
        ld c,#0A
        jr space.out
space:  push bc
        ld c,' '
.out:   call putc
        pop bc
        ret

hex16:  ld a,h
        call hexout
        ld a,l
; #F815: A двумя шестнадцатеричными цифрами.
hexout: push af
        rrca
        rrca
        rrca
        rrca
        call .nib
        pop af
.nib:   push af
        push bc
        and #0F
        add a,#90
        daa
        adc a,#40
        daa
        ld c,a
        call putc
        pop bc
        pop af
        ret

; #F818: строка по адресу HL до нулевого байта.
puts:   ld a,(hl)
        or a
        ret z
        push bc
        ld c,a
        call putc
        pop bc
        inc hl
        jr puts

; #F82A: контрольная сумма блока HL...DE в BC, как считает её Монитор РК:
; младший байт - сумма всех байт, старший - сумма с переносами из младшего
; всех байт, кроме последнего.
chksum: push af
        push hl
        ld bc,0
.next:  ld a,(hl)
        add a,c
        ld c,a
        push af
        ld a,h
        cp d
        jr nz,.more
        ld a,l
        cp e
        jr z,.done
.more:  pop af
        ld a,b
        adc a,(hl)
        ld b,a
        inc hl
        jr .next
.done:  pop af
        pop hl
        pop af
        ret

; #F81E: положение курсора в координатах РК (H = строка + 3, L = столбец + 8).
getcur: push af
        ld hl,(curpos)
        ld a,h
        add a,3
        ld h,a
        ld a,l
        add a,8
        ld l,a
        pop af
        ret

; #F821: знак под курсором.
getchr: push hl
        ld hl,(curaddr)
        ld a,(hl)
        pop hl
        ret

; #F830 / #F833: верхняя граница свободной памяти.
gettop: ld hl,(ramtop)
        ret
settop: ld (ramtop),hl
        ret

        INCLUDE "console.inc"

; ---------------------------------------------------------------------------
; Лента. Формат спектрумовский: заголовок типа 3 с именем "RADIO FILE" и блок
; данных. В режиме "всё ОЗУ" ПЗУ нет, поэтому SA-BYTES и LD-BYTES - копии из
; ПЗУ 48K, как и в оригинале.
;
; #F824: загрузка. Вход: HL = смещение. Выход: HL = начало, DE = конец,
; BC = второй параметр заголовка (сумма, с которой файл записан).
; SPACE прерывает загрузку.
tload:  push hl
.head:  ld ix,hdr
        ld de,17
        xor a
        scf
        call ldbytes
        jr c,.got
.brk:   ld a,#7F
        in a,(#FE)
        rra
        jr c,.head
        jp error
.got:   ld a,(hdr)
        cp 3
        jr nz,.head
        call crlf
        ld hl,hdr + 1
        ld b,10
.name:  ld c,(hl)
        call putc
        inc hl
        djnz .name
        halt                    ; дать прерыванию нарисовать имя
        halt
        pop hl
        ld bc,(hdr + 13)
        add hl,bc               ; в оригинале ADC с неизвестным переносом
        push hl
        push hl
        pop ix
        ld de,(hdr + 11)
        ld a,#FF
        scf
        call ldbytes
        jp nc,error
        pop hl
        push hl
        ld de,(hdr + 11)
        dec de
        add hl,de
        ex de,hl
        pop hl
        ld bc,(hdr + 15)
        ret

; #F827: запись. Вход: HL = начало, DE = конец, BC = контрольная сумма.
tsave:  push af
        push bc
        push de
        push hl
        ld (hdr + 15),bc
        ld (hdr + 13),hl
        ex de,hl
        or a
        sbc hl,de
        inc hl
        ld (hdr + 11),hl
        ld ix,hdr
        ld de,17
        xor a
        call sabytes
        ld b,50                 ; секунда между заголовком и данными
.pause: halt
        djnz .pause
        ld ix,(hdr + 13)
        ld de,(hdr + 11)
        ld a,#FF
        call sabytes
        pop hl
        pop de
        pop bc
        pop af
        ret

hdr:    DB 3,"RADIO FILE"
        DW 0,0,0

; SA-BYTES (#04C2 в ПЗУ): A = флаг, IX = адрес, DE = длина.
sabytes:
        ld hl,saldret
        push hl
        ld hl,#1F80
        bit 7,a
        jr z,.flag
        ld hl,#0C98
.flag:  ex af,af'
        inc de
        dec ix
        di
        ld a,2
        ld b,a
.leader:
        djnz .leader
        out (#FE),a
        xor #0F
        ld b,#A4
        dec l
        jr nz,.leader
        dec b
        dec h
        jp p,.leader
        ld b,#2F
.sync1: djnz .sync1
        out (#FE),a
        ld a,#0D
        ld b,#37
.sync2: djnz .sync2
        out (#FE),a
        ld bc,#3B0E
        ex af,af'
        ld l,a
        jp .start
.loop:  ld a,d
        or e
        jr z,.parity
        ld l,(ix+0)
.loop1: ld a,h
        xor l
.start: ld h,a
        ld a,1
        scf
        jp .bits
.parity:
        ld l,h
        jr .loop1
.bit2:  ld a,c
        bit 7,b
.bit1:  djnz .bit1
        jr nc,.out
        ld b,#42
.set:   djnz .set
.out:   out (#FE),a
        ld b,#3E
        jr nz,.bit2
        dec b
        xor a
        inc a
.bits:  rl l
        jp nz,.bit1
        dec de
        inc ix
        ld b,#31
        ld a,#7F
        in a,(#FE)
        rra
        ret nc
        ld a,d
        inc a
        jp nz,.loop
        ld b,#3B
.delay: djnz .delay
        ret

; SA/LD-RET: бордюр на место, прерывания включить.
saldret:
        push af
        ld a,BORDER
        out (#FE),a
        pop af
        ei
        ret

; LD-BYTES (#0556 в ПЗУ): A = флаг, CF = 1, IX = адрес, DE = длина.
; На выходе CF = 1, если блок прочитан.
ldbytes:
        inc d
        ex af,af'
        dec d
        di
        ld a,#0F
        out (#FE),a
        ld hl,saldret
        push hl
        in a,(#FE)
        rra
        and #20
        or 2
        ld c,a
        cp a
.break: ret nz
.start: call ldedge1
        jr nc,.break
        ld hl,#0415
.wait:  djnz .wait
        dec hl
        ld a,h
        or l
        jr nz,.wait
        call ldedge2
        jr nc,.break
.leader:
        ld b,#9C
        call ldedge2
        jr nc,.break
        ld a,#C6
        cp b
        jr nc,.start
        inc h
        jr nz,.leader
.sync:  ld b,#C9
        call ldedge1
        jr nc,.break
        ld a,b
        cp #D4
        jr nc,.sync
        call ldedge1
        ret nc
        ld a,c
        xor 3
        ld c,a
        ld h,0
        ld b,#B0
        jr .marker
.loop:  ex af,af'
        jr nz,.flag
        jr nc,.verify
        ld (ix+0),l
        jr .next
.flag:  rl c
        xor l
        ret nz
        ld a,c
        rra
        ld c,a
        inc de
        jr .dec
.verify:
        ld a,(ix+0)
        xor l
        ret nz
.next:  inc ix
.dec:   dec de
        ex af,af'
        ld b,#B2
.marker:
        ld l,1
.bits:  call ldedge2
        ret nc
        ld a,#CB
        cp b
        rl l
        ld b,#B0
        jp nc,.bits
        ld a,h
        xor l
        ld h,a
        ld a,d
        or e
        jr nz,.loop
        ld a,h
        cp 1
        ret

ldedge2:
        call ldedge1
        ret nc
ldedge1:
        ld a,#16
.delay: dec a
        jr nz,.delay
        and a
.sample:
        inc b
        ret z
        ld a,#7F
        in a,(#FE)
        rra
        ret nc
        xor c
        and #20
        jr z,.sample
        ld a,c
        cpl
        ld c,a
        and 7
        or 8
        out (#FE),a
        scf
        ret

        INCLUDE "render.inc"

; ---------------------------------------------------------------------------
t_banner:
        DB #0D,#0A,"|mulqtor radio-86rk. WRITTEN BY VASILY KHORUZHICK",#0D,#0A,0
t_prompt:
        DB #0D,#0A,"->",0

curaddr: DW VIDEO               ; адрес курсора в видеопамяти
curpos: DW 0                    ; столбец, строка
escst:  DB 0                    ; разбор ESC Y: 1 - был ESC, 2 - ждём строку, 3 - столбец
rus:    DB 0                    ; 0 - ЛАТ, #20 - РУС
extdown: DB 0
lastkey: DB #FF
repcnt: DB 25
kready: DB 0                    ; есть непрочитанное нажатие
kcode:  DB 0
ramtop: DW VTOP - #D1           ; #75FF, как у РК
scanoff: DB 0
frames: DB 0
cur_scr: DW 0                   ; байт экрана с курсором; старший байт 0 - курсора нет
cur_vid: DW 0                   ; и адрес этой пары в видеопамяти
isr_usp: DW 0
isr_sp: DW 0
p1:     DW 0
p2:     DW 0
p3:     DW 0
lbuf:   DS 6
linebuf: DS LINELEN
        DS 48
isr_stack:

; Шрифт с кассеты, кроме последнего знака. Код #7F у РК - закрашенное
; знакоместо (им "Питон" рисует еду, а RAMDOS - рамку); в шрифте с кассеты на
; его месте фигура вроде уголка.
font:   INCBIN "../green_svema/side_1/svema_27/12_Radio_Font.bin", 0, #7F * 8
        DS 8, #F0
        ASSERT $ - font == #400

        ASSERT $ <= IMBYTE * 257
        BLOCK IMBYTE * 257 - $, 0
        jp isr                  ; #F7F7
        BLOCK #F800 - $, 0

; Таблица переходов Монитора РК.
        jp start                ; #F800 холодный старт
        jp getkey               ; #F803 ввод знака с клавиатуры
        ret                     ; #F806 байт с ленты: формат ленты не тот
        nop
        nop
        jp putc                 ; #F809 вывод знака C
        ret                     ; #F80C байт на ленту
        nop
        nop
        jp putc                 ; #F80F вывод знака C
        jp kpressed             ; #F812 нажата ли клавиша
        jp hexout               ; #F815 A в шестнадцатеричном виде
        jp puts                 ; #F818 строка HL
        jp kstat                ; #F81B код клавиши без ожидания
        jp getcur               ; #F81E положение курсора
        jp getchr               ; #F821 знак под курсором
        jp tload                ; #F824 загрузка с ленты
        jp tsave                ; #F827 запись на ленту
        jp chksum               ; #F82A контрольная сумма
        ret                     ; #F82D запуск изображения
        nop
        nop
        jp gettop               ; #F830 граница памяти
        jp settop               ; #F833
        ASSERT $ == #F836
        jp start                ; #F836: в Мониторе РК здесь начинается холодный
                                ; старт, и программы выходят сюда напрямую
        BLOCK #F86C - $, 0
        jp warm                 ; #F86C тёплый старт, как у Монитора РК
image_end:
        ENT

code_end:

; --- загрузчик на BASIC ----------------------------------------------------
        ORG #5D00
basic:  DB 0,10
        DW .end - .body
.body:  DB #FD,#B0,'"24575":'           ; CLEAR VAL "24575":
        DB #EF,'""',#AF,':'             ; LOAD ""CODE:
        DB #F9,#C0,#B0,'"24576"',#0D    ; RANDOMIZE USR VAL "24576"
.end:

        EMPTYTAP "rk86.tap"
        SAVETAP "rk86.tap",BASIC,"RK86",basic,basic.end - basic,10
        SAVETAP "rk86.tap",CODE,"rk86",LOADER,code_end - LOADER
