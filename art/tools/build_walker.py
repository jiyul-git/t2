#!/usr/bin/env python3
"""Build a walking character for the lounge from a 4x4 Gemini walk sheet (one config per character).

    python3 art/tools/build_walker.py rabbit turtle [--out DIR]   # build these (default: all in CHARS)
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
6. <out>/{atlas, manifest.json} (walk_r / walk_l + face patches): one anchor for every frame (body x,
   ground line), so the body glides level. The scene uses these through art/tools/build_character.py,
   which builds the whole character (walking and sitting) on top; run alone this writes to a
   temporary folder unless --out is given.

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
import sr_upscale   # noqa: E402
from walk_bob import spread, bob_series, quantize, stretch_layer, bottom_row   # noqa: E402
import face_patch   # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
ATLAS_K = float(os.environ.get('T2_ATLAS_K', '1.25'))   # atlas resolution multiplier (art/README.md): default 1.25 = 0.775 atlas px per working px; T2_ATLAS_K=1 gives the old 0.62
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
        # walking bob (walk_bob.py): feet distance = the width of the feet; leg ~ hip to sole, base px;
        # pp = peak-to-peak as a share of the figure height
        bob=dict(mode='spread', leg=70, pp=0.01),
        # face variants (face_patch.py), base-cell px; donors from this same sheet. The base already
        # laughs with an open mouth, so only the eyes change. Base eyes: (198, 153.5), (259, 149.5).
        # The sheet has no plain closed eye, only the smiling one of f_12: the blink uses it turned
        # upside down (a lid curving down, like the tiger's), the smile as drawn.
        faces=dict(
            sheet='art/sources/rabbit_walk_sheet_4x4_gemini.webp', donor_upscale=1, preview_box=(165, 120, 290, 190),
            variants={
                'blink': dict(cell='12', scale=0.85, erase=[(198, 153.5, 12, 12.5), (259, 149.5, 8.5, 10.5)], feats=[
                    dict(box=(176, 144, 222, 165), at=(198, 157), flip_v=True),
                    dict(box=(246, 137, 274, 161), at=(259.5, 153), flip_v=True)]),
                'smile': dict(cell='12', scale=0.85, erase=[(198, 153.5, 12, 12.5), (259, 149.5, 8.5, 10.5)], feats=[
                    dict(box=(176, 144, 222, 165), at=(198, 152)),
                    dict(box=(246, 137, 274, 161), at=(259.5, 148))]),
            }),
    ),
    'turtle': dict(
        sheet='art/sources/turtle_walk_sheet_4x4_gemini.webp', grid=(4, 4), upscale=2, sr=True,
        base='11',
        hem=[(18, 135), (30, 139), (45, 141), (60, 146), (80, 146), (100, 143), (112, 138)],
        legx=(25, 135),
        keep=[(15, 125)],
        torso=(30, 80, 125, 140),
        crotch=7,
        ramp=18,
        near='rear',             # the rear leg is the one nearer the viewer (drawn on top)
        # a real stride (docs/LOUNGE_SCENE_DESIGN.md 7.10, art/README.md): the two leg pieces of the base cell are
        # pendulums that swing about hip pivots under the hem (rotation, not a slide), the pivots drawn together
        # to 28 px apart so that the feet really pass each other. Each leg is planted for half a loop (its foot
        # moves back steadily, 5 px a frame) and swings forward lifted for the other half; the near (rear) leg
        # stays on top, so the swing leg passes in front of the planted one and, half a loop later, behind it.
        stride=dict(frames=8, amp=15.0, leg=30.0, slide=(8.0, -9.0), lift=6.0),
        loop='stride',
        height=400,
        atlas=0.62,
        step=5,
        fps=10,
        # the hip is highest while the feet pass each other and lowest at the contact (feet spread)
        bob=dict(mode='spread', leg=32, pp=0.01),
        # face variants (face_patch.py), base-cell px. The face sheet walks the other way: its cells are
        # mirrored first, the boxes are in the mirrored cells. Base: big near eye (80.5, 54), narrow far
        # eye (116.5, 51) by the head's outline, small smile at (104.5, 65.5).
        faces=dict(
            sheet='art/sources/turtle_walk_sheet_faces_gemini.webp', donor_upscale=2, donor_flip=True,
            preview_box=(45, 25, 135, 80),
            variants={
                'blink': dict(cell='10', scale=1.05, erase=[(80.5, 54, 12, 15), (117, 50.5, 6.5, 11, 0, False, 16)], feats=[
                    dict(box=(54, 50, 81, 65), at=(80.5, 57)),
                    dict(box=(95, 46, 115, 60), at=(116, 54), scale=0.8)]),
                'smile': dict(cell='11', scale=1.05, erase=[(80.5, 54, 12, 15), (117, 50.5, 6.5, 11, 0, False, 16)], feats=[
                    dict(box=(53, 44, 81, 63), at=(80.5, 53)),
                    dict(box=(93, 42, 115, 60), at=(116, 50), scale=0.8)]),
                'laugh': dict(cell='21', scale=1.05, erase=[(80.5, 54, 12, 15), (117, 50.5, 6.5, 11, 0, False, 16),
                                                           (104.5, 65.5, 9.5, 4, 0, False)], feats=[
                    dict(box=(54, 45, 80, 61), at=(80.5, 53)),
                    dict(box=(94, 42, 115, 59), at=(116, 50), scale=0.8),
                    dict(box=(75, 59, 103, 74), at=(105, 67.5), scale=0.75, color=True)]),
            }),
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


def stride_loop(cfg):
    """The loop entries of a 'stride' config: dict(cell, A=(slide, angle, lift), B=(...)) per frame; A is the rear
    (screen-left, near) leg, B the front leg. The foot of the planted leg moves back linearly, the swing leg
    comes forward with a smooth ease and a lift."""
    st = cfg['stride']
    n, s, L, lift = st['frames'], st['amp'], st['leg'], st['lift']
    half = n // 2
    sm = lambda q: q * q * (3 - 2 * q)
    out = []
    for f in range(n):
        g = f % half                         # frame within the half
        planted_off = s * (1 - 2 * g / half)         # +s ... -s over the stance
        swing_q = g / half
        swing_off = -s + 2 * s * sm(swing_q)         # -s ... +s over the swing
        swing_lift = lift * np.sin(np.pi * swing_q)
        # first half: B (front) planted, A swings; second half: the other way round
        offA, liftA, offB, liftB = (swing_off, swing_lift, planted_off, 0.0) if f < half else (planted_off, 0.0, swing_off, swing_lift)
        ang = lambda off: float(np.degrees(np.arcsin(np.clip(off / L, -0.95, 0.95))))
        out.append(dict(cell=cfg['base'], A=(st['slide'][0], ang(offA), liftA), B=(st['slide'][1], ang(offB), liftB)))
    return out


def resolve(cfg, sr=True):
    """(config, sr path) as it is built; see resolve_sr. A 'stride' loop is expanded into its entries."""
    cfg, path = resolve_sr(cfg, sr)
    if cfg.get('loop') == 'stride':
        cfg = dict(cfg, loop=stride_loop(cfg))
    return cfg, path


def resolve_sr(cfg, sr=True):
    """The config as it is built: a small sheet (cfg 'sr': True) is super-resolved 4x (sr_upscale.py) and
    cut 4x, so 'upscale' becomes 4 and the atlas factor halves (it is atlas px per working px); without
    the network weights the old LANCZOS 2x path stays. Returns (config, path of the 4x sheet or None)."""
    if sr and cfg.get('sr') and cfg['upscale'] == 2:
        im = sr_upscale.upscale(ROOT / cfg['sheet'])
        if im is not None:
            p = Path(tempfile.mkdtemp(prefix='sr_')) / 'sheet4.png'
            im.save(p, compress_level=1)
            faces = cfg.get('faces')
            if faces and faces.get('donor_upscale') == 2:
                faces = dict(faces, donor_upscale=4, kern=2)       # the face donors are super-resolved too; erase sizes were tuned at 2x
            return dict(cfg, upscale=4, atlas=cfg['atlas'] * cfg['upscale'] / 4, _sr=str(p), faces=faces), str(p)
    return cfg, None


def cut_cells(cfg, tmp):
    k = cfg['upscale']
    if cfg.get('_sr'):            # super-resolved (resolve): cells are cut 4x from the 1x mask and the 4x colours
        src = ROOT / cfg['sheet']
        extra = [cfg['_sr']]
    else:
        sheet = Image.open(ROOT / cfg['sheet']).convert('RGB')
        if k != 1:   # no AI upscaler: LANCZOS and a light unsharp so the outlines stay crisp
            sheet = sheet.resize((sheet.width * k, sheet.height * k), Image.LANCZOS)
            sheet = sheet.filter(ImageFilter.UnsharpMask(radius=1.2 * k, percent=70, threshold=2))
        src = tmp / 'sheet.png'; sheet.save(src)
        extra = []
    cells = tmp / 'cells'
    subprocess.run([sys.executable, '-I', str(TOOLS / 'cut_sheet.py'), str(src), str(cells),
                    str(cfg['grid'][0]), str(cfg['grid'][1])] + extra, check=True, stdout=subprocess.DEVNULL)
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

    def legs(self, n, front=0, rear=0, lift_front=0, lift_rear=0, tw=None):
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
        if tw is not None:                       # a rotation stride (tween_rot)
            L = tw(L, keep)
            zone = zone | (self.yy > hemg)
        elif front or rear or lift_front or lift_rear:
            L = self.tween(L, keep, front * k, rear * k, lift_front * k, lift_rear * k)
            zone = zone | (self.yy > hemg)
        # right under the hem the legs stay inside the base's silhouette (no bits beside the skirt); a stride may
        # reach a little beyond it (the legs swing about pivots under the hem)
        allowed = self.base_al if tw is None else cv2.dilate(self.base_al.astype(np.uint8), np.ones((1, 12 * k + 1), np.uint8)).astype(bool)
        L[(self.yy < hemg + 6 * k) & ~allowed] = 0
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

    def tween_rot(self, L, mask, e):
        """The legs as two pendulums (a stride): the layer L is split between the legs; each piece swings about its
        hip pivot just under the hem by its angle, is slid sideways (pivot towards the other leg) and lifted, e =
        dict(A=(slide, angle, lift), B=...) in base-cell px / degrees (A = the left piece). A static band under the
        hem keeps the crotch closed; the near leg (cfg 'near') is drawn over the other and outlined where it lies
        over it."""
        cfg, k = self.cfg, self.k
        hemg = self.hem[None, :]
        low = mask & (self.yy > hemg + cfg['crotch'] * k)
        cols = low.sum(0).astype(np.float32)
        xs = np.nonzero(cols)[0]
        a, b = xs.min(), xs.max()
        mid = slice(int(a + 0.3 * (b - a)), int(a + 0.7 * (b - a)) + 1)
        cx = mid.start + int(np.argmin(cols[mid]))          # the gap between the legs
        pa, pb = L.copy(), L.copy()
        pa[self.xx >= cx] = 0
        pb[self.xx < cx] = 0
        hem_y = float(np.median(self.hem[self.legx[0]:self.legx[1]])) + 3 * k      # the pivot row, a little under the hem
        band = L.copy(); band[self.yy > hemg + 9 * k] = 0
        # close the crotch: between the legs, in every row of the band, fill from the leftmost to the rightmost leg pixel
        # with the leg's own (shadowed) colour, so no hole shows once the legs have been slid together
        ba = band[..., 3] > 128
        shade = np.median(band[..., :3][ba & (self.yy > hemg + 2 * k)], 0) * 0.82 if (ba & (self.yy > hemg + 2 * k)).any() else np.float32([60, 80, 40])
        for y in np.nonzero(ba.any(1))[0]:
            xs_ = np.nonzero(ba[y])[0]
            gap = (np.arange(self.W) > xs_.min()) & (np.arange(self.W) < xs_.max()) & ~ba[y]
            band[y, gap, :3] = shade
            band[y, gap, 3] = 255

        def hip(piece):
            rows = (self.yy > hem_y) & (self.yy < hem_y + 10 * k) & (piece[..., 3] > 128)
            return float(np.nonzero(rows)[1].mean())

        t = np.clip((self.yy.astype(np.float32) - (hem_y - 3 * k)) / (max(cfg['ramp'], 1) * k), 0, 1)
        r = (t * t * (3 - 2 * t)).astype(np.float32)          # 0 at the hem, 1 from the ankles down

        def swing(piece, spec):
            """the piece rotated about its hip pivot by the angle, slid and lifted - by the share r(y) of it, so
            nothing moves at the hem and the foot gets all of it (no seam, no ragged flap)"""
            dx, ang, lift = spec
            px = hip(piece)
            c_, s_ = np.cos(np.radians(ang)), np.sin(np.radians(ang))
            X, Y = self.xx.astype(np.float32) - px, self.yy.astype(np.float32) - hem_y
            # the exact inverse of the full rotation + slide + lift, blended with the identity by r(y)
            Xo, Yo = X - dx * k, Y + lift * k
            Xi, Yi = c_ * Xo - s_ * Yo, s_ * Xo + c_ * Yo
            out = cv2.remap(piece, (self.xx + r * (Xi - X)).astype(np.float32), (self.yy + r * (Yi - Y)).astype(np.float32), cv2.INTER_CUBIC,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            out = np.clip(out, 0, 255)
            out[..., :3] = np.minimum(out[..., :3], out[..., 3:])
            return out
        ma, mb = swing(pa, e['A']), swing(pb, e['B'])
        near, far = (ma, mb) if cfg.get('near') == 'rear' else (mb, ma)
        # outline the near leg where it lies over the far one
        na = near[..., 3] > 40
        edge = na & ~cv2.erode(na.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        edge &= (far[..., 3] > 40) & (self.yy > hemg + 8 * k)
        edge = cv2.dilate(edge.astype(np.uint8), np.ones((2, 2), np.uint8)).astype(bool) & na
        out = over(over(band, far), near)
        out[edge] = np.float32([34, 24, 20, 255])
        # a hole between the legs that the slide closed over (the sheet's white between the legs was cut out) is
        # the shadow between them: fill it with the leg colour, darker
        solid = (out[..., 3] > 20).astype(np.uint8)
        n_, lab, st, _ = cv2.connectedComponentsWithStats(1 - solid, connectivity=4)
        for c in range(1, n_):
            x, y, w_, h_, area = st[c]
            if x > 0 and y > 0 and x + w_ < self.W and y + h_ < self.H and area < 400 * k * k:
                m = lab == c
                m = cv2.dilate(m.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
                ring = cv2.dilate(m.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool) & ~m & (out[..., 3] > 200)
                col = np.median(out[..., :3][ring], 0) * 0.8 if ring.any() else np.float32([60, 80, 40])
                out[m, :3] = col; out[m, 3] = 255
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
        """(legs layer, legs mask, match info) of one loop entry; compose() makes the picture."""
        if isinstance(entry, dict):
            return self.legs(entry['cell'], tw=lambda L, m: self.tween_rot(L, m, entry))
        n, *shift = entry if isinstance(entry, (tuple, list)) else (entry,)
        return self.legs(n, *shift)

    def compose(self, Lp):
        return defringe(unpremul(over(Lp, self.top)), width=2 * self.k)

    def lifts(self, entry):
        """(front lift, rear lift) of a loop entry: a foot with lift 0 is on the floor."""
        if isinstance(entry, dict):
            return entry['B'][2], entry['A'][2]
        if not isinstance(entry, (tuple, list)):
            return 0, 0
        return (entry[3] if len(entry) > 3 else 0), (entry[4] if len(entry) > 4 else 0)

    def spreads(self, masks, feet):
        """Per frame, the feet distance s (base-cell px) that sets the hip height (walk_bob.py).
        'spread': the width of the feet - narrow when the legs cross, wide when they are apart.
        'stance' (short legs that never cross): twice the planted foot's distance from its own hip,
        each foot's hip being the middle of its swing."""
        cfg = self.cfg
        if cfg['bob']['mode'] == 'spread':
            w = np.array([spread(m & (self.yy > self.hem[None, :] + cfg['crotch'] * self.k)) / self.k for m in masks])
            return w - w.min()
        soles = np.array([[f[3] for f in ff] for ff in feet], np.float64)   # (rear, front) per frame
        hip = soles.mean(0)
        out = []
        for i, entry in enumerate(cfg['loop']):
            lf, lr = self.lifts(entry)
            d = [abs(soles[i, 1] - hip[1])] if lf == 0 else []
            d += [abs(soles[i, 0] - hip[0])] if lr == 0 else []
            out.append(2 * max(d) if d else 0.0)
        return np.array(out)


def face_cfg(cfg, w):
    """cfg['faces'] with base-cell coordinates turned into working px of the (padded) frame."""
    f = cfg.get('faces') or dict(variants={})
    k, pad = w.k, w.pad
    P = lambda v: v * k + pad
    out = dict(f, variants={})
    for name, v in f['variants'].items():
        out['variants'][name] = dict(
            v, scale=v['scale'] * k, line_w=v.get('line_w', 2.4) * k,
            erase=[(P(e[0]), P(e[1]), e[2] * k, e[3] * k) + tuple(e[4:]) for e in v.get('erase', [])],
            feats=[dict(ft, at=(P(ft['at'][0]), P(ft['at'][1])), **({'scale': ft['scale'] * k} if 'scale' in ft else {}))
                   for ft in v.get('feats', [])])
    if 'preview_box' in f:
        out['preview_box'] = tuple(int(P(v)) for v in f['preview_box'])
    return out


def face_base(name):
    """(base cell at working px, faces config in working px), for face_patch.py --preview."""
    cfg = CHARS[name]
    tmp = Path(tempfile.mkdtemp())
    w = Walker(name, cfg, cut_cells(cfg, tmp), pad=30 * cfg['upscale'])
    return w.B, face_cfg(cfg, w)


def build(name, cfg, measure=False, dump=None):
    cfg, _ = resolve(cfg)
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
        layers, masks, feet = [], [], []
        for n in cfg['loop']:
            Lp, mask, info = w.frame(n)
            layers.append(Lp); masks.append(mask); feet.append(w.feet(mask))
        k, a = w.k, cfg['atlas'] * ATLAS_K
        # the crop's top: the head (the upper body is the same in every frame; the legs only move down)
        al = np.zeros(layers[0].shape[:2], bool)
        for Lp in layers: al |= (over(Lp, w.top)[..., 3] > 0)
        ys, xs = np.nonzero(al)
        y0 = ys.min()
        # ground line: where the planted (lower) foot of each frame stands, median over the loop
        ground = float(np.median([max(f[2] for f in ff) for ff in feet])) * k + w.pad - y0
        fig_h = ground                                    # ear tips (top of the crop) to the ground
        # walking bob (walk_bob.py): the body a little higher while the legs pass each other. ay of
        # frame i = body + bob_i in whole atlas px; the legs are stretched so the lowest foot ends on
        # that row, so the feet stay on the floor while the body rises and sinks
        bc = cfg['bob']
        s_feet = w.spreads(masks, feet)
        pp = bc['pp'] * fig_h * a                         # peak-to-peak in atlas px (bc['pp'] of the figure)
        bob = quantize(bob_series(s_feet, bc['leg'], pp))
        ay0 = int(round(ground * a)) - 1
        ays = [ay0 + b for b in bob]
        frames, planted = [], []
        for i, Lp in enumerate(layers):
            foot = bottom_row(Lp[..., 3] > 20)
            target = (ays[i] + 1) / a + y0                # working px row the lowest foot should end on
            Lp = stretch_layer(Lp, w.hem + 4 * k, foot, target)
            planted.append((foot - w.pad) / k)
            frames.append(w.compose(Lp))
        # face variants (face_patch.py) on the first frame: the head is the same in every frame
        faces = face_patch.variants(frames[0], face_cfg(cfg, w)) if cfg.get('faces') else {}
    al = np.zeros(frames[0].shape[:2], bool)
    for im in frames: al |= im[..., 3] > 0
    ys, xs = np.nonzero(al)
    x0, x1, y1 = xs.min(), xs.max() + 1, ys.max() + 1
    frames = [Image.fromarray(im.clip(0, 255).astype(np.uint8)).crop((x0, y0, x1, y1)) for im in frames]
    faces = {k: Image.fromarray(im.clip(0, 255).astype(np.uint8)).crop((x0, y0, x1, y1)) for k, im in faces.items()}
    # anchor x: the middle of the base's torso box
    bx = (w.box[0] + w.box[2]) / 2 - x0
    bobinfo = dict(s=[round(float(v), 1) for v in s_feet], bob=bob, ay=ays, planted_before=planted,
                   pp_scene=round(cfg['height'] / (fig_h * a) * (max(bob) - min(bob)), 2))
    if dump:
        Path(dump).mkdir(parents=True, exist_ok=True)
        for i, im in enumerate(frames):
            im.save(Path(dump) / ('%s_r%d.png' % (name, i)))
        for k, im in faces.items():
            im.save(Path(dump) / ('%s_r0_%s.png' % (name, k)))
        (Path(dump) / ('%s_meta.json' % name)).write_text(json.dumps({'ground': ground, 'bx': bx, 'feet': feet, 'bob': bobinfo}))
    return frames, ays, bx, fig_h, bobinfo, faces


def pack(name, cfg, frames, ays, bx, fig_h, faces=None, out_dir=None, lossless=False, quiet=False):
    """Write <out_dir>/<name>_walker/{atlas, manifest.json}; out_dir defaults to a new temporary folder.
    lossless=True writes atlas.png (build_character.py re-encodes the whole atlas once)."""
    a = cfg['atlas'] * ATLAS_K
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
            out.append({'x': x, 'y': y, 'w': fw, 'h': fh, 'ax': int(round(ax)), 'ay': ays[i]})
    # face variants: one patch per direction, every frame of that direction points at it (frame.v)
    if faces:
        varied = {k: im.resize(right[0].size, Image.LANCZOS) for k, im in faces.items()}
        patches = face_patch.direction_patches(right[0], varied, list(range(n))) + \
            face_patch.direction_patches(right[0], varied, list(range(n, 2 * n)), flip=True)
        atlas = face_patch.attach(atlas, out, patches)
    # manifest scale: atlas px -> scene px before charScale, so the figure is cfg['height'] scene px
    scale = cfg['height'] / (fig_h * a * SCENE_CHAR_SCALE)
    # scene px per frame = the planted foot's step, so it stays put on the floor
    adv = int(round(cfg['step'] * cfg['upscale'] * cfg['height'] / fig_h))
    d = (Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix='walkers_'))) / (name + '_walker')
    d.mkdir(parents=True, exist_ok=True)
    aname = 'atlas.png' if lossless else 'atlas.webp'
    if lossless:
        atlas.save(d / aname)
    else:
        atlas.save(d / aname, lossless=False, quality=90, method=6)
    man = {
        'name': name + '_walker', 'walker': True, 'pass': 'r', 'atlas': aname,
        'scale': round(scale, 4), 'mirrorable': False, 'frames': out,
        'poses': {'walk_r': 0, 'walk_l': n},
        'clips': {
            'walk_r': {'from': 'walk_r', 'to': 'walk_r', 'loop': True, 'fps': cfg['fps'], 'frames': list(range(n)), 'advance': adv},
            'walk_l': {'from': 'walk_l', 'to': 'walk_l', 'loop': True, 'fps': cfg['fps'], 'frames': list(range(n, 2 * n)), 'advance': adv},
        },
    }
    (d / 'manifest.json').write_text(json.dumps(man, separators=(',', ':')))
    if not quiet:
        print('%s_walker: %d frames, atlas %dx%d, %d bytes, scale %.4f, advance %s -> %s' % (
            name, n, atlas.width, atlas.height, (d / aname).stat().st_size, scale, adv, d))
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('names', nargs='*')
    ap.add_argument('--measure', action='store_true')
    ap.add_argument('--dump')
    ap.add_argument('--out', help='output folder (default: a new temporary folder)')
    a = ap.parse_args()
    for name in a.names or list(CHARS):
        cfg = CHARS[name]
        if a.measure:
            build(name, cfg, measure=True)
            continue
        frames, ays, bx, fig_h, bob, faces = build(name, cfg, dump=a.dump)
        print('%s bob: s %s -> bob %s atlas px (%.1f scene px peak-to-peak)' % (name, bob['s'], bob['bob'], bob['pp_scene']))
        pack(name, resolve(cfg)[0], frames, ays, bx, fig_h, faces, out_dir=a.out)


if __name__ == '__main__':
    main()
