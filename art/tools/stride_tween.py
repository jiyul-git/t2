#!/usr/bin/env python3
"""Make an in-between walk frame from a contact pose by hand-style editing: the front foot is
moved back (and lifted a little), the back foot forward, each as a rigid piece, and the pants
between them are pulled along smoothly. Upper body (above the hem) is untouched.

    python3 art/tools/stride_tween.py IN OUT --front DX [--back DX] [--lift PX] [--cx X]
"""
import argparse
import os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inkfix import reink
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


# legs: below the hem, minus the suitcase and the hand/handle/tail block (same rule as lockbody.py)
from lockbody import navy_mask, HAND_BLOCK
zone = (yy > hm - 4) & ~navy_mask(im) & ~((xx >= HAND_BLOCK[0]) & (yy < HAND_BLOCK[1]))   # where legs may be
legs = zone & (im[..., 3] > 0)
front_m = legs & (xx < a.cx)
back_m = legs & (xx >= a.cx)
top = pm.copy(); top[legs] = 0
band = pm.copy(); band[~(legs & (yy < hm + 16))] = 0     # pants right under the hem fills small gaps
front = pm.copy(); front[~front_m] = 0
back = pm.copy(); back[~back_m] = 0
mb = moved(back, -a.back, 0)
mf = moved(front, a.front, a.lift)
legs_l = over(over(band, mb), mf)
# the front leg now overlaps the back one: draw its outline where it lies over the back leg
fa = mf[..., 3] > 40
edge = fa & ~cv2.erode(fa.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
edge &= (mb[..., 3] > 40) & (yy > hm + 8)
edge = cv2.dilate(edge.astype(np.uint8), np.ones((2, 2), np.uint8)).astype(bool) & fa
legs_l[edge] = np.array([34, 24, 20, 255], np.float32)
legs_l = reink(legs_l, allow=zone.astype(np.float32), protect=(yy < hm + 8))
out = over(legs_l, top)
al = out[..., 3:]
out[..., :3] = np.where(al > 0, out[..., :3] * 255. / np.maximum(al, 1e-3), 0)
Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(a.dst)
