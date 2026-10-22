#ifndef MD_H
#define MD_H

typedef unsigned char u8;
typedef signed char s8;
typedef unsigned short u16;
typedef signed short s16;
typedef unsigned long u32;
typedef signed long s32;

#define VDP_DATA   (*(volatile u16 *)0xC00000)
#define VDP_DATA32 (*(volatile u32 *)0xC00000)
#define VDP_CTRL   (*(volatile u16 *)0xC00004)
#define VDP_CTRL32 (*(volatile u32 *)0xC00004)

#define VRAM_W(a)  (0x40000000UL | (((u32)(a) & 0x3FFF) << 16) | ((u32)(a) >> 14))
#define CRAM_W(a)  (0xC0000000UL | ((u32)(a) << 16))
#define VSRAM_W(a) (0x40000010UL | ((u32)(a) << 16))

#endif
