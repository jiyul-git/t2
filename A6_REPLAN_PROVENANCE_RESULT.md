# A6 full fixture — replan provenance 결과

기준 브랜치: `claude/a6-replan-opt`  
실행 기준 HEAD: `a0c7a8a5c755a55c6a255d21881f386c1b1a1b24`

이 문서는 A6 full fixture의 실행 결과를 동결한다. production 코드와
`runner.revise_plan`은 수정하지 않은 상태의 결과다.

## 1. 실행 전 고정값

```
HEAD             a0c7a8a5c755a55c6a255d21881f386c1b1a1b24
tool_revision    0086fa339c58244d8459a789f5ed838a79acf58a6e7a99b2753986d5d4485a44
code_digest      d8b9676e5df69880e9d7e7e3cc37b06dce15402166510aec1ef0cea7db3577d2
arm_spec_digest  287839a6754fb794db0223352e5bfa472632fc0dbc0b9f023520c74fb6c75550
fixture          entries=100, hands=16,
                 seeds=[5150,9001,4242],
                 fmts=[standard,deep,turbo]
_assert_defaults OK
```

reference full run은 돌리지 않았다. 최적화 구현의 subset exact-equivalence는
도구 개발 단계에서 별도로 확인되어 있다.

## 2. capture

```
update_plan            4,736
revise_path            2,580
board_changed/replan     810
engine_errors              0
events total             810
```

engine error 0이므로 결과는 VALID이다.

## 3. provenance mismatch

| 필드 | different / 810 | rate |
|---|---:|---:|
| oop_vs_aggr | 520 | 64.2% |
| oop_legacy_abs | 810 | 100.0% |
| initiative | 562 | 69.4% |
| tilt | 0 | 0.0% |
| bb_chips | 810 | 100.0% |
| opp_est | 810 | 100.0% |
| opp_stack_bb | 489 | 60.4% |

## 4. single-field behavioral impact

| 필드 | changed | different_input | diff |
|---|---:|---:|---|
| oop_vs_aggr | 0 | 520 | 없음 |
| oop_legacy_abs | 0 | 810 | 없음 |
| initiative | 0 | 562 | 없음 |
| tilt | 0 | 0 | 반사실 성립 안 함 |
| bb_chips | 2 | 810 | size 2 |
| opp_est | 7 | 810 | size 7 |
| opp_stack_bb | 0 | 489 | 없음 |

`bb_chips` changed ids: 228, 231.  
`opp_est` changed ids: 50, 112, 137, 208, 277, 459, 565.

## 5. all-current

```
changed 15 / 810 = 1.85%
diff_kinds {size: 15}
ids [50,112,137,208,228,231,277,362,429,459,565,608,647,727,733]
```

plan label 변화 0건, intent act 변화 0건. 15건 전부 size 차이다.

## 6. interaction arms

```
bb+opp_est             9  [50,112,137,208,228,231,277,459,565]
bb+opp_stack           8  [228,231,362,429,608,647,727,733]
opp_est+opp_stack      7  [50,112,137,208,277,459,565]
context_core3         15  [50,112,137,208,228,231,277,362,429,459,565,608,647,727,733]
core+initiative        9  [50,112,137,208,228,231,277,459,565]
core+oop_vs            9  [50,112,137,208,228,231,277,459,565]
core+oop_legacy        9  [50,112,137,208,228,231,277,459,565]
core+position          9  [50,112,137,208,228,231,277,459,565]
all7                  15  [50,112,137,208,228,231,277,362,429,459,565,608,647,727,733]
```

모든 arm의 diff_kinds는 `size` 단독이다.

## 7. leave-one-out

```
빼는 필드         without  removed  added
bb_chips             7        8       0
initiative          15        0       0
oop_legacy_abs      15        0       0
oop_vs_aggr         15        0       0
opp_est              8        7       0
opp_stack_bb         9        6       0
tilt                15        0       0
```

removed ids:
- `bb_chips`: 228, 231, 362, 429, 608, 647, 727, 733
- `opp_est`: 50, 112, 137, 208, 277, 459, 565
- `opp_stack_bb`: 362, 429, 608, 647, 727, 733

모든 필드에서 added=0. 필드를 빼서 새 divergence가 생기지 않는다.

## 8. 구조 해석

### 8-1. 단독 행동 효과가 확인된 필드

`opp_est` 7건, `bb_chips` 2건이다. 둘 다 plan/act가 아니라 size만 바꾼다.

### 8-2. `opp_stack_bb`는 단독효과 0이지만 interaction에 기여한다

`plan.py`의 유효 상대 스택 계산은 다음 AND gate다.

```python
_opp_eff = None
if opp_stack_bb and bb_chips and stack > 0:
    _opp_eff = min(1.0, (opp_stack_bb * bb_chips) / stack)
```

`target_commit(..., opp_stack_bb=...)`은 인자를 받지만 본문에서 직접
`opp_stack_bb`를 소비하지 않고 `opp_eff`가 행동 경로에 닿는다.

따라서 baseline에서 `bb_chips=None`이면 `_opp_eff`는 항상 None이고,
`opp_stack_bb` 단독 0건은 이 fixture의 표본 부족으로 해석하지 않는다.

분해:

```
opp_est 단독               7
bb_chips 단독              2
bb_chips × opp_stack_bb    6
----------------------------
context_core3             15
```

세 집합은 서로 겹치지 않는다.

### 8-3. 위치/initiative 3개는 A6만으로 무효과 판정을 내리지 않는다

`oop_vs_aggr`, `oop_legacy_abs`, `initiative`는 mismatch가 크지만
single-field 0, LOO removed/added 0이다.

그러나 이 셋의 `make_plan` 소비처인 blockbet 분기는 기존 A5 계측에서
block 선택 후 뒤의 머징 분기가 plan을 다시 대입하여 최종 block이 0건인
도달 불가 경로로 확인됐다.

따라서 현재의 0은 "필드가 필요 없다"가 아니라 **소비처가 죽어 있어
효과가 가려진 상태**로 해석한다. blockbet 제어흐름 수정 뒤 관련 arm을
재측정해야 한다.

### 8-4. tilt는 판정 보류

`tilt`는 current와 baseline이 다른 event가 0/810이다. 따라서
"행동 영향이 없다"가 아니라 이 fixture에서 반사실이 한 번도 성립하지 않았다.

## 9. size divergence와 실제 칩 divergence는 구분한다

15건의 plan-level size 변화폭은 -0.072 ~ +0.232 pot이다.
그중 6건은 `|Δ| <= 0.012`다.

다만 `plan.py`의 100칩 반올림 때문에 사라지는지 여부는 각 event의
pot과 반올림 전/후 최종 chip amount를 직접 계산해야 한다.
따라서 15건을 곧바로 production-visible bet amount divergence 15건으로
부르지 않는다.

## 10. 성능

```
capture              252.6 s
analysis             452.6 s
total                706.2 s
actual replays       13,267
cache hits           arm 5,334 + baseline signature 17,791
naive 대비           18,581 -> 13,267  (-28.6%)
loaded_from_checkpoint=0
heartbeat 최대 간격  10.7 s
```

재생 횟수 예측은 정확했다. 시간 calibration만 낮게 편향됐다.
앞 20 event에서 baseline 직후 같은 event arm을 재생해 warm-cache 조건
`0.0108 s/replay`를 측정했기 때문이다. full 평균은
`452.6 / 13,267 = 0.0341 s/replay` 수준이다.

## 11. 다음 순서

1. 이 A6 결과를 기준점으로 유지한다.
2. blockbet의 덮어쓰기 제어흐름을 별도 브랜치에서 수정한다.
3. 수정 후 `oop_vs_aggr`, `oop_legacy_abs`, `initiative` 관련 A6 arm을 재측정한다.
4. 그 결과와 이미 확인된 `opp_est`, `bb_chips`, `opp_stack_bb`를 합쳐
   최종 `revise_plan` context 전달 계약을 정한다.

A5와 A6를 따로 읽지 않는다. A5를 살리기 전의 위치/initiative 0건을
최종 무효과 판정으로 사용하지 않는다.
