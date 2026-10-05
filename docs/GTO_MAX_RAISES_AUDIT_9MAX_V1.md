# 9-max 30bb action-abstraction audit: `max_raises = 2` (open + 3-bet cap) — v1

Read-only audit after state T (`GTO_HU_3BET_9MAX_T3_RESULT_V1.md`). No preflop re-solve was started. Data:
`data/gto_validation/pilot9/step3/max_raises_audit.json`, `fourbet_ab.json`.

## 1. What the current tree allows (verified)
- `max_raises` counts the open as raise 1; the pilot uses 2. After a 3-bet nobody may raise: no 4-bet and no 4-bet jam
  (`legal_actions_of`: raises and jams only while `raises < max_raises`). `fourbet_mults` is inactive.
- On all 25 selected 3-bet paths: opener facing the 3-bet = `Fold, Call 6 | 8 | 10`; a cold player behind the 3-bet = `Fold, Call`;
  the 3-bettor's own node = `Fold, Call, 3-bet, All-in`.
- In the joint-OL trigger vector M, 50 of 216 elements (opener-vs-3-bet raise and jam on 25 paths) are structurally 0.

## 2. How much the missing 4-bet matters (conditional A/B, `tools/gto_validation/pilot9_4bet_ab.py`)
Subgame at the opener's node facing the 3-bet, ranges fixed at state T, CFR+ 20k iterations, the solver's own equity table
(seed 202, 1200 samples). A = current tree (fold / call). B = fold / call / 4-bet jam, 3-bettor fold / call vs the jam.
The payoff reconstruction reproduces T's own fold / call EVs to 1e-6. B_table keeps T's per-class flop values for the call branch,
B_eq replaces them by pot x equity vs the current range (sensitivity).

| spot | A: opener fold / call | B_table: fold / call / jam | 3-bettor fold vs jam | 3-bettor EV at the node: A -> B_table (B_eq) |
|---|---|---|---|---|
| BTN open, SB 3-bet 8 (n51) | 3.6 / 96.4 | 3.6 / 91.3 / 5.1 | 31% | 2.76 -> 2.51 (1.34) bb |
| CO open, BTN 3-bet 6 (n196) | 0 / 100 | 0 / 52.6 / 47.4 | 40% | 2.37 -> 0.49 (0.32) bb |
| SB open, BB 3-bet 10 (n14) | 16.5 / 83.5 | 1.8 / 56.4 / 41.7 | 15% | 2.36 -> 1.34 (-0.02) bb |

- With the 4-bet jam available, openers jam 5-47% of their range and the 3-bettor's EV at the node drops by 0.25-1.9 bb (table
  variant) or 1.4-2.4 bb (equity variant). The 3-bet range is held fixed here; in the full game it would shrink and re-balance, so
  these are sizes of the distortion, not the corrected strategy.
- Consequence for T: 3-bets are overvalued in the capped tree (they can never be 4-bet), which feeds back into open / flat / 3-bet
  frequencies everywhere upstream. The opener's "never fold to an IP 3-bet" is an artefact of the same cap.

## 3. Cost of adding the 4-bet
| tree | nodes | arena | 1st iteration, 4 threads | memory | 100 it (est.) | new postflop work |
|---|---|---|---|---|---|---|
| mr2 (current) | 75.7k | 102 MB | 23.6 s (iters 1-5: 22-30 s) | not measured | ~45 min | — |
| **mr3, 4-bet = jam only** | 913k | 1.23 GB | **73.5 s** | **1.52 GB peak** | **~2-2.5 h** | **none** |
| mr3, 4-bet 2.2x + jam | 1.75M | 2.37 GB | 382.6 s (earlier audit) | ~3 GB | ~11 h | 4-bet pots (SPR < 1) |
| mr4 (default) | 16.1M | 21.7 GB | — | > 16 GB | not runnable | — |

- mr3 jam-only has the same 18,660 flop-terminal action lines as mr2 (identical sets); only node ids change. All 33 solved tables
  (8 SRP + 25 3-bet) map to mr3 nodes by action line (e.g. 51 -> 74, 196 -> 428), so no new flop solve is needed.
- As in mr2, multiway terminals dominate: multiway CPU per iteration ~99 s in mr2 (5-iteration profile) vs 236 s in mr3 jam-only
  (3-way 34 s, 4-way 64 s, 5+-way 138 s). The added lines are multiway all-ins after a 4-bet jam, which are exact pot x equity
  terminals, not static continuation models.

## 4. Recommendation (no solve started)
1. Re-key the 33 tables by action line (loader keyed by path instead of node id; identity-checked against mr2).
2. One mr3 jam-only preflop solve (100 it, ~2-2.5 h, 1.5 GB) with the 33 tables; compare with T. Then run the same pre-registered
   trigger idea on the new tree before any joint OL.
3. Keep the 2.2x 4-bet (mr3 full) and 5-bet out for now, on cost / priority grounds only: ~5x the cost and new 4-bet-pot
   terminals. Whether a non-all-in 4-bet matters at 30 bb is not tested here and is not assumed. Record "4-bet = jam only" as the
   declared abstraction in every DB record until it is tested.

## 5. Plan J (approved 2026-10-05), pre-registered before any J solve
States: **T2** = state T (max_raises 2, 33 solved tables; `/home/user/gto_ckpt/step3/t3/T`). **J** = max_raises 3, 4-bet option =
jam only (`fourbet_mults` 10 -> clamps to the stack), the same 33 tables re-keyed by action line, same seeds / equity samples,
100 iterations from scratch with checkpoints, no new flop solve.

A. Action-line re-key with an identity gate. Tables are stored keyed by a canonical preflop action line (every action from the root
   with actor, kind and to-amount) and resolved to node ids of a target tree through that tree's own terminal enumeration
   (`t2_cont_census`, 0 iterations); the Rust loader is unchanged and still checks node kind, live mask and pot (fail closed).
   Gate on the mr2 tree, at the T checkpoint: the 33 resolved node ids equal the original ids; every resolved table equals the
   original table field by field (gross arrays exact); all 33 path exports with the resolved manifest equal the original T exports
   exactly (every field except the manifest path string). Any difference stops the plan; no tolerance.

B. Shared comparison metric M4 (166 elements): RFI UTG..SB (8); first-in opener jam share of opens (8); on the 25 selected 3-bet
   paths, the 3-bettor's node facing the open: fold / call / raise / jam (100); the opener's node facing the 3-bet: fold and
   continue = 1 - fold (50). D4 = max |M4(J) - M4(T2)|, reference R = 4.33 pp (last HU OL residual).
   D4 > R -> missing-4-bet is a structural effect larger than the previous outer-loop change. D4 <= R does NOT promote the mr2 tree
   if J shows material 4-bet frequencies.
   Reported separately (new actions): opener 4-bet-jam frequency on the 25 paths; 3-bettor fold / call vs the 4-bet jam (25 jam paths);
   hand classes that 4-bet jam. Also: gap / convergence, RFI, 3-bet frequencies, first-in open-jam, selected-terminal reach and
   coverage (census at J), near-reference comparison.

C. Stop after J. No 33-table joint OL and no 2.2x 4-bet tree without a new decision.
