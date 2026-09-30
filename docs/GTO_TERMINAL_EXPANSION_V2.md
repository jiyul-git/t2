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
