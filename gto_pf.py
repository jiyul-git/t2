"""GTO 계산기 푸시/폴드 기준(10~25bb) — 프리플랍 판단의 **기준(reference)** 층.

데이터: data/gto_pf/pushfold_v1.json (tools/gto_pf_build.py 가 GTO 브랜치의
pf10/15/20/25 기록에서 만든다). 9맥스, 안테 합계 1bb, 전원 같은 스택, 칩 EV,
등급 quick(빠른 값). 사용자 결정 2026-10-19: 계산한 레인지를 T2 기준으로 쓴다.

이 모듈은 '레귤러가 공부한 답'만 돌려준다. 사람이 그 답을 얼마나 따르는가
(차트 지식), ICM/버블 체감, 성향 이탈은 preflop.py 가 정한다.

조회 규칙
  - 스택: 유효 스택(bb, 핸드 시작 기준). 10~25bb(±0.25) 밖이면 None(기존 경로).
    버킷 사이는 선형 보간. 한쪽 버킷에 노드가 없으면 None.
  - 좌석: 6~9인 테이블은 '뒤에 남은 인원'이 같은 9맥스 자리로 옮긴다.
    SB/BB 는 그대로. 5인 이하와 노안테는 None.
"""
import json, os

_D = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(_D, 'data', 'gto_pf', 'pushfold_v1.json')
_DATA = None
_IDX = None

PRE9 = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
SEATS_OK = (6, 7, 8, 9)
RV = {r: i + 2 for i, r in enumerate('23456789TJQKA')}


def _load():
    global _DATA, _IDX
    if _DATA is None:
        _DATA = json.load(open(_PATH, encoding='utf-8'))
        _IDX = {c: i for i, c in enumerate(_DATA['classes'])}
    return _DATA


def hand_class(c):
    """홀카드 2장 → 'AKs' / 'AKo' / 'AA'. preflop.cls 와 같은 표기."""
    v = sorted([c[0][0], c[1][0]], key=lambda x: -RV[x])
    if c[0][0] == c[1][0]:
        return v[0] + v[1]
    return v[0] + v[1] + ('s' if c[0][1] == c[1][1] else 'o')


def pos9(pos, seats):
    """좌석 수가 다른 테이블의 자리를 뒤 인원이 같은 9맥스 자리로."""
    if pos in ('SB', 'BB'):
        return pos
    if int(seats) not in SEATS_OK:
        return None
    import table as _TB
    _, pre, _ = _TB.orders(int(seats))
    if pos not in pre:
        return None
    behind = len(pre) - 1 - pre.index(pos)          # 뒤에 남은 인원(블라인드 포함)
    i = len(PRE9) - 1 - behind
    return PRE9[i] if 0 <= i < len(PRE9) - 2 else None


EDGE_BB = 0.25      # 경계 허용폭: 10bb/25bb 시작 스택이 안테·소수점으로 살짝 벗어나는 것


def covered(eff_bb, seats, ante):
    d = _load()
    b = d['buckets']
    return (bool(ante) and int(seats) in SEATS_OK and eff_bb is not None
            and b[0] - EDGE_BB <= float(eff_bb) <= b[-1] + EDGE_BB)


def _interp(table, key, eff_bb, pick):
    """버킷 사이 선형 보간. pick(entry) → 169 리스트 또는 None."""
    d = _load()
    b = d['buckets']
    x = max(b[0], min(b[-1], float(eff_bb)))
    hi = next(i for i, v in enumerate(b) if v >= x)
    lo = max(0, hi - 1) if b[hi] > x else hi
    ea = (d[table].get(str(b[lo])) or {}).get(key)
    eb = (d[table].get(str(b[hi])) or {}).get(key)
    if ea is None or eb is None:
        return None
    va, vb = pick(ea), pick(eb)
    if va is None and vb is None:
        return None
    va = va or [0.0] * len(d['classes'])
    vb = vb or [0.0] * len(d['classes'])
    t = 0.0 if hi == lo else (x - b[lo]) / (b[hi] - b[lo])
    return va, vb, t


def _at(trip, hand):
    if trip is None:
        return None
    va, vb, t = trip
    i = _IDX[hand_class(hand)]
    return max(0.0, min(1.0, va[i] + t * (vb[i] - va[i])))


def first_in(pos, seats, eff_bb, hand, ante=True):
    """첫 진입 {'jam','open','fold'} 확률. 범위 밖이면 None."""
    if not covered(eff_bb, seats, ante):
        return None
    p = pos9(pos, seats)
    if p is None or p == 'BB':
        return None
    jam = _at(_interp('first_in', p, eff_bb, lambda e: e['jam']), hand)
    opn = _at(_interp('first_in', p, eff_bb, lambda e: e['open']), hand)
    if jam is None:
        return None
    opn = opn or 0.0
    s = jam + opn
    if s > 1.0:
        jam, opn = jam / s, opn / s
    return {'jam': jam, 'open': opn, 'fold': max(0.0, 1.0 - jam - opn)}


def call_vs_jam(jammer_pos, def_pos, seats, eff_bb, hand, ante=True):
    """앞 전원 폴드 뒤 단독 올인에 콜할 확률. 범위 밖이면 None."""
    if not covered(eff_bb, seats, ante):
        return None
    a, b = pos9(jammer_pos, seats), pos9(def_pos, seats)
    if a is None or b is None:
        return None
    return _at(_interp('vs_jam', a + '>' + b, eff_bb, lambda e: e), hand)


def call_vs_3bet_jam(opener_pos, jammer_pos, seats, eff_bb, hand, ante=True):
    """오픈 후 3벳 올인을 받은 오프너가 콜할 확률. 범위 밖이면 None."""
    if not covered(eff_bb, seats, ante):
        return None
    a, b = pos9(opener_pos, seats), pos9(jammer_pos, seats)
    if a is None or b is None:
        return None
    return _at(_interp('vs_3bjam', a + '>' + b, eff_bb, lambda e: e), hand)
