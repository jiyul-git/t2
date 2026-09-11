#!/usr/bin/env python3
"""sb_calib.py / sb_114.py 의 측정 결과를 PNG 로 낸다. 분석은 하지 않는다."""
import os, sys, math, collections
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'WenQuanYi Zen Hei'
plt.rcParams['axes.unicode_minus'] = False
import persona as PS
from sb_calib import load, branch_of, p_formula, river_odds
from sb_114 import thresholds

rows = load([os.path.join(D, 'collected.jsonl')])
for i in rows:
    i['_branch'] = branch_of(i)
    i['_sk'] = PS.sk(i['_prof'], 'semibluff') / 3.33
    i['_v3'], i['_v2'], i['_pcz'] = thresholds(i)
mp = [i for i in rows if i['_branch']]
gate = lambda i: i['outs'] >= 8 and i.get('behind', 0) <= 1 and i['_sk'] >= 0.4
cand = [i for i in mp if gate(i)]
rolled = [i for i in cand if i['_branch'] != 'above']
took = [i for i in rolled if i['_branch'] == 'semibluff']
g3 = [i for i in rolled if i['_branch'] != 'semibluff' and i['outs_true'] >= 8]

def corr(xs, ys):
    n = len(xs); mx, my = sum(xs)/n, sum(ys)/n
    sx = math.sqrt(sum((x-mx)**2 for x in xs)); sy = math.sqrt(sum((y-my)**2 for y in ys))
    return 0.0 if sx == 0 or sy == 0 else sum((x-mx)*(y-my) for x, y in zip(xs, ys))/(sx*sy)
_ps = [p_formula(i['_sk']) for i in rolled]
_ro = [river_odds(i['outs_true'], i['street']) for i in rolled]
CORR = corr(_ps, _ro)
TSTAT = CORR*math.sqrt(len(rolled)-2)/math.sqrt(max(1e-9, 1-CORR*CORR))

FG, GR = '#1b1b1b', '#8a8a8a'
BLUE, RED, GREY, GREEN, ORA = '#2f6fb5', '#c1453c', '#b9b9b9', '#3f8f5e', '#d08a33'
fig = plt.figure(figsize=(13.5, 9.8), dpi=150, facecolor='white')
gs = fig.add_gridspec(2, 2, hspace=0.46, wspace=0.26,
                      left=0.075, right=0.975, top=0.855, bottom=0.075)
fig.suptitle('세미블러프 확률식  p = min(0.95, 0.25 + 0.24 × 개념)  실측 분해',
             fontsize=15, color=FG, y=0.975)
fig.text(0.5, 0.936,
         '봇 대전 1,000핸드 · make_plan 원본 레코드(eq_sims=400) 1,047건 · '
         '후보 %d건 · 주사위 실행 %d건' % (len(cand), len(rolled)),
         ha='center', fontsize=10, color=GR)

# ① 두 축의 눈금
ax = fig.add_subplot(gs[0, 0])
sk = [x/100 for x in range(40, 301)]
ax.plot(sk, [p_formula(s) for s in sk], color=BLUE, lw=2.4, label='식이 반응하는 축: 개념')
o = [8, 9, 11, 13]
ro = [river_odds(x, 'flop') for x in o]
ax2 = ax.twiny()
ax2.plot(o, ro, color=RED, lw=2.4, marker='o', ms=6, label='식이 무시하는 축: 드로우')
ax2.set_xlim(7.5, 13.5); ax2.set_xlabel('물리 아웃츠 (플랍)', color=RED, fontsize=10)
ax2.tick_params(axis='x', colors=RED, labelsize=9)
for x, y in zip(o, ro):
    ax2.annotate('%d아웃 %.0f%%' % (x, y*100), (x, y), textcoords='offset points',
                 xytext=(0, -16), ha='center', fontsize=8, color=RED)
ax.set_xlim(0.3, 3.05); ax.set_ylim(0.15, 1.0)
ax.set_xlabel('semibluff 개념 sk (0~3 스케일)', color=BLUE, fontsize=10)
ax.tick_params(axis='x', colors=BLUE, labelsize=9)
ax.set_ylabel('확률', fontsize=10)
ax.text(0.02, 0.97, '① 개념 축은 2.75배로 움직이고\n    드로우 축(1.53배)은 0배로 들어간다',
        transform=ax.transAxes, va='top', ha='left', fontsize=11, color=FG,
        bbox=dict(fc='white', ec='none', alpha=0.85, pad=2))
ax.grid(alpha=0.25, lw=0.6)
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1+h2, l1+l2, fontsize=8.5, loc='lower right', framealpha=0.95)

# ② 후보 분해
ax = fig.add_subplot(gs[0, 1])
def cls(i):
    # 관측된 분기로 분류한다. 재구성한 pcz 는 쓰지 않는다.
    if i['_branch'] == 'above':
        return '② 선점\n(분기 구조)'
    if i['_branch'] == 'semibluff':
        return '④ 채택'
    if i['outs_true'] < 8:
        return '① 인지편향\n(calc_noise)'
    return '③ 주사위 탈락\n(확률식)'
c = collections.Counter(cls(i) for i in cand)
order = ['① 인지편향\n(calc_noise)', '② 선점\n(분기 구조)', '③ 주사위 탈락\n(확률식)', '④ 채택']
vals = [c.get(k, 0) for k in order]
cols = [ORA, RED, BLUE, GREEN]
b = ax.bar(range(4), vals, color=cols, edgecolor=FG, lw=0.7, width=0.62)
for i, v in enumerate(vals):
    ax.text(i, v+0.5, '%d\n(%.0f%%)' % (v, 100*v/len(cand)), ha='center',
            fontsize=10, color=FG)
ax.set_xticks(range(4)); ax.set_xticklabels(order, fontsize=9)
ax.set_ylim(0, max(vals)*1.32); ax.set_ylabel('건수', fontsize=10)
ax.set_title('② 후보 %d건의 책임 소재\n    확률식이 닿는 구역은 ③ 하나뿐이다' % len(cand),
             fontsize=11, color=FG, loc='left')
ax.grid(axis='y', alpha=0.25, lw=0.6)

# ③ 물리 outs 별 배정 p — 산점도
ax = fig.add_subplot(gs[1, 0])
import random as _rnd
_rnd.seed(7)
for i in rolled:
    if i['outs_true'] < 8:
        continue
    took_i = (i['_branch'] == 'semibluff')
    ax.scatter(i['outs_true'] + _rnd.uniform(-0.22, 0.22), p_formula(i['_sk']),
               s=44, color=(GREEN if took_i else RED), alpha=0.75,
               edgecolor='white', lw=0.7, zorder=3)
for oo in (8, 9, 11, 13):
    sub = [p_formula(i['_sk']) for i in rolled if i['outs_true'] == oo]
    if not sub:
        continue
    m = sum(sub)/len(sub)
    ax.plot([oo-0.38, oo+0.38], [m, m], color=FG, lw=2.0, zorder=4)
    ax.annotate('n=%d' % len(sub), (oo, 0.905), ha='center', fontsize=8.5, color=GR)
ax.set_xlim(7.2, 13.8); ax.set_xticks([8, 9, 11, 13]); ax.set_ylim(0.30, 0.95)
ax.set_xlabel('물리 아웃츠 outs_true  (draw_strength 는 8·9·11·13 만 낸다)', fontsize=10)
ax.set_ylabel('식이 배정한 확률 p', fontsize=10)
ax.set_title('③ 식에 outs 항이 없다 — 세로 산포(개념)가 가로 추세(드로우)를 압도한다\n'
             '    물리 8아웃 n=%d 안에서만 p 0.47~0.71.  corr(p,완성확률) %+.2f (t=%.2f, 유의하지 않음)'
             % (sum(1 for i in rolled if i['outs_true'] == 8), CORR, TSTAT),
             fontsize=11, color=FG, loc='left')
from matplotlib.lines import Line2D
ax.legend(handles=[Line2D([], [], marker='o', ls='', color=GREEN, label='주사위 통과'),
                   Line2D([], [], marker='o', ls='', color=RED, label='주사위 탈락'),
                   Line2D([], [], color=FG, lw=2, label='그 아웃츠의 평균 p')],
          fontsize=8.5, loc='lower right')
ax.grid(alpha=0.25, lw=0.6)

# ④ 계획 라벨 vs 행동
ax = fig.add_subplot(gs[1, 1])
def dist(grp):
    c = collections.Counter(i.get('action') for i in grp)
    return [c.get(k, 0)/len(grp) for k in ('bet', 'raise', 'call', 'check', 'fold')]
labs = ['bet', 'raise', 'call', 'check', 'fold']
cols2 = [GREEN, '#6fb58a', GREY, '#8a8a8a', RED]
for row, (nm, grp) in enumerate((('④ 주사위 통과  n=%d' % len(took), took),
                                 ('③ 주사위 탈락  n=%d' % len(g3), g3))):
    left = 0.0
    for v, lb, cl in zip(dist(grp), labs, cols2):
        if v <= 0:
            continue
        ax.barh(row, v, left=left, color=cl, edgecolor='white', lw=1.0, height=0.5)
        if v >= 0.09:
            ax.text(left+v/2, row, '%s\n%.0f%%' % (lb, v*100), ha='center', va='center',
                    fontsize=8.5, color='white' if cl != GREY else FG)
        left += v
ax.set_yticks([0, 1]); ax.set_yticklabels(['④ 주사위 통과  n=%d' % len(took),
                                           '③ 주사위 탈락  n=%d' % len(g3)], fontsize=9.5)
ax.set_xlim(0, 1); ax.set_xlabel('실제 액션 비율', fontsize=10)
a4 = sum(1 for i in took if i.get('action') in ('bet', 'raise'))/max(1, len(took))
a3 = sum(1 for i in g3 if i.get('action') in ('bet', 'raise'))/max(1, len(g3))
ax.set_title('④ 계획 라벨 != 행동 — 주사위 뒤에 decide_aggression 이 또 굴린다\n'
             '    공격률 %.0f%% → %.0f%% (%+.0f%%p). 라벨 차이만큼 행동이 벌어지지 않는다'
             % (a3*100, a4*100, (a4-a3)*100), fontsize=11, color=FG, loc='left')
ax.grid(axis='x', alpha=0.25, lw=0.6)

out = os.path.join(D, 'tools', 'sb_calib.png')
fig.savefig(out, facecolor='white')
print(out)
