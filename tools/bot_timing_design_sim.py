#!/usr/bin/env python3
"""Design simulation for bot thinking time (no production code is changed).

Reads a beta trace (tools/beta_trace.py output) for real decision provenance and
applies the *proposed* formula and timing-personality distributions from
docs/semantic_audit/TIME_SYSTEM_DESIGN.md §F/§E.  Everything here is a candidate
for the user's decision, not a calibrated value.

  python tools/bot_timing_design_sim.py TRACE.json [OUT.png]
"""
import json, math, random, statistics as st, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import gto as G

BASE = 18.0          # 사용자 결정: 일반 MTT 기본 액션 18초
BANK0 = 60.0         # 사용자 결정: 시작 타임뱅크 60초, 충전 없음
HOUR_DECISIONS = 110  # 약 70핸드/시간 × 1.57 결정/플레이어-핸드
AMP_B = 1.0          # 커밋 증폭 계수(후보) — main 의 격자 탐색으로 정한다
AMP_G = 1.0


# ---------- 상황 근거 → 근접도 c (0 쉬움 ~ 1 아슬아슬) ----------
def c_facing(eq, need):
    return max(0.0, 1.0 - abs(eq - need) / 0.15)


import re
_PCT = re.compile(r'\((\d+)%\)')
CLOSENESS = 'v1'     # v1: eq-need 절대폭 0.15(기록값) / v2: 최종 비교값·상대폭·분기확률
#                      v3: v2 응답 + 믹스확률·규칙 선택 제거 + 프리플랍 인간모델 경계


def c_final(eq_used, need_used):
    """v2 응답 근접도: 실제로 비교된 eq/need, 폭은 need 에 비례(0.03~0.15).

    need 가 작으면(가격이 좋아 사실상 콜이 정해진 숏스택) 같은 절대차도 멀다.
    need 가 0.3 이상인 진짜 코인플립 경계(버블 올인 콜 등)는 v1 과 같은 폭이다.
    """
    w = min(0.15, max(0.03, 0.5 * need_used))
    return max(0.0, 1.0 - abs(eq_used - need_used) / w)


RANK_W = 2.0         # 프리플랍 경계 폭 배수(defend 혼합폭 대비). 민감도: K.6


def c_rank(r, thr):
    """핸드 백분위 r 과 인간모델 임계값 thr 의 거리. 폭은 defend 혼합폭(max(0.015, 0.15·thr))의 RANK_W 배."""
    w = RANK_W * max(0.015, 0.15 * thr)
    return max(0.0, 1.0 - abs(r - thr) / w)


def c_preflop_human(p):
    """v3 프리플랍: timing_trace 가 남긴 인간모델의 최종 선택 경계."""
    pb = p.get('pf_bound') or {}
    bs = pb.get('bounds') or []
    if pb.get('calloff_layer') and pb['calloff_layer'].get('eq') is not None:
        cl = pb['calloff_layer']
        c = c_final(float(cl['eq']), float(cl['need']))
    elif not bs:
        return 0.0, p['act'] == 'fold'
    else:
        b = bs[-1]
        if b.get('eq') is not None and b.get('need') is not None:
            c = c_final(b['eq'], b['need'])
        elif 'cap' in b:
            c = c_rank(b['r'], b['cap'])
        elif 'tot' in b:
            c = c_rank(b['r'], b['tot'])
        else:
            c = c_rank(b['r'], b['thr'])
    return c, (p['act'] == 'fold' and c < 0.05)


def c_branch(p):
    """확률 분기(믹스)의 근접도: 50% 에 가까울수록 1."""
    return max(0.0, 1.0 - abs(2.0 * p - 1.0))


def c_choice(eq):
    # 가정: 벳/체크 선택은 중간 강도가 가장 어렵다. 구현 때는 실제 분기 확률을 쓴다.
    return max(0.0, 1.0 - abs(eq - 0.5) / 0.30)


def c_preflop(p):
    s = p['seed']
    pct = s.get('pf_hand_pct')
    if pct is None:
        return 0.0, True
    bb = float(p.get('bbs') or 100.0)
    if s.get('pf_decision_kind') == 'unopened':
        thr = G.rfi(p['pos'], 9, bb, True) or 0.01
    else:
        try:
            thr = G.defend_pct(p['pos'], p.get('aggr_pos') or 'HJ', 9, bb, True,
                               float(p.get('open_bb') or 2.5))
        except Exception:
            thr = 0.2
    c = max(0.0, 1.0 - abs(pct - thr) / max(0.04, 0.35 * thr))
    trivial = (p['act'] == 'fold' and c < 0.05)
    return c, trivial


# ---------- 성향 분포(새 prior 후보) ----------
def make_traits(rng):
    pace = math.exp(rng.gauss(math.log(1.5), 0.35))            # 쉬운 결정 기본 초
    tank = 0.2 + 1.8 * rng.betavariate(2.0, 2.5)                # 어려움 민감도
    u = rng.random()
    mask = (rng.uniform(0, 0.15) if u < 0.70 else
            rng.uniform(0.3, 0.6) if u < 0.90 else rng.uniform(0.7, 1.0))
    clock = rng.uniform(0.30, 0.75) if rng.random() < 0.15 else 0.0
    return {'pace': pace, 'tank': tank, 'mask': mask, 'clock': clock}


def kind(t):
    if t['clock'] > 0:
        return '시계사용형'
    if t['mask'] >= 0.7:
        return '숨기는형'
    if t['tank'] < 0.6 and t['pace'] < 1.3:
        return '충동형'
    if t['pace'] > 2.1:
        return '느린형'
    return '일반형'


# ---------- 공식 ----------
def visible_time(t, sp, K, rng, B=None, G=None):
    """sp = (c, s, m, trivial, commit).

    commit 은 독립 난이도가 아니다: commit_effect = commit × c(결정 근접도).
    명백한 올인(c≈0)은 커밋이 커도 빠르게 남는다.
    """
    c, s, m, trivial, commit = sp[:5]
    B = AMP_B if B is None else B
    G = AMP_G if G is None else G
    D_c = 0.60 * c * (0.55 + 0.45 * K)          # 근접도: 몰라도 어느 정도 느낌
    D_o = K * (0.25 * s + 0.15 * m)             # 구조·돈 압박: 알아야 느낌
    P = min(1.0, D_c + D_o)
    effect = commit * c                         # commit_pressure × decision_closeness
    reasoning = t['pace'] * (0.6 + 11.0 * t['tank'] * P ** 1.6) * (1.0 + B * effect ** G)
    hold = max(t['mask'] * 6.0, t['clock'] * BASE)
    if trivial:
        hold *= 0.3                              # 쓰레기 패 즉시 폴드는 숨길 이유가 적다
    jitter = math.exp(rng.gauss(0.0, 0.20))
    return max(reasoning, hold) * jitter, P


DEPTHS = ('40bb+', '25-40bb', '15-25bb', '<15bb')
PHASES = ('early_mid', 'bubble', 'itm', 'final')


def _depth(effbb):
    return ('<15bb' if effbb < 15 else '15-25bb' if effbb < 25 else
            '25-40bb' if effbb < 40 else '40bb+')


def _phase(stg, max_seat=9):
    """상호배타 구간 — 한 결정은 한 구간에만 들어간다.

    우선순위: final(남은 ≤ 한 테이블+1) > itm(남은 ≤ ITM) > bubble(남은 ≤ ITM×1.2) > early_mid.
    예: 10명 남은 ITM 결정은 final 로만 집계된다.
    """
    if not stg:
        return 'unknown'
    r, itm = stg['remaining'], stg['itm']
    if r <= max_seat + 1:
        return 'final'
    if r <= itm:
        return 'itm'
    if r <= itm * 1.20:                          # field.Field.BUBBLE_HI
        return 'bubble'
    return 'early_mid'


def _pf_kind(p):
    pb = p.get('pf_bound') or {}
    if pb.get('calloff_layer'):
        return 'calloff_layer'
    bs = pb.get('bounds') or []
    if not bs:
        return 'unknown'
    k = bs[-1]['kind']
    return k + ('_eq' if bs[-1].get('eq') is not None else '')


def load_spots(trace):
    """(c, s, m, trivial, commit, depth, phase) — 포스트플랍 먼저, 그다음 프리플랍."""
    stage = trace.get('stage') or {}
    post, pre = [], []
    for h in trace['hands']:
        bb = float(h.get('bb') or 100.0)
        ph = _phase(stage.get(h.get('hash')))
        for i in h['intents']:
            st_ = {'flop': 0.33, 'turn': 0.67, 'river': 1.0}.get(i.get('street'), 0.5)
            bf = float(i.get('bf') or 1.0)
            m = max(0.0, min(1.0, (bf - 1.0) / 0.6))
            stack = float(i.get('stack') or 0.0)
            opp = i.get('opp_stack_bbs')
            opp_rem = (max([float(x) for x in opp.values()]) * bb) if isinstance(opp, dict) and opp else None
            tocall = float(i.get('tocall') or 0.0)
            facing = i.get('resp_eq') is not None and i.get('resp_need') is not None
            if CLOSENESS == 'v1':
                opp_c = opp_rem if opp_rem is not None else stack
                eff = max(1.0, min(stack, opp_c))
            else:
                # 상대가 이미 올인(남은 0)이어도 상대가 건 금액만큼은 맞서 있다.
                opp_c = (opp_rem + (tocall if facing else 0.0)) if opp_rem is not None else stack
                eff = max(1.0, min(stack, opp_c) if opp_c > 0 else stack)
            if facing:
                if CLOSENESS == 'v3' and i.get('dr_eq_used') is not None:
                    # 레이즈 믹스 확률은 전략 빈도라 쓰지 않는다. 콜/폴드 경계 거리만.
                    c = c_final(float(i['dr_eq_used']), float(i['dr_need_used']))
                elif CLOSENESS == 'v3':
                    c = c_final(float(i['resp_eq']), float(i['resp_need']))
                elif CLOSENESS == 'v2' and i.get('dr_eq_used') is not None:
                    pm = _PCT.search(i.get('dr_why') or '')
                    if i.get('dr_act') == 'raise' and pm:
                        c = c_branch(int(pm.group(1)) / 100.0)
                    else:
                        c = c_final(float(i['dr_eq_used']), float(i['dr_need_used']))
                elif CLOSENESS == 'v2':
                    c = c_final(float(i['resp_eq']), float(i['resp_need']))
                else:
                    c = c_facing(i['resp_eq'], i['resp_need'])
                s = min(1.0, 0.6 * st_ + 0.4)
                commit = min(1.0, tocall / (eff if CLOSENESS == 'v1' else max(1.0, stack)))
            else:
                eq = i.get('eq')
                if eq is None:
                    continue
                if CLOSENESS == 'v3':
                    # 경쟁 선택지 점수/임계값이 기록돼 있지 않다 → 낮은 기본 난이도.
                    c = 0.0
                else:
                    pm = _PCT.search(i.get('intent_src') or '') if CLOSENESS == 'v2' else None
                    c = c_branch(int(pm.group(1)) / 100.0) if pm else c_choice(float(eq))
                s = 0.6 * st_
                commit = min(1.0, float(i.get('calc_amt') or i.get('amt') or 0.0) / eff)
            post.append((c, s, m, False, commit, _depth(eff / bb), ph,
                         'post_response' if facing else 'post_choice'))
    for p in trace['pf']:
        c, triv = c_preflop_human(p) if CLOSENESS == 'v3' else c_preflop(p)
        s = 0.3 * min(1.0, (int(p.get('rlevel') or 1) - 1) / 2.0)
        sd = p['seed']
        stk = float(sd.get('pf_stack_bb') or p.get('bbs') or 100.0)
        commit = min(1.0, float(sd.get('pf_to_call_bb') or 0.0) / max(1.0, stk))
        pre.append((c, s, 0.0, triv, commit, _depth(stk), _phase(stage.get(p.get('hash'))),
                    'pre_' + _pf_kind(p)))
    return post, pre


def main():
    if sys.argv[1] == '--stages':
        return stage_main(sys.argv[2:])
    trace = json.load(open(sys.argv[1]))
    rng = random.Random(20261005)
    post, pre = load_spots(trace)
    spots = [sp[:5] for sp in post]
    n_post = len(spots)
    spots += [sp[:5] for sp in pre]
    n_dec = len(spots)

    rng0 = random.Random(20261005)
    players = []
    for _ in range(1000):                       # 모집단 감사 상한 1000명
        t = make_traits(rng0)
        t['K'] = rng0.uniform(0.3, 0.95)
        t['kind'] = kind(t)
        players.append(t)
    tank_p90 = sorted(t['tank'] for t in players)[int(0.9 * (len(players) - 1))]

    # 평가용 스팟: 실제 포스트플랍 스팟의 (c, s, m) 위에 커밋만 바꿔 얹는다.
    post = spots[:n_post]
    hard_base = [sp for sp in post if sp[0] >= 0.7]
    easy_base = [sp for sp in post if sp[0] <= 0.1]
    rs = random.Random(7)
    hard_allin = [(c, s, m, False, rs.uniform(0.5, 1.0)) for (c, s, m, _t, _k) in hard_base]
    obvious_allin = [(c, s, m, False, rs.uniform(0.5, 1.0)) for (c, s, m, _t, _k) in easy_base]
    hard_small = [(c, s, m, False, rs.uniform(0.0, 0.15)) for (c, s, m, _t, _k) in hard_base]
    real_hard_allin = [sp for sp in post if sp[0] >= 0.7 and sp[4] >= 0.5]

    def evaluate(B, G, hours=10, n_eval=120, pool=None):
        pool = spots if pool is None else pool
        rng = random.Random(11)
        q = lambda a, x: sorted(a)[int(x * (len(a) - 1))] if a else float('nan')
        res = {'types': {}}
        tb_hour, gen, corr = {}, {}, {}
        hard_t, obv_t, small_t, tank_hard = {}, {}, {}, []
        for t in players:
            k = t['kind']
            over = 0.0
            vs, Ps = [], []
            for _ in range(hours * HOUR_DECISIONS):
                v, P = visible_time(t, pool[rng.randrange(len(pool))], t['K'], rng, B, G)
                over += max(0.0, v - BASE)
                vs.append(v); Ps.append(P)
            tb_hour.setdefault(k, []).append(over / hours)
            gen.setdefault(k, []).extend(vs[:300])
            corr.setdefault(k, []).append(st.correlation(Ps, vs) if len(set(Ps)) > 1 else 0.0)
            for _ in range(n_eval // 10):
                hv = visible_time(t, hard_allin[rng.randrange(len(hard_allin))], t['K'], rng, B, G)[0]
                hard_t.setdefault(k, []).append(hv)
                if t['tank'] >= tank_p90:
                    tank_hard.append(hv)
                obv_t.setdefault(k, []).append(
                    visible_time(t, obvious_allin[rng.randrange(len(obvious_allin))], t['K'], rng, B, G)[0])
                small_t.setdefault(k, []).append(
                    visible_time(t, hard_small[rng.randrange(len(hard_small))], t['K'], rng, B, G)[0])
        for k in sorted(tb_hour):
            res['types'][k] = {
                'players': len(tb_hour[k]),
                'all_p50': round(q(gen[k], .5), 1), 'all_p90': round(q(gen[k], .9), 1),
                'over_base_pct': round(100 * sum(v > BASE for v in gen[k]) / len(gen[k]), 2),
                'tb_sec_per_hour_mean': round(st.mean(tb_hour[k]), 1),
                'tb_sec_per_hour_p50': round(q(tb_hour[k], .5), 1),
                'tb_sec_per_hour_p90': round(q(tb_hour[k], .9), 1),
                'hard_allin_mean': round(st.mean(hard_t[k]), 1),
                'hard_allin_p90': round(q(hard_t[k], .9), 1),
                'hard_small_commit_mean': round(st.mean(small_t[k]), 1),
                'obvious_allin_mean': round(st.mean(obv_t[k]), 1),
                'obvious_allin_p90': round(q(obv_t[k], .9), 1),
                'corr_difficulty_time': round(st.mean(corr[k]), 2),
            }
        allhard = [v for k in hard_t for v in hard_t[k]]
        res['hard_allin_all_p90'] = round(q(allhard, .9), 1)
        res['top10_tank_hard_allin_mean'] = round(st.mean(tank_hard), 1)
        res['top10_tank_hard_allin_p50'] = round(q(tank_hard, .5), 1)
        res['_raw'] = {'gen': gen, 'hard': hard_t, 'obv': obv_t, 'small': small_t, 'tb': tb_hour}
        return res

    def score(r):
        n = r['types'].get('일반형', {})
        sl = r['types'].get('느린형', {})
        pen = lambda x, lo, hi: 0.0 if lo <= x <= hi else min(abs(x - lo), abs(x - hi))
        return (pen(n['hard_allin_mean'], 20, 24) + pen(r['top10_tank_hard_allin_mean'], 30, 40)
                + pen(n['tb_sec_per_hour_mean'], 6, 12) + pen(sl['tb_sec_per_hour_mean'], 12, 20))

    grid = []
    base = evaluate(0.0, 1.0, hours=4, n_eval=60)
    for G in (1.0, 1.5, 2.0):
        for B in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0):
            r = evaluate(B, G, hours=4, n_eval=60)
            n = r['types']['일반형']
            grid.append({'B': B, 'G': G, 'score': round(score(r), 2),
                         'normal_hard_allin': n['hard_allin_mean'],
                         'top10_tank_hard': r['top10_tank_hard_allin_mean'],
                         'normal_tb_h': n['tb_sec_per_hour_mean'],
                         'slow_tb_h': r['types']['느린형']['tb_sec_per_hour_mean'],
                         'normal_obvious': n['obvious_allin_mean']})
    grid.sort(key=lambda g: g['score'])
    best = grid[0]
    final = evaluate(best['B'], best['G'])
    out = {
        'decisions_in_trace': n_dec,
        'real_hard_allin_spots_in_trace': len(real_hard_allin),
        'eval_hard_allin_spots': len(hard_allin), 'eval_obvious_allin_spots': len(obvious_allin),
        'no_amplifier_B0': {k: {x: v[x] for x in ('hard_allin_mean', 'tb_sec_per_hour_mean', 'obvious_allin_mean')}
                            for k, v in base['types'].items()},
        'no_amplifier_top10_tank_hard': base['top10_tank_hard_allin_mean'],
        'grid_top5': grid[:5],
        'chosen': {'B': best['B'], 'G': best['G']},
        'final': {k: v for k, v in final.items() if k != '_raw'},
    }
    # 단계 민감도: 트레이스는 초반(중앙 80bb)이다. 후반 짧은 스택은 같은 콜 금액이
    # 더 큰 커밋이 되므로 커밋을 ×f 로 근사해 시간당 타임뱅크 사용을 본다.
    sens = {}
    for f in (2.0, 4.0):
        pool = [(c, s_, m, tr, min(1.0, k * f)) for (c, s_, m, tr, k) in spots]
        r = evaluate(best['B'], best['G'], hours=4, n_eval=10, pool=pool)
        sens['commit_x%g' % f] = {k: r['types'][k]['tb_sec_per_hour_mean'] for k in r['types']}
    out['tb_per_hour_stage_sensitivity'] = sens
    print(json.dumps(out, indent=1, ensure_ascii=False))

    if len(sys.argv) > 2:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        raw = final['_raw']
        en = {'일반형': 'normal', '숨기는형': 'masker', '시계사용형': 'clock-user',
              '충동형': 'impulsive', '느린형': 'slow'}
        names = list(final['types'])
        lab = [en[k] for k in names]
        fig, ax = plt.subplots(1, 3, figsize=(16, 5))
        pos = range(len(names))
        for off, key, col, nm in ((-0.27, 'obv', '#7ab', 'obvious all-in (c<=0.1)'),
                                  (0.0, 'small', '#bb7', 'hard, small commit'),
                                  (0.27, 'hard', '#c66', 'hard all-in (c>=0.7)')):
            bp = ax[0].boxplot([raw[key][k] for k in names], positions=[p + off for p in pos],
                               widths=0.24, showfliers=False, whis=(10, 90), patch_artist=True)
            for b in bp['boxes']:
                b.set_facecolor(col)
            ax[0].plot([], [], color=col, lw=8, label=nm)
        ax[0].set_xticks(list(pos), lab)
        ax[0].axhline(BASE, color='red', ls='--', lw=1)
        ax[0].axhspan(20, 24, color='#c66', alpha=0.12)
        ax[0].set_ylabel('visible action time (s)')
        ax[0].set_title('Decision time by spot (box 25-75%, whisker 10-90%)\nshaded = normal hard all-in target 20-24s', fontsize=10)
        ax[0].legend(fontsize=8, loc='upper left')
        ax[1].boxplot([raw['tb'][k] for k in names], tick_labels=lab, showfliers=False, whis=(10, 90))
        ax[1].axhspan(6, 12, color='#4a7', alpha=0.15, label='normal target 6-12')
        ax[1].axhspan(12, 20, color='#a74', alpha=0.12, label='slow target 12-20')
        ax[1].set_ylabel('time bank seconds used per hour')
        ax[1].set_title('Time bank use per hour (110 decisions/h)', fontsize=10)
        ax[1].legend(fontsize=8)
        ax[2].plot([g['B'] for g in sorted(grid, key=lambda g: (g['G'], g['B'])) if g['G'] == best['G']],
                   [g['normal_hard_allin'] for g in sorted(grid, key=lambda g: g['B']) if g['G'] == best['G']],
                   'o-', color='#c66', label='normal hard all-in mean')
        ax[2].plot([g['B'] for g in sorted(grid, key=lambda g: g['B']) if g['G'] == best['G']],
                   [g['top10_tank_hard'] for g in sorted(grid, key=lambda g: g['B']) if g['G'] == best['G']],
                   's-', color='#844', label='top-10% tank hard all-in mean')
        ax[2].plot([g['B'] for g in sorted(grid, key=lambda g: g['B']) if g['G'] == best['G']],
                   [g['normal_obvious'] for g in sorted(grid, key=lambda g: g['B']) if g['G'] == best['G']],
                   '^-', color='#7ab', label='normal obvious all-in mean')
        ax[2].axhspan(20, 24, color='#c66', alpha=0.12)
        ax[2].axhspan(30, 40, color='#844', alpha=0.08)
        ax[2].axvline(best['B'], color='k', ls=':', lw=1)
        ax[2].set_xlabel('amplifier B  (reasoning x (1 + B * (commit*c)^%.1f))' % best['G'])
        ax[2].set_ylabel('seconds')
        ax[2].set_title('Amplifier sweep (chosen B=%.1f, gamma=%.1f)' % (best['B'], best['G']), fontsize=10)
        ax[2].legend(fontsize=8)
        fig.suptitle('Bot timing sim v3: commit_effect = commit_pressure x closeness '
                     '(%d real decisions, seed 11 beta trace, 1000 bots)' % n_dec, fontsize=11)
        fig.tight_layout()
        fig.savefig(sys.argv[2], dpi=110)



def population(n=1000, seed=20261005):
    rng0 = random.Random(seed)
    players = []
    for _ in range(n):                          # 모집단 감사 상한 1000명
        t = make_traits(rng0)
        t['K'] = rng0.uniform(0.3, 0.95)
        t['kind'] = kind(t)
        players.append(t)
    return players


def stage_main(args):
    """단계별 측정.  --stages OUT.json B TRACE...   (B 는 측정용 임시값, 확정 아님)"""
    global CLOSENESS
    out_path, B, paths = args[0], float(args[1]), args[2:]
    global RANK_W
    while paths and paths[0].startswith('--'):
        k, v = paths[0][2:].split('=', 1)
        if k == 'closeness':
            CLOSENESS = v
        elif k == 'rankw':
            RANK_W = float(v)
        paths = paths[1:]
    G = 1.0
    post, pre = [], []
    for pth in paths:
        a, b = load_spots(json.load(open(pth)))
        post += a; pre += b
    allsp = post + pre
    players = population()
    q = lambda a, x: round(sorted(a)[int(x * (len(a) - 1))], 1) if a else None
    mean = lambda a: round(st.mean(a), 1) if a else None
    focus = ('일반형', '느린형')

    def dist(vs):
        return {'mean': mean(vs), 'p50': q(vs, .5), 'p90': q(vs, .9), 'n': len(vs)}

    def think(pool, per_player=6):
        """그 스팟 집합에서 유형별 생각시간 분포."""
        rng = random.Random(5)
        res = {}
        if not pool:
            return {}
        for t in players:
            if t['kind'] not in focus:
                continue
            for _ in range(per_player):
                v = visible_time(t, pool[rng.randrange(len(pool))], t['K'], rng, B, G)[0]
                res.setdefault(t['kind'], []).append(v)
        return {k: dist(v) for k, v in sorted(res.items())}

    def tb_hour(pool, hours=4, by_kind=None):
        rng = random.Random(11)
        res = {}
        for t in players:
            over = 0.0
            for _ in range(hours * HOUR_DECISIONS):
                sp = pool[rng.randrange(len(pool))]
                v = visible_time(t, sp, t['K'], rng, B, G)[0]
                x = max(0.0, v - BASE)
                over += x
                if by_kind is not None and t['kind'] in focus and len(sp) > 7:
                    d = by_kind.setdefault(t['kind'], {})
                    d[sp[7]] = d.get(sp[7], 0.0) + x
            res.setdefault(t['kind'], []).append(over / hours)
        return {k: dist(v) for k, v in sorted(res.items())}

    def _kinds(pool, bk):
        """결정 유형별: 수, 어려운 수, 어려운 올인 수, 일반형/느린형 어려운 결정 생각시간, TB 기여 비율."""
        out = {}
        for k in sorted(set(sp[7] for sp in pool if len(sp) > 7)):
            sub = [sp for sp in pool if len(sp) > 7 and sp[7] == k]
            hd = [sp for sp in sub if sp[0] >= 0.7]
            out[k] = {'n': len(sub), 'hard': len(hd),
                      'hard_allin': sum(1 for sp in hd if sp[4] >= 0.5),
                      'think_hard': think(hd, 3) if len(hd) >= 5 else 'n<5'}
        for t, d in (bk or {}).items():
            tot = sum(d.values()) or 1.0
            for k, v in d.items():
                out.setdefault(k, {})['tb_share_%s' % t] = round(100 * v / tot, 1)
        return out

    def section(pool):
        _bk = {}
        hard = [sp for sp in pool if sp[0] >= 0.7]
        hard_ai = [sp for sp in hard if sp[4] >= 0.5]
        obvious = [sp for sp in pool if sp[0] <= 0.1 and sp[4] >= 0.5]
        big_effect_low_c = [sp for sp in pool if sp[4] >= 0.5 and sp[0] < 0.3]
        return {
            'decisions': len(pool),
            'hard_decisions(c>=0.7)': len(hard),
            'hard_allin(c>=0.7,commit>=0.5)': len(hard_ai),
            'hard_allin_pre_post': [sum(1 for sp in hard_ai if sp in pre_set),
                                    sum(1 for sp in hard_ai if sp not in pre_set)],
            'obvious_allin(c<=0.1,commit>=0.5)': len(obvious),
            'think_all': think(pool),
            'think_hard': think(hard),
            'think_hard_allin': think(hard_ai) if len(hard_ai) >= 5 else 'n<5',
            'think_obvious_allin': think(obvious) if len(obvious) >= 5 else 'n<5',
            'think_commit>=0.5_c<0.3': think(big_effect_low_c) if len(big_effect_low_c) >= 5 else 'n<5',
            'tb_sec_per_hour': tb_hour(pool, by_kind=_bk) if len(pool) >= 100 else 'n<100',
            'by_kind': _kinds(pool, _bk),
        }

    pre_set = _IdSet(pre)
    out = {'traces': paths, 'B_temporary': B, 'G': G, 'closeness': CLOSENESS, 'rank_w': RANK_W,
           'phase_priority': 'final > itm > bubble > early_mid (mutually exclusive)',
           'postflop': len(post), 'preflop': len(pre),
           'all': section(allsp), 'depth': {}, 'phase': {}}
    for d in DEPTHS:
        out['depth'][d] = section([sp for sp in allsp if sp[5] == d])
    for ph in PHASES:
        out['phase'][ph] = section([sp for sp in allsp if sp[6] == ph])
    json.dump(out, open(out_path, 'w'), indent=1, ensure_ascii=False)


class _IdSet:
    """튜플 값이 같아도 프리플랍/포스트플랍 출처를 구분하는 멤버십."""
    def __init__(self, items):
        self.ids = set(id(x) for x in items)

    def __contains__(self, x):
        return id(x) in self.ids


if __name__ == '__main__':
    main()
