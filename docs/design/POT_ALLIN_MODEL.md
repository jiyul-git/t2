# POT / SIDE-POT / ALL-IN MODEL

## 2026-10-02 코드 재감사 동기화

F8은 PARTIAL ACTIVE: pure preflop calloff, complete closing postflop call, no-raise closing river bet-vs-check veto. 일반 sidepot raise tree와 비종결 street 전체 EV는 OPEN. effective-allin v1 조건/threshold는 변경하지 않았다.

현재 근거: [전체 구조](docs/semantic_audit/CURRENT_ARCHITECTURE_AUDIT.md), [개념→함수](docs/semantic_audit/CONCEPT_FUNCTION_REGISTRY.md), [문서 차이](docs/semantic_audit/DOCUMENT_DRIFT.md), [리팩터링·검증](docs/semantic_audit/REFACTOR_AND_VERIFICATION.md). 아래 과거 실험/commit별 증거는 그 시점 기록이며 현재 배포 인증이 아니다.

이 문서는 uncalled excess, effective-all-in, leave-behind, F8 side-pot decision semantics를 통합한다.

## 1. Settlement/legal layer

### Uncalled excess — CLOSED

검증된 규칙:
- HU short-stack call에서 unmatched excess는 반환.
- legitimate side pot은 false return 없음.
- raise 후 fold되어도 matched money는 pot에 남고 unmatched excess만 반환.
- short stack의 contestable-pot view는 도달 가능한 money만 봄.
- tied top contribution은 false return 없음.

`tools/verify_uncalled_excess.py`: 5/5 PASS.

6000-6007 audit:
- field hands 1,608
- aggressive postflop actions 1,467
- engine errors 0
- physical all-in/clamped 118
- non-all-in >=95% own-stack commit 6

uncalled accounting은 near-all-in strategy 자체를 바꾸지 않았다.

## 2. Effective-all-in v1 — CLOSED / ACTIVE RULE

Postflop bet/raise를 actor effective-all-in으로 승격하는 조건:

1. actor가 limiting effective stack:
   `actor_cap <= opp_cap_max`
2. final legal target / actor cap >= **0.90**
3. actor residual / pot after action <= **0.05**

v1 execution mode는 physical shove.

검증:
- `verify_effective_allin_v1.py`: 6/6 PASS
- `verify_allin_raise_rights.py`: 5/5 PASS

OOS 6100-6107:
- aggressive postflop actions 1,445
- classifier/applied 77
- already exact/full 62
- actual near-all-in -> shove promotions 15
- promotion rate 1.04%
- flop 10 / turn 5 / river 0
- pre-v1 commit 90.45%..99.82%
- post-action own SPR 0.0013..0.0444

opponent-effective case는 own-stack commit이 커도 actor shove로 자동 승격하지 않는다.

## 3. Intentional leave-behind — NOT ENABLED

Exploratory sample에서 ladder-survival candidate가 보였지만 broad cluster는 아니었다.

Confirmatory OOS 6200-6215:
- 16 tournaments
- 3,496 field hands
- 2,885 aggressive postflop actions
- effective-all-in promotions 15
- locked leave-behind candidates **0/15**

따라서:
- 1BB residue constant 추가 금지
- locked selector를 OOS 결과 보고 완화 금지
- BF-containing self-preservation을 execution selector에 중복 사용 금지
- effective-all-in v1은 계속 physical shove

leave-behind는 future optional execution mode로만 보존.

## 4. F8 main/side-pot decision semantics — PARTIAL ACTIVE / GENERAL TREE OPEN

Settlement와 legal contribution plumbing은 sound지만 **전략 판단층**은 아직 완전히 닫히지 않았다.

핵심 문제:
- 이미 all-in인 opponent의 money는 pot에 남지만 그 opponent를 equity 계산에서 제거하면 판단 불일치.
- 하나의 scalar `pot_live`는 main/side pot의 서로 다른 eligibility를 표현할 수 없음.
- response EV와 proactive bet/raise EV 모두 layer-specific equity가 필요.

따라서 side-pot 상황은 최소한:
- pot layer
- eligible seats per layer
- hero share/equity per layer
- incremental call/bet가 접근하는 layer
를 보존해야 한다.

F8 plumbing에서 만든 seat-keyed range / layer equity foundation은 유지한다.
남은 것은 이 정보를 plan/response EV에 semantic하게 연결하는 단계다.

## 5. ICM interaction

ICM/BF는 pot-layer semantics를 대체하지 않는다.
BF를 이미 upstream decision threshold에 사용한 뒤 survival logic에서 같은 risk를 다시 넣으면 double count가 될 수 있다.

F8-ICM semantic closure는 OPEN.

## 6. Verification rules

- accounting fix와 strategy policy를 같은 commit/실험에 섞지 않는다.
- actor-effective vs opponent-effective population 분리.
- side-pot fixture는 chip conservation + eligibility + equity + EV를 각각 검사.
- frozen baseline movement는 intentional strategy consumer에서만 허용하고 attribution 필요.

## 7. Historical sources

- `UNCALLED_EXCESS_DESIGN.md`
- `UNCALLED_EXCESS_RESULT.md`
- `NEAR_ALLIN_DESIGN.md`
- `NEAR_ALLIN_FIRST_FIX_RESULT.md`
- `EFFECTIVE_ALLIN_V1_DESIGN.md`
- `EFFECTIVE_ALLIN_V1_RESULT.md`
- `LEAVE_BEHIND_AUDIT.md`
- `LEAVE_BEHIND_AUDIT_RESULT.md`
- `LEAVE_BEHIND_SHADOW_DESIGN.md`
- `F8_SIDE_POT_DECISION_AUDIT.md`
