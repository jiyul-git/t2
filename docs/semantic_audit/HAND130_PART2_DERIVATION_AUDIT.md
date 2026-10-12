# HAND130 / 파트 2 — 방어·콜오프 계산식 및 경험상수 도입 근거 감사

> **2026-10-10 후속 정정:** 아래 최초 감사의 W5 수치 `0.013483745270`는 실제 엔진 값이 아니라 재계산 오류였다. `tighten_defend_widths_for_raise_level`에서 `tp *= lt`가 먼저 실행되고, 이어지는 `tot = tp + (tot-tp)*(lt*0.8)`에서는 **축소된 tp**를 사용한다. 이 순서대로 재계산하면 `W5=0.016657816839054443`이며 기존 보고 `0.0166578`과 반올림 일치한다. 참조: [후속검증/데이터 계약](HAND130_PART2_W5_FOLLOWUP_CONTRACT.md). 실제 실행 중간 로그·당시 원본 코드 SHA·틸트/플래그 기록이 있었다는 뜻은 아니다.\n\n- 조사 기준: `test3` @ `945758accf095c634e7a543da73d38160f8b00e2` (2026-10-10)
- 관련 원본: `docs/handoff/T2_T3_HANDOFF_20261010.md` 부록 F (HAND 130)
- 범위: `gto.py`, `preflop.py`, `persona.py`, `depth.py`, `plan.py`, `session.py`, `ranges.py`, `icm.py`
- 상태: **판단 전략 변경 없음**. 수식과 소비처 정적 감사; 읽기 전용 재현 스크립트 `tools/verify_hand130_part2.py`.
- 원칙: 하나의 AK 사례에 맞춘 범위 하한·임의 계수 변경 금지. 9-max의 비올인 3bet/4bet prior가 검증되지 않은 상황에서 정답 수치 만들지 않음.

## 1. 공개 액션과 계산의 질문이 다른 구조적 원인

HAND130: B37(좌석3, LJ) A♣K♥, 2BB 오픈 후 BB(좌석9) 총7.3442BB 올인 대면, 추가 콜비용 53,442칩, 콜 전 팟 108,442칩, 총 경합 팟 161,884칩, 추가 레이즈 불가, 테이블 8명, 버블(남은 8명/ITM 7명). 

실제 호출은 `defend_thresholds(profile, def_pos='LJ', opener_pos='BB', bb=20.9864, open_bb=7.3442, raise_level=2, seats=8, ante=True)`. 그러나 `gto.rfi('BB')=0`: BB는 이 핸드에서 **3벳을 한 사람**이지 첫 오프너가 아니다. `gto.defend_pct`는 vs-open 방어 기준을 이 인자에 적용한다. 그래서 BB의 관측 3벳 레인지, B37의 기존 LJ 오픈 레인지, 유효스택, 팟오즈를 반영하는 것이 아니라 `DEF_A * MDF_scale * DEF_SEAT['LJ']`로 출발한다.

동일 생산자 `preflop.defend_thresholds`는 봇 액션의 `preflop.defend_action_likelihoods/defend_decision`과 상대의 `ranges._def_thresholds/preflop_range`에서 공유한다. `preflop.calloff_cap`은 이 생산자를 다시 호출한다. 이 공유 함수를 수정하면 5번 담당뿐 아니라 8번 상대 레인지 복원·관측 likelihood까지 영향을 받는다. 현재 수식의 값만 바꾸지 않았고 producer도 수정하지 않았다.

`session.HandRun` → `plan.preflop_plan` → `preflop.defend_decision` 에서 legacy 폴드를 산출하고, 별도로 `session._preflop_perceived_range` → pot layers → `preflop.calloff_layer_judgment`를 계산한다. pure calloff·complete이고 `pf_defend` 지식 게이트에 통과해야만 layer EV 행동으로 덮어쓴다. 게이트 실패 시 legacy `pf_rank<=cap` 판단으로 확정된다.

## 2. 단계별 현재 코드 식 — B37 저장 *기본* 프로필 기준 독립 재계산

전제: `T2_GTO_MEMORY_V2=0`, `T2_PREFLOP_REASONING_V3=0`; 틸트 변환 없는 `actor_profile` 그대로; 중립 exploit `E=1`. 실제 런타임 planning view 및 환경변수는 원자료에서 독립적으로 확정되지 않는다. **아래는 코드 기반 정적 재계산이지 당시 프로세스 재실행이 아니다.**

| 단계 | 공격 폭 tp | 전체 계속 폭 tot | 수식/원인 |
|---|---:|---:|---|
| `gto.defend_pct/threebet_pct` | 0.005643000 | 0.031350000 | `(.22+.68*RFI(BB=0))*(.38/.56)*DEF_SEAT[LJ=.21]`, tp=`tot*.18` |
| 인간 기억/성향 원시 | 0.007965585441 | 0.052495575000 | `acc=.29`, `room=.71`, `d_call=1`, `d_tb=.527`, `tot*=1+room*d_call*.95`, `tp*=1+room*d_tb*1.10` |
| `normalize` | 0.011050549970 | 0.072826407931 | `tot=.8*(1-exp(-rawTot/.55))`, tp 원시비율 유지 |
| `adjust_for_callers` | 0.011050549970 | 0.072826407931 | 콜러0명, 변경 없음 |
| `adjust_for_short_stack` | 0.017680879952 | 0.045152372917 | 깊이 D=.1318368<.20, tp*1.6, tot*.62 |
| `tighten_for_raise_level` | 0.006011499184 | **0.016657816839** | 레벨2→lt=.34; `tp*=lt;tot=tp+(oldTot-tp)*lt*.8` (**갱신된 tp 사용**) |

이후 `calloff_cap`: `C_raw = tot*.22*2.6*(1-.18*D)/max(1,BF)`, BF=3.465325; 중립 exploit. 계산값은 0.005 하한보다 작으므로 **최종 cap=0.005(0.5%)**. 이것을 `legacy_preflop_order_percentile(A♣K♥)=.0302`와 비교하여 폴드한다.

**오류 해소:** 이전 재계산 `0.013483745270`는 갱신 이전 tp를 빼서 나온 수치이다. 실제 소스의 갱신 순서를 적용한 `W5=0.016657816839054443`과 대화에서 보고된 `0.0166578`은 반올림 일치한다. 정확한 후속 `C_raw=0.0026843541110758663` (0.2684354111%); 하한 적용 후 `0.005`. 과거 실행에서 동일 코드를 실행했음을 입증하는 원본 intermediate telemetry는 없다.

## 3. 주요 계수·구조별 provenance, 단위, 소비 및 중복 가능성

| 항목 | 최초 확인 커밋/후속 | 도입 의도와 정량 근거 | 정의역/단위·소비처·중복 판정 |
|---|---|---|---|
| `DEF_A=.22; DEF_B=.68` | `58d64a436bc19c5a4ebf8a3102cbf950f4dc201c` 2026-09-01 | BB vs 3x 오픈 공개자료 4점의 **경험근사**. 자료명·계산 스팟·파일 locator 없음 | 무차원; `defend_pct`에서 `A+B*RFI`. vs 3bet에도 재사용되어 wrong quantity. 조건부 range prior 아니다 |
| `DEF_SEAT` | `58d64a4` | BB 기준 자리별 축소 의도. .62/.46/.34/.26/.21/.18/.16/.14의 각각 정량 근거 없음 | 무차원 좌석 배수; gto.defend_pct; LJ .21의 과도한 압축. `LEVEL_TIGHTEN`과 반복 축소 가능 |
| `DEF_VS_SB=.60` | `58d64a4` | BB vs SB 특별 구도; .60 외부 자료 locator 없음 | 전체 방어 비율, 무차원; `gto.defend_pct` 전용. HAND130 직접 영향 없음 |
| `TB_SHARE=.18` | `58d64a4` | 방어 폭 중 3bet 몫. .18의 독립 수치 출처 없음 | [0,1] 몫, `threebet_pct`→tp→shallow×1.6→level contraction. HAND130 LJ 경로에 사용 |
| `NINE_MAX_TB_SHARE_BRIDGE` | 2026-10-06 주석/코드 | BB/SB/BTN/CO에 8max 안테 몫을 차용한 임시 다리. 9max 실측 독립 prior 아님 | 자리별 차트 소비; HAND130 LJ에는 미적용 |
| `_MDF` 5점, `mdf(open)/mdf(3)` | `58d64a4` 당시 표; `b23ca4f0` 비율 동작 확인, `982a8f8d` 확장 후 회귀 악화로 되돌림 | 오픈 사이즈에 따른 방어 폭 반응을 대용. 수학적 MDF 아님; 6BB 이상은 .38 포화. 원본 솔버 근거 미확인 | 무차원; `gto.defend_pct`에 곱함. 쇼브의 **콜 가격**으로 쓰는 것은 개념 오류 |
| `LEVEL_TIGHTEN={2:1,3:.34,4:.16,5:.10}`, `*.8` | 확인 가능한 최초 `preflop.py` 커밋 `6543b92be70d` 2026-08-27부터 이미 존재; `33df2ee4` 단계 함수 분리·동작 동일 | 상위 재레이즈일수록 tight. 모든 수치의 외부 대응 조건/근거 미확인 | 무차원 축소 계수, raised-level producer; 4bet 독립 prior가 아님. 콜오프 추가 축소와 중복 **효과** 가능 |
| `CALLOFF_TIGHTEN={2:.55,3:.22,4:.11,5:.07}` | `6543b92` earliest baseline에 이미 있음; `ac05c00a` 새 calloff_cap에서 재사용 | 올인 수준 높을수록 축소. 계수별 증거 없음 | 무차원, `calloff_cap`; 기존 raise-level 축소 직후 다시 감소; `.22`는 `DEF_A`와 별개의 값 |
| 콜오프 `*2.6`, `*(1-.18*depth)`, `clip(.005,.85)` | `ac05c00a620a8963b61424a184c9209fded469b9` 2026-09-01 | 구 경로의 올인 대응/임플라이드 오즈 소멸/상한 보호. 계수 2.6,.18,.005,.85의 정량 도출·표본 근거 없음 | 전부 무차원; `calloff_cap` → `calloff_decision`, `legacy_calloff_likelihoods`, P5 fallback. .005는 실현 최소 AA 손실 회피 근거가 아님 |
| `BF`로 폭 나눗셈 | `ac05c00a` | 버블에서 생존·ICM 압력 표현. 실제 **필요 equity** 공식과 비동치 | BF ≥1 무차원; cap에서는 객관 BF로 `tot/BF`; layer는 개인 인지 BF. 두 경로 의미 불일치 |
| `LOADING_PROVISIONAL=True`, `LOADING` | 잠정값 명시 `8306c61fcc0b` 2026-08-28; 원래 loading은 더 이전 | 잠재 study/aggro/exp 요인과 개념점수 생성. 모든 base/loading 계수의 모집단 피팅 근거 확인 안 됨 | 0~10 숙련점수에 선형 결합·노이즈. persona 생성 → `pf_defend` → knowledge, gate, 상대모델로 간접 소비 |
| `SPREAD`, `DEFAULT_SPREAD=1.45` | `e5bdc1fb1fd5` 2026-08-28 | 개념별 개인차 분산 구별. 분산의 인간 표본 근거 없음 | 0~10 점수에 정규 노이즈 **표준편차 점수**; 일부 2.45 등. 생성된 개념 질량과 장기 행동에 영향. 기존 B37 보존 프로필을 바로 바꾸는 항은 아님 |
| `_split_concepts()` | `8f506e6f0790ff7941f9fecfb1ef10c29087c6f5` 2026-10-06 | 11개 독립 분할키를 부모와 상관시키고 shared RNG 불변. 부모 mean/sd는 1,000명 시뮬레이션 측정, `r=.6~.85`/offset은 설계값이지 인구학적 보정자료 아님 | `mean+r*(parent-mean)+sqrt(1-r²)*sd*z+offset`; 점수·상관·노이즈. clipping/학습필터 뒤 실제 r 달라질 수 있음. 분할된 3bet/read 소비자에 간접 영향 |
| `_apply_concept_learning_structure()` | 학습 관계 추가 `3ceb2c51` 2026-10-04; `e8348beb`→`64f7e7f7`→`1c9303ed`→`b7cf4638`→`c905a8cf`; v5 `64cd1eb70d` 2026-10-06 | 고급숙련 꼬리/선행보다 후행만 높음 방지. capacity=.6·study+.4·exp, margin3/tail2·hard margin2/tail1 및 readiness^1.5 **모두 실증 근거 확인 안 됨** | 숙련점수 0~10을 아래로 압축. `pf_defend`, `potodds`, `icm`, `range_read` 분포와 게이트·레인지 추정에 간접 영향 |

**주석으로 확인되는 의도와 수치가 검증됐다는 증거는 별개다.** 최초 GitHub 공개 기준선에 이미 존재하는 값은 그보다 앞선 실제 선정 시점·실측 근거를 확인했다고 말할 수 없다.

## 4. 올인 콜의 별도 단위가 있는 기본식

`C` = 추가 콜 비용(칩), `P` = 콜 전 경합 가능 팟(칩), `E` = 상대 쇼브 레인지에 대한 에쿼티(0~1), `BF` = 버블 팩터(1 이상).

- 칩 EV: 콜 유리 조건 `E >= C/(P+C)`. HAND130: `C=53442, P=108442`, 필요 에쿼티 0.330125(33.0125%).
- T2 현재 ICM 근사: `E >= BF*C/(P+BF*C)` (실제 `icm.required_equity` 코드). BF 3.465325이면 **필요 0.630692**, 원 저장 observer-layer 에쿼티 **0.631820**. 차이 +0.001128(0.1128%p).
- 800회/계층 Monte Carlo 결과가 ICM 문턱과 **매우 가까우므로** 0.63182를 참값으로 간주하거나 robust +EV를 단정하지 않는다. 더 큰 독립 시드·레이어별 에쿼티 오차·observer range sensitivity 검사 필요.
- 실제 B37 인지 BF는 1.369799, `potodds_noise=.65`, 기록된 인지 필요 승률 .261954, 개인 layer 판단은 call, 하지만 `pf_defend_gate_p=.439355 < roll=.664054`이므로 legacy fold 유지.
- **새로운 독립 고정 레인지 하한은 도입하지 않는다.** 검증 가능한 원시 변수(팟/추가비용/상대 조건부 레인지/팟 레이어/인식한 ICM/카드별 equity)로만 행동 판단을 교정한다.

## 5. 지금 전략식을 임의 대체하지 않은 이유

1. actor/observer 공유 producer를 건드리면 상대 posterior가 같이 달라져 5번·8번 파트 및 테스트 영향 추적이 필요하다.
2. 현재 9-max asymmetric stack/3bet/4bet/올인 상황에 맞는 완전 검증된 action-conditional prior가 없다. `RFI * other multiplier`는 검증된 콜오프 지식으로 대체할 수 없다.
3. 지식 게이트에 실패한 인간을 어떻게 합리적으로 행동시킬지(불완전 기억·근사 계산)는 5번 파트 정책과 연결된다. 정확한 에쿼티를 모든 낮은 숙련자에게 무조건 강제하는 것도 인간모델의 능력 의미를 훼손한다.
4. 인수인계 W5와 정적 재계산의 **수치 차이는 감사 수식 오류로 해소**되었다. 다만 당시 tilted planning profile, 환경 플래그, 실행 프로세스 SHA 및 진짜 W5 중간 telemetry는 별도 미기록이다.

기존 감사 `docs/semantic_audit/r2/CALLOFF_PATH_AUDIT.md`는 P1/P2/P4/P5/P6/P7의 다른 판단량과 first-in shove 레인지 복원 문제를 확인했다. 보고된 비교 9-max push/fold 63 spot에서 solver DB jam range를 주었을 때 94.0% 일치, T2 observer range를 쓸 때 77.1% 일치. 이 데이터는 T2의 해당 비올인/안테 상황과 정확 조건이 같지 않으므로 정답 수치로 직행하지 않는다.

## 6. 검증 및 후속 수용조건

- `python3 tools/verify_hand130_part2.py`: 아카이브 기본 프로필로 현재 코드 각 단계와 순수 가격·ICM 산술 검증; 의도적 W5 불일치 기록; **행동 미변경**.
- `python3 tools/regress.py check --baseline current`: 전략 미변경 기대. 실제 수행 결과는 별도 Actions 로그 또는 로컬 실행 로그에만 근거한다.
- 5번/8번 합동: actor와 observer의 같은 상태에서 `pure_calloff`, `near_allin`, `covering_stack`, `opener_backaction`, `multiway` 다섯 경로별 조건·뜻·값·레인지 질량 비교.
- 검증된 prior 확보 또는 불확실성 표시 후, `chip price + equity + ICM` 계산을 공통 decision evidence로, 불완전 지식/인지 부족을 개인 capability에 대응시키는 정책 설계. 각 수정은 9-max 고정 시드 paired counterfactual, per-spot action attribution, 레인지 복원 검사 통과 후만 배포.
