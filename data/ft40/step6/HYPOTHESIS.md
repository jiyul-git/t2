# ft40 step 6 hypothesis (coordinator decision 2026-11-26)

Step 6 keeps step 5 conditions: balanced panel (FT_PANEL_SET=bal), two-player endpoint tables only (no three-way tables), mixing alpha unchanged (0.5, 0.25 for cycling endpoints).

## H1
The three-step rise of dM_vs_prev_step median (0.670 -> 0.728 -> 0.823, steps 3-5) is a transient effect of the step 4 -> 5 panel change (prec -> bal).

Prediction: at step 6, with conditions unchanged, dM_vs_prev_step median < 0.823 and D/U median < 1.04 (step 5 values; D<=U seats 30/68, D/U max 3.49).

## Falsification
If dM rises again at step 6, the panel is not the cause. The oscillation then comes from the two-player table update (mixing alpha). Next: lower alpha, or review three-way tables.

## Why no three-way tables now
Adding them now would change two variables at once and H1 could not be judged.

## Operations
Tables: 49 (next_tables 5, commit 006f52712). Tree solve to exact gap < 0.02, then prepare (20 sessions, FT_PANEL_SET=bal). Each board session gets an hourly wake-up trigger (create_trigger, persistent_session_id).
