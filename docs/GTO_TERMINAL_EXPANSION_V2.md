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
