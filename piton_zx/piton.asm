; "Питон" - игра для "Радио-86РК" с кассеты green_svema (сторона 1, запись 26,
; `RADIO FILE`, 399 байт с адреса #1100), перенесённая на ZX Spectrum 48K.
;
; Сборка:  sjasmplus piton.asm   ->  piton.tap  (LOAD "")
;
; Что сохранено от оригинала:
;   - экран 64 знака в строке шрифтом РК шириной 4 точки (шрифт взят с той же
;     кассеты, запись 34, без изменений);
;   - игра сама себе видеопамять: знак в ячейке и есть состояние поля
;     (0 - пусто, #7F - еда, всё остальное - препятствие);
;   - очередь адресов для хвоста, рост на 7 звеньев за еду, счётчик длины
;     прямо в строке экрана, генератор случайных чисел, тексты в КОИ-7;
;   - разворот на 180 градусов - это смерть, как и было.
; Что изменено:
;   - строк 24, а не 25: поле на одну строку ниже;
;   - вызовы Монитора РК (#F803...#F821) заменены своими процедурами, ПЗУ
;     Спектрума используется только как обработчик прерывания IM 1 (для HALT);
;   - задержка считается в кадрах: 11 - скорость (в оригинале пустой цикл
;     #40FF - #600*скорость оборотов по 24 такта на 1,78 МГц - те же 0,22...0,04 с);
;   - клавиши опрашиваются каждый кадр, а не один раз за ход;
;   - скорость можно менять цифрой перед каждой партией, на экране
;     "НАЖМИТЕ <ВК>" (в оригинале она спрашивалась один раз при запуске);
;   - за каждую съеденную еду весь экран меняет цвет (в оригинале цвета нет);
;   - очередь хвоста 2048 звеньев вместо 384 (в оригинале она переполнялась),
;     стек не утекает при каждой новой игре.
;
; Управление: 5 6 7 8 (курсор) или Q A O P, <ВК> - ENTER.

        DEVICE ZXSPECTRUM48

FONT    EQU #8000               ; 128 знаков по 8 байт; адрес кратен #800
BUF     EQU #C000               ; "видеопамять" 64x24; адрес кратен #800
BUFLEN  EQU 64*24
QUEUE   EQU #C800               ; кольцевая очередь адресов звеньев
QLEN    EQU #1000
INK     EQU #44                 ; ярко-зелёный по чёрному - цвет в начале партии

EMPTY   EQU 0
WALL    EQU '+'
BODY    EQU 'O'
FOOD    EQU #7F

        ORG FONT
        INCBIN "../green_svema/side_1/svema_34/04_RadioFont_.bin"
        ASSERT $ == FONT + #400

; ---------------------------------------------------------------------------
start:
        ld (restart+1),sp

; Шрифт на ленте хранит знак в старшем полубайте. Копируем его и в младший:
; тогда при печати ничего не надо сдвигать, достаточно маски. Повторный
; запуск ничего не портит.
        ld hl,FONT
.dup:   ld a,(hl)
        rrca
        rrca
        rrca
        rrca
        or (hl)
        ld (hl),a
        inc hl
        ld a,h
        cp high (FONT + #400)
        jr nz,.dup
; Знак 0 - пустая ячейка (в шрифте РК там псевдографика).
        ld hl,FONT
        ld b,8
.zero:  ld (hl),0
        inc l
        djnz .zero

        xor a
        out (#FE),a
        call cls
        ld hl,t_title
        call print
        ld hl,t_speed
        call print              ; DE = ячейка после текста
.digit: call getdig
        jr nc,.digit
        call setdly
        add a,'0'
        ex de,hl
        call putc

; --- новая игра (#1127 в оригинале) ----------------------------------------
; Пока ждём ENTER, цифра меняет скорость. Цифры принимаются только после
; того, как все они отпущены: иначе клавиша направления 5...8, зажатая в
; момент смерти, сменила бы скорость.
restart:
        ld sp,0
        ld hl,t_press
        call print
        call showspd
        ld e,0                  ; 0 - цифры ещё не отпускали
.wait:  call rnd                ; пока ждём, крутим генератор
        call getdig
        jr c,.digit
        ld e,1
        jr .enter
.digit: dec e
        inc e
        jr z,.enter
        call setdly
        call showspd
.enter: ld a,#BF
        in a,(#FE)
        rra
        jr c,.wait              ; ENTER

        call cls
        ld bc,1
        ld hl,BUF
        ld e,63
        call line               ; верх
        ld hl,BUF + 23*64
        ld e,63
        call line               ; низ
        ld c,64
        ld hl,BUF + 63
        ld e,24
        call line               ; право
        ld hl,BUF
        ld e,24
        call line               ; лево
        ld hl,t_len
        call print

        ld hl,QUEUE
        ld (qhead),hl
        ld (qtail),hl
        ld hl,BUF + 22*64 + 30
        ld (head),hl
        ld hl,-64
        ld (dir),hl

; --- еда (#11CA) -----------------------------------------------------------
food:   ld a,7
        ld (grow),a
        call beep
.again: call rnd
        ld a,h
        and 7
        or high BUF
        ld h,a
        cp high (BUF + BUFLEN)
        jr nc,.again
        ld a,(hl)
        or a
        jr nz,.again
        ld a,FOOD
        call putc

; --- рост или стирание хвоста (#11ED) --------------------------------------
step:   ld hl,grow
        dec (hl)
        jp m,.erase
        ld hl,BUF + 37          ; младшая цифра длины
.inc:   ld a,(hl)
        inc a
        cp '9' + 1
        jr nz,.put
        ld a,'0'
        call putc
        dec hl
        jr .inc
.put:   call putc
        jr move
.erase: inc (hl)
        ld hl,(qtail)
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        call qwrap
        ld (qtail),hl
        ex de,hl
        xor a
        call putc

; --- ход (#1177) -----------------------------------------------------------
move:   ld a,(delay)
        ld b,a
.pause: halt
        call keys
        djnz .pause

        ld hl,(head)
        ld de,(dir)
        add hl,de
        ld (head),hl
        ld c,(hl)               ; что было в ячейке
        ld a,BODY
        call putc
        ex de,hl
        ld hl,(qhead)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        call qwrap
        ld (qhead),hl
        ld a,c
        or a
        jr z,step
        cp FOOD
        jp nz,restart
        call nextink            ; съел - весь экран другого цвета
        jp food

qwrap:  ld a,h
        cp high (QUEUE + QLEN)
        ret nz
        ld h,high QUEUE
        ret

; E знаков стены от HL с шагом BC.
line:   ld a,WALL
        call putc
        add hl,bc
        dec e
        jr nz,line
        ret

; ---------------------------------------------------------------------------
; Печать знака A в ячейку HL буфера (BUF + строка*64 + столбец): знак
; записывается в буфер и рисуется на экране. Портит только AF.
;
; Смещение ячейки, сдвинутое вправо на бит, - это уже почти адрес экрана:
; младший байт готов, два старших бита дают треть экрана, а выдвинутый бит
; говорит, левая или правая половина знакоместа. Шрифт хранит знак в обоих
; полубайтах, так что строка знака - это (шрифт XOR экран) AND маска XOR экран.
; Около 530 тактов на знак вместе с CALL и RET, из них 312 - восемь строк.
putc:   ld (hl),a
        push hl
        push de
        push bc
        ex de,hl
        ld l,a
        ld h,FONT >> 11
        add hl,hl
        add hl,hl
        add hl,hl               ; HL = FONT + знак*8
        ex de,hl                ; DE = знак в шрифте, HL = ячейка
        srl h
        rr l                    ; L = младший байт адреса экрана
        sbc a,a
        xor #F0
        ld c,a                  ; #F0 - левая половина, #0F - правая
        ld a,h
        and 3
        add a,a
        add a,a
        add a,a
        or #40
        ld h,a
        DUP 7
        ld a,(de)
        xor (hl)
        and c
        xor (hl)
        ld (hl),a
        inc e
        inc h
        EDUP
        ld a,(de)
        xor (hl)
        and c
        xor (hl)
        ld (hl),a
        pop bc
        pop de
        pop hl
        ret

; Строка по адресу HL: DW ячейка, текст, 0. На выходе DE = следующая ячейка.
print:  ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
.next:  ld a,(hl)
        inc hl
        or a
        ret z
        ex de,hl
        call putc
        inc hl
        ex de,hl
        jr .next

; Очистка экрана и буфера.
cls:    ld hl,#4000
        ld de,#4001
        ld bc,#1800
        ld (hl),l
        ldir
        ld a,INK
        call setink
        ld hl,BUF
        ld de,BUF + 1
        ld bc,BUFLEN - 1
        ld (hl),EMPTY
        ldir
        ret

; Следующий цвет знаков по кругу: 4 5 6 7 2 3 (яркие, по чёрному;
; синий слишком тёмный).
nextink:
        ld a,(ink)
        inc a
        cp #48
        jr c,setink
        ld a,#42
; Атрибут A на весь экран.
setink: ld (ink),a
        ld hl,#5800
        ld de,#5801
        ld bc,#02FF
        ld (hl),a
        ldir
        ret

; Скорость A (0..9) -> кадров на ход. A сохраняется.
setdly: ld b,a
        ld a,11
        sub b
        ld (delay),a
        ld a,b
        ret

; Текущая скорость в нижней строке. Сохраняет DE.
showspd:
        push de
        ld hl,t_spd
        call print
        ld a,(delay)
        neg
        add a,11 + '0'
        ex de,hl
        call putc
        inc hl
        ld a,' '
        call putc
        pop de
        ret

; Цифра без ожидания: CF=1 и A=0..9, если нажата, иначе CF=0. Портит BC.
getdig: ld bc,#F7FE             ; 1 2 3 4 5
        in a,(c)
        cpl
        and #1F
        jr z,.high
        ld b,0
.low:   inc b
        rrca
        jr nc,.low
        ld a,b
        scf
        ret
.high:  ld b,#EF                ; 0 9 8 7 6
        in a,(c)
        cpl
        and #1F
        ret z
        ld b,10
.bit:   rrca
        jr c,.found
        dec b
        jr .bit
.found: ld a,b
        cp 10
        jr nz,.ok
        xor a
.ok:    scf
        ret

; Опрос клавиш направления; нажатая меняет dir. Портит AF, HL.
keys:   ld a,#F7
        in a,(#FE)
        ld hl,-1
        bit 4,a                 ; 5 - влево
        jr z,.set
        ld a,#EF
        in a,(#FE)
        ld hl,64
        bit 4,a                 ; 6 - вниз
        jr z,.set
        ld hl,-64
        bit 3,a                 ; 7 - вверх
        jr z,.set
        ld hl,1
        bit 2,a                 ; 8 - вправо
        jr z,.set
        ld a,#DF
        in a,(#FE)
        bit 0,a                 ; P - вправо
        jr z,.set
        ld hl,-1
        bit 1,a                 ; O - влево
        jr z,.set
        ld a,#FB
        in a,(#FE)
        ld hl,-64
        rra                     ; Q - вверх
        jr nc,.set
        ld a,#FD
        in a,(#FE)
        rra                     ; A - вниз
        ret c
        ld hl,64
.set:   ld (dir),hl
        ret

; Генератор из оригинала (#1224): 16 сдвигов регистра с обратной связью
; от битов 14 и 13.
rnd:    ld hl,(seed)
        ld c,16
.loop:  ld a,h
        add hl,hl
        and #60
        jp pe,.skip
        inc hl
.skip:  dec c
        jr nz,.loop
        ld (seed),hl
        ret

; Звонок (код 7 у РК): около 1,7 кГц, 40 мс.
beep:   xor a
        ld b,140
.half:  xor #10
        out (#FE),a
        ld c,60
.wait:  dec c
        jr nz,.wait
        djnz .half
        ret

; Тексты в КОИ-7, как в оригинале: строчные латинские - это русские заглавные.
t_title:
        DW BUF + 1*64
        DB "*** piton ***",0            ; *** ПИТОН ***
t_speed:
        DW BUF + 2*64
        DB "skorostx (0..9)?",0         ; СКОРОСТЬ (0..9)?
t_press:
        DW BUF + 23*64 + 18
        DB " navmite <wk>",0            ; НАЖМИТЕ <ВК>
t_spd:
        DW BUF + 23*64 + 32
        DB " skorostx - ",0             ; СКОРОСТЬ - n
t_len:
        DW BUF + 26
        DB " dlina - 000 ",0            ; ДЛИНА - 000

seed:   DW 1
head:   DW 0                    ; ячейка головы
dir:    DW 0                    ; шаг: +-1 или +-64
qhead:  DW 0
qtail:  DW 0
grow:   DB 0                    ; сколько ещё расти
delay:  DB 0                    ; кадров на ход
ink:    DB INK                  ; текущий атрибут экрана
code_end:

; --- загрузчик на BASIC ----------------------------------------------------
        ASSERT start == 33792
        ORG #6000
basic:  DB 0,10
        DW .end - .body
.body:  DB #FD,#B0,'"32767":'           ; CLEAR VAL "32767":
        DB #EF,'""',#AF,':'             ; LOAD ""CODE:
        DB #F9,#C0,#B0,'"33792"',#0D    ; RANDOMIZE USR VAL "33792"
.end:

        EMPTYTAP "piton.tap"
        SAVETAP "piton.tap",BASIC,"PITON",basic,.end - basic,10
        SAVETAP "piton.tap",CODE,"piton",FONT,code_end - FONT
