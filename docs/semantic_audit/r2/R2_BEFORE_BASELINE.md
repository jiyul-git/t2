# R2 before baseline — 행동 봉인

R2 행동 변경의 기준점은 `test` **`46a2070c1af4d4585c9ef00902de6405d98d4cef`** 이다.
R2 첫 보고 커밋은 읽기 전용 도구(`tools/r2_*.py`)와 문서만 추가한다. production 모듈은 이 커밋과 바이트 단위로 같다.
- 확인 방법: `git diff --stat 46a2070 -- '*.py' ':!tools'` 가 비어 있어야 한다.

R2 행동 변경은 이 봉인 위에 **semantic cleanup 과 분리된 별도 커밋**으로 시작한다.
변경 커밋마다 아래 세 가지를 이 봉인값과 비교해 차이를 보고한다.

## 1. baseline sim 지문

조건: tilt 0, exploit/상대 적응 중립(read book 누적 없음), 전원 동일 max-skill 프로필(개념 10, 기질 중립), 90 entries, 시드별 60핸드 상한, 시드마다 별도 프로세스.

```
python tools/r2_baseline_sim.py 11 60
python tools/r2_baseline_sim.py 12 60
```

| 시드 | 핸드 | 프리플랍 결정 | 오류 | sha256(결정 + 핸드 기록의 canonical JSON) |
|---|---|---|---|---|
| 11 | 583 | 5,147 | 0 | `e6d8b5e58e91d599869244d1782b28e31cefbb25d7c777030fdc7d923a015339` |
| 12 | 566 | 5,010 | 0 | `c13a5bf4b0775876fccb6e70a8f97371316eed5c1bf28a0975b993e79583c057` |

교차 확인: 재감사 단계에서 46a2070 작업 트리로 만든 baseline sim 기록(별도 하네스)과 비교했다. 프리플랍 결정 10,157건(액션·사이즈·레벨)과 1,149핸드 전체 로그·최종 스택이 모두 같다. 그래서 이 하네스는 재감사 때 쓴 baseline 과 같은 행동을 재현한다.

## 2. 게이트

23개 게이트(`CANONICAL_VERIFIER_MANIFEST` 의 in_23_gate)를 46a2070 작업 트리에서 실행한 결과(재감사 단계 기록과 동일)는 17 통과 / 6 기존 실패다.
- 기존 실패: `verify_p4_vs_3bet`, `verify_f3_checkraise_response`, `verify_f4_facing_bet`, `verify_f6_caller_backaction`, `verify_f7_street_closure`, `verify_weighted_boundaries`.
- 이 6개는 46a2070 이전부터 실패한 legacy 실패다. manifest 에 사유가 있다.
- R2 변경 후 통과·실패 집합이 달라지면 그 차이를 보고한다.

## 3. 디펜스 지식 동결값

`defend_baseline_46a2070.json`(B 표의 원자료)이 vs-open 디펜스의 L0/L1/L2 값을 동결한다. 8-max·9-max, 15~100bb, 모든 opener/defender 쌍이 들어 있다.
- 다시 만들기: `python tools/r2_freeze_defend_baseline.py out.json` → 46a2070 에서는 이 파일과 같은 숫자가 나와야 한다.

## 4. 측정 재현 (외부 자료)

- 기준 차트: `git clone https://github.com/matthiola0/poker-hand-review` (커밋 `9ef33a4d70b48c4ec8aea6093562e38ef46feb24`)
- `python tools/r2_reference_charts.py <clone>/gto-preflop/mtt/8max/charts reference_8max_summary.json`
- `python tools/r2_compare_defend_reference.py r2/reference_8max_summary.json out.json`
- `python tools/r2_ordering_fidelity.py <charts> out.json` (equity 순서는 `eq_vs_random_169.json` 캐시를 쓴다. 지우면 다시 계산하며 약 1.5분 걸린다)
- `python tools/r2_vs3bet_probe.py <charts> out.json`
- `python tools/r2_plot_defend.py`
