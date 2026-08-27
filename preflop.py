import json, os, random
import persona as PS
D = os.path.dirname(os.path.abspath(__file__))
PCT = json.load(open(os.path.join(D, 'pf_rank.json')))
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

def _open(prof, pos):
    """프로필 dict(개념 벡터 우선) 또는 라벨 문자열 둘 다 받는다."""
    if isinstance(prof, dict):
        if prof.get('concepts'): return PS.open_pct(prof, pos)[pos]
        prof = prof.get('type', 'TAG')
    return BASE_OPEN.get(prof, BASE_OPEN['TAG']).get(pos, 0.2)

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

OPENER_MULT = {'UTG':1.4,'UTG+1':1.5,'LJ':1.8,'HJ':2.2,'CO':2.9,'BTN':4.2,'SB':4.6}
DEF_POS_MULT = {'BB':1.0,'SB':0.55,'BTN':0.9,'CO':0.7,'HJ':0.6,'LJ':0.5,'UTG+1':0.45,'UTG':0.4}

# ---------- 스택 뎁스 ----------
def depth_band(bb):
    if bb < 8:   return 'micro'     # 순수 푸시/폴드
    if bb < 15:  return 'short'     # 쇼브 위주 + 소수 레이즈
    if bb < 25:  return 'mid'       # 레이즈/쇼브 혼합
    if bb < 60:  return 'normal'
    return 'deep'

DEPTH_OPEN_MULT = {'micro':2.40,'short':1.75,'mid':1.35,'normal':1.0,'deep':0.95}

def open_size_bb(band, pos, rng):
    if band == 'micro':  return 2.0                    # 실제로는 쇼브로 처리됨
    if band == 'short':  return 2.0                    # 쇼브 아니면 최소 사이즈
    if band == 'mid':    return rng.choice([2.0, 2.2])
    if band == 'normal': return rng.choice([2.2, 2.5])
    return rng.choice([2.5, 3.0])

def should_shove(band, hand_pct, traits, pos, bb):
    """레이즈 대신 오픈 쇼브할지."""
    if band == 'micro': return True
    if band == 'short':
        return hand_pct <= 0.55 or bb < 12
    if band == 'mid':
        # 폴드에쿼티가 전부인 경계 핸드만 쇼브
        return 0.15 < hand_pct <= 0.55 and bb < 22
    return False

def open_decision(prof, pos, bb, hand, rng, behind_stacks=None,
                  tilt=0.0, field_q=0.6):
    band = depth_band(bb)
    t = _tr(prof)
    # 분산 추구: 실력 열세를 자각한 사람(또는 틸트난 사람)은 딥스택에서도
    # 프리플랍 쇼브로 간다. 포스트플랍이라는 스킬 구간을 없애 결과를
    # 카드에 수렴시키는 것이다. 못 이기니까 운으로 가는 것.
    vs = PS.variance_seek(prof, tilt, field_q, bb) if prof.get('concepts') else 0.0
    thr = _open(prof, pos) * DEPTH_OPEN_MULT[band]
    thr = min(0.9, thr + t['shove_add'] if band in ('micro','short','mid') else thr)
    r = pct(hand)
    if r > thr: return ('fold', 0)
    # 림프는 미들~약한 핸드에 몰린다. 프리미엄은 거의 림프하지 않는다.
    limp_p = t['limp']
    if r <= 0.05:   limp_p *= 0.08          # 상위 5% (AQs+, TT+)
    elif r <= 0.12: limp_p *= 0.25
    elif r <= 0.25: limp_p *= 0.70
    else:           limp_p *= 1.35          # 약한 핸드일수록 림프 선호
    if rng.random() < limp_p and band in ('normal','deep') and pos != 'SB':
        return ('limp', 1.0)
    if should_shove(band, r, t, pos, bb): return ('shove', bb)
    # 분산 추구 오픈 쇼브.
    # 스택 상한이 중요하다. 실제로 '스킬 구간을 없애려고' 쇼브하는 건
    # 대략 60bb 이하에서다. 134bb 에서 AKs 를 쇼브하면 콜 레인지가
    # AA/KK 뿐이라 분산을 키우는 게 아니라 그냥 최악의 EV 다.
    # 예전에는 band 조건만 있고 상한이 없어 155bb 쇼브까지 나왔다.
    if vs > 0.12 and band == 'normal' and bb <= 60:
        p_sh = vs * (0.22 if r <= 0.10 else 0.12 if r <= 0.25 else 0.05)
        if rng.random() < p_sh:
            return ('shove', bb)
    sz = open_size_bb(band, pos, rng)
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


def hotzone_pressure(prof, pos, bb, behind_stacks):
    """뒤에 핫존 스택이 있으면 오픈 레인지를 줄인다 (리쇼브 압박)."""
    n_hot = sum(1 for s in behind_stacks if in_hotzone(s))
    if not n_hot: return 1.0
    aware = 1.0
    if prof.get('concepts'):
        import persona as _PS
        aware = min(1.2, _PS.sk(prof, 'spr')/6.0)   # 스택 인식이 낮으면 압박을 모름
    return max(0.55, 1.0 - 0.13*n_hot*aware)


def _tr_loose(prof):
    """루즈함 0~10. 개념 벡터가 없으면 call 성향에서 역산한다."""
    if isinstance(prof, dict) and prof.get('concepts'):
        return PS.temper(prof, 'looseness', 5.0)
    return max(0.0, min(10.0, _tr(prof)['call']/0.022))


def defend_thresholds(prof, def_pos, opener_pos, bb, open_bb=2.5, n_callers=0,
                      raise_level=1):
    """디펜스 역치 (tp, tot) 를 내는 유일한 지점.

    tp  — 이 값 이하면 3벳 구간
    tot — 이 값 이하면 계속 참가(3벳+콜) 구간, 초과하면 폴드

    defend_decision(실제 판단)과 ranges.preflop_range(상대 레인지 모델)이
    반드시 같은 구간을 보도록 여기 하나만 쓴다. 절대 복제하지 말 것.
    """
    t = _tr(prof)
    m = OPENER_MULT.get(opener_pos, 2.0) * DEF_POS_MULT.get(def_pos, 0.7)
    m *= (2.5 / max(1.5, open_bb)) ** 0.6
    if def_pos in ('BB','SB'): m *= 1.35      # BB 안테로 팟이 커져 방어 폭 확대
    tp = min(.85, t['threebet'] * m * (t['sqz'] if n_callers else 1.0) * (0.92 ** n_callers))
    # 다인원 플랫 축소율을 상수로 두면 안 된다.
    # 규율 있는 레귤러는 다인원에서 크게 조이지만 콜링 스테이션은 거의 신경 쓰지 않는다.
    # 상수로 두면 루즈한 필드일수록 다인원이 되어 축소가 세게 걸리고,
    # 결국 필드의 헐거움이 스스로를 상쇄해 어떤 필드든 같은 참여율로 수렴한다.
    loose = _tr_loose(prof)
    mw = max(0.45, min(0.95, 0.48 + 0.048*loose))       # 닛 0.53 / 스테이션 0.87
    cp = min(.85, t['call'] * m * (mw ** n_callers))
    if depth_band(bb) in ('micro','short','mid'):
        tp = tp * 1.6; cp *= 0.45                # 짧으면 콜 대신 쇼브/폴드
    tp, tot = _saturate(tp, tp+cp)
    # 포화 '이후'에 단계별 축소를 적용해야 좁아진 값이 되살아나지 않는다
    if raise_level >= 2:
        lt = LEVEL_TIGHTEN.get(raise_level+1, 0.10)
        tp *= lt
        tot = tp + (tot - tp) * (lt*0.8)
    return tp, tot


def defend_decision(prof, def_pos, opener_pos, hand, bb, open_bb, n_callers, rng,
                    raise_level=1, stack_bb=None, tilt=0.0, field_q=0.6,
                    exploit=None):
    """오픈(또는 오픈+콜러)에 대한 대응. 중첩 없는 연속 구간.

    exploit — persona.read_opponent() 결과. 상대 정보가 쌓이면
    3벳/콜 구간 자체가 움직인다. 정보가 없으면 w=0 이라 무보정.
    """
    band = depth_band(bb)
    vs = PS.variance_seek(prof, tilt, field_q, bb) if prof.get('concepts') else 0.0
    tp, tot = defend_thresholds(prof, def_pos, opener_pos, bb, open_bb,
                                n_callers, raise_level)
    if exploit and exploit.get('w', 0) > 0:
        w = exploit['w']
        if raise_level >= 2:
            # 3벳을 마주한 상황: 상대가 3벳을 남발하면 4벳/콜을 넓힌다.
            tbg = exploit.get('tb_gap', 0.0)
            tp = max(0.0, min(0.9, tp * (1.0 + w*1.3*tbg)))
            tot = max(tp, min(0.95, tot * (1.0 + w*0.8*tbg)))
        else:
            # 오픈을 마주한 상황: 상대가 3벳에 잘 접으면 3벳을 넓힌다.
            # 포스트플랍 폴드율이 아니라 '3벳 대면 폴드율'을 봐야 한다.
            f2tb = exploit.get('f2tb_gap', exploit.get('fold_gap', 0.0))
            tp = max(0.0, min(0.9, tp * (1.0 + w*1.5*f2tb)))
            tot = max(tp, min(0.95, tot * (1.0 - w*0.5*f2tb)))
    r = pct(hand)
    # --- 핫존 리쇼브: 콜 대신 3벳 올인 (혼합) ---
    if stack_bb is not None and in_hotzone(stack_bb) and raise_level == 1:
        rs = reshove_range(prof, def_pos, opener_pos, stack_bb, open_bb, n_callers)
        if r <= rs:
            # 역치 안쪽일수록 쇼브 비중이 높고, 경계에서는 콜/폴드와 섞인다
            depth = 1.0 - (r / max(1e-6, rs))          # 0(경계)~1(최상위)
            p_shove = 0.30 + 0.60*depth
            if rng.random() < p_shove:
                return ('shove', stack_bb)
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
        if band in ('micro','short','mid'): return ('shove', bb)
        mult = reraise_mult(raise_level, def_pos) + 1.0*n_callers
        target = open_bb*mult
        if stack_bb is not None and (target >= 0.55*stack_bb or stack_bb - target < open_bb*2):
            return ('shove', stack_bb)
        return ('3bet', target)
    if x < w_raise + w_call: return ('call', open_bb)
    return ('fold', 0)

def iso_decision(prof, pos, hand, n_limpers, bb, rng):
    t = _tr(prof)
    thr = _open(prof, pos) * (1.0 + 0.35*t['iso'])
    r = pct(hand)
    if r <= thr and rng.random() < t['iso']:
        return ('raise', 3.0 + n_limpers)
    if r <= thr * 2.2 and prof['type'] in ('FISH','STATION'):
        return ('limp', 1.0)
    return ('fold', 0)

def vs_shove(prof, hand, bb_risk, pot, tocall, bubble_factor, equity_fn):
    """숏스택 쇼브에 대한 콜오프. ICM 반영."""
    eq = equity_fn()
    need = (tocall * bubble_factor) / (pot + tocall)
    return ('call', tocall) if eq >= need else ('fold', 0)


def calloff_decision(prof, def_pos, hand, bb, raise_level, pot, tocall, bubble_factor=1.0):
    """올인(또는 커밋 사이즈)에 대한 콜 판단. 단계가 깊을수록 극단적으로 좁다."""
    t = TRAITS[prof['type']]
    base = (t['threebet'] + t['call']) * OPENER_MULT.get('CO', 2.5) * 0.5
    cap = base * CALLOFF_TIGHTEN.get(raise_level, 0.07)
    cap = min(0.85, cap * (1.0/max(1.0, bubble_factor)))
    r = pct(hand)
    return ('call', tocall) if r <= cap else ('fold', 0), cap
