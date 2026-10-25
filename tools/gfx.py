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
# map: 2-4 grass (5/2/14 on the Dire side), 5/2/6 tree crowns, 8-10 orange dirt, 11-13 river, 14/15/7 Dire stone
PAL_MAP = [(0, 0, 0), (0, 0, 0), (0, 3, 1), (1, 4, 1), (2, 5, 1), (0, 2, 1), (3, 6, 2), (3, 3, 6),
           (4, 2, 1), (7, 4, 1), (7, 6, 3), (0, 1, 4), (1, 3, 7), (4, 6, 7), (0, 0, 1), (2, 2, 4)]
PAL_UI = [(0, 0, 0), (0, 0, 0), (7, 7, 7), (5, 7, 7), (3, 6, 7), (2, 4, 7), (7, 7, 2), (7, 4, 0),
          (7, 1, 1), (1, 6, 1), (0, 3, 0), (2, 4, 7), (0, 1, 3), (0, 0, 0), (7, 6, 1), (3, 3, 4)]   # 13: the black HUD
UNIT_COMMON = {0: (0, 0, 0), 1: (0, 0, 0), 2: (2, 2, 2), 3: (4, 4, 4), 4: (6, 6, 6), 5: (7, 7, 7),
               6: (7, 6, 5), 7: (6, 4, 3), 8: (3, 5, 7), 12: (7, 1, 0), 13: (2, 0, 0), 14: (4, 1, 1),
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
# dirs: 0 = down (south), 1 = up (north), 2 = side (east; west is h-flipped); hero32 adds the diagonals
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


SF_S = [   # 32x32 top-down, traced from the Dota 2 / Genesis reference sheet: lyre horns round a
    "                                ",
    "        #              #        ",
    "       #h#           r#h#       ",
    "      #hH#   #    #   #Hh#      ",
    "      #h#   #h#  #h#   #h#      ",
    "     #hh#   #h#  #h#   #hh#     ",
    "     #h#   #hh####hh#   #h#     ",
    "     #h#   #h#hhhh#h#   #h#     ",
    "     #hh# #hh#hHHh#hh# #hh#     ",
    "    ##hhh##h#hhHHhh#h##hhh#r    ",
    "    #hhhhh#h#hhhhhh#h#hhhhh#    ",
    "   r#hhHhh##hhh##hhh##hhHhh#r   ",
    "  r #hhhhh##r#h##h#r##hhhhh# r  ",
    " rk ##hhh###kk####kk###hhh## kr ",
    " kr #h## ####DryyrD#### ##h#  k ",
    "rkD #hD#  ###D#rr#D###  #Dh# Dkr",
    " rk#hh#   #####kk#####   #hh#kr ",
    "rkD#hD#  r#h###kk#####   #Dh#Dkr",
    " r#hD#    #####rr##h##    #Dh#r ",
    "rkr#D# r  ##h##kk##### kr #D#rkr",
    " rk#Dr     ####kk####     rD#kr ",
    "  rkDk     ####rr###h     kDkr  ",
    "   rr      ##D#kk####      rr   ",
    "   r        ###kk###            ",
    "            ###rr#D#            ",
    "             ##kk##             ",
    "             ##kk##             ",
    "              #rr#              ",
    "              r  r              ",
    "                                ",
    "                                ",
    "                                ",
]
SF_N = [   # dark dome head, red eyes over a glowing maw, a red seam down the black body,
    "                                ",
    "        #              #        ",
    "       #h#           r#h#       ",
    "      #hH#   #    #   #Hh#      ",
    "      #h#   #h#  #h#   #h#      ",
    "     #hh#   #h#  #h#   #hh#     ",
    "     #h#   #hh####hh#   #h#     ",
    "     #h#   #h#hhhh#h#   #h#     ",
    "     #hh# #hh#h##h#hh# #hh#     ",
    "    ##hhh##h#hhHHhh#h##hhh#r    ",
    "    #hhhhh#h#hhhhhh#h#hhhhh#    ",
    "   r#hhHhh##hhh##hhh##hhHhh#r   ",
    "  r #hhhhh####h##h####hhhhh# r  ",
    " rk ##hhh###kk#hh#kk###hhh## kr ",
    " kr #h## ####D####D#### ##h#  k ",
    "rkD #hD#  ###D#hh#D###  #Dh# Dkr",
    " rk#hh#   ############   #hh#kr ",
    "rkD#hD#  r#hk##hh##k##   #Dh#Dkr",
    " r#hD#    ###r####rh##    #Dh#r ",
    "rkr#D# r  ##h##hh##### kr #D#rkr",
    " rk#Dr     ##########     rD#kr ",
    "  rkDk     ####hh###h     kDkr  ",
    "   rr      #kD#######      rr   ",
    "   r        ###hh##k            ",
    "            ######D#            ",
    "             ##hh##             ",
    "             ######             ",
    "              #rr#              ",
    "              r  r              ",
    "                                ",
    "                                ",
    "                                ",
]
SF_E = [   # arms apart from it trailing red flame; the side view is a 3/4 turn, far arm darker behind the body (mirrored for west)
    "                                ",
    "        #              #        ",
    "       #h#           r#h#       ",
    "      #hH#   #    #   #Hh#      ",
    "      #h#   #h#  #h#   #h#      ",
    "     #hh#   #h#  #h#   #hh#     ",
    "     #h#   #hh####hh#   #h#     ",
    "     #h#   #h#hhhh#h#   #h#     ",
    "     #hh# #hh#hHHh#hh# #hh#     ",
    "      ##DD#h#hhHHhh#h##hhh#r    ",
    "      #DDD#h#hhhhhh#h#hhhhh#    ",
    "     r#DDh##hhh##hhh##hhHhh#r   ",
    "    r #DDD####r##h###rhhhhh# r  ",
    "   rk ##DD####kk####kk#hhh## kr ",
    "   kr #D#####D##ryyr### ##h#  k ",
    "  rkD #DD####D###rr###  #Dh# Dkr",
    "   rk#DD# #######kk###   #hh#kr ",
    "  rkD#DD# #h###kk#####   #Dh#Dkr",
    "   r#DD#  #####rr##h##    #Dh#r ",
    "  rkr#D# r##h##kk##### kr #D#rkr",
    "   rk#Dr   ####kk####     rD#kr ",
    "    rkDk   ####rr###h     kDkr  ",
    "     rr    ##D#kk####      rr   ",
    "     r      ###kk###            ",
    "            ###rr#D#            ",
    "             ##kk##             ",
    "             ##kk##             ",
    "              #rr#              ",
    "              r  r              ",
    "                                ",
    "                                ",
    "                                ",
]
SF_SA = [   # attack: a red claw slash sweeping round the right side
    "                                ",
    "        #              #        ",
    "       #h#           r#h#       ",
    "      #hH#   #    #   #Hh#      ",
    "      #h#   #h#  #h#   #h#      ",
    "     #hh#   #h#  #h#   #hh#     ",
    "     #h#   #hh####hh#   #h#     ",
    "     #h#   #h#hhhh#h#   #hk     ",
    "     #hh# #hh#hHHh#hh# #hh# r   ",
    "    ##hhh##h#hhHHhh#h##hhh#r r  ",
    "    #hhhhh#h#hhhhhh#h#hhhhh# kr ",
    "   r#hhHhh##hhh##hhh##hhHhh#r   ",
    "  r #hhhhh##r#h##h#r##hhhhh# ryr",
    " rk ##hhh###kk####kk###hhh## kry",
    " kr #h## ####DryyrD#### ##h#  kr",
    "rkD #hD#  ###D#rr#D###  #Dh# Dkr",
    " rk#hh#   #####kk#####   #hh#kr ",
    "rkD#hD#  r#h###kk#####   #Dh#krr",
    " r#hD#    #####rr##h##    #Dhkr ",
    "rkr#D# r  ##h##kk##### kr #Dkrkr",
    " rk#Dr     ####kk####     rD#kr ",
    "  rkDk     ####rr###h     kDkr  ",
    "   rr      ##D#kk####      rr   ",
    "   r        ###kk###            ",
    "            ###rr#D#            ",
    "             ##kk##             ",
    "             ##kk##             ",
    "              #rr#              ",
    "              r  r              ",
    "                                ",
    "                                ",
    "                                ",
]
SF_NA = [   # attack from behind
    "                                ",
    "        #              #        ",
    "       #h#           r#h#       ",
    "      #hH#   #    #   #Hh#      ",
    "      #h#   #h#  #h#   #h#      ",
    "     #hh#   #h#  #h#   #hh#     ",
    "     #h#   #hh####hh#   #h#     ",
    "     #h#   #h#hhhh#h#   #hk     ",
    "     #hh# #hh#h##h#hh# #hh# r   ",
    "    ##hhh##h#hhHHhh#h##hhh#r r  ",
    "    #hhhhh#h#hhhhhh#h#hhhhh# kr ",
    "   r#hhHhh##hhh##hhh##hhHhh#r   ",
    "  r #hhhhh####h##h####hhhhh# ryr",
    " rk ##hhh###kk#hh#kk###hhh## kry",
    " kr #h## ####D####D#### ##h#  kr",
    "rkD #hD#  ###D#hh#D###  #Dh# Dkr",
    " rk#hh#   ############   #hh#kr ",
    "rkD#hD#  r#hk##hh##k##   #Dh#krr",
    " r#hD#    ###r####rh##    #Dhkr ",
    "rkr#D# r  ##h##hh##### kr #Dkrkr",
    " rk#Dr     ##########     rD#kr ",
    "  rkDk     ####hh###h     kDkr  ",
    "   rr      #kD#######      rr   ",
    "   r        ###hh##k            ",
    "            ######D#            ",
    "             ##hh##             ",
    "             ######             ",
    "              #rr#              ",
    "              r  r              ",
    "                                ",
    "                                ",
    "                                ",
]
SF_EA = [   # attack to the side
    "                                ",
    "        #              #        ",
    "       #h#           r#h#       ",
    "      #hH#   #    #   #Hh#      ",
    "      #h#   #h#  #h#   #h#      ",
    "     #hh#   #h#  #h#   #hh#     ",
    "     #h#   #hh####hh#   #h#     ",
    "     #h#   #h#hhhh#h#   #hk     ",
    "     #hh# #hh#hHHh#hh# #hh# r   ",
    "      ##DD#h#hhHHhh#h##hhh#r r  ",
    "      #DDD#h#hhhhhh#h#hhhhh# kr ",
    "     r#DDh##hhh##hhh##hhHhh#r   ",
    "    r #DDD####r##h###rhhhhh# ryr",
    "   rk ##DD####kk####kk#hhh## kry",
    "   kr #D#####D##ryyr### ##h#  kr",
    "  rkD #DD####D###rr###  #Dh# Dkr",
    "   rk#DD# #######kk###   #hh#kr ",
    "  rkD#DD# #h###kk#####   #Dh#krr",
    "   r#DD#  #####rr##h##    #Dhkr ",
    "  rkr#D# r##h##kk##### kr #Dkrkr",
    "   rk#Dr   ####kk####     rD#kr ",
    "    rkDk   ####rr###h     kDkr  ",
    "     rr    ##D#kk####      rr   ",
    "     r      ###kk###            ",
    "            ###rr#D#            ",
    "             ##kk##             ",
    "             ##kk##             ",
    "              #rr#              ",
    "              r  r              ",
    "                                ",
    "                                ",
    "                                ",
]
SF_COLS = {"#": 1, "h": 2, "H": 3, "D": 13, "k": 14, "r": 12, "y": 15}


def sf_frame(d, f, sh=True):
    """Shadow Fiend from above; the walk step bobs a pixel and flickers the flame wisps."""
    rows = ((SF_S, SF_N, SF_E) if f < 2 else (SF_SA, SF_NA, SF_EA))[d]
    b = bmp(32, 32)
    if sh:
        shadow(b, 16, 28, 10, 3.5)
    dy = 1 if f == 1 else 0
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != " " and y + dy < 32:
                if f == 1 and ch in "rk":
                    ch = "k" if ch == "r" else "r"
                b[y + dy][x] = SF_COLS[ch]
    return b


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


PUDGE_S = [   # 32x32 top-down, after the Dota 2 / Genesis reference sheet: green crest, huge pink
    "                                ",
    "                                ",
    "              ####              ",
    "             #GGGG#             ",
    "            #sGggGs#            ",
    "           #sSgGGgSs#           ",
    "          #sSSsggsSSs#          ",
    "      #####sSSSssSSSs#####      ",
    "     #kkss#ss##ss##ss#sskk#     ",
    "    #kssSSk#yy#ss#yy#kSSssk#    ",
    "   #kssSSSSk##DDDD##kSSSSssk#   ",
    "  #kDssSSSSSk#WDDW#kSSSSSssDk#  ",
    "  #kDsssSSSSs#DDDD#sSSSSsssDk#  ",
    " #hhDkssSSSSSkskkskSSSSSsskDhh# ",
    " #hhhDkssSSSSSSssSSSSSSsskDhhh# ",
    " #hhkkksssSSSSSSSSSSSSssskkkhh# ",
    " #ksSkksswwwwwwWWwwwwwwsskkSsk# ",
    " #kSSsk#wwWWWWWrrWWWWWww#ksSSk# ",
    " #kSSsk#wWWWWWWrrWWWWWWw#ksSSk# ",
    " #DsSsk#wWWWWWrrrrWWWWWw#ksSsD# ",
    " #DksskD#wWWrWrWWrWWWWw#DksskD# ",
    "#HDkkkkD#wWWWrWWWWrWWWw#DkkkkDH#",
    "#H##DDk#wwwWWrWWWWrWWwww#kDD##H#",
    "#H# ### #wwwwwwrwwwwwww# ### #H#",
    "H#       #wwwwwwwwwwww#       #H",
    "H#       #gggggggggggg#       #H",
    "#H#  H    #gggggggggg#    H  #H#",
    " #HHH     #Dkk####kkD#     HHH# ",
    "  r       ############       r  ",
    "   r                        r   ",
    "                                ",
    "                                ",
]
PUDGE_N = [   # gut, bloody apron, hooks in both fists; S = towards the camera, N = back
    "                                ",
    "                                ",
    "              ####              ",
    "             #GGGG#             ",
    "            #sGggGs#            ",
    "           #sSGggGSs#           ",
    "          #sSSGggGSSs#          ",
    "      #####sSSsGGsSSs#####      ",
    "     #kkss#sSssGGssSs#sskk#     ",
    "    #kssSSksSssssssSskSSssk#    ",
    "   #kssSSSSksSssssSsrSSSSssk#   ",
    "  #kDssSSSSrkssssssrSSSSSssDk#  ",
    "  #kDsssSSSSrkskksksSSSSsssDk#  ",
    " #hhDkssSSSSSrkssksSSSSSsskDhh# ",
    " #hhhDkssSSSSSskksSSSSSsskDhhh# ",
    " #hhkkksssSSSSSssSSSSrssskkkhh# ",
    " #ksSkksssSSSSSssSSSSSssskkSsk# ",
    " #kSSsk#ssrSSSskksSSSSss#ksSSk# ",
    " #kSSsk#ksSSSsskkssSSSrk#ksSSk# ",
    " #DsSsk#kssssskkkksssssk#ksSsD# ",
    " #DksskD#kkkkkkkkkkkkkk#DksskD# ",
    "#HDkkkkD#DwwwwwwwwwwwwD#DkkkkDH#",
    "#H##DDk#ggDwggggggggwDgg#kDD##H#",
    "#H# ### #gggggggggggggg# ### #H#",
    "H#       #gggggggggggg#       #H",
    "H#       #gggggggggggg#       #H",
    "#H#  H    #gggggggggg#    H  #H#",
    " #HHH     #Dkk####kkD#     HHH# ",
    "  r       ############       r  ",
    "   r                        r   ",
    "                                ",
    "                                ",
]
PUDGE_E = [   # facing right; the game mirrors it for west
    "                                ",
    "                                ",
    "                ###             ",
    "              ##GGG#            ",
    "             #sGgGGs#           ",
    "            #ssGgGSs#           ",
    "         ####ssSGgSSs#          ",
    "        #kkss#sSSSs##s#         ",
    "       #kssSSksSSs#yy#s#        ",
    "      #kssSSSSksSSs##sDD#       ",
    "     #kDssSSSSSksSSssW#D#       ",
    "     #kDsssSSSSSkSSSssDD#       ",
    "    #hhDkssSSSSSSkSSSSssk#      ",
    "    #hhhDkssSSSSSSSSSSSSs#      ",
    "    #hhkkksssSSSSSSSSSSSSs#     ",
    "    #ksSkksssSSSSwwwwwSSSs#     ",
    "    #kSSsk#ssSSwwWWWWWwSss#     ",
    "    #kSSsk#kSSwWWWWWWWWwss#     ",
    "    #DsSsk#kssWWWWrrWWWWwk#     ",
    "    #DksskD#ksWWWWrrWWWWw#      ",
    "    #HkkkkD#kkwWWrWWrWWWw#      ",
    "    #H#DDk#kkkwwrWWWWrww#       ",
    "   #H# ### #DgwwwwrwwwD#        ",
    "   H#       #gggggggggg#        ",
    "   H#       #ggggg#ggg#         ",
    "   #H#  H   #Dkk# #Dkk#         ",
    "    #HHH     ####  ####         ",
    "     r                          ",
    "      r                         ",
    "                                ",
    "                                ",
    "                                ",
]
PUDGE_SA = [   # attack: the hook arm swung overhead
    "                           #H#  ",
    "                          #HWH# ",
    "              ####        #Hk#  ",
    "             #GGGG#      #kk#   ",
    "            #sGggGs#     #ksk#  ",
    "           #sSgGGgSs#   #ksSk#  ",
    "          #sSSsggsSSs#  #kSsk#  ",
    "      #####sSSSssSSSs###ksSk#   ",
    "     #kkss#ss##ss##ss#s#kSsk#   ",
    "    #kssSSk#yy#ss#yy#k#kSsk#    ",
    "   #kssSSSSk##DDDD##kS#kSsk##   ",
    "  #kDssSSSSSk#WDDW#kSSksSk#Dk#  ",
    "  #kDsssSSSSs#DDDD#sSSkSk#sDk#  ",
    " #hhDkssSSSSSkskkskSSSsk#       ",
    " #hhhDkssSSSSSSssSSSSSSss       ",
    " #hhkkksssSSSSSSSSSSSSsss       ",
    " #ksSkksswwwwwwWWwwwwwwss       ",
    " #kSSsk#wwWWWWWrrWWWWWww#       ",
    " #kSSsk#wWWWWWWrrWWWWWWw#       ",
    " #DsSsk#wWWWWWrrrrWWWWWw#       ",
    " #DksskD#wWWrWrWWrWWWWw#D       ",
    "#HDkkkkD#wWWWrWWWWrWWWw#D       ",
    "#H##DDk#wwwWWrWWWWrWWwww#       ",
    "#H# ### #wwwwwwrwwwwwww#        ",
    "H#       #wwwwwwwwwwww#         ",
    "H#       #gggggggggggg#         ",
    "#H#  H    #gggggggggg#          ",
    " #HHH     #Dkk####kkD#          ",
    "  r       ############          ",
    "   r                            ",
    "                                ",
    "                                ",
]
PUDGE_NA = [   # attack from behind
    "                           #H#  ",
    "                          #HWH# ",
    "              ####        #Hk#  ",
    "             #GGGG#      #kk#   ",
    "            #sGggGs#     #ksk#  ",
    "           #sSGggGSs#   #ksSk#  ",
    "          #sSSGggGSSs#  #kSsk#  ",
    "      #####sSSsGGsSSs###ksSk#   ",
    "     #kkss#sSssGGssSs#s#kSsk#   ",
    "    #kssSSksSssssssSsk#kSsk#    ",
    "   #kssSSSSksSssssSsrS#kSsk##   ",
    "  #kDssSSSSrkssssssrSSksSk#Dk#  ",
    "  #kDsssSSSSrkskksksSSkSk#sDk#  ",
    " #hhDkssSSSSSrkssksSSSsk#       ",
    " #hhhDkssSSSSSskksSSSSSss       ",
    " #hhkkksssSSSSSssSSSSrsss       ",
    " #ksSkksssSSSSSssSSSSSsss       ",
    " #kSSsk#ssrSSSskksSSSSss#       ",
    " #kSSsk#ksSSSsskkssSSSrk#       ",
    " #DsSsk#kssssskkkksssssk#       ",
    " #DksskD#kkkkkkkkkkkkkk#D       ",
    "#HDkkkkD#DwwwwwwwwwwwwD#D       ",
    "#H##DDk#ggDwggggggggwDgg#       ",
    "#H# ### #gggggggggggggg#        ",
    "H#       #gggggggggggg#         ",
    "H#       #gggggggggggg#         ",
    "#H#  H    #gggggggggg#          ",
    " #HHH     #Dkk####kkD#          ",
    "  r       ############          ",
    "   r                            ",
    "                                ",
    "                                ",
]
PUDGE_EA = [   # attack to the side: the hook thrust forward
    "                                ",
    "                                ",
    "                ###             ",
    "              ##GGG#            ",
    "             #sGgGGs#           ",
    "            #ssGgGSs#           ",
    "         ####ssSGgSSs#          ",
    "        #kkss#sSSSs##s#         ",
    "       #kssSSksSSs#yy#s#        ",
    "      #kssSSSSksSSs##sDD#       ",
    "     #kDssSSSSSksSSssW#D#       ",
    "     #kDsssSSSSSkSSSssDD#       ",
    "    #hhDkssSSSSSSkSSSSssk#      ",
    "    #hhhDkssSSSSSSSSSS#kk##     ",
    "    #hhkkksssSSSSSSSSSsSSkk#####",
    "    #ksSkksssSSSSwwwwwsSSSkkkkk#",
    "    #kSSsk#ssSSwwWWWWW#kkk#####H",
    "    #kSSsk#kSSwWWWWWWW#####    #",
    "    #DsSsk#kssWWWWrrWWWWwk#     ",
    "    #DksskD#ksWWWWrrWWWWw#      ",
    "    #HkkkkD#kkwWWrWWrWWWw#      ",
    "    #H#DDk#kkkwwrWWWWrww#       ",
    "   #H# ### #DgwwwwrwwwD#        ",
    "   H#       #gggggggggg#        ",
    "   H#       #ggggg#ggg#         ",
    "   #H#  H   #Dkk# #Dkk#         ",
    "    #HHH     ####  ####         ",
    "     r                          ",
    "      r                         ",
    "                                ",
    "                                ",
    "                                ",
]
PUDGE_COLS = {"#": 1, "S": 6, "s": 7, "k": 14, "D": 13, "G": 10, "g": 9, "W": 5, "w": 4, "r": 12,
              "H": 3, "h": 2, "y": 15}


def pudge_frame(d, f, sh=True):
    """The Butcher seen from above, after the Dota 2 / Genesis top-down reference sheet. The green
    crest and trousers are colours 9-10; the walk step bobs the body a pixel."""
    rows = ((PUDGE_S, PUDGE_N, PUDGE_E) if f < 2 else (PUDGE_SA, PUDGE_NA, PUDGE_EA))[d]
    b = bmp(32, 32)
    if sh:
        shadow(b, 16, 28, 11, 3.5)
    dy = 1 if f == 1 else 0
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != " " and y + dy < 32:
                b[y + dy][x] = PUDGE_COLS[ch]
    return b


def viper_wing(b, f, span=1.0):
    """Viper's left wing from above, after the Dota 2 look: spread flat and wide, the leading edge
    bowed up to a spiked elbow, the trailing edge torn into long spikes, dark grey membrane with
    dark green veins fanning from the shoulder. The walk step lifts and folds the tips (a flap)."""
    sx, sy = 14, 10
    k, lift = {0: (1.0, 0), 1: (0.84, -2), 2: (1.0, -1)}[f]
    k *= span

    def P(x, y):
        return round(sx + (x - sx) * k), round(sy + (y - sy) * k + lift * (sx - x) / 14)

    elbow, tip = P(9, 6), P(0, 12)
    spikes = [P(1, 18), P(4, 21), P(8, 22), P(12, 21)]
    mem = [(sx, sy - 1), elbow, P(4, 7), tip, spikes[0], P(3, 15.5), spikes[1], P(6, 17), spikes[2], P(9.5, 17.5),
           spikes[3], P(13, 17.5), (14, 19)]
    for y in range(32):
        for x in range(16):
            if point_in_poly(x + 0.5, y + 0.5, mem):
                b[y][x] = 2
    for p in spikes:                                     # veins out to every spike
        line(b, sx - 1, sy + 1, *p, 9)
    line(b, *elbow, *spikes[0], 9)
    line(b, sx, sy - 1, *elbow, 10)                      # leading edge with a spiked elbow
    line(b, *elbow, *P(4, 7), 10)
    line(b, *P(4, 7), *tip, 10)
    put(b, *P(9, 5), 11)
    put(b, *P(8, 4), 11)
    put(b, *P(4, 6), 11)
    put(b, *tip, 11)


def viper_frame(d, f, sh=True, span=1.0):
    """Viper, the netherdrake, from above: wide dark wings, a narrow dark body with a glowing
    yellow-green spine from tail to head.
    North is the south pose turned round without the face; the side pose is it turned a quarter,
    head east. The attack thrusts the head and spits a poison glob."""
    b = bmp(32, 32)
    viper_wing(b, f, span)
    for y in range(32):
        b[y][16:] = b[y][:16][::-1]
    ell(b, 16, 12, 3.2, 6, 2)                            # chest, tapering to the tail
    ell(b, 16, 17, 2.4, 3.5, 2)
    rect(b, 15, 2, 16, 6, 2)
    put(b, 15, 1, 11)
    put(b, 16, 1, 11)
    for y in range(3, 21):                               # the segmented glowing spine
        c = 11 if y % 3 == 0 else 15
        put(b, 15, y, c)
        put(b, 16, y, c)
    for y in range(8, 20, 3):                            # ribs
        put(b, 14, y, 9)
        put(b, 17, y, 9)
    dy = 1 if f == 2 else 0
    ell(b, 16, 22.5 + dy, 2.6, 2.5, 2)                   # head
    rect(b, 15, 21 + dy, 16, 22 + dy, 11)
    for x, y in ((13, 20), (18, 20)):                    # head spikes
        put(b, x, y + dy, 11)
    if d != 1:
        put(b, 14, 23 + dy, 15)                          # eyes and the glowing jaw
        put(b, 17, 23 + dy, 15)
        rect(b, 15, 24 + dy, 16, 24 + dy, 11)
    if f == 2:
        rect(b, 15, 27, 16, 28, 11)                      # the poison glob
        put(b, 16, 27, 15)
        put(b, 15, 29, 11)
    b = add_outline(b)
    if d == 1:
        b = b[30::-1] + [[0] * 32]
    elif d == 2:
        b = [[b[x][31 - y] for x in range(32)] for y in range(32)]
    o = bmp(32, 32)
    if sh:
        shadow(o, 16, 28, 10, 3.5)
    for y in range(32):
        for x in range(32):
            if b[y][x]:
                o[y][x] = b[y][x]
    return o


# ------------------------------------------------------------ hand-drawn 32x32 kit
def mirror_rows(half):
    """a front or back view drawn as its left half; the right half is the mirror image"""
    return [h.ljust(16)[:16] + h.ljust(16)[:16][::-1] for h in half]


def pad_rows(rows):
    return [list(r.ljust(32)) for r in rows] + [[" "] * 32 for _ in range(32 - len(rows))]


def overlay(rows, pts):
    rows = pad_rows(rows)
    for x, y, ch in pts:
        rows[y][x] = ch
    return ["".join(r) for r in rows]


def limb(rows, path, c=("S", "s"), wrap=None):
    """a 2-px arm along the joint path, outlined in black even where it crosses the body;
    wrap = (n, ch) paints the last n steps as a bracer"""
    rows = pad_rows(rows)
    px = []
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        for i in range(n + 1):
            x, y = round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n)
            px += [(x, y, c[0]), (x + 1, y, c[1]), (x, y + 1, c[1]), (x + 1, y + 1, c[1])]
    if wrap:
        px += [(x, y, wrap[1]) for x, y, _ in px[-4 * wrap[0]:]]
    own = {(x, y) for x, y, _ in px}
    for x, y, _ in px:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            X, Y = x + dx, y + dy
            if 0 <= X < 32 and 0 <= Y < 32 and (X, Y) not in own:
                rows[Y][X] = "#"
    for x, y, ch in px:
        rows[y][x] = ch
    return ["".join(r) for r in rows]


def katana(rows, x0, y0, x1, y1, hilt=3, cols="DYW"):
    """a blade from the fist (x0, y0) to the tip: dark hilt, a gold guard, then steel"""
    rows = pad_rows(rows)
    n = max(abs(x1 - x0), abs(y1 - y0))
    pts = [(round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n),
            cols[0] if i < hilt else (cols[1] if i == hilt else cols[2])) for i in range(n + 1)]
    for x, y, _ in pts:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            X, Y = x + dx, y + dy
            if 0 <= X < 32 and 0 <= Y < 32 and rows[Y][X] == " ":
                rows[Y][X] = "#"
    for x, y, ch in pts:
        if 0 <= x < 32 and 0 <= y < 32:
            rows[y][x] = ch
    return ["".join(r) for r in rows]


def ascii_frame(poses, cols, d, f, sh=True, rx=10):
    """a hand-drawn hero: poses = (S, N, E, S attack, N attack, E attack); the walk step bobs a pixel"""
    rows = poses[d + (3 if f == 2 else 0)]
    b = bmp(32, 32)
    if sh:
        shadow(b, 16, 28, rx, 3.5)
    dy = 1 if f == 1 else 0
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != " " and y + dy < 32:
                b[y + dy][x] = cols[ch]
    return b


JUGG_S_HALF = [
"              ##",
"            ##OO",
"          ##OOGG",
"        ##OGGGgg",
"       #OG######",
"       #O#YYYYYY",
"      #OG#YoYYYY",
"      #OG#YDDYYr",
"      #Gg#Y##YYr",
"      #Gg#o##YYY",
"      #Gg#oYYYYY",
"      #Gg##k####",
"      #Gg#kkWkWk",
"     #sGg##kkkkk",
"    #sSsg#sssss#",
"   #sSSSSs#sSSss",
"   #sSSSSs#sSSSs",
"   #ksSSsk#ksSSs",
"    #kSSk#kssSss",
"    #GGGG#ksksss",
"    #GOOG#kkkkks",
"    #ssSs#GGGGOO",
"     #ssk#hhhhGO",
"      ##hhhhhHHH",
"       #hhhhhHH#",
"       #hhhhHHH#",
"       #hhhhhHH#",
"       #GGGGGGG#",
"       #kkkkkkk#",
"        ########",
]   # Juggernaut: a wooden tiki mask under an orange mane, bare chest, baggy grey trousers
JUGG_N_HALF = [
"              ##",
"            ##OO",
"          ##OOGG",
"        ##OGGGOO",
"       #OG#OOGGO",
"       #O#OGGOOG",
"      #OG#OGgGGO",
"      #OG#hhhhhh",
"      #Gg#GGOOGG",
"      #Gg#OGgGGO",
"      #Gg#GgGOGg",
"      #Gg#gGgGOG",
"      #Gg##gGgGG",
"     #sGg##gGgGg",
"    #sSsg#ssgGgG",
"   #sSSSSs#sSsgG",
"   #sSSSSs#sSSsg",
"   #ksSSsk#ksSSs",
"    #kSSk#kssSsk",
"    #GGGG#ksssks",
"    #GOOG#kkkkks",
"    #ssSs#GGGGOO",
"     #ssk#hhhhGO",
"      ##hhhhhHHH",
"       #hhhhhHH#",
"       #hhhhHHH#",
"       #hhhhhHH#",
"       #GGGGGGG#",
"       #kkkkkkk#",
"        ########",
]   # from behind: the mane spills down the back over the mask strap
JUGG_E = [
"                                ",
"                ####            ",
"              ##OOOO##          ",
"            ##OOGGGGOO#         ",
"           #OOGGgg######        ",
"          #OGGgg#YYYYYYY#       ",
"         #OGGgg#oYYYYYYY#       ",
"         #OGgg#ooYYYDDYr#       ",
"        #OGGg#ooYYYY##Yr#       ",
"        #OGg##ooYYYY##YY#       ",
"        #OGg#ooYYYYYYYYY#       ",
"       #OGg##oYYY######Y#       ",
"       #OGg#kooY#WkWkWk#        ",
"       #OGg##kkk#######         ",
"       #OGg##ssskk#             ",
"      #OGg#ssSSSSss#            ",
"      #Gg#sSSSSSSSss#           ",
"      #Gg#sSSSSSSSSs#           ",
"      #g#ksSSSSSSssk#           ",
"       #kkssSSSSssk#            ",
"       #kksssssSSkk#            ",
"        #GGGGGGOOG#             ",
"        #hhhhhhGO#              ",
"       #hhhhhhhHHH#             ",
"       #hhhhhhhHHH#             ",
"      #hhhh##hhhHHH#            ",
"      #hhh#  #hhhHH#            ",
"      #GGG#  #GGGGG#            ",
"      #kkkk# #kkkkkk#           ",
"       ####   ######            ",
]   # facing right, the mane streaming back
JUGG_COLS = {"#": 1, "S": 6, "s": 7, "k": 14, "Y": 15, "o": 7, "D": 13, "r": 12, "W": 5, "w": 4, "H": 3,
             "h": 2, "G": 10, "g": 9, "O": 11}
_JS, _JN = mirror_rows(JUGG_S_HALF), mirror_rows(JUGG_N_HALF)
JUGG_POSES = (
    katana(_JS, 6, 21, 1, 30),                                       # katana hanging from the right fist
    katana(_JN, 25, 21, 30, 30),
    katana(limb(JUGG_E, [(13, 15), (13, 18), (18, 20)], wrap=(2, "G")), 20, 20, 31, 13),
    overlay(katana(_JS, 25, 20, 3, 26, 2), [(x, 27 + (x < 10), "w") for x in range(5, 22)]),   # flat sweep
    katana(_JN, 25, 18, 29, 1, 2),                                   # blade raised overhead
    overlay(katana(limb(JUGG_E, [(13, 15), (16, 16), (20, 16)], wrap=(2, "G")), 22, 16, 31, 22, 2),
            [(27, 24, "w"), (28, 25, "w"), (29, 26, "w"), (30, 27, "w")]),                     # forward slash
)


def jugg_frame(d, f, sh=True):
    return ascii_frame(JUGG_POSES, JUGG_COLS, d, f, sh)


# Axe: red-skinned brute, black topknot and beard, steel pauldrons, a double-bitted battle axe
AXE_COLS = {"#": 1, "S": 12, "s": 10, "k": 14, "D": 13, "Y": 15, "h": 2, "H": 3, "W": 4, "V": 5, "t": 7, "O": 11, "g": 9, "w": 4}
AXE_S_HALF = [
"                ",
"               #",
"              #h",
"             #hH",
"            ##hh",
"           #hhhh",
"           #hSSS",
"           #k##S",
"           #kSYs",
"           #ksSS",
"           #k#hh",
"      #### #khhh",
"    ##HHHH##khhh",
"   #HVVVHHH#Shhh",
"  #HVWWHHHH#SShh",
"  #HVWHHHHk#SSSh",
"  #hHHHHkSs#SSSs",
"  ##hhhh#sSs#SSs",
"   #kSSs#sSSs#Ss",
"   #kSSs#ssSSs#s",
"   #kSss#kssSSss",
"   #kssD#kkssssk",
"   #ksD##kOOOOOO",
"   #SSs##kOYYOgO",
"   #sSs# #ghhhhh",
"    #k#  #hhhhhh",
"     #   #hhhhh#",
"         #hhhhh#",
"         #kkkkk#",
"          ######",
]
AXE_N_HALF = [
"                ",
"               #",
"              #h",
"             #hH",
"            ##hh",
"           #hhhh",
"           #hhhh",
"           #khhh",
"           #kshh",
"           #kSSh",
"           #ksSS",
"      #### #ksss",
"    ##HHHH##kSSS",
"   #HVVVHHH#sSSS",
"  #HVWWHHHH#sSSS",
"  #HVWHHHHk#sSSs",
"  #hHHHHkSs#sSSs",
"  ##hhhh#sSs#sSs",
"   #kSSs#sSSs#ss",
"   #kSSs#ssSSsks",
"   #kSss#kssSSss",
"   #kssD#kkssssk",
"   #ksD##kOOOOOO",
"   #SSs##kOOOOgO",
"   #sSs# #ghhhhh",
"    #k#  #hhhhhh",
"     #   #hhhhh#",
"         #hhhhh#",
"         #kkkkk#",
"          ######",
]
AXE_E = [
"                                ",
"              ##                ",
"             #hh#               ",
"            #hHh#               ",
"           ##hh##               ",
"         ##hhhhhh##             ",
"        #hhhhhSSSSS#            ",
"        #hhhhSSSSSSS#           ",
"        #hhhkSS###SS#           ",
"        #hhhkSSSY#SSS#          ",
"        #hhkssSSSSSSS#          ",
"        #hhkss#hhhsss#          ",
"       ##hkkshhhhhhhh#          ",
"     ##HHH#khhhhhhhhh#          ",
"    #HVVHHH#hhhhHhhh#           ",
"   #HVWHHHHH#hhhhhh#            ",
"   #HWHHHHHk#hhhhh#             ",
"   #hHHHHkSs#Shhhs#             ",
"   ##hhhh#sSs#SSss#             ",
"     #ss#ssSSSsSss#             ",
"     #ks#sSSSSSSss#             ",
"     #k##kssssssk#              ",
"      ##kOOOOOOOO#              ",
"       #kOOOOYYOO#              ",
"       ##ghhhhhhh#              ",
"       #hhhhhhhhhh#             ",
"      #hhhh##hhhhhh#            ",
"      #hhh#  #hhhhh#            ",
"      #kkkk# #kkkkkk#           ",
"       ####   ######            ",
]
_AS, _AN = mirror_rows(AXE_S_HALF), mirror_rows(AXE_N_HALF)
AXE_V = ["##         ##", "#V#       #V#", "#VW#     #WV#", "#VWW#####WWV#", "#VWWHHtHHWWV#", "#VWW#####WWV#",
         "#VW#     #WV#", "#V#       #V#", "##         ##"]
AXE_H = ["".join(r[i] for r in AXE_V) for i in range(9)]
def axe_haft(rows, x0, y0, x1, y1):
    """the haft from the fist (x0, y0) to (x1, y1), straight up/down or across, with a double-bit
    crescent head stamped at (x1, y1)"""
    r = pad_rows(katana(rows, x0, y0, x1, y1, 0, "ttt"))
    st = AXE_V if x0 == x1 else AXE_H
    h, w = len(st), len(st[0])
    for y, row in enumerate(st):
        for x, ch in enumerate(row):
            X, Y = x1 - w // 2 + x, y1 - h // 2 + y
            if ch != " " and 0 <= X < 32 and 0 <= Y < 32:
                r[Y][X] = ch
    return ["".join(q) for q in r]
AXE_POSES = (
    axe_haft(_AS, 27, 25, 27, 7),
    axe_haft(_AN, 4, 25, 4, 7),
    axe_haft(limb(AXE_E, [(12, 16), (13, 20), (17, 21)], ("S", "s"), (2, "D")), 19, 26, 19, 5),
    overlay(axe_haft(_AS, 27, 25, 6, 25), [(x, 29, "w") for x in range(9, 24)]),      # low cleave across the front
    axe_haft(_AN, 27, 18, 27, 4),                                                    # raised overhead
    axe_haft(limb(AXE_E, [(12, 15), (16, 15), (20, 15)], ("S", "s"), (2, "D")), 20, 16, 27, 16),   # chop forward
)


def axe_frame(d, f, sh=True):
    return ascii_frame(AXE_POSES, AXE_COLS, d, f, sh, 11)



# Sniper: a short Keen in a steel helmet with goggles, a bushy beard, green coat and a long scoped rifle
SNIPER_COLS = {"#": 1, "S": 6, "s": 7, "k": 14, "B": 7, "b": 14, "D": 13, "h": 2, "H": 3, "W": 4, "V": 5, "8": 8,
        "G": 10, "g": 9, "L": 11, "t": 7, "Y": 15}
SNIPER_S_HALF = [
"                ",
"                ",
"                ",
"                ",
"          ######",
"         #VWWWWW",
"        #VWWWWHH",
"       #HVWWHHHH",
"      #hHHHHHHHH",
"     #hhh#######",
"      ##S#88#SSS",
"       #S#8V#SSS",
"       #ks##SSSs",
"       #kBBBsSSs",
"       #kBBBBBBb",
"       #BBBbBBBB",
"      ##BBbBBBBb",
"    ##gG#BBbBBBB",
"   #gGLG#kBBbBBB",
"   #gGLG#GkBBbBB",
"   #gGGG#GGkBBbB",
"   #SSs##GGGkBBB",
"   #ss# #hhYhkkk",
"    ##  #hhhhhhh",
"        #gGGGGGG",
"        #gGG##GG",
"       #hhhh##hh",
"       #hhhh##hh",
"        ####  ##",
]
SNIPER_N_HALF = [
"                ",
"                ",
"                ",
"                ",
"          ######",
"         #VWWWWW",
"        #VWWWWWW",
"       #HVWWWWHH",
"      #hHHHHHHHH",
"     #hhhHHHHHHH",
"      ##hhhhhhhh",
"       #ks#hhhhh",
"       #ksSSSSSs",
"       #kssSSSSs",
"       #kGGGGGGG",
"      ##gGGGGGGG",
"      #gGGLGGGGG",
"    ##gG#gGGGLGG",
"   #gGLG#gGGGGLG",
"   #gGLG#gGGGGGG",
"   #gGGG#ggGGGGG",
"   #SSs##ggGGGGG",
"   #ss# #hhhhkkk",
"    ##  #hhhhhhh",
"        #gGGGGGG",
"        #gGG##GG",
"       #hhhh##hh",
"       #hhhh##hh",
"        ####  ##",
]
SNIPER_E = [
"                                ",
"                                ",
"                                ",
"                                ",
"           ######               ",
"         ##VWWWWW#              ",
"        #VVWWWWWHH#             ",
"       #HVWWWWHHHHH#            ",
"      #hHHHHHHHHHHHH##          ",
"      #hhhhhh########           ",
"       #hhhSS#88#SS#            ",
"       #hhhSS#8V#SSS#           ",
"       #khsSSs##SSSS#           ",
"       #kkssSSBBBSSs#           ",
"        #kssBBBBBBBB#           ",
"        #kkBBBBbBBBB#           ",
"         #BBBBbBBBB#            ",
"        ##gBBBbBBB#             ",
"       #gGGgBBbBB#              ",
"       #gGGGkBBB#               ",
"       #gGGGGkB#                ",
"       #ggGGGGG#                ",
"       #hhhhYhh#                ",
"       #hhhhhhh#                ",
"       #gGGGGGG#                ",
"      #gGGG#gGGG#               ",
"      #hhhh#hhhhh#              ",
"      #hhhh#hhhhhh#             ",
"       ####  #####              ",
]
_SS, _SN = mirror_rows(SNIPER_S_HALF), mirror_rows(SNIPER_N_HALF)
def rifle(rows, x0, y0, x1, y1, flash=False):
    """stock from (x0, y0), a long barrel to the muzzle at (x1, y1), a dark scope on top"""
    r = katana(rows, x0, y0, x1, y1, 5, "tHh")
    n = max(abs(x1 - x0), abs(y1 - y0))
    sx, sy = round(x0 + (x1 - x0) * 0.45), round(y0 + (y1 - y0) * 0.45)
    pts = [(sx, sy, "8"), (sx + (1 if x0 == x1 else 0), sy - (0 if x0 == x1 else 1), "#")]
    if flash:
        dx, dy = (x1 > x0) - (x1 < x0), (y1 > y0) - (y1 < y0)
        pts += [(x1 + dx, y1 + dy, "V"), (x1 + 2 * dx, y1 + 2 * dy, "Y"), (x1 + dx - dy, y1 + dy + dx, "Y"),
                (x1 + dx + dy, y1 + dy - dx, "Y")]
    return overlay(r, [(x, y, c) for x, y, c in pts if 0 <= x < 32 and 0 <= y < 32])
SNIPER_POSES = (
    rifle(_SS, 26, 25, 26, 3),                                   # rifle stood upright at his side
    rifle(_SN, 5, 25, 5, 3),
    rifle(limb(SNIPER_E, [(12, 18), (15, 21)], ("S", "s")), 17, 23, 29, 11),
    rifle(_SS, 24, 17, 18, 23, True),                            # firing at the camera, the barrel foreshortened
    rifle(_SN, 23, 21, 20, 3, True),
    rifle(limb(SNIPER_E, [(11, 17), (15, 17)], ("S", "s")), 10, 17, 31, 16, True),   # aimed level
)


def sniper_frame(d, f, sh=True):
    return ascii_frame(SNIPER_POSES, SNIPER_COLS, d, f, sh, 10)


# Zeus: a white-haired old god with bushy brows and a long beard, grey robe trimmed in gold, lightning in hand
ZEUS_COLS = {"#": 1, "S": 6, "s": 7, "k": 14, "V": 5, "W": 4, "H": 3, "h": 2, "8": 8, "Y": 15, "D": 13}
ZEUS_S_HALF = [
"                ",
"                ",
"           #####",
"         ##VVVVV",
"        #VVWVVVV",
"       #VWWVVVVV",
"       #VW#SSSSS",
"      #VW#VVV#SS",
"      #VW#S8#SSS",
"      #WV#sSSSsS",
"      #WV#VVVVVs",
"       #WVVVVVVV",
"    ####WVVVWVVV",
"   #WWW#WVVVVWVV",
"  #WWWHH#WVVVVWV",
"  #WWWHH#WWVVVVW",
"  #WWHHH##WWVVVV",
"  #WWHHh#H#WWVVV",
"  #YYYYY#HH#WWVV",
"  #SSss#WWHH#WWV",
"  #Ssk##WWWH#8#W",
"   ##  #YYYYYY8Y",
"       #WWWHHHH#",
"      #WWWWHHHHH",
"      #WWWWHHHHH",
"     #WWWWWHHHHH",
"     #WWWWHHHHHH",
"     #YYYYYYYYYY",
"      ##########",
]
ZEUS_N_HALF = [
"                ",
"                ",
"           #####",
"         ##VVVVV",
"        #VVWVVVV",
"       #VWWVVVVV",
"       #VWVVVVVV",
"      #VWVVVVVVV",
"      #VWVVVWVVV",
"      #WVVVWVVVV",
"      #WVVVVVWVV",
"       #WVVVVVVV",
"    ####WWVVWVVV",
"   #WWW#HWWVVWVV",
"  #WWWHH#HWWVVVW",
"  #WWWHH#HHWWWVV",
"  #WWHHH#WHHWWWW",
"  #WWHHh#WWHHHHW",
"  #YYYYY#WWWHHHH",
"  #SSss#WWWWHHHH",
"  #Ssk##WWWWHHHH",
"   ##  #YYYYYY8Y",
"       #WWWHHHH#",
"      #WWWWHHHHH",
"      #WWWWHHHHH",
"     #WWWWWHHHHH",
"     #WWWWHHHHHH",
"     #YYYYYYYYYY",
"      ##########",
]
ZEUS_E = [
"                                ",
"                                ",
"           #####                ",
"         ##VVVVV##              ",
"        #VVWVVVVVV#             ",
"       #VWWVVVVVVVV#            ",
"       #VWVVVSSSSSSS#           ",
"      #VWVVVSSVVV#SS#           ",
"      #VWVVVSSS8#SSSS#          ",
"      #WVVVVSssSSSSS#           ",
"      #WVVVWsVVVVVVV#           ",
"       #WVVVVVVVVVVV#           ",
"      ##WWVVVWVVVVWV#           ",
"     #WWWWVVVVWVVVW#            ",
"     #WWHHWVVVVWVV#             ",
"     #WWHHWWVVVVW#              ",
"     #WWHHHWWVVV#               ",
"     #WWHHHHWWV#                ",
"     #WWWHHHH##                 ",
"     #WWWHHHHH#                 ",
"     #WWWWHHHH#                 ",
"     #YYYYYY8Y#                 ",
"     #WWWWHHHH#                 ",
"    #WWWWWHHHHH#                ",
"    #WWWWWHHHHH#                ",
"   #WWWWWWHHHHHH#               ",
"   #WWWWWHHHHHHH#               ",
"   #YYYYYYYYYYYY#               ",
"    ############                ",
]
_ZS, _ZN = mirror_rows(ZEUS_S_HALF), mirror_rows(ZEUS_N_HALF)
def bolt_through(rows, pts):
    """a zig-zag of lightning through the points: white core, yellow edges"""
    r = pad_rows(rows)
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        for i in range(n + 1):
            out.append((round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n)))
    for x, y in out:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            X, Y = x + dx, y + dy
            if 0 <= X < 32 and 0 <= Y < 32 and (X, Y) not in out and r[Y][X] == " ":
                r[Y][X] = "Y"
    for x, y in out:
        if 0 <= x < 32 and 0 <= y < 32:
            r[y][x] = "V"
    return ["".join(q) for q in r]
def crackle(rows, x, y):
    return overlay(rows, [(x, y, "V"), (x - 1, y, "Y"), (x + 1, y, "Y"), (x, y - 1, "Y"), (x, y + 1, "8")])
ZEUS_ARM_E = [(8, 15), (9, 19), (11, 21)]
ZEUS_POSES = (
    crackle(_ZS, 4, 20),                                                            # a crackle in the open hand
    crackle(_ZN, 27, 20),
    crackle(limb(ZEUS_E, ZEUS_ARM_E, ("W", "H"), (1, "S")), 13, 22),
    bolt_through(_ZS, [(27, 17), (25, 12), (29, 8), (26, 2)]),                         # arm up, a bolt called down
    bolt_through(_ZN, [(4, 17), (6, 12), (2, 8), (5, 2)]),
    bolt_through(limb(ZEUS_E, [(8, 16), (13, 18), (18, 18)], ("W", "H"), (1, "S")), [(20, 18), (23, 15), (26, 19), (31, 16)]),
)


def zeus_frame(d, f, sh=True):
    return ascii_frame(ZEUS_POSES, ZEUS_COLS, d, f, sh, 10)


# Lina: hair rising in flames, a crimson gown with a gold girdle, fire cupped in her hand
LINA_COLS = {"#": 1, "S": 6, "s": 7, "k": 14, "r": 12, "D": 13, "O": 11, "G": 10, "g": 9, "Y": 15, "V": 5}
LINA_S_HALF = [
"          #    #",
"         #Y#  #Y",
"     #  #OY# #OY",
"    #Y# #OO##OOO",
"    #OY##GOO#GOO",
"     #OO#GOOGGOO",
"     #GOOGGOOGGO",
"      #GGrrGGrrG",
"      #GrrGSSSSS",
"      #Gr#rSSSSS",
"      #Gr#rS#SSS",
"      #Gr#rsSSSS",
"      #Gr##rsSSr",
"      #GrG##ssss",
"      #rG#sSSSSS",
"     #SS#rrrrrrr",
"     #SS#rrrrrrr",
"     #Ss#Drrrrrr",
"     #Ss#DrrYrrr",
"     #ss#DrrrYYY",
"     #SS#DDrrrrr",
"     #Ss##Drrrrr",
"      ##  #Drrrr",
"         #DDrrrr",
"        #DDrrrrr",
"        #DDrrrrr",
"       #DDDrrrrr",
"       #kkkkkkkk",
"        ########",
]
LINA_N_HALF = [
"          #    #",
"         #Y#  #Y",
"     #  #OY# #OY",
"    #Y# #OO##OOO",
"    #OY##GOO#GOO",
"     #OO#GOOGGOO",
"     #GOOGGOOGGO",
"      #GGOGGOOGG",
"      #GGOGGOGGO",
"      #GrGGOGGOG",
"      #GrGOGGOGG",
"      #GrGGGOGGO",
"      #GrrGGGOGG",
"      #GrGrGGGOG",
"      #rG#rGGGGO",
"     #SS#rrrGGGG",
"     #SS#rrrrGGG",
"     #Ss#DrrrrrG",
"     #Ss#DrrYrrr",
"     #ss#DrrrYYY",
"     #SS#DDrrrrr",
"     #Ss##Drrrrr",
"      ##  #Drrrr",
"         #DDrrrr",
"        #DDrrrrr",
"        #DDrrrrr",
"       #DDDrrrrr",
"       #kkkkkkkk",
"        ########",
]
LINA_E = [
"           #   #                ",
"          #Y# #Y#               ",
"     #   #OY##OY#  #            ",
"    #Y# #OOO#OOO# #Y#           ",
"    #OY##GOOOGOOO##OY#          ",
"     #OO#GOOGGOOGGOO#           ",
"     #GOOGGOOGGOOGGO#           ",
"      #GGOGGrrGGrrSS#           ",
"      #GGOGrrSSSSSSS#           ",
"      #GrGGrSSSSSSSSS#          ",
"      #GrGGrSSSS#SSSS#          ",
"      #GrGGrsSSSSSSSS#          ",
"      #GrGGrrsSSSSSr#           ",
"      #GrGGr##sssss#            ",
"      #rGGr#sSSSS#              ",
"      #rGr#rrrrrrr#             ",
"       #r#rrrrrrrrr#            ",
"        #Drrrrrrrrr#            ",
"        #DrrrYrrrrr#            ",
"        #DrrrrYYYYY#            ",
"        #DDrrrrrrrr#            ",
"        #DDrrrrrrrr#            ",
"        #DDrrrrrrr#             ",
"       #DDDrrrrrrr#             ",
"       #DDDrrrrrrrr#            ",
"      #DDDrrrrrrrrr#            ",
"      #DDDDrrrrrrrrr#           ",
"      #kkkkkkkkkkkkk#           ",
"       #############            ",
]
_LS, _LN = mirror_rows(LINA_S_HALF), mirror_rows(LINA_N_HALF)
def fire_in(rows, x, y, big=False):
    """a fireball held in the hand: yellow-white core, orange, then red licks"""
    pts = [(x, y, "V"), (x - 1, y, "Y"), (x + 1, y, "Y"), (x, y - 1, "Y"), (x, y + 1, "O"), (x - 1, y - 1, "O"),
           (x + 1, y - 1, "O"), (x, y - 2, "G"), (x - 1, y + 1, "G"), (x + 1, y + 1, "G")]
    if big:
        pts += [(x - 2, y, "O"), (x + 2, y, "O"), (x, y + 2, "G"), (x - 2, y - 1, "G"), (x + 2, y - 1, "G"), (x - 1, y - 2, "O"),
                (x + 1, y - 2, "O"), (x, y - 3, "Y"), (x - 2, y + 1, "r"), (x + 2, y + 1, "r"), (x - 1, y - 3, "G"), (x + 1, y - 3, "G")]
    r = pad_rows(rows)
    own = {(a, b) for a, b, _ in pts}
    for a, b, _ in pts:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            X, Y = a + dx, b + dy
            if 0 <= X < 32 and 0 <= Y < 32 and (X, Y) not in own and r[Y][X] == " ":
                r[Y][X] = "#"
    for a, b, c in pts:
        if 0 <= a < 32 and 0 <= b < 32:
            r[b][a] = c
    return ["".join(q) for q in r]
def drop_arm(rows, x0, x1):
    """clear the hanging arm (columns x0..x1, rows 15-22) when that hand is raised"""
    return overlay(rows, [(x, y, " ") for x in range(x0, x1 + 1) for y in range(15, 23)])
LINA_POSES = (
    fire_in(_LS, 26, 20),                                               # a flame cupped in the hand
    fire_in(_LN, 5, 20),
    fire_in(limb(LINA_E, [(10, 15), (11, 19), (14, 21)]), 16, 21),
    fire_in(limb(drop_arm(_LS, 24, 26), [(23, 15), (26, 11), (27, 7)]), 27, 4, True),     # arm thrown up, the fireball flaring
    fire_in(limb(drop_arm(_LN, 5, 7), [(8, 15), (5, 11), (4, 7)]), 4, 4, True),
    fire_in(limb(LINA_E, [(10, 15), (15, 15), (20, 14)]), 24, 14, True),
)


def lina_frame(d, f, sh=True):
    return ascii_frame(LINA_POSES, LINA_COLS, d, f, sh, 10)


# Crystal Maiden: a pale blue hooded cloak with white fur trim over a white gown, an ice-crystal staff
CM_COLS = {"#": 1, "S": 6, "s": 7, "k": 14, "8": 8, "H": 3, "h": 2, "V": 5, "W": 4, "t": 7, "Y": 15}
CM_S_HALF = [
"                ",
"           #####",
"         ##88888",
"        #888888V",
"       #88VVVVVV",
"       #8V#YYYYY",
"      #88V#SSSSS",
"      #88V#S#SSS",
"      #88V#sSSSS",
"      #88V##sSSs",
"      #888V##sss",
"     #888VVVVVVV",
"    #8888VVWVVWV",
"   #88888#VVVVVV",
"   #8888H#VVVVVW",
"   #888HH#WVVVVV",
"   #888HH#WVVVVV",
"   #88HHH#WVVVVV",
"   #SS#HH#WWVVVV",
"   #ss#HH#WWVVVV",
"    ##HHH#WWVVVV",
"     #8HH#WWWVVV",
"     #88H#WWWVVV",
"    #888H#WWWWVV",
"    #888HH#WWWVV",
"   #8888HH#WWWWV",
"   #888HHH#WWWWV",
"   #VVVVVVVVVVVV",
"    ############",
]
CM_N_HALF = [
"                ",
"           #####",
"         ##88888",
"        #8888888",
"       #88888888",
"       #88888888",
"      #888888888",
"      #888888888",
"      #888888888",
"      #888888888",
"      #888888888",
"     #888VVVVVVV",
"    #8888VVWVVWV",
"   #88888#888888",
"   #8888H#888888",
"   #888HH#888888",
"   #888HH#H88888",
"   #88HHH#H88888",
"   #SS#HH#HH8888",
"   #ss#HH#HH8888",
"    ##HHH#HH8888",
"     #8HH#HHH888",
"     #88H#HHH888",
"    #888H#HHHH88",
"    #888HH#HHH88",
"   #8888HH#HHHH8",
"   #888HHH#HHHH8",
"   #VVVVVVVVVVVV",
"    ############",
]
CM_E = [
"                                ",
"           ######               ",
"         ##888888##             ",
"        #888888888V#            ",
"       #88888888VVV#            ",
"       #8888888VYYY#            ",
"      #88888888VSSSS#           ",
"      #8888888VSS#SS#           ",
"      #8888888VSSSSSS#          ",
"      #8888888VsSSSS#           ",
"      #88888888VVsss#           ",
"     #888888VVVVVVV#            ",
"    #8888888VVVWVV#             ",
"    #888888H#VVVVV#             ",
"   #888888HH#VVVVW#             ",
"   #888888HH#WVVVVV#            ",
"   #88888HHH#WVVVVV#            ",
"   #88888HHH#WVVVVV#            ",
"   #8888HHHH#WWVVVV#            ",
"   #8888HHHH#WWVVVVV#           ",
"   #8888HHH#WWWVVVVV#           ",
"    #888HHH#WWWVVVVV#           ",
"    #888HHH#WWWWVVVV#           ",
"    #888HHH#WWWWVVVVV#          ",
"   #8888HHH#WWWWWVVVV#          ",
"   #8888HHH#WWWWWVVVVV#         ",
"   #888HHHH#WWWWWVVVVV#         ",
"   #VVVVVVVVVVVVVVVVVVV#        ",
"    ###################         ",
]
_CS, _CN = mirror_rows(CM_S_HALF), mirror_rows(CM_N_HALF)
def ice_staff(rows, x0, y0, x1, y1, glow=False):
    """a wooden staff from the fist to (x1, y1), topped with an ice crystal"""
    r = katana(rows, x0, y0, x1, y1, 0, "ttt")
    pts = [(x1, y1, "V"), (x1, y1 - 1, "8"), (x1, y1 - 2, "V"), (x1 - 1, y1 - 1, "8"), (x1 + 1, y1 - 1, "8"), (x1, y1 - 3, "8")]
    if glow:
        pts += [(x1 - 2, y1 - 1, "V"), (x1 + 2, y1 - 1, "V"), (x1, y1 - 4, "V"), (x1 - 2, y1 - 3, "8"), (x1 + 2, y1 - 3, "8"),
                (x1 - 2, y1 + 1, "8"), (x1 + 2, y1 + 1, "8")]
    r = pad_rows(r)
    own = {(a, b) for a, b, _ in pts}
    for a, b, _ in pts:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            X, Y = a + dx, b + dy
            if 0 <= X < 32 and 0 <= Y < 32 and (X, Y) not in own and r[Y][X] == " ":
                r[Y][X] = "#"
    for a, b, c in pts:
        if 0 <= a < 32 and 0 <= b < 32:
            r[b][a] = c
    return ["".join(q) for q in r]
CM_POSES = (
    ice_staff(_CS, 4, 26, 4, 5),                                          # the staff planted at her side
    ice_staff(_CN, 27, 26, 27, 5),
    ice_staff(limb(CM_E, [(10, 14), (13, 18), (16, 19)], ("8", "H"), (1, "S")), 18, 26, 18, 5),
    ice_staff(_CS, 4, 22, 7, 2, True),                                    # staff raised, the crystal flaring
    ice_staff(_CN, 27, 22, 24, 2, True),
    ice_staff(limb(CM_E, [(10, 14), (15, 14), (19, 13)], ("8", "H"), (1, "S")), 20, 18, 27, 7, True),
)


def cm_frame(d, f, sh=True):
    return ascii_frame(CM_POSES, CM_COLS, d, f, sh, 10)


# Drow Ranger: blue skin, white hair under a dark hood and cloak, a silver breastplate, a recurve bow
DROW_COLS = {"#": 1, "S": 8, "s": 3, "V": 5, "W": 4, "H": 3, "h": 2, "t": 7, "k": 14, "G": 10, "g": 9, "L": 11, "Y": 15}
DROW_S_HALF = [
"                ",
"                ",
"           #####",
"         ##hhhhh",
"        #hhHHHHH",
"       #hhHVVVVV",
"       #hHVSSSSS",
"      #hhVSS#SSS",
"      #hhVSS#SSS",
"      #hhVsSSSSS",
"      #hhVVsSSss",
"      #hhVVV##ss",
"     #hhHVVVV#ss",
"    #hhHH#VVV#hH",
"    #hHHH#VhWWVW",
"    #hHHH#hWVWWW",
"    #hHHH#hHWWWH",
"    #hHHh#hhHHHH",
"    #SS#h#hhkkYk",
"    #Ss#h#hgGGGG",
"     ##hh#hgGgGG",
"      #hh#hgGGGg",
"      #hh#hSSSSg",
"      #hH##SSss#",
"      #hH# #SSs#",
"      #hh# #SSs#",
"      #hh# #hhh#",
"       ##  #kkk#",
"            ### ",
]
DROW_N_HALF = [
"                ",
"                ",
"           #####",
"         ##hhhhh",
"        #hhHHHHH",
"       #hhHHHHHH",
"       #hHHHHHHH",
"      #hhHHHHHHh",
"      #hhHHHHHhh",
"      #hhHHHHhhV",
"      #hhHHHhhVV",
"      #hhHHVVVVW",
"     #hhHVVVVVVV",
"    #hhHH#VVVWVk",
"    #hHHH#hVWVkt",
"    #hHHH#hWVktk",
"    #hHHH#hhktkt",
"    #hHHh#hhkttt",
"    #SS#h#hhkkYk",
"    #Ss#h#hgGGGG",
"     ##hh#hgGgGG",
"      #hh#hgGGGg",
"      #hh#hSSSSg",
"      #hH##SSss#",
"      #hH# #SSs#",
"      #hh# #SSs#",
"      #hh# #hhh#",
"       ##  #kkk#",
"            ### ",
]
DROW_E = [
"                                ",
"                                ",
"           ######               ",
"         ##hhhhhh##             ",
"        #hhHHHHHHHh#            ",
"       #hhHHHHHVVVV#            ",
"       #hHHHHHVVSSSS#           ",
"      #hhHHHHVVSS#SS#           ",
"      #hhHHHHVVSSSSSS#          ",
"      #hhHHHHVVsSSSS#           ",
"      #hhHHHVVVVsss#            ",
"      #hhHHVVVVVV#              ",
"    #thhHHVVVVhWW#              ",
"   #tkhhHHHVVhWWW#              ",
"   #tkhhHHHHhWWWVW#             ",
"   #tkhhHHHHhWVWWW#             ",
"    #khhHHHHhHWWWH#             ",
"    #hhhHHHhhHHHH#              ",
"    #hhhHHHhhHHHH#              ",
"    #hhhHHhhkkYkk#              ",
"    #hhhHHhhgGGGG#              ",
"     #hhHHhhgGGGG#              ",
"     #hhHhhSSSgGG#              ",
"     #hhHhhSSSsgG#              ",
"     #hhHhSSs#SSs#              ",
"      #hhhSSs#SSs#              ",
"      #hhhhhh#hhhh#             ",
"       #kkkk# #kkkk#            ",
"        ####   ####             ",
]
_DS, _DN = mirror_rows(DROW_S_HALF), mirror_rows(DROW_N_HALF)
def drow_bow(rows, c, a0, a1, side=1, pull=0, arrow=False, horiz=False):
    """a recurve bow along the axis from a0 to a1 at cross position c (x for an upright bow, y for one
    held across), its limb bowing out to side; the string is drawn back by pull, an arrow nocked"""
    pts = []
    n = a1 - a0
    m = n // 2
    for i in range(n + 1):
        t = i / n
        pts.append((c + side * round(2.4 * (1 - (2 * t - 1) ** 2)), a0 + i, "t"))
        if 0 < i < n:
            k = round(pull * (1 - abs(i - m) / m))
            pts.append((c - side * k, a0 + i, "W"))
    if arrow:
        pts += [(c - side * pull + side * k, a0 + m, "W" if k < 7 else "V") for k in range(9)]
    if horiz:
        pts = [(q, p, ch) for p, q, ch in pts]
    r = pad_rows(rows)
    own = {(x, y) for x, y, _ in pts}
    for x, y, _ in pts:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            X, Y = x + dx, y + dy
            if 0 <= X < 32 and 0 <= Y < 32 and (X, Y) not in own and r[Y][X] == " ":
                r[Y][X] = "#"
    for x, y, ch in pts:
        if 0 <= x < 32 and 0 <= y < 32:
            r[y][x] = ch
    return ["".join(q) for q in r]
DROW_POSES = (
    drow_bow(_DS, 25, 11, 27),                                          # bow held at her side
    drow_bow(_DN, 6, 11, 27, -1),
    drow_bow(limb(DROW_E, [(10, 14), (13, 18), (16, 19)], ("h", "H"), (1, "S")), 18, 10, 27),
    drow_bow(_DS, 21, 8, 24, 1, 3, True, True),                         # held across, drawn, loosing at us
    drow_bow(_DN, 9, 8, 24, -1, 3, True, True),
    drow_bow(limb(DROW_E, [(10, 14), (15, 15), (19, 15)], ("h", "H"), (1, "S")), 22, 7, 23, 1, 4, True),
)


def drow_frame(d, f, sh=True):
    return ascii_frame(DROW_POSES, DROW_COLS, d, f, sh, 10)


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
    """a Dota-style guard tower in 3/4 view, 32x48: a stepped stone plinth, a block-built pillar with
    a team-coloured rune seam and buttresses, and a slab crown whose claws grip a glowing team orb"""
    b = bmp(32, 48)
    for y in range(48):                                    # cast shadow on the ground, down-right
        for x in range(32):
            dx, dy = (x + 0.5 - 20) / 12, (y + 0.5 - 42) / 5
            if dx * dx + dy * dy < 1 and (x + y) % 2 == 0:
                b[y][x] = 1
    def slab(x0, x1, ytop, depth, front, inset=2):         # a stone step: lit top face, front face
        for y in range(ytop, ytop + depth):
            k = (ytop + depth - 1 - y)
            rect(b, x0 + inset - min(inset, depth - 1 - k), y, x1 - inset + min(inset, depth - 1 - k), y, 4)
        rect(b, x0, ytop + depth, x1, ytop + depth + front - 1, 3)
        rect(b, x0, ytop + depth, x0 + 1, ytop + depth + front - 1, 4)
        rect(b, x1 - 2, ytop + depth, x1, ytop + depth + front - 1, 2)
        rect(b, x0, ytop + depth + front - 1, x1, ytop + depth + front - 1, 2)
        for x in range(x0 + 4, x1 - 2, 6):                 # block joints on the front
            rect(b, x, ytop + depth, x, ytop + depth + front - 2, 2)
        rect(b, x0 + inset, ytop, x1 - inset, ytop, 5)
    slab(2, 29, 34, 4, 5)                                  # bottom step
    slab(6, 25, 30, 3, 3)                                  # upper step
    for y in range(14, 32):                                # pillar
        w = 6 + (y - 14) / 9
        for x in range(round(16 - w), round(16 + w)):
            t = (x + 0.5 - (16 - w)) / (2 * w)
            c = 4 if t < 0.25 else (3 if t < 0.7 else 2)
            if (y - 14) % 6 == 5:
                c = 2 if t < 0.7 else 1                   # mortar between block courses
            elif abs(x + 0.5 - (16 - w / 2 if ((y - 14) // 6) % 2 else 16 + w / 2)) < 0.6:
                c = 2                                      # staggered joints
            b[y][x] = c
    for sx, c in ((-1, 3), (1, 2)):                        # buttresses
        for y in range(22, 32):
            k = (y - 22) // 3
            for x in range(16 + sx * 7, 16 + sx * (8 + k) + sx, sx):
                b[y][x] = c
        line(b, 16 + sx * 7, 22, 16 + sx * 11, 31, 4 if sx < 0 else 3)
    for y in range(16, 31):                                # glowing rune seam
        if (y - 14) % 6 != 5:
            b[y][15] = 10
            b[y][16] = 11 if y % 3 else 5
        else:
            b[y][15] = b[y][16] = 9
    slab(5, 26, 10, 2, 3)                                  # crown slab
    for sx in (-1, 1):                                     # claws curling up round the orb
        c, hi = (4, 5) if sx < 0 else (2, 3)
        line(b, 16 + sx * 9, 11, 16 + sx * 10, 5, c, 2)
        line(b, 16 + sx * 10, 5, 16 + sx * 8, 1, hi, 2)
        put(b, 16 + sx * 7, 0, hi)
    line(b, 16, 10, 16, 9, 2)
    for y in range(48):                                    # a faint glow round the orb
        for x in range(32):
            if not b[y][x] and 6.2 < math.hypot(x + 0.5 - 16, y + 0.5 - 6) < 7.4 and (x + y) % 2:
                b[y][x] = 10
    shade_sphere(b, 16, 6, 5.5, [9, 10, 11])               # the orb
    disc(b, 14.5, 4.5, 1.5, 5)
    put(b, 18, 8, 11)
    return add_outline(b)


def barracks():
    """a barracks, 24x24: a long stone hall on a plinth under a team-coloured roof, a door in front"""
    return add_outline([r[4:28] for r in _barracks32()[6:30]])


def _barracks32():
    b = bmp(32, 32)
    shadow(b, 18, 28, 14, 3)
    rect(b, 2, 22, 29, 27, 3)                              # plinth
    rect(b, 2, 22, 29, 22, 4)
    rect(b, 2, 27, 29, 27, 2)
    for y in range(12, 23):                                # walls, block courses
        for x in range(4, 28):
            c = 4 if x < 7 else (2 if x > 24 else 3)
            if (y - 12) % 4 == 3 or (x + (4 if (y - 12) // 4 % 2 else 0)) % 8 == 0:
                c = 2
            b[y][x] = c
    for y in range(3, 13):                                 # the roof, lit on the left
        k = 12 - y
        for x in range(3 + k // 2, 29 - k // 2):
            b[y][x] = 11 if x < 16 - k // 3 else (10 if x < 24 - k // 3 else 9)
    rect(b, 3, 12, 28, 12, 9)
    line(b, 9, 3, 22, 3, 5)
    rect(b, 13, 16, 18, 22, 1)                             # door
    rect(b, 14, 15, 17, 15, 1)
    for x in (8, 23):                                      # glowing windows
        rect(b, x, 15, x + 1, 17, 10)
        put(b, x, 15, 11)
    for x in (2, 29):                                      # banners
        line(b, x, 6, x, 21, 2)
        rect(b, x - 1 if x > 16 else x + 1, 7, x - 1 if x > 16 else x + 1, 12, 10)
    return b


def wolf_frame(d, f):
    """a grey jungle wolf, 24x24: d 0 = towards us, 1 = away, 2 = east; f 0/1 = the two strides.
    Shaggy grey fur lit from the top left, a dark stripe down the back, red eyes and white fangs"""
    b = bmp(24, 24)
    G = [2, 3, 4]
    if d == 2:
        shadow(b, 12, 21, 9, 2)
        for k, (x, ph) in enumerate(((6, 0), (8, 1), (15, 1), (17, 0))):   # legs: near pair darker
            off = 2 if (ph + f) % 2 else -1
            c = 2 if k in (0, 2) else 3
            line(b, x, 14, x + off, 20, c, 2)
            put(b, x + off + 1, 20, 2)
        path(b, [(5, 12), (2, 10), (1, 7), (2, 5)], 3, 2)                  # bushy tail, curled up
        put(b, 2, 4, 4); put(b, 1, 6, 4)
        shade_sphere(b, 11, 12, 0, G, 7.5, 4)                               # body
        shade_sphere(b, 7, 12, 0, G, 3.5, 3.5)                              # haunch
        for x in range(6, 17, 2):                                          # shaggy back
            put(b, x, 8, 4); put(b, x + 1, 8, 2)
        line(b, 6, 9, 15, 9, 2)
        shade_sphere(b, 17, 10, 0, G, 3.5, 4)                               # neck ruff
        shade_sphere(b, 19, 9, 0, G, 3, 2.6)                                # head
        rect(b, 20, 9, 23, 11, 3)                                          # muzzle
        line(b, 20, 11, 23, 11, 2)
        put(b, 23, 9, 1)                                                   # nose
        put(b, 22, 12, 5); put(b, 20, 12, 5)                               # fangs
        path(b, [(17, 7), (17, 4), (19, 6)], 4)                            # ear
        put(b, 18, 5, 2)
        put(b, 20, 8, 12)                                                  # eye
    elif d == 0:
        shadow(b, 12, 21, 8, 2)
        lift = (0, 2) if f else (2, 0)
        for k, x in enumerate((7, 15)):                                     # hind legs
            rect(b, x, 15, x + 1, 19, 2)
        for k, x in enumerate((9, 13)):                                     # forelegs
            rect(b, x, 15 - lift[k], x + 1, 20 - lift[k], 3)
            rect(b, x, 20 - lift[k], x + 1, 20 - lift[k], 2)
        shade_sphere(b, 12, 13, 0, G, 6, 4.5)                               # body seen head-on
        shade_sphere(b, 12, 11, 0, G, 5, 3.5)                               # ruff
        shade_sphere(b, 12, 8, 0, G, 4, 3.5)                                # head
        path(b, [(8, 7), (7, 2), (10, 5)], 3); put(b, 8, 4, 2)             # ears
        path(b, [(16, 7), (17, 2), (14, 5)], 3); put(b, 16, 4, 2)
        rect(b, 10, 10, 14, 12, 4)                                         # muzzle
        rect(b, 11, 10, 13, 10, 1)                                         # nose
        put(b, 10, 13, 5); put(b, 14, 13, 5)                               # fangs
        line(b, 11, 13, 13, 13, 13)
        put(b, 9, 8, 12); put(b, 15, 8, 12)                                # eyes
    else:
        shadow(b, 12, 21, 8, 2)
        lift = (0, 2) if f else (2, 0)
        for k, x in enumerate((8, 14)):
            rect(b, x, 15 - lift[k], x + 1, 20 - lift[k], 2)
        shade_sphere(b, 12, 13, 0, G, 5.5, 6)                               # back, seen from behind
        line(b, 12, 8, 12, 17, 2)                                          # dark stripe
        for y in range(9, 17, 2):
            put(b, 10, y, 4); put(b, 14, y, 4)
        path(b, [(12, 18), (13, 21), (12, 23)], 3, 2)                      # tail down
        shade_sphere(b, 12, 6, 0, G, 3.5, 3)                                # back of the head
        path(b, [(9, 5), (8, 1), (11, 3)], 3)
        path(b, [(15, 5), (16, 1), (13, 3)], 3)
    return add_outline(b)


def ogre_frame(d, f):
    """a hulking jungle ogre, 24x24, after the Dota ogre bruiser: a big blue-grey body, a small head
    sunk between huge shoulders, a red loincloth, tusks and a spiked wooden club; f 0/1 = strides"""
    b = bmp(24, 24)
    S = [2, 8, 4]                                                          # skin: dark, blue, light
    shadow(b, 12, 21, 9, 2)
    if d == 2:
        for k, x in enumerate((9, 14)):                                    # stumpy legs
            off = (2 if (k + f) % 2 else -2)
            rect(b, x + off, 16, x + off + 2, 20, 2 if k == 0 else 8)
            rect(b, x + off, 20, x + off + 3, 20, 2)
        shade_sphere(b, 11, 12, 0, S, 6, 5.5)                               # torso, hunched
        rect(b, 6, 16, 16, 17, 13)                                         # loincloth
        line(b, 6, 16, 16, 16, 12)
        shade_sphere(b, 15, 6, 0, S, 3.4, 3.2)                              # head thrust forward
        line(b, 15, 4, 18, 4, 2)                                           # brow
        put(b, 17, 5, 12)
        put(b, 18, 8, 5); put(b, 17, 9, 5)                                 # tusk
        line(b, 14, 12, 19, 10 if f else 13, 8, 2)                         # arm
        if f:                                                              # the club swung down
            line(b, 19, 10, 23, 15, 7, 2)
            disc(b, 22, 16, 2, 14); put(b, 23, 14, 6); put(b, 21, 18, 6)
        else:                                                              # or raised
            line(b, 19, 13, 22, 5, 7, 2)
            disc(b, 22, 5, 2.2, 14); put(b, 23, 3, 6); put(b, 21, 3, 6)
    else:
        lift = (0, 2) if f else (2, 0)
        for k, x in enumerate((8, 13)):                                    # stumpy legs
            rect(b, x, 17 - lift[k], x + 2, 20 - lift[k], 2)
            rect(b, x - 1, 20 - lift[k], x + 3, 20 - lift[k], 2)
        shade_sphere(b, 12, 12, 0, S, 6.5, 5.5)                             # the great torso
        rect(b, 7, 16, 16, 17, 13)                                         # loincloth
        line(b, 7, 16, 16, 16, 12)
        shade_sphere(b, 5, 9, 0, S, 2.2, 2.2)                               # shoulders
        shade_sphere(b, 19, 9, 0, S, 2.2, 2.2)
        line(b, 4, 11, 3, 16, 8, 2)                                        # left arm, fist
        disc(b, 3.5, 17, 1.6, 2)
        if d == 0:
            shade_sphere(b, 12, 6, 0, S, 3.6, 3.4)                          # the head, between the shoulders
            line(b, 10, 5, 14, 5, 2)                                       # heavy brow
            put(b, 10, 6, 12); put(b, 14, 6, 12)
            line(b, 11, 8, 13, 8, 1)                                       # mouth and tusks
            put(b, 10, 9, 5); put(b, 14, 9, 5); put(b, 10, 8, 5); put(b, 14, 8, 5)
            line(b, 10, 13, 14, 13, 2)                                     # belly crease
        else:
            shade_sphere(b, 12, 6, 0, S, 3.4, 3)
            line(b, 12, 9, 12, 15, 2)                                      # spine
        cy = 3 if not f else 9                                             # the club in the right hand
        line(b, 20, 11, 20, cy + 2, 7, 2)
        disc(b, 20.5, cy, 2.2, 14)
        put(b, 22, cy, 6); put(b, 20, cy - 2, 6); put(b, 18, cy, 6)
    return add_outline(b)


def camp_patch():
    """the neutral camp, 32x24, drawn under the creeps: a trampled dirt clearing ringed with stones,
    a smouldering fire in the middle, bones and a fallen log"""
    b = bmp(32, 24)
    for y in range(24):
        for x in range(32):
            d = ((x + 0.5 - 16) / 15.5) ** 2 + ((y + 0.5 - 12) / 10.5) ** 2
            if d <= 1 and (d < 0.78 or (x + y) % 2 == 0):
                b[y][x] = 14 if d > 0.6 or (x * 7 + y * 3) % 13 == 0 else 7
    for k in range(14):                                                    # the ring of stones
        a = k * 2 * math.pi / 14
        x, y = 16 + math.cos(a) * 13.5, 12 + math.sin(a) * 9
        disc(b, x, y, 1.3, 3)
        put(b, int(x) - 1, int(y) - 1, 4)
    line(b, 12, 15, 20, 11, 2, 2)                                          # the fire: crossed logs
    line(b, 12, 11, 20, 15, 1, 2)
    disc(b, 16, 12, 2.2, 12)
    disc(b, 16, 11.5, 1.2, 15)
    put(b, 16, 9, 15); put(b, 15, 8, 12)
    line(b, 5, 17, 9, 19, 6); put(b, 5, 16, 6); put(b, 9, 20, 6)         # a bone
    line(b, 22, 5, 27, 7, 13, 2)                                           # a log
    put(b, 27, 6, 6)
    return b


# ---------------------------------------------------------------- Roshan, runes, the Aegis
def path(b, pts, c, w=1):
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        line(b, x0, y0, x1, y1, c, w)


def roshan(f):
    """Roshan, 48x48, facing the camera, after the Dota 2 model: a huge hunched back of big grey
    scale plates with spikes on the ridge, purple-black bony wings hooked at the tips, a low dark
    head with yellow eyes and bone tusks, two massive banded mauve forearms with long dark claws,
    a spiked tail and a torn red cloth. f = 1: rearing up, right arm raised to strike, maw open."""
    b = bmp(48, 48)
    shadow(b, 24, 43, 21, 4)
    # wings: bony rods from the shoulders, hooked at the ends (dark maroon for the purple)
    for s in (-1, 1):
        X = lambda x: 24 + s * x
        path(b, [(X(8), 13), (X(13), 5), (X(19), 1), (X(23), 3)], 13, 2)
        path(b, [(X(23), 3), (X(23), 8), (X(21), 10)], 13, 1)
        path(b, [(X(14), 4), (X(16), 11)], 14, 1)
        path(b, [(X(19), 2), (X(20), 9)], 14, 1)
    # tail with green spines, out to the right behind the haunch
    path(b, [(34, 34), (40, 36), (44, 34), (46, 30)], 2, 2)
    for x, y in ((39, 35), (43, 33), (45, 30)):
        put(b, x, y - 1, 10)
        put(b, x, y - 2, 11)
    # hind feet
    for s in (-1, 1):
        ell(b, 24 + s * 11, 39, 4, 2.5, 2)
    # the hump of big plates
    for y in range(48):
        for x in range(48):
            if ((x + 0.5 - 24) / 16.0) ** 2 + ((y + 0.5 - 21) / 12.5) ** 2 > 1:
                continue
            best = []
            for j in range(-1, 9):
                for i in range(-1, 8):
                    cx = i * 8 + (4 if j % 2 else 0)
                    cy = j * 6 + 8
                    best.append(((x + 0.5 - cx) ** 2 + ((y + 0.5 - cy) * 1.2) ** 2, cx, cy))
            best.sort()
            d0, cx, cy = best[0]
            dark = y > 26 or abs(x - 24) > 13
            if best[1][0] - d0 < 7:
                c = 1 if dark else 2                      # the seams
            elif (x + 0.5 - cx) + (y + 0.5 - cy) < -2:
                c = 3 if dark else 4                      # each plate's lit upper-left
            else:
                c = 2 if dark else 3
            b[y][x] = c
    for x, y, h in ((14, 12, 3), (19, 10, 4), (24, 9, 4), (29, 10, 4), (34, 12, 3)):   # ridge spikes
        line(b, x, y, x, y - h, 4)
        put(b, x, y - h, 5)
    # torn red cloth over the right haunch
    path(b, [(37, 18), (39, 23), (38, 29)], 12, 2)
    put(b, 40, 24, 13)
    put(b, 38, 30, 13)
    # forearms: heavy, mauve, banded, with long dark claws
    def arm(sx, sy, wx, wy, up):
        n = 6
        for k in range(n + 1):                              # thick at the elbow, thinner to the wrist
            t = k / float(n)
            ell(b, sx + (wx - sx) * t, sy + (wy - sy) * t, 4.2 - t * 1.2, 3.2 - t * 0.6, 7)
        for k in range(n + 1):
            t = k / float(n)
            px, py = sx + (wx - sx) * t, sy + (wy - sy) * t
            put(b, round(px + (3 if sx > 24 else -3)), round(py), 14)    # shaded outer side
            if k in (2, 4):
                line(b, round(px - 2), round(py), round(px + 2), round(py), 14)   # plate bands
        hyy = wy + (-3 if up else 2)
        ell(b, wx, hyy, 5.5, 3, 7)
        line(b, wx - 4, hyy + (-1 if up else 1), wx + 4, hyy + (-1 if up else 1), 14)
        for k in (-4, -1, 2, 5):                            # claws
            d = -1 if wx < 24 else 1
            if up:
                path(b, [(wx + k - 1, hyy - 3), (wx + k - 1 + d, hyy - 6)], 2)
                put(b, wx + k - 1 + d, hyy - 7, 3)
            else:
                path(b, [(wx + k - 1, hyy + 3), (wx + k - 1 + d, hyy + 6)], 2)
                put(b, wx + k - 1 + d, hyy + 6, 3)
    arm(13, 26, 10, 37, False)
    if f:
        arm(35, 24, 41, 11, True)
    else:
        arm(35, 26, 38, 37, False)
    # head: low in front, under the shoulders
    hy = 31 if not f else 30
    ell(b, 24, hy + 1, 9, 7, 1)
    shade_sphere(b, 24, hy, 8, [2, 2, 3], 8.5, 6.5)
    line(b, 18, hy - 4, 30, hy - 4, 3)                      # brow ridge
    for s in (-1, 1):
        path(b, [(24 + s * 6, hy - 5), (24 + s * 9, hy - 9)], 14, 1)      # horn stubs
        rect(b, 24 + s * 4 - (1 if s < 0 else 0), hy - 2, 24 + s * 4 + (0 if s < 0 else 1), hy - 2, 15)   # yellow eyes
        put(b, 24 + s * 3, hy - 3, 1)
    if f:                                                   # maw open
        ell(b, 24, hy + 4, 5, 3, 13)
        ell(b, 24, hy + 4, 3.5, 1.6, 12)
        for x in (21, 23, 25, 27):
            put(b, x, hy + 2, 5)
    else:
        line(b, 19, hy + 3, 29, hy + 3, 1)
    for s in (-1, 1):                                       # bone tusks curling out and down
        path(b, [(24 + s * 4, hy + 2), (24 + s * 7, hy + 5), (24 + s * 8, hy + 8), (24 + s * 6, hy + 9)], 6)
        put(b, 24 + s * 6, hy + 10, 5)
    return add_outline(b)


RUNE_COLS = [(8, 5, 3), (12, 15, 13), (10, 11, 9), (15, 6, 7)]   # double damage, haste, regeneration, bounty


def rune(k, size=16):
    """a power rune: a glowing crystal diamond with a bright facet; the bounty rune a gold coin.
    size 8 gives the mark shown over a hero while the rune lasts."""
    b = bmp(size, size)
    mid, lit, dark = RUNE_COLS[k]
    c = size / 2.0
    r = size * 0.42
    if size == 16:
        for y in range(16):                               # faint glow ring
            for x in range(16):
                d = math.hypot(x + 0.5 - c, y + 0.5 - c)
                if 6.6 < d < 7.6 and (x + y) % 2:
                    b[y][x] = mid
    for y in range(size):
        for x in range(size):
            dx, dy = x + 0.5 - c, y + 0.5 - c
            if k == 3:
                inside = dx * dx + dy * dy <= (r * 0.95) ** 2
            else:
                inside = abs(dx) / 0.8 + abs(dy) <= r
            if inside:
                b[y][x] = lit if dx + dy < -size * 0.12 else (dark if dx + dy > size * 0.2 else mid)
    if k == 3:                                            # the coin's mark
        if size == 16:
            line(b, 8, 5, 8, 10, 7)
            line(b, 6, 6, 10, 6, 7)
            line(b, 6, 9, 10, 9, 7)
        put(b, int(c) - 2, int(c) - 2, 5)
    else:
        put(b, int(c) - 1, int(c) - (3 if size == 16 else 2), 5)
        if size == 16:
            put(b, 7, 5, 5)
            put(b, 6, 6, 5)
    return add_outline(b)


def aegis():
    """the Aegis of the Immortal over its holder: a small gold shield"""
    return add_outline(from_ascii(["........", ".5f6f6..", ".f6f6f..", ".6fef6..", ".f6f6f..", "..6f6...", "...f....", "........"], 8))


def stamp_pit(img, wx, wy):
    """Roshan's pit, 80x80 at world (wx, wy): a ring of dark stone blocks round a sunken slab floor"""
    for y in range(80):
        for x in range(80):
            d = math.hypot(x + 0.5 - 40, y + 0.5 - 40)
            if d >= 40:
                continue
            px, py = wx + x, wy + y
            if d >= 39:
                c = 1
            elif d >= 33:                                   # the wall: blocks lit from the top left
                a = math.atan2(y + 0.5 - 40, x + 0.5 - 40)
                blk = int((a + math.pi) / (2 * math.pi) * 28)
                edge = int(((a + math.pi) / (2 * math.pi) * 28 - blk) * 8) == 0
                c = 1 if edge or abs(d - 36) < 0.5 else (7 if (x + y) < 72 else 15)
            else:
                bx, by = px % 16, py % 16
                c = 15 if bx == 0 or by == 0 else (14 if (bx * 3 + by * 5) % 11 else 15)
                if d > 29 and (x + y) < 80:
                    c = 14 if (x + y) % 2 else 1                # the wall's shadow on the floor
            img[y][x] = c


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
                c = 1 if k < 0.35 else (13 if k < 0.7 else (12 if rnd.random() < 0.535 else 14))
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
        disc(b, x, y, 1.5 + f * 0.6, 3 if rnd.random() < 0.535 else 4)
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
    [("drop", 10, 11, 15), ("cloud", 9, 10, 11, 5, 2), ("heart", 9, 10, 15, 5, 2), ("claw", 10, 11, 15, 5, 1)],  # Viper
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
forest = [[1 if rnd.random() < 0.535 else 0 for _ in range(N)] for _ in range(N)]
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


TOWERS_RAD = [(104, 336), (104, 640), (432, 592), (296, 728), (688, 920), (384, 920)]
ANCIENT_RAD = (176, 848)
FOUNTAIN_RAD = (64, 960)
ROSH_PIT = (288, 288)
RAX_RAD = [(140, 720), (264, 808), (300, 884)]          # barracks behind the T2s: top, mid, bot
CAMPS_RAD = [(232, 552), (536, 776)]                     # neutral camps in the Radiant jungle
# jungle trails (pixels): from each camp out to the lanes and the river, so heroes can walk the woods
TRAILS_RAD = [[(104, 552), (232, 552), (344, 440)], [(232, 552), (300, 660)],
              [(536, 920), (536, 776), (640, 680)], [(536, 776), (420, 720)]]


def rot(p):
    return (1024 - p[0], 1024 - p[1])


BUILDINGS = TOWERS_RAD + [ANCIENT_RAD] + RAX_RAD + [rot(p) for p in TOWERS_RAD + [ANCIENT_RAD] + RAX_RAD]
CAMPS = CAMPS_RAD + [rot(p) for p in CAMPS_RAD]
TRAILS = TRAILS_RAD + [[rot(p) for p in t] for t in TRAILS_RAD]


def jungle_open(x, y):
    """cells kept clear for the neutral camps and the trails between them"""
    px, py = x * 16 + 8, y * 16 + 8
    if any(math.hypot(px - cx, py - cy) < 44 for cx, cy in CAMPS):
        return True
    return any(dseg(px, py, *a, *b_) < 20 for t in TRAILS for a, b_ in zip(t, t[1:]))

clear = [[0] * N for _ in range(N)]     # cells that must stay open (lanes, river, bases, buildings)
for y in range(N):
    for x in range(N):
        ld = lane_dist(x, y)
        rd = dseg(x, y, *RIVER[0], *RIVER[1])
        in_base = (x <= 15 and y >= 48) or (x >= 48 and y <= 15)
        t = forest[y][x]
        if ld < 2.8 or rd < 2.6 or in_base or jungle_open(x, y):
            t = 0
        for bx, by in BUILDINGS:
            if math.hypot(x + 0.5 - bx / 16, y + 0.5 - by / 16) < 3.5:
                t = 0
        if not t:
            clear[y][x] = forest[y][x]
            if ld < 2.8 or rd < 2.6 or in_base or jungle_open(x, y):
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
TEX_ASH = [periodic_tex(3, 5, [2, 14, 2], 22, True), periodic_tex(4, 5, [2, 2, 14], 18, True)]   # the Dire: darker grass
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


DARKEN = {2: 5, 5: 14, 3: 2, 4: 2, 6: 2, 8: 1, 9: 8, 10: 9, 14: 1, 15: 14, 7: 14, 12: 11, 13: 12, 11: 1}

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
            img[y][x] = c


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
_tw = tower()
define("T_TOWER", add_sprite(_tw[:32]))          # crown and pillar, 32x32
define("T_TOWER_B", add_sprite(_tw[32:]))        # plinth, 32x16
an = ancient()
define("T_ANCIENT", add_sprite([r[0:24] for r in an[0:24]]))
add_sprite([r[24:48] for r in an[0:24]])
add_sprite([r[0:24] for r in an[24:48]])
add_sprite([r[24:48] for r in an[24:48]])
for f in range(2):                               # Roshan: stand, slam; 48x48 as four 24x24 sprites
    rb = roshan(f)
    first = add_sprite([r[0:24] for r in rb[0:24]])
    if f == 0:
        define("T_ROSH", first)
    add_sprite([r[24:48] for r in rb[0:24]])
    add_sprite([r[0:24] for r in rb[24:48]])
    add_sprite([r[24:48] for r in rb[24:48]])
define("T_RAX", add_sprite(barracks()))
define("ROSH_X", ROSH_PIT[0])
define("ROSH_Y", ROSH_PIT[1])
define("T_RUNE", add_sprite(rune(0)))           # 16x16: double damage, haste, regeneration, bounty
for k in range(1, 4):
    add_sprite(rune(k))
define("T_RUNEM", add_sprite(rune(0, 8)))       # 8x8 marks over a hero
for k in range(1, 3):
    add_sprite(rune(k, 8))
define("T_AEGIS", add_sprite(aegis()))
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
define("T_ORB_POISON", add_sprite(orb(9, 11, 10, 2.6)))
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
HERO_FNS = [sf_frame, pudge_frame, axe_frame, sniper_frame, zeus_frame, lina_frame, cm_frame, drow_frame, viper_frame, jugg_frame]
PORT_ORG = {pudge_frame: (4, 2), sf_frame: (4, 2), viper_frame: (4, 7)}   # where each 24x24 HUD portrait is cut


def scale2x(b):
    """EPX: doubles pixel art keeping its edges sharp"""
    h, w = len(b), len(b[0])
    o = bmp(2 * w, 2 * h)
    for y in range(h):
        for x in range(w):
            p = b[y][x]
            a = b[y - 1][x] if y else p
            c = b[y][x - 1] if x else p
            r = b[y][x + 1] if x < w - 1 else p
            d = b[y + 1][x] if y < h - 1 else p
            o[2 * y][2 * x] = c if c == a and c != d and a != r else p
            o[2 * y][2 * x + 1] = a if a == r and a != c and r != d else p
            o[2 * y + 1][2 * x] = c if d == c and d != r and c != a else p
            o[2 * y + 1][2 * x + 1] = r if r == d and r != a and d != c else p
    return o


def strip_outline(b, c=1):
    """drops the outline (and dithered shadow) pixels that touch the empty background"""
    h, w = len(b), len(b[0])
    o = [r[:] for r in b]
    for y in range(h):
        for x in range(w):
            if b[y][x] == c and any(not (0 <= x + dx < w and 0 <= y + dy < h) or b[y + dy][x + dx] == 0
                                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                o[y][x] = 0
    return o


def rotate45(b, cw, cx=16, cy=15):
    """RotSprite-style: scale up 8x with EPX, then sample the centre of every pixel turned 45 degrees"""
    u = scale2x(scale2x(scale2x(b)))
    t = 0.70710678 * (-1 if cw else 1)
    o = bmp(32, 32)
    for y in range(32):
        for x in range(32):
            px, py = x + 0.5 - cx, y + 0.5 - cy
            sx, sy = cx + 0.70710678 * px - t * py, cy + t * px + 0.70710678 * py
            if 0 <= sx < 32 and 0 <= sy < 32:
                o[y][x] = u[int(sy * 8)][int(sx * 8)]
    return o


def half_turn(b, k=0.7, shift=2, c=16):
    """a front or back pose turned halfway to the east: the screen-left (far) side squeezes to the
    middle and the middle moves right"""
    u = scale2x(scale2x(b))
    o = bmp(32, 32)
    for y in range(32):
        for x in range(32):
            X = x + 0.5
            sx = c + (X - c - shift) / k if X < c + shift else X - shift
            if 0 <= sx < 32:
                o[y][x] = u[y * 4 + 1][int(sx * 4)]
    return o


TOP_DOWN = {viper_frame}   # seen straight from above: its diagonals are the pose turned 45 degrees


def hero32(fn, d, f):
    """a hero pose on its 32x32 sprite; d 3/4 are the diagonals south-east and north-east, made from
    the south and north poses"""
    if d < 3:
        return fn(d, f)
    if fn in TOP_DOWN:
        b = rotate45(fn(d - 3, f, sh=False, span=0.82), d == 4)
    else:
        b = half_turn(strip_outline(fn(d - 3, f)))
    b = add_outline(b)
    o = bmp(32, 32)
    shadow(o, 16, 28, 9, 3)
    for y in range(32):
        for x in range(32):
            if b[y][x]:
                o[y][x] = b[y][x]
    return o


hero_tiles, hero_port = [], []
for fn in HERO_FNS:
    for d in range(5):
        for f in range(3):
            b = hero32(fn, d, f)
            for tx in range(4):
                for ty in range(4):
                    hero_tiles.append(tile_at(b, tx, ty))
    px, py = PORT_ORG.get(fn, (4, 1))
    b = hero32(fn, 0, 0)
    b = [r[px:px + 24] for r in b[py:py + 24]]
    for tx in range(3):
        for ty in range(3):
            hero_port.append(tile_at(b, tx, ty))

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
# Roshan's pit, on the river between the top lane and mid (the same way from both fountains)
x0, y0 = ROSH_PIT[0] - 40, ROSH_PIT[1] - 40
img = bmp(80, 80)
for ty in range(10):
    for tx in range(10):
        t = tiles[map_ground[((y0 >> 3) + ty) * 128 + (x0 >> 3) + tx] - 1]
        for r in range(8):
            for c in range(8):
                img[ty * 8 + r][tx * 8 + c] = (t[r] >> (28 - c * 4)) & 15
stamp_pit(img, x0, y0)
for ty in range(10):
    for tx in range(10):
        t = tile_at(img, tx, ty)
        if t not in dedupe:
            tiles.append(t)
            dedupe[t] = len(tiles)
        map_ground[((y0 >> 3) + ty) * 128 + (x0 >> 3) + tx] = dedupe[t]
assert len(tiles) < 1280, len(tiles)
# match-only sprites go after the hero pose slots and the HUD art (6 * 16 + 50), loaded at the match start
match_tiles = []


def add_match(b):
    start = len(match_tiles)
    for tx in range(len(b[0]) // 8):
        for ty in range(len(b) // 8):
            match_tiles.append(tile_at(b, tx, ty))
    return start


for name, fn in (("NA_WOLF", wolf_frame), ("NA_OGRE", ogre_frame)):   # dir * 18 + stride * 9
    define(name, add_match(fn(0, 0)))
    for d, f in ((0, 1), (1, 0), (1, 1), (2, 0), (2, 1)):
        add_match(fn(d, f))
define("NA_CAMP", add_match(camp_patch()))
define("MATCH_TILES", len(match_tiles))
assert len(tiles) + 1 + 6 * 16 + 50 + len(match_tiles) <= 1280, ("match art overflows into plane A", len(match_tiles))
assert len(tiles) + 1 + 9 * 32 <= 1280, ("draft hero frames overflow into plane A", len(tiles))

walk = [0 if cells[y][x] == TREE else 1 for y in range(N) for x in range(N)]
for k, (bx, by) in enumerate(BUILDINGS):      # 2 + k: open, but next to tower k, which the game makes solid
    if k % 10 != 6:
        for y in range(N):
            for x in range(N):
                nx, ny = min(max(bx, x * 16), x * 16 + 15), min(max(by, y * 16), y * 16 + 15)
                if math.hypot(nx - bx, ny - by) < 14 and walk[y * N + x]:
                    walk[y * N + x] = 2 + k


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
out.append(carr("hero_port", "u32", [v for t in hero_port for v in t], 8, "0x{:08X}"))
out.append(carr("skill_icons", "u32", [v for t in skill_icon_tiles for v in t], 8, "0x{:08X}"))
out.append(carr("match_art", "u32", [v for t in match_tiles for v in t], 8, "0x{:08X}"))
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
        bm = an if k % 10 == 6 else (barracks() if k % 10 > 6 else tower())
        h, w = len(bm), len(bm[0])
        oy = h // 2 if k % 10 == 6 else (18 if k % 10 > 6 else 40)
        for y in range(h):
            for x in range(w):
                if bm[y][x]:
                    full[by - oy + y][bx - w // 2 + x] = 15
    save("map", full, PAL_MAP)
    sheet = bmp(9 * 24, 5 * 24 + 16)
    for i in range(6):
        for y, row in enumerate(melee_frame(i // 2, i % 2)):
            sheet[48 + y][i * 16:i * 16 + 16] = row
        for y, row in enumerate(ranged_frame(i // 2, i % 2)):
            sheet[64 + y][i * 16:i * 16 + 16] = row
    for y, row in enumerate(tower()[:48]):
        if 48 + y < len(sheet):
            sheet[48 + y][100:132] = row
    for y, row in enumerate(an):
        sheet[48 + y][140:188] = row
    save("units_rad", sheet, PAL_RAD, 4)
    save("units_dire", sheet, PAL_DIRE, 4)
    heroes = bmp(15 * 32, len(HERO_FNS) * 32)
    for h, fn in enumerate(HERO_FNS):
        for i in range(15):
            for y, row in enumerate(hero32(fn, i // 3, i % 3)):
                heroes[h * 32 + y][i * 32:i * 32 + 32] = row
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
