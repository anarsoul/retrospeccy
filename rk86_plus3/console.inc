; Печать в видеопамять РК и клавиатура.
; Общая часть двух сборок: rk86.asm (свой Монитор) и ../rk86mon_plus3/rk86mon.asm
; (Монитор РК-86).

; ---------------------------------------------------------------------------
; #F809: вывод знака C. Знак только записывается в видеопамять РК, на экран
; его перенесёт прерывание. Управляющие коды и ESC Y - как в Мониторе РК,
; только строк 24. Все регистры сохраняются; прерывания на выходе разрешены
; (программы РК щёлкают динамиком через DI/EI, а здесь без прерываний нет
; экрана).
putc:   push af
        push bc
        push de
        push hl
        call .do
        pop hl
        pop de
        pop bc
        pop af
        ei
        ret

.do:    ld hl,(curaddr)
        ld de,(curpos)          ; D = строка, E = столбец
        ld a,(escst)
        or a
        jp nz,.esc
        ld a,c
        and #7F
        ld c,a
        cp ' '
        jr nc,.print
        cp #1F
        jr z,.cls
        cp #0C
        jr z,.home
        cp #0D
        jr z,.cr
        cp #0A
        jr z,.lf
        cp #08
        jr z,.left
        cp #18
        jr z,.right
        cp #19
        jr z,.up
        cp #1A
        jr z,.down
        cp #1B
        jp z,.esc0
        cp #07
        jp z,bell
.print: ld (hl),c
        call right
        ld a,d                  ; перешли в начало экрана - значит, это была
        or e                    ; последняя позиция: назад и перевод строки
        jr nz,.store
        call up
.lf:    ld a,d
        cp ROWS - 1
        jr nz,.down
        push hl
        push de
        ld hl,VIDEO + PITCH     ; прокрутка: только видеопамять
        ld de,VIDEO
        ld bc,PITCH * (ROWS - 1)
        ldir
        ld hl,VIDEO + PITCH * (ROWS - 1)
        ld b,COLS
.clr:   ld (hl),0
        inc hl
        djnz .clr
        pop de
        pop hl
        jr .store
.down:  call down
        jr .store
.up:    call up
        jr .store
.left:  call left
        jr .store
.right: call right
        jr .store
.cr:    ld a,l
        sub e
        ld l,a
        jr nc,.cr1
        dec h
.cr1:   ld e,0
        jr .store
.cls:   ld hl,VTOP              ; РК чистит видеопамять нулями
        ld de,VTOP + 1
        ld bc,VLEN - 1
        ld (hl),0
        ldir
.home:  ld hl,VIDEO
        ld de,0
.store: di                      ; прерывание читает обе ячейки для курсора
        ld (curaddr),hl
        ld (curpos),de
        ret
.esc0:  ld a,1
.setst: ld (escst),a
        jr .store

; ESC Y <строка + #20> <столбец + #20>. Монитор РК ставит курсор в начало и
; шагает вниз и вправо нужное число раз, поэтому слишком большие числа
; заворачиваются, а больше #80 - не шагают совсем. Здесь так же.
.esc:   dec a
        jr z,.esc1
        dec a
        jr z,.esc2
        xor a
        ld (escst),a
        ld a,c
        sub ' '
        ld c,a
.col:   dec c
        jp m,.store
        push bc
        call right
        pop bc
        jr .col
.esc2:  ld a,c
        sub ' '
        ld c,a
.row:   dec c
        ld a,3
        jp m,.setst
        push bc
        call down
        pop bc
        jr .row
.esc1:  ld a,c
        cp 'Y'
        ld a,0
        jr nz,.setst
        ld hl,VIDEO
        ld de,0
        ld a,2
        jr .setst

; Шаги курсора: HL - адрес в видеопамяти, D - строка, E - столбец.
right:  inc hl
        inc e
        ld a,e
        cp COLS
        ret nz
        ld e,0
        ld bc,-COLS
        add hl,bc
down:   inc d
        ld bc,PITCH
        ld a,d
        cp ROWS
        jr nz,.add
        ld d,0
        ld bc,-PITCH * (ROWS - 1)
.add:   add hl,bc
        ret
left:   dec hl
        dec e
        ret p
        ld e,COLS - 1
        ld bc,COLS
        add hl,bc
up:     dec d
        ld bc,-PITCH
        jp p,.add
        ld d,ROWS - 1
        ld bc,PITCH * (ROWS - 1)
.add:   add hl,bc
        ret

; Звонок (код 7): около 2,8 кГц, 36 мс. Прерывания запрещены, иначе
; перерисовка рубит тон с частотой кадров.
bell:   di
        ld b,200
        ld a,BORDER
.half:  xor #10
        out (#FE),a
        ld c,38
.wait:  dec c
        jr nz,.wait
        djnz .half
        ret

; ---------------------------------------------------------------------------
; Клавиатура.
;
; #F81B: код нажатой клавиши без ожидания, #FF - ничего не нажато, #FE -
; РУС/ЛАТ (CAPS+SYM).
kstat:  push bc
        push de
        push hl
        call kscan
        pop hl
        pop de
        pop bc
        ei
        ret

; Ввод устроен как в Мониторе РК: нажатие - это событие. Прерывание раз в
; кадр опрашивает матрицу; новая клавиша (или автоповтор удержанной) взводит
; kready, #F803 его сбрасывает, отпускание - тоже. Поэтому <ВК>, которым
; закончили строку, не считается нажатой клавишей в следующем опросе #F812 -
; иначе, например, LIST Бейсика принимал бы его за паузу.
;
; #F812: A = #FF, если есть непрочитанное нажатие, иначе 0.
kpressed:
        ei
        ld a,(kready)
        or a
        ret z
        ld a,#FF
        ret

; #F803: ожидание клавиши, с автоповтором и щелчком.
getkey: ei
.wait:  ld a,(kready)
        or a
        jr nz,.got
        halt
        jr .wait
.got:   xor a
        ld (kready),a
        push bc
        ld a,BORDER + #10       ; щелчок
        out (#FE),a
        ld b,40
.click: djnz .click
        ld a,BORDER
        out (#FE),a
        pop bc
        ld a,(kcode)
        ret

; Опрос матрицы. A = код, #FF или #FE. Портит BC, DE, HL.
; Номер клавиши - полуряд * 5 + бит; CAPS (0) и SYM (36) - регистры.
kscan:  ld a,#FE
        in a,(#FE)
        cpl
        and 1
        ld d,a
        ld a,#7F
        in a,(#FE)
        cpl
        and 2
        or d
        ld d,a                  ; бит 0 - CAPS, бит 1 - SYM
        ld bc,#FEFE
        ld e,0
.row:   in a,(c)
        cpl
        and #1F
        ld h,5
.bit:   rra
        jr nc,.nobit
        ld l,a
        ld a,e
        or a
        jr z,.shift
        cp 36
        jr nz,.found
.shift: ld a,l
.nobit: inc e
        dec h
        jr nz,.bit
        rlc b
        jr c,.row
        ld hl,extdown           ; ничего, кроме регистров
        ld a,d
        cp 3
        jr z,.ext
        ld (hl),0
        ld a,#FF
        ret
.ext:   ld a,(hl)               ; CAPS+SYM: РУС/ЛАТ, один раз на нажатие
        ld (hl),1
        or a
        jr nz,.fe
        ld a,(rus)
        xor #20
        ld (rus),a
.fe:    ld a,#FE
        ret
.found: ld hl,keys
        ld a,d
        or a
        jr z,.table
        ld hl,keys + 40
        dec a
        jr z,.table
        ld hl,keys + 80
.table: ld d,0
        add hl,de
        ld a,(hl)
        cp #40                  ; РУС: коды #40-#5E уходят в #60-#7E
        ret c
        cp #5F
        ret nc
        ld hl,rus
        add a,(hl)
        ret

keys:   ; без регистра
        DB #FF,"ZXCV", "ASDFG", "QWERT", "12345", "09876", "POIUY"
        DB #0D,"LKJH", " ",#FF,"MNB"
        ; CAPS: буква - управляющий код (УС), цифры - клавиши РК:
        ; 1 АР2, 2 ТАБ, 3 домой, 4 СТР, 5 6 7 8 стрелки, 9 ПС, 0 ЗБ
        DB #FF,#1A,#18,#03,#16, #01,#13,#04,#06,#07, #11,#17,#05,#12,#14
        DB #1B,#09,#0C,#1F,#08, #7F,#0A,#18,#19,#1A, #10,#0F,#09,#15,#19
        DB #0D,#0C,#0B,#0A,#08, #03,#FF,#0D,#0E,#02
        ; SYM: знаки, как на клавишах Спектрума; D - "\", Y U - "[" "]", H - "^"
        DB #FF,":",#FF,"?/", #FF,#FF,#5C,#FF,#FF, #FF,#FF,#FF,"<>"
        DB "!@#$%", "_)('&", #22,";",#FF,"][", #0D,"=+-^", " ",#FF,".,*"

