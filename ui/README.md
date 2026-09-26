# UI — 현재 실행 가이드

이 문서는 **현재 코드 기준**이다. 과거 브랜치 단계 설명은 신뢰하지 않는다.

## 폴더 역할

- 저장소/개발 원본: `~/t2`
- 플레이 실행폴더: `~/t2_play`
- 실행폴더에는 게임 상태와 아카이브가 생긴다. Git 원본과 섞지 않는다.
- 별도 `t2_play_src` clone은 필요 없다.

## 최신 코드를 플레이 폴더에 반영

```sh
cd ~/t2
git pull --ff-only
sh ui/tools/setup_run_dir.sh ~/t2_play
cd ~/t2_play
python3 ui_server.py
```

`setup_run_dir.sh`는 코드/필수 데이터만 허용목록으로 복사한다. 기존 `~/t2_play`의
게임 상태와 아카이브는 유지한다.

## URL과 권한

서버 시작 시 현재 키를 사용한 주소를 직접 출력한다.

- `/watch` — 관전 전용. 상태 변경 API를 호출할 수 없다.
- `/play/<PLAY_KEY>` — 최초 플레이 인증. 쿠키를 발급한 뒤 `/play`로 이동한다.
- `/play?k=<PLAY_KEY>` — 동일한 최초 인증 방식의 호환 주소.
- `/play` — 이미 인증된 브라우저의 재접속 주소.

로컬 Termux의 `http://127.0.0.1`에서는 Secure 없는 HttpOnly 쿠키를 사용한다.
HTTPS reverse proxy에서는 `X-Forwarded-Proto: https` 또는 `T2_COOKIE_SECURE=1`일 때
Secure 쿠키를 사용한다.

플레이 키 파일은 실행폴더의 `.play_key`이다. 이 파일은 Git에 넣지 않는다.

## API 경계

읽기:

- `GET /api/state`
- `GET /api/history`
- `GET /api/stats`

플레이어 전용:

- `GET /api/memos`
- `POST /api/new`
- `POST /api/step`
- `POST /api/memo`

상태 변경 요청은 **플레이 인증 + `X-T2-Client-Mode: play`** 둘 다 필요하다.

## 원칙

1. UI는 서버 응답을 유일한 진실로 본다.
2. 플레이 실행폴더에서만 게임 상태를 생성한다.
3. 저장소 루트의 상태/아카이브 파일을 플레이에 재사용하지 않는다.
4. 상대 홀카드는 실제 공개 규칙에 맞는 경우만 표시한다.
5. UI 변경과 엔진 판단 변경은 같은 항목으로 취급하지 않는다.

## 검증

```sh
cd ~/t2
python3 ui/tools/verify_ui.py --hands 12 --entries 100
```

검증기는 실제 `~/t2_play` 상태를 덮어쓰지 않는 임시 실행 환경을 사용해야 한다.
