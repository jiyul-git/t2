# STYLE_SHADOW_V1_RESULT

기준: STYLE_MODEL_V1.md / branch `chatgpt/style-shadow-v1`

## 구현

- `reads.style_shadow(est)`
  - 입력은 `perceived_profile` 의 공개행동 추정치뿐이다.
  - 실제 상대 profile/concepts 를 읽지 않는다.
  - L(looseness) / A(aggression) / X(pressure extremeness) 계산.
  - NIT / TAG / LAG / LOOSE_PASSIVE / TIGHT_PASSIVE / MANIAC 6개 확률분포.
  - entropy 기반 certainty.
  - STICKY / OVERFOLD / BLUFFY / LIMP_HEAVY / THREEBET_HEAVY /
    BIG_SIZER / SIZE_VOLATILE modifier.
- `session.py`
  - postflop intent snapshot 에 `style_target`, `style_target_pid`,
    `style_shadow` 를 기록한다.
  - plan/range/sizing/read_opponent 입력에는 전달하지 않는다.

## 계약 검증

`tools/verify_style_shadow.py`:

- 무표본: 6개 균등분포, certainty=0.
- 전형 합성점 6종이 각각 의도한 스타일 top1.
- 확률합=1, L/A/X 및 modifier 범위 검증.
- 입력 dict mutation 0.
- 표본/확신 증가 시 q 증가.
- sticky / overfold / bluffy 방향 sanity PASS.

합성점 출력:

```
NIT             -> NIT             L 1.45 A 5.18 X 1.00 cert 0.487
TAG             -> TAG             L 3.12 A 7.85 X 1.82 cert 0.607
LAG             -> LAG             L 7.78 A 9.20 X 4.01 cert 0.635
LOOSE_PASSIVE   -> LOOSE_PASSIVE   L 8.75 A 0.51 X 1.00 cert 0.985
TIGHT_PASSIVE   -> TIGHT_PASSIVE   L 1.96 A 0.91 X 1.00 cert 0.724
MANIAC          -> MANIAC          L 8.86 A 10.00 X 9.35 cert 0.964
```

## 행동 보존 검증

GitHub Actions run `35798971834`:

- compile PASS
- style shadow contract PASS
- OOP semantics PASS
- blockbet selftest PASS
- replan current-context PASS
- current regression PASS

current regression:

```
기준선 : VPIP 19.1%  PFR 11.4%  flop 44.4%
현재   : VPIP 19.1%  PFR 11.4%  flop 44.4%
전 시드 지문 일치 — 동작 보존 확인.
```

따라서 STYLE_MODEL_V1은 현재 **SHADOW only**다.
스타일/Modifier는 기록되지만 production 의사결정에는 영향 0.

## 다음 단계

1. 실제 자연상태에서 style posterior 분포/entropy/top1 flip을 측정.
2. 앞 구간 style belief가 뒤 구간 행동을 population prior보다 잘 예측하는지 holdout 검증.
3. modifier별 분포와 상호중복 확인.
4. 그 결과를 본 뒤에만 style prior → concept 또는 exploit 연결 여부를 결정한다.
