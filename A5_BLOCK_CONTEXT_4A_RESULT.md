# A5 4-A block context 전달성 결과

기준 브랜치: `chatgpt/a5-block-context-4a-20260925`  
기준: A5 1~3단계 종결 `e722fdc` 이후, production 무수정  
도구: `tools/block_context_arms.py`  
실행: `--seeds 5000-5007`, single-process, tournament마다 분석 하네스에서만 `_TILT_VIEW_CACHE` clear

## 1. 건전성

- 4 arm × 8 seed
- 모든 seed engine errors = 0
- production 코드 수정 없음
- A6 baseline 의미:
  - `oop_vs_aggr=None`
  - `oop_legacy_abs=None`
  - `initiative=True`

## 2. Funnel totals

| arm | S1 | S3 | S4 | S5 | S6 | S8 |
|---|---:|---:|---:|---:|---:|---:|
| current | 459 | 146 | 23 | 23 | 21 | 15 |
| oop_vs_aggr_default | 463 | 158 | 26 | 26 | 24 | 17 |
| oop_legacy_abs_default | 446 | 138 | 18 | 18 | 18 | 13 |
| initiative_default | 0 | 0 | 0 | 0 | 0 | 0 |

Delta vs current:

| arm | ΔS1 | ΔS3 | ΔS4 | ΔS6 | ΔS8 |
|---|---:|---:|---:|---:|---:|
| oop_vs_aggr_default | +4 | +12 | +3 | +3 | +2 |
| oop_legacy_abs_default | -13 | -8 | -5 | -3 | -2 |
| initiative_default | -459 | -146 | -23 | -21 | -15 |

## 3. Current-street linked path

| arm | S6_linked | S8_linked |
|---|---:|---:|
| current | 13 | 8 |
| oop_vs_aggr_default | 14 | 9 |
| oop_legacy_abs_default | 10 | 6 |
| initiative_default | 0 | 0 |

## 4. 해석 범위

이 도구는 live-arm이다. arm이 한 번 행동을 바꾸면 이후 tournament state도 갈릴 수 있으므로
arm 간 절대 건수 차이를 paired-event 인과효과로 읽지 않는다.

그래도 전달성에 대해서는 다음이 확인된다.

1. `initiative=True` 기본값은 block 조건의 `not initiative`를 직접 막아
   이 fixture에서 S1부터 S8까지 block 경로를 완전히 제거했다.
2. `oop_legacy_abs=None` arm은 current-street linked S8을 8→6으로 줄였다.
3. `oop_vs_aggr=None` arm은 `_oop_a = oop_vs_aggr if ... else bool(oop_legacy_abs)`
   fallback 때문에 relative-to-aggressor 의미를 끄는 것이 아니라 legacy absolute 의미로
   교체된다. 따라서 count 증가(+2 S8)를 “무효과”로 해석하면 안 된다.
4. S4 변화만으로 행동 효과 판정하지 않는다. S8까지 별도로 확인했다.
5. 최종 `revise_plan` context 계약은 4-B paired board_changed/replan fixture에서 결정한다.

## 5. 참고

과거 A5 `block_trace --jobs 1`의 절대 funnel과 이번 current arm의 S1/S3/S4가 완전히
같지 않은 것은 이번 4-A가 tournament마다 `_TILT_VIEW_CACHE`를 clear한 clean 조건이기
때문이다. S8은 15로 동일했다. 이 차이는 4-B에서 R1 replication / R2 clean을 분리해
명시적으로 측정한다.
