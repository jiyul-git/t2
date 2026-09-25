# Concept / wiring full audit — result

Branch: `chatgpt/concept-wiring-audit-20260926`

## Static inventory result

Final v2 scan:

- declared strategic concepts: 37
- core-runtime static references: 119
- parse errors: 0
- zero core-runtime consumers: **0**

No declared concept is completely unreferenced in the audited runtime set.

Static reference count is not treated as proof of reachability or behavioral materiality.
Single-function concepts are often intentionally centralized.

## Status map

### Wiring present — broad or multi-site

These have multiple explicit consumers or a clearly shared role:

- bluff
- semibluff
- barrel_river
- checkraise_flop
- checkraise_late
- bluffcatch_river
- thin_value_turn
- thin_value_river
- overbet
- stackoff
- outs
- potodds
- spr
- range_read
- blocker
- icm
- board_texture
- sizing_tell
- pf_range
- positional
- stack_decay
- open_size
- multiway
- fold_equity

### Centralized wiring — low reference count is not itself a defect

These are funneled through one main decision function by design:

- cbet_flop -> `cbet_freq`
- barrel_turn -> `cbet_freq`
- bluffcatch_early -> `calldown_need`
- potcontrol -> `make_plan`
- trap -> `trap_judgment`
- probe -> `decide_aggression`
- delayed_cbet -> `decide_aggression`
- equity_denial -> `decide_size`
- reraise -> `decide_response`
- pf_defend -> `defend_thresholds`
- range_merge -> `make_plan`

These require reachability/materiality checks only if behavior looks suspicious; the
single-consumer shape alone is not evidence of missing wiring.

### Wired, but semantic debt remains

`blockbet` is live in both plan selection and aggression execution, but its semantics are
not fully closed.

`plan.py` explicitly preserves a legacy absolute-OOP fallback when there is no identified
aggressor.  The same unresolved boundary also affects donk suppression:

- true blockbet: price-setting before a known aggressor acts;
- true donk: leading into the previous/current aggressor;
- no-aggressor OOP lead: currently falls back to legacy absolute position semantics.

This is the highest-priority semantic audit after the inventory.

### Partial/shadow wiring

`money_jump` is **partially wired**:

Live:
- unopened preflop range factor.

Shadow-only:
- open-size factor;
- limp-form pull.

Therefore the old comment saying money-jump is observation-only was stale and has been
corrected.  The shadow channels should not be promoted merely because they exist; each
needs its own preregistered measurement.

## Direct compatibility-field reads

The audit found direct reads of top-level compatibility fields such as
`profile['bluff']` and `profile['icm']`.

This is not automatically a tilt desynchronization bug.  `persona.tilted_view()` tilts
the concept vector and then calls `derive()`, rebuilding the top-level compatibility
fields from the tilted profile.

These direct reads remain technical debt because they make dependency tracing harder, but
there is no current evidence that they observe a different untitled player state.

## Global calibration debt

Independent of wiring, `persona.py` explicitly marks concept loading/base/spread values
as provisional.

This is a separate problem:

- wiring audit asks whether a concept reaches decisions;
- calibration asks whether the generated population distribution is realistic.

Do not retune concept priors until semantic wiring problems are closed, otherwise
population changes can mask logic changes.

## Priority order from this audit

1. blockbet / donk / no-aggressor semantic boundary;
2. money-jump shadow channels, each with separate evidence;
3. direct compatibility-field cleanup only if counterfactual checks show inconsistency;
4. concept loading/spread calibration;
5. global balance validation after the above are closed or explicitly deferred.

## What was not changed

This audit did not change poker decisions, thresholds, plan probabilities, ICM formulas,
or the frozen regression baseline.

The only code change outside audit tooling is a stale explanatory comment in
`persona.py` describing `money_jump` as partially wired rather than observation-only.
