# Concept / wiring full audit — design

Status: audit only.  No production behavior changes on this branch.

## Goal

Before global balance validation, inventory the engine's strategic concepts and separate:

1. **declared concept** — exists in `persona.EXEC/CALC/PERCEPTION`;
2. **decision-wired concept** — actually consumed by production decision code;
3. **partial/shadow concept** — signal exists but some intended consumers are still shadow-only;
4. **semantic debt** — behavior exists in code but its concept/meaning is unresolved;
5. **parameter debt** — wiring exists but concept generation priors are still provisional.

Do not delete behavior merely because its concept is incomplete.  First document it and
decide whether it belongs to an existing concept, a new concept, or a non-skill engine
mechanic.

## Known issues before automated inventory

### money_jump is no longer perception-only

`persona.py` still says `money_jump` is not connected to behavior.  That comment is
stale: money-jump state already changes unopened preflop range through
`money_open['range_factor']`.

However two related channels remain explicitly shadow-only:

- open-size adjustment (`size_factor_shadow`);
- limp-form adjustment (`limp_pull_shadow`).

Therefore `money_jump` is currently **partially wired**, not purely observational.

### blockbet / donk semantic debt

`plan.py` contains two `TODO/F` markers stating that blockbet/donk semantics are
unresolved when there is no aggressor.  This is not a missing numeric coefficient; it is
a concept-boundary problem and must be resolved before treating `blockbet` coverage as
complete.

### concept priors are provisional

`persona.LOADING` / spread values are explicitly marked provisional.  Wiring correctness
and population calibration are separate tasks.  This audit first answers "is the concept
actually used, and where?" before changing any generation priors.

## Automated inventory

`tools/concept_wiring_audit.py` performs a read-only AST scan of production Python files.

For every declared concept it reports:

- production consumer count;
- unique files/functions;
- `PS.sk/has/gate/calc_noise`-style reads;
- local `sk('concept')` reads;
- street-family mappings such as cbet/barrel/checkraise/bluffcatch/thin_value;
- direct top-level profile reads that may bypass the normal concept accessor;
- zero-consumer and single-consumer concepts;
- TODO/FIXME/shadow markers near strategic code.

The tool excludes `tools/`, caches and generated/vendor directories from consumer counts.

Static references are an inventory, not proof that a branch is reachable or behaviorally
material.  Any suspicious concept found here must be followed by a reachability /
counterfactual test before code is changed.

## Order after the scan

1. zero/single-consumer concepts;
2. partial/shadow wiring;
3. semantic TODOs;
4. direct accessor bypasses;
5. only then concept-prior calibration;
6. global balance validation comes after these are closed or explicitly deferred.


## First static scan: interpretation correction

The first scan completed without parse errors and found no declared concept with zero
references.  However its consumer counts are **not yet final** for two reasons:

1. it excluded all of `persona.py`, even though `persona.open_pct`, bias helpers,
   ICM helpers and variance helpers are real decision-time consumers;
2. it counted root diagnostic helpers such as `tools_pcz_semibluff.py` and legacy
   modules as if they were production consumers.

Therefore low-coverage findings from v1 must not be treated as missing wiring yet.

Examples:

- `positional` appeared to have only the money-jump observation consumer, but
  `persona.open_pct` directly uses `sk(prof, 'positional')` to flatten or preserve
  positional RFI differences.  It is behaviorally wired.
- top-level reads such as `profile['bluff']` and `profile['icm']` are not
  automatically stale under tilt: `persona.tilted_view` rebuilds the compatibility
  fields through `derive()` after tilting the concept vector.
- a single central consumer can be intentional; e.g. street-specific c-bet concepts are
  funneled through `cbet_freq`.

`tools/concept_wiring_audit_v2.py` corrects the inventory scope by including
`persona.py` behavioral helpers and excluding root diagnostics / legacy dynamics from
core-runtime consumer counts.

The structural issues that remain independently confirmed before v2 are:

- money-jump is partially wired: unopened range is live, open-size and limp-form remain
  shadow-only;
- blockbet/donk semantics without an aggressor remain explicitly unresolved in
  `plan.py`;
- concept generation priors/loadings remain explicitly provisional.
