# ACTIVE WORK — READ AFTER CURRENT_STATUS

Last updated: 2026-09-28 KST

이 파일은 채팅 간 인수인계를 위한 **짧은 실시간 작업 장부**다.
완료된 상세 근거는 기존 설계/결과 문서와 Git commit에 남기고, 여기에는 현재 작업만 적는다.

## Branch topology right now

Stable canonical baseline:
- `chatgpt/decision-architecture-audit-20260926`
- current remote head observed: `9330c4f7fc5acb09775f39f7f9174183299cc7fc`

Active engine / hand-review line:
- `chatgpt/logic-tuning-20260927`
- head: `6d2a663460acd2ed296741d828a960f4d9b3c557`
- recent engine fixes include board-danger connectivity and duplicate preflop defend-call cliff removal.
- this branch has 8 commits not contained in the mini-CFR line. Do not assume the solver branch contains these engine fixes.

GTO reference line:
- `chatgpt/gto-reference-20260928`
- head: `2897def3543bc61f080252f234709af7f2deb499`
- reference workflow: `GTO_REFERENCE.md`
- situation data: `data/gto_scenarios.jsonl`

Mini-CFR / vendored solver line:
- `chatgpt/mini-cfr-solver-20260928`
- head: `80026c02326e54694ce40ee27c87e521d2098708`
- diverged from both logic-tuning and gto-reference; do not merge or delete by branch name alone.
- compared with gto-reference, branch graph currently contains unique commits on both sides.

Legacy-looking but not actually latest:
- `integration/latest-20260927` @ `a02a51960f9c27de207f464be35ac52115381c24`
- despite its name, it is behind the current workstreams. Do not use its name as proof of recency.

## Current workstream

Primary task: continue live hand review one table/spot at a time, using GTO only as a reference baseline.

Immediate state:
- board-danger had a real zero/under-detection issue and was fixed on `logic-tuning`.
- betting/action probabilities affected by that signal must be measured again from the post-fix engine before drawing conclusions from earlier captures.
- GTO frequencies already obtained should be appended/preserved in `data/gto_scenarios.jsonl`; do not leave solver results only in chat.
- do not stop the hand-review flow merely because a solver run/result is pending; preserve the spot and continue from the recorded checkpoint when possible.

## Next actions

1. Reconcile the exact hand-review spot against `logic-tuning` post-fix output.
2. Save the resulting T2 probabilities and matched GTO frequencies to the reference dataset.
3. Inspect the 8 logic-tuning-only commits before any solver/engine branch integration.
4. Inspect the 4 gto-reference-only commits relative to mini-CFR before cleanup.
5. Only after containment/intent is clear, choose merge/cherry-pick/abandon and update this file.

## Session rule

A new chat should not reread the entire repository.
Read, in order:
1. `CURRENT_STATUS.md`
2. `ACTIVE_WORK.md`
3. only the detailed document/code files named by the active workstream.

Before ending a work session, update this file with:
- branch + exact HEAD
- what changed
- verification/result
- unresolved item
- exact next action
