#!/usr/bin/env python3
"""Extend the lounge interior downward with the floor Gemini drew (sofa bases, legs, carpet).

    python3 art/tools/extend_floor.py

Gemini did not keep the original pixels when asked to extend the picture: it redrew the room a
little further out. So only its lower part is used: scaled so its sofas match ours, attached
under art/lounge_bg/interior_<v>.webp from the row where our picture is cut (mid seat front),
cross-faded over 60 rows and colour-matched (Lab mean/std) to each lighting variant's bottom band.
Writes art/lounge_bg/interior_<v>_ext.webp. Source: art/sources/bg_floor_extension_gemini.webp
(the Gemini star watermark already painted out).
"""
from pathlib import Path
import numpy as np
import cv2
from PIL import Image

ART = Path(__file__).resolve().parent.parent
SRC = ART / 'sources/bg_floor_extension_gemini.webp'
# Gemini px -> interior px: the same in both directions (width fills the picture, 2490 / 1024).
# A smaller vertical scale doubled the right sofa's seat front.
ANCHOR = 505        # Gemini row that meets the interior's bottom edge (where the seat fronts join the base)
BLEND = 40
TPL = 90            # rows of the original's bottom matched against Gemini's picture
STEP, WIN = 30, 180 # local alignment: one shift per 30 columns, matched on a 180-column window
SEARCH_X, SEARCH_Y = 70, 50
GAP, GAP_W = 1470, 140                       # floor between the long sofa and the chairs
PIECES = [(0, 1420), (1520, 2490)]


def local_shifts(o, gs, top):
    """Per column: how far Gemini's floor must move so its sofa fronts line up with ours.
    Gemini redrew the room a little differently (the right chairs sit lower and further right), so one
    global placement doubles their seat fronts; this lines each part up where it meets the original."""
    H, W = o.shape[:2]
    def edges(a):
        g = cv2.cvtColor(a.clip(0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
        g = cv2.GaussianBlur(g, (3, 3), 0)
        return np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    eo, eg = edges(o[H - TPL:H, :, :3]), edges(gs)
    xs, dxs, dys, ok = [], [], [], []
    for xc in range(WIN // 2, W - WIN // 2 + 1, STEP):
        x0 = xc - WIN // 2
        t = eo[:, x0:x0 + WIN]
        gx0, gy0 = max(0, x0 - SEARCH_X), max(0, top - TPL - SEARCH_Y)
        reg = eg[gy0:top + SEARCH_Y, gx0:min(W, x0 + WIN + SEARCH_X)]
        r = cv2.matchTemplate(reg, t, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(r)
        xs.append(xc); dxs.append(gx0 + loc[0] - x0); dys.append(gy0 + loc[1] - (top - TPL)); ok.append(mx)
    xs, dxs, dys, ok = map(np.array, (xs, dxs, dys, ok))
    # one rigid shift per piece of furniture (the long sofa, the chairs), so lines stay straight;
    # they meet in the gap between the two, where there is only floor
    dx, dy = np.zeros(W), np.zeros(W)
    shifts = []
    for lo, hi in PIECES:
        sel = (xs >= lo) & (xs < hi) & (ok > 0.35)
        if sel.sum() == 0: sel = (xs >= lo) & (xs < hi)
        shifts.append((float(np.median(dxs[sel])), float(np.median(dys[sel]))))
    x = np.arange(W)
    t = np.clip((x - (GAP - GAP_W / 2)) / GAP_W, 0, 1); t = t * t * (3 - 2 * t)
    dx = shifts[0][0] * (1 - t) + shifts[1][0] * t
    dy = shifts[0][1] * (1 - t) + shifts[1][1] * t
    print('  long sofa shift', shifts[0], ' chairs shift', shifts[1])
    return dx, dy


def lab(a):
    return cv2.cvtColor(a.clip(0, 255).astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)


def extend(variant):
    im = Image.open(ART / ('lounge_bg/interior_%s.webp' % variant)).convert('RGBA')
    o = np.asarray(im).astype(np.float32)
    H, W = o.shape[:2]
    g = np.asarray(Image.open(SRC).convert('RGB')).astype(np.float32)
    scale = W / g.shape[1]
    gs = cv2.resize(g, (W, int(round(g.shape[0] * scale))), interpolation=cv2.INTER_CUBIC)
    top = int(ANCHOR * scale)                    # Gemini row that meets our bottom edge, before alignment
    dx, dy = SHIFT if SHIFT else local_shifts(o, gs, top)
    rows = gs.shape[0] - top - 60 + BLEND        # same height for every lighting variant
    yy, xx = np.mgrid[0:rows, 0:W].astype(np.float32)
    # the alignment matters where the furniture meets ours; further down (open carpet) it fades to
    # one even shift so the carpet's stripes stay straight
    k = np.clip((yy - (BLEND + 170)) / 140.0, 0, 1); k = k * k * (3 - 2 * k)
    dxk = dx[None] * (1 - k) + dx.mean() * k
    dyk = dy[None] * (1 - k) + np.median(dy) * k
    mapx = (xx + dxk).astype(np.float32)
    mapy = (yy + (top - BLEND) + dyk).astype(np.float32)
    ext = cv2.remap(gs, mapx, mapy, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    print('  shift x %.0f..%.0f  y %.0f..%.0f' % (dx.min(), dx.max(), dy.min(), dy.max()))
    ref, src = lab(o[H - 160:H, :, :3]), lab(ext[:160])
    e = lab(ext)
    for c in range(3):
        e[..., c] = (e[..., c] - src[..., c].mean()) / (src[..., c].std() + 1e-3) * ref[..., c].std() + ref[..., c].mean()
    ext = cv2.cvtColor(e.clip(0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB).astype(np.float32)
    ext = np.dstack([ext, np.full(ext.shape[:2], 255, np.float32)])
    out = np.zeros((H + ext.shape[0] - BLEND, W, 4), np.float32)
    out[:H] = o
    w = np.linspace(0, 1, BLEND)[:, None, None]
    out[H - BLEND:H] = o[H - BLEND:] * (1 - w) + ext[:BLEND] * w
    out[H:] = ext[BLEND:]
    dst = ART / ('lounge_bg/interior_%s_ext.webp' % variant)
    Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(dst, 'WEBP', quality=92, method=6)
    return W, out.shape[0]


SHIFT = None

if __name__ == '__main__':
    # measure once, on the night picture (strongest lines), and use it for every variant so the
    # three lighting layers stay aligned
    SHIFT = None
    o = np.asarray(Image.open(ART / 'lounge_bg/interior_night.webp').convert('RGB')).astype(np.float32)
    g = np.asarray(Image.open(SRC).convert('RGB')).astype(np.float32)
    sc = o.shape[1] / g.shape[1]
    gs = cv2.resize(g, (o.shape[1], int(round(g.shape[0] * sc))), interpolation=cv2.INTER_CUBIC)
    SHIFT = local_shifts(np.dstack([o, np.full(o.shape[:2], 255, np.float32)]), gs, int(ANCHOR * sc))
    for v in ('night', 'golden', 'day'):
        print(v, 'extended to %dx%d' % extend(v))
