#!/usr/bin/env python3
"""eq / rel 이 make_plan 의 어디에 들어가는지 그린다. → docs/EQREL_V1.png

읽기 전용 도구다. plan.py 를 수정하지 않는다.
근거는 TRACE_EQREL.md. 행번호는 그 문서와 같은 시점(8bc42b3)의 것이다.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager as fm

FONT = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
fp = fm.FontProperties(fname=FONT)
matplotlib.rcParams['font.family'] = fp.get_name()
matplotlib.rcParams['axes.unicode_minus'] = False

C_EQ, C_REL, C_BAD, C_BOX, C_TXT = '#1f6fb4', '#c2471c', '#b00020', '#f4f4f2', '#222222'


def box(ax, x, y, w, h, text, fc=C_BOX, ec='#999999', fs=9, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.012',
                                linewidth=1.2, facecolor=fc, edgecolor=ec, zorder=2))
    ax.text(x + w/2, y + h/2, text, ha='center', va='center', fontsize=fs,
            color=C_TXT, fontproperties=fp, zorder=3,
            fontweight='bold' if bold else 'normal', linespacing=1.5)


def arrow(ax, p, q, color='#666666', ls='-', lw=1.3):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle='-|>', mutation_scale=13,
                                 color=color, linestyle=ls, linewidth=lw,
                                 shrinkA=2, shrinkB=2, zorder=4))


fig, ax = plt.subplots(figsize=(12.6, 9.4), dpi=170)
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
fig.patch.set_facecolor('white')

ax.text(0.5, 0.975, 'make_plan 의 계획 사다리 — 진입은 미래 포함 eq, 내부 심사는 현재 보드만',
        ha='center', fontsize=15, fontweight='bold', color=C_TXT, fontproperties=fp)
ax.text(0.5, 0.945, 'plan.py 기준 8bc42b3 · TRACE_EQREL.md + TRACE_EQREL_COUNT.md (1,000핸드)',
        ha='center', fontsize=9, color='#777777', fontproperties=fp)

# --- 두 계산값 ---
box(ax, 0.035, 0.825, 0.275, 0.085,
    'eq   (plan.py:268)\n남은 보드를 끝까지 돌린 승률\n미래 카드 전개를 포함한다',
    fc='#e3eff8', ec=C_EQ, fs=9.5, bold=True)
box(ax, 0.345, 0.825, 0.275, 0.085,
    'rel  (plan.py:311-312)\n지금 보드에서만 평가한 강도\nbot.eval7(hero + board)',
    fc='#fbe9e2', ec=C_REL, fs=9.5, bold=True)
box(ax, 0.655, 0.825, 0.31, 0.085,
    'eq_current (plan.py:271)\n기록 전용. 판단에 쓰지 않는다\n→ eq_delta 로만 남는다',
    fc='#f0f0ee', ec='#aaaaaa', fs=9.5)

# --- 문턱 ---
box(ax, 0.035, 0.665, 0.585, 0.105,
    '문턱 생성   plan.py:337-339        v3 = 0.80+0.06·mw    v2 = 0.66+0.07·mw    pcz = 0.50+0.06·mw\n'
    '상대 읽기 보정 plan.py:354-356      v3 · v2 · pcz  셋 다 움직인다\n'
    'rel 페널티   plan.py:381-394        v3 · v2  만 움직인다',
    fc='#fdfdfb', ec='#888888', fs=9)
arrow(ax, (0.48, 0.825), (0.48, 0.772), color=C_REL, lw=1.8)

ax.text(0.645, 0.700,
        'rel ≤ 0.45 → _pen = 1.0\n  v3 = 1.10   도달 불가\n  v2 = 0.88\n  pcz = 0.50   ← 그대로\n'
        '  (헤즈업·무리딩 유도값)',
        fontsize=9.5, color=C_BAD, fontproperties=fp, va='center',
        fontweight='bold', linespacing=1.6)

# --- 사다리 ---
rows = [
    (0.545, 'eq ≥ v3      (plan.py:403)', 'trap / value_3street', '#eef4ee'),
    (0.455, 'eq ≥ v2      (plan.py:420)', 'value_2street / value_3street', '#eef4ee'),
    (0.365, 'eq ≥ pcz     (plan.py:439)', '진입은 eq 하나. 내부는 현재 보드만 본다', '#fbe9e2'),
    (0.185, 'outs ≥ 8     (plan.py:468)', 'semibluff  — pcz 아래에 있다', '#f2f2ef'),
    (0.095, 'eq < 0.42    (plan.py:490)', 'bluff_2street', '#f2f2ef'),
    (0.005, 'else          (plan.py:502)', 'has_sd = made ≥ 1 or eq ≥ 0.42+0.05·mw', '#f2f2ef'),
]
for y, cond, res, fc in rows:
    box(ax, 0.035, y, 0.26, 0.062, cond, fc=fc, ec='#888888', fs=9, bold=True)
    box(ax, 0.315, y, 0.40, 0.062, res, fc=fc, ec='#bbbbbb', fs=9)

# pcz 내부
box(ax, 0.335, 0.255, 0.38, 0.095,
    '내부 심사 — rel AND made. 둘 다 현재 보드만\n'
    '  0.25 ≤ rel ≤ 0.80        → block      (plan.py:442)\n'
    '  rel ≥ max(0.28, …) & made ≥ 1 → value_2street (458)  ← made 가 병목\n'
    '  else → showdown if made ≥ 1 else giveup  (465)',
    fc='#f9ddd3', ec=C_REL, fs=8.5)
arrow(ax, (0.525, 0.365), (0.525, 0.350), color=C_REL, lw=1.6)

for i in range(len(rows) - 1):
    arrow(ax, (0.165, rows[i][0]), (0.165, rows[i+1][0] + 0.062))

# eq 화살표
arrow(ax, (0.17, 0.825), (0.17, 0.772), color=C_EQ, lw=1.8)
arrow(ax, (0.165, 0.665), (0.165, 0.607), color=C_EQ, lw=1.8)

# --- 핵심 진술 ---
box(ax, 0.745, 0.115, 0.225, 0.445,
    '비대칭\n\n'
    'rel 페널티는 v3 · v2 만\n올린다. pcz 는 그대로다\n\n'
    '그래서 rel 이 낮아도\neq 만 높으면 pcz 로\n들어간다\n\n'
    '들어간 뒤 현재 보드만 보는\nrel · made 가 심사한다\n'
    '실측 병목은 made 다\n\n'
    'semibluff 분기는 pcz 아래라\n도달하지 못한다',
    fc='#fff4f2', ec=C_BAD, fs=9, bold=False)

# --- h18 ---
box(ax, 0.035, -0.105, 0.93, 0.088,
    '1,000핸드 실측    전체 관측 1,689  →  pcz 진입 183  →  465 탈락 36  →  최종 giveup 31\n'
    'h18   eq .586   outs 20   rel .02   made 0   →   439 진입 → 442 · 458 탈락 → 465 → giveup'
    '      (468 semibluff 도달 안 함)',
    fc='#fff0ee', ec=C_BAD, fs=9.5, bold=True)

ax.set_ylim(-0.12, 1.0)
plt.savefig('docs/EQREL_V1.png', bbox_inches='tight', facecolor='white')
print('docs/EQREL_V1.png')
