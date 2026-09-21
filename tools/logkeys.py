# -*- coding: utf-8 -*-
"""intent 로그의 키 호환. 읽기 전용.

session 이 기록하는 OOP 플래그는 소비처마다 기준이 달라 셋으로 나뉘었다.

  oop_field       뒤에 아직 액션할 상대가 있는가 (= last to act 가 아닌가)
  oop_vs_aggr     어그레서보다 내가 먼저 액션하는가 (없으면 None)
  oop_legacy_abs  옛 절대식 (h.POST.index(pos) < 3). 대조용으로만 남긴다

과거 로그에는 이 셋 대신 'oop' 하나가 있고 그 값은 절대식이다.
분석 도구는 새 로그를 우선하고 과거 로그로 폴백해야 하는데, 그냥
`rec.get('oop')` 로 두면 새 로그에서 **조용히 전부 IP/0** 이 된다.
"""

_MISSING = object()


def oop_of(rec, default=None):
    """OOP 플래그. 새 로그는 oop_field, 과거 로그는 oop.

    둘 다 없으면 침묵하지 않고 default(기본 None)를 돌려준다.
    호출부는 None 을 'IP'/0 으로 접지 말고 '없음'으로 표시할 것.
    """
    v = rec.get('oop_field', _MISSING)
    if v is _MISSING:
        v = rec.get('oop', _MISSING)
    return default if v is _MISSING else v


def oop_label(rec, missing='?'):
    """표시용 'OOP' / 'IP' / missing."""
    v = oop_of(rec)
    return missing if v is None else ('OOP' if v else 'IP')
