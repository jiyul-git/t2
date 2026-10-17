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

## Sessions
| session | spot | stage | next | blocked / note |
|---|---|---|---|---|
| this (01BLRH...) | p60v2b_co_vs_sb_3b40 | 24-board loop converged step 2; P144 under amendment 11 inconsistent (3-bet-call D144 > U24). 144-board loop: first launch (13:54Z) re-retried Qc9d4h at 9000 its in step 0 (bug: amendment 11a allows one retry) and was killed at the 2 h task limit; fixed (a board with first_attempt/ is not retried again). Side effect: the original 1000-it Qc9d4h artifact was overwritten by the 3000-it retry (its numbers 0.71956% / 1000 its stay in step2_p144/report.json); the values used are the 3000-it retry as before | 144-board loop running as a tracked task from 19:29Z (detached launches die when the idle container is reclaimed: 16:00Z and 18:27Z restarts, step 1 at 2/288 flops) | - |
| this | p60v2b_utg1_vs_sb_3b40, then _3b35 | queued | | |
| T2 (01XV9...) | p60v2b_utg_vs_btn | v4 step 7 running (f597b50b, amendment 11 included). Step 6 continue: 3-bet-call UTG 1.23/1.20, BTN 1.89/0.76; 4-bet-call UTG 1.66/1.07 (opp 24.8 combos), BTN 1.53/1.04 (opp 35.7); no exempt cells; 3-bet-call alternates pass/fail between steps. Backup ccr-9a10123b-0lyye0 e5ee0ff4 (steps 0-6) | hj_vs_bb_3b40 -> _3b35 | - |
| Claude (session_01GvcQ...) | p60v2b_hj_vs_bb_3b40 | DONE, NOT CONVERGED -> research: loop stopped at step 5 (amendment 7/11): flop Qc9d7d at the 4-bet-call terminal (non-exempt in step 5) 0.3297% pot at 3000 its (target 0.3) after the 1000-it first attempt 0.3294%. 3-bet-call terminal passed both seats steps 2-5 (HJ D 0.72/0.47/0.28/0.36); 4-bet-call HJ D 16.05/0.98/1.75/3.15/3.36/- cycles. No P144 / sensitivity run (chain stops at NOT CONVERGED). Data: branch claude/p60v2b_hj_vs_bb_3b40-20261016, gto_split_backup/p60v2b_hj_vs_bb_3b40/ (step0-5.tgz, state.json, records/, spots.log). Note: a retry killed mid-solve leaves the first-attempt file in first_attempt/ and the relaunch then crashes on the missing flop file; restored by moving it back (no code/criteria change) | | |
| new Claude | p60v2b_btn_vs_bb_3b40 ... | ? | | |

## Open decision items (user)
1. DECIDED 2026-10-14 (user, via the T2 session): a+b -> amendment 11. Qc9d4h (p60v2b_co_vs_sb_3b40, 4-bet-call terminal = amendment-8 exempt, CO 0.017 combos): 0.72% pot vs target 0.6% at 1000 its.
   Retry with 3000 iterations under test. Options the user may choose from:
   (a) if the retry converges: add "an unconverged flop gets one retry at 3x the iteration budget" (documented, before/after verdicts kept);
   (b) T2-session proposal: unconverged flops at an amendment-8 exempt terminal are recorded but do not stop the loop
       (same logic as amendment-8 condition (2) applied to G6(b)); unconverged flops at judged terminals still stop (research);
   (c) keep amendment 7 as is: the spot stays research.
