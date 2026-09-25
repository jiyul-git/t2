# Concept prior sensitivity audit design

Status: read-only calibration mechanics audit. No production parameter changes.

## Why this step

The realized-prior audit showed that nominal `base` and `spread` values are not direct
population means because latent loadings, clamping, and the overall-skill rejection filter
reshape them.

Before choosing new targets, measure how much a small local parameter change actually moves
the realized population.

## Locked perturbations

Reference population:

- field quality: 0.78
- generator seed: 20260926
- profiles per arm: 3,000

For each concept in `LOADING`, independently evaluate:

- base -0.25
- base +0.25
- spread -0.15
- spread +0.15

Only that concept's parameter is changed in each arm. The full production generator,
including rejection by `overall_skill`, is otherwise used unchanged.

`money_jump` is reported separately because it has a separate generator and is not part
of `LOADING` / `overall_skill`.

## Output

For every concept, report local realized sensitivity:

- median delta from +/-0.25 base;
- q10/q90 movement;
- floor/ceiling saturation movement;
- median delta from +/-0.15 spread;
- width movement (`q90-q10`);
- whether the response is approximately symmetric.

## Interpretation

This tool does not choose new values.

It answers only:

- how much nominal base must move to shift the realized median;
- how strongly spread changes realized width vs merely increasing clamp saturation;
- which concepts are nonlinear because the rejection filter or 0/10 clamp dominates.

Target medians/bands are chosen only after this mechanics map exists.
