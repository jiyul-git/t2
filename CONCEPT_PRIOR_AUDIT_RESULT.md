# Concept prior / population audit — result

Sample design:

- generator seed: 20260926
- profiles per field quality: 3,000
- field quality grid: 0.40, 0.60, 0.78, 1.00, 1.20
- production generator unchanged

## Sanity

Overall skill moves monotonically with field quality:

- q=0.40: median 3.69
- q=0.60: median 4.38
- q=0.78: median 5.05
- q=1.00: median 5.89
- q=1.20: median 6.58

The field-quality mechanism is therefore active and directionally coherent.

## Main finding

The current `base` values are **not** the realized population medians.

Latent study/aggro/experience loadings, concept-specific spread, 0-10 clamping and the
overall-skill rejection filter materially reorder the realized population.

Examples at q=0.78:

- `range_read`: nominal base rank 17 -> realized difficulty rank 25
- `pf_defend`: nominal 16 -> realized 24
- `spr`: nominal 19 -> realized 26
- `bluff`: nominal 23 -> realized 15
- `semibluff`: nominal 30 -> realized 22
- `checkraise_flop`: nominal 25 -> realized 18

Therefore future calibration must target **realized distributions**, not edit nominal
base values as if they were direct means.

## Realized q=0.78 difficulty shape

Hardest realized medians:

1. stack_decay 3.7
2. overbet 3.9
3. checkraise_late 4.0
4. barrel_river 4.2
5. thin_value_river 4.2
6. blockbet / reraise / range_merge 4.3

Easiest realized medians:

- cbet_flop 6.1
- pf_range 5.8
- outs / potodds 5.5
- bluffcatch_early 5.4
- several common concepts around 5.2-5.3

This ordering is broadly plausible, but it is not yet an accepted semantic calibration.

## Saturation

Concepts exceeding 5% at either 0 or 10:

- stack_decay: 10.6% at 0
- pf_range: 7.8% at 10
- range_merge: 5.7% at 0
- blocker: 5.3% at 0
- money_jump: 5.2% at 0

These are the first candidates for spread/base review because clamping is visibly shaping
their population rather than merely bounding rare tails.

## Latent loading behavior

The intended latent factors are visible in the generated population.

Examples:

- study strongly drives outs, thin-value river, bluffcatch river, board texture;
- aggression strongly drives bluff, barrel turn, c-bet, river barrel;
- experience strongly drives trap and positional awareness;
- pot control is negatively correlated with aggression as intended.

So the loading architecture itself is not dead. The issue is calibration of magnitude and
realized ordering, not missing dependency.

## Money-jump scale

`money_jump` is generated separately and excluded from `overall_skill`, but its q=0.78
realized distribution is still on a comparable 0-10 scale:

- q10 1.0
- median 4.8
- q90 8.4
- floor 5.2%
- ceiling 3.3%

It should remain separately calibrated because including it in overall-skill rejection
would retroactively change the existing player population.

## Decision

Do **not** edit LOADING or SPREAD directly from this audit.

Next calibration must:

1. define an ordinal semantic difficulty order / rough target bands first;
2. distinguish "common/basic concept" from "specialist/advanced concept";
3. preserve intended latent directions;
4. reduce obvious clamp saturation;
5. optimize against realized distributions after the rejection filter;
6. keep `money_jump` outside overall skill unless separately justified;
7. verify action-level balance only after the population prior is locked.

No generator parameter or frozen regression baseline is changed by this audit.
