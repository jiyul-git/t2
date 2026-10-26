# Amendment 11(a), CFR+ retry variant (approved 2026-10-23)

Approval: the user delegated it to the coordinator session (session_012qfUk9MsH6Hp2gBX6Q18sA) on 2026-10-23.

Standard amendment 11(a) "an unconverged flop gets one retry at 3x the iteration budget" is replaced for this run
(p40_flat_sb_limp_vs_bb) by: **an unconverged flop gets one retry with CFR+ (`T2_ALGO=cfr+`) at the same iteration budget and the same
exploitability target (0.3% pot).** Nothing else changes: same game, same target, other amendments (7, 11(b)) as before; no grading change,
no ICM, no P144, no runtime connection to T2. The first (DCFR) artifact of a retried flop is kept in `first_attempt/`.

Reason: docs/GTO_SB_LIMP_FLOP_DIAG.md (branch claude/sb_limp_flop_diag_20261022): DCFR plateaus on these flops; CFR+ converged all four
known failing flops (40 bb KcJhJd 0.284% at 250 it, AcQc2c 0.279% at 325, AcKc6c 0.270% at 325) without regressing three control flops.

Both verdicts are kept: `data/gto_spot/quick/p40_flat_sb_limp_vs_bb_dcfr_stop.json` (step 0 only, DCFR, 3x retry, stopped) and
`data/gto_spot/quick/p40_flat_sb_limp_vs_bb.json` (CFR+ retry; status_note "CFR+ retry per amendment 11(a) variant, user-approved 2026-10-23").

Code: `T2_ALGO` in `t2_cont_panel` copied from the diagnosis branch (default unchanged = DCFR); `retry_flops` in `tools/gto_spot/spot_loop.py`
sets `T2_ALGO=cfr+` and the first-attempt iteration budget.

Also applied (coordinator task 2026-10-25, branch claude/flat_open25_20261025) to the BB-vs-2.5-bb-open flat-call quick spots
p40_flat_btn_vs_bb_o25, p40_flat_co_vs_bb_o25, p30_flat_btn_vs_bb_o25, p30_flat_co_vs_bb_o25 (same budget, same target, retries in parallel).
