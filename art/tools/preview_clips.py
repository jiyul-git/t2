#!/usr/bin/env python3
"""Play a lounge character's clips from its atlas + manifest into a GIF, and 8x check sheets of its pictures.

    python3 art/tools/preview_clips.py penguin OUTDIR

Writes OUTDIR/sit_<facing>.gif for every seat facing of the character: it walks in (from the left for 'f',
from the right for 'l'), turns, sits down, sits (with a blink), sips, waves, stands up, turns and walks out,
drawn the way the renderer places frames (anchor on the floor point; walking advances `advance` px a frame),
at half the scene size on a mid-grey floor; and OUTDIR/check_8x_sit_<facing>.png: 8x nearest-neighbour crops
(outline at the top, flipper, cup, feet) of every distinct picture of the seated clips of that facing.
"""
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
BG = (128, 134, 140)
FLOOR = (104, 108, 114)


def load(name):
    d = ROOT / 'ui/web/lounge/assets/chars' / name
    man = json.loads((d / 'manifest.json').read_text())
    return man, Image.open(d / man['atlas']).convert('RGBA')


def frame_img(atlas, man, i, face=None):
    f = man['frames'][i]
    im = atlas.crop((f['x'], f['y'], f['x'] + f['w'], f['y'] + f['h']))
    if face and f.get('v', {}).get(face) is not None:
        p = man['frames'][f['v'][face]]
        patch = atlas.crop((p['x'], p['y'], p['x'] + p['w'], p['y'] + p['h']))
        im = im.copy()
        im.alpha_composite(patch, (f['ax'] - p['ax'], f['ay'] - p['ay']))
    return im, f['ax'], f['ay']


def sequence(man, facing):
    """[(clip id, frame index, x offset in atlas px, face)] for a whole visit at one seat facing"""
    sfx = '' if facing == 'f' else '@' + facing
    c = man['clips']
    side = 'r' if facing == 'f' else 'l'
    walk_in, walk_out = c['walk_' + side], c['walk_' + ('l' if side == 'r' else 'r')]
    adv_in = walk_in['advance'] / man['scale'] / 1.25          # scene px -> atlas px
    out = []
    n_in = 3 * len(walk_in['frames'])
    for k in range(n_in):                                       # walk in, ending on the seat's floor point
        out.append(('walk', walk_in['frames'][k % len(walk_in['frames'])], (k - n_in) * adv_in * (1 if side == 'r' else -1), None))
    for cid in ['turn_%s_front' % side, 'sit_down']:
        out += [(cid, i, 0, None) for i in c[cid + sfx if cid != 'walk' else cid]['frames']]
    idle = c['sit_idle' + sfx]['frames']
    out += [('sit_idle', i, 0, 'blink' if 6 <= k <= 7 else None) for k, i in enumerate(idle[:16])]
    for cid in ('eat_in', 'eat_loop', 'eat_out', 'wave'):
        if cid + sfx in c:
            fr = c[cid + sfx]['frames'][:16]
            out += [(cid, i, 0, None) for i in fr]
    for cid in ['stand_up', 'turn_front_' + ('l' if side == 'r' else 'r')]:
        out += [(cid, i, 0, None) for i in c[cid + sfx]['frames']]
    adv_out = walk_out['advance'] / man['scale'] / 1.25
    for k in range(2 * len(walk_out['frames'])):
        out.append(('walk', walk_out['frames'][k % len(walk_out['frames'])], (k + 1) * adv_out * (-1 if side == 'r' else 1), None))
    return out


def gif(man, atlas, facing, path):
    seq = sequence(man, facing)
    imgs = [frame_img(atlas, man, i, face) for _, i, _, face in seq]
    xs = [x for _, _, x, _ in seq]
    left = int(min(x - ax for (_, ax, _), x in zip(imgs, xs))) - 4
    right = int(max(x - ax + im.width for (im, ax, _), x in zip(imgs, xs))) + 4
    top = int(min(-ay for (_, _, ay) in imgs)) - 4
    bottom = int(max(im.height - ay for (im, _, ay) in imgs)) + 4
    W, H = right - left, bottom - top
    frames = []
    for (im, ax, ay), x in zip(imgs, xs):
        bg = Image.new('RGBA', (W, H), BG + (255,))
        ImageDraw.Draw(bg).rectangle((0, -top, W, H), fill=FLOOR + (255,))
        bg.alpha_composite(im, (int(round(x - ax - left)), int(-ay - top)))
        frames.append(bg.convert('RGB').resize((W // 2, H // 2), Image.LANCZOS))
    pal = frames[0].quantize(colors=255, method=Image.MEDIANCUT, dither=Image.NONE)
    q = [f.quantize(palette=pal, dither=Image.NONE) for f in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=1000 // 10, loop=0, disposal=1, optimize=False)
    return len(frames)


def check_sheet(man, atlas, facing, path):
    """8x crops of every distinct picture (by atlas rectangle) of the seated clips at this facing"""
    import build_penguin_walk as P
    sfx = '' if facing == 'f' else '@' + facing
    seen, rows = set(), []
    for cid in ('sit_down', 'sit_idle', 'eat_in', 'eat_loop', 'wave', 'doze_loop', 'doze_loop_b'):
        c = man['clips'].get(cid + sfx)
        if not c:
            continue
        for i in c['frames']:
            f = man['frames'][i]
            key = (f['x'], f['y'])
            if key in seen or i < len(man['clips']['walk_r']['frames']) * 4:    # the walker's own frames are checked with the walk
                continue
            seen.add(key)
            im, _, _ = frame_img(atlas, man, i)
            a = np.asarray(im).astype(np.float32)
            cs, S = P.crops(a)
            bg = Image.new('RGBA', im.size, BG + (255,)); bg.alpha_composite(im)
            K = 8
            row = Image.new('RGB', (len(cs) * (S * K + 8), S * K), (40, 40, 40))
            for j, (_, (x, y)) in enumerate(cs):
                row.paste(bg.crop((x, y, x + S, y + S)).convert('RGB').resize((S * K, S * K), Image.NEAREST), (j * (S * K + 8), 0))
            rows.append(row)
    W = max(r.width for r in rows)
    sheet = Image.new('RGB', (W, len(rows) * (rows[0].height + 8)), (40, 40, 40))
    for k, r in enumerate(rows):
        sheet.paste(r, (0, k * (r.height + 8)))
    sheet.save(path, optimize=True)
    return len(rows)


if __name__ == '__main__':
    name, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    man, atlas = load(name)
    for facing in man.get('facings', ['f']):
        n = gif(man, atlas, facing, out / ('sit_%s.gif' % facing))
        k = check_sheet(man, atlas, facing, out / ('check_8x_sit_%s.png' % facing))
        print('%s %s: %d GIF frames, %d pictures checked' % (name, facing, n, k))
