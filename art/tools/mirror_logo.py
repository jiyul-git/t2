"""Mirror a frame left<->right but keep the gold 'T2' letters readable: each letter blob on the
green hoodie is flipped back inside its own box. usage: mirror_logo.py IN OUT"""
import sys, numpy as np, cv2
from PIL import Image
im = np.asarray(Image.open(sys.argv[1]).convert('RGBA'))[:, ::-1].copy()
a = im.astype(int); r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
gold = (r > 140) & (g > 100) & (b < 120) & (r - b > 60) & (g - b > 35) & (r - g < 75) & (al > 0)
green = (g > r) & (g > b) & (g < 140) & (al > 0)
near_green = cv2.blur(green.astype(np.float32), (15, 15)) > 0.45
gold &= near_green
blob = cv2.dilate(gold.astype(np.uint8), np.ones((9, 9), np.uint8))
n, lab, st, _ = cv2.connectedComponentsWithStats(blob)
H, W = gold.shape
for k in range(1, n):
    x, y, w, h, area = st[k]
    if gold[lab == k].sum() < H * W * 1.2e-4 or w > W * 0.25: continue
    x0, y0, x1, y1 = max(0, x - 2), max(0, y - 2), min(W, x + w + 2), min(H, y + h + 2)
    box = im[y0:y1, x0:x1]
    m = (lab[y0:y1, x0:x1] == k)
    flipped = box[:, ::-1]; mf = m[:, ::-1]
    # put back: clear the old letters with the surrounding green, then draw the flipped letters
    fill = np.median(box[~m & green[y0:y1, x0:x1]], axis=0) if (~m & green[y0:y1, x0:x1]).any() else None
    if fill is None: continue
    out = box.copy(); out[m] = fill.astype(np.uint8)
    out[mf] = flipped[mf]
    soft = cv2.GaussianBlur((m | mf).astype(np.float32), (3, 3), 0)[..., None]
    im[y0:y1, x0:x1] = (out * soft + box * (1 - soft) * 0 + out * (1 - soft)).astype(np.uint8)
Image.fromarray(im).save(sys.argv[2])
