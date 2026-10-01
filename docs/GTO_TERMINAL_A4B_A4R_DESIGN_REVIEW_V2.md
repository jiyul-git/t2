# A4b / A4R independent design review (before any F144 or A4R result)

**Scope.**
- Independent check of three things:
  - the A4b blend correction (amendment 1, `1792020`);
  - the A4R metric in `a4r_robust/prereg.json`;
  - the proposal to judge A4R against the existing solver error budget.
- Inputs: the code and artifacts only. No F144 table, F144 solve, bootstrap or A4R evaluation existed when this was written.
- 144-board flop solves continue. The downstream preflop chain is gated behind `a4b_panel144/DOWNSTREAM_APPROVED`, which is not set.

## 1. Blend correction

### Checked directly

| item | result |
|---|---|
| `step_k14_summary.json` | both terminals `blend_candidate_accepted: true`, α = 0.5. Unallocated: node 28 measured −0.0090 → used −0.0137 bb; node 6 +0.0067 → +0.0180 bb |
| P15 manifest | both `k15/terminal_node*.json` were solved with `k14/manifest.json`, which lists `k14/used_node28.json` and `k14/used_node6.json` (not `table_measured`) |
| loader | `t2cont.rs` reads only `seats[].gross` from each manifest entry |
| A3 driver | `outer_loop_multi.py` blends gross, CI lo/hi and br as `α·x + (1−α)·y` with y = previous used. Guard: \|unallocated\| ≤ 0.05 bb at the step's ranges. On failure it falls back to the measured table undamped; if the measured table also fails, hard stop |
| 0.5·V14_72 + 0.5·M13 (M13 = `k13/used_node*.json`) | **bit-identical** to `k14/used_node*.json`: gross, CI and br, both terminals |
| F72 = preflop solve on that table | **exact** P15 reproduction: main aggregates, gaps, EVs, ranges hash, and every export field except the manifest path (`review/F72_identity/identity.json`) |
| `t2_cross_eval` on the F72 save under its own tables | gaps and EVs exact |

### Answers

1. **Is the correction structurally right?**
   - **Yes, as a statement about the A3 data flow:** P15 = g(M14), not g(V14).
   - The original pre-registration's justification ("at a fixed point used = measured") does not apply, because A3 is sealed as not converged.
   - **No, as a conclusion about what A4b must compare.** See 4.
2. **Bit-exact reproduction of used14:** yes.
3. **Exact reproduction of P15:** yes.
4. **Is the same rule on 144 boards justified?** Algorithmically it is well defined. Statistically it does not answer the panel-precision question.
   - **The 72-board history stays in.** M14_144 = 0.5·V14_144 + 0.5·M13. Half the weight sits on M13, a geometric mixture of V10..V13, all measured on the same 72 boards. Those boards' errors are coherent across steps (A4 resampled them jointly for exactly that reason). Refining only V14 removes at most half of the panel error from the input. F_M144 − P15 therefore contains about 0.5·g′·(V14_144 − V14_72): the refinement effect is diluted, not isolated.
   - **The amended bootstrap keeps M13 fixed.** It therefore propagates only the 0.5·V14 noise. It understates the panel uncertainty of P15 that A4 measured with the full chain, so its h72 is not comparable to A4's.
   - **M13 is not an estimate of any game.** It is a step-size (damping) device of the outer iteration, built from tables at P10..P13 ranges. The estimand of a continuation DB is the table at the current ranges, V(P14), not a damped history.
5. **Better comparison: a decomposition.** Report three differences, not one.

   | quantity | measures |
   |---|---|
   | g(V14_144) − g(V14_72) | **panel refinement** at fixed (P14) ranges: the precision question |
   | g(V14_72) − g(M14_72) = g(V14_72) − P15 | **damping / staleness**: P15's distance from the response to its own current-range table (non-convergence) |
   | g(M14_144) − g(M14_72) | the A3-process counterfactual (amendment 1's comparison): what P15 would have been had k14 measured on 144 boards |

   The first is the primary A4b quantity. Its reference distribution is the V-type bootstrap: V14 on resampled boards, no blend.

## 2. A4R metric

Current pre-registered metric: L(σ;T) = gap_total(σ;T) − gap_total(σ_T;T). Here `gap_p` is seat p's best-response gain against the others' fixed average strategies (`gaps_and_evs`), and `gap_total` is their sum (NashConv).

| question | finding |
|---|---|
| Is L the EV loss of a fixed policy? | **No.** The two NashConv terms are taken against different opponent profiles (σ_−p vs σ_T,−p), so the best-response values do not cancel. L is a difference of two distances to equilibrium, not a regret |
| Can L be negative? | Yes, whenever σ happens to be closer to equilibrium of T than the 400-iteration σ_T. That says nothing about EV |
| Sum over seats vs per seat? | The sum mixes seats whose decisions are untouched (CO is identical by construction) with SB/BB, where the node-6 effect lives. It must be reported per seat |
| Cross-evaluation direction | The deployed object is one seat's policy facing opponents. The clean quantity holds the opponents fixed and swaps only seat p's strategy (below) |
| Symmetric cross-eval? | Useful as a check: truth is unknown and both tables are estimates. The robustness distribution matters more (policy fixed, plausible tables varied) |
| Near-indifference | Pair a frequency distance with the seat-swap EV loss. A large frequency change with an EV loss inside the preflop solver floor means near-indifference: frequency not identified, EV identified |

**Seat-swap loss (exact by construction).** For game G with its own solve σ_G and a candidate policy A:

Δ_p(A; G) = u_p(σ_G; G) − u_p(A_p, σ_G,−p; G) = gap_p(A_p ⊕ σ_G,−p; G) − gap_p(σ_G; G)

- Both profiles share σ_G,−p, so seat p's best-response value is identical and cancels exactly. The difference is the EV seat p loses by playing A instead of σ_G against the same opponents, in bb per hand.
- Bounds: −gap_p(σ_G;G) ≤ Δ_p ≤ gap_p(A_p ⊕ σ_G,−p;G).
- A negative value is possible only up to σ_G's own seat gap, i.e. solver convergence.
- **Feasibility:** `PNode.data_off`, `actor`, `actions` and `nodes` are public, and the save is a header plus the regret and strat_sum arenas. A splice of seat p's blocks therefore needs no solver-library change.
- **Validation:**
  - (i) splice(σ_G's own p into σ_G) is bit-identical to σ_G;
  - (ii) u_p + gap_p (the best-response value) agrees between σ_G and the splice;
  - (iii) splicing every seat from A reproduces A.

**Games.** V-type tables (point and bootstrap at P14 ranges), not M-type: M is not an estimate of the game.

**Limitation.** All of this is the frozen-table game at P14 ranges. A policy that moves ranges changes the true continuation values, which needs new postflop solves and is not measured.

## 3. "Compare with the existing solver error budget"

The postflop `exploitability_pct_pot` (`best_response.rs`) is the **average of the two players' BR gains** in one flop subgame, divided by pot. The subgame NashConv is therefore 2·ε·pot.

**What can be converted.** Hold the preflop profile fixed and let the two postflop players deviate inside the solved subgames. The resulting NashConv contribution, in bb per hand dealt, is

B_post = Σ_n reach_n · 2 · ε̄_n · pot_n

with ε̄_n the panel-weighted mean.

| | reach (P15) | pot | ε̄ (k14, 72 flops) | B_post at ε̄ | B_post at 0.30% target |
|---|---|---|---|---|---|
| node 6 | 0.172 | 6.0 | 0.260% | 0.0054 | 0.0062 |
| node 28 | 0.084 | 5.5 | 0.245% | 0.0023 | 0.0028 |
| total | | | | **0.0076** | 0.0090 |

The preflop solver's own NashConv at P15 is 0.00035 (per seat 0.7–1.0 × 10⁻⁴).

**What cannot be converted.**
- **ε does not bound per-class table values.**
  - ε bounds range-weighted values: each player's subgame value under an ε-equilibrium is within 2ε·pot of the game value.
  - It does not bound per-class values (non-unique equilibria, near-zero-reach classes).
  - A preflop deviation concentrates on classes, so ε gives no rigorous bound on the preflop policy loss caused by table error.
- **B_post is a different quantity.** It is the exploitability of the postflop play, not the loss of a preflop policy caused by value-estimation error. The preflop game uses table values only.
- **Panel sampling error is a different kind of error.**
  - It is a random estimation error of V around the all-flop average. Solver error is a deterministic, bounded per-flop error.
  - Bounded errors add linearly across terminals; this triangle inequality is valid for worst-case bounds.
  - Random errors add in quadrature under independence, which does not hold here (A4: same boards at every step).
  - Putting both into one budget is a modelling choice, not a derivation.

**Conclusion.**
- There is currently **not enough basis to fix a production acceptance threshold as a single number.**
- B_post and the preflop floor are legitimate *references*: "below the preflop solver floor" is a detectability statement, and "below the existing postflop exploitability contribution" is a ranking of error sources. Neither is an acceptance criterion.
- The 0.005 / 0.02 bb/hand thresholds in `a4r_robust/prereg.json` were arbitrary and are withdrawn. 0.005 happened to be close to a mis-scaled version of B_post (missing the factor 2), which is not a justification.

## 4. Additional problems found

1. **Nested-panel calibration.**
   - The 144-board panel contains the 72. For the iid-within-stratum model, Var(x̄144 − x̄72) = Var(x̄144), so the shift should be scaled by sd144, not by h72.
   - "|shift| ≤ h72" is an implicit |z| ≤ 2.77 test without a multiplicity statement.
2. **Non-linear bias** (the A4 finding that replicates are not centred on P15). g(V̂) is biased by an amount that scales with Var(V̂), so it halves from 72 to 144. Part of the shift is therefore expected bias change, not error. Report bootstrap bias estimates (mean(boot) − point) at both sizes.
3. **30 replicates:** percentile 95% intervals are the 2nd-smallest / 2nd-largest values. SDs are the steadier statistic.
4. **Resampling vs drawing.** The panel was drawn without replacement, proportional to raw-flop counts; the bootstrap resamples with replacement and equal weight within strata. This is approximate, as in A4.
5. **Profile saves** are 2.4 MB each. Bootstrap saves (about 60) are kept out of git (`*.gtop` ignored). They are regenerable bit-exactly: the deterministic re-solve is shown exact.
6. **Frozen-table limitation** (section 2) applies to every A4R number.
7. **Two container restarts** today. The driver now refuses to start beside a live driver, and the downstream steps are gated.

## 5. Recommended measurement (D) and how to use it (E)

**A4b (primary):**
- Point solves: g(V14_72), g(V14_144), plus g(M14_144) as the A3-process counterfactual. g(M14_72) = P15 is reproduced exactly.
- V-type bootstrap with 30 replicates per panel, profiles saved.
- Report per main aggregate:
  - the shift S = g(V144) − g(V72), with z = S / sd144;
  - a Bonferroni-adjusted reading over m aggregates with sd > 1e-3: z* = Φ⁻¹(1 − 0.05/(2m));
  - the staleness term g(V72) − P15;
  - the counterfactual g(M144) − P15;
  - bias estimates at 72 and 144.
- Readings: "consistent" if every |z| ≤ z*, else "inconsistent", recorded as-is.

**A4R:**
- Δ_p(A; G) per seat, with the three validations above. Policies A ∈ {P15, g(V72), g(V144)}; games G ∈ {V72, V144} points and their bootstrap replicates (each replicate's own solve is σ_G).
- Also report NashConv(A; G) next to NashConv(σ_G; G) as the raw worst-case exploitability, without subtracting.
- Pair each Δ_p with the reach-weighted L1 frequency distance at the SB first-in and BB-vs-SB nodes, to separate near-indifference from real EV change.

**Production reading:**
- No PASS/FAIL. Per seat, Δ_p is classified only as:
  - **"below the preflop solver floor"**: Δ_p ≤ gap_p(σ_G; G), not detectable with this solver;
  - otherwise reported with its magnitude next to B_post (0.0076 bb/hand) as a ranking reference.
- The production criterion stays open (the user's).
- 288 boards are never started automatically. If Δ is above the floor and the frequencies are not near-indifferent, the report gives the expected 288 effect (√n scaling) and its cost, then waits.
