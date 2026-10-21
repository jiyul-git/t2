# T2 online gateway

구글 계정 로그인 + 플레이어마다 따로 도는 게임 서버. 설계는 `docs/APP_DESIGN.md`.

## 휴대폰(털묵스)에서 바로 해보기 — 개발용 로그인

```
git -C ~/t2 fetch origin claude/t2-ui-changes-dobpqd && git -C ~/t2 checkout -q FETCH_HEAD
python3 ~/t2/gateway/gateway.py --config ~/t2/gateway/gateway.dev.json
```
브라우저에서 `http://127.0.0.1:8080` → 로그인 화면 아래 "개발용 이메일"에 아무 주소나 넣고 입장(`signup_mode`가 `"open"`일 때).
개발용 로그인은 127.0.0.1에서만 켜지고, 공개 서버에서는 구글 로그인만 쓴다.

## 화면 흐름 (`login.html`)

1. 로딩 화면: 로고와 진행 막대가 나오고, `/auth/me`로 로그인 상태를 확인한다.
2. 로그인: 구글 버튼. 앱 안에서는 앱이 구글 로그인을 하고 `window.t2SignIn(idToken)`으로 넘긴다.
3. 회원가입: 처음 들어온 계정이면 닉네임·캐릭터를 정하고 이용 안내에 동의한다(`/auth/register`).
   가입을 마치기 전에는 게임 화면과 `/api/*`가 막힌다.
4. 로비: 가입한 계정은 다음부터 로딩 화면에서 바로 로비로 들어간다.

데이터: `~/t2_online/users/<uid>/`(지갑·프로필·기록), `~/t2_online/run/<uid>/`(진행 중 게임).
계정 목록(이메일 포함)은 `~/t2_online/gateway/accounts.json`에만 있다. 설계는 `docs/ACCOUNT_DATA.md`.

## 가입 설정 (`gateway.json`)

| 키 | 기본값 | 뜻 |
|---|---|---|
| `signup_mode` | `"open"` | `"open"`: 구글 계정이 있으면 누구나 가입. `"invite"`: `allowed_emails`에 있는 계정만 |
| `allowed_emails` | `[]` | `"invite"` 모드에서만 쓴다 |
| `max_accounts` | `20` | 계정 수 상한. 넘으면 새 가입은 "정원이 찼습니다", 기존 계정은 들어온다 |
| `idle_seconds` | `1800` | 요청이 이만큼 없으면 그 사람의 게임 서버를 끈다(다음 요청에 다시 뜨고 저장된 대회를 이어간다) |
| `busy_idle_seconds` | `21600` | **대회가 진행 중인** 사람의 게임 서버는 `idle_seconds`가 아니라 이 시간(6시간) 동안 요청이 없을 때만 끈다. 앱을 백그라운드에 두어도 대회가 끊기지 않게 한다 |
| `max_backends` | `4` | 동시에 띄우는 게임 서버 수 |
| `backup_dir` | `~/t2_online/backups` | `admin.py backup` 결과 위치 |

옛 `users.json`(버전 1)은 처음 뜰 때 `accounts.json`으로 옮기고 `users.json.v1.bak`으로 남긴다.
옮긴 계정은 다음 로그인에서 원래 폴더를 그대로 이어 쓴다.

## 관리 도구 (`admin.py`)

게이트웨이와 같은 설정 파일을 읽는다(`--config`, 기본 `gateway/gateway.json`).

```
python3 gateway/admin.py list                      # uid, 이메일, 닉네임, 칩, 상태, 마지막 로그인
python3 gateway/admin.py disable <uid|이메일>      # 이용 중지(쿠키가 있어도 다음 요청부터 막힘)
python3 gateway/admin.py enable  <uid|이메일>
python3 gateway/admin.py delete  <uid|이메일> [--yes]   # 확인 질문 후 폴더와 기록 삭제
python3 gateway/admin.py backup                    # backups/t2-YYYYMMDD-HHMM.tar.gz, 최근 7개만 보관
```
게이트웨이는 요청마다 `accounts.json` 변경을 확인하므로 재시작 없이 적용된다.
백업의 지갑은 SQLite 백업 기능으로 복사해 게임 중에도 깨지지 않는다(파일 권한 0600).

## 시험
```
python3 gateway/verify_gateway.py
```
