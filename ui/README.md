# UI — 현재 실행 가이드

UI는 **플레이 전용**이다. 관전 모드와 플레이 키 인증은 제거되었다.

## 폴더 역할

- 개발 원본: `~/t2`
- 실제 플레이 실행폴더: `~/t2_play`
- 추가 clone(`t2_play_src`)은 사용하지 않는다.

## 최신 코드 반영 / 실행

```sh
cd ~/t2
T2_UI_REF=master sh ui/tools/setup_run_dir.sh ~/t2_play
cd ~/t2_play
python3 ui_server.py
```

- 플레이는 **master** 로 한다. `T2_UI_REF=master` 는 `~/t2` 의 현재 체크아웃(test 등)과 무관하게 원격 master 커밋으로 실행 폴더를 만든다.
- 어느 커밋으로 만들었는지는 `~/t2_play/UI_SOURCE` 에 남는다.
- `T2_UI_REF` 를 빼면 예전처럼 `~/t2` 작업 트리 내용으로 만든다(개발 중 확인용).
- 진행 중인 게임 상태·아카이브는 다시 만들어도 유지된다.

브라우저에서 아래 주소 하나만 연다.

```
http://127.0.0.1:8765
```

- `/play`은 호환용으로 루트 `/`로 이동한다.
- `/watch`는 제거되었다.
- `.play_key`, 쿠키 인증, `X-T2-Play-Key`는 사용하지 않는다.

## API

- `GET /api/state`
- `GET /api/history`
- `GET /api/stats`
- `GET /api/memos`
- `POST /api/new`
- `POST /api/step`
- `POST /api/step-stream`
- `POST /api/step-ack` — UI 모션 완료 ACK; 다음 봇 계산을 여는 내부 제어용
- `POST /api/memo`

## 원칙

1. UI는 서버 응답을 유일한 진실로 본다.
2. 게임 상태/아카이브는 `~/t2_play`에서만 생성한다.
3. 저장소 루트의 상태 파일을 플레이에 재사용하지 않는다.
4. 상대 홀카드는 실제 공개 규칙에 맞는 경우만 표시한다.
5. UI 변경과 엔진 판단 변경은 별개로 검증한다.
6. 실시간 액션의 화면 모션 순서는 유지하되 엔진 계산은 모션 ACK를 기다리지 않는다. 기록/대회정보 같은 읽기 요청도 계산 중 응답 가능해야 한다.
7. final-table 배선 검증은 `tools/playtest_final_table_ui.py`와 `.github/workflows/final-table-wiring.yml`에서 자동 수행한다.

## 개인 지갑을 분리한 설치와 업데이트 (test, 2026-10-05)

예약 토너먼트/지갑 기능이 들어있는 `test` 소스 기준이다. 위의 기존 master 플레이 절차는
아직 이 기능을 배포하는 절차가 아니다. 아래 명령의 빈 `T2_UI_REF`는 현재 작업 트리를 선택한다.

| 구분 | 설치 결과 | 개인 지갑 |
|---|---|---|
| 최초 설치 | `~/T2/system`과 `~/T2/personal` | 처음 한 번 생성/지급 |
| 시스템 업데이트 | `~/T2/system`의 게임 파일 교체 | 그대로 유지 |

최초 설치와 실행:

```sh
cd ~/t2
T2_UI_REF= python3 ui/tools/install_game.py install ~/T2
cd ~/T2/system
python3 ui_server.py
```

업데이트는 실행 중인 서버를 `Ctrl+C`로 종료한 뒤 수행한다. `system`만 교체하며,
기존 개인 지갑을 찾거나 검증할 수 없으면 초기화하지 않고 중단한다.

```sh
cd ~/t2
T2_UI_REF= python3 ui/tools/install_game.py update ~/T2
cd ~/T2/system
python3 ui_server.py
```

`personal/tournaments.sqlite3`에는 지갑·거래·참가·대회 상태 원본이 들어간다.
`personal/installation.json`은 같은 지갑을 다시 연결하는 정보다. 서버를 종료하고
`personal` 폴더 전체를 백업/복원한다. 게임 코드와 `personal`은 서로 포함되지 않는 별도
폴더여야 한다. 두 폴더를 함께 옮기면 기본 상대 경로 연결도 유지된다.
외부 개인 폴더는 최초 설치에 `--personal-dir ~/T2-wallet`을 추가해 지정한다.
업데이트에서 개인 폴더를 새로 지정하거나 다른 지갑을 덮어쓰는 옵션은 허용하지 않는다.

기존 예약 대회 실행본에 `userdata` 지갑이 있으면 서버를 종료하고 명시적으로 이전한다.
원본 지갑은 남기며, 거래·참가·대회 상태와 `schedule.json`을 함께 가져온다.

```sh
cd ~/t2
T2_UI_REF= python3 ui/tools/install_game.py install ~/T2 --migrate-from ~/old_t2_run
```

배포용 최초 설치/업데이트 ZIP 생성:

```sh
T2_UI_REF= python3 ui/tools/build_game_packages.py ~/T2-packages
```

- `T2-install.zip`: 시스템 + 개인 폴더 안내 + `install.py`. 압축을 푼 `T2` 폴더에서 `python3 install.py`로
  처음 설치한다. 개인 지갑 DB는 패키지에 없으며 해당 사용자의 최초 설치에서 생성한다.
- `T2-update.zip`: 시스템 + `update.py`. 별도 위치에 압축을 푼 `T2` 폴더에서 `python3 update.py ~/T2`로
  기존 설치를 업데이트한다. 개인 폴더/지갑은 포함하지 않는다.

수동 `setup_run_dir` 실행본의 개인 데이터 기본 경로도 코드 밖으로 바뀌었다.
Linux/Termux에서는 `~/.local/share/T2/personal`이며 `XDG_DATA_HOME`이 있으면 이를 따른다.
수동 실행본의 `T2_DATA_DIR`도 코드 밖의 폴더로 지정한다. 표준 설치에서는 연결된 지갑과
다른 `T2_DATA_DIR`가 설정되면 시작/업데이트를 중단한다.

예약 대회 API: `GET /api/wallet`, `GET /api/lobby`, `POST /api/register`, `/api/enter`,
`/api/unregister`, `/api/reenter`. 일반 예약 대회 UI에서는 `/api/new`가 차단된다.
기존 JSON 상태/아카이브는 UI 호환 파일이며, 예약 대회의 복구 원본은 개인 SQLite다.
검증: `python3 ui/tools/verify_personal_installation.py` (23개),
`python3 tools/verify_scheduled_tournaments.py` (37개), `python3 ui/tools/verify_scheduled_ui.py`.

기본 대회는 한국 시간 00시부터 2시간마다 표준 → 터보 → 딥스택 순서로 열린다.
기존 기본 일정의 미참가 빈 슬롯만 정리하며, 기존 참가·취소 내역과 지갑은 보존한다.
개인 `schedule.json`이 있으면 그 명시적 설정을 유지한다.
레이트 바이인은 접수 후 대기 화면에서 자동으로 입장한다. 기존 필드가 먼저 등록을 마감하면
미착석 참가비를 자동 환불한다. `T2_UI_DEFER=0`과 `1` 모두 정산/재참가를 지원한다.
재현 검증의 `T2_VERIFY_SCHEDULE_LATE=1`은 진행 스냅샷이 없는 레이트 참가 경로를 선택한다.
`T2_VERIFY_SCHEDULE_TIMING=enforce`는 봇 예정표/액션 시계가 켜진 입장 검증을 선택한다.

## 가상 시계 / 화면 버전 68 (test, 2026-10-04)

새 UI 대회는 핸드 수 대신 가상 진행 시간으로 레벨이 오른다. 로비에서 레벨 길이를
1~120 정수 분으로 지정할 수 있다. 속도별 기본값은 딥 15, 표준 10, 터보 5,
하이퍼 2분이다. 그 외 형식은 Regular 10분을 기본 선택으로 사용하며, 바이인·바운티·
위성이라는 이름 자체가 그 속도를 정한다는 뜻은 아니다.

근거: PokerStars 현재 Tournament speed 도움말(2026-10-04 확인):
https://www.pokerstars.com/help/articles/tournament-speed/246700/
유형 설명 페이지에는 Hyper 3분도 있다. 개별 이벤트의 실제 구조표가 우선이며,
T2 기본값은 현재 속도 도움말의 2분을 채택했다.
https://www.pokerstars.com/poker/tournaments/types/

- 상단: `가상 경과 MM:SS` (1시간 이상이면 HH:MM:SS).
- 가상 플레이 55분마다 진행 중 핸드를 마친 뒤 5분 브레이크 창.
- 창: `남은 시간 05:00` 카운트다운. 표시용 5분 실제 대기는 건너뛸 수 있다.
  건너뛰어도 가상 휴식 5분은 한 번만 기록한다. 휴식 중 블라인드 시계는 정지한다.
- 다른 테이블이 끝나지 않았으면 `다른 테이블 진행 완료 대기 중`으로 바뀐다.
- 자동 진행이 꺼져 있어도 브레이크는 표시한다. 정산·휴식이 끝나야 다음 핸드 버튼을 표시한다.
- 준비 상태 조회가 실패하면 다시 조회한다. 네트워크 실패를 준비 완료로 간주하지 않는다.
- 기존 저장 대회에는 시계를 역산하지 않는다. `기존 대회 · 핸드 기준`으로 표시한다.
  새 시계를 쓰려면 새 게임이 필요하다.

### 구현 범위와 남은 검증

가상 핸드 시간은 설계 시뮬레이터의 **가정 모델**(기본 8초, 액션별 1.5~5.5초,
스트리트 전환 2초, 쇼다운 3초)을 사용한다. 실제 관측값이나 공식 액션 타이머가 아니다.
현재는 raw shape를 적용하며, 시뮬레이터가 표본 평균으로 계산하는 속도 보정 배율은
아직 적용하지 않았다. 레벨 길이와 가상 핸드 속도 모델은 서로 다른 설정이다.

비-HERO 테이블은 각자 독립 `vclock_seconds`로 55분 세션을 선계산한다. 탈락/테이블
이동 가능 지점에서는 barrier를 세우고 HERO 실제 시간이 도달했을 때만 확정한 뒤
실제 `_collect_busts()`/`_balance()`를 실행한다. 머니·좌석 버블과 9-max 10명
FT 버블에서는 hand-for-hand로 모든 테이블이 한 핸드씩 끝날 때까지 동기화한다.

검증: `ui/tools/verify_clock_ui.py`, `node ui/tools/verify_clock_ui_js.js`,
`ui/tools/verify_ui.py` 단일 9명/여러 테이블 18명. 단일 테이블 경로의
`single_table_skip` 초기값 누락(KeyError)도 수정했다. 이는 최신 test에서 재현한 문제이며,
62abf3f에서 보고된 76핸드 후 멈춤과 동일한 원인이라고 판정하지 않았다.

### UI 70 — 히어로 실제 시간
히어로 대회의 경과 시간은 대회 시작 시각부터 실제 시간과 함께 흐르며 화면은 매초 서버 시간을 조회합니다. 레벨 길이 설정은 분 단위지만 실제 남은 레벨 시간과 55분 세션 시간은 초 단위로 계산·표시합니다. 레벨은 휴식 시간을 제외한 실제 경과 시간으로 계산해 다음 핸드 시작에 적용하며 핸드 중간에 블라인드를 바꾸지는 않습니다. 비-HERO 테이블은 독립 가상시계로 선계산합니다. 공식 5분 브레이크가 끝나도 뒤처진 봇 계산이 남아 있으면 그 추가 대기까지 브레이크로 처리해 HERO 플레이 시계를 계속 정지시키고, 전 테이블 동기화가 끝난 뒤에만 다음 55분 세션을 시작합니다.


### UI 71 — 히어로 15초 액션 제한
히어로의 액션창이 실제로 열린 순간 서버가 15초 deadline을 만든다. 카드 딜/앞선 봇 액션 재생 시간은 포함하지 않는다. 같은 decision token을 새로고침하거나 다시 렌더해도 deadline은 연장되지 않는다. 남은 시간은 액션바 위에 표시하고 15초가 끝나면 자동 폴드한다. 늦게 도착한 콜/레이즈도 서버가 deadline을 다시 확인해 폴드로 바꾼다. 해당 decision에서 fold가 노출되지 않는 무료 체크 상황만 check를 안전 fallback으로 쓴다. 테스트에서는 `T2_HERO_ACTION_SECONDS`로 시간을 줄일 수 있고 기본값은 15초다.
