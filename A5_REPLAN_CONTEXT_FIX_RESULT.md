# revise_plan position-context production fix verification

기준 브랜치: `chatgpt/revise-plan-position-context-20260925`

## Production change

최소 배선 변경만 적용했다.

- `plan.update_plan` 이 현재 decision context의
  `oop_vs_aggr`, `oop_legacy_abs`, `initiative` 를 `runner.revise_plan` 에 전달
- `runner.revise_plan` 이 board_changed 재계획의 `plan.make_plan` 에 세 값을 그대로 전달

새 임계값, 확률, block_p 계수, stat_read, aggressor 없는 pot semantics는 수정하지 않았다.

## Pre-fix paired evidence

A5 4-B joint paired replay에서 R1/R2 모두 동일:

- `oop_vs+initiative`: changed 6, raw chip target changed 3
- `legacy+initiative`: changed 7, raw chip target changed 3
- `position3`: changed 7, raw chip target changed 3

따라서 board_changed replan에서 세 context가 행동적으로 도달 가능한 입력임을 확인했다.

## Regression after production fix

Termux 실행:

```
python3 -m py_compile plan.py runner.py session.py
python3 tools/regress.py check --baseline current
```

결과:

```
기준선 : VPIP 19.1%  PFR 11.4%  flop 44.4%
현재   : VPIP 19.1%  PFR 11.4%  flop 44.4%  (rev 062374d)
전 시드 지문 일치 — 동작 보존 확인.
```

이 regression은 기존 고정 fixture의 전 시드 지문이 보존됐음을 뜻한다.
A5 4-B에서 확인한 rare board_changed/block interaction 자체를 다시 검증하는 것은
별도 focused post-fix check로 닫는다.
