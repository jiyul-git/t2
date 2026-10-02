# 30bb RFI diagnostic — solver 30bb vs Jens 20bb / 40bb (v1)

**Diagnostic only.** No solver or DB value was changed. No new solve was run.

- Solver: GTOpen 30bb pilot, `chatgpt/mini-cfr-solver-20260928@434abfe`, iteration 20, gap_total 0.309 (target 0.5). Tree: no limp, open 2bb (SB 2.5bb) or jam; opener vs 3-bet can only call/fold.
- Jens: 9-max MTT 20bb / 40bb, `chatgpt/gto-external-harvest-20261003@c7f2cb3`. Ante, open size, raise/jam split, and chipEV/ICM are not recorded in the pack. Values are chart-rounded.
- **No exact 30bb hand-level reference exists in any branch.** 20/40 are a stack-sensitivity bracket, not truth. Being "inside" the bracket is not proof of correctness, and being "below both" is not proof of error, because a hand's open frequency need not be monotone in stack depth.
- Open = raise + jam. Raw solver actions are kept in the JSON. SB is handled separately (solver has no limp).

## 1. Aggregate RFI (% of 1326 combos)

| Pos | Jens 20 | Solver 30 (raise / jam) | Jens 40 | 20–40 midpoint | PR 30 agg | inside 20–40? | missing mass | extra mass | midpoint residual |
|---|---:|---:|---:|---:|---:|:-:|---:|---:|---:|
| UTG | 16.0 | **10.6** (9.9 / 0.7) | 15.3 | 15.6 | 16.5 | NO | -4.5 | 0.2 | -5.0 |
| UTG+1 | 17.4 | **12.2** (11.8 / 0.4) | 17.2 | 17.3 | 18.6 | NO | -4.7 | 0.1 | -5.2 |
| UTG+2 | 19.7 | **12.6** (12.3 / 0.3) | 19.7 | 19.7 | 21.7 | NO | -6.0 | 0.2 | -7.1 |
| LJ | 21.6 | **15.5** (15.2 / 0.3) | 23.4 | 22.5 | 25.7 | NO | -6.3 | 0.3 | -7.0 |
| HJ | 26.2 | **20.1** (19.6 / 0.6) | 27.4 | 26.8 | 29.9 | NO | -5.8 | 0.5 | -6.7 |
| CO | 31.8 | **26.1** (23.6 / 2.5) | 35.6 | 33.7 | 37.5 | NO | -7.1 | 0.7 | -7.6 |
| BTN | 41.9 | **35.6** (28.4 / 7.2) | 50.0 | 45.9 | 48.7 | NO | -6.3 | 0.0 | -10.3 |
| SB | 31.4 | **60.4** (34.9 / 25.6) | 57.8 | 44.6 | 89.4 | NO | -0.7 | 3.8 | +15.8 |

SB note: Jens 20bb SB = open 31.4% + **limp 53.1%**; Jens 40bb SB = open 57.8%, limp 0.0%. The solver tree has no limp option, so SB raise-vs-raise is not a like-for-like comparison at 20bb. PR 30 SB 89.4% very likely includes limps and uses 3.5bb opens — not comparable.

## 2. Where the gap sits: reference class (by Jens 20+40 agreement)

clear_open = both ≥95%, clear_fold = both ≤5%, boundary = everything else. Mass in pp of 1326 combos.

| Pos | clear_open: solver avg / missing | boundary: solver avg vs midpoint / missing | clear_fold: solver avg / midpoint residual | clear_open hands below both |
|---|---|---|---|---|
| UTG | 74.4% / -3.3 | 14.6% vs 50.4% / -1.2 | 0.2% / +0.1 | A9s, A8s, A7s, A6s, A5s, A4s, KJs, KTs, K9s, KQo, QJs, QTs, AJo, JTs, T9s |
| UTG+1 | 72.9% / -4.3 | 9.2% vs 29.5% / -0.5 | 0.2% / +0.1 | A9s, A8s, A7s, A6s, A5s, A4s, KTs, K9s, K8s, KQo, QJs, QTs, Q9s, KJo, JTs, J9s, ATo, T9s |
| UTG+2 | 71.0% / -4.8 | 7.0% vs 41.9% / -1.1 | 0.3% / +0.3 | A9s, A8s, A7s, A6s, A5s, A4s, A3s, KTs, K9s, K8s, QJs, QTs, Q9s, KJo, JTs, J9s, ATo, T9s, T8s, 98s |
| LJ | 74.3% / -5.0 | 13.0% vs 51.1% / -1.3 | 0.2% / +0.2 | A7s, A6s, A5s, A4s, A3s, K8s, K7s, Q9s, Q8s, KJo, QJo, JTs, J9s, T9s, T8s, A9o, 98s |
| HJ | 77.2% / -5.6 | 8.4% vs 37.0% / -0.2 | 0.8% / +0.6 | A7s, A6s, A4s, A3s, A2s, K8s, K7s, K6s, K5s, Q9s, Q8s, QJo, J9s, J8s, KTo, QTo, JTo, T9s, T8s, A9o, 98s, A8o, 87s |
| CO | 81.6% / -5.4 | 16.3% vs 56.0% / -1.7 | 1.0% / +0.7 | A4s, A3s, A2s, K8s, K7s, K6s, K5s, K4s, Q9s, Q8s, Q7s, Q6s, QJo, J9s, J8s, J7s, KTo, QTo, JTo, T9s, T8s, T7s, K9o, 98s, 97s, 87s, A7o, A5o |
| BTN | 87.1% / -5.0 | 8.1% vs 57.1% / -1.3 | 0.1% / +0.1 | K7s, K5s, K4s, K3s, Q8s, Q7s, Q6s, Q5s, Q4s, J8s, J7s, J6s, J5s, JTo, T8s, T7s, T6s, K9o, Q9o, J9o, T9o, 97s, K8o, 87s, 86s, 76s, A3o, A2o |
| SB | 97.9% / -0.2 | 79.9% vs 55.6% / -0.5 | 3.8% / +1.1 | T4s |

## 3. Family decomposition — missing mass below the 20–40 bracket (pp of 1326)

| Pos | pair | suited_Ax | suited_Kx | suited_broadway | suited_connector | suited_one_gapper | suited_other | offsuit_Ax | offsuit_broadway | offsuit_other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| UTG | 0.0 | -1.5 | -0.4 | -0.5 | -0.3 | -0.3 | -0.3 | -0.4 | -0.9 | 0.0 |
| UTG+1 | 0.0 | -1.6 | -0.5 | -0.4 | -0.5 | -0.3 | -0.3 | -0.4 | -0.7 | 0.0 |
| UTG+2 | 0.0 | -1.6 | -0.6 | -0.3 | -0.6 | -0.6 | -0.3 | -0.3 | -1.7 | 0.0 |
| LJ | 0.0 | -1.1 | -0.7 | -0.0 | -0.8 | -0.6 | -0.6 | -0.7 | -1.9 | 0.0 |
| HJ | 0.0 | -0.6 | -0.9 | 0.0 | -0.7 | -0.6 | -0.5 | -0.5 | -2.1 | 0.0 |
| CO | 0.0 | -0.2 | -0.7 | 0.0 | -0.6 | -0.7 | -1.6 | -0.9 | -0.9 | -1.6 |
| BTN | 0.0 | 0.0 | -0.3 | 0.0 | -0.2 | -0.3 | -2.1 | -0.2 | -0.1 | -3.1 |
| SB | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | -0.7 | 0.0 | 0.0 | 0.0 |

Family open rate (pp of all 1326 combos): Jens 20 / solver 30 / Jens 40

| Pos | pair | suited_Ax | suited_Kx | suited_broadway | suited_connector | suited_one_gapper | suited_other | offsuit_Ax | offsuit_broadway | offsuit_other |
|---|---|---|---|---|---|---|---|---|---|---|
| UTG | 4.1 / **4.3** / 4.1 | 3.1 / **1.6** / 3.3 | 1.5 / **0.8** / 1.2 | 0.9 / **0.4** / 0.9 | 0.4 / **0.0** / 0.5 | 0.3 / **0.0** / 0.3 | 0.3 / **0.0** / 0.3 | 3.6 / **2.8** / 3.1 | 1.7 / **0.7** / 1.5 | 0.0 / **0.0** / 0.0 |
| UTG+1 | 4.2 / **4.5** / 4.5 | 3.3 / **1.7** / 3.3 | 1.5 / **1.0** / 1.5 | 0.9 / **0.5** / 0.9 | 0.5 / **0.0** / 0.8 | 0.5 / **0.0** / 0.4 | 0.3 / **0.0** / 0.3 | 3.8 / **3.2** / 3.6 | 2.4 / **1.2** / 1.8 | 0.0 / **0.0** / 0.0 |
| UTG+2 | 4.4 / **4.7** / 4.5 | 3.3 / **1.7** / 3.6 | 1.7 / **1.1** / 1.7 | 0.9 / **0.6** / 0.9 | 0.6 / **0.0** / 1.1 | 0.6 / **0.0** / 0.6 | 0.6 / **0.0** / 0.3 | 4.4 / **3.3** / 3.6 | 3.1 / **1.1** / 3.3 | 0.0 / **0.0** / 0.0 |
| LJ | 4.5 / **5.0** / 4.8 | 3.3 / **2.2** / 3.6 | 2.0 / **1.3** / 2.1 | 0.9 / **0.9** / 0.9 | 0.9 / **0.1** / 1.3 | 0.6 / **0.0** / 0.6 | 0.9 / **0.1** / 0.7 | 4.5 / **3.8** / 4.5 | 3.8 / **2.0** / 4.8 | 0.0 / **0.0** / 0.0 |
| HJ | 4.7 / **5.4** / 5.0 | 3.6 / **3.0** / 3.6 | 2.4 / **1.6** / 2.7 | 0.9 / **0.9** / 0.9 | 0.9 / **0.2** / 1.8 | 0.7 / **0.2** / 0.9 | 1.3 / **0.5** / 1.3 | 6.2 / **4.9** / 5.4 | 5.4 / **3.3** / 5.4 | 0.0 / **0.1** / 0.4 |
| CO | 5.0 / **5.8** / 5.4 | 3.6 / **3.4** / 3.6 | 2.7 / **2.1** / 3.3 | 0.9 / **0.9** / 0.9 | 1.1 / **0.5** / 1.8 | 1.1 / **0.4** / 1.3 | 2.3 / **0.7** / 2.8 | 7.5 / **7.0** / 7.7 | 5.4 / **4.5** / 5.4 | 2.2 / **0.7** / 3.3 |
| BTN | 5.9 / **5.9** / 5.7 | 3.6 / **3.6** / 3.6 | 3.0 / **2.8** / 3.3 | 0.9 / **0.9** / 0.9 | 1.2 / **1.0** / 1.8 | 1.2 / **0.9** / 1.8 | 3.6 / **1.5** / 6.0 | 10.9 / **10.6** / 10.9 | 5.4 / **5.3** / 5.4 | 6.1 / **3.1** / 10.5 |
| SB | 4.2 / **5.9** / 5.9 | 1.8 / **3.6** / 3.6 | 0.5 / **3.3** / 3.3 | 0.3 / **0.9** / 0.9 | 0.8 / **1.8** / 1.8 | 0.3 / **1.9** / 2.1 | 2.8 / **6.2** / 7.8 | 8.1 / **10.9** / 10.9 | 2.2 / **5.4** / 5.4 | 10.4 / **20.5** / 16.0 |

Hands below both brackets, by family:

- **UTG** — suited_Ax: A9s, A8s, A7s, A6s, A5s, A4s, A3s; suited_Kx: KJs, KTs, K9s; suited_broadway: QJs, QTs, JTs; suited_connector: T9s; suited_one_gapper: J9s; suited_other: Q9s; offsuit_Ax: AJo, ATo; offsuit_broadway: KQo, KJo
- **UTG+1** — suited_Ax: A9s, A8s, A7s, A6s, A5s, A4s, A3s; suited_Kx: KTs, K9s, K8s; suited_broadway: QJs, QTs, JTs; suited_connector: T9s, 98s; suited_one_gapper: J9s, T8s; suited_other: Q9s; offsuit_Ax: ATo; offsuit_broadway: KQo, KJo
- **UTG+2** — suited_Ax: A9s, A8s, A7s, A6s, A5s, A4s, A3s; suited_Kx: KTs, K9s, K8s, K7s; suited_broadway: QJs, QTs, JTs; suited_connector: T9s, 98s; suited_one_gapper: J9s, T8s; suited_other: Q9s; offsuit_Ax: ATo; offsuit_broadway: KJo, QJo, KTo
- **LJ** — suited_Ax: A7s, A6s, A5s, A4s, A3s; suited_Kx: K8s, K7s, K6s; suited_broadway: JTs; suited_connector: T9s, 98s, 87s; suited_one_gapper: J9s, T8s; suited_other: Q9s, Q8s, J8s; offsuit_Ax: A9o; offsuit_broadway: KJo, QJo, KTo, QTo, JTo
- **HJ** — suited_Ax: A7s, A6s, A4s, A3s, A2s; suited_Kx: K8s, K7s, K6s, K5s; suited_connector: T9s, 98s, 87s; suited_one_gapper: J9s, T8s, 97s; suited_other: Q9s, Q8s, Q7s, J8s; offsuit_Ax: A9o, A8o; offsuit_broadway: QJo, KTo, QTo, JTo
- **CO** — suited_Ax: A4s, A3s, A2s; suited_Kx: K8s, K7s, K6s, K5s, K4s; suited_connector: T9s, 98s, 87s, 76s; suited_one_gapper: J9s, T8s, 97s, 86s; suited_other: Q9s, Q8s, Q7s, Q6s, Q5s, J8s, J7s, T7s; offsuit_Ax: A7o, A5o; offsuit_broadway: QJo, KTo, QTo, JTo; offsuit_other: K9o, Q9o, J9o, T9o
- **BTN** — suited_Kx: K7s, K5s, K4s, K3s; suited_connector: 87s, 76s, 65s; suited_one_gapper: T8s, 97s, 86s; suited_other: Q8s, Q7s, Q6s, Q5s, Q4s, J8s, J7s, J6s, J5s, T7s, T6s, 96s; offsuit_Ax: A3o, A2o; offsuit_broadway: JTo; offsuit_other: K9o, Q9o, J9o, T9o, K8o, Q8o, J8o, T8o, K7o
- **SB** — suited_other: J3s, J2s, T4s, T3s, T2s, 84s

## 4. Boundary hands (Jens 20/40 disagree or mix), sorted by midpoint residual

### UTG

| Hand | family | J20 | Solver 30 (jam) | J40 | residual | bracket |
|---|---|---:|---:|---:|---:|---|
| J9s | suited_one_gapper | 92.0 | 1.1 (0.2) | 100.0 | -94.9 | below_both |
| Q9s | suited_other | 100.0 | 1.7 (0.3) | 92.1 | -94.3 | below_both |
| KJo | offsuit_broadway | 80.0 | 11.6 (0.5) | 68.2 | -62.6 | below_both |
| A3s | suited_Ax | 13.0 | 0.8 (0.6) | 100.0 | -55.7 | below_both |
| K8s | suited_Kx | 97.0 | 0.9 (0.3) | 2.3 | -48.8 | inside |
| 65s | suited_connector | 0.0 | 0.0 (0.0) | 75.7 | -37.8 | inside |
| ATo | offsuit_Ax | 100.0 | 38.3 (0.9) | 44.9 | -34.2 | below_both |
| 98s | suited_connector | 46.0 | 1.2 (0.2) | 0.0 | -21.8 | inside |
| QJo | offsuit_broadway | 8.0 | 0.8 (0.3) | 0.0 | -3.2 | inside |
| 55 | pair | 17.0 | 55.9 (0.8) | 11.4 | +41.7 | above_both |

### HJ

| Hand | family | J20 | Solver 30 (jam) | J40 | residual | bracket |
|---|---|---:|---:|---:|---:|---|
| 97s | suited_one_gapper | 48.0 | 0.2 (0.1) | 100.0 | -73.8 | below_both |
| Q7s | suited_other | 100.0 | 0.4 (0.2) | 18.7 | -59.0 | below_both |
| 65s | suited_connector | 0.0 | 0.0 (0.0) | 100.0 | -50.0 | inside |
| 54s | suited_connector | 0.0 | 0.0 (0.0) | 100.0 | -50.0 | inside |
| 76s | suited_connector | 0.0 | 0.0 (0.0) | 100.0 | -50.0 | inside |
| T7s | suited_other | 0.0 | 0.3 (0.2) | 100.0 | -49.7 | inside |
| K4s | suited_Kx | 0.0 | 0.4 (0.2) | 100.0 | -49.6 | inside |
| A7o | offsuit_Ax | 65.0 | 0.9 (0.2) | 0.0 | -31.6 | inside |
| T9o | offsuit_other | 0.0 | 0.3 (0.2) | 41.6 | -20.6 | inside |
| Q6s | suited_other | 15.0 | 0.4 (0.2) | 0.0 | -7.1 | inside |
| A5o | offsuit_Ax | 15.0 | 0.7 (0.2) | 0.0 | -6.8 | inside |
| 44 | pair | 49.0 | 99.4 (0.3) | 100.0 | +24.9 | inside |

### CO

| Hand | family | J20 | Solver 30 (jam) | J40 | residual | bracket |
|---|---|---:|---:|---:|---:|---|
| 86s | suited_one_gapper | 56.0 | 0.0 (0.0) | 100.0 | -78.0 | below_both |
| 76s | suited_connector | 56.0 | 0.0 (0.0) | 100.0 | -78.0 | below_both |
| Q5s | suited_other | 57.0 | 1.2 (0.2) | 100.0 | -77.3 | below_both |
| T9o | offsuit_other | 46.0 | 0.5 (0.3) | 100.0 | -72.5 | below_both |
| J9o | offsuit_other | 42.0 | 0.7 (0.3) | 100.0 | -70.3 | below_both |
| Q9o | offsuit_other | 52.0 | 8.9 (0.2) | 69.7 | -51.9 | below_both |
| 65s | suited_connector | 0.0 | 0.0 (0.0) | 100.0 | -50.0 | inside |
| 54s | suited_connector | 0.0 | 0.0 (0.0) | 100.0 | -50.0 | inside |
| Q4s | suited_other | 0.0 | 0.2 (0.2) | 100.0 | -49.8 | inside |
| K2s | suited_Kx | 0.0 | 0.7 (0.2) | 100.0 | -49.3 | inside |
| K3s | suited_Kx | 0.0 | 29.9 (0.2) | 100.0 | -20.1 | inside |
| 75s | suited_one_gapper | 0.0 | 0.0 (0.0) | 18.7 | -9.3 | inside |
| T6s | suited_other | 0.0 | 0.2 (0.1) | 14.4 | -7.0 | inside |
| A6o | offsuit_Ax | 33.0 | 58.4 (0.2) | 51.4 | +16.3 | above_both |
| 33 | pair | 0.0 | 97.4 (2.7) | 100.0 | +47.4 | inside |

### BTN

| Hand | family | J20 | Solver 30 (jam) | J40 | residual | bracket |
|---|---|---:|---:|---:|---:|---|
| Q8o | offsuit_other | 55.0 | 2.3 (0.3) | 100.0 | -75.2 | below_both |
| J8o | offsuit_other | 49.0 | 0.9 (0.2) | 100.0 | -73.6 | below_both |
| T8o | offsuit_other | 11.0 | 1.0 (0.5) | 100.0 | -54.5 | below_both |
| K7o | offsuit_other | 57.0 | 26.2 (0.2) | 100.0 | -52.3 | below_both |
| 96s | suited_other | 7.0 | 1.9 (1.3) | 100.0 | -51.6 | below_both |
| 65s | suited_connector | 8.0 | 2.8 (1.6) | 100.0 | -51.2 | below_both |
| 95s | suited_other | 0.0 | 0.0 (0.0) | 100.0 | -50.0 | inside |
| 85s | suited_other | 0.0 | 0.0 (0.0) | 100.0 | -50.0 | inside |
| 75s | suited_one_gapper | 0.0 | 0.0 (0.0) | 100.0 | -50.0 | inside |
| 64s | suited_one_gapper | 0.0 | 0.0 (0.0) | 100.0 | -50.0 | inside |
| 54s | suited_connector | 0.0 | 0.0 (0.0) | 100.0 | -50.0 | inside |
| T5s | suited_other | 0.0 | 0.1 (0.0) | 100.0 | -49.9 | inside |
| J3s | suited_other | 0.0 | 0.1 (0.0) | 100.0 | -49.9 | inside |
| J4s | suited_other | 0.0 | 0.2 (0.2) | 100.0 | -49.8 | inside |
| Q2s | suited_other | 0.0 | 0.4 (0.2) | 100.0 | -49.6 | inside |
| 98o | offsuit_other | 0.0 | 0.9 (0.5) | 100.0 | -49.1 | inside |
| Q3s | suited_other | 0.0 | 2.2 (0.2) | 100.0 | -47.8 | inside |
| K6o | offsuit_other | 0.0 | 4.5 (0.2) | 100.0 | -45.5 | inside |
| K2s | suited_Kx | 9.0 | 23.0 (0.3) | 100.0 | -31.5 | inside |
| 87o | offsuit_other | 0.0 | 0.0 (0.0) | 59.6 | -29.8 | inside |
| 22 | pair | 100.0 | 99.8 (96.6) | 55.8 | +21.9 | inside |

### SB

| Hand | family | J20 | Solver 30 (jam) | J40 | residual | bracket |
|---|---|---:|---:|---:|---:|---|
| T3s | suited_other | 90.0 | 15.3 (6.1) | 100.0 | -79.7 | below_both |
| T2s | suited_other | 37.0 | 4.5 (0.8) | 100.0 | -64.0 | below_both |
| J3s | suited_other | 90.0 | 53.3 (11.0) | 100.0 | -41.7 | below_both |
| J2s | suited_other | 54.0 | 42.2 (4.3) | 100.0 | -34.8 | below_both |
| 84s | suited_other | 48.0 | 40.7 (36.0) | 100.0 | -33.3 | below_both |
| 97o | offsuit_other | 30.0 | 33.5 (21.4) | 100.0 | -31.5 | inside |
| 52s | suited_other | 60.0 | 2.7 (1.1) | 0.0 | -27.3 | inside |
| T7o | offsuit_other | 41.0 | 49.3 (7.3) | 100.0 | -21.2 | inside |
| 42s | suited_one_gapper | 44.0 | 0.8 (0.7) | 0.0 | -21.2 | inside |
| T5s | suited_other | 53.0 | 56.4 (26.7) | 100.0 | -20.1 | inside |
| 63s | suited_other | 54.0 | 11.9 (7.3) | 0.0 | -15.1 | inside |
| 93s | suited_other | 53.0 | 15.9 (9.7) | 0.0 | -10.6 | inside |
| J4s | suited_other | 68.0 | 74.1 (10.7) | 100.0 | -9.9 | inside |
| J7o | offsuit_other | 56.0 | 68.6 (0.6) | 100.0 | -9.4 | inside |
| 94s | suited_other | 51.0 | 17.2 (8.9) | 0.0 | -8.3 | inside |
| 53s | suited_one_gapper | 11.0 | 49.7 (45.5) | 100.0 | -5.8 | inside |
| 95s | suited_other | 65.0 | 77.2 (70.2) | 100.0 | -5.3 | inside |
| 96o | offsuit_other | 12.0 | 1.6 (0.5) | 0.0 | -4.4 | inside |
| 32s | suited_connector | 7.0 | 0.1 (0.1) | 0.0 | -3.4 | inside |
| 65o | offsuit_other | 15.0 | 4.1 (1.2) | 0.0 | -3.4 | inside |
| 54o | offsuit_other | 10.0 | 2.8 (1.0) | 0.0 | -2.2 | inside |
| 43s | suited_connector | 25.0 | 13.0 (10.2) | 0.0 | +0.5 | inside |
| 87o | offsuit_other | 30.0 | 66.3 (60.6) | 100.0 | +1.3 | inside |
| A7s | suited_Ax | 92.0 | 100.0 (71.9) | 100.0 | +4.0 | inside |
| 74s | suited_other | 23.0 | 65.7 (62.4) | 100.0 | +4.2 | inside |
| T6o | offsuit_other | 24.0 | 17.2 (0.7) | 0.0 | +5.2 | inside |
| KK | pair | 87.0 | 100.0 (8.0) | 100.0 | +6.5 | inside |
| 99 | pair | 86.0 | 100.0 (8.6) | 100.0 | +7.0 | inside |
| 76o | offsuit_other | 23.0 | 18.8 (14.6) | 0.0 | +7.3 | inside |
| TT | pair | 85.0 | 100.0 (7.0) | 100.0 | +7.5 | inside |
| AJs | suited_Ax | 80.0 | 100.0 (94.8) | 100.0 | +10.0 | inside |
| 88 | pair | 80.0 | 100.0 (20.8) | 100.0 | +10.0 | inside |
| AKs | suited_Ax | 76.0 | 100.0 (95.4) | 100.0 | +12.0 | inside |
| K8o | offsuit_other | 75.0 | 99.9 (1.1) | 100.0 | +12.4 | inside |
| JTs | suited_broadway | 74.0 | 100.0 (91.0) | 100.0 | +13.0 | inside |
| AQs | suited_Ax | 72.0 | 100.0 (94.7) | 100.0 | +14.0 | inside |
| Q7o | offsuit_other | 54.0 | 92.3 (0.5) | 100.0 | +15.3 | inside |
| Q6o | offsuit_other | 80.0 | 91.0 (0.5) | 70.7 | +15.6 | above_both |
| KTo | offsuit_broadway | 67.0 | 100.0 (20.2) | 100.0 | +16.5 | inside |
| A9s | suited_Ax | 67.0 | 100.0 (97.8) | 100.0 | +16.5 | inside |
| 86o | offsuit_other | 26.0 | 30.0 (24.4) | 0.0 | +17.0 | inside |
| KQs | suited_Kx | 65.0 | 100.0 (34.7) | 100.0 | +17.5 | inside |
| 77 | pair | 63.0 | 100.0 (35.3) | 100.0 | +18.5 | inside |
| KJo | offsuit_broadway | 62.0 | 100.0 (58.2) | 100.0 | +19.0 | inside |
| 85s | suited_other | 40.0 | 89.0 (84.5) | 100.0 | +19.0 | inside |
| K7o | offsuit_other | 60.0 | 99.7 (1.0) | 100.0 | +19.7 | inside |
| A8s | suited_Ax | 60.0 | 100.0 (84.6) | 100.0 | +20.0 | inside |
| JJ | pair | 60.0 | 100.0 (5.5) | 100.0 | +20.0 | inside |
| A6s | suited_Ax | 59.0 | 100.0 (72.0) | 100.0 | +20.5 | inside |
| J8o | offsuit_other | 45.0 | 93.0 (1.1) | 100.0 | +20.5 | inside |
| Q8o | offsuit_other | 53.0 | 98.2 (0.7) | 100.0 | +21.7 | inside |
| J5o | offsuit_other | 17.0 | 30.6 (0.4) | 0.0 | +22.1 | above_both |
| K5o | offsuit_other | 50.0 | 97.6 (0.6) | 100.0 | +22.6 | inside |
| KQo | offsuit_broadway | 54.0 | 100.0 (88.9) | 100.0 | +23.0 | inside |
| K6o | offsuit_other | 50.0 | 99.0 (0.9) | 100.0 | +24.0 | inside |
| 64s | suited_one_gapper | 28.0 | 88.1 (83.9) | 100.0 | +24.1 | inside |
| 98o | offsuit_other | 35.0 | 92.0 (65.3) | 100.0 | +24.5 | inside |
| K9o | offsuit_other | 51.0 | 100.0 (3.7) | 100.0 | +24.5 | inside |
| T8o | offsuit_other | 35.0 | 92.3 (26.9) | 100.0 | +24.8 | inside |
| QQ | pair | 50.0 | 100.0 (5.8) | 100.0 | +25.0 | inside |
| Q9o | offsuit_other | 46.0 | 99.8 (1.8) | 100.0 | +26.8 | inside |
| KJs | suited_Kx | 46.0 | 100.0 (49.1) | 100.0 | +27.0 | inside |
| J9o | offsuit_other | 40.0 | 98.3 (7.3) | 100.0 | +28.3 | inside |
| 76s | suited_connector | 30.0 | 98.5 (95.5) | 100.0 | +33.5 | inside |
| K9s | suited_Kx | 33.0 | 100.0 (19.2) | 100.0 | +33.5 | inside |
| T7s | suited_other | 30.0 | 98.7 (71.2) | 100.0 | +33.7 | inside |
| ATo | offsuit_Ax | 30.0 | 100.0 (95.3) | 100.0 | +35.0 | inside |
| AJo | offsuit_Ax | 30.0 | 100.0 (95.9) | 100.0 | +35.0 | inside |
| QJo | offsuit_broadway | 29.0 | 100.0 (49.4) | 100.0 | +35.5 | inside |
| QTo | offsuit_broadway | 26.0 | 100.0 (23.8) | 100.0 | +37.0 | inside |
| Q5o | offsuit_other | 80.0 | 77.2 (0.5) | 0.0 | +37.2 | inside |
| AQo | offsuit_Ax | 20.0 | 100.0 (96.2) | 100.0 | +40.0 | inside |
| 66 | pair | 20.0 | 100.0 (55.8) | 100.0 | +40.0 | inside |
| QJs | suited_broadway | 20.0 | 100.0 (67.1) | 100.0 | +40.0 | inside |
| AKo | offsuit_Ax | 19.0 | 100.0 (96.9) | 100.0 | +40.5 | inside |
| J6o | offsuit_other | 8.0 | 44.6 (0.4) | 0.0 | +40.6 | above_both |
| J5s | suited_other | 0.0 | 91.8 (19.7) | 100.0 | +41.8 | inside |
| Q2s | suited_other | 0.0 | 92.2 (1.4) | 100.0 | +42.2 | inside |
| KTs | suited_Kx | 15.0 | 100.0 (27.0) | 100.0 | +42.5 | inside |
| T6s | suited_other | 0.0 | 93.8 (45.4) | 100.0 | +43.8 | inside |
| J6s | suited_other | 0.0 | 94.7 (14.6) | 100.0 | +44.7 | inside |
| 96s | suited_other | 0.0 | 95.1 (85.4) | 100.0 | +45.1 | inside |
| 75s | suited_one_gapper | 0.0 | 95.4 (92.7) | 100.0 | +45.4 | inside |
| Q3s | suited_other | 0.0 | 96.3 (3.9) | 100.0 | +46.3 | inside |
| T9o | offsuit_other | 3.0 | 98.2 (32.2) | 100.0 | +46.7 | inside |
| JTo | offsuit_broadway | 6.0 | 99.9 (50.3) | 100.0 | +46.9 | inside |
| Q4s | suited_other | 0.0 | 97.0 (5.7) | 100.0 | +47.0 | inside |
| 54s | suited_connector | 0.0 | 97.3 (94.8) | 100.0 | +47.3 | inside |
| J7s | suited_other | 0.0 | 98.3 (28.1) | 100.0 | +48.3 | inside |
| 65s | suited_connector | 0.0 | 98.4 (97.8) | 100.0 | +48.4 | inside |
| 86s | suited_one_gapper | 0.0 | 98.6 (94.3) | 100.0 | +48.6 | inside |
| Q5s | suited_other | 0.0 | 98.6 (20.5) | 100.0 | +48.6 | inside |
| Q7s | suited_other | 0.0 | 98.9 (4.5) | 100.0 | +48.9 | inside |
| 97s | suited_one_gapper | 0.0 | 99.0 (90.7) | 100.0 | +49.0 | inside |
| Q6s | suited_other | 0.0 | 99.5 (31.1) | 100.0 | +49.5 | inside |
| K2s | suited_Kx | 0.0 | 99.6 (4.7) | 100.0 | +49.6 | inside |
| K3s | suited_Kx | 0.0 | 99.7 (4.9) | 100.0 | +49.7 | inside |
| 98s | suited_connector | 0.0 | 99.8 (95.4) | 100.0 | +49.8 | inside |
| T8s | suited_one_gapper | 0.0 | 99.8 (91.6) | 100.0 | +49.8 | inside |
| J8s | suited_other | 0.0 | 99.8 (62.0) | 100.0 | +49.8 | inside |
| K4s | suited_Kx | 0.0 | 99.8 (12.1) | 100.0 | +49.8 | inside |
| Q8s | suited_other | 0.0 | 99.9 (28.7) | 100.0 | +49.9 | inside |
| K5s | suited_Kx | 0.0 | 99.9 (25.8) | 100.0 | +49.9 | inside |
| J9s | suited_one_gapper | 0.0 | 99.9 (76.3) | 100.0 | +49.9 | inside |
| A3s | suited_Ax | 0.0 | 100.0 (95.4) | 100.0 | +50.0 | inside |
| QTs | suited_broadway | 0.0 | 100.0 (62.1) | 100.0 | +50.0 | inside |
| Q9s | suited_other | 0.0 | 100.0 (41.2) | 100.0 | +50.0 | inside |
| A5s | suited_Ax | 0.0 | 100.0 (64.9) | 100.0 | +50.0 | inside |
| K8s | suited_Kx | 0.0 | 100.0 (5.1) | 100.0 | +50.0 | inside |
| K7s | suited_Kx | 0.0 | 100.0 (4.3) | 100.0 | +50.0 | inside |
| A2s | suited_Ax | 0.0 | 100.0 (97.7) | 100.0 | +50.0 | inside |
| A4s | suited_Ax | 0.0 | 100.0 (83.7) | 100.0 | +50.0 | inside |
| K6s | suited_Kx | 0.0 | 100.0 (16.1) | 100.0 | +50.0 | inside |
| 55 | pair | 0.0 | 100.0 (82.3) | 100.0 | +50.0 | inside |
| Q4o | offsuit_other | 16.0 | 70.3 (0.6) | 0.0 | +62.3 | above_both |
| K4o | offsuit_other | 50.0 | 97.2 (0.6) | 0.0 | +72.2 | above_both |
| K2o | offsuit_other | 20.0 | 91.3 (0.4) | 0.0 | +81.3 | above_both |
| K3o | offsuit_other | 15.0 | 92.7 (0.4) | 0.0 | +85.2 | above_both |

## 5. Hand sample (12 fixed family probes + 3 reference-boundary hands)

Exact 30bb reference column: **no exact 30bb hand-level reference** for every row.

### UTG

| Hand | family | ref class | solver fold / raise / jam | solver open | J20 open | J40 open | J20 limp | bracket |
|---|---|---|---|---:|---:|---:|---:|---|
| AA | pair | clear_open | 0.0 / 85.5 / 14.4 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| AKo | offsuit_Ax | clear_open | 0.0 / 88.3 / 11.7 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| KQo | offsuit_broadway | clear_open | 39.3 / 59.6 / 1.1 | 60.7 | 100.0 | 100.0 | 0.0 | below_both |
| KTo | offsuit_broadway | clear_fold | 99.5 / 0.3 / 0.3 | 0.5 | 0.0 | 0.0 | 0.0 | inside |
| A5s | suited_Ax | clear_open | 84.2 / 4.2 / 11.7 | 15.8 | 100.0 | 100.0 | 0.0 | below_both |
| A2s | suited_Ax | clear_fold | 99.7 / 0.1 / 0.2 | 0.3 | 0.0 | 0.0 | 0.0 | inside |
| K9s | suited_Kx | clear_open | 70.1 / 29.3 / 0.5 | 29.9 | 100.0 | 100.0 | 0.0 | below_both |
| 98s | suited_connector | boundary | 98.8 / 1.0 / 0.2 | 1.2 | 46.0 | 0.0 | 0.0 | inside |
| 76s | suited_connector | clear_fold | 99.5 / 0.3 / 0.2 | 0.5 | 0.0 | 0.3 | 0.0 | inside |
| 55 | pair | boundary | 44.1 / 55.0 / 0.8 | 55.9 | 17.0 | 11.4 | 0.0 | above_both |
| 22 | pair | clear_fold | 99.7 / 0.1 / 0.2 | 0.3 | 0.0 | 0.0 | 0.0 | inside |
| 72o | offsuit_other | clear_fold | 100.0 / 0.0 / 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | inside |
| K8s | suited_Kx | boundary | 99.1 / 0.7 / 0.3 | 0.9 | 97.0 | 2.3 | 0.0 | inside |
| A3s | suited_Ax | boundary | 99.2 / 0.2 / 0.6 | 0.8 | 13.0 | 100.0 | 0.0 | below_both |
| 65s | suited_connector | boundary | 100.0 / 0.0 / 0.0 | 0.0 | 0.0 | 75.7 | 0.0 | inside |

### HJ

| Hand | family | ref class | solver fold / raise / jam | solver open | J20 open | J40 open | J20 limp | bracket |
|---|---|---|---|---:|---:|---:|---:|---|
| AA | pair | clear_open | 0.0 / 99.4 / 0.6 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| AKo | offsuit_Ax | clear_open | 0.0 / 80.5 / 19.5 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| KQo | offsuit_broadway | clear_open | 0.0 / 99.7 / 0.2 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| KTo | offsuit_broadway | clear_open | 21.8 / 78.0 / 0.2 | 78.2 | 100.0 | 100.0 | 0.0 | below_both |
| A5s | suited_Ax | clear_open | 4.3 / 95.3 / 0.4 | 95.7 | 100.0 | 100.0 | 0.0 | inside |
| A2s | suited_Ax | clear_open | 99.3 / 0.6 / 0.2 | 0.7 | 100.0 | 100.0 | 0.0 | below_both |
| K9s | suited_Kx | clear_open | 1.9 / 97.9 / 0.2 | 98.1 | 100.0 | 100.0 | 0.0 | inside |
| 98s | suited_connector | clear_open | 76.9 / 22.9 / 0.2 | 23.1 | 100.0 | 100.0 | 0.0 | below_both |
| 76s | suited_connector | boundary | 100.0 / 0.0 / 0.0 | 0.0 | 0.0 | 100.0 | 0.0 | inside |
| 55 | pair | clear_open | 0.0 / 99.7 / 0.3 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| 22 | pair | clear_fold | 81.9 / 17.9 / 0.2 | 18.1 | 0.0 | 0.0 | 0.0 | above_both |
| 72o | offsuit_other | clear_fold | 100.0 / 0.0 / 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | inside |
| 54s | suited_connector | boundary | 100.0 / 0.0 / 0.0 | 0.0 | 0.0 | 100.0 | 0.0 | inside |
| 65s | suited_connector | boundary | 100.0 / 0.0 / 0.0 | 0.0 | 0.0 | 100.0 | 0.0 | inside |
| K4s | suited_Kx | boundary | 99.6 / 0.2 / 0.2 | 0.4 | 0.0 | 100.0 | 0.0 | inside |

### CO

| Hand | family | ref class | solver fold / raise / jam | solver open | J20 open | J40 open | J20 limp | bracket |
|---|---|---|---|---:|---:|---:|---:|---|
| AA | pair | clear_open | 0.0 / 99.2 / 0.8 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| AKo | offsuit_Ax | clear_open | 0.0 / 28.3 / 71.7 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| KQo | offsuit_broadway | clear_open | 0.0 / 97.3 / 2.6 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| KTo | offsuit_broadway | clear_open | 6.7 / 92.6 / 0.7 | 93.3 | 100.0 | 100.0 | 0.0 | below_both |
| A5s | suited_Ax | clear_open | 1.8 / 96.4 / 1.9 | 98.2 | 100.0 | 100.0 | 0.0 | inside |
| A2s | suited_Ax | clear_open | 38.7 / 60.8 / 0.6 | 61.3 | 100.0 | 100.0 | 0.0 | below_both |
| K9s | suited_Kx | clear_open | 1.6 / 97.7 / 0.7 | 98.4 | 100.0 | 100.0 | 0.0 | inside |
| 98s | suited_connector | clear_open | 35.3 / 41.2 / 23.5 | 64.7 | 100.0 | 100.0 | 0.0 | below_both |
| 76s | suited_connector | boundary | 100.0 / 0.0 / 0.0 | 0.0 | 56.0 | 100.0 | 0.0 | below_both |
| 55 | pair | clear_open | 0.0 / 98.3 / 1.7 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| 22 | pair | clear_fold | 10.7 / 84.3 / 5.0 | 89.3 | 0.0 | 0.0 | 0.0 | above_both |
| 72o | offsuit_other | clear_fold | 100.0 / 0.0 / 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | inside |
| 33 | pair | boundary | 2.6 / 94.7 / 2.7 | 97.4 | 0.0 | 100.0 | 0.0 | inside |
| 54s | suited_connector | boundary | 100.0 / 0.0 / 0.0 | 0.0 | 0.0 | 100.0 | 0.0 | inside |
| 65s | suited_connector | boundary | 100.0 / 0.0 / 0.0 | 0.0 | 0.0 | 100.0 | 0.0 | inside |

### BTN

| Hand | family | ref class | solver fold / raise / jam | solver open | J20 open | J40 open | J20 limp | bracket |
|---|---|---|---|---:|---:|---:|---:|---|
| AA | pair | clear_open | 0.0 / 98.6 / 1.4 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| AKo | offsuit_Ax | clear_open | 0.0 / 18.9 / 81.1 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| KQo | offsuit_broadway | clear_open | 0.0 / 58.6 / 41.4 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| KTo | offsuit_broadway | clear_open | 0.2 / 97.8 / 2.0 | 99.8 | 100.0 | 100.0 | 0.0 | inside |
| A5s | suited_Ax | clear_open | 0.0 / 67.0 / 33.0 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| A2s | suited_Ax | clear_open | 0.4 / 96.8 / 2.7 | 99.6 | 100.0 | 100.0 | 0.0 | inside |
| K9s | suited_Kx | clear_open | 0.1 / 93.9 / 6.0 | 99.9 | 100.0 | 100.0 | 0.0 | inside |
| 98s | suited_connector | clear_open | 3.4 / 7.4 / 89.2 | 96.6 | 100.0 | 100.0 | 0.0 | inside |
| 76s | suited_connector | clear_open | 56.9 / 2.5 / 40.6 | 43.1 | 100.0 | 100.0 | 0.0 | below_both |
| 55 | pair | clear_open | 0.0 / 33.0 / 67.0 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| 22 | pair | boundary | 0.2 / 3.3 / 96.6 | 99.8 | 100.0 | 55.8 | 0.0 | inside |
| 72o | offsuit_other | clear_fold | 100.0 / 0.0 / 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | inside |
| 98o | offsuit_other | boundary | 99.1 / 0.4 / 0.5 | 0.9 | 0.0 | 100.0 | 0.0 | inside |
| K6o | offsuit_other | boundary | 95.5 / 4.3 / 0.2 | 4.5 | 0.0 | 100.0 | 0.0 | inside |
| 54s | suited_connector | boundary | 100.0 / 0.0 / 0.0 | 0.0 | 0.0 | 100.0 | 0.0 | inside |

### SB

| Hand | family | ref class | solver fold / raise / jam | solver open | J20 open | J40 open | J20 limp | bracket |
|---|---|---|---|---:|---:|---:|---:|---|
| AA | pair | clear_open | 0.0 / 58.3 / 41.7 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| AKo | offsuit_Ax | boundary | 0.0 / 3.0 / 96.9 | 100.0 | 19.0 | 100.0 | 81.0 | inside |
| KQo | offsuit_broadway | boundary | 0.0 / 11.1 / 88.9 | 100.0 | 54.0 | 100.0 | 46.0 | inside |
| KTo | offsuit_broadway | boundary | 0.0 / 79.8 / 20.2 | 100.0 | 67.0 | 100.0 | 33.0 | inside |
| A5s | suited_Ax | boundary | 0.0 / 35.1 / 64.9 | 100.0 | 0.0 | 100.0 | 100.0 | inside |
| A2s | suited_Ax | boundary | 0.0 / 2.3 / 97.7 | 100.0 | 0.0 | 100.0 | 100.0 | inside |
| K9s | suited_Kx | boundary | 0.0 / 80.8 / 19.2 | 100.0 | 33.0 | 100.0 | 67.0 | inside |
| 98s | suited_connector | boundary | 0.2 / 4.4 / 95.4 | 99.8 | 0.0 | 100.0 | 100.0 | inside |
| 76s | suited_connector | boundary | 1.5 / 3.0 / 95.5 | 98.5 | 30.0 | 100.0 | 70.0 | inside |
| 55 | pair | boundary | 0.0 / 17.7 / 82.3 | 100.0 | 0.0 | 100.0 | 100.0 | inside |
| 22 | pair | clear_open | 0.0 / 0.4 / 99.6 | 100.0 | 100.0 | 100.0 | 0.0 | inside |
| 72o | offsuit_other | clear_fold | 100.0 / 0.0 / 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | inside |
| 54s | suited_connector | boundary | 2.7 / 2.5 / 94.8 | 97.3 | 0.0 | 100.0 | 100.0 | inside |
| 65s | suited_connector | boundary | 1.6 / 0.6 / 97.8 | 98.4 | 0.0 | 100.0 | 100.0 | inside |
| 75s | suited_one_gapper | boundary | 4.6 / 2.7 / 92.7 | 95.4 | 0.0 | 100.0 | 100.0 | inside |

## Caveats

- Solver pilot is a 20-iteration run (gap_total 0.309). A later convergence-qualified run (gap 0.095) gave similar aggregate RFI, but its per-hand table was not stored, so hand values here come from the loose run.
- Solver trash hands show a ~0.01% jam floor (averaging residue); treat <1% as zero.
- Jens pack conditions (ante, sizing, ICM) are unknown, so even an "inside" result is only a consistency check.
- 20 and 40 are not bracketing endpoints of a monotone function; some families (e.g. small pairs, offsuit Ax) can legitimately move non-monotonically with stack depth.
