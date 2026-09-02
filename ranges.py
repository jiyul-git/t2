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
                  opener_pos=None, open_bb=2.5, seats=8, ante=True, polar=0.0):
    """액션 경로로부터 그 플레이어의 프리플랍 레인지.
       call/3bet은 실제 디펜스 역치와 동일한 구간을 쓴다 (중첩 없음)."""
    base = _base_open(prof_type, pos, seats, bb, ante)
    t = _traits(prof_type)
    lo, hi = 0.0, 0.35
    if action == 'open':
        hi = base            # 깊이는 _open 안에서 이미 반영됨
    elif action == 'limp':
        hi = min(0.85, base * 2.6)
    elif action in ('call','3bet'):
        if opener_pos:
            tp, tot = _def_thresholds(prof_type, pos, opener_pos, bb, open_bb, n_callers)
            lo, hi = (0.0, tp) if action == '3bet' else (tp, tot)
        else:
            hi = t['threebet']*3.0 if action == '3bet' else min(0.85, t['call']*2.4)

    ok = lambda c: c[0] not in dead and c[1] not in dead
    if action == '3bet' and polar > 0.02:
        # **폴라라이즈된 3벳 레인지는 상위 N% 슬라이스가 아니다.**
        # 밸류 덩어리(위)와 블러프 덩어리(아래)가 따로 있고 가운데가 비어 있다.
        # 슬라이스로 만들면 로우 오프숏이 아예 안 들어가서,
        # 상대가 그걸로 3벳한다는 것을 플랍 계획이 가정하지 못한다.
        val_hi = hi * (1.0 - 0.55*polar)                  # 밸류 몫은 줄고
        blf_lo = min(0.90, hi + 0.10 + 0.25*polar)        # 아래쪽에서 블러프를 뽑는다
        blf_hi = min(0.95, blf_lo + (hi - val_hi) * 2.2)
        out = []
        for c in _SORTED:
            if not ok(c):
                continue
            v = pf.PCT[pf.cls(list(c))]
            if v <= val_hi or (blf_lo < v <= blf_hi):
                out.append(c)
        return out
    return [c for c in _SORTED
            if lo < pf.PCT[pf.cls(list(c))] <= hi and ok(c)]

def narrow(r, board, keep_frac, mode='top'):
    if not board or not r: return r
    ranked = sorted(r, key=lambda c: bot.eval7(list(c)+board), reverse=True)
    k = max(1, int(len(ranked)*keep_frac))
    return ranked[:k] if mode == 'top' else ranked[-k:]

# betting_range 는 bot.betting_range 하나만 쓴다.
# (여기 있던 사본은 호출부가 없었고 시그니처·로직이 갈라져 있어 제거)
def range_advantage(r_a, r_b, board, sims=180, seed=None):
    """전체 에쿼티 우위. −1~1.

    nut_advantage 와 다른 것을 잰다.
      range_advantage — 레인지 **전체**가 이 보드에서 유리한가 -> 얼마나 자주 칠까
      nut_advantage   — **최상단** 구간을 누가 더 갖고 있나 -> 얼마나 크게 칠까
    둘 다 있어야 '자주 작게'와 '드물게 크게'가 구분된다.
    """
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

# strong_shares 는 _strong_share 를 감싼 표시용 래퍼였고 호출부가 없었다.
# nut_advantage 가 같은 재료를 쓰므로 제거한다.

def blocker_score(hero, opp_range, board):
    """내 카드가 상대의 강한 콤보를 얼마나 지우는가. 0~1.

    **근사값이다.** 정확히는 blocker_effect 를 쓸 것 —
    강한 콤보를 지우는 것과 '콜할 콤보'를 지우는 것은 다르다.
    이 함수는 상대 벳 사이즈를 모를 때의 폴백으로 남긴다.
    """
    if not opp_range or not board: return 0.0
    strong = sorted(opp_range, key=lambda c: bot.eval7(list(c)+board), reverse=True)
    strong = strong[:max(4, len(strong)//5)]
    return sum(1 for c in strong if c[0] in hero or c[1] in hero)/len(strong)


def blocker_effect(hero, opp_range, board, street, size_frac, for_value=False):
    """블로커의 **순 효과**. -1 ~ +1.

    핵심은 '강한 콤보를 지웠나'가 아니라
    **'내 벳을 마주하면 콜할 콤보를 지웠나'** 이다.

      블로커   — 상대의 콜 몫을 지운다  -> 블러프가 잘 통한다
      언블로커 — 상대의 폴드 몫을 지운다 -> 남은 레인지가 더 강해져 손해다

    예: K9 4 2 7 (스페이드 셋) 리버에서 J♠T 로 블러프.
    J♠ 는 상대의 **약한 플러시**를 지운다. 그건 큰 벳에 접었을 패다.
    접을 패를 지웠으니 상대의 남은 레인지가 더 강해지고 블러프가 덜 먹힌다.
    강한 콤보만 세는 방식으로는 이 손해가 보이지 않는다.

    밸류로 칠 때는 부호가 뒤집힌다. 상대가 콜해줘야 벌 수 있으므로
    콜 몫을 지우는 것이 손해다.
    """
    if not opp_range or not board:
        return 0.0
    calls = set(_call_range(opp_range, board, street, size_frac))
    folds = [c for c in opp_range if c not in calls]
    if not calls or not folds:
        return 0.0
    hit = lambda c: (c[0] in hero or c[1] in hero)
    blocked_call = sum(1 for c in calls if hit(c)) / len(calls)
    blocked_fold = sum(1 for c in folds if hit(c)) / len(folds)
    net = blocked_call - blocked_fold
    return max(-1.0, min(1.0, -net if for_value else net))


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


def _bet_range(r, board, street, bluff_axis, size_frac, damp=1.0, barrel=0.0):
    """벳/레이즈: 양극화. 사이즈가 클수록 밸류가 좁고 블러프 비중이 커진다."""
    ranked = _ranked(r, board)
    n = len(ranked)
    # **고정 상수였다.** 닛이 턴에 배럴하든 매니악이 하든 같은 상위 30% 로
    # 좁혀졌다. 실제로는 닛의 턴 배럴이 상위 15%, 매니악이 55% 다.
    # barrel_gap 은 그 사람의 배럴 빈도가 기준보다 얼마나 넓은가(−1~+1).
    vfrac = {'flop': 0.42, 'turn': 0.30, 'river': 0.22}.get(street, 0.32)
    vfrac = max(0.08, min(0.85, vfrac * (1.0 + 1.15*barrel)))
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


def perceived_range(base, board, acts, profile=None, actor_read=None):
    """이 사람이 **실제로 인식하는** 상대 레인지.

    개념을 아는 것과 그 정보가 판단에 들어오는 것은 다르다.
    range_read 가 낮은 사람은 '상대가 어떤 액션을 밟아왔는가'를
    레인지에 반영하지 못한다. 그런 사람에게는 상대가 3배럴을 하든
    체크만 하든 레인지가 거의 그대로다.

    예전에는 이 축소가 range_read 와 무관하게 항상 완전히 적용돼서,
    피시도 레귤러와 똑같이 정밀한 상대 레인지를 얻었다.
    """
    if not profile or not profile.get('concepts'):
        return narrow_by_actions(base, board, acts, actor_read, profile)
    rr = PS.sk(profile, 'range_read')
    if rr < 1.5:
        return list(base)                     # 액션을 아예 반영 못 한다
    full = narrow_by_actions(base, board, acts, actor_read, profile)
    grasp = min(1.0, (rr - 1.5) / 6.0)        # rr 7.5 이상이면 완전 반영
    if grasp >= 0.98 or not full:
        return full
    # 부분 인식: 좁혀진 레인지와 원본 사이를 섞는다.
    # '어렴풋이 안다'는 좁힌 레인지 + 원본 잔여로 표현된다.
    keep = set(full)
    rest = [c for c in base if c not in keep]
    n_extra = int(len(rest) * (1.0 - grasp))
    return full + rest[:n_extra]


def narrow_by_actions(base, board, acts, actor_read=None, observer=None):
    """관측된 포스트플랍 액션 경로로 레인지를 순차 축소한다.

    acts — [(street, action, size_frac), ...] 관측 순서대로.
           size_frac 은 그 시점 팟 대비 베팅 비율(모르면 0.0).

    **인자가 둘이다. 예전에는 하나였고 그게 뒤섞여 있었다.**
      actor_read — 레인지의 주인(상대)에 대한 읽기. read_opponent 결과.
                   블러프 성향·씨벳 성향은 **그 사람의 것**이어야 한다.
      observer   — 이 축소를 수행하는 사람. 인식 한계는 perceived_range 가 건다.

    예전에는 관찰자 프로필 하나만 받아 거기서 bluff/cbet 을 꺼냈다.
    그래서 **자기 블러프 성향으로 상대 레인지를 좁혔다** — 자기 투사다.
    블러프를 많이 하는 사람일수록 상대도 블러프가 많다고 가정했다.
    """
    if not board or not base:
        return base
    # 기본값은 필드 평균. 읽기가 없으면 상대를 평균으로 가정한다.
    bluff = 5.0
    cbet = 5.0
    barrel = 0.0
    if actor_read and actor_read.get('w', 0) > 0:
        w = actor_read['w']
        # bluff_gap −1~+1 을 1~10 축으로 되돌린다.
        bluff = max(1.0, min(10.0, 5.0 + 5.0*actor_read.get('bluff_gap', 0.0)*w))
        # 씨벳 성향은 '체크했다'의 정보량을 정한다.
        # 자주 치는 사람의 체크는 강한 신호, 안 치는 사람의 체크는 정보가 없다.
        cbet = max(1.0, min(10.0, 5.0 - 5.0*actor_read.get('passive', 0.0)*w))
        barrel = max(-1.0, min(1.0, actor_read.get('barrel_gap', 0.0)))
    r = list(base)
    floor = max(_MIN_KEEP, int(len(base)*_MIN_FRAC))
    step = 0
    for (stt, a, sz) in acts:
        if len(r) <= floor:
            break
        # 연속 액션일수록 추가 정보량이 줄어든다 (축소 누적 폭주 방지)
        d = _DECAY ** step
        if a in ('bet', 'raise', 'allin'):
            r = _bet_range(r, board, stt, bluff, sz, d, barrel)
        elif a == 'call':
            r = _call_range(r, board, stt, sz, d)
        elif a == 'check':
            r = _check_range(r, board, stt, cbet, d)
        else:
            continue                      # fold 는 살아있는 상대에게 나오지 않는다
        step += 1
    return r if r else list(base)
