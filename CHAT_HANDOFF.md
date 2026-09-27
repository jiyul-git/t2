# CHAT HANDOFF PROTOCOL

Purpose: keep ChatGPT sessions small without losing project continuity.

## Start of every new chat

The assistant should:
1. open `CURRENT_STATUS.md` on the stable canonical baseline;
2. open `ACTIVE_WORK.md`;
3. verify the referenced remote branch HEADs before trusting branch names;
4. read only the files required for the selected workstream.

Do not reconstruct the whole project from old chats when GitHub already contains the source, result, or decision.

## One chat = one workstream

Recommended separation:
- engine / decision logic
- live hand review + GTO reference
- solver / CFR tooling
- UI
- experiments / calibration

A chat may cross files inside one workstream, but a major topic switch should start a new chat.

## What belongs in GitHub

Must be written to GitHub rather than left only in chat:
- code changes
- exact experiment configuration
- solver/GTO frequency data
- bug diagnosis that changes future work
- branch/commit chosen as a checkpoint
- verification results needed for later decisions

Chat is for reasoning and execution, not durable storage.

## End-of-session handoff

Before moving to a new chat, update `ACTIVE_WORK.md` with five fields:
- branch and exact HEAD
- completed work
- measured/verified result
- unresolved issue
- exact next action

If a new permanent design decision was made, update the relevant design/status document too.

## Branch rule

Do not create a new branch merely because a new chat starts.
New chat and new Git branch are independent.

A new branch requires a code-history reason such as:
- risky experiment
- attribution-sensitive experiment
- migration/rollback boundary
- intentionally isolated solver/vendor work

Before deleting or merging a branch, prove containment or inspect its unique commits.

## Minimal starter message for a new chat

"GitHub `jiyul-git/t2`의 `CURRENT_STATUS.md`와 `ACTIVE_WORK.md`를 먼저 읽고, ACTIVE_WORK의 현재 작업부터 이어서 진행해. 필요 파일만 추가로 읽어."

That should be enough; do not paste previous chats unless a fact exists only there.
