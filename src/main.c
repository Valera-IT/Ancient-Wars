/* ANCIENT WARS - a Dota-style MOBA for the Sega Mega Drive / Genesis.
 * Top-down 1024x1024 map in the spirit of Herzog Zwei: three lanes, a river, jungle,
 * one hero per side (Shadow Fiend, Pudge or Axe), creep waves, towers and Ancients. */
#include "md.h"
#include "gfx.h"
#include "sound.h"

/* VRAM layout: tiles 0x0000-0x9FFF, 64x64 planes */
#define PLANE_A 0xA000
#define PLANE_B 0xC000
#define WINDOW  0xE000
#define SPRTAB  0xF000
#define HSCRL   0xF400

#define ATTR(pal, prio, t) ((u16)(((prio) << 15) | ((pal) << 13) | (t)))
#define HFLIP 0x0800
#define FX(v) ((s16)((v) << 4))
#define PX(v) ((s16)((v) >> 4))
#define ABS(v) ((v) < 0 ? -(v) : (v))

#define WORLD 1024
#define VIEW_W 320
#define VIEW_H 192
#define HUD_Y 24

enum { B_UP = 1, B_DOWN = 2, B_LEFT = 4, B_RIGHT = 8, B_B = 16, B_C = 32, B_A = 64, B_START = 128,
       B_Z = 0x100, B_Y = 0x200, B_X = 0x400, B_MODE = 0x800 };

/* gcc may emit calls to these */
void *memset(void *d, int c, unsigned long n) { u8 *p = d; while (n--) *p++ = (u8)c; return d; }
void *memcpy(void *d, const void *s, unsigned long n) { u8 *p = d; const u8 *q = s; while (n--) *p++ = *q++; return d; }

/* ================================================================ platform */
static volatile u8 vflag;
static volatile u16 vcount;

void vint_c(void)
{
    vflag = 1;
    vcount++;
    sound_update();
}

static void wait_vsync(void)
{
    vflag = 0;
    while (!vflag)
        ;
}

static void vdp_reg(u8 r, u8 v) { VDP_CTRL = 0x8000 | ((u16)r << 8) | v; }

static const u8 vdp_init_regs[24] = {
    0x04, 0x34, 0x28, 0x38, 0x06, 0x78, 0x00, 0x00,
    0x00, 0x00, 0xFF, 0x00, 0x81, 0x3D, 0x00, 0x02,
    0x11, 0x00, 0x98, 0x00, 0x00, 0x00, 0x00, 0x00 };   /* 64x64 planes, window = bottom 4 rows */

static void display(u8 on) { vdp_reg(1, on ? 0x74 : 0x34); }

static void vdp_init(void)
{
    u16 i;
    for (i = 0; i < 24; i++)
        vdp_reg(i, vdp_init_regs[i]);
    VDP_CTRL32 = VRAM_W(0);
    for (i = 0; i < 0x4000; i++) VDP_DATA32 = 0;
    VDP_CTRL32 = CRAM_W(0);
    for (i = 0; i < 64; i++) VDP_DATA = 0;
    VDP_CTRL32 = VSRAM_W(0);
    for (i = 0; i < 40; i++) VDP_DATA = 0;
    VDP_CTRL32 = VRAM_W(32);
    for (i = 0; i < GFX_TILES * 8; i++) VDP_DATA32 = gfx_tiles[i];
}

/* hero sprites stay in ROM (15 poses of 4x4 tiles each); the ones in play get a pose slot after the other graphics */
#define T_HSLOT (GFX_TILES + 1)
#define T_SKI (T_HSLOT + 16 * NH)    /* the HUD hero's four ability icons, 2x2 tiles each */
#define T_PORT (T_SKI + 16)          /* and its portrait, 3x3 */
#define T_SKI2 (T_PORT + 9)          /* split screen: the same for the second player */
#define T_PORT2 (T_SKI2 + 16)
#define T_MATCH (T_PORT2 + 9)        /* the jungle creeps and the camp, loaded at the match start (the draft uses this room) */
#define T_CLOCK 1954                 /* match: the clock digits (0xF440, after the 4 bytes of hscroll) */
#define T_DICON 1984                 /* draft: the skills of the hero under the cursor (0xF800, past the hscroll table) */
#define T_DHERO(k) ((k) < NHERO - 1 ? T_HSLOT + times(32, k) : T_DICON + 16)   /* draft: stand and attack poses; the last hero's fit up there */
static void hero_tiles(u8 kind, u8 first, u8 n, u16 dst)
{
    const u32 *src = hero_art + (first << 3);
    u16 k;
    while (kind--) src += 240 * 8;
    VDP_CTRL32 = VRAM_W(dst << 5);
    for (k = (u16)n << 3; k; k--) VDP_DATA32 = *src++;
}

static volatile u16 dma_cmd[2];

static void dma_vram(const void *src, u16 dst, u16 words);

static void dma_vram(const void *src, u16 dst, u16 words)
{
    u32 s = ((u32)src) >> 1, c;
    VDP_CTRL = 0x9300 | (words & 0xFF);
    VDP_CTRL = 0x9400 | (words >> 8);
    VDP_CTRL = 0x9500 | (s & 0xFF);
    VDP_CTRL = 0x9600 | ((s >> 8) & 0xFF);
    VDP_CTRL = 0x9700 | ((s >> 16) & 0x7F);
    c = VRAM_W(dst) | 0x80;
    dma_cmd[0] = c >> 16;
    dma_cmd[1] = c;
    VDP_CTRL = dma_cmd[0];
    VDP_CTRL = dma_cmd[1];
}

static u16 palbuf[64];

static void pal_set(u8 n, const u16 *p)
{
    u8 i;
    for (i = 0; i < 16; i++) palbuf[(n << 4) + i] = p[i];
}

/* day and night: dn_lvl 0 (day) .. 8 (night) takes the red, then the green, then a little of the
   blue out of the map line; the unit lines get half of it, the UI line none */
static u8 dn_lvl, pal_dirty;
static u16 palnow[64];      /* the match palette at dn_lvl, for flush() to copy in the blank */

static u16 pal_color(u8 i)
{
    u16 c = palbuf[i];
    u8 n = dn_lvl;
    s8 r, g, b;
    if (!n || (i & 0x30) == 0x10) return c;
    if (i & 0x20) n >>= 1;
    r = ((c >> 1) & 7) - (n >> 1);
    g = ((c >> 5) & 7) - ((n * 3) >> 3);
    b = ((c >> 9) & 7) - (n >> 3);
    if (r < 0) r = 0;
    if (g < 0) g = 0;
    if (b < 0) b = 0;
    return (r << 1) | (g << 5) | ((u16)b << 9);
}

static void pal_night(void)
{
    u8 i;
    for (i = 0; i < 64; i++) palnow[i] = pal_color(i);
    pal_dirty = 1;
}

static void pal_upload(u8 lvl)
{
    u8 i;
    VDP_CTRL32 = CRAM_W(0);
    for (i = 0; i < 64; i++) {
        u16 c = pal_color(i);
        if (lvl < 8) {
            u16 r = (((c >> 1) & 7) * lvl) >> 3;
            u16 g = (((c >> 5) & 7) * lvl) >> 3;
            u16 b = (((c >> 9) & 7) * lvl) >> 3;
            c = (r << 1) | (g << 5) | (b << 9);
        }
        VDP_DATA = c;
    }
}

static void fade(u8 in)
{
    u8 l;
    for (l = 0; l <= 8; l++) {
        wait_vsync();
        pal_upload(in ? l : 8 - l);
        wait_vsync();
    }
}

/* plane A never scrolls: it is the overlay for menus and messages - except in split screen,
   where it holds the left player's map and all text goes to the window plane */
static u16 afont = T_FONT;     /* T_FONTW while drawing on an opaque panel */
static u8 split;

static void textA(u8 x, u8 y, const char *s)
{
    if (split) return;
    VDP_CTRL32 = VRAM_W(PLANE_A + ((u16)y << 7) + (x << 1));
    while (*s) { VDP_DATA = ATTR(1, 1, afont + (u8)(*s - 32)); s++; }
}

/* opaque panel on plane A, rows y0..y1, columns x0..x1-1; following text is drawn opaque too */
static void panelA(u8 x0, u8 x1, u8 y0, u8 y1)
{
    u8 x;
    if (split) return;
    for (; y0 <= y1; y0++) {
        VDP_CTRL32 = VRAM_W(PLANE_A + ((u16)y0 << 7) + (x0 << 1));
        for (x = x0; x < x1; x++) VDP_DATA = ATTR(1, 1, T_FONTW);
    }
    afont = T_FONTW;
}

static u8 slen(const char *s) { u8 n = 0; while (s[n]) n++; return n; }
static void textA_c(u8 y, const char *s) { textA((40 - slen(s)) >> 1, y, s); }

static void clearA(u8 y)
{
    u8 i;
    if (split) return;
    VDP_CTRL32 = VRAM_W(PLANE_A + ((u16)y << 7));
    for (i = 0; i < 64; i++) VDP_DATA = 0;
}

static void textW(u8 x, u8 y, const char *s)
{
    VDP_CTRL32 = VRAM_W(WINDOW + ((((u16)y << 6) + x) << 1));
    while (*s) { VDP_DATA = ATTR(1, 1, T_FONTW + (u8)(*s - 32)); s++; }
}

static void clearW(u8 y)
{
    u8 i;
    VDP_CTRL32 = VRAM_W(WINDOW + ((u16)y << 7));
    for (i = 0; i < 64; i++) VDP_DATA = ATTR(1, 1, T_FONTW);
}

static void num(u16 v, u8 digits, char *buf)
{
    static const u16 pw[5] = { 10000, 1000, 100, 10, 1 };
    u8 i;
    for (i = 5 - digits; i < 5; i++) {
        char c = '0';
        while (v >= pw[i]) { v -= pw[i]; c++; }
        *buf++ = c;
    }
    *buf = 0;
}

static u16 rs = 0x5EED;
static u16 rnd(void)
{
    rs ^= rs << 7;
    rs ^= rs >> 9;
    rs ^= rs << 8;
    return rs;
}

/* 3- and 6-button pad reading. Returns the button mask, sets *six for 6-button pads. */
static u16 read_pad(u8 port, u8 *six)
{
    volatile u8 *d = (volatile u8 *)(0xA10003 + (port << 1));
    u8 a, b, c, e;
    u16 r;
    *d = 0x40; __asm__ volatile ("nop\n\tnop"); a = *d;
    *d = 0x00; __asm__ volatile ("nop\n\tnop"); b = *d;
    *d = 0x40; __asm__ volatile ("nop\n\tnop");
    *d = 0x00; __asm__ volatile ("nop\n\tnop");
    *d = 0x40; __asm__ volatile ("nop\n\tnop");
    *d = 0x00; __asm__ volatile ("nop\n\tnop"); c = *d;
    *d = 0x40; __asm__ volatile ("nop\n\tnop"); e = *d;
    *d = 0x00; __asm__ volatile ("nop\n\tnop");
    *d = 0x40;
    r = (~a & 0x3F) | ((~b & 0x30) << 2);
    *six = (c & 0x0F) == 0;
    if (*six)
        r |= (u16)(~e & 0x0F) << 8;
    return r;
}

static u16 sprbuf[80 * 4];
static u8 nspr;
static s16 clip_x0 = -32, clip_x1 = 352;   /* split screen: sprites must fit inside their view */
static s16 vw_x0 = 0, vw_x1 = 320;         /* the selected view's visible screen columns */

/* split screen: each frame redraws one half's scene into its cache; both caches are then
   replayed, shifted by how far that half's camera moved since the cache was made */
typedef struct { s16 x, y; u16 attr; u8 size, pad; } CSpr;
static CSpr scache[2][64];
static u8 scn[2], sc_rec = 0xFF;

static void spr(s16 x, s16 y, u8 size, u16 attr)
{
    u16 *p;
    if (sc_rec < 2) {
        if (scn[sc_rec] < 64 && x > -32 && x < 320 && y > -32 && y < 224) {
            CSpr *c = &scache[sc_rec][scn[sc_rec]++];
            c->x = x; c->y = y; c->attr = attr; c->size = size;
        }
        return;
    }
    if (nspr >= 80 || x <= -32 || x >= 320 || y <= -32 || y >= 224 ||
        x < clip_x0 || x + ((((size >> 2) & 3) + 1) << 3) > clip_x1)
        return;
    p = &sprbuf[nspr << 2];
    p[0] = (y + 128) & 0x3FF;
    p[1] = ((u16)size << 8) | (nspr + 1);
    p[2] = attr;
    p[3] = (x + 128) & 0x1FF;
    nspr++;
}

static void spr_finish(void)
{
    if (!nspr) {
        sprbuf[0] = sprbuf[1] = sprbuf[2] = sprbuf[3] = 0;
        nspr = 1;
    }
    sprbuf[((nspr - 1) << 2) + 1] &= 0xFF00;
}

/* ================================================================ scrolling map */
static s16 camx, camy;      /* top-left of the view in world pixels */
static s16 ldx, ldy;        /* tile origin the plane currently holds */
static u8 shake;

/* Split screen: view 0 (left, 160 px) streams into plane A, view 1 (right, 152 px) into plane B.
   The window plane covers columns 20-39 (a divider, then see-through cells over plane B) and the
   rows from 23 down (messages and the two HUDs); column 20 is an 8 px divider. camx/camy/ldx/ldy belong to the selected view;
   outside vsel() pairs the selected view is always 1, the normal single-screen one. A view's camx
   is the world x at screen x 0, so the right view's camx is 168 px left of what it shows. */
#define SPLIT_H 184
static u16 plane_cur = PLANE_B;
static u8 cur_v = 1;
static s16 vcx[2], vcy[2], vldx[2], vldy[2];

static void vsel(u8 k)
{
    vcx[cur_v] = camx; vcy[cur_v] = camy; vldx[cur_v] = ldx; vldy[cur_v] = ldy;
    cur_v = k;
    camx = vcx[k]; camy = vcy[k]; ldx = vldx[k]; ldy = vldy[k];
    plane_cur = k ? PLANE_B : PLANE_A;
    clip_x0 = split ? (k ? 160 : -32) : -32;
    clip_x1 = split ? (k ? 352 : 168) : 352;
    vw_x0 = split && k ? 168 : 0;
    vw_x1 = split && !k ? 160 : 320;
}

static u16 map_at(s16 tx, s16 ty)
{
    if (tx < 0) tx = 0;
    if (tx > 127) tx = 127;
    if (ty < 0) ty = 0;
    if (ty > 127) ty = 127;
    return map_ground[((u16)ty << 7) + tx];
}

static void put_cell(s16 tx, s16 ty)
{
    VDP_CTRL32 = VRAM_W(plane_cur + (((u16)(ty & 63)) << 7) + ((tx & 63) << 1));
    VDP_DATA = map_at(tx, ty);
}

static void stream_col(s16 tx)
{
    s16 ty;
    for (ty = ldy - 1; ty <= ldy + 25; ty++) put_cell(tx, ty);
}

static void stream_row(s16 ty)
{
    s16 tx;
    VDP_CTRL32 = VRAM_W(plane_cur + (((u16)(ty & 63)) << 7));
    for (tx = 0; tx < 64; tx++) {       /* the whole plane row: cheap and wrap-free */
        s16 w = ldx - 1 + ((tx - (ldx - 1)) & 63);
        VDP_DATA = map_at(w, ty);
    }
}

static void map_load(void)
{
    s16 ty;
    ldx = camx >> 3;
    ldy = camy >> 3;
    for (ty = ldy - 1; ty <= ldy + 25; ty++) stream_row(ty);
}

static void map_stream(void)
{
    s16 cx = camx >> 3, cy = camy >> 3;
    if (ABS(cx - ldx) > 20 || ABS(cy - ldy) > 12) { map_load(); return; }
    while (ldx < cx) { ldx++; stream_col(ldx + 41); }
    while (ldx > cx) { ldx--; stream_col(ldx - 1); }
    while (ldy < cy) { ldy++; stream_row(ldy + 25); }
    while (ldy > cy) { ldy--; stream_row(ldy - 1); }
}

static void scroll_set(void)
{
    s16 sx = camx, sy = camy, ax = 0, ay = 0;
    if (shake) { s16 jx = (rnd() & 3) - 1, jy = (rnd() & 3) - 1; shake--; sx += jx; sy += jy; ax = jx; ay = jy; }
    if (split) { ax += vcx[0]; ay += vcy[0]; } else ax = ay = 0;
    VDP_CTRL32 = VRAM_W(HSCRL);
    VDP_DATA = -ax;
    VDP_DATA = -sx;
    VDP_CTRL32 = VSRAM_W(0);
    VDP_DATA = ay;
    VDP_DATA = sy;
}

static u8 in_match;
static void hero_poses(void);
static void flush(void)
{
    wait_vsync();
    if (pal_dirty) {
        u8 i;
        pal_dirty = 0;
        VDP_CTRL32 = CRAM_W(0);
        for (i = 0; i < 64; i++) VDP_DATA = palnow[i];
    }
    dma_vram(sprbuf, SPRTAB, nspr << 2);
    if (in_match) hero_poses();
    if (split) { vsel(0); map_stream(); vsel(1); }
    map_stream();
    scroll_set();
}

static void clear_planeA(void)
{
    u8 y;
    for (y = 0; y < 32; y++) clearA(y);
}

static u8 hud_dirty;

static void clear_band(void)
{
    u8 y;
    if (split) { hud_dirty = 1; return; }   /* split-screen menus live in the HUD */
    for (y = 5; y < 16; y++) clearA(y);
}

static u8 walkable(s16 x, s16 y)
{
    if (x < 0 || y < 0 || x >= WORLD || y >= WORLD) return 0;
    return walk_map[((u16)(y >> 4) << 6) + (x >> 4)];
}

/* ================================================================ game data */
enum { U_HERO, U_MELEE, U_RANGED, U_WOLF, U_OGRE, U_ROSH, U_TOWER, U_ANCIENT, U_RAX };
enum { PJ_SF, PJ_CREEP, PJ_TOWER, PJ_BULLET, PJ_ICE, PJ_FIRE, PJ_POISON, PJ_REQ, PJ_LFIRE, PJ_LROCK };  /* REQ on: lines */
enum { FX_RAZE, FX_SPARK, FX_POOF, FX_DENY, FX_GOLD, FX_RING, FX_HELIX, FX_DMG, FX_FIRE, FX_ICE, FX_BOLT };
enum { R_DD, R_HASTE, R_REGEN, R_BOUNTY };     /* runes */
enum { IT_BOOTS = 1, IT_BLADES = 2, IT_VIT = 4, IT_BLINK = 8, IT_BRACER = 16 };
#define NITEM 5
#define F_HERO 1
#define F_CREEP 2
#define F_BLD 4

/* hero slots: even = Radiant, odd = Dire (team = slot & 1), so i ^ 1 is an enemy hero; slots 2 and 3
   are used in 2v2 only. hk[] says which hero plays in each */
enum { K_SF, K_PUDGE, K_AXE, K_SNIPER, K_ZEUS, K_LINA, K_CM, K_DROW, K_VIPER, K_JUGG, NHERO };
#define K_GEN K_SNIPER     /* heroes from here on use the table-driven skills (skdef) */
#define NH 6                     /* hero slots: Radiant 0, 2, 4 and Dire 1, 3, 5 */
#define FIRST_BLD NH
#define NBLD 26                  /* 13 a side: 6 towers, the Ancient, 6 barracks (melee and ranged a lane) */
#define FIRST_CREEP (FIRST_BLD + NBLD)
#define ROSH (FIRST_CREEP + 42)   /* Roshan: neutral (team 2), in both teams' enemy lists */
#define NEUT (ROSH + 1)           /* jungle neutrals: 4 camps of 3 slots, neutral like Roshan */
#define NCAMP 4
#define NU (NEUT + NCAMP * 3)
#define NP 28
#define NFX 24
/* building slot inside a team: top T1, top T2, mid T1, mid T2, bot T1, bot T2, Ancient,
   then the barracks of the top, mid and bot lanes */
#define B_ANCIENT 6
#define B_RAX 7

typedef struct {
    s16 x, y, hp, hpmax;
    s8 tgt, killer;
    u8 on, type, team, face, cd, wind, stun, slow, aggro, imm, anim, slot, hit, lane, wp;
    s8 mvx, mvy, mtgt;  /* creeps: cached walking direction (x64) and what it points at */
    u8 mtick, nav;      /* nav: updates left to follow nav_map back to the lane */
    u8 taunt, hunger;   /* Berserker's Call frames left; Battle Hunger ticks (of 8 frames) left */
    u8 sup;             /* lane creeps: 1 = super, 2 = mega (the enemy barracks are down) */
} Unit;

typedef struct {
    s16 mana, manamax, hx, hy, hvx, hvy;
    u16 xp, gold, lasthits, denies, respawn, cd[5];
    u16 pad, pad_new;
    u16 earned, hdmg;   /* match stats: gold earned, damage dealt to the enemy hero */
    u8 towers;
    u8 lvl, souls, heap, rot, items, kills, deaths, bot, six;
    u8 sk[4], pts;      /* learned levels: three basic skills and the ultimate; unspent points */
    u8 call_t, helix_cd;
    u8 hold_k, hold_t;  /* a skill key held down to learn that skill (255 = none), frames held */
    u8 stat, at[3], rate;   /* points in +1 to all attributes; STR, AGI, INT now; attack frames */
    s16 arm, amul;      /* armor in tenths; what an attack on the hero keeps, of 256 */
    u8 buf_t, heal_t, omni_n;   /* Blade Fury and Healing Ward frames left; Omnislash jumps left */
    u8 chan_t, chan_kind, hook_st, hook_t, ai_st, cast_lock, ai_lane, ai_t;
    s8 chan_tgt, hook_tgt;
    u8 rune, rune_t;    /* the power rune in effect and its seconds left */
} Hero;

typedef struct { s8 mvx, mvy, tgt; u8 cast, aim, face; s16 ax, ay; } Cmd;
typedef struct { s16 x, y, vx, vy, dmg; s8 tgt, src; u8 on, kind, t, life, st, sl, ph; } Proj;  /* st/sl: stun, slow on hit; ph: an attack */
typedef struct { s16 x, y; u16 val; u8 on, kind, t; } Fx;

static Unit un[NU];
static Hero hr[NH];
static u8 nh = 2;                  /* heroes in play: 2 (1v1), 4 (2v2) or 6 (3v3) */
static Proj pj[NP];
static Fx fxs[NFX];
static u8 hk[NH] = { K_SF, K_PUDGE, K_AXE, K_SF, K_LINA, K_CM };
static u8 port_of[NH] = { 0, 1, 2, 2, 2, 2 };   /* controller port driving each hero */
static u8 versus;   /* two players on two pads, split screen */
static u8 me, view, winner, msg_t, first_blood, waves, shop_open, shop_sel, paused, board, learn_open;
static u16 game_t, wave_t, game_sec;   /* game_t wraps after 18 minutes, game_sec does not */
/* the game logic steps at 30 Hz: game_t still counts 60 Hz frames (+DT a step), timers are kept in
   frames and count down by DT, speeds are per step */
#define DT 2
static u16 pad_acc[2];
static u8 stc, half, bot_ph;        /* logic steps, for staggering work; which half of a step this frame is;
                                       3v3: the bot that thinks this step */
static u8 sec_f;

static const s8 dvx[8] = { 64, 45, 0, -45, -64, -45, 0, 45 };
static const s8 dvy[8] = { 0, 45, 64, 45, 0, -45, -64, -45 };
static const u8 face_of[9] = { 5, 6, 7, 4, 255, 0, 3, 2, 1 };
/* Radiant buildings; the Dire ones are the same rotated by 180 degrees */
static const s16 bld_x[13] = { 104, 104, 432, 296, 688, 384, 148, 76, 132, 200, 234, 240, 240 };
static const s16 bld_y[13] = { 336, 640, 592, 728, 920, 920, 872, 790, 790, 790, 824, 892, 948 };
/* the jungle camps: Radiant wolves, Radiant ogres, then the Dire ones (rotated) */
static const s16 camp_x[NCAMP] = { 232, 536, 792, 488 };
static const s16 camp_y[NCAMP] = { 552, 776, 472, 248 };
static const s16 fountain_x[2] = { 64, 960 };      /* by team: index with slot & 1 */
static const s16 fountain_y[2] = { 960, 64 };
static const s8 slot_dx[4] = { -9, 9, 0, 0 };
static const s8 slot_dy[4] = { 0, 0, -9, 9 };
static const u16 raze_dist[3] = { 24, 56, 88 };
static const u16 item_price[NITEM] = { 500, 450, 1000, 2250, 400 };
static const u8 bot_buy[NITEM] = { 4, 0, 1, 2, 3 };    /* bots start with a Bracer */

/* lane waypoints (lane_top/mid/bot in gfx.h) from the Radiant Ancient to the Dire Ancient */
static const s16 *const lane_pts[3] = { lane_top, lane_mid, lane_bot };
static const u8 lane_len[3] = { 6, 4, 6 };

/* ------------------------------------------------------------- helpers */
/* 32/16 signed divide with the 68000 DIVS instruction (the quotient must fit 16 bits) */
static inline s16 divs(s32 a, s16 b)
{
    __asm__ ("divs.w %2, %0" : "=d"(a) : "0"(a), "d"(b) : "cc");
    return (s16)a;
}

/* 16x16 -> 32 signed multiply with MULS, where gcc cannot see both factors are 16-bit */
static inline s32 muls(s16 a, s16 b)
{
    s32 r = a;
    __asm__ ("muls.w %2, %0" : "=d"(r) : "0"(r), "d"(b) : "cc");
    return r;
}

static inline s16 dist(s16 dx, s16 dy)
{
    dx = ABS(dx);
    dy = ABS(dy);
    return dx > dy ? dx + (dy >> 2) + (dy >> 3) : dy + (dx >> 2) + (dx >> 3);
}

static s16 udist(u8 a, u8 b) { return dist(PX(un[a].x) - PX(un[b].x), PX(un[a].y) - PX(un[b].y)); }

static u8 face_dir(s16 dx, s16 dy)
{
    s16 ax = ABS(dx), ay = ABS(dy);
    s8 mx = 0, my = 0;
    if (ax > (ay >> 1)) mx = dx > 0 ? 1 : -1;
    if (ay > (ax >> 1)) my = dy > 0 ? 1 : -1;
    if (!mx && !my) mx = 1;
    return face_of[(my + 1) * 3 + mx + 1];
}

static void face_to(u8 i, u8 t)
{
    un[i].face = face_dir(PX(un[t].x) - PX(un[i].x), PX(un[t].y) - PX(un[i].y));
}

static const u8 slot_tab[NBLD] = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 };
static u8 bld_slot(u8 t) { return slot_tab[t - FIRST_BLD]; }
/* the Dire buildings are the Radiant ones turned by 180 degrees, so their top slots stand on the bot lane */
static u8 slot_lane(u8 team, u8 l) { return team ? 2 - l : l; }
static u8 bld_lane(u8 t) { return slot_lane(un[t].team, (bld_slot(t) >= B_RAX ? bld_slot(t) - B_RAX : bld_slot(t)) >> 1); }

static u8 protected_bld(u8 t)
{
    u8 base, k;
    if (t < FIRST_BLD || t >= FIRST_CREEP) return 0;
    base = t - bld_slot(t);
    k = bld_slot(t);
    if (k == B_ANCIENT) return un[base + 1].on && un[base + 3].on && un[base + 5].on;
    if (k >= B_RAX) return un[base + ((k - B_RAX) | 1)].on;      /* barracks: while the lane's T2 stands */
    return (k & 1) && un[t - 1].on;
}

static u8 attackable(s8 t, u8 team)
{
    return t >= 0 && un[(u8)t].on && un[(u8)t].team != team && un[(u8)t].hp > 0 && !protected_bld(t);
}

/* a hero may last-hit its own creep once it is below half health */
static u8 deniable(s8 t, u8 team)
{
    return t >= FIRST_CREEP && un[(u8)t].on && un[(u8)t].team == team && un[(u8)t].hp > 0 &&
           un[(u8)t].hp * 2 < un[(u8)t].hpmax;
}

/* per-frame lists of living units by team, with cached pixel positions */
static u8 tlist[2][NU], tcount[2], ukind[NU];
static s16 cpx[NU], cpy[NU];

static void build_lists(void)
{
    u8 t;
    tcount[0] = tcount[1] = 0;
    for (t = 0; t < NU; t++)
        if (un[t].on) {
            u8 k = un[t].team;
            cpx[t] = PX(un[t].x);
            cpy[t] = PX(un[t].y);
            ukind[t] = t < FIRST_BLD ? 0 : (t < FIRST_CREEP ? 2 : 1);
            if (k > 1) {                    /* Roshan is everybody's enemy */
                tlist[0][tcount[0]++] = t;
                tlist[1][tcount[1]++] = t;
            } else tlist[k][tcount[k]++] = t;
        }
}

/* sight: by day every hero is in plain view; as night falls a team sees an enemy hero only within
   NIGHT_R px (at full night) of one of its own units. seen[team] has a bit per hero slot; the
   neutrals (team 2) see everything */
#define NIGHT_R 128
static u8 seen[3] = { 0x3F, 0x3F, 0x3F };
#define SEEN(team, h) ((seen[team] >> (h)) & 1)

static void vision_update(void)
{
    s16 r = NIGHT_R + muls(8 - dn_lvl, 40);
    u8 team;
    if (!dn_lvl) { seen[0] = seen[1] = 0x3F; return; }
    for (team = 0; team < 2; team++) {
        u8 want = 0, got = 0, h, n = tcount[team];
        const u8 *l = tlist[team];
        for (h = team ^ 1; h < nh; h += 2)
            if (un[h].on) want |= 1 << h;
        while (n-- && got != want) {
            u8 m = *l++;
            if (un[m].team != team) continue;       /* Roshan and the camps are in both lists */
            for (h = team ^ 1; h < nh; h += 2) {
                s16 dx, dy;
                if (!((want & ~got) >> h & 1)) continue;
                dx = cpx[h] - cpx[m];
                dy = cpy[h] - cpy[m];
                if (dx < r && dx > -r && dy < r && dy > -r && dist(dx, dy) < r) got |= 1 << h;
            }
        }
        seen[team] = got | (0x3F & ~want);      /* own heroes, and the dead, count as seen */
    }
}

/* nearest enemies of unit i in one pass: best[0] = hero, best[1] = creep, best[2] = building,
 * each within r[k]; flags select which kinds to look for (F_HERO, F_CREEP, F_BLD) */
static void scan(u8 i, const s16 *r, u8 flags, s8 *best)
{
    const u8 *l = tlist[un[i].team ^ 1];
    u8 n = tcount[un[i].team ^ 1], k;
    s16 x = PX(un[i].x), y = PX(un[i].y), bd[3], lim = 0;
    for (k = 0; k < 3; k++) {
        best[k] = -1;
        bd[k] = r[k] + 1;
        if (((flags >> k) & 1) && r[k] + 16 > lim) lim = r[k] + 16;
    }
    while (n--) {
        u8 t = *l++, kind;
        s16 dx = cpx[t] - x, dy, d;
        if (dx > lim || dx < -lim) continue;
        dy = cpy[t] - y;
        if (dy > lim || dy < -lim) continue;
        kind = ukind[t];
        if (!((flags >> kind) & 1) || !un[t].on) continue;
        if (!kind && !SEEN(un[i].team, t)) continue;    /* a hero out in the dark */
        d = dist(dx, dy);
        if (kind == 2) {
            if (protected_bld(t)) continue;
            d -= 12;
        }
        if (d < bd[kind]) { bd[kind] = d; best[kind] = t; }
    }
}

static s8 nearest(u8 i, s16 radius, u8 flags)
{
    s16 r[3];
    s8 b[3], best = -1;
    s16 bd = 32767;
    u8 k;
    r[0] = r[1] = r[2] = radius;
    scan(i, r, flags, b);
    for (k = 0; k < 3; k++)
        if (b[k] >= 0) {
            s16 d = udist(i, b[k]) - (k == 2 ? 12 : 0);
            if (d < bd) { bd = d; best = b[k]; }
        }
    return best;
}

static s8 aggro_hero(u8 i, s16 r)
{
    u8 t;
    for (t = 0; t < nh; t++)
        if (un[t].aggro && attackable(t, un[i].team) && SEEN(un[i].team, t) && udist(i, t) < r)
            return t;
    return -1;
}

static void clamp_pos(Unit *v)
{
    if (v->x < FX(16)) v->x = FX(16);
    if (v->x > FX(WORLD - 16)) v->x = FX(WORLD - 16);
    if (v->y < FX(16)) v->y = FX(16);
    if (v->y > FX(WORLD - 16)) v->y = FX(WORLD - 16);
}

/* standing towers are solid discs: a step that ends inside one is put back on the rim and turned
   along it, so units walk round instead of through. walk_map marks the cells round tower k with 2 + k. */
#define BLD_R FX(13)
static void bld_slide(Unit *v, s16 mx, s16 my)
{
    u8 k = walkable(PX(v->x), PX(v->y));
    Unit *b;
    s16 dx, dy, d, tx, ty, sp;
    if (k < 2) return;
    b = &un[FIRST_BLD + k - 2];
    if (!b->on) return;
    dx = v->x - b->x;
    dy = v->y - b->y;
    d = dist(dx, dy);
    if (d >= BLD_R) return;
    if (d < 8) { dx = 0; dy = BLD_R; d = BLD_R; }
    tx = -dy;
    ty = dx;
    if (muls(mx, tx) + muls(my, ty) < 0) { tx = dy; ty = -dx; }
    sp = dist(mx, my);
    v->x = b->x + divs(muls(dx, BLD_R), d) + divs(muls(tx, sp), d);
    v->y = b->y + divs(muls(dy, BLD_R), d) + divs(muls(ty, sp), d);
}

/* move by (mx, my) in 1/16 px, sliding along trees and round towers */
static void step(Unit *v, s16 mx, s16 my)
{
    s16 nx = v->x + mx, ny = v->y + my;
    if (walkable(PX(nx), PX(ny))) { v->x = nx; v->y = ny; }
    else if (mx && walkable(PX(nx), PX(v->y))) v->x = nx;
    else if (my && walkable(PX(v->x), PX(ny))) v->y = ny;
    bld_slide(v, mx, my);
    clamp_pos(v);
}

static void move_to(u8 i, s16 tx, s16 ty, s16 spd)
{
    Unit *v = &un[i];
    s16 dx = tx - PX(v->x), dy = ty - PX(v->y), d = dist(dx, dy);
    if (d < 2) return;
    if (v->slow) spd = (spd * 11) >> 4;
    step(v, divs((s32)dx * spd, d), divs((s32)dy * spd, d));
    v->face = face_dir(dx, dy);
    v->anim++;
}

static void fx_val(s16 x, s16 y, u8 kind, u16 val)
{
    u8 i;
    for (i = 0; i < NFX; i++)
        if (!fxs[i].on) {
            fxs[i].on = 1; fxs[i].x = x; fxs[i].y = y; fxs[i].kind = kind; fxs[i].t = 0; fxs[i].val = val;
            return;
        }
}

static void fx_add(s16 x, s16 y, u8 kind) { fx_val(x, y, kind, 0); }

static void msg(const char *s, u8 t)
{
    if (split) {            /* the message row above the HUDs */
        clearW(23);
        textW((40 - slen(s)) >> 1, 23, s);
        msg_t = t;
        return;
    }
    clearA(6);
    textA_c(6, s);
    msg_t = t;
}

/* ------------------------------------------------------------- hero stats */
/* skills: SF = Shadowraze, Necromastery, Presence, Requiem; Pudge = Hook, Rot, Flesh Heap, Dismember;
   Axe = Berserker's Call, Battle Hunger, Counter Helix, Culling Blade; the rest are in skdef */
static const char *const hero_name[NHERO] = { "SHADOW FIEND", "PUDGE", "AXE", "SNIPER", "ZEUS", "LINA",
                                              "CRYSTAL MAIDEN", "DROW RANGER", "VIPER", "JUGGERNAUT" };
static const char *const hero_short[NHERO] = { "SF   ", "PUDGE", "AXE  ", "SNIPR", "ZEUS ", "LINA ",
                                               "CM   ", "DROW ", "VIPER", "JUGG " };
/* base values and per-level growth */
static const s16 st_hp[NHERO] = { 460, 600, 620, 530, 450, 440, 470, 450, 500, 580 };
static const s16 st_mp[NHERO] = { 230, 190, 180, 220, 300, 280, 300, 220, 230, 200 };
static const u8 st_dmg[NHERO] = { 30, 44, 42, 37, 28, 32, 28, 30, 34, 40 };
/* Dota attributes: STR, AGI, INT at level 1 and their gain a level in tenths, the primary one.
   Above level 1 each STR is +20 HP, each INT +12 mana, each AGI +1% attack speed and each
   point of the primary attribute +1 damage; the st_ tables are the level 1 values */
static const u8 at_base[NHERO][3] = { { 19, 25, 16 }, { 25, 13, 16 }, { 25, 18, 18 }, { 19, 27, 15 }, { 21, 11, 23 },
                                      { 20, 21, 28 }, { 17, 16, 20 }, { 16, 24, 15 }, { 21, 21, 17 }, { 20, 32, 14 } };
static const u8 at_gain[NHERO][3] = { { 27, 36, 22 }, { 30, 14, 18 }, { 27, 17, 16 }, { 20, 32, 26 }, { 21, 12, 33 },
                                      { 24, 24, 40 }, { 22, 18, 33 }, { 19, 28, 14 }, { 24, 29, 20 }, { 20, 28, 14 } };
/* Dota base armor; each AGI adds 1/6 armor, and armor cuts attack damage by 6a / (100 + 6a) */
static const s8 st_arm[NHERO] = { 0, 0, 0, 0, 1, 0, 0, 0, -2, 0 };
enum { A_STR, A_AGI, A_INT };
static const u8 at_prim[NHERO] = { A_AGI, A_STR, A_STR, A_AGI, A_INT, A_INT, A_INT, A_AGI, A_AGI, A_AGI };
#define MAX_LVL 30
static const u8 st_rng[NHERO] = { 80, 20, 20, 96, 72, 76, 70, 90, 80, 20 };
static const u8 st_spd[NHERO] = { 21, 19, 22, 20, 20, 21, 19, 21, 21, 23 };
static const u8 st_rate[NHERO] = { 50, 56, 54, 52, 56, 54, 58, 52, 52, 50 };
/* the palette line each hero is drawn in: Radiant's (green 9-11) or Dire's (orange-red 9-11) */
static const u8 hero_pal[NHERO] = { 2, 2, 3, 2, 2, 3, 2, 2, 2, 3 };
static const u8 st_pj[NHERO] = { PJ_SF, 0, 0, PJ_BULLET, PJ_ICE, PJ_FIRE, PJ_ICE, PJ_ICE, PJ_POISON, 0 };

/* table-driven skills. cd is in units of 16 frames; dmg = base + per * level; for SK_LINE range is
   the flight time in frames (3 px each) and rad the hit radius; pj = a homing projectile for SK_NUKE */
enum { SK_PASSIVE, SK_NUKE, SK_AREA, SK_LINE, SK_GLOBAL, SK_CHAN, SK_BUFF, SK_HEAL, SK_DRAIN, SK_OMNI };
typedef struct { u8 kind, mana, cd, range, rad, base, per, stun, slow, fx, pj; } SkDef;
static const SkDef skdef[NHERO - K_GEN][4] = {
    { { SK_AREA, 70, 45, 90, 30, 50, 40, 0, 120, FX_FIRE, 0 }, { SK_PASSIVE }, { SK_PASSIVE },      /* Sniper */
      { SK_NUKE, 140, 64, 240, 0, 200, 100, 24, 0, FX_SPARK, PJ_BULLET } },
    { { SK_NUKE, 80, 22, 90, 40, 30, 20, 0, 0, FX_SPARK, 0 }, { SK_NUKE, 90, 26, 110, 0, 50, 50, 14, 0, FX_BOLT, 0 },
      { SK_PASSIVE }, { SK_GLOBAL, 200, 150, 0, 0, 120, 60, 0, 0, FX_BOLT, 0 } },                    /* Zeus */
    { { SK_LINE, 90, 30, 40, 14, 50, 45, 0, 0, FX_FIRE, PJ_LFIRE }, { SK_AREA, 100, 30, 70, 26, 50, 40, 30, 0, FX_FIRE, 0 },
      { SK_PASSIVE }, { SK_NUKE, 220, 131, 90, 0, 200, 120, 0, 0, FX_FIRE, 0 } },                    /* Lina */
    { { SK_AREA, 100, 34, 64, 30, 60, 45, 0, 150, FX_ICE, 0 }, { SK_NUKE, 100, 34, 80, 0, 40, 30, 40, 0, FX_ICE, 0 },
      { SK_PASSIVE }, { SK_CHAN, 200, 150, 0, 70, 18, 12, 0, 30, FX_ICE, 0 } },                      /* Crystal Maiden */
    { { SK_PASSIVE }, { SK_AREA, 90, 38, 40, 34, 20, 20, 24, 60, FX_POOF, 0 },
      { SK_AREA, 70, 30, 72, 36, 30, 25, 0, 90, FX_ICE, 0 }, { SK_PASSIVE } },                       /* Drow Ranger */
    { { SK_PASSIVE }, { SK_AREA, 70, 30, 70, 30, 40, 30, 0, 90, FX_POOF, 0 },
      { SK_PASSIVE }, { SK_NUKE, 125, 70, 90, 0, 150, 100, 0, 160, FX_POOF, 0 } },                    /* Viper */
    { { SK_BUFF, 100, 56, 0, 36, 12, 7, 0, 0, FX_HELIX, 0 }, { SK_HEAL, 80, 94, 0, 80, 4, 2, 0, 0, FX_SPARK, 0 },
      { SK_PASSIVE }, { SK_OMNI, 200, 131, 70, 0, 70, 0, 0, 0, FX_HELIX, 0 } },                      /* Juggernaut */
};
static const SkDef *sk_def(u8 i, u8 k) { return &skdef[hk[i] - K_GEN][k]; }
static u8 passive(u8 kind, u8 k)
{
    return kind < K_GEN ? kind != K_SF && k == 2 : skdef[kind - K_GEN][k].kind == SK_PASSIVE;
}

static u8 ult_lv(u8 i) { return hr[i].sk[3]; }
static u8 sk_max(u8 k) { return k == 3 ? 3 : 4; }
static u8 sk_need(u8 i, u8 k) { u8 l = hr[i].sk[k]; return k == 3 ? 6 + l * 6 : 1 + (l << 1); }   /* ultimate 6/12/18 */
static u8 souls_max(u8 i) { return hr[i].sk[1] * 5; }

static s16 times(s16 a, u8 n) { s16 r = 0; while (n--) r += a; return r; }   /* no __mulsi3 */

/* in a match each hero slot holds just the pose on screen (16 tiles), sent from ROM in vblank */
static u8 pose_want[NH], pose_have[NH];
static void hero_poses(void)
{
    u8 k;
    for (k = 0; k < nh; k++)
        if (pose_want[k] != pose_have[k]) {
            const u32 *src = hero_art + times(128, pose_want[k]);      /* 16 tiles of 8 longs a pose */
            u8 j;
            for (j = hk[k]; j; j--) src += 240 * 8;
            pose_have[k] = pose_want[k];
            if ((((u32)src) & 0x1FFFF) + 512 > 0x20000) {       /* DMA can't cross a 128K boundary */
                u16 w;
                VDP_CTRL32 = VRAM_W((T_HSLOT + times(16, k)) << 5);
                for (w = 128; w; w--) VDP_DATA32 = *src++;
            } else dma_vram(src, (T_HSLOT + times(16, k)) << 5, 256);
        }
}

/* k = 0-3 a skill, 4 = +1 to all attributes, which takes any point */
static u8 can_learn(u8 i, u8 k)
{
    Hero *H = &hr[i];
    return H->pts && (k == 4 || (H->sk[k] < sk_max(k) && H->lvl >= sk_need(i, k)));
}
/* the skill a key learns: Shadow Fiend's three Shadowraze keys all level Shadowraze */
static u8 key_skill(u8 i, u8 k) { return hk[i] == K_SF && k < 3 ? 0 : k; }
static void refresh_max(u8 i);

static u8 learn(u8 i, u8 k)
{
    Hero *H = &hr[i];
    if (!can_learn(i, k)) return 0;
    if (k == 4) { H->stat++; refresh_max(i); }
    else H->sk[k]++;
    H->pts--;
    hud_dirty = 1;
    return 1;
}

/* bots: the ultimate whenever possible, then the skills in order */
static void bot_learn(u8 i)
{
    static const u8 order[NHERO][4] = { { 3, 0, 1, 2 }, { 3, 0, 1, 2 }, { 3, 0, 2, 1 }, { 3, 0, 1, 2 }, { 3, 1, 0, 2 },
                                        { 3, 0, 1, 2 }, { 3, 0, 1, 2 }, { 3, 2, 0, 1 }, { 3, 0, 1, 2 }, { 3, 0, 2, 1 } };
    u8 k;
    while (hr[i].pts) {
        for (k = 0; k < 4; k++)
            if (learn(i, order[hk[i]][k])) break;
        if (k == 4) learn(i, 4);            /* nothing to level: attributes */
    }
}

static s16 calc_hpmax(u8 i)
{
    Hero *H = &hr[i];
    s16 v = st_hp[hk[i]] + times(20, H->at[A_STR] - at_base[hk[i]][A_STR]);
    if (hk[i] == K_PUDGE) v += times(20, H->heap);
    if (H->items & IT_VIT) v += 200;
    if (H->items & IT_BRACER) v += 80;
    return v;
}

static s16 calc_mpmax(u8 i) { return st_mp[hk[i]] + times(12, hr[i].at[A_INT] - at_base[hk[i]][A_INT]); }

static s16 atk_dmg(u8 i)
{
    Hero *H = &hr[i];
    u8 a = at_prim[hk[i]];
    s16 d = st_dmg[hk[i]] + H->at[a] - at_base[hk[i]][a];
    if (hk[i] == K_SF) d += H->souls << 1;
    if (hk[i] == K_DROW) d += (H->sk[0] << 1) + (H->sk[3] << 3);      /* Frost Arrows, Marksmanship */
    if (H->items & IT_BLADES) d += 10;
    if (H->items & IT_BRACER) d += 3;
    if (H->rune_t && H->rune == R_DD) d <<= 1;
    return d;
}

/* what an attack keeps, of 256: the hero's own armor, else Dota's 2 for melee creeps, 0 ranged,
   12 for a T1 tower, 16 for a T2 and 23 for the Ancient */
static s16 armor_cut(u8 t, s16 d)
{
    s16 m;
    switch (un[t].type) {
    case U_HERO: m = hr[t].amul; break;
    case U_MELEE: m = 228; break;
    case U_TOWER: m = bld_slot(t) & 1 ? 130 : 148; break;
    case U_ANCIENT: m = 107; break;
    case U_ROSH: m = 170; break;
    case U_RAX: m = 140; break;
    case U_OGRE: m = 200; break;
    default: return d;
    }
    return (s16)(muls(d, m) >> 8);
}

static s16 atk_range(u8 i)
{
    s16 r = st_rng[hk[i]];
    if (hk[i] == K_SNIPER) r += hr[i].sk[2] << 3;                       /* Take Aim */
    if (hk[i] == K_DROW) r += hr[i].sk[3] << 3;
    return r;
}

static s16 hero_spd(u8 i)
{
    s16 s = st_spd[hk[i]];
    if (hk[i] == K_LINA) s += hr[i].sk[2];                               /* Fiery Soul */
    if (hr[i].items & IT_BOOTS) s += 6;
    if (hr[i].rune_t && hr[i].rune == R_HASTE) s = 34;        /* Haste: the top speed */
    return s;
}

static u8 unit_rate(u8 i)
{
    switch (un[i].type) {
    case U_HERO: return hr[i].rate - (hk[i] == K_LINA ? hr[i].sk[2] << 2 : 0);
    case U_MELEE: return 60;
    case U_RANGED: return 66;
    case U_ROSH: return 70;
    case U_WOLF: return 50;
    case U_OGRE: return 76;
    default: return 56;
    }
}

static void refresh_max(u8 i)
{
    Hero *H = &hr[i];
    u8 a, kind = hk[i];
    s16 n, m;
    for (a = 0; a < 3; a++)         /* the base, the gain over the levels above 1, the + points */
        H->at[a] = at_base[kind][a] + divs(times(at_gain[kind][a], H->lvl - 1), 10) + H->stat;
    H->rate = divs(times(st_rate[kind], 100), 100 + H->at[A_AGI] - at_base[kind][A_AGI]);
    H->arm = st_arm[kind] * 10 + divs(muls(H->at[A_AGI], 10), 6);
    H->amul = H->arm >= 0 ? divs(256000, 1000 + muls(6, H->arm))          /* negative armor adds damage */
                          : divs(muls(1000 - muls(12, H->arm), 256), 1000 - muls(6, H->arm));
    n = calc_hpmax(i);
    m = calc_mpmax(i);
    un[i].hp += n - un[i].hpmax;
    un[i].hpmax = n;
    hr[i].mana += m - hr[i].manamax;
    hr[i].manamax = m;
    hud_dirty = 1;
}

static void give_xp(u8 i, u16 v)
{
    Hero *H = &hr[i];
    H->xp += v;
    while (H->lvl < MAX_LVL && H->xp >= 140 + H->lvl * 60) {
        H->xp -= 140 + H->lvl * 60;
        H->lvl++;
        H->pts++;
        refresh_max(i);
        if (H->bot) bot_learn(i);
        if (i == view) {
            sfx_play(SFX_PICKUP);
            if (!H->bot) msg(H->lvl == 6 ? "LEVEL 6! HOLD Y TO LEARN THE ULTIMATE" : "LEVEL UP! HOLD A SKILL KEY TO LEARN", 120);
        }
    }
    hud_dirty = 1;
}

/* ------------------------------------------------------------- damage */
static void kill_unit(u8 t, s8 src);
static void hud_part1(u8 part);
static void clock_text(char *b);
static void counter_helix(u8 i);

/* Roshan, the Aegis and the runes */
static u16 rosh_t;                 /* seconds until Roshan comes back; 0 while he lives */
static u8 rosh_calm, rosh_slam;    /* frames since he was last hit (to 255); slam cooldown */
static s8 aegis;                   /* the hero holding the Aegis of the Immortal, else -1 */
static u16 aegis_t;                /* its seconds left */
static u8 rune_on[4];              /* each spot's rune kind + 1, 0 = none */
static u8 power_t, bounty_t;       /* seconds to the next power rune, bounty runes */
/* the power runes sit in the river above and below mid, a bounty rune in each side's jungle */
static const s16 rune_x[4] = { 400, 624, 296, 728 };
static const s16 rune_y[4] = { 400, 624, 472, 552 };
static const u8 rune_secs[3] = { 45, 22, 30 };
static const char *const rune_name[4] = { ": DOUBLE DAMAGE", ": HASTE", ": REGENERATION", ": BOUNTY" };

static u8 rax_down[2];      /* each side's fallen barracks, bit = lane * 2 + (ranged) */
static s16 game_min(void) { return divs(game_sec, 60); }
static s16 rosh_dmg(void) { return 65 + times(3, game_min()); }
static const u8 neu_tab[NCAMP * 3] = { 0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3 };
static u8 neu_camp(u8 i) { return neu_tab[i - NEUT]; }

/* Dota-style kill streak announcements */
static u8 streak[NH];
static const char *const streak_msg[8] = { ": KILLING SPREE!", ": DOMINATING!", ": MEGA KILL!", ": UNSTOPPABLE!",
                                           ": WICKED SICK!", ": MONSTER KILL!", ": GODLIKE!", ": BEYOND GODLIKE!" };
static void announce(u8 kind, const char *m)
{
    char b[40];
    const char *n = hero_name[kind];
    u8 j = 0;
    while (*n) b[j++] = *n++;
    while (*m) b[j++] = *m++;
    b[j] = 0;
    msg(b, 150);
    sfx_play(SFX_ALARM);
}

/* a burst of smoke and sparks when a building falls */
static void debris(s16 x, s16 y, u8 r)
{
    u8 k;
    fx_add(x, y, FX_RAZE);
    for (k = 0; k < 6; k++) {
        u8 a = (u8)(k * 11 + (rnd() & 7));
        fx_add(x + ((sintab[(a + 16) & 63] * r) >> 6), y + ((sintab[a & 63] * r) >> 7), k & 1 ? FX_SPARK : FX_POOF);
    }
}

static void hurt(s8 src, u8 t, s16 dmg)
{
    Unit *v = &un[t];
    if (!v->on || v->hp <= 0 || protected_bld(t)) return;
    if (t < NH && hr[t].chan_t && hr[t].chan_kind == 4) return;     /* mid-Omnislash */
    if (src >= 0 && un[(u8)src].team == v->team && (src >= NH || !deniable(t, v->team))) return;
    {
        u8 e;
        for (e = v->team > 1 ? 0 : v->team ^ 1; e < nh; e += v->team > 1 ? 1 : 2)      /* the enemy heroes' slots */
            if (hk[e] == K_SF && un[e].on && udist(e, t) < 80) dmg += times(dmg >> 5, hr[e].sk[2]);  /* Presence */
    }
    if (t < NH && hk[t] == K_PUDGE) dmg -= times(dmg >> 5, hr[t].sk[2]);                         /* Flesh Heap */
    if (t < NH && hk[t] == K_AXE && hr[t].call_t) dmg -= dmg >> 2;                              /* Call armour */
    if (dmg < 1) dmg = 1;
    if (t < NH && src >= 0 && src < NH && hr[(u8)src].hdmg < 60000) hr[(u8)src].hdmg += dmg;
    v->hp -= dmg;
    v->hit = 4;
    /* damage numbers: hero duels, towers on heroes, and big spells */
    if (src >= 0 && ((t < NH && (src < NH || un[(u8)src].type >= U_WOLF)) || (src < NH && dmg >= 50)))
        fx_val(PX(v->x) + (rnd() & 7) - 4, PX(v->y) - (t < NH ? 30 : 18), FX_DMG, dmg);
    if (src >= 0) {
        v->killer = src;
        if (src < NH && t < NH) un[(u8)src].aggro = 120;
        if (t < NH && hr[t].rune == R_REGEN && (src < NH || un[(u8)src].type >= U_WOLF)) hr[t].rune_t = 0;
        if (t == ROSH) {                    /* Roshan turns on whoever hits him */
            rosh_calm = 0;
            if (v->tgt < 0) v->tgt = src;
        } else if (t >= NEUT) {             /* the whole camp turns on whoever hits one of it */
            u8 j = NEUT + times(neu_camp(t), 3), e = j + 3;
            for (; j < e; j++)
                if (un[j].on && un[j].tgt < 0) un[j].tgt = src;
        }
    }
    if (t == view && (vcount & 7) == 0) sfx_play(SFX_HIT);
    if (v->hp <= 0) { kill_unit(t, src); return; }
    if (t < NH && src >= 0 && hk[t] == K_AXE && hr[t].sk[2] && !hr[t].helix_cd && (rnd() & 3) == 0)
        counter_helix(t);
}

static void kill_unit(u8 t, s8 src)
{
    Unit *v = &un[t];
    u8 k, eteam = v->team > 1 ? (v->type == U_ROSH || src < 0 ? 3 : un[(u8)src].team) : v->team ^ 1, denied = src >= 0 && src < NH && un[(u8)src].team == v->team;
    u16 xpv = v->type == U_MELEE ? 45 : (v->type == U_RANGED ? 60 : v->type == U_WOLF ? 50 : v->type == U_OGRE ? 80 :
              (v->type == U_HERO ? 120 + hr[t].lvl * 25 : 140));
    if ((s8)t == aegis) {           /* the Aegis: back on its feet where it fell, at full health */
        Hero *H = &hr[t];
        aegis = -1;
        v->hp = v->hpmax;
        H->mana = H->manamax;
        v->stun = v->slow = v->taunt = v->hunger = 0;
        H->chan_t = 0;
        fx_val(PX(v->x), PX(v->y) - 10, FX_RING, 0);
        fx_add(PX(v->x), PX(v->y) - 8, FX_SPARK);
        announce(hk[t], ": REINCARNATED BY THE AEGIS");
        hud_dirty = 1;
        return;
    }
    v->hp = 0;
    v->on = 0;
    fx_add(PX(v->x), PX(v->y) - 8, FX_POOF);
    if (denied) xpv >>= 1;                      /* a denied creep gives the enemy half the experience */
    for (k = 0; k < nh; k++)
        if (un[k].on && un[k].team == eteam && udist(k, t) < 160)
            give_xp(k, xpv);
    switch (v->type) {
    case U_MELEE:
    case U_RANGED:
    case U_WOLF:
    case U_OGRE:
        if (src >= 0 && src < NH && un[(u8)src].team == eteam) {
            Hero *H = &hr[(u8)src];
            static const u8 bounty[4] = { 40, 52, 34, 62 };
            u8 g = bounty[v->type - U_MELEE] + (rnd() & 7);
            H->gold += g;
            H->earned += g;
            H->lasthits++;
            if (hk[(u8)src] == K_SF && H->souls < souls_max(src)) H->souls++;
            if (src == view || (versus && src < NH)) { sfx_play(SFX_SHOT); fx_val(PX(v->x), PX(v->y) - 20, FX_GOLD, g); }
        } else if (denied) {
            hr[(u8)src].denies++;
            fx_add(PX(v->x), PX(v->y) - 20, FX_DENY);
            if (src == view) sfx_play(SFX_SHOT);
        }
        break;
    case U_TOWER:
        for (k = 0; k < nh; k++)
            if (un[k].team == eteam) { hr[k].gold += 160; hr[k].earned += 160; }
        hr[eteam].towers++;      /* slots 0/1 hold the team totals */
        msg(v->team ? "DIRE TOWER DESTROYED" : "RADIANT TOWER DESTROYED", 120);
        debris(PX(v->x), PX(v->y) - 8, 12);
        sfx_play(SFX_BIGEXPL);
        shake = 20;
        break;
    case U_ROSH: {
        u8 team = src >= 0 ? un[(u8)src].team : 2, best = 255;
        s16 bd = 200;
        rosh_t = 480 + (rnd() & 127) + (rnd() & 63);     /* back in 8 to 11 minutes */
        debris(PX(v->x), PX(v->y) - 12, 16);
        sfx_play(SFX_BIGEXPL);
        shake = 20;
        if (team > 1) { msg("ROSHAN HAS FALLEN", 150); break; }
        for (k = team; k < nh; k += 2) {               /* the whole side: gold; those close: experience */
            hr[k].gold += 150;
            hr[k].earned += 150;
            if (un[k].on && udist(k, t) < 200) give_xp(k, 300);
        }
        if (src < NH) best = src;                      /* the Aegis to the killer, else the nearest ally */
        else
            for (k = team; k < nh; k += 2)
                if (un[k].on && udist(k, t) < bd) { bd = udist(k, t); best = k; }
        if (best < NH) {
            char b[40];
            const char *m = "ROSHAN SLAIN! AEGIS: ", *n = hero_name[hk[best]];
            u8 j = 0;
            while (*m) b[j++] = *m++;
            while (*n) b[j++] = *n++;
            b[j] = 0;
            aegis = best;
            aegis_t = 300;
            msg(b, 180);
        } else msg(team ? "THE DIRE HAVE SLAIN ROSHAN" : "THE RADIANT HAVE SLAIN ROSHAN", 150);
        sfx_play(SFX_ALARM);
        break;
    }
    case U_RAX: {
        u8 l = (bld_lane(t) << 1) | ((bld_slot(t) - B_RAX) & 1);
        for (k = 0; k < nh; k++)
            if (un[k].team == eteam) { hr[k].gold += 120; hr[k].earned += 120; }
        rax_down[v->team] |= 1 << l;
        msg(rax_down[v->team] == 0x3F ? (eteam ? "MEGA CREEPS FOR THE DIRE!" : "MEGA CREEPS FOR THE RADIANT!")
                                   : (v->team ? "DIRE BARRACKS DESTROYED" : "RADIANT BARRACKS DESTROYED"), 150);
        debris(PX(v->x), PX(v->y) - 8, 14);
        sfx_play(SFX_BIGEXPL);
        shake = 20;
        break;
    }
    case U_ANCIENT:
        winner = eteam + 1;
        debris(PX(v->x), PX(v->y) - 8, 24);
        sfx_play(SFX_BIGEXPL);
        shake = 40;
        break;
    default: {
        Hero *H = &hr[t];
        u8 e = src >= 0 && src < NH && un[(u8)src].team == eteam ? src : t ^ 1;   /* the killer, else an enemy */
        H->deaths++;
        H->respawn = 200 + H->lvl * 40;
        H->rune_t = 0;
        H->chan_t = 0;
        H->hook_st = 0;
        H->rot = 0;
        H->buf_t = H->heal_t = 0;
        if (hk[t] == K_SF) H->souls >>= 1;
        hr[e].gold += 200 + H->lvl * 12;
        hr[e].earned += 200 + H->lvl * 12;
        hr[e].kills++;
        if (hk[e] == K_SF) { hr[e].souls += 2; if (hr[e].souls > souls_max(e)) hr[e].souls = souls_max(e); }
        if (hk[e] == K_PUDGE && un[e].on && udist(e, t) < 160) {
            hr[e].heap++;
            refresh_max(e);
        }
        fx_val(PX(v->x), PX(v->y) - 10, FX_RING, 0);
        {
            u8 was = streak[t];
            streak[t] = 0;
            if (streak[e] < 255) streak[e]++;
            if (was >= 3) { announce(hk[e], ": SHUTDOWN!"); goto slain; }
            if (streak[e] >= 3) { announce(hk[e], streak_msg[streak[e] > 9 ? 7 : streak[e] - 3]); goto slain; }
        }
        if (!first_blood) { first_blood = 1; msg("FIRST BLOOD!", 120); sfx_play(SFX_ALARM); }
        else {
            char b[32];
            const char *n = hero_name[hk[t]], *m = " HAS BEEN SLAIN";
            u8 j = 0;
            while (*n) b[j++] = *n++;
            while (*m) b[j++] = *m++;
            b[j] = 0;
            msg(b, 120);
        }
    slain:
        sfx_play(SFX_DEATH);
        shake = 12;
    }
    }
    hud_dirty = 1;
}

/* ------------------------------------------------------------- projectiles */
static s16 aim_h(u8 t) { return un[t].type >= U_TOWER ? 4 : (un[t].type == U_ROSH ? 16 : 10); }

static Proj *proj_homing(u8 src, u8 tgt, u8 kind, s16 dmg, s16 spd)
{
    static Proj spare;      /* all slots busy: the shot is lost */
    u8 i;
    for (i = 0; i < NP; i++)
        if (!pj[i].on) {
            Proj *p = &pj[i];
            p->on = 1; p->kind = kind; p->src = src; p->tgt = tgt; p->dmg = dmg; p->vx = spd; p->t = 0;
            p->st = p->sl = 0;
            p->ph = 1;
            p->x = un[src].x;
            p->y = un[src].y - FX(un[src].type == U_TOWER ? 34 : (un[src].type > U_TOWER ? 6 : 12));   /* towers shoot from the orb */
            return p;
        }
    return &spare;
}

static void proj_line(u8 src, s16 vx, s16 vy, s16 dmg, u8 kind, u8 life, u8 st, u8 sl)
{
    u8 i;
    for (i = 0; i < NP; i++)
        if (!pj[i].on) {
            Proj *p = &pj[i];
            p->on = 1; p->kind = kind; p->src = src; p->tgt = -1; p->dmg = dmg; p->t = 0;
            p->life = life; p->st = st; p->sl = sl;
            p->x = un[src].x; p->y = un[src].y - FX(8); p->vx = vx; p->vy = vy;
            return;
        }
}

static void stun_slow(u8 t, u8 st, u8 sl)
{
    if (st > un[t].stun) un[t].stun = st;
    if (sl > un[t].slow) un[t].slow = sl;
}

static void update_projectiles(void)
{
    u8 i, t;
    for (i = 0; i < NP; i++) {
        Proj *p = &pj[i];
        if (!p->on) continue;
        if (p->kind >= PJ_REQ) {
            p->x += p->vx * DT;
            p->y += p->vy * DT;
            if ((p->t += DT) > p->life) { p->on = 0; continue; }
            if (p->kind == PJ_LROCK && (p->t & 7) == 0) fx_add(PX(p->x), PX(p->y) + 4, FX_POOF);
            {
                u8 team = un[(u8)p->src].team, n = tcount[team ^ 1];
                const u8 *l = tlist[team ^ 1];
                s16 px = PX(p->x), py = PX(p->y) + 8;
                while (n--) {               /* the enemies, from the lists of this step */
                    Unit *v;
                    s16 dx, dy;
                    t = *l++;
                    dx = cpx[t] - px;
                    dy = cpy[t] - py;
                    if (dx > 12 || dx < -12 || dy > 12 || dy < -12 || ukind[t] == 2) continue;
                    v = &un[t];
                    if (v->imm || !attackable(t, team)) continue;
                    if (dist(dx, dy) < 11) {
                        v->imm = 12;
                        stun_slow(t, p->st, p->sl);
                        hurt(p->src, t, p->dmg);
                    }
                }
            }
        } else {
            s16 dx, dy, d;
            if (p->tgt < 0 || !un[(u8)p->tgt].on) { p->on = 0; continue; }
            dx = un[(u8)p->tgt].x - p->x;
            dy = un[(u8)p->tgt].y - FX(aim_h(p->tgt)) - p->y;
            d = dist(PX(dx), PX(dy));
            if (d <= PX(p->vx * DT) + 3) {
                if (un[(u8)p->tgt].type < U_TOWER) stun_slow(p->tgt, p->st, p->sl);
                hurt(p->src, p->tgt, p->ph ? armor_cut(p->tgt, p->dmg) : p->dmg);
                fx_add(PX(p->x), PX(p->y), FX_SPARK);
                p->on = 0;
            } else {
                p->x += divs((s32)dx * p->vx, d << 3);      /* d << 4 at one frame a step */
                p->y += divs((s32)dy * p->vx, d << 3);
            }
        }
    }
}

/* ------------------------------------------------------------- generic attack */
static void deliver(u8 i, u8 t)
{
    switch (un[i].type) {
    case U_MELEE: hurt(i, t, armor_cut(t, (11 + waves) + (((11 + waves) * un[i].sup) >> 1))); break;
    case U_RANGED: proj_homing(i, t, PJ_CREEP, (15 + waves) + (((15 + waves) * un[i].sup) >> 1), 48); break;
    case U_WOLF: hurt(i, t, armor_cut(t, 18 + game_min())); break;
    case U_OGRE:
        hurt(i, t, armor_cut(t, 30 + times(2, game_min())));
        if ((rnd() & 7) == 0 && un[t].on) stun_slow(t, 0, 40);         /* a club to the knees */
        break;
    case U_TOWER: proj_homing(i, t, PJ_TOWER, 62, 80); break;
    case U_ROSH:
        hurt(i, t, armor_cut(t, rosh_dmg()));
        if ((rnd() & 3) == 0 && un[t].on) stun_slow(t, 24, 0);      /* Bash */
        break;
    default: {
        s16 d = atk_dmg(i);
        u8 st = 0, sl = 0, l = hr[i].sk[2];
        if (hk[i] == K_SNIPER && hr[i].sk[1] && (rnd() & 3) == 0) {            /* Headshot */
            d += 10 + times(15, hr[i].sk[1]);
            st = 8;
        }
        if (hk[i] == K_DROW && hr[i].sk[0]) sl = 40;                            /* Frost Arrows */
        if (hk[i] == K_VIPER && hr[i].sk[0]) {                                  /* Poison Attack */
            d += hr[i].sk[0] << 2;
            sl = 24 + (hr[i].sk[0] << 3);
        }
        if (hk[i] == K_JUGG && l && (rnd() & 7) < l) {                          /* Blade Dance */
            d <<= 1;
        }
        if (st_pj[hk[i]]) {
            Proj *p = proj_homing(i, t, st_pj[hk[i]], d, 64);
            p->st = st;
            p->sl = sl;
        } else hurt(i, t, armor_cut(t, d));
    }
    }
    if (t < NH && hk[t] == K_VIPER && hr[t].sk[2] && un[i].type < U_TOWER) {     /* Corrosive Skin */
        stun_slow(i, 0, 30);
        hurt(t, i, times(4, hr[t].sk[2]));
    }
}

static void unit_attack(u8 i, u8 t)
{
    Unit *v = &un[i];
    if (v->wind) {
        if (--v->wind == 0 && (attackable(t, v->team) || (i < NH && deniable(t, v->team)))) deliver(i, t);
        return;
    }
    if (!v->cd) {
        v->wind = 4;            /* steps: 8 frames for heroes and towers; creeps tick less often */
        v->cd = unit_rate(i);
    }
}

/* ------------------------------------------------------------- creeps & buildings */
static s16 lane_x(u8 lane, u8 wp) { return lane_pts[lane][wp << 1]; }
static s16 lane_y(u8 lane, u8 wp) { return lane_pts[lane][(wp << 1) + 1]; }


static void spawn_creep(u8 team, u8 type, u8 lane, u8 slot)
{
    u8 i, w;
    Unit *c;
    for (i = FIRST_CREEP; i < ROSH; i++)
        if (!un[i].on) break;
    if (i == ROSH) return;
    c = &un[i];
    memset(c, 0, sizeof(Unit));
    c->on = 1; c->type = type; c->team = team; c->slot = slot; c->tgt = -1; c->killer = -1;
    c->lane = lane;
    w = team ? lane_len[lane] - 2 : 1;
    c->wp = team ? w - 1 : w + 1;
    c->x = FX(lane_x(lane, w) + slot_dx[slot]);
    c->y = FX(lane_y(lane, w) + slot_dy[slot]);
    c->hpmax = c->hp = (type == U_MELEE ? 110 : 75) + waves * 3;
    c->sup = rax_down[team ^ 1] == 0x3F ? 2 : (rax_down[team ^ 1] >> ((lane << 1) | (type == U_RANGED))) & 1;   /* the enemy melee or ranged barracks of this lane */
    c->hpmax = c->hp += (c->hp >> 1) * c->sup;
    c->face = face_dir(lane_x(lane, c->wp) - lane_x(lane, w), lane_y(lane, c->wp) - lane_y(lane, w));
}

static void spawn_wave(void)
{
    u8 team, lane, k;
    for (team = 0; team < 2; team++)
        for (lane = 0; lane < 3; lane++) {
            for (k = 0; k < 2; k++) spawn_creep(team, U_MELEE, lane, k);
            spawn_creep(team, U_RANGED, lane, 2 + (lane & 1));
        }
    if (waves < 30) waves++;
}

#define DECN(v, n) ((v) = (v) > (n) ? (v) - (n) : 0)

/* walk toward (tx, ty); the direction is only recomputed every few updates.
   Returns 0 when trees stopped the creep dead. */
static u8 creep_walk(Unit *c, s8 tgt, s16 tx, s16 ty, s16 spd)
{
    s16 ox = c->x, oy = c->y;
    if (!c->mtick || c->mtgt != tgt) {
        s16 dx = tx - PX(c->x), dy = ty - PX(c->y), d = dist(dx, dy);
        if (d < 2) return 1;
        c->mvx = divs((s32)dx << 6, d);
        c->mvy = divs((s32)dy << 6, d);
        c->mtgt = tgt;
        c->mtick = d < 40 ? 1 : 4;     /* close in: re-aim every update */
        c->face = face_dir(dx, dy);
    }
    c->mtick--;
    if (c->slow) spd = (spd * 11) >> 4;
    step(c, (c->mvx * spd) >> 6, (c->mvy * spd) >> 6);
    c->anim++;
    return c->x != ox || c->y != oy;
}

/* nav_map nibble: the face index of the shortest walk around the trees to this creep's next
   waypoint, plus 8 when the creep is close enough to its lane to walk there straight */
static u8 nav_at(u8 lane, u8 wp, s16 x, s16 y)
{
    u16 cell = ((u16)(y >> 4) << 6) + (x >> 4);
    u8 v = nav_map[((u16)nav_idx[lane * 6 + wp] << 11) + (cell >> 1)];
    return cell & 1 ? v >> 4 : v & 15;
}

static u8 nav_dir(Unit *c) { return nav_at(c->lane, c->wp, PX(c->x), PX(c->y)); }

/* creeps update every n-th frame (2 near the camera, 8 elsewhere), moving and ticking n times as far */
static void creep_update(u8 i, u8 n)
{
    Unit *c = &un[i];
    s8 t = c->tgt;
    s16 rng = c->type == U_MELEE ? 16 : 70, spd = n * 12;
    DECN(c->hit, n);
    DECN(c->slow, n);
    DECN(c->imm, n);
    DECN(c->cd, n);
    DECN(c->taunt, n);
    if (c->stun) { DECN(c->stun, n); c->wind = 0; return; }
    if (c->nav) {           /* got stuck: follow nav_map back to the lane, ignoring enemies */
        u8 v = nav_dir(c), f = v & 7;
        if (c->nav > n) c->nav -= n;
        else if (v & 8) c->nav = 0;
        if (c->nav) {
            c->wind = 0;
            c->mtick = 0;
            c->face = f;
            step(c, (dvx[f] * spd) >> 6, (dvy[f] * spd) >> 6);
            c->anim++;
            return;
        }
    }
    if (c->taunt && attackable(t, c->team)) ;     /* taunted: stay on Axe */
    else if (((stc + i) & (t >= 0 ? 15 : 3)) == 0 || (t >= 0 && !attackable(t, c->team))) {
        static const s16 radii[3] = { 50, 70, 70 };
        s8 b[3], n = aggro_hero(i, 70);
        if (n < 0) {
            scan(i, radii, F_HERO | F_CREEP | F_BLD, b);
            n = b[1] >= 0 ? b[1] : (b[2] >= 0 ? b[2] : b[0]);
        }
        c->tgt = t = n;
    }
    if (t >= 0) {
        s16 d = udist(i, t) - (un[(u8)t].type >= U_ROSH ? 12 : 0);
        if (d <= rng) {
            face_to(i, t);
            unit_attack(i, t);
        } else {
            c->wind = 0;
            if (!creep_walk(c, t, PX(un[(u8)t].x), PX(un[(u8)t].y), spd)) { c->tgt = -1; c->nav = 64; }
        }
    } else {
        s16 tx = lane_x(c->lane, c->wp) + slot_dx[c->slot], ty = lane_y(c->lane, c->wp) + slot_dy[c->slot];
        c->wind = 0;
        if (dist(tx - PX(c->x), ty - PX(c->y)) < 10) {
            if (c->team == 0 && c->wp < lane_len[c->lane] - 1) c->wp++;
            if (c->team == 1 && c->wp > 0) c->wp--;
            c->mtick = 0;
        }
        if (!creep_walk(c, -1, tx, ty, spd)) c->nav = 64;
    }
}

static void building_update(u8 i)
{
    Unit *w = &un[i];
    s8 t = w->tgt, a;
    DECN(w->hit, 2);
    DECN(w->cd, 2);
    if (w->type == U_ANCIENT || w->type == U_RAX) return;
    if (t >= 0 && (!attackable(t, w->team) || udist(i, t) > 100)) t = -1;
    a = aggro_hero(i, 100);
    if (a >= 0) t = a;
    if (t < 0 && ((stc + i) & 3) == 0) {
        static const s16 radii[3] = { 100, 100, 0 };
        s8 b[3];
        scan(i, radii, F_HERO | F_CREEP, b);
        t = b[1] >= 0 ? b[1] : b[0];
    }
    w->tgt = t;
    if (t >= 0) unit_attack(i, t);
    else w->wind = 0;
}

/* ------------------------------------------------------------- Roshan and the runes */
static void rosh_spawn(void)
{
    Unit *R = &un[ROSH];
    memset(R, 0, sizeof(Unit));
    R->on = 1;
    R->type = U_ROSH;
    R->team = 2;
    R->x = FX(ROSH_X);
    R->y = FX(ROSH_Y);
    R->face = 1;
    R->tgt = R->killer = -1;
    R->hpmax = R->hp = 3000 + times(150, game_min());      /* he grows with the game */
    rosh_calm = 255;
}

/* Roshan stays in his pit: he fights whoever comes close or hits him, never strays more than
   80 px, slams the ground round him every few seconds and heals when left alone */
static void rosh_update(void)
{
    Unit *R = &un[ROSH];
    s8 t = R->tgt;
    s16 x = PX(R->x), y = PX(R->y);
    u8 k;
    if (!R->on) return;
    DECN(R->hit, DT);
    DECN(R->cd, DT);
    DECN(R->slow, DT);
    DECN(R->imm, DT);
    DECN(rosh_slam, DT);
    R->stun = R->taunt = 0;                 /* no stuns or taunts hold him */
    if (rosh_calm < 255) rosh_calm++;
    if (rosh_calm > 120 && (game_t & 15) == 0 && R->hp < R->hpmax) {
        R->hp += 6 + (R->hpmax >> 7);
        if (R->hp > R->hpmax) R->hp = R->hpmax;
    }
    if (t >= 0 && (!attackable(t, 2) || dist(PX(un[(u8)t].x) - ROSH_X, PX(un[(u8)t].y) - ROSH_Y) > 88)) t = -1;
    if (t < 0 && (stc & 3) == 0) {          /* any hero that walks up to him */
        s16 bd = 40;
        for (k = 0; k < nh; k++)
            if (attackable(k, 2) && udist(ROSH, k) < bd) { bd = udist(ROSH, k); t = k; }
    }
    R->tgt = t;
    if (t < 0) {
        R->wind = 0;
        if (dist(x - ROSH_X, y - ROSH_Y) > 3) move_to(ROSH, ROSH_X, ROSH_Y, 16 * DT);
        else R->face = 1;
        return;
    }
    if (udist(ROSH, t) > 30) {
        R->wind = 0;
        move_to(ROSH, PX(un[(u8)t].x), PX(un[(u8)t].y), 16 * DT);
        return;
    }
    face_to(ROSH, t);
    unit_attack(ROSH, t);
    if (!rosh_slam) {                       /* Slam: hurts and slows every hero close by */
        s16 d = rosh_dmg() >> 1;
        rosh_slam = 200;
        fx_val(x, y - 8, FX_RING, 0);
        for (k = 0; k < nh; k++)
            if (attackable(k, 2) && udist(ROSH, k) < 44) {
                stun_slow(k, 0, 90);
                hurt(ROSH, k, d);
            }
        if (dist(x - camx - 160, y - camy - 96) < 200) { sfx_play(SFX_BIGEXPL); shake = 6; }
    }
}

/* the jungle: wolves and ogres stand at their camp until somebody hits one; then the camp fights
   back, never strays more than 96 px, and walks home to heal. An emptied camp refills on the minute */
static const s8 camp_ox[3] = { 0, -17, 17 }, camp_oy[3] = { -6, 2, 2 };   /* round the fire */

static void camp_spawn(u8 k)
{
    u8 j, kind = k & 1 ? U_OGRE : U_WOLF;
    for (j = 0; j < (kind == U_OGRE ? 2 : 3); j++) {
        Unit *n = &un[NEUT + times(k, 3) + j];
        memset(n, 0, sizeof(Unit));
        n->on = 1;
        n->type = kind;
        n->team = 2;
        n->x = FX(camp_x[k] + camp_ox[j + (kind == U_OGRE)]);   /* two ogres flank the fire */
        n->y = FX(camp_y[k] + camp_oy[j + (kind == U_OGRE)]);
        n->face = 1;
        n->tgt = n->killer = -1;
        n->hpmax = n->hp = kind == U_OGRE ? 420 + times(14, game_min()) : 190 + times(7, game_min());
    }
}

static void camps_second(void)
{
    u8 k, j;
    if (game_sec % 60) return;
    for (k = 0; k < NCAMP; k++) {
        for (j = 0; j < 3; j++)
            if (un[NEUT + times(k, 3) + j].on) break;
        if (j == 3) camp_spawn(k);
    }
}

static void neutrals_update(void)
{
    u8 i;
    for (i = NEUT; i < NU; i++) {
        Unit *n = &un[i];
        s8 t = n->tgt;
        u8 k = neu_camp(i), j = i - NEUT - times(k, 3) + (n->type == U_OGRE);
        s16 x, y, hx = camp_x[k] + camp_ox[j], hy = camp_y[k] + camp_oy[j];
        if (!n->on) continue;
        DECN(n->hit, DT);
        DECN(n->cd, DT);
        DECN(n->slow, DT);
        DECN(n->imm, DT);
        DECN(n->taunt, DT);
        if (n->stun) { DECN(n->stun, DT); n->wind = 0; continue; }
        x = PX(n->x);
        y = PX(n->y);
        if (t >= 0 && (!attackable(t, 2) || dist(PX(un[(u8)t].x) - camp_x[k], PX(un[(u8)t].y) - camp_y[k]) > 96)) t = -1;
        n->tgt = t;
        if (t < 0) {
            n->wind = 0;
            if (dist(x - hx, y - hy) > 3) { move_to(i, hx, hy, (n->type == U_WOLF ? 14 : 11) * DT); n->anim++; }
            else {
                n->face = 1;
                if ((game_t & 15) == 0 && n->hp < n->hpmax) {    /* back home: heal up */
                    n->hp += 8 + (n->hpmax >> 5);
                    if (n->hp > n->hpmax) n->hp = n->hpmax;
                }
            }
            continue;
        }
        if (udist(i, t) > 18) {
            n->wind = 0;
            move_to(i, PX(un[(u8)t].x), PX(un[(u8)t].y), (n->type == U_WOLF ? 14 : 11) * DT);
            n->anim++;
            continue;
        }
        face_to(i, t);
        unit_attack(i, t);
    }
}

static void rune_spawn(u8 k, u8 kind)
{
    rune_on[k] = kind + 1;
}

static void rune_take(u8 i, u8 k)
{
    Hero *H = &hr[i];
    u8 kind = rune_on[k] - 1;
    rune_on[k] = 0;
    if (kind == R_BOUNTY) {                 /* gold for the whole side, experience for the taker */
        u16 g = 40 + times(4, game_min());
        u8 j;
        for (j = i & 1; j < nh; j += 2) { hr[j].gold += g; hr[j].earned += g; }
        give_xp(i, 40 + times(6, game_min()));
        fx_val(PX(un[i].x), PX(un[i].y) - 24, FX_GOLD, g);
    } else {
        H->rune = kind;
        H->rune_t = rune_secs[kind];
    }
    announce(hk[i], rune_name[kind]);
    hud_dirty = 1;
}

/* heroes pick up a rune by walking over it */
static void runes_update(void)
{
    u8 k, i;
    for (k = 0; k < 4; k++)
        if (rune_on[k])
            for (i = 0; i < nh; i++) {
                s16 dx = PX(un[i].x) - rune_x[k], dy = PX(un[i].y) - rune_y[k];
                if (un[i].on && dx < 12 && dx > -12 && dy < 12 && dy > -12) { rune_take(i, k); break; }
            }
}

static void rosh_plan(u8 team);

/* once a second: rune spawns and timers, Roshan's return, the Aegis running out, the bots' plans */
/* day and night take 5 minutes each; dusk and dawn take 8 seconds, a level a second */
#define DAY_S 300
#define NIGHT_S 300
static u16 dn_sec;

static void day_night(void)
{
    u8 want;
    if (++dn_sec == DAY_S + NIGHT_S) dn_sec = 0;
    if (dn_sec == DAY_S) msg("NIGHT FALLS", 120);
    else if (dn_sec == 0) msg("THE SUN RISES", 120);
    want = dn_sec >= DAY_S ? 8 : 0;
    if (dn_lvl == want) return;
    dn_lvl += want ? 1 : -1;
    pal_night();
}

static void world_second(void)
{
    u8 k;
    day_night();
    if (game_sec & 1) rosh_plan(game_sec & 2 ? 1 : 0);
    if (!--power_t) {                       /* every 2 minutes, at one of the two river spots */
        k = rnd() & 3;
        power_t = 120;
        rune_on[0] = rune_on[1] = 0;
        rune_spawn(rnd() & 1, k == 3 ? R_DD : k);
    }
    if (!--bounty_t) {
        bounty_t = 180;
        rune_spawn(2, R_BOUNTY);
        rune_spawn(3, R_BOUNTY);
    }
    for (k = 0; k < nh; k++) {
        Hero *H = &hr[k];
        if (H->rune_t) H->rune_t--;
    }
    if (rosh_t && !--rosh_t) rosh_spawn();
    camps_second();
    if (aegis >= 0 && !--aegis_t) {
        if (un[(u8)aegis].on) un[(u8)aegis].hp = un[(u8)aegis].hpmax;     /* it heals as it fades, as in Dota */
        aegis = -1;
        msg("THE AEGIS HAS EXPIRED", 120);
    }
}

/* ------------------------------------------------------------- abilities */
static void raze(u8 i, s16 d)
{
    Unit *U = &un[i];
    s16 cx = PX(U->x) + ((dvx[U->face] * d) >> 6);
    s16 cy = PX(U->y) - 4 + ((dvy[U->face] * d) >> 6);
    s16 dmg = 20 + times(70, hr[i].sk[0]);
    u8 t;
    fx_add(cx, cy, FX_RAZE);
    for (t = 0; t < NU; t++)
        if (un[t].type < U_TOWER && attackable(t, U->team) &&
            dist(PX(un[t].x) - cx, PX(un[t].y) - 4 - cy) < 24)
            hurt(i, t, dmg);
    sfx_play(SFX_EXPL);
}

static void requiem(u8 i)
{
    u8 n = 8 + (hr[i].souls >> 1), k;
    s16 dmg = 55 + 30 * ult_lv(i);
    if (n > 18) n = 18;
    for (k = 0; k < n; k++) {
        u8 a = (u8)divs((u16)k << 6, n);
        proj_line(i, (sintab[(a + 16) & 63] * 48) >> 6, (sintab[a & 63] * 48) >> 6, dmg, PJ_REQ, 52, 0, 90);
    }
    sfx_play(SFX_BIGEXPL);
    shake = 10;
}

static void counter_helix(u8 i)
{
    s16 dmg = 50 + times(25, hr[i].sk[2]);
    u8 t;
    hr[i].helix_cd = 18;
    fx_add(PX(un[i].x), PX(un[i].y) - 8, FX_HELIX);
    for (t = 0; t < NU; t++)
        if (un[t].type < U_TOWER && attackable(t, un[i].team) && udist(i, t) < 32)
            hurt(i, t, dmg);
}

/* Berserker's Call: nearby enemy creeps and heroes must attack Axe */
static void berserkers_call(u8 i)
{
    u8 t, dur = 96 + times(18, hr[i].sk[0]);
    hr[i].call_t = dur;
    fx_add(PX(un[i].x), PX(un[i].y) - 8, FX_RING);
    for (t = 0; t < NU; t++)
        if (un[t].type < U_TOWER && attackable(t, un[i].team) && udist(i, t) < 40) {
            un[t].taunt = dur;
            un[t].tgt = i;
            un[t].nav = 0;
            if (t < NH) { hr[t].chan_t = 0; un[t].wind = 0; }
        }
    sfx_play(SFX_BIGEXPL);
    shake = 6;
}

/* the enemy Axe of a team (Battle Hunger, Berserker's Call) */
static u8 axe_of(u8 team)
{
    u8 a;
    for (a = team ^ 1; a < nh; a += 2)
        if (hk[a] == K_AXE) return a;
    return team ^ 1;
}

static s8 hero_or_creep(u8 i, s16 r)
{
    s8 t = nearest(i, r, F_HERO);
    return t >= 0 ? t : nearest(i, r, F_CREEP);
}

static s16 cull_limit(u8 i) { return 150 + times(100, ult_lv(i)); }

/* Battle Hunger damage: every 8 frames, from the hero on the other side */
static void hunger_tick(void)
{
    u8 t;
    for (t = 0; t < NU; t++)
        if (un[t].on && un[t].hunger) {
            u8 src = axe_of(un[t].team);
            un[t].hunger--;
            if (un[t].slow < 10) un[t].slow = 10;
            hurt(src, t, 2 + hr[src].sk[1]);
        }
}

/* ---- table-driven skills (K_GEN and later) */
static s16 sk_dmg(u8 i, u8 k) { const SkDef *d = sk_def(i, k); return d->base + times(d->per, hr[i].sk[k]); }

/* a spell lands on t: stun and slow first, then the damage with Zeus's Static Field on top */
static void zap(u8 i, u8 t, s16 dmg, u8 st, u8 sl)
{
    if (un[t].type < U_TOWER) stun_slow(t, st, sl);
    if (hk[i] == K_ZEUS && hr[i].sk[2] && un[t].type < U_TOWER) dmg += times(un[t].hp >> 5, hr[i].sk[2]);
    if (dmg) hurt(i, t, dmg);
    else if (t < NH) un[i].aggro = 120;
}

static void area_at(u8 i, const SkDef *d, s16 dmg, s16 cx, s16 cy)
{
    u8 t;
    fx_add(cx, cy, d->fx);
    for (t = 0; t < NU; t++)
        if (un[t].type < U_TOWER && attackable(t, un[i].team) && dist(PX(un[t].x) - cx, PX(un[t].y) - 4 - cy) < d->rad)
            zap(i, t, dmg, d->stun, d->slow);
}

/* where an aimed skill goes: the bot's aim point, else the nearest enemy in reach, else straight ahead;
   returns the offset from the hero clamped to r */
static void aim_at(u8 i, Cmd *c, s16 r, s16 reach, s16 *ox, s16 *oy)
{
    Unit *U = &un[i];
    s16 dx, dy, d;
    s8 t;
    if (c && c->aim) { dx = c->ax - PX(U->x); dy = c->ay - PX(U->y); }
    else if ((t = hero_or_creep(i, reach)) >= 0) { dx = PX(un[(u8)t].x - U->x); dy = PX(un[(u8)t].y - U->y); }
    else { dx = (dvx[U->face] * r) >> 6; dy = (dvy[U->face] * r) >> 6; }
    d = dist(dx, dy);
    if (d > r) { dx = divs((s32)dx * r, d); dy = divs((s32)dy * r, d); }
    if (dx || dy) U->face = face_dir(dx, dy);
    *ox = dx;
    *oy = dy;
}

static void cast_gen(u8 i, u8 k, Cmd *c)
{
    Hero *H = &hr[i];
    Unit *U = &un[i];
    const SkDef *d = sk_def(i, k);
    s16 dmg = sk_dmg(i, k), ox, oy;
    s8 t = -1;
    u8 e;
    if (!H->sk[k] || d->kind == SK_PASSIVE || H->mana < d->mana) return;
    switch (d->kind) {
    case SK_NUKE:
    case SK_DRAIN:
    case SK_OMNI:
        t = d->pj ? nearest(i, d->range, F_HERO) : hero_or_creep(i, d->range);
        if (t < 0) return;
        face_to(i, t);
        break;
    }
    H->mana -= d->mana;
    H->cd[k] = (u16)d->cd << 4;
    H->cast_lock = 8;
    U->wind = 0;
    switch (d->kind) {
    case SK_NUKE:
        if (d->pj) {            /* Assassinate */
            Proj *p = proj_homing(i, t, d->pj, dmg, 96);
            p->st = d->stun;
            p->ph = 0;
            H->cast_lock = 20;
            sfx_play(SFX_SHOT);
            break;
        }
        fx_add(PX(un[(u8)t].x), PX(un[(u8)t].y) - (d->fx == FX_BOLT ? 0 : 10), d->fx);
        if (d->rad)             /* Arc Lightning jumps to up to 4 more enemies */
            for (e = 0, ox = 0; e < NU && ox < 4; e++)
                if (e != t && un[e].type < U_TOWER && attackable(e, U->team) && udist(e, t) < d->rad) {
                    fx_add(PX(un[e].x), PX(un[e].y) - 10, FX_SPARK);
                    zap(i, e, dmg - (dmg >> 2), 0, 0);
                    ox++;
                }
        zap(i, t, dmg, d->stun, d->slow);
        sfx_play(d->fx == FX_BOLT || d->rad ? SFX_HIT : SFX_EXPL);
        if (dmg >= 250) { shake = 8; sfx_play(SFX_BIGEXPL); }
        break;
    case SK_AREA:
        aim_at(i, c, d->range, d->range + d->rad, &ox, &oy);
        area_at(i, d, dmg, PX(U->x) + ox, PX(U->y) - 4 + oy);
        sfx_play(SFX_EXPL);
        break;
    case SK_LINE: {
        s16 r = times(3, d->range), n;
        aim_at(i, c, r, r, &ox, &oy);
        n = dist(ox, oy);
        if (n < 1) { ox = dvx[U->face]; oy = dvy[U->face]; n = 64; }
        proj_line(i, divs((s32)ox * 48, n), divs((s32)oy * 48, n), dmg, d->pj, d->range, d->stun, d->slow);
        sfx_play(SFX_EXPL);
        break;
    }
    case SK_GLOBAL:             /* Thundergod's Wrath: every enemy hero alive */
        for (e = U->team ^ 1; e < nh; e += 2)
            if (un[e].on) {
                fx_add(PX(un[e].x), PX(un[e].y), FX_BOLT);
                zap(i, e, dmg, 0, 0);
            }
        sfx_play(SFX_BIGEXPL);
        shake = 10;
        break;
    case SK_CHAN:               /* Freezing Field */
        H->chan_t = 96;
        H->chan_kind = 3;
        break;
    case SK_BUFF:               /* Blade Fury */
        H->buf_t = 80;
        sfx_play(SFX_HIT);
        break;
    case SK_HEAL:               /* Healing Ward */
        H->heal_t = 160;
        fx_add(PX(U->x), PX(U->y) - 20, FX_SPARK);
        sfx_play(SFX_PICKUP);
        break;
    case SK_DRAIN:              /* Mana Drain: hero mana comes over, creeps just take damage */
        if (t < NH) {
            s16 m = hr[(u8)t].mana < dmg ? hr[(u8)t].mana : dmg;
            hr[(u8)t].mana -= m;
            H->mana += m;
            if (H->mana > H->manamax) H->mana = H->manamax;
            zap(i, t, dmg >> 2, 0, 20);
        } else zap(i, t, dmg >> 1, 0, 20);
        fx_add(PX(un[(u8)t].x), PX(un[(u8)t].y) - 12, FX_SPARK);
        fx_add(PX(U->x), PX(U->y) - 12, FX_SPARK);
        sfx_play(SFX_PICKUP);
        break;
    case SK_OMNI:
        H->omni_n = 2 + (H->sk[3] << 1);
        H->chan_t = 8 + (H->omni_n << 3);
        H->chan_kind = 4;
        H->chan_tgt = t;
        sfx_play(SFX_START);
        break;
    }
    hud_dirty = 1;
}

/* the per-frame part of channels, buffs and auras of the table-driven heroes */
static void gen_update(u8 i)
{
    Hero *H = &hr[i];
    Unit *U = &un[i];
    u8 t;
    if (hk[i] == K_CM && H->sk[2] && (game_t & 63) == 0)        /* Arcane Aura: the team's mana */
        for (t = U->team; t < nh; t += 2)
            if (un[t].on && hr[t].mana < hr[t].manamax) hr[t].mana += H->sk[2];
    if (H->buf_t) {             /* Blade Fury: spinning, unstoppable */
        DECN(H->buf_t, DT);
        U->stun = 0;
        if ((H->buf_t & 15) == 0) fx_add(PX(U->x), PX(U->y) - 8, FX_HELIX);
        if ((H->buf_t & 7) == 0) {
            s16 dmg = sk_dmg(i, 0);
            for (t = 0; t < NU; t++)
                if (un[t].type < U_TOWER && attackable(t, U->team) && udist(i, t) < 34) hurt(i, t, dmg);
        }
    }
    if (H->heal_t) {            /* Healing Ward: Juggernaut and the allies near him */
        DECN(H->heal_t, DT);
        if ((H->heal_t & 7) == 0) {
            s16 v = sk_dmg(i, 1);
            for (t = U->team; t < nh; t += 2)
                if (un[t].on && udist(i, t) < 80) {
                    un[t].hp += v;
                    if (un[t].hp > un[t].hpmax) un[t].hp = un[t].hpmax;
                }
            if ((H->heal_t & 31) == 0) fx_add(PX(U->x), PX(U->y) - 22, FX_SPARK);
        }
    }
}

/* Freezing Field (kind 3) and Omnislash (kind 4); returns 1 while the hero is busy with it */
static u8 gen_channel(u8 i)
{
    Hero *H = &hr[i];
    Unit *U = &un[i];
    u8 t;
    if (H->chan_kind == 3) {
        if ((H->chan_t & 7) == 0) {
            const SkDef *d = sk_def(i, 3);
            u8 a = rnd() & 63;
            s16 r = 16 + (rnd() & 31), dmg = sk_dmg(i, 3);
            fx_add(PX(U->x) + ((sintab[(a + 16) & 63] * r) >> 6), PX(U->y) - 6 + ((sintab[a] * r) >> 7), FX_ICE);
            for (t = 0; t < NU; t++)
                if (un[t].type < U_TOWER && attackable(t, U->team) && udist(i, t) < d->rad) zap(i, t, dmg, 0, d->slow);
            if ((H->chan_t & 15) == 0) sfx_play(SFX_EXPL);
        }
        DECN(H->chan_t, DT);
        return 1;
    }
    /* Omnislash: a slash every 8 frames on the target, then on whatever enemy is near */
    U->stun = 0;
    if ((H->chan_t & 7) == 0) {
        s8 n = H->chan_tgt;
        if (n < 0 || !attackable(n, U->team) || udist(i, n) > 100) n = hero_or_creep(i, 100);
        if (n < 0 || !H->omni_n) { H->chan_t = 0; return 0; }
        H->chan_tgt = n;
        H->omni_n--;
        fx_add(PX(U->x), PX(U->y) - 8, FX_POOF);
        U->x = un[(u8)n].x + ((rnd() & 1) ? FX(10) : -FX(10));
        U->y = un[(u8)n].y + FX(2);
        clamp_pos(U);
        face_to(i, n);
        fx_add(PX(un[(u8)n].x), PX(un[(u8)n].y) - 8, FX_HELIX);
        hurt(i, n, sk_dmg(i, 3) + (atk_dmg(i) >> 1));
        sfx_play(SFX_HIT);
    }
    DECN(H->chan_t, DT);
    return 1;
}

static void cast(u8 i, u8 slot, Cmd *c)
{
    Hero *H = &hr[i];
    Unit *U = &un[i];
    if (H->cd[slot]) return;
    if (slot == 4) {
        s16 d;
        if (!(H->items & IT_BLINK)) return;
        fx_add(PX(U->x), PX(U->y) - 8, FX_POOF);
        for (d = 120; d > 0; d -= 8) {      /* furthest walkable spot along the facing */
            s16 nx = PX(U->x) + ((dvx[U->face] * d) >> 6), ny = PX(U->y) + ((dvy[U->face] * d) >> 6);
            if (nx > 16 && ny > 16 && nx < WORLD - 16 && ny < WORLD - 16 && walkable(nx, ny)) {
                U->x = FX(nx);
                U->y = FX(ny);
                break;
            }
        }
        fx_add(PX(U->x), PX(U->y) - 8, FX_POOF);
        H->cd[4] = 720;
        sfx_play(SFX_START);
        hud_dirty = 1;
        return;
    }
    if (hk[i] >= K_GEN) { cast_gen(i, slot, c); return; }
    if (hk[i] == K_AXE) {
        if (slot == 0) {
            if (!H->sk[0] || H->mana < 80) return;
            H->mana -= 80;
            H->cd[0] = 600;
            H->cast_lock = 8;
            berserkers_call(i);
        } else if (slot == 1) {
            s8 t;
            if (!H->sk[1] || H->mana < 50 || (t = hero_or_creep(i, 100)) < 0) return;
            H->mana -= 50;
            H->cd[1] = 720;
            H->cast_lock = 6;
            un[(u8)t].hunger = 60;
            face_to(i, t);
            fx_add(PX(un[(u8)t].x), PX(un[(u8)t].y) - 12, FX_SPARK);
            sfx_play(SFX_HIT);
        } else if (slot == 3) {
            s8 t;
            if (!ult_lv(i) || H->mana < 100 || (t = hero_or_creep(i, 32)) < 0) return;
            H->mana -= 100;
            H->cd[3] = 1500 - times(240, ult_lv(i));
            H->cast_lock = 12;
            face_to(i, t);
            fx_add(PX(un[(u8)t].x), PX(un[(u8)t].y) - 10, FX_RAZE);
            sfx_play(SFX_BIGEXPL);
            shake = 8;
            if (un[(u8)t].hp <= cull_limit(i)) {
                if (t < NH) { H->cd[3] = 0; msg("CULLING BLADE!", 90); }   /* a hero kill refreshes it */
                kill_unit(t, i);
            } else hurt(i, t, 150);
        }
    } else if (hk[i] == K_SF) {
        if (slot < 3) {
            if (!H->sk[0] || H->mana < 75) return;
            H->mana -= 75;
            H->cd[slot] = 540;
            U->wind = 0;
            H->cast_lock = 10;
            raze(i, raze_dist[slot]);
        } else if (slot == 3) {
            if (!ult_lv(i) || H->mana < 200) return;
            H->mana -= 200;
            H->cd[3] = 2400;
            H->chan_t = 40;
            H->chan_kind = 1;
        }
    } else {
        if (slot == 0) {
            s16 vx, vy;
            if (!H->sk[0] || H->hook_st || H->mana < 110) return;
            if (c && c->aim) {
                s16 dx = c->ax - PX(U->x), dy = c->ay - PX(U->y), d = dist(dx, dy);
                if (d < 1) d = 1;
                vx = divs((s32)dx * 80, d);
                vy = divs((s32)dy * 80, d);
                U->face = face_dir(dx, dy);
            } else {
                vx = (dvx[U->face] * 80) >> 6;
                vy = (dvy[U->face] * 80) >> 6;
            }
            H->mana -= 110;
            H->cd[0] = 780;
            H->hx = U->x;
            H->hy = U->y - FX(10);
            H->hvx = vx;
            H->hvy = vy;
            H->hook_t = 0;
            H->hook_st = 1;
            H->cast_lock = 8;
            sfx_play(SFX_HOOK);
        } else if (slot == 1) {
            if (!H->rot && !H->sk[1]) return;
            H->rot ^= 1;
            H->cd[1] = 20;
        } else if (slot == 3) {
            s8 t;
            if (!ult_lv(i) || H->mana < 120) return;
            t = nearest(i, 32, F_HERO);
            if (t < 0) t = nearest(i, 32, F_CREEP);
            if (t < 0) return;
            H->mana -= 120;
            H->cd[3] = 1200;
            H->chan_t = 180;
            H->chan_kind = 2;
            H->chan_tgt = t;
        }
    }
    hud_dirty = 1;
}

static void hook_update(u8 i)
{
    Hero *H = &hr[i];
    Unit *P = &un[i];
    u8 t;
    if (!H->hook_st) return;
    if (H->hook_st == 1) {
        H->hx += H->hvx * DT;
        H->hy += H->hvy * DT;
        for (t = 0; t < NU; t++) {
            if (un[t].type >= U_TOWER || !attackable(t, P->team)) continue;
            if (dist(PX(un[t].x - H->hx), PX(un[t].y - FX(8) - H->hy)) < 10) {
                H->hook_tgt = t;
                H->hook_st = t == ROSH ? 3 : 2;               /* Roshan is far too heavy to drag */
                hurt(i, t, times(90, hr[i].sk[0]));
                sfx_play(SFX_HIT);
                break;
            }
        }
        if (H->hook_st == 1 && ((H->hook_t += DT) >= 32 || H->hx < FX(8) || H->hy < FX(8) ||
                                H->hx > FX(WORLD - 8) || H->hy > FX(WORLD - 8)))
            H->hook_st = 3;
    } else {
        s16 dx = P->x - H->hx, dy = P->y - FX(10) - H->hy, d = dist(PX(dx), PX(dy));
        if (d < 12) {
            if (H->hook_st == 2 && H->hook_tgt >= 0 && un[(u8)H->hook_tgt].on) un[(u8)H->hook_tgt].stun = 12;
            H->hook_st = 0;
            return;
        }
        H->hx += divs((s32)dx * 80, d << 3);
        H->hy += divs((s32)dy * 80, d << 3);
        if (H->hook_st == 2) {
            Unit *v = &un[(u8)H->hook_tgt];
            if (!v->on) H->hook_st = 3;
            else {
                v->x = H->hx;
                v->y = H->hy + FX(8);
                clamp_pos(v);
                v->stun = 4;
                if (H->hook_tgt < NH) hr[(u8)H->hook_tgt].chan_t = 0;
            }
        }
    }
}

/* ------------------------------------------------------------- player & bot control */
/* nearest creep within r that one hit kills: an enemy one to last-hit, else one of ours to deny */
static s8 cs_target(u8 i, s16 r, s16 bonus)
{
    s16 dmg = atk_dmg(i) + bonus, best = r + 1;
    s8 t = -1;
    u8 side;
    for (side = 0; side < 2; side++) {
        u8 team = un[i].team ^ side ^ 1, n = tcount[team];
        const u8 *l = tlist[team];
        while (n--) {
            u8 m = *l++;
            s16 d;
            if (m < FIRST_CREEP || !un[m].on || un[m].hp > dmg) continue;
            if (side && un[m].hp * 2 >= un[m].hpmax) continue;
            d = udist(i, m);
            if (d < best) { best = d; t = m; }
        }
        if (t >= 0) return t;
    }
    return -1;
}

static const u16 key_bit[4] = { B_B, B_C, B_X, B_Y };

static void player_cmd(u8 i, Cmd *c)
{
    Hero *H = &hr[i];
    u16 p = H->pad, n = H->pad_new;
    s16 r = atk_range(i);
    s8 t;
    c->mvx = (p & B_RIGHT) ? 1 : ((p & B_LEFT) ? -1 : 0);
    c->mvy = (p & B_DOWN) ? 1 : ((p & B_UP) ? -1 : 0);
    c->tgt = -1;
    t = un[i].tgt;
    if (p & B_A) {
        if (n & B_A) {          /* a fresh press goes for a last hit or a deny first */
            s8 k = cs_target(i, r + 40, 2);
            if (k >= 0) t = k;
        }
        if (!(attackable(t, un[i].team) || deniable(t, un[i].team)) || udist(i, t) > r + 70)
            t = nearest(i, r + 70, F_HERO | F_CREEP | F_BLD);
        c->tgt = t;
    } else if (!c->mvx && !c->mvy) {
        if (!(attackable(t, un[i].team) || deniable(t, un[i].team)) || un[(u8)t].type == U_HERO || udist(i, t) > r + 4)
            t = nearest(i, r + 4, F_CREEP | F_BLD);
        c->tgt = t;
    }
    c->cast = (n & B_Z) ? 16 : 0;
    /* B C X Y cast at once, unless that skill can be learned: then holding the key learns it
       and a short press casts on release, as in Dota */
    if (H->hold_k < 4) {
        u8 k = H->hold_k;
        if (!(p & key_bit[k])) { c->cast |= 1 << k; H->hold_k = 255; }
        else if ((H->hold_t += DT) >= 30) {
            H->hold_k = 255;
            if (learn(i, key_skill(i, k))) sfx_play(SFX_PICKUP);
        }
    }
    for (u8 k = 0; k < 4; k++)
        if (n & key_bit[k]) {
            if (can_learn(i, key_skill(i, k)) && H->hold_k > 3) { H->hold_k = k; H->hold_t = 0; }
            else if (H->hold_k != k) c->cast |= 1 << k;
        }
}

/* Lane geometry for the bots: s is the distance along a lane from the Radiant Ancient. */
#define NO_FRONT 0x7FFF
static s16 lane_cum[3][6], bld_s[NBLD];
static s16 cross_s[2];      /* where the top lane and mid cross the river */
static u8 ls_seg;

/* project (x, y) onto segments k0..k1 of a lane: returns s, sets *off to the distance
   from it and ls_seg */
static s16 lane_s_seg(u8 l, u8 k0, u8 k1, s16 x, s16 y, s16 *off)
{
    s16 best = 0x7FFF, s = 0;
    u8 k;
    for (k = k0; k <= k1; k++) {
        s16 ax = lane_x(l, k), ay = lane_y(l, k), vx = lane_x(l, k + 1) - ax, vy = lane_y(l, k + 1) - ay;
        s16 len = lane_cum[l][k + 1] - lane_cum[l][k], u, d;
        s16 rx = x - ax, ry = y - ay;      /* 16-bit operands: muls, not __mulsi3 */
        s32 dot = (s32)rx * vx + (s32)ry * vy;
        if (dot <= 0) u = 0;
        else if (dot >= (s32)len * len) u = len;
        else u = divs(dot, len);
        d = dist(x - ax - divs((s32)vx * u, len), y - ay - divs((s32)vy * u, len));
        if (d < best) { best = d; s = lane_cum[l][k] + u; ls_seg = k; }
    }
    *off = best;
    return s;
}

static s16 lane_s(u8 l, s16 x, s16 y, s16 *off) { return lane_s_seg(l, 0, lane_len[l] - 2, x, y, off); }

static void lane_point(u8 l, s16 s, s16 *x, s16 *y)
{
    u8 k = 0;
    s16 len, u;
    if (s < 0) s = 0;
    while (k + 2 < lane_len[l] && s > lane_cum[l][k + 1]) k++;
    len = lane_cum[l][k + 1] - lane_cum[l][k];
    u = s - lane_cum[l][k];
    if (u > len) u = len;
    *x = lane_x(l, k) + divs((s32)(s16)(lane_x(l, k + 1) - lane_x(l, k)) * u, len);
    *y = lane_y(l, k) + divs((s32)(s16)(lane_y(l, k + 1) - lane_y(l, k)) * u, len);
}

static s16 lane_end(u8 l) { return lane_cum[l][lane_len[l] - 1]; }

static void lanes_init(void)
{
    u8 l, k;
    s16 off;
    for (l = 0; l < 3; l++)
        for (k = 0; k + 1 < lane_len[l]; k++)
            lane_cum[l][k + 1] = lane_cum[l][k] +
                dist(lane_x(l, k + 1) - lane_x(l, k), lane_y(l, k + 1) - lane_y(l, k));
    for (k = 0; k < NBLD; k++)
        if (slot_tab[k] < B_ANCIENT)
            bld_s[k] = lane_s(slot_lane(k >= 13, slot_tab[k] >> 1), PX(un[FIRST_BLD + k].x), PX(un[FIRST_BLD + k].y), &off);
    cross_s[0] = lane_s(0, 112, 112, &off);
    cross_s[1] = lane_s(1, 512, 512, &off);
}

/* a team's first standing structure on a lane, from the outside in */
static u8 outer_bld(u8 team, u8 l)
{
    u8 b = FIRST_BLD + times(team, 13) + slot_lane(team, l) * 2;
    if (un[b].on) return b;
    if (un[b + 1].on) return b + 1;
    return FIRST_BLD + times(team, 13) + B_ANCIENT;
}

static s16 bld_lane_s(u8 b, u8 l)
{
    if (bld_slot(b) == B_ANCIENT) return un[b].team ? lane_end(l) : 0;
    return bld_s[b - FIRST_BLD];
}

/* how far the team's leading creep on a lane has got; rescanned every 16 frames */
static s16 front[2][3];

/* all six fronts in one pass over the creeps, every 16 frames in the second half of a step */
static void fronts_update(void)
{
    u8 i, k;
    for (k = 0; k < 3; k++) front[0][k] = front[1][k] = NO_FRONT;
    for (i = FIRST_CREEP; i < ROSH; i++) {
        Unit *c = &un[i];
        s16 p, *f;
        u8 cl;
        if (!c->on) continue;
        cl = c->lane;
        p = dist(lane_x(cl, c->wp) - PX(c->x), lane_y(cl, c->wp) - PX(c->y));
        p = c->team ? lane_cum[cl][c->wp] + p : lane_cum[cl][c->wp] - p;
        f = &front[c->team][cl];
        if (*f == NO_FRONT || (c->team ? p < *f : p > *f)) *f = p;
    }
}

static s16 creep_front(u8 team, u8 l) { return front[team][l]; }

static u8 nearest_lane(s16 x, s16 y) { return lane_map[((u16)(y >> 4) << 6) + (x >> 4)]; }

static void goto_pt(Cmd *c, s16 x, s16 y, s16 tx, s16 ty)
{
    s16 dx = tx - x, dy = ty - y;
    c->mvx = dx > 4 ? 1 : (dx < -4 ? -1 : 0);
    c->mvy = dy > 4 ? 1 : (dy < -4 ? -1 : 0);
}

/* walk to s = want on lane l: back onto the lane along the nav field, then along the road */
static void lane_walk(Cmd *c, u8 i, u8 l, s16 want)
{
    static u8 last_l[NH] = { 255, 255, 255, 255, 255, 255 }, last_k[NH];
    static const s8 side_off[3] = { 0, 10, -10 };      /* teammates keep apart */
    s16 x = PX(un[i].x), y = PX(un[i].y), off, s, tx, ty;
    off = 0x7FFF;
    if (last_l[i] == l)         /* heroes move slowly: usually only the neighbouring segments matter */
        s = lane_s_seg(l, last_k[i] ? last_k[i] - 1 : 0,
                       last_k[i] + 2 < lane_len[l] ? last_k[i] + 1 : last_k[i], x, y, &off);
    if (off > 24) s = lane_s(l, x, y, &off);
    last_l[i] = l;
    last_k[i] = ls_seg;
    if (off > 24) {
        u8 v = nav_at(l, want > s ? ls_seg + 1 : ls_seg, x, y);
        if (!(v & 8)) {
            s16 fx = dvx[v & 7], fy = dvy[v & 7];
            c->mvx = fx > 0 ? 1 : (fx < 0 ? -1 : 0);
            c->mvy = fy > 0 ? 1 : (fy < 0 ? -1 : 0);
            return;
        }
    }
    if (want > s + 48) want = s + 48;
    if (want < s - 48) want = s - 48;
    lane_point(l, want, &tx, &ty);
    goto_pt(c, x, y, tx + ((i & 1) ? -6 : 6) + side_off[i >> 1], ty + ((i & 1) ? -6 : 6) - side_off[i >> 1]);
}

/* the straight walk from (x, y) to (tx, ty) has no trees on it */
static u8 clear_path(s16 x, s16 y, s16 tx, s16 ty)
{
    s16 dx = (tx - x) >> 3, dy = (ty - y) >> 3;
    u8 k;
    for (k = 0; k < 8; k++) {
        x += dx;
        y += dy;
        if (!walkable(x, y)) return 0;
    }
    return 1;
}

/* Roshan: along the river to the pit (from mid or the top lane), then hit him */
static void rosh_cmd(Cmd *c, u8 i, s16 x, s16 y)
{
    if (dist(x - ROSH_X, y - ROSH_Y) < 72) { c->tgt = ROSH; return; }
    if (x - y < 40 && y - x < 40) goto_pt(c, x, y, ROSH_X, ROSH_Y);
    else {
        u8 l = nearest_lane(x, y) == 0 ? 0 : 1;
        lane_walk(c, i, l, cross_s[l]);
    }
}

/* every 2 seconds: can the side's bots (and players next to the pit) kill Roshan in time without
   losing too much health, with no more enemy heroes up than ours? */
/* the nearest jungle neutral within r that the hero can walk straight to */
static s8 jungle_target(s16 x, s16 y, s16 r)
{
    u8 j;
    s8 best = -1;
    for (j = NEUT; j < NU; j++)
        if (un[j].on) {
            s16 d = dist(PX(un[j].x) - x, PX(un[j].y) - y);
            if (d < r && clear_path(x, y, PX(un[j].x), PX(un[j].y))) { r = d; best = j; }
        }
    return best;
}

static u8 rosh_go[2];
static void rosh_plan(u8 team)
{
    Unit *R = &un[ROSH];
    u8 k, n = 0, foes = 0, was = rosh_go[team];
    s16 dps = 0, hp = 0, secs, rd;
    rosh_go[team] = 0;
    if (!R->on || (aegis >= 0 && (aegis & 1) == team)) return;
    for (k = team; k < nh; k += 2)
        if (un[k].on && (hr[k].bot ? hr[k].ai_st != 1 && hr[k].lvl >= 9 : udist(k, ROSH) < 120)) {
            n++;
            dps += divs(muls(atk_dmg(k), 60), unit_rate(k));
            hp += un[k].hp;
        }
    for (k = team ^ 1; k < nh; k += 2)
        if (un[k].on) foes++;
    if (!n || foes > n || (nh > 2 && n < 2)) return;
    dps -= (dps >> 2) + (dps >> 4);                 /* his armor */
    if (dps < 8) return;
    secs = divs(R->hp, dps);
    rd = divs(muls(rosh_dmg(), 60), 70);
    rd -= rd >> 2;
    rosh_go[team] = secs < 50 && muls(rd, secs) < (was ? hp : hp - (hp >> 1));
}

static void bot_shop(u8 i)
{
    Hero *H = &hr[i];
    u8 n, k;
    for (n = 0; n < NITEM; n++) {
        k = bot_buy[n];
        if (!(H->items & (1 << k))) {           /* in order: save up for the next item */
            if (H->gold < item_price[k]) return;
            H->gold -= item_price[k];
            H->items |= 1 << k;
            refresh_max(i);
        }
    }
}

/* where to fight: defend a tower under attack, else meet (or, when outlevelled, avoid) the
   enemy hero, else push the lane with the weakest enemy structure */
static u8 enemy_hero(u8 i)
{
    u8 e = i ^ 1, f, team = i & 1;
    s16 d = un[e].on && SEEN(team, e) ? udist(i, e) : 0x7FFF;
    for (f = e + 2; f < nh; f += 2)
        if (un[f].on && SEEN(team, f)) {
            s16 df = udist(i, f);
            if (df < d) { d = df; e = f; }
        }
    return e;
}

static u8 choose_lane1(u8 i);

/* 2v2, 3v3: the whole side holds mid together, leaving only to defend */
static u8 choose_lane(u8 i) { return choose_lane1(i); }

static u8 choose_lane1(u8 i)
{
    u8 team = un[i].team, e = enemy_hero(i), l, k, best = 1;
    s16 hp = 0x7FFF;
    Unit *A = &un[FIRST_BLD + times(team, 13) + B_ANCIENT];
    for (k = 0; k < 2; k++)             /* inner towers first */
        for (l = 0; l < 3; l++) {
            Unit *b = &un[FIRST_BLD + times(team, 13) + slot_lane(team, l) * 2 + 1 - k];
            if (b->on && b->tgt >= FIRST_CREEP) return l;
        }
    for (k = 0; k < tcount[team ^ 1]; k++) {
        u8 m = tlist[team ^ 1][k];
        if (m >= FIRST_CREEP && dist(cpx[m] - PX(A->x), cpy[m] - PX(A->y)) < 160) return un[m].lane;
    }
    if (nh == 2 && un[e].on && dist(PX(un[e].x) - fountain_x[e & 1], PX(un[e].y) - fountain_y[e & 1]) > 240) {
        /* 1v1: meet the enemy hero on its lane (in team games the bots hold mid instead) */
        l = nearest_lane(PX(un[e].x), PX(un[e].y));
        if (hr[i].lvl + 1 < hr[e].lvl) return l == 1 ? (team ? 0 : 2) : 2 - l;
        return l;
    }
    if (nh > 2) return 1;
    for (k = 0; k < 3; k++) {                   /* mid wins unless a side tower is much weaker */
        static const u8 order[3] = { 1, 0, 2 };
        u8 b;
        s16 v;
        l = order[k];
        b = outer_bld(team ^ 1, l);
        v = un[b].hp - (l == 1 ? 500 : 0);
        if (!protected_bld(b) && v < hp) { hp = v; best = l; }
    }
    return best;
}

/* lined up for Meat Hook: no enemy creep within 12 px of the path to (ax, ay) */
static u8 hook_clear(u8 i, s16 ax, s16 ay)
{
    s16 x = PX(un[i].x), y = PX(un[i].y) - 10, dx = ax - x, dy = ay - y, d = dist(dx, dy);
    s32 dd = (s32)dx * dx + (s32)dy * dy;
    const u8 *l = tlist[un[i].team ^ 1];
    u8 n = tcount[un[i].team ^ 1];
    while (n--) {
        u8 m = *l++;
        s16 cx, cy;
        s32 dot, cr;
        if (m < FIRST_CREEP) continue;
        cx = cpx[m] - x;
        cy = cpy[m] - 8 - y;
        dot = (s32)cx * dx + (s32)cy * dy;
        cr = (s32)cx * dy - (s32)cy * dx;
        if (cr < 0) cr = -cr;
        if (dot > 0 && dot < dd && cr < (s32)12 * d) return 0;
    }
    return 1;
}

/* the table-driven heroes: the first skill that fits the situation */
static void bot_gen(u8 i, Cmd *c, u8 e, s16 ed, s16 ex, s16 ey)
{
    Hero *H = &hr[i];
    Unit *U = &un[i], *E = &un[e];
    u8 k, t;
    if (H->chan_t || (rnd() & 1)) return;
    for (k = 0; k < 4; k++) {
        const SkDef *d = sk_def(i, k);
        s16 dmg;
        u8 go = 0;
        if (!H->sk[k] || d->kind == SK_PASSIVE || H->cd[k] || H->mana < d->mana) continue;
        dmg = sk_dmg(i, k);
        switch (d->kind) {
        case SK_NUKE: go = ed < d->range && (k < 3 || E->hp <= dmg + (dmg >> 1) || E->hp * 2 < E->hpmax); break;
        case SK_DRAIN: go = ed < d->range && hr[e].mana > 40 && H->mana * 2 < H->manamax; break;
        case SK_AREA: go = ed < d->range + d->rad - 6; break;
        case SK_LINE: go = ed < times(3, d->range) - 10; break;
        case SK_GLOBAL:
            for (t = U->team ^ 1; t < nh; t += 2)
                if (un[t].on && un[t].hp <= dmg) go = 1;
            break;
        case SK_CHAN: go = ed < 50 && U->hp * 2 > U->hpmax; break;
        case SK_BUFF: go = ed < 50; break;
        case SK_HEAL: go = U->hp * 2 < U->hpmax; break;
        case SK_OMNI: go = ed < d->range && E->hp * 3 < E->hpmax * 2; break;
        }
        if (!go) continue;
        c->cast |= 1 << k;
        if (d->kind == SK_AREA || d->kind == SK_LINE) { c->aim = 1; c->ax = ex; c->ay = ey; }
        return;
    }
}

static void bot_cmd(u8 i, Cmd *c)
{
    static s16 seen_x[NH], seen_y[NH];
    Hero *H = &hr[i];
    Unit *U = &un[i];
    u8 e = enemy_hero(i), k, l;
    Unit *E = &un[e];
    s16 x = PX(U->x), y = PX(U->y), ex = PX(E->x), ey = PX(E->y);
    s16 evx = ex - seen_x[i], evy = ey - seen_y[i];      /* enemy movement over 4 frames */
    s8 dir = (i & 1) ? -1 : 1, t;
    s16 ed = E->on && SEEN(i & 1, e) ? dist(ex - x, ey - y) : 999;     /* at night: only the ones in sight */
    u8 et, busy, dived;
    s16 front, want, lim, own;

    seen_x[i] = ex;
    seen_y[i] = ey;
    if (H->ai_t) H->ai_t--;
    if (!H->ai_t && H->ai_st == 0) {
        H->ai_t = 8;
        if (ed > 200) {             /* a whole think of its own: the movement of the last one repeats */
            H->ai_lane = choose_lane(i);
            H->ai_t = 60;
            return;
        }
    }
    c->mvx = c->mvy = 0;
    c->tgt = -1;
    c->cast = 0;
    c->aim = 0;
    c->face = 255;

    l = H->ai_lane;
    et = outer_bld(e & 1, l);
    busy = un[et].tgt >= FIRST_CREEP;
    dived = un[et].tgt == (s8)i;                       /* the enemy tower is shooting at us */

    if (U->hp * 10 < U->hpmax * 3 || (dived && U->hp * 2 < U->hpmax)) H->ai_st = 1;
    if (H->ai_st == 1) {
        s16 fd = dist(x - fountain_x[i & 1], y - fountain_y[i & 1]);
        if (fd > 200) lane_walk(c, i, l, (i & 1) ? lane_end(l) : 0);     /* the base itself is open ground */
        else if (fd > 24) goto_pt(c, x, y, fountain_x[i & 1], fountain_y[i & 1]);
        else {
            bot_shop(i);
            if (U->hp * 10 >= U->hpmax * 9 && H->mana * 10 >= H->manamax * 7) { H->ai_st = 0; H->ai_t = 0; }
        }
        if (H->rot) c->cast |= 2;
        return;
    }

    if (ed < 200) {
        if (hk[i] == K_AXE) {
            if (H->sk[0] && !H->cd[0] && H->mana >= 80 && ed < 34 && U->hp * 5 > U->hpmax * 2) c->cast |= 1;
            if (H->sk[1] && !H->cd[1] && H->mana >= 50 && ed < 96 && !E->hunger && (rnd() & 3) == 0) c->cast |= 2;
            if (ult_lv(i) && !H->cd[3] && H->mana >= 100 && ed < 30 && E->hp <= cull_limit(i)) c->cast |= 8;
        } else if (hk[i] == K_PUDGE) {
            if (!H->hook_st && !H->cd[0] && H->mana >= 110 && ed > 36 && ed < 150 && (rnd() & 7) == 0) {
                s16 iv = nh == 2 ? 20 : (nh == 4 ? 40 : 60);  /* evx is over 4, 8 or 12 frames; the hook flies 5 px a frame */
                s16 ax = ex + divs((s32)evx * ed, iv), ay = ey - 8 + divs((s32)evy * ed, iv);
                if (dist(ax - x, ay - y) < 156 && hook_clear(i, ax, ay)) {
                    c->cast |= 1;
                    c->aim = 1;
                    c->ax = ax;
                    c->ay = ay;
                }
            }
            if ((ed < 34 && !H->rot) || (ed > 60 && H->rot)) c->cast |= 2;
            if (ult_lv(i) && !H->cd[3] && H->mana >= 120 && ed < 28) c->cast |= 8;
        } else if (hk[i] == K_SF) {
            u8 f = face_dir(ex - x, ey - y);
            for (k = 0; k < 3; k++) {
                s16 cx = x + ((dvx[f] * (s16)raze_dist[k]) >> 6), cy = y + ((dvy[f] * (s16)raze_dist[k]) >> 6);
                if (!H->cd[k] && H->mana >= 75 && dist(cx - ex, cy - ey) < 18 && (rnd() & 3) == 0) {
                    c->face = f;
                    c->cast |= 1 << k;
                    break;
                }
            }
            if (ult_lv(i) && !H->cd[3] && H->mana >= 200 && ed < 56 && (E->hp * 2 < E->hpmax || E->stun))
                c->cast |= 8;
        }
    }

    if (hk[i] >= K_GEN && E->on) bot_gen(i, c, e, ed, ex, ey);
    if (H->buf_t && E->on && ed < 120) { c->tgt = e; return; }   /* Blade Fury: run the enemy hero down */

    /* step out of range of the enemy tower when it has nothing else to shoot */
    if (dived) {
        lane_walk(c, i, l, bld_lane_s(et, l) - dir * 150);
        return;
    }

    /* Roshan, when the side is up to it and the enemy hero is not about */
    if (rosh_go[U->team] && (!E->on || ed > 150)) { rosh_cmd(c, i, x, y); return; }
    /* a rune close by */
    if (!E->on || ed > 110)
        for (k = 0; k < 4; k++)
            if (rune_on[k] && dist(rune_x[k] - x, rune_y[k] - y) < 160 && clear_path(x, y, rune_x[k], rune_y[k])) {
                goto_pt(c, x, y, rune_x[k], rune_y[k]);
                return;
            }

    /* a jungle camp on us: finish it */
    for (k = NEUT; k < NU; k++)
        if (un[k].on && un[k].tgt == (s8)i) { c->tgt = k; return; }

    /* last hits and denies */
    t = cs_target(i, 130, hk[i] == K_SF ? 6 : 2);
    if (t >= 0) { c->tgt = t; return; }

    /* trade hits with the enemy hero when it is not under its tower */
    if (E->on && ed < atk_range(i) + 30 && dist(PX(un[et].x) - ex, PX(un[et].y) - ey) > 100 &&
        divs((s32)U->hp * 100, U->hpmax) + 10 >= divs((s32)E->hp * 100, E->hpmax)) {
        c->tgt = e;
        return;
    }
    /* go shopping (before farming on) when an item is affordable and the enemy hero is far */
    for (k = 0; k < NITEM; k++)
        if (!(H->items & (1 << bot_buy[k]))) {
            if (H->gold >= item_price[bot_buy[k]] && ed > 160) { H->ai_st = 1; return; }
            break;
        }
    /* a jungle camp close by, when it is safe and the hero can take it: farm it between last hits */
    if (H->lvl >= 3 && U->hp * 5 > U->hpmax * 3 && (!E->on || ed > 200)) {
        t = jungle_target(x, y, 200);
        if (t >= 0) { c->tgt = t; return; }
    }
    /* push when the enemy hero is away */
    if (!E->on || ed > 220) {
        t = nearest(i, 110, F_CREEP | F_BLD);
        if (t >= 0 && (un[(u8)t].type < U_TOWER || busy || un[(u8)t].type == U_ANCIENT)) {
            c->tgt = t;
            return;
        }
    }
    /* stand a little behind our creep wave */
    front = creep_front(U->team, l);
    own = bld_lane_s(outer_bld(U->team, l), l);
    if (front == NO_FRONT) {
        /* between waves: harass the enemy hero away from its tower, else walk out to meet the next
           wave (theirs if it is already coming) instead of idling under our tower */
        if (E->on && ed < 150 && dist(PX(un[et].x) - ex, PX(un[et].y) - ey) > 130 &&
            divs((s32)U->hp * 100, U->hpmax) + 5 >= divs((s32)E->hp * 100, E->hpmax)) {
            c->tgt = e;
            return;
        }
        front = creep_front(U->team ^ 1, l);
        want = front != NO_FRONT ? front - dir * 40 : (own + bld_lane_s(et, l)) >> 1;
    } else want = front - dir * 36;
    if ((dir > 0 && want < own + 24) || (dir < 0 && want > own - 24)) want = own + dir * 24;   /* never behind our tower */
    lim = bld_lane_s(et, l) - dir * 148;
    if (!busy && ((dir > 0 && want > lim) || (dir < 0 && want < lim))) want = lim;
    lane_walk(c, i, l, want);
}

/* ------------------------------------------------------------- hero update */
static void respawn(u8 i)
{
    Unit *U = &un[i];
    Hero *H = &hr[i];
    U->on = 1;
    static const s8 spawn_off[3] = { 0, 20, -20 };
    U->x = FX(fountain_x[i & 1] + ((i & 1) ? -28 : 28) + spawn_off[i >> 1]);
    U->y = FX(fountain_y[i & 1] + ((i & 1) ? 28 : -28) + spawn_off[i >> 1]);
    U->face = (i & 1) ? 3 : 7;
    U->hp = U->hpmax;
    U->stun = U->slow = U->wind = U->taunt = U->hunger = 0;
    H->call_t = 0;
    U->tgt = -1;
    H->mana = H->manamax;
    H->ai_st = 0;
    H->ai_t = 0;
    hud_dirty = 1;
    if (i == me) clearA(7);   /* the countdown may skip its last tick */
}

static void hero_update(u8 i)
{
    Hero *H = &hr[i];
    Unit *U = &un[i];
    Cmd c;
    u8 k;
    if (!U->on) {
        if (H->respawn) { DECN(H->respawn, DT); if (!H->respawn) respawn(i); }
        return;
    }
    for (k = 0; k < 5; k++) DECN(H->cd[k], DT);
    DECN(U->aggro, DT);
    DECN(U->slow, DT);
    DECN(U->imm, DT);
    DECN(U->hit, DT);
    DECN(U->cd, DT);
    DECN(U->taunt, DT);
    DECN(H->call_t, DT);
    DECN(H->helix_cd, DT);
    if ((game_t & 31) == 0 && U->hp < U->hpmax) U->hp++;
    if ((game_t & 15) == 0 && H->mana < H->manamax) H->mana++;
    if ((game_t & 3) == 0 && dist(PX(U->x) - fountain_x[i & 1], PX(U->y) - fountain_y[i & 1]) < 56) {
        U->hp += 1 + (U->hpmax >> 6);
        H->mana += 1 + (H->manamax >> 6);
        if (U->hp > U->hpmax) U->hp = U->hpmax;
        if (H->mana > H->manamax) H->mana = H->manamax;
    }
    if (H->rune_t && H->rune == R_REGEN && (game_t & 7) == 0) {     /* until full or hit */
        U->hp += 1 + (U->hpmax >> 5);
        H->mana += 1 + (H->manamax >> 5);
        if (U->hp > U->hpmax) U->hp = U->hpmax;
        if (H->mana > H->manamax) H->mana = H->manamax;
        if (U->hp == U->hpmax && H->mana == H->manamax) H->rune_t = 0;
    }
    if ((game_t & 7) == 0 && dist(PX(U->x) - fountain_x[(i ^ 1) & 1], PX(U->y) - fountain_y[(i ^ 1) & 1]) < 72) hurt(-1, i, 40);
    if (!U->on) return;

    if (hk[i] == K_PUDGE) {
        hook_update(i);
        if (H->rot && (game_t & 7) == 0) {
            s16 d = (20 + times(15, hr[i].sk[1])) >> 3;
            u8 t;
            for (t = 0; t < NU; t++)
                if (un[t].type < U_TOWER && attackable(t, U->team) && udist(i, t) < 34) {
                    un[t].slow = 12;
                    hurt(i, t, d);
                }
            if (U->hp > d) U->hp -= d >> 1;
        }
    }
    if (hk[i] >= K_GEN) gen_update(i);
    if (H->chan_t && H->chan_kind == 4) U->stun = 0;
    if (!U->on) return;
    if (U->stun) {
        DECN(U->stun, DT);
        U->wind = 0;
        H->chan_t = 0;
        return;
    }

    memset(&c, 0, sizeof(c));
    c.face = 255;
    if (H->bot) {   /* bots think every few frames and repeat their movement in between */
        static Cmd last[NH];
        /* 1v1: every other step (4 frames); 2v2: every 4th step; 3v3: every 6th, one bot a step */
        if (nh == 2 ? !((stc ^ i) & 1) : (nh == 4 ? (stc & 3) == i : bot_ph == i)) {
            bot_cmd(i, &last[i]);
        }
        c = last[i];
        last[i].cast = 0;
        last[i].face = 255;
    } else player_cmd(i, &c);
    if (U->taunt) {         /* Berserker's Call: no moving, no casting, hit Axe */
        u8 a = axe_of(un[i].team);                     /* the Axe that called */
        c.mvx = c.mvy = 0;
        c.cast = 0;
        c.face = 255;
        c.tgt = attackable(a, un[i].team) ? a : -1;
        H->chan_t = 0;
    }

    if (H->chan_t) {
        if (!H->bot && (c.mvx || c.mvy) && H->chan_kind != 4) H->chan_t = 0;
        else if (H->chan_kind >= 3) {
            if (gen_channel(i)) return;
        } else if (H->chan_kind == 1) {
            DECN(H->chan_t, DT);
            if (!H->chan_t) requiem(i);
            return;
        } else {
            s8 t = H->chan_tgt;
            if (t < 0 || !un[(u8)t].on || udist(i, t) > 44) H->chan_t = 0;
            else {
                un[(u8)t].stun = 8;
                if ((H->chan_t & 7) == 0) hurt(i, t, (70 + 30 * ult_lv(i)) >> 3);
                DECN(H->chan_t, DT);
                return;
            }
        }
    }

    if (c.face < 8) U->face = c.face;
    for (k = 0; k < 5; k++)
        if (c.cast & (1 << k)) cast(i, k, &c);
    if (H->chan_t) return;
    if (H->cast_lock) { DECN(H->cast_lock, DT); return; }

    if (c.mvx || c.mvy) {
        s16 s = hero_spd(i) * DT;
        if (U->slow) s = (s * 11) >> 4;
        if (c.mvx && c.mvy) s = (s * 45) >> 6;
        U->wind = 0;
        step(U, c.mvx * s, c.mvy * s);
        U->face = face_of[(c.mvy + 1) * 3 + c.mvx + 1];
        U->anim += DT;
        U->tgt = -1;
    } else if (c.tgt >= 0) {
        s8 t = c.tgt;
        s16 d = udist(i, t) - (un[(u8)t].type >= U_ROSH ? 12 : 0), r = atk_range(i);
        if (un[(u8)t].type >= U_TOWER && r > 84) r = 84;      /* towers reach 100: nobody hits them for free */
        U->tgt = t;
        if (d <= r) {
            face_to(i, t);
            unit_attack(i, t);
        } else {
            U->wind = 0;
            move_to(i, PX(un[(u8)t].x), PX(un[(u8)t].y), hero_spd(i) * DT);
            U->anim++;
        }
    } else
        U->wind = 0;
}

/* ------------------------------------------------------------- HUD (window, rows 24-27) */
static void bar_tiles(u8 x, u8 y, u8 cells, s16 v, s16 vmax, u16 base)
{
    s16 fill = vmax > 0 ? divs((s32)v * (cells * 8), vmax) : 0;
    u8 k;
    VDP_CTRL32 = VRAM_W(WINDOW + ((((u16)y << 6) + x) << 1));
    for (k = 0; k < cells; k++) {
        s16 f = fill - k * 8;
        VDP_DATA = ATTR(1, 1, base + (f < 0 ? 0 : (f > 8 ? 8 : f)));
    }
}

static const char *const skill_name[NHERO][4] = {
    { "SHADOWRAZE      ", "NECROMASTERY    ", "PRESENCE        ", "REQUIEM OF SOULS" },
    { "MEAT HOOK       ", "ROT             ", "FLESH HEAP      ", "DISMEMBER       " },
    { "BERSERKERS CALL ", "BATTLE HUNGER   ", "COUNTER HELIX   ", "CULLING BLADE   " },
    { "SHRAPNEL        ", "HEADSHOT        ", "TAKE AIM        ", "ASSASSINATE     " },
    { "ARC LIGHTNING   ", "LIGHTNING BOLT  ", "STATIC FIELD    ", "THUNDERGOD WRATH" },
    { "DRAGON SLAVE    ", "LIGHT STRIKE    ", "FIERY SOUL      ", "LAGUNA BLADE    " },
    { "CRYSTAL NOVA    ", "FROSTBITE       ", "ARCANE AURA     ", "FREEZING FIELD  " },
    { "FROST ARROWS    ", "GUST            ", "MULTISHOT       ", "MARKSMANSHIP    " },
    { "POISON ATTACK   ", "NETHERTOXIN     ", "CORROSIVE SKIN  ", "VIPER STRIKE    " },
    { "BLADE FURY      ", "HEALING WARD    ", "BLADE DANCE     ", "OMNISLASH       " } };

/* ------------------------------------------------------------- split-screen HUD: 20 columns per player */
static void pad_to(char *b, u8 j, u8 n) { while (j < n) b[j++] = ' '; b[n] = 0; }

static void split_menu(u8 xo, u8 k)
{
    static const char *const items[NITEM] = { "BOOTS       ", "BLADES      ", "VITALITY    ", "BLINK DAGGER", "BRACER      " };
    Hero *H = &hr[me];
    const char *n;
    char b[24];
    u8 j = 0, m;
    if (shop_sel > 3) k++;                      /* four rows: scroll to the fifth item */
    n = shop_open ? items[k] : (k == 4 ? "+1 ATTRIBUTES   " : skill_name[hk[me]][k]);
    b[j++] = shop_sel == k ? '>' : ' ';
    for (m = 0; m < 12; m++) b[j++] = *n++;
    b[j++] = ' ';
    if (shop_open) {
        if (H->items & (1 << k)) { b[j++] = 'O'; b[j++] = 'W'; b[j++] = 'N'; }
        else { num(item_price[k], 4, b + j); j += 4; }
    } else if (k == 4) {
        b[j++] = '+';
        num(H->stat, 2, b + j); j += 2;
    } else if (H->sk[k] < sk_max(k) && H->lvl < sk_need(me, k)) {
        b[j++] = 'L'; b[j++] = 'V';
        num(sk_need(me, k), 2, b + j); j += 2;
    } else
        for (m = 0; m < sk_max(k); m++) b[j++] = m < H->sk[k] ? '*' : '.';
    pad_to(b, j, 20);
    textW(xo, 24 + k, b);
}

static void wtile(u8 x, u8 y, u16 attr);
static void split_row23(void)
{
    char b[44];
    u8 j = 0, k;
    const char *t;
    if (shop_open || learn_open) {
        t = shop_open ? " SHOP   A:BUY   START:EXIT" : " LEARN  A:LEARN  POINTS ";
        b[j++] = 'P'; b[j++] = port_of[me] ? '2' : '1';
        while (*t) b[j++] = *t++;
        if (learn_open) {
            num(hr[me].pts, 2, b + j); j += 2;
            t = "  START:EXIT";
            while (*t) b[j++] = *t++;
        }
        b[j] = 0;
    } else if (paused) {
        t = "PAUSED"; while (*t) b[j++] = *t++; b[j] = 0;
    } else if (msg_t) return;
    else {                  /* score line: P1 kills/deaths, clock, P2 kills/deaths - all 40 columns */
        u8 l = port_of[0] ? 1 : 0;
        for (k = 0; k < 40; k++) b[k] = ' ';
        b[40] = 0;
        b[1] = 'P'; b[2] = '1'; b[4] = 'K'; num(hr[l].kills, 2, b + 5); b[8] = 'D'; num(hr[l].deaths, 2, b + 9);
        b[29] = 'K'; num(hr[l ^ 1].kills, 2, b + 30); b[33] = 'D'; num(hr[l ^ 1].deaths, 2, b + 34);
        b[37] = 'P'; b[38] = '2';
        clock_text(b + 17);
        for (k = 0; k < 40; k++) if (!b[k]) b[k] = ' ';
        b[40] = 0;
        textW(0, 23, b);
        return;
    }
    clearW(23);
    textW((40 - j) >> 1, 23, b);
}

static void wicon(u8 x, u8 y, u16 attr);
static void abilities(u8 x0, u8 step, u16 tski);

/* part 0-3 of the HUD; only = 0 or 1 draws just that hero's half, 2 draws both.
   Each half is the full HUD cut down to 20 columns:
     portrait | HP, mana, XP bars | HP, mana, item marks | four abilities
     level    | gold              | Blink Dagger, +     | level pips      */
static void split_hud(u8 part, u8 only)
{
    u8 k, sv = view;
    char b[8];
    if (part == 3 && only != 1) split_row23();
    for (k = 0; k < 2; k++) {
        if (only < 2 && k != only) continue;
        Hero *H = &hr[k];
        Unit *U = &un[k];
        u8 xo = port_of[k] ? 20 : 0, x, y;
        if (k == me && (shop_open || learn_open)) { split_menu(xo, part); continue; }
        view = k;
        if (part == 0) {                /* portrait, level, HP and mana */
            u16 tp = k ? T_PORT2 : T_PORT;
            for (y = 0; y < 3; y++)
                for (x = 0; x < 3; x++) wtile(xo + x, 24 + y, ATTR(hero_pal[hk[k]], 1, tp + times(3, x) + y));
            if (U->on) { b[0] = 'L'; num(H->lvl, 2, b + 1); }
            else { b[0] = 'R'; num(divs(H->respawn + 59, 60), 2, b + 1); }
            textW(xo, 27, b);
            bar_tiles(xo + 3, 24, 5, U->on ? U->hp : 0, U->hpmax, T_HPBAR);
            num(U->on ? U->hp : 0, 4, b);
            textW(xo + 8, 24, b);
            bar_tiles(xo + 3, 25, 5, H->mana, H->manamax, T_MPBAR);
            num(H->mana, 4, b);
            textW(xo + 8, 25, b);
        } else if (part == 1) {
            abilities(xo + 12, 2, k ? T_SKI2 : T_SKI);
        } else if (part == 2) {         /* XP, items, gold, Blink Dagger, skill points */
            u16 need = 140 + times(60, H->lvl);
            bar_tiles(xo + 3, 26, 5, H->lvl >= MAX_LVL ? 1 : H->xp, H->lvl >= MAX_LVL ? 1 : need, T_XPBAR);
            for (x = y = 0; x < NITEM; x++)    /* marks of the first four items owned */
                if ((H->items & (1 << x)) && y < 4) wtile(xo + 8 + y++, 26, ATTR(1, 1, T_MINIIT + x));
            for (; y < 4; y++) wtile(xo + 8 + y, 26, ATTR(1, 1, T_FONTW));
            b[0] = '$';
            num(H->gold > 9999 ? 9999 : H->gold, 4, b + 1);
            textW(xo + 3, 27, b);
            if (H->items & IT_BLINK) {
                b[0] = 'Z';
                if (H->cd[4]) num(divs(H->cd[4] + 59, 60), 2, b + 1); else { b[1] = 'O'; b[2] = 'K'; }
            } else b[0] = b[1] = b[2] = ' ';
            b[3] = H->pts && (vcount & 32) ? '+' : ' ';
            b[4] = 0;
            textW(xo + 8, 27, b);
        }
        view = sv;
    }
}

/* the HUD is redrawn one part at a time: VDP writes during the active display are slow */
static void hud_part(u8 part)
{
    if (split) { split_hud(part & 3, part < 4 ? 2 : (part >> 2) - 1); return; }
    hud_part1(part);
}

/* window plane: one tile, and a 2x2 icon stored column-major */
static void wtile(u8 x, u8 y, u16 attr)
{
    VDP_CTRL32 = VRAM_W(WINDOW + ((((u16)y << 6) + x) << 1));
    VDP_DATA = attr;
}
static void wicon(u8 x, u8 y, u16 attr)
{
    wtile(x, y, attr); wtile(x, y + 1, attr + 1);
    wtile(x + 1, y, attr + 2); wtile(x + 1, y + 1, attr + 3);
}

/* the view hero's abilities from column x0, step columns apart: icon, cooldown or key, level pips */
static void abilities(u8 x0, u8 step, u16 tski)
{
    Hero *H = &hr[view];
    u8 kind = hk[view], k, x = x0;
    char b[4];
    for (k = 0; k < 4; k++, x += step) {
        u8 sk = kind == K_SF && k < 3 ? 0 : k, lv = H->sk[sk], j, st[4];
        u8 up = !H->bot && can_learn(view, sk), blink = up && (vcount & 32);   /* learnable: flashes */
        wicon(x, 24, lv || blink ? ATTR(2, 1, tski + (sk << 2)) : ATTR(2, 1, T_LOCK));
        if (!lv) { b[0] = b[1] = ' '; }
        else if (kind == K_PUDGE && k == 1) { b[0] = 'O'; b[1] = H->rot ? 'N' : 'F'; }
        else if (passive(kind, k)) { b[0] = b[1] = ' '; }
        else if (H->cd[k]) {
            u16 sec = divs(H->cd[k] + 59, 60);
            num(sec > 99 ? 99 : sec, 2, b);
        } else { b[0] = "BCXY"[k]; b[1] = ' '; }
        if (up && b[1] == ' ' && blink) b[1] = '+';      /* not over a cooldown or Rot's ON/OF */
        b[2] = 0;
        textW(x, 26, b);
        for (j = 0; j < 4; j++) st[j] = j < lv ? 2 : (j < sk_max(sk) ? 1 : 0);
        if (blink) st[lv] = 2;
        wtile(x, 27, ATTR(1, 1, T_PIPS + times(3, st[0]) + st[1]));
        wtile(x + 1, 27, ATTR(1, 1, T_PIPS + times(3, st[2]) + st[3]));
    }
}

/* Dota-style HUD: minimap | portrait | HP, mana, XP bars | four abilities | items;
   the clock and the team kills sit in a panel at the top of the screen */
static void hud_part1(u8 part)
{
    Hero *H = &hr[view];
    Unit *U = &un[view];
    char b[12];
    u8 k;
    if (part == 0) {                    /* big level (or respawn countdown), segmented bars */
        u16 need = 140 + times(60, H->lvl);
        u16 v = U->on ? H->lvl : divs(H->respawn + 59, 60);
        textW(8, 24, U->on ? "LVL" : "RES");
        num(v > 99 ? 99 : v, 2, b);
        for (k = 0; k < 2; k++) {
            wtile(8 + k, 25, ATTR(1, 1, T_BIGD + ((b[k] - '0') << 1)));
            wtile(8 + k, 26, ATTR(1, 1, T_BIGD + ((b[k] - '0') << 1) + 1));
        }
        bar_tiles(12, 24, 6, U->on ? U->hp : 0, U->hpmax, T_HPBAR);
        bar_tiles(12, 25, 6, H->mana, H->manamax, T_MPBAR);
        bar_tiles(12, 26, 6, H->lvl >= MAX_LVL ? 1 : H->xp, H->lvl >= MAX_LVL ? 1 : need, T_XPBAR);
        b[0] = H->pts && !H->bot && (vcount & 32) ? '+' : ' ';   /* skill points to spend */
        b[1] = H->pts && !H->bot && (vcount & 32) ? '0' + H->pts : ' ';
        b[2] = 0;
        textW(12, 27, b);
        return;
    }
    if (part == 1) { abilities(20, 3, T_SKI); return; }
    if (part == 2) {                    /* gold, Blink Dagger, the six item slots */
        u8 n = 0;
        b[0] = '$';
        num(H->gold > 99999 ? 99999 : H->gold, 5, b + 1);
        textW(5, 27, b);
        if (H->items & IT_BLINK) {
            b[0] = 'Z';
            if (H->cd[4]) num(divs(H->cd[4] + 59, 60), 2, b + 1); else { b[1] = 'O'; b[2] = 'K'; }
        } else b[0] = b[1] = b[2] = ' ';
        b[3] = 0;
        textW(15, 27, b);
        static const u8 sx[6] = { 33, 35, 37, 33, 35, 37 }, sy[6] = { 24, 24, 24, 26, 26, 26 };
        for (k = 0; k < NITEM; k++)         /* what the hero owns fills the slots from the left */
            if (H->items & (1 << k)) { wicon(sx[n], sy[n], ATTR(2, 1, T_ITEMS + (k << 2))); n++; }
        for (; n < 6; n++) wicon(sx[n], sy[n], ATTR(2, 1, T_SLOT0));
        return;
    }
    if (!split) {                       /* at the top: a big clock between the team kills, over the map */
        u8 kills[2] = { 0, 0 };
        for (k = 0; k < nh; k++) kills[k & 1] += hr[k].kills;
        clock_text(b);
        for (k = 0; k < 5; k++) {
            u8 d = b[k] == ':' ? 10 : b[k] - '0';
            VDP_CTRL32 = VRAM_W(PLANE_A + (18 + k) * 2);
            VDP_DATA = ATTR(1, 1, T_CLOCK + (d << 1));
            VDP_CTRL32 = VRAM_W(PLANE_A + 128 + (18 + k) * 2);
            VDP_DATA = ATTR(1, 1, T_CLOCK + (d << 1) + 1);
        }
        num(kills[0], 2, b); textA(15, 0, b);
        num(kills[1], 2, b); textA(24, 0, b);
    }
}

static void hud_draw(void)
{
    u8 k;
    if (split) for (k = 24; k < 28; k++) clearW(k);
    for (k = 0; k < 4; k++) hud_part(k);
}

/* the view hero's ability icons and portrait (its front pose on an opaque field) into VRAM */
static void hud_art(u8 h, u16 tski, u16 tport)
{
    const u32 *src = skill_icons + times(128, hk[h]);   /* 4 icons of 4 tiles of 8 longs */
    u16 k;
    VDP_CTRL32 = VRAM_W(tski << 5);
    for (k = 128; k; k--) VDP_DATA32 = *src++;
    src = hero_port + times(72, hk[h]);
    VDP_CTRL32 = VRAM_W(tport << 5);
    for (k = 0; k < 72; k++) {          /* 9 tiles column-major: on an orange field in a white frame */
        u32 v = *src++, o = 0;
        u8 n, t = k >> 3, r = k & 7, tx = t >= 6 ? 2 : (t >= 3 ? 1 : 0), ty = t - times(3, tx);
        u8 edge_y = (ty == 0 && r == 0) || (ty == 2 && r == 7);
        for (n = 0; n < 8; n++, v <<= 4) {
            u8 c = v >> 28;
            if (edge_y || (tx == 0 && n == 0) || (tx == 2 && n == 7)) c = 5;
            else if (!c) c = 15;
            o = (o << 4) | c;
        }
        VDP_DATA32 = o;
    }
}

static void hud_static(void)
{
    u8 x, y;
    for (y = HUD_Y; y < 28; y++) {
        clearW(y);
        VDP_CTRL32 = VRAM_W(WINDOW + ((((u16)y << 6)) << 1));
        for (x = 0; x < 4; x++) VDP_DATA = ATTR(0, 1, T_MINIMAP + x * 4 + (y - HUD_Y));
        VDP_DATA = ATTR(1, 1, T_FRAME + 1);
    }
    if (split) { hud_art(0, T_SKI, T_PORT); hud_art(1, T_SKI2, T_PORT2); return; }
    hud_art(view, T_SKI, T_PORT);
    for (y = 0; y < 3; y++)
        for (x = 0; x < 3; x++) wtile(5 + x, 24 + y, ATTR(hero_pal[hk[view]], 1, T_PORT + times(3, x) + y));
    for (y = 0; y < 3; y++) wtile(11, 24 + y, ATTR(1, 1, T_HICON + y));
    for (y = HUD_Y; y < 28; y++) { wtile(19, y, ATTR(1, 1, T_FRAME + 1)); wtile(31, y, ATTR(1, 1, T_FRAME + 1)); }
    afont = T_FONT;
}

static void clock_text(char *b)
{
    u16 sec = game_sec;
    u8 mm = 0;
    while (sec >= 60) { sec -= 60; mm++; }
    num(mm > 99 ? 99 : mm, 2, b);
    b[2] = ':';
    num(sec, 2, b + 3);
}

static void scoreboard(u8 show)
{
    u8 k;
    char b[8];
    for (k = 8; k < 16; k++) clearA(k);
    if (!show) return;
    panelA(0, 40, 8, 9 + nh);
    textA(1, 8, "HERO          LV  K  D  CS/DN  GOLD");
    for (k = 0; k < nh; k++) {
        u8 h = k < (nh >> 1) ? k << 1 : ((k - (nh >> 1)) << 1) + 1;     /* Radiant first */
        Hero *H = &hr[h];
        u8 y = 9 + k;
        textA(1, y, hero_name[hk[h]]);
        num(H->lvl, 2, b); textA(15, y, b);
        num(H->kills, 2, b); textA(18, y, b);
        num(H->deaths, 2, b); textA(21, y, b);
        num(H->lasthits, 3, b); b[3] = '/'; num(H->denies > 99 ? 99 : H->denies, 2, b + 4); textA(24, y, b);
        num(H->gold > 9999 ? 9999 : H->gold, 4, b); textA(32, y, b);
    }
    afont = T_FONT;
}

static void shop_draw(void)
{
    if (split) { hud_dirty = 1; return; }
    static const char *const names[NITEM] = { "BOOTS OF SPEED  ", "BLADES OF ATTACK", "VITALITY BOOSTER", "BLINK DAGGER    ",
                                              "BRACER          " };
    Hero *H = &hr[me];
    u8 k;
    char b[8];
    panelA(4, 36, 6, 14);
    textA_c(7, "- SHOP -  A:BUY  START:EXIT");
    for (k = 0; k < NITEM; k++) {
        textA(6, 9 + k, shop_sel == k ? ">" : " ");
        textA(8, 9 + k, names[k]);
        if (H->items & (1 << k)) textA(26, 9 + k, " OWNED");
        else { b[0] = ' '; num(item_price[k], 4, b + 1); textA(26, 9 + k, b); }
    }
    afont = T_FONT;
}

static void learn_draw(void)
{
    Hero *H = &hr[me];
    u8 k, j;
    char b[12];
    if (split) { hud_dirty = 1; return; }
    panelA(2, 38, 6, 16);
    textA_c(7, "- LEARN SKILL - A:LEARN START:EXIT");
    textA(4, 13, shop_sel == 4 ? ">" : " ");
    textA(6, 13, "+1 ALL ATTRIBUTES");
    b[0] = '+';
    num(H->stat, 2, b + 1);
    b[3] = 0;
    textA(24, 13, b);
    {                               /* STR AGI INT now */
        char a[40] = "STR     AGI     INT     ARM    ";
        s16 r = H->arm < 0 ? -H->arm : H->arm;
        for (k = 3; k--; ) { num(H->at[k], 3, a + 4 + (k << 3)); a[7 + (k << 3)] = ' '; }   /* num ends the string */
        num(divs(r, 10), 2, a + 28);
        if (a[28] == '0') a[28] = H->arm < 0 ? '-' : ' ';
        a[30] = '.';
        a[31] = '0' + r - times(divs(r, 10), 10);
        a[32] = 0;
        textA_c(15, a);
    }
    for (k = 0; k < 4; k++) {
        u8 mx = sk_max(k);
        textA(4, 9 + k, shop_sel == k ? ">" : " ");
        textA(6, 9 + k, skill_name[hk[me]][k]);
        for (j = 0; j < mx; j++) b[j] = j < H->sk[k] ? '*' : '.';
        b[mx] = ' ';
        b[mx + 1] = 0;
        textA(24, 9 + k, b);
        if (H->sk[k] < mx && H->lvl < sk_need(me, k)) {
            b[0] = 'L'; b[1] = 'V';
            num(sk_need(me, k), 2, b + 2);
        } else { b[0] = b[1] = b[2] = b[3] = ' '; b[4] = 0; }
        textA(31, 9 + k, b);
    }
    b[0] = 'P'; b[1] = 'O'; b[2] = 'I'; b[3] = 'N'; b[4] = 'T'; b[5] = 'S'; b[6] = ' ';
    num(H->pts, 2, b + 7);
    b[9] = 0;
    textA_c(16, b);
    afont = T_FONT;
}

/* ------------------------------------------------------------- drawing */
typedef struct { s16 key, x, y; u16 attr; u8 size, pad[7]; } DrawEnt;
static DrawEnt de[48];
static u8 nde, dhead[48], dnext[48];   /* depth order: 8-pixel buckets of the key, each sorted */

static void de_add(s16 key, s16 x, s16 y, u8 size, u16 attr)
{
    DrawEnt *d;
    if (nde >= 48 || x <= vw_x0 - 48 || x >= vw_x1 || y <= -48 || y >= VIEW_H) return;
    d = &de[nde];
    d->key = key; d->x = x; d->y = y; d->size = size; d->attr = attr;
    {
        s16 b = (key + 64) >> 3;
        u8 *l;
        if (b < 0) b = 0;
        if (b > 47) b = 47;
        for (l = &dhead[b]; *l != 255 && de[*l].key >= key; l = &dnext[*l]) ;   /* nearer (larger key) first */
        dnext[nde] = *l;
        *l = nde;
    }
    nde++;
}

static void wspr(s16 x, s16 y, u8 size, u16 attr)
{
    x -= camx;
    y -= camy;
    if (y < VIEW_H) spr(x, y, size, attr);
}

static void unit_bar(s16 x, s16 y, u8 cells, s16 hp, s16 hpmax, u8 pal)
{
    s16 fill;
    u8 k;
    if (x - camx < vw_x0 - 32 || x - camx > vw_x1 || y - camy < -8 || y - camy > VIEW_H) return;
    fill = divs((s32)hp * (cells * 8), hpmax);
    for (k = 0; k < cells; k++) {
        s16 f = fill - k * 8;
        wspr(x + k * 8, y, 0, ATTR(pal, 0, T_UBAR + (f < 0 ? 0 : (f > 8 ? 8 : f))));
    }
}

/* sprite direction for a facing: 0 = down, 1 = up, 2 = side; flip for the west half */
static const u8 sdir_of[8] = { 2, 0, 0, 0, 2, 1, 1, 1 };
static const u8 hdir_of[8] = { 2, 3, 0, 3, 2, 4, 1, 4 };   /* heroes: S, N, E, SE, NE; the west half h-flipped */

/* the team whose sight the picture shows: the player's (in split screen, the selected view's), or 2 for all */
static u8 vteam;
#define HIDDEN(h) (vteam < 2 && !SEEN(vteam, h))

static void draw_minimap(void)
{
    u8 i;
    for (i = 0; i < FIRST_CREEP; i++) {
        Unit *v = &un[i];
        if (!v->on) continue;
        if (i < NH) {
            if ((i == view && (vcount & 16)) || HIDDEN(i)) continue;
            spr((PX(v->x) >> 5) - 2, HUD_Y * 8 + (PX(v->y) >> 5) - 2, 0, ATTR(v->team + 2, 1, T_MARK + 1));
        } else
            spr((PX(v->x) >> 5) - 1, HUD_Y * 8 + (PX(v->y) >> 5) - 1, 0, ATTR(v->team + 2, 1, T_MARK));
    }
}

static void draw_scene(void)
{
    u8 i, h;
    nde = 0;
    memset(dhead, 255, sizeof(dhead));
    /* bodies, depth-sorted */
    for (i = 0; i < NU; i++) {
        Unit *v = &un[i];
        s16 x, y;
        u8 pal, sd;
        u16 fl;
        if (!v->on) continue;
        x = PX(v->x) - camx;
        y = PX(v->y) - camy;
        if (x < vw_x0 - 40 || x > vw_x1 + 40 || y < -40 || y > VIEW_H + 40) continue;
        pal = v->team + 2;
        sd = sdir_of[v->face & 7];
        fl = (v->face >= 3 && v->face <= 5) ? HFLIP : 0;
        switch (v->type) {
        case U_HERO: {           /* heroes keep their own colours on either side */
            Hero *H = &hr[i];
            if (HIDDEN(i)) break;
            pal = hero_pal[hk[i]];
            u8 f = (v->wind || H->chan_t || H->cast_lock || H->hook_st == 1) ? 2 : ((v->anim >> 3) & 1);
            if (v->stun && (vcount & 4)) break;
            if (v->hunger && (vcount & 8)) pal ^= 1;
            sd = hdir_of[v->face & 7];
            if (H->buf_t) {                                                 /* Blade Fury spin */
                u8 a = (vcount >> 2) & 7;
                sd = hdir_of[a];
                fl = a >= 3 && a <= 5 ? HFLIP : 0;
                f = 2;
            }
            pose_want[i] = sd * 3 + f;
            de_add(y, x - 16, y - 26, 0x0F, ATTR(pal, 0, T_HSLOT + times(16, i)) | fl);
            break;
        }
        case U_MELEE:
        case U_RANGED:
            if (v->hit & 2) pal ^= 1;
            de_add(y, x - 8, y - 12, 0x05,
                   ATTR(pal, 0, (v->type == U_MELEE ? T_MELEE : T_RANGED) + (sd * 2 + ((v->anim >> 2) & 1)) * 4) | fl);
            break;
        case U_WOLF:
        case U_OGRE:            /* the jungle: in the Radiant palette, as Roshan */
            pal = 2;
            if (v->hit & 2) pal = 3;
            de_add(y, x - 12, y - 20, 0x0A,
                   ATTR(pal, 0, T_MATCH + (v->type == U_WOLF ? NA_WOLF : NA_OGRE) + times(sd, 18) + ((v->anim >> 2) & 1) * 9) | fl);
            break;
        case U_RAX:
            de_add(y + 8, x - 12, y - 18, 0x0A, ATTR(pal, 0, T_RAX));
            break;
        case U_ROSH: {          /* 48x48 in four 24x24 pieces: standing, or reared up to strike */
            u16 a = ATTR(2, 0, T_ROSH + (v->wind || rosh_slam > 184 ? 36 : 0)) | (v->face >= 3 && v->face <= 5 ? HFLIP : 0);
            s16 l = fl ? x : x - 24, r = fl ? x - 24 : x;
            if (v->hit & 2) a ^= 0x2000;         /* a flash of the other palette when hit */
            de_add(y, l, y - 42, 0x0A, a);
            de_add(y, r, y - 42, 0x0A, a + 9);
            de_add(y, l, y - 18, 0x0A, a + 18);
            de_add(y, r, y - 18, 0x0A, a + 27);
            break;
        }
        case U_TOWER:
            de_add(y + 8, x - 16, y - 40, 0x0F, ATTR(pal, 0, T_TOWER));      /* 32x48: crown and pillar, */
            de_add(y + 8, x - 16, y - 8, 0x0D, ATTR(pal, 0, T_TOWER_B));    /* then the plinth */
            break;
        default:
            de_add(y + 16, x - 32, y - 50, 0x0F, ATTR(pal, 0, T_MATCH + NA_ANCIENT));      /* 64x64 in four */
            de_add(y + 16, x, y - 50, 0x0F, ATTR(pal, 0, T_MATCH + NA_ANCIENT + 16));
            de_add(y + 16, x - 32, y - 18, 0x0F, ATTR(pal, 0, T_MATCH + NA_ANCIENT + 32));
            de_add(y + 16, x, y - 18, 0x0F, ATTR(pal, 0, T_MATCH + NA_ANCIENT + 48));
        }
    }
    /* the neutral camps: a clearing with a fire, under the creeps */
    for (i = 0; i < NCAMP; i++) {
        s16 cx = camp_x[i] - camx, cy = camp_y[i] - camy;
        if (cx > -24 && cx < 344 && cy > -24 && cy < 240)
            de_add(cy - 32, cx - 16, cy - 12, 0x0E, ATTR(2, 0, T_MATCH + NA_CAMP));
    }
    /* runes, bobbing */
    for (i = 0; i < 4; i++)
        if (rune_on[i]) {
            s16 rx = rune_x[i] - camx, ry = rune_y[i] - camy;
            de_add(ry, rx - 8, ry - 12 + (sintab[(game_t >> 1) & 63] >> 5), 0x05, ATTR(2, 0, T_RUNE + ((rune_on[i] - 1) << 2)));
        }
    /* hero bars above everything, with the rune in effect and the Aegis beside them */
    for (i = 0; i < nh; i++)
        if (un[i].on && !HIDDEN(i)) {
            s16 hx = PX(un[i].x), hy = PX(un[i].y);
            unit_bar(hx - 12, hy - 30, 3, un[i].hp, un[i].hpmax, un[i].team + 2);
            if (hr[i].rune_t) wspr(hx - 21, hy - 32, 0, ATTR(2, 1, T_RUNEM + hr[i].rune));
            if (aegis == (s8)i) wspr(hx + 12, hy - 32, 0, ATTR(2, 1, T_AEGIS));
        }
    {
        s8 b;
        for (b = 47; b >= 0; b--)
            for (i = dhead[b]; i != 255; i = dnext[i]) {
                DrawEnt *d = &de[i];
                spr(d->x, d->y, d->size, d->attr);
            }
    }
    /* creep & building bars */
    for (i = FIRST_BLD; i < NU; i++) {
        Unit *v = &un[i];
        if (!v->on || v->hp >= v->hpmax) continue;
        if (v->type == U_TOWER) unit_bar(PX(v->x) - 12, PX(v->y) - 46, 3, v->hp, v->hpmax, v->team + 2);
        else if (v->type == U_ANCIENT) unit_bar(PX(v->x) - 16, PX(v->y) - 56, 4, v->hp, v->hpmax, v->team + 2);
        else if (v->type == U_ROSH) unit_bar(PX(v->x) - 16, PX(v->y) - 48, 4, v->hp, v->hpmax, 3);
        else if (v->type == U_RAX) unit_bar(PX(v->x) - 12, PX(v->y) - 24, 3, v->hp, v->hpmax, v->team + 2);
        else if (v->team > 1) unit_bar(PX(v->x) - 4, PX(v->y) - 16, 1, v->hp, v->hpmax, 3);
        else unit_bar(PX(v->x) - 4, PX(v->y) - 16, 1, v->hp, v->hpmax, v->team + 2);
    }
    /* hook & rot */
    for (h = 0; h < nh; h++) if (hk[h] == K_PUDGE && un[h].on) {
        Hero *H = &hr[h];
        s16 ux = PX(un[h].x), uy = PX(un[h].y) - 10;
        if (H->hook_st) {
            s16 hx = PX(H->hx), hy = PX(H->hy), d = dist(hx - ux, hy - uy);
            s16 n = divs(d, 10), k, sx = 0, sy = 0, ex = 0, ey = 0;
            wspr(hx - 4, hy - 4, 0, ATTR(2, 0, T_HOOK));
            if (n > 0) {
                ex = divs((s32)(s16)(hx - ux) << 6, n);
                ey = divs((s32)(s16)(hy - uy) << 6, n);
            }
            for (k = 1; k < n && k < 16; k++) {
                sx += ex;
                sy += ey;
                wspr(ux + (sx >> 6) - 4, uy + (sy >> 6) - 4, 0, ATTR(2, 0, T_CHAIN));
            }
        }
        if (H->rot && !HIDDEN(h))
            for (i = 0; i < 4; i++) {
                u8 a = (u8)((game_t << 1) + (i << 4));
                wspr(ux + ((sintab[a & 63] * 24) >> 6) - 4, uy + 8 + ((sintab[(a + 16) & 63] * 16) >> 6) - 4,
                     0, ATTR(2, 0, T_ROT));
            }
    }
    /* projectiles */
    for (i = 0; i < NP; i++) {
        Proj *p = &pj[i];
        u8 pal;
        if (!p->on) continue;
        pal = p->src < NH ? 2 : un[(u8)p->src].team + 2;    /* hero shots in the hero's colours */
        switch (p->kind) {
        case PJ_SF: wspr(PX(p->x) - 4, PX(p->y) - 4, 0, ATTR(pal, 0, T_ORB_SF)); break;
        case PJ_CREEP: wspr(PX(p->x) - 4, PX(p->y) - 4, 0, ATTR(pal, 0, T_ORB_CREEP)); break;
        case PJ_TOWER:
        case PJ_BULLET: wspr(PX(p->x) - 4, PX(p->y) - 4, 0, ATTR(pal, 0, T_ORB_TOWER)); break;
        case PJ_ICE: wspr(PX(p->x) - 4, PX(p->y) - 4, 0, ATTR(pal, 0, T_ORB_ICE)); break;
        case PJ_FIRE: wspr(PX(p->x) - 4, PX(p->y) - 4, 0, ATTR(pal, 0, T_ORB_FIRE)); break;
        case PJ_POISON: wspr(PX(p->x) - 4, PX(p->y) - 4, 0, ATTR(pal, 0, T_ORB_POISON)); break;
        case PJ_LFIRE: wspr(PX(p->x) - 12, PX(p->y) - 12, 0x0A, ATTR(2, 0, T_FIRE + 9 + ((p->t >> 2) & 1) * 9)); break;
        case PJ_LROCK: wspr(PX(p->x) - 4, PX(p->y), 0, ATTR(2, 0, T_SPARK)); break;
        default: wspr(PX(p->x) - 8, PX(p->y) - 8, 0x05, ATTR(pal, 0, T_SOUL));
        }
    }
    /* effects */
    for (i = 0; i < NFX; i++) {
        Fx *f = &fxs[i];
        if (!f->on) continue;
        switch (f->kind) {
        case FX_RAZE: wspr(f->x - 12, f->y - 12, 0x0A, ATTR(2, 0, T_RAZE + (f->t / 6) * 9)); break;
        case FX_FIRE: wspr(f->x - 12, f->y - 12, 0x0A, ATTR(2, 0, T_FIRE + (f->t / 6) * 9)); break;
        case FX_ICE: wspr(f->x - 12, f->y - 12, 0x0A, ATTR(2, 0, T_ICE + (f->t / 6) * 9)); break;
        case FX_BOLT:
            if (f->t & 2) wspr(f->x - 4, f->y - 32, 0x03, ATTR(2, 0, T_BOLT));
            break;
        case FX_SPARK: wspr(f->x - 4, f->y - 4, 0, ATTR(2, 0, T_SPARK + (f->t >> 2))); break;
        case FX_POOF: wspr(f->x - 8, f->y - 8, 0x05, ATTR(2, 0, T_POOF + (f->t / 7) * 4)); break;
        case FX_RING:         /* Berserker's Call: a growing ring of sparks */
        case FX_HELIX: {      /* Counter Helix: blades spinning around Axe */
            u8 k, r = f->kind == FX_RING ? 8 + (f->t << 1) : 18;
            for (k = 0; k < 8; k++) {
                u8 a = (u8)((k << 3) + (f->kind == FX_HELIX ? f->t << 3 : 0));
                wspr(f->x + ((sintab[(a + 16) & 63] * r) >> 6) - 4, f->y + ((sintab[a & 63] * r) >> 7) - 4, 0,
                     ATTR(2, 0, f->kind == FX_RING ? T_SPARK : T_ORB_TOWER));
            }
            break;
        }
        case FX_DENY: wspr(f->x - 4, f->y - (f->t >> 2), 0, ATTR(1, 1, T_FONT + ('!' - 32))); break;
        default: {          /* "+NN" gold (yellow) or damage (red) popup, rising */
            char b[6];
            u8 k, s = 0, gold = f->kind != FX_DMG;
            s16 x;
            num(f->val, 4, b);
            while (s < 3 && b[s] == '0') s++;          /* strip leading zeros */
            x = f->x - ((4 - s + gold) << 2);
            if (gold) { wspr(x, f->y - (f->t >> 2), 0, ATTR(2, 1, T_DIGY + 10)); x += 8; }
            for (k = s; k < 4; k++, x += 8)
                wspr(x, f->y - (f->t >> 2), 0, ATTR(2, 1, (gold ? T_DIGY : T_DIGR) + b[k] - '0'));
        }
        }
    }
    /* SF channel aura */
    for (h = 0; h < nh; h++) if (hk[h] == K_SF && un[h].on && hr[h].chan_t && !HIDDEN(h))
        for (i = 0; i < 6; i++) {
            u8 a = (u8)((game_t << 2) + i * 11);
            wspr(PX(un[h].x) + ((sintab[a & 63] * 20) >> 6) - 4,
                 PX(un[h].y) - 10 + ((sintab[(a + 16) & 63] * 20) >> 6) - 4, 0, ATTR(2, 0, T_ORB_SF));
        }
}

static void draw_world(void)
{
    nspr = 0;
    if (split) {
        static u8 flip;
        static s16 scx[2], scy[2];
        u8 k, j;
        flip ^= 1;
        vsel(flip);
        vteam = port_of[0] == flip ? 0 : 1;
        sc_rec = flip;
        scn[flip] = 0;
        draw_scene();
        sc_rec = 0xFF;
        scx[flip] = camx;
        scy[flip] = camy;
        for (k = 0; k < 2; k++) {
            s16 dx, dy;
            vsel(k);
            dx = scx[k] - camx;
            dy = scy[k] - camy;
            for (j = 0; j < scn[k]; j++) {
                CSpr *c = &scache[k][j];
                spr(c->x + dx, c->y + dy, c->size, c->attr);
            }
        }
    } else {
        vteam = me < 2 ? me & 1 : 2;
        draw_minimap();
        draw_scene();
    }
    spr_finish();
}

static void update_fx(void)
{
    u8 i;
    static const u8 len[11] = { 18, 8, 14, 40, 40, 16, 12, 32, 18, 18, 12 };
    for (i = 0; i < NFX; i++)
        if (fxs[i].on && (fxs[i].t += DT) >= len[fxs[i].kind]) fxs[i].on = 0;
}

/* ================================================================ screens */

static void read_pads(void)
{
    u8 k;
    for (k = 0; k < 2; k++) {
        Hero *H = &hr[k];
        u16 old = H->pad, p = read_pad(port_of[k], &H->six);
        if (!H->six) {   /* 3-button fallback: A+B = X, B+C = Y, A+C = Z */
            if ((p & (B_A | B_B)) == (B_A | B_B)) p = (p & ~(B_A | B_B)) | B_X;
            else if ((p & (B_B | B_C)) == (B_B | B_C)) p = (p & ~(B_B | B_C)) | B_Y;
            else if ((p & (B_A | B_C)) == (B_A | B_C)) p = (p & ~(B_A | B_C)) | B_Z;
        }
        H->pad = p;
        H->pad_new = p & ~old;
    }
}

static void cam_clamp(void)
{
    if (camx < 0) camx = 0;
    if (camx > WORLD - VIEW_W) camx = WORLD - VIEW_W;
    if (camy < 0) camy = 0;
    if (camy > WORLD - VIEW_H) camy = WORLD - VIEW_H;
}

/* slow pan along the mid lane, used behind the title and hero select */
static void title_cam(u16 t)
{
    s16 p = (sintab[(t >> 4) & 63] * 300) >> 6;
    camx = ((WORLD + p) >> 1) - 160;
    camy = ((WORLD - p) >> 1) - 96 + ((sintab[((t >> 3) + 16) & 63] * 40) >> 6);
    cam_clamp();
}

static void title(void)
{
    u8 x, y;
    u16 t = 0;
    port_of[0] = 0;
    port_of[1] = 1;
    display(0);
    clear_planeA();
    for (y = HUD_Y; y < 28; y++) clearW(y);
    pal_set(0, pal_map); pal_set(1, pal_logo); pal_set(2, pal_rad); pal_set(3, pal_dire);
    pal_upload(0);
    title_cam(0);
    map_load();
    for (y = 0; y < 4; y++) {
        VDP_CTRL32 = VRAM_W(PLANE_A + ((u16)(6 + y) << 7) + (((40 - LOGO_W) >> 1) << 1));
        for (x = 0; x < LOGO_W; x++) {
            u16 v = map_logo[y * LOGO_W + x];
            VDP_DATA = v ? ATTR(1, 1, v) : 0;
        }
    }
    textA_c(11, "- 16 BIT MOBA -");
    textW(7, 25, "A DOTA 2 FAN PROJECT  2026");
    nspr = 0; spr_finish();
    flush();
    display(1);
    fade(1);
    music_play(0, 7);
    for (;;) {
        flush();
        read_pads();
        title_cam(t);
        if ((t & 31) == 0) textA_c(14, "PRESS START");
        if ((t & 31) == 20) clearA(14);
        t++;
        if ((hr[0].pad_new | hr[1].pad_new) & (B_START | B_A)) {
            rs ^= vcount | 1;
            sfx_play(SFX_START);
            break;
        }
    }
    fade(0);
}

/* hero select: your hero, your side and the enemy hero; returns your slot, or 2 to watch bots */
static void pick_row(u8 y, const char *label, const char *val)
{
    char b[28];
    u8 j = 0;
    while (*label) b[j++] = *label++;
    b[j++] = '<';
    b[j++] = ' ';
    while (*val) b[j++] = *val++;
    while (j < 23) b[j++] = ' ';
    b[j++] = '>';
    b[j] = 0;
    textA(10, y, b);
}

/* ---------------------------------------------------------- battery save (SRAM, odd bytes at 0x200001) */
#define SRAM_B(i) (*(volatile u8 *)(0x200001 + ((i) << 1)))
#define SAVE_LEN 17
/* magic, version, hero, side, enemy, wins, losses, tips on, tips already shown (bits),
   teams (0 1v1, 1 2v2, 2 3v3), ally, second enemy, game mode, second ally, third enemy, checksum */
static u8 save[SAVE_LEN] = { 'A', 'W', 5, K_SF, 0, K_PUDGE, 0, 0, 1, 0, 0, K_AXE, K_AXE, 0, K_LINA, K_CM, 0 };
enum { SV_HERO = 3, SV_SIDE, SV_ENEMY, SV_WINS, SV_LOSS, SV_TIPS, SV_SEEN, SV_2V2, SV_ALLY, SV_EN2, SV_GAME,
       SV_ALLY2, SV_EN3, SV_SUM };

static u8 save_sum(const u8 *b) { u8 k, c = 0x5A; for (k = 0; k < SV_SUM; k++) c += b[k]; return c; }

static void save_load(void)
{
    u8 b[SAVE_LEN], k;
    *(volatile u8 *)0xA130F1 = 1;           /* map SRAM in (only matters on big ROMs) */
    for (k = 0; k < SAVE_LEN; k++) b[k] = SRAM_B(k);
    if (b[0] == 'A' && b[1] == 'W' && b[2] == 5 && b[SV_SUM] == save_sum(b) &&
        b[SV_HERO] < NHERO && b[SV_ENEMY] < NHERO && b[SV_SIDE] < 2 && b[SV_2V2] < 3 &&
        b[SV_ALLY] < NHERO && b[SV_EN2] < NHERO && b[SV_GAME] < 3 && b[SV_ALLY2] < NHERO && b[SV_EN3] < NHERO)
        for (k = 0; k < SAVE_LEN; k++) save[k] = b[k];
}

static void save_write(void)
{
    u8 k;
    save[SV_SUM] = save_sum(save);
    for (k = 0; k < SAVE_LEN; k++) SRAM_B(k) = save[k];
}


/* screen 1: the game mode. rows: 0 game (1 player / split screen / watch), 1 teams, 2 side, 3 tips.
   Returns 0 to go on to the draft */
static void mode_screen(void)
{
    static const char *const games[3] = { "1 PLAYER", "2P SPLITSCREEN", "BOT VS BOT" };
    static const char *const teams[3] = { "1V1", "2V2 WITH BOTS", "3V3 WITH BOTS" };
    u8 row = 0, y;
    u16 t = 0;
    clear_band();
    for (y = 0; y < 24; y++) clearA(y);
    for (y = HUD_Y; y < 28; y++) clearW(y);
    pal_set(1, pal_ui);
    textA_c(5, "GAME MODE");
    panelA(6, 34, 9, 15);
    {
        char b[24] = "RECORD  W ";
        num(save[SV_WINS], 3, b + 10);
        b[13] = b[14] = b[16] = ' ';
        b[15] = 'L';
        num(save[SV_LOSS], 3, b + 17);
        textW(2, 24, b);
    }
    textW(2, 25, "UP/DOWN: CHOOSE   LEFT/RIGHT: CHANGE");
    textW(2, 26, "A OR START: PICK HEROES");
    fade(1);
    for (;;) {
        u16 n;
        s8 dx = 0;
        if (save[SV_GAME] == 1) save[SV_2V2] = 0;          /* split screen is always 1v1 */
        pick_row(10, "GAME   ", games[save[SV_GAME]]);
        pick_row(11, "TEAMS  ", teams[save[SV_2V2]]);
        pick_row(12, "SIDE   ", save[SV_GAME] == 1 ? (save[SV_SIDE] ? "P1 DIRE" : "P1 RADIANT")
                                                   : (save[SV_SIDE] ? "DIRE" : "RADIANT"));
        pick_row(13, "TIPS   ", save[SV_TIPS] ? "ON" : "OFF");
        flush();
        read_pads();
        title_cam(t);
        n = hr[0].pad_new;
        if (n & B_UP) row = row ? row - 1 : 0;
        if (n & B_DOWN) row = row < 3 ? row + 1 : 3;
        if (n & B_LEFT) dx = -1;
        if (n & B_RIGHT) dx = 1;
        if (dx) {
            if (row == 0) save[SV_GAME] = dx > 0 ? (save[SV_GAME] == 2 ? 0 : save[SV_GAME] + 1) : (save[SV_GAME] ? save[SV_GAME] - 1 : 2);
            else if (row == 1 && save[SV_GAME] != 1)
                save[SV_2V2] = dx > 0 ? (save[SV_2V2] == 2 ? 0 : save[SV_2V2] + 1) : (save[SV_2V2] ? save[SV_2V2] - 1 : 2);
            else if (row == 2) save[SV_SIDE] ^= 1;
            else if (row == 3) { save[SV_TIPS] ^= 1; if (save[SV_TIPS]) save[SV_SEEN] = 0; }   /* on = replay them */
        }
        if (n & (B_LEFT | B_RIGHT | B_DOWN | B_UP)) sfx_play(SFX_HIT);
        t++;
        nspr = 0;
        if (t & 16) spr(66, (row + 10) << 3, 0, ATTR(1, 1, T_FONT + ('>' - 32)));
        spr_finish();
        if (n & (B_START | B_A)) { sfx_play(SFX_START); break; }
    }
    fade(0);
    afont = T_FONT;
}

/* screen 2: the draft. Each slot picks in turn on a 5x2 hero grid: A locks the pick, B steps back
   (from the first pick back to the mode screen). In split screen player 2 picks the enemy with pad 2.
   Returns 0 when done, 1 to go back */
static u8 draft(void)
{
    static const char *const role[NHERO] = { "RANGED CARRY", "MELEE DISABLER", "MELEE INITIATOR", "RANGED CARRY",
                                             "RANGED NUKER", "RANGED NUKER", "RANGED SUPPORT", "RANGED CARRY",
                                             "RANGED CARRY", "MELEE CARRY" };
    static const char *const label[6] = { "YOU    ", "ENEMY  ", "ALLY   ", "ENEMY 2", "ALLY 2 ", "ENEMY 3" };
    static const char *const title[2][6] = { { "PICK YOUR HERO", "PICK THE ENEMY HERO", "PICK YOUR ALLY",
                                               "PICK THE SECOND ENEMY", "PICK YOUR SECOND ALLY", "PICK THE THIRD ENEMY" },
                                             { "RADIANT PICKS", "DIRE PICKS", "RADIANT PICKS AN ALLY", "DIRE PICKS AN ALLY",
                                               "RADIANT PICKS AN ALLY", "DIRE PICKS AN ALLY" } };
    u8 *slot[6], cur, ns = (save[SV_2V2] + 1) << 1, k, y, shown = 255, back = 0, game = save[SV_GAME];
    s8 at = 0;
    u16 t = 0;
    slot[0] = &save[SV_HERO]; slot[1] = &save[SV_ENEMY]; slot[2] = &save[SV_ALLY]; slot[3] = &save[SV_EN2];
    slot[4] = &save[SV_ALLY2]; slot[5] = &save[SV_EN3];
    if (game == 1) ns = 2;
    for (y = 0; y < 24; y++) clearA(y);
    for (y = HUD_Y; y < 28; y++) clearW(y);
    for (k = 0; k < NHERO; k++) {          /* facing down: standing and attacking */
        hero_tiles(k, 0, 16, T_DHERO(k));
        hero_tiles(k, 32, 16, T_DHERO(k) + 16);
    }
    pal_set(1, pal_ui);
    panelA(1, 39, 12, 23);
    textW(2, 25, "D-PAD: HERO   A: PICK   B: BACK");
    cur = *slot[0];
    fade(1);
    for (;;) {
        u16 n;
        u8 pad = game == 1 && at == 1;              /* player 2 drafts the enemy */
        if (shown != (cur | (at << 4))) {
            char b[40];
            const char *m;
            u8 j, w, o;
            shown = cur | (at << 4);
            clearA(1);
            textA_c(1, game == 1 ? (at == 1 ? "PLAYER 2: PICK YOUR HERO" : "PLAYER 1: PICK YOUR HERO")
                                  : title[game == 2][at]);
            w = slen(hero_name[cur]) + 3 + slen(role[cur]);
            for (j = 0; j < 38; j++) b[j] = ' ';
            b[38] = 0;
            o = (38 - w) >> 1;
            for (j = 0, m = hero_name[cur]; *m; ) b[o + j++] = *m++;
            b[o + j + 1] = '-';
            for (j += 3, m = role[cur]; *m; ) b[o + j++] = *m++;
            textA(1, 12, b);
            {                       /* the four skills: icon, name, and whether it is the ultimate or a passive */
                const u32 *src = skill_icons + times(128, cur);
                u16 w;
                VDP_CTRL32 = VRAM_W(T_DICON << 5);
                for (w = 128; w; w--) VDP_DATA32 = *src++;
            }
            for (k = 0; k < 4; k++) {
                u8 x = (k & 1) ? 20 : 2, yy = 13 + ((k >> 1) << 1);
                u16 at = ATTR(2, 1, T_DICON + (k << 2));
                VDP_CTRL32 = VRAM_W(PLANE_A + ((u16)yy << 7) + (x << 1));
                VDP_DATA = at; VDP_DATA = at + 2;
                VDP_CTRL32 = VRAM_W(PLANE_A + ((u16)(yy + 1) << 7) + (x << 1));
                VDP_DATA = at + 1; VDP_DATA = at + 3;
                for (j = 0; j < 16; j++) b[j] = skill_name[cur][k][j];
                b[16] = 0;
                textA(x + 2, yy, b);
                m = k == 3 ? "ULTIMATE        " : ((cur == K_SF ? k == 1 || k == 2 : passive(cur, k)) ? "PASSIVE         " : "                ");
                textA(x + 2, yy + 1, m);
            }
            for (k = 0; k < 6; k++) {
                const char *v = k >= ns ? "" : (k < at ? hero_name[*slot[k]] : (k == at ? "..." : ""));
                for (j = 0; j < 30; j++) b[j] = ' ';
                b[30] = 0;
                b[0] = k == at ? '>' : ' ';
                for (j = 0, m = k < ns ? label[k] : ""; *m; ) b[2 + j++] = *m++;
                for (j = 0; *v; ) b[11 + j++] = *v++;
                textA(5, 18 + k, b);
            }
        }
        flush();
        read_pads();
        title_cam(t);
        n = hr[pad].pad_new;
        if (n & B_LEFT) cur = cur == 0 || cur == 5 ? cur + 4 : cur - 1;
        if (n & B_RIGHT) cur = cur == 4 || cur == 9 ? cur - 4 : cur + 1;
        if (n & (B_UP | B_DOWN)) cur = cur < 5 ? cur + 5 : cur - 5;
        if (n & (B_LEFT | B_RIGHT | B_DOWN | B_UP)) sfx_play(SFX_HIT);
        if (n & (B_A | B_START | B_C)) {
            *slot[at] = cur;
            sfx_play(SFX_START);
            if (++at == ns) break;
            cur = *slot[at];
        } else if (n & B_B) {
            sfx_play(SFX_HIT);
            if (!at) { back = 1; break; }
            cur = *slot[--at];
        }
        t++;
        nspr = 0;
        for (k = 0; k < NHERO; k++) {
            s16 gx = 36 + times(56, k < 5 ? k : k - 5), gy = k < 5 ? 28 : 64;
            u8 m, tx = 0;
            char tag[6];
            for (m = 0; m < at; m++)
                if (*slot[m] == k) tag[tx++] = "PEAEAE"[m];
            spr(gx - 4, gy - 6, 0x0F, ATTR(hero_pal[k], 0, T_DHERO(k) + (k == cur && (t & 32) ? 16 : 0)));
            for (m = 0; m < tx; m++)
                spr(gx + 12 - (tx << 2) + (m << 3), gy + 25, 0, ATTR(1, 1, T_FONT + (tag[m] - 32)));
            if (k == cur && (t & 16)) {
                spr(gx - 10, gy + 8, 0, ATTR(1, 1, T_FONT + ('>' - 32)));
                spr(gx + 26, gy + 8, 0, ATTR(1, 1, T_FONT + ('<' - 32)));
            }
        }
        spr_finish();
    }
    fade(0);
    afont = T_FONT;
    return back;
}

/* mode screen, then the draft; returns the side played, 2 (watch) or 3 (split screen) */
static u8 pick(void)
{
    u8 side, game;
    save_load();                /* re-read: a web emulator may restore SRAM after boot */
    do mode_screen(); while (draft());
    save_write();
    side = save[SV_SIDE];
    game = save[SV_GAME];
    nh = game == 1 ? 2 : (save[SV_2V2] + 1) << 1;
    hk[side] = save[SV_HERO];
    hk[side ^ 1] = save[SV_ENEMY];
    hk[side + 2] = save[SV_ALLY];
    hk[(side ^ 1) + 2] = save[SV_EN2];
    hk[side + 4] = save[SV_ALLY2];
    hk[(side ^ 1) + 4] = save[SV_EN3];
    return game == 1 ? 3 : (game == 2 ? 2 : side);
}

static u8 tip_t;

static void match_init(u8 mode)
{
    u8 k;
    memset(un, 0, sizeof(un));
    memset(pj, 0, sizeof(pj));
    memset(fxs, 0, sizeof(fxs));
    for (k = 0; k < NH; k++) { pose_want[k] = 0; pose_have[k] = 255; }
    in_match = 1;
    fronts_update();       /* no creeps yet: no fronts */
    for (k = 0; k < nh; k++) {
        u8 six = hr[k].six;
        u16 pad = hr[k].pad;
        memset(&hr[k], 0, sizeof(Hero));
        hr[k].six = six;
        hr[k].pad = pad;
        hr[k].lvl = 1;
        hr[k].gold = 600;
        hr[k].bot = mode < 2 ? mode != k : mode == 2;   /* 2 = watch: all bots, 3 = split: none */
        hr[k].sk[0] = 1;        /* level 1 starts with the first skill learned */
        hr[k].chan_tgt = hr[k].hook_tgt = -1;
        hr[k].hold_k = 255;
        un[k].type = U_HERO;
        un[k].team = k & 1;
        un[k].killer = -1;
        refresh_max(k);
        un[k].hp = un[k].hpmax;
        hr[k].mana = hr[k].manamax;
        respawn(k);
    }
    for (k = 0; k < NBLD; k++) {
        Unit *b = &un[FIRST_BLD + k];
        u8 s = slot_tab[k], team = k >= 13;
        b->on = 1;
        b->type = s == B_ANCIENT ? U_ANCIENT : (s >= B_RAX ? U_RAX : U_TOWER);
        b->team = team;
        b->x = FX(team ? WORLD - bld_x[s] : bld_x[s]);
        b->y = FX(team ? WORLD - bld_y[s] : bld_y[s]);
        b->hpmax = b->hp = b->type == U_ANCIENT ? 2400 : (b->type == U_RAX ? ((s - B_RAX) & 1 ? 900 : 1300) : 1100);
        b->tgt = -1;
        b->killer = -1;
    }
    lanes_init();
    rosh_t = 0;
    rosh_slam = 0;
    aegis = -1;
    game_sec = 0;
    rosh_spawn();
    rax_down[0] = rax_down[1] = 0;
    for (k = 0; k < NCAMP; k++) camp_spawn(k);
    {
        u16 w;
        VDP_CTRL32 = VRAM_W(T_MATCH << 5);
        for (w = 0; w < MATCH_TILES * 8; w++) VDP_DATA32 = match_art[w];
        VDP_CTRL32 = VRAM_W(T_CLOCK << 5);
        for (w = 0; w < CLOCK_TILES * 8; w++) VDP_DATA32 = clock_art[w];
    }
    memset(rune_on, 0, sizeof(rune_on));
    rune_spawn(2, R_BOUNTY);            /* bounty runes at the horn, power runes from 2:00 */
    rune_spawn(3, R_BOUNTY);
    power_t = 120;
    bounty_t = 180;
    versus = mode == 3;
    me = mode < 2 ? mode : 255;
    port_of[0] = me == 1;       /* the human always uses controller 1 */
    port_of[1] = me != 1;
    view = mode < 2 ? mode : 0;
    if (versus) {               /* player 1 (pad 1) plays the side chosen on the pick screen */
        port_of[save[SV_SIDE]] = 0;
        port_of[save[SV_SIDE] ^ 1] = 1;
        me = view = save[SV_SIDE];
    }
    winner = 0;
    game_t = game_sec = sec_f = 0;
    dn_sec = dn_lvl = 0;
    seen[0] = seen[1] = 0x3F;
    stc = half = bot_ph = 0;
    pad_acc[0] = pad_acc[1] = 0;
    wave_t = 150;
    waves = 0;
    first_blood = 0;
    streak[0] = streak[1] = 0;
    tip_t = 0;
    shop_open = paused = board = learn_open = 0;
    msg_t = 0;
    hud_dirty = 1;
}

/* ------------------------------------------------------------- tutorial tips, each shown once */
static void tips_update(void)
{
    static const char *const tips[8] = {
        "TIP: D-PAD MOVES   A ATTACKS", "TIP: LAST HIT CREEPS WITH A FOR GOLD",
        "TIP: HIT YOUR OWN WEAK CREEP TO DENY", "TIP: B C X Y CAST YOUR SKILLS",
        "TIP: HOLD A SKILL KEY TO LEARN IT", "TIP: LOW HP - RUN BACK TO FOUNTAIN",
        "TIP: START AT FOUNTAIN OPENS THE SHOP", "TIP: 3-BUTTON PAD A+B=X B+C=Y A+C=Z" };
    Hero *H = &hr[me];
    Unit *U = &un[me];
    static const u8 order[8] = { 5, 4, 6, 0, 1, 3, 2, 7 };   /* urgent ones first */
    u8 seen = save[SV_SEEN], j, k = 8;
    if (tip_t) { DECN(tip_t, DT); if (!tip_t) clearA(4); }
    if (tip_t || !save[SV_TIPS] || (game_t & 15)) return;
    for (j = 0; j < 8 && k > 7; j++) {
        u8 c, n = order[j];
        if (seen & (1 << n)) continue;
        switch (n) {
        case 0: c = game_t > 90; break;
        case 1: c = (seen & 1) && game_t > 1500; break;
        case 2: c = (seen & 2) && game_t > 2700; break;
        case 3: c = (seen & 1) && game_t > 600 && U->on && H->mana >= 80; break;
        case 4: c = H->pts && game_t > 300; break;
        case 5: c = U->on && (U->hp << 2) < U->hpmax; break;
        case 6: c = game_t > 600 && U->on && H->gold >= 400 &&
                    dist(PX(U->x) - fountain_x[me & 1], PX(U->y) - fountain_y[me & 1]) < 96; break;
        default: c = !H->six && game_t > 3000;
        }
        if (c) k = n;
    }
    if (k > 7 || (save[SV_SEEN] & (1 << k))) return;
    save[SV_SEEN] |= 1 << k;
    if (save[SV_SEEN] == 0xFF) save[SV_TIPS] = 0;   /* tutorial finished */
    save_write();
    clearA(4);
    textA_c(4, tips[k]);
    tip_t = 240;
    sfx_play(SFX_PICKUP);
}

/* end of match: VICTORY/DEFEAT for the player (or the winning side when watching) and a stats table */
static void result(void)
{
    static const char *const rows[9] = { "HERO", "LEVEL", "KILLS", "DEATHS", "LAST HITS", "DENIES",
                                         "GOLD EARNED", "HERO DAMAGE", "TOWERS" };
    static const char *const rows3[9] = { "", "LV", "K", "D", "LH", "DN", "GLD", "DMG", "TWR" };
    u16 t = 0;
    u8 k, y;
    char b[8];
    for (y = 0; y < HUD_Y; y++) clearA(y);
    panelA(0, 40, 0, HUD_Y - 1);
    if (versus) textA_c(3, port_of[winner - 1] ? "PLAYER 2 WINS!" : "PLAYER 1 WINS!");
    else if (me < NH) textA_c(3, un[me].team == winner - 1 ? "*  V I C T O R Y  *" : "D E F E A T");
    else textA_c(3, winner == 1 ? "RADIANT VICTORY" : "DIRE VICTORY");
    textA_c(5, winner == 1 ? "THE RADIANT ARE VICTORIOUS!" : "THE DIRE ARE VICTORIOUS!");
    clock_text(b);
    textA(15, 6, "TIME ");
    textA(20, 6, b);
    textA(nh > 4 ? 9 : 15, 8, "RADIANT");
    textA(nh > 4 ? 28 : 28, 8, "DIRE");
    for (y = 0; y < 9; y++) textA(nh > 4 ? 1 : 2, 10 + y, nh > 4 ? rows3[y] : rows[y]);
    for (k = 0; k < nh; k++) {     /* 1v1: two wide columns; 2v2, 3v3: narrow ones, Radiant first */
        static const u8 x4[4] = { 14, 20, 28, 34 }, x6[6] = { 5, 11, 17, 23, 29, 35 };
        u8 h = k < (nh >> 1) ? k << 1 : ((k - (nh >> 1)) << 1) + 1;
        Hero *H = &hr[h];
        u8 x = nh > 4 ? x6[k] : (nh > 2 ? x4[k] : (k ? 28 : 15));
        textA(x, 10, nh > 2 ? hero_short[hk[h]] : hero_name[hk[h]]);
        {
            const u16 v[8] = { H->lvl, H->kills, H->deaths, H->lasthits, H->denies, H->earned, H->hdmg,
                               h < 2 ? H->towers : 0 };
            for (y = 0; y < 8; y++) {
                u8 z = 0;
                num(v[y], 5, b);
                while (z < 4 && b[z] == '0') z++;     /* no leading zeros */
                textA(x, 11 + y, b + z);
            }
        }
    }
    music_stop();
    sfx_play(SFX_START);
    if (me < NH && !versus) {
        u8 *c = &save[un[me].team == winner - 1 ? SV_WINS : SV_LOSS];
        if (*c < 255) (*c)++;
        save_write();
    }
    for (;;) {
        flush();
        read_pads();
        if ((t & 31) == 0) textA_c(20, "PRESS START");
        if ((t & 31) == 20) textA_c(20, "           ");
        if (t++ > 60 && ((hr[0].pad_new | hr[1].pad_new) & B_START)) break;
    }
    afont = T_FONT;
    fade(0);
}

static void cam_follow1(u8 slot, s16 ox, s16 oy, u8 snap)
{
    s16 wx = PX(un[slot].x) - ox, wy = PX(un[slot].y) - oy;
    if (!un[slot].on) { wx = fountain_x[slot & 1] - ox; wy = fountain_y[slot & 1] - oy; }
    if (snap) { camx = wx; camy = wy; }
    else {
        camx += (wx - camx) >> 2;
        camy += (wy - camy) >> 2;
        if (ABS(wx - camx) < 4) camx = wx;
        if (ABS(wy - camy) < 4) camy = wy;
    }
}

/* split screen: each player's view centred on their hero */
static void cam_split(u8 snap)
{
    u8 k;
    for (k = 0; k < 2; k++) {
        u8 slot = port_of[0] == k ? 0 : 1;          /* pad 1 plays on the left */
        vsel(k);
        cam_follow1(slot, k ? 244 : 80, SPLIT_H / 2, snap);
        if (camx < (k ? -168 : 0)) camx = k ? -168 : 0;
        if (camx > WORLD - (k ? 320 : 160)) camx = WORLD - (k ? 320 : 160);
        if (camy < 0) camy = 0;
        if (camy > WORLD - SPLIT_H) camy = WORLD - SPLIT_H;
    }
}

static void cam_follow(u8 snap)
{
    if (split) { cam_split(snap); return; }
    s16 wx = PX(un[view].x) - VIEW_W / 2, wy = PX(un[view].y) - VIEW_H / 2;
    if (!un[view].on) { wx = fountain_x[view & 1] - VIEW_W / 2; wy = fountain_y[view & 1] - VIEW_H / 2; }
    if (snap) { camx = wx; camy = wy; }
    else {
        camx += (wx - camx) >> 1;      /* once a step: twice the catch-up of a frame */
        camy += (wy - camy) >> 1;
        if (ABS(wx - camx) < 4) camx = wx;
        if (ABS(wy - camy) < 4) camy = wy;
    }
    cam_clamp();
}


static void split_on(void)
{
    u8 x, y;
    split = 1;
    scn[0] = scn[1] = 0;
    vdp_reg(0x11, 0x80 | 10);       /* window: columns 20-39 ... */
    vdp_reg(0x12, 0x80 | 23);       /* ... and rows 23-27 */
    for (y = 0; y < 23; y++) {
        VDP_CTRL32 = VRAM_W(WINDOW + ((u16)y << 7) + (20 << 1));
        VDP_DATA = ATTR(1, 1, T_FONTW);         /* 8 px opaque, high-priority divider hides sprite overhang */
        for (x = 21; x < 40; x++) VDP_DATA = 0; /* see-through to plane B */
    }
    for (y = 23; y < 28; y++) clearW(y);
    vsel(1);
}

static void split_off(void)
{
    split = 0;
    vsel(1);
    vdp_reg(0x11, 0x00);
    vdp_reg(0x12, 0x98);
    clear_planeA();
}


/* part 0 runs in the first half of a step, part 1 in the second: each takes half of the creeps due */
static void creeps_update(u8 part)
{
    u8 i;
    for (i = FIRST_CREEP; i < ROSH; i++) {
        s16 sx, sy;
        if (!un[i].on) continue;
        sx = PX(un[i].x) - camx;
        sy = PX(un[i].y) - camy;
        if (split) {            /* near either half, with tighter margins than one full view */
            if (!(sx > 168 - 48 && sx < VIEW_W + 48 && sy > -48 && sy < SPLIT_H + 48)) {
                sx = PX(un[i].x) - vcx[0];
                sy = PX(un[i].y) - vcy[0];
                if (!(sx > -48 && sx < 160 + 48 && sy > -48 && sy < SPLIT_H + 48)) sx = 9999;
            }
        }
        if (sx > -96 && sx < VIEW_W + 96 && sy > -96 && sy < VIEW_H + 96) {
            if (nh > 2) { if (!((i ^ stc) & 1) && ((i >> 1) & 1) == part) creep_update(i, 4); }   /* more heroes cost the time */
            else if ((i & 1) == part) creep_update(i, 2);
        } else if (!part) ;     /* off screen: all in the second half */
        else if (nh > 2) { if (!((i + stc) & 7)) creep_update(i, 16); }
        else if (!((i + stc) & 3)) creep_update(i, 8);
    }
}

static void match(u8 mode)
{
    display(0);
    match_init(mode);
    clear_planeA();
    pal_set(1, pal_ui);
    scn[0] = scn[1] = 0;
    if (versus) split_on();
    hud_static();
    hud_draw();
    cam_follow(1);
    if (split) { vsel(0); map_load(); vsel(1); }
    map_load();
    draw_world();
    flush();
    display(1);
    msg("WELCOME TO THE ANCIENT WARS", 150);
    fade(1);
    music_play(1, 7);

    for (;;) {
        u8 i;
        flush();
        read_pads();
        if (hud_dirty) { hud_dirty = 0; hud_draw(); }
        else if (half) hud_part(split ? 4 + (stc & 7) : stc & 3);   /* between the two halves of a step */
        if (winner) { draw_world(); if (split) split_off(); result(); return; }

        /* versus: whoever presses Start gets the menus */
        if (versus && !shop_open && !paused && !learn_open) {
            if (hr[0].pad_new & B_START) me = view = 0;
            else if (hr[1].pad_new & B_START) me = view = 1;
        }

        /* menus */
        if (me < 2) {
            Hero *H = &hr[me];
            if (H->pad_new & B_START) {
                if (shop_open || paused || learn_open) {
                    shop_open = paused = learn_open = 0;
                    clear_band();
                    music_pause(0);
                } else if (H->pts) {
                    learn_open = 1;
                    shop_sel = 0;
                    board = 0;
                    clear_band();
                    learn_draw();
                } else if (un[me].on && dist(PX(un[me].x) - fountain_x[me & 1], PX(un[me].y) - fountain_y[me & 1]) < 96) {
                    shop_open = 1;
                    shop_sel = 0;
                    board = 0;
                    shop_draw();
                } else {
                    paused = 1;
                    music_pause(1);
                    hud_dirty = 1;
                    panelA(15, 25, 8, 10);
                    textA_c(9, "PAUSED");
                    afont = T_FONT;
                }
            }
            if (shop_open) {
                if (H->pad_new & B_UP) shop_sel = shop_sel ? shop_sel - 1 : NITEM - 1;
                if (H->pad_new & B_DOWN) shop_sel = shop_sel < NITEM - 1 ? shop_sel + 1 : 0;
                if (H->pad_new & (B_A | B_B | B_C)) {
                    u8 bit = 1 << shop_sel;
                    if (!(H->items & bit) && H->gold >= item_price[shop_sel]) {
                        H->gold -= item_price[shop_sel];
                        H->items |= bit;
                        refresh_max(me);
                        sfx_play(SFX_PICKUP);
                    } else sfx_play(SFX_HIT);
                }
                if (H->pad_new & (B_UP | B_DOWN | B_A | B_B | B_C)) shop_draw();
                hud_draw();
                continue;
            }
            if (learn_open) {
                if (H->pad_new & B_UP) shop_sel = shop_sel ? shop_sel - 1 : 4;     /* four skills, attributes */
                if (H->pad_new & B_DOWN) shop_sel = shop_sel < 4 ? shop_sel + 1 : 0;
                if (H->pad_new & (B_A | B_B | B_C)) sfx_play(learn(me, shop_sel) ? SFX_PICKUP : SFX_HIT);
                if (!H->pts) { learn_open = 0; clear_band(); }
                else if (H->pad_new & (B_UP | B_DOWN | B_A | B_B | B_C)) learn_draw();
                hud_draw();
                continue;
            }
            if (paused) continue;
            if ((H->pad & B_MODE) != (board ? B_MODE : 0)) {
                board = (H->pad & B_MODE) ? 1 : 0;
                scoreboard(board);
            }
        } else if ((hr[0].pad_new | hr[1].pad_new) & B_START) {
            fade(0);
            return;
        }

        if (msg_t && --msg_t == 0) { clearA(6); if (split) hud_dirty = 1; }
        /* a logic step takes two frames: heroes, buildings and missiles in the first,
           creeps and the picture in the second (the sprites stay up in between) */
        pad_acc[0] |= hr[0].pad_new;          /* presses from both frames of a step count */
        pad_acc[1] |= hr[1].pad_new;
        if ((half ^= 1)) {
            hr[0].pad_new = pad_acc[0];
            hr[1].pad_new = pad_acc[1];
            pad_acc[0] = pad_acc[1] = 0;
            game_t += DT;
            stc++;
            if (++bot_ph == 6) bot_ph = 0;
            if ((sec_f += DT) == 60) {      /* every hero earns 1 gold a second, as in Dota */
                sec_f = 0;
                game_sec++;
                for (u8 k = 0; k < nh; k++) { hr[k].gold++; hr[k].earned++; }
                world_second();
            }
            build_lists();
            if ((stc & 3) == 0) vision_update();
            if ((wave_t -= DT) == 0) {
                spawn_wave();
                wave_t = 1800;
            }
            if (me < 2 && !un[me].on && hr[me].respawn && (game_t & 15) == 0) {
                char b[16] = "RESPAWN IN ";
                num(divs(hr[me].respawn + 59, 60), 2, b + 11);
                clearA(7);
                textA_c(7, b);
                if (hr[me].respawn < 16) clearA(7);
            }
            for (i = 0; i < nh; i++) hero_update(i);
            if ((game_t & 7) == 4) hunger_tick();
            creeps_update(0);
            for (i = FIRST_BLD; i < FIRST_CREEP; i++)
                if (un[i].on) building_update(i);
            rosh_update();
            neutrals_update();
            if ((stc & 1) == 0) runes_update();
            update_projectiles();
            update_fx();
            if (me < 2 && !versus) tips_update();
            if (split) { cam_follow(0); draw_world(); }     /* split screen draws one half a frame */
            continue;
        }
        build_lists();
        creeps_update(1);
        if (!(game_t & 15)) fronts_update();
        cam_follow(0);
        draw_world();
    }
}

int main(void)
{
    *(volatile u8 *)0xA10009 = 0x40;
    *(volatile u8 *)0xA1000B = 0x40;
    vdp_init();
    sound_init();
    nspr = 0;
    spr_finish();
    __asm__ volatile ("move.w #0x2000, %sr");
    for (;;) {
        title();
        match(pick());
        in_match = 0;
        dn_lvl = 0;         /* the menus by day */
    }
    return 0;
}
