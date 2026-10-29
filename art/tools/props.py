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
    return (g > r - 12) & (g > b + 40) & (r < 215)


def piece(walk, poly, kind, cloth=None, paw=False):
    """paw=True keeps the paw holding it (a hand-held prop moves with its paw); the clothes are always left behind
    when cloth is given"""
    m = np.zeros(walk.shape[:2], np.uint8)
    cv2.fillPoly(m, [np.int32(poly)], 1)
    keep = (m > 0) & (walk[..., 3] > 0)
    if not paw:
        keep &= ~skin(walk[..., :3], kind)
    if cloth is not None:
        keep &= ~cloth(walk[..., :3], kind)
    if paw:                  # only the prop and the paw with their own outline: no stray bits of the sleeve's line
        lum = walk[..., :3].mean(-1)
        core = keep & (lum >= 45)
        if kind == 'tiger':  # the hood string's white tip beside the phone is not part of it
            r_, g_ = walk[..., 0], walk[..., 1]
            keep &= ~((walk[..., :3].mean(-1) > 125) & (r_ - g_ < 50))   # the phone is dark, the paw orange: the string's
            # beige tip (light, not orange) stays behind
            core &= keep
        n, lab, st, _ = cv2.connectedComponentsWithStats(core.astype(np.uint8), connectivity=8)
        core = np.isin(lab, [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 30])
        keep &= cv2.dilate(core.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    n, lab, st, _ = cv2.connectedComponentsWithStats(keep.astype(np.uint8), connectivity=8)
    big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    keep = lab == big
    a = walk * keep[..., None]
    ys, xs = np.nonzero(keep)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1], (xs.min(), ys.min())


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


def clean(q):
    """binary alpha, inner pinholes painted from around them, only the biggest piece (no islands)"""
    q = q.copy()
    q[..., 3] = np.where(q[..., 3] > 110, 255, 0)
    n, lab, st, _ = cv2.connectedComponentsWithStats((q[..., 3] > 0).astype(np.uint8), connectivity=8)
    if n > 2:
        q[lab != 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))] = 0
    ff = np.pad((q[..., 3] > 0).astype(np.uint8), 1)
    cv2.floodFill(ff, np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8), (0, 0), 1)
    hole = ff[1:-1, 1:-1] == 0
    if hole.any():
        q[..., :3] = cv2.inpaint(q[..., :3].clip(0, 255).astype(np.uint8), hole.astype(np.uint8), 2, cv2.INPAINT_TELEA)
        q[hole, 3] = 255
    return q


def carry(a, ax, ay, hp, pieces, kind):
    """hp: {'l': (x, y), 'r': (x, y), 'c': (x, y)} paw points of the picture ('c': the middle, where both paws meet
    for a hand-over). pieces: [(name, side, rgba, info)]:
    - a hand-held prop ('phone', 'ticket') is cut WITH the walk frame's paw that holds it; info = grip (x, y) in the
      piece: it is drawn IN FRONT of the figure with the grip on the paw point, so prop and paw move together;
    - 'case': info = degrees that stand it upright; drawn BEHIND the figure on the floor, its handle (top corner on the
      paw's side) under the paw.
    Returns (array, ax, ay, zone, metrics): metrics {name: (gap px from the prop to the paw, pieces of the prop)}."""
    floor = np.nonzero((a[..., 3] > 128).any(1))[0].max()
    back, front = [], []
    for name, side, p, info in pieces:
        if side not in hp:
            continue
        hx, hy = hp[side]
        if name == 'case':
            q = clean(rotate(p, info))
            h, w = q.shape[:2]
            cols = np.nonzero(q[:max(3, h // 8), :, 3].any(0))[0]        # the handle: the top rows
            tx = cols.mean()
            back.append((name, q, int(round(hx - tx)), int(floor - h + 1)))
        else:
            q = clean(p)
            gx, gy = info
            front.append((name, q, int(round(hx - gx)), int(round(hy - gy))))
    layers = back + front
    if not layers:
        return a, ax, ay, np.zeros(a.shape[:2], bool), {}
    X0 = min([0] + [x for _, _, x, _ in layers])
    Y0 = min([0] + [y for _, _, _, y in layers])
    X1 = max([a.shape[1]] + [x + q.shape[1] for _, q, x, _ in layers])
    Y1 = max([a.shape[0]] + [y + q.shape[0] for _, q, _, y in layers])
    H, W = Y1 - Y0, X1 - X0
    out = np.zeros((H, W, 4), np.float32)
    zone = np.zeros((H, W), bool)
    masks = {}

    def over(dst, src):
        k = src[..., 3:] / 255.
        dst[..., :3] = src[..., :3] * k + dst[..., :3] * (1 - k)
        dst[..., 3] = src[..., 3] + dst[..., 3] * (1 - k[..., 0])

    def lay(name, q, x, y):
        t = np.zeros((H, W, 4), np.float32)
        t[y - Y0:y - Y0 + q.shape[0], x - X0:x - X0 + q.shape[1]] = q
        masks[name] = t[..., 3] > 0
        return t
    for name, q, x, y in back:
        over(out, lay(name, q, x, y))
    fig = np.zeros((H, W, 4), np.float32)
    fig[-Y0:-Y0 + a.shape[0], -X0:-X0 + a.shape[1]] = a
    over(out, fig)
    for name, q, x, y in front:
        over(out, lay(name, q, x, y))
    # metrics: the prop's visible px, its pieces, and its gap to the paw (skin px of the figure near the paw point)
    sk = skin(fig[..., :3], kind) & (fig[..., 3] > 128)
    metrics = {}
    for name, side, _, _ in pieces:
        if name not in masks:
            continue
        if name != 'case':
            # a hand-held prop is cut with its paw: the gap is between the prop px and the paw px of the piece itself
            q = dict((n_, q_) for n_, q_, _, _ in front)[name]
            pw = skin(q[..., :3], kind) & (q[..., 3] > 0)
            pr = (q[..., 3] > 0) & ~pw & (q[..., :3].mean(-1) >= 45)
            g_ = float(cv2.distanceTransform((~pw).astype(np.uint8), cv2.DIST_L2, 3)[pr].min()) - 1 if pw.any() and pr.any() else 99.0
            metrics[name] = (max(0.0, g_), cv2.connectedComponents(masks[name].astype(np.uint8), connectivity=8)[0] - 1)
            zone |= masks[name]
            continue
        hx, hy = hp[side][0] - X0, hp[side][1] - Y0
        yy, xx = np.mgrid[:H, :W]
        paw = sk & ((xx - hx) ** 2 + (yy - hy) ** 2 < 14 ** 2) & ~masks[name]
        n = cv2.connectedComponents(masks[name].astype(np.uint8), connectivity=8)[0] - 1   # the prop itself (a suitcase
        # behind a tail or leg can show in two places; that is the figure covering it, not a fragment)
        if paw.any():
            d = cv2.distanceTransform((~paw).astype(np.uint8), cv2.DIST_L2, 3)
            gap = float(d[masks[name]].min()) - 1 if name != 'case' else float(d[masks[name]].min()) - 1
        else:
            gap = 0.0                      # the paw is covered by the prop's own paw (hand-held pieces)
        metrics[name] = (max(0.0, gap), n)
        zone |= masks[name]
    zone = cv2.dilate(zone.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    return out, ax - X0, ay - Y0, zone, metrics


def gold(rgb):
    r, g, b = (rgb[..., i].astype(np.float32) for i in range(3))
    return (r > 100) & (g > 85) & (r - b > 40) & (g - b > 25) & (r - g < 70) & (r > g)


def logo_mask(a, cloth, kind='tiger'):
    """the gold letters on the hoodie (the T2 marks): light gold (r - g 15-55, g - b over 35) next to the garment"""
    r, g, b = (a[..., i].astype(np.float32) for i in range(3))
    m = (r > 120) & (r - g > 10) & (r - g < 60) & (g - b > 28) & (a[..., 3] > 200)
    near = cv2.dilate(cloth(a[..., :3], kind).astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    return m & near


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
    # beside the drawstrings, not under them: the nearest offset (up to 12 px) where no light string px is under a letter
    light = (a[..., :3].min(-1) > 150) & (a[..., 3] > 200)
    for dx in sorted(range(-12, 13), key=abs):
        sub_ = light[Y - 2:Y + h + 2, X + dx - 2:X + dx + W + 2]
        if not sub_.any():
            X += dx
            break
    sub = a[Y:Y + h, X:X + W]
    k = (m[:sub.shape[0], :sub.shape[1]] * (sub[..., 3] > 200) * ~(sub[..., :3].min(-1) > 185))[..., None]   # never over a string
    sub[..., :3] = sub[..., :3] * (1 - k) + p[:sub.shape[0], :sub.shape[1], :3] * k
    return a


def paw_only(p, kind):
    """the paw of a hand-held piece without the prop: skin px and the dark outline around them"""
    sk = skin(p[..., :3], kind) & (p[..., 3] > 128)
    n, lab, st, _ = cv2.connectedComponentsWithStats(sk.astype(np.uint8), connectivity=8)
    if n < 2:
        return p
    sk = lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    near = cv2.dilate(sk.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    keep = (sk | (near & (p[..., :3].mean(-1) < 70))) & (p[..., 3] > 0)
    return p * keep[..., None]


def erase_paw(a, pt, kind):
    """the figure's own paw near pt (read off the view) taken away, for a frame where that paw is in the middle: the
    paw-sized skin blob nearest pt (within 25 px) and its dark outline; a tail or a leg (other blobs) stays"""
    a = a.copy()
    sk = skin(a[..., :3], kind) & (a[..., 3] > 128)
    n, lab, st, cen = cv2.connectedComponentsWithStats(sk.astype(np.uint8), connectivity=8)
    big = 0.04 * (a[..., 3] > 128).sum()           # a leg or the face is bigger than a paw
    cand = [i for i in range(1, n) if 40 <= st[i, cv2.CC_STAT_AREA] < big and np.hypot(*(cen[i] - np.float64(pt))) < 25]
    if not cand:
        return a
    i = min(cand, key=lambda i: np.hypot(*(cen[i] - np.float64(pt))))
    blob = lab == i
    m = blob | (cv2.dilate(blob.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & (a[..., :3].mean(-1) < 70) & ~sk)
    a[m] = 0
    # a paw held in front of the body leaves a hole in the coat: painted from the coat around it
    sol = a[..., 3] > 0
    ff = np.pad(sol.astype(np.uint8), 1)
    cv2.floodFill(ff, np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8), (0, 0), 1)
    hole = (ff[1:-1, 1:-1] == 0)
    n, lab = cv2.connectedComponents(hole.astype(np.uint8), connectivity=4)
    mine = set(np.unique(lab[m & hole])) - {0}           # only holes the erase opened (a paw in front of the coat),
    hole = np.isin(lab, list(mine))                      # not the gaps between arm, body, tail and legs
    if hole.any():
        rgb = cv2.inpaint(a[..., :3].clip(0, 255).astype(np.uint8), cv2.dilate(hole.astype(np.uint8), np.ones((3, 3), np.uint8)), 4, cv2.INPAINT_TELEA)
        a[hole, :3] = rgb[hole]
        a[hole, 3] = 255
    return a
