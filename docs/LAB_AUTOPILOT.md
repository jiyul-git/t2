# 연구실 자동 계산·판단 봇 (lab autopilot)

사용자가 2주 동안 연구실에 안 들어와도 GTO 풀트리 계산이 알아서 이어지게 하는 봇. 계산·기록만 한다(GTO 결과를 봇 런타임에 연결하지 않음, 결과를 거꾸로 맞추지 않음).
브랜치 `claude/lab_autopilot` (claude/ft30_coord 에서 분기). 코드: `tools/gto_fulltree/lab_autopilot/` (`autopilot.py` 본체, `judge.py` 판정 함수, `board_run.py` 보드 실행 래퍼, `lab_autopilot.sh` 시작 스크립트, `config.json`, `test_autopilot.py`).
기존 `lab_ft.sh` 는 그대로 둔다(같은 작업 폴더 `~/t2lab/b<n>` 을 이어서 쓴다).

## 1. 한 줄 요약
깃허브를 공용 작업판으로 읽어서(조정 브랜치 + 보드 브랜치 + claim 브랜치) **남이 안 잡은 일만** 골라, 코어 6개·낮은 우선순위로 계산하고, 단계가 끝날 때마다 **코디네이터와 같은 기준으로 판정**해서 완료면 멈추고 미완이면 다음 단계(표 → 트리 풀이 → prepare → 보드)로 자동 진행한다.

## 2. 판정 기준 표 (`judge.py` 의 `judge()` 하나)
출처: [P3]/[P7] = `docs/GTO_FULLTREE_PILOT_60BB.md` 3·7장, [U] = 사용자 결정(날짜), [M] = `docs/GTO_FT_MATRIX_TERMINAL.md`, [C] = `ft60.py` collect/next_tables 코드.
`collect` 가 `report.json` 에 이미 계산해 둔 값(D, U, 복제, dM_vs_prev_step …)을 읽어서 판정한다. 봇이 숫자를 새로 만들지 않는다.

| 번호 | 기준 | 규칙(통과 조건) | 출처 | 상태 |
|---|---|---|---|---|
| C1 | 묶음 전부 도착 | `bundles_missing` 0 | [C] | 구현 |
| C2 | 플랍 실패(재시도 뒤에도 안 풀린 보드) | 재시도 결과 ≤ 0.6 % pot 이면 받아들이고 `flop_failure_decision.json` 기록. 초과하면 그 끝점은 정적 유지(`static_nodes.json`)하고 계속 | [U 11-08] [M] | 구현. "초과 시 멈춤" 은 설정 `flop_fail_action: stop` |
| C3 | 트리 풀이 정확 gap | < 0.02 (미만). 0.010 초과면 "기록"만. 반복 횟수 상한·"50회 감소 10 %" 규칙 없음 | [U 11-10] [P7] | 구현(풀이 스크립트가 이 기준으로 멈춤, 판정표에는 값 기록) |
| C4 | **D ≤ U** (A∪B 144보드) | **모든 자리**에서 통과. 상대가 1콤보 미만으로 오는 자리는 면제(개정 8) | [P3 ①] | 구현 |
| C5 | **A·B 복제**(값) | 모든 자리 \|V_A − V_B\| ≤ 2·√(U_A² + U_B²) | [P3 ②] | 구현 |
| C6 | 끝점 고르기 안정 | 이번 단계에서 새로 기준을 넘은 끝점의 헤즈업 도달 몫 합 ≤ 1 % (이전 단계 `bundles.tsv` 와 비교, 분모 `prepare.json` 의 `hu_mass`). 이전 단계가 없으면 알 수 없음(통과 막지 않음) | [P7] | 구현 |
| C7 | **뿌리 복제**(A만·B만 전체 트리) | 전략 차이 ≤ 5 %p 인 콤보 ≥ 95 % | [P3 ③] | **확인 필요 NC-1**: 도구가 없음. `step<k>/root_replication.json`(`{"fraction":0.97}`) 이 올라오면 읽음. 없으면 "값 통과(뿌리 복제 확인 대기)"에서 그 스택을 멈춤 |
| C8 | 진동 끝점 감쇠 | 끝점 최대 D/U 기록 h 에서 `h[-1] > 1` 이고 `(h[-3]-h[-2])·(h[-2]-h[-1]) < 0` 이면 α = 0.25, 아니면 0.5 (`next_tables` 가 적용, 판정표는 어느 끝점이 진동인지 기록) | [C] [P3] | 구현(정보) |
| C9 | 수렴 추세 | D/U 중앙값·D≤U 자리 수·`dM_vs_prev_step` 를 단계별로 기록. 사용자 11-12 "수렴률로 판단"의 **숫자 문턱이 문서에 없음** | [U 11-12] | **확인 필요 NC-2**: 판정에 쓰지 않음. 정체 경고만(최근 3단계에 D/U 중앙값이 5 % 도 안 줄면 경고, 임시값) |
| C10 | 합=팟 점검(`sum_check`) | 기록만(문턱 없음) | [M] | 기록 |
| C11 | 단계 상한 | 사용자 11-12 는 "단계 제한 없음". 무인 안전장치로 12단계(설정 `max_steps`)를 넘으면 사람 확인 대기 | 설정 | 임시값(NC-2) |
| — | 0단계는 통과 불가 | 최소 1회 갱신 뒤에만 통과로 침 | [C] | 구현 |

**판정 결과(status)**
| status | 뜻 | 봇의 행동 |
|---|---|---|
| `wait_boards` | 묶음이 덜 옴 | 기다림 |
| `continue` | 미통과 | `next_tables` → 트리 풀이 → `prepare` → 보드 순으로 다음 단계 |
| `converged` | C4·C5·C6 통과 + C7 통과 | 그 스택을 **완료**로 표시하고 멈춤(다음 스택으로) |
| `values_pass_pending_root` | C4·C5·C6 통과, C7 확인 필요 | 멈추고 코디네이터 확인 대기(상태 파일에 표시) |
| `stop_report` | 플랍 실패 처리 불가·단계 상한 | 멈추고 보고 |

실제 보고서로 검증: ft30 0단계 D≤U 0/58·D/U 중앙값 4.38, 1단계 5/50·3.13 (문서 8·10장 숫자와 일치), ft60 2단계 11/80·3.22·dM 중앙값 3.35 (`GTO_FT60_STEP2_RESULT.md` 와 일치).
판정표 보기: `python3 autopilot.py judge 30 1` (깃허브 조정 브랜치를 읽음) 또는 `judge.py <report.json>`. 단계가 판정될 때마다 `data/ft<스택>/step<k>/judge.json·judge.md` 로 조정 브랜치에 남긴다.

## 3. 단계 흐름과 누가 하나
한 단계 = 표 → 트리 풀이(solve) → prepare(끝점·묶음·assign.tsv) → 보드(묶음 A/B 패널 72보드) → collect → 판정 → next_tables → 다음 단계 표.
봇은 스택마다 **조정 브랜치의 파일만** 보고 지금 어느 단계인지 정한다.

| 조정 브랜치에 있는 것 | 지금 단계(phase) | 하는 일 |
|---|---|---|
| `step<k>/tables/manifest.json` 만 | solve | `ft_solve.sh k` (정확 gap < 0.02 까지, 처음부터) → `solve/`·`convergence.json` 올림 |
| `solve/final_n`+`dump.jsonl.gz`, prepare 없음 | prepare | `ft60.py prepare k` + `used_gross.jsonl.gz`·`terminals_mass.json.gz` 올림 (체크포인트가 연구실에 없으면 풀이를 다시 함) |
| `bundles.tsv`·`assign.tsv`·`prepare.json` | boards | 보드 번호별로 아래 4장 규칙으로 계산 |
| 모든 묶음에 `done.json` | collect | `ft60.py collect k` → `collect/report.json`, 판정 `judge.json` 올림 |
| `collect/report.json`(완료) + 판정 continue | next_tables | `ft60.py next_tables k` → `step<k+1>/tables/`·`history.json` 올림 |
| 판정 converged / 확인 대기 / 멈춤 | halted | 그 스택은 더 안 함 |

**이미 있으면 하지 않는다**(규칙 d): 단계 결과가 조정 브랜치에 이미 있으면 그 단계는 건너뛴다. 또 조정 브랜치의 마지막 푸시가 4시간(`coord_idle_hours`) 안이면 조정 세션이 작업 중일 수 있어 조정 단계(solve·prepare·collect·next_tables)는 시작하지 않는다. 조정 단계도 claim 을 먼저 잡는다. `next_tables` 는 `history.json` 에 덧붙이는 방식이라 실패하면 되돌리고, 같은 조정 일은 6시간 안에 반복하지 않는다.
조정 단계는 설정 `coord_actions: true` 인 스택(기본 30 만)에서만 한다. 다른 스택은 **보드만 돕는다**.
도구 버전은 **각 스택 조정 브랜치에 있는 tools 를 그대로** 쓴다(코디가 새 버전을 올리면 자동 반영, 풀이·내보내기 바이너리는 도구가 바뀌면 `ft_coord_setup.sh` 로 다시 빌드).

## 4. 깃허브 공용 작업판 (겹치지 않게)
(a) **읽기**: 스택마다 조정 브랜치(`claude/ft<S>_coord`)에서 단계·`assign.tsv`·묶음 목록을 읽고, `claude/ft<S>_board_<n>` 에서 묶음별 `done.json`(끝남)/그 밖 결과 파일(부분)/없음을 읽는다. `git ls-remote` 로 브랜치 sha 가 바뀐 것만 얕게(`--depth=1 --filter=blob:none`) 가져온다. 읽기 전용 저장소(`~/t2lab/peek`)를 따로 써서 사용자 저장소의 이력을 건드리지 않는다.

(b) **claim**: 보드 번호 하나(= 그 번호의 묶음 전부)를 시작하기 전에 `claude/ft_claims` 브랜치에 파일 하나를 푸시한다.
- 파일: `claims/ft<스택>/step<단계>/board_<n>.json` (조정 단계는 `coord_solve|coord_prepare|coord_collect|coord_next_tables`)
  `{"owner","host","t_claim","t_heartbeat","note"}`
- 같은 부모에서 푸시 경쟁이 나면 **나중 푸시가 거절**된다 → 다시 읽어서 파일이 이미 있으면 진 것. 원자성은 git 푸시 거절로 확보(force 없음). 로컬 시험: 3개 프로세스 동시 → 정확히 1개 성공.
- 일하는 동안 30분마다 `t_heartbeat` 갱신. 하트비트가 `claim_ttl_hours`(3시간)보다 오래되면 죽은 claim 으로 보고 인계 가능. 끝나거나 실패하면 파일을 지운다(release).
- 다른 계정·클라우드 세션도 같은 방식으로 쓸 수 있다: `python3 tools/gto_fulltree/lab_autopilot/autopilot.py claim 30 1 board_7 --owner <이름>` (성공 시 `CLAIM_OK`, 이미 잡혔으면 종료코드 3 `CLAIM_TAKEN`), 끝나면 `release`.

(c) **건너뛰는 규칙**(보드 번호 n 마다):
| 상태 | 연구실 행동 |
|---|---|
| 모든 묶음 `done.json` 있음 | 건너뜀(끝남) |
| 다른 쪽 claim 이 하트비트 3시간 안 | 건너뜀 |
| 그 브랜치에 다른 쪽이 3시간(`active_hours`) 안에 푸시 | 건너뜀(작업 중) |
| 부분 푸시/일부 끝남이 있고 내 것이 아님 | 건너뜀. 마지막 푸시가 24시간(`stale_takeover_hours`) 넘게 멈췄으면 인계(그 브랜치를 이어서, 끝난 12보드 덩어리는 건너뜀) |
| 이 단계 결과가 없음(브랜치가 없거나 옛 단계 흔적만) | 새로 시작 |
| 내 것(내 claim 또는 내 작업 폴더가 있는 브랜치) | 이어서 |

(d) **우선순위**: 스택 우선순위 순(기본 30 → 40 → 60 → 100). 30bb 에 연구실이 잡을 보드·조정 일이 없으면(끝났거나 모두 남이 잡음/막힘) 자동으로 다음 스택의 "아무도 안 잡은 보드"를 돕는다. 스택별 허용 여부는 `config.json` 의 `stacks.<S>.enabled/boards/coord_actions`. 잡을 일이 없으면 30분 뒤 다시 확인.
**주의**: 아직 claim 을 모르는 클라우드 세션이 같은 번호를 막 시작했다면(첫 푸시 전 약 1시간) 겹칠 수 있다. 결과는 같은 입력·같은 절차라 어느 쪽이 먼저 올려도 같은 값이고, 보드 세션이 새로 열릴 때 위 claim 명령을 먼저 쓰도록 코디네이터가 알려 주면 완전히 막힌다.

(e) **상태 하트비트**: `claude/lab_status` 브랜치의 `status/t2-lab.json`·`.md`·`.log_tail.txt` 를 30분마다 갱신(지금 하는 일, 스택별 단계·보드 진행, 판정 요약, 오류, 디스크·CPU, 확인 필요 목록).
원격으로 보기: `git fetch origin claude/lab_status && git show origin/claude/lab_status:status/t2-lab.md`

## 5. CPU·디스크·무인 운영
- **CPU 6코어만**: 보드 2개 × 워커 3개(`SPOT_PANEL_WORKERS=3`, `RAYON_NUM_THREADS=1`) = 6. 조정 계산(풀이·prepare·collect)은 코어 3개(`RAYON_NUM_THREADS=3`)로 보드 1개와 함께(3+3). 모든 계산은 `nice -n 19` + (WSL 에서 되면) `ionice -c3`. 컴파일도 같은 낮은 우선순위. ft_board 가 못 맞춘 보드를 한꺼번에 최대 12개 재시도하는 것은 `board_run.py` 가 3개씩으로 제한한다(ft_board.py 수정 없음).
- **메모리**: 보드 워커 1개 약 8 % × 3 × 2 — 35GB 안.
- **재시도**: 계산이 죽으면 같은 명령으로 이어서(끝난 12보드 덩어리는 푸시돼 있음). 보드 하나가 5번 연속 실패하면 그 일을 5분→15분→1시간→3시간→12시간 간격으로 다시 시도(`input sha256 differs` 면 코디 확인 대기 표시). 봇 자체가 죽어도 `lab_autopilot.sh run` 이 30초 뒤 다시 시작하고, 시작할 때 이전 실행이 남긴 계산을 정리한다.
- **디스크 정리**: 푸시가 끝난 묶음의 보드 원본 폴더 삭제, 단계 지난 `collect_s*`(최근 2개만 유지)·오래된 체크포인트 삭제, 로그 50MB 넘으면 자름, 디스크 여유가 15GB 아래면 새 일 시작 안 하고 정리.
- **자체 갱신**: 5분마다 `claude/lab_autopilot` 새 커밋을 확인, 받으면 진행 중인 일이 끝나는 대로(최대 12시간) 다시 시작. 코디네이터가 이 브랜치에 고쳐 올리면 연구실이 알아서 받는다.
- **부팅 후 자동 시작**: Windows 작업 스케줄러(아래 6장). WSL 1 은 창이 닫히면 꺼지므로 `wsl.exe` 가 `run` 을 계속 붙잡고 있는 방식이다(10분마다 같은 명령을 한 번 더 걸어도 잠금 때문에 하나만 돈다).
- 커밋 이름 `t2-lab`. force push·PR·master/test3 수정 없음. 푸시 대상: 보드 브랜치(결과, 기존 방식), `claude/ft_claims`, `claude/lab_status`, (조정 단계) 스택 조정 브랜치 — 일반 푸시만, 거절되면 병합 후 다시, 충돌이면 중단·보고.

## 6. 설치·시작·상태 (사용자가 연구실 cmd 에 붙여넣기)
**설치+시작(한 덩어리, cmd)** — 봇 코드 받기 → 준비 점검(예전 lab_ft.sh 가 돌고 있으면 멈춤) → 로그인 때·10분마다 시작하는 작업 등록 → 절전 끄기 → 지금 시작:
```
wsl -d Ubuntu-22.04 -u user -- bash -lc "cd /home/user/t2 && git fetch -q origin claude/lab_autopilot && git show origin/claude/lab_autopilot:tools/gto_fulltree/lab_autopilot/lab_autopilot.sh | bash -s install" && schtasks /Create /F /TN T2LabAutopilot /SC ONLOGON /TR "wsl.exe -d Ubuntu-22.04 -u user -- bash -lc 'bash /home/user/t2lab/autopilot/tools/gto_fulltree/lab_autopilot/lab_autopilot.sh run'" && schtasks /Create /F /TN T2LabAutopilotKeep /SC MINUTE /MO 10 /TR "wsl.exe -d Ubuntu-22.04 -u user -- bash -lc 'bash /home/user/t2lab/autopilot/tools/gto_fulltree/lab_autopilot/lab_autopilot.sh run'" && powercfg /change standby-timeout-ac 0 && schtasks /Run /TN T2LabAutopilot
```
- 이 PC 가 재부팅 뒤 **로그인 없이** 바로 돌아야 하면: Windows 자동 로그인을 켜 두거나(`netplwiz`), 두 `schtasks /Create` 뒤에 `/RU <사용자> /RP <비밀번호>` 를 붙여 "로그온 여부와 관계없이" 로 등록한다(**확인 필요 NC-5**: 이 PC 설정을 몰라서 기본은 로그인 필요).
- 설치는 처음 한 번 계산 체크아웃이 없을 때만 10~20분 걸린다(이미 `/home/user/calc` 가 있으면 건너뜀).
- 시험만 해 보려면(푸시·계산 없이 "지금 할 일" 보기): `wsl -d Ubuntu-22.04 -u user -- bash -lc "bash /home/user/t2lab/autopilot/tools/gto_fulltree/lab_autopilot/lab_autopilot.sh once"`

**상태 확인(cmd)**
```
wsl -d Ubuntu-22.04 -u user -- bash -lc "bash /home/user/t2lab/autopilot/tools/gto_fulltree/lab_autopilot/lab_autopilot.sh status"
```
로그: 같은 명령에서 `status` 대신 `logs`. **멈춤**: `stop` (다시 시작은 작업 스케줄러가 10분 안에 하므로 완전히 끄려면 `schtasks /Delete /F /TN T2LabAutopilot` 와 `... T2LabAutopilotKeep` 도).
코디네이터가 원격으로: `git fetch origin claude/lab_status && git show origin/claude/lab_status:status/t2-lab.md`

## 7. 설정 (`config.json`, 바꿀 때는 `~/t2lab/config.local.json` 에 바꿀 것만)
코어 수·보드 수·워커 수·nice, 스택별 `enabled / priority / boards / coord_actions / coord_branch / coord_push_branch / cfg_file / solve_env / prepare_env / judge`, 시간 문턱(`claim_ttl_hours 3`, `active_hours 3`, `stale_takeover_hours 24`, `coord_idle_hours 4`), 디스크(`min_free_gb 15`), 판정 문턱(`judge.*`).
ft30 기본: `FT_MIN_REACH=1e-3`, `FT_SESSIONS=20`(코디네이터가 ft30 에서 쓴 값), 풀이 `FT_GAP_TARGET=0.02 FT_GATE=0.024`.

## 8. 시험 결과 (2026-11-26, 이 컨테이너, 계산기 없이/있이)
`python3 tools/gto_fulltree/lab_autopilot/test_autopilot.py`:
- 판정: 실제 ft30 0·1단계 보고서 숫자 일치, 가짜 전부 통과 → `values_pass_pending_root`, 뿌리 복제 97 % → `converged`, 90 % → 아님, 플랍 실패 0.43 % → 수용 / 0.9 % → 정적 유지, 진동 식.
- 공용 작업판(로컬 가짜 origin): 끝남/남이 방금 푸시/40시간 멈춤(인계)/일부 끝남/옛 단계 흔적/방금 시작된 보드를 의도대로 구분, claim 3개 동시 → 1개만 성공, 남의 claim 보드는 계획에서 빠짐, 상태 브랜치 푸시.
- 실제 계산기(`/home/user/calc` 빌드, `FT_TEST_BOARDS=2`, `FT_NO_PUSH=1`)로 보드 일 하나를 돌려 봄: 아래 9장.

## 9. 아직 확인 필요 (코디네이터에게 질문함, 답 전 기본값)
| 번호 | 내용 | 기본값 |
|---|---|---|
| NC-1 | 뿌리 복제(③) 도구가 없음. 생략해도 되는가? | 값 통과 뒤 그 스택을 멈추고 확인 대기 |
| NC-2 | "수렴률"(D/U 중앙값, D≤U 자리, dM_vs_prev_step)의 숫자 문턱, 단계 상한 | 판정에 안 씀, 정체 경고만, 12단계 상한 |
| NC-3 | ft30 2단계부터 쓸 도구 버전(행렬 끝점·bal 패널·`static_nodes.json`) | 조정 브랜치의 tools 를 그대로 따름. 구버전은 `static_nodes.json` 을 읽지 않음 |
| NC-4 | 조정 단계 결과를 어디에 푸시하나 | 조정 브랜치에 일반 푸시(`coord_push_branch` 로 `claude/ft30_lab_coord` 같은 별도 브랜치로 바꿀 수 있음) |
| NC-5 | 로그인 없이 부팅만으로 시작해야 하는가(작업 스케줄러 등록 방식) | 로그인 때 + 10분마다 |
| NC-6 | 풀이는 체크포인트 이어서가 아니라 "처음부터 정확 gap<0.02"(ft60 3·4단계와 같음) | 처음부터 |
