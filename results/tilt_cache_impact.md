# persona.tilted_view 캐시 오염 — 영향 범위 측정 (2026-09-12)

persona.py 는 수정하지 않았다. 래퍼로 관찰만 했다.
도구: `tools/tilt_impact.py`, `tools/tilt_cache_probe.py`

## 결함

    persona.py:567  _TILT_VIEW_CACHE = {}
    persona.py:588  key = (prof.get('id'), round(t, 2))

`prof['id']` 는 **좌석 번호**다 (tourney:199 → F.make_player(self.rng, s, ...)
→ PS.make_player(rng, q, pid=s) → p['id'] = s, 1~8).
같은 좌석에 나중에 앉은 **다른 사람**이 반올림 tilt 까지 같으면
먼저 캐시를 채운 사람의 개념 벡터를 그대로 돌려받는다.

`if len(_TILT_VIEW_CACHE) > 4000: clear()` 는 **절대 실행되지 않는다** —
키 공간이 8 × (tilt 2자리) ≈ 400 이다.

같은 docstring 이 id(prof) 를 거부한 이유로 "해제된 객체의 id 가 재사용되면
다른 사람의 뷰를 돌려준다" 고 적어두고, 그 실패 양상을 좌석 번호로 재현했다.

## A. 오염 횟수 (491핸드 · 4토너먼트 · seed0 900000)

    tilted_view 호출              10,390
      캐시 관여 (tilt > 0.02)         188   (1.8%)
      캐시 비관여                   10,202
    **오염된 반환 8** — 캐시 관여의 4.26% · 전체 호출의 0.077%
      type 도 다름                     8
      type 은 같고 개념만 다름           0

"type 비교는 하한"이라는 우려는 이 표본에서 실현되지 않았다.
반환값 전체(concepts·temper·상위필드)를 무캐시 그림자 계산과 비교했다.

오염되면 개념 격차는 크다 (0~10 스케일)

    좌석5 tilt .06  ROCK      → STUDIED_TAG_TIGHT  reraise      4.63
    좌석4 tilt .37  FISH      → TAG_TIGHT          delayed_cbet 6.75
    좌석5 tilt .11  LOOSE_REG → STUDIED_TAG_TIGHT  fold_equity  5.61
    좌석1 tilt .07  TAG_AGGRO → STUDIED_TAG_AGGRO  semibluff    4.01

## B. 실제 판단까지 갔는가 — 호출부 귀속

    호출부              캐시관여  오염   용도
    session.py:161         58     4    프리플랍 판단 프로필  ← 쓰인다
    session.py:189         58     4    h.axes(s)[1] — tilt 숫자만, 프로필 버림
    session.py:376         21     0    상대 프로필 (oax)   ← 쓰인다
    session.py:339         17     0    포스트플랍 판단 프로필 ← 쓰인다
    session.py:440         17     0    프로필 버림
    session.py:484         17     0    프로필 버림

**오염 8 중 실제 판단에 흘러간 것은 4건**(전부 session.py:161 프리플랍).
나머지 4건은 호출부가 tilt 숫자만 쓰고 프로필을 버린다.

앞선 B 단계 서술("8/8 이 판단에 쓰였다")은 틀렸다 —
tilted_view 호출부가 play.py:81 하나라는 것은 맞지만,
그 결과를 받는 session.py 쪽 사용처가 여섯 곳이고 절반은 프로필을 버린다.

## C. 캐시 ON/OFF 반사실

    ON  491핸드 (현재 코드) · OFF 491핸드 (NoCache 로 메모 차단)
    **다른 핸드 0 / 491**

검정이 공허하지 않음을 따로 확인했다.
- NoCache 작동: 같은 토너에서 ON 캐시적중 13 / OFF 0
- 같은 C 구성(4토너 × 최대200, 491핸드)에서 오염 8건이 실재

즉 **프리플랍 판단 4건이 남의 개념 벡터로 내려갔지만 행동은 바뀌지 않았다.**

## 영향 규모에 대한 결론

이 표본에서는 0 이지만 0 이라고 단정하면 안 된다.
앞선 block A/B(6,000핸드 × 2)에서 접두 동일성 검사가 1건 어긋났고,
그 핸드는 포스트플랍 intent 의 type·spr·range 가 달랐다 —
session.py:339 경로의 오염이다.

    관측된 규모: 대략 6,000핸드당 기록이 달라지는 건 1건

실재하는 결함이고 발생하면 봇이 남의 머리로 생각하지만,
지금까지의 측정을 무효화할 규모는 아니다.

## 수정 방향 — 아직 정하지 않는다

- `id(prof)` 로 바꾸면 안 된다. play.py:72 가 `base = dict(p)` 로 매 호출
  새 dict 를 만들어 적중률이 0 이 되고, docstring 이 경고한 id 재사용 문제도
  부활한다
- 프로필에 있는 식별자는 id(좌석)·type·label 뿐이고 **생성 시점의 고유
  식별자가 없다**. 캐시 키를 고치려면 identity 를 먼저 만들어야 한다
