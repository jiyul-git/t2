#!/usr/bin/env python3
"""Build the weather window plates (outside_rain.webp, outside_snow.webp) in art/lounge_bg/.

    python3 art/tools/build_weather_plates.py [--qa DIR]

Input: art/sources/bg_interior_{rain,snow}_window_gemini.webp (2490 x 1728, the same room as the
other layers, with weather painted in the window) and the aligned interior_day.webp / outside_day.webp
in art/lounge_bg/. Steps, per plate:

 1. align the whole picture to interior_day: ECC affine on the line work (gradient images), then three
    rounds of a smooth low-resolution displacement field measured on 96 px patches of the interior.
    The window area is moved with the same field. The report prints the residual (median / p90 of the
    patch shifts, and the edge agreement used by lounge_check_assets.py).
 2. clean out the painted weather that the renderer draws live instead:
    rain: thin bright slanted streaks (top-hat -> oriented line opening -> long components) are
          replaced by a row-wise linear fill; the beads and runs that sit on the glass stay.
    snow: round white flakes (disc top-hat, compact components) and the two painted crystals are
          inpainted; the frost, the icicles and the snow on the ground and roofs stay.
 3. cut: alpha = outside_day.webp's alpha (the glass area; mullions and everything in front of the
    glass are transparent), so the plate drops into the `outside` slot with the exact same mask.

The Gemini sparkle watermark sits in the lower right of the source (on the sofa cushion), outside the
cut, so it never reaches the plate. The interior of these two pictures is not used (the day / golden /
night interiors are); the lighting system grades the plates for the time of day.
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ART = Path(__file__).resolve().parent.parent
SRC = ART / 'sources'
BG = ART / 'lounge_bg'
sys.path.insert(0, str(ART.parent / 'ui' / 'tools'))

ROI = (1180, 0, 2490, 1400)          # the window part of the 2490 x 1728 picture: x0, y0, x1, y1
S = 8                                # displacement field grid: 1/8 resolution


# ---------------------------------------------------------------------------- alignment

def grad(rgb):
    g = cv2.cvtColor(rgb[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 1.5)
    r = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    return r / r.max()


def ecc_affine(a, b, mask):
    w = np.eye(2, 3, dtype=np.float32)
    for s in (4, 2, 1):
        A = cv2.resize(a, None, fx=1 / s, fy=1 / s, interpolation=cv2.INTER_AREA)
        B = cv2.resize(b, None, fx=1 / s, fy=1 / s, interpolation=cv2.INTER_AREA)
        M = cv2.resize(mask, None, fx=1 / s, fy=1 / s, interpolation=cv2.INTER_NEAREST)
        if s != 4:
            w[:, 2] *= 2
        _, w = cv2.findTransformECC(A, B, w, cv2.MOTION_AFFINE,
                                    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), M, 5)
    return w


def patch_shifts(ref, src, mask, size=96, step=32, rmin=0.2):
    """Local shifts (x, y, dx, dy, response) of src against ref by phase correlation of gradient images."""
    a = np.clip(grad(ref), 0, 1) * 1.0
    b = np.clip(grad(src), 0, 1) * 1.0
    win = cv2.createHanningWindow((size, size), cv2.CV_32F)
    out = []
    for y in range(0, a.shape[0] - size + 1, step):
        for x in range(0, a.shape[1] - size + 1, step):
            if mask[y:y + size, x:x + size].mean() < 0.98:
                continue
            pa = a[y:y + size, x:x + size]
            if pa.mean() < 0.01:
                continue
            (dx, dy), r = cv2.phaseCorrelate(pa, b[y:y + size, x:x + size], win)
            if r > rmin and abs(dx) < 12 and abs(dy) < 12:
                out.append((x + size / 2, y + size / 2, dx, dy, r))
    return np.array(out)


def smooth_field(shifts, shape, sigma=14):
    h, w = shape[0] // S, shape[1] // S
    num = np.zeros((h, w, 2), np.float32)
    den = np.zeros((h, w), np.float32)
    for x, y, dx, dy, r in shifts:
        num[int(y / S), int(x / S)] = (dx * r, dy * r)
        den[int(y / S), int(x / S)] = r
    n1, d1 = cv2.GaussianBlur(num, (0, 0), sigma / S * 2.5), cv2.GaussianBlur(den, (0, 0), sigma / S * 2.5)
    n2, d2 = cv2.GaussianBlur(num, (0, 0), 60), cv2.GaussianBlur(den, (0, 0), 60)
    c = np.clip(d1 / 0.02, 0, 1)[..., None]
    f = n1 / np.maximum(d1, 1e-9)[..., None] * c + n2 / np.maximum(d2, 1e-9)[..., None] * (1 - c)
    return cv2.resize(f, (shape[1], shape[0]), interpolation=cv2.INTER_CUBIC)


def align(ref_rgba, src, log):
    """Warp src (RGB) onto ref_rgba's interior line work. Returns the aligned RGB picture."""
    h, w = src.shape[:2]
    mask = cv2.erode((ref_rgba[..., 3] > 250).astype(np.uint8), np.ones((15, 15), np.uint8))
    ref = ref_rgba[..., :3]
    wm = ecc_affine(grad(ref), grad(src), mask)
    cur = cv2.warpAffine(src, wm, (w, h), flags=cv2.INTER_LANCZOS4 + cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    log('  affine: scale %.4f %.4f, shift %.2f %.2f px' % (wm[0, 0], wm[1, 1], wm[0, 2], wm[1, 2]))
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    for _ in range(3):
        s = patch_shifts(ref, cur, mask, 80, 24)
        med = np.median(s[:, 2:4], axis=0)
        s = s[np.hypot(s[:, 2] - med[0], s[:, 3] - med[1]) < 6]
        f = smooth_field(s, (h, w))
        cur = cv2.remap(cur, xs + f[..., 0], ys + f[..., 1], cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)
    s = patch_shifts(ref, cur, mask)
    d = np.hypot(s[:, 2], s[:, 3])
    log('  residual over %d interior patches: median %.2f px, p90 %.2f px' % (len(d), np.median(d), np.percentile(d, 90)))
    return cur


# ---------------------------------------------------------------------------- cleaning

def line_kernel(length, theta):
    k = np.zeros((length, length), np.uint8)
    c = length // 2
    t = np.deg2rad(theta)                    # from vertical; negative = the top leans to the right
    dx, dy = np.sin(t) * c, np.cos(t) * c
    cv2.line(k, (int(round(c - dx)), int(round(c - dy))), (int(round(c + dx)), int(round(c + dy))), 1, 1)
    return k


def streak_strength(rgb):
    lum = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    thin = lum - cv2.morphologyEx(lum, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))      # bright, narrower than 7 px
    best = np.zeros_like(thin)
    for a in range(-26, -5, 3):                                                         # long and slanted like the painted rain
        best = np.maximum(best, cv2.morphologyEx(thin, cv2.MORPH_OPEN, line_kernel(33, a)))
    return best


def subtract_streaks(rgb, mask):
    """Take the thin bright excess (what a 7 px opening cannot keep) out of the masked pixels, per channel.
    A painted rain streak is a semi-transparent white line, so what is left is the picture behind it, edges
    of the tower and the terminal included; nothing is smeared across them."""
    f = rgb.astype(np.float32)
    thin = f - cv2.morphologyEx(f, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    soft = np.clip(cv2.GaussianBlur(mask.astype(np.float32), (0, 0), 1.0) * 1.5, 0, 1)[..., None]
    return np.clip(f - thin * soft, 0, 255).astype(np.uint8)


def clean_rain(crop, glass, passes=((6, 28), (3.5, 36), (2.5, 44))):
    for thr, min_h in passes:
        strength = streak_strength(crop)
        m = ((strength > thr) & (glass > 0)).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        keep = np.zeros_like(m)
        for i in range(1, n):
            if st[i, cv2.CC_STAT_HEIGHT] >= min_h:
                keep[lab == i] = 1
        crop = subtract_streaks(crop, cv2.dilate(keep, np.ones((3, 3), np.uint8), iterations=2))
    return crop


# painted ice crystals in the snow picture (x0, y0, x1, y1 in the window crop): not falling snow
CRYSTALS = [(470, 240, 545, 310), (795, 340, 850, 395)]


def clean_snow(crop):
    se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    # (top-hat threshold, smallest area, largest side, lowest peak brightness): big flakes first, then the
    # small faint ones, which must be nearly white so that lamp posts and window glints stay
    for thr, min_a, max_side, peak in ((22, 12, 34, 0), (13, 8, 14, 215)):
        lum = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY).astype(np.float32)
        top = lum - cv2.morphologyEx(lum, cv2.MORPH_OPEN, se)
        n, lab, st, _ = cv2.connectedComponentsWithStats((top > thr).astype(np.uint8), connectivity=8)
        keep = np.zeros(lum.shape, np.uint8)
        for i in range(1, n):
            x, y, w, h, a = st[i]
            if min_a <= a <= 900 and max(w, h) <= max_side and max(w, h) / max(1, min(w, h)) < 2.2 and a / (w * h) > 0.45 \
                    and lum[lab == i].max() >= peak:
                keep[lab == i] = 1
        for x0, y0, x1, y1 in CRYSTALS:
            keep[y0:y1, x0:x1] |= (top[y0:y1, x0:x1] > 6).astype(np.uint8)
        crop = cv2.inpaint(crop, cv2.dilate(keep, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))) * 255, 6, cv2.INPAINT_TELEA)
    return crop


# ---------------------------------------------------------------------------- main

def build(kind, interior, glass_alpha, log, qa=None):
    log('%s:' % kind)
    src = np.asarray(Image.open(SRC / ('bg_interior_%s_window_gemini.webp' % kind)).convert('RGB'))
    aligned = align(interior, src, log)
    x0, y0, x1, y1 = ROI
    crop = np.ascontiguousarray(aligned[y0:y1, x0:x1])
    gcrop = glass_alpha[y0:y1, x0:x1]
    cleaned = clean_rain(crop, gcrop) if kind == 'rain' else clean_snow(crop)
    full = aligned.copy()
    full[y0:y1, x0:x1] = cleaned
    # outside the cleaned window region the picture is irrelevant (alpha is 0 there)
    rgba = np.dstack([full, glass_alpha])
    rgba[glass_alpha == 0, :3] = 0
    out = BG / ('outside_%s.webp' % kind)
    Image.fromarray(rgba).save(out, 'WEBP', quality=90, method=6)
    log('  wrote %s (%d KB)' % (out.name, out.stat().st_size // 1024))
    if qa:
        Path(qa).mkdir(parents=True, exist_ok=True)
        Image.fromarray(full[y0:y1, x0:x1]).save(Path(qa) / ('%s_clean.png' % kind))
        Image.fromarray(aligned[y0:y1, x0:x1]).save(Path(qa) / ('%s_aligned.png' % kind))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--qa', help='also write the aligned and the cleaned window crops here for a look')
    ap.add_argument('kinds', nargs='*', default=['rain', 'snow'])
    args = ap.parse_args(argv)
    interior = np.asarray(Image.open(BG / 'interior_day.webp').convert('RGBA'))
    glass = np.asarray(Image.open(BG / 'outside_day.webp').convert('RGBA'))[..., 3]
    for kind in args.kinds:
        build(kind, interior, glass, print, args.qa)


if __name__ == '__main__':
    main()
