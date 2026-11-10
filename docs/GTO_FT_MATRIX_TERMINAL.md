# ft 전체 트리: 행렬 끝점 (모든 스택 공용) — 2026-11-10

배경: 클래스별 고정 값 표는 트리 레인지가 바뀌면 두 자리 합이 팟과 어긋난다(ft60 1단계: 합−팟 중앙값 +5bb, D/U 미개선). 끝점 값을 손패×손패 행렬 M 으로 두고 트리 안에서 상대의 현재 레인지로 푼다.
검토: `docs/GTO_FT60_MATRIX_TERMINAL_REVIEW.md`, 진단: `docs/GTO_FT60_STEP1_DIAGNOSIS.md`.

## 바뀐 것
| 파일 | 내용 |
|---|---|
| `tools/gto_fulltree/t2_matrix_terminal.patch` | 엔진(census 79a9aca6 의 `t2cont.rs`, `mod.rs`) 패치: 표 seats[].matrix(169×169 행우선 M[h*169+j])가 있으면 끝점 값 = Σ_j dist_opp[j]·M[h][j] (dist_opp = 그 순간 상대 도착 분포). matrix 없는 표·표 없는 끝점은 이전과 비트 동일 |
| `tools/gto_fulltree/t2_pf_solve.rs`, `t2_ft_export.rs` | 풀이·내보내기 드라이버(원본 소스가 없어 ft40/ft100 조정 세션이 다시 쓴 것을 0단계 재현으로 검증해 가져옴). `T2_EXPORT_STATIC_MATRIX=1` 이면 정적 행렬 `static_matrix`도 낸다 |
| `tools/gto_fulltree/ft_coord_setup.sh` | 위를 적용·빌드(끝줄 FT_COORD_SETUP_OK). 모으는 세션은 `ft_board_setup.sh` 대신(또는 뒤에) 이것 |
| `tools/gto_fulltree/ft60.py` | `FT_STACK`(데이터 data/ft<스택>, 브랜치 claude/ft<스택>_board_<n>, 설정 `FT_CFG`), `FT_MATRIX_ALL`(기본 1: 모든 헤즈업 끝점이 행렬 끝점. 0 이면 이전 규칙), prepare 가 `step<k>/static_matrix.npz` 저장, collect 가 행렬을 표에 그대로 저장, next_tables 가 행렬 단위로 섞음 |
| `tools/gto_fulltree/ft_board.py` | `FT_STACK` 지원(보드 세션 규칙 동일). 행렬 끝점이면 이미 `matrix_sums.npz` 를 내보낸다 |

## 재현 시험 (모두 통과)
1. 비트 동일(행렬 없음): 0단계 표(`step0/tables`)로 처음부터 50회 → 기록된 `step0/solve/solve_50.json` 과 gap_total·gaps·evs·노드 수 전부 비트 동일(gap 0.1402187471292131).
   (0단계 100·250회 풀이·체크포인트 sha·덤프 sha·끝점 입력 80개 sha 는 새 소스 검증 때 이미 비트 동일을 확인.)
2. 행렬 의미: 끝점 40개 전부를 정적 행렬(`static_matrix`)과 정적 값을 담은 행렬 표로 넣고 5회 풀이 vs 표 없음 5회 → gap_total 5.126074928 vs 5.126079447 (상대 8.8e-7), gaps 최대 차 2.4e-5. 정적 행렬 @ 분포와 정적 값의 차이 최대 0.0085bb(정적 식의 팟 상한 클립은 분포에 선형이 아니라서 생기는 차이).
3. 합=팟: 저장된 1단계 3벳 행렬 27개는 손패 쌍마다 |M_A[h][j]+M_B[j][h]−팟| 최대 2.4e-4bb.

## 규칙
- 채움(보드 풀이 밖 칸, den=0): 정적 행렬로 채운다. collect 가 자리마다 `matrix_fill_cells`(채운 칸 비율)와 `matrix_fill_mass`(끝점 레인지 가중 질량 비율)를 보고서에 남긴다. 1단계 데이터에서는 도착 레인지가 169클래스 전부여서 둘 다 0.
- 섞기(행렬 단위): 새 표 = (1−a)·이전 행렬 + a·M_A∪B. 이전 행렬 = 표의 행렬 | 이전 표가 벡터뿐이면 정적 행렬(열 복제 벡터는 칸 단위로 합=팟이 안 돼서 쓰지 않는다; 기록 `legacy_vector_old_replaced_by_static`) | 표가 없던 끝점이면 정적 행렬. a = 0.5 (순환 끝점 0.25).
- 합=팟 투영: 섞은 뒤 칸마다 r = M_a[h][j]+M_b[j][h]−팟 를 두 자리에 반씩 빼서 모든 칸에서 합=팟(칸 단위, 행렬 모양 유지). 투영 전 잔차는 표의 `provenance.pair_sum_projection` 에 남는다(1단계 데이터로 시험: 투영 전 0.23bb, 후 3.6e-15). 보드에서 온 M 만 쓰면 잔차는 거의 0이고, 정적 행렬이 섞일 때만 생긴다(정적 식의 위치 가중치).
- 정적 유지 끝점: `step<k>/static_nodes.json`(노드 번호 목록)이 있으면 next_tables 가 그 끝점의 표를 만들지 않는다(플랍 실패 > 0.6% pot 규칙).
- 판정 항목 추가(collect 보고서): 자리마다 `Dm` = 레인지 가중 L1(|M_A∪B − 이번 단계가 쓴 표 행렬|)과 `Dm_over_U`, 끝점마다 `dM_vs_prev_step`(이전 단계 M 과의 레인지 가중 L1), `sum_check`(보드 M 칸 단위 합−팟). 기존 D/U(접은 벡터), A·B 복제는 그대로.

## 남는 한계
- 레인지가 크게 이동하면 M 자체가 달라진다(M 은 보드 풀이 때 레인지 아래의 균형 전략으로 잰다). 단계마다 새 보드로 M 을 다시 재므로 고정점에서(레인지가 더 안 움직일 때) 해소된다. 단계 간 `dM_vs_prev_step` 이 줄어드는지로 확인한다.
- 3명 이상 플랍 갈래는 정적 값(간이)이다 — 이번 범위 밖.
- 정적 행렬로 채운 칸은 위치 가중치(R)와 팟 클립 때문에 정확히 영합이 아니다(투영으로 맞춤).
- 보드 시간: 행렬 모드 단일 레이즈 팟 보드 4장 529초(BTN 오픈→BB 콜), 569초(HJ 오픈→BB 콜) vs 비행렬 279초, 303초 → 약 1.9배(패널 A 첫 층 보드, 4 workers×1 thread). 72보드 묶음 ≈ 2.6h(행렬) vs 1.4h(비행렬), 3벳 행렬 묶음 1.9h(기존 실측). prepare 의 배분 예상 시간에 반영했다. 다른 층 보드는 달라질 수 있다.

## 다음 단계 계획 (ft60)
- 현재까지: 1단계 보드(80/80)에서 3벳 행렬 끝점 27개의 M 이 있고, 단일 레이즈 13개는 벡터뿐.
- 제안: 2단계 입력을 `next_tables 1` 로 만든다 → 27개는 행렬 표(0.5·정적 행렬+0.5·M, 합=팟 투영), 13개는 벡터 표. 트리는 처음부터 정확 gap < 0.02 까지, 이어서 `prepare 2`(FT_MATRIX_ALL=1: 40개 전부 행렬 끝점 묶음 80개, 예상 총 약 170 컨테이너 시간 = 20세션 × 약 8.5h). 2단계 보드부터 모든 끝점이 행렬이 되고, 3단계부터 전부 행렬 단위로 섞인다.
- 다른 스택(ft40, ft100…): 이 브랜치의 `tools/gto_fulltree/`(ft60.py, ft_board.py, ft_coord_setup.sh, 패치·소스)를 가져가 `FT_STACK=<스택>` 으로 쓴다. 첫 단계(표 없음, 전부 정적)부터 `FT_MATRIX_ALL=1` 로 모든 헤즈업 끝점을 행렬 모드로 풀 수 있다. 0단계 설정은 `FT_CFG` 로 지정.
