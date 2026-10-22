#ifndef SOUND_H
#define SOUND_H
#include "md.h"

enum {
    SFX_SHOT = 1, SFX_EXPL, SFX_BIGEXPL, SFX_PICKUP, SFX_HIT, SFX_ALARM, SFX_DEATH, SFX_START, SFX_HOOK
};

void sound_init(void);
void sound_update(void);        /* called from the VBlank interrupt */
void music_play(u8 song, u8 tempo);   /* song 0/1, frames per 16th note */
void music_stop(void);
void music_pause(u8 on);
void sfx_play(u8 id);

#endif
