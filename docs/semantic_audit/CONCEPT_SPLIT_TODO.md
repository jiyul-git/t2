# CONCEPT_SPLIT_TODO

기준: 2026-10-05 `test`

현재 Human Model에서 **서로 다른 판단 능력이 하나의 숙련치/개념을 공유하는 문제**를 따로 추적한다.
이 문서는 구현 지시가 아니라 분리 필요성 메모다. 새 수치나 새 prior는 근거 확보 전 만들지 않는다.

## 분리 필요 항목

1. `checkraise_late` — **PHASE 1 DONE**
   - 의미 경계: 턴은 `checkraise_turn`, 리버는 `checkraise_river`로 분리
   - 기존 생성 프로필: 두 새 키가 없으면 모두 `checkraise_late`로 fallback하여 행동 보존
   - 새 prior/loading/base/spread: 아직 만들지 않음
   - 다음 단계: 실제 모집단에서 turn/river를 독립 생성할 근거와 난이도/분포를 정한 뒤 compatibility fallback 제거 검토
   - 이유: 턴은 세미블러프/드로우가 존재하지만 리버는 드로우가 끝난 별도 판단

2. `bluffcatch_early` — **PHASE 1 DONE**
   - 의미 경계: 플랍은 `bluffcatch_flop`, 턴은 `bluffcatch_turn`, 리버는 기존 `bluffcatch_river`
   - 기존 생성 프로필: 새 두 키가 없으면 모두 `bluffcatch_early`로 fallback하여 행동 보존
   - 새 prior/loading/base/spread: 아직 만들지 않음
   - 다음 단계: 실제 모집단에서 flop/turn을 독립 생성할 근거와 난이도/분포를 정한 뒤 compatibility fallback 제거 검토
   - 이유: 남은 스트리트 수, 미래 액션, 실현 가능성이 다름

3. 플랍 thin value — **PHASE 1 DONE**
   - 조사(소비처 전부): `range_merge` 는 두 곳에서만 읽힌다.
     1. `plan.make_plan` 중간강도 분기 — 팟컨트롤 / 얇은 밸류(`value_2street`) / 쇼다운 선택. 숙련이 높을수록 얇은 밸류.
     2. `persona.street_concept('thin_value','flop')` — 플랍 2스트리트 확률(`middle_value_two_street_probability`)과 플랍 밸류벳 빈도(`decide_aggression`).
     둘 다 "중간 강도를 얇은 밸류로 칠 줄 아는가"라는 같은 능력 → 의미 이름 `thin_value_flop`.
   - 의미 경계: `street_concept('thin_value','flop')` → `thin_value_flop`, `make_plan` 플랍 → `thin_value_flop`
   - 기존 생성 프로필: `thin_value_flop` 키가 없으면 `range_merge` 로 fallback(ALIAS) → 행동 동일(기준 하네스 지문 불변)
   - 남긴 것: 보드 변경으로 턴/리버에서 `make_plan` 을 다시 세울 때는 phase 1 에서 기존 `range_merge` 를 그대로 쓴다. 이 경로가 `thin_value_turn/river` 를 써야 하는지는 phase 2 에서 판단(지금 바꾸면 행동이 바뀜)
   - 새 prior/loading/base/spread: 만들지 않음
   - 검증: `tools/verify_thin_value_flop_split.py`(매핑, fallback 동일, 독립 override, 소비처 두 곳 counterfactual — 플랍만 바뀌고 턴 불변, 새 prior 없음)

4. 프리플랍 3-bet — **PHASE 1 DONE**
   - 조사: `pf_defend` 는 (a) `traits_of()['threebet']` 의 숙련 입력(코드 주석이 스스로 'proxy, 전용 3벳 숙련 아님'), (b) 디펜스 차트 기억(`gto_knowledge('defend')` → `defend_thresholds` 의 3벳 폭 tp·전체 폭), (c) 정확한 콜오프 계산 게이트(`pf_defend_exact_calc_gate`)에 쓰인다.
   - 판정: (a)만 '3벳 판단 숙련'의 proxy. (b)는 3벳과 콜이 한 차트에 있는 디펜스 차트 기억, (c)는 계산 실행 게이트라 다른 질문.
   - 의미 경계: `traits_of()['threebet']` → `pf_threebet`(관찰 통계 키 `pf_3bet` 과 다른 이름). 소비: 핫존 리쇼브 폭(`reshove_range`), 관찰자 3벳 레인지(`ranges`)
   - 기존 생성 프로필: `pf_threebet` 없으면 `pf_defend` fallback → 행동 동일(기준 하네스 지문 불변)
   - 남긴 것: 디펜스 차트 안의 3벳 구간 기억(b)을 따로 볼지는 phase 2 (차트를 3벳/콜로 나눠 기억하는 사람을 표현할지 결정 필요)
   - 검증: `tools/verify_pf_threebet_split.py`

5. limp / iso — **PHASE 1 DONE**
   - 조사: 림프는 `limp_theory_knowledge` 가 RFI 차트 기억(`gto_knowledge('rfi')` = `pf_range`)을 그대로 씀. 아이솔은 `iso_entry_threshold` 가 오픈 폭 `_open`(차트 기억 `pf_range`) × iso 성향 배수로 파생. 습관적 림프/아이솔 성향(`traits_of` limp/iso)은 기질 식이라 숙련 proxy 아님.
   - 의미 경계: `limp_theory`(숏스택 이론 림프 지식), `iso_raise`(아이솔 폭 파생의 차트 기억 입력)
   - 기존 생성 프로필: 둘 다 없으면 `pf_range` fallback(`concept_knowledge` 는 `gto_knowledge` 와 같은 식) → 행동 동일(기준 하네스 지문 불변). `iso_raise` 는 명시 값이 있을 때만 폭 파생 입력을 바꾼다.
   - 남긴 것: 독립 iso prior(오픈 폭 파생이 아닌 아이솔 고유 기준)는 근거 확보 전 만들지 않음
   - 검증: `tools/verify_limp_iso_split.py`(기질 방향이 0 이면 기억 크기가 폭에 영향이 없어 루즈 기질로 측정)

6. `range_read` — **PHASE 1 DONE**
   - 조사(소비처 전수, 주석·생성 구조 제외):
     | 소비처 | 역할 | 새 의미 이름 |
     |---|---|---|
     | `ranges.perceived_range` / `perceived_facing_bet_response` / `perceived_continue_range` (액션으로 레인지 축소 정확도) | 복원 | `range_reconstruction` |
     | `persona.bias('bluff_fear')` (`interpret_bluff_threat_bias` 의 `line_interpretation_skill`) | 해석 | `line_interpretation` |
     | `persona.read_opponent` 의 `see_line`(스트리트 구분·블러프 성향 감지) | 해석 | `line_interpretation` |
     | `reads.obs_from_profile` 관찰 정확도 | 해석 | `line_interpretation` |
     | `preflop` 다인원 근거 적용(`multiway_evidence_application_capacity` 의 `read_application_skill`) | 적용 | `read_application` |
     | `money_pressure.actor_from_profile` 압박 근거 적용 | 적용 | `read_application` |
     | `persona.bias('overpair_love')` (레인지를 못 읽어 오버페어 과대평가) | 미분류 | `range_read` 유지 |
     | `persona` 자기 실력 자각(`aware`) | 미분류 | `range_read` 유지 |
     | 학습 선행 구조(`LEARNING_PREREQUISITES`, 난이도, 고숙련 압축) | 생성 구조 | `range_read` 유지 |
   - 기존 생성 프로필: 세 키가 없으면 모두 `range_read` 로 fallback → 행동 동일(기준 하네스 지문 시드 11·12 불변)
   - 남긴 것: 미분류 2곳의 귀속, 세 역할의 독립 생성(prior·난이도·선행 구조)은 phase 2
   - 검증: `tools/verify_range_read_split.py`(fallback 동일, 각 역할 override 가 자기 소비처만 움직임, 새 prior 없음)

## 원칙

- 기존 행동을 먼저 보존한 채 의미 경계부터 분리한다.
- 새 숙련치의 loading/base/spread는 근거 없이 임의 생성하지 않는다.
- 분리 후에는 same-state counterfactual + frozen regression으로 영향 측정한다.
- GTO/reference 브랜치 정리와 이 작업은 분리한다.

## PHASE 2 — 분할 키 독립 생성 (2026-10-06, 사용자 요청·위임)

phase 1 에서 의미만 나누고 부모 값을 빌려 쓰던 11개 키를 독립 숙련치로 생성한다(`persona.SPLIT_CONCEPTS`).

```
child = mean_p + r * (parent - mean_p) + sqrt(1 - r^2) * sd_p * z + offset
z: pid·잠재요인으로 시드한 별도 결정적 난수 (money_jump 와 같은 방식, 공유 rng 불변)
mean_p, sd_p: 부모의 모집단 평균·표준편차(1,000명 측정, SPLIT_PARENT_STATS)
```

| 키 | 부모 | offset | 목표 r | 난이도 | 학습 도움 선행 |
|---|---|---:|---:|---:|---|
| checkraise_turn | checkraise_late | +0.3 | 0.85 | 6.0 | checkraise_flop |
| checkraise_river | checkraise_late | −0.3 | 0.85 | 7.0 | checkraise_flop |
| bluffcatch_flop | bluffcatch_early | +0.3 | 0.85 | 4.5 | potodds |
| bluffcatch_turn | bluffcatch_early | −0.2 | 0.85 | 5.5 | potodds |
| thin_value_flop | range_merge | +0.4 | 0.80 | 5.0 | — |
| pf_threebet | pf_defend | −0.2 | 0.70 | 5.0 | — (차트 계열) |
| limp_theory | pf_range | −1.0 | 0.60 | 6.0 | — (차트 계열) |
| iso_raise | pf_range | 0.0 | 0.75 | 4.5 | — (차트 계열) |
| range_reconstruction | range_read | +0.2 | 0.80 | 7.5 | pf_range+positional+board_texture+sizing_tell |
| line_interpretation | range_read | 0.0 | 0.80 | 7.5 | range_reconstruction |
| read_application | range_read | −0.3 | 0.80 | 8.0 | line_interpretation |

읽기 3역할은 고숙련 압축(v3) 대상에 추가. 부모 키(checkraise_late, bluffcatch_early, range_merge, range_read 등)는
남은 소비처·fallback 용으로 그대로 생성한다.

1,000명 결과: 기질·기존 37개 개념 전원 불변. 분할 키 표준편차는 부모와 같은 수준(1.91~2.74 vs 2.02~2.99),
부모 상관 0.63~0.86(목표 근처). 선후행 위반 0. 분할 검증기 4개의 `no_new_prior`(phase 1 불변식)는
`split_prior_phase2`(키 존재 + 상관이 목표 ±0.15)로 바꿨다. 첫 시도(독립 편차만 더함)는 상관이 0.93~0.97 로
사실상 부모 복사라 폐기했다.
