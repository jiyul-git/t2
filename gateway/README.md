# T2 online gateway

구글 계정 로그인 + 플레이어마다 따로 도는 게임 서버. 설계는 `docs/APP_DESIGN.md`.

## 휴대폰(털묵스)에서 바로 해보기 — 개발용 로그인

```
git -C ~/t2 fetch origin claude/t2-ui-changes-dobpqd && git -C ~/t2 checkout -q FETCH_HEAD
python3 ~/t2/gateway/gateway.py --config ~/t2/gateway/gateway.dev.json
```
브라우저에서 `http://127.0.0.1:8080` → 로그인 화면 아래 "개발용 이메일"에 허용된 주소를 넣고 입장.
개발용 로그인은 127.0.0.1에서만 켜지고, 공개 서버에서는 구글 로그인만 쓴다.

## 화면 흐름 (`login.html`)

1. 로딩 화면: 로고와 진행 막대가 나오고, `/auth/me`로 로그인 상태를 확인한다.
2. 로그인: 구글 버튼. 앱 안에서는 앱이 구글 로그인을 하고 `window.t2SignIn(idToken)`으로 넘긴다.
3. 회원가입: 처음 들어온 계정이면 닉네임·캐릭터를 정하고 이용 안내에 동의한다(`/auth/register`).
   가입을 마치기 전에는 게임 화면과 `/api/*`가 막힌다.
4. 로비: 가입한 계정은 다음부터 로딩 화면에서 바로 로비로 들어간다.

데이터: `~/t2_online/users/<uid>/`(지갑·프로필·기록), `~/t2_online/run/<uid>/`(진행 중 게임).

## 시험
```
python3 gateway/verify_gateway.py
```
