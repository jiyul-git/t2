# A4: production-DB acceptance audit of A3 (panel bootstrap)

- **Rules:** pre-registered in `data/gto_terminal_expansion/a4_audit/prereg.json` (`005561b`), unchanged.
- **A3:** sealed at `94502b8`, not modified.
- **Verdict:** `a4_audit/a4_verdict.json`.
- **Figure:** [`GTO_TERMINAL_A4_AUDIT_V2.png`](GTO_TERMINAL_A4_AUDIT_V2.png).

**Classification: `precision_limited`** (overall, and for node 28 and node 6 each). P15 is **not** adopted as a production candidate.

## Method
- 30 stratified resamples of the 72 panel boards; one draw is applied to every A3 step k10..k14.
- The used-table chain is rebuilt with the recorded accept/reject flags.
- One frozen-table preflop solve per replicate, in three variants: both terminals, node 28 only, node 6 only.
- No new postflop solve and no outer-loop step.
- **Validation (exact):**
  - The identity draw reproduces the A3 `used_14` tables (max |d| = 0).
  - It also reproduces the P15 aggregates (max |d| = 0), with bit-identical gaps, EVs and ranges hash.
- **Limitation:** the bootstrap measures the board-sampling sensitivity of P15. It does not directly measure the noise of a fully re-converged fixed point. With 30 replicates the percentile interval is coarse; the SD-based ratio gives the same classification.

## Result (both terminals; the own-terminal variant gives the same numbers)

| aggregate | P15 | \|P15−P14\| | bootstrap mean | SD | 95% interval | d / half-width |
|---|---|---|---|---|---|---|
| CO first-in (all actions) | .727/.262/.011 | 0 | = | 0 | — | — |
| BTN fold / raise / jam | .590/.370/.040 | .004/.006/.002 | .590/.370/.040 | .009/.012/.004 | ±.017/.021/.006 | 0.21–0.35 |
| SB fold | .355 | .031 | .316 | .026 | [.269, .367] | 0.63 |
| SB raise 2.5 | .501 | .045 | .554 | .041 | [.468, .614] | 0.62 |
| SB jam | .144 | .015 | .130 | .021 | [.098, .171] | 0.40 |
| BB vs BTN fold | .103 | .016 | .124 | .029 | [.082, .172] | 0.35 |
| BB vs BTN call | .756 | .020 | .723 | .039 | [.652, .788] | 0.30 |
| BB vs BTN jam | .141 | .004 | .153 | .011 | [.134, .171] | 0.23 |
| BB vs SB fold | .014 | .031 | .069 | .033 | [.020, .123] | 0.60 |
| BB vs SB call | .802 | .053 | .720 | .053 | [.639, .789] | 0.70 |
| BB vs SB jam | .184 | .022 | .211 | .021 | [.187, .243] | 0.77 |

- **gap_total:** 0.00035 at P15; replicates up to 0.0009.
- **Attribution:** the two terminals act on disjoint aggregates.
  - Node 28 moves BTN first-in and BB vs BTN.
  - Node 6 moves SB first-in and BB vs SB.
  - Cross effects are ≤ 0.0001.
  - Node 28 does not set the precision floor alone: max half-width 0.068 for node 28 vs 0.075 for node 6.
- **Threshold 0.005:** not identifiable at 72 flops. Every aggregate that a solved terminal moves has a half-width above 0.005, from 0.006 (BTN jam) up to 0.075.
- **Period-2:**
  - Node 28: half-amplitude 0.13–0.19 of its own half-width, negligible.
  - Node 6: 0.23–0.75 of its own half-width; below the noise, but not negligible.

## Unexpected: the replicate distribution is not centred on P15
- The bootstrap mean differs from P15 by up to 0.08 (BB-vs-SB call −0.082, fold +0.055; SB raise +0.053).
- For BB vs SB, P15 lies at or outside the replicate range.
- **Diagnostic (not pre-registered):** one preflop solve on the mean replicate table.
  - The mean table matches the A3 table within 30-sample noise.
  - That solve stays near P15: BB-vs-SB fold .029 and call .783; SB raise .527.
- **Reading:** the cause is the non-linear table → strategy map under noise (BB-vs-SB fold sits at the 0 boundary), not a biased table estimator.
- **Consequence:** panel noise also shifts these aggregates systematically, by about the same size as the half-width. The total 72-flop error of SB first-in and BB vs SB is therefore about ±0.05–0.10, more than the half-width alone suggests.

## Minimum additional compute (nothing started)
- **The registered precision-limited branch** is a denser board panel for the terminal(s) that set the floor, which here means both.
  - This conflicts with the standing rule against 144/288-flop panels, so it needs an explicit decision.
- **144 boards per terminal** (+72 each):
  - about 16 CPU-h, about 4 h wall;
  - expected half-width ×0.71 (about 0.052), with the noise-induced shift roughly halved.
- **288 boards per terminal:**
  - about 48 CPU-h, about 12 h wall;
  - expected half-width ×0.5 (about 0.037).
- **Range state:** the existing 72 solves are at the P14 (k14) ranges. The added boards would be solved at the same ranges, followed by one frozen-table preflop solve.
- **Not recommended:** more outer steps at 72 flops. The last step already moves less than the panel resolution.
