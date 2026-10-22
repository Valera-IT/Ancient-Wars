/* VIPER STORM - sound driver running on the 68000 (Z80 kept halted).
 * FM: ch0 bass, ch1 lead, ch2 arpeggio, ch3 kick drum, ch4 lead echo.
 * PSG: ch0 shot sfx, ch1 misc sfx, ch2 noise pitch source, noise = drums/explosions. */
#include "md.h"
#include "sound.h"
#include "music.h"

#define YM   ((volatile u8 *)0xA04000)
#define PSG  (*(volatile u8 *)0xC00011)
#define Z80_BUSREQ (*(volatile u16 *)0xA11100)
#define Z80_RESET  (*(volatile u16 *)0xA11200)

typedef struct { u8 algfb; u8 op[4][6]; } Patch;   /* ops in register order S1,S3,S2,S4 */

static const Patch patch_bass = { 0x2C, {
    {0x01, 0x1E, 0x1F, 0x0D, 0x05, 0x6F},
    {0x01, 0x22, 0x1F, 0x0A, 0x05, 0x5F},
    {0x01, 0x08, 0x1F, 0x08, 0x03, 0x2F},
    {0x02, 0x12, 0x1F, 0x08, 0x03, 0x2F} } };
static const Patch patch_lead = { 0x24, {
    {0x01, 0x1C, 0x14, 0x05, 0x02, 0x1A},
    {0x02, 0x26, 0x1F, 0x06, 0x02, 0x1A},
    {0x01, 0x0E, 0x1F, 0x04, 0x02, 0x17},
    {0x31, 0x10, 0x1F, 0x04, 0x02, 0x17} } };
static const Patch patch_echo = { 0x24, {
    {0x01, 0x1C, 0x14, 0x05, 0x02, 0x1A},
    {0x02, 0x26, 0x1F, 0x06, 0x02, 0x1A},
    {0x01, 0x22, 0x1F, 0x04, 0x02, 0x17},
    {0x31, 0x24, 0x1F, 0x04, 0x02, 0x17} } };
static const Patch patch_arp = { 0x1C, {
    {0x03, 0x24, 0x1F, 0x10, 0x08, 0x8F},
    {0x01, 0x22, 0x1F, 0x10, 0x08, 0x8F},
    {0x01, 0x1A, 0x1F, 0x0E, 0x08, 0x6F},
    {0x02, 0x1E, 0x1F, 0x0E, 0x08, 0x6F} } };
static const Patch patch_kick = { 0x07, {
    {0x00, 0x7F, 0x1F, 0x00, 0x00, 0x0F},
    {0x00, 0x7F, 0x1F, 0x00, 0x00, 0x0F},
    {0x00, 0x7F, 0x1F, 0x00, 0x00, 0x0F},
    {0x01, 0x00, 0x1F, 0x0E, 0x0C, 0x2F} } };

static const u16 fnum_tab[12] = { 644, 682, 723, 766, 811, 859, 910, 965, 1022, 1083, 1147, 1215 };
static const u16 kick_tab[8] = { 1500, 1150, 900, 720, 600, 520, 480, 460 };
static const u8 snare_env[9] = { 0, 1, 3, 5, 7, 9, 11, 13, 15 };
static const u8 hat_env[4] = { 5, 8, 11, 15 };
static const u16 pickup_tab[4] = { 214, 170, 143, 107 };

static u8 mus_on, mus_paused, mus_tempo, mus_tick, mus_step;
static const u8 *m_bass, *m_lead, *m_arp, *m_drum;
static u8 kick_t = 0xFF, drum_t = 0xFF, drum_kind;
static volatile u8 req0, req1, reqn;
static u8 s0_id, s0_t, s1_id, s1_t, sn_id, sn_t;

/* ------------------------------------------------------------ YM2612 */
static void ym_write(u8 part, u8 reg, u8 val)
{
    u16 t = 0x400;
    while ((YM[0] & 0x80) && --t)
        ;
    YM[part << 1] = reg;
    YM[(part << 1) + 1] = val;
}

static u8 ch_code(u8 ch) { return ch < 3 ? ch : ch + 1; }
static void ym_keyoff(u8 ch) { ym_write(0, 0x28, ch_code(ch)); }
static void ym_keyon(u8 ch) { ym_write(0, 0x28, 0xF0 | ch_code(ch)); }

static void ym_freq(u8 ch, u8 block, u16 fnum)
{
    u8 part = ch >= 3, c = part ? ch - 3 : ch;
    ym_write(part, 0xA4 + c, (block << 3) | (fnum >> 8));
    ym_write(part, 0xA0 + c, fnum & 0xFF);
}

static void ym_note(u8 ch, u8 midi)
{
    u8 oct = 0;
    while (midi >= 12) { midi -= 12; oct++; }
    oct = oct ? oct - 1 : 0;
    if (oct > 7) oct = 7;
    ym_freq(ch, oct, fnum_tab[midi]);
}

static void ym_patch(u8 ch, const Patch *p)
{
    u8 part = ch >= 3, c = part ? ch - 3 : ch, s, o;
    for (s = 0; s < 4; s++) {
        o = (s << 2) + c;
        ym_write(part, 0x30 + o, p->op[s][0]);
        ym_write(part, 0x40 + o, p->op[s][1]);
        ym_write(part, 0x50 + o, p->op[s][2]);
        ym_write(part, 0x60 + o, p->op[s][3]);
        ym_write(part, 0x70 + o, p->op[s][4]);
        ym_write(part, 0x80 + o, p->op[s][5]);
        ym_write(part, 0x90 + o, 0);
    }
    ym_write(part, 0xB0 + c, p->algfb);
    ym_write(part, 0xB4 + c, 0xC0);
}

/* ------------------------------------------------------------ PSG */
static void psg_tone(u8 ch, u16 n) { PSG = 0x80 | (ch << 5) | (n & 0xF); PSG = (n >> 4) & 0x3F; }
static void psg_vol(u8 ch, u8 att) { PSG = 0x90 | (ch << 5) | (att & 0xF); }

/* ------------------------------------------------------------ API */
void sound_init(void)
{
    u8 ch;
    Z80_BUSREQ = 0x100;          /* take the Z80 bus for good */
    Z80_RESET = 0x100;           /* release reset (also un-resets the YM2612) */
    while (Z80_BUSREQ & 0x100)
        ;
    ym_write(0, 0x22, 0);        /* LFO off */
    ym_write(0, 0x27, 0);        /* normal ch3 mode, timers off */
    ym_write(0, 0x2B, 0);        /* DAC off */
    for (ch = 0; ch < 6; ch++) {
        ym_keyoff(ch);
        ym_patch(ch, &patch_kick);
        ym_write(ch >= 3, 0xB4 + (ch % 3), 0xC0);
    }
    for (ch = 0; ch < 4; ch++)
        psg_vol(ch, 15);
}

void music_play(u8 song, u8 tempo)
{
    mus_on = 0;
    if (song) { m_bass = mus2_bass; m_lead = mus2_lead; m_arp = mus2_arp; m_drum = mus2_drum; }
    else { m_bass = mus1_bass; m_lead = mus1_lead; m_arp = mus1_arp; m_drum = mus1_drum; }
    ym_patch(0, &patch_bass);
    ym_patch(1, &patch_lead);
    ym_patch(2, &patch_arp);
    ym_patch(3, &patch_kick);
    ym_patch(4, &patch_echo);
    mus_tempo = tempo;
    mus_tick = 0;
    mus_step = 0;
    mus_paused = 0;
    mus_on = 1;
}

static void silence_music(void)
{
    u8 ch;
    for (ch = 0; ch < 5; ch++)
        ym_keyoff(ch);
    kick_t = 0xFF;
}

void music_stop(void)
{
    mus_on = 0;
    silence_music();
}

void music_pause(u8 on)
{
    mus_paused = on;
    if (on)
        silence_music();
}

void sfx_play(u8 id)
{
    switch (id) {
    case SFX_SHOT: req0 = id; break;
    case SFX_EXPL:
    case SFX_BIGEXPL: reqn = id; break;
    case SFX_DEATH: reqn = SFX_BIGEXPL; req1 = id; break;
    default: req1 = id; break;
    }
}

static void play_ch(u8 ch, u8 v)
{
    if (!v)
        return;
    ym_keyoff(ch);
    if (v > 1) {
        ym_note(ch, v);
        ym_keyon(ch);
    }
}

static void music_step(void)
{
    u8 s = mus_step, d;
    play_ch(0, m_bass[s]);
    play_ch(1, m_lead[s]);
    play_ch(4, m_lead[(u8)(s - 3)]);
    play_ch(2, m_arp[s]);
    d = m_drum[s];
    if (d & 1) {
        ym_keyoff(3);
        kick_t = 0;
    }
    if (!sn_id && (d & 6)) {
        drum_kind = (d & 2) ? 2 : 4;
        PSG = (d & 2) ? 0xE5 : 0xE4;
        drum_t = 0;
    }
    mus_step++;
}

static void update_drums(void)
{
    if (kick_t < 8) {
        ym_freq(3, 2, kick_tab[kick_t]);
        if (kick_t == 0)
            ym_keyon(3);
        if (++kick_t == 8)
            ym_keyoff(3);
    }
    if (!sn_id && drum_t != 0xFF) {
        if (drum_kind == 2) {
            psg_vol(3, snare_env[drum_t]);
            if (++drum_t >= sizeof(snare_env)) drum_t = 0xFF;
        } else {
            psg_vol(3, hat_env[drum_t]);
            if (++drum_t >= sizeof(hat_env)) drum_t = 0xFF;
        }
    }
}

static void update_sfx(void)
{
    u8 r;
    if ((r = req0)) { req0 = 0; s0_id = r; s0_t = 0; }
    if ((r = req1)) { req1 = 0; s1_id = r; s1_t = 0; }
    if ((r = reqn)) {
        reqn = 0;
        if (!(sn_id == SFX_BIGEXPL && r == SFX_EXPL && sn_t < 30)) {
            sn_id = r; sn_t = 0;
            PSG = (r == SFX_BIGEXPL) ? 0xE7 : 0xE6;
        }
    }

    if (s0_id) {                                   /* player shot: falling blip */
        if (s0_t < 6) {
            psg_tone(0, 0x50 + s0_t * 0x18);
            psg_vol(0, 3 + s0_t * 2);
            s0_t++;
        } else { psg_vol(0, 15); s0_id = 0; }
    }

    if (s1_id) {
        u8 t = s1_t++, done = 0;
        switch (s1_id) {
        case SFX_PICKUP:
            if (t < 16) { psg_tone(1, pickup_tab[t >> 2]); psg_vol(1, 2 + (t & 3)); } else done = 1;
            break;
        case SFX_HIT:
            if (t < 3) { psg_tone(1, 0x300 + t * 0x40); psg_vol(1, 7 + t); } else done = 1;
            break;
        case SFX_ALARM:
            if (t < 160) { psg_tone(1, (t & 8) ? 120 : 170); psg_vol(1, (t & 7) < 6 ? 3 : 15); } else done = 1;
            break;
        case SFX_DEATH:
            if (t < 56) { psg_tone(1, 0x60 + t * 16); psg_vol(1, t >> 2); } else done = 1;
            break;
        case SFX_HOOK:
            if (t < 18) { psg_tone(1, 0x180 - t * 14); psg_vol(1, 2 + (t >> 2)); } else done = 1;
            break;
        case SFX_START:
            if (t < 32) { psg_tone(1, 400 - t * 11); psg_vol(1, (t & 3) == 3 ? 8 : 2); } else done = 1;
            break;
        default: done = 1;
        }
        if (done) { psg_vol(1, 15); s1_id = 0; }
    }

    if (sn_id) {
        u8 t = sn_t++;
        if (sn_id == SFX_BIGEXPL) {
            if (t < 60) { psg_tone(2, 0x80 + t * 12); psg_vol(3, t >> 2); }
            else { psg_vol(3, 15); sn_id = 0; }
        } else {
            if (t < 24) psg_vol(3, t >> 1);
            else { psg_vol(3, 15); sn_id = 0; }
        }
    }
}

void sound_update(void)
{
    update_sfx();
    if (mus_on && !mus_paused) {
        if (mus_tick == 0)
            music_step();
        if (++mus_tick >= mus_tempo)
            mus_tick = 0;
        update_drums();
    }
}
