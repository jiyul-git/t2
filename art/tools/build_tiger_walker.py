#!/usr/bin/env python3
"""Pack the tiger walk loop (art/cutouts/tiger_walk_b/loop) into a walker character for the lounge.

    python3 art/tools/build_tiger_walker.py

Writes ui/web/lounge/assets/chars/tiger_walker/{atlas.webp, manifest.json}. A walker only has
walk_r / walk_l: it crosses the lounge and leaves (no sofa). Each frame's anchor is the head's centre
column and the bottom of the feet, so the body stays put and only bobs as the legs change.
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'art/cutouts/tiger_walk_b/loop'
OUT = ROOT / 'ui/web/lounge/assets/chars/tiger_walker'
SCALE = 0.62          # atlas pixels per source pixel (keeps the atlas small)
FPS, ADVANCE = 10, 16  # frames per second, scene px moved per frame (before charScale)


def anchor(im):
    a = np.asarray(im)[..., 3] > 128
    top = int(np.nonzero(a.any(1))[0][0])
    xs = np.nonzero(a[top:top + int(im.height * 0.35)])[1]
    return int(round(xs.mean())), im.height - 1


def main():
    frames_img = []
    for side in ('right', 'left'):
        for i in range(8):
            im = Image.open(SRC / ('%s_%d.png' % (side, i))).convert('RGBA')
            im = im.resize((round(im.width * SCALE), round(im.height * SCALE)), Image.LANCZOS)
            frames_img.append(im)
    W = sum(im.width for im in frames_img[:8]) + 16
    H = max(im.height for im in frames_img) * 2 + 4
    atlas = Image.new('RGBA', (max(W, sum(im.width for im in frames_img[8:]) + 16), H), (0, 0, 0, 0))
    frames, x, y, rowh = [], 0, 0, max(im.height for im in frames_img) + 2
    for k, im in enumerate(frames_img):
        if k == 8: x, y = 0, rowh
        atlas.paste(im, (x, y))
        ax, ay = anchor(im)
        frames.append({'x': x, 'y': y, 'w': im.width, 'h': im.height, 'ax': ax, 'ay': ay})
        x += im.width + 2
    OUT.mkdir(parents=True, exist_ok=True)
    atlas.save(OUT / 'atlas.webp', lossless=False, quality=90, method=6)
    man = {
        'name': 'tiger_walker', 'walker': True, 'pass': 'r', 'atlas': 'atlas.webp',
        'scale': round(1 / SCALE, 4), 'mirrorable': False, 'frames': frames,
        'poses': {'walk_r': 0, 'walk_l': 8},
        'clips': {
            'walk_r': {'from': 'walk_r', 'to': 'walk_r', 'loop': True, 'fps': FPS, 'frames': list(range(8)), 'advance': ADVANCE},
            'walk_l': {'from': 'walk_l', 'to': 'walk_l', 'loop': True, 'fps': FPS, 'frames': list(range(8, 16)), 'advance': ADVANCE},
        },
    }
    (OUT / 'manifest.json').write_text(json.dumps(man, separators=(',', ':')))
    print('tiger_walker: atlas %dx%d, %d bytes' % (atlas.width, atlas.height, (OUT / 'atlas.webp').stat().st_size))


if __name__ == '__main__':
    main()
