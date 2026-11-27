# 전체 트리 GTO 계산 — 인수인계 (어느 계정·세션이든 이것만 읽고 이어받는다)

## 0. 시작 전에 반드시 (중복 계산 금지)
1. `cat data/ft<STACK>/RUNNING.md` — 지금 누가 무엇을 돌리는지. 여기 있는 일은 다시 돌리지 않는다.
2. `bash tools/gto_fulltree/ft_status.sh <단계>` (FT_STACK=60|100) — 모든 계정의 보드 브랜치를 보고 남은 묶음만 출력. `@`는 최근 3시간 안에 진행 중.
3. 새 일을 시작하면 RUNNING.md 에 한 줄 추가·푸시, 끝나면 지운다. 로컬에서 긴 계산을 돌리면 `tools/gto_fulltree/ft_progress_push.sh <로그> <저장소 경로> <브랜치> <pgrep 패턴>` 로 진행 기록을 자동 푸시.

## 1. 한 단계의 흐름 (조정 세션)
`ft60.py`(공용, FT_STACK 로 스택 선택) 기준. 작업 폴더 FT_WORK, 계산 체크아웃 /home/user/calc (`sh tools/gto_fulltree/ft_coord_setup.sh`).
1. 트리 풀이: `FT_STACK=S FT_WORK=... setsid nohup sh tools/gto_fulltree/ft_solve.sh k > log &` — 정확 gap < 0.02 에서 멈추고 dump.jsonl 생성. 4코어 약 2~4시간.
2. 끝점 준비: `FT_PANEL_SET=bal FT_SESSIONS=<세션수> FT_BOARD_HOURS=data/ft<S>/step<k-1>_board_hours.json python3 tools/gto_fulltree/ft60.py prepare k <ck.gtop> <dump.jsonl>` → bundles.tsv·assign.tsv. 패널은 반드시 균형 패널(bal).
3. 보드 계산(묶음 80개 안팎): 아래 2장. 사람 세션 대신 GitHub Actions 를 먼저 쓴다(3장).
4. 모으기: `FT_PANEL_SET=bal python3 tools/gto_fulltree/ft60.py collect k` (used_gross.jsonl.gz 가 없으면 FT_WORK/step<k>_export.jsonl 을 gzip 해서 data/ft<S>/step<k>/ 에 둔다).
5. 다음 표: `python3 tools/gto_fulltree/ft60.py next_tables k` (패널을 바꾼 직후처럼 알려진 오류를 뺄 때만 FT_REPLACE=1). 세 명 팟 표 10개는 그대로 이어진다(아래 4장 주의).

## 2. 보드 세션(클라우드 세션을 쓸 때) — 토큰 최소화 규칙
- 모델: Haiku. 지시문: `tools/gto_fulltree/WORKER_PROMPT.md` 의 <N>, <묶음들> 만 바꿔 그대로 쓴다.
- 세션은 `ft_worker.sh` 한 명령만 반복한다(브랜치·setup·실행·중복 방지·재시작·잔여 프로세스 정리·푸시 확인 내장). 마지막 줄 WORKER_ALL_DONE / WORKER_RUNNING / WORKER_FAIL.
- 세션을 만든 뒤 PENDING 으로 멈춰 있으면 "시작해 주세요" 메시지 한 줄로 깨운다.
- 세션 보관(archive) 전에는 get_session 으로 제목을 확인한다(계산 중인 세션을 보관한 사고 있음).
- 동시 세션은 약 50개가 한계로 보임. 주간 사용 한도에 걸리면 세션이 멈춘다(11-18 실제 발생).

## 3. GitHub Actions (토큰 0) — 우선 사용
- 워크플로: `.github/workflows/ft-board.yml` (이 브랜치). 트리거 브랜치에 묶음 목록을 푸시하면 묶음마다 작업 하나가 돈다. 작업은 ft_worker.sh 를 최대 5시간 40분 돌리고, 못 끝난 묶음은 다시 트리거하면 이어서 한다.
- 무료 실행 시간 한도 안에서 쓴다. 자세한 사용법은 워크플로 파일 머리말.

## 4. 현재 상태 (2026-11-27)
- 60bb: 6단계 보드 79/80 끝, 남은 s6_t11_B 는 다른 계정 보드 26 이 계산 중. 끝나면 collect 6 → next_tables 6 → 7단계.
- 100bb: 2단계 트리 풀이 진행 중(RUNNING.md 참조, 브랜치 claude/ft100_coord). 끝나면 prepare 2 부터.
- 세 명 팟 값의 알려진 문제: 턴·리버를 일부만 본 계산(지금 표)은 정답(연구실 전체 계산) 대비 평균 0.4~0.9bb 차이, BB·BTN 을 높게 보는 쏠림, SB 선베팅을 25~35%로 과대(정답 1~10%). 보정 방법은 미정 — 연구실 정답 4개(Kc7d4h, AhQh3h, Ts4c4s 완료, 9c8d2c·AcKhJd 진행) 결과로 결정한다. 비교 스크립트·데이터: 브랜치 claude/ft3way_lab_1, claude/ft3way_calib_1~4.
- 사용자 규칙: 결과에 맞추지 말 것, 그림은 PNG, master·봇 연결은 사용자 승인, 강제 푸시 금지, 커밋에 모델명 금지.
