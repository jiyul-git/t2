#!/usr/bin/env python3
"""최종 has_sd 블록 giveup 중 의심 48건의 개선 유형을 태깅한다.

plan.py 는 수정하지 않는다. 홀카드 + 그 스트리트의 보드로
실제 드로우 구조를 판정할 뿐이다.
"""
import os, sys, json, collections
from itertools import combinations

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
import bot

R = bot.RANKS          # '23456789TJQKA'
RV = {c: i for i, c in enumerate(R)}   # 2->0 ... A->12


def W(i):
    return i['why'] if isinstance(i['why'], list) else [i['why']]


def this_street(i, frag):
    pre = '%s: ' % i['street']
    return any(x.startswith(pre) and frag in x for x in W(i))


def board_at(board, street):
    n = {'flop': 3, 'turn': 4, 'river': 5}[street]
    return list(board)[:n]


def straight_span(ranks):
    """주어진 랭크 집합에서 5장 윈도 안에 몇 장이 들어있는지 최대값.
       A를 1로도 세어 휠을 잡는다."""
    s = set(ranks)
    if RV['A'] in s:
        s = s | {-1}
    best = 0
    for lo in range(-1, 9):
        win = set(range(lo, lo + 5))
        best = max(best, len(s & win))
    return best


def tag(hole, board):
    """개선 유형 태그 집합을 낸다."""
    tags = []
    cards = hole + board
    suits = [c[1] for c in cards]
    hs = [c[1] for c in hole]
    sc = collections.Counter(suits)
    top_suit, top_n = sc.most_common(1)[0]
    # 내 홀카드가 그 수트에 기여하는지 (보드만의 수트는 내 드로우가 아니다)
    mine_in = sum(1 for x in hs if x == top_suit)

    if top_n >= 4 and mine_in >= 1:
        tags.append('플러시드로우')
    elif top_n == 3 and mine_in >= 1:
        tags.append('백도어플러시')

    rk = [RV[c[0]] for c in cards]
    span = straight_span(rk)
    hole_r = [RV[c[0]] for c in hole]
    board_r = [RV[c[0]] for c in board]
    # 홀카드가 그 스트레이트 구조에 기여하는지 확인: 보드만으로 센 값과 비교
    span_board = straight_span(board_r)
    if span >= 4 and span > span_board:
        # 오픈엔드/검샷 구분: 4장 윈도가 연속인지
        s = set(rk)
        oesd = False
        for lo in range(-1, 10):
            if all((lo + k) in s or (lo + k) == -1 and RV['A'] in s
                   for k in range(4)):
                # 양쪽이 열려 있는지
                if 0 <= lo and lo + 4 <= 12:
                    oesd = True
        tags.append('오픈엔드' if oesd else '검샷')
    elif span == 3 and span > span_board:
        tags.append('백도어스트레이트')

    # 오버카드: 홀카드가 보드 최고 랭크보다 높고 페어를 안 이룸
    if board_r:
        hi = max(board_r)
        ov = sum(1 for x in hole_r if x > hi)
        paired = any(x in board_r for x in hole_r)
        if ov >= 1 and not paired:
            tags.append('오버카드%d' % ov)

    if not tags:
        tags.append('실질 드로우 없음')
    return tags


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(D, 'collected.jsonl')
    rows = []
    for l in open(path):
        r = json.loads(l)
        for i in r.get('intents', []):
            if i.get('eq_current') is None:
                continue
            if not this_street(i, '쇼다운 가치 없고'):
                continue
            hole = r['hole'].get(str(i['seat']))
            if not hole:
                continue
            bd = board_at(r['board'], i['street'])
            if len(bd) < 3:
                continue
            i['_h'] = r['hand_no']; i['_hole'] = hole; i['_bd'] = bd
            rows.append(i)

    def grp(i):
        a = i['outs'] >= 4
        b = i['eq_delta'] >= 0.20
        return 'A∩B' if (a and b) else ('A only' if a else ('B only' if b else '해당없음'))

    sus = [i for i in rows if grp(i) != '해당없음']
    print('최종 else giveup %d건 · 의심 %d건' % (len(rows), len(sus)))
    print()

    print('=' * 100)
    print('의심 48건 태깅')
    print('=' * 100)
    print('%-8s %-6s %-4s %-7s %-13s %5s %6s %7s %5s  %s' % (
        'group', 'hand', 'st', '홀', '보드', 'outs', 'delta', 'eq', 'rel', '태그'))
    print('-' * 100)
    for i in sorted(sus, key=lambda x: (grp(x), -x['eq_delta'])):
        tg = tag(i['_hole'], i['_bd'])
        print('%-8s %-6s %-4s %-7s %-13s %5d %+6.3f %7.3f %5.2f  %s' % (
            grp(i), 'h%d' % i['_h'], i['street'], ' '.join(i['_hole']),
            ' '.join(i['_bd']), i['outs'], i['eq_delta'], i['eq'], i['rel'],
            ', '.join(tg)))

    print()
    print('=' * 66)
    print('그룹별 태그 분포')
    print('=' * 66)
    for g in ('A∩B', 'A only', 'B only'):
        sub = [i for i in sus if grp(i) == g]
        if not sub:
            continue
        c = collections.Counter()
        for i in sub:
            for t in tag(i['_hole'], i['_bd']):
                c[t] += 1
        print('%-8s n=%d' % (g, len(sub)))
        for k, v in c.most_common():
            print('     %-18s %2d' % (k, v))

    print()
    print('=' * 66)
    print('대조군 — 해당없음 222건의 태그 분포 (giveup 이 맞는 쪽)')
    print('=' * 66)
    ctl = [i for i in rows if grp(i) == '해당없음']
    c = collections.Counter()
    for i in ctl:
        for t in tag(i['_hole'], i['_bd']):
            c[t] += 1
    for k, v in c.most_common():
        print('  %-18s %3d (%.0f%%)' % (k, v, 100*v/len(ctl)))


if __name__ == '__main__':
    main()
