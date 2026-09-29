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

## C4. Terminal injection and the outer fixed point

**Injection.** Feature `t2-cont` (off by default), `src/preflop/t2cont.rs`:
- `terminal_value` pays `prob × (gross_h − invested_p)` at exactly one node. That node is identified by index and checked against the tree's pot and live mask.
- CFR updates and the gap checks (`traverse_checkpoint`) both go through this function, so they see the same payoff.
- Every other terminal keeps the existing payoff.

**Loop.** `tools/gto_hu_continuation/outer_loop.py` runs P_k → V_k → P_{k+1}:
- P_k: 400 preflop DCFR iterations, gap 0.0003 at every step.
- V_k: the 24-flop panel at P_k's ranges, M2 menu, ε-tremble, `ht_rho` estimator.
- Every table passed the conservation guard: at its own ranges, the two players' values summed to the pot within 0.006–0.031 bb.
- Postflop exploitability stayed ≤ 0.30% pot on every flop of every step.

Figure: [`GTO_HU_CONTINUATION_LOOP_V1.png`](GTO_HU_CONTINUATION_LOOP_V1.png).

### Undamped run (as specified: no damping until oscillation is seen)

| step | BTN open / jam | BB fold / call / jam | range L1 vs previous step (BTN / BB) | previous table at these ranges (unallocated bb) |
|---|---|---|---|---|
| P0 (static payoff) | 0.302 / 0.074 | 0.000 / 0.831 / 0.169 | — | — |
| P1 | 0.452 / 0.008 | 0.101 / 0.744 / 0.154 | 0.791 / 0.397 | −0.527 |
| P2 | 0.325 / 0.059 | 0.099 / 0.757 / 0.144 | 0.544 / 0.168 | −0.088 |
| P3 | 0.357 / 0.037 | 0.153 / 0.677 / 0.170 | 0.260 / 0.227 | +0.031 |
| P4 | 0.330 / 0.053 | 0.100 / 0.752 / 0.148 | 0.210 / 0.239 | −0.026 |
| P5 | 0.347 / 0.044 | 0.148 / 0.690 / 0.162 | 0.185 / 0.218 | +0.020 |

- **Aggregates looked like damped convergence, but class level showed a period-2 cycle.**
  - P2 ≈ P4 (L1 0.077 / 0.067) and P3 ≈ P5 (L1 0.059 / 0.051), while adjacent steps stay 0.19–0.24 apart.
  - The same marginal classes flip 0 ↔ 1 on both P2→P3 and P3→P4:
    - BB: 77, 99, A2o, K2o, T3o, JTs;
    - BTN: 85s, T8o, T7s, 43s, T9s, 97s.
  - This is the classic best-response 2-cycle: a stationary value table makes near-indifferent classes switch purely, the ranges move, and the next table pushes them back.
- The measured table change still halved each step (mean |ΔV| BB 0.187 → 0.148 → 0.077 → 0.072; BTN 0.516 → 0.165 → 0.082 → 0.057). The cycle lives in a few classes, not in the whole table.
- Per the rule, undamped was stopped after P5; the k5 panel would add no information. Under-relaxation was then run as a separate A/B.

### Damped A/B (α = 0.5, branched at k3; `outer_v1_damped_a05/`)

- The injected table is V_used_k = 0.5·V_measured_k + 0.5·V_used_{k−1}. Both tables are kept.
- Every blend passed the same guard at its step's ranges (+0.016 … +0.024 bb).

| step | BTN open / jam | BB fold / call / jam | range L1 vs previous step (BTN / BB) | measured mean \|ΔV\| (BTN / BB) |
|---|---|---|---|---|
| P3 (shared) | 0.357 / 0.037 | 0.153 / 0.677 / 0.170 | — | — |
| P4d | 0.335 / 0.048 | 0.107 / 0.735 / 0.158 | 0.145 / 0.173 | 0.047 / 0.052 |
| P5d | 0.339 / 0.046 | 0.133 / 0.702 / 0.165 | 0.044 / 0.109 | 0.015 / 0.018 |
| P6d | 0.341 / 0.046 | 0.128 / 0.712 / 0.160 | 0.053 / 0.057 | 0.033 / 0.023 |

- Aggregate frequencies now move ≤ 0.005 per step.
- Range steps are 3–4× smaller than undamped.
- The measured table change fell to 0.015–0.018 bb per class (P4d→P5d), then **stopped falling** (0.033 / 0.023 bb at P5d→P6d).
  - The floor is set by the few classes that still switch.
  - It is still 10–25× below the panel's 95% CI half-width (±0.36–0.47 bb).
- The last tables pass the guard: measured +0.023 bb, blended +0.011 bb.
- **Not converged at class level:** a few near-indifferent classes still move a lot between P5d and P6d:
  - BB: JTs, JTo, KQo (call ↔ jam), T7o, A2o;
  - BTN: 85s, 43s, T7s.
- Their mixes are unidentified at this precision. The aggregates are not affected.

**BB defence at P6d** (vs the 2bb BTN open, SB folded), an outcome, not a target:

| | value |
|---|---|
| fold | **12.8%** |
| call | 71.2% |
| jam | 16.0% |
| folds 100% | 32o, 62o, 72o, 82o, 92o, T2o, J2o, Q2o, 85o, T5o, J5o |
| folds partially | T4o 98%, 42o 93%, K2o 69%, 72s 67%, T7o 31% |

- The static model's 0.000 fold came from a structural artifact, and it is gone once the terminal pays solved postflop values.
- BTN open settles at ≈ 0.34 raise + 0.046 jam, versus 0.302 + 0.074 under the static model.
- CO and SB do not change. That is by construction: only the BTN–BB terminal is injected.

## Conclusions of the prototype

1. **The mechanism works and was not forced.**
   - Solved postflop values make the trash offsuit classes realize 31–39% of pot × equity; premiums realize > 2×.
   - Fed back into preflop CFR, they produce BB folds (0 → ≈ 13%) through the regrets alone.
2. **The internal-consistency criteria were met.**
   - Value-convention invariants hold per flop (≤ 7e-8) and per table (≤ 0.031 bb, after the aggregation fix).
   - Postflop exploitability is ≤ 0.30% pot throughout.
   - The fixed point is reached at aggregate level with α = 0.5 (frequencies ±0.005 per step). The table change plateaus at 0.02–0.03 bb; the class level is not converged.
3. **Precision, not correctness, is now the constraint.**
   - The 24-flop panel gives per-class 95% CIs of ±0.36–0.48 bb, and the two estimators differ per class by up to 2 bb.
   - Near-indifferent classes therefore cannot be resolved; they cycle undamped and drift damped.
   - A larger panel (same strata, more draws per stratum; cost ≈ 2.5 min per flop per outer step on 4 cores with M2) is the direct lever.
4. **Model inputs that remain and must be reported with any number:**
   - the postflop menu (M2 single-size; the M1 two-size menu needs 20 GB in f32);
   - the zero-reach definition (ε-tremble; the BR band is ≤ 0.033 bb here);
   - the missing inter-player card removal in preflop (≈ ±0.02–0.05 bb per table);
   - one injected terminal only.
5. **Not established:** any GTO DB frequency. The 4-handed game still prices every other terminal (3-way pots, 3bet pots, SB pots) with the old model.

## Next steps (proposed, not started)

1. **Panel precision.**
   - Panel v2 with 4–6 draws per stratum.
   - Re-run the damped loop from the P6d state and check that the class mixes of the unresolved classes stabilise.
   - Report the CI of BB fold % across bootstrap tables.
2. **Menu sensitivity.** M1 on a sub-panel (compressed storage, ≈ 50 min per flop) at the P6d ranges, compared with M2 per class.
3. **Generalise the terminal set** before any 9-max step:
   - SB-open → BB-call;
   - CO-open → BB-call;
   - BTN-open → SB-call.
   - Then check how the 3-way terminals interact, since they remain on the old model.
4. **Joint CFR** (upstream `integrated_continuation` style) as the reference method, to confirm the damped fixed point without the stationary-value assumption.

---

# v1.1 — error decomposition before scaling (J1–J3)

Instruction for this phase:
- Do not enlarge the panel or add terminals yet.
- First separate the error of the value-construction method from the sampling error.

Question: *is the error of the continuation method itself smaller than the flop-sampling error?*

## J0. Constraints found before running

**Joint CFR cannot run on the 24-flop panel in 16 GB.** It holds every flop's postflop solver at once:
- M2 needs 2.14 GB per flop in f32 (1.07 GB compressed);
- 24 flops therefore need 51 GB f32 or 26 GB compressed.

J1 and J2 therefore use a **pre-registered 6-flop sub-panel**, `panel_sub6_v1.json` (sha256 `33ebbea5…`):

| texture | flop |
|---|---|
| monotone | Jc6c2c |
| paired | 6d6c3c |
| rainbow dry | Kc7d4h |
| rainbow connected | Tc9d5h |
| two-tone dry | AcKd5d |
| two-tone connected | Qc9d7d |

- Selection rule: one flop from panel_v1 per texture category, all top ranks distinct.
- A first candidate with loose texture labels was replaced before any J1/J2 result.

**HT/ρ fails the conservation guard on 6 flops.**
- On the 24-flop runs' data it gives up to 0.11 bb unallocated. The class-normaliser variability does not average out over 6 flops.
- Both methods on the sub-panel therefore use a **fixed class-independent normaliser**: Σ_f w_f Σ_h r_h c_hf evaluated once at the P6d ranges (BTN 0.8790, BB 0.8803).
- Because it is fixed, there is no own-range feedback. It passes the guard (≤ 0.021 bb on every stored step).

**Storage.**
- Joint CFR must use compressed (i16/u16) storage: 6.4 GB for 6 flops.
- The outer fixed point's flop solves are f32.
- Measured on Kc7d4h, M2, P6d ranges, target 0.3% pot (`j2/quant_*`):

| per-class \|f32 − compressed\| | BB | BTN |
|---|---:|---:|
| mean | 0.050 bb | 0.055 bb |
| max | 0.43 bb | 0.27 bb |

- Compressed is also 1.5× slower (233 s vs 154 s).
- This **storage band** is the floor below which no method difference is interpreted.

## J1. Outer fixed point vs joint CFR (identical 6-flop game, M2)

**Joint CFR** (`t2-joint` feature, `examples/t2_joint.rs`, `preflop/t2joint.rs`):
- At the one terminal, each postflop solver on the panel runs one alternating DCFR update per role per preflop iteration. It uses the *current* preflop reaches: own reach feeds the strategy sums; opponent reach × folded seats' mass feeds the counterfactual weights.
- It returns current-strategy CFVs, turned into the same per-class gross functional.
- The joint-game gap uses postflop best response and average values separately.
- 500 iterations from scratch.
- A first run was lost to a container restart at iteration 200. The re-run reproduced its checkpoints 50–200 bit-for-bit.

**Outer fixed point:**
- Undamped k0–k4 showed **the same period-2 cycle** as on 24 flops, with a larger amplitude: BB fold 0.250 / 0.187 / 0.281 / 0.206.
- Damping was then applied from k3 (α = 0.5) up to k6.
- A first attempt that damped from k1 was **refused by the conservation guard**: the blend was −0.32 bb at P1, because V0 is stale after the large first move. That was a protocol deviation (damping before observing oscillation) and is recorded in `outer_sub6_fp_a05_rejected_k1/`.

Figure: [`GTO_HU_J1_COMPARE_V1.png`](GTO_HU_J1_COMPARE_V1.png). Numbers: `data/gto_hu_continuation/j1/compare_j1.json`.

| | damped outer fixed point (k6) | joint CFR (500 it) |
|---|---|---|
| CO open / jam | 0.262 / 0.011 | 0.262 / 0.012 |
| BTN open / jam | 0.356 / 0.047 | 0.358 / 0.046 |
| SB open / jam | 0.393 / 0.240 | 0.395 / 0.239 |
| BB vs BTN: fold / call / jam | 0.242 / 0.591 / 0.166 | 0.246 / 0.586 / 0.168 |
| arriving-range distance (BTN / BB) | — | L1 0.025 / 0.034 |
| convergence | preflop gap 0.00037; last table change 0.023–0.027 bb | joint-game gap (incl. postflop BR) 0.00085, still falling |
| postflop exploitability (max over panel) | 0.29% pot (per-flop fixed-range solves) | 0.088% pot |
| conservation (unallocated) | +0.037 bb | +0.039 bb |
| cost | 42 flop solves, 1.6 h + 7 preflop solves ≈ 1.7 h; peak ≈ 2.4 GB | 2.0 h; 6.7 GB |

**(a) Aggregates agree; only marginal classes differ.**
- Aggregates agree within 0.002, except BB fold/call at 0.004–0.005.
- Class actions differing by > 0.1: 7 BB classes and 5 BTN classes. None differ by > 0.5.
- The largest are mixed, near-indifferent classes:
  - BB: Q4o fold 0.04 vs 0.54; 84s call/jam 0.39/0.61 vs 0.02/0.98; J9o;
  - BTN: T7s, T8o, A5s.

**(b) The continuation values themselves agree.**
- Weighted by the arriving range, the mean |ΔV| is BTN 0.019 bb and BB 0.011 bb.
- Over all 169 classes, joint best-response value vs the fixed-point table: mean 0.014 / 0.017 bb, max 0.056 / 0.060 bb.
- Both are **inside the storage band** (mean 0.05, max 0.27–0.43 bb).

**(c) Zero-reach handling.**
- Joint CFR needs no ε in the regret path: CFVs of every hand come from its current, regret-matched postflop strategy.
- For *reporting*, however, its average-strategy value of a never-reached hand is the solver's uniform-fallback play. That is off by 1.0 bb (BTN, 21 classes) and 1.6 bb (BB, 48 classes).
- The joint **best-response** value of those hands matches the fixed point's ε-tremble value within 0.009 / 0.025 bb.
- So ε-tremble (fixed point) and current-strategy CFVs (joint) are consistent. Uniform-fallback averages must never be exported as continuation values.

**(d) The period-2 cycle does not appear in joint CFR.**
- The largest class-strategy change per 50 iterations falls monotonically: 0.54 → 0.25 → 0.14 → 0.07 → 0.03.
- Aggregates approach the damped fixed-point values from one side (BB fold 0.330 → 0.246).
- The cycle is an artefact of stationary value tables plus pure best responses of near-indifferent classes, not a property of the game.

**J1 verdict.**
- On an identical game, the damped outer fixed point and joint CFR reach the same strategy structure and the same continuation values within the storage-quantisation band.
- Their disagreement is confined to near-indifferent classes, and is smaller than any other error source measured below.
