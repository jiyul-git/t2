#!/usr/bin/env python3
"""④ 판단층 f 계측 — 프리플랍층 [B] 와 응답층 [C].

  python3 tools/f_trace_layers.py --entries 24 --hpl 12 --seeds 5000-5007

`f_trace.py` 는 `decide_aggression`(포스트플랍 공격) 하나만 감싼다.
그래서 48개 축 중 10개만 측정됐고 `looseness` 같은 프리플랍 축이 통째로
빠졌다. 여기서 나머지 두 층을 같은 방식으로 잰다.

**축마다 "무엇이 f 인가" 를 먼저 정한다.** 층마다 반환값의 성격이 다르다.

  [B] 프리플랍
      persona.open_pct        → 오픈 폭(%)        looseness·pf_range·positional
      preflop.defend_thresholds → (tp, tot)       aggression=tp / looseness·pf_defend=tot
      preflop.open_size_bb    → 오픈 사이즈(bb)   open_size·consistency

  [C] 응답
      plan.calldown_need      → 체감 필요승률     potodds·bluffcatch_*·station·
                                                 bluff_fear·hero_call·sticky
      plan.decide_response    → 행동             reraise·stackoff (실현층)

`defend_thresholds` 는 `(tp, tot)` 를 낸다 — `aggression` 은 tp(3벳 구간),
`looseness` 는 tot(참가 구간)에만 걸린다. 하나만 보면 다른 축이 무반응으로
보인다 (CLAUDE.md 기록).

`calldown_need` 의 need 는 **낮을수록 잘 콜한다.** 기대 방향 부호가
반대인 축이 많으니 표의 '기대' 열을 확인할 것.

읽기 전용. 원본을 정확히 한 번 부르고 반환값을 그대로 돌려준다.
플레이어 식별은 profile['id'] (f_trace.py 와 같은 이유).
"""
import os, sys, argparse, math, statistics as stat, collections
import multiprocessing as mp

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)

# 지표 이름 → (축, 기대 부호). 부호는 f 가 축과 같은 방향이면 +1.
METRICS = {
    'open_pct':      [('looseness', +1), ('pf_range', +1), ('positional', +1)],
    'defend_tp':     [('aggression', +1), ('pf_defend', +1)],
    'defend_tot':    [('looseness', +1), ('pf_defend', +1)],
    'open_size':     [('open_size', +1), ('consistency', +1)],
    # need_ratio = need / need_true. 낮을수록 잘 콜한다 → '잘 콜하는' 축은 −1.
    # need_true 는 코드가 만든 상황 기준선이다(plan.py:633) — 팟오즈와 bf 가
    # 그 안에 있으므로 나누면 상황·ICM 성분이 같이 빠진다. 새 정규화가 아니다.
    'ratio_flop':    [('potodds', -1), ('bluffcatch_early', -1), ('station', -1),
                      ('sticky', -1), ('hero_call', -1), ('bluff_fear', +1),
                      ('range_read', -1), ('sizing_tell', -1)],
    'ratio_turn':    [('potodds', -1), ('bluffcatch_early', -1), ('station', -1),
                      ('hero_call', -1), ('bluff_fear', +1)],
    'ratio_river':   [('potodds', -1), ('bluffcatch_river', -1),
                      ('station', -1), ('hero_call', -1), ('bluff_fear', +1)],
}


def run_one(args):
    entries, hpl, stack, seed, cap = args
    import fieldsim as FS
    import plan as PL
    import preflop as PF
    import persona as PS
    FS.Field.BOT_LOG = 0
    f = FS.Field(entries=entries, start_stack=stack, hero_pid=0, seed=seed,
                 hands_per_level=hpl)
    rec = []
    push = lambda pid, m, v: rec.append({'pid': pid, 'metric': m, 'v': v}) \
        if pid is not None and v is not None else None

    _op = PS.open_pct
    def w_op(prof, pos, seats=8, bb=100.0, ante=True, band=None):
        v = _op(prof, pos, seats, bb, ante, band)
        push(prof.get('id'), 'open_pct', float(v) if not isinstance(v, tuple) else float(v[0]))
        return v
    PS.open_pct = w_op

    _dt = PF.defend_thresholds
    def w_dt(prof, def_pos, opener_pos, bb, open_bb=2.5, n_callers=0,
             raise_level=1, seats=8, ante=True):
        out = _dt(prof, def_pos, opener_pos, bb, open_bb, n_callers,
                  raise_level, seats, ante)
        try:
            tp, tot = out
            push(prof.get('id'), 'defend_tp', float(tp))
            push(prof.get('id'), 'defend_tot', float(tot))
        except Exception:
            pass
        return out
    PF.defend_thresholds = w_dt

    _os_ = PF.open_size_bb
    def w_os(feel, pos, rng, prof=None, ante=True, n_limpers=0,
             bb_chips=None, table_soft=0.0):
        v = _os_(feel, pos, rng, prof, ante, n_limpers, bb_chips, table_soft)
        if prof is not None:
            push(prof.get('id'), 'open_size', float(v))
        return v
    PF.open_size_bb = w_os

    _cn = PL.calldown_need
    def w_cn(profile, hero, board, street, pot, tocall, bf, read,
             to_act_behind, opp_est, n_opp=1, rng=None, _bf_gated=True):
        out = _cn(profile, hero, board, street, pot, tocall, bf, read,
                  to_act_behind, opp_est, n_opp, rng, _bf_gated)
        need = out[0] if isinstance(out, tuple) else out
        # --- plan.py:607-633 을 그대로 복제한다. 줄 대응을 주석으로 박는다. ---
        try:
            _bf = bf
            if profile.get('concepts') and _bf and _bf > 1.0 and not _bf_gated:   # 607
                _bf = PS.icm_bf(profile, _bf)                                     # 608
            _p0 = max(1.0, float(pot) - float(tocall))                            # 617
            _sz_true = float(tocall)/_p0                                          # 618
            _sz_seen = _sz_true                                                   # 620
            if profile.get('concepts') and board:                                 # 622
                _rdz = PS.read_opponent(profile, opp_est) if opp_est else None    # 623
                _sz_seen = PS.size_read(profile,
                                        PS.opp_size_norm(_rdz, _sz_true, street)) # 624
            _tocall_seen = _sz_seen * _p0                                         # 625
            need_true = (_tocall_seen*_bf)/max(1.0, _p0 + 2.0*_tocall_seen)       # 633
            # 자체 검증: 비발동군에서 (tocall*bf)/(pot+tocall) 과 맞는지 본다.
            #
            # **비트 동일성으로 재면 안 된다.** plan.py:630 주석이 "비트까지
            # 같다" 고 하는데 정확하지 않다 — 괄호가 설명하는 분모는 실제로
            # 50만 조합 전부 비트 일치하지만, 분자 _tocall_seen = _sz_seen*_p0
            # 가 (tocall/p0)*p0 왕복이라 5.77% 에서 1~2 ULP 어긋난다.
            # 엔진도 같은 왕복을 하므로(plan.py:625) 복제는 맞고 주장이 과하다.
            # 상대오차로 잰다 — 인자 순서나 p0 오류 같은 진짜 버그는 O(1) 로
            # 어긋나므로 1e-12 로도 충분히 잡힌다.
            fired = abs(_sz_seen - _sz_true) > 1e-12
            ok = None
            if not fired:
                alt = (float(tocall)*_bf)/max(1.0, float(pot) + float(tocall))
                ok = abs(need_true - alt) <= 1e-12*max(abs(need_true), abs(alt), 1e-30)
            rec.append({'pid': profile.get('id'), 'metric': 'ratio_%s' % street,
                        'v': float(need)/need_true if need_true > 0 else None,
                        'need': float(need), 'need_true': need_true,
                        'tocall': float(tocall), 'p0': _p0, 'bf': float(_bf),
                        'sz_true': _sz_true, 'sz_seen': _sz_seen,
                        'fired': fired, 'verify': ok})
        except Exception:
            pass
        return out
    PL.calldown_need = w_cn

    try:
        while f.remaining() > 1 and f.hand_no < cap:
            f.hand_no += 1
            f.advance_level()
            for tid, tb in list(f.tables.items()):
                if tb.n() >= 2:
                    f._play_table(tb)
            f._collect_busts()
            f._balance()
            f.notes = []
    finally:
        PS.open_pct = _op
        PF.defend_thresholds = _dt
        PF.open_size_bb = _os_
        PL.calldown_need = _cn

    axv = {}
    for p in f.players.values():
        d = dict(p['prof']['concepts']); d.update(p['prof']['temper'])
        # persona.bias 파생축은 프로필에 없다 — 여기서 만들어 붙인다.
        try:
            for k in ('station', 'bluff_fear', 'hero_call', 'sticky',
                      'draw_love', 'overpair_love'):
                d[k] = PS.bias(p['prof'], k) if hasattr(PS, 'bias') else None
        except Exception:
            pass
        axv[p['pid']] = d
    return rec, axv, len(f.errors)


def spearman(a, b):
    n = len(a)
    if n < 4: return None
    def rank(x):
        o = sorted(range(n), key=lambda i: x[i]); r = [0.0]*n; i = 0
        while i < n:
            j = i
            while j+1 < n and x[o[j+1]] == x[o[i]]: j += 1
            for k in range(i, j+1): r[o[k]] = (i+j)/2.0 + 1
            i = j+1
        return r
    ra, rb = rank(a), rank(b)
    ma, mb = sum(ra)/n, sum(rb)/n
    num = sum((ra[i]-ma)*(rb[i]-mb) for i in range(n))
    da = math.sqrt(sum((x-ma)**2 for x in ra)); db = math.sqrt(sum((x-mb)**2 for x in rb))
    return num/(da*db) if da and db else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=24)
    ap.add_argument('--hpl', type=int, default=12)
    ap.add_argument('--stack', type=int, default=30000)
    ap.add_argument('--seeds', default='5000-5007')
    ap.add_argument('--cap', type=int, default=3000)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--half-min', type=int, default=3)
    a = ap.parse_args()

    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi)+1)) if hi else [int(lo)]
    with mp.Pool(a.jobs) as pool:
        out = pool.map(run_one, [(a.entries, a.hpl, a.stack, s, a.cap) for s in seeds])

    rows, AX = [], {}
    errs = 0
    for si, (rec, axv, e) in enumerate(out):
        errs += e
        for r in rec:
            r = dict(r); r['key'] = (si, r['pid']); rows.append(r)
        for pid, v in axv.items(): AX[(si, pid)] = v

    print('# 프리플랍·응답층 f 계측   entries=%d hpl=%d 시드 %d개  기준 >=%d'
          % (a.entries, a.hpl, len(seeds), a.half_min))
    print('플레이어 %d명   관측 %d건   오류 %d건' % (len(AX), len(rows), errs))
    print()
    mc = collections.Counter(r['metric'] for r in rows)
    print('지표별 총 관측:', dict(mc.most_common()))
    print()
    # --- 복제 검증 관문 ---
    vr = [r for r in rows if r.get('verify') is not None]
    bad = [r for r in vr if r['verify'] is False]
    fired = [r for r in rows if r.get('fired') is True]
    nonf = [r for r in rows if r.get('fired') is False]
    print('## need_true 복제 검증')
    print('  비발동군(_sz_seen == _sz_true) %d건 중 불일치 **%d건** (상대오차 1e-12 기준)'
          % (len(vr), len(bad)))
    print('  발동군(인지 사이즈 != 실제) %d건 — 이쪽은 교차검증 수단이 없다 (%.1f%%)'
          % (len(fired), 100.0*len(fired)/max(1, len(fired)+len(nonf))))
    if bad:
        print()
        print('  ** 불일치가 있다. 결과를 해석하지 않는다 — 도구를 먼저 고친다. **')
        for r in bad[:3]:
            print('     need_true=%r  tocall=%r p0=%r bf=%r' %
                  (r['need_true'], r['tocall'], r['p0'], r['bf']))
        return
    print()
    rr = [r['v'] for r in rows if r['metric'].startswith('ratio_') and r.get('v')]
    if rr:
        rs = sorted(rr)
        g = lambda f: rs[min(len(rs)-1, int(f*len(rs)))]
        print('## need_ratio 분포 (코드 클램프는 0.55 ~ 1.75+0.05/need_true)')
        print('  중앙 %.3f   5%% %.3f   25%% %.3f   75%% %.3f   95%% %.3f   최소 %.3f 최대 %.3f'
              % (stat.median(rs), g(0.05), g(0.25), g(0.75), g(0.95), rs[0], rs[-1]))
        print()

    hdr = '%-18s %-18s %5s %7s %8s %8s %8s | %7s %6s'
    print(hdr % ('지표', '축', '기대', '총관측', 'f중앙', 'ρ(전원)', 'n', 'split r', 'n'))
    print('-'*100)
    for metric, pairs in METRICS.items():
        sel = [r for r in rows if r['metric'] == metric and r.get('v') is not None]
        if not sel:
            print(hdr % (metric, '(관측 0)', '', 0, '-', '-', '-', '-', '-'))
            continue
        per = collections.defaultdict(list)
        for r in sel: per[r['key']].append(r['v'])
        med = stat.median([r['v'] for r in sel])
        ks = [k for k in per if per[k]]
        hk = [k for k in ks if len(per[k]) >= a.half_min]
        fmt = lambda v: ('%+.3f' % v) if v is not None else '  -  '
        for ax, sgn in pairs:
            xs = [AX[k].get(ax) for k in ks]
            if any(x is None for x in xs):
                print(hdr % (metric, ax, '%+d' % sgn, len(sel), '%.3f' % med,
                             '(축 없음)', '-', '-', '-'))
                continue
            rho = spearman(xs, [stat.mean(per[k]) for k in ks])
            if len(hk) >= 4:
                h1 = [stat.mean(per[k][0::2]) for k in hk]
                h2 = [stat.mean(per[k][1::2]) for k in hk]
                rh = spearman(h1, h2)
            else:
                rh = None
            print(hdr % (metric, ax, '%+d' % sgn, len(sel), '%.3f' % med,
                         fmt(rho), len(ks), fmt(rh), len(hk)))
    print()
    print('기대 : f 가 축과 같은 방향이면 +1. need 는 낮을수록 잘 콜하므로')
    print('       "잘 콜하는" 축은 -1 이다. 부호를 기대와 맞춰 읽을 것.')
    print('n < 20 인 ρ 는 부호가 뒤집힐 수 있다.')


if __name__ == '__main__':
    main()
