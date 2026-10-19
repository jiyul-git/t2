# Stack buckets 30 / 40 bb: open / 3-bet / response (pre-registered 2026-10-19, before any solve)

User decisions 2026-10-19 (docs/GTO_SESSIONS_BOARD.md): quick fill, symmetric stacks, this session takes 30 / 40 bb after the
10-25 bb push/fold buckets (docs/GTO_PUSHFOLD_10_25_V1.md). Order inside a bucket: all-position RFI, BB defence, 3-bet response first;
4-bet-and-later later.

## 1. Declared game: the Plan A v2b parent tree at S = 30 and 40 bb
- data/gto_spot/stack3040/cfg_s{30,40}.json = data/gto_spot/plan_a/cfg_p60_v2b.json with cfg.stack = S - 1/9 and nothing else changed:
  9-max, ante 1 bb shared, blinds 0.5 / 1, opens 2.0 bb (SB open 3.0 bb, SB limp allowed), 3-bet 3.0x (blinds 3.5x / 4.0x), jam
  always on offer (add_allin, allin_threshold 0.85), max_raises 3 with the 4-bet = jam only, static continuation for flop pots, chip EV.
- Tree size (t2_tree_estimate): 1,338,299 nodes, 1.81 GB arena per bucket (identical to the 60 bb v2b parent).
- Same menu as the 60 bb parent so the 30 / 40 / 60 bb buckets differ only in depth (interpolation between buckets stays a pure
  stack effect).

## 2. Solve (as the Plan A parents, docs/GTO_PLAN_A_60BB_V1.md section 3)
- DCFR, PREFLOP_EQ_SEED=202, PREFLOP_MULTIWAY_SEED=202, PREFLOP_EQ_SAMPLES=1200; chunks of 25 iterations with the 1e-9 multiway skip;
  exact gap (skip off, separate call on the checkpoint) when the chunk's skip gap <= 0.011 bb or every 100 iterations; stop at exact
  gap_total <= 0.010 bb or 400 iterations; whole-tree dump (reach >= 1e-6). Driver t2_pf_solve; script tools/gto_spot/stack_run.sh.

## 3. Record
- data/gto_spot/records/s{S}.json, built like the push/fold records (tools/gto_spot/pushfold_record.py with the bucket prefix):
  first-in (RFI), facing a single open / jam, opener facing a single 3-bet / 3-bet jam; per class strategy, action EVs, arriving combos;
  `unsupported_low_reach` as in the push/fold standard.
- Status `quick`: parent-level equilibrium only (no HU subgame loop, no P144 — user decision); flags symmetric_stack_assumption,
  static_continuation_for_flop_pots (flat calls and 3-bet-call pots are model-valued: refinement targets), chip_ev, db_promotion forbidden,
  T2 runtime connection needs user approval. G2 (exact gap <= 0.010 bb) reported.

## 4. Results (2026-10-19, branch claude/pushfold-10-25-20261019; chart docs/img/GTO_STACK_30_40_V1.png)
| bucket | iterations | exact gap (bb) | G2 | nodes kept | unsupported_low_reach | RFI UTG / BTN; SB raise / limp |
|---|---|---|---|---|---|---|
| s30 | 150 | 0.00913 | pass | 308 | 9 | 14 / 37 %; 20 / 80 % |
| s40 | 150 | 0.00858 | pass | 308 | 67 | 15 / 41 %; 21 / 79 % |
No open jams at 30 / 40 bb. BB vs a 2.0 open: call 85-96 %, 3-bet 4-15 % (30 bb almost all jam; 40 bb ~4 % non-jam + jam);
fold ~0 % (same static-continuation caveat as the push/fold buckets). Opener vs a 3-bet (30 bb): fold 28-46, call 38-54, 4-bet jam ~17 %.
