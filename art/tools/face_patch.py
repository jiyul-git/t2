#!/usr/bin/env python3
"""Face variants (blink, smile, laugh) for the walkers, from the Gemini face sheets (art/README.md).

The upper body of a walker is one locked base for every loop frame, so a face change is the same
small patch on every frame. A variant is made on one base frame at working resolution:

1. erase: the base's open eyes (and for a laugh its mouth) are painted over with the surrounding
   skin (ellipses in base px, inpainted and softened, feathered at the edge);
2. features: each donor feature (one eye, the mouth) is cut out of its donor cell by matting it
   against the skin colour around it (so only the line/mouth comes along, never the donor's skin or
   a pale halo), scaled, and placed with its centre on the given base point. Eyes are placed one by
   one on the base's own eye positions rather than by registering the whole head: Gemini draws the
   head of every cell a little differently (rounder, more frontal), and the eyes are what must land
   right. Lines are drawn in the base's line colour so the weight and colour match;
3. the builders run the patched frame through the same resize/mirror as the plain frames and keep only
   the pixels that differ (patch_of), stored once per direction in the atlas.

    python3 art/tools/face_patch.py tiger --preview OUT.png    # base + every variant side by side, zoomed
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
LINE = np.float32([34, 24, 20])          # the drawings' line colour (inkfix.LINE)


# ---------------------------------------------------------------- donors
def donor_cell(sheet, cell, upscale=1, flip=False):
    """One cell of a 4x4 donor sheet, cut like cut_sheet.py (straight RGBA float)."""
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = ROOT / sheet
        extra = []
        if upscale == 4:                      # super-resolved donor (sr_upscale.py): cut 4x like the base cells
            import sr_upscale
            im = sr_upscale.upscale(src)
            if im is not None:
                p4 = tmp / 'sr4.png'; im.save(p4, compress_level=1)
                extra = [str(p4)]
            else:
                upscale = 2
        if upscale != 1 and not extra:
            im = Image.open(src).convert('RGB')
            im = im.resize((im.width * upscale, im.height * upscale), Image.LANCZOS)
            src = tmp / 'sheet.png'; im.save(src)
        subprocess.run([sys.executable, '-I', str(TOOLS / 'cut_sheet.py'), str(src), str(tmp / 'cells'), '4', '4'] + extra,
                       check=True, stdout=subprocess.DEVNULL)
        im = Image.open(tmp / 'cells' / ('f_%s.png' % cell)).convert('RGBA')
    if flip:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return np.asarray(im).astype(np.float32)


def matte(cell, box, dark=(150, 55), keep_color=False, line=LINE):
    """The feature inside box (x0, y0, x1, y1) of a donor cell, as a premultiplied RGBA layer the size
    of the box. A line (an eye) is what is truly dark: alpha from the luminance between dark[0] (none)
    and dark[1] (full), so orange fur, a cream patch's edge or soft shading never come along, and it is
    drawn in the line colour. keep_color=True (a mouth): the dark outline plus everything it encloses
    (tongue, inside of the mouth) in its own colours. Only pieces that reach the middle of the box are
    kept, so a bit of a neighbouring line cut by the box edge does not come along."""
    x0, y0, x1, y1 = box
    P = cell[y0:y1, x0:x1].copy()
    rgb = P[..., :3]
    lum = rgb @ np.float32([0.3, 0.59, 0.11])
    a = np.clip((dark[0] - lum) / (dark[0] - dark[1]), 0, 1)
    a[P[..., 3] < 128] = 0
    h, w = a.shape
    if keep_color:
        red = (rgb[..., 0] - rgb[..., 1] > 45) & (rgb[..., 0] > 120)
        core = ((a > 0.4) | red).astype(np.uint8)
        core = cv2.morphologyEx(core, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        # what the outline encloses: the background pieces that do not touch the box's border
        n0, lab0 = cv2.connectedComponents((1 - core).astype(np.uint8), connectivity=4)
        border = set(np.unique(np.concatenate([lab0[0], lab0[-1], lab0[:, 0], lab0[:, -1]])))
        filled = (core | ~np.isin(lab0, list(border))).astype(np.uint8)
    else:
        filled = (a > 0.35).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(filled, connectivity=8)
    keep = np.zeros((h, w), bool)
    for k in range(1, n):
        cx, cy = st[k, 0] + st[k, 2] / 2, st[k, 1] + st[k, 3] / 2
        if st[k, cv2.CC_STAT_AREA] >= 3 and w * 0.2 <= cx <= w * 0.8 and h * 0.15 <= cy <= h * 0.85:
            keep |= lab == k
    if keep_color:          # the whole mouth in its own colours, with a 1 px soft edge of the donor's skin
        a = np.clip(cv2.GaussianBlur(keep.astype(np.float32), (0, 0), 0.8) * 2.0, 0, 1)
        a = np.maximum(a, keep)
        col = rgb
    else:
        a = a * cv2.dilate(keep.astype(np.uint8), np.ones((3, 3), np.uint8))
        col = np.broadcast_to(line, rgb.shape)
    out = np.zeros(P.shape, np.float32)
    out[..., :3] = col * a[..., None]
    out[..., 3] = a * 255
    return out


def place(layer, center_src, center_dst, scale, shape, flip_v=False, angle=0.0):
    """Warp a premultiplied feature layer so center_src (in the layer) lands on center_dst, scaled."""
    sy = -scale if flip_v else scale
    c, s = np.cos(np.radians(angle)), np.sin(np.radians(angle))
    A = np.float32([[scale * c, -sy * s], [scale * s, sy * c]])
    t = np.float32(center_dst) - A @ np.float32(center_src)
    M = np.hstack([A, t[:, None]])
    out = cv2.warpAffine(layer, M, (shape[1], shape[0]), flags=cv2.INTER_CUBIC,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    out = out.clip(0, 255)
    out[..., :3] = np.minimum(out[..., :3], out[..., 3:])
    return out


def centroid(layer):
    a = layer[..., 3]
    ys, xs = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    t = a.sum()
    return (float((xs * a).sum() / t), float((ys * a).sum() / t))


# ---------------------------------------------------------------- base
def erase(img, ellipses, feather=1.8, protect_px=6, line_w=3.0, k=1, kern=None):
    """Erase the ellipses one by one (each with the skin around it), see erase_one. k: the picture is k
    times bigger than the source px the ellipses are given in (a super-resolved sheet)."""
    for e in ellipses:
        img = erase_one(img, [scaled_ellipse(e, k)], feather, protect_px, line_w, kern or k)
    return img


def scaled_ellipse(e, k):
    """An erase entry (tuple or dict, see erase_one) with its px values times k (the caller's coordinates
    are in source px, the picture is k times bigger: a super-resolved sheet)."""
    if k == 1:
        return e
    if isinstance(e, dict):
        d = dict(e, e=tuple(v * k if i != 4 else v for i, v in enumerate(e['e'])))
        if 'skin' in e:
            d['skin'] = (e['skin'][0] * k, e['skin'][1] * k)
        if e.get('close'):
            d['close'] = e['close'] * k
        return d
    e = list(e)
    for i in (0, 1, 2, 3):
        e[i] *= k
    if len(e) > 6 and e[6]:
        e[6] *= k
    return tuple(e)


def erase_one(img, ellipses, feather=1.8, protect_px=6, line_w=3.0, ks=1):
    """Paint the ellipses over with the surrounding skin. An ellipse is (cx, cy, rx, ry[, angle[, rim[,
    close]]]): the hole also takes the dark anti-aliased rim around what is erased (rim=True, else the
    fill would pull it in as a grey smudge); the figure's outer outline is never erased. close > 0
    (px): the eye cuts a notch into the silhouette (an eye white that Gemini drew open to the white
    background, so the cutout made it transparent): the silhouette is closed there, filled with skin
    and given a new outline of line_w px. The fill is a normalised blur of the skin around the hole
    (never of a dark line), so no smudge and no halo."""
    H, W = img.shape[:2]
    # every px size below is for a 1x picture; ks scales them for a super-resolved one
    K = lambda n: np.ones((2 * int(round((n - 1) / 2 * ks)) + 1,) * 2, np.uint8)
    feather, protect_px, line_w = feather * ks, protect_px * ks, line_w * ks
    m = np.zeros((H, W), np.uint8)
    norim = np.zeros((H, W), np.uint8)
    notch_zone = np.zeros((H, W), np.uint8)
    close_r = 0
    skin_at = None
    for e in ellipses:
        if isinstance(e, dict):         # {'e': (cx, cy, rx, ry[, angle]), 'rim', 'close', 'skin': (x, y)}
            skin_at = e.get('skin')
            e = tuple(e['e']) + ((0,) if len(e['e']) < 5 else ()) + (e.get('rim', True), e.get('close', 0))
        cx, cy, rx, ry = e[:4]
        ang = e[4] if len(e) > 4 else 0
        c, ax = (int(round(cx * 4)), int(round(cy * 4))), (int(round(rx * 4)), int(round(ry * 4)))
        cv2.ellipse(m, c, ax, ang, 0, 360, 255, -1, cv2.LINE_AA, 2)
        if len(e) > 5 and not e[5]:
            cv2.ellipse(norim, c, (ax[0] + 12, ax[1] + 12), ang, 0, 360, 255, -1, cv2.LINE_AA, 2)
        if len(e) > 6 and e[6]:
            cv2.ellipse(notch_zone, c, (ax[0] + 16, ax[1] + 16), ang, 0, 360, 255, -1, cv2.LINE_AA, 2)
            close_r = max(close_r, int(e[6]))
    if not m.any():
        return img
    out = img.copy()
    sil = img[..., 3] > 128
    sil2 = sil.copy()
    notch = np.zeros((H, W), bool)
    if close_r:
        kk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * close_r + 1, 2 * close_r + 1))
        closed = cv2.morphologyEx(sil.astype(np.uint8), cv2.MORPH_CLOSE, kk).astype(bool)
        notch = closed & ~sil & (notch_zone > 0)
        sil2 = sil | notch
        m[notch] = 255
    rgb = img[..., :3].clip(0, 255).astype(np.uint8)
    lum = img[..., :3] @ np.float32([0.3, 0.59, 0.11])
    dist_out = cv2.distanceTransform(sil2.astype(np.uint8), cv2.DIST_L2, 3)
    keep_line = (dist_out < protect_px) & (lum < 110) & sil
    m[keep_line] = 0
    hard = m > 0
    near = cv2.dilate(hard.astype(np.uint8), K(5)).astype(bool) & ~(norim > 0)
    h5 = cv2.dilate(hard.astype(np.uint8), K(5)).astype(bool)
    ring = cv2.dilate(h5.astype(np.uint8), K(5)).astype(bool) & ~h5 & (img[..., 3] > 200)
    ref = np.median(lum[ring]) if ring.any() else 200
    rim = near & (lum < ref - 40) & sil
    hole = cv2.dilate((hard | rim).astype(np.uint8), K(3)).astype(bool)
    hole &= ~keep_line & sil2
    skin = np.median(img[..., :3][ring], 0) if ring.any() else np.float32([200, 200, 200])
    if skin_at is not None:          # the eye sits on a patch of this colour: fill with that only
        x, y = int(round(skin_at[0])), int(round(skin_at[1]))
        skin = np.median(img[y - 2:y + 3, x - 2:x + 3, :3].reshape(-1, 3), 0)
    src = ~hole & (np.sqrt(((img[..., :3] - skin) ** 2).sum(-1)) < (30 if skin_at is not None else 45)) & (img[..., 3] > 200)
    fill = np.broadcast_to(skin, img[..., :3].shape).astype(np.float32).copy()
    got = np.zeros(hole.shape, bool)
    for sig in (2.5 * ks, 4.0 * ks, 6.0 * ks, 10.0 * ks, 16.0 * ks):
        w = cv2.GaussianBlur(src.astype(np.float32), (0, 0), sig)
        c = cv2.GaussianBlur(img[..., :3] * src[..., None], (0, 0), sig) / np.maximum(w[..., None], 1e-6)
        new = (w > 0.12) & ~got
        fill[new] = c[new]
        got |= new
    fill = cv2.GaussianBlur(fill, (0, 0), 1.5 * ks)
    kf = np.clip(cv2.GaussianBlur(hole.astype(np.float32), (0, 0), feather) * 1.5, 0, 1)[..., None]
    kf = np.where(notch[..., None], 1.0, kf)
    out[..., :3] = img[..., :3] * (1 - kf) + fill * kf
    if notch.any():
        # the closed silhouette: anti-aliased edge and a new outline where the notch was
        soft = cv2.GaussianBlur(sil2.astype(np.float32), (0, 0), 0.8 * ks)
        zone = cv2.dilate(notch.astype(np.uint8), K(5)).astype(bool)
        a_new = np.clip((soft - 0.5) * 3.0 + 0.5, 0, 1) * 255
        out[..., 3] = np.where(zone, np.maximum(img[..., 3], a_new), img[..., 3])
        d = cv2.distanceTransform(sil2.astype(np.uint8), cv2.DIST_L2, 3)
        ring_l = np.clip(line_w + 0.5 - d, 0, 1) * zone
        out[..., :3] = out[..., :3] * (1 - ring_l[..., None]) + LINE * ring_l[..., None]
    return out


def _aa(shape, draw, ss=4):
    """Anti-aliased mask (float 0..1) of whatever `draw(canvas, ss)` paints on a canvas ss times bigger."""
    big = np.zeros((shape[0] * ss, shape[1] * ss), np.uint8)
    draw(big, ss)
    return cv2.resize(big, (shape[1], shape[0]), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.


def paint(img, mask, color):
    """colour * mask over a straight RGBA image (alpha unchanged: the face is opaque)."""
    out = img.copy()
    out[..., :3] = img[..., :3] * (1 - mask[..., None]) + np.float32(color) * mask[..., None]
    return out


def draw_eye(img, e, k=1):
    """A drawn open eye (the animal's dark round eye with its highlights): e = dict(c=(x, y), r=(rx, ry),
    angle=0, color=(r, g, b), hl=[(dx, dy, radius, strength)] highlights relative to the centre, in units of
    rx / ry, radius in px). Coordinates in source px (times k). Used where a cell has no open eye of the right
    view: both eyes of a pair get the same colour and highlights and are scaled by the view's
    foreshortening, measured on the real 3/4 faces of the turnaround sheets."""
    cx, cy = e['c'][0] * k, e['c'][1] * k
    rx, ry = e['r'][0] * k, e['r'][1] * k
    ang = e.get('angle', 0.0)

    def disc(c, ss):
        cv2.ellipse(c, (int(round(cx * ss)), int(round(cy * ss))), (max(1, int(round(rx * ss))), max(1, int(round(ry * ss)))), ang, 0, 360, 255, -1)
    out = paint(img, _aa(img.shape[:2], disc), e['color'])
    for dx, dy, r, st in e.get('hl', []):
        hx, hy = cx + dx * rx, cy + dy * ry

        def dot(c, ss, hx=hx, hy=hy, r=r):
            cv2.circle(c, (int(round(hx * ss)), int(round(hy * ss))), max(1, int(round(r * k * ss))), 255, -1)
        out = paint(out, _aa(img.shape[:2], dot) * st, (255, 255, 255))
    return out


def draw_lid(img, l, k=1):
    """A closed eye: a tapered arc in the line colour. l = dict(c=(x, y), w=width, sag=how far the middle
    hangs below the ends (negative: bulges up), t=thickness in the middle, angle=0, color=LINE)."""
    cx, cy = l['c'][0] * k, l['c'][1] * k
    w, sag, t = l['w'] * k, l['sag'] * k, l['t'] * k
    c, s_ = np.cos(np.radians(l.get('angle', 0))), np.sin(np.radians(l.get('angle', 0)))
    u = np.linspace(0, 1, 40)
    x = (u - 0.5) * w
    y = (1 - (2 * u - 1) ** 2) * sag - sag / 2            # ends at -sag/2, middle at +sag/2: sags down
    th = np.maximum(t * np.sin(np.pi * u) ** 0.6, 0.35 * k)
    top = np.stack([x, y - th / 2], 1); bot = np.stack([x, y + th / 2], 1)[::-1]
    pts = np.concatenate([top, bot]) @ np.array([[c, s_], [-s_, c]]) + np.array([cx, cy])

    def poly(cv, ss):
        cv2.fillPoly(cv, [np.int32(np.round(pts * ss))], 255)
    return paint(img, _aa(img.shape[:2], poly), l.get('color', LINE))


def over_straight(img, layer):
    """premultiplied layer over a straight RGBA image (the face is opaque: alpha unchanged)."""
    out = img.copy()
    a = layer[..., 3:] / 255.
    out[..., :3] = layer[..., :3] + img[..., :3] * (1 - a)
    return out


def apply(base, spec, donors, up=1, k=1, kern=None):
    """The base frame (straight RGBA float, working px) with the variant's face. up: the donor sheet's
    enlargement (its boxes are in the donor's 1x px). k: the base's enlargement; when it is not 1 the
    coordinates of the spec (erase, at, skin, scale) are in the base's 1x source px and are multiplied
    here (build_character.py with super-resolved sheets)."""
    img = erase(base, spec.get('erase', []), line_w=spec.get('line_w', 3.0), k=k, kern=kern)
    for feat in spec.get('feats', []):
        cell = donors[(spec.get('sheet'), feat.get('cell', spec.get('cell')))]
        u = up
        lay = matte(cell, tuple(int(round(v * u)) for v in feat['box']), dark=feat.get('dark', (150, 55) if u == 1 else (135, 70)), keep_color=feat.get('color', False))
        lay = cv2.GaussianBlur(lay, (0, 0), feat.get('soften', 0.5) if u == 1 else feat.get('soften', 0.8))
        c = feat.get('src') or centroid(lay)
        at = (feat['at'][0] * k, feat['at'][1] * k)
        lay = place(lay, c, at, feat.get('scale', spec['scale']) * k / u, img.shape[:2],
                    flip_v=feat.get('flip_v', False), angle=feat.get('angle', 0.0))
        lay *= feat.get('opacity', 1.0)
        img = over_straight(img, lay)
    for e in spec.get('eyes', []):
        img = draw_eye(img, e, k)
    for l in spec.get('lids', []):
        img = draw_lid(img, l, k)
    return img


def load_donors(cfg):
    cache = {}
    for v in cfg['variants'].values():
        for feat in v.get('feats', []):
            key = (v.get('sheet'), feat.get('cell', v.get('cell')))
            if key not in cache:
                cache[key] = donor_cell(v.get('sheet') or cfg['sheet'], key[1], cfg.get('donor_upscale', 1), cfg.get('donor_flip', False))
    return cache


def variants(base, cfg):
    """{name: patched base} for every variant of a character's FACES config."""
    donors = load_donors(cfg)
    return {name: apply(base, spec, donors, cfg.get('donor_upscale', 1), kern=cfg.get('kern')) for name, spec in cfg['variants'].items()}


# ---------------------------------------------------------------- atlas patches
def patch_of(plain, varied, tol=1.5):
    """(patch RGBA uint8, x, y): the pixels of `varied` that differ from `plain` (two PIL RGBA images
    of the same atlas frame, resized/mirrored the same way). Pixels that do not differ are transparent,
    so the patch never thickens an outline when drawn over the frame."""
    a = np.asarray(plain).astype(np.int16); b = np.asarray(varied).astype(np.int16)
    diff = np.abs(a - b).max(-1) > tol
    if not diff.any():
        return None
    ys, xs = np.nonzero(diff)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    p = np.asarray(varied)[y0:y1, x0:x1].copy()
    p[..., 3] = np.where(diff[y0:y1, x0:x1], p[..., 3], 0)
    p[p[..., 3] == 0] = 0
    return Image.fromarray(p), int(x0), int(y0)


def attach(atlas, frames, patches):
    """Add face patches to an atlas and its manifest frames (docs/LOUNGE_SCENE_DESIGN.md 6.2).
    patches: [(name, patch image, px, py, [frame indices])]: the patch lies at (px, py) inside each of
    those frames (same size and head). It is stored once, in a new row under the atlas; every frame
    gets its own small entry {x, y, w, h, ax, ay, over: frame} placed by its anchor (the anchors differ
    per frame because of the bob), and the frame's "v" names it. Returns the new atlas."""
    if not patches:
        return atlas
    row_h = max(p[1].height for p in patches)
    W = max(atlas.width, sum(p[1].width + 2 for p in patches))
    out = Image.new('RGBA', (W, atlas.height + 2 + row_h), (0, 0, 0, 0))
    out.paste(atlas, (0, 0))
    x, y = 0, atlas.height + 2
    for name, img, px, py, idxs in patches:
        out.paste(img, (x, y))
        for i in idxs:
            f = frames[i]
            frames.append({'x': x, 'y': y, 'w': img.width, 'h': img.height,
                           'ax': f['ax'] - px, 'ay': f['ay'] - py, 'over': i})
            f.setdefault('v', {})[name] = len(frames) - 1
        x += img.width + 2
    return out


def direction_patches(plain, varied, idxs, flip=False):
    """[(name, patch, px, py, idxs)] for one direction: plain = that direction's atlas-size frame (PIL),
    varied = {name: the same frame with the face}; flip mirrors both first (the walk_l row)."""
    out = []
    for name, im in varied.items():
        a, b = plain, im
        if flip:
            a, b = a.transpose(Image.FLIP_LEFT_RIGHT), b.transpose(Image.FLIP_LEFT_RIGHT)
        p = patch_of(a, b)
        if p:
            out.append((name, p[0], p[1], p[2], idxs))
    return out


# ---------------------------------------------------------------- preview
def preview(base, vars_, box, k, out):
    tiles = [base] + list(vars_.values())
    x0, y0, x1, y1 = box
    ims = []
    for t in tiles:
        im = Image.fromarray(t.clip(0, 255).astype(np.uint8)).crop(box)
        bg = Image.new('RGBA', im.size, (200, 200, 200, 255)); bg.alpha_composite(im)
        ims.append(bg.resize((im.width * k, im.height * k), Image.LANCZOS))
    M = Image.new('RGB', (sum(i.width for i in ims) + 4 * len(ims), ims[0].height), (255, 255, 255))
    x = 0
    for i in ims:
        M.paste(i, (x, 0)); x += i.width + 4
    M.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name')
    ap.add_argument('--preview', required=True)
    ap.add_argument('--zoom', type=int, default=3)
    a = ap.parse_args()
    if a.name == 'tiger':
        import build_tiger_walker as T
        base = np.asarray(Image.open(T.SRC / 'left_0.png').convert('RGBA')).astype(np.float32)
        cfg = T.FACES
    else:
        import build_walker as Wk
        base, cfg = Wk.face_base(a.name)
    vs = variants(base, cfg)
    preview(base, vs, cfg['preview_box'], a.zoom, a.preview)
    print('wrote', a.preview)


if __name__ == '__main__':
    sys.path.insert(0, str(TOOLS))
    main()
