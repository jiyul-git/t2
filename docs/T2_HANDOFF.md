# T2 이어받기 매뉴얼 (봇 판단 검증 · GTO 연결 · 화면)

새 세션이 이 문서만 읽고 이어서 일할 수 있게 쓴다. 마지막 갱신: 2026-10-24(연결: 3벳 받은 오프너·SB 림프·BB 플랫콜 새 자리).
작성: T2 봇 판단 검증 세션(session_01XV9GKUYpuxdA2ckcjg1qsv). 2026-10-24 갱신: 코디네이터 세션(session_012qfUk9MsH6Hp2gBX6Q18sA,
T2 세션이 사용량 한도로 멈춘 동안 사용자 승인으로 연결을 맡음). 연결 검사 결과: `docs/GTO_CONNECT_QUICK_REPORT_20261024.md`.

---

## 0. 먼저 지킬 것 (사용자 규칙)

- 답은 **한국어**, 짧게, 전문용어 없이. 그림은 **PNG**로만 보낸다(SVG 파일 금지).
- 풀이·계산은 정답에 맞춰 거꾸로 맞추지 않는다. 결과가 다르면 다르다고 말한다.
- **master(배포)는 사용자 승인 후에만.** test3 가 시험 배포 브랜치다. force push 금지.
- 커밋 메시지에 모델 이름을 넣지 않는다. 끝줄은 `Co-Authored-By: ...` / `Claude-Session: ...`(세션 안내를 따른다).
- master 에 올리기 전에는 **화면(UI)·게이트웨이 검사도 같이** 돌린다(사용자 지적: "UI 도 확인했어야지").
- 사용자에게 Termux 명령을 줄 때는 **한 덩어리로 붙여넣을 수 있게** 준다(6장).
- 사용자 계정의 칩·개인정보는 출시 전 초기화돼도 된다. **버전 관리만** 신경 쓴다.
- GTO 계산 데이터를 봇에 붙이는 것은 사용자 승인 사항이다. 지금까지 승인된 범위는 3장.

## 1. 지도: 브랜치와 세션

| 이름 | 역할 |
|---|---|
| `master` | 배포. 지금 `27d0424b` (GTO 10~40bb 올인·3벳 연결까지). test3 보다 많이 뒤처져 있다 |
| `test3` | 시험 배포. 사용자가 Termux 서버로 이것을 돌린다. 이 문서의 모든 작업이 여기 있다 |
| `claude/pushfold-10-25-20261019` | 10/15/20/25bb 푸시/폴드 기록(pf10~25) + 30/40bb 부모 트리(s30, s40) |
| `claude/p30-flat-20261019` | 30bb 플랫콜 루프 기록. **Gto제작2 세션**(session_011TJwxsbnvbQgF3L3dSFKFd)이 돌린다 |
| `chatgpt/terminal-census-v2-20260930` | 40bb 플랫콜 루프 + 60bb(s60) + 계산 표준 문서 + `docs/GTO_SESSIONS_BOARD.md`(계산 세션 게시판). **Gto제작1 세션**(session_01BLRHV14gJtnk3f8cLagcNs) |
| `ccr-fb71f1d0-3wvj9e` | **코디네이터 세션**(session_012qfUk9…, 다른 계정)의 브랜치: 기록 안내 `docs/GTO_RESULTS_FOR_T2_20261024.md`, 진동 분석 문서 |
| `claude/archive-gto-runs-20261024` | **끝난 계산 브랜치 17개 보관**(2026-10-24). 커밋 하나의 부모가 각 브랜치의 마지막 커밋 — 단계별 백업 tar·state·덤프 조각이 정밀 검사(P144 등)용으로 그대로 있다. 목록·되살리는 법은 `ARCHIVE.md` |
| `claude/p40_flat_utg2_20261024`, `claude/p100_parent_20261024`, `claude/open_sizes_20261024`, `claude/icm_pushfold_20261024` | 진행 중(10-24): 40bb UTG+2 플랫콜, 100bb 부모, 오픈 2.0/2.5 부모(40·30bb), ICM 푸시/폴드 계획·파일럿(끝남, 사용자 결정 대기) |

- 계산 세션들은 계산만 한다. 봇에 붙이는 일(연결)은 이 문서의 담당(T2 세션)이 한다.
- **연결에 쓰는 기록은 test3 안의 사본 `data/gto_records/*.json.gz`**(출처표 `MANIFEST.tsv`). 계산 브랜치가 지워져도 연결이 깨지지 않는다.
- 이 계정과 다른 계정의 세션 사이에는 `send_message` 가 닿지 않는다. 그럴 때는 브랜치의 문서로 주고받는다.
- 계산 세션에 일을 맡길 때는 `send_message` 로 보낸다(사용자: "둘 다 그냥 너가 보내").
- 계산 표준·결정 이력은 census 브랜치의 `docs/GTO_SESSIONS_BOARD.md` 가 원본이다.

## 2. GTO 기준 연결 구조

### 2.1 파일
| 파일 | 하는 일 |
|---|---|
| `gto_pf.py` | 기준 데이터 조회. 버킷 사이 직선 보간, ±0.25bb 경계, 6~9인 → 9인 자리 변환, 노안테·범위 밖은 None |
| `gto_pf_data.json` | 기준 데이터(실행 폴더에 평평하게 복사된다). `tools/gto_pf_build.py` 가 만든다 |
| `tools/gto_pf_build.py` | 계산 기록 → `gto_pf_data.json` |
| `data/gto_records/` | 연결에 쓰는 기록 사본(압축) + `MANIFEST.tsv`(파일별 sha256, 브랜치별 커밋). `refresh_records.sh` 가 만든다 |
| `tools/t2_handoff/verify_gto_connect.py` | 연결 검사(값 일치·실제 엔진 경로·경로 선택·실패 내성). 4장 |
| `preflop.py` | 연결 지점(아래 2.3). `T2_GTO_PF=0` 이면 전부 끔. 모듈·데이터가 없으면 None(기존 판단) |
| `plan.py` `preflop_plan` | 연결 결과를 실제 행동으로 바꿈 |
| `session.py` | `pf_other_live_actors`, `pf_actor_acted`, `pf_aggressor_total_bb` 계산(공개 행동 기록 `action_meta`) |
| 실행 폴더 목록 | `ui/tools/setup_run_dir.sh`, `ui/tools/setup_run_dir.py`, `install_game.py` STATIC_DATA, `verify_fresh_install_startup.py` — **새 모듈·데이터는 네 곳 모두에 넣는다**(빠뜨려서 게이트웨이 서버가 죽은 적 있음, 27d0424b) |

### 2.2 데이터 표 (`gto_pf_data.json`)
| 표 | 내용 | 기록 |
|---|---|---|
| `first_in` | 첫 진입 jam/open/limp 빈도 (SB 는 림프가 있는 30bb 이상에서 뺌) | pf10~25, s30, s40, s60, s100 |
| `vs_jam` | 단독 올인에 콜 | pf10~25 |
| `vs_3bjam` | 오픈 후 3벳 올인에 콜 | pf15~s60 |
| `vs_open` | 단독 오픈에 대한 공격(3벳·3벳 올인)만 | pf15~s100 |
| `vs_3bet` | 3벳 받은 오프너의 4벳 올인 | s30~s60 |
| `vs_open_full` | **플랫콜 루프로 보정된 자리**: 단독 오픈을 받은 BB 의 폴드·콜·3벳·올인 전체 + 오픈 크기(`open_bb`) | p30/p40_flat_*_vs_bb |
| `vs_open_full_o25` | 같은 수비를 **오픈 2.5bb** 로 푼 기록(10-25). 실제 오픈 2.0~2.5 는 두 표 직선 보간, 2.5~3.125 는 이 표, 이 표가 없는 스택은 2.0 표만 | p30/p40_flat_*_vs_bb_o25 (`claude/flat_open25_20261025`; 지금 p40 BTN·CO, 30bb 계산 중) |
| `vs_3bet_full` | **3벳 받은 오프너**의 폴드·콜·작은 4벳(`r4`)·올인 전체 + 3벳 크기(`threebet_bb`), 4벳 크기. 기록에 없는 클래스(그 오프너가 오픈하지 않는 패)는 null → 기존 판단 | p30/p40v1_*_vs_* (10-24) |
| `vs_limp_full` | **SB 림프를 받은 BB** 의 체크·레이즈(3.5bb) + 불안정 몫(`unstable_share`) | p30/p40_flat_sb_limp_vs_bb (CFR+ 재시도 기록, 10-24) |

- 공격자 콤보 < 10 인 노드는 뺀다(거의 안 쓰는 올인).
- 버킷: 10, 15, 20, 25, 30, 40, 60, 100bb. 3벳 받은 4벳 올인(`vs_3bet`)은 100bb 트리에 작은 4벳이 있어 비운다 → 60bb 초과는 기존 판단. 유효 스택 = 핸드 시작 기준, 상대와의 작은 쪽.

### 2.3 연결 지점 (preflop.py)
| 함수 | 상황 | 막는 조건 |
|---|---|---|
| `gto_pf_first_in_choice` | 첫 진입 | ICM 압력(BF > 1.05 또는 머니점프 pressure/brake/위험 몫), 범위 밖 |
| `gto_pf_call_choice` | 단독 올인 콜, 내가 오픈 후 3벳 올인 콜 | 콜러가 낀 팟, 행동 여부 모름 |
| `gto_pf_aggr_choice` | 오픈 받음(3벳/3벳 올인), 3벳 받음(4벳 올인). 보정된 자리는 콜·폴드까지. **3벳 받은 오프너 중 기록이 있는 짝은 폴드·콜·작은 4벳·올인**(`'4bet'` = 3벳 크기 × reraise_mult(2): IP 2.15 / OOP 2.35, 계산기 메뉴와 같음) | 위와 같음 + 3벳 크기가 기록의 0.9~1.25배 밖 |
| `gto_pf_limp_choice` (10-24) | SB 가 림프하고 나머지 전원 폴드, BB 차례: 체크 / 레이즈 3.5bb | BB 아님, 림퍼가 SB 한 명이 아님, 다른 사람이 돈을 넣음, 체크 불가, ICM 압력, 유효 스택(둘 중 작은 쪽) 범위 밖 |

- 기준 범위 안에서 봇이 오픈할 때는 **계산기와 같은 크기(2.0bb, SB 3.0bb)** 로 친다(사용자 결정 10-20).
- 보정된 자리(`vs_open_full`)는 실제 오픈 크기가 기록 크기의 0.9~1.25배일 때만 쓴다.
- 플랫콜 기록의 3벳은 크기 두 개(7·8bb)를 합쳐 빈도만 연결한다. 크기는 봇 습관(3.7배 = 7.4bb). 40bb UTG+1 오픈 vs BB 의
  KK·AA 처럼 계산기가 8bb 를 고르는 패도 봇은 대부분 7bb 로 친다(연결 검사 size_split 에 기록).
- 버킷 사이는 양쪽 기록이 모두 있어야 쓴다. 한쪽만 있는 자리는 그 버킷 ±0.25bb 에서만 쓰인다(10-24 UTG+2 40bb 연결로 30~40bb BB 수비는 전 자리 양쪽 있음).

## 3. 연결 현황 (2026-10-24)

| 상황 | 10~25bb | 30bb | 40bb | 60bb | 100bb(10-24) |
|---|---|---|---|---|---|
| 첫 진입(SB 제외) | ✅ | ✅ | ✅ | ✅ | ✅ |
| SB 첫 진입 | ✅(림프 없는 트리) | ✗ 기존 판단 | ✗ | ✗ | ✗ |
| 올인 콜 / 3벳 올인 콜 | ✅ | ✅ | ✅ | ✅(데이터 적음) | ✗(데이터 없음) |
| 오픈 받은 공격(3벳·3벳 올인) | ✅(15~) | ✅ | ✅ | ✅ | ✅ |
| 3벳 받은 4벳 올인 | – | ✅ | ✅ | ✅(작은 4벳 없음) | ✗ 기존 판단(60bb 초과 전부) |
| **BB 플랫콜 수비(보정)** | – | UTG·UTG+1·UTG+2·LJ·HJ·CO·BTN·SB | UTG·UTG+1·UTG+2·LJ·HJ·CO·BTN·SB (UTG+2 10-24 연결) | ✗ | ✗ |
| **3벳 받은 오프너(폴드·콜·작은 4벳·올인)** | – | CO·UTG+1 vs SB, UTG vs BTN | 같음 | ✗ | ✗ |
| **SB 림프 받은 BB(체크·레이즈)** | – | ✅ | ✅ | ✗ | ✗ |
| 3벳 받은 오프너, 그 밖의 짝 | – | 4벳 올인만(기존) | 같음 | 같음 | 기존 판단 |

연결 갱신 2026-10-27(사용자 승인 "ㄱㄱ"):
- 60·100bb 부모를 오픈 2.5bb(SB 3.0) 판으로 교체(s60_open25, s100_open25 → s60.json, s100.json 이름으로 사본). 첫 진입·오픈 받은 공격·3벳 받은 4벳(60) 이 2.5 오픈 기준이 됐다.
- 3벳 받은 오프너(vs_3bet_full): 30bb 13짝, 40bb 11짝. 남은 것: 40bb UTG+1 vs BTN(30bb 만 있음), UTG+1 vs SB 외 일부.
- 오픈 2.5 플랫콜 수비(vs_open_full_o25): 30·40·60bb BTN·CO. 30bb SB 오픈 vs BB 는 재계산 최종본으로 교체(KcTd9h 예외 승인분).
- refresh_records.sh 는 이제 기존 사본을 먼저 풀고 덮어쓴다(지워진 계산 브랜치의 기록이 빠지지 않게).

사용자 결정 2026-10-26:
- 100bb 를 넘는 스택(standard 시작 150bb)은 100bb 표를 그대로 쓴다(`gto_pf.covered` 상한 없음).
- 기준 범위 안 GTO 오픈은 유효 스택 60bb 이상이면 2.5bb, 그 아래는 2.0bb, SB 는 3.0bb
  (`preflop.GTO_PF_OPEN_DEEP_*`). 60·100bb 수비·3벳 표는 아직 2.0 오픈 기준이다. 2.5 부모(세션 E·F)가 오면 교체한다.
- ICM 연결은 보류. 칩 기준을 먼저 완성한다(`docs/ICM_DISCUSSION_REPLY_20261026.md`).

기록 상태(모두 quick, 대칭 스택, chip EV — 정밀 검사 대상):
- 100bb 부모(s100): 400회 상한에서 멈춤, 정확도 0.0169bb(목표 0.010 미달, G2 false). 60~100bb 는 s60·s100 직선 보간. 보고서 `docs/GTO_CONNECT_S100_20261024.md`.
- 3벳 받은 오프너 6개: 40bb CO vs SB 는 수렴, 나머지 5개는 3단계 상한(마지막 2단계 평균). 연결은 뿌리 노드만(4벳·올인 뒤는 연구용).
- 플랫콜 새 자리: 모두 3단계 상한(마지막 2단계 평균, 일부는 상한 표시를 손으로 붙임 — 기록의 status_note).
- SB 림프: CFR+ 재시도(사용자 위임 승인 10-23, 근거 `docs/GTO_SB_LIMP_FLOP_DIAG.md` — archive 브랜치)로 3단계까지 갔고 상한.
  **BB 뿌리에서 콤보의 39%(30bb)·45%(40bb)가 단계마다 체크↔레이즈로 뒤집혀** 평균 50/50 으로 찍힌 클래스가 많다
  (`vs_limp_full.unstable_share`). 체크·레이즈 차이가 작은 패들이라 손실은 작지만 정밀 검사 1순위.
- 30bb SB 오픈 vs BB 는 1단계 플랍 미수렴으로 멈춘 기록 그대로(재계산 대상, CFR+ 로 풀릴 가능성).

## 4. 새 기록이 오면 연결하는 절차

```
cd <test3 체크아웃>
sh tools/t2_handoff/refresh_records.sh               # (새 기록이 왔을 때만) 계산 브랜치 → data/gto_records/ 사본 갱신.
                                                     #   새 브랜치·파일은 스크립트 목록에 한 줄 추가. 지운 브랜치는 archive 에서 읽는다
sh tools/t2_handoff/fetch_records.sh /tmp/rec        # 사본을 한 폴더에 풀기
sh tools/t2_handoff/rebuild_gto_pf.sh /tmp/rec       # gto_pf_data.json 다시 만들기 + verify_gto_pf
python3 tools/t2_handoff/flat_check.py /tmp/rec      # 보정 자리: 연결 값 = 기록 값(클래스별 ≤ 0.002)
python3 tools/t2_handoff/verify_gto_connect.py /tmp/rec 40 /tmp/connect.json   # 연결 검사(약 30분, 아래)
# 기존 표 값이 바뀌지 않았는지: 이전 gto_pf_data.json 과 표·키별 비교(바뀐 키가 없어야 함)
bash tools/t2_handoff/regress.sh                     # 회귀 20개 = 기준(모두 0)
bash tools/t2_handoff/ui_checks.sh                   # 화면·게이트웨이(모두 0, opencv 필요)
```

- 연결 검사(`verify_gto_connect.py`): A 조회 값 = 기록 값(≤ 0.002, 기록에 없는 클래스는 None) /
  B 실제 엔진 경로로 기록 상황을 재현해 클래스마다 40회: GTO 경로를 탔는가(100%여야), 행동 종류별 빈도(도착 콤보 가중)가
  기록과 3%p 안인가, 클래스마다 표본 오차 안인가, 엔진 오류 0 / C 경로 선택(버킷 사이·범위 밖·크기 밖·멀티웨이·ICM·다른 림퍼) /
  D 새 표·모듈이 없어도 예외 없이 기존 판단. 결과 JSON 에 클래스별 숫자와 크기 배분(size_split)이 남는다.
- 새 종류의 노드는 빌더(`gto_pf_build.py`: id 로 종류를 가른다 — `_limp_`, `v1_`, 나머지 플랫콜)·조회(`gto_pf.py`)·연결 지점(`preflop.py`)·
  `plan.py` 행동 변환·`verify_gto_connect.py` 를 함께 만든다. 빌더는 `_dcfr_stop` 기록(옛 정지 기록)을 건너뛴다.
- 실제 봇 행동 비교(옛 기록 형식 spot_record_v2 전용): `tools/t2_handoff/pfcmp.py`. quick 기록은 verify_gto_connect 를 쓴다.
- 커밋 메시지에 계산기 값과 봇 값(폴드/콜/3벳/올인 %)을 적어 둔다(지금까지 그렇게 해 왔다).

## 5. 검사에서 알아야 할 함정

- **`pkill -f <패턴>` 을 같은 셸 명령 안에 쓰면 자기 셸도 죽는다**(명령줄에 패턴이 들어 있어서). 테스트 서버는
  `/proc/*/cmdline` 을 보고 `python3 ui_server.py --port 879*` 로 시작하는 것만 kill 한다.
- 검사는 `T2_DATA_DIR` 를 빈 임시 폴더로 준다. 안 주면 `~/.local/share/T2/personal` 의 참가 기록 때문에
  `/api/new` 가 "로비에서 예약 토너먼트에 바이인해 주세요"로 막혀 검사가 실패한다.
- 화면 검사(`ui/tools/verify_*.js`)는 `app.js` 에서 함수를 잘라 실행한다. 함수가 새 함수를 부르면 검사 쪽에 막이(stub)를 추가해야 한다.
- 화면 확인은 Playwright(크롬 내장)로 실제로 눌러 본다: `require('/opt/node-tools/node_modules/playwright')`,
  `executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'`. 터치는 CDP `Input.dispatchTouchEvent`.
  S23 화면은 360×760. 낮/밤 로비는 `timezoneId`(예 'America/Los_Angeles' 낮, 'Asia/Seoul' 밤)로 바꾼다.
- 웹 파일을 바꾸면 `index.html`/`lobby.html` 의 `?v=` 캐시 번호를 꼭 올린다(한 번 빠뜨렸다).
- 라운지 자산 검사(`verify_lounge_assets.py`, `lounge_check_assets.py`)는 `opencv-python-headless` 가 없으면 환경 오류로 실패한다.
- 이 클라우드 세션 권한으로는 원격 **태그 생성과 브랜치 삭제가 거부(403)** 된다. 브랜치 정리는 보관 브랜치를 만든 뒤 사용자가 GitHub 에서 지운다.

## 6. 배포·사용자 환경

- 사용자는 안드로이드 앱(WebView) → Termux 게이트웨이(`127.0.0.1:8080`) 로 플레이한다.
- 사용자에게 주는 서버 갱신 명령(그대로 붙여넣기):
```
pkill -f run_forever.sh; pkill -f gateway.py; pkill -f ui_server.py; sleep 1
cd ~/t2 && git fetch origin && git checkout test3 && git pull origin test3 && git log -1 --oneline
termux-wake-lock
sh gateway/run_forever.sh
```
- `gateway/run_forever.sh`: 게이트웨이가 죽으면(안드로이드 signal 9) 다시 켠다. 게이트웨이는 시작할 때 같은 폴더에 남은 게임 서버를 정리한다(`run/<uid>/server.pid`).
- **앱(APK)**: `android/**` 를 바꿔 push 하면 `android-apk.yml` 이 빌드해 릴리스 `android-latest` 를 덮어쓴다.
  테스트 서명 키는 `~/.t2-signing/test.jks` 를 캐시(키 `t2-test-signing-key-v2`, **브랜치별 캐시**)한다.
  test3 에서 빌드하는 동안은 같은 키. master 에서 빌드하면 키가 달라질 수 있다 → 출시 전 저장소 비밀값
  `T2_KEYSTORE_B64`/`T2_KEYSTORE_PASSWORD` 로 영구 키를 넣어야 한다(사용자 작업).
- 앱 안의 JS 다리 `T2App`: `signIn()`, `tap()`(버튼 진동). 앱은 왼쪽 가장자리(가운데 높이 200dp)의 뒤로가기 끌기를 막는다(순위 창용).

## 7. 화면(UI) 상태

**1인칭 가로 화면 개편 (2026-10-26, 설계·시제품 단계 — 게임 코드는 아직 안 바꿈)**
- 사양: `docs/presentation-spec.md`(화면 방향 규칙, 그림체 규칙, 좌석별 카메라, 말풍선·채팅창 규칙, 손 동작, 구현 순서, 열린 질문)
- 시안 PNG: `docs/presentation/`(가로 로비 `lobby_landscape.png`, 인게임 `ingame_landscape.png`, 구도 `layout_fov55.png`)
- 손 동작 시제품: `ui/web/proto/motions.html`(Three.js 0.160.0 동봉, `ui/web/vendor/`). 로그인 후 `/proto/motions.html`
- 사용자는 이 시제품 수준으로 충분하다고 했고, 이후 작업은 사용자의 프로젝트에서 이어간다.


**test3 에 들어간 것(10-19~21)**: 버튼 눌림(입체 음영+금테)·진동, 길게 누르기 메뉴 막기, 봇·새 가입자 이름 `T-########`(가입 때 닉네임 없음),
칩/BB 전환(금액 터치), 칩 더미(테마 3색, 펠트 위), 좌석 크기 = √(화면 면적/390×844), 타임뱅크 글자를 이름표 자리에,
안내 창(옻칠 갈색+금테, 아래에서 올라옴), 대회 정보 창 정리(상금은 칩), 브레이크 = 위에서 내려오는 알림 + 테이블 비우기,
결과·예약 문구 숨김, 순위 창 = 왼쪽 가장자리 끌기로 열기·왼쪽으로 밀어 닫기.

**보류(사용자 "UI 보류", 10-21)** — 코드는 `docs/handoff/lobby_ui_wip_20261020.patch`(test3 위에 `git apply`):
- 대회 카드에 `참가 신청 ↔ 참가 취소` 단추(카드를 누르면 대회 정보), 상황별 문구(대기실로/테이블로/결과 보기)
- 낮에는 모래·상아색 바탕(밤은 청록), 하늘빛 테두리·민트 상태 표시 → 금색, 선 아이콘
- 사용자 반응: 로비 시안 2안(밤 **남색**+금 / 낮 상아+금)이 좋다고 함. 3안(캐릭터 얼굴·단청 띠)은 별로.
  → 패치를 다시 쓸 때는 밤 색을 청록이 아니라 남색으로.
- 미결정: 게임 상단 단추 시안 A(금테 원형 아이콘)/B(알약 묶음)/C(아이콘+글자), 순위 창·대회 정보 창 새 시안 적용 여부.

**라운지 캐릭터 상호작용(다마고치형) — 설계만, 구현 안 함.** 사용자 결정 대기 5가지:
① 폴짝·흔들기(그림 전체 이동) 허용? ② 터치 중 여러 마리 동시 움직임? ③ 친밀도 저장 위치(기기/계정)?
④ 캐릭터 성격·말투(호랑이 허세·토끼 수줍음·거북이 느긋), 펭귄 포함? ⑤ 효과음?
기존 설계 `docs/LOUNGE_SCENE_DESIGN.md`(프레임 그림만, 포즈 그래프, 움직임 잠금)와 부딪히는 점 정리는 대화 기록 기준 —
결정이 나면 그 문서에 새 장으로 쓴다.

## 8. 아직 아무도 안 하고 있는 일 (2026-10-24 갱신)

| # | 일 | 상태 / 누가 | 메모 |
|---|---|---|---|
| 1 | 3벳 받은 오프너 30/40bb | **연결함(10-24)**: CO·UTG+1 vs SB, UTG vs BTN | 남은 짝(UTG+2·LJ·HJ vs SB, BTN vs SB 등)은 계산 필요. 정밀 검사 대상 |
| 2 | SB 림프 팟 | **BB 쪽 연결함(10-24)** | SB 첫 진입(30bb 이상 림프/오픈 선택)은 아직 기존 판단. BB 뿌리 불안정 39~45% — 정밀 검사 1순위 |
| 3 | 30bb SB 오픈 vs BB 재계산 | 계산 세션 | 1단계 플랍 미수렴(4.2% 팟). CFR+ 재시도(10-23 승인 방식)로 풀릴 가능성 |
| 4 | ICM 푸시/폴드 | 계획·파일럿 끝남(`claude/icm_pushfold_20261024`, `docs/GTO_ICM_PLAN.md`) | **사용자 결정 대기**: 표/실시간/버블 팩터, 점프·폴드만 할지, 상금 구조. 연결 안 함 |
| 5 | 오픈 2.5bb 부모(40·30bb) | 끝남(`claude/open_sizes_20261024`): 40bb 400회 상한·정확도 0.0116bb, 30bb 325회·0.00969bb(목표 충족). 기록 `records/s40_open25.json`, `s30_open25.json` | **사용자 결정 대기, 연결 안 함**: 2.0/2.5 를 고르게 하면 30·40bb 모두 오픈의 약 99% 가 2.5. 오픈 범위 30bb 0.6~1.6%p·40bb 0.2~1.8%p 좁아짐, BB 수비 거의 같음(BTN 상대 85%). **계획(사용자 승인 10-25)**: 상대 봇은 여러 크기로 오픈하므로 크기별 수비가 모두 필요하다. ① 2.5 오픈 BB 플랫콜 수비 계산(`claude/flat_open25_20261025`, 40bb→30bb, BTN·CO 먼저) ② 플랍 보정값으로 2.0 vs 2.5 오프너 손익 재비교(99% 2.5 가 간이 플랍 모델 탓인지 확인) ③ 오픈 {2.0, 2.5, 3.0}(SB {3.0, 3.5}) 부모 + 3.0 수비 ④ 2.0·2.5 차이가 크면 2.25 추가. 연결: `vs_open_full` 을 오픈 크기별로, 실제 오픈 크기로 이웃 크기 사이 보간, 3.0 초과는 3.0. 오픈 크기를 무제한으로 늘리지 않는 이유: 크기 수에 비례해 부모·수비 계산이 커지고, 크기 선택 자체가 플랍 간이 모델에 좌우된다. 봇 오픈 크기를 2.5 로 바꾸면(10-20 결정 2.0 변경) 지금 연결된 플랫콜·3벳 서브게임 기록(모두 2.0 오픈 기준)을 2.5 로 다시 계산해야 한다 |
| 6 | 100bb 부모 | **연결함(10-24)**: 첫 진입·오픈 받은 공격. 4벳 표는 비움, 플랫콜·서브게임 없음 | 60bb 작은 4벳은 이 컨테이너(15GB)로 불가능 |
| 7 | 원래 실패하던 검사 5개 | **끝남(10-24, 0d9dfa5c 반영)** | 남은 문제: 타이밍 규칙을 켜면 시간당 약 58핸드(검사 기준 70) — 검사는 규칙 끔으로 확인 |
| 8 | master 반영 준비 | T2 + 사용자 | test3 가 master 보다 크게 앞섬. APK 영구 서명 키 필요(사용자) |
| 9 | 헤즈업 폴드 뒤 결과 지연 확인 | T2 | 로컬 재현 안 됨. 사용자 기기 로그 필요(`~/t2_online/run/*/server.log`) |
| 10 | 화면 디자인 보류분(7장) | 화면 세션 | 사용자 결정 후 |
| 11 | 브랜치 삭제 | 사용자 | 끝난 17개는 `claude/archive-gto-runs-20261024` 에 보관 완료. 삭제는 이 세션 권한 밖(403) — GitHub 에서 `ARCHIVE.md` 표대로 |
| 12 | 3벳 크기 선택 | 미정 | 플랫콜 기록은 3벳 7·8bb 를 나누지만 봇은 3.7배 하나. 크기까지 따르려면 연결 확장 필요 |
