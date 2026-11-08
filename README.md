# T2 — 사람처럼 두는 포커 봇 토너먼트

처음 보는 사람(또는 새 세션)이 가장 먼저 읽는 지도다. **지금 상태는 `docs/STATUS.md`**, 일하는 방법은 `docs/T2_HANDOFF.md`.

## 브랜치
| 이름 | 역할 |
|---|---|
| `master` | 배포. 사용자 승인 때만 test3 를 fast-forward 로 올린다 |
| `test3` | 시험 배포. 사용자가 Termux 서버로 이것을 돌린다. 모든 작업은 여기로 모인다 |
| `claude/*` | 작업·계산 브랜치(GTO 계산, 정밀 검사, 실험). 끝나면 필요한 결과만 test3 로 옮긴다 |

강제 푸시 금지. 커밋 메시지에 모델 이름 금지.

## 폴더
| 위치 | 내용 |
|---|---|
| 맨 위 `*.py` | 엔진. 실행에 쓰는 모듈 목록은 `ui/tools/setup_run_dir.sh` 의 `MODULES`(허용 목록)가 기준 |
| `ui/server/` | 게임 서버(`ui_server.py`: 입장·시계·스트림, `ui_view.py`: 화면용 상태) |
| `ui/web/` | 게임 화면(`app.js`, `style.css`)과 로비(`lobby.*`, `lounge/`) |
| `gateway/` | Termux 게이트웨이(계정별 게임 서버를 띄우고 프록시). `gateway/README.md` |
| `android/` | 안드로이드 앱(WebView). push 하면 `android-apk.yml` 이 빌드 |
| `data/gto_records/` | 봇에 연결한 GTO 기록 사본(출처표 `MANIFEST.tsv`) |
| `tools/` | 검사·분석 도구. 분류는 `tools/README.md`, 이어받기 검사는 `tools/t2_handoff/` |
| `docs/` | 문서. 아래 표 |
| `legacy/` | 더 이상 쓰지 않는 코드·결과물·Actions 설정 보관(지우지 않음). 각 폴더 README 에 이유 |
| `.github/workflows/` | 지금 도는 자동 검사 5개(앱 빌드, 라운지 그림, test3 검사 3개) |

## 문서
| 문서 | 내용 |
|---|---|
| `docs/STATUS.md` | **지금 상태**: 배포, 화면 남은 문제, GTO 방향, 사용자 결정 대기 |
| `docs/HANDOFF_ACCOUNT.md` | 다른 계정으로 인계: 누가 무엇을 돌리는지, 세션 여는 문구, 조정 이어받기 |
| `docs/GTO_FULLTREE_STATUS.md` | GTO 전체 트리 정밀 계산 진행(스택·단계·브랜치·세션) |
| `docs/T2_HANDOFF.md` | 일하는 방법: 사용자 규칙, 연결 절차, 검사 함정, Termux 명령 |
| `docs/handoff/` | 날짜별 인계 기록(색인 `docs/handoff/README.md`) |
| `docs/design/` | 설계 문서(결정 시스템, 레인지, 토너먼트 런타임, 머니점프 등 — 2026-10-08 기준 정리본) |
| `docs/GTO_*`, `docs/MULTIWAY_*`, `docs/PF_*` | GTO 연결·조사 보고(날짜별) |
| `docs/semantic_audit/` | 예전 전수 점검 기록(기록이므로 고치지 않음) |

## 검사 (test3 에 올리기 전)
```
bash tools/t2_handoff/regress.sh      # 끝줄 SAME_AS_BASELINE
bash tools/t2_handoff/ui_checks.sh    # 전부 0 (라운지 그림 2개는 opencv 필요)
```
