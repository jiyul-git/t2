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
| this (01BLRH...) | p60v2b_co_vs_sb_3b40 | 24-board loop converged step 2; P144 rerun under amendment 11 (amendment-7 verdict research archived as *_p144_amend7) | Qc9d4h retry, then amendment-10 144-board loop | - |
| this | p60v2b_utg1_vs_sb_3b40, then _3b35 | queued | | |
| T2 (01XV9...) | p60v2b_utg_vs_btn | v4 step 5 (from its message) | | |
| new Claude | p60v2b_btn_vs_bb_3b40 ... | ? | | |

## Open decision items (user)
1. DECIDED 2026-10-14 (user, via the T2 session): a+b -> amendment 11. Qc9d4h (p60v2b_co_vs_sb_3b40, 4-bet-call terminal = amendment-8 exempt, CO 0.017 combos): 0.72% pot vs target 0.6% at 1000 its.
   Retry with 3000 iterations under test. Options the user may choose from:
   (a) if the retry converges: add "an unconverged flop gets one retry at 3x the iteration budget" (documented, before/after verdicts kept);
   (b) T2-session proposal: unconverged flops at an amendment-8 exempt terminal are recorded but do not stop the loop
       (same logic as amendment-8 condition (2) applied to G6(b)); unconverged flops at judged terminals still stop (research);
   (c) keep amendment 7 as is: the spot stays research.
