#!/usr/bin/env python3
"""④ 파일럿 — fieldsim 으로 플레이어당 관측 표본이 얼마나 나오는지 잰다.

  python3 tools/player_pilot.py --entries 100 --hpl 12 --stack 30000 --seed 5000

**측정이 아니라 정찰이다.** 여기서 재는 것은 행동 지표가 아니라
지표를 잴 수 있는 **기회 수**다. OBS_AXIS_PLAN.md 5절이 요구하는 다섯 가지:

  1. 플레이어당 관측 핸드 수 분포
  2. 지표별 기회 수 (핸드 수가 아니라 이게 실제 표본이다)
  3. hands_per_level 이 토너 종료 시점을 제어하는가
  4. opp_est 누적 여부 (reads.Book 이 fieldsim 에서 핸드마다 초기화된다)
  5. 축-축 상관행렬

읽기 전용이다. plan.py 도 fieldsim.py 도 수정하지 않는다 —
_log_bot_hand 를 인스턴스에서 가로채 핸드를 메모리로 받고,
reads.perceived_profile 을 감싸 관측 수 n 을 센다.
"""
import os, sys, json, argparse, statistics as stat, collections, itertools, math

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)

import fieldsim as FS
import reads as RD

# ---------- 계측 ----------
EST_N = []          # 판단 시점의 opp_est['n'] (관측 누적량)

_orig_pp = RD.perceived_profile
def _pp(book, observer, target, observer_type, rng=None):
    r = _orig_pp(book, observer, target, observer_type, rng)
    if r is not None:
        EST_N.append((r.get('n') or 0, r.get('confidence') or 0.0))
    return r
RD.perceived_profile = _pp


def run(entries, hpl, stack, seed, cap):
    f = FS.Field(entries=entries, start_stack=stack, hero_pid=0, seed=seed,
                 hands_per_level=hpl)
    FS.Field.BOT_LOG = 0            # 파일로 안 쓴다. 아래에서 가로챈다.
    hands = []

    def grab(tb, h, run_):
        res = getattr(run_, 'result', None) or {}
        hands.append({
            'hand_no': f.hand_no, 'level': f.level, 'table': tb.id,
            'pids': dict(getattr(h, 'seat_pid', {})),
            'full_log': list(res.get('full_log') or []),
            'intents': list(getattr(h, 'intents', []) or []),
            'board': res.get('board'),
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
    return f, hands


# ---------- 기회 세기 ----------
STREETS = ('flop', 'turn', 'river')

def opportunities(hands):
    """pid → 지표별 기회/사건 수.

    분모는 핸드가 아니라 기회다 (OBS_AXIS_PLAN 2절 1번).
    블라인드는 rnd.apply 를 거치지 않아 로그에 없다 (session.py:117-127) —
    그래서 프리플랍 로그는 전부 자발 액션이다.
    """
    C = collections.defaultdict(collections.Counter)
    for rec in hands:
        pid = {int(k): v for k, v in rec['pids'].items()}
        log = rec['full_log']
        for s in set(pid):
            C[pid[s]]['hands'] += 1

        pre = [r for r in log if r[0] == 'preflop']
        # --- 프리플랍 ---
        raised = False
        for (_, s, a, _amt) in pre:
            p = pid.get(s)
            if p is None: continue
            C[p]['pf_opp'] += 1
            if raised:
                C[p]['pf_vs_raise'] += 1
                if a in ('raise', 'allin'): C[p]['pf_3bet'] += 1
            if a in ('call', 'raise', 'allin'): C[p]['vpip'] += 1
            if a in ('raise', 'allin'):
                C[p]['pfr'] += 1
                raised = True

        # 프리플랍 마지막 공격자 = 이니셔티브
        aggr = None
        for (_, s, a, _amt) in pre:
            if a in ('raise', 'allin'): aggr = s

        # --- 포스트플랍: 이니셔티브 보유자의 첫 액션 기회 ---
        for stt in STREETS:
            rows = [r for r in log if r[0] == stt]
            if not rows: continue
            seats_here = [r[1] for r in rows]
            # 이니셔티브 보유자가 이 스트리트에 액션했고, 그 앞에 벳이 없었는가
            if aggr is not None and aggr in seats_here:
                i = seats_here.index(aggr)
                before = [rows[k][2] for k in range(i)]
                if not any(a in ('bet', 'raise', 'allin') for a in before):
                    p = pid.get(aggr)
                    if p:
                        C[p]['%s_cbet_opp' % stt] += 1
                        if rows[i][2] in ('bet', 'allin'):
                            C[p]['%s_cbet' % stt] += 1
                            aggr = aggr        # 유지
                        else:
                            aggr = None        # 체크 → 이니셔티브 포기
                else:
                    aggr = None
            else:
                aggr = None
            # --- 벳 직면 (응답 축 분모) ---
            live_bet = False
            for (_, s, a, _amt) in rows:
                p = pid.get(s)
                if p and live_bet:
                    C[p]['%s_vs_bet' % stt] += 1
                    if a in ('call',):  C[p]['%s_call' % stt] += 1
                    if a in ('raise', 'allin'): C[p]['%s_raise' % stt] += 1
                    if a == 'fold':     C[p]['%s_fold' % stt] += 1
                if a in ('bet', 'raise', 'allin'): live_bet = True

        # --- 계획/이탈 (실행 축) ---
        for it in rec['intents']:
            p = pid.get(it.get('seat'))
            if not p: continue
            if it.get('action') is None: continue
            C[p]['plan_actions'] += 1
            if it.get('dev'): C[p]['deviations'] += 1
    return C


def dist(vals, name, unit='명'):
    if not vals:
        print('  %-22s  (없음)' % name); return
    v = sorted(vals)
    q = lambda f: v[min(len(v)-1, int(f*len(v)))]
    print('  %-22s  중앙 %6.1f   25%% %6.1f   75%% %6.1f   최대 %6.1f' % (
        name, stat.median(v), q(0.25), q(0.75), v[-1]))


def spearman(a, b):
    n = len(a)
    if n < 3: return 0.0
    def rank(x):
        o = sorted(range(n), key=lambda i: x[i])
        r = [0.0]*n
        i = 0
        while i < n:
            j = i
            while j+1 < n and x[o[j+1]] == x[o[i]]: j += 1
            avg = (i+j)/2.0 + 1
            for k in range(i, j+1): r[o[k]] = avg
            i = j+1
        return r
    ra, rb = rank(a), rank(b)
    ma, mb = sum(ra)/n, sum(rb)/n
    num = sum((ra[i]-ma)*(rb[i]-mb) for i in range(n))
    da = math.sqrt(sum((x-ma)**2 for x in ra))
    db = math.sqrt(sum((x-mb)**2 for x in rb))
    return num/(da*db) if da and db else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--hpl', type=int, default=12)
    ap.add_argument('--stack', type=int, default=30000)
    ap.add_argument('--seed', type=int, default=5000)
    ap.add_argument('--cap', type=int, default=2000)
    a = ap.parse_args()

    import time
    t0 = time.time()
    f, hands = run(a.entries, a.hpl, a.stack, a.seed, a.cap)
    dt = time.time()-t0

    print('# ④ 파일럿  entries=%d  hpl=%d  stack=%d  seed=%d' % (
        a.entries, a.hpl, a.stack, a.seed))
    print()
    print('토너 종료  핸드 %d  레벨 %d  생존 %d  (%.0fs)' % (
        f.hand_no, f.level, f.remaining(), dt))
    print('테이블-핸드 기록 %d건   엔진 오류 %d건' % (len(hands), len(f.errors)))
    if f.errors:
        for e in f.errors[:3]: print('   ⚠', e)
    print()

    C = opportunities(hands)
    print('플레이어 %d명 (엔트리 %d)' % (len(C), a.entries))
    print()
    print('## 1. 플레이어당 관측 핸드 수')
    dist([c['hands'] for c in C.values()], '핸드')
    print()
    print('## 2. 지표별 기회 수 (플레이어당)')
    for key, name in [
        ('pf_opp',        'VPIP/PFR 분모'),
        ('pf_vs_raise',   '3bet 분모'),
        ('flop_cbet_opp', '플랍 c-bet 분모'),
        ('turn_cbet_opp', '턴 배럴 분모'),
        ('river_cbet_opp','리버 배럴 분모'),
        ('flop_vs_bet',   '플랍 벳 직면'),
        ('turn_vs_bet',   '턴 벳 직면'),
        ('river_vs_bet',  '리버 벳 직면'),
        ('plan_actions',  '계획 있는 액션'),
    ]:
        dist([c[key] for c in C.values()], name)
    print()
    print('   총합:', {k: sum(c[k] for c in C.values()) for k in
                      ('pf_opp','flop_cbet_opp','turn_cbet_opp','river_cbet_opp',
                       'plan_actions','deviations')})
    print()
    print('## 3. opp_est 누적 (reads.Book)')
    if EST_N:
        ns = [n for n, _ in EST_N]
        cf = [c for _, c in EST_N]
        print('  perceived_profile 호출 %d회' % len(ns))
        print('  관측 수 n   중앙 %.1f  평균 %.2f  최대 %d   n==0 비율 %.1f%%' % (
            stat.median(ns), sum(ns)/len(ns), max(ns), 100*sum(1 for x in ns if x == 0)/len(ns)))
        print('  confidence  중앙 %.3f  최대 %.3f' % (stat.median(cf), max(cf)))
    else:
        print('  호출 없음')
    print()
    print('## 4. 축-축 상관 (|rho| >= 0.20 만)')
    profs = [p['prof'] for p in f.players.values()]
    axes = {}
    for k in sorted(profs[0]['concepts']): axes['c:'+k] = [p['concepts'][k] for p in profs]
    for k in sorted(profs[0]['temper']):   axes['t:'+k] = [p['temper'][k]   for p in profs]
    hits = []
    for x, y in itertools.combinations(sorted(axes), 2):
        r = spearman(axes[x], axes[y])
        if abs(r) >= 0.20: hits.append((abs(r), x, y, r))
    hits.sort(reverse=True)
    if not hits:
        print('  없음 — 축이 서로 독립적으로 생성된다')
    for _, x, y, r in hits[:15]:
        print('  %-24s %-24s  rho %+0.3f' % (x, y, r))


if __name__ == '__main__':
    main()
