#!/usr/bin/env python3
"""Make the other-foot-forward pose by hand-style editing of a frame of the 3/4-view walk.

The tiger stands turned toward the viewer, so the near leg and the far leg do not look alike:
the far leg is a little higher on screen (further away), a little smaller, in shade, and behind
the near leg. The sheet only has the near leg stepping forward. Here the two leg pieces (split at
the crotch) swap roles: the front piece becomes the far leg (raised, narrowed toward the crotch,
darkened, drawn first) and the back piece becomes the near leg (lowered, drawn on top with its
outline where it covers the far one). Upper body untouched.

    python3 art/tools/swap_legs.py IN OUT [--cx 125] [--rise 7] [--shade 0.78] [--narrow 0.92]
"""
import argparse, os, sys
import numpy as np, cv2
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inkfix import reink, LINE
from lockbody import navy_mask, HAND_BLOCK, hem_rows, premul, unpremul, over

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('dst')
ap.add_argument('--cx', type=float, default=None)   # crotch split; default: the gap between the feet
ap.add_argument('--rise', type=float, default=7)      # px the far leg moves up (the near leg moves down by half)
ap.add_argument('--shade', type=float, default=0.78)  # colour multiplier for the far leg
ap.add_argument('--narrow', type=float, default=0.92) # far leg pulled toward the crotch (foreshortening)
a = ap.parse_args()

im = np.asarray(Image.open(a.src).convert('RGBA')).astype(np.float32)
H, W = im.shape[:2]
hb, hm = hem_rows(im)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
zone = (yy > hm - 4) & ~navy_mask(im) & ~((xx >= HAND_BLOCK[0]) & (yy < HAND_BLOCK[1]))
legs = zone & (im[..., 3] > 0)
if a.cx is None:
    # the emptiest column between the feet (rows below the crotch), searched around the middle
    low = legs & (yy > hm + 30)
    cols = low.sum(0).astype(np.float32)
    cols = np.convolve(cols, np.ones(5) / 5, mode='same')
    lo, hi = 95, 175
    a.cx = float(lo + np.argmin(cols[lo:hi]))
pm = premul(im)
top = pm.copy(); top[legs] = 0
band = pm.copy(); band[~(legs & (yy < hm + 16))] = 0


def ramp(y, start=22, length=26):
    """0 above the crotch (the hips stay one piece), 1 from the knees down"""
    t = np.clip((y - (hm + start)) / float(length), 0, 1)
    return t * t * (3 - 2 * t)


def warp(piece, dy, sx=1.0):
    """move rows down by dy*ramp, and pull x toward the crotch by factor sx (grows with ramp)"""
    r = ramp(yy)
    k = 1 - (1 - sx) * r
    src_x = a.cx + (xx - a.cx) / k
    src_y = yy - dy * r
    return cv2.remap(piece, src_x.astype(np.float32), src_y.astype(np.float32), cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=0)


front = pm.copy(); front[~(legs & (xx < a.cx))] = 0
back = pm.copy(); back[~(legs & (xx >= a.cx))] = 0
far = warp(front, -a.rise, a.narrow)
far[..., :3] *= (1 - (1 - a.shade) * ramp(yy, 28, 18))[..., None]   # shade fades in below the crotch
near = warp(back, a.rise * 0.5)
legs_l = over(over(band, far), near)
na = near[..., 3] > 40
edge = na & ~cv2.erode(na.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
edge &= (far[..., 3] > 40) & (yy > hm + 8)
edge = cv2.dilate(edge.astype(np.uint8), np.ones((2, 2), np.uint8)).astype(bool) & na
legs_l[edge] = np.append(LINE, 255)
legs_l = reink(legs_l, allow=zone.astype(np.float32), protect=(yy < hm + 8))
# drop stray bits (keep the leg blob) and pale specks left inside
la = legs_l[..., 3] > 20
n_, lab, st, _ = cv2.connectedComponentsWithStats(la.astype(np.uint8))
if n_ > 1:
    big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    legs_l[(lab > 0) & (lab != big)] = 0
u = unpremul(legs_l)
mn, mx = u[..., :3].min(-1), u[..., :3].max(-1)
speck = ((mn > 200) & (mx - mn < 25) & (legs_l[..., 3] > 20)).astype(np.uint8)
if speck.any():
    rgb = cv2.inpaint(u[..., :3].clip(0, 255).astype(np.uint8), cv2.dilate(speck, np.ones((3, 3), np.uint8)), 3, cv2.INPAINT_TELEA)
    u[..., :3] = rgb
    legs_l = premul(u)
out = unpremul(over(legs_l, top))
Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(a.dst)
