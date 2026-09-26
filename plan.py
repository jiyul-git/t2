import random, zlib as _zlib, hashlib as _hashlib
import bot, ranges as R, preflop as pf, archetypes as A, persona as PS, texture as TX

PLANS = ['value_3street','value_2street','pot_control','semibluff','bluff_2street',
         'giveup','trap','block']

def spr(stack, pot): return stack/max(1, pot)

def line_bluff_prior(opp_profile, street, n_barrels, sizing_frac, board, aggressor_pos_oop):
    """주의: opp_profile 은 '관찰로 추정된' 프로필이어야 한다.
       reads.perceived_profile() 결과를 넘길 것. 진짜 축을 넘기면 정보 누출."""
    """상대의 '이 라인'이 블러프일 사전확률. 0~1.
       성향(블러프축) × 배럴 수 × 사이징 × 보드 × 포지션."""
    base = opp_profile.get('bluff', 5)/10.0
    b = base
    b *= {1: 1.00, 2: 0.72, 3: 0.48}.get(n_barrels, 0.40)   # 배럴 겹칠수록 블러프↓
    if sizing_frac >= 1.0:   b *= 1.25                       # 오버벳은 양극화
    elif sizing_frac <= 0.35: b *= 0.75                      # 소액은 밸류/머지
    b *= (1.0 + 0.35*bot.board_danger(board))                    # 젖은 보드면 블러프↑
    if aggressor_pos_oop: b *= 0.80                          # OOP 리드는 블러프↓
    if street == 'river':  b *= 0.85
    return max(0.02, min(0.85, b))

def board_paired(board):
    rs = [c[0] for c in board]
    return len(set(rs)) < len(rs)

_RS_CACHE={}
def relative_strength(hero, board, opp_range=None):
    """상대의 '벳할 만한' 레인지 중 나를 이기는 비율의 역수. 0(최하)~1(넛).
       전체 랜덤이 아니라 실제 레인지 기준이라 낮은 플러시가 제대로 낮게 나온다."""
    if len(board) < 3: return 0.5
    # 레인지 크기만으로는 서로 다른 레인지를 구분하지 못한다 → 내용 해시 사용.
    # 단 파이썬 내장 hash() 는 문자열에 대해 프로세스마다 값이 달라지고(PYTHONHASHSEED),
    # XOR 로 합치면 순서를 무시해 서로 다른 레인지가 같은 키로 충돌한다.
    # 캐시가 프로세스 안에서 대회 간에 남으므로 그대로 재현성 붕괴로 이어진다.
    # crc32 + 정렬로 프로세스 독립·순서 안정 키를 만든다.
    if opp_range:
        rk = _zlib.crc32(repr(sorted(opp_range)).encode())
    else:
        rk = 0
    ck=(tuple(sorted(hero)),tuple(board),rk)
    if ck in _RS_CACHE: return _RS_CACHE[ck]
    mine = bot.eval7(hero + board)
    dead = set(hero) | set(board)
    pool = opp_range if opp_range else None
    if pool:
        cand = [c for c in pool if not (set(c) & dead)]
    else:
        deck = [c for c in bot.FULLDECK if c not in dead]
        cand = [(deck[i], deck[j]) for i in range(len(deck)) for j in range(i+1, len(deck))]
    if not cand: return 0.5
    # **레인지가 주어지면 다시 좁히지 않는다.**
    # 예전에는 항상 상위 절반만 봤는데, opp_range 는 이미 perceived_range 로
    # 액션에 맞게 좁혀진 값이다. 여기서 또 자르면 이중 축소가 된다 —
    # 상대를 잘 읽을수록 자기 핸드를 과소평가하게 되어 방향이 거꾸로다
    # (미들페어가 rel 0.60 -> 0.00 까지 떨어졌다).
    #
    # opp_range 가 없을 때만 절반으로 자른다. 그 경우 cand 는 덱 전체라
    # 쓰레기 조합까지 포함되어 아무 페어나 강해 보이기 때문이다.
    ranked = sorted(cand, key=lambda c: bot.eval7(list(c)+board), reverse=True)
    top = ranked if pool else ranked[:max(1, len(ranked)//2)]
    better = sum(1 for c in top if bot.eval7(list(c)+board) > mine)
    out = 1.0 - better/len(top)
    _RS_CACHE[ck]=out
    return out

# draw_strength 는 bot.draw_strength 하나뿐이다 (ranges 도 같이 쓴다).
draw_strength = bot.draw_strength


def perceived_rel(profile, rel, hero, board, outs=0, made=0):
    """**이 사람이 느끼는** 상대적 강도. 계산값 rel 을 편향으로 흔든다.

    relative_strength 는 전원이 정확하게 계산했다. 그러면 피시도 레귤러와
    똑같이 자기 핸드 강도를 안다는 뜻인데, 그건 사실이 아니다.
    persona.bias 의 축 다섯이 이걸 재려고 만들어져 있었으나
    plan.py 도 session.py 도 읽지 않아 전부 죽어 있었다.

      overpair_love — 오버페어·탑페어를 과대평가
      draw_love     — 드로우를 과대평가
      bluff_fear    — 상대가 세면 자기 핸드를 과소평가 (여기서는 미적용,
                      콜다운 문턱 쪽에서 작동한다)
    """
    if not profile or not profile.get('concepts'):
        return rel
    adj = 0.0
    # 오버페어·탑페어 과대평가. 이미 강한 구간에서만 작동한다 —
    # 에어를 오버페어로 착각하는 것이 아니라 '이기고 있다'를 과신하는 것이다.
    if made >= 1 and rel >= 0.45:
        adj += 0.14 * max(0.0, PS.bias(profile, 'overpair_love'))
    # 드로우 과대평가. 아웃이 있을 때만.
    if outs >= 4:
        adj += 0.10 * max(0.0, PS.bias(profile, 'draw_love')) * min(1.0, outs/9.0)
    # 매몰비용형은 약한 핸드도 놓지 못한다 — 낮은 rel 을 끌어올린다.
    if rel < 0.45:
        adj += 0.08 * max(0.0, PS.bias(profile, 'sticky'))
    return max(0.0, min(1.0, rel + adj))


def _range_sig(combos):
    """레인지의 재현용 서명. **기록 전용** — 판단에 쓰지 않는다.

    파이썬 내장 hash 는 프로세스마다 달라져 아카이브 ID 로 못 쓴다.
    정렬 후 sha256 으로 고정한다. 앞으로 이 정규화를 바꾸지 말 것 —
    바꾸면 과거 아카이브와 대조가 끊긴다.
    """
    if not combos:
        return None
    payload = '\n'.join(sorted(str(tuple(c)) for c in combos))
    return _hashlib.sha256(payload.encode()).hexdigest()[:16]


def _normalize_opp_pools(opp_range, n_opp, opp_ranges=None):
    """상대별 레인지를 잃지 않고 equity 계산용 pool 목록으로 정규화한다.

    opp_range 는 과거 단일/합집합 인터페이스 호환용이다.
    opp_ranges 는 {seat: range} 또는 [range, ...] 이다.
    """
    pools = []
    if isinstance(opp_ranges, dict):
        for k in sorted(opp_ranges, key=lambda x: str(x)):
            r = opp_ranges.get(k) or []
            if r:
                pools.append(list(r))
    elif isinstance(opp_ranges, (list, tuple)):
        for r in opp_ranges:
            if r:
                pools.append(list(r))

    if pools:
        # 호출부가 일부 상대 레인지만 만들었어도 상대 수를 조용히 줄이면 안 된다.
        fallback = list(opp_range or pools[-1])
        while len(pools) < max(1, n_opp):
            pools.append(fallback)
        return pools[:max(1, n_opp)]

    if opp_range:
        return [list(opp_range)] * max(1, n_opp)
    return []


def _opp_ranges_signature(opp_ranges):
    if isinstance(opp_ranges, dict):
        return tuple((str(k), _range_sig(v)) for k, v in
                     sorted(opp_ranges.items(), key=lambda kv: str(kv[0])))
    if isinstance(opp_ranges, (list, tuple)):
        return tuple((str(i), _range_sig(v)) for i, v in enumerate(opp_ranges))
    return ()


def _eq_current(hero, board, opp_range, n_opp, sims=400, seed=None, opp_ranges=None):
    """**보드를 돌리지 않은** 에쿼티. 상대별 레인지를 각각 보존한다.

    기록 전용이다. 계획 판단에는 쓰지 않는다.
    """
    if not board:
        return None
    dead = set(hero) | set(board)
    pools0 = _normalize_opp_pools(opp_range, n_opp, opp_ranges)
    if pools0:
        pools = [sorted(c for c in p if c[0] not in dead and c[1] not in dead)
                 for p in pools0]
    else:
        pools = [bot.range_combos(0.35, dead) for _ in range(max(1, n_opp))]
    pools = [p for p in pools if p]
    if not pools:
        return None
    if seed is None:
        seed = _zlib.crc32(repr((sorted(hero), tuple(board), pools, sims)).encode())
    rng = random.Random(seed)
    hs = bot.eval7(hero + board)
    win = tie = run = 0
    for _ in range(sims):
        used = set(dead); opps = []; ok = True
        for pool in pools:
            for _t in range(40):
                cc = rng.choice(pool)
                if cc[0] not in used and cc[1] not in used:
                    used.add(cc[0]); used.add(cc[1]); opps.append(list(cc)); break
            else:
                ok = False; break
        if not ok:
            continue
        run += 1
        best = max(bot.eval7(o + board) for o in opps)
        if hs > best: win += 1
        elif hs == best: tie += 1
    return (win + tie*0.5) / max(1, run)


def _eq_vs(hero, board, opp_range, n_opp, sims=400, seed=None, opp_ranges=None):
    """추정 레인지 기준 에쿼티. 멀티웨이는 상대별 pool을 각각 사용한다."""
    pools = _normalize_opp_pools(opp_range, n_opp, opp_ranges)
    if pools:
        # 좁은 레인지는 정보가 많은 것이다. 표본만 늘린다.
        _s = sims if min(len(p) for p in pools if p) >= 20 else int(sims*1.8)
        # seed=None 이면 bot 쪽이 실제 pool 내용에서 고정 seed 를 유도한다.
        return bot.equity_vs_combos(hero, board, pools, sims=_s)
    return bot.equity_vs_range(hero, board, [0.35]*max(1, n_opp), sims=sims, seed=seed)


def opp_bet_prob(opp_est, w, street):
    """체크했을 때 상대가 벳해줄 확률. 트랩의 성립 조건 그 자체다.

    정보가 없거나(w=0) 이 사람이 상대를 안 보는 타입이면 모집단 평균으로 돌아간다.
    그게 '자기 전략대로 친다'의 의미다 — 상대를 특정하지 않고 평균적인 상대를 가정한다.
    """
    base = {'flop': 0.45, 'turn': 0.38, 'river': 0.30}.get(street, 0.40)
    if not opp_est or w <= 0.0:
        return base
    # 관찰된 씨벳/배럴 빈도와 공격축에서 추정
    obs = opp_est.get('cbet' if street == 'flop' else 'barrel')
    if obs is None:
        obs = base
    # aggr 은 관측 추정치라 그대로 쓴다 — 이 함수는 '상대가 칠 확률'을 내는
    # 모델이지 내가 얼마나 읽는가가 아니다. 인식 한계는 호출부의 w 가 이미 건다.
    obs = 0.65*obs + 0.35*(opp_est.get('aggr', 5.0)/10.0)
    return max(0.05, min(0.92, PS.blend(base, obs, w)))


def trap_judgment(profile, opp_est, spr_now, danger, multiway, street, tilt, sk):
    """트랩을 팔지 판단. 반환 (확률, 사유).

    축이 셋이다.

      취향   slowplay_taste 가 방향을 정한다. 넛급에서 숨기는 게 편한가,
             바로 뽑는 게 편한가. **능력이 아니라 성격이다.**
      수렴   공부(study)가 높을수록 그 취향이 씻겨나가고 상황이 시키는
             빈도로 끌려간다. 포커에는 GTO 라는 정답이 있어서, 공부할수록
             개인 취향이 옅어지고 서로 비슷해지는 것이 실제 필드의 모습이다.
      상황   상대가 쳐줄 사람인가 · 딥한가 · 보드가 안전한가 · 인원.

    예전에는 취향 축이 없어 sk('trap') 이 그대로 빈도가 됐다. 그래서
    '트랩을 잘 아는데 취향은 속공인 사람'을 표현할 방법이 아예 없었다.
    """
    # 스트리트별 개념을 써야 한다. sk('checkraise') 는 ALIAS 가 항상
    # checkraise_flop 으로 고정 해석하므로, 리버 체크레이즈가 1.0 인 사람도
    # 플랍 값 9.0 으로 계산됐다 — street 를 인자로 받으면서 쓰지 않았다.
    # 발상(trap)보다 **실행(checkraise)**에 무게를 둔다. 숨긴다는 생각은
    # 누구나 하지만, 숨겨서 실제로 밸류를 뽑아내는 것이 실력을 가른다.
    # 예전에는 0.13/0.06 으로 발상 쪽이 2배 넘게 실렸다.
    tool = 0.07*sk('trap') + 0.12*sk(PS.street_concept('checkraise', street))
    if tool <= 0.05:
        return 0.0, ''
    conf = (opp_est or {}).get('confidence', 0.0)
    n    = (opp_est or {}).get('n', 0)
    w    = PS.exploit_weight(profile, conf, n)
    pbet = opp_bet_prob(opp_est, w, street)

    # --- 상황이 시키는 빈도 ---
    # 상대가 벳해줘야 트랩이 성립한다. 안 치는 상대면 무료 카드만 주는 셈.
    situ = 0.35 + 1.30*pbet
    _sp = max(0.0, min(1.0, (spr_now - 1.5) / 3.5))    # SPR 1.5 -> 0, 5.0 -> 1
    situ *= 0.35 + 0.90*_sp                            # 딥해야 나중에 받아낼 게 있다
    _mw = multiway if isinstance(multiway, (int, float)) else (1 if multiway else 0)
    situ *= 0.45 ** min(3, max(0, _mw))                # 다인원 체크는 위험
    situ *= 1.0 - 0.55*max(0.0, min(1.0, danger/0.65))  # 젖은 보드에 무료 카드 금지
    situ = max(0.0, min(1.0, situ))

    # --- 취향과 수렴 ---
    taste = PS.temper(profile, 'slowplay_taste', 5.0)/10.0   # 0 속공 ~ 1 숨김
    # 아키타입 기반 프로필(기질 벡터가 없는 경우)은 slowplay_taste 가 없어
    # 기본 5.0 으로 떨어진다. 'xr'(체크레이즈 선호) 표식이 그 자리를 대신한다.
    if profile.get('value') == 'xr':
        taste = min(1.0, taste + 0.25)
    study = (profile.get('latent') or {}).get('study', 4.5)
    conv = max(0.0, min(1.0, (study - 2.0)/6.0))        # 공부할수록 상황값으로 수렴
    lean = taste*(1.0 - conv) + situ*conv

    p = tool * lean
    p *= (1.0 - 0.55*max(0.0, min(1.0, tilt)))         # 틸트나면 인내가 안 된다
    p = max(0.0, min(0.70, p))
    why = ('넛급 + 상대 벳확률 %.0f%% · 취향 %.1f · 수렴 %.0f%% → 함정(%.0f%%)'
           % (pbet*100, taste*10, conv*100, p*100))
    if w > 0.05:
        why += ' [리딩 %.0f%%]' % (w*100)
    return p, why


def make_plan(hero, board, my_range, opp_range, profile, pot, stack, street,
              seed=None, n_opp=1, to_act_behind=0, oop_vs_aggr=None,
              initiative=True,
              opp_est=None, opp_stack_bb=None, tilt=0.0, bb_chips=None,
              oop_legacy_abs=None, opp_ranges=None):
    """플랍에서 라인을 확정. 상대 수와 뒤에 남은 액션자를 반영.

    opp_est — reads.perceived_profile() 결과. 진짜 프로필을 넘기면 정보 누출이다.
    opp_stack_bb — 주 상대의 유효 스택(bb). 트랩·오버벳은 스택 없이는 무의미하다.
    tilt — 내 틸트 강도 0~1. 틸트 나면 인내가 필요한 계획(트랩)이 줄고 공격이 는다.
    """
    rng = random.Random(seed)
    # 추정한 opp_range 를 그대로 쓴다. 고정 35% 가정으로 되돌리지 말 것 —
    # 좁혀놓은 레인지를 버리고 EV 를 판단하면 리딩이 전부 무의미해진다.
    eq = _eq_vs(hero, board, opp_range, n_opp, sims=400, seed=seed,
                opp_ranges=opp_ranges)
    # 기록 전용. 같은 레인지·같은 인원으로 '보드를 안 돌린' 값을 같이 남긴다.
    # eq 하나만 남기면 나중에 0.535 를 보고 '지금 강한 건가, 드로우 때문인가'를
    # 구분할 수 없다. 판단에는 절대 쓰지 않는다 — 쓰려면 먼저 검증이 필요하다.
    eq_cur = _eq_current(hero, board, opp_range, n_opp, sims=400, seed=seed,
                         opp_ranges=opp_ranges)
    dang = bot.board_danger(board)
    if profile.get('concepts'):
        dang *= min(1.0, PS.sk(profile,'board_texture')/6.0)   # 텍스처를 못 읽으면 위험을 모름
    outs_true = draw_strength(hero, board)
    outs = outs_true * PS.calc_noise(profile, 'outs', rng) if profile.get('concepts') else outs_true
    outs = int(round(outs))
    # 블로커는 개념이 없으면 아예 못 본다
    blk_true = R.blocker_score(hero, opp_range, board)
    # 개념 6 이상이 전부 만점이던 것을 완만하게 편다. 다른 게이트는 /7~/8 인데
    # 여기만 /6 이라 근거가 없었다.
    _bg = (max(0.0, min(1.0, (PS.sk(profile, 'blocker') - 1.0)/7.0))
           if profile.get('concepts') else 1.0)
    blk = blk_true * _bg
    # 순 효과 — '강한 콤보를 지웠나'가 아니라 '콜할 콤보를 지웠나'.
    # 접을 콤보를 지우면(언블로커) 상대의 남은 레인지가 강해져 손해다.
    # 아직 사이즈를 정하기 전이라 스트리트별 표준 사이즈를 가정한다.
    _typ = {'flop': 0.60, 'turn': 0.70, 'river': 0.78}.get(street, 0.65)
    blk_net = (R.blocker_effect(hero, opp_range, board, street, _typ, False) * _bg
               if (opp_range and board) else 0.0)
    nut = R.nut_advantage(my_range, opp_range, board) if my_range else 0.0
    # 전체 에쿼티 우위. 넛 우위와 다른 축이다 —
    # 전자는 '얼마나 자주 칠까', 후자는 '얼마나 크게 칠까'를 정한다.
    adv = (R.range_advantage(my_range, opp_range, board, seed=seed)
           if (my_range and opp_range) else 0.0)
    # 사이즈 배분은 rel/made 를 알아야 목표를 정할 수 있어 아래로 옮겼다.
    s_true = spr(stack, pot)
    s = s_true * PS.calc_noise(profile, 'spr', rng) if profile.get('concepts') else s_true
    # SPR 인식. 예전에는 개념 2.5 미만이면 s=5.0 으로 **통째로 무시**했다.
    # 2.4 와 2.6 이 완전히 다른 사람이 되고, 개념 2.4 인 사람은 SPR 1 이든
    # 20 이든 같은 판단을 했다. 중립값 쪽으로 끌어당기는 연속 처리로 바꾼다.
    if profile.get('concepts'):
        _sa = max(0.0, min(1.0, (PS.sk(profile, 'spr') - 1.0) / 6.0))
        s = s*_sa + 5.0*(1.0 - _sa)
    pc = max(0.0, min(1.0, (profile['icm'] + (10-profile['gamble']) + (10-profile['aggr']))/30.0))

    # 절대 강도 + 상대 레인지 대비 강도
    # 내 카드가 실제로 기여한 강도만 센다 (보드만으로 성립하는 건 내 것이 아니다)
    made = bot.made_strength(hero, board) if board else 0
    rel_true = relative_strength(hero, board, opp_range) if board else 0.5
    rel = perceived_rel(profile, rel_true, hero, board,
                        bot.draw_strength(hero, board) if board else 0,
                        bot.made_strength(hero, board) if board else 0)
    _bluff_mode, _bluff_mul = None, 1.0      # 블러프 세부 전략(아래에서 확정)
    _goal, _mode = None, None                # 계획의 목적 / 실행 방식
    monster = made >= 5                     # 플러시 이상은 다인원 보정 면제
    strong  = made >= 3                     # 트립스 이상

    # 3스트리트로 목표치를 다 넣을 수 있는가. 사이즈를 미리 배분해둔다.
    # 스트리트마다 즉흥으로 정하면 리버에 스택이 어중간하게 남는다.
    # 목표(commit)는 강도가 정하고, 역산 능력은 sk('spr')이 가른다.
    # 상대 유효 스택 비율(내 스택 대비). 상대가 못 따라올 목표는 무의미하다.
    _opp_eff = None
    if opp_stack_bb and bb_chips and stack > 0:
        _opp_eff = min(1.0, (float(opp_stack_bb) * float(bb_chips)) / float(stack))
    _commit = target_commit(profile, rel, made, s_true, street,
                            opp_stack_bb=opp_stack_bb,
                            opp_eff=_opp_eff)
    _so = stackoff_plan(hero, board, profile, pot, stack, street, rng,
                        commit=_commit, danger=dang, opp_est=opp_est)

    # 다인원 보정: 밸류 문턱이 올라가고 블러프는 급감한다
    mw = max(0, n_opp - 1)
    if monster: mw = 0                      # 넛급은 상대 수와 무관하게 밸류
    elif strong: mw = min(mw, 1)            # 트립스/셋은 보정 절반만
    v3 = 0.80 + 0.06*mw          # 3스트리트 밸류 문턱
    v2 = 0.66 + 0.07*mw
    pcz = 0.50 + 0.06*mw

    # ---------- 상대 정보가 판단의 뼈대에 들어간다 ----------
    # 정보가 없으면(초반) rd['w']=0 이라 아래 보정이 전부 0 이 되어
    # 자동으로 '내 전략대로'가 된다. 별도 분기가 필요 없다.
    # 정보가 쌓이면 밸류 문턱·블러프 빈도·함정 빈도가 같이 움직인다 —
    # 익스플로잇은 한 지점에 붙는 보정이 아니라 판단 체계 전체의 전환이다.
    rd = PS.read_opponent(profile, opp_est)
    if rd['w'] > 0:
        wq = rd['w']
        # **그 스트리트의** 폴드 성향을 쓴다. 전체 평균으로 뭉개면
        # '플랍은 잘 치는데 턴에서 멈추는' 사람을 구분할 수 없다.
        sg = PS.street_gap(rd, street)
        # 잘 접는 상대: 밸류로 콜을 못 받으니 문턱을 올리고, 블러프는 늘린다.
        # 안 접는 상대(스테이션): 밸류 문턱을 낮추고 블러프를 줄인다.
        v3 += wq * 0.55 * sg
        v2 += wq * 0.45 * sg
        pcz += wq * 0.30 * sg
    # 블로커는 하드 게이트가 아니라 가중치. 넛 우위가 없으면 블러프 빈도 하락.
    # 0~10 개념은 /10 으로 정규화한다. 예전에는 여기만 /12 여서
    # 개념 10 인 사람도 0.83 이 최대였고 그 12 에 근거가 없었다.
    bluff_ok = (profile['bluff']/10.0) * (0.5 + 1.8*blk) * (0.75 + 0.35*max(0, nut)) \
               * (0.35 ** mw) * (0.55 ** min(to_act_behind, 3))
    # 순 효과를 곱한다. 한 장이 지우는 콤보가 3~4% 수준이라 값이 작으므로
    # 4배로 편다. 언블로커면 1 미만이 되어 블러프가 줄어든다.
    bluff_ok *= max(0.45, min(1.65, 1.0 + 4.0*blk_net))
    if rd['w'] > 0:
        # 잘 접는 상대에게 블러프를 늘린다. 그 스트리트 기준으로.
        bluff_ok *= max(0.25, 1.0 + rd['w'] * 1.6 * PS.street_gap(rd, street))
    # 트랩 판정은 trap_judgment 한 곳에서만 한다.
    # 예전에는 여기서 trap_p 를 한 번 굴리고(평균 0.27) trap_judgment 에서
    # 또 굴려서(평균 0.26) 곱해진 실효 확률이 7.8% 였다. 두 판정이 같은 것을
    # (trap 숙련도 · SPR · 보드 위험 · 인원) 중복해서 봤고, 1차는 상대 성향과
    # 체크레이즈 능력을 못 보는 열등한 판정인데 앞에 서서 74% 를 미리 잘랐다.
    # 그래서 넛급의 92% 가 value_3street 로 직행했다.
    trap_ok = True

    # 상대 레인지에 지는 콤보가 많으면 밸류 계획 자체를 강등한다.
    # eq(랜덤/광역 레인지 대비)가 높아도 rel이 낮으면 얇은 밸류다.
    # 상대 레인지에 지는 콤보가 많으면 밸류 문턱을 올린다.
    # 예전에는 0.45 / 0.65 / 0.92 세 계단이라 rel 0.44 와 0.46 이
    # 완전히 다른 계획으로 갈렸다. 연속 곡선으로 바꾼다.
    if rel <= 0.45:
        _pen = 1.0
    elif rel <= 0.85:
        _pen = (0.85 - rel) / 0.40                  # 0.45 -> 1.0, 0.85 -> 0.0
    else:
        _pen = -min(1.0, (rel - 0.85) / 0.10)       # 넛급은 문턱 완화
    # 양쪽 폭이 다르다. 약할 때 봉쇄는 강하게, 넛급 완화는 약하게 —
    # 완화를 크게 하면 밸류 계획이 과하게 열려 3스트리트가 남발된다.
    if _pen >= 0:
        v3 += 0.30 * _pen
        v2 += 0.22 * _pen
    else:
        v3 += 0.10 * _pen
        v2 += 0.08 * _pen

    T = profile.get('type')
    if profile.get('concepts'):
        sk = lambda c: PS.sk(profile, c)/3.33          # 0~10 → 0~3 스케일로 환산
    else:
        sk = (lambda c: A.skill(T, c)) if T in A.ARCHETYPES else (lambda c: 2)
    why = []                                   # 의도 로그

    if eq >= v3:
        # 트랩은 '확률로 고르는 것'이 아니라 상대를 보고 내리는 판단이다.
        # 개념을 가졌는가(sk)는 사람마다 다르지만, 그 도구를 지금 쓸지는
        # 상대가 벳해줄 사람인가 · 스택이 남았는가 · 보드가 안전한가로 결정된다.
        # 패시브한 상대에게 체크하면 무료 카드만 주는 최악의 수다.
        p_trap, trap_why = trap_judgment(profile, opp_est, s, dang, mw,
                                         street, tilt, sk)
        if trap_ok and rng.random() < p_trap:
            plan = 'trap'; why.append(trap_why)
            # trap 은 **목적이 아니라 실행 방식**이다. 목적은 밸류 추출이고,
            # 그것을 '숨겼다가 상대가 치면 올린다'는 방식으로 실행하는 것.
            # 예전에는 계획명이 trap → value_3street 로 바뀌어, 로그만 보면
            # 목적이 달라진 것처럼 보였다(실제로는 같은 계획의 2단계).
            # plan 문자열은 기존 분기를 위해 유지하고 goal/mode 를 병기한다.
            _goal, _mode = 'value_3street', 'trap'
        else:
            plan = 'value_3street'; why.append('강도 최상위 → 3스트리트 밸류')
    elif eq >= v2:
        # 2스트리트냐 3스트리트냐. 예전에는 `dang > 0.35 or s < 2 or mw` 라는
        # 결정론적 조건이라 같은 상황이면 전원이 같은 선택을 했다.
        # 세 가지가 3스트리트를 막는다 — 보드 위험, 얕은 스택, 다인원.
        # 그리고 3스트리트로 다 넣을 수 있는가(stackoff)와
        # 얇은 밸류를 뽑을 줄 아는가(thin_value)가 사람마다 다르다.
        _p2 = (0.55*min(1.0, dang/0.45)
               + 0.30*max(0.0, min(1.0, (3.0 - s)/2.5))
               + 0.30*min(1.0, mw))
        _p2 *= max(0.45, 1.35 - 0.09*PS.sk(profile, 'stackoff')) if profile.get('concepts') else 1.0
        if profile.get('concepts'):
            # 얇은 밸류를 아는 사람은 3스트리트로 끌고 갈 여지를 더 본다.
            _p2 *= max(0.55, 1.25 - 0.07*PS.sk(profile, PS.street_concept('thin_value', street)))
        if rng.random() < max(0.05, min(0.95, _p2)):
            plan = 'value_2street'
            why.append('밸류(eq %.2f, rel %.2f)지만 위험 %.2f/SPR %.1f/다인원 %d → 2스트리트'
                       % (eq, rel, dang, s, mw))
        else:
            plan = 'value_3street'; why.append('밸류 → 3스트리트')
    elif eq >= pcz:
        # 블락벳: OOP + 이니셔티브 없음 + 쇼다운은 되는 중간 강도
        block_p = 0.0
        # 블락벳은 '알려진 어그레서가 치기 전에 내가 가격을 고정'하는 수다.
        # 어그레서가 없으면 단순 OOP lead일 뿐 blockbet으로 분류하지 않는다.
        # oop_legacy_abs는 기록/과거 비교용이지 이 의미 판정의 대체값이 아니다.
        _oop_a = (oop_vs_aggr is True)
        if _oop_a and not initiative and 0.25 <= rel <= 0.80:
            block_p = 0.12 + 0.05*profile['aggr'] - 0.03*profile.get('bluff', 5)
            block_p *= (1 + 0.4*dang)          # 젖은 보드일수록 가격 통제 욕구↑
            if (not profile.get('concepts')
                    and A.ARCHETYPES.get(profile.get('type'),(0,)*6+('reg',''))[6] == 'fish'):
                block_p *= 0.25
            block_p = max(0.0, min(0.42, block_p))
        if sk('blockbet') >= 1 and rng.random() < block_p:
            plan = 'block'; why.append('OOP 중간강도 → 블락벳으로 가격 통제')
        else:
            # block 과 머징은 같은 중간강도 자리의 대안이다. block 을 이미
            # 선택했으면 아래 분기에서 다시 plan 을 대입하면 안 된다.
            # 예전에는 이 else 가 없어 block 선택 뒤에도 세 갈래가 반드시
            # 실행돼 plan='block' 이 100% 덮어써졌다.
            #
            # 머징 — 밸류/블러프 이분법을 넘어 중간 강도로도 친다.
            # 개념이 낮으면 중간 강도를 전부 팟 컨트롤로 보내고,
            # 높으면 얇은 밸류로 돌린다. thin_value_* 는 턴·리버 한정이라
            # 플랍 단계의 이 갈림이 성향과 무관하게 고정돼 있었다.
            # make_plan 안의 sk() 는 0~3 스케일이다(PS.sk/3.33). 0~10 로 착각하지 말 것.
            _mg = sk('range_merge')                        # 0~3
            _pc_p = min(0.75, pc*0.8 + 0.12 + 0.18*mw) * max(0.35, 1.0 - 0.22*_mg)
            if sk('potcontrol') >= 1 and rng.random() < _pc_p:
                plan = 'pot_control'; why.append('중간강도(eq %.2f, rel %.2f) → 팟 컨트롤' % (eq, rel))
            elif rel >= max(0.28, 0.52 - 0.080*_mg) and made >= 1:
                plan = 'value_2street'
                why.append('중간강도(eq %.2f, rel %.2f, 머징 %.1f) → 얇은 밸류' % (eq, rel, _mg))
            else:
                # 폴백이 밸류면 안 된다. rel 0.0 에 made 0 인 완전 미스가
                # '얇은 밸류'로 분류돼, 계획은 밸류인데 실행은 체크하는
                # 모순이 생겼다 (decide_aggression 이 rel 을 보므로).
                plan = 'showdown' if made >= 1 else 'giveup'
                why.append('중간강도이나 상대레인지 열세(rel %.2f, made %d) → %s'
                           % (rel, made, plan))
    elif outs >= 8 and to_act_behind <= 1 and sk('semibluff') >= 0.4 \
         and rng.random() < min(0.95, 0.25 + 0.24*sk('semibluff')):
        plan = 'semibluff'; why.append('드로우 %d아웃 → 세미블러프' % outs)
        # 세미블러프는 이기는 경로가 둘(접거나, 맞추거나)이라 순수 블러프와
        # 다르다. **위장(merged)은 필요가 적고** — 콜받아도 손해가 아니므로
        # 밸류인 척할 이유가 약하다 — **포기(probe)는 방향이 반대다** — 미스해도
        # 아웃츠가 남아 있으면 계속 갈 이유가 있다.
        # 그래서 폴드율 역산(barrel)만 적용한다.
        _fe = 0.5
        if isinstance(opp_est, dict) and opp_est.get('fold') is not None:
            _fe = float(opp_est['fold'])
        _bluff_mode = 'barrel'
        _bluff_mul = barrel_size(_fe, profile, floor=0.35, cap=1.20)
        why.append('세미블러프 사이즈: 폴드율 %.0f%% 역산 → 팟의 %.0f%%'
                   % (_fe*100, _bluff_mul*100))
    # **쇼다운 가치가 있으면 블러프 계획으로 가지 않는다.**
    # 예전에는 이 분기가 made 를 확인하지 않아, 세컨페어(made 1, eq 0.38)가
    # '쇼다운 가치 없음'이라는 이유로 2스트리트 블러프가 됐다.
    # 아래 else 에만 has_sd 검사가 있어서 메이드 핸드가 먼저 새어나갔다.
    #
    # 다만 '가치가 있다/없다'가 이분법이면 안 된다. 약한 페어는 쇼다운 가치가
    # 얇아서 블러프로 전환할 여지가 있고, 그 판단은 rel 이 정한다.
    elif (eq < 0.42 and sk('bluff') >= 1
          and (made == 0 or rel < 0.30)
          and rng.random() < bluff_ok * (1 + 0.9*min(1.0, outs/8.0) + 0.6*(eq>=0.30))
                            * (0.45 + 0.28*sk('bluff'))):
        plan = 'bluff_2street'
        why.append('쇼다운 가치 없음 + 블로커 %.2f/넛우위 %.2f → 블러프 계획' % (blk, nut))
        # 큰 전략(블러프) 아래 세부 전략을 고른다. 사이즈는 여기서 갈린다.
        _bm, _bmul, _bwhy = bluff_mode(profile, rel, dang, nut, opp_est,
                                       street, s, rng)
        _bluff_mode, _bluff_mul = _bm, _bmul
        why.append('블러프 세부: %s — %s' % (_bm, _bwhy))
    else:
        # giveup은 '쇼다운 가치 없음'일 때만. 메이드 핸드는 팟컨트롤로 간다.
        has_sd = made >= 1 or eq >= 0.42 + 0.05*mw
        if has_sd and sk('potcontrol') >= 1 and rng.random() < 0.72:
            plan = 'pot_control'; why.append('쇼다운 가치 있음 → 팟 컨트롤')
        elif has_sd:
            # 팟컨트롤 개념이 없거나 확률에서 떨어진 경우. 예전에는 같은 조건의
            # elif 가 하나 더 있어 **세 번째 분기가 도달 불가능**이었다.
            plan = 'showdown'
            why.append('쇼다운 가치 있음 → 체크다운(팟컨트롤 개념 %.1f)'
                       % (sk('potcontrol')*3.33))
        else:
            plan = 'giveup'; why.append('쇼다운 가치 없고 블러프 개념/조건 미달 → 포기')
    st = {'plan': plan, 'street_made': street, 'streets': [street],
            'eq': round(eq,3), 'danger': round(dang,2), 'outs': outs,
            'blocker': round(blk,2), 'blocker_net': round(blk_net,3),
            'nut_adv': round(nut,2), 'range_adv': round(adv,2),
            'stackoff': dict(_so, _blk_net=round(blk_net, 3)) if isinstance(_so, dict) else _so,
            'bluff_mode': _bluff_mode, 'bluff_mul': round(_bluff_mul, 2),
            'plan_goal': _goal or plan, 'plan_mode': _mode, 'spr': round(s,1), 'pc': round(pc,2),
            'n_opp': n_opp, 'behind': to_act_behind, 'rel': round(rel,2), 'made': made,
            # ---- 기록 전용 provenance. 판단에 쓰지 않는다 ----
            # eq 가 '현재 강도'인지 '미래 개선분'인지 나중에 복원하기 위한 값들.
            # outs 는 calc_noise 를 거친 체감값이라 물리값(outs_true)을 따로 남긴다.
            'eq_current': (None if eq_cur is None else round(eq_cur, 3)),
            'eq_delta': (None if eq_cur is None else round(eq - eq_cur, 3)),
            'eq_sims': 400, 'eq_seed': seed,
            'outs_true': outs_true,
            'my_range_n': len(my_range) if my_range else 0,
            'my_range_sig': _range_sig(my_range),
            'opp_range_n': len(opp_range) if opp_range else 0,
            'opp_range_sig': _range_sig(opp_range),
            'opp_ranges_n': ({str(k): len(v) for k, v in opp_ranges.items()}
                             if isinstance(opp_ranges, dict) else None),
            'opp_ranges_sig': ({str(k): _range_sig(v) for k, v in opp_ranges.items()}
                               if isinstance(opp_ranges, dict) else None),
            # 사유에 어느 스트리트에서 붙은 줄인지 표시한다. why 는 스트리트를
            # 넘어 누적되는데 표시가 없어서, 리버 기록의 why[0] 이 플랍 때 붙은
            # '포기' 문자열인 채로 남았다. 계획은 value_2street 인데 사유 첫 줄이
            # '포기'라 정면으로 모순됐고, 실제로 리뷰 때 오독을 유발했다.
            'why': ['%s: %s' % (street, w) if not w.startswith(
                ('flop:', 'turn:', 'river:', '프리플랍')) else w for w in why],
            'type': T,
            # 내 레인지를 보존한다. 후반 스트리트에서 넛 우위를 다시 계산하려면 필요하다
            # (오버벳 판단이 이걸 쓴다).
            'my_range': my_range,
            # 상대 추정치도 계획에 실어 보낸다. 턴·리버는 make_plan 을 다시 부르지 않고
            # revise_plan/refresh 로 가므로, 이게 없으면 익스플로잇이 플랍에서 끊긴다.
            'opp_est': opp_est, 'opp_stack_bb': opp_stack_bb,
            'protect': round(min(1.0, dang*(1+0.5*mw)), 2)}
    # 의도는 파이프라인 끝(session)에서 최종 계획 기준으로 붙인다.
    return st


def attach_intent(st, hero, board, my_range, opp_range, profile, pot, stack,
                  street, rng, n_opp, to_act_behind, oop, initiative, opp_est=None,
                  oop_vs_aggr=None, oop_legacy_abs=None):
    """계획에 이 스트리트의 의도를 붙인다. 판단 층의 마지막 단계."""
    plan = st.get('plan')
    rel = st.get('rel', 0.5)
    p_aggr, why_a = decide_aggression(profile, board, street, plan, rel, n_opp,
                                      oop, initiative, to_act_behind, rng,
                                      opp_est, st.get('outs', 0), plan_state=st,
                                      oop_vs_aggr=oop_vs_aggr,
                                      oop_legacy_abs=oop_legacy_abs)
    _roll = rng.random()
    _trace(st, street, 'aggression', p=round(p_aggr, 3), roll=round(_roll, 3),
           why=why_a, plan=plan, rel=round(rel, 3))
    if _roll < p_aggr:
        size = decide_size(profile, hero, board, street, plan, rel,
                           opp_range, my_range, pot, stack, rng, opp_est,
                           st.get('nut_adv', 0.0),
                           deviating=why_a.startswith('DEVIATE:'),
                           stackoff=st.get('stackoff'), plan_state=st)
        if size > 0:
            st = set_intent(st, street, mk_intent('bet', size, why_a))
            # 계획과 반대되는 의도는 이탈로 남긴다. 기록이 없으면
            # 나중에 '왜 이렇게 쳤는지'를 사람이 눈으로 찾아야 한다.
            if why_a.startswith('DEVIATE:'):
                st = record_deviation(st, street, 'bet', plan, why_a[8:])
        else:
            st = set_intent(st, street, mk_intent('check', 0.0, '사이즈 0 → 체크'))
    else:
        st = set_intent(st, street, mk_intent('check', 0.0, why_a))
    return st

# ---------- 의도(intent): 판단 층의 출력 ----------
# 계획은 라벨만으로 부족하다. {'plan':'giveup'} 만 있으면
# 집행부가 "그래도 칠까?"를 다시 결정하게 되고, 그 순간 모순이 생긴다.
# 판단 층이 **이 스트리트에 무엇을 할지**까지 확정해서 넘긴다.
#
#   act  : 'bet' | 'check' | 'call' | 'fold' | 'raise'
#   size : 팟 대비 비율 (bet/raise 일 때만). 집행부는 이 값을 칩으로 환산만 한다.
#   src  : 이 의도가 어느 판단에서 나왔는가 (디버깅·불변식용)
#
# 집행부는 intent 를 만들지 않는다. 읽고 환산할 뿐이다.

def calldown_need(profile, hero, board, street, pot, tocall, bf, read,
                  to_act_behind, opp_est, n_opp=1, rng=None, _bf_gated=True,
                  facing_size_frac=None, objective_breakeven=None):
    """콜 문턱(need)을 정하는 **유일한 지점**.

    예전에는 이 계산 전체가 act_with_plan(집행부) 안에 인라인으로 있었다.
    "집행부는 판단 금지, intent 를 칩으로 환산만" 이라는 규약을 어긴다.
    이름이 없으니 어느 개념이 여기 걸려야 하는지도 점검할 수 없었다
    (tools/wirecheck.py 가 bluffcatch 를 decide_response 에서 못 찾은 이유).

    팟오즈에서 시작해 순서대로 보정한다.
      ICM -> 다인원 -> 배팅라인 리딩(bluffcatch/range_read/sizing_tell)
      -> 상대 블러프 성향(bluff_gap) -> 상·하한
    """
    # 팟오즈 × 버블팩터. bf 는 호출부에서 이미 인지 보정된 값이지만,
    # 보정 없이 들어오는 경로(다른 호출부)도 있으므로 여기서 한 번 더 확인한다.
    # icm_aware 는 멱등이 아니므로 1.0 초과일 때만, 그리고 원본 bf 를 쓴다.
    if profile.get('concepts') and bf and bf > 1.0 and not _bf_gated:
        bf = PS.icm_bf(profile, bf)
    # 상대 벳을 '이 사람이 인식한 크기'로 바꾼 뒤 팟오즈를 낸다.
    # 예전에는 이 인식이 아래쪽에서 need 를 **통째로 재대입**해서, 이미 쌓은
    # 오차·뒤사람 위험·리딩·클램프·call_bias 를 전부 지웠다. 인식은 판단
    # 근거의 **입력**이지 쌓은 판단을 지우는 사건이 아니다. 그래서 여기로 올린다.
    #   균형 공식 정의역 밖(2팟 초과)을 못 읽는 사람은 팟오즈를 오독한다.
    #   순서가 중요하다 — opp_size_norm 은 '상대 기준 보정'(관찰),
    #   size_read 는 '내 인식 한계'(능력)다.
    # 난수는 건드리지 않는다 (read_opponent·opp_size_norm·size_read 전부 무작위 없음).
    # 현재 hero가 받는 가격과 상대의 마지막 공격 사이즈는 같은 양이 아니다.
    # tc/(pot-tc)는 첫 HU bet에서만 우연히 상대의 pot-fraction과 일치한다.
    # bet->call->hero / raise->hero에서는 callers/이전 기여분이 섞여 틀어진다.
    _p0 = max(1.0, float(pot) - float(tocall))
    _sz_fallback = float(tocall)/_p0
    _sz_true = (float(facing_size_frac)
                if facing_size_frac is not None and facing_size_frac > 0
                else _sz_fallback)
    _rdz = None
    _sz_seen = _sz_true
    _tocall_seen = float(tocall)
    if profile.get('concepts') and board:
        _rdz = PS.read_opponent(profile, opp_est) if opp_est else None
        _sz_seen = PS.size_read(profile, PS.opp_size_norm(_rdz, _sz_true, street))
        # 사이즈 오독은 실제 call price에 비례 적용한다.
        # callers의 칩을 상대 bet으로 재해석하지 않는다.
        if _sz_true > 1e-9:
            _tocall_seen = float(tocall) * (_sz_seen / _sz_true)
    # pot 은 pot_live 다 — 상대가 방금 낸 벳은 들어 있고 **내 콜은 아직
    # 아니다**(session.py:449 의 pot_now + sum(r2.contrib)). 콜하면 내 칩도
    # 팟에 들어가므로 분모에 내 콜을 더해야 한다.
    #   필요승률 = 벳 / (벳전팟 + 상대벳 + 내콜) = sz/(1+2sz)
    # _sz_seen == _sz_true 일 때 (tocall*bf)/(pot + tocall) 과 **비트까지 같다**
    # (정수 칩이라 (pot-tocall) + 2*tocall 이 pot + tocall 과 정확히 일치한다).
    # 50만 조합 대조에서 불일치 0건. 비발동군 무변화 관문이 이것에 걸려 있다.
    need_true = (_tocall_seen*bf)/max(1.0, _p0 + 2.0*_tocall_seen)

    # F8-D4: layer-aware call price는 legacy response eq/need를 덮지 않는다.
    # objective_breakeven은 실제 pot-layer geometry의 객관적 break-even equity다.
    # size_read 오독은 기존 scalar pot-odds 체인에서 생기는 비율만큼만 같은 방향으로
    # 옮긴다. 새 side-pot 계수는 만들지 않는다.
    call_need_true = None
    if objective_breakeven is not None:
        _base_scalar = float(tocall) / max(1.0, _p0 + 2.0*float(tocall))
        _seen_scalar = _tocall_seen / max(1.0, _p0 + 2.0*_tocall_seen)
        _size_ratio = (_seen_scalar / _base_scalar) if _base_scalar > 1e-12 else 1.0
        call_need_true = max(
            0.0, float(objective_breakeven) * float(bf) * _size_ratio)

    need = need_true
    call_need = call_need_true
    if profile.get('concepts'):
        # 팟오즈 계산 오차. calc_noise 는 최대 3배까지 곱하는데,
        # need 는 확률이라 3배를 곱하면 38% 가 100% 가 되어 '더 강해졌는데
        # 폴드'하는 모순이 나온다. 오차는 오차 범위 안에 있어야 한다.
        nz = PS.calc_noise(profile, 'potodds', rng)
        nz = max(0.65, min(1.55, nz))
        need = need_true * nz
        if call_need is not None:
            call_need = call_need_true * nz
    if to_act_behind:
        # 뒤에 남은 사람 리스크. 확률에 상수를 더하지 않고
        # 남은 팟 지분 기준으로 비례 가산한다.
        _behind_add = min(0.18, 0.06*to_act_behind)
        need += (1.0 - need_true) * _behind_add
        if call_need is not None:
            call_need += (1.0 - call_need_true) * _behind_add
    need = max(0.01, min(0.97, need))
    if call_need is not None:
        call_need = max(0.01, min(0.97, call_need))
    # 배팅라인 리딩 — 상대가 블러프일 사전확률만큼 문턱을 낮춘다
    if read is not None:
        trust = 0.25 + 0.06*profile.get('aggr', 5)
        if profile.get('concepts'):
            bc = PS.sk(profile, PS.street_concept('bluffcatch', street))
            trust *= min(1.4, (0.6*PS.sk(profile,'range_read') + 0.4*bc)/5.0)    # 리딩을 얼마나 신뢰하는가
        if (not profile.get('concepts')
                and A.ARCHETYPES.get(profile.get('type'),(0,)*6+('reg',''))[6] == 'fish'):
            trust *= 0.35
        # 사이징 텔: 사이즈에서 정보를 읽는 능력. 없으면 큰 벳도 작은 벳도 똑같이 본다.
        if profile.get('concepts'):
            stell = PS.sk(profile, 'sizing_tell')
            sz_now = tocall/max(1.0, float(pot) - tocall)
            dev = abs(sz_now - 0.6)                      # 표준 사이즈에서 벗어난 정도
            trust *= (1.0 + 0.10*(stell - 5.0)/5.0 * min(2.0, dev/0.4))
        _read_adj = trust * (read - 0.35)
        need -= _read_adj
        if call_need is not None:
            call_need -= _read_adj
    # 상·하한. 상한은 팟오즈를 배 이상 부풀리지 못하게,
    # 하한은 팟오즈의 절반 아래로 못 내려가게 한다.
    # 예전엔 하한이 없어서 상대를 블러프로 크게 읽으면
    # need 가 실제 팟오즈(32%)보다 낮은 19% 까지 떨어졌다.
    # 리딩은 문턱을 조정하는 것이지 팟오즈를 뒤집는 게 아니다.
    need = min(need, need_true*1.75 + 0.05)
    need = max(need, need_true*0.55)
    need = max(0.01, min(0.95, need))
    if call_need is not None:
        call_need = min(call_need, call_need_true*1.75 + 0.05)
        call_need = max(call_need, call_need_true*0.55)
        call_need = max(0.01, min(0.95, call_need))
    made_now = bot.made_strength(hero, board) if board else 0
    # 개인 행동 편향 — 같은 eq·같은 팟오즈라도 사람마다 다른 답을 낸다.
    # 이게 없으면 성향이 아무리 달라도 콜/폴드는 eq>=need 하나의 문턱으로 수렴해서
    # '평균은 맞지만 아무도 개성이 없는' 필드가 된다. calc_noise(랜덤 오차)와 달리
    # 이건 그 사람에게 고정된 방향성 편향이다.
    if profile.get('concepts') and board:
        # _sz_seen / _rdz 는 위에서 이미 만들었다 (need_true 자리).
        # 여기서 다시 계산하지 않는다 — 같은 값을 두 번 만들면 언젠가 갈린다.
        _cbias = PS.call_bias(profile, street, _sz_seen,
                              made_now, bot.draw_strength(hero, board))
        need *= _cbias
        if call_need is not None:
            call_need *= _cbias
        # 예전에는 여기서 `if abs(_sz_seen - _sz_true) > 1e-9: need = …` 로
        # need 를 통째로 재대입했다. 0.2% 오독에도 발동해서(실측 발동률 80~89%,
        # 오독 중앙 1.5%) 앞의 체인이 전부 지워졌다. 인지 사이즈는 이제
        # need_true 의 입력으로 들어간다 — 같은 정보를 안 지우고 반영한다.
        # 근거: FIX_PLAN.md 2-A / TRACE_SZSEEN.md / TRACE_STELL.md
        # 상대가 블러프를 많이 하는 사람이면 더 넓게 받아야 한다.
        # 개인 편향(call_bias)은 '내가 어떤 사람인가', 이건 '상대가 어떤 사람인가'다.
        if _rdz and _rdz.get('w', 0) > 0:
            # read_opponent 의 bluff_gap 을 쓴다. 예전에는 opp_est['bluff'] 를
            # 날것으로 읽어 see_line 게이트를 우회했다 —
            # 라인을 못 읽는 사람도 상대 블러프 성향에 완전히 반응했다.
            bl = _rdz.get('bluff_gap', 0.0)
            _bl_mult = max(0.55, 1.0 - 0.35*bl)
            need = PS.blend(need, need*_bl_mult, _rdz['w'])
            if call_need is not None:
                call_need = PS.blend(
                    call_need, call_need*_bl_mult, _rdz['w'])
        need = max(0.03, min(0.95, need))
        if call_need is not None:
            call_need = max(0.03, min(0.95, call_need))
    need = max(0.03, min(0.95, need))
    if call_need is None:
        return need
    return need, max(0.03, min(0.95, call_need))

def decide_response(profile, hero, board, street, plan, plan_state, eq, need,
                    made_now, opp_range, pot, tocall, stack, committed, rng,
                    allow_raise=True, call_eq=None, call_need=None):
    """저항(tocall>0)을 마주했을 때 폴드/콜/레이즈를 정하는 **유일한 지점**.

    예전에는 이 판단이 집행부에 흩어져 p_raise 를 네 곳에서 각자 굴렸다.
    무저항 쪽은 decide_aggression 으로 합쳤으므로 저항 쪽도 같은 형태로 맞춘다.
    집행부는 여기 결과를 칩으로 환산만 한다.

    반환: (act, size_mult, need, why)
      act       : 'fold' | 'call' | 'raise'
      size_mult : raise 일 때 (pot + 2*tocall) 에 곱할 배수
    """
    rel_ps = plan_state.get('rel', 0.5)
    has_c = bool(profile.get('concepts'))

    # F8-D4: raise eligibility keeps legacy eq/need.  These two values are used
    # only when the response has reached an actual call-vs-fold choice.
    _layer_call = (call_eq is not None and call_need is not None)
    _cf_eq = float(call_eq) if _layer_call else eq
    _cf_need = float(call_need) if _layer_call else need

    # --- 넛급 메이드: 레이즈할 것인가 ---
    if made_now >= 5 and eq > need + 0.10:
        rel = relative_strength(hero, board, opp_range)
        paired = board_paired(board)
        p = 0.30 + 0.45*rel
        p *= (0.55 if paired and made_now == 5 else 1.0)
        p *= (0.55 + 0.09*profile['aggr'])
        p *= (0.75 + 0.05*profile['gamble'])
        if has_c:
            rr = PS.sk(profile, 'reraise')/10.0
            p *= (0.55 + 0.85*rr)
            if rel >= 0.95:
                p = max(p, 0.32 + 0.40*rr)
        p = max(0.05, min(0.95, p))
        if allow_raise and rng.random() < p:
            return 'raise', 1.0, need, '넛급 레이즈(%.0f%%)' % (p*100)
        if _layer_call and _cf_eq < _cf_need:
            return 'fold', 0.0, _cf_need, (
                '넛급 레이즈 미선택 + layer call EV 미달(%.3f < %.3f)'
                % (_cf_eq, _cf_need))
        return 'call', 0.0, (_cf_need if _layer_call else need), '넛급이나 콜 선택'

    # --- 밸류 계획: 레이즈할 것인가 ---
    # value_2street 가 빠져 있었다. 그래서 2스트리트 밸류 계획인 봇은 저항이
    # 오면 이 분기를 못 타고 아래로 흘러가 팟오즈만으로 콜/폴드가 정해졌다.
    # **밸류 계획의 목적은 팟을 목표까지 키우는 것이므로, 상대 벳이 목표에
    # 못 미치면 레이즈로 채우는 것이 계획의 일부다.**
    if plan in ('value_3street', 'value_2street', 'trap') and eq > need + 0.15:
        rr = PS.sk(profile, 'reraise')/10.0 if has_c else 0.5
        so = PS.sk(profile, 'stackoff')/10.0 if has_c else 0.5
        p = 0.20 + 0.55*rr + (0.25 if committed else 0.0)
        p *= (0.7 + 0.06*profile.get('aggr', 5))
        if committed and so < 0.35:
            p *= 0.5
        if plan == 'value_2street':
            p *= 0.80                      # 2스트리트 계획은 3스트리트보다 소극적
        if rel_ps >= 0.95:
            floor = 0.38 + 0.42*rr
            if street == 'river': floor *= 0.85
            p = max(p, floor)
        elif rel_ps >= 0.88:
            p = max(p, 0.22 + 0.34*rr)
        p = min(p, 0.93)
        if allow_raise and rng.random() < max(0.05, min(0.92, p)):
            # 레이즈 크기는 **목표 대비 부족분**이 정한다. 고정 배수(1.1)면
            # 상대가 이미 크게 쳐서 목표를 채워준 경우에도 똑같이 올린다.
            _so = plan_state.get('stackoff') or {}
            _cm = _so.get('commit') if isinstance(_so, dict) else None
            mult = 1.1
            if _cm and stack > 0:
                want = stack*float(_cm)            # 넣을 작정인 총액
                gap = max(0.0, want - tocall) / max(1.0, want)
                mult = max(0.75, min(1.6, 0.75 + 0.85*gap))
            return 'raise', mult, need, '밸류 레이즈(%.0f%%, x%.2f)' % (p*100, mult)
        if _layer_call and _cf_eq < _cf_need:
            return 'fold', 0.0, _cf_need, (
                '밸류 레이즈 미선택 + layer call EV 미달(%.3f < %.3f)'
                % (_cf_eq, _cf_need))
        return 'call', 0.0, (_cf_need if _layer_call else need), '밸류이나 콜 선택(상대가 팟을 키워줌)'

    # --- 블러프 레이즈: reraise × bluff 개념 ---
    # 계획을 반드시 본다. 예전에는 plan 조건이 없어서 pot_control(팟을 작게
    # 유지하겠다는 계획)인데도 여기로 떨어져 올인급 레이즈가 나왔다.
    # 또 쇼다운 가치가 있는 패를 블러프로 쓰면 이길 수 있는 상황을 버리게 된다.
    # giveup 은 제외한다. 그 계획의 사유 자체가 '블러프 개념/조건 미달'이라
    # 여기서 블러프 레이즈를 내면 판단 층이 이미 기각한 것을 집행부가 되살리는 셈이다.
    # 규율이 낮아 뒤집는 경우는 아래 이탈 경로에서 따로 처리한다.
    if allow_raise and has_c and eq < need - 0.05 and plan in ('bluff_2street', 'semibluff', 'river_bluff'):
        made_sd = plan_state.get('made', 0)
        if made_sd >= 2:
            pass                       # 투페어 이상은 쇼다운 가치가 있다 → 블러프 부적합
        else:
            blr = (PS.sk(profile, 'reraise')/10.0) * (PS.sk(profile, 'bluff')/10.0)
            if rng.random() < blr*0.28:
                return 'raise', 1.0, need, '블러프 레이즈(개념 %.2f)' % blr

    # --- 세미블러프: 레이즈 or 내재오즈 콜 ---
    if plan == 'semibluff' and plan_state.get('outs', 0) >= 8 and street != 'river':
        # 예전에는 0.35 고정이라 **전원이 같은 빈도로** 세미블러프 레이즈를 했다.
        _p_sb = 0.35
        if has_c:
            _p_sb = (0.10 + 0.055*PS.sk(profile, 'semibluff')
                          + 0.030*PS.sk(profile, 'reraise'))
            _p_sb *= 0.70 + 0.06*PS.temper(profile, 'aggression', 5.0)
            _p_sb = max(0.03, min(0.80, _p_sb))
        if allow_raise and rng.random() < _p_sb:
            return 'raise', 0.95, need, '세미블러프 레이즈(%.0f%%)' % (_p_sb*100)
        if stack > pot:
            # 내재오즈. 얼마나 벌 수 있는지는 아웃 계산과 팟오즈 감각의 함수다.
            # 예전에는 0.08 상한 고정이라 개념과 무관했다.
            _io = 0.05
            if has_c:
                _io = 0.02 + 0.008*(0.6*PS.sk(profile, 'outs') + 0.4*PS.sk(profile, 'potodds'))
            implied = min(0.12, _io * min(1.0, stack/max(1.0, 2.0*pot)))
            need = max(0.02, need - implied)
            if _layer_call:
                _cf_need = max(0.02, _cf_need - implied)
        _use_eq = _cf_eq if _layer_call else eq
        _use_need = _cf_need if _layer_call else need
        act = 'call' if _use_eq >= _use_need else 'fold'
        return act, 0.0, _use_need, (
            '세미블러프 내재오즈 반영%s'
            % (' + layer call EV' if _layer_call else ''))

    if plan == 'giveup' and has_c and eq < need - 0.05:
        # 포기 계획을 뒤집는 블러프 레이즈. 규율이 낮을수록 자주 나온다.
        # 계획 이탈이므로 반드시 기록한다.
        disc = PS.temper(profile, 'discipline', 5.0)
        blr = (PS.sk(profile, 'reraise')/10.0) * (PS.sk(profile, 'bluff')/10.0)
        p_dev = blr * 0.28 * max(0.05, 1.0 - 0.085*disc)
        if allow_raise and plan_state.get('made', 0) < 2 and rng.random() < p_dev:
            plan_state.setdefault('deviations', []).append(
                {'street': street, 'planned': 'fold', 'executed': 'raise',
                 'why': '규율 %.1f → 포기 계획 뒤집고 블러프 레이즈' % disc})
            return 'raise', 1.0, need, 'DEVIATE:포기 계획 뒤집은 블러프 레이즈'

    if plan in ('bluff_2street', 'giveup', 'river_bluff'):
        # 계획은 포기지만 팟오즈가 실제로 맞으면 접으면 안 된다.
        # 부등호를 계획으로 덮어쓰면 eq > need 인데 폴드하는 모순이 생긴다.
        # (계획이 못 미더우면 need 를 올려야지 부등호를 무시하면 안 된다)
        _use_eq = _cf_eq if _layer_call else eq
        _use_need = _cf_need if _layer_call else need
        if _use_eq >= _use_need:
            return 'call', 0.0, _use_need, (
                '포기 계획이나 팟오즈가 맞음%s(eq %.3f ≥ need %.3f)'
                % (' [layer]' if _layer_call else '', _use_eq, _use_need))
        return 'fold', 0.0, _use_need, (
            '포기/블러프 계획 + 팟오즈 미달%s → 폴드'
            % (' [layer]' if _layer_call else ''))

    # --- 인식 편향: 같은 eq/need 여도 사람마다 다르게 결정한다 ---
    # station / bluff_fear / hero_call 은 전부 이 판단을 재려고 만든 축인데
    # 아무도 읽지 않아 죽어 있었다. 결과적으로 콜/폴드가 순수 산수였다.
    need_seen = _cf_need if _layer_call else need
    _eq_seen = _cf_eq if _layer_call else eq
    if has_c:
        sz = tocall/max(1.0, float(pot) - tocall)
        # 스테이션: 문턱을 낮춰 넓게 콜한다.
        need_seen *= max(0.55, 1.0 - 0.22*max(0.0, PS.bias(profile, 'station')))
        # 블러프 공포: 큰 벳일수록, 후반 스트리트일수록 문턱을 올린다.
        _bf_w = min(1.0, sz/0.9) * (1.0 if street == 'river' else 0.65)
        need_seen *= 1.0 + 0.30*max(0.0, PS.bias(profile, 'bluff_fear', street))*_bf_w
        # 히어로콜: 가볍게 받아준다. 큰 벳에서 더 크게 작동한다.
        need_seen *= max(0.60, 1.0 - 0.18*max(0.0, PS.bias(profile, 'hero_call', street))*_bf_w)
        need_seen = max(0.02, min(0.97, need_seen))
    act = 'call' if _eq_seen >= need_seen else 'fold'
    return act, 0.0, need_seen, (
        'eq %.3f vs 체감 need %.3f (실제 %.3f)%s'
        % (_eq_seen, need_seen, need, ' [layer-call]' if _layer_call else ''))


def decide_aggression(profile, board, street, plan, rel, n_opp, oop, initiative,
                      to_act_behind, rng, opp_est=None, outs=0, plan_state=None,
                      oop_vs_aggr=None, oop_legacy_abs=None):
    """무저항 상황(tocall==0)에서 칠지 체크할지 결정하는 **유일한 지점**.

    예전에는 이 판단이 집행부(act_with_plan)에 흩어져 있었다:
      ② 씨벳 분기 — plan 을 보지 않고 cbet_freq 만 굴려서 벳
      ③ 동크 억제 — OOP 블러프를 확률로 차단
      ④ p_bet — 밸류 계획의 체크 빈도
    ②가 plan 을 안 봤기 때문에 'giveup 계획인데 벳' 같은 모순이 나왔다.

    지금은 셋을 하나로 합치고 **plan 을 반드시 본다**.
    반환: (칠 확률, 사유)
    """
    a = profile.get('aggr', 5)
    has_c = bool(profile.get('concepts'))

    # 지연 씨벳 — 플랍을 실제로 체크하고 턴에 다시 공격권을 쓰는 것.
    # probe(상대가 체크한 뒤 내가 공격하는 것)와 다르다.
    # 이 값을 포기/showdown 분기보다 먼저 만든다. 예전에는 그 분기가 먼저
    # return 해서 delayed_cbet 개념이 정작 대표적인 delayed-cbet 후보에서 죽어 있었다.
    if (street == 'turn' and initiative and has_c
            and (plan_state or {}).get('flop_checked')):
        _dc = PS.sk(profile, 'delayed_cbet')/10.0
        _dc_boost = 0.55 + 0.90*_dc
    else:
        _dc_boost = 1.0

    # --- 포기 계획은 원칙적으로 체크한다 ---
    # 다만 이니셔티브가 있으면 지속벳/지연씨벳이라는 별개 동기가 존재한다.
    if plan in ('giveup', 'showdown'):
        if not initiative:
            return 0.0, '포기 계획 + 이니셔티브 없음 → 체크'
        cf = cbet_freq(profile, board, n_opp, street, oop, rel, opp_est,
                       range_adv=(plan_state or {}).get('range_adv', 0.0))
        cf *= _dc_boost
        if has_c:
            disc = PS.temper(profile, 'discipline', 5.0)
            cf *= max(0.05, 1.0 - 0.085*disc)
        _kind = '지연씨벳' if _dc_boost != 1.0 else '지속벳'
        return max(0.0, min(0.9, cf)), 'DEVIATE:포기 계획이나 %s(%.0f%%)' % (_kind, cf*100)

    if plan == 'trap':
        return 0.0, '함정 계획 → 체크'

    if plan in ('bluff_2street', 'semibluff', 'river_bluff'):
        if to_act_behind >= 2:
            return 0.0, '뒤에 %d명 → 블러프 포기' % to_act_behind
        p = 0.25 + 0.070*profile.get('bluff', 5) + 0.02*profile.get('gamble', 5)
        # 상대가 접을 것인가. 아웃 계산(semibluff)과 별개 축이다.
        # 안 접는 상대에게 세미블러프는 순수 드로우 플레이가 된다.
        if has_c and opp_est:
            _fe = PS.sk(profile, 'fold_equity')/10.0
            _rdf = PS.read_opponent(profile, opp_est)
            if _rdf.get('w', 0) > 0:
                _fg = PS.street_gap(_rdf, street)
                p *= max(0.40, min(1.80, 1.0 + _fe*_rdf['w']*2.2*_fg))
        # 턴/리버 카드가 누구를 도왔는가. 브릭이면 배럴이 먹히고
        # 상대를 도운 카드면 멈춰야 한다.
        # texture.turn_card_effect 가 이걸 재는데 호출부가 없었다.
        if street in ('turn', 'river') and len(board) >= 4 and has_c:
            _tce = TX.turn_card_effect(board[:3], board[3] if street == 'turn' else board[-1],
                                       aggressor_range_high=bool(initiative))
            _bt = min(1.0, PS.sk(profile, 'board_texture')/7.0)
            p *= max(0.35, min(1.70, 1.0 + 0.75*_tce*_bt))
        _mw2 = PS.sk(profile, 'multiway')/10.0 if has_c else 0.5
        p *= (1 - (0.12 + 0.20*_mw2)*max(0, n_opp-1))
        # 동크는 '알려진 어그레서보다 먼저 리드한다'는 뜻이다.
        # 어그레서가 없으면 체크어라운드/림프팟의 lead이지 donk가 아니다.
        # 따라서 절대 좌석 OOP를 donk 억제의 대체 신호로 쓰지 않는다.
        _oop_a = (oop_vs_aggr is True)
        if not initiative and _oop_a:
            # 동크(같은 스트리트 선제)는 정석이 아니다. 수동형일수록 강하게 억제.
            supp = 0.92 - 0.05*a - 0.02*profile.get('bluff', 5)
            if has_c and outs >= 8:
                supp = max(0.45, supp - 0.020*PS.sk(profile, 'probe'))
            # **프로브는 동크가 아니다.** 상대가 이전 스트리트를 체크백했으면
            # 그 사람 레인지가 약하다는 뜻이라 먼저 치는 것이 정석이다.
            # 예전에는 probe 개념이 동크 억제에만, 그것도 outs>=8 일 때만
            # 쓰여서 프로브 스팟 자체가 표현되지 않았다.
            if has_c and (plan_state or {}).get('opp_checked_prev'):
                supp *= max(0.25, 1.0 - 0.085*PS.sk(profile, 'probe'))
            p *= max(0.03, 1.0 - max(0.30, min(0.97, supp)))
        p *= _dc_boost
        # **clamp 이후 값으로 로그를 만든다.** 예전에는 원본 p 로 문자열을
        # 만들어 115% 같은 불가능한 확률이 기록됐다(실제 반환은 0.95).
        _fp = max(0.02, min(0.95, p))
        return _fp, '블러프 계획 실행(%.0f%%)' % (_fp*100)

    if plan == 'block':
        # 상수 0.80 이었다. 블락벳은 개념이 있어야 실행하는 라인인데
        # 계획만 잡히면 전원이 같은 빈도로 쳤다.
        _bb = 0.80
        if has_c:
            _bb = 0.35 + 0.055*PS.sk(profile, 'blockbet')
        return max(0.15, min(0.92, _bb)), '블락벳 계획(%.0f%%)' % (_bb*100)

    if plan == 'pot_control':
        # 팟컨트롤인데 3분의 1 확률로 벳하면 계획과 행동이 어긋난다.
        # 치기로 했으면 그건 이미 팟컨트롤이 아니다 —
        # 얇은 밸류라면 river_fix 가 thin_river 로 승격시켰어야 한다.
        if rel < 0.30:
            return 0.04, '팟컨트롤 + 강도 %.2f → 체크' % rel
        return max(0.05, min(0.6, 0.18 + 0.035*a)), '팟컨트롤 → 대부분 체크'

    # --- 밸류 계획 ---
    p = 0.30 + 0.058*a + 0.018*profile.get('gamble', 5)
    # 지연 씨벳은 블러프만의 기술이 아니다. 플랍 체크 범위에는 밸류도
    # 포함돼야 하므로, 실제 플랍 체크 후 턴 밸류벳에도 같은 delayed-cbet
    # 숙련도 배수를 적용한다. 한쪽에만 걸면 턴 delayed range가 블러프 쪽으로
    # 비정상적으로 기운다.
    p *= _dc_boost
    if has_c and rel < 0.85:
        p *= (0.55 + 0.09*PS.sk(profile, PS.street_concept('thin_value', street)))
    # derive()['value'] 는 구형 호환/설명 필드다.
    # checkraise_flop 에서 만든 'xr' 라벨이 일반 밸류벳 빈도를 줄이면
    # 플랍 XR 숙련도가 턴/리버 밸류벳까지 새는 도메인 누수가 된다.
    # trap/induce 는 line-plan 단계가 이미 직접 결정한다.
    if street == 'river': p *= 0.92
    if rel >= 0.65:
        p = p + (1.0 - p) * (((rel - 0.65)/0.35) ** 0.8)
    else:
        p *= (0.35 + 0.65 * (rel/0.80) ** 0.8)
    _fp = max(0.05, min(0.97, p))
    return _fp, '밸류 계획 실행(%.0f%%)' % (_fp*100)


def decide_size(profile, hero, board, street, plan, rel, opp_range, my_range,
                pot, stack, rng, opp_est=None, nut=0.0, deviating=False,
                stackoff=None, plan_state=None):
    """이 스트리트 벳 사이즈(팟 대비)를 정하는 **유일한 지점**.

    예전에는 한 사이즈가 네 번 재계산됐다:
      SIZING 표 → TX.size_fraction 과 혼합 → overbet_frac 이 덮어씀
      → RU.shape_size 가 또 흔듦
    그래서 어느 값이 최종인지 추적이 안 됐고, 개인 성향이 어디서 반영되는지도 불명확했다.

    지금은 여기 하나에서 정한다. 집행부는 이 값을 칩으로 환산만 한다.
    (shape_size 는 '사람다운 끝자리'만 만드는 표현 계층이므로 집행부에 남긴다.)
    """
    base = SIZING.get(plan, {}).get(street, 0.0)
    # 블러프 세부 전략이 사이즈를 바꾼다(bluff_mode). 예전에는 계획이
    # bluff_2street 이면 상대가 누구든 보드가 뭐든 고정값(0.45/0.60)이었다.
    #   merged    — 같은 상황의 **밸류 사이즈를 그대로** 쓴다. 위장의 핵심이라
    #               배수가 아니라 표 자체를 바꿔야 구분이 불가능해진다.
    #   polarized — 오버벳
    #   probe     — 최소 비용
    _bm = (plan_state or {}).get('bluff_mode')
    if _bm and base > 0:
        if _bm == 'merged':
            # base 만 바꾸면 뒤따르는 보정(텍스처·aggr·오버벳)이 여전히
            # 블러프 계획 기준으로 걸려 사이즈가 어긋난다. 위장이 목적이므로
            # **계획명 자체를 밸류로 바꿔** 이후 경로를 통째로 같게 만든다.
            plan = 'value_2street'
            base = SIZING.get(plan, {}).get(street, base)
        elif _bm == 'barrel':
            # 폴드율에서 역산한 **절대 사이즈**다(배수가 아니다).
            base = float((plan_state or {}).get('bluff_mul') or base)
        else:
            base *= float((plan_state or {}).get('bluff_mul') or 1.0)
    # 예산 소진 검사. 이름이 2스트리트인 계획이 3배럴이 되면 안 된다.
    # 계획을 어기고 치는 경우(deviating)는 규율 문제라 예산 밖이다.
    if not deviating:
        _left = budget_left(plan_state, plan, street)
        if _left is not None and _left <= 0:
            return 0.0
    # 보드 구조 사이징. texture.size_fraction 이 마른/연결/페어/모노톤을
    # 구분하는데 호출부가 없어 죽어 있었다. SIZING 표는 계획별 상수라
    # 같은 계획이면 어떤 보드든 같은 사이즈가 나왔다.
    if base > 0:
        _bt2 = min(1.0, PS.sk(profile, 'board_texture')/7.0) if profile.get('concepts') else 0.5
        _tf = TX.size_fraction(board, plan, street)
        base = base*(1.0 - 0.45*_bt2) + _tf*(0.45*_bt2)
    # 블로커 순 효과(밸류 관점). 콜할 콤보를 지웠으면 크게 쳐도 콜을 못 받으므로
    # 사이즈를 줄이고, 접을 콤보를 지웠으면(상대 레인지가 강함) 오히려 키운다.
    if base > 0 and plan in ('value_3street', 'value_2street', 'trap', 'thin_river'):
        _bn = (stackoff or {}).get('_blk_net') if isinstance(stackoff, dict) else None
        if _bn is None:
            _bn = 0.0
        base *= max(0.75, min(1.25, 1.0 - 2.0*_bn))
    # 에쿼티 부정 — 상대에게 드로우가 많은 보드에서 크게 쳐서 오즈를 안 준다.
    # 개념이 낮으면 젖은 보드든 마른 보드든 같은 사이즈를 친다.
    if base > 0 and profile.get('concepts') and street != 'river':
        _ed = PS.sk(profile, 'equity_denial')/10.0
        _dg = bot.board_danger(board)
        base *= 1.0 + 0.55*_ed*_dg
    # 3스트리트 밸류 계획이면 미리 배분한 사이즈를 기준으로 삼는다.
    # stackoff_plan 은 만들어져 있었지만 호출부가 없어, 스트리트마다
    # 즉흥으로 정한 사이즈가 리버에 스택을 어중간하게 남겼다.
    if base > 0 and stackoff and stackoff.get('ok') and plan == 'value_3street':
        _sf = stackoff.get(street)
        if _sf:
            base = 0.35*base + 0.65*float(_sf)
    if base <= 0:
        # SIZING 표가 0인 계획(giveup/showdown)은 '원래 안 친다'는 뜻이다.
        # 그런데 규율이 낮아 계획을 뒤집고 치기로 한 경우엔 사이즈가 필요하다.
        # 표를 고치면 계획 자체의 의미가 흐려지므로, 이탈 전용 기본값을 쓴다.
        if not deviating:
            return 0.0
        base = {'flop': 0.50, 'turn': 0.55, 'river': 0.60}.get(street, 0.50)
    # 보드 텍스처 인식 — 인식 능력만큼만 반영된다
    if profile.get('concepts'):
        tex = TX.perceived(board, PS.sk(profile, 'board_texture'), rng,
                           TX.size_fraction, plan, street)
        base = 0.45*base + 0.55*tex
    base *= (0.85 + 0.05*profile.get('aggr', 5))
    if rel < 0.45 and _bm != 'merged':
        # 약할수록 작게. **이 감쇠가 곧 사이즈에서 강도가 새는 통로다** —
        # 블러프는 정의상 약한 패라 항상 이 감쇠를 받고, 사이즈를 읽는
        # 상대에게는 그대로 노출된다. 위장형(merged)은 그래서 면제한다.
        base *= 0.80
    # 오버벳: 개념·넛우위·양극화가 갖춰졌을 때만. 판단 층에서 결정된다.
    ob = overbet_frac(profile, hero, board, opp_range, my_range, street, plan,
                      rel, rng, opp_est)
    if ob:
        return ob
    return max(0.15, min(1.0, base))


def mk_intent(act, size=0.0, src=''):
    return {'act': act, 'size': round(float(size), 3), 'src': src}


def intent_of(state, street):
    """이 스트리트에 대해 판단 층이 정한 의도. 없으면 None."""
    return (state.get('intents') or {}).get(street)


def set_intent(state, street, intent):
    st = dict(state)
    st['intents'] = dict(st.get('intents') or {})
    st['intents'][street] = intent
    return st


def apply_layer_bet_ev_judgment(state, street, bet_minus_check_ev):
    """F8-D5-C2: terminal side-pot bet/check EV를 즉시 intent에 반영.

    실행부 override가 아니다. 판단층 intent를 새 정보로 갱신한다.
    delta < 0 인 기존 bet만 check로 내린다. check를 bet으로 승격시키거나
    line plan 자체를 바꾸지 않는다.
    """
    it = intent_of(state, street)
    delta = (None if bet_minus_check_ev is None
             else float(bet_minus_check_ev))
    if not it or it.get('act') != 'bet' or delta is None:
        return state, False
    if delta >= 0:
        return state, False

    st = set_intent(
        state, street,
        mk_intent('check', 0.0,
                  'F8 layer EV: bet-check %.1f < 0 → 체크' % delta))
    st['layer_bet_ev_judgments'] = list(
        st.get('layer_bet_ev_judgments') or [])
    st['layer_bet_ev_judgments'].append({
        'street': street,
        'prior_act': 'bet',
        'new_act': 'check',
        'bet_minus_check_ev': round(delta, 6),
        'reason': 'terminal_layer_ev_negative',
    })
    st['why'] = list(st.get('why') or []) + [
        '%s: F8 side-pot terminal EV %.1f → bet 철회, check'
        % (street, delta)]
    _trace(st, street, 'layer_bet_ev',
           prior='bet', act='check', delta=round(delta, 3))
    return st, True


def record_response_plan(state, street, response):
    """상대 액션 뒤 새 judgment가 만든 **현재 액션 계획**을 보존한다.

    line plan(value_2street 등)과 별개다. 같은 스트리트에서
    bet -> call -> raise처럼 새 정보가 들어오면 response plan도 새로 생긴다.
    """
    rows = state.setdefault('response_plans', {})
    rows.setdefault(street, []).append(dict(response))
    state['_last_response_plan'] = dict(response)
    return response


STREET_ORDER = ['flop', 'turn', 'river']

# 계획 이름이 뜻하는 **예산** — 몇 스트리트를 칠 작정인가.
# SIZING 표와 분리한 이유: 예전에는 river:0.0 하나가 '예산 소진'과
# '원래 안 치는 계획'을 동시에 뜻해서, bet_size 의 `base <= 0` 가드가
# 둘을 구분하지 못했다. 사이즈는 SIZING 이, 예산은 여기가 맡는다.
# value_3street 은 스트리트가 셋뿐이라 실제로는 걸리지 않는다(명시 목적).
BUDGET = {'value_2street': 2, 'value_3street': 3}


def budget_left(plan_state, plan, street):
    """이 계획이 앞으로 더 칠 수 있는 스트리트 수. 예산 개념이 없으면 None.

    지출은 bet_streets(실제로 공격한 스트리트)로 세되, 계획을 채택한
    시점(plan_since) 이후만 센다.
    """
    cap = BUDGET.get(plan)
    if cap is None:
        return None
    since = (plan_state or {}).get('plan_since') or 'flop'
    i0 = STREET_ORDER.index(since) if since in STREET_ORDER else 0
    spent = sum(1 for s in ((plan_state or {}).get('bet_streets') or [])
                if s in STREET_ORDER and STREET_ORDER.index(s) >= i0)
    return cap - spent


SIZING = {
    'value_3street': {'flop':0.60,'turn':0.70,'river':0.75},
    # river 가 0 이면 bet_size 의 `base <= 0` 가드가 '원래 안 치는 계획'으로 읽는다.
    # 그 0 은 사이즈가 아니라 '예산을 다 썼다'는 뜻이었는데 giveup/showdown 의 0 과
    # 구분되지 않아서, **턴에서 승격된 value_2street 이 rel 0.93 을 들고도
    # 리버를 체크했다.** (계획을 어기는 deviating 경로로만 칠 수 있었다)
    # 예산과 사이즈를 한 표에 겹쳐 담은 것이 원인이고, 예산 카운터 분리는 별건이다.
    # 여기서는 사이즈만 채운다 — 값은 deviating 폴백이 쓰던 리버 기본값과 같다.
    'value_2street': {'flop':0.50,'turn':0.55,'river':0.60},
    'pot_control':   {'flop':0.30,'turn':0.0, 'river':0.30},
    'semibluff':     {'flop':0.55,'turn':0.65,'river':0.0},
    'bluff_2street': {'flop':0.45,'turn':0.60,'river':0.0},
    # 리버 전용. bluff_2street 은 이름 그대로 2스트리트라 리버가 0 인데,
    # river_fix 가 미스한 드로우를 그리로 보내면 **칠 수단이 없어진다.**
    # '플랍부터 이어온 블러프의 리버'와 '리버에서 새로 시작한 블러프'는
    # 다른 계획이므로 이름을 나눈다.
    'river_bluff':   {'flop':0.0, 'turn':0.0, 'river':0.72},
    # 리버 얇은 밸류. value_2street 도 리버가 0 이라 얇은 밸류를 뽑는
    # 경로가 아예 없었다.
    'thin_river':    {'flop':0.0, 'turn':0.0, 'river':0.42},
    'trap':          {'flop':0.0, 'turn':0.65,'river':0.75},
    'giveup':        {'flop':0.0, 'turn':0.0, 'river':0.0},
    'block':         {'flop':0.25,'turn':0.28,'river':0.30},
    'showdown':      {'flop':0.0, 'turn':0.0, 'river':0.0},
}

def overbet_frac(profile, hero, board, opp_range, my_range, street, plan, rel, rng,
                 opp_est=None):
    """오버벳(팟 초과) 사이즈를 낼지, 낸다면 얼마나. 안 내면 None.

    오버벳은 아무나 치는 게 아니다. 세 가지가 동시에 필요하다:
      1. 개념 보유 — sk('overbet'). 이 개념이 낮으면 아예 선택지에 없다.
      2. 넛 우위 — 내 레인지가 상대보다 넛 구간을 많이 점유해야 한다.
         우위 없이 오버벳하면 레이즈당하고 끝난다.
      3. 양극화된 라인 — 밸류 극단 아니면 순수 블러프. 미들레인지는 오버벳하지 않는다.

    트랩(플랍 체크)으로 상대 레인지에 약한 핸드를 남겨두면 리버 넛 우위가 커진다.
    '플랍 트랩 → 리버 오버벳'은 그래서 성립하는 라인이다.
    """
    if street == 'flop': return None                # 플랍 오버벳은 다루지 않는다
    ob = PS.sk(profile, 'overbet') if profile.get('concepts') else 2.0
    nut = R.nut_advantage(my_range, opp_range, board) if (my_range and opp_range) else 0.0

    # 예전에는 ob<4.0, nut<0.10, rel>=0.85 / rel<=0.25 네 개가 전부 하드 컷이었다.
    # 개념 3.9 와 4.1 이 완전히 다른 사람이 되고, rel 0.84 는 오버벳이
    # 아예 불가능했다. 전부 연속 가중으로 바꾼다 — 조건이 약하면
    # 확률이 낮아질 뿐 선택지에서 사라지지는 않는다.
    value_line = plan in ('value_3street', 'trap')
    bluff_line = plan in ('bluff_2street', 'semibluff', 'river_bluff')
    if not (value_line or bluff_line): return None  # 계획 자체가 아니면 제외

    # 양극화 정도. 밸류는 rel 이 높을수록, 블러프는 낮을수록 오버벳에 맞는다.
    pol = (max(0.0, (rel - 0.62) / 0.30) if value_line
           else max(0.0, (0.42 - rel) / 0.30))
    pol = min(1.0, pol)
    if pol <= 0.02: return None                     # 미들레인지는 제외

    p = 0.16 * max(0.0, min(1.0, (ob - 2.5) / 5.0))  # 개념 숙련도, 연속
    p *= (0.25 + 1.9*max(0.0, min(0.5, nut)))        # 넛 우위에 비례
    p *= pol
    p *= (0.75 + 0.05*profile.get('aggr', 5))
    if street == 'river': p *= 1.35                 # 리버가 오버벳의 주 무대
    if bluff_line: p *= 0.65                        # 블러프 오버벳은 더 드물다
    # 상대가 큰 사이즈에 어떻게 반응하는가 — 오버벳 판단의 나머지 절반이다.
    # 잘 접는 상대에게 밸류 오버벳은 손해고(콜을 못 받음),
    # 안 접는 상대에게 블러프 오버벳은 자살이다. 방향이 정반대다.
    if opp_est:
        # read_opponent 를 쓴다. 예전에는 opp_est['ftb'] 를 날것으로 읽어
        # see_freq 게이트를 우회했다 — 빈도를 못 세는 사람도
        # 상대 폴드율에 완전히 반응했다.
        _rdo = PS.read_opponent(profile, opp_est)
        if _rdo.get('w', 0) > 0:
            d = PS.street_gap(_rdo, street)
            mult = (1.0 - 1.6*d) if value_line else (1.0 + 1.6*d)
            p = PS.blend(p, p*max(0.25, mult), _rdo['w'])
    if rng.random() > max(0.0, min(0.55, p)): return None

    # 사이즈: 넛 우위가 클수록 크게
    base = 1.15 + 0.55*min(1.0, nut) + 0.03*(ob - 4.0)
    return round(min(2.2, base * rng.uniform(0.92, 1.10)), 2)


def cbet_freq(profile, board, n_opp, street, oop, rel, opp_est=None, range_adv=0.0):
    """이니셔티브 보유자의 지속벳 빈도. 핸드 강도와 별개인 구조적 빈도.

    opp_est 가 있고 이 사람이 상대를 보는 타입이면(exploit_weight) 조정한다.
    잘 접는 상대에겐 더 치고, 안 접는 상대에겐 덜 친다 —
    익스플로잇의 가장 기본이며, 자기 전략만 치는 선수는 이 조정을 하지 않는다.
    """
    a = profile.get('aggr', 5); b = profile.get('bluff', 5)
    base = {'flop': 0.42, 'turn': 0.30, 'river': 0.22}.get(street, 0.30)
    # 스트리트별 공격 개념. street_concept 에 매핑은 있었으나 'cbet'/'barrel'
    # 키로 부르는 곳이 없어 cbet_flop/barrel_turn/barrel_river 가 전부 죽어 있었다.
    # 그래서 '플랍은 잘 치는데 턴에서 멈추는 사람'이 표현되지 않았다 —
    # 스트리트 구분이 상수표로만 되고 전원 공통이었다.
    if profile.get('concepts'):
        _sc = PS.sk(profile, PS.street_concept('cbet', street))
        base *= max(0.35, min(1.85, 0.45 + 0.11*_sc))
    f = base + 0.035*a + 0.020*b
    # 다인원 축소. 예전에는 0.62 고정이라 **누구나 같은 비율로** 줄였다.
    # 실제로는 제대로 조이는 사람과 헤즈업처럼 치는 사람이 갈린다.
    _mw = PS.sk(profile, 'multiway')/10.0 if profile.get('concepts') else 0.5
    f *= ((0.80 - 0.30*_mw) ** max(0, n_opp-1))
    # 보드 구조. board_danger(젖은 정도)만 보면 A하이·페어보드처럼
    # '아무도 못 맞은' 보드에서 쳐야 한다는 것이 안 나온다.
    # texture.cbet_multiplier 가 그 구조를 이미 갖고 있었는데 호출부가 없었다.
    _bt = min(1.0, PS.sk(profile, 'board_texture')/7.0) if profile.get('concepts') else 0.5
    _cm = TX.cbet_multiplier(board, not oop)
    f *= 1.0 + (_cm - 1.0) * _bt            # 개념이 낮으면 구조를 못 읽는다
    f *= (1 - 0.18*bot.board_danger(board)) # 젖은 정도는 남기되 비중을 줄인다
    if oop: f *= 0.88
    f += 0.35*max(0.0, rel-0.6)             # 강할수록 추가
    # 레인지 우위. 씨벳 빈도의 가장 큰 구조적 근거인데 예전에는 들어가지 않았다.
    # 개념(board_texture)이 없으면 보드가 누구에게 유리한지 못 읽는다.
    if range_adv:
        _ba = min(1.0, PS.sk(profile, 'board_texture')/7.0) if profile.get('concepts') else 0.5
        f *= max(0.45, min(1.75, 1.0 + 0.85*range_adv*_ba))
    if opp_est:
        # read_opponent 경유. 예전에는 opp_est['ftb'] 를 날것으로 읽어
        # see_freq 게이트를 우회했다 — 빈도를 못 세는 사람도
        # 상대 폴드율에 완전히 반응했다. 그리고 스트리트 구분도 없었다.
        _rdc = PS.read_opponent(profile, opp_est)
        if _rdc.get('w', 0) > 0:
            adj = f * (1.0 + 1.10*PS.street_gap(_rdc, street))
            f = PS.blend(f, adj, _rdc['w'])
    return max(0.03, min(0.95, f))

def _trace(st, street, kind, **kw):
    """판단 흔적. 리뷰가 '왜 그랬는지'를 재구성하는 데 쓴다.

    오늘 디버깅에서 매번 부족했던 것들이다 —
    확률과 **주사위 눈**을 함께 남겨야 '확률이 낮아서 체크'와
    '아예 0이라 체크'를 구분할 수 있다.
    상한을 두어 무한히 쌓이지 않게 한다.
    """
    if st is None:
        return
    tr = st.setdefault('trace', [])
    if len(tr) < 40:
        rec = {'street': street, 'kind': kind}
        rec.update(kw)
        tr.append(rec)


def act_with_plan(hero, board, profile, plan_state, pot, tocall, stack, street,
                  initiative=True, opp_range=None, bf=1.0, seed=None,
                  n_opp=1, to_act_behind=0, read=None, opp_est=None,
                  opp_ranges=None, facing_seat=None, checked_before=False,
                  can_raise=True, checkraise_seed=None, checkraise_size_seed=None,
                  facing_size_frac=None, hero_contrib=0, response_kind=None,
                  response_context=None, call_value=None):
    """계획을 스트리트에 걸쳐 실행. 체크레이즈·커밋 판단 포함."""
    # ICM 인지. 예전에는 이 두 줄이 docstring **앞에** 있어서
    # docstring 이 첫 문장이 아니게 되고 __doc__ 이 None 이 됐다.
    #
    # 그리고 식이 icm_press() 와 달랐다 — 여기만 하한이 없어
    # icm 개념 0 인 사람이 버블을 **완전히** 무시했다.
    # '이번에 죽으면 상금을 못 받는다'는 개념이 아니라 상식이다.
    # 계산을 두 곳에 다르게 두면 이런 차이가 조용히 생긴다.
    if profile.get('concepts') and bf and bf > 1.0:
        bf = PS.icm_bf(profile, bf)
    rng = random.Random(seed)
    plan = plan_state['plan']
    if opp_est is None:
        opp_est = plan_state.get('opp_est')      # 계획에 실린 추정치를 이어 쓴다
    # (예전에 `frac = SIZING[plan].get(street, 0.0)` 이 여기 있었다. 대입만
    #  하고 함수 안에서 한 번도 읽지 않는 죽은 줄이었고, SIZING 에 없는
    #  계획이 오면 KeyError 만 낼 수 있었다. 사이즈는 decide_size 가 정한다.)
    committed = spr(stack, pot) < 1.2          # 커밋 구간
    if response_kind is not None:
        plan_state['_last_response_kind'] = response_kind
    if response_context is not None:
        plan_state['_last_response_context'] = dict(response_context)

    if tocall > 0:
        callers = [(0.30, 5)]*max(0, n_opp-1)
        _pools = _normalize_opp_pools(opp_range, n_opp, opp_ranges)
        if _pools:
            # session 이 현재 스트리트의 bet/call/raise까지 상대별로 이미
            # perceived_range 에 반영해 넘긴다. 다시 bettor 액션을 한 번 더
            # 먹이면 같은 벳을 중복 관측하게 된다.
            eq = bot.equity_vs_combos(hero, board, _pools, sims=600)
        elif opp_range and len(opp_range) >= 20:
            # 상대가 실제로 밟아온 액션 경로로 좁혀진 레인지가 있으면 그것을 쓴다.
            # 여기서 다시 22% 고정 가정으로 돌아가면 콜/폴드 판단만 리딩을 못 받는다.
            sz = tocall/max(1.0, float(pot))
            # 상대의 사이즈 습관을 반영한다.
            # 항상 같은 사이즈만 치는 사람(size_info 낮음)은 사이즈가 레인지를
            # 나누지 않는다. 그런 상대의 이번 사이즈는 정보가 아니므로
            # 그 사람의 평균 쪽으로 되돌려 해석한다.
            # 사이즈를 섞는 사람이면 실제 사이즈를 그대로 믿는다.
            _rdo = PS.read_opponent(profile, opp_est)
            if _rdo['w'] > 0 and opp_est and opp_est.get('sz_mean'):
                _pull = _rdo['w'] * (1.0 - _rdo.get('size_info', 0.0))
                if _pull > 0:
                    sz = sz*(1.0 - _pull) + float(opp_est['sz_mean'])*_pull
            # 상대 레인지는 '내가 관찰한 상대 추정치'로 모델링한다.
            # profile 은 나 자신이므로 여기 쓰면 내 블러프 성향을 상대에게 투영하게 된다.
            # perceived_range 를 써야 한다. narrow_by_actions 를 직접 부르면
            # range_read 가 낮은 사람도 완전한 축소를 얻어, session 에서 걸러둔
            # 인식 한계가 여기서 무효화된다.
            # 인식 주체는 '나'(profile)다 — opp_est 는 상대 성향 모델링용이다.
            bet_r = R.perceived_range(opp_range, board,
                                      [(street, 'bet', sz)], profile)
            eq = bot.equity_vs_combos(hero, board,
                                      [bet_r] + [opp_range]*max(0, n_opp-1),
                                      sims=600)
        else:
            eq = bot.equity_vs_betting(hero, board, [(0.22, profile['bluff'])], callers,
                                       street, sims=600, seed=seed)
        # pot 은 pot_live 다 — 상대가 방금 낸 벳이 이미 포함돼 있고
        # **내 콜은 아직 아니다.** 팟오즈 분모에는 내 콜도 들어가야 하므로
        # calldown_need 가 tocall 을 한 번 더한다 (거기 주석 참조).
        # 예전에 여기 "두 번 들어가면 안 된다"고 적혀 있었는데 틀렸다 —
        # 한 번은 상대 벳으로, 한 번은 내 콜로 들어가는 것이 맞다.
        _objective_be = (
            float(call_value.get('breakeven_equity'))
            if (call_value and call_value.get('breakeven_equity') is not None)
            else None)
        _need_out = calldown_need(
            profile, hero, board, street, pot, tocall, bf,
            read, to_act_behind, opp_est, n_opp=n_opp, rng=rng,
            facing_size_frac=facing_size_frac,
            objective_breakeven=_objective_be)
        if _objective_be is None:
            need = _need_out
            _call_need = None
            _call_eq = None
        else:
            need, _call_need = _need_out
            _call_eq = float(call_value.get('effective_equity'))
        # made_now 계산이 calldown_need 로 딸려 들어갔다. 여기서도 필요하다.
        made_now = bot.made_strength(hero, board) if board else 0
        # ---------- 저항(tocall>0): 판단 -> response plan -> 집행 ----------
        # 체크 후 벳을 맞은 경우의 raise 는 checkraise_decision 한 곳만 만든다.
        # 예전에는 generic decide_response 가 먼저 raise 를 만들 수 있었고,
        # call/fold 일 때만 session 의 checkraise gate가 한 번 더 돌아
        # checkraise_flop/late 숙련도를 우회하는 중복 producer 였다.
        _need_in = need
        if checked_before and can_raise:
            _ckr = checkraise_decision(
                hero, board, profile, plan_state, pot, tocall, stack, street,
                seed=(checkraise_seed if checkraise_seed is not None else seed),
                opp_est=opp_est)
            if _ckr:
                _ckr_rng = random.Random(
                    checkraise_size_seed if checkraise_size_seed is not None else seed)
                _amt = checkraise_size(
                    profile, pot, tocall, stack, board, street, _ckr_rng)
                plan_state['_last_response_source'] = 'checkraise_gate'
                why = '체크 후 새 판단 → 체크레이즈 실행'
                plan_state.setdefault('acts', []).append(why)
                record_response_plan(plan_state, street, {
                    'response_kind': response_kind,
                    'context': dict(response_context or {}),
                    'act': 'raise',
                    'target': _amt,
                    'size_mult': None,
                    'need': round(need, 4),
                    'eq': round(eq, 4),
                    'source': 'checkraise_gate',
                    'why': why,
                })
                _trace(plan_state, street, 'response', act='raise',
                       source='checkraise_gate', response_kind=response_kind,
                       need=round(need, 3),
                       need_raw=round(_need_in, 3), eq=round(eq, 3), why=why,
                       plan=plan, tocall=tocall, pot=pot)
                return ('raise', _amt), eq, need

        # 체크레이즈 gate가 거절했거나, 아직 체크하지 않은 일반 facing-bet 상태.
        # checked_before=True 이면 generic reraise/bluff raise는 금지한다.
        # raise 권리가 닫힌 incomplete-allin 상태도 계획 단계에서 raise를 제거한다.
        _direct_raise = bool(can_raise and not checked_before)
        act, mult, need, why = decide_response(
            profile, hero, board, street, plan, plan_state, eq, need,
            made_now, opp_range, pot, tocall, stack, committed, rng,
            allow_raise=_direct_raise,
            call_eq=_call_eq, call_need=_call_need)
        _source = ('checkraise_declined' if checked_before else 'generic_response')
        plan_state['_last_response_source'] = _source
        plan_state.setdefault('acts', []).append(why)
        _rp = {
            'response_kind': response_kind,
            'context': dict(response_context or {}),
            'act': act,
            'target': None,
            'size_mult': (round(float(mult), 4) if act == 'raise' else None),
            'need': round(need, 4),
            'eq': round(eq, 4),
            'call_eq': (round(_call_eq, 4) if _call_eq is not None else None),
            'call_need': (round(_call_need, 4) if _call_need is not None else None),
            'layer_call_used': bool(_call_eq is not None and _call_need is not None),
            'source': _source,
            'why': why,
        }
        _trace(plan_state, street, 'response', act=act, source=_source,
               response_kind=response_kind,
               need=round(need, 3), need_raw=round(_need_in, 3),
               eq=round(eq, 3), why=why, plan=plan, tocall=tocall, pot=pot)
        if act == 'raise':
            # 반환 amt 는 Round.apply 가 기대하는 **street 총 contribution target**이다.
            #
            # 첫 액션(hero_contrib=0)에서는 종전 식과 동일하다.
            # hero가 이미 bet/raise 한 뒤 재레이즈를 맞은 경우에는
            # 현재까지 넣은 칩을 target 좌표에 다시 더해야 한다.
            #
            # 예:
            #   pot_live 300, hero contrib 50, tocall 100, mult 1.0
            #   pot-size re-raise target = 50 + 300 + 200 = 550
            # 종전 식은 500으로 50을 누락했다.
            _hc = max(0.0, float(hero_contrib or 0))
            _base = int(round((pot + 2*tocall)*mult/100))*100
            _max_target = float(stack) + _hc
            amt = min(_max_target, _hc + _base)
            # call target도 street 총 contribution 좌표다.
            # amt를 단순 tocall과 비교하면 이미 넣은 칩만큼 좌표가 어긋난다.
            _call_target = _hc + float(tocall)
            if amt <= _call_target:
                _rp['act'] = 'call'
                _rp['target'] = float(_call_target)
                _rp['why'] = _rp['why'] + ' | raise target <= call target → call'
                record_response_plan(plan_state, street, _rp)
                return ('call', tocall), eq, need
            _rp['target'] = int(amt)
            record_response_plan(plan_state, street, _rp)
            return ('raise', int(amt)), eq, need
        if act == 'call':
            _rp['target'] = float(hero_contrib or 0) + float(tocall)
            record_response_plan(plan_state, street, _rp)
            return ('call', tocall), eq, need
        _rp['target'] = float(hero_contrib or 0)
        record_response_plan(plan_state, street, _rp)
        return ('fold', 0), eq, need

    # ---------- 무저항(tocall==0): 순수 집행 ----------
    # 여기서 "칠까 말까"를 다시 결정하지 않는다.
    # 그 판단은 전부 판단 층(decide_aggression / decide_size)이 이미 내렸고,
    # 결과는 plan_state['intents'][street] 에 들어 있다.
    # 집행부의 유일한 일은 그 의도를 칩으로 환산하는 것이다.
    it = intent_of(plan_state, street)
    if it is None:
        # 의도가 없다 = 판단 층이 이 스트리트를 아직 안 봤다.
        # 조용히 추측하지 말고 체크한다 (그리고 불변식이 이걸 잡는다).
        return ('check', 0), None, None
    if it['act'] == 'check':
        return ('check', 0), None, None
    if it.get('size', 0) <= 0:
        plan_state.setdefault('deviations', []).append(
            {'street': street, 'planned': 'bet', 'executed': 'check',
             'why': '의도 사이즈 0'})
        return ('check', 0), None, None
    amt = min(stack, int(round(pot*it['size']/100))*100)
    if amt <= 0:
        # 의도는 벳인데 칩으로 환산하니 0이 됐다 (팟이 작아 반올림 소실).
        # 이건 판단 변경이 아니라 환산 한계이므로 그 사실을 남긴다.
        plan_state.setdefault('deviations', []).append(
            {'street': street, 'planned': 'bet', 'executed': 'check',
             'why': '사이즈 %.2f팟이 최소단위 미만' % it.get('size', 0)})
        return ('check', 0), None, None
    return ('bet', amt), None, None


def checkraise_decision(hero, board, profile, plan_state, pot, tocall, stack, street,
                        seed=None, opp_est=None):
    """체크 후 벳을 맞았을 때 레이즈할지. 개념 보유·성향·강도의 함수."""
    import archetypes as _A
    rng = random.Random(seed)
    if profile.get('concepts'):
        sk = PS.sk(profile, PS.street_concept('checkraise', street))/3.33
    else:
        T = profile.get('type')
        sk = _A.skill(T, 'checkraise') if T in _A.ARCHETYPES else 2
    if sk <= 0.2: return False
    plan = plan_state.get('plan')
    rel = plan_state.get('rel', 0.5)
    outs = plan_state.get('outs', 0)
    p = 0.0
    if plan == 'trap':
        p = 0.55 + 0.12*sk
    elif plan == 'semibluff' and outs >= 8 and street != 'river':
        p = 0.06 + 0.115*sk
    elif plan == 'bluff_2street':
        p = 0.03 + 0.05*sk
    # 강한 핸드의 밸류 체크레이즈. 예전에는 rel>=0.90 하드 컷이라
    # rel 0.89 는 아예 못 했고, 순서상 trap 다음이라 밸류 계획이
    # semibluff 분기보다 먼저 잡아채는 문제도 있었다.
    _val = max(0.0, min(1.0, (rel - 0.72) / 0.22))
    p = max(p, (0.10 + 0.11*sk) * _val)
    p *= (0.7 + 0.05*profile.get('aggr', 5))
    # 블러프 체크레이즈는 '상대가 **벳한 뒤 레이즈에 접는가**'를 봐야 한다.
    # 예전에는 street_gap = fold-to-bet 을 재사용했는데, 그건 전혀 다른 사건이다:
    #   fold-to-bet: 내가 벳을 맞고 접는가
    #   fold-to-raise: 내가 먼저 벳한 뒤 레이즈를 맞고 접는가
    # 전용 postflop fold-to-raise read가 아직 없으므로, 잘못된 신호를 쓰지 않는다.
    # opp_est 인자는 향후 그 전용 관측을 연결할 자리로 유지한다.
    return rng.random() < max(0.0, min(0.90, p))


def preflop_plan(profile, pos, hand, bb, rng, aggressor_pos=None, open_bb=0.0,
                 n_callers=0, n_limpers=0, raise_level=1, behind_stacks=None,
                 tilt=0.0, field_q=0.6, opp_est=None, bf=1.0,
                 seats=8, ante=True, field_avg_bb=None, erosion=0.0,
                 payout_flat=0.0, reentry=False, progress=0.0,
                 behind_est=None, limper_est=None, bb_chips=None,
                 opener_allin=False, money_open=None, can_check=False,
                 can_raise=True, pot_bb=None, to_call_bb=None,
                 prior_pf=None, pot_layers=None):
    """프리플랍 판단 층. 액션과 함께 **이 핸드를 어떻게 칠 것인가**를 남긴다.

    예전에는 preflop.py 의 세 함수(open/iso/defend)가 각자 액션만 내고 끝났다.
    그래서 '왜 3벳했는가'가 플랍 계획에 이어지지 않았고,
    포스트플랍 계획이 매번 백지에서 시작했다.

    반환: (act, size_bb, plan_seed)
      plan_seed 는 포스트플랍 계획의 출발점이 되는 사전 정보다.
    """
    import preflop as _pf
    # 상대 정보가 프리플랍 레인지부터 움직인다.
    # 예전에는 preflop_plan 이 opp_est 를 아예 안 받아서,
    # 상대가 3벳에 과하게 접는 걸 알아도 3벳 레인지가 안 넓어졌다.
    # 잘 접는 상대의 오픈에는 3벳을 넓히고, 안 접는 상대에겐 좁힌다.
    # 실제 반영은 defend_decision(exploit=rd) 안의 역치 보정에서 이뤄진다.
    rd = PS.read_opponent(profile, opp_est)
    if aggressor_pos is None and not n_limpers:
        a, sz = _pf.open_decision(profile, pos, bb, hand, rng,
                                  behind_stacks=behind_stacks,
                                  tilt=tilt, field_q=field_q, bf=bf,
                                  seats=seats, ante=ante,
                                  field_avg_bb=field_avg_bb, erosion=erosion,
                                  payout_flat=payout_flat, reentry=reentry,
                                  progress=progress,
                                  behind_reads=[PS.read_opponent(profile, e)
                                                for e in (behind_est or []) if e],
                                  bb_chips=bb_chips,
                                  money_open=money_open)
        role = 'open'
    elif aggressor_pos is None:
        a, sz = _pf.iso_decision(
            profile, pos, hand, n_limpers, bb, rng,
            limper_reads=[PS.read_opponent(profile, e)
                          for e in (limper_est or []) if e],
            behind_stacks=behind_stacks,
            behind_reads=[PS.read_opponent(profile, e)
                          for e in (behind_est or []) if e],
            seats=seats, ante=ante,
            field_avg_bb=field_avg_bb, erosion=erosion, field_q=field_q, bf=bf,
            can_check=can_check)
        role = 'iso'
    else:
        a, sz = _pf.defend_decision(profile, pos, aggressor_pos, hand, bb, open_bb,
                                    n_callers, rng, raise_level=raise_level,
                                    stack_bb=bb, tilt=tilt, field_q=field_q,
                                    exploit=rd, bf=bf, seats=seats, ante=ante,
                                    payout_flat=payout_flat,
                                    reentry=reentry, progress=progress,
                                    opener_allin=opener_allin, can_raise=can_raise,
                                    pot_bb=pot_bb, to_call_bb=to_call_bb)
        role = 'defend'

    # 현재 판단 사건의 종류. 행동 결과만 남기면
    # cold 4bet / opener 4bet / caller backraise 가 모두 'defend'로 뭉개진다.
    _prev = dict(prior_pf or {})
    _prev_act = _prev.get('pf_act')
    _prev_role = _prev.get('pf_role')
    if aggressor_pos is None:
        _decision_kind = 'limped_unopened' if n_limpers else 'unopened'
    elif not _prev:
        _decision_kind = ('face_first_open' if raise_level <= 1
                          else 'cold_vs_reraise')
    elif _prev_act in ('call', 'limp', 'check'):
        _decision_kind = 'caller_backaction'
    elif _prev_role == 'open':
        _decision_kind = 'opener_backaction'
    else:
        _decision_kind = 'reraiser_backaction'

    # 프리플랍에서 확정된 것들 — 포스트플랍 계획이 이걸 물려받는다
    seed_info = {
        'pf_role': role,                       # open / iso / defend
        'pf_act': a,                           # raise / call / limp / shove / fold
        'pf_decision_kind': _decision_kind,
        'pf_pos': pos,
        'pf_vs': aggressor_pos,
        'pf_level': raise_level,
        'pf_open_bb': float(open_bb or 0.0),
        'pf_n_callers': int(n_callers or 0),
        'pf_n_limpers': int(n_limpers or 0),
        'pf_can_raise': bool(can_raise),
        'pf_facing_allin': bool(opener_allin),
        'pf_pot_bb': (float(pot_bb) if pot_bb is not None else None),
        'pf_to_call_bb': (float(to_call_bb) if to_call_bb is not None else None),
        # F8-D6-A provenance only. Same layer schema as postflop; no strategy use yet.
        'pf_pot_layers': [dict(x) for x in (pot_layers or [])],
        # D2 provenance: later streets must not rebuild an all-in player's
        # preflop range from current stack=0.
        'pf_stack_bb': float(bb or 0.0),
        'pf_initiative': a in ('raise', '3bet', 'shove'),
        'pf_multiway': (n_callers + n_limpers) >= 2,
        'pf_hand_pct': _pf.pct(hand),
        'money_open': dict(money_open or {}) if role == 'open' else None,
    }
    return a, sz, seed_info


def update_plan(state, hero, board, my_range, opp_range, profile, pot, stack,
                street, seed, n_opp, behind, prev_board, oop, initiative,
                opp_est=None, opp_stack_bb=None, tilt=0.0, first=False,
                pf_seed=None, bb_chips=None,
                oop_vs_aggr=None, oop_legacy_abs=None, opp_ranges=None,
                opp_checked_prev=None):
    """계획 갱신의 **유일한 진입점**.

    예전에는 session 이 make_plan / revise_plan / refresh / river_fix / _allowed 를
    직접 순서대로 불렀다. 다섯 함수가 각자 dict 를 새로 만들거나 갈아엎어서
    (1) 순서에 의존하고 (2) 이력(intents/deviations)이 중간에 사라졌다.

    여기서 순서를 한 번만 정의한다. 각 단계는 아래 헬퍼로 남아 있지만
    호출부는 이 함수 하나만 쓴다.

      생성/재수립 → 보드변화 재평가 → 스트리트 재평가 → 리버 정리
      → 개념 보유 검사 → 의도 확정
    """
    import runner as _RU
    rng = random.Random(seed)
    prev = dict(state) if state else None

    if first or state is None:
        st = make_plan(hero, board, my_range, opp_range, profile, pot, stack, street,
                       seed=seed, n_opp=n_opp, to_act_behind=behind,
                       oop_vs_aggr=oop_vs_aggr, initiative=initiative,
                       opp_est=opp_est, opp_stack_bb=opp_stack_bb, tilt=tilt,
                       bb_chips=bb_chips, oop_legacy_abs=oop_legacy_abs,
                       opp_ranges=opp_ranges)
        # 프리플랍에서 확정된 것을 물려받는다. 이게 없으면 포스트플랍 계획이
        # 매번 백지에서 시작하고, '왜 3벳했는가'가 플랍 판단과 무관해진다.
        if pf_seed:
            st.update({k: v for k, v in pf_seed.items()})
            if pf_seed.get('pf_role') == 'defend' and pf_seed.get('pf_initiative'):
                # 3벳 이상으로 들어온 팟은 내 레인지가 강하게 대표된다.
                # defend_decision 은 공격 액션을 '3bet'/'shove'로 반환하므로
                # 예전 pf_act=='raise' 조건은 실제로 영원히 닫혀 있었다.
                st['why'] = (st.get('why') or []) + ['프리플랍 3벳+ 팟 → 레인지 우위']
    else:
        st = _RU.revise_plan(
            state, hero, board, my_range, opp_range, profile,
            pot, stack, street, seed, n_opp, behind, prev_board,
            oop_vs_aggr=oop_vs_aggr,
            oop_legacy_abs=oop_legacy_abs,
            initiative=initiative, opp_ranges=opp_ranges)

    # 계획 이력은 라벨과 별개로 이어진다. 새 dict 가 만들어져도 유지한다.
    if prev:
        for k in ('intents', 'deviations', 'streets', 'refreshed', 'bet_streets',
                  'executed_actions', 'plan_since', '_rsig', '_opps_sig'):
            if prev.get(k) is not None and st.get(k) is None:
                st[k] = prev[k]

    # 갱신 조건. 예전에는 '스트리트당 한 번'이었는데, **상대 레인지는 같은
    # 스트리트 안에서도 액션마다 좁혀진다.** 보드 의존 지표에는 그 가드가
    # 맞지만 레인지 의존 지표(nut_adv/range_adv)에는 맞지 않았다.
    # 실측: 같은 스트리트 2회차 393건 중 25건이 진짜 stale 이었고,
    # 상대 레인지가 2배로 늘거나 절반으로 준 상태에서 낡은 값을 썼다
    # (nut 0.67 → -0.02 처럼 부호가 뒤집히는 폭).
    # 레인지가 실제로 바뀌었을 때만 다시 갱신한다 — 같으면 재계산하지 않는다.
    # 길이만 보면 **크기가 같은데 내용이 바뀐 경우**를 놓친다(25→17 로만
    # 줄었다). 레인지는 콤보 집합이므로 내용 기반 서명을 쓴다.
    # **내 레인지는 서명에서 뺀다.** 그 스트리트 안에서 내 레인지는 변하지
    # 않는데 매번 새로 만들어져 서명만 흔들린다(실측 3건이 그 때문에
    # 변화로 오판됐다). 같은 스트리트에서 실제로 좁혀지는 것은 상대 레인지다.
    _rsig = 0 if not opp_range else hash(frozenset(map(str, opp_range)))
    _first = (street != st.get('street_made')
              and street not in (st.get('refreshed') or []))
    _opps_sig = _opp_ranges_signature(opp_ranges)
    _range_moved = (st.get('_rsig') is not None and st.get('_rsig') != _rsig)
    _pools_moved = (bool(_opps_sig) and st.get('_opps_sig') is not None
                    and st.get('_opps_sig') != _opps_sig)
    if _first or _range_moved or _pools_moved:
        st = refresh(st, hero, board, opp_range, profile, pot, stack, street,
                     n_opp, seed=seed, opp_est=opp_est, my_range=my_range,
                     opp_ranges=opp_ranges)
        if _first:
            st.setdefault('refreshed', []).append(street)
    st['_rsig'] = _rsig
    st['_opps_sig'] = _opps_sig

    st = river_fix(st, hero, board, profile, opp_range, rng)

    # F2/probe context must exist **before** attach_intent.
    # Session used to write this after update_plan returned, so the already-frozen
    # current-action intent could not react to the previous aggressor checking.
    if opp_checked_prev is not None:
        st['opp_checked_prev'] = bool(opp_checked_prev)

    st['plan'] = _allowed(profile, st['plan'], rng)

    # 이 라벨을 언제 채택했는가. 예산(BUDGET)을 세는 기준점이다.
    # 플랍에 bluff_2street 으로 치다가 턴에 value_2street 으로 승격한 사람은
    # 플랍의 벳을 새 계획의 예산에서 까면 안 된다 — 그건 다른 계획의 지출이었다.
    if not prev or prev.get('plan') != st.get('plan') or not st.get('plan_since'):
        st['plan_since'] = street

    # 의도는 무저항 시점에만, 한 번만 확정한다.
    if intent_of(st, street) is None:
        st = attach_intent(st, hero, board, my_range, opp_range, profile,
                           pot, stack, street, rng, n_opp, behind,
                           oop, initiative, opp_est,
                           oop_vs_aggr=oop_vs_aggr,
                           oop_legacy_abs=oop_legacy_abs)
    return st


def river_fix(state, hero, board, profile=None, opp_range=None, rng=None):
    """리버 도달 시 드로우 기반 계획은 무효. 메이드 여부로 재분류.

    **미스한 드로우가 전부 giveup 으로 가면 안 된다.** busted 드로우는
    리버 블러프의 대표 후보다 — 쇼다운 가치가 없어서 체크해도 못 이기고,
    그 드로우를 구성하던 카드가 상대의 완성 콤보를 지운다.
    예전에는 그 라인이 통째로 없어서 리버 블러프가 거의 나오지 않았다.
    """
    if len(board) < 5: return state
    st = dict(state)
    st['outs'] = 0
    # 리버 얇은 밸류. value_2street / pot_control 은 리버 사이즈가 0 이라
    # 리버에서 얇게 뽑는 경로가 아예 없었다.
    # thin_value_river 개념이 있어야 시도한다 — 얇은 밸류는 배워야 하는 라인이고,
    # 못 하는 사람은 체크하고 쇼다운을 본다.
    if st.get('plan') in ('value_2street', 'pot_control', 'block'):
        rel = st.get('rel', 0.5)
        made = bot.made_strength(hero, board)
        if profile and profile.get('concepts') and rng is not None and made >= 1:
            _tv = PS.sk(profile, 'thin_value_river')/10.0
            # 이길 여지가 있어야 얇은 밸류다. 너무 강하면 이미 3스트리트고,
            # 너무 약하면 블러프캐치 대상이다.
            _band = max(0.0, min(1.0, (rel - 0.48)/0.30)) * max(0.0, min(1.0, (0.92 - rel)/0.20))
            if rng.random() < 0.75*_tv*_band:
                st['plan'] = 'thin_river'
                st['why'] = (st.get('why') or []) + [
                    '리버: 얇은 밸류(rel %.2f, 개념 %.1f)' % (rel, _tv*10)]
        return st

    if st.get('plan') != 'semibluff':
        return st
    made = bot.made_strength(hero, board)
    rel = st.get('rel', 0.5)
    # 완성 판정. 계단(made>=2 or rel>=0.65)이 아니라 둘을 함께 본다.
    if made >= 2 or rel >= 0.62:
        st['plan'] = 'value_2street'
        st['why'] = (st.get('why') or []) + ['리버: 드로우 완성 → 밸류 전환']
        return st

    # 미스. 블러프로 갈지 포기할지 — 개념과 블로커가 정한다.
    p_bluff = 0.0
    if profile and profile.get('concepts'):
        _bl = PS.sk(profile, 'bluff')/10.0
        _br = PS.sk(profile, 'barrel_river')/10.0
        p_bluff = 0.10 + 0.55*_bl*_br
        if opp_range:
            # 콜할 콤보를 지웠으면 블러프가 통한다. 순 효과를 본다.
            _net = R.blocker_effect(hero, opp_range, board, 'river', 0.75, False)
            _bg = max(0.0, min(1.0, (PS.sk(profile, 'blocker') - 1.0)/7.0))
            p_bluff *= max(0.35, min(1.80, 1.0 + 4.0*_net*_bg))
        # 쇼다운 가치가 조금이라도 있으면 블러프로 쓰면 안 된다.
        if made >= 1 or rel >= 0.42:
            p_bluff *= 0.15
    if rng is not None and rng.random() < max(0.0, min(0.75, p_bluff)):
        st['plan'] = 'river_bluff'
        st['why'] = (st.get('why') or []) + [
            '리버: 드로우 미스 → 리버 블러프(%.0f%%)' % (p_bluff*100)]
    else:
        st['plan'] = 'giveup'
        st['why'] = (st.get('why') or []) + ['리버: 드로우 미스 → 포기']
    return st


def _prof_hint(st):
    return {'type': st.get('type')}

def record_deviation(state, street, executed_action, planned_action, reason=''):
    """계획과 다른 액션이 실행됐을 때 그 사실을 기록한다.

    예전에는 여기 enforce_consistency 가 있었고, 계획이 giveup 인데 벳이 나오면
    **계획을 벳에 맞춰 고쳐썼다**. 즉 모순이 생길 때마다 증거를 지웠다.
    그래서 '계획을 무시하는 실행 경로'가 오래 안 보였다.

    방향이 반대여야 한다. 실행이 계획을 따르고, 못 따랐으면 이탈로 남긴다.
    이탈은 discipline 이 낮아서 생기는 현상이며, 기록이 있어야
    불변식이 '계획에 없는 액션인데 이탈 로그가 없다'를 잡을 수 있다.
    """
    st = dict(state)
    st['deviations'] = list(st.get('deviations') or [])
    st['deviations'].append({'street': street, 'planned': planned_action,
                             'executed': executed_action, 'why': reason})
    st['why'] = (st.get('why') or []) + [
        '계획이탈: %s 계획인데 %s (%s)' % (planned_action, executed_action, reason)]
    return st


def _allowed(profile, plan, rng=None):
    """그 개인이 해당 계획을 실행할 개념을 갖고 있는가. 벡터면 연속 확률.

    rng 는 필수다. 예전에는 `(rng or random).random()` 으로 전역 RNG 에 폴백했는데,
    전역 RNG 는 OS 엔트로피로 시드되므로 폴백이 한 번이라도 타면
    같은 시드가 재현되지 않는다 (semibluff→showdown 강등이 매번 달라졌다).
    호출부가 rng 를 안 넘기면 조용히 깨지므로 예외를 던진다.
    """
    if profile.get('concepts'):
        need = {'bluff_2street': 'bluff', 'semibluff': 'semibluff', 'trap': 'checkraise',
                'block': 'blockbet', 'pot_control': 'potcontrol',
                'river_bluff': 'barrel_river', 'thin_river': 'thin_value_river'}
        if plan in need:
            s = PS.sk(profile, need[plan])
            _down = {'bluff_2street':'giveup','semibluff':'showdown',
                     'trap':'value_3street','block':'value_2street',
                     'pot_control':'showdown',
                     'river_bluff':'giveup','thin_river':'showdown'}
            if s < 1.5: return _down[plan]
            if s < 3.5:
                if rng is None:
                    raise ValueError('plan._allowed: rng 필수 (전역 RNG 사용 금지)')
                if rng.random() > (s-1.5)/2.0:
                    return _down[plan]
        return plan
    T = profile.get('type')
    if T not in A.ARCHETYPES: return plan
    c = A.concepts(T)
    need = {'bluff_2street': ('bluff', 1), 'semibluff': ('semibluff', 1),
            'trap': ('checkraise', 2), 'block': ('blockbet', 1),
            'pot_control': ('potcontrol', 1)}
    if plan in need:
        k, lv = need[plan]
        if c.get(k, 0) < lv:
            return {'bluff_2street': 'giveup', 'semibluff': 'showdown',
                    'trap': 'value_3street', 'block': 'value_2street',
                    'pot_control': 'showdown'}[plan]
    return plan


def refresh(state, hero, board, opp_range, profile, pot, stack, street, n_opp=1, seed=None,
            opp_est=None, my_range=None, opp_ranges=None):
    """계획은 유지하되 **보드 의존 지표를 현재 보드로 한 번에 갱신**하고,
       근거가 무너지면 계획을 강등한다.

    예전에는 rel/eq/outs/danger 만 갱신하고 nut_adv/range_adv 는 빠져 있었다.
    그 둘은 make_plan(플랍, 또는 board_changed 시 revise_plan)에서만 계산되어
    **플랍 값이 턴·리버까지 그대로 승계**됐다. 계측으로 확인한 실제 사례:

        flop  3cTs7d    nut_adv -0.08 range_adv -0.15  (계산 호출 1회)
        turn  3cTs7dTh  nut_adv -0.08 range_adv -0.15  (계산 호출 **0회**)

    보드도 상대 레인지도 바뀌었는데 함수가 아예 안 불렸다. 그리고 이 값들은
    로그가 아니라 **판단 입력**이다 — decide_size(483), overbet_frac(763),
    bluff_mode 의 양극화 조건(1763)이 소비한다. 즉 '칠까 말까'는 최신값
    (decide_aggression 이 자체 재계산)인데 '얼마나·어떻게'는 낡은 값이었다.

    새 보드 의존 지표를 추가할 때도 여기 한 곳에서 갱신한다.
    """
    st = dict(state)
    # goal/mode 는 계획의 이력이다. 없으면 현재 계획명을 목적으로 본다.
    st.setdefault('plan_goal', st.get('plan'))
    st.setdefault('plan_mode', None)
    # 플랍을 체크백했는가. 지연 씨벳(delayed_cbet)이 이걸 본다.
    # 의도 기록에서 읽는다 — 별도 상태를 만들면 두 곳이 어긋난다.
    if street == 'turn':
        _fx = ((state.get('executed_actions') or {}).get('flop') or [])
        if _fx:
            # delayed cbet means the player actually checked the flop through.
            # A planned check that later became call/raise is not a delayed-cbet line.
            st['flop_checked'] = all(a == 'check' for a in _fx)
        else:
            # Legacy/replay states without execution provenance fall back to intent.
            _fi = intent_of(state, 'flop') or {}
            st['flop_checked'] = (_fi.get('act') in (None, 'check'))
    outs_true = draw_strength(hero, board)
    # make_plan:277 과 같은 체감 보정을 건다. 여기만 날것이라 **같은 사람이
    # 플랍과 턴에서 자기 아웃츠를 다르게 셌다.** 아래 rel 은 이미 고쳐져
    # 있었는데 outs 만 그 수정에서 빠져 있었다.
    # refresh 에는 rng 가 없다 — seed 로 새로 만든다. 이 함수의 다른 난수는
    # _allowed 가 자기 random.Random(crc32(...)) 를 따로 만들어 쓰므로
    # 스트림이 겹치지 않는다.
    outs = (int(round(outs_true * PS.calc_noise(profile, 'outs',
                                                random.Random(seed))))
            if profile.get('concepts') else outs_true)
    made = bot.made_strength(hero, board)
    # make_plan 과 같은 편향을 쓴다. 예전에는 여기만 날것이라
    # **같은 사람이 플랍과 턴에서 자기 핸드를 다르게 평가했다.**
    rel_true = relative_strength(hero, board, opp_range)
    # perceived_rel 에는 **날것**을 넘긴다 (make_plan:312-314 와 같게).
    # 체감값을 넘기면 노이즈가 두 번 먹혀 새 불일치가 생긴다.
    rel = perceived_rel(profile, rel_true, hero, board, outs_true, made)
    eq  = _eq_vs(hero, board, opp_range, n_opp, sims=300, seed=seed,
                 opp_ranges=opp_ranges)
    # 레인지 우위도 같은 시점에 갱신한다. my_range 가 없으면(구 호출부)
    # 이전 값을 유지해 동작을 깨지 않는다.
    # `my_range if my_range is not None` 로 쓰면 **빈 리스트가 들어올 때
    # 폴백을 안 탄다**([] 는 None 이 아니다). 그러면 계획 상태에 레인지가
    # 남아 있는데도 재계산이 통째로 건너뛰어진다(실측: 새 시드 320핸드에서
    # stale 9건, 전부 이 경로). 값이 비었으면 상태의 것을 쓴다.
    _mr = my_range if my_range else st.get('my_range')
    if _mr and opp_range:
        st['nut_adv'] = round(R.nut_advantage(_mr, opp_range, board), 2)
        st['range_adv'] = round(
            R.range_advantage(_mr, opp_range, board, seed=seed), 2)
    # 갱신 **전** 값을 잡아둔다. st.update 뒤에는 이전 강도를 알 수 없다.
    _prev_made = st.get('made') or 0
    _prev_rel = st.get('rel') or 0.0
    st.update({'rel': round(rel,2), 'eq': round(eq,3), 'outs': outs,
               'made': made, 'danger': round(bot.board_danger(board),2)})
    # eq 를 갱신했으면 기록용 짝도 같이 갱신한다. 안 그러면 eq 는 새 값,
    # eq_current 는 make_plan 시점 값이 되어 eq_delta 가 의미를 잃는다.
    _eqc = _eq_current(hero, board, opp_range, n_opp, sims=300, seed=seed,
                       opp_ranges=opp_ranges)
    st.update({'eq_current': (None if _eqc is None else round(_eqc, 3)),
               'eq_delta': (None if _eqc is None else round(eq - _eqc, 3)),
               'eq_sims': 300, 'eq_seed': seed,
               'outs_true': outs_true,
               'opp_range_n': len(opp_range) if opp_range else 0,
               'opp_range_sig': _range_sig(opp_range),
               'opp_ranges_n': ({str(k): len(v) for k, v in opp_ranges.items()}
                                if isinstance(opp_ranges, dict) else None),
               'opp_ranges_sig': ({str(k): _range_sig(v) for k, v in opp_ranges.items()}
                                  if isinstance(opp_ranges, dict) else None),
               'my_range_n': len(_mr) if _mr else 0,
               'my_range_sig': _range_sig(_mr)})
    why = list(st.get('why') or [])
    old = st.get('plan')

    # 강등 임계값은 상대에 따라 움직인다.
    # 잘 접는 상대라면 내 강도가 떨어져도 계속 밀어붙일 근거가 되고,
    # 안 접는 상대(스테이션)라면 더 일찍 포기해야 한다.
    # 자기 전략만 치는 선수(exploit_weight=0)는 이 조정을 하지 않는다.
    oe = opp_est if opp_est is not None else st.get('opp_est')
    give_thr, ctrl_thr = 0.12, 0.30
    if oe:
        # read_opponent 경유. oe['ftb'] 날것은 see_freq 게이트를 우회하고
        # 스트리트 구분도 못 한다 — '플랍은 잘 치는데 턴에서 접는' 사람이
        # 여기서는 전체 평균으로만 보였다.
        _rdr = PS.read_opponent(profile, oe)
        w = _rdr.get('w', 0.0)
        if w > 0.0:
            d = PS.street_gap(_rdr, street)       # 그 스트리트의 폴드 성향
            give_thr = PS.blend(give_thr, max(0.02, give_thr - 0.35*d), w)
            ctrl_thr = PS.blend(ctrl_thr, max(0.10, ctrl_thr - 0.55*d), w)
            if abs(d) > 0.04:
                why.append('%s: 상대 폴드성향 %+.0f%%p → 포기 문턱 %.2f'
                           % (street, 100*d, ctrl_thr))

    # 턴/리버 카드가 누구를 도왔는가. 상대를 도운 카드면 근거가 더 빨리 무너지고,
    # 나를 도운 카드면 더 버틴다. turn_card_effect 가 이걸 재는데
    # decide_aggression 에서만 쓰이고 계획 재평가에는 안 들어갔다.
    if len(board) >= 4 and profile.get('concepts'):
        _tce = TX.turn_card_effect(board[:3], board[-1],
                                   aggressor_range_high=bool(st.get('plan') in
                                       ('value_3street', 'value_2street', 'trap')))
        _bt = min(1.0, PS.sk(profile, 'board_texture')/7.0)
        _shift = 0.45 * _tce * _bt          # +면 내 레인지에 유리
        give_thr = max(0.02, give_thr * (1.0 - _shift))
        ctrl_thr = max(0.08, ctrl_thr * (1.0 - _shift))

    # 근거 붕괴 판정
    if old in ('value_3street','value_2street') and rel < ctrl_thr and made <= 1:
        st['plan'] = 'giveup' if rel < give_thr else 'pot_control'
        why.append('%s: 상대강도 %.2f로 하락 → %s' % (street, rel, st['plan']))
    elif old == 'value_3street' and rel < 0.62:
        # 중간 강등. 예전에는 3스트리트가 pot_control/giveup 으로만 떨어져서,
        # A 가 떨어져 rel 0.94 -> 0.47 이 되어도 계획이 그대로였다.
        # 3배럴은 못 하지만 2스트리트는 가능한 구간이 통째로 없었다.
        st['plan'] = 'value_2street'
        why.append('%s: 상대강도 %.2f → 3스트리트 철회, 2스트리트' % (street, rel))
    elif old == 'semibluff' and outs < 6 and street != 'river':
        # 드로우가 사라진 경우는 둘이다 — **완성됐거나 죽었거나.**
        # 둘 다 outs 가 줄어서 같은 분기를 타는데, 예전에는 rel 만 봐서
        # 플러시를 맞췄어도 rel 0.6 미만이면 giveup 으로 내려갔다.
        # river_fix 는 (made >= 2 or rel >= 0.62)로 둘을 함께 보는데
        # 턴만 rel 단독이라 같은 판정이 스트리트마다 달랐다.
        if made >= 2 or rel >= 0.62:
            st['plan'] = 'value_2street'
            why.append('%s: 드로우 완성(made %d) → 밸류 전환' % (street, made))
        else:
            st['plan'] = 'giveup'
            why.append('%s: 드로우 소멸(%d아웃) → 포기' % (street, outs))
        # 리버는 river_fix 가 맡는다. 여기서 먼저 giveup 으로 내리면
        # **미스한 드로우의 블러프 전환 경로가 통째로 막힌다** —
        # 리버는 outs 가 항상 0 이라 이 조건이 무조건 걸렸다.
    elif old == 'trap' and st.get('_no_bite', 0) >= 1:
        # 함정을 팠는데 아무도 물지 않았다 → 직접 밸류로 전환.
        # **목적(goal)은 바뀌지 않는다.** 처음부터 밸류 추출이었고, 숨기는
        # 방식이 안 통해서 직접 치는 방식으로 바꾼 것이다. 모드만 종료한다.
        st['plan'] = 'value_3street' if rel >= 0.85 else 'value_2street'
        st['plan_goal'] = st.get('plan_goal') or st['plan']
        st['plan_mode'] = None
        why.append('%s: 상대가 벳하지 않음 → 함정 해제, 직접 밸류' % street)
    elif old == 'giveup' and (rel >= 0.55 or made >= 2):
        # **포기에서 나오는 길이 없었다.** 승격 분기가 pot_control/block/showdown
        # 만 다뤄서, rel 이 0.35 -> 0.73 으로 올라도 giveup 에 갇혀
        # p_bet 0.00 으로 체크했다. 보드가 바뀌어 강도가 올라간 것은
        # 계획을 다시 세울 근거다.
        st['plan'] = 'value_2street' if (rel >= 0.72 or made >= 3) else 'showdown'
        why.append('%s: 포기했으나 강도 상승(rel %.2f, made %d) → %s'
                   % (street, rel, made, st['plan']))
    elif old in ('pot_control', 'block', 'showdown') and (
            rel >= 0.70 or made >= max(2, st.get('made', 0) + 1)):
        # 승격 조건. 예전에는 rel >= 0.88 하나뿐이라
        # 리버에 트립스가 되어 rel 0.05 → 0.76, made 1 → 3 이 됐는데도
        # 계획이 턴의 pot_control 그대로 남아 체크했다.
        # rel 만이 아니라 '내 완성 강도가 올라갔는가'도 승격 근거다.
        #
        # **주의 — 이 made 항은 실제로는 죽어 있다.** st.update 가 위에서
        # st['made'] 를 새 값으로 덮어쓴 뒤라 `made >= max(2, st['made']+1)`
        # 이 `made >= made+1` 이 되어 모든 값에서 거짓이다. 실질 조건은
        # rel >= 0.70 단독이다.
        #
        # _prev_made 로 고쳐봤으나 **되돌렸다.** made 1→2 가 내가 핸드를
        # 개선한 경우와 **보드가 페어링된 경우**를 구분하지 못한다. 실측
        # 신규 승격 11건이 대부분 페어 보드였고, rel 0.00 / eq 0.031 인
        # 핸드까지 밸류 계획으로 승격됐다.
        # 즉 단순 stale-variable 버그가 아니라 **made 를 승격 신호로 쓰는
        # 설계 자체의 한계**다. eq/rel 하한을 새로 박는 방식은 결과에 맞춘
        # 보정이 되므로 쓰지 않는다. hand-strength transition 을 제대로
        # 정의하는 별도 설계가 필요하다(known issue E).
        st['plan'] = 'value_3street' if rel >= 0.88 else 'value_2street'
        why.append('%s: 강도 상승(rel %.2f, made %d) → 밸류 전환' % (street, rel, made))
    elif old == 'bluff_2street' and rel >= 0.75:
        st['plan'] = 'value_2street'
        why.append('%s: 블러프였으나 강도 상승 → 밸류 전환' % street)
    elif (old == 'value_2street'
          and made > _prev_made
          and rel >= max(0.85, _prev_rel)
          and budget_left(st, 'value_2street', street) is not None
          and budget_left(st, 'value_2street', street) <= 0):
        # **예산이 다 떨어졌는데 강도가 더 올라간 경우.**
        # value_2street 은 '두 스트리트에 걸쳐 밸류를 뽑는다'는 계획이라
        # 플랍·턴을 치면 리버에 못 친다. 그런데 리버에 완성 강도가 올라가면
        # (예: 투페어 → 풀하우스) 그 계획의 전제 자체가 바뀐다.
        # 예전에는 value_2street 에서 올라가는 경로가 없어, 리버에 풀하우스를
        # 완성하고도(rel 1.00, made 7) 예산 0 때문에 체크했다.
        #
        # rel 숫자 하나로 승격시키지 않는다. **완성 강도가 실제로 올라갔고
        # (made 증가), 상대 레인지 대비도 여전히 최상위이며, 예산이 소진돼
        # 계획이 더는 유효하지 않을 때**만 올린다. 예산이 남아 있으면 원래
        # 계획대로 치면 되므로 승격할 이유가 없다.
        st['plan'] = 'value_3street'
        st['plan_goal'] = 'value_3street'
        why.append('%s: 예산 소진 후 강도 상승(rel %.2f, made %d→%d) → 3스트리트 승격'
                   % (street, rel, _prev_made, made))
    # 개념 보유/허용 판정은 update_plan 파이프라인 끝에서 **한 번만** 한다.
    # 여기서도 _allowed 를 굴리면 낮은 숙련도의 stochastic gate가
    # refresh 1회 + update_plan 1회로 곱해진다.
    # why 는 스트리트를 넘어 누적된다. 그대로 두면 턴 로그에 플랍 사유가
    # 섞여 리뷰 때 오독을 유발한다(실측 15건). 누적본은 이력으로 남기되,
    # **현재 스트리트의 사유만 따로** 보관한다. 설명 내용 자체는 바꾸지 않는다.
    st['why'] = why[-4:]
    _wbs = dict(st.get('why_by_street') or {})
    # 폴백으로 why[-2:] 를 쓰면 그 스트리트에 새 사유가 없을 때 **이전
    # 스트리트 사유를 그대로 가져온다**(실측 9건). 없으면 비어 있는 것이
    # 정확한 기록이다 — 계획이 유지됐다는 뜻이므로.
    _wbs[street] = [w for w in why if w.startswith(street + ':')]
    st['why_by_street'] = _wbs
    # 의도는 파이프라인 끝(session)에서 한 번만 붙인다. 여기서 붙이면 낡는다.
    return st


def mark_no_bite(state):
    """트랩 계획인데 그 스트리트에서 아무 벳도 안 나온 경우 기록."""
    st = dict(state)
    st['_no_bite'] = st.get('_no_bite', 0) + 1
    return st


def checkraise_size(profile, pot, tocall, stack, board, street, rng):
    """체크레이즈 사이즈. 팟이 아니라 '맞은 벳' 기준."""
    a = profile.get('aggr', 5)
    ob = PS.sk(profile, 'overbet') if profile.get('concepts') else 4.0
    mult = 2.7 + 0.09*a + 0.06*ob                  # 대략 3.0~4.3배
    dang = bot.board_danger(board)
    mult *= (1 + 0.18*dang)                        # 젖은 보드는 크게
    if street == 'river': mult *= 0.92
    mult *= (1 + rng.uniform(-0.12, 0.12))
    target = tocall * max(2.2, min(5.0, mult))
    # 팟 대비 상한 — 공격성이 높을수록 상한도 높다
    cap_mult = 1.15 + 0.075*a + 0.03*ob
    target = min(target, (pot + tocall) * cap_mult)
    return int(min(stack, max(tocall*2.2, round(target/100)*100)))


def target_commit(profile, rel, made, s, street, opp_stack_bb=None,
                  opp_eff=None):
    """이 핸드로 **스택의 몇 %까지 넣을 작정인가**. 0~1.

    value_Nstreet 의 뜻을 '몇 번 친다'에서 '목표까지 팟을 키운다'로 바꾸는
    축이다. 횟수로 정의하면 상대가 대신 키워줬을 때 계획이 무너진다 —
    상대 벳은 내 목표를 대신 채워준 것이므로 콜이 계획의 일부여야 하고,
    모자라면 레이즈로 채우는 것이 같은 계획의 다른 수단이다.

    **이건 공부한 사람의 개념이다.** 역산을 못 하는 사람은 목표라는 것이
    없고 습관 사이즈로 친다. 그래서 aware(sk('spr'))로 두 판단을 섞는다.
    aware 가 0 이면 강도와 무관한 습관값으로 수렴한다.
    """
    # 레귤러의 목표: 강도가 높을수록 전액에 가깝다.
    # rel 0.5 부근에서 급히 오르지 않게 완만한 곡선으로 둔다 —
    # 계단이면 rel 0.69 와 0.71 이 완전히 다른 사람이 된다.
    tgt = max(0.12, min(1.0, 0.10 + 1.15*max(0.0, rel - 0.30)))
    if made >= 5:                      # 셋 이상 — 전액을 목표로
        tgt = max(tgt, 0.92)
    # 상대가 못 따라올 목표는 의미가 없다. 내가 40bb 를 넣을 작정이어도
    # 상대에게 15bb 밖에 없으면 실제로 들어가는 건 15bb 다. 그 이상을
    # 목표로 잡으면 사이즈만 부풀고 폴드만 유도한다.
    if opp_eff and opp_eff > 0:
        tgt = min(tgt, max(0.05, float(opp_eff)))
    aware = 1.0
    if profile.get('concepts'):
        aware = max(0.0, min(1.0, (PS.sk(profile, 'spr') - 2.0) / 6.0))
    habit = 0.55                       # 목표 개념이 없는 사람의 습관적 지출
    return max(0.05, min(1.0, tgt*aware + habit*(1.0 - aware)))


def breakeven_fold(size_frac):
    """이 사이즈로 블러프할 때 **상대가 몇 % 접어야 본전인가.**

    팟 대비 f 를 걸면 f/(1+f). 팟의 절반이면 33%, 팟만큼이면 50%.
    사이즈가 커질수록 요구 폴드율이 가파르게 오른다.
    """
    f = max(0.01, float(size_frac))
    return f / (1.0 + f)


def barrel_size(fold_est, profile, floor=0.15, cap=1.10):
    """상대 폴드 성향에서 **역산한** 블러프 사이즈.

    필요 폴드율이 상대의 실제 폴드 확률보다 낮아야 이익이다.
    그래서 목표 필요폴드율을 상대 폴드율에서 마진만큼 뺀 값으로 두고,
    거기서 사이즈를 되돌린다 — f = r/(1-r).

    예전에는 barrel 이 고정 배수(1.15/0.85)로 근사했다. 상대가 30% 접는지
    70% 접는지가 사이즈에 제대로 반영되지 않았다.
    """
    r = max(0.05, min(0.75, float(fold_est)))
    margin = 0.08
    if profile and profile.get('concepts'):
        # 폴드에퀴티 개념이 낮으면 마진을 크게 잡지 못하고 대충 친다.
        margin = 0.03 + 0.010*PS.sk(profile, 'fold_equity')
    r_t = max(0.05, r - margin)
    return max(floor, min(cap, r_t / max(0.05, 1.0 - r_t)))


def bluff_mode(profile, rel, danger, nut_adv, opp_est, street, s, rng):
    """블러프라는 **큰 전략** 아래 어떤 세부 전략으로 갈 것인가.

    밸류는 목표가 하나('팟을 키운다')지만 블러프는 목표끼리 충돌한다.
      중간에 접을 생각이면 최소한만 걸어야 손실이 작다.
      그런데 작게 걸면 상대가 안 접어서 애초의 목적을 못 이룬다.
      레귤러 상대로는 밸류벳과 똑같이 보여야 하는데, 밸류 사이즈는 크다.

    그래서 세부 전략을 나눈다. 반환 (모드, 사이즈배수, 사유).

      merged     위장형 — 같은 상황의 내 밸류 사이즈와 일치시킨다.
                 상대가 사이즈를 읽을 때만 의미가 있다.
      polarized  양극화 — 오버벳으로 '넛 아니면 블러프'만 남긴다.
                 내 레인지에 넛이 있어야(nut_adv) 성립한다.
      barrel     지속형 — 폴드율 위주. 상대가 사이즈를 안 읽을 때.
      probe      저비용 — 중간에 접을 생각. 반응만 보고 손실을 줄인다.

    **이건 레귤러의 개념이다.** 상대의 읽기 능력을 고려해 사이즈를 바꾸는 것
    자체가 공부의 산물이다. 못 하는 사람은 늘 같은 크기로 친다.
    """
    aware = 1.0
    if profile.get('concepts'):
        aware = max(0.0, min(1.0,
                             (0.5*PS.sk(profile, 'sizing_tell')
                              + 0.5*PS.sk(profile, 'fold_equity') - 2.0) / 6.0))
    if aware < 0.15:
        return 'habit', 1.0, '사이즈로 속인다는 개념 없음 — 습관 사이즈'

    # 상대가 사이즈에서 정보를 읽는가. 읽는 상대에게만 위장이 값을 한다.
    reads = 0.5
    folds = 0.5
    if isinstance(opp_est, dict):
        if opp_est.get('sizing_tell') is not None:
            reads = float(opp_est['sizing_tell'])/10.0
        if opp_est.get('fold') is not None:
            folds = float(opp_est['fold'])

    # 끝까지 갈 생각인가. 딥할수록·젖을수록 도중 포기 가능성이 크다.
    risk = max(0.0, min(1.0, 0.25 + 0.45*max(0.0, min(1.0, danger/0.65))
                        + 0.05*max(0.0, s - 4.0)))
    if risk > 0.62 and rng.random() < 0.55*aware:
        return 'probe', 0.55, '도중 포기 위험 %.0f%% — 최소 비용 탐색' % (risk*100)
    if reads >= 0.55 and nut_adv >= 0.55 and rng.random() < 0.45*aware:
        return 'polarized', 1.45, '상대가 사이즈를 읽음 + 넛 우위 — 양극화'
    if reads >= 0.55:
        return 'merged', 1.0, '상대가 사이즈를 읽음 — 밸류와 같은 사이즈로 위장'
    # barrel 은 폴드율에서 사이즈를 **역산한다**. 고정 배수는 상대가 30%
    # 접는지 70% 접는지를 사이즈에 제대로 싣지 못했다.
    _bs = barrel_size(folds, profile)
    return 'barrel', _bs, \
        '상대가 사이즈를 안 읽음 — 폴드율 %.0f%% 역산(팟의 %.0f%%, 요구 %.0f%%)' \
        % (folds*100, _bs*100, breakeven_fold(_bs)*100)


def spread_curve(profile, danger, opp_est=None):
    """목표를 세 스트리트에 **어떻게 나눠 실을 것인가**. (플랍, 턴, 리버) 가중치.

    같은 목표라도 배분이 다르다.
      앞에 싣기  — 젖은 보드. 드로우에 값을 물리고 폴드에쿼티도 크다.
      뒤로 미루기 — 마른 보드 + 잘 안 접는 상대. 약한 패로 따라오게 두었다가
                   마지막에 뽑는다.
    예전에는 기하급수 균등 배분 하나뿐이라 보드도 상대도 성향도 반영되지 않았다.

    **이것도 레귤러의 개념이다.** 배분을 계획하려면 남은 스트리트를 내다봐야
    하는데, 그게 안 되는 사람은 매 스트리트 같은 비율로 친다.
    """
    front = 0.0
    front += 0.55*max(0.0, min(1.0, danger/0.65))       # 젖을수록 앞에
    if opp_est:
        # 잘 접는 상대면 앞에서 끝내는 게 이득, 안 접으면 뒤로 미뤄 뽑는다.
        _f = opp_est.get('fold') if isinstance(opp_est, dict) else None
        if _f is not None:
            front += 0.35*(float(_f) - 0.5)
    a = profile.get('aggr', 5)
    if profile.get('temper'):
        a = PS.temper(profile, 'aggression', 5.0)
        front -= 0.030*(PS.temper(profile, 'slowplay_taste', 5.0) - 5.0)
    front += 0.025*(a - 5.0)
    front = max(-0.45, min(0.55, front))
    w = [1.0 + front, 1.0, 1.0 - 0.55*front]
    aware = 1.0
    if profile.get('concepts'):
        aware = max(0.0, min(1.0, (PS.sk(profile, 'spr') - 2.0) / 6.0))
    w = [1.0 + (x - 1.0)*aware for x in w]              # 못 보는 사람은 균등
    tot = sum(w)
    return [x*3.0/tot for x in w]                       # 평균 1.0 로 정규화


def stackoff_plan(hero, board, profile, pot, stack, street, rng,
                  commit=1.0, danger=0.0, opp_est=None):
    """목표까지 팟을 키우는 스트리트별 사이즈 배분.

    commit 은 '스택의 몇 %까지 넣을 작정인가'(target_commit). 1.0 이면
    예전과 같은 전액 스택오프다. 예전에는 목표가 항상 전액으로 고정이라
    **강도가 중간인 핸드의 '여기까지만 키운다'를 표현할 수 없었다.**
    """
    s = spr(stack, pot)
    so = PS.sk(profile, 'stackoff') if profile.get('concepts') else 4.0
    eff = max(1.0, stack*max(0.05, min(1.0, commit)))   # 실제로 넣을 칩
    s_eff = spr(eff, pot)
    if s_eff < 1.2:
        return {'ok': True, 'why': 'SPR %.1f — 이미 커밋, 계획 불필요' % s,
                'commit': round(commit, 2),
                'flop': 0.75, 'turn': 1.0, 'river': 1.0}
    if s_eff <= 5.5:
        # 3스트리트로 목표치를 정확히 다 넣는 기하급수 사이즈
        r = (2*eff/pot + 1) ** (1/3)
        frac = (r - 1) / 2
        w = spread_curve(profile, danger, opp_est)
        return {'ok': True, 'why': 'SPR %.1f · 목표 %.0f%% — 3스트리트 배분(%.2f/%.2f/%.2f)'
                                   % (s, commit*100, w[0], w[1], w[2]),
                'commit': round(commit, 2), 'spread': [round(x,2) for x in w],
                'flop': round(frac*w[0], 2), 'turn': round(frac*w[1], 2),
                'river': round(frac*w[2], 2)}
    if s_eff <= 10 and so >= 6.5:
        # 오버벳 성향이 강한 사람만 시도
        r = (2*eff/pot + 1) ** (1/3)
        frac = min(1.6, (r - 1) / 2)
        return {'ok': True, 'why': 'SPR %.1f · 목표 %.0f%% — 오버벳 배분(소수 유형)'
                                   % (s, commit*100),
                'commit': round(commit, 2),
                'flop': round(frac, 2), 'turn': round(frac, 2), 'river': round(frac, 2)}
    return {'ok': False, 'why': 'SPR %.1f — 딥스택이라 3스트리트로 못 넣음' % s,
            'commit': round(commit, 2),
            'flop': 0.6, 'turn': 0.65, 'river': 0.7}
