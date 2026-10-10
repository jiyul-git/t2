import random, zlib as _zlib, hashlib as _hashlib
import bot, ranges as R, preflop as pf, archetypes as A, persona as PS, texture as TX
import icm as _ICM
import reads as RD

def spr(stack, pot): return stack/max(1, pot)


def board_texture_read(profile):
    """보드 텍스처를 읽는 정도 0~1 = min(1, sk(board_texture)/7).

    같은 능력이 위험 인지(/6)와 나머지 다섯 소비처(/7)에서 다른 포화점으로
    정규화돼 있었다(stage9 B6). 하나의 인지 능력이므로 한 정규화로 통일했다 —
    기존 다수값 7 을 썼고 새 수치는 만들지 않았다. 개념 없는 프로필의
    처리(0.5 기본값 / 원시값)는 각 소비처의 아키타입 기본값이라 호출부에 둔다.
    """
    return min(1.0, PS.sk(profile, 'board_texture')/7.0)


def perceived_board_danger(profile, board):
    """이 사람이 인지하는 보드 위험(0~1).

    원시 위험(bot.board_danger)에 텍스처 읽기 능력을 곱한다 — 텍스처를 못
    읽으면 위험을 모른다. 개념이 없는 프로필은 원시값 그대로다.
    plan_state['danger'] 는 언제나 이 값이고, 원시값은 'danger_raw' 로 따로
    기록한다(L-RA06/L109, stage9 B6).
    """
    d = bot.board_danger(board)
    if profile.get('concepts'):
        d *= board_texture_read(profile)
    return d

def line_bluff_prior(opp_profile, street, n_barrels, sizing_frac, board,
                     aggressor_pos_oop, opp_read=None):
    """현재 betting range 안의 bluff share를 설명용으로 반환한다.

    판단의 단일 근거는 ranges.line_bluff_share()다. 이 값은 call threshold를
    직접 움직이지 않는다. 같은 값이 상대 betting combo 구성에 반영되고,
    call/fold는 그 combo range에 대한 equity와 pot odds로 결정한다.

    aggressor_pos_oop은 당장은 기록 호환용이다. 포지션을 line share에 넣으려면
    opponent range 생성에도 똑같이 넣어야 하므로 별도 보정은 하지 않는다.
    """
    base_axis = 5.0
    if opp_read:
        w = max(0.0, min(1.0, float(opp_read.get('w', 0.0) or 0.0)))
        gap = max(-1.0, min(1.0, float(opp_read.get('bluff_gap', 0.0) or 0.0)))
        base_axis = max(1.0, min(10.0, 5.0 + 5.0*w*gap))
    return R.line_bluff_share(
        board, street, sizing_frac, base_axis, n_barrels=n_barrels)

def board_paired(board):
    rs = [c[0] for c in board]
    return len(set(rs)) < len(rs)

_RS_CACHE={}
def relative_strength(hero, board, opp_range=None):
    """상대 레인지 중 나를 이기는 probability mass의 역수. 0(최하)~1(넛).

    equity 가 아니다(L097, stage9 B5 판정: 이름 유지 + 정의 명시). 지금 보드에서의
    순위 몫이며 남은 카드와 무승부 분할을 보지 않는다. 판단용 rel 은
    _decision_relative_strength 가 멀티웨이 joint / 불완전 시 합집합 fallback 으로 만든다.

    Legacy unique-list input is exactly the former combo-count metric because
    every combo has unit mass. A non-uniform posterior contributes according to
    its relative probability mass instead of being silently flattened.
    """
    if len(board) < 3:
        return 0.5

    if opp_range:
        rk = _zlib.crc32(repr(R.range_signature(opp_range)).encode())
    else:
        rk = 0
    ck = (tuple(sorted(hero)), tuple(board), rk)
    if ck in _RS_CACHE:
        return _RS_CACHE[ck]

    mine = bot.eval7(hero + board)
    dead = set(hero) | set(board)
    pool = opp_range if opp_range else None

    if pool:
        items = [
            (c, w) for c, w in R.range_items(pool)
            if not (set(c) & dead)
        ]
        if not items:
            return 0.5
        total = sum(w for _c, w in items)
        better = sum(
            w for c, w in items
            if bot.eval7(list(c) + board) > mine)
        out = 1.0 - (better / total if total > 0 else 0.5)
    else:
        deck = [c for c in bot.FULLDECK if c not in dead]
        cand = [
            (deck[i], deck[j])
            for i in range(len(deck))
            for j in range(i + 1, len(deck))
        ]
        if not cand:
            return 0.5
        # No perceived range: keep the historical top-half heuristic exactly.
        ranked = sorted(
            cand,
            key=lambda c: bot.eval7(list(c) + board),
            reverse=True)
        top = ranked[:max(1, len(ranked)//2)]
        better = sum(
            1 for c in top
            if bot.eval7(list(c) + board) > mine)
        out = 1.0 - better / len(top)

    _RS_CACHE[ck] = out
    return out


def joint_relative_strength(hero, board, opp_ranges, n_opp=None, sims=600, seed=None):
    """멀티웨이용 현재 보드 상대강도.

    기존 relative_strength 의 heads-up 의미를 그대로 확장한다:
    각 상대의 seat-keyed perceived range 에서 호환 가능한 한 콤보씩 뽑았을 때
    **어느 상대에게도 엄밀히 뒤지지 않을 확률**.

    - tie 는 기존 relative_strength 와 마찬가지로 '뒤지지 않음'이므로 1로 센다.
    - 한 좌석이라도 range 가 없으면 None. 다른 상대 range 를 복제하지 않는다.
    - heads-up(한 pool)은 기존 relative_strength 와 정확히 같은 값을 반환한다.
    - Monte Carlo 는 별도 deterministic seed 를 써 shared RNG 를 소비하지 않는다.
    """
    if len(board) < 3:
        return 0.5 if (n_opp in (None, 1)) else None

    pools = []
    if isinstance(opp_ranges, dict):
        items = sorted(opp_ranges.items(), key=lambda kv: str(kv[0]))
        if n_opp is not None and len(items) != int(n_opp):
            return None
        for _, r in items:
            if not r:
                return None
            pools.append(dict(r) if isinstance(r, dict) else list(r))
    elif isinstance(opp_ranges, (list, tuple)):
        if n_opp is not None and len(opp_ranges) != int(n_opp):
            return None
        for r in opp_ranges:
            if not r:
                return None
            pools.append(dict(r) if isinstance(r, dict) else list(r))
    else:
        return None

    if not pools:
        return None

    dead = set(hero) | set(board)
    clean = []
    for r in pools:
        rr = bot._filter_pool(r, dead, sort_legacy=True)
        if not rr:
            return None
        clean.append(rr)

    if len(clean) == 1:
        return relative_strength(hero, board, clean[0])

    if seed is None:
        seed = _zlib.crc32(
            repr((tuple(sorted(hero)), tuple(board),
                  tuple(tuple(r) for r in clean), int(sims))).encode())
    rng = random.Random(seed)
    mine = bot.eval7(hero + board)
    not_behind = 0
    run = 0
    prepped = [bot.prepare_pool(p) for p in clean]
    for _ in range(int(sims)):
        used = set(dead)
        scores = []
        ok = True
        for pool in prepped:
            for _try in range(60):
                c = bot._sample_pool_combo(rng, pool)
                if c[0] not in used and c[1] not in used:
                    used.add(c[0]); used.add(c[1])
                    scores.append(bot.eval7(list(c) + board))
                    break
            else:
                ok = False
                break
        if not ok:
            continue
        run += 1
        if mine >= max(scores):
            not_behind += 1
    return (not_behind / run) if run else None


def _decision_relative_strength(hero, board, opp_range, n_opp=1,
                                opp_ranges=None, sims=600, seed=None):
    """판단용 상대강도 + provenance.

    HU 는 legacy relative_strength 그대로.
    MW 는 complete seat pools 일 때 joint metric, 불완전하면 legacy union fallback.
    """
    legacy = relative_strength(hero, board, opp_range) if board else 0.5
    if int(n_opp or 1) <= 1:
        return legacy, {
            'source': 'heads_up',
            'union': legacy,
            'joint': legacy,
            'complete': True,
        }

    joint = joint_relative_strength(
        hero, board, opp_ranges, n_opp=n_opp, sims=sims, seed=seed)
    if joint is None:
        return legacy, {
            'source': 'union_fallback_incomplete',
            'union': legacy,
            'joint': None,
            'complete': False,
        }
    return joint, {
        'source': 'joint_seat_pools',
        'union': legacy,
        'joint': joint,
        'complete': True,
    }


def _decision_nut_advantage(my_range, board, opp_range, n_opp=1,
                            opp_ranges=None, sims=1600, seed=None):
    """판단용 nut advantage + provenance. HU exact, MW seat-keyed, incomplete union fallback."""
    if not my_range or not opp_range or not board:
        return 0.0, {'source':'unavailable','union':0.0,'joint':None,'complete':False}
    legacy=R.nut_advantage(my_range,opp_range,board)
    if int(n_opp or 1)<=1:
        return legacy, {'source':'heads_up','union':legacy,'joint':legacy,'complete':True}
    joint=R.joint_nut_advantage(
        my_range,opp_ranges,board,n_opp=n_opp,sims=sims,seed=seed)
    if joint is None:
        return legacy, {'source':'union_fallback_incomplete','union':legacy,
                        'joint':None,'complete':False}
    return joint, {'source':'joint_seat_pools','union':legacy,
                   'joint':joint,'complete':True}

def _decision_range_advantage(my_range, board, opp_range, n_opp=1,
                              opp_ranges=None, sims=600, seed=None,
                              joint_seed=None):
    """판단용 range advantage + provenance.

    HU 는 legacy R.range_advantage 그대로.
    MW complete seat pools 은 R.joint_range_advantage.
    불완전한 seat 정보는 legacy union 으로만 fallback 하며 range 를 발명하지 않는다.
    """
    if not my_range or not opp_range or not board:
        return 0.0, {
            'source': 'unavailable',
            'union': 0.0,
            'joint': None,
            'complete': False,
        }

    legacy = R.range_advantage(
        my_range, opp_range, board, sims=sims, seed=seed)
    if int(n_opp or 1) <= 1:
        return legacy, {
            'source': 'heads_up',
            'union': legacy,
            'joint': legacy,
            'complete': True,
        }

    joint = R.joint_range_advantage(
        my_range, opp_ranges, board, n_opp=n_opp,
        sims=sims, seed=joint_seed)
    if joint is None:
        return legacy, {
            'source': 'union_fallback_incomplete',
            'union': legacy,
            'joint': None,
            'complete': False,
        }
    return joint, {
        'source': 'joint_seat_pools',
        'union': legacy,
        'joint': joint,
        'complete': True,
    }


def _decision_blocker_effect(hero, board, opp_range, street, size_frac,
                             n_opp=1, opp_ranges=None, seed=None, tag='blocker'):
    """판단용 blocker_effect + provenance.

    HU 는 legacy blocker_effect 그대로.
    MW complete seat pools 은 same-scale joint_blocker_effect.
    불완전한 seat 정보는 현재 union 의미로 fallback 한다. 이 fallback 자체는
    partial-pool audit 의 별도 미해결 항목이며 여기서 상대 range 를 발명하지 않는다.
    """
    legacy = (R.blocker_effect(
        hero, opp_range, board, street, size_frac, False)
        if (opp_range and board) else 0.0)

    if int(n_opp or 1) <= 1:
        return legacy, {
            'source': 'legacy_hu',
            'union': legacy,
            'joint': legacy,
            'complete': True,
        }

    _jseed = (_zlib.crc32(('%s|%s' % (seed, tag)).encode())
              if seed is not None else None)
    joint = R.joint_blocker_effect(
        hero, opp_ranges, board, street, size_frac,
        n_opp=n_opp, sims=1200, seed=_jseed, for_value=False)
    if joint is None:
        return legacy, {
            'source': 'union_fallback_incomplete',
            'union': legacy,
            'joint': None,
            'complete': False,
        }
    return joint, {
        'source': 'joint_seat_pools',
        'union': legacy,
        'joint': joint,
        'complete': True,
    }


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
    return max(0.0, min(1.0, rel + self_strength_bias_shift(profile, rel, outs, made)))


def self_strength_bias_shift(profile, rel, outs=0, made=0):
    """계산된 rel(사실) 위에 얹는 자기 핸드 인식 편향(PERCEPTION, ledger L105).

    overpair_love / draw_love / sticky 의 합. 클램프는 perceived_rel 이 한다.
    """
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
    return adj


def _range_sig(combos):
    """Stable archive signature for support + posterior mass.

    Legacy lists and uniformly weighted dicts keep the historical support-only
    SHA payload exactly, so old archives remain comparable. Only genuinely
    non-uniform weighted ranges add normalized mass to the payload.
    """
    if not combos:
        return None

    if isinstance(combos, dict) and not R.range_is_uniform(combos):
        wr = R.weighted_range(combos)
        total = sum(wr.values()) or 1.0
        payload = '\n'.join(
            '%s@%.17g' % (str(tuple(c)), float(w) / total)
            for c, w in R.range_items(wr)
        )
    else:
        support = R.range_support(combos)
        payload = '\n'.join(sorted(str(tuple(c)) for c in support))
    return _hashlib.sha256(payload.encode()).hexdigest()[:16]


def _decision_range_sig(combos):
    """In-process refresh signature.

    Preserve the old legacy support hash exactly. Weighted posteriors with the
    same support but different probability mass must still trigger refresh.
    """
    if not combos:
        return 0
    if isinstance(combos, dict) and not R.range_is_uniform(combos):
        return hash(R.range_signature(combos))
    return hash(frozenset(map(str, R.range_support(combos))))


def _normalize_opp_pools(opp_range, n_opp, opp_ranges=None):
    """Equity용 seat pools. **모르는 상대를 아는 상대로 복제하지 않는다.**

    반환 list 길이는 항상 n_opp이고, 모르는 seat는 None이다.
    HU legacy에서만 opp_range를 실제 상대 pool로 사용한다. Multiway의
    opp_range는 과거 union/compat 값이라 한 사람의 identity로 재사용하지 않는다.

    이전 구현은 일부 seat range만 있을 때 마지막/union range를 복제했다.
    그러면 "B를 모르니 A와 같은 사람"으로 가정하는 비인간적 판단이 된다.
    """
    want=max(1,int(n_opp or 1))
    pools=[]
    if isinstance(opp_ranges,dict):
        for k in sorted(opp_ranges,key=lambda x:str(x)):
            r=opp_ranges.get(k)
            pools.append(R.range_copy(r) if r else None)
    elif isinstance(opp_ranges,(list,tuple)):
        pools=[R.range_copy(r) if r else None for r in opp_ranges]

    if pools:
        pools=pools[:want]
        while len(pools)<want:
            pools.append(None)
        return pools

    if want==1 and opp_range:
        return [R.range_copy(opp_range)]
    return [None]*want


def _opp_ranges_signature(opp_ranges):
    """좌석별 레인지 묶음의 refresh 서명(좌석 키 + 각 레인지의 보관용 SHA).

    네 서명은 계약이 다르다(ledger L082):
      ranges.range_signature   equity/캐시 시드 payload(균일 가중치는 legacy support)
      _range_sig               보관용 16자리 SHA(과거 아카이브와 비교 가능)
      _decision_range_sig      프로세스 내 refresh 해시(질량이 다르면 refresh)
      _opp_ranges_signature    seat-keyed 묶음의 refresh 비교(이 함수)
    """
    if isinstance(opp_ranges, dict):
        return tuple((str(k), _range_sig(v)) for k, v in
                     sorted(opp_ranges.items(), key=lambda kv: str(kv[0])))
    if isinstance(opp_ranges, (list, tuple)):
        return tuple((str(i), _range_sig(v)) for i, v in enumerate(opp_ranges))
    return ()


def _eq_current(hero, board, opp_range, n_opp, sims=400, seed=None, opp_ranges=None,
                audit=None):
    """**보드를 돌리지 않은** 에쿼티. 상대별 레인지를 각각 보존한다.

    소비처(stage9 B3 확인): make_plan 은 이 값을 '지금 바로 쇼다운했을 때'의
    쇼다운 가치(`_sd_eq`)로 써서 순수 블러프 분기 진입을 막는다 — 판단에
    쓰인다. refresh 는 eq 를 갱신할 때 기록용 짝(eq_current/eq_delta)으로만
    다시 계산한다. (예전 문구 '기록 전용'은 make_plan 소비를 빠뜨렸다.)
    """
    if not board:
        if audit is not None:
            audit.update(complete=False, reason='missing_board',
                         requested=int(sims), accepted=0)
        return None
    dead = set(hero) | set(board)
    pools0 = _normalize_opp_pools(opp_range, n_opp, opp_ranges)
    pools = [
        (bot._filter_pool(p, dead, sort_legacy=True)
         if p else bot.range_combos(0.35, dead))
        for p in pools0
    ]
    # A missing seat is not a zero-equity opponent and must not be dropped.
    if not pools or any(not p for p in pools):
        if audit is not None:
            audit.update(complete=False, reason='missing_opponent_range',
                         requested=int(sims), accepted=0)
        return None
    if seed is None:
        seed = _zlib.crc32(repr((sorted(hero), tuple(board), pools, sims)).encode())
    rng = random.Random(seed)
    hs = bot.eval7(hero + board)
    share = 0.0; run = 0
    prepped = [bot.prepare_pool(p) for p in pools]
    for _ in range(sims):
        used = set(dead); opps = []; ok = True
        for pool in prepped:
            for _t in range(40):
                cc = bot._sample_pool_combo(rng, pool)
                if cc[0] not in used and cc[1] not in used:
                    used.add(cc[0]); used.add(cc[1]); opps.append(list(cc)); break
            else:
                ok = False; break
        if not ok:
            continue
        run += 1
        opp_scores = [bot.eval7(o + board) for o in opps]
        share += bot._showdown_share(hs, opp_scores)
    # Match bot.equity_vs_pools: even a partial accepted sample is not a
    # decision-grade estimate. A fully accepted real zero remains numeric 0.0.
    complete = (sims > 0 and run == sims)
    if audit is not None:
        audit.update(complete=complete, requested=int(sims), accepted=run,
                     rejected=int(sims) - run,
                     reason=('computed' if complete else
                             'no_valid_current_samples' if run == 0 else
                             'insufficient_current_samples'))
    return share / run if complete else None


def _eq_vs(hero, board, opp_range, n_opp, sims=400, seed=None, opp_ranges=None,
           audit=None):
    """추정 레인지 기준 에쿼티.

    아는 상대는 그 seat의 perceived range, 모르는 상대는 중립 field range를
    사용한다. 다른 실제 상대의 range를 복사하지 않는다.
    """
    dead=set(hero)|set(board or [])
    raw=_normalize_opp_pools(opp_range,n_opp,opp_ranges)
    pools=[
        (bot._filter_pool(p,dead,sort_legacy=True)
         if p else bot.range_combos(0.35,dead))
        for p in raw
    ]
    # Never drop a missing opponent: that would turn multiway into fictitious HU.
    if not pools or any(not p for p in pools):
        if audit is not None:
            audit.update(complete=False, reason='missing_opponent_range',
                         requested=int(sims), accepted=0)
        return None
    _s=sims if min(len(p) for p in pools)>=20 else int(sims*1.8)
    return bot.equity_vs_combos(hero,board,pools,sims=_s, audit=audit)


def _plan_eq(hero, board, opp_range, n_opp, sims, seed=None, opp_ranges=None,
             audit=None):
    """계획용 에쿼티. 추정 레인지가 보드·내 패와 전부 겹치면(모순) 모르는 상대로 본다.

    _eq_vs 는 이때 None 을 돌려준다(근거 없음). continue_range_call_equity 는 그 None 을
    '근거 없음'으로 쓰지만, make_plan/refresh 는 에쿼티가 반드시 있어야 해서 예전에는
    핸드 전체가 예외로 건너뛰어졌다(완주 시뮬 시드 11·12). 새 값을 짓지 않고
    모르는 seat 와 같은 중립 field range 로 잰다. 반환: (eq, fallback 여부).
    """
    original_audit = {}
    eq = _eq_vs(hero, board, opp_range, n_opp, sims=sims, seed=seed,
                opp_ranges=opp_ranges, audit=original_audit)
    if eq is not None:
        return eq, False
    fallback_audit = {}
    eq = _eq_vs(hero, board, None, n_opp, sims=sims, seed=seed,
                audit=fallback_audit)
    if eq is None and audit is not None:
        audit.update(source='plan_and_field_equity_unavailable',
                     original=original_audit, field_fallback=fallback_audit)
    return eq, True


def opp_bet_prob(opp_est, w, street, opp_role=None):
    """체크했을 때 상대가 벳해줄 확률. 트랩의 성립 조건 그 자체다.

    정보가 없거나(w=0) 이 사람이 상대를 안 보는 타입이면 모집단 평균으로 돌아간다.
    그게 '자기 전략대로 친다'의 의미다 — 상대를 특정하지 않고 평균적인 상대를 가정한다.

    opp_role 은 상대가 이 스트리트에서 어떤 입장으로 '체크받는가'다.
      'aggressor' — 직전 스트리트 공격자: 라인을 잇는 c벳/배럴 빈도
      'probe'     — 비공격자(내가 공격자이고 내가 체크함): 프로브 빈도
    프로브는 c벳/배럴과 다른 질문이라, 예전처럼 상대의 c벳 빈도로 대신하면
    '공격자일 때 잘 치는 사람'을 '체크받으면 치는 사람'으로 오독한다.
    프로브 표본이 적으면 같은 질문의 기본값(base)으로 표본 수만큼 당긴다
    (reads._shrink 와 같은 수축). None 은 예전 동작(c벳/배럴)이다.
    """
    base = {'flop': 0.45, 'turn': 0.38, 'river': 0.30}.get(street, 0.40)
    if not opp_est or w <= 0.0:
        return base
    if opp_role == 'probe':
        _raw = opp_est.get('probe_%s' % street)
        _n = int(opp_est.get('probe_%s_n' % street, 0) or 0)
        obs = RD._shrink(_raw, _n, base, 1.0, 1.0) if _raw is not None else base
        obs = 0.65*obs + 0.35*(opp_est.get('aggr', 5.0)/10.0)
        return max(0.05, min(0.92, PS.blend(base, obs, w)))
    # 관찰된 씨벳/배럴 빈도와 공격축에서 추정
    obs = opp_est.get('cbet' if street == 'flop' else 'barrel')
    if obs is None:
        obs = base
    # aggr 은 관측 추정치라 그대로 쓴다 — 이 함수는 '상대가 칠 확률'을 내는
    # 모델이지 내가 얼마나 읽는가가 아니다. 인식 한계는 호출부의 w 가 이미 건다.
    obs = 0.65*obs + 0.35*(opp_est.get('aggr', 5.0)/10.0)
    return max(0.05, min(0.92, PS.blend(base, obs, w)))




def field_effective_stack_bb(opp_stack_bbs, fallback=None):
    """Maximum stack depth that can still contest hero in a multiway pot.

    Stack identity is preserved upstream; this scalar is used only by the
    existing target-commit geometry which accepts one effective cap.  Using the
    former single 'main opponent' could understate the amount at risk whenever
    the aggressor was short but another live opponent was deep.
    """
    vals=[]
    if isinstance(opp_stack_bbs, dict):
        for v in opp_stack_bbs.values():
            if v is not None:
                try:
                    vals.append(max(0.0,float(v)))
                except (TypeError,ValueError):
                    pass
    if vals:
        return max(vals)
    return fallback

def select_field_opponent(profile, opp_ests, street, purpose='fold_constraint'):
    """Select the real opponent that constrains a multiway judgment.

    We do not average identities into a synthetic villain.  Each seat keeps its
    own perceived estimate/read.  The decision asks a purpose-specific question:

    - fold_constraint: bluff/value extraction must survive the opponent least
      likely to fold. Unknown evidence is neutral and therefore constrains an
      overconfident exploit against some other seat.
    - bet_probability: a trap only needs one opponent likely to bet, so choose
      the highest perceived bet probability.

    Returns {'seat','est','read','score'} or None.  Heads-up callers may keep
    using the direct opp_est path.
    """
    if not isinstance(opp_ests, dict) or not opp_ests:
        return None
    rows=[]
    for seat, est in sorted(opp_ests.items(), key=lambda kv: str(kv[0])):
        if not est:
            continue
        rd=PS.read_opponent(profile, est)
        if purpose == 'bet_probability':
            see=(0.65*float(rd.get('see_freq',0.0))
                 +0.35*float(rd.get('see_line',0.0)))
            w=float(rd.get('w',0.0))*see
            score=opp_bet_prob(est,w,street)
        else:
            # effective fold adjustment; 0 means no usable exploit evidence.
            score=float(rd.get('w',0.0))*float(PS.street_gap(rd,street) or 0.0)
        rows.append({'seat':seat,'est':est,'read':rd,'score':float(score)})
    if not rows:
        return None
    if purpose == 'bet_probability':
        return max(rows,key=lambda x:(x['score'],str(x['seat'])))
    return min(rows,key=lambda x:(x['score'],str(x['seat'])))

def trap_judgment(profile, opp_est, spr_now, danger, multiway, street, tilt, sk,
                  opp_role=None):
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
    # 상대 정보 적용은 모든 읽기 소비처와 같은 단일 입구(read_opponent)를
    # 쓴다(Human Model 3차 EXPLOIT_WEIGHT_V3 통합). 적용 의지·증거량은 공통 w,
    # '벳 빈도를 보는 능력'은 opp_bet_prob 자신의 혼합(빈도 0.65 / 공격 축 0.35)
    # 그대로 see_freq / see_line 로 나눠 건다. 예전 exploit_weight 는
    # range_read·attention 을 전역 의지 배수에 다시 섞어 인식을 이중으로 셌다.
    _rd_trap = PS.read_opponent(profile, opp_est)
    _see_bet = (0.65*_rd_trap.get('see_freq', 0.0)
                + 0.35*_rd_trap.get('see_line', 0.0))
    w = _rd_trap.get('w', 0.0) * _see_bet
    pbet = opp_bet_prob(opp_est, w, street, opp_role=opp_role)

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


def _blocker_score_bluff_factor(blk):
    """make_plan blocker_score contribution to bluff_ok.

    Isolated so the approximate strong-combo proxy can be audited separately
    from blocker_effect without changing production behavior.
    """
    return 0.5 + 1.8*blk


def _blocker_net_bluff_factor(blk_net):
    """make_plan blocker_effect contribution to bluff_ok."""
    return max(0.45, min(1.65, 1.0 + 4.0*blk_net))


def has_showdown_value(made, equity, mw):
    """쇼다운 가치: 메이드 핸드이거나 equity가 0.42+0.05*다인원 이상.

    make_plan 의 두 호출부가 **다른 equity 기준**을 넘긴다 — 중간강도 폴백은
    eq(런아웃 포함), 최종 분기는 eq_current(지금 보드). 기준 차이는 보존하고
    호출부에서 드러나게만 했다(semantic audit re-audit; 통일은 행동 변경).
    """
    return made >= 1 or equity >= 0.42 + 0.05*mw


def potcontrol_disposition(profile):
    """팟을 작게 유지하려는 성향 0~1 (ICM 인식·도박성·공격성). potcontrol 라벨/빈도와 분리(L122)."""
    return max(0.0, min(1.0, (profile['icm'] + (10-profile['gamble']) + (10-profile['aggr']))/30.0))


# '콜당했을 때도 앞서는가'의 판단 기준(L-S9-03). 벳/레이즈를 밸류로 분류하는
# 이진 질문은 continue range 대비 equity 가 이 값 이상이어야 한다 — 콜받는
# 부분의 손익분기다(접는 핸드는 어차피 지는 핸드이거나, 우리 equity 를
# 포기하고 나간 것이라 밸류 판정을 낮추는 방향이 아니다).
VALUE_WHEN_CALLED_EQ = 0.50


def ahead_when_called(eq_vs_continue):
    """밸류 자격: continue range 대비 equity 가 손익분기(0.50) 이상인가.

    river 얇은 밸류, 개선된 블러프 재분류, 밸류 레이즈 자격이 같은 질문을
    서로 다른 문턱(0.50 / 0.54 + 전체 rel 0.55 / > 0.5)으로 물었다. 하나로 합친다.
    근거가 없으면(None) 밸류로 인정하지 않는다 — 콜 레인지를 지어내지 않는다.
    """
    return eq_vs_continue is not None and float(eq_vs_continue) >= VALUE_WHEN_CALLED_EQ


def continue_range_strength(hero, board, profile, street, size_frac,
                            opp_range, opp_ranges, n_opp, made, seed=None):
    """그 사이즈를 계속하는 상대 레인지 대비 '인지된' 상대강도(rel 척도). 없으면 None.

    연속 강도 입력(커밋 목표, 오버벳 양극성)이 쓰는 단일 계산(L-S9-03/04).
    멀티웨이는 seat 별 continue range 가 전부 있을 때 joint, 아니면 HU/합집합
    경로(_decision_relative_strength 의 기존 fallback)를 그대로 쓴다.
    인지 편향은 perceived_rel 로 rel 과 같은 방식으로 건다.
    """
    _cont = None
    if int(n_opp or 1) > 1 and isinstance(opp_ranges, dict):
        _cm = {k: R.perceived_continue_range(v, board, street, size_frac,
                                             profile)
               for k, v in opp_ranges.items() if v}
        if len(_cm) == int(n_opp or 1) and all(_cm.values()):
            _cont = ('mw', _cm)
    elif opp_range:
        _cr = R.perceived_continue_range(opp_range, board, street,
                                         size_frac, profile)
        if _cr:
            _cont = ('hu', _cr)
    if _cont is None:
        return None
    _rc, _ = _decision_relative_strength(
        hero, board,
        (_cont[1] if _cont[0] == 'hu' else opp_range),
        n_opp=n_opp,
        opp_ranges=(_cont[1] if _cont[0] == 'mw' else None),
        sims=400, seed=seed)
    return perceived_rel(profile, _rc, hero, board,
                         bot.draw_strength(hero, board) if board else 0,
                         made)


def continue_range_commit_strength(hero, board, profile, pot, stack, street, rel,
                                   made, s_true, dang, commit, opp_est,
                                   opp_stack_bb, opp_eff, n_opp, opp_range,
                                   opp_ranges, rel_seed):
    """목표 커밋을 '그 사이즈를 실제로 콜할 레인지' 대비 강도로 다시 잰다.

    반환 (commit, commit_rel). 레인지 전체 rel 이 아니라 continue range 대비
    rel 이 더 낮으면 그 값으로 목표를 낮춘다(ledger L119/L-RA03 —
    '콜당했을 때도 앞서는가'). 탐색용 stackoff 는 Random(0) 을 써서 결정 RNG 를
    소비하지 않는다.
    """
    _commit = commit
    _plan_opp_est = opp_est
    _plan_opp_stack_bb = opp_stack_bb
    _opp_eff = opp_eff
    _commit_rel = rel
    _so_probe = stackoff_plan(hero, board, profile, pot, stack, street,
                              random.Random(0), commit=_commit,
                              danger=dang, opp_est=_plan_opp_est)
    _probe_sz = float((_so_probe or {}).get(street) or 0.0)
    if board and _probe_sz > 0 and _commit > 0.30 and made < 5:
        _rc = continue_range_strength(
            hero, board, profile, street, _probe_sz, opp_range, opp_ranges,
            n_opp, made, seed=rel_seed)
        if _rc is not None and _rc < rel:
            _commit_rel = _rc
            _commit = target_commit(profile, _rc, made, s_true, street,
                                    opp_stack_bb=_plan_opp_stack_bb,
                                    opp_eff=_opp_eff)
    return _commit, _commit_rel


def multiway_value_thresholds(n_opp, monster, strong):
    """다인원 보정된 밸류 문턱. 반환 (mw, v3, v2, pcz).

    넛급(monster)은 상대 수와 무관, 트립스/셋(strong)은 보정 절반(L115).
    """
    mw = max(0, n_opp - 1)
    if monster: mw = 0                      # 넛급은 상대 수와 무관하게 밸류
    elif strong: mw = min(mw, 1)            # 트립스/셋은 보정 절반만
    v3 = 0.80 + 0.06*mw          # 3스트리트 밸류 문턱
    v2 = 0.66 + 0.07*mw
    pcz = 0.50 + 0.06*mw
    return mw, v3, v2, pcz


def read_value_threshold_shift(v3, v2, pcz, rd, street):
    """상대 읽기(그 스트리트의 폴드 성향)로 밸류 문턱을 옮긴다(L115).

    잘 접는 상대: 문턱을 올린다. 안 접는 상대: 내린다. w=0 이면 그대로.
    """
    if rd['w'] > 0:
        wq = rd['w']
        # **그 스트리트의** 폴드 성향을 쓴다. 전체 평균으로 뭉개면
        # '플랍은 잘 치는데 턴에서 멈추는' 사람을 구분할 수 없다.
        sg = PS.street_gap(rd, street)
        v3 += wq * 0.55 * sg
        v2 += wq * 0.45 * sg
        pcz += wq * 0.30 * sg
    return v3, v2, pcz


def pure_bluff_evidence(profile, blk, blk_net, nut, mw, to_act_behind, rd, street):
    """순수 블러프의 근거 합성 0~: 능력 × 블로커 × 넛 우위 × 인원/뒤 좌석 × 언블로커 × 읽기.

    ledger L121 의 '근거(evidence)' 층이다. 실행 확률(동기·능력 배수)은
    pure_bluff_attempt_probability, 사이즈 위장은 bluff_mode 가 맡는다.
    """
    bluff_ok = (profile['bluff']/10.0) * _blocker_score_bluff_factor(blk) \
               * (0.75 + 0.35*max(0, nut)) \
               * (0.35 ** mw) * (0.55 ** min(to_act_behind, 3))
    # 순 효과를 곱한다. 한 장이 지우는 콤보가 3~4% 수준이라 값이 작으므로
    # 4배로 편다. 언블로커면 1 미만이 되어 블러프가 줄어든다.
    bluff_ok *= _blocker_net_bluff_factor(blk_net)
    if rd['w'] > 0:
        # 잘 접는 상대에게 블러프를 늘린다. 그 스트리트 기준으로.
        bluff_ok *= max(0.25, 1.0 + rd['w'] * 1.6 * PS.street_gap(rd, street))
    return bluff_ok


def pure_bluff_attempt_probability(bluff_ok, outs, eq, bluff_skill_03):
    """순수 블러프 계획을 고를 확률(드로우 보너스 × 0~3 스케일 bluff 숙련)."""
    return (bluff_ok * (1 + 0.9*min(1.0, outs/8.0) + 0.6*(eq>=0.30))
            * (0.45 + 0.28*bluff_skill_03))


def relative_strength_value_threshold_shift(v3, v2, rel):
    """상대 레인지 대비 강도(rel)로 밸류 문턱을 연속적으로 옮긴다(L115).

    약하면 올리고(봉쇄 강), 넛급이면 약하게 내린다(완화 약). 반환 (v3, v2).
    """
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
    return v3, v2


def deep_one_pair_vulnerability(dang, s_true, made):
    """깊은 스택 원페어의 미래 카드/스택 성장 위험 0~1. 셋+ 은 0 (ledger L118, make_plan 문맥).

    decide_response 의 넛급 레이즈 감쇠(paired_board_flush_raise_damp)와는
    다른 질문·다른 문턱이라 합치지 않는다.
    """
    _deep = max(0.0, min(1.0, (s_true - 4.0) / 10.0))
    return (_deep * max(0.0, min(1.0, (dang - 0.20) / 0.45))
            if made <= 1 else 0.0)


def middle_value_two_street_context(eq, v2, v3, dang, s_true, made, mw):
    """중간 밸류에서 2스트리트로 줄일 상황 근거 0.05~0.95 (ledger L116 make_plan 문맥)."""
    _band = max(1e-6, v3 - v2)
    _where = max(0.0, min(1.0, (eq - v2) / _band))  # 1이면 v3 직전
    _danger = max(0.0, min(1.0, dang / 0.60))
    _shallow = max(0.0, min(1.0, (3.0 - s_true) / 2.5))
    _vulnerable_deep = deep_one_pair_vulnerability(dang, s_true, made)
    _ctx_p2 = (
        0.18
        + 0.42*(1.0 - _where)
        + 0.22*_danger
        + 0.28*_vulnerable_deep
        + 0.18*_shallow
        + 0.22*min(1.0, mw))
    return max(0.05, min(0.95, _ctx_p2))


def middle_value_two_street_probability(profile, street, eq, v2, v3, dang,
                                        s_true, made, mw):
    """중간 밸류를 2스트리트로 칠 확률 = 숙련도로 섞은 (상황 근거, 성향 습관)."""
    _ctx_p2 = middle_value_two_street_context(eq, v2, v3, dang, s_true, made, mw)
    # 미숙한 사람은 상황 판단보다 성향(공격성)에 더 끌린다.
    # 숙련자는 위 context를 더 충실히 따른다.
    _habit_p2 = max(
        0.18, min(0.82, 0.52 - 0.055*(float(profile.get('aggr', 5.0))-5.0)))
    if profile.get('concepts'):
        _judge = max(0.0, min(1.0, (
            PS.sk(profile, 'stackoff')
            + PS.sk(profile, PS.street_concept('thin_value', street))
        ) / 20.0))
        _p2 = _judge*_ctx_p2 + (1.0-_judge)*_habit_p2
    else:
        _p2 = _habit_p2
    return _p2


def blockbet_probability(profile, rel, dang, oop_vs_aggr, initiative):
    """OOP 중간강도의 블락벳(가격 고정) 동기 0~0.42 (ledger L124).

    알려진 어그레서 앞(oop_vs_aggr is True)이고 이니셔티브가 없을 때만.
    어그레서가 없으면 단순 OOP lead 라 블락벳으로 분류하지 않는다.
    """
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
    return block_p


def medium_potcontrol_probability(pc, mw, merge_skill_03):
    """중간강도에서 팟컨트롤을 고를 확률(성향 pc, 인원, 머징 숙련 0~3) — L122 빈도 층."""
    return min(0.75, pc*0.8 + 0.12 + 0.18*mw) * max(0.35, 1.0 - 0.22*merge_skill_03)


def semibluff_line_probability(semibluff_skill_03):
    """드로우 8아웃+ 에서 세미블러프 계획을 고를 확률(flop/turn 계획 단계, L120)."""
    return min(0.95, 0.25 + 0.24*semibluff_skill_03)


def semibluff_barrel_sizing(opp_est, profile):
    """세미블러프 사이즈: 상대 폴드율에서 역산(위장·포기 모드 없음). 반환 (폴드율, 팟 배수)."""
    _fe = 0.5
    if isinstance(opp_est, dict) and opp_est.get('fold') is not None:
        _fe = float(opp_est['fold'])
    return _fe, barrel_size(_fe, profile, floor=0.35, cap=1.20)


def make_plan(hero, board, my_range, opp_range, profile, pot, stack, street,
              seed=None, n_opp=1, to_act_behind=0, oop_vs_aggr=None,
              initiative=True,
              opp_est=None, opp_stack_bb=None, tilt=0.0, bb_chips=None,
              oop_legacy_abs=None, opp_ranges=None, opp_ests=None,
              opp_stack_bbs=None):
    """플랍에서 라인을 확정. 상대 수와 뒤에 남은 액션자를 반영.

    opp_est — reads.perceived_profile() 결과. 진짜 프로필을 넘기면 정보 누출이다.
    opp_stack_bb — 주 상대의 유효 스택(bb). 트랩·오버벳은 스택 없이는 무의미하다.
    tilt — 내 틸트 강도 0~1. 틸트 나면 인내가 필요한 계획(트랩)이 줄고 공격이 는다.
    """
    rng = random.Random(seed)
    _field_fold = (
        select_field_opponent(profile, opp_ests, street, 'fold_constraint')
        if int(n_opp or 1) > 1 else None)
    _field_bettor = (
        select_field_opponent(profile, opp_ests, street, 'bet_probability')
        if int(n_opp or 1) > 1 else None)
    _plan_opp_est = (_field_fold.get('est') if _field_fold else opp_est)
    _trap_opp_est = (_field_bettor.get('est') if _field_bettor else _plan_opp_est)
    _stack_map = dict(opp_stack_bbs or {})
    _plan_opp_stack_bb = (
        field_effective_stack_bb(_stack_map, opp_stack_bb)
        if int(n_opp or 1) > 1 else opp_stack_bb)
    # 추정한 opp_range 를 그대로 쓴다. 고정 35% 가정으로 되돌리지 말 것 —
    # 좁혀놓은 레인지를 버리고 EV 를 판단하면 리딩이 전부 무의미해진다.
    _eq_audit = {}
    eq, _eq_fallback = _plan_eq(hero, board, opp_range, n_opp, sims=400, seed=seed,
                                opp_ranges=opp_ranges, audit=_eq_audit)
    if eq is None:
        return {'plan': 'showdown', 'plan_goal': 'showdown',
                'street_made': street, 'streets': [street],
                'eq': None, 'rel': None, 'outs': 0,
                'my_range': my_range, 'n_opp': n_opp,
                'equity_status': 'unavailable_not_negative_ev',
                'equity_unavailable': _eq_audit,
                'why': ['%s: MC equity unavailable; no positive betting EV' % street]}
    # 기록 전용. 같은 레인지·같은 인원으로 '보드를 안 돌린' 값을 같이 남긴다.
    # eq 하나만 남기면 나중에 0.535 를 보고 '지금 강한 건가, 드로우 때문인가'를
    # 구분할 수 없다. 판단에는 절대 쓰지 않는다 — 쓰려면 먼저 검증이 필요하다.
    _eq_cur_audit = {}
    eq_cur = _eq_current(hero, board, opp_range, n_opp, sims=400, seed=seed,
                         opp_ranges=opp_ranges, audit=_eq_cur_audit)
    dang = perceived_board_danger(profile, board)
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
    _blk_raw, _blk_meta = _decision_blocker_effect(
        hero, board, opp_range, street, _typ,
        n_opp=n_opp, opp_ranges=opp_ranges, seed=seed, tag='make')
    blk_net = _blk_raw * _bg
    _nut_seed = (_zlib.crc32(('%s|f7b_nut_make' % seed).encode())
                 if seed is not None else None)
    nut, _nut_meta = _decision_nut_advantage(
        my_range, board, opp_range, n_opp=n_opp, opp_ranges=opp_ranges,
        sims=1600, seed=_nut_seed)
    # 전체 에쿼티 우위. 넛 우위와 다른 축이다 —
    # 전자는 '얼마나 자주 칠까', 후자는 '얼마나 크게 칠까'를 정한다.
    _adv_joint_seed = (_zlib.crc32(('%s|f7b_range_adv_make' % seed).encode())
                       if seed is not None else None)
    adv, _adv_meta = _decision_range_advantage(
        my_range, board, opp_range, n_opp=n_opp, opp_ranges=opp_ranges,
        sims=600, seed=seed, joint_seed=_adv_joint_seed)
    # 사이즈 배분은 rel/made 를 알아야 목표를 정할 수 있어 아래로 옮겼다.
    s_true = spr(stack, pot)
    s = s_true * PS.calc_noise(profile, 'spr', rng) if profile.get('concepts') else s_true
    # SPR 인식. 예전에는 개념 2.5 미만이면 s=5.0 으로 **통째로 무시**했다.
    # 2.4 와 2.6 이 완전히 다른 사람이 되고, 개념 2.4 인 사람은 SPR 1 이든
    # 20 이든 같은 판단을 했다. 중립값 쪽으로 끌어당기는 연속 처리로 바꾼다.
    if profile.get('concepts'):
        _sa = max(0.0, min(1.0, (PS.sk(profile, 'spr') - 1.0) / 6.0))
        s = s*_sa + 5.0*(1.0 - _sa)
    pc = potcontrol_disposition(profile)

    # 절대 강도 + 상대 레인지 대비 강도
    # 내 카드가 실제로 기여한 강도만 센다 (보드만으로 성립하는 건 내 것이 아니다)
    made = bot.made_strength(hero, board) if board else 0
    _rel_seed = (_zlib.crc32(('%s|f7b_rel_make' % seed).encode())
                 if seed is not None else None)
    rel_true, _rel_meta = _decision_relative_strength(
        hero, board, opp_range, n_opp=n_opp, opp_ranges=opp_ranges,
        sims=600, seed=_rel_seed)
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
    if _plan_opp_stack_bb and bb_chips and stack > 0:
        _opp_eff = min(1.0, (float(_plan_opp_stack_bb) * float(bb_chips)) / float(stack))
    _commit = target_commit(profile, rel, made, s_true, street,
                            opp_stack_bb=_plan_opp_stack_bb,
                            opp_eff=_opp_eff)
    # 목표 커밋은 '지금 레인지 전체 대비'가 아니라 **그 사이즈를 실제로 콜할
    # 레인지 대비** 강도로 정한다. 리버 thin value 의 '콜당했을 때도 앞서는가'
    # 원칙과 같은 질문이다. 레인지 전체 rel 0.90 인 A8(877 보드)이 79% 커밋
    # → 턴 1.6 팟 오버벳을 계획했는데, 그 크기를 콜하는 레인지(7x·88·오버페어)
    # 대비로는 앞서지 않았다(audit9 HAND 16). 같은 continue-range 모델을 쓴다.
    _commit, _commit_rel = continue_range_commit_strength(
        hero, board, profile, pot, stack, street, rel, made, s_true, dang,
        _commit, _plan_opp_est, _plan_opp_stack_bb, _opp_eff, n_opp,
        opp_range, opp_ranges, _rel_seed)
    _so = stackoff_plan(hero, board, profile, pot, stack, street, rng,
                        commit=_commit, danger=dang, opp_est=_plan_opp_est)
    if isinstance(_so, dict):
        _so['commit_rel'] = round(float(_commit_rel), 3)

    mw, v3, v2, pcz = multiway_value_thresholds(n_opp, monster, strong)

    # ---------- 상대 정보가 판단의 뼈대에 들어간다 ----------
    # 정보가 없으면(초반) rd['w']=0 이라 아래 보정이 전부 0 이 되어
    # 자동으로 '내 전략대로'가 된다. 별도 분기가 필요 없다.
    # 정보가 쌓이면 밸류 문턱·블러프 빈도·함정 빈도가 같이 움직인다 —
    # 익스플로잇은 한 지점에 붙는 보정이 아니라 판단 체계 전체의 전환이다.
    rd = (_field_fold.get('read') if _field_fold else PS.read_opponent(profile, _plan_opp_est))
    v3, v2, pcz = read_value_threshold_shift(v3, v2, pcz, rd, street)
    # 블로커는 하드 게이트가 아니라 가중치. 넛 우위가 없으면 블러프 빈도 하락.
    # 0~10 개념은 /10 으로 정규화한다. 예전에는 여기만 /12 여서
    # 개념 10 인 사람도 0.83 이 최대였고 그 12 에 근거가 없었다.
    bluff_ok = pure_bluff_evidence(profile, blk, blk_net, nut, mw,
                                   to_act_behind, rd, street)
    # 트랩 판정은 trap_judgment 한 곳에서만 한다.
    # 예전에는 여기서 trap_p 를 한 번 굴리고(평균 0.27) trap_judgment 에서
    # 또 굴려서(평균 0.26) 곱해진 실효 확률이 7.8% 였다. 두 판정이 같은 것을
    # (trap 숙련도 · SPR · 보드 위험 · 인원) 중복해서 봤고, 1차는 상대 성향과
    # 체크레이즈 능력을 못 보는 열등한 판정인데 앞에 서서 74% 를 미리 잘랐다.
    # 그래서 넛급의 92% 가 value_3street 로 직행했다.
    # Same-street trap/check-raise only exists if someone can still act after us.
    # If we are closing action (e.g. IP after OOP checked), checking ends the street;
    # assigning a trap there incorrectly assumes the opponent can still bet.
    trap_ok = (to_act_behind > 0)

    # 상대 레인지에 지는 콤보가 많으면 밸류 계획 자체를 강등한다.
    # eq(랜덤/광역 레인지 대비)가 높아도 rel이 낮으면 얇은 밸류다.
    # 상대 레인지에 지는 콤보가 많으면 밸류 문턱을 올린다.
    # 예전에는 0.45 / 0.65 / 0.92 세 계단이라 rel 0.44 와 0.46 이
    # 완전히 다른 계획으로 갈렸다. 연속 곡선으로 바꾼다.
    v3, v2 = relative_strength_value_threshold_shift(v3, v2, rel)

    T = profile.get('type')
    if profile.get('concepts'):
        sk = lambda c: PS.sk(profile, c)/3.33          # 0~10 → 0~3 스케일로 환산
    else:
        sk = (lambda c: A.skill(T, c)) if T in A.ARCHETYPES else (lambda c: 2)
    why = []                                   # 의도 로그

    # 현재 쇼다운 가치는 미래 런아웃까지 포함한 eq가 아니라
    # **지금 보드에서 바로 쇼다운했을 때의 eq_current**로 본다.
    # eq는 드로우/오버카드의 미래 개선분까지 포함하므로 K-high+gutshot 같은
    # 미완성 핸드를 '쇼다운 가치 있음'으로 잘못 분류할 수 있다.
    _sd_eq = eq_cur if eq_cur is not None else eq

    if eq >= v3:
        # 트랩은 '확률로 고르는 것'이 아니라 상대를 보고 내리는 판단이다.
        # 개념을 가졌는가(sk)는 사람마다 다르지만, 그 도구를 지금 쓸지는
        # 상대가 벳해줄 사람인가 · 스택이 남았는가 · 보드가 안전한가로 결정된다.
        # 패시브한 상대에게 체크하면 무료 카드만 주는 최악의 수다.
        # 내가 공격자면 상대는 '체크받으면 칠지'(프로브), 아니면 상대가 공격자다.
        p_trap, trap_why = trap_judgment(profile, _trap_opp_est, s, dang, mw,
                                         street, tilt, sk,
                                         opp_role=('probe' if initiative else 'aggressor'))
        # Preserve the historical RNG consumption even when trap is structurally
        # impossible, so the downstream aggression roll is not shifted by this gate.
        _trap_roll = rng.random()
        if trap_ok and _trap_roll < p_trap:
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
        # 중간 밸류는 "실력이 높으면 무조건 3스트리트"가 아니다.
        # 사람은 현재 equity가 밸류 구간 어디쯤인지, 보드 취약성, SPR,
        # 다인원을 함께 보고 몇 거리까지 갈지 정한다.
        #
        # 기존 식은 max-skill에서 stackoff(×0.45)와 thin-value(×0.55)가
        # 위험 신호를 약 75% 지웠다. 실제 플레이에서 SPR 20의 66/743가
        # pot-pot-pot value_3street가 된 원인이다. 숙련도는 위험을 지우는
        # 방향이 아니라 **상황 기반 판단을 더 정확히 따르는 정도**로 쓴다.
        _p2 = middle_value_two_street_probability(
            profile, street, eq, v2, v3, dang, s_true, made, mw)

        if rng.random() < max(0.05, min(0.95, _p2)):
            plan = 'value_2street'
            why.append(
                '중간 밸류(eq %.2f, rel %.2f) + 위험 %.2f/SPR %.1f/다인원 %d'
                ' → 2스트리트(p2 %.2f)'
                % (eq, rel, dang, s_true, mw, _p2))
        else:
            plan = 'value_3street'
            why.append(
                '중간 밸류이나 3스트리트 유지(eq %.2f, rel %.2f, p2 %.2f)'
                % (eq, rel, _p2))
    elif eq >= pcz:
        # 블락벳: OOP + 이니셔티브 없음 + 쇼다운은 되는 중간 강도
        block_p = blockbet_probability(profile, rel, dang, oop_vs_aggr, initiative)
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
            # 의미: 중간 강도를 얇은 밸류로 칠 줄 아는가. 플랍은 thin_value_flop
            # (기존 프로필은 range_merge fallback). 보드 변경으로 턴/리버에 계획을
            # 다시 세울 때는 phase 1 에서 기존 range_merge 를 그대로 쓴다(행동 보존,
            # CONCEPT_SPLIT_TODO 3 참고).
            _mg = sk('thin_value_flop' if street == 'flop' else 'range_merge')   # 0~3
            _pc_p = medium_potcontrol_probability(pc, mw, _mg)
            if sk('potcontrol') >= 1 and rng.random() < _pc_p:
                plan = 'pot_control'; why.append('중간강도(eq %.2f, rel %.2f) → 팟 컨트롤' % (eq, rel))
            elif rel >= max(0.28, 0.52 - 0.080*_mg) and made >= 1:
                plan = 'value_2street'
                why.append('중간강도(eq %.2f, rel %.2f, 머징 %.1f) → 얇은 밸류' % (eq, rel, _mg))
            else:
                # 폴백이 밸류면 안 된다. rel 0.0 에 made 0 인 완전 미스가
                # '얇은 밸류'로 분류돼, 계획은 밸류인데 실행은 체크하는
                # 모순이 생겼다 (decide_aggression 이 rel 을 보므로).
                # 쇼다운 가치 정의는 아래 else 분기와 같아야 한다
                # (made 또는 에쿼티). 예전에는 made 만 봐서 eq 0.59·rel 0.68 인
                # A-K 하이가 '상대레인지 열세 → 포기'로 분류됐다(audit9 HAND 16).
                _sd_here = has_showdown_value(made, eq, mw)
                plan = 'showdown' if _sd_here else 'giveup'
                why.append('중간강도이나 얇은 밸류 조건 미달(rel %.2f, made %d) → %s'
                           % (rel, made, plan))
    elif outs >= 8 and to_act_behind <= 1 and sk('semibluff') >= 0.4 \
         and rng.random() < semibluff_line_probability(sk('semibluff')):
        plan = 'semibluff'; why.append('드로우 %d아웃 → 세미블러프' % outs)
        # 세미블러프는 이기는 경로가 둘(접거나, 맞추거나)이라 순수 블러프와
        # 다르다. **위장(merged)은 필요가 적고** — 콜받아도 손해가 아니므로
        # 밸류인 척할 이유가 약하다 — **포기(probe)는 방향이 반대다** — 미스해도
        # 아웃츠가 남아 있으면 계속 갈 이유가 있다.
        # 그래서 폴드율 역산(barrel)만 적용한다.
        _fe, _bluff_mul = semibluff_barrel_sizing(_plan_opp_est, profile)
        _bluff_mode = 'barrel'
        why.append('세미블러프 사이즈: 폴드율 %.0f%% 역산 → 팟의 %.0f%%'
                   % (_fe*100, _bluff_mul*100))
    # **쇼다운 가치가 있으면 블러프 계획으로 가지 않는다.**
    # 예전에는 이 분기가 made 를 확인하지 않아, 세컨페어(made 1, eq 0.38)가
    # '쇼다운 가치 없음'이라는 이유로 2스트리트 블러프가 됐다.
    # 아래 else 에만 has_sd 검사가 있어서 메이드 핸드가 먼저 새어나갔다.
    #
    # 메이드 원페어는 약하더라도 블러프 후보로 재분류하지 않는다.
    # 상대 레인지 대비 약하다는 사실(rel)은 콜/폴드와 얇은 밸류 판단에 쓰지,
    # 이미 이기는 worse made hand를 접게 만드는 '블러프' 근거가 아니다.
    elif (_sd_eq < 0.42 and sk('bluff') >= 1
          and made == 0
          and rng.random() < pure_bluff_attempt_probability(
              bluff_ok, outs, eq, sk('bluff'))):
        plan = ('river_bluff' if street == 'river' else 'bluff_2street')
        why.append(
            ('리버: 쇼다운 가치 없음 + 블로커 %.2f/넛우위 %.2f → 리버 블러프 계획'
             if street == 'river'
             else '쇼다운 가치 없음 + 블로커 %.2f/넛우위 %.2f → 블러프 계획')
            % (blk, nut))
        # 큰 전략(블러프) 아래 세부 전략을 고른다. 사이즈는 여기서 갈린다.
        _bm, _bmul, _bwhy = bluff_mode(profile, rel, dang, nut, _plan_opp_est,
                                       street, s, rng)
        _bluff_mode, _bluff_mul = _bm, _bmul
        why.append('블러프 세부: %s — %s' % (_bm, _bwhy))
    else:
        # giveup은 '쇼다운 가치 없음'일 때만. 메이드 핸드는 팟컨트롤로 간다.
        has_sd = has_showdown_value(made, _sd_eq, mw)
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
            'eq': round(eq,3), 'danger': round(dang,2),
            'danger_raw': round(bot.board_danger(board), 2), 'outs': outs,
            'blocker': round(blk,2), 'blocker_net': round(blk_net,3),
            'blocker_net_raw': float(_blk_raw),
            'blocker_source': _blk_meta.get('source'),
            'nut_adv': round(nut,2), 'nut_adv_raw': float(nut),
            'nut_adv_union': (round(float(_nut_meta.get('union')), 6)
                              if _nut_meta.get('union') is not None else None),
            'nut_adv_joint': (round(float(_nut_meta.get('joint')), 6)
                              if _nut_meta.get('joint') is not None else None),
            'nut_adv_source': _nut_meta.get('source'),
            'range_adv': round(adv,2),
            'range_adv_union': (round(float(_adv_meta.get('union')), 6)
                                if _adv_meta.get('union') is not None else None),
            'range_adv_joint': (round(float(_adv_meta.get('joint')), 6)
                                if _adv_meta.get('joint') is not None else None),
            'range_adv_source': _adv_meta.get('source'),
            'stackoff': dict(_so, _blk_net=round(blk_net, 3)) if isinstance(_so, dict) else _so,
            'bluff_mode': _bluff_mode, 'bluff_mul': round(_bluff_mul, 2),
            'plan_goal': _goal or plan, 'plan_mode': _mode, 'spr': round(s,1), 'pc': round(pc,2),
            'n_opp': n_opp, 'behind': to_act_behind, 'rel': round(rel,2), 'made': made,
            'rel_true': round(rel_true, 6),
            'rel_union': round(float(_rel_meta.get('union')), 6)
                         if _rel_meta.get('union') is not None else None,
            'rel_joint': round(float(_rel_meta.get('joint')), 6)
                         if _rel_meta.get('joint') is not None else None,
            'rel_source': _rel_meta.get('source'),
            # ---- 기록 전용 provenance. 판단에 쓰지 않는다 ----
            # eq 가 '현재 강도'인지 '미래 개선분'인지 나중에 복원하기 위한 값들.
            # outs 는 calc_noise 를 거친 체감값이라 물리값(outs_true)을 따로 남긴다.
            'eq_current': (None if eq_cur is None else round(eq_cur, 3)),
            'eq_delta': (None if eq_cur is None else round(eq - eq_cur, 3)),
            'eq_sims': 400, 'eq_seed': seed,
            'outs_true': outs_true,
            'my_range_n': len(my_range) if my_range else 0,
            'my_range_mass': (R.range_mass(my_range) if my_range else 0.0),
            'my_range_sig': _range_sig(my_range),
            'opp_range_n': len(opp_range) if opp_range else 0,
            'opp_range_mass': (R.range_mass(opp_range) if opp_range else 0.0),
            'opp_range_sig': _range_sig(opp_range),
            'opp_ranges_n': ({str(k): len(v) for k, v in opp_ranges.items()}
                             if isinstance(opp_ranges, dict) else None),
            'opp_ranges_mass': ({
                str(k): R.range_mass(v) for k, v in opp_ranges.items()}
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
            'opp_est': _plan_opp_est, 'opp_stack_bb': _plan_opp_stack_bb,
            'opp_ests': dict(opp_ests or {}), 'opp_stack_bbs': dict(opp_stack_bbs or {}),
            'field_fold_seat': (_field_fold.get('seat') if _field_fold else None),
            'field_bettor_seat': (_field_bettor.get('seat') if _field_bettor else None),
            'protect': round(min(1.0, dang*(1+0.5*mw)), 2)}
    if _eq_fallback:
        st['eq_field_fallback'] = True
    if eq_cur is None:
        st['eq_current_sampling'] = dict(_eq_cur_audit)
    # 의도는 파이프라인 끝(session)에서 최종 계획 기준으로 붙인다.
    return st


# ---------- 레인지 주장 기준선 (FLOP_CLAIM_BASELINE.md, 2026-10-06) ----------
# 숙련자의 c벳 빈도는 '자기 레인지에 실제로 있는 주장 가능한 핸드 비율'에 수렴한다(층 A).
# 예전에는 range_adv 가 지속벳 빈도를 몇 % 흔드는 곱셈항일 뿐이라 보드별 빈도가
# 레인지 구성을 따라가지 않았다(봇 A·K 하이 62% vs 목표 80%+, 숙련자일수록 더 낮음).
# 오프너 HU IP 플랍, 체크를 받은 상황에서만 쓴다.
#   V      = 내 레인지 중 작은 벳 밸류(넛급·강·중) 비율
#   목표 T = max(60%, 2V)  — 최저선 60%(작업용 작은 벳), 플랍 밸류:블러프 1:1
#   밸류 핸드는 거의 항상, 나머지는 (T-V)/(1-V) 로 채운다.
# 숙련(cbet_flop)이 낮으면 기준선을 거의 안 따른다(w→0) — 초보는 층 B(내 핸드)만 본다.
RANGE_CLAIM_ANCHOR = True
_CLAIM_FLOOR = 0.60
_CLAIM_VALUE_P = 0.95
_CLAIM_CACHE = {}
_CLAIM_RV = {r: i for i, r in enumerate('23456789TJQKA', 2)}


def claim_value_hand(hole, board):
    """작은 벳으로 밸류를 주장할 수 있는 핸드인가(넛급·강·중). 플랍 3장 기준.

    넛급: 투페어(보드 페어 제외)·셋/트립스·스트레이트+. 강: 오버페어·탑페어 좋은 키커.
    중: 탑페어 약한 키커·세컨페어·보드 최저 카드보다 높은 포켓페어.
    """
    cat = bot.eval7(list(hole) + list(board))[0]
    rv = _CLAIM_RV
    bcnt = {}
    for c in board:
        bcnt[rv[c[0]]] = bcnt.get(rv[c[0]], 0) + 1
    paired = max(bcnt.values()) >= 2
    if cat >= 3 or (cat == 2 and not paired):
        return True
    hr = [rv[c[0]] for c in hole]
    unpaired = sorted((r for r, n in bcnt.items() if n == 1), reverse=True) \
        or sorted(bcnt, reverse=True)
    top = max(bcnt)
    if hr[0] == hr[1]:
        return hr[0] > min(unpaired)
    hits = [r for r in hr if r in unpaired]
    if not hits:
        return False
    h = max(hits)
    return h == unpaired[0] or (len(unpaired) >= 3 and h == unpaired[1])


def range_claim_value_share(my_range, board):
    key = (_range_sig(my_range), tuple(board))
    v = _CLAIM_CACHE.get(key)
    if v is not None:
        return v
    dead = set(board)
    tot = val = 0.0
    for c, w in R.range_items(my_range):
        if dead & set(c):
            continue
        tot += w
        if claim_value_hand(c, board):
            val += w
    v = (val / tot) if tot > 0 else 0.0
    if len(_CLAIM_CACHE) > 4096:
        _CLAIM_CACHE.clear()
    _CLAIM_CACHE[key] = v
    return v


# OOP 오프너(먼저 액션): 같은 레인지 기준에 포지션 숙련만큼 할인(플랍 c벳 포지션 수정 B 와
# 같은 계수, 숙련 10 에서 ×0.76). 체크 레인지 보호를 위해 밸류도 85% 만 친다.
# 사용자 원칙: 포지션이 없으면 이점이 없다(상대가 뒤에서 레이즈/플로트, 에퀴티 실현이 어렵다).
RANGE_CLAIM_ANCHOR_OOP = True
_CLAIM_VALUE_P_OOP = 0.85


def range_claim_anchor(profile, hero, board, my_range, p_old, oop=False):
    """레인지 기준선 쪽으로 당긴 벳 확률. 반환 None 이면 적용 안 함."""
    V = range_claim_value_share(my_range, board)
    if V <= 0.0:
        return None
    T = min(0.95, max(_CLAIM_FLOOR, 2.0 * V))
    vp = _CLAIM_VALUE_P
    if oop:
        T *= 1.0 - 0.24 * (PS.sk(profile, 'positional') / 10.0)
        vp = _CLAIM_VALUE_P_OOP
    is_val = claim_value_hand(hero, board)
    fill = max(0.0, min(1.0, (T - V*vp) / max(1e-6, 1.0 - V)))
    tgt = vp if is_val else fill
    # 기질은 기준선 위에서 조금만 흔든다(같은 숙련이라도 사람마다 다르게).
    tgt = max(0.0, min(0.97, tgt + 0.03*(PS.temper(profile, 'aggression', 5.0) - 5.0)))
    w = 0.9 * max(0.0, min(1.0, (PS.sk(profile, 'cbet_flop') - 2.0) / 7.0))
    p = p_old + w * (tgt - p_old)
    return {'p': round(max(0.0, min(0.97, p)), 4), 'p_old': round(p_old, 4),
            'oop': bool(oop),
            'target': round(T, 4), 'V': round(V, 4), 'value': bool(is_val),
            'hand_target': round(tgt, 4), 'w': round(w, 3)}


# ---------- 리버 블러프 기준선 v2 (FLOP_CLAIM_BASELINE.md 10절, 2026-10-07) ----------
# 주장(이야기)마다 진짜:가짜 비율을 맞춘다. 그 비율은 벳 사이즈가 정한다 —
# 상대가 콜/폴드에 무차별해지는 가짜 비율 = s/(1+2s)
#   1/3팟 20%(8:2), 팟 33%(7:3, 사용자 기준), 1.5배 38%(6:4, '넓힐 수도').
# 리버가 새 오버카드(예 Q84 2 → K)면 이야기가 둘이다.
#   새 카드 주장(K): 진짜 = 그 랭크를 가진 손. 크게(팟, 스택이 모자라면 올인) 폴라.
#   기존 탑 주장(Q): 진짜 = 기존 탑 페어 좋은 키커(J+)·그 이상. 작게(1/3), 리스크 적음.
# 오버카드가 아니면 이야기 하나(리버 밸류 전체), 2/3팟.
# 가짜 후보(메이드 없는 손)에 이야기별 가짜 수를 나눠 준다. 블로커 순효과가 +면
# 큰 이야기, 아니면 작은 이야기로 간다. 블러프 리스크(스택 대비 벳)가 크면
# 신중한 성향(규율 높고 도박성 낮음)은 덜 친다. 쇼다운 계획은 건드리지 않는다(베타 A #3).
RIVER_BLUFF_ANCHOR = True
_RB_CACHE = {}
_RB_BIG, _RB_SMALL, _RB_SINGLE = 1.0, 0.33, 0.67


def bluff_share_for_size(s):
    """사이즈 s(팟 대비)에서 벳 레인지 안 가짜 비율 s/(1+2s)."""
    s = max(0.05, float(s))
    return s / (1.0 + 2.0*s)


def river_value_hand(hole, board):
    """리버에서 벳 레인지의 밸류로 셀 손: 홀카드가 기여한 투페어+, 오버페어,
    탑페어 좋은 키커(T+)."""
    rv = _CLAIM_RV
    cat = bot.eval7(list(hole) + list(board))[0]
    bcat = bot.eval7(list(board))[0]
    if cat >= 2 and cat > bcat:
        return True
    hr = sorted((rv[c[0]] for c in hole), reverse=True)
    br = sorted({rv[c[0]] for c in board}, reverse=True)
    if hr[0] == hr[1]:
        return hr[0] > br[0]
    if br[0] in hr:
        k = hr[1] if hr[0] == br[0] else hr[0]
        return k >= 10
    return False


def _line_keeps(c, board_now, small):
    """내가 이 보드에서 벳했다면 그 벳 레인지에 들어갈 손인가(자기 라인 근사).
    탑페어+·오버페어, 강한 드로우(아웃 8+), 오버카드 낀 드로우(아웃 4+).
    작은 벳(플랍 1/3)이면 오버카드·약한 페어·약한 드로우까지 넓게."""
    rv = _CLAIM_RV
    h = list(c)
    cat = bot.eval7(h + list(board_now))[0]
    top = max(rv[x[0]] for x in board_now)
    hr = sorted((rv[x[0]] for x in h), reverse=True)
    if cat >= 2 or (hr[0] == hr[1] and hr[0] > top) or top in hr:
        return True
    outs = bot.draw_strength(h, list(board_now))
    if outs >= 8:
        return True
    if small:
        return outs >= 3 or hr[0] > top or bot.made_strength(h, list(board_now)) >= 1
    return outs >= 4 and hr[0] > top


def river_story_shares(my_range, board, bet_streets=()):
    """내 레인지의 리버 이야기별 진짜 비율과 미스(메이드 없음) 비율.
    bet_streets 가 있으면 그 스트리트에 벳한 자기 라인으로 레인지를 좁혀 센다."""
    bet_streets = tuple(s for s in ('flop', 'turn') if s in (bet_streets or ()))
    key = (_range_sig(my_range), tuple(board), bet_streets)
    v = _RB_CACHE.get(key)
    if v is not None:
        return v
    rv = _CLAIM_RV
    new_r = rv[board[4][0]]
    prev_top = max(rv[c[0]] for c in board[:4])
    over = new_r > prev_top
    dead = set(board)
    tot = new = top = val = air = 0.0
    for c, w in R.range_items(my_range):
        if dead & set(c):
            continue
        if 'flop' in bet_streets and not _line_keeps(c, board[:3], True):
            continue
        if 'turn' in bet_streets and not _line_keeps(c, board[:4], False):
            continue
        tot += w
        hr = [rv[x[0]] for x in c]
        if bot.made_strength(list(c), board) < 1:
            air += w
            continue
        if river_value_hand(c, board):
            val += w
        if over:
            if new_r in hr:
                new += w
            elif prev_top in hr:
                k = hr[1] if hr[0] == prev_top else hr[0]
                cat = bot.eval7(list(c) + list(board))[0]
                if k >= 11 or k == prev_top or cat >= 2:
                    top += w
    v = {'over': over, 'new': new / tot if tot else 0.0,
         'top': top / tot if tot else 0.0, 'value': val / tot if tot else 0.0,
         'air': air / tot if tot else 0.0}
    if len(_RB_CACHE) > 4096:
        _RB_CACHE.clear()
    _RB_CACHE[key] = v
    return v


def river_bluff_anchor(profile, hero, board, my_range, st, p_old, pot=None, stack=None):
    """메이드 없는 손의 리버 블러프 확률·사이즈를 이야기별 기준선으로 정한다."""
    if bot.made_strength(list(hero), board) >= 1:
        return None
    sh = river_story_shares(my_range, board, (st or {}).get('bet_streets') or ())
    A = sh['air']
    if A <= 0.0:
        return None
    _spr = (float(stack)/float(pot)) if (pot and stack is not None and pot > 0) else 99.0
    big = min(_RB_BIG, _spr) if _spr > 0 else _RB_BIG     # 스택이 팟보다 작으면 올인
    blk = float(st.get('blocker_net') or 0.0)
    if sh['over']:
        f_big = sh['new'] * bluff_share_for_size(big) / (1.0 - bluff_share_for_size(big))
        f_small = sh['top'] * bluff_share_for_size(_RB_SMALL) / (1.0 - bluff_share_for_size(_RB_SMALL))
        if blk >= 0.0 or f_small <= 0.0:
            story, size, fake = 'new', big, f_big
            share = f_big / max(1e-9, f_big + f_small)
        else:
            story, size, fake = 'top', _RB_SMALL, f_small
            share = f_small / max(1e-9, f_big + f_small)
        total = f_big + f_small
    else:
        size = min(_RB_SINGLE, _spr) if _spr > 0 else _RB_SINGLE
        total = sh['value'] * bluff_share_for_size(size) / (1.0 - bluff_share_for_size(size))
        story, fake, share = 'single', total, 1.0
    if total <= 0.0:
        return None
    base = min(1.0, total / A)
    f = max(0.3, min(1.8, 1.0 + 10.0*blk))
    if 'A' in (hero[0][0], hero[1][0]):
        f *= 0.6                      # A 하이는 미스한 드로우를 이기는 쇼다운 가치
    tgt = base * f
    # 블러프 리스크: 실패 시 잃는 칩 / 남은 스택. 신중한 성향일수록 크게 깎는다.
    _risk = max(0.0, min(1.0, size / max(1e-6, _spr))) if _spr < 99 else 0.0
    _caution = max(0.0, min(1.0, 0.5 + (PS.temper(profile, 'discipline', 5.0)
                                         - PS.temper(profile, 'gamble', 5.0))/10.0))
    tgt *= 1.0 - 0.6*_risk*_caution
    tgt = max(0.0, min(0.95, tgt))
    _sk = 0.5*(PS.sk(profile, 'barrel_river') + PS.sk(profile, 'bluff'))
    w = 0.9 * max(0.0, min(1.0, (_sk - 2.0) / 7.0))
    p = p_old + w * (tgt - p_old)
    return {'p': round(max(0.0, min(0.95, p)), 4), 'p_old': round(p_old, 4),
            'story': story, 'size': round(size, 3), 'fake': round(total, 4),
            'air': round(A, 4), 'base': round(base, 4), 'blk_net': round(blk, 4),
            'f': round(f, 3), 'risk': round(_risk, 3), 'caution': round(_caution, 3),
            'w': round(w, 3), 'new': round(sh['new'], 4), 'top': round(sh['top'], 4)}


def attach_intent(st, hero, board, my_range, opp_range, profile, pot, stack,
                  street, rng, n_opp, to_act_behind, oop, initiative, opp_est=None,
                  oop_vs_aggr=None, oop_legacy_abs=None, opp_ranges=None, tilt=0.0):
    """계획에 이 스트리트의 의도를 붙인다. 판단 층의 마지막 단계."""
    plan = st.get('plan')
    rel = st.get('rel', 0.5)
    p_aggr, why_a = decide_aggression(profile, board, street, plan, rel, n_opp,
                                      oop, initiative, to_act_behind, rng,
                                      opp_est, st.get('outs', 0), plan_state=st,
                                      oop_vs_aggr=oop_vs_aggr,
                                      oop_legacy_abs=oop_legacy_abs,
                                      spr_now=(float(stack)/max(1.0, float(pot))
                                               if pot else None),
                                      tilt=tilt)
    _anc_ip = (not oop and int(to_act_behind or 0) == 0)
    _anc_oop = (RANGE_CLAIM_ANCHOR_OOP and oop and int(to_act_behind or 0) == 1)
    if (RANGE_CLAIM_ANCHOR and street == 'flop' and len(board) == 3
            and initiative and (_anc_ip or _anc_oop) and int(n_opp or 1) == 1
            and profile.get('concepts')
            and plan != 'trap' and my_range):
        _anc = range_claim_anchor(profile, hero, board, my_range, p_aggr,
                                  oop=bool(_anc_oop))
        if _anc is not None:
            _trace(st, street, 'range_claim', **_anc)
            if _anc['p'] > p_aggr + 1e-9 and plan in ('giveup', 'showdown') \
                    and not why_a.startswith('DEVIATE:'):
                why_a = 'DEVIATE:' + why_a
            p_aggr = _anc['p']
            why_a = '%s | 레인지 주장 기준선 %.0f%%(V %.0f%%, w %.2f)' % (
                why_a, _anc['target']*100, _anc['V']*100, _anc['w'])
    _rb_size = None
    if (RIVER_BLUFF_ANCHOR and street == 'river' and len(board) == 5
            and initiative and int(n_opp or 1) == 1
            and int(to_act_behind or 0) == 0 and profile.get('concepts')
            and plan in ('giveup', 'bluff_2street', 'river_bluff') and my_range):
        _rb = river_bluff_anchor(profile, hero, board, my_range, st, p_aggr,
                                 pot=pot, stack=stack)
        if _rb is not None:
            _trace(st, street, 'river_bluff_claim', **_rb)
            p_aggr = _rb['p']
            _rb_size = _rb['size']
            if not why_a.startswith('DEVIATE:') and plan != 'river_bluff':
                why_a = 'DEVIATE:' + why_a
            why_a = '%s | 리버 블러프 기준선 %.0f%%(%s 주장 %.2f팟, 가짜 %.0f%%/미스 %.0f%%, blk %+.3f, w %.2f)' % (
                why_a, _rb['p']*100, _rb['story'], _rb['size'],
                _rb['fake']*100, _rb['air']*100, _rb['blk_net'], _rb['w'])
    _roll = rng.random()
    why_a += ' | 최종 실행 확률 %.2f%%' % (p_aggr * 100.0)
    _trace(st, street, 'aggression', p=round(p_aggr, 3), roll=round(_roll, 3),
           why=why_a, plan=plan, rel=round(rel, 3))
    if _roll < p_aggr:
        size = decide_size(profile, hero, board, street, plan, rel,
                           opp_range, my_range, pot, stack, rng, opp_est,
                           st.get('nut_adv_raw', st.get('nut_adv', 0.0)),
                           deviating=why_a.startswith('DEVIATE:'),
                           stackoff=st.get('stackoff'), plan_state=st,
                           n_opp=n_opp, opp_ranges=opp_ranges)
        if _rb_size:
            # 블러프 사이즈는 이야기가 정한다(새 오버카드 = 크게 폴라, 기존 탑 = 작게).
            size = _rb_size
        if size > 0:
            st = set_intent(st, street, mk_intent('bet', size, why_a))
            # 계획과 반대되는 의도는 이탈로 남긴다. 기록이 없으면
            # 나중에 '왜 이렇게 쳤는지'를 사람이 눈으로 찾아야 한다.
            if why_a.startswith('DEVIATE:'):
                st = record_deviation(st, street, 'bet', plan, why_a[8:])
        else:
            _trace(st, street, 'size_veto', act='check', size=0.0,
                   why='베팅 의향 추첨 통과 후 사이즈 판단이 0 → 최종 체크',
                   plan=plan)
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

def perceived_facing_price(profile, opp_est, board, street, sz_true, tocall):
    """마주한 벳의 사실(FACT)을 이 사람이 인지한 값(PERCEPTION)으로 옮긴다.

    입력 sz_true / tocall 은 공개 사실이며 바뀌지 않는다. 반환:
      read      read_opponent(관찰 기반 상대 읽기) 또는 None
      sz_seen   상대 기준 정규화(opp_size_norm, 읽기) → 정의역 밖 인지(size_read, 능력)
      tocall_seen  인지된 사이즈 비율만큼 옮긴 콜 금액(callers 칩은 재해석하지 않음)
    개념 벡터가 없거나 프리플랍이면 사실 그대로다(ledger L169). RNG 없음.
    """
    read = None
    sz_seen = sz_true
    tocall_seen = float(tocall)
    if profile.get('concepts') and board:
        read = PS.read_opponent(profile, opp_est) if opp_est else None
        sz_seen = PS.size_read(profile, PS.opp_size_norm(read, sz_true, street))
        # 사이즈 오독은 실제 call price에 비례 적용한다.
        # callers의 칩을 상대 bet으로 재해석하지 않는다.
        if sz_true > 1e-9:
            tocall_seen = float(tocall) * (sz_seen / sz_true)
    return read, sz_seen, tocall_seen


def perceived_call_price_share(tocall, tocall_seen, pot_before_bet, bf,
                               objective_breakeven=None):
    """가격 층: 인지된 콜 금액으로 계산한 필요 승률(BF 포함). 반환 (need, layer_need).

    calldown_need 의 '가격' 질문만 맡는다(ledger L145). 계산 오차·뒤 좌석
    위험·개인 콜 편향(주관 문턱)은 calldown_need 가 이어서 얹는다.
    지역 이름 need_true 는 역사적 이름이다 — 값은 '사실 가격'이 아니라
    size_read 오독이 반영된 인지 가격이다(tocall_seen == tocall 이면 사실 가격과 같다).
    """
    _p0 = pot_before_bet
    _tocall_seen = tocall_seen
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
    return need_true, call_need_true


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

    층(ledger L145): 사실(tocall, facing_size_frac) → 인지(perceived_facing_price)
    → 가격(perceived_call_price_share) → 주관 문턱(calc_noise, 뒤 좌석 위험,
    call_bias). 인자 `read` 는 현재 쓰이지 않는다(호환용; 상대 읽기는
    opp_est 에서 read_opponent 로 다시 만든다).
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
    _rdz, _sz_seen, _tocall_seen = perceived_facing_price(
        profile, opp_est, board, street, _sz_true, tocall)
    # pot 은 pot_live 다 — 상대가 방금 낸 벳은 들어 있고 **내 콜은 아직
    # 아니다**(session.py:449 의 pot_now + sum(r2.contrib)). 콜하면 내 칩도
    # 팟에 들어가므로 분모에 내 콜을 더해야 한다.
    #   필요승률 = 벳 / (벳전팟 + 상대벳 + 내콜) = sz/(1+2sz)
    # _sz_seen == _sz_true 일 때 (tocall*bf)/(pot + tocall) 과 **비트까지 같다**
    # (정수 칩이라 (pot-tocall) + 2*tocall 이 pot + tocall 과 정확히 일치한다).
    # 50만 조합 대조에서 불일치 0건. 비발동군 무변화 관문이 이것에 걸려 있다.
    need_true, call_need_true = perceived_call_price_share(
        tocall, _tocall_seen, _p0, bf, objective_breakeven)

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
        # 남은 팟 지분 기준으로 비례 가산한다(canonical producer: icm).
        need += _ICM.players_behind_required_equity_premium(
            need_true, to_act_behind)
        if call_need is not None:
            call_need += _ICM.players_behind_required_equity_premium(
                call_need_true, to_act_behind)
    need = max(0.01, min(0.97, need))
    if call_need is not None:
        call_need = max(0.01, min(0.97, call_need))
    # line bluff/value 판단은 이미 opponent combo range 구성에 반영된다.
    # 여기서 같은 정보를 need에 다시 더하거나 빼면 동일 증거를 두 번 소비한다.
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
        # 상대 bluff 성향 역시 perceived opponent range에 이미 들어간다.
        # call threshold에는 다시 넣지 않는다.
        need = max(0.03, min(0.95, need))
        if call_need is not None:
            call_need = max(0.03, min(0.95, call_need))
    need = max(0.03, min(0.95, need))
    if call_need is None:
        return need
    return need, max(0.03, min(0.95, call_need))

def _nonvalue_raise_ev_gate(profile, hero, board, street, opp_range,
                            opp_ranges, n_opp, pot, tocall, stack,
                            hero_contrib, response_context,
                            mult=None, target=None):
    """Veto a bluff/semi-bluff response raise that is negative even optimistically.

    Uses the already-perceived opponent range.  The opponent's fold share comes
    from the same continue-range heuristic used elsewhere, at the *actual price*
    created by our candidate raise.

    For non-all-in future streets this deliberately treats every continue as a
    call followed by immediate showdown.  That is optimistic for the raiser:
    future re-raises / imperfect realization can only make many weak raises
    worse.  Therefore a negative result is a safe structural veto, not a new
    frequency knob.

    적용 범위(ledger L146): 상대 한 명(facing seat, 없으면 opp_range)의 콜/폴드만
    본다. 멀티웨이 응답 트리와 사이드팟 레이즈 분기는 다루지 않으며(LATER),
    레인지나 MC 근거를 모르면 공격 허용을 승인하지 않는다(known=False).
    """
    ctx = dict(response_context or {})
    fs = ctx.get('facing_seat')
    pool = None
    if isinstance(opp_ranges, dict) and fs in opp_ranges:
        pool = opp_ranges.get(fs)
    if not pool:
        pool = opp_range
    if not pool or not board:
        return {'known': False, 'allow': False, 'ev': None,
                'equity_status': 'unavailable_not_negative_ev',
                'why': 'opponent range unavailable'}

    hc = max(0.0, float(hero_contrib or 0.0))
    actor_cap = hc + max(0.0, float(stack or 0.0))
    if target is None:
        if mult is None:
            return {'known': False, 'allow': False, 'ev': None,
                    'equity_status': 'unavailable_not_negative_ev',
                    'why': 'raise target unavailable'}
        base = max(0.0, float(pot + 2*tocall) * float(mult))
        target = hc + base
    cand = min(actor_cap, max(hc + float(tocall or 0.0), float(target)))
    hero_inc = max(0.0, cand - hc)
    call_target = hc + max(0.0, float(tocall or 0.0))
    if cand <= call_target:
        return {
            'known': True, 'allow': False, 'ev': None,
            'candidate_target': round(cand, 3),
            'why': 'candidate raise does not exceed call target',
        }

    opp_contrib = ctx.get('facing_contrib')
    if opp_contrib is None:
        opp_contrib = ctx.get('facing_target')
    if opp_contrib is None:
        return {'known': False, 'allow': False, 'ev': None,
                'equity_status': 'unavailable_not_negative_ev',
                'why': 'facing contribution unavailable'}
    opp_contrib = max(0.0, float(opp_contrib or 0.0))

    opp_stack = ctx.get('facing_stack')
    opp_cap = (
        opp_contrib + max(0.0, float(opp_stack or 0.0))
        if opp_stack is not None else cand)
    opp_call_target = min(cand, opp_cap)
    opp_call = max(0.0, opp_call_target - opp_contrib)

    pot_after_raise = float(pot or 0.0) + hero_inc
    price_frac = opp_call / max(1.0, pot_after_raise)
    cont = R.perceived_continue_range(
        pool, board, street, price_frac, profile=profile)
    # Hand-conditioned fold share (L-S9-02a): the continue slice is taken on
    # the full perceived range (opponent strategy), but the probability that
    # *this* holding gets a fold counts only combos the opponent can hold.
    _dead = set(hero) | set(board or [])
    base_mass = float(R.range_mass_live(pool, _dead) or 0.0)
    cont_mass = float(R.range_mass_live(cont, _dead) or 0.0)
    if base_mass <= 0 or cont_mass <= 0:
        return {'known': False, 'allow': False, 'ev': None,
                'equity_status': 'unavailable_not_negative_ev',
                'why': 'range mass unavailable'}

    fold_p = max(0.0, min(1.0, 1.0 - cont_mass/base_mass))
    _mc_audit = {}
    eq_cont = bot.equity_vs_combos(hero, board, [cont], sims=400,
                                   audit=_mc_audit)
    if eq_cont is None:
        return {'known': False, 'allow': False, 'ev': None,
                'continue_eq': None, 'fold_p': round(fold_p, 4),
                'equity_status': 'unavailable_not_negative_ev',
                'mc_audit': _mc_audit,
                'why': 'continue-range MC unavailable; raise EV not computed'}
    final_pot = pot_after_raise + opp_call

    # Incremental EV relative to folding now.  If villain folds, the raise chips
    # return with the pot, so the net win is the current pot.
    ev_continue = float(eq_cont) * final_pot - hero_inc
    ev = fold_p * float(pot or 0.0) + (1.0 - fold_p) * ev_continue
    return {
        'known': True,
        'allow': bool(ev > 0.0),
        'ev': round(ev, 3),
        'fold_p': round(fold_p, 4),
        'continue_eq': round(float(eq_cont), 4),
        'continue_mass': round(cont_mass, 4),
        'base_mass': round(base_mass, 4),
        'candidate_target': round(cand, 3),
        'hero_increment': round(hero_inc, 3),
        'opp_call': round(opp_call, 3),
        'price_frac': round(price_frac, 4),
        'optimistic': True,
        'n_opp': int(n_opp or 1),
        'why': 'optimistic immediate raise EV',
    }


def paired_board_flush_raise_damp(board, made_now):
    """넛급 레이즈에서 페어 보드 위 플러시(made 5)의 취약성 감쇠(ledger L116, 응답 문맥).

    make_plan 의 깊은 원페어 위험(deep_one_pair_vulnerability)과 다른 질문·문턱.
    """
    paired = board_paired(board)
    return 0.55 if paired and made_now == 5 else 1.0


def monster_raise_probability(profile, rel, board, made_now, has_concepts):
    """넛급 메이드가 벳을 맞았을 때 레이즈할 확률 0.05~0.95."""
    p = 0.30 + 0.45*rel
    p *= paired_board_flush_raise_damp(board, made_now)
    p *= (0.55 + 0.09*profile['aggr'])
    p *= (0.75 + 0.05*profile['gamble'])
    if has_concepts:
        rr = PS.sk(profile, 'reraise')/10.0
        p *= (0.55 + 0.85*rr)
        if rel >= 0.95:
            p = max(p, 0.32 + 0.40*rr)
    return max(0.05, min(0.95, p))


def value_raise_size_mult(plan_state, stack, tocall):
    """밸류 레이즈 크기 배수: 목표 커밋까지 남은 몫이 클수록 크게(0.75~1.6, 기본 1.1)."""
    _so = plan_state.get('stackoff') or {}
    _cm = _so.get('commit') if isinstance(_so, dict) else None
    mult = 1.1
    if _cm and stack > 0:
        want = stack*float(_cm)
        gap = max(0.0, want - tocall) / max(1.0, want)
        mult = max(0.75, min(1.6, 0.75 + 0.85*gap))
    return mult


def value_raise_probability(profile, plan, street, rel_ps, rr, so, committed):
    """밸류 계획이 벳을 맞았을 때 레이즈할 빈도(자격 판정 뒤, 클램프 전 상한 0.93)."""
    p = 0.20 + 0.55*rr + (0.25 if committed else 0.0)
    p *= (0.7 + 0.06*profile.get('aggr', 5))
    if committed and so < 0.35:
        p *= 0.5
    if plan == 'value_2street':
        p *= 0.80
    if rel_ps >= 0.95:
        floor = 0.38 + 0.42*rr
        if street == 'river': floor *= 0.85
        p = max(p, floor)
    elif rel_ps >= 0.88:
        p = max(p, 0.22 + 0.34*rr)
    return min(p, 0.93)


def semibluff_raise_probability(profile, has_concepts):
    """세미블러프 계획이 벳을 맞았을 때(리버 제외) 레이즈할 빈도(L120 응답 문맥)."""
    _p_sb = 0.35
    if has_concepts:
        _p_sb = (0.10 + 0.055*PS.sk(profile, 'semibluff')
                      + 0.030*PS.sk(profile, 'reraise'))
        _p_sb *= 0.70 + 0.06*PS.temper(profile, 'aggression', 5.0)
        _p_sb = max(0.03, min(0.80, _p_sb))
    return _p_sb


def semibluff_implied_odds_credit(profile, has_concepts, stack, pot):
    """드로우 콜의 내재 오즈만큼 필요 승률을 깎는 몫(최대 0.12). stack > pot 일 때만 호출."""
    _io = 0.05
    if has_concepts:
        _io = 0.02 + 0.008*(0.6*PS.sk(profile, 'outs') + 0.4*PS.sk(profile, 'potodds'))
    return min(0.12, _io * min(1.0, stack/max(1.0, 2.0*pot)))


def value_raise_qualification(hero, board, street, eq, n_opp, opp_range,
                              response_context, hero_contrib, stack, pot, tocall,
                              mult, profile, audit=None):
    """밸류 재레이즈 자격(판단). 반환 (ok, continue_eq 또는 None, fair_share).

    콜 equity 가 팟오즈를 넘는 것만으로는 부족하다 — 공정지분을 넘어야 하고,
    HU 에서는 제안한 레이즈를 맞고도 계속하는 레인지 대비 50% 를 넘어야 한다.
    결과 기록(plan_state['_last_value_raise_gate'])은 호출자가 한다(ledger L147).
    equity 는 내용 seed 를 쓰며 결정 RNG 를 소비하지 않는다.
    """
    _fair_share = 1.0 / max(2.0, float(n_opp) + 1.0)
    _vr_eq_cont = None
    _vr_ok = (eq is not None and float(eq) > _fair_share)
    if audit is not None:
        audit['status'] = ('fair_share_only' if _vr_ok else
                           'current_eq_unavailable' if eq is None else
                           'current_eq_below_fair_share')

    # HU에서는 한 단계 더 본다. 내가 제안한 raise를 맞고도 상대가
    # fold하지 않는 전체 range(call + re-raise) 상대로도 50%를 넘어야
    # "value raise"라고 부를 수 있다. 이 조건이 아니면 콜은 가능해도
    # 재레이즈는 금지한다.
    if (_vr_ok and int(n_opp or 1) == 1 and opp_range
            and isinstance(response_context, dict)
            and response_context.get('facing_target') is not None):
        _hc = max(0.0, float(hero_contrib or 0.0))
        _max_target = _hc + max(0.0, float(stack or 0.0))
        _base_target = _hc + max(
            0.0, float(pot + 2*tocall) * float(mult))
        _candidate_target = min(_max_target, _base_target)
        _hero_increment = max(0.0, _candidate_target - _hc)
        _pot_after_raise = float(pot) + _hero_increment
        _opp_contrib = max(
            0.0, float(response_context.get('facing_target') or 0.0))
        _opp_call = max(0.0, _candidate_target - _opp_contrib)
        _continue_price = _opp_call / max(1.0, _pot_after_raise)
        _cont = R.perceived_continue_range(
            opp_range, board, street, _continue_price, profile=profile)
        if _cont:
            _mc_audit = {}
            _vr_eq_cont = bot.equity_vs_combos(
                hero, board, [_cont], sims=400, audit=_mc_audit)
            _vr_ok = ahead_when_called(_vr_eq_cont)
            if audit is not None:
                audit['status'] = ('computed' if _vr_eq_cont is not None
                                   else 'continue_mc_unavailable')
                audit['mc_audit'] = _mc_audit
        else:
            # An empty continue slice does not certify a value raise.
            _vr_ok = False
            if audit is not None:
                audit['status'] = 'continue_range_unavailable'
    return _vr_ok, _vr_eq_cont, _fair_share


def river_nut_value_response(profile, hero, board, street, opp_range,
                             pot, tocall, stack, hero_contrib,
                             response_context, n_opp, allow_raise):
    """Exact river nuts use value sizing, never a generic raise-frequency roll.

    Hole cards must improve the board. Board-only nuts need separate chop /
    bluff reasoning. HU sizing compares weighted, blocker-conditioned river
    EV for legal raise candidates, including the effective all-in. No actual
    opponent hole cards or sampled equity enter this decision.
    """
    if street != 'river' or len(board) != 5 or len(hero) != 2:
        return None
    cards = list(hero) + list(board)
    if len(set(cards)) != 7:
        return None
    mine = bot.eval7(cards)
    if mine <= bot.eval7(list(board)):
        return None
    dead = set(cards)
    deck = [c for c in bot.FULLDECK if c not in dead]
    for i, a in enumerate(deck):
        for b in deck[i+1:]:
            if bot.eval7([a, b] + list(board)) > mine:
                return None

    hc = max(0.0, float(hero_contrib or 0.0))
    call_target = hc + float(tocall)
    cap = hc + max(0.0, float(stack))
    ctx = dict(response_context or {})
    info = {'exact_nuts': True, 'sizing_model': 'existing_value_size',
            'candidates': []}
    if not allow_raise or cap <= call_target:
        info.update(act='call', why='raise unavailable')
        return 'call', 0.0, info
    if int(n_opp or 1) == 1 and ctx.get('facing_stack') is not None:
        oc = ctx.get('facing_contrib')
        oc = call_target if oc is None else max(0.0, float(oc))
        cap = min(cap, oc + max(0.0, float(ctx['facing_stack'])))
        if cap <= call_target:
            info.update(act='call', why='opponent already all-in')
            return 'call', 0.0, info
    else:
        oc = call_target

    denom = max(1.0, float(pot) + 2.0*float(tocall))
    # The betting round owns the actual last full-raise increment. Facing
    # to-call is not the same increment after a hero bet or short all-in.
    min_increment = float(ctx.get('min_raise') or max(float(tocall), call_target))
    floor = call_target + min_increment
    targets = {cap, min(cap, floor)}
    for mult in (0.5, 1.0, 1.5):
        targets.add(min(cap, max(floor, hc + denom*mult)))

    items = [(c, w) for c, w in R.range_items(opp_range)
             if not (set(c) & dead)] if opp_range else []
    mass = sum(w for _, w in items)
    if int(n_opp or 1) != 1 or mass <= 0:
        target = min(cap, max(floor, hc + denom))
        info.update(act='raise', target=target, why='exact nuts value raise')
        return 'raise', (target-hc)/denom, info

    scores = {tuple(c): bot.eval7(list(c) + list(board)) for c, _ in items}
    def eq_of(rows):
        total = sum(w for _, w in rows)
        return (sum(w*(0.5 if scores[tuple(c)] == mine else 1.0)
                    for c, w in rows)/total) if total else 0.0

    call_ev = eq_of(items)*(float(pot) + float(tocall)) - float(tocall)
    best = None
    for target in sorted(targets):
        if target <= call_target:
            continue
        inc = target-hc
        opp_call = max(0.0, target-oc)
        cont = R.perceived_continue_range(
            opp_range, board, street,
            opp_call/max(1.0, float(pot)+inc), profile=profile)
        rows = [(c, w) for c, w in R.range_items(cont)
                if tuple(c) in scores and not (set(c) & dead)]
        cm = sum(w for _, w in rows)
        cp = max(0.0, min(1.0, cm/mass))
        ev = ((1.0-cp)*float(pot) + cp*(
            eq_of(rows)*(float(pot)+inc+opp_call)-inc))
        info['candidates'].append({'target': target, 'ev': ev,
                                   'continue_p': cp})
        # Equal EV favors the smaller raise, rather than needless all-in.
        if best is None or ev > best[0] + 1e-9:
            best = (ev, target)
    info.update(sizing_model='heads_up_river_value_ev', call_ev=call_ev)
    if best is None or best[0] < call_ev - 1e-9:
        info.update(act='call', why='raise EV below call EV (split-pot range)')
        return 'call', 0.0, info
    info.update(act='raise', target=best[1], why='exact nuts best value target')
    return 'raise', (best[1]-hc)/denom, info


def decide_response(profile, hero, board, street, plan, plan_state, eq, need,
                    made_now, opp_range, pot, tocall, stack, committed, rng,
                    allow_raise=True, call_eq=None, call_need=None,
                    opp_ranges=None, n_opp=1, rel_seed=None,
                    response_context=None, hero_contrib=0.0):
    """저항(tocall>0)을 마주했을 때 폴드/콜/레이즈를 정하는 **유일한 지점**.

    예전에는 이 판단이 집행부에 흩어져 p_raise 를 네 곳에서 각자 굴렸다.
    무저항 쪽은 decide_aggression 으로 합쳤으므로 저항 쪽도 같은 형태로 맞춘다.
    집행부는 여기 결과를 칩으로 환산만 한다.

    반환: (act, size_mult, need, why)
      act       : 'fold' | 'call' | 'raise'
      size_mult : raise 일 때 (pot + 2*tocall) 에 곱할 배수
    """
    # Public/direct callers must obey the same unavailable-equity contract
    # as act_with_plan: do not let the legacy comparisons run on None.
    if eq is None or need is None:
        plan_state['equity_status'] = 'unavailable_not_negative_ev'
        plan_state.setdefault('equity_unavailable', {}).setdefault(
            'reason', 'response_equity_or_price_unavailable')
        return 'fold', 0.0, need, (
            'MC/price unavailable; executable fold, NOT verified negative EV')

    rel_ps = plan_state.get('rel', 0.5)
    has_c = bool(profile.get('concepts'))

    plan_state.pop('_last_river_nuts_value', None)
    plan_state.pop('_last_nonvalue_raise_gate', None)
    plan_state.pop('_last_value_raise_gate', None)
    nuts = river_nut_value_response(
        profile, hero, board, street, opp_range, pot, tocall, stack,
        hero_contrib, response_context, n_opp, allow_raise)
    if nuts is not None:
        act, mult, info = nuts
        plan_state['_last_river_nuts_value'] = info
        return act, mult, need, info['why']

    # F8-D4: raise eligibility keeps legacy eq/need.  These two values are used
    # only when the response has reached an actual call-vs-fold choice.
    _layer_call = (call_eq is not None and call_need is not None)
    _cf_eq = float(call_eq) if _layer_call else eq
    _cf_need = float(call_need) if _layer_call else need

    def _nv_gate(mult=None, target=None):
        g = _nonvalue_raise_ev_gate(
            profile, hero, board, street, opp_range, opp_ranges, n_opp,
            pot, tocall, stack, hero_contrib, response_context,
            mult=mult, target=target)
        plan_state['_last_nonvalue_raise_gate'] = dict(g)
        return g

    # --- 넛급 메이드: 레이즈할 것인가 ---
    if made_now >= 5 and eq > need + 0.10:
        rel, _resp_rel_meta = _decision_relative_strength(
            hero, board, opp_range, n_opp=n_opp, opp_ranges=opp_ranges,
            sims=600, seed=rel_seed)
        plan_state['_last_response_rel_source'] = _resp_rel_meta.get('source')
        plan_state['_last_response_rel_union'] = _resp_rel_meta.get('union')
        plan_state['_last_response_rel_joint'] = _resp_rel_meta.get('joint')
        p = monster_raise_probability(profile, rel, board, made_now, has_c)
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

        # 레이즈 크기는 먼저 정한다. 이 크기를 상대가 실제로 맞았을 때의
        # continue range를 만들어야 "콜 가능"과 "밸류 재레이즈 가능"을
        # 서로 다른 판단으로 볼 수 있다.
        mult = value_raise_size_mult(plan_state, stack, tocall)

        # Value-raise invariant:
        #   현재 range에 대한 콜 equity가 팟오즈를 넘는 것만으로는 부족하다.
        #   추가 칩을 넣는 "value" raise라면 최소한 공정지분(fair share)을
        #   넘어야 한다. HU에서는 50%, 3-way에서는 33.3%다.
        _vr_audit = {}
        _vr_ok, _vr_eq_cont, _fair_share = value_raise_qualification(
            hero, board, street, eq, n_opp, opp_range, response_context,
            hero_contrib, stack, pot, tocall, mult, profile,
            audit=_vr_audit)

        plan_state['_last_value_raise_gate'] = {
            'current_eq': round(float(eq), 4),
            'fair_share': round(_fair_share, 4),
            'continue_eq': (
                round(float(_vr_eq_cont), 4)
                if _vr_eq_cont is not None else None),
            'ok': bool(_vr_ok),
            'continue_eq_status': _vr_audit.get('status'),
            'continue_mc_audit': (_vr_audit.get('mc_audit') if _vr_eq_cont is None
                                  else None),
        }

        if not _vr_ok:
            _use_eq = _cf_eq if _layer_call else eq
            _use_need = _cf_need if _layer_call else need
            if _use_eq < _use_need:
                return 'fold', 0.0, _use_need, (
                    '밸류 계획이나 재레이즈 자격 없음 + 콜 기준 미달'
                    '(eq %.3f < need %.3f)' % (_use_eq, _use_need))
            return 'call', 0.0, _use_need, (
                '콜 가능하지만 밸류 재레이즈 자격 없음'
                '(eq %.3f, continue_eq %s)'
                % (_use_eq,
                   ('%.3f' % _vr_eq_cont
                    if _vr_eq_cont is not None else 'n/a')))

        p = value_raise_probability(profile, plan, street, rel_ps, rr, so,
                                    committed)
        if allow_raise and rng.random() < max(0.05, min(0.92, p)):
            return 'raise', mult, need, (
                '밸류 레이즈(%.0f%%, x%.2f, continue_eq %s)'
                % (p*100, mult,
                   ('%.3f' % _vr_eq_cont
                    if _vr_eq_cont is not None else 'n/a')))
        if _layer_call and _cf_eq < _cf_need:
            return 'fold', 0.0, _cf_need, (
                '밸류 레이즈 미선택 + layer call EV 미달(%.3f < %.3f)'
                % (_cf_eq, _cf_need))
        return 'call', 0.0, (_cf_need if _layer_call else need), '밸류이나 콜 선택(상대가 팟을 키워줌)'

    # --- 블러프/세미블러프 재레이즈 ---
    # 빈도 주사위보다 먼저 공통 EV gate를 통과해야 한다.
    # 재레이즈 깊이/올인 여부는 response_context와 현재 range에 이미 반영된다.
    if allow_raise and has_c and eq < need - 0.05 and plan in ('bluff_2street', 'semibluff', 'river_bluff'):
        made_sd = plan_state.get('made', 0)
        if made_sd < 2:
            blr = (PS.sk(profile, 'reraise')/10.0) * (PS.sk(profile, 'bluff')/10.0)
            _g_bl = _nv_gate(mult=1.0)
            if _g_bl.get('allow') and rng.random() < blr*0.28:
                return 'raise', 1.0, need, (
                    '블러프 레이즈(개념 %.2f, EV %s)'
                    % (blr, _g_bl.get('ev')))

    # --- 세미블러프: 레이즈 or 내재오즈 콜 ---
    if plan == 'semibluff' and plan_state.get('outs', 0) >= 8 and street != 'river':
        _p_sb = semibluff_raise_probability(profile, has_c)
        _g_sb = _nv_gate(mult=0.95) if allow_raise else {'allow': False}
        if allow_raise and _g_sb.get('allow') and rng.random() < _p_sb:
            return 'raise', 0.95, need, (
                '세미블러프 레이즈(%.0f%%, EV %s)'
                % (_p_sb*100, _g_sb.get('ev')))
        if stack > pot:
            implied = semibluff_implied_odds_credit(profile, has_c, stack, pot)
            need = max(0.02, need - implied)
            if _layer_call:
                _cf_need = max(0.02, _cf_need - implied)
        _use_eq = _cf_eq if _layer_call else eq
        _use_need = _cf_need if _layer_call else need
        act = 'call' if _use_eq >= _use_need else 'fold'
        _gate_note = ''
        if allow_raise and isinstance(_g_sb, dict) and not _g_sb.get('allow'):
            if _g_sb.get('ev') is not None:
                _gate_note = ' | raise EV %.1f ≤ 0' % float(_g_sb['ev'])
            else:
                _gate_note = ' | raise EV 계산 불가(%s)' % _g_sb.get('why', 'unknown')
        return act, 0.0, _use_need, (
            '세미블러프 내재오즈 반영%s%s'
            % (' + layer call EV' if _layer_call else '', _gate_note))

    if plan == 'giveup' and has_c and eq < need - 0.05:
        disc = PS.temper(profile, 'discipline', 5.0)
        blr = (PS.sk(profile, 'reraise')/10.0) * (PS.sk(profile, 'bluff')/10.0)
        p_dev = blr * 0.28 * max(0.05, 1.0 - 0.085*disc)
        _g_dev = _nv_gate(mult=1.0) if allow_raise else {'allow': False}
        if (allow_raise and _g_dev.get('allow')
                and plan_state.get('made', 0) < 2
                and rng.random() < p_dev):
            plan_state.setdefault('deviations', []).append(
                {'street': street, 'planned': 'fold', 'executed': 'raise',
                 'why': '규율 %.1f + raise EV %s → 포기 계획 뒤집음'
                        % (disc, _g_dev.get('ev'))})
            return 'raise', 1.0, need, (
                'DEVIATE:포기 계획 뒤집은 블러프 레이즈(EV %s)'
                % _g_dev.get('ev'))

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

    # --- 인식 편향은 이미 need 에 들어 있다 ---
    # station / bluff_fear / hero_call / draw_love / sticky 는 calldown_need 의
    # persona.call_bias 에서 한 번만 적용된다(L148). 여기서 다시 곱하면 같은
    # 기질이 두 번 반영된다.
    need_seen = _cf_need if _layer_call else need
    _eq_seen = _cf_eq if _layer_call else eq
    act = 'call' if _eq_seen >= need_seen else 'fold'
    return act, 0.0, need_seen, (
        'eq %.3f vs 체감 need %.3f (실제 %.3f)%s'
        % (_eq_seen, need_seen, need, ' [layer-call]' if _layer_call else ''))


def _called_prior_street_aggression(plan_state, street):
    """Did hero call an opponent's aggression on the immediately prior street?

    This is line history, not hand strength.  After bet/raise -> call, the
    aggressor normally keeps initiative on the next street.  Losing this fact
    caused lines like bet/call flop -> donk turn -> fold to raise.
    """
    prev = {'turn': 'flop', 'river': 'turn'}.get(street)
    if not prev or not isinstance(plan_state, dict):
        return False
    rows = ((plan_state.get('response_plans') or {}).get(prev) or [])
    for rp in reversed(rows):
        if rp.get('act') != 'call':
            continue
        if rp.get('response_kind') in (
                'aggressor_backaction', 'face_bet', 'check_then_face_bet'):
            return True
        # Legacy response rows may not have response_kind but do carry source.
        if rp.get('source') in ('generic_response', 'checkraise_declined'):
            return True
    return False


def line_owned_by_live_aggressor(plan_state, street, initiative, oop_vs_aggr):
    """이 스트리트의 베팅 라인이 뒤에 살아 있는 어그레서 것인가.

    턴/리버: 직전 스트리트에 상대 공격을 내가 콜했다.
    플랍: 직전 스트리트는 프리플랍이다. 프리플랍 레이즈를 받고 들어와 그
    레이저가 뒤에 살아 있으면 라인은 그 사람 것이다(audit9 batch 1 R5a-ext).
    공통 조건: 나는 이니셔티브가 없고 그 어그레서보다 먼저 행동한다.
    """
    _called_prev_aggr = _called_prior_street_aggression(plan_state, street)
    if street == 'flop' and not initiative and oop_vs_aggr is True:
        _called_prev_aggr = True
    return bool(_called_prev_aggr and not initiative and oop_vs_aggr is True)


def bluff_donk_suppression(profile, aggr, outs, plan_state, has_concepts):
    """알려진 어그레서 앞에서 블러프 계열로 먼저 칠 때의 억제 강도(클램프 전).

    두 질문이 다른 항으로 들어간다(ledger L134):
      드로우 의존(outs >= 8)  — 턴까지의 세미블러프 근거로 억제를 덜 함
      프로브(상대가 직전 street 체크백) — 상대 레인지가 약하다는 공개 사실
    리버에는 future draw 가 없어 첫 항이 outs 0 으로 자연히 꺼진다.
    """
    # 동크(같은 스트리트 선제)는 정석이 아니다. 수동형일수록 강하게 억제.
    supp = 0.92 - 0.05*aggr - 0.02*profile.get('bluff', 5)
    if has_concepts and outs >= 8:
        supp = max(0.45, supp - 0.020*PS.sk(profile, 'probe'))
    # **프로브는 동크가 아니다.** 상대가 이전 스트리트를 체크백했으면
    # 그 사람 레인지가 약하다는 뜻이라 먼저 치는 것이 정석이다.
    # 예전에는 probe 개념이 동크 억제에만, 그것도 outs>=8 일 때만
    # 쓰여서 프로브 스팟 자체가 표현되지 않았다.
    if has_concepts and (plan_state or {}).get('opp_checked_prev'):
        supp *= max(0.25, 1.0 - 0.085*PS.sk(profile, 'probe'))
    return supp


def potcontrol_bet_probability(aggr, rel, initiative, oop_vs_aggr):
    """팟컨트롤 계획에서 그래도 벳할 확률과 사유(ledger L123).

    continuation(이니셔티브/어그레서 없음) 과 caller stab(살아 있는 어그레서
    앞의 리드)을 구분한다 — 후자는 block 계획의 몫이라 거의 체크한다.
    """
    # 팟컨트롤인데 3분의 1 확률로 벳하면 계획과 행동이 어긋난다.
    # 치기로 했으면 그건 이미 팟컨트롤이 아니다 —
    # 얇은 밸류라면 river_fix 가 thin_river 로 승격시켰어야 한다.
    if rel < 0.30:
        return 0.04, '팟컨트롤 + 강도 %.2f → 체크' % rel
    # 알려진 어그레서가 뒤에 있는데 먼저 치는 것은 팟컨트롤이 아니라 리드다.
    # OOP 중간강도의 '먼저 쳐서 가격 고정'은 make_plan 의 block 계획 몫이고,
    # pot_control 은 그 대안(체크)으로 선택된 것이다. 예전에는 위치를 보지
    # 않아 SB 55 가 3-way 플랍에서 PFR 앞으로 2,200 리드 → 레이즈 맞고 콜 →
    # 턴 폴드했다(audit9 HAND 38).
    if not initiative and oop_vs_aggr is True:
        return 0.04, '팟컨트롤 + 어그레서가 뒤에 있음 → 체크(리드는 block 계획)'
    return max(0.05, min(0.6, 0.18 + 0.035*aggr)), '팟컨트롤 → 대부분 체크'


def decide_aggression(profile, board, street, plan, rel, n_opp, oop, initiative,
                      to_act_behind, rng, opp_est=None, outs=0, plan_state=None,
                      oop_vs_aggr=None, oop_legacy_abs=None, spr_now=None, tilt=0.0):
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
        # 리버의 쇼다운 계획은 '콜 레인지 대비 앞서지 않는다'는 판정의 결과다
        # (river_fix 가 앞서면 얇은 밸류로 승격한다). 이 손으로 치면 더 좋은 손만
        # 콜하고 더 나쁜 손만 접는다 — 쇼다운 가치를 블러프로 바꾸는 것이라
        # 체크보다 항상 나쁘다(베타 A #3). 플랍/턴은 남은 카드에 대한 보호·
        # 에쿼티 거부 동기가 있고, 포기(에어) 계획의 리버 벳은 순수 블러프다.
        if plan == 'showdown' and street == 'river':
            return 0.0, '리버 쇼다운 계획 → 체크(치면 더 좋은 손만 콜)'
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
        # texture.new_card_effect 가 이걸 잰다. 새 카드는 직전 보드 전체 대비로
        # 본다(리버면 플랍+턴, L-RA07).
        if street in ('turn', 'river') and len(board) >= 4 and has_c:
            _tce = TX.new_card_effect(board[:-1], board[-1],
                                      aggressor_range_high=bool(initiative))
            _bt = board_texture_read(profile)
            p *= max(0.35, min(1.70, 1.0 + 0.75*_tce*_bt))
        _mw2 = PS.sk(profile, 'multiway')/10.0 if has_c else 0.5
        p *= (1 - (0.12 + 0.20*_mw2)*max(0, n_opp-1))
        # 동크는 '알려진 어그레서보다 먼저 리드한다'는 뜻이다.
        # 어그레서가 없으면 체크어라운드/림프팟의 lead이지 donk가 아니다.
        # 따라서 절대 좌석 OOP를 donk 억제의 대체 신호로 쓰지 않는다.
        _oop_a = (oop_vs_aggr is True)
        if not initiative and _oop_a:
            supp = bluff_donk_suppression(profile, a, outs, plan_state, has_c)
            p *= max(0.03, 1.0 - max(0.30, min(0.97, supp)))
        p *= _dc_boost
        # **clamp 이후 값으로 로그를 만든다.** 예전에는 원본 p 로 문자열을
        # 만들어 115% 같은 불가능한 확률이 기록됐다(실제 반환은 0.95).
        _fp = max(0.02, min(0.95, p))
        return _fp, '블러프 기본 실행률(%.0f%%)' % (_fp*100)

    if plan == 'block':
        # 상수 0.80 이었다. 블락벳은 개념이 있어야 실행하는 라인인데
        # 계획만 잡히면 전원이 같은 빈도로 쳤다.
        _bb = 0.80
        if has_c:
            _bb = 0.35 + 0.055*PS.sk(profile, 'blockbet')
        return max(0.15, min(0.92, _bb)), '블락벳 계획(%.0f%%)' % (_bb*100)

    if plan == 'pot_control':
        return potcontrol_bet_probability(a, rel, initiative, oop_vs_aggr)

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

    # Line ownership: if we CALLED the opponent's aggression on the prior
    # street and remain OOP to that aggressor, default back to them.  A value
    # label describes hand class; it does not erase who owns the betting line.
    #
    # Keep a small personality-driven donk/re-lead frequency instead of a hard
    # prohibition.  Aggressive humans sometimes lead strong hands, but the
    # previous implementation effectively treated it as a fresh 97% value bet.
    if line_owned_by_live_aggressor(plan_state, street, initiative, oop_vs_aggr):
        # 분명한 밸류(rel >= CLEAR_VALUE_REL)에서 상대에게 액션을 넘기는 것은
        # '체크로 상대 벳을 유도'하는 트랩이다. 트랩은 상대가 쳐줄 때만 성립하므로
        # 그 판단(trap_judgment: 상대 벳 확률·SPR·인원·보드 위험·취향)을 그대로
        # 거친다. 트랩이 아니면 리드한다. 예전에는 강도와 무관하게 재리드 4~16%
        # 였고, 넛급으로 체크 → 상대 체크백으로 밸류를 잃었다(베타 A #2).
        # 중간 강도는 아래 라인 소유 규칙(대부분 체크)을 그대로 쓴다.
        if has_c and rel >= CLEAR_VALUE_REL:
            _ps = plan_state or {}
            _spr = spr_now if spr_now is not None else (_ps.get('spr') or 5.0)
            p_trap, _twhy = trap_judgment(
                profile, opp_est, _spr, _ps.get('danger', 0.0) or 0.0,
                max(0, int(n_opp or 1) - 1), street, tilt,
                lambda c: PS.sk(profile, c), opp_role='aggressor')
            _fp = max(0.0, min(0.97, 1.0 - p_trap))
            return _fp, (
                '라인은 상대 것이나 분명한 밸류(rel %.2f) → 트랩 %.0f%%, 아니면 리드(%.0f%%)'
                % (rel, p_trap*100, _fp*100))
        _relead = max(0.04, min(0.16, 0.04 + 0.010*float(a)))
        p *= _relead
        _fp = max(0.02, min(0.35, p))
        return _fp, (
            '직전 스트리트 상대 공격 콜 + OOP → 상대에게 액션 우선'
            ' (재리드 %.0f%%)' % (_fp*100))

    _fp = max(0.05, min(0.97, p))
    return _fp, '밸류 계획 실행(%.0f%%)' % (_fp*100)


def planned_size_base(plan, street, plan_state):
    """계획(과 블러프 세부 모드)이 정하는 기준 사이즈. 반환 (사이즈용 plan, base, bluff_mode).

    decide_size 의 '계획 → 기준 사이즈' 질문이다(ledger L138). 강도에 따른
    보정(약한 패 축소, 오버벳)과 실행 보정(텍스처·성향)은 decide_size 에 남는다.
    merged 위장은 사이즈 경로 전체를 밸류와 같게 하려고 plan 자체를 바꾼다.
    """
    base = SIZING.get(plan, {}).get(street, 0.0)
    # 블러프 세부 전략이 사이즈를 바꾼다(bluff_mode). 예전에는 계획이
    # bluff_2street 이면 상대가 누구든 보드가 뭐든 고정값(0.45/0.60)이었다.
    #   merged    — 같은 상황의 **밸류 사이즈를 그대로** 쓴다. 위장의 핵심이라
    #               배수가 아니라 표 자체를 바꿔야 구분이 불가능해진다.
    #   polarized — 오버벳
    #   probe     — 최소 비용(사이즈 모드. 공개 probe 기회와 다른 이름, L144)
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
    return plan, base, _bm


def decide_size(profile, hero, board, street, plan, rel, opp_range, my_range,
                pot, stack, rng, opp_est=None, nut=0.0, deviating=False,
                stackoff=None, plan_state=None, n_opp=1, opp_ranges=None):
    """이 스트리트 벳 사이즈(팟 대비)를 정하는 **유일한 지점**.

    예전에는 한 사이즈가 네 번 재계산됐다:
      SIZING 표 → TX.size_fraction 과 혼합 → overbet_frac 이 덮어씀
      → (실행 층의) shape_size 가 또 흔듦
    그래서 어느 값이 최종인지 추적이 안 됐고, 개인 성향이 어디서 반영되는지도 불명확했다.

    지금은 여기 하나에서 정한다. 집행부는 이 값을 칩으로 환산만 한다.
    (shape_size 는 '사람다운 끝자리'만 만드는 표현 계층이므로 집행부에 남긴다.)
    """
    plan, base, _bm = planned_size_base(plan, street, plan_state)
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
        _bt2 = board_texture_read(profile) if profile.get('concepts') else 0.5
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

    # Thin value has a different objective from polarized value: get called by
    # worse.  Its eligibility in river_fix is evaluated against the opponent's
    # continue range at the 42% base size, so execution must not later inflate
    # that bet into a 70%+ polar sizing.  Texture/style may nudge the size, but
    # keep it in a genuinely thin-value band and never route it through overbet.
    if plan == 'thin_river':
        return max(0.25, min(0.50, base))
    # Block bet은 OOP 중간강도의 '가격 통제'다. 텍스처·equity denial·공격성
    # 보정은 밸류/보호 사이즈를 위한 것이라, 그대로 곱하면 블락이 0.76팟이
    # 됐다(audit9 HAND 83: SB AQs A856 턴 '블락벳' 7,100/9,200). 같은 이유로
    # 계획 대역 안에서만 움직이게 한다.
    if plan == 'block':
        return max(0.18, min(0.40, base))

    # 오버벳: 개념·넛우위·양극화가 갖춰졌을 때만. 판단 층에서 결정된다.
    ob = overbet_frac(profile, hero, board, opp_range, my_range, street, plan,
                      rel, rng, opp_est, nut=nut, n_opp=n_opp,
                      opp_ranges=opp_ranges,
                      seed=(plan_state or {}).get('eq_seed'))
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
    response = dict(response)
    # Only unavailable evidence needs extra provenance in the final
    # response record. Do not silently reinterpret this as verified -EV.
    nonvalue = state.get('_last_nonvalue_raise_gate') or {}
    if nonvalue.get('equity_status') == 'unavailable_not_negative_ev':
        response['nonvalue_raise_gate'] = dict(nonvalue)
    value = state.get('_last_value_raise_gate') or {}
    if value.get('continue_eq_status') in (
            'continue_mc_unavailable', 'continue_range_unavailable',
            'current_eq_unavailable'):
        response['value_raise_gate'] = dict(value)
    rows = state.setdefault('response_plans', {})
    rows.setdefault(street, []).append(response)
    state['_last_response_plan'] = dict(response)
    return response


STREET_ORDER = ['flop', 'turn', 'river']

# 계획 이름이 뜻하는 **예산** — 몇 스트리트를 칠 작정인가.
# SIZING 표와 분리한 이유: 예전에는 river:0.0 하나가 '예산 소진'과
# '원래 안 치는 계획'을 동시에 뜻해서, bet_size 의 `base <= 0` 가드가
# 둘을 구분하지 못했다. 사이즈는 SIZING 이, 예산은 여기가 맡는다.
# value_3street 은 스트리트가 셋뿐이라 실제로는 걸리지 않는다(명시 목적).
BUDGET = {'value_2street': 2, 'value_3street': 3, 'bluff_2street': 2}


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
    # 리버 0 은 value_2street 와 같은 예산/사이즈 겹침 결함이었다. 플랍을 체크하고
    # 턴부터 블러프를 시작하면 예산(2스트리트)이 리버에 1 남는데, 사이즈 0 이
    # '원래 안 치는 계획'으로 읽혀 판단층의 리버 벳(95%)이 체크로 바뀌었다
    # (audit9 HAND 20). 횟수는 budget_left 가 막고, 사이즈는 river_bluff 값을 쓴다.
    'bluff_2street': {'flop':0.45,'turn':0.60,'river':0.72},
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

def overbet_value_continue_rel(hero, board, opp_range, street, rel, profile,
                               opp_ranges=None, n_opp=1, seed=None):
    """밸류 오버벳의 강도 = min(rel, 오버벳(1.15팟)을 계속하는 레인지 대비 강도).

    커밋 재측정과 같은 continue_range_strength 를 쓴다(L-S9-03/04): 멀티웨이는
    seat 별 continue range 의 joint 강도, 인지 편향도 rel 과 같은 방식.
    """
    _rc = continue_range_strength(
        hero, board, profile, street, 1.15, opp_range, opp_ranges, n_opp,
        bot.made_strength(hero, board) if board else 0, seed=seed)
    if _rc is not None:
        rel = min(rel, _rc)
    return rel


def overbet_line_polarization(rel, value_line):
    """라인의 양극화 정도 0~1: 밸류는 rel 이 높을수록, 블러프는 낮을수록."""
    pol = (max(0.0, (rel - 0.62) / 0.30) if value_line
           else max(0.0, (0.42 - rel) / 0.30))
    return min(1.0, pol)


def overbet_selection_base(overbet_skill, nut, pol, aggr, street, bluff_line):
    """오버벳 선택 확률(상대 읽기 보정 전). street 분기는 리버 가중 하나뿐(L139/L140)."""
    p = 0.16 * max(0.0, min(1.0, (overbet_skill - 2.5) / 5.0))  # 개념 숙련도, 연속
    p *= (0.25 + 1.9*max(0.0, min(0.5, nut)))        # 넛 우위에 비례
    p *= pol
    p *= (0.75 + 0.05*aggr)
    if street == 'river': p *= 1.35                 # 리버가 오버벳의 주 무대
    if bluff_line: p *= 0.65                        # 블러프 오버벳은 더 드물다
    return p


def overbet_size(nut, overbet_skill, rng):
    """오버벳 실행 사이즈(팟 배수): 넛 우위가 클수록 크게. rng.uniform 1회."""
    base = 1.15 + 0.55*min(1.0, nut) + 0.03*(overbet_skill - 4.0)
    return round(min(2.2, base * rng.uniform(0.92, 1.10)), 2)


def overbet_frac(profile, hero, board, opp_range, my_range, street, plan, rel, rng,
                 opp_est=None, nut=0.0, n_opp=1, opp_ranges=None, seed=None):
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
    # factual nut metric is produced by judgment/refresh and forwarded here.
    # Sizing must not silently rebuild a collapsed opponent range judgment.
    nut = float(nut or 0.0)

    # 예전에는 ob<4.0, nut<0.10, rel>=0.85 / rel<=0.25 네 개가 전부 하드 컷이었다.
    # 개념 3.9 와 4.1 이 완전히 다른 사람이 되고, rel 0.84 는 오버벳이
    # 아예 불가능했다. 전부 연속 가중으로 바꾼다 — 조건이 약하면
    # 확률이 낮아질 뿐 선택지에서 사라지지는 않는다.
    value_line = plan in ('value_3street', 'trap')
    bluff_line = plan in ('bluff_2street', 'semibluff', 'river_bluff')
    if not (value_line or bluff_line): return None  # 계획 자체가 아니면 제외

    # 양극화 정도. 밸류는 rel 이 높을수록, 블러프는 낮을수록 오버벳에 맞는다.
    # 밸류 오버벳의 양극화는 '레인지 전체 대비'가 아니라 **오버벳을 콜하는
    # 레인지 대비** 강도로 본다. 전체 rel 0.90 인 A8(877) 이 턴 1.64 팟
    # 오버벳을 쳤는데, 그 크기를 콜하는 레인지(7x·88·오버페어)에는 앞서지
    # 않았다(audit9 HAND 16). 리버 thin value 와 같은 continue-range 모델.
    if value_line and opp_range and board:
        rel = overbet_value_continue_rel(hero, board, opp_range, street, rel,
                                         profile, opp_ranges=opp_ranges,
                                         n_opp=n_opp, seed=seed)
    pol = overbet_line_polarization(rel, value_line)
    if pol <= 0.02: return None                     # 미들레인지는 제외

    p = overbet_selection_base(ob, nut, pol, profile.get('aggr', 5), street,
                               bluff_line)
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

    return overbet_size(nut, ob, rng)


def cbet_flop_frequency(profile, board, n_opp, oop, rel, opp_est=None, range_adv=0.0):
    """Flop continuation entry; consumes cbet_flop capability."""
    return _continuation_frequency(profile, board, n_opp, 'flop', oop, rel,
                                   opp_est, range_adv)


def barrel_turn_frequency(profile, board, n_opp, oop, rel, opp_est=None, range_adv=0.0):
    """Turn continuation entry; consumes barrel_turn capability."""
    return _continuation_frequency(profile, board, n_opp, 'turn', oop, rel,
                                   opp_est, range_adv)


def barrel_river_frequency(profile, board, n_opp, oop, rel, opp_est=None, range_adv=0.0):
    """Terminal continuation entry; consumes barrel_river capability.

    Existing shared board multiplier remains a documented follow-up question.
    """
    return _continuation_frequency(profile, board, n_opp, 'river', oop, rel,
                                   opp_est, range_adv)


def cbet_freq(profile, board, n_opp, street, oop, rel, opp_est=None, range_adv=0.0):
    """Compatibility dispatcher; actual street entry points are explicit."""
    producer = {'flop': cbet_flop_frequency, 'turn': barrel_turn_frequency,
                'river': barrel_river_frequency}.get(street)
    if producer is None:
        return _continuation_frequency(profile, board, n_opp, street, oop, rel,
                                       opp_est, range_adv)
    return producer(profile, board, n_opp, oop, rel, opp_est, range_adv)


def _continuation_frequency(profile, board, n_opp, street, oop, rel, opp_est=None, range_adv=0.0):
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
    _bt = board_texture_read(profile) if profile.get('concepts') else 0.5
    _cm = TX.cbet_multiplier(board, not oop)
    f *= 1.0 + (_cm - 1.0) * _bt            # 개념이 낮으면 구조를 못 읽는다
    f *= (1 - 0.18*bot.board_danger(board)) # 젖은 정도는 남기되 비중을 줄인다
    # 포지션 효과는 positional 숙련에 따라 다르다(2026-10-06, 사용자 승인). 예전에는 전원 OOP ×0.88 로
    # 같아서 '포지션을 아는 사람이 IP/OOP 를 다르게 친다'가 없었다. 숙련 0 은 포지션 차이를 무시하고
    # (OOP ×1.00, IP ×0.94), 숙련 10 은 크게 반영한다(OOP ×0.76, IP ×1.06). 숙련 5 에서 OOP ×0.88 로 예전과 같다.
    _pk = PS.sk(profile, 'positional')/10.0 if profile.get('concepts') else 0.5
    if oop:
        f *= 1.0 - 0.24*_pk
    else:
        f *= 1.0 + 0.12*(_pk - 0.5)
    f += 0.35*max(0.0, rel-0.6)             # 강할수록 추가
    # 레인지 우위. 씨벳 빈도의 가장 큰 구조적 근거인데 예전에는 들어가지 않았다.
    # 개념(board_texture)이 없으면 보드가 누구에게 유리한지 못 읽는다.
    if range_adv:
        _ba = board_texture_read(profile) if profile.get('concepts') else 0.5
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



def response_equity(hero, board, profile, opp_range, opp_ranges, n_opp,
                    opp_est, pot, tocall, street, response_context, seed,
                    audit=None):
    """벳을 맞았을 때 판단에 쓰는 equity — 3단 fallback(ledger L153 추론 층).

      1. seat pools: 아는 상대는 perceived range(hero/board 카드 제외),
         모르는 seat 는 중립 fallback range_combos(0.35)
      2. pool 이 하나도 없고 opp_range 가 20콤보 이상: 이번 벳 사건으로 좁힌 레인지
      3. 그 외: 고정 벳/콜러 레인지 근사(equity_vs_betting)
    결정 RNG 를 소비하지 않는다(equity 는 내용/seed 기반).
    """
    callers = [(0.30, 5)]*max(0, n_opp-1)
    _raw_pools = _normalize_opp_pools(opp_range, n_opp, opp_ranges)
    _dead = set(hero) | set(board or [])
    _pools = [
        (bot._filter_pool(p, _dead, sort_legacy=True)
         if p else bot.range_combos(0.35, _dead))
        for p in _raw_pools
    ]
    if any(not p for p in _pools):
        if audit is not None:
            audit.update(complete=False, reason='missing_opponent_range',
                         requested=600, accepted=0)
        return None
    if _pools:
        # 아는 상대는 실제 perceived range, 모르는 상대는 중립 field range.
        # 다른 상대의 range를 복제하지 않는다.
        eq = bot.equity_vs_combos(hero, board, _pools, sims=600,
                                  audit=audit)
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
        _rk = (response_context or {}).get('facing_kind')
        _event_action = 'raise' if _rk == 'raise' else 'bet'
        _price_frac = float(tocall) / max(
            1.0, float(pot) - float(tocall))
        _fallback_event = {
            'street': street,
            'action_kind': _event_action,
            'size_frac': sz,
            'facing_kind': (
                (response_context or {}).get('raiser_facing_kind')
                if _event_action == 'raise' else None),
            'facing_size_frac': (
                (response_context or {}).get('raiser_facing_size_frac')
                if _event_action == 'raise' else None),
            'facing_price_frac': (
                (response_context or {}).get('raiser_facing_price_frac')
                if _event_action == 'raise' else None),
            'allin': bool((response_context or {}).get('facing_allin')),
            'allin_raise': bool(
                (response_context or {}).get('facing_allin_raise')),
            'full_raise': bool(
                (response_context or {}).get('facing_full_raise')),
            'incomplete_raise': bool(
                (response_context or {}).get('facing_incomplete_raise')),
            'raise_depth_full_after': int(
                (response_context or {}).get('raise_depth_full', 0) or 0),
            'raise_depth_any_after': int(
                (response_context or {}).get('raise_depth_any', 0) or 0),
        }
        bet_r = R.perceived_range(
            opp_range, board, [_fallback_event], profile)
        eq = bot.equity_vs_combos(hero, board,
                                  [bet_r] + [opp_range]*max(0, n_opp-1),
                                  sims=600, audit=audit)
    else:
        eq = bot.equity_vs_betting(hero, board, [(0.22, profile['bluff'])], callers,
                                   street, sims=600, seed=seed)
        if eq is None and audit is not None:
            audit.update(complete=False, reason='betting_range_mc_unavailable')
    return eq


# 벳·레이즈 뒤 남는 스택이 콜 받은 팟의 이 비율 이하이면 사람은 그냥 올인한다
# (예: 4,600 벳에 34,000 레이즈하고 5,395 남기기 — 남은 칩으로는 폴드할 수 없다).
ALLIN_SNAP_FRAC = 0.30


def snap_allin(new_chips, stack, pot_if_called):
    """이번 액션에 새로 넣을 칩(new_chips) 뒤 남는 스택이 너무 적으면 스택 전체를 반환."""
    behind = float(stack) - float(new_chips)
    if 0 < behind <= ALLIN_SNAP_FRAC * max(0.0, float(pot_if_called)):
        return float(stack)
    return float(new_chips)


def response_raise_target(pot, tocall, mult, stack, hero_contrib):
    """응답 레이즈의 street 총 contribution target 좌표. 반환 (target, 최대 target).

    hero 가 이미 넣은 칩(hero_contrib)을 target 좌표에 다시 더한다(실행 층 환산).
    """
    _hc = hero_contrib
    _base = int(round((pot + 2*tocall)*mult/100))*100
    _max_target = float(stack) + _hc
    _new = min(float(stack), float(_base))
    _new = snap_allin(_new, stack, pot + 2*_new - tocall)
    return min(_max_target, _hc + _new), _max_target


def intent_chip_amount(pot, size_frac, stack):
    """판단 층이 정한 사이즈(팟 배수)를 칩으로 환산(100 단위, 스택 상한). 실행 층."""
    amt = min(stack, int(round(pot*size_frac/100))*100)
    if amt <= 0:
        return amt
    snapped = snap_allin(amt, stack, pot + 2*amt)
    return stack if snapped >= stack else amt


def shape_planned_target(amount, profile, pot, actor_cap, seed=None):
    """Apply human sizing habit inside PLAN, before execution legality.

    Returns (target, provenance). Exact all-in targets are never reduced by
    jitter. Round/session remain responsible only for min-raise/legal/effective
    caps after this function.
    """
    a=float(amount or 0.0)
    cap=max(0.0,float(actor_cap or 0.0))
    meta={'called':False,'changed':False,'before':a,'after':a,'source':'plan'}
    if a<=0 or (cap>0 and a>=cap-1e-9):
        return a,meta
    rng=random.Random(seed)
    shaped=float(PS.shape_size(a,profile.get('type'),rng,pot=pot,
                               profile=profile))
    meta.update({'called':True,'changed':abs(shaped-a)>1e-9,'after':shaped})
    if profile.get('concepts') and profile.get('temper'):
        meta.update(mode='planned_amount_variation',
                    jitter=PS.profile_sizing_signature(profile)['jitter'])
    return shaped,meta

def act_with_plan(hero, board, profile, plan_state, pot, tocall, stack, street,
                  initiative=True, opp_range=None, bf=1.0, seed=None,
                  n_opp=1, to_act_behind=0, read=None, opp_est=None,
                  opp_ranges=None, facing_seat=None,
                  can_raise=True, checkraise_seed=None, checkraise_size_seed=None,
                  facing_size_frac=None, hero_contrib=0, response_kind=None,
                  response_context=None, call_value=None,
                  size_shape_seed=None):
    """계획을 스트리트에 걸쳐 실행. 체크레이즈·커밋 판단 포함."""
    # 사이즈 습관 RNG 는 결정적이어야 한다. 세션은 항상 size_shape_seed 를 넘기지만,
    # 직접 호출에서 빠지면 random.Random(None)(OS 엔트로피)이 돼 같은 입력이
    # 다른 금액을 냈다(stage10 f3 판정). seed 에서 파생한다.
    if size_shape_seed is None and seed is not None:
        size_shape_seed = _zlib.crc32(('%s|size_shape' % seed).encode())
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
    plan_state['_last_size_shape'] = {
        'called': False, 'changed': False, 'before': None, 'after': None,
        'source': 'plan'}
    plan = plan_state['plan']
    if opp_est is None:
        opp_est = plan_state.get('opp_est')      # 계획에 실린 추정치를 이어 쓴다
    # (예전에 `frac = SIZING[plan].get(street, 0.0)` 이 여기 있었다. 대입만
    #  하고 함수 안에서 한 번도 읽지 않는 죽은 줄이었고, SIZING 에 없는
    #  계획이 오면 KeyError 만 낼 수 있었다. 사이즈는 decide_size 가 정한다.)
    committed = spr(stack, pot) < 1.2          # 커밋 구간
    # 시간 모델용: 이 응답에서 실제로 비교한 eq/need(관측 전용). 이전 결정 값이 남지 않게 비운다.
    plan_state.pop('_last_response_boundary', None)
    if response_kind is not None:
        plan_state['_last_response_kind'] = response_kind
    if response_context is not None:
        plan_state['_last_response_context'] = dict(response_context)

    if tocall > 0:
        _mc_audit = {}
        eq = (None if plan_state.get('equity_status') == 'unavailable_not_negative_ev'
              else response_equity(hero, board, profile, opp_range, opp_ranges,
                                   n_opp, opp_est, pot, tocall, street,
                                   response_context, seed, audit=_mc_audit))
        if eq is None:
            details = dict(_mc_audit)
            if plan_state.get('equity_unavailable'):
                details['plan'] = plan_state['equity_unavailable']
            plan_state['equity_status'] = 'unavailable_not_negative_ev'
            plan_state['equity_unavailable'] = details
            plan_state['_last_response_boundary'] = {
                'eq': None, 'need': None, 'act': 'fold',
                'mathematically_justified': False}
            why = 'MC unavailable; executable fold, NOT verified -EV'
            record_response_plan(plan_state, street, {
                'response_kind': response_kind, 'act': 'fold',
                'target': None, 'eq': None, 'need': None,
                'source': 'equity_unavailable',
                'equity_status': 'unavailable_not_negative_ev',
                'equity_unavailable': details, 'why': why})
            plan_state.setdefault('acts', []).append(why)
            _trace(plan_state, street, 'response', act='fold',
                   source='equity_unavailable', eq=None, need=None, why=why)
            return ('fold', 0), None, None
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
        # 체크레이즈 gate는 오직 "이번 응답이 check -> face bet"인 경우에만 탄다.
        # 같은 스트리트에서 과거에 한 번 체크했다는 이유만으로
        # check -> raise -> opponent re-raise 뒤의 aggressor_backaction까지
        # 다시 체크레이즈 스팟으로 분류하면 안 된다.
        #
        # 판정은 canonical response_kind 하나로 한다(stage9 B5). 세션은 항상
        # kind 를 넘기며(action_events._response_kind), 예전 response_kind=None +
        # checked_before 호환 분기는 직접 호출 전용이라 제거했다.
        _is_checkraise_spot = (response_kind == 'check_then_face_bet')
        _river_nuts_response = river_nut_value_response(
            profile, hero, board, street, opp_range, pot, tocall, stack,
            hero_contrib, response_context, n_opp, can_raise)
        if _is_checkraise_spot and can_raise and _river_nuts_response is None:
            _ckr = checkraise_decision(
                hero, board, profile, plan_state, pot, tocall, stack, street,
                seed=(checkraise_seed if checkraise_seed is not None else seed),
                opp_est=opp_est)
            if _ckr:
                _ckr_rng = random.Random(
                    checkraise_size_seed if checkraise_size_seed is not None else seed)
                _amt = checkraise_size(
                    profile, pot, tocall, stack, board, street, _ckr_rng)
                if (plan in ('bluff_2street', 'semibluff', 'giveup', 'river_bluff')
                        and made_now < 2):
                    _g_ckr = _nonvalue_raise_ev_gate(
                        profile, hero, board, street, opp_range, opp_ranges,
                        n_opp, pot, tocall, stack, hero_contrib,
                        response_context, target=_amt)
                    plan_state['_last_nonvalue_raise_gate'] = dict(_g_ckr)
                    if not _g_ckr.get('allow'):
                        _ckr = False
                        _trace(
                            plan_state, street, 'checkraise_ev_veto',
                            ev=_g_ckr.get('ev'),
                            fold_p=_g_ckr.get('fold_p'),
                            continue_eq=_g_ckr.get('continue_eq'),
                            target=_amt)
                if _ckr:
                    _cap = float(stack) + float(hero_contrib or 0.0)
                    _amt, _shape = shape_planned_target(
                        _amt, profile, pot, _cap, seed=size_shape_seed)
                    plan_state['_last_size_shape'] = dict(_shape)
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
        # 체크 후 마주한 벳(check_then_face_bet)이면 generic reraise/bluff raise는 금지한다.
        # raise 권리가 닫힌 incomplete-allin 상태도 계획 단계에서 raise를 제거한다.
        _direct_raise = bool(can_raise and (
            not _is_checkraise_spot or _river_nuts_response is not None))
        act, mult, need, why = decide_response(
            profile, hero, board, street, plan, plan_state, eq, need,
            made_now, opp_range, pot, tocall, stack, committed, rng,
            allow_raise=_direct_raise,
            call_eq=_call_eq, call_need=_call_need,
            opp_ranges=opp_ranges, n_opp=n_opp,
            rel_seed=(_zlib.crc32(('%s|f7b_rel_response' % seed).encode())
                      if seed is not None else None),
            response_context=response_context,
            hero_contrib=hero_contrib)
        plan_state['_last_response_boundary'] = {
            'eq': float(_call_eq if (_call_eq is not None and _call_need is not None) else eq),
            'need': float(need), 'act': act}
        _source = ('river_nuts_value' if _river_nuts_response is not None else
                   'checkraise_declined' if _is_checkraise_spot else 'generic_response')
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
            amt, _max_target = response_raise_target(pot, tocall, mult, stack, _hc)
            _nuts_size = plan_state.get('_last_river_nuts_value')
            if _nuts_size and _nuts_size.get('act') == 'raise':
                amt = min(_max_target, float(_nuts_size['target']))
            # call target도 street 총 contribution 좌표다.
            # amt를 단순 tocall과 비교하면 이미 넣은 칩만큼 좌표가 어긋난다.
            _call_target = _hc + float(tocall)
            if amt <= _call_target:
                _rp['act'] = 'call'
                _rp['target'] = float(_call_target)
                _rp['why'] = _rp['why'] + ' | raise target <= call target → call'
                record_response_plan(plan_state, street, _rp)
                return ('call', tocall), eq, need
            if _nuts_size and _nuts_size.get('act') == 'raise':
                _shape = {'called': False, 'changed': False, 'before': amt,
                          'after': amt, 'source': 'river_nuts_value'}
            else:
                amt, _shape = shape_planned_target(
                    amt, profile, pot, _max_target, seed=size_shape_seed)
            plan_state['_last_size_shape'] = dict(_shape)
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
    amt = intent_chip_amount(pot, it['size'], stack)
    if amt <= 0:
        # 의도는 벳인데 칩으로 환산하니 0이 됐다 (팟이 작아 반올림 소실).
        # 이건 판단 변경이 아니라 환산 한계이므로 그 사실을 남긴다.
        plan_state.setdefault('deviations', []).append(
            {'street': street, 'planned': 'bet', 'executed': 'check',
             'why': '사이즈 %.2f팟이 최소단위 미만' % it.get('size', 0)})
        return ('check', 0), None, None
    _cap = float(stack) + float(hero_contrib or 0.0)
    amt, _shape = shape_planned_target(
        amt, profile, pot, _cap, seed=size_shape_seed)
    plan_state['_last_size_shape'] = dict(_shape)
    return ('bet', int(amt)), None, None


def _checkraise_value_floor_probability(plan_probability, rel, skill, aggression):
    """Combine a motive probability with the existing current-strength floor."""
    value_band = max(0.0, min(1.0, (rel - 0.72) / 0.22))
    probability = max(plan_probability, (0.10 + 0.11*skill) * value_band)
    probability *= (0.7 + 0.05*aggression)
    return probability


def checkraise_draw_street_probability(plan, rel, outs, skill, aggression):
    """Flop/turn checkraise motive: a future draw may support a semibluff.

    Same poker question and formula on these two streets. This pure producer
    consumes the street-selected skill and never samples the decision RNG.
    """
    probability = 0.0
    if plan == 'trap':
        probability = 0.55 + 0.12*skill
    elif plan == 'semibluff' and outs >= 8:
        probability = 0.06 + 0.115*skill
    elif plan == 'bluff_2street':
        probability = 0.03 + 0.05*skill
    return _checkraise_value_floor_probability(probability, rel, skill, aggression)


def checkraise_river_probability(plan, rel, skill, aggression):
    """Terminal checkraise motive: no future draw/semibluff branch.

    The legacy bluff_2street label is intentionally retained. Adding a
    river_bluff branch would be a strategy change, not semantic extraction.
    """
    probability = 0.0
    if plan == 'trap':
        probability = 0.55 + 0.12*skill
    elif plan == 'bluff_2street':
        probability = 0.03 + 0.05*skill
    return _checkraise_value_floor_probability(probability, rel, skill, aggression)


def draw_completion_supports_value(made, rel):
    """Existing completion evidence, shared by turn and terminal river policy.

    This is a policy predicate, not an exact claim that the original draw hit.
    Street-specific outcomes (especially missed-draw river bluffs) stay separate.
    """
    return made >= 4 or rel >= 0.62


def strength_improvement_supports_value(rel, previous_rel):
    """Promotion evidence: already strong, or increased into the value band.

    previous_rel 은 plan_state 에 반올림(2자리)으로 저장된 값이다. '올랐는가'는
    같은 정밀도로 비교한다 — 원값 0.7240 이 저장값 0.72 보다 크다고 '상승'으로
    읽던 오판을 막는다(베타 A #5 와 같은 정밀도 불일치).
    """
    return rel >= 0.88 or (rel >= 0.70 and round(rel, 2) > previous_rel)


def checkraise_street_skill(profile, street):
    """체크레이즈 숙련(0~3 스케일)을 street 별 개념에서 공급(ledger L149).

    flop → checkraise_flop, turn → checkraise_turn, river → checkraise_river.
    기존 생성 프로필은 새 두 키가 없으므로 persona.sk()가 checkraise_late로
    fallback해 행동을 보존한다. 결정 확률 식
    (checkraise_draw_street_probability / checkraise_river_probability)과
    분리된 '공급' 질문이다. 라벨 기반 프로필은 아키타입 표를 쓴다.
    """
    import archetypes as _A
    if profile.get('concepts'):
        return PS.sk(profile, PS.street_concept('checkraise', street))/3.33
    T = profile.get('type')
    return _A.skill(T, 'checkraise') if T in _A.ARCHETYPES else 2


def checkraise_decision(hero, board, profile, plan_state, pot, tocall, stack, street,
                        seed=None, opp_est=None):
    """체크 후 벳을 맞았을 때 레이즈할지. 개념 보유·성향·강도의 함수."""
    import archetypes as _A
    rng = random.Random(seed)
    sk = checkraise_street_skill(profile, street)
    if sk <= 0.2: return False
    plan = plan_state.get('plan')
    rel = plan_state.get('rel', 0.5)
    outs = plan_state.get('outs', 0)
    if street == 'river':
        p = checkraise_river_probability(plan, rel, sk, profile.get('aggr', 5))
    else:
        # Flop and turn ask the same draw/value question here. Their capability
        # sources remain distinct via street_concept above; do not clone logic.
        p = checkraise_draw_street_probability(
            plan, rel, outs, sk, profile.get('aggr', 5))
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
                 prior_pf=None, pot_layers=None, opp_ranges=None,
                 opp_range_meta=None, call_ev_shadow=None,
                 calloff_decision_seed=None, cold_context=None,
                 cold_decision_seed=None):
    """프리플랍 판단 층. 액션과 함께 **이 핸드를 어떻게 칠 것인가**를 남긴다.

    예전에는 preflop.py 의 세 함수(open/iso/defend)가 각자 액션만 내고 끝났다.
    그래서 '왜 3벳했는가'가 플랍 계획에 이어지지 않았고,
    포스트플랍 계획이 매번 백지에서 시작했다.

    반환: (act, size_bb, plan_seed)
      plan_seed 는 포스트플랍 계획의 출발점이 되는 사전 정보다.
    """
    import preflop as _pf
    _calloff_compare = None
    _calloff_consumer = None
    _cold_audit = None
    # 상대 정보가 프리플랍 레인지부터 움직인다.
    # 예전에는 preflop_plan 이 opp_est 를 아예 안 받아서,
    # 상대가 3벳에 과하게 접는 걸 알아도 3벳 레인지가 안 넓어졌다.
    # 잘 접는 상대의 오픈에는 3벳을 넓히고, 안 접는 상대에겐 좁힌다.
    # 실제 반영은 defend_decision(exploit=rd) 안의 역치 보정에서 이뤄진다.
    rd = PS.read_opponent(profile, opp_est)
    _pf.take_timing_bound()          # 시간 모델용 경계 기록을 이 결정 것으로만 받는다
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
    elif opener_allin and not can_raise and float(to_call_bb or 0) > 0:
        # An all-in call/fold is an incremental-EV question, not a vs-open
        # defend-percentile question. Deliberately bypass defend_decision,
        # gto.defend_pct, calloff_cap and shared decision RNG entirely.
        role = 'defend'
        _sh = dict(call_ev_shadow or {})
        _exact_hu_icm = dict(_sh.get('exact_hu_icm') or {})
        _spot_bf = float(_exact_hu_icm.get('equivalent_bubble_factor', bf))
        _layer_j = _pf.calloff_layer_judgment(
            profile, _sh, bubble_factor=_spot_bf,
            seed=calloff_decision_seed)
        if _layer_j is None:
            # Incomplete input is NOT evidence of -EV and must never be
            # presented as a successful mathematical fold. The engine needs
            # a legal action; explicitly mark its conservative fallback.
            a, sz = 'fold', 0.0
            _calloff_consumer = {
                'eligible': True, 'strategy_consumer': False,
                'selected_action': 'fold',
                'decision_quantity': 'unverified_missing_calloff_equity',
                'missing_equity_layers': list(
                    _sh.get('missing_equity_layers') or []),
                'incomplete_reasons': dict(
                    _sh.get('incomplete_reasons') or {}),
                'equity_status': 'unavailable_not_negative_ev',
                'legacy_evaluated': False,
                'mathematically_justified': False,
                'fallback_reason': 'missing_pot_or_range_evidence',
            }
            _pf_timing = {'kind': 'calloff_evidence_missing'}
        else:
            a = _layer_j['layer_action']
            sz = float(to_call_bb or 0) if a == 'call' else 0.0
            _calloff_consumer = dict(_layer_j)
            _calloff_consumer.update({
                'eligible': True, 'strategy_consumer': True,
                'legacy_action': None, 'legacy_evaluated': False,
                'selected_action': a, 'selected_size_bb': sz,
                'gate_role': 'diagnostic_only',
                'decision_quantity': (
                    'perceived_layer_equity_vs_spot_icm_price'
                    if _exact_hu_icm else 'perceived_layer_equity_vs_price'),
                'objective_unconditional_bf': float(bf),
                'objective_spot_bf': float(_spot_bf),
                'icm_pricing_basis': (
                    'terminal_hu_exact_outcome_prices'
                    if _exact_hu_icm
                    else 'generic_bf_approximation_not_spot_validated'),
                'icm_fallback_risk': (
                    None if _exact_hu_icm
                    else 'other_tables_or_nonterminal_or_missing_field_data'),
                'exact_hu_icm': dict(_exact_hu_icm) if _exact_hu_icm else None,
                # A complete layer is NOT a confidence interval. Even an
                # exact payout ICM model cannot certify the unarchived
                # opponent range or finite-MC equity point estimate.
                'mathematically_justified': False,
                'conditional_point_estimate_action': True,
                'objective_icm_tie_verdict_conditional': (
                    _exact_hu_icm.get('objective_action_with_fixed_equity')
                    if _exact_hu_icm else None),
                'estimate_status': 'point_estimate_sampling_and_range_error_unbounded',
            })
            _pf_timing = {'kind': 'calloff_layer',
                          'eq': _layer_j.get('layer_effective_equity'),
                          'need': _layer_j.get('perceived_required_equity')}

    else:
        # Re-raise 판단에서 핵심은 '마지막 aggressor 한 명'이 아니라
        # 현재 살아 있는 seat-keyed range 전체다.
        #
        # P7 cold path(아직 행동 전 open+re-raise)는 기존 계약을 유지하고,
        # 이미 open/call/3bet 했던 플레이어의 backaction에서도 2개 이상의
        # 살아 있는 상대 range가 있으면 같은 multiway 판단을 실제로 소비한다.
        _cc = dict(cold_context or {})
        _live_ranges = {
            k: v for k, v in (opp_ranges or {}).items() if v
        }
        # 직전 레이저가 올인이어도 다른 생존 상대가 남아 raise 가 가능하면
        # (예: UTG+1 open → BTN 17bb 올인 → BB, 오프너가 아직 뒤에 있음)
        # 순수 calloff 경로(can_raise=False 전용)에도, multiway 경로에도
        # 들어가지 못해 일반 percentile 디펜스로 떨어졌다. 그 경로는 6bb 이상의
        # 가격을 보지 못해 17bb 올인을 6bb 3벳처럼 받아 K9s 가 콜했다
        # (audit9 HAND 36). 두 상대 range 와 실제 가격을 보는 판단을 쓴다.
        _allin_ok = (not opener_allin) or bool(can_raise)
        _use_cold = bool(
            raise_level >= 2 and not prior_pf and _allin_ok
            and _cc.get('original_opener_seat') is not None
            and _cc.get('reraiser_seat') is not None)
        _use_multiway_backaction = bool(
            raise_level >= 2 and prior_pf and _allin_ok
            and len(_live_ranges) >= 2)
        # A limper facing an isolation raise plus a caller pays only the
        # incremental price. Reuse the existing N-way evidence consumer
        # instead of discarding this context into a first-open rank filter.
        _use_limp_backaction = bool(
            raise_level == 1 and prior_pf
            and prior_pf.get('pf_act') == 'limp' and _allin_ok
            and len(_live_ranges) >= 2
            and pot_bb is not None and to_call_bb is not None)

        # 이미 올인한 상대(폴드 불가) — 공격 근거 계산에서 뺀다.
        _locked_seats = set()
        for _ly in (pot_layers or []):
            for _o in (_ly.get('locked_allin_opponents') or []):
                _locked_seats.add(str(_o))
        if _use_cold:
            _op_seat = _cc.get('original_opener_seat')
            _rr_seat = _cc.get('reraiser_seat')
            a, sz, _cold_audit = _pf.cold_reraise_decision(
                profile, pos, aggressor_pos, hand, bb, open_bb,
                n_callers, rng, raise_level=raise_level, stack_bb=bb,
                exploit=rd, bf=bf, seats=seats, ante=ante,
                can_raise=can_raise, pot_bb=pot_bb, to_call_bb=to_call_bb,
                original_opener_range=(opp_ranges or {}).get(_op_seat),
                reraiser_range=(opp_ranges or {}).get(_rr_seat),
                players_behind=len(_cc.get('players_behind') or []),
                decision_seed=cold_decision_seed,
                locked_keys=[k for k, st_ in (('original_opener', _op_seat),
                                              ('reraiser', _rr_seat))
                             if str(st_) in _locked_seats])
        elif _use_multiway_backaction or _use_limp_backaction:
            # 이미 opponent_ranges에 들어간 좌석은 multiway equity가 그 위험을
            # 직접 포함한다. players_behind에 또 세면 같은 상대를 두 번 조인다.
            _pending_behind = [
                x for x in (_cc.get('players_behind') or [])
                if x not in _live_ranges
            ]
            a, sz, _cold_audit = _pf.multiway_reraise_decision(
                profile, pos, aggressor_pos, hand, bb, open_bb,
                n_callers, rng, raise_level=raise_level, stack_bb=bb,
                exploit=rd, bf=bf, seats=seats, ante=ante,
                can_raise=can_raise, pot_bb=pot_bb, to_call_bb=to_call_bb,
                opponent_ranges=_live_ranges,
                players_behind=len(_pending_behind),
                decision_seed=cold_decision_seed,
                locked_keys=[k for k in _live_ranges
                             if str(k) in _locked_seats])
            _cold_audit['context_kind'] = (
                'limp_vs_isolation_multiway' if _use_limp_backaction
                else 'backaction_multiway_reraise')
            _cold_audit['pending_behind_seats'] = [
                str(x) for x in _pending_behind]
        else:
            a, sz = _pf.defend_decision(
                profile, pos, aggressor_pos, hand, bb, open_bb,
                n_callers, rng, raise_level=raise_level,
                stack_bb=bb, tilt=tilt, field_q=field_q,
                exploit=rd, bf=bf, seats=seats, ante=ante,
                payout_flat=payout_flat,
                reentry=reentry, progress=progress,
                opener_allin=opener_allin, can_raise=can_raise,
                pot_bb=pot_bb, to_call_bb=to_call_bb)
        role = 'defend'

    # Preserve a dedicated price/ICM timing boundary. Only general defend
    # and open/iso decisions consume the existing preflop timing tracer.
    _recorded_timing = _pf.take_timing_bound()
    if _calloff_consumer is None:
        _pf_timing = _recorded_timing

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
    elif (_cold_audit and
          _cold_audit.get('context_kind') == 'backaction_multiway_reraise'):
        if _prev_role == 'open':
            _decision_kind = 'opener_multiway_backaction'
        elif _prev_act in ('call', 'limp', 'check'):
            _decision_kind = 'caller_multiway_backaction'
        else:
            _decision_kind = 'reraiser_multiway_backaction'
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
        # F8-D6-B provenance: full combo maps stay transient; seed stores compact seat-keyed proof.
        'pf_opp_ranges_n': {
            str(k): len(v) for k, v in (opp_ranges or {}).items()},
        'pf_opp_ranges_mass': {
            str(k): R.range_mass(v) for k, v in (opp_ranges or {}).items()},
        'pf_opp_ranges_sig': {
            str(k): _range_sig(v) for k, v in (opp_ranges or {}).items()},
        'pf_opp_range_meta': {
            str(k): dict(v) for k, v in (opp_range_meta or {}).items()},
        # F8-D6-C objective preflop call-EV shadow. No action consumer yet.
        'pf_call_ev_shadow': (
            dict(call_ev_shadow) if call_ev_shadow is not None else None),
        'pf_calloff_compare': (
            dict(_calloff_compare) if _calloff_compare is not None else None),
        'pf_calloff_consumer': (
            dict(_calloff_consumer) if _calloff_consumer is not None else None),
        # P7 dedicated cold-vs-reraise judgment provenance.
        'pf_cold_context': dict(cold_context or {}) if cold_context else None,
        'pf_cold_audit': dict(_cold_audit) if _cold_audit is not None else None,
        # D2 provenance: later streets must not rebuild an all-in player's
        # preflop range from current stack=0.
        'pf_stack_bb': float(bb or 0.0),
        'pf_initiative': a in ('raise', '3bet', 'shove'),
        'pf_multiway': (n_callers + n_limpers) >= 2,
        'pf_hand_pct': _pf.pct(hand),
        'pf_timing': _pf_timing,
        'money_open': dict(money_open or {}) if role == 'open' else None,
    }
    # Human sizing habit is part of the plan, not execution.  This is
    # deliberately last: historically session shaped immediately after
    # preflop_plan returned, so using the same rng here preserves consumption.
    _pf_shape = None
    if (a not in ('fold','check','limp','call','shove')
            and bb_chips and float(sz or 0.0) > 0):
        _before = float(bb_chips) * float(sz)
        _after = float(PS.shape_size(
            _before, profile.get('type'), rng, pot=None,
            profile=profile))
        sz = _after / float(bb_chips)
        _pf_shape = {
            'called': True, 'changed': abs(_after-_before)>1e-9,
            'before': _before, 'after': _after, 'source': 'plan'}
        if profile.get('concepts') and profile.get('temper'):
            _pf_shape.update(mode='planned_amount_variation',
                             jitter=PS.profile_sizing_signature(profile)['jitter'])
    seed_info['pf_size_shape'] = _pf_shape
    return a, sz, seed_info


def update_plan(state, hero, board, my_range, opp_range, profile, pot, stack,
                street, seed, n_opp, behind, prev_board, oop, initiative,
                opp_est=None, opp_stack_bb=None, tilt=0.0, first=False,
                pf_seed=None, bb_chips=None,
                oop_vs_aggr=None, oop_legacy_abs=None, opp_ranges=None,
                opp_checked_prev=None, opp_ests=None, opp_stack_bbs=None):
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

    if first or state is None or (state or {}).get('equity_status') == 'unavailable_not_negative_ev':
        st = make_plan(hero, board, my_range, opp_range, profile, pot, stack, street,
                       seed=seed, n_opp=n_opp, to_act_behind=behind,
                       oop_vs_aggr=oop_vs_aggr, initiative=initiative,
                       opp_est=opp_est, opp_stack_bb=opp_stack_bb, tilt=tilt,
                       bb_chips=bb_chips, oop_legacy_abs=oop_legacy_abs,
                       opp_ranges=opp_ranges, opp_ests=opp_ests,
                       opp_stack_bbs=opp_stack_bbs)
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

    if st.get('equity_status') == 'unavailable_not_negative_ev':
        return set_intent(st, street, mk_intent(
            'check', 0.0, 'MC unavailable; no verified betting EV'))

    # 계획 이력은 라벨과 별개로 이어진다.
    if prev:
        for k in ('intents', 'deviations', 'streets', 'refreshed', 'bet_streets',
                  'executed_actions', 'response_plans', '_last_response_plan',
                  'plan_since', 'plan_made', '_rsig', '_opps_sig'):
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
    _rsig = _decision_range_sig(opp_range)
    _first = (street != st.get('street_made')
              and street not in (st.get('refreshed') or []))
    _opps_sig = _opp_ranges_signature(opp_ranges)
    _range_moved = (st.get('_rsig') is not None and st.get('_rsig') != _rsig)
    _pools_moved = (bool(_opps_sig) and st.get('_opps_sig') is not None
                    and st.get('_opps_sig') != _opps_sig)
    if _first or _range_moved or _pools_moved:
        st = refresh(st, hero, board, opp_range, profile, pot, stack, street,
                     n_opp, seed=seed, opp_est=opp_est, my_range=my_range,
                     opp_ranges=opp_ranges, opp_ests=opp_ests)
        if st.get('equity_status') == 'unavailable_not_negative_ev':
            return set_intent(st, street, mk_intent(
                'check', 0.0, 'MC unavailable; no verified betting EV'))
        if _first:
            st.setdefault('refreshed', []).append(street)
        st = turn_value_reassessment(
            st, hero, board, profile, opp_range, n_opp=n_opp, opp_ranges=opp_ranges,
            rng=rng)
    st['_rsig'] = _rsig
    st['_opps_sig'] = _opps_sig

    st = river_fix(
        st, hero, board, profile, opp_range, rng,
        n_opp=n_opp, opp_ranges=opp_ranges)

    # F2/probe context must exist **before** attach_intent.
    # Session used to write this after update_plan returned, so the already-frozen
    # current-action intent could not react to the previous aggressor checking.
    if opp_checked_prev is not None:
        st['opp_checked_prev'] = bool(opp_checked_prev)

    st['plan'] = _allowed(profile, st['plan'], rng, street=street)

    # 이 라벨을 언제 채택했는가. 예산(BUDGET)을 세는 기준점이다.
    # 플랍에 bluff_2street 으로 치다가 턴에 value_2street 으로 승격한 사람은
    # 플랍의 벳을 새 계획의 예산에서 까면 안 된다 — 그건 다른 계획의 지출이었다.
    if not prev or prev.get('plan') != st.get('plan') or not st.get('plan_since'):
        st['plan_since'] = street
        # 채택 시점의 완성 강도. 예산 소진 후 승격은 '이 계획을 세운 뒤 강도가
        # 올랐는가'를 본다(아래 refresh 참고).
        st['plan_made'] = st.get('made') or 0

    # 의도는 무저항 시점에만, 한 번만 확정한다.
    _intent_pick = (
        select_field_opponent(
            profile,
            opp_ests if isinstance(opp_ests, dict) else st.get('opp_ests'),
            street, 'fold_constraint')
        if int(n_opp or 1) > 1 else None)
    _intent_est = _intent_pick.get('est') if _intent_pick else opp_est
    if intent_of(st, street) is None:
        st = attach_intent(st, hero, board, my_range, opp_range, profile,
                           pot, stack, street, rng, n_opp, behind,
                           oop, initiative, _intent_est,
                           oop_vs_aggr=oop_vs_aggr,
                           oop_legacy_abs=oop_legacy_abs,
                           opp_ranges=opp_ranges, tilt=tilt)
    return st


def continue_range_call_equity(hero, board, profile, street, size_frac,
                               opp_range, opp_ranges, n_opp):
    """'이 사이즈로 벳했을 때 계속하는 레인지' 대비 equity 와 그 레인지 support 수.

    river 얇은 밸류(river_value_reassessment)와 개선된 블러프 재판정(refresh)이
    같은 질문을 같은 식으로 물었다(ledger L119). 멀티웨이는 seat 별 continue
    range 가 전부 있을 때만, 헤즈업은 opp_range 의 continue range 로 잰다.
    레인지 근거가 없으면 (None, None) — 새 값을 지어내지 않는다.
    반환 n 은 콤보 support 수이며 hero 카드 호환 여부를 거르지 않은 기록값이다.
    """
    _eq = None
    _n = None
    if int(n_opp or 1) > 1 and isinstance(opp_ranges, dict):
        _cont_map = {}
        for _seat, _rr in opp_ranges.items():
            if _rr:
                _cr = R.perceived_continue_range(
                    _rr, board, street, size_frac, profile)
                if _cr:
                    _cont_map[_seat] = _cr
        if len(_cont_map) == int(n_opp or 1):
            _eq = _eq_vs(
                hero, board, opp_range, int(n_opp or 1),
                sims=500, opp_ranges=_cont_map)
            _n = sum(len(_r) for _r in _cont_map.values())
    elif opp_range:
        _cr = R.perceived_continue_range(
            opp_range, board, street, size_frac, profile)
        if _cr:
            _eq = _eq_vs(hero, board, _cr, 1, sims=500)
            _n = len(_cr)
    return _eq, _n


# 이 rel 이상이면 '분명한 밸류'다 — 콜 레인지 대비 재평가 없이 계획대로 친다.
# 리버 재평가에 있던 리터럴을 턴 재평가와 공유하려고 이름을 붙였다(값 불변).
CLEAR_VALUE_REL = 0.92
# 리버 얇은 밸류 v2 (FLOP_CLAIM_BASELINE.md 7절): 쇼다운 계획도 재평가하고,
# 콜 받아도 앞서는 자리는 숙련만큼 친다.
RIVER_THIN_VALUE_V2 = True


TURN_THIN_VALUE_V1 = True


def turn_value_promotion(st, hero, board, profile, opp_range, rng,
                         n_opp=1, opp_ranges=None):
    """턴 팟컨트롤·쇼다운 계획을, 콜 받아도 앞서면 2스트리트 밸류로 올린다.

    turn_value_reassessment 는 밸류 → 팟컨트롤 **강등**만 했다. 플랍부터 팟컨트롤·
    쇼다운이던 메이드 핸드는 블랭크 턴에 콜 레인지보다 앞서도 턴 사이즈가 0 이라
    항상 체크했다(블랭크 턴 rel 0.5~0.7 벳 32%). 사용자 기준(2026-10-06):
    블랭크 턴, 플랍 작은 벳-콜, K9 탑페어 → 더 약한 Kx·드로우·Ax·낮은 페어에게
    2/3 밸류. 무서운 턴은 콜 레인지 대비 eq 가 내려가 자연히 팟컨트롤에 남는다.
    리버 v2 와 같은 확률식: (0.10+0.85·개념)·여유·밴드.
    """
    if (not TURN_THIN_VALUE_V1 or rng is None or len(board) != 4
            or st.get('plan') not in ('pot_control', 'showdown')
            or not (profile and profile.get('concepts'))):
        return st
    rel = st.get('rel') or 0.0
    if rel >= CLEAR_VALUE_REL or bot.made_strength(hero, board) < 1:
        return st
    _size = float(SIZING['value_2street']['turn'])
    _eq, _n = continue_range_call_equity(
        hero, board, profile, 'turn', _size, opp_range, opp_ranges, n_opp)
    if not ahead_when_called(_eq):
        return st
    _tv = PS.sk(profile, PS.street_concept('thin_value', 'turn'))/10.0
    _band = max(0.0, min(1.0, (rel - 0.40)/0.15))
    _margin = max(0.0, min(1.0, 0.4 + (float(_eq) - 0.5)/0.08))
    if rng.random() < (0.10 + 0.85*_tv) * _margin * _band:
        st = dict(st)
        st['turn_call_eq'] = round(float(_eq), 3)
        st['turn_call_range_n'] = _n
        st['plan'] = 'value_2street'
        st['plan_goal'] = 'value_2street'
        st['plan_since'] = 'turn'
        st['why'] = (st.get('why') or []) + [
            '턴: 팟컨트롤이나 콜 레인지 상대 eq %.2f ≥ 0.50 → 2스트리트 밸류(개념 %.1f)'
            % (float(_eq), _tv*10)]
    return st


def turn_value_reassessment(st, hero, board, profile, opp_range,
                            n_opp=1, opp_ranges=None, rng=None):
    """턴의 2스트리트 밸류: 계획한 턴 사이즈로 쳤을 때 **콜당해도 앞서는가**(베타 A #4).

    리버에는 이 질문(river_value_reassessment)이 있는데 턴에는 없어서, 플랍에
    '중간강도 → 얇은 밸류'로 세운 계획이 턴 카드로 밀린 뒤에도 강등 문턱
    (rel 0.30)만 넘으면 계속 쳤다(예: KK 가 J♦T♦9♦6♣ 에서 rel 0.37 로 베팅).
    콜 레인지 대비 eq 가 손익분기(0.50) 미만이면 팟 컨트롤로 내려 쇼다운 가치를
    지킨다. 근거(콜 레인지)가 없으면 계획을 유지한다 — 턴은 마지막 스트리트가
    아니고, 콜 레인지를 지어내지 않는다.
    """
    if len(board) == 4 and st.get('plan') in ('pot_control', 'showdown'):
        return turn_value_promotion(st, hero, board, profile, opp_range, rng,
                                    n_opp=n_opp, opp_ranges=opp_ranges)
    if len(board) != 4 or st.get('plan') != 'value_2street':
        return st
    if (st.get('rel') or 0.0) >= CLEAR_VALUE_REL:
        return st
    _size = float(SIZING['value_2street']['turn'])
    _eq, _n = continue_range_call_equity(
        hero, board, profile, 'turn', _size, opp_range, opp_ranges, n_opp)
    st = dict(st)
    st['turn_call_eq'] = None if _eq is None else round(float(_eq), 3)
    st['turn_call_range_n'] = _n
    if _eq is not None and not ahead_when_called(_eq):
        st['plan'] = 'pot_control'
        st['why'] = (st.get('why') or []) + [
            '턴: 전체 rel %.2f지만 콜 레인지 상대 eq %.2f < 0.50 → 밸류 아님, 팟 컨트롤'
            % (st.get('rel') or 0.0, float(_eq))]
    return st


def river_value_reassessment(st, hero, board, profile, opp_range, rng,
                             n_opp=1, opp_ranges=None):
    """Terminal value question: value when called, otherwise showdown/giveup.

    Receives the copied river state; no extra copy, sampling or skill lookup.
    """
    rel = st.get('rel', 0.5)
    made = bot.made_strength(hero, board)

    # River is terminal: protection/future-equity is gone.  A turn
    # value_2street label therefore cannot by itself authorize one more bet.
    # Re-evaluate whether this is still clear value, a learned thin-value
    # spot, or simply showdown value.
    #
    # Keep the existing semantic bands; the bug was the fallback direction.
    # Previously, failing the thin-value gate returned the old value_2street
    # plan, so a hand *not good enough for thin value* still bet as value.
    if rel >= CLEAR_VALUE_REL:
        # 분명한 밸류는 친다. 그런데 2스트리트 계획이 플랍·턴에 예산을 다
        # 썼으면 리버 사이즈가 0 이라 '사이즈 0 → 체크'가 됐다 — 밸류라고
        # 판정하고 치지 않는 모순(베타 A, #5 와 같은 계열).
        if (st.get('plan') == 'value_2street'
                and (budget_left(st, 'value_2street', 'river') or 0) <= 0):
            st['plan'] = 'value_3street'
            st['plan_goal'] = 'value_3street'
            st['why'] = (st.get('why') or []) + [
                '리버: 2스트리트 예산 소진이나 분명한 밸류(rel %.2f) → 리버 밸류' % rel]
        return st

    if profile and profile.get('concepts') and rng is not None and made >= 1:
        _tv = PS.sk(profile, 'thin_value_river')/10.0
        _band = (max(0.0, min(1.0, (rel - 0.48)/0.30))
                 * max(0.0, min(1.0, (CLEAR_VALUE_REL - rel)/0.20)))

        # Thin value asks a different question from "am I ahead of their
        # whole range?": am I still ahead **when called**?
        # Use the same canonical continue-range model at the actual
        # thin_river base size (42% pot).  This prevents medium showdown
        # hands from betting merely because folds make the *overall* range
        # look weak.
        _thin_size = float(SIZING['thin_river']['river'])
        _thin_eq, _thin_n = continue_range_call_equity(
            hero, board, profile, 'river', _thin_size, opp_range, opp_ranges,
            n_opp)

        st['thin_call_eq'] = (
            None if _thin_eq is None else round(float(_thin_eq), 3))
        st['thin_call_range_n'] = _thin_n

        # With no usable range evidence, do not invent a thin-value call
        # range.  Check and take showdown value instead.
        _value_when_called = ahead_when_called(_thin_eq)
        if RIVER_THIN_VALUE_V2 and _thin_eq is not None:
            # 콜 받아도 앞서면 얇은 밸류다. 숙련자는 그 자리를 대부분 치고,
            # 콜 레인지 대비 여유(eq-0.5)가 클수록 더 확실히 친다.
            # 예전 0.75*개념*밴드 는 숙련 5 에서도 최대 ~37% 였고, 밴드 상단 감쇠가
            # rel 0.85~0.92(분명한 밸류 직전)에서 오히려 확률을 깎았다(2026-10-06).
            _band = max(0.0, min(1.0, (rel - 0.40)/0.15))
            _margin = max(0.0, min(1.0, 0.4 + (float(_thin_eq) - 0.5)/0.08))
            _p_thin = (0.10 + 0.85*_tv) * _margin * _band
        else:
            _p_thin = 0.75*_tv*_band
        if (_value_when_called
                and rng.random() < _p_thin):
            st['plan'] = 'thin_river'
            st['why'] = (st.get('why') or []) + [
                '리버: 얇은 밸류(rel %.2f, call-eq %.2f, 개념 %.1f)'
                % (rel, float(_thin_eq), _tv*10)]
            return st
        elif _thin_eq is not None and not _value_when_called:
            st['why'] = (st.get('why') or []) + [
                '리버: 전체 rel %.2f지만 콜 레인지 상대 eq %.2f < 0.50'
                ' → 얇은 밸류 아님'
                % (rel, float(_thin_eq))]

    # If it is not clear value and the learned thin-value judgment did not
    # fire, take the showdown value.  Air is handled by the bluff/giveup
    # paths below; a made hand should not keep firing merely because the
    # previous street called it value_2street.
    if made >= 1:
        st['plan'] = 'showdown'
        st['why'] = (st.get('why') or []) + [
            '리버: 밸류 계획 재평가 → 얇은 밸류 아님(rel %.2f) → 쇼다운'
            % rel]
    else:
        st['plan'] = 'giveup'
        st['why'] = (st.get('why') or []) + [
            '리버: 밸류 계획 근거 소멸(rel %.2f, made 0) → 포기' % rel]
    return st



def river_semibluff_resolution(st, hero, board, profile, opp_range, rng,
                               n_opp=1, opp_ranges=None):
    """Terminal draw question: completed value, showdown, missed-draw bluff/fold."""
    made = bot.made_strength(hero, board)
    rel = st.get('rel', 0.5)
    # 완성 판정. 드로우가 목표 등급(스트레이트 4 이상)에 닿았거나 상대 대비
    # 강해졌을 때만 밸류다. made >= 2 는 보드 페어로도 성립해 원페어 + 보드
    # 페어(rel 0.00)가 '드로우 완성 → 밸류'로 올인했다(audit9 HAND 63).
    if draw_completion_supports_value(made, rel):
        st['plan'] = 'value_2street'
        st['why'] = (st.get('why') or []) + ['리버: 드로우 완성 → 밸류 전환']
        # 완성됐어도 분명한 밸류가 아니면 '콜당했을 때 앞서는가'를 묻는다.
        # 낮은 플러시(55 의 5 하이 플러시, rel 0.36)가 완성만으로 밸류벳했다
        # (베타 A J4). 다른 리버 밸류 후보와 같은 재평가를 거친다.
        if rel < CLEAR_VALUE_REL:
            return river_value_reassessment(
                st, hero, board, profile, opp_range, rng, n_opp, opp_ranges)
        return st
    if made >= 2:
        st['plan'] = 'showdown'
        st['why'] = (st.get('why') or []) + [
            '리버: 드로우 미스, 쇼다운 가치(made %d, rel %.2f) → 쇼다운'
            % (made, rel)]
        return st

    # 미스. 블러프로 갈지 포기할지 — 개념과 블로커가 정한다.
    p_bluff = 0.0
    if profile and profile.get('concepts'):
        _bl = PS.sk(profile, 'bluff')/10.0
        _br = PS.sk(profile, 'barrel_river')/10.0
        p_bluff = 0.10 + 0.55*_bl*_br
        if opp_range:
            # 현재 street 판단층이 계산한 동일 blocker judgment 를 소비한다.
            # 오래된 replay/state 에 raw provenance 가 없을 때만 legacy union 으로
            # 호환 fallback 한다. 여기서 별도 전략 판단을 다시 만들지 않는다.
            _net = st.get('blocker_net_raw')
            if _net is None:
                _net = R.blocker_effect(
                    hero, opp_range, board, 'river', 0.75, False)
            _bg = max(0.0, min(1.0, (PS.sk(profile, 'blocker') - 1.0)/7.0))
            p_bluff *= max(0.35, min(1.80, 1.0 + 4.0*float(_net)*_bg))
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


def river_fix(state, hero, board, profile=None, opp_range=None, rng=None,
              n_opp=1, opp_ranges=None):
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
    _reassess = ('value_2street', 'pot_control', 'block') + (
        ('showdown',) if RIVER_THIN_VALUE_V2 else ())
    if (st.get('plan') == 'showdown'
            and bot.made_strength(hero, board) < 1):
        # 메이드 없는 쇼다운 가치(A하이 등)는 재평가하지 않는다 —
        # giveup 으로 떨어지면 쇼다운 가치가 블러프로 새는 길이 열린다(베타 A #3).
        _reassess = ()
    if st.get('plan') in _reassess:
        if (st.get('plan') == 'showdown' and RIVER_THIN_VALUE_V2
                and st.get('rel', 0.5) >= CLEAR_VALUE_REL):
            # 플랍에서 쇼다운으로 잡은 손이 리버에 분명한 밸류가 됐다.
            st['plan'] = 'value_3street'
            st['plan_goal'] = 'value_3street'
            st['why'] = (st.get('why') or []) + [
                '리버: 쇼다운 계획이나 분명한 밸류(rel %.2f) → 리버 밸류'
                % st.get('rel', 0.5)]
            return st
        return river_value_reassessment(
            st, hero, board, profile, opp_range, rng, n_opp, opp_ranges)

    if st.get('plan') != 'semibluff':
        return st
    return river_semibluff_resolution(st, hero, board, profile, opp_range, rng,
                                      n_opp=n_opp, opp_ranges=opp_ranges)


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


# 계획 → 실행에 필요한 개념(_allowed). street 공유 개념('checkraise')은 _allowed 가
# persona.street_concept 로 지금 street 의 능력으로 해석한다(L157 / L-S9-07).
PLAN_REQUIRED_CONCEPT = {'bluff_2street': 'bluff', 'semibluff': 'semibluff', 'trap': 'checkraise',  # street 별로 해석(_allowed)
                         'block': 'blockbet', 'pot_control': 'potcontrol',
                         'river_bluff': 'barrel_river', 'thin_river': 'thin_value_river'}
# 개념이 부족할 때 내려가는 계획.
PLAN_DOWNGRADE = {'bluff_2street':'giveup','semibluff':'showdown',
                  'trap':'value_3street','block':'value_2street',
                  'pot_control':'showdown',
                  'river_bluff':'giveup','thin_river':'showdown'}


def _allowed(profile, plan, rng=None, street=None):
    """그 개인이 해당 계획을 실행할 개념을 갖고 있는가. 벡터면 연속 확률.

    rng 는 필수다. 예전에는 `(rng or random).random()` 으로 전역 RNG 에 폴백했는데,
    전역 RNG 는 OS 엔트로피로 시드되므로 폴백이 한 번이라도 타면
    같은 시드가 재현되지 않는다 (semibluff→showdown 강등이 매번 달라졌다).
    호출부가 rng 를 안 넘기면 조용히 깨지므로 예외를 던진다.
    """
    if profile.get('concepts'):
        need = PLAN_REQUIRED_CONCEPT
        if plan in need:
            # 'checkraise' 같은 street 공유 개념은 지금 street 의 능력으로 묻는다
            # (L-S9-07). generic 별칭은 항상 checkraise_flop 이라, 턴/리버 트랩
            # 허용을 플랍 능력으로 판정했다. trap_judgment 와 같은 해석이다.
            _c = (PS.street_concept(need[plan], street) if street
                  else need[plan])
            s = PS.sk(profile, _c)
            _down = PLAN_DOWNGRADE
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
            opp_est=None, my_range=None, opp_ranges=None, opp_ests=None):
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
    _rel_seed = (_zlib.crc32(('%s|f7b_rel_refresh' % seed).encode())
                 if seed is not None else None)
    rel_true, _rel_meta = _decision_relative_strength(
        hero, board, opp_range, n_opp=n_opp, opp_ranges=opp_ranges,
        sims=600, seed=_rel_seed)
    # perceived_rel 에는 **날것**을 넘긴다 (make_plan 과 같게).
    # 체감값을 넘기면 노이즈가 두 번 먹혀 새 불일치가 생긴다.
    rel = perceived_rel(profile, rel_true, hero, board, outs_true, made)
    _eq_audit = {}
    eq, _eq_fallback = _plan_eq(hero, board, opp_range, n_opp, sims=300, seed=seed,
                                opp_ranges=opp_ranges, audit=_eq_audit)
    if eq is None:
        st.update(plan='showdown', eq=None,
                  equity_status='unavailable_not_negative_ev',
                  equity_unavailable=_eq_audit)
        st['why'] = (st.get('why') or []) + [
            '%s: MC refresh equity unavailable; no verified betting EV' % street]
        return st
    st.pop('equity_status', None)
    st.pop('equity_unavailable', None)
    # 레인지 우위도 같은 시점에 갱신한다. my_range 가 없으면(구 호출부)
    # 이전 값을 유지해 동작을 깨지 않는다.
    # `my_range if my_range is not None` 로 쓰면 **빈 리스트가 들어올 때
    # 폴백을 안 탄다**([] 는 None 이 아니다). 그러면 계획 상태에 레인지가
    # 남아 있는데도 재계산이 통째로 건너뛰어진다(실측: 새 시드 320핸드에서
    # stale 9건, 전부 이 경로). 값이 비었으면 상태의 것을 쓴다.
    _mr = my_range if my_range else st.get('my_range')
    if _mr and opp_range:
        _nut_joint_seed = (_zlib.crc32(
            ('%s|f7b_nut_refresh' % seed).encode())
            if seed is not None else None)
        _nut_raw, _nut_meta = _decision_nut_advantage(
            _mr, board, opp_range, n_opp=n_opp, opp_ranges=opp_ranges,
            sims=1600, seed=_nut_joint_seed)
        st['nut_adv_raw'] = float(_nut_raw)
        st['nut_adv'] = round(_nut_raw, 2)
        st['nut_adv_union'] = (
            round(float(_nut_meta.get('union')), 6)
            if _nut_meta.get('union') is not None else None)
        st['nut_adv_joint'] = (
            round(float(_nut_meta.get('joint')), 6)
            if _nut_meta.get('joint') is not None else None)
        st['nut_adv_source'] = _nut_meta.get('source')
        _adv_joint_seed = (_zlib.crc32(
            ('%s|f7b_range_adv_refresh' % seed).encode())
            if seed is not None else None)
        _adv, _adv_meta = _decision_range_advantage(
            _mr, board, opp_range, n_opp=n_opp, opp_ranges=opp_ranges,
            sims=600, seed=seed, joint_seed=_adv_joint_seed)
        st['range_adv'] = round(_adv, 2)
        st['range_adv_union'] = (
            round(float(_adv_meta.get('union')), 6)
            if _adv_meta.get('union') is not None else None)
        st['range_adv_joint'] = (
            round(float(_adv_meta.get('joint')), 6)
            if _adv_meta.get('joint') is not None else None)
        st['range_adv_source'] = _adv_meta.get('source')

    # blocker 도 board/range 의존 판단이다. 플랍 값을 턴/리버 sizing 에
    # 재사용하지 않고 현재 board + 현재 perceived ranges 로 갱신한다.
    if opp_range and board:
        _blk_typ = {'flop': 0.60, 'turn': 0.70, 'river': 0.78}.get(street, 0.65)
        _blk_raw, _blk_meta = _decision_blocker_effect(
            hero, board, opp_range, street, _blk_typ,
            n_opp=n_opp, opp_ranges=opp_ranges, seed=seed, tag='refresh')
        _blk_bg = (max(0.0, min(1.0, (PS.sk(profile, 'blocker') - 1.0)/7.0))
                   if profile.get('concepts') else 1.0)
        _blk_net = float(_blk_raw) * _blk_bg
        st['blocker'] = round(R.blocker_score(hero, opp_range, board) * _blk_bg, 2)
        st['blocker_net'] = round(_blk_net, 3)
        st['blocker_net_raw'] = float(_blk_raw)
        st['blocker_source'] = _blk_meta.get('source')
        if isinstance(st.get('stackoff'), dict):
            _so = dict(st['stackoff'])
            _so['_blk_net'] = round(_blk_net, 3)
            st['stackoff'] = _so

    # 갱신 **전** 값을 잡아둔다. st.update 뒤에는 이전 강도를 알 수 없다.
    _prev_made = st.get('made') or 0
    _prev_rel = st.get('rel') or 0.0
    st.update({
        'rel': round(rel, 2),
        'rel_true': round(rel_true, 6),
        'rel_union': (round(float(_rel_meta.get('union')), 6)
                      if _rel_meta.get('union') is not None else None),
        'rel_joint': (round(float(_rel_meta.get('joint')), 6)
                      if _rel_meta.get('joint') is not None else None),
        'rel_source': _rel_meta.get('source'),
        'eq': round(eq, 3), 'outs': outs,
        'made': made,
        # 'danger' 는 make_plan 과 같은 의미(이 사람이 인지한 위험)로 기록한다.
        # 예전에는 여기서 원시값으로 덮어써 같은 키의 의미가 바뀌었다(L-RA06).
        'danger': round(perceived_board_danger(profile, board), 2),
        'danger_raw': round(bot.board_danger(board), 2)})
    if _eq_fallback:
        st['eq_field_fallback'] = True
    else:
        st.pop('eq_field_fallback', None)
    # eq 를 갱신했으면 기록용 짝도 같이 갱신한다. 안 그러면 eq 는 새 값,
    # eq_current 는 make_plan 시점 값이 되어 eq_delta 가 의미를 잃는다.
    _eqc_audit = {}
    _eqc = _eq_current(hero, board, opp_range, n_opp, sims=300, seed=seed,
                       opp_ranges=opp_ranges, audit=_eqc_audit)
    if _eqc is None:
        st['eq_current_sampling'] = dict(_eqc_audit)
    else:
        st.pop('eq_current_sampling', None)
    st.update({'eq_current': (None if _eqc is None else round(_eqc, 3)),
               'eq_delta': (None if _eqc is None else round(eq - _eqc, 3)),
               'eq_sims': 300, 'eq_seed': seed,
               'outs_true': outs_true,
               'opp_range_n': len(opp_range) if opp_range else 0,
               'opp_range_mass': (R.range_mass(opp_range) if opp_range else 0.0),
               'opp_range_sig': _range_sig(opp_range),
               'opp_ranges_n': ({str(k): len(v) for k, v in opp_ranges.items()}
                                if isinstance(opp_ranges, dict) else None),
               'opp_ranges_mass': ({
                   str(k): R.range_mass(v) for k, v in opp_ranges.items()}
                   if isinstance(opp_ranges, dict) else None),
               'opp_ranges_sig': ({str(k): _range_sig(v) for k, v in opp_ranges.items()}
                                  if isinstance(opp_ranges, dict) else None),
               'my_range_n': len(_mr) if _mr else 0,
               'my_range_mass': (R.range_mass(_mr) if _mr else 0.0),
               'my_range_sig': _range_sig(_mr)})
    why = list(st.get('why') or [])
    old = st.get('plan')

    # 강등 임계값은 상대에 따라 움직인다.
    # 잘 접는 상대라면 내 강도가 떨어져도 계속 밀어붙일 근거가 되고,
    # 안 접는 상대(스테이션)라면 더 일찍 포기해야 한다.
    # 자기 전략만 치는 선수(exploit_weight=0)는 이 조정을 하지 않는다.
    _oe_map = opp_ests if isinstance(opp_ests, dict) else st.get('opp_ests')
    _field_refresh = (
        select_field_opponent(profile, _oe_map, street, 'fold_constraint')
        if int(n_opp or 1) > 1 else None)
    oe = (_field_refresh.get('est') if _field_refresh
          else (opp_est if opp_est is not None else st.get('opp_est')))
    if isinstance(_oe_map, dict):
        st['opp_ests'] = dict(_oe_map)
    if _field_refresh:
        st['field_fold_seat'] = _field_refresh.get('seat')
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
    # 나를 도운 카드면 더 버틴다. texture.new_card_effect 가 이걸 잰다
    # (직전 보드 전체 대비 — 리버면 플랍+턴, L-RA07).
    if len(board) >= 4 and profile.get('concepts'):
        _tce = TX.new_card_effect(board[:-1], board[-1],
                                   aggressor_range_high=bool(st.get('plan') in
                                       ('value_3street', 'value_2street', 'trap')))
        _bt = board_texture_read(profile)
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
        # '완성'은 드로우가 목표로 한 등급(스트레이트 4 이상)에 닿았거나
        # 상대 대비 강해진 것이다. made >= 2 는 보드 페어만으로도 성립해서
        # 원페어 + 보드 페어(made 2, rel 0.00)가 '드로우 완성 → 밸류'가 됐다
        # (audit9 HAND 63, river_fix 동일). 완성이 아닌 투페어 이상은 쇼다운.
        if draw_completion_supports_value(made, rel):
            st['plan'] = 'value_2street'
            why.append('%s: 드로우 완성(made %d) → 밸류 전환' % (street, made))
        elif made >= 2:
            st['plan'] = 'showdown'
            why.append('%s: 드로우 소멸, 쇼다운 가치(made %d, rel %.2f) → 쇼다운'
                       % (street, made, rel))
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
            strength_improvement_supports_value(rel, _prev_rel)):
        # '강도 상승'은 실제로 올랐을 때만이다. 예전 조건 rel >= 0.70 단독은
        # 생성 때 rel 0.70 으로 pot_control 을 받은 핸드가 다음 스트리트에
        # **같은 0.70** 이어도 승격시켰다(audit9 HAND 46: KK A-9-7 → 턴 3♥,
        # rel 0.70→0.70 '강도 상승'). 0.88(이 블록의 3스트리트 문턱) 이상은
        # 이전 값과 무관하게 승격한다. (아래 주석의 made 항은 제거했다.)
        # (역사) 한때 `made >= max(2, st['made']+1)` 항이 있었으나 st.update 뒤라
        # 항상 거짓인 죽은 항이었고, audit9 에서 제거했다. 현재 조건은
        # strength_improvement_supports_value(rel, _prev_rel) 하나다.
        #
        # _prev_made 로 made 승격을 되살려봤으나 **되돌렸다.** made 1→2 가 내가 핸드를
        # 개선한 경우와 **보드가 페어링된 경우**를 구분하지 못한다. 실측
        # 신규 승격 11건이 대부분 페어 보드였고, rel 0.00 / eq 0.031 인
        # 핸드까지 밸류 계획으로 승격됐다.
        # 즉 단순 stale-variable 버그가 아니라 **made 를 승격 신호로 쓰는
        # 설계 자체의 한계**다. eq/rel 하한을 새로 박는 방식은 결과에 맞춘
        # 보정이 되므로 쓰지 않는다. hand-strength transition 을 제대로
        # 정의하는 별도 설계가 필요하다(known issue E).
        st['plan'] = 'value_3street' if rel >= 0.88 else 'value_2street'
        why.append('%s: 강도 상승(rel %.2f, made %d) → 밸류 전환' % (street, rel, made))
    elif old == 'bluff_2street' and (
            made >= 1 or rel >= 0.75):
        # A bluff that improves must be RE-JUDGED, not automatically promoted.
        # "made=2" on a paired board can still be behind the raiser's overpairs
        # and Ax.  Human reasoning asks whether worse hands will continue versus
        # a bet, not merely whether the hand now has a made-hand label.
        _vb_size = float(SIZING['value_2street'].get(street, 0.55) or 0.55)
        _call_eq, _call_n = continue_range_call_equity(
            hero, board, profile, street, _vb_size, opp_range, opp_ranges,
            n_opp)

        st['improved_bluff_call_eq'] = (
            None if _call_eq is None else round(float(_call_eq), 3))
        st['improved_bluff_call_range_n'] = _call_n

        # Clear value only if the hand is actually ahead when called.
        # Otherwise stop treating it as air and take showdown value.
        # If the range evidence is unavailable, default to showdown rather than
        # inventing a value bet.
        # 밸류 재분류는 '콜받는 레인지 대비 앞서는가' 하나로 판정한다
        # (L-S9-03). 예전 0.54 여유분과 전체 레인지 rel ≥ 0.55 는 근거가 없거나
        # (aae4b908 에 설명 없음) 이 커밋이 대체하려던 옛 전체-rel 규칙의 잔재였다.
        if ahead_when_called(_call_eq):
            st['plan'] = 'value_2street'
            why.append(
                '%s: 블러프 중 강도 획득(made %d, rel %.2f),'
                ' 콜 레인지 상대 eq %.2f → 밸류 재분류'
                % (street, made, rel, float(_call_eq)))
        else:
            st['plan'] = 'showdown'
            if _call_eq is None:
                why.append(
                    '%s: 블러프 중 쇼다운 가치 획득(made %d, rel %.2f),'
                    ' 콜 레인지 근거 부족 → 블러프 중단/쇼다운'
                    % (street, made, rel))
            else:
                why.append(
                    '%s: 블러프 중 쇼다운 가치 획득(made %d, rel %.2f)이나'
                    ' 콜 레인지 상대 eq %.2f → 밸류 아님, 쇼다운'
                    % (street, made, rel, float(_call_eq)))
    elif (old == 'value_2street'
          and made > st.get('plan_made', _prev_made)
          # _prev_rel 은 저장된 반올림값(2자리)이다. 같은 정밀도로 비교한다 —
          # 원값 0.957 을 저장값 0.96 과 비교해 '강도 하락'으로 오판했다.
          and round(rel, 2) >= max(0.85, _prev_rel)
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
        #
        # made 증가의 기준은 **계획을 채택한 시점**(plan_made)이다. 직전
        # 스트리트와 비교하면, 턴에 강해지고(예산 남음) 리버에 예산이 떨어진
        # 경우(made 그대로) 승격 시점이 영영 오지 않았다: 플랍 얇은 밸류 →
        # 턴 트립스(rel 0.96) → 리버 '사이즈 0 → 체크'(베타 A #5).
        st['plan'] = 'value_3street'
        st['plan_goal'] = 'value_3street'
        why.append('%s: 예산 소진 후 강도 상승(rel %.2f, made %d→%d) → 3스트리트 승격'
                   % (street, rel, st.get('plan_made', _prev_made), made))
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
    mult = checkraise_street_multiplier(a, ob, board, street)
    mult *= (1 + rng.uniform(-0.12, 0.12))
    return checkraise_target_amount(tocall, pot, stack, mult, a, ob)


def checkraise_street_multiplier(aggr, overbet_skill, board, street):
    """체크레이즈 크기의 street 기준 배수(맞은 벳 대비, 잡음 전) — ledger L152."""
    mult = 2.7 + 0.09*aggr + 0.06*overbet_skill    # 대략 3.0~4.3배
    dang = bot.board_danger(board)
    mult *= (1 + 0.18*dang)                        # 젖은 보드는 크게
    if street == 'river': mult *= 0.92
    return mult


def checkraise_target_amount(tocall, pot, stack, mult, aggr, overbet_skill):
    """배수를 칩 target 으로 환산: 맞은 벳 × [2.2, 5.0], 팟 상한, 100 단위, 스택 상한.

    단위 주의(L152): 반환값은 이 street 의 '절대 target' 이 아니라
    tocall 기준으로 만든 금액이다. hero 가 이미 넣은 칩(hero_contrib)은
    호출부(act_with_plan)가 target 좌표로 옮기지 않는다 — 체크 후 첫 레이즈라
    hero_contrib 이 0 인 경로에서만 쓰인다.
    """
    target = tocall * max(2.2, min(5.0, mult))
    # 팟 대비 상한 — 공격성이 높을수록 상한도 높다
    cap_mult = 1.15 + 0.075*aggr + 0.03*overbet_skill
    target = min(target, (pot + tocall) * cap_mult)
    amt = int(min(stack, max(tocall*2.2, round(target/100)*100)))
    return int(snap_allin(amt, stack, pot + 2*amt - tocall))


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

    인자 `s`(SPR)와 `street` 는 현재 식에 쓰이지 않는다(ledger L142). 목표는
    남은 street 수와 무관한 '전체 지출' 비율이며, 남은 street 에 맞춘 horizon
    교정(stackoff_plan 의 고정 3스트리트 기하, L143)은 행동 변화라 LATER 다.
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
      low_cost   저비용 — 중간에 접을 생각. 반응만 보고 손실을 줄인다.
                 (L-S9-05: 예전 라벨 'probe'. 상대가 체크백한 뒤의 공개 probe
                 벳 기회 — decide_aggression/bluff_donk_suppression 의 probe
                 개념 — 와 다른 질문이라 사이즈 모드 이름으로 바꿨다.)

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
        return 'low_cost', 0.55, '도중 포기 위험 %.0f%% — 최소 비용 탐색' % (risk*100)
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
