# Strategy -> code cross-check V1

Basis: `POKER_DECISION_MODEL_V2.md`
Updated against current branch: 2026-09-28

| Node | Current implementation | Status |
|---|---|---|
| P1 unopened | `preflop_plan -> open_decision` returns action/size/`pf_seed` | PARTIAL / no unified plan object |
| P2 limpers | `preflop_plan -> iso_decision` | PARTIAL / motive and action still fused |
| P3 facing open | `preflop_plan -> defend_decision` with current reads/stack/price | PARTIAL / no unified response-plan object |
| P4 facing 3-bet | same defend pipeline with recursive `raise_level` | KEEP STRUCTURE / strategy remains shared |
| P5 facing 4-bet+ | recursive raise depth is preserved; defend/calloff path handles higher levels | KEEP STRUCTURE / no depth loss |
| P6 facing all-in | full/incomplete all-in and call-off geometry preserved by rule engine | KEEP RULES / planning object still implicit |
| F1/T1/R1 no wager faced | `update_plan -> intent -> act_with_plan` | CLOSE TO TARGET |
| F3/T3/R3 check then face bet | canonical response context -> checkraise gate or generic response -> response-plan record | DUP CLOSED |
| F4/T4/R4 bet then face raise | `aggressor_backaction` context -> fresh response selection -> response-plan record | KEEP STRUCTURE |
| F5/T5/R5 raise then face re-raise | same recursive context with arbitrary raise depth | KEEP STRUCTURE |
| multiway judgment | per-opponent `opp_ranges` preserved through core equity | MAJOR LOSS CLOSED |
| proactive size | selected in planning layer, then converted by session | PARTIAL / expression shaping still mutates size |
| emotion | production judgment uses tilted planning profile | ARCH MISMATCH |

## Current action-story path

`runner.Round.apply()`
-> raw rule metadata
-> `action_events.postflop_events()`
-> canonical semantic events
-> per-opponent action histories
-> `ranges.perceived_range()`
-> current opponent pools
-> plan/response judgment

## Current response ownership

### check -> face bet
Only the check-raise gate may create a raise for that response node.
Generic response raising is disabled at that node.

### bet/raise -> face raise
Uses ordinary response path with response kind `aggressor_backaction`.

### call -> later face raise
Uses response kind `caller_backaction`.

### cold facing raise
Uses response kind `cold_facing_raise`.

Every response is recorded in `response_plans`.

## Opponent observations now available

Current postflop observation book distinguishes:
- facing bet / fold to bet
- facing raise / fold to raise
- street-specific versions
- c-bet / barrel / delayed c-bet
- sizing
- showdown evidence

## Range behavior after observed actions

- bet and raise are not the same event
- raise first conditions on surviving the wager faced
- repeated raises repeat the same conditional update
- call/continue uses actual incremental price
- full raise / incomplete raise / all-in call / all-in raise remain distinct
- same-street re-raises do not increase barrel count

## Current open mismatches against V2

1. Preflop has no uniform explicit plan object.
2. Tilt still changes judgment inputs because `Hand.axes()` returns tilted profile.
3. Production `shape_size()` can change strategic sizing after the plan selected it.
4. Some consumers still use legacy union range / one main opponent despite per-opponent pools existing.
5. Compatibility fallback paths remain for incomplete/legacy metadata.

## Findings from older versions that are no longer current

CLOSED:
- duplicate check-raise producers
- missing arbitrary re-raise depth
- higher re-raises collapsed into a single generic bet
- all-in call and all-in raise treated the same
- same-street re-raises counted as barrels
- no fold-to-raise observation
- all multiway ranges flattened before core equity
