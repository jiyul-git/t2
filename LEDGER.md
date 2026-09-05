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
| ~~`station`~~ | `fold_gap` 의 부호 반전 | — | **제거** (중복 축) |
| `size_gap` | 평균적으로 크게 치는가 | `persona.opp_size_norm` | OK |
| `size_big` | 극단 사이즈 빈도 | `persona.opp_size_norm` | OK |
| `size_river` | 리버 사이즈 | `persona.opp_size_norm` | OK |
| `bluff_gap` | 블러프 빈도 | `plan` (콜다운 문턱) | OK |
| `open_gap` ★ | **기준 대비** 오픈 폭 (−1~+2) | defend(역치), table_pressure | OK |
| `limp_gap` ★ | 림프 빈도 편차 | iso_decision | OK |
| `see_freq/see_line/see_size` | 관측 능력 게이트 | — | 진단용 |

**프리플랍 관찰 소비 (200핸드, 발동률 44.3%)**

| 소비처 | 받는 것 |
|---|---|
| `defend_decision` | `tb_gap` `f2tb_gap` `fb_gap` `f2fb_gap` |
| `raise_form` | 상대 폴드에쿼티 |
| `open_decision` ★ | `table_pressure(behind_reads)` — 뒤 사람들의 3벳 위협·폴드 성향 |
| `iso_decision` ★ | `limper_reads` — 림퍼가 약할수록 아이소 확대 |

**관찰을 기준 대비로 바꿨다.** 예전에는 절대값(VPIP 34%)으로 쌓아
포지션을 구분하려면 자리마다 따로 세야 했고 표본이 그만큼 쪼개졌다.
지금은 그 자리의 기준 오픈 폭(`gto.rfi`)을 같이 누적해 배수로 만든다 —
BTN 40% 와 UTG 40% 가 같은 값이 아니게 된다.

측정 결과: 저바이인 필드는 기준의 **0.76배**로 연다(200핸드, 기회 16088회).
`open_gap` 은 −0.86 ~ +0.73 범위에서 5327/5350 발동.

`table_pressure` 는 **평균이 아니라 최댓값**을 본다. 뒤에 3벳 머신이 한 명만
있어도 좁혀야 하는데, 평균을 내면 나머지가 신호를 씻어낸다
(배수가 0.96~1.03 에 머물렀다. 최댓값으로 바꾸니 0.76~1.05).

**해결됨.** `size_gap`/`size_big`/`size_river` 는 `persona.opp_size_norm` 이
상대의 **자기 기준** 대비로 사이즈를 정규화하는 데 쓴다 —
항상 1.2팟을 치는 사람의 1.2팟은 폴라라이즈가 아니다.
절대 사이즈만 보면 그런 사람 앞에서 늘 과다 폴드한다.

`bluff_gap` 은 `plan` 의 콜다운 문턱에 붙는다. 예전에는 `opp_est['bluff']` 를
날것으로 읽어 **see_line 게이트를 우회**했다 — 라인을 못 읽는 사람도
상대 블러프 성향에 완전히 반응했다.

`station` 은 `fold_gap` 의 부호 반전일 뿐이라 축을 제거했다.
같은 것을 두 이름으로 두면 한쪽만 게이팅되는 사고가 난다.

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
| ~~`icm.icm_pressure`~~ | | | **제거** (bubble_factor 가 비율로 냄) |
| ~~`icm.required_equity`~~ | | | **제거** (`plan.calldown_need`) |
| ~~`icm.is_bubble`~~ | | | **제거** (`field.in_bubble`) |
| ~~`preflop.vs_shove`~~ | | | **제거** (`calloff_cap`) |
| ~~`preflop.depth_band`~~ | | | **제거** (`feel_of`) |
| ~~`bot.act`~~ | | | **제거** (`plan.act_with_plan`) |
| ~~`session.showdown`~~ | | | **제거** (`award_pots`) |
| ~~`persona.sk_tilted` / `err`~~ | | | **제거** (`tilted_view`) |
| `preflop.calloff_cap` ★ | 올인 대면 콜 문턱 | `defend_decision` (올인 분기) | OK |
| `preflop.calloff_decision` | 콜오프 판단 | `defend_decision` | OK |
| `preflop.vs_shove` | 구형. 에쿼티 함수 필요 | — | 미사용 (calloff_cap 로 대체) |
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
| `texture.cbet_multiplier` | `plan.cbet_freq` | OK |
| `texture.turn_card_effect` | `plan.decide_aggression` (배럴) | OK |

---

## E. 레인지 모델

| 요소 | 소비처 | 상태 |
|---|---|---|
| `ranges.preflop_range` | preflop, session | OK |
| `ranges._call_range` | preflop_range 내부 | OK |
| `reads.perceived_range` | plan, session | OK |
| `ranges.range_advantage` | `plan.make_plan` → `cbet_freq` | OK |
| ~~`ranges.strong_shares`~~ | `_strong_share` 래퍼 | **제거** (중복) |
| `ranges.narrow_by_actions` | `perceived_range` | OK. **인자 2개로 분리** |
| `plan.stackoff_plan` | `make_plan` → `decide_size` | OK |
| `barrel_gap` ★ | `narrow_by_actions` (벳 레인지 폭) | OK |

---

## F. 필드 동역학

| 요소 | 소비처 | 상태 |
|---|---|---|
| `field.avg_stack_bb` | live, tourney, view | OK |
| `field_q` | persona, preflop, plan | OK |
| `dynamics.Tilt` ★ | session `_tilt_update`, tourney `self.tilt` | OK |
| `Tilt.on_pot` / `on_result` / `on_fold_after_investing` ★ | session `_tilt_update` | OK |
| `Tilt.note_showdown` / `shown` ★ | session 쇼다운 → runner `adjust_range_by_history` | OK |
| `persona.tilted_view` ★ | `play.Hand.axes()` — 판단 층 단일 진입점 | OK |
| `persona.tilt_decay` / `tilt_direction` ★ | `tilted_view` 내부 | OK |
| `persona.sk_tilted` | — | 미사용 (tilted_view 로 대체. 남겨둠) |

**틸트를 진입점 한 곳에서 반영한다.** 개별 `sk()` 호출부 27곳을 고치는 대신
`axes()` 가 개념 벡터 자체를 깎은 사본을 넘긴다. 판단 층 코드는 그대로이고
새 개념을 추가해도 자동 적용된다. 호출부를 하나 빠뜨리면 그 축만
틸트에 반응하지 않는데, 그런 누락은 드러나지 않는다.
| ~~table_break / adapt_to_hero / observe_hero~~ | legacy_dynamics.py | 삭제 (중복) |

**정정**: 예전 `dynamics` 는 죽어 있지 않았다. `record_pot`/`decay`/`tilted_profile`
은 호출되고 있었으나 `try/except Exception: pass` 안에 있었고, `tourney` 가
`dyn` 을 넘기지 않아 **매 핸드 새 dict 가 만들어져 틸트가 핸드를 넘기지 못했다.**
live 경로만 JSON 으로 유지됐다. `field_remaining` 과 같은 유형의 누락이다.

---

## G. 경로별 차이 — 해결됨

**`context.py` 가 단일 출처다.** 드라이버는 `h.xxx = ...` 로 직접 심지 않는다.

- `tourney` — `self.ctx.update(...).apply(h, strict=True)`
- `fieldsim` / `live2` — `Field.stamp(h)`
- `live` — `_stamp_from_state(st, h)` (JSON 상태 기반이라 별도)

`tools/ctxcheck.py` 가 네 경로를 실제로 구동해 누락을 잡는다.
**문맥 값을 추가할 때는 `context.SPEC` 에만 넣고 이 도구를 돌린다.**

해결 전에는 이랬다:

| 값 | tourney | live | live2 | fieldsim |
|---|---|---|---|---|
| 심는 값 개수 | 8 | 3 | 4 | 2 |

`live`·`live2`·`fieldsim` 에는 `field_q`·`ante`·`payouts` 가 없어
ICM·안테·분산추구가 그 경로에서만 죽어 있었다.
같은 유형으로 세 번 걸렸다 (`field_remaining`, `ante_from`, `dyn`).

`fieldsim.Field._init_runtime()` 도 같은 이유로 만들었다 —
`live2._load_field` 가 `__new__` 로 만들고 속성을 수동 나열해서,
새 속성을 추가하면 복원 경로만 빠졌다.

---

## 대장별 필요 배선 (역색인)

**어떤 대장을 열기 전에 이 표를 먼저 볼 것.**
미룬 배선 중 그 작업에 필요한 것이 있으면 거기서 같이 처리한다.
배선을 빠뜨린 채 그 위에 로직을 쌓으면 나중에 되돌리기 어렵다.

| 열려는 대장 | 먼저 필요한 배선 | 왜 |
|---|---|---|
| ~~**4 — 오픈 사이즈**~~ | ~~`depth_feel`~~ | 선행 배선 완료. 작업만 남음 |
| ~~**4 — 디펜스 레인지**~~ | — | **완료** (`gto.defend_pct`, `pf_defend` 개념) |
| ~~**4 — 오픈 사이즈**~~ | — | **완료** (`open_size_bb`, `open_size` 개념) |
| **4 — 축적형 분산** | `payout_flat`·`reentry` 판독 | 포맷에 값은 있으나 아무도 안 읽는다 |
| ~~**4 — 오픈 쇼브 통합**~~ | — | **완료** (`open_form`) |
| ~~**판단 층 전반**~~ | — | **완료** (`tilted_view`) |
| **6 관찰과 기억** | `Tilt.note_showdown` 호출 | 기록 함수는 있으나 부르는 곳이 없다 |
| **6 관찰과 기억** | `gto.adapt_mult` | 3층 누적 판단. 관찰이 정리되어야 붙는다 |
| **6 — 상대 레인지 추정** | 기준표 대비 관측 | `Book` 이 절대값(VPIP 34%)으로 쌓는다. `gto.rfi` 대비 배수로 바꾸면 표본이 훨씬 적게 든다 |
| **7 리뷰** | `perceived_edge`, 판단 로그 | 상대가 왜 그렇게 쳤는지 되짚으려면 판단 시점 값이 남아야 한다 |
| ~~**포스트플랍 전반**~~ | — | **완료** (`opp_size_norm`, `bluff_gap`) |
| ~~**올인 대면**~~ | — | **완료** (`calloff_cap`) |

---

## 개념 소비 현황 — 36개 전부 읽힌다

**동적 키(`persona.street_concept`)로 읽히는 9개는 grep 으로 안 보인다.**
`sk(profile, PS.street_concept('cbet', street))` 형태라
`sk(profile, 'barrel_turn')` 을 찾는 정규식에 안 잡힌다.
`fold_gap_*` 과 같은 함정이다 — 스캔할 때 매핑표를 같이 봐야 한다.

```
cbet_flop / barrel_turn / barrel_river        cbet_freq
checkraise_flop / checkraise_late             checkraise_decision
thin_value_turn / thin_value_river            decide_aggression
bluffcatch_early / bluffcatch_river           콜다운 문턱
```

`street_concept` 에 매핑은 있었으나 **`'cbet'`/`'barrel'` 키로 부르는 곳이 없어**
앞의 셋이 죽어 있었다. 그래서 '플랍은 잘 치는데 턴에서 멈추는 사람'이
표현되지 않았다 — 스트리트 구분이 상수표로만 되고 전원 공통이었다.

| 개념값 | flop | turn | river |
|---|---|---|---|
| 2 | 92% | 80% | 54% |
| 9 | 95% | 95% | 73% |

## 미배선 목록 (한꺼번에 처리)

### 오늘 새로 만든 것 — 전부 미배선

| 대상 | 있어야 할 자리 |
|---|---|
| ~~`depth.depth_feel`~~ | **배선 완료** — `preflop.feel_of` 가 단일 진입점 |
| ~~`depth.lookahead_hands`~~ | **배선 완료** — `context.erosion_per_hand` 로 전달 |
| `gto.adapt_mult` | 3층 누적 판단. 대장 6 의존 |
| ~~`persona.perceived_edge`~~ | **배선 완료** — `feel_of` 가 방향축으로 씀 |
| ~~`stack_decay` 개념~~ | **배선 완료** — 침식 예측에 사용 |

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

## 개념 검증 사례 #1 — 쇼다운 가치의 이분법 (2026-09-05, 핸드 #25)

A♠T♣ / K♥2♦2♣ / 4-way / SB OOP / rel 0.62 / eq 0.156 → `giveup` → check
이후 BTN 28,000 레이즈에 fold. 결과적으로 BTN 은 92(트립스)였다.

| 단계 | 판정 | 이유 |
|---|---|---|
| ① 상황 | 정상 | 4-way K22 OOP 에서 AT 체크는 합리적 |
| ② 개념 | 보완 필요 | multiway / OOP / SDV / bluff viability 가 핵심 |
| ③ 계획 | **문제 있음** | '쇼다운 가치 없음'이라는 근거가 부정확 |
| ④ 실행 | 정상 | check(p=0) → 저항 시 response 로 fold, 일관적 |

**행동은 맞았는데 그 행동을 만든 사고 과정의 설명이 틀렸다.** A-high 는
쇼다운 가치가 0 인 핸드가 아니라 **낮지만 존재하는** 가치다. 무료로
쇼다운까지 가면 QJ/JT/QT 를 이긴다.

현재:  쇼다운 가치 없음 → giveup
바람직: 낮은 SDV + multiway + OOP + 보드/레인지 → 블러프 EV 낮음 → check

`rel 0.62` 와 `eq 0.156` 의 괴리는 모순이 아니다. rel 은 상대 레인지 대비
상대적 강도(QJ/JT/98/77 등을 이김)이고 eq 는 3명 상대 실제 승률이다.
문제는 rel 0.62 를 계산해놓고 설명에서 '쇼다운 가치 없음'으로 뭉갠 것.

**향후**
- `showdown_value` 를 0/1 이분법이 아니라 연속값으로
- multiway / OOP / fold equity 가 계획 판단에 연결되어야 함

지금은 수정하지 않는다. 개념을 조금씩 붙이며 실전으로 검증하는 순서를 지킨다.

### 별도 버그 트랙 (판단 품질과 무관)
- 핸드 #22: `블러프 계획 실행(107%)` — 확률이 1.0 을 넘어 표시됨. 표시인지 계산인지 미확인
- 핸드 #51: 계획이 블러프→밸류로 전환됐는데 `why` 에 블러프 사이즈 사유가 잔류. why 가 street-local 이어야 한다는 사례
- 재생 경로에 `trace` 없음 / `range_adv`·`nut_adv` 스트리트 미갱신

## 개념 검증 사례 #2 — 트랩 실행은 정상, 계획 상태 표현이 결함 (핸드 #39)

K♦A♠ / 7♣2♠K♣ / BB vs BTN 헤즈업 / rel 0.97 eq 0.891 / SPR 6.2

```
idx 0  plan=trap          check   why: 넛급 + 상대 벳확률 46% · 취향 4.2 · 수렴 82% → 함정(29%)
       BTN bet 1,800
idx 1  plan=value_3street raise 13,700   trace(response): 밸류 레이즈(55%, x1.53)
       BTN fold → 19,300 획득
```

| 단계 | 판정 |
|---|---|
| ① 상황 | 정상 — AK 탑페어를 체크로 벳 유도 |
| ② 개념 | 정상 — 트랩 판단이 상대 벳확률(46%)을 실제로 고려 |
| ③ 계획 | 정상 — 숨김 → 유도 → 밸류 추출이 계획에 반영 |
| ④ 실행 | 정상 — 계획대로 체크 후 체크레이즈 |
| **최종** | **정상** |

`trap_judgment` 를 '발상(trap)보다 실행(checkraise)이 실력을 가른다'로
고친 경로가 실전에서 작동하는 것을 처음 확인.

**별도 결함 — 계획 상태/로그 모델링**
같은 계획의 2단계(숨기기 → 올리기)인데 `trap` → `value_3street` 로 이름이
갈려 기록만 보면 계획이 바뀐 것처럼 보인다. `intent_act` 도 `check` 로 남아
더 헷갈린다. 계획 생성 오류가 아니라 **상태 표현 문제**.

**기술부채 재확인**: `nut_adv -0.02` / `range_adv -0.08`. AK 탑페어 톱키커인데
레인지 우위가 음수이고 K 가 떨어진 뒤에도 그대로다. 핸드 #9 의 스트리트
미갱신과 동일 원인으로 보인다. 이번 판정을 뒤집을 정도는 아니나 점검 대상.

## 개념 검증 사례 #2 — 트랩의 2단계가 다른 계획으로 기록됨 (핸드 #39)

K♦A♠ / 7♣2♠K♣ / BB / heads-up / rel 0.97 / eq 0.891

```
idx 0  plan=trap          check   why: 넛급 + 상대 벳확률 46% · 취향 4.2
                                       · 수렴 82% → 함정(29%) [리딩 59%]
       BTN bet 1,800
idx 1  plan=value_3street raise 13,700   trace kind=response: 밸류 레이즈(55%, x1.53)
```

| 단계 | 판정 |
|---|---|
| ① 상황 | 정상 — AK 탑페어를 체크로 상대 벳 유도 |
| ② 개념 | 정상 — 트랩 판단이 상대 벳확률(46%)을 실제로 반영 |
| ③ 계획 | 정상 — 숨김 → 유도 → 밸류 추출이 계획에 연결됨 |
| ④ 실행 | 정상 — 계획대로 체크 후 체크레이즈 |
| 최종 | **정상** |

`trap_judgment` 의 '발상보다 실행(checkraise)이 실력을 가른다' 수정이 실전에서
작동하는 것을 처음 확인. BTN(J8s 미스) 폴드로 19,300 획득.

**별도 결함 — 계획 상태/로그 모델링**
실제 사고는 `TRAP → check → 상대 벳 → 밸류 추출` 하나의 흐름인데, 기록은
`trap` 과 `value_3street` 라는 **서로 다른 계획**으로 남는다. `intent_act` 도
`check` 로 고정돼 있어 로그만 보면 계획이 바뀐 것처럼 보인다.
계획 생성 오류가 아니라 표현 문제. 트랩의 2단계를 한 계획의 국면으로 남길 것.

**기술적 결함 — range_adv / nut_adv**
AK 탑페어 톱키커인데 `nut_adv -0.02`, `range_adv -0.08`. K 가 떨어진 뒤에도
플랍 값 그대로. 핸드 #9 의 스트리트 미갱신과 동일 원인으로 보인다.
이번 판정을 뒤집을 정도는 아니나 점검 대상.

## 개념 검증 사례 #3 — 강도 변화에 따른 계획 재평가 (핸드 #54)

T♦A♣ / T♠Q♣4♦ → T♥ / 3-way / BB / FISH

```
flop  showdown       rel 0.79 eq 0.446 made 1   check 의도 → 저항에 call 3,000
                     response: eq 0.440 vs 체감 need 0.254 (실제 0.263)
turn  value_3street  rel 1.00 eq 0.862 made 3   raise 18,200
                     why: turn: 강도 상승(rel 1.00, made 3) → 밸류 전환
                     response: 밸류 레이즈(45%, x0.82)
```

| 단계 | 판정 |
|---|---|
| ① 상황 | 정상 — 플랍 콜, 턴 트립스 밸류 전환 모두 합리적 |
| ② 개념 | 정상 — 핸드 강도 변화에 따른 계획 재평가 |
| ③ 계획 | 정상 — showdown → value_3street 전환이 강도 상승과 연결 |
| ④ 실행 | 정상 — 콜 → 밸류 레이즈가 계획대로 |
| 최종 | **정상** |

**FISH 퍼소나는 판정에 영향을 주지 않는다.** '피시가 레이즈했다'가 아니라
'트립스를 맞춰서 레이즈했다'가 정확한 서술. #39 보다 계획 전환이 더 명확하게
검증된 사례. 팟 49,800 획득.

---

## 반복 확인된 시스템 결함 4종 (판단 품질과 무관, 리뷰를 방해함)

세 사례를 거치며 같은 결함이 반복 관측됐다. **판단은 정상인데 기록이
그것을 정확히 표현하지 못해, 리뷰할 때마다 오독 위험이 생긴다.**

| # | 결함 | 관측된 핸드 |
|---|---|---|
| 1 | `intent_src` 의 확률 표시가 실제 `p` 와 불일치 (100% vs p=0.97, 107%) | #22, #54 |
| 2 | 저항 상황에서 `intent_act` 가 `check` 로 고정 — 실행은 call/raise | #39, #54 |
| 3 | `range_adv` / `nut_adv` 가 스트리트가 바뀌어도 동일 | #9, #39, #54 |
| 4 | `why` 첫 줄에 이전 스트리트 사유 잔존 | #9, #51, #54 |
| 5 | 트랩의 2단계가 서로 다른 계획명으로 기록 | #39 |

2번은 설계상 `decide_response` 가 별도 판단하므로 값 자체는 정상이나,
**기록만 보면 의도와 실행이 어긋나 보인다.** 3번은 세 핸드에서 모두
플랍 값이 그대로라 우연으로 보기 어렵다.
