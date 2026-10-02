# A. R2_QUANTITY_SEPARATION — PCT 소비처별로 실제 필요한 판단량

기준 `test` `d284a9e`. 읽기 전용이며 행동 변화는 없다.

이 문서는 `PCT_CONSUMER_AUDIT.md`(22개 소비처)를 이어받아, 각 소비처가 실제로 필요로 하는 양을 다섯 종류로 분리한다.

- **O** ordering: 핸드 순서만
- **E** equity: 상대 레인지 대비 승률과 가격
- **V** EV: 액션별 기대값 비교
- **F** fold equity: 상대가 접을 확률
- **S** solver prior: 기준 빈도/집합

9-max 완료 자료가 없는 S 는 **MISSING_KNOWLEDGE** 로 표시한다. 새 숫자는 만들지 않는다. 8-max 값은 9-max 에 쓰지 않는다.

## 1. 요약표

| # | 소비처 | 지금 쓰는 양 | 실제로 필요한 양 | PCT 의 올바른 역할 | 9-max 근거 | 상태 |
|---|---|---|---|---|---|---|
| 1 | RFI 진입 `open_decision` | O + rfi 폭 | O + S(RFI 폭) | 순서(유지) | 공개 9-max RFI 집계: 비블라인드 25/28칸 ±0.024 | 유지 |
| 2 | 오픈 형태(레이즈/쇼브) `open_form` | O 대역 | V(쇼브 vs 레이즈) = F + E(콜당했을 때) | 후보 순서 | DB 첫 진입 쇼브 4~20bb(near). 레이즈 선택지가 있는 트리는 없음 | 분리 대상. 쇼브/레이즈 혼합 빈도는 MISSING_KNOWLEDGE |
| 3 | 림프 `limp_p` | O 대역 | 이론형 S(숏스택 림프). 습관형은 인간 습관 | 대역(습관형) | 없음 | 이론형 MISSING_KNOWLEDGE. 습관형 유지 |
| 4 | iso 진입 | O + 오픈 폭 × iso | O + S(iso 폭) | 순서(유지) | 없음 | iso 폭 MISSING_KNOWLEDGE |
| 5 | vs-open 계속 집합 | O + tot | O + S(디펜스 폭) | 순서(유지) | 없음(비올인) | 폭 MISSING_KNOWLEDGE(출처 미상 값 유지, 변경 금지) |
| 6 | vs-open 3벳 | O 상위 슬라이스 + tp | S(3벳 집합/빈도) + 동기·증거(아래 3절) | **후보 순서만** | 없음 | 구조 분리 대상. 빈도 MISSING_KNOWLEDGE |
| 7 | 콜 구간 (tp,tot] | O 중간 슬라이스 | S | 순서 | 없음 | 6 에 종속 |
| 8 | 프리미엄/슬로플레이 | O 최상단 | O | 순서(유지) | — | 유지 |
| 9 | 핫존 리쇼브 | O + 휴리스틱 폭 + 선형 확률 | V = F + E(콜당했을 때) + 가격/스택 + 뒤 좌석 | **후보 순서만** | 없음(비올인 오픈 대상) | 구조 분리 대상(2절). 빈도 MISSING_KNOWLEDGE |
| 10 | vs-3bet | 위치를 바꾼 vs-open prior × LEVEL_TIGHTEN | S(vs-3bet) + E(가격) | 후보 순서 | 없음 | MISSING_KNOWLEDGE(구조 명시) |
| 11 | 4벳/cold 4벳 | LEVEL_TIGHTEN + 증거층 | S(4벳) + E + F + B | 후보 순서 | 없음 | MISSING_KNOWLEDGE(구조 명시) |
| 12 | 콜오프 legacy cap | O ≤ cap | 경로마다 다름(`CALLOFF_PATH_AUDIT.md` 3절) | 없음(계산하지 않는 사람의 기억 차트로 대체) | **DB call-vs-shove 10~20bb** | **DB 근거가 있어 수정 후보** |
| 12a | 커버 스택의 쇼브 대응(뒤 좌석 있음) | vs-open 디펜스 폭 | E + 가격 + 뒤 좌석 위험 | 없음 | DB call-vs-shove(유효 스택 기준) | **수정 후보** |
| 14 | 상대 레인지 구성 open/limp/polar 3벳 | O 슬라이스 | 액션별 S | 순서 | open 만 공개 RFI 근사 | limp, polar 3벳 MISSING_KNOWLEDGE |
| 14a | 상대 레인지: **첫 진입 쇼브** | `'open'` 라벨 → RFI 슬라이스 | S(쇼브 레인지) | 없음 | **DB 첫 진입 쇼브 4~20bb** | **수정 후보** |
| 14b | 상대 레인지: **쇼브에 콜** | 깊은 스택은 vs-open 플랫 구간 | 콜오프 정책(12)과 같은 것 | 없음 | DB call-vs-shove | **수정 후보** |
| 15 | 4벳 사후 레인지 | O 분위 exp 가중, rate = `reads.PRIOR['pf_4bet']` 0.04(출처 미상) | S(4벳 레인지 모양) | 순서 | 없음 | MISSING_KNOWLEDGE |
| 16 | 블로커 최상단 | O | O | 순서(유지) | — | 유지 |
| 17 | 쇼다운 기반 확장 | O 분위 | 관찰 빈도 | 순서 | — | 상대 적응층. R2 범위 밖 |
| 18 | 쇼다운 관찰 | 프리플랍 분위 | 쇼다운 강도 | 없음 | — | exploit 층. 기록만 |
| 21 | 두 번째 순서표 `_pf_score` | 별도 공식 | O | — | — | `PREFLOP_ORDERING_DUPLICATION.md` |

## 2. 리쇼브 — "좋은 패 순서"와 "쇼브가 +EV 인가"가 섞인 지점

현재 코드:
- `preflop.py:756-761` `defend_action_likelihoods` 핫존 분기
- `preflop.py:510` `reshove_range`
- `preflop.py:875-885` `defend_decision` 실행
- `preflop.py:539` `hotzone_pressure`

| 단계 | 현재 식 | 섞인 양 | 분리 후 담당 |
|---|---|---|---|
| 후보 | `r <= rs` (pf_rank) | O | **O 로 유지**: 리쇼브 후보 집합 |
| 폭 `rs` | `(0.055 + 0.011·aggr + 0.35·traits.threebet) × depth_mult(26−bb)/9 × OPENER_MULT[opener]/2.6 × (1.25 블라인드/0.85) × 1/(1+0.55·callers)` | 성향(aggr, threebet 형질) + F 의 대용(오프너 위치, 콜러 수) + 스택(깊이) | 성향 → 이탈층. F → 오프너 perceived range 와 그 콜오프 정책에서 계산. 스택 → 가격·리스크. 위치 표 `OPENER_MULT` 는 L-RA12 과적재(open_form 깊이와 공유) |
| 확률 `p_hot` | `0.30 + 0.60·(1 − r/rs)` | 순서 깊이를 확률로 변환(근거 없음) | MISSING_KNOWLEDGE(빈도). V 판정이 생기면 V>0 인 후보 안에서의 혼합만 남는다 |
| 형태 | `raise_form` 이 쇼브/논올인을 다시 결정 | 핫존 "리쇼브"가 논올인 3벳으로 나갈 수 있다 | 리쇼브 판정과 형태 판정이 서로 다른 질문이라는 점만 명시(행동 불변) |
| 빠진 양 | — | 콜당했을 때 equity, 팟/스택 리스크, 뒤 좌석(아직 행동 전) | 기존 부품: `bot.equity_vs_combos`, `icm.required_equity`, `players_behind_required_equity_premium`, 오프너 perceived range(`opp_ranges`) |
| 오프너 쪽 `hotzone_pressure` | 뒤 스택만 보고 오픈 폭을 축소 | 위협의 F 와 E 가 없음 | 기록만 |

리쇼브 V 의 최소 구성(설계만, 수치 없음):

`EV(리쇼브) = P(오프너 폴드)·팟 + P(콜)·[eq(내 핸드 vs 오프너 콜 레인지)·최종팟 − 투자액]` 에 뒤 좌석 위험을 더한다.

- `P(오프너 폴드)` 와 `오프너 콜 레인지`: 오프너 perceived range 에 그 사람의 콜오프 정책(12번 정리 결과)을 적용해 얻는다.
- 빈도(혼합 비율)는 비올인 오픈→리쇼브 DB spot 이 없으므로 만들지 않는다. **이번 단계에서 리쇼브 행동은 바꾸지 않는다.**

## 3. 3벳 / 4벳 — 코드에서 나눌 네 층

| 층 | 현재 위치 | 내용 | 상태 |
|---|---|---|---|
| (a) 후보 순서 | `defend_action_likelihoods` `w_raise = logistic(r, tp)`, (0, tp] | pf_rank 상위 슬라이스 | O 로 유지 가능. 단 집합 모양 재현율 0.61(8-max 관찰). 후보 이상의 의미를 주지 않는다 |
| (b) 동기/증거 | exploit(`og`, `f2tb`, `fbg`, `tbg`, `tb_polar`, `f2fb`), `_pf_slow`(슬로플레이 기질), `prof_aggr` 형상 `0.55+0.085a`, multiway: eq vs fair share, `bluff_support`(읽기 F, 블로커 몫), locked 가격 게이트 | 왜 공격하는가 | 이미 분리된 부분(multiway)과 섞인 부분(HU exploit 배수)이 공존. baseline 에서 exploit 은 중립 |
| (c) 3벳 prior/빈도 | `gto.threebet_pct`(9-max `TB_SHARE 0.18`, 8-max `_MTT8_ANTE_TB_SHARE`) → `defend_thresholds` → `_saturate` / 콜러 `sqz·0.92^n` / 짧은 스택 ×1.6 | 기준 폭 | 9-max **MISSING_KNOWLEDGE**(출처 미상 값). 정답으로 승격하지 않는다 |
| (d) 4벳 prior | `tighten_defend_widths_for_raise_level`: `LEVEL_TIGHTEN[level+1]` × (c) — 위치를 바꾼 vs-open prior 위에서. 관찰 쪽은 `preflop_reraise_posterior` rate = `reads.PRIOR['pf_4bet']` 0.04 | 3벳 prior 를 줄여 4벳으로 씀 | **MISSING_KNOWLEDGE.** 독립 4벳 지식이 없다는 것을 코드 이름과 주석으로 명시할 대상(행동 불변) |

## 4. 순서로 충분한 곳 (변경 없음)

#1 RFI, #4 iso 진입, #5 계속 집합, #8 프리미엄, #14 open 레인지, #16 블로커 최상단, #19 머니점프 기록.

pf_rank 를 전역적으로 equity 로 바꾸지 않는다. 순서를 쓰는 곳에서 HU equity 순서는 pf_rank 보다 재현율이 낮았다(0.84 vs 0.90).
