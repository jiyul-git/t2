"""Mirror a frame left<->right but keep the gold 'T2' letters readable: each letter blob on the
green hoodie is flipped back inside its own box. usage: mirror_logo.py IN OUT [K]   (K: the picture is K times bigger than the 1x sheet; sizes in px scale with it)"""
import sys, numpy as np, cv2
from PIL import Image
NEW = len(sys.argv) > 3          # the K form (build_character.py) uses the better fill below; the plain form is unchanged
K = int(sys.argv[3]) if NEW else 1
im = np.asarray(Image.open(sys.argv[1]).convert('RGBA'))[:, ::-1].copy()
a = im.astype(int); r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
gold = (r > 140) & (g > 100) & (b < 120) & (r - b > 60) & (g - b > 35) & (r - g < 75) & (al > 0)
green = (g > r) & (g > b) & (g < 140) & (al > 0)
near_green = cv2.blur(green.astype(np.float32), (15 * K, 15 * K)) > 0.45
gold &= near_green
blob = cv2.dilate(gold.astype(np.uint8), np.ones((9 * K, 9 * K), np.uint8))
n, lab, st, _ = cv2.connectedComponentsWithStats(blob)
H, W = gold.shape
for k in range(1, n):
    x, y, w, h, area = st[k]
    if gold[lab == k].sum() < H * W * (2e-5 if NEW else 1.2e-4) or w > W * 0.25: continue
    x0, y0, x1, y1 = max(0, x - 2 * K), max(0, y - 2 * K), min(W, x + w + 2 * K), min(H, y + h + 2 * K)
    box = im[y0:y1, x0:x1]
    m = (lab[y0:y1, x0:x1] == k)
    flipped = box[:, ::-1]; mf = m[:, ::-1]
    if not NEW:      # put back: clear the old letters with the surrounding green, then draw the flipped letters
        fill = np.median(box[~m & green[y0:y1, x0:x1]], axis=0) if (~m & green[y0:y1, x0:x1]).any() else None
        if fill is None: continue
        out = box.copy(); out[m] = fill.astype(np.uint8)
        out[mf] = flipped[mf]
        soft = cv2.GaussianBlur((m | mf).astype(np.float32), (3, 3), 0)[..., None]
        im[y0:y1, x0:x1] = (out * soft + box * (1 - soft) * 0 + out * (1 - soft)).astype(np.uint8)
        continue
    # clear the old letters by inpainting them from the cloth around (a flat colour left a visible patch on a shaded sleeve)
    old = cv2.dilate((m & gold[y0:y1, x0:x1]).astype(np.uint8), np.ones((3 * K, 3 * K), np.uint8))
    # (a normalised blur of the cloth pixels around, never of a dark outline, so no line gets pulled in)
    cloth = (green[y0:y1, x0:x1] & (old == 0)).astype(np.float32)
    lumb = box[..., :3].astype(np.float32) @ np.float32([0.3, 0.59, 0.11])
    cloth *= (lumb > 38)
    rgb = box[..., :3].astype(np.float32)
    for sig in (2 * K, 4 * K, 8 * K, 16 * K):
        wsum = cv2.GaussianBlur(cloth, (0, 0), sig)
        col = cv2.GaussianBlur(rgb * cloth[..., None], (0, 0), sig) / np.maximum(wsum[..., None], 1e-4)
        rgb = np.where((old[..., None] > 0) & (wsum[..., None] > 0.05), col, rgb)
    out = box.copy(); out[..., :3] = np.where(old[..., None] > 0, rgb, box[..., :3])
    out[mf] = flipped[mf]
    soft = cv2.GaussianBlur((m | mf).astype(np.float32), (2 * K + 1, 2 * K + 1), 0)[..., None]
    im[y0:y1, x0:x1] = (out * soft + out * (1 - soft)).astype(np.uint8)
Image.fromarray(im).save(sys.argv[2])
