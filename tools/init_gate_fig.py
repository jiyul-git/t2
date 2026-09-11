#!/usr/bin/env python3
"""init_gate.py 결과의 PNG. 계산은 init_gate 에서 가져온다."""
import os, sys, glob, collections
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'WenQuanYi Zen Hei'
plt.rcParams['axes.unicode_minus'] = False
import persona as PS
from sb_calib import load, branch_of
from sb_114 import thresholds
from init_gate import block_p, pc_p, cf_no_gate, fired

paths = sys.argv[1:] or sorted(glob.glob(os.path.join(D, 'collected_p*.jsonl')))
rows = load(paths)
for i in rows:
    i['_branch'] = branch_of(i)
    i['_v3'], i['_v2'], i['_pcz'] = thresholds(i)
mp = [i for i in rows if i['_branch']]
pop = [i for i in mp if (not i.get('init')) and i['rel'] >= 0.5 and i.get('made', 0) == 0]
inpcz = [i for i in pop if i['_branch'] == 'above']
hit = [i for i in pop if i['plan'] in ('giveup', 'showdown') and (i.get('tocall') or 0) == 0]

FG, GR = '#1b1b1b', '#8a8a8a'
BLUE, RED, GREEN, GREY, ORA = '#2f6fb5', '#c1453c', '#3f8f5e', '#b9b9b9', '#d08a33'
fig = plt.figure(figsize=(13.5, 9.8), dpi=150, facecolor='white')
gs = fig.add_gridspec(2, 2, hspace=0.46, wspace=0.28,
                      left=0.075, right=0.975, top=0.855, bottom=0.075)
fig.suptitle('initiative = False · rel >= 0.5 · made == 0 에서 계획 가능성이 사라지는 지점',
             fontsize=15, color=FG, y=0.975)
fig.text(0.5, 0.936,
         'make_plan 원본 %d건 · 모집단 %d건 · eq>=pcz 진입 %d건  (봇 대전 %s핸드)'
         % (len(mp), len(pop), len(inpcz), '{:,}'.format(len(rows) and sum(1 for _ in open(paths[0])) * len(paths))),
         ha='center', fontsize=10, color=GR)

# ① 관문별 회계
ax = fig.add_subplot(gs[0, 0])
acct = collections.Counter()
for i in inpcz:
    f = fired(i)
    if f == 'block':
        acct['[B] block 발화'] += 1
    elif f == 'pot_control':
        acct['[P] pot_control 발화'] += 1
    elif f == 'thin_value':
        acct['[V] 얇은 밸류 발화'] += 1
    else:
        bp, why = block_p(i)
        bg = PS.sk(i['_prof'], 'blockbet')/3.33 >= 1
        pg = PS.sk(i['_prof'], 'potcontrol')/3.33 >= 1
        if not bg and not pg:
            acct['개념 게이트 둘 다 탈락'] += 1
        elif why != 'ok' and not pg:
            acct['block 진입불가\n+ potcontrol 개념 탈락'] += 1
        elif why != 'ok':
            acct['block 진입불가\n→ pot_control 확률 탈락'] += 1
        elif not pg:
            acct['block 확률 탈락\n+ potcontrol 개념 탈락'] += 1
        else:
            acct['둘 다 확률에서 탈락'] += 1
ks = [k for k, _ in acct.most_common()]
vs = [acct[k] for k in ks]
cols = [GREEN if '발화' in k else (ORA if '개념' in k else RED) for k in ks]
ax.barh(range(len(ks))[::-1], vs, color=cols, edgecolor=FG, lw=0.7)
for n, (k, v) in enumerate(zip(ks, vs)):
    ax.text(v + max(vs)*0.02, len(ks)-1-n, '%d (%.0f%%)' % (v, 100*v/max(1, sum(vs))),
            va='center', fontsize=9.5)
ax.set_yticks(range(len(ks))[::-1]); ax.set_yticklabels(ks, fontsize=8.5)
ax.set_xlim(0, max(vs)*1.28); ax.set_xlabel('건수', fontsize=10)
ax.set_title('① 가능성은 "확률에서" 사라진다\n'
             '    개념이 없어서가 아니라, 개념을 갖고도 주사위에서 떨어진다',
             fontsize=11, color=FG, loc='left')
ax.grid(axis='x', alpha=0.25, lw=0.6)

# ② block 진입 조건
ax = fig.add_subplot(gs[0, 1])
ip = [i for i in inpcz if not i.get('oop')]
oop_out = [i for i in inpcz if i.get('oop') and not (0.25 <= i['rel'] <= 0.80)]
elig = [i for i in inpcz if i.get('oop') and 0.25 <= i['rel'] <= 0.80]
gate = [i for i in elig if PS.sk(i['_prof'], 'blockbet')/3.33 >= 1]
exp = sum(block_p(i)[0] for i in gate)
got = sum(1 for i in gate if fired(i) == 'block')
stages = ['eq>=pcz\n진입', 'OOP\n(block 필수)', 'rel 0.25~0.80', 'sk(blockbet)\n>=1', '실측 발화']
vals = [len(inpcz), len(inpcz)-len(ip), len(elig), len(gate), got]
ax.plot(range(5), vals, color=BLUE, lw=2.4, marker='o', ms=9, zorder=3)
for x, v in enumerate(vals):
    ax.annotate('%d' % v, (x, v), textcoords='offset points', xytext=(0, 11),
                ha='center', fontsize=10, color=FG)
ax.axhline(exp, color=GREEN, ls='--', lw=1.5)
ax.text(4.0, exp, ' 기대 Σp %.1f' % exp, color=GREEN, fontsize=9, va='bottom', ha='right')
ax.set_xticks(range(5)); ax.set_xticklabels(stages, fontsize=8.5)
ax.set_ylim(0, len(inpcz)*1.18)
ax.set_ylabel('건수', fontsize=10)
ax.set_title('② block 은 이 집단을 위해 설계된 분기인데\n'
             '    `oop` 요구가 IP %d건을 입구에서 잘라낸다' % len(ip),
             fontsize=11, color=FG, loc='left')
ax.grid(alpha=0.25, lw=0.6)

# ③ _pc_p 는 핸드 강도를 안 본다
ax = fig.add_subplot(gs[1, 0])
g = [i for i in inpcz if PS.sk(i['_prof'], 'potcontrol')/3.33 >= 1]
xs = [i['rel'] for i in g]; ys = [pc_p(i) for i in g]
cl = [GREEN if fired(i) == 'pot_control' else RED for i in g]
ax.scatter(xs, ys, s=58, c=cl, alpha=0.82, edgecolor='white', lw=0.8, zorder=3)
ax.set_xlabel('rel — 상대 레인지 대비 현재 강도', fontsize=10)
ax.set_ylabel('_pc_p  (pot_control 채택 확률)', fontsize=10)
ax.set_ylim(0, 0.8)
ax.set_title('③ _pc_p 에는 rel 도 eq 도 들어가지 않는다\n'
             '    icm·gamble·aggr·다인원·머징만 본다 — 세로로 완전히 평평하다',
             fontsize=11, color=FG, loc='left')
from matplotlib.lines import Line2D
ax.legend(handles=[Line2D([], [], marker='o', ls='', color=GREEN, label='pot_control 발화'),
                   Line2D([], [], marker='o', ls='', color=RED, label='확률에서 탈락')],
          fontsize=8.5, loc='upper right')
ax.grid(alpha=0.25, lw=0.6)

# ④ initiative 하드 게이트
ax = fig.add_subplot(gs[1, 1])
if hit:
    cfs = sorted(cf_no_gate(i) for i in hit)
    ax.hist(cfs, bins=12, color=BLUE, edgecolor='white', lw=0.8)
    ax.axvline(sum(cfs)/len(cfs), color=RED, lw=1.8, ls='--')
    ax.text(sum(cfs)/len(cfs), ax.get_ylim()[1]*0.92, ' 평균 %.2f' % (sum(cfs)/len(cfs)),
            color=RED, fontsize=9.5)
    ax.set_xlabel('하드 게이트를 제거했다면 기존 코드가 냈을 p', fontsize=10)
    ax.set_ylabel('건수', fontsize=10)
    ax.set_title('④ `if not initiative: return 0.0` — %d건이 여기서 0 이 된다\n'
                 '    다만 그다음 줄은 cbet_freq 다: 이니셔티브 보유자용 함수'
                 % len(hit), fontsize=11, color=FG, loc='left')
ax.grid(axis='y', alpha=0.25, lw=0.6)

out = os.path.join(D, 'tools', 'init_gate.png')
fig.savefig(out, facecolor='white')
print(out)
