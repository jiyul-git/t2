# A5 blockbet control-flow fix

기준:
- A6 결과 동결: `A6_REPLAN_PROVENANCE_RESULT.md`
- 수정 브랜치: `claude/a5-blockbet-fix`
- A6 결과 동결 커밋: `492a2ed0151c2d29b8743080719155d6a2ee31c2`

## 문제

`make_plan`의 `eq >= pcz` 중간강도 분기에서 blockbet을 선택한 뒤에도
바로 아래 머징 `if/elif/else`가 항상 실행됐다.

수정 전 구조:

```python
if block_roll_passed:
    plan = 'block'

if potcontrol_roll_passed:
    plan = 'pot_control'
elif merge_value:
    plan = 'value_2street'
else:
    plan = 'showdown' if made >= 1 else 'giveup'
```

두 번째 체인은 세 갈래 모두 `plan`을 대입하므로 선택된 `block`이
make_plan 반환까지 살아남는 경로가 없었다. 과거 계측에서도 block 메시지가
남은 이벤트의 최종 plan이 모두 다른 라벨로 바뀌었다.

## 수정 원칙

새 임계값, 새 확률, 새 plan 라벨을 만들지 않는다.

block과 머징 폴백은 같은 중간강도 자리의 **서로 배타적인 대안**으로 취급한다.
block이 선택되지 않았을 때만 기존 머징 체인을 평가한다.

수정 후 구조:

```python
if block_roll_passed:
    plan = 'block'
else:
    if potcontrol_roll_passed:
        plan = 'pot_control'
    elif merge_value:
        plan = 'value_2street'
    else:
        plan = 'showdown' if made >= 1 else 'giveup'
```

계수, 게이트, 확률식, `SIZING['block']`, `decide_aggression(plan=='block')`,
`_allowed`는 건드리지 않는다.

## 검증 순서

1. `python3 tools/block_trace.py --seeds 5000-5007`
   - 핵심 불변식: S4(블락벳 선택) == S5(make_plan 반환 block)
   - S6 이후 감소는 `river_fix` / `_allowed`와 분리해서 본다.
2. `python3 tools/regress.py check --baseline current`
   - 이 수정은 의도적으로 행동을 바꿀 수 있으므로 기존 지문과 다르면
     곧바로 실패로 단정하지 않는다.
   - 변화가 block 선택 이벤트에서만 시작되는지 귀속을 확인한다.
3. A6의 위치 관련 arm 재측정
   - `oop_vs_aggr`
   - `oop_legacy_abs`
   - `initiative`
   A5 수정 전에는 이 세 필드의 유일한 소비처가 죽어 있어 A6 영향 0이었다.
4. 최종 `revise_plan` context 전달 계약은 3의 결과가 나온 뒤 결정한다.

## 범위 밖

- blockbet 확률 calibration
- `blockbet` concept 분포
- aggressor 없는 pot의 block/donk semantics
- `revise_plan` 누락 필드 전달
- tilt calibration

이 항목들은 이번 control-flow 수정과 섞지 않는다.
