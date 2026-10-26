#!/usr/bin/env python3
"""Colour / value match of the turn views to the walk frames, and the check that keeps it so (art/README.md "돌아서기").

regions(a, kind): masks of the picture's colour regions - 'fur' (fur / skin), 'cloth' (the main garment; the
    turtle's shell backpack is 'shell'), 'line' (dark outline px) - from head_lead.cloth / props.skin and lightness.
match(a, ref, kind): a with each region's CIE Lab mean and spread moved to those of the same region in ref (the
    walk frame next to it); px outside every region are left alone.
delta(a, b, kind): {region: ΔE76 between the region means of a and b}.

    python3 art/tools/color_match.py [tiger rabbit turtle] [--max 6]

checks every turn and walk clip of the built characters: ΔE of every region between consecutive distinct pictures
must stay under --max (default 6.0; a just noticeable step is about 2-3, the walk loop itself moves 0.1-1.5).
Prints the biggest step per clip and exits 1 if any is over.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import head_lead   # noqa: E402
import props       # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
REGIONS = ('fur', 'cloth', 'shell', 'line')


def lab(rgb):
    return cv2.cvtColor((rgb / 255.).astype(np.float32), cv2.COLOR_RGB2Lab)


def regions(a, kind):
    rgb = a[..., :3]
    op = a[..., 3] > 200
    L = lab(rgb)[..., 0]
    line = op & (L < 22)
    cloth = op & head_lead.cloth(rgb, kind) & ~line
    fur = op & props.skin(rgb, kind) & ~line & ~cloth
    out = dict(fur=fur, cloth=cloth, line=line)
    if kind == 'turtle':     # navy jacket and brown shell apart: how much of each shows changes with the angle
        r, b = rgb[..., 0].astype(np.float32), rgb[..., 2].astype(np.float32)
        out['cloth'], out['shell'] = cloth & (b > r), cloth & (b <= r) & (L < 45)   # gold patterns (lighter) left out
    return out


def stats(a, kind):
    L = lab(a[..., :3])
    out = {}
    floor = 0.02 * (a[..., 3] > 200).sum()      # a region under 2 % of the figure is too few px for a stable mean
    for k, m in regions(a, kind).items():
        if m.sum() > max(50, floor):
            out[k] = (L[m].mean(0), L[m].std(0))
    return out


def match(a, ref, kind):
    sr, sa = stats(ref, kind), stats(a, kind)
    L = lab(a[..., :3])
    out = a.copy()
    for k, m in regions(a, kind).items():
        if k not in sr or k not in sa:
            continue
        (mr, dr), (ma, da) = sr[k], sa[k]
        g = np.clip(dr / np.maximum(da, 1e-3), 0.7, 1.4)
        L[m] = (L[m] - ma) * g + mr
    rgb = cv2.cvtColor(L.astype(np.float32), cv2.COLOR_Lab2RGB) * 255.
    for k, m in regions(a, kind).items():
        out[m, :3] = rgb[m].clip(0, 255)
    return out


def delta(a, b, kind):
    sa, sb = stats(a, kind), stats(b, kind)
    return {k: float(np.linalg.norm(sa[k][0] - sb[k][0])) for k in REGIONS if k in sa and k in sb}


def check(names, limit):
    bad, worst = 0, 0.0
    for name in names:
        d = ROOT / 'ui/web/lounge/assets/chars' / name
        man = json.loads((d / 'manifest.json').read_text())
        at = np.asarray(Image.open(d / man['atlas']).convert('RGBA')).astype(np.float32)
        pic = lambda i: (lambda f: at[f['y']:f['y'] + f['h'], f['x']:f['x'] + f['w']])(man['frames'][i])
        kind = man.get('walker') and name
        for cid, c in man['clips'].items():
            if not (cid.startswith('turn_') or cid.startswith('walk_')):
                continue
            seq = [i for j, i in enumerate(c['frames']) if j == 0 or c['frames'][j - 1] != i]
            top, where = 0.0, ''
            for x, y in zip(seq, seq[1:]):
                for k, v in delta(pic(x), pic(y), kind).items():
                    if v > top:
                        top, where = v, '%d->%d %s' % (x, y, k)
            worst = max(worst, top)
            flag = 'OVER' if top > limit else 'ok'
            bad += top > limit
            print('%-7s %-16s max dE %5.2f  %s  %s' % (name, cid, top, where, flag))
    print('max dE %.2f (limit %.1f), %d clip(s) over' % (worst, limit, bad))
    return bad == 0


if __name__ == '__main__':
    args = sys.argv[1:]
    limit = 6.0
    if '--max' in args:
        i = args.index('--max'); limit = float(args[i + 1]); del args[i:i + 2]
    sys.exit(0 if check(args or ['tiger', 'rabbit', 'turtle'], limit) else 1)
