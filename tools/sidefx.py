"""리버 수정의 부작용 점검 — 핸드 결과 수준의 광역 지표.

    python3 tools/sidefx.py

계획 층을 건드리면 팟 크기 / 쇼다운 빈도 / 탈락 속도가 같이 움직일 수 있다.
같은 시드로 수정 전후를 돌려 비교하는 것이 목적이라 판정하지 않고 숫자만 낸다.
"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import tourney as T

SEEDS = (7001, 7002, 7003, 7004, 7005, 7006)
HANDS = 50


def main():
    c = collections.Counter()
    pots = []
    for sd in SEEDS:
        t = T.Tournament(entries=60, seed=sd, fmt='standard', hero_seat=7)
        alive0 = sum(1 for s in t.seats if t.stacks[s] > 0)
        for _ in range(HANDS):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            g = 0
            while st and not st.get('done') and g < 250:
                st = t.submit('fold')
                g += 1
            c['hands'] += 1
            h = getattr(t.run, 'h', None)
            res = getattr(t.run, 'result', None) or {}
            if res.get('pot'):
                pots.append(float(res['pot']))
            if res.get('showdown'):
                c['showdown'] += 1
            log = getattr(t.run, 'full_log', []) or []
            streets = set(x[0] for x in log)
            for s in ('flop', 'turn', 'river'):
                if s in streets:
                    c['saw_' + s] += 1
            if any(x[0] == 'river' and x[2] in ('bet', 'raise', 'allin') for x in log):
                c['river_bet_hand'] += 1
            if any(x[2] == 'allin' for x in log):
                c['allin_hand'] += 1
        c['busted'] += alive0 - sum(1 for s in t.seats if t.stacks[s] > 0)
    n = max(1, c['hands'])
    print('핸드 %d' % c['hands'])
    print('  쇼다운 도달      %5.1f%%' % (100.0 * c['showdown'] / n))
    print('  플랍 도달        %5.1f%%' % (100.0 * c['saw_flop'] / n))
    print('  턴 도달          %5.1f%%' % (100.0 * c['saw_turn'] / n))
    print('  리버 도달        %5.1f%%' % (100.0 * c['saw_river'] / n))
    print('  리버 벳 있는 핸드 %5.1f%%' % (100.0 * c['river_bet_hand'] / n))
    print('  올인 있는 핸드   %5.1f%%' % (100.0 * c['allin_hand'] / n))
    print('  평균 팟          %8.0f' % (sum(pots) / max(1, len(pots))))
    print('  탈락 인원        %d' % c['busted'])


if __name__ == '__main__':
    main()
