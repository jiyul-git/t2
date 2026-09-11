# INSTRUMENTATION_BASELINE

    date: 2026-09-10
    tag:  instrumented_eq_v1

판단 로직 수정 **전**, 계측 확장 **완료** 상태. 데이터 축적의 기준점.

---

## production_decision_logic: unchanged

    action_fingerprint:
      seeds:  3000-3005
      hands:  30 each
      method: 전체 full_log 이어붙여 SHA-256
      sha256: 8f02a035d46af7e7ad929843f509cf6362a94221f6d00db75028d63e530c8eaa

    변경 전 백업 코드와 변경 후 코드가 위 지문에서 완전 일치.
    _eq_current 는 자체 random.Random 을 쓰므로 make_plan 의 rng 소비 순서를
    건드리지 않는다.

    tools/wirecheck.py   개념 36개 / 명세 36개, 배선 누락 없음
    tools/repro_test.py  A~D 전부 OK
    성능                 25핸드 x 2시드 기준 16.11s -> 16.58s (+2.9%)

---

## added (기록 전용 — 판단에 쓰지 않는다)

    eq_current      보드를 돌리지 않은 에쿼티. 지금 쇼다운했다면.
    eq_delta        eq - eq_current. 남은 카드가 만드는 변화량. 음수 가능.
    eq_sims         make_plan 400 / refresh 300
    eq_seed         해당 계산에 넘긴 seed
    outs_true       draw_strength 원값 (calc_noise 미적용)
    my_range_n      내 레인지 콤보 수
    my_range_sig    sha256(정렬된 콤보 문자열)[:16]
    opp_range_n     상대 레인지 콤보 수
    opp_range_sig   동일 방식

    기록 위치: plan_state(plan.py make_plan / refresh) -> session.py intents

    _range_sig 의 정규화(정렬 후 sha256, 16자 절단)는 앞으로 바꾸지 말 것.
    바꾸면 과거 아카이브와 대조가 끊긴다.

    _eq_current 는 _eq_vs 의 pool 구성 규칙(opp_range 6콤보 미만이면 0.35 근사)과
    seed 유도(zlib.crc32(repr(...)))를 그대로 복제한다. 유일한 차이는
    남은 보드를 뽑지 않는다는 것 하나뿐이어야 한다.

---

## known_issue (이번 배치에서 고치지 않음)

    refresh.outs    = draw_strength(hero, board)              <- 날것
    make_plan.outs  = draw_strength * calc_noise('outs')      <- 체감값

    같은 값을 두 함수가 다르게 계산한다. rel 은 이미 같은 문제를 고쳤으나
    (refresh 주석 참조) outs 는 그 수정을 못 받았다.
    h61 에서 why 는 "12아웃"인데 outs 필드가 9였던 원인.
    판단 로직 변경이므로 계측 배치에 넣지 않았다.

    regression_baseline: stale / unreliable
      tools/regress.py 의 tools/baseline.json 이 이전 어느 커밋 시점에
      이미 어긋나 있다. 변경 전 백업 코드로 돌려도 동일하게 실패한다.
        기준선 VPIP 21.7% PFR 13.2% flop 43.3%
        현재   VPIP 18.2% PFR 11.8% flop 36.7%
      항상 실패하므로 진짜 회귀와 구분되지 않는다.
      회귀 검증은 위 action_fingerprint 를 쓸 것.

---

## 미해결 원인 (조사 중, 수정식 미확정)

    (1) plan.py:402  eq >= pcz 폴백이 made 만 보고 giveup/showdown 을 가른다
                     -> #44 (AK/Q77), #58 (AQ/642)
                     원 커밋 4462c0b 의 의도는 "rel 0 AND made 0" 이었으나
                     구현이 made == 0 만으로 과일반화됨

    (2) eq >= pcz 분기가 semibluff 분기보다 위에 있어 드로우를 선점
                     -> h37 (9sTs/574, outs 9, delta +0.46)
                     단순 순서 교체는 탈락 (AsAc/투페어까지 빨려 들어감)

    (3) session.py:441  first=(key not in h.plans or street == 'flop')
                     플랍에서 재행동할 때마다 make_plan 전체 재실행 -> RNG 재추첨
                     -> h61 semibluff -> showdown
                     저장소 첫 커밋 이전부터 존재, 근거 미기록. unreviewed legacy

    (4) plan.py:440  has_sd = made >= 1 or eq >= 0.42 + 0.05*mw
                     eq 가 all-in equity 라 드로우 지분과 쇼다운 지분을 구분 못 함
                     -> h34 (9d8d/Jd7dQh, outs 22, eq_current 0.004, delta +0.494)

    공통 원인 가설: eq 가 현재 쇼다운 강도와 미래 개선분을 합친 단일 값인데
    make_plan 이 그것을 분류 근거로 재사용한다.

    검증 보류 사유: 아카이브에 opp_range 가 없어 35% 근사로 계산했고,
    기록된 eq 와의 절대 격차가 최대 0.444 로 delta 신호(최대 0.494)와 맞먹었다.
    -> 이번 계측 확장이 그 한계를 없애기 위한 것.

    delta_eq 탐색 결과 (35% 근사, made==0 n=84):
      outs 와 Pearson +0.77 / Spearman +0.65   <- 주된 변동은 아웃츠 수
      rel  와 Pearson -0.43 / Spearman -0.23   <- rel 의 재표현은 아님
      계획 라벨 중앙값은 정렬되나 범위가 전부 겹침
      outs 9 여섯 건의 delta 가 +0.461 ~ +0.090 으로 흩어짐 (기존 신호로 설명 안 됨)

---

## 다음 순서

    1. 이 스냅샷에서 시작해 세션 진행 (데이터 축적)
    2. 실제 opp_range 위에서 eq_current / eq_delta / outs_true 수집
    3. (1)(2)(4) 가 하나의 eq 분해 문제인지 재검증
    4. 그 다음에야 production 수정

    회귀 검증 명령:
      python3 tools/wirecheck.py
      python3 tools/repro_test.py
      action_fingerprint 재계산 (위 sha256 과 대조)

---

## 분석 도구 (이번 조사에서 추가, 전부 읽기 전용)

    tools_giveup_decompose.py   giveup 75건을 10개 축으로 분해
    tools_cf_719.py             719 조기 return 반사실 (0/18, 필드 대입 6/720)
    tools_hassd_variants.py     has_sd A/B/C 비교
    tools_eq_decompose.py       특정 핸드의 runout vs frozen
    tools_pcz_semibluff.py      eq >= pcz AND outs >= 8 모집단
    tools_eq_modes.py           아카이브 전체 eq 2모드 계산 -> eq_decomp.json
    tools_delta_probe.py        made==0 고정, delta_eq 와 기존 변수 관계
