REM _RC2014_ + _Tektronix 4006-1_ + _BBC BASIC_ vector image slideshow program
REM
REM Forfeited into the public domain with NO WARRANTY. Read LICENSE for details.
REM
REM This program powers an interactive, menu-driven slideshow display of vector
REM graphics files on a Tektronix 4010-compatible terminal. It was written for
REM an RC2014 Zed Pro computer with an SIO/2 Dual Serial Module and the Digital
REM I/O Module (for blinkenlights!) connected to a Tektronix 4006-1 terminal
REM attached (via a TTL to RS-232 voltage level shifter) to the second (Port B)
REM serial port. Other hardware configurations may work but haven't been tested.
REM
REM (Hardcoded serial port parameters: 4600 BPS, 7 bits, even parity, 2 stop
REM bits; note that on your RC2014 Zed Pro, you will need to set the Clock 2
REM jumper on your Dual Clock Module to the 0.3072 position and **remove** the
REM Port B Clock jumper on the SIO/2 Dual Serial Module.)
REM
REM This program contains inline Z80 assembly code that talks directly to the
REM Z80 SIO/2 chip, so porting it to a different platform or a different BASIC
REM may be challenging.
REM
REM The program expects to run in a location where it has access to a file
REM called CATALOG.DAT. This file contains a sequence of records that list the
REM name of an accompanying file containing vector image data, the size of the
REM file in bytes, and a user-visible menu item name for the drawing stored in
REM the file. The easiest way to prepare this file is to use the
REM `make_slidesho_distro.py` file distributed alongside this program.
REM
REM Vector image data files are simply dumped directly to the terminal and so
REM don't strictly have to draw vector graphics per se, but in case that's
REM what you want, then the files should be set up to place the terminal into
REM graphic plot mode immediately (i.e. they should start with an ASCII GS
REM character, hex $1D). It's not necessary for the file to return the terminal
REM to alpha mode (ASCII US, hex $1F) when it's finished, but doing so is good
REM manners. The files created by the `hpgl2tek.py` program with the `tek4010`
REM device specified via the `-d` flag "do the right thing" out of the box.
REM
REM This program is released into the public domain without any warranty. For
REM details, refer to the LICENSE file distributed with this program, or, if
REM it's missing, to:
REM   - https://github.com/stepleton/hpgl2tek/blob/main/LICENSE
REM For further information, visit http://unlicense.org.
REM
REM This program originated at https://github.com/stepleton/hpgl2tek, and may
REM have been modified if obtained elsewhere.
REM
REM With thanks to these folks:
REM    - Spencer Owen for the delightful RC2014 family of Z80-based computers
REM    - Wayne Warthen for the RomWBW system software suite
REM    - R. T. Russell for maintaining and extending BBC BASIC for Z80 systems
REM and help from the following references:
REM    - http://www.bitsavers.org/pdf/tektronix/4006/
REM    - http://www.z80.info/zip/um0081.pdf
REM
REM Dependencies
REM ------------
REM
REM This program has been tested with version 5.00 of R. T. Russell's generic
REM BBC BASIC for Z80 systems. Tested hardware is described above. This program
REM will not work with earlier versions of BBC BASIC.
REM
REM Revision history
REM ----------------
REM
REM This section records the development of this file as part of the `hpgl2tek`
REM project at <http://github.com/stepleton/hpgl2tek>.
REM
REM 8 July 2024: Initial release.
REM (Tom Stepleton, stepleton@gmail.com, London)

   10 REM Serial port slideshow: print files to the serial port.
   20 REM ### Serial port initialisation ###
   30 DIM serinit 25
   40 FOR pass%=0 TO 2 STEP 2
   50   P%=serinit
   60   [
   70   OPT pass%
   80   ld hl,confstart
   90   ld b,confend-confstart
  100   ld c,&82 ; Serial port #2 control port
  110   otir
  120   ret
  130   .confstart
  140   DEFB &18 ; Wr0 Channel reset
  150   DEFB &14 ; Wr0 Pointer R4 + reset ex st int
  160   DEFB &CF ; Wr4 /64, async mode, 2 stop bit, even parity
  170   DEFB &03 ; Wr0 Pointer R3
  180   DEFB &41 ; Wr3 Receive enable, 7 bit
  190   DEFB &05 ; Wr0 Pointer R5
  200   DEFB &AA ; Wr5 Transmit enable, 7 bit, flow ctrl
REM  200   DEFB &68 ; Wr5 Transmit enable, 8 bit
  210   DEFB &11 ; Wr0 Pointer R1 + reset ex st int
  220   DEFB &00 ; Wr1 No Tx interrupts
  230   DEFB &00 ; Wr0 Pointer R0 (for future status reads)
  240   .confend
  250   ]
  260 NEXT pass%
  270 :

  280 REM ### Write the character in B% to the serial port ###
  290 DIM serput 40
  300 P%=serput
  310 [
  320 OPT 2
  330 .loop
  340 in a,(&82)   ; Get serial port 2 status
  350 bit 2,a      ; Are we done sending the previous byte?
  360 jr z,loop    ; Not yet, loop again
  370 ld a,b       ; Copy %B lsbyte to a
  380 out (&83),a  ; Send it out of serial port 2
  390 ret
  400 ]
  410 DEF PROC_serput(c%) : B%=c% : CALL serput : ENDPROC
  420 :

  430 REM ### Get a character from the serial port (or 0) into HL ###
  440 DIM serget 30
  450 FOR pass% = 0 TO 2 STEP 2
  460   P%=serget
  470   [
  480   OPT pass%
  490   di
  500   ld hl,0
  510   exx
  520   ld hl,0
  530   in a,(&82)  ; Get port status
  540   bit 0,a     ; Is there a character waiting?
  550   jr z,bye    ; Not now, bail out
  560   in a,(&83)  ; Get the character and copy it to L'
  570   and &7F     ; Strip high-order bit, which is parity sometimes
  580   ld l,a
  590   .bye
  600   exx
  610   ei
  620   ret
  630   ]
  640 NEXT pass%
  650 DEF FN_serget : =USR(serget)
  660 :

  670 REM ### Write B% bytes from address %H%L to the serial port ###
  680 DIM serputs 40
  690 P%=serputs
  700 [
  720 OPT 2
  730 .outer       ; Top of outer loop
  740 ld d,(hl)    ; Copy next byte to emit from the serial port to d
  750 inc hl       ; Point hl at the byte to send after the one in d
  760 .inner       ; Top of inner loop
  770 in a,(&82)   ; Get serial port 2 status
  780 bit 2,a      ; Are we done sending the previous byte?
  790 jr z,inner   ; Not yet, loop again
  800 ld a,d       ; Move the byte to send from d to a
  810 out (&83),a  ; Send the byte in a out of the serial port
  820 djnz outer   ; Loop to send the the next byte if one is left
  830 ret
  840 ]
  850 DEF PROC_serputs(b%,s%): B%=s% : L%=b%:H%=b% >> 8 : CALL serputs : ENDPROC
  860 :

 1000 REM ###### MAIN PROGRAM ######
 1010 REM ### Load the slide catalogue ###
 1020 fh=OPENIN "CATALOG.DAT"
 1030 nUM_FILES%=0
 1040 REPEAT : REM Count number of entries in the slide catalogue
 1050   INPUT#fh,filename$,size$,description$
 1060   nUM_FILES%=nUM_FILES%+1
 1070 UNTIL filename$="__END__" OR EOF#fh
 1080 nUM_FILES%=nUM_FILES%-1 : REM delimiting data files is hard
 1090 IF nUM_FILES% <= 0 THEN PRINT "No slides to show, giving up" : END
 1100 DIM fILENAMES$(nUM_FILES%) : REM Allocate memory for catalogue data
 1110 DIM sIZES%(nUM_FILES%)
 1120 DIM dESCRIPTIONS$(nUM_FILES%)
 1130 PTR#fh=0 : REM Rewind to catalogue start and load data
 1140 FOR i% = 1 TO nUM_FILES%
 1150   INPUT#fh,fILENAMES$(i%),size$,dESCRIPTIONS$(i%)
 1160   sIZES%(i%)=VAL(size$)
 1170 NEXT i%
 1180 CLOSE#fh
 1190 :
 1200 REM ### More initialisation ###
 1210 CALL serinit : REM Initialise serial port
 1220 cURSOR%=1 : REM Index of the first catalogue entry shown on screen
 1230 DIM bUF% 256 : REM 255 character buffer plus room for a terminator
 1240 :
 1250 REM ### Main loop! ###
 1260 REPEAT
 1270   PROC_showmenu
 1280   choice%=FN_getchoice(3 + FN_min(29, nUM_FILES% - cURSOR% + 1))
 1290   CASE choice% OF
 1300     WHEN 0 : PROC_slideshow : REM Play slideshow
 1310     WHEN 1 : cURSOR%=FN_max(1, cURSOR%-29) : REM Previous page 
 1320     WHEN 2 : cURSOR%=FN_min(nUM_FILES%, cURSOR%+29) : REM Next page
 1330     OTHERWISE : PROC_oneslide(cURSOR%+choice%-3) : REM Slide choice
 1340   ENDCASE
 1350 UNTIL FALSE
 1360 :

 4080 END : REM ###### LONG FUNCTION AND PROCEDURE DEFINITIONS ######
 4090 :

 5010 REM ### Tell the terminal to clear the screen; delay to give it time ###
 5020 DEF PROC_page
 5030 LOCAL i%
 5040 PROC_serput(&1B) : REM ESC FF --- a Tek-specific code
 5050 PROC_serput(&0C)
 5060 FOR i% = 1 TO 2000 : NEXT i% : REM Approx. two-second delay
 5070 ENDPROC
 5080 :

 6000 REM ### Write a nonempty string to the terminal screen ###
 6010 DEF PROC_write(s$)
 6020 LOCAL p% : REM p%=pointer to s$'s variable record, whose contents are:
 6030 p%=^s$ : REM [len, maxlen, data address LSByte, data address MSByte]
 6040 B%=?p% : L%=p%?2 : H%=p%?3 : CALL serputs
 6050 ENDPROC
 6060 :

 7000 REM ### Write nonempty string to the terminal screen followed by CR/LF ###
 7010 DEF PROC_writeln(s$)
 7020 PROC_write(s$)
 7030 PROC_serput(&0D) : REM CR
 7040 PROC_serput(&0A) : REM LF
 7050 ENDPROC
 7060 :

 8000 REM ### Get number from term in 0..(max-1) mapped to "0".."9""A".."Z" ###
 8010 DEF FN_getchoice(max%)
 8020 LOCAL c%
 8030 REPEAT : c%=FN__getchoice_inner : UNTIL c%<max%
 8040 =c%
 8050 DEF FN__getchoice_inner
 8060 LOCAL i%,c%,k%,choice%
 8070 i%=0 : k%=&FEFF
 8080 REPEAT
 8090   choice%=-1
 8100   REPEAT : REM Line below cycles blinkenlights while awaiting input
 8110     IF i% MOD 8==0 THEN k%=k%>>1 : PUT 0,k% : IF k% MOD 2==0 THEN k%=&FEFF
 8120     c%=FN_serget
 8130     i%+=1
 8140     IF i%>=8352 THEN c%=&30 : REM Timeout: as if the user pressed '0'
 8150   UNTIL c%<>0
 8160   IF c%>=&30 AND c%<=&39 THEN choice%=c%-&30 : REM 0..9
 8170   IF c%>=&41 AND c%<=&5A THEN choice%=c%-&37 : REM 10..35 (uppercase)
 8180   IF c%>=&61 AND c%<=&7A THEN choice%=c%-&57 : REM 10..35 (lowercase)
 8190 UNTIL choice%>=0
 8200 =choice%
 8210 :

 9000 REM ### Dump i'th catalogue file to terminal; abort+return on keypress ###
 9010 DEF FN_show(filenum%) : REM Arg is 1-indexed
 9020 LOCAL s%,i%,c%,k%,fh
 9030 PROC_page
 9040 fh=OPENIN fILENAMES$(filenum%)
 9050 s%=sIZES%(filenum%)
 9060 REPEAT
 9070   k%=s% >> 8
 9080   IF s%>=255 THEN PROC_sercopy(fh,255,k%) : s%=s%-255
 9090   IF s%<255 THEN PROC_sercopy(fh,s%,k%)
 9100   c%=FN_serget
 9110 UNTIL s%<255 OR c%<>0
 9120 CLOSE#fh
 9130 PROC_gotorc(0,0) : REM Returns us to alpha mode
 9140 =c%
 9150 :

10000 REM ### Move cursor on terminal to a specified row/column location ###
10010 DEF PROC_gotorc(row%, col%) : REM Args are 0-indexed
10020 LOCAL x%,y%
10030 x%=col%*1024/75 : REM Compute graphical X, Y coordinates
10040 y%=767*(1-row%/34)
10050 PROC_serput(&1D) : REM GS - enter graphics mode, moving not drawing
10060 PROC_serput(32 + (y% >> 5)) : REM Y coordinate high byte
10070 PROC_serput(96 + (y% MOD 32)) : REM Y coordinate high byte
10080 PROC_serput(32 + (x% >> 5)) : REM X coordinate high byte
10090 PROC_serput(64 + (x% MOD 32)) : REM X coordinate high byte
10100 PROC_serput(&1F) : REM US - return to alpha mode
10110 ENDPROC
10120 :

11000 REM ### Integer min and max ###
11010 DEF FN_min(a%, b%) IF a%<b% THEN =a% ELSE =b%
11020 DEF FN_max(a%, b%) IF a%>b% THEN =a% ELSE =b%
11030 :

12000 REM ### Show main menu ###
12010 DEF PROC_showmenu
12020 LOCAL i%,keys$
12030 keys$="3456789ABCDEFGHIJKLMNOPQRSTUV"
12040 PROC_page
12050 PROC_gotorc(0, 22)
12060 PROC_write("TEKTRONIX 4006-1 TERMINAL DEMO")
12070 PROC_gotorc(1, 12)
12080 PROC_write("0) START SLIDESHOW  1) PREVIOUS PAGE  2) NEXT PAGE")
12090 PROC_gotorc(33, 24)
12100 PROC_write("AWAITING YOUR SELECTION...")
12110 IF cURSOR%>nUM_FILES% THEN ENDPROC
12120 FOR i%=1 TO FN_min(29, nUM_FILES%-cURSOR%+1)
12130   PROC_gotorc(2+i%, 4)
12140   PROC_write(MID$(keys$,i%,1))
12150   PROC_write(") ")
12160   PROC_write(LEFT$(dESCRIPTIONS$(cURSOR%+i%-1), 64))
12170 NEXT i%
12180 PROC_gotorc(0,0)
12190 ENDPROC
12200 :

13000 REM ### Delay awaiting a terminal keypress, or return 0 ###
13010 DEF FN_delay(loops%)
13020 LOCAL i%,c%
13030 FOR i%=1 TO loops%
13040   c%=FN_serget
13050   IF c%<>0 THEN i%=loops%
13060 NEXT i%
13070 =c%
13080 :

14000 REM ### Show a continuously looping slideshow from the catalogue ###
14010 DEF PROC_slideshow
14020 LOCAL start%,i%,c% : REM Starting from a random file
14030 IF nUM_FILES%>1 THEN start%=RND(nUM_FILES%) ELSE start%=1
14040 REPEAT
14050   FOR i%=start% TO nUM_FILES%
14060     c%=FN_show(i%) : REM User can abort or go to next with a keypress
14070     IF c%=0 THEN c%=FN_delay(4000) : REM Otherwise, delay about 10s
14080     IF c%=&51 OR c%=&71 THEN i%=nUM_FILES% : REM Quit if user said Q
14090   NEXT i%
14100   start%=1
14110 UNTIL c%=&51 OR c%=&71 : REM One more check for Q
14120 ENDPROC
14130 :

15000 REM ### Show a single slide, awaiting a terminal keypress ###
15010 DEF PROC_oneslide(filenum%)
15020 LOCAL i%,c%
15030 i%=0
15040 IF FN_show(filenum%)<>0 THEN ENDPROC
15050 REPEAT
15060   c%=FN_serget
15070   i%=i%+1
15080   IF i%>=20000 THEN c%=&20 : REM Experiment to find a good timeout value
15090 UNTIL c%<>0
15100 ENDPROC
15110 :

16000 REM ### Copy n%<256 file chars to SIO port 2; k% to blinkenlights ###
16010 DEF PROC_sercopy(fh,n%,k%)
16020 $bUF%=GET$#fh BY n% : REM Load data from the filehandle
16030 PUT 0,k%
16040 B%=n% : L%=bUF% : H%=bUF% >> 8 : CALL serputs
16050 ENDPROC
16060 :
