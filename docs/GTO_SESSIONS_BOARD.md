# GTO sessions board (shared status; read by the T2 session, which reports to the user)

Decisions (criteria, procedures) are the user's. This board records status, shared fixes and open decision items only.
Updated by session_01BLRHV14gJtnk3f8cLagcNs (branch chatgpt/terminal-census-v2-20260930).

## User decisions 2026-10-19 (relayed by T2 session 01XV9, confirmed by the user in session 01BLRH...)
1. Direction: fill fast first, refine later and only where needed.
   - `quick` grade: 24-board loop converged -> use that state; cycling / not converged -> mean of the last 4 steps (draft of
     docs/GTO_PLAN_A_OSCILLATION_ANALYSIS_20261016.md section 4). No P144. Records carry `quick` so they are refinement targets later.
     No further oscillation research (damping experiments etc.).
   - 60bb: start nothing new. Running spots (hj_vs_bb_3b35, btn_vs_bb_3b40, co_vs_sb_3b40 144-board loop) finish if close, otherwise
     stop and are summarised as quick; each session decides.
   - Order per stack: all-position RFI, BB defence, 3-bet response first; 4-bet-and-later later.
     (1) 10/15/20/25 bb: push/fold (open jam, 3-bet jam), preflop only; (2) 30/40 bb: open / 3-bet / response;
     (3) 60 bb: quick summary of existing results; (4) 100 bb and deeper: last.
   - Refinement (P144 etc.) only after everything is filled, where T2 bots and GTO values differ most.
   - Unchanged: game rules + standard sizes only; connecting GTO data to the T2 runtime needs user approval; no force push; no ICM (chip EV).
2. Different stacks per player: every stack bucket (10/15/20/25/30/40/60/100 bb) is computed with all players at the same stack.
   Lookup later: effective stack (min with the opponent) -> nearest bucket, interpolate between buckets; HU pots are exact in chip EV.
   Known error: decisions with players left to act (RFI) depend on the stacks behind; ignored now, records state "symmetric-stack assumption".
   First refinement candidates: <= 25 bb push/fold solved with the real stack vector; measure the symmetric approximation where a short
   stack sits behind and fix only large errors.

## 30 / 40 bb flat-call pots (user decision 2026-10-19, relayed by T2 session 01XV9; same message to 011TJ)
Background: s30 (parent tree only, no loop) keeps the static continuation for flat calls: BB open defence 85-95 % call, SB 30 bb limp 80 % /
fold 0 %. User: "defence (flat calls) is the problem; the rest (all-in, 3-bet attack, RFI) is OK". T2 (test3) already uses GTO for 10-30 bb
first entry / lone-shove call / 3-bet-jam call (cc826bc8, fa9dcaa5); SB limp reverted; flat call / limp are NOT connected until corrected values exist.
Request: for 30 bb and 40 bb run the Plan A loop (HU subgame + 24-board panel, rule v4) on the pots that reach the flop. Priority:
(1) BB flat call of a single open (openers UTG..BTN, SB 3.0 included), (2) SB limp pots, (3) 3-bet-call pots. After the 4-bet out of scope.
Not converged -> quick (mean of the last 4 steps), no P144.
Split proposed by 01BLRH... (011TJ: please confirm or change on this board): 011TJ = 30 bb (its s30 parent exists); 01BLRH... = 40 bb
(parent cfg_p40_v1 = v2b sizes at stack 39.89, 1.34 M nodes; parent CONVERGED 2026-10-19 12:56Z at 150 iterations, exact gap 0.00858 bb; chart data/gto_spot/quick/chart_40bb_*; flat-call spots p40_flat_<opener>_vs_bb x8 + p40_flat_sb_limp_vs_bb running 13:00Z onward, order BTN, CO, SB, HJ, LJ, UTG+2, UTG+1, UTG, SB limp; 011TJ has not confirmed the split yet). The 100 bb parent is PAUSED at 200 iterations
(gap 0.0272 bb, checkpoint in /home/user/gto_ckpt/plan_a/p100_v1, resumable) because the user's order puts 30/40 bb before 100 bb.

## Stack split (2026-10-19, user)
| session | buckets |
|---|---|
| Gto제작 01BLRH... (this board's maintainer, branch chatgpt/terminal-census-v2-20260930) | 60 bb quick summary of all v2b spots (DONE 2026-10-19: data/gto_spot/quick/, see its README; hj_vs_bb_3b35 quick = steps 3-6, refresh when the T2 run ends), then 100 bb: parent full tree cfg_p100_v1 PAUSED at 200 iterations (gap 0.0272; see the 30/40 bb section above) (stack 99.89 = 100 - ante, same sizes as v2b, max_raises 3 with 4-bet 2.25x or jam and no 5-bet in the parent; 2.58M nodes / 3.5 GB; the max_raises 4 tree with a 5-bet jam is 43M nodes / 59 GB, infeasible) -> quick chart (RFI / vs open / vs 3-bet) first, HU subgames (5-bet jam) after |
| btn session 011TJw... | 10 / 15 / 20 / 25 bb push/fold and the 30 / 40 bb parent trees: DONE 2026-10-19 (branch claude/pushfold-10-25-20261019, section below); then the 30 bb flat-call pot loop (same 9 spots, tools plan_a_flat_specs.py / run_quick.sh) |
| T2 session 01XV9... | no computation; compares results with T2 bot behaviour hand by hand |

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
3. RELAYED 2026-10-19 (user decision "3" via T2 session 01XV9): when the 4-bet-and-later terminals do not converge, grade the 3-bet-call
   terminal on its own as the T2 connection candidate; mark 4-bet-and-later research (runtime connection still needs user approval).
   Not implemented yet: the grading definition is a criterion change and goes to the user first (draft below).
   Measurement (01BLRH..., hj_vs_bb_3b40 steps 1-5 from the branch backups, no recompute): the 3-bet-call terminal passes D <= U in
   steps 2-5, but the ROOT node (HJ facing the 3-bet) still swings: call 52.3 / 37.9 / 43.0 / 37.1 % (steps 2-5); between steps 4 and 5,
   12 classes (57.8 of 358.3 combos, e.g. 55, 88, K9s, Q9s, KJs, K7s) move > 10 pp, mostly whole call <-> fold flips of near-indifferent
   classes. So "3-bet-call terminal converged" does not by itself make the root call/fold frequencies stable.
   Draft for the user: 3-bet-call sub-grade = G3 on the 3-bet-call terminal only (both seats D <= U), plus a root-stability check over the
   last two steps (classes moving > 10 pp listed as unstable / near-indifferent, frequency not exported as GTO); nodes after the 4-bet
   unsupported at connection; label at most conditional_verified with reason "4-bet-and-later research".

## Decisions 2026-10-19 14:00Z (user, via T2 session 01XV9: "reassess the split, decide what is open")
1. Split confirmed: 40 bb flat-call pot loop = 01BLRH... (the 9 spots running since 12:57Z); 30 bb flat-call pot loop = 011TJ (same tools, same 9 spots);
   the 100 bb parent resumes after the 40 bb flat-call spots (paused at 200 iterations, gap 0.0272 bb).
2. Open decision item 2 -> (a): the standard-amendment-8 unsupported set is extended to EVERY node the opponent reaches with < 1 combo (G6(b) skips
   them, pass_strict kept, before / after verdicts recorded). Frequencies at these nodes are never used by T2 (the T2 connection already excludes
   attacker < 10 combo nodes). To register as amendment 12 by 01BLRH...
3. Open decision item 3 (3-bet-call sub-grade) -> closed, replaced by the quick direction; the root-stability measurement stays as a record only.
4. 60 bb: the stopped runs of the other account's sessions (co_vs_sb_3b40 resume, hj_vs_bb_3b35, btn_vs_bb_3b40 paused) are not resumed. The 60 bb
   quick summary (data/gto_spot/quick/, 611bfc58) is final for now.
5. T2 side: master = test3 = 39e204a7 is the new baseline (10-30 bb first entry, lone-shove call, 3-bet-jam call, open / 3-bet facing attacks connected; flat call / limp NOT
   connected). T2 connects s40 (40 bb) next; BB defence / SB limp are connected when the corrected flat-call values exist.
6. Computation runs as tracked tasks; restart / back up before the 2 h limit (idle containers are reclaimed).

## Session 011TJw... status (merged from docs/GTO_SESSIONS_BOARD_011TJ_STATUS.md, branch claude/pushfold-10-25-20261019 @30b7c1c9)
All records `quick`, symmetric stacks, chip EV, 9-max, ante 1 bb, vendored preflop DCFR (seeds 202, 1200 samples), stop at exact gap <= 0.010 bb.
Pre-registered: docs/GTO_PUSHFOLD_10_25_V1.md, docs/GTO_STACK_30_40_V1.md.
| bucket | menu | iterations | exact gap (bb) | record |
|---|---|---|---|---|
| pf10 | jam / fold | 25 | 0.00663 | data/gto_spot/records/pf10.json |
| pf15 / pf20 / pf25 | fold / open 2.0 (SB 3.0) / jam; vs open fold / call / 3-bet jam | 75 / 100 / 75 | 0.00751 / 0.00539 / 0.00736 | pf15/20/25.json |
| s30 / s40 | Plan A v2b parent menu (cfg_p60_v2b with stack S - 1/9) | 150 / 150 | 0.00913 / 0.00858 | s30.json / s40.json |
Run files: data/gto_spot/pushfold/runs/pf*/, data/gto_spot/stack3040/runs/s{30,40}/ (dump.jsonl.gz + SHA256SUMS) on that branch (not merged into this branch yet).
- Cross-session reproduction: the 40 bb parent was solved independently by 011TJ and by 01BLRH...: cfg identical (cfg_s40 = cfg_p40_v1), exact gap
  0.00858 bb at 150 iterations in both, dump.jsonl sha256 a092af6d5eb989aa11c622ad829c3b4083bf3d69b0bdaaddff94705e61af1589 IDENTICAL (checked 2026-10-19 by 01BLRH...).
  30 bb dump sha256 f8cc8ea5bbb8140bdd949b959119a7e75d84d313ce23323aa12b702b157e3671 (011TJ only).
- Same finding as the flat-call request: BB flat-call defence vs a 2.0 open ~100 % at 15-40 bb under the static continuation.
- 011TJ claims on 60 bb (btn_vs_bb_3b35, co_vs_sb_3b35) withdrawn, never started; btn_vs_bb_3b40 left to the 60 bb quick summary.

## 60 bb record for the T2 builder (01BLRH..., 2026-10-19)
data/gto_spot/records/s60.json (pushfold_record_v1; stack_bb 60, quick, symmetric-stack, static continuation for flop pots, gap 0.009568 bb) built with
tools/gto_spot/pushfold_record.py (011TJ's builder; env overrides PF_W / PF_CFG / PF_STD added). Verified: the same builder on 01BLRH...'s 40 bb dump
reproduces 011TJ's s40.json exactly. 100 bb later (parent paused at 200 its). Also fixed: data/gto_spot/quick/chart_*.json first double-weighted combos
(`mix` / `combos` only; class frequencies and EVs unaffected) - see data/gto_spot/quick/README.md.

## Decision 2026-10-20 (user, via the T2 bot-verification session): flat-call loop, remaining seats
1. BTN and CO run to convergence (max 8 steps). BTN vs BB converged at step 4 (record data/gto_spot/quick/p40_flat_btn_vs_bb.json, f426c9a8); CO in progress.
2. The other 7 spots (HJ, LJ, UTG, UTG+1, UTG+2, SB open, SB limp) get at most 3 steps (spec max_steps 3, tools/gto_spot/plan_a_flat_specs.py):
   they stop earlier when converged; if not converged at step 3 the quick record uses the mean of the last 2 steps and carries
   `stopped_at_step_cap: true` + `status_note` (tools/gto_spot/quick_spot.py).
3. 40 bb = 01BLRH..., 30 bb = 011TJ (unchanged). T2 connects the corrected BTN vs BB flat call (30 / 40 bb) first; tell T2 if the record format changes.
