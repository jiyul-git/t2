#!/usr/bin/env python3
"""cf_pcz.py 의 반사실 결과를 PNG 로. 계산은 cf_pcz 에서 가져온다."""
import os, sys, collections, random
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

rows = load([os.path.join(D, 'collected.jsonl')])
for i in rows:
    i['_branch'] = branch_of(i)
    i['_sk'] = PS.sk(i['_prof'], 'semibluff') / 3.33
    i['_v3'], i['_v2'], i['_pcz'] = thresholds(i)
cand = [i for i in rows if i['_branch'] and i['outs'] >= 8
        and i.get('behind', 0) <= 1 and i['_sk'] >= 0.4]
g2 = [i for i in cand if i['_branch'] == 'above']
for i in g2:
    i['_p_sb'] = p_formula(i['_sk'])
    i['_a0'], _ = actual_aggr(i)
    i['_a1'] = cf_semibluff_aggr(i)[0]
    i['_d'] = i['_p_sb'] * (i['_a1'] - i['_a0'])
    made_plan = (i['plan'] not in PASSIVE) or (i['rel'] >= 0.30 and i['plan'] != 'giveup')
    i['_abc'] = 'A' if made_plan else ('B' if i['_d'] > 0 else 'C')

FG, GR = '#1b1b1b', '#8a8a8a'
BLUE, RED, GREEN, GREY = '#2f6fb5', '#c1453c', '#3f8f5e', '#b9b9b9'
CA, CB = '#c1453c', '#2f6fb5'
fig = plt.figure(figsize=(13.5, 9.8), dpi=150, facecolor='white')
gs = fig.add_gridspec(2, 2, hspace=0.44, wspace=0.26,
                      left=0.075, right=0.975, top=0.855, bottom=0.075)
fig.suptitle('② eq >= pcz 선점 26건의 반사실  —  난수를 새로 굴리지 않는다',
             fontsize=15, color=FG, y=0.975)
fig.text(0.5, 0.936,
         'CF-1: semibluff 분기를 eq>=pcz 위로 재정렬 · 게이트는 26/26 전건 통과 · '
         '기대 세미블러프 Σp = %.1f건' % sum(i['_p_sb'] for i in g2),
         ha='center', fontsize=10, color=GR)

# ① rel × 기대변화
ax = fig.add_subplot(gs[0, 0])
for i in g2:
    ax.scatter(i['rel'], i['_d'], s=52, color=(CA if i['_abc'] == 'A' else CB),
               alpha=0.8, edgecolor='white', lw=0.8, zorder=3)
ax.axhline(0, color=FG, lw=1.0, zorder=2)
# rel 0.30 선은 긋지 않는다 — A/B 정의에 rel 이 들어가므로
# 그 선을 그리면 정의를 관측처럼 보이게 만든다.
ax.set_xlabel('rel — 현재 보드에서의 실현 강도', fontsize=10)
ax.set_ylabel('기대 공격확률 변화  p × (반사실 - 현재)', fontsize=10)
_nB = sum(1 for i in g2 if i['_abc'] == 'B')
ax.set_title('① 수동·포기 계획 %d건은 **전부** 기대변화 > 0 — C = 0건\n'
             '    (A/B 구분에 rel 이 쓰이므로 갈림 자체는 정의다. C=0 이 관측이다)' % _nB,
             fontsize=11, color=FG, loc='left')
ax.legend(handles=[Line2D([], [], marker='o', ls='', color=CA, label='A 선점이 계획을 만듦 (n=%d)' % sum(1 for i in g2 if i['_abc'] == 'A')),
                   Line2D([], [], marker='o', ls='', color=CB, label='B 선점이 포기를 만듦 (n=%d)' % sum(1 for i in g2 if i['_abc'] == 'B'))],
          fontsize=8.5, loc='lower left')
ax.grid(alpha=0.25, lw=0.6)

# ② 현재 → 반사실 기울기
ax = fig.add_subplot(gs[0, 1])
for i in g2:
    col = CA if i['_abc'] == 'A' else CB
    ax.plot([0, 1], [i['_a0'], i['_a1']], color=col, lw=1.5, alpha=0.6, zorder=2)
    ax.scatter([0, 1], [i['_a0'], i['_a1']], s=26, color=col, zorder=3,
               edgecolor='white', lw=0.6)
ax.set_xlim(-0.18, 1.18); ax.set_xticks([0, 1])
ax.set_xticklabels(['현재 계획', '반사실: semibluff'], fontsize=10)
ax.set_ylabel('그 스팟의 공격확률', fontsize=10)
ax.set_title('② 재정렬은 한쪽만 돕지 않는다\n'
             '    A 는 내려가고(-0.89건) B 는 올라간다(+2.22건). 순변화 +1.33건',
             fontsize=11, color=FG, loc='left')
ax.grid(axis='y', alpha=0.25, lw=0.6)

# ③ A/B 기여 분해
ax = fig.add_subplot(gs[1, 0])
sa = sum(i['_d'] for i in g2 if i['_abc'] == 'A')
sb = sum(i['_d'] for i in g2 if i['_abc'] == 'B')
bars = ax.bar([0, 1, 2], [sb, sa, sa+sb], color=[CB, CA, GREY],
              edgecolor=FG, lw=0.8, width=0.55)
for x, v in zip([0, 1, 2], [sb, sa, sa+sb]):
    ax.text(x, v + (0.06 if v >= 0 else -0.14), '%+.2f건' % v, ha='center',
            fontsize=11, color=FG)
ax.axhline(0, color=FG, lw=1.0)
ax.set_xticks([0, 1, 2])
ax.set_xticklabels(['B — 포기가 공격으로', 'A — 밸류가 블러프로', '순변화'], fontsize=9.5)
ax.set_ylabel('기대 공격 건수 변화 (1,000핸드당)', fontsize=10)
ax.set_title('③ 선점은 절반은 일을 하고 있다\n'
             '    게이트는 outs·behind·sk 만 본다. made·rel 을 막는 것은 분기 순서뿐',
             fontsize=11, color=FG, loc='left')
ax.grid(axis='y', alpha=0.25, lw=0.6)

# ④ CF-2 행선지
ax = fig.add_subplot(gs[1, 1])
cur = collections.Counter(i['plan'] for i in g2)
S = sum(i['_p_sb'] for i in g2)
npc = sum(1 for i in g2 if PS.sk(i['_prof'], 'potcontrol')/3.33 >= 1)
cf2 = {'semibluff': S,
       'pot_control': (len(g2)-S) * (npc/len(g2)) * 0.72,
       'showdown': (len(g2)-S) * (1 - (npc/len(g2))*0.72)}
keys = ['semibluff', 'giveup', 'pot_control', 'showdown', 'value_2street', 'value_3street']
x = range(len(keys)); w = 0.38
ax.bar([i-w/2 for i in x], [cur.get(k, 0) for k in keys], w,
       color=GREY, edgecolor=FG, lw=0.7, label='현재')
ax.bar([i+w/2 for i in x], [cf2.get(k, 0) for k in keys], w,
       color=GREEN, edgecolor=FG, lw=0.7, label='CF-2: eq>=pcz 분기 제거')
ax.annotate('giveup 9건은\n구조적으로 소멸', (1+w/2, 0.4), fontsize=9, color=RED,
            ha='center', va='bottom')
ax.set_xticks(list(x)); ax.set_xticklabels(keys, fontsize=9, rotation=18, ha='right')
ax.set_ylabel('건수 (기대값)', fontsize=10)
ax.set_title('④ CF-2 에서 giveup 은 도달 불가\n'
             '    402줄 폴백은 eq>=pcz 분기 안에만 있다. has_sd 는 26/26 참',
             fontsize=11, color=FG, loc='left')
ax.legend(fontsize=8.5); ax.grid(axis='y', alpha=0.25, lw=0.6)

out = os.path.join(D, 'tools', 'cf_pcz.png')
fig.savefig(out, facecolor='white')
print(out)
