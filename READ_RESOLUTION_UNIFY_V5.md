# READ_RESOLUTION_UNIFY_V5

기준 integration: `b040da54a953b39a2fd5e1748ae668cfe07103f3`

## 목적

V4 SHADOW와 production `persona.read_opponent`가 같은 관찰자 능력을
각자 따로 0~1 gate로 계산하고 있었다.

둘을 따로 유지하면 앞으로 한쪽 threshold/축만 바뀌어
"로그에는 DETAIL인데 실제 판단은 frequency만 본다" 같은 의미 분리가 생긴다.

이번 단계는 **행동 변화 없는 공통화**다.

## 공통 원천

`persona.read_resolution(prof)`

반환:
- `see_freq` <- attention
- `see_line` <- range_read
- `see_size` <- sizing_tell
- `use` <- adaptability

변환은 기존 production과 V4가 공통으로 쓰던 그대로다.

```
see(v) = clamp((v - 2) / 6, 0, 1)
```

반환값은 내부 계산용 raw float이며 반올림하지 않는다.

## 소비

### production
`persona.read_opponent`가 `read_resolution`을 사용한다.

기존:
- see_freq
- see_line
- see_size
- use
계산식과 downstream 식은 바꾸지 않는다.

### SHADOW
`reads.observer_resolution_v4`가 같은 `persona.read_resolution`을 사용한다.

V4의 trait/detail access 및 표시용 mode 계산은 그대로다.

## 금지

- threshold 변경 없음
- 새로운 style 영향 없음
- coarse/trait/detail을 production에 추가 연결하지 않음
- baseline 갱신 없음
- `mode` 문자열 action 사용 없음

## 완료 조건

1. 기존 production gate 공식과 공통 helper가 exact match.
2. V4의 see_freq/see_line/see_size/apply_willingness가 helper와 일치.
3. 기존 V1/V3/V4 contracts PASS.
4. OOP/blockbet/replan PASS.
5. current regression fingerprint exact match.

