# t2 — 포커 토너먼트 시뮬레이터

봇이 인간처럼 사고하도록 모델링하고, 그 사고에서 행동을 생성하고,
관찰자가 행동으로부터 사고방식을 역추론할 수 있게 하는 것이 목표다.
10,489줄 / 33개 모듈.

---

## 작업 원칙 — 반드시 지킬 것

### 1. 지금은 원인 규명 단계다. `plan.py` 판단 로직을 수정하지 마라.

수정과 검증이 섞이면 원인을 잃는다.

**현재 baseline: `8dc14d3`** (2026-09-12). 행동 지문:

```
python3 tools/fingerprint.py --seeds 3000-3005 --hands 30   # 격리 폴더에서
1dd5d83f7a638d174636d7dc44d39f1c2250ce35a1d674d5789ff90b57935e59
```

레시피는 `tools/fingerprint.py` docstring 에 박혀 있다. 바꾸면 과거와
대조가 끊긴다.

**historical reference — 아래는 `f7e03ac` 시절의 지문이다.**

```
seeds 3000-3005 × 30핸드 full_log SHA-256
8f02a035d46af7e7ad929843f509cf6362a94221f6d00db75028d63e530c8eaa
```

계측 확장 전후가 동일함을 보인 기록이다(`INSTRUMENTATION_BASELINE.md`).
**현재 엔진의 지문이 아니고 위 값과 비교 대상도 아니다** — 그때의
레시피(엔트리 수·히어로 정책)가 기록되지 않아 재현할 수 없다.
지우지 말 것. 그 시점의 분석이 어느 코드에 대한 것이었는지 가리키는
유일한 표식이다.

`plan.py`의 판단 분기를 건드리면 현재 지문이 깨지고, 지금까지의 분석이
어느 코드에 대한 것이었는지 추적 불가능해진다.

**허용:** `tools/` 아래 읽기 전용 분석 스크립트 추가, 기록 전용 계측 필드 추가
**금지:** 조건식·임계값·확률 계수 변경, 분기 순서 변경

수정에 들어갈 때는 먼저 반사실 evaluator로 영향 범위를 재고,
그 결과를 보고 나서 별도 브랜치에서 한다.

### 2. 임계값을 새로 발명하지 마라.

현재 코드의 문제 상당수가 "첫 커밋부터 박혀 있는데 근거가 기록되지 않은
숫자"다. 같은 실수를 반복하지 않는다. 수정안은 기존에 이미 존재하는
값을 재사용하는 것만 후보로 삼는다.

### 3. 새 plan 라벨을 추가하지 마라.

라벨을 늘리면 그 라벨을 만드는 조건문이 늘고, 조건문마다 임계값을
새로 만들어야 한다. `draw` 같은 것은 핸드 상태이지 행동 계획이 아니다.

### 4. 코드를 먼저 읽고 진단한다.

로그나 통계만 보고 원인을 추정하지 않는다. 실제 분기를 따라간다.
이 프로젝트에서 여러 차례, 통계로 세운 가설이 코드를 읽자 틀린 것으로
드러났다.

### 5. `why` 로그는 스트리트별로 누적된다.

특정 스트리트의 판정만 세려면 `'{street}: '` 접두사로 걸러야 한다.
이걸 놓쳐서 402줄 발동 건수를 39건으로 잘못 셌고(실제 22건),
최종 else giveup을 383건으로 잘못 셌다(실제 270건).

---

## baseline 이력

플레이어 식별 문제를 잡은 두 커밋이다. 둘 다 `plan.py` 무수정이다.

```
f7e03ac  seat-key contamination
   │     Tilt.state 의 키가 str(seat) 였다. 테이블마다 좌석 번호가 겹쳐
   │     서로 다른 사람이 틸트와 shown(쇼다운에 깐 패)을 공유했다.
   │     **"조금 다른 구현"이 아니라 오염된 구현으로 취급한다.**
   ↓
a247f7f  seat → pid 격리
   │     변환 규칙은 play.Hand.pid_of 하나. 새 식별자는 만들지 않았다.
   │     f7e03ac 대비 400핸드 divergence 395/398, 탈락 순서·최종 생존자 변경.
   │     → 전략이 바뀐 것이 아니라 기존 엔진이 틀린 상대 정보로 판단하고
   │       있었던 것이다. 두 엔진의 행동을 전략 비교로 읽지 말 것.
   ↓
8dc14d3  decay_all 프로필 격리          ← **현재 baseline**
         Tilt 감쇠가 그 사람 자신의 프로필을 쓴다 (context.pid_prof).
         a247f7f 대비 400핸드에서 액션·칩·탈락순서·최종생존자 전부 동일,
         다른 것은 한 테이블-핸드의 확률 0.284 → 0.283 하나뿐.
```

계산 일관성 수정 (`claude/fix-calc-nks1k7` 브랜치).

```
1-C  refresh 의 outs 를 make_plan 과 같은 체감값으로
     (plan.py:1661). **지문을 깨지 않았다** — 1dd5d83f… 유지.
     안 깨진 이유: outs 소비처가 전부 게이트(8 또는 6)인데,
     6시드×30핸드에서 턴·리버에 semibluff/bluff_2street/river_bluff
     계획이 0건이라 그 게이트를 탄 상황이 없었다.
     영향이 없다는 뜻이 아니다 — tools/cf_refresh.py 에서 outs 축
     뒤집힘이 1.7% → 2.6% 로 오르고 전환이 semibluff → giveup 으로 바뀐다.
   ↓
1-A  need_true 팟오즈 분모에 내 콜을 더한다 (plan.py:616).
     **지문이 바뀐다** — 1dd5d83f… → 44da00bf…, 6시드 전부.
     tocall/(pot_live + tocall). 예전 식은 필요승률을 (1+2sz)/(1+sz) 배
     부풀렸다. 뒤집힘 69건이 전부 한 방향(fold→call 65, call→raise 4).
     _sz_seen 덮어쓰기(FIX_PLAN 2-A)가 80~89% 를 가리고 있어 전체 대비
     2.5% 로 보이지만, 덮어쓰기가 안 걸린 자리만 보면 12.8% 다.
     부작용: sizing_tell 의 플랍 영향이 21.2% → 14.8%. 리딩 조정의
     하한 need_true*0.55 가 need_true 에 비례해 같이 좁아진다.
     하한 계수는 건드리지 않았다 (FIX_PLAN 1-A 참조).

   ↓
2-A  _sz_seen 이 need 를 통째로 재대입하던 구조를 없앤다 (plan.py:609-633).
     인지 사이즈를 need_true 의 **입력**으로 올리고, 재대입 네 줄을 삭제.
     **지문이 바뀐다** — 44da00bf… → d8e9271e…, 6시드 중 5개.
     비발동군(_sz_seen == _sz_true)은 **비트까지 동일**해서 변화 0/200.
     발동군 행동 변화 flop 17.1% / turn 12.1% / river 7.9%.
     살아난 것: potodds 1.8% → 11.0%, aggression 6.5% → 13.2%,
       looseness 1.2% → 5.5%, discipline 1.0% → 3.8% (플랍 기준)
     줄어든 것: sizing_tell 14.8% → 2.2%, range_read(리버) 40.5% → 29.8%.
       둘 다 need 재대입 레버를 타고 있었다 — 레버가 없어졌다.
     계수는 하나도 안 건드렸다. size_river 게이트 우회도 그대로 남아 있다.
     근거: FIX_PLAN.md 2-A / TRACE_SZSEEN.md / TRACE_STELL.md
```

**현재 baseline 지문 (2-A 적용)**

```
python3 tools/fingerprint.py --seeds 3000-3005 --hands 30   # 격리 폴더에서
d8e9271ec730c01d80c801550bf0e5b50fabc5fa3533ea3f43200046afb832cc
```

1-A 시점 지문은 `44da00bf…` 였다. `tools/cf_szseen.py` 가 그 시점 코드를
`git show 6574360:plan.py` 로 복원해 비교하므로 BASE_REV 를 바꾸지 말 것.

`f7e03ac` / `a247f7f` 를 새 실험의 비교군으로 쓰지 마라. 특히 prefetch 같은
성능 최적화의 의미 보존 검증은 **같은 baseline 의 ON/OFF 로만** 비교한다.

---

## 계층 구조

| 대장 | 모듈 | 상태 |
|---|---|---|
| 1. 봇 생성 | persona.py(1029), archetypes, field | 분포 미검증 |
| 2. 토너 진행 | tourney, fieldsim, live2, formats | 작동 |
| 3. 한 핸드 | session.py(802), runner.py(200) | 작동 |
| 4. 봇 판단 | **plan.py(2039)**, preflop.py(716), bot.py | 조사 중 |
| 5. 정산 | runner, session | 작동 |
| 6. 관찰과 기억 | reads.py(611), dynamics, context | 작동 |
| 7. 리뷰 | audit.py | 거의 없음 |

---

## 현재 조사 — `make_plan` 의 계획 라벨 생성

### 핵심 구조 문제

`eq`는 **all-in equity**(리버까지 돌린 승률)이고 `rel`은 **현재 보드만**
평가한 값이다. 그런데 같은 분기 안에서 둘이 반대 방향으로 쓰인다.

```
진입 심사   eq  (미래 포함)  →  "충분히 강하다"  →  밸류 사다리로 올림
내부 심사   rel (현재만)     →  "완전히 약하다"  →  giveup
```

드로우 핸드일수록 이 모순이 커진다. 대표 사례:

```
h18  flop  eq .586  eq_current .000  delta +.586  outs 20  rel .02  → giveup
```

현재 승률 0%, 아웃츠 20개. 승률 전부가 드로우 지분인데 포기.

### 확정된 것 (1,000핸드 봇 대전 실측)

**402줄 폴백** `plan = 'showdown' if made >= 1 else 'giveup'`
- 발동 22건(전체의 1.8%). giveup 의 7%에 불과 — 주범이 아니다
- 진입 조건이 `eq >= pcz`(0.50+)라 최종 `has_sd`(`eq >= 0.42`)가 **항상 참**.
  즉 이 자리에서 giveup 은 구조적으로 나올 수 없어야 한다
- 도입 커밋이 명시한 대상("rel 0에 made 0인 완전 미스")은 애초에
  `eq >= pcz`를 통과 못 해 여기 도달하지 못한다. **의도한 대상이 한 건도 없다**
- 실제로 걸린 것: rel 0.5~0.7(현재 이기고 있음) 14건, 드로우 5건

**세미블러프 선점** — `eq >= pcz`가 semibluff 분기보다 위에 있다
- 같은 드로우 조건(`outs>=8`, 뒤 액션자 ≤1)에서
  `eq < pcz` → semibluff 44% / `eq >= pcz` → semibluff 3%
- **승률이 오르면 세미블러프 자격을 잃는다.** 논리적으로 뒤집혔다
- 선점된 자리를 `value_2street`(27%)·`value_3street`(30%)가 차지.
  `made == 0`인 하이카드가 밸류 계획을 받는다

**최종 has_sd 블록** `has_sd = made >= 1 or eq >= 0.42 + 0.05*mw`
- giveup 270건 중 90% 생성. 그중 82%(222건)는 eq 중앙 0.165로 **정상**
- `outs`를 전혀 읽지 않는다. 드로우는 `eq`가 0.42를 넘어야만 살아남는다
- 의심 48건을 태깅한 결과 세 부류로 갈림:

| 집단 | n | 성격 | 판정 |
|---|---|---|---|
| A∩B | 14 | 플랍 직접 드로우 (오픈엔드 4, 검샷 9, 플드 1) | **오류 확정** |
| A only | 16 | 턴 검샷 (리버 1장, 8.7%) | 오류 아님 |
| B only | 18 | 백도어+오버카드, 직접 아웃츠 0 | 행동 영향 없음 |

### `eq_delta` 에 대한 결론

`eq_delta = eq - eq_current`. 미래 카드 전개가 만드는 승률 변화량.

**신호는 실물이다:**
- 몬테카를로 단건 오차 ±0.05, 집단 차이 0.123, t=5.10
- 표준 35% 레인지로 전부 재계산해도 차이 유지(0.120 → 0.123).
  레인지 추정 artifact 로는 설명되지 않는다
- `outs`가 원리적으로 못 보는 것을 본다 — 두 장이 필요한 개선(백도어)은
  `draw_strength`가 0으로 센다

**그러나 행동을 바꾸지 않는다:**
- 계획: delta 높은 집단이 오히려 레인지 열세가 심하고(-0.31 vs -0.19)
  OOP 비율이 높다(72% vs 59%). 공격 조건이 아니다
- 응답: 33건 중 85%가 상대 벳에 직면조차 하지 않는다(그냥 체크로 끝남).
  직면한 5건도 승률이 필요치에 7~12%p 모자라고 SPR 3.5짜리도 있다

**결론: `eq_delta`는 기록 전용으로 둔다.** 판단 변수로 승격하지 않는다.
현재 코드의 "판단에는 절대 쓰지 않는다" 주석이 옳았다.

### 계측 설계의 알려진 결함

`eq`와 `eq_current`는 **독립된 난수 스트림**에서 나온다.

```
eq          equity_vs_combos(...)  seed 안 넘김 → 내용에서 crc32 유도
                                   sims = 400 또는 720 (레인지 20콤보 미만이면 1.8배)
eq_current  seed=seed 넘김        → make_plan 의 seed 그대로, sims = 400 고정
```

`_eq_current`의 docstring 이 "유일한 차이는 남은 보드를 뽑지 않는다는 것
하나뿐"이라고 주장하는데 사실이 아니다. 다만 실측 결과 페어드로 바꿔도
단건 sd 가 0.025 → 0.023 으로 거의 안 변해서 결론은 뒤집히지 않았다.

### 아직 안 본 것

1. **A∩B 14건 calibration** — 세미블러프 확률이 `0.25 + 0.24 × 개념`이라
   드로우 강도가 전혀 안 들어간다. 오픈엔드 13아웃과 최소 8아웃이 같은
   확률로 굴려진다. "사고 수준(개념)"과 "상황의 객관적 강도(드로우)"가
   같은 축에 섞여 있다
2. **h69 응답 산수** — `eq .338 ≥ 필요승률 .311`인데 폴드했다.
   giveup 계획은 `decide_response:719` 조기 return 으로 순수 팟오즈
   산수 경로를 타는데, 그 산수조차 맞지 않았다. 표본 1건
3. **rel 0.6대가 402줄까지 내려오는 이유** — `value_2street` 조건
   `rel >= max(0.28, ...)`을 왜 통과 못 했는지

---

## 후속 조사 대상 (지금 건드리지 않는다)

- **틸트가 거의 작동하지 않는다.** entries 100 / 30핸드에서 감쇠 호출
  32,292건 중 `level > 0` 인 것은 **271건(0.84%)** 뿐이다.
  `tools/verify_decay_profile.py` 의 `calls_active` 로 잰다.
  틸트 강도·`DECAY_BASE`·회복 계수·`level` 반올림은 **지금 수정하지 않는다.**
  calibration 을 건드리면 baseline 지문이 깨진다.
- **25% 생존 지점이 빨라졌을 가능성.** `f7e03ac` → `a247f7f` 10시드 페어
  대조에서 75/50/25/ITM 네 지점의 부호가 전부 음수(새 엔진이 빠름)였고,
  25% 지점만 유의했다(핸드 t −3.77, 레벨 t −5.01). 50%·ITM 은 노이즈 범위,
  ITM 평균스택 28.7bb → 31.3bb (t +1.33). 30시드 확인은 보류한다 —
  고친 것이 전략 파라미터가 아니라 state ownership 이라 calibration 문제로
  볼 근거가 아직 없다.

---

## 기타 확인된 이슈 (수정 안 함, 기록만)

- `session.py:475` `oop = (h.POST.index(h.pos[s]) < 3)` — 절대 포지션이라
  CO vs BTN 헤즈업에서 CO 가 OOP 인데 false
- `view.py:32,45` 레이즈 상한 표시 — `st`(남은 스택)를 상한으로 찍는데
  amount 는 raise-to. 실제 상한은 `st + inv[hero]`
- `live2.py:12` `_SUFFIX` — `T2_LIVE_STATE` 존재 여부만 보고 `_alt` 고정.
  경로가 달라도 아카이브는 모듈 폴더를 공유한다. 서버를 붙이려면
  별도 폴더에서 실행할 것
- 히어로 탈락 후 `step()` 호출 시 `'NoneType' object has no attribute 'alive'`
  로 크래시. 깔끔한 종료 메시지가 없다
- ~~`refresh`의 outs 는 `draw_strength` 날것~~ → **고쳤다**
  (`claude/fix-calc-nks1k7`, FIX_PLAN.md 1-C). `perceived_rel` 에는
  여전히 날것을 넘긴다 — `make_plan:312-314` 와 같게 유지하기 위해서다
- `audit.py:171` 이 설계상 허용된 이탈까지 전부 "포기계획인데 벳" 경보
- `persona.py:755` `size_read` 는 2.0팟 이하에서 항등이다. 아카이브 648건에서
  포스트플랍 sz 최대 0.915 — **한 번도 동작한 적이 없다.** `sizing_tell` 이
  실제로 닿는 곳은 `see_size → size_gap → opp_size_norm` 이다 (`TRACE_STELL.md`).
  **죽은 축이 아니라 도달 불가능한 축이다** — 정의역 밖(2.5~9팟)에서는 오차가
  2.000 → 0.000 으로 정확히 작동한다 (`TRACE_AXIS_ACC.md`)
- `ranges.blocker_score` 를 잴 때 상대 레인지를 `hero+board` dead 로 만들면
  **구조적으로 항상 0** 이다. 엔진은 dead 가 `set(board)` 뿐이다(`session.py:370`).
  이걸로 "blocker 가 죽었다"는 잘못된 결론을 한 번 냈다. 도구 만들 때 주의
- `persona.open_pct` 에는 축이 셋 섞여 있다 — `pf_range`(폭)·`positional`(곡선)·
  `_G.adapt_mult`. 하나를 재려면 나머지를 9 로 고정해야 한다
- `plan.py:398` `make_plan` 안의 `sk()` 는 **0~3 스케일**이다 (`PS.sk/3.33`).
  `sk('potcontrol') >= 1` 은 실제로 PS.sk ≥ **3.33** 이다. 실측 게이트가
  3.3→3.4 사이에서 열린다 (`bluff`·`potcontrol` 3.33, `semibluff` 1.33)
- **`potcontrol` 은 빈도 축이 아니라 스위치다.** 게이트 위에서 기울기가 0
  (PS.sk 3.4~9 전부 `pot_control` 14.4%). 확률식 `_pc_p` 에 축이 안 들어간다
- **`persona.call_bias` 의 `max(0.0, bias(...))` 가 축의 절반을 차단한다.**
  `looseness` 는 날것이 −0.36→+0.36 로 완전 선형인데 clamp 후 하위 절반이 0,
  `discipline` 은 상위 절반이 0. 빈도만 보면 '무반응'으로 오독한다 —
  **중간값(날것/clamp 후)을 반드시 같이 기록할 것** (`TRACE_AXIS_FREQ.md`)
- **`overbet` 은 플랍에서 아예 `return None` 이다** (`plan.py:1120`). 리버에서도
  게이트가 곱으로 셋이라 실현 발동이 102건 중 2건 — **실현 빈도가 아니라 발동
  확률로 재야 한다.** 병목은 `nut_advantage`(중앙 0.005, 50%가 ≤0)이지
  양극화가 아니다 (`TRACE_AXIS_FREQ.md` 4단계)
- **`equity_denial` 은 두 번 희석된다.** `plan.py:1009` 의 배수 뒤에
  `plan.py:1030` 의 45/55 텍스처 블렌드가 와서 명목 +7.5% 가 +0.8% 로 깎이고,
  `plan.py:1317` 의 100칩 반올림이 11.0%p 를 더 지운다. 실제 칩 금액이
  달라지는 것은 26.2% 뿐이라 중앙값으로는 안 보인다
- **`probe`·`delayed_cbet` 은 단일 스트리트 harness 로 잴 수 없다.**
  `plan_state` 의 `opp_checked_prev`·`flop_checked` 라인 이력을 요구한다.
  전 레벨 동일하게 나오는 것은 축이 죽어서가 아니라 조건이 성립한 적이 없어서다
- **계획 층도 집계 %가 아니라 전환 수를 세야 한다.** `stackoff` 에서 집계표는
  전 레벨 동일인데 상황별로는 뒤집힘이 있었다 — 양방향 건수가 맞으면 표가
  안 움직인다
- **`river_bluff` 0건은 버그가 아니다 — 기대 빈도가 0.45건이다.**
  `tools/river_trace.py` 로 파이프라인을 계측하니(300핸드) 리버 판정 82건 중
  `river_fix` 가 `semibluff` 를 받은 것이 **1회**, 그것도 드로우가 완성돼
  `value_2street` 로 갔다. `p_bluff` 굴림에 도달한 적이 0회다.
  필드 중앙값으로 `p_bluff = 0.10 + 0.55×0.50×0.41 = 0.212`, 아카이브 리버
  intent 351건 기준 기대 **0.45건**. Poisson λ=0.45 에서 P(0)=0.64 다.
  **"975핸드 0건"을 구조적 신호로 읽은 것이 처음부터 잘못이었다** —
  이 항목에서 세 번 틀렸다(`TRACE_BLUFF.md` 1절에 과정을 남겼다)
- **`river_fix` 는 `street` 를 인자로 받지 않는다.** `plan.py:1529` 의
  `if len(board) < 5: return state` 로 스스로 막는다. 그래서 플랍·턴에서도
  호출되고 즉시 반환한다 — 호출 횟수를 셀 때 **보드 길이로 갈라야 한다.**
  no-op 4회를 진입으로 세서 "5회 받았다"는 틀린 숫자를 냈다
- **`SIZING` 에서 리버에 벳 사이즈가 있는 블러프 계획은 `river_bluff`(0.72)
  하나뿐이다** (`semibluff`·`bluff_2street`·`giveup` 의 river 는 전부 0.0).
  그래서 리버 `bluff_2street` 계획 12건은 전부 check/fold 였다 — 칠 수단이 없다.
  설계이지만, 리버 블러프 공급이 기대 0.45건짜리 한 경로에만 걸려 있다
- **아카이브 파일들은 서로 겹친다.** `review_*.jsonl` 과 `bak_*` 를 함께
  읽으면 같은 핸드가 여러 번 세어진다. `(hand_no, seat, board)` 로 중복을
  제거할 것 — 안 하면 9건이 실제로는 6건이다
- **블러프 품질을 잴 때 밸류 벳을 대조군으로 두지 않으면 임계값 artifact 가
  나온다.** `blocker_net <= 0` 같은 컷은 그 값의 중앙이 0 근처라 절반이
  자동으로 걸린다. 실제로 '블로커 무의미 72%' 를 만들 뻔했는데 밸류 벳도
  −0.000 이었다. 그리고 강도 백분위를 `made_strength` 버킷으로 재면
  `made == 0` 일 때 0 으로 고정된다 — `eval7` 연속값을 쓸 것
- **`bluff_fear` 와 `hero_call` 은 거의 완전한 거울상이다.** 둘 다 `persona.bias`
  파생값이고 `bluffcatch_river`·`aggression` 을 **반대 부호로** 공유한다
  (bcr 1→9 에서 0.554→−0.086 vs −0.559→0.161). 독립적으로 흔들 수 없다 —
  축이 아니라 중간값으로 다룰 것
- **`potodds` 는 `station` 과 고정으로 분리할 수 없다.** `station` 식이
  `potodds` 를 −0.30 가중으로 직접 읽는다. 그래서 `potodds` 를 흔들면 `station`
  이 필연적으로 움직인다. 실측에서 폴드율이 ∩ 모양으로 나오는 원인 중 하나다
  (체감 need 는 중앙·분산 둘 다 단조 감소인데 행동은 ∩)
- `bluffcatch_early` 는 플랍·턴, `bluffcatch_river` 는 리버 축이다. **그 스트리트
  에서 재야 한다** — 리버 축을 플랍에서 재서 ◐ 로 잘못 볼 뻔했다.
  그리고 `decide_response:827-832` 의 계수가 비대칭이다: `bluff_fear` 0.30(하위
  절반) vs `hero_call` 0.18(상위 절반). `bluffcatch_river` 는 아래쪽으로만
  실질 작동한다 (`TRACE_AXIS_FREQ.md` 3단계)
- `preflop.defend_thresholds` 는 `(tp, tot)` 를 낸다. `aggression` 은 `tp`
  (3벳 구간)에만, `looseness` 는 `tot`(참가 구간)에만 걸린다. 하나만 보면
  다른 축이 무반응으로 보인다
- `act_with_plan` 은 **무저항에서 판단하지 않는다**(`plan.py:1315`). 의도는
  `attach_intent`(→`decide_aggression`)가 붙인다. 도구에서 `make_plan` 만
  부르고 `act_with_plan` 을 호출하면 `intent` 가 None 이라 **전부 체크**가 된다
- `persona.py:955` `size_river` 만 `see_size` 게이트가 빠져 있다. 리버에서는
  사이즈를 못 읽는 사람도 `_sz_norm` 이 어긋난다. 2-A 로 덮어쓰기가 없어져
  피해는 줄었지만 게이트 누락 자체는 그대로다
- `calldown_need` 의 `trust` 블록은 `dev` 를 **실제 사이즈**(`_sz_true`)로 잰다.
  2-A 로 팟오즈는 인지 사이즈를 쓰게 됐는데 이쪽은 아직 실제 사이즈다.
  같이 바꾸면 2-A 효과와 섞이므로 이번에는 두었다

---

## 도구

전부 읽기 전용 분석용. `plan.py` 를 수정하지 않는다.

| 파일 | 용도 |
|---|---|
| `tools/review.py` | 토너 한 판 되짚기. `--list` / `--hand N` / `--flags` / `--sizes` / `--pid N` |
| `tools/collect.py` | 히어로 없이 봇끼리 돌려 intent 수집. `python3 tools/collect.py 250 out.jsonl` |
| `tools/cf_B.py` | 402줄에서 아래 체인으로 흘려보냈을 때의 반사실 |
| `tools/cf_hassd.py` | 최종 has_sd 블록 해부 + 4분할 |
| `tools/tag_draws.py` | 홀카드+보드로 드로우 유형 태깅 |
| `tools/delta_var.py` | eq_delta 의 몬테카를로 분산 측정 |
| `tools/implied.py` | full_log 로 팟·콜비용 재구성, 가격 분석 |
| `tools/cf_potodds.py` | 팟오즈 식 수정(FIX_PLAN 1-A)의 행동 영향 |
| `tools/cf_szseen.py` | `_sz_seen` 덮어쓰기(FIX_PLAN 2-A) 3변종 분해 |
| `tools/cf_stell.py` | `sizing_tell` 해부 (방향·크기·2×2 충돌) |
| `tools/axis_accuracy.py` | 인식 정확도 축의 호출 지점 오차 (축 1/3/5/7/9) |
| `tools/axis_sites.py` | 성향 축 사용처 전수 (별칭·지역 lambda·street_concept 포함) |
| `tools/axis_freq.py` | 빈도 축의 **층별** 변화. 교락 축 고정, 중간값 같이 기록 |
| `tools/bluff_coherence.py` | 블러프 라인·레인지 일관성. 밸류 벳이 대조군 |
| `tools/river_trace.py` | 리버 파이프라인 계측. 반환 state 의 plan 으로 판정 |
| `tools/ctx_bonly.py` | 행동 맥락(포지션·SPR·레인지우위) 비교 |
| `tools/wirecheck.py` | 개념 배선 검사 (36/36 나와야 정상) |
| `tools/fingerprint.py` | 행동 지문. 레시피가 docstring 에 박혀 있다 |
| `tools/verify_tilt_isolation.py` | 틸트 pid 격리 (single/repeat/leak/struct) |
| `tools/verify_tilt_divergence.py` | 엔진 두 벌의 divergence·필드 페이스 대조 |
| `tools/verify_decay_profile.py` | 감쇠가 자기 프로필을 쓰는지 (객체 동일성) |
| `tools/verify_defer.py` | prefetch 의미 보존 (off/inline/worker/http) |
| `cli.py` | 히어로 직접 플레이. `python3 cli.py` |

수집 시 주의: 명령 하나가 300초를 넘으면 안 되는 환경이었다면
250핸드씩 끊어 돌리고 합쳤다. 제한이 없는 환경에서는 한 번에 돌려도 된다.

데이터 파일(`collected*.jsonl`)은 용량이 커서 저장소에 넣지 않았다.
필요하면 `tools/collect.py`로 다시 만든다.

---

## 시뮬레이션 운영 규칙 (히어로 플레이 시)

- 액션이 있을 때만 진행. "액션?"으로 끝내면 거기서 종료
- 폴드로 끝난 핸드는 상대 패 비공개. 쇼다운 도달 핸드만 공개
- 필요 승률·팟오즈 표시 금지. 팟 금액과 콜 비용만
- 핸드 진행 중 코칭·힌트 금지
- 핸드 종료 시 확인 없이 바로 다음 핸드 딜
- `ㅍ`/`ㅍㄷ` 폴드, `ㅋ` 콜, `ㅊㅋ` 체크, 숫자는 raise-to, `ㅇ` 올인

## 응답 스타일

- 한국어 존댓말
- 물어본 것만. 부연 설명 없이 간결하게
- 시각 자료는 PNG 파일로. ASCII 도식과 SVG 는 쓰지 않는다
- 계산 결과가 예상과 다르면 끼워맞추지 말고 다르다고 말할 것
- 수식은 나눗셈 기호 대신 분수 형태로, 첨자는 실제 아래/위첨자로
