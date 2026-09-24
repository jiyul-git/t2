# A5 blockbet control-flow fix — 검증 결과 (1~3단계)

브랜치: `claude/a5-blockbet-fix` · 수정 커밋 `951939e`
범위 문서: `A5_BLOCKBET_FIX.md` (그대로 준수)
production 변경: **없음** — `951939e` 이후 추가 수정 없음. 추가한 것은 읽기 전용 도구뿐.

---

## 1. 수정 내용 확인

`plan.py:455-457`. diff 는 **들여쓰기 + `else:` 삽입뿐**이다.
새 임계값·확률·plan 라벨 없음. `SIZING['block']`·`decide_aggression(plan=='block')`·
`_allowed` 무수정.

**부수 효과 하나**: 옛 코드는 block 선택 뒤에도 머징 체인을 평가했으므로
`sk('potcontrol') >= 1` 이면 `rng.random()` 을 한 번 더 소비했다. 수정 후에는
소비하지 않는다. 즉 block 선택 시점부터 `make_plan` 내부 RNG 스트림이 밀린다.

## 2. 제어흐름 불변식 — PASS

`python3 tools/block_trace.py --seeds 5000-5007 --jobs 1`

```
S0 포스트플랍 make_plan                 3502
S1 block_p>0 조건                        462  (13.2% of S0)
S2 eq>=pcz 분기 진입                     550  (15.7% of S0)
S3 S1 ∩ S2  ← block opportunity         153  ( 4.4% of S0)
S4 블락벳 메시지                          21  (13.7% of S3)
S5 make_plan 반환 block                   21  (100.0% of S4)   ← 불변식
S6 attach_intent 시점 block               21  (100.0% of S5)
S8 실제 벳                                15  ( 71.4% of S6)
```

**S4 == S5 == 21, 보존율 100%.** 머징 체인이 덮어쓰지 않는다.

### 2-1. S5 → S6 는 모집단이 달라 그대로 빼면 안 된다

`block_trace` 는 S5 를 make_plan 기록에서, S6 를 attach_intent 기록에서 센다
(3502 vs 4598). 병렬 실행 때 나온 22→20 을 "2건이 죽었다"로 읽으면 안 된다.

`tools/block_s6_attrib.py` 가 `(시드,핸드,pid,스트리트)` + **호출 순번**으로
조인한다. 그 키는 1:1 이 아니다 — 한 스트리트에서 make_plan 이 최대 3회 불린다.

```
S5 23  →  뒤따르는 attach_intent 없음 10  (저항 → decide_response, 또는 핸드 종료)
          matched 13 → 13 전부 block 유지, **진짜 이탈 0건**
S6 21  →  이번 스트리트 결정 13 / 이전 스트리트 이월 8 (turn 5, river 3)
```

`river_fix(thin_river)` · `_allowed` 어느 쪽으로도 빠지지 않는다.

## 3. regression — divergence 0건, 그러나 레시피가 거의 눈이 멀었다

`python3 tools/regress.py check --baseline current` → **전 시드 지문 일치**.

baseline 동결 rev `60e16d8`(2026-09-21)는 A5 수정 `951939e`(2026-09-22)보다
**앞선다**. 즉 baseline 에 수정이 없는데도 일치한다. 이유를 추정하지 않고
A/B 로 직접 쟀다 (`tools/a5_fingerprint_ab.py`).

현재 `plan.py` 에서 **A5 diff 만 역적용**한 변형을 만든다(옛 커밋 전체를
쓰면 이후 다른 모듈 변경과 안 맞는다). 역적용본이 진짜 `951939e^` 와
**실행 코드 기준 동일**함을 대조로 확인했다 — 차이는 주석 5줄뿐.
대회 간 캐시 이월(§5)이 있으므로 두 변형을 **각각 별도 프로세스**에서 돌린다.

```
              block_msg   plan_block
cur (A5 적용)      1           1
pre (역적용)       1           0        ← 옛 코드는 실제로 덮어쓴다

시드 3000~3005   지문 6/6 일치
```

**두 가지가 동시에 확정된다.**

1. **수정은 작동한다.** 같은 시드·같은 레시피에서 `plan_block` 이 0 → 1 이다.
   `A5_BLOCKBET_FIX.md` 의 진단("두 번째 체인이 세 갈래 모두 plan 을 대입하므로
   block 이 살아남는 경로가 없었다")이 실측으로 재현됐다.
2. **그런데 최종 `full_log` 는 같다.**

### 3-1. 왜 같은가 — 계측 결과

`attach_intent` 를 감싸 그 자리의 최종 의도를 잡았다.

```
cur   (attach_intent 에서 현재 스트리트 block 흔적 없음)
pre   (attach_intent 에서 현재 스트리트 block 흔적 없음)
```

**그 1건은 `attach_intent` 에 도달하지 못했다.** §2-1 의 "뒤따르는
attach_intent 없음 10건"과 같은 부류다 — 저항을 만나 `decide_response` 로
갔거나 핸드가 끝났다. 공격 경로를 타지 않으므로 `SIZING['block']` 도
`decide_aggression(plan=='block')` 도 관여하지 못한다.

### 3-2. 그래서 이 지문 일치를 "행동 보존"으로만 읽으면 안 된다

regress 레시피(entries=100, seeds 3000-3005, 30핸드, 히어로 fold)에서

```
make_plan                      323
중간강도 분기                    41
block 선택                        1      ← 전체의 0.3%
그 1건이 공격 경로에 도달           0
```

**회귀 위험이 없다는 결론은 유효하다** — baseline 대비 차이가 0이다.
동시에 **이 레시피는 A5 가 바꾼 것을 거의 측정하지 못한다.** 표본 1건이고
그 1건마저 소비처에 닿지 않는다. A5 의 행동 영향은 여기서 재면 안 된다.

## 4. 1~3단계 종합

```
수정 내용      문서 범위 그대로. 새 임계값·확률·라벨 없음
제어흐름       S4 == S5 == 21 (100%). 조인 기준 진짜 이탈 0건
회귀           divergence 0건. 귀속할 최초 divergence 자체가 없다
작동 증거      plan_block 0 → 1 (A/B, 동일 시드)
측정 한계      regress 레시피는 block 을 1건만 만들고 그마저 소비처에 닿지 않는다
```

## 5. 범위 밖에서 발견한 것 (고치지 않음, 기록만)

**`persona._TILT_VIEW_CACHE` 가 대회 간 오염을 일으킨다.**

`persona.py:605` 의 키가 `(prof['id'], round(tilt, 2))` 인데 `pid` 는
**대회마다 재사용되는 번호**다. 한 프로세스에서 두 번째 대회를 돌리면
대회 A 의 pid N 캐시가 대회 B 의 pid N(다른 사람)에게 반환될 수 있다.
`len > 4000` 에서만 비우므로 간헐적이다.

실측(새 프로세스 단일 시행):

```
seed 5002   차가운 프로세스                  480 / 628
            5000 뒤 (따뜻함)                 430 / 581
            5000 뒤 + _TILT_VIEW_CACHE 만 비움  480 / 628   ← cold 복원
            5000 뒤 + _EQ_CACHE·_RS_CACHE 만 비움 430 / 581  ← warm 유지
```

`_EQ_CACHE`(내용 기반 crc32 시드)와 `_RS_CACHE` 는 순수 메모라 원인이 아니다.
`f7e03ac` seat-key contamination 과 같은 계열이되 **대회 수준**이다.

영향: 한 프로세스에서 대회를 둘 이상 도는 모든 것.
`tools/block_trace.py --jobs 4`(워커가 여러 시드를 이어 받는다),
그리고 **`tools/regress.py fingerprint()`** — 6개 대회를 한 프로세스에서
순차 실행한다. 따라서 **시드별 지문은 서로 독립이 아니다.**

지문 재현성은 깨지지 않는다(시드 순서가 고정이고 매번 새 프로세스라
오염도 결정적으로 같다). 깨지는 것은 "시드 N 의 지문이 시드 N 만의
성질"이라는 해석이다. `CLAUDE.md` 의 `3003·3004 불일치` 귀속이 이 교락을
받는지는 **확인하지 않았다** — 추측으로 적지 않는다.

**고치지 않는다.** A5 범위 밖이고, 고치면 baseline 지문 3세대가 전부 깨진다.

### 5-1. 계측 도구는 `--jobs 1` 로 고정할 것

`block_trace --jobs 4` 는 실행마다 결과가 달라진다(첫 실행 3506/4612,
이후 3540/4682). 시드별로는 순차와 Pool 이 완전히 일치하므로 원인은
위 이월이다. **A5 판정 자체는 어느 설정에서도 같다** — 모든 실행에서
`S4 == S5`, 이탈 0건. 달라지는 것은 깔때기의 절대 건수뿐이다.

## 6. 도구

```
tools/block_trace.py          기존. 무수정
tools/block_s6_attrib.py      S5→S6 조인 귀속 (신규, 읽기 전용)
tools/regress_block_reach.py  regress 레시피의 block 도달성 (신규, 읽기 전용)
tools/a5_fingerprint_ab.py    A5 diff 역적용 A/B + 의도 계측 (신규, 읽기 전용)
```

## 7. 다음 (4단계) — 설계가 바뀌어야 한다

`A6_REPLAN_PROVENANCE_RESULT.md` 는 세 필드를 이렇게 기록했다.

```
oop_vs_aggr      mismatch 520 (64.2%)   소비처 효과 0/520
oop_legacy_abs   mismatch 810 (100.0%)  소비처 효과 0/810
initiative       mismatch 562 (69.4%)   소비처 효과 0/562
```

그리고 8-3 절이 "이 셋은 A6 만으로 무효과 판정을 내리지 않는다",
194 절이 "수정 후 재측정한다" 로 이미 유보해 두었다.

A5 검증이 바꾼 전제는 이것이다 — **세 필드가 `block_p` 를 거쳐
`plan='block'` 까지 살아남는 것은 확인됐다.** 남은 질문은
**plan → intent → 실제 행동** 구간에서 영향이 전달되는가다.

측정 조건 두 가지가 강제된다.

1. **regress 레시피를 쓰면 안 된다.** block 1건, 소비처 도달 0건이다.
   `block_trace` 규모(8시드에서 S4 21 / S8 15) 이상이 필요하다.
2. **`--jobs 1` 로 고정한다** (§5-1).

이 설계는 사용자 확인 후 진행한다.
