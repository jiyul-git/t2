#!/usr/bin/env python3
"""구조도 v1 — 실제 런타임 경로와 검증 계층을 분리해 PNG 로 그린다.

  python3 tools/draw_arch.py docs/ARCH_V1.png

**진단용 계측 코드를 런타임 구조처럼 그리지 않는다.** 위쪽은 엔진이
실제로 도는 경로이고, 아래쪽은 그 경로를 밖에서 관측하는 검증 계층이다.
"""
import sys, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

FP = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
fm.fontManager.addfont(FP)
plt.rcParams['font.family'] = fm.FontProperties(fname=FP).get_name()
plt.rcParams['axes.unicode_minus'] = False

INK   = '#1b1b1f'
MUTED = '#6b6b76'
RUN   = '#e8eef7'; RUN_E = '#4a6fa5'      # 런타임
PLAN  = '#eaf2ea'; PLAN_E = '#4d7c4d'     # 계획층
EXEC  = '#faf0e4'; EXEC_E = '#b07c34'     # 실행층
VER   = '#f2eef7'; VER_E = '#7a5ea8'      # 검증 계층


def box(ax, x, y, w, h, text, fc, ec, fs=9, bold=False, ls='-'):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle='round,pad=0.012,rounding_size=0.02',
                                fc=fc, ec=ec, lw=1.3, ls=ls, zorder=2))
    ax.text(x + w/2, y + h/2, text, ha='center', va='center', fontsize=fs,
            color=INK, zorder=3, linespacing=1.45,
            fontweight=('bold' if bold else 'normal'))


def arrow(ax, p, q, ec=MUTED, ls='-', lw=1.2, rad=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle='-|>', mutation_scale=11,
                                 color=ec, lw=lw, ls=ls, zorder=1,
                                 connectionstyle='arc3,rad=%.2f' % rad,
                                 shrinkA=2, shrinkB=2))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'docs/ARCH_V1.png'
    fig, ax = plt.subplots(figsize=(13.6, 12.0))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')

    ax.text(0.5, 0.977, '구조도 v1 - 실제 런타임 경로와 검증 계층',
            ha='center', fontsize=15, fontweight='bold', color=INK)
    ax.text(0.5, 0.956,
            '기준 커밋 8be8b4e (Level 2 결과)  ·  검증 CF_RESULT_NORM.md  ·  plan.py 무수정',
            ha='center', fontsize=8.5, color=MUTED)

    # ================= 런타임 =================
    ax.add_patch(FancyBboxPatch((0.025, 0.415), 0.95, 0.520,
                                boxstyle='round,pad=0.008,rounding_size=0.02',
                                fc='#fbfcfe', ec=RUN_E, lw=1.0, zorder=0))
    ax.text(0.042, 0.916, '런타임 - 엔진이 실제로 도는 경로', fontsize=10.5,
            fontweight='bold', color=RUN_E)

    # 진입 체인
    box(ax, 0.05, 0.855, 0.185, 0.044, 'fieldsim\n_play_table', RUN, RUN_E, 8.5)
    box(ax, 0.275, 0.855, 0.185, 0.044, 'session.HandRun\n_run  (113)', RUN, RUN_E, 8.5)
    box(ax, 0.50, 0.855, 0.245, 0.044,
        "for street in flop/turn/river  (306)\n프리플랍은 여기 없다", RUN, RUN_E, 8)
    box(ax, 0.785, 0.855, 0.165, 0.044, 'while True  (315)\n한 스트리트의 액션 라운드',
        RUN, RUN_E, 7.5)
    for a, b in ((0.235, 0.275), (0.46, 0.50), (0.745, 0.785)):
        arrow(ax, (a, 0.877), (b, 0.877))

    box(ax, 0.05, 0.778, 0.31, 0.046,
        'update_plan   session.py:436\n계획 갱신의 유일한 진입점', RUN, RUN_E, 8.5, True)
    arrow(ax, (0.8675, 0.855), (0.205, 0.824), rad=-0.11)

    # ---- 계획층 ----
    ax.text(0.055, 0.748, '계획층 (L2)', fontsize=9.5, fontweight='bold', color=PLAN_E)
    box(ax, 0.05, 0.672, 0.31, 0.052,
        'make_plan / revise_plan → refresh\n→ river_fix → _allowed', PLAN, PLAN_E, 8.5)
    box(ax, 0.05, 0.600, 0.31, 0.052,
        'perceived_rel  (312 / 1698)\n→ state["rel"]', PLAN, PLAN_E, 8.5)
    arrow(ax, (0.205, 0.778), (0.205, 0.724))
    arrow(ax, (0.205, 0.672), (0.205, 0.652))

    box(ax, 0.05, 0.512, 0.31, 0.050,
        'if intent_of(st, street) is None\nplan.py:1521', RUN, RUN_E, 8.5, True)
    arrow(ax, (0.205, 0.600), (0.205, 0.562))
    ax.text(0.205, 0.487, '거짓이면 attach_intent 를 건너뛴다 = 반복 호출 6,188',
            fontsize=7.5, color=MUTED, ha='center')
    ax.text(0.205, 0.466, '참인 호출 31,189 = attached_O = 비교 단위',
            fontsize=7.5, color=RUN_E, ha='center')

    # ---- 실행층 ----
    ax.text(0.445, 0.748, '실행층 (L1) - attach_intent 안', fontsize=9.5,
            fontweight='bold', color=EXEC_E)
    box(ax, 0.44, 0.672, 0.245, 0.052, 'decide_aggression → p\nplan.py:556', EXEC, EXEC_E, 8.5)
    box(ax, 0.44, 0.600, 0.245, 0.052, '_roll = rng.random()\nplan.py:559', EXEC, EXEC_E, 8.5)
    box(ax, 0.44, 0.528, 0.245, 0.052, 'roll < p ?\nplan.py:562', EXEC, EXEC_E, 8.5, True)
    box(ax, 0.715, 0.528, 0.235, 0.052, 'decide_size → size\nplan.py:563', EXEC, EXEC_E, 8.5, True)
    box(ax, 0.44, 0.440, 0.510, 0.054,
        "size > 0 → intent 'bet'  (569)        size == 0 → intent 'check'  (575)\n"
        "roll >= p → intent 'check'  (577)", EXEC, EXEC_E, 8)

    arrow(ax, (0.36, 0.537), (0.44, 0.694), rad=0.20)
    arrow(ax, (0.5625, 0.672), (0.5625, 0.652))
    arrow(ax, (0.5625, 0.600), (0.5625, 0.580))
    arrow(ax, (0.685, 0.554), (0.715, 0.554))
    arrow(ax, (0.8325, 0.528), (0.75, 0.494), rad=0.10)
    arrow(ax, (0.5625, 0.528), (0.56, 0.494), ls='--')

    arrow(ax, (0.36, 0.626), (0.44, 0.690), ec=PLAN_E, ls='--', rad=-0.22)
    ax.text(0.400, 0.662, 'rel', fontsize=8.5, color=PLAN_E, ha='center', va='center')

    # ================= 검증 =================
    ax.add_patch(FancyBboxPatch((0.025, 0.052), 0.95, 0.336,
                                boxstyle='round,pad=0.008,rounding_size=0.02',
                                fc='#fdfcfe', ec=VER_E, lw=1.0, ls='--', zorder=0))
    ax.text(0.042, 0.370, '검증 계층 - 위 경로를 밖에서 관측한다. 런타임이 아니다',
            fontsize=10.5, fontweight='bold', color=VER_E)

    box(ax, 0.05, 0.262, 0.275, 0.082,
        'Level 1   tools/cf_axis.py\nattach_intent 를 감싼다\n'
        'decide_aggression 만 반사실 호출\n→ plan.py:556 을 관측', VER, VER_E, 8, ls='--')
    box(ax, 0.365, 0.262, 0.275, 0.082,
        'Level 2   tools/cf_axis_l2.py\nupdate_plan 을 감싼다\n'
        '실행층 아홉 함수를 교체\n→ session.py:436 을 관측', VER, VER_E, 8, ls='--')
    box(ax, 0.68, 0.262, 0.270, 0.082,
        '진단 계측  d1e6cac\np · size · src 를 팔·tag 별 기록\n--rows → JSONL.gz\n'
        '→ plan.py:556 · 563 을 관측', VER, VER_E, 8, ls='--')

    box(ax, 0.05, 0.158, 0.900, 0.082,
        'tools/l2_recount.py - 같은 원자료에 두 정의를 모두 적용한다\n'
        'L1등가_act = "bet" if crossed else "check"   (size 단계 전)      vs      '
        'L2실제_act = intent 의 act   (size 단계 후)\n'
        'crossed 는 src 로 복원한다 - act == "bet" 이거나 src == "사이즈 0 → 체크"',
        VER, VER_E, 8.5, ls='--')
    for x in (0.1875, 0.5025, 0.815):
        arrow(ax, (x, 0.262), (x, 0.240), ec=VER_E, ls='--')

    box(ax, 0.05, 0.070, 0.900, 0.078,
        '실측  55시드 · 분모 31,176\n'
        'aggression D   L1 9.2%   ·   L1등가 2,876 (9.225%)  →  L2실제 2,567 (8.234%)    차 309건\n'
        'bluff      D   L1 3.5%   ·   L1등가 1,090 (3.496%)  →  L2실제   979 (3.140%)    차 111건\n'
        'aggression M   L1등가 110  →  L2실제 117    차 -7    ← size 단계는 양방향이다',
        '#ffffff', VER_E, 8, ls='--')

    ax.text(0.5, 0.020,
            'size 단계가 flip 을 제거하는 원인이라고 쓰지 않는다 - '
            '동일 실행에서 size 적용 전후의 차이가 그 잔여 차이를 구성한다는 관측이다',
            ha='center', fontsize=8, color=MUTED, style='italic')

    fig.savefig(out, dpi=170, bbox_inches='tight', facecolor='white')
    print('wrote', out)


if __name__ == '__main__':
    main()
