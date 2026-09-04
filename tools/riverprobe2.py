"""리버 밸류 라인 계측 — value_2street 의 리버 사이즈 수정 전후 비교용.

    python3 tools/riverprobe2.py

같은 시드로 두 번 돌려 비교하는 것이 목적이므로 판정하지 않고 숫자만 낸다.
"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import tourney as T

SEEDS = (7001, 7002, 7003, 7004, 7005, 7006)
HANDS = 50


def main():
    c = collections.Counter()
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
            for i in (getattr(h, 'intents', None) or []):
                street = i.get('street')
                if street not in ('flop', 'turn', 'river'):
                    continue
                c['n_' + street] += 1
                if i['action'] in ('bet', 'raise'):
                    c['aggr_' + street] += 1
                if street != 'river':
                    continue
                p = i['plan']
                c['plan_' + p] += 1
                if p == 'value_2street':
                    c['v2_' + i['action']] += 1
                    if i.get('rel', 0) >= 0.92:
                        c['v2_rel92_' + i['action']] += 1
    for s in ('flop', 'turn', 'river'):
        n = c['n_' + s]
        if n:
            print('%-6s n=%-4d 공격률 %.1f%%' % (s, n, 100.0 * c['aggr_' + s] / n))
    print()
    for k in sorted(c):
        if k.startswith(('plan_', 'v2_')):
            print('  %-24s %d' % (k, c[k]))


if __name__ == '__main__':
    main()
