# TDA POSITION / BLIND DESIGN — 2026-09-27

Scope: t2의 NLH 토너먼트 좌석·BTN·SB·BB·테이블 이동·관련 쇼다운/odd-chip 순서.
전략 튜닝과 무관하며 UI가 아니라 엔진 규칙이 단일 출처다.

## 1. 2026 Poker TDA contract

- Rule 34 Dead Button: 토너먼트는 dead button을 쓴다. BTN은 빈 좌석일 수 있다.
- Rule 36-B: 탈락으로 dead BTN이 생기고 BTN→SB 사이에 추가 빈 좌석이 있으면 정상 blind progression을 보존하며 BTN을 빈 좌석 위로 전진시켜 incoming seat를 최대화한다. 누구도 BB를 건너뛰거나 연속으로 내게 만들면 안 된다.
- Rule 36-C Heads-up: BTN=SB, preflop first, postflop last. HU 시작 때 같은 플레이어가 BB를 두 번 연속 내지 않게 BTN을 조정한다.
- Rule 11: broken/new player는 BTN/SB/BB 포함 어느 자리도 받을 수 있으나 SB와 BTN 사이에는 들어가지 않는다. t2는 field RNG 기반 무작위 seat assignment를 쓴다.
- Rule 12-A: balance source는 다음 BB 예정자. destination은 worst position이고 SB는 절대 아니다.
- Rule 12-D: 가장 큰 테이블보다 3명 이상 부족해 blind 진행이 영향을 받는 테이블은 play를 멈추고 balance를 기다린다.
- Rule 18-A: final street에 bet이 없으면 BTN 왼쪽 첫 플레이어부터 showdown 공개.
- Rule 21-A: board-game split의 odd chip은 BTN 왼쪽 첫 승자부터 최소 칩 단위로 지급.
- RP-11: BBA는 big-blind-first 계산. session은 BB 먼저, 남은 stack에서 ante를 게시한다.

## 2. Engine representation

fieldsim.Table이 물리 seat와 세 marker를 소유한다.

- button_seat: BTN marker, 빈 좌석 가능
- sb_seat: SB marker, 빈 좌석 가능
- bb_seat: 현재 BB 의무를 지는 생존 좌석
- button: legacy save 호환용 live-index

BTN을 압축된 생존자 배열 index로 규칙 판단에 쓰지 않는다.

## 3. Per-hand layout

Table.hand_layout()이 토너먼트 position의 단일 출처다.

반환값:
- physical button / sb / bb
- live seat → position map
- pre_seats / post_seats
- dead_button / dead_sb

play.Hand은 토너먼트 경로에서 explicit layout을 그대로 받는다.
따라서 dead SB/BTN을 다음 생존자에게 압축하지 않는다.

Example — BB bust:
previous BTN S1 / SB S2 / BB S3 bust / UTG S4
next BTN S2 / dead SB S3 / BB S4
S4가 SB가 되는 것은 금지다.

## 4. Rotation

한 hand 종료 후 기준축은 BB다.

1. next BB = old BB 다음 생존자
2. non-HU: next SB marker = old BB physical seat
3. next BTN marker = 새 SB 바로 전 physical slot. 이것이 Rule 36-B의 "blind progression 보존 + incoming seat 최대화"를 직접 표현한다.
4. BTN/SB marker는 비어 있을 수 있지만 BB는 항상 생존 좌석이다.
5. HU: next BB는 old BB 다음 생존자, 다른 생존자가 BTN=SB

## 5. Bust / balance ordering

advance_button()은 hand 결과 stack 반영 뒤, busted seat를 물리 slot에서 제거하기 전에 다음 blind obligation을 계산한다.
그 뒤 _collect_busts()가 seat를 비운다. 그래서 old BB bust가 정확히 dead SB를 만든다.

_balance():
- source = next_bb_player()
- destination = worst_open_seat(), SB 제외
- broken table = Rule 11 허용 seat pool에서 RNG 배정
- step_others는 Rule 12-D에 따라 max table보다 3명 이상 적은 table을 그 round에서 halt

## 6. Persistence and old live-state migration

live2 state schema:
- blind_state = tda_dead_button_v1
- table마다 button_seat / sb_seat / bb_seat 저장

신규 state는 세 marker를 그대로 복원한다.
구 state는 button_seat만 있었으므로 1회 migration한다:
- saved BTN 바로 다음 physical slot이 비어 있으면 dead SB 후보
- BB는 그 뒤 next live seat
- 새 schema 저장 뒤부터 다시 추정하지 않는다

이 migration은 현재 발견된 BB bust 후 HERO가 잘못 SB가 된 진행중 state를 복구하기 위한 호환 경로다.

## 7. Parallel HERO / OTHER round

UI branch parallel worker는 table row 전체를 ownership 단위로 merge하므로 세 blind marker도 worker table 소유 상태로 함께 merge된다.
merge 뒤 bust collection / balancing은 한 번만 수행한다.

## 8. UI contract

- dead BTN: 빈 physical seat에 D 표시
- dead SB: 빈 physical seat에 SB · DEAD 표시
- position label은 engine hand_layout 결과만 사용
- ⋯ 메뉴: 필드 / ITM / 내 chip rank / stack / average / money jump
- 오른쪽 swipe: 별도 전체 stack standings drawer
- standings API는 hidden persona, hole cards, reads, intents를 노출하지 않음

## 9. Verification gates

Promotion 전에 모두 통과해야 한다.

- tools/verify_tda_dead_button.py
- tools/verify_tda_live_integration.py
- UI line: tools/verify_parallel_tables.py
- UI line: tools/verify_ui_tournament_panel.py
- changed Python modules py_compile

검증 전에는 canonical branch에 merge하지 않는다.
