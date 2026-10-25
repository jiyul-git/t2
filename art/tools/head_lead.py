"""Head-leads frames for the turns (art/README.md "돌아서기"): in a real turn the head turns first and the
body follows, so between two views a frame shows the NEXT view's head on the CURRENT view's body.

head_mask(a, kind): the head of a straight-RGBA picture (fur, ears, bow, beanie, eyes and its outline),
    found by colour: everything not ink and not the main garment, in the upper part of the figure. The
    garment is the big connected area of the animal's clothing colour (kind: 'tiger' green hoodie,
    'rabbit' pink coat and scarf, 'turtle' navy jacket and brown shell backpack); thick dark fills (the
    turtle's beanie) count as fill, only thin dark lines are ink.
transplant(body, head_from): the body picture with its own head taken off and the other picture's head put
    on, meeting at the neck point (bottom middle of the head), drawn over the collar / scarf / hood, which
    hides the seam. Garment px the old head covered and the new one does not are inpainted from the
    garment around them. Returns (array, dx, dy): where the body's (0, 0) went in the new array.
"""
import cv2
import numpy as np


def cloth(rgb, kind):
    r, g, b = (rgb[..., i].astype(np.float32) for i in range(3))
    lum = rgb.astype(np.float32).mean(-1)
    if kind == 'tiger':
        return (g > r + 4) & (g >= b - 4)
    if kind == 'rabbit':
        return (r > 140) & (r - g > 38)
    return ((b > r + 12) & (lum < 100)) | ((r > g) & (g > b) & (r - b > 35) & (lum < 150) & (lum > 40))


def fill_holes(m):
    ff = np.pad(m.astype(np.uint8), 1)
    seed = np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8)
    cv2.floodFill(ff, seed, (0, 0), 1)
    return m | (ff[1:-1, 1:-1] == 0)


def head_mask(a, kind, cut=None):
    al = a[..., 3] > 128
    rgb = a[..., :3]
    dark = rgb.astype(np.float32).mean(-1) < 26
    thick = cv2.morphologyEx(dark.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))).astype(bool)
    ink = dark & ~thick
    ys = np.nonzero(al.any(1))[0]
    top, H = ys.min(), ys.max() - ys.min()
    cl = cloth(rgb, kind) & al
    n, lab, st, cen = cv2.connectedComponentsWithStats(cl.astype(np.uint8), connectivity=8)
    garment = np.zeros_like(al)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] > 0.012 * al.sum() and cen[i][1] > top + 0.4 * H:
            garment |= lab == i
    free = al & ~ink & ~garment
    free[int(top + (cut or 0.6) * H):] = False             # cut: a lower limit for one picture (a cup under the chin)
    n, lab, st, cen = cv2.connectedComponentsWithStats(free.astype(np.uint8), connectivity=4)
    cand = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 0.004 * al.sum() and cen[i][1] < top + 0.45 * H]
    face = max(cand, key=lambda i: st[i, cv2.CC_STAT_AREA])          # the face / skull: the biggest piece
    head = np.zeros_like(al)
    for i in cand:
        # ears, bow, beanie: above the face's middle (eyes, nose, stripes are holes in the face, filled below).
        # A hand holding a phone beside the cheek is not
        if i == face or cen[i][1] < cen[face][1]:
            head |= lab == i
    head = fill_holes(head)
    # thin bits hanging off (a hood string, a strip of hood rim) are not head
    head = cv2.morphologyEx(head.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))).astype(bool)
    n, lab, st, _ = cv2.connectedComponentsWithStats(head.astype(np.uint8), connectivity=8)
    keep = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 0.004 * al.sum()]
    head = np.isin(lab, keep)
    head |= cv2.dilate(head.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool) & ink & al
    head = cv2.morphologyEx(head.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)).astype(bool) & al
    if cut:
        # a forced cut is a chin, not a ruler line: lowest in the middle, rising toward the cheeks
        ys_, xs_ = np.nonzero(head)
        cx, hw = (xs_.min() + xs_.max()) / 2, (xs_.max() - xs_.min()) / 2
        yy, xx = np.mgrid[:head.shape[0], :head.shape[1]]
        head &= yy < top + cut * H - 0.06 * H * ((xx - cx) / hw) ** 2
    return head


def neck(m):
    """bottom middle of a head mask: the lowest row, x = middle of the lowest 12 % of the head"""
    ys, xs = np.nonzero(m)
    y1 = ys.max()
    sel = ys >= y1 - 0.12 * (y1 - ys.min())
    return float(xs[sel].mean()), float(y1)


def seal(a, m):
    """close the head's outline where the mask cuts through colour (under a chin hidden by a cup): the edge px of
    the mask that are not ink, and the px just inside them, take the head's own line colour"""
    a = a.copy()
    lum = a[..., :3].mean(-1)
    pad = np.pad(~m, 1, constant_values=True)
    edge = m & (pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:])
    line = np.median(a[edge & (lum < 60)][:, :3], 0)
    cut = edge & (lum >= 90)
    cut |= cv2.dilate(cut.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & m & (lum >= 90)
    a[cut, :3] = line
    return a


def transplant(body, head_from, kind, cut_body=None, cut_head=None):
    hb, hd = head_mask(body, kind, cut_body), head_mask(head_from, kind, cut_head)
    (bx, by), (dx_, dy_) = neck(hb), neck(hd)
    ox, oy = int(round(bx - dx_)), int(round(by - dy_))           # head_from px -> body px, necks together
    # then the offset (within 40 px across, 14 up or down) where the new head covers the old one best: least garment left open,
    # least new head hanging over the shoulders
    ys, xs = np.nonzero(hd)
    best = None
    for ddy in range(-14, 15, 2):
        for ddx in range(-40, 41, 2):
            y2, x2 = ys + oy + ddy, xs + ox + ddx
            ok = (y2 >= 0) & (y2 < hb.shape[0]) & (x2 >= 0) & (x2 < hb.shape[1])
            inter = hb[y2[ok], x2[ok]].sum()
            score = inter / (hb.sum() + len(ys) - inter) - 0.0005 * (abs(ddx) + abs(ddy))
            if best is None or score > best[0]:
                best = (score, ddx, ddy)
    ox, oy = ox + best[1], oy + best[2]
    # canvas holding both
    x0, y0 = min(0, ox), min(0, oy)
    x1 = max(body.shape[1], ox + head_from.shape[1])
    y1 = max(body.shape[0], oy + head_from.shape[0])
    W, H = x1 - x0, y1 - y0
    out = np.zeros((H, W, 4), np.float32)
    out[-y0:-y0 + body.shape[0], -x0:-x0 + body.shape[1]] = body
    old = np.zeros((H, W), bool)
    old[-y0:-y0 + body.shape[0], -x0:-x0 + body.shape[1]] = hb
    out[old] = 0                                                   # the body's own head off, with its faint rim
    ring = cv2.dilate(old.astype(np.uint8), np.ones((11, 11), np.uint8)).astype(bool)
    lum = out[..., :3].mean(-1)
    rim = ring & ((out[..., 3] <= 128) | ((lum < 90) & ~cloth(out[..., :3], kind)))
    out[rim] = 0
    old |= rim
    lay = np.zeros((H, W, 4), np.float32)
    lay[oy - y0:oy - y0 + head_from.shape[0], ox - x0:ox - x0 + head_from.shape[1]] = seal(head_from, hd) * hd[..., None]
    # the new head comes with its own collar: the head_from garment (its colour only: no strings, phone or seams)
    # within D px of its head, faded into the
    # body's garment over the outer part of that band (so a cheek its own hood hid is not left open)
    full = np.zeros((H, W, 4), np.float32)
    full[oy - y0:oy - y0 + head_from.shape[0], ox - x0:ox - x0 + head_from.shape[1]] = head_from
    hn = lay[..., 3] > 0
    rows = np.nonzero(((out[..., 3] > 0) | hn).any(1))[0]
    D = 0.07 * (rows.max() - rows.min() + 1)                      # 7 % of the figure's height
    dist = cv2.distanceTransform((~hn).astype(np.uint8), cv2.DIST_L2, 5)
    _, ny = neck(hn)
    yy = np.mgrid[:H, :W][0]
    band = (dist > 0) & (dist < D) & (full[..., 3] > 128) & cloth(full[..., :3], kind) & (yy > ny - 0.5 * D - 0.35 * (ny - np.nonzero(hn)[0].min()))
    wgt = np.clip((D - dist) / (0.5 * D), 0, 1) * band
    body_on = out[..., 3] > 128
    wgt = np.where(body_on, wgt, (wgt >= 1) * band)
    lay[band] = full[band]
    lay[..., 3] *= np.where(band, wgt, 1)
    new = lay[..., 3] > 0
    k = lay[..., 3:] / 255.
    out[..., :3] = lay[..., :3] * k + out[..., :3] * (1 - k) * (out[..., 3:] > 0)
    out[..., :3] = np.where(out[..., 3:] > 0, out[..., :3], lay[..., :3])
    out[..., 3] = np.maximum(out[..., 3], lay[..., 3])
    # garment the old head covered and the new one leaves open: first the new head's own collar (the head_from
    # picture just below its head, same offset), what is still open takes the colour of the nearest garment px
    sil = out[..., 3] > 128
    closed = fill_holes(cv2.morphologyEx(sil.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)).astype(bool))
    gap = closed & ~sil & cv2.dilate(old.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & ~new
    own = gap & (full[..., 3] > 128)
    out[own] = full[own]
    gap &= ~own
    if gap.any():
        src = (out[..., 3] > 250) & cloth(out[..., :3], kind) & ~gap
        if src.any():
            _, lab = cv2.distanceTransformWithLabels((~src).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
            ys, xs = np.nonzero(src)
            idx = np.zeros(lab.max() + 1, np.int64)
            idx[lab[ys, xs]] = np.arange(len(ys))
            g = idx[lab[gap]]
            out[gap, :3] = out[ys[g], xs[g], :3]
            out[gap, 3] = 255
    zone = cv2.dilate((old | new | gap | own).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    # slivers 1-2 px wide left around the neck (bits of the old outline) go
    solid = out[..., 3] > 0
    opened = cv2.morphologyEx(solid.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    out[zone & solid & ~opened & ~(lay[..., 3] > 0)] = 0
    # and pieces no longer joined to the figure (old ear tips above the new head)
    n, lab, st, _ = cv2.connectedComponentsWithStats((out[..., 3] > 0).astype(np.uint8), connectivity=8)
    if n > 2:
        big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        for i in range(1, n):
            if i != big and st[i, cv2.CC_STAT_AREA] < 0.02 * st[big, cv2.CC_STAT_AREA]:
                out[lab == i] = 0
    return out, -x0, -y0, zone
