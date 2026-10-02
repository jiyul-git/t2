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
