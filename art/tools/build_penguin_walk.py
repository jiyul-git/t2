#!/usr/bin/env python3
"""Build the penguin waddle (walk) from WHOLE cells of the waddle sheet, and pack it for the lounge.

    python3 art/tools/build_penguin_walk.py [--out DIR] [--scene DIR]

The first try cut f_00 of the walk sheet into a body and two leg pieces and moved the pieces
(art/README.md); the user rejected it (seams at pixel level, a rigid body). This one uses only whole
drawn cells of art/sources/penguin_waddle_sheet_4x4_gemini.webp (cut to art/cutouts/penguin_waddle/,
rows 1-3; row 4 has no cap, f_13 has a stray blob under the feet):

1. every cell is enlarged 2x (LANCZOS) and registered on f_00's head and scarf (top 60 %: scale and shift by
   template matching), so the head stays in one place and one size from frame to frame;
2. the whole cell is turned about its stance foot (a point on the sole line, PIVOT of the way across
   the figure) by DEG degrees (+ = clockwise on screen) and raised by BOB px: the waddle;
3. blink: the closed eyes of the walk sheet's f_01 are put on each frame's own eyes (found in the
   cell), before the turn, so they turn with the head (face_patch.py; one patch per frame);
4. writes <out>/right_<i>.png, left_<i>.png (mirrored) and walk_right.gif / walk_left.gif
   (FPS, mid-grey background), and the lounge walker <scene>/{atlas.webp, manifest.json} (walk_r /
   walk_l only, like build_walker.py's; sitting comes with the climb sheet). 'advance': two steps per
   loop, each the feet's distance at contact, so the feet do not skate on average (the cells waddle in
   place: a planted foot does not slide back from cell to cell).
Deterministic: same cells in, same pixels out.
"""
import argparse
import json
import os
import sys
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import face_patch                  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CELLS = ROOT / 'art/cutouts/penguin_waddle'
OUT = ROOT / 'art/cutouts/penguin_walk_loop'
SCENE = ROOT / 'ui/web/lounge/assets/chars/penguin'
REF = '00'                       # the head every cell is registered on
UP = 2                           # cells are enlarged this much (LANCZOS) before anything else
# the waddle: (cell, degrees (+ = clockwise), bob px at 2x (+ = up), pivot: stance foot, share of the figure's width)
SEQ = [('00', -6, 0, .3), ('01', -3, 3, .3), ('02', 0, 6, .5), ('03', 3, 3, .7),
       ('10', 6, 0, .7), ('11', 3, 3, .7), ('02', 0, 6, .5), ('20', -3, 3, .3)]
FPS = 8
PAD = 40                         # canvas margin around the registered f_00 (2x px): room for the turn
HEAD = 0.6                       # the top share of the figure used to register (cap, face and scarf; the head alone let f_20's body jump)
GIF_BG = (128, 134, 140)
HEIGHT = 360                     # scene px from the cap to the soles (tiger ~440, turtle ~400)
ATLAS = 0.62 * float(os.environ.get('T2_ATLAS_K', '1.25'))   # atlas px per working (2x) px, as build_walker.py
SCENE_CHAR_SCALE = 1.25          # scene.json charScale (the renderer multiplies manifest.scale by it)
# blink donor: the walk sheet's f_01 walks with both eyes shut (happy arcs); boxes in its 1x cell px
BLINK = dict(sheet='art/sources/penguin_walk_sheet_4x4_gemini.webp', cell='01',
             near=(62, 56, 81, 68), far=(97, 54, 112, 66))


def load(name):
    return np.asarray(Image.open(CELLS / ('f_%s.png' % name)).convert('RGBA')).astype(np.float32)


def up(a):
    im = Image.fromarray(a.clip(0, 255).round().astype(np.uint8))
    im = im.resize((im.width * UP, im.height * UP), Image.LANCZOS)
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


def gray(a):
    g = cv2.cvtColor(a[..., :3].clip(0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    return g * (a[..., 3] / 255) + 128 * (1 - a[..., 3] / 255)


def register(a, ref):
    """(scale, dx, dy): a scaled by `scale` and moved by (dx, dy) puts its head on ref's head"""
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


def eyes(a):
    """the two eye blobs of a 2x cell (upper head, dark, about 7x9 px at 1x): [(x, y)] left to right"""
    lum = a[..., :3] @ np.float32([0.3, 0.59, 0.11])
    m = (lum < 70) & (a[..., 3] > 200)
    rows = np.nonzero(a[..., 3].max(1) > 128)[0]
    top, h = rows[0], rows[-1] - rows[0]
    m[:top + int(h * 0.2)] = 0; m[top + int(h * 0.45):] = 0
    n, _, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8))
    k = UP * UP
    c = [tuple(cen[i]) for i in range(1, n)
         if st[i][2] <= 10 * UP and 8 * UP <= st[i][3] <= 11 * UP and 25 * k <= st[i][4] <= 60 * k]
    if len(c) != 2:
        raise SystemExit('eyes: expected 2, found %r' % (c,))
    return sorted(c)


def face_white(a, x, y):
    """(x, y) in 1x px: the nearest spot of plain white face around an eye. The far eye sits between the
    grey stripe of the face, the blush and the dark side of the head, so the fill colour is taken from here."""
    best = None
    for dy in range(-9, 10):
        for dx in range(-9, 10):
            if dx * dx / 4.5 ** 2 + dy * dy / 6.5 ** 2 <= 1.6:
                continue                              # still on the eye or its rim
            cx, cy = int(round((x + dx) * UP)), int(round((y + dy) * UP))
            p = a[cy - 2:cy + 3, cx - 2:cx + 3]
            if p.shape[:2] != (5, 5) or p[..., 3].min() < 250:
                continue
            rgb = np.median(p[..., :3].reshape(-1, 3), 0)
            if rgb.min() > 200 and rgb.max() - rgb.min() < 30 and (best is None or dx * dx + dy * dy < best[0]):
                best = (dx * dx + dy * dy, (x + dx, y + dy))
    return best[1] if best else (x, y + 7)


def blink(a, donors):
    """the 2x cell with its eyes shut (face_patch.apply, coordinates in the cell's 1x px)"""
    (nx, ny), (fx, fy) = [(x / UP, y / UP) for x, y in eyes(a)]
    spec = dict(scale=1.0, cell=BLINK['cell'],
                erase=[(nx, ny, 6.5, 7.5), dict(e=(fx, fy, 4.5, 6.5), skin=face_white(a, fx, fy))],
                feats=[dict(box=BLINK['near'], at=(nx, ny + 0.5)), dict(box=BLINK['far'], at=(fx, fy + 0.5))])
    return face_patch.apply(a, spec, donors, 1, k=UP)


def feet(a):
    """orange foot blobs in the bottom 30 % of the figure: [(cx, bottom)] left to right"""
    r, g, b, al = [a[..., k] for k in range(4)]
    m = (r > 170) & (g > 70) & (g < 175) & (b < 120) & (r - b > 90) & (al > 128)
    rows = np.nonzero(al.max(1) > 128)[0]
    m[:rows[0] + int((rows[-1] - rows[0]) * 0.7)] = 0
    n, _, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8))
    sole = rows[-1] - 0.12 * (rows[-1] - rows[0])     # a foot reaches near the sole line (not the beak)
    out = [(float(cen[i][0]), int(st[i][1] + st[i][3])) for i in range(1, n)
           if st[i][4] > 30 * UP * UP and st[i][1] + st[i][3] > sole]
    return sorted(out)


def build():
    ref = up(load(REF))
    H, W = ref.shape[0] + 2 * PAD, ref.shape[1] + 2 * PAD
    donors = {(None, BLINK['cell']): face_patch.donor_cell(BLINK['sheet'], BLINK['cell'])}
    frames, blinks, spread = [], [], []
    for cell, deg, bob, piv in SEQ:
        a = up(load(cell))
        s, dx, dy = register(a, ref)
        M = np.float32([[s, 0, dx + PAD], [0, s, dy + PAD]])
        al = warp(a, M, (H, W))
        rows = np.nonzero(al[..., 3].max(1) > 128)[0]
        cols = np.nonzero(al[..., 3].max(0) > 128)[0]
        px, py = cols[0] + piv * (cols[-1] - cols[0]), float(rows[-1])
        R = cv2.getRotationMatrix2D((float(px), py), -deg, 1.0)     # cv2: + = counter-clockwise
        R[1, 2] -= bob
        # one warp from the cell: register, turn about the stance foot, bob
        T = (np.vstack([R, [0, 0, 1]]) @ np.vstack([M, [0, 0, 1]]))[:2].astype(np.float32)
        frames.append(warp(a, T, (H, W)))
        blinks.append(warp(blink(a, donors), T, (H, W)))
        f = feet(frames[-1])
        if abs(deg) == max(abs(q[1]) for q in SEQ):
            spread.append(f[-1][0] - f[0][0])         # contact (widest turn): both feet down, a step apart
        print('f_%s: scale %.3f, turn %+d, bob %d, feet x %s' % (cell, s, deg, bob, ['%.1f' % x for x, _ in f]))
    # Gemini drew the waddle in place: a planted foot does not slide back from cell to cell, so no advance
    # keeps it still in every frame. The loop is two steps, each as long as the feet are apart at contact:
    # advancing that much per loop keeps the feet from skating on average.
    step = 2 * float(np.mean(spread)) / len(SEQ)
    alpha = np.max([f[..., 3] for f in frames], 0)
    rows = np.nonzero(alpha.max(1) > 128)[0]
    r0 = np.nonzero(frames[0][..., 3].max(1) > 128)[0]
    info = dict(step=step, spread=spread, sole=int(r0[-1]), fig_h=int(r0[-1] + 1 - r0[0]), top=int(rows[0]))
    print('feet apart at contact %s px (2x) -> %.2f px per frame' % (['%.1f' % v for v in spread], step))
    return frames, blinks, info


def to_img(f):
    return Image.fromarray(f.clip(0, 255).round().astype(np.uint8))


def save(frames, out):
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob('*_*.png'):
        f.unlink()
    for side in ('right', 'left'):
        gif = []
        for i, f in enumerate(frames):
            im = to_img(f)
            if side == 'left':
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            im.save(out / ('%s_%d.png' % (side, i)))
            bg = Image.new('RGBA', im.size, GIF_BG + (255,))
            bg.alpha_composite(im)
            gif.append(bg.convert('RGB'))
        pal = gif[0].quantize(colors=255, method=Image.MEDIANCUT, dither=Image.NONE)
        gq = [g.quantize(palette=pal, dither=Image.NONE) for g in gif]
        gq[0].save(out / ('walk_%s.gif' % side), save_all=True, append_images=gq[1:],
                   duration=int(1000 / FPS), loop=0, disposal=1, optimize=False)
    print('wrote %d frames x 2 sides + walk_right.gif / walk_left.gif to %s' % (len(frames), out))


def enlarge(f, a):
    im = to_img(f)
    im = im.resize((round(im.width * a), round(im.height * a)), Image.LANCZOS)
    rgb = im.convert('RGB').filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))
    return Image.merge('RGBA', (*rgb.split(), im.getchannel('A')))


def anchor_x(im):
    """body x: the middle of the top 35 % of the figure (head and cap), as build_tiger_walker.py"""
    m = np.asarray(im)[..., 3] > 128
    top = int(np.nonzero(m.any(1))[0][0])
    xs = np.nonzero(m[top:top + int(im.height * 0.35)])[1]
    return int(round(xs.mean()))


def pack(frames, blinks, info, out):
    """<out>/{atlas.webp, manifest.json}: a walker (walk_r / walk_l, a blink patch on every frame), the
    same format as build_walker.py's. All frames share one canvas and one foot line (the bob is drawn in)."""
    a = ATLAS                                         # atlas px per 2x frame px (the 2x frames are the working px)
    n = len(frames)
    t = int(round(max(info['top'] - 4, 0) * a))       # empty rows above the highest cap are cut off
    right = [enlarge(f, a) for f in frames]
    right = [im.crop((0, t, im.width, im.height)) for im in right]
    left = [im.transpose(Image.FLIP_LEFT_RIGHT) for im in right]
    fw, fh = right[0].size
    bx = anchor_x(right[0])
    ay = int(round((info['sole'] + 1) * a)) - 1 - t
    per = (n + 1) // 2                                # frames per atlas row
    rows = -(-n // per)
    atlas = Image.new('RGBA', (per * (fw + 2), 2 * rows * (fh + 2)), (0, 0, 0, 0))
    out_frames = []
    for side, seq in enumerate((right, left)):
        for i, im in enumerate(seq):
            x, y = (i % per) * (fw + 2), (side * rows + i // per) * (fh + 2)
            atlas.paste(im, (x, y))
            out_frames.append({'x': x, 'y': y, 'w': fw, 'h': fh, 'ax': bx if side == 0 else fw - bx, 'ay': ay})
    # blink: one patch per frame (every frame's head is its own drawing), both directions
    patches = []
    for i in range(n):
        v = {'blink': enlarge(blinks[i], a).crop((0, t, fw, t + fh))}
        patches += face_patch.direction_patches(right[i], v, [i])
        patches += face_patch.direction_patches(right[i], v, [n + i], flip=True)
    atlas = face_patch.attach(atlas, out_frames, patches)
    # manifest scale: atlas px -> scene px before charScale, so the figure is HEIGHT scene px
    scale = HEIGHT / (info['fig_h'] * a * SCENE_CHAR_SCALE)
    # scene px per frame = the stance foot's step, so it stays put on the floor
    adv = int(round(info['step'] * HEIGHT / info['fig_h']))
    out.mkdir(parents=True, exist_ok=True)
    atlas.save(out / 'atlas.webp', lossless=False, quality=90, method=6)
    clip = dict(loop=True, fps=FPS, advance=adv)
    man = {
        'name': 'penguin', 'walker': True, 'pass': 'r', 'atlas': 'atlas.webp',
        'scale': round(scale, 4), 'mirrorable': False, 'frames': out_frames,
        'poses': {'walk_r': 0, 'walk_l': n},
        'poseInfo': {},                               # what seat poses face: none yet (no sitting art)
        'clips': {
            'walk_r': {'from': 'walk_r', 'to': 'walk_r', 'frames': list(range(n)), **clip},
            'walk_l': {'from': 'walk_l', 'to': 'walk_l', 'frames': list(range(n, 2 * n)), **clip},
        },
    }
    (out / 'manifest.json').write_text(json.dumps(man, separators=(',', ':')))
    print('penguin: %d frames, atlas %dx%d, %d bytes, scale %.4f, advance %d -> %s' % (
        n, atlas.width, atlas.height, (out / 'atlas.webp').stat().st_size, scale, adv, out))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(OUT), help='loop frames and preview GIFs')
    ap.add_argument('--scene', default=str(SCENE), help="the lounge walker (atlas, manifest); '' to skip")
    args = ap.parse_args()
    frames, blinks, info = build()
    save(frames, Path(args.out))
    if args.scene:
        pack(frames, blinks, info, Path(args.scene))
