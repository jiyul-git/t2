"""Cut an R x C white-background sprite sheet into frames: split at the emptiest rows/columns,
keep each cell's own figure (largest pieces), white bg + pale shadow -> transparent.
usage: cut_sheet.py SHEET OUTDIR [R C]"""
import sys, os, numpy as np, cv2
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cutout_white import background_mask

def cuts(profile, n):
    L = len(profile); out = [0]
    for k in range(1, n):
        c = k * L / n; w = int(L / n * 0.3)
        lo, hi = int(c - w), int(c + w)
        seg = profile[lo:hi]
        best = np.flatnonzero(seg == seg.min())
        out.append(lo + int(best[len(best) // 2]))
    return out + [L]

def main():
    src, outdir = sys.argv[1], sys.argv[2]
    R, C = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (4, 4)
    rgb = np.asarray(Image.open(src).convert('RGB'))
    fg = ~background_mask(rgb, False)
    # warm ground shadows (sat ~25) a little past cutout_white's grey limit, still touching the background
    a = rgb.astype(int); mn = a.min(2)
    seed = (~fg) | ((mn >= 150) & (a.max(2) - mn <= 34))
    n, lab = cv2.connectedComponents(seed.astype(np.uint8), connectivity=4)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    fg &= ~np.isin(lab, list(edge))
    # enclosed white gaps (between arm and body) are background too; tiny eye highlights stay
    a = rgb.astype(int); white = (a.min(2) >= 240) & (a.max(2) - a.min(2) <= 14) & fg
    n, lab, st, _ = cv2.connectedComponentsWithStats(white.astype(np.uint8), connectivity=4)
    minarea = int(rgb.shape[0] * rgb.shape[1] * 2.5e-5)
    for k in range(1, n):
        if st[k, cv2.CC_STAT_AREA] >= minarea: fg[lab == k] = False
    fg = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    os.makedirs(outdir, exist_ok=True)
    ys = cuts(fg.sum(1), R)
    for r in range(R):
        band = fg[ys[r]:ys[r + 1]]
        xs = cuts(band.sum(0), C)
        for c in range(C):
            m = fg[ys[r]:ys[r + 1], xs[c]:xs[c + 1]].astype(np.uint8)
            closed = cv2.dilate(m, np.ones((15, 15), np.uint8))
            n, lab, st, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
            if n < 2: continue
            big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
            keep = (lab == big) & (m > 0)
            # also keep other big pieces (suitcase) not touching the cell border
            for k in range(1, n):
                if k == big: continue
                x, y, w, h, a = st[k]
                border = x == 0 or y == 0 or x + w >= m.shape[1] or y + h >= m.shape[0]
                if a > 0.08 * st[big, cv2.CC_STAT_AREA] and not border:
                    keep |= (lab == k) & (m > 0)
            alpha = cv2.GaussianBlur(keep.astype(np.uint8) * 255, (3, 3), 0)
            alpha[~cv2.dilate(keep.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)] = 0
            cell = rgb[ys[r]:ys[r + 1], xs[c]:xs[c + 1]]
            yy, xx = np.nonzero(keep)
            box = (xx.min(), yy.min(), xx.max() + 1, yy.max() + 1)
            im = Image.fromarray(np.dstack([cell, alpha])).crop(box)
            im.save(os.path.join(outdir, 'f_%d%d.png' % (r, c)))
            touch = []
            if xx.min() == 0: touch.append('L')
            if yy.min() == 0: touch.append('T')
            if xx.max() == m.shape[1] - 1: touch.append('R')
            if yy.max() == m.shape[0] - 1: touch.append('B')
            print('f_%d%d %dx%d %s' % (r, c, im.width, im.height, ''.join(touch) or '-'))

main()
