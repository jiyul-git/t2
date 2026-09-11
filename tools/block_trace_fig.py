#!/usr/bin/env python3
"""block_trace.py 결과의 PNG. 계산은 block_trace 에서 가져온다."""
import os, sys, glob, collections
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'WenQuanYi Zen Hei'
plt.rcParams['axes.unicode_minus'] = False
import persona as PS
from sb_calib import load, branch_of
from init_gate import block_fired, block_p
from cf_block import aggr, now_aggr
from block_trace import allowed_keep

paths = sys.argv[1:] or sorted(glob.glob(os.path.join(D, 'collected_p*.jsonl')))
allr = load(paths, pure=False)
pure = load(paths)
bf_all = [i for i in allr if block_fired(i)]
bf = [i for i in pure if block_fired(i)]
unres = [i for i in bf if (i.get('tocall') or 0) == 0]
res = [i for i in bf if (i.get('tocall') or 0) > 0]

FG, GR = '#1b1b1b', '#8a8a8a'
BLUE, RED, GREEN, GREY, ORA = '#2f6fb5', '#c1453c', '#3f8f5e', '#b9b9b9', '#d08a33'
fig = plt.figure(figsize=(13.5, 9.8), dpi=150, facecolor='white')
gs = fig.add_gridspec(2, 2, hspace=0.50, wspace=0.26,
                      left=0.075, right=0.975, top=0.855, bottom=0.085)
fig.suptitle('block 발화 %d건의 생존 경로 전수 추적' % len(bf_all),
             fontsize=15, color=FG, y=0.975)
fig.text(0.5, 0.936,
         '진입 조건(oop · not initiative · 0.25<=rel<=0.80) 41/41 전건 충족 · '
         '전부 flop · [2] 456~467 이 100% 덮는다',
         ha='center', fontsize=10, color=GR)

# ① 파이프라인 깔때기
ax = fig.add_subplot(gs[0, 0])
keep = sum(allowed_keep(i['_prof']) for i in bf_all)
stages = ['[1] 발화', '[2] 456 체인\n생존', '[3] _allowed\n(반사실)', '[6] 행동까지\n(반사실)']
vals = [len(bf_all), 0, keep, keep]
cols = [BLUE, RED, GREY, GREY]
ax.bar(range(4), vals, color=cols, edgecolor=FG, lw=0.8, width=0.58)
for x, v in enumerate(vals):
    ax.text(x, v + 1.2, '%.1f' % v if v % 1 else '%d' % v, ha='center',
            fontsize=11, color=FG)
ax.annotate('', xy=(1, 1.5), xytext=(0, len(bf_all)-1.5),
            arrowprops=dict(arrowstyle='->', color=RED, lw=2))
ax.text(0.5, len(bf_all)*0.55, '-41\n(100%)', ha='center', fontsize=10, color=RED)
ax.set_xticks(range(4)); ax.set_xticklabels(stages, fontsize=9)
ax.set_ylim(0, len(bf_all)*1.28); ax.set_ylabel('건수', fontsize=10)
ax.set_title('① 병목은 [2] 하나다\n'
             '    [3] _allowed 는 %.0f%% 를 통과시킨다 — 두 번째 사망 지점이 아니다'
             % (100*keep/len(bf_all)), fontsize=11, color=FG, loc='left')
ax.grid(axis='y', alpha=0.25, lw=0.6)

# ② 네 그룹
ax = fig.add_subplot(gs[0, 1])
g1 = sum(allowed_keep(i['_prof']) * aggr(i, 'block') for i in unres)
g2 = sum(allowed_keep(i['_prof']) * (1 - aggr(i, 'block')) for i in unres)
g4 = sum(1 - allowed_keep(i['_prof']) for i in unres)
ks = ['1. block → bet', '2. block → check', '3. 덮어써짐\n(현재 실제)', '4. 이후 소멸\n(_allowed)']
vs = [g1, g2, len(unres), g4]
cols = [GREEN, GREY, RED, ORA]
ax.bar(range(4), vs, color=cols, edgecolor=FG, lw=0.8, width=0.58)
for x, v in enumerate(vs):
    ax.text(x, v + 0.7, '%.2f' % v if v % 1 else '%d' % v, ha='center',
            fontsize=10.5, color=FG)
    if x != 2:
        ax.text(x, v + 2.0, '(%.0f%%)' % (100*v/len(unres)), ha='center',
                fontsize=9, color=GR)
ax.set_xticks(range(4)); ax.set_xticklabels(ks, fontsize=9)
ax.set_ylim(0, len(unres)*1.32); ax.set_ylabel('건수 (무저항 %d건 기준)' % len(unres),
                                               fontsize=10)
ax.set_title('② 반사실로 도달하는 곳 — 3번만 실제다\n'
             '    살아남았다면 65%가 벳, 35%가 체크. 4번은 0.00건',
             fontsize=11, color=FG, loc='left')
ax.grid(axis='y', alpha=0.25, lw=0.6)

# ③ 발화 vs 비발화 — block_p 만 다르다
ax = fig.add_subplot(gs[1, 0])
cand = [i for i in pure
        if i.get('oop') and not i.get('init') and 0.25 <= i['rel'] <= 0.80
        and branch_of(i) == 'above' and PS.sk(i['_prof'], 'blockbet')/3.33 >= 1]
ff = [i for i in cand if block_fired(i)]
nf = [i for i in cand if not block_fired(i)]
names = ['rel', 'eq', 'made', 'danger', 'sk(bb)/10', 'block_p']
getf = [lambda x: x['rel'], lambda x: x['eq'], lambda x: x.get('made', 0),
        lambda x: x.get('danger') or 0.0,
        lambda x: PS.sk(x['_prof'], 'blockbet')/10.0, lambda x: block_p(x)[0]]
a = [sum(f(x) for x in ff)/len(ff) for f in getf]
b = [sum(f(x) for x in nf)/len(nf) for f in getf]
x = range(len(names)); w = 0.36
ax.bar([v-w/2 for v in x], a, w, color=GREEN, edgecolor=FG, lw=0.7,
       label='발화 (n=%d)' % len(ff))
ax.bar([v+w/2 for v in x], b, w, color=GREY, edgecolor=FG, lw=0.7,
       label='비발화 (n=%d)' % len(nf))
for xi, (u, v) in enumerate(zip(a, b)):
    ax.text(xi-w/2, u+0.012, '%.2f' % u, ha='center', fontsize=8)
    ax.text(xi+w/2, v+0.012, '%.2f' % v, ha='center', fontsize=8)
ax.set_xticks(list(x)); ax.set_xticklabels(names, fontsize=9)
ax.set_ylim(0, 0.95); ax.set_ylabel('평균', fontsize=10)
ax.set_title('③ 발화/비발화를 가르는 것은 block_p 하나뿐\n'
             '    rel·eq·made 는 두 집단이 같다 — 공식을 제대로 읽었는지의 검산',
             fontsize=11, color=FG, loc='left')
ax.legend(fontsize=8.5); ax.grid(axis='y', alpha=0.25, lw=0.6)

# ④ _allowed 문턱 분포
ax = fig.add_subplot(gs[1, 1])
sks = sorted(PS.sk(i['_prof'], 'blockbet') for i in bf_all)
ax.hist(sks, bins=14, color=BLUE, edgecolor='white', lw=0.8)
ax.axvline(3.33, color=ORA, lw=2.0, ls='--')
ax.axvline(3.5, color=RED, lw=2.0, ls='--')
ax.text(3.33, ax.get_ylim()[1]*0.96, ' make_plan 게이트 3.33', color=ORA,
        fontsize=9, va='top', rotation=90)
ax.text(3.5, ax.get_ylim()[1]*0.60, ' _allowed 안전선 3.5', color=RED,
        fontsize=9, va='top', rotation=90)
ax.set_xlabel('blockbet 원개념 (0~10)', fontsize=10)
ax.set_ylabel('건수', fontsize=10)
n_mid = sum(1 for s in sks if 1.5 <= s < 3.5)
ax.set_title('④ 문턱 불일치는 실재하나 영향이 없다\n'
             '    3.33~3.5 사이 %d건 · 확률 강등 대상 %d건 · 무조건 강등 0건'
             % (sum(1 for s in sks if 3.33 <= s < 3.5), n_mid),
             fontsize=11, color=FG, loc='left')
ax.grid(axis='y', alpha=0.25, lw=0.6)

out = os.path.join(D, 'tools', 'block_trace.png')
fig.savefig(out, facecolor='white')
print(out)
