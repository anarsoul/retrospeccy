; Шрифты, сравнение видеопамяти с теневой копией и кадровое прерывание.
; Общая часть двух сборок: rk86.asm (свой Монитор) и ../rk86mon_plus3/rk86mon.asm
; (Монитор РК-86).
;
; Программа работает в раскладке памяти 0-1-2-3, где экрана Спектрума нет.
; Прерывание работает в ней же и подключает экран (раскладка 4-5-6-3, экран в
; #4000) только на время записи в него: код, шрифты и стек прерывания лежат в
; странице 3, которая есть в обеих. В альтернативных регистрах на время
; прерывания: BC' = #1FFD, D' и E' - значения порта для раскладки с экраном и
; без.

; ---------------------------------------------------------------------------
; Два сдвинутых шрифта, разложенные по линиям: линия n знака c лежит в
; FONTL + n*256 + c (в старшем полубайте) и в FONTR + n*256 + c (в младшем).
; Коды #80-#FF (у РК это управляющие коды ВГ75) - пустые.
fontinit:
        ld hl,FONTL
        ld de,FONTL + 1
        ld bc,#0FFF
        ld (hl),l
        ldir
        ld ix,font
        ld e,0
.char:  ld d,high FONTL
        ld b,8
.line:  ld a,(ix+0)
        inc ix
        and #F0
        ld (de),a
        rrca
        rrca
        rrca
        rrca
        set 3,d                 ; FONTR = FONTL + #800
        ld (de),a
        res 3,d
        inc d
        djnz .line
        inc e
        jp p,.char
        ret

; Код сравнения видеопамяти с теневой копией. На каждую пару знаков:
;       POP HL                  ; пара из видеопамяти РК (SP идёт по строке)
;       LD DE,тень              ; что сейчас нарисовано
;       SBC HL,DE
;       CALL NZ,fixrows + 6*строка
; 45 тактов на пару, 34 560 на экран. Теневая копия - это операнды LD DE.
; В начале каждой строки LD SP,адрес строки; в конце JP scandone.
scaninit:
        ld hl,SCAN
        ld de,VIDEO
        ld bc,fixrows
        ld a,ROWS
.row:   ex af,af'
        ld (hl),#31             ; LD SP,nn
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,COLS / 2
.pair:  ld (hl),#E1             ; POP HL
        inc hl
        ld (hl),#11             ; LD DE,0: экран пуст
        inc hl
        ld (hl),0
        inc hl
        ld (hl),0
        inc hl
        ld (hl),#ED             ; SBC HL,DE
        inc hl
        ld (hl),#52
        inc hl
        ld (hl),#C4             ; CALL NZ,nn
        inc hl
        ld (hl),c
        inc hl
        ld (hl),b
        inc hl
        dec a
        jr nz,.pair
        push hl
        ld hl,PITCH
        add hl,de
        ex de,hl
        ld hl,6
        add hl,bc
        ld b,h
        ld c,l
        pop hl
        ex af,af'
        dec a
        jr nz,.row
        ld (hl),#C3             ; JP scandone
        inc hl
        ld (hl),low scandone
        inc hl
        ld (hl),high scandone
        ret
        ASSERT SCAN + ROWS * (3 + 9 * COLS / 2) + 3 <= IMTAB

; ---------------------------------------------------------------------------
; Кадровое прерывание.
isr:    push af
        ld (isr_usp),sp
        ld sp,isr_stack
        push bc
        push de
        push hl
        push ix
        exx
        push bc
        push de
        ld bc,#1FFD
        ld de,(MAP_SCREEN << 8) | MAP_RUN
        exx

        ld a,#FE                ; CAPS+ENTER - выход в Монитор
        in a,(#FE)
        rra
        jr c,.nocaps
        ld a,#BF
        in a,(#FE)
        rra
        jp nc,start
.nocaps:
        ld a,#7F                ; SYM+A - перерисовка выключена, SYM+B - включена
        in a,(#FE)
        bit 1,a
        jr nz,.nosym
        bit 4,a
        jr nz,.notb
        xor a
        ld (scanoff),a
.notb:  ld a,#FD
        in a,(#FE)
        rra
        jr c,.nosym
        ld a,1
        ld (scanoff),a
.nosym: call kscan              ; события клавиатуры для #F803 и #F812
        ld hl,lastkey
        cp (hl)
        jr z,.ksame
        ld (hl),a               ; другая клавиша или отпускание
        xor a
        ld (kready),a
        ld a,25                 ; полсекунды до автоповтора
        jr .knew
.ksame: ld hl,repcnt
        dec (hl)
        jr nz,.kdone
        ld a,3
.knew:  ld (repcnt),a
        ld a,(lastkey)
        cp #FE
        jr nc,.kdone
        ld (kcode),a
        ld a,1
        ld (kready),a
.kdone:
        ld a,(rus)              ; РУС - мигает первое знакоместо
        add a,a
        add a,a                 ; #20 -> #80
        or ATTR
        ld de,SCREEN + #1800
        call scrput
        ld a,(scanoff)
        or a
        jr nz,scanskip
        ld (isr_sp),sp
        jp SCAN                 ; CF = 0 после OR A

scandone:
        ld sp,(isr_sp)
scanskip:
; Курсор - подчёркивание, 16 кадров горит, 16 нет. На время сравнения он с
; экрана не снимается: сравнение идёт, пока луч рисует верхнюю половину
; экрана, и курсор, стёртый в начале прерывания, в верхних строках не был бы
; виден вовсе. Вместо этого после сравнения нижняя линия пары на старом месте
; рисуется заново из видеопамяти, и сразу ставится курсор на новом.
        ld hl,(cur_scr)
        ld a,h
        or a
        jr z,.noold
        ex de,hl
        ld hl,(cur_vid)
        call curline
        call scrput
        xor a
        ld (cur_scr + 1),a
.noold: ld hl,frames
        inc (hl)
        bit 4,(hl)
        jr z,.exit
        ld hl,(curaddr)
        ld de,(curpos)
        ld c,#F0
        bit 0,e
        jr z,.left
        ld c,#0F
        dec hl                  ; HL - начало пары в видеопамяти
.left:  ld (cur_vid),hl
        call curline
        xor c
        ld c,a
        ld a,d
        and #18
        or (high SCREEN) + 7
        ld h,a
        ld a,d
        rrca
        rrca
        rrca
        and #E0
        ld l,a
        ld a,e
        srl a
        or l
        ld l,a
        ld (cur_scr),hl
        ex de,hl
        ld a,c
        call scrput
.exit:  exx
        pop de
        pop bc
        exx
        pop ix
        pop hl
        pop de
        pop bc
        ld sp,(isr_usp)
        pop af
        ei
        ret

; Байт A в экран по адресу DE.
scrput: exx
        out (c),d
        exx
        ld (de),a
        exx
        out (c),e
        exx
        ret

; Нижняя линия пары знаков по адресу HL в видеопамяти. Портит HL.
curline:
        push de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld h,(high FONTL) + 7
        ld l,e
        ld a,(hl)
        ld h,(high FONTR) + 7
        ld l,d
        or (hl)
        pop de
        ret

; Пара знаков изменилась. Сюда приходят через CALL NZ из кода сравнения:
; HL = пара - тень, DE = тень, BC = константа строки, а адрес возврата CALL
; записал в видеопамять РК поверх самой пары (SP - указатель по видеопамяти).
; Пара возвращается на место, тень в коде обновляется, знаки рисуются.
; Адрес экрана = (SP + BC) / 2, где BC = 2 * адрес строки экрана - адрес
; строки видеопамяти - 2. Около 500 тактов на пару.
fix:    add hl,de               ; HL = новая пара: L - левый знак, H - правый
        pop ix                  ; адрес возврата
        push hl                 ; пару - обратно в видеопамять
        pop af
        ld (ix-7),l             ; новая тень
        ld (ix-6),h
        ex de,hl
        ld hl,0
        add hl,sp
        add hl,bc
        or a
        rr h
        rr l
        ld b,h
        ld c,l                  ; BC - байт экрана
        ld h,high FONTL
        ld l,e                  ; HL - левый знак в своём шрифте
        ld e,d
        ld d,high FONTR         ; DE - правый в своём
        exx
        out (c),d               ; экран на место
        exx
        DUP 7
        ld a,(de)
        or (hl)
        ld (bc),a
        inc d
        inc h
        inc b
        EDUP
        ld a,(de)
        or (hl)                 ; заодно CF = 0 для следующего SBC
        ld (bc),a
        exx
        out (c),e               ; и обратно: код сравнения - в странице 2
        exx
        jp (ix)

fixrows:
row = 0
        DUP ROWS
        ld bc,(2 * (SCREEN + ((row & #18) << 8) + ((row & 7) << 5)) - (VIDEO + PITCH * row) - 2) & #FFFF
        jp fix
row = row + 1
        EDUP

