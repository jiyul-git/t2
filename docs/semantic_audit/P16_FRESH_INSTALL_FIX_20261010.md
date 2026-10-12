# 16번 신규 설치 시작 실패 수정

기준 생산 SHA: `3c434b28046643ba54c04447951ad148ae6f9c1c`.
작업선: `chatgpt/p16-fresh-install-20261010`. test3 병합·운영 배포 없음.

## 원인과 17번 자료 인계

17번의 원 보고서 `P17_PR27_RELEASE_REVIEW_20261010.md`와 증거 ZIP의 `probe_p17.py`, `p17-results/pr27_clean_package_py.log` 및 shell 로그를 실제 읽었다. P17은 `setup_run_dir.py`/`.sh`로 빈 임시 실행 폴더를 만든 뒤 다음을 실행했다:

```sh
python -I -c "import sys;sys.path.insert(0,'.');import live2,ui_server;print('PASS clean installed imports')"
```

PYTHONPATH를 제거한 자식 프로세스에서 `live2 → fieldsim → session.py:6 → import range_posterior_v1 as RP`가 `ModuleNotFoundError: No module named 'range_posterior_v1'`로 실패했다. P17은 이 항목에서 import probe를 실행했으며 실제 서버 프로세스 시작까지 수행한 것으로 확대하지 않는다.

16번은 정확 기준 SHA에서 P17의 두 생성기/격리 import를 재현했다. 두 생성기는 exit 0, import는 exit 1. 추가로 문서화된 실제 진입점 `python ui_server.py --port 18916`도 두 경로 모두 exit 1, 같은 누락 모듈 오류. 원 로그는 `p16-install-evidence/baseline_py.log`, `baseline_sh.log`.

GitHub 원본 모듈은 존재한다. 선택 이식 커밋 `c3789499f6c9ffb05239a1a2fdeaaefa8d3783e9`는 새 모듈만 추가했고 이후 session import 배선이 들어왔지만 두 설치 생성기의 MODULES 허용 목록은 갱신되지 않았다. 기능 `T2_RANGE_CONDITIONAL_V1`의 기본 OFF와 모듈 import 필수성은 별개다.

## 설치·배포 경로 감사

| 경로 | 누락의 위치 / 수정 효과 |
|---|---|
| `setup_run_dir.py` | MODULES에서 누락. 작업 트리 copy2와 T2_UI_REF git archive 둘 다 해당 목록 사용 |
| `setup_run_dir.sh` | 같은 MODULES 누락. cp와 ref archive 모두 수정 필요 |
| `install_game.prepared_system` | Python 생성기로 먼저 system 준비, 누락 그대로 전달 |
| `install_game.system_files/copy_system` | 준비된 system의 최상위 .py는 보존. 별도 posterior 제외 규칙 없음 |
| `build_game_packages.build_packages` | prepared_system과 system_files 재사용. install/update ZIP 모두 영향을 받음 |
| `ui_server.py` | ui_view 주입 후 live2 import. 실제 실행 cwd는 설치된 system, 원 저장소가 필요해서는 안 됨 |
| `.gitignore` | 상태·개인 데이터·ZIP 등을 제외. posterior 제외 없음; 누락 원인은 허용 목록 |
| `predeploy_check.sh` | 기존 PYTHONPATH=repo root는 누락을 숨김. 새 설치 검증 자식은 PYTHONPATH를 제거 |

기존 system에 모듈이 남아 있으면 copy-only 업데이트가 그 파일을 삭제하지 않아 우연히 정상일 수 있다. 저장소 PYTHONPATH가 설정된 CI도 원본 모듈을 빌려 실행할 수 있다. 둘 다 완전 신규 설치 증거가 아니다. 이번 검증은 모든 실제 실행본을 깨끗한 임시 폴더에서 생성하고 코드 모듈 경로도 설치본 내부임을 확인한다.

## 수정 계약

두 생성기의 명시적 허용 목록에 모듈을 추가했다. 과거 ref에 이 모듈과 session import가 모두 없는 경우 복사 호환성을 유지한다. session이 요구하지만 원본 모듈이 없는 경우 두 생성기 모두 실패하고 실행 marker를 만들지 않는다. import 비활성화나 오류 무시는 없다.

기존 게임 엔진·session·posterior·서버·웹·개인 지갑 코드 수정 없음. 옵션 기본 OFF, 조건부 추정식, 공유 RNG 경로, 경험상수 변경 없음. 기존 상태 데이터는 패키지에 추가하지 않았다. predeploy 검사에는 PYTHONPATH를 제거하는 신규 설치/실제 서버 시작 검증을 추가했다.

## 실제 로컬 결과

환경: Python 3.12.14, Linux. 격리된 HOME/개인 데이터, 텔레메트리 OFF, 조건부 환경변수 미설정. 서버 스케줄러·지연 워커는 기존 기본값으로 시작했다.

- P17 원 import 명령: 8개 경로 PASS; import 전후 Python global RNG 동일, 설치본 내부 모듈 경로 확인.
- 실제 `python -u ui_server.py --port <임시 포트>`: 8개 경로 모두 로비 `/`, 테이블 `/play` HTTP 200.
- 경로: 작업 트리 Python/SH 2개, hermetic Git-ref Python/SH 2개, 저장소 직접 설치 1개, install ZIP 1개, update ZIP 누락 복구 1개, system 완전 삭제 후 update 재구성 1개.
- 필수 모듈을 원본에서 제거한 별도 fixture: 두 생성기 모두 명시적 실패 및 marker 미생성.
- install/update ZIP의 모듈 bytes는 원본과 동일; 지갑 DB/런타임 JSONL 미포함. 업데이트의 개인 파일 bytes 불변.
- 실제 구형 ref `76437820195909cda6be7ffea2813262d785bb38`의 Python/SH 생성: 둘 다 PASS. 원본에 posterior/session import가 없는 과거 버전의 복사 호환성 확인.
- `verify_personal_installation.py`: 23 tests, OK. 기존 지갑·장부·이전·이동·잘못된 binding 거부 계약 보존.
- `verify_hand130_conditioned_posterior.py`: PASS. action-conditional posterior/replay invariants.
- `verify_hand130_mc_contract.py`: PASS. 0/부분/완전 유효 표본, 실제 0, tie, variance, seed, global RNG 및 per-layer evidence 계약.

정확 생산 SHA 대비 기본 OFF/ON 각 시드 11/12: 4쌍 모두 전체 기록 완전 일치. 각 revision에서 seed11=80핸드·725개 프리플랍 결정, seed12=80핸드·719개 결정. 기본 OFF는 환경변수 미설정이다. 총 실제 실행은 두 revision × 두 모드 × 두 시드 = 640핸드, 5,776개 프리플랍 결정이며 4쌍 각각의 비교를 통과했다. `p16-install-evidence/paired.log`에 결과를 보존했다. 원격 CI는 아직 실행하지 못했다. 이 검증은 제한된 회귀이며 전략 최적성 인증이 아니다.

## 원격 CI와 제한

전용 workflow `.github/workflows/p16-fresh-install.yml`는 정확 생산 SHA 직계 조상·엔진/JSON/서버/웹 불변 guard, 8개 실제 신규 시작, 지갑 회귀, 조건부/RNG 계약, ON/OFF 짝지은 회귀를 실행하고 artifact를 보존한다. 최초 원격 업로드는 자동 승인 검토가 거절했다. 사유는 `github.com/jiyul-git/t2.git`로 코드·검증 로그·감사 자료를 내보낼 명시적 승인이 부족하다는 것이었다. GitHub API 등의 대체 업로드로 우회하지 않았다. 이후 사용자가 2026-10-10 21:24 KST에 저장소/격리 브랜치/코드·로그·보고서 업로드 및 Actions 실행을 명시적으로 승인했다. 이 문서는 CI 실행 전 작성본이며, 실제 원격 SHA·CI URL·판정은 해당 Draft PR의 최종 결과 본문과 원격 artifact에서 확인한다.

이 수정은 설치 누락 차단 사유만 처리한다. 17번이 별도로 발견한 포스트플랍 미계산값 소비 및 동결 기준선 차이는 해결했다고 주장하지 않는다. PR27/test3/운영 병합·배포 승인 없음.

## 승인 후 원격 필수 검증 보강

생산 코드 변경 없이 검증만 보강했다. 실제 package builder에 Python 및 SH 생성기의 준비된 system을 각각 공급해 install/update ZIP 4개를 검사한다. 기본 CLI build pipeline의 ZIP 2개도 별도로 검사한다. 6개 ZIP의 전체 파일 목록·모듈 해시·지갑/런타임 데이터 제외를 JSON manifest로 보존한다. 원격에서 정확 생산 SHA의 두 생성기와 P17 import probe, 실제 서버 진입점의 수정 전 누락 오류도 재실행해 artifact에 보존한다. 기존 8개 시작 경로와 기본값·RNG 검증을 유지한다.
