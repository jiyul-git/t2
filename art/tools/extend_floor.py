#!/usr/bin/env python3
"""Extend the lounge interior downward with the floor Gemini drew (sofa bases, legs, carpet).

    python3 art/tools/extend_floor.py

Gemini did not keep the original pixels when asked to extend the picture: it redrew the room a
little further out. So only its lower part is used: scaled so its sofas match ours, attached
under art/lounge_bg/interior_<v>.webp from the row where our picture is cut (mid seat front),
cross-faded over 60 rows and colour-matched (Lab mean/std) to each lighting variant's bottom band.
Writes art/lounge_bg/interior_<v>_ext.webp. Source: art/sources/bg_floor_extension_gemini.webp
(the Gemini star watermark already painted out).
"""
from pathlib import Path
import numpy as np
import cv2
from PIL import Image

ART = Path(__file__).resolve().parent.parent
SRC = ART / 'sources/bg_floor_extension_gemini.webp'
# Gemini px -> interior px: the same in both directions (width fills the picture, 2490 / 1024).
# A smaller vertical scale doubled the right sofa's seat front.
ANCHOR = 505        # Gemini row that meets the interior's bottom edge (where the seat fronts join the base)
BLEND = 60


def lab(a):
    return cv2.cvtColor(a.clip(0, 255).astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)


def extend(variant):
    im = Image.open(ART / ('lounge_bg/interior_%s.webp' % variant)).convert('RGBA')
    o = np.asarray(im).astype(np.float32)
    H, W = o.shape[:2]
    g = np.asarray(Image.open(SRC).convert('RGB')).astype(np.float32)
    scale = W / g.shape[1]
    gs = cv2.resize(g, (W, int(round(g.shape[0] * scale))), interpolation=cv2.INTER_CUBIC)
    ext = gs[int(ANCHOR * scale) - BLEND:]
    ref, src = lab(o[H - 160:H, :, :3]), lab(ext[:160])
    e = lab(ext)
    for c in range(3):
        e[..., c] = (e[..., c] - src[..., c].mean()) / (src[..., c].std() + 1e-3) * ref[..., c].std() + ref[..., c].mean()
    ext = cv2.cvtColor(e.clip(0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB).astype(np.float32)
    ext = np.dstack([ext, np.full(ext.shape[:2], 255, np.float32)])
    out = np.zeros((H + ext.shape[0] - BLEND, W, 4), np.float32)
    out[:H] = o
    w = np.linspace(0, 1, BLEND)[:, None, None]
    out[H - BLEND:H] = o[H - BLEND:] * (1 - w) + ext[:BLEND] * w
    out[H:] = ext[BLEND:]
    dst = ART / ('lounge_bg/interior_%s_ext.webp' % variant)
    Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(dst, 'WEBP', quality=92, method=6)
    return W, out.shape[0]


if __name__ == '__main__':
    for v in ('night', 'golden', 'day'):
        print(v, 'extended to %dx%d' % extend(v))
