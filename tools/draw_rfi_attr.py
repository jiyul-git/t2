#!/usr/bin/env python3
"""RFI_ATTRIBUTION_RESULT.md 의 그림. docs/RFI_ATTR_V1.png 를 만든다. 읽기 전용.

  (a) 회귀 격차 분해 — 0962cb2(동결 기준) → e17be45(RFI 직전) → ca418d2(RFI)
      수치: tools/rfi_ladder.py 결과 (문서 1절)
  (b) gto.rfi 새/옛 비율, 9맥스·ante=False (레시피 전 결정이 이 조건)
      + unopened 결정의 스택 깊이 분포 (tools/rfi_preflop_cf.py, 657건)
  (c) 채널 녹아웃 — arm × seed 지문 (tools/rfi_channel_split.py, 문서 3절)

(b) 의 비율은 --repo 의 gto 로 직접 계산한다 (옛 표는 git show e17be45:gto.py).

    python3 tools/draw_rfi_attr.py --repo <ca418d2 worktree> --out docs/RFI_ATTR_V1.png
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

FONT = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
fm.fontManager.addfont(FONT)
fp = fm.FontProperties(fname=FONT)
matplotlib.rcParams['font.family'] = fp.get_name()
matplotlib.rcParams['axes.unicode_minus'] = False

# (a) tools/rfi_ladder.py — seeds 3000-3005 × 30핸드
LADDER = [('0962cb2\n동결 기준', 283, 1368, 165, 85),
          ('e17be45\nRFI 직전', 315, 1379, 167, 100),
          ('ca418d2\nRFI 변경', 317, 1380, 167, 101)]

# unopened 결정의 스택 깊이 분포 (ca418d2 궤적, 657건). 구간 상한 bb
DEPTH_HIST = [(40, 6), (70, 12), (100, 25), (130, 57), (160, 389), (190, 87),
              (220, 32), (260, 21), (400, 28)]

# (c) tools/rfi_channel_split.py. N=ca418d2 지문, O=e17be45 지문, x=둘 다 아님
KO = [('ALL_OLD', 'OOOOOO'), ('ALL_NEW', 'NNNNNN'),
      ('ONLY_OPEN_DEC', 'xxOxxx'), ('ONLY_DEF_DEC', 'OOOOOO'),
      ('ONLY_PF_RANGE', 'OOOOOO'), ('ONLY_POST_RANGE', 'xxNxxO'),
      ('ONLY_OBS', 'OOOOOO'), ('DROP_OPEN_DEC', 'xxNxxO'),
      ('DROP_DEF_DEC', 'NNNNNN'), ('DROP_PF_RANGE', 'NNNNNN'),
      ('DROP_POST_RANGE', 'xxOxxx'), ('DROP_OBS', 'NNNNNx')]


def ratio_grid(repo):
    sys.path.insert(0, repo)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import gto as G
    import table as TB
    import rfi_decision_cf as M
    old = M.old_tables(repo)
    cur = {t: getattr(G, t) for t in M.TABLES}
    _, pre, _ = TB.orders(9)
    pos = [p for p in pre if p != 'BB']
    bbs = list(range(20, 361, 5))
    grid = []
    for p in pos:
        row = []
        for b in bbs:
            n = G.rfi(p, 9, b, False)
            for t in M.TABLES:
                setattr(G, t, old[t])
            o = G.rfi(p, 9, b, False)
            for t in M.TABLES:
                setattr(G, t, cur[t])
            row.append(n / o if o else 1.0)
        grid.append(row)
    return pos, bbs, grid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--out', default='docs/RFI_ATTR_V1.png')
    a = ap.parse_args()
    pos, bbs, grid = ratio_grid(a.repo)

    fig = plt.figure(figsize=(15, 10.5), dpi=130)
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.05], hspace=0.38, wspace=0.22)

    # (a)
    ax = fig.add_subplot(gs[0, 0])
    labs = [x[0] for x in LADDER]
    vp = [100.0 * x[1] / x[2] for x in LADDER]
    pf = [100.0 * x[3] / x[2] for x in LADDER]
    fl = [100.0 * x[4] / 180 for x in LADDER]
    xs = range(len(LADDER))
    w = 0.26
    for off, ys, lab, col in ((-w, vp, 'VPIP', '#3a6ea5'), (0, pf, 'PFR', '#999999'),
                              (w, fl, 'flop', '#d9822b')):
        bars = ax.bar([x + off for x in xs], ys, w, label=lab, color=col)
        for b_, y in zip(bars, ys):
            ax.text(b_.get_x() + b_.get_width() / 2, y + 0.6, '%.1f' % y,
                    ha='center', fontsize=9)
    ax.set_xticks(list(xs))
    ax.set_xticklabels(labs, fontsize=10)
    ax.set_ylabel('%')
    ax.set_ylim(0, 65)
    ax.legend(loc='upper left', fontsize=9, ncol=3)
    ax.set_title('(a) 회귀 격차 분해: 격차의 대부분은 RFI 커밋 이전에 이미 있었다\n'
                 'VPIP +34건 중 RFI +2 / flop +16핸드 중 RFI +1 / PFR +2 중 RFI 0',
                 fontsize=11)

    # (b)
    ax = fig.add_subplot(gs[0, 1])
    im = ax.imshow(grid, aspect='auto', cmap='RdBu', vmin=0.8, vmax=1.2,
                   extent=[bbs[0], bbs[-1], len(pos) - 0.5, -0.5])
    ax.set_yticks(range(len(pos)))
    ax.set_yticklabels(pos, fontsize=9)
    ax.set_xlabel('유효 스택 (bb)')
    cb = fig.colorbar(im, ax=ax, orientation='horizontal', fraction=0.05,
                      pad=0.16)
    cb.set_label('새 RFI / 옛 RFI  (파랑=넓어짐, 빨강=좁아짐)', fontsize=9)
    ax2 = ax.twinx()
    lo = 20
    for hi, n in DEPTH_HIST:
        hi_ = min(hi, bbs[-1])
        ax2.bar((lo + hi_) / 2, n, hi_ - lo, color='k', alpha=0.18,
                edgecolor='k', linewidth=0.4)
        lo = hi_
    ax2.set_ylabel('unopened 결정 수 (657건)', fontsize=9)
    ax2.set_ylim(0, 1300)
    ax.set_title('(b) 9맥스·ante=False 에서 새/옛 비율: 150–170bb 에서 부호가 바뀐다\n'
                 '결정의 59% 가 130–160bb 에 몰려 있어 넓힘과 좁힘이 거의 상쇄',
                 fontsize=11)

    # (c)
    ax = fig.add_subplot(gs[1, :])
    ax.set_xlim(0, 10.2)
    ax.set_ylim(len(KO) + 0.5, -1.2)
    ax.axis('off')
    col = {'O': '#cfd8e3', 'N': '#f2c58c', 'x': '#c0504d'}
    for j, sd in enumerate(range(3000, 3006)):
        ax.text(1.9 + j * 0.9, -0.6, str(sd), ha='center', fontsize=10,
                fontweight='bold')
    for i, (arm, sig) in enumerate(KO):
        ax.text(1.35, i, arm, ha='right', va='center', fontsize=10)
        for j, ch in enumerate(sig):
            ax.add_patch(plt.Rectangle((1.5 + j * 0.9, i - 0.4), 0.8, 0.8,
                                       color=col[ch]))
            ax.text(1.9 + j * 0.9, i, {'O': '옛', 'N': '새', 'x': '혼합'}[ch],
                    ha='center', va='center', fontsize=9)
    ax.text(8.75, 0.5,
            '채널 (호출 스택 기준)\n\n'
            'OPEN_DEC  open/iso 결정의 _open\n'
            'DEF_DEC   defend_decision 의 역치\n'
            'PF_RANGE  프리플랍 중 상대 레인지 모델\n'
            'POST_RANGE 포스트플랍 my_r / opp_r\n'
            'OBS       book.observe_preflop 기대 RFI\n\n'
            '단독 효과: OPEN_DEC, POST_RANGE 둘뿐\n'
            'DEF_DEC · PF_RANGE · OBS 단독 = 옛 지문\n'
            '3005 는 OBS 까지 셋이 겹쳐야 새 지문',
            ha='center', va='top', fontsize=9.5, linespacing=1.45,
            bbox=dict(boxstyle='round', fc='#f7f7f7', ec='#999999'))
    ax.set_title('(c) 채널 녹아웃 — 각 arm 은 해당 채널만 새 표(ONLY) 또는 해당 채널만 옛 표(DROP)',
                 fontsize=11, loc='left')

    fig.savefig(a.out, bbox_inches='tight')
    print('wrote', a.out)


if __name__ == '__main__':
    main()
