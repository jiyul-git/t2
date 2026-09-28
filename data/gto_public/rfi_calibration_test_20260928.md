# RFI calibration audit — current test vs public 8-max MTT frequencies

No production constants changed. Source chart files identify the set as **8-max MTT ante**, but do not encode the exact ante amount; the primary T2 comparison therefore uses `ante=True` and retains `ante=False` only as sensitivity.

## Global
- charts: 112
- hand_node_rows: 18928
- source_label: 8-max MTT ante (exact ante amount not encoded in source chart files)
- primary_comparison: T2 ante=True
- t2_ante_true_brier_mean: 0.091872
- t2_ante_true_mae_mean: 0.105629
- t2_ante_true_abs_rate_error_mean: 0.052505
- t2_ante_false_brier_mean: 0.100778
- t2_ante_false_abs_rate_error_mean: 0.069878
- best_hard_cutoff_brier_mean: 0.054236
- best_hard_cutoff_abs_rate_error_mean: 0.031661
- best_monotone_current_rank_brier_mean: 0.032417
- threshold_gap: 0.037636
- hard_cutoff_gap: 0.021820
- non_sb_current_brier_mean: 0.062022
- non_sb_candidate_reversefit_brier_mean: 0.053704
- non_sb_best_hard_cutoff_brier_mean: 0.043467
- non_sb_best_monotone_brier_mean: 0.028430
- non_sb_current_abs_rate_error_mean: 0.035147
- non_sb_candidate_abs_rate_error_mean: 0.006441

## Position summary

| pos | target RFI | T2 RFI | bias | T2 Brier | best cutoff | best monotone |
|---|---:|---:|---:|---:|---:|---:|
| BTN | 0.4634 | 0.4523 | -0.0111 | 0.0741 | 0.0445 | 0.0293 |
| CO | 0.3509 | 0.3211 | -0.0298 | 0.0649 | 0.0489 | 0.0326 |
| HJ | 0.2839 | 0.2526 | -0.0312 | 0.0617 | 0.0478 | 0.0318 |
| LJ | 0.2455 | 0.2107 | -0.0348 | 0.0627 | 0.0399 | 0.0274 |
| SB | 0.3707 | 0.3088 | -0.0619 | 0.2710 | 0.1189 | 0.0563 |
| UTG | 0.1861 | 0.1587 | -0.0275 | 0.0513 | 0.0374 | 0.0230 |
| UTG1 | 0.2108 | 0.1757 | -0.0351 | 0.0574 | 0.0423 | 0.0266 |

## Stack summary

| bb | target RFI | T2 RFI | bias | Brier |
|---:|---:|---:|---:|---:|
| 3 | 0.4594 | 0.3286 | -0.1308 | 0.1480 |
| 5 | 0.4018 | 0.3286 | -0.0732 | 0.1305 |
| 8 | 0.3321 | 0.2769 | -0.0553 | 0.1236 |
| 10 | 0.2952 | 0.2441 | -0.0511 | 0.1047 |
| 12 | 0.2738 | 0.2454 | -0.0283 | 0.0943 |
| 15 | 0.2568 | 0.2476 | -0.0093 | 0.0864 |
| 17 | 0.2594 | 0.2547 | -0.0047 | 0.0779 |
| 20 | 0.2689 | 0.2631 | -0.0058 | 0.0842 |
| 22 | 0.2761 | 0.2633 | -0.0128 | 0.0833 |
| 26 | 0.2880 | 0.2614 | -0.0266 | 0.0825 |
| 30 | 0.2968 | 0.2609 | -0.0359 | 0.0718 |
| 35 | 0.2992 | 0.2782 | -0.0210 | 0.0706 |
| 40 | 0.2932 | 0.2956 | +0.0024 | 0.0622 |
| 50 | 0.2855 | 0.2657 | -0.0198 | 0.0734 |
| 70 | 0.2724 | 0.2489 | -0.0236 | 0.0825 |
| 100 | 0.2673 | 0.2340 | -0.0333 | 0.0940 |

## Largest current-T2 hand errors
- A4s: weighted MSE 0.4169, pct 0.2127
- A3s: weighted MSE 0.3884, pct 0.2187
- 33: weighted MSE 0.3711, pct 0.1267
- 65s: weighted MSE 0.3704, pct 0.4570
- A2s: weighted MSE 0.3584, pct 0.2489
- ATo: weighted MSE 0.3464, pct 0.2066
- 98s: weighted MSE 0.3358, pct 0.2247
- 76s: weighted MSE 0.3275, pct 0.3876
- 22: weighted MSE 0.3245, pct 0.1885
- A7o: weighted MSE 0.3133, pct 0.3333
- A6o: weighted MSE 0.2911, pct 0.3454
- T8s: weighted MSE 0.2889, pct 0.1599
- 87s: weighted MSE 0.2676, pct 0.2700
- J8s: weighted MSE 0.2637, pct 0.2790
- 54s: weighted MSE 0.2598, pct 0.5415
- A6s: weighted MSE 0.2595, pct 0.1750
- Q8s: weighted MSE 0.2567, pct 0.2097
- A8o: weighted MSE 0.2559, pct 0.2911
- 97s: weighted MSE 0.2536, pct 0.2278
- Q7s: weighted MSE 0.2428, pct 0.2821
- K7s: weighted MSE 0.2406, pct 0.1538
- A3o: weighted MSE 0.2402, pct 0.4540
- K2s: weighted MSE 0.2331, pct 0.2941
- A9o: weighted MSE 0.2314, pct 0.2368
- A4o: weighted MSE 0.2283, pct 0.3846

Interpretation: first recalibrate aggregate RFI/depth thresholds; then quantify whether a soft mixed boundary materially improves fit; only after that consider changing pf_rank ordering.
