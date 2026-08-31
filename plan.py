import random, zlib as _zlib
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
    # 상대가 리버에 벳/콜할 만한 상위 절반만 고려 (에어는 어차피 나를 못 이김)
    ranked = sorted(cand, key=lambda c: bot.eval7(list(c)+board), reverse=True)
    top = ranked[:max(1, len(ranked)//2)]
    better = sum(1 for c in top if bot.eval7(list(c)+board) > mine)
    out = 1.0 - better/len(top)
    _RS_CACHE[ck]=out
    return out

# draw_strength 는 bot.draw_strength 하나뿐이다 (ranges 도 같이 쓴다).
draw_strength = bot.draw_strength


def _eq_vs(hero, board, opp_range, n_opp, sims=400, seed=None):
    """추정 레인지 기준 에쿼티. 레인지가 없거나 너무 얇으면 비율 근사로 물러난다.

    opp_range 는 상대 '한 명분' 추정이므로 인원수만큼 복제해 쓴다.
    """
    if opp_range and len(opp_range) >= 20:
        # seed 를 넘기지 않는다 → 레인지 내용에서 유도된 고정 seed 를 쓴다.
        # 같은 스팟·같은 레인지면 항상 같은 추정치가 나와야 재현성이 유지된다.
        return bot.equity_vs_combos(hero, board, [opp_range]*max(1, n_opp), sims=sims)
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
    obs = 0.65*obs + 0.35*(opp_est.get('aggr', 5.0)/10.0)
    return max(0.05, min(0.92, PS.blend(base, obs, w)))


def trap_judgment(profile, opp_est, spr_now, danger, multiway, street, tilt, sk):
    """트랩을 팔지 판단. 반환 (확률, 사유).

    확률로 남기는 이유는 '가끔 무작위로 트랩한다'가 아니라
    실행 편차(집중력·일관성) 때문이다. 판단 자체는 아래 조건들이 만든다.
    """
    tool = 0.13*sk('trap') + 0.06*sk('checkraise')     # 도구 보유 정도
    if tool <= 0.05:
        return 0.0, ''
    conf = (opp_est or {}).get('confidence', 0.0)
    n    = (opp_est or {}).get('n', 0)
    w    = PS.exploit_weight(profile, conf, n)
    pbet = opp_bet_prob(opp_est, w, street)

    # 상대가 벳해줘야 트랩이 성립한다. 안 치는 상대면 무료 카드만 주는 셈.
    p = tool * (0.35 + 1.30*pbet)
    p *= (1.35 - 0.055*profile.get('aggr', 5))         # 공격적일수록 그냥 친다
    if spr_now >= 4:   p *= 1.25                       # 딥해야 나중에 받아낼 게 있다
    elif spr_now < 2:  p *= 0.35                       # 저SPR이면 함정 의미 없음
    if multiway:       p *= 0.45                       # 다인원 체크는 위험
    if danger > 0.45:  p *= 0.50                       # 젖은 보드에 무료 카드 금지
    p *= (1.0 - 0.55*max(0.0, min(1.0, tilt)))         # 틸트나면 인내가 안 된다
    p = max(0.0, min(0.70, p))
    why = '넛급 + 상대 벳확률 %.0f%% → 함정(%.0f%%)' % (pbet*100, p*100)
    if w > 0.05:
        why += ' [리딩 %.0f%%]' % (w*100)
    return p, why


def make_plan(hero, board, my_range, opp_range, profile, pot, stack, street,
              seed=None, n_opp=1, to_act_behind=0, oop=False, initiative=True,
              opp_est=None, opp_stack_bb=None, tilt=0.0):
    """opp_est — reads.perceived_profile() 결과. 진짜 프로필을 넘기면 정보 누출이다.
       opp_stack_bb — 주 상대의 유효 스택(bb). 트랩·오버벳은 스택 없이는 무의미하다.
       tilt — 내 틸트 강도 0~1. 틸트 나면 인내가 필요한 계획(트랩)이 줄고 공격이 는다."""
    """플랍에서 라인을 확정. 상대 수와 뒤에 남은 액션자를 반영."""
    rng = random.Random(seed)
    # 추정한 opp_range 를 그대로 쓴다. 고정 35% 가정으로 되돌리지 말 것 —
    # 좁혀놓은 레인지를 버리고 EV 를 판단하면 리딩이 전부 무의미해진다.
    eq = _eq_vs(hero, board, opp_range, n_opp, sims=400, seed=seed)
    dang = bot.board_danger(board)
    if profile.get('concepts'):
        dang *= min(1.0, PS.sk(profile,'board_texture')/6.0)   # 텍스처를 못 읽으면 위험을 모름
    outs_true = draw_strength(hero, board)
    outs = outs_true * PS.calc_noise(profile, 'outs', rng) if profile.get('concepts') else outs_true
    outs = int(round(outs))
    # 블로커는 개념이 없으면 아예 못 본다
    blk_true = R.blocker_score(hero, opp_range, board)
    blk = blk_true * min(1.0, PS.sk(profile, 'blocker')/6.0) if profile.get('concepts') else blk_true
    nut = R.nut_advantage(my_range, opp_range, board) if my_range else 0.0
    s_true = spr(stack, pot)
    s = s_true * PS.calc_noise(profile, 'spr', rng) if profile.get('concepts') else s_true
    if profile.get('concepts') and PS.sk(profile,'spr') < 2.5:
        s = 5.0                                   # SPR 개념이 없으면 아예 고려 안 함
    pc = max(0.0, min(1.0, (profile['icm'] + (10-profile['gamble']) + (10-profile['aggr']))/30.0))

    # 절대 강도 + 상대 레인지 대비 강도
    # 내 카드가 실제로 기여한 강도만 센다 (보드만으로 성립하는 건 내 것이 아니다)
    made = bot.made_strength(hero, board) if board else 0
    rel = relative_strength(hero, board, opp_range) if board else 0.5
    monster = made >= 5                     # 플러시 이상은 다인원 보정 면제
    strong  = made >= 3                     # 트립스 이상

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
    bluff_ok = (profile['bluff']/12.0) * (0.5 + 1.8*blk) * (0.75 + 0.35*max(0, nut)) \
               * (0.35 ** mw) * (0.55 ** min(to_act_behind, 3))
    if rd['w'] > 0:
        # 잘 접는 상대에게 블러프를 늘린다. 그 스트리트 기준으로.
        bluff_ok *= max(0.25, 1.0 + rd['w'] * 1.6 * PS.street_gap(rd, street))
    # 트랩 빈도 = 성향 함수. 저SPR·젖은 보드에서 줄되 0이 되지는 않는다.
    trap_p = (0.10 + 0.045*profile.get('bluff', 5)) * (1 - 0.55*dang)
    if rd['w'] > 0:
        # 함정은 상대가 쳐줘야 성립한다. 수동적인 상대에게는 무료 카드만 준다.
        trap_p *= max(0.15, 1.0 - rd['w'] * 1.2 * max(0.0, rd['passive']))
    if s < 3.0: trap_p *= 0.45          # 커밋 구간이면 줄지만 남는다
    if n_opp > 1: trap_p *= 0.5
    if profile['value'] == 'xr': trap_p *= 1.8
    trap_ok = rng.random() < max(0.02, min(0.45, trap_p))

    # 상대 레인지에 지는 콤보가 많으면 밸류 계획 자체를 강등한다.
    # eq(랜덤/광역 레인지 대비)가 높아도 rel이 낮으면 얇은 밸류다.
    if rel < 0.45:   v3 += 0.30; v2 += 0.22          # 사실상 밸류 계획 봉쇄
    elif rel < 0.65: v3 += 0.14; v2 += 0.10
    elif rel >= 0.92: v3 -= 0.10; v2 -= 0.08         # 넛급은 밸류 문턱 완화

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
        else:
            plan = 'value_3street'; why.append('강도 최상위 → 3스트리트 밸류')
    elif eq >= v2:
        if (dang > 0.35 or s < 2 or mw):
            plan = 'value_2street'
            why.append('밸류(eq %.2f, rel %.2f)지만 보드위험/다인원 → 2스트리트' % (eq, rel))
        else:
            plan = 'value_3street'; why.append('밸류 → 3스트리트')
    elif eq >= pcz:
        # 블락벳: OOP + 이니셔티브 없음 + 쇼다운은 되는 중간 강도
        block_p = 0.0
        if oop and not initiative and 0.25 <= rel <= 0.80:
            block_p = 0.12 + 0.05*profile['aggr'] - 0.03*profile.get('bluff', 5)
            block_p *= (1 + 0.4*dang)          # 젖은 보드일수록 가격 통제 욕구↑
            if A.ARCHETYPES.get(profile.get('type'),(0,)*6+('reg',''))[6] == 'fish': block_p *= 0.25
            block_p = max(0.0, min(0.42, block_p))
        if sk('blockbet') >= 1 and rng.random() < block_p:
            plan = 'block'; why.append('OOP 중간강도 → 블락벳으로 가격 통제')
        elif sk('potcontrol') >= 1 and rng.random() < min(0.75, pc*0.8 + 0.12 + 0.18*mw):
            plan = 'pot_control'; why.append('중간강도(eq %.2f, rel %.2f) → 팟 컨트롤' % (eq, rel))
        elif rel >= 0.45 and made >= 1:
            plan = 'value_2street'
            why.append('중간강도(eq %.2f, rel %.2f) → 얇은 밸류' % (eq, rel))
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
    elif (eq < 0.42 and sk('bluff') >= 1
          and rng.random() < bluff_ok * (1 + 0.9*min(1.0, outs/8.0) + 0.6*(eq>=0.30))
                            * (0.45 + 0.28*sk('bluff'))):
        plan = 'bluff_2street'
        why.append('쇼다운 가치 없음 + 블로커 %.2f/넛우위 %.2f → 블러프 계획' % (blk, nut))
    else:
        # giveup은 '쇼다운 가치 없음'일 때만. 메이드 핸드는 팟컨트롤로 간다.
        has_sd = made >= 1 or eq >= 0.42 + 0.05*mw
        if has_sd and sk('potcontrol') >= 1 and rng.random() < 0.72:
            plan = 'pot_control'; why.append('쇼다운 가치 있음 → 팟 컨트롤')
        elif has_sd:
            plan = 'showdown'; why.append('쇼다운 가치 있음 → 체크다운')
        elif has_sd:
            plan = 'showdown'; why.append('쇼다운 가치만 있음(팟컨트롤 개념 없음) → 체크다운 지향')
        else:
            plan = 'giveup'; why.append('쇼다운 가치 없고 블러프 개념/조건 미달 → 포기')
    st = {'plan': plan, 'street_made': street, 'streets': [street],
            'eq': round(eq,3), 'danger': round(dang,2), 'outs': outs,
            'blocker': round(blk,2), 'nut_adv': round(nut,2), 'spr': round(s,1), 'pc': round(pc,2),
            'n_opp': n_opp, 'behind': to_act_behind, 'rel': round(rel,2), 'made': made,
            'why': why, 'type': T,
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
                  street, rng, n_opp, to_act_behind, oop, initiative, opp_est=None):
    """계획에 이 스트리트의 의도를 붙인다. 판단 층의 마지막 단계."""
    plan = st.get('plan')
    rel = st.get('rel', 0.5)
    p_aggr, why_a = decide_aggression(profile, board, street, plan, rel, n_opp,
                                      oop, initiative, to_act_behind, rng,
                                      opp_est, st.get('outs', 0))
    if rng.random() < p_aggr:
        size = decide_size(profile, hero, board, street, plan, rel,
                           opp_range, my_range, pot, stack, rng, opp_est,
                           st.get('nut_adv', 0.0),
                           deviating=why_a.startswith('DEVIATE:'))
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

def decide_response(profile, hero, board, street, plan, plan_state, eq, need,
                    made_now, opp_range, pot, tocall, stack, committed, rng):
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
        if rng.random() < p:
            return 'raise', 1.0, need, '넛급 레이즈(%.0f%%)' % (p*100)
        return 'call', 0.0, need, '넛급이나 콜 선택'

    # --- 밸류 계획: 레이즈할 것인가 ---
    if plan in ('value_3street', 'trap') and eq > need + 0.15:
        rr = PS.sk(profile, 'reraise')/10.0 if has_c else 0.5
        so = PS.sk(profile, 'stackoff')/10.0 if has_c else 0.5
        p = 0.20 + 0.55*rr + (0.25 if committed else 0.0)
        p *= (0.7 + 0.06*profile.get('aggr', 5))
        if committed and so < 0.35:
            p *= 0.5
        if rel_ps >= 0.95:
            floor = 0.38 + 0.42*rr
            if street == 'river': floor *= 0.85
            p = max(p, floor)
        elif rel_ps >= 0.88:
            p = max(p, 0.22 + 0.34*rr)
        p = min(p, 0.93)
        if rng.random() < max(0.05, min(0.92, p)):
            return 'raise', 1.1, need, '밸류 레이즈(%.0f%%)' % (p*100)
        return 'call', 0.0, need, '밸류이나 콜 선택'

    # --- 블러프 레이즈: reraise × bluff 개념 ---
    # 계획을 반드시 본다. 예전에는 plan 조건이 없어서 pot_control(팟을 작게
    # 유지하겠다는 계획)인데도 여기로 떨어져 올인급 레이즈가 나왔다.
    # 또 쇼다운 가치가 있는 패를 블러프로 쓰면 이길 수 있는 상황을 버리게 된다.
    # giveup 은 제외한다. 그 계획의 사유 자체가 '블러프 개념/조건 미달'이라
    # 여기서 블러프 레이즈를 내면 판단 층이 이미 기각한 것을 집행부가 되살리는 셈이다.
    # 규율이 낮아 뒤집는 경우는 아래 이탈 경로에서 따로 처리한다.
    if has_c and eq < need - 0.05 and plan in ('bluff_2street', 'semibluff'):
        made_sd = plan_state.get('made', 0)
        if made_sd >= 2:
            pass                       # 투페어 이상은 쇼다운 가치가 있다 → 블러프 부적합
        else:
            blr = (PS.sk(profile, 'reraise')/10.0) * (PS.sk(profile, 'bluff')/10.0)
            if rng.random() < blr*0.28:
                return 'raise', 1.0, need, '블러프 레이즈(개념 %.2f)' % blr

    # --- 세미블러프: 레이즈 or 내재오즈 콜 ---
    if plan == 'semibluff' and plan_state.get('outs', 0) >= 8 and street != 'river':
        if rng.random() < 0.35:
            return 'raise', 0.95, need, '세미블러프 레이즈'
        if stack > pot:
            implied = min(0.08, 0.05 * min(1.0, stack/max(1.0, 2.0*pot)))
            need = max(0.02, need - implied)
        act = 'call' if eq >= need else 'fold'
        return act, 0.0, need, '세미블러프 내재오즈 반영'

    if plan == 'giveup' and has_c and eq < need - 0.05:
        # 포기 계획을 뒤집는 블러프 레이즈. 규율이 낮을수록 자주 나온다.
        # 계획 이탈이므로 반드시 기록한다.
        disc = PS.temper(profile, 'discipline', 5.0)
        blr = (PS.sk(profile, 'reraise')/10.0) * (PS.sk(profile, 'bluff')/10.0)
        p_dev = blr * 0.28 * max(0.05, 1.0 - 0.085*disc)
        if plan_state.get('made', 0) < 2 and rng.random() < p_dev:
            plan_state.setdefault('deviations', []).append(
                {'street': street, 'planned': 'fold', 'executed': 'raise',
                 'why': '규율 %.1f → 포기 계획 뒤집고 블러프 레이즈' % disc})
            return 'raise', 1.0, need, 'DEVIATE:포기 계획 뒤집은 블러프 레이즈'

    if plan in ('bluff_2street', 'giveup'):
        # 계획은 포기지만 팟오즈가 실제로 맞으면 접으면 안 된다.
        # 부등호를 계획으로 덮어쓰면 eq > need 인데 폴드하는 모순이 생긴다.
        # (계획이 못 미더우면 need 를 올려야지 부등호를 무시하면 안 된다)
        if eq >= need:
            return 'call', 0.0, need, '포기 계획이나 팟오즈가 맞음(eq %.3f ≥ need %.3f)' % (eq, need)
        return 'fold', 0.0, need, '포기/블러프 계획 + 팟오즈 미달 → 폴드'

    act = 'call' if eq >= need else 'fold'
    return act, 0.0, need, 'eq %.3f vs need %.3f' % (eq, need)


def decide_aggression(profile, board, street, plan, rel, n_opp, oop, initiative,
                      to_act_behind, rng, opp_est=None, outs=0):
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

    # --- 포기 계획은 원칙적으로 체크한다 ---
    # 다만 이니셔티브가 있으면 '지속벳'이라는 별개 동기가 존재한다.
    # 그 동기의 크기는 블러프 개념과 규율에서 나온다.
    if plan in ('giveup', 'showdown'):
        if not initiative:
            return 0.0, '포기 계획 + 이니셔티브 없음 → 체크'
        # 포기하기로 했는데 치는 것은 **계획 이탈**이다.
        # 계획을 못 지키는 정도는 discipline 의 함수다.
        # 규율 9.7 인 사람과 1.4 인 사람이 같은 빈도로 뒤집으면 성향이 죽는다.
        cf = cbet_freq(profile, board, n_opp, street, oop, rel, opp_est)
        if has_c:
            disc = PS.temper(profile, 'discipline', 5.0)
            cf *= max(0.05, 1.0 - 0.085*disc)
        return max(0.0, min(0.9, cf)), 'DEVIATE:포기 계획이나 지속벳(%.0f%%)' % (cf*100)

    if plan == 'trap':
        return 0.0, '함정 계획 → 체크'

    if plan in ('bluff_2street', 'semibluff'):
        if to_act_behind >= 2:
            return 0.0, '뒤에 %d명 → 블러프 포기' % to_act_behind
        p = 0.25 + 0.070*profile.get('bluff', 5) + 0.02*profile.get('gamble', 5)
        p *= (1 - 0.20*max(0, n_opp-1))
        if not initiative and oop:
            # 동크는 정석이 아니다. 수동형일수록 강하게 억제.
            supp = 0.92 - 0.05*a - 0.02*profile.get('bluff', 5)
            if has_c and outs >= 8:
                supp = max(0.45, supp - 0.035*PS.sk(profile, 'probe'))
            p *= max(0.03, 1.0 - max(0.30, min(0.97, supp)))
        return max(0.02, min(0.95, p)), '블러프 계획 실행(%.0f%%)' % (p*100)

    if plan == 'block':
        return 0.80, '블락벳 계획'

    if plan == 'pot_control':
        return max(0.05, min(0.6, 0.18 + 0.035*a)), '팟컨트롤 → 대부분 체크'

    # --- 밸류 계획 ---
    p = 0.30 + 0.058*a + 0.018*profile.get('gamble', 5)
    if has_c and rel < 0.85:
        p *= (0.55 + 0.09*PS.sk(profile, PS.street_concept('thin_value', street)))
    if profile.get('value') == 'xr':   p *= 0.68
    if profile.get('value') == 'lead': p *= 1.12
    if street == 'river': p *= 0.92
    if rel >= 0.65:
        p = p + (1.0 - p) * (((rel - 0.65)/0.35) ** 0.8)
    else:
        p *= (0.35 + 0.65 * (rel/0.80) ** 0.8)
    return max(0.05, min(0.97, p)), '밸류 계획 실행(%.0f%%)' % (p*100)


def decide_size(profile, hero, board, street, plan, rel, opp_range, my_range,
                pot, stack, rng, opp_est=None, nut=0.0, deviating=False):
    """이 스트리트 벳 사이즈(팟 대비)를 정하는 **유일한 지점**.

    예전에는 한 사이즈가 네 번 재계산됐다:
      SIZING 표 → TX.size_fraction 과 혼합 → overbet_frac 이 덮어씀
      → RU.shape_size 가 또 흔듦
    그래서 어느 값이 최종인지 추적이 안 됐고, 개인 성향이 어디서 반영되는지도 불명확했다.

    지금은 여기 하나에서 정한다. 집행부는 이 값을 칩으로 환산만 한다.
    (shape_size 는 '사람다운 끝자리'만 만드는 표현 계층이므로 집행부에 남긴다.)
    """
    base = SIZING.get(plan, {}).get(street, 0.0)
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
    if rel < 0.45:
        base *= 0.80                       # 약할수록 작게
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


SIZING = {
    'value_3street': {'flop':0.60,'turn':0.70,'river':0.75},
    'value_2street': {'flop':0.50,'turn':0.55,'river':0.0},
    'pot_control':   {'flop':0.30,'turn':0.0, 'river':0.30},
    'semibluff':     {'flop':0.55,'turn':0.65,'river':0.0},
    'bluff_2street': {'flop':0.45,'turn':0.60,'river':0.0},
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
    if ob < 4.0: return None                        # 개념이 없으면 선택지에 없음
    nut = R.nut_advantage(my_range, opp_range, board) if (my_range and opp_range) else 0.0
    if nut < 0.10: return None                      # 넛 우위 없이는 치지 않는다

    value_line = plan in ('value_3street', 'trap') and rel >= 0.85
    bluff_line = plan in ('bluff_2street', 'semibluff') and rel <= 0.25
    if not (value_line or bluff_line): return None  # 미들레인지는 제외

    p = 0.10 + 0.075*(ob - 4.0)                     # 개념 숙련도
    p *= (0.5 + 2.0*min(0.5, nut))                  # 넛 우위에 비례
    p *= (0.75 + 0.05*profile.get('aggr', 5))
    if street == 'river': p *= 1.35                 # 리버가 오버벳의 주 무대
    if bluff_line: p *= 0.65                        # 블러프 오버벳은 더 드물다
    # 상대가 큰 사이즈에 어떻게 반응하는가 — 오버벳 판단의 나머지 절반이다.
    # 잘 접는 상대에게 밸류 오버벳은 손해고(콜을 못 받음),
    # 안 접는 상대에게 블러프 오버벳은 자살이다. 방향이 정반대다.
    if opp_est:
        w = PS.exploit_weight(profile, opp_est.get('confidence', 0.0), opp_est.get('n', 0))
        if w > 0.0:
            d = opp_est.get('ftb', 0.52) - 0.52
            mult = (1.0 - 1.6*d) if value_line else (1.0 + 1.6*d)
            p = PS.blend(p, p*max(0.25, mult), w)
    if rng.random() > max(0.0, min(0.55, p)): return None

    # 사이즈: 넛 우위가 클수록 크게
    base = 1.15 + 0.55*min(1.0, nut) + 0.03*(ob - 4.0)
    return round(min(2.2, base * rng.uniform(0.92, 1.10)), 2)


def cbet_freq(profile, board, n_opp, street, oop, rel, opp_est=None):
    """이니셔티브 보유자의 지속벳 빈도. 핸드 강도와 별개인 구조적 빈도.

    opp_est 가 있고 이 사람이 상대를 보는 타입이면(exploit_weight) 조정한다.
    잘 접는 상대에겐 더 치고, 안 접는 상대에겐 덜 친다 —
    익스플로잇의 가장 기본이며, 자기 전략만 치는 선수는 이 조정을 하지 않는다.
    """
    a = profile.get('aggr', 5); b = profile.get('bluff', 5)
    base = {'flop': 0.42, 'turn': 0.30, 'river': 0.22}.get(street, 0.30)
    f = base + 0.035*a + 0.020*b
    f *= (0.62 ** max(0, n_opp-1))          # 다인원일수록 급감
    f *= (1 - 0.30*bot.board_danger(board)) # 젖은 보드에서 감소
    if oop: f *= 0.88
    f += 0.35*max(0.0, rel-0.6)             # 강할수록 추가
    if opp_est:
        w = PS.exploit_weight(profile, opp_est.get('confidence', 0.0), opp_est.get('n', 0))
        if w > 0.0:
            ftb = opp_est.get('ftb', 0.52)
            # 관측된 폴드율이 모집단 평균(0.52)보다 높으면 블러프 빈도를 올린다
            adj = f * (1.0 + 1.10*(ftb - 0.52))
            f = PS.blend(f, adj, w)
    return max(0.03, min(0.95, f))

def act_with_plan(hero, board, profile, plan_state, pot, tocall, stack, street,
                  initiative=True, oop=False, opp_range=None, bf=1.0, seed=None,
                  n_opp=1, to_act_behind=0, read=None, opp_est=None):
    if profile.get('concepts'):
        # ICM 개념이 없으면 버블팩터를 인지하지 못한다
        bf = 1.0 + (bf - 1.0) * min(1.0, PS.sk(profile, 'icm')/6.0)
    """계획을 스트리트에 걸쳐 실행. 체크레이즈·커밋 판단 포함."""
    rng = random.Random(seed)
    plan = plan_state['plan']
    if opp_est is None:
        opp_est = plan_state.get('opp_est')      # 계획에 실린 추정치를 이어 쓴다
    frac = SIZING[plan].get(street, 0.0)
    committed = spr(stack, pot) < 1.2          # 커밋 구간

    if tocall > 0:
        callers = [(0.30, 5)]*max(0, n_opp-1)
        if opp_range and len(opp_range) >= 20:
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
        # pot 은 pot_live 다 — 상대가 방금 낸 벳이 이미 포함돼 있다.
        # 여기서 tocall 을 또 더하면 분모에 콜 비용이 두 번 들어가 need 가
        # 실제보다 훨씬 낮게 나온다 (2,500/8,800=28% 가 6% 로 계산됐다).
        need_true = (tocall*bf)/max(1.0, float(pot))
        need = need_true
        if profile.get('concepts'):
            # 팟오즈 계산 오차. calc_noise 는 최대 3배까지 곱하는데,
            # need 는 확률이라 3배를 곱하면 38% 가 100% 가 되어 '더 강해졌는데
            # 폴드'하는 모순이 나온다. 오차는 오차 범위 안에 있어야 한다.
            nz = PS.calc_noise(profile, 'potodds', rng)
            nz = max(0.65, min(1.55, nz))
            need = need_true * nz
        if to_act_behind:
            # 뒤에 남은 사람 리스크. 확률에 상수를 더하지 않고
            # 남은 팟 지분 기준으로 비례 가산한다.
            need += (1.0 - need_true) * min(0.18, 0.06*to_act_behind)
        need = max(0.01, min(0.97, need))
        # 배팅라인 리딩 — 상대가 블러프일 사전확률만큼 문턱을 낮춘다
        if read is not None:
            trust = 0.25 + 0.06*profile.get('aggr', 5)
            if profile.get('concepts'):
                bc = PS.sk(profile, PS.street_concept('bluffcatch', street))
                trust *= min(1.4, (0.6*PS.sk(profile,'range_read') + 0.4*bc)/5.0)    # 리딩을 얼마나 신뢰하는가
            if A.ARCHETYPES.get(profile.get('type'),(0,)*6+('reg',''))[6] == 'fish': trust *= 0.35
            # 사이징 텔: 사이즈에서 정보를 읽는 능력. 없으면 큰 벳도 작은 벳도 똑같이 본다.
            if profile.get('concepts'):
                stell = PS.sk(profile, 'sizing_tell')
                sz_now = tocall/max(1.0, float(pot) - tocall)
                dev = abs(sz_now - 0.6)                      # 표준 사이즈에서 벗어난 정도
                trust *= (1.0 + 0.10*(stell - 5.0)/5.0 * min(2.0, dev/0.4))
            need -= trust * (read - 0.35)
        # 상·하한. 상한은 팟오즈를 배 이상 부풀리지 못하게,
        # 하한은 팟오즈의 절반 아래로 못 내려가게 한다.
        # 예전엔 하한이 없어서 상대를 블러프로 크게 읽으면
        # need 가 실제 팟오즈(32%)보다 낮은 19% 까지 떨어졌다.
        # 리딩은 문턱을 조정하는 것이지 팟오즈를 뒤집는 게 아니다.
        need = min(need, need_true*1.75 + 0.05)
        need = max(need, need_true*0.55)
        need = max(0.01, min(0.95, need))
        made_now = bot.made_strength(hero, board) if board else 0
        # 개인 행동 편향 — 같은 eq·같은 팟오즈라도 사람마다 다른 답을 낸다.
        # 이게 없으면 성향이 아무리 달라도 콜/폴드는 eq>=need 하나의 문턱으로 수렴해서
        # '평균은 맞지만 아무도 개성이 없는' 필드가 된다. calc_noise(랜덤 오차)와 달리
        # 이건 그 사람에게 고정된 방향성 편향이다.
        if profile.get('concepts') and board:
            # 실제 사이즈가 아니라 '이 사람이 인식한 사이즈'로 판단한다.
            # 균형 공식 정의역(2팟) 밖을 못 읽는 사람은 팟오즈를 오독한다.
            _sz_true = tocall/max(1.0, float(pot) - tocall)
            _sz_seen = PS.size_read(profile, _sz_true)
            need *= PS.call_bias(profile, street, _sz_seen,
                                 made_now, bot.draw_strength(hero, board))
            # 오독한 사이즈로 팟오즈를 다시 계산한다 (인식이 곧 판단 근거다)
            if abs(_sz_seen - _sz_true) > 1e-9:
                _p0 = float(pot) - tocall
                need = (_sz_seen*_p0)/max(1.0, _p0 + 2*_sz_seen*_p0)
            # 상대가 블러프를 많이 하는 사람이면 더 넓게 받아야 한다.
            # 개인 편향(call_bias)은 '내가 어떤 사람인가', 이건 '상대가 어떤 사람인가'다.
            if opp_est:
                w = PS.exploit_weight(profile, opp_est.get('confidence', 0.0),
                                      opp_est.get('n', 0))
                if w > 0.0:
                    bl = (opp_est.get('bluff', 4.5) - 4.5)/5.0     # -0.9 ~ +1.1
                    need = PS.blend(need, need*max(0.55, 1.0 - 0.35*bl), w)
            need = max(0.03, min(0.95, need))
        # ---------- 저항(tocall>0): 순수 집행 ----------
        # 폴드/콜/레이즈 판단은 전부 decide_response(판단 층)가 내린다.
        # 집행부는 그 결과를 칩으로 환산만 한다.
        act, mult, need, why = decide_response(
            profile, hero, board, street, plan, plan_state, eq, need,
            made_now, opp_range, pot, tocall, stack, committed, rng)
        plan_state.setdefault('acts', []).append(why)
        if act == 'raise':
            amt = min(stack, int(round((pot + 2*tocall)*mult/100))*100)
            if amt <= tocall:
                return ('call', tocall), eq, need
            return ('raise', amt), eq, need
        if act == 'call':
            return ('call', tocall), eq, need
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
    if plan == 'trap':               p = 0.55 + 0.12*sk
    elif rel >= 0.90:                p = 0.10 + 0.11*sk
    elif plan == 'semibluff' and outs >= 8 and street != 'river':
                                     p = 0.06 + 0.115*sk
    elif plan == 'bluff_2street':    p = 0.03 + 0.05*sk
    p *= (0.7 + 0.05*profile.get('aggr', 5))
    # 블러프 체크레이즈는 상대가 접어줘야 성립하고,
    # 밸류 체크레이즈는 상대가 콜해줘야 성립한다. 방향이 반대다.
    if opp_est:
        w = PS.exploit_weight(profile, opp_est.get('confidence', 0.0), opp_est.get('n', 0))
        if w > 0.0:
            d = opp_est.get('ftb', 0.52) - 0.52
            is_bluff = plan in ('semibluff', 'bluff_2street')
            mult = (1.0 + 1.5*d) if is_bluff else (1.0 - 1.0*d)
            p = PS.blend(p, p*max(0.2, mult), w)
    return rng.random() < max(0.0, min(0.90, p))


def preflop_plan(profile, pos, hand, bb, rng, aggressor_pos=None, open_bb=0.0,
                 n_callers=0, n_limpers=0, raise_level=1, behind_stacks=None,
                 tilt=0.0, field_q=0.6, opp_est=None, bf=1.0,
                 seats=8, ante=True, field_avg_bb=None, erosion=0.0):
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
                                  field_avg_bb=field_avg_bb, erosion=erosion)
        role = 'open'
    elif aggressor_pos is None:
        a, sz = _pf.iso_decision({'type': profile.get('type')}, pos, hand,
                                 n_limpers, bb, rng)
        role = 'iso'
    else:
        a, sz = _pf.defend_decision(profile, pos, aggressor_pos, hand, bb, open_bb,
                                    n_callers, rng, raise_level=raise_level,
                                    stack_bb=bb, tilt=tilt, field_q=field_q,
                                    exploit=rd, bf=bf)
        role = 'defend'

    # 프리플랍에서 확정된 것들 — 포스트플랍 계획이 이걸 물려받는다
    seed_info = {
        'pf_role': role,                       # open / iso / defend
        'pf_act': a,                           # raise / call / limp / shove / fold
        'pf_pos': pos,
        'pf_vs': aggressor_pos,
        'pf_level': raise_level,
        'pf_initiative': a in ('raise', '3bet', 'shove'),
        'pf_multiway': (n_callers + n_limpers) >= 2,
        'pf_hand_pct': _pf.pct(hand),
    }
    return a, sz, seed_info


def update_plan(state, hero, board, my_range, opp_range, profile, pot, stack,
                street, seed, n_opp, behind, prev_board, oop, initiative,
                opp_est=None, opp_stack_bb=None, tilt=0.0, first=False,
                pf_seed=None):
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
                       oop=oop, initiative=initiative,
                       opp_est=opp_est, opp_stack_bb=opp_stack_bb, tilt=tilt)
        # 프리플랍에서 확정된 것을 물려받는다. 이게 없으면 포스트플랍 계획이
        # 매번 백지에서 시작하고, '왜 3벳했는가'가 플랍 판단과 무관해진다.
        if pf_seed:
            st.update({k: v for k, v in pf_seed.items()})
            if pf_seed.get('pf_role') == 'defend' and pf_seed.get('pf_act') == 'raise':
                # 3벳 이상으로 들어온 팟은 내 레인지가 강하게 대표된다
                st['why'] = (st.get('why') or []) + ['프리플랍 3벳 팟 → 레인지 우위']
    else:
        st = _RU.revise_plan(state, hero, board, my_range, opp_range, profile,
                             pot, stack, street, seed, n_opp, behind, prev_board)

    # 계획 이력은 라벨과 별개로 이어진다. 새 dict 가 만들어져도 유지한다.
    if prev:
        for k in ('intents', 'deviations', 'streets', 'refreshed', 'bet_streets'):
            if prev.get(k) is not None and st.get(k) is None:
                st[k] = prev[k]

    if street != st.get('street_made') and street not in (st.get('refreshed') or []):
        st = refresh(st, hero, board, opp_range, profile, pot, stack, street,
                     n_opp, seed=seed, opp_est=opp_est)
        st.setdefault('refreshed', []).append(street)

    st = river_fix(st, hero, board)
    st['plan'] = _allowed(profile, st['plan'], rng)

    # 의도는 무저항 시점에만, 한 번만 확정한다.
    if intent_of(st, street) is None:
        st = attach_intent(st, hero, board, my_range, opp_range, profile,
                           pot, stack, street, rng, n_opp, behind,
                           oop, initiative, opp_est)
    return st


def river_fix(state, hero, board):
    """리버 도달 시 드로우 기반 계획은 무효. 메이드 여부로 재분류."""
    if len(board) < 5: return state
    st = dict(state)
    st['outs'] = 0
    if st.get('plan') == 'semibluff':
        made = bot.made_strength(hero, board)
        rel = st.get('rel', 0.5)
        if made >= 2 or rel >= 0.65:
            st['plan'] = 'value_2street'
            st['why'] = (st.get('why') or []) + ['리버: 드로우 완성 → 밸류 전환']
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
                'block': 'blockbet', 'pot_control': 'potcontrol'}
        if plan in need:
            s = PS.sk(profile, need[plan])
            if s < 1.5: return {'bluff_2street':'giveup','semibluff':'showdown',
                                'trap':'value_3street','block':'value_2street',
                                'pot_control':'showdown'}[plan]
            if s < 3.5:
                if rng is None:
                    raise ValueError('plan._allowed: rng 필수 (전역 RNG 사용 금지)')
                if rng.random() > (s-1.5)/2.0:
                    return {'bluff_2street':'giveup','semibluff':'showdown',
                            'trap':'value_3street','block':'value_2street',
                            'pot_control':'showdown'}[plan]
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
            opp_est=None):
    """계획은 유지하되 rel/eq/outs/danger 를 현재 보드로 갱신하고,
       근거가 무너지면 계획을 강등한다."""
    st = dict(state)
    rel = relative_strength(hero, board, opp_range)
    eq  = _eq_vs(hero, board, opp_range, n_opp, sims=300, seed=seed)
    outs = draw_strength(hero, board)
    made = bot.made_strength(hero, board)
    st.update({'rel': round(rel,2), 'eq': round(eq,3), 'outs': outs,
               'made': made, 'danger': round(bot.board_danger(board),2)})
    why = list(st.get('why') or [])
    old = st.get('plan')

    # 강등 임계값은 상대에 따라 움직인다.
    # 잘 접는 상대라면 내 강도가 떨어져도 계속 밀어붙일 근거가 되고,
    # 안 접는 상대(스테이션)라면 더 일찍 포기해야 한다.
    # 자기 전략만 치는 선수(exploit_weight=0)는 이 조정을 하지 않는다.
    oe = opp_est if opp_est is not None else st.get('opp_est')
    give_thr, ctrl_thr = 0.12, 0.30
    if oe:
        w = PS.exploit_weight(profile, oe.get('confidence', 0.0), oe.get('n', 0))
        if w > 0.0:
            d = (oe.get('ftb', 0.52) - 0.52)      # 모집단 평균 대비 폴드 성향
            give_thr = PS.blend(give_thr, max(0.02, give_thr - 0.35*d), w)
            ctrl_thr = PS.blend(ctrl_thr, max(0.10, ctrl_thr - 0.55*d), w)
            if abs(d) > 0.04:
                why.append('상대 폴드성향 %+.0f%%p → 포기 문턱 %.2f' % (100*d, ctrl_thr))

    # 근거 붕괴 판정
    if old in ('value_3street','value_2street') and rel < ctrl_thr and made <= 1:
        st['plan'] = 'giveup' if rel < give_thr else 'pot_control'
        why.append('%s: 상대강도 %.2f로 하락 → %s' % (street, rel, st['plan']))
    elif old == 'semibluff' and outs < 6:
        st['plan'] = 'value_2street' if rel >= 0.6 else 'giveup'
        why.append('%s: 드로우 소멸(%d아웃) → %s' % (street, outs, st['plan']))
    elif old == 'trap' and st.get('_no_bite', 0) >= 1:
        # 함정을 팠는데 아무도 물지 않았다 → 직접 밸류로 전환
        st['plan'] = 'value_3street' if rel >= 0.85 else 'value_2street'
        why.append('%s: 상대가 벳하지 않음 → 함정 해제, 직접 밸류' % street)
    elif old in ('pot_control', 'block', 'showdown') and (
            rel >= 0.70 or made >= max(2, st.get('made', 0) + 1)):
        # 승격 조건. 예전에는 rel >= 0.88 하나뿐이라
        # 리버에 트립스가 되어 rel 0.05 → 0.76, made 1 → 3 이 됐는데도
        # 계획이 턴의 pot_control 그대로 남아 체크했다.
        # rel 만이 아니라 '내 완성 강도가 올라갔는가'도 승격 근거다.
        st['plan'] = 'value_3street' if rel >= 0.88 else 'value_2street'
        why.append('%s: 강도 상승(rel %.2f, made %d) → 밸류 전환' % (street, rel, made))
    elif old == 'bluff_2street' and rel >= 0.75:
        st['plan'] = 'value_2street'
        why.append('%s: 블러프였으나 강도 상승 → 밸류 전환' % street)
    st['plan'] = _allowed(profile, st['plan'],
                          random.Random(_zlib.crc32(repr((hero, board, street)).encode())))
    st['why'] = why[-4:]
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


def stackoff_plan(hero, board, profile, pot, stack, street, rng):
    """강한 핸드로 리버 올인까지 가는 사이즈 배분.
       SPR이 낮을수록 유효하고, 딥에서는 사실상 불가능하다."""
    s = spr(stack, pot)
    so = PS.sk(profile, 'stackoff') if profile.get('concepts') else 4.0
    if s < 1.2:
        return {'ok': True, 'why': 'SPR %.1f — 이미 커밋, 계획 불필요' % s,
                'flop': 0.75, 'turn': 1.0, 'river': 1.0}
    if s <= 5.5:
        # 3스트리트로 정확히 다 넣는 기하급수 사이즈
        r = (2*stack/pot + 1) ** (1/3)
        frac = (r - 1) / 2
        return {'ok': True, 'why': 'SPR %.1f — 3스트리트 스택오프 가능' % s,
                'flop': round(frac, 2), 'turn': round(frac, 2), 'river': round(frac, 2)}
    if s <= 10 and so >= 6.5:
        # 오버벳 성향이 강한 사람만 시도
        r = (2*stack/pot + 1) ** (1/3)
        frac = min(1.6, (r - 1) / 2)
        return {'ok': True, 'why': 'SPR %.1f — 오버벳으로 스택오프 시도(소수 유형)' % s,
                'flop': round(frac, 2), 'turn': round(frac, 2), 'river': round(frac, 2)}
    return {'ok': False, 'why': 'SPR %.1f — 딥스택이라 3스트리트로 못 넣음' % s,
            'flop': 0.6, 'turn': 0.65, 'river': 0.7}
