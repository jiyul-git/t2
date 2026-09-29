# GTO terminal expansion v1 — census before multi-terminal injection

Branch: `chatgpt/terminal-census-20260929`

## Purpose

The HU continuation prototype established that solved postflop continuation values can
replace the structural error in the legacy terminal payoff.  The next task is to expand
coverage without choosing terminals by intuition or creating order-dependent results.

This phase does **not** change the production payoff yet.  It first measures the complete
set of flop-reaching preflop terminals under the current solution.

## Why terminal expansion must be synchronous

Do not update terminal A, re-solve preflop, then measure terminal B and call the result a
single expansion step.  A changes B's arriving range before B is measured.

For a selected terminal set T, one outer step must be:

[
P_k
ightarrow {R_{t,k}: t in T}
ightarrow {V_{t,k}: t in T}
ightarrow P_{k+1}.
]

All ranges (R_{t,k}) are extracted from the **same** preflop solution (P_k), and all
continuation tables (V_{t,k}) are injected together into (P_{k+1}).

Sequential terminal insertion is allowed only as a diagnostic A/B and must not be used as
the production fixed-point definition.

## T0 — terminal census

New tool:

`vendor/gtopen/crates/solver/examples/t2_cont_census.rs`

It solves the existing preflop game, enumerates every pot-share terminal that:

- has at least two live seats; and
- has positive effective stack behind, so a postflop decision tree actually exists.

For each terminal it records:

- exact node id;
- exact action-index path;
- human-readable action labels;
- live-seat mask and positions;
- aggressor;
- raise count and pot family (limped / SRP / 3bet / 4bet / ...);
- pot, effective stack and SPR;
- per-seat average-strategy reach mass;
- terminal reach probability;
- share of all flop-reaching mass;
- whether it is the terminal currently supplied by `T2_CONT_FILE`.

The reach definition intentionally matches the existing preflop abstraction:

[
P(t)=prod_p sum_h r_{p,h}(t).
]

It therefore has the same known missing inter-player card-removal effect as the preflop
model.  It is a ranking statistic, not a claim of exact physical hand frequency.

### Run

From `vendor/gtopen`:

```bash
PREFLOP_EQ_SEED=202 \
PREFLOP_MULTIWAY_SEED=202 \
PREFLOP_EQ_SAMPLES=1200 \
T2_CONT_FILE=../../data/gto_hu_continuation/outer_v1_damped_a05/k6/table.json \
cargo run --release -p solver --example t2_cont_census --features t2-cont -- \
  ../../data/gto_hu_continuation/cfg_4h_mr4_30bb.json \
  400 \
  ../../data/gto_terminal_expansion/census_p6d.json
```

The `T2_CONT_FILE` line is optional.  With it, the census ranks the *remaining*
terminals after the BTN-open / SB-fold / BB-call correction.

## T1 — ranking protocol

A terminal must not be promoted only because it is frequent.

First-stage ranking is reach-only:

[
C_t = P(t).
]

That ranking is explicitly provisional.

For the leading candidates, run the same pre-registered six-flop texture pilot used in
J1/J2 and measure the per-class solved-vs-legacy continuation difference.  The primary
impact score is:

[
I_t =
P(t)
	imes
sum_{p,h} 	ilde r_{t,p,h}
left|V^{solved}_{t,p,h}-V^{legacy}_{t,p,h}ight|.
]

Here (	ilde r) is the normalized arriving range inside terminal t.

The repository helper:

`tools/gto_hu_continuation/rank_terminal_census.py`

accepts an impact JSON and ranks by:

`reach_probability * mean_abs_solved_minus_legacy_bb`.

Without an impact file it prints a reach-only ranking and labels it provisional.

### Coverage metrics that must always be reported

- solved HU flop-reach mass / all HU flop-reach mass;
- solved total flop-reach mass / all flop-reach mass;
- remaining legacy HU mass;
- remaining legacy multiway mass;
- coverage split by SRP / 3bet / 4bet.

This prevents the solver from silently preferring terminal families that still use the
legacy payoff.

## T2 — pilot promotion rule

For a candidate terminal, use the fixed six-flop texture set first.

Record:

- reach probability;
- mean and reach-weighted (|V^{solved}-V^{legacy}|);
- range-EV shift;
- affected preflop decision boundaries;
- solve cost;
- invariant error;
- postflop exploitability.

Do not promote a terminal merely because one hand class moves a lot.

Priority is driven by total expected impact and boundary effects together.

A candidate is promoted to the larger panel only if either:

1. its impact score is material relative to already-solved terminal families; or
2. it changes an important preflop decision boundary despite modest range-level EV.

Thresholds are to be registered before the pilot results are viewed.

## T3 — provisional candidate families

Before the census result exists, the likely first HU candidates are:

1. SB open -> BB call;
2. CO open -> intervening folds -> BB call;
3. BTN open -> SB call -> BB fold.

This is **not** the final ranking.  Census reach and six-flop solved-vs-legacy error can
reorder them.

After single-raised HU coverage, inspect HU 3bet-call terminals before indiscriminately
expanding expensive multiway solves.

Multiway cannot be left on the legacy payoff indefinitely: once a substantial fraction of
HU terminals are solved, legacy multiway paths can become an artificial escape route.

## T4 — multi-terminal loader requirements

The eventual loader must preserve backward compatibility with the current
`T2_CONT_FILE` single-table path while adding a manifest mode.

Proposed manifest:

```json
{
  "schema": "t2_hu_continuation_manifest_v1",
  "tables": [
    {"file": "terminal_28.json"},
    {"file": "terminal_143.json"}
  ]
}
```

Required loader guards for every table:

- schema = `t2_hu_continuation_table_v1`;
- value convention = `gross_share`;
- node unique in the manifest;
- node id matches;
- live mask matches;
- pot matches within 1e-9;
- 169 values for every live seat;
- no NaN / infinity.

The lookup must be by terminal node, with live-mask and pot guards retained.  A manifest
must fail closed on duplicate or mismatched nodes.

## T5 — synchronous outer-loop requirements

At each k:

1. solve one preflop game using the complete manifest from k-1;
2. extract every selected terminal range from that same solved game;
3. solve each terminal's flop panel independently and resumably;
4. aggregate each terminal table with its own conservation guard;
5. damp values per terminal using the same registered alpha;
6. construct one manifest containing every terminal table for k;
7. solve (P_{k+1}).

Never solve the preflop game independently once per terminal.  That is both wasteful and,
if tables differ, not the same fixed point.

## Current boundary

This branch intentionally stops before modifying `terminal_value()` or the single-table
loader.  The first census result should determine the selected terminal set before the
core injection API is generalized.
