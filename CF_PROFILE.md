# 반사실 — 성향을 바꾸면 계획이 실제로 뒤집히는가

`tools/cf_profile.py`. 읽기 전용이다. `plan.py` 를 수정하지 않고 `make_plan` 을
그대로 부른다.

**방법**: 같은 상황·같은 seed 로 `make_plan` 을 두 번 부른다. 축 하나만
**1.0 ↔ 9.0** (척도 전체)로 놓고. 라벨이 달라지면 그 축이 그 상황에서
계획을 뒤집은 것이다.

**위약(placebo)**: `make_plan` 은 `sk(...) >= 1 and rng.random() < p` 처럼
단축평가를 쓴다. 게이트가 막히면 난수 스트림이 어긋나 축과 무관하게
라벨이 바뀔 수 있다. 그래서 `plan.py` 가 한 번도 읽지 않는 축
(`tilt_swing`, `tilt_stack`)을 같이 돌렸다.

> **위약 바닥값이 네 조건 모두 0.0% 였다.**
> 스트림 어긋남으로 인한 가짜 뒤집힘이 없다. 아래 숫자는 전부 인과다.

---

## 1. 플랍, 상대 읽기 없음 (n=400)

| 축 | 뒤집힘 | 비율 | | 가장 흔한 전환 |
|---|---|---|---|---|
| `bluff` | 72 | **18.0%** | ● | `giveup → bluff_2street` ×72 |
| `potcontrol` | 66 | **16.5%** | ● | `showdown → pot_control` ×40 |
| `semibluff` | 14 | 3.5% | △ | `giveup → semibluff` ×5 |
| `range_merge` | 13 | 3.2% | △ | `pot_control → value_2street` ×11 |
| `gamble` | 7 | 1.8% | △ | |
| `discipline` | 5 | 1.2% | △ | |
| `icm` | 4 | 1.0% | △ | |
| `stackoff` | 3 | 0.8% | △ | |
| `board_texture` | 3 | 0.8% | △ | |
| **`aggression`** | **2** | **0.5%** | △ | |
| `trap` | 2 | 0.5% | △ | |
| **`looseness`** | **0** | **0.0%** | ○ | |
| **`blocker`** | **0** | **0.0%** | ○ | |
| **`spr`** | **0** | **0.0%** | ○ | |
| `tilt_swing` (위약) | 0 | 0.0% | | |
| `tilt_stack` (위약) | 0 | 0.0% | | |

---

## 2. 턴 (n=300)

| 축 | 비율 | |
|---|---|---|
| `potcontrol` | **19.3%** | ● |
| `bluff` | **16.3%** | ● |
| **`semibluff`** | **7.7%** | ● (플랍 3.5% → 턴 7.7%) |
| `range_merge` | 4.0% | △ |
| `aggression` | 1.0% | △ |
| `looseness` / `blocker` / `spr` | 0.0% | ○ |

턴에서 `semibluff` 가 두 배로 오른다. 드로우가 실제로 계획을 가르는 자리가
턴에 몰려 있다는 뜻이다.

---

## 3. 상대 읽기가 쌓인 조건 (플랍, n=400)

| 축 | 읽기 없음 | 읽기 있음 |
|---|---|---|
| `bluff` | 18.0% | 19.0% |
| `potcontrol` | 16.5% | 16.8% |
| `range_merge` | 3.2% | 5.0% |
| `aggression` | 0.5% | 2.0% |

**거의 안 바뀐다.** `read_opponent` 로 문턱을 옮기는 경로가 라벨을
뒤집지 못한다 — `TRACE_PLAN.md` 5절에서 실측한 이동 폭 0.03 과 일치한다.

## 3-1. 읽는 능력 자체를 흔들어보면 (플랍, 읽기 있음, n=300)

| 축 | 비율 | |
|---|---|---|
| `adaptability` | 3.7% | △ |
| `range_read` | 2.0% | △ |
| `outs` | 1.7% | △ |
| `attention` | 1.3% | △ |
| `potodds` | 0.7% | △ |
| **`sizing_tell`** | **0.0%** | ○ |
| **`pf_range`** | **0.0%** | ○ |
| **`fold_equity`** | **0.0%** | ○ |

`sizing_tell` 0.0% 은 `REVIEW_2.md` 4절과 정확히 맞물린다 — 로그에서
"상대가 사이즈를 읽음" 이 0건이고 "안 읽음" 이 24건이었던 이유가 이것이다.
**그 개념은 계획을 하나도 바꾸지 않는다.**

---

## 4. 가장 중요한 것 — 두 개념이 하는 일은 하나뿐이다

살아 있는 두 축의 전환 방향을 보면:

```
bluff       72건 중 72건 (100%)  giveup   → bluff_2street
potcontrol  66건 중 40건  (61%)  showdown → pot_control
```

**둘 다 "사다리 맨 끝 `else` 블록에서 탈출시킬지"만 정한다.**
밸류 사다리(`v3`/`v2`/`pcz`) 안에서 무엇을 고를지는 거의 건드리지 못한다.

`TRACE_PLAN.md` 2절에서 그 `else` 블록이 플랍 계획의 67% 를 먹는다고
측정했다. 두 결과가 같은 것을 가리킨다 —
**성향은 "포기할까 칠까" 한 갈래에만 개입하고, "어떻게 칠까"에는 개입하지
않는다.**

---

## 5. 판정

| 축 | 판정 | 근거 |
|---|---|---|
| `bluff` | **살아 있다** | 18% 뒤집음. 단, `giveup → bluff` 한 방향뿐 |
| `potcontrol` | **살아 있다** | 17% 뒤집음. `showdown → pot_control` 위주 |
| `semibluff` | **턴에서 살아 있다** | 플랍 3.5% / 턴 7.7% |
| `range_merge` | 약하게 살아 있다 | 3~5% |
| `gamble`·`icm`·`discipline`·`stackoff`·`board_texture`·`trap` | **거의 장식** | 0.5~1.8% |
| **`aggression`** | **거의 죽어 있다** | **0.5%** (읽기 있어도 2.0%) |
| **`looseness`** | **완전히 죽어 있다** | **0.0%** — `make_plan` 안에 존재하지 않는다 |
| **`blocker`·`spr`** | **라벨에 영향 0** | 지각 보정(입력값)만 흔들고 라벨은 안 바꾼다 |
| **`sizing_tell`·`pf_range`·`fold_equity`** | **라벨에 영향 0** | |

---

## 6. 한계

- **상황이 합성이다.** 무작위 보드·홀카드에 상위 15~45% 레인지를 붙였다.
  기준 계획 분포는 `giveup 51%` / `pot_control 14%` / `value_3street 10%` 로,
  아카이브 실측(플랍 `giveup` 38%)보다 약한 쪽으로 치우쳐 있다.
  **`giveup` 이 과대표집돼 있어서, `else` 블록을 여는 축(`bluff`,
  `potcontrol`)의 비율은 실제보다 높게 나왔을 수 있다.** 방향은 바뀌지
  않지만 크기는 할인해서 볼 것.
- **라벨만 잰다.** 라벨이 같아도 사이즈·빈도는 바뀔 수 있다.
  `decide_size`·`decide_aggression` 은 여기서 안 봤다.
- **1.0 ↔ 9.0 은 최대 폭이다.** 실제 필드는 개념이 5 근처에 몰려 있어
  (`REVIEW_2.md` 6절) 실전에서 나타나는 차이는 이보다 작다.
  즉 위 숫자는 **상한**이다.

---

## 재현

```
python3 tools/cf_profile.py --n 400
python3 tools/cf_profile.py --n 400 --reads
python3 tools/cf_profile.py --n 300 --street turn
python3 tools/cf_profile.py --n 300 --reads \
    --axes attention,adaptability,range_read,sizing_tell,pf_range,fold_equity,outs,potodds
```
