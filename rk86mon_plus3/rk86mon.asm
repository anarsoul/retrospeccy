; "Радио-86РК" (32К) с настоящим Монитором для ZX Spectrum +2A/+2B/+3.
;
; Второе поколение программы с кассеты green_svema (сторона 1, записи 31-49):
; вместо своего Монитора - ПЗУ Монитора РК-86, подменено только то, что
; обращается к железу. Лента - в родном формате РК, процедурами самого
; Монитора: директивы I и O, входы #F806 и #F80C.
;
; Сборка:  make  (mkmon.py делает mon32.bin из копии Монитора на кассете,
;                 sjasmplus rk86mon.asm -> rk86mon.tap)
;
; Печать, клавиатура и прерывание - общие с первой пересборкой:
; ../rk86_plus3/console.inc и render.inc.
;
; У +2A/+3 страницы 4-7 "медленные": пока луч рисует картинку, видеоконтроллер
; придерживает процессор на каждом обращении к ним. Процедуры ленты Монитора
; отмеряют время циклами, и в такой памяти длительность бита плавает на десятки
; процентов в зависимости от места в кадре - запись РК не читается. Поэтому
; всё, что исполняется, лежит в страницах 0-3 (раскладка "всё ОЗУ" номер 0):
;   #0000-#75FF  ОЗУ программы РК (страницы 0 и 1)
;   #7600-#76CF  рабочие ячейки и стек Монитора
;   #76D0-#7FF3  видеопамять РК, 30 строк по 78; видимое окно с #77C2
;   #8100-#9C4A  код сравнения с теневой копией (страница 2, генерируется)
;   #9D00-#9E00  таблица векторов IM 2
;   #D000-#DFFF  два сдвинутых шрифта по линиям (страница 3, генерируются)
;   #E290-#F7FF  эта программа
;   #F800-#FFFF  Монитор РК-86 с правками (в конце файла)
; Экрана Спектрума в этой раскладке нет: он бывает только в страницах 5 и 7.
; Прерывание на время записи в экран включает раскладку 4-5-6-3 - страница 3
; с кодом остаётся на месте, экран появляется в #4000 - и сразу возвращает
; прежнюю.
;
; Монитор пишет в порты ВВ55 (#8000-#8003, #A000-#A003), ВГ75 (#C000-#C001) и
; ВТ57 (#E000-#E008). По этим адресам ничего нет.

        DEVICE ZXSPECTRUM48

VTOP    EQU #76D0               ; начало видеопамяти РК
VLEN    EQU 78*30
VIDEO   EQU #77C2               ; первый видимый знак
PITCH   EQU 78
ROWS    EQU 24
COLS    EQU 64
SCAN    EQU #8100               ; сгенерированный код сравнения
IMTAB   EQU #9D00
IMBYTE  EQU #F7                 ; вектор #F7F7
FONTL   EQU #D000               ; 8 линий по 256 байт: знак в старшем полубайте
FONTR   EQU #D800               ; то же в младшем
SCREEN  EQU #4000               ; экран Спектрума: страница 5, когда она подключена
MAP_RUN    EQU 1                ; порт #1FFD: страницы 0-1-2-3
MAP_SCREEN EQU 5                ; страницы 4-5-6-3
BORDER  EQU 1
ATTR    EQU #0F                 ; белый по синему

LOADER  EQU #6000
ENTRY   EQU #E290

MONITOR EQU #F800
MCOLD   EQU #F836               ; холодный старт Монитора
MERROR  EQU #FAAE               ; "?" и приглашение

; Константы ленты. Монитор РК держит их в ячейках #762F (чтение) и #7630
; (запись): это число оборотов цикла задержки. У РК они равны #2A и #1D, а
; оборот цикла (POP PSW : DCR B : JNZ) занимает 25 тактов 8080 на 1,78 МГц.
; Здесь оборот - NOP : DEC B : JP NZ, 18 тактов Z80 на 3,55 МГц, и вокруг него
; другие команды, поэтому числа другие. Подобраны так, чтобы длительности
; совпали с РК: см. README и test.py.
TAPE_RD     EQU 118
TAPE_WR     EQU 80
TAPE_RDSUB  EQU 25              ; поправка задержки на границе байта при чтении
TAPE_WRSUB  EQU 17              ; и при записи

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
; Запуск и CAPS+ENTER. Память программы РК не трогается.
start:  di
        ld bc,#7FFD
        ld a,#13                ; показывать обычный экран (страницу 5)
        out (c),a
        ld bc,#1FFD
        ld a,MAP_SCREEN         ; экран в #4000; мотор выключен
        out (c),a
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
        ld sp,VTOP - 1

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
        ld (kready),a
        jp MCOLD                ; дальше - Монитор: чистит экран кодом #1F,
                                ; печатает "РАДИО-86РК" и приглашение

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

; #F82D: Монитор здесь запускает ВГ75 и ВТ57 - в начале работы и после
; каждого обмена с лентой. Запускать нечего; возвращаем бордюр.
vinit:  push af
        ld a,BORDER
        out (#FE),a
        pop af
        ret

; ---------------------------------------------------------------------------
; Лента. Монитор выводит бит в разряд 0 порта C ВВ55 (#8002) и читает из
; разряда 4. Обе команды заменены вызовами этих процедур.
;
; Прерывания запрещаются и остаются запрещёнными: первая же печать или опрос
; клавиатуры их разрешит. Во время обмена экран не обновляется.
;
; Запись: A, разряд 0 -> выход на магнитофон (MIC) и бордюр.
tape_out:
        di
        rrca
        sbc a,a
        and #0F
        out (#FE),a
        ret

; То же для второй половины бита. У РК она на 59 тактов (33 мкс) длиннее
; первой: в неё попадают счётчик битов и перезагрузка константы. Здесь эти
; команды идут вдвое быстрее, разницу добирает задержка: 75 тактов.
tape_out2:
        di
        rrca
        sbc a,a
        and #0F
        out (#FE),a
        push af
        pop af
        push af
        pop af
        push af
        pop af
        jr $+2
        ret

; Чтение: вход EAR (разряд 6) -> разряд 4 A; заодно бордюр.
tape_in:
        di
        in a,(#FE)
        rlca
        rlca
        and 1
        out (#FE),a
        rlca
        rlca
        rlca
        rlca
        ret

        INCLUDE "../rk86_plus3/console.inc"

        INCLUDE "../rk86_plus3/render.inc"

; ---------------------------------------------------------------------------
curaddr: DW VIDEO               ; адрес курсора в видеопамяти
curpos: DW 0                    ; столбец, строка
escst:  DB 0                    ; разбор ESC Y: 1 - был ESC, 2 - ждём строку, 3 - столбец
rus:    DB 0                    ; 0 - ЛАТ, #20 - РУС
extdown: DB 0
lastkey: DB #FF
repcnt: DB 25
kready: DB 0                    ; есть непрочитанное нажатие
kcode:  DB 0
scanoff: DB 0
frames: DB 0
cur_scr: DW 0                   ; байт экрана с курсором; старший байт 0 - курсора нет
cur_vid: DW 0                   ; и адрес этой пары в видеопамяти
isr_usp: DW 0
isr_sp: DW 0
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
        BLOCK MONITOR - $, 0

; ---------------------------------------------------------------------------
; Монитор РК-86 (32К) с правками. MONTO копирует ПЗУ до указанного адреса,
; за ним идёт то, что стоит на этом месте вместо родных байт.
        MACRO MONTO addr
        INCBIN "mon32.bin", $ - MONITOR, addr - $
        ENDM

        ASSERT $ == MONITOR
        MONTO MCOLD
        xor a                   ; LD A,#8A : LD (#8003),A - режим ВВ55.
        ld (escst),a            ; Вместо него: программа могла выйти сюда
        nop                     ; посреди ESC Y, а первым печатается код #1F
        MONTO #F862
        DB TAPE_RD, TAPE_WR     ; LD HL,#1D2A : LD (#762F),HL - константы ленты
        MONTO #F88F
        DW MERROR               ; директива U уходила в ПЗУ пользователя, #F000
        MONTO #F8DA
        DW MERROR               ; туда же - неизвестная директива
        MONTO #FA7B
        jp getcur               ; #F81E
        MONTO #FA7F
        jp getchr               ; #F821
        MONTO #FACE
        jp vinit                ; #F82D: запуск ВГ75 и ВТ57

; Чтение байта (#F806, #FB98). В РК на время обмена SP ставится в ноль, и
; POP PSW служит задержкой. С вызовами вместо команд порта так нельзя: CALL
; писал бы адрес возврата в память программы. Стек остаётся на месте,
; задержка - NOP.
        MONTO #FBA5
        nop                     ; LD SP,#0000
        nop
        nop
        MONTO #FBAD
        call tape_in            ; LD A,(#8002)
        MONTO #FBB7
        nop                     ; POP PSW
        MONTO #FBC3
        nop                     ; POP PSW
        call tape_in            ; LD A,(#8002)
        MONTO #FBDB
        DB TAPE_RDSUB           ; SUB #12
        MONTO #FBDD
        nop                     ; POP PSW
        MONTO #FBE3
        call tape_in            ; LD A,(#8002)

; Запись байта (#F80C, #FC46).
        MONTO #FC53
        nop                     ; LD SP,#0000
        nop
        nop
        MONTO #FC58
        nop                     ; POP PSW
        MONTO #FC5F
        call tape_out           ; LD (#8002),A
        MONTO #FC66
        nop                     ; POP PSW
        MONTO #FC6E
        call tape_out2          ; LD (#8002),A
        MONTO #FC79
        DB TAPE_WRSUB           ; SUB #0E
        MONTO #FC7B
        nop                     ; POP PSW

        MONTO #FCBA
        jp putc                 ; #F809: вывод знака C
        MONTO #FE01
        jp kpressed             ; #F812: нажата ли клавиша
        MONTO #FE63
        jp getkey               ; #F803: ввод знака с клавиатуры
        MONTO #FE72
        jp kstat                ; #F81B: код клавиши без ожидания
        INCBIN "mon32.bin", $ - MONITOR
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

        EMPTYTAP "rk86mon.tap"
        SAVETAP "rk86mon.tap",BASIC,"RK86MON",basic,basic.end - basic,10
        SAVETAP "rk86mon.tap",CODE,"rk86mon",LOADER,code_end - LOADER
