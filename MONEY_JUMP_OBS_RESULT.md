# Money-jump natural-state observation — first full stage run

Status: observational baseline only.  Money-jump is **not connected to behavior**
in this run, so action rates are descriptive and must not be interpreted as
causal effects of money-jump.

## Run

- entries: 100
- format: standard
- seed: 92020
- rounds: 181
- stop: 8 remaining
- decision observations: 11,885
- engine errors: 0

Stage observations:

- pre >1.5x ITM: 10,907
- approach 1.2--1.5x ITM: 255
- bubble 1.0--1.2x ITM: 208
- ITM: 448
- final 9: 67

The first requirement is satisfied: the instrumentation reaches approach,
bubble, ITM and final-table states without engine errors.

## Signal coverage

Across all observations:

- money_jump skill p10 / p50 / p90 = 1.9 / 5.3 / 8.1
- shorter fraction p10 / p50 / p90 = 0.103 / 0.493 / 0.905
- players yet to act p10 / p50 / p90 = 0 / 2 / 6
- S/J (shorter stacks / eliminations needed for next jump)
  p10 / p50 / p90 = 0.137 / 0.677 / 1.382

So the proposed signals are not degenerate: profiles, ladder buffers and seat
topology all span useful ranges.

## Descriptive patterns — not causal conclusions

Position shows a strong baseline gradient in the near-ladder sample: BTN folds
less than early positions, while BB has few aggressive actions.  This confirms
that nominal position is visible in the collected data.

Cover topology is also populated:

- covering stack still behind: n=504
- hero covers someone behind: n=540
- facing a covering aggressor: n=226
- facing an aggressor hero covers: n=220

When facing aggression, raw fold rates are high in both directions
(75.7% versus a covering aggressor, 78.6% versus a covered aggressor).  Because
hand strength, street and action history are uncontrolled, this is **not** a
test of whether the engine exploits covered stacks.  It does show why a later
counterfactual must separate target pressure from generic "facing a bet".

The S/J buckets are also not monotone in raw fold rate.  In particular S<J had
86.2% folds while S<<J had 69.1%.  This is expected to be confounded by stack
depth, position, street and facing-action mix.  Therefore S/J must not be turned
directly into a strategy threshold from this table.

## Important short-stack observation

The extreme unprotected examples include repeated preflop folds at about
0.68--1.08 BB with S/J=0 and no shorter stack buffer.  This is a useful design
warning.

It does not establish a baseline bug by itself because the hole cards and exact
decision class were not controlled in the aggregate report.  But any future
ladder-preservation effect must be opposed by a waiting-cost/urgency signal.
Otherwise money-jump could make already-short stacks wait even longer.

The next instrumentation therefore records time to the next BB and forced blind
cost as a fraction of the remaining stack.

## Why the aggregate action rates are insufficient

The 11,885 rows are decisions, not independent hands or players.  A postflop
hand can contribute several rows, and "facing a raise", "unopened", "limped
pot", and "free postflop action" have very different baseline fold/aggression
rates.

Before behavioral intervention, analysis must split at least:

1. preflop unopened
2. preflop versus limp
3. preflop versus raise
4. postflop free action
5. postflop facing bet

and then condition on position, stack percentile, S/J and cover relation.

No money-jump strategy coefficient is selected from this first run.

## Decision-class split from the completed run

Near-ladder observations were split by decision class before any strategy
coefficient was selected:

- unopened: n=380, fold 71.6%, aggression 28.4%
- versus raise: n=389, fold 77.1%, aggression 3.3%
- postflop free action: n=152, aggression 30.3%
- postflop facing bet: n=57, fold 77.2%

Unopened preflop showed the expected existing position gradient:

- UTG aggression 20.3%
- CO aggression 33.3%
- BTN aggression 63.3%
- SB aggression 44.4%

Thus money-jump does not need to invent positional awareness; it should adjust
the existing positional decision only when payout/stack/topology context calls
for it.

Preflop versus raise showed nearly identical raw folds by cover direction:

- raiser covers hero: fold 77.2%, aggression 4.8% (n=189)
- hero covers raiser: fold 77.0%, aggression 2.0% (n=200)

These are not causal comparisons because cards and opener ranges are not held
fixed.  They motivate a controlled counterfactual rather than a direct tuning
rule.

Waiting-cost diagnostics:

- forced-cost share p10/p50/p90 = 0.039 / 0.066 / 0.147
- cannot survive to next BB under the diagnostic approximation: n=15
- those rows include repeated 0.68--1.08 BB decisions with S/J=0

This locks the design requirement that urgency/waiting feasibility must be an
independent counterforce to ladder preservation.
