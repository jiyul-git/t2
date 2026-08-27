# 진행 중 작업 — 판단/집행 층 분리

## 왜 하는가
"A를 넣었는데 B가 나온다"의 원인: 상류가 계산한 값을 하류가 안 쓴다.
같은 것을 두 곳에서 각자 결정하는 경로가 여러 개 있다.

## 층 규칙 (앞으로 새 요소는 여기 맞춰 넣는다)
- 인식: texture, ranges, reads, relative_strength, blocker, nut_advantage
- 판단: make_plan / refresh / decide_aggression / decide_size / trap_judgment
- 집행: act_with_plan — intent 를 칩으로 환산만 한다. **판단 금지.**

집행부에 조건을 앞에 끼워넣지 않는다. 그게 지금 문제의 원인이었다.

## 완료
- [x] enforce_consistency 제거 (계획을 실행에 맞춰 고쳐써서 모순을 은폐하던 함수)
- [x] intent 자료구조 (mk_intent / intent_of / set_intent / attach_intent)
- [x] decide_size — 사이즈 결정 단일화 (SIZING/TX/overbet 혼재 해소)
- [x] decide_aggression — cbet_freq + 동크억제 + p_bet 통합, plan 을 반드시 본다
- [x] make_plan / refresh / revise_plan 이 intent 확정
- [x] act_with_plan 무저항 분기를 intent 읽기로 교체
- [x] revise_plan 이 opp_est 유실하던 것 수정

## 완료 (이어서)
- [x] (1) 의도 누락: make_plan/revise_plan 이 새 dict 반환 → intents 이력 유실. 명시 승계
- [x] (2) 의도불일치: 의도는 tc==0 시점에만 확정. 폴백/환산실패도 deviations 에 기록
- [x] (3) discipline 기반 이탈 — DEVIATE 표시 + record_deviation.
        측정: 규율<4 → 4.2%, 중간 3.1%, 규율>7 → 1.7%
- [x] 데드칩 실수 나눗셈으로 칩 1개 소멸하던 것 정수 분배로 수정

- [x] (4) tocall>0 의 콜/폴드/레이즈 → decide_response (판단 층). p_raise 집행부에서 제거
- [x] (5) 프리플랍 계획 층 preflop_plan 신설. session.py:167 에서 호출 중
        실측: 274회 호출 (fold 196 / call 35 / raise 31 / 3bet 6 / shove 4 / limp 2)
- [x] (6) 재현성 검증: seed 3000, 50핸드, 별도 프로세스 3회 → 해시 완전 일치

## 남음
- [ ] 성향이 실제 의사결정에 제대로 전달되는지 핸드 단위 교차검증
      (불변식이 못 잡는 영역. 지금까지 버그는 대부분 여기서 나왔다)
- [ ] 대량 시뮬 기반 전략 품질 측정 (익스플로잇 봇이 실제로 더 따는가)

## 문서 신뢰성 주의
README/WORKLOG 를 근거로 상태를 판단하지 말 것.
문서가 코드보다 낡아 있던 사례가 실제로 있었다 (4·5번을 구현하고 문서를 안 고침).
상태 확인은 반드시 호출부 grep + 실행 계측으로 한다.
'함수가 존재한다'와 '호출된다'는 다르다 — 이 프로젝트에서 반복된 버그 유형이다.
- [ ] (4) tocall>0 의 p_raise 4곳도 판단 층으로 이동 (콜/레이즈 의도)
- [ ] (5) 프리플랍 계획 층 신설 — 현재 preflop.py 는 즉석 액션만, intent 없음
- [ ] (6) 정리 후 재현성 확인 → 기준선 재저장

## 검증
- tools/regress.py — 지문. 구조 정리 중엔 깨지는 게 정상
- tools/invariants.py — 이미 아는 것만 잡는다. 보조 수단일 뿐
- 실제 확인은 핸드를 직접 뜯어보는 것 (사용자가 발견한 버그가 대부분)

## 백업
/mnt/user-data/outputs/poker_sim.tar.gz


## 실제 플레이 검증으로 잡은 버그 (코드 리뷰로는 안 나왔음)

**이 방식이 가장 효과적이다.** 히어로로 직접 치면서
① 상대 성향 → ② 그 시점 추정 레인지 → ③ 실제 홀카드 → ④ 행동이 논리적인가
→ ⑤ 봇 내부 판단 로그 대조. 이상하면 코드로 역추적.

### ranges._call_range — 최상위를 안 잘랐다
"최상위 6%는 레이즈했을 것이므로 제외"라고 해놓고
잘라낸 lo 를 결과에 다시 더했다. 그래서 아무것도 안 잘렸고,
3배럴을 **콜만** 한 레인지에 999·KK·QQ 풀하우스가 그대로 남았다.
결과: 콜 레인지가 벳 레인지보다 강해지는 역전.
넛 플러시가 rel 0.59 로 나와 v3 문턱이 0.94 까지 올라가고
밸류 계획이 봉쇄되어 pot_control(체크백)으로 떨어졌다.
→ 콜 경로 rel 0.50 → 0.818, eq 0.751 → 0.910

### bot.draw_strength / straight_run — 갭을 무시했다
'5칸 창 안의 서로 다른 값 개수'를 세는 방식이라
2-3-4-6 처럼 갭 있는 조합을 오픈엔더(8아웃)로 판정했다.
실제로는 5 하나만 필요한 거트샷(4아웃). 정확히 2배.
그 값이 semibluff 계획 선정과 need 감산에 들어가
rel 0.0 인 66 이 30bb 를 밀어넣었다.
→ 필요 카드 수를 실제로 세는 방식으로 교체. 66 은 8 → 4아웃.

주의: 65/A5 가 0아웃으로 나오는 건 정상이다.
해당 보드에서 이미 스트레이트가 완성돼 draw_strength 첫 줄에서 걸러진다.
