; The BASIC shell shared by rle.asm and delta.asm, and the tape itself.
; Expects TITLE, TAPNAME, BUF and code_end.
;
;  10 CLEAR 25999: LOAD ""CODE
;  20 LET n=0: CLS: PRINT title''"1  record from EAR"'"2  play"'"3  save to tape"'"4  load from tape"''"Any key stops."
;  30 PAUSE 0: LET k$=INKEY$
;  40 IF k$="1" THEN PRINT AT 9,0;"Recording...": LET n=USR 64000: PRINT AT 9,0;"Recorded ";n;" bytes   "
;  50 IF k$="2" THEN PRINT AT 9,0;"Playing...": RANDOMIZE USR 64003: PRINT AT 9,0;"Done."
;  60 IF k$="3" AND n THEN SAVE "sound"CODE 26000,n
;  70 IF k$="4" THEN LOAD ""CODE 26000
;  80 GO TO 30
;
; Numbers are written as VAL "..." and NOT PI to keep the tokenising by hand simple.

        ASSERT BUF == 26000
        ORG #6000
basic
        DB 0,10
        DW .e1 - .b1
.b1     DB #FD,#B0,'"25999":'                   ; CLEAR VAL "25999":
        DB #EF,'""',#AF,#0D                     ; LOAD ""CODE
.e1     DB 0,20
        DW .e2 - .b2
.b2     DB #F1,'n=',#C3,#A7,':',#FB,':'         ; LET n=NOT PI: CLS:
        DB #F5,'"',TITLE,'"',"''"               ; PRINT title''
        DB '"1  record from EAR"',"'"
        DB '"2  play"',"'"
        DB '"3  save to tape"',"'"
        DB '"4  load from tape"',"''"
        DB '"Any key stops."',#0D
.e2     DB 0,30
        DW .e3 - .b3
.b3     DB #F2,#C3,#A7,':'                      ; PAUSE NOT PI:
        DB #F1,'k$=',#A6,#0D                    ; LET k$=INKEY$
.e3     DB 0,40
        DW .e4 - .b4
.b4     DB #FA,'k$="1"',#CB                     ; IF k$="1" THEN
        DB #F5,#AC,#B0,'"9",',#C3,#A7,';"Recording...          ":'
        DB #F1,'n=',#C0,#B0,'"64000":'          ; LET n=USR VAL "64000":
        DB #F5,#AC,#B0,'"9",',#C3,#A7,';"Recorded ";n;" bytes   "',#0D
.e4     DB 0,50
        DW .e5 - .b5
.b5     DB #FA,'k$="2"',#CB                     ; IF k$="2" THEN
        DB #F5,#AC,#B0,'"9",',#C3,#A7,';"Playing...            ":'
        DB #F9,#C0,#B0,'"64003":'               ; RANDOMIZE USR VAL "64003":
        DB #F5,#AC,#B0,'"9",',#C3,#A7,';"Done.     "',#0D
.e5     DB 0,60
        DW .e6 - .b6
.b6     DB #FA,'k$="3"',#C6,'n',#CB             ; IF k$="3" AND n THEN
        DB #F8,'"sound"',#AF,#B0,'"26000",n',#0D ; SAVE "sound"CODE VAL "26000",n
.e6     DB 0,70
        DW .e7 - .b7
.b7     DB #FA,'k$="4"',#CB                     ; IF k$="4" THEN
        DB #EF,'""',#AF,#B0,'"26000"',#0D       ; LOAD ""CODE VAL "26000"
.e7     DB 0,80
        DW .e8 - .b8
.b8     DB #EC,#B0,'"30"',#0D                   ; GO TO VAL "30"
.e8
basic_end

        EMPTYTAP TAPNAME
        SAVETAP TAPNAME,BASIC,"sampler",basic,basic_end - basic,10
        SAVETAP TAPNAME,CODE,"sampler",64000,code_end - 64000
