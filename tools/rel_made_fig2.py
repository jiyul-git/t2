#!/usr/bin/env python3
"""(가) 402 made↔rel 판별자 불일치 — 원인 귀속 그림. 계산은 rel_made 에서."""
import os, sys, glob, collections
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'WenQuanYi Zen Hei'
plt.rcParams['axes.unicode_minus'] = False
import bot, persona as PS
from sb_calib import load, branch_of
from sb_114 import thresholds
from cf_402 import is_402
from tag_draws import board_at

def arm(paths):
    rows = load(paths)
    for i in rows:
        i['_branch'] = branch_of(i); i['_v3'], i['_v2'], i['_pcz'] = thresholds(i)
    mp = [i for i in rows if i['_branch']]
    a = [i for i in mp if is_402(i)]
    ga = [i for i in a if i.get('made', 0) == 0 and i['outs_true'] == 0]
    return mp, a, ga

mpA, aA, gaA = arm([os.path.join(D, 'ab_A_%d.jsonl' % i) for i in range(4)])
mpB, aB, gaB = arm([os.path.join(D, 'ab_B_%d.jsonl' % i) for i in range(4)])

RV = {c: i for i, c in enumerate(bot.RANKS)}
def hi_class(hole, bd):
    hr = sorted((RV[c[0]] for c in hole), reverse=True)
    br = [RV[c[0]] for c in bd]
    if br and hr[0] <= max(br):
        return '보드 이하'
    return {12: 'A-high', 11: 'K-high', 10: 'Q-high'}.get(hr[0], '기타')

FG, GR = '#1b1b1b', '#8a8a8a'
BLUE, RED, GREEN, GREY, ORA = '#2f6fb5', '#c1453c', '#3f8f5e', '#b9b9b9', '#d08a33'
fig = plt.figure(figsize=(13.5, 9.6), dpi=150, facecolor='white')
gs = fig.add_gridspec(2, 2, hspace=0.46, wspace=0.26,
                      left=0.075, right=0.975, top=0.855, bottom=0.08)
fig.suptitle('(가) 402 폴백의 판별자 불일치 — 원인 귀속', fontsize=15, color=FG, y=0.975)
fig.text(0.5, 0.936,
         'ab_B 6,000핸드 (block 수정 후) · make_plan 원본 %d · 402 발동 %d · '
         'made==0 & 물리 outs==0 → **%d건**' % (len(mpB), len(aB), len(gaB)),
         ha='center', fontsize=10, color=GR)

# ① rel 분포 + 기존 임계값
ax = fig.add_subplot(gs[0, 0])
rels = [i['rel'] for i in gaB]
ax.hist(rels, bins=16, color=BLUE, edgecolor='white', lw=0.8)
for v, c, lab in ((0.42, ORA, '1562 쇼다운 가치\nrel >= 0.42'),
                  (0.55, RED, '1767 giveup 탈출\nrel >= 0.55')):
    ax.axvline(v, color=c, lw=2.0, ls='--')
    ax.text(v + 0.004, ax.get_ylim()[1]*0.96, lab, color=c, fontsize=8.5, va='top')
ax.set_xlabel('rel — 상대 레인지 대비 현재 승률 순위', fontsize=10)
ax.set_ylabel('건수', fontsize=10)
n42 = sum(1 for r in rels if r >= 0.42); n55 = sum(1 for r in rels if r >= 0.55)
ax.set_title('① 이미 코드에 있는 임계값으로 재면\n'
             '    rel>=0.42 %d/%d (%.0f%%) · rel>=0.55 %d/%d (%.0f%%)'
             % (n42, len(rels), 100*n42/len(rels), n55, len(rels), 100*n55/len(rels)),
             fontsize=11, color=FG, loc='left')
ax.grid(axis='y', alpha=0.25, lw=0.6)

# ② 구성
ax = fig.add_subplot(gs[0, 1])
c = collections.Counter(hi_class(i['_hole'], board_at(i['_board'], i['street']))
                        for i in gaB if i['_hole'])
ks = [k for k, _ in c.most_common()]; vs = [c[k] for k in ks]
cols = [RED if k == 'A-high' else GREY for k in ks]
ax.bar(range(len(ks)), vs, color=cols, edgecolor=FG, lw=0.8, width=0.55)
for x, v in enumerate(vs):
    ax.text(x, v + 1.5, '%d (%.0f%%)' % (v, 100*v/len(gaB)), ha='center', fontsize=10)
ax.set_xticks(range(len(ks))); ax.set_xticklabels(ks, fontsize=10)
ax.set_ylim(0, max(vs)*1.25); ax.set_ylabel('건수', fontsize=10)
ax.set_title('② 단일 현상이다 — A-high 가 92%\n'
             '    스트리트도 플랍 100%. 보드 구조·포지션은 흩어져 있다',
             fontsize=11, color=FG, loc='left')
ax.grid(axis='y', alpha=0.25, lw=0.6)

# ③ 얇은 밸류 게이트 회계
ax = fig.add_subplot(gs[1, 0])
ok_rel = 0
for i in gaB:
    mg = PS.sk(i['_prof'], 'range_merge') / 3.33
    if i['rel'] >= max(0.28, 0.52 - 0.080*mg):
        ok_rel += 1
ax.bar([0, 1], [ok_rel, 0], color=[GREEN, RED], edgecolor=FG, lw=0.8, width=0.5)
for x, v in enumerate([ok_rel, 0]):
    ax.text(x, v + 2, '%d / %d' % (v, len(gaB)), ha='center', fontsize=12)
ax.set_xticks([0, 1])
ax.set_xticklabels(['rel 조건 통과\nrel >= max(0.28, 0.52-0.08×머징)',
                    'made 조건 통과\nmade >= 1'], fontsize=9.5)
ax.set_ylim(0, len(gaB)*1.2); ax.set_ylabel('건수', fontsize=10)
ax.set_title('③ 얇은 밸류 게이트 `rel >= ... and made >= 1`\n'
             '    막은 것은 made 하나뿐이다 (%d/%d 이 rel 은 통과)'
             % (ok_rel, len(gaB)), fontsize=11, color=FG, loc='left')
ax.grid(axis='y', alpha=0.25, lw=0.6)

# ④ 판별자 신뢰 census
ax = fig.add_subplot(gs[1, 1])
sites = ['1545\nriver_fix', '1562\nriver_bluff', '1750\nrevise', '1767\ngiveup 탈출',
         '465 (402)\n조사 대상']
kind = [1, 1, 1, 1, 0]      # 1 = made OR rel, 0 = made 단독
ax.bar(range(5), [1]*5, color=[GREEN if k else RED for k in kind],
       edgecolor=FG, lw=0.8, width=0.6)
labs = ['made>=2\nor rel>=0.62', 'made>=1\nor rel>=0.42', 'made>=2\nor rel>=0.62',
        'rel>=0.55\nor made>=2', 'made>=1\n**단독**']
for x, l in enumerate(labs):
    ax.text(x, 0.5, l, ha='center', va='center', fontsize=8.5,
            color='white' if kind[x] else 'white')
ax.set_xticks(range(5)); ax.set_xticklabels(sites, fontsize=8.5)
ax.set_yticks([]); ax.set_ylim(0, 1.35)
ax.set_title('④ 코드는 이미 rel 을 쇼다운 가치 판별자로 신뢰한다\n'
             '    같은 질문에 네 곳이 made **또는** rel 로 답한다. 402 만 단독',
             fontsize=11, color=FG, loc='left')
ax.text(0.5, -0.16, '1767 주석: "포기에서 나오는 길이 없었다 … rel 이 0.35→0.73 으로 올라도 giveup 에 갇혀 체크했다"',
        transform=ax.transAxes, ha='center', fontsize=8.5, color=GR)

out = os.path.join(D, 'tools', 'rel_made2.png')
fig.savefig(out, facecolor='white')
print(out)
