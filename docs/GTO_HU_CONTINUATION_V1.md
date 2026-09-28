# HU continuation value v1 — postflop-solved terminal values for the preflop solver

Branch `claude/gto-hu-continuation-v1-20260928` (from audit commit 711f281).

**Scope.** One mechanism prototype:
- the 4-handed CO/BTN/SB/BB full legal tree (max_raises 4), 30bb, 1bb total ante;
- the single HU terminal **BTN open 2bb → SB fold → BB call**.

This isolates the continuation mechanism; it is **not** a strategy cut for speed. Every other terminal keeps the existing payoff, so no RFI from this prototype is a GTO DB value. The public RFI is a sanity marker only, never a target.

**Success criteria (fixed before any result).** Internal consistency of the continuation game:
- value-convention invariants;
- postflop solve quality (exploitability per flop);
- flop-panel CI;
- fixed-point convergence.

BB fold frequency is reported as an outcome. It is not a target.

---

## C0. Upstream code read before writing anything

Files read:
- `examples/range_value_reference.rs`
- `examples/integrated_continuation.rs`
- `examples/continuation_zero_reach.rs`
- `examples/continuation_joint.rs` (header)
- `src/preflop/continuation.rs`
- `src/best_response.rs` (`traverse_avg`, `traverse_br`, `exploitability`)
- `src/cfr.rs` (`iterate`, `research_continuation_sweep`)
- `src/game.rs` (`Spot`)
- `docs/preflop_balanced_model.md`
- `docs/preflop_modeling_research.md` §4

The research history (`tools/research`, `research/*`, `cache/realization_fit.json`) is **not** in the vendored snapshot, so the upstream pilots' results cannot be inspected; only their code.

### What upstream already did

| artifact | method | value convention | zero-reach hands |
|---|---|---|---|
| `range_value_reference` (GPU) | Fixed-range HU postflop solve; per-class `ev` from `node_view` plus per-class `br_ev` from `exploit_view` | **gross pot share**; asserts `mean_OOP + mean_IP = pot` (zero rake) | **excluded** (`w <= 0 → continue`); no value produced |
| `integrated_continuation` (GPU, `preflop-research`) | **Joint CFR**: a small HU preflop tree + postflop spots on a fixed board panel, one postflop CFR+ sweep per preflop iteration with the current preflop ranges (`research_continuation_sweep`) | postflop engine's native **half-pot utility**, converted with `+ (pot/2 − invested)`; asserts EV sum + rake = dead money | spots are built with **all hands**; preflop regrets use the CFV of every hand under its **current (regret-matched) postflop strategy**; the gap uses `traverse_br` |
| `continuation_zero_reach` | Diagnostic only: counts HU terminals where a traverser's own reach is 0 while opponents' is positive | — | defines no value |
| `continuation.rs` (`continuation_estimate`) | Read-only diagnostic of the existing heuristic pricing | gross pot share, labelled "not a solved postflop value" | — |
| upstream docs §4 | Engine validation: BB defence vs a BTN open is **84% (positional heuristic) / 97% (raw) / 37% (calibrated fit) vs solver 35–40%** at 100bb | — | — |

Upstream therefore reached the same diagnosis at 100bb: **"the postflop model decides blind-defence width."** Their fix (`calibrated` / `balanced`) is a fitted per-class factor. The file is absent here, and upstream notes it embeds training rake.

The warning in `terminal_value` also stands: feeding back *context multipliers* (initiative, range equity) as correlates let the solver "buy the aggressor premium" (100% opens). So any range dependence must come from actually solving with those ranges, never from a regression feature.

### C0 decisions

**1. Value conventions (sealed).** Every stored value names its convention, and each convention has its own invariant. Conventions are never mixed in one check.

| `value_convention` | definition (bb) | invariant at zero rake |
|---|---|---|
| `gross_share` | expected chips of the terminal pot (incl. dead money) that the hand ends with, given the opponent's range | Σ over live players of range-weighted mean = **pot** (weights = joint reach with card removal) |
| `net_chip_delta` | gross_share − own preflop investment (incl. own ante) | Σ over **all seats** (folded seats contribute −their investment) = **0** |
| `postflop_half_pot_utility` | engine native: chips relative to having put pot/2 in | Σ over the two live players = **0** |
| `counterfactual_value` | per-hand value × opponent reach mass (unnormalized; what CFR consumes) | Σ_p Σ_h own_reach_h · cfv_h = pot × joint mass (gross form) |

The artifact stores `gross_share` per class plus the pot and investments, so the other forms are derived, not stored separately.

**2. Zero-reach hands.** The BR value is not adopted up front. Three definitions are measured in C2, and one is chosen on theory plus data:

| id | definition | property |
|---|---|---|
| (a) `avg_uniform_fallback` | CFV under the postflop *average* strategy; a hand with zero own reach has a zero strategy sum, so it plays uniformly at random | **biased low** (random play) |
| (b) `hand_br` | hand-level best response against the opponent's fixed average postflop strategy | Nash-deviation value in the limit; **biased high** by the opponent's residual exploitability when not converged |
| (c) `eps_tremble_avg` | re-solve with every class's reach floored at ε (trembling), then CFV under the average strategy | every hand has a learned strategy; perturbs the opponent by O(ε) |

- In-range hands use their equilibrium (average) CFV; the difference between (b) and the average is a direct measure of the solve's exploitability share.
- Theory: for a stationary continuation value, the preflop regret of "call with h" should be h's value when h plays sequentially rationally against the opponent's fixed postflop strategy. That is (b) in the limit, which is also what upstream's joint CFR converges to through current-strategy CFVs.
- (c) should approach (b) from below as the solve converges.
- The choice rule, fixed now: **use (c) if max_h |(b) − (c)| ≤ the per-flop exploitability bound; otherwise report the disagreement and keep both as a sensitivity band.** (a) is kept only as a diagnostic.

**3. Two ways to close the loop:**
- the requested **outer fixed point** (preflop solve → ranges → postflop panel → values → preflop solve …, undamped first);
- upstream's **joint CFR**, which avoids stationarity assumptions but needs a postflop sweep per preflop iteration.

The prototype runs the fixed point (CPU, batchable). The joint CFR is noted as the reference method if the fixed point oscillates or disagrees.

**4. Tooling.**
- Use the CPU postflop `Solver` directly: `Spot::new` with all 1326 combos, then overwrite the public `spot.weights` with the terminal's class-uniform reach (zeros allowed), then `iterate`, `exploitability`, `traverse_avg`, `traverse_br`.
- No `preflop-research`/GPU feature is needed. No upstream research code is copied; the examples were read for definitions only.

---

## C1. Terminal extraction (`t2_cont_terminal`)

- **Solve.** 4-handed CO/BTN/SB/BB, 30bb, max_raises 4, uniform ante 0.25 (1bb total), eq 1200 / seed 202, static payoff everywhere. 400 DCFR iterations reach gap_total 0.00031. Config: `data/gto_hu_continuation/cfg_4h_mr4_30bb.json`.
- **Terminal.** Path fold, raise 2, fold, call → node reached with pot 5.5bb, 28bb behind (SPR 5.09), aggressor BTN. Postflop OOP is BB, IP is BTN.
- **Arriving ranges** (average strategy, class level, `c1_terminal_btn_bb.json`, ranges hash `b4890f18751c20b8`):

| seat | combos | classes with reach > 0 | zero-reach classes |
|---|---:|---:|---|
| BTN | 30.2% | 107 | e.g. 53s, 63s, 64s, 73s, 74s, 82s–84s (not opened) |
| BB | 83.1% | 152 | 77+, AJs+, … (17 classes that 3bet or jam instead of calling) |

The BB's zero-reach classes are premiums. Their continuation value is exactly what the preflop regret of "call instead of 3bet" needs.

## C2. Cost of one flop (`t2_cont_flop`, board Ks7d2c)

**Tree size** (all 1326 combos in the hand list; 1176 per player after board removal):

| menu (pre-registered) | tree nodes | action nodes | arena f32 | arena i16/u16 | fits the 16 GB container? |
|---|---:|---:|---:|---:|---|
| M1 standard (33/75, 50/100, 50/100; raises 2.5×; all-in; 2 raises) | 2,427,621 | 884,815 | 20.1 GB | 10.1 GB | f32: no (the first attempt was OOM-killed); compressed: yes |
| M2 single (50% per street, raise = all-in, 1 raise) | 263,733 | 101,632 | 2.14 GB | 1.07 GB | yes |

- M1 was registered as the primary menu before any cost was known. It cannot run in f32 here.
- **Amendment, made before any value result was seen:** M2 is the prototype's working menu. M1 is kept as the sensitivity menu (compressed storage) and its cost is measured below.
- The choice of menu is a model input and is reported as such.

**M2 solve (4 threads, DCFR, isomorphism on):**

| item | value |
|---|---|
| build | 0.43 s |
| solve to target 0.3% pot | 150 iterations, 275 s |
| exploitability | 0.288% pot (0.016 bb) |
| peak RSS | 2.35 GB |
| CFV query (avg + BR + equity, both players) | 2.8 s |
| per-hand CFV stored | 1176 floats per player per flop; class table 169 per player |
| ε-tremble second solve | 150 iterations, 266 s, 0.245% pot |

**Extrapolation (M2, 4 threads):**
- All 1,755 canonical flops × 1 solve ≈ 1755 × 4.5 min ≈ **132 h** per outer iteration. Not feasible.
- The pre-registered 24-flop panel ≈ **1.8 h** per outer iteration.

**Invariant.** At the solve's own ranges, the gross shares sum to the pot to −1.6e-8 bb.

**Zero-reach definitions on this flop** (decision rule C0-2):

| player | in-range max(BR − avg) | in-range max \|ε − avg\| | zero-reach BR − ε (min … max) | zero-reach ε − uniform-fallback (max) |
|---|---:|---:|---:|---:|
| BB (OOP) | 0.097 bb | 0.040 bb | 0.013 … 0.105 bb | 0.012 bb |
| BTN (IP) | 0.032 bb | 0.057 bb | −0.002 … 0.088 bb | 0.027 bb |

- On zero-reach classes, BR and ε-tremble differ by no more than the solve's own per-hand residual on in-range classes (BR − avg up to 0.097 bb).
- **Decision:** ε-tremble (c) is the primary value, from **one ε-floored solve per flop** (ε = 1e-3). That solve's in-range values differ from the unfloored solve by ≤ 0.06 bb. BR (b) is kept per class as a sensitivity band.
- The uniform fallback (a) was also close on this flop, but it has no theoretical standing and is dropped.

**Board realism check** (BB OOP on Ks7d2c):
- 72o has equity 0.85 (two pair) and gross 9.98 bb, realization 2.14× the pot·equity proxy.
- T5o has equity 0.14 and gross ≈ 0.00 bb: it folds and realizes nothing.
- The raw-equity terminal instead gives every hand pot·equity·0.95.

## C3. Panel values and the conservation check (outer step k0)

**Panel.** 24 flops, 12 strata × 2 (`panel_v1.json`, seed 20260928, sha256 `4bec9015…`); fixed before any value was seen.

**Per-flop solves.** One ε-floored solve per flop at the k0 ranges, M2 menu, target 0.3% pot, 4 threads:
- 66–302 s per flop (monotone ≈ 70 s; unpaired offsuit boards up to 5 min); the whole panel took ≈ 1 h.
- Exploitability is 0.20–0.30% pot on every flop.
- The per-flop invariant (gross sum = pot at the solve's ranges) holds to ≤ 7e-8 bb on every flop.

**An aggregation error was caught by the invariant.** The first aggregation used the class-conditional *ratio* estimator Σ_f c_hf v_hf / Σ_f c_hf, where c_hf is the share of class-h combos not blocked by the board. Evaluated at the preflop arriving ranges, it gave Σ = 5.853 bb for a 5.5 bb pot: **0.353 bb of chips created**.

Decomposition, flop by flop:

| weighting of that flop's class values | invariant error per flop |
|---|---|
| joint reach incl. opponent blockers (valid mass) | ≤ 7e-8 (exact) |
| board-removal only (combos on board × keep) | −0.044 … +0.057 bb |
| preflop class reach (no removal at all) | +0.12 … +1.30 bb |

- The ±0.05 bb residual is the preflop model's own missing inter-player card removal. It cannot be removed without combo-level preflop.
- The 0.35 bb came from the estimator. On a 24-flop panel the per-class normaliser Σ_f P(f) c_hf ranges from 0.766 to 0.969, whereas over all 1,755 flops it equals exactly 19600/22100 = 0.887 for every class.
- **Fix:** divide by that exact constant (`ht_rho`, a Horvitz–Thompson estimator). It is the same estimator for the full flop set and keeps conservation on a panel. The ratio estimator stays in the artifact as `gross_ratio` (sensitivity).
- **Guard:** the aggregator now refuses to write a table with |unallocated| > 0.05 bb. The rejected k0 table is kept as `k0/table_ratio_rejected.json`.
- The two estimators differ per class by up to 2 bb (mean 0.21–0.25 bb). That is a direct measure of how little a 24-flop panel pins down individual classes.

**k0 table** (`outer_v1/k0/table.json`, estimator `ht_rho`):
- unallocated **+0.020 bb** (0.36% of pot);
- 95% CI half-width averaged over classes: BTN ±0.38 bb, BB ±0.53 bb (stratified bootstrap, B = 2000);
- max per-class (BR − ε) value: BTN 0.028 bb, BB 0.033 bb.

What the solved continuation says about BB defence at the k0 ranges:
- The fold/call boundary is gross = 1.0 bb: calling leaves the BB with 2.25 bb invested, folding loses 1.25 bb.
- **13 BB classes are below it** at the point estimate; **4 have their whole 95% CI below it** (72o, 82o, 92o, T2o).
- Those classes realize **31–39%** of pot × equity. Example: 72o gross 0.45 bb (CI 0.19–0.69) against 1.35 bb under the static model.
- Premiums realize far more than their equity share because they win future bets: AA 2.42×, KK 2.19×.
- Nothing forces a fold: this is the solved value. Whether the preflop solve then folds these hands is measured in C4.
