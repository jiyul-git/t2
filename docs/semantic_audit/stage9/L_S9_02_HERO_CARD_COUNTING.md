# L-S9-02 — 복원 상대 레인지의 hero 카드 콤보와 '개수/질량' 소비처

기준: 9단계 B3. 이 문서는 추적과 영향 측정이다. **코드는 고치지 않았다.**

## 전제(사용자 지시)

- 관찰자가 복원한 상대 레인지에 hero 카드가 들어간 콤보가 남아 있는 것 자체를 문제로 보지 않는다.
  - 상대의 전략(무엇으로 벳/콜/폴드하는가)은 hero 의 패를 모른 채 정해진다.
  - 따라서 상대 레인지를 액션으로 자를 때는 전체 레인지 위에서 자르는 것이 맞다.
- 문제가 되는 곳은 **hero 패 하나에 조건을 건 양**(이 패로 본 equity, fold 확률, 표본 크기)을 셀 때뿐이다. 그때 hero 카드와 겹치는 콤보가 분모나 문턱에 들어가면 값이 틀어진다.
- 일부 양은 hero 카드와의 상호작용을 일부러 본다(블로커). 이런 양은 걸러내면 안 된다.

## 소비처 분류

| 소비처 | 무엇을 세는가 | hero 카드 콤보 | 판정 |
|---|---|---|---|
| `bot._filter_pool` → equity(`_eq_vs`, `_eq_current`, `equity_vs_combos`, `response_equity` 1단계) | 표본 콤보 | dead 카드로 거른다 | 맞음(KEEP) |
| `plan.relative_strength` | 나를 이기는 질량 | hero+board 로 거른다 | 맞음(KEEP) |
| `ranges.blocker_score` / `blocked_mass_share` / `bot.bluff_nut_blocking` | hero 가 막는 강한 질량 | **일부러 포함** | 의도된 상호작용(KEEP) |
| `ranges._strong_share` / `nut_advantage` / `range_advantage` | 레인지 대 레인지 모양(board 만) | hero 무관 | 레인지 수준 양(KEEP) |
| `_bet_range` / `_call_range` / `_continue_range` / `_check_range` / `narrow` 의 `n*frac` 슬라이스 | 상대 전략의 폭 | 전체 위에서 자름 | **맞음.** 상대 전략은 hero 패를 모른다. hero 쪽 사후 분포는 '전체에서 자른 뒤 hero 와 겹치는 콤보를 빼는 것'이다. 먼저 걸러내고 자르면 상대가 hero 패를 아는 셈이 된다(KEEP) |
| `ranges.narrow_by_actions` 바닥 `len(range_support(base))*_MIN_FRAC`, `_MIN_KEEP` | 표본이 죽지 않게 하는 안전장치 | 전체 수로 셈 | 측정: hero 호환 콤보만 12개 미만인데 전체는 12개 이상인 경우가 2,697건 중 1건. KEEP(기록) |
| `plan.response_equity` 2단계 `len(opp_range) >= 20` | 대체 경로 진입 조건 | 전체 수로 셈 | 1단계 풀이 비어야만 들어간다. 측정 1,267건이 전부 1단계였고 2단계는 0건이다. 이론상 모든 콤보가 hero 와 겹치는 레인지에서만 문제가 된다. KEEP(기록) |
| make_plan / refresh `opp_range_n`, `*_mass`, `thin_call_range_n`, `improved_bluff_call_range_n` | 기록 | 전체 수 | 기록 전용. 판단에 쓰지 않음(KEEP) |
| **`plan._nonvalue_raise_ev_gate` 의 `fold_p = 1 − cont_mass/base_mass`** | **이 hero 패로 본 상대 fold 확률** | **분모와 분자에 포함** | **실제 왜곡. 행동 자격에 영향.** 아래 측정 |

## `_nonvalue_raise_ev_gate` 측정

`tools/l_s9_02_measure.py`, 봉인 baseline sim(시드 11/12, 상한 60, 1,149핸드):

- 측정 실행의 지문이 R2 봉인값과 같다(`e6d8b5e5…`, `c13a5bf4…`). 계측이 진행을 바꾸지 않았다는 뜻이다.
- 비교 대상: 같은 continue range 를 그대로 쓰고, 질량만 hero/board 와 겹치지 않는 콤보로 다시 쟀다. 상대 전략을 자르는 방식은 바꾸지 않았다.

| | 시드 11 | 시드 12 |
|---|---|---|
| 판정이 나온 호출(known) | 102 | 117 |
| 풀에 hero/board 와 겹치는 질량이 있는 호출 | 99 | 114 |
| \|fold_p − hero 조건 fold_p\| 평균 / 중앙값 / 최대 | 0.0212 / 0.0180 / 0.0736 | 0.0211 / 0.0152 / 0.0881 |
| 차이 > 0.02 / > 0.05 | 45 / 11 | 44 / 9 |
| 부호 평균(hero 조건 − 현재) | −0.0113 | −0.0101 |
| allow 판정이 뒤집히는 호출 | **1** | **1** |

- 방향: 현재 식은 fold 확률을 평균 약 1%p **높게** 본다. 그래서 블러프/세미블러프 레이즈 EV 가 낙관적이다.
- 이 gate 는 거부만 하는 구조적 veto 다. 뒤집힘은 모두 '허용 → 거부' 방향이다. 실제 레이즈가 나갔는지는 이후 확률 판정에 달려 있다. 여기서 확인한 것은 **레이즈 자격**까지다.

재현 사례(측정 도구로 결정적으로 재현된다):

| 시드 | street | hero | board | fold_p 현재 → hero 조건 | EV 현재 → hero 조건 | 풀 support 전체 / 호환 |
|---|---|---|---|---|---|---|
| 11 | flop | 9c Kh | Kc Ac 5c | 0.2282 → 0.2049 | +131.7 → −24.2 | 242 / 193 |
| 12 | flop | Jh Ac | Ks Tc 2h | 0.3067 → 0.2398 | +214.9 → −218.1 | 128 / 103 |

영향 경로:
1. `act_with_plan` → `decide_response` 의 `_nv_gate`(블러프 재레이즈, 세미블러프 레이즈, giveup 이탈 레이즈)
2. 체크레이즈 경로의 `_g_ckr`

두 경로 모두 `gate.allow` 에서 갈린다.

**처리**: B3 구조분리 기준점(20e206f7)에서는 고치지 않았다. 이후 B3 통합에서 판정하고 적용했다. 슬라이스는 지금처럼 전체 레인지 위에서 하고, 분모와 분자 질량만 hero/board 와 겹치지 않는 콤보로 잰다(`ranges.range_mass_live`). ledger 'B3 통합' 절 참고.
