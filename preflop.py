import json, os, random
import persona as PS
import depth as _DP
D = os.path.dirname(os.path.abspath(__file__))
PCT = json.load(open(os.path.join(D, 'pf_rank.json'), encoding='utf-8'))
RV = {r: i+2 for i, r in enumerate("23456789TJQKA")}

def cls(c):
    v = sorted([c[0][0], c[1][0]], key=lambda x: -RV[x])
    if c[0][0] == c[1][0]: return v[0]+v[1]
    return v[0]+v[1]+('s' if c[0][1] == c[1][1] else 'o')

def pct(c): return PCT[cls(c)]

# ---------- 아키타입 ----------
import archetypes as A
import persona as PS

BASE_OPEN = {n: A.open_range(n) for n in A.all_names()}   # 구형 호환
TRAITS    = {n: A.traits(n)     for n in A.all_names()}

def _open(prof, pos, seats=8, bb=100.0, ante=True):
    """오픈 폭. 깊이·안테·좌석수가 이미 반영된 값을 돌려준다.

    호출부에서 DEPTH_OPEN_MULT 를 또 곱하지 말 것.
    깊이는 gto.rfi 안에서 한 번만 적용된다.
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
DEF_POS_MULT = {'BB':1.0,'SB':0.55,'BTN':0.9,'CO':0.7,'HJ':0.6,'LJ':0.5,'UTG+2':0.47,'UTG+1':0.45,'UTG':0.4}

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
DEPTH_OPEN_MULT = {'micro':2.40,'short':1.75,'mid':1.35,'normal':1.0,'deep':0.95}

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


def limp_p(prof, feel, hand_pct, pos, traits=None):
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
    acc = 0.10 + 0.80*min(1.0, PS.sk(prof, 'pf_range')/8.0) if prof.get('concepts') else 0.5

    # --- 이론적 림프 ---
    # feel 0.12(=20bb) 아래에서만. 얕을수록 커진다.
    theory = max(0.0, min(1.0, (0.12 - feel) / 0.12))
    if hand_pct <= 0.03 or hand_pct > 0.30:
        theory *= 0.15          # 레인지가 좁다. 프리미엄도 최약체도 아니다
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


def open_form(prof, feel, hand_pct, bb, rng, vs=0.0, traits=None):
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
    # 폴드에쿼티가 전부인 대역에서 최대. 프리미엄은 작게 올려 액션을 받는 게 낫다.
    if hand_pct <= 0.06:   shape = 0.45
    elif hand_pct <= 0.55: shape = 1.00
    else:                  shape = 0.30
    p_struct = struct * shape

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
    p_struct = crude*(1.0 - aware) + p_struct*aware

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


def open_decision(prof, pos, bb, hand, rng, behind_stacks=None,
                  tilt=0.0, field_q=0.6, bf=1.0, seats=8, ante=True,
                  field_avg_bb=None, erosion=0.0,
                  payout_flat=0.0, reentry=False, progress=0.0,
                  behind_reads=None, bb_chips=None, money_open=None):
    feel = feel_of(prof, bb, field_avg_bb, erosion, field_q, bf)
    t = _tr(prof)
    # 분산 추구: 실력 열세를 자각한 사람(또는 틸트난 사람)은 딥스택에서도
    # 프리플랍 쇼브로 간다. 포스트플랍이라는 스킬 구간을 없애 결과를
    # 카드에 수렴시키는 것이다. 못 이기니까 운으로 가는 것.
    vs = PS.variance_seek(prof, tilt, field_q, bb, bf, payout_flat, reentry, progress) if prof.get('concepts') else 0.0
    # 깊이 배수는 _open 안(gto.rfi)에서 이미 적용된다. 여기서 또 곱하면 이중이다.
    # 뒤 사람의 성향(3벳 위협)과 스택(리쇼브 위협)은 다른 압력이다.
    # 후자는 hotzone_pressure 가 재는데 호출부가 없어 죽어 있었다.
    thr = (_open(prof, pos, seats, bb, ante)
           * table_pressure(behind_reads)
           * hotzone_pressure(prof, pos, bb, behind_stacks or []))
    thr = min(0.9, thr + t['shove_add'] if feel < 0.20 else thr)
    r = pct(hand)
    # 같은 결정 상태에서 "머니점프가 없었다면"과 "있다면"을 정확히 비교하기
    # 위한 로컬 반사실. 진입 여부는 threshold 하나로 결정되므로 RNG 재생 없이
    # widen_entry / narrow_fold를 판정할 수 있다.
    _base_thr = thr
    # 머니점프 첫 행동 개입. 기준 레인지 자체를 새로 만들지 않고,
    # 기존 open threshold에 연속 factor만 곱한다.
    if money_open:
        try:
            thr *= max(0.0, float(money_open.get('range_factor', 1.0)))
        except (TypeError, ValueError):
            pass
        thr = max(0.0, min(0.9, thr))
        money_open['base_threshold'] = round(_base_thr, 6)
        money_open['money_threshold'] = round(thr, 6)
        money_open['hand_pct'] = round(r, 6)
        _base_in = (r <= _base_thr)
        _money_in = (r <= thr)
        money_open['range_cf'] = (
            'widen_entry' if (not _base_in and _money_in) else
            'narrow_fold' if (_base_in and not _money_in) else
            'unchanged')
    if r > thr: return ('fold', 0)
    # 쇼브 판정이 먼저다. 10bb 에서 림프를 먼저 물으면 쇼브해야 할 자리에서
    # 림프가 나온다(실제로 38% 나왔다). 얕으면 쇼브가 선택지를 먹는다.
    act, amt = open_form(prof, feel, r, bb, rng, vs, t)
    if act: return (act, amt)

    _base_limp_p = limp_p(prof, feel, r, pos, t)
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
        money_open['sb_limp_currently_blocked'] = bool(pos == 'SB')

    if _limp_roll < _base_limp_p and pos != 'SB':
        return ('limp', 1.0)
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
        # open_size_bb()는 runner.shape_size와 규칙상 최소레이즈 적용 전 값이다.
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

    # ---------- 1. 기하: 여기 걸리면 판단 이전에 이미 올인이다 ----------
    # 콜당했을 때의 팟: 내가 target, 상대가 (target - 이미 넣은 것)을 더 넣는다.
    # pot_bb 는 내가 치기 전의 팟(블라인드+오픈+콜러)이다.
    rem = stack_bb - target_bb
    pot_after = max(1.0, pot_bb + 2.0*target_bb - facing_bb)
    spr_after = rem / pot_after
    # 하드 게이트는 '논올인이라는 선택지가 실제로 없는' 구간에만 둔다.
    # 여기를 넓게 잡으면 아래 판단 층이 통째로 죽는다 —
    # 실제로 1.15 로 잡았더니 32bb 까지 100% 쇼브, 40bb 0% 인 새 계단이 됐다.
    if target_bb >= 0.75*stack_bb or spr_after < 0.50:
        return ('shove', stack_bb)      # 쳐놓고 접을 수 없다 = 형태만 다른 올인

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
        sh = min(1.0, sh + 0.20*(n_opp - 1))   # 다인원은 폴드에쿼티가 낮아 쇼브 쪽

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
    pos_mult = OPENER_MULT.get(opener_pos, 2.0) / 2.6
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


def defend_thresholds(prof, def_pos, opener_pos, bb, open_bb=2.5, n_callers=0,
                      raise_level=1, seats=8, ante=True):
    """디펜스 역치 (tp, tot) 를 내는 유일한 지점.

    tp  — 이 값 이하면 3벳 구간
    tot — 이 값 이하면 계속 참가(3벳+콜) 구간, 초과하면 폴드

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

    if not (isinstance(prof, dict) and prof.get('concepts')):
        tp, tot = _saturate(base_tp, base_tot)
    else:
        # 크기 <- 개념, 방향 <- 기질. 상한 0.90 (완벽한 사람은 없다)
        acc = 0.10 + 0.80*min(1.0, PS.sk(prof, 'pf_defend')/8.0)
        loose = PS.temper(prof, 'looseness', 5.0)
        aggr = PS.temper(prof, 'aggression', 5.0)
        d_call = max(-1.0, min(1.0, (loose - 5.0)/4.0))
        d_tb = max(-1.0, min(1.0, ((0.45*loose + 0.55*aggr) - 5.0)/4.0))
        tot = base_tot * (1.0 + (1.0-acc)*d_call*0.95)
        tp = base_tp * (1.0 + (1.0-acc)*d_tb*1.10)
        tp, tot = _saturate(tp, max(tp, tot))

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

    # 짧으면 콜 대신 쇼브/폴드. 콜 구간이 줄고 3벳 구간이 는다.
    if _DP.base_feel(bb) < 0.20:
        tp = min(tot, tp * 1.6)
        tot = max(tp, tot * 0.62)

    # 단계별 축소는 마지막에. 앞에서 하면 이후 곱셈이 좁아진 값을 되살린다.
    if raise_level >= 2:
        lt = LEVEL_TIGHTEN.get(raise_level+1, 0.10)
        tp *= lt
        tot = tp + (tot - tp) * (lt*0.8)
    return max(0.0, min(0.9, tp)), max(0.0, min(0.95, tot))


def defend_decision(prof, def_pos, opener_pos, hand, bb, open_bb, n_callers, rng,
                    raise_level=1, stack_bb=None, tilt=0.0, field_q=0.6,
                    exploit=None, bf=1.0,
                    payout_flat=0.0, reentry=False, progress=0.0,
                    seats=8, ante=True, opener_allin=False):
    """오픈(또는 오픈+콜러)에 대한 대응. 중첩 없는 연속 구간.

    exploit — persona.read_opponent() 결과. 상대 정보가 쌓이면
    3벳/콜 구간 자체가 움직인다. 정보가 없으면 w=0 이라 무보정.
    """
    # 올인 대면은 별도 경로다. 포스트플랍이 없으므로 계산이 다르다.
    _st = stack_bb if stack_bb is not None else bb
    if open_bb >= _st * 0.92:
        _a, _cap = calloff_decision(prof, def_pos, hand, bb, raise_level,
                                    1.5 + open_bb*(1 + n_callers), open_bb,
                                    bf, opener_pos, open_bb, exploit, n_callers)
        return _a
    vs = PS.variance_seek(prof, tilt, field_q, bb, bf, payout_flat, reentry, progress) if prof.get('concepts') else 0.0
    tp, tot = defend_thresholds(prof, def_pos, opener_pos, bb, open_bb,
                                n_callers, raise_level, seats, ante)
    if exploit and exploit.get('w', 0) > 0:
        w = exploit['w']
        if raise_level >= 2:
            # 3벳을 마주한 상황: 상대가 3벳을 남발하면 4벳/콜을 넓힌다.
            tbg = exploit.get('tb_gap', 0.0)
            tp = max(0.0, min(0.9, tp * (1.0 + w*1.3*tbg)))
            tot = max(tp, min(0.95, tot * (1.0 + w*0.8*tbg)))
            # 3벳 빈도만으로는 부족하다. '3벳은 자주 하는데 4벳에는 접는' 사람과
            # '4벳도 안 접는' 사람은 4벳 블러프 여부가 정반대다.
            # 3벳 레인지가 폴라라이즈됐으면 아래 덩어리가 크다는 뜻이다.
            # 폴드가 아니라 **참여**로 대응한다 — 콜을 넓히고 4벳을 넓힌다.
            pol = exploit.get('tb_polar', 0.0)
            if pol > 0.02:
                tot = max(tot, min(0.95, tot * (1.0 + w*0.85*pol)))
                tp = max(0.0, min(0.9, tp * (1.0 + w*1.10*pol)))
            f2fb = exploit.get('f2fb_gap', 0.0)
            tp = max(0.0, min(0.9, tp * (1.0 + w*1.5*f2fb)))
            tot = max(tp, min(0.95, tot * (1.0 - w*0.5*f2fb)))
        else:
            # 오픈을 마주한 상황: 상대가 3벳에 잘 접으면 3벳을 넓힌다.
            # 포스트플랍 폴드율이 아니라 '3벳 대면 폴드율'을 봐야 한다.
            # 상대가 기준보다 넓게 열면 그 레인지가 약하다는 뜻이다.
            # 절대 VPIP 가 아니라 '그 자리 기준의 몇 배'라 포지션 보정이 필요 없다.
            og = exploit.get('open_gap', 0.0)
            if abs(og) > 1e-6:
                tot = max(tot, min(0.95, tot * (1.0 + w*0.55*og)))
                tp = max(0.0, min(0.9, tp * (1.0 + w*0.45*og)))
            f2tb = exploit.get('f2tb_gap', exploit.get('fold_gap', 0.0))
            tp = max(0.0, min(0.9, tp * (1.0 + w*1.5*f2tb)))
            tot = max(tp, min(0.95, tot * (1.0 - w*0.5*f2tb)))
            # 4벳을 자주 하는 상대에게 라이트 3벳은 손해다. 3벳 구간만 줄이고
            # 참가 폭(tot)은 유지한다 — 3벳 대신 콜로 흡수되어야 한다.
            fbg = exploit.get('fb_gap', 0.0)
            if fbg > 0:
                # 줄어드는 건 라이트 3벳이다. 4벳 머신을 상대로도 밸류 3벳은
                # 오히려 늘어야 하므로 상위 6%(밸류 코어)는 바닥으로 남긴다.
                # 하한이 없으면 fb_gap 이 커질 때 3벳 자체가 사라진다.
                tp = max(min(tp, 0.06), tp * (1.0 - w*1.1*fbg))
    r = pct(hand)
    # --- 핫존 리쇼브: 콜 대신 3벳 올인 (혼합) ---
    if stack_bb is not None and in_hotzone(stack_bb) and raise_level == 1:
        rs = reshove_range(prof, def_pos, opener_pos, stack_bb, open_bb, n_callers)
        if r <= rs:
            # 역치 안쪽일수록 쇼브 비중이 높고, 경계에서는 콜/폴드와 섞인다
            depth = 1.0 - (r / max(1e-6, rs))          # 0(경계)~1(최상위)
            p_shove = 0.30 + 0.60*depth
            if rng.random() < p_shove:
                # reshove_range 는 '이 핸드가 짧은 스택 3벳 구간인가'만 정한다.
                # 형태(올인/논올인)는 raise_form 한 곳에서만 정한다 —
                # 여기서 바로 shove 를 반환하면 같은 결정을 두 곳에서 하게 된다.
                _tgt = open_bb*(reraise_mult(1, def_pos) + 1.0*n_callers)
                _act, _sz = raise_form(prof, stack_bb, _tgt,
                                       1.5 + open_bb*(1 + n_callers), rng,
                                       exploit=exploit, level=1,
                                       n_opp=1 + n_callers, facing_bb=open_bb)
                return (_act, _sz) if _act == 'shove' else ('3bet', _sz)
    # --- 혼합 전략 ---
    import math
    def logit(x, center, width):
        return 1.0/(1.0+math.exp((x-center)/max(1e-6, width)))
    a = prof_aggr(prof)
    # 3벳 가중치: 역치 안에서도 핸드가 약할수록 단조 감소
    w_raise = logit(r, tp, max(0.015, tp*0.35))
    w_raise *= (0.35 + 0.65*max(0.0, 1.0 - r/max(1e-6, tp)))   # tp 안에서 강도 비례
    w_raise *= (0.55 + 0.085*a)
    if (prof.get('concepts') and PS.sk(prof,'thin_value') < 3.5 and prof['temper']['aggression'] < 4.5) or \
       (not prof.get('concepts') and A.ARCHETYPES.get(prof.get('type'), (0,)*7+('reg',))[6] == 'fish'):
        w_raise *= (0.30 + 0.5*min(1.0, r/0.10))   # 수동형은 강할수록 오히려 덜 올림
    # 계속 참가 가중치
    w_cont = logit(r, tot, max(0.02, (tot-tp)*0.35))
    w_call = max(0.0, w_cont - w_raise*0.6) * (1.5 - 0.055*a)
    if (prof.get('concepts') and PS.sk(prof,'thin_value') < 3.5 and prof['temper']['aggression'] < 4.5) or \
       (not prof.get('concepts') and A.ARCHETYPES.get(prof.get('type'), (0,)*7+('reg',))[6] == 'fish'):
        w_call *= 1.9                              # 수동형은 콜로 받는다
    w_fold = max(0.0, 1.0 - w_cont)
    # 경계 절단: 프리미엄은 폴드 없음, 쓰레기는 3벳 없음
    if r <= 0.03:  w_fold = 0.0                 # AA/KK급은 폴드 없음
    if r <= 0.015: w_call *= 0.16               # 최상위 플랫은 드물게
    elif r <= 0.04: w_call *= 0.35
    # 어떤 액션도 100%가 되지 않도록 슬로우플레이 하한을 둔다
    slow = 0.04 + 0.012*(10-a)                  # 수동형일수록 슬로우플레이↑
    if w_raise > 0 and w_call >= 0:
        w_call = max(w_call, w_raise*slow)
    if r > tot*1.35: w_raise = 0.0              # 레인지 밖은 3벳 금지
    if r > tot:     w_call *= 0.15              # 레인지 밖 콜은 극히 드물게
    tot_w = w_raise + w_call + w_fold
    if tot_w <= 0: return ('fold', 0)
    x = rng.random()*tot_w
    if x < w_raise:
        mult = reraise_mult(raise_level, def_pos) + 1.0*n_callers
        target = open_bb*mult
        # 상대가 이미 올인이면 리레이즈할 대상이 없다. 그런데 open_bb 에
        # 올인 금액이 그대로 들어와서 '큰 오픈'으로 취급됐고, 거기에 3벳
        # 배수를 또 곱해 목표가 부풀었다(22bb 올인 -> target 66bb).
        # 그 목표는 raise_form 의 `spr_after < 0.50`(쳐놓고 접을 수 없다)에
        # 걸려 100% 쇼브가 됐다 — **100bb 가 22bb 를 상대로 통째로 올인.**
        # 올인 대면에서는 그 금액을 넘어설 이유가 없으므로 목표를 묶는다.
        if opener_allin:
            target = open_bb
        pot_bb = 1.5 + open_bb*(1 + n_callers)
        act, sz = raise_form(prof, stack_bb if stack_bb is not None else bb,
                             target, pot_bb, rng, exploit=exploit,
                             level=raise_level, n_opp=1 + n_callers,
                             facing_bb=open_bb)
        return (act, sz) if act == 'shove' else ('3bet', sz)
    if x < w_raise + w_call: return ('call', open_bb)
    return ('fold', 0)

def iso_decision(prof, pos, hand, n_limpers, bb, rng, limper_reads=None):
    t = _tr(prof)
    thr = _open(prof, pos) * (1.0 + 0.35*t['iso'])
    # 림퍼가 약할수록(잘 접고 수동적) 아이소를 넓힌다.
    # 예전에는 림퍼가 누군지 전혀 보지 않았다.
    if limper_reads:
        _lv = [r for r in limper_reads if r and r.get('w', 0) > 0]
        if _lv:
            _n = float(len(_lv))
            _w = sum(r['w'] for r in _lv) / _n
            _fg = sum(r.get('fold_gap', 0.0) for r in _lv) / _n
            _ps = sum(r.get('passive', 0.0) for r in _lv) / _n
            # 림프를 많이 하는 사람일수록 림프 레인지가 넓고 약하다.
            _lg = max((r.get('limp_gap', 0.0) for r in _lv), default=0.0)
            thr *= max(0.70, min(1.60,
                       1.0 + _w*(0.45*max(0.0, _fg) + 0.25*max(0.0, _ps))
                       + 0.30*max(0.0, _lg)))   # iso 는 깊이 미반영(기존 유지)
    r = pct(hand)
    if r <= thr and rng.random() < t['iso']:
        return ('raise', 3.0 + n_limpers)
    if r <= thr * 2.2 and prof['type'] in ('FISH','STATION'):
        return ('limp', 1.0)
    return ('fold', 0)


# vs_shove 는 제거했다. 에쿼티 함수를 인자로 받는 구형 인터페이스였고
# 호출부가 없었다. 올인 대면은 calloff_cap 이 맡는다.
def calloff_cap(prof, def_pos, opener_pos, bb, open_bb, raise_level,
                bf=1.0, exploit=None, n_callers=0):
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
                                n_callers, raise_level)
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


def calloff_decision(prof, def_pos, hand, bb, raise_level, pot, tocall,
                     bubble_factor=1.0, opener_pos='CO', open_bb=None,
                     exploit=None, n_callers=0):
    """올인 대면 콜/폴드. 반환: (액션, 문턱)"""
    cap = calloff_cap(prof, def_pos, opener_pos, bb,
                      open_bb if open_bb is not None else tocall,
                      raise_level, bubble_factor, exploit, n_callers)
    r = pct(hand)
    return (('call', tocall) if r <= cap else ('fold', 0)), cap
