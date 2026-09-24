# A5 4-B interim — single-field result and design correction

기준: `chatgpt/a5-block-context-4a-20260925`

## 1. 최초 4-B 실행 결과

동일 fixture:
- entries=100
- hands=16
- seeds=[5150,9001,4242]
- fmts=[standard,deep,turbo]

R1 replication / R2 clean 모두:
- update_plan 4,687
- revise_path 2,547
- board_changed 789
- engine errors 0

single-field 결과:

| field | different | changed | raw chip target changed |
|---|---:|---:|---:|
| oop_vs_aggr | 503 | 0 | 0 |
| oop_legacy_abs | 789 | 0 | 0 |
| initiative | 544 | 0 | 0 |

R1/R2 aggregate는 세 필드 모두 SAME.

과거 frozen A6는 810 events에서 각각 520/0, 810/0, 562/0이었다.
현재 A5 기준 fixture는 789 events이므로 절대 모집단 수는 직접 동일시하지 않는다.

## 2. 이 0건으로 계약 판정을 하면 안 되는 이유

block gate는 다음 AND 구조다.

```python
_oop_a = oop_vs_aggr if oop_vs_aggr is not None else bool(oop_legacy_abs)
if _oop_a and not initiative and 0.25 <= rel <= 0.80:
    block_p = ...
```

A6 baseline default는:

```
oop_vs_aggr    = None
oop_legacy_abs = None
initiative     = True
```

따라서 single-field arm은 구조적으로 block gate를 열 수 없다.

- oop_vs_aggr만 current로 교체
  - `_oop_a`가 True가 되어도 `initiative=True`가 남아 gate false
- oop_legacy_abs만 current로 교체
  - 같은 이유로 `initiative=True`가 gate를 막음
- initiative만 current(False)로 교체
  - 두 oop 값이 None이라 `_oop_a=False`, gate false

즉 single-field 0건은 “세 필드가 revise_plan에 불필요”라는 증거가 아니다.
A6의 `opp_stack_bb × bb_chips`와 같은 종류의 interaction 문제다.

## 3. 수정된 4-B 설계

single-field arm은 continuity용으로 유지하고 다음 joint arms를 추가한다.

- `oop_vs_aggr + initiative`
- `oop_legacy_abs + initiative`
- `position3 = oop_vs_aggr + oop_legacy_abs + initiative`

각 arm에서:
- effective input event 수
- block gate true 수
- plan / intent act / intent size changed
- raw chip target changed
- final plan==block 수
- block 선택 메시지 수

를 기록한다.

R1 replication과 R2 clean을 다시 분리해 실행한다.
production 코드는 수정하지 않는다.

도구 수정 commit: `0feed659613b9d8232f6520303227ef6f2839165`
