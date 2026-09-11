#!/usr/bin/env python3
"""rel_made.py 결과의 PNG. 계산은 rel_made 에서 가져온다."""
import os, sys, collections
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
plt.rcParams['font.family'] = 'WenQuanYi Zen Hei'
plt.rcParams['axes.unicode_minus'] = False
import bot, persona as PS
from sb_calib import load, branch_of
from sb_114 import thresholds
from cf_402 import is_402
from rel_made import board_cat, CAT
from tag_draws import board_at

rows = load([os.path.join(D, 'collected.jsonl')])
for i in rows:
    i['_branch'] = branch_of(i)
    i['_v3'], i['_v2'], i['_pcz'] = thresholds(i)
mp = [i for i in rows if i['_branch']]
ga = [i for i in mp if is_402(i) and i.get('made', 0) == 0 and i['outs_true'] == 0]
for i in ga:
    bd = board_at(i['_board'], i['street'])
    i['_bd'] = bd
    i['_c7'] = bot.eval7(list(i['_hole']) + list(bd))[0] if (i['_hole'] and len(bd) >= 3) else 0
    mg = PS.sk(i['_prof'], 'range_merge') / 3.33
    i['_thr'] = max(0.28, 0.52 - 0.080 * mg)

FG, GR = '#1b1b1b', '#8a8a8a'
BLUE, RED, GREEN, GREY, ORA = '#2f6fb5', '#c1453c', '#3f8f5e', '#b9b9b9', '#d08a33'
fig = plt.figure(figsize=(13.5, 9.8), dpi=150, facecolor='white')
gs = fig.add_gridspec(2, 2, hspace=0.46, wspace=0.26,
                      left=0.075, right=0.975, top=0.855, bottom=0.075)
fig.suptitle('(가) made == 0 · 물리 outs == 0 인데 rel 이 높아 giveup 이 된 %d건' % len(ga),
             fontsize=15, color=FG, y=0.975)
fig.text(0.5, 0.936,
         'rel = relative_strength(plan.py:29) — eval7(hero+board) 로 상대 레인지 대비 승률 순위. '
         'made_strength 는 홀카드 기여가 없으면 0',
         ha='center', fontsize=10, color=GR)

# ① 핸드 구성 × rel
ax = fig.add_subplot(gs[0, 0])
COL = {0: ORA, 1: BLUE, 3: GREEN}
import random as _r; _r.seed(5)
for i in ga:
    ax.scatter(i['rel'], {0: 0, 1: 1, 3: 2}.get(i['_c7'], 0) + _r.uniform(-0.16, 0.16),
               s=62, color=COL.get(i['_c7'], GREY), alpha=0.82,
               edgecolor='white', lw=0.8, zorder=3)
ax.set_yticks([0, 1, 2])
ax.set_yticklabels(['하이카드 (%d)' % sum(1 for i in ga if i['_c7'] == 0),
                    '원페어 (%d)' % sum(1 for i in ga if i['_c7'] == 1),
                    '트립스 (%d)' % sum(1 for i in ga if i['_c7'] == 3)], fontsize=10)
ax.set_xlim(0.38, 0.85); ax.set_ylim(-0.6, 2.6)
ax.set_xlabel('rel — 상대 레인지 대비 현재 승률 순위', fontsize=10)
ax.set_title('① 전부 A-high / K-high 류다\n'
             '    원페어·트립스도 전부 보드가 만든 것 — 홀카드 기여 0건',
             fontsize=11, color=FG, loc='left')
ax.grid(alpha=0.25, lw=0.6)

# ② 얇은 밸류 게이트 — rel 은 통과, made 가 막는다
ax = fig.add_subplot(gs[0, 1])
xs = [i['_thr'] for i in ga]; ys = [i['rel'] for i in ga]
ax.scatter(xs, ys, s=62, color=BLUE, alpha=0.8, edgecolor='white', lw=0.8, zorder=3)
lim = [0.25, 0.85]
ax.plot(lim, lim, color=RED, lw=1.6, ls='--', zorder=2)
ax.text(0.62, 0.60, 'rel = 문턱', color=RED, fontsize=9, rotation=33)
ax.fill_between(lim, lim, 0.9, color=GREEN, alpha=0.07)
ax.text(0.30, 0.82, 'rel 조건 통과 구역', color=GREEN, fontsize=9.5)
ax.set_xlim(0.25, 0.60); ax.set_ylim(0.35, 0.88)
ax.set_xlabel('얇은 밸류 rel 문턱  max(0.28, 0.52 - 0.080×머징)', fontsize=10)
ax.set_ylabel('실제 rel', fontsize=10)
ax.set_title('② 얇은 밸류 게이트는 rel 로는 25/26 이 통과한다\n'
             '    막는 것은 뒤에 AND 로 붙은 `made >= 1` 하나뿐',
             fontsize=11, color=FG, loc='left')
ax.grid(alpha=0.25, lw=0.6)

# ③ 행동 층
ax = fig.add_subplot(gs[1, 0])
unres = [i for i in ga if (i.get('tocall') or 0) == 0]
res = [i for i in ga if (i.get('tocall') or 0) > 0]
grp = [('이니셔티브 있음\n지속벳 가능', [i for i in unres if i.get('init')]),
       ('이니셔티브 없음\n체크 고정', [i for i in unres if not i.get('init')]),
       ('저항 직면', res)]
labs = ['bet', 'check', 'call', 'fold']
cols = [GREEN, GREY, BLUE, RED]
for row, (nm, g) in enumerate(grp):
    if not g:
        continue
    c = collections.Counter(i.get('action') for i in g)
    left = 0
    for lb, cl in zip(labs, cols):
        v = c.get(lb, 0)
        if not v:
            continue
        ax.barh(row, v, left=left, color=cl, edgecolor='white', lw=1.2, height=0.55)
        ax.text(left+v/2, row, '%s\n%d' % (lb, v), ha='center', va='center',
                fontsize=9, color='white' if cl != GREY else FG)
        left += v
ax.set_yticks(range(len(grp))); ax.set_yticklabels([g[0] for g in grp], fontsize=9.5)
ax.invert_yaxis(); ax.set_xlabel('건수', fontsize=10)
ax.set_title('③ "포기 행동 계층"은 항상 체크가 아니다\n'
             '    이니셔티브가 있으면 지속벳 확률이 생긴다 (중앙 0.36)',
             fontsize=11, color=FG, loc='left')
ax.grid(axis='x', alpha=0.25, lw=0.6)

# ④ 계획 eq vs 응답 eq
ax = fig.add_subplot(gs[1, 1])
pe, re_, nd, names = [], [], [], []
for i in res:
    t = None
    for x in (i.get('trace') or []):
        if (x or {}).get('kind') == 'response' and x.get('street') == i['street']:
            t = x
    if not t:
        continue
    names.append('h%d' % i['_hand']); pe.append(i['eq'])
    re_.append(float(t.get('eq', 0))); nd.append(float(t['need']))
y = range(len(names))
for v, a, b in zip(y, pe, re_):
    ax.plot([a, b], [v, v], color=GR, lw=1.2, zorder=2)
ax.scatter(pe, list(y), s=56, color=GREY, edgecolor=FG, lw=0.7, zorder=3, label='계획 시점 eq')
ax.scatter(re_, list(y), s=56, color=BLUE, edgecolor=FG, lw=0.7, zorder=3, label='응답 시점 eq')
ax.scatter(nd, list(y), s=70, color=RED, marker='|', lw=2.2, zorder=4, label='need (필요 승률)')
ax.set_yticks(list(y)); ax.set_yticklabels(names, fontsize=9)
ax.set_xlim(0, 0.75); ax.set_xlabel('확률', fontsize=10)
ax.set_title('④ 계획 eq 와 응답 eq 는 다른 값이다 (중앙 -0.101)\n'
             '    팟오즈 판정은 응답 시점 eq 로만 해야 한다 — 7/8 콜, 1 폴드',
             fontsize=11, color=FG, loc='left')
ax.legend(fontsize=8.5, loc='lower right'); ax.grid(axis='x', alpha=0.25, lw=0.6)

out = os.path.join(D, 'tools', 'rel_made.png')
fig.savefig(out, facecolor='white')
print(out)
