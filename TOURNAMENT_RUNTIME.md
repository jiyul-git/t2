# TOURNAMENT RUNTIME — 9-max, TDA, parallel tables, UI pipeline

## 2026-10-02 코드 재감사 동기화

live2/fieldsim 물리9max가 UI runtime이고 tools/regress는 tourney alternate runtime이다. hero Book은 저장되지만 bot-only table은 새 Hand/Book으로 시작한다. showdown 관측은 shown/muck 판정 전에 수행되어 visibility 후속 수정이 필요하다. standalone setup 목록의 action_events/telemetry_sync 누락은 기존 모듈 배선으로 복구했다.

현재 근거: [전체 구조](docs/semantic_audit/CURRENT_ARCHITECTURE_AUDIT.md), [개념→함수](docs/semantic_audit/CONCEPT_FUNCTION_REGISTRY.md), [문서 차이](docs/semantic_audit/DOCUMENT_DRIFT.md), [리팩터링·검증](docs/semantic_audit/REFACTOR_AND_VERIFICATION.md). 아래 과거 실험/commit별 증거는 그 시점 기록이며 현재 배포 인증이 아니다.

## 1. 9-max baseline

Main tournament baseline is 9-max.
Historical module-level 8-max assumptions were removed from field table creation/balancing.
Initial table equalization is setup, not an in-tournament move, and must not increment hero move counters.

## 2. TDA physical-seat model

Engine owns physical:
- `button_seat`
- `sb_seat`
- `bb_seat`

BTN/SB may be dead/empty. BB is a live obligated seat.
compressed live-player index를 규칙의 source로 쓰지 않는다.

`Table.hand_layout()`이 per-hand position의 단일 출처:
- physical BTN/SB/BB
- live seat -> position
- pre/post action order
- dead button/dead SB

## 3. Rotation rules

Non-HU:
1. next BB = old BB 다음 live player
2. next SB marker = old BB physical seat
3. next BTN = new SB 직전 physical slot
4. BTN/SB는 dead 가능

HU:
- BTN = SB
- BTN preflop first, postflop last
- transition에서 같은 player가 BB를 연속으로 내지 않도록 조정

BB bust example:
old BTN S1 / SB S2 / BB S3 bust / UTG S4
-> next BTN S2 / dead SB S3 / BB S4.

## 4. Balance / broken tables

- balance source = next BB 예정자
- destination = worst open position, SB 제외
- broken table seat assignment = allowed seat pool에서 field RNG
- table이 largest table보다 3명 이상 부족해 blind progression에 영향이면 balance를 기다림

Showdown/odd chip:
- final street no-bet showdown은 BTN 왼쪽 첫 live player부터
- split odd chip은 BTN 왼쪽 첫 winner부터

## 5. Persistence

live state stores:
- `blind_state = tda_dead_button_v1`
- button_seat/sb_seat/bb_seat

legacy state는 1회 migration 후 다시 추정하지 않는다.

TDA verification:
- `verify_tda_dead_button.py`: 16 checks PASS
- `verify_tda_live_integration.py`: PASS
- `verify_button_rotation.py`: PASS

## 6. Parallel table round

한 tournament hand number를 하나의 round snapshot으로 본다.

```
round snapshot
├─ HERO table: main process
└─ OTHER tables: worker
        ↓
ownership merge
        ↓
collect busts once
balance once
```

Ownership:
- HERO branch: hero-table stacks/table state/tilt/UI result
- worker: non-HERO pids/tables/tilt/log
- shared tournament metadata는 main에서 유지

Both sides start from the same round snapshot.
해당 round 도중 다른 table의 bust/stack change는 다음 round부터 전략에 반영.

base_key mismatch는 fail closed.

## 7. Final-table latency closure

세 원인 처리:
1. exact ICM subset-DP를 safe 2..9-player state에 사용.
2. single-table이면 empty worker/pending을 만들지 않음.
3. bot compute-ahead를 motion-gated pipeline으로 변경.

Live order:
`HERO motion -> bot compute -> bot motion -> ACK -> next bot compute`

Server는 threaded라 ACK와 read-only history/memo/tournament 요청이 long gameplay request 뒤에 막히지 않는다.

100-entry / ITM15 / final 9-player API playtest:
- HERO decisions 3
- streamed events 10
- motion ACK 10/10
- timeout 0
- bot next-compute gap min 0.0243s / avg 0.1410s / max 0.4819s
- read-only max latency: history 0.0013s, memos 0.0026s, tournament 0.0048s

## 8. UI current contract

- play-only local table UI
- no watch-mode restore
- portrait/character assets frozen unless explicit request
- hero action dock is absolute bottom dock; table geometry fixed when controls appear/disappear/fold
- hero hole cards 46×64px
- inter-card gap 4.6px
- cards 3px lifted from separator
- side chip lanes: 9 o'clock x=22%, y=51%; 3 o'clock x=78%, y=51%
- dead BTN: empty physical seat에 D
- dead SB: SB · DEAD
- tournament info는 menu
- right swipe는 full standings drawer
- standings가 hidden persona/hole cards/reads/intents를 노출하면 안 됨

Current browser pipeline cache checkpoint: `app.js?v=77` (`test` scheduled-tournament admission/refund UI).

Runtime folders are not source of truth.
source -> runtime copy는 `ui/tools/setup_run_dir.sh` 경로를 사용.

## 9. Scheduled tournaments / durable wallet V1 (2026-10-05, test)

Manual game creation is replaced by scheduled buy-in tournaments. Personal chips,
entry receipts and authoritative live state share one SQLite transaction in
the personal data folder, separate from replaceable game code. First installation
creates `T2/system/` plus `T2/personal/`; updates contain and copy system files only.
`personal/installation.json` binds the existing wallet. Missing/corrupt wallets or
bindings stop an update/startup without creating a replacement account or grant.
Manual runtime copies default to the OS user-data folder outside code, with an
optional external `T2_DATA_DIR`. Legacy `userdata/` requires explicit migration.
Stop the server before an update or migration. See [installation commands](ui/README.md#개인-지갑을-분리한-설치와-업데이트-test-2026-10-05).
Off-screen registered seats check/fold and pay blinds; late entry/re-entry joins the
existing field between hands. Integer payouts conserve the pool and credit once.
The existing single-HERO installation remains the account scope. Operational
amounts/schedule are provisional and configurable. This is not yet a production
server/master promotion. See [implementation and verification](docs/semantic_audit/SCHEDULED_TOURNAMENTS_V1.md).

2026-10-06 KST follow-up: default slots are two hours apart, rotating standard,
turbo and deep in Seoul time. Paid/cancelled legacy receipts retain their rules.
Late requests persist a waiting admission, then join the existing field after
their request timestamp at a completed hand. Takeover uses the fixed entry-request
time, not a moving wall-clock target. Unseated requests refund atomically if the
field closes naturally first. Selected admissions get scheduler priority; expired
unowned fields do not crowd its queue. With `T2_UI_DEFER=0`, vclock settlement
computes the needed coverage synchronously rather than waiting for an absent pool.

## 10. Historical sources

- `NINE_MAX_MIGRATION.md`
- `TDA_POSITION_DESIGN.md`
- `PARALLEL_TABLE_ROUND.md`
- `UI_CURRENT_STATUS.md`
- CURRENT_STATUS의 final-table/UI sections
