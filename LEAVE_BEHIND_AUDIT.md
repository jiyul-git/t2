# Intentional leave-behind audit — pre-design findings

Branch: `chatgpt/leave-behind-audit-20260925`

This audit starts **after** effective-all-in v1 was accepted.  It does not change
production decisions.  The question is narrower:

> when an action is already classified effective-all-in, is there an existing
> tournament-state signal that can justify an explicit survival-oriented
> leave-behind execution mode instead of a physical shove?

## 1. Existing state is already rich enough

`session._money_jump_observe` already exposes, per decision:

- next payout jump size and distance;
- current/next prize and players-to-jump;
- number and severity of shorter stacks;
- waiting feasibility;
- forced cost to the next BB and its share of the current stack;
- actor BF;
- field-average stack;
- cover relations;
- player concepts/temperaments through `money_pressure.actor_from_profile`.

`money_pressure.signals` already derives:

- payout importance;
- ladder buffer;
- waiting feasibility;
- objective and perceived self-preservation;
- objective and perceived urgency;
- commitment budget.

No new personality axis is needed to decide whether survival has strategic value.

## 2. The existing signals have different responsibilities

`self_preservation` is **not** a pure ladder signal.  Its objective component is

- payout importance
- multiplied by the union of:
  - BF signal;
  - ladder buffer × shorter-stack severity × waiting feasibility.

That matters because postflop facing-bet decisions already consume BF through
`act_with_plan -> calldown_need`.  Feeding the full self-preservation signal into
a later execution-mode selector can therefore count the same BF risk twice.

For a leave-behind policy, the clean candidate signal is the *ladder/survival option*
component already implicit in the existing state, with urgency acting in the opposite
direction.  Do not multiply BF again merely because the action is close to all-in.

`pressure_opportunity` is target exploitation.  It should not directly decide whether
the actor preserves chips for tournament survival.

## 3. Free-action and facing-bet paths must remain distinguishable

Postflop money-jump state is currently observed on both:

- `free_action`
- `facing_bet`

but `act_with_plan` does not consume the money-jump observation directly.

The facing-bet path already applies BF to call/fold/raise requirements.  The free-action
path does not consume the same live BF state in the final execution layer.

Therefore a single opaque "ICM leave-behind score" applied to both decision classes would
hide different upstream semantics.  Audit output must retain `decision_kind`.

## 4. A hard-coded one-BB residue is not yet justified

The repository already knows:

- hands to next BB;
- forced cost to next BB;
- stack after the next BB if folding every hand;
- ante state.

A fixed one-BB residue can have very different survival value depending on position and
forced costs.  One BB may buy a real future option in one state and be forced in almost
immediately in another.

The execution architecture should therefore remain:

```
effective_allin = true
    -> execution selector
         -> shove
         -> leave_behind(reason, leave_amount)
```

but `leave_amount` must be measured against the existing waiting-cost state before it is
defined.  No `1BB` constant is introduced in this audit.

## 5. Field-simulation observability needs care

`fieldsim` plays tables sequentially inside a field step.  Each table is stamped with
the then-current `remaining()` and money-jump context.  A table played later in the same
cycle can therefore observe busts from tables that were simulated earlier in that cycle,
while an earlier table cannot observe later busts.

This is especially relevant to a survival/ladder execution mode.  A policy that reacts
sharply to exact `players_to_jump` or current remaining count could learn simulator
ordering rather than tournament strategy.

Before enabling leave-behind, measure the candidate population and avoid using an exact
same-cycle ladder boundary as a hard trigger.  If the measured policy proves sensitive to
this ordering, field-context snapshot/hand-for-hand semantics must be addressed first.

## 6. What the next measurement must record

For each actual effective-all-in **promotion** (not actions already exact/full), record
the money-jump observation from the same seat/street/action occurrence:

- decision kind;
- BF;
- payout importance;
- ladder buffer;
- waiting feasibility;
- self-preservation objective/perceived;
- urgency objective/perceived;
- commitment budget;
- players-to-jump;
- number/severity of shorter stacks;
- forced cost to next BB;
- stack after next BB if folding;
- current residual that v1 would otherwise convert to shove.

No leave-behind threshold is preregistered.  First inspect whether these promotions
naturally separate into "survival option has value" versus "shove is clearly preferable"
states.

## 7. Non-goals

This audit does not:

- change effective-all-in v1;
- add a leave-behind action;
- add a 1BB constant;
- alter ICM/BF formulas;
- change plan probabilities;
- use opponent-pressure signals as actor-survival signals;
- update the frozen regression baseline.
