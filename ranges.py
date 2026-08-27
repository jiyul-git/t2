import random
import bot
import preflop as pf

ALL = bot._ALLCOMBOS
_SORTED = sorted(ALL, key=lambda c: pf.PCT[pf.cls(list(c))])

def _def_thresholds(prof_type, def_pos, opener_pos, bb, open_bb=2.5, n_callers=0,
                    raise_level=1):
    """역치 계산은 preflop.defend_thresholds 하나뿐이다. 여기서 복제하지 않는다.

    이렇게 해야 '봇이 실제로 어떻게 방어하는가'와
    '상대 레인지를 어떻게 추정하는가'가 영원히 같은 값을 본다.
    """
    return pf.defend_thresholds(prof_type, def_pos, opener_pos, bb, open_bb,
                                n_callers, raise_level)

import persona as PS

# 오픈 폭·성향 조회도 preflop 의 것을 그대로 쓴다 (사본 금지).
_base_open = pf._open
_traits    = pf._tr

def preflop_range(prof_type, pos, action, bb, dead, n_callers=0,
                  opener_pos=None, open_bb=2.5):
    """액션 경로로부터 그 플레이어의 프리플랍 레인지.
       call/3bet은 실제 디펜스 역치와 동일한 구간을 쓴다 (중첩 없음)."""
    base = _base_open(prof_type, pos)
    t = _traits(prof_type)
    lo, hi = 0.0, 0.35
    if action == 'open':
        hi = base * pf.DEPTH_OPEN_MULT[pf.depth_band(bb)]
    elif action == 'limp':
        hi = min(0.85, base * 2.6)
    elif action in ('call','3bet'):
        if opener_pos:
            tp, tot = _def_thresholds(prof_type, pos, opener_pos, bb, open_bb, n_callers)
            lo, hi = (0.0, tp) if action == '3bet' else (tp, tot)
        else:
            hi = t['threebet']*3.0 if action == '3bet' else min(0.85, t['call']*2.4)
    return [c for c in _SORTED
            if lo < pf.PCT[pf.cls(list(c))] <= hi and c[0] not in dead and c[1] not in dead]

def narrow(r, board, keep_frac, mode='top'):
    if not board or not r: return r
    ranked = sorted(r, key=lambda c: bot.eval7(list(c)+board), reverse=True)
    k = max(1, int(len(ranked)*keep_frac))
    return ranked[:k] if mode == 'top' else ranked[-k:]

# betting_range 는 bot.betting_range 하나만 쓴다.
# (여기 있던 사본은 호출부가 없었고 시그니처·로직이 갈라져 있어 제거)
def range_advantage(r_a, r_b, board, sims=250, seed=None):
    rng = random.Random(seed)
    if not r_a or not r_b: return 0.0
    w = 0.0; run = 0
    for _ in range(sims):
        a = list(rng.choice(r_a)); b = list(rng.choice(r_b))
        if set(a) & set(b) or set(a+b) & set(board): continue
        run += 1
        ea, eb = bot.eval7(a+board), bot.eval7(b+board)
        w += 1 if ea > eb else (0.5 if ea == eb else 0)
    return 0.0 if run == 0 else (w/run - 0.5)*2

def _strong_share(r, board, cutoff=2):
    if not r: return 0.0
    n = ok = 0
    for c in r:
        if set(c) & set(board): continue
        n += 1
        if bot.eval7(list(c)+board)[0] >= cutoff: ok += 1
    return ok/n if n else 0.0

def nut_advantage(r_a, r_b, board):
    """넛 구간 점유율 차이. -1~1."""
    if not board or not r_a or not r_b: return 0.0
    t_a, t_b = _strong_share(r_a, board, 2), _strong_share(r_b, board, 2)
    s_a, s_b = _strong_share(r_a, board, 3), _strong_share(r_b, board, 3)
    return max(-1.0, min(1.0, (0.5*(t_a-t_b) + 0.5*(s_a-s_b))*6))

def strong_shares(r_a, r_b, board):
    return {'A_2p+': round(_strong_share(r_a,board,2),3), 'B_2p+': round(_strong_share(r_b,board,2),3),
            'A_set+': round(_strong_share(r_a,board,3),3), 'B_set+': round(_strong_share(r_b,board,3),3)}

def blocker_score(hero, opp_range, board):
    """내 카드가 상대의 강한 콤보를 얼마나 지우는가. 0~1."""
    if not opp_range or not board: return 0.0
    strong = sorted(opp_range, key=lambda c: bot.eval7(list(c)+board), reverse=True)
    strong = strong[:max(1, len(strong)//5)]
    return sum(1 for c in strong if c[0] in hero or c[1] in hero)/len(strong)


# ---------- 액션 경로에 따른 레인지 축소 ----------
# 프리플랍 레인지를 매 스트리트 그대로 쓰면 "상대가 왜 이 액션을 했는가"가
# 전혀 반영되지 않는다. 아래는 관측된 액션마다 남을 수 있는 콤보만 남긴다.
# 강도 기준은 bot._sd_strength (완성 강도 + 드로우 지분) 하나만 쓴다.

_MIN_KEEP = 12          # 이 밑으로는 줄이지 않는다 (표본이 죽으면 추정이 무의미)
_MIN_FRAC = 0.10        # 원본 레인지의 이 비율 밑으로도 줄이지 않는다
_DECAY    = 0.75        # 연속 액션의 정보량 감쇠

def _ranked(r, board):
    return sorted(r, key=lambda c: bot._sd_strength(c, board), reverse=True)


def _damp(frac, d):
    """축소 강도를 완화한다. d=1 이면 그대로, d 가 작을수록 덜 자른다.

    같은 상대가 연속으로 공격하면 두 번째·세 번째 액션의 추가 정보량은 줄어든다.
    이미 강함을 대표하고 있기 때문이다. 매번 '남은 것의 상위 X%'를 다시 취하면
    원본의 3% 같은 값이 나오고, 그러면 상대가 항상 넛인 것처럼 보여 과잉 폴드한다.
    """
    return 1.0 - (1.0 - frac)*d


def _bet_range(r, board, street, bluff_axis, size_frac, damp=1.0):
    """벳/레이즈: 양극화. 사이즈가 클수록 밸류가 좁고 블러프 비중이 커진다."""
    ranked = _ranked(r, board)
    n = len(ranked)
    vfrac = {'flop': 0.42, 'turn': 0.30, 'river': 0.22}.get(street, 0.32)
    if size_frac >= 1.0:   vfrac *= 0.60          # 오버벳은 극단적으로 양극화
    elif size_frac >= 0.7: vfrac *= 0.78
    elif size_frac <= 0.35: vfrac *= 1.45         # 소액은 넓고 머지드
    vfrac = _damp(vfrac, damp)
    nv = max(1, int(n*min(0.95, vfrac)))
    value = ranked[:nv]
    # 블러프 비중은 사이즈에서 유도한다 (bot.bluff_share 참조)
    nb = bot.bluff_count(nv, size_frac, street, bluff_axis)
    return value + bot.pick_bluffs(ranked, board, street, nb)


def _call_range(r, board, street, size_frac, damp=1.0):
    """콜: 최상위 일부는 올렸을 것이고, 최하위는 접었을 것이다. 가운데가 남는다."""
    ranked = _ranked(r, board)
    n = len(ranked)
    # 큰 벳에 콜할수록 아래쪽이 더 잘려나간다
    keep = {'flop': 0.62, 'turn': 0.48, 'river': 0.38}.get(street, 0.50)
    keep = _damp(keep * (1.25 - 0.45*min(1.5, size_frac)), damp)
    # 최상위는 대부분 레이즈했을 것이므로 콜 레인지에서 빠진다.
    # 다만 전부 빼면 슬로우플레이가 사라지므로 일부(trap_keep)만 남긴다.
    #
    # 예전에는 top_cut 만큼 잘라낸 lo 를 다시 결과에 더해서 최상위가
    # 하나도 안 잘렸다. 그래서 3배럴을 '콜만' 한 레인지에 풀하우스·쿼드가
    # 그대로 남았고, 콜 레인지가 벳 레인지보다 강해지는 역전이 생겼다.
    cut = max(1, int(n*0.18))                      # 이 위쪽은 레이즈했을 구간
    trap_keep = max(0, int(cut*0.25))              # 그중 함정으로 남기는 몫
    lo = ranked[:trap_keep]
    mid = ranked[cut:max(cut+1, int(n*min(0.95, keep)))]
    out = lo + mid
    return out if len(out) >= _MIN_KEEP else ranked[cut:cut+_MIN_KEEP] or ranked[:_MIN_KEEP]


def _check_range(r, board, street, cbet_axis, damp=1.0):
    """체크: 밸류의 일부는 벳했을 것이므로 최상위가 얇아진다. 나머지는 대부분 남는다."""
    ranked = _ranked(r, board)
    n = len(ranked)
    drop = int(n*0.10*min(1.0, cbet_axis/6.0)*damp)     # c-bet 성향이 높을수록 더 깎인다
    return ranked[drop:] if n - drop >= _MIN_KEEP else ranked


def narrow_by_actions(base, board, acts, profile=None):
    """관측된 포스트플랍 액션 경로로 레인지를 순차 축소한다.

    acts — [(street, action, size_frac), ...] 관측 순서대로.
           size_frac 은 그 시점 팟 대비 베팅 비율(모르면 0.0).
    """
    if not board or not base:
        return base
    bluff = 5.0
    cbet = 5.0
    if profile:
        bluff = profile.get('bluff', 5.0)
        if profile.get('concepts'):
            cbet = PS.sk(profile, 'cbet_flop')
    r = list(base)
    floor = max(_MIN_KEEP, int(len(base)*_MIN_FRAC))
    step = 0
    for (stt, a, sz) in acts:
        if len(r) <= floor:
            break
        # 연속 액션일수록 추가 정보량이 줄어든다 (축소 누적 폭주 방지)
        d = _DECAY ** step
        if a in ('bet', 'raise', 'allin'):
            r = _bet_range(r, board, stt, bluff, sz, d)
        elif a == 'call':
            r = _call_range(r, board, stt, sz, d)
        elif a == 'check':
            r = _check_range(r, board, stt, cbet, d)
        else:
            continue                      # fold 는 살아있는 상대에게 나오지 않는다
        step += 1
    return r if r else list(base)
