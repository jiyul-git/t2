#!/usr/bin/env python3
"""Numbers for every turn clip of the built characters (art/README.md "돌아서기 v3"):

- head size: the face (head_lead.face_size: fur / skin blob, ears and hats left out) of each picture: sqrt(area); the change between
  consecutive pictures in % (limit 2 % on sqrt(area); height and width are listed - they change with the angle);
- colour: the biggest per-region ΔE between consecutive pictures (color_match.delta);
- props: gap from each prop to its paw and its number of pieces, per turn view, from the build
  (art/cutouts/turns/<name>_props.json).

    python3 art/tools/turn_check.py [tiger rabbit turtle] [--md OUT.md]

- pixels (every picture of every turn clip that is not a walk frame): stray islands (separate alpha pieces under
  30 px), outline breaks (silhouette edge px lighter than the outline, lum > 110) and spurs / stair steps (edge px
  with three or four transparent neighbours), against the walk frame of the same clip as the baseline;
- logo (tiger): the chest "T2" - the biggest gold blob on the hoodie in the upper body - must be one mark of 0.5-1.4x (a 3/4 chest shows it narrower)
  the walk frame's px count, in at most 4 pieces (T, 2 and the anti-aliased ends the walk frame also has), wherever it is drawn.

Exits 1 if a head step is over 2 %, a prop gap over 1 px or a prop in more than one piece, a new picture has a stray
island or more outline breaks / spurs than its walk frame (+10 %), or a logo is out of tolerance.
"""
import cv2
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import color_match   # noqa: E402
import head_lead     # noqa: E402
import props         # noqa: E402


def pixels(a):
    """(stray islands, outline breaks, spurs) of a picture"""
    al = a[..., 3] > 0
    n, lab, st, _ = cv2.connectedComponentsWithStats(al.astype(np.uint8), connectivity=8)
    stray = int((st[1:, cv2.CC_STAT_AREA] < 30).sum()) if n > 2 else 0
    cl = np.pad(~al, 1, constant_values=True).astype(np.uint8)
    nb = cl[:-2, 1:-1] + cl[2:, 1:-1] + cl[1:-1, :-2] + cl[1:-1, 2:]
    edge = al & (nb > 0)
    light = int((edge & (a[..., :3].mean(-1) > 110)).sum())
    spur = int((al & (nb >= 3)).sum())
    return stray, light, spur


def logo(a):
    """(px, pieces) of the chest T2: the gold letters (props.logo_mask) in the upper 62 % of the figure, the mark nearest
    the middle of the chest (the sleeve T2 of a walk frame is the other one)"""
    op = a[..., 3] > 200
    ys, xs = np.nonzero(op)
    g = props.logo_mask(a, head_lead.cloth)
    g[int(ys.min() + 0.62 * (ys.max() - ys.min())):] = False
    n, lab, st, cen = cv2.connectedComponentsWithStats(cv2.dilate(g.astype(np.uint8), np.ones((5, 5), np.uint8)), connectivity=8)
    cand = [i for i in range(1, n) if (g & (lab == i)).sum() >= 8 and cen[i][1] > ys.min() + 0.45 * (ys.max() - ys.min())]
    if not cand:
        return 0, 0
    mx = (xs.min() + xs.max()) / 2
    i = min(cand, key=lambda i: abs(cen[i][0] - mx))
    mark = g & (lab == i)
    return int(mark.sum()), cv2.connectedComponents(mark.astype(np.uint8), connectivity=8)[0] - 1


ROOT = Path(__file__).resolve().parents[2]
HEAD_MAX, GAP_MAX = 2.0, 1.0


def main():
    args = sys.argv[1:]
    md = None
    if '--md' in args:
        i = args.index('--md'); md = args[i + 1]; del args[i:i + 2]
    names = args or ['tiger', 'rabbit', 'turtle']
    rows, bad, pix = [], 0, []
    worst = dict(head=0.0, gap=0.0, de=0.0, stray=0)
    for name in names:
        d = ROOT / 'ui/web/lounge/assets/chars' / name
        man = json.loads((d / 'manifest.json').read_text())
        at = np.asarray(Image.open(d / man['atlas']).convert('RGBA')).astype(np.float32)
        pic = lambda i: (lambda f: at[f['y']:f['y'] + f['h'], f['x']:f['x'] + f['w']])(man['frames'][i])
        size = {}
        walkers = set(man['clips']['walk_r']['frames']) | set(man['clips']['walk_l']['frames'])
        done = set()
        ref_logo = logo(pic(man['clips']['walk_r']['frames'][0])) if name == 'tiger' else None

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
            walk0 = seq[0] if cid.startswith('turn_r') or cid.startswith('turn_l') else seq[-1]
            base = pixels(pic(walk0))
            for i in seq:
                if i in walkers or i in done:
                    continue
                done.add(i)
                st_, li, sp = pixels(pic(i))
                ok = st_ == 0 and li <= base[1] * 1.1 and sp <= base[2] * 1.1
                lg = ''
                if name == 'tiger':
                    lp, lpc = logo(pic(i))
                    ok &= 0.5 * ref_logo[0] <= lp <= 1.4 * ref_logo[0] and lpc <= 4
                    lg = 'T2 %d px / %d pc (walk %d)' % (lp, lpc, ref_logo[0])
                bad += not ok
                worst['stray'] = max(worst['stray'], st_)
                pix.append('| %s | %d | %d | %d (walk %d) | %d (walk %d) | %s | %s |' % (name, i, st_, li, base[1], sp, base[2], lg, 'ok' if ok else 'FAIL'))
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
    text += '\n| 동물 | 그림 | 떨어진 조각 | 윤곽 끊김(밝은 가장자리 px) | 계단·돌기 px | 로고 | 판정 |\n|---|---|---|---|---|---|---|\n' + '\n'.join(pix) + '\n'
    print(text)
    if md:
        Path(md).write_text(text)
    return bad == 0


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
