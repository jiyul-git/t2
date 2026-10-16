# Plan A v2b: is the step-to-step oscillation indifference? (analysis, 2026-10-16)

Read-only analysis. No rule, criterion or tool of the census branch was changed. The amendment text in section 4 is a DRAFT for the user's decision.

Method: `analysis/plan_a_ev_gap/ev_gap.py <spot_id> <step> <out.json>` re-solves the HU subgame of a finished step from its saved `tables_used.json` / `matrices_used.json` (the same call `grade_spot.py` makes, ~3 s) and writes, for every class that reaches a node, the action frequencies and action EVs (bb) of the acting seat. The "gap" is EV(best action) - EV(second best). Data: `analysis/plan_a_ev_gap/*.json`. The decisive node is the root of the subgame (opener facing the 3-bet).

## 1. p60v2b_utg_vs_btn (UTG opens 2, BTN 3-bets 6; UTG root: fold / call 6 / 4-bet 14.1 / jam), steps 0-9
- The oscillation is real, not indifference. At every step 34-47% of the reaching combos change their best action versus the previous step, and 21-86% of the combos have a gap > 0.3 bb inside a step.
- AA, EV in bb (call / 4-bet): s2 18.3 / 20.5, s3 20.0 / 19.7, s4 18.5 / 20.4, s5 20.3 / 20.3, s6 17.8 / 19.7, s7 20.0 / 20.0, s8 18.4 / 20.6, s9 20.2 / 20.1. Even steps: 4-bet better by 0.5-1.5 bb; odd steps: call better by 0.01-0.35 bb. The pot at 4-bet-call is ~30 bb, so these are small relative to the stakes but far above the 0.01 bb gate.
- Cause: the 4-bet terminal is a flop all-in fight at 60 bb whose value depends strongly on the opponent's arriving range (BTN 4-bet-call combos 0.2 / 31 / 36 / 21 between steps). The ranges chase each other: the matrix fixed point is the unstable part, not the strategy mix.
- Averaging helps: the mean strategy of steps 6-9, evaluated with each step's EVs, loses 0.05-0.14 bb per combo against the best response of that step (own-step loss is 0 by definition). Usable as an approximate frequency, not as a verified one (the standard's tolerance is 0.010 bb).
- Observed UTG root frequency of AA: call 100% (odd steps) / 4-bet 100% (even steps); the 4-step mean is roughly 50 / 50. AKs / QQ / TT / JJ also cycle between call, fold and 4-bet.

## 2. p60v2b_btn_vs_bb_3b40 (BTN opens 2, BB 3-bets 8; BTN root: fold / call 8 / 4-bet 17.2 / jam), steps 0-3 (converged)
- Much more stable: step 1 / 2 / 3 best-action flips 48% / 25% / 19% of the combos.
- AA: call 100% at steps 2 and 3 (gap 2.6 / 1.1 bb); KK call (gap 0.48 / 0.02); AKo 4-bet / jam mix; JJ 4-bet then jam (gap 0.33 / 0.01).
- This spot converged at step 3 under v4 (converged_strict=false: amendment 8 exemption used).

## 3. p60v2b_co_vs_sb_3b40 (CO opens 2, SB 3-bets 8; CO root same actions), accepted state of step 2
- 8% of the combos have a gap < 0.05 bb, 34% < 0.3 bb. AA call 100% (gap 1.95), KK call (0.73), QQ call (0.59), AKs call (0.24), AKo call / jam 84 / 16 (gap 0.0001), JJ jam (0.11), TT call (0.26).
- Only the accepted state of step 2 could be analysed (the step directories of the earlier container are lost; rebuilt from `state.json`).

## 4. DRAFT amendment (not registered, not applied; user decides)
Reason: utg_vs_btn shows a period-2 cycle that v4 damping does not remove; 12 steps will end as `research`. Proposal: when the spot strategy cycles (>= 25% of the reaching combos change their best action on each of the last 4 steps) the loop stops with status `cycle`, the record stores the mean frequencies of the last 4 steps and, per node, the reach-weighted EV loss of that mean strategy against each of the 4 steps' EVs (this analysis). Cap: `provisional`; never `verified`; both verdicts (strict D <= U and `cycle`) are kept. This changes no existing criterion; it only adds a label for spots that would otherwise end as `research`.

## 5. Priorities before the Monday reset
- Compute is not shared (one container per spot), so there is no competition; order only decides what the user reviews first: btn_vs_bb_3b40 (nearest to a P144 verdict), then hj_vs_bb_3b40 / utg1_vs_sb_3b40 (step 1 of up to 12), then co_vs_sb_3b40 (P144 pass has to be recomputed), utg_vs_btn (cycle; decision in section 4).
- Every container must be backed up per step (done) and relaunched every 2 h (tracked tasks stop at the limit).
