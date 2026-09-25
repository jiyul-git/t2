# Concept prior / population calibration audit design

Status: read-only audit. No production behavior changes.

## Why this is next

The wiring audit is closed:

- 37 declared strategic concepts;
- zero dead core-runtime concepts;
- blockbet/donk semantic debt fixed;
- money-jump size/limp shadows measured and intentionally left inactive.

The remaining declared debt in `persona.py` is population calibration:
`LOADING`, `SPREAD`, and the separate `money_jump` prior are explicitly provisional.

Do not tune them from intuition alone. First measure the **realized** population produced
by the full generator, including latent-factor distributions, clamping, and the
`overall_skill` rejection bounds.

## Questions

For each concept, at several field-quality levels:

1. what are the realized median / q10 / q90?
2. how often does it saturate at 0 or 10?
3. how wide is the realized population?
4. how much does stronger field quality move the concept?
5. does the realized ordering match the intended difficulty ordering?
6. do study/experience/aggression loadings show up in the realized correlations?
7. does `money_jump`, which is generated separately and excluded from
   `overall_skill`, sit on a comparable scale?

## Locked measurement grid

No poker behavior simulation is required. Sample deterministic generated profiles only.

Field quality:

```
0.40, 0.60, 0.78, 1.00, 1.20
```

Profiles per field-quality point:

```
3000
```

Fixed generator seed:

```
20260926
```

No loading/spread value is changed on this branch.

## Output

For every concept:

- nominal `base` and `spread` where applicable;
- q=0.78 realized q10 / median / q90;
- 0-floor / 10-ceiling rate;
- median at q=0.40 and q=1.20;
- high-minus-low median shift;
- Pearson correlation with final latent study / aggro / exp;
- correlation with realized overall skill.

Also report:

- overall-skill distribution by field quality;
- count of concepts with >5% floor or ceiling saturation;
- realized q=0.78 difficulty ordering;
- nominal-base ordering next to realized ordering;
- largest nominal-vs-realized rank inversions.

## Interpretation

This first audit is internal consistency only. It does **not** decide what real poker
population should look like.

A later calibration proposal may use:

- semantic difficulty ordering;
- observed poker population data where defensible;
- action-level balance measurements.

Do not alter priors until the current generator distortion is understood.  In particular,
a low nominal base can be offset by high study/experience loadings, and the rejection
filter can compress or reorder the realized population.
