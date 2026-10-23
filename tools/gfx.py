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


# ---- shared 32x32 body
def robe_fill(b, y0, y1, w0, w1, shades, cx=16, trim=None):
    """a robe from the shoulders (half width w0 at y0) to the hem (w1 at y1), lit from the left"""
    for y in range(y0, y1 + 1):
        w = w0 + (w1 - w0) * (y - y0) / max(1, y1 - y0)
        for x in range(round(cx - w), round(cx + w)):
            t = (x + 0.5 - (cx - w)) / (2 * w)
            b[y][x] = shades[2] if t < 0.3 else (shades[1] if t < 0.78 else shades[0])
    if trim is not None:
        w = w1
        for x in range(round(cx - w), round(cx + w)):
            b[y1][x] = trim


def legs32(b, d, f, col, boot, y0=22, y1=27):
    if d == 2:
        for x, k in ((13, -1), (17, 1)):                 # back leg, front leg; the step swaps them
            off = [0, -k * 2, k][f] if f != 1 else -k * 2
            off = [k, -k, k * 2][f]
            rect(b, x + off, y0, x + off + 2, y1 - 1, col)
            rect(b, x + off, y1 - 1, x + off + 3, y1, boot)
    else:
        lift = [(0, 0), (2, 0), (0, 0)][f]
        for k, x in enumerate((12, 17)):
            rect(b, x, y0 - lift[k], x + 2, y1 - 1 - lift[k], col)
            rect(b, x, y1 - 1 - lift[k], x + 2, y1 - lift[k], boot)


def arms32(b, d, f, col, hand, sy=15, wide=6):
    sw = 1 if f == 1 else 0
    if d == 2:
        line(b, 16, sy, 17 + sw, sy + 6, col, 2)
        disc(b, 18 + sw, sy + 7.5, 1.4, hand)
    else:
        line(b, 16 - wide, sy, 15 - wide, sy + 6 - sw, col, 2)
        line(b, 15 + wide, sy, 16 + wide, sy + 6 - (1 - sw), col, 2)
        disc(b, 16 - wide, sy + 7.5 - sw, 1.4, hand)
        disc(b, 17 + wide, sy + 6.5 + sw, 1.4, hand)


def head32(b, d, hx, hy, skin, r=5.2, eyes=1):
    shade_sphere(b, hx, hy, r, skin)
    if d == 0:
        put(b, hx - 2, hy + 1, eyes)
        put(b, hx + 1, hy + 1, eyes)
    elif d == 2:
        put(b, hx + 2, hy + 1, eyes)


def finish(b, d, f, rx=9):
    b = add_outline(b)
    o = bmp(32, 32)
    shadow(o, 16, 28, rx, 3)
    for y in range(32):
        for x in range(32):
            if b[y][x]:
                o[y][x] = b[y][x]
    return o


def crescent(b, cx, cy, rx, ry, horiz=False, flip=False):
    """an axe blade: a grey half-moon out from the haft at (cx, cy), its cutting edge lit"""
    for y in range(32):
        for x in range(32):
            u, v = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
            if horiz:
                u, v = v, u
            if flip:
                u = -u
            if u >= 0 and u * u + v * v <= 1 and not (u < 0.35 and abs(v) > 0.45):
                b[y][x] = 5 if u * u + v * v > 0.55 else (4 if v < 0.2 else 3)


# ---- Axe (palette line 3: red skin)
AXE_SKIN = [14, 10, 12]
def axe32(d, f):
    b = bmp(32, 32)
    hx = 17 if d == 2 else 16
    if d == 1 and f != 2:                                # axe on his back seen from behind
        line(b, 8, 26, 24, 4, 7)
        crescent(b, 23, 6, 4.5, 5, horiz=True, flip=True)
    legs32(b, d, f, 2, 13)
    shade_sphere(b, 16, 17, 0, AXE_SKIN, rx=7.5 if d != 2 else 5.5, ry=5.5)   # bare red torso
    if d != 1:
        line(b, 10, 13, 21, 21, 13, 2)                   # leather strap across the chest
    else:
        line(b, 22, 13, 11, 21, 13, 2)
    rect(b, 9, 21, 23, 22, 13)                           # belt with a gold buckle
    put(b, 16, 21, 15)
    put(b, 16, 22, 15)
    if d != 2:
        shade_sphere(b, 8.5, 13.5, 3, [2, 3, 4])         # pauldrons
        shade_sphere(b, 23.5, 13.5, 3, [2, 3, 4])
    else:
        shade_sphere(b, 16, 13.5, 3, [2, 3, 4])
    if f != 2:
        arms32(b, d, f, 10, 10, sy=15, wide=8)
    head32(b, d, hx, 8, AXE_SKIN, r=4.6)
    rect(b, hx - 3, 3, hx + 3, 4, 1)                     # black hair, topknot
    rect(b, hx - 1, 0, hx + 1, 3, 1)
    if d != 1:
        rect(b, hx - 2 + (1 if d == 2 else 0), 11, hx + 2, 13, 1)    # beard
        put(b, hx + (1 if d == 2 else 0), 14, 1)
        if d == 0:
            put(b, hx - 2, 9, 15)
            put(b, hx + 1, 9, 15)
        else:
            put(b, hx + 2, 9, 15)
    else:
        rect(b, hx - 3, 4, hx + 3, 9, 1)
    blade = [2, 3, 4, 5]
    if f == 2:                                           # the chop
        if d == 0:
            line(b, 22, 15, 20, 29, 7, 2)
            crescent(b, 20, 25, 5, 5.5, horiz=True)
            line(b, 23, 15, 21, 19, 10, 2)
        elif d == 1:
            line(b, 22, 15, 21, 2, 7, 2)
            crescent(b, 21, 6, 5, 5.5, horiz=True, flip=True)
            line(b, 23, 15, 22, 11, 10, 2)
        else:
            line(b, 17, 15, 30, 13, 7, 2)
            crescent(b, 26, 13, 5, 5.5)
            line(b, 16, 15, 21, 15, 10, 2)
    elif d != 1:
        x = 26 if d == 0 else 24
        line(b, x, 5 - (f & 1), x, 27 - (f & 1), 7)      # haft held upright
        crescent(b, x + 1, 6.5 - (f & 1), 4.5, 5.5)      # double blade
        crescent(b, x, 6.5 - (f & 1), 4.5, 5.5, flip=True)
    return finish(b, d, f, 10)


# ---- Sniper (keen: short, big helmet, long rifle)
SN_SKIN = [7, 6, 6]
def sniper32(d, f):
    b = bmp(32, 32)
    hx = 17 if d == 2 else 16
    if f == 2:
        gun = {0: ((16, 18), (16, 31)), 1: ((16, 15), (16, 1)), 2: ((17, 18), (31, 18))}[d]
    else:
        gun = ((7, 26), (26, 7)) if d != 1 else ((6, 8), (25, 26))
    if d == 1:
        line(b, *gun[0], *gun[1], 2, 2)
    legs32(b, d, f, 7, 14, y0=23)
    shade_sphere(b, 16, 19.5, 0, [9, 10, 11], rx=6 if d != 2 else 4.5, ry=4.5)   # green coat
    rect(b, 10, 21, 22, 22, 14)
    put(b, 15, 21, 15)
    if d != 1:
        arms32(b, d, f, 10, 6, sy=17, wide=6)
        line(b, *gun[0], *gun[1], 2, 2)                  # rifle: dark barrel, wooden stock
        line(b, gun[0][0], gun[0][1], (gun[0][0] * 2 + gun[1][0]) // 3, (gun[0][1] * 2 + gun[1][1]) // 3, 7, 2)
        put(b, *gun[1], 15 if f == 2 else 4)
        if f == 2:
            put(b, gun[1][0] + (1 if d == 2 else 0), gun[1][1] + (1 if d == 0 else 0), 5)
    else:
        arms32(b, d, f, 10, 6, sy=17, wide=6)
    head32(b, d, hx, 11, SN_SKIN, r=5)
    # brass helmet with goggles
    for y in range(3, 10):
        for x in range(hx - 6, hx + 7):
            if ((x + 0.5 - hx) / 6.2) ** 2 + ((y + 0.5 - 9) / 5.6) ** 2 <= 1:
                b[y][x] = 15 if (x - hx) < -1 and y < 7 else 7
    rect(b, hx - 6, 9, hx + 6, 9, 14)                    # brim
    if d == 0:
        rect(b, hx - 4, 6, hx + 3, 7, 2)
        disc(b, hx - 2, 6.5, 1.3, 8)
        disc(b, hx + 2, 6.5, 1.3, 8)
        rect(b, hx - 4, 13, hx + 4, 16, 15)               # bushy beard
        put(b, hx, 17, 15)
        rect(b, hx - 2, 13, hx + 2, 13, 7)
    elif d == 2:
        disc(b, hx + 3, 6.5, 1.3, 8)
        rect(b, hx, 13, hx + 4, 16, 15)
    return finish(b, d, f, 8)


# ---- Zeus (white robe, white beard, lightning)
ZEUS_SKIN = [7, 6, 6]
def zeus32(d, f):
    b = bmp(32, 32)
    hx = 17 if d == 2 else 16
    robe_fill(b, 14, 27, 5, 8, [3, 4, 5], trim=8)
    rect(b, 11, 19, 21, 19, 8)                           # blue sash
    if d == 2:
        for y in range(14, 28):
            for x in range(8, 11):
                b[y][x] = 0
    if f != 2:
        arms32(b, d, f, 4, 7, sy=15, wide=6)
        if d != 1:
            put(b, 9 + (f & 1), 23, 8)                   # sparks in his hands
            put(b, 24, 22, 15)
    head32(b, d, hx, 9, ZEUS_SKIN, r=5)
    for y in range(2, 9):                                # white hair, combed back
        for x in range(hx - 6, hx + 7):
            if ((x + 0.5 - hx) / 6) ** 2 + ((y + 0.5 - 8) / 5.5) ** 2 <= 1 and (d == 1 or y < 7 or abs(x - hx) > 4):
                b[y][x] = 5 if x - hx < 1 else 4
    if d == 1:
        rect(b, hx - 5, 7, hx + 5, 15, 4)
        rect(b, hx - 4, 7, hx + 3, 14, 5)
    else:
        bx = 1 if d == 2 else 0
        rect(b, hx - 3 + bx, 11, hx + 3, 16, 5)          # long beard
        rect(b, hx - 2 + bx, 17, hx + 2, 18, 4)
        put(b, hx + bx, 19, 4)
        for x in ((hx - 2, hx + 1) if d == 0 else (hx + 2,)):    # eyes under bushy white brows
            put(b, x, 10, 1)
            put(b, x, 9, 4)
            put(b, x + 1 if x > hx else x - 1, 9, 4)
    if f == 2:                                           # arm thrown out with a bolt
        if d == 0:
            line(b, 21, 15, 23, 21, 4, 2)
            for p in ((23, 23), (22, 24), (24, 25), (23, 26), (25, 27), (24, 28), (26, 29)):
                put(b, *p, 15)
            put(b, 24, 22, 5)
        elif d == 1:
            line(b, 21, 15, 23, 8, 4, 2)
            for p in ((23, 6), (22, 5), (24, 4), (23, 3), (25, 2), (24, 1)):
                put(b, *p, 15)
        else:
            line(b, 17, 15, 23, 13, 4, 2)
            for p in ((25, 13), (26, 12), (27, 14), (28, 13), (29, 15), (30, 14), (31, 16)):
                put(b, *p, 15)
            put(b, 24, 13, 5)
    return finish(b, d, f, 9)


# ---- Lina (palette line 3: flame hair, red dress)
LINA_SKIN = [7, 6, 6]
def lina32(d, f):
    b = bmp(32, 32)
    hx = 17 if d == 2 else 16
    robe_fill(b, 14, 27, 4, 7.5, [9, 10, 11], trim=15)
    if f != 2:
        arms32(b, d, f, 6, 6, sy=15, wide=5)
        if d != 1:
            put(b, 10, 21 - (f & 1), 15)                 # embers in her hands
            put(b, 22, 20 + (f & 1), 11)
    head32(b, d, hx, 9, LINA_SKIN, r=4.8)
    # hair: swept up and back into flame tongues
    flick = f & 1
    for k, x in enumerate(range(hx - 5, hx + 6)):
        top = 1 + ((k * 3 + flick) % 4)
        for y in range(top, 7 if d != 1 else 12):
            b[y][x] = 15 if y < top + 1 else (11 if y < top + 3 else 10)
    rect(b, hx - 6, 6, hx - 5, 13, 10)
    rect(b, hx + 5, 6, hx + 6, 13, 10)
    if d == 1:
        rect(b, hx - 5, 6, hx + 5, 14, 10)
        rect(b, hx - 3, 8, hx + 3, 13, 11)
    if f == 2:                                           # a fireball thrown forward
        if d == 0:
            line(b, 11, 15, 14, 21, 6, 2)
            line(b, 21, 15, 18, 21, 6, 2)
            shade_sphere(b, 16, 25, 3.2, [10, 11, 15, 5])
        elif d == 1:
            line(b, 11, 15, 13, 9, 6, 2)
            line(b, 21, 15, 19, 9, 6, 2)
            shade_sphere(b, 16, 4, 3.2, [10, 11, 15, 5])
        else:
            line(b, 17, 15, 23, 15, 6, 2)
            shade_sphere(b, 27, 15, 3.2, [10, 11, 15, 5])
    return finish(b, d, f, 8)


# ---- Crystal Maiden (blue hooded cloak, staff)
CM_SKIN = [7, 6, 5]
CM_CLOAK = [3, 8, 5]
def cm32(d, f):
    b = bmp(32, 32)
    hx = 17 if d == 2 else 16
    sx = 25 if d == 0 else (22 if d == 2 else 7)
    if d == 1 and f != 2:
        line(b, sx, 4, sx, 27, 7)
    robe_fill(b, 13, 27, 5.5, 9, CM_CLOAK, trim=5)
    if d != 1:
        robe_fill(b, 15, 27, 2, 3.5, [4, 5, 5])          # white dress between the cloak flaps
    if f != 2:
        arms32(b, d, f, 8, 6, sy=15, wide=6)
    if d != 1 and f != 2:
        line(b, sx, 4 - (f & 1), sx, 27 - (f & 1), 7)    # staff
        shade_sphere(b, sx, 3.5 - (f & 1), 2.3, [8, 5, 5])
    shade_sphere(b, hx, 9, 6, CM_CLOAK)                  # hood
    if d != 1:
        ox = 1 if d == 2 else 0
        shade_sphere(b, hx + ox, 10, 3.6, CM_SKIN, rx=3.4, ry=3.8)   # face in the hood
        rect(b, hx - 3 + ox, 7, hx + 3 + ox, 7, 5)       # white fringe
        if d == 0:
            put(b, hx - 2, 10, 1)
            put(b, hx + 1, 10, 1)
        else:
            put(b, hx + 2, 10, 1)
    else:
        rect(b, hx - 1, 4, hx + 1, 14, 3)
    if f == 2:                                           # staff thrust forward in a burst of frost
        if d == 0:
            line(b, 21, 15, 20, 28, 7)
            line(b, 21, 15, 21, 20, 8, 2)
            pts = (20, 29)
        elif d == 1:
            line(b, 21, 15, 21, 2, 7)
            line(b, 21, 15, 22, 10, 8, 2)
            pts = (21, 2)
        else:
            line(b, 16, 15, 29, 11, 7)
            line(b, 16, 15, 21, 15, 8, 2)
            pts = (29, 11)
        x, y = pts
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1), (-2, -2), (2, 2), (2, -2), (-2, 2)):
            put(b, x + dx, y + dy, 5 if dx == dy == 0 else 8)
    return finish(b, d, f, 9)


# ---- Drow Ranger (pale blue skin, white hair, dark hood, bow)
DROW_SKIN = [3, 8, 5]
def drow32(d, f):
    b = bmp(32, 32)
    hx = 17 if d == 2 else 16
    if d != 2:
        robe_fill(b, 13, 25, 5, 8, [2, 2, 3])            # dark cloak behind
    legs32(b, d, f, 2, 1)
    shade_sphere(b, 16, 18, 0, [9, 10, 10], rx=5.5 if d != 2 else 4, ry=5)   # green leather tunic
    rect(b, 11, 21, 21, 21, 14)
    if d == 1:
        rect(b, 19, 11, 21, 20, 14)                      # quiver
        for x in (19, 21):
            put(b, x, 10, 5)
        robe_fill(b, 13, 25, 4, 7, [2, 2, 3])
    if f != 2:
        arms32(b, d, f, 3, 8, sy=15, wide=6)
        if d != 1:
            bx = 24 if d == 0 else 21                    # bow held at the side
            line(b, bx, 9, bx + 2, 14, 7)
            line(b, bx + 2, 14, bx + 2, 20, 7)
            line(b, bx + 2, 20, bx, 25, 7)
            line(b, bx, 9, bx, 25, 4)
    head32(b, d, hx, 9, DROW_SKIN, r=4.6)
    shade_sphere(b, hx, 7.5, 5.8, [2, 2, 3], rx=6, ry=5)   # dark hood
    if d != 1:
        ox = 1 if d == 2 else 0
        shade_sphere(b, hx + ox, 10, 3.3, DROW_SKIN, rx=3.2, ry=3.4)
        rect(b, hx - 4 + ox, 8, hx - 3 + ox, 15, 5)       # white hair falling out of the hood
        rect(b, hx + 3 + ox, 8, hx + 4 + ox, 15, 4)
        if d == 0:
            put(b, hx - 2, 10, 1)
            put(b, hx + 1, 10, 1)
        else:
            put(b, hx + 2, 10, 1)
    else:
        rect(b, hx - 3, 10, hx + 3, 17, 5)
        rect(b, hx + 1, 10, hx + 3, 17, 4)
    if f == 2:                                           # bow drawn, arrow nocked
        if d == 0:
            line(b, 10, 23, 16, 26, 7)
            line(b, 16, 26, 22, 23, 7)
            line(b, 10, 23, 22, 23, 4)
            line(b, 16, 17, 16, 29, 5)
            put(b, 16, 30, 3)
            line(b, 11, 15, 15, 21, 3, 2)
            line(b, 21, 15, 17, 21, 3, 2)
        elif d == 1:
            line(b, 10, 8, 16, 5, 7)
            line(b, 16, 5, 22, 8, 7)
            line(b, 10, 8, 22, 8, 4)
            line(b, 16, 14, 16, 3, 5)
        else:
            line(b, 25, 8, 27, 14, 7)
            line(b, 27, 14, 27, 18, 7)
            line(b, 27, 18, 25, 24, 7)
            line(b, 25, 8, 25, 24, 4)
            line(b, 18, 16, 30, 16, 5)
            line(b, 17, 15, 25, 16, 3, 2)
    return finish(b, d, f, 8)


# ---- Juggernaut (tiki mask, red crest, bare chest, katana)
JUGG_SKIN = [7, 6, 6]
def jugg32(d, f):
    b = bmp(32, 32)
    hx = 17 if d == 2 else 16
    legs32(b, d, f, 3, 1)
    rect(b, 11, 21, 21, 23, 4)                           # baggy grey trousers top
    shade_sphere(b, 16, 17, 0, JUGG_SKIN, rx=6 if d != 2 else 4.5, ry=5)   # bare chest
    rect(b, 10, 20, 22, 21, 12)                          # red sash
    put(b, 21, 22, 12)
    if f != 2:
        arms32(b, d, f, 7, 7, sy=14, wide=6)
        if d != 1:
            line(b, 23, 21, 29, 9, 5)                    # katana held low
            line(b, 22, 22, 23, 21, 15)
    # mask: a tall orange tiki mask covering the head
    shade_sphere(b, hx, 8.5, 5.5, [7, 7, 15], rx=5, ry=6)
    rect(b, hx - 1, 0, hx + 1, 3, 12)                    # red crest
    put(b, hx, 0, 14)
    if d == 0:
        rect(b, hx - 3, 7, hx - 2, 8, 1)                 # eye holes and a red painted mouth
        rect(b, hx + 1, 7, hx + 2, 8, 1)
        rect(b, hx - 2, 11, hx + 2, 12, 12)
        for x in range(hx - 2, hx + 3, 2):
            put(b, x, 11, 5)                             # teeth
        line(b, hx, 4, hx, 9, 14)                        # carved ridge down the brow
    elif d == 2:
        rect(b, hx + 2, 7, hx + 3, 8, 1)
        rect(b, hx + 1, 11, hx + 4, 12, 12)
    else:
        rect(b, hx - 3, 9, hx + 3, 14, 7)                # back of the mask, strap
        line(b, hx - 4, 9, hx + 4, 9, 14)
    if f == 2:                                           # the slash: blade swept wide in front
        if d == 0:
            line(b, 21, 14, 19, 21, 7, 2)
            line(b, 19, 22, 6, 28, 5)
            line(b, 19, 23, 7, 29, 4)
            put(b, 20, 22, 15)
        elif d == 1:
            line(b, 21, 14, 21, 9, 7, 2)
            line(b, 21, 8, 8, 2, 5)
            put(b, 21, 8, 15)
        else:
            line(b, 16, 14, 21, 17, 7, 2)
            line(b, 22, 18, 31, 22, 5)
            line(b, 22, 19, 30, 23, 4)
            put(b, 22, 18, 15)
    return finish(b, d, f, 8)


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
HERO_FNS = [sf_frame, pudge_frame, axe32, sniper32, zeus32, lina32, cm32, drow32, viper_frame, jugg32]
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
out.append(carr("hero_port", "u32", [v for t in hero_port for v in t], 8, "0x{:08X}"))
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
