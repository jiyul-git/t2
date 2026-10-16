#!/usr/bin/env python3
"""Build the tiger walk loop and pack it into a walker character for the lounge.

    python3 art/tools/build_tiger_walker.py

1. legs: the cells of art/cutouts/tiger_walk_b/left_*.png, plus the "other foot forward" poses made
   by flipping only the legs (mirror_legs.py) - Gemini never drew that foot stepping;
2. one upper body for every frame (lockbody.py), written to art/cutouts/tiger_walk_b/loop/left_*;
3. right-facing copies with the T2 letters kept readable (mirror_logo.py) -> loop/right_*;
4. ui/web/lounge/assets/chars/tiger_walker/{atlas.webp, manifest.json}.
A walker only has walk_r / walk_l: it crosses the lounge and leaves (no sofa). Every frame shares one
anchor on the upper body, so the body glides level and only the legs move.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CELLS = ROOT / 'art/cutouts/tiger_walk_b'
SRC = CELLS / 'loop'
TOOLS = Path(__file__).resolve().parent
# leg order (as drawn by Gemini, put in pose order). The flipped-legs poses ('m..', mirror_legs.py)
# turned out worse - toes pointing backward, a doubled frame - so they are not used until a proper
# "other foot forward" drawing arrives (docs/LOUNGE_ART_PROMPTS.md).
ORDER = ['10', '02', '03', '13', '31', '30', '22', '20']
BASE = '10'               # the upper body every frame shares
OUT = ROOT / 'ui/web/lounge/assets/chars/tiger_walker'
SCALE = 0.62          # atlas pixels per source pixel (keeps the atlas small)
FPS, ADVANCE = 10, 25  # frames per second, scene px moved per frame (matches the planted foot, see footslip check)


def anchor_x(im):
    a = np.asarray(im)[..., 3] > 128
    top = int(np.nonzero(a.any(1))[0][0])
    xs = np.nonzero(a[top:top + int(im.height * 0.35)])[1]
    return int(round(xs.mean()))


def run(*args):
    subprocess.run([sys.executable, '-I', *map(str, args)], check=True, stdout=subprocess.DEVNULL)


def build_loop():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp); cells, out = tmp / 'cells', tmp / 'loop'
        cells.mkdir()
        for p in CELLS.glob('left_*.png'):
            shutil.copy(p, cells / ('f_' + p.stem[5:] + '.png'))
        for n in {o[1:] for o in ORDER if o.startswith('m')}:
            run(TOOLS / 'mirror_legs.py', cells / ('f_%s.png' % n), cells / ('f_m%s.png' % n))
        run(TOOLS / 'lockbody.py', cells, BASE, out, ','.join(ORDER))
        SRC.mkdir(exist_ok=True)
        for i in range(len(ORDER)):
            shutil.copy(out / ('f_%d.png' % i), SRC / ('left_%d.png' % i))
            run(TOOLS / 'mirror_logo.py', out / ('f_%d.png' % i), SRC / ('right_%d.png' % i))


def main():
    build_loop()
    frames_img = []
    for side in ('right', 'left'):
        for i in range(8):
            im = Image.open(SRC / ('%s_%d.png' % (side, i))).convert('RGBA')
            im = im.resize((round(im.width * SCALE), round(im.height * SCALE)), Image.LANCZOS)
            frames_img.append(im)
    # same height for all (pad at the bottom): the frames all start at the top of the shared head
    hmax = max(im.height for im in frames_img)
    for k, im in enumerate(frames_img):
        pad = Image.new('RGBA', (im.width, hmax), (0, 0, 0, 0)); pad.paste(im, (0, 0)); frames_img[k] = pad
    base_h = round(Image.open(SRC / 'left_0.png').height * SCALE)
    W = sum(im.width for im in frames_img[:8]) + 16
    H = max(im.height for im in frames_img) * 2 + 4
    atlas = Image.new('RGBA', (max(W, sum(im.width for im in frames_img[8:]) + 16), H), (0, 0, 0, 0))
    frames, x, y, rowh = [], 0, 0, max(im.height for im in frames_img) + 2
    # every frame is cropped at the top of the (shared) head, so one foot line for all of them keeps
    # the body level: the base frame's own feet
    body_y = base_h - 1
    for k, im in enumerate(frames_img):
        if k == 8: x, y = 0, rowh
        atlas.paste(im, (x, y))
        ax, ay = anchor_x(im), body_y
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
