# A4b / A4R report: 72 → 144 boards for nodes 28 and 6 (pre-registered, amendments 1–3)

**Sources**
- Rules: `data/gto_terminal_expansion/a4b_panel144/prereg*.json`. Amendments 2 (`b94722d`) and 3 (`20e70cc`) were fixed before any result.
- Verdict: `data/gto_terminal_expansion/a4r_robust/a4r_a4b_verdict.json`.
- Figures: [`GTO_TERMINAL_A4B_PAIRED_V2.png`](GTO_TERMINAL_A4B_PAIRED_V2.png), [`GTO_TERMINAL_A4R_ROBUST_V2.png`](GTO_TERMINAL_A4R_ROBUST_V2.png).
- Design review: [`GTO_TERMINAL_A4B_A4R_DESIGN_REVIEW_V2.md`](GTO_TERMINAL_A4B_A4R_DESIGN_REVIEW_V2.md).

**Scope**
- Frozen-table preflop game at the P14 ranges. This is not a re-converged fixed point.
- A3 and A4 are unchanged.

## A4b: panel refinement, primary D = g(V144) − g(V72)

- **Identity checks:** V72 and V144 rebuilt from the flops reproduce the table files exactly (|d| = 0). g(M14_72) = P15 exactly.
- **Postflop:** 144 new flop solves, all converged. Worst exploitability 0.298% pot (node 6) and 0.299% (node 28), target 0.300%.
- **Nested paired bootstrap:** 60/60 replicates usable. Simultaneous max-stat c95 = 2.59 (Bonferroni z = 2.87) over 12 moving aggregates.
- **No panel-detectable shift.** The largest |D|/SD(D*) is 1.49:

  | aggregate | g(V72) | g(V144) | D | SD(D*) |
  |---|---|---|---|---|
  | SB raise 2.5 | .500 | .549 | +.049 | .043 |
  | BB vs BTN call | .741 | .796 | +.055 | .040 |
  | BB vs BTN jam | | | −.016 | .011 |

- **Resolution:**
  - Max 95% half-width is 0.108 at 72 boards and 0.077 at 144 boards.
  - The BB-vs-BTN and BB-vs-SB half-widths shrink by 0.66–0.75, close to the √½ expectation.
- **Unexpected:** the SB first-in half-widths grow (raise .064 → .077, fold .039 → .048, jam .033 → .037). Recorded as is; cause not isolated.
- **Secondary components:**
  - Staleness |g(V72) − P15| ≤ 0.023.
  - A3-process counterfactual |g(M144) − P15| ≤ 0.036.

## A4R: seat-swap EV, opponents fixed at the game's own solve

Values are bb per hand; the own residual gap per seat is 0.6–1.2e-4.

| seat | 72 → G144: point / boot q95 | 144 → G72: point / boot q95 | P15 → G72 | P15 → G144 |
|---|---|---|---|---|
| CO | 0 / 0 | 0 / 0 | 0 | 0 |
| BTN | 0.0003 / 0.0022 | 0.0010 / 0.0024 | 0.00001 | 0.0003 |
| SB | 0.0026 / 0.0073 | 0.0019 / 0.0095 | 0.0001 | 0.0026 |
| BB | 0.0026 / 0.0091 | 0.0027 / 0.0105 | 0.0002 | 0.0032 |

- **Excess over the residual gap:** for BTN, SB and BB in both directions, point E > 0 and q05(E) > 0. The loss exceeds the residual suboptimality of the baseline solve by about 20–100×.
- **No near-indifference.** dEV rises with the class-level L1 frequency distance of the swapped node.
- **Staleness carries almost no EV:** P15 → G72 ≤ 0.00015.
- **Scale:** the losses are 0.3–1.4× B_post (0.0076). B_post is a different error source and is not a pass line.

## Validation failure (recorded as is)

- **What failed:** |dEV − gap difference| and the BR-value identity reach 6.7e-11 in 128 of 744 records. The pre-registered tolerance was 1e-12; the median is 8e-17.
- **Isolation:**
  - deterministic;
  - thread-independent;
  - the own-solve values match exactly between sources;
  - the values repeat at a fixed rounding quantum (2.2475e-11).
- **Reading:** the solver's BR value for seat p depends on p's own strategy at the 1e-11 level. This is a numerical effect; the exact source is not isolated.
- **Impact:** at most 3.5e-8 relative to the dEV values. The EV rule gives the same result using dEV or the gap difference, and the smallest |E| at a decision point is 9.8e-5.

## Final classification

- **Pre-registered label: inconclusive.** Validation tolerance exceeded, 6.7e-11 > 1e-12.
- **EV rule result, given the isolation above: EV-sensitive to panel refinement** (BTN, SB, BB).
- **Frequency:** frequency-unstable. No detectable 72 → 144 shift, but the 144-board resolution is up to 0.077.
- **No production PASS/FAIL.**
