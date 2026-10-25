"""Props through the turns (art/README.md "돌아서기"): the suitcase / phone / ticket the character carries while
walking stays with it on the turnaround views, in the same hand as in the walk frame next to them.

piece(walk, poly, kind): the prop cut from the walk picture (straight RGBA, atlas px): the px inside a hand-drawn
    polygon that are not skin / fur (the walking paw stays behind), cropped.
hands(a, kind, cloth): a guess at the paws (skin blobs beside the garment above its hem); not used by the builder,
    whose paw points are read off the 8x grids by hand (tails and feet fooled it).
carry(a, pieces): the picture with each prop drawn BEHIND it, so the view's own paw holds it:
    'phone' / 'ticket' upright, hanging from the paw on its outer side; 'case' stood upright on the floor (the
    picture's bottom row) beside the paw, its near edge under the paw.
"""
import cv2
import numpy as np


def skin(rgb, kind):
    r, g, b = (rgb[..., i].astype(np.float32) for i in range(3))
    if kind == 'tiger':
        return (r > 150) & (r - b > 60) & (r > g)
    if kind == 'rabbit':
        return (r > 205) & (g > 175) & (b > 150) & (r - b < 70)
    return (g > r + 5) & (g > b + 25)


def piece(walk, poly, kind, cloth=None):
    m = np.zeros(walk.shape[:2], np.uint8)
    cv2.fillPoly(m, [np.int32(poly)], 1)
    keep = (m > 0) & (walk[..., 3] > 0) & ~skin(walk[..., :3], kind)
    if cloth is not None:                      # a small prop held against the clothes: leave the clothes behind
        keep &= ~cloth(walk[..., :3], kind)
    n, lab, st, _ = cv2.connectedComponentsWithStats(keep.astype(np.uint8), connectivity=8)
    big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    keep = lab == big
    a = walk * keep[..., None]
    ys, xs = np.nonzero(keep)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def rotate(a, ang):
    h, w = a.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    c, s = abs(M[0, 0]), abs(M[0, 1])
    W, H = int(h * s + w * c) + 2, int(h * c + w * s) + 2
    M[0, 2] += W / 2 - w / 2
    M[1, 2] += H / 2 - h / 2
    p = a.copy()
    p[..., :3] *= p[..., 3:] / 255.
    r = cv2.warpAffine(p, M, (W, H), flags=cv2.INTER_CUBIC, borderValue=0)
    r[..., 3] = r[..., 3].clip(0, 255)
    r[..., :3] = np.where(r[..., 3:] > 0, r[..., :3] * 255. / np.maximum(r[..., 3:], 1e-3), 0)
    ys, xs = np.nonzero(r[..., 3] > 8)
    return r[ys.min():ys.max() + 1, xs.min():xs.max() + 1].clip(0, 255)


def hands(a, kind, cloth):
    al = a[..., 3] > 128
    gm = cloth(a[..., :3], kind) & al
    ys, xs = np.nonzero(al)
    top, bot = ys.min(), ys.max()
    H = bot - top
    gy, gx = np.nonzero(gm)
    rows = gy[gy > top + 0.3 * H]
    hem = np.percentile(rows, 99)
    x0, x1 = gx.min(), gx.max()
    win = np.zeros_like(al)
    win[int(hem - 0.3 * H):int(hem + 0.04 * H), max(0, x0 - 8):x1 + 9] = True
    cand = skin(a[..., :3], kind) & al & win
    n, lab, st, cen = cv2.connectedComponentsWithStats(cand.astype(np.uint8), connectivity=8)
    mid = (x0 + x1) / 2
    out = {}
    for side, test in (('l', lambda c: c < mid - 0.2 * (x1 - x0)), ('r', lambda c: c > mid + 0.2 * (x1 - x0))):
        # paws come out of the sleeves above the hem (legs and feet are below it): the outermost blob
        ids = [i for i in range(1, n) if test(cen[i][0]) and st[i, cv2.CC_STAT_AREA] > 12 and cen[i][1] < hem + 0.02 * H]
        if ids:
            i = max(ids, key=lambda i: abs(cen[i][0] - mid))
            py, px = np.nonzero(lab == i)
            out[side] = (float(px.mean()), float(py.max()))
    return out


def carry(a, ax, ay, hp, pieces):
    """hp: {'l': (x, y), 'r': (x, y)} paw points (bottom middle) of the picture; pieces: [(name, side 'l'/'r', rgba,
    degrees that turn it upright)]. Returns (array, ax, ay, zone)."""
    floor = np.nonzero((a[..., 3] > 128).any(1))[0].max()
    layers = []
    for name, side, p, ang in pieces:
        if side not in hp:
            continue
        hx, hy = hp[side]
        q = rotate(p, ang)
        q[..., 3] = np.where(q[..., 3] > 110, 255, 0)      # a clean cut edge (finish_edges inks it)
        solid = q[..., 3] > 0                               # pinholes inside the piece: painted from around them
        ff = np.pad(solid.astype(np.uint8), 1)
        cv2.floodFill(ff, np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8), (0, 0), 1)
        hole = (ff[1:-1, 1:-1] == 0)
        if hole.any():
            q[..., :3] = cv2.inpaint(q[..., :3].clip(0, 255).astype(np.uint8), hole.astype(np.uint8), 2, cv2.INPAINT_TELEA)
            q[hole, 3] = 255
        h, w = q.shape[:2]
        out_ = -1 if side == 'l' else 1                     # away from the body
        if name == 'case':
            y0 = floor - h + 1
            x0 = hx - w + 0.25 * w if side == 'l' else hx - 0.25 * w
        else:                                               # hanging from the paw, outside the silhouette
            y0 = hy - 0.45 * h
            x0 = hx - w / 2 + out_ * 0.45 * w
        layers.append((q, int(round(x0)), int(round(y0))))
    if not layers:
        return a, ax, ay, np.zeros(a.shape[:2], bool)
    X0 = min([0] + [x for _, x, _ in layers])
    Y0 = min([0] + [y for _, _, y in layers])
    X1 = max([a.shape[1]] + [x + q.shape[1] for q, x, _ in layers])
    Y1 = max([a.shape[0]] + [y + q.shape[0] for q, _, y in layers])
    out = np.zeros((Y1 - Y0, X1 - X0, 4), np.float32)
    zone = np.zeros(out.shape[:2], bool)
    for q, x, y in layers:
        sl = (slice(y - Y0, y - Y0 + q.shape[0]), slice(x - X0, x - X0 + q.shape[1]))
        k = q[..., 3:] / 255.
        out[sl][..., :3] = q[..., :3] * k + out[sl][..., :3] * (1 - k)
        out[sl][..., 3] = np.maximum(out[sl][..., 3], q[..., 3])
        zone[sl] |= q[..., 3] > 0
    fig = np.zeros_like(out)
    fig[-Y0:-Y0 + a.shape[0], -X0:-X0 + a.shape[1]] = a
    k = fig[..., 3:] / 255.
    out[..., :3] = fig[..., :3] * k + out[..., :3] * (1 - k)
    out[..., 3] = fig[..., 3] + out[..., 3] * (1 - k[..., 0])
    zone = cv2.dilate(zone.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    return out, ax - X0, ay - Y0, zone


def gold(rgb):
    r, g, b = (rgb[..., i].astype(np.float32) for i in range(3))
    return (r > 100) & (g > 85) & (r - b > 40) & (g - b > 25) & (r - g < 70) & (r > g)


def emblem(a, walk, box, cloth, kind, wx=0.85):
    """the chest mark of a view replaced by the walk frame's (box: x0, y0, x1, y1 of it in walk px): the view's own
    gold mark (the biggest gold blob on the garment, upper half) is painted over with the garment colour around it,
    and the walk frame's gold letters (squeezed to wx for the turned chest) are put at its centre."""
    a = a.copy()
    op = a[..., 3] > 200
    ys = np.nonzero(op.any(1))[0]
    near = cv2.dilate(cloth(a[..., :3], kind).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    g = gold(a[..., :3]) & op & near & ~skin(a[..., :3], kind)
    g &= ~(a[..., :3].min(-1) > 150)                  # cream face / fur is not gold
    g[int(ys.min() + 0.62 * (ys.max() - ys.min())):] = False
    n, lab, st, cen = cv2.connectedComponentsWithStats(cv2.dilate(g.astype(np.uint8), np.ones((3, 3), np.uint8)), connectivity=8)
    if n < 2:
        return a
    i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    old = cv2.dilate((lab == i).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & op
    ring = cv2.dilate(old.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool) & ~old & cloth(a[..., :3], kind)
    a[old, :3] = np.median(a[ring][:, :3], 0)
    cx, cy = cen[i]
    x0, y0, x1, y1 = box
    p = walk[y0:y1, x0:x1].copy()
    m = (gold(p[..., :3]) & (p[..., 3] > 200)).astype(np.float32)
    m = cv2.GaussianBlur(m, (3, 3), 0.6)
    h, w = p.shape[:2]
    W = max(1, int(round(w * wx)))
    p = cv2.resize(p, (W, h), interpolation=cv2.INTER_AREA)
    m = cv2.resize(m, (W, h), interpolation=cv2.INTER_AREA)
    X, Y = int(round(cx - W / 2)), int(round(cy - h / 2))
    sub = a[Y:Y + h, X:X + W]
    k = (m[:sub.shape[0], :sub.shape[1]] * (sub[..., 3] > 200) * cloth(sub[..., :3], kind))[..., None]   # never over a string
    sub[..., :3] = sub[..., :3] * (1 - k) + p[:sub.shape[0], :sub.shape[1], :3] * k
    return a
