# UI — 현재 실행 가이드

UI는 **플레이 전용**이다. 관전 모드와 플레이 키 인증은 제거되었다.

## 폴더 역할

- 개발 원본: `~/t2`
- 실제 플레이 실행폴더: `~/t2_play`
- 추가 clone(`t2_play_src`)은 사용하지 않는다.

## 최신 코드 반영 / 실행

```sh
cd ~/t2
git pull --ff-only
sh ui/tools/setup_run_dir.sh ~/t2_play
cd ~/t2_play
python3 ui_server.py
```

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
6. 실시간 액션은 `계산 -> 모션 -> ACK -> 다음 계산` 순서를 지키며, 기록/대회정보 같은 읽기 요청은 계산 중에도 응답 가능해야 한다.
7. final-table 배선 검증은 `tools/playtest_final_table_ui.py`와 `.github/workflows/final-table-wiring.yml`에서 자동 수행한다.
