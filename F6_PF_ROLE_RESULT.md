# F-6 — 관찰자가 읽는 상대 프리플랍 역할

관측 사실과 귀속만 동결한다. 평가·튜닝 결론은 넣지 않는다.

```
base            80355c3  (integration/ui-v49-money-jump-20260920)
측정 도구        tools/pf_role_boundary.py
                tools/f6_q4c_live.py
                tools/f6_q4b_fallback.py
수정            2de8212  fix: update preflop runtime state from applied hero action
                022dc66  fix: reconstruct observed preflop role from public action log
```

## 1. 원래 가설 — 기각

> 관찰자가 상대의 비공개 플래너 의도를 `pf_seed` 에서 훔쳐본다

`pf_role` 은 `aggressor_pos` 와 `n_limpers` 두 **공개** 입력만의 함수다
(`plan.py:1437/1450/1455`). 비공개 입력이 없다.

소비 지점(`session.py:701-707`)이 실제로 쓰는 값은 3값이 아니라 2값이다 —
`{open, iso} -> 'open'`, `{defend} -> 'call'`, 그 뒤 BB 는 `'call'`.

기록 수준 대조 (pf_seed 를 가진 전 좌석, 포스트플랍 생존 무관):

```
Fixture A  fieldsim 3시드 x 8핸드 x 100엔트리     950 / 950 일치
Fixture B  tourney 히어로 10시드 x 20핸드          625 / 625 일치
합계                                          1,575 / 1,575 일치, 불일치 0
```

**정보 누출은 지지되지 않는다.** 다만 조사 중 별개의 behavioral bug 두 개가
확정됐고 E-2 / E-3 으로 분리했다.

공개 재구성기는 `(실제 적용된 프리플랍 로그, seat->pos)` 둘만 받는다.
AST guard 로 금지 이름 참조를 막고, 일부러 새게 만든 변형이 guard 에
걸리는지 음성 대조했다.

## 2. E-3 — 폴백 semantics 불일치 (측정)

`pf_seed` 가 없으면 `'open' if o == aggressor else 'call'` 로 떨어진다.
이건 `pf_role` 과 **다른 술어**이고, 그 `aggressor` 는 그 순간의 공격자라
포스트플랍 공격자일 수 있다 — `session.py:670-675` 주석이 스스로 하면 안
된다고 적어둔 경로다. 히어로는 구조적으로 기록이 없다(히어로 분기가 기록 전에
`continue`).

```
Fixture B  소비 지점 조회 586건 중 불일치 48건 (8.19%)
           폴백 조회 227건 중 48건 (21.1%)
           고유 (핸드,좌석) 79 폴백 중 16 (20.3%)
           방향 전원 internal 'call'  vs  public 'open'
           원인 전원 hero_no_seed
Fixture A  폴백 0건 (fieldsim 은 히어로가 없다)
```

### 하류 (Q4-B, 10시드 x 25핸드, 전체 결정 330)

```
Tier 1  레인지 층   소비 사이트 57,  레인지 다름 54
                   예: 186 -> 140,  51 -> 129,  200 -> 163 콤보
Tier 2  결정 층     update_plan 에 실제로 들어간 opp_range 다른 결정  54
                   plan 4 · size 2 · chips 2
```

깨끗한 인과 증거는 각 시드의 **첫 divergence** 두 건이다 (그 이전 결정은 전부
동일, 이후는 두 팔이 자연 진행으로 갈리므로 단독 인과로 읽지 않는다).

```
seed 3005  river  value_3street bet 0.742  600칩  ->  value_2street bet 0.655  500칩
seed 4242  flop   giveup        check           ->  bluff_2street check
```

## 3. E-2 — 거부된 히어로 액션이 runtime preflop state 를 오염 (측정)

`session.py:436-448` 이 적용 액션이 아니라 **첫 요청**으로
`aggressor`/`limpers`/`callers` 를 갱신했다. 포스트플랍 경로
(`session.py:641-642`)는 이미 두 번째 act 를 쓴다 — 프리플랍만 어긋나 있었다.

CONTROL/RETRY paired, 단일 핸드, 10시드. 두 팔의 차이는 "첫 제출이 불법
raise 였는가" 하나. 히어로 최종 적용 액션 동일, 첫 요청이 실제로 ValueError
였음을 `state['error']` 로 확인(주입 9건 전부, "불법인 줄 알았는데 합법" 0건).

```
수정 전   none 1 / C0 0 / C1 2 / C2 7      깨끗한 C2 6건
수정 후   none 10 / C0 0 / C1 0 / C2 0
음성 대조 CONTROL vs CONTROL 은 수정 전후 모두 exact match
```

### phantom aggressor

```
seed 3001  첫 입력 divergence (idx 3)
  CONTROL  aggressor_pos=None,  open_bb=0.0,  n_limpers=1
  RETRY    aggressor_pos='LJ',  open_bb=1.0,  n_limpers=0
```

`open_bb = 1.0` 은 현재 베팅액이 빅블라인드 그대로라는 뜻이다 — **레이즈가
없는데 공격자가 있다.** 동시에 히어로의 실제 림프가 `n_limpers` 에서 빠졌다.

뒤 봇의 실제 행동이 뒤집힌 사례:

```
seed 3001  ('raise', 4.0) -> ('3bet', 3.0)    적용 (9,'raise',800) -> (9,'raise',600)
seed 3002  ('raise', 4.0) -> ('call', 1.0)    적용 (9,'raise',800) -> (9,'call',200)
seed 3003  ('fold', 0.0)  -> ('call', 2.5)    적용 (8,'fold',0)    -> (8,'call',500)
seed 7301  ('fold', 0.0)  -> ('call', 3.0)    적용 (8,'fold',0)    -> (8,'call',600)
```

`Round.apply` 는 이 예외 경로에서 상태를 건드리지 않는다. 코드(체크 불가
`runner.py:87` / 최소 레이즈 미달 `104`, 둘 다 mutation 전에 raise)와 단위
시험(stacks/contrib/folded/allin/acted/current/min_raise/incomplete/last_idx/log
전부 변화 0) 양쪽으로 확인했다.

## 4. REPLAY 경로 — production count 제외

`session.py:469-472` 도 같은 모양(요청값으로 상태 갱신)이다. 합성으로
`pre|<seat>|0` 키를 주입하면 재현된다 — 공개 로그에 레이즈가 없는데 뒤 좌석
4/5 가 `pf_role='defend'` 로 기록됐다.

그러나 `run.recorded` 는 `session.py:931` 포스트플랍에서만 채워지므로
`pre|` 키를 만드는 production driver 가 **없다**. 따라서

- 경로 존재성만 문서화한다
- production-reachable count 에 넣지 않는다
- E 판정 근거로 쓰지 않는다

latent / dead compatibility edge 로 분리한다. REPLAY producer 가 생기면 즉시
같은 consistency bug 가 발현한다.

## 5. 수정 후 검증

```
E-2  f6_q4c_live.py --verify        전 시드 CONTROL == RETRY,
                                    ValueError 경로 9/10 시드에서 실제 발동
E-3  f6_q4b_fallback.py --verify    production role != public 인 소비 사이트 0
                                    INTERNAL/PUBLIC 결정 차이 0
     (수정 전 같은 fixture 에서 사이트 57 / plan 4 / size 2 / chips 2)
     3005 river 600->500, 4242 giveup->bluff_2street 두 사례 소멸
정상 경로  pf_seed-present 기록 수준 950/950 유지
```

## 6. 안 한 것

- C-record (같은 captured postflop input 고정 + 잘못된 pf_role 만 교체) 미측정
- 히어로 자신의 `my_r` 경로(`session.py:688-698`)는 건드리지 않았다 —
  자기 역할은 자기 기록이라 정보경계 문제가 아니다
- 두 번째 제출도 불법인 경우 `rnd.apply` 가 감싸여 있지 않다(기존 동작).
  이번 범위 밖이다
