#!/usr/bin/env python3
"""Numbers for every turn clip of the built characters (art/README.md "돌아서기 v3"):

- head size: the face (head_lead.face_size: fur / skin blob, ears and hats left out) of each picture: sqrt(area); the change between
  consecutive pictures in % (limit 2 % on sqrt(area); height and width are listed - they change with the angle);
- colour: the biggest per-region ΔE between consecutive pictures (color_match.delta);
- props: gap from each prop to its paw and its number of pieces, per turn view, from the build
  (art/cutouts/turns/<name>_props.json).

    python3 art/tools/turn_check.py [tiger rabbit turtle] [--md OUT.md]

Exits 1 if a head step is over 2 %, a prop gap over 1 px or a prop in more than one piece.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import color_match   # noqa: E402
import head_lead     # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HEAD_MAX, GAP_MAX = 2.0, 1.0


def main():
    args = sys.argv[1:]
    md = None
    if '--md' in args:
        i = args.index('--md'); md = args[i + 1]; del args[i:i + 2]
    names = args or ['tiger', 'rabbit', 'turtle']
    rows, bad = [], 0
    worst = dict(head=0.0, gap=0.0, de=0.0)
    for name in names:
        d = ROOT / 'ui/web/lounge/assets/chars' / name
        man = json.loads((d / 'manifest.json').read_text())
        at = np.asarray(Image.open(d / man['atlas']).convert('RGBA')).astype(np.float32)
        pic = lambda i: (lambda f: at[f['y']:f['y'] + f['h'], f['x']:f['x'] + f['w']])(man['frames'][i])
        size = {}

        def head(i):
            if i not in size:
                size[i] = head_lead.face_size(pic(i), name)
            return size[i]
        for cid, c in man['clips'].items():
            if not cid.startswith('turn_') or not cid.split('@')[0].endswith('_front'):
                continue
            seq = [i for j, i in enumerate(c['frames']) if j == 0 or c['frames'][j - 1] != i]
            if len(seq) < 2:
                continue
            hs, de = [], []
            for x, y in zip(seq, seq[1:]):
                a, b = head(x), head(y)
                hs.append(abs(b[0] / a[0] - 1) * 100)
                de.append(max(color_match.delta(pic(x), pic(y), name).values()))
            hmax, dmax = max(hs), max(de)
            worst['head'] = max(worst['head'], hmax)
            worst['de'] = max(worst['de'], dmax)
            bad += hmax > HEAD_MAX
            rows.append('| %s | `%s` | %s | %s | %.1f | %.2f |' % (
                name, cid, ' '.join(str(i) for i in seq), ' '.join('%.0f' % head(i)[0] for i in seq), hmax, dmax))
        pj = ROOT / 'art/cutouts/turns' / ('%s_props.json' % name)
        if pj.is_file():
            for view, props in sorted(json.loads(pj.read_text()).items()):
                for prop, (gap, pieces) in sorted(props.items()):
                    worst['gap'] = max(worst['gap'], gap)
                    bad += gap > GAP_MAX or pieces != 1
                    rows.append('| %s | prop `%s` on `%s` | | gap %.1f px, %d piece(s) | | |' % (name, prop, view, gap, pieces))
    head_ = '| 동물 | 클립 / 소품 | 그림(프레임 번호) | 머리 크기 √면적 px | 머리 최대 변화 % | 최대 ΔE |\n|---|---|---|---|---|---|'
    text = head_ + '\n' + '\n'.join(rows) + '\n\nmax head %.1f %% (limit %.0f), max prop gap %.1f px (limit %.0f), max dE %.2f\n' % (
        worst['head'], HEAD_MAX, worst['gap'], GAP_MAX, worst['de'])
    print(text)
    if md:
        Path(md).write_text(text)
    return bad == 0


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
