#!/usr/bin/env python3
"""init_gate.py 결과의 PNG. 계산은 init_gate 에서 가져온다."""
import os, sys, glob, math, collections
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
plt.rcParams['font.family'] = 'WenQuanYi Zen Hei'
plt.rcParams['axes.unicode_minus'] = False
import persona as PS
from sb_calib import load, branch_of
from sb_114 import thresholds
from init_gate import block_p, pc_p, cf_no_gate, fired, block_fired, _street_why

paths = sys.argv[1:] or sorted(glob.glob(os.path.join(D, 'collected_p*.jsonl')))
rows = load(paths)
allr = load(paths, pure=False)
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
gs = fig.add_gridspec(2, 2, hspace=0.52, wspace=0.26,
                      left=0.075, right=0.975, top=0.855, bottom=0.085)
fig.suptitle('initiative = False 에서 비공격 계획은 어느 단계에서 사라지는가',
             fontsize=15, color=FG, y=0.975)
fig.text(0.5, 0.936,
         '봇 대전 6,000핸드 · make_plan 원본 %d건 · 모집단(init=False·rel>=0.5·made==0) %d건 · '
         'eq>=pcz 진입 %d건' % (len(mp), len(pop), len(inpcz)),
         ha='center', fontsize=10, color=GR)


def funnel(ax, stages, vals, title, note, exp=None):
    n = len(stages)
    for x, (s, v) in enumerate(zip(stages, vals)):
        col = GREEN if x == n-1 and v > 0 else (BLUE if x < n-1 else RED)
        ax.bar(x, v, color=col, edgecolor=FG, lw=0.8, width=0.62)
        ax.text(x, v + max(vals)*0.03, '%d' % v, ha='center', fontsize=11, color=FG)
        if x > 0 and vals[x-1] - v > 0:
            ax.annotate('-%d' % (vals[x-1]-v), (x-0.5, (vals[x-1]+v)/2),
                        ha='center', fontsize=9, color=RED)
    if exp is not None:
        ax.axhline(exp, color=ORA, ls='--', lw=1.5)
        ax.text(n-1, exp, ' 기대 Σp %.1f' % exp, color=ORA, fontsize=9,
                va='bottom', ha='right')
    ax.set_xticks(range(n)); ax.set_xticklabels(stages, fontsize=8.5)
    ax.set_ylim(0, max(vals)*1.22); ax.set_ylabel('건수', fontsize=10)
    ax.set_title(title, fontsize=11, color=FG, loc='left')
    ax.grid(axis='y', alpha=0.25, lw=0.6)
    ax.text(0.5, -0.30, note, transform=ax.transAxes, ha='center',
            fontsize=9, color=GR)


# ① block 깔때기
ax = fig.add_subplot(gs[0, 0])
elig = [i for i in inpcz if i.get('oop') and 0.25 <= i['rel'] <= 0.80]
gate = [i for i in elig if PS.sk(i['_prof'], 'blockbet')/3.33 >= 1]
bf = [i for i in gate if block_fired(i)]
surv = [i for i in bf if i['plan'] == 'block']
funnel(ax, ['eq>=pcz\n진입', '후보 조건\noop & rel', '개념 게이트\nsk>=1', '주사위\n발화', '살아남음'],
       [len(inpcz), len(elig), len(gate), len(bf), len(surv)],
       '① block — 마지막 칸이 0 이다',
       '주사위는 정상 범위(기대 %.1f vs 발화 %d, z=%+.2f). 문제는 그 다음 칸이다'
       % (sum(block_p(i)[0] for i in gate), len(bf),
          (len(bf)-sum(block_p(i)[0] for i in gate)) /
          math.sqrt(max(1e-9, sum(block_p(i)[0]*(1-block_p(i)[0]) for i in gate)))),
       exp=sum(block_p(i)[0] for i in gate))

# ② pot_control 깔때기
ax = fig.add_subplot(gs[0, 1])
pg = [i for i in inpcz if PS.sk(i['_prof'], 'potcontrol')/3.33 >= 1]
pf = [i for i in pg if fired(i) == 'pot_control']
psurv = [i for i in pf if i['plan'] == 'pot_control']
expp = sum(pc_p(i) for i in pg)
varp = sum(pc_p(i)*(1-pc_p(i)) for i in pg)
funnel(ax, ['eq>=pcz\n진입', '후보 조건\n(없음)', '개념 게이트\nsk>=1', '주사위\n발화', '살아남음'],
       [len(inpcz), len(inpcz), len(pg), len(pf), len(psurv)],
       '② pot_control — 끝까지 살아남는다',
       '기대 %.1f vs 발화 %d, z=%+.2f — 정상. _allowed 강등 0건'
       % (expp, len(pf), (len(pf)-expp)/math.sqrt(max(1e-9, varp))),
       exp=expp)

# ③ block 발화 41건의 운명 (전 표본)
ax = fig.add_subplot(gs[1, 0])
over = collections.Counter()
nfire = 0
for i in allr:
    if not block_fired(i):
        continue
    nfire += 1
    ch = [x for x in _street_why(i) if x.startswith(('중간강도(', '중간강도이나'))]
    over[ch[0].split('→')[-1].strip() if ch else '체인 없음'] += 1
ks = [k for k, _ in over.most_common()]
vs = [over[k] for k in ks]
b = ax.bar(range(len(ks)), vs, color=RED, edgecolor=FG, lw=0.8, width=0.55)
for x, v in enumerate(vs):
    ax.text(x, v+0.3, '%d' % v, ha='center', fontsize=11, color=FG)
ax.set_xticks(range(len(ks))); ax.set_xticklabels(ks, fontsize=10)
ax.set_ylim(0, max(vs)*1.25)
ax.set_ylabel('건수', fontsize=10)
ax.set_title('③ 전 표본 %d건 발화 — 무엇이 덮었나 (살아남은 것 0)' % nfire,
             fontsize=11, color=FG, loc='left')
ax.text(0.5, -0.22, 'plan.py:447 은 독립 if. 456~467 의 if/elif/else 가 무조건 plan 을 재할당한다',
        transform=ax.transAxes, ha='center', fontsize=9, color=GR)
ax.grid(axis='y', alpha=0.25, lw=0.6)

# ④ initiative 하드 게이트
ax = fig.add_subplot(gs[1, 1])
src = collections.Counter()
for i in hit:
    w = _street_why(i)
    if any(x.startswith('중간강도이나') for x in w):
        src['402 폴백\n(eq>=pcz 안)'] += 1
    elif any(x.startswith('쇼다운 가치 있음') for x in w):
        src['최종 else\n쇼다운 가치 있음'] += 1
    elif any(x.startswith('쇼다운 가치 없고') for x in w):
        src['최종 else\n포기'] += 1
    else:
        src['기타/revise'] += 1
ks = [k for k, _ in src.most_common()]
vs = [src[k] for k in ks]
ax.bar(range(len(ks)), vs, color=GREY, edgecolor=FG, lw=0.8, width=0.55)
for x, v in enumerate(vs):
    ax.text(x, v+0.8, '%d (%.0f%%)' % (v, 100*v/len(hit)), ha='center', fontsize=10)
ax.set_xticks(range(len(ks))); ax.set_xticklabels(ks, fontsize=9)
ax.set_ylim(0, max(vs)*1.3); ax.set_ylabel('건수', fontsize=10)
cfs = [cf_no_gate(i) for i in hit]
ax.set_title('④ `if not initiative: return 0.0` 에 걸린 %d건 — 전부 체크' % len(hit),
             fontsize=11, color=FG, loc='left')
ax.text(0.5, -0.26,
        '과반이 eq < pcz 인 최종 else 에서 온다 — (가) 402 집단과 같은 인구가 아니다',
        transform=ax.transAxes, ha='center', fontsize=9, color=GR)
ax.grid(axis='y', alpha=0.25, lw=0.6)

out = os.path.join(D, 'tools', 'init_gate.png')
fig.savefig(out, facecolor='white')
print(out)
