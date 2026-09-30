# GTO terminal expansion v2 — start from the 72-flop P9 state

Baseline: `8393f9913f2fbc803fba47f4135d3d514d6cbcd6`  
Work branch: `chatgpt/terminal-census-v2-20260930`

## Decision after the 72-flop study

Do **terminal expansion before another panel enlargement**.

Reason:
- 72 flops reduced the corrected sampling CI to about 0.32 bb (BTN) / 0.47 bb (BB), but one continuation terminal is still the only solved terminal.
- BB is still sampling-limited inside that one terminal.
- BTN is already near the point where action abstraction matters.
- Spending the next large compute block only on 144 flops would refine one terminal while every other flop-reaching terminal still uses the legacy payoff.

The next panel should use a newly pre-registered allocation (for example the proposed Neyman allocation), but only after the terminal-coverage census and first expansion pilots. Do not retrofit weights into the completed 72-flop panel.

## Exact starting state

The final reported preflop state is **P9**:

- ranges hash: `d8707f750f1f9ec2`
- gap_total: `0.00045716747132362777`
- BTN: fold 0.591381 / raise 2bb 0.367696 / jam 0.040924
- BB vs BTN-open terminal parent: fold 0.099905 / call 0.755859 / raise 7bb 0.0000027 / jam 0.144233

Important indexing detail:

- `k9/terminal.json` is **P9**.
- P9 was solved using **`k8/table.json`**.
- `k9/table.json` is V9, which would produce P10 if injected into a fresh preflop solve.

Therefore the census must reproduce P9 with:

`T2_CONT_FILE=data/gto_hu_continuation/panel72/outer_v2_damped_a05/k8/table.json`

Do **not** use k9/table.json for the P9 census.

## T0 — enumerate every flop-reaching terminal

Tool:

`vendor/gtopen/crates/solver/examples/t2_cont_census.rs`

It enumerates every preflop pot-share terminal with:
- at least two live players;
- positive effective stack behind.

For each terminal it records:
- exact node id;
- exact action-index path and labels;
- live mask and positions;
- aggressor;
- raise depth (limped / SRP / 3bet / 4bet / ...);
- pot, effective stack and SPR;
- per-seat average-strategy reach mass;
- joint terminal reach proxy;
- share of total flop-reaching mass;
- whether it is the currently injected terminal.

The reach proxy intentionally matches the existing class-level preflop abstraction and therefore carries the same missing inter-player card-removal caveat.

### Run at P9

From `vendor/gtopen`:

```bash
PREFLOP_EQ_SEED=202 \
PREFLOP_MULTIWAY_SEED=202 \
PREFLOP_EQ_SAMPLES=1200 \
T2_CONT_FILE=../../data/gto_hu_continuation/panel72/outer_v2_damped_a05/k8/table.json \
cargo run --release -p solver --example t2_cont_census --features t2-cont -- \
  ../../data/gto_hu_continuation/cfg_4h_mr4_30bb.json \
  400 \
  ../../data/gto_terminal_expansion/census_p9.json
```

Before interpreting the census, confirm that the same solver settings reproduce the known P9 diagnostics above. If they do not, stop and investigate provenance before ranking terminals.

## T1 — reach-only ranking is provisional

Helper:

`tools/gto_hu_continuation/rank_terminal_census.py`

Example:

```bash
python3 tools/gto_hu_continuation/rank_terminal_census.py \
  data/gto_terminal_expansion/census_p9.json \
  --exclude-current --top 30 \
  --json-out data/gto_terminal_expansion/rank_reach_p9.json
```

This is only a screening pass.

The final expansion score must include the error of the legacy payoff:

[
I_t = P(t) 	imes
sum_{p,h} 	ilde r_{t,p,h}
left|V^{solved}_{t,p,h}-V^{legacy}_{t,p,h}ight|.
]

A frequent terminal with a good legacy approximation can rank below a less frequent terminal with a large continuation error.

## T2 — six-flop impact pilots

Take the leading HU candidates from the census and run the same fixed six-texture panel used for J1/J2:

- monotone
- paired
- rainbow dry
- rainbow connected
- two-tone dry
- two-tone connected

Do not start each new terminal at 72 flops.

For each candidate record:
- reach probability and share of flop-reach;
- mean and reach-weighted (|V^{solved}-V^{legacy}|);
- signed range-EV shift;
- affected preflop action boundaries using the new action-EV diagnostics;
- solve cost;
- conservation error;
- postflop exploitability.

Then pass the measured mean absolute delta into `rank_terminal_census.py --impact ...`.

## T3 — synchronous multi-terminal fixed point

Once the terminal set is selected, update them **synchronously**.

Correct outer step:

[
P_k
ightarrow
{R_{t,k}}_{tin T}
ightarrow
{V_{t,k}}_{tin T}
ightarrow
P_{k+1}.
]

Every selected terminal range must come from the same P_k.

Do not:
1. solve terminal A,
2. inject A and re-solve preflop,
3. then measure terminal B,
and call that one outer step.

That creates order dependence because A changes B's arriving range before B is measured.

## T4 — multi-terminal loader

Only after T0/T2 identifies the set, generalize the current single `T2_CONT_FILE` loader.

Keep backward compatibility with the current table schema and add a manifest mode, for example:

```json
{
  "schema": "t2_hu_continuation_manifest_v1",
  "tables": [
    {"file": "terminal_28.json"},
    {"file": "terminal_143.json"}
  ]
}
```

Required fail-closed guards:
- table schema and gross-share convention;
- unique terminal node;
- exact node match;
- exact live mask;
- pot match within 1e-9;
- 169 finite values for every live seat;
- no duplicate node entries.

Lookup should be node-indexed; live-mask and pot guards remain mandatory.

## Coverage metrics

After each terminal-expansion phase report:
- solved HU flop-reach / all HU flop-reach;
- solved total flop-reach / all flop-reach;
- remaining legacy HU mass;
- remaining legacy multiway mass;
- coverage split by SRP / 3bet / 4bet.

This is necessary because once some HU terminals are solved, the solver must not gain an artificial advantage by routing strategy toward still-legacy terminal families.

## Provisional candidate families

Before the P9 census exists, likely HU candidates remain:

1. SB open -> BB call;
2. CO open -> intervening folds -> BB call;
3. BTN open -> SB call -> BB fold.

This ordering is **not sealed**. The P9 census plus six-flop solved-vs-legacy impact score decides the actual order.

After the high-impact single-raised HU terminals, inspect HU 3bet-call pots before doing broad multiway expansion. Multiway must still be measured in the census because it can become an artificial legacy-payoff escape route as HU coverage increases.

---

## T0 result — P9 census (run 2026-09-30)

Files:
- `data/gto_terminal_expansion/census_p9.json`: full census.
- `rank_reach_p9{,_hu}.{json,txt}`: reach-only ranking, provisional.
- `census_p0_legacy.json`: the same census at P0 (no injection), for comparison.

### Code review of `t2_cont_census.rs`

No defect was found in the enumeration, the reach definition or the all-in filter.

Three additions, all read-only:
- **`p9_verification`**: the injected terminal's ranges hash (same FNV as `t2_cont_terminal`) and the aggregate mixes along its path, computed inside the census process.
- **`summary.reach_check`**: the reach mass of every terminal kind. Fold-win + no-flop pot-share + flop must sum to 1. This validates the reach definition.
- **`summary.by_pot_type`**: terminal counts and HU/multiway reach per pot type, plus the number of terminals with reach > 0 and > 1e-6.

### P9 reproduction: exact

- Ranges hash `d8707f750f1f9ec2`. `gap_total` 0.00045716747132362777 is bit-identical, and so are gaps and evs.
- Mixes match `k9/terminal.json`:
  - BTN fold 0.5913807 / raise 0.3676956 / jam 0.0409237;
  - BB fold 0.0999054 / call 0.755859 / 3bet 0.0000027 / jam 0.1442329.
- An independent `t2_cont_terminal` re-run with the same `T2_CONT_FILE` (`k8/table.json`) also reproduces `k9/terminal.json` exactly.
- The census at P0 reproduces `outer_v1/k0` (gap 0.0003111254470083314).

### Census

- **Reach check:** flop 0.4784 + fold-win 0.4263 + all-in/no-flop 0.0954 = **1.0000002**.
- **Terminals:** 181 flop-reaching (all with reach > 0, only **18 > 1e-6**); 238 fold-win; 604 pot-share without a flop.

| family | terminals | flop-reach share |
|---|---:|---:|
| SRP HU | 6 | 56.7% |
| SRP 3-way | 4 | 41.6% |
| SRP 4-way | 1 | 0.6% |
| 3bet HU | 22 | 1.05% |
| 3bet 3-way | 14 | 0.06% |
| 4bet (all) | 131 | 0.0006% |
| limped / 5bet | 0 | 0 |

- HU 57.7% / multiway 42.3%.
- SRP 98.9% / 3bet 1.1% / 4bet ≈ 0.
- **Solved node 28** (BTN open → SB fold → BB call): reach 0.0835, **17.5%** of flop reach, rank 4.
- **Concentration:** the top 5 terminals carry 97.4% of flop reach, the top 10 99.95%.

### Structural findings

1. **41.6% of flop reach is SRP 3-way, all legacy.** The HU postflop pipeline cannot solve these pots.
   - node 246 (CO open → SB call → BB call) is 21.9%.
   - node 46 (BTN open → SB call → BB call) is 18.9%.
2. **The BB never folds after an SB flat.**
   - node 45 (BTN open → SB call → BB fold) and node 245 (the CO-open equivalent) have reach ≈ 0.
   - Every SB flat therefore becomes a 3-way pot.
   - The SB flats the BTN open 43% of the time at P9 (fold 41%, jam 16%, 3bet 0.06%).
3. **Mass moved into the legacy 3-way terminal after node 28 was solved** (P0 → P9):
   - node 46 reach 0.063 → 0.090 (+43%);
   - node 28 0.088 → 0.084, although the BTN opens more (0.30 → 0.37);
   - HU share of flop reach 62.3% → 57.7%.
   - This is the "legacy escape route" anticipated above, now measured. It is not yet separated from the other P0→P9 changes, because both states differ in the whole injected table.
4. **3bet pots are rare and shallow.**
   - HU 3bet flop reach is 1.05% in total, 0.999% of it node 1371 (CO open → BTN 3bet 6 → CO call; SPR 1.66).
   - 3bets other than the jam are almost unused at 30bb: SB 3bet 7 = 0.06%, BB 3bet 7 = 0.0003%.
   - 4bet flop terminals exist structurally (131) but carry 6e-6 of the reach at SPR 0.5.
5. **Class-level reach proxy.** Reach is class-level, so it carries the preflop model's missing inter-player card removal.

### Reach-only screening of HU candidates (provisional, not the expansion order)

| # | node | path | pot / SPR | reach | flop share |
|---|---|---|---|---:|---:|
| 1 | 6 | CO fold → BTN fold → SB open 2.5 → BB call | 6.0 / 4.58 | 0.1180 | 24.7% |
| 2 | 228 | CO open 2 → BTN fold → SB fold → BB call | 5.5 / 5.09 | 0.0696 | 14.5% |
| 3 | 1371 | CO open → BTN 3bet 6 → SB, BB fold → CO call | 14.5 / 1.66 | 0.0048 | 1.0% |
| 4 | 135 | BTN open → SB 3bet 7 → BB fold → BTN call | 16.0 / 1.44 | 8.5e-5 | 0.018% |
| 5 | 1382 | CO open → BTN 3bet → BB call → CO fold | 15.5 / 1.55 | 6.9e-5 | 0.014% |
| 6 | 9 | SB open → BB 3bet 8.8 → SB call | 18.5 / 1.15 | 2.5e-5 | 0.005% |

**Implication for T2.**
- With a per-class legacy error of a few tenths of a bb, reach × |Δ| can only be competitive for nodes 6, 228 and, marginally, 1371.
  - 1371 would need a Δ about 15–25× that of the SRP terminals.
  - 1371 has SPR 1.66, where the legacy equity-share payoff should be closest to the truth.
- Candidates 4–6 are listed for completeness. Their reach is 3–4 orders of magnitude too small to matter at P9.
- The larger coverage question is the 3-way family (41.6%), which needs a different continuation method than the HU solver.


## T0 result — P9 census

Census completed on the P9 state and reproduced the sealed diagnostics exactly.

Key distribution:
- 181 flop-reaching terminals in the tree; only 18 have reach > 1e-6.
- HU = 57.7% of flop reach.
- multiway = 42.3% (3-way 41.7%, 4-way 0.6%).
- SRP = 98.9%; 3bet = 1.1%; 4bet = 0.0006%.
- solved node 28 = 17.5% of flop reach.
- top five terminals = 97.4% of flop reach.

Dominant unsolved terminals:
- node 6, SB open -> BB call, HU SRP: 24.7%
- node 246, CO open -> SB call -> BB call, 3-way SRP: 21.9%
- node 46, BTN open -> SB call -> BB call, 3-way SRP: 18.9%
- node 228, CO open -> BB call, HU SRP: 14.5%

The two dominant unsolved HU terminals (6 + 228) cover about 39.2% of flop reach.
The two dominant 3-way terminals (246 + 46) cover about 40.8%.

### Structural consequence

The current preflop multiway terminal is not a solved postflop continuation. For 3+ live
players it uses `coupled_deck_v1`: a pot-conserving coupled showdown-equity model over
the arriving class distributions. There is no postflop betting tree or positional
realization adjustment in that branch.

Therefore a solved HU terminal and a legacy 3-way terminal are values from different
models. The observed P0 -> P9 movement toward node 46 is consistent with a possible
routing/escape effect, but does not by itself prove how much of the movement is caused by
the model mismatch.

The vendored postflop solver is explicitly heads-up only, so nodes 46/246 cannot simply be
passed through the existing HU continuation pipeline.

## T2 revised next step

Run two workstreams in parallel.

### A. HU impact pilots — existing solver, low risk

Run the fixed six-flop pilot on:
1. node 6 (SB vs BB SRP)
2. node 228 (CO vs BB SRP)
3. node 1371 only as the representative 3bet HU control if compute is cheap

Measure solved-vs-legacy values and feed them into the terminal impact ranking. Do not
promote them to 72 flops yet and do not implement the multi-terminal loader yet.

### B. 3-way legacy-mismatch diagnostic — research only

Target node 246 and node 46 first because together they cover ~40.8% of flop reach.

Before building any production 3-way solver:
1. export exact arriving ranges, invested amounts, pot, SPR, acting order and aggressor;
2. reproduce the current coupled-deck legacy values exactly;
3. quantify which preflop decisions feed each terminal and their action-EV margins;
4. define a restricted 3-way postflop research game and its validation criteria before
   looking at solved values;
5. keep all resulting 3-way values out of production until conservation, determinism,
   best-response/regret diagnostics and sensitivity to the action menu are understood.

Because multiplayer no-limit is not covered by the existing heads-up exploitability
framework, do not label an approximate 3-way research solution as GTO or mix it into the
production DB without a separate validation standard.

### Decision gate after A/B

- If HU nodes 6/228 have large impact scores and the 3-way mismatch diagnostic is small,
  continue HU terminal expansion first.
- If the 3-way mismatch is material, pause broad HU expansion and build a validated
  multiway continuation approximation before allowing more solved HU mass to redirect into
  legacy 3-way paths.

---

## T2-A result — HU six-flop impact pilot (P9)

Numbers: `data/gto_terminal_expansion/pilot6/analysis.json`. Figure: [`GTO_TERMINAL_PILOT6_V2.png`](GTO_TERMINAL_PILOT6_V2.png).

**Setup** (identical for every terminal):
- P9 arriving ranges (`T2_CONT_FILE=k8/table.json`).
- M2 f32, ε-tremble, target 0.3% pot.
- panel_sub6 boards and weights, with the terminal's own fixed normaliser computed from its ranges before any solve (`pilot6/panel_node*.json`).
- Legacy = the solver's own P9 terminal payoff with injection bypassed (`legacy_gross`).

**Solves:** 24, 0 failed, all converged (≤ 0.30% pot).
- The node 28 reference flops are bit-identical to the k9 artifacts of the same boards.
- Runtime: 9–11 min per SRP terminal, 4 min for node 1371 (4 workers).

| | node 28 (solved; reference) | **node 6** SB–BB SRP | **node 228** CO–BB SRP | node 1371 CO–BTN 3bet |
|---|---|---|---|---|
| reach / flop share | 0.0835 / 17.5% | 0.1180 / 24.7% | 0.0696 / 14.5% | 0.0048 / 1.0% |
| pot / SPR | 5.5 / 5.09 | 6.0 / 4.58 | 5.5 / 5.09 | 14.5 / 1.66 |
| mean \|solved − legacy\| (OOP / IP) | 0.71 / 0.48 | 0.63 / 0.97 | 0.74 / 0.74 | 1.21 / 2.51 |
| reach-weighted \|Δ\| (OOP / IP) | 0.62 / 0.47 | 0.61 / 0.72 | 0.67 / 0.55 | 1.04 / 2.84 |
| signed range-EV shift (OOP / IP) | BB −0.41 / BTN +0.36 | SB +0.29 / BB −0.25 | BB −0.54 / CO +0.45 | CO −0.55 / BTN +0.45 |
| solved ÷ legacy range EV (caller) | BB 0.80 | BB 0.90 | BB 0.71 | CO 0.89 |
| unallocated: solved / legacy (bb) | −0.009 / −0.059 | +0.006 / +0.055 | +0.010 / −0.080 | +0.036 / −0.069 |
| postflop exploitability max | 0.26% | 0.30% | 0.29% | 0.29% |
| **impact = reach × mean \|Δ\|** | 0.050 | **0.094** | **0.051** | 0.009 |
| impact, reach-weighted \|Δ\| (Σ seats) | 0.091 | **0.157** | **0.085** | 0.019 |

Preflop decisions whose best action flips when legacy is replaced by the six-flop solved value (other strategies fixed at P9):
- **node 6:** SB open node 67 classes (38% of SB mass); BB 102 classes (61%).
- **node 228:** CO open 20 classes (11%); BB 98 classes (58%).
- **node 1371:** BTN 3bet node 34 classes (16%); CO call node 84 classes (49%).

Reading:
- **Pilot noise.** The node 28 six-flop values differ from the 72-flop k9 table by 0.30 / 0.43 bb mean per class.
  - That is the six-flop sampling noise, and it inflates every mean |Δ| above.
  - A rough deconvolution (√(|Δ|² − noise²)) leaves roughly 0.71 / 0.65 / 0.48 bb for nodes 6 / 228 / 28. The ranking is unchanged.
  - The signed range-EV shifts (0.25–0.55 bb) exceed the range-level noise (±0.11 bb).
- **Legacy bias.** The static-r legacy overvalues the caller and undervalues the aggressor or IP player in every HU terminal: caller range EV is 10–29% too high.
  - The legacy HU payoff is also not pot-conserving (−0.08 … +0.055 bb).
- **Ranking** (both variants): **node 6 > node 228 ≈ node 28 (already solved) ≫ node 1371**.
  - Node 6's impact is about 1.9× node 28's.
- **The earlier expectation for node 1371 was wrong.**
  - I wrote that at SPR 1.66 the legacy payoff "should be closest to the truth". The per-class error is in fact the largest: 1.2 / 2.5 bb, or 8% / 17% of the pot.
  - Its impact stays about 10× below node 6 only because of reach.

## T2-B result — legacy 3-way diagnostic (nodes 46, 246)

Numbers:
- `data/gto_terminal_expansion/mw_legacy/analysis.json`;
- `transfer_proxy.json`;
- terminal exports at P9 and P0 in `terminals/`.

**1. Arriving state at P9** (pot 7.0, behind 27.75, SPR 4.0; postflop order SB, BB, aggressor):

| node | aggressor | range mass / classes in range | static r |
|---|---|---|---|
| 46 (BTN open, SB flat, BB call) | BTN | BTN 0.368 / 126, SB 0.430 / 133, BB 0.785 / 143 | BTN 1.04, SB 0.96, BB 1.00 |
| 246 (CO open, SB flat, BB call) | CO | CO 0.262 / 86, SB 0.547 / 157, BB 0.856 / 150 | CO 1.04, SB 0.96, BB 1.00 |

- The static r is **not used** by the 3-way branch; only HU uses it.
- Normalised 169-class ranges, invested amounts and behind for every live seat are in the exports.

**2. Legacy 3-way payoff reproduced independently, bit-identically.**
- `coupled_deck_ref.py` rebuilds the 1,024-particle table from the published algorithm: RNG, shuffles, per-class sampled combos, board = first five remaining deck cards, 7-card ordering, Gauss–Legendre 2-point rule.
- It matches the solver's f64 value **bit for bit** for all 3 seats × 2 nodes × {P0, P9}.
- It matches `terminal_value` (f32) within 1.5e-7 bb.
- The model is exactly pot-conserving (unallocated 0.0000).
- What it computes: each class's share of the pot = its coupled-deck showdown equity against the other live seats' independent class distributions.
  - No betting, positional realization, fold equity or card removal between the seats.
- P9 range EVs: node 46 BTN 2.93 / SB 2.26 / BB 1.81; node 246 CO 3.13 / SB 2.10 / BB 1.77.

**3. Decisions feeding the 3-way terminals (P9)**
- SB flat vs the BTN open: 0.430 (fold 0.413, jam 0.156, 3bet 0.0006).
  - 74 classes mostly flat, with a reach-weighted margin over the best alternative of 0.16 bb; 19 of them are within 0.05 bb.
- **BB after the SB flat: fold 0.000**, call 0.785, jam 0.214.
  - The 122 calling classes have a reach-weighted margin of **0.48 bb** over folding or jamming.
  - The weakest calling class is still better than folding. Example: 72o call −0.92 vs fold −1.25.
- The same holds on the CO path (node 246): the SB flats 0.547, the BB folds 0.000, and the calling margin is 0.51 bb.
- The contrast is large. After an SB **fold**, the BB folds 10% against the BTN (node 28, solved). After an SB **flat**, it folds 0% into the legacy 3-way pot.

**4. P0 → P9 decomposition.** Reach = product of the per-decision reach factors, so the log change splits exactly:

| node | reach P0 → P9 | CO | BTN | SB | BB |
|---|---|---|---|---|---|
| 46 | 0.0630 → 0.0902 (+43.3%) | 0 | **+0.197** (open 0.302 → 0.368) | **+0.164** (flat 0.365 → 0.430) | −0.001 (0.787 → 0.785) |
| 28 | 0.0881 → 0.0835 (−5.2%) | 0 | +0.197 | −0.156 (fold 0.483 → 0.413) | −0.095 (call 0.831 → 0.756) |
| 246 | 0.1047 → 0.1047 (0.0%) | 0 | 0 | 0 | 0 |

- **55% of node 46's growth is the wider BTN open.** It raises node 28 and node 46 alike and is the intended effect of solving node 28: BTN solved values are higher than legacy.
- **45% is the SB flat (+17.8% relative).**
  - The SB's legacy node-46 value, over its P9 flatting range, rose by +0.049 bb when the BTN distribution alone was moved P0 → P9. Moving the BB distribution changed it by −0.001 bb.
  - So the flat increase is the SB exploiting a wider, weaker BTN range inside a payoff that pays raw equity.
- **The BB side changed only where the payoff was solved:** its call at node 28 fell 0.831 → 0.756. Its 3-way call (0.787 → 0.785) did not change.
- **Node 246 is exactly unchanged.** No decision on the CO path touches node 28, so nothing moved there.
- **Answer.** The escape route is real but indirect.
  - Solving node 28 did not push the BB into the 3-way pot; the BB never folds there in either state.
  - It widened the BTN range. Under the legacy equity-share payoff the SB then profits by flatting more.
  - The share of flop reach that is priced by the legacy 3-way model grew accordingly: node 46 from 13.6% to 18.9% of flop reach.

**5. Structural error of the 3-way payoff — a proxy, not a measurement.**
- **Assumption (untested):** HU solved realization transfers by role. The aggressor takes the HU aggressor's per-class realization; both callers take the HU caller's.
  - Node 28 k9 for the BTN path; node 228 pilot for the CO path.
  - Renormalised to conserve the pot.

| | node 46 | node 246 |
|---|---|---|
| mean \|proxy − legacy\| (aggressor / SB / BB) | 0.77 / 0.53 / 0.51 | 0.98 / 0.77 / 0.75 |
| range-EV shift (aggressor / SB / BB) | +0.70 / −0.33 / −0.37 | +0.89 / −0.37 / −0.52 |
| SB: share of mass whose best action is the flat, legacy → proxy | 0.42 → 0.21 | 0.54 → 0.31 |
| BB: share whose best action is the overcall | 0.78 → 0.53 | 0.86 → 0.43 |
| impact proxy = reach × mean \|Δ\| (3 seats) | 0.055 | 0.087 |

- If the assumption holds, the 3-way legacy error is of the **same order as the largest HU terminals**, and it sustains the 0% BB fold and part of the SB flat.
- In a real 3-way pot the callers' realization is plausibly lower still (squeezed, multiway), so the proxy is not an upper bound.
- It is not a lower bound either: 3-way fold equity and card removal are not in it.

## T2-C — 3-way research game: design only (nothing built, nothing enters production)

**Goal.** Measure, for nodes 46 and 246, how far the coupled-deck value is from a strategic 3-way continuation, under a pre-registered validation standard. It is not a GTO claim.

**Game (restricted, fixed before any value is seen):**
- One flop panel (panel_sub6), exact P9 arriving 169-class ranges expanded to combos.
  - Card removal between all three seats is exact, which the coupled deck lacks.
- Streets: flop, turn and river, with the M2-like menu: one 50% pot bet, raise = all-in only, at most one raise per street, no donk distinction.
- Once a player folds, the continuation is a HU subgame. It can be delegated to the existing vendored HU solver and cached, keeping the 3-player part small.
- **Size estimate** (sequence counting, to be replaced by a build-only measurement):
  - One M2 street has 3 continuing HU sequences out of 13, against 10 continuing 3-way sequences (4 three-handed + 6 into HU) out of 55.
  - A full 3-way tree is therefore about 10× the HU tree, ≈ 20 GB f32. That does not fit this 15 GB machine.
  - Fallbacks, in order:
    1. HU subgames solved separately and substituted as values;
    2. compressed storage with BR values, since ε values are known to break under compression (J2);
    3. turn/river chance sampling (external-sampling MCCFR).

**Algorithm.** 3-player CFR (DCFR or CFR+ with alternating updates; MCCFR if chance sampling is needed). It converges to a coarse correlated equilibrium, not to Nash; this is stated with every number.

**Validation standard.** HU exploitability does not apply, so all of the following must hold before a value is reported:
1. **Conservation:** Σ_players gross = pot at every terminal and in aggregate (zero rake), to 1e-6.
2. **Per-player best-response gain** δ_i = BR_i − u_i against the others' average strategies (the NashConv terms), in % pot. Tracked for convergence; required to plateau below a threshold fixed before the run.
3. **Average external regret** per player, bounding the CCE gap. Monotone decline required.
4. **Determinism** (identical re-run) and **seed / sampling sensitivity** (MCCFR seeds, particle order): per-class value spread reported, required below the six-flop sampling noise (≈ 0.3 bb).
5. **HU degeneracy test:** with one seat's range forced to fold, the engine must reproduce the vendored HU solver's node-28-type values within the storage band (≈ 0.03 bb).
6. **Showdown limit test:** with all betting removed, it must reproduce exact-card-removal showdown equity. This also measures the coupled deck's own card-removal error separately from its missing betting.
7. **Menu sensitivity:** a second menu (e.g., 33/75 pot) on a subset. Report the spread, as J2 did for HU.
8. **Stability across checkpoints:** per-class values at 50/75/100% of the iteration budget.

**Order of work:**
1. Build-only size and memory measurement.
2. Tests 5 and 6 on one flop.
3. One flop of node 46.
4. The six-flop panel for nodes 46 and 246.
5. Compare with legacy and with the transfer proxy above.

**Nothing enters the preflop solver until tests 1–6 pass and the numbers are reviewed.**

## Decision after T2-A/B (measured, criteria not changed)

- **HU node 6 has the largest measured impact** (0.094 / 0.157), ≈ 1.9× the terminal already solved.
  - Its branch (SB open → BB call) has **no 3-way sibling**, so solving it cannot open a legacy escape route.
- **HU node 228 has an impact similar to node 28** (0.051 / 0.085).
  - It has the 3-way sibling node 246: SB flat after the CO open. Node 28 showed that solving such a terminal moves mass into its 3-way sibling (via the aggressor's wider range).
- **The 3-way legacy payoff is exactly reproduced and structurally equity-only.** Its error is unmeasured; the transfer proxy puts it at the size of the largest HU terminals (0.055 / 0.087).
- **Proposal: both, with a specific split.**
  1. Add node 6 next; it is escape-free.
  2. Start the 3-way research game (T2-C) in parallel.
  3. Hold node 228 until the 3-way continuation for node 246 is at least measured, because 228 feeds 246.
  4. Leave node 1371 and the other 3bet terminals aside (impact ≤ 0.02).
