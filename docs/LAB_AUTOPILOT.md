# 연구실 자동 계산·판단 봇 (lab autopilot)

사용자가 2주 동안 연구실에 안 들어와도 GTO 풀트리 계산이 알아서 이어지게 하는 봇. 계산·기록만 한다(GTO 결과를 봇 런타임에 연결하지 않음, 결과를 거꾸로 맞추지 않음).
브랜치 `claude/lab_autopilot` (claude/ft30_coord 에서 분기). 코드: `tools/gto_fulltree/lab_autopilot/` — `autopilot.py` 본체, `judge.py` 판정 함수, `board_run.py` 보드 실행 래퍼, `lab_autopilot.sh` 시작 스크립트, `config.json`, `test_autopilot.py`.
기존 `lab_ft.sh` 는 그대로 둔다(같은 작업 폴더 `~/t2lab/b<n>` 을 이어서 쓴다).
**연구실 PC 와 Claude 는 직접 연결하지 않는다. 깃허브만 쓴다**: 오류 보고(`claude/lab_status`) → 원격 수정(`claude/lab_autopilot` 에 푸시 → 봇이 자동 반영) / 원격 명령(`claude/lab_status` 의 `control.json`).

## 1. 한 줄 요약
깃허브를 공용 작업판으로 읽어서(조정 브랜치 + 보드 브랜치 + claim 브랜치) **남이 안 잡은 일만** 골라, 코어 6개·낮은 우선순위로 계산하고, 단계가 끝날 때마다 **코디네이터와 같은 기준으로 판정**해서 완료면 멈추고 미완이면 다음 단계(표 → 트리 풀이 → prepare → 보드)로 자동 진행한다. 이상이 생기면 스스로 알아채서 `claude/lab_status` 에 올린다.

## 2. 판정 기준 표 (`judge.py` 의 `judge()` 하나)
출처: [P3]/[P7] = `docs/GTO_FULLTREE_PILOT_60BB.md` 3·7장, [U] = 사용자 결정(날짜), [M] = `docs/GTO_FT_MATRIX_TERMINAL.md`, [C] = `ft60.py` collect/next_tables 코드, [코디] = 코디네이터 답(11-26).
`collect` 가 `report.json` 에 이미 계산해 둔 값(D, U, 복제, dM_vs_prev_step …)을 읽어서 판정한다. 봇이 숫자를 새로 만들지 않는다.

| 번호 | 기준 | 규칙(통과 조건) | 출처 | 상태 |
|---|---|---|---|---|
| C1 | 묶음 전부 도착 | `bundles_missing` 0 | [C] | 구현 |
| C2 | 플랍 실패(재시도 뒤에도 안 풀린 보드) | 재시도 결과 ≤ 0.6 % pot 이면 받아들이고 `flop_failure_decision.json` 기록. 초과하면 그 끝점은 정적 유지(`static_nodes.json`)하고 계속 + 경고 | [U 11-08] [M] | 구현. "초과 시 멈춤" 은 설정 `flop_fail_action: stop` |
| C3 | 트리 풀이 정확 gap | < 0.02 (미만). 0.010 초과면 기록만. 반복 횟수 상한 없음 | [U 11-10] [P7] | 구현(풀이 스크립트가 이 기준으로 멈추고 판정표에 값 기록) |
| C4 | **D ≤ U** (A∪B 144보드) | **모든 자리**에서 통과. 상대가 1콤보 미만으로 오는 자리는 면제(개정 8) | [P3 ①] | 구현 |
| C5 | **A·B 복제**(값) | 모든 자리 \|V_A − V_B\| ≤ 2·√(U_A² + U_B²) | [P3 ②] | 구현 |
| C6 | 끝점 고르기 안정 | 새로 기준을 넘은 끝점의 헤즈업 도달 몫 합 ≤ 1 % (이전 단계 `bundles.tsv` 와 비교, 분모 `prepare.json` 의 `hu_mass`). 이전 단계가 없으면 알 수 없음(통과 막지 않음) | [P7] | 구현 |
| C7 | **뿌리 복제**(A만·B만 전체 트리) | 전략 차이 ≤ 5 %p 인 콤보 ≥ 95 % | [P3 ③] | 도구 없음(실제로 돌린 적 없음 [코디]). `step<k>/root_replication.json`(`{"fraction":0.97}`)이 올라오면 읽음. 없으면 "값 통과(뿌리 복제 확인 대기)"로 **그 스택을 멈추고 heartbeat 에 경고 표시** |
| C8 | 진동 끝점 감쇠 | 끝점 최대 D/U 기록 h 에서 `h[-1] > 1` 이고 `(h[-3]-h[-2])·(h[-2]-h[-1]) < 0` 이면 α = 0.25, 아니면 0.5 (`next_tables` 가 적용, 판정표는 어느 끝점이 진동인지 기록) | [C] [P3] | 구현(정보) |
| C9 | 수렴 추세 | D/U 중앙값·D≤U 자리 수·`dM_vs_prev_step` 를 단계별로 기록. **숫자 문턱 없음**(코디 확인): 자동 중단에 쓰지 않음. 최근 3단계 D/U 중앙값이 5 % 도 안 줄면 정체 경고(임시 문턱), **3단계 연속 정체 경고면 진행은 계속하되 heartbeat 에 경고** | [U 11-12] [코디] | 구현 |
| C10 | 합=팟 점검(`sum_check`) | 기록만(문턱 없음) | [M] | 기록 |
| C11 | 단계 상한 | **없음**(사용자 11-12, 코디 확인). 설정 `max_steps` 에 숫자를 넣어야만 적용 | [U 11-12] | 구현(기본 꺼짐) |
| — | 0단계는 통과 불가 | 최소 1회 갱신 뒤에만 통과로 침 | [C] | 구현 |

**판정 결과(status)**
| status | 뜻 | 봇의 행동 |
|---|---|---|
| `wait_boards` | 묶음이 덜 옴 | 기다림 |
| `continue` | 미통과 | `next_tables` → 트리 풀이 → `prepare` → 보드 순으로 다음 단계 |
| `converged` | C4·C5·C6 통과 + C7 통과 | 그 스택을 **완료**로 표시하고 멈춤(다음 스택으로) |
| `values_pass_pending_root` | C4·C5·C6 통과, C7 확인 필요 | 그 스택 멈춤 + status 에 `needs_confirmation` 경고(코디네이터가 읽고 조치) |
| `stop_report` | 플랍 실패 처리 불가(설정이 stop 일 때)·단계 상한(설정 시) | 멈추고 `needs_confirmation` 경고 |

실제 보고서로 검증: ft30 0단계 D≤U 0/58·D/U 중앙값 4.38, 1단계 5/50·3.13 (문서 8·10장 숫자와 일치), ft60 2단계 11/80·3.22·dM 중앙값 3.35 (`GTO_FT60_STEP2_RESULT.md` 와 일치).
판정표 보기: `python3 autopilot.py judge 30 1` (깃허브 조정 브랜치를 읽음) 또는 `judge.py <report.json>`. 단계가 판정될 때마다 `data/ft<스택>/step<k>/judge.json·judge.md` 로 조정 브랜치에 남긴다.

## 3. 단계 흐름과 누가 하나
한 단계 = 표 → 트리 풀이(solve) → prepare(끝점·묶음·assign.tsv) → 보드(묶음 A/B 패널 72보드) → collect → 판정 → next_tables → 다음 단계 표.
봇은 스택마다 **조정 브랜치의 파일만** 보고 지금 어느 단계인지 정한다.

| 조정 브랜치에 있는 것 | 지금 단계(phase) | 하는 일 |
|---|---|---|
| `step<k>/tables/manifest.json` 만 | solve | `ft_solve.sh k` (정확 gap < 0.02 까지, **처음부터**) → `solve/`·`convergence.json` 올림 |
| `solve/final_n`+`dump.jsonl.gz`, prepare 없음 | prepare | `ft60.py prepare k` + `used_gross.jsonl.gz`·`terminals_mass.json.gz` 올림 (체크포인트가 연구실에 없으면 풀이를 다시 함) |
| `bundles.tsv`·`assign.tsv`·`prepare.json` | boards | 보드 번호별로 아래 4장 규칙으로 계산 |
| 모든 묶음에 `done.json` | collect | `ft60.py collect k` → `collect/report.json`, 판정 `judge.json`, 보드 시간 실측(`step<k>_board_hours.json`) 올림 |
| `collect/report.json`(완료) + 판정 continue | next_tables | `ft60.py next_tables k` → `step<k+1>/tables/`·`history.json` 올림 |
| 판정 converged / 확인 대기 / 멈춤 | halted | 그 스택은 더 안 함 |

**이미 있으면 하지 않는다**(규칙 d): 단계 결과가 조정 브랜치에 이미 있으면 그 단계는 건너뛴다. 조정 브랜치의 마지막 푸시가 4시간(`coord_idle_hours`) 안이면 조정 세션이 작업 중일 수 있어 조정 단계는 시작하지 않는다. 조정 단계도 claim 을 먼저 잡는다. `next_tables` 는 `history.json` 에 덧붙이는 방식이라 실패하면 되돌리고, 같은 조정 일은 6시간 안에 반복하지 않는다.
조정 단계는 설정 `coord_actions: true` 인 스택(기본 30 만)에서만 한다. 다른 스택은 **보드만 돕는다**.

**도구 버전(코디 지시 11-26)**: 최신 도구 = `claude/ft60_3way_s5` 의 `tools/gto_fulltree`(행렬 끝점 `FT_MATRIX_ALL=1`, `FT_PANEL_SET`, `FT_REPLACE`, 보드 시간 실측 `FT_BOARD_HOURS`)를 기준으로 하고, 스택 조정 브랜치의 도구가 더 새로우면(= 필요한 기능이 이미 다 있으면) 그것을 따른다. ft30 조정 브랜치는 구버전이라, 첫 조정 일에서 같은 푸시에 (1) 도구 덮어쓰기(+ ft100_coord 방식 `FT_MIN_REACH` 3줄: ft60_3way_s5 에는 없음) (2) 균형 패널 `panel_bal_A72/B72.json` 을 `data/ft30/panels/` 로 복사를 넣는다.
**30bb 는 2단계부터 `FT_PANEL_SET=bal`**(1단계를 다시 모을 때는 prec), `FT_REPLACE` 는 쓰지 않는다(혼합 α 그대로). **세 명 끝점 표(`ft60_add3way.py`)는 넣지 않는다**: 설정 `three_way_tables: false`(사용자 승인 뒤 켜기 — 켜는 코드는 아직 없고, 승인되면 코디가 추가). 풀이·내보내기 바이너리는 도구(패치·소스)가 바뀌면 `ft_coord_setup.sh` 로 다시 빌드한다.

## 4. 깃허브 공용 작업판 (겹치지 않게)
(a) **읽기**: 스택마다 조정 브랜치(`claude/ft<S>_coord`)에서 단계·`assign.tsv`·묶음 목록을 읽고, `claude/ft<S>_board_<n>` 에서 묶음별 `done.json`(끝남)/그 밖 결과 파일(부분)/없음을 읽는다. `git ls-remote` 로 브랜치 sha 가 바뀐 것만 얕게(`--depth=1 --filter=blob:none`) 가져온다. 읽기 전용 저장소(`~/t2lab/peek`)를 따로 써서 사용자 저장소의 이력을 건드리지 않는다.

(b) **claim**: 보드 번호 하나(= 그 번호의 묶음 전부)를 시작하기 전에 `claude/ft_claims` 브랜치에 파일 하나를 푸시한다.
- 파일: `claims/ft<스택>/step<단계>/board_<n>.json` (조정 단계는 `coord_solve|coord_prepare|coord_collect|coord_next_tables`) — `{"owner","host","t_claim","t_heartbeat","note"}`
- 같은 부모에서 푸시 경쟁이 나면 **나중 푸시가 거절**된다 → 다시 읽어서 파일이 이미 있으면 진 것. 원자성은 git 푸시 거절로 확보(force 없음). 시험: 3개 프로세스 동시 → 정확히 1개 성공.
- 일하는 동안 30분마다 `t_heartbeat` 갱신. 하트비트가 `claim_ttl_hours`(3시간)보다 오래되면 죽은 claim 으로 보고 인계 가능. 끝나거나 실패하면 파일을 지운다(release).
- 다른 계정·클라우드 세션도 같은 방식으로 쓸 수 있다: `python3 tools/gto_fulltree/lab_autopilot/autopilot.py claim 30 1 board_7 --owner <이름>` (성공 시 `CLAIM_OK`, 이미 잡혔으면 종료코드 3 `CLAIM_TAKEN`), 끝나면 `release`.

(c) **건너뛰는 규칙**(보드 번호 n 마다; **판단은 묶음 단위** — 묶음이 `assign.tsv` 의 번호가 아니라 다른 보드 브랜치(`…_board_4b`, 21 등)로 재배정돼 끝났거나 진행 중이어도 모든 `claude/ft<S>_board_*` 에서 그 묶음의 `done.json`·최근 푸시를 보고 건너뜀. 봇이 일하는 중에도 묶음마다 다시 확인. 조정 대기 판단(마지막 푸시 4시간)에서는 봇 자신의 커밋은 뺌):
| 상태 | 연구실 행동 |
|---|---|
| 모든 묶음 `done.json` 있음 | 건너뜀(끝남) |
| 다른 쪽 claim 이 하트비트 3시간 안 | 건너뜀 |
| 그 브랜치에 다른 쪽이 3시간(`active_hours`) 안에 푸시 | 건너뜀(작업 중) |
| 부분 푸시/일부 끝남이 있고 내 것이 아님 | 건너뜀. 마지막 푸시가 24시간(`stale_takeover_hours`) 넘게 멈췄으면 인계(그 브랜치를 이어서, 끝난 12보드 덩어리는 건너뜀) |
| 이 단계 결과가 없음(브랜치가 없거나 옛 단계 흔적만) | 새로 시작 |
| 내 것(내 claim 또는 내 작업 폴더가 있는 브랜치) | 이어서 |

(d) **우선순위**: 스택 우선순위 순(기본 30 → 40 → 60 → 100). 30bb 에 연구실이 잡을 보드·조정 일이 없으면(끝났거나 모두 남이 잡음/막힘) 자동으로 다음 스택의 "아무도 안 잡은 보드"를 돕는다. 스택별 허용 여부는 `config.json` 의 `stacks.<S>.enabled/boards/coord_actions`(원격 명령으로도 바꿈). 잡을 일이 없으면 30분 뒤 다시 확인.
**주의**: 아직 claim 을 모르는 클라우드 세션이 같은 번호를 막 시작했다면(첫 푸시 전 약 1시간) 겹칠 수 있다. 결과는 같은 입력·같은 절차라 어느 쪽이 먼저 올려도 같은 값이고, 보드 세션이 새로 열릴 때 위 claim 명령을 먼저 쓰도록 코디네이터가 알려 주면 완전히 막힌다.

## 5. CPU·디스크·무인 운영
- **CPU 6코어만**: 보드 2개 × 워커 3개(`SPOT_PANEL_WORKERS=3`, `RAYON_NUM_THREADS=1`) = 6. 조정 계산(풀이·prepare·collect)은 코어 3개(`RAYON_NUM_THREADS=3`)로 보드 1개와 함께(3+3). 모든 계산은 `nice -n 19` + (WSL 에서 되는지 시험해서 되면) `ionice -c3`. 컴파일도 같은 낮은 우선순위. ft_board 가 못 맞춘 보드를 한꺼번에 최대 12개 재시도하는 것은 `board_run.py` 가 3개씩으로 제한한다(ft_board.py 수정 없음).
- **메모리**: 보드 워커 1개 약 8 % × 3 × 2 — 35GB 안. 여유가 3GB 아래면 새 일 시작 안 함.
- **재시도**: 계산이 죽으면 같은 명령으로 이어서(끝난 12보드 덩어리는 푸시돼 있음). 보드 하나가 5번 연속 실패하면 그 일을 5분→15분→1시간→3시간→12시간 간격으로 다시 시도(`input sha256 differs` 면 코디 확인 대기 표시). 봇 자체가 죽어도 `lab_autopilot.sh run` 이 30초 뒤 다시 시작하고, 시작할 때 이전 실행이 남긴 계산을 정리한다.
- **디스크 정리**: 푸시가 끝난 묶음의 보드 원본 폴더 삭제, 단계 지난 `collect_s*`(최근 2개만 유지)·오래된 체크포인트 삭제, 로그 50MB 넘으면 자름, 디스크 여유가 15GB 아래면 새 일 시작 안 하고 정리.
- **부팅 후 자동 시작**: Windows 작업 스케줄러(아래 8장). WSL 1 은 창이 닫히면 꺼지므로 `wsl.exe` 가 `run` 을 계속 붙잡고 있는 방식이다(10분마다 같은 명령을 한 번 더 걸어도 잠금 때문에 하나만 돈다).
- 커밋 이름 `t2-lab`. force push·PR·master/test3 수정 없음. 푸시 대상: 보드 브랜치(결과, 기존 방식), `claude/ft_claims`, `claude/lab_status`, (조정 단계) 스택 조정 브랜치 — 일반 푸시만, 거절되면 병합 후 다시, 충돌이면 중단·보고.

## 6. 오류 인식과 보고 (코디네이터용)
봇이 스스로 이상을 알아채서 `claude/lab_status` 브랜치의 **`status.json`**(+ 읽기 쉬운 `status.md`, 로그 `log_tail.txt`)을 올린다. **코디네이터 판별 규칙: `status != "ok"` 이면 오류/주의 있음 → `alerts` 를 읽는다.**
`status` 값: `ok`(경고 없음) / `warn`(주의: 확인 필요·정체·일시 오류) / `error`(조치 필요: 멈춤·반복 실패·디스크 부족·업데이트 실패).

**푸시 규칙**: 경고 구성이 바뀌면 바로(최소 5분 간격), 오류가 없을 때는 **6시간마다 짧은 heartbeat**(`heartbeat_hours`), 같은 오류가 계속되면 6시간마다만 다시(중복 푸시 줄임). 같은 (코드, 대상) 경고는 한 건으로 합치고 `count` 만 늘린다.

**`status.json` 형식** (`schema: lab_status_v1`)
```
{ "status": "ok|warn|error", "time": "...Z", "host", "owner", "uptime_h", "mode": "live|dry|no_push",
  "code_release": "<현재 봇 코드 sha 앞 10자리>", "update": {"pending": "<sha>|null", "failed": {sha,t,err}|null},
  "cpu": {budget,in_use,load}, "mem_avail_gb", "disk_free_gb", "paused": {"all":bool,"stacks":[..]},
  "jobs": [ {stack, step, unit, started, progress, cpu_idle_min, file_idle_min} ],
  "stacks": { "30": {phase, why, step, coord_tip_age_h, stall_streak, boards:{n:{done,bundles,tip_age_h,claim}}, verdict:{step,status,reasons,warnings,pass_D_le_U,dou_median,dM_vs_prev_median,needs_confirmation}} },
  "alerts": [ {code, severity: warn|error, key, msg, since, last, count, ctx, log_file, log_tail:[마지막 200줄]} ],
  "recent_errors": [..], "control": {applied:{id:{t,cmd,ok,msg}}, skip, priority, cfg_overrides, stack_overrides}, "blocked": {...} }
```
**경고 코드(최소 분류)**
| 코드 | 뜻 | 심각도 |
|---|---|---|
| `bot_restarted` / `bot_restart_loop` | 봇이 비정상 종료 후 다시 시작됨 / 1시간에 3번 넘게 다시 시작(프로세스 죽음·재시작 실패) | warn / error |
| `process_dead` | 계산 프로세스가 신호로 죽음 | warn→error(3번째) |
| `no_progress` | **실제 계산 프로세스(프로세스 그룹 전체의 CPU 시간)가 N시간 동안 안 늘음** → 프로세스를 끄고 다시 시작(error). 또는 CPU 는 쓰는데 결과 파일이 N시간 안 늘음(warn). N = 묶음 덩어리(12보드) 예상 시간 × 2(직전 단계 실측 중앙값 ÷ 6 × 2, 최소 2시간; 조정 계산 4시간). `solve_panel` 같은 이름이 아니라 CPU 로 판단 | error / warn |
| `solver_rc` | 솔버·ft_board 가 비정상 종료코드/미완료로 끝남(재시도 중) | warn→error(3번째) |
| `flop_over_limit` | 재시도 뒤에도 0.6 % pot 초과 플랍(그 끝점 정적 유지) | warn |
| `push_failed` / `fetch_failed` / `push_failed_status` | 결과·조정 브랜치 푸시 실패 5번 / 깃허브 읽기 3번 연속 실패 / 상태 푸시 3번 연속 실패 | warn·error |
| `input_changed` | 입력 sha 불일치(옛 입력으로 안 풂) — 코디 확인 | error |
| `merge_conflict`·`coord_failed` | 조정 브랜치 병합 충돌, 조정 일(collect·solve 등) 실패 | error |
| `disk_low` / `mem_low` | 디스크 15GB·메모리 3GB 미만 → 새 일 중지 | error |
| `needs_confirmation` | 판정이 `값 통과(뿌리 복제 확인 대기)` 또는 멈춤 — **코디가 조치할 것** | warn |
| `stall_streak` | 정체 경고 3단계 연속(진행은 계속) | warn |
| `update_failed` | 봇 코드 새 버전이 자체 점검에 실패해 이전 버전 유지 | error |
| `paused` | 원격 명령으로 일시정지 중 | warn |
| `control_invalid` | `control.json` 이 JSON 이 아님 | warn |
사용자 요청대로 **코디네이터에게 직접 send_message 는 보내지 않는다**(봇에는 Claude 연결이 없음). 코디네이터가 정기 확인으로 `status.json` 만 읽으면 된다:
`git fetch origin claude/lab_status && git show origin/claude/lab_status:status.json`

## 7. 원격 수정·원격 명령 (깃허브만)
**자체 업데이트**(`claude/lab_autopilot` 에 코디네이터가 고쳐서 푸시하면):
1. 봇이 5분마다 이 브랜치를 fetch → 새 커밋이면 `~/t2lab/releases/<sha10>/` 에 **별도 폴더로** 받는다(현재 코드는 그대로).
2. **자체 점검**(`autopilot.py selfcheck`): 파이썬 문법, 시작 스크립트 문법, 판정 함수가 저장소의 실제 ft30 1단계 보고서로 문서 숫자(5/50, 3.13)를 재현하는지, 드라이런(깃허브를 읽어 계획까지)을 통과해야 한다.
3. 통과하면 **진행 중인 계산을 끊지 않고** 다음 묶음 경계(보드는 묶음 하나씩 실행하므로 한 묶음이 끝날 때)에서 `current` 링크를 새 릴리스로 바꾸고 다시 시작한다(최대 12시간 기다려도 안 끝나면 강제). 새 일은 교체 예약 중에 시작하지 않는다.
4. 실패하면 **이전 버전을 유지**하고 `update_failed` 경고(error)를 올린다. 같은 커밋은 다시 안 시도한다(새 커밋이 오면 다시).
이 브랜치에 푸시하는 사람은 봇 코드를 바꿀 수 있다는 뜻이다(깃허브 쓰기 권한이 곧 연구실 제어 권한).

**원격 명령**: 코디네이터가 `claude/lab_status` 브랜치 루트에 `control.json` 을 올리면 봇이 5분마다 읽고 처리한다. 봇은 이 파일을 쓰지 않는다. 같은 `id` 는 한 번만 처리한다(id 없으면 `seq:번호`). 처리 결과는 `status.json` 의 `control.applied` 에 남는다.
```
{"seq": 3, "commands": [
  {"id": "c1", "cmd": "pause"},                                    // 새 일 시작 중지(진행 중은 계속). "stack":"60" 이면 그 스택만
  {"id": "c2", "cmd": "resume"},
  {"id": "c3", "cmd": "skip",   "stack": "30", "unit": "board_7"}, // 그 단위를 건너뜀(실행 중이면 취소). "step" 생략 = 모든 단계
  {"id": "c4", "cmd": "cancel", "stack": "30", "unit": "board_7"}, // 실행 중인 것만 취소(건너뜀 등록은 안 함)
  {"id": "c5", "cmd": "retry",  "stack": "30", "unit": "board_7"}, // 실패·대기·건너뜀 기록 지움(stack/unit 생략 가능)
  {"id": "c6", "cmd": "priority", "order": ["60", "30"]},          // 스택 우선순위
  {"id": "c7", "cmd": "stack", "stack": "60", "enabled": false},   // enabled / boards / coord_actions
  {"id": "c8", "cmd": "config", "path": "cpu.boards_parallel", "value": 1},
  {"id": "c9", "cmd": "restart"}                                    // 일이 끝나면 봇 다시 시작
]}
```
`config` 로 바꿀 수 있는 것: `cpu.boards_parallel, cpu.workers_per_board, cpu.coord_threads, loop.no_progress_min_hours, loop.no_progress_coord_hours, loop.active_hours, loop.stale_takeover_hours, loop.coord_idle_hours, loop.heartbeat_hours`. 그 밖 경로·모르는 명령은 거절하고 `ok:false` 로 기록.
(코디네이터가 `control.json` 을 올리는 법: `git clone -b claude/lab_status <원격> x && cd x && (control.json 쓰기) && git add control.json && git commit -m control && git push origin HEAD`. 같은 브랜치에 봇도 푸시하므로 거절되면 `git pull --rebase` 후 다시.)

## 8. 설치·시작·상태 (사용자가 연구실 cmd 에 붙여넣기)
**설치+시작(한 덩어리, cmd)** — 봇 코드 받기(`~/t2lab/releases/<sha>` + `current` 링크) → 준비 점검(예전 lab_ft.sh 가 돌고 있으면 멈춤) → 로그인 때·10분마다 시작하는 작업 등록 → 절전 끄기 → 지금 시작:
```
wsl -d Ubuntu-22.04 -u user -- bash -lc "cd /home/user/t2 && git fetch -q origin claude/lab_autopilot && git show origin/claude/lab_autopilot:tools/gto_fulltree/lab_autopilot/lab_autopilot.sh | bash -s install" && schtasks /Create /F /TN T2LabAutopilot /SC ONLOGON /TR "wsl.exe -d Ubuntu-22.04 -u user -- bash -lc 'bash /home/user/t2lab/current/tools/gto_fulltree/lab_autopilot/lab_autopilot.sh run'" && schtasks /Create /F /TN T2LabAutopilotKeep /SC MINUTE /MO 10 /TR "wsl.exe -d Ubuntu-22.04 -u user -- bash -lc 'bash /home/user/t2lab/current/tools/gto_fulltree/lab_autopilot/lab_autopilot.sh run'" && powercfg /change standby-timeout-ac 0 && schtasks /Run /TN T2LabAutopilot
```
- 이 PC 가 재부팅 뒤 **로그인 없이** 바로 돌아야 하면: Windows 자동 로그인을 켜 두거나(`netplwiz`), 두 `schtasks /Create` 뒤에 `/RU <사용자> /RP <비밀번호>` 를 붙여 "로그온 여부와 관계없이" 로 등록한다(**확인 필요 NC-5**: 이 PC 설정을 몰라서 기본은 로그인 필요).
- 설치는 처음 한 번 계산 체크아웃이 없을 때만 10~20분 걸린다(이미 `/home/user/calc` 가 있으면 건너뜀). 조정 계산(풀이·내보내기)용 빌드는 첫 조정 일에서 자동으로 한다.
- 시험만 해 보려면(푸시·계산 없이 "지금 할 일" 보기): `wsl -d Ubuntu-22.04 -u user -- bash -lc "bash /home/user/t2lab/current/tools/gto_fulltree/lab_autopilot/lab_autopilot.sh once"`

**상태 확인(cmd)**
```
wsl -d Ubuntu-22.04 -u user -- bash -lc "bash /home/user/t2lab/current/tools/gto_fulltree/lab_autopilot/lab_autopilot.sh status"
```
로그: 같은 명령에서 `status` 대신 `logs`. **멈춤**: `stop` (다시 시작은 작업 스케줄러가 10분 안에 하므로 완전히 끄려면 `schtasks /Delete /F /TN T2LabAutopilot` 와 `... T2LabAutopilotKeep` 도).

## 9. 설정 (`config.json`, 바꿀 때는 `~/t2lab/config.local.json` 에 바꿀 것만)
코어 수·보드 수·워커 수·nice, 스택별 `enabled / priority / boards / coord_actions / coord_branch / coord_push_branch / cfg_file / tools_ref / tools_markers / panel_set_from_step / copy_panels / three_way_tables / solve_env / prepare_env / judge`, 시간 문턱(`claim_ttl_hours 3`, `active_hours 3`, `stale_takeover_hours 24`, `coord_idle_hours 4`, `heartbeat_hours 6`, `no_progress_min_hours 2`), 디스크·메모리(`min_free_gb 15`, `min_free_mem_gb 3`), 판정 문턱(`judge.*`).
ft30 기본: `FT_MIN_REACH=1e-3`, `FT_SESSIONS=20`, `FT_MATRIX_ALL=1`, 풀이 `FT_GAP_TARGET=0.02 FT_GATE=0.024`, 2단계부터 bal 패널. 배분 시간 추정(`FT_BOARD_HOURS`/`FT_H_*`)은 직전 단계 보드 실측(묶음당 약 5시간)으로 봇이 갱신한다.

## 10. 시험 결과 (2026-11-26, 이 컨테이너)
`python3 tools/gto_fulltree/lab_autopilot/test_autopilot.py` (가짜 origin, 계산기 불필요):
- 판정: 실제 ft30 0·1단계 보고서 숫자 일치, 가짜 전부 통과 → `values_pass_pending_root`, 뿌리 복제 97 % → `converged`, 90 % → 아님, 플랍 실패 0.43 % → 수용 / 0.9 % → 정적 유지, 진동 식.
- 공용 작업판: 끝남/남이 방금 푸시/40시간 멈춤(인계)/일부 끝남/옛 단계 흔적/방금 시작된 보드를 의도대로 구분, claim 3개 동시 → 1개만 성공, 남의 claim 보드는 계획에서 빠짐.
- 오류 보고: 경고 없으면 `ok`, 경고 있으면 `warn/error` + 로그 꼬리 200줄, 같은 경고 반복은 한 건(count), 같은 오류 중복 푸시 안 함, 경고가 바뀌면 바로 푸시, 오류 없을 때 6시간 heartbeat.
- 원격 명령: pause/skip/priority/config/retry/resume 처리, 허용 안 된 설정·모르는 명령은 실패 기록, 같은 id 재처리 안 함.
- 감시: CPU 를 안 쓰는 프로세스 그룹 → `no_progress` 경고 + 종료.
- 도구 갱신: 구버전 coord 도구 → 최신 도구 기준으로 덮어쓰기 + `FT_MIN_REACH` 패치 + 균형 패널 복사 + 패널 세트(2단계부터 bal), 덮어쓴 `ft60.py` 문법 정상.
- 자체 점검: 정상 새 버전 통과, 문법이 깨진 새 버전은 실패(교체 안 됨).
- **실제 계산기**(`/home/user/calc` 빌드 후): 보드 일 하나(ft30 1단계 보드 20번, `FT_TEST_BOARDS=2`, `FT_NO_PUSH=1`, 워커 3, nice 19 + ionice)로 묶음 3개(행렬 끝점 포함) 정상 완료(약 10분, `done.json`·`values.json.gz`·`matrix_sums.npz` 생성, 작업 폴더 정리). 이 시험에서 발견·수정한 것: 연구실 계산 체크아웃(`ft_board_setup.sh` 의 sparse 목록)에 `data/gto_spot/plan_a`(설정 파일)가 없어 풀이·prepare 가 실패 → 봇이 첫 조정 일에서 자동으로 추가.
- 풀이(`ft_solve.sh`) 연결(설정 파일 경로·표 manifest·낮은 우선순위·코어 3개)은 실제로 시작되는 것까지 확인했다(30bb 1단계 표로 50회 시험). **2시간 넘는 전체 풀이·prepare·collect 는 이 컨테이너에서 끝까지 돌리지 못했다**(첫 실제 조정 일에서 로그를 봐야 함).

## 11. 아직 확인 필요 (코디네이터 답 반영)
| 번호 | 내용 | 상태 |
|---|---|---|
| NC-1 | 뿌리 복제(③) | 코디 답: 실제로 돌린 적 없음 → 기본대로 "값 통과 시 멈춤+경고". 도구가 생기면 `root_replication.json` 로 연결 |
| NC-2 | 수렴 숫자 문턱 | 코디 답: 문턱 없음 → 기록·정체 경고만, 단계 상한 없음. 3단계 연속 정체 경고는 heartbeat 경고(구현) |
| NC-3 | 도구 버전 | 코디 답: `claude/ft60_3way_s5` 기준(스택 조정 도구가 더 새로우면 그것). 구현(3장). 단, 이 도구의 `prepare` 는 끝점을 상위 40개로 고정하므로 ft30 의 `FT_MIN_REACH=1e-3`(25개)를 위해 3줄 패치를 같이 넣는다 — **코디가 확인해 줄 것**(없애면 ft30 2단계는 끝점 40개·묶음 80개) |
| NC-4 | 조정 결과 푸시 위치 | 코디 답: 해당 coord 브랜치에 일반 푸시(충돌 시 merge, force 금지) + claim |
| NC-5 | 로그인 없이 부팅만으로 시작? | 사용자에게 확인 필요(8장) |
| NC-6 | 풀이 체크포인트 | 코디 답: 처음부터 정확 gap<0.02 로 OK |
| NC-7 | 세 명 끝점 표 | 코디 답: 아직 넣지 않음(설정 off) |
