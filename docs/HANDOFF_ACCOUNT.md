# 다른 계정으로 인계 (2026-11-08 22시 UTC)

다른 Claude 계정(같은 사용자)이 이어받을 때 이 문서 하나로 시작한다. 지금 상태 전체는 `docs/STATUS.md`,
GTO 계산 진행은 `docs/GTO_FULLTREE_STATUS.md`, 일하는 규칙은 `docs/T2_HANDOFF.md`.

## 0. 먼저 알 것

- **세션은 계정끼리 보이지 않는다.** 이 계정에서 연 세션(조정·보드)은 새 계정에서 메시지를 보내거나 멈출 수 없다.
  둘이 만나는 곳은 **GitHub 브랜치뿐**이다. 그래서 "누가 어떤 브랜치에 쓰는지"를 겹치지 않게 나누는 것이 핵심이다.
- 한 보드 브랜치(`claude/ft<스택>_board_<n>`)에는 **한 세션만** 쓴다. 두 세션이 같은 브랜치에 밀면 푸시가 부딪친다.
- 계정당 동시에 뜨는 세션 수에 한도가 있다(11-08 관찰: 약 50개 넘으면 새 세션이 PENDING 에서 안 뜬다. 정확한 수는 문서에 없음).
- 사용자 규칙(요약): 한국어로 짧게, 전문 용어 줄이기 / 그림은 PNG / 결과를 기대에 끼워 맞추지 않기 /
  master 는 사용자 승인 때만 / 강제 푸시 금지 / 커밋에 모델 이름 금지 / Termux 명령은 한 덩어리로 /
  GTO 결과를 봇에 붙이는 것은 사용자 승인 / 비밀값은 채팅·환경 변수에 넣지 않기 / 꼼꼼하게.

## 1. 지금 누가 무엇을 돌리나 (11-08 22시 UTC)

진행은 언제든 `sh tools/t2_handoff/ft_progress.sh <스택> <단계>` 로 센다(test3 에 있음, 읽기만 함).

| 스택·단계 | 끝난 묶음 | 돌리는 쪽 | 비어 있는 보드 번호 |
|---|---|---|---|
| 60bb 1단계 | 23/80 | 이 계정 보드 세션 20개(1~20) | 없음 |
| 100bb 0단계 | 47/98 | 이 계정 보드 세션 20개(1~20) | 없음 |
| 40bb 0단계 | 72/74 | 이 계정 보드 17·18번(각 1묶음 남음) | 없음 |
| 30bb 1단계 | 6/50 | 이 계정 보드 1~5·20번 | **6~19번 (14개, 묶음 39개)** — 이 계정에서 세션이 안 떠서 닫아 둠 |

**새 계정이 바로 할 일 = 30bb 1단계 보드 6~19번.** 아래 2장 문구로 세션 14개를 연다(1~5·20번은 건드리지 않는다).
30bb 묶음 하나는 실측 약 5시간(11-08, 문서 예상 0.8~1.9h 보다 느림), 세션당 2~3묶음 → 10~15시간.

각 스택의 "모으기·판정·다음 단계 입력 만들기"는 이 계정의 조정 세션이 한다(세션 id 는 `docs/GTO_FULLTREE_STATUS.md` 3장).
이 계정이 멈추면 3장대로 새 계정이 조정을 이어받는다.

## 2. 보드 세션 여는 문구 (새 계정, Sonnet 으로)

저장소 `jiyul-git/t2`, 시작 브랜치 `claude/ft<스택>_coord`. `<S>`(스택), `<K>`(단계), `<n>`(보드 번호)만 바꿔 붙인다.
30bb 1단계 6~19번이면 `<S>=30`, `<K>=1`, `<n>=6..19`.

```
You are board session <n> of 20 for the <S>bb full-tree precision run (ft<S>), STEP <K>. Reply in short Korean. Never force push. No model names in commits; end commit messages with:
Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: <this session's URL>
Only push to claude/ft<S>_board_<n>. Do not touch test3, master, or other branches. Do not compute values or judge pass/fail. The user approved this run.

Read docs/GTO_FULLTREE_PILOT_60BB.md section 9 (on origin/claude/ft<S>_coord). Then run as one command:
git fetch origin claude/ft<S>_coord claude/ft<S>_board_<n> && git checkout -B claude/ft<S>_board_<n> origin/claude/ft<S>_board_<n> && git merge -q --no-edit origin/claude/ft<S>_coord && sh tools/gto_fulltree/ft_board_setup.sh && B=$(awk -F'\t' -v n=<n> 'NR>1 && $2==n {print $1}' data/ft<S>/step<K>/assign.tsv | tr '\n' ' ') && (FT_SESSION=<this session id> setsid nohup /home/user/gto_ckpt/py311bin/python3 tools/gto_fulltree/ft_board.py $B > /home/user/gto_ckpt/ft<S>_board.log 2>&1 < /dev/null &)
(setup must end with FT_BOARD_SETUP_OK). Always keep one tracked waiting task (Bash run_in_background=true, timeout=7100000): until ! pgrep -f ft_board.py > /dev/null; do sleep 120; done; tail -5 /home/user/gto_ckpt/ft<S>_board.log
On each notification: alive → re-arm only; died and last line not FT_BOARD_ALL_DONE → rerun the run part (pushed chunks are skipped) and re-arm. Same error twice in a row → stop and report. After a usage limit, check pgrep and resume.
Send one short line when the run has started, and one at FT_BOARD_ALL_DONE (bundles, boards, failures after retry).
```

- 만든 세션이 몇 분 넘게 PENDING 이면 닫고 다시 만든다. 그래도 안 뜨면 동시 실행 한도다 → 다른 세션이 끝난 뒤에 연다.
- 컨테이너가 죽거나 사용량 한도로 멈춰도, 같은 명령을 다시 돌리면 이미 올라간 덩어리(12보드)는 건너뛴다.
- 보드 브랜치가 아직 없으면(`claude/ft<S>_board_<n>`) 첫 명령의 fetch 가 실패한다 → `git checkout -b claude/ft<S>_board_<n> origin/claude/ft<S>_coord` 로 만들고 이어 간다.

## 3. 이 계정이 멈췄을 때 (조정 이어받기)

알아보는 법: `ft_progress.sh` 에서 어떤 보드의 마지막 커밋이 **3시간 넘게** 그대로이고, 끝난 묶음이 맡은 수보다 적다
(보드는 12보드마다, 보통 1시간 안쪽으로 푸시한다).

1. **멈춘 보드 이어받기**: 그 보드 번호로 2장 문구를 새 계정에서 연다(같은 브랜치, 올라간 덩어리는 건너뜀).
   이 계정의 옛 세션이 나중에 되살아나 같은 브랜치에 밀 수 있으니, 사용자에게 이 계정에서 그 세션을 닫아 달라고 한다.
2. **조정 이어받기**: 스택마다 새 세션 하나(Sonnet 또는 Opus)를 `claude/ft<S>_coord` 에서 열고 아래 문구를 준다.

```
You take over as the coordinator of the <S>bb full-tree precision run (ft<S>) from another account. Reply in short Korean. Never force push. No model names in commits.
Only push to claude/ft<S>_coord. Read, in this order: docs/HANDOFF_ACCOUNT.md and docs/GTO_FULLTREE_STATUS.md (on origin/test3), then docs/GTO_FULLTREE_PILOT_60BB.md sections 3, 7, 9 and docs/GTO_FULLTREE_<S>BB.md if present (on origin/claude/ft<S>_coord), and git log of claude/ft<S>_coord.
Work out the current step k from the branch (data/ft<S>/step<k>/ and data/ft<S>/step<k>/collect/). Count finished bundles with: sh tools/t2_handoff/ft_progress.sh <S> <k> (from a test3 checkout).
When all bundles of step k have done.json: run `ft60.py collect k` (FT_STACK=<S>), report the verdict (D vs U, A/B replication, root replication, flop failures) in short Korean, then if not passed prepare step k+1 (next_tables 0.5·T + 0.5·V, full-tree solve, bundles, assign over 20 board sessions) and stop: board sessions are opened by the user's main session, not by you.
Rules decided by the user: full-tree solve gap < 0.02bb then proceed (record if > 0.010; max 800 iterations; stop and report if 50-iteration decrease < 10% or gap rises); a flop still failing after CFR+ retry is accepted if ≤ 0.6% pot and recorded; 20 board sessions per stack; max steps 0–3; do not connect any result to the bots.
```

## 4. 스택별 다음 일

| 스택 | 다음 |
|---|---|
| 40bb | 74/74 되면 collect 0 → 판정 → (안 통과면) 1단계 입력 + 보드 20개 |
| 60bb | 80/80 되면 collect 1 → 판정. **0단계 대비 D/U 가 줄었는지**가 사용자 관심사. 끝나면 결과 저장 방식 결정(5장) |
| 30bb | 50/50 되면 collect 1 |
| 100bb | 98/98 되면 collect 0 |

3명 이상 플랍 갈래(전체 플랍의 37~53%)는 아직 간이 값이다. 정밀하게 풀지는 사용자 결정 대기.

## 5. 사용자 결정 대기 (GTO 쪽)

1. 결과 저장 방식: 측정 끝(`claude/strategy_percard_20261108`, `docs/STRATEGY_PERCARD_MEASURE.md`).
   리버까지 카드별 = 4스택 한 단계 약 1.1TB(줄여도 85~170GB) → 측정 세션 추천은 "턴만 카드별, 리버는 지금처럼 평균,
   약 1.6~3GB, git 말고 객체 저장소". **60bb 끝난 뒤 사용자와 정하기로 함.**
2. 연구실 컴퓨터(24시간)로 보드 계산: 운영체제·코어·RAM·GitHub 로그인 정보를 사용자에게서 받으면 실행 스크립트를 만든다.
   보드 하나 최대 메모리 약 2.1GB, 4코어 기준 시간은 위 표.

## 6. GTO 밖에서 남은 일 (`docs/STATUS.md` 3·5·6장)

- 폰 리버 폴드 뒤 약 15초 멈춤: 폰 `server.log` 의 `[처리시간]` 줄을 사용자에게서 받아야 한다.
- 관전 2단계(입장 로딩 없애기) 미착수. 코드 정리 3단계(`app.js`, `ui_server.py` 나누기)는 사용자 승인 대기.
- test3 의 Actions `p17-test3-integration` 은 내 변경 전부터 실패(고정 기준선 검사). 손대지 않음.
- APK 영구 서명 키(사용자 작업).
