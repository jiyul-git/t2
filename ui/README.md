# 그래픽 UI (1단계)

포커 엔진에 HTTP 래퍼를 씌워 그래픽 테이블 UI 를 붙이기 위한 폴더다.
엔진 파일은 하나도 건드리지 않는다.

## 절대 규칙

1. **엔진 파일을 수정하지 않는다.** `live2.py`, `session.py`, `plan.py`,
   `view.py`, `fieldsim.py` 등 기존 파일 전부 해당한다. 새 파일은 `ui/` 아래에만 만든다.
   엔진 수정이 필요하면 이유와 diff 초안만 보고하고 승인을 기다린다.
2. **메인 엔진 폴더에서 `live2.new_game()` 을 부르지 않는다.** 진행 중인 게임을
   덮어쓰고 아카이브를 옮긴다.
3. **라이브 화면에 봇 내부값(plan, eq, why, rel, outs, profile)을 노출하지 않는다.**
4. 상대 홀카드는 쇼다운까지 간 좌석만 공개한다.
5. 화면에는 팟과 콜 비용만 표시한다. 팟 오즈·에쿼티·추천 액션은 넣지 않는다.
6. UI 작업은 엔진 연구와 별도 브랜치에서 한다.

## 구성

```
ui/
  server/ui_view.py      live2 가 import 하는 view 를 대체한다. 원본 view.build()
                         를 그대로 부르고 결과를 화이트리스트 JSON 으로 바꾼다.
  server/ui_server.py    표준 라이브러리 http.server 기반 래퍼.
  tools/setup_run_dir.sh 실행 폴더를 만든다 (허용 목록 복사).
  tools/verify_ui.py     자동 검증.
  web/                   2단계 산출물.
```

## 실행

```sh
sh ui/tools/setup_run_dir.sh ~/t2_ui_run
cd ~/t2_ui_run && python3 ui_server.py            # 기본 8765 포트
```

### 왜 별도 폴더인가

`live2` 는 아카이브(`hand_archive2*.jsonl`, `book*`, `dynamics*`, `bot_hands*`)를
**모듈 폴더**에 쓴다. 또 `T2_LIVE_STATE` 를 설정하면 경로와 무관하게 접미사가
`_alt` 하나로 고정되어(`live2.py:12`), `cli.py` 세션과 같은 폴더면 파일을 공유하게 된다.
그래서 실행 폴더에 `UI_SERVER_DIR` 표시 파일이 없으면 서버가 시작을 거부한다.

**`ui_server.py` 에 `T2_LIVE_STATE` 를 추가하지 말 것.** 설정하지 않아야
접미사가 비고, 상태·아카이브가 실행 폴더 안의 무접미사 이름으로 격리된다.

### 복사 대상

`setup_run_dir.sh` 는 **허용 목록 방식**이다. 제외 목록으로 짜면 안 된다 —
`live2_state.json`, `claude_state.json`, `hand_archive2*.jsonl`,
`bot_hands*.jsonl` 이 전부 git 에 커밋되어 있어서 `cp *.json` 이나 clone 으로는
진행 중인 게임이 실행 폴더로 딸려 들어간다.

- 모듈 22개: live2 가 전이적으로 import 하는 전부. `view.py` 는 `ui_view` 가
  `view_text` 라는 이름으로 직접 로드하므로 반드시 포함한다.
- 데이터 3개: `pf_rank.json`(없으면 `preflop.py` import 실패),
  `style_sig.json`, `style_prior.json`(없으면 스타일 추정 경로가 꺼진다).

이미 있는 폴더에 다시 돌려도 된다. 코드만 덮어쓰고 상태·아카이브는 건드리지 않는다.

## API

| | |
|---|---|
| `GET /api/state` | 캐시된 마지막 응답. 없으면 현재 상태를 재생해서 만든다 |
| `POST /api/new` | `{entries?, seed?, fmt?, start_stack?}` |
| `POST /api/step` | `{action, amount, token}` |

- `action`: `fold/check/call/bet/raise/allin`, 또는 `null`(다음 핸드 딜)
- `amount`: **이번 스트리트 총 투입 목표(raise-to)**. 증분이 아니다.
- `token`: 직전 응답의 값. 다르면 409 — 재전송으로 액션이 두 번 들어가는 것을 막는다.
- 응답: `{done, view, token}`. 종료 시 `busted`, `rank`. 탈락 후에는 `game_over`.
  엔진의 `raw`/`result` 원본은 내보내지 않는다.

## 검증

```sh
python3 ui/tools/verify_ui.py --hands 12 --entries 100
```

**항상 임시 폴더를 새로 만들어서 거기서 검사한다.** `/api/new` 를 부르기 때문에
실제 실행 폴더에서 돌리면 진행 중인 게임이 날아간다. 그래서 대상 폴더를 인자로 받지 않는다.

검사 항목: 칩 보존, 홀카드 누출(아카이브 대조), 내부값 키 누출, 오래된 token → 409,
최소 미달 레이즈 → error + token 불변, `legal` 과 `Round.apply` 의 일치,
워크 핸드, 지연 시간.

## 알려진 사항

- **엔진의 오류 응답에는 `stacks`/`contrib` 가 빠져 있다**(`session.py:150,330`).
  그래서 좌석 값이 틀린다. 서버가 직전 정상 화면에 `error` 만 붙여 돌려준다
  (token 불변, `ui_server.py:127-133`).
- 원본 `view` 의 좌석 stack 은 **스트리트 시작값**이다. `ui_view` 가 raw 의
  현재값으로 바꿔 넣는다.
- 원본 `view.py:45` 의 레이즈 상한 표시(`mn ~ st`)는 단위 버그다. 실제 상한은
  `st + 이미 투입한 금액`이다. `ui_view` 의 `max_to` 는 올바르게 계산한다.
  원본 수정은 승인 사항이라 손대지 않았다.
- 히어로가 액션하지 않고 끝나는 핸드(워크)가 있다. 딜 직후 곧바로
  `type: result` 가 올 수 있다(`session.py:131-136`).
- 핸드 사이의 `step(None)` 은 다음 핸드를 딜한다. 부작용이 있는 호출이다.
- 테이블은 8슬롯 고정이다(`fieldsim.MAXSEAT = 8`). 슬롯 번호는 고정이고
  빈 슬롯이 생긴다 — `seats` 배열의 길이는 8보다 작을 수 있다.
- 핸드를 끝내는 액션은 오래 걸린다. 대부분 `finish()` 안의 `step_others()`
  (타 테이블 진행)이고, entries 에 비례한다. 단축하려면 `live2` 수정이 필요하다
  → 승인 사항. UI 는 로딩 상태로 대응한다.
