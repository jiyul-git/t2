# P15 PR27 independent remote audit

Production target: `3c434b28046643ba54c04447951ad148ae6f9c1c`.
Historical local audit: `63e47c10d881153095b33f9711c09764d6dc1ad5`.
User authorized an isolated audit-only branch and Actions execution. No merge,
production modification, test3 update or deployment is authorized.
All tracked additions are audit scripts, historical evidence, this report and a
separate workflow. CI asserts every changed path is an allowed new audit file;
existing target files, strategy, coefficients and scheduling remain identical.

Historical evidence under `p15_history/` describes its original revisions, not
this CI. Its P15 metadata patch is deliberately NOT applied to PR27. The archived
historical script is reference-only. The current origin probe observes call-stack
source labels without injecting new fields into production BF logs. PR27 already
archives `field_epoch_timing`: synchronous finish states after-HERO origin and
`common_start_epoch_verified: false`. Deferred/vclock finish deliberately reports
`not_observed_in_synchronous_finish`; the audit cannot upgrade that to a shared
HERO epoch claim. The audit's independent origin evidence supplements this log.

| Path | Snapshot created | Consumed | Provenance boundary |
|---|---|---|---|
| build_hand | HERO observed field before action | HERO stamp | HERO start, including already committed events |
| finish default | HERO result committed first | step_others simultaneous | After HERO; not HERO common start |
| step_others simultaneous | After plan seeds, before batch | all planned stamps/workers | Common start of THAT batch; earlier same-batch results deliberately hidden |
| compute_others_parallel | supplied retained round_base | serial runner or process workers | Common retained round start; ownership-checked merge later |
| compute_others | supplied input dump | legacy simultaneous batch | Input origin; recovery may supply post-HERO dump |
| compute_vclock_ahead | supplied observed field at invocation | speculative local event tasks | Independent batch start, local event clocks may advance |
| apply_vclock_events | no replacement for stamped historical reference | completion-time ordered merge | Results committed at event boundary; next HERO observes committed state |

Release, hand and level transitions must invalidate a retained frozen attestation.
A changed current roster with no valid batch reference is stale; a valid frozen
batch intentionally omits uncommitted other-table outcomes. Frozen exact ICM is
reference-epoch exact, never latest decision-current exact. Large fields may use
empirical BF despite a valid frozen reference; the 27-player probe does not
mistakenly require an exact method. Small-field exact/partial comparisons are
covered separately by the existing P13 gate.

Reproduce: `PYTHONHASHSEED=0 python tools/run_p15_pr27_audit.py`.
Python 3.12, remote ubuntu-latest; exact Python/kernel/CPU/env are persisted in
`p15-ci-results/summary.json`. Per-check stdout and exit codes are separate.
Only nondeterministic `compute_ms` is removed from the parallel log comparison;
all actions and BF provenance remain compared. The entire worker return, direct
field dump, coordinator RNG and time banks are compared.
Seed 4 naturally schedules one hand on each of two nonhero tables. Seed 11 is
retained as compatibility coverage, never described as two executed hands.
The 27-player origin replay compares default/deferred/vclock, three HERO rounds,
timing OFF and ON against an exact detached target worktree. It compares game
state, ranks, bust ordering, moves, cards/actions/stacks, banks and RNG. Virtual
speculative hand counts are logged separately from committed HERO rounds.
Async-refill and virtual-finish fixtures cover donor arrival, active pot ownership,
replay idempotence, chip conservation, bust/rank/archive and H4H barriers.

Upstream CI `38049054671` is verified SUCCESS at the exact target SHA; it is not
this audit's remote result. The independent workflow's actual result must be read
from its run and artifact before approval. No unconditional approval is recorded
in this pre-run report. Final evidence and department 8/5/17 handoff belong in the
PR27 review conversation after all nine gates complete.
