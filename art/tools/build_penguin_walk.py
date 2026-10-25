#!/usr/bin/env python3
"""Build the penguin walk loop (left foot, right foot) from the Gemini sheet cells.

    python3 art/tools/build_penguin_walk.py [--out DIR]

Gemini drew the same (front, right-hand) foot forward in all 8 walk cells, so the cells in a row
read as one foot kicking. Here the walk is drawn again the way a hand animator would, from the
pieces of one cell (art/README.md, "펭귄 걷기 루프"):

1. body: f_00 with the two leg pieces (below the lower arc of the body) cut off and the new lower
   edge re-inked (inkfix.reink, only in the bottom rows; the rest is the drawing's own). Upper body is
   the drawing untouched, the same in every frame (no face flicker between cells);
2. legs: the two pieces below the arc of f_00 (orange foot + short grey stump), each grown a few
   rows upward so the stump always reaches under the body. The extended piece is the "front" shape,
   the tucked piece the "back" shape. Both are drawn BEHIND the body, so the body's lower outline
   covers every stump join;
3. one step = N frames: the planted foot slides back from the front position to the back one while
   the other foot swings forward, lifted, and they pass under the body. A foot in front of the
   middle uses the front shape, behind the middle the back shape. Every step the near and far
   roles swap: the far leg is darker (SHADE), a few px higher (RISE) and drawn first, the near leg
   normal and drawn on top with its outline where it covers the far one. So the loop is two steps,
   left-right;
4. body bob per step frame is measured from the sheet cells (BOB_CELLS: contact, down, passing, up);
   only the body moves, the feet stay on the floor;
5. writes <out>/right_<i>.png, left_<i>.png (mirrored) and walk_right.gif / walk_left.gif
   (FPS, mid-grey background, 2x for viewing);
6. the lounge walker ui/web/lounge/assets/chars/penguin/{atlas.webp, manifest.json} (walk_r / walk_l
   only, like build_walker.py's; sitting comes with the climb sheet).
Deterministic: same sheet cells in, same pixels out.
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
from inkfix import LINE, WIDTH    # noqa: E402
import face_patch                  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CELLS = ROOT / 'art/cutouts/penguin_walk'
OUT = ROOT / 'art/cutouts/penguin_walk_loop'
BASE = '00'                      # body and leg pieces come from this cell
# lower arc of the body in f_00 px: ellipse centre x, centre y, x radius, y radius.
# Fitted to the visible bottom between the feet (x 60~80 at y 168~169) and the sides (x 16 / 110 at ~153 / ~160)
ARC = (68.0, 137.0, 60.0, 31.5)
SPLIT = 60                       # leg pieces: left of this x is the back (tucked) piece
FRONT_STUMP = 33                 # the front stump starts this many px left of the front foot
GROW = 14                        # rows each stump is extended upward (hidden behind the body)
N = 5                            # frames per step; loop = 2 steps
LIFT = 5.0                       # px the swinging foot rises at the middle of the swing
RISE = 3.0                       # px the far foot sits higher (it is further away)
FAR_DX = 5.0                     # px the far foot sits to the right of the near one (3/4 view)
SHADE = 0.78                     # colour multiplier for the far leg
BOB_CELLS = ['00', '02', '03', '01']   # sheet cells whose body height (over the planted foot) gives step phases 0, 1/4, 1/2, 3/4 (contact, down, passing, up)
FPS = 10                         # the scene's walk speed (same as tiger / rabbit / turtle)
PAD = 8                          # canvas margin around the f_00 cell
GIF_BG = (128, 134, 140)
SCENE = ROOT / 'ui/web/lounge/assets/chars/penguin'
HEIGHT = 360                     # scene px from the cap to the soles (tiger ~440, turtle ~400)
ATLAS = 0.62 * float(os.environ.get('T2_ATLAS_K', '1.25'))   # atlas px per working px, as build_walker.py (the frames are 2x enlarged first)
SCENE_CHAR_SCALE = 1.25          # scene.json charScale (the renderer multiplies manifest.scale by it)
# Blink (face_patch.py) on the shared head, frame px (= f_00 px + PAD). Base eyes: near (80.5, 70.5),
# far (112.4, 68.6) next to the dark side of the head (filled from the white face only, `skin`). Donor: f_01 of the same sheet walks with both
# eyes shut (happy arcs); its arcs are placed on the base's eyes.
FACES = dict(
    sheet='art/sources/penguin_walk_sheet_4x4_gemini.webp', donor_upscale=1,
    variants={
        'blink': dict(cell='01', scale=1.0, erase=[(80.5, 70.5, 6.5, 7.5), dict(e=(112.2, 68.6, 4, 6.5), skin=(106, 72))], feats=[
            dict(box=(62, 56, 81, 68), at=(80.5, 71)),
            dict(box=(97, 54, 112, 66), at=(112.5, 69))]),
    })


def load(name):
    return np.asarray(Image.open(CELLS / ('f_%s.png' % name)).convert('RGBA')).astype(np.float32)


def premul(a):
    p = a.copy(); p[..., :3] *= p[..., 3:] / 255.
    return p


def unpremul(p):
    o = p.copy(); al = p[..., 3:]
    o[..., :3] = np.where(al > 0, p[..., :3] * 255. / np.maximum(al, 1e-3), 0)
    return o


def over(dst, src):
    return src + dst * (1 - src[..., 3:] / 255.)


def arc_y(x):
    cx, cy, rx, ry = ARC
    t = np.clip((x - cx) / rx, -1, 1)
    return cy + ry * np.sqrt(1 - t * t)


def feet(a):
    """orange foot blobs in the bottom 30% of a cell: [(x0, y0, w, h, area, cx)] left to right"""
    r, g, b, al = [a[..., k] for k in range(4)]
    m = (r > 170) & (g > 70) & (g < 175) & (b < 120) & (r - b > 90) & (al > 128)
    m[:int(a.shape[0] * 0.75)] = 0
    n, _, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8))
    out = [tuple(int(v) for v in st[i]) + (float(cen[i][0]),) for i in range(1, n) if st[i][4] > 40]
    return sorted(out, key=lambda f: f[0])


def body_height(name, ref):
    """height of the body (matched to f_00 by template) over the lowest sole in that cell, in f_00 px"""
    a = load(name)
    def gray(x):
        g = cv2.cvtColor(x[..., :3].clip(0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
        return g * (x[..., 3] / 255) + 200 * (1 - x[..., 3] / 255)
    tpl = gray(ref)[5:130, 5:145]
    best = None
    for s in np.arange(0.97, 1.06, 0.005):
        b = cv2.resize(a, None, fx=s, fy=s, interpolation=cv2.INTER_LINEAR)
        r = cv2.matchTemplate(gray(b), tpl, cv2.TM_CCOEFF_NORMED)
        _, mv, _, ml = cv2.minMaxLoc(r)
        if best is None or mv > best[0]:
            best = (mv, s, ml[1] - 5)
    _, s, oy = best
    sole = np.nonzero(a[..., 3].max(1) > 128)[0].max()
    return sole * s - oy


def split_base(a):
    """f_00 -> (body layer, back piece, front piece), premultiplied, in f_00 px"""
    H, W = a.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ay = arc_y(xx)
    pm = premul(a)
    below = (yy >= ay) & (a[..., 3] > 0)
    fb, ff = feet(a)[0], feet(a)[-1]
    n, lab = cv2.connectedComponents(below.astype(np.uint8))
    masks = []
    for side in (xx < SPLIT, xx >= SPLIT):
        ids = [i for i in range(1, n) if ((lab == i) & side).sum() > 30]
        masks.append(np.isin(lab, ids) & side)
    # the back foot hangs straight under the body: its piece is only its own columns (the grey bulge
    # of the body beside it stays with the body, or it would slide along with the foot)
    masks[0] &= (xx >= fb[0] - 1) & (xx <= fb[0] + fb[2] + 3)
    # the front piece is the stump and foot only (not the scrap of belly between the legs)
    masks[1] &= xx >= ff[0] - FRONT_STUMP
    # no slivers (the belly line just under the arc would slide along with a piece)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    for i, m in enumerate(masks):
        o = cv2.dilate(cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, k), np.ones((3, 3), np.uint8))
        masks[i] = m & o.astype(bool)
    # body: cut along the arc in every column where something hangs under it (the scraps left of the
    # back foot go with neither), anti-aliased, the drawing's line width drawn just above the cut
    legcol = (a[..., 3] * (yy > ay + 2) > 128).any(0)
    legcol = cv2.dilate(legcol.astype(np.uint8)[None], np.ones((1, 7), np.uint8))[0].astype(bool)
    keep = np.where(legcol[None, :], np.clip(ay - yy + 0.5, 0, 1), 1.0)
    keep[masks[0] | masks[1]] = 0
    body = pm * keep[..., None]
    slope = np.gradient(arc_y(np.arange(W, dtype=np.float32)))
    d = (ay - yy) / np.sqrt(1 + slope[None, :] ** 2)            # distance above the arc, px
    ring = np.clip(WIDTH + 0.5 - d, 0, 1) * (d > -0.5) * legcol[None, :] * (a[..., 3] > 128)
    body[..., :3] = body[..., :3] * (1 - ring[..., None]) + LINE * body[..., 3:] / 255. * ring[..., None]
    # legs: each grown upward by repeating its top rows (hidden behind the body), outline re-inked
    pieces = []
    for m in masks:
        p = np.zeros_like(pm); p[m] = pm[m]
        for x in np.nonzero(m.any(0))[0]:
            top = int(np.nonzero(m[:, x])[0].min())
            if top > arc_y(np.float32(x)) + 1.5:
                continue                      # the piece's own outer edge here, not the cut: leave it
            # copy a row 2 px under the top (body grey / side line, not the cut edge) upward
            src = p[min(top + 2, H - 1), x]
            y0 = max(top - GROW, 0)
            p[y0:top, x] = src
        pieces.append(p)
    return body, pieces[0], pieces[1]


def shift(layer, dx, dy):
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(layer, M, (layer.shape[1], layer.shape[0]), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def outline_over(near, far):
    """draw the near leg's outline where it lies over the far leg"""
    na = near[..., 3] > 40
    edge = na & ~cv2.erode(na.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    edge &= far[..., 3] > 40
    edge = cv2.dilate(edge.astype(np.uint8), np.ones((2, 2), np.uint8)).astype(bool) & na
    out = near.copy()
    out[edge, :3] = LINE * out[edge, 3:] / 255.
    return out


def build():
    a = load(BASE)
    H, W = a.shape[:2]
    a = np.pad(a, ((PAD, PAD), (PAD, PAD), (0, 0)))
    global ARC
    ARC = (ARC[0] + PAD, ARC[1] + PAD, ARC[2], ARC[3])
    body, back, front = split_base(a)
    fb, ff = feet(a)[0], feet(a)[-1]
    xb, xf = fb[5], ff[5]                     # foot centres: back (tucked) and front (extended)
    mid = (xb + xf) / 2
    ref = load(BASE)
    hts = [body_height(c, ref) for c in BOB_CELLS]
    ph = np.arange(len(hts) + 1) / len(hts)
    bob = [int(round(np.interp(k / N, ph, hts + hts[:1]) - hts[0])) for k in range(N)]   # + = body higher, per step frame
    print('feet back %.1f front %.1f stride %.1f px, bob %s' % (xb, xf, xf - xb, bob))

    def leg(pos, lift, far):
        """the leg piece whose foot centre is at x=pos, lifted by `lift`"""
        shape, x0 = (front, xf) if pos > mid + 0.5 else (back, xb)
        dy = -lift - (RISE if far else 0)
        p = shift(shape, pos - x0 + (FAR_DX if far else 0), dy)
        if far:
            p[..., :3] *= SHADE
        return p

    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]].astype(np.float32)
    frames = []
    for step in range(2):
        for k in range(N):
            t = k / N
            planted = xf - (xf - xb) * t
            swing = xb + (xf - xb) * t
            lift = LIFT * np.sin(np.pi * t)
            # step 0: the near leg is planted in front; step 1: the far leg is
            p_far = step == 1
            lp = leg(planted, 0, p_far)
            ls = leg(swing, lift, not p_far)
            far, near = (lp, ls) if p_far else (ls, lp)
            legs = over(far, outline_over(near, far))
            # only the body bobs, the feet stay on the floor (the stumps reach far enough up behind
            # it). Drawn with the head fixed: the legs move down by the bob and the frame's foot line
            # with them (manifest ay), so the face patches fit every frame. The stump extensions only
            # ever show under the body's arc.
            legs = shift(legs, 0, bob[k]) * np.clip(yy - arc_y(xx) + 1.0, 0, 1)[..., None]
            frames.append(unpremul(over(legs, body)))
    sole = int(np.nonzero(a[..., 3].max(1) > 128)[0].max())
    top = int(np.nonzero(a[..., 3].max(1) > 128)[0].min())
    info = dict(step=(xf - xb) / N, sole=sole, fig_h=sole + 1 - top, bob=bob * 2)
    return frames, info


def save(frames, info, out):
    """the loop frames with the feet on one floor line (the body bobs), and the preview GIFs"""
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob('*_*.png'):
        f.unlink()
    for side in ('right', 'left'):
        gif = []
        for i, f in enumerate(frames):
            f = unpremul(shift(premul(f), 0, -info['bob'][i]))
            im = Image.fromarray(f.clip(0, 255).astype(np.uint8))
            if side == 'left':
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            im.save(out / ('%s_%d.png' % (side, i)))
            bg = Image.new('RGBA', im.size, GIF_BG + (255,))
            bg.alpha_composite(im)
            gif.append(bg.convert('RGB').resize((im.width * 2, im.height * 2), Image.LANCZOS))
        pal = gif[0].quantize(colors=255, method=Image.MEDIANCUT, dither=Image.NONE)
        gq = [g.quantize(palette=pal, dither=Image.NONE) for g in gif]
        gq[0].save(out / ('walk_%s.gif' % side), save_all=True, append_images=gq[1:],
                   duration=int(1000 / FPS), loop=0, disposal=1, optimize=False)
    print('wrote %d frames x 2 sides + walk_right.gif / walk_left.gif to %s' % (len(frames), out))


def pack(frames, info, out):
    """<out>/{atlas.webp, manifest.json}: a walker (walk_r / walk_l only, no sitting yet), the same
    format as build_walker.py's. The cells are small, so they are enlarged 2x (LANCZOS + light unsharp,
    like the turtle) on the way into the atlas."""
    a = 2 * ATLAS                                     # atlas px per frame px
    right = [enlarge(f, a) for f in frames]
    left = [im.transpose(Image.FLIP_LEFT_RIGHT) for im in right]
    n = len(frames)
    fw, fh = right[0].size
    bx = anchor_x(right[0])
    ay = int(round((info['sole'] + 1) * a)) - 1
    per = (n + 1) // 2                                # frames per atlas row (keeps it under 2048 px wide)
    rows = -(-n // per)
    atlas = Image.new('RGBA', (per * (fw + 2), 2 * rows * (fh + 2)), (0, 0, 0, 0))
    out_frames = []
    for side, seq in enumerate((right, left)):
        for i, im in enumerate(seq):
            x, y = (i % per) * (fw + 2), (side * rows + i // per) * (fh + 2)
            atlas.paste(im, (x, y))
            out_frames.append({'x': x, 'y': y, 'w': fw, 'h': fh, 'ax': bx if side == 0 else fw - bx,
                               'ay': ay + int(round(info['bob'][i] * a))})
    # face variants (face_patch.py) on the shared head: one patch per direction, every frame points at it
    varied = {k: enlarge(v, a) for k, v in face_patch.variants(frames[0], FACES).items()}
    patches = face_patch.direction_patches(right[0], varied, list(range(n))) + \
        face_patch.direction_patches(right[0], varied, list(range(n, 2 * n)), flip=True)
    atlas = face_patch.attach(atlas, out_frames, patches)
    # manifest scale: atlas px -> scene px before charScale, so the figure is HEIGHT scene px
    scale = HEIGHT / (info['fig_h'] * a * SCENE_CHAR_SCALE)
    # scene px per frame = the planted foot's step, so it stays put on the floor
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


def enlarge(f, a):
    im = Image.fromarray(f.clip(0, 255).round().astype(np.uint8))
    im = im.resize((round(im.width * a), round(im.height * a)), Image.LANCZOS)
    rgb = im.convert('RGB').filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))
    return Image.merge('RGBA', (*rgb.split(), im.getchannel('A')))


def anchor_x(im):
    """body x: the middle of the top 35 % of the figure (head and cap), as build_tiger_walker.py"""
    m = np.asarray(im)[..., 3] > 128
    top = int(np.nonzero(m.any(1))[0][0])
    xs = np.nonzero(m[top:top + int(im.height * 0.35)])[1]
    return int(round(xs.mean()))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(OUT), help='loop frames and preview GIFs')
    ap.add_argument('--scene', default=str(SCENE), help="the lounge walker (atlas, manifest); '' to skip")
    a = ap.parse_args()
    frames, info = build()
    save(frames, info, Path(a.out))
    if a.scene:
        pack(frames, info, Path(a.scene))
