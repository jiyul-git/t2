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
import math
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

# Sofa parts that are nearer than a seated character and must cover it: the left sofa's left arm (its
# front face and rounded top, traced on the picture). Drawn after seated people, before the aisle.
SOFA_ARMS = [
    [(150, 755), (268, 755), (285, 763), (293, 777), (296, 800), (298, 850), (301, 900), (303, 950), (305, 1000),
     (302, 1012), (150, 1012)],
]

# Seats, measured on the 1440 x 1152 interior (docs/LOUNGE_SCENE_DESIGN.md 7.8). cx, cy: where a sitter's
# butt rests - the middle of a seat cushion, a third of the way from its back edge to its front edge.
# facing: 'f' the left sofa (seen from the front), 'l' the right sofa (turned three-quarters toward
# the front-left: its seat edges run down to the right, its back cushions lean). scale: size there.
# blocks: seats that cannot be taken at the same time (the figures are wider than a cushion).
# The left sofa has three seat cushions (x 305-590, 590-780, 780-880); the third is too narrow and
# half under the right arm, so it is not used. The right sofa shows two seats (its right arm is
# outside the picture).
SEATS = [
    dict(id='s0', cx=447, cy=905, facing='f', scale=0.8, blocks=['s1']),
    dict(id='s1', cx=685, cy=898, facing='f', scale=0.8, blocks=['s0']),
    dict(id='s2', cx=1095, cy=918, facing='l', scale=0.8, blocks=['s3']),
    dict(id='s3', cx=1325, cy=965, facing='l', scale=0.88, blocks=['s2']),
]
# per facing: from the floor point in front of a seat (seats[].x, y: where a character stops and hops
# from) to the butt contact, scene px at scale 1 (rest up, dx right): for 'l' the character stands in
# front-left of the seat, the way the seat faces
SEAT_FACINGS = {'f': {'rest': 100, 'dx': 0}, 'l': {'rest': 90, 'dx': 40}}
# the angle (degrees, clockwise) of the cushion's front edge, for the contact shadow
SEAT_TILT = {'f': -1.5, 'l': 5.5}


def seats_json():
    out = []
    for s in SEATS:
        fc = SEAT_FACINGS[s['facing']]
        out.append({'id': s['id'], 'x': round(s['cx'] - fc['dx'] * s['scale']), 'y': round(s['cy'] + fc['rest'] * s['scale']),
                    'cx': s['cx'], 'cy': s['cy'], 'scale': s['scale'], 'facing': s['facing'],
                    'tilt': SEAT_TILT[s['facing']], 'blocks': s['blocks']})
    return out


SCENE = {
    'placeholder': False,
    'size': [W, H],
    'baselineY': 1118,             # walkers pass on the carpet in front of the sofas
    'horizonY': 560,
    'windowFacing': 225,
    'charScale': 1.25,
    'seatedInFront': True,         # seated characters sit on the cushion in front of the sofa front
    'seatFacings': SEAT_FACINGS,
    # The real animals (art/tools/build_character.py): each one passes by (left to right) or walks to a
    # seat, sits a while and leaves - one thing moving at a time (docs/LOUNGE_SCENE_DESIGN.md 7.7).
    'characters': ['tiger', 'rabbit', 'turtle'],
    'passEvery': [15, 45],           # seconds of quiet after each mover (walker, sitter, plane), then a random pick
    # shown first, right away, while their motion is reviewed: a name passes by, 'arrive:<name>' goes to a seat
    'preview': ['arrive:tiger'],
    'window': {'x': 700, 'y': 0, 'w': 740, 'h': 700},
    # painted row boundaries of the panel, top to bottom, each [[x_left, y], [x_right, y]]
    'board': {'x': 64, 'y': 101, 'w': 516, 'h': 398, 'rows': 6, 'textRows': 5,   # bottom row left empty
              'lines': [[[64, 100.7], [580, 208.6]], [[64, 160.9], [580, 258.9]], [[64, 222.0], [580, 308.7]], [[64, 282.1], [580, 359.5]], [[64, 343.2], [580, 413.4]], [[64, 406.3], [580, 465.1]], [[64, 449.4], [580, 497.9]]]},
    'seats': None,                 # filled from SEATS below
    'entries': {'left': -320, 'right': 1760},
    'lamps': [{'x': 120, 'y': 700, 'r': 520}, {'x': 660, 'y': 660, 'r': 460}],
    'floorLight': None,
    # a plane taxis past the window every `period` seconds, taking `duration` seconds.
    # As big as in the approved illustration: about half the picture wide, fuselage mid-window,
    # wheels hidden behind the sofas.
    'planes': None,                # filled from PLANES below
    # Weather (docs/LOUNGE_SCENE_DESIGN.md 13): overcast window plates cut like `outside`, crossfaded in
    # when it rains or snows; the rain and the snow are drawn live inside `rect` (scene px) and clipped
    # to the glass, i.e. to the alpha of the `outside` layer. Needs the plates in bg/.
    'weather': {'plates': {'rain': 'bg/outside_rain.webp', 'snow': 'bg/outside_snow.webp'}, 'rect': [700, 0, 740, 770], 'mask': 'outside'},
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
# Taxi lanes on the apron (docs/LOUNGE_SCENE_DESIGN.md 14). The plane is a pure side view, so it only
# moves along a lane: a straight line on the ground plane whose depth changes a little along the run.
#   horizon: screen y of the horizon the apron recedes to (measured on the plates: the ground lines
#            that run toward the right meet at about (1950, 480); the terminal windows sit at 480-520)
#   ref: a plane whose wheels touch screen y `ref.y` is `ref.h` tall; elsewhere its height follows
#        the distance below the horizon, (y - horizon) / (ref.y - horizon)
#   lane.y: wheel contact line at the start and the end of the run, in the direction of travel. The
#        art shows the nose toward the viewer, so a plane always comes a little nearer: end y > start y.
#   lane.haze: share of the apron's colour mixed into the sprite at the start and the end (farther = hazier)
#   lane.duration: seconds, from a constant ground speed (SPEED screen px/s at scale 1), so a far plane is
#        slower on screen than a near one; computed below
#   ground: where the wheels touch inside the sprite, as a fraction of its height from the top (the three
#        wheels sit at 0.945 / 0.97 / 0.99: the art is seen a little from the front and above)
PLANES = {'right': 'bg/plane_right.webp', 'left': 'bg/plane_left.webp',
          'period': 150, 'ground': 0.97, 'horizon': 475, 'ref': {'y': 690, 'h': 300},
          'lanes': [{'id': 'far', 'y': [592, 606], 'haze': [0.34, 0.30]},
                    {'id': 'near', 'y': [654, 677], 'haze': [0.2, 0.16]}],
          'margin': 30,
          # wheel hubs on each cut-out, as fractions of the image (cx, cy, rx, ry): spokes are drawn
          # on them and turn with the distance travelled, so the gear rolls
          'wheels': {'right': [[378, 385, 6, 10], [571, 375, 5, 8], [792, 398, 7, 9]],
                     'left': [[168, 394, 6.5, 8], [387, 371, 6, 9], [578, 381, 6, 9.5]]}}
SPEED = 24                                  # screen px per second at plane scale 1 (the near lane's end)
PLANE_ASPECT = 922 / 400                    # sprite width / height


def plane_lanes(p, window=(700, 1440)):
    """Fill in each lane's run time: constant ground speed, so the screen speed follows the scale."""
    out = []
    for lane in p['lanes']:
        s0, s1 = [(y - p['horizon']) / (p['ref']['y'] - p['horizon']) for y in lane['y']]
        half = 0.5 * PLANE_ASPECT * p['ref']['h'] * max(s0, s1) + p['margin']
        x0, x1 = window[0] - half, window[1] + half               # centre of the sprite from fully left to fully right
        secs = (x1 - x0) / (SPEED * (s1 - s0)) * math.log(s1 / s0) if abs(s1 - s0) > 1e-6 else (x1 - x0) / (SPEED * s0)
        out.append(dict(lane, duration=round(secs, 1)))
    return out


def mask_image(polys=None):
    m = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(m)
    for poly in (SOFA_FRONT if polys is None else polys):
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
    arms = mask_image(SOFA_ARMS)
    layers = {'outside': [], 'interior': [], 'sofaFront': [], 'sofaArms': []}
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
                arm = im.copy()
                arm.putalpha(Image.fromarray(np.minimum(np.asarray(arm.getchannel('A')), np.asarray(arms))))
                arm.save(bg / ('sofa_arms_%s.webp' % name), 'WEBP', quality=88, method=6)
                layers['sofaArms'].append({'elev': elev, 'file': 'bg/sofa_arms_%s.webp' % name})
    for kind in ('rain', 'snow'):         # the weather plates: cut and padded like the outside plates
        top = Image.open(SRC / ('outside_%s.webp' % kind)).convert('RGBA').resize((W, H0), Image.LANCZOS)
        a = np.asarray(top)
        Image.fromarray(np.concatenate([a, np.repeat(a[-1:], H - H0, axis=0)])).save(bg / ('outside_%s.webp' % kind), 'WEBP', quality=88, method=6)
    cut = Path(__file__).resolve().parent.parent / 'cutouts'
    for side in ('right', 'left'):
        im = Image.open(cut / ('plane_%s.png' % side)).convert('RGBA')
        im = im.resize((round(im.width * 400 / im.height), 400), Image.LANCZOS)
        im.save(bg / ('plane_%s.webp' % side), 'WEBP', quality=90, method=6)
    scene = dict(SCENE)
    scene['seats'] = seats_json()
    scene['planes'] = dict(PLANES)
    scene['planes']['lanes'] = plane_lanes(PLANES)
    scene['planes']['duration'] = max(l['duration'] for l in scene['planes']['lanes'])
    for side in ('right', 'left'):        # source px -> fractions of the cut-out
        im = Image.open(Path(__file__).resolve().parent.parent / 'cutouts' / ('plane_%s.png' % side))
        scene['planes']['wheels'] = dict(scene['planes']['wheels'])
        scene['planes']['wheels'][side] = [[round(cx / im.width, 4), round(cy / im.height, 4), round(rx / im.height, 4), round(ry / im.height, 4)]
                                           for cx, cy, rx, ry in PLANES['wheels'][side]]
    scene['layers'] = [
        {'id': 'outside', 'group': 'far', 'tint': False, 'variants': layers['outside']},
        {'id': 'interior', 'group': 'back', 'tint': False, 'variants': layers['interior']},
        {'id': 'sofaFront', 'group': 'mid', 'tint': False, 'cutFrom': 'interior', 'variants': layers['sofaFront']},
        # over seated characters (seatedInFront), under the aisle
        {'id': 'sofaArms', 'group': 'arms', 'tint': False, 'cutFrom': 'interior', 'variants': layers['sofaArms']},
    ]
    (out / 'scene.json').write_text(json.dumps(scene, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    total = sum(p.stat().st_size for p in bg.iterdir())
    print('wrote %d background files, %d KB' % (len(list(bg.iterdir())), total // 1024))


if __name__ == '__main__':
    main()
