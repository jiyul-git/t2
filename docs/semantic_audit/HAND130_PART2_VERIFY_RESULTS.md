# HAND130 Part2 후속 재현·회귀 검증 결과 — 2026-10-10

## 대상·사전 상태
- 저장소: `jiyul-git/t2`; 브랜치 `test3`.
- 감사 전 기준: `945758accf095c634e7a543da73d38160f8b00e2`.
- 실행 검증 대상: `a3ed1dd9849bf919bdf14117239e2115bc952fec`.
- 실전 HAND130 실행 당시 SHA / tilt 값 / 플래그 / W5 중간 텔레메트리: 원자료에 미보존. 이 테스트는 당시의 라이브 프로세스 전체 재생이 아니다.
- 전체 전략 코드/기준선 코드는 감사 전후 동일. 위 두 SHA 비교에서 변경 파일은 새 문서 2개·fixture 1개·진단 스크립트 1개·CI 1개 등 총 5개이며, `preflop.py`, `gto.py`, `persona.py`, `depth.py`, `icm.py`, `plan.py`, `session.py`, `ranges.py`, `tourney.py`, `play.py`, `tools/regress.py` 및 `tools/baseline_9max_post_f8.json`은 변경되지 않았다.

## W5 원인과 숫자
- 문제는 기존 분석자가 `preflop.tighten_defend_widths_for_raise_level`의 `tp *= lt` 이후 사용되는 `tp`를 **갱신 전 값으로 잘못 대입한 것**이다.
- 정상 소스 결과 `W5=0.016657816839054443`, 과거 대화 값 `0.0166578`과 표시 자리 일치.
- 과거 잘못된 정적 재구성 `0.013483745270123415`, 차이 `0.003174071568931028`.
- 레이즈 축소 전 `tp=.017680879951710263`, `tot=.04515237291693793`, `lt=.34`. 먼저 `tp_new=.006011499183581489`; 다음 `W5=tp_new+(tot_old-tp_new)*.272`.
- 원시 콜오프 cap `0.0026843541110758663`(0.2684354111%); 기존 임의 하한으로 최종 `0.005`. AKo 핸드순위 `0.0302`이므로 기존 정책 `fold`.
- 콜 비용 53,442, 콜 후 경합 가능 팟161,884 → 칩 승률 문턱 `0.33012527488819154`. 객관 BF 3.465325 → 현행 scalar-BF 문턱 `0.6306922944416353`. 원 800-sim 에쿼티 0.63182와의 차이 0.0011277055583647222(추정 오차 민감).

## 실제 실행 검증 결과(혼동 금지)

| 검증 | 결과 | 정확한 의미 |
|---|---|---|
| 독립 로컬 Python 산술·계약 단언(12개의 명시적 assert) 및 컴파일 | PASS | 원자료에서 선택한 칩/레이어/정수/수식 재계산. **GitHub 엔진 전체 실행 아님** |
| GitHub Actions `hand130-part2/compile` | **success** | 감사 파일 및 핵심 계산 모듈 Python 문법 |
| GitHub Actions `hand130-part2/equations` | **success** | 실제 저장소 함수를 호출한 고정 B37 projection fixture 재현; W5·공격폭 in-place 순서·플래그 스윕·틸트 민감도·콜 가격 계산 검증 |
| GitHub Actions `hand130-part2/paired` | **success** | 감사 시작 SHA 945758acc와 검증 SHA a3ed1dd에서 동일 Python3.12 runner·`PYTHONHASHSEED=0`·3000~3005(6개) 시드 행동지문 6/6 **완전 동일** |
| GitHub Actions `hand130-part2/regression` | **failure** | 별도 `tools/baseline_9max_post_f8.json`(저장 rev `0962cb2`)과 현재 엔진 지문이 **6/6 시드 불일치**. 이 기준선과 `regress.py`는 이번 작업 동안 변하지 않았다. 기존 기준선 불일치를 동작 보존 PASS로 덮지 않음 |
| GitHub Actions 통합 워크플로 | **failure** | 동결 `current` 기준선 대조 실패를 의도대로 별도 결함으로 남긴 결과. W5 재현과 감사 전후 행동보존 단계는 PASS |

초기 재현기 검증 실패는 `master`에만 존재하는 302KB HAND130 인수인계 문서를 `test3`에서 찾지 못한 fixture 의존 문제였다. `docs/semantic_audit/fixtures/hand130_b37_part2.json`에 관련 **최소 투영값만** 저장하고 재실행하여 해결했다. 전체 실전 토너먼트/실제 tilt를 재생했다고 부풀리지 않는다.

## 5번 부서 인계
`docs/semantic_audit/HAND130_PART2_W5_FOLLOWUP_CONTRACT.md` 참조. `calloff_evidence_v1` 필수: public action history/올인 레이즈 맥락, 정확 칩 기여·콜비용·eligible pot layers, 액션 조건부 관측 레인지(실제 상대 홀카드 금지), layer별 equity/seed/sims/누락, 객관/인지 ICM-BF, 인간 계산·적용 능력의 별도 소비. `gross_return=Σ eligible layer amount*equity`; `chip EV=gross_return-call_cost`; `chip required=call_cost/contestable_after`; `scalar-BF required=BF*call_cost/(pot_before+BF*call_cost)`. 이 BF는 exact payout dollar-EV가 아니다.

결론: **W5 불일치의 원인은 감사 산술 순서 오류로 특정됨. 이번 감사 변경은 전략 행동 보존(6/6)으로 확인. 기존 동결 current baseline 불일치는 별도 열린 문제이며 기존 기준선을 수정하지 않았음. 실제 HAND130의 당시 틸트·플래그·소스 SHA는 근거 미확인으로 유지.**
