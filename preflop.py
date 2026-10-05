import json, os, random, threading, zlib
import persona as PS
import depth as _DP
import icm as _ICM
D = os.path.dirname(os.path.abspath(__file__))
PCT = json.load(open(os.path.join(D, 'pf_rank.json'), encoding='utf-8'))
RV = {r: i+2 for i, r in enumerate("23456789TJQKA")}

def cls(c):
    v = sorted([c[0][0], c[1][0]], key=lambda x: -RV[x])
    if c[0][0] == c[1][0]: return v[0]+v[1]
    return v[0]+v[1]+('s' if c[0][1] == c[1][1] else 'o')

def legacy_preflop_order_percentile(c):
    """Compatibility ordering, NOT decision-family equity or EV.

    RFI/defend/reraise/calloff and reconstruction currently share this table.
    Their separate policies must not be mistaken for independent solved priors.
    """
    return PCT[cls(c)]


def pct(c):
    """Compatibility API for existing tools and recorded diagnostics."""
    return legacy_preflop_order_percentile(c)

# ---------- 아키타입 ----------
import archetypes as A
import persona as PS

BASE_OPEN = {n: A.open_range(n) for n in A.all_names()}   # 구형 호환
TRAITS    = {n: A.traits(n)     for n in A.all_names()}

def _open(prof, pos, seats=8, bb=100.0, ante=True):
    """오픈 폭. 깊이·안테·좌석수가 이미 반영된 값을 돌려준다.

    깊이는 gto.rfi 안에서 한 번만 적용된다. 호출부에서 깊이 배수를 또 곱하지 말 것.
    """
    if isinstance(prof, dict):
        if prof.get('concepts'):
            return PS.open_pct(prof, pos, seats, bb, ante)
        prof = prof.get('type', 'TAG')
    import gto as _G
    lab = BASE_OPEN.get(prof, BASE_OPEN['TAG']).get(pos, 0.2)
    ref = _G.rfi(pos, seats, 100.0, True) or 0.2
    return max(0.02, min(0.92, _G.rfi(pos, seats, bb, ante) * (lab/ref)))

def _tr(prof):
    """프로필 dict(개념 벡터 우선) 또는 라벨 문자열 둘 다 받는다."""
    if isinstance(prof, dict):
        if prof.get('concepts'): return PS.traits_of(prof)
        prof = prof.get('type', 'TAG')
    return TRAITS.get(prof, TRAITS['TAG'])

import math
def _saturate(tp_raw, tot_raw, ceiling=0.80, scale=0.55):
    """곱셈 모델이 100%를 넘지 않도록 포화시킨다."""
    if tot_raw <= 0: return 0.0, 0.0
    tot = ceiling * (1 - math.exp(-tot_raw/scale))
    return tot * (tp_raw/tot_raw), tot

OPENER_MULT = {'UTG':1.4,'UTG+1':1.5,'UTG+2':1.65,'LJ':1.8,'HJ':2.2,'CO':2.9,'BTN':4.2,'SB':4.6}
# 같은 표가 두 질문에 쓰인다(ledger L-RA12, 과적재). 값을 나누는 것은 행동 변화라
# 표는 공유하고 질문별 이름만 둔다.
#   RESHOVE_OPENER_ATTACK     리쇼브 폭: 오프너 위치가 늦을수록 리쇼브를 넓힌다
#   OPEN_SHOVE_BEHIND_PROXY   오픈쇼브 판단 깊이: 앞자리일수록 뒤 인원이 많다는 대용
RESHOVE_OPENER_ATTACK = OPENER_MULT
OPEN_SHOVE_BEHIND_PROXY = OPENER_MULT

# ---------- 스택 뎁스 ----------
def feel_of(prof, bb, field_avg_bb=None, erosion=0.0, field_q=0.6, bf=1.0):
    """깊이 인식 0~1. 프리플랍의 모든 깊이 판단이 여기를 지난다.

    depth_band 계단(8/15/25/60)을 대체한다. 사람마다 다르고 연속이다.
    prof 가 없으면 기준 곡선만 쓴다(정체 불명 상대의 스택을 볼 때).
    """
    if not prof or not prof.get('concepts'):
        return _DP.base_feel(bb)
    return _DP.depth_feel(bb, prof, field_avg_bb, erosion,
                          PS.sk, PS.temper,
                          PS.perceived_edge(prof, field_q),
                          PS.icm_press(prof, bf))



# depth_band 는 제거했다. feel_of / depth.base_feel 이 대체했다.
# (stage9 B5: 읽는 곳이 없던 DEPTH_OPEN_MULT / DEF_POS_MULT 표 제거, L-RA14)

def round_unit_bb(bb_chips):
    """호가 단위를 bb 로 환산. 사람은 33,920 을 부르지 않는다.

    BB 크기에 비례한 자릿수를 쓴다.
      BB 200 -> 100 단위,  BB 1,000 -> 500 단위,  BB 5,000 -> 1,000 단위
    별도 기질 축을 만들지 않는다 — 대부분이 라운드값으로 부르기 때문이다.
    갈리는 것은 '하느냐'가 아니라 '얼마나 딱 맞추느냐'이고, 그것은
    consistency 가 정한다.
    """
    b = max(1.0, float(bb_chips or 1.0))
    if b < 400:     u = b/2.0
    elif b < 2000:  u = b/2.0
    elif b < 20000: u = b/5.0
    else:           u = b/5.0
    return max(0.05, u/b)          # bb 단위 호가


def open_size_bb(feel, pos, rng, prof=None, ante=True, n_limpers=0,
                 bb_chips=None, table_soft=0.0):
    """오픈 사이즈(bb). 축이 셋이다.

    사이즈    상황에 맞는 값을 아는가 (open_size 개념)
    일관성    매번 같은 사이즈를 치는가 (consistency 기질)
    반올림    호가 단위에 맞추는가 (위와 같은 기질이 강도만 정함)

    기준값 (공개 자료)
      온라인 2~2.5bb / 라이브 3~4bb / 안테 전 2.5bb / 안테 후 2~2.2bb
      SB 3bb (포스트플랍 항상 OOP) / 림퍼당 +1bb
      깊을수록 크게 — 임플라이드 오즈가 커져 루즈 콜이 유도되므로 상쇄한다
      안테가 있으면 작게 — 죽은 돈이 이미 있어 스틸 이득이 크다

    **콜러를 줄이려고 크게 친다**는 심리는 정식 논리다. 다만 조건이 붙는다 —
    사이에 앉은 사람들이 레크리에이셔널이라 큰 레이즈에 실제로 좁혀줄 때만
    유효하다. 같은 레인지로 3벳하는 상대에겐 오히려 작게 치는 게 낫다.
    그래서 table_soft(뒤 사람들이 얼마나 물렁한가)가 곱해진다.
    """
    # --- 기준 ---
    base = 2.5 if not ante else 2.15
    base += 0.35 * max(0.0, feel - 0.40)      # 깊을수록 크게
    if pos == 'SB':
        base += 0.6                            # 항상 OOP 라 싸게 주면 안 된다
    base += 1.0 * max(0, int(n_limpers or 0))  # 림퍼당 +1bb

    if prof is None or not prof.get('concepts'):
        return round(max(2.0, min(6.0, base)), 2)

    acc = 0.10 + 0.80*min(1.0, PS.sk(prof, 'open_size')/8.0)
    cons = PS.temper(prof, 'consistency', 5.0)/10.0

    # --- 멀티웨이 회피 ---
    # 개념이 낮은데 핸드가 강하면 "콜러를 줄이려고" 크게 친다.
    # 아는 사람은 사이즈로 레인지를 노출하지 않으려고 이러지 않는다.
    lean = (1.0 - acc) * max(0.0, table_soft)
    base *= 1.0 + 0.55*lean

    # --- 일관성 ---
    # 개념도 낮고 일관성도 낮으면 사이즈가 천차만별이 된다.
    # 이것은 버그가 아니라 재현해야 할 현상이다 — 관찰자에게 정보를 준다
    # (size_info 축이 그 전제 위에 있다).
    spread = (1.0 - acc)*0.55 + (1.0 - cons)*0.45
    if spread > 0.02:
        base *= 1.0 + rng.uniform(-0.42, 0.42)*spread

    v = max(1.8, min(6.5, base))

    # --- 반올림 ---
    if bb_chips:
        u = round_unit_bb(bb_chips)
        snapped = round(v/u)*u
        # 일관성이 높을수록 호가에 딱 맞춘다. 낮으면 어중간한 값이 남는다.
        v = v + (snapped - v)*(0.35 + 0.65*cons)
    return round(max(1.8, min(6.5, v)), 2)

def crude_edge(prof):
    """밴드로 생각하는 사람의 '짧다' 기준선. feel 단위.

    전원 공통 문턱(feel<0.20)을 쓰면 그 폴백 자체가 계단이 되어,
    깊이를 잘 아는 사람의 곡선에도 튐이 남는다(26bb 27% -> 30bb 0%).
    실제로 밴드로 생각하는 사람들도 각자 다른 선을 갖고 있다 —
    '20bb 밑이면 쇼브'인 사람과 '25bb 밑'인 사람이 다르다.
    도박성이 높을수록 그 선이 위로 올라간다.
    """
    g = PS.temper(prof, 'gamble', 5.0) if prof else 5.0
    return 0.13 + 0.014*g          # gamble 0 -> 0.13, 10 -> 0.27


def limp_theory_knowledge(prof):
    """숏스택 이론형 림프를 아는 정도 0.10~0.90 (개념 벡터 없으면 0.5).

    의미 이름은 limp_theory. 전용 prior 가 없어 기존 생성 프로필은 RFI 차트
    기억(pf_range)으로 fallback 한다(ALIAS, ledger L064 — 공급 공유 유지, 값 동일).
    limp_p 호출부는 seats/bb/ante 를 넘기지 않아 condition match 를 잴 수 없으므로
    knowledge 만 쓴다.
    """
    return PS.concept_knowledge(prof, 'limp_theory') if prof.get('concepts') else 0.5


def theory_limp_hand(hand):
    """숏스택 이론형 림프 레인지: 22-88, A2s-A8s (아래 limp_p 설명의 정의)."""
    if not hand or len(hand) != 2:
        return False
    rv = '23456789TJQKA'
    a, b = hand[0], hand[1]
    ra, rb = rv.index(a[0]) + 2, rv.index(b[0]) + 2
    if ra == rb:
        return 2 <= ra <= 8
    suited = a[1] == b[1]
    hi, lo = max(ra, rb), min(ra, rb)
    return suited and hi == 14 and 2 <= lo <= 8


def limp_p(prof, feel, hand_pct, pos, traits=None, hand=None):
    """오픈 림프 확률. **동기가 둘이고 방향이 반대다.**

    이론적 림프 — 얕을 때만. 20bb 아래에서 성립한다.
      상대가 내 림프 위로 쇼브해도 오픈레이즈 위로 쇼브하는 것보다 덜 벌고,
      내가 쇼브당해 접어도 덜 잃는다. 레인지는 좁다(22-88, A2s-A8s 계열).
      소수만 한다. pf_range 가 높아야 나온다.

    습관적 림프 — 깊이 무관. 라이브 저스테이크의 임플라이드 오즈 심리.
      "싸게 보고 트립스 이상 맞으면 스택을 딴다". 넓고 약한 핸드 위주.
      pf_range 가 낮을수록 크다.

    예전 코드는 `feel >= 0.20`(28bb 이상)에서만 림프했다. 이론적 림프를
    막고 습관적 림프만 남긴 셈인데, 이론과 정반대 방향이다.
    """
    t = traits or _tr(prof)
    acc = limp_theory_knowledge(prof)

    # --- 이론적 림프 ---
    # feel 0.12(=20bb) 아래에서만. 얕을수록 커진다.
    theory = max(0.0, min(1.0, (0.12 - feel) / 0.12))
    # 레인지가 좁다. 프리미엄도 최약체도 아니다 — 정의 밖의 손은 0 이다.
    # 예전에는 손 순위 3~30% 구간을 대용으로 쓰고 구간 밖에도 0.15 를 남겨,
    # 최고 숙련이 UTG 에서 84o·J2o·KK 를 이론 림프했다(베타 A).
    if hand is not None:
        if not theory_limp_hand(hand):
            theory = 0.0
    elif hand_pct <= 0.03 or hand_pct > 0.30:
        theory = 0.0
    theory *= acc * 0.42        # 아는 사람만 한다

    # --- 습관적 림프 ---
    habit = t['limp'] * (1.0 - acc) * 2.2
    if hand_pct <= 0.05:   habit *= 0.10     # 프리미엄은 거의 림프 안 한다
    elif hand_pct <= 0.12: habit *= 0.30
    elif hand_pct <= 0.25: habit *= 0.85
    else:                  habit *= 1.45     # 약할수록 림프 선호
    # 아주 얕으면 습관형도 림프 대신 쇼브/폴드로 간다
    habit *= min(1.0, feel / 0.10) if feel < 0.10 else 1.0

    return max(0.0, min(0.85, 1.0 - (1.0-min(1.0, theory))*(1.0-min(1.0, habit))))


def open_form(prof, feel, hand_pct, bb, rng, vs=0.0, traits=None, eff_bb=None,
              pos=None):
    """오픈을 레이즈로 칠지 쇼브할지 — 형태를 정하는 유일한 지점.

    예전에는 두 곳이 같은 질문에 각자 답했다.
      should_shove   25bb 미만. `bb<12`, `bb<22`, `hand_pct<=0.55` 계단
      분산추구 쇼브   25~60bb. band == 'normal' 창
    스택 25bb 를 경계로 서로 다른 함수가 오픈 형태를 정했고,
    그 경계에서 사람이 갑자기 바뀌었다.
    3벳 쪽에서 raise_form 으로 합친 것과 같은 정리다.

    두 항을 더한다. 이유가 다르므로 지우지 않고 합치기만 한다.
      구조항  스택이 얕아서 쇼브. 정상 플레이
      성향항  사람이 그래서 쇼브. 의도적으로 나쁜 플레이(분산 추구)
    핸드 대역도 반대다 — 구조항은 중간 핸드에서 최대, 성향항은 강할수록 크다.

    반환: ('shove', bb) 또는 (None, 0) — 후자면 일반 오픈으로 간다.
    """
    t = traits or {}
    # ---------- 구조항 ----------
    # feel 0(극단 숏) -> 1.0, feel 0.22 이상 -> 0. 연속이다.
    struct = max(0.0, min(1.0, (0.22 - feel) / 0.22))
    # 기하를 계산하는 사람(aware)의 구조항은 **뒤 사람과의 유효 스택**으로 잰다.
    # feel 은 필드 평균 대비 체감이 섞여 있어, 평균 50~60bb 필드에서 32.5bb 가
    # 체감 0.18 → 오픈 쇼브 구간이 됐다(audit9 HAND 49: BTN 87o 32.5bb 오픈
    # 올인). 쇼브 리스크/이득은 실제로 콜할 수 있는 스택이 정한다. 체감은
    # 계산을 못 하는 사람(crude) 경로에 그대로 남는다.
    struct_aware = struct
    if eff_bb is not None:
        # 뒤에 남은 사람이 많을수록 쇼브의 폴드에쿼티가 곱으로 줄고 콜당할
        # 확률이 커진다. 같은 21bb 라도 UTG 쇼브와 BTN 쇼브는 다른 판단이다
        # (audit9 HAND 81: UTG JTs 21.3bb 오픈 올인, 구조항 38% — 포지션 무관).
        # 필드가 이 오프너를 얼마나 공격하는가는 reshove_range 의 pos_mult
        # (OPENER_MULT/2.6)가 이미 정의한다. 같은 양을 써서 앞 포지션의
        # 쇼브 판단 깊이를 늘린다. 늦은 포지션은 기존 곡선을 유지한다(≥1 클립).
        _pos_depth = 1.0
        if pos in OPEN_SHOVE_BEHIND_PROXY:
            _pos_depth = max(1.0, 2.6 / OPEN_SHOVE_BEHIND_PROXY[pos]) ** 0.5
        struct_aware = max(0.0, min(1.0,
                                    (0.22 - _DP.base_feel(eff_bb*_pos_depth))
                                    / 0.22))
    # 폴드에쿼티가 전부인 대역에서 최대. 프리미엄은 작게 올려 액션을 받는 게 낫다.
    if hand_pct <= 0.06:   shape = 0.45
    elif hand_pct <= 0.55: shape = 1.00
    else:                  shape = 0.30
    p_struct = struct * shape
    p_struct_aware = struct_aware * shape

    # ---------- 성향항 ----------
    # 강할수록 크다. 구조항과 반대 방향이다.
    p_vs = 0.0
    if vs > 0.12 and feel < 0.90:
        p_vs = vs * (0.22 if hand_pct <= 0.10
                     else 0.12 if hand_pct <= 0.25 else 0.05)

    # ---------- 개념 게이트 ----------
    # 스택 깊이를 못 읽는 사람은 구조 판단을 못 한다. 예전 계단으로 물러난다.
    aware = 1.0
    if prof and prof.get('concepts'):
        aware = max(0.0, min(1.0, (PS.sk(prof, 'spr') - 2.0) / 6.0))
    # crude 는 예전에 `feel < edge` 의 0/1 계단이었다. struct 를 연속으로
    # 만들어놓고 여기서 다시 계단을 넣은 셈이라, SPR 개념이 낮은 사람은
    # **27bb 78% → 28bb 1.5%** 로 1bb 차이에 78%p 가 사라졌다.
    # 경계 폭(edge 의 40%)에 걸쳐 부드럽게 넘긴다. 이 시뮬레이터의 원칙은
    # 'BB 절대값 계단이 아니라 연속 함수'다 — 그 원칙이 여기만 빠져 있었다.
    _edge = crude_edge(prof)
    _w = max(1e-6, 0.40*_edge)
    crude = max(0.0, min(1.0, (_edge + _w - feel) / (2.0*_w)))
    p_struct = crude*(1.0 - aware) + p_struct_aware*aware

    p = 1.0 - (1.0 - min(1.0, p_struct)) * (1.0 - min(1.0, p_vs))
    if rng.random() < max(0.0, min(1.0, p)):
        return ('shove', bb)
    return (None, 0)


def table_pressure(behind_reads):
    """뒤에 남은 사람들이 오픈 폭에 주는 압력. 배수 1.0 기준.

    예전에는 open_decision 이 상대 정보를 **전혀 받지 않았다.**
    뒤에 3벳 머신이 앉아 있어도 같은 폭으로 열었다.
    뒤 스택(behind_stacks)은 넘어가는데 뒤 사람의 성향은 안 넘어갔다.

    두 방향이 있다.
      3벳을 많이 하는 사람이 뒤에 있다 -> 좁힌다
      블라인드가 잘 접는다             -> 넓힌다(스틸)
    """
    if not behind_reads:
        return 1.0
    live = [r for r in behind_reads if r and r.get('w', 0) > 0]
    if not live:
        return 1.0
    # **평균이 아니라 최댓값이다.** 뒤에 3벳 머신이 한 명만 있어도 좁혀야 한다.
    # 평균을 내면 나머지 대여섯 명이 그 신호를 씻어내서 배수가 0.96~1.03 에
    # 머문다(실제로 그랬다).
    threat = max((r['w'] * (max(0.0, r.get('tb_gap', 0.0))
                            + 0.35*max(0.0, r.get('open_gap', 0.0)))
                  for r in live), default=0.0)
    # 스틸 여지는 반대로 전원이 접어야 생긴다. 이쪽은 최솟값을 본다.
    steal = min((r['w'] * max(0.0, r.get('fold_gap', 0.0)) for r in live), default=0.0)
    return max(0.55, min(1.45, 1.0 - 0.85*threat + 0.70*steal))


def open_entry_threshold(prof, pos, bb, seats, ante, feel, traits,
                         behind_reads, behind_stacks):
    """첫 진입(RFI) 레이즈 레인지 폭 — 판단(JUDGMENT) 층.

    기준 폭(gto.rfi × 성향, `_open`) × 뒤 사람 성향 압력 × 뒤 리쇼브 스택 압력,
    짧으면 성향 쇼브 몫을 더한다. 깊이 배수는 `_open` 안(gto.rfi)에서 한 번만.
    형태(레이즈/쇼브)와 사이즈는 별도 함수가 정한다(ledger L067).
    """
    # 뒤 사람의 성향(3벳 위협)과 스택(리쇼브 위협)은 다른 압력이다.
    # 후자는 hotzone_pressure 가 재는데 호출부가 없어 죽어 있었다.
    thr = (_open(prof, pos, seats, bb, ante)
           * table_pressure(behind_reads)
           * hotzone_pressure(prof, pos, bb, behind_stacks or []))
    return min(0.9, thr + traits['shove_add'] if feel < 0.20 else thr)


def apply_money_open_threshold(thr, hand_pct, money_open):
    """머니점프 첫 행동 개입을 진입 폭에 곱하고 반사실(머니점프가 없었다면)을 기록.

    기준 레인지를 새로 만들지 않고 기존 open threshold 에 연속 factor 만 곱한다.
    진입 여부가 threshold 하나로 결정되므로 RNG 재생 없이 widen_entry /
    narrow_fold 를 판정한다. money_open 이 없으면 thr 를 그대로 돌려준다.
    """
    _base_thr = thr
    if money_open:
        try:
            thr *= max(0.0, float(money_open.get('range_factor', 1.0)))
        except (TypeError, ValueError):
            pass
        thr = max(0.0, min(0.9, thr))
        money_open['base_threshold'] = round(_base_thr, 6)
        money_open['money_threshold'] = round(thr, 6)
        money_open['hand_pct'] = round(hand_pct, 6)
        _base_in = (hand_pct <= _base_thr)
        _money_in = (hand_pct <= thr)
        money_open['range_cf'] = (
            'widen_entry' if (not _base_in and _money_in) else
            'narrow_fold' if (_base_in and not _money_in) else
            'unchanged')
    return thr


# ---------- 시간 모델용 결정 경계 기록(관측 전용) ----------
# 행위자 결정 함수가 실제로 비교한 경계를 남긴다. RNG·행동과 무관하다.
# preflop_plan 이 결정 직전에 비우고 직후에 가져가 plan seed 의 pf_timing 으로 싣는다.
_TIMING = threading.local()


def _timing_bound(d):
    _TIMING.bound = d


def take_timing_bound():
    d = getattr(_TIMING, 'bound', None)
    _TIMING.bound = None
    return d


def open_decision(prof, pos, bb, hand, rng, behind_stacks=None,
                  tilt=0.0, field_q=0.6, bf=1.0, seats=8, ante=True,
                  field_avg_bb=None, erosion=0.0,
                  payout_flat=0.0, reentry=False, progress=0.0,
                  behind_reads=None, bb_chips=None, money_open=None):
    feel = feel_of(prof, bb, field_avg_bb, erosion, field_q, bf)
    t = _tr(prof)
    # 분산 추구: 실력 열세를 자각한 사람(또는 틸트난 사람)은 딥스택에서도
    # 프리플랍 쇼브로 갈 수 있다. 이것은 open_form 의 **계획 선택** 입력이다.
    # P3/P4의 defend_decision 에 있던 variance_seek 는 dead value 였지만,
    # 여기 값은 실제로 open_form(vs=...) 이 소비한다. 제거하면 NameError가 난다.
    # V2 기준으로도 emotion이 PLAN 선택에 들어가는 위치 자체는 맞다.
    # (단, profile 자체가 tilted_view 인 전역 문제는 별도 리팩터링 대상.)
    vs = (PS.variance_seek(prof, tilt, field_q, bb, bf,
                           payout_flat, reentry, progress)
          if prof.get('concepts') else 0.0)
    # 깊이 배수는 _open 안(gto.rfi)에서 이미 적용된다. 여기서 또 곱하면 이중이다.
    thr = open_entry_threshold(prof, pos, bb, seats, ante, feel, t,
                               behind_reads, behind_stacks)
    r = legacy_preflop_order_percentile(hand)
    thr = apply_money_open_threshold(thr, r, money_open)
    _timing_bound({'kind': 'open', 'r': float(r), 'thr': float(thr)})
    _in_raise_range = (r <= thr)
    # 쇼브 판정은 **raise/open range 안**에서 먼저다. 10bb 에서 림프를 먼저
    # 물으면 쇼브해야 할 자리에서 림프가 나온다.
    if _in_raise_range:
        _eff = None
        if behind_stacks:
            try:
                _eff = min(float(bb), max(float(x) for x in behind_stacks))
            except (TypeError, ValueError):
                _eff = None
        act, amt = open_form(prof, feel, r, bb, rng, vs, t, eff_bb=_eff,
                             pos=pos)
        if act: return (act, amt)

    # limp_p 자체는 "이론형은 좁고, 습관형은 약한 핸드에서 넓다"고 설계돼 있다.
    # 그런데 예전에는 r>thr 를 여기보다 먼저 fold 시켜서, 약한 핸드일수록
    # limp 확률을 높인 habit 분기가 사실상 도달 불가능했다.
    # SB complete도 포커의 정상 선택지인데 pos!='SB'로 전역 차단돼 있었다.
    _base_limp_p = limp_p(prof, feel, r, pos, t, hand=hand)
    _limp_roll = rng.random()
    if money_open is not None:
        _pull = max(0.0, min(1.0, float(money_open.get('limp_pull_shadow', 0.0))))
        _limp_shadow = 1.0 - (1.0 - _base_limp_p) * (1.0 - _pull)
        _limp_shadow = max(0.0, min(1.0, _limp_shadow))
        money_open['base_limp_p'] = round(_base_limp_p, 6)
        money_open['money_limp_p_shadow'] = round(_limp_shadow, 6)
        money_open['limp_roll'] = round(_limp_roll, 6)
        money_open['limp_cf'] = (
            'add_limp' if (_limp_roll >= _base_limp_p and
                           _limp_roll < _limp_shadow) else
            'base_limp' if _limp_roll < _base_limp_p else
            'unchanged_raise')
        money_open['sb_limp_currently_blocked'] = False

    if _limp_roll < _base_limp_p:
        return ('limp', 1.0)
    if not _in_raise_range:
        return ('fold', 0)

    # 뒤 사람들이 물렁할수록(잘 접고 수동적) 큰 사이즈가 실제로 통한다.
    _soft = 0.0
    if behind_reads:
        _bl = [r for r in behind_reads if r and r.get('w', 0) > 0]
        if _bl:
            _soft = min(1.0, max(0.0, sum(r['w']*(0.6*max(0.0, r.get('fold_gap', 0.0))
                                                  + 0.4*max(0.0, r.get('passive', 0.0)))
                                          for r in _bl)/len(_bl)))
    sz = open_size_bb(feel, pos, rng, prof, ante, 0,
                      bb_chips=bb_chips, table_soft=_soft)
    if money_open is not None:
        # open_size_bb()는 사이즈 습관(persona.shape_size)과 규칙상 최소레이즈 적용 전 값이다.
        # 실제 sizing shadow는 session에서 최종 적용 금액을 본 뒤 계산한다.
        money_open['raw_open_size_bb'] = round(float(sz if sz else 2.0), 3)
    return ('raise', sz if sz else 2.0)

# 레이즈 단계별 레인지 축소 계수 (3벳 대비)
LEVEL_TIGHTEN = {2: 1.00,   # 3벳
                 3: 0.34,   # 4벳
                 4: 0.16,   # 5벳
                 5: 0.10}   # 6벳+
# 올인 콜오프는 별도로 더 좁다
CALLOFF_TIGHTEN = {2: 0.55, 3: 0.22, 4: 0.11, 5: 0.07}

def prof_aggr(prof):
    if prof.get('temper'): return prof['temper']['aggression']
    t = prof.get('type', 'TAG')
    return A.ARCHETYPES[t][1] if t in A.ARCHETYPES else 5

def reraise_mult(level, def_pos):
    """레이즈 단계별 배수. 단계가 올라갈수록 작아진다."""
    ip = def_pos in ('BTN','CO','HJ','LJ')
    # level 규약은 '마주한 레이즈 수'다 (defend_thresholds 와 동일).
    # 오픈 대면 = 1 → 내가 치면 3벳. 예전 표는 키가 2부터라
    # 오픈 대면이 표에 없어 기본값 2.1 이 나왔고, 모든 3벳이 2.1배로 작았다.
    # AA 로도 3bb 오픈에 6.25bb 밖에 못 쳐서 밸류가 안 나왔다.
    return {1: (3.0 if ip else 3.7),   # 3벳
            2: (2.15 if ip else 2.35), # 4벳
            3: (2.1 if ip else 2.2),   # 5벳
            }.get(level, 2.1)

def raise_commit_geometry(stack_bb, target_bb, pot_bb, facing_bb):
    """레이즈 형태의 '기하' 질문: 논올인으로 치면 이미 커밋인가.

    반환 (forced_shove, spr_after). 동기(폴드에쿼티·상대 4벳 성향)와 분리한다
    (ledger L072). pot_bb 는 내가 치기 전의 팟(블라인드+오픈+콜러)이다.
    """
    # ---------- 1. 기하: 여기 걸리면 판단 이전에 이미 올인이다 ----------
    # 콜당했을 때의 팟: 내가 target, 상대가 (target - 이미 넣은 것)을 더 넣는다.
    rem = stack_bb - target_bb
    pot_after = max(1.0, pot_bb + 2.0*target_bb - facing_bb)
    spr_after = rem / pot_after
    # 하드 게이트는 '논올인이라는 선택지가 실제로 없는' 구간에만 둔다.
    # 여기를 넓게 잡으면 아래 판단 층이 통째로 죽는다 —
    # 실제로 1.15 로 잡았더니 32bb 까지 100% 쇼브, 40bb 0% 인 새 계단이 됐다.
    if target_bb >= 0.75*stack_bb or spr_after < 0.50:
        return True, spr_after
    return False, spr_after


def shove_form_pressure(spr_after, exploit, level, n_opp):
    """레이즈 형태의 '동기' 질문: 커밋 구간 근처에서 올인 형태를 고를 압력 0~1.

    기하(SPR) 압력에 상대 폴드에쿼티·4벳 성향(읽기)과 다인원 배율을 더한다.
    """
    # ---------- 2. 연속 판단 ----------
    # 스택 깊이는 bb 가 아니라 '3벳 후 SPR' 로 잰다.
    # bb 만 보면 오픈 사이즈와 3벳 배수를 무시하게 된다 —
    # 같은 30bb 라도 2bb 오픈과 3.5bb 오픈은 남는 스택이 다르다.
    sh = max(0.0, min(1.0, (1.75 - spr_after) / 1.25))
    if exploit and exploit.get('w', 0) > 0:
        w = exploit['w']
        # 이 단계에서 상대가 접는가. 오픈 대면이면 '3벳 대면 폴드율',
        # 3벳 대면이면 '4벳 대면 폴드율'을 봐야 한다.
        fe = (exploit.get('f2fb_gap', 0.0) if level >= 2
              else exploit.get('f2tb_gap', exploit.get('fold_gap', 0.0)))
        # 잘 접는 상대(+)에게는 논올인으로 충분하다 — 같은 폴드에쿼티를 싸게 산다.
        # 안 접는 상대(-)에게 어중간한 3벳은 콜당한 뒤 SPR 2 짜리 난제가 된다.
        sh *= max(0.25, 1.0 - w*1.1*fe)
        # 4벳을 자주 하는 상대에게 논올인 3벳은 유도가 된다. 쇼브로 그 기회를 없앨 이유가 없다.
        sh *= max(0.35, 1.0 - w*0.5*max(0.0, exploit.get('fb_gap', 0.0)))
    if n_opp > 1:
        # 다인원 보정은 **이미 있는 기하적 커밋 압력**을 키우는 배율이다.
        # 예전에는 +0.20 을 바닥값으로 더해, 콜당해도 SPR 3 이 남는 99bb
        # 스퀴즈에서도 22% 가 올인 형태가 됐다(audit9 HAND 23: SB AA 99bb 쇼브 —
        # 밸류 핸드가 더 약한 핸드를 전부 접게 만든다). 커밋 구간이 아니면 0.
        sh = min(1.0, sh * (1.0 + 0.20*(n_opp - 1)))

    return sh


def raise_form(prof, stack_bb, target_bb, pot_bb, rng, exploit=None,
               level=1, n_opp=1, facing_bb=0.0):
    """레이즈를 논올인으로 칠지 올인으로 갈지 — 형태를 정하는 유일한 지점.

    기존에는 `band in ('micro','short','mid')` 한 줄이었다.
    스택 24.9bb 와 25.1bb 가 완전히 다른 사람이 되고,
    같은 20bb 에서 '3벳에 항상 접는 상대'와 '절대 안 접는 상대'가
    같은 형태로 처리됐다. 그건 판단이 아니라 계단이다.

    세 가지가 형태를 정한다:
      1. 기하 — 논올인으로 치고 남는 스택이 팟 대비 얕으면 이미 커밋이다
      2. 폴드에쿼티 — 잘 접는 상대에겐 굳이 다 밀 이유가 없다(싸게 같은 결과)
                      안 접는 상대에겐 어중간한 3벳이 최악의 SPR 을 만든다
      3. 상대 4벳 성향 — 4벳을 자주 하는 상대에게 논올인 3벳은 유도다
    자기 개념(spr)이 낮으면 위 판단을 못 하고 예전 계단으로 물러난다.

    반환: ('shove', stack_bb) 또는 ('raise', target_bb)
    """
    if stack_bb is None or target_bb >= stack_bb:
        return ('shove', stack_bb if stack_bb is not None else target_bb)

    # ---------- 1. 기하(raise_commit_geometry) / 2. 동기(shove_form_pressure) ----------
    forced, spr_after = raise_commit_geometry(stack_bb, target_bb, pot_bb, facing_bb)
    if forced:
        return ('shove', stack_bb)      # 쳐놓고 접을 수 없다 = 형태만 다른 올인

    sh = shove_form_pressure(spr_after, exploit, level, n_opp)

    # ---------- 3. 개념 게이트 ----------
    # 스택 깊이를 못 읽는 사람은 위 판단을 못 한다. 예전 밴드 계단으로 물러난다.
    aware = 1.0
    if prof.get('concepts'):
        aware = max(0.0, min(1.0, (PS.sk(prof, 'spr') - 2.0) / 6.0))
    crude = 1.0 if _DP.base_feel(stack_bb) < crude_edge(prof) else 0.0
    p = crude*(1.0 - aware) + sh*aware
    if rng.random() < max(0.0, min(1.0, p)):
        return ('shove', stack_bb)
    return ('raise', target_bb)


HOT_LO, HOT_HI = 12.0, 26.0

def in_hotzone(bb): return HOT_LO <= bb <= HOT_HI

def reshove_range(prof, def_pos, opener_pos, bb, open_bb, n_callers=0):
    """핫존(12~26bb)에서 오픈에 대한 3벳 올인 레인지 폭.
       스택이 얕을수록, 오프너가 늦은 포지션일수록 넓다."""
    t = _tr(prof)
    a = prof_aggr(prof)
    base = 0.055 + 0.011*a + 0.35*t['threebet']
    # 스택 곡선: 12bb 최대, 26bb에서 급감
    depth_mult = max(0.25, min(1.6, (26.0 - bb) / 9.0))
    pos_mult = RESHOVE_OPENER_ATTACK.get(opener_pos, 2.0) / 2.6
    blind_mult = 1.25 if def_pos in ('SB', 'BB') else 0.85
    fold_eq = 1.0 / (1.0 + 0.55*n_callers)          # 콜러가 있으면 폴드에쿼티 하락
    cap = base * depth_mult * pos_mult * blind_mult * fold_eq
    return max(0.02, min(0.60, cap))


def reshove_weight(stack_bb):
    """그 스택이 리쇼브 위협인 정도. 0~1 연속.

    예전에는 in_hotzone(12.0 <= bb <= 26.0) 하드 경계였다.
    11.9bb 는 위협이 아니고 12.1bb 는 위협이 되는 것은 말이 안 된다.
    깊이 인식 곡선으로 재면 자연스럽게 이어진다 —
    너무 얕으면 이미 다 넣을 것이고, 너무 깊으면 리쇼브가 아니라 3벳이다.
    """
    f = _DP.base_feel(stack_bb)
    if f <= 0.0 or f >= 0.26:
        return 0.0
    return max(0.0, 1.0 - abs(f - 0.09) / 0.17)


def hotzone_pressure(prof, pos, bb, behind_stacks):
    """뒤에 리쇼브 위협이 있으면 오픈 레인지를 줄인다. 배수 1.0 기준."""
    if not behind_stacks:
        return 1.0
    w = sum(reshove_weight(s) for s in behind_stacks)
    if w <= 0.01:
        return 1.0
    aware = 1.0
    if prof.get('concepts'):
        aware = min(1.2, PS.sk(prof, 'spr')/6.0)
    return max(0.55, 1.0 - 0.15*w*aware)


def _tr_loose(prof):
    """루즈함 0~10. 개념 벡터가 없으면 call 성향에서 역산한다."""
    if isinstance(prof, dict) and prof.get('concepts'):
        return PS.temper(prof, 'looseness', 5.0)
    return max(0.0, min(10.0, _tr(prof)['call']/0.022))


def normalize_defend_prior_widths(attack_width, continue_width, calibrated_mtt8):
    """Preserve the prior-specific clamp/saturation contract; no new prior."""
    _tp, _tot = attack_width, continue_width
    _tot = max(_tp, _tot)
    if calibrated_mtt8:
        # 이 경로의 base_tot/base_tp 자체가 공개 8-max MTT 빈도에 맞춘
        # 확률이다. 100% 초과 방지용 exp saturation을 다시 적용하면
        # 정상적인 0~1 확률까지 불필요하게 압축된다.
        _tot = max(0.0, min(0.95, float(_tot)))
        _tp = max(0.0, min(_tot, float(_tp)))
        return _tp, _tot
    return _saturate(_tp, _tot)


def adjust_defend_widths_for_callers(prof, attack_width, continue_width, n_callers):
    """Caller/squeeze context; preserves existing personality and evaluation order."""
    tp, tot = attack_width, continue_width
    # 다인원. 축소율을 상수로 두면 안 된다 —
    # 규율 있는 레귤러는 크게 조이지만 콜링 스테이션은 거의 신경 쓰지 않는다.
    # 상수면 루즈한 필드일수록 다인원이 되어 축소가 세게 걸리고,
    # 결국 필드의 헐거움이 스스로를 상쇄해 어떤 필드든 같은 참여율로 수렴한다.
    if n_callers:
        loose_v = _tr_loose(prof)
        # 계수 근거: 콜러가 늘 때 축소가 거듭제곱으로 들어가 타이트한 퍼소나가
        # 과도하게 압축됐다. 검토(2026-09-04)에서 하한/기울기를 조정.
        # 실측: 콜러1명 디펜스율 28.1%->31.5%, 콜러2명 19.9%->24.8%.
        # 효과는 균일하지 않다 — loose_v 낮을수록 크게 풀린다(+22% vs +1%).
        mw = max(0.60, min(0.96, 0.60 + 0.040*loose_v))
        tot *= mw ** n_callers
        tp *= (_tr(prof)['sqz'] if 'sqz' in _tr(prof) else 1.0) * (0.92 ** n_callers)
        tp = min(tp, tot)

    return tp, tot


def adjust_defend_widths_for_short_stack(attack_width, continue_width, bb):
    """Existing shallow-stack attack/call partition, not a reshove EV model."""
    tp, tot = attack_width, continue_width
    # 짧으면 콜 대신 쇼브/폴드. 콜 구간이 줄고 3벳 구간이 는다.
    if _DP.base_feel(bb) < 0.20:
        tp = min(tot, tp * 1.6)
        tot = max(tp, tot * 0.62)

    return tp, tot


def tighten_defend_widths_for_raise_level(attack_width, continue_width, raise_level):
    """Legacy higher-reraise contraction and final caps; NOT a 4bet prior.

    raise_level=1 faces an open; >=2 faces a reraise. Preserve this final
    stage after caller and short-stack transforms, including operation order.

    지식 상태(R2): 독립 vs-3bet / 4bet / 5bet prior 는 MISSING_KNOWLEDGE 다.
    여기서는 vs-open 디펜스 prior(오프너가 3벳을 맞으면 위치를 바꿔 쓴 값)를
    LEVEL_TIGHTEN 으로 줄일 뿐이며, 이 값을 4벳 정답으로 간주하지 않는다.
    """
    tp, tot = attack_width, continue_width
    # 단계별 축소는 마지막에. 앞에서 하면 이후 곱셈이 좁아진 값을 되살린다.
    if raise_level >= 2:
        lt = LEVEL_TIGHTEN.get(raise_level+1, 0.10)
        tp *= lt
        tot = tp + (tot - tp) * (lt*0.8)
    return max(0.0, min(0.9, tp)), max(0.0, min(0.95, tot))


def defend_thresholds(prof, def_pos, opener_pos, bb, open_bb=2.5, n_callers=0,
                      raise_level=1, seats=8, ante=True):
    """디펜스 역치 (tp, tot) 를 내는 유일한 지점.

    tp  — 공격 구간 폭(3bet 또는 상위 재레이즈; 독립 4bet prior 아님)
    tot — 전체 계속 참가(공격+콜) 구간 폭

    defend_decision(실제 판단)과 ranges.preflop_range(상대 레인지 모델)이
    반드시 같은 구간을 보도록 여기 하나만 쓴다. 절대 복제하지 말 것.

    오픈과 같은 3층이다 — 기준(gto.defend_pct) x 성향 x 누적판단.
    예전에는 기준이 없고 아키타입 형질(t['threebet'], t['call'])에
    포지션 배수를 곱했다. 그래서 좌석수·안테·오픈사이즈 보정이
    gto.rfi 와 따로 놀았다.
    """
    import gto as _G
    base_tot = _G.defend_pct(def_pos, opener_pos, seats, bb, ante, open_bb)
    base_tp = _G.threebet_pct(def_pos, opener_pos, seats, bb, ante, open_bb)
    _calibrated_mtt8 = _G._use_mtt8_ante_defense(def_pos, seats, ante)

    if not (isinstance(prof, dict) and prof.get('concepts')):
        tp, tot = normalize_defend_prior_widths(base_tp, base_tot, _calibrated_mtt8)
    else:
        loose = PS.temper(prof, 'looseness', 5.0)
        aggr = PS.temper(prof, 'aggression', 5.0)
        d_call = PS.preflop_temper_direction(loose)
        d_tb = PS.preflop_temper_direction(0.45*loose + 0.55*aggr)
        if getattr(PS, 'PREFLOP_REASONING_V3', False):
            # 공부한 defend chart를 먼저 기억하고, 낯선 stack/table/ante의
            # 차이만 기존 reasoning skills로 보정한다. condition mismatch가
            # temperament deviation 자체를 키우지는 않는다.
            anchor_tp, anchor_tot = PS.gto_studied_anchor(
                'defend', def_pos, seats, bb, ante,
                opener_pos=opener_pos, open_bb=open_bb)
            tot = PS.preflop_reasoned_width(
                prof, 'defend', base_tot, d_call, def_pos, seats, bb, ante,
                opener_pos=opener_pos, open_bb=open_bb,
                deviation_scale=0.95, anchor=anchor_tot)
            tp = PS.preflop_reasoned_width(
                prof, 'defend', base_tp, d_tb, def_pos, seats, bb, ante,
                opener_pos=opener_pos, open_bb=open_bb,
                deviation_scale=1.10, anchor=anchor_tp)
        else:
            # v2 / production path: V3 OFF이면 기존 수치 그대로.
            acc = PS.gto_memory_confidence(prof, 'defend', def_pos, seats, bb, ante,
                                           opener_pos=opener_pos, open_bb=open_bb)
            tot = base_tot * (1.0 + PS.chart_deviation_room(acc)*d_call*0.95)
            tp = base_tp * (1.0 + PS.chart_deviation_room(acc)*d_tb*1.10)
        tp, tot = normalize_defend_prior_widths(tp, tot, _calibrated_mtt8)

    tp, tot = adjust_defend_widths_for_callers(prof, tp, tot, n_callers)
    tp, tot = adjust_defend_widths_for_short_stack(tp, tot, bb)
    return tighten_defend_widths_for_raise_level(tp, tot, raise_level)


def legacy_calloff_likelihoods(prof, def_pos, opener_pos, hand, bb, open_bb,
                               n_callers, raise_level, stack_bb, exploit, bf,
                               seats, ante, opener_allin, can_raise,
                               pot_bb, to_call_bb):
    """올인/거의 올인 대면 콜·폴드의 legacy 경로. 해당하지 않으면 None.

    판단량은 `calloff_cap`(디펜스 폭에서 파생한 pf_rank 백분위 cap)이다 —
    equity/가격이 아니다(R2 CALLOFF_PATH_AUDIT). 현재 이 값이 행동을 직접 정하는
    경로: near-all-in(`open_bb >= 스택×0.92`), 계산 게이트를 통과하지 못한
    순수 콜오프, 관찰자의 '쇼브에 콜한 사람' 레인지 복원. 공격(리쇼브)은 0.
    """
    _st = stack_bb if stack_bb is not None else bb
    _hero_calloff = open_bb >= _st * 0.92
    _pure_short_shove = bool(opener_allin and not can_raise)
    if not (_hero_calloff or _pure_short_shove):
        return None
    _pot = float(pot_bb if pot_bb is not None
                 else 1.5 + open_bb*(1 + n_callers))
    _tc = float(to_call_bb if to_call_bb is not None else open_bb)
    _a, _cap = calloff_decision(
        prof, def_pos, hand, bb, raise_level,
        _pot, _tc, bf, opener_pos, open_bb, exploit, n_callers,
        seats, ante)
    _kind = _a[0]
    return {
        'attack': 0.0,
        'call': 1.0 if _kind == 'call' else 0.0,
        'fold': 1.0 if _kind == 'fold' else 0.0,
        'hot_attack': 0.0,
        'mixed_attack': 0.0,
        'mixed_call': 1.0 if _kind == 'call' else 0.0,
        'mixed_fold': 1.0 if _kind == 'fold' else 0.0,
        'w_raise': 0.0,
        'w_call': 1.0 if _kind == 'call' else 0.0,
        'w_fold': 1.0 if _kind == 'fold' else 0.0,
        'total_weight': 1.0,
        'calloff': True,
        'calloff_cap': _cap,
        'tp': None,
        'tot': None,
        'hand_pct': legacy_preflop_order_percentile(hand),
    }


def apply_defend_exploit_evidence(tp, tot, exploit, raise_level):
    """상대 읽기(exploit read)를 공격 폭 tp / 계속 폭 tot 에 적용한다.

    3벳/4벳의 '동기·증거' 층이다(R2 A 3절 (b)). prior 폭(tp, tot)과 후보 순서는
    바꾸지 않고 읽기만 반영한다. baseline(exploit 중립, w=0)에서는 그대로 통과.
    """
    if exploit and exploit.get('w', 0) > 0:
        w = exploit['w']
        if raise_level >= 2:
            tbg = exploit.get('tb_gap', 0.0)
            tp = max(0.0, min(0.9, tp * (1.0 + w*1.3*tbg)))
            tot = max(tp, min(0.95, tot * (1.0 + w*0.8*tbg)))
            pol = exploit.get('tb_polar', 0.0)
            if pol > 0.02:
                tot = max(tot, min(0.95, tot * (1.0 + w*0.85*pol)))
                tp = max(0.0, min(0.9, tp * (1.0 + w*1.10*pol)))
            f2fb = exploit.get('f2fb_gap', 0.0)
            tp = max(0.0, min(0.9, tp * (1.0 + w*1.5*f2fb)))
            tot = max(tp, min(0.95, tot * (1.0 - w*0.5*f2fb)))
        else:
            og = exploit.get('open_gap', 0.0)
            if abs(og) > 1e-6:
                tot = max(tot, min(0.95, tot * (1.0 + w*0.55*og)))
                tp = max(0.0, min(0.9, tp * (1.0 + w*0.45*og)))
            f2tb = exploit.get('f2tb_gap', exploit.get('fold_gap', 0.0))
            tp = max(0.0, min(0.9, tp * (1.0 + w*1.5*f2tb)))
            tot = max(tp, min(0.95, tot * (1.0 - w*0.5*f2tb)))
            fbg = exploit.get('fb_gap', 0.0)
            if fbg > 0:
                tp = max(min(tp, 0.06), tp * (1.0 - w*1.1*fbg))

    return tp, tot


def hot_reshove_probability(prof, def_pos, opener_pos, hand_pct, stack_bb,
                            open_bb, n_callers, raise_level, can_raise):
    """핫존(12~26bb) 리쇼브 확률 — legacy 근사.

    세 층이 섞여 있음을 이름으로 드러낸다(R2 A 2절):
      후보      hand_pct <= rs            (pf_rank 순서: 유지 가능)
      legacy 폭 rs = reshove_range(...)   (성향 + 폴드에쿼티 대용 + 스택)
      legacy 확률 0.30 + 0.60·(1 − r/rs)  (근거 없는 순서→확률 변환)
    리쇼브가 +EV 인지(콜당했을 때 equity, 폴드에쿼티, 가격, 뒤 좌석)는 계산하지
    않는다. 빈도 지식은 MISSING_KNOWLEDGE.
    """
    p_hot = 0.0
    if can_raise and stack_bb is not None and in_hotzone(stack_bb) and raise_level == 1:
        rs = reshove_range(prof, def_pos, opener_pos, stack_bb, open_bb, n_callers)
        if hand_pct <= rs:
            depth = 1.0 - (hand_pct / max(1e-6, rs))
            p_hot = max(0.0, min(1.0, 0.30 + 0.60*depth))
    return p_hot


def _defend_logistic(x, center, width):
    return 1.0/(1.0+math.exp((x-center)/max(1e-6, width)))


def attack_candidate_weight(hand_pct, tp, aggr):
    """공격(3벳/상위 재레이즈) 후보 가중치 — pf_rank 상위 슬라이스 (0, tp] 의 형상.

    3벳/4벳의 '후보 순서' 층이다(R2 A 3절 (a)). 집합 모양이 solver 3벳 집합을
    재현한다는 근거는 없다(8-max 관찰 재현율 0.61). tp 는 독립 4벳 prior 가 아니다.
    """
    w_raise = _defend_logistic(hand_pct, tp, max(0.015, tp*0.35))
    w_raise *= (0.35 + 0.65*max(0.0, 1.0 - hand_pct/max(1e-6, tp)))
    w_raise *= (0.55 + 0.085*aggr)
    return w_raise


def preflop_slowplay_share(prof, hand_pct, aggr):
    """프리미엄을 공격 대신 콜로 돌리는 슬로플레이 몫(기질). 0~1."""
    _pf_slow = 0.0
    if prof.get('concepts'):
        _taste = PS.temper(prof, 'slowplay_taste', 5.0) / 10.0
        _passive = max(0.0, min(1.0, (5.0 - aggr) / 5.0))
        _premium = max(0.0, min(1.0, (0.10 - hand_pct) / 0.10))
        _pf_slow = _passive * (0.35 + 0.65*_taste) * _premium
    elif A.ARCHETYPES.get(prof.get('type'), (0,)*7+('reg',))[6] == 'fish':
        _pf_slow = max(0.0, min(1.0, (0.10 - hand_pct) / 0.10)) * 0.55
    return _pf_slow


def defend_action_likelihoods(prof, def_pos, opener_pos, hand, bb, open_bb,
                              n_callers, raise_level=1, stack_bb=None,
                              exploit=None, bf=1.0, seats=8, ante=True,
                              opener_allin=False, can_raise=True,
                              pot_bb=None, to_call_bb=None):
    """RNG를 소비하지 않는 defend 액션 범주 확률.

    반환 범주는 관찰자 레인지가 구분할 수 있는 세 가지다.

      attack  3bet / raise-form shove
      call    flat / call-off
      fold

    현재 defend_decision의 혼합정책 수학을 그대로 계산하지만 실제 액션
    또는 사이즈를 뽑지 않는다. B1D weighted-posterior가 actor의 비공개 RNG를
    재생하지 않고 P(observed action | hand, model)을 계산하기 위한 단일 의미
    계약이다.

    exploit는 actor 쪽에서는 실제 read를 받을 수 있지만 observer는 자신의
    공개/추정 모델만 넣어야 한다. 이 helper 자체는 hidden state를 조회하지 않는다.
    """
    _calloff = legacy_calloff_likelihoods(
        prof, def_pos, opener_pos, hand, bb, open_bb, n_callers, raise_level,
        stack_bb, exploit, bf, seats, ante, opener_allin, can_raise,
        pot_bb, to_call_bb)
    if _calloff is not None:
        return _calloff

    tp, tot = defend_thresholds(prof, def_pos, opener_pos, bb, open_bb,
                                n_callers, raise_level, seats, ante)
    tp, tot = apply_defend_exploit_evidence(tp, tot, exploit, raise_level)

    r = legacy_preflop_order_percentile(hand)

    p_hot = hot_reshove_probability(prof, def_pos, opener_pos, r, stack_bb,
                                    open_bb, n_callers, raise_level, can_raise)

    _logit = _defend_logistic
    a = prof_aggr(prof)
    w_raise = attack_candidate_weight(r, tp, a)
    _pf_slow = preflop_slowplay_share(prof, r, a)
    w_raise *= max(0.30, 1.0 - 0.70*_pf_slow)

    # 혼합 폭은 참가 경계(tot) 근처의 불확실성이다. (tot-tp)*0.35 는 tot 의
    # 약 30% 폭이라, 경계에서 먼 핸드까지 폴드 꼬리가 남았다 — 최대숙련
    # 프로필이 BB 대 BTN 오픈에 AKo 3%·88 4%, HJ 대 LJ 오픈에 AKo 12% 폴드,
    # SB 대 LJ 오픈+콜에 AKo 6% 폴드(audit9 HAND 17 실제 발생). 폭을 tot 의
    # 15% 로 묶어 경계 근처에서만 섞는다(경계 근처 AQo/ATs 혼합은 유지).
    w_cont = _logit(r, tot, max(0.015, tot*0.15))
    w_call = max(0.0, w_cont - w_raise*0.6) * (1.5 - 0.055*a)
    w_call *= 1.0 + 0.90*_pf_slow
    if not can_raise:
        w_raise = 0.0
    w_fold = max(0.0, 1.0 - w_cont)
    if r <= 0.03:
        w_fold = 0.0
    if r <= 0.015:
        w_call *= 0.16
    elif r <= 0.04:
        w_call *= 0.35
    slow = 0.04 + 0.012*(10-a)
    if w_raise > 0 and w_call >= 0:
        w_call = max(w_call, w_raise*slow)
    if r > tot*1.35:
        w_raise = 0.0
    # w_cont is already a smooth logistic around tot.  Do not add a second
    # hard cliff immediately outside the defend threshold; that turned hands
    # barely outside tot (e.g. A3o vs CO) from marginal continues into
    # near-pure folds.

    total = w_raise + w_call + w_fold
    if total <= 0:
        m_raise, m_call, m_fold = 0.0, 0.0, 1.0
    else:
        m_raise = w_raise / total
        m_call = w_call / total
        m_fold = w_fold / total

    attack = p_hot + (1.0-p_hot)*m_raise
    call = (1.0-p_hot)*m_call
    fold = (1.0-p_hot)*m_fold
    z = attack + call + fold
    if z > 0:
        attack, call, fold = attack/z, call/z, fold/z

    return {
        'attack': attack,
        'call': call,
        'fold': fold,
        'hot_attack': p_hot,
        'mixed_attack': m_raise,
        'mixed_call': m_call,
        'mixed_fold': m_fold,
        'w_raise': w_raise,
        'w_call': w_call,
        'w_fold': w_fold,
        'total_weight': total,
        'calloff': False,
        'calloff_cap': None,
        'tp': tp,
        'tot': tot,
        'hand_pct': r,
    }

def defend_decision(prof, def_pos, opener_pos, hand, bb, open_bb, n_callers, rng,
                    raise_level=1, stack_bb=None, tilt=0.0, field_q=0.6,
                    exploit=None, bf=1.0,
                    payout_flat=0.0, reentry=False, progress=0.0,
                    seats=8, ante=True, opener_allin=False, can_raise=True,
                    pot_bb=None, to_call_bb=None):
    """오픈(또는 오픈+콜러)에 대한 대응.

    액션 확률 의미는 defend_action_likelihoods 한 곳에서 계산한다.
    이 함수는 그 확률을 기존과 동일한 RNG 순서로 실행하고, 공격이 선택됐을
    때 raise_form 으로 형태/사이즈를 정하는 실행 계층만 맡는다.

    tilt/field_q/payout_flat/reentry/progress 는 V2 plan selector 경계 호환 인자다.
    현재 defend 확률식에는 들어가지 않는다.
    """
    lik = defend_action_likelihoods(
        prof, def_pos, opener_pos, hand, bb, open_bb, n_callers,
        raise_level=raise_level, stack_bb=stack_bb,
        exploit=exploit, bf=bf, seats=seats, ante=ante,
        opener_allin=opener_allin, can_raise=can_raise,
        pot_bb=pot_bb, to_call_bb=to_call_bb)
    _timing_bound(
        {'kind': 'defend_calloff', 'r': float(lik['hand_pct']),
         'cap': float(lik['calloff_cap'])} if lik['calloff'] else
        {'kind': 'defend', 'r': float(lik['hand_pct']),
         'tot': float(lik['tot']), 'tp': float(lik['tp'])})

    # 올인 대면 call-off는 원래부터 RNG가 없는 결정이다.
    if lik['calloff']:
        if lik['call'] >= 1.0:
            _tc = float(to_call_bb if to_call_bb is not None else open_bb)
            return ('call', _tc)
        return ('fold', 0)

    # 핫존 리쇼브는 기존과 똑같이 mixed roll보다 먼저 RNG를 한 번 소비한다.
    # 실패한 경우에만 아래 일반 mixed policy로 내려간다.
    p_hot = lik['hot_attack']
    if p_hot > 0.0 and rng.random() < p_hot:
        _tgt = open_bb*(reraise_mult(1, def_pos) + 1.0*n_callers)
        _act, _sz = raise_form(
            prof, stack_bb, _tgt,
            1.5 + open_bb*(1 + n_callers), rng,
            exploit=exploit, level=1,
            n_opp=1 + n_callers, facing_bb=open_bb)
        return (_act, _sz) if _act == 'shove' else ('3bet', _sz)

    w_raise = lik['w_raise']
    w_call = lik['w_call']
    w_fold = lik['w_fold']
    tot_w = lik['total_weight']
    if tot_w <= 0:
        return ('fold', 0)

    x = rng.random()*tot_w
    if x < w_raise:
        mult = reraise_mult(raise_level, def_pos) + 1.0*n_callers
        target = open_bb*mult

        # 상대가 이미 올인이면 리레이즈 목표를 올인 금액 위로 부풀리지 않는다.
        if opener_allin:
            target = open_bb

        _raise_pot = 1.5 + open_bb*(1 + n_callers)
        act, sz = raise_form(
            prof, stack_bb if stack_bb is not None else bb,
            target, _raise_pot, rng, exploit=exploit,
            level=raise_level, n_opp=1 + n_callers,
            facing_bb=open_bb)
        return (act, sz) if act == 'shove' else ('3bet', sz)

    if x < w_raise + w_call:
        return ('call', open_bb)
    return ('fold', 0)


def top_value_class_order(classes):
    """블로커 계산에서 '상대 최상단 밸류'를 정의하는 클래스 순서(pf_rank).

    블로커 몫은 두 질문이다: (1) 어느 클래스가 최상단인가 — 순서(PCT),
    (2) 그 구간에서 내 카드가 지운 질량 — 관측 레인지의 실제 가중치.
    (1)만 이 함수가 맡는다(ledger L075). 블러프 실력과는 무관하다.
    """
    return sorted(classes, key=lambda x: PCT.get(x, 1.0))


def preflop_blocker_share(hand, pools):
    """내 두 장이 상대들의 최상단 밸류 질량을 지운 몫. 0~1.

    최상단 = 각 pool 질량의 상위 20%(ranges.blocker_score 의 '상위 1/5'와
    같은 정의). pool 이 이미 내 카드를 dead 로 뺐을 수도, 안 뺐을 수도 있어
    클래스별 원래 콤보 수(페어 6/수딧 4/오프 12) 대비 사라진 질량과
    남아 있는 '내 카드 포함 콤보' 질량을 함께 센다.
    순서는 PCT(pf_rank) — R2 의존. 최상단(AA/KK/QQ/AK 근처)에서만 쓴다.
    """
    import ranges as _R
    if not pools or not hand:
        return 0.0
    hs = set(hand)
    full_tot = 0.0
    blocked_tot = 0.0
    for r in pools:
        wr = _R.weighted_range(r)
        by = {}
        for c, w in wr.items():
            by.setdefault(cls(list(c)), []).append((c, float(w)))
        mass = sum(w for v in by.values() for _, w in v)
        if mass <= 0:
            continue
        acc = 0.0
        for k in top_value_class_order(by):
            rows = by[k]
            mw = sum(w for _, w in rows) / len(rows)
            n_full = 6 if len(k) == 2 else (4 if k.endswith('s') else 12)
            present = sum(w for _, w in rows)
            mine = sum(w for c, w in rows if c[0] in hs or c[1] in hs)
            full = n_full * mw
            full_tot += full
            blocked_tot += max(0.0, full - present) + mine
            acc += present
            if acc >= 0.20 * mass:
                break
    return max(0.0, min(1.0, blocked_tot / full_tot)) if full_tot > 0 else 0.0


def multiway_evidence_application_capacity(read_application_skill, potodds_skill, multiway_skill):
    """How strongly multiway evidence replaces the existing preflop baseline."""
    return max(0.0, min(1.0, (read_application_skill + potodds_skill + multiway_skill) / 30.0))


def apply_multiway_call_evidence(call, fold, equity, required_equity, application_capacity):
    """Move existing call/fold mass toward the price comparison; attack mass is separate."""
    cf_mass = call + fold
    evidence_call = cf_mass if equity >= required_equity else 0.0
    call = (1.0 - application_capacity)*call + application_capacity*evidence_call
    fold = max(0.0, cf_mass - call)
    return call, fold


def multiway_reraise_decision(prof, def_pos, reraiser_pos, hand, bb, open_bb,
                              n_callers, rng, raise_level=2, stack_bb=None,
                              exploit=None, bf=1.0, seats=8, ante=True,
                              can_raise=True, pot_bb=None, to_call_bb=None,
                              opponent_ranges=None, players_behind=0,
                              decision_seed=None, locked_keys=None):
    """두 개 이상의 살아 있는 상대 레인지를 함께 보는 재레이즈 판단.

    핵심은 '마지막 aggressor 한 명 vs 나'로 축약하지 않는 것이다.
    이미 오픈/콜/3벳 등으로 행동한 플레이어가 다시 액션을 맞는 경우에도
    현재 살아 있는 seat-keyed range를 모두 독립된 pool로 유지한다.

    generic defend는 마지막 aggressor에 대한 인간적 baseline을 제공하고,
    multiway evidence는 다음 두 부분만 교정한다.
      - call: 실제 팟오즈와 모든 살아 있는 레인지에 대한 showdown equity
      - attack: N-way fair share에 못 미칠 때 무근거 재재레이즈를 억제

    아직 행동하지 않은 뒤 좌석은 range pool에 들어 있지 않을 수 있으므로
    players_behind 위험은 기존 6%p/인, 최대 18%p 규칙을 그대로 재사용한다.
    """
    _locked = {str(k) for k in (locked_keys or [])}
    if isinstance(opponent_ranges, dict):
        pools = [r for _, r in sorted(opponent_ranges.items(), key=lambda kv: str(kv[0]))
                 if r]
        range_seats = [str(k) for k, r in sorted(
            opponent_ranges.items(), key=lambda kv: str(kv[0])) if r]
        # 공격으로 접게 만들 수 있는 상대만. 이미 올인한 상대는 폴드가 없다.
        free_pools = [r for k, r in sorted(
            opponent_ranges.items(), key=lambda kv: str(kv[0]))
            if r and str(k) not in _locked]
    else:
        pools = [r for r in (opponent_ranges or []) if r]
        range_seats = []
        free_pools = list(pools)

    if len(pools) < 2 or pot_bb is None or to_call_bb is None:
        act, sz = defend_decision(
            prof, def_pos, reraiser_pos, hand, bb, open_bb, n_callers, rng,
            raise_level=raise_level, stack_bb=stack_bb,
            exploit=exploit, bf=bf, seats=seats, ante=ante,
            opener_allin=False, can_raise=can_raise,
            pot_bb=pot_bb, to_call_bb=to_call_bb)
        return act, sz, {
            'complete': False,
            'reason': 'missing_multiway_ranges_or_price',
            'strategy_consumer': False,
            'opponent_range_count': len(pools),
            'opponent_range_seats': range_seats,
        }

    import bot as _B
    _seed = int(decision_seed or 0)
    eq = float(_B.equity_vs_combos(
        hand, [], pools, sims=900, seed=_seed))

    cost = max(0.0, float(to_call_bb or 0.0))
    pot_before = max(0.0, float(pot_bb or 0.0))
    bf_seen = (
        PS.icm_bf(prof, max(1.0, float(bf or 1.0)))
        if isinstance(prof, dict) and prof.get('concepts')
        else max(1.0, float(bf or 1.0)))
    need_base = (cost * bf_seen) / max(1e-9, pot_before + cost)

    noise = 1.0
    reason_skill = 0.5
    bluff_skill = 0.5
    if isinstance(prof, dict) and prof.get('concepts'):
        _nseed = zlib.crc32(('%s|multiway_reraise_potodds' % _seed).encode())
        noise = PS.calc_noise(prof, 'potodds', random.Random(_nseed))
        noise = max(0.65, min(1.55, float(noise)))
        reason_skill = multiway_evidence_application_capacity(
            PS.sk(prof, 'read_application'), PS.sk(prof, 'potodds'), PS.sk(prof, 'multiway'))
        # 블러프 능력 = '근거(블로커·폴드 에쿼티)를 블러프 행동으로 옮기는 능력'.
        # 여기서는 그 근거를 얼마나 활용하는지에만 곱한다 — bluff 개념의 정의와
        # 같은 질문이라 유지한다(3벳 성향 형질과는 다른 질문, stage9 closeout A2).
        bluff_skill = max(0.0, min(1.0, PS.sk(prof, 'bluff') / 10.0))

    need = need_base * noise
    if players_behind:
        need += _ICM.players_behind_required_equity_premium(
            need_base, int(players_behind))
    need = max(0.01, min(0.95, need))

    lik = defend_action_likelihoods(
        prof, def_pos, reraiser_pos, hand, bb, open_bb, n_callers,
        raise_level=raise_level, stack_bb=stack_bb,
        exploit=exploit, bf=bf, seats=seats, ante=ante,
        opener_allin=False, can_raise=can_raise,
        pot_bb=pot_bb, to_call_bb=to_call_bb)

    attack = float(lik['attack'])
    call = float(lik['call'])
    fold = float(lik['fold'])
    base = {'attack': attack, 'call': call, 'fold': fold}

    # call/fold는 '휴리스틱 확률에 약간 보정'이 아니라
    # multiway 계산을 실제로 이해하는 정도만큼 계산 결과로 교체한다.
    #
    # reason_skill=1 인 플레이어가 eq < perceived need라고 정확히 계산했는데도
    # generic call 찌꺼기가 남아 랜덤 콜하는 것은 reasoning error다.
    # 계산오차/인간차이는 이미 need의 calc_noise와 reason_skill<1에 들어 있다.
    call, fold = apply_multiway_call_evidence(call, fold, eq, need, reason_skill)
    _timing_bound({'kind': 'multiway', 'r': float(lik['hand_pct']),
                   'eq': float(eq), 'need': float(need),
                   'reason_skill': float(reason_skill)})

    # 이미 올인한 상대가 있으면 내 공격은 그 상대에게는 '콜'이다. 폴드
    # 에쿼티가 없으므로 기준은 fair share 가 아니라 가격(need)이다. 다른
    # 상대가 전부 접는 가장 낙관적인 경우의 eq(올인 상대 레인지만)조차
    # need 에 못 미치면 공격은 -EV 다(audit9 HAND 51: TT eq 0.336 > fair
    # 0.333 이라 억제 0, 실제 need 0.466).
    eq_locked = None
    if attack > 0.0 and _locked and isinstance(opponent_ranges, dict):
        _lk_pools = [r for k, r in sorted(
            opponent_ranges.items(), key=lambda kv: str(kv[0]))
            if r and str(k) in _locked]
        if _lk_pools:
            eq_locked = float(_B.equity_vs_combos(
                hand, [], _lk_pools, sims=900, seed=_seed + 17))
            if eq_locked < need:
                _rm = attack * reason_skill
                attack -= _rm
                fold += _rm

    # 공격도 헤즈업 기준이 아니라 현재 N-way fair share를 본다.
    fair = 1.0 / (1.0 + len(pools))
    bluff_support = None
    if eq < fair and attack > 0.0:
        f2fb = 0.0
        rw = 0.0
        if exploit:
            rw = max(0.0, min(1.0, float(exploit.get('w', 0.0) or 0.0)))
            f2fb = max(0.0, float(exploit.get('f2fb_gap', 0.0) or 0.0))
        # 블러프 '실력'은 공격 근거가 아니다. 근거는 (1) 상대가 4벳에 잘
        # 접는다는 읽기, (2) 내 카드가 접을 수 있는 상대의 최상단 밸류를
        # 실제로 지우는 블로커다. 실력은 그 근거를 얼마나 쓰는가에만 곱한다.
        # 예전 max(bluff_skill, …)는 bluff 10 인 사람에게 근거 없이 keep=1 을
        # 줘서 88/TT 의 cold 4bet·올인 위 재쇼브가 eq<fair 에서도 그대로
        # 남았다(audit9 HAND 28/41/45/51 — 51은 올인 상대 앞 eq 0.30 쇼브).
        _blk = preflop_blocker_share(hand, free_pools)
        _read_ev = min(1.0, rw*f2fb) if free_pools else 0.0
        bluff_support = max(_read_ev, bluff_skill*_blk)
        suppress = reason_skill * min(1.0, (fair - eq) / fair)
        keep = (1.0 - suppress) + suppress*bluff_support
        removed = attack * (1.0 - keep)
        attack *= keep
        fold += removed

    if not can_raise:
        fold += attack
        attack = 0.0

    z = attack + call + fold
    if z <= 0:
        attack, call, fold = 0.0, 0.0, 1.0
    else:
        attack, call, fold = attack/z, call/z, fold/z

    x = rng.random()
    if x < attack:
        mult = reraise_mult(raise_level, def_pos) + 1.0*n_callers
        target = open_bb * mult
        _raise_pot = max(
            1.5 + open_bb*(1 + n_callers),
            float(pot_bb or 0.0))
        act, sz = raise_form(
            prof, stack_bb if stack_bb is not None else bb,
            target, _raise_pot, rng, exploit=exploit,
            level=raise_level, n_opp=max(2, len(pools)+n_callers),
            facing_bb=open_bb)
        action = (act, sz) if act == 'shove' else ('3bet', sz)
    elif x < attack + call:
        action = ('call', open_bb)
    else:
        action = ('fold', 0)

    return action[0], action[1], {
        'complete': True,
        'strategy_consumer': True,
        'equity_vs_multiway_ranges': round(eq, 6),
        'opponent_range_count': len(pools),
        'opponent_range_seats': range_seats,
        'need_base': round(need_base, 6),
        'need_seen': round(need, 6),
        'potodds_noise': round(noise, 6),
        'reason_skill': round(reason_skill, 6),
        'players_behind': int(players_behind or 0),
        'fair_share': round(fair, 6),
        'locked_keys': sorted(_locked),
        'equity_vs_locked': (round(eq_locked, 6)
                             if eq_locked is not None else None),
        'bluff_support': (round(bluff_support, 6)
                          if bluff_support is not None else None),
        'base_likelihoods': {k: round(v, 6) for k, v in base.items()},
        'final_likelihoods': {
            'attack': round(attack, 6),
            'call': round(call, 6),
            'fold': round(fold, 6)},
        'roll': round(x, 6),
        'selected_action': action[0],
    }


def cold_reraise_decision(prof, def_pos, reraiser_pos, hand, bb, open_bb,
                          n_callers, rng, raise_level=2, stack_bb=None,
                          exploit=None, bf=1.0, seats=8, ante=True,
                          can_raise=True, pot_bb=None, to_call_bb=None,
                          original_opener_range=None, reraiser_range=None,
                          players_behind=0, decision_seed=None,
                          locked_keys=None):
    """P7 호환 wrapper: 아직 행동하지 않은 플레이어의 open+re-raise 대응."""
    act, sz, audit = multiway_reraise_decision(
        prof, def_pos, reraiser_pos, hand, bb, open_bb, n_callers, rng,
        raise_level=raise_level, stack_bb=stack_bb,
        exploit=exploit, bf=bf, seats=seats, ante=ante,
        can_raise=can_raise, pot_bb=pot_bb, to_call_bb=to_call_bb,
        opponent_ranges={
            'original_opener': original_opener_range,
            'reraiser': reraiser_range,
        },
        players_behind=players_behind,
        decision_seed=decision_seed, locked_keys=locked_keys)

    # 기존 P7 verifier / telemetry 계약은 유지한다.
    if audit.get('reason') == 'missing_multiway_ranges_or_price':
        audit['reason'] = 'missing_two_ranges_or_price'
    if audit.get('complete'):
        audit['equity_vs_open_and_reraise'] = audit.get(
            'equity_vs_multiway_ranges')
        audit['fair_share_3way'] = audit.get('fair_share')
    return act, sz, audit

def _iso_skill_view(prof):
    """아이솔 폭 파생용 프로필: 명시 iso_raise 가 있을 때만 RFI 기억 입력을 대체."""
    c = prof.get('concepts') if isinstance(prof, dict) else None
    if not c or 'iso_raise' not in c:
        return prof
    view = dict(prof)
    view['concepts'] = dict(c)
    view['concepts']['pf_range'] = c['iso_raise']
    return view


def iso_entry_threshold(prof, pos, bb, seats, ante, traits, behind_reads,
                        behind_stacks):
    """림퍼 상대 아이솔레이트 레인지 폭(림퍼 읽기 반영 전).

    독립 iso prior 가 없어 오픈 폭에 iso 성향 배수를 곱해 파생한다(ledger L068,
    R2: MISSING_KNOWLEDGE). 뒤 3벳/리쇼브 위협은 오픈과 같은 압력 함수.
    판단 숙련 의미 이름은 iso_raise. 명시 값이 있으면 폭 파생의 차트 기억 입력을
    iso_raise 로 바꿔 읽고, 없으면 기존 RFI 차트 기억(pf_range) 그대로다.
    """
    return (_open(_iso_skill_view(prof), pos, seats, bb, ante)
            * (1.0 + 0.35*traits['iso'])
            * table_pressure(behind_reads)
            * hotzone_pressure(prof, pos, bb, behind_stacks or []))


def iso_decision(prof, pos, hand, n_limpers, bb, rng, limper_reads=None,
                 behind_stacks=None, behind_reads=None, seats=8, ante=True,
                 field_avg_bb=None, erosion=0.0, field_q=0.6, bf=1.0,
                 can_check=False):
    """림퍼만 있는 팟에서의 판단.

    iso 성향은 **레인지 폭**을 정한다. 같은 iso 성향으로 레인지를 넓힌 뒤
    rng<t['iso'] 를 다시 걸면 같은 판단을 두 번 적용하게 되고, 그 롤에서
    떨어진 TAG 가 AA까지 폴드할 수 있었다.

    뒤 사람의 3벳/리쇼브 위협과 실제 좌석수·안테·스택도 unopened 와 같은
    공개정보이므로 그대로 반영한다.
    """
    t = _tr(prof)
    feel = feel_of(prof, bb, field_avg_bb, erosion, field_q, bf)
    thr = iso_entry_threshold(prof, pos, bb, seats, ante, t, behind_reads,
                              behind_stacks)

    # 림퍼가 약할수록 아이소를 넓힌다.
    # '레이즈에 접는가'는 포스트플랍 fold_to_bet 이 아니라
    # 림프 후 첫 프리플랍 레이즈에 실제로 접었는지를 본다.
    if limper_reads:
        _lv = [r for r in limper_reads if r and r.get('w', 0) > 0]
        if _lv:
            _n = float(len(_lv))
            _w = sum(r['w'] for r in _lv) / _n
            _fg = sum(r.get('f2iso_gap', 0.0) for r in _lv) / _n
            _ps = sum(r.get('passive', 0.0) for r in _lv) / _n
            # 림프를 많이 하는 사람일수록 림프 레인지가 넓고 약하다.
            _lg = max((r.get('limp_gap', 0.0) for r in _lv), default=0.0)
            thr *= max(0.70, min(1.60,
                       1.0 + _w*(0.45*max(0.0, _fg) + 0.25*max(0.0, _ps))
                       + 0.30*max(0.0, _lg)))

    r = legacy_preflop_order_percentile(hand)
    _timing_bound({'kind': 'iso', 'r': float(r), 'thr': float(thr)})
    if r <= thr:
        return ('raise', 3.0 + n_limpers)

    # BB option: 추가 비용이 없으면 '폴드'나 '오버림프'가 아니라 체크다.
    if can_check:
        return ('check', 0)

    # 오버림프는 표시용 type 라벨(FISH/STATION)로 결정하지 않는다.
    # 같은 플레이어도 STUDIED_FISH / *_TILTY 라벨이 붙으면 행동이 바뀌는
    # 문제가 있었다. 기존 limp 동기(이론형+습관형)를 그대로 재사용한다.
    _lp = limp_p(prof, feel, r, pos, t, hand=hand)
    if r <= min(0.95, thr * 2.2) and rng.random() < _lp:
        return ('limp', 1.0)
    return ('fold', 0)


# vs_shove 는 제거했다. 에쿼티 함수를 인자로 받는 구형 인터페이스였고
# 호출부가 없었다. 올인 대면은 calloff_cap 이 맡는다.
def calloff_cap(prof, def_pos, opener_pos, bb, open_bb, raise_level,
                bf=1.0, exploit=None, n_callers=0, seats=8, ante=True):
    """올인 대면 콜 문턱. 일반 디펜스와 **다른 계산이다.**

    포스트플랍이 없다. 그래서
      - 임플라이드 오즈가 사라진다. 셋마이닝·수티드커넥터의 가치가 크게 준다
      - 순수 에쿼티 대 팟오즈 문제가 된다
      - ICM 이 가장 세게 걸린다. 지면 그 자리에서 탈락이다

    예전에는 올인 대면이 일반 레이즈와 같은 경로로 처리됐다
    (defend_decision 호출의 16.7% 가 올인 대면인데 ICM 이 안 걸렸다).
    calloff_decision 은 존재했지만 호출부가 없었고, 구형 아키타입 라벨에
    의존해 개념 벡터를 무시했다.
    """
    tp, tot = defend_thresholds(prof, def_pos, opener_pos, bb, open_bb,
                                n_callers, raise_level, seats, ante)
    # 참가 폭에서 시작해 단계별로 좁힌다. 3벳 올인보다 5벳 올인이 훨씬 좁다.
    cap = tot * CALLOFF_TIGHTEN.get(raise_level + 1, 0.07) * 2.6

    # 임플라이드 오즈 소멸 — 스택이 깊을수록 잃는 것이 크다.
    # 얕으면 어차피 셋마이닝이 안 되므로 차이가 없다.
    cap *= 1.0 - 0.18 * _DP.base_feel(bb)

    # ICM. 여기가 콜오프에서 가장 큰 항이다.
    cap /= max(1.0, float(bf or 1.0))

    if exploit and exploit.get('w', 0) > 0:
        w = exploit['w']
        # 아무 핸드나 쇼브하는 상대에겐 넓게 받는다.
        og = exploit.get('open_gap', 0.0)
        tbg = exploit.get('tb_gap', 0.0)
        cap *= max(0.5, min(2.0, 1.0 + w*(0.45*og + 0.60*max(0.0, tbg))))
    return max(0.005, min(0.85, cap))


def calloff_ev_comparison(hand, legacy_action, legacy_cap, call_ev_shadow,
                          bubble_factor=1.0):
    """F8-D6-D1 shadow: percentile calloff와 layer-EV+ICM 판단을 나란히 비교.

    실제 action을 바꾸지 않는다.
    """
    sh = dict(call_ev_shadow or {})
    if not sh.get('pure_calloff') or not sh.get('complete'):
        return None
    eq = sh.get('effective_equity')
    cost = sh.get('call_cost')
    total_after = sh.get('contestable_after_call')
    if eq is None or cost is None or total_after is None:
        return None
    cost = float(cost)
    total_after = float(total_after)
    pot_before = max(0.0, total_after - cost)
    need = _ICM.required_equity(
        pot_before, cost, max(1.0, float(bubble_factor or 1.0)))
    ev_action = 'call' if float(eq) >= float(need) else 'fold'
    legacy = legacy_action[0] if isinstance(legacy_action, tuple) else legacy_action
    return {
        'hand_pct': round(float(legacy_preflop_order_percentile(hand)), 6),
        'legacy_action': legacy,
        'legacy_cap': round(float(legacy_cap), 6),
        'layer_effective_equity': round(float(eq), 6),
        'chip_breakeven_equity': sh.get('breakeven_equity'),
        'bubble_factor': round(max(1.0, float(bubble_factor or 1.0)), 6),
        'icm_required_equity': round(float(need), 6),
        'layer_ev_action': ev_action,
        'agree': bool(legacy == ev_action),
        'strategy_consumer': False,
    }


def pf_defend_exact_calc_gate(prof):
    """정확한 프리플랍 콜오프 계산을 실제로 실행할 확률 0~1 (pf_defend 개념).

    pf_defend 개념의 '추론 게이트' 역할이다(ledger L033/L078). 같은 개념의
    차트 기억 역할(gto_knowledge('defend'))과 질문이 다르다. 통과하지 못하면
    legacy 콜오프 폭(legacy_calloff_likelihoods)의 행동이 남는다.
    """
    return max(0.0, min(1.0, float(PS.gate(prof, 'pf_defend'))))


def calloff_by_price(effective_equity, required_equity):
    """올인 콜오프의 수학적 판단: equity ≥ 필요 equity 이면 call."""
    return 'call' if float(effective_equity) >= required_equity else 'fold'


def calloff_layer_judgment(prof, call_ev_shadow, bubble_factor=1.0,
                           seed=None):
    """F8-D6-D2: pure-calloff layer equity를 개인이 실제로 적용한 판단.

    factual input:
      - observer-perceived seat ranges
      - exact layer equity / exact call price

    personal application:
      - icm_bf: 객관 BF를 이 사람이 인식한 BF로
      - potodds calc_noise: 계산 정확도
      - pf_defend gate: 이 정확한 프리플랍 디펜스 계산을 실제로 실행하는가

    새 side-pot 계수나 새 성향 축은 만들지 않는다.
    """
    sh = dict(call_ev_shadow or {})
    if not sh.get('pure_calloff') or not sh.get('complete'):
        return None
    eq = sh.get('effective_equity')
    cost = sh.get('call_cost')
    total_after = sh.get('contestable_after_call')
    if eq is None or cost is None or total_after is None:
        return None

    cost = float(cost)
    total_after = float(total_after)
    pot_before = max(0.0, total_after - cost)
    bf_true = max(1.0, float(bubble_factor or 1.0))
    bf_seen = (
        PS.icm_bf(prof, bf_true)
        if isinstance(prof, dict) and prof.get('concepts')
        else bf_true)
    need_base = _ICM.required_equity(pot_before, cost, bf_seen)

    # New consumer must not consume the shared decision RNG.
    base_seed = int(seed or 0)
    noise_seed = zlib.crc32(('%s|potodds' % base_seed).encode())
    gate_seed = zlib.crc32(('%s|pf_defend_gate' % base_seed).encode())
    noise = 1.0
    gate_p = 1.0
    if isinstance(prof, dict) and prof.get('concepts'):
        noise = PS.calc_noise(
            prof, 'potodds', random.Random(noise_seed))
        noise = max(0.65, min(1.55, float(noise)))
        gate_p = pf_defend_exact_calc_gate(prof)

    need_seen = max(0.01, min(0.95, float(need_base) * noise))
    layer_action = calloff_by_price(eq, need_seen)
    gate_roll = random.Random(gate_seed).random()
    gate_pass = bool(gate_roll < gate_p)

    return {
        'layer_effective_equity': round(float(eq), 6),
        'objective_bubble_factor': round(bf_true, 6),
        'perceived_bubble_factor': round(float(bf_seen), 6),
        'icm_required_equity_before_calc_error': round(float(need_base), 6),
        'potodds_noise': round(float(noise), 6),
        'perceived_required_equity': round(float(need_seen), 6),
        'layer_action': layer_action,
        'pf_defend_gate_p': round(float(gate_p), 6),
        'pf_defend_gate_roll': round(float(gate_roll), 6),
        'gate_pass': gate_pass,
        'noise_seed': int(noise_seed),
        'gate_seed': int(gate_seed),
    }


def calloff_decision(prof, def_pos, hand, bb, raise_level, pot, tocall,
                     bubble_factor=1.0, opener_pos='CO', open_bb=None,
                     exploit=None, n_callers=0, seats=8, ante=True):
    """올인 대면 콜/폴드. 반환: (액션, 문턱)

    현재 cap 모델은 아직 percentile 기반이며 pot/tocall을 전략식에 직접
    사용하지 않는다. 두 값은 호출 문맥을 정확히 보존하기 위해 받는다.
    pot-odds/equity 직접 비교는 P6 전략 리팩터링의 남은 항목이다.
    """
    cap = calloff_cap(prof, def_pos, opener_pos, bb,
                      open_bb if open_bb is not None else tocall,
                      raise_level, bubble_factor, exploit, n_callers,
                      seats, ante)
    r = legacy_preflop_order_percentile(hand)
    return (('call', tocall) if r <= cap else ('fold', 0)), cap
