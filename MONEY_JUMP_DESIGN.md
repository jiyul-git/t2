# Money-jump strategy design

Status: **behavioral design only**.  
Do not change action frequencies/ranges/sizing from this document until the
measurement/validation plan is agreed.

The engine already has ICM/bubble-factor and tournament context.  Money jump is
not a replacement for ICM.  It is a separate perception of *where the next
payout discontinuity is, how valuable it is, and whether other stacks can carry
the player to it*.

## 1. Separate truth from personality

The tournament state must first produce objective public facts.  No personality
belongs in this layer.

Raw money-jump facts:

- `remaining`, `itm`
- `current_rank`
- `current_prize`
- `next_rank`
- `next_prize`
- `next_jump`
- `players_to_jump`
- normalized jump size: jump / min-cash, jump / next-prize
- normalized distance: players-to-jump / ITM, players-to-jump / remaining
- hero stack, BB, field-average stack
- number/fraction of surviving stacks below hero
- nearest shorter stacks and nearest larger stacks
- table opponents hero covers / opponents that cover hero

The current `context.money_jump_context()` only supplies the payout facts.  The
stack-distribution facts are a later context extension.

No thresholds may be hard-coded as "100-entry tournament => N players".  Rank
and stage signals must scale with the actual field, ITM fraction and payout
table.

Raw payout points are kept for audit, but strategy must not compare them across
different field sizes/formats without normalized versions.  A 1.0-point jump in
a 10-paid event is not automatically equivalent to a 1.0-point jump in a
100-paid event.

## 2. Money jump is a concept

Add a separate calculation concept (provisional name `money_jump`) rather than
folding everything into `icm`.

- `icm`: understands that tournament chips are not cash and that losing chips
  can be more expensive than winning the same chips.
- `money_jump`: notices the actual payout ladder: the next discontinuity, its
  size, its distance, and which stacks are likely to bust first.
- `stack_decay`: understands the cost of waiting while blinds rise.

These concepts should be correlated through the existing latent study/experience
generation, but not identical.  This allows, for example, a player who knows
basic ICM but does not track exact payout jumps, or a player who sees the ladder
but over-waits because stack decay is weak.

## 3. Perceived pressure, not one global scalar

Money-jump strategy needs at least two independent channels.

### A. Self-preservation pressure

How expensive is *my own elimination* right now?

Inputs:

- objective payout jump size
- distance to the next jump
- own stack / field average
- own stack in BB
- fraction/count of shorter stacks
- stack gap to the shorter stacks
- ICM/BF
- `money_jump` concept
- `icm` concept
- `stack_decay` concept
- temperament: discipline, gamble, consistency

This channel can tighten calls, reduce marginal stack-offs and increase
pot-control.

### B. Pressure opportunity

How much does *the opponent* have to lose, and can I make use of that?

Inputs:

- opponent's estimated self-preservation pressure from public information
- whether hero covers that opponent
- whether opponent covers hero
- opponent stack position in the field
- hero's aggression/adaptability
- hero's `fold_equity`, `money_jump`, `range_read` and attention concepts

This channel can widen steals/3-bets and increase low-risk pressure without
making the bot globally reckless.

A chip leader can therefore have low self-preservation pressure and high
pressure opportunity at the same time.

## 4. The number of stacks below you is structural

`n_shorter` is not cosmetic.  It changes whether waiting can plausibly buy a
payout jump.

The important comparison is not simply "short / medium / big" but:

    next jump requires J eliminations
    there are S stacks below me

When S is comfortably larger than J, a disciplined player has a real laddering
buffer.  When S is smaller than J, waiting alone cannot deliver the jump.

The size distribution matters too.  Five players one chip below hero are not
the same as five players with 1-2 BB.  Therefore later implementation should
carry both:

- ordinal buffer: how many stacks are below hero
- severity buffer: how short those stacks are in BB / relative stack terms

Do not convert this to a single hard categorical cutoff before measuring it.

## 5. Stack roles are derived, continuous states

Do not assign personality from a fixed role.  Role is tournament state.

Useful derived roles:

- **dominant/covering leader**: covers most relevant opponents
- **large protected stack**: above field but not universally covering
- **vulnerable middle**: meaningful stack to lose, several short stacks below
- **protected short**: short, but enough shorter/critical stacks can bust before
  the next jump
- **unprotected short**: short with little or no ladder buffer
- **desperate shortest**: waiting cost/stack decay dominates ladder value

These are descriptions of continuous signals, not fixed entry-count buckets.

Important consequence: "short stack = lock" is not universally correct.
A protected short stack may lock strongly; the actual shortest stack can be
forced to attack because blind erosion makes waiting worse than taking a spot.

## 6. Table position and seat topology are part of money-jump strategy

Nominal poker position matters:

- UTG/HJ/CO/BTN/SB/BB change how many players remain behind.
- Late position creates lower-risk pressure opportunities because fewer players
  can wake up with resistance.
- Blinds are structurally different because waiting costs chips immediately.
  A short BB close to a money jump cannot be treated like the same stack on BTN.
- SB/BB also change whether folding preserves a meaningful stack for another
  orbit or simply accelerates blind erosion.

But nominal position alone is not enough.  The *relative seating of stack sizes*
also matters.

Examples:

- a chip leader with two medium stacks immediately to the left has a different
  pressure opportunity from a chip leader with another covering big stack on
  the left.
- a medium stack with the table chip leader directly behind should defend and
  open differently from the same stack when the covering stack has already
  folded.
- a protected short stack in BTN can wait more cheaply than the same stack in
  the blinds.
- a big stack on BTN with vulnerable medium stacks in SB/BB has a natural
  steal/pressure target.

Therefore the future context/decision layer should expose public seat-topology
facts such as:

- hero nominal position
- number of players yet to act
- stack ratios of players yet to act
- number of players behind who cover hero
- number of players behind hero covers
- nearest covering stack on the left / right
- vulnerable medium stacks in the blinds
- critical short stacks in the blinds
- whether the main pressure target has position on hero

This must be recomputed per decision, not once per hand.  After folds, the same
seat layout can create a completely different pressure opportunity.

Money-jump strategy therefore depends on:

    payout state
    + own stack role
    + field stack buffer
    + opponent stack role
    + table position
    + relative seat topology
    + personality/concept perception

Position is not another global multiplier.  It changes which target is
available, who can resist, and how costly waiting is.

## 7. Waiting feasibility: ladder buffer is not enough

A large number of shorter stacks does not automatically mean a player can
profitably wait.  The player must also be able to survive the forced costs that
arrive before those eliminations are likely to happen.

Seat position therefore affects laddering through *time to the next blinds*.

Observation inputs should include:

- hands until the player's next BB
- stack remaining after already-posted blinds
- forced cost to the next BB
- full-orbit forced cost in BB (SB + BB + BBA when active)
- forced cost as a fraction of the remaining stack

This is especially important for the shortest stacks.  The first natural-state
run contained repeated folds with roughly 0.7--1.1 BB and no shorter stack
buffer.  That does **not** by itself prove the baseline action was wrong because
cards/action context were uncontrolled, but it proves that a future
money-jump/ladder rule must have an urgency counterforce.  "Short = lock" is not
an acceptable rule.

Conceptually:

    ladder buffer  = can other players bust before me?
    waiting budget = can my stack survive long enough to benefit?
    urgency        = waiting cost versus the available ladder buffer

The strategy layer should only tighten for a ladder when both payout value and
waiting feasibility support it.

## 12. Personality decides *how* the same state is played

Do not create a new temperament unless existing axes fail to explain observed
variation.

Examples using existing axes/concepts:

- high money_jump + high discipline + low gamble:
  strong laddering / fold marginal calls
- high money_jump + high aggression + high adaptability + high fold_equity:
  recognizes opponent pain and applies pressure
- high money_jump + high aggression but low discipline:
  pressure can become over-application
- low money_jump:
  largely baseline strategy even when the objective ladder is large
- high money_jump + low stack_decay:
  risk of waiting too long
- high money_jump + high stack_decay:
  understands both payout value and the cost of waiting

Thus two chip leaders can diverge naturally:
one attacks pressured medium stacks, another preserves the lead and selects only
low-risk spots.

## 8. Strategy should be target-specific

Money-jump response must not be implemented as one global aggression multiplier.

Candidate effects, to be designed and measured separately:

Preflop:
- RFI width
- steal targeting
- 3-bet bluff frequency
- flat-call tolerance
- jam/call threshold
- iso/raise sizing

Postflop:
- c-bet/barrel frequency
- bluff selection
- bluff-catch threshold
- thin-value threshold
- pot-control
- stack-off threshold
- pressure sizing versus capped/covered stacks

The same player can tighten against a covering big stack while attacking a
covered medium stack in the same orbit.

## 9. Interaction with ICM

Money jump and ICM must not double-count the same risk.

Proposed responsibility split:

- BF/ICM = base risk premium from tournament survival value.
- money jump = local payout-ladder discontinuity and stack-distribution context.
- strategy combines them once at the decision layer.

Before implementation, trace every current BF use so a money-jump modifier is
not multiplied into a path that already contains the same payout information.

## 10. First measurement plan before behavior code

Before changing decisions, instrument only the derived context and collect:

- current/next prize and jump
- players_to_jump
- hero stack / field average / BB
- n_shorter and shorter fraction
- nearest shorter stack ratios
- cover counts at the table
- hero position and number of players yet to act
- cover/covered counts among players yet to act
- stack ratios of players yet to act
- short/medium stacks in SB/BB and whether they are pressure targets
- BF
- perceived money-jump strength by profile
- eventual action from the unchanged baseline engine

Then inspect representative states:

1. bubble: medium stack, many shorter stacks
2. bubble: shortest stack
3. ITM: one elimination from a large jump
4. final table: chip leader covering medium stacks
5. final table: chip leader facing another big stack
6. satellite/flat payout after ITM
7. same objective state with low vs high money_jump concept

Only after those signals behave monotonically and sensibly should strategy
interventions be preregistered.

## 11. Invariants

- no absolute "100 entrants => N players" strategy thresholds
- no hidden-card information in money-jump state
- payout/stack facts are objective and personality-free
- personality changes perception/response, not the tournament facts
- exact same public state can produce different bot strategies through concepts
  and temperament
- same bot can attack one opponent and avoid another in the same state
- nominal position and relative seat topology must be explicit inputs, not inferred from entry count
- seat-topology signals are recomputed after action/folds because the set of players behind changes
- money-jump intervention must never be silently counted twice with BF/ICM
- behavior changes require a frozen measurement/design document first
