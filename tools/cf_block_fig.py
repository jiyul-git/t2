#!/usr/bin/env python3
"""cf_block.py 결과의 PNG. 계산은 cf_block 에서 가져온다."""
import os, sys, glob, random, collections
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
plt.rcParams['font.family'] = 'WenQuanYi Zen Hei'
plt.rcParams['axes.unicode_minus'] = False
import plan as PL
from sb_calib import load, branch_of
from init_gate import block_fired, block_p
from cf_block import aggr, now_aggr, RESP

paths = sys.argv[1:] or sorted(glob.glob(os.path.join(D, 'collected_p*.jsonl')))
pure = load(paths)
allr = load(paths, pure=False)
bf = [i for i in pure if block_fired(i)]
for i in bf:
    i['_now'] = now_aggr(i)
    i['_cf'] = aggr(i, 'block')
    i['_res'] = (i.get('tocall') or 0) > 0
    i['_d'] = None if i['_now'] is None else abs(i['_cf'] - i['_now'])
unres = [i for i in bf if not i['_res'] and i['_d'] is not None]
res = [i for i in bf if i['_res']]

FG, GR = '#1b1b1b', '#8a8a8a'
BLUE, RED, GREEN, GREY, ORA = '#2f6fb5', '#c1453c', '#3f8f5e', '#b9b9b9', '#d08a33'
COL = {'value_2street': BLUE, 'pot_control': ORA, 'giveup': RED}
fig = plt.figure(figsize=(13.5, 9.8), dpi=150, facecolor='white')
gs = fig.add_gridspec(2, 2, hspace=0.48, wspace=0.26,
                      left=0.075, right=0.975, top=0.855, bottom=0.085)
fig.suptitle("block 이 덮이지 않았다면 — 행동 반사실 (난수 재추첨 없음)",
             fontsize=15, color=FG, y=0.975)
fig.text(0.5, 0.936,
         '봇 대전 6,000핸드 · block 발화 %d건(정제 %d) · 생존 0건 · '
         '행동 변경 확률 = |p_cf - p_now| (같은 난수를 공유)'
         % (len([i for i in allr if block_fired(i)]), len(bf)),
         ha='center', fontsize=10, color=GR)

# ① 덮어쓴 대상별
ax = fig.add_subplot(gs[0, 0])
order = ['value_2street', 'pot_control', 'giveup']
ns, chs = [], []
for pl in order:
    sub = [i for i in unres if i['plan'] == pl]
    ns.append(len(sub)); chs.append(sum(i['_d'] for i in sub))
x = range(len(order))
ax.bar(x, chs, color=[COL[p] for p in order], edgecolor=FG, lw=0.8, width=0.58,
       label='행동 변경 기대')
ax.bar(x, [n-c for n, c in zip(ns, chs)], bottom=chs, color=GREY,
       edgecolor=FG, lw=0.8, width=0.58, label='행동 동일')
for xi, (n, c) in enumerate(zip(ns, chs)):
    ax.text(xi, n + 0.35, 'n=%d\n변경 %.2f (%.0f%%)' % (n, c, 100*c/n),
            ha='center', fontsize=9.5, color=FG)
ax.set_xticks(list(x)); ax.set_xticklabels(order, fontsize=9.5)
ax.set_ylim(0, max(ns)*1.38); ax.set_ylabel('건수 (무저항)', fontsize=10)
ax.set_title('① 덮어쓴 대상별 — 합계 %d건 중 기대 변경 %.2f건 (%.0f%%)'
             % (sum(ns), sum(chs), 100*sum(chs)/sum(ns)),
             fontsize=11, color=FG, loc='left')
ax.legend(fontsize=8.5, loc='upper right'); ax.grid(axis='y', alpha=0.25, lw=0.6)

# ② 현재 p → CF p
ax = fig.add_subplot(gs[0, 1])
for i in unres:
    c = COL[i['plan']]
    ax.plot([0, 1], [i['_now'], i['_cf']], color=c, lw=1.6, alpha=0.65, zorder=2)
    ax.scatter([0, 1], [i['_now'], i['_cf']], s=30, color=c, zorder=3,
               edgecolor='white', lw=0.6)
ax.set_xlim(-0.2, 1.2); ax.set_xticks([0, 1])
ax.set_xticklabels(['현재 계획', 'CF: block'], fontsize=10)
ax.set_ylim(-0.05, 1.0); ax.set_ylabel('그 스팟의 공격확률', fontsize=10)
ax.set_title('② 방향이 집단마다 반대다\n'
             '    CF 가 더 침 %d건 (Σ%+.2f) · 덜 침 %d건 (Σ%+.2f)'
             % (sum(1 for i in unres if i['_cf'] > i['_now']),
                sum(i['_cf']-i['_now'] for i in unres if i['_cf'] > i['_now']),
                sum(1 for i in unres if i['_cf'] < i['_now']),
                sum(i['_cf']-i['_now'] for i in unres if i['_cf'] < i['_now'])),
             fontsize=11, color=FG, loc='left')
ax.legend(handles=[Line2D([], [], color=COL[p], lw=2, label=p) for p in order],
          fontsize=8.5, loc='lower left')
ax.grid(axis='y', alpha=0.25, lw=0.6)

# ③ 사이즈 기본표
ax = fig.add_subplot(gs[1, 0])
cur = [PL.SIZING.get(p, {}).get('flop', 0.0) for p in order]
blk = [PL.SIZING['block']['flop']] * len(order)
w = 0.36
ax.bar([v-w/2 for v in x], cur, w, color=[COL[p] for p in order],
       edgecolor=FG, lw=0.8, label='현재 계획')
ax.bar([v+w/2 for v in x], blk, w, color=GREEN, edgecolor=FG, lw=0.8, label='block')
for xi, (a, b) in enumerate(zip(cur, blk)):
    ax.text(xi-w/2, a+0.012, '%.2f' % a, ha='center', fontsize=9.5)
    ax.text(xi+w/2, b+0.012, '%.2f' % b, ha='center', fontsize=9.5)
ax.set_xticks(list(x)); ax.set_xticklabels(order, fontsize=9.5)
ax.set_ylim(0, 0.62); ax.set_ylabel('SIZING 기본표 (플랍, 팟 대비)', fontsize=10)
ax.set_title('③ 사이즈는 별개 축이다\n'
             '    giveup 0.00 → 0.25 는 "칠 수단 없음"에서 "친다"로 바뀐다',
             fontsize=11, color=FG, loc='left')
ax.legend(fontsize=8.5); ax.grid(axis='y', alpha=0.25, lw=0.6)
ax.text(0.5, -0.24, 'decide_size 가 rng 를 소비하므로 최종 사이즈는 복원하지 않았다',
        transform=ax.transAxes, ha='center', fontsize=9, color=GR)

# ④ 저항 10건
ax = fig.add_subplot(gs[1, 1])
cat = collections.Counter()
for i in res:
    tr = None
    for xx in (i.get('trace') or []):
        if (xx or {}).get('kind') == 'response' and xx.get('street') == i['street']:
            tr = xx
    if i['plan'] in ('value_2street', 'value_3street', 'trap'):
        ok = tr and float(tr.get('eq', 0)) > float(tr['need']) + 0.15
        cat['밸류 레이즈 기회 상실\n(발동 조건 충족)' if ok
            else '분기는 다르나\n발동 조건 미충족'] += 1
    elif RESP.get(i['plan'], 'calldown') == RESP['block']:
        cat['분기 동일\n바뀔 수 없음'] += 1
    else:
        cat['giveup 조기 return\n→ calldown'] += 1
ks = [k for k, _ in cat.most_common()]
vs = [cat[k] for k in ks]
cols = [RED if '상실' in k or 'calldown' in k else GREY for k in ks]
ax.bar(range(len(ks)), vs, color=cols, edgecolor=FG, lw=0.8, width=0.55)
for xi, v in enumerate(vs):
    ax.text(xi, v+0.08, '%d' % v, ha='center', fontsize=11)
ax.set_xticks(range(len(ks))); ax.set_xticklabels(ks, fontsize=8.5)
ax.set_ylim(0, max(vs)*1.35); ax.set_ylabel('건수', fontsize=10)
ax.set_title('④ 저항 %d건 — decide_aggression 을 타지 않는다\n'
             '    실제로 달라질 수 있는 것은 %d건'
             % (len(res), sum(v for k, v in cat.items() if '상실' in k or 'calldown' in k)),
             fontsize=11, color=FG, loc='left')
ax.grid(axis='y', alpha=0.25, lw=0.6)

out = os.path.join(D, 'tools', 'cf_block.png')
fig.savefig(out, facecolor='white')
print(out)
