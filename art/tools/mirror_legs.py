"""Make the 'other leg forward' pose: flip the legs (below the hoodie hem, left of the suitcase)
about the hip centre. Near the waist, pixels the flip leaves empty are filled from the original so
the waistband outline stays whole. usage: mirror_legs.py IN OUT [cx]"""
import sys, numpy as np
from PIL import Image
a = np.asarray(Image.open(sys.argv[1]).convert('RGBA')).astype(np.float32)
cx = float(sys.argv[3]) if len(sys.argv) > 3 else 127.0
H, W = a.shape[:2]
r, g, b, al = [a[..., i] for i in range(4)]
green = (g > r + 5) & (g > b) & (al > 128)
hem = np.array([np.nonzero(green[:, x])[0].max() if green[:, x].sum() >= 3 else -1 for x in range(W)])
hm = int(np.median(hem[(hem > 0) & (np.arange(W) < 215)]))
EDGE = [(0, 218), (262, 218), (285, 230), (305, 243), (H, 258)]
xb = np.interp(np.arange(H), [p[0] for p in EDGE], [p[1] for p in EDGE])
out = a.copy()
for y in range(hm + 2, H):
    lim = int(xb[y])
    src = a[y, :lim].copy()
    flip = np.zeros_like(src)
    xs = np.arange(lim); nx = np.round(2 * cx - xs).astype(int); okx = (nx >= 0) & (nx < lim)
    flip[nx[okx]] = src[xs[okx]]
    if y < hm + 30:                                   # waist: original silhouette, flipped inside
        fill = (flip[:, 3] < 200) & (src[:, 3] > flip[:, 3])
        flip[fill] = src[fill]
        flip[src[:, 3] < 20] = 0
    out[y, :lim] = flip
Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(sys.argv[2])
