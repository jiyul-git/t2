# 2026-10-04 플레이 피드백 반영 (test only)

보고한 실행본: UI_SOURCE origin/master 62abf3f. 이번 변경 출발점: 3de478c5.

| 피드백 | 처리 |
|---|---|
| 레벨 상승이 빠름 | 새 UI 게임에 분 단위 가상 시계, 포맷 속도 기본값과 독립 설정 추가 |
| 경과 시간 표시 | UI 상단 가상 경과, 기존 게임은 시간 역산 없이 구 방식 표시 |
| 브레이크 창·남은 시간 | 55분 플레이 / 5분 휴식, 서버 기한 기반 countdown, 정산 대기 후 닫힘 |
| 76핸드 뒤 10분 이상 멈춤 | 준비 조회에 네트워크 timeout/재시도와 워커 경과 표시. 최신 test 단일 테이블 KeyError 재현·수정. 원래 신고의 원인은 미확정 |
| 페어 보드 인식 | texture.classify의 paired/trips, plan.board_paired, paired_board_flush_raise_damp와 리버 기여 판정 경로 확인. 미구현 상태 아님. 실제 신고 핸드의 인지/소비 검토는 남음 |
| 리레이즈가 큼 | 체크레이즈 배수 2.7+0.09·aggr+0.06·overbet, danger 승수·±12% 잡음·2.2~5.0 clamp 확인. 프리플랍/밸류/체크레이즈를 합쳐 일괄 축소하지 않음. 실제 표본 감사 남음 |
| 큰 블러프에 잘 폴드 | 응답 판단은 상대 사이즈 인지→팟오즈→ICM/리딩/주관 문턱 경로. 단순 객관 콜 EV 하나만 쓰는 구조라는 해석은 부정확. 실제 베팅 라인/레인지/인지 가격 표본이 없어 행동 계수 변경하지 않음 |

가상 핸드 시간은 기존 설계의 raw duration 가정이다. 공식 근거는 레벨 길이에만 해당한다.
UI README에 적용 범위와 표본 보정 미적용을 명시했다.

기존 병렬 검증 `verify_parallel_table_processes`: 수정 전 3de478c5와 수정 후 모두
P1 bot_log_same=false / diff_keys=[]; P2 라운드 시작 문맥 통과. 기존 실패로 기록하며
통과라고 보고하지 않는다. 이번 변경은 parallel worker 구현을 바꾸지 않는다.

검증: 23-gate PASS 23 / FAIL 0 / TIMEOUT 0. UI 9명 4핸드와 18명 4핸드
모두 통과(칩 보존·좌석·홀카드 누출·legal·스트림). 시계·저장·HTTP 브레이크
수명주기·JS 남은 시간/대기/닫힘 검증 통과. 균등 안테 검증 통과.

completeness: sites 1,145 / owned 1,145 / unowned 0, span errors 0.
virtual_tournament_clock 개념과 코드 span을 registry에 추가했다.
