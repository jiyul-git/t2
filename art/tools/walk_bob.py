"""A very slight walking bob for the walker loops (art/README.md, docs/LOUNGE_SCENE_DESIGN.md 6.2).

The body is a little higher while the legs pass each other and a little lower while they are spread
apart: with leg length L and the feet s apart, the hip is about sqrt(L^2 - (s/2)^2) above the floor.
The builders measure s on every loop frame, turn it into a smooth periodic series scaled to a tiny
peak-to-peak (about 1% of the figure), and give every frame its own anchor ay = body + bob (the
renderer draws a frame with (ax, ay) on the floor, so a larger ay draws the sprite higher).

So that the feet stay on the floor while the body rises and sinks, the legs of each frame are also
stretched (or squeezed) a little: nothing at the hem, the full amount at the sole, until the lowest
(planted) foot ends exactly on the frame's anchor row. That also removes the few px the planted foot
used to float or sink from frame to frame.
"""
import cv2
import numpy as np


def spread(legmask, band=0.4):
    """Horizontal extent of the lower part of the legs (the feet): narrow when the feet are together
    or crossing, wide when they are apart. legmask: bool image holding only the legs."""
    ys = np.nonzero(legmask.any(1))[0]
    if not len(ys):
        return 0.0
    top, bot = ys.min(), ys.max()
    lo = int(round(bot - band * (bot - top)))
    xs = np.nonzero(legmask[lo:bot + 1].any(0))[0]
    return float(xs.max() - xs.min() + 1)


def bob_series(s, leg, pp, smooth=1):
    """Body height per frame (positive = higher), peak-to-peak pp, from the feet distances s.
    The series is treated as periodic (a loop) and smoothed with a circular [1 2 1] filter."""
    s = np.asarray(s, np.float64)
    h = np.sqrt(np.maximum(leg ** 2 - (s / 2) ** 2, 1.0))
    b = h - h.mean()
    for _ in range(smooth):
        b = (np.roll(b, 1) + 2 * b + np.roll(b, -1)) / 4
    rng = b.max() - b.min()
    if rng < 1e-6:
        return np.zeros_like(b)
    b = b / rng * pp
    return b - (b.max() + b.min()) / 2


def quantize(b):
    """Whole atlas px (anchors are integers), keeping the shape: round, never more than ceil(pp)."""
    q = np.round(b).astype(int)
    return [int(v) for v in q]


def stretch_layer(p, hem, foot, target):
    """Move the pixels of a premultiplied legs-only layer down by (target - foot) at the sole, by 0 at
    the hem, linearly in between. hem: row where the legs start (scalar or per column); foot: current
    bottom row of the lowest foot; target: the row it should end on."""
    d = float(target - foot)
    if abs(d) < 0.05:
        return p
    H, W = p.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    hem = np.broadcast_to(np.asarray(hem, np.float32), (W,))[None, :]
    span = np.maximum(foot - hem, 1.0)
    # inverse map: output row y shows input row y - d * r, r = share of the way from the hem to the
    # (new) sole, so the hem stays and the old sole row lands exactly on the target row
    r = np.clip((yy - hem) / np.maximum(span + d, 1.0), 0, 1)
    moved = cv2.remap(p, xx, yy - d * r, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    moved = np.clip(moved, 0, 255)
    moved[..., :3] = np.minimum(moved[..., :3], moved[..., 3:])
    return moved


def stretch_legs(rgba, legmask, hem, foot, target):
    """stretch_layer for a finished frame (straight RGBA float): only the pixels in legmask move,
    and they are drawn back over the rest."""
    if abs(target - foot) < 0.05 or not legmask.any():
        return rgba
    p = rgba.copy()
    p[..., :3] *= p[..., 3:] / 255.
    legs = p.copy(); legs[~legmask] = 0
    rest = p.copy(); rest[legmask] = 0
    moved = stretch_layer(legs, hem, foot, target)
    out = moved + rest * (1 - moved[..., 3:] / 255.)
    res = out.copy()
    al = out[..., 3:]
    res[..., :3] = np.where(al > 0, out[..., :3] * 255. / np.maximum(al, 1e-3), 0)
    return res


def bottom_row(mask):
    ys = np.nonzero(mask.any(1))[0]
    return int(ys.max()) if len(ys) else 0
