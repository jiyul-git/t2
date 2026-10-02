# 30bb 9-max solver vs reference audit v1

Read-only audit. No solver code or DB value was changed. Machine-readable: `30bb_solver_reference_audit_v1.json`.

Scope limits: (1) there is no exact-comparable 9-max hand-level reference, so the gaps below are differences to near-references, not a measured error against exact GTO, and the ~10 pp RFI gap is not attributed in full to solver defects; (2) jam is judged "probably not the main cause", to be re-checked after the continuation model is corrected; (3) the 4-handed solved-continuation runs show the mechanism only and are not a 9-max correction.

## 1. Comparability
**Verdict:** no exact-comparable reference exists locally; all comparisons below are near-reference and are labelled so.

| | table | stack | ante | open | raise tree | limp | jam | max raises | ICM/rake | granularity | class |
|---|---|---|---|---|---|---|---|---|---|---|---|
| solver pilot | 9 | cfg.stack 30.0 bb after the ante -> hand-start 30.1111 bb | uniform 0.1111 bb x 9 (total 1 bb), paid outside cfg.stack | 2.0 bb (SB 2.5) | 3bet = 3x (blinds 4x), fourbet_mults [2.2] unreachable at max_raises 2 | False | add_allin True, allin_threshold 0.85 | 2 (open + one re-raise; no 4bet) | chip EV, rake 0 | per hand (no EV stored) | solver |
| PreflopRanges public MTT 9-max 30bb chart (manual aggregate, external_rfi_crosscheck_9max.json) | 9 | 30 bb | chart-specific MTT ante, not recorded | 2.0 bb (SB 3.5) | not recorded | unknown (SB RFI 89.4% suggests limps included) | unknown | unknown | chip EV presumed, not recorded | aggregate RFI per position only | near-reference |
| Matthiola 8-max MTT 30bb charts (MIT, commit 9ef33a4) | 8 | 30 bb | MTT ante, unspecified | unspecified | unspecified | call column present (SB limps) | allin column present | 3bet / 4bet nodes exist (EPopen-vs-IP3bet etc.) | unspecified | per hand, 7 RFI nodes + vs-open nodes | near-reference |
| GTOpen 4-handed 30bb (CO/BTN/SB/BB), same engine, P0 static payoff vs A4c solved flop continuation at nodes 6 / 28 | 4 | 30 bb after a 0.25 ante (30.25 hand-start) | 0.25 x 4 | 2.0 (SB 2.5) | 3x / 3.5x, 4bet 2.2x | False | add_allin, 0.85 | 4 | chip EV, rake 0 | per class, converged (400 iterations, gap 3e-4) | internal same-engine comparator (not a reference) |

Solver postflop model: no postflop tree: pot-share terminal payoff, realization 'static' (class-independent), multiway coupled_deck_v1. Convergence: 20 iterations, gap_total 0.309 bb (target 0.5).

## 2. Aggregate RFI
| position | solver pilot | reproduction 20 it | reproduction 100 it | ensemble static 100 it | PreflopRanges 9-max | Matthiola 8-max (mapped) |
|---|---|---|---|---|---|---|
| UTG | 10.6% | 9.6% | — | 10.0% | 16.5% | 18.5% (nearest node) |
| UTG+1 | 12.2% | 10.9% | — | 11.9% | 18.6% | 18.5% |
| UTG+2 | 12.6% | 13.1% | — | 14.3% | 21.7% | 21.3% |
| LJ | 15.5% | 16.1% | — | 16.8% | 25.7% | 24.5% |
| HJ | 20.1% | 18.5% | — | 20.8% | 29.9% | 29.0% |
| CO | 26.1% | 25.1% | — | 26.0% | 37.5% | 36.3% |
| BTN | 35.6% | 35.2% | — | 36.2% | 48.7% | 48.7% |
| SB | 60.4% | — | — | — | 89.4% | 29.4% |

SB is not comparable (references include limps / 3.5bb opens; the solver has no limp and opens 2.5bb).

## 3. RFI shortfall by hand family (vs Matthiola 8-max, combo-weighted, % of 1326)
| position | pocket pair | suited Ax | suited Kx/Qx | suited connectors/gappers | offsuit broadway | offsuit Ax/Kx | other suited | other offsuit | total |
|---|---|---|---|---|---|---|---|---|---|
| UTG | +0.40 | +1.77 | +1.34 | +1.79 | +2.68 | -0.03 | -0.01 | -0.02 | +7.91 |
| UTG+1 | +0.20 | +1.68 | +1.05 | +1.74 | +1.77 | -0.04 | -0.01 | -0.02 | +6.37 |
| UTG+2 | +0.29 | +1.93 | +1.21 | +2.20 | +2.79 | +0.28 | -0.01 | -0.03 | +8.68 |
| LJ | -0.10 | +1.41 | +1.40 | +2.64 | +2.98 | +0.72 | -0.00 | -0.03 | +9.02 |
| HJ | -0.10 | +0.63 | +1.94 | +2.80 | +2.10 | +1.30 | +0.18 | +0.03 | +8.89 |
| CO | -0.47 | +0.17 | +2.40 | +2.71 | +0.89 | +1.52 | +0.58 | +2.45 | +10.25 |
| BTN | -0.53 | +0.00 | +1.97 | +2.57 | +0.13 | +1.75 | +2.45 | +4.72 | +13.07 |

Solver jam share of all combos (reference jam share is 0 in every family at 30bb):
| position | pocket pair | suited Ax | suited Kx/Qx | suited connectors/gappers | offsuit broadway | offsuit Ax/Kx | other suited | other offsuit |
|---|---|---|---|---|---|---|---|---|
| UTG | 0.29 | 0.12 | 0.03 | 0.01 | 0.17 | 0.02 | 0.00 | 0.01 |
| HJ | 0.07 | 0.01 | 0.10 | 0.14 | 0.20 | 0.02 | 0.00 | 0.01 |
| CO | 0.35 | 0.14 | 0.39 | 0.59 | 0.95 | 0.03 | 0.00 | 0.02 |
| BTN | 2.09 | 0.43 | 0.53 | 1.79 | 2.29 | 0.03 | 0.01 | 0.04 |

## 4. Hand level (UTG / HJ / CO / BTN)
Solver = pilot artifact; EV = 20-iteration reproduction of the same config (bb, net, per action in the order shown); ref = Matthiola 8-max mapped node.

### UTG (Matthiola node UTG)
| group | hand | family | fold | raise | jam | modal | EV fold / raise / jam | ref fold / raise / allin / call | open diff |
|---|---|---|---|---|---|---|---|---|---|
| focus | A5s | suited Ax | 0.84 | 0.04 | 0.12 | fold | -0.111 / -0.381 / -0.483 | 0.00 / 1.00 / 0.00 / 0.00 | -0.84 |
| focus | K9s | suited Kx/Qx | 0.70 | 0.29 | 0.01 | fold | -0.111 / -0.309 / -0.943 | 0.00 / 1.00 / 0.00 / 0.00 | -0.70 |
| focus | KQo | offsuit broadway | 0.39 | 0.60 | 0.01 | raise | -0.111 / -0.000 / -0.654 | 0.00 / 1.00 / 0.00 / 0.00 | -0.39 |
| focus | 22 | pocket pair | 1.00 | 0.00 | 0.00 | fold | -0.111 / -0.937 / -1.084 | 1.00 / 0.00 / 0.00 / 0.00 | +0.00 |
| focus | 55 | pocket pair | 0.44 | 0.55 | 0.01 | raise | -0.111 / +0.082 / -0.658 | 0.00 / 1.00 / 0.00 / 0.00 | -0.44 |
| focus | 98s | suited connectors/gappers | 0.99 | 0.01 | 0.00 | fold | -0.111 / -0.442 / -0.948 | 0.00 / 1.00 / 0.00 / 0.00 | -0.99 |
| focus | AKo | offsuit broadway | 0.00 | 0.88 | 0.12 | raise | -0.111 / +1.077 / +0.501 | 0.00 / 1.00 / 0.00 / 0.00 | -0.00 |
| clear_open_by_ref | A4s | suited Ax | 0.99 | 0.00 | 0.00 | fold | -0.111 / -0.715 / -0.672 | 0.00 / 1.00 / 0.00 / 0.00 | -0.99 |
| clear_open_by_ref | A3s | suited Ax | 0.99 | 0.00 | 0.01 | fold | -0.111 / -0.794 / -0.652 | 0.00 / 1.00 / 0.00 / 0.00 | -0.99 |
| clear_open_by_ref | K8s | suited Kx/Qx | 0.99 | 0.01 | 0.00 | fold | -0.111 / -0.491 / -1.032 | 0.00 / 1.00 / 0.00 / 0.00 | -0.99 |
| boundary_by_ref | QJo | offsuit broadway | 0.99 | 0.01 | 0.00 | fold | -0.111 / -0.432 / -1.004 | 0.49 / 0.51 / 0.00 / 0.00 | -0.50 |
| boundary_by_ref | 44 | pocket pair | 0.97 | 0.02 | 0.00 | fold | -0.111 / -0.858 / -0.910 | 0.56 / 0.44 / 0.00 / 0.00 | -0.41 |
| boundary_by_ref | 76s | suited connectors/gappers | 0.99 | 0.00 | 0.00 | fold | -0.111 / -0.693 / -0.887 | 0.42 / 0.58 / 0.00 / 0.00 | -0.57 |
| clear_fold_by_ref | J8s | suited connectors/gappers | 0.99 | 0.01 | 0.00 | fold | -0.111 / -0.429 / -1.029 | 1.00 / 0.00 / 0.00 / 0.00 | +0.01 |
| clear_fold_by_ref | Q8s | suited Kx/Qx | 0.99 | 0.01 | 0.00 | fold | -0.111 / -0.465 / -1.085 | 1.00 / 0.00 / 0.00 / 0.00 | +0.01 |
| clear_fold_by_ref | K3s | suited Kx/Qx | 0.99 | 0.01 | 0.00 | fold | -0.111 / -0.776 / -1.155 | 1.00 / 0.00 / 0.00 / 0.00 | +0.01 |

### HJ (Matthiola node HJ)
| group | hand | family | fold | raise | jam | modal | EV fold / raise / jam | ref fold / raise / allin / call | open diff |
|---|---|---|---|---|---|---|---|---|---|
| focus | A5s | suited Ax | 0.04 | 0.95 | 0.00 | raise | -0.111 / +0.061 / -0.142 | 0.00 / 1.00 / 0.00 / 0.00 | -0.04 |
| focus | K9s | suited Kx/Qx | 0.02 | 0.98 | 0.00 | raise | -0.111 / +0.113 / -0.372 | 0.00 / 1.00 / 0.00 / 0.00 | -0.02 |
| focus | KQo | offsuit broadway | 0.00 | 1.00 | 0.00 | raise | -0.111 / +0.307 / -0.043 | 0.00 / 1.00 / 0.00 / 0.00 | -0.00 |
| focus | 22 | pocket pair | 0.82 | 0.18 | 0.00 | fold | -0.111 / -0.084 / -0.406 | 1.00 / 0.00 / 0.00 / 0.00 | +0.18 |
| focus | 55 | pocket pair | 0.00 | 1.00 | 0.00 | raise | -0.111 / +0.391 / -0.075 | 0.00 / 1.00 / 0.00 / 0.00 | -0.00 |
| focus | 98s | suited connectors/gappers | 0.77 | 0.23 | 0.00 | fold | -0.111 / -0.133 / -0.421 | 0.00 / 1.00 / 0.00 / 0.00 | -0.77 |
| focus | AKo | offsuit broadway | 0.00 | 0.80 | 0.20 | raise | -0.111 / +1.593 / +1.495 | 0.00 / 1.00 / 0.00 / 0.00 | -0.00 |
| clear_open_by_ref | 65s | suited connectors/gappers | 1.00 | 0.00 | 0.00 | fold | -0.111 / -1.251 / -0.601 | 0.00 / 1.00 / 0.00 / 0.00 | -1.00 |
| clear_open_by_ref | 76s | suited connectors/gappers | 1.00 | 0.00 | 0.00 | fold | -0.111 / -1.102 / -0.522 | 0.00 / 1.00 / 0.00 / 0.00 | -1.00 |
| clear_open_by_ref | 97s | suited connectors/gappers | 1.00 | 0.00 | 0.00 | fold | -0.111 / -0.271 / -0.473 | 0.00 / 1.00 / 0.00 / 0.00 | -1.00 |
| boundary_by_ref | K9o | offsuit Ax/Kx | 0.96 | 0.04 | 0.00 | fold | -0.111 / -0.101 / -0.815 | 0.45 / 0.55 / 0.00 / 0.00 | -0.51 |
| boundary_by_ref | 86s | suited connectors/gappers | 1.00 | 0.00 | 0.00 | fold | -0.111 / -1.098 / -0.580 | 0.44 / 0.56 / 0.00 / 0.00 | -0.56 |
| boundary_by_ref | 54s | suited connectors/gappers | 1.00 | 0.00 | 0.00 | fold | -0.111 / -1.289 / -0.498 | 0.57 / 0.43 / 0.00 / 0.00 | -0.43 |
| clear_fold_by_ref | 22 | pocket pair | 0.82 | 0.18 | 0.00 | fold | -0.111 / -0.084 / -0.406 | 1.00 / 0.00 / 0.00 / 0.00 | +0.18 |
| clear_fold_by_ref | K3s | suited Kx/Qx | 0.99 | 0.01 | 0.00 | fold | -0.111 / -0.572 / -0.656 | 1.00 / 0.00 / 0.00 / 0.00 | +0.01 |
| clear_fold_by_ref | A6o | offsuit Ax/Kx | 0.99 | 0.01 | 0.00 | fold | -0.111 / -0.574 / -0.833 | 1.00 / 0.00 / 0.00 / 0.00 | +0.01 |

### CO (Matthiola node CO)
| group | hand | family | fold | raise | jam | modal | EV fold / raise / jam | ref fold / raise / allin / call | open diff |
|---|---|---|---|---|---|---|---|---|---|
| focus | A5s | suited Ax | 0.02 | 0.96 | 0.02 | raise | -0.111 / +0.142 / -0.037 | 0.00 / 1.00 / 0.00 / 0.00 | -0.02 |
| focus | K9s | suited Kx/Qx | 0.02 | 0.98 | 0.01 | raise | -0.111 / +0.120 / -0.079 | 0.00 / 1.00 / 0.00 / 0.00 | -0.02 |
| focus | KQo | offsuit broadway | 0.00 | 0.97 | 0.03 | raise | -0.111 / +0.433 / +0.203 | 0.00 / 1.00 / 0.00 / 0.00 | -0.00 |
| focus | 22 | pocket pair | 0.11 | 0.84 | 0.05 | raise | -0.111 / -0.005 / -0.215 | 1.00 / 0.00 / 0.00 / 0.00 | +0.89 |
| focus | 55 | pocket pair | 0.00 | 0.98 | 0.02 | raise | -0.111 / +0.519 / +0.161 | 0.00 / 1.00 / 0.00 / 0.00 | -0.00 |
| focus | 98s | suited connectors/gappers | 0.35 | 0.41 | 0.23 | raise | -0.111 / -0.112 / -0.130 | 0.00 / 1.00 / 0.00 / 0.00 | -0.35 |
| focus | AKo | offsuit broadway | 0.00 | 0.28 | 0.72 | jam | -0.111 / +2.000 / +2.087 | 0.00 / 1.00 / 0.00 / 0.00 | -0.00 |
| clear_open_by_ref | 54s | suited connectors/gappers | 1.00 | 0.00 | 0.00 | fold | -0.111 / -1.208 / -0.487 | 0.00 / 1.00 / 0.00 / 0.00 | -1.00 |
| clear_open_by_ref | 65s | suited connectors/gappers | 1.00 | 0.00 | 0.00 | fold | -0.111 / -1.177 / -0.557 | 0.00 / 1.00 / 0.00 / 0.00 | -1.00 |
| clear_open_by_ref | 76s | suited connectors/gappers | 1.00 | 0.00 | 0.00 | fold | -0.111 / -1.035 / -0.424 | 0.00 / 1.00 / 0.00 / 0.00 | -1.00 |
| boundary_by_ref | 75s | suited connectors/gappers | 1.00 | 0.00 | 0.00 | fold | -0.111 / -1.196 / -0.631 | 0.49 / 0.51 / 0.00 / 0.00 | -0.51 |
| boundary_by_ref | K2s | suited Kx/Qx | 0.99 | 0.01 | 0.00 | fold | -0.111 / -0.508 / -0.572 | 0.46 / 0.54 / 0.00 / 0.00 | -0.53 |
| clear_fold_by_ref | 22 | pocket pair | 0.11 | 0.84 | 0.05 | raise | -0.111 / -0.005 / -0.215 | 1.00 / 0.00 / 0.00 / 0.00 | +0.89 |
| clear_fold_by_ref | A4o | offsuit Ax/Kx | 0.89 | 0.11 | 0.00 | fold | -0.111 / -0.134 / -0.587 | 1.00 / 0.00 / 0.00 / 0.00 | +0.11 |
| clear_fold_by_ref | K8o | offsuit Ax/Kx | 0.90 | 0.10 | 0.00 | fold | -0.111 / -0.336 / -0.712 | 1.00 / 0.00 / 0.00 / 0.00 | +0.10 |

### BTN (Matthiola node BTN)
| group | hand | family | fold | raise | jam | modal | EV fold / raise / jam | ref fold / raise / allin / call | open diff |
|---|---|---|---|---|---|---|---|---|---|
| focus | A5s | suited Ax | 0.00 | 0.67 | 0.33 | raise | -0.111 / +0.358 / +0.207 | 0.00 / 1.00 / 0.00 / 0.00 | -0.00 |
| focus | K9s | suited Kx/Qx | 0.00 | 0.94 | 0.06 | raise | -0.111 / +0.273 / +0.119 | 0.00 / 1.00 / 0.00 / 0.00 | -0.00 |
| focus | KQo | offsuit broadway | 0.00 | 0.59 | 0.41 | raise | -0.111 / +0.684 / +0.582 | 0.00 / 1.00 / 0.00 / 0.00 | -0.00 |
| focus | 22 | pocket pair | 0.00 | 0.03 | 0.97 | jam | -0.111 / +0.073 / +0.209 | 1.00 / 0.00 / 0.00 / 0.00 | +1.00 |
| focus | 55 | pocket pair | 0.00 | 0.33 | 0.67 | jam | -0.111 / +0.874 / +0.856 | 0.00 / 1.00 / 0.00 / 0.00 | -0.00 |
| focus | 98s | suited connectors/gappers | 0.03 | 0.07 | 0.89 | jam | -0.111 / -0.051 / +0.146 | 0.00 / 1.00 / 0.00 / 0.00 | -0.03 |
| focus | AKo | offsuit broadway | 0.00 | 0.19 | 0.81 | jam | -0.111 / +2.534 / +2.808 | 0.00 / 1.00 / 0.00 / 0.00 | -0.00 |
| clear_open_by_ref | 54s | suited connectors/gappers | 1.00 | 0.00 | 0.00 | fold | -0.111 / -1.141 / -0.335 | 0.00 / 1.00 / 0.00 / 0.00 | -1.00 |
| clear_open_by_ref | 64s | suited connectors/gappers | 1.00 | 0.00 | 0.00 | fold | -0.111 / -1.241 / -0.486 | 0.00 / 1.00 / 0.00 / 0.00 | -1.00 |
| clear_open_by_ref | 75s | suited connectors/gappers | 1.00 | 0.00 | 0.00 | fold | -0.111 / -1.075 / -0.358 | 0.00 / 1.00 / 0.00 / 0.00 | -1.00 |
| boundary_by_ref | K6o | offsuit Ax/Kx | 0.96 | 0.04 | 0.00 | fold | -0.111 / -0.286 / -0.610 | 0.40 / 0.60 / 0.00 / 0.00 | -0.56 |
| boundary_by_ref | 95s | other suited | 1.00 | 0.00 | 0.00 | fold | -0.111 / -1.049 / -0.440 | 0.34 / 0.66 / 0.00 / 0.00 | -0.66 |
| boundary_by_ref | 98o | other offsuit | 0.99 | 0.00 | 0.00 | fold | -0.111 / -0.346 / -0.361 | 0.28 / 0.72 / 0.00 / 0.00 | -0.71 |
| clear_fold_by_ref | 22 | pocket pair | 0.00 | 0.03 | 0.97 | jam | -0.111 / +0.073 / +0.209 | 1.00 / 0.00 / 0.00 / 0.00 | +1.00 |
| clear_fold_by_ref | K5o | offsuit Ax/Kx | 0.99 | 0.01 | 0.00 | fold | -0.111 / -0.416 / -0.777 | 1.00 / 0.00 / 0.00 / 0.00 | +0.01 |
| clear_fold_by_ref | K4o | offsuit Ax/Kx | 0.99 | 0.01 | 0.00 | fold | -0.111 / -0.480 / -0.832 | 1.00 / 0.00 / 0.00 / 0.00 | +0.01 |

## 5. BB defence (the link to RFI)
- solver BB vs CO open: fold 1.1% of all combos; trash continue rates [['32o', 0.945], ['42o', 0.951], ['72o', 0.952], ['82o', 0.965], ['92o', 0.972], ['J3o', 0.984], ['T2o', 0.983]]
- solver BB vs BTN open: fold 0.8% of all combos; trash continue rates [['32o', 0.962], ['42o', 0.965], ['72o', 0.95], ['82o', 0.975], ['92o', 0.979], ['J3o', 0.989], ['T2o', 0.985]]
- solver BB vs SB open: fold 2.4% of all combos; trash continue rates [['32o', 0.814], ['42o', 0.846], ['72o', 0.754], ['82o', 0.876], ['92o', 0.931], ['J3o', 0.98], ['T2o', 0.96]]
- Matthiola 8-max BB vs BTN: fold 10.4%; same trash [['32o', 0.0], ['42o', 0.85], ['72o', 0.0], ['82o', 0.0], ['92o', 0.0], ['J3o', 1.0], ['T2o', 0.0]]

## 5b. Facing an open: solver 9-max vs Matthiola 8-max (combo share jam / 3-bet / call / fold)
| ref node | solver spot | ref allin / raise / call / fold | solver jam / 3-bet / call / fold |
|---|---|---|---|
| EP-vs-MP | UTG->UTG+2 | 0.0 / 8.0 / 9.0 / 83.1 | 4.2 / 7.0 / 3.9 / 85.0 |
| EP-vs-MP | UTG->LJ | 0.0 / 8.0 / 9.0 / 83.1 | 1.9 / 6.3 / 2.9 / 88.9 |
| EP-vs-BTN | UTG->BTN | 0.0 / 7.7 / 14.3 / 78.0 | 3.0 / 6.6 / 4.5 / 85.9 |
| EP-vs-BTN | UTG+1->BTN | 0.0 / 7.7 / 14.3 / 78.0 | 3.4 / 6.2 / 5.8 / 84.6 |
| EP-vs-SB | UTG->SB | 3.6 / 7.2 / 13.7 / 75.6 | 6.1 / 4.8 / 31.7 / 57.3 |
| EP-vs-SB | UTG+1->SB | 3.6 / 7.2 / 13.7 / 75.6 | 5.2 / 4.7 / 33.2 / 57.0 |
| EP-vs-BB | UTG->BB | 0.7 / 8.7 / 66.3 / 24.3 | 5.8 / 3.1 / 81.0 / 10.1 |
| EP-vs-BB | UTG+1->BB | 0.7 / 8.7 / 66.3 / 24.3 | 3.8 / 3.1 / 90.8 / 2.3 |
| MP-vs-BTN | LJ->BTN | 1.3 / 9.6 / 14.1 / 75.0 | 4.0 / 8.7 / 4.3 / 83.0 |
| MP-vs-BTN | HJ->BTN | 1.3 / 9.6 / 14.1 / 75.0 | 4.6 / 10.8 / 2.0 / 82.6 |
| MP-vs-SB | LJ->SB | 7.3 / 8.0 / 12.7 / 71.9 | 4.5 / 4.6 / 37.6 / 53.3 |
| MP-vs-SB | HJ->SB | 7.3 / 8.0 / 12.7 / 71.9 | 5.7 / 6.6 / 37.1 / 50.6 |
| MP-vs-BB | LJ->BB | 4.9 / 8.8 / 69.7 / 16.6 | 5.3 / 2.5 / 89.6 / 2.6 |
| MP-vs-BB | HJ->BB | 4.9 / 8.8 / 69.7 / 16.6 | 5.4 / 5.1 / 88.5 / 1.0 |
| BTN-vs-SB | BTN->SB | 11.8 / 9.9 / 7.2 / 71.1 | 8.9 / 16.1 / 20.4 / 54.5 |
| BTN-vs-BB | BTN->BB | 8.6 / 9.3 / 71.6 / 10.4 | 8.1 / 11.0 / 80.2 / 0.8 |
| SB-vs-BB | SB->BB | 4.0 / 7.8 / 62.6 / 25.6 | 14.9 / 22.6 / 60.1 / 2.4 |

## 6. Small same-engine A/B (4-handed 30bb, 400 iterations, one factor per arm)
| arm | CO RFI | BTN RFI | BTN jam | SB RFI | BB vs BTN fold | BB vs SB fold |
|---|---|---|---|---|---|---|
| base_static_mr4 | 27.3% | 37.6% | 7.4% | 63.4% | 0.0% | 0.0% |
| raw_realization | 26.0% | 36.0% | 8.3% | 68.4% | 0.0% | 0.0% |
| max_raises_2 | 27.0% | 37.4% | 5.9% | 60.5% | 0.0% | 0.0% |
| no_jam_option | 32.9% | 44.7% | 0.0% | 72.2% | 0.0% | 0.0% |
| mr2_no_jam | 31.7% | 41.5% | 0.0% | 66.2% | 0.0% | 0.0% |
| A4c_solved_continuation_nodes_6_28 | 27.3% | 41.4% | — | — | 6.5% | 3.6% |

## 7. Convergence
- 20 iterations: gap_total 0.303 bb; share of combos whose most-frequent action is not the best-EV action / mean class regret (bb): UTG 2.7% / 0.0109, HJ 5.6% / 0.0078, CO 3.9% / 0.0074, BTN 7.7% / 0.0087, BB 6.9% / 0.0160


## 8. Attribution (where the evidence points)
| candidate | evidence | leaning |
|---|---|---|
| realization model (static: pot x equity x r, r = 1 +- 0.08 by seat order, identical for every hand class) | BB vs BTN: 72o call EV -0.617 vs fold -1.111 bb (raw equity realized in full OOP); solver BB folds 0.8% vs Matthiola 10.4%; removing only the positional skew (raw) moves CO / BTN RFI by -1.3 / -1.6 pp (skew is not the driver; the class-independence is); shortfall concentrates in playability families (suited Kx/Qx, suited connectors) whose value a raw-equity payoff cannot express | **solver/model mismatch (strong)** |
| preflop terminal value (pot-share payoff at every flop-reaching terminal) | 4-handed same engine: replacing the payoff at only the two HU terminals 6 / 28 with solved flop values raises BTN RFI 37.6% -> 41.4% and BB vs BTN fold 0% -> 6.5%; CO RFI unchanged (27.3%) because CO's terminals stayed static | **solver/model mismatch (strong internal evidence; the 4-handed numbers are mechanism evidence, not a 9-max correction or calibration target)** |
| opponent defence saturation (BB continues ~99%) | present in the current 30bb 9-max artifact: BB vs CO fold 1.1%, vs BTN 0.8%; 72o/82o/92o continue >= 95% (Matthiola folds them 100%); when BB starts folding (solved continuation) the BTN opens more; this is the channel through which the payoff model makes openers tight -> the old 'BB never folds' finding and today's low RFI are the same problem | **solver/model mismatch (strong, mechanism)** |
| multiway continuation / payoff approximation (coupled_deck_v1 raw equity) | not isolated by an A/B here; it shares the class-independent raw-equity payoff, so speculative hands get no multiway playability premium; no near-reference covers multiway pots | **both/uncertain (leaning solver)** |
| action abstraction / sizing | non-SB opens are 2.0 bb in solver and both references; the SB tree differs (2.5 bb, no limp vs 3.5 bb / limps) so SB is excluded; 3-bet sizes of the references are not recorded | **uncertain (minor for UTG-BTN; decisive only for SB comparability)** |
| max_raises (pilot uses 2: open + one re-raise, no 4-bet) | 4-handed A/B max_raises 4 -> 2: CO / BTN RFI -0.3 / -0.2 pp; 9-max has more players behind, so the 9-max effect may be somewhat larger but is not of the 10 pp order | **solver abstraction, small contributor** |
| all-in threshold / jam availability | 4-handed A/B without any jam option: CO / BTN RFI 32.9% / 44.7% (base 27.3% / 37.6%) -> the reshove structure is a large lever on RFI; but the solver's 3-bet-jam frequencies are close to the near-reference (BB vs BTN jam 8.1% vs Matthiola 8.6%; SB vs BTN 8.9% vs 11.8%), early-position cold jams are somewhat higher (2-6% vs 0-4%); removing jams is not T2 play. Open-jams by the opener (BTN 22 / 98s / 55) are a symptom of the 2 bb raise getting no folds | **probably not the main cause (reshove rates near reference in the main spots), but a large structural lever: re-check jam frequencies after the continuation model is corrected; opener jam overuse looks like a symptom of the payoff model** |
| over-calling by SB / BB / BTN (passive continuation value) | vs-open table: SB flats 32-37% of combos vs EP/MP opens (Matthiola 13-14%); BB folds 1-3% vs MP opens (Matthiola 17%) and 10% / 2% vs UTG / UTG+1 (Matthiola EP 24%); BTN cold-calls only 2-6% (Matthiola 14%) but 3-bets more; flat calls are valued by raw-equity realization, so blinds over-call and pots go multiway against the opener | **solver/model mismatch (strong; this is how the payoff model reaches the opener)** |
| convergence (pilot: 20 iterations, gap_total 0.31 bb) | 20 it: modal action != best-EV action for 2.7% (UTG) - 7.7% of combos (e.g. UTG KQo raise EV beats fold by 0.11 bb but folds 66%); ensemble static 100 it gives the same aggregate RFI -> convergence adds hand-level noise but does not explain the aggregate gap | **solver issue at hand level; not the aggregate cause** |
| reference side (conditions / provenance) | two independent near-references agree on aggregate RFI (UTG+1 18.6 vs 18.5, CO 37.5 vs 36.3, BTN 48.7 vs 48.7); neither records the ante model or raise tree; Matthiola is 8-max; no exact-comparable reference exists locally; a larger chart ante (e.g. 12.5% = 1.125 bb) would widen the reference somewhat | **reference mismatch possible for part of the gap; not the main cause** |

## 9. Termux / GTOpen stack semantics
- **GTOpen semantics:** cfg.stack is the stack AFTER the ante (behind = stack - invested + ante); hand-start stack S needs cfg.stack = S - ante
- **30bb (44 spots in the Termux branch):** imported from the 9-max pilot: cfg.stack 30, ante 1/9 -> actual hand-start stack 30.1111 bb (each seat paid 1/9 from outside the 30); state metadata says prehand_bb 30 and target "T2 1BB BBA"; realization static, 20 iterations, gap_total 0.309 bb
- **25bb (added in 9730a5f, removed in 355f033):** worker cfg_for(25): cfg.stack 25, ante 1/9, realization balanced, 40 iterations, gap_total 0.085 -> hand-start 25.1111 bb; no longer on the branch
- **20 / 40bb:** not present on origin/chatgpt/gto-db-worker-v1-20261003 (head 355f033); if produced by cfg_for they are 20.1111 / 40.1111 bb hand-start
- **ante model actually solved:** uniform 1/9 bb per seat (9 x 1/9 = 1 bb) = the new T2 uniform_total rule in structure, but at a stack 1/9 bb deeper than labelled; it is NOT the 1 bb big-blind ante the metadata names
- **migration proposal:** do not delete or overwrite; import with canonical_state = what was solved (hand_start_players 9, stacks 30.1111, ante uniform_total 1 bb) as its own sk1 spot, tier 3, with a provenance note and a link to the nominal 30 bb target spot; the 30 bb sk1 spot stays empty until an exact solve exists (lookup may offer the 30.1111 solution only as a declared near match)
- **re-solve needed?:** yes eventually for exact 20/25/30/40 bb (cfg.stack = S - 1/9), but only after the payoff-model issue is addressed; re-solving with the current static model would reproduce the same bias at a 0.11 bb different stack, which matters far less than the model

## 10. Fix proposals (not applied)
- Do not promote the 30bb pilot or the Termux spots beyond tier 3 / unassessed; record the stack-semantics correction in their provenance before migration.
- Primary fix to evaluate: replace the class-independent pot-share payoff at the dominant flop-reaching terminals (BB vs CO / BTN / SB SRPs) with solved continuation values (A4c-style panels) or a class-dependent realization fit; A4c already shows the direction (BTN +3.8 pp, BB starts folding).
- Check the calibrated ("balanced") realization before relying on it: the existing ensemble balanced arm was tighter, not looser (MAE 10.3% vs 8.9%), and its fit file (cache/realization_fit.json) is not present in this checkout.
- Convergence gate for any stored frequency: >= 100 iterations and a per-seat gap target well below the marginal EV gaps (e.g. gap_total <= 0.02 bb), plus the hand_records_v1 status fields.
- Use max_raises >= 3 for stored 9-max trees (small effect, but the no-4bet tree is not T2 play).
- Acquire one exact-comparable reference (known 9-max, 30 bb, ante model, open / 3-bet sizes, raise depth) before any re-calibration; until then all reference comparisons stay near-reference.
- Only after the payoff model is fixed: exact 20/25/30/40 bb re-solves with cfg.stack = S - 1/9 and hand_start_players in the key.
