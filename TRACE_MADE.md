# `made` 전수 추적 — 생성식·게이트·반사실 ARM 후보

**추적이다. 아직 측정하지 않았다.** `plan.py` 무수정. 기준 `37372d0`.

`pcz` 실험(`CF_RESULT_PCZ.md`)과 **관측 목적을 분리한다.**

```
pcz    분기 탈출 효과 — eq >= pcz 진입 자체를 막는다
made   분기 내부 게이트 효과 — 465 의 showdown/giveup 을 가른다
```

두 효과를 섞지 않는다. 같이 켜서 재지 않는다.

---

## 1. `made` 의 생성식 (`bot.py:259-291`)

```python
made = bot.made_strength(hero, board)      # plan.py:310
```

**반환은 `eval7` 의 정수 등급, 아니면 0 이다.** 카운트도 합도 아니다.

```
0                내 홀카드의 기여가 없다
eval7 카테고리    기여가 있다  (1 원페어 · 3 트립스 · 5 플러시 …)
```

"기여" 판정이 이 함수의 전부다.

```
board >= 5 장    full = eval7(hero+board),  board_best = eval7(board)
                 full[0] <= board_best[0]  →  0
                 킥커는 보지 않는다 — 98o 가 KK 보드에서 원페어로 잡히는 것을 막는다

board < 5 장     보드의 랭크 빈도 최대값 m 으로 board_cat 을 추정한다
                 {1:0, 2:1, 3:3, 4:7}[m],  같은 수트 5장이면 최소 5
                 full[0] <= board_cat  →  0
```

### 1-1. **드로우는 한 글자도 들어가지 않는다**

`made_strength` 는 `draw_strength` 를 부르지 않는다. 설계상 "완성 강도"
이므로 당연하다. **문제는 `465` 가 그 값 하나로 계속 여부를 가른다는 것이다.**

---

## 2. `made` 게이트 전수 (`plan.py`)

```
 90   perceived_rel   made >= 1 and rel >= 0.45   overpair_love 편향 적용 조건
317   monster         made >= 5
318   strong          made >= 3
458   value_2street   rel >= max(0.28, …) and made >= 1
465   **showdown / giveup**   plan = 'showdown' if made >= 1 else 'giveup'
491   bluff_2street   made == 0 or rel < 0.30
503   has_sd          made >= 1 or eq >= 0.42 + 0.05*mw
1546  river_fix       made >= 1                    (블러프 전환 억제)
1562  river_fix       made >= 2 or rel >= 0.62     완성 판정
1579  river_fix       made >= 1 or rel >= 0.42     쇼다운 가치 있으면 블러프 금지
1763  refresh         made <= 1
1778  refresh         made >= 2 or rel >= 0.62
1795  refresh         rel >= 0.55 or made >= 2     giveup 구제
1800  refresh         rel >= 0.72 or made >= 3
1904  target_commit   made >= 5
```

`bot.made_strength` 호출은 7곳이다 — `plan.py:310 · 314 · 669 · 1291 ·
1545 · 1559 · 1692`.

---

## 3. 이미 코드에 있는 "계속 가치" 술어

**새 임계값을 만들지 않으려면 여기서 골라야 한다.**

```
A   plan.py:503    made >= 1 or eq >= 0.42 + 0.05*mw     같은 함수 안, has_sd
B   plan.py:1579   made >= 1 or rel >= 0.42              river_fix
C   plan.py:468    outs >= 8                             semibluff 게이트
D   bot.py:296     _sd_strength = made + min(1.8, outs*0.11)
```

`D` 는 `ranges.py:161` 과 `bot.py:378` 이 **상대 레인지를 좁힐 때** 쓴다.

> 엔진은 "완성 강도 + 드로우 지분" 이 계속 가치의 옳은 척도라고 이미
> 믿고 있다. **다만 그 척도를 상대 레인지에만 적용하고 자기 계획
> 게이트에는 적용하지 않는다.**

---

## 4. `made` **값 자체**를 바꾸는 개입은 깨끗하지 않다

값을 바꾸면 2절의 15개 게이트와 `perceived_rel` · `target_commit` ·
`refresh` 의 `_prev_made` 비교까지 전부 따라 움직인다. `465` 의 효과가
분리되지 않는다 — `pcz` 때보다 해석이 어렵다.

그리고 **`_sd_strength` 를 그대로 `made` 자리에 넣을 수 없다.**

```python
def _sd_strength(combo, board):
    made = eval7(list(combo) + board)      # ← 보드 기여 차감이 없다
```

`made_strength` 가 막아 둔 것(98o 가 KK 보드에서 원페어로 잡히는 것)이
되살아난다. 차감을 얹어 합성하려면 **새 식을 쓰는 것**이고, 그것은
작업 원칙 2 위반이다.

> **결론: 새 값 없이 깨끗하게 만들 수 있는 것은 `465` 의 게이트 술어를
> 기존 술어로 교체하는 것뿐이다.**

---

## 5. ARM 후보 — `465` 의 술어만 바꾼다

`plan.py:465` 한 줄만 바꾼다. `made` 값도, `458` 도, 다른 게이트도
건드리지 않는다.

```
O       plan = 'showdown' if made >= 1 else 'giveup'          현재

ARM-S   plan = 'showdown' if (made >= 1 or eq >= 0.42 + 0.05*mw) else 'giveup'
        plan.py:503 의 has_sd 식을 **그대로** 옮긴다

ARM-R   plan = 'showdown' if (made >= 1 or rel >= 0.42) else 'giveup'
        plan.py:1579 의 술어를 **그대로** 옮긴다

ARM-D   plan = 'showdown' if (made >= 1 or outs >= 8) else 'giveup'
        plan.py:468 의 8 을 **그대로** 쓴다
```

세 팔 모두 **숫자를 새로 만들지 않았다.** 우열은 가르지 않는다.

### 5-1. `458` 을 건드리지 않는 이유

`458` 도 `made >= 1` 을 갖는다. 거기까지 바꾸면 이 핸드들이 `showdown`
이 아니라 `value_2street` 를 받게 되어 **두 개입이 겹친다.** 이번에는
`465` 만 본다.

### 5-2. 코드에서 유도되는 것 (아직 예측 등록이 아니다)

```
ARM-S 는 giveup 을 거의 없앤다.
  465 에 도달했다는 것은 eq >= pcz 를 통과했다는 뜻이고
  pcz = 0.50 + 0.06*mw + w*0.30*sg,  has_sd 문턱 = 0.42 + 0.05*mw
  차이 = 0.08 + 0.01*mw + w*0.30*sg
  → sg 가 충분히 음수가 아니면 eq >= pcz ⟹ has_sd 참이다
  **0 이 될지 '거의 0' 이 될지는 sg 가 정한다. 재야 안다**
```

이것은 `CLAUDE.md` 가 이미 적어 둔 관찰과 같다 — "진입 조건이
`eq >= pcz` 라 최종 `has_sd` 가 항상 참. 이 자리에서 giveup 은 구조적으로
나올 수 없어야 한다."

---

## 6. 다음 단계에서 잠글 것

```
비교 단위   make_plan 반환 시점 라벨. update_plan 통과 후 intent 와 섞지 않는다
            (cf_pcz 에서 이걸 틀려 한 번 폐기했다 — CF_RESULT_PCZ 0절)
스냅샷      반환 dict 를 **사본**으로 담는다
집합 정의   고정 eq 구간을 쓰지 않는다. why 문자열로 가른다
사전등록    C1~Cn 을 측정 전에 박고, 결과를 보고 고치지 않는다
분리        pcz 개입과 동시에 켜지 않는다
```
