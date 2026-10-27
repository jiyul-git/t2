# Effective-stack approximation, part A (push/fold, chip EV) - 2026-10-26, request from the T2 bot session (user: "1번 Gto제작1에 맡겨")
Code `tools/gto_icm/eff_stack_test.py`, data `data/gto_spot/icm/eff_stack_A.json`, picture `data/gto_spot/icm/eff_stack_A.png`. Measurement only; nothing is connected.
Game: jam/fold, first caller only, chip EV, ante 1 bb over 9 seats (folded seats leave dead money), blinds 0.5/1, 169 classes, exact gap <= 0.010 bb (same solver as the ICM pilot, `icm_pushfold.py`).
Asymmetric solution = Nash of the real stack vector. Approximation = per decision node the strategy of the symmetric game (all active seats at stack X, X from a rule). Loss = EV the approximate strategy loses at that node against the
asymmetric equilibrium of the others (unilateral deviation), bb, then summed over nodes with reach as weight (bb per hand dealt, all seats).
Rules: R1 = T2 (first-in X = min(own, max stack behind); facing a jam X = min(own, jammer)); R2 = first-in min(own, min stack behind); R3 = first-in expected min(own, first caller) with the asymmetric first-caller probabilities. Calls use R1 in all.
A3: the request lists 7 stacks behind UTG for 8 seats; BB was assumed 18 bb.

| config | R1 (T2) loss | R2 loss | R3 loss | R1 first-in mean abs diff / classes flipped | R1 call mean abs diff / classes flipped |
|---|---|---|---|---|---|
| A1 BTN 20, SB 8, BB 40 | 0.035 | 0.034 | 0.021 | 4.0 % / 15 | 3.3 % / 15 |
| A2 CO 15, BTN 40, SB 10, BB 10 | 0.016 | 0.013 | 0.012 | 1.6 % / 7 | 1.1 % / 10 |
| A3 9 seats mixed (25,10,40,15,60,8,30,20,18) | 0.069 | 0.117 | 0.046 | 2.3 % / 45 | 1.6 % / 108 |
| A4 check SB 20 vs BB 60 | 0.0099 | 0.0099 | 0.0099 | 0.0 % / 0 | 0.0 % / 0 |
Noise floor: the A4 check (identical to the 20 bb symmetric table) shows 0.0099 bb, equal to the solver gap tolerance, so losses below ~0.01 bb are noise. A4 first-in and call frequencies are identical (0 classes flip).

Largest node errors (R1): CO 8 bb calling HJ jam 10.0 pp (17 classes), CO 8 bb calling UTG+2 jam 8.1 pp (16), BTN 20 first-in with SB 8 behind 7.9 pp (15), HJ 60 bb first-in with a 30 bb max behind 6.9 pp (16), BB 40 calling BTN jam 5.7 pp (10).
Reading: typical node error is 1-4 pp; it is concentrated where (a) a SHORT stack acts and deeper stacks sit behind it (the symmetric table treats the seats behind as equally short, so the short stack calls too wide: CO 8 bb calls 12 vs 22 %), and (b) a deep stack opens with one much shorter stack behind (first-in range too narrow by 5-8 pp). Rule R3 (weighting by the callers' probabilities) halves the first-in error; the min-stack rule R2 is worse than T2's rule in the 9-seat spread.
Limits: 4 configs; jam/fold, first caller only, no flop play; chip EV; X is solved exactly (no stack bucket rounding); loss includes solver noise 0.01 bb. Part B (30-60 bb with flops) is NOT done: it needs flop-panel solves and is queued after the running calculations.
