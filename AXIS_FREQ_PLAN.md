# 성향 축 검증 ② — 빈도 축의 지표 정의서

**아직 측정하지 않았다. 코드도 고치지 않았다.** 지표를 먼저 확정하려고 쓴 문서다.

`TRACE_AXIS_ACC.md`(①)에서 두 번 틀렸다. 통계를 먼저 보고 축의 생사를
판단했다가, 코드를 읽고 나서야 도구 결함이었음이 드러났다. 그래서 ②는
순서를 뒤집는다 — **경로 추적 → 지표 확정 → 측정**.

도구 `tools/axis_sites.py` 로 사용처를 전수 추출했다. `wirecheck.py` 가
"명세한 자리에 배선됐는가"를 보는 반대편이다. 이쪽은 **실제로 어디서 읽히는가**를
전부 모은다(명세에 없는 자리 포함).

---

## 0. 세 단계를 분리한다

```
① 인식 정확도   축이 참값에 가까워지게 하는가         → TRACE_AXIS_ACC.md (완료)
② 행동 빈도     그 값이 의사결정 빈도를 바꾸는가       → 이 문서
③ 실제 의미     빈도 변화가 이름이 주장하는 방향인가,
                그리고 그 행동이 말이 되는가          → 나중
```

**①이 전부 ●라고 해서 "인식 시스템이 정상"이 아니다.** ①이 증명한 것은
각 축의 인식값 생성 경로에서 1→9 가 참값에 가까워진다는 것뿐이다.

**②에서 `bluff` 빈도가 정상으로 나와도 "블러프가 어색하다"는 해결되지 않는다.**
그건 ③이다 — 레인지·이전 베팅 라인·보드·대표 가능한 밸류 레인지의 일관성.
지금 섞지 않는다.

---

## 1. 먼저 읽어야 할 함정 넷

### (가) `make_plan` 안의 `sk()` 는 **0~3 스케일**이다

```python
plan.py:398   sk = lambda c: PS.sk(profile, c)/3.33     # 0~10 → 0~3
```

그래서 `make_plan` 안의 문턱은 전부 3.33 배로 읽어야 한다.

| 코드 | 실제 문턱 (0~10 기준) |
|---|---|
| `sk('potcontrol') >= 1` | PS.sk ≥ **3.33** |
| `sk('bluff') >= 1` | PS.sk ≥ **3.33** |
| `sk('semibluff') >= 0.4` | PS.sk ≥ **1.33** |

코드 자신이 `plan.py:453` 에 "0~10 로 착각하지 말 것"이라고 적어 뒀다.
**축을 9로 두면 `sk()` 가 2.7 이지 9 가 아니다.**

### (나) 도메인 밖에서는 축이 구조적으로 무반응이다

①의 `sizing_tell` 이 그랬다. 같은 구조가 최소 둘 더 있다.

| 축 | 코드 | 무반응이 되는 조건 |
|---|---|---|
| `multiway` | `p *= (1 − (0.12+0.20*_mw2)*max(0, n_opp−1))` (`plan.py:903`) | **`n_opp == 1` 이면 계수가 0** — 헤즈업에서 재면 반드시 0 이 나온다 |
| `fold_equity` | `if has_c and opp_est:` → `if _rdf['w'] > 0:` (`plan.py:887-892`) | **`opp_est` 가 없거나 exploit weight 가 0 이면 통째로 꺼진다** |
| `sizing_tell` | `if s <= 2.0: return s` (`persona.py:755`) | 2팟 이하 (실전 표본 전부) |

**측정 상황을 그 도메인 안에서 만들어야 한다.** 안 그러면 ①의 `blocker`
오판을 반복한다.

### (다) `bias` 경유 축은 다른 축 셋과 교락된다

`looseness` 는 **포스트플랍에 직접 읽히는 자리가 하나도 없다.** 전부 `bias` 경유다.

```python
persona.py:445   station = _z(0.45*looseness + 0.35*gamble
                              + 0.20*(10 − discipline) − 0.30*(potodds − 5))
persona.py:463   draw_love = _z(0.50*(10 − outs) + 0.35*gamble + 0.15*looseness)
```

그리고 `call_bias` 는 `max(0.0, bias(...))` 로 받는다 — **합이 중앙 아래면
0 으로 잘린다.** `looseness` 만 1↔9 로 흔들어도 `gamble`·`discipline`·`potodds`
값에 따라 양끝 모두 0 에 잘려 "무반응"으로 보일 수 있다.

→ `looseness`·`discipline` 포스트플랍 측정에서는 **교락 축 셋을 고정하고,
잘린 비율을 따로 보고한다.**

### (라) 한 축이 여러 층에 걸쳐 있다

`aggression` 은 결정 지점이 **13곳**이고 층이 다섯이다.

```
프리플랍   open_pct:393(오픈 폭)   defend_thresholds:483(방어)
계획       make_plan:306(pc, 팟컨트롤 압력)   make_plan:443(블락벳 확률)
무저항     decide_aggression:851   cbet_freq:1176   overbet_frac:1147
저항       decide_response:716,737,785   calldown_need:649(리딩 신뢰)
사이즈     decide_size:1031   checkraise_size:1873
```

**"벳 비율" 하나로 재면 안 된다.** 층마다 따로 재고, 층마다 방향을 따로 적는다.
`make_plan:306` 은 방향이 반대다 — `pc = (icm + (10−gamble) + (10−aggr))/30`
이라 aggression↑ 이면 팟컨트롤 압력이 **내려간다**.

---

## 2. 축별 경로와 지표

표기: **직접** = 그 축을 직접 읽는 자리, **간접** = `bias` 등을 경유.
고정란은 **그 축을 흔들 때 붙잡아야 할 축**이다.

### 2-1. 기질 축

| 축 | 층 | 경로 (축 → 값 → 게이트 → 행동) | 지표 | 방향 | 고정 |
|---|---|---|---|---|---|
| `aggression` | 프리플랍 | `temper` → `open_pct` 의 `direction` → 오픈 폭 | 오픈 % | ↑ | `looseness`(같은 식에 0.75 가중), `pf_range`, `positional` |
| | 계획 | `profile['aggr']` → `pc` → `_pc_p` → `pot_control` 라벨 | `pot_control` 비율 | **↓** | `icm`, `gamble`, `range_merge` |
| | 계획 | → `block_p = 0.12+0.05*aggr−0.03*bluff` → `blockbet` | 블락벳 채택률 | ↑ | `bluff` |
| | 무저항 | `decide_aggression:851` `a` / `cbet_freq:1176` | 무저항 벳 빈도 | ↑ | `bluff`, `cbet_flop`/`barrel_*` |
| | 저항 | `decide_response:716,737` `p *= (0.55+0.09*aggr)` | 저항 시 레이즈율 | ↑ | `reraise`, `stackoff` |
| | 저항 | `decide_response:785` `_p_sb *= 0.70+0.06*aggr` | 세미블러프 레이즈율 | ↑ | `semibluff`, `reraise` |
| | 사이즈 | `decide_size:1031` `base *= (0.85+0.05*aggr)` | 벳 사이즈 중앙 | ↑ | `board_texture`, `equity_denial` |
| `looseness` | 프리플랍 | `open_pct` / `defend_thresholds` / `traits_of`(limp·call·3bet) | 오픈 %, BB 방어율, VPIP | ↑ | `aggression`, `pf_range`, `pf_defend` |
| | 포스트 | **직접 없음.** `bias('station')` 0.45, `bias('draw_love')` 0.15 경유 | 저항 시 콜률 | ↑ | `gamble`, `discipline`, `potodds`, `outs` — **필수** |
| `discipline` | 프리플랍 | `traits_of` limp 항 `−0.02*(disc−5)` | 림프율 | ↓ | `looseness`, `aggression` |
| | 저항 | `decide_response:803` | 계획 이탈 콜 | ↓ | `gamble` |
| | 무저항 | `decide_aggression:866` | 계획 이탈 벳 | ↓ | `gamble` |
| | 간접 | `bias('station')` 0.20, `bias('overpair_love')` 0.30 | 위 콜률에 포함 | ↓ | (다)와 동일 |
| `gamble` | 저항·무저항 | `decide_response`/`decide_aggression`/`accum_drive`/`traits_of` | 콜·벳 빈도 | ↑ | `looseness`, `discipline` |

### 2-2. 계획 라벨 축

| 축 | 경로 | 지표 | 방향 | 주의 |
|---|---|---|---|---|
| `potcontrol` | `make_plan:456` `sk>=1` + `_pc_p` / `:504` `sk>=1` + 고정 0.72 | `pot_control` 라벨 비율 | ↑ | **확률에 축이 안 들어간다.** `_pc_p = pc*0.8+0.12+0.18*mw` 이고 축은 `>= 1` 게이트뿐 — **3.33 을 넘느냐 마느냐의 on/off** 다. 1↔9 가 아니라 **3.0 ↔ 3.6 에서 계단**이 나와야 정상 |
| `semibluff` | `make_plan:468` `outs>=8 and behind<=1 and sk>=0.4` → `p = 0.25+0.24*sk` | `semibluff` 라벨 비율 | ↑ | 진입에 `outs >= 8` 이 걸려 있다. **드로우가 있는 상황만 표본으로 쓴다.** 드로우 강도는 확률에 안 들어간다(CLAUDE.md 기록) |
| `bluff` | `make_plan:490` `eq<0.42 and sk>=1` → `(0.45+0.28*sk)` | `bluff_2street`/`river_bluff` 비율 | ↑ | `eq < 0.42` 구간만. **약한 핸드 표본**이 필요하다 |
| `trap` | `trap_judgment:218` `tool = 0.07*trap + 0.12*checkraise` → `tool<=0.05` 컷 | `trap` 라벨 비율 | ↑ | **`checkraise_*` 가 무게 1.7배다.** `trap` 만 흔들면 효과가 작게 나오는 게 정상 — 오판 금지. `slowplay_taste` 고정 필수 |
| `range_merge` | `make_plan:454` `_mg=sk` → `_pc_p *= max(0.35, 1−0.22*_mg)`, `rel` 문턱 `max(0.28, 0.52−0.080*_mg)` | `value_2street` 비율 / `pot_control` 비율 | ↑ / ↓ | 축 하나가 **두 라벨을 반대로** 민다. 둘 다 봐야 한다 |
| `stackoff` | `make_plan:429` `_p2 *= max(0.45, 1.35−0.09*sk)` | `value_3street` 비율 | ↑ (`value_2street` ↓) | `thin_value_*` 가 바로 다음 줄에서 같은 `_p2` 를 곱한다 — 고정 필수 |
| `blockbet` | `make_plan:443` + `decide_aggression` | 블락벳 채택·실행률 | ↑ | `aggression`·`bluff` 고정 |

### 2-3. 응답 축

| 축 | 경로 | 지표 | 방향 | 주의 |
|---|---|---|---|---|
| `reraise` | `decide_response` 5곳 (`:719,734,774,784,804`) | 저항 시 레이즈율 | ↑ | 밸류(719/734)·블러프(774/804)·세미블러프(784) 경로가 갈린다. **합산만 보면 안 된다** |
| `stackoff` | `decide_response:735` `so` | 콜오프율 (딥스택) | ↑ | SPR 이 낮으면 어차피 커밋 — **SPR 3 이상 표본**으로 재야 한다 |
| `bluffcatch_early/river` | `calldown_need` `trust` 안 | `need` 하락 → 콜률 | ↑ | 스트리트별 축이 다르다. 플랍·턴 = early, 리버 = river |
| `hero_call` / `station` / `bluff_fear` | `call_bias` / `decide_response` | 콜률 | ↑/↑/↓ | `bias` 경유 — (다) 적용 |

### 2-4. 실행 축

| 축 | 경로 | 지표 | 방향 | 주의 |
|---|---|---|---|---|
| `cbet_flop` / `barrel_turn` / `barrel_river` | `cbet_freq` (`street_concept('cbet', st)`) | 해당 스트리트 이니셔티브 보유 시 벳률 | ↑ | **스트리트를 틀리면 다른 축을 재게 된다.** 셋을 따로 |
| `probe` | `decide_aggression:909` `supp -= 0.020*sk` | 상대 체크백 다음 스트리트 선제율 | ↑ | **`not initiative and oop` 이고 `outs>=8` 일 때만 걸린다** — 도메인 좁다 |
| `delayed_cbet` | `decide_aggression` | 플랍 체크백 후 턴 벳률 | ↑ | 플랍을 체크백한 라인만 |
| `multiway` | `decide_aggression:903` `p *= (1−(0.12+0.20*_mw2)*(n_opp−1))` / `cbet_freq:1188` | 다인원에서의 벳률 | **↓** | **`n_opp >= 2` 필수.** 헤즈업은 구조적 0 |
| `fold_equity` | `decide_aggression:889` `p *= clamp(1+_fe*w*2.2*fold_gap)` | 잘 접는 상대 상대 블러프율 | ↑ | **`opp_est` 필수 + `w > 0` 필수.** 그리고 `fold_gap` 부호에 따라 방향이 뒤집힌다 — **잘 접는 상대/안 접는 상대를 나눠서** 재야 한다 |
| `overbet` | `overbet_frac` `p = 0.16*clamp((ob−2.5)/5)` | 사이즈 > 1.0팟 비율 | ↑ | 진입에 `plan in (value_3street, trap, bluff_2street, semibluff, river_bluff)` 와 `pol > 0.02` 게이트. **미들레인지 표본은 전부 탈락** |
| `equity_denial` | `decide_size` | 젖은 보드에서의 사이즈 | ↑ | 젖은/마른 보드를 나눠서 |
| `checkraise_flop` / `checkraise_late` | `checkraise_decision` / `trap_judgment` | 체크레이즈율 | ↑ | 스트리트별. `trap`·`slowplay_taste` 고정 |
| `thin_value_turn` / `thin_value_river` | `make_plan:431` `_p2` / `decide_aggression` / `river_fix` | 얇은 밸류 벳률, `value_3street` 비율 | ↑ | `stackoff` 와 같은 `_p2` 를 곱한다 — 서로 고정 |

---

## 3. 측정 프로토콜

축마다 아래를 **전부** 낸다. 하나라도 빠지면 ①에서 겪은 오판이 재발한다.

```
0) 도메인       그 축이 살아 있는 상황만 표본으로 쓴다 (1절 (나) 표)
                도메인 밖 표본이 섞이면 희석돼 '약한 축'으로 보인다
1) 고정         2절 '고정' 란의 축을 전부 기준값에 묶는다.
                묶지 않으면 pf_range 때처럼 단조성이 깨진다
2) 위약         plan.py 가 읽지 않는 축(tilt_swing·tilt_stack)이 0.0% 인가
3) 결정성       같은 코드 두 번 → 불일치 0건
4) 수준별       1 / 3 / 5 / 7 / 9 전부 낸다. 양끝만 보면 계단을 못 본다
                (potcontrol 은 계단이 정상이다 — 1절 (가))
5) 변화량       지표의 1 → 9 절대 변화 + 뒤집힘 비율 두 가지
                순 비율만 보면 양방향 전환이 서로 지워진다 (sizing_tell 사례)
6) 단조성       3·5·7 이 사이에 놓이는가. 안 놓이면 교락을 의심한다
```

### 판정 분류

```
● 이름값       지표가 주장 방향으로 단조 변화. 범위도 의미 있는 크기
◐ 범위 한정    특정 층·도메인에서만 작동. **범위를 명시한다**
▲ 방향 불일치  변하기는 하는데 이름이 주장하는 방향이 아니다
□ 계단         연속이 아니라 게이트 하나 (potcontrol 예상)
○ 도달 불가    코드는 맞는데 실전 표본이 도메인에 안 들어간다 (sizing_tell)
✕ 무반응       고정·도메인을 다 맞췄는데도 안 변한다
```

**`●` 하나로 뭉뚱그리지 않는다.** 예를 들어 `aggression` 이 무저항 벳은
늘리는데 저항 시 레이즈는 안 늘린다면 "정상"이 아니라
**"선제 공격에는 연결되고 저항 대응에는 약하게 연결됨"** 으로 적는다.

---

## 4. 이번 단계에서 하지 않는 것

- **코드 수정 없음.** ②는 측정 체계를 세우는 단계다
- 계수 조정 없음 — `0.09`·`0.24`·`0.22`·`3.33` 전부 그대로
- `size_river` 게이트 누락, `trust` 블록의 `dev` 는 기록만 (`CLAUDE.md`)
- 블러프 레인지·라인 일관성(③)은 시작하지 않는다

## 5. 확인이 필요한 것

측정 순서를 어디부터 갈지. 제안은 **기질 축 넷 → 계획 라벨 축 → 응답 축 →
실행 축** 이다. 기질 축이 층을 가장 많이 걸치므로, 거기서 "층별로 따로 재고
따로 적는다"는 형식을 먼저 굳히는 것이 나머지에 그대로 재사용된다.
