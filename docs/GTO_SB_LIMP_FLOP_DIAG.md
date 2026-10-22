# SB-limp flop non-convergence: diagnosis (branch claude/sb_limp_flop_diag_20261022, 2026-10-22)

Scope: why some flops of the first terminal of the SB limp vs BB flat-call spots (30 bb, 40 bb) stay above the 0.3% pot target after the
3x retry (amendments 7, 11), and fixes that keep the same game and the same target. No grading criterion or tolerance was changed or applied.

## Cause
It is the solver algorithm, not numerics and not the ranges.
- The flop solver (vendored GTOpen, `t2_cont_panel`) always runs DCFR (alpha 1.5, beta 0, gamma 2). On the failing flops DCFR plateaus:
  30 bb KcJhJd (terminal `p30_flat_sb_limp_vs_bb` step 0) goes 8.54 -> 1.31 (it 100) -> 0.897 (200) -> 0.783 (400) -> 0.758 (600) ->
  0.748 (800) -> 0.7436 (1000); the 3x retry only reaches 0.7359 (3000). The trace reproduces the original run bit for bit
  (8.5441 at it 25, 3.1012 at it 50).
- Not the EPS keep-fraction floor: trimming every class with keep fraction < 0.01 (62 BB classes sit at the 1e-3 floor weight, SB has 3)
  lowers the level only slightly (0.676% at 1000, same flat shape) and does not remove the floor.
- Not f32 storage: the floor is smooth and algorithm dependent. The same flop, same terminal, same f32 storage, same EPS floor, reaches
  the target with CFR+ (0.263% at 250 iterations) and PCFR+ (0.287% at 325). (A true f64 switch was not tried: the arenas are f32-only
  and the algorithm change already removes the floor, so it was not needed.)
- DCFR converges 22 of the 24 step-0 flops at 30 bb in 125-175 iterations; only KcJhJd (floor) and AcKc6c (1325 iterations) are slow.
  The slow flops are the paired-board / ace-high-two-flush boards where the SB range (~133 weighted combos) is wide and the BB
  check range is narrow.

## Fixes tested (same game, same target 0.3% pot, same terminal files, same panel_v1 / menu m2_single_v1)
Runtimes are wall-clock on this 4-core box with 1-2 threads and other solves running at the same time: compare iterations, not seconds,
across rows. Original DCFR runtimes (1 thread, other machine) are in the DCFR rows from the step backups.

| flop | fix | exploitability % pot | iterations | runtime |
|---|---|---|---|---|
| 30 bb KcJhJd | DCFR (original, 3x retry) | 0.7359 | 3000 | 16444 s |
| 30 bb KcJhJd | DCFR, trim keep < 0.01 | 0.6763 | 1000 | 1739 s |
| 30 bb KcJhJd | more iterations | 0.7436 -> 0.7359 for 3x (floor) | 1000 -> 3000 | -- |
| 30 bb KcJhJd | PCFR+ | 0.287 (converged) | 325 | 618 s (2 thr) |
| 30 bb KcJhJd | CFR+ | 0.263 (converged) | 250 | 447 s (2 thr) |
| 40 bb KcJhJd | DCFR (original) | 1.359 | 3000 | -- |
| 40 bb KcJhJd | CFR+ | 0.284 (converged) | 250 | 444 s (2 thr) |
| 40 bb AcQc2c | DCFR (original) | 0.3185 | 3000 | -- |
| 40 bb AcQc2c | CFR+ | 0.279 (converged) | 325 | 175 s (2 thr) |
| 40 bb AcKc6c | DCFR (original) | 0.4201 | 3000 | -- |
| 40 bb AcKc6c | CFR+ | 0.270 (converged) | 325 | 328 s (1 thr) |
| 30 bb 6c4d3d (control) | DCFR / CFR+ | 0.277 (125 it, 485 s) / 0.255 | 125 / 225 | 475 s CFR+ (1 thr) |
| 30 bb Tc9d5h (control) | DCFR / CFR+ | 0.251 (175 it, 1057 s) / 0.275 | 175 / 250 | 882 s CFR+ (1 thr) |
| 30 bb Qc5c2c (control) | DCFR / CFR+ | 0.265 (175 it, 332 s) / 0.270 | 175 / 250 | 259 s CFR+ (1 thr) |

All four known failing flops converge under CFR+ within 250-325 iterations (well inside the 1000 budget). The three controls converge
too (no regression), at about 1.4-1.8x the iterations DCFR needed on easy flops.

Effect on the terminal values (same game, different converged solution of it): per-class gross values (`gross_eps`, classes with
valid mass > 0.5) of CFR+ vs the stored converged DCFR artifact differ by at most 0.028 bb (6c4d3d), 0.043 bb (Tc9d5h), 0.024 bb (Qc5c2c)
on a 3 bb pot, i.e. within what two 0.3%-pot-exploitable solutions of the same game can differ. For KcJhJd the CFR+ values differ from the
unconverged DCFR artifact by up to 0.153 bb, which is the error the floor caused. Trimming low-weight classes was NOT recommended: it changes the
game (drops combos the ranges contain), and does not fix the floor anyway.

## Recommendation
Use CFR+ (or PCFR+) for any flop that DCFR leaves unconverged: a retry with the other algorithm instead of the 3x-iterations retry.
Cost: 4 flops x about 3-8 minutes (2 threads) at 250-325 iterations, versus 3x DCFR iterations that never converge (16444 s for one flop).
Implementation (not wired into the spot loop, per instructions): `t2_cont_panel` now reads `T2_ALGO=dcfr|cfr+|pcfr+` (default dcfr;
the value is recorded in the provenance key as `algo`; `trim`, `eps` also recorded). The spot loop would set `T2_ALGO=cfr+` for the retry. Extra diagnostic
env: `T2_PROGRESS=1` (trace lines), `T2_DIAG=1` (per player/class gap split), `T2_EPS`, `T2_TRIM`.

## Criterion question for the user (options, none applied)
The amendment 11(a) retry is currently "3x the iteration budget (same target)". Option A: keep it as is (the 4 flops stay research).
Option B: amend (a) to "retry with CFR+ at the same iteration budget and the same target; the first DCFR artifact is kept beside it".
Before / after verdicts: p30_flat_sb_limp_vs_bb step 0: research (KcJhJd 0.736%) -> passes the flop gate (all 24 flops <= 0.3% with CFR+ on
KcJhJd; the other flops keep their DCFR artifacts). p40_flat_sb_limp_vs_bb step 0: research (AcQc2c 0.319%, AcKc6c 0.420%, KcJhJd 1.359%)
-> all three <= 0.3%. The target (0.3% pot) and the exploitability definition are unchanged under B.

Caveat: not tested beyond these 7 flops; the earlier 60 bb p60v2b_co_vs_sb_3b40 9c7d4h floor (amendment 7) was not rerun and is not claimed fixed.
Raw logs: not committed (/tmp); numbers above are from the run logs and artifacts of this session.
