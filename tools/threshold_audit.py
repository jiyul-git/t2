"""추정 belief 의 분포와, 그 값에 걸린 절대 문턱을 함께 점검한다.

    python3 tools/threshold_audit.py

배경: bluff_mode 의 merged/polarized 가 실전에서 0건이었다. 원인은
`sizing_tell >= 5.5` 라는 절대 문턱인데, 추정값은 표본이 적으면 중립(5.0)
쪽으로 **수축하도록 설계**돼 있어 5.5 를 넘는 경우가 11% 뿐이었다.

  추정 시스템: "확신 없으면 중간값"
  소비 측:     그 중간값을 "능력이 없는 상대"로 해석

같은 패턴이 다른 곳에도 있는지 본다. 실제 개념값에 거는 문턱은 괜찮을 수
있지만, **수축되는 추정값**에 거는 절대 문턱은 설계가 따로 필요하다.

① 추정값 분포 — concept 별 mean/median/sd 와 5.0/5.5/6.0 초과 비율
② 소비 측 절대 문턱 — 코드에서 개념 비교를 찾아 대상이 실제값인지 추정값인지 분류
"""
import sys, os, re, math, random, statistics, collections

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import tourney as T   # noqa: E402

SEEDS = (19001, 19002, 19003)
HANDS = 40


def stage_distribution():
    print('① 추정 belief 분포 (opp_est 로 실제 전달되는 값)')
    vals = collections.defaultdict(list)
    for sd in SEEDS:
        t = T.Tournament(entries=60, seed=sd, fmt='standard', hero_seat=7)
        for _ in range(HANDS):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            g = 0
            while st and not st.get('done') and g < 250:
                st = t.submit('fold')
                g += 1
            h = getattr(t.run, 'h', None)
            for _k, v in (getattr(h, 'plans', {}) or {}).items():
                oe = v.get('opp_est')
                if not isinstance(oe, dict):
                    continue
                for kk in ('sizing_tell', 'range_read'):
                    if oe.get(kk) is not None:
                        vals[kk].append(float(oe[kk]))
                ec = oe.get('est_concepts')
                if isinstance(ec, dict):
                    for kk, vv in ec.items():
                        if vv is not None:
                            vals['est:' + kk].append(float(vv))
    print('   %-22s %6s %6s %6s %7s %7s %7s'
          % ('값', 'n', 'mean', 'sd', '>5.0', '>5.5', '>6.0'))
    for kk in sorted(vals):
        a = vals[kk]
        if len(a) < 20:
            continue
        n = len(a)
        print('   %-22s %6d %6.2f %6.2f %6.0f%% %6.0f%% %6.0f%%'
              % (kk, n, statistics.mean(a),
                 statistics.pstdev(a) if n > 1 else 0.0,
                 100.0*sum(1 for x in a if x > 5.0)/n,
                 100.0*sum(1 for x in a if x > 5.5)/n,
                 100.0*sum(1 for x in a if x > 6.0)/n))
    print()
    return vals


CONCEPTS = ('bluff', 'semibluff', 'cbet_flop', 'barrel_turn', 'barrel_river',
            'checkraise_flop', 'checkraise_late', 'bluffcatch_early',
            'bluffcatch_river', 'thin_value_turn', 'thin_value_river',
            'blockbet', 'potcontrol', 'trap', 'overbet', 'probe',
            'delayed_cbet', 'equity_denial', 'stackoff', 'reraise', 'outs',
            'potodds', 'spr', 'range_read', 'blocker', 'icm', 'board_texture',
            'sizing_tell', 'pf_range', 'positional', 'stack_decay',
            'open_size', 'pf_defend', 'range_merge', 'multiway', 'fold_equity')

_CMP = re.compile(r"([A-Za-z_]*(?:%s))[^\n]{0,40}?([<>]=?)\s*([0-9.]+)"
                  % '|'.join(CONCEPTS))


def stage_thresholds():
    print('② 개념에 걸린 절대 문턱')
    print('   대상이 **추정값(opp_est/belief)**이면 수축을 고려해야 한다.')
    hits = []
    for fn in ('plan.py', 'preflop.py', 'reads.py', 'session.py'):
        p = os.path.join(_ROOT, fn)
        if not os.path.exists(p):
            continue
        for i, line in enumerate(open(p), 1):
            s = line.strip()
            if s.startswith('#') or not s:
                continue
            m = _CMP.search(s)
            if not m:
                continue
            # 추정값 대상인지 실제값 대상인지 구분
            est = any(t in s for t in ('opp_est', 'oe[', 'oe.get', 'est[',
                                       'belief', 'perceived', '_ec', 'rd['))
            hits.append((fn, i, 'EST' if est else 'REAL', s[:88]))
    for fn, i, kind, s in hits:
        if kind == 'EST':
            print('   [추정값] %s:%d  %s' % (fn, i, s))
    n_est = sum(1 for h in hits if h[2] == 'EST')
    print('   추정값 문턱 %d건 / 전체 개념 비교 %d건' % (n_est, len(hits)))


def main():
    stage_distribution()
    stage_thresholds()


if __name__ == '__main__':
    main()
