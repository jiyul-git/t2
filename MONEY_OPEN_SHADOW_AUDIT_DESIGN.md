# Money-open shadow audit design

Status: audit only. No production behavior changes.

## Background

The concept-wiring audit found `money_jump` is partially wired:

- unopened range factor: live;
- open-size factor: shadow-only;
- limp-form pull: shadow-only.

The existing architecture already defines these shadow signals and logs same-state
counterfactual information. This audit measures those two remaining channels separately.
It does not promote either channel.

## Locked population

Fresh confirmatory sample, not previously inspected for these shadow channels:

- seeds 6400-6415
- 24 entries
- standard format
- 12 hands per blind level
- normal field simulator
- engine errors must be zero

Only preflop decisions with:

```
decision_kind == 'unopened'
unopened_modifiers is not None
```

enter the analysis.

## Open-size shadow

Use the **actual legal applied raise target** already recorded by
`session._money_jump_attach_action`:

- `applied_open_size_bb`
- `applied_money_size_bb_shadow`

Do not evaluate the raw pre-shape `open_size_bb` output.

Report:

- number of unopened raises with a legal-size shadow;
- count and rate whose shadow size differs;
- base and shadow size distributions by tournament stage;
- reduction `base - shadow` distribution;
- count pulled exactly to the legal 2BB floor;
- split by position;
- corresponding restraint / size-awareness distributions.

No numeric promotion cutoff is selected from this sample.

## Limp-form shadow

Use the existing same-RNG-roll counterfactual recorded by `preflop.open_decision`:

- `base_limp_p`
- `money_limp_p_shadow`
- `limp_roll`
- `limp_cf`

The key event is `limp_cf == 'add_limp'`, not merely a probability increase.

Report:

- eligible unopened decisions;
- add-limp / base-limp / unchanged-raise counts by stage;
- add-limp events by position;
- SB events separately, because the current action path blocks SB open-limps;
- pressure, restraint, late-fraction and form-awareness distributions for add-limp rows.

No SB behavior change is made by this audit.

## Interpretation

The two channels are independent decisions.

Possible outcomes:

- size shadow has little/no material movement -> keep shadow;
- size shadow creates broad coherent small reductions without pathological 2BB pile-up ->
  eligible for a separate production experiment;
- limp shadow has zero/very rare same-roll additions -> keep shadow;
- limp shadow appears only in coherent late-position survival contexts -> eligible for a
  separate production experiment;
- SB dominates add-limp candidates -> resolve SB open-limp semantics before any promotion.

Do not tune formulas from seeds 6400-6415. If a production experiment is justified,
lock it first and use fresh seeds.
