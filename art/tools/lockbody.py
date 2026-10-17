"""One upper body (head, hoodie, arms, tail, suitcase) from a base frame + the legs of each frame.
usage: lockbody.py DIR BASE OUTDIR f1,f2,...   (frames DIR/f_<n>.png, walking left)

The base frame keeps: everything above its hoodie hem, its suitcase (body + outline), and the block
right of the pulling hand above the suitcase (hand, handle, tail). Everything else below the hem
is legs and comes from each frame, aligned on the head and the hem. Cleanup, so no seam shows:
- each frame contributes only its leg blob (its own suitcase, handle and stray bits are dropped);
- right under the hem the legs may not stick out past the base's hips;
- where a leg is cut by the suitcase or the hip line, the cut edge gets the drawing's outline.
"""
import sys, os, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inkfix import reink, defringe
from PIL import Image

OUTLINE = np.array([34, 24, 20, 255], np.float32)   # the line colour of the drawing
HAND_BLOCK = (218, 286)    # x >= 218 and y < 286 in the base: pulling hand, handle, tail -> base
HIP_ROWS = 22              # rows under the hem where legs stay inside the base's hips


def load(d, n):
    return np.asarray(Image.open(os.path.join(d, 'f_%s.png' % n)).convert('RGBA')).astype(np.float32)


def hem_rows(a, right=215):
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    green = (g > r + 5) & (g > b) & (al > 128)
    W = a.shape[1]
    h = np.full(W, -1)
    for x in range(W):
        ys = np.nonzero(green[:, x])[0]
        if len(ys) >= 3: h[x] = ys.max()
    ok = np.nonzero((h > 0) & (np.arange(W) < right))[0]
    hh = np.interp(np.arange(W), ok, h[ok])
    hp = np.pad(hh, 10, mode='edge')
    hh = np.array([np.median(hp[i:i + 21]) for i in range(W)])
    return hh.round().astype(int), int(np.median(h[ok]))


def navy_mask(a, grow=3):
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    navy = (b > r + 4) & (b >= g) & (al > 128)
    n, lab, st, _ = cv2.connectedComponentsWithStats(navy.astype(np.uint8))
    if n < 2: return np.zeros(navy.shape, bool)
    keep = np.isin(lab, [k for k in range(1, n) if st[k, cv2.CC_STAT_AREA] > 200])
    return cv2.dilate(keep.astype(np.uint8), np.ones((2 * grow + 1, 2 * grow + 1), np.uint8)).astype(bool)


def head_x(a):
    al = a[..., 3] > 128
    top = np.nonzero(al.any(1))[0][0]
    return np.nonzero(al[top:top + 120])[1].mean()


def edge_of(mask):
    m = mask.astype(np.uint8)
    return mask & ~cv2.erode(m, np.ones((3, 3), np.uint8)).astype(bool)


def over(dst, src):                       # premultiplied
    return src + dst * (1 - src[..., 3:] / 255.)


def premul(a):
    p = a.copy(); p[..., :3] *= p[..., 3:] / 255.; return p


def unpremul(p):
    out = p.copy(); al = p[..., 3:]
    out[..., :3] = np.where(al > 0, p[..., :3] * 255. / np.maximum(al, 1e-3), 0)
    return out


def main():
    d, base, outd, names = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split(',')
    os.makedirs(outd, exist_ok=True)
    B = load(d, base)
    H, W = B.shape[:2]
    hb, hemB = hem_rows(B)
    pad = 40
    HH = H + pad
    yy, xx = np.mgrid[0:HH, 0:W]
    hbp = np.concatenate([hb[None].repeat(HH, 0)], 0)
    Bp = np.zeros((HH, W, 4), np.float32); Bp[:H] = B
    keep = (yy <= hbp + 2) | navy_mask(Bp) | ((xx >= HAND_BLOCK[0]) & (yy < HAND_BLOCK[1]))
    region = ~keep
    # legs reach a little under the hoodie so no gap shows along the hem's soft edge
    legzone = (yy > hbp - 4) & ~(navy_mask(Bp) | ((xx >= HAND_BLOCK[0]) & (yy < HAND_BLOCK[1])))
    base_al = Bp[..., 3] > 20
    hips = cv2.dilate(base_al.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    top = premul(Bp); top[region] = 0
    band = premul(Bp); band[~(region & (yy < hbp + 16))] = 0
    for k, n in enumerate(names):
        F = load(d, n)
        hf, hemF = hem_rows(F)
        dx = int(round(head_x(B) - head_x(F))); dy = hemB - hemF
        L = np.zeros((HH, W, 4), np.float32)
        ys0, ys1 = max(0, -dy), min(F.shape[0], HH - dy)
        xs0, xs1 = max(0, -dx), min(F.shape[1], W - dx)
        L[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx] = F[ys0:ys1, xs0:xs1]
        hfp = np.full(W, hemB)                         # the frame's hem, moved like the frame
        L[yy <= hbp - 4] = 0                            # this frame's hoodie stays out (top covers the rest)
        L[navy_mask(L)] = 0                             # and its own suitcase
        before = L[..., 3] > 20
        clip = legzone & ~((yy < hbp + 2 + HIP_ROWS) & ~hips)
        L[~clip] = 0
        a = L[..., 3] > 20
        n_, lab, st, _ = cv2.connectedComponentsWithStats(a.astype(np.uint8), connectivity=8)
        if n_ > 1:
            big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
            L[(lab != big) & (lab > 0)] = 0
            a = lab == big
        # one clean silhouette and outline for the legs; the hem edge is covered by the hoodie
        Lp = reink(premul(L), allow=clip.astype(np.float32), protect=(yy < hbp + 8))
        a = Lp[..., 3] > 20
        # base pants under the hem only fill gaps inside this frame's legs, never widen them
        bnd = band.copy(); bnd[~cv2.erode(a.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)] = 0
        out = over(over(bnd, Lp), top)
        res = defringe(unpremul(out))
        al = res[..., 3] > 0
        ys, xs = np.nonzero(al)
        Image.fromarray(res.clip(0, 255).astype(np.uint8)).crop((0, ys.min(), W, ys.max() + 1)).save(os.path.join(outd, 'f_%d.png' % k))
        print(n, 'dx', dx, 'dy', dy)


if __name__ == '__main__':
    main()
