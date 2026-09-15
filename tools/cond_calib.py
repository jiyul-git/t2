#!/usr/bin/env python3
"""④ 측정조건 calibration — hpl / entries 를 흔들었을 때 무엇이 같이 변하는가.

  python3 tools/cond_calib.py --seeds 5000-5003 --grid 24x12,24x40,48x40 --jobs 4

**목표는 최대 표본이 아니라 교란이 최소인 측정조건 결정이다.**

'플랍 도달률 몇 %' 하나만 보지 않는다. 손잡이를 돌릴 때 같이 움직이는 것을
전부 같이 싣는다:

  필드 구성      field_q, 잠재요인(study/aggro/exp) 평균·sd, 주요 축 평균·sd
  스택 깊이      관측 시점 유효 스택(bb) 중앙 — 포스트플랍 성격을 정하는 값
  블라인드       종료 레벨, 관측 핸드의 레벨 분포
  생존 시간      플레이어당 관측 핸드
  기회율         스트리트별 도달률, 플레이어당 지표 기회 수

start_stack 은 고정한다. 표본량 손잡이가 아니라 전략 환경 자체라서다.

읽기 전용. fieldsim.py 도 plan.py 도 수정하지 않는다.
"""
import os, sys, json, argparse, statistics as stat, collections, math
import multiprocessing as mp

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)


def one(args):
    entries, hpl, stack, seed, cap = args
    import fieldsim as FS
    import field as FLD
    FS.Field.BOT_LOG = 0
    f = FS.Field(entries=entries, start_stack=stack, hero_pid=0, seed=seed,
                 hands_per_level=hpl)
    rows = []

    def grab(tb, h, run_):
        res = getattr(run_, 'result', None) or {}
        st0 = dict(getattr(h, '_start_stacks', {}) or {})
        rows.append({
            'level': f.level, 'bb': h.bb,
            'pids': dict(getattr(h, 'seat_pid', {})),
            'stacks0': st0,
            'log': list(res.get('full_log') or []),
        })
    f._log_bot_hand = grab

    while f.remaining() > 1 and f.hand_no < cap:
        f.hand_no += 1
        f.advance_level()
        for tid, tb in list(f.tables.items()):
            if tb.n() >= 2:
                f._play_table(tb)
        f._collect_busts()
        f._balance()
        f.notes = []

    # ---- 필드 구성 ----
    profs = [p['prof'] for p in f.players.values()]
    lat = {k: [p['latent'][k] for p in profs] for k in ('study', 'aggro', 'exp')}
    AX = ('cbet_flop', 'barrel_turn', 'barrel_river', 'bluff', 'reraise',
          'potcontrol', 'thin_value_turn')
    axd = {k: [p['concepts'][k] for p in profs] for k in AX}
    axd['aggression'] = [p['temper']['aggression'] for p in profs]
    axd['looseness'] = [p['temper']['looseness'] for p in profs]
    axd['discipline'] = [p['temper']['discipline'] for p in profs]

    # ---- 스택 깊이 / 레벨 ----
    depth, lvls = [], []
    for r in rows:
        v = [x/r['bb'] for x in r['stacks0'].values() if x > 0]
        if v: depth.append(stat.median(v))
        lvls.append(r['level'])

    # ---- 도달률 / 기회 ----
    C = collections.defaultdict(collections.Counter)
    reach = collections.Counter()
    for r in rows:
        pid = {int(k): v for k, v in r['pids'].items()}
        log = r['log']
        seen = set(x[0] for x in log)
        for k in ('flop', 'turn', 'river'):
            if k in seen: reach[k] += 1
        for s in set(pid): C[pid[s]]['hands'] += 1
        pre = [x for x in log if x[0] == 'preflop']
        raised = False
        for (_, s, a, _amt) in pre:
            p = pid.get(s)
            if p is None: continue
            C[p]['pf_opp'] += 1
            if raised: C[p]['pf_vs_raise'] += 1
            if a in ('raise', 'allin'): raised = True
        aggr = None
        for (_, s, a, _amt) in pre:
            if a in ('raise', 'allin'): aggr = s
        for stt in ('flop', 'turn', 'river'):
            rr = [x for x in log if x[0] == stt]
            if not rr: continue
            seats = [x[1] for x in rr]
            if aggr is not None and aggr in seats:
                i = seats.index(aggr)
                if not any(x in ('bet', 'raise', 'allin') for x in [rr[k][2] for k in range(i)]):
                    p = pid.get(aggr)
                    if p: C[p]['%s_cbet_opp' % stt] += 1
                    if rr[i][2] not in ('bet', 'allin'): aggr = None
                else:
                    aggr = None
            else:
                aggr = None
            live = False
            for (_, s, a, _amt) in rr:
                p = pid.get(s)
                if p and live: C[p]['%s_vs_bet' % stt] += 1
                if a in ('bet', 'raise', 'allin'): live = True

    def med(key): return stat.median([c[key] for c in C.values()]) if C else 0.0
    n = max(1, len(rows))
    return {
        'entries': entries, 'hpl': hpl, 'seed': seed,
        'hands': f.hand_no, 'end_level': f.level, 'table_hands': len(rows),
        'errors': len(f.errors),
        'field_q': round(f.field_q, 3),
        'lat': {k: (round(stat.mean(v), 2), round(stat.pstdev(v), 2)) for k, v in lat.items()},
        'ax': {k: (round(stat.mean(v), 2), round(stat.pstdev(v), 2)) for k, v in axd.items()},
        'depth_med': round(stat.median(depth), 1) if depth else 0.0,
        'depth_q25': round(sorted(depth)[len(depth)//4], 1) if depth else 0.0,
        'depth_q75': round(sorted(depth)[3*len(depth)//4], 1) if depth else 0.0,
        'lvl_med': stat.median(lvls) if lvls else 0,
        'reach': {k: round(100*reach[k]/n, 1) for k in ('flop', 'turn', 'river')},
        'players': len(C),
        'p_hands': med('hands'),
        'p_pf': med('pf_opp'),
        'p_flop': med('flop_cbet_opp'),
        'p_turn': med('turn_cbet_opp'),
        'p_river': med('river_cbet_opp'),
        'p_vsbet': med('flop_vs_bet') + med('turn_vs_bet') + med('river_vs_bet'),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='5000-5002')
    ap.add_argument('--grid', default='24x12,24x40,48x40')
    ap.add_argument('--stack', type=int, default=30000)
    ap.add_argument('--cap', type=int, default=3000)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()

    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi)+1)) if hi else [int(lo)]
    grid = []
    for g in a.grid.split(','):
        e, h = g.lower().split('x'); grid.append((int(e), int(h)))

    jobs = [(e, h, a.stack, s, a.cap) for (e, h) in grid for s in seeds]
    print('# 측정조건 calibration  stack=%d 고정  조합 %d × 시드 %d = %d회'
          % (a.stack, len(grid), len(seeds), len(jobs)), flush=True)

    with mp.Pool(a.jobs) as pool:
        res = pool.map(one, jobs)

    if a.out:
        json.dump(res, open(a.out, 'w'))

    by = collections.defaultdict(list)
    for r in res: by[(r['entries'], r['hpl'])].append(r)

    def agg(rs, f): return stat.mean([f(r) for r in rs])

    print()
    print('## 진행·표본')
    print('%-9s %7s %7s %8s %8s | %7s %7s %7s %7s %7s' % (
        '조건', '핸드', '종료Lv', '테이블핸드', '플레이어',
        '인당핸드', 'PF기회', '플랍', '턴', '리버'))
    for k in sorted(by):
        rs = by[k]
        print('%-9s %7.0f %7.1f %8.0f %8.0f | %7.1f %7.1f %7.1f %7.1f %7.1f' % (
            '%dx%d' % k, agg(rs, lambda r: r['hands']), agg(rs, lambda r: r['end_level']),
            agg(rs, lambda r: r['table_hands']), agg(rs, lambda r: r['players']),
            agg(rs, lambda r: r['p_hands']), agg(rs, lambda r: r['p_pf']),
            agg(rs, lambda r: r['p_flop']), agg(rs, lambda r: r['p_turn']),
            agg(rs, lambda r: r['p_river'])))

    print()
    print('## 전략 환경 (교란)')
    print('%-9s %8s %8s %8s %8s | %7s %7s %7s' % (
        '조건', '유효bb', 'bb25%', 'bb75%', '중앙Lv', '플랍%', '턴%', '리버%'))
    for k in sorted(by):
        rs = by[k]
        print('%-9s %8.1f %8.1f %8.1f %8.1f | %7.1f %7.1f %7.1f' % (
            '%dx%d' % k, agg(rs, lambda r: r['depth_med']),
            agg(rs, lambda r: r['depth_q25']), agg(rs, lambda r: r['depth_q75']),
            agg(rs, lambda r: r['lvl_med']),
            agg(rs, lambda r: r['reach']['flop']), agg(rs, lambda r: r['reach']['turn']),
            agg(rs, lambda r: r['reach']['river'])))

    print()
    print('## 필드 구성 (교란) — field_q 와 잠재요인')
    print('%-9s %8s | %-13s %-13s %-13s' % ('조건', 'field_q', 'study', 'aggro', 'exp'))
    for k in sorted(by):
        rs = by[k]
        c = lambda n: (agg(rs, lambda r: r['lat'][n][0]), agg(rs, lambda r: r['lat'][n][1]))
        print('%-9s %8.3f | %6.2f±%-6.2f %6.2f±%-6.2f %6.2f±%-6.2f' % (
            '%dx%d' % k, agg(rs, lambda r: r['field_q']), *c('study'), *c('aggro'), *c('exp')))

    print()
    print('## 성격 축 분포 (교란) — 평균±sd')
    names = sorted(res[0]['ax'])
    for nm in names:
        line = '  %-16s' % nm
        for k in sorted(by):
            rs = by[k]
            line += '  %dx%d %4.2f±%-4.2f' % (k[0], k[1],
                    agg(rs, lambda r: r['ax'][nm][0]), agg(rs, lambda r: r['ax'][nm][1]))
        print(line)


if __name__ == '__main__':
    main()
