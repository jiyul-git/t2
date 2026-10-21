# T2 이어받기 매뉴얼 (봇 판단 검증 · GTO 연결 · 화면)

새 세션이 이 문서만 읽고 이어서 일할 수 있게 쓴다. 마지막 갱신: 2026-10-21, test3 `6fc58080` 기준.
작성: T2 봇 판단 검증 세션(session_01XV9GKUYpuxdA2ckcjg1qsv).

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

- 계산 세션들은 계산만 한다. 봇에 붙이는 일(연결)은 이 문서의 담당(T2 세션)이 한다.
- 계산 세션에 일을 맡길 때는 `send_message` 로 보낸다(사용자: "둘 다 그냥 너가 보내").
- 계산 표준·결정 이력은 census 브랜치의 `docs/GTO_SESSIONS_BOARD.md` 가 원본이다.

## 2. GTO 기준 연결 구조

### 2.1 파일
| 파일 | 하는 일 |
|---|---|
| `gto_pf.py` | 기준 데이터 조회. 버킷 사이 직선 보간, ±0.25bb 경계, 6~9인 → 9인 자리 변환, 노안테·범위 밖은 None |
| `gto_pf_data.json` | 기준 데이터(실행 폴더에 평평하게 복사된다). `tools/gto_pf_build.py` 가 만든다 |
| `tools/gto_pf_build.py` | 계산 기록 → `gto_pf_data.json` |
| `preflop.py` | 연결 지점(아래 2.3). `T2_GTO_PF=0` 이면 전부 끔. 모듈·데이터가 없으면 None(기존 판단) |
| `plan.py` `preflop_plan` | 연결 결과를 실제 행동으로 바꿈 |
| `session.py` | `pf_other_live_actors`, `pf_actor_acted`, `pf_aggressor_total_bb` 계산(공개 행동 기록 `action_meta`) |
| 실행 폴더 목록 | `ui/tools/setup_run_dir.sh`, `ui/tools/setup_run_dir.py`, `install_game.py` STATIC_DATA, `verify_fresh_install_startup.py` — **새 모듈·데이터는 네 곳 모두에 넣는다**(빠뜨려서 게이트웨이 서버가 죽은 적 있음, 27d0424b) |

### 2.2 데이터 표 (`gto_pf_data.json`)
| 표 | 내용 | 기록 |
|---|---|---|
| `first_in` | 첫 진입 jam/open/limp 빈도 (SB 는 림프가 있는 30bb 이상에서 뺌) | pf10~25, s30, s40, s60 |
| `vs_jam` | 단독 올인에 콜 | pf10~25 |
| `vs_3bjam` | 오픈 후 3벳 올인에 콜 | pf15~s60 |
| `vs_open` | 단독 오픈에 대한 공격(3벳·3벳 올인)만 | pf15~s60 |
| `vs_3bet` | 3벳 받은 오프너의 4벳 올인 | s30~s60 |
| `vs_open_full` | **플랫콜 루프로 보정된 자리**: 단독 오픈을 받은 BB 의 폴드·콜·3벳·올인 전체 + 오픈 크기(`open_bb`) | p30/p40_flat_*_vs_bb |

- 공격자 콤보 < 10 인 노드는 뺀다(거의 안 쓰는 올인).
- 버킷: 10, 15, 20, 25, 30, 40, 60bb. 유효 스택 = 핸드 시작 기준, 상대와의 작은 쪽.

### 2.3 연결 지점 (preflop.py)
| 함수 | 상황 | 막는 조건 |
|---|---|---|
| `gto_pf_first_in_choice` | 첫 진입 | ICM 압력(BF > 1.05 또는 머니점프 pressure/brake/위험 몫), 범위 밖 |
| `gto_pf_call_choice` | 단독 올인 콜, 내가 오픈 후 3벳 올인 콜 | 콜러가 낀 팟, 행동 여부 모름 |
| `gto_pf_aggr_choice` | 오픈 받음(3벳/3벳 올인), 3벳 받음(4벳 올인). 보정된 자리는 콜·폴드까지 | 위와 같음 |

- 기준 범위 안에서 봇이 오픈할 때는 **계산기와 같은 크기(2.0bb, SB 3.0bb)** 로 친다(사용자 결정 10-20).
- 보정된 자리(`vs_open_full`)는 실제 오픈 크기가 기록 크기의 0.9~1.25배일 때만 쓴다.

## 3. 연결 현황 (2026-10-21)

| 상황 | 10~25bb | 30bb | 40bb | 60bb |
|---|---|---|---|---|
| 첫 진입(SB 제외) | ✅ | ✅ | ✅ | ✅ |
| SB 첫 진입 | ✅(림프 없는 트리) | ✗ 기존 판단 | ✗ | ✗ |
| 올인 콜 / 3벳 올인 콜 | ✅ | ✅ | ✅ | ✅(데이터 적음) |
| 오픈 받은 공격(3벳·3벳 올인) | ✅(15~) | ✅ | ✅ | ✅ |
| 3벳 받은 4벳 올인 | – | ✅ | ✅ | ✅(작은 4벳 없음) |
| **BB 플랫콜 수비(보정)** | – | BTN·CO·SB | BTN·CO·SB·HJ | ✗ |
| 3벳 받은 뒤 콜 | ✗ 기존 판단(봇 12% vs 계산 68%, 가장 큰 차이) | | | |

플랫콜 기록 상태: 30bb SB 오픈은 1단계에서 멈춤(한 보드 플랍 미수렴 4.2% 팟) — 재계산 대상.
40bb SB·HJ 는 3단계 상한(마지막 2단계 평균). BTN·CO 는 수렴.
HJ 는 40bb 기록만 있어 40bb(±0.25) 근처에서만 쓰인다(30bb 기록이 오면 30~40 전체).
30bb SB 림프 기록은 있지만 **연결 안 함**: 0단계에서 멈췄고, "SB 림프를 받은 BB"를 받는 연결 지점이 아직 없다.

## 4. 새 기록이 오면 연결하는 절차

```
cd <test3 체크아웃>
sh tools/t2_handoff/fetch_records.sh /tmp/rec        # 계산 브랜치에서 기록 모으기(새 경로가 생기면 스크립트에 추가)
sh tools/t2_handoff/rebuild_gto_pf.sh /tmp/rec       # gto_pf_data.json 다시 만들기 + verify_gto_pf
python3 tools/t2_handoff/flat_check.py /tmp/rec      # 보정 자리: 연결 값 = 기록 값(클래스별 ≤ 0.002)
git diff --stat gto_pf_data.json                     # 기존 버킷·자리 값이 바뀌지 않았는지 확인(파이썬으로 표별 비교)
bash tools/t2_handoff/regress.sh                     # 회귀 20개 = 기준
bash tools/t2_handoff/ui_checks.sh                   # 화면·게이트웨이(원래 실패 목록은 스크립트 머리말)
```

- 새 종류의 노드(예: 림프 팟, 3벳 콜 팟)는 빌더·연결 지점을 새로 만들어야 한다. 빌더는 모르는 기록을 건너뛴다.
- 실제 봇 행동 비교(선택): `tools/t2_handoff/pfcmp.py <코드폴더> <기록.json> <노드번호> 2 <out.json>`
  — 기록 노드를 엔진으로 재현해 169 클래스마다 봇의 첫 행동을 뽑는다. 클래스당 2회라 섞인 빈도는 몇 %p 흔들린다.
  연결 전과 비교하려면 옛 코드 폴더(예: master `4f6cf100` 워크트리)로 한 번 더 돌린다.
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

## 8. 아직 아무도 안 하고 있는 일

| # | 일 | 누가 할 수 있나 | 메모 |
|---|---|---|---|
| 1 | **3벳 콜 팟 루프**(오픈 → 3벳 받고 콜) 30/40bb | 계산 세션 | 표준의 우선순위 (3). 봇 12% vs 계산 68% 로 가장 큰 차이 |
| 2 | **SB 림프 팟 연결**(BB 가 림프를 받음 + SB 첫 진입 30bb 이상) | 계산 + T2 | 30bb 림프 기록 재계산(0단계 정지) + 새 연결 지점 |
| 3 | **30bb SB 오픈 재계산** | 계산 세션 | 1단계에서 플랍 미수렴(4.2% 팟)으로 멈춤 |
| 4 | **ICM 푸시/폴드 표**(버블·파이널 테이블) | 계산 세션(새 작업) | 지금 ICM 압력이 있으면 GTO 를 끄고 기존 판단. 토너먼트 승부처 |
| 5 | **다른 오픈 크기(2.2·2.5bb) 계산** | 계산 세션 | 사용자: 2bb 먼저, 나중에. 사람 플레이어 오픈은 크기가 제각각 |
| 6 | 60bb 작은 4벳, 100bb 부모(200회에서 멈춤) | 계산 세션 | 사용자 순서상 마지막 |
| 7 | **원래 실패하는 검사 정리** | 아무 코드 세션 | verify_preflop_closure, verify_clock_ui, verify_vclock_session, verify_action_clock_js, verify_ui_tournament_panel |
| 8 | **master 반영 준비** | T2 + 사용자 | test3 가 master 보다 크게 앞섬. APK 영구 서명 키 필요(사용자) |
| 9 | 헤즈업 폴드 뒤 결과 지연 확인 | T2 | 로컬 재현 안 됨. 사용자 기기 로그 필요(`~/t2_online/run/*/server.log`) |
| 10 | 화면 디자인 보류분(7장) | 화면 세션 | 사용자 결정 후 |
