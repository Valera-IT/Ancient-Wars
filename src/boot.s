| ANCIENT WARS - Mega Drive boot code: vector table, ROM header, startup.

    .section .text.boot,"ax"
    .globl  _start

vectors:
    .long   0x00FFFE00          | initial stack pointer
    .long   _start              | reset
    .rept   26
    .long   int_null            | CPU exceptions
    .endr
    .long   int_null            | level 4: HBlank
    .long   int_null            | level 5
    .long   vint                | level 6: VBlank
    .long   int_null            | level 7
    .rept   32
    .long   int_null            | TRAPs / reserved
    .endr

    .org    0x100, 0x20
    .ascii  "SEGA MEGA DRIVE "
    .ascii  "(C)FAN  2026.OCT"
    .ascii  "ANCIENT WARS"
    .org    0x150, 0x20
    .ascii  "ANCIENT WARS"
    .org    0x180, 0x20
    .ascii  "GM 00000001-00"
    .word   0x0000              | checksum (patched by tools/fixrom.py)
    .ascii  "J"
    .org    0x1A0, 0x20
    .long   0x00000000          | ROM start
    .long   0x003FFFFF          | ROM end (patched)
    .long   0x00FF0000          | RAM start
    .long   0x00FFFFFF          | RAM end
    .ascii  "RA"                | battery SRAM, odd bytes
    .byte   0xF8, 0x20
    .long   0x00200001          | SRAM start
    .long   0x00203FFF          | SRAM end
    .org    0x1F0, 0x20
    .ascii  "JUE"
    .org    0x200, 0x20

_start:
    move.w  #0x2700, %sr
    move.b  0xA10001, %d0       | TMSS: write 'SEGA' on hardware revisions > 0
    andi.b  #0x0F, %d0
    beq.s   1f
    move.l  #0x53454741, 0xA14000
1:
    move.w  0xC00004, %d0       | reset VDP command latch
    lea     0xFF0000, %a0       | clear work RAM
    move.w  #0x3FFF, %d0
    moveq   #0, %d1
2:  move.l  %d1, (%a0)+
    dbra    %d0, 2b
    lea     _data_load, %a0     | copy initialised data to RAM
    lea     _data_start, %a1
    lea     _data_end, %a2
3:  cmpa.l  %a2, %a1
    bhs.s   4f
    move.w  (%a0)+, (%a1)+
    bra.s   3b
4:  lea     0x00FFFE00, %sp
    jsr     main
5:  bra.s   5b

int_null:
    rte

vint:
    movem.l %d0-%d1/%a0-%a1, -(%sp)
    jsr     vint_c
    movem.l (%sp)+, %d0-%d1/%a0-%a1
    rte
