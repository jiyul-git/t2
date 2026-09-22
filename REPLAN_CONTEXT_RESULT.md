# replan current-context forwarding — 결과

이 문서는 PHASE 2 의 **관측 사실과 귀속**만 동결한다. 평가나 튜닝 결론은
넣지 않는다.

```
base                576f483  (integration/ui-v49-money-jump-20260920)
production commits  12d7c7e  fix: forward current decision context through revise_plan
도구 commits         5b6c546  tools: verify replan context forwarding contract
                    462bd90  tools: characterize post-fix replan behavior (paired)
                    c716a40  test: freeze post-replan-context regression baseline
                    7553538  tools: add post-replan-context reachability reference
```

## 1. 계약

`board_changed` 재계획이 최초 `make_plan` 과 같은 현재 결정 맥락을 받는다.
대상 7필드:

```
oop_vs_aggr  oop_legacy_abs  initiative  tilt  bb_chips  opp_est  opp_stack_bb
```

수정 전에는 `update_plan` 에 이미 들어와 있는 7개를 `revise_plan` 호출에서
버렸다. `opp_est`/`opp_stack_bb` 는 state 스냅샷으로 되돌아가고 나머지 다섯은
`make_plan` 기본값으로 떨어졌다.

## 2. explicit None != missing

`if x is None: fallback` 을 쓰지 않는다. `oop_vs_aggr=None` 은 '지금
어그레서가 없다' 라는 실제 관측이고, 그렇게 쓰면 관측이 조용히 기본값으로
바뀐다.

`runner._MISSING` sentinel 로 "인자가 아예 생략됨" 과 "명시적으로 None 이
전달됨" 을 가른다.

```
생략한 옛 직접 호출자   opp_est/opp_stack_bb = state 스냅샷
                      나머지 5개 = make_plan 기본값 (수정 전과 동일)
update_plan 정상 경로   7개 전부 명시 전달. None 도 명시로 간다.
```

기본값은 runner 에 적지 않고 `inspect.signature(PL.make_plan)` 에서 읽는다.
**import 시점 1회** 고정이다 — 지연시키면 도구가 `PL.make_plan` 을
monkeypatch 한 뒤 처음 불릴 수 있고, 그러면 래퍼의 `(*a, **k)` 를 기본값으로
캐시한다. 실제로 그렇게 한 번 깨졌다.

## 3. direct caller inventory (AST 전수)

| caller | 분류 | 처리 |
|---|---|---|
| `plan.py:1515` | production | 유일한 직접 호출. 7개 명시 전달 |
| `tools/edge_probe.py:31` | tools | `revise_plan` 을 대체. `**ctx` 로 받아 그대로 전달 |
| `tools/replan_oop_probe.py:150` | tools | 대체. `**_ctx` 로 받아 버리고, baseline arm 도 옛 semantics 를 명시 설치 |
| `tools/river_trace.py:31` | dead | `PL.revise_plan` 속성이 없어 `hasattr` 가드에서 건너뜀 |
| `tools/axis_dataflow.py:35` | 정적 | 이름 목록만 |
| `tools/verify_replan_contract.py:76` | 정적 | `KNOWN_MISSING` 비움, 옛 목록은 `HISTORICAL_MISSING` 으로 보존 |

## 4. paired fixture

`tools/replan_context_paired.py`. 같은 입력을 두 계약으로 재생한다.
before = 7개 생략 경로, after = 현재 맥락 전달.

```
fixture   seeds 5150,9001,4242 x standard x 16핸드 x entries 100
replan events                        237
engine_errors                          0

plan changed                           1
act changed                            0
normalized size changed                7
실제 chip amount changed               6
size 는 달랐는데 100칩 반올림 후 같음      1
```

칩 환산은 엔진 식 그대로다 (`plan.py:1363`,
`min(stack, int(round(pot*size/100))*100)`).

```
ev11   turn   value_2street -> block          size 0.604->0.486  chips  800-> 700
ev50   turn   bluff_2street -> bluff_2street  size 0.725->0.700  chips 6700->6500
ev116  river  value_3street -> value_3street  size 0.471->0.473  chips 5000->5100
ev141  turn   bluff_2street -> bluff_2street  size 0.649->0.749  chips 2200->2500
ev212  turn   bluff_2street -> bluff_2street  size 0.796->0.881  chips 2500->2700
ev232  river  value_3street -> value_3street  size 0.892->0.882  chips 9200->9100
ev235  turn   value_3street -> value_3street  size 0.798->0.795  chips 3800->3800
```

`ev235` 가 반올림에 묻힌 1건이다.

### first divergence

```
event 11 (turn)
  before  {'plan': 'value_2street', 'act': 'bet', 'size': 0.604}  ->  800칩
  after   {'plan': 'block',         'act': 'bet', 'size': 0.486}  ->  700칩
  값이 다른 맥락 필드  oop_vs_aggr, oop_legacy_abs, initiative, bb_chips, opp_est
```

### RNG

```
최초 행동 divergence   event 11
최초 RNG divergence    event 60
그 이전 event 들에서 호출열·최종 state 동일   예
```

"최종 RNG state 가 항상 같아야 한다" 는 요구하지 않았다. 맥락이 전달돼
행동이 달라진 뒤 스트림이 갈리는 것은 정상이다. 각 replan event 는 같은
입력에서 독립적으로 재생되므로 이건 연속 스트림 비교가 아니라 event 단위
짝 비교다.

## 5. regress

```
불일치 시드  [3004]   (3000·3001·3002·3003·3005 는 post-oop 와 동일)
VPIP 19.1%  PFR 11.4%  flop 44.4%   (기준선과 동일)
```

### seed 3004 귀속

같은 fixture 에서 arm 을 갈랐다.

```
before(7개 생략)   91dc80039cce055b
after (7개 전달)   c65338fd43321e98

단일 필드 arm
  opp_est          c65338fd43321e98     after 와 같다
  나머지 6개        91dc80039cce055b     before 와 같다

leave-one-out
  -opp_est         91dc80039cce055b     빼면 before 로 돌아간다
  나머지 6개 제거    c65338fd43321e98     영향 없음

최초 divergence   23번째 핸드, 로그 12번 항목
  before ('turn', 1, 'bet', 2100)  ->  after ('turn', 1, 'bet', 2000)
```

**`opp_est` 단독이 완전히 설명한다.** 단일 arm 지문이 all7 지문과 같고,
빼면 정확히 옛 지문으로 돌아간다.

**설명되지 않는 divergence 0.**

## 6. reachability

세 세대. 앞 두 세대는 숫자를 그대로 보존한다.

```
                    PRE_BLOCKBET  POST_BLOCKBET  POST_REPLAN_CONTEXT
blockbet eligible        2815          2803             2747
         entered         1773          1773             1740
         mid_branch       301           300              296
         block_condition   61            60               81
         gate_true         49            48               63
         taken             13            12               12
         changed            0            12               12
sk_fallback eligible    1773          1773             1740
oop_sensitive eligible   586           586              584
overbet entered           95            96               96
```

`taken`/`changed` 는 12/12 로 그대로인데 게이트가 더 자주 열린다
(`block_condition` 60 → 81, `gate_true` 48 → 63). `oop_vs_aggr` 와
`initiative` 가 replan 경로의 `make_plan` 에도 도달하기 때문이다.

구조 invariant `blockbet changed == taken` 은 세대와 무관하게 계속 검사하고
현재 PASS 다.

## 7. 하지 않은 것

- A6 full 810-event fixture 재실행 **안 했다**
- 기존 baseline/reference 파일 **덮어쓰지 않았다**
- 임계값·확률식·사이징 공식 **변경 없다**
