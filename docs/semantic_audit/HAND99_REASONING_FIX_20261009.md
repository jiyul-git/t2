# HAND 99: premium continuation and intended sizing

Review baseline: `e6cc4618657e12853a12d61627ba19562612cb7b` (test3).
The historical UI hand was eight-handed; new model contract checks use nine-max.
This is a behavior correction, not a behavior-preserving refactor or a solved
GTO calibration. No global personality floor was introduced.

## Observed problems

- B14, UTG+1, A♠ K♣, 81.518bb after ante: limp, then fold after CO raised
  to 4.6bb and SB called. Its incremental call was 3.6bb into 12.2bb.
- The shared hand ordering placed AKo behind KTs, QTs, 66 and KJs, at 7.09%.
  This affected open, defend, fallback ranges and premium limp suppression.
- B13, CO, A♣ 3♥: river intention was 0.33 pot / 5,100 chips. A separate
  odd-size lottery replaced it with one pot / 15,500 chips, without revisiting
  the risk or fold-equity judgment.
- Vector players still inherited size jitter from their derived type label.
- Aggression explanations retained the pre-anchor probability (80%) when
  the actual river decision probability was 62.05%.

## Changes and judgment

### Premium ordering

The compatibility order now starts AA, KK, QQ, AKs, JJ, AKo, TT, 99. Only
AKs and AKo were moved; all other classes retain their relative order.
All 169 cumulative percentiles were recomputed from exact class combination
counts (6 paired, 4 suited, 12 offsuit, total 1,326). AKo is now 3.02%.

This is an explicitly heuristic correction to a universal compatibility
ordering, not a claim that every decision family prefers this exact order.
AK should not be systematically treated as weaker than small pairs or KTs
when deciding an ordinary open/continuation. Separate situation-specific
priors remain necessary for precise strategy.

### Limp backaction

A prior limper facing a first isolation raise plus another live opponent now
uses the existing multiway reasoning path, when perceived ranges and actual
price are available. It compares equity with the incremental call price,
retaining the existing knowledge, calculation error and personality blend.
It records `context_kind=limp_vs_isolation_multiway` in `pf_cold_audit`.
It does not override every premium hand into a call or suppress 4-bet paths.

### Intended size variation

Production vector players use consistency and attention to vary an already
judged amount. The provisional variation envelope is:

`jitter = .03 + .12 * (1 - consistency/10) + .05 * (1 - attention/10)`

The envelope is 3–20%, plus at most 50 chips of nearest-100 rounding for
targets above the minimum unit. These coefficients are human-model choices,
not empirically measured population estimates. Lower consistency broadens
amount variation, while preserving the strategic size decision.

Type labels no longer determine vector-player sizing. Random pot-multiple
replacement is retained only for old label-only callers. A substantial
alternative size must be evaluated in judgment/plan before execution, rather
than invented by the amount-shaping helper. Exact all-in targets are retained.
Metadata records `mode=planned_amount_variation` and the applied envelope.
Aggression explanations distinguish base probability and final probability.

## Exact review replay

The reproducible input is `tools/fixtures/hand99_reasoning.json`:
hand seed `65903569`, deal hash `7c03e7208f83`, original profiles, book and tilt.
Before editing, an uncached full replay matched every original action.

After editing, the same hand has B14 raise to 1,300 chips and win preflop;
the previous postflop sequence therefore no longer exists in that full replay.
Holding B13's original river intention, pot, stack and shape seed fixed
isolates sizing: 5,100 → 5,500 chips, versus the old 5,100 → 15,500.
This controlled comparison must not be described as a new full-hand river.

## Verification

- `tools/verify_review_reasoning.py`: 169-class combo accounting; 3,600
  label-invariance/bounded-sizing comparisons; all-in preservation; nine-max
  cheap-price call vs expensive-price fold; deterministic historical replay.
- Core sizing ownership, preflop closure, temperament direction, timing
  familiarity, preflop error fallback and archive trace schema checks pass.
- Defend formula comparison uses the review baseline above because the
  historical verifier's original git checkpoint is absent from this shallow
  checkout. It compares formula semantics with the same current rank input;
  it does not assert old/new rank-dependent behavior is identical.
- `verify_replan_contract.py` reports its existing C4 failure with byte-identical
  output before/after. This change does not modify the replan contract.

- Repeated nine-max integration passes all five checks: seeds 5150/9001/4242,
  24 hands each, production/opt-in/repeated opt-in (216 completed hands),
  identical repeated fingerprints, zero engine/book errors, bounded history.
  The additional single-feature attribution run also completes (24 hands).
  This establishes composition/determinism, not a population frequency target.
