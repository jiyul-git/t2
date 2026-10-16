# 로비 공항 라운지 장면 설계서

작성: 2026-10-16 · 대상: 로비 상단 일러스트 영역(`.airport-scene`)
구현 담당 세션이 이 문서만 읽고 작업을 시작할 수 있도록 결정 사항, 파일 구조, 데이터 형식, 공식, 완료 기준을 모두 적는다.
이 문서와 코드가 다르면 **이 문서가 기준**이다. 바꿔야 하면 문서를 먼저 고치고 커밋한다.

---

## 구현 현황 (2026-10-16)

1단계(11장의 1~10) 구현 완료. 임시 그림으로 동작하며, 실제 그림은 12장에서 이어진다.

- 코드: `ui/web/lounge/` (태양, 조명, 위치, 안내판, 행동, 에셋 로더, 렌더러, 진입점, 디버그 패널)
- 임시 그림: `ui/web/lounge/assets/` (`ui/tools/lounge_make_placeholders.py`로 다시 만들 수 있다)
- 시험: `ui/tools/verify_lounge_*.js`, `ui/tools/verify_lounge_assets.py`, `ui/tools/lounge_check_assets.py`. CI는 `.github/workflows/lounge-scene.yml`
- 화면 확인: `node ui/tools/lounge_screens.js docs/lounge` (Playwright 필요). 서울 2026-03-20의 5개 시각 스크린샷이 `docs/lounge/`에 있고, 프레임 비용은 평균 1ms 안팎(기준 6ms)이다.
- 위치 버튼은 두지 않는다. 장면이 뜬 뒤 브라우저에 정확한 위치를 한 번 요청한다(5.3절).
- 알려진 한계: 걷는 캐릭터끼리 겹쳐 지나갈 수 있다(충돌 회피 없음). 대화 교대 순간은 최대 한 루프 어긋난다(7.3절). 위치 요청은 장면을 기다리게 하지 않는다.

---

## 0. 목표와 범위

**최종 목표**

1. 그림체는 지금 승인된 일러스트 그대로 유지한다(부드러운 페인팅 + 2~3등신 동물 캐릭터).
2. 사용자의 실제 위치와 시각을 반영한다. 하늘색, 노을, 해·달·별, 바닥 그림자, 실내 조명이 실시간으로 바뀐다.
3. 캐릭터(호랑이, 토끼, 거북이, 펭귄)가 화면 좌우 밖에서 걸어 들어와 벤치에 앉는다. 앉아서 폰 보기, 전화, 밥 먹기, 선글라스, 옷매무새, 옆 캐릭터와 대화, 졸기 같은 동작을 하다가 다시 걸어 나간다.
4. 출발 안내판에는 실제 토너먼트 일정을 항공편처럼 표시한다.

**이번 1단계에서 할 것** (그림 제작은 보류. 자금 확보 후 진행)

- 위 2~4를 모두 구현한 **엔진**. 그림은 코드로 생성한 **임시 그림(플레이스홀더)**을 쓴다.
- 임시 그림도 나중에 들어올 실제 그림과 **같은 파일 규격(에셋 계약, 6장)**을 따른다. 실제 그림이 오면 파일만 교체하고 코드는 고치지 않는다.

**하지 않을 것**

- 게임 테이블 화면(`index.html`, `app.js`, `style.css`, `theme.css`, `visuals.js`), 포커 엔진, 지갑, 서버 로직은 건드리지 않는다.
- 위치 정보는 서버를 포함해 어디로도 전송하지 않는다.
- 외부 네트워크 요청을 추가하지 않는다. 날씨 API는 나중 단계에서 검토한다.

---

## 1. 확정된 결정

| # | 결정 | 근거 |
|---|---|---|
| D1 | 구도는 캐릭터가 걸어 들어올 공간이 있는 **넓은 라운지 샷**으로 바꾼다. 캐릭터가 서 있을 때 키는 장면 높이의 약 40%다. | 지금 클로즈업 구도에는 걸어 다닐 공간이 없다 |
| D2 | 캐릭터 애니메이션은 **프레임 바이 프레임**(매 프레임을 통째로 다시 그린 그림)으로 한다. 관절을 잘라 회전시키는 컷아웃·본 애니메이션과 셰이더 변형은 **금지**한다. | 사용자 요구. 이전 GPT 결과(관절 절단)는 부자연스러웠다 |
| D3 | 모든 동작 클립은 정해진 **기준 포즈에서 시작해 기준 포즈로 끝난다**(포즈 그래프, 5장). | 어떤 순서로 이어도 튀지 않게 하려고 |
| D4 | 조명 상태는 시계 시각이 아니라 **태양 고도**로 정한다. | 계절과 위치에 따라 일출·일몰이 실제와 맞도록 |
| D5 | 위치는 **최종적으로 브라우저 위치 권한**을 쓴다. 권한이 없으면 기기 시간대로 추정한다. | 사용자 결정 |
| D6 | 렌더링은 **Canvas 2D**로 한다. WebGL은 쓰지 않는다. | 단순하고 테스트하기 쉽다. 필요한 효과(합성, 틴트, 그림자)는 Canvas 2D로 충분하다 |
| D7 | 안내판 글자는 그림에 넣지 않고 **코드로 그린다**. 실제 대회와 가상 항공편을 섞어 표시하며, 잘 안 보여도 된다. | 사용자 결정 |
| D8 | 시간 테스트 UI는 **디버그 모드에서만** 보인다(`?lounge_debug=1`). | PR #40의 `TEST_CLOCK_MODE=true` 상태로 배포될 위험을 없앤다 |

---

## 2. 기준 브랜치와 기존 코드 정리

- 작업 브랜치 `claude/t2-ui-changes-dobpqd`는 **PR #40 head(`d6e6d7ba`, `chatgpt/airport-lobby-day-night-20261016`)에서 분기**했다. 로비의 한글 문구, 추천 대회 카드, 필터 탭, 하단 메뉴는 그대로 쓴다.
- PR #40에 새 커밋이 생기면 merge로 가져온다. rebase는 하지 않는다.
- PR #40의 장면 관련 코드는 이 엔진으로 **대체**한다. 아래 목록대로 정리한다.

| 파일 | 처리 |
|---|---|
| `ui/web/airport-theme.js`, `ui/web/airport-motion.js` | 삭제. 새 `ui/web/lounge/*`로 대체 |
| `ui/web/assets/t2-airport/layers/*` | 삭제. 쓰는 곳이 없다 |
| `ui/web/assets/t2-airport/toggle_remove_*.webp`, `lobby_hero_day.webp` | 삭제. 쓰는 곳이 없다 |
| `ui/web/assets/t2-airport/lobby_hero_night.webp` | **유지**. 엔진이 실패했을 때 보여줄 정적 그림이다 |
| `ui/web/assets/t2-airport/card_*.webp` | 유지. `lobby.js`의 대회 카드 썸네일이다 |
| `ui/tools/build_airport_layers.py`, `.github/workflows/airport-layers.yml` | 삭제. 브랜치에 직접 push하는 워크플로라서 없앤다 |
| `ui/tools/preview_airport_termux.sh` | 새 브랜치와 새 파일 목록에 맞게 고친다(7장) |
| `ui/AIRPORT_ASSET_README.md` | 삭제. 이 문서가 대신한다 |
| `ui/web/lobby.css`의 `.airport-*` 규칙 | 장면 영역 규칙을 새로 한 벌 쓰고, 중복·덮어쓰기 규칙(`!important` 덮어쓰기, `--airport-lamp-alpha` 자기참조 등)은 삭제한다 |
| `ui/web/lobby.html`의 장면 `<section>`과 `#airportTimeTest` | 4.6절 구조로 교체 |

---

## 3. 장면 좌표계와 구도

논리 좌표계는 **1440 × 1040**(가로 × 세로, 원점은 왼쪽 위)이다. 화면에서는 장면 박스 너비에 맞춰 비율을 유지한 채 그린다. 높이는 `너비 × 1040 / 1440`이며 잘라내지 않는다. 로비 최대 너비 520px 기준으로 393px 폰에서는 약 284px 높이가 된다.

```
y   0 ┌──────────────┬─────────────────────────────────────────┐
      │ 왼쪽 벽       │  유리창(x 560~1440, y 40~600)            │
 110  │ ┌──────────┐ │  창살 x=560,780,1000,1220,1440 (두께 16) │
      │ │ 출발 안내판│ │  가로창살 y=300                          │
 370  │ └──────────┘ │  창밖: 하늘 / 원경 도시(y 380~480)        │
      │              │  지평선 horizonY=470, 비행기(x 860~1380)  │
 600  ├──────────────┴─────────────────────────────────────────┤ 바닥 시작
 650  │      벤치 등받이(y 650~800)  좌석 6개                     │
 800  │      벤치 앞면·팔걸이(y 800~905)  ← 앉은 캐릭터를 가림    │
 940  │ ─ ─ ─ ─ 기준선 baselineY=940 (통로·서 있는 발 위치) ─ ─ ─ │
1040  └──────────────────────────────────────────────────────────┘
```

`scene.json`에 들어갈 값이다(플레이스홀더와 실제 그림 모두 이 값을 따른다).

| 항목 | 값 |
|---|---|
| 좌석 x(중심) | 330, 500, 670, 840, 1010, 1180 (id `s0`~`s5`) |
| 기준선 `baselineY` | 940. 걷기, 서기, 앉기 클립 전부 이 선에 발 기준점을 둔다 |
| 화면 밖 등장 지점 | 왼쪽 x = −220, 오른쪽 x = 1660 |
| 안내판 영역 | x 70~520, y 110~370, 5줄 |
| 창문 영역 | x 560~1440, y 40~600 |
| 지평선 `horizonY` | 470 |
| 창문 방향 `windowFacing` | 225° (남서향, 나침반 방위. 북=0, 동=90). 오후 햇살이 들어오고 노을이 창밖으로 보인다 |
| 조명(밤 그림자용) | 바닥 투영점 기준 `[{x:150,y:900,r:520},{x:720,y:620,r:600},{x:1330,y:900,r:520}]` |
| 전경 소품 | 왼쪽 화분(x 0~140, y 700~1040), 오른쪽 캐리어(x 1300~1440, y 820~1040). 들어오는 캐릭터를 잠깐 가린다 |
| 캐릭터 크기 | 서 있을 때 키 약 420(장면 높이의 40%) |

---

## 4. 모듈 구조

### 4.1 파일 배치

```
ui/web/lounge/
  sun.js         태양·달 위치 계산 (순수 함수)
  location.js    위치 결정: 시간대 추정 / 위치 권한 / 디버그 수동값
  lighting.js    태양 고도 → 조명 값 표 보간, CSS 변수 출력
  board.js       대회 목록 → 안내판 줄 데이터 (순수 함수)
  behavior.js    캐릭터 상태 기계 + 행동 선택 (순수 로직, 시드 고정 가능)
  assets.js      scene.json / 캐릭터 manifest 로드, 이미지 디코드
  renderer.js    Canvas 2D 합성
  debug.js       디버그 패널 (?lounge_debug=1 일 때만 로드)
  lounge.js      진입점: 초기화, 루프, 가시성 처리, 로비 연동 API
ui/web/lounge/assets/
  scene.json
  bg/…           배경 레이어(시간대 변형 포함)
  chars/<name>/manifest.json, atlas.webp|png
ui/tools/
  lounge_make_placeholders.py   임시 그림 + manifest 생성 (PIL)
  lounge_check_assets.py        에셋 계약 검사 (6.4절)
  verify_lounge_assets.py       위 두 도구의 자체 시험
  verify_lounge_sun.js
  verify_lounge_lighting.js
  verify_lounge_location.js
  verify_lounge_board.js
  verify_lounge_behavior.js
  lounge_screens.js             Playwright 스크린샷·성능 측정 (개발용)
.github/workflows/lounge-scene.yml   위 검사들을 실행 (쓰기 권한 없음)
```

### 4.2 모듈 형식

번들러 없이 `<script>`로 읽는다. Node 테스트에서도 `require`할 수 있게 아래 형식을 지킨다.

```js
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.T2LoungeSun = api;           // 모듈마다 T2Lounge<이름>
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  /* … */
  return { sunPosition, moonPhase };
});
```

- `sun.js`, `lighting.js`, `board.js`, `behavior.js`는 DOM을 쓰지 않는다. 그래야 Node에서 바로 테스트할 수 있다.
- `location.js`는 `navigator`와 `localStorage`를 인자로 주입받는다(`createLocation({navigator, storage, now, intl})`).

### 4.3 로비 연동 API

`lounge.js`는 `window.T2Lounge`를 노출한다.

```js
T2Lounge.mount(sectionEl)              // lobby.html 로드 후 자동 호출
T2Lounge.setTournaments(list, serverNow) // lobby.js의 loadLobby() 성공 직후 호출
T2Lounge.requestLocation()             // 정확한 위치를 다시 요청한다(보통은 장면이 뜬 뒤 자동으로 한 번 요청한다)
```

- `lobby.js`에서 바꿀 곳은 `loadLobby()`의 `renderCurrent(); renderFeatured(); renderCards();` 뒤에 아래 한 줄을 넣는 것뿐이다.

  ```js
  window.T2Lounge && T2Lounge.setTournaments(catalog, data.server_now);
  ```

- 장면 모듈은 서버 API를 **직접 호출하지 않는다**.

### 4.4 시간 기준

- 조명과 태양 계산은 **기기 현재 시각**(`Date.now()`)을 쓴다. 디버그 모드에서만 덮어쓸 수 있다.
- 안내판 시각 표시는 기존 로비와 같은 `Asia/Seoul` 기준이다. 대회 일정이 한국 시간으로 운영되기 때문이다.

### 4.5 루프

- `requestAnimationFrame`으로 돌리되 **최대 24fps**로 제한한다. 캐릭터 클립은 각자의 fps(기본 12)로 진행한다.
- 다음 경우에는 루프를 멈춘다.
  - `document.hidden`일 때
  - 장면이 화면에서 벗어났을 때(`IntersectionObserver`)
  - `pagehide`가 발생했을 때
- 다시 보이게 됐을 때 멈춰 있던 시간이 60초를 넘으면 행동 AI를 **웜 스타트**(7.4절)로 다시 시작한다.
- 캔버스 해상도는 `CSS 크기 × min(devicePixelRatio, 1.5)`이다.

### 4.6 HTML 구조 (`lobby.html`의 장면 영역 교체)

```html
<section class="airport-scene" id="lounge" aria-label="공항 라운지 일러스트">
  <div class="lounge-fallback" aria-hidden="true"></div>      <!-- 실패하거나 로딩 중일 때 보이는 lobby_hero_night.webp -->
  <canvas class="lounge-canvas" aria-hidden="true"></canvas>
</section>
<div class="airport-scene-copy"><h1>…</h1><p>…</p></div>   <!-- 장면 아래에 둔다. 위에 겹치면 캐릭터 발과 벤치를 가린다 -->
<script src="lounge/sun.js"></script> … <script src="lounge/lounge.js"></script>
```

- 장면은 `aspect-ratio: 1440/1040`이고, 엔진이 준비되면 `#lounge.lounge-ready`가 붙어 캔버스가 정적 그림을 대신한다. 실패하면 `lounge-failed`가 붙고 정적 그림이 남는다.
- 스크립트 순서는 `sun → location → lighting → board → behavior → assets → renderer → lounge`이다. 디버그 모드일 때만 `debug.js`를 동적으로 로드한다.
- 캐시 무효화용 `?v=` 쿼리는 기존 관례대로 붙인다.

### 4.7 실패와 접근성 처리

| 상황 | 동작 |
|---|---|
| Canvas 2D 사용 불가, `scene.json` 로드 실패, 예외 발생 | 캔버스를 숨기고 `.lounge-fallback`(정적 그림)을 보인다. 콘솔에 경고를 한 번만 남긴다 |
| `prefers-reduced-motion: reduce` | 걷기 없이 웜 스타트로 앉은 캐릭터 2명을 `sit_idle` 첫 프레임에 정지시킨다. 조명은 60초마다 갱신한다 |
| 캐릭터 manifest 없음 또는 로드 실패 | 그 캐릭터만 등장시키지 않는다 |
| 특정 클립 없음 | 행동 AI가 그 동작을 고르지 않는다(7장) |

---

## 5. 태양·달·위치

### 5.1 태양 위치 (`sun.js`)

NOAA Solar Calculator 공식(Meeus 간략식)을 쓴다.

```
sunPosition(date: Date, lat: number, lon: number)
  → { elevation: 도(대기굴절 보정 없음), azimuth: 도(북=0, 시계방향) }
```

계산 순서는 아래와 같다. 검증용 Python 구현과 같은 식이다.

1. 율리우스일 `jd = ms/86400000 + 2440587.5`, `T = (jd − 2451545)/36525`
2. 평균황경 L0, 평균근점이각 M, 이심률 e, 중심차 C → 진황경 → 겉보기황경 λ(Ω 보정)
3. 황도경사 ε(Ω 보정) → 적위 δ = asin(sin ε · sin λ)
4. 균시차 EoT(분) = 4·deg(y·sin2L0 − 2e·sinM + 4ey·sinM·cos2L0 − ½y²·sin4L0 − 1.25e²·sin2M), y = tan²(ε/2)
5. 진태양시 = (UTC분 + EoT + 4·lon) mod 1440, 시간각 H = 진태양시/4 − 180
6. 고도 = 90 − acos(sin φ sin δ + cos φ cos δ cos H), 방위각 = (atan2(sin H, cos H sin φ − tan δ cos φ) + 180) mod 360

**테스트 기준값** (`verify_lounge_sun.js`)

일출·일몰은 고도가 −0.833°를 지나는 시각이다. 아래 값은 같은 NOAA 식을 Python으로 구현해 얻은 기준값이며, 한국천문연구원 등 외부 공표값과는 **아직 대조하지 않았다**(허용 오차 ±3분이 그 차이를 흡수한다).

| 장소 | 날짜(현지) | 일출 (방위) | 일몰 (방위) | 최대 고도 | 허용 오차 |
|---|---|---|---|---|---|
| 서울 37.5665, 126.9780 | 2026-03-20 | 06:37 (89.8°) | 18:44 (270.6°) | 52.25° @12:40 | 시각 ±3분, 방위 ±1.5°, 고도 ±0.3° |
| 서울 | 2026-06-21 | 05:11 (59.1°) | 19:57 (300.9°) | 75.87° @12:34 | 〃 |
| 서울 | 2026-12-21 | 07:43 (119.4°) | 17:18 (240.8°) | 29.00° @12:30 | 〃 |
| 레이캬비크 64.15, −21.94 | 2026-06-21 | — | — | 하루 최저 고도 −2.41° (완전한 밤 없음) | ±0.3° |
| 시드니 −33.87, 151.21 | 2026-06-21 12:00 AEST | — | — | 고도 32.69°, 방위 359.15° (북쪽) | ±0.3°, ±1.5° |

추가로 서울 2026-03-20 KST 기준 점검값이다: 12:00 → (51.15°, 164.08°), 18:00 → (7.77°, 263.86°), 06:40 → (−0.11°, 90.27°). 허용 오차는 ±0.3°이다.

### 5.2 달 (장식용 정확도)

- `moonPhase(date)` = ((ms − Date.UTC(2000,0,6,18,14)) / 86400000 / 29.530588853) mod 1. 0은 삭, 0.5는 망이다.
- 달 위치는 근사로 구한다: `sunPosition(new Date(ms − phase·86400000), lat, lon)`. 태양보다 위상만큼 늦게 뜨는 것을 흉내 낸 것이다.
- 그리는 조건은 달 고도 > 0이고 태양 고도 < −4°일 때다. 위상에 맞춰 밝은 면을 그린다. 북반구 기준으로 상현은 오른쪽이 밝다. 남반구(lat < 0)면 좌우를 뒤집는다.

### 5.3 위치 결정 (`location.js`)

상태는 `{lat, lon, source: 'timezone'|'offset'|'geolocation'|'debug', ts}`이다.

1. **시작 시**(권한 요청 없음)
   - 저장된 위치가 있으면 그것을 쓴다.
   - 없으면 `Intl.DateTimeFormat().resolvedOptions().timeZone`을 내장 표에서 찾는다(`source:'timezone'`).
   - 표에 없으면 `lon = −getTimezoneOffset()/4`, `lat = 35`로 둔다(`source:'offset'`).
   - 내장 표에는 최소한 다음 시간대의 도시 좌표를 넣는다: Asia/Seoul, Asia/Tokyo, Asia/Shanghai, Asia/Hong_Kong, Asia/Taipei, Asia/Singapore, Asia/Bangkok, Asia/Ho_Chi_Minh, Asia/Manila, Asia/Jakarta, Asia/Kolkata, Asia/Dubai, Europe/London, Europe/Paris, Europe/Berlin, Europe/Madrid, Europe/Rome, Europe/Moscow, America/New_York, America/Chicago, America/Denver, America/Los_Angeles, America/Toronto, America/Vancouver, America/Sao_Paulo, America/Mexico_City, Australia/Sydney, Australia/Melbourne, Australia/Perth, Pacific/Auckland, Pacific/Honolulu.
2. **정확한 위치 요청:** 장면이 뜬 뒤 방문마다 한 번, 아래 조건을 **모두** 만족하면 브라우저에 위치를 요청한다. 허용 창은 브라우저가 띄운다. 별도 버튼은 두지 않는다.
   - `window.isSecureContext === true`
   - `navigator.geolocation`이 있음
   - 권한 상태가 `'denied'`가 아님(`navigator.permissions.query({name:'geolocation'})`. 이 API가 없으면 '알 수 없음'으로 보고 요청)
   - 저장된 위치의 출처가 `geolocation`이 아님(이미 정확한 위치가 있으면 다시 묻지 않는다)
   - 이전에 거절한 지 30일이 지남
3. **요청 결과**: `getCurrentPosition({enableHighAccuracy:false, maximumAge:86400000, timeout:10000})`을 호출한다.
   - 성공하면 좌표를 **소수 둘째 자리로 반올림**(약 1km)해서 `localStorage['t2_lounge_loc']`에 저장하고, 조명을 즉시 다시 계산한다.
   - 거절되면 거절 시각을 저장해 30일 동안 다시 묻지 않는다. 시간 초과 같은 다른 실패는 기록하지 않고 다음 방문에 다시 시도한다.
   - 어느 경우든 장면은 위치 결과를 기다리지 않고 시간대 추정으로 먼저 그린다.
4. **다음 방문 시** 권한 상태가 `'granted'`이고 저장한 지 24시간이 지났으면, 팝업 없이 위치를 조용히 갱신한다.
5. 좌표는 어디로도 전송하지 않는다. 이 모듈에는 `fetch`나 `XMLHttpRequest`를 쓰지 않는다. 테스트로 확인한다.
6. **참고:** 위치 권한은 HTTPS나 `127.0.0.1`/`localhost`에서만 작동한다.
   - Termux에서 `http://127.0.0.1:8766`으로 열면 작동한다.
   - 다른 기기에서 `http://192.168.x.x`로 열면 `isSecureContext`가 false라서 요청하지 않고, 시간대 추정으로 동작한다.

---

## 6. 에셋 계약 (임시 그림과 실제 그림 공통)

### 6.1 `scene.json`

```json
{
  "placeholder": true,
  "size": [1440, 1040],
  "baselineY": 940,
  "horizonY": 470,
  "windowFacing": 225,
  "characters": ["tiger", "rabbit", "turtle", "penguin"],
  "window": {"x": 560, "y": 40, "w": 880, "h": 560},
  "board": {"x": 70, "y": 110, "w": 450, "h": 260, "rows": 5},
  "seats": [{"id": "s0", "x": 330}, {"id": "s1", "x": 500}, {"id": "s2", "x": 670},
            {"id": "s3", "x": 840}, {"id": "s4", "x": 1010}, {"id": "s5", "x": 1180}],
  "entries": {"left": -220, "right": 1660},
  "lamps": [{"x": 150, "y": 900, "r": 520}, {"x": 720, "y": 620, "r": 600}, {"x": 1330, "y": 900, "r": 520}],
  "floorLight": {"file": "bg/floor_light.png", "anchor": [1000, 600]},
  "layers": [
    {"id": "outside",  "group": "back",  "tint": true,
     "variants": [{"elev": -18, "file": "bg/outside_night.png"}, {"elev": 10, "file": "bg/outside_day.png"}],
     "emission": "bg/outside_emit.png", "emissionKey": "city"},
    {"id": "interior", "group": "back",  "tint": true,
     "variants": [{"elev": -18, "file": "bg/interior_night.png"}, {"elev": 10, "file": "bg/interior_day.png"}],
     "emission": "bg/interior_emit.png", "emissionKey": "lamp"},
    {"id": "benchBack",  "group": "back",  "tint": true, "variants": [{"elev": 0, "file": "bg/bench_back.png"}]},
    {"id": "benchFront", "group": "mid",   "tint": true, "variants": [{"elev": 0, "file": "bg/bench_front.png"}]},
    {"id": "props",      "group": "front", "tint": true, "variants": [{"elev": 0, "file": "bg/props.png"}],
     "emission": "bg/props_emit.png", "emissionKey": "lamp"}
  ]
}
```

- `characters`: 읽어 들일 캐릭터 폴더 이름(`chars/<이름>/`)이다. 필수 클립이 없는 캐릭터는 읽고도 등장시키지 않는다.
- `placeholder`: 임시 그림이면 true. 실제 그림으로 교체할 때 지우거나 false로 둔다(용량 상한이 바뀐다, 6.4절). 캐릭터 manifest에도 같은 값이 들어간다.
- **모든 배경 파일은 1440×1040**이고 알파 채널을 가진다. `interior`는 창문 자리가 투명하다. 그 구멍으로 하늘과 `outside`가 보인다.
- `variants`: 같은 장면을 시간대별로 다르게 칠한 그림이다. 선, 윤곽, 구도는 **완전히 같아야** 한다(6.4절에서 검사). 렌더러는 현재 태양 고도와 가장 가까운 두 변형을 고도 비율로 섞는다. 변형이 하나뿐이면 그것만 쓴다.
- `tint: true`: 조명 표의 `ambient` 색으로 곱하기 틴트를 한다. 단, 변형이 2개 이상인 레이어는 그림 자체에 조명이 칠해져 있으므로 강도를 절반으로 줄인다.
- `emission`: 램프, 도시 불빛, 활주로 유도등만 그린 레이어다. `lighter` 합성으로 더하고, 세기는 조명 표의 `emissionKey` 값(`lamp` 또는 `city`)을 따른다.
- `group`: 캐릭터와의 앞뒤 관계를 정한다(8.2절).
- `floorLight`: 창문 모양 햇빛이 바닥에 떨어진 패치(흰색과 알파)다. 해가 창 쪽에 있을 때만 그린다(8.3절). 이미지는 임의 크기이고, **위쪽 중앙 픽셀**이 `anchor`(장면 좌표)에 놓인다.

### 6.2 캐릭터 `manifest.json`

```json
{
  "name": "rabbit",
  "atlas": "atlas.png",
  "scale": 1.0,
  "mirrorable": false,
  "frames": [{"x": 0, "y": 0, "w": 180, "h": 430, "ax": 90, "ay": 420}],
  "poses": {"walk_r": 0, "walk_l": 8, "stand_front": 16, "sit": 40, "phone": 70},
  "clips": {
    "walk_r":   {"from": "walk_r", "to": "walk_r", "loop": true, "fps": 12, "frames": [0,1,2,3,4,5,6,7], "advance": 13},
    "sit_down": {"from": "stand_front", "to": "sit", "fps": 12, "frames": [30,31,32,33,34,35,36,37,38,40], "laneSwitchAt": 5}
  }
}
```

- `scale`: 아틀라스 픽셀 1개가 장면 논리 좌표 몇 px인지 나타낸다. 실제 그림은 1.0(프레임 높이 약 420px), 임시 그림은 3(프레임 높이 147px)이다. 렌더러는 프레임을 `w·scale × h·scale`로 그린다.
- `frames`: 아틀라스 안의 사각형과 **발 기준점**(`ax, ay`, 사각형 기준 아틀라스 px)이다. 여백을 잘라낸 프레임도 기준점이 같으면 위치가 흔들리지 않는다.
- 기준점의 의미는 이렇다. 서 있거나 걷는 프레임에서는 두 발 사이 바닥점이다. 좌석 관련 클립(돌기, 앉기, 앉은 동작, 일어서기)은 **좌석 앞 기준선 위의 한 점**(`seat.x`, `baselineY`)에 고정된다. 즉 앉는 동작에서 뒤로 물러나 앉는 움직임은 프레임 그림 자체에 들어 있다.
- `poses`: 각 기준 포즈의 대표 프레임 번호다. 클립 이음새 검사에 쓴다.
- `advance`: 걷기 클립에서 프레임마다 실제로 이동하는 논리 px이다. 발이 미끄러지지 않도록 그림의 보폭과 맞춘다. 걷기가 아닌 클립은 0이다.
- `laneSwitchAt`: 이 프레임부터 캐릭터가 벤치 앞면 레이어 **뒤**로 들어간다(`sit_down`). `stand_up`에서는 반대로 이 프레임부터 앞으로 나온다.
- `mirrorable: true`인 경우에만 `walk_l` 등을 `walk_r`의 좌우 반전으로 대신할 수 있다. 옷의 T2 로고처럼 비대칭인 디자인이 있으면 false다.

### 6.3 클립 목록 (포즈 그래프)

기준 포즈(노드)는 `walk_r`, `walk_l`, `stand_front`, `sit`, `phone`, `call`, `eat`, `chat_l`, `chat_r`, `doze`이다.

| 클립 id | from → to | 반복 | 프레임 가이드 | 필수 |
|---|---|---|---|---|
| `walk_r`, `walk_l` | 자기 자신 | ○ | 8 | **필수** |
| `turn_r_front`, `turn_l_front` | walk_r/walk_l → stand_front | | 6 | **필수** |
| `turn_front_r`, `turn_front_l` | stand_front → walk_r/walk_l | | 6 | **필수** |
| `sit_down` | stand_front → sit | | 10 | **필수** |
| `stand_up` | sit → stand_front | | 10 | **필수** |
| `sit_idle` | sit → sit | ○ | 24 (숨쉬기, 눈 깜빡임) | **필수** |
| `phone_in` / `phone_loop` / `phone_out` | sit → phone / phone / phone → sit | –/○/– | 8 / 16 / 8 | 선택 |
| `call_in` / `call_loop` / `call_out` | sit → call / call / call → sit | –/○/– | 8 / 16 / 8 | 선택 |
| `eat_in` / `eat_loop` / `eat_out` | sit → eat / eat / eat → sit | –/○/– | 8 / 24 / 8 | 선택 |
| `sunglasses` | sit → sit | | 20 | 선택 |
| `fix_clothes` | sit → sit | | 18 | 선택 |
| `chat_in_l` / `chat_talk_l` / `chat_listen_l` / `chat_out_l` | sit → chat_l / chat_l / chat_l / chat_l → sit | –/○/○/– | 6 / 16 / 16 / 6 | 선택 |
| `chat_in_r` … `chat_out_r` | 위와 같고 오른쪽 방향 | | | 선택 |
| `doze_in` / `doze_loop` / `doze_out` | sit → doze / doze / doze → sit | –/○/– | 10 / 24 / 10 | 선택 |

필수 9개만 있어도 캐릭터가 등장한다. 선택 클립은 생기는 대로 행동 AI가 자동으로 쓴다.

### 6.4 에셋 검사 (`lounge_check_assets.py`, CI에서 실행)

1. `scene.json`과 manifest의 스키마가 맞는지, 참조한 파일이 모두 있는지 확인한다. 배경 파일 크기는 1440×1040이어야 한다.
2. **변형 정렬 검사:** 같은 레이어의 변형끼리 알파 윤곽이 일치하는지 본다. 알파 > 0.5 영역의 IoU ≥ 0.98이어야 한다. 또 **선화 일치율** ≥ 0.90이어야 한다. 한쪽 변형의 뚜렷한 Canny 에지(임계값 60/150) 중, 다른 쪽 변형의 약한 에지(임계값 15/45)를 3px 팽창한 영역 안에 들어오는 비율이며, 두 방향 중 낮은 값을 쓴다. 색과 조명이 달라 대비가 변해도 통과하고, 선이 4px 이상 어긋나면 걸린다. 검은 배경과 흰 배경 위에 합성한 결과, 그리고 알파 윤곽의 에지를 합쳐서 본다. PR #40에서 생긴 "낮·밤 실루엣 이중 겹침" 같은 문제를 여기서 막는다.
3. **포즈 이음새 검사:** 기준점을 맞춘 뒤 알파 곱한(premultiplied) RGBA 평균 절대 오차를 잰다.
   - 모든 클립: 첫 프레임과 `poses[from]` 프레임의 오차가 ≤ 6/255이어야 한다.
   - 반복하지 않는 클립: 마지막 프레임과 `poses[to]` 프레임의 오차도 ≤ 6/255이어야 한다.
   - 반복 클립: 마지막 프레임 다음에 첫 프레임이 이어지므로 **마지막→첫 프레임 오차**와 **마지막 두 프레임 사이 오차**가 각각 `max(6, 1.25 × 나머지 연속 프레임 간 오차의 최댓값)` 이하여야 한다(마지막 프레임이 `poses[to]`와 같을 필요는 없다).
4. 필수 클립 9개가 모두 있는지 확인한다(없으면 그 캐릭터는 "비활성"으로 표시한다. 오류는 아니다).
5. 필수가 아닌 클립이 있다면 그 from과 to 노드에 도달할 수 있는 경로가 있는지 확인한다(그래프 연결성).
6. 용량 상한: 배경 전체 ≤ 2.5MB, 캐릭터 1명 ≤ 1.5MB. 임시 그림(`scene.json`에 `"placeholder": true`)은 `assets/` 전체 ≤ 1MB이다.
7. 실제 그림은 아틀라스 하나에 모든 클립이 들어가므로 디코드 메모리가 커질 수 있다(캐릭터 1명 약 700프레임 × 420px 높이). 실제 그림 단계에서 클립 그룹별로 아틀라스를 나누는 방안을 정한다(12장).

### 6.5 임시 그림 생성기 (`lounge_make_placeholders.py`)

PIL만 사용하고 결과는 결정적이어야 한다(같은 입력이면 같은 바이트). 6.1~6.3의 계약을 **전부** 채워야 한다.

- **배경:** 낮과 밤 2가지 변형. 벽, 창틀, 바닥, 벤치, 소품을 단순 도형으로 그리고 3장의 구도대로 배치한다. 안내판은 빈 판이다. 원경 도시는 블록 실루엣이다. emission 레이어에는 램프 원과 도시 창문 점을 그린다.
- **캐릭터 4명:** 각자 다른 색의 둥근 실루엣이다. 머리, 몸통, 다리 2개, 귀 같은 특징 1개를 넣는다(토끼 귀, 호랑이 줄무늬, 거북이 등껍질, 펭귄 부리). 모든 클립을 만든다.
  - 걷기는 다리가 교대로 움직이고 몸이 위아래로 흔들린다.
  - 앉기는 몸이 낮아진다.
  - 동작마다 손 위치에 작은 소품 도형을 넣는다(폰은 사각형, 그릇은 반원 등).
  - 프레임에는 글씨를 넣지 않는다(이음새 검사가 정확히 0이 되도록). 클립 id와 프레임 번호는 디버그 오버레이(10장)가 그려 준다.
- 출력은 팔레트 PNG다(알파 정확성 우선). 배경은 색이 256가지 이하라 그대로 저장하고, 캐릭터 아틀라스는 64색으로 줄여 저장한다. 실제 그림이 오면 WebP로 바꿔도 된다.
- 프레임 크기는 논리 240×441이고 아틀라스에는 1/3(80×147px)로 저장한다(`scale: 3`). 아틀라스 열 수는 24이고 발 기준점은 프레임 안 (40, 144)다.
- 점검용: `ui/tools/verify_lounge_assets.py`가 생성기와 검사기를 함께 시험한다(결정성, 클립 전체 세트, 일부러 망가뜨린 에셋을 거부하는지).

---

## 7. 행동 AI (`behavior.js`)

### 7.1 상태

캐릭터마다 아래 상태를 가진다.

```
OFFSCREEN → ENTERING(walk) → TURN_IN → SIT_DOWN → SEATED(활동) → STAND_UP → TURN_OUT → EXITING(walk) → OFFSCREEN
```

- `ENTERING`: 화면 밖에서 예약한 좌석의 x까지 걷는다. 왼쪽에서 들어오면 `walk_r`, 오른쪽에서 들어오면 `walk_l`이다.
  - 걷기는 루프 한 주기(`frames.length × advance`, 아래 `cycle`) 단위로만 끝낼 수 있다. 기준 포즈 `walk_r`/`walk_l`이 루프 첫 프레임이기 때문이다.
  - 그래서 출발 x를 거꾸로 정한다. 왼쪽 등장이면 `startX = seat.x − ceil((seat.x − entries.left) / cycle) · cycle`이다. 즉 등장 지점이거나 그보다 더 바깥이다. 오른쪽 등장도 같은 방식으로 정한다.
  - 루프가 끝난 순간 x가 정확히 `seat.x`가 되고, 여기서 `turn_*_front`로 넘어간다. 걷기 루프 중간에 끊지 않는다.
  - `EXITING`은 x가 반대편 등장 지점 바깥으로 나갈 때까지 걷는다. 마지막 주기를 다 채울 필요는 없다.
- `SEATED`: 아래 활동을 반복하다가 착석 시간이 끝나면 `sit` 포즈로 돌아온 뒤 `STAND_UP`으로 넘어간다.
- 나갈 방향은 가까운 쪽 출구 70%, 반대쪽 30%다.
- **클립 전환은 항상 같은 포즈 노드에서만** 일어난다. 현재 클립의 `to`가 다음 클립의 `from`과 같아야 한다. 이 규칙을 어기는 전환은 코드에서 예외로 막는다.

### 7.2 인원과 등장 간격

| 현지 시각(기기 기준) | 목표 인원 | 다음 등장까지 대기 |
|---|---|---|
| 07:00~23:00 | 2~4명 | 20~70초 |
| 23:00~07:00 | 1~2명 | 60~180초 |

- 같은 캐릭터는 동시에 한 번만 등장한다(캐릭터는 4명뿐이다).
- 좌석은 등장할 때 **예약**한다. 빈 좌석 중에서 고르는데, 이미 앉은 캐릭터 옆자리를 40% 확률로 선호한다(대화가 생기도록).
- 착석 시간은 120~360초다.

### 7.3 앉아 있을 때 활동 선택

현재 활동이 끝나면 가중치에 따라 다음 활동을 뽑는다. 해당 클립이 없는 활동은 가중치를 0으로 둔다.

| 활동 | 기본 가중치 | 조건 / 보정 | 지속 |
|---|---|---|---|
| `idle` (`sit_idle`) | 3 | — | 6~15초 |
| `phone` | 3 | — | 20~60초 |
| `call` | 1 | 23:00~07:00이면 ×0.3 | 15~40초 |
| `eat` | 0.3 | 11:30~13:30, 18:00~20:00이면 3 | 30~60초 |
| `sunglasses` | 1.5 | 태양 고도 > 10°일 때만. 한 번 앉을 때 최대 1회 | 1회 재생 |
| `fix_clothes` | 1 | — | 1회 재생 |
| `doze` | 0.2 | 00:00~05:00이면 3 | 40~120초 |
| `chat` | 4 | 바로 옆 좌석 캐릭터가 `idle` 상태일 때만. 두 캐릭터가 함께 들어간다 | 20~50초 |

- **대화:** 왼쪽 캐릭터는 `chat_*_r`(오른쪽을 봄), 오른쪽 캐릭터는 `chat_*_l`을 쓴다. 4~8초마다 말하기와 듣기를 교대한다. 한쪽이 끝나면 두 캐릭터 모두 `chat_out`으로 돌아간다.
- 반복 클립은 지속 시간이 끝나도 **루프가 끝나는 프레임**까지 재생한 뒤 `_out`으로 넘어간다.
- 활동 지속 시간이 남은 착석 시간보다 길면 남은 시간으로 줄이되, 그 활동의 최소 시간 아래로는 줄이지 않는다.
- **대화 시작 맞추기:** 먼저 대화를 고른 쪽은 `sit_idle` 첫 프레임(= `sit` 포즈)에서 멈춰 기다리고, 옆자리 캐릭터는 자기 `sit_idle` 루프가 한 바퀴 끝나는 시점에 같은 모습으로 멈춘다. 둘 다 멈춘 순간 함께 `chat_in`을 시작한다. 8초 안에 맞춰지지 않으면 대화를 포기하고 원래 활동으로 돌아간다.
- 말하기/듣기 교대는 각자 자기 루프가 끝나는 지점에서 하므로, 교대 순간에 최대 한 루프(약 1.3초) 어긋날 수 있다.

### 7.4 난수와 웜 스타트

- 난수는 시드를 가진 PRNG(mulberry32)를 쓴다. 기본 시드는 `Date.now()`이다. 테스트와 디버그에서는 고정할 수 있다.
- **웜 스타트**(처음 로드할 때, 60초 넘게 멈췄다 돌아왔을 때): 목표 인원의 절반(올림)을 **이미 앉은 상태**로 배치한다. 활동은 `idle`이고 루프 시작 프레임은 랜덤이다. 나머지 인원은 평소 등장 일정을 따른다. 장면이 빈 채로 시작하는 일을 막기 위해서다.
- 인터페이스:

  ```
  createDirector({seed, scene, characters(manifest 목록), clock: ()=>ms, solar: ()=>{elevation}, minuteOfDay?, onEvent?})
  .step(dtMs) → 화면에 있는 캐릭터별 {name, clip, frame, x, lane, mirrored, state, activity, seat}
  .warmStart() → 같은 형식 (모두 다시 앉힌다)
  ```

  - `frame`은 클립 안의 번호(0부터)이고, 아틀라스 프레임은 `manifest.clips[clip].frames[frame]`이다. `mirrored`는 지금은 항상 false다.
  - `seat`는 `scene.seats`의 인덱스이고, 일어나서 나가는 중이라 자리가 비워졌으면 −1이다.
  - 내부 시뮬레이션은 25ms 단위로 고정이라 `dtMs`를 어떻게 쪼개 넣어도 결과가 같다.
  - 시각은 `minuteOfDay()`(없으면 `clock()`의 현지 시각)로 판단한다. 테스트는 이 함수로 하루를 재현한다.
  - 필수 클립 9개가 없는 캐릭터는 등장하지 않는다(`isActive`).
  - `onEvent({type:'clip', t, name, from, to, state, activity, seat})`는 클립이 바뀔 때마다 불린다(테스트와 디버그용).

### 7.5 불변식 (`verify_lounge_behavior.js`)

시드 5개 × 시뮬레이션 24시간(100ms 간격)을 돌린다. 클립 전체 세트와 필수 9개만 있는 세트 두 경우 모두 검사한다.

1. 두 캐릭터가 같은 좌석을 동시에 예약하거나 점유하지 않는다.
2. 모든 전환에서 이전 클립의 `to` = 다음 클립의 `from`이다.
3. 없는 클립은 한 번도 재생되지 않는다.
4. `SEATED`는 착석 시간 + 2분을, 그 밖의 상태는 2분을 넘기지 않는다(멈춤 없음).
5. 인원이 0명인 시간이 연속 3분을 넘지 않는다(07:00~23:00).
6. 걷기 중 x는 `advance`만큼만 변하고, 목표 좌석 x에서 멈춘다(오차 0).
7. `sunglasses`는 태양 고도 ≤ 10°일 때 재생되지 않는다.

---

## 8. 렌더링 (`renderer.js`)

### 8.1 조명 표 (`lighting.js`)

입력은 태양 고도 `h`(도)다. 아래 키 사이를 **선형 보간**하고 양 끝은 고정한다. 색은 sRGB 16진수다.

| h | zenith | horizonSun | horizonAway | ambient | ambientStr | sunColor | lamp | city | stars |
|---|---|---|---|---|---|---|---|---|---|
| −18 | #070b1c | #121a33 | #0e1530 | #4a5a8c | 0.55 | #000000 | 1.00 | 1.00 | 1.00 |
| −12 | #0d1430 | #26305a | #1d2650 | #55608f | 0.50 | #000000 | 1.00 | 1.00 | 0.75 |
| −6 | #1b2a5c | #b0566a | #3a3f78 | #6b6a9a | 0.40 | #000000 | 1.00 | 0.90 | 0.25 |
| −2 | #2d3f7c | #ff7a45 | #6d5f99 | #a77a8a | 0.30 | #ff6a3a | 0.90 | 0.60 | 0.00 |
| 2 | #4a6db0 | #ff9b55 | #9a8cbc | #e0a27e | 0.20 | #ff8a4a | 0.70 | 0.30 | 0.00 |
| 8 | #5b8fd6 | #ffc985 | #b3c8e6 | #ffd9b0 | 0.12 | #ffb36b | 0.40 | 0.10 | 0.00 |
| 20 | #4b8fe0 | #d9ecff | #c2dcf7 | #fff4e6 | 0.04 | #ffe2b8 | 0.15 | 0.00 | 0.00 |
| 45 | #3a86e3 | #d2e8ff | #c8e1fa | #ffffff | 0.00 | #fff4e0 | 0.10 | 0.00 | 0.00 |

추가로 계산하는 값:

- `dayness = smoothstep(−8, 8, h)`
- **CSS 변수 출력:** `<html>`에 아래 변수를 쓴다. 로비 배경과 헤더 색이 장면과 함께 바뀐다(PR #40과 같은 변수 이름이다).
  - `--airport-surface-top` = mix(#122e32, #3c6762, dayness)
  - `--airport-surface-mid` = mix(#061b1f, #113c3c, dayness)
  - `--airport-surface-bottom` = mix(#081f22, #0f2b30, dayness)
- 조명 값은 15초마다 다시 계산한다. 디버그 모드에서 시간을 움직이면 즉시 다시 계산하되, 최대 초당 10회로 제한한다.
- **테스트:** 각 키 고도에서의 정확한 값, 키 사이 중간값, 범위 밖에서 끝값으로 고정되는지를 확인한다.

### 8.2 그리는 순서

1. **하늘**(매 프레임, 창문 영역만 클립).
   - 세로 그라디언트: 위는 `zenith`, `horizonY`에서는 지평선색이다. 지평선색은 x 위치에 따라 `horizonSun`과 `horizonAway`를 섞는데, 태양이 화면상 있는 쪽(8.3절의 `rel`)에 가까울수록 `horizonSun` 비중이 커진다.
   - 별: 시드 고정 점 120개, 알파 = `stars`. 별 이미지는 조명 갱신 때만 다시 만든다.
   - 해와 달 원판.
   - 구름: 반투명 타원 3~5개가 천천히 흐른다(초당 4px). 구름 색은 지평선색과 흰색을 섞는다.
2. **back 캐시**: `outside` → `interior` → `benchBack` → 안내판 글자(9장)
3. **바닥 햇빛 패치** (8.3절)
4. **그림자** (8.3절, 모든 캐릭터)
5. **lane = seat**인 캐릭터 (좌석 x 순서)
6. **mid 캐시**: `benchFront`
7. **lane = aisle**인 캐릭터 (x 순서)
8. **front 캐시**: `props`
9. 디버그 오버레이 (디버그 모드일 때만)

캐시 규칙:

- back, mid, front 캐시는 캔버스와 같은 크기의 오프스크린 캔버스다.
- **다시 만드는 경우:** 조명 값이 바뀌었을 때(고도 변화 > 0.05°), 안내판 데이터가 바뀌었을 때, 1분 단위 시각이 바뀌었을 때, 캔버스 크기가 바뀌었을 때.
- **레이어 하나를 캐시에 그리는 순서:** 변형 2개를 고도 비율로 섞음(`globalAlpha`) → 틴트 → emission을 `lighter` 합성으로 `alpha = 해당 키 값`만큼 더함.

**틴트 방법** (캐릭터에도 같은 방법을 쓴다)

```
off.clear();  off.drawImage(src);
off.globalCompositeOperation = 'multiply';    off.fillStyle = mix('#ffffff', ambient, strength); off.fillRect(…);
off.globalCompositeOperation = 'destination-in'; off.drawImage(src);   // 알파 복원
off.globalCompositeOperation = 'source-over';
```

### 8.3 해·그림자·바닥 햇빛

**창문 기준 상대 방위**

- `rel = wrap180(sunAzimuth − windowFacing)`. 0이면 해가 창 정면 바깥에 있다는 뜻이다.
- **해의 화면 위치**
  - x = `window.x + window.w/2 + (rel/60)·(window.w/2)`
  - y = `horizonY − h·12`
  - |rel| ≤ 60이고 −2 < h < 40일 때만 그린다.
  - 반지름은 26이고, 바깥 글로우는 반지름 90에 `sunColor`, 알파 0.35다.
- **달**도 같은 식으로 위치를 구한다. 달 고도와 달 방위를 쓴다.

**직사광 판정**

- `direct = clamp(cos(rel), 0, 1) · smoothstep(0, 6, h)`. 해가 창 쪽에 있고 지평선 위에 있을 때만 0보다 크다.

**바닥 햇빛 패치** (`direct > 0`일 때)

- `floorLight` 이미지를 쓴다.
- 변환은 `translate(anchor) · skewX(clamp(−rel·0.8, −40, 40)°) · scale(1, clamp(0.25/tan(h), 0.15, 1.0))`이다.
- 색은 `sunColor`, 합성은 `soft-light`, 알파는 `0.45·direct`다.

**캐릭터 그림자** (순서대로 겹친다)

1. **접지 그림자:** 항상 그린다. 발 기준점 중심의 타원(가로 = 프레임 너비 × 0.45, 세로 18), 검정, 알파 0.30이다. 레이어는 `seat`와 `aisle` 모두 같다.
2. **햇빛 그림자:** `direct > 0`일 때 그린다.
   - 현재 프레임의 실루엣을 검정으로 채우고, 1/4 해상도로 그린 뒤 확대해서 부드럽게 만든다.
   - 발 기준점을 축으로 변환한다. 방향은 화면 아래쪽(창 반대편)이고 x 기울기는 `−sin(rel)`, 세로 길이 배율은 `clamp(1/tan(h), 0.3, 3.0)·0.35`다.
   - 알파는 `0.35·direct`다.
   - 그림자 캔버스는 `(클립, 프레임)` 단위로 캐시한다.
3. **램프 그림자:** `lamp > 0.5`이고 `direct < 0.2`일 때 그린다.
   - 발 기준점에서 가장 가까운 램프(거리 < r)를 고른다.
   - 램프 바닥점에서 발로 향하는 방향으로 길이 배율 0.6·0.35, 알파 `0.22·lamp·(1 − 거리/r)`로 그린다.

**캐릭터 틴트**

- 8.2절의 틴트 방법에 `ambient`와 `ambientStr`를 쓴다.
- 결과는 `(클립, 프레임, ambient 16진수)` 단위로 캐시하고, 조명이 바뀌면 캐시를 비운다.
- (선택) **림라이트:** `direct > 0.3`이면 실루엣을 빛 방향으로 2px 이동한 것에서 원본 실루엣을 빼서 가장자리를 만들고, `sunColor`, 알파 `0.5·direct`로 덧그린다. 1단계 필수는 아니다.

### 8.4 성능 기준

- 393×852 뷰포트, DPR 2.75(내부적으로 1.5로 제한) 기준으로 헤드리스 Chromium에서 측정한다. 엔진 내부 `performance.now()` 기준 **프레임당 렌더 시간 평균 ≤ 6ms, 95분위 ≤ 12ms**를 지킨다.
- 측정과 스크린샷 도구는 `lounge_screens.js`다. Playwright를 쓰고, 이 개발 환경에서는 `executablePath: '/opt/pw-browsers/chromium'`을 사용한다.
- 스크린샷 시점은 서울 2026-03-20 03:00 / 06:40 / 12:00 / 18:40 / 21:00 다섯 개다. 디버그 시간을 덮어써서 찍는다.

---

## 9. 출발 안내판 (`board.js`)

```
boardRows(tournaments, serverNowSec, nowMs) → [{flight, dest, time, status, mine}] × 5
```

- **실제 대회 줄:** 상태가 `finished`나 `retired`인 대회는 뺀다. `starts_at` 오름차순으로 최대 5개를 고른다.
  - `flight` = `'T2 ' + (id의 FNV-1a 해시 % 900 + 100)`. 같은 대회는 항상 같은 번호가 나온다.
  - `dest`: 대회 종류(`key`, 없으면 `fmt`)로 정한다.

    | key | dest |
    |---|---|
    | standard | SEOUL |
    | turbo | TOKYO |
    | deep | NEW YORK |
    | hyper | SINGAPORE |
    | lowbuyin | BANGKOK |
    | main | PARIS |
    | 그 외 | T2 CITY |

  - `time`: `starts_at`을 `Asia/Seoul` 기준 `HH:MM`으로 표시한다.
  - `status`

    | 대회 상태 | 표시 |
    |---|---|
    | `scheduled`, 등록 열림, 시작까지 30분 이내 | BOARDING |
    | `scheduled`, 그 외 | ON TIME |
    | `late_registration` | LAST CALL |
    | `closed` | DEPARTED |

  - `mine`: `my_entry`가 있고 `cancelled`가 아니면 true다. 줄 왼쪽에 금색 점을 표시한다.
- **가상 줄:** 실제 대회 줄이 5개보다 적으면 나머지를 가상 항공편으로 채운다.
  - 도시 목록: OSAKA, HONG KONG, SYDNEY, LONDON, HAWAII, DUBAI, TAIPEI, VANCOUVER
  - 시각: 마지막 줄 시각(없으면 현재 시각)에 25분 간격으로 더한다. 5분 단위로 올림한다.
  - 상태는 ON TIME, 편명은 `'TT ' + 3자리`다.
  - 도시와 편명은 **날짜 + 줄 번호**로 시드를 정해서, 같은 날에는 바뀌지 않게 한다.
- **그리기:** 안내판 영역에 5줄을 그린다.
  - 열 비율은 편명 0.22 / 도시 0.34 / 시각 0.18 / 상태 0.26이다.
  - 글꼴은 `bold monospace`, 줄 높이의 0.55배다.
  - 색은 상태별로 다르다: 시각 #ffd27a, BOARDING #7dffb0, LAST CALL #ff9d6a, DEPARTED #8a97a6, 그 외 흰색.
  - 안내판은 자체 발광이므로 **틴트하지 않는다**.
- 테스트 입력으로 `tournament_store.catalog()`의 실제 필드(`id`, `key`, `starts_at`, `status`, `registration_open`, `my_entry`)를 흉내 낸 샘플 데이터를 쓴다. 상태 표시, 줄 채우기, 편명이 매번 같은지를 확인한다.

---

## 10. 디버그 모드 (`debug.js`)

**켜는 방법:** URL에 `?lounge_debug=1`을 붙이거나, `localStorage['t2_lounge_debug'] = '1'`을 설정한다. 기본값은 꺼짐이다.

장면 아래에 접을 수 있는 패널이 생긴다.

- 날짜와 시각 슬라이더(1분 단위), "현재 시각" 버튼
- 위치 프리셋: 서울, 레이캬비크, 시드니, 직접 입력
- 시간 배속: 1× / 60× / 600×
- 시드 입력과 "다시 시작"
- 오버레이 표시: 좌석, 기준선, 발 기준점, 레이어 경계, 클립 id·프레임
- 캐릭터별로 강제할 활동 선택
- 현재 값 표시: 태양 고도·방위, `direct`, `lamp`, 위치 출처

디버그 모드에서도 위치를 전송하지 않는다. 직접 입력한 위치는 저장하지 않는다.

---

## 11. 작업 순서와 완료 기준 (1단계)

순서대로 진행하고, 각 단계의 테스트가 통과하면 커밋한다. 커밋 메시지 접두어는 `lounge:`다.

| 단계 | 작업 | 완료 기준 |
|---|---|---|
| 1 | `sun.js` + `verify_lounge_sun.js` | 5.1절 표의 모든 값이 허용 오차 안에 든다 |
| 2 | `lighting.js` + 테스트 | 8.1절 키 값 정확, 보간과 끝값 고정 확인 |
| 3 | `location.js` + 테스트 | 시간대 표, 오프셋 대체, 반올림, 24시간 갱신, 거절 처리, 보안 컨텍스트가 아닐 때 요청하지 않음, 네트워크 API 미사용(소스에 `fetch`와 `XMLHttpRequest` 없음) |
| 4 | `board.js` + 테스트 | 9장 규칙 전부 |
| 5 | `lounge_make_placeholders.py`, `scene.json`, 캐릭터 4명 manifest, `lounge_check_assets.py` | 검사기가 임시 그림에서 통과한다. 일부러 어긋나게 만든 변형과 끊긴 클립을 **거부**하는지 확인한다 |
| 6 | `behavior.js` + 테스트 | 7.5절 불변식 7개가 시드 5개 × 24시간 × 클립 세트 2종에서 모두 통과 |
| 7 | `assets.js`, `renderer.js`, `lounge.js` | 로비에 장면이 뜨고, 캐릭터가 걸어 들어와 앉고 활동하다가 나간다. 4.7절 실패 처리가 동작한다 |
| 8 | 로비 통합: `lobby.html`과 `lobby.css` 정리, `lobby.js` 한 줄 추가, 2장 삭제 목록 처리 | 기존 로비 기능(대회 카드, 탭, 참가 시트, 지갑, 프로필)이 그대로 동작한다. `node --check`로 모든 JS 문법 통과 |
| 9 | `debug.js` | 10장 기능이 모두 동작한다 |
| 10 | `lounge_screens.js`, `lounge-scene.yml`, `preview_airport_termux.sh` 갱신 | 8.4절 성능 기준 충족. 스크린샷 5장을 `docs/lounge/`에 커밋한다 |

**CI (`lounge-scene.yml`)**

- 트리거: `ui/web/lounge/**`, `ui/tools/*lounge*`, 이 워크플로 파일이 바뀐 push.
- `permissions: contents: read`
- 실행: Node 20 + Python 3.12(Pillow, numpy, opencv-python-headless)로 4.1절의 verify 스크립트 5개와 `lounge_check_assets.py`

---

## 12. 나중 단계 (그림 제작, 보류 중)

자금이 확보되면 진행한다. 순서와 원칙만 적어 둔다.

1. **구도 원화:** 3장 좌표계에 맞춰 넓은 라운지 배경을 다시 그린다. 가로 1440 기준으로, 레이어별로 분리하고 안내판은 빈 판으로 그린다.
2. **시간대 변형:** 밤과 낮은 필수다. 노을(h ≈ 2)과 블루아워(h ≈ −6)는 선택이다. 원화의 선을 고정하고 색과 빛만 바꾼다. 6.4절 정렬 검사를 통과해야 한다.
3. **캐릭터 설정화:** 정면, 3/4, 옆, 뒤 모습을 그린다. 조명은 **평평하게** 해야 한다. 그림에 빛이 박혀 있으면 엔진의 조명과 충돌한다.
4. **기준 포즈 정지화:** 6.3절 노드별로 그린다.
5. **동작 생성:** 이미지→영상 AI의 첫 프레임·끝 프레임 지정 기능으로 클립을 만든다(조사 시점 후보: Kling 3.0, Veo 3.1 Fast, Wan). 배경은 **마젠타 #FF00FF 단색**으로 한다. 거북이가 초록색이라 초록 배경은 쓰지 않는다.
6. **후처리 도구** (아래 도구는 이때 만든다)
   - 프레임 추출 → 12fps로 정리 → 배경 제거(크로마키 + BiRefNet으로 가장자리 정리)
   - 발 기준점 정렬 → 아틀라스 패킹 → `manifest.json` 생성
   - 6.4절 검사
7. **시범 1명**(토끼, 필수 9클립)으로 품질을 판정한 뒤 나머지를 진행한다.
8. 실제 그림을 넣을 때는 서버 정적 파일의 `no-store` 헤더 때문에 매번 다시 내려받게 된다. 이때 `lounge/assets/` 아래 파일명에 버전을 붙이고 캐시 헤더를 따로 주는 방안을 검토한다(서버 변경이므로 별도 승인이 필요하다).
