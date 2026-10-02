# A4c report: 144 → 232 / 218 boards (node 6 / node 28), downstream-aware nested extension at P14 ranges

Prereg `data/gto_terminal_expansion/a4c/prereg.json` (dfd9c78) + amendment 1 (joint cross-terminal draws, f12ed9e) + registered
diagnostics (marginal approximation, Kc9h9d LOBO). 162 is not a production acceptance threshold. Figure: `docs/GTO_TERMINAL_A4C_V2.png`.

## 1. Solve integrity
- 162/162 new flops: **161 target-converged + 1 prereg-approved capped exception** (node6/Kc9h9d, 1000 iterations, 0.3025% pot;
  `a4c/exception_nonconverged_1.json`, exact sha256 whitelist, threshold not relaxed). Max exploitability otherwise 0.2989%; mean 0.26% / 0.24%.
- V144 rebuilt from the panel = stored 144 table exactly (0.0, both terminals). G144 re-solve identical to the A4b export.
- Numerical: max floating identity 6.5e-11 ≤ 1e-9; classification unchanged under ±1e-9.
- Bootstrap: 60/60; `a4c/boot_verify.json` PASS — **bootstrap draw assignment / replay / restart integrity verified** (every replicate's
  tables equal those rebuilt from its own draw; 60 distinct draws, 120 distinct profiles; interrupted replicate 38 and control 5 re-run
  bit-identical). Statistical independence is not tested by the script; it rests on the seeded RNG design.

## 2. Allocation / boards
As preregistered: node 6 232 (+88), node 28 218 (+74), 55 shared new boards; CPU 14.1 h + 10.3 h.

## 3. Refinement (Gext − G144, point)
SB first-in raise 0.549 → 0.592 (+4.3 pp), fold −3.0 pp, jam −1.3 pp; BB vs SB fold +1.8 pp, call −2.5 pp, jam +0.7 pp;
BTN first-in jam +0.3 pp; BB vs BTN fold −0.4 pp. CO unchanged (< 1e-6).

## 4–5. Out-of-sample test (same 60 FPC replicates; ratio = L_ext / L_144)
| metric | measured ratio | predicted (calibrated) | L_ext (bb/hand) | L_ext / predicted equal-24 |
|---|---|---|---|---|
| seat BTN | 0.42 | 0.46 | 0.00045 | 0.96 |
| seat SB | 0.51 | 0.53 | 0.00234 | 1.18 |
| seat BB | 0.51 | 0.58 | 0.00217 | 0.99 |
| regret BTN first-in | 0.40 | 0.46 | 0.00057 | 0.91 |
| regret BB vs BTN | 0.54 | 0.58 | 0.00646 | 1.02 |
| regret SB first-in | **0.62** | 0.53 | 0.00681 | **1.38** |
| regret BB vs SB | 0.44 | 0.58 | 0.00509 | 0.86 |
| regret SB vs BTN (diagnostic) | 0.25 | 0.60 | 0.00005 | 0.51 |

Seat ratios within 0.02–0.07 of prediction (all slightly better). The SB seat misses the predicted equal-24 absolute level by 18% because this
bootstrap's L_144 (0.00461) is above the pre-analysis pooled value (0.00374); its ratio matched. SB first-in regret is the one formal miss
(ratio 0.62 vs 0.53). Equal-24 itself was not measured. Bootstrap q05–q95 of L_ext are wide (e.g. SB 0.0012–0.0036).

## 6. SB vs BTN (diagnostic)
5.1e-5 bb/hand, q05 < 0 — at the residual floor; no action.

## 7. FPC ±2% (paired strata)
Loss change ≤ 0.28% (BTN 0.16%, SB 0.28%, BB 0.26%) — negligible.

## 8. Hand-level stability
Bootstrap (policy of replicate into its point game), mean reach-weighted strategy L1 (L1 = Σ|Δfreq|, so 0.22 ≈ 11% of mass moved):

| node | 144 | ext |
|---|---|---|
| BTN first-in | 0.114 | 0.075 |
| SB vs BTN | 0.037 | 0.021 |
| BB vs BTN | 0.282 | 0.240 |
| SB first-in | 0.339 | 0.216 |
| BB vs SB | 0.299 | 0.226 |

Point 144 ↔ ext: policy-argmax switch 12.1% (BB vs BTN), 11.2% (BB vs SB), 6.6% (SB first-in), 5.7% (BTN first-in), 2.4% (SB vs BTN) of reach.
EV-level precision is ~0.2 bb/100 per seat; action frequencies at the two BB nodes and SB first-in are not yet stable at this panel size.
Part of this is near-indifference: Kc9h9d LOBO moved J2s SB first-in from raise 0.39 / jam 0.61 to 0.63 / 0.37 with 5.7e-6 bb regret change.

## 9. Panel error vs frozen-range proxy
L_ext / proxy: BTN 0.89, SB 0.69, BB 0.99 (at 144: 2.1, 1.36, 1.94). Panel error no longer dominates; panel and outer-loop
(self-consistency) error are now of the same size.

## Registered diagnostics
- Marginal approximation (amendment 1 split vs pooled new-board resample), variance ratio median / 5% / min: table node 6 0.983 / 0.952 / 0.920,
  node 28 0.996 / 0.971 / 0.952; reach-weighted value 0.992 / 0.997. Recorded only.
- Kc9h9d LOBO: seat-swap dEV ≤ 6.8e-6, regret excess ≤ 2.9e-5, L1 ≤ 0.0075, one policy-argmax switch (J2s, 0.3% reach). The whole board's
  influence is small; its 0.0025 pp solver residual is a practical non-issue (not a rigorous bound).
- Continuity label: EV-sensitive (as expected before results), stable under ±1e-9.

## 10. PNG
`docs/GTO_TERMINAL_A4C_V2.png` checked directly: three panels render (predicted vs measured ratios; panel vs proxy; 144 ↔ ext hand regret).

## Conclusion
1. The downstream-aware allocation predicted out-of-sample error reduction well for all three seats and 3 of 4 formal regret nodes;
   SB first-in regret fell less than predicted.
2. With 162 new solves it reached the predicted equal-24 level for BTN and BB seat EV and for 3 regret nodes, not for the SB seat / SB first-in.
3. Panel error is now comparable to the outer-loop proxy, so further panel-only work has diminishing returns.
4. EVs are usable at ~0.2 bb/100 precision; class-level action frequencies at BB vs BTN, BB vs SB and SB first-in are not (≈11% mass moves).
The A4c loop ends here (no top-up). This is a 4-handed 30bb HU-terminal research result, not a production GTO table.
