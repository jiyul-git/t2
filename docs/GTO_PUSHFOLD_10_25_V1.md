# Push/fold buckets 10 / 15 / 20 / 25 bb (pre-registered 2026-10-19, before any graded solve)

User decisions 2026-10-19 (docs/GTO_SESSIONS_BOARD.md): fill fast first (`quick`), refine later where needed; every stack bucket is
computed with all players at the same stack (symmetric-stack assumption); this session (011TJw...) takes 10 / 15 / 20 / 25 bb
push/fold first (open jam, 3-bet jam, preflop only), then 30 / 40 bb. Game rules + standard sizes only; chip EV (no ICM).

## 1. Declared game (one full 9-max preflop tree per bucket, same frame as Plan A)
- 9-max, hand-start stack exactly S bb for every seat (cfg.stack = S - 1/9), ante 1 bb shared (1/9 per seat, dead), blinds 0.5 / 1,
  no rake, chip EV.
- S = 10: jam / fold. Every seat's first-in option is jam or fold (no open raise, no limp); facing a jam: fold / call
  (overcalls allowed; multiway all-ins use the engine's multiway equity model).
- S = 15, 20, 25: first in: fold / open 2.0 bb (SB 3.0 bb, as T2 and Plan A amendment A2) / jam; facing an open: fold / call / 3-bet jam
  (no non-jam 3-bet); facing a jam: fold / call; max_raises 2 (open + jam). No limp.
- Pots that reach a flop without an all-in (open called, possibly multiway): static continuation (`realization: static`, positional
  realization vs SPR) — "preflop only"; their values are approximate and every record says so.
- Reason for the menus: T2's own open form (preflop.py open_form: `bb < 12` -> shove, below 22-25 bb shove or open) and the 2.0 bb open
  of T2 at <= 80 bb; a 15-25 bb tree with the 2.0 open keeps the min-raise / reshove structure T2 bots face. A different menu per
  bucket (e.g. adding a 15 bb pure jam / fold tree) is a later comparison, not a change of this pre-registration.
- Configs: data/gto_spot/pushfold/cfg_pf{10,15,20,25}.json. Tree sizes (t2_tree_estimate): 10 bb 1,021 nodes; 15-25 bb 38,851 nodes.

## 2. Solve
- Engine: vendored gtopen preflop DCFR (same build as the Plan A parents), PREFLOP_EQ_SEED=202, PREFLOP_MULTIWAY_SEED=202,
  PREFLOP_EQ_SAMPLES=1200; new driver vendor/gtopen/crates/solver/examples/t2_pf_solve.rs (solve + checkpoint + exact gaps, no
  terminal export; the 10 bb tree has no flop-reaching pot, which t2_cont_terminal requires).
- Iterate in chunks (PREFLOP_MW_SKIP_BELOW=1e-9 while iterating, as the Plan A parents); measure the exact gap with the skip off
  after every chunk (separate call on the saved checkpoint, 0 further iterations).
- Stop at exact gap_total <= 0.010 bb (Plan A parent G2 limit) or 400 iterations, whichever first; the gap is recorded.
- Whole-tree dump: t2_tree_dump (reach >= 1e-6), as the Plan A parents.

## 3. Record and grade
- One record per bucket: data/gto_spot/records/pf{S}.json with, for every seat, the first-in strategy per class (fold / open / jam),
  BB (and every other seat) response to each single open and to each single jam (fold / call / 3-bet jam), and the response to a
  3-bet jam after an open (fold / call); action EVs; reach; the exact gap.
- Status `quick` (user decision): no P144, no outer loop. Flags in every record: `symmetric_stack_assumption: true`,
  `static_continuation_for_flop_pots: true` (S >= 15), `chip_ev: true`, `db_promotion: forbidden`, T2 runtime connection needs user
  approval.
- Gate reported (not a status lift): G2 exact gap <= 0.010 bb. Nodes reached with < 1e-3 combos by the actor or < 1 combo by the
  opponent are marked `unsupported_low_reach` (frequencies there are not used, same idea as amendment 8).

## 4. Order
10 -> 15 -> 20 -> 25 bb, one at a time (4 cores); then 30 / 40 bb (separate pre-registration: open / 3-bet / response).

## 5. Results (2026-10-19, branch claude/pushfold-10-25-20261019; chart docs/img/GTO_PUSHFOLD_10_25_V1.png)
| bucket | iterations | exact gap (bb) | G2 | nodes kept | unsupported_low_reach | RFI total UTG / BTN / SB |
|---|---|---|---|---|---|---|
| pf10 | 25 | 0.00663 | pass | 44 | 0 | 14 / 43 / 73 % (all jam) |
| pf15 | 75 | 0.00751 | pass | 200 | 0 | 11 / 38 / 64 % (mostly jam) |
| pf20 | 100 | 0.00539 | pass | 200 | 0 | 12 / 36 / 58 % (UTG opens, BTN 11 open + 25 jam) |
| pf25 | 75 | 0.00736 | pass | 200 | 15 | 13 / 36 / 58 % (UTG opens, BTN 22 open + 14 jam) |
Finding (15-25 bb): the BB defends ~100 % vs a 2.0 open (fold <= 0.05 %) - static continuation for the flop pot with the 1 bb ante
(call 1 to win 4.5); call vs fold there is model-dependent and a refinement target. All-in decisions do not use the continuation.
