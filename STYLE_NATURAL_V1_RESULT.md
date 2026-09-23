# STYLE_NATURAL_V1_RESULT

Run: GitHub Actions 35799904836
Seeds: 810001..810012
Fixture: 12 seeds × 40 field rounds, 100 entries, standard
Production behavior: unchanged; measurement branch only.

## Health

- 12/12 jobs success
- engine errors: 0

## Posterior stability

Weighted across observer-target pairs:

| round | pairs | mean certainty | mean entropy |
|---:|---:|---:|---:|
| 10 | 9,264 | 0.0352 | 1.5778 |
| 20 | 9,824 | 0.1297 | 1.3845 |
| 30 | 10,660 | 0.1993 | 1.3058 |
| 40 | 11,664 | 0.2228 | 1.2855 |

Top1 flip rate falls with more evidence:

| window | comparable pairs | flips | rate |
|---|---:|---:|---:|
| 10→20 | 9,264 | 4,273 | 46.12% |
| 20→30 | 9,824 | 3,118 | 31.74% |
| 30→40 | 10,660 | 2,725 | 25.56% |

Mean certainty increases each window and mean entropy decreases each window.

At round 40 top1 distribution:
- TAG 3,932
- TIGHT_PASSIVE 3,605
- NIT 1,977
- LOOSE_PASSIVE 1,567
- LAG 583
- MANIAC 0

The absence of MANIAC top1 in the observed/shrunk posterior is a calibration warning, not yet a bug verdict.
Raw future-window behavior did produce MANIAC 24/7,464 pairs.

## 20-round belief -> rounds 21–40 behavior

Pooled n = 7,464 pairs.

Scaled L/A/X RMSE:
- style posterior centroid: **1.22523**
- population baseline (5,5,1): **1.33136**
- direct current L/A/X: **1.33891**

Ratios:
- style / population = **0.92029** → ~7.97% lower RMSE
- style / direct = **0.91510** → ~8.49% lower RMSE

Preregistered gates from STYLE_MODEL_V1.md:
- `style <= 0.90 × population`: **FAIL pooled**
- `style <= 1.10 × direct`: **PASS pooled**

Per-seed:
- population 0.90 gate: 1/12 PASS
- direct 1.10 gate: 12/12 PASS

## Interpretation boundary

This first natural-state pass is encouraging but **not enough for LIVE promotion**.

Positive:
- certainty rises as evidence accumulates;
- entropy falls;
- top1 flip rate falls;
- style compression predicts future L/A/X better than both the direct current snapshot and the simple neutral population baseline.

Open:
1. The strict 10% improvement over population missed: 7.97% instead of 10%.
2. The current population baseline is the neutral coordinate `(5,5,1)`, not an independently calibrated empirical population mean.
3. MANIAC never becomes posterior top1 in this fixture despite rare MANIAC-like future windows.
4. This is one holdout family, not the two independent holdouts required by the preregistration.

Next step: calibrate the population baseline and style centers on a separate calibration seed set, then run two untouched holdout sets. Do not wire style -> concepts/exploit before that.
