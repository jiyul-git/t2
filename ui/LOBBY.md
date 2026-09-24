# T2 Lobby Shell

앱/웹 진입점을 단일 토너 테이블에서 상위 로비 구조로 확장한다.

## 라우트

- `/` 또는 `/lobby`: 로비
- `/play`: 기존 실제 토너 테이블
- `/watch`: 기존 관전 테이블
- `/api/lobby`: formats.py 기반 토너 카탈로그 + 현재 진행 대회 요약
- `/lobby/<PLAY_KEY>`: 플레이 인증 후 로비 진입
- `/play/<PLAY_KEY>`: 기존 플레이 인증 후 테이블 진입

## 현재 지원 게임 모드

- Tournament: 실제 동작
- Cash Game: UI 확장 자리만 예약
- Sit & Go: UI 확장 자리만 예약

로비는 `formats.py`를 단일 출처로 사용한다. 토너 구조 수치를 프론트에 복제하지 않는다.

## 토너 참가

로비는 `POST /api/new`에 `fmt`, `entries`, 선택적 `seed`를 보낸다.
`live2.new_game()`은 명시값이 없을 때 선택된 포맷의 다음 값을 실제 런타임에 적용한다.

- `start_bb × 초기 BB` -> 시작 스택
- `hpl` -> 레벨당 핸드 수
- `itm_frac` -> ITM 비율

standard 기본값은 기존 값과 동일하다(150BB × 200 = 30,000, 12 hands/level, ITM 15%).

## 확장 원칙

이 로비가 상위 셸이다. 이후 캐시게임, Sit & Go, 계정/재화, 이벤트 등을 추가하더라도
기존 테이블 UI는 `/play` 하위의 한 게임 화면으로 유지한다.

Android 래퍼/앱은 로비를 시작 화면으로 사용할 수 있고, 서버 계약은 웹과 동일하게 유지한다.
