#!/usr/bin/env python3
"""Check pictures for the turns (art/README.md "돌아서기"), read from the built character
(ui/web/lounge/assets/chars/<name>/{atlas.webp, manifest.json}):

- art/cutouts/turns/<name>_turn_8x.png: every turn in-between at 8x nearest-neighbour, between the walk frame
  before it and the standing frame after it (on mid grey, feet on one line), to check the pixels;
- art/cutouts/turns/<name>_<facing>.gif: walk -> turn -> stand -> turn back -> walk, at atlas size, 12 fps.

    python3 art/tools/turn_preview.py [tiger rabbit turtle]
"""
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CHARS = ROOT / 'ui/web/lounge/assets/chars'
OUT = ROOT / 'art/cutouts/turns'
BG = (128, 128, 128, 255)


def load(name):
    man = json.loads((CHARS / name / 'manifest.json').read_text())
    return man, Image.open(CHARS / name / man['atlas']).convert('RGBA')


def crop(atlas, f):
    return atlas.crop((f['x'], f['y'], f['x'] + f['w'], f['y'] + f['h']))


def contact(name, man, atlas, zoom=8):
    """the walk frame, every distinct turn in-between and the standing frame of the first turn of each facing"""
    order, seen = [], set()
    for cid, c in man['clips'].items():
        if cid.split('@')[0] in ('turn_r_front', 'turn_l_front') and len(set(c['frames'])) > 1:
            for i in c['frames']:
                f = man['frames'][i]
                if (f['x'], f['y']) not in seen:          # the same picture under another frame index
                    seen.add((f['x'], f['y']))
                    order.append(i)
    fr = [man['frames'][i] for i in order]
    up = max(f['ay'] for f in fr)
    down = max(f['h'] - f['ay'] for f in fr)
    W = sum(f['w'] for f in fr) + 4 * (len(fr) + 1)
    sheet = Image.new('RGBA', (W, up + down + 8), BG)
    x = 4
    for f in fr:
        im = crop(atlas, f)
        sheet.alpha_composite(im, (x, 4 + up - f['ay']))
        x += f['w'] + 4
    sheet = sheet.resize((sheet.width * zoom, sheet.height * zoom), Image.NEAREST)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / ('%s_turn_8x.png' % name)
    sheet.convert('RGB').save(p, optimize=True)
    return p, order


def gif(name, man, atlas, facing):
    """walk_r in, turn to the seat's standing pose, hold, turn back to walk_l, walk out (12 fps)"""
    sx = '' if facing == 'f' else '@' + facing
    stand = 'stand_front' if facing == 'f' else 'stand' + sx
    clips = man['clips']
    adv = clips['walk_r'].get('advance', 12)
    seq = []                                   # (frame index, x of the anchor)
    x = 60
    for i in clips['walk_r']['frames'] * 2:
        seq.append((i, x)); x += adv
    for i in clips['turn_r_front' + sx]['frames']:
        seq.append((i, x))
    seq += [(man['poses'][stand], x)] * 10
    for i in clips['turn_front_l' + sx]['frames']:
        seq.append((i, x))
    for i in clips['walk_l']['frames'] * 2:
        x -= adv; seq.append((i, x))
    fr = man['frames']
    up = max(fr[i]['ay'] for i, _ in seq)
    down = max(fr[i]['h'] - fr[i]['ay'] for i, _ in seq)
    left = min(x0 - fr[i]['ax'] for i, x0 in seq)
    right = max(x0 - fr[i]['ax'] + fr[i]['w'] for i, x0 in seq)
    W, H = right - left + 20, up + down + 20
    ims = []
    for i, x0 in seq:
        f = fr[i]
        c = Image.new('RGBA', (W, H), BG)
        c.alpha_composite(crop(atlas, f), (x0 - f['ax'] - left + 10, 10 + up - f['ay']))
        ims.append(c.convert('RGB').quantize(colors=255, method=Image.MEDIANCUT, dither=Image.NONE))
    p = OUT / ('%s_%s.gif' % (name, facing))
    ims[0].save(p, save_all=True, append_images=ims[1:], duration=83, loop=0, optimize=False, disposal=1)
    return p


def main():
    names = sys.argv[1:] or ['tiger', 'rabbit', 'turtle']
    for name in names:
        man, atlas = load(name)
        p, order = contact(name, man, atlas)
        print(p.relative_to(ROOT), 'frames', order)
        for facing in man['facings']:
            print(gif(name, man, atlas, facing).relative_to(ROOT))


if __name__ == '__main__':
    main()
