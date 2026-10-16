#!/usr/bin/env python3
"""Cut objects out of white-background art: background and soft grey ground shadows become
transparent, then each separate object is saved on its own (left to right).

    python3 art/tools/cutout_white.py IN.png OUT_PREFIX [--names a,b,c] [--split N] [--keep-shadow]

Background = near-white pixels connected to the image border. Shadow = light, colourless grey
connected to that background (outlined art keeps its interior safe). Needs Pillow, numpy, OpenCV.
"""
import argparse
import numpy as np
import cv2
from PIL import Image


def background_mask(rgb, keep_shadow):
    a = rgb.astype(int)
    mn, mx = a.min(axis=2), a.max(axis=2)
    seed = (mn >= 236)
    if not keep_shadow:
        seed |= (mn >= 150) & (mx - mn <= 24)          # pale, nearly colourless grey: ground shadow
    n, lab = cv2.connectedComponents(seed.astype(np.uint8), connectivity=4)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    return np.isin(lab, list(edge))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('prefix')
    ap.add_argument('--names', default=''); ap.add_argument('--keep-shadow', action='store_true')
    ap.add_argument('--min-area', type=int, default=4000)
    ap.add_argument('--split', type=int, default=0, help='cut into N objects at the emptiest columns (touching figures)')
    ap.add_argument('--join', type=int, default=25, help='px gap closed when grouping pieces')
    a = ap.parse_args()
    rgb = np.asarray(Image.open(a.src).convert('RGB'))
    bg = background_mask(rgb, a.keep_shadow)
    alpha = np.where(bg, 0, 255).astype(np.uint8)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    # group pieces that belong together (a suitcase beside its owner) by closing small gaps
    if a.split > 1:
        col = cv2.GaussianBlur((alpha > 0).sum(axis=0).astype(np.float32)[None], (0, 0), 6)[0]
        xs_any = np.where(col > 0)[0]
        lo, hi = xs_any.min(), xs_any.max()
        cuts = []
        for k in range(1, a.split):                         # emptiest column near each even split point
            c = lo + (hi - lo) * k // a.split
            w = (hi - lo) // (2 * a.split)
            cuts.append(c - w + int(np.argmin(col[c - w:c + w])))
        edges = [0] + cuts + [alpha.shape[1]]
        lab = np.zeros(alpha.shape, np.int32)
        for k in range(a.split):
            lab[:, edges[k]:edges[k + 1]] = k + 1
        lab[alpha == 0] = 0
        parts = list(range(1, a.split + 1))
    else:
        joined = cv2.dilate(alpha, np.ones((a.join, a.join), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats((joined > 0).astype(np.uint8))
        parts = sorted([i for i in range(1, n) if st[i][4] >= a.min_area], key=lambda i: st[i][0])
    names = [s for s in a.names.split(',') if s] or ['part%d' % k for k in range(len(parts))]
    soft = cv2.GaussianBlur(alpha, (0, 0), 0.7)
    for k, i in enumerate(parts):
        sel = (lab == i)
        part_alpha = np.where(sel, soft, 0).astype(np.uint8)
        ys, xs = np.where(part_alpha > 8)
        x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        out = np.dstack([rgb, part_alpha])[y0:y1, x0:x1]
        name = names[k] if k < len(names) else 'part%d' % k
        Image.fromarray(out).save('%s_%s.png' % (a.prefix, name), optimize=True)
        print('%s_%s.png %dx%d' % (a.prefix, name, x1 - x0, y1 - y0))


if __name__ == '__main__':
    main()
