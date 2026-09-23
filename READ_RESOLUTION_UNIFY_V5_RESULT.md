# READ_RESOLUTION_UNIFY_V5_RESULT

기준: `READ_RESOLUTION_UNIFY_V5.md`
브랜치: `chatgpt/read-resolution-unify-v5`

## 구현

production `persona.read_opponent`와 V4 SHADOW가 각자 따로 계산하던
관찰자 해상도 게이트를 `persona.read_resolution(prof)` 하나로 통합했다.

공통 출력:
- see_freq <- attention
- see_line <- range_read
- see_size <- sizing_tell
- use <- adaptability

변환은 기존 production/V4와 동일:

```
see(v) = clamp((v - 2) / 6, 0, 1)
```

production 수치 보존을 위해 helper는 raw float를 반환하고,
V4 SHADOW 쪽에서만 로그용으로 3자리 반올림한다.

## 행동 보존

`persona.read_opponent`의 downstream 계산식은 바꾸지 않았다.

변경 전 직접 계산:
- attention -> see_freq
- range_read -> see_line
- sizing_tell -> see_size
- adaptability -> use

변경 후:
- 같은 네 값을 `read_resolution()`에서 받음

즉 의미 공통화만 하고 exploit strength/threshold는 바꾸지 않았다.

## 검증

GitHub Actions run `35809574210` 전부 PASS.

- shared read resolution contract
- observer depth v4 contract
- hierarchy v3 contract
- style v1 contract
- OOP semantics
- blockbet selftest
- replan context
- current regression

shared contract:
```
READ_RESOLUTION_UNIFY_V5 contract: PASS
grid_cases=1375
```

경계값 포함 1,375개 조합에서 기존 production 식과 helper가 exact match.

current regression:
```
기준선 : VPIP 19.1%  PFR 11.4%  flop 44.4%
현재   : VPIP 19.1%  PFR 11.4%  flop 44.4%
전 시드 지문 일치 — 동작 보존 확인.
```

## 현재 의미

이제 "약한 봇은 coarse 위주, 강한 봇은 detail까지"라는 V4 해상도와
실제 production의 frequency/line/size exploit 능력이 같은 관찰자 능력 원천을 쓴다.

단, coarse/trait/detail 자체를 production action에 새로 연결한 것은 아니다.

다음 단계는 이 공통 해상도를 이용해
coarse / trait / detail 정보를 어떤 비중으로 실제 판단에 섞을지
별도 사전등록하는 것이다.
