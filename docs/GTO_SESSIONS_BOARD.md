# GTO sessions board (shared status; read by the T2 session, which reports to the user)

Decisions (criteria, procedures) are the user's. This board records status, shared fixes and open decision items only.
Updated by session_01BLRHV14gJtnk3f8cLagcNs (branch chatgpt/terminal-census-v2-20260930).

## Commits every session should be on
| commit | content |
|---|---|
| f377682f | standard amendment 11 (user decision a+b): one flop retry at 3x budget; still unconverged at an exempt-level terminal -> recorded, run continues; includes everything below |
| 101a2e7c | P144 no longer aborts at the first unconverged flop (records it, keeps exemption info) |
| 186e6927 | standard amendment 10: 144-board continuation after an inconsistent P144 (user decision A; step 0 = P144, <= 3 more steps, D <= U144) — includes 101a2e7c; run_plan_a.sh runs it automatically |
| 4f4551f2 | amendment 9 (G6(a) on EV) + G6(b) skips amendment-8 unsupported nodes (pass_strict kept) |
| 4c1db4e1 | amendment 8 accepted (exempt terminal-seat when the opponent arrives with < 1 combo; nodes unsupported at connection) |
| e6efd38c / 609555d9 | rule v4 (damped matrices) / amendment 7 (unconverged flop -> research) |

## Sessions (survey 2026-10-19 02:30Z from the remote branches; this session's own runs stopped to avoid duplicates)
| spot | session / branch | stage (last backup) | verdict so far |
|---|---|---|---|
| p60v2b_co_vs_sb_3b40 | 01FbCz... / claude/p60v2b_co_vs_sb_3b40-resume-20261016 | P144 recomputed (matches this session's), amendment-10 144-board loop step 1 at 115/288 flops (10-18 04:29Z) | pending; this session's partial p144s1 (term0 18/24 panel_v1) is behind and not resumed here |
| p60v2b_utg1_vs_sb_3b40 | claude/p60v2b_utg1_vs_sb_3b40-20261016 | 24-board loop converged step 3; record committed (10-17 08:01Z) | provisional: P144 not graded; G6(b) dominated material (SB vs UTG+1 4-bet jam: QQ fold 28%, EV loss 14.1 bb; JJ call 40%, 4.9 bb); G6(a) pass |
| p60v2b_btn_vs_bb_3b40 | 011TJw... (running) / claude/p60v2b_btn_vs_bb_3b40-resume-20261016 | P144 inconsistent; 144-board loop in progress (10-18 03:41Z) | 24-board provisional; P144 research (G3 D144 > U24, G6 a+b fail: BB QJs fold 64%, 0.42 bb) |
| p60v2b_hj_vs_bb_3b40 | 01GvcQ... / claude/p60v2b_hj_vs_bb_3b40-20261016 | done (10-17 21:44Z) | research: step 5 flop Qc9d7d 0.3297% at 3000 its (target 0.3) at the 4-bet-call terminal; 4-bet-call D cycles 16.05/0.98/1.75/3.15/3.36 |
| p60v2b_utg_vs_btn | T2 side / ccr-fb71f1d0-3wvj9e (steps 0-7 on ccr-9a10123b-0lyye0) | done after 12 steps (10-17 02:51Z) | research: G3 not converged; G6(b) invariant violation |
| p60v2b_hj_vs_bb_3b35 | 012qfU... (T2 side) / ccr-fb71f1d0-3wvj9e | v4 step 7 (10-18 03:59Z) | pending |
| p60v2b_utg1_vs_sb_3b35, p60v2b_co_vs_sb_3b35, p60v2b_btn_vs_bb_3b35 | unclaimed | - | - |

Connection-eligible spots: 0 of 9. Common problems: the 4-bet-call terminal does not converge (D cycles), and G6(b) dominated-material
mixes after 4-bet / jam nodes. G6(b) cause: see open decision item 2.

## Open decision items (user)
1. DECIDED 2026-10-14 (user, via the T2 session): a+b -> amendment 11. Qc9d4h (p60v2b_co_vs_sb_3b40, 4-bet-call terminal = amendment-8 exempt, CO 0.017 combos): 0.72% pot vs target 0.6% at 1000 its.
   Retry with 3000 iterations under test. Options the user may choose from:
   (a) if the retry converges: add "an unconverged flop gets one retry at 3x the iteration budget" (documented, before/after verdicts kept);
   (b) T2-session proposal: unconverged flops at an amendment-8 exempt terminal are recorded but do not stop the loop
       (same logic as amendment-8 condition (2) applied to G6(b)); unconverged flops at judged terminals still stop (research);
   (c) keep amendment 7 as is: the spot stays research.
2. OPEN (analysis by 01BLRH..., 2026-10-19; records on the branches above, no recompute). Every G6(b) dominated-material violation in the
   v2b records sits at a node where the OPPONENT arrives with < 1 combo, i.e. the "facing jam" node after an almost never taken jam:
   | record | node (actor faces) | opponent arriving combos | violations |
   |---|---|---|---|
   | p60v2b_utg1_vs_sb_3b40 | SB faces UTG+1 4-bet jam | 0.00037 (UTG+1 jam freq 1.8e-6) | QQ fold 28% (EV loss 14.1 bb), JJ call 40% (4.9 bb) |
   | p60v2b_btn_vs_bb_3b40 P144 | BB faces BTN 4-bet jam | 0.0115 | QJs fold 64% (0.42 bb) |
   | p60v2b_utg_vs_btn | BTN faces UTG 4-bet jam | 0.00039 | AKo call 53% (5.2 bb), AKs call 72% (2.4 bb); KK fold 2.2% (premium_fold) |
   No violation at a node the opponent reaches with >= 1 combo; chip conservation passes in all. Mechanism: CFR updates at a node are
   weighted by the opponent's reach, so with ~0 reach the strategy there never moves (any strategy is a Nash equilibrium there; it is
   not a solver bug and does not affect exploitability). Amendment 8 already treats "opponent arrives < 1 combo" as unsupported, but its
   node list is built only from the outer loop's flop terminals; an all-in node has no flop terminal, so these nodes are not on it.
   Options for the user: (a) extend the amendment-8 unsupported set to every node whose opponent arrives with < 1 combo (same fixed
   threshold, all spots; G6(b) skips them, pass_strict kept; before/after verdicts recorded) -> G6(b) would pass in all three records;
   (b) keep G6(b) as is (these spots stay provisional / research on G6(b)); (c) (a) plus a best-response refinement at those nodes so a
   connection that hits an off-path jam gets sensible frequencies (later work). Under any option the frequencies at these nodes must not
   be used by T2 as GTO.
   Side observation (G3 cycling): in p60v2b_btn_vs_bb_3b40 the BTN 4-bet choice flips between 4-bet 17.2 and jam from the 24-board state
   to the P144 state (BB facing 4-bet: 0.41 -> 36.6 combos; facing jam: 22.7 -> 0.012), so the 4-bet-call terminal's arriving range swings,
   which matches the D cycling there and in hj_vs_bb_3b40.
