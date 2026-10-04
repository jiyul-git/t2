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
그 뒤 `apply_concept_prerequisites()`에서 deterministic cap만 적용한다.

따라서:
- RNG 소비량 불변
- latent 생성 불변
- 원래 raw 분포는 유지
- 선후행 위반 표본만 아래로 보정

## 검증

1. 모든 생성 플레이어가 hard prerequisite를 만족해야 한다.
2. 선행이 높은데 후행이 낮은 조합은 그대로 허용해야 한다.
3. 같은 seed에서 난수 소비 순서는 바뀌지 않아야 한다.
4. 필터 적용 전/후 concept 분포 변화량을 별도로 측정한다.

## 다음 단계 — 아직 구현하지 않음

기초 판단지식의 출현 빈도/분포를 개념 난이도에 따라 재설계한다.

현재는 각 concept이 서로 다른 `base`, `SPREAD`, latent loading을 이미 갖지만,
'기초 판단지식일수록 후행 전략의 기반이 된다'는 구조적 중요도가 population prior에
직접 반영되지는 않는다.

다음 단계에서는:
- 기초 판단 / 후행 활용을 구분
- 각 개념 난이도 정의
- 난이도에 따른 base/spread 또는 습득확률 설계
- prerequisite filter와 중복 효과가 생기지 않는지 모집단 audit

을 먼저 설계한 뒤 수치를 조정한다.
