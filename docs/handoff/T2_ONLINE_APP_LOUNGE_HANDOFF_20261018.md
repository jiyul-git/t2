# T2 온라인 계정·안드로이드 앱·라운지 장면 인수인계

작성: 2026-10-18 · 작성 시점 저장소: 브랜치 `claude/t2-ui-changes-dobpqd`, 마지막 푸시 커밋 `beeb2f4f`
대상: 2026-10-17~18 세션(온라인 계정, 안드로이드 앱, 게임 화면 손질, 로비 라운지 장면)을 이어받는 담당자.
이 문서만 읽고 이어갈 수 있게 적었다. 포커 엔진·전략 쪽 인수인계는 `docs/handoff/T2_T3_HANDOFF_20261010.md`에 따로 있다.

상태 표기: **확인함**(이번에 실제로 실행·열어 봄), **보고만**(작업자 보고, 재확인 안 함), **미확인**(확인하지 못함), **보류**(하지 않기로 했거나 아직 시작 안 함).

---

## 0. 먼저 읽을 것

### 0-1. 사용자와 일하는 규칙 (확인함)
- 답변은 **한국어**, 커밋 메시지도 한국어. 사용자는 폰(삼성, 털묵스 + 안드로이드 앱)으로 직접 확인한다. 화면은 390×844 기준으로 본다.
- 사용자는 비개발자에 가깝다. 명령은 **한 줄씩 붙여 넣을 수 있게** 주고, 스크린샷으로 결과를 받는다.
- 사용자가 "괜찮다"고 하기 전에는 미리보기·임시 설정(`scene.json`의 `preview`)을 지우지 않는다.
- **비밀키는 절대 요청·저장하지 않는다**(SSH 개인키, OCI API 키 등). 사용자가 이미 한 번 OCI API 개인키를 스크린샷으로 노출했으므로 **키 교체를 안내했고, 교체 여부는 미확인**이다(7장).
- PR은 사용자가 요청할 때만 만든다. 이번 세션에서 PR #41(라운지 승격), #42(프로필 서버 저장 + 게이트웨이 + 로그인 화면)가 master에 합쳐졌다.
- 커밋은 `Co-Authored-By` / `Claude-Session` 줄로 끝낸다(시스템 안내문 기준). 푸시는 `git push -u origin <브랜치>`.
- 종료 때 Stop hook이 "커밋하지 않은 변경이 있다"고 계속 알린다. 백그라운드 에이전트가 쓰는 중간 파일이면 올리지 말고 끝난 뒤 검토·시험하고 올린다.

### 0-2. 저장소·브랜치 현황 (확인함)
- master 머리: `4f6cf100` (#42). 이 브랜치는 master보다 **10커밋 앞**이고 **아직 master에 합치지 않았다**(PR 없음). 합칠 때 사용자 확인 후 새 PR을 만든다.
- 브랜치에만 있는 커밋(오래된 순):
  1. `1ff04f5c`, `3913c253` 계정·개인정보 설계와 구현(열린 가입, 계정 삭제, 관리 도구)
  2. `fe570058` 안드로이드 앱 + APK 빌드 워크플로
  3. `1bf1e747` 로그아웃 501 수정, 로비 창을 떠 있는 카드로, 앱 아이콘 여백
  4. `a4dbf53a`, `3c5eab3b` 게임 화면(테이블 모양은 되돌림, 위쪽 좌석·금테 이름표는 유지)
  5. `3c035225`, `a1108e44` 토끼·거북이 걷기, 걷는 캐릭터·비행기 무작위 일정
  6. `f138f5f7` 눈 깜빡임·표정·걸음 흔들림
  7. `beeb2f4f` 앉기(소파에 앉기, 다리 보이게)
- 시험 상태(마지막 푸시 기준, 확인함): 라운지 시험 전부 통과, `verify_ui.py` 통과, 게이트웨이 시험 120개 통과.
- **master에 원래 실패하던 시험 2개**가 있다(이번 작업과 무관, 보고만): `verify_clock_ui`, `verify_vclock_session`.

### 0-3. 최근에 끝낸 작업 (소파에 정밀하게 맞추기)
사용자 피드백 요지: "보내준 사진만 봐도 여러 개 보인다. 의자랑 더 정교하게 붙여야 한다. 의자 방향과 몸 방향을 고려해 앉혀야 한다. 레이어 문제도 보인다."
이 작업은 끝났고 시험도 통과했다(커밋은 이 문서 다음 커밋을 볼 것). 내용:
- 소파 방석을 그림에서 재서 좌석을 다시 정했다: 왼쪽 소파 정면 3방석 중 앞의 2개(s0, s1), 오른쪽 소파는 왼쪽 앞을 향해 비스듬함(s2, s3). `scene.json` 좌석마다 엉덩이 접촉점 `cx, cy`, `facing`(f 정면 / l 3/4 왼쪽), `scale`, `tilt`, `blocks`가 있다.
- **캐릭터가 방석보다 넓어서 소파마다 한 명만 앉는다**(`blocks`로 이웃 좌석을 막음). 장면 전체로 최대 2명.
- 앉은 그림은 마지막 발이 아니라 **엉덩이 접촉점** 기준으로 놓는다. 방향별 그림은 `<id>@l` 같은 이름. 감독은 좌석 방향에 맞는 클립 세트와 활동만 쓰고, 맞는 그림이 없는 자리에는 앉히지 않는다(예: 정면 자리에는 거북이가 앉지 않음, 호랑이는 정면에서 폰 없음, 토끼는 정면에서 통화 없음).
- 레이어: 소파 → 소파 앞면 → 방석 위 접촉 그림자 → 앉은 캐릭터(먼 자리부터) → **소파 팔걸이 레이어(`bg/sofa_arms_*.webp`, 새로 오려 냄)** → 통로 걷는 캐릭터. 모든 반투명 겹침을 없애고 늘이기·줄이기로 가린 즉시 교체로 바꿨다.
- 이전 커밋(`beeb2f4f`)에 이미 있던 버그를 같이 고쳤다: 뛰어오르는 프레임의 아틀라스 사각형이 옆 그림으로 번져 호랑이 머리가 비쳤다 → 프레임에 여백을 주고 검사기에 "프레임 사각형 겹침" 규칙과 시험을 추가했다.
- 용량: 호랑이 1.09MB, 토끼 0.78MB, 거북이 0.62MB(상한 1.5MB). 디코드 메모리 합계 약 44MB.

남은 약점(작업자 보고 + 눈으로 확인):
- 뛰어오른 꼭대기에서 서 있는 그림이 앉은 그림으로 한 프레임에 바뀐다(0.08초). 늘인 모양으로 가렸지만 자세히 보면 보인다.
- 오른쪽 소파(s2, s3)에서는 걷던 모습(캐리어·폰 든 채)으로 뛰어올라 물건 없이 내려앉는다.
- 정면 자리(s0, s1)는 종이 뒤집기 전환, 활동 종류가 적다.
- 호랑이가 s2에서 한쪽 다리를 옆으로 길게 뻗는 자세(과장돼 보임). s3 거북이 등껍질·토끼 꼬리가 그림 오른쪽 끝에서 약 10px.
- 어두운 소파 위에서 흰 시트를 오린 옅은 가장자리가 캐릭터 둘레에 조금 보인다.
- 앉은 그림이 걷는 그림보다 작게(0.8~0.88) 그려진다.

---

## 1. 온라인 계정과 게이트웨이

### 1-1. 구조 (확인함, 코드 읽음)
- `gateway/gateway.py`(표준 라이브러리만): 구글 ID 토큰 확인 → 세션 쿠키 → **사용자마다 `ui_server`를 따로 띄워** 프록시. 게임 서버는 전역 상태 하나뿐이라 이렇게 했다. 설계 근거는 `docs/APP_DESIGN.md`, 개인정보 설계는 `docs/ACCOUNT_DATA.md`.
- 계정은 `accounts.json`(버전 2, 상태 pending/active/disabled, 구글 `sub` → 무작위 uid). 이메일은 이 파일에만 있고 사용자 폴더에는 없다. 옛 `users.json`은 첫 실행 때 자동 이전한다(`.v1.bak` 남김).
- 설정(`gateway/gateway.dev.json` 참고): `signup_mode`(`open` 기본 / `invite`), `allowed_emails`(invite일 때만), `max_accounts`(기본 20), `max_backends`, `idle_seconds`, `google_client_ids`, `dev_login`(127.0.0.1 전용), `secure_cookie`, `backup_dir`.
- 화면 흐름 `gateway/login.html`: 로딩 → 구글 로그인(앱 안에서는 `window.T2App.signIn()` → `window.t2SignIn(token)`) → 회원가입(닉네임·캐릭터 9종·동의) → 로비. 가입 전에는 게임 화면과 `/api/*`가 막힌다.
- 로비 설정 시트에 "내 계정"(이메일, 로그아웃, 계정 삭제 — "삭제" 입력 확인)이 있다. 게이트웨이 뒤에서만 보인다.
- 관리 도구 `gateway/admin.py`: `list`, `disable`, `enable`, `delete`, `backup`(SQLite 백업 API로 안전 사본, 7개 보관).
- 고친 버그: 로그아웃 후 `Error 501 Unsupported method ('{}GET')` — 응답하면서 읽지 않은 요청 본문이 같은 연결의 다음 요청에 붙던 문제. `_handle`에서 남은 본문을 읽어 버린다(시험 있음).

### 1-2. 사용자 쪽 실행 (털묵스, 확인함 — 사용자가 직접 돌려 봄)
사용자는 **털묵스 자체**에서 돌린다(우분투/proot 없음). 저장소는 `~/t2`에 있다.
```
cd ~/t2
git fetch origin claude/t2-ui-changes-dobpqd
git checkout -q FETCH_HEAD
termux-wake-lock
pkill -f gateway.py
python3 gateway/gateway.py --config gateway/gateway.dev.json
```
- 포트 8080에 이미 떠 있으면 `Address already in use`가 나온다 → `pkill -f gateway.py` 후 재시작.
- 데이터: `~/t2_online/users/<uid>/`, `~/t2_online/run/<uid>/`, `~/t2_online/gateway/`.
- 예전 털묵스 칩(`~/t2_ui_run` 쪽)은 새 계정과 **따로**다. **계정으로 옮기기는 하지 않았다(보류)**. 옮길 때는 기존 지갑 이동 규칙(`personal_data.py`)대로, 덮어쓰지 말고 옮긴다.

### 1-3. 아직 안 된 것
- **구글 로그인 설정 없음**(`google_client_ids` 비어 있음). 지금은 `dev_login`으로만 입장. 5장 참고.
- 공개 서버 배포·HTTPS·자동 재시작·매일 백업 스케줄 — 모두 **보류**(4장).

---

## 2. 안드로이드 앱 (`android/`)

### 2-1. 구조 (확인함)
- Kotlin 액티비티 하나 + 전체 화면 WebView. 주소창·상태바·내비게이션 바 없음(가장자리 쓸면 잠깐 표시). 뒤로 가기, 연결 끊김 화면("다시 연결", "서버 주소 바꾸기"), 키보드가 입력칸을 가리지 않게 `adjustResize`/인셋 처리.
- 구글 로그인은 WebView 안에서 막히므로 Credential Manager로 받아 `window.t2SignIn(idToken)`으로 넘긴다(`BuildConfig.WEB_CLIENT_ID` 필요).
- 네트워크: https만, 같은 폰의 `127.0.0.1`/`localhost`는 http 허용(`network_security_config.xml`).
- 아이콘: 짙은 초록 바탕에 금색 ♠T2(`drawable-nodpi/ic_launcher_fg.png`, 어댑티브).

### 2-2. 빌드·배포 (확인함)
- `.github/workflows/android-apk.yml`: `android/**` 변경 시 빌드 → 릴리스 `android-latest`에 `t2.apk` 게시. 받는 주소: `https://github.com/jiyul-git/t2/releases/download/android-latest/t2.apk` (사용자가 이미 설치해 봄).
- 저장소 변수/비밀값(전부 **아직 미설정**): 변수 `T2_SERVER_URL`(기본 `http://127.0.0.1:8080`), `T2_WEB_CLIENT_ID`; 비밀값 `T2_KEYSTORE_B64`, `T2_KEYSTORE_PASSWORD`. 없으면 Actions 캐시의 시험용 서명 키를 쓴다 — 정식 키로 바꾸면 사용자가 앱을 지우고 다시 깔아야 한다.
- 안드로이드용 구글 클라이언트 ID에 필요한 **서명 키 지문(SHA-1)** 은 Actions 실행 요약에 출력된다.
- 개발 환경에서 Android SDK를 받을 수 없어(dl.google.com 차단) 로컬 빌드는 못 한다. 빌드 검증은 Actions로만 한다.

### 2-3. 앞으로
정식 서명 키 생성(사용자 비밀값에 한 번 넣기), 서버 주소 변수 설정, 구글 클라이언트 ID 연결 후 재빌드. 앱 화면은 서버에서 오므로 UI 수정은 앱 재설치 없이 반영된다.

---

## 3. 로비 UI·게임 화면 (확인함)

- 로비 창(대회 정보·프로필·지갑·계정 삭제): 가장자리에서 떨어진 둥근 카드, 뒤 배경 어둡게·흐리게, 창이 떠 있는 동안 뒤 화면은 스크롤·터치 안 됨, 창 밖을 누르면 아래로 내려가며 닫힘(`ui/web/lobby.{html,css,js}`의 `showSheet/hideSheet/lockPage`).
- 게임 화면(`ui/web/{theme.css,app.js}`): 위쪽(먼 쪽) 좌석을 `slotPos`에서 바깥으로 올림(UTG·BB가 레일에서 더 벗어남), 이름표·팟·상단 바·버튼을 어두운 유리 + 금색 테두리로, 레이즈 버튼 금색. **테이블 모양·레일은 사용자 요청으로 이전(둥근 사각형 계열)으로 되돌렸다.**
- 폰 비율에 따른 차이: 좌석은 % 좌표, 테이블은 고정 픽셀 여백이라 비율에 따라 거리가 조금 달라진다. 5가지 비율(360×740 … 430×932)에서 크게 어긋나지 않음을 확인했다.
- 캐시 번호: `index.html`의 `theme.css?v`, `app.js?v`, `lobby.html`의 lounge js 버전들. 파일을 고치면 올릴 것.

---

## 4. 서버 호스팅 (Oracle Cloud) — 미완, 상당 부분 **미확인**

대화 기록 기준(보고만):
- 홈 리전 도쿄(ap-tokyo-1). 작은 x86 인스턴스 `T2`(E2.1.Micro, 1GB RAM, Oracle Linux 9, 사용자 `opc`, IP 168.110.7.22), 스왑 2GB 추가, oracle-cloud-agent 비활성화.
- 원래 목표인 ARM A1(4 OCPU/24GB)은 "Out of host capacity"로 실패. `~/grab.sh`가 nohup으로 60초마다 재시도(로그 `~/grab.log`). **지금 잡혔는지 미확인** — `tail ~/grab.log` 확인.
- 유료 전환은 카드(토스 체크카드) 승인 거절로 실패. 138.19 SGD 사전승인이 보였는데 자동 취소될 가능성이 높다고 안내함(해결 여부 미확인).
- 사용자의 Wi-Fi는 22번 포트를 막아 SSH는 모바일 데이터로만 된다. SSH 키 `~/.ssh/t2.key`는 사용자 폰 털묵스에 있다.
- **노출된 OCI API 개인키는 교체해야 한다**(새 키 생성 → `~/.oci/config` 지문 갱신 → 옛 키 삭제). 교체했는지 미확인.
- 배포 계획(전부 **보류**): 서버에 게이트웨이 설치 + 자동 재시작(systemd) + Cloudflare Tunnel로 https 주소 + 매일 `admin.py backup`. 1GB RAM에서는 동시에 띄우는 게임 서버 수(`max_backends`)를 작게 잡아야 한다.

---

## 5. 구글 로그인 설정 (사용자가 직접, 안내만 함)

1. 구글 클라우드 콘솔에서 프로젝트 → OAuth 동의 화면 → 클라이언트 ID 2개 생성: **웹**용, **안드로이드**용(패키지 `com.t2.lounge` + 위 SHA-1).
2. 게이트웨이 설정 `google_client_ids`에 두 ID를 넣고, 저장소 변수 `T2_WEB_CLIENT_ID`에 웹용 ID를 넣는다.
3. APK 재빌드. 화면을 보면서 같이 하는 방식으로 안내했다(오라클 때처럼 스크린샷 주고받기).

---

## 6. 라운지 장면 (로비 위쪽 공항 일러스트)

설계서는 `docs/LOUNGE_SCENE_DESIGN.md`(문서와 코드가 다르면 문서가 기준 — 단, 이번 작업 일부는 문서가 최신이 아닐 수 있으니 날짜 붙은 절을 읽을 것), 그림 자료와 도구 설명은 `art/README.md`.

### 6-1. 현재 동작 (beeb2f4f 기준, 확인함)
- 캐릭터 3종 **호랑이·토끼·거북이** = 캐릭터마다 매니페스트 하나(`chars/<이름>/`)에 걷기·앉기가 모두 있다(`walker: true` + 앉기 클립 전부 = "하이브리드"). 한 캐릭터는 한 번에 한 가지 활동만 한다(두 번 나오지 않음).
- **움직임 잠금**: 지나가는 캐릭터, 앉으러 오거나 떠나는 캐릭터, 비행기 중 **한 번에 하나만** 움직인다. 끝나면 `passEvery`([15,45]초) 쉰 뒤 가중 무작위(지나가기/비행기/앉으러 오기/떠나기/아무것도 안 함). 같은 이벤트·같은 캐릭터 연달아 없음. 비행기도 감독(`behavior.js`)이 정한다(`director.plane()`).
- **공유 타임라인(2026-10-21)**: 열 때마다 무작위가 아니라 서버 시각을 따른다. 30분 칸마다 같은 시드, 빈 방으로 시작해 빈 방으로 끝나며, 앱을 열면 지금까지를 빨리 감는다. 같은 순간에는 모든 기기가 같은 장면을 본다(`docs/LOUNGE_SCENE_DESIGN.md` 7.9). 에피소드 모드에서는 `scene.preview`가 쓰이지 않는다(디버그 `reseed`를 쓰면 옛 방식).
- 걷기: 몸은 기준 칸 하나로 고정, 다리만 칸마다 교체. 프레임마다 `ay`로 **위아래 흔들림**(두 발 사이 거리로 엉덩이 높이 계산, 몸 높이의 약 1%, 발은 바닥에 고정).
- 얼굴: 프레임 항목의 `v: {blink, smile, laugh}`가 바꿔 그릴 프레임을 가리키며(`over` 조각이면 얼굴 부분만 덧그림), 감독이 `face` 필드를 스냅샷에 낸다. 깜빡임 2.2~6초마다 120~170ms(15% 두 번 연달아), 표정은 가끔. 얼굴용 난수는 별도 스트림(`seed ^ 0x9e3779b9`).
- 앉기: 걸어와 정면으로 종이 뒤집듯 돌아선 뒤(가로 폭 0.12까지 좁혔다 펴기), 웅크렸다 방석 높이로 뛰어올라 앉은 그림으로 바뀜. 일어나기는 반대. 앉은 뒤 숨쉬기(±1% 늘임)·눈 깜빡임, 활동 = 호랑이 폰·토끼 통화·거북이 티켓·졸기(졸음 시트). 채팅·선글라스·옷매무새는 그림이 없어 생략(감독이 없는 클립은 건너뜀).
- 펭귄은 **제외**(걷는 그림이 한 장뿐). 앉은 그림·졸음 그림은 있다.

### 6-2. 알려진 약점 (옛 기록, 최신은 0-3)
- (0-3에서 고침) 겹쳐 바뀌는 순간 반투명 이중 영상.
- 옆모습↔정면 전환에서 몸이 얇은 막대처럼 보이고 들고 있는 물건이 바뀜(걸을 땐 캐리어·폰, 서서는 커피/없음).
- 앉은 그림이 "바닥에 앉아 다리를 앞으로 뻗은" 그림이라 방석 위에서 다리가 늘어지지 않고 뻗음.
- (0-3에서 고침) 이웃 자리끼리 겹침, 오른쪽 끝에서 잘림.
- 토끼 통화 자세의 소매는 직접 덧칠한 것(평평한 분홍), 토끼의 눈은 걷기 그림에서 빌려 옴.
- 사용자가 지적한 것: **앉았을 때 다리가 안 보임**(소파 앞면 뒤로 가라앉는 방식 때문) → `beeb2f4f`에서 고침. 이후 **의자와 정밀 접착, 방향, 레이어** 지적 → 0-3.

### 6-3. 그림 자료 (`art/sources/`, 모두 Gemini 4×4 시트·흰 배경)
- 걷기: `rabbit_walk_sheet_4x4_gemini`, `turtle_walk_sheet_4x4_gemini`, 호랑이 `tiger_walk_sheet_b1~b6`(사용: b1)
- 표정(눈 감음·웃음·크게 웃음 기증용): `turtle_walk_sheet_faces_gemini`, `tiger_walk_sheet_faces_gemini`
- 앉기·졸기: `chars_sitting_group_gemini`(네 마리 앉은 모습, 한 장씩), `all_doze_sheet_gemini`(4마리×4포즈), `tiger_doze_sheet_gemini`(호랑이 16)
- 서 있는 정면 포즈: `stand_poses_tiger_turtle_penguin_{a,b}_gemini`(같은 시트 두 판), `rabbit_pose_sheet_4x4_gemini`(토끼 16)
- **호랑이가 소파에 올라가 앉는 순서**: `tiger_climb_sit_sheet_a_gemini`(2400px), `..._b_ledge_gemini`(1024px, 소파 앞 가장자리선이 그려짐) — **아직 안 씀**(7장)
- 임시 도형 캐릭터(시험용)는 `ui/tools/lounge_placeholder_manifests.json`에 보관, 실제 장면에는 없다.

### 6-4. 도구와 다시 만들기 (결과는 byte 동일, 확인함)
```
python3 art/tools/build_character.py tiger rabbit turtle     # 앉기+걷기 포함 완성 캐릭터
python3 art/tools/build_tiger_walker.py                      # 호랑이 걷기 라이브러리(위 도구가 가져다 씀)
python3 art/tools/build_walker.py rabbit turtle              # 토끼·거북이 걷기 라이브러리
python3 art/tools/build_lounge_scene.py                      # scene.json 다시 씀(좌석·preview·passEvery 등 포함)
```
- 보조: `art/tools/{walk_bob,face_patch,cut_sheet,lockbody,stride_tween,swap_legs,mirror_logo,inkfix}.py`. `ui/tools/lounge_make_placeholders.py`는 `--out`이 필수(실제 장면을 덮어쓰지 못하게).
- 캐릭터 한 명 용량 상한 1.5MB(검사기가 확인). 지금 호랑이 약 740KB, 토끼 590KB, 거북이 560KB. 디코드 메모리 합계 약 31MB.

### 6-5. 시험 (전부 통과해야 함)
```
for f in ui/web/lounge/*.js; do node --check $f; done
node ui/tools/verify_lounge_sun.js
node ui/tools/verify_lounge_lighting.js
node ui/tools/verify_lounge_location.js
node ui/tools/verify_lounge_board.js
node ui/tools/verify_lounge_behavior.js        # 약 1분, 24시간 시뮬레이션 포함
python3 ui/tools/lounge_check_assets.py
python3 ui/tools/verify_lounge_assets.py
python3 ui/tools/verify_ui.py --port 8861      # 끝나고 fuser -k 8861/tcp 로 남은 서버 정리
python3 gateway/verify_gateway.py              # 게이트웨이 120개
python3 ui/tools/verify_profile_api.py         # 16개
```
CI: `.github/workflows/lounge-scene.yml`(PR·푸시), `android-apk.yml`.

---

## 7. 다음 할 일 (우선순위 대략순)

1. **사용자에게 앉기 결과를 보여 주고 피드백 받기**(자리별 정지 화면·확대 접촉 부분·전체 순서). 흰 가장자리, 반투명 없음, 방향이 맞는지.
2. **호랑이 실제 올라가 앉기**: `tiger_climb_sit_sheet_a/b`의 칸들로 `sit_down`/`stand_up`을 만든다. 빌더가 캐릭터별 `sit_frames`/`stand_frames` 목록을 받으므로 엔진 수정 없이 끼울 수 있다. 칸 크기·위치가 서로 달라 따로 맞춰야 한다(작업자 보고). b의 가로선 = 소파 앞 가장자리.
3. **서 있는 반응 동작**("걷다가 멈춰 손 흔들기/하트/엄지척/커피 등"): `stand_poses_*`와 토끼 포즈 시트의 정면 포즈를 쓴다. 지나가는 캐릭터가 임의 위치에서 멈춰 포즈 → 다시 걷기. 감독에 새 상태가 필요하다. 아직 시작 안 함(**보류**).
4. **펭귄**: 걷는 옆모습 시트가 있어야 자연스럽다. `docs/LOUNGE_ART_PROMPTS.md` 끝의 "추가로 받으면 좋은 그림"에 Gemini 요청 문구(1~5번)를 적어 두었다: 거북이·토끼·펭귄의 소파 올라가 앉기, 일어나기, 눈 뜬 정면 앉은 모습, 옆을 보고 앉아 대화하는 모습, 펭귄 걷기 시트.
5. 사용자가 괜찮다고 하면 `scene.preview` 제거, 이 브랜치를 master에 합치는 PR(사용자 확인 후).
6. 서버 배포·구글 로그인·APK 정식 서명(1·2·4·5장). 털묵스 칩 이전.
7. master의 기존 실패 시험 2개 점검.

사용자가 줄 수 있는 것: 위 4번의 새 그림, 구글 클라우드 콘솔에서 만든 클라이언트 ID, 서버 주소.

---

## 8. 작업 요령과 함정 (확인함)

- **앉기 확인 항목**(눈으로): 자리별(s0~s3) 낮·밤 정지 화면 390×844 @2x + 접촉 부분 확대, 한 사이클 필름(걸어와서 돌고, 뛰어올라 앉고, 숨쉬기·깜빡임, 활동, 일어나 돌아 나가기), 이웃 동시 앉기, 팔걸이 가림, 오른쪽 끝 잘림, 반투명 겹침 없음, 다리·꼬리·등껍질이 소파와 맞는지.
- 화면 확인 스크립트는 저장소에 없다(작업 중 임시 폴더에 있었고 세션이 끝나면 사라진다). 필요하면 `ui/tools/lounge_screens.js`를 참고해 다시 만든다. 핵심 방법: 정적 서버로 `ui/web`을 서빙(`/api/lobby`는 가짜 JSON), Playwright(전역 node 모듈 `NODE_PATH=$(npm root -g)`, 크롬은 `/opt/pw-browsers`)로 열고, `window.T2LoungeBehavior.createDirector`를 감싸 `director.step` 결과를 `window.__chars`로 꺼내며, `T2Lounge.debugHandle()`의 `setClock/reseed/setScale/setFace/request(name,'pass'|'arrive'|'leave',seat)/mover()/redraw()`로 장면을 구동한다.
- `pkill -f "<패턴>"`을 패턴이 들어 있는 같은 셸 명령에서 쓰면 **자기 셸을 죽여** 명령이 끊긴다(종료 코드 144). 포트로 `fuser -k <포트>/tcp`를 쓴다.
- `verify_ui.py`는 끝나고 `ui_server.py` 프로세스를 남기는 경우가 있다 → 다음 실행에서 포트 충돌. 정리하고 다른 포트를 쓴다.
- 백그라운드 에이전트(특히 큰 모델)는 **사용 한도(rate limit)** 에 걸려 중간에 멈춘다(이번 세션에서 3번). 작업물은 파일로 남고, 한도가 풀리면 `SendMessage`로 이어서 하게 할 수 있다. 에이전트가 쓴 파일은 끝나기 전까지 **시험하지 않은 중간 상태**다 — 올리지 말 것.
- 에이전트 보고는 "보고만"이다. 시험과 화면은 직접 다시 확인한다(이번에도 직접 돌려 확인한 뒤 커밋했다).
- 캐릭터 그림은 AI(Gemini)가 칸마다 조금씩 다르게 그려서 칸을 그대로 이어 붙이면 얼굴·옷이 깜빡인다. 그래서 몸은 한 장으로 고정하고 바뀌는 부분만 교체하는 방식(`lockbody`, `build_character`)을 쓴다. 이 원칙을 깨는 변경은 먼저 `art/README.md`의 근거를 읽을 것.
- 저장소가 크다(수 GB). 클론·fetch는 브랜치 하나씩.

---

## 9. 사용자 요청 이력 (이번 세션, 요지)

| 요청 | 상태 |
|---|---|
| 로비 라운지(호랑이 걷기, 소파 바닥 확장, 비행기, 하단 흐림, 로고 ♠T2 등) | 완료, master 합침(#41) |
| 안드로이드 앱 + 구글 계정 + 서버 저장 | 프로필 서버 저장·게이트웨이·로그인/가입 화면 master 합침(#42). 앱·계정 정리·UI는 브랜치에 있음 |
| 허용 이메일 끄기, 개인정보 정리 설계 | 완료(`signup_mode: open`, `docs/ACCOUNT_DATA.md`) |
| 앱 아이콘 로고 여백, 로딩 화면부터 전체 화면 | 완료 |
| 대회 정보 창을 떠 있는 창으로, 뒤 터치 막기, 밖 터치로 닫기 | 완료 |
| 로그아웃 후 501 오류 | 완료 |
| 인게임 UI 고급스럽게, 위쪽 좌석 바깥으로, 테이블 완전 타원 | 좌석·이름표·버튼 완료, **테이블 모양은 이전으로 되돌림(사용자 요청)** |
| 걷는 캐릭터·비행기를 앱 열 때마다 무작위, 겹침 없이 | 완료 |
| 토끼·거북이 걷기 | 완료(사용자 확인 "걷는 건 좋아") |
| 눈 깜빡임, 걸음에 맞춘 위아래 흔들림 | 완료 |
| 의자에 앉기까지, 있는 그림으로 가능한 모션 전부 | 앉기·졸기·폰·통화·티켓 완료, 의자 정밀 접착·방향·레이어 완료(0-3), 서 있는 반응 동작·호랑이 올라가기 **미시작** |

---

## 10. 파일 지도 (이번 세션에서 만들거나 크게 바뀐 것)

- 게이트웨이: `gateway/{gateway.py,admin.py,login.html,gateway.dev.json,verify_gateway.py,README.md}`
- 앱: `android/**`, `.github/workflows/android-apk.yml`
- 계정 설계: `docs/{ACCOUNT_DATA,APP_DESIGN}.md`
- 로비: `ui/web/lobby.{html,css,js}`, 게임 화면 `ui/web/{app.js,theme.css,index.html}`, 프로필 API는 `ui/server/ui_server.py`(`/api/profile`)
- 라운지 엔진: `ui/web/lounge/{behavior,renderer,lounge,assets,debug}.js`, 에셋 `ui/web/lounge/assets/{scene.json,bg/,chars/}`
- 라운지 시험: `ui/tools/{verify_lounge_*.js,lounge_check_assets.py,verify_lounge_assets.py,lounge_screens.js}`
- 그림 도구·자료: `art/{README.md,sources/,cutouts/,tools/}`, 요청 문구 `docs/LOUNGE_ART_PROMPTS.md`
