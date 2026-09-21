# 전수조사 장부 — 개념·결함·처리 상태

기준 `7910412` + 이 브랜치의 수정 커밋들. 읽기 전용 조사 → 동적 재현 →
확정된 것만 수정 → 나머지는 분류해서 남긴다.

## 분류와 상태

| 분류 | 뜻 |
|---|---|
| A | 실제 독립 개념인데 문서/구조도에 없다 |
| B | 의도된 중복·호환 계층 |
| C | 불필요한 중복 가능성 |
| D | dead / obsolete 후보 |
| E | 실제 충돌·버그 (입력→출력 차이 재현됨) |
| F | 판단 보류 — 동적 검증이 더 필요하다 |

상태는 여섯 중 하나만 쓴다.
`FIXED` · `VERIFIED_KEEP` · `DOCUMENT` · `CLEANUP_LATER` · `EXPERIMENT_LATER` · `UNRESOLVED`

**"이상해 보인다 = 삭제" 로 처리하지 않는다.** 재현되지 않은 의심은 E 로
올리지 않고 F 로 내린다. 실제로 이 조사에서 E 후보 5건 중 3건이 강등됐다.

---

## 1. A — 구현돼 있으나 문서화되지 않은 개념

### A-1  style belief 미배선층
- **파일:라인** `reads.py:493 style_hypotheses` · `513 prior_spread` · `521 concept_belief` · `538 style_certainty` · `548 opponent_belief`
- **현재 역할** 상대 추정의 **두 번째 갈래**. 행동빈도 → "TAG 같다" 스타일 가설 분포 → 그 스타일의 개념 prior. 직접 경로(`estimate_concepts`)와 확신도로 가중해 결합하도록 설계돼 있다. 캘리브레이션 파일 `style_sig.json` · `style_prior.json` 이 실재한다
- **production 도달** 없음 (호출 0). `tools/` 에서만 `opponent_belief` 6회, `concept_belief` 9회
- **행동 영향** 없음
- **동적 검증** 해당 없음 (호출 자체가 0)
- **상태** `DOCUMENT`
- **다음 조치** 배선 여부는 설계 결정이다. 배선하려면 별도 사전등록 실험이 필요하다. 삭제 대상 아님

### A-2  money pressure 서브시스템
- **파일:라인** `money_pressure.py` 전체 · 생산 `session.py:37 _money_jump_observe` · 소비 `session.py:489 PL.preflop_plan(money_open=…)` → `preflop.py:305 thr *= range_factor`
- **현재 역할** 상금 점프 압력을 관측해 **프리플랍 오픈 레인지 폭**만 조정한다(LIVE). limp·sizing 은 SHADOW(기록만)
- **production 도달** 있음 — 프리플랍 한정
- **행동 영향** 있음 — 프리플랍 레인지 폭. **포스트플랍은 영향 0**: `session.py:769` 의 `_mj_obs` 는 생성 후 `_money_jump_attach_action` 으로 기록만 되고 어떤 plan/act 인자로도 들어가지 않는다
- **동적 검증** Phase C 40시드 2,046행 (`MONEY_SIZING_9MAX_RESULT.md`, INCONCLUSIVE)
- **상태** `VERIFIED_KEEP`
- **다음 조치** 계층표에 행을 추가한다. SHADOW→LIVE 승격은 별건

### A-3  드라이버 4종 / 필드 모델 2종
- **파일:라인** `fieldsim.py:234 _play_table` · `tourney.py:105 next_hand` · `live2.py:307 step` · `live.py:131 step` / 필드 모델 `field.py:57 Field`(확률적 탈락곡선) vs `fieldsim.py:48 Field`(명시적 다테이블)
- **현재 역할** 넷 다 `play.Hand` + `session.HandRun` 으로 수렴하지만 필드 모델이 둘로 갈린다. `tourney` 는 `field.Field` + `field.Tables` + `table.Table`, `fieldsim` 은 자체 `Field`/`Table`(`max_seat` 검증 포함)
- **production 도달** `fieldsim`·`tourney`·`live2` 있음. `live.py` 는 루트에서 import 0
- **행동 영향** 있음 (드라이버가 핸드 구성·필드 상태를 정한다)
- **동적 검증** 두 경로 모두 실행해 `make_plan` 분기 계측 (1,190회 전부 concepts 경로)
- **상태** `DOCUMENT`
- **다음 조치** 같은 이름 `Field`/`Table` 이 다른 개념임을 구조도에 명시. `live.py` 는 D-3 참조

### A-4  intents 판단 스냅샷
- **파일:라인** `session.py:786` · `964`
- **현재 역할** 매 액션 전 그 시점에 **무엇을 봤는가**를 남긴다 — plan·why·rel·eq·outs·made·eq_current·eq_delta·eq_sims·eq_seed·bf·tilt·포지션·n_opp·behind
- **production 도달** 있음 (기록 전용)
- **행동 영향** 없음
- **동적 검증** 해당 없음
- **상태** `VERIFIED_KEEP`
- **다음 조치** 역추론 연구의 1차 자료다. 계층표에 "관측·기록" 층으로 올린다. 키 스키마는 F-6 참조

### A-5  ui 서브시스템
- **파일:라인** `ui/server/ui_server.py`(720) · `ui/server/ui_view.py`(125) · `ui/web/app.js`(3,763) · `ui/tools/verify_ui.py`(369) — 합 5,112줄
- **현재 역할** 히어로 플레이·리뷰 표시 계층
- **production 도달** 엔진과 분리된 표시 계층 (엔진이 import 하지 않는다)
- **행동 영향** 없음
- **동적 검증** 안 함
- **상태** `DOCUMENT`
- **다음 조치** 계층표에 행 추가. 브랜치 이름이 `ui-v49` 인데 `CLAUDE.md` 에 한 줄도 없다

---

## 2. 확정·수정 완료

### FX-1  audit 8-max 사다리 → 핸드별 도출
- **분류** E → **FIXED** (`72ac16c`)
- **파일:라인** `audit.py:8-40 orders_for_labels` · `147-158`
- **현재 역할** 스트리트 액션 순서 검사. 그 핸드의 포지션 집합으로 사다리를 도출한다
- **production 도달** 리뷰 계층 (엔진 import 0)
- **행동 영향** 없음 (엔진 지문 무영향). 리뷰 출력에는 영향 있음
- **동적 검증** 9인 실제 핸드에서 거짓 "순서" 경보 재현 → 수정 후 소멸. 아카이브 1,037건(현대 957 / 구 80) 결과 완전 보존. `tools/verify_audit_order.py` D1~D6
- **다음 조치** 없음

### FX-2  포스트플랍 포지션 semantics
- **분류** E → **FIXED** (`0d202c5`)
- **파일:라인** 정의 `session.py:12 oop_field` · `28 oop_vs` / 계산 `session.py:659-668` / 소비 `plan.py:449-450`(blockbet) · `917-919`(donk) · `1211,1214`(cbet_freq) · `session.py:834`(line_bluff_prior)
- **현재 역할** 절대 슬롯(`POST.index < 3`)을 셋으로 분리 — `oop_field`(뒤에 행동 가능자 존재) / `oop_vs_aggr`(어그레서 대비 선행) / `aggressor_pos_oop`(어그레서가 나보다 선행)
- **production 도달** 있음
- **행동 영향** 있음. 수정 전 비트 오염률 124/771(16.1%), 행동 변화는 8/771 중 교집합 1건
- **동적 검증** 쌍 비교 3시드×20핸드: 핸드-테이블 665 중 21 divergence, **시드별 최초 divergence 3건 전부 귀속됨(설명 불가 0)**, 나머지는 최초 이후 전파. regress 6시드 중 2시드 지문 변경(3003·3004). 새 지문 `4f3a37bf…`
- **다음 조치** 없음. 어그레서 없는 팟은 F-1 로 격리

### FX-3  죽은 `act_with_plan(oop=)` 제거
- **분류** D → **FIXED** (`7d084bd`)
- **파일:라인** `plan.py:1248` + 호출자 11곳
- **현재 역할** 없어졌다. 인자를 받기만 하고 본문 참조가 0이었다(AST 확인)
- **production 도달** 있었음
- **행동 영향** 없음
- **동적 검증** `regress.py check` 전 시드 지문 일치. 격리 지문 `26b373a9…` 유지
- **다음 조치** 없음

### FX-4  OOP verifier / 계약 테스트
- **분류** — → **FIXED** (`95624b0`, `72969a4`, `3e27b44`)
- **파일:라인** `tools/verify_oop_semantics.py` · `tools/verify_replan_contract.py`
- **현재 역할** A1~A15(술어·불가액션 좌석·죽은 어그레서) / C1~C2(불변식) / B1~B2(행동 도달) / C3(난수 특성화) / 재계획 입력 계약 고정
- **production 도달** 없음 (검증 도구)
- **행동 영향** 없음
- **동적 검증** 전부 PASS
- **다음 조치** 난수 소비 계측은 **위임 프록시만** 쓴다. `random.Random` 서브클래스로 `random()` 을 덮으면 CPython 이 `_randbelow` 를 바꿔 `choice()` 결과가 달라진다 — 실제로 없는 divergence 1건이 만들어졌다

---

## 3. E — 재현된 버그 (미수정)

### E-1  `revise_plan` 이 `bb_chips` 를 넘기지 않는다
- **분류** E
- **개념명** 보드변화 재계획의 상대 유효스택 인식
- **파일:라인** `runner.py:150-153` (누락) → `plan.py:327-328 _opp_eff` → `target_commit(opp_eff=…)`
- **현재 역할** `_opp_eff = opp_stack_bb × bb_chips / stack`. `bb_chips` 가 없으면 `_opp_eff` 가 `None` 이 되어 커밋 목표가 상대 스택을 못 본다
- **production 도달** 있음 — 턴·리버 재계획 810건
- **행동 영향** **있음** — 810건 중 2건(0.25%)에서 사이즈 변화
- **동적 검증** 5팔 반사실. `CF-bb` 단독으로 2건 재현. 최소 사례 `standard seed4242 h14 t5 river LJ: value_3street bet 0.892 → 0.885` (RNG 소비 동일 2827→2827)
- **상태** `UNRESOLVED`
- **다음 조치** 구조정리 때 다섯 인자를 **한 번에** 넘기고 `runner.py:148` 의 틀린 주석도 같이 고친다. 고치면 `tools/verify_replan_contract.py` 의 `KNOWN_MISSING` 을 줄여야 한다

---

## 4. F — 판단 보류

### F-1  어그레서 없는 팟의 blockbet / donk semantics
- **개념명** 선제 억제의 기준 대상
- **파일:라인** `plan.py:446-450` · `915-919` (TODO/F 주석 있음)
- **현재 역할** 어그레서가 없으면 옛 절대식을 legacy 경로로만 써서 기존 행동을 보존한다. `oop_vs_aggr` 에는 절대 legacy 값을 넣지 않는다
- **production 도달** 있음 — 전체 결정의 33.1% (926/2,800)
- **행동 영향** 3팔 차이 A vs B = **926건 중 1건**
- **동적 검증** OLD/A/B 3팔 + 게이트 진입 계측. A 에서 442 게이트 33회·904 억제 9회 통과, B 에서 0회. 그러나 `block` 계획 채택은 **세 팔 모두 0건**
- **상태** `EXPERIMENT_LATER`
- **다음 조치** 개념 논증은 B(어그레서 없으면 미적용) 쪽이다 — `plan.py:921-924` 가 스스로 "**프로브는 동크가 아니다**"라고 예외를 단다. 그러나 표본 1건으로 확정하지 않는다. F-2 가 먼저 풀려야 442 쪽을 관측할 수 있다

### F-2  `blockbet` 실현 0 / 2,800
- **개념명** 블락벳 계획의 실현 가능성
- **파일:라인** `plan.py:451-456` (`sk('blockbet') >= 1 and rng.random() < block_p`)
- **현재 역할** 게이트 통과 뒤 개념 문턱과 확률 굴림을 더 통과해야 `plan='block'` 이 된다
- **production 도달** 게이트는 열린다 (A팔 33회)
- **행동 영향** **실현 0건** — 2,800 결정에서 `block` 계획이 한 번도 채택되지 않았다
- **동적 검증** 3팔 반사실에서 세 팔 모두 0
- **상태** `EXPERIMENT_LATER`
- **다음 조치** `sk()` 가 0~3 스케일이라 `>= 1` 은 `PS.sk >= 3.33` 이다. `block_p` 상한은 0.42. 최소 프로필로 한 번이라도 실현 가능한지부터 확인한다. **이번 단계에서는 하지 않는다**

### F-3  `revise_plan` 의 `oop_vs_aggr` / `oop_legacy_abs` / `initiative` 누락
- **개념명** 재계획 시점의 포지션·공격권
- **파일:라인** `runner.py:150-153`
- **현재 역할** 기본값으로 떨어진다 — `oop_vs_aggr=None`, `oop_legacy_abs=None`, `initiative=True`
- **production 도달** 있음 — 810건
- **행동 영향** **없음 (0/810)**. `initiative=True` 기본값이 `not initiative` 를 막아 442 게이트가 어차피 닫힌다. 포지션만 고쳐도 0, initiative 만 고쳐도 0
- **동적 검증** CF-pos 0/810, CF-init 0/810. 실제 값과 기본값은 다르다 — `oop_field` 478/810(59.0%), `oop_vs_aggr` 315/810(38.9%)
- **상태** `UNRESOLVED`
- **다음 조치** E-1 과 함께 고친다. 단독으로는 행동이 안 바뀌므로 E 로 올리지 않는다

### F-4  `revise_plan` 의 `tilt` 누락
- **개념명** 재계획 시점의 틸트
- **파일:라인** `runner.py:148` 주석 vs `150-153` 코드 · 소비 `plan.py:411 trap_judgment(…, tilt, …)`
- **현재 역할** 주석은 *"상대 추정치·**틸트**를 그대로 넘긴다"* 라고 적혀 있으나 실제로 넘기는 것은 `opp_est`·`opp_stack_bb` 뿐이다. `tilt` 는 기본값 0.0
- **production 도달** 있음 — 810건
- **행동 영향** **없음 (0/810)**
- **동적 검증** CF-tilt 0/810. 틸트 `level > 0` 자체가 0.84% 라 표본에서 효과가 관측되지 않는다
- **상태** `UNRESOLVED`
- **다음 조치** 의미상 전달 대상이다(주석이 그렇게 약속한다). E-1 과 함께 고치고 주석을 코드에 맞춘다

### F-5  `_rsig` 프로세스 salt
- **개념명** 상대 레인지 변동 감지 서명
- **파일:라인** `plan.py:1519` `_rsig = hash(frozenset(map(str, opp_range)))`
- **현재 역할** 같은 스트리트 안에서 상대 레인지가 실제로 좁혀졌는지 판정해 `refresh` 를 다시 태운다
- **production 도달** 있음
- **행동 영향** 한 프로세스 안에서는 자기일관적이라 현재는 없다
- **동적 검증** 안 함. `live2` 는 계획을 직렬화하지 않고 `decisions` 재생으로 복원하므로 프로세스를 넘지 않는다
- **상태** `EXPERIMENT_LATER`
- **다음 조치** 계획 상태가 프로세스를 넘어 재사용되는 경로가 생기면 즉시 결함이 된다. `PYTHONHASHSEED` 고정 여부와 함께 확인

### F-6  `pf_seed` 의 내부 역할을 관찰자가 읽는다
- **개념명** 프리플랍 역할의 관찰 가능성
- **파일:라인** `session.py:664` 부근 (`_pfo = h.pf_seed[o]['pf_role']`)
- **현재 역할** 상대 레인지를 만들 때 상대의 프리플랍 역할(open/iso/defend)을 그 사람의 **플래너 내부 기록**에서 직접 읽는다. 주석은 "액션은 공개 정보"라고 한다
- **production 도달** 있음
- **행동 영향** 미측정
- **동적 검증** 안 함
- **상태** `EXPERIMENT_LATER`
- **다음 조치** 공개 로그만으로 `pf_role` 을 복원했을 때와 결과가 같은지 반사실로 잰다. 같으면 B, 다르면 정보 누출

### F-7  `sk` fallback 의 미래 도달 위험
- **개념명** 개념 벡터가 없는 프로필의 기본 숙련도
- **파일:라인** `plan.py:396-400` (`else: (lambda c: A.skill(T,c)) if T in A.ARCHETYPES else (lambda c: 2)`)
- **현재 역할** concepts 도 archetype 도 없으면 **모든 개념을 상수 2** 로 본다. 게이트가 `sk(...) >= 1` 형태라 **전 게이트를 무조건 통과**시킨다
- **production 도달** **없음 (0/1,190)** — fieldsim 3포맷 1,070회 + tourney 120회 전부 concepts 경로
- **행동 영향** 없음
- **동적 검증** 했음. concepts 없는 프로필 생성자는 셋뿐이고 전부 막혀 있다 — `tourney.py:74`(히어로, TAG∈ARCHETYPES 이고 `session.py:645`가 히어로를 계획 전에 yield 한다), `field.py:203 seat_newcomers`(호출 0), `live.py:29`(모듈 dead)
- **상태** `DOCUMENT`
- **다음 조치** 삭제하지 않는다. `seat_newcomers` 부활이나 비-archetype 리터럴 프로필이 생기면 **조용히** 모든 게이트가 열린다. else 분기에 경고를 붙이는 쪽이 맞다

### F-8  `revise_plan` 입력 계약 불일치 (구조적 항목)
- **개념명** 같은 함수의 두 생성 경로가 서로 다른 전제를 쓴다
- **파일:라인** `plan.py:1483-1489`(최초) vs `runner.py:150-153`(재계획)
- **현재 역할** `update_plan` 은 계획을 두 경로로 만든다. 최초는 상황 입력 10개, 재계획은 5개. 재계획은 **완전한 새 dict 생성**이고 이력 7키만 승계한다 — 부분 갱신이 아니다
- **production 도달** 있음 — 재계획 경로 2,580/4,736(54.5%), 그중 `make_plan` 도달 810(17.1%)
- **행동 영향** E-1 참조 (bb_chips 경유 2건). 나머지 넷은 F-3·F-4
- **동적 검증** `tools/verify_replan_contract.py` 가 누락 5개를 고정
- **상태** `DOCUMENT`
- **다음 조치** **이 항목은 개별 동적 판정(E-1/F-3/F-4)과 분리해 읽는다.** 개별 인자의 행동 영향과 무관하게, 완전 재생성 함수가 현재 상황 대신 기본값을 받는 것 자체가 구조 문제다

---

## 5. C / D — 중복·사문

### C-1  `icm.field_bf` 이중 정의
- **분류** C (앞 정의 자체는 D)
- **파일:라인** `icm.py:205`(사문) · `icm.py:292`(런타임 유효) · 유일 호출자 `icm.py:316`
- **현재 역할** 뒤 정의가 앞을 완전히 가린다. 호출자는 위치인자 5개를 넘기고 **뒤 정의 시그니처와 정확히 일치**한다
- **production 도달** 뒤 정의만
- **행동 영향** **없음** — 현재 경로는 정상
- **동적 검증** 했음. 앞 정의를 별도 이름으로 복원해 같은 입력 4,000건 비교: **3,818건이 다르고 최대 차이 0.768 BF**. 앞 정의의 정확-ICM 분기는 `table_bf:312` 가 `rem ≤ 9` 를 먼저 빼돌려 **도달 불가**. `git blame` 상 둘 다 `8fadcb3` 최초 커밋부터 공존. 같은 값 상수도 둘이다(`EXACT_MAX_SEATS=9` 181, `EXACT_MAX=9` 255)
- **상태** `CLEANUP_LATER`
- **다음 조치** 순서가 뒤집히면 즉시 0.77 BF 짜리 행동 변화가 된다. 정리 시 상수도 하나로

### C-2  `SIZING_SIG` / `_ObsMap` 의 dict API 불일치
- **분류** C
- **파일:라인** `runner.py:22-28 _SigMap` · `reads.py:35-46 _ObsMap`
- **현재 역할** `dict` 를 상속해 `__getitem__` 만 덮었다. 실제 dict 는 비어 있고 조회 때 값을 계산한다
- **production 도달** `runner.py:28 SIZING_SIG[ptype]` 하나. `reads.py:355 OBSERVER.get(...)` 하나
- **행동 영향** **없음**
- **동적 검증** 했음. `SIZING_SIG.get(k)` → **모든 키에서 None**, `k in S` → **False**, `list/dict/len/keys/items` → 전부 빈 값. `_ObsMap` 은 `get` 은 덮었지만 `in` 은 여전히 False, iteration 빈 값 — **두 클래스가 서로 다른 방식으로 불완전하다**
- **상태** `CLEANUP_LATER`
- **다음 조치** `__contains__`/`__iter__`/`keys` 를 맞추거나 dict 상속을 버리고 함수로

### D-1  미사용 `PRE_ORDER` / `POST_ORDER` import
- **분류** D
- **파일:라인** `view.py:2` · `session.py:5` (`from play import Hand, POST, PRE`) · 재수출 `play.py:7-8`
- **현재 역할** 정적 8맥스 사다리를 import 하지만 본문에서 참조가 0이다 (AST 확인). session 의 포지션 사용 6곳은 전부 `h.PRE`/`h.POST` 동적 값
- **production 도달** 이름만 스코프에 있다
- **행동 영향** 없음
- **동적 검증** 했음 — 1차 조사에서 E 후보였다가 재현 실패로 **D 로 강등**
- **상태** `CLEANUP_LATER`
- **다음 조치** 지금 무해하지만 다음 수정자가 잡아쓰면 즉시 9맥스 버그가 된다

### D-2  `persona.skill` / `persona.has`
- **분류** D
- **파일:라인** `persona.py:291 skill` · `296 has`
- **현재 역할** `sk`(338) 가 대체했다. `has` 는 전체 호출 0, `skill` 은 `has` 내부 호출로만 도달. 기본값도 다르다 (`skill` 3.0 vs `sk` 4.0)
- **production 도달** 없음
- **행동 영향** 없음
- **동적 검증** AST 호출 그래프
- **상태** `CLEANUP_LATER`

### D-3  dead `live.py` / `legacy_dynamics.py` / `legacy/`
- **분류** D
- **파일:라인** `live.py`(279줄, 루트 import 0) · `legacy_dynamics.py`(88) · `legacy/engine.py`(87) · `legacy/players.py`(46) · 루트 `tools_*.py` 7개(약 730줄)
- **현재 역할** `live2.py` 가 `live.py` 를 대체했다 — `new_game`/`step`/`finish`/`build_hand`/`save`/`load` 6쌍이 평행 구현이다. `legacy/engine.py` 는 포지션 사다리의 **세 번째** 하드코딩 사본
- **production 도달** 없음 (`tools/ctxcheck.py:50` 만 `live` 를 import)
- **행동 영향** 없음
- **동적 검증** import 그래프
- **상태** `CLEANUP_LATER`
- **다음 조치** `live.py:74` 가 `hash((...)) & 0xffffffff` 를 **RNG 시드로** 쓴다 — 프로세스마다 달라져 재현이 안 된다. 죽은 파일이라 현재 피해는 없다

### D-4  `table.Table` 사문 메서드
- **분류** D
- **파일:라인** `table.py:64 level_for_hand` · `72 posmap` · `78 street_order` · `82 rotate_button` · `95 reset_committed` · `97 award` · `102 sidepots` · `115 bust_check`
- **현재 역할** 정산·순서 기능이 `runner`/`session` 으로 옮겨간 뒤 남은 껍데기. 살아 있는 것은 `orders()`(9곳)와 클래스 자체(`runner.py:4` import)뿐이며 그 import 도 미사용이다
- **production 도달** 없음
- **행동 영향** 없음
- **동적 검증** AST 호출 그래프 (`posmap` tools 1회, `street_order` tools 2회)
- **상태** `CLEANUP_LATER`

### D-5  기타 미호출
- **분류** D
- **파일:라인** `runner.py:67 _only_incomplete`(같은 식이 `can_raise:71` 에 인라인) · `runner.py:130 pot_contrib` · `icm.py:131 icm_pressure` · `icm.py:161 required_equity` · `bot.py:83 equity` · `bot.py:238 straight_run` · `field.py:37 draw_type` · `field.py:193 seat_newcomers` · `reads.py:414 save_book` · `417 load_book` · `plan.py:1613 _prof_hint` · `persona.py:307 describe` · `355 gate` · `1039 profile_card` · `live2.py:188 level_of` · `fieldsim.py:45 chips` · `352 rank_of` · `play.py:3` 의 미사용 import 5개
- **상태** `CLEANUP_LATER`

### B-1  공개 API 로 보존
- **분류** B
- **파일:라인** `tourney.py:105 next_hand`(tools 31회) · `143 submit`(32회) · `146 finish_hand`(11회) · `formats.py:100 names`(9회) · `review.py:23 show`(5회)
- **현재 역할** production 내부 호출은 0이지만 도구·UI 의 진입점이다
- **상태** `VERIFIED_KEEP`

### B-2  archetype 호환 계층
- **분류** B
- **파일:라인** `preflop.py:19-20 BASE_OPEN/TRAITS`("구형 호환") · `plan.py:400` archetype 폴백 · `reads.py:40 _ObsMap` 의 ARCHETYPES 조회
- **상태** `VERIFIED_KEEP`

---

## 6. 실제 개념 지도

```
[driver]
  fieldsim._play_table:234 / tourney.next_hand:105 / live2.step:307 / (live.step:131 dead)
        │ 좌석·스택·버튼·블라인드·payouts·field_remaining/itm/avg
        ▼
[hand / state]
  play.Hand.__init__ → table.orders(n) 으로 2~9인 포지션 사다리
  play.Hand.deal        홀·보드 전부 선딜, hash 확정
  play.Hand.pid_of:48   대회 단위 상태의 유일한 키
        │
        ▼
[preflop money observation]
  session._money_jump_observe:37
     → money_pressure.actor_from_profile / signals / pressure_opportunity
       / low_commit_pressure / unopened_modifiers
        │ unopened_modifiers
        ▼
[preflop decision]
  session.py:489 PL.preflop_plan → preflop.py:305 thr *= range_factor   (LIVE)
        │ limp·sizing 은 SHADOW (기록만)
        │ h.pf_seed[seat] = _seed   ← 포스트플랍으로 넘어가는 유일한 프리플랍 상태
        ▼
[range reconstruction]            스트리트마다·액션마다 재계산 (캐시 없음)
  ranges.preflop_range → ranges.perceived_range → runner.adjust_range_by_history
        ▼
[reads / opponent model]
  reads.Book → reads.estimate:200 → reads.estimate_concepts:340
             → reads.perceived_profile:375
  (reads.opponent_belief:548 스타일 갈래는 **미배선**)
        ▼
[persona / archetype / dynamics]
  persona.make_player → play.Hand.axes:75 → persona.tilted_view   ← 틸트 반영 유일 지점
  archetypes 는 구형 폴백 경로로만
        ▼
[exploit interpretation]
  persona.read_opponent:850  → plan 16곳 · preflop · ranges
        ▼
[plan]
  session.py:754 PL.update_plan:1463   ← 유일한 진입점
     first/flop     → make_plan:256                        (상황 입력 10개)
     turn/river     → runner.revise_plan:145
                        board_changed 면 make_plan (상황 입력 5개)  ← F-8
     → refresh:1676 → river_fix:1550 → _allowed:1636 → attach_intent:559
        ▼
[position semantics]
  session.oop_field:12 / oop_vs:28  (session.py:659-668 에서 계산)
     oop_field      → cbet_freq (plan.py:1211, 1214)
     oop_vs_aggr    → blockbet 449 · donk 919      (어그레서 없으면 legacy, F-1)
     aggressor_pos_oop → session.py:834 line_bluff_prior
        ▼
[action / response / sizing]
  attach_intent → decide_aggression:849 → _roll → decide_size
  session.py:847 PL.act_with_plan:1248
     무저항 : intent 를 칩으로 환산만
     저항   : calldown_need:602 → decide_response:706
  보조: checkraise_decision / checkraise_size / overbet_frac / bluff_mode
        ▼
[round execution]
  runner.Round.apply:77   금액은 raise-to, 규칙 검증 포함
  runner.shape_size:26    타입별 사이즈 버릇 (rng 소비, 멱등 아님)
  session._finish:1108 → award_pots
        ▼
[intent snapshot]
  session.py:786 / 964   그 시점에 무엇을 봤는가 (기록 전용)
        ▼
[observation]
  스트리트 종료 session.py:1008  book.observe_postflop / observe_size
  핸드 종료  _finish             observe_preflop / _3bet / _4bet / showdown
        ▼
[book / tilt learning]
  reads.Book (대회 상태가 소유) · dynamics.Tilt (pid 별)
        └────────────► 다음 결정의 perceived_profile / axes 로 되돌아간다
```

**별도 가지**

```
ICM        play.Hand.bf:95 → icm.table_bf:302
              rem ≤ 9 → bubble_factor:144 → icm_equity:118 (9인 subset-DP 고속경로)
              rem > 9 → field_bf:292
           → session.py:847 act_with_plan(bf=…) → calldown_need:602 need_true
           (icm_pressure:131 · required_equity:161 은 호출자 0)

money      money_pressure → preflop.py:305 range_factor  (프리플랍 레인지 폭만)
           포스트플랍 _mj_obs(session.py:769) 는 관측 전용

style      reads.style_hypotheses:493 / concept_belief:521 / opponent_belief:548
           + style_sig.json · style_prior.json        ← **현재 미배선**

관측·표시  audit.py · ui/ · tools/ (103파일)  — 엔진이 import 하지 않는다
```

---

## 7. 기존 구조도와의 차이

`docs/ARCH_V1.png` (`tools/draw_arch.py`) 는 `fieldsim._play_table → session.HandRun._run → 스트리트 루프 → attach_intent → decide_aggression → _roll → decide_size` 한 줄기만 그린다.

| 빠진 것 | 근거 |
|---|---|
| 관찰 층 전체 | `_money_jump_observe`(액션 전)와 `book.observe_*`(스트리트·핸드 종료)라는 **서로 다른 두 관찰 시점**이 없다 |
| 상대 모델 층 | `perceived_profile` · `read_opponent` · `perceived_range` · `adjust_range_by_history` 가 매 액션 재계산되는데 노드가 없다 |
| 되먹임 고리 | `book`/`Tilt` → 다음 핸드 `axes`/`perceived_profile` 가 이 프로그램의 "학습"인데 화살표가 없다 |
| 드라이버 3종 | `tourney` · `live2` · `live` 가 없다. 필드 모델이 둘(`field.Field` vs `fieldsim.Field`)이라는 것도 없다 |
| ICM 가지 | `Hand.bf → table_bf → calldown_need` 한 점으로 수축한다는 사실이 없다 |
| money 가지 | 프리플랍에만 들어가고 포스트플랍은 관측 전용이라는 비대칭이 없다 |
| style belief | 미배선 분기가 코드에는 있고 그림에는 없다 |
| 재계획 두 경로 | `make_plan` 직접 vs `revise_plan` 경유가 서로 다른 입력을 받는다(F-8) |
| 포지션 세 술어 | `oop_field` / `oop_vs_aggr` / `aggressor_pos_oop` 의 소비처가 다르다 |
| 줄 번호 | `session.HandRun _run (113)` · `while True (315)` 로 적혀 있으나 실제는 `_run` 397, 스트리트 루프 610 |
| 관측·표시 층 | `audit.py` · `ui/`(5,112줄) · `tools/`(103파일) |

**새 구조도에 반드시 들어가야 할 노드**

1. driver 4 (fieldsim / tourney / live2 / live-dead) — 필드 모델 2종 표시
2. play.Hand (좌석·덱·pos 사다리·pid_of)
3. preflop money observation → preflop range (LIVE / SHADOW 구분)
4. pf_seed (프리플랍 → 포스트플랍 유일 통로)
5. range reconstruction 3단 (preflop_range → perceived_range → adjust_range_by_history)
6. reads: Book → estimate → estimate_concepts → perceived_profile
7. reads: style belief 갈래 (점선 = 미배선)
8. persona / archetype / tilted_view
9. read_opponent (exploit 해석)
10. update_plan 5단 파이프라인 + **재계획 분기(입력 5개 누락 표시)**
11. position semantics 3술어와 각자의 소비처
12. act_with_plan 두 갈래 (무저항 / 저항)
13. Round.apply + shape_size (RNG 소비 지점)
14. intent snapshot
15. 관찰 2시점 (스트리트 종료 / 핸드 종료)
16. Book / Tilt → 다음 결정 되먹임 화살표
17. ICM 가지 (Hand.bf → table_bf → need_true)
18. 관측·표시 층 (audit / ui / tools)

**화살표에 반드시 표시할 것**
- 실선 = 행동을 바꾸는 경로 / 점선 = 기록·관측 전용 또는 미배선
- money pressure 의 프리플랍 단방향성
- ICM 이 한 점으로 수축한다는 것
- 되먹임 고리가 핸드 경계를 넘는다는 것
- 재계획 경로의 입력 누락 5개
