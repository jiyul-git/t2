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


# ---------- 상황 근거 → 근접도 c (0 쉬움 ~ 1 아슬아슬) ----------
def c_facing(eq, need):
    return max(0.0, 1.0 - abs(eq - need) / 0.15)


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
def visible_time(t, c, s, m, K, trivial, rng):
    D_c = 0.60 * c * (0.55 + 0.45 * K)          # 근접도: 몰라도 어느 정도 느낌
    D_o = K * (0.25 * s + 0.15 * m)             # 구조·돈 압박: 알아야 느낌
    P = min(1.0, D_c + D_o)
    reasoning = t['pace'] * (0.6 + 11.0 * t['tank'] * P ** 1.6)
    hold = max(t['mask'] * 6.0, t['clock'] * BASE)
    if trivial:
        hold *= 0.3                              # 쓰레기 패 즉시 폴드는 숨길 이유가 적다
    jitter = math.exp(rng.gauss(0.0, 0.20))
    return max(reasoning, hold) * jitter, P


def main():
    trace = json.load(open(sys.argv[1]))
    rng = random.Random(20261005)
    spots = []
    for h in trace['hands']:
        for i in h['intents']:
            st_ = {'flop': 0.33, 'turn': 0.67, 'river': 1.0}.get(i.get('street'), 0.5)
            bf = float(i.get('bf') or 1.0)
            m = max(0.0, min(1.0, (bf - 1.0) / 0.6))
            if i.get('resp_eq') is not None and i.get('resp_need') is not None:
                c = c_facing(i['resp_eq'], i['resp_need'])
                s = min(1.0, 0.6 * st_ + 0.4)
            else:
                eq = i.get('eq')
                if eq is None:
                    continue
                c = c_choice(float(eq))
                s = 0.6 * st_
            spots.append((c, s, m, False))
    n_post = len(spots)
    for p in trace['pf']:
        c, triv = c_preflop(p)
        s = 0.3 * min(1.0, (int(p.get('rlevel') or 1) - 1) / 2.0)
        spots.append((c, s, 0.0, triv))
    n_dec = len(spots)
    per_hand = n_dec / max(1, len(trace['hands'])) / 8.0

    players = [make_traits(rng) for _ in range(400)]
    by = {}
    corr = {}
    bank_hands = {}
    for t in players:
        K = rng.uniform(0.3, 0.95)
        k = kind(t)
        vs, Ps = [], []
        for _ in range(300):
            c, s, m, triv = spots[rng.randrange(n_dec)]
            v, P = visible_time(t, c, s, m, K, triv, rng)
            vs.append(v); Ps.append(P)
        by.setdefault(k, []).extend(vs)
        corr.setdefault(k, []).append(st.correlation(Ps, vs) if len(set(Ps)) > 1 else 0.0)
        # 타임뱅크 60초(충전 없음)가 몇 핸드 만에 바닥나는가
        bank, hands, dec_acc = BANK0, 0, 0.0
        while bank > 0 and hands < 3000:
            hands += 1
            dec_acc += per_hand
            while dec_acc >= 1.0:
                dec_acc -= 1.0
                c, s, m, triv = spots[rng.randrange(n_dec)]
                v, _ = visible_time(t, c, s, m, K, triv, rng)
                bank -= max(0.0, v - BASE)
        bank_hands.setdefault(k, []).append(hands)

    q = lambda a, x: sorted(a)[int(x * (len(a) - 1))]
    # 어려운 포스트플랍(근접도 c >= 0.7)만: 유형별 보이는 시간
    hard = [sp for sp in spots[:n_post] if sp[0] >= 0.7]
    easy = [sp for sp in spots[:n_post] if sp[0] <= 0.1]
    hard_by = {}
    easy_by = {}
    for t in players:
        K = 0.7
        k = kind(t)
        for sp in hard[:200]:
            hard_by.setdefault(k, []).append(visible_time(t, sp[0], sp[1], sp[2], K, False, rng)[0])
        for sp in easy[:200]:
            easy_by.setdefault(k, []).append(visible_time(t, sp[0], sp[1], sp[2], K, False, rng)[0])
    out = {'decisions_in_trace': n_dec, 'decisions_per_player_hand': round(per_hand, 2), 'types': {}}
    for k, vs in sorted(by.items()):
        out['types'][k] = {
            'players': len(corr[k]),
            'p10': round(q(vs, .1), 1), 'p50': round(q(vs, .5), 1), 'p90': round(q(vs, .9), 1),
            'p99': round(q(vs, .99), 1),
            'over_base_pct': round(100 * sum(v > BASE for v in vs) / len(vs), 2),
            'corr_difficulty_time': round(st.mean(corr[k]), 2),
            'hands_until_bank_empty_median': q(bank_hands[k], .5),
            'postflop_easy_p50': round(q(easy_by[k], .5), 1),
            'postflop_hard_p50': round(q(hard_by[k], .5), 1),
            'postflop_hard_p90': round(q(hard_by[k], .9), 1),
        }
    out['postflop_hard_share_pct'] = round(100 * len(hard) / max(1, n_post), 1)
    out['preflop_trivial_fold_share_pct'] = round(100 * sum(1 for sp in spots[n_post:] if sp[3]) / max(1, n_dec), 1)
    print(json.dumps(out, indent=1, ensure_ascii=False))

    if len(sys.argv) > 2:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib import font_manager as fm
        names = list(out['types'])
        en = {'일반형': 'normal', '숨기는형': 'masker', '시계사용형': 'clock-user',
              '충동형': 'impulsive', '느린형': 'slow'}
        fig, ax = plt.subplots(1, 2, figsize=(12, 4.8))
        ax[0].boxplot([by[k] for k in names], tick_labels=[en[k] for k in names],
                      showfliers=False, whis=(10, 90))
        ax[0].axhline(BASE, color='red', ls='--', lw=1)
        ax[0].text(0.6, BASE + 0.4, 'base 18s', color='red')
        ax[0].set_ylabel('visible action time (s)')
        ax[0].set_title('Visible time by timing type (box 25-75%, whisker 10-90%)', fontsize=10)
        ax[1].bar([en[k] for k in names], [out['types'][k]['corr_difficulty_time'] for k in names],
                  color='#4a7')
        ax[1].set_title('Correlation: perceived difficulty vs visible time\n(lower = less timing tell)',
                        fontsize=10)
        ax[1].set_ylim(0, 1)
        fig.suptitle('Bot timing design sim (proposed formula, %d real decisions, seed 11 beta trace)' % n_dec,
                     fontsize=11)
        fig.tight_layout()
        fig.savefig(sys.argv[2], dpi=110)


if __name__ == '__main__':
    main()
