#!/usr/bin/env python3
"""Placeholder art for the lobby lounge scene (docs/LOUNGE_SCENE_DESIGN.md 6.5).

Draws flat-colour backgrounds and four round characters with every clip of the
asset contract (6.1-6.3), so the engine can be built and tested before the real
artwork exists. Real art replaces these files; no code changes are needed.
Output is deterministic: the same arguments give byte-identical files.
Needs Pillow and numpy.
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

W, H = 1440, 1040
WINDOW = dict(x=560, y=40, w=880, h=560)
BOARD = dict(x=70, y=110, w=450, h=260, rows=5)
SEAT_X = [330, 500, 670, 840, 1010, 1180]
BASELINE_Y = 940
HORIZON_Y = 470
MULLIONS_X = [560, 780, 1000, 1220, 1440]
MULLION_W = 16
TRANSOM_Y = 300
LAMPS = [dict(x=150, y=900, r=520), dict(x=720, y=620, r=600), dict(x=1330, y=900, r=520)]

# Character cell: logical frame LW x LH, stored at 1/SCALE size.
SCALE = 3
CELL_W, CELL_H = 80, 147
LW, LH = CELL_W * SCALE, CELL_H * SCALE
AX_L, AY_L = LW // 2, 432                    # foot anchor in logical px
AX_A, AY_A = AX_L // SCALE, AY_L // SCALE    # same, in atlas px
ATLAS_COLS = 24

# ----------------------------------------------------------------------------- backgrounds

NIGHT = dict(
    wall=['#2a2f4f', '#262b49', '#222642'], frame='#11162c', frame_edge='#3b4268',
    floor_a='#1d2138', floor_b='#191d32', floor_line='#323a5e',
    board_frame='#0a0e1f', board_bg='#0f2a5a', board_row='#183a78',
    bench_back='#4a3b55', bench_front='#352a42', bench_arm='#5a4868', bench_edge='#2a2034',
    leaf='#2f7a55', leaf2='#3f9a6a', pot='#6a4a3a', pole='#8a7a55', suit='#a24a3a', suit_trim='#e0b060',
    city=['#151c36', '#1b2342', '#101730'], tower='#1c2848', runway='#0e1226', mark='#6a7399',
    plane='#d4dbe8', plane_trim='#3a4a9a', plane_win='#2a3566', lamp_shade='#f0d9a0',
)
DAY = dict(
    wall=['#e9d9c0', '#e2d0b4', '#dac6a8'], frame='#8a6f58', frame_edge='#fff1d8',
    floor_a='#b99b78', floor_b='#ad8f6c', floor_line='#8e7254',
    board_frame='#2a2a33', board_bg='#274a86', board_row='#35609f',
    bench_back='#c9a07c', bench_front='#a9805e', bench_arm='#d8b290', bench_edge='#7a5a42',
    leaf='#4fa66a', leaf2='#6cc088', pot='#c08060', pole='#b89a60', suit='#d86a5a', suit_trim='#fff0b0',
    city=['#9fb4cc', '#8ea5c0', '#b4c6da'], tower='#7a90ac', runway='#5a6270', mark='#e8ecf4',
    plane='#ffffff', plane_trim='#3a5ac0', plane_win='#4a6a9a', lamp_shade='#fff0c0',
)


def new_layer():
    return Image.new('RGBA', (W, H), (0, 0, 0, 0))


def rect(d, x0, y0, x1, y1, fill):
    """Half-open rectangle [x0,x1) x [y0,y1), no antialiasing so alpha is identical across palettes."""
    if x1 > x0 and y1 > y0:
        d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=fill)


def glass_cells():
    """Window panes between the mullions and the transom bar."""
    xs = []
    prev = None
    for mx in MULLIONS_X:
        lo = mx - MULLION_W // 2
        hi = mx + MULLION_W // 2
        if prev is not None:
            xs.append((prev, lo))
        prev = hi
    ys = [(WINDOW['y'] + 8, TRANSOM_Y - 8), (TRANSOM_Y + 8, WINDOW['y'] + WINDOW['h'] - 8)]
    return [(x0, y0, x1, y1) for (x0, x1) in xs for (y0, y1) in ys]


def build_outside(p):
    img = new_layer()
    d = ImageDraw.Draw(img)
    rng = random.Random(7)
    x = WINDOW['x'] + 8
    xr = W
    # skyline
    while x < xr:
        bw = rng.randint(34, 70)
        bh = rng.randint(30, 85)
        rect(d, x, HORIZON_Y - bh, min(x + bw, xr), HORIZON_Y, p['city'][rng.randint(0, 2)])
        x += bw
    # control tower
    rect(d, 700, 345, 716, HORIZON_Y, p['tower'])
    rect(d, 688, 322, 728, 345, p['tower'])
    rect(d, 680, 316, 736, 324, p['frame'])
    # runway / apron
    rect(d, WINDOW['x'] + 8, HORIZON_Y, W, WINDOW['y'] + WINDOW['h'], p['runway'])
    for dash in range(WINDOW['x'] + 40, W, 120):
        rect(d, dash, 548, dash + 60, 556, p['mark'])
    # airplane
    rect(d, 880, 408, 1360, 462, p['plane'])
    d.ellipse([1300, 408, 1396, 462], fill=p['plane'])
    d.ellipse([850, 410, 920, 462], fill=p['plane'])
    d.polygon([(880, 408), (840, 330), (872, 330), (940, 408)], fill=p['plane_trim'])      # tail fin
    d.polygon([(1040, 440), (1190, 440), (1130, 500), (1050, 500)], fill=p['plane_trim'])  # wing
    rect(d, 960, 438, 1250, 446, p['plane_trim'])
    for wx in range(1010, 1330, 30):
        rect(d, wx, 420, wx + 12, 430, p['plane_win'])
    d.ellipse([1180, 452, 1230, 482], fill=p['plane_win'])                                # engine
    # clip everything to the glass cells so the layer never spills onto the wall
    mask = Image.new('L', (W, H), 0)
    md = ImageDraw.Draw(mask)
    for (x0, y0, x1, y1) in glass_cells():
        rect(md, x0 - 8, y0 - 8, x1 + 8, y1 + 8, 255)
    img.putalpha(Image.composite(img.getchannel('A'), Image.new('L', (W, H), 0), mask))
    return img


def build_outside_emit():
    img = new_layer()
    d = ImageDraw.Draw(img)
    rng = random.Random(11)
    for _ in range(150):                      # lit windows in the skyline
        x = rng.randint(WINDOW['x'] + 16, W - 8)
        y = rng.randint(380, HORIZON_Y - 6)
        rect(d, x, y, x + 4, y + 5, (255, 220, 130, 255))
    for x in range(WINDOW['x'] + 30, W, 80):  # taxiway lights
        rect(d, x, 520, x + 6, 526, (120, 200, 255, 255))
        rect(d, x + 40, 580, x + 46, 586, (255, 120, 120, 255))
    rect(d, 700, 316, 736, 324, (255, 90, 90, 255))
    return img


def build_interior(p):
    img = new_layer()
    d = ImageDraw.Draw(img)
    # wall in three flat bands over the whole canvas above the floor, then floor
    rect(d, 0, 0, W, 200, p['wall'][0])
    rect(d, 0, 200, W, 400, p['wall'][1])
    rect(d, 0, 400, W, WINDOW['y'] + WINDOW['h'], p['wall'][2])
    for i, y in enumerate(range(WINDOW['y'] + WINDOW['h'], H, 56)):
        rect(d, 0, y, W, min(y + 56, H), p['floor_a'] if i % 2 == 0 else p['floor_b'])
        rect(d, 0, y, W, y + 3, p['floor_line'])
    # departures board (blank)
    b = BOARD
    rect(d, b['x'] - 12, b['y'] - 12, b['x'] + b['w'] + 12, b['y'] + b['h'] + 12, p['board_frame'])
    rect(d, b['x'], b['y'], b['x'] + b['w'], b['y'] + b['h'], p['board_bg'])
    rh = b['h'] // b['rows']
    for r in range(b['rows']):
        rect(d, b['x'] + 6, b['y'] + r * rh + rh - 6, b['x'] + b['w'] - 6, b['y'] + r * rh + rh - 3, p['board_row'])
    # window frame: everything inside the window rectangle is frame except the glass cells
    wx0, wy0, wx1, wy1 = WINDOW['x'], WINDOW['y'], WINDOW['x'] + WINDOW['w'], WINDOW['y'] + WINDOW['h']
    rect(d, wx0, wy0, wx1, wy1, p['frame'])
    for (x0, y0, x1, y1) in glass_cells():
        rect(d, x0 - 2, y0 - 2, x1 + 2, y1 + 2, p['frame_edge'])
        rect(d, x0, y0, x1, y1, (0, 0, 0, 0))   # glass: transparent so the sky shows through
    # small lamp on the sill
    rect(d, 712, 584, 728, 592, p['pole'])
    d.polygon([(700, 584), (740, 584), (732, 566), (708, 566)], fill=p['lamp_shade'])
    # wall sconces
    for sx in (30, 545):
        rect(d, sx - 8, 52, sx + 8, 76, p['pole'])
        d.polygon([(sx - 14, 52), (sx + 14, 52), (sx + 8, 30), (sx - 8, 30)], fill=p['lamp_shade'])
    return img


def glow(img, cx, cy, radius, color, steps=6):
    d = ImageDraw.Draw(img)
    for i in range(steps):
        r = radius * (1 - i / steps)
        a = int(40 + 215 * (i + 1) / steps)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (a // 3 if i < steps - 1 else a,))
    return img


def build_interior_emit():
    img = new_layer()
    for sx in (30, 545):
        glow(img, sx, 42, 60, (255, 205, 120))
    glow(img, 720, 574, 48, (255, 215, 140))
    return img


def build_bench_back(p):
    img = new_layer()
    d = ImageDraw.Draw(img)
    rect(d, SEAT_X[0] - 95, 790, SEAT_X[-1] + 95, 806, p['bench_edge'])
    for x in SEAT_X:
        d.rounded_rectangle([x - 76, 650, x + 76, 800], radius=24, fill=p['bench_back'], outline=p['bench_edge'], width=4)
    return img


def build_bench_front(p):
    img = new_layer()
    d = ImageDraw.Draw(img)
    x0, x1 = SEAT_X[0] - 95, SEAT_X[-1] + 95
    d.rounded_rectangle([x0, 800, x1, 905], radius=18, fill=p['bench_front'], outline=p['bench_edge'], width=4)
    for bx in [x0 + 6] + [(SEAT_X[i] + SEAT_X[i + 1]) // 2 for i in range(len(SEAT_X) - 1)] + [x1 - 6]:
        d.rounded_rectangle([bx - 11, 772, bx + 11, 905], radius=9, fill=p['bench_arm'], outline=p['bench_edge'], width=3)
    return img


def build_props(p):
    img = new_layer()
    d = ImageDraw.Draw(img)
    # floor lamps
    for lx in (150, 1330):
        rect(d, lx - 4, 730, lx + 4, 900, p['pole'])
        d.ellipse([lx - 26, 898, lx + 26, 914], fill=p['pole'])
        d.polygon([(lx - 34, 730), (lx + 34, 730), (lx + 22, 690), (lx - 22, 690)], fill=p['lamp_shade'])
    # plant (left)
    d.rounded_rectangle([14, 920, 118, 1040], radius=10, fill=p['pot'])
    for ang, ln, col in [(-70, 190, 'leaf'), (-45, 230, 'leaf2'), (-20, 250, 'leaf'), (0, 270, 'leaf2'), (20, 240, 'leaf'), (45, 200, 'leaf2')]:
        tx = 66 + math.sin(math.radians(ang)) * ln * 0.55
        ty = 930 - math.cos(math.radians(ang)) * ln
        d.line([(66, 930), (tx, ty)], fill=p[col], width=22)
        d.ellipse([tx - 24, ty - 24, tx + 24, ty + 24], fill=p[col])
    # suitcase (right)
    d.rounded_rectangle([1340, 840, 1440, 1040], radius=14, fill=p['suit'])
    rect(d, 1384, 800, 1396, 842, p['pole'])
    rect(d, 1340, 900, 1440, 912, p['suit_trim'])
    rect(d, 1340, 970, 1440, 982, p['suit_trim'])
    return img


def build_props_emit():
    img = new_layer()
    for lx in (150, 1330):
        glow(img, lx, 712, 70, (255, 205, 120))
    return img


def build_floor_light():
    """Window-shaped patch of sunlight. Drawn with its top-centre pixel on `anchor`."""
    w, h = 800, 300
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pane_w, gap, skew = 170, 22, 60
    x = (w - (4 * pane_w + 3 * gap)) // 2
    for _ in range(4):
        d.polygon([(x, 10), (x + pane_w, 10), (x + pane_w + skew, h - 10), (x + skew, h - 10)], fill=(255, 255, 255, 220))
        x += pane_w + gap
    return img


def build_backgrounds(out):
    bg = out / 'bg'
    bg.mkdir(parents=True, exist_ok=True)
    files = {
        'outside_night.png': build_outside(NIGHT), 'outside_day.png': build_outside(DAY),
        'outside_emit.png': build_outside_emit(),
        'interior_night.png': build_interior(NIGHT), 'interior_day.png': build_interior(DAY),
        'interior_emit.png': build_interior_emit(),
        'bench_back.png': build_bench_back(NIGHT), 'bench_front.png': build_bench_front(NIGHT),
        'props.png': build_props(NIGHT), 'props_emit.png': build_props_emit(),
        'floor_light.png': build_floor_light(),
    }
    for name, img in files.items():
        save_png(img, bg / name)


def scene_json():
    return {
        'placeholder': True,
        'size': [W, H],
        'baselineY': BASELINE_Y,
        'horizonY': HORIZON_Y,
        'windowFacing': 225,
        'window': dict(WINDOW),
        'board': dict(BOARD),
        'seats': [{'id': 's%d' % i, 'x': x} for i, x in enumerate(SEAT_X)],
        'entries': {'left': -220, 'right': 1660},
        'lamps': [dict(l) for l in LAMPS],
        'floorLight': {'file': 'bg/floor_light.png', 'anchor': [1000, 600]},
        'layers': [
            {'id': 'outside', 'group': 'back', 'tint': True,
             'variants': [{'elev': -18, 'file': 'bg/outside_night.png'}, {'elev': 10, 'file': 'bg/outside_day.png'}],
             'emission': 'bg/outside_emit.png', 'emissionKey': 'city'},
            {'id': 'interior', 'group': 'back', 'tint': True,
             'variants': [{'elev': -18, 'file': 'bg/interior_night.png'}, {'elev': 10, 'file': 'bg/interior_day.png'}],
             'emission': 'bg/interior_emit.png', 'emissionKey': 'lamp'},
            {'id': 'benchBack', 'group': 'back', 'tint': True, 'variants': [{'elev': 0, 'file': 'bg/bench_back.png'}]},
            {'id': 'benchFront', 'group': 'mid', 'tint': True, 'variants': [{'elev': 0, 'file': 'bg/bench_front.png'}]},
            {'id': 'props', 'group': 'front', 'tint': True, 'variants': [{'elev': 0, 'file': 'bg/props.png'}],
             'emission': 'bg/props_emit.png', 'emissionKey': 'lamp'},
        ],
    }


def save_png(img, path, max_colors=0):
    """Palette PNG. Flat art (<=256 colours) is stored exactly; with max_colors the image is
    reduced to that many colours first (used for the antialiased character atlases)."""
    rgba = img.convert('RGBA')
    arr = np.asarray(rgba, dtype=np.uint8)
    packed = arr.view('>u4').reshape(arr.shape[:2])
    uniq, inverse = np.unique(packed, return_inverse=True)
    if len(uniq) > 256:
        if not max_colors:
            rgba.save(path, 'PNG', optimize=True)
            return
        q = rgba.quantize(colors=max_colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
        q.save(path, 'PNG', optimize=True)
        return
    pal = np.zeros((len(uniq), 4), dtype=np.uint8)
    pal[:, 0] = (uniq >> 24) & 255
    pal[:, 1] = (uniq >> 16) & 255
    pal[:, 2] = (uniq >> 8) & 255
    pal[:, 3] = uniq & 255
    out = Image.fromarray(inverse.reshape(arr.shape[:2]).astype(np.uint8), 'P')
    out.putpalette(pal[:, :3].reshape(-1).tolist())
    out.save(path, 'PNG', optimize=True, transparency=bytes(pal[:, 3].tolist()))


# ----------------------------------------------------------------------------- characters

CHARS = {
    'tiger': dict(body='#f2a23a', belly='#ffe2a8', accent='#3a2a1a', ear_in='#ffd0a0', scale=1.00),
    'rabbit': dict(body='#fbf3f0', belly='#ffe6ec', accent='#f08aa8', ear_in='#f6b3c6', scale=0.90),
    'turtle': dict(body='#7fc36b', belly='#d9f0a8', accent='#3f7f4a', ear_in='#3f7f4a', scale=0.92),
    'penguin': dict(body='#34414f', belly='#f4f1ea', accent='#f2a33a', ear_in='#f2a33a', scale=0.74),
}
OUTLINE = '#2b2230'
POSE_ORDER = ['walk_r', 'walk_l', 'stand_front', 'sit', 'phone', 'call', 'eat', 'chat_l', 'chat_r', 'doze']

BASE = dict(
    turn=0.0, bob=0.0, sit=0.0, head_dx=0.0, head_dy=0.0, mouth=0.0, eyes='open',
    legs=(0.0, 0.0, 0.0, 0.0),            # footL dx, footL lift, footR dx, footR lift
    handL=(-92.0, 262.0), handR=(92.0, 262.0),
    item=None, item_pos=(0.0, 0.0),
)


def P(**kw):
    q = dict(BASE)
    q.update(kw)
    return q


def lerp(a, b, t):
    if isinstance(a, tuple):
        return tuple(lerp(x, y, t) for x, y in zip(a, b))
    if isinstance(a, (int, float)):
        return a + (b - a) * t
    return a if t < 0.5 else b


def mix_pose(a, b, t):
    return {k: lerp(a[k], b[k], t) for k in a}


def walk_pose(phase):
    s = math.sin(phase)
    c = math.cos(phase)
    swing = 38.0
    return P(turn=1.0, bob=-6.0 * abs(s) * 0 + 5.0 * (c * c) * 0 - 4.0 * abs(s), mouth=0.0,
             legs=(swing * s, max(0.0, c) * 16, -swing * s, max(0.0, -c) * 16),
             handL=(-swing * 0.8 * s, 262.0 + 4 * abs(s)), handR=(swing * 0.8 * s, 262.0 + 4 * abs(s)))


def pose_table():
    sit = dict(sit=1.0, handL=(-58.0, 352.0), handR=(58.0, 352.0))
    return {
        'walk_r': walk_pose(0.0),
        'stand_front': P(),
        'sit': P(**sit),
        'phone': P(sit=1.0, head_dy=12.0, handL=(-34.0, 306.0), handR=(34.0, 306.0), item='phone', item_pos=(0.0, 300.0)),
        'call': P(sit=1.0, head_dx=8.0, handL=(-58.0, 352.0), handR=(80.0, 178.0), item='phone', item_pos=(84.0, 170.0), mouth=0.2),
        'eat': P(sit=1.0, head_dy=6.0, handL=(-30.0, 322.0), handR=(38.0, 306.0), item='bowl', item_pos=(-10.0, 336.0)),
        'chat_r': P(sit=1.0, turn=1.0, handL=(-30.0, 352.0), handR=(60.0, 300.0)),
        'doze': P(sit=1.0, head_dy=26.0, head_dx=-10.0, eyes='closed', handL=(-52.0, 350.0), handR=(52.0, 350.0)),
    }


def periodic(k, n):
    """0 at k=0, one smooth bump over the loop."""
    return (1 - math.cos(2 * math.pi * k / n)) / 2


def build_clips(poses):
    """-> list of (clip_id, from, to, loop, fps, [pose dicts], advance, laneSwitchAt)."""
    sit, stand = poses['sit'], poses['stand_front']
    out = []

    def trans(cid, a, b, n, **kw):
        pa, pb = poses[a], poses[b]
        out.append((cid, a, b, False, 12, [mix_pose(pa, pb, i / (n - 1)) for i in range(n)], 0, kw.get('lane')))

    def loop(cid, node, n, fn, fps=12):
        base = poses[node]
        out.append((cid, node, node, True, fps, [fn(base, k, n) for k in range(n)], 0, None))

    def once(cid, node, n, fn):
        base = poses[node]
        out.append((cid, node, node, False, 12, [fn(base, k, n) for k in range(n)], 0, None))

    # walking
    out.append(('walk_r', 'walk_r', 'walk_r', True, 12, [walk_pose(2 * math.pi * k / 8) for k in range(8)], 13, None))
    out.append(('walk_l', 'walk_l', 'walk_l', True, 12, [walk_pose(2 * math.pi * k / 8) for k in range(8)], 13, None))
    for side in ('r', 'l'):
        trans('turn_%s_front' % side, 'walk_' + side, 'stand_front', 6)
        trans('turn_front_%s' % side, 'stand_front', 'walk_' + side, 6)
    trans('sit_down', 'stand_front', 'sit', 10, lane=5)
    trans('stand_up', 'sit', 'stand_front', 10, lane=5)

    def breathe(base, k, n):
        q = dict(base)
        q['bob'] = base['bob'] - 3.0 * periodic(k, n)
        if k in (15, 16):
            q['eyes'] = 'closed'
        return q
    loop('sit_idle', 'sit', 24, breathe)

    # phone / call / eat / doze: in, loop, out
    for act in ('phone', 'call', 'eat', 'doze'):
        n_in, n_loop, n_out = {'phone': (8, 16, 8), 'call': (8, 16, 8), 'eat': (8, 24, 8), 'doze': (10, 24, 10)}[act]
        trans(act + '_in', 'sit', act, n_in)
        trans(act + '_out', act, 'sit', n_out)

    def phone_loop(base, k, n):
        q = dict(base)
        q['head_dy'] = base['head_dy'] + 4 * periodic(k, n)
        q['handR'] = (base['handR'][0], base['handR'][1] - 5 * periodic(k * 2, n))
        return q
    loop('phone_loop', 'phone', 16, phone_loop)

    def call_loop(base, k, n):
        q = dict(base)
        q['mouth'] = 0.2 + 0.7 * periodic(k * 2, n)
        q['head_dx'] = base['head_dx'] + 3 * periodic(k, n)
        return q
    loop('call_loop', 'call', 16, call_loop)

    def eat_loop(base, k, n):
        q = dict(base)
        up = periodic(k, n)
        q['handR'] = (base['handR'][0] - 40 * up, base['handR'][1] - 120 * up)
        q['mouth'] = 0.6 * max(0.0, up - 0.6) / 0.4
        return q
    loop('eat_loop', 'eat', 24, eat_loop)

    def doze_loop(base, k, n):
        q = dict(base)
        q['head_dy'] = base['head_dy'] + 10 * periodic(k, n)
        q['head_dx'] = base['head_dx'] - 4 * periodic(k, n)
        return q
    loop('doze_loop', 'doze', 24, doze_loop)

    def sunglasses(base, k, n):
        q = dict(base)
        t = k / (n - 1)
        up = math.sin(math.pi * min(1.0, t * 1.0))        # hand goes to the face and back
        q['handR'] = (base['handR'][0] + (30 - base['handR'][0]) * up, base['handR'][1] + (200 - base['handR'][1]) * up)
        if 0.45 < t < 0.9:
            q['eyes'] = 'glasses'
        if 0.45 < t <= 1.0 and k < n - 1:
            q['eyes'] = 'glasses'
        if k == n - 1:
            q['eyes'] = base['eyes']
        return q
    once('sunglasses', 'sit', 20, sunglasses)

    def fix_clothes(base, k, n):
        q = dict(base)
        up = math.sin(math.pi * k / (n - 1))
        q['handL'] = (base['handL'][0] + 30 * up, base['handL'][1] - 110 * up)
        q['handR'] = (base['handR'][0] - 30 * up, base['handR'][1] - 110 * up)
        return q
    once('fix_clothes', 'sit', 18, fix_clothes)

    # chat: the `_r` clips face right (mirror of `_l`)
    for suffix in ('r', 'l'):
        node = 'chat_' + suffix
        trans('chat_in_' + suffix, 'sit', node, 6)
        trans('chat_out_' + suffix, node, 'sit', 6)

        def talk(base, k, n):
            q = dict(base)
            q['mouth'] = 0.9 * periodic(k * 4, n) if (k * 4) % n else 0.0
            q['handR'] = (base['handR'][0], base['handR'][1] - 22 * periodic(k * 2, n))
            return q

        def listen(base, k, n):
            q = dict(base)
            q['head_dy'] = base['head_dy'] + 5 * periodic(k * 2, n)
            return q
        loop('chat_talk_' + suffix, node, 16, talk)
        loop('chat_listen_' + suffix, node, 16, listen)
    return out


def _ellipse(d, cx, cy, rx, ry, fill, outline=OUTLINE, width=3):
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill, outline=outline, width=width)


def _limb(d, x0, y0, x1, y1, w, fill):
    d.line([(x0, y0), (x1, y1)], fill=OUTLINE, width=w + 6)
    for (x, y) in ((x0, y0), (x1, y1)):
        d.ellipse([x - w / 2 - 3, y - w / 2 - 3, x + w / 2 + 3, y + w / 2 + 3], fill=OUTLINE)
    d.line([(x0, y0), (x1, y1)], fill=fill, width=w)
    for (x, y) in ((x0, y0), (x1, y1)):
        d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=fill)


def draw_figure(name, pose):
    """One character frame at logical size LW x LH, feet anchored at (AX_L, AY_L)."""
    spec = CHARS[name]
    sc = spec['scale']
    canvas = Image.new('RGBA', (LW, LH), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    turn, sit = pose['turn'], pose['sit']
    bob = pose['bob']
    cx = AX_L
    hip_y = 325 + 55 * sit + bob
    ty = hip_y - 70
    rx = 66 - 14 * turn
    ry = 72
    body, belly, accent = spec['body'], spec['belly'], spec['accent']

    def T(x, y):          # logical figure space -> canvas, scaled about the foot anchor
        return AX_L + (x - AX_L) * sc, AY_L + (y - AY_L) * sc

    # draw into a full-size layer of the figure, then scale it about the anchor
    fig = Image.new('RGBA', (LW, LH), (0, 0, 0, 0))
    g = ImageDraw.Draw(fig)

    # back accessories
    if name == 'turtle':
        _ellipse(g, cx - 24 * turn, ty - 4, rx + 22, ry + 12, accent)
    # legs
    fl, ll, fr, lr = pose['legs']
    foot_y = AY_L
    spread = 30 * (1 - turn)
    for (dx_front, lift, side) in ((fl, ll, -1), (fr, lr, 1)):
        hx = cx + side * spread * (1 - 0.0)
        fx = cx + side * spread + dx_front
        fy = foot_y - lift
        _limb(g, hx, hip_y, fx, fy - 8, 44, body if name != 'penguin' else spec['accent'])
        _ellipse(g, fx + 8 * turn, fy - 6, 30, 14, body if name != 'penguin' else spec['accent'])
    # torso
    _ellipse(g, cx, ty, rx, ry, body)
    _ellipse(g, cx + 6 * turn, ty + 10, rx * 0.62, ry * 0.7, belly, outline=belly, width=1)
    if name == 'tiger':
        for yy in (ty - 40, ty - 12, ty + 16):
            g.line([(cx - rx + 8, yy), (cx - rx + 30, yy + 6)], fill=accent, width=7)
            g.line([(cx + rx - 8, yy), (cx + rx - 30, yy + 6)], fill=accent, width=7)
    # arms
    sh_y = ty - 40
    for side, hand in ((-1, pose['handL']), (1, pose['handR'])):
        sx = cx + side * (rx - 6) * (1 - 0.55 * turn)
        hx, hy = cx + hand[0], hand[1] + bob + 55 * sit * 0
        _limb(g, sx, sh_y, hx, hy, 30, body if name != 'penguin' else spec['body'])
        _ellipse(g, hx, hy, 17, 17, belly if name != 'penguin' else spec['body'], width=3)
    # head
    hx = cx + pose['head_dx'] + 16 * turn
    hy = ty - 127 + pose['head_dy']
    R = 70
    if name == 'tiger':
        for side in (-1, 1):
            _ellipse(g, hx + side * 50, hy - 52, 24, 24, body)
            _ellipse(g, hx + side * 50, hy - 52, 12, 12, spec['ear_in'], outline=spec['ear_in'], width=1)
    if name == 'rabbit':
        for side in (-1, 1):
            _ellipse(g, hx + side * 30 - 8 * turn, hy - 112, 20, 54, body)
            _ellipse(g, hx + side * 30 - 8 * turn, hy - 108, 9, 38, spec['ear_in'], outline=spec['ear_in'], width=1)
    _ellipse(g, hx, hy, R, R - 2, body)
    if name == 'turtle':
        g.pieslice([hx - R, hy - R + 2, hx + R, hy + R - 6], 180, 360, fill=accent, outline=OUTLINE, width=3)
    if name == 'penguin':
        _ellipse(g, hx + 4 * turn, hy + 18, R * 0.7, R * 0.55, belly, outline=belly, width=1)
    # face
    ex = [-26 * (1 - turn) + 22 * turn, 26 * (1 - turn) + 38 * turn]
    ey = hy - 6
    eyes = pose['eyes']
    show = [True, turn < 0.6]
    for i in range(2):
        if not show[i]:
            continue
        x = hx + ex[i]
        if eyes == 'closed':
            g.arc([x - 9, ey - 6, x + 9, ey + 8], 20, 160, fill=OUTLINE, width=4)
        elif eyes == 'glasses':
            g.rounded_rectangle([x - 15, ey - 11, x + 15, ey + 11], radius=6, fill='#15131c')
        else:
            g.ellipse([x - 7, ey - 9, x + 7, ey + 9], fill=OUTLINE)
            g.ellipse([x - 2, ey - 6, x + 3, ey - 1], fill='#ffffff')
    if eyes == 'glasses':
        g.line([(hx + ex[0], ey), (hx + ex[1] if show[1] else hx + ex[0] + 30, ey)], fill='#15131c', width=5)
    mx = hx + 30 * turn
    my = hy + 30
    mo = pose['mouth']
    if name == 'penguin':
        g.polygon([(mx - 16 + 12 * turn, my - 4), (mx + 16 + 12 * turn, my - 4), (mx + 12 * turn, my + 10 + 12 * mo)], fill=accent, outline=OUTLINE)
    else:
        g.ellipse([mx - 5, my - 8, mx + 5, my - 2], fill=accent if name == 'rabbit' else OUTLINE)
        if mo > 0.05:
            g.ellipse([mx - 8, my, mx + 8, my + 4 + 14 * mo], fill='#7a2b3a', outline=OUTLINE, width=2)
        else:
            g.arc([mx - 10, my - 8, mx + 10, my + 8], 20, 160, fill=OUTLINE, width=3)
    # held items
    item, (ix, iy) = pose['item'], pose['item_pos']
    ix, iy = cx + ix, iy + bob
    if item == 'phone':
        g.rounded_rectangle([ix - 14, iy - 24, ix + 14, iy + 24], radius=5, fill='#2d3340', outline=OUTLINE, width=3)
        g.rectangle([ix - 9, iy - 18, ix + 9, iy + 15], fill='#9fd4ff')
    elif item == 'bowl':
        g.pieslice([ix - 30, iy - 22, ix + 30, iy + 22], 0, 180, fill='#e8924a', outline=OUTLINE, width=3)
        g.ellipse([ix - 30, iy - 30, ix + 30, iy - 14], fill='#f7d98a', outline=OUTLINE, width=3)

    # scale about the anchor and place
    if sc != 1.0:
        w2, h2 = round(LW * sc), round(LH * sc)
        small = fig.resize((w2, h2), Image.NEAREST if False else Image.LANCZOS)
        ox = round(AX_L - AX_L * sc)
        oy = round(AY_L - AY_L * sc)
        canvas.alpha_composite(small, (ox, oy))
    else:
        canvas = fig
    return canvas


def render_frame(name, pose, mirror):
    img = draw_figure(name, pose)
    if mirror:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return img.resize((CELL_W, CELL_H), Image.LANCZOS)


def build_character(name, out):
    poses = pose_table()
    poses['chat_l'] = poses['chat_r']                # mirrored when rendered
    mirrored_nodes = {'walk_l', 'chat_l'}
    # clips are generated for the right-facing node and mirrored for the left-facing one
    poses['walk_l'] = poses['walk_r']
    clips = build_clips(poses)

    frames_img = []
    pose_index = {}
    for node in POSE_ORDER:
        pose_index[node] = len(frames_img)
        frames_img.append(render_frame(name, poses[node], node in mirrored_nodes))
    clip_json = {}
    for (cid, a, b, loop, fps, plist, advance, lane) in clips:
        mirror = cid.endswith('_l') and cid.split('_')[0] in ('walk', 'chat') or cid in ('turn_l_front', 'turn_front_l')
        idx = []
        for pose in plist:
            idx.append(len(frames_img))
            frames_img.append(render_frame(name, pose, mirror))
        entry = {'from': a, 'to': b, 'loop': loop, 'fps': fps, 'frames': idx}
        if advance:
            entry['advance'] = advance
        if lane is not None:
            entry['laneSwitchAt'] = lane
        clip_json[cid] = entry
    # chat_*_l clips mirror the right-facing poses
    cols = ATLAS_COLS
    rows = (len(frames_img) + cols - 1) // cols
    atlas = Image.new('RGBA', (cols * CELL_W, rows * CELL_H), (0, 0, 0, 0))
    frames = []
    for i, im in enumerate(frames_img):
        x, y = (i % cols) * CELL_W, (i // cols) * CELL_H
        atlas.paste(im, (x, y))
        frames.append({'x': x, 'y': y, 'w': CELL_W, 'h': CELL_H, 'ax': AX_A, 'ay': AY_A})
    cdir = out / 'chars' / name
    cdir.mkdir(parents=True, exist_ok=True)
    save_png(atlas, cdir / 'atlas.png', max_colors=64)
    manifest = {'name': name, 'placeholder': True, 'atlas': 'atlas.png', 'scale': SCALE, 'mirrorable': False,
                'frames': frames, 'poses': pose_index, 'clips': clip_json}
    (cdir / 'manifest.json').write_text(json.dumps(manifest, separators=(',', ':')) + '\n', encoding='utf-8')
    return atlas, len(frames)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default='ui/web/lounge/assets')
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    build_backgrounds(out)
    (out / 'scene.json').write_text(json.dumps(scene_json(), indent=1) + '\n', encoding='utf-8')
    for name in CHARS:
        _, n = build_character(name, out)
        print('%-8s %d frames' % (name, n))
    return 0


if __name__ == '__main__':
    sys.exit(main())
