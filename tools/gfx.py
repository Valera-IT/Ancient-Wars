#!/usr/bin/env python3
"""Generates all ANCIENT WARS graphics into src/gfx.h.

Top-down map in the spirit of Herzog Zwei: a 1024x1024 world built from a 64x64 grid of
16x16 terrain cells, rendered with smooth marching-squares style blending and cached per
cell neighbourhood so the tile count stays small. Units are 3/4 top-down sprites.
"""
import math
import os
import random

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "src", "gfx.h")
random.seed(2005)


def md_color(r, g, b):
    return (b << 9) | (g << 5) | (r << 1)


PAL_FG = [(0, 0, 0), (0, 0, 0), (7, 7, 7), (5, 7, 7), (3, 6, 7), (2, 4, 7), (7, 7, 2), (7, 4, 0),
          (7, 1, 1), (6, 6, 7), (7, 7, 7), (4, 7, 7), (1, 4, 7), (1, 1, 4), (7, 3, 1), (7, 6, 2)]


# ---------------------------------------------------------------- bitmaps
def bmp(w, h, c=0):
    return [[c] * w for _ in range(h)]


def from_ascii(rows, w=None):
    w = w or max(len(r) for r in rows)
    out = bmp(w, len(rows))
    for y, r in enumerate(rows):
        assert len(r) <= w, (r, w)
        for x, ch in enumerate(r):
            out[y][x] = 0 if ch == "." else int(ch, 16)
    return out


def add_outline(b, color=1):
    h, w = len(b), len(b[0])
    out = [row[:] for row in b]
    for y in range(h):
        for x in range(w):
            if b[y][x]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and b[ny][nx] not in (0, color):
                    out[y][x] = color
                    break
    return out


def shade_sphere(b, cx, cy, r, shades, rx=None, ry=None):
    rx = rx or r
    ry = ry or r
    for y in range(len(b)):
        for x in range(len(b[0])):
            dx = (x + 0.5 - cx) / rx
            dy = (y + 0.5 - cy) / ry
            d2 = dx * dx + dy * dy
            if d2 <= 1.0:
                nz = math.sqrt(1 - d2)
                light = -0.55 * dx - 0.6 * dy + 0.6 * nz
                i = int((light + 0.35) / 1.3 * len(shades))
                b[y][x] = shades[max(0, min(len(shades) - 1, i))]


def disc(b, cx, cy, r, color):
    for y in range(len(b)):
        for x in range(len(b[0])):
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r:
                b[y][x] = color


# ---------------------------------------------------------------- tiles
tiles = []          # list of 8-tuples of u32 rows
dedupe = {}


def tile_at(b, tx, ty):
    rows = []
    for r in range(8):
        v = 0
        for c in range(8):
            v = (v << 4) | (b[ty * 8 + r][tx * 8 + c] & 15)
        rows.append(v)
    return tuple(rows)


def add_sprite(b):
    """Sprite tiles, column-major. Returns first tile index (VRAM tile 0 is blank)."""
    h, w = len(b), len(b[0])
    assert w % 8 == 0 and h % 8 == 0
    start = len(tiles) + 1
    for tx in range(w // 8):
        for ty in range(h // 8):
            tiles.append(tile_at(b, tx, ty))
    return start


def add_map(b):
    """Background map, row-major, deduplicated; fully empty tiles map to 0."""
    h, w = len(b), len(b[0])
    m = []
    for ty in range(h // 8):
        for tx in range(w // 8):
            t = tile_at(b, tx, ty)
            if not any(t):
                m.append(0)
                continue
            if t not in dedupe:
                tiles.append(t)
                dedupe[t] = len(tiles)
            m.append(dedupe[t])
    return m


# ---------------------------------------------------------------- font
FONT = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."],
    "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    "-": [".....", ".....", ".....", ".###.", ".....", ".....", "....."],
    ".": [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    ":": [".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
    "/": ["....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."],
    "(": ["...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."],
    ")": [".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."],
    "*": [".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "....."],
    "'": ["..#..", "..#..", ".#...", ".....", ".....", ".....", "....."],
    "+": [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
    "=": [".....", ".....", "#####", ".....", "#####", ".....", "....."],
    "$": ["..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."],
    ">": [".#...", "..#..", "...#.", "....#", "...#.", "..#..", ".#..."],
    "<": ["...#.", "..#..", ".#...", "#....", ".#...", "..#..", "...#."],
}
FONT_GRAD = [2, 2, 3, 3, 4, 4, 5]


def glyph_tile(ch):
    b = bmp(8, 8)
    g = FONT.get(ch)
    if g:
        for y, row in enumerate(g):
            for x, c in enumerate(row):
                if c == "#":
                    b[y + 1 - 1][x + 1] = FONT_GRAD[y]
        # drop shadow
        for y in range(7, -1, -1):
            for x in range(7, -1, -1):
                if b[y][x] and b[y][x] != 1:
                    if y + 1 < 8 and x + 1 < 8 and b[y + 1][x + 1] == 0:
                        b[y + 1][x + 1] = 1
    return b


def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xi:
                inside = not inside
    return inside


def make_logo(text):
    scale, adv = 4, 24
    gw, gh = 5 * scale, 7 * scale
    slant = gh // 4
    W = len(text) * adv + slant + 8
    W = (W + 7) // 8 * 8
    H = 32
    mask = bmp(W, H)
    ox, oy = 2, 1
    for i, ch in enumerate(text):
        g = FONT.get(ch)
        if not g:
            continue
        for gy, row in enumerate(g):
            for gx, c in enumerate(row):
                if c != "#":
                    continue
                for sy in range(scale):
                    for sx in range(scale):
                        y = gy * scale + sy
                        x = ox + i * adv + gx * scale + sx + (gh - y) // 4
                        mask[oy + y][x] = 1
    b = bmp(W, H)
    for y in range(H):
        gy = y - oy
        if gy < 4:
            c = 10
        elif gy < 8:
            c = 11
        elif gy < 13:
            c = 12
        elif gy < 15:
            c = 13
        elif gy < 20:
            c = 15
        else:
            c = 14
        for x in range(W):
            if mask[y][x]:
                b[y][x] = c
    b = add_outline(b, 1)
    for y in range(H - 1, -1, -1):
        for x in range(W - 1, -1, -1):
            if b[y][x] == 0 and y >= 2 and x >= 2 and b[y - 2][x - 2] not in (0, 13):
                b[y][x] = 13
    # trim empty tile columns on the right
    while all(b[y][W - 1 - i] == 0 for y in range(H) for i in range(8)):
        b = [row[:-8] for row in b]
        W -= 8
    return b


BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


# ---------------------------------------------------------------- palettes
# map: 2-4 grass, 5/2/6 tree crowns, 8-10 orange dirt, 11-13 river, 14/15/7 the Dire's dusk
PAL_MAP = [(0, 0, 0), (0, 0, 0), (0, 3, 1), (1, 4, 1), (2, 5, 1), (0, 2, 1), (3, 6, 2), (3, 3, 6),
           (4, 2, 1), (7, 4, 1), (7, 6, 3), (0, 1, 4), (1, 3, 7), (4, 6, 7), (0, 0, 1), (2, 2, 4)]
PAL_UI = [(0, 0, 0), (0, 0, 0), (7, 7, 7), (5, 7, 7), (3, 6, 7), (2, 4, 7), (7, 7, 2), (7, 4, 0),
          (7, 1, 1), (1, 6, 1), (0, 3, 0), (2, 4, 7), (0, 1, 3), (0, 0, 0), (7, 6, 1), (3, 3, 4)]   # 13: the black HUD
UNIT_COMMON = {0: (0, 0, 0), 1: (0, 0, 0), 2: (2, 2, 2), 3: (4, 4, 4), 4: (6, 6, 6), 5: (7, 7, 7),
               6: (7, 6, 5), 7: (6, 4, 3), 8: (3, 5, 7), 12: (7, 1, 0), 13: (2, 0, 2), 14: (4, 1, 4),
               15: (7, 6, 2)}
PAL_RAD = [UNIT_COMMON.get(i) or {9: (0, 3, 1), 10: (1, 5, 2), 11: (4, 7, 3)}[i] for i in range(16)]
PAL_DIRE = [UNIT_COMMON.get(i) or {9: (3, 0, 0), 10: (6, 1, 0), 11: (7, 4, 2)}[i] for i in range(16)]


# ---------------------------------------------------------------- drawing helpers
def ell(b, cx, cy, rx, ry, c):
    for y in range(len(b)):
        for x in range(len(b[0])):
            if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1:
                b[y][x] = c


def rect(b, x0, y0, x1, y1, c):
    for y in range(max(0, y0), min(len(b), y1 + 1)):
        for x in range(max(0, x0), min(len(b[0]), x1 + 1)):
            b[y][x] = c


def line(b, x0, y0, x1, y1, c, w=1):
    n = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(n + 1):
        x = round(x0 + (x1 - x0) * i / n)
        y = round(y0 + (y1 - y0) * i / n)
        rect(b, x, y, x + w - 1, y + w - 1, c)


def put(b, x, y, c):
    if 0 <= y < len(b) and 0 <= x < len(b[0]):
        b[y][x] = c


def shadow(b, cx, cy, rx, ry):
    """Dithered ground shadow, drawn first so the body covers it."""
    for y in range(len(b)):
        for x in range(len(b[0])):
            if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1 and (x + y) % 2 == 0:
                b[y][x] = 1


def hflip(b):
    return [row[::-1] for row in b]


# ---------------------------------------------------------------- heroes (24x24, 3/4 top-down)
# dirs: 0 = down (south), 1 = up (north), 2 = side (east; west is h-flipped)
# frames: 0/1 = walk, 2 = attack
def legs(b, d, f, cx, y0, col, foot):
    if d == 2:
        a = [(-2, 2), (2, -2), (-3, 3)][f]
        for k, off in enumerate(a if isinstance(a, tuple) else (a,)):
            x = cx + off
            rect(b, x - 1, y0, x, y0 + 3, col)
            rect(b, x - 1, y0 + 3, x + 1, y0 + 3, foot)
    else:
        lift = [(0, 1), (1, 0), (0, 0)][f]
        for k, x in enumerate((cx - 3, cx + 2)):
            rect(b, x - 1, y0 - lift[k], x + 1, y0 + 3 - lift[k], col)
            rect(b, x - 1, y0 + 3 - lift[k], x + 1, y0 + 3 - lift[k], foot)


def sf_frame(d, f):
    b = bmp(24, 24)
    shadow(b, 12, 21, 8, 3)
    bob = 1 if f == 1 else 0
    # tattered cloak trailing behind
    for y in range(12, 22):
        w = 3 + (y - 12) // 2
        for x in range(12 - w, 12 + w + 1):
            if (x * 3 + y + f) % 7 or y < 19:
                put(b, x + (-2 if d == 2 else 0), y, 13)
    legs(b, d, f, 12, 17, 13, 2)
    ell(b, 12, 13 + bob, 5, 5, 14 if d != 1 else 13)
    rect(b, 8, 11 + bob, 16, 12 + bob, 9)           # team-coloured mantle
    put(b, 8, 11 + bob, 11)
    ell(b, 12 + (2 if d == 2 else 0), 7 + bob, 3.6, 3.6, 13)
    # horns
    for k in range(4):
        put(b, 9 - k // 2 + (2 if d == 2 else 0), 4 + bob - k, 4)
        put(b, 15 + k // 2 + (2 if d == 2 else 0), 4 + bob - k, 4)
    if d == 0:
        put(b, 11, 7 + bob, 12)
        put(b, 13, 7 + bob, 12)
        put(b, 12, 14 + bob, 15)
    elif d == 2:
        put(b, 15, 7 + bob, 12)
    # arms / soul hand
    if f == 2:
        if d == 0:
            line(b, 15, 13, 17, 19, 14, 2)
            disc(b, 17.5, 20.5, 2, 15)
            put(b, 17, 20, 5)
        elif d == 1:
            line(b, 15, 12, 17, 5, 14, 2)
            disc(b, 17.5, 3.5, 2, 15)
        else:
            line(b, 15, 12, 21, 12, 14, 2)
            disc(b, 21.5, 12.5, 2, 15)
            put(b, 21, 12, 5)
    else:
        sw = 1 if f == 1 else 0
        if d == 2:
            line(b, 13, 12, 14 + sw, 17, 14, 2)
        else:
            line(b, 7, 12 + bob, 6, 17 - sw, 14, 2)
            line(b, 17, 12 + bob, 18, 16 + sw, 14, 2)
            put(b, 6, 18 - sw, 15)
            put(b, 18, 17 + sw, 15)
    return add_outline(b)


def flesh(b, cx, cy, r, rx=None, ry=None):
    """a pink ball: dark underside, one small white gleam up-left"""
    rx, ry = rx or r, ry or r
    for y in range(len(b)):
        for x in range(len(b[0])):
            dx, dy = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
            d2 = dx * dx + dy * dy
            if d2 <= 1.0:
                b[y][x] = 14 if dy > 0.55 or dx * 0.6 + dy > 0.75 else 6
                if (dx + 0.45) ** 2 + (dy + 0.5) ** 2 < 0.05:
                    b[y][x] = 5


PUDGE_FRONT = [                    # traced from the reference: one squat hunched mass, the wide
    "                        ",       # flat head sunk on top, arms spread, the hook held out up-right
    "                        ",
    "                       5",
    "      ##########     #4#",
    "     #SSSSSSSSSS#    #3 ",
    "    #SSS#SSSS##SS#   3  ",
    "   #sSSSSSsddsSSSs# 3   ",
    "  #s##SSSSSSSSSSs#####  ",
    " #SS#sSSSSSSSSSSSs#SSs# ",
    " #S#S#SSSSSdSSSSSSSSSs# ",
    "#SSSs#SSSSSdSSSSSs#sss# ",
    "#S#S#sSSSSSdsSSSSs####  ",
    "#ss#ssSSSSsdssSSs#      ",
    " ###sssSSSsdsssSss#     ",
    "    #ssssssdsssss#      ",
    "    ##dddddddddd##      ",
    "     #BBBBbbBBBBb#      ",
    "     #BBbBBBBbBBb#      ",
    "     #bBBb#bBBbb#       ",
    "      #bb# #bbb#        ",
    "   1 1 ### 1###1 1      ",
    "    1 1 1 1 1 1 1 1     ",
    "     1 1 1 1 1 1 1      ",
    "                        ",
]
PUDGE_LEGS = ["     #BBbBBBBbBBb#      ", "     #bBBbb#bBBb#       ", "      #bbb# #bb#        ",
              "   1 1 ### 1###1 1      "]
PUDGE_THROW = {                    # the attack: the hook arm flung straight up, chain taut
    0: "                   #4#  ",
    1: "                   #3#  ",
    2: "                   #3#  ",
    3: "      ##########  #Ss#  ",
    4: "     #SSSSSSSSSS##SSs#  ",
    5: "    #SSS#SSSS##SS#Ss#   ",
    6: "   #sSSSSSsddsSSSSSs#   ",
    7: "  #s##SSSSSSSSSSsSSs#   ",
    8: " #SS#sSSSSSSSSSSSss#    ",
    9: " #S#S#SSSSSdSSSSSss#    ",
    10: "#SSSs#SSSSSdSSSSSs#     ",
    11: "#S#S#sSSSSSdsSSSSs#     ",
}
PUDGE_COLS = {"#": 1, "1": 1, "S": 6, "s": 7, "d": 13, "B": 8, "b": 13, "3": 3, "4": 4, "5": 5}


def pudge_frame(d, f):
    """The Butcher, traced from the Dota pixel-art reference: a squat pale gut with the wide flat
    head sunk on top, arms spread, blue trousers, the chained hook held out up-right; the attack
    frame flings the hook arm straight up. The back view has no face or belly line; the side
    view shares the front art (the game mirrors it)."""
    rows = list(PUDGE_FRONT)
    if f == 1:
        rows[17:21] = PUDGE_LEGS
    elif f == 2:
        for y, r in PUDGE_THROW.items():
            rows[y] = r
    if d == 1:                                                      # from behind
        rows = [r[:6] + r[6:17].replace("d", "s") + r[17:] if 5 <= y <= 14 else r for y, r in enumerate(rows)]
        rows[5] = rows[5][:5] + "SSSSSSSSSSSS" + rows[5][17:]
    b = bmp(24, 24)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != " ":
                b[y][x] = PUDGE_COLS[ch]
    return b


def axe_frame(d, f):
    """Axe: red-skinned, black topknot, grey armour, a huge double-bladed axe."""
    b = bmp(24, 24)
    shadow(b, 12, 21, 8, 3)
    sx = 2 if d == 2 else 0
    legs(b, d, f, 12, 17, 3, 1)
    shade_sphere(b, 12, 12, 6, [12, 12, 12], rx=6.5, ry=5.5)
    if d != 1:
        rect(b, 9, 11, 15, 14, 3)                       # chest plate
        rect(b, 10, 12, 14, 13, 4)
    else:
        line(b, 8, 9, 16, 15, 3)                         # harness
    rect(b, 7, 15, 17, 16, 9)                            # team-coloured belt
    put(b, 8, 15, 11)
    rect(b, 6, 9, 8, 11, 4)                              # pauldrons
    rect(b, 16, 9, 18, 11, 4)
    ell(b, 12 + sx, 6, 3.3, 3, 12)
    rect(b, 11 + sx, 2, 13 + sx, 4, 13)                  # topknot
    put(b, 12 + sx, 1, 13)
    if d == 0:
        put(b, 11, 6, 15)
        put(b, 13, 6, 15)
        line(b, 10, 8, 14, 8, 13)                        # beard
    elif d == 2:
        put(b, 15, 6, 15)
        line(b, 14, 8, 16, 8, 13)
    if f == 2:                                           # overhead chop
        if d == 0:
            line(b, 16, 12, 18, 20, 6, 1)
            ell(b, 18, 21, 4, 2.5, 4)
            line(b, 15, 21, 21, 21, 5)
        elif d == 1:
            line(b, 16, 11, 18, 3, 6, 1)
            ell(b, 18, 2.5, 4, 2.5, 4)
        else:
            line(b, 16, 11, 22, 11, 6, 1)
            ell(b, 21.5, 11, 2.5, 5, 4)
            line(b, 23, 7, 23, 15, 5)
    else:
        sw = f
        line(b, 6, 11, 5, 16 + sw, 12, 2)
        line(b, 18, 11, 19, 15 - sw, 12, 2)
        line(b, 20, 3 - sw, 20, 19 - sw, 6)              # haft
        ell(b, 17.5, 5 - sw, 2.5, 3, 4)                  # double blade
        ell(b, 22.5, 5 - sw, 2.5, 3, 4)
        put(b, 16, 5 - sw, 5)
        put(b, 23, 5 - sw, 5)
    return add_outline(b)


def humanoid(d, f, skin, body, legs_c=2, robe=False, trim=11, hair=None, style="short", beard=None,
             weapon="hands", wcol=4, glow=5, short=False):
    """Generic caster/fighter body for the newer heroes: robe or legs, team belt, a head with hair
    of some style, and one weapon whose pose follows the frame (2 = attack)."""
    b = bmp(24, 24)
    shadow(b, 12, 21, 8, 3)
    sx = 2 if d == 2 else 0
    dy = 2 if short else 0                               # keen-sized: everything sits lower
    if robe:
        for y in range(11 + dy, 21):
            w = 4 + (y - 11 - dy) // 3
            for x in range(12 - w, 12 + w + 1):
                put(b, x + (-1 if d == 2 else 0), y, body)
        rect(b, 8, 20, 16, 20, trim)                     # hem
        put(b, 9 + f, 21, 1)
        put(b, 14 - f, 21, 1)
    else:
        legs(b, d, f, 12, 17, legs_c, 1)
    ell(b, 12, 12 + dy, 5, 4.5 - dy * 0.5, body)
    rect(b, 8, 14 + dy // 2, 16, 15 + dy // 2, 9)        # team-coloured belt
    put(b, 8, 14 + dy // 2, 11)
    hx, hy = 12 + sx, 7 + dy
    if style == "hood":
        ell(b, hx, hy, 4.2, 4, hair)
        if d != 1:
            ell(b, hx + (1 if d == 2 else 0), hy + 1, 2.3, 2.2, skin)
    else:
        ell(b, hx, hy, 3.3, 3.2, skin if d != 1 else (hair or skin))
        if hair is not None:
            if style == "long":
                rect(b, hx - 4, hy - 2, hx - 3, hy + 5, hair)
                rect(b, hx + 3, hy - 2, hx + 4, hy + 5, hair)
                rect(b, hx - 3, hy - 4, hx + 3, hy - 2, hair)
                if d == 1:
                    rect(b, hx - 3, hy - 2, hx + 3, hy + 6, hair)
                if d == 2:
                    rect(b, hx - 4, hy - 2, hx - 1, hy + 6, hair)
            elif style == "flame":                     # Lina: hair rising into flames
                rect(b, hx - 3, hy - 4, hx + 3, hy - 2, hair)
                for k in range(-3, 4, 2):
                    put(b, hx + k, hy - 5, 12)
                    put(b, hx + k + 1, hy - 6 + (k & 1), 12)
                rect(b, hx - 4, hy - 2, hx - 3, hy + 3, hair)
                rect(b, hx + 3, hy - 2, hx + 4, hy + 3, hair)
            elif style == "helmet":
                rect(b, hx - 3, hy - 4, hx + 3, hy - 1, hair)
                rect(b, hx - 4, hy - 1, hx + 4, hy - 1, hair)
                put(b, hx - 1, hy - 3, 5)
            elif style == "mask":                      # Juggernaut: tiki mask and a red crest
                if d != 1:
                    ell(b, hx + (1 if d == 2 else 0), hy, 3, 3.2, 15)
                    line(b, hx - 2 + (1 if d == 2 else 0), hy - 1, hx + 2 + (1 if d == 2 else 0), hy - 1, 12)
                    put(b, hx - 1 + (2 if d == 2 else 0), hy, 1)
                    if d == 0:
                        put(b, hx + 1, hy, 1)
                    line(b, hx - 1, hy + 2, hx + 1, hy + 2, 12)
                rect(b, hx - 1, hy - 6, hx + 1, hy - 3, hair)
            elif style == "horns":                     # Lion: swept back horns
                for k in range(4):
                    put(b, hx - 3 - k // 2, hy - 2 - k, hair)
                    put(b, hx + 3 + k // 2, hy - 2 - k, hair)
            else:
                rect(b, hx - 3, hy - 4, hx + 3, hy - 2, hair)
    if d == 0 and style != "mask":
        put(b, hx - 1, hy, 1 if skin != 1 else 5)
        put(b, hx + 1, hy, 1 if skin != 1 else 5)
        if style == "horns":
            put(b, hx - 1, hy, 12)
            put(b, hx + 1, hy, 12)
    elif d == 2 and style != "mask":
        put(b, hx + 2, hy, 12 if style == "horns" else 1)
    if beard is not None and d != 1:
        rect(b, hx - 2 + (1 if d == 2 else 0), hy + 2, hx + 2, hy + 4, beard)
        put(b, hx + (1 if d == 2 else 0), hy + 5, beard)
    # arms and weapon
    sw = 1 if f == 1 else 0
    arm = body if robe else skin
    ay = 11 + dy
    if f == 2:
        if weapon == "staff":
            if d == 0:
                line(b, 16, ay, 19, 21, wcol)
                disc(b, 19.5, 21.5, 2, glow)
            elif d == 1:
                line(b, 16, ay, 19, 3, wcol)
                disc(b, 19.5, 2.5, 2, glow)
            else:
                line(b, 14, ay, 22, ay - 4, wcol)
                disc(b, 21.5, ay - 4.5, 2, glow)
            line(b, 15, ay, 17, ay + 2, arm, 2)
        elif weapon == "gun":
            if d == 0:
                line(b, 12, 13 + dy, 12, 23, wcol, 2)
                put(b, 12, 23, 15)
            elif d == 1:
                line(b, 12, 11, 12, 1, wcol, 2)
                put(b, 12, 0, 15)
            else:
                line(b, 13, ay + 1, 23, ay + 1, wcol, 2)
                put(b, 18, ay, 5)
                put(b, 23, ay, 15)
        elif weapon == "bow":
            if d == 0:
                line(b, 7, 19, 12, 22, wcol)
                line(b, 12, 22, 17, 19, wcol)
                line(b, 12, 13, 12, 21, 5)
            elif d == 1:
                line(b, 7, 4, 12, 1, wcol)
                line(b, 12, 1, 17, 4, wcol)
                line(b, 12, 10, 12, 2, 5)
            else:
                line(b, 20, 6, 22, 12, wcol)
                line(b, 22, 12, 20, 18, wcol)
                line(b, 20, 6, 20, 18, 4)
                line(b, 14, 12, 23, 12, 5)
        elif weapon == "sword":
            if d == 0:
                line(b, 14, 13, 22, 21, 5)
                line(b, 13, 12, 15, 14, 15)
            elif d == 1:
                line(b, 14, 10, 22, 2, 5)
                line(b, 13, 11, 15, 9, 15)
            else:
                line(b, 15, 12, 23, 8, 5)
                put(b, 14, 12, 15)
            line(b, 15, ay, 15, ay + 2, arm, 2)
        else:                                          # casters: both hands forward, glowing
            if d == 0:
                line(b, 9, ay + 1, 10, ay + 7, arm, 2)
                line(b, 15, ay + 1, 14, ay + 7, arm, 2)
                disc(b, 12, 20.5, 2.6, glow)
                put(b, 12, 20, 5)
            elif d == 1:
                line(b, 9, ay, 10, 4, arm, 2)
                line(b, 15, ay, 14, 4, arm, 2)
                disc(b, 12, 2.5, 2.6, glow)
            else:
                line(b, 13, ay, 19, ay, arm, 2)
                disc(b, 21.5, ay + 0.5, 2.4, glow)
                put(b, 21, ay, 5)
    else:
        if d == 2:
            line(b, 13, ay + 1, 14 + sw, ay + 5, arm, 2)
        else:
            line(b, 7, ay, 6, ay + 5 - sw, arm, 2)
            line(b, 17, ay, 18, ay + 4 + sw, arm, 2)
        if weapon == "staff":
            line(b, 19, 3 - sw, 19, 20 - sw, wcol)
            disc(b, 19.5, 3.5 - sw, 1.8, glow)
        elif weapon == "gun":
            line(b, 16, 17 - sw, 22, 5 - sw, wcol)
            put(b, 20, 8 - sw, 5)
            put(b, 22, 4 - sw, 3)
        elif weapon == "bow":
            line(b, 19, 5, 21, 9, wcol)
            line(b, 21, 9, 21, 14, wcol)
            line(b, 21, 14, 19, 18, wcol)
            line(b, 19, 5, 19, 18, 4)
        elif weapon == "sword":
            line(b, 18, 15 - sw, 22, 5 - sw, 5)
            line(b, 17, 16 - sw, 18, 16 - sw, 15)
        else:
            put(b, 6, ay + 6 - sw, glow)
            put(b, 18, ay + 5 + sw, glow)
    return add_outline(b)


HERO_SPECS = {
    "sniper": dict(skin=6, body=3, legs_c=2, hair=15, style="helmet", beard=15, weapon="gun", wcol=2, short=True),
    "zeus": dict(skin=6, body=4, robe=True, trim=8, hair=5, style="long", beard=5, glow=8),
    "lina": dict(skin=6, body=12, robe=True, trim=15, hair=15, style="flame", glow=15),
    "cm": dict(skin=6, body=8, robe=True, trim=5, hair=5, style="hood", weapon="staff", wcol=4, glow=5),
    "drow": dict(skin=8, body=13, legs_c=13, hair=5, style="long", weapon="bow", wcol=6),
    "lion": dict(skin=3, body=2, robe=True, trim=12, hair=2, style="horns", glow=12),
    "jugg": dict(skin=6, body=6, legs_c=15, hair=12, style="mask", weapon="sword"),
}


def spec_frame(name):
    return lambda d, f: humanoid(d, f, **HERO_SPECS[name])


# ---------------------------------------------------------------- creeps (16x16, 3/4 top-down)
def melee_frame(d, f):
    b = bmp(16, 16)
    shadow(b, 8, 14, 5, 2)
    legs(b, d, f, 8, 11, 2, 1)
    ell(b, 8, 9, 4, 3.5, 10)
    rect(b, 4, 10, 12, 11, 9)
    ell(b, 8 + (1 if d == 2 else 0), 5, 3, 3, 4 if d != 1 else 3)
    rect(b, 5 + (1 if d == 2 else 0), 3, 11 + (1 if d == 2 else 0), 3, 11)
    if d == 0:
        put(b, 7, 5, 1)
        put(b, 9, 5, 1)
    if d == 2:
        rect(b, 3, 6, 4, 11, 9)                       # shield on the back arm
        line(b, 10, 9, 14 if f == 0 else 13, 5 if f == 0 else 9, 4)
    else:
        rect(b, 2, 7, 4, 11, 9)
        put(b, 3, 8, 11)
        line(b, 12, 9, 13, 3 if d == 1 else 13 - f, 4)
        put(b, 13, 2 if d == 1 else 14 - f, 5)
    return add_outline(b)


def ranged_frame(d, f):
    b = bmp(16, 16)
    shadow(b, 8, 14, 5, 2)
    for y in range(6, 14):
        w = 2 + (y - 6) // 2
        for x in range(8 - w, 8 + w + 1):
            put(b, x, y, 10 if x < 8 else 9)
    rect(b, 6 + f, 14, 10 - f, 14, 9)
    ell(b, 8 + (1 if d == 2 else 0), 4.5, 2.8, 2.8, 11 if d != 1 else 10)
    if d == 0:
        rect(b, 7, 4, 9, 5, 6)
    elif d == 2:
        rect(b, 9, 4, 10, 5, 6)
    sx = 13 if d != 2 else 12
    line(b, sx, 3, sx, 14, 2)
    disc(b, sx + 0.5, 2.5, 1.8, 15)
    put(b, sx, 2, 5)
    return add_outline(b)


# ---------------------------------------------------------------- buildings (top-down)
def tower():
    b = bmp(32, 32)
    for y in range(32):                                   # cast shadow to the bottom-right
        for x in range(32):
            if 6 <= x - 3 <= 26 and 6 <= y - 3 <= 26 and (x + y) % 2 == 0:
                b[y][x] = 1
    rect(b, 4, 4, 26, 26, 3)
    rect(b, 4, 4, 26, 5, 4)
    rect(b, 4, 4, 5, 26, 4)
    rect(b, 4, 25, 26, 26, 2)
    rect(b, 25, 4, 26, 26, 2)
    for k in range(5, 26, 5):                            # crenellations
        rect(b, k, 2, k + 2, 3, 4)
        rect(b, k, 27, k + 2, 28, 2)
        rect(b, 2, k, 3, k + 2, 4)
        rect(b, 27, k, 28, k + 2, 2)
    shade_sphere(b, 15.5, 15.5, 8, [2, 3, 4])
    shade_sphere(b, 15.5, 15.5, 5, [9, 10, 11])
    disc(b, 14, 14, 1.6, 5)
    return add_outline(b)


def ancient():
    b = bmp(48, 48)
    poly = [(14, 3), (34, 3), (45, 14), (45, 34), (34, 45), (14, 45), (3, 34), (3, 14)]
    for y in range(48):
        for x in range(48):
            if point_in_poly(x + 0.5 - 3, y + 0.5 - 3, poly) and (x + y) % 2 == 0:
                b[y][x] = 1
            if point_in_poly(x + 0.5, y + 0.5, poly):
                b[y][x] = 3 if (x // 6 + y // 6) % 2 else 4
    for x0, y0 in ((8, 8), (34, 8), (8, 34), (34, 34)):    # corner pylons
        shade_sphere(b, x0 + 3, y0 + 3, 3.5, [9, 10, 11])
    shade_sphere(b, 24, 24, 13, [2, 3, 4])
    for k in range(6):                                      # big crystal star
        a = k * math.pi / 3
        line(b, 24, 24, round(24 + math.cos(a) * 11), round(24 + math.sin(a) * 11), 10, 2)
    shade_sphere(b, 24, 24, 6.5, [9, 10, 11])
    disc(b, 22, 22, 2, 5)
    return add_outline(b)


# ---------------------------------------------------------------- effects
def raze_frame(f):
    b = bmp(24, 24)
    rnd = random.Random(10 + f)
    r = [6, 10, 11.5][f]
    for y in range(24):
        for x in range(24):
            d = math.hypot(x + 0.5 - 12, y + 0.5 - 12) + rnd.uniform(-1.5, 1.5)
            if d > r:
                continue
            k = d / r
            if f == 0:
                c = 12 if k < 0.4 else 13
            elif f == 1:
                c = 1 if k < 0.35 else (13 if k < 0.7 else (12 if rnd.random() < 0.5 else 14))
            else:
                if rnd.random() < 0.55:
                    continue
                c = 13 if k < 0.6 else 14
            b[y][x] = c
    return b


def soul_wave():
    b = bmp(16, 16)
    ell(b, 8, 8, 6, 6, 13)
    ell(b, 7, 7, 4, 4, 14)
    put(b, 6, 7, 12)
    put(b, 9, 7, 12)
    return add_outline(b, 1)


def bolt():
    """A lightning strike, 8x32: jagged white core with a blue glow."""
    b = bmp(8, 32)
    x = 4
    rnd = random.Random(77)
    for y in range(32):
        x = max(1, min(6, x + rnd.choice((-1, 0, 1))))
        put(b, x - 1, y, 8)
        put(b, x + 1, y, 8)
        put(b, x, y, 5)
    return b


def orb(c_out, c_in, c_mid=5, r=3.2):
    b = bmp(8, 8)
    disc(b, 4, 4, r, c_out)
    disc(b, 4, 4, r - 1.2, c_in)
    put(b, 3, 3, c_mid)
    return b


def hook_head():
    return from_ascii(["........", "..334...", ".3...4..", "3.....4.", "3....44.", ".3..444.", "..3333..", "........"], 8)


def chain_link():
    return from_ascii(["........", "........", "...33...", "..3..3..", "..3..3..", "...33...", "........", "........"], 8)


def rot_puff():
    b = bmp(8, 8)
    disc(b, 3.5, 4, 2.6, 11)
    disc(b, 3, 3.5, 1.4, 3)
    return b


def spark(f):
    if f == 0:
        return from_ascii(["........", "...f....", "...5....", ".f555f..", "...5....", "...f....", "........", "........"], 8)
    return from_ascii(["...f....", "........", ".f.5.f..", "...5....", ".f.5.f..", "........", "...f....", "........"], 8)


def poof(f):
    b = bmp(16, 16)
    rnd = random.Random(30 + f)
    for _ in range(18 + f * 6):
        x, y = rnd.uniform(3, 13), rnd.uniform(3, 13)
        disc(b, x, y, 1.5 + f * 0.6, 3 if rnd.random() < 0.5 else 4)
    if f:
        for y in range(16):
            for x in range(16):
                if (x + y) % 2 and b[y][x]:
                    b[y][x] = 0
    return b


def unit_bar(level):
    b = bmp(8, 8)
    for x in range(8):
        b[0][x] = 1
        b[1][x] = 10 if x < level else 2
        b[2][x] = 1
    return b


def ui_bar(level, full, empty, seg=True):
    """bar cell, filled to level/8: segmented every 4 px like the Dota HUD"""
    b = bmp(8, 8, 13)
    for x in range(8):
        for y in range(2, 6):
            b[y][x] = full if x < level else empty
        if seg and x % 4 == 3:
            for y in range(2, 6):
                b[y][x] = 13
    for x in range(8):
        b[2][x] = 2 if x < level and b[2][x] == full else b[2][x]    # a bright top edge
    return b


def marker(kind):
    b = bmp(8, 8)
    if kind == 0:     # building: 2x2 dot with a black rim
        rect(b, 0, 0, 3, 3, 1)
        rect(b, 1, 1, 2, 2, 11)
    elif kind == 1:   # hero: 3x3 with a white core and a black rim
        rect(b, 0, 0, 4, 4, 1)
        rect(b, 1, 1, 3, 3, 11)
        put(b, 2, 2, 5)
    else:             # camera frame corner
        rect(b, 0, 0, 0, 0, 5)
    return b


def frame_tile(kind):
    """HUD frame pieces (pal UI): 0 = horizontal rule, 1 = vertical rule."""
    b = bmp(8, 8, 13)
    if kind == 0:
        rect(b, 0, 3, 7, 3, 15)
        rect(b, 0, 4, 7, 4, 13)
    else:
        rect(b, 3, 0, 3, 7, 15)
        rect(b, 4, 0, 4, 7, 13)
    return b



# ---------------------------------------------------------------- HUD icons (16x16, unit palette 2)
GLYPHS = {
    "flame": [".....a......", "....aa......", "....aba.....", "...abba..a..", "...abbaa.aa.", "..abbcbaaba.",
              "..abccbbbba.", ".abbccccbba.", ".abcccdccba.", ".abccddccba.", "..abcddcba..", "...aabbaa..."],
    "flake": [".....a......", "...a.a.a....", "....aaa.....", ".a..aba..a..", "..a.aba.a...", "aaaabbbaaaa.",
              "..a.aba.a...", ".a..aba..a..", "....aaa.....", "...a.a.a....", ".....a......", "............"],
    "bolt": [".......aa...", "......aba...", ".....abba...", "....abba....", "...abba.....", "..abbbbbaa..",
             "..aabbbbba..", ".....abba...", "....abba....", "...abba.....", "..aba.......", "..aa........"],
    "hook": ["....aa......", "....ab......", "....ab......", "....ab......", "....ab......", "....ab...a..",
             "....ab...ab.", "....ab...ab.", "....abb.abb.", ".....abbbb..", "......aaa...", "............"],
    "skull": ["...aaaaaa...", "..abbbbbba..", ".abbbbbbbba.", ".abbbbbbbba.", ".ab..bb..ba.", ".ab..bb..ba.",
              ".abbbb.bbba.", "..abbbbbba..", "...ab.b.ba..", "...abbbbba..", "....aaaaa...", "............"],
    "cloud": ["............", "....aaa.....", "...abbba.aa.", "..abbbbbabba", ".aabbbbbbbba", "abbbcbbbcbba",
              "abbbbbbbbbba", ".abbbbbbbba.", "..aaaaaaaa..", "..a..a..a...", ".a..a..a....", "............"],
    "heart": ["............", "..aa....aa..", ".abba..abba.", "abbbbaabbbba", "abcbbbbbbbba", "abcbbbbbbbba",
              ".abbbbbbbba.", "..abbbbbba..", "...abbbba...", "....abba....", ".....aa.....", "............"],
    "blade": ["..........aa", ".........aba", "........aba.", ".......aba..", "......aba...", ".....aba....",
              "..c.aba.....", "...cba......", "...ccc......", "..c..cd.....", ".......d....", "........d..."],
    "swords": ["aa........aa", "aba......aba", ".aba....aba.", "..aba..aba..", "...abaaba...", "....abba....",
               "....abba....", "...abaaba...", ".cc.a..a.cc.", ".ccc....ccc.", "c..c....c..c", "............"],
    "spiral": ["....aaaa....", "..aa....a...", ".a...aa..a..", ".a..a..a.a..", "a..a.b..a.a.", "a..a.bb.a.a.",
               "a..a....a.a.", ".a..aaaa..a.", ".a.......a..", "..a.....a...", "...aaaaa....", "............"],
    "ring": ["...aaaaaa...", "..a......a..", ".a..bbbb..a.", "a..b....b..a", "a.b..cc..b.a", "a.b.cccc.b.a",
             "a.b.cccc.b.a", "a.b..cc..b.a", "a..b....b..a", ".a..bbbb..a.", "..a......a..", "...aaaaaa..."],
    "claw": ["..a...a...a.", "..a...a...a.", ".ab..ab..ab.", ".ab..ab..ab.", ".ab..ab..ab.", "ab..ab..ab..",
             "ab..ab..ab..", "ab..ab..ab..", "a...a...a...", "a...a...a...", "............", "............"],
    "cross": [".....a......", "...aaaaa....", "..a..a..a...", ".a...a...a..", ".a...a...a..", "aaaaabaaaaa.",
              ".a...a...a..", ".a...a...a..", "..a..a..a...", "...aaaaa....", ".....a......", "............"],
    "burst": [".a...a...a..", "..a..a..a...", "...a.a.a....", "....bbb.....", "aaa.bcb.aaa.", "....bbb.....",
              "...a.a.a....", "..a..a..a...", ".a...a...a..", "............", "...a...a....", "............"],
    "arrow": ["........aaaa", ".........baa", "........b.aa", ".......b...a", "......b.....", ".....b......",
              "....b.......", "...b........", ".cb.........", ".cc.........", "c.c.........", "............"],
    "arrows": [".aa...aa..aa", "..ba...ba..b", "...b....b...", "...b....b...", "...b....b...", "...b....b...",
               "..b....b....", "..b....b....", "..b....b....", ".cc...cc....", "............", "............"],
    "wind": ["............", ".aaaaaaa....", "........a...", "..aaaaaa.a..", ".........a..", "aaaaaaaaa...",
             "............", "..aaaaaaaa..", "..........a.", "....aaaaa.a.", ".........a..", "............"],
    "spike": ["............", ".....a......", ".....ab.....", "....abb.....", "....abb..a..", "...abbb.ab..",
              ".a.abbbbabb.", "abaabbbbabb.", "abbabbbbabbb", "cccccccccccc", ".cccccccccc.", "............"],
    "drop": [".....a......", ".....a......", "....aba.....", "....aba.....", "...abbba....", "..abbbbba...",
             "..abcbbba...", ".abccbbbba..", ".abcbbbbba..", "..abbbbba...", "...aaaaa....", "............"],
    "hand": ["............", "....a.......", "...aba......", "...aba......", "...abaaaa...", ".aaabababaa.",
             "abababababa.", "abbbbbbbbba.", ".abbbbbbbba.", "..abbbbbba..", "...abbbba...", "....aaaa...."],
    "plus": ["....aaaa....", "....abba....", "....abba....", "aaaaabbaaaaa", "abbbbbbbbbba", "abbbbbbbbbba",
             "aaaaabbaaaaa", "....abba....", "....abba....", "....abba....", "....aaaa....", "............"],
    "star": [".....a......", ".....a......", "....aba.....", "aaaabbbaaaa.", ".abbbcbbba..", "..abbbbba...",
             "...abbba....", "..abbabba...", "..aba.aba...", ".aa.....aa..", "............", "............"],
    "eye": ["............", "............", "...aaaaaa...", "..a..bb..a..", ".a..bccb..a.", "a...bccb...a",
            ".a..bccb..a.", "..a..bb..a..", "...aaaaaa...", "............", "............", "............"],
    "frog": ["............", "..aa....aa..", ".abca..abca.", ".abba..abba.", "..abbbbbbba.", ".abbbbbbbbba",
             "abbbbbbbbbba", "abbccccccbba", ".abbbbbbbba.", "..aa....aa..", ".a.a....a.a.", "............"],
    "boot": ["..aaaa......", "..abba......", "..abba......", "..abba......", "..abba......", "..abbaa.....",
             "..abbbbaa...", "..abbbbbba..", ".aabbbbbbba.", ".accccccccca", ".aaaaaaaaaaa", "............"],
    "lock": ["....aaaa....", "...a....a...", "...a....a...", "...a....a...", "..aaaaaaaa..", "..abbbbbba..",
             "..abbccbba..", "..abbccbba..", "..abbbcbba..", "..abbbbbba..", "..aaaaaaaa..", "............"],
    "bracer": ["............", "............", "..aaaaaaaa..", ".abbbbbbbba.", ".abccbbccba.", ".abbbddbbba.",
               ".abbbddbbba.", ".abccbbccba.", ".abbbbbbbba.", "..aaaaaaaa..", "............", "............"],
    "none": ["............"] * 12,
}


def icon(glyph, a, b=None, c=None, d=None, bg=13):
    """16x16 ability or item icon: black rim, bevelled grey frame, glyph on a dark field."""
    col = {"a": a, "b": b if b is not None else a, "c": c if c is not None else (b if b is not None else a),
           "d": d if d is not None else 5}
    im = bmp(16, 16, bg)
    for i in range(16):
        im[0][i] = im[15][i] = im[i][0] = im[i][15] = 1
    for i in range(1, 15):
        im[1][i] = im[i][1] = 3
        im[14][i] = im[i][14] = 2
    for y, row in enumerate(GLYPHS[glyph]):
        for x, ch in enumerate(row):
            if ch != ".":
                im[2 + y][2 + x] = col[ch]
    return im


# per hero, the icon of each skill in skill order (Shadow Fiend's razes all use the first)
SKILL_ICONS = [
    [("flame", 12, 12, 15), ("flame", 14, 14, 5, 5, 1), ("eye", 14, 12, 1), ("skull", 14, 5, 5, 5, 1)],  # SF
    [("hook", 3, 5), ("cloud", 2, 7, 15), ("heart", 13, 12, 5), ("claw", 12, 5, 5, 5, 1)],                # Pudge
    [("ring", 12, 15, 5, 5, 1), ("claw", 12, 15), ("spiral", 4, 15, 5, 5, 2), ("blade", 3, 12, 15, 6, 1)], # Axe
    [("burst", 15, 12, 5, 5, 2), ("cross", 12, 5), ("eye", 8, 5, 1, 5, 2), ("cross", 15, 5, 5, 5, 1)],     # Sniper
    [("bolt", 8, 5), ("bolt", 15, 5, 5, 5, 2), ("star", 8, 5, 5), ("bolt", 15, 5, 5, 5, 1)],              # Zeus
    [("flame", 12, 15, 15), ("ring", 12, 15, 5, 5, 1), ("flame", 15, 15, 5, 5, 2), ("bolt", 12, 15, 5, 5, 1)],  # Lina
    [("flake", 8, 5), ("flake", 5, 8, 5, 5, 2), ("star", 8, 5, 5, 5, 2), ("flake", 5, 5, 5, 5, 1)],       # CM
    [("arrow", 8, 5, 3), ("wind", 8, 5), ("arrows", 4, 5, 3, 5, 2), ("cross", 8, 5, 5, 5, 1)],            # Drow
    [("spike", 3, 4, 6, 5, 2), ("frog", 7, 7, 1), ("drop", 8, 8, 5), ("hand", 14, 12, 5, 5, 1)],          # Lion
    [("spiral", 15, 5, 5, 5, 2), ("plus", 7, 7), ("swords", 4, 5, 15), ("blade", 8, 5, 15, 6, 1)],        # Jugg
]
ITEM_ICONS = [("boot", 1, 6, 15, 5, 2), ("blade", 3, 5, 15, 6, 2), ("heart", 13, 7, 5, 5, 2), ("blade", 8, 5, 15, 6, 13),
              ("bracer", 1, 6, 15, 12, 2)]


def small_icon(kind):
    """8x8 bar labels in the UI palette: heart, drop, star."""
    pats = {"heart": [".88.88..", "8888888.", "8888888.", ".88888..", "..888...", "...8....", "........", "........"],
            "drop": ["...b....", "...b....", "..bbb...", ".bbbbb..", ".bbbbb..", "..bbb...", "........", "........"],
            "star": ["...6....", "..666...", "6666666.", ".66666..", ".66.66..", "6.....6.", "........", "........"],
            # split-screen item marks: boots, blades, vitality, blink dagger
            "boot": [".77.....", ".77.....", ".77.....", ".777....", ".77777..", ".777777.", ".222222.", "........"],
            "sword": [".....22.", "....2f2.", "...2f2..", "2.2f2...", ".2f2....", "..77....", ".7.7....", "........"],
            "vital": ["..888...", "..888...", "8888888.", "8888888.", "8888888.", "..888...", "..888...", "........"],
            "bracer": ["........", ".777777.", "7e7ee7e7", "7eee8ee7", "7eee8ee7", "7e7ee7e7", ".777777.", "........"],
            "blink": [".....bb.", "....b3b.", "...b3b..", "e.b3b...", ".eeb....", "..ee....", ".e..e...", "........"]}
    b = bmp(8, 8, 13)
    for y, row in enumerate(pats[kind]):
        for x, ch in enumerate(row):
            if ch != ".":
                b[y][x] = int(ch, 16)
    return b


def pip_tile(a, b):
    """two ability level pips: 0 none, 1 not learned, 2 learned"""
    t = bmp(8, 8, 13)
    for k, s in enumerate((a, b)):
        if s:
            rect(t, 1 + k * 4, 2, 2 + k * 4, 4, 14 if s == 2 else 15)
    return t


def big_digit(ch):
    """8x16 clock digit: the font glyph stretched to two rows, on the opaque HUD colour"""
    g = glyph_tile(ch)
    return [[c or 13 for c in g[y >> 1]] for y in range(16)]

# ---------------------------------------------------------------- map layout (64x64 cells of 16 px)
N = 64
GRASS, TREE, ROAD, WATER, BASE = range(5)
cells = [[GRASS] * N for _ in range(N)]


def side(cx, cy):
    """0 = Radiant (bottom-left of the river), 1 = Dire."""
    return 1 if cy < cx or (cy == cx and cx >= 32) else 0


rnd = random.Random(77)
forest = [[1 if rnd.random() < 0.56 else 0 for _ in range(N)] for _ in range(N)]
for _ in range(4):
    nf = [[0] * N for _ in range(N)]
    for y in range(N):
        for x in range(N):
            n = sum(forest[(y + dy) % N][(x + dx) % N] for dy in (-1, 0, 1) for dx in (-1, 0, 1))
            nf[y][x] = 1 if n >= 5 else 0
    forest = nf


def dseg(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / float(vx * vx + vy * vy)))
    return math.hypot(px - (ax + vx * t), py - (ay + vy * t))


# lane centre lines in cell units (cell centre = c + 0.5)
TOP = [(6, 48), (6, 6), (48, 6)]
BOT = [(16, 57), (57, 57), (57, 16)]
MID = [(14, 49), (49, 14)]
LANES = [TOP, MID, BOT]
RIVER = [(9, 9), (54, 54)]


def lane_dist(x, y):
    best = 99
    for lane in LANES:
        for a, b_ in zip(lane, lane[1:]):
            best = min(best, dseg(x, y, a[0], a[1], b_[0], b_[1]))
    return best


TOWERS_RAD = [(104, 400), (104, 640), (400, 624), (296, 728), (624, 920), (384, 920)]
ANCIENT_RAD = (176, 848)
FOUNTAIN_RAD = (64, 960)


def rot(p):
    return (1024 - p[0], 1024 - p[1])


BUILDINGS = TOWERS_RAD + [ANCIENT_RAD] + [rot(p) for p in TOWERS_RAD] + [rot(ANCIENT_RAD)]

clear = [[0] * N for _ in range(N)]     # cells that must stay open (lanes, river, bases, buildings)
for y in range(N):
    for x in range(N):
        ld = lane_dist(x, y)
        rd = dseg(x, y, *RIVER[0], *RIVER[1])
        in_base = (x <= 15 and y >= 48) or (x >= 48 and y <= 15)
        t = forest[y][x]
        if ld < 2.8 or rd < 2.6 or in_base:
            t = 0
        for bx, by in BUILDINGS:
            if math.hypot(x + 0.5 - bx / 16, y + 0.5 - by / 16) < 3.5:
                t = 0
        if not t:
            clear[y][x] = forest[y][x]
            if ld < 2.8 or rd < 2.6 or in_base:
                clear[y][x] = 1
            for bx, by in BUILDINGS:
                if math.hypot(x + 0.5 - bx / 16, y + 0.5 - by / 16) < 3.5:
                    clear[y][x] = 1
        if x < 2 or y < 2 or x >= N - 2 or y >= N - 2:
            t = 1
            clear[y][x] = 0
        c = TREE if t else GRASS
        if rd < 1.6:
            c = WATER
        if in_base and 2 <= x < N - 2 and 2 <= y < N - 2:
            c = BASE
        if ld < 2.1 and not in_base:
            c = ROAD
        if rd < 1.6:
            c = WATER                       # the river cuts the mid road: units wade across
        cells[y][x] = c
# river ends in small ponds
for cx, cy in RIVER:
    for y in range(cy - 3, cy + 4):
        for x in range(cx - 3, cx + 4):
            if math.hypot(x - cx, y - cy) < 2.6 and cells[y][x] != ROAD:
                cells[y][x] = WATER


def seal_pockets():
    """Grass pockets that touch the open map only through a diagonal gap between two trees
    become forest: units could squeeze in there, but the creep nav fields cannot lead out."""
    from collections import deque
    seen = [[0] * N for _ in range(N)]
    q = deque([(64 >> 4, 960 >> 4)])      # the Radiant fountain
    seen[960 >> 4][64 >> 4] = 1
    while q:
        cx, cy = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            x, y = cx + dx, cy + dy
            if 0 <= x < N and 0 <= y < N and cells[y][x] != TREE and not seen[y][x]:
                seen[y][x] = 1
                q.append((x, y))
    for y in range(N):
        for x in range(N):
            if not seen[y][x]:
                cells[y][x] = TREE


# forests are groups of single trees, each standing on a 2x2-cell block
for by in range(0, N, 2):
    for bx in range(0, N, 2):
        blk = [(bx + dx, by + dy) for dy in (0, 1) for dx in (0, 1)]
        n = sum(cells[y][x] == TREE for x, y in blk)
        free = all(cells[y][x] in (TREE, GRASS) and not clear[y][x] for x, y in blk)
        for x, y in blk:
            if cells[y][x] in (TREE, GRASS):
                cells[y][x] = TREE if (n >= 2 and free) else (GRASS if cells[y][x] == TREE and n < 2 else cells[y][x])

seal_pockets()
# no lone forest cells: a forest cell outside a whole 2x2 tree block becomes grass, unless that opens a pocket
for _ in range(4):
    for y in range(N):
        for x in range(N):
            if cells[y][x] == TREE and not all(cells[(y & ~1) + dy][(x & ~1) + dx] == TREE for dy in (0, 1) for dx in (0, 1)):
                cells[y][x] = GRASS
    seal_pockets()
print("lone forest cells left:", sum(cells[y][x] == TREE and not all(cells[(y & ~1) + dy][(x & ~1) + dx] == TREE
      for dy in (0, 1) for dx in (0, 1)) for y in range(N) for x in range(N)))


def cell(x, y):
    return cells[min(N - 1, max(0, y))][min(N - 1, max(0, x))]


# ---------------------------------------------------------------- textures (16 px periodic)
def periodic_tex(seed, base, flecks, n, blades):
    r = random.Random(seed)
    t = [[base] * 16 for _ in range(16)]
    for _ in range(n):
        x, y = r.randrange(16), r.randrange(16)
        c = r.choice(flecks)
        t[y][x] = c
        if blades and r.random() < 0.6:
            t[(y + 1) % 16][x] = flecks[0]
    return t


TEX_GRASS = [periodic_tex(1, 3, [2, 4, 4], 22, True), periodic_tex(2, 3, [4, 2, 4], 18, True)]
TEX_ASH = [periodic_tex(3, 14, [15, 15, 1], 20, False), periodic_tex(4, 14, [15, 1], 16, False)]
TEX_DIRT = [periodic_tex(5, 9, [10, 10, 8], 18, False)]
TEX_WATER = [[12] * 16 for _ in range(16)]
for y in range(16):
    for x in range(16):
        if (y % 8 == 2 and 2 <= (x + y) % 16 < 7) or (y % 8 == 6 and 10 <= (x + y) % 16 < 13):
            TEX_WATER[y][x] = 11
        if y % 8 == 2 and (x + y) % 16 == 7:
            TEX_WATER[y][x] = 13


def cobble(x, y):
    """Dire stone road: offset cobblestones."""
    bx, by = x % 8, y % 8
    if (y // 8) % 2:
        bx = (x + 4) % 8
    if bx == 0 or by == 0:
        return 1
    return 7 if bx == 1 or by == 1 else 15


def slab(x, y, hi, lo, line_c):
    bx, by = x % 16, y % 16
    if bx == 0 or by == 0:
        return line_c
    if bx == 1 or by == 1:
        return hi
    return lo if (bx + by) % 11 else hi


DARKEN = {2: 5, 3: 2, 4: 2, 6: 2, 8: 1, 9: 8, 10: 9, 14: 1, 15: 14, 7: 14, 12: 11, 13: 12, 11: 1}

LUMPS = [(4, 4, 6.4), (12, 12, 6.4)]


def lump(x, y):
    """Tree crown structure, 16 px periodic: returns (inside, shade) for the nearest lump."""
    lx, ly = x % 16, y % 16
    best = None
    for cx, cy, r in LUMPS:
        for ox in (-16, 0, 16):
            for oy in (-16, 0, 16):
                dx, dy = (lx + 0.5 - cx - ox) / r, (ly + 0.5 - cy - oy) / r
                d = dx * dx + dy * dy
                if best is None or d < best[0]:
                    best = (d, dx, dy)
    return best


def field(layer, px, py):
    u = px / 16.0 - 0.5
    v = py / 16.0 - 0.5
    i, j = math.floor(u), math.floor(v)
    fu, fv = u - i, v - j

    def ind(a, b_):
        return 1.0 if cell(a, b_) == layer else 0.0
    return (ind(i, j) * (1 - fu) * (1 - fv) + ind(i + 1, j) * fu * (1 - fv) +
            ind(i, j + 1) * (1 - fu) * fv + ind(i + 1, j + 1) * fu * fv)


TREE_ART = [
"      ############      ",
"     #mmmmmmmmmmmm#     ",
"   ##mmmmmLmmLmmmmm##   ",
"  #.mmmLmLLLLLLmmmmmm#  ",
" #mmmmLmLLLLLLLLLLmmm.# ",
"#mmmmLmLLLLLLLLLLLmmm.m#",
"#.mmmmLLLLLLLLLLLmmmm.k#",
"#mmmmmLLLLLLLLLLLmmmm#m#",
"#kmmLmLLLLLLLLLLLmmm.kk#",
"#mmLmmLLLLLLLLLLLmmmmm.#",
"#.mmmmmLLLLLLLLmmmmmm.k#",
"#m#m#mLmmLLmmmLLmmmm#m.#",
"#..mmmmmmmmLLmmmmmm...k#",
"#m#m#mmmmmLmmmmLmmmm#.#.",
" #m#.#mmmm.mmm.#k#.#k#  ",
"  #m#m#mmmmmmmkk#.##k   ",
"    #.#.#m#m.#kk#.#.    ",
"     #####.##.####.     ",
"      mm#######km       ",
"      #m#b####kkk       ",
"     #m###bbbb##k#      ",
"    #m##bbbbbbbb#.#     ",
"     #L#bbbbbbbbk#.     ",
"    #m#m##bbbb#k#k#     ",
"     #m#m##bb#kk.#.     ",
"    #.#.#m###kkk#.#     ",
"       #.#.##k#kk.      ",
"        # # .#kk        ",
]


def tree_stamp(s):
    """a single 32x32 tree on a 2x2-cell block, copied pixel for pixel from the Dota pixel-art
    reference: a round crown with a light centre and a dithered dark rim, a red-brown trunk in a
    dithered cast shadow. Rows from 17 down are trunk and shadow on the ground: their greens are
    the ground itself (0) or the ground darkened (-1), so the shadow works on both sides."""
    crown = {'#': 1, 'k': 14, '.': 5, 'm': 5, 'L': 2, 'b': 8} if s else {'#': 1, 'k': 5, '.': 2, 'm': 3, 'L': 4, 'b': 8}
    im = [[0] * 32 for _ in range(32)]
    for y, row in enumerate(TREE_ART):
        for x, ch in enumerate(row):
            if ch == ' ':
                continue
            if y >= 17 and ch in 'mL':
                c = 0
            elif y >= 17 and ch in 'k.':
                c = -1
            else:
                c = crown[ch]
            im[y + 2][x + 4] = c
    return im


TREES = [tree_stamp(s) for s in (0, 1)]


def pixel(px, py, s, var):
    """Colour of world pixel (px, py) in a cell on side s."""
    lx, ly = px % 16, py % 16
    cx, cy = px >> 4, py >> 4
    if cell(cx, cy) == TREE:
        bs = side(cx & ~1, cy & ~1)
        g = (TEX_ASH if bs else TEX_GRASS)[0][ly][lx]
        t = TREES[bs][py % 32][px % 32]
        return DARKEN.get(g, g) if t == -1 else (t or g)
    c = (TEX_ASH if s else TEX_GRASS)[var % 2][ly][lx]
    fr = field(ROAD, px, py)
    fw = field(WATER, px, py)
    fb = field(BASE, px, py)
    if fr >= 0.5:
        c = cobble(px, py) if s else TEX_DIRT[0][ly][lx]
        if fr < 0.56:
            c = 1 if s else 8                               # road edge
        elif fr < 0.62 and not s:
            c = 10                                          # sunlit rim
    elif fr >= 0.42 and not s and fw < 0.5:
        c = 2                                               # darker grass along the road
    if fw >= 0.5:
        c = TEX_WATER[ly][lx]
        if fw < 0.62:
            c = 13 if (lx + ly) % 3 else 12                # foam rim
        elif field(WATER, px - 3, py - 3) < 0.5:
            c = 11                                          # bank shadow
    elif s and field(WATER, px - 7, py + 11) >= 0.5:
        c = 1 if px % 4 == 0 else 14                        # the Dire bank: a dark cliff face
    if fb >= 0.5:
        c = slab(px, py, 10, 10, 9) if not s else slab(px, py, 15, 15, 14)
        if fb < 0.58:
            c = 8 if not s else 1
        elif field(BASE, px - 2, py - 2) < 0.5:
            c = 8 if not s else 14
    return c


def build_map():
    cache = {}
    m = [0] * (128 * 128)
    for ty in range(128):
        for tx in range(128):
            cx, cy = tx >> 1, ty >> 1
            s = side(cx, cy)
            var = (cx * 7 + cy * 3) % 5 == 0
            key = (tx & 1, ty & 1, cx & 1, cy & 1, side(cx & ~1, cy & ~1), s, var, tuple(cell(cx + dx, cy + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)))
            if key not in cache:
                tb = [[pixel(tx * 8 + x, ty * 8 + y, s, var) for x in range(8)] for y in range(8)]
                # store tile pixels relative to a cell-quadrant: textures are 16 px periodic, the
                # neighbourhood is in the key, so the same key always renders the same tile.
                cache[key] = tile_at(tb, 0, 0)
            m[ty * 128 + tx] = cache[key]
    return m


def stamp_fountain(img, x0, y0):
    for y in range(48):
        for x in range(48):
            d = math.hypot(x + 0.5 - 24, y + 0.5 - 24)
            if d >= 23:
                continue
            if d > 19:
                c = 10 if (x + y) % 5 else 9
            elif d > 17:
                c = 8
            elif d < 5:
                c = 10 if d < 3.5 else 9
            elif d < 6:
                c = 13
            else:
                c = 12 if (int(d * 2) + (x // 4)) % 5 else 13
            img[y0 + y][x0 + x] = c


def minimap():
    b = bmp(32, 32)
    for y in range(32):
        for x in range(32):
            ks = [cells[y * 2 + dy][x * 2 + dx] for dy in (0, 1) for dx in (0, 1)]
            s = side(x * 2, y * 2)
            if ROAD in ks:
                c = 7 if s else 9
            elif WATER in ks:
                c = 12
            elif BASE in ks:
                c = 7 if s else 10
            elif ks.count(TREE) >= 2:
                c = 14 if s else 5
            else:
                c = 15 if s else 3
            b[y][x] = c
    for k in range(32):                     # white frame, as on the Dota HUD
        b[0][k] = b[31][k] = b[k][0] = b[k][31] = 13
    return b


# ---------------------------------------------------------------- build
defs = []


def define(name, value):
    defs.append(f"#define {name} {value}")


define("T_FONT", len(tiles) + 1)
for code in range(32, 96):
    tiles.append(tile_at(glyph_tile(chr(code)), 0, 0))
define("T_FONTW", len(tiles) + 1)       # opaque variant for the HUD window; T_FONTW itself is the blank
for code in range(32, 96):
    tiles.append(tile_at([[c or 13 for c in row] for row in glyph_tile(chr(code))], 0, 0))
# coloured popup digits for unit palettes: "0".."9" then "+" ; red = damage, gold = gold
for name, col in (("T_DIGR", 12), ("T_DIGY", 15)):
    define(name, len(tiles) + 1)
    for ch in "0123456789+":
        tiles.append(tile_at([[col if c > 1 else c for c in row] for row in glyph_tile(ch)], 0, 0))
for name, fn in (("T_MELEE", melee_frame), ("T_RANGED", ranged_frame)):
    first = None
    for d in range(3):
        for f in range(2):
            i = add_sprite(fn(d, f))
            first = first or i
    define(name, first)
define("T_TOWER", add_sprite(tower()))
an = ancient()
define("T_ANCIENT", add_sprite([r[0:24] for r in an[0:24]]))
add_sprite([r[24:48] for r in an[0:24]])
add_sprite([r[0:24] for r in an[24:48]])
add_sprite([r[24:48] for r in an[24:48]])
define("T_RAZE", add_sprite(raze_frame(0)))
add_sprite(raze_frame(1))
add_sprite(raze_frame(2))
define("T_SOUL", add_sprite(soul_wave()))
for name, cmap in (("T_FIRE", {12: 15, 13: 12, 14: 15, 1: 12}), ("T_ICE", {12: 5, 13: 8, 14: 5, 1: 4})):
    define(name, add_sprite([[cmap.get(c, c) for c in row] for row in raze_frame(0)]))
    add_sprite([[cmap.get(c, c) for c in row] for row in raze_frame(1)])
    add_sprite([[cmap.get(c, c) for c in row] for row in raze_frame(2)])
define("T_BOLT", add_sprite(bolt()))
define("T_ORB_SF", add_sprite(orb(13, 12)))
define("T_ORB_CREEP", add_sprite(orb(10, 11)))
define("T_ORB_TOWER", add_sprite(orb(15, 5, 5, 3.5)))
define("T_ORB_ICE", add_sprite(orb(8, 5)))
define("T_ORB_FIRE", add_sprite(orb(12, 15)))
define("T_ORB_DARK", add_sprite(orb(13, 12, 12, 2.6)))
define("T_HOOK", add_sprite(hook_head()))
define("T_CHAIN", add_sprite(chain_link()))
define("T_ROT", add_sprite(rot_puff()))
define("T_SPARK", add_sprite(spark(0)))
add_sprite(spark(1))
define("T_POOF", add_sprite(poof(0)))
add_sprite(poof(1))
define("T_UBAR", add_sprite(unit_bar(0)))
for lv in range(1, 9):
    add_sprite(unit_bar(lv))
define("T_HPBAR", add_sprite(ui_bar(0, 9, 10)))
for lv in range(1, 9):
    add_sprite(ui_bar(lv, 9, 10))
define("T_MPBAR", add_sprite(ui_bar(0, 11, 12)))
for lv in range(1, 9):
    add_sprite(ui_bar(lv, 11, 12))
define("T_MARK", add_sprite(marker(0)))
add_sprite(marker(1))
add_sprite(marker(2))
define("T_FRAME", add_sprite(frame_tile(0)))
add_sprite(frame_tile(1))
define("T_XPBAR", add_sprite(ui_bar(0, 6, 12)))
for lv in range(1, 9):
    add_sprite(ui_bar(lv, 6, 12))
define("T_HICON", add_sprite(small_icon("heart")))   # heart, drop, star
add_sprite(small_icon("drop"))
add_sprite(small_icon("star"))
define("T_MINIIT", add_sprite(small_icon("boot")))   # one 8x8 mark per item, split-screen HUD
for k in ("sword", "vital", "blink", "bracer"):
    add_sprite(small_icon(k))
define("T_PIPS", add_sprite(pip_tile(0, 0)))          # 3 * a + b
for a in range(3):
    for b in range(3):
        if a or b:
            add_sprite(pip_tile(a, b))
define("T_BIGD", len(tiles) + 1)                      # "0".."9", ":" as 8x16, column-major (2 tiles each)
for ch in "0123456789:":
    add_sprite(big_digit(ch))
define("T_ITEMS", add_sprite(icon(*ITEM_ICONS[0][:1], *ITEM_ICONS[0][1:5], bg=ITEM_ICONS[0][5])))
for it in ITEM_ICONS[1:]:
    add_sprite(icon(it[0], *it[1:5], bg=it[5]))
define("T_SLOT0", add_sprite(icon("none", 1, bg=1)))   # an empty item slot
define("T_LOCK", add_sprite(icon("lock", 3, 2, 1, 5, 1)))
mini = minimap()
define("T_MINIMAP", add_sprite(mini))   # 4x4 tiles, column-major
logo = make_logo("ANCIENT WARS")
logo_map = add_map(logo)
sprite_tiles = len(tiles)

# heroes live in ROM only: the game copies the four in play into VRAM slots after GFX_TILES
HERO_FNS = [sf_frame, pudge_frame, axe_frame] + [spec_frame(n) for n in
            ("sniper", "zeus", "lina", "cm", "drow", "lion", "jugg")]
hero_tiles = []
for fn in HERO_FNS:
    for d in range(3):
        for f in range(3):
            b = fn(d, f)
            for tx in range(3):
                for ty in range(3):
                    hero_tiles.append(tile_at(b, tx, ty))

# ability icons live in ROM too: the HUD copies the four of the hero on view
skill_icon_tiles = []
for hero in SKILL_ICONS:
    for spec in hero:
        g, cols = spec[0], list(spec[1:])
        bg = cols[4] if len(cols) > 4 else 13
        im = icon(g, *cols[:4], bg=bg)
        for tx in range(2):
            for ty in range(2):
                skill_icon_tiles.append(tile_at(im, tx, ty))

world = build_map()
uniq = {}
map_ground = []
for t in world:
    if t not in dedupe:
        tiles.append(t)
        dedupe[t] = len(tiles)
    map_ground.append(dedupe[t])
# fountains are stamped on top of the generated tiles
for fx, fy in (FOUNTAIN_RAD, rot(FOUNTAIN_RAD)):
    x0, y0 = fx - 24, fy - 24
    img = bmp(48, 48)
    for ty in range(6):
        for tx in range(6):
            t = tiles[map_ground[((y0 >> 3) + ty) * 128 + (x0 >> 3) + tx] - 1]
            for r in range(8):
                for c in range(8):
                    img[ty * 8 + r][tx * 8 + c] = (t[r] >> (28 - c * 4)) & 15
    stamp_fountain(img, 0, 0)
    for ty in range(6):
        for tx in range(6):
            t = tile_at(img, tx, ty)
            if t not in dedupe:
                tiles.append(t)
                dedupe[t] = len(tiles)
            map_ground[((y0 >> 3) + ty) * 128 + (x0 >> 3) + tx] = dedupe[t]
assert len(tiles) < 1280, len(tiles)
assert len(tiles) + 1 + 9 * 18 <= 1280, ("draft hero frames overflow into plane A", len(tiles))

walk = [0 if cells[y][x] == TREE else 1 for y in range(N) for x in range(N)]


# creep lanes in pixels, from the Radiant Ancient to the Dire Ancient
LANES_PX = [
    [(176, 848), (104, 760), (104, 120), (120, 104), (760, 104), (848, 176)],
    [(176, 848), (256, 768), (768, 256), (848, 176)],
    [(176, 848), (264, 920), (904, 920), (920, 904), (920, 264), (848, 176)],
]


def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / float(vx * vx + vy * vy)))
    return math.hypot(px - ax - t * vx, py - ay - t * vy)


def nav_field(lane, tx, ty):
    """Per cell nibble: bits 0-2 the face index (0 = east, clockwise) of the shortest walk to
    (tx, ty), bit 3 set when the cell is within 20 px of the lane, where walking straight works."""
    from collections import deque
    dist = [-1] * (N * N)
    src = (ty >> 4) * N + (tx >> 4)
    dist[src] = 0
    q = deque([src])
    steps = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    while q:
        c = q.popleft()
        cx, cy = c % N, c // N
        for dx, dy in steps:
            x, y = cx + dx, cy + dy
            if not (0 <= x < N and 0 <= y < N) or not walk[y * N + x] or dist[y * N + x] >= 0:
                continue
            if dx and dy and not (walk[cy * N + x] and walk[y * N + cx]):
                continue    # no cutting tree corners: step() slides, it does not squeeze
            dist[y * N + x] = dist[c] + 1
            q.append(y * N + x)
    field = [0] * (N * N)
    for c in range(N * N):
        cx, cy = c % N, c // N
        if any(seg_dist(cx * 16 + 8, cy * 16 + 8, *a, *b) < 20 for a, b in zip(lane, lane[1:])):
            field[c] = 8
        if dist[c] <= 0:
            continue
        for f, (dx, dy) in enumerate(steps):
            x, y = cx + dx, cy + dy
            if 0 <= x < N and 0 <= y < N and dist[y * N + x] == dist[c] - 1:
                if dx and dy and not (walk[cy * N + x] and walk[y * N + cx]):
                    continue
                field[c] |= f
                break
    return [field[i] | (field[i + 1] << 4) for i in range(0, N * N, 2)]


nav_fields = [nav_field(lane, *p) for lane in LANES_PX for p in lane]
# per cell, the index of the nearest lane (for the bots' "where is the enemy hero")
lane_map = []
for c in range(N * N):
    px, py = (c % N) * 16 + 8, (c // N) * 16 + 8
    ds = [min(seg_dist(px, py, *a, *b) for a, b in zip(l, l[1:])) for l in LANES_PX]
    lane_map.append(ds.index(min(ds)))
nav_idx = [sum(len(l) for l in LANES_PX[:j]) + min(k, len(LANES_PX[j]) - 1) for j in range(3) for k in range(6)]


def carr(name, ctype, values, per_line=16, fmt="0x{:04X}"):
    lines = [f"static const {ctype} {name}[{len(values)}] = {{"]
    for i in range(0, len(values), per_line):
        lines.append("  " + ", ".join(fmt.format(v) for v in values[i:i + per_line]) + ",")
    lines.append("};")
    return "\n".join(lines)


out = ["/* Generated by tools/gfx.py - do not edit */", "#ifndef GFX_H", "#define GFX_H", ""]
out += defs
out.append(f"#define LOGO_W {len(logo[0]) // 8}")
out.append(f"#define GFX_TILES {len(tiles)}")
for name, pal in (("pal_map", PAL_MAP), ("pal_ui", PAL_UI), ("pal_logo", PAL_FG), ("pal_rad", PAL_RAD), ("pal_dire", PAL_DIRE)):
    out.append(carr(name, "u16", [md_color(*c) for c in pal], 8))
sin = [max(-64, min(63, int(round(64 * math.sin(2 * math.pi * i / 64))))) for i in range(64)]
out.append(carr("sintab", "s8", sin, 16, "{}"))
out.append(carr("map_logo", "u16", logo_map))
out.append(carr("map_ground", "u16", map_ground))
out.append(carr("walk_map", "u8", walk, 64, "{}"))
for k, lane in enumerate(LANES_PX):
    out.append(carr(("lane_top", "lane_mid", "lane_bot")[k], "s16", [v for p in lane for v in p], 12, "{}"))
out.append(carr("nav_idx", "u8", nav_idx, 6, "{}"))
out.append(carr("lane_map", "u8", lane_map, 64, "{}"))
out.append(carr("nav_map", "u8", [v for f in nav_fields for v in f], 32, "0x{:02X}"))
out.append(carr("gfx_tiles", "u32", [v for t in tiles for v in t], 8, "0x{:08X}"))
out.append(f"#define HERO_ART_N {len(HERO_FNS)}")
out.append(carr("hero_art", "u32", [v for t in hero_tiles for v in t], 8, "0x{:08X}"))
out.append(carr("skill_icons", "u32", [v for t in skill_icon_tiles for v in t], 8, "0x{:08X}"))
out.append("#endif")
with open(OUT, "w") as f:
    f.write("\n".join(out) + "\n")
print(f"gfx.h: {sprite_tiles} sprite/ui tiles, {len(tiles) - sprite_tiles} map tiles, {len(tiles)} total")

if os.environ.get("PREVIEW"):
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)

    def save(name, b, pal, scale=1):
        h, w = len(b), len(b[0])
        with open(os.path.join(ROOT, "build", name + ".ppm"), "wb") as f:
            f.write(f"P6 {w * scale} {h * scale} 255\n".encode())
            for y in range(h * scale):
                for x in range(w * scale):
                    c = b[y // scale][x // scale]
                    r, g, bl = pal[c] if c else (6, 4, 6)
                    f.write(bytes([r * 36, g * 36, bl * 36]))
    full = bmp(1024, 1024)
    for ty in range(128):
        for tx in range(128):
            t = tiles[map_ground[ty * 128 + tx] - 1]
            for r in range(8):
                for c in range(8):
                    full[ty * 8 + r][tx * 8 + c] = (t[r] >> (28 - c * 4)) & 15
    for k, (bx, by) in enumerate(BUILDINGS):
        bm = an if k % 7 == 6 else tower()
        h = len(bm)
        for y in range(h):
            for x in range(h):
                if bm[y][x]:
                    full[by - h // 2 + y][bx - h // 2 + x] = 15
    save("map", full, PAL_MAP)
    sheet = bmp(9 * 24, 5 * 24 + 16)
    for i in range(9):
        for y, row in enumerate(sf_frame(i // 3, i % 3)):
            sheet[y][i * 24:i * 24 + 24] = row
        for y, row in enumerate(pudge_frame(i // 3, i % 3)):
            sheet[24 + y][i * 24:i * 24 + 24] = row
        for y, row in enumerate(axe_frame(i // 3, i % 3)):
            sheet[112 + y][i * 24:i * 24 + 24] = row
    for i in range(6):
        for y, row in enumerate(melee_frame(i // 2, i % 2)):
            sheet[48 + y][i * 16:i * 16 + 16] = row
        for y, row in enumerate(ranged_frame(i // 2, i % 2)):
            sheet[64 + y][i * 16:i * 16 + 16] = row
    for y, row in enumerate(tower()):
        sheet[48 + y][100:132] = row
    for y, row in enumerate(an):
        sheet[48 + y][140:188] = row
    save("units_rad", sheet, PAL_RAD, 4)
    save("units_dire", sheet, PAL_DIRE, 4)
    heroes = bmp(9 * 24, len(HERO_FNS) * 24)
    for h, fn in enumerate(HERO_FNS):
        for i in range(9):
            for y, row in enumerate(fn(i // 3, i % 3)):
                heroes[h * 24 + y][i * 24:i * 24 + 24] = row
    save("heroes_rad", heroes, PAL_RAD, 4)
    sheet = bmp(16 * 5, 16 * 12)
    for h, hero in enumerate(SKILL_ICONS):
        for k, spec in enumerate(hero):
            cols = list(spec[1:])
            im = icon(spec[0], *cols[:4], bg=cols[4] if len(cols) > 4 else 13)
            for y in range(16):
                sheet[h * 16 + y][k * 16:k * 16 + 16] = im[y]
    for k, it in enumerate(ITEM_ICONS + [("none", 1, 1, 1, 5, 1), ("lock", 3, 2, 1, 5, 1)]):
        im = icon(it[0], *it[1:5], bg=it[5])
        for y in range(16):
            sheet[160 + (k // 5) * 16 + y][(k % 5) * 16:(k % 5) * 16 + 16] = im[y]
    save("icons", sheet, PAL_RAD, 4)
