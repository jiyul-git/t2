"""One upper body (head, hoodie, arms, tail, suitcase) from a base frame + the legs of each frame.
Legs = below the hoodie hem and left of the suitcase (per row, from the base frame).
usage: lockbody.py DIR BASE OUTDIR f1,f2,...   (frames DIR/f_<n>.png, walking left)"""
import sys, os, numpy as np, cv2
from PIL import Image
d, base, outd, names = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split(',')
os.makedirs(outd, exist_ok=True)
def load(n): return np.asarray(Image.open(os.path.join(d, 'f_%s.png' % n)).convert('RGBA')).astype(np.float32)
def hem(a, right):
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    green = (g > r + 5) & (g > b) & (al > 128)
    h = np.full(a.shape[1], -1)
    for x in range(a.shape[1]):
        ys = np.nonzero(green[:, x])[0]
        if len(ys) >= 3: h[x] = ys.max()
    ok = np.nonzero((h > 0) & (np.arange(len(h)) < right))[0]
    hh = np.interp(np.arange(len(h)), ok, h[ok])
    hp = np.pad(hh, 10, mode='edge'); hh = np.array([np.median(hp[i:i + 21]) for i in range(len(hh))])
    hh[:ok.min()] = hh[ok.min()]; hh[ok.max():] = hh[ok.max()]
    hem.end = ok.max()
    return hh.round().astype(int)
def suitcase_left(a):
    """per row: leftmost x of the suitcase (navy body + its outline + handle) in the base frame"""
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    navy = (b > r + 4) & (b >= g) & (al > 128)
    n, lab, st, _ = cv2.connectedComponentsWithStats(navy.astype(np.uint8))
    k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    body = cv2.dilate((lab == k).astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    x0, y0 = st[k, 0], st[k, 1]
    grey = (np.minimum(np.minimum(r, g), b) > 90) & (np.ptp(a[..., :3], axis=2) < 30) & (al > 128)
    handle = grey.copy(); handle[:, :x0 - 30] = False; handle[y0:] = False; handle[:y0 - 70] = False
    m = body | handle
    H, W = m.shape; left = np.full(H, W, float)
    for y in range(H):
        xs = np.nonzero(m[y])[0]
        if len(xs): left[y] = xs.min() - 1
    rows = np.nonzero(left < W)[0]
    left[:rows.min()] = W; left[rows.max():] = left[rows.max()]
    return left.astype(int)
def head_x(a):
    al = a[..., 3] > 128; top = np.nonzero(al.any(1))[0][0]
    return np.nonzero(al[top:top + 120])[1].mean()
def unwhite(a, hm, left):
    """light-grey gap between the pulling arm and the body, left over from the sheet"""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mn = np.minimum(np.minimum(r, g), b); mx = np.maximum(np.maximum(r, g), b)
    yy = np.arange(a.shape[0])[:, None]; xx = np.arange(a.shape[1])[None]
    xl = int(np.median(left[hm - 40:hm]))
    a[(mn > 200) & (mx - mn < 30) & (xx > xl - 60) & (xx < xl + 25) & (yy > hm - 70) & (yy < hm + 25)] = 0

B = load(base); H, W = B.shape[:2]
left = suitcase_left(B); hb = hem(B, int(np.median(left)))
unwhite(B, int(np.median(hb)), left)
pad = 40
yy = np.arange(H + pad)[:, None]; xx = np.arange(W)[None]
hbp = hb[None]; lp = np.concatenate([left, np.full(pad, left[-1])])[:, None]
hoodie_end = hem.end
region = (yy > hbp + 3) & (xx < lp) & ((xx < hoodie_end) | (yy > hbp + 45))   # past the hoodie only the feet rows: the hand stays                       # the legs, in canvas coords
# the pulling hand sits under the sleeve cuff: keep the base's hand (orange + its outline)
rB, gB, bB = B[..., 0], B[..., 1], B[..., 2]
orange = (rB > 150) & (bB < 140) & (rB > bB + 50) & (B[..., 3] > 0)
zone = (xx[:, :W] > hoodie_end - 70) & (yy[:H] < hbp + 40)
hand = cv2.dilate((orange & zone[:H]).astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
region[:H] &= ~hand
band = region[:H] & (yy[:H] < hbp + 24)
hemB = int(np.median(hb[:int(np.median(left))]))
for k, n in enumerate(names):
    F = load(n); fl = suitcase_left(F); hf = hem(F, int(np.median(fl)))
    dx = int(round(head_x(B) - head_x(F))); dy = hemB - int(np.median(hf[:int(np.median(fl))]))
    canvas = np.zeros((H + pad, W, 4), np.float32)
    Fl = F.copy(); yf = np.arange(F.shape[0])[:, None]
    xf = np.arange(F.shape[1])[None]
    r_, g_, b_ = F[..., 0], F[..., 1], F[..., 2]
    case = ((b_ > r_ + 4) & (b_ >= g_)) | ((np.maximum(np.maximum(r_, g_), b_) < 70) & (r_ < b_ + 6))
    Fl[~(yf > hf[None] - 4) | ((xf >= fl[:, None] - 8) & case)] = 0   # below its hem, minus its own suitcase                          # this frame below its own hem
    sh = np.zeros_like(canvas)
    ys0, ys1 = max(0, -dy), min(F.shape[0], H + pad - dy); xs0, xs1 = max(0, -dx), min(F.shape[1], W - dx)
    sh[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx] = Fl[ys0:ys1, xs0:xs1]
    sh[~region] = 0
    # base underneath, only in a band under the hem: fills the small holes where the two frames disagree
    canvas[:H][band] = B[band]
    a = sh[..., 3:4] / 255.
    canvas[..., :3] = sh[..., :3] * a + canvas[..., :3] * (1 - a); canvas[..., 3:] = np.maximum(canvas[..., 3:], sh[..., 3:])
    up = B.copy(); up[region[:H]] = 0
    a = up[..., 3:4] / 255.
    canvas[:H, :, :3] = up[..., :3] * a + canvas[:H, :, :3] * (1 - a)
    canvas[:H, :, 3:] = np.maximum(canvas[:H, :, 3:], up[..., 3:])
    al = canvas[..., 3] > 0; ys, xs = np.nonzero(al)
    Image.fromarray(canvas.clip(0, 255).astype(np.uint8)).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)).save(os.path.join(outd, 'f_%d.png' % k))
    print(n, 'dx', dx, 'dy', dy)
