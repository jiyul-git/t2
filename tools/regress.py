"""리팩터 안전망.

같은 시드로 토너를 돌려 모든 액션을 이어붙인 뒤 SHA-256 지문을 낸다.
리팩터가 동작을 바꾸지 않았다면 지문이 완전히 같아야 한다.

  python3 tools/regress.py save    # 기준선 저장
  python3 tools/regress.py check   # 기준선과 대조
"""
import sys, os, json, hashlib, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import tourney as T

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'baseline_9max.json')
SEEDS = list(range(3000, 3006))
HANDS = 30


def fingerprint():
    per_seed, stats = {}, collections.Counter()
    for sd in SEEDS:
        t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                         seed=sd, hands_per_level=200)
        rows = ['q=%.3f|a=%.2f' % (t.field_q, t.aggr_bias)]
        for _ in range(HANDS):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            guard = 0
            while st and not st.get('done') and guard < 200:
                st = t.submit('fold')
                guard += 1
            log = getattr(t.run, 'full_log', []) or []
            rows.append(';'.join('%s:%s:%s:%s' % x for x in log))
            seen = set()
            for (stt, x, a, _) in log:
                if stt != 'preflop' or x == t.hero or x in seen:
                    continue
                seen.add(x)
                stats['n'] += 1
                if a in ('bet', 'raise', 'allin'):
                    stats['vpip'] += 1
                    stats['pfr'] += 1
                elif a == 'call':
                    stats['vpip'] += 1
            stats['hands'] += 1
            if any(s == 'flop' for (s, _, _, _) in log):
                stats['flop'] += 1
            t.finish_hand()
        per_seed[sd] = hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:16]
    return per_seed, dict(stats)


def summarize(stats):
    n = max(1, stats.get('n', 0))
    h = max(1, stats.get('hands', 0))
    return ('VPIP %.1f%%  PFR %.1f%%  flop %.1f%%'
            % (100*stats.get('vpip', 0)/n, 100*stats.get('pfr', 0)/n,
               100*stats.get('flop', 0)/h))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    fp, stats = fingerprint()
    if cmd == 'save':
        json.dump({'fp': fp, 'stats': stats}, open(BASE, 'w'), indent=1)
        print('기준선 저장:', BASE)
        print(summarize(stats))
        return 0
    if not os.path.exists(BASE):
        print('기준선 없음. 먼저 save 를 실행하세요.')
        return 2
    old = json.load(open(BASE))
    bad = [s for s in fp if old['fp'].get(str(s)) != fp[s]]
    print('기준선 :', summarize(old['stats']))
    print('현재   :', summarize(stats))
    if bad:
        print('불일치 시드: %s  → 동작이 바뀌었습니다.' % bad)
        return 1
    print('전 시드 지문 일치 — 동작 보존 확인.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
