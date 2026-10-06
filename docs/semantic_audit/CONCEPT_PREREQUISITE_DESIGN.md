# CONCEPT_PREREQUISITE_DESIGN

기준: 2026-10-05 `test`

## 목적

서로 선후행 관계가 명확한 독립 개념에서, 후행 개념만 비정상적으로 높고 선행 개념이 매우 낮은 플레이어 생성을 막는다.

반대 방향은 제한하지 않는다.
- 선행 지식이 높고 후행 활용이 낮은 사람: 허용
- 후행 지식이 선행보다 조금 높은 사람: 경험/암기/직관으로 허용
- 후행 지식이 선행보다 지나치게 높은 사람: 제한

## v1 규칙

점수 범위는 기존 0..10을 그대로 사용한다.

```
downstream <= prerequisite + 2.0
```

허용 격차 `+2.0`은 잠정값이다. 새 난수나 새 latent를 만들지 않는다.

### v1 hard prerequisite

```
cbet_flop -> barrel_turn -> barrel_river
cbet_flop -> delayed_cbet
```

의미:
- 턴 배럴 지식은 플랍 지속베팅 지식보다 2점을 초과해 앞설 수 없다.
- 리버 배럴 지식은 턴 배럴 지식보다 2점을 초과해 앞설 수 없다.
- delayed c-bet 지식은 기본 c-bet 지식보다 2점을 초과해 앞설 수 없다.

## 이번에 hard filter로 넣지 않는 관계

현재 코드가 의도적으로 독립 조합을 허용하거나, '도움 선행'에 가까운 관계는 제한하지 않는다.

예:
- positional / pf_range
- range_read / board_texture / sizing_tell
- board_texture / potcontrol / trap
- money_jump / icm
- stack_decay / open_size

이들은 실제 행동상 관련은 있지만 한쪽이 낮다고 다른 쪽의 높은 숙련을 불가능으로 만들 근거가 아직 부족하다.

## 생성 위치

기존 `LOADING + SPREAD + latent`로 모든 concept raw score를 먼저 만든다.
그 뒤 `persona.make_player()` 내부에서 deterministic cap만 적용한다.

따라서:
- prerequisite 필터 자체는 새 RNG를 소비하지 않음
- latent/raw concept draw 순서는 유지
- 선후행 위반 표본만 아래로 보정
- 보정 뒤 `overall_skill`이 필드 하한/상한을 벗어나면 기존 재추첨이 작동할 수 있으므로 최종 모집단 RNG 진행은 달라질 수 있음

## 검증

1. 모든 생성 플레이어가 hard prerequisite를 만족해야 한다.
2. 선행이 높은데 후행이 낮은 조합은 그대로 허용해야 한다.
3. 같은 seed에서 난수 소비 순서는 바뀌지 않아야 한다.
4. 필터 적용 전/후 concept 분포 변화량을 별도로 측정한다.


## v2: 독자 개념 난이도

복합 capability(판단+계획, 계획+실행, 판단+계획+실행)는 아직 제외한다.

| 개념 | 난이도(0~10) | 해석 |
|---|---:|---|
| positional | 2.0 | 포지션 유불리 기본 |
| open_size | 2.5 | 기본 오픈 사이즈 |
| outs | 2.5 | 드로우 개선 카드 계산 |
| board_texture | 3.0 | 기본 보드 구조 해석 |
| potodds | 3.5 | 콜 가격 계산 |
| pf_range | 3.5 | 포지션별 기본 프리플랍 레인지 |
| cbet_flop | 4.0 | 기본 지속베팅 |
| trap | 4.0 | 강한 패를 숨겨 유도하는 기본 개념 |
| multiway | 4.5 | 다인팟 가치 조정 |
| money_jump | 4.5 | 상금 점프 인식 |
| potcontrol | 5.0 | 중간 강도 핸드의 팟 관리 |
| sizing_tell | 5.0 | 상대 사이징 의미 해석 |
| delayed_cbet | 5.0 | 플랍 체크 뒤 턴 공격 |
| probe | 5.5 | 체크로 약해진 범위 공격 |
| barrel_turn | 6.0 | 플랍 이후 변화까지 반영한 지속공격 |
| stack_decay | 6.5 | 미래 블라인드 침식 반영 |
| blocker | 7.0 | 콤보 제거 근거 활용 |
| barrel_river | 7.5 | 전체 라인을 반영한 마지막 스트리트 공격 |
| range_read | 8.0 | 포지션/액션/보드/사이징을 종합한 레인지 복원 |
| icm | 8.5 | 칩 EV와 상금 EV의 비선형 관계 반영 |

난이도는 평균점수를 직접 덮어쓰지 않는다. 기존 LOADING/SPREAD로 뽑은 raw score에 대해,
플레이어의 학습량보다 난이도가 높은 개념에서만 고숙련 꼬리를 제한한다.

```
capacity = clamp(0.60 * study + 0.40 * exp, 0, 10)
difficulty_cap = 10 - max(0, difficulty - capacity)
score = min(raw_score, difficulty_cap)
```

따라서 capacity가 difficulty 이상이면 기존 raw score는 그대로다.

## v2: 학습 선후행

실전 의사결정 의존성과 학습 순서는 구분한다.

### 도움 선행

후행을 배우는 데 도움이 되지만, 암기/직관/경험으로 일부 건너뛸 수 있다.

```
pf_range + positional + board_texture -> cbet_flop
potodds + board_texture -> multiway
potodds + board_texture -> potcontrol
pf_range + positional + board_texture + sizing_tell -> range_read
cbet_flop + board_texture -> barrel_turn
cbet_flop + board_texture -> delayed_cbet
range_read + board_texture -> probe
board_texture + range_read -> trap
barrel_turn + range_read + board_texture -> barrel_river
money_jump + potodds + stack_decay -> icm
```

도움 선행은 개별 최솟값이 아니라 평균을 쓴다.

```
downstream <= mean(prerequisites) + 3.0
```

한 선행이 약해도 다른 지식과 경험으로 보완할 수 있게 하기 위해서다.

### 필수에 가까운 선행

기존 v1 규칙을 유지한다.

```
cbet_flop -> barrel_turn -> barrel_river
cbet_flop -> delayed_cbet

downstream <= prerequisite + 2.0
```

### 의도적으로 묶지 않은 관계

`positional -> pf_range`는 학습상 자연스럽지만 hard/soft cap 모두 걸지 않는다.
현재 코드가 "차트 총량은 외웠지만 포지션 의미는 약한 사람"과
"포지션 감각은 있지만 차트를 외우지 않은 사람"을 의도적으로 표현하기 때문이다.

같은 이유로 blocker도 range_read의 필수 후행으로 묶지 않는다. blocker 개념 자체를
따로 배울 수 있고, 실제 활용 품질은 소비 단계에서 달라질 수 있다.

## 적용 순서

```
raw LOADING/SPREAD draw
    -> money_jump 생성
    -> difficulty cap
    -> 도움 선행 cap (위상순서)
    -> hard prerequisite cap
    -> temperament 생성
    -> overall_skill field bound / 기존 재추첨
```

새 RNG는 추가하지 않는다.


## v3: 고급 개념 고숙련 꼬리

1,000명 모집단 감사에서 blocker / range_read / icm의 7~10 숙련 비율이
난이도 정의에 비해 높게 나타났다. 세 개의 난이도 점수 자체는 유지하고,
0~6점의 기초/중급 이해와 6~10점의 고급 활용을 분리한다.

대상:
- blocker (difficulty 7.0)
- range_read (difficulty 8.0)
- icm (difficulty 8.5)

규칙:

```
capacity <= difficulty - 3:
    6점 초과 숙련은 열리지 않음

difficulty - 3 < capacity < difficulty:
    6~10 구간을 readiness 비율만큼만 유지

capacity >= difficulty:
    기존 고숙련 raw score를 그대로 허용

readiness = clamp((capacity - (difficulty - 3)) / 3, 0, 1)
score = 6 + (score - 6) * readiness   # score > 6인 경우만
```

의도:
- 기본적인 blocker 감각 / 상대 range 감 / 상금 압박 인식까지 희귀하게 만들지 않는다.
- 정교한 combo 제거 활용, range reconstruction, ICM exploitation 같은 고숙련만
  충분한 study/experience가 있는 플레이어에게 집중시킨다.
- 별도 RNG를 추가하지 않는다.
- 모집단 감사와 구조 검증 모두 한 번에 생성하는 플레이어 수는 최대 1,000명으로 제한한다.


### v3.1 고숙련 습득 곡선

1차 1,000명 감사 결과 7점 이상 비율이 blocker 20.0%, range_read 18.7%,
icm 14.1%로 여전히 높았다. readiness를 선형으로 쓰지 않고 다음처럼 조정한다.

```
readiness = readiness ** 1.5
score = 6 + (score - 6) * readiness
```

초중간 학습량에서는 7~10 숙련이 더 천천히 열리고,
difficulty 수준까지 도달하면 기존과 동일하게 완전히 열린다.


## v4: 선후행 필터 soft compression

기존 `downstream <= upstream + 2` / `mean(prerequisites) + 3` hard cap은
경계값에 표본을 몰아넣는 문제가 있다. v4부터 +2/+3은 절대 상한이 아니라
"감쇠 없이 허용되는 자유 격차"로 해석한다.

공통식:

```
gap = downstream - upstream
if gap <= free_margin:
    unchanged
else:
    excess = gap - free_margin
    kept = soft_tail * excess / (soft_tail + excess)
    downstream' = upstream + free_margin + kept
```

특성:
- downstream 점수를 절대 올리지 않는다.
- free_margin 안쪽은 완전히 보존한다.
- 초과분은 연속적으로 압축하므로 경계점 pile-up을 줄인다.
- raw downstream이 커질수록 최종 downstream도 계속 커져 순위가 보존된다.
- 최종 격차는 `free_margin + soft_tail`에 점근한다.

현재 값:

| 관계 | free margin | soft tail | 점근 최대 격차 |
|---|---:|---:|---:|
| hard prerequisite | +2.0 | +1.0 | +3.0 |
| learning support | +3.0 | +2.0 | +5.0 |

예: hard 관계에서 upstream=3일 때
- raw 5.0 -> 5.0 (그대로)
- raw 6.0 -> 5.5
- raw 7.0 -> 약 5.67
- raw 9.0 -> 약 5.80

즉 +2를 넘는 예외는 남기되, 멀리 벗어날수록 추가 이득이 급격히 줄어든다.



## v5 초안: 표에 없는 개념 17개의 난이도·선후행 (2026-10-06, **제안 — 승인 전, 코드 없음**)

### 출발점 (다시 확인)

"각 개념 숙련도가 독립적으로 튀면, 고급 개념은 잘 아는데 그걸 떠받치는 기초 개념은 전혀 모르는 이상한
플레이어가 생긴다 → **정말 관계 있는 개념에만** 선후행 필터를 건다."
- 연관만 있다고 묶지 않는다(positional → pf_range 를 뺀 이유: 이론 없이도 차트는 외운다).
- 필수 선행(hard)은 "앞 개념 없이는 뒤 개념을 배우기 어려운" 경우만. 지금은 c벳 계열 3쌍뿐이다.
- 이 필터는 persona 의 숙련도 생성·조정이다. ranges.py 의 상대 레인지 컷오프와 무관하다.
- 분할 키(checkraise_turn 등)의 독립 생성은 이 작업이 아니다 — CONCEPT_SPLIT_TODO 의 phase 2 로 따로 다룬다.

지금 v1~v4 는 생성 개념 37개 중 20개만 다룬다. 남은 17개를 같은 원칙으로 채운다.

### v5-1. 난이도 (기존 20개 값은 그대로)

| 개념 | 난이도 | 개념 | 난이도 |
|---|---:|---|---:|
| bluff | 3.5 | thin_value_turn | 6.0 |
| fold_equity | 4.0 | blockbet | 6.0 |
| semibluff | 4.5 | equity_denial | 6.0 |
| pf_defend | 4.5 | range_merge | 6.5 |
| bluffcatch_early | 5.0 | checkraise_late | 6.5 |
| reraise | 5.0 | bluffcatch_river | 7.0 |
| spr | 5.0 | thin_value_river | 7.0 |
| stackoff | 5.5 | overbet | 7.0 |
| checkraise_flop | 5.5 | | |

난이도는 평균을 정하지 않고 낮은 학습량에서의 비현실적 고숙련 꼬리만 자른다(v2 방식 그대로).

### v5-2. 학습 도움 선행 (L, 평균 +3.0 자유 / tail 2.0)

뒤 개념이 앞 개념을 **문자 그대로 재료로 쓰는** 경우만 넣었다.

```
L  outs + fold_equity            -> semibluff        (세미블러프 = 드로우 에퀴티 + 폴드 에퀴티)
L  outs + fold_equity            -> equity_denial
L  potodds + spr                 -> stackoff
L  potodds                       -> bluffcatch_early
L  potodds + range_read          -> bluffcatch_river
L  range_read + board_texture    -> thin_value_river
L  range_read + board_texture    -> overbet          (폴라라이즈는 레인지 우위 이해가 재료)
L  potcontrol + sizing_tell      -> blockbet
```

묶지 않은 것과 이유:
- bluff, fold_equity, spr, reraise: 기초이거나 독립적으로 익힌다.
- pf_defend: pf_range 와 같은 차트 암기 계열. positional → pf_range 를 뺀 이유와 같다.
- checkraise_flop, thin_value_turn, range_merge: 관련 개념은 많지만 특정 선행 없이는 못 배운다고 보기 어렵다.

### v5-3. 필수 선행(hard) 후보 — **기본은 추가하지 않음, 사용자 판단 요청**

c벳 계열과 같은 "스트리트를 이어 가는 같은 기술"인지가 기준이다.

| 후보 | 찬성 근거 | 반대 근거 |
|---|---|---|
| checkraise_flop → checkraise_late | cbet_flop → barrel_turn 과 같은 구조(플랍 기술을 턴·리버로 확장) | 턴·리버 체크레이즈는 드로우·리버 판단이 달라 따로 익힐 수 있음 |
| bluffcatch_early → bluffcatch_river | 앞 스트리트에서 블러프캐치를 못 하면 리버까지 갈 일이 적음 | 리버만 따로 콜다운 감각이 있는 사람도 흔함 |
| outs → semibluff | 아웃을 모르면 세미블러프가 아님 | 감으로 드로우를 세게 치는 사람은 아웃을 몰라도 있음 → L 로 충분 |

### v5-4. 영향과 검증

- 기존 개념 값 생성 순서·난수는 그대로이고, 새 cap 에 걸리는 표본만 아래로 압축된다(v4 방식).
  R2 기준선은 바뀔 수 있으므로 측정 후 사용자 승인으로 다시 봉인한다.
- 검증: 모든 플레이어가 새 관계를 v4 압축 범위 안에서 만족, 선행이 높고 후행이 낮은 조합은 그대로 허용,
  1,000명 감사(개념별 평균 변화, 7점 이상 비율), cap 에 걸린 표본 비율, 행동 지문 변화.
