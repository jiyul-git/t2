# HIERARCHICAL_READ_V6 — 반사실 결과

사전등록: `HIERARCHICAL_READ_V6_PREREG.md` (Amendment A1 포함).
기준 integration `2610ec9`. 측정 브랜치 `chatgpt/hierarchical-read-v6` @ `2a25b4f`
(merge-base 가 integration HEAD 라 integration 이 그대로 들어 있다).
집계 대상: Actions run **35816924409**, CF job 12개 + verify job 1개, 전부 success.

**production 무수정. LIVE 배선 없음. V6 는 SHADOW 후보 그대로 둔다.**

---

## 0. 재현 확인

12개 CF job 로그의 `V6_CF_JSON` 을 전부 받아 이 환경에서 같은 도구로 재실행해
대조했다. `control_hash` · `v6_hash` · `diff_hands` · `diff_entries` · `calls` ·
`w_positive` · bin 3개 — **12시드 전부 불일치 0**. 아래 수치는 CI 로그의 값이고,
로그에 없는 세부(핸드별 분해·채널 귀속)는 같은 것으로 확인된 로컬 재현에서 얻었다.

`read_opponent` · `hierarchical_read_v6` · `read_resolution` ·
`hierarchical_belief_v3` 는 전부 RNG 를 쓰지 않는 순수 함수다. 정적으로 확인했다.
그래서 arm 사이 차이는 **반환값으로만** 전파된다 — RNG 소비 차이는 없다.

## 1. 12시드 집계

```
engine_errors   0        (사전등록 8절 필수조건 충족)
read 호출       15,348
w > 0           11,818   (77.0%)
bin             LOW 4,137 · MID 5,640 · HIGH 5,571
diff_hands      22 / 360
diff_entries    233
```

| seed | control_hash | v6_hash | dHand | dEntry | LOW | MID | HIGH |
|---|---|---|---:|---:|---:|---:|---:|
| 850001 | 381c9a8457d6d263 | 6a935f9a43293c4b | 1 | 1 | 216 | 689 | 338 |
| 850002 | 22e1a1fd6e8b590a | 6340ad1c8a4e9718 | 1 | 1 | 476 | 335 | 506 |
| 850003 | bb47a978582d9b47 | 9a7143d2f65e26a0 | 1 | 1 | 522 | 360 | 287 |
| 850004 | 53e20024fe06f951 | = | 0 | 0 | 152 | 0 | 1120 |
| 850005 | 821c97b11ceed35d | 320aabdd864e8c78 | 1 | 3 | 523 | 415 | 324 |
| **850006** | 374f444c3970cac6 | c21de2741f4f5508 | **17** | **223** | 192 | 584 | 732 |
| 850007 | f03a49b5df61c063 | = | 0 | 0 | 444 | 886 | 0 |
| 850008 | 975261d999b58150 | 4c60ab936fc39eec | 1 | 4 | 0 | 485 | 815 |
| 850009 | 8103ae6d04843eff | = | 0 | 0 | 668 | 238 | 161 |
| 850010 | 7ae01b4d8cc9fb25 | = | 0 | 0 | 474 | 818 | 0 |
| 850011 | a88d56bdad730bb1 | = | 0 | 0 | 470 | 631 | 133 |
| 850012 | ec258081e5a052d0 | = | 0 | 0 | 0 | 199 | 1155 |

6시드는 해시 동일, 5시드는 1핸드짜리, 850006 하나만 크다.
**233개 diff entry 중 223개가 850006 하나에서 나온다.**

## 2. LOW/MID/HIGH source weight (호출수 가중, 12시드 pooled)

| bin | axis | coarse | trait | detail |
|---|---|---:|---:|---:|
| LOW | freq | 0.5670 | 0.2437 | 0.1893 |
| LOW | line | 0.8317 | 0.1393 | 0.0289 |
| LOW | size | 0.8263 | 0.1466 | 0.0271 |
| MID | freq | 0.4088 | 0.2230 | 0.3681 |
| MID | line | 0.5639 | 0.2624 | 0.1736 |
| MID | size | 0.5227 | 0.3005 | 0.1768 |
| HIGH | freq | 0.2292 | 0.1538 | 0.6169 |
| HIGH | line | 0.2025 | 0.1349 | 0.6626 |
| HIGH | size | 0.2841 | 0.2212 | 0.4947 |

사전등록 8절 대조

```
HIGH 가 detail 로 수렴한다      freq OK · line OK · size OK
LOW 에 coarse 가 남는다         freq OK · line OK · size OK
MID 의 trait 이 LOW/HIGH 보다 크다   freq **실패** (LOW 0.2437 > MID 0.2230) · line OK · size OK
```

**9칸 중 8칸이 의도대로 나오고 freq 축의 MID trait 하나가 어긋난다.**

### 2-1 어긋남의 원인은 설계가 아니라 **bin 축이 보간 축과 다르다**는 것이다

반사실 도구는 관찰자를 `observer_resolution_v4.detail_access` 로 나눈다.

```
detail_access = 0.30·see_freq + 0.45·see_line + 0.25·see_size
```

그런데 V6 의 보간 파라미터는 채널마다 다르다 — freq 는 `see_freq`, line 은
`see_line`, size 는 `see_size`. 즉 **bin 축은 see_line 이 가장 무겁다.**

같은 12시드의 봇 1,200명에서 (`tools/v6_axis_bin_check.py`):

```
corr(detail_access, see_freq) = 0.4488
corr(detail_access, see_line) = 0.8483
corr(detail_access, see_size) = 0.6455
```

여기에 `2a(1−a)` 가 오목이라, bin 안에서 a 가 넓게 퍼지면 평균 trait weight 가
bin 평균 a 에서의 값보다 크게 내려간다(Jensen). LOW 의 평균 see_freq 는 0.350
이고 그 지점의 `2a(1−a)` 는 0.455 인데 bin 내 평균은 0.303 이다.

두 효과를 합치면 모집단만으로도 freq 축의 MID trait 역전이 재현된다.

```
detail_access 로 bin      LOW freq trait 0.303  >  MID freq trait 0.292
CF 실측(호출수 가중)       LOW 0.2437          >  MID 0.2230
```

**같은 모집단을 각 채널 자신의 `a` 로 bin 하면 세 축 전부 깨끗하다.**

| bin | freq c/t/d | line c/t/d | size c/t/d |
|---|---|---|---|
| LOW | 0.749 / 0.217 / 0.034 | 0.764 / 0.204 / 0.033 | 0.717 / 0.242 / 0.041 |
| MID | 0.247 / **0.482** / 0.271 | 0.243 / **0.481** / 0.276 | 0.253 / **0.483** / 0.264 |
| HIGH | 0.025 / 0.176 / 0.800 | 0.023 / 0.161 / 0.816 | 0.029 / 0.198 / 0.773 |

**보간 자체는 의도대로 작동한다. 어긋난 것은 계측 축이다.**
사전등록 8절의 "MID trait 최대" 조건은 freq 채널에 대해 잘못된 축에서 측정됐다.
**사전등록 문서를 고치지 않는다.** 다음 판에서 bin 축을 채널별 `a` 로 바꾸는 것을
새로 등록해야 한다.

가중 합이 정확히 1인 것(같은 신호를 세 번 더하지 않는 것)은 `_style_v6_weights`
가 `(1−a)², 2a(1−a), a²` 를 그대로 내므로 구조적으로 보장된다. 위 표의 각 행
합이 1.0000 인 것으로도 확인된다.

## 3. seed 850006 — 최초 divergence 추적

도구: `tools/v6_divergence_trace.py`. CF 와 같은 harness 위에서
**채널을 하나씩 production 값으로 되돌린 arm**(필요성)과
**control 위에 채널 하나만 V6 로 올린 arm**(충분성),
그리고 `layer_sources` 로 만든 **단일층 arm**(층 귀속)을 돌린다.
arm 마다 반환값 digest 도 같이 낸다 — 로그가 같을 때 그것이 값이 같아서인지
문턱을 안 넘어서인지 가르기 위해서다.

최초 divergence

```
hand 13  entry 14
control  ['turn', 3, 'call',  8800]
v6       ['turn', 3, 'fold',     0]
```

핸드 13 은 플랍부터 seat 3 대 seat 6 헤즈업이다. entry 13 에서 seat 6 이
8,800 을 베팅하고, entry 14 가 seat 3 의 응답이다.

| arm | hands_hash | reads_digest | dHand | dEntry | control 대비 최초 divergence |
|---|---|---|---:|---:|---|
| control | 28e4bbd8aabb2ea0 | e7ca18c61e30323f | 0 | 0 | — |
| v6 | b0c0f590ec5ca2a3 | a2dcb0bf82b01a7b | 17 | 223 | h13 e14 turn |
| **v6_freq_ctl** | **28e4bbd8aabb2ea0** | ff6b1927c55f9e9a | **0** | **0** | **없음** |
| v6_line_ctl | b0c0f590ec5ca2a3 | 7f123bc48597d6ae | 17 | 223 | h13 e14 turn |
| v6_size_ctl | 5b304f5771b8807f | 7b61b44eadb303a3 | 1 | 3 | h26 e7 preflop |
| v6_wsee_ctl | b0c0f590ec5ca2a3 | **a2dcb0bf82b01a7b** | 17 | 223 | h13 e14 turn |
| v6_only_freq | bb02246f4fe5b7ec | fa12ecee7750d517 | 17 | 221 | h13 **e16 river** |
| v6_only_line | 28e4bbd8aabb2ea0 | 6e8af644fab47694 | 0 | 0 | 없음 |
| v6_only_size | bb02246f4fe5b7ec | 063c462d87c0ba26 | 17 | 221 | h13 **e16 river** |

읽는 법.

- **freq 채널을 production 값으로 되돌리면 30핸드가 control 과 비트까지 같다.**
  이 시드의 모든 divergence 에 freq 채널이 필요하다.
- **line 채널은 되돌려도 v6 와 완전히 같다.** 이 시드에서 line 은 기여 0 이다.
  control 위에 line 만 올린 arm 도 divergence 0 이다 — 필요도 충분도 아니다.
- size 채널을 되돌리면 h13 의 뒤집힘이 사라지고 h26 의 1핸드만 남는다.
  **turn 뒤집힘에는 size 도 필요하다.**
- `v6_wsee_ctl` 의 reads_digest 가 v6 와 **완전히 같다.** production 의
  `w = min(0.85, use·data)` 와 see_* 가 V6 와 동일식이라는 뜻이다 (공허검사 통과).
- 충분성 쪽을 보면 freq 만, size 만 올린 arm 은 둘 다 h13 의 **river(e16)** 를
  뒤집을 뿐 turn(e14) 은 안 뒤집는다.

**결론: entry 14 의 turn 폴드는 freq × size 의 결합 효과다.**
어느 한쪽만으로는 같은 핸드의 한 스트리트 뒤에서만 뒤집힌다.
line 은 이 시드에서 아무것도 하지 않는다.

### 3-1 층(coarse/trait/detail) 귀속 — 단일 층으로 갈리지 않는다

| arm | hands_hash | reads_digest | 최초 divergence |
|---|---|---|---|
| v6_freq_coarse | d8c9866f978a0526 | 6e69e6ad8dd4122f | h13 e14 |
| v6_freq_trait | d8c9866f978a0526 | eb586fe28d7e82d6 | h13 e14 |
| v6_freq_detail | b0c0f590ec5ca2a3 | 7a17edfe74bdd535 | h13 e14 |
| v6_size_coarse | bb02246f4fe5b7ec | 3aaab3f330e01f7e | h13 e16 |
| v6_size_trait | bb02246f4fe5b7ec | 85203c8b121b4a25 | h13 e16 |
| v6_size_detail | bb02246f4fe5b7ec | 22c82ab5ef5610d0 | h13 e16 |
| v6_coarse | 6ba9fd83fcb70976 | bda4fa67837bd153 | h13 e16 |
| v6_trait | 6ba9fd83fcb70976 | feaf8e3f9624b16c | h13 e16 |
| v6_detail | 5b304f5771b8807f | 99814239336cfe94 | h26 e7 |

freq 채널을 **어느 한 층으로 고정해도 entry 14 는 그대로 뒤집힌다.**
즉 최초 행동 변화는 **freq 채널 전체**에 귀속되고 층으로는 분해되지 않는다 —
coarse·trait·detail 세 값이 전부 production 값과 같은 방향으로 문턱을 넘긴다.

**reads_digest 가 arm 마다 전부 다른데 hands_hash 가 겹치는 칸이 많다.**
예를 들어 `v6_coarse` 와 `v6_trait` 는 반환값이 다른데 30핸드 로그가 같고,
`v6_size_{coarse,trait,detail}` 과 `v6_only_freq` · `v6_only_size` 는
digest 다섯 개가 전부 다른데 로그 해시가 하나다.
**행동 층이 read 값에 그만큼 둔감하다는 뜻이다** — 대부분의 섭동은 아무 행동도
바꾸지 않고, 바뀌는 곳은 문턱 근처의 소수 결정에 몰려 있다.
`w` 가 0.19~0.37 로 작아 read 차이가 소비처에서 더 줄어드는 것과 맞는다.

### 3-2 뒤집힌 결정의 산술 — 약한 freq 관찰자에게 coarse 가 통째로 들어간다

entry 14 를 낸 seat 3 의 그 시점 read (상대 = seat 6):

```
coarse_top   LOOSE_PASSIVE (p=0.471)   est n=14 conf=0.23   w=0.188
source_weights   freq  coarse 0.902 / trait 0.095 / detail 0.003   → see_freq ≈ 0.050
                 line  coarse 0.034 / trait 0.299 / detail 0.667   → see_line ≈ 0.816
                 size  coarse 0.340 / trait 0.486 / detail 0.174   → see_size ≈ 0.417
```

| key | 축 | coarse×w | trait×w | detail×w | V6 | production | Δ |
|---|---|---:|---:|---:|---:|---:|---:|
| passive | freq | +0.2252 | +0.0363 | +0.0009 | **+0.2623** | +0.0176 | **+0.2447** |
| open_gap | freq | +0.2213 | +0.0400 | +0.0018 | **+0.2631** | +0.0354 | **+0.2277** |
| fold_gap | freq | −0.0559 | −0.0008 | −0.0000 | −0.0568 | −0.0002 | −0.0566 |
| tb_gap | freq | −0.0254 | −0.0091 | −0.0002 | −0.0347 | −0.0041 | −0.0306 |
| size_info | size | +0.0000 | +0.1779 | +0.0651 | **+0.2430** | +0.0651 | **+0.1779** |
| size_gap | size | +0.0000 | +0.1240 | +0.1736 | +0.2976 | +0.4167 | −0.1191 |
| size_big | size | +0.0000 | +0.0620 | +0.1157 | +0.1777 | +0.2778 | −0.1001 |
| barrel_gap | line | −0.0066 | −0.1143 | −0.0964 | −0.2173 | −0.1181 | −0.0992 |

**seat 3 은 freq 를 거의 못 보는 관찰자다** (`see_freq ≈ 0.050`).
production 은 detail 신호에 `see_freq` 를 곱하므로 이런 관찰자에게 거의 0 을 준다
(`passive` +0.0176, `open_gap` +0.0354). V6 는 같은 관찰자에게 **coarse 스타일
인상을 감쇠 없이** 준다 — `passive` 의 86%(0.2252/0.2623), `open_gap` 의
84%(0.2213/0.2631)가 coarse 층에서 온다. 상대가 LOOSE_PASSIVE 라는 가설이
"수동적이고 넓게 들어온다"로 통째로 들어가고, size 쪽에서 `size_info` 가
0.0651 → 0.2430 으로 세 배 넘게 오른다. 둘이 겹쳐 turn 콜이 폴드로 바뀐다.

이것은 버그가 아니라 **설계대로 동작한 결과**다. 다만 방향이 주목할 만하다 —
계층 구조는 약한 관찰자를 "덜 읽게" 만들지 않고 **다른 것을 더 강하게 읽게** 만든다.

이 관찰자의 `detail_access` 는 0.30(0.050)+0.45(0.816)+0.25(0.417) = **0.487 →
MID bin** 이다. freq 로는 사실상 장님인데 bin 은 MID 다. 2-1 의 축 불일치가
한 사례로 그대로 드러난다.

### 3-3 223개 중 220개는 연쇄다

핸드마다 **read 를 하기 전의** 사전 상태(좌석별 스택·버튼·레벨) 서명을 남겨
비교했다.

```
divergence 가 있는 핸드            13, 14, 15, ... 29  (17개)
사전 상태가 이미 다른 핸드          14 ... 29           (16개)
divergence 가 있고 사전 상태가 같은 핸드   13 하나뿐
```

| 핸드 | diff entries | 사전 상태 |
|---|---:|---|
| 13 | 3 | **동일** — 독립 원인 |
| 14~29 | 220 | 이미 다름 — 연쇄 |

seed 850006 의 pre-state 는 핸드 13 까지 완전히 같고 **핸드 14 에서 처음 갈린다.**
핸드 13 에서 seat 3 이 8,800 을 콜 대신 폴드하면서 팟과 스택이 달라지고,
그 뒤 16핸드는 시작 상태부터 다른 게임이다.

**따라서 "17핸드/223엔트리"를 17번의 독립적인 판단 변화로 읽으면 안 된다.
독립 원인은 1건(3 entry)이고 나머지 220 entry 는 그 1건의 연쇄다.**

다른 시드도 같은 방식으로 재면, 850002·850003·850008 은 사전 상태가 30핸드
내내 한 번도 갈리지 않는다 — 뒤집힘이 그 핸드 안에서 흡수된다.
850001 은 핸드 29, 850005 는 핸드 22 에서 처음 갈린다.

## 4. 다른 divergence 시드의 채널 귀속

같은 필요성 검정(채널 하나를 production 으로 되돌리기)을 5개 시드에 더 돌렸다.

| seed | 최초 divergence | 되돌리면 사라지는 채널 | pre-state 최초 차이 |
|---|---|---|---|
| 850001 | h28 e15 river s4 call→fold | **line** | 핸드 29 |
| 850002 | h21 e3 preflop s5 raise 500→600 | **freq** | 없음 |
| 850003 | h17 e4 preflop s2 raise 500→600 | **freq** | 없음 |
| 850005 | h21 e9 flop s9 fold→call | **size** | 핸드 22 |
| 850006 | h13 e14 turn s3 call→fold | **freq**(+size 결합) | 핸드 14 |
| 850008 | h14 e13 turn s6 bet→check | **line** | 없음 |

**원인 채널이 시드마다 다르다** — freq 3건, line 2건, size 1건.
어느 한 채널이 지배적이지 않다. 850006 이 큰 이유는 원인 채널이 특별해서가
아니라 **뒤집힌 지점이 큰 팟의 중간 스트리트여서 연쇄가 길게 남았기** 때문이다.
850002·850003 은 프리플랍 레이즈 사이즈가 500→600 으로 바뀐 것뿐이라
핸드 안에서 흡수됐다.

그림: `docs/HIERARCHICAL_READ_V6.png` (`tools/draw_v6_result.py`)

## 5. 사전등록 8절 판정

| 조건 | 결과 |
|---|---|
| engine_errors = 0 | **충족** (12시드, control·v6 양쪽) |
| HIGH 가 current detail 쪽으로 수렴 | **충족** (freq 0.617 · line 0.663 · size 0.495) |
| LOW 에 coarse 가 남는다 | **충족** (freq 0.567 · line 0.832 · size 0.826) |
| MID 의 trait 이 LOW/HIGH 보다 크다 | line·size **충족**, freq **미충족** — 계측 축 불일치로 설명됨 |
| hidden target 정보 0 | **충족** — 입력은 observer 자신의 profile 과 `opp_est` 뿐, 코드에서 확인 |
| 동일 채널 합산 없이 보간 1회 | **충족** — weight 합이 구조적으로 1 |
| production current regression exact match | **충족** — verify job 의 Current regression 단계 success |

"행동 차이가 0이어도 실패는 아니다. 다만 LOW/MID/HIGH source 분리가 안 나오면
설계 실패다" 기준으로 보면, **분리는 나온다.** 9칸 중 8칸이 직접 충족하고
남은 한 칸은 잘못된 축에서 잰 것임을 모집단에서 보였다.

## 6. LIVE 승격 — 하지 않는다

사전등록 9절대로 이 결과만으로 `persona.read_opponent` 를 교체하지 않는다.
이번 단계는 EV 시험이 아니고, 아래는 전략 의미를 확인하기 전에는 판단할 수 없다.

- V6 는 **약한 관찰자의 read 를 약하게 만들지 않는다. 다른 것을 더 강하게 만든다.**
  3-2 의 seat 3 이 그 예다 — production 이 +0.018 을 주는 자리에 V6 는 +0.262 를
  준다. 이것이 "사람처럼 큰 그림으로 본다" 인지 "근거 없이 확신한다" 인지는
  행동 품질로 재야 하고, 이번 측정에는 그 축이 없다.
- 30핸드 × 12시드에서 diff hand 가 22개뿐이고 그중 16개가 한 시드의 연쇄다.
  **효과 크기를 재기에 표본이 작다.** 방향성도 아직 없다.
- 3-1 에서 행동 층이 read 값에 상당히 둔감하다는 것이 나왔다. 계층 구조를
  LIVE 로 올려도 대부분의 결정이 안 바뀔 가능성이 있다. 효과를 보려면
  어느 소비처가 문턱 근처인지부터 봐야 한다.

## 7. 재현

```
python3 tools/hierarchical_read_v6_cf.py --seed 850006
python3 tools/v6_divergence_trace.py --seed 850006 --out trace.json
python3 tools/v6_divergence_trace.py --seed 850006 --probe-hand 13 --probe-entry -1 \
        --arms control,v6 --out probe13.json
python3 tools/v6_axis_bin_check.py --seeds 850001-850012
```

`.github/workflows/hierarchical-read-v6.yml` 이 CF 를 시드 단위 matrix 로 돌린다.
추적 도구는 읽기 전용이고 `plan.py` · `persona.py` · `reads.py` 를 수정하지 않는다.
