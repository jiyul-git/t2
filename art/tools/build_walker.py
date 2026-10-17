#!/usr/bin/env python3
"""Build a walking character for the lounge from a 4x4 Gemini walk sheet (one config per character).

    python3 art/tools/build_walker.py rabbit turtle      # build these (default: all in CHARS)
    python3 art/tools/build_walker.py rabbit --measure   # print the feet of every usable cell
    python3 art/tools/build_walker.py rabbit --dump DIR  # also save the loop frames as PNGs

Same idea as the tiger (build_tiger_walker.py / lockbody.py, art/README.md): Gemini draws every
cell a little differently, so playing the cells as they are makes the face, ears and suitcase
flicker. Here the whole upper body (head, ears, bow, coat, both arms, phone, suitcase or backpack)
comes from ONE base cell and only the legs below the skirt/jacket hem come from each cell:

1. cut the sheet into cells (cut_sheet.py); a small sheet is first enlarged (LANCZOS + light unsharp);
2. every cell is registered on the base cell's torso (scale + shift, template match), so its legs
   hang from the base's hem in the right place;
3. its legs = what lies under the base's hem (only pieces that come out from under the hem, so its
   own suitcase and stray bits are dropped); the cut edge gets a clean outline (inkfix.reink);
   An in-between pose slides each leg (more toward the foot, nothing at the hem) and can lift it;
4. base upper body on top (the skirt hides where the legs start), pale sheet fringe removed;
5. walk_r = the frames as drawn (all these sheets walk right), walk_l = mirrored;
6. ui/web/lounge/assets/chars/<name>_walker/{atlas.webp, manifest.json}, the same format as
   tiger_walker: one anchor for every frame (body x, ground line), so the body glides level.

The loop order is chosen by measuring the feet (--measure): the planted foot moves steadily backward
relative to the body while the other swings forward; 'advance' (scene px per frame) is that backward
step times the scene scale, so the planted foot does not slide on the floor.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inkfix import reink, defringe   # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
CHARS_DIR = ROOT / 'ui/web/lounge/assets/chars'
SCENE_CHAR_SCALE = 1.25        # scene.json charScale (the renderer multiplies manifest.scale by it)

# Coordinates are in the base cell as cut_sheet.py cuts it from the (enlarged) sheet, divided by
# 'upscale' - i.e. in px of the original sheet's cell.
CHARS = {
    'rabbit': dict(
        sheet='art/sources/rabbit_walk_sheet_4x4_gemini.webp', grid=(4, 4), upscale=1,
        base='03',              # bow on, eyes open
        # the skirt's lower edge in the base cell (refined to the outline's bottom row)
        hem=[(118, 318), (126, 326), (140, 329), (160, 332), (180, 334), (200, 334), (220, 331),
             (240, 326), (255, 320), (266, 314)],
        legx=(112, 330),         # legs live in these columns (left of it: the base's suitcase)
        keep=[(55, 330)],        # pieces under the hem that stay from the base (suitcase)
        torso=(120, 205, 275, 335),   # registration box: scarf to hem
        crotch=30,               # rows under the hem where the two legs may still touch
        ramp=30,                 # rows over which an in-between's leg shift grows from 0 to full
        # one step, (cell, front dx, rear dx, front lift, rear lift): the planted foot moves back
        # ~13 px a frame; the swing foot comes forward, and the step repeats with the legs' roles swapped
        loop=['33', ('11', -8, 6, 0, 4), ('13', -15, 19, 0, 8), ('01', -19, 16, 0, 6),
              ('01', -15, 21, 10, 0), ('01', 1, 8, 8, 0), ('11', 0, 19, 5, 0), ('33', 3, 13, 3, 0)],
        height=470,              # scene px from the ear tips to the ground
        atlas=0.62,              # atlas px per working px
        step=13.25,              # planted foot, base-cell px it moves back per frame (--measure / the loop)
        fps=10,
    ),
    'turtle': dict(
        sheet='art/sources/turtle_walk_sheet_4x4_gemini.webp', grid=(4, 4), upscale=2,
        base='11',
        hem=[(18, 135), (30, 139), (45, 141), (60, 146), (80, 146), (100, 143), (112, 138)],
        legx=(25, 135),
        keep=[(15, 125)],
        torso=(30, 80, 125, 140),
        crotch=7,
        ramp=18,
        near='rear',             # the rear leg is the one nearer the viewer (drawn on top)
        # short legs on wide hips: the feet do not cross; each foot swings back and forth under its own
        # hip. Only the base cell's legs, bent at the foot, so they never flicker; the planted foot
        # moves back 5 px a frame (front foot planted in frames 0-4, rear foot in 4-0)
        loop=[('11', 11.5, -9.5, 0, 0), ('11', 6.5, -4.5, 0, 2), ('11', 1.5, 0.5, 0, 4), ('11', -3.5, 5.5, 0, 3),
              ('11', -8.5, 10.5, 0, 0), ('11', -2.5, 5.5, 3, 0), ('11', 4.5, 0.5, 4, 0), ('11', 10.5, -4.5, 2, 0)],
        height=400,
        atlas=0.62,
        step=5,
        fps=10,
    ),
}


# ---------------------------------------------------------------- images
def load(p):
    return np.asarray(Image.open(p).convert('RGBA')).astype(np.float32)


def premul(a):
    p = a.copy(); p[..., :3] *= p[..., 3:] / 255.; return p


def unpremul(p):
    out = p.copy(); al = p[..., 3:]
    out[..., :3] = np.where(al > 0, p[..., :3] * 255. / np.maximum(al, 1e-3), 0)
    return out


def over(dst, src):                      # premultiplied
    return src + dst * (1 - src[..., 3:] / 255.)


def gray_on_white(a):
    al = a[..., 3] / 255.
    return ((a[..., :3] @ np.float32([0.3, 0.59, 0.11])) * al + 255 * (1 - al)).astype(np.float32)


def cut_cells(cfg, tmp):
    sheet = Image.open(ROOT / cfg['sheet']).convert('RGB')
    k = cfg['upscale']
    if k != 1:   # no AI upscaler offline: LANCZOS and a light unsharp so the outlines stay crisp
        sheet = sheet.resize((sheet.width * k, sheet.height * k), Image.LANCZOS)
        sheet = sheet.filter(ImageFilter.UnsharpMask(radius=1.2 * k, percent=70, threshold=2))
    src = tmp / 'sheet.png'; sheet.save(src)
    cells = tmp / 'cells'
    subprocess.run([sys.executable, '-I', str(TOOLS / 'cut_sheet.py'), str(src), str(cells),
                    str(cfg['grid'][0]), str(cfg['grid'][1])], check=True, stdout=subprocess.DEVNULL)
    return cells


# ---------------------------------------------------------------- geometry
def register(B, F, box, search, scales):
    """Scale s and shift (dx, dy) so that F scaled by s and moved by -dx,-dy matches B inside box."""
    x0, y0, x1, y1 = box
    T = gray_on_white(B)[y0:y1, x0:x1]
    best = None
    for s in scales:
        Fs = cv2.resize(F, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
        G = np.full((max(Fs.shape[0], y1) + 2 * search, max(Fs.shape[1], x1) + 2 * search), 255, np.float32)
        G[search:search + Fs.shape[0], search:search + Fs.shape[1]] = gray_on_white(Fs)
        R = cv2.matchTemplate(G[y0:y1 + 2 * search, x0:x1 + 2 * search], T, cv2.TM_CCOEFF_NORMED)
        _, v, _, (mx, my) = cv2.minMaxLoc(R)
        if best is None or v > best[0]:
            best = (v, mx - search, my - search, s)
    return best


def warp(F, s, dx, dy, shape):
    M = np.float32([[s, 0, -dx], [0, s, -dy]])
    return cv2.warpAffine(F, M, (shape[1], shape[0]), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0).clip(0, 255)


def hem_line(B, pts, W):
    """Per column: the bottom row of the hem's dark outline near the given polyline."""
    xs, ys = zip(*pts)
    guess = np.interp(np.arange(W), xs, ys)
    lum = B[..., :3] @ np.float32([0.3, 0.59, 0.11])
    dark = (lum < 95) & (B[..., 3] > 128)
    h = guess.copy()
    for x in range(int(xs[0]), int(xs[-1]) + 1):
        g = int(round(guess[x]))
        rows = [y for y in range(g - 7, g + 8) if 0 <= y < B.shape[0] - 1 and dark[y, x]]
        if not rows: continue
        y = min(rows, key=lambda r: abs(r - g))         # the outline run nearest the guess ...
        while y + 1 < B.shape[0] and dark[y + 1, x]: y += 1   # ... down to its last dark row
        if y - g <= 8: h[x] = y
    hp = np.pad(h, 4, mode='edge')
    return np.array([np.median(hp[i:i + 9]) for i in range(W)])


def components(mask, conn=8):
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=conn)
    return n, lab, st


# ---------------------------------------------------------------- one character
class Walker:
    def __init__(self, name, cfg, cells, pad):
        self.name, self.cfg, self.cells, self.pad = name, cfg, cells, pad
        k = cfg['upscale']; self.k = k
        P = lambda v: int(round(v * k)) + pad
        B = load(cells / ('f_%s.png' % cfg['base']))
        H, W = B.shape[0] + 2 * pad, B.shape[1] + 2 * pad
        self.B = np.zeros((H, W, 4), np.float32); self.B[pad:pad + B.shape[0], pad:pad + B.shape[1]] = B
        self.H, self.W = H, W
        self.yy, self.xx = np.mgrid[0:H, 0:W]
        self.hem = hem_line(self.B, [(P(x), P(y)) for x, y in cfg['hem']], W)
        self.box = tuple(P(v) for v in cfg['torso'])
        self.legx = (P(cfg['legx'][0]), P(cfg['legx'][1]))
        hemg = self.hem[None, :]
        below = self.yy > hemg                 # everything under the hem goes, even faint edge pixels ...
        n, lab, st = components(below & (self.B[..., 3] > 20))
        keepB = ~below                         # ... except the pieces named in 'keep' (suitcase)
        for (x, y) in cfg['keep']:
            l = lab[P(y), P(x)]
            if l > 0: keepB |= lab == l
        self.top = premul(self.B); self.top[~keepB] = 0
        self.base_al = cv2.dilate((self.B[..., 3] > 20).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)

    def legs(self, n, front=0, rear=0, lift_front=0, lift_rear=0):
        """The legs of cell n, aligned to the base's hem: (premultiplied layer, alpha mask, info).
        front/rear move the front (right) and rear (left) leg by that many working px, lift_* raise
        them: an in-between pose, made like stride_tween.py (each leg slides as a piece, more toward
        the foot, nothing at the hem)."""
        cfg, k = self.cfg, self.k
        F = load(self.cells / ('f_%s.png' % n))
        v, dx, dy, s = register(self.B, F, self.box, search=60 * k + self.pad, scales=np.arange(0.9, 1.125, 0.01))
        A = warp(F, s, dx, dy, (self.H, self.W))
        hemg = self.hem[None, :]
        zone = (self.yy > hemg - 3) & (self.xx >= self.legx[0]) & (self.xx <= self.legx[1])
        m = (A[..., 3] > 20) & zone
        n_, lab, st = components(m)
        band = (self.yy > hemg - 3) & (self.yy < hemg + 10)
        keep = np.zeros_like(m)
        for c in range(1, n_):
            piece = lab == c
            if st[c, cv2.CC_STAT_AREA] > 40 * k * k and (piece & band).any():
                keep |= piece
        L = premul(A); L[~keep] = 0
        al = A[..., :3]
        L[(al.min(-1) > 225) & (al.max(-1) - al.min(-1) < 14)] = 0     # white sheet left between the legs
        if front or rear or lift_front or lift_rear:
            L = self.tween(L, keep, front * k, rear * k, lift_front * k, lift_rear * k)
            zone = zone | (self.yy > hemg)
        # right under the hem the legs stay inside the base's silhouette (no bits beside the skirt)
        L[(self.yy < hemg + 6 * k) & ~self.base_al] = 0
        Lp = reink(L, allow=zone.astype(np.float32), protect=(self.yy < hemg + 4 * k))
        return Lp, Lp[..., 3] > 20, dict(score=v, dx=dx, dy=dy, s=s)

    def tween(self, L, mask, front, rear, lift_front, lift_rear):
        hemg = self.hem[None, :]
        low = mask & (self.yy > hemg + self.cfg['crotch'] * self.k)
        cols = low.sum(0).astype(np.float32)
        xs = np.nonzero(cols)[0]
        a, b = xs.min(), xs.max()
        mid = slice(int(a + 0.3 * (b - a)), int(a + 0.7 * (b - a)) + 1)
        cx = mid.start + int(np.argmin(cols[mid]))          # the gap between the legs
        yy, xx = self.yy.astype(np.float32), self.xx.astype(np.float32)
        t = np.clip((yy - (hemg + 4 * self.k)) / (max(self.cfg['ramp'], 1) * self.k), 0, 1)
        r = (t * t * (3 - 2 * t)).astype(np.float32)        # 0 at the hem, 1 from the ankles down

        def moved(piece, sx, lift):
            """the leg slid by sx (raised by lift) times the ramp: nothing at the hem, all of it at the foot"""
            return cv2.remap(piece, xx - sx * r, yy + lift * r, cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        rp = L.copy(); rp[self.xx >= cx] = 0
        fp = L.copy(); fp[self.xx < cx] = 0
        mr, mf = moved(rp, rear, lift_rear), moved(fp, front, lift_front)
        cut = np.zeros_like(L); cut[..., 3][(np.abs(self.xx - cx) <= 2) & mask] = 255
        if self.cfg.get('near') == 'rear':                   # the rear leg is the near one: on top
            cut = moved(cut, rear, lift_rear)[..., 3] > 0
            mf, mr = mr, mf
        else:
            cut = moved(cut, front, lift_front)[..., 3] > 0   # where the near piece was cut off
        # the near leg is drawn over the rear one: outline it where it lies over it
        fa = mf[..., 3] > 40
        edge = fa & ~cv2.erode(fa.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        edge &= (mr[..., 3] > 40) & (self.yy > hemg + 8 * self.k) & ~cv2.dilate(cut.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        edge = cv2.dilate(edge.astype(np.uint8), np.ones((2, 2), np.uint8)).astype(bool) & fa
        out = over(mr, mf)
        out[edge] = np.float32([34, 24, 20, 255])
        return out

    def feet(self, mask):
        """Both feet, rear first: (x_left, x_right, bottom y, x of the sole's lowest rows) of the two
        leg pieces below the crotch, in base-cell px; one tuple when the legs overlap."""
        below = mask & (self.yy > self.hem[None, :] + self.cfg['crotch'] * self.k)
        n, lab, st = components(below)
        parts = sorted(range(1, n), key=lambda c: -st[c, cv2.CC_STAT_AREA])[:2]
        out = []
        for c in parts:
            ys, xs = np.nonzero(lab == c)
            sole = xs[ys >= ys.max() - 3 * self.k]
            out.append(tuple(int(v) for v in ((xs.min() - self.pad) / self.k, (xs.max() - self.pad) / self.k,
                                                (ys.max() - self.pad) / self.k, (sole.mean() - self.pad) / self.k)))
        return sorted(out)

    def frame(self, entry):
        n, *shift = entry if isinstance(entry, (tuple, list)) else (entry,)
        Lp, mask, info = self.legs(n, *shift)
        out = unpremul(over(Lp, self.top))
        return defringe(out, width=2 * self.k), mask, info


def build(name, cfg, measure=False, dump=None):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cells = cut_cells(cfg, tmp)
        w = Walker(name, cfg, cells, pad=30 * cfg['upscale'])
        if measure:
            print('%s: base %s; feet (x_left, x_right, bottom, sole x) in base-cell px, rear foot first' % (name, cfg['base']))
            for p in sorted(cells.glob('f_*.png')):
                n = p.stem[2:]
                _, mask, info = w.legs(n)
                print('  %s match %.2f scale %.2f feet %s' % (n, info['score'], info['s'], w.feet(mask)))
            return
        frames, feet = [], []
        for n in cfg['loop']:
            im, mask, info = w.frame(n)
            frames.append(im); feet.append(w.feet(mask))
    # one crop for all frames so they share one anchor
    al = np.zeros(frames[0].shape[:2], bool)
    for im in frames: al |= im[..., 3] > 0
    ys, xs = np.nonzero(al)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    frames = [Image.fromarray(im.clip(0, 255).astype(np.uint8)).crop((x0, y0, x1, y1)) for im in frames]
    # ground line: where the planted (lower) foot of each frame stands, median over the loop
    ground = float(np.median([max(f[2] for f in ff) for ff in feet])) * w.k + w.pad - y0
    fig_h = ground                                    # ear tips (top of the crop) to the ground
    # anchor x: the middle of the base's torso box
    bx = (w.box[0] + w.box[2]) / 2 - x0
    if dump:
        Path(dump).mkdir(parents=True, exist_ok=True)
        for i, im in enumerate(frames):
            im.save(Path(dump) / ('%s_r%d.png' % (name, i)))
        (Path(dump) / ('%s_meta.json' % name)).write_text(json.dumps({'ground': ground, 'bx': bx, 'feet': feet}))
    return frames, ground, bx, fig_h, feet


def pack(name, cfg, frames, ground, bx, fig_h):
    a = cfg['atlas']
    n = len(frames)
    right = [im.resize((round(im.width * a), round(im.height * a)), Image.LANCZOS) for im in frames]
    left = [im.transpose(Image.FLIP_LEFT_RIGHT) for im in right]
    fw, fh = right[0].size
    atlas = Image.new('RGBA', (n * (fw + 2), 2 * (fh + 2)), (0, 0, 0, 0))
    out = []
    for row, seq in enumerate((right, left)):
        for i, im in enumerate(seq):
            x, y = i * (fw + 2), row * (fh + 2)
            atlas.paste(im, (x, y))
            ax = bx * a if row == 0 else fw - bx * a
            out.append({'x': x, 'y': y, 'w': fw, 'h': fh, 'ax': int(round(ax)), 'ay': int(round(ground * a)) - 1})
    # manifest scale: atlas px -> scene px before charScale, so the figure is cfg['height'] scene px
    scale = cfg['height'] / (fig_h * a * SCENE_CHAR_SCALE)
    # scene px per frame = the planted foot's step, so it stays put on the floor
    adv = int(round(cfg['step'] * cfg['upscale'] * cfg['height'] / fig_h))
    d = CHARS_DIR / (name + '_walker')
    d.mkdir(parents=True, exist_ok=True)
    atlas.save(d / 'atlas.webp', lossless=False, quality=90, method=6)
    man = {
        'name': name + '_walker', 'walker': True, 'pass': 'r', 'atlas': 'atlas.webp',
        'scale': round(scale, 4), 'mirrorable': False, 'frames': out,
        'poses': {'walk_r': 0, 'walk_l': n},
        'clips': {
            'walk_r': {'from': 'walk_r', 'to': 'walk_r', 'loop': True, 'fps': cfg['fps'], 'frames': list(range(n)), 'advance': adv},
            'walk_l': {'from': 'walk_l', 'to': 'walk_l', 'loop': True, 'fps': cfg['fps'], 'frames': list(range(n, 2 * n)), 'advance': adv},
        },
    }
    (d / 'manifest.json').write_text(json.dumps(man, separators=(',', ':')))
    print('%s_walker: %d frames, atlas %dx%d, %d bytes, scale %.4f, advance %s' % (
        name, n, atlas.width, atlas.height, (d / 'atlas.webp').stat().st_size, scale, adv))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('names', nargs='*')
    ap.add_argument('--measure', action='store_true')
    ap.add_argument('--dump')
    a = ap.parse_args()
    for name in a.names or list(CHARS):
        cfg = CHARS[name]
        if a.measure:
            build(name, cfg, measure=True)
            continue
        frames, ground, bx, fig_h, feet = build(name, cfg, dump=a.dump)
        pack(name, cfg, frames, ground, bx, fig_h)


if __name__ == '__main__':
    main()
