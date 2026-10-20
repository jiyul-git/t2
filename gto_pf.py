"""GTO 계산기 프리플랍 기준(10~60bb) — 프리플랍 판단의 **기준(reference)** 층.

데이터: data/gto_pf/pushfold_v1.json (tools/gto_pf_build.py 가 GTO 브랜치의
pf10/15/20/25 와 s30/s40/s60 기록에서 만든다). 9맥스, 안테 합계 1bb, 전원 같은 스택, 칩 EV,
등급 quick(빠른 값). 사용자 결정 2026-10-19: 계산한 레인지를 T2 기준으로 쓴다.

이 모듈은 '레귤러가 공부한 답'만 돌려준다. 사람이 그 답을 얼마나 따르는가
(차트 지식), ICM/버블 체감, 성향 이탈은 preflop.py 가 정한다.

조회 규칙
  - 스택: 유효 스택(bb, 핸드 시작 기준). 10~60bb(±0.25) 밖이면 None(기존 경로).
    버킷 사이는 선형 보간(40~60 사이는 두 버킷의 직선 보간). 한쪽 버킷에 노드가 없으면 None.
  - 좌석: 6~9인 테이블은 '뒤에 남은 인원'이 같은 9맥스 자리로 옮긴다.
    SB/BB 는 그대로. 5인 이하와 노안테는 None.
"""
import json, os

_D = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(_D, 'gto_pf_data.json')   # 실행 폴더에 pf_rank.json 처럼 평평하게 복사된다
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
    if table not in d:
        return None
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
    """첫 진입 {'jam','open','limp','fold'} 확률. 범위 밖이면 None."""
    if not covered(eff_bb, seats, ante):
        return None
    p = pos9(pos, seats)
    if p is None or p == 'BB':
        return None
    trips = {k: _interp('first_in', p, eff_bb, lambda e, k=k: e.get(k))
             for k in ('jam', 'open', 'limp')}
    if all(v is None for v in trips.values()):
        return None
    g = {k: (_at(v, hand) or 0.0) for k, v in trips.items()}
    s = sum(g.values())
    if s > 1.0:
        g = {k: v / s for k, v in g.items()}
    g['fold'] = max(0.0, 1.0 - sum(g.values()))
    return g


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


def aggr_vs_open(opener_pos, def_pos, seats, eff_bb, hand, ante=True):
    """단독 오픈을 받은 자리의 공격 확률 {'jam','r3'}(3벳 올인, 일반 3벳).

    콜/폴드는 돌려주지 않는다 — 플랍 팟을 간이 모델로 매긴 값이라 교정 전까지
    기존 판단이 맡는다. 범위 밖이면 None.
    """
    if not covered(eff_bb, seats, ante):
        return None
    a, b = pos9(opener_pos, seats), pos9(def_pos, seats)
    if a is None or b is None:
        return None
    key = a + '>' + b
    jam = _at(_interp('vs_open', key, eff_bb, lambda e: e.get('jam')), hand)
    r3 = _at(_interp('vs_open', key, eff_bb, lambda e: e.get('r3')), hand)
    if jam is None and r3 is None:
        return None
    return {'jam': jam or 0.0, 'r3': r3 or 0.0}


FULL_OPEN_BB = (1.8, 2.5)   # 플랫콜 루프는 2.0bb 오픈 기준. 이 범위 밖 오픈 크기는 기존 경로.


def defend_vs_open(opener_pos, def_pos, seats, eff_bb, hand, open_bb, ante=True):
    """단독 오픈을 받은 수비자의 전체 응답 {'fold','call','r3','jam'}.

    플랫콜 루프로 보정된 자리(vs_open_full)만. 양쪽 버킷(예: 30·40)에 모두 있어야
    하고(한쪽만 있으면 None), 오픈 크기가 FULL_OPEN_BB 안이어야 한다.
    """
    if not covered(eff_bb, seats, ante) or open_bb is None:
        return None
    if not (FULL_OPEN_BB[0] <= float(open_bb) <= FULL_OPEN_BB[1]):
        return None
    a, b = pos9(opener_pos, seats), pos9(def_pos, seats)
    if a is None or b is None:
        return None
    d = _load()
    if not d.get('vs_open_full'):
        return None
    key = a + '>' + b
    g = {k: _at(_interp('vs_open_full', key, eff_bb, lambda e, k=k: e.get(k)), hand)
         for k in ('fold', 'call', 'r3', 'jam')}
    if any(v is None for v in g.values()):
        return None
    s = sum(g.values())
    return {k: v / s for k, v in g.items()} if s > 0 else None


def jam_vs_3bet(opener_pos, threebettor_pos, seats, eff_bb, hand, ante=True):
    """오픈 후 일반 3벳을 받은 오프너의 4벳(올인) 확률. 범위 밖이면 None.

    s30~s60 트리의 4벳은 올인뿐이다. 60bb 에서도 작은 4벳은 없다(사용자 승인 2026-10-20:
    60bb 도 올인·3벳·4벳 판단만 같은 방식으로 연결)."""
    if not covered(eff_bb, seats, ante):
        return None
    a, b = pos9(opener_pos, seats), pos9(threebettor_pos, seats)
    if a is None or b is None:
        return None
    return _at(_interp('vs_3bet', a + '>' + b, eff_bb, lambda e: e.get('jam')), hand)
