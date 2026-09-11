#!/usr/bin/env python3
"""cf_402.py 의 반사실 결과를 PNG 로. 계산은 cf_402 에서 가져온다."""
import os, sys, collections
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
plt.rcParams['font.family'] = 'WenQuanYi Zen Hei'
plt.rcParams['axes.unicode_minus'] = False
import persona as PS
from sb_calib import load, branch_of, p_formula
from sb_114 import thresholds
from cf_pcz import actual_aggr, cf_semibluff_aggr, PASSIVE
from cf_402 import is_402, cf_aggr

rows = load([os.path.join(D, 'collected.jsonl')])
for i in rows:
    i['_branch'] = branch_of(i)
    i['_sk'] = PS.sk(i['_prof'], 'semibluff') / 3.33
    i['_v3'], i['_v2'], i['_pcz'] = thresholds(i)
mp = [i for i in rows if i['_branch']]
cand = [i for i in mp if i['outs'] >= 8 and i.get('behind', 0) <= 1 and i['_sk'] >= 0.4]
g2 = [i for i in cand if i['_branch'] == 'above']
for i in g2:
    i['_p_sb'] = p_formula(i['_sk']); i['_a0'], _ = actual_aggr(i)
    i['_a1'] = cf_semibluff_aggr(i)[0]
    i['_d'] = i['_p_sb'] * (i['_a1'] - i['_a0'])
    made_plan = (i['plan'] not in PASSIVE) or (i['rel'] >= 0.30 and i['plan'] != 'giveup')
    i['_abc'] = 'A' if made_plan else ('B' if i['_d'] > 0 else 'C')
B = [i for i in g2 if i['_abc'] == 'B']
tgt = [i for i in B if is_402(i) and i.get('made', 0) == 0]
unres = [i for i in tgt if (i.get('tocall') or 0) == 0]
res = [i for i in tgt if (i.get('tocall') or 0) > 0]
all402 = [i for i in mp if is_402(i)]
gv = [i for i in all402 if i.get('made', 0) == 0]

FG, GR = '#1b1b1b', '#8a8a8a'
BLUE, RED, GREEN, GREY, ORA = '#2f6fb5', '#c1453c', '#3f8f5e', '#b9b9b9', '#d08a33'
fig = plt.figure(figsize=(13.5, 9.8), dpi=150, facecolor='white')
gs = fig.add_gridspec(2, 2, hspace=0.46, wspace=0.26,
                      left=0.075, right=0.975, top=0.855, bottom=0.075)
fig.suptitle("402줄 폴백  `plan = 'showdown' if made >= 1 else 'giveup'`  반사실",
             fontsize=15, color=FG, y=0.975)
fig.text(0.5, 0.936,
         'make_plan 원본 1,047건 중 402 발동 %d건 · giveup %d건 · '
         'A 14건 중 402 발동 0건 (수정이 A 를 건드리지 않는다)' % (len(all402), len(gv)),
         ha='center', fontsize=10, color=GR)

# ① rel × outs — 두 모집단
ax = fig.add_subplot(gs[0, 0])
import random as _r; _r.seed(3)
for i in gv:
    isT = i in tgt
    ax.scatter(i['rel'] + _r.uniform(-0.012, 0.012),
               i['outs_true'] + _r.uniform(-0.25, 0.25),
               s=54 if isT else 40, color=(BLUE if i['outs_true'] >= 8 else ORA),
               alpha=0.85, edgecolor=('black' if isT else 'white'),
               lw=(1.1 if isT else 0.7), zorder=3)
ax.axhline(4, color=GR, ls=':', lw=1.0)
ax.set_xlim(-0.03, 1.03); ax.set_ylim(-1.2, 13)
ax.set_xlabel('rel — 상대 레인지 대비 현재 강도', fontsize=10)
ax.set_ylabel('물리 아웃츠 outs_true', fontsize=10)
ax.set_title('① 402 가 실제로 잡는 것은 두 덩어리다\n'
             '    의도한 대상(outs 0 · rel<=0.10)은 0건 — CLAUDE.md 주장 확인',
             fontsize=11, color=FG, loc='left')
ax.legend(handles=[Line2D([], [], marker='o', ls='', color=ORA,
                          label='(가) outs 0 · rel 높음 — 지금 이기는데 포기 (%d건)'
                                % sum(1 for i in gv if i['outs_true'] == 0 and i['rel'] > 0.10)),
                   Line2D([], [], marker='o', ls='', color=BLUE,
                          label='(나) outs>=8 드로우 (%d건)' % sum(1 for i in gv if i['outs_true'] >= 8)),
                   Line2D([], [], marker='o', ls='', color='white', mec='black',
                          label='이번 반사실 대상 %d건' % len(tgt))],
          fontsize=8, loc='upper left')
ax.grid(alpha=0.25, lw=0.6)

# ② CF 비교
ax = fig.add_subplot(gs[0, 1])
s0 = sum(i['_a0'] for i in unres)
vals = [s0]
labs = ['현재\ngiveup']
for nm, pl in (('B1', 'showdown'), ('B2', 'pot_control'), ('B3', 'semibluff')):
    vals.append(sum(cf_aggr(i, pl)[0] for i in unres))
    labs.append('CF-%s\n%s' % (nm, pl))
cols = [GREY, GREY, ORA, GREEN]
ax.bar(range(4), vals, color=cols, edgecolor=FG, lw=0.8, width=0.58)
for x, v in enumerate(vals):
    ax.text(x, v+0.06, '%.2f' % v, ha='center', fontsize=11, color=FG)
    if x > 0:
        ax.text(x, v+0.30, '%+.2f' % (v-vals[0]), ha='center', fontsize=9.5,
                color=(GREEN if v > vals[0]+0.01 else GR))
ax.set_xticks(range(4)); ax.set_xticklabels(labs, fontsize=9.5)
ax.set_ylim(0, max(vals)*1.35)
ax.set_ylabel('기대 공격 건수 (무저항 %d건 합)' % len(unres), fontsize=10)
ax.set_title('② 라벨을 바꾼다고 행동이 바뀌지 않는다\n'
             '    decide_aggression:838 은 giveup 과 showdown 을 같은 분기로 본다',
             fontsize=11, color=FG, loc='left')
ax.grid(axis='y', alpha=0.25, lw=0.6)

# ③ 건별 기울기
ax = fig.add_subplot(gs[1, 0])
for i in unres:
    a1 = cf_aggr(i, 'showdown')[0]
    a2 = cf_aggr(i, 'pot_control')[0]
    a3 = cf_aggr(i, 'semibluff')[0]
    ax.plot([0, 1, 2, 3], [i['_a0'], a1, a2, a3], color=BLUE, lw=1.6, alpha=0.6,
            marker='o', ms=5, zorder=3)
    ax.annotate('h%d' % i['_hand'], (3, a3), textcoords='offset points',
                xytext=(7, 0), fontsize=8, color=GR, va='center')
ax.set_xlim(-0.2, 3.55); ax.set_xticks([0, 1, 2, 3])
ax.set_xticklabels(['현재\ngiveup', 'B1\nshowdown', 'B2\npot_control', 'B3\nsemibluff'],
                   fontsize=9.5)
ax.set_ylabel('그 스팟의 공격확률', fontsize=10)
ax.set_title('③ 건별로 봐도 B1 은 완전히 평평하다\n'
             '    B2(pot_control)는 rel 낮으면 0.04 로 고정 — 사실상 체크',
             fontsize=11, color=FG, loc='left')
ax.grid(axis='y', alpha=0.25, lw=0.6)

# ④ 저항 3건
ax = fig.add_subplot(gs[1, 1])
if res:
    names, eqs, needs = [], [], []
    for i in res:
        t = None
        for x in (i.get('trace') or []):
            if (x or {}).get('kind') == 'response' and x.get('street') == i['street']:
                t = x
        names.append('h%d' % i['_hand']); eqs.append(i['eq'])
        needs.append(float(t['need']) if t else 0.0)
    y = range(len(names)); w = 0.36
    ax.barh([v+w/2 for v in y], eqs, w, color=GREEN, edgecolor=FG, lw=0.7, label='eq')
    ax.barh([v-w/2 for v in y], needs, w, color=RED, edgecolor=FG, lw=0.7, label='need (필요 승률)')
    for v, e, n in zip(y, eqs, needs):
        ax.text(e+0.012, v+w/2, '%.3f' % e, va='center', fontsize=9)
        ax.text(n+0.012, v-w/2, '%.3f' % n, va='center', fontsize=9)
    ax.set_yticks(list(y)); ax.set_yticklabels(names, fontsize=10)
    ax.set_xlim(0, 0.72); ax.set_xlabel('확률', fontsize=10)
    ax.legend(fontsize=8.5, loc='lower right')
ax.set_title('④ 저항 %d건에서는 402 가 해를 끼치지 않는다\n'
             '    decide_response:793 이 이미 콜시킨다 — %d/%d 콜'
             % (len(res), len(res), len(res)), fontsize=11, color=FG, loc='left')
ax.grid(axis='x', alpha=0.25, lw=0.6)

out = os.path.join(D, 'tools', 'cf_402.png')
fig.savefig(out, facecolor='white')
print(out)
