#!/usr/bin/env python3
"""Make an in-between walk frame from a contact pose by hand-style editing: the front foot is
moved back (and lifted a little), the back foot forward, each as a rigid piece, and the pants
between them are pulled along smoothly. Upper body (above the hem) is untouched.

    python3 art/tools/stride_tween.py IN OUT --front DX [--back DX] [--lift PX] [--cx X]
"""
import argparse
import numpy as np, cv2
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('dst')
ap.add_argument('--front', type=float, default=25)    # px the front (left) foot moves back (right)
ap.add_argument('--back', type=float, default=25)     # px the back (right) foot moves forward (left)
ap.add_argument('--lift', type=float, default=6)      # px the front foot rises
ap.add_argument('--cx', type=float, default=125)      # crotch x: left of it is the front leg
ap.add_argument('--right', type=float, default=238)   # suitcase starts here: untouched
a = ap.parse_args()

im = np.asarray(Image.open(a.src).convert('RGBA')).astype(np.float32)
H, W = im.shape[:2]
R, G, B, A = [im[..., k] for k in range(4)]
green = (G > R + 5) & (G > B) & (A > 128)
hem = np.array([np.nonzero(green[:, x])[0].max() if green[:, x].sum() >= 3 else -1 for x in range(W)])
hm = int(np.median(hem[(hem > 0) & (np.arange(W) < 215)]))

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
pm = im.copy(); pm[..., :3] *= pm[..., 3:] / 255.          # premultiplied, so edges blend cleanly


def ramp(y):            # share of the foot motion a row gets: 0 at the hem, 1 from the ankles down
    t = np.clip((y - (hm + 6)) / 34.0, 0, 1)
    return t * t * (3 - 2 * t)


def moved(piece, shift_x, lift):
    """the piece slid by shift_x * ramp(y) (and raised by lift * ramp(y)); one direction, so exact"""
    sx = xx - shift_x * ramp(yy)
    sy = yy + lift * ramp(yy)
    return cv2.remap(piece, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def over(dst, src):
    return src + dst * (1 - src[..., 3:] / 255.)


# right edge of the legs: a line along the suitcase's front edge (same as lockbody.py), clear of the
# pulling hand and the handle
EDGE = [(0, 218), (262, 218), (285, 230), (305, 243), (H, 258)]
xb = np.interp(np.arange(H), [p[0] for p in EDGE], [p[1] for p in EDGE]).astype(np.float32)[:, None]
legs = (yy > hm + 2) & (xx < np.minimum(xb, a.right))
front_m = legs & (xx < a.cx)
back_m = legs & (xx >= a.cx)
top = pm.copy(); top[legs] = 0
band = pm.copy(); band[~(legs & (yy < hm + 16))] = 0     # pants right under the hem fills small gaps
front = pm.copy(); front[~front_m] = 0
back = pm.copy(); back[~back_m] = 0
out = band
out = over(out, moved(back, -a.back, 0))
out = over(out, moved(front, a.front, a.lift))
out = over(out, top)
al = out[..., 3:]
out[..., :3] = np.where(al > 0, out[..., :3] * 255. / np.maximum(al, 1e-3), 0)
Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(a.dst)
