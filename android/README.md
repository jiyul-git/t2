# T2 안드로이드 앱

T2 웹 화면을 전체 화면으로 띄우는 앱이다(주소창·상태바 없음). 화면은 서버에서 오므로 UI를 고쳐도 앱을 다시 깔 필요가 없다.

- 받기: https://github.com/jiyul-git/t2/releases/download/android-latest/t2.apk
- 빌드: `android/`를 고쳐 올리면 GitHub Actions(`android-apk`)가 APK를 만들어 위 주소에 올린다.
- 서버 주소: 저장소 변수 `T2_SERVER_URL`. 없으면 `http://127.0.0.1:8080`(같은 폰의 털묵스 게이트웨이).
  앱에서 연결이 안 되면 나오는 화면의 "서버 주소 바꾸기"로도 바꿀 수 있다.
- 구글 로그인: 저장소 변수 `T2_WEB_CLIENT_ID`(구글 클라우드의 웹 클라이언트 ID). 없으면 개발용 로그인만 쓴다.
- 서명 키: 저장소 비밀값 `T2_KEYSTORE_B64`, `T2_KEYSTORE_PASSWORD`. 없으면 시험용 키(Actions 캐시)로 서명한다.
  시험용 키에서 정식 키로 바꿀 때는 앱을 한 번 지우고 다시 설치해야 한다.

## 털묵스로 시험하기
```
python3 ~/t2/gateway/gateway.py --config ~/t2/gateway/gateway.dev.json
```
켜 둔 채로 T2 앱을 열고 개발용 이메일로 입장한다.
