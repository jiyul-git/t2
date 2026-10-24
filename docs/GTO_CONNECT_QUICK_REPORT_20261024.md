# GTO quick 기록 연결 검사 보고 (2026-10-24)

작성: 코디네이터 세션(session_012qfUk9MsH6Hp2gBX6Q18sA). 사용자 승인(10-24): "연결성 검사를 제대로 하고 test3 에 반영".
T2 세션(01XV9)이 사용량 한도로 멈춘 동안 연결을 맡았다. master 는 건드리지 않았다.

## 연결한 것
| 상황 | 스택 | 짝 / 자리 | 새 표 |
|---|---|---|---|
| 3벳 받은 오프너: 폴드 · 콜 · 작은 4벳 · 올인 | 30, 40bb | CO vs SB(4.0x), UTG+1 vs SB(4.0x), UTG vs BTN(3.0x) | `vs_3bet_full` |
| SB 림프를 받은 BB: 체크 · 레이즈 3.5bb | 30, 40bb | SB>BB (나머지 전원 폴드) | `vs_limp_full` (새 연결 지점 `gto_pf_limp_choice`) |
| BB 플랫콜 수비(보정) 새 자리 | 30bb | UTG, UTG+1, UTG+2, LJ, HJ | `vs_open_full` (기존 표) |
| 같음 | 40bb | UTG, UTG+1, LJ | 같음 |

- 기존 표의 값은 하나도 바뀌지 않았다(표·키별 비교: changed 0, removed 0).
- 기록에 없는 클래스(3벳 기록에서 그 오프너가 오픈하지 않는 패)는 None → 기존 판단. 값을 지어내지 않는다.
- 작은 4벳 크기 = 3벳 크기 × reraise_mult(2)(IP 2.15 / OOP 2.35, 계산기 메뉴와 같음). 6개 기록 모두 작은 4벳 빈도는 0~0.01%.
- 연결에 쓰는 기록은 test3 안의 사본 `data/gto_records/`(압축 2.1MB, 출처표 MANIFEST.tsv). 계산 브랜치를 지워도 연결이 깨지지 않는다.

## 검사 (모두 통과)
| 검사 | 결과 |
|---|---|
| A 값 일치: 조회 = 기록(클래스별, 버킷 스택) | 29건 통과, 최대 차이 0.0006. 3벳 기록에 없는 클래스는 모두 None |
| B 실제 엔진 경로: 기록 상황을 session.HandRun → plan.preflop_plan 으로 재현, 클래스마다 40회(16개 기록, 도착 클래스 전부) | GTO 경로 사용 100%(16/16), 엔진 오류 0, 행동 종류별 빈도 차이 최대 0.6%p, 모든 클래스가 표본 오차 안 |
| C 경로 선택 | 버킷 사이(35bb) 보간 / 범위 밖(25·45bb) None / 3벳 크기 밖(12bb) None, 7.5bb 사용 / 기록 없는 짝 None / 콜러 있는 팟·ICM 압력(BF 1.2) None / 림퍼가 SB 아님·림퍼 둘·다른 돈·체크 불가·BB 아님·ICM → None / 유효 스택은 작은 쪽 / 6인 좌석 변환 |
| D 실패 내성 | 새 표가 없는 데이터, 모듈 없음 → None, 예외 없음 |
| verify_gto_pf | 43개 통과(HJ 가 보정된 뒤 낡은 두 검사의 자리를 바꿈: 보정 안 된 수비자 CO, 한쪽 버킷 UTG+2) |
| 회귀 20개(regress.sh) | 기준과 같음, 모두 0(verify_preflop_closure 는 검사 갱신 0d9dfa5c 로 통과) |
| 화면·게이트웨이 28개(ui_checks.sh) | 모두 0. 원래 실패하던 4개는 0d9dfa5c 로 통과. 라운지 자산 검사 2개는 opencv-python-headless 설치 후 통과(없으면 환경 오류) |

재실행: `sh tools/t2_handoff/fetch_records.sh /tmp/rec && python3 tools/t2_handoff/verify_gto_connect.py /tmp/rec 40 /tmp/connect.json`
(약 30분). 이번 결과 JSON: `docs/handoff/connect_quick_20261024.json.gz`(클래스별 봇 행동 수·기록 빈도·허용치).

## 기록별 결과 (봇 실제 행동 vs 기록, 도착 콤보 가중, %)
| 기록 | 방법 | 봇 | 기록 | 최대 차이 | 같은 종류 안의 크기 차이(>0.3%p) |
|---|---|---|---|---|---|
| `p30_flat_hj_vs_bb` | mean_of_last_2_steps | fold 19.2 / call 72.9 / raise 4.8 / jam 3.1 | fold 19.3 / call 72.8 / raise 4.7 / jam 3.3 | 0.1%p | - |
| `p30_flat_lj_vs_bb` | mean_of_last_2_steps | fold 22.5 / call 70.0 / raise 4.8 / jam 2.6 | fold 22.5 / call 70.1 / raise 4.9 / jam 2.5 | 0.1%p | 3-bet 7 봇 3.6·기록 4.0 |
| `p30_flat_sb_limp_vs_bb` | mean_of_last_2_steps | call 57.7 / raise 42.3 | call 57.9 / raise 42.1 | 0.2%p | - |
| `p30_flat_utg1_vs_bb` | mean_of_last_2_steps | fold 28.4 / call 66.6 / raise 5.0 / jam 0.0 | fold 28.4 / call 66.7 / raise 4.9 / jam 0.0 | 0.1%p | 3-bet 7 봇 3.6·기록 3.3 |
| `p30_flat_utg2_vs_bb` | mean_of_last_2_steps | fold 25.9 / call 67.9 / raise 5.9 / jam 0.3 | fold 25.8 / call 68.3 / raise 5.7 / jam 0.3 | 0.3%p | 3-bet 7 봇 4.3·기록 3.8 |
| `p30_flat_utg_vs_bb` | mean_of_last_2_steps | fold 31.6 / call 63.9 / raise 4.5 / jam 0.0 | fold 31.0 / call 64.5 / raise 4.5 / jam 0.0 | 0.6%p | 3-bet 7 봇 3.3·기록 2.9; 3-bet 8 봇 1.2·기록 1.7 |
| `p30v1_co_vs_sb_3b40` | mean_of_last_2_steps | fold 54.5 / call 31.1 / raise 0.0 / jam 14.4 | fold 55.4 / call 30.7 / raise 0.0 / jam 13.9 | 0.9%p | - |
| `p30v1_utg1_vs_sb_3b40` | mean_of_last_2_steps | fold 52.0 / call 34.3 / raise 0.0 / jam 13.7 | fold 51.3 / call 34.6 / raise 0.0 / jam 14.1 | 0.7%p | - |
| `p30v1_utg_vs_btn` | mean_of_last_2_steps | fold 48.3 / call 32.3 / raise 0.0 / jam 19.4 | fold 48.4 / call 32.4 / raise 0.0 / jam 19.2 | 0.2%p | - |
| `p40_flat_lj_vs_bb` | mean_of_last_2_steps | fold 19.5 / call 74.3 / raise 5.8 / jam 0.4 | fold 19.8 / call 73.9 / raise 5.9 / jam 0.4 | 0.4%p | - |
| `p40_flat_sb_limp_vs_bb` | mean_of_last_2_steps | call 51.1 / raise 48.9 | call 51.2 / raise 48.8 | 0.1%p | - |
| `p40_flat_utg1_vs_bb` | mean_of_last_2_steps | fold 31.8 / call 63.9 / raise 4.3 / jam 0.0 | fold 31.7 / call 64.1 / raise 4.2 / jam 0.0 | 0.1%p | 3-bet 7 봇 2.9·기록 0.4; 3-bet 8 봇 1.4·기록 3.9 |
| `p40_flat_utg_vs_bb` | mean_of_last_2_steps | fold 32.2 / call 64.4 / raise 3.4 / jam 0.0 | fold 31.7 / call 64.8 / raise 3.5 / jam 0.0 | 0.5%p | - |
| `p40v1_co_vs_sb_3b40` | converged_final_step | fold 49.9 / call 39.7 / raise 0.0 / jam 10.3 | fold 49.7 / call 40.0 / raise 0.0 / jam 10.2 | 0.3%p | - |
| `p40v1_utg1_vs_sb_3b40` | mean_of_last_2_steps | fold 44.4 / call 52.3 / raise 0.0 / jam 3.3 | fold 44.9 / call 52.0 / raise 0.0 / jam 3.1 | 0.5%p | - |
| `p40v1_utg_vs_btn` | mean_of_last_2_steps | fold 58.1 / call 32.1 / raise 0.0 / jam 9.8 | fold 58.5 / call 31.4 / raise 0.0 / jam 10.1 | 0.7%p | - |
## 알려 둘 것 (정밀 검사·후속)
1. **3벳 크기**: 플랫콜 기록의 3벳은 7bb·8bb 두 크기다. 연결은 3벳 빈도만 기록대로 하고 크기는 봇 습관(3.7배 = 7.4bb).
   클래스 단위로 보면 계산기가 8bb 를 고르는 패(예: 40bb UTG+1 오픈 vs BB 의 KK 87%·AA 90%)도 봇은 대부분 7bb.
   처음 검사(라벨 단위 비교)에서 이것 때문에 4건이 실패했고, 행동 종류 단위로 바꿨다(커밋 34e98066). 크기까지 따르려면 연결 확장이 필요하다.
2. **SB 림프 BB 뿌리 불안정**: 콤보의 39%(30bb)·45%(40bb)가 단계마다 체크↔레이즈로 뒤집혀, 평균 50/50 으로 찍힌 클래스가 많다.
   봇은 그 50/50 을 그대로 따른다. 차이가 작은 패들이지만 정밀 검사 1순위.
3. 모든 기록은 quick(대칭 스택, chip EV, 다수가 3단계 상한의 마지막 2단계 평균). 단계별 원자료는
   `claude/archive-gto-runs-20261024` 에 보관 — P144 등 정밀 검사는 거기서 이어간다.
4. 40bb UTG+2 오픈 vs BB 는 계산 중(`claude/p40_flat_utg2_20261024`). 들어오면 refresh_records → rebuild → 이 검사, 그리고
   verify_gto_pf 의 UTG+2 두 검사를 바꾼다.
