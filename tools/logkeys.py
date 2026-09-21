# -*- coding: utf-8 -*-
"""intent 로그 키의 의미별 접근자. 읽기 전용.

**OOP 에 단일 canonical key 는 없다.** 세 개가 서로 다른 것을 뜻한다.

  oop_field       현재 스트리트에서 내 뒤에 **행동 가능한 상대가 남아 있는가**
  oop_vs_aggr     내가 **어그레서보다 먼저** 행동하는가.
                  어그레서가 없거나 죽었으면 **정당하게 None** 이다
  oop_legacy_abs  옛 절대식 `h.POST.index(pos) < 3`. 대조·호환용

과거 아카이브의 `oop` 는 **정확히 셋째**다 — `0d202c5` 이전 엔진이 쓰던
절대식 그 값이다. 따라서

  legacy `oop` -> oop_legacy_abs   복원 가능
  legacy `oop` -> oop_field        **금지**
  legacy `oop` -> oop_vs_aggr      **금지**

복원할 수 없으면 반드시 `None` 이다. `False`/`0` 으로 만들지 않는다.
771 결정에서 절대식과 field 식이 124건(16.1%) 달랐다 — 폴백으로 메우면
그 16%가 조용히 틀린 값이 된다.

**`False` 는 정상 데이터다.** 없음과 구분해야 하므로 sentinel 로 판정하고
`or` / truthiness 로 판정하지 않는다.

같은 이름, 다른 의미 — 주의
---------------------------
키 `oop` 는 **레코드 종류에 따라 뜻이 다르다.**

  아카이브 intent 레코드   `oop` = 절대식 (oop_legacy_abs)
  tools/f_trace.py 레코드  `oop_field` = field 식  ← A7 에서 이름을 명시로 바꿨다

그 밖에 `tools/axis_freq.py` 의 `s['oop']`, `cf_*.py` 의 `sit['oop']` 은
**로그 키가 아니라 합성 harness 의 상황 필드**다. make_plan 의 입력이지
기록된 관측이 아니므로 이 모듈의 대상이 아니다.
"""

_MISSING = object()


def _pick(rec, names, default):
    """앞선 이름부터 **존재 여부**로 고른다. 값의 참거짓을 보지 않는다."""
    for n in names:
        v = rec.get(n, _MISSING)
        if v is not _MISSING:
            return v
    return default


def oop_field_of(rec, default=None):
    """뒤에 행동 가능한 상대가 남아 있는가.

    현재 로그의 `oop_field` 만 읽는다. 과거 로그에는 이 의미가 **기록된 적이
    없으므로** 폴백하지 않는다 — 없으면 default(기본 None)다.
    """
    return _pick(rec, ('oop_field',), default)


def oop_vs_aggr_of(rec, default=None):
    """어그레서보다 내가 먼저 행동하는가.

    값 자체가 `None` 일 수 있다(어그레서 없음). 그 `None` 과 '키가 없음'은
    둘 다 None 으로 나오므로, 구분이 필요하면 `has_key(rec, 'oop_vs_aggr')`.
    과거 로그에는 이 의미가 없다 — 폴백하지 않는다.
    """
    return _pick(rec, ('oop_vs_aggr',), default)


def oop_legacy_abs_of(rec, default=None):
    """옛 절대식. 과거 아카이브의 `oop` 가 이것이다.

    현재 로그의 명시 키를 우선하고, 없으면 과거 `oop` 로 내려간다.
    """
    return _pick(rec, ('oop_legacy_abs', 'oop'), default)


def has_key(rec, name):
    """키가 실제로 있는가. `None` 값과 '없음'을 구분할 때 쓴다."""
    return rec.get(name, _MISSING) is not _MISSING


def oop_conflict(rec):
    """`oop_legacy_abs` 와 과거 `oop` 가 **둘 다 있고 다른가**.

    진단용이다. 읽기 쪽은 임의로 추론하지 않고 명시 키를 그대로 쓴다.
    """
    if not (has_key(rec, 'oop_legacy_abs') and has_key(rec, 'oop')):
        return None
    a, b = rec.get('oop_legacy_abs'), rec.get('oop')
    return None if a == b else (a, b)


def generation_of(rec):
    """이 레코드가 어느 세대인가. 아카이브 판정용.

      'current'  새 세 키 중 하나라도 있다
      'legacy'   새 키가 없고 `oop` 가 있다
      'unknown'  둘 다 없다 (포지션이 기록되지 않은 레코드)
    """
    if any(has_key(rec, k) for k in
           ('oop_field', 'oop_vs_aggr', 'oop_legacy_abs')):
        return 'current'
    return 'legacy' if has_key(rec, 'oop') else 'unknown'


# ---------------------------------------------------------------- 세대

# 아카이브 세대. `generation_of` 의 세 라벨로는 G0 과 G1 이 뭉친다.
#
#   G0  최소 intent schema. 포지션 키 없음, 실행 필드도 없음
#   G1  실행 필드 있음. 포지션 키 없음. 일부 파일에 retired `replayed`
#   G2  legacy `oop` (절대식)
#   G3  현재. oop_field / oop_vs_aggr / oop_legacy_abs
#
# **G0/G1 을 "legacy OOP 세대"로 읽으면 안 된다.** 그 세대에는 포지션이
# 기록된 적이 **없다**. legacy 로 접으면 "절대식이 있다"는 거짓이 된다.

G3_KEYS = ('oop_field', 'oop_vs_aggr', 'oop_legacy_abs')
G2_KEYS = ('oop',)

# G1 을 G0 과 가르는 표식. 실행(액션 집행) 단계가 기록되기 시작한 세대다.
G1_MARKERS = ('intent_act', 'intent_size', 'intent_src',
              'amt', 'pre_clamp', 'min_raise', 'tocall')

# 현재 producer 가 더 이상 쓰지 않는데 과거 파일에는 있는 키.
# **삭제·migration 대상이 아니다.** 미지의 키 경보와 구분하기 위해 등록한다.
RETIRED_KEYS = {
    'replayed': 'G1 한 파일에만 있다. 강제 액션 재생 여부. '
                'ab06165/959f40a 시절 기록. 현재 producer 0',
    'oop': 'G2 의 절대식. 현재는 oop_legacy_abs 로 이름이 바뀌었다',
}


def archive_generation(rec):
    """레코드의 세대. 'G0' / 'G1' / 'G2' / 'G3'.

    포지션 키가 있으면 그것이 세대를 정하고, 없으면 실행 필드 유무로 가른다.
    """
    if any(has_key(rec, k) for k in G3_KEYS):
        return 'G3'
    if any(has_key(rec, k) for k in G2_KEYS):
        return 'G2'
    return 'G1' if any(has_key(rec, k) for k in G1_MARKERS) else 'G0'


def position_recoverable(rec):
    """이 레코드에서 **복원 가능한** 포지션 의미. 없으면 빈 튜플.

    복원 불가능한 의미를 호출부가 0/False 로 지어내지 않게 하려고 둔다.
    """
    g = archive_generation(rec)
    if g == 'G3':
        return tuple(k for k in G3_KEYS if has_key(rec, k))
    if g == 'G2':
        return ('oop_legacy_abs',)
    return ()


def retired_in(rec):
    """이 레코드에 있는 retired 키. 경보가 아니라 기록용이다."""
    return tuple(k for k in sorted(RETIRED_KEYS) if has_key(rec, k))


def oop_field_label(rec, missing='?'):
    """표시용 'OOP' / 'IP' / missing. field 식 기준."""
    v = oop_field_of(rec)
    return missing if v is None else ('OOP' if v else 'IP')


def oop_legacy_label(rec, missing='?'):
    """표시용. 절대식 기준."""
    v = oop_legacy_abs_of(rec)
    return missing if v is None else ('OOP' if v else 'IP')


# ---------------------------------------------------------------- deprecated

def oop_of(rec, default=None):
    """**deprecated.** `oop_legacy_abs_of` 의 호환 별칭이다.

    예전에는 `oop_field` 를 먼저 보고 없으면 `oop` 로 내려갔는데, 그 폴백은
    **의미를 바꾼다** — 과거 로그의 절대식이 field 식 자리에 들어간다.
    그래서 의미를 절대식 하나로 고정했다.

    **일반적 의미의 'OOP' 는 더 이상 존재하지 않는다.** 새 코드는 세 접근자
    중 하나를 이름으로 골라 써야 한다. 저장소 안에서 이 함수를 부르는 곳은
    0 이고, 바깥의 오래된 스크립트 호환을 위해서만 남겨 둔다.
    """
    return oop_legacy_abs_of(rec, default)


def oop_label(rec, missing='?'):
    """**deprecated.** 절대식 기준 표시. `oop_legacy_label` 을 쓸 것."""
    return oop_legacy_label(rec, missing)
