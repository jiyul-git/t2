#!/usr/bin/env python3
"""Build the penguin waddle (walk) and hop from WHOLE cells of the waddle sheet, and pack them for the lounge.

    python3 art/tools/build_penguin_walk.py [--out DIR] [--scene DIR]

The first try cut f_00 of the walk sheet into a body and two leg pieces and moved the pieces
(art/README.md); the user rejected it (seams at pixel level, a rigid body). This one uses only whole
drawn cells of art/sources/penguin_waddle_sheet_4x4_gemini.webp (cut to art/cutouts/penguin_waddle/,
rows 1-3; row 4 has no cap, f_13 has a stray blob under the feet, f_02 has no coffee cup):

1. every cell is enlarged 4x (LANCZOS) and registered on f_00's head and scarf (top 60 %: scale and
   shift by template matching), so the head stays in one place and one size from frame to frame;
2. walk: the whole cell is turned about its stance foot (a point on the sole line, PIVOT of the way
   across the figure) by DEG degrees (+ = clockwise on screen) and raised by BOB px: the waddle.
   hop: f_22 squashed / stretched about its feet (HOP: bob, scale x, scale y) and raised;
   one warp per frame at 4x, then down to the 2x working size (no resampling twice);
3. blink: the closed eyes of the walk sheet's f_01 are put on each walk frame's own eyes (found in
   the cell), before the turn, so they turn with the head (face_patch.py; one patch per frame);
4. finishing pass on every 2x frame (finish()): the edge ring re-inked in the drawing's line colour
   (soft, see-through or pale edge pixels: fringe, halo, broken outline), stray specks and pinholes
   removed, pockets of the white sheet kept between a foot and the body opened (see-through); then the hand fixes in FIXES. check_8x_<clip>.png: 8x crops (outline, feet, cup, flipper)
   of every finished right-facing frame to check (left frames are exact mirrors);
5. writes <out>/right_<i>.png, left_<i>.png, hop_right_<i>.png, hop_left_<i>.png, walk_right.gif /
   walk_left.gif / hop_right.gif, and the lounge walker <scene>/{atlas.webp, manifest.json}: walk_r /
   walk_l, and hop_r / hop_l (walk frame 0 -> 8 hop frames -> walk frame 0, so the director can swap
   it in at a walk-loop wrap, behavior.js). 'advance': two steps per loop, each the feet's distance at
   contact, so the feet do not skate on average (the cells waddle in place: a planted foot does not
   slide back from cell to cell); the hop moves HOP_FASTER times as far per frame.
Deterministic: same cells in, same pixels out.
"""
import argparse
import json
import os
import sys
from pathlib import Path
import numpy as np
import cv2
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import face_patch                  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CELLS = ROOT / 'art/cutouts/penguin_waddle'
OUT = ROOT / 'art/cutouts/penguin_walk_loop'
SCENE = ROOT / 'ui/web/lounge/assets/chars/penguin'
REF = '00'                       # the head every cell is registered on
UP = 4                           # cells are enlarged this much (LANCZOS) for the transforms
DOWN = 2                         # ...and the result brought down by this much: 2x working frames
# the waddle: (cell, degrees (+ = clockwise), bob px at 2x (+ = up), pivot: stance foot, share of the figure's width).
# Starts on feet together (f_22) so the hop can start and end on walk frame 0.
SEQ = [('22', 0, 6, .5), ('03', 3, 3, .7), ('10', 6, 0, .7), ('11', 3, 3, .7),
       ('22', 0, 6, .5), ('20', -3, 3, .3), ('00', -6, 0, .3), ('01', -3, 3, .3)]
FPS = 8
# the hop, from f_22: (bob px at 2x, scale x, scale y), scaled about the feet
HOP_CELL = '22'
HOP = [(0, 1.08, .88), (10, .94, 1.08), (46, .97, 1.04), (64, 1, 1), (46, .97, 1.04), (8, .96, 1.06),
       (0, 1.1, .86), (0, 1.03, .96)]
HOP_FPS = 10
HOP_FASTER = 1.15                # hop advance per frame / walk advance per frame
PAD = 40                         # canvas margin around the registered f_00 (2x px): room for the turn
TOP_ROOM = 70                    # extra room above (2x px): the hop goes 64 px up
HEAD = 0.6                       # the top share of the figure used to register (cap, face and scarf; the head alone let f_20's body jump)
GIF_BG = (128, 134, 140)
HEIGHT = 360                     # scene px from the cap to the soles (tiger ~440, turtle ~400)
ATLAS = 0.62 * float(os.environ.get('T2_ATLAS_K', '1.25'))   # atlas px per working (2x) px, as build_walker.py
SCENE_CHAR_SCALE = 1.25          # scene.json charScale (the renderer multiplies manifest.scale by it)
# blink donor: the walk sheet's f_01 walks with both eyes shut (happy arcs); boxes in its 1x cell px
BLINK = dict(sheet='art/sources/penguin_walk_sheet_4x4_gemini.webp', cell='01',
             near=(62, 56, 81, 68), far=(97, 54, 112, 66))
# hand fixes after the finishing pass, from the 8x checks: {(clip, frame): [(x, y, 'line' | 'clear'), ...]}
# in 2x frame px of the right-facing frame (the left frame is its mirror)
FIXES = {}


def load(name):
    return np.asarray(Image.open(CELLS / ('f_%s.png' % name)).convert('RGBA')).astype(np.float32)


def up(a, k=UP):
    im = Image.fromarray(a.clip(0, 255).round().astype(np.uint8))
    im = im.resize((im.width * k, im.height * k), Image.LANCZOS)
    return np.asarray(im).astype(np.float32)


def premul(a):
    p = a.copy(); p[..., :3] *= p[..., 3:] / 255.
    return p


def unpremul(p):
    o = p.copy(); al = p[..., 3:]
    o[..., :3] = np.where(al > 0, p[..., :3] * 255. / np.maximum(al, 1e-3), 0)
    return o


def warp(a, M, shape):
    """straight RGBA a through the 2x3 affine M into an image of `shape` (premultiplied in between)"""
    p = cv2.warpAffine(premul(a), M, (shape[1], shape[0]), flags=cv2.INTER_CUBIC,
                       borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    p[..., 3] = p[..., 3].clip(0, 255)
    p[..., :3] = np.minimum(p[..., :3].clip(0, None), p[..., 3:])
    return unpremul(p)


def down(a):
    """4x -> 2x (area average of the premultiplied picture: no ringing at the edge)"""
    p = cv2.resize(premul(a), None, fx=1 / DOWN, fy=1 / DOWN, interpolation=cv2.INTER_AREA)
    return unpremul(p)


def gray(a):
    g = cv2.cvtColor(a[..., :3].clip(0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    return g * (a[..., 3] / 255) + 128 * (1 - a[..., 3] / 255)


def register(a, ref):
    """(scale, dx, dy): a scaled by `scale` and moved by (dx, dy) puts its head and scarf on ref's"""
    ys = np.nonzero(ref[..., 3].max(1) > 128)[0]
    xs = np.nonzero(ref[..., 3].max(0) > 128)[0]
    y0, y1 = ys[0], ys[0] + int((ys[-1] - ys[0]) * HEAD)
    tpl = gray(ref)[y0:y1, xs[0]:xs[-1] + 1]
    best = None
    for s in np.arange(0.94, 1.16, 0.005):
        b = cv2.resize(a, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
        g = np.pad(gray(b), 40, constant_values=128)
        r = cv2.matchTemplate(g, tpl, cv2.TM_CCOEFF_NORMED)
        _, mv, _, ml = cv2.minMaxLoc(r)
        if best is None or mv > best[0]:
            best = (mv, s, xs[0] - (ml[0] - 40), y0 - (ml[1] - 40))
    return best[1:]


def eyes(a, k):
    """the two eye blobs of a k-times cell (upper head, dark, about 7x9 px at 1x): [(x, y)] left to right"""
    lum = a[..., :3] @ np.float32([0.3, 0.59, 0.11])
    m = (lum < 70) & (a[..., 3] > 200)
    rows = np.nonzero(a[..., 3].max(1) > 128)[0]
    top, h = rows[0], rows[-1] - rows[0]
    m[:top + int(h * 0.2)] = 0; m[top + int(h * 0.45):] = 0
    n, _, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8))
    c = [tuple(cen[i]) for i in range(1, n)
         if st[i][2] <= 10 * k and 8 * k <= st[i][3] <= 11 * k and 25 * k * k <= st[i][4] <= 60 * k * k]
    if len(c) != 2:
        raise SystemExit('eyes: expected 2, found %r' % (c,))
    return sorted(c)


def face_white(a, x, y, k):
    """(x, y) in 1x px: the nearest spot of plain white face around an eye. The far eye sits between the
    grey stripe of the face, the blush and the dark side of the head, so the fill colour is taken from here."""
    best = None
    for dy in range(-9, 10):
        for dx in range(-9, 10):
            if dx * dx / 4.5 ** 2 + dy * dy / 6.5 ** 2 <= 1.6:
                continue                              # still on the eye or its rim
            cx, cy = int(round((x + dx) * k)), int(round((y + dy) * k))
            p = a[cy - k:cy + k + 1, cx - k:cx + k + 1]
            if p.shape[:2] != (2 * k + 1, 2 * k + 1) or p[..., 3].min() < 250:
                continue
            rgb = np.median(p[..., :3].reshape(-1, 3), 0)
            if rgb.min() > 200 and rgb.max() - rgb.min() < 30 and (best is None or dx * dx + dy * dy < best[0]):
                best = (dx * dx + dy * dy, (x + dx, y + dy))
    return best[1] if best else (x, y + 7)


def blink(a, donors, a2, k=UP):
    """the k-times cell with its eyes shut (face_patch.apply, coordinates in the cell's 1x px). The eyes
    are found on the same cell at 2x (a2), where the size limits of eyes() were measured."""
    (nx, ny), (fx, fy) = [(x / 2, y / 2) for x, y in eyes(a2, 2)]
    spec = dict(scale=1.0, cell=BLINK['cell'],
                erase=[(nx, ny, 6.5, 7.5), dict(e=(fx, fy, 4.5, 6.5), skin=face_white(a, fx, fy, k))],
                feats=[dict(box=BLINK['near'], at=(nx, ny + 0.5)), dict(box=BLINK['far'], at=(fx, fy + 0.5))])
    return face_patch.apply(a, spec, donors, 1, k=k)


def feet(a, k=DOWN):
    """orange foot blobs near the sole line of a k-times frame: [(cx, bottom)] left to right"""
    r, g, b, al = [a[..., i] for i in range(4)]
    m = (r > 170) & (g > 70) & (g < 175) & (b < 120) & (r - b > 90) & (al > 128)
    rows = np.nonzero(al.max(1) > 128)[0]
    m[:rows[0] + int((rows[-1] - rows[0]) * 0.7)] = 0
    n, _, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8))
    sole = rows[-1] - 0.12 * (rows[-1] - rows[0])     # a foot reaches near the sole line (not the beak)
    out = [(float(cen[i][0]), int(st[i][1] + st[i][3])) for i in range(1, n)
           if st[i][4] > 30 * k * k and st[i][1] + st[i][3] > sole]
    return sorted(out)


def line_colour(a):
    """the drawing's outline colour: the dark pixels just inside the silhouette of a 1x cell"""
    solid = (a[..., 3] > 250).astype(np.uint8)
    ring = solid.astype(bool) & ~cv2.erode(solid, np.ones((5, 5), np.uint8)).astype(bool)
    lum = a[..., :3] @ np.float32([0.3, 0.59, 0.11])
    return np.median(a[..., :3][ring & (lum < 70)], 0).astype(np.float32)


def finish(f, line):
    """the finishing pass on one 2x frame (straight RGBA float): the silhouette's edge ring is the
    outline everywhere in this drawing, so every soft, see-through or pale pixel on it becomes the line
    colour (a halo of the white sheet, a lighter fringe from resampling, a broken outline); faint
    alpha dust and specks away from the figure are dropped; pinholes inside are closed."""
    out = f.copy()
    al = out[..., 3]
    al[al < 24] = 0
    # keep the figure (and any big piece), drop specks
    n, lab, st, _ = cv2.connectedComponentsWithStats((al > 0).astype(np.uint8), connectivity=8)
    if n > 2:
        big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        for i in range(1, n):
            if i != big and st[i][cv2.CC_STAT_AREA] < 150:
                al[lab == i] = 0
    # pinholes: see-through specks of a few px inside the figure
    hole = (al < 128).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(hole, connectivity=4)
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if area <= 6 and x > 0 and y > 0 and x + w < al.shape[1] and y + h < al.shape[0]:
            m = lab == i
            al[m] = 255
            out[..., :3][m] = cv2.inpaint(out[..., :3].clip(0, 255).astype(np.uint8), m.astype(np.uint8), 2,
                                          cv2.INPAINT_TELEA)[m]
    # pockets of the white sheet the cut-out kept (enclosed between a foot and the body): small light
    # unsaturated blobs low on the figure (the cream belly is one big piece) become see-through gaps;
    # their rim is then re-inked with the rest of the edge below
    rgb = out[..., :3]
    light = (rgb.min(-1) > 140) & (rgb.max(-1) - rgb.min(-1) < 40) & (al > 128)
    rows = np.nonzero((al > 128).any(1))[0]
    light[:rows[0] + int((rows[-1] - rows[0]) * 0.75)] = False
    n, lab, st, _ = cv2.connectedComponentsWithStats(light.astype(np.uint8), connectivity=8)
    for i in range(1, n):
        if st[i][cv2.CC_STAT_AREA] <= 40:
            m = cv2.dilate((lab == i).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & (rgb.min(-1) > 100)
            al[m] = 0
    # the edge ring: within 2 px of the outside
    solid = (al > 127).astype(np.uint8)
    d = cv2.distanceTransform(solid, cv2.DIST_L2, 3)
    lum = out[..., :3] @ np.float32([0.3, 0.59, 0.11])
    lline = float(line @ np.float32([0.3, 0.59, 0.11]))
    soft = (al > 0) & (al < 250) & ((d < 2.5) | (solid == 0))     # anti-aliased edge and faint dust outside: line colour, alpha kept
    pale = (solid > 0) & (d <= 1.5) & (lum > lline + 45)           # opaque but pale on the very edge
    out[..., :3][soft | pale] = line
    out[..., 3] = al
    return out


def apply_fixes(f, fixes, line):
    for x, y, what in fixes:
        if what == 'line':
            f[y, x, :3] = line; f[y, x, 3] = 255
        elif what == 'clear':
            f[y, x] = 0
    return f


class Builder:
    def __init__(self):
        self.ref = up(load(REF))
        self.H = self.ref.shape[0] + (2 * PAD + TOP_ROOM) * DOWN
        self.W = self.ref.shape[1] + 2 * PAD * DOWN
        self.donors = {(None, BLINK['cell']): face_patch.donor_cell(BLINK['sheet'], BLINK['cell'])}
        self.line = line_colour(load(REF))
        self.cache = {}

    def cell(self, name):
        """(the cell at 4x, its registration M on the 4x canvas, its registered bbox)"""
        if name not in self.cache:
            a = up(load(name))
            s, dx, dy = register(up(load(name), 2), up(load(REF), 2))
            M = np.float32([[s, 0, dx * 2 + PAD * DOWN], [0, s, dy * 2 + (PAD + TOP_ROOM) * DOWN]])
            al = warp(a, M, (self.H, self.W))[..., 3]
            rows = np.nonzero(al.max(1) > 128)[0]
            cols = np.nonzero(al.max(0) > 128)[0]
            self.cache[name] = (a, M, (cols[0], rows[0], cols[-1], rows[-1]), s)
        return self.cache[name]

    def render(self, name, A, with_blink):
        """one 2x frame: the 4x cell through registration M, then the 3x3 A (in 4x canvas px)"""
        a, M, _, _ = self.cell(name)
        T = (A @ np.vstack([M, [0, 0, 1]]))[:2].astype(np.float32)
        f = finish(down(warp(a, T, (self.H, self.W))), self.line)
        b = finish(down(warp(blink(a, self.donors, up(load(name), 2)), T, (self.H, self.W))), self.line) if with_blink else None
        return f, b

    def walk(self):
        frames, blinks, spread = [], [], []
        for cell, deg, bob, piv in SEQ:
            _, _, (x0, _, x1, y1), s = self.cell(cell)
            R = cv2.getRotationMatrix2D((float(x0 + piv * (x1 - x0)), float(y1)), -deg, 1.0)   # cv2: + = counter-clockwise
            R[1, 2] -= bob * DOWN
            f, b = self.render(cell, np.vstack([R, [0, 0, 1]]), True)
            frames.append(f); blinks.append(b)
            ft = feet(f)
            if abs(deg) == max(abs(q[1]) for q in SEQ):
                spread.append(ft[-1][0] - ft[0][0])   # contact (widest turn): both feet down, a step apart
            print('walk f_%s: scale %.3f, turn %+d, bob %d, feet x %s' % (cell, s, deg, bob, ['%.1f' % x for x, _ in ft]))
        # Gemini drew the waddle in place: a planted foot does not slide back from cell to cell, so no advance
        # keeps it still in every frame. The loop is two steps, each as long as the feet are apart at contact:
        # advancing that much per loop keeps the feet from skating on average.
        step = 2 * float(np.mean(spread)) / len(SEQ)
        print('feet apart at contact %s px (2x) -> %.2f px per frame' % (['%.1f' % v for v in spread], step))
        return frames, blinks, step

    def hop(self):
        _, _, (x0, _, x1, y1), _ = self.cell(HOP_CELL)
        cx, cy = (x0 + x1) / 2.0, float(y1)
        out = []
        for bob, sx, sy in HOP:
            A = np.float32([[sx, 0, cx - sx * cx], [0, sy, cy - sy * cy - bob * DOWN], [0, 0, 1]])
            out.append(self.render(HOP_CELL, A, False)[0])
        return out


def to_img(f):
    return Image.fromarray(f.clip(0, 255).round().astype(np.uint8))


def gif(frames, path, fps):
    ims = []
    for im in frames:
        bg = Image.new('RGBA', im.size, GIF_BG + (255,))
        bg.alpha_composite(im)
        ims.append(bg.convert('RGB'))
    pal = ims[0].quantize(colors=255, method=Image.MEDIANCUT, dither=Image.NONE)
    q = [g.quantize(palette=pal, dither=Image.NONE) for g in ims]
    q[0].save(path, save_all=True, append_images=q[1:], duration=int(1000 / fps), loop=0, disposal=1, optimize=False)


def crops(f):
    """the places to check at 8x in a 2x frame: [(name, box)]: cap outline, flipper tip, cup, feet"""
    al = f[..., 3] > 128
    rows = np.nonzero(al.any(1))[0]; cols = np.nonzero(al.any(0))[0]
    top, bot, left, right = rows[0], rows[-1], cols[0], cols[-1]
    S = 64
    mid = (left + right) // 2
    ys_left = np.nonzero(al[:, left])[0]
    ys_right = np.nonzero(al[:, right - 2])[0]
    ft = feet(f) or [(mid - S / 2, bot), (mid + S / 2, bot)]
    ft = [ft[0], ft[-1]] if len(ft) > 1 else ft * 2
    return [('cap', (mid - S // 2, top - 6)), ('flipper', (left - 6, int(ys_left.mean()) - S // 2)),
            ('cup', (right - S + 6, int(ys_right.mean()) - S // 2))] + \
        [('foot', (int(fx) - S // 2, bot - S + 8)) for fx, _ in ft], S


def check_sheet(frames, path):
    """8x nearest-neighbour crops of every frame (rows) at the places in crops() (columns)"""
    K, rows = 8, []
    for f in frames:
        cs, S = crops(f)
        im = to_img(f)
        bg = Image.new('RGBA', im.size, GIF_BG + (255,)); bg.alpha_composite(im)
        row = Image.new('RGB', (len(cs) * (S * K + 8), S * K), (40, 40, 40))
        for j, (_, (x, y)) in enumerate(cs):
            c = bg.crop((x, y, x + S, y + S)).convert('RGB').resize((S * K, S * K), Image.NEAREST)
            row.paste(c, (j * (S * K + 8), 0))
        rows.append(row)
    sheet = Image.new('RGB', (rows[0].width, len(rows) * (rows[0].height + 8)), (40, 40, 40))
    for i, r in enumerate(rows):
        sheet.paste(r, (0, i * (r.height + 8)))
    sheet.save(path, optimize=True)


def save(walk, hop, out):
    out.mkdir(parents=True, exist_ok=True)
    for f in list(out.glob('*.png')) + list(out.glob('*.gif')):
        f.unlink()
    for name, frames, fps in (('', walk, FPS), ('hop_', hop, HOP_FPS)):
        right = [to_img(f) for f in frames]
        left = [im.transpose(Image.FLIP_LEFT_RIGHT) for im in right]
        for i, (r, l) in enumerate(zip(right, left)):
            r.save(out / ('%sright_%d.png' % (name, i))); l.save(out / ('%sleft_%d.png' % (name, i)))
        if name == '':
            gif(right, out / 'walk_right.gif', fps); gif(left, out / 'walk_left.gif', fps)
            check_sheet(frames, out / 'check_8x_walk.png')
        else:
            check_sheet(frames, out / 'check_8x_hop.png')
    # the hop as the scene plays it: two walk loops, the hop, a walk loop
    w = [to_img(f) for f in walk]
    seq = [w[i % len(w)] for i in range(16)] + [w[0]] + [to_img(f) for f in hop] + [w[0]] + w[1:]
    gif(seq, out / 'hop_right.gif', FPS)
    print('wrote %d walk + %d hop frames x 2 sides, GIFs and 8x checks to %s' % (len(walk), len(hop), out))


def anchor_x(im):
    """body x: the middle of the top 35 % of the figure (head and cap), as build_tiger_walker.py"""
    m = np.asarray(im)[..., 3] > 128
    top = int(np.nonzero(m.any(1))[0][0])
    xs = np.nonzero(m[top:top + int(im.height * 0.35)])[1]
    return int(round(xs.mean()))


def shrink(f, a):
    im = to_img(f)
    return im.resize((round(im.width * a), round(im.height * a)), Image.LANCZOS)


def pack(walk, blinks, hop, step, out):
    """<out>/{atlas.webp, manifest.json}: walk_r / walk_l with a blink patch on every walk frame, and
    hop_r / hop_l, the same format as build_walker.py's. All frames share one canvas and one foot line."""
    a = ATLAS                                         # atlas px per 2x frame px
    allf = walk + hop
    alpha = np.max([f[..., 3] for f in allf], 0)
    rows = np.nonzero(alpha.max(1) > 128)[0]
    t = int(round(max(rows[0] - 4, 0) * a))           # empty rows above the highest hop are cut off
    right = [shrink(f, a) for f in allf]
    right = [im.crop((0, t, im.width, im.height)) for im in right]
    left = [im.transpose(Image.FLIP_LEFT_RIGHT) for im in right]
    n, nw = len(allf), len(walk)
    fw, fh = right[0].size
    bx = anchor_x(right[0])
    r0 = np.nonzero(walk[0][..., 3].max(1) > 128)[0]
    sole = int(r0[-1]) + 6 * DOWN // DOWN * 0      # walk frame 0 is raised by its bob: the floor is below it
    sole = int(np.nonzero(walk[2][..., 3].max(1) > 128)[0][-1])   # frame 2 (f_10, bob 0) stands on the floor
    ay = int(round((sole + 1) * a)) - 1 - t
    fig_h = sole + 1 - int(np.nonzero(walk[2][..., 3].max(1) > 128)[0][0])
    per = nw                                          # one atlas row: the walk; the next: the hop
    atlas = Image.new('RGBA', (per * (fw + 2), 4 * (fh + 2)), (0, 0, 0, 0))
    out_frames = []
    for side, seq in enumerate((right, left)):
        for i, im in enumerate(seq):
            x, y = (i % per) * (fw + 2), (side * 2 + i // per) * (fh + 2)
            atlas.paste(im, (x, y))
            out_frames.append({'x': x, 'y': y, 'w': fw, 'h': fh, 'ax': bx if side == 0 else fw - bx, 'ay': ay})
    # blink: one patch per walk frame (every frame's head is its own drawing), both directions
    patches = []
    for i in range(nw):
        v = {'blink': shrink(blinks[i], a).crop((0, t, fw, t + fh))}
        patches += face_patch.direction_patches(right[i], v, [i])
        patches += face_patch.direction_patches(right[i], v, [n + i], flip=True)
    atlas = face_patch.attach(atlas, out_frames, patches)
    # manifest scale: atlas px -> scene px before charScale, so the figure is HEIGHT scene px
    scale = HEIGHT / (fig_h * a * SCENE_CHAR_SCALE)
    adv = int(round(step * HEIGHT / fig_h))           # scene px per walk frame = the feet's step
    hop_adv = int(round(adv * HOP_FASTER))
    out.mkdir(parents=True, exist_ok=True)
    atlas.save(out / 'atlas.webp', lossless=False, quality=90, method=6)
    W, H = list(range(nw)), list(range(nw, n))
    man = {
        'name': 'penguin', 'walker': True, 'pass': 'r', 'atlas': 'atlas.webp',
        'scale': round(scale, 4), 'mirrorable': False, 'frames': out_frames,
        'poses': {'walk_r': 0, 'walk_l': n},
        'poseInfo': {},                               # what seat poses face: none yet (no sitting art)
        'clips': {
            'walk_r': {'from': 'walk_r', 'to': 'walk_r', 'loop': True, 'fps': FPS, 'frames': W, 'advance': adv},
            'walk_l': {'from': 'walk_l', 'to': 'walk_l', 'loop': True, 'fps': FPS, 'frames': [n + i for i in W], 'advance': adv},
            # a hop in the middle of a pass (behavior.js): starts and ends on walk frame 0
            'hop_r': {'from': 'walk_r', 'to': 'walk_r', 'loop': False, 'fps': HOP_FPS, 'frames': [0] + H + [0], 'advance': hop_adv},
            'hop_l': {'from': 'walk_l', 'to': 'walk_l', 'loop': False, 'fps': HOP_FPS, 'frames': [n] + [n + i for i in H] + [n], 'advance': hop_adv},
        },
    }
    (out / 'manifest.json').write_text(json.dumps(man, separators=(',', ':')))
    print('penguin: %d frames, atlas %dx%d, %d bytes, scale %.4f, advance %d, hop advance %d -> %s' % (
        n, atlas.width, atlas.height, (out / 'atlas.webp').stat().st_size, scale, adv, hop_adv, out))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(OUT), help='loop frames, preview GIFs and 8x checks')
    ap.add_argument('--scene', default=str(SCENE), help="the lounge walker (atlas, manifest); '' to skip")
    args = ap.parse_args()
    B = Builder()
    walk, blinks, step = B.walk()
    hop = B.hop()
    for (clip, i), fx in FIXES.items():
        tgt = walk if clip == 'walk' else hop
        tgt[i] = apply_fixes(tgt[i], fx, B.line)
        if clip == 'walk':
            blinks[i] = apply_fixes(blinks[i], fx, B.line)
    save(walk, hop, Path(args.out))
    if args.scene:
        pack(walk, blinks, hop, step, Path(args.scene))
