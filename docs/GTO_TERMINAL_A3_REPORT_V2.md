# A3 — node 28 + node 6 synchronous damped outer fixed point (final report)

Branch `chatgpt/terminal-census-v2-20260930`.

- **Rules:** fixed before results in `data/gto_terminal_expansion/outer_m28_6/`:
  - `prereg.json` (damping and fallback);
  - `convergence_rule.json` (existing aggregate criterion, cases A–D);
  - `decision_after_3_steps.json` (case-C extension to the cap).
- **Figures:**
  - [`GTO_TERMINAL_A3_V2.png`](GTO_TERMINAL_A3_V2.png): per-step dynamics;
  - [`GTO_TERMINAL_FINAL_CENSUS_V2.png`](GTO_TERMINAL_FINAL_CENSUS_V2.png): coverage and ranking at P15.
- **Scope:** only nodes 28 and 6 carry solved continuation values; every other terminal keeps the legacy payoff. **This is not a finished GTO DB.**

## Verdict

**Not converged at the 5-measured-step cap — case C, decaying period-2** (`a3_verdict.json`).

| transition | P9→P10 (frozen) | P10→P11 | P11→P12 | P12→P13 | P13→P14 | P14→P15 |
|---|---|---|---|---|---|---|
| max main-aggregate change | 0.510 | 0.409 | 0.213 | 0.166 | 0.084 | **0.053** |
| max range L1 | 1.174 | 0.881 | 0.553 | 0.446 | 0.234 | 0.208 |

- **Criterion:** ≤ 0.005 per step, the V1/V2 aggregate fixed point. It was not reached.
- **Node 6 measured table change:** mean |ΔV|, max seat, V(k) vs V(k−1).
  - k10: 0.56
  - k11: 0.44
  - k12: 0.23
  - k13: 0.19
  - k14: **0.07** bb
- **Node 28 measured table change:** 0.021–0.028 bb at every step (its V1/V2 plateau).

## Per step

| | P9 | P10* | P11 | P12 | P13 | P14 | P15 |
|---|---|---|---|---|---|---|---|
| SB fold / raise 2.5 / jam | .367/.393/.240 | .091/.903/.007 | .368/.493/.139 | .277/.581/.142 | .361/.521/.118 | .324/.546/.130 | **.355/.501/.144** |
| BB vs SB fold / call / jam | .000/.698/.301 | .054/.755/.191 | .000/.880/.120 | .102/.667/.231 | .001/.833/.165 | .045/.750/.205 | **.014/.802/.184** |
| BB vs BTN fold / call / jam | .100/.756/.144 | .090/.766/.143 | .102/.757/.141 | .088/.772/.140 | .105/.751/.143 | .087/.776/.137 | .103/.756/.141 |
| BTN raise / jam | .368/.041 | .369/.040 | .370/.040 | .364/.043 | .371/.041 | .365/.042 | .370/.040 |
| CO raise / jam | .262/.011 | = | = | = | = | = | = |
| reach node 6 | .118 | .293 | .186 | .167 | .186 | .177 | **.172** |
| reach node 28 | .0835 | .0841 | .0841 | .0836 | .0837 | .0842 | .0841 |
| reach node 46 (3-way) | .0902 | .0915 | .0909 | .0901 | .0909 | .0904 | .0908 |
| reach node 246 (3-way) | .1047 | .1047 | .1047 | .1047 | .1047 | .1047 | .1047 |
| flop reach 2/3/4-way | .276/.199/.003 | .452/.200/.003 | .346/.199/.003 | .326/.199/.003 | .344/.199/.003 | .335/.199/.003 | .331/.200/.003 |
| preflop EV sum (bb) | +0.001 | +0.159 | +0.097 | −0.008 | +0.026 | +0.003 | +0.011 |

\* P10 = the A2.5 frozen-table solve, reused by hash.

**Damping history** (candidate α = 0.5 blend at the step's ranges, guard ±0.05 bb):

| step | node 28 candidate | node 6 candidate | node 6 previous table at new ranges | combined residual |
|---|---|---|---|---|
| k10 | −0.012 accepted | **−0.253 rejected** → measured undamped (+0.009) | −0.516 | +0.0015 |
| k11 | −0.014 accepted | **−0.235 rejected** → measured undamped (+0.009) | −0.480 | +0.0004 |
| k12 | −0.009 accepted | +0.044 accepted | +0.088 | +0.0065 |
| k13 | −0.013 accepted | −0.049 accepted | −0.099 | −0.010 |
| k14 | −0.014 accepted | +0.018 accepted | +0.029 | +0.0020 |

- **Postflop:** 720 flop solves (5 steps × 2 terminals × 72), **all converged** (≤ 0.300% pot), 0 failed.
- **Preflop gap:** 0.00027–0.00041.

## Reading

- **The SB oscillation is real and decaying.**
  - SB raise: 49 → 58 → 52 → 55 → 50%.
  - BB-vs-SB fold: 0 → 10 → 0 → 4.5 → 1.4%.
  - It started while node 6 ran undamped (k10, k11 blends rejected: stale-table mismatch after the large P9→P10 move). It shrinks once node-6 damping is active (k12–k14).
- **SB open settles far from the frozen-table 90%.** About 50% raise / 14% jam / 35% fold at P15, versus 39/24/37 at P9 (legacy node 6). The direction found in A1/A2.5 holds (more 2.5 opens, fewer jams); the size is about +11 points of raise, not +51.
- **Node 28 alone shows a small period-2 in BB-vs-BTN fold** (0.087 ↔ 0.105, ±0.009). Its table change stays at its 0.02–0.03 bb plateau. This oscillation alone exceeds the 0.005 criterion; the aggregate criterion would not be met at this panel precision even if node 6 were frozen.
- **No indirect 3-way leak.** Nodes 46/246 move ≤ 0.0013 / ≤ 0.00001 in reach; multiway flop mass 0.202 → 0.203.

## Final census at P15 (`final_census.json`)

| | P9 | P15 |
|---|---|---|
| total flop reach | 0.478 | 0.534 |
| 2 / 3 / 4-way share | 57.7 / 41.7 / 0.6% | 62.0 / 37.5 / 0.5% |
| SRP / 3bet share | 98.9 / 1.1% | 99.0 / 1.0% |
| solved flop reach (nodes 28 + 6) | 0.084 (17.5%) | **0.256 (48.0%)** |
| solved share of HU flop reach | 30% | **78%** |
| remaining legacy HU flop reach | 0.193 | 0.075 |
| remaining legacy multiway flop reach | 0.202 | 0.203 |

**Top terminals at P15:**

| rank | node | reach | type |
|---|---|---|---|
| 1 | 6 | 0.172 | solved |
| 2 | 246 | 0.105 | 3-way legacy |
| 3 | 46 | 0.091 | 3-way legacy |
| 4 | 28 | 0.084 | solved |
| 5 | 228 | 0.070 | HU legacy |
| 6 | 1371 | 0.005 | |
| 7 | 420 | 0.004 | |
| 8 | 508 | 0.003 | |

The rest are below 0.001.

**Node 6 re-check:** the A1 table at P9 ranges vs the last measured table V14 at P14 ranges.

| | SB | BB |
|---|---|---|
| range-EV shift vs legacy, A1 → V14 | +0.142 → +0.133 bb | −0.090 → −0.109 bb |
| class mean \|V14 − A1\| | 0.48 bb | 0.31 bb |

- The direction is unchanged.
- The class level moves well inside its own CI scale; the A1 class CI half-width is 0.38 / 0.51 bb.

**Next-terminal ranking** (reach(P15) × mean |solved − legacy|; proposal only, nothing injected):

| rank | node | type | reach | mean \|Δ\| (bb) | source | score |
|---|---|---|---|---|---|---|
| 1 | 246 | 3-way | 0.105 | 0.83 | proxy | 0.087 |
| 2 | 46 | 3-way | 0.091 | 0.61 | proxy | 0.055 |
| 3 | 228 | HU | 0.070 | 0.74 | measured, six-flop pilot | 0.052 |
| 4 | 1371 | HU | 0.005 | 1.86 | measured | 0.009 |

The 3-way |Δ| values are untested transfer proxies. The largest remaining legacy mass is 3-way, which has no validated solver yet (B3a FAIL, B3b wiring OK).

## Interruptions and provenance (`interruptions.json`)

- **Three container restarts** (k10 node 6, k11 node 28, k11 node 6). Resumed with provenance reuse; no data loss.
- **One operator error** (k14 node 6): a second driver ran for about 10 s.
  - Artifacts were unaffected; the k10–k13 tables were rewritten byte-identically.
  - 57 extra ledger rows were added, and the text logs of 9 flops were lost.
  - `resume_a3.sh` now refuses to start when a driver is alive.
- **Two commit messages ran ahead of the state** (`1728317`, `bcc43aa`): message inaccurate, artifacts valid.

## Kept for the production-DB decision

All per-flop solves, measured/used/rejected tables, exports, censuses and logs are kept (`convergence_rule.json` → artifact_retention). The stricter DB acceptance criterion is to be evaluated on these outputs first, with targeted validation only where it finds gaps.
