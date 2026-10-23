# Procedure change: CFR+ flop retry (variant of standard amendment 11(a)), p30 SB-limp flat-call spot

Approved 2026-10-23 (user delegated the approval to the coordinator session). Applies to this run only (`p30_flat_sb_limp_vs_bb`).

- Standard amendment 11(a): "an unconverged flop gets one retry at 3x the iteration budget".
- This run: "an unconverged flop gets one retry with CFR+ (`T2_ALGO=cfr+`) at the **same** iteration budget and the same exploitability target".
- Unchanged: same game and menu, target 0.3% pot, all other amendments (7, 8, 10, 11(b), 12), rule v4, max 3 steps, no P144, chip EV, no ICM.
- Reason: `docs/GTO_SB_LIMP_FLOP_DIAG.md` (branch `claude/sb_limp_flop_diag_20261022`): DCFR plateaus on these flops (30 bb KcJhJd stuck near 0.74% from iteration 600); CFR+ converged all 4 known failing flops (30 bb KcJhJd 0.263% at 250 it) with no regression on 3 control flops.
- Code: the `T2_ALGO` flag in `t2_cont_panel.rs` copied from that branch (default DCFR unchanged); `tools/gto_spot/spot_loop.py` reads `SPOT_RETRY_ALGO=cfr+` to switch the retry (same iterations instead of 3x).
- Both verdicts kept: step-0 DCFR stop record `data/gto_spot/quick/p30_flat_sb_limp_vs_bb_dcfr_stop.json` (from `claude/p30-flat-20261019`); CFR+ run record `data/gto_spot/quick/p30_flat_sb_limp_vs_bb.json` with `status_note` "CFR+ retry per amendment 11(a) variant, user-approved 2026-10-23".
- Restored step 0: 23 flops converged under DCFR (AcKc6c converged under the standard 3x retry); KcJhJd restored to its 1000-it DCFR first attempt (0.7436%), the DCFR 3x attempt (0.7359%) is kept in `dcfr_3x_attempt/`.
