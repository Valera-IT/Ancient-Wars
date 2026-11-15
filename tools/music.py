#!/usr/bin/env python3
"""Composes the VIPER STORM theme and writes it to src/music.h.

The song is 16 bars of 16th-note steps (256 steps). Per-step values:
0 = nothing, 1 = key off, >=2 = MIDI note. Drums are bit flags:
1 = kick, 2 = snare, 4 = hi-hat.
"""
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "src", "music.h")

NAMES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def midi(n):
    return 12 * (int(n[-1]) + 1) + NAMES[n[:-1]]


CHORDS = ["Dm", "Dm", "Bb", "A", "Dm", "Bb", "Gm", "A", "Dm", "F", "C", "Dm", "Bb", "Gm", "A", "Dm"]
ROOT_NOTE = {"Dm": "D2", "Bb": "A#1", "A": "A1", "Gm": "G1", "F": "F2", "C": "C2"}
TRIAD = {
    "Dm": ["D4", "F4", "A4"],
    "Bb": ["A#3", "D4", "F4"],
    "A": ["A3", "C#4", "E4"],
    "Gm": ["G3", "A#3", "D4"],
    "F": ["F4", "A4", "C5"],
    "C": ["C4", "E4", "G4"]
}

MELODY = [
    [("D4", 8), ("F4", 4), ("G4", 4)],
    [("A4", 8), ("G4", 4), ("F4", 4)],
    [("G4", 4), ("A4", 4), ("F4", 4), ("D4", 4)],
    [("E4", 8), ("D4", 4), ("C#4", 4)],
    [("D4", 8), ("F4", 4), ("G4", 4)],
    [("A4", 6), ("A#4", 2), ("A4", 4), ("G4", 4)],
    [("F4", 4), ("G4", 4), ("E4", 4), ("D4", 4)],
    [("D4", 8), ("C#4", 4), ("A3", 4)],
    [("D5", 8), ("C5", 4), ("A#4", 4)],
    [("A4", 8), ("C5", 4), ("F5", 4)],
    [("G5", 6), ("F5", 2), ("E5", 4), ("D5", 4)],
    [("F5", 8), ("D5", 8)],
    [("A#4", 4), ("C5", 4), ("D5", 4), ("F5", 4)],
    [("G5", 4), ("F5", 4), ("D5", 4), ("A#4", 4)],
    [("E5", 6), ("D5", 2), ("C#5", 4), ("A4", 4)],
    [("D4", 8), ("E4", 4), ("C#4", 4)],
]

CHORDS2 = ["Dm", "Dm", "F", "C", "Dm", "Bb", "Gm", "A", "Dm", "F", "C", "Dm", "Bb", "Gm", "A", "Dm"]
ROOT2 = {"Dm": "D2", "F": "F2", "C": "C2", "Bb": "A#1", "Gm": "G1", "A": "A1"}
TRIAD2 = {
    "Dm": ["D4", "F4", "A4"],
    "F": ["F4", "A4", "C5"],
    "C": ["C4", "E4", "G4"],
    "Bb": ["A#3", "D4", "F4"],
    "Gm": ["G3", "A#3", "D4"],
    "A": ["A3", "C#4", "E4"]
}

MELODY2 = [
    [("D5", 4), ("F5", 4), ("A5", 4), ("D6", 4)],
    [("C6", 4), ("A5", 2), ("G5", 2), ("F5", 4), ("A5", 4)],
    [("C5", 4), ("F5", 4), ("A5", 4), ("C6", 4)],
    [("G5", 6), ("F5", 2), ("E5", 4), ("C5", 4)],
    [("D5", 2), ("D5", 2), ("F5", 2), ("G5", 2), ("A5", 4), ("D5", 4)],
    [("A#5", 4), ("A5", 2), ("G5", 2), ("F5", 4), ("D5", 4)],
    [("G5", 4), ("A#5", 4), ("D6", 4), ("G6", 4)],
    [("E6", 6), ("D6", 2), ("C#6", 4), ("A5", 4)],
    [("D6", 2), ("D6", 2), ("D6", 2), ("F6", 2), ("E6", 4), ("D6", 4)],
    [("C6", 4), ("A5", 4), ("F5", 4), ("A5", 4)],
    [("G5", 2), ("G5", 2), ("G5", 2), ("A#5", 2), ("A5", 4), ("G5", 4)],
    [("F5", 4), ("E5", 2), ("D5", 2), ("F5", 4), ("A5", 4)],
    [("D6", 4), ("C6", 2), ("A#5", 2), ("A5", 4), ("F5", 4)],
    [("G5", 4), ("A#5", 4), ("D6", 4), ("F6", 4)],
    [("E6", 4), ("D6", 2), ("C#6", 2), ("A5", 4), ("E5", 4)],
    [("D5", 8), ("E5", 4), ("C#5", 4)],
]
DRUMS1 = ({0: 1, 2: 4, 4: 2, 6: 4, 8: 1, 10: 5, 12: 2, 14: 4},
          {0: 1, 2: 4, 4: 2, 6: 4, 8: 1, 10: 2, 12: 2, 13: 2, 14: 2, 15: 2})
DRUMS2 = ({0: 1, 2: 4, 3: 1, 4: 2, 6: 4, 8: 1, 10: 5, 11: 1, 12: 2, 14: 4, 15: 4},
          {0: 1, 2: 4, 3: 1, 4: 2, 6: 5, 8: 2, 9: 2, 10: 1, 11: 2, 12: 2, 13: 2, 14: 2, 15: 2})
ARP_SHAPE = [0, 1, 2, 3, 2, 1, 0, 1, 0, 1, 2, 3, 2, 1, 2, 1]


def build(chords, roots, triads, melody, drums):
    bass, lead, arp, drum = [], [], [], []
    for bar, chord in enumerate(chords):
        r = midi(roots[chord])
        for s in range(16):
            if s % 2:
                bass.append(1)
            elif bar % 4 == 3 and s in (12, 14):
                bass.append(r + (7 if s == 12 else 10))
            else:
                bass.append(r if s % 4 == 0 else r + 12)
        tri = [midi(n) for n in triads[chord]] + [midi(triads[chord][0]) + 12]
        arp += [tri[i] for i in ARP_SHAPE]
        notes = melody[bar]
        assert sum(d for _, d in notes) == 16, bar
        for n, d in notes:
            lead.append(midi(n))
            lead += [0] * (d - 2)
            lead.append(1 if d >= 4 else 0)
        pat = drums[1] if bar % 4 == 3 else drums[0]
        drum += [pat.get(s, 0) for s in range(16)]
    for arr in (bass, lead, arp, drum):
        assert len(arr) == 256
    return bass, lead, arp, drum


def build_battle_theme():
    """A dark, processional 16-bar fantasy battle theme for the YM2612."""
    chords = ["Dm", "Dm", "Bb", "A", "Dm", "F", "Gm", "A",
              "Bb", "F", "C", "Dm", "Gm", "Bb", "A", "A"]
    melody = [
        [("D4", 8), ("A4", 4), ("F4", 4)],
        [("D5", 6), ("C5", 2), ("A4", 8)],
        [("A#4", 8), ("D5", 4), ("F5", 4)],
        [("E5", 6), ("D5", 2), ("C#5", 8)],
        [("D5", 8), ("A4", 4), ("F4", 4)],
        [("F4", 4), ("A4", 4), ("C5", 8)],
        [("D5", 8), ("A#4", 4), ("G4", 4)],
        [("A4", 8), ("C#5", 4), ("E5", 4)],
        [("F5", 8), ("D5", 4), ("A#4", 4)],
        [("C5", 8), ("F5", 4), ("A5", 4)],
        [("G5", 8), ("E5", 4), ("C5", 4)],
        [("D5", 12), ("A4", 4)],
        [("G4", 4), ("A#4", 4), ("D5", 8)],
        [("F5", 8), ("D5", 4), ("A#4", 4)],
        [("E5", 8), ("C#5", 4), ("A4", 4)],
        [("C#5", 8), ("E5", 4), ("A4", 4)],
    ]
    bass, lead, arp, drum = [], [], [], []
    for bar, chord in enumerate(chords):
        root = midi(ROOT_NOTE[chord])
        triad = [midi(n) - 12 for n in TRIAD[chord]]
        for step in range(16):
            bass.append(root if step in (0, 8) else root + 7 if step == 12 else 1 if step in (6, 11, 15) else 0)
            # Low sustained harmony, alternating chord tones, leaves space around the lead.
            arp.append(triad[(bar + (step == 8)) % 3] if step in (0, 8) else 1 if step in (6, 14) else 0)
            beat = {0: 1, 4: 4, 8: 1, 12: 2}.get(step, 0)
            if bar % 4 == 3 and step in (14, 15):
                beat = 2
            drum.append(beat)
        assert sum(duration for _, duration in melody[bar]) == 16, bar
        for note, duration in melody[bar]:
            lead.append(midi(note))
            lead.extend([0] * (duration - 2))
            lead.append(1)
    for channel in (bass, lead, arp, drum):
        assert len(channel) == 256
    return bass, lead, arp, drum


songs = [build_battle_theme(), build(CHORDS, ROOT_NOTE, TRIAD, MELODY, DRUMS2)]


def carr(name, values):
    lines = [f"static const u8 {name}[256] = {{"]
    for i in range(0, 256, 16):
        lines.append("  " + ", ".join(str(v) for v in values[i:i + 16]) + ",")
    lines.append("};")
    return "\n".join(lines)


with open(OUT, "w") as f:
    f.write("/* Generated by tools/music.py - do not edit */\n")
    for i, song in enumerate(songs):
        for name, arr in zip(("bass", "lead", "arp", "drum"), song):
            f.write(carr(f"mus{i + 1}_{name}", arr) + "\n")
print("music.h written")
