#!/usr/bin/env python3
"""Build the lounge scene assets from the aligned background layers in art/lounge_bg/.

    python3 art/tools/build_lounge_scene.py [--out ui/web/lounge/assets]

Writes bg/*.webp at the scene's logical size and rewrites scene.json (characters untouched).
The sofa front (what hides a seated character's lower body) is cut from each interior variant
with the polygon below, measured on the 1440 x 1000 scene.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC = Path(__file__).resolve().parent.parent / 'lounge_bg'
W, H = 1440, 1000
VARIANTS = [('night', -10), ('golden', 2), ('day', 14)]       # lighting stage -> sun elevation anchor

# Everything in front of a seated character: armrests and the front of the seat cushions.
SOFA_FRONT = [
    [(0, 770), (300, 770), (300, 868), (870, 868), (870, 1000), (0, 1000)],                 # left sofa
    [(870, 835), (1050, 835), (1050, 925), (1440, 925), (1440, 1000), (870, 1000)],        # right sofa
]

SCENE = {
    'placeholder': False,
    'size': [W, H],
    'baselineY': 1070,             # walkers pass in front, feet below the frame
    'horizonY': 560,
    'windowFacing': 225,
    'charScale': 1.25,
    'characters': ['tiger', 'rabbit', 'turtle', 'penguin'],
    'window': {'x': 700, 'y': 0, 'w': 740, 'h': 700},
    # painted row boundaries of the panel, top to bottom, each [[x_left, y], [x_right, y]]
    'board': {'x': 64, 'y': 101, 'w': 516, 'h': 398, 'rows': 6,
              'lines': [[[64, 100.7], [580, 208.6]], [[64, 160.9], [580, 258.9]], [[64, 222.0], [580, 308.7]], [[64, 282.1], [580, 359.5]], [[64, 343.2], [580, 413.4]], [[64, 406.3], [580, 465.1]], [[64, 449.4], [580, 497.9]]]},
    'seats': [{'id': 's0', 'x': 430, 'y': 995}, {'id': 's1', 'x': 665, 'y': 995},
              {'id': 's2', 'x': 1145, 'y': 1050}, {'id': 's3', 'x': 1335, 'y': 1050}],
    'entries': {'left': -320, 'right': 1760},
    'lamps': [{'x': 120, 'y': 700, 'r': 520}, {'x': 660, 'y': 660, 'r': 460}],
    'floorLight': None,
    # a plane taxis past the window every `period` seconds, taking `duration` seconds
    'planes': {'right': 'bg/plane_right.webp', 'left': 'bg/plane_left.webp',
               'y': 712, 'height': 170, 'from': 520, 'to': 1760, 'period': 150, 'duration': 70},
}


def mask_image():
    m = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(m)
    for poly in SOFA_FRONT:
        d.polygon(poly, fill=255)
    return m.filter(ImageFilter.GaussianBlur(1.5))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default='ui/web/lounge/assets')
    out = Path(ap.parse_args(argv).out)
    bg = out / 'bg'
    bg.mkdir(parents=True, exist_ok=True)
    for old in bg.iterdir():
        old.unlink()
    front = mask_image()
    layers = {'outside': [], 'interior': [], 'sofaFront': []}
    for name, elev in VARIANTS:
        for kind in ('outside', 'interior'):
            im = Image.open(SRC / ('%s_%s.webp' % (kind, name))).convert('RGBA').resize((W, H), Image.LANCZOS)
            im.save(bg / ('%s_%s.webp' % (kind, name)), 'WEBP', quality=88, method=6)
            layers[kind].append({'elev': elev, 'file': 'bg/%s_%s.webp' % (kind, name)})
            if kind == 'interior':
                sofa = im.copy()
                a = np.minimum(np.asarray(sofa.getchannel('A')), np.asarray(front))
                sofa.putalpha(Image.fromarray(a))
                sofa.save(bg / ('sofa_front_%s.webp' % name), 'WEBP', quality=88, method=6)
                layers['sofaFront'].append({'elev': elev, 'file': 'bg/sofa_front_%s.webp' % name})
    cut = Path(__file__).resolve().parent.parent / 'cutouts'
    for side in ('right', 'left'):
        im = Image.open(cut / ('plane_%s.png' % side)).convert('RGBA')
        im = im.resize((round(im.width * 260 / im.height), 260), Image.LANCZOS)
        im.save(bg / ('plane_%s.webp' % side), 'WEBP', quality=90, method=6)
    scene = dict(SCENE)
    scene['layers'] = [
        {'id': 'outside', 'group': 'far', 'tint': False, 'variants': layers['outside']},
        {'id': 'interior', 'group': 'back', 'tint': False, 'variants': layers['interior']},
        {'id': 'sofaFront', 'group': 'mid', 'tint': False, 'cutFrom': 'interior', 'variants': layers['sofaFront']},
    ]
    (out / 'scene.json').write_text(json.dumps(scene, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    total = sum(p.stat().st_size for p in bg.iterdir())
    print('wrote %d background files, %d KB' % (len(list(bg.iterdir())), total // 1024))


if __name__ == '__main__':
    main()
