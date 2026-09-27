# RANGE MODEL — weighted ranges + multiway semantics

## 1. Canonical weighted representation

Weighted range:
```python
{
    ('As','Kd'): 1.0,
    ('Qh','Qs'): 0.35,
}
```

값은 normalized probability가 아니라 positive finite **relative mass**다.

Rules:
- zero mass omitted
- common scale factor는 distribution을 바꾸지 않음
- legacy iterable은 occurrence당 mass 1.0
- duplicate legacy combo는 mass로 합산
- non-uniform weighted input을 legacy list로 조용히 flatten 금지

## 2. Migration status

### W0 CLOSED
representation + adapter.

### W1 CLOSED
weighted sampling:
- equity vs pools/combos
- range advantage
- joint range advantage
- joint relative strength
- current equity

legacy list는 기존 RNG choice path 보존.

### W2 CLOSED
weighted aggregates:
- relative strength
- strong share / nut
- blocker score/effect
- joint blocker effect

### W3 CLOSED
range transforms preserve incoming mass:
- ranked/bet/continue/call/check range
- perceived range
- facing-bet response
- action-history narrowing

### W4 CLOSED
downstream boundaries/signatures preserve weight.

Canonical CI: `.github/workflows/weighted-range-wiring.yml`
W0-W4 exact production parity PASS.

### W5 — NOT STARTED / LOGIC BARRIER
실제 observation을 non-uniform posterior mass로 생산하는 첫 전략 변화.
read/persona attribution과 별도 실험 없이 시작하지 않는다.

## 3. Multiway identity rule

seat-keyed opponent pools가 factual source다.

Showdown equity와 F8 layer equity는 이미 seat identity를 보존한다.
문제는 일부 strategy metric이 과거 union `opp_range`를 사용했다는 점이다.

Union은 seat 평균이 아니다.
range size가 큰 opponent가 더 큰 weight를 가져 multiway factual judgment를 왜곡할 수 있다.

## 4. F7-B status

### B1-A joint relative strength — CLOSED

Multiway relative strength의 direct extension:
> 각 seat range에서 compatible combo를 하나씩 뽑았을 때, 현재 board에서 **어느 상대에게도 strictly behind가 아닐 확률**.

Heads-up에서는 기존 relative_strength와 동일.

초기 live shadow:
- multiway 96 decisions
- pool sizes unequal 96/96
- union vs joint abs delta mean 0.189
- p90 0.353
- max 0.818
- existing rel strategy band crossing 59/96 = 61.5%

consumer activation 후 forced-union attribution으로 baseline movement가 모두 설명되어 closure.

### B1-B1 range advantage — CLOSED

Multiway candidate는 field fair share `1/(N+1)`을 0점으로 하는 normalized current-board share.
한 opponent에서는 기존 `2*equity-1`로 환원.

Shadow sample:
- 112 complete multiway states
- sign flip 20/112 = 17.9%
- abs delta mean 0.123
- p90 0.255
- max 1.075

이후 dedicated consumer로 승격/검증되어 closed.

### Nut semantics — OPEN

기존 nut advantage는 literal nuts가 아니라 strong occupancy bands를 비교한다.
multiway에서는 “opponent seat 평균”과 “field에서 최소 한 명이 strong region에 있을 확률”이 서로 다른 의미다.
최종 production semantic을 확정하지 않음.

### Blocker lifecycle — CLOSED

blocker factual metric과 consumer timing/provenance를 seat-aware lifecycle로 정리/검증.
새 multiway bluff tuning과는 별개.

### B1D defend likelihood — CLOSED

공통 likelihood helper rewire:
- probability invariants 97,344
- scripted checks 164,444
- mismatch 0

production exact parity:
- exact checks 92,883
- hotzone 1,611
- calloff 13,050
- attack outputs 2,124
- action/RNG mismatch 0

### B2 representative opponent — OPEN

현재 multiway에서도 일부 경로가 main aggressor 또는 deepest opponent 한 명의:
- perceived profile
- stack
을 scalar로 넘긴다.

fold-heavy 한 명이 있다고 “field 전체가 fold-heavy”인 것은 아니다.
replacement는 union profile이 아니라 downstream quantity별 정의가 필요하다:
- all-fold probability
- per-seat response
- stack constraint
등.

## 5. Missing/unknown pool rule

required seat range가 missing이면 unknown으로 남긴다.
다른 seat range나 union을 복제해서 가짜 opponent pool을 만들지 않는다.

## 6. Invariants

1. weighted mass silently flatten 금지.
2. uniform legacy path는 기존 behavior/RNG 보존.
3. opponent identity가 필요한 metric은 seat pool 사용.
4. metric마다 multiway 의미를 별도 정의.
5. W5와 F7-B semantic change를 한 실험에 섞지 않음.
6. range change와 GTO tuning을 구분.

## 7. Historical sources

- `WEIGHTED_RANGE_DESIGN.md`
- `F7B_MULTIWAY_DOWNSTREAM_AUDIT.md`

세부 preregistration/measurement sections는 pre-consolidation Git history에 보존.
