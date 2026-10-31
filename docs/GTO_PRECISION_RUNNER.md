# GTO 프리플랍 정밀(precision) 검사 실행 도구 (2026-10-31)

작성: session_01JQGBPMv985 (코디네이터 session_012qfUk9 지시, 사용자 승인 10-31). 표준: `docs/GTO_PRECISION_PRIORITY_20261030.md` 3장 초안 그대로.
도구: `tools/gto_precision/precision_loop.py`(계산), `tools/gto_precision/run_precision.sh`(한 번 실행 + 백업·푸시), 패널: `data/gto_precision/panels/`.
**런타임(gto_pf_data.json) 연결 없음 — 계산·기록만.**

## 1. 사용법 (한 줄)
```sh
PREC_CALC_ROOT=/home/user/calc PREC_SESSION=session_<내 세션 id> sh tools/gto_precision/run_precision.sh <spot_id>   # 추적 백그라운드, 타임아웃 7200000, PREC_DONE/PREC_PAUSED 나올 때까지 같은 명령 재실행
```

### 1.1 새 spot (24보드 quick 상태 없이, precision 패널로 바로 시작)
```sh
PREC_START=fresh PREC_CALC_ROOT=/home/user/calc PREC_SESSION=session_<id> sh tools/gto_precision/run_precision.sh <spot_id>
```
- 필요한 것: 계산 브랜치의 `data/gto_spot/plan_a/specs/<id>.json`(hu_spot spec, `rule: v4`) + 부모 덤프·승률표 설치. state.json·quick 기록은 필요 없다.
- 0단계: 정적 연속값(부모 트리 값)으로 spot 을 풀고 끝점마다 A·B 를 푼다 → **0단계는 통과로 치지 않는다**(quick 루프처럼 최소 1회 갱신; 이전 표가 없는 끝점은 A∪B 값을 그대로 받음).
- 1단계부터 3장 통과 조건 그대로. 기본 최대 4단계(0단계 + 3), 기본으로 끝까지 돈다(`PREC_STAGE_LIMIT` 로 끊을 수 있음, `PREC_MAX_STEPS` 로 바꿀 수 있음 — 코디네이터 결정).
- 4단계 안에 못 통과 → `precision_failed`(기록 `status: quick` 아님 — 빈 자리이므로 **연결할 값 없음**으로 보고). 평균값을 만들지 않는다.
- u_outer 기준: 그 단계가 쓴 표(이전 단계 상태).
- spec 만들기: 기존 `tools/gto_spot/plan_a_flat_specs.py` 등(계산 브랜치)으로 만든 뒤 내 브랜치에 커밋해 두면 다른 세션도 같은 spec 을 쓴다.

## 2. 준비 (컨테이너 하나, 약 20분)
1. 이 브랜치(`claude/precision_runner_20261031`)에서 내 브랜치를 판다: `git checkout -b claude/precision_<spot>_<날짜> origin/claude/precision_runner_20261031`. 진행 기록은 **지금 체크아웃된 브랜치**에 커밋·푸시된다(master/test3 이면 거부).
2. 계산 브랜치(그 spot 의 quick 기록이 있는 브랜치, 예: p100 CO = `claude/resume_p100_flat_20261030`)를 작업 트리로: `git worktree add /home/user/calc origin/<계산 브랜치>`.
   필요한 것(24보드 상태에서 시작할 때): `data/gto_spot/plan_a/specs/<id>.json`, `data/gto_spot/plan_a/progress/<id>/state.json`(24보드 최종 상태), `data/gto_spot/quick/<id>.json`(바뀐 클래스 비교용).
   state.json 이 그 브랜치에 없으면(보관 브랜치 tar 안) 꺼내서 `PREC_START=<경로>` 로 준다.
3. 솔버: `cd /home/user/calc/vendor/gtopen && cargo build --release -p solver --features t2-cont --example t2_cont_panel`.
4. Python 3.11 + numpy 2.4.6(3.12+ 는 float 합·해시가 달라짐):
   `python3.11 -m venv /home/user/gto_ckpt/py311 && /home/user/gto_ckpt/py311/bin/pip install numpy==2.4.6`,
   `mkdir -p /home/user/gto_ckpt/py311bin && printf '#!/bin/sh\nexec /home/user/gto_ckpt/py311/bin/python "$@"\n' > /home/user/gto_ckpt/py311bin/python3 && chmod +x /home/user/gto_ckpt/py311bin/python3`.
5. 부모 덤프와 승률표: spec 의 `dump`/`equity` 경로에 설치(계산 브랜치 `data/gto_spot/plan_a/transfer/*.gz` 를 `gunzip -c`, `SHA256SUMS` 확인). spec 안의 `/home/user/t2/` 경로는 자동으로 PREC_CALC_ROOT 로 바꿔 읽는다.
6. **CLAIM**: 시작 전 `docs/GTO_SESSIONS_BOARD.md`(이 브랜치) 맨 위 CLAIM 표에 한 줄 추가 후 커밋·푸시. 남이 CLAIM 한 spot 은 돌리지 않는다.
7. 한 컨테이너에 spot 하나만(재실행 때 `t2_cont_panel` 을 전부 정리한다).

## 3. 하는 일 (표준 초안 그대로)
- 패널: A·B 각 72보드(12층 × 6), 시드 A=20261031, B=20261131. 층마다 panel_v1 의 2보드를 뺀 풀에서 원-플랍 수 비례·비복원으로 A 6장, 그다음 A 를 뺀 풀에서 B 6장.
  A·B·panel_v1 은 서로 겹치지 않는다. 값을 보기 전에 고정(`make_precision_panels.py`), sha256 은 `panels/MANIFEST.json`. **다시 만들지 말 것.**
- 시작: quick 24보드 루프의 최종 상태(state.json 의 표·행렬 = 마지막 단계 갱신 후).
- 단계 k: 그 표로 spot 풀기 → 끝점마다 A 72보드, B 72보드 풀기(quick 과 같은 솔버 목표, 못 맞춘 플랍은 CFR+ 1회 재시도 = 개정 11(a)) → A, B, A∪B 값.
- 통과 = ① 모든 끝점·자리 D = |V_A∪B − V_사용| ≤ U(144)  **그리고** ② 복제: |V_A − V_B| ≤ 2√(U_A²+U_B²) 이고,
  A만·B만으로 푼 뿌리 전략이 클래스별(행동 중 최대) 차이 ≤ 5%p 인 콤보가 95% 이상. (개정 8: 상대가 1콤보 미만으로 오는 끝점-자리는 면제, `strict` 도 같이 기록)
- 통과 → precision 상태 = A∪B 값으로 푼 spot. 실패 → 다음 표 = 0.5 T_k + 0.5 V_A∪B, D/U 가 오르내리는(순환) 끝점은 0.25. 최대 3단계. 그래도 안 되면 `precision_failed` + quick 유지.
  **평균값을 precision 이라 부르지 않는다.** 플랍이 재시도 후에도 안 풀리면 그 자리에서 `precision_failed`.
- 등급: `grade_spot.py` 규칙 그대로 + u_rep. 클래스마다 u = u_panel(A∪B) + u_outer(|gap − 24보드 시작 상태 gap|) + u_solver(spot exploitability) + **u_rep = |gap_A − gap_B|/2**,
  gap > 2u 이면 stable. u_solver 는 따로도 기록(`spot_exploitability_bb`, 플랍별 솔버 정확도는 report 의 `flops.<A|B>.solver`).
- `PREC_STAGE_LIMIT`(기본 1): 한 번 승인에 돌 단계 수. 1단계(복제) 끝나면 `PREC_PAUSED` 로 멈춘다 → 코디네이터 확인 후 `PREC_STAGE_LIMIT=1` 로 다시 실행하면 다음 단계.

## 4. 결과 파일
| 파일 | 내용 |
|---|---|
| `data/gto_precision/records/<id>.json` | `status`(`precision` 은 통과일 때만, 아니면 `quick`), `summary`(통과 여부, 끝점별 D/U·복제 차이, 뿌리 복제 몫, stable 콤보 몫, quick 대비 5%p 넘게 바뀐 뿌리 클래스), `grade`(노드·클래스별 빈도, gap, u 네 개) |
| `data/gto_precision/progress/<id>/state.json` | 다음 단계 표·행렬, 단계별 D/U 이력 |
| `data/gto_precision/progress/<id>/s<k>/` | report.json.gz, 사용한 표·행렬, A/B/A∪B 원값 표·행렬(gz), term*.json, 패널별 플랍 기록(ledger), panels_done.txt |
| `/home/user/gto_ckpt/precision/<id>/` | 컨테이너 안 작업 폴더(플랍 결과물). 컨테이너가 없어지면 run_precision.sh 가 브랜치에서 state·끝점을 되살리고 플랍은 다시 푼다 |

## 5. 비용
끝점 하나 × 24보드 × 1단계 ≈ 1시간(4코어) → 단계당 끝점 하나 6시간. BB 수비 1단계 18시간, 100bb(끝점 5개) 30시간.

## 6. 검사
- 10-31 배관 시험(p100 CO, 작은 패널 A·B 각 24보드, 반복 1회 + 행렬 끝점은 실제 결과물 복사본): 24보드 상태 시작 경로와 `PREC_START=fresh` 경로 모두
  끝까지 돌았다(단계 보고, 복제 비교, 등급·라벨, 멈춤/실패 처리). 값은 의미 없음. 실제 72+72 계산은 아직 한 번도 안 돌렸다.
- 시간 실측: 100bb 행렬 끝점(3벳 팟) 플랍 하나는 반복 1회여도 약 10분(행렬 내보내기), 단순 끝점은 약 25초 + 반복 시간.
`PREC_TEST=1 PREC_PANELS=<작은 패널 폴더> PREC_WORKDIR=/tmp/x PREC_POSTFLOP="10 50 5"` 로 배관만 시험할 수 있다(솔버 검사 끔, 결과는 의미 없음, 기록은 PREC_WORKDIR 안).

## 7. 첫 시험 p100_flat_co_vs_bb_o25 — 멈춤 기준 (계산 시작 전에 적음, 2026-10-31)
사용자 결정(10-31, 코디네이터 전달): 정밀 검사가 "되는지" 시험부터. 1단계(복제)만 돌린다.
- 시작: 계산 브랜치 `claude/resume_p100_flat_20261030` 의 `progress/p100_flat_co_vs_bb_o25/state.json`(quick 3단계 상한 끝 상태), `PREC_STAGE_LIMIT=1`.
- 1단계가 끝나면 **무조건 멈춘다**(통과해도, 실패해도). 2단계 이상은 코디네이터 확인 후에만.
- 1단계 중간에도 멈추는 경우: 플랍이 CFR+ 재시도 후에도 안 풀림(→ precision_failed 기록, 그대로 보고), 같은 오류로 실행이 두 번 연속 죽음(→ 원인 보고).
- 보고 항목: 통과 ①(D ≤ U144) / ②(복제) 여부, 끝점·자리별 D/U, 복제 차이 |V_A−V_B| 와 허용폭 2√(U_A²+U_B²), 뿌리 클래스별 5%p 초과 몫과 클래스,
  u_rep 크기(뿌리 콤보 가중 평균·최대, u_panel·u_outer 와 비교), stable 콤보 몫, quick 대비 5%p 넘게 바뀐 뿌리 클래스.
- 진행 기록: 끝점·패널 하나가 끝날 때마다 커밋·푸시(`run_precision.sh`).
