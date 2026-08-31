# 배선 대장

개념을 만든 곳과 쓰는 곳을 한 장에 적는다.
**새 개념을 붙일 때 여기 줄을 먼저 추가하고, 소비처가 빈 채로 커밋하지 않는다.**

이 파일이 필요한 이유: 이 프로젝트에서 반복된 버그는 로직 오류가 아니라
'만들었는데 아무도 안 쓴다'였다. grep 으로 매번 확인하는 대신 여기서 본다.

상태 표기
- `OK` — 산출·소비 양쪽 확인됨
- `죽음` — 산출만 되고 아무도 안 읽음
- `표시용` — 화면 출력에만 쓰임. 판단에 안 들어감
- `동적` — 키를 문자열로 조립해서 읽음. grep 으로 안 보임 (주의)
- `진단용` — 의도적으로 소비 안 함 (내부 게이트 결과를 밖에서 확인하는 값)

---

## A. 상대 읽기 (익스플로잇)

산출: `persona.read_opponent(prof, opp_est)` — 판단 층 단일 입구
게이트: `see_freq`←attention / `see_line`←range_read / `see_size`←sizing_tell / `use`←adaptability

| 축 | 뜻 | 소비처 | 상태 |
|---|---|---|---|
| `w` | 익스플로잇 가중치 상한 | plan, preflop 외 다수 | OK |
| `fold_gap` | 전체 폴드율 편차 (폴백) | preflop | OK |
| `fold_gap_flop/turn/river` | 스트리트별 폴드율 | `persona.street_gap()` → plan | **동적** |
| `tb_gap` | 상대 3벳 빈도 | preflop (4벳 판단) | OK |
| `f2tb_gap` | 상대가 3벳에 접는 비율 | preflop (3벳 폭, raise_form) | OK |
| `fb_gap` | 상대 4벳 빈도 | preflop (라이트 3벳 억제) | OK |
| `f2fb_gap` | 상대가 4벳에 접는 비율 | preflop (4벳 폭, raise_form) | OK |
| `size_info` | 사이즈가 레인지를 나누는가 | plan | OK |
| `passive` | 상대 수동성 | plan (trap_p) | OK |
| `station` | 안 접는 정도 (= -fold_gap) | — | **죽음** |
| `size_gap` | 평균적으로 크게 치는가 | — | **죽음** |
| `size_big` | 극단 사이즈 빈도 | — | **죽음** |
| `size_river` | 리버 사이즈 | — | **죽음** |
| `bluff_gap` | 블러프 빈도 | — | **죽음** |
| `see_freq/see_line/see_size` | 관측 능력 게이트 | — | 진단용 |

미배선 4축 실제 발화량 (300핸드): `size_gap` 538, `bluff_gap` 593

---

## B. ICM / 상금 구조

| 요소 | 산출 | 소비처 | 상태 |
|---|---|---|---|
| `icm.icm_equity` | Malmuth-Harville | bubble_factor 내부 | OK |
| `icm.bubble_factor` | BF 1.0~4.0 (정확, ≤9명) | `icm.table_bf` | OK |
| `icm.stage_pressure` | 단계 압박. 버블 정점 | `icm.field_bf` | OK |
| `icm.stack_pressure` | 스택 위치. 중간이 최대 | `icm.field_bf` | OK |
| `icm.field_bf` | 곡선 근사 (>9명) | `icm.table_bf` | OK |
| `icm.table_bf` | **BF 단일 진입점** | `play.Hand.bf()` | OK |
| `play.Hand.bf(s)` | 좌석별 BF | session → 프리플랍·포스트플랍 | OK |
| `persona.icm_press` | ICM 압박 **배수** | depth_feel, variance_seek | OK |
| `field.in_bubble` | 버블 판정 **단일 출처** | field, fieldsim, view | OK |
| `persona.icm_signal(bf)` | BF → 0~1 신호 | variance_seek | OK |
| `icm.icm_pressure` | 칩당 상금 한계하락 | — | **죽음** |
| `icm.required_equity` | BF 반영 필요승률 | — | **죽음** |
| `preflop.vs_shove` | 올인 대면 판단 | — | **죽음** |
| `preflop.calloff_decision` | 콜오프 레인지 | — | **죽음** |
| `field.status()['bubble']` | 버블 플래그 | view | 표시용 |

**해결됨**: 예전 `play.Hand.bf` 는 필드를 9명 모델로 축약하고 상금표를
`k = round(9·itm/rem)` 로 잘랐다. 근거 없는 축약이었고 결과가 이랬다 —
`rem>itm*3` 컷오프 계단(181명 1.00 → 180명 1.53), 60자리 상금 대회를
3자리로 계산, 버블(61명 2.03)이 70명(2.66)보다 낮음, 9~40명 구간 평평.
지금은 9명 이하 정확 ICM / 그 위 곡선 근사로 나뉘고 경계에서 연속이다
(10명 2.07 → 9명 2.03). 대회 규모와 무관하다(50~400명 버블 BF 2.47~2.50).

주의: `bf` 를 소비하는 두 곳의 단위가 다르다.
- `plan.py:625` — BF 단위 그대로 (`1.0 + (bf-1)*icm/6`). 팟오즈 식에 넣어야 해서
- `persona.variance_seek` — 0~1 신호 × 개념 가중치

규약은 0~1 이다. `plan.py:625` 는 나중에 맞출 것.

---

## C. 스택 깊이 / 액션 형태

| 요소 | 하는 일 | 상태 |
|---|---|---|
| `preflop.raise_form` | 3벳을 논올인/올인 중 무엇으로 | OK (SPR 기반, 연속) |
| `preflop.depth_band` | bb → micro/short/mid/normal/deep | OK. **계단** |
| `preflop.should_shove` | 오픈을 레이즈/쇼브 중 무엇으로 | OK. **계단** (`bb<12`, `bb<22`) |
| `preflop.in_hotzone` | 12~26bb 하드 경계 | OK. **계단** |
| `preflop.reshove_range` | 짧은 스택 3벳 레인지 폭 | OK |
| `preflop.hotzone_pressure` | 뒤 숏스택 압박 → 오픈 축소 | **죽음** |
| `persona.variance_seek` | 분산 추구 성향 0~1 | OK |

미해결: 오픈 쇼브 결정이 `should_shove` 와 분산추구 두 곳으로 갈려 있다.
스택 25bb 가 그 경계다. `raise_form` 처럼 합쳐야 한다.

---

## D. 보드 텍스처

| 요소 | 소비처 | 상태 |
|---|---|---|
| `texture.texture()` | plan | OK |
| `texture.size_fraction` | plan | OK |
| `texture.cbet_multiplier` | — | **죽음** |
| `texture.turn_card_effect` | — | **죽음** |

---

## E. 레인지 모델

| 요소 | 소비처 | 상태 |
|---|---|---|
| `ranges.preflop_range` | preflop, session | OK |
| `ranges._call_range` | preflop_range 내부 | OK |
| `reads.perceived_range` | plan, session | OK |
| `ranges.range_advantage` | — | **죽음** |
| `ranges.strong_shares` | — | **죽음** |

---

## F. 필드 동역학

| 요소 | 소비처 | 상태 |
|---|---|---|
| `field.avg_stack_bb` | live, tourney, view | OK |
| `field_q` | persona, preflop, plan | OK |
| `dynamics.Tilt` ★ | session `_tilt_update`, tourney `self.tilt` | OK |
| `Tilt.on_pot` / `on_result` / `on_fold_after_investing` ★ | session `_tilt_update` | OK |
| `Tilt.note_showdown` / `shown` ★ | runner `adjust_range_by_history` | 부분 (기록 호출 필요) |
| `persona.tilt_decay` / `sk_tilted` ★ | — | **미배선** (판단 층이 sk 대신 sk_tilted 를 써야) |
| `persona.tilt_direction` ★ | — | **미배선** |
| ~~table_break / adapt_to_hero / observe_hero~~ | legacy_dynamics.py | 삭제 (중복) |

**정정**: 예전 `dynamics` 는 죽어 있지 않았다. `record_pot`/`decay`/`tilted_profile`
은 호출되고 있었으나 `try/except Exception: pass` 안에 있었고, `tourney` 가
`dyn` 을 넘기지 않아 **매 핸드 새 dict 가 만들어져 틸트가 핸드를 넘기지 못했다.**
live 경로만 JSON 으로 유지됐다. `field_remaining` 과 같은 유형의 누락이다.

---

## G. 경로별 차이 (주의)

같은 값이 경로마다 채워지기도 하고 안 되기도 한다.

| 값 | `tourney.py` | `fieldsim.py` | `live.py` |
|---|---|---|---|
| `field_q` | O | O | O |
| `field_remaining` / `field_itm` | O (방금 추가) | O | O |
| `payouts` | X | ? | ? |

`payouts` 가 없으면 `play.Hand.bf()` 가 기본 상금표를 쓴다.
실제 상금 구조와 다르면 BF 가 틀린다.

---

## 대장별 필요 배선 (역색인)

**어떤 대장을 열기 전에 이 표를 먼저 볼 것.**
미룬 배선 중 그 작업에 필요한 것이 있으면 거기서 같이 처리한다.
배선을 빠뜨린 채 그 위에 로직을 쌓으면 나중에 되돌리기 어렵다.

| 열려는 대장 | 먼저 필요한 배선 | 왜 |
|---|---|---|
| **4 프리플랍 — 오픈 사이즈** | `depth_feel` | 사이즈가 깊이에 따라 달라진다. 계단이면 사이즈도 계단이 된다 |
| **4 프리플랍 — 디펜스 레인지** | `depth_feel`, `sk_tilted` | 역치 4곳이 `depth_band` 를 쓴다 |
| **4 — 축적형 분산** | `payout_flat`·`reentry` 판독 | 포맷에 값은 있으나 아무도 안 읽는다 |
| **4 — 오픈 쇼브 통합** | `depth_feel` | `should_shove` 의 `bb<12`,`bb<22` 를 대체할 값 |
| **판단 층 전반** | `sk_tilted`, `tilt_direction` | 지금 틸트는 수치만 쌓이고 행동에 안 나온다 |
| **6 관찰과 기억** | `Tilt.note_showdown` 호출 | 기록 함수는 있으나 부르는 곳이 없다 |
| **6 관찰과 기억** | `gto.adapt_mult` | 3층 누적 판단. 관찰이 정리되어야 붙는다 |
| **6 — 상대 레인지 추정** | 기준표 대비 관측 | `Book` 이 절대값(VPIP 34%)으로 쌓는다. `gto.rfi` 대비 배수로 바꾸면 표본이 훨씬 적게 든다 |
| **7 리뷰** | `perceived_edge`, 판단 로그 | 상대가 왜 그렇게 쳤는지 되짚으려면 판단 시점 값이 남아야 한다 |
| **포스트플랍 전반** | `size_gap`·`bluff_gap`·`station` | 상대 베팅 해석 축들 |
| **올인 대면** | `vs_shove`, `calloff_decision`, `required_equity` | 함수는 완성돼 있고 호출부만 없다 |

---

## 미배선 목록 (한꺼번에 처리)

### 오늘 새로 만든 것 — 전부 미배선

| 대상 | 있어야 할 자리 |
|---|---|
| `depth.depth_feel` | `preflop.depth_band` 소비처 4곳 (82 / 196 / 262 / 281행) |
| `depth.lookahead_hands` | 침식률을 세션이 넘겨야 함 (`hpl`·`blind_mult` 에서) |
| `gto.adapt_mult` | 3층 누적 판단. 대장 6 의존 |
| `persona.perceived_edge` | `variance_seek` 만 씀. `depth_feel` 이 아직 안 받음 |
| `stack_decay` 개념 | `lookahead_hands` 만 씀 (그 자체가 미배선) |

**배선 시 필요한 값**: `field_avg_bb`, `erosion_per_hand`.
전자는 `tourney.field_avg_stack / bb`, 후자는 `blind_mult` 와 `hpl` 에서 나온다.


1. `size_gap` / `size_big` / `size_river` / `bluff_gap` — 상대 베팅 해석
2. `station` — `passive` 와 같은 원천인데 한쪽만 배선됨
3. `icm_pressure` / `required_equity` / `vs_shove` / `calloff_decision` — 올인 받는 쪽
4. `hotzone_pressure` — 뒤 숏스택 압박
5. `range_advantage` / `strong_shares` — 레인지 우위
6. `cbet_multiplier` / `turn_card_effect` — 텍스처 기반 사이징
7. `table_break` / `adapt_to_hero` / `observe_hero` — 필드가 히어로에 반응

## 계단 목록 (연속화 대상)

- `depth_band` 경계 8/15/25/60bb
- `should_shove` 의 `bb<12`, `bb<22`, `hand_pct<=0.55`
- `in_hotzone` 12.0/26.0
- 분산추구의 `band == 'normal'` (25~60bb 창)
