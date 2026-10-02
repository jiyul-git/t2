# KNOWLEDGE_COVERAGE_MATRIX

A=직접 수학·EV, B=learned/solver prior, C=인간 empirical 지식의 출처를 구별한다. 아래 “human”은 **구현된 경험칙**이며 검증된 최상위 플레이어 데이터/학습 파이프라인은 test 생산 경로에서 확인되지 않았다. GTO-inspired scalar table을 검증된 solver combo policy라고 부르지 않는다. 별도 GTO branch 산출물의 존재는 production wiring의 증거가 아니다. 신뢰할 수 있는 provenance/loader 없는 항목은 빠졌다고 명시한다.

| decision family | math/EV (A) | GTO prior (B) | human heuristic (C; unverified provenance) | reasoning | exploit | production wiring |
| --- | --- | --- | --- | --- | --- | --- |
| RFI | depth/position arithmetic; no full action EV | gto.rfi authored width | open_form/limp/size rules | open_decision | behind_reads + money range | ACTIVE |
| limp | price/depth geometry | independent prior missing; rfi skill borrowed | limp_p theory/habit | open_form | limper/behind context partial | ACTIVE |
| iso | depth/price geometry | independent prior missing; RFI-derived width | iso_decision | rank+limpers+reads | limper reads | ACTIVE |
| vs-open call | price, BF; mainly rank threshold | gto.defend_pct authored width | mixed flat/slowplay rules | defend_action_likelihoods | opener read | ACTIVE |
| 3bet | geometry; not full re-raise EV | gto.threebet_pct derived defend share | reraise/hotzone rules | defend_decision | 3bet polar/fold read | ACTIVE |
| vs-3bet | price/layer partial | independent chart missing; LEVEL_TIGHTEN | rank mixed response | defend + multiway routing | f2tb/rate reads | ACTIVE |
| 4bet | multiway equity/price partial | independent solver policy missing | shared attack width/form | multiway_reraise_decision | f2fb and blocker grounds | ACTIVE heuristic |
| cold-4bet | original opener+reraiser joint equity | independent solver policy missing | shared attack width/form | cold_reraise_decision | cold counters exist; limited dedicated downstream | ACTIVE |
| reshove | hotzone stack/geometry; no complete shove EV | independent solver policy missing | reshove_range PCT | defend hot branch | fold response partial | ACTIVE |
| calloff | layer equity EV required share when complete | independent chart missing | legacy PCT fallback | calloff_layer_judgment + skill gate | legacy exploit cap | ACTIVE partial + FALLBACK |
| flop cbet | range/hand equity and advantage | no imported board-family solver policy | texture.cbet_multiplier | make_plan / cbet_freq | street_gap | ACTIVE |
| flop vs cbet | equity, price, BF | missing independent policy | calldown/bias rules | decide_response | line/read/sizing | ACTIVE |
| flop raise | partial optimistic nonvalue EV | missing independent policy | checkraise/value/draw rules | checkraise_decision / decide_response | opp bet/read | ACTIVE |
| turn barrel | equity/rel/draw/blockers | missing independent policy | turn-card/ownership/budget | decide_aggression | street gap | ACTIVE |
| turn probe | equity/draw facts | missing independent policy | checkthrough trigger | decide_aggression | opp_checked_prev/read | ACTIVE |
| turn raise | partial nonvalue EV | missing independent policy | shared late checkraise, semibluff | checkraise_decision / response | read | ACTIVE |
| river value | continue-range equity; partial closing layer EV | missing independent policy | thin-value/overbet/size rules | river_fix + response | street fold/size read | ACTIVE |
| river bluff | blocker/FE; partial EV | missing independent policy | missed-draw conversion | river_fix + aggression | river gap | ACTIVE |
| river bluffcatch | equity/price/BF | missing independent policy | bluffcatch skill/bias | calldown_need + response | line range and sizing reads | ACTIVE |
| multiway | seat-joint equity/rel/adv/blocker | missing independent policy | count damp and target selectors | make_plan + preflop multiway | per-seat and representative mix | ACTIVE, incomplete response tree |
| side-pot | geometry/settlement/layer equity EV | missing | no independent empirical policy | complete closing consumers only | one-active-opponent fold-call model | PARTIAL ACTIVE / SHADOW |
| ICM | exact <=9 stack-share ICM; field BF heuristic | no solver action policy | awareness/survival/pressure rules | icm_bf + money signals | cover pressure/read adjustment | ACTIVE BF + RFI, later money SHADOW |

기본 prior를 계산하는 gto.py에는 RFI/defend/derived 3bet 폭이 존재한다. 실제 postflop 학습 빈도/사이즈 테이블 또는 solver 정책 loader는 없다. `style_sig.json/style_prior.json`은 별도 style-belief 참조이고 production 정책을 학습시키는 데이터가 아니다. telemetry는 출력 경로이며 학습/적응의 입력은 Book 관측이다.

## 재감사(2026-10-02) 보정

위 표에서 바뀌거나 빠져 있던 것만 적는다. A=직접 수학/EV, B=학습/solver prior, C=검증된 인간 empirical 지식(현재 production에 없음), H=작성된 휴리스틱.

| decision family | 보정 내용 | 근거 코드 |
| --- | --- | --- |
| vs-open call / 3bet (9-max) | 보정된 MTT8-ante 디펜스·3벳 share 표는 **seats==8 + ante**에서만 쓰인다. standard/main/lowbuyin(9-max)은 이전 공식(`_MDF`, `DEF_SEAT`, `TB_SHARE`)이다 → 9-max의 B는 "미보정 폭" | `gto._use_mtt8_ante_defense`, `formats` seats |
| RFI (9-max UTG) | `RFI_BY_BEHIND[8]`(9-max UTG)는 주석상 공개 8-max 표 밖이라 유지된 값 | `gto.RFI_BY_BEHIND` |
| reshove / cold-4bet over an all-in | A 추가: 올인 상대 레인지 대비 eq vs 가격 need (`locked_allin_price_gate`, batch 1) — production ACTIVE | `preflop.multiway_reraise_decision` |
| 4bet / cold-4bet 공격 | 근거 = 4bet 폴드 읽기 또는 블러프 숙련×폴드 가능 상대 최상단 블로커 몫. 블로커 순서는 PCT(R2 의존) | `reraise_attack_evidence`, `preflop.preflop_blocker_share` |
| players behind (모든 콜 결정) | 필요 승률 가산 6%p/인, 최대 18%p — H(상수), 프리/포스트 단일 producer | `icm.players_behind_required_equity_premium` |
| flop/turn draw call | 내재 오즈는 H(스택/팟 비 × outs·potodds 숙련, 최대 0.12). 미래 스트리트 EV 모델 없음 | `implied_odds_adjustment` |
| flop raise / turn raise / river raise (exploit) | 상대의 fold-to-raise(전체·스트리트별)는 **추정되지만 소비처가 없다**. 블러프 체크레이즈는 fold-to-bet을 대용하지 않도록 명시적으로 읽기를 안 씀 → exploit 열 "evidence exists, unwired" | `opponent_unconsumed_estimates`, `plan.checkraise_decision` |
| cold-4bet / squeeze (exploit) | cold re-raise 반응, backraise, squeeze 대면 콜 후 폴드 추정치가 소비되지 않음 | 같음 |
| multiway (postflop) | equity는 seat 풀(A), 일부 continue-range 게이트와 blocker_score는 합집합 레인지 — 부분 A | `multiway_representative_union_range` |
| 모든 family의 C | 정상급 플레이어 empirical 데이터는 production 어디에도 연결돼 있지 않다. "human" 표기는 작성된 휴리스틱(H)이다 | — |
