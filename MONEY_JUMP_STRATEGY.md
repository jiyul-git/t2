# Money-jump strategy design — locked behavioral architecture

Status: **design/preregistration only**.  
No action frequency, range or sizing code is changed by this document.

This design follows the natural-state observation run (100 entries, seed 92020,
181 rounds, 8 remaining, 11,885 decision observations, 0 engine errors).

## 1. What the baseline showed

The baseline already has a strong ordinary positional gradient.  In unopened
near-ladder preflop spots, BTN attacked much more often than UTG/UTG+1.
Therefore money-jump must **not recreate position from scratch**; it must modify
the existing positional strategy.

The baseline does **not** currently distinguish cover topology in a meaningful
way when facing a raise:

- versus a covering raiser: fold 77.2%, aggression 4.8%
- versus a raiser hero covers: fold 77.0%, aggression 2.0%

These are observational, hand-strength-uncontrolled rates, so they do not prove
a defect.  They do show that cover topology is not already producing an obvious
tournament-pressure effect that money-jump could safely assume exists.

Waiting-cost diagnostics found 15 near-ladder decisions where the player could
not survive the forced cost to the next BB under the current approximation.
Several were 0.68--1.08 BB stacks with no shorter-stack ladder buffer.  Any
money-jump system that only tightens short stacks would therefore be structurally
wrong.

## 2. Three outputs, not one aggression scalar

Money-jump state must produce three separate continuous outputs.

### A. self_preservation

Question: **how expensive is my own elimination right now?**

Objective inputs:
- normalized payout jump size
- distance to the next jump
- S/J ladder buffer
- severity of shorter stacks
- own stack / field-average stack
- own stack in BB
- BF/ICM
- position and forced waiting cost

Perception/personality inputs:
- money_jump concept
- icm concept
- discipline
- gamble
- consistency

Direction:
- increases with payout importance and feasible ladder buffer
- decreases when waiting is not feasible
- stronger for players who perceive money jumps and ICM well

### B. pressure_opportunity(target)

Question: **how much can I exploit this specific opponent's survival pressure?**

Objective inputs:
- whether hero covers target
- target's stack role and approximate ladder buffer from public information
- target position
- whether target is in SB/BB
- players still behind hero
- whether a stack that covers hero remains behind
- pot/action context

Perception/personality inputs:
- money_jump
- fold_equity
- range_read
- attention
- adaptability
- aggression

Direction:
- high when hero covers a vulnerable stack and few dangerous players remain
- suppressed when a covering stack remains behind hero
- target-specific: the same hero may attack one opponent and avoid another

### C. urgency

Question: **how costly is waiting instead of taking a playable spot?**

Objective inputs:
- remaining stack in BB after already-posted blinds
- hands to next BB
- forced cost to next BB
- forced cost / current stack
- blind/ante structure
- S/J ladder buffer
- severity of shorter stacks

Perception/personality inputs:
- stack_decay
- money_jump
- discipline
- gamble

Direction:
- rises as forced costs consume a larger share of the stack
- rises when there are too few realistic shorter-stack bust candidates
- can override self-preservation for an unprotected/desperate short stack

This is the key guard against the invalid rule "short = lock".

## 3. Structural pressure and exploit realization are separate

`pressure_opportunity(target)` must not bypass the existing exploit system.

There are two layers:

### structural_pressure(target)

A public-state prior.  It asks whether this opponent is *theoretically exposed*
to payout/stack pressure before any personal read is available.

Inputs:
- target stack role
- target ladder buffer / waiting budget
- payout jump and distance
- whether hero covers target
- whether another stack covers hero
- target position and forced blind cost
- action class

This exists even with zero history.

### exploit_realization(target)

How strongly this bot recognizes and acts on that pressure.

Use the existing exploit architecture:
- `attention`
- `range_read`
- `adaptability`
- `fold_equity`
- `reads.perceived_profile()`
- `persona.read_opponent()`
- read confidence / sample size

If reads show that the target is actually overfolding, pressure can be amplified.
If the target has resisted pressure or calls too wide, the adjustment should be
suppressed even when structural pressure is high.

Therefore the split is:

    theory_pressure
      = structural_pressure
        × money-jump/ICM perception
        × adaptability/fold-equity realization
        × topology safety

    read_adjustment
      = opponent-specific deviation learned through the existing reads system

    pressure_opportunity
      = theory_pressure adjusted up/down by read_adjustment

This avoids a failure mode where zero hand history would make
pressure_opportunity zero.  A strong tournament player can infer structural ICM
pressure immediately; actual reads then modify that prior rather than create it.

Do not add a new generic "exploit" temperament unless the existing
attention/range_read/adaptability/fold_equity structure demonstrably fails.

This preserves an important distinction:
- a strong player can infer an ICM-vulnerable target before observing many hands
- a strong exploiter can then update that prior from actual opponent behavior

## 4. Pot-growth geometry: range choice and action form are separate

Money-jump/ICM pressure may change not only *which hands* are played, but also
*how much pot growth a player is willing to create*.

Do not hard-code "large money jump => smaller size" or "large money jump =>
more limps".  Both have real counterexamples.

Instead derive a continuous **pot_growth_budget** from:
- self_preservation
- pressure_opportunity
- urgency
- position
- effective stack
- cover relation
- opponent response tendency
- pot / SPR / board context

Interpretation:

- high self_preservation + low urgency:
  prefer lower-commitment lines when strategically available
  (more checking, calling, selected limping, smaller raises/bets)
- high pressure_opportunity + low own risk:
  may attack frequently, but size is target-dependent
  (small frequent pressure in some spots; larger leverage sizing in others)
- high urgency:
  small-pot preservation can disappear and shove/fold forms become more likely
- high self_preservation + high pressure from a covering opponent:
  reduce voluntary pot growth strongly

The existing engine already separates several relevant mechanisms:
- `open_decision` chooses whether to enter
- `open_form` chooses raise versus shove
- `limp_p` chooses open-limp mixes
- `open_size_bb` chooses opening size
- postflop planning separates action choice from bet sizing

Money-jump should therefore feed **action form and sizing as separate hooks**
rather than one global range multiplier.

### Why this should be partly emergent, not manually scripted

The intended implementation is "engineered incentives, emergent frequency":

1. compute public tournament pressure
2. let personality determine perception
3. let exploit determine target response
4. let pot_growth_budget choose among already-valid strategic forms
5. measure the resulting limp/min-open/small-bet/shove frequencies

The target output frequencies should not be typed in directly.

The current engine can already produce some of this indirectly through
stack depth and BF/ICM affecting perceived depth and shove/limp form.  However,
opening size itself does not currently consume money-jump state directly, so a
systematic payout-ladder-specific sizing shift should not be expected to emerge
without an explicit pot-growth hook.

## 5. Role is derived from the three outputs

No fixed entry-count buckets.

Descriptive roles:

- **covering leader**:
  low/moderate self_preservation, high pressure opportunity against covered
  vulnerable targets
- **protected large stack**:
  low self_preservation but may suppress pressure when another large stack is
  behind
- **vulnerable middle**:
  meaningful stack to lose, feasible ladder buffer, often high
  self_preservation
- **protected short**:
  high self_preservation only when waiting budget is sufficient
- **unprotected short**:
  ladder buffer weak; urgency rises
- **desperate shortest**:
  urgency dominates; waiting is no longer a valid default

These labels are explanatory outputs only.  Strategy uses the continuous signals.

## 6. Position/topology interaction

The existing positional engine remains the base.

Money-jump adds context to it:

- UTG/HJ: more players can resist, so pressure opportunity is naturally capped
- CO/BTN: fewer players remain, making covered-stack pressure cheaper
- SB: waiting cost is high because BB arrives next hand
- BB: current forced cost is already paid; future-cost accounting must not
  double count it

Topology is recomputed every decision:
- players yet to act
- covered players yet to act
- players who cover hero yet to act
- facing target
- blind targets
- current pot/action class

A static "seat strength" multiplier is prohibited.

## 7. Decision-class interventions

Money-jump is not applied identically to all decisions.

### Preflop unopened

Base: existing GTO/position/persona open range.

Effects:
- self_preservation can narrow marginal opens
- pressure_opportunity can widen steals when covered vulnerable SB/BB targets
  are available
- urgency can widen shove/open commitment for desperate short stacks
- a covering stack behind suppresses pressure expansion

This is where chip-leader pressure should appear most cleanly.

### Preflop versus limp

Treat separately from unopened pots.
- exploit/iso logic remains base
- pressure opportunity may widen isolation against covered vulnerable limpers
- self_preservation suppresses marginal bloating of pots
- urgency can favor decisive shove/iso forms for very short stacks

### Preflop versus raise

Separate call and re-raise channels.

- self_preservation tightens marginal calls/stack-offs, especially when the
  raiser covers hero
- pressure_opportunity may widen selective 3-bet pressure when hero covers the
  raiser and the raiser is survival-sensitive
- urgency can prevent an unprotected short stack from over-folding indefinitely
- premium/core value regions remain protected from money-jump overcorrection

No single defend-range multiplier may change calls and 3-bets in the same
direction automatically.

### Postflop free action

- pressure opportunity can increase selected c-bets/barrels against covered
  survival-sensitive targets
- self_preservation can increase pot control with medium-strength hands
- aggression expansion must still pass existing hand/board/fold-equity gates

### Postflop facing bet

- self_preservation increases risk premium on marginal bluff-catches/stack-offs
- urgency should have much less influence than preflop; being short does not
  justify loose postflop calls by itself
- cover relation modifies the target-specific response, not the base equity
  calculation directly

## 8. Personality mapping

Do not add a new temperament axis yet.

Expected natural differences:

- high money_jump + high discipline + low gamble
  -> strong self-preservation when waiting is feasible
- high money_jump + high aggression/adaptability/fold_equity
  -> more target-specific pressure
- high money_jump + low stack_decay
  -> risk of over-waiting
- high money_jump + high stack_decay
  -> recognizes both ladder value and forced waiting cost
- low money_jump
  -> small deviation from baseline even at large payout steps

Money-jump awareness changes the **strength of the response**, not the objective
tournament facts.

## 9. ICM responsibility split

Avoid double counting.

- BF/ICM remains the base tournament risk premium.
- money_jump adds local payout discontinuity and stack-distribution context.
- urgency adds cost-of-waiting context.
- pressure_opportunity models target exploitation.

Money-jump must not multiply BF again inside a path that already consumed BF.
Implementation must trace each hook before coding.

## 10. Implementation order

### Minimal-constant rule

The signal layer should use the smallest possible set of fixed numbers.

Prefer variables that already have a natural scale:

- concepts/temperaments: existing 0..10 profile scale
- stacks: BB and stack ratios
- payout: jump/next-prize and jump/min-cash
- distance: players-to-jump/ITM and players-to-jump/remaining
- ladder buffer: S/(S+J)
- waiting cost: forced-cost/current-stack
- cover: relative stack difference
- exploit: existing read confidence and fold-gap

The first signal layer therefore uses generic continuous transforms only:
`x/(1+x)`, `1/(1+x)`, arithmetic mean, multiplication, bounded union and
bottleneck `min(a,b)`.
It adds no new behavioral thresholds such as "15bb", "top 20%" or "three
players from a jump".

If a future poker mechanism cannot be represented without a fixed coefficient,
that coefficient must be named, documented and measured separately rather than
being buried in a decision formula.

Behavior code is added in this order only:

1. objective signal calculator: self-preservation / target opportunity /
   urgency / commitment budget — DONE
2. pure diagnostic output, no behavior change — DONE
3. preflop unopened intervention — RANGE ONLY enabled first
   - existing open threshold × continuous `range_factor`
   - range pressure uses the **mean** pressure across players still to act
     rather than one target's maximum
   - self-preservation becomes a range brake only in proportion to the fraction
     of players still to act who cover hero
   - generic chip-loss caution remains in the separate pot-growth/sizing shadow;
     the range layer does not duplicate it
   - sizing and limp effects remain shadow-only until range effect is measured
   - sizing shadow pulls the existing size toward the legal 2BB minimum; it does
     not invent a new tournament-specific target size
   - limp shadow adds a tournament-pressure channel on top of the existing limp
     probability, weighted continuously by players-behind/table-size and the
     existing pf_range/positional concepts
   - SB open-limp is measured in shadow even though the current action path still
     blocks SB limps; this must be evaluated before changing the action path
   - every unopened decision logs a same-state local counterfactual:
     `base_threshold`, `money_threshold`, `hand_pct`,
     and `range_cf = widen_entry/narrow_fold/unchanged`
   - aggregate before/after action rates are not sufficient because one changed
     elimination alters the rest of the tournament trajectory
4. preflop versus raise intervention
5. postflop free-action intervention
6. postflop facing-bet intervention

Each step receives a counterfactual/regression test before the next is enabled.

## 11. Required monotonic checks before promotion

Without fixing numerical coefficients yet, the following directions must hold:

- larger normalized jump, same state -> self_preservation must not decrease
- more realistic shorter-stack buffer, same state -> self_preservation must not
  decrease when waiting remains feasible
- higher forced-cost share, same state -> urgency must not decrease
- hero covers target, all else same -> pressure opportunity must not decrease
- target covers hero, all else same -> self_preservation must not decrease
- additional covering stack behind hero -> pressure opportunity must not increase
- higher money_jump skill -> response magnitude must not decrease
- higher stack_decay skill at desperate-short state -> urgency response must not
  decrease

These are structural tests, not empirical poker-optimality claims.

## 12. Prohibited shortcuts

- no absolute "100 entries => N players" thresholds
- no global money-jump aggression multiplier
- no "short = lock"
- no "chip leader = always pressure"
- no treating S/J alone as a strategy rule
- no using raw payout-point differences across formats without normalization
- no hidden-card information in target pressure
- no personality in objective context
- no double counting payout pressure through both BF and money-jump
