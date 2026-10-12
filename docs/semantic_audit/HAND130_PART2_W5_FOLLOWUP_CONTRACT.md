# HAND130 B37 — W5 불일치 해결·콜오프 데이터 계약 v1

검증 기준: `jiyul-git/t2` 브랜치 `test3`, 기존 분석 출발 HEAD `945758accf095c634e7a543da73d38160f8b00e2`. 대상은 HAND130 B37 LJ A♣K♥ vs BB 7.3442BB 올인, 현재 테이블 8인/ITM 7인이다. **계약은 5번(콜오프 판단)·8번(조건부 레인지)·13번(ICM)·14번(팟 레이어)·17번(검증) 공용 명세이며, 전략 엔진에 아직 적용하지 않았다.** 고정 임계값, AA 포함 하한, 새 경험상수를 추가하지 않는다.

## A. W5 차이 원인 — 정적 감사 수식 오류 확정

현재 `preflop.tighten_defend_widths_for_raise_level(tp,tot,level=2)`에서 `lt=LEVEL_TIGHTEN[3]=0.34`:

```python
tp *= lt                   # 여기서 tp는 즉시 0.006011499183581489로 갱신
tot = tp + (tot-tp)*(lt*0.8)  # 이 식도 갱신된 tp를 읽음
```

직전 입력은 `tp_old=0.017680879951710263`, `tot_old=0.04515237291693793`. 따라서

- 올바른 실행 순서: `tp_new=0.006011499183581489`; `W5=tp_new+(tot_old-tp_new)*0.272=0.016657816839054443`. 이전 대화 추적 `W5=0.0166578`과 표시 자릿수 기준 일치(차이 `+0.000000016839054443`).
- 과거 정적 감사의 실수: `tp_new+(tot_old-tp_old)*0.272=0.013483745270123415`. `tp *= lt`를 미반영하고 감소 전 공격폭을 다시 뺐다.
- 두 결과 차이 `0.003174071568931028`의 항등식: `tp_old*(1-lt)*(lt*0.8)`. 인지나 배포 버전 때문이라는 가정이 필요 없다.
- 정확한 legacy 원시 cap: `0.016657816839054443 * 0.22 * 2.6 * (1-0.18*0.1318368) / 3.465325 = 0.0026843541110758663` = `0.2684354111075866%`; 마지막 `max(0.005, …)` 때문에 실제 cap `0.005`.

### A.1 상태별 증거 수준

| 범주 | 확인값/설명 | 재현성 등급 |
|---|---|---|
| 원 HAND130 보존 로그 | `legacy_cap=.005`, `hand_pct=.0302`, `fold`, `layer_effective_equity=.63182`, `icm_required_equity=.630692`, `gate_p=.439355`, `roll=.664054` | 보존된 원자료의 **결과 필드** |
| 이전 대화 보고 | `W5=.0166578` | 이전 계산 보고. **원 HAND archive에서 W5 중간 telemetry가 직접 저장됐다는 뜻 아님** |
| 현재 소스+저장 base 프로필+중립 exploit | `W5=.016657816839054443` | 함수 순서 독립 검산 + `preflop.defend_thresholds()` 직접 비교를 위한 회귀 테스트 |
| 틸트(실행 중 실제 값) | `play.Hand.axes() -> planning_profile() -> PS.tilted_view()`로 변환되는 경로를 소스에서 확인 | HAND130 원 자료에 실제 `dyn.level`과 변환된 planning profile **미보존** |
| 환경 플래그 | `persona.GTO_MEMORY_V2`, `PREFLOP_REASONING_V3` 기본 OFF. 8max/안테/20.9864BB는 studied defend 범위와 일치하여 두 플래그 ON/OFF도 동일 폭(함수 불변 검증 대상으로 추가) | 당시 실행 환경변수 값 **미보존**; 다른 일반 spot으로 확대 해석 금지 |
| 깊이/좌석수/오픈크기 | B37 재구성은 `bb=20.9864`, `seats=8`, `open_bb=7.3442`, `n_callers=0`, `raise_level=2`. BB RFI=0, MDF는 6BB 이상 포화 | 당시 실제 결정의 공개 맥락과 보존 seed |
| 원 HAND130 실행 SHA | original archive에 당시 프로세스의 strategy/source SHA 식별값 없음. 현재 기준소스 파일 blob SHA 비교는 가능하나 최초 실행 동일성 증명 아님 | **미확인** |

틀린 정적 W5와 이전 W5의 **산술 불일치 자체는 해결**됐다. 그러나 이전 대화 W5가 진짜 당시 런타임 수치였다는 명제까지 확인된 것은 아니다. 기록되지 않은 틸트·읽기·실행 SHA를 0/기본값으로 단정하지 않는다.

### A.2 전체 단계 (기본 프로필)

| 단계 | attack(tp) | continue(tot) | 의의 |
|---|---:|---:|---|
| GTO vs-open prior를 잘못된 vs-3bet 의미에 재사용 | 0.005643000 | 0.031350000 | BB의 `RFI=0`, `DEF_A=.22`, MDF 축소 `.38/.56`, LJ 배수 `.21` |
| 성향/차트기억 원시 | 0.007965585441 | 0.052495575000 | `pf_defend=1.9`, `looseness=10`, `aggression=5.7` |
| 정규화 | 0.011050549970 | 0.072826407931 | `_saturate(ceiling=.8,scale=.55)` |
| 콜러0명 | 0.011050549970 | 0.072826407931 | 변동 없음 |
| 숏스택 | 0.017680879952 | 0.045152372917 | attack×1.6, continue×.62 |
| 레이즈단계2 | 0.006011499184 | **0.016657816839** | attack 먼저×.34, 이후 갱신된 attack으로 continue 재구성 |
| 콜오프 축소 | — | 0.002684354111 | 레벨 콜오프×.22, 보정×2.6, depth factor 0.976269376, BF÷3.465325 |
| 임의 강제 하한 | — | **0.005000000000** | 최종 legacy 판단의 cap |

## B. 경험상수는 도입 의도 ≠ 수치 타당성

1. `DEF_A=.22`, `DEF_B=.68`, `DEF_SEAT[LJ]=.21`: 2026-09-01 `58d64a436bc19c5a4ebf8a3102cbf950f4dc201c`, BB vs open 공개자료 네 점의 경험 근사와 자리별 투영. 개별 숫자/3bet 대응에 대한 수학적 정당성 **없음**. 4-bet 상황에선 `rfi(BB)=0`이 되며 문제 종류부터 잘못됨.
2. `_MDF`(6BB 이상 .38 포화), `_saturate(.8,.55)`: 일반 오픈 방어폭 근사·100% 넘지 않도록 포화. MDF 엄밀 정의 `P/(P+B)`의 응용이나 올인 가격 보정이 아니다; 실제 검증 provenance가 불충분.
3. `short-stack tp×1.6, tot×.62` → `LEVEL_TIGHTEN[3]=.34`와 `*.8`: 콜 몫 감소 및 높은 레이즈 단계 축소라는 의도; 다만 같은 raise/stack 위험이 레인지에 **연쇄 반영**된다. 독립 4-bet conditional range 모델이 아니어서 통계적 정당성 미검증.
4. `CALLOFF_TIGHTEN[3]=.22`, `×2.6`, `(1-.18D)`, `/BF`, `clip [.005,.85]`: 2026-09-01 `ac05c00a620a8963b61424a184c9209fded469b9`에서 별도 올인 경로 도입(기존 CALLOFF_TIGHTEN 표는 그 이전 최초 저장소 기준선부터 존재). 팟오즈, 유효 스택·조건부 레인지에서 이 숫자들이 **도출되지는 않는다**.
5. `LOADING_PROVISIONAL`, `SPREAD`, `_split_concepts`, `_apply_concept_learning_structure`: 인간형 프로필 생성·능력 학습 분포. 기본 콜 가격/에쿼티가 아니며 생성 뒤 변환으로 `pf_defend`/게이트/관측 범위에 간접 영향. 분포 관련 검증 자료와 올인 콜 전략 근거는 분리한다.

**중복 효과와 중복 '의미'를 구분:** 물리적으로 같은 행을 두 번 곱한 코딩 버그가 증명된 것은 아니다. 하지만 `DEF_SEAT` + 숏스택 축소 + `LEVEL_TIGHTEN` + `CALLOFF_TIGHTEN` + BF 폭 나눗셈은 서로 독립적으로 적합한 조건부 prior가 아닌데도 같은 continue/call 집합을 반복 축소한다. BF는 필요 승률에서 해석해야지 레인지 폭을 나누는 것과 수학적으로 동일하지 않다.

## C. 5번 담당 재사용 계약: `calloff_evidence_v1` (설계 확정, 구현은 별도)

### C.1 질문 및 범위

**콜/폴드만 합법인 최종 올인 대응**: 상대 올인, `can_raise=False`, 추가 `call_cost>0`, 더 이상 행동할 대상 없음. 합법 리레이즈/뒤 좌석 위험/콜드 4bet/다인원 재레이즈는 계약의 `pure_calloff` 조건을 만족하지 않으며 다른 정책으로 분기하되 동일 가격·레이어 producer는 재사용할 수 있다.

입력 단위: 칩(정수 우선)과 [0,1] 무차원 확률을 절대 혼용하지 않는다. BB값은 표시/전략 맥락용이며 콜 가격 계산에는 변환된 정확한 칩을 사용한다. `hand_pct` 또는 `defend_width`는 **계산 계약의 필수 입력이 아니다**.

**최소 필수 입력**

| 필드/원천 | 형식·불변 조건 | 생산자·참고 |
|---|---|---|
| `state_id`, `source_sha`, `player_id`, `street`, `action_index` | 판단 사건 식별, 출처 추적. `source_sha` 미기록이면 null | `session.HandRun`, 17번 |
| `hero_cards`, `public_actions`, `actor_pos`, `original_opener`, `current_aggressor`, `raise_level` | 공개 액션 역사와 조건. `original_opener`≠`current_aggressor` 가능 | `session`·`plan` |
| `hero_stack_remaining`, `opponent_contributions`, `ante_dead_chips`, `folded`, `allin`, `can_raise` | 칩 단위, 0 이상. 상대의 매칭 안 된 초과 베팅 금액을 이길 돈에 포함하지 않음 | `round`·`session._project_call_layers` |
| `call_cost`, `projected_pot_layers` | `call_cost=min(tocall,hero_remaining)`; 각 layer에 `amount`, `eligible_seats`, `hero_eligible` | `session._project_call_layers` |
| `opponent_ranges`, `range_meta` | 개인 observer 시점의 **액션·사이즈·스택 조건부 레인지** 및 provenance, dead-card removal, 가중 콤보. 상대의 비공개 실제 홀카드 사용 금지 | `session._preflop_perceived_range`, 8번 |
| `layer_equities` | 각 hero-eligible layer의 `idx`, `equity`∈[0,1] 또는 null, `complete`, `missing_ranges`, `sims`, `seed`; 평균 및 tie share 포함 | `session.layer_equities_by_pot_layer` |
| `objective_bf`, `perceived_bf`, `payout_model_id` | BF ≥1(해당 근사 계약). `objective_bf=Hand.bf`, `perceived_bf=persona.icm_bf`. 실제 ICM utility가 있으면 별도 model | 13번·`icm.py` |
| `calculation_accuracy`, `application_skill`, `gate_seed` | 개인의 주관적 계산/적용 능력은 **객관 가격·레이어 에쿼티 생산자와 분리** | `persona.calc_noise`, `pf_defend_exact_calc_gate`; 5번이 정책 소유 |

### C.2 결정적인 수학 관계(새 계수 없음)

```text
eligible_layers      = [layer for layer in projected_layers if hero_eligible]
contestable_after    = Σ amount[layer]
gross_return         = Σ equity[layer] × amount[layer]  # tie share 포함
chip_call_EV         = gross_return − call_cost
effective_equity     = gross_return / contestable_after
pot_before           = contestable_after − call_cost
chip_required_equity = call_cost / contestable_after
bf_required_equity   = (BF × call_cost) / (pot_before + BF × call_cost)
```

`BF=1`일 때 `bf_required_equity == chip_required_equity`는 정확한 항등식이다. BF 모델은 개별 대회 ICM payout utility 전체를 다시 계산한 **정확 달러 EV**가 아니라 현행 T2의 scalar approximation이다. 완전한 payouts/스택 분포가 사용 가능하면 진짜 ICM 반사실 콜/폴드 utility를 별도로 출력해 검증한다. 다수 레이어의 각기 다른 상대/ICM 위험에 단일 BF를 적용하는 모델 오차를 기록한다.

- `complete=False` 또는 필수 레인지·equity 미확보 → `decision_status='insufficient_evidence'`, 계산 결과 숫자·콜/폴드를 만들어내지 않는다.
- `complete=True` → 반드시 `point_estimate`와 `sims/seed/range_source`를 함께 전달한다. 특히 문턱과 가까운 표본은 bootstrap/독립시드·조건부 레인지 sensitivity를 요구한다. 불확실성을 숨겨 임의로 call/fold 하지 않는다.
- **실제 행동 정책(5번 소유)**에서만 `application_skill`, `perceived_bf`, 계산 노이즈·지식/기억을 적용한다. 게이트 미통과를 무근거 `pf_rank <= .005`로 대체하는 것은 승계 가능한 수학 모델이 아니다.
- 로그: `producer_complete`, `source_sha`, `range_provenance`, `sims`, `objective_required`, `perceived_required`, `equity_margin`, `gate_roll`, `selected_action`, `missing_evidence`를 별도 기록한다.

### C.3 HAND130 로그 기반 계약 예시(각 숫자 원자료에서 반올림)

```json
{
  "contract": "calloff_evidence_v1",
  "source_sha": null,
  "actor_pid": 37,
  "actor_pos": "LJ",
  "original_opener": "LJ",
  "current_aggressor": "BB",
  "raise_level": 2,
  "can_raise": false,
  "pure_calloff": true,
  "call_cost_chips": 53442,
  "contestable_after_call_chips": 161884,
  "pot_before_chips": 108442,
  "opponent_range_source": "standard_preflop_range:3bet",
  "opponent_range_combos": 288,
  "complete": true,
  "layer_equities": [
    {"idx": 0, "amount": 25000, "equity": 0.62125, "sims": 800, "seed": 2987020386},
    {"idx": 1, "amount": 136884, "equity": 0.63375, "sims": 800, "seed": 3016243797}
  ],
  "gross_return_chips_logged": 102281.485,
  "call_chip_ev_logged": 48839.485,
  "effective_equity_logged_rounded": 0.63182,
  "chip_required_equity": 0.33012527488819154,
  "objective_bf": 3.465325,
  "objective_bf_required_equity": 0.6306922944416353,
  "perceived_bf_logged": 1.369799,
  "potodds_noise_logged": 0.65,
  "gate_probability_logged": 0.439355,
  "gate_roll_logged": 0.664054,
  "observed_final_action": "fold",
  "objective_equity_margin_point_estimate": 0.0011277055583647222,
  "source_certainty": "archive_outcome_and_source_based_reconstruction_not_live_w5_trace"
}
```

참고: 보존된 `effective_equity=0.63182`는 반올림값이라 이를 경합팟에 재곱한 EV는 `48839.485`와 몇 십분의 1칩 차이가 난다. **원본 `gross_return`을 다시 계산한 값으로 덮어쓰지 않는다.**

## D. 검증·회귀·수정 범위

- `tools/verify_hand130_part2.py`: 현재 전략 함수를 불러 base-profile W5/원시 cap/최종 cap, 잘못된 연산 반례, 온오프 플래그, 틸트 sensitivity, ICM 가격, 저장된 결과와 비교한다. 5번 전략 코드를 변경하지 않는다.
- 검증 사실은 `실제 실행` / `독립 산술` / `GitHub 코드 확인` / `기존 로그 검토`로 나눠 보고한다. CI 워크플로 등록이나 저장만으로 CI PASS 주장 금지.
- `test3`의 기존 기준 HEAD와 새 감사 HEAD 사이에서 `preflop.py`, `gto.py`, `persona.py`, `depth.py`, `icm.py`, `session.py`, `plan.py`, `ranges.py` blob SHA가 모두 동일하다는 GitHub 조회를 확보했다. 원 HAND130 실행 바이너리 동일성은 **미확인**이다.
- 최종 행동 전략 교체는 5번 별도 PR과 행동/레인지 posterior/ICM/9-max paired-regression 증거 필요. 임의 하한·AA 특례·추가 shrink 상수 도입하지 않는다.
