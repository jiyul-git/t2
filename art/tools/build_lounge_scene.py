#!/usr/bin/env python3
"""Build the lounge scene assets from the aligned background layers in art/lounge_bg/.

    python3 art/tools/build_lounge_scene.py [--out ui/web/lounge/assets]

Writes bg/*.webp at the scene's logical size and rewrites scene.json.
The sofa front (what hides a seated character's lower body) is cut from each interior variant
with the polygon below, measured on the 1440 x 1000 picture.

The interior is the floor-extended version (interior_<v>_ext.webp, see extend_floor.py), so the
scene is taller than the original picture: rows below 1000 are sofa bases and carpet. The window
view only fills the top, so it is padded down with its own last row.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC = Path(__file__).resolve().parent.parent / 'lounge_bg'
W, H0 = 1440, 1000                 # the original picture
H = 1152                           # with the floor extension (1990 / 1728 * 1000)
VARIANTS = [('night', -10), ('golden', 2), ('day', 14)]       # lighting stage -> sun elevation anchor

# Everything in front of a seated character: armrests and the front of the seat cushions.
SOFA_FRONT = [
    [(0, 770), (300, 770), (300, 868), (870, 868), (870, H), (0, H)],                       # left sofa
    [(870, 835), (1050, 835), (1050, 925), (1440, 925), (1440, H), (870, H)],              # right sofa
]

SCENE = {
    'placeholder': False,
    'size': [W, H],
    'baselineY': 1118,             # walkers pass on the carpet in front of the sofas
    'horizonY': 560,
    'windowFacing': 225,
    'charScale': 1.25,
    # Only real walkers so far (tiger, rabbit, turtle), crossing left to right one at a time, taking
    # turns. The placeholder sitters (tiger, rabbit, turtle, penguin) stay on disk for the tests and
    # come back with real sitting art.
    'characters': ['tiger_walker', 'rabbit_walker', 'turtle_walker'],
    'passEvery': [15, 45],           # seconds of quiet between crossings (walker or plane), then a random pick
    'preview': ['rabbit_walker', 'turtle_walker'],   # shown first, right away, while their motion is reviewed
    'window': {'x': 700, 'y': 0, 'w': 740, 'h': 700},
    # painted row boundaries of the panel, top to bottom, each [[x_left, y], [x_right, y]]
    'board': {'x': 64, 'y': 101, 'w': 516, 'h': 398, 'rows': 6, 'textRows': 5,   # bottom row left empty
              'lines': [[[64, 100.7], [580, 208.6]], [[64, 160.9], [580, 258.9]], [[64, 222.0], [580, 308.7]], [[64, 282.1], [580, 359.5]], [[64, 343.2], [580, 413.4]], [[64, 406.3], [580, 465.1]], [[64, 449.4], [580, 497.9]]]},
    'seats': [{'id': 's0', 'x': 430, 'y': 995}, {'id': 's1', 'x': 665, 'y': 995},
              {'id': 's2', 'x': 1145, 'y': 1050}, {'id': 's3', 'x': 1335, 'y': 1050}],
    'entries': {'left': -320, 'right': 1760},
    'lamps': [{'x': 120, 'y': 700, 'r': 520}, {'x': 660, 'y': 660, 'r': 460}],
    'floorLight': None,
    # a plane taxis past the window every `period` seconds, taking `duration` seconds.
    # As big as in the approved illustration: about half the picture wide, fuselage mid-window,
    # wheels hidden behind the sofas.
    'planes': None,                # filled from PLANES below
    # aviation lights painted on the tower and a pole outside: at night they pulse (period s, phase s)
    'beacons': [
        {'x': 855, 'y': 197, 'r': 16, 'color': '#ff4a3a', 'period': 1.5, 'phase': 0.0},
        {'x': 834, 'y': 256, 'r': 12, 'color': '#ff4a3a', 'period': 1.5, 'phase': 0.75},
        {'x': 884, 'y': 253, 'r': 12, 'color': '#ff4a3a', 'period': 1.5, 'phase': 0.75},
        {'x': 907, 'y': 217, 'r': 12, 'color': '#ff4a3a', 'period': 1.5, 'phase': 0.0},
        {'x': 1017, 'y': 426, 'r': 12, 'color': '#ff5a6a', 'period': 2.2, 'phase': 0.4},
        {'x': 1135, 'y': 436, 'r': 12, 'color': '#6a8bff', 'period': 2.6, 'phase': 1.3},
    ],
}
PLANES = {'right': 'bg/plane_right.webp', 'left': 'bg/plane_left.webp',
          'y': 745, 'height': 370, 'from': 380, 'to': 1980, 'period': 150, 'duration': 80, 'haze': 0.3,
          # wheel hubs on each cut-out, as fractions of the image (cx, cy, rx, ry): spokes are drawn
          # on them and turn with the distance travelled, so the gear rolls
          'wheels': {'right': [[378, 385, 6, 10], [571, 375, 5, 8], [792, 398, 7, 9]],
                     'left': [[168, 394, 6.5, 8], [387, 371, 6, 9], [578, 381, 6, 9.5]]}}


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
            if kind == 'interior':
                im = Image.open(SRC / ('interior_%s_ext.webp' % name)).convert('RGBA').resize((W, H), Image.LANCZOS)
            else:
                top = Image.open(SRC / ('outside_%s.webp' % name)).convert('RGBA').resize((W, H0), Image.LANCZOS)
                a = np.asarray(top)
                im = Image.fromarray(np.concatenate([a, np.repeat(a[-1:], H - H0, axis=0)]))
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
        im = im.resize((round(im.width * 400 / im.height), 400), Image.LANCZOS)
        im.save(bg / ('plane_%s.webp' % side), 'WEBP', quality=90, method=6)
    scene = dict(SCENE)
    scene['planes'] = dict(PLANES)
    for side in ('right', 'left'):        # source px -> fractions of the cut-out
        im = Image.open(Path(__file__).resolve().parent.parent / 'cutouts' / ('plane_%s.png' % side))
        scene['planes']['wheels'] = dict(scene['planes']['wheels'])
        scene['planes']['wheels'][side] = [[round(cx / im.width, 4), round(cy / im.height, 4), round(rx / im.height, 4), round(ry / im.height, 4)]
                                           for cx, cy, rx, ry in PLANES['wheels'][side]]
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
