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


def _depth(effbb):
    return ('<20bb' if effbb < 20 else '20-30bb' if effbb < 30 else
            '30-50bb' if effbb < 50 else '>=50bb')


def _phase(stg):
    if not stg:
        return 'unknown'
    r, itm = stg['remaining'], stg['itm']
    if r <= itm:
        return 'itm'
    if r <= itm * 1.20:                          # field.Field.BUBBLE_HI
        return 'bubble'
    return 'pre_bubble'


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
            opp_c = (max([float(x) for x in opp.values()]) * bb) if isinstance(opp, dict) and opp else stack
            eff = max(1.0, min(stack, opp_c))
            if i.get('resp_eq') is not None and i.get('resp_need') is not None:
                c = c_facing(i['resp_eq'], i['resp_need'])
                s = min(1.0, 0.6 * st_ + 0.4)
                commit = min(1.0, float(i.get('tocall') or 0.0) / eff)
            else:
                eq = i.get('eq')
                if eq is None:
                    continue
                c = c_choice(float(eq))
                s = 0.6 * st_
                commit = min(1.0, float(i.get('calc_amt') or i.get('amt') or 0.0) / eff)
            post.append((c, s, m, False, commit, _depth(eff / bb), ph))
    for p in trace['pf']:
        c, triv = c_preflop(p)
        s = 0.3 * min(1.0, (int(p.get('rlevel') or 1) - 1) / 2.0)
        sd = p['seed']
        stk = float(sd.get('pf_stack_bb') or p.get('bbs') or 100.0)
        commit = min(1.0, float(sd.get('pf_to_call_bb') or 0.0) / max(1.0, stk))
        pre.append((c, s, 0.0, triv, commit, _depth(stk), _phase(stage.get(p.get('hash')))))
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
    """후반 실제 상태 추적으로 단계별 측정.  --stages OUT.json[.png] TRACE...  """
    out_path, paths = args[0], args[1:]
    post, pre = [], []
    for pth in paths:
        a, b = load_spots(json.load(open(pth)))
        post += a; pre += b
    allsp = post + pre
    players = population()
    tank_p90 = sorted(t['tank'] for t in players)[int(0.9 * (len(players) - 1))]
    q = lambda a, x: sorted(a)[int(x * (len(a) - 1))] if a else None
    mean = lambda a: round(st.mean(a), 1) if a else None

    # 실제 스팟 그대로(구성 없음)
    hard_post = [sp for sp in post if sp[0] >= 0.7 and sp[4] >= 0.5]
    hard_pre = [sp for sp in pre if sp[0] >= 0.7 and sp[4] >= 0.5]
    hard_allin = hard_post + hard_pre
    obvious_allin = [sp for sp in post + pre if sp[0] <= 0.1 and sp[4] >= 0.5]

    def allin_eval(B, G, n=12):
        rng = random.Random(5)
        hk, ok, top = {}, {}, []
        for t in players:
            for _ in range(n):
                v = visible_time(t, hard_allin[rng.randrange(len(hard_allin))], t['K'], rng, B, G)[0]
                hk.setdefault(t['kind'], []).append(v)
                if t['tank'] >= tank_p90:
                    top.append(v)
                ok.setdefault(t['kind'], []).append(
                    visible_time(t, obvious_allin[rng.randrange(len(obvious_allin))], t['K'], rng, B, G)[0])
        return hk, ok, top

    grid = []
    for G in (1.0, 1.5):
        for B in (2.0, 3.0, 4.0, 5.0, 6.0, 8.0):
            hk, ok, top = allin_eval(B, G)
            grid.append({'B': B, 'G': G, 'normal_hard_allin_mean': mean(hk['일반형']),
                         'normal_hard_allin_p90': round(q(hk['일반형'], .9), 1),
                         'top10_tank_mean': mean(top), 'top10_tank_p50': round(q(top, .5), 1),
                         'normal_obvious_allin_mean': mean(ok['일반형']),
                         'slow_hard_allin_mean': mean(hk['느린형']),
                         'impulsive_hard_allin_mean': mean(hk['충동형'])})

    def in_target(g):
        return 20 <= g['normal_hard_allin_mean'] <= 24 and 30 <= g['top10_tank_mean'] <= 40

    # 단계 구분: 깊이 × (버블 전 / 버블 / ITM)
    buckets = {}
    for sp in allsp:
        buckets.setdefault(('depth', sp[5]), []).append(sp)
        buckets.setdefault(('phase', sp[6]), []).append(sp)
        if sp[6] == 'pre_bubble':
            buckets.setdefault(('pre_bubble_depth', sp[5]), []).append(sp)
    buckets[('all', 'all')] = allsp

    def tb_hour(B, G, pool, hours=4):
        rng = random.Random(11)
        res = {}
        for t in players:
            over = 0.0
            for _ in range(hours * HOUR_DECISIONS):
                v = visible_time(t, pool[rng.randrange(len(pool))], t['K'], rng, B, G)[0]
                over += max(0.0, v - BASE)
            res.setdefault(t['kind'], []).append(over / hours)
        return {k: {'mean': mean(v), 'p50': round(q(v, .5), 1), 'p90': round(q(v, .9), 1)}
                for k, v in sorted(res.items())}

    tb = {}
    for B in (3.0, 4.0, 5.0):
        for key, pool in sorted(buckets.items()):
            if len(pool) < 200:
                continue
            tb.setdefault('B%g' % B, {})['%s:%s' % key] = tb_hour(B, 1.0, pool)

    counts = {}
    for key, pool in sorted(buckets.items()):
        n = len(pool)
        ha = sum(1 for sp in pool if sp[0] >= 0.7 and sp[4] >= 0.5)
        counts['%s:%s' % key] = {
            'decisions': n,
            'hard_allin': ha,
            'hard_allin_per_hour': round(HOUR_DECISIONS * ha / n, 2) if n else None,
            'commit>=0.5_share_pct': round(100 * sum(1 for sp in pool if sp[4] >= 0.5) / n, 1) if n else None,
        }
    out = {'traces': paths, 'postflop': len(post), 'preflop': len(pre),
           'real_hard_allin_spots': len(hard_allin), 'real_hard_allin_post_pre': [len(hard_post), len(hard_pre)], 'real_obvious_allin_spots': len(obvious_allin),
           'bucket_counts': counts, 'allin_grid': grid,
           'grid_in_target': [g for g in grid if in_target(g)], 'tb_per_hour': tb}
    json.dump(out, open(out_path, 'w'), indent=1, ensure_ascii=False)
    print(json.dumps({k: out[k] for k in ('postflop', 'preflop', 'real_hard_allin_spots',
                                          'real_obvious_allin_spots', 'grid_in_target')},
                     indent=1, ensure_ascii=False))

if __name__ == '__main__':
    main()
