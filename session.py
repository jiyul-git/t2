"""제너레이터 기반 재개형 핸드 진행 + 쇼다운/사이드팟 정산 + 토너 세션."""
import random, json, os, hashlib, itertools, zlib as _zlib
import zlib as _zlib
import bot, preflop as pf, ranges as R, plan as PL, icm, dynamics as DY, runner as RU, reads as RD, gto as _GTO, persona as PS, money_pressure as MP
from play import Hand, POST, PRE

D = os.path.dirname(os.path.abspath(__file__))

def best5(cards): return bot.eval7(cards)


def oop_field(order, seat, folded=(), allin=()):
    """그 스트리트 액션 순서에서 **내 뒤에 아직 액션할 상대가 남아 있는가.**

    = last to act 가 아닌가. 포지션 라벨 목록이든 좌석 번호 목록이든 같다.
    폴드·올인은 더 이상 액션하지 않으므로 뒤에 있어도 세지 않는다.

    예전에는 h.POST 의 **절대** 인덱스 < 3 이었다. 그러면 CO 가 BTN 만
    상대해도 IP 로 세고, 헤즈업 포스트플랍에서는 BB·SB 가 **둘 다** OOP 가
    된다(POST 가 [BB, SB] 인데 길이가 2 라 둘 다 3 미만이다).
    """
    if seat not in order:
        return False
    i = order.index(seat)
    return any(x not in folded and x not in allin for x in order[i+1:])


def oop_vs(order, seat, other):
    """order 상에서 seat 이 other 보다 **먼저** 액션하는가."""
    if seat not in order or other not in order:
        return False
    return order.index(seat) < order.index(other)

def _cache_key(street, seat, n):
    return '%s|%s|%d' % (street, seat, n)


def _merge_pf_seed(prev, new):
    """한 좌석의 프리플랍 판단/액션 스토리를 덮어쓰지 않고 이어 붙인다."""
    prev = dict(prev or {})
    out = dict(new or {})
    line = list(prev.get('pf_line') or [])
    line.append({
        'role': out.get('pf_role'),
        'act': out.get('pf_act'),
        'kind': out.get('pf_decision_kind'),
        'vs': out.get('pf_vs'),
        'level': out.get('pf_level'),
        'open_bb': out.get('pf_open_bb'),
        'n_callers': out.get('pf_n_callers'),
        'n_limpers': out.get('pf_n_limpers'),
        'can_raise': out.get('pf_can_raise'),
        'facing_allin': out.get('pf_facing_allin'),
        'pot_bb': out.get('pf_pot_bb'),
        'to_call_bb': out.get('pf_to_call_bb'),
        'stack_bb': out.get('pf_stack_bb'),
    })
    out['pf_line'] = line
    out['pf_origin_role'] = prev.get(
        'pf_origin_role', prev.get('pf_role', out.get('pf_role')))
    out['pf_origin_act'] = prev.get(
        'pf_origin_act', prev.get('pf_act', out.get('pf_act')))
    return out

def _update_pf_state_after_apply(rnd, seat, aggressor, callers, limpers):
    """방금 적용된 실제 규칙 사건으로 preflop 상태를 갱신한다.

    문자열 'allin'만 보고 aggressor로 만들면 all-in call도 raise로 오인된다.
    """
    m = rnd.action_meta[-1]
    if m.get('raised'):
        return seat, 0, limpers
    a = m.get('action')
    if a == 'call' or m.get('allin_call'):
        if aggressor is not None:
            callers += 1
        elif seat not in limpers:
            limpers.append(seat)
    return aggressor, callers, limpers


def _pf_observation_flags(action_meta, seat):
    """공개 프리플랍 사건을 역할별 관측으로 분해한다.

    opener의 fold-to-3bet/4bet과 caller의 squeeze 대응을 섞지 않는다.
    """
    full_before = 0
    first_raiser = None
    second_raiser = None
    prior = []
    called_first_raise = False
    out = {
        'threebet_chance': False, 'did_threebet': False,
        'faced_threebet_as_opener': False, 'folded_to_threebet_as_opener': False,
        'fourbet_chance_as_opener': False, 'did_fourbet_as_opener': False,
        'faced_fourbet_as_threebettor': False, 'folded_to_fourbet_as_threebettor': False,
        'backraise_chance_as_caller': False, 'did_backraise': False,
        'folded_to_squeeze_after_call': False,
    }

    for m in action_meta:
        x = m.get('seat')
        if x == seat:
            a = m.get('action')
            # 아직 자발적 액션이 없고 첫 full raise를 맞은 자리 = 3bet 기회.
            if full_before == 1 and not prior:
                out['threebet_chance'] = True
                out['did_threebet'] = bool(m.get('full_raise'))

            # 첫 raiser가 두 번째 full raise를 맞으면 opener vs 3bet.
            if seat == first_raiser and full_before == 2:
                out['faced_threebet_as_opener'] = True
                out['folded_to_threebet_as_opener'] = (a == 'fold')
                out['fourbet_chance_as_opener'] = True
                out['did_fourbet_as_opener'] = bool(m.get('full_raise'))

            # 두 번째 raiser가 세 번째 full raise를 맞으면 3bettor vs 4bet.
            if seat == second_raiser and full_before == 3:
                out['faced_fourbet_as_threebettor'] = True
                out['folded_to_fourbet_as_threebettor'] = (a == 'fold')

            # 첫 raise를 콜한 뒤 두 번째 full raise(squeeze)가 돌아온 상태.
            if called_first_raise and full_before == 2:
                out['backraise_chance_as_caller'] = True
                out['did_backraise'] = bool(m.get('full_raise'))
                out['folded_to_squeeze_after_call'] = (a == 'fold')

            if full_before == 1 and a == 'call' and not m.get('raised'):
                called_first_raise = True
            prior.append(m)

        if m.get('full_raise'):
            full_before += 1
            if full_before == 1:
                first_raiser = x
            elif full_before == 2:
                second_raiser = x

    return out


def _facing_wager_context(rnd, aggressor, pot_start):
    """현재 hero가 마주한 마지막 공격 액션의 실제 wager 문맥.

    size_frac = 그 공격자가 **그 액션에서 새로 넣은 칩** / 액션 직전 팟.
    hero의 to_call 이나 street 시작 팟으로 대신 계산하면
    bet->call->hero / raise->hero에서 사이즈가 왜곡된다.
    """
    if aggressor is None:
        return None
    pot_before = float(pot_start or 0)
    latest = None
    for m in (getattr(rnd, 'action_meta', None) or []):
        inc = float(m.get('increment', 0) or 0)
        if m.get('seat') == aggressor and m.get('raised'):
            latest = {
                'seat': aggressor,
                'increment': inc,
                'pot_before': pot_before,
                'size_frac': inc / max(1.0, pot_before),
                'full_raise': bool(m.get('full_raise')),
                'incomplete_raise': bool(m.get('incomplete_raise')),
            }
        pot_before += inc
    return latest


def _observed_postflop_action(meta):
    """행동 문자열이 아니라 규칙 의미로 postflop read 액션을 정규화."""
    if meta.get('raised'):
        return 'raise'
    if meta.get('allin_call'):
        return 'call'
    return meta.get('action')


def _postflop_facing_contexts(action_meta):
    """각 액션 직전에 actor가 무엇을 마주했는지 분류한다.

    반환 원소: None | 'bet' | 'raise'

    첫 가격 생성은 bet, 이미 가격이 있는데 다시 올린 사건은 raise다.
    incomplete all-in raise도 다음 actor 입장에서는 'raise를 맞은 것'이다.
    """
    out = []
    facing = None
    for m in (action_meta or []):
        out.append(facing)
        if m.get('raised'):
            facing = ('raise'
                      if float(m.get('pre_current', 0) or 0) > 0
                      else 'bet')
    return out


def _postflop_response_context(rnd, seat):
    """현재 seat의 재판단 사건을 공개 액션 이력으로 분류한다.

    caller_backaction 하나만 남기면
      bet -> call -> raise
    와
      bet -> raise -> call -> re-raise
    가 같은 사건으로 뭉개진다. 마지막 hero action이 **어떤 가격을
    마주하고 나온 것인지**와 현재 raise depth도 함께 보존한다.
    """
    metas = list(getattr(rnd, 'action_meta', None) or [])
    facing_before = _postflop_facing_contexts(metas)
    hero_idx = [i for i, m in enumerate(metas) if m.get('seat') == seat]
    last_idx = hero_idx[-1] if hero_idx else None
    last_hero = metas[last_idx] if last_idx is not None else None
    latest_aggr = next((m for m in reversed(metas) if m.get('raised')), None)

    facing_kind = None
    if latest_aggr is not None:
        facing_kind = ('raise'
                       if float(latest_aggr.get('pre_current', 0) or 0) > 0
                       else 'bet')

    if last_hero and last_hero.get('raised'):
        prior_action = ('raise'
                        if float(last_hero.get('pre_current', 0) or 0) > 0
                        else 'bet')
    elif last_hero and last_hero.get('allin_call'):
        prior_action = 'call'
    else:
        prior_action = last_hero.get('action') if last_hero else None
    prior_aggressive = bool(last_hero and last_hero.get('raised'))
    prior_facing_kind = (
        facing_before[last_idx] if last_idx is not None and last_idx < len(facing_before)
        else None)

    if facing_kind == 'raise' and prior_aggressive:
        kind = 'aggressor_backaction'
    elif facing_kind == 'raise' and prior_action == 'call':
        kind = 'caller_backaction'
    elif facing_kind == 'raise':
        kind = 'cold_facing_raise'
    elif facing_kind == 'bet' and prior_action == 'check':
        kind = 'check_then_face_bet'
    elif facing_kind == 'bet':
        kind = 'face_bet'
    else:
        kind = 'free_action'

    return {
        'kind': kind,
        'facing_kind': facing_kind,
        'prior_action': prior_action,
        'prior_aggressive': prior_aggressive,
        'prior_facing_kind': prior_facing_kind,
        'raise_depth_full': sum(1 for m in metas if m.get('full_raise')),
        'raise_depth_any': sum(1 for m in metas if m.get('raised')),
        'facing_full_raise': bool(latest_aggr and latest_aggr.get('full_raise')),
        'facing_incomplete_raise': bool(
            latest_aggr and latest_aggr.get('incomplete_raise')),
        'hero_contrib': float(getattr(rnd, 'contrib', {}).get(seat, 0) or 0),
    }


def _postflop_street_outcome(action_meta):
    """완료된 스트리트의 POST-F 결과를 규칙 사건으로 요약한다.

    전략 판단은 원본 action_meta 를 그대로 볼 수 있어야 하고, 이 요약은
    provenance/다음 단계 감사용이다. raw 'allin' 문자열은 쓰지 않는다.
    """
    metas = list(action_meta or [])
    aggr_idx = [i for i, m in enumerate(metas) if m.get('raised')]
    if not aggr_idx:
        return {
            'kind': 'checkthrough',
            'last_aggressor': None,
            'callers': [],
            'allin_callers': [],
            'raise_depth_full': 0,
            'raise_depth_any': 0,
        }

    j = aggr_idx[-1]
    last = metas[j]
    callers = []
    allin_callers = []
    for m in metas[j+1:]:
        a = _observed_postflop_action(m)
        if a == 'call':
            callers.append(m.get('seat'))
            if m.get('allin_call'):
                allin_callers.append(m.get('seat'))

    if not callers:
        kind = 'all_fold'
    elif len(callers) == 1 and allin_callers:
        kind = 'one_allin_call'
    elif len(callers) == 1:
        kind = 'one_call'
    elif allin_callers:
        kind = 'multi_call_with_allin'
    else:
        kind = 'multi_call'

    return {
        'kind': kind,
        'last_aggressor': last.get('seat'),
        'callers': callers,
        'allin_callers': allin_callers,
        'raise_depth_full': sum(1 for m in metas if m.get('full_raise')),
        'raise_depth_any': sum(1 for m in metas if m.get('raised')),
    }


def _decision_pot_layers(prior_contrib, street_contrib, folded, stacks,
                         hero=None, dead=0):
    """판단 시점 누적 기여를 main/side-pot contribution layer로 보존한다.

    기록/감사용 read-only provenance다. 전략 함수에는 넘기지 않는다.

    - prior_contrib: 완료된 이전 street까지의 누적 기여
    - street_contrib: 현재 street에서 지금까지의 기여
    - folded: 이미 폴드한 좌석. 칩은 pot amount에 남지만 eligibility에서는 빠진다.
    - stacks: 현재 남은 스택. eligible seat 중 0이면 locked all-in,
      양수면 아직 행동 가능한 active seat로 분류한다.
    - dead: ante 등 개인 contribution이 아닌 dead money. 첫/main layer에만 더한다.

    아직 콜되지 않은 현재 wager도 contribution level로 보존한다. 그 upper layer에서
    hero_eligible=False일 수 있으며, 이후 F8 EV 단계가 '콜하면 새로 contest하게 되는
    금액'을 계산할 때 이 차이를 사용한다.
    """
    prior = dict(prior_contrib or {})
    street = dict(street_contrib or {})
    folded = set(folded or ())
    stacks = dict(stacks or {})

    seats = sorted(
        set(prior) | set(street) | set(stacks),
        key=lambda x: str(x))
    total = {
        s: float(prior.get(s, 0) or 0) + float(street.get(s, 0) or 0)
        for s in seats
    }
    levels = sorted(set(v for v in total.values() if v > 0))

    # 일반 게임에서는 blind/contribution level이 항상 있으나, dead-only 상태도
    # provenance 합계가 보존되도록 명시적으로 다룬다.
    if not levels:
        if float(dead or 0) <= 0:
            return []
        elig = [s for s in seats if s not in folded]
        locked = [s for s in elig if float(stacks.get(s, 0) or 0) <= 0]
        active = [s for s in elig if float(stacks.get(s, 0) or 0) > 0]
        return [{
            'level': 0.0,
            'amount': float(dead),
            'contributors': [],
            'eligible_seats': elig,
            'hero_eligible': (hero in elig) if hero is not None else None,
            'locked_allin_seats': locked,
            'active_seats': active,
            'locked_allin_opponents': [s for s in locked if s != hero],
            'active_opponents': [s for s in active if s != hero],
        }]

    out = []
    prev = 0.0
    first = True
    for lv in levels:
        contributors = [s for s in seats if total.get(s, 0) >= lv]
        amount = (lv - prev) * len(contributors)
        if first:
            amount += float(dead or 0)
            first = False
        eligible = [s for s in contributors if s not in folded]
        locked = [
            s for s in eligible if float(stacks.get(s, 0) or 0) <= 0]
        active = [
            s for s in eligible if float(stacks.get(s, 0) or 0) > 0]
        out.append({
            'level': float(lv),
            'amount': float(amount),
            'contributors': contributors,
            'eligible_seats': eligible,
            'hero_eligible': (hero in eligible) if hero is not None else None,
            'locked_allin_seats': locked,
            'active_seats': active,
            'locked_allin_opponents': [s for s in locked if s != hero],
            'active_opponents': [s for s in active if s != hero],
        })
        prev = lv
    return out


def _diagnostic_layer_equities(hero, board, pot_layers,
                                  active_ranges, locked_ranges, sims=600):
    """F8-D3: 현재 참가 가능한 pot layer별 showdown equity 진단.

    기록 전용이다. 결과를 plan/action/sizing에 넘기지 않는다.

    range가 하나라도 없으면 임의 fallback을 만들지 않고 complete=False,
    equity=None 으로 남긴다. hero_eligible=False인 pending wager layer도
    현재 상태의 equity로 해석하지 않는다. D4가 fold/call 가상 상태를
    따로 구성할 때 처리한다.
    """
    active_ranges = dict(active_ranges or {})
    locked_ranges = dict(locked_ranges or {})
    out = []

    for idx, layer in enumerate(pot_layers or []):
        eligible = list(layer.get('eligible_seats') or [])
        opps = sorted((x for x in eligible if x != hero), key=lambda x: str(x))
        missing = []
        pools = []
        sources = {}

        for o in opps:
            if o in active_ranges and active_ranges.get(o):
                pools.append(list(active_ranges[o]))
                sources[str(o)] = 'active'
            elif o in locked_ranges and locked_ranges.get(o):
                pools.append(list(locked_ranges[o]))
                sources[str(o)] = 'locked_allin'
            else:
                missing.append(o)

        row = {
            'idx': idx,
            'level': layer.get('level'),
            'amount': layer.get('amount'),
            'hero_eligible': bool(layer.get('hero_eligible')),
            'opponents': opps,
            'range_sources': sources,
            'missing_ranges': missing,
            'complete': False,
            'equity': None,
            'sims': int(sims),
        }

        if not row['hero_eligible']:
            row['reason'] = 'hero_not_currently_eligible'
        elif missing:
            row['reason'] = 'missing_opponent_range'
        elif not opps:
            row['complete'] = True
            row['equity'] = 1.0
            row['reason'] = 'sole_eligible'
        else:
            row['complete'] = True
            row['equity'] = round(
                float(bot.equity_vs_combos(
                    hero, board, pools, sims=int(sims))), 6)
            row['reason'] = 'computed'
        out.append(row)

    return out


def _barrel_count(full_meta, current_meta, seat, current_street):
    """상대가 공격한 **postflop street 수**. 현재 street도 포함."""
    streets = {
        m.get('street') for m in (full_meta or [])
        if m.get('seat') == seat and m.get('raised') and m.get('street')
    }
    if any(m.get('seat') == seat and m.get('raised') for m in (current_meta or [])):
        streets.add(current_street)
    return max(1, len(streets))


def _money_jump_observe(h, seat, rnd, street, profile, to_call=0, pot=0,
                        facing_seat=None, decision_context=None,
                        facing_read=None):
    """행동을 바꾸지 않고 머니점프/스택/자리의 공개 상태만 기록한다."""
    bb = max(1, getattr(h, 'bb', 1) or 1)
    mj = dict(getattr(h, 'money_jump', None) or {})
    field = [float(x) for x in (getattr(h, 'field_stacks', ()) or ()) if x > 0]
    start = float((getattr(h, '_start_stacks', {}) or {}).get(
        seat, rnd.stacks.get(seat, 0) + rnd.contrib.get(seat, 0)))
    behind = float(rnd.stacks.get(seat, 0))

    shorter = sorted(x for x in field if x < start)
    n_others = max(0, len(field) - 1)
    nearest_shorter = max(shorter) if shorter else None
    shortest = min(shorter) if shorter else None
    median_shorter = (shorter[len(shorter)//2] if shorter else None)

    order = list(rnd.order)
    decision_context = dict(decision_context or {})
    pos = (getattr(h, 'pos', {}) or {}).get(seat)
    pre_order = list(getattr(h, 'PRE', []) or [])
    n_seats = len(getattr(h, 'seats', []) or pre_order)
    if pos in pre_order and 'BB' in pre_order:
        if pos == 'BB':
            hands_to_next_bb = n_seats
        else:
            hands_to_next_bb = pre_order.index('BB') - pre_order.index(pos)
            if hands_to_next_bb <= 0:
                hands_to_next_bb += n_seats
    else:
        hands_to_next_bb = None

    ante_on = (getattr(h, 'ante', 0) or 0) > 0
    orbit_cost_bb = 1.5 + (1.0 if ante_on else 0.0)
    # 현재 SB/BB의 강제 납부는 rnd.stacks에 이미 반영됐다. 지금부터 다음 BB까지
    # 추가로 버틸 비용을 본다. SB만 다음 핸드 BB라 이미 낸 SB 0.5BB를 제외한다.
    forced_to_next_bb = ((1.0 + (1.0 if ante_on else 0.0))
                         if pos == 'SB' else orbit_cost_bb)

    pending = []
    if seat in order:
        i = order.index(seat)
        cyc = order[i+1:] + order[:i]
        for x in cyc:
            if x == seat or x in rnd.folded or x in rnd.allin:
                continue
            if x not in rnd.acted or rnd.to_call(x) > 0:
                pending.append(x)

    start_stacks = getattr(h, '_start_stacks', {}) or {}
    targets = []
    for x in pending:
        xs = float(start_stacks.get(
            x, rnd.stacks.get(x, 0) + rnd.contrib.get(x, 0)))
        xb = float(rnd.stacks.get(x, 0))
        _ts = sorted(v for v in field if v < xs)
        _tm = (_ts[len(_ts)//2] if _ts else None)
        _tpos = (getattr(h, 'pos', {}) or {}).get(x)
        _tforced = ((1.0 + (1.0 if ante_on else 0.0))
                    if _tpos == 'SB' else orbit_cost_bb)
        _tbb = xs / bb
        targets.append({
            'seat': x,
            'pid': (getattr(h, 'seat_pid', {}) or {}).get(x),
            'pos': _tpos,
            'stack_bb': round(_tbb, 3),
            'stack_behind_bb': round(xb / bb, 3),
            'stack_ratio_to_me': round(xs / max(1.0, start), 4),
            'i_cover': bool(start > xs),
            'covers_me': bool(xs > start),
            'n_shorter': len(_ts),
            'median_shorter_ratio': (
                round(_tm / max(1.0, xs), 4) if _tm is not None else None),
            'forced_cost_to_next_bb': round(_tforced, 3),
            'stack_after_next_bb_if_fold_all': round(
                max(0.0, xb / bb - _tforced), 3),
            'forced_cost_share_of_stack': round(
                _tforced / max(0.001, xb / bb), 4),
            'bf': round(h.bf(x), 4) if hasattr(h, 'bf') else 1.0,
        })

    live_opp = [x for x in rnd.live() if x != seat]
    live_stacks = [float(start_stacks.get(
        x, rnd.stacks.get(x, 0) + rnd.contrib.get(x, 0))) for x in live_opp]

    facing = None
    if facing_seat is not None and facing_seat != seat:
        facing = next((dict(t) for t in targets if t['seat'] == facing_seat), None)
        if facing is None:
            xs = float(start_stacks.get(
                facing_seat,
                rnd.stacks.get(facing_seat, 0) + rnd.contrib.get(facing_seat, 0)))
            xb = float(rnd.stacks.get(facing_seat, 0))
            _ts = sorted(v for v in field if v < xs)
            _tm = (_ts[len(_ts)//2] if _ts else None)
            _tpos = (getattr(h, 'pos', {}) or {}).get(facing_seat)
            _tforced = ((1.0 + (1.0 if ante_on else 0.0))
                        if _tpos == 'SB' else orbit_cost_bb)
            _tbb = xs / bb
            facing = {
                'seat': facing_seat,
                'pid': (getattr(h, 'seat_pid', {}) or {}).get(facing_seat),
                'pos': _tpos,
                'stack_bb': round(_tbb, 3),
                'stack_behind_bb': round(xb / bb, 3),
                'stack_ratio_to_me': round(xs / max(1.0, start), 4),
                'i_cover': bool(start > xs),
                'covers_me': bool(xs > start),
                'n_shorter': len(_ts),
                'median_shorter_ratio': (
                    round(_tm / max(1.0, xs), 4) if _tm is not None else None),
                'forced_cost_to_next_bb': round(_tforced, 3),
                'stack_after_next_bb_if_fold_all': round(
                    max(0.0, xb / bb - _tforced), 3),
                'forced_cost_share_of_stack': round(
                    _tforced / max(0.001, xb / bb), 4),
                'bf': round(h.bf(facing_seat), 4) if hasattr(h, 'bf') else 1.0,
            }

    obs = {
        'street': street,
        'seat': seat,
        'pid': (getattr(h, 'seat_pid', {}) or {}).get(seat),
        'pos': pos,
        'decision_kind': decision_context.get('kind'),
        'n_limpers': decision_context.get('n_limpers'),
        'n_callers': decision_context.get('n_callers'),
        'remaining': getattr(h, 'field_remaining', None),
        'itm': getattr(h, 'field_itm', None),
        'current_prize': mj.get('current_prize', 0.0),
        'next_prize': mj.get('next_prize', 0.0),
        'next_jump': mj.get('next_jump', 0.0),
        'players_to_jump': mj.get('players_to_jump', 0),
        'min_cash': mj.get('min_cash', 0.0),
        'jump_vs_mincash': mj.get('jump_vs_mincash', 0.0),
        'jump_frac_next': mj.get('jump_frac_next', 0.0),
        'distance_frac_itm': mj.get('distance_frac_itm', 0.0),
        'distance_frac_remaining': mj.get('distance_frac_remaining', 0.0),
        'money_jump_skill': PS.sk(profile, 'money_jump', 3.0),
        'icm_skill': PS.sk(profile, 'icm', 3.0),
        'stack_decay_skill': PS.sk(profile, 'stack_decay', 3.0),
        'pf_range_skill': PS.sk(profile, 'pf_range', 3.0),
        'open_size_skill': PS.sk(profile, 'open_size', 3.0),
        'positional_skill': PS.sk(profile, 'positional', 3.0),
        'bf': round(h.bf(seat), 4) if hasattr(h, 'bf') else 1.0,
        'stack_start_bb': round(start / bb, 3),
        'stack_behind_bb': round(behind / bb, 3),
        'field_avg_bb': round(float(getattr(h, 'field_avg_stack', 0) or 0) / bb, 3),
        'table_n': n_seats,
        'hands_to_next_bb': hands_to_next_bb,
        'orbit_cost_bb': round(orbit_cost_bb, 3),
        'forced_cost_to_next_bb': round(forced_to_next_bb, 3),
        'stack_after_next_bb_if_fold_all': round(
            max(0.0, behind / bb - forced_to_next_bb), 3),
        'forced_cost_share_of_stack': round(
            forced_to_next_bb / max(0.001, behind / bb), 4),
        'n_shorter': len(shorter),
        'shorter_frac': round(len(shorter) / max(1, n_others), 4),
        'nearest_shorter_ratio': (round(nearest_shorter / max(1.0, start), 4)
                                  if nearest_shorter is not None else None),
        'median_shorter_ratio': (round(median_shorter / max(1.0, start), 4)
                                 if median_shorter is not None else None),
        'shortest_ratio': (round(shortest / max(1.0, start), 4)
                           if shortest is not None else None),
        'shorter_minus_needed': (
            len(shorter) - int(mj.get('players_to_jump') or 0)
            if (mj.get('players_to_jump') or 0) > 0 else None),
        'shorter_to_needed_ratio': (
            round(len(shorter) / float(mj.get('players_to_jump')), 4)
            if (mj.get('players_to_jump') or 0) > 0 else None),
        'table_cover_count': sum(1 for x in live_stacks if start > x),
        'table_covered_by_count': sum(1 for x in live_stacks if x > start),
        'players_yet_to_act': len(pending),
        'players_yet_to_act_frac': round(
            len(pending) / max(1, len(live_opp)), 4),
        'covers_yet_to_act': sum(1 for t in targets if t['i_cover']),
        'covered_by_yet_to_act': sum(1 for t in targets if t['covers_me']),
        'blind_targets_yet_to_act': sum(
            1 for t in targets if t['pos'] in ('SB', 'BB')),
        'targets_yet_to_act': targets,
        'facing_target': facing,
        'to_call_bb': round(float(to_call or 0) / bb, 3),
        'pot_bb': round(float(pot or 0) / bb, 3),
    }

    _actor = MP.actor_from_profile(profile, PS.sk, PS.temper)
    obs['money_signals'] = MP.signals(obs, _actor)

    def _target_state(t):
        if not t:
            return None
        d = dict(obs)
        d.update({
            'stack_start_bb': t.get('stack_bb', 0.0),
            'stack_behind_bb': t.get('stack_behind_bb', t.get('stack_bb', 0.0)),
            'n_shorter': t.get('n_shorter', 0),
            'median_shorter_ratio': t.get('median_shorter_ratio'),
            'forced_cost_to_next_bb': t.get('forced_cost_to_next_bb', 0.0),
            'stack_after_next_bb_if_fold_all': t.get(
                'stack_after_next_bb_if_fold_all', 0.0),
            'forced_cost_share_of_stack': t.get(
                'forced_cost_share_of_stack', 0.0),
            'bf': t.get('bf', 1.0),
        })
        return d

    _target_signals = []
    for _t in targets:
        _ts = _target_state(_t)
        _pr = MP.pressure_opportunity(obs, _ts, _actor, read=None)
        _u = dict(_t)
        _u['pressure'] = _pr
        _target_signals.append(_u)
    obs['target_signals'] = _target_signals

    _fstate = _target_state(facing)
    if _fstate is not None:
        _fread = PS.read_opponent(profile, facing_read) if facing_read else None
        _rch = ('preflop_3bet'
                if decision_context.get('kind') == 'vs_raise' else 'generic')
        obs['facing_pressure'] = MP.pressure_opportunity(
            obs, _fstate, _actor, read=_fread, read_channel=_rch)
        _pressure = obs['facing_pressure']['pressure_opportunity']
    else:
        obs['facing_pressure'] = None
        _pressure = max(
            (x['pressure']['pressure_opportunity'] for x in _target_signals),
            default=0.0)
    obs['low_commit_pressure'] = round(
        MP.low_commit_pressure(_pressure, obs, _actor), 6)
    obs['unopened_modifiers'] = (
        MP.unopened_modifiers(obs)
        if decision_context.get('kind') == 'unopened' else None)

    h.money_jump_obs = getattr(h, 'money_jump_obs', [])
    h.money_jump_obs.append(obs)
    return obs


def _money_jump_attach_action(obs, rnd):
    if obs is None or not rnd.log:
        return
    _s, _a, _amt = rnd.log[-1]
    obs['action'] = _a
    obs['amount'] = _amt

    # 미오픈 raise의 실제 적용 금액은 open_size_bb 뒤에 shape_size와
    # 최소레이즈 규칙을 모두 통과한 값이다. sizing shadow는 이 최종값을
    # 기준으로 계산해야 한다. 행동 자체는 아직 바꾸지 않는다.
    _m = obs.get('unopened_modifiers') or {}
    if (obs.get('street') == 'preflop'
            and obs.get('decision_kind') == 'unopened'
            and _a == 'raise' and _s not in rnd.allin and _m):
        _base_bb = float(_amt) / max(1.0, float(rnd.bb))
        _sf = max(0.0, min(1.0, float(_m.get('size_factor_shadow', 1.0))))
        _m['applied_open_size_bb'] = round(_base_bb, 3)
        # unopened NLH에서 BB가 1BB 게시된 상태의 최소 raise-to는 2BB.
        _m['applied_money_size_bb_shadow'] = round(
            max(2.0, _base_bb * _sf), 3)


def award_pots(contrib, hole, board, folded, stacks, dead=0, unit=1):
    """사이드팟별로 승자에게 분배. 반환: {seat: 획득액}, 팟 내역

    dead(안테 등 데드머니)는 **메인팟에만** 얹는다.
    예전에는 각자 기여분(contrib)에 균등 분배했는데,
    100 단위 게임에서 안테를 인원수로 나누면 나눠떨어지지 않아
    스택에 51,370 같은 끝자리가 생겼다. 안테는 개인 기여가 아니라
    팟 전체에 들어가는 돈이므로 기여분을 건드리면 안 된다.
    """
    levels = sorted(set(v for v in contrib.values() if v > 0))
    won = {s: 0 for s in contrib}
    detail = []; prev = 0
    first_pot = True
    for lv in levels:
        elig_all = [s for s, v in contrib.items() if v >= lv]
        amount = (lv - prev) * len(elig_all); prev = lv
        if first_pot:
            amount += int(dead)          # 데드머니는 메인팟에만
            first_pot = False
        elig = [s for s in elig_all if s not in folded]
        if not elig:
            elig = elig_all
        if len(elig) == 1:
            winners = elig
        else:
            ranks = {s: best5(hole[s]+board) for s in elig}
            top = max(ranks.values())
            winners = [s for s in elig if ranks[s] == top]
        # 칩 단위(unit) 아래로는 쪼갤 수 없다. 실제 토너에서 300 을 둘이 나눠
        # 150 씩 갖는 일은 없다 — 나눌 수 없는 칩은 한 명에게 간다.
        u = max(1, int(unit))
        share = (amount // len(winners) // u) * u
        rem = amount - share*len(winners)
        for i, w in enumerate(winners):
            won[w] += share + (rem if i == 0 else 0)
        detail.append({'amount': amount, 'eligible': elig, 'winners': winners})
    for s, v in won.items(): stacks[s] += v
    return won, detail


class HandRun:
    """히어로 차례에 yield하고 send()로 재개하는 핸드 진행기.
       REPLAY: 이미 확정된 봇 결정은 재계산하지 않고 그대로 재생한다."""
    def __init__(self, hand, decisions=None):
        self.h = hand
        self.REPLAY = list(decisions or [])
        self.recorded = []
        self._didx = 0
        self.gen = self._run()
        self.result = None
        self._pot_at = {}          # street -> 스트리트 시작 시점 팟

    def start(self):
        try: return next(self.gen)
        except StopIteration as e: return {'done': True, 'result': self.result}

    def send(self, action, amount=0):
        try: return self.gen.send((action, amount))
        except StopIteration: return {'done': True, 'result': self.result}

    # ---------- 내부 ----------
    def _pid(self, seat):
        """관찰 장부와 틸트의 키. 좌석이 아니라 사람이어야 테이블 간 오염이 없다.

        _run 안의 지역 람다로 두면 _finish 에서 NameError 가 나고,
        그게 except: pass 에 삼켜져 쇼다운 관찰이 통째로 유실된다. (실제로 그랬다)

        변환 규칙은 play.Hand.pid_of 하나뿐이다. 여기에 사본을 두지 않는다.
        """
        return self.h.pid_of(seat)

    def _dseed(self, seat, street, tag, extra=0):
        """결정 하나에 쓸 시드. 공유 rng 에서 뽑지 않고 상황에서 유도한다.

        h.rng 를 모든 결정이 공유하면, 어느 한 곳에서 소비 횟수가 한 번만 어긋나도
        이후 모든 결정의 난수가 밀려 같은 시드가 재현되지 않는다.
        (조건부로만 난수를 쓰는 함수가 하나만 있어도 그렇게 된다.)
        상황에서 유도하면 '같은 핸드·같은 좌석·같은 스트리트·같은 시점 = 같은 난수'가
        보장되고, 다른 결정의 소비량과 무관해진다.
        """
        h = self.h
        key = '%s|%s|%s|%s|%s' % (getattr(h, 'hash', ''), seat, street, tag, extra)
        return _zlib.crc32(key.encode())

    def _acts_of(self, seat, upto_street=None, current_street=None,
                     current_log=None, current_meta=None):
        """그 좌석의 공개 포스트플랍 액션 [(street, action, size_frac), ...].

        size_frac 은 항상 **그 액션에서 새로 넣은 칩 / 액션 직전 팟**이다.

        완료된 스트리트는 full_action_meta 를 우선한다. full_log 의 amount 는
        bet/raise target 좌표라, 다음 스트리트에서 target/street-start-pot 으로
        읽으면 액션 크기가 부풀 수 있다.

        raw 'allin' 문자열도 그대로 쓰지 않는다. all-in call은 call,
        가격을 올린 all-in은 raise로 정규화해야 상대 레인지가 맞게 좁혀진다.
        """
        out = []
        _ord = {'flop': 0, 'turn': 1, 'river': 2}

        full_meta = list(getattr(self, 'full_action_meta', []) or [])
        if full_meta:
            added = {}
            for m in full_meta:
                stt = m.get('street')
                if stt not in _ord:
                    continue
                if (upto_street is not None and upto_street in _ord
                        and _ord[stt] > _ord[upto_street]):
                    continue
                inc = float(m.get('increment', 0) or 0)
                before = (float((self._pot_at or {}).get(stt, 0) or 0)
                          + added.get(stt, 0.0))
                if m.get('seat') == seat:
                    a = _observed_postflop_action(m)
                    sz = inc / max(1.0, before) if inc > 0 else 0.0
                    out.append((stt, a, sz))
                added[stt] = added.get(stt, 0.0) + inc
        else:
            # 구형/외부 기록 폴백.
            for (stt, x, a, amt) in (getattr(self, 'full_log', []) or []):
                if stt == 'preflop' or x != seat:
                    continue
                if (upto_street is not None and stt in _ord and upto_street in _ord
                        and _ord[stt] > _ord[upto_street]):
                    continue
                pot = (self._pot_at or {}).get(stt, 0)
                sz = (amt/pot) if (pot and amt) else 0.0
                out.append((stt, a, sz))

        if current_street:
            if current_meta:
                added = 0.0
                pot0 = float((self._pot_at or {}).get(current_street, 0) or 0)
                for m in current_meta:
                    inc = float(m.get('increment', 0) or 0)
                    before = pot0 + added
                    if m.get('seat') == seat:
                        a = _observed_postflop_action(m)
                        sz = inc / max(1.0, before) if inc > 0 else 0.0
                        out.append((current_street, a, sz))
                    added += inc
            elif current_log:
                # meta가 없는 외부 호출용 폴백.
                contrib = {}
                pot0 = float((self._pot_at or {}).get(current_street, 0) or 0)
                for x, a, amt in current_log:
                    before = pot0 + sum(contrib.values())
                    prev = contrib.get(x, 0.0)
                    target = prev
                    if a in ('bet', 'raise', 'allin', 'call'):
                        target = max(prev, float(amt or 0))
                    inc = max(0.0, target - prev)
                    if x == seat:
                        sz = (inc / max(1.0, before)) if inc > 0 else 0.0
                        out.append((current_street, a, sz))
                    contrib[x] = target
        return out

    def _pf_range_action(self, seat, aggressor=None):
        """pf_seed 의 실제 액션을 포스트플랍 레인지 역할로 바꾼다.

        역할(open/iso/defend)만 보면 iso 뒤 체크/오버림프도 open 으로
        오인된다. 실제 공개 액션을 우선한다.
        """
        h = self.h
        st = (getattr(h, 'pf_seed', {}) or {}).get(seat) or {}
        act = st.get('pf_act')
        role = st.get('pf_role')

        if act == 'check':
            return 'check'
        if act == 'limp':
            return 'limp'
        if act == 'call':
            return 'call'
        if act == '3bet':
            return '3bet'
        if act in ('raise', 'shove'):
            if role == 'defend':
                return '3bet'
            # BB의 iso raise는 RFI가 아니어서 open 모델이 0이 된다.
            # 전용 iso-range 모델을 만들기 전까지 기존 call 근사를 유지한다.
            if h.pos.get(seat) == 'BB' and role == 'iso':
                return 'call'
            return 'open'

        # seed가 없는 구형/외부 경로만 기존 추정으로 물러난다.
        return 'open' if seat == aggressor else 'call'

    def _locked_postflop_range(self, observer, target, observer_profile,
                               board, street, rnd, aggressor, seats, ante):
        """이전 street에서 이미 올인한 상대의 공개 range를 재구성한다.

        target은 현재 Round.order/rnd.live()에는 없지만 main-pot eligibility는
        남아 있다. 전략에는 아직 사용하지 않고 F8-D2 provenance로만 보존한다.

        현재 stack은 0이므로 preflop range stack input으로 쓰면 안 된다.
        마지막 preflop 판단 당시 pf_stack_bb를 우선하고, 구형/REPLAY seed에는
        hand-start stack depth로 물러난다.
        """
        h = self.h
        pfo = (getattr(h, 'pf_seed', {}) or {}).get(target) or {}
        act_o = self._pf_range_action(target, aggressor)
        oe = RD.perceived_profile(
            h.book, self._pid(observer), self._pid(target), observer_profile,
            random.Random(self._dseed(observer, street, 'polar', target)))
        opp_view = RD.range_profile(oe)
        rdp = None
        pol = 0.0
        if oe:
            rdp = PS.read_opponent(observer_profile, oe)
            pol = rdp.get('tb_polar', 0.0)
            if rdp.get('w', 0) > 0 and self._was_3bettor(target):
                act_o = '3bet'

        stack_bb = pfo.get('pf_stack_bb')
        if stack_bb is None:
            stack_bb = (
                float((getattr(h, '_start_stacks', {}) or {}).get(target, 0))
                / max(1.0, float(h.bb)))
        pf_vs_o = pfo.get('pf_vs') or h.pos.get(aggressor)
        orange = R.preflop_range(
            opp_view, h.pos[target], act_o, float(stack_bb or 0.0), set(board),
            n_callers=int(pfo.get('pf_n_callers', 0) or 0),
            opener_pos=pf_vs_o,
            open_bb=float(pfo.get('pf_open_bb', 2.5) or 2.5),
            seats=seats, ante=ante, polar=pol,
            raise_level=int(pfo.get('pf_level', 1) or 1))

        acts = self._acts_of(
            target, current_street=street, current_log=rnd.log,
            current_meta=rnd.action_meta)
        orange = R.perceived_range(
            orange, board, acts, observer_profile,
            actor_read=rdp if oe else None)
        orange, _note = RU.adjust_range_by_history(
            orange, h.dyn, self._pid(target), board,
            dead=set(h.hole[observer]) | set(board))
        return sorted(set(orange)), {
            'stack_bb': float(stack_bb or 0.0),
            'acts': list(acts),
        }


    def _run(self):
        h = self.h
        self._before = dict(h.stacks)
        rnd = RU.Round(None, [h.seat_of[p] for p in h.PRE if p in h.seat_of], h.stacks, h.bb)
        sb_s, bb_s = h.seat_of.get('SB'), h.seat_of.get('BB')
        if sb_s:
            pay = min(h.sb, rnd.stacks[sb_s]); rnd.stacks[sb_s] -= pay; rnd.contrib[sb_s] = pay
            if rnd.stacks[sb_s] <= 0:
                rnd.allin.add(sb_s)
        ante_pot = 0
        # 안테는 포맷이 정한 레벨부터 걷는다.
        # 예전에는 ante_from 이 저장만 되고 무조건 1레벨부터 걷혔다.
        _ante = getattr(h, 'ante', None)
        if _ante is None: _ante = h.bb
        if bb_s:
            pay = min(h.bb, rnd.stacks[bb_s]); rnd.stacks[bb_s] -= pay; rnd.contrib[bb_s] = pay
            if _ante > 0:
                a = min(_ante, rnd.stacks[bb_s]); rnd.stacks[bb_s] -= a; ante_pot = a
            if rnd.stacks[bb_s] <= 0:
                rnd.allin.add(bb_s)
        rnd.current = h.bb; rnd.min_raise = h.bb
        aggressor = None; limpers = []; callers = 0

        while True:
            # 살아있는 사람이 하나뿐이면 끝난 핸드다. BB 에게 액션을 물으면 안 된다.
            # (needs_action 은 '아직 액션 안 한 좌석'을 그대로 돌려주므로
            #  전원 폴드된 워크 상황에서도 BB 를 반환한다.)
            if len(rnd.live()) <= 1: break
            s = rnd.needs_action()
            if s is None: break
            pos = h.pos[s]; tc = rnd.to_call(s)
            if s == h.hero:
                act = yield {'stage': 'preflop', 'pos': pos, 'hole': h.hole[s],
                             'stacks': dict(rnd.stacks), 'contrib': dict(rnd.contrib),
                             'pot': rnd.contestable_contrib(s)+ante_pot, 'tocall': tc,
                             'stack': rnd.stacks[s], 'min_raise': rnd.current+rnd.min_raise,
                             'can_raise': rnd.can_raise(s), 'log': list(rnd.log),
                             'contrib': dict(rnd.contrib), 'live': list(rnd.live()),
                             'allin': list(rnd.allin), 'hash': h.hash}
                a, amt = act
                try: rnd.apply(s, a, amt)
                except ValueError as e:
                    act = yield {'stage': 'preflop', 'error': str(e), 'pos': pos,
                                 'hole': h.hole[s], 'pot': rnd.contestable_contrib(s)+ante_pot,
                                 'tocall': tc, 'stack': rnd.stacks[s],
                                 'min_raise': rnd.current+rnd.min_raise,
                                 'can_raise': rnd.can_raise(s), 'log': list(rnd.log),
                                 'hash': h.hash}
                    rnd.apply(s, act[0], act[1])
                aggressor, callers, limpers = _update_pf_state_after_apply(
                    rnd, s, aggressor, callers, limpers)
                continue
            ax, _ = h.axes(s); hand = h.hole[s]; bbs = rnd.stacks[s]/h.bb
            _opp_est_pf = (RD.perceived_profile(
                h.book, self._pid(s), self._pid(aggressor), ax,
                random.Random(self._dseed(s, 'preflop', 'pfest', aggressor)))
                if aggressor is not None and aggressor != s else None)
            _mj_obs = _money_jump_observe(
                h, s, rnd, 'preflop', ax, tc,
                rnd.contestable_contrib(s) + ante_pot,
                facing_seat=aggressor,
                decision_context={
                    'kind': ('vs_raise' if aggressor is not None else
                             'vs_limp' if limpers else 'unopened'),
                    'n_limpers': len(limpers),
                    'n_callers': callers,
                },
                facing_read=_opp_est_pf)
            _ck = _cache_key('pre', s, len(rnd.log))
            _cached = next((d for d in self.REPLAY if d[0] == _ck), None)
            if _cached:
                try: rnd.apply(s, _cached[1], _cached[2])
                except ValueError: rnd.apply(s, 'call' if tc > 0 else 'check')
                aggressor, callers, limpers = _update_pf_state_after_apply(
                    rnd, s, aggressor, callers, limpers)
                _money_jump_attach_action(_mj_obs, rnd)
                continue
            _pre_len = len(rnd.log)
            try:
                # 프리플랍도 판단 층을 거친다. 액션만 내고 끝내면
                # '왜 이렇게 쳤는가'가 플랍 계획에 이어지지 않는다.
                _behind = [rnd.stacks[x]/h.bb for x in rnd.order
                           if x != s and x not in rnd.folded
                           and rnd.order.index(x) > rnd.order.index(s)] \
                    if aggressor is None else None
                _obb = (rnd.current/h.bb) if aggressor is not None else 0.0
                _ordr = list(rnd.order)
                _behind_seats = ([x for x in _ordr[_ordr.index(s)+1:] if x in rnd.live()]
                                 if s in _ordr else [])
                _rlevel = max(1, int(getattr(rnd, 'full_raise_count', 0) or 0))
                a, sz, _seed = PL.preflop_plan(
                    ax, pos, hand, bbs, h.rng,
                    aggressor_pos=(h.pos[aggressor] if aggressor is not None else None),
                    open_bb=_obb, n_callers=callers, n_limpers=len(limpers),
                    raise_level=_rlevel, behind_stacks=_behind,
                    tilt=h.axes(s)[1], field_q=getattr(h, 'field_q', 0.6),
                    bf=h.bf(s),
                    seats=len(h.seats), ante=(getattr(h, 'ante', h.bb) > 0),
                    field_avg_bb=((getattr(h, 'field_avg_stack', None) or 0)
                                  / max(1, h.bb)) or None,
                    erosion=getattr(h, 'erosion_per_hand', 0.0),
                    bb_chips=h.bb,
                    # 어그레서가 이미 올인이면 리레이즈 대상이 없다.
                    # 이 정보가 없어서 올인 금액을 '큰 오픈'으로 보고 그 위에
                    # 3벳 배수를 곱했고, 100bb 가 22bb 상대로 통째로 올인했다.
                    opener_allin=(aggressor is not None
                                  and rnd.stacks.get(aggressor, 1) <= 0),
                    # 뒤에 남은 사람 / 림퍼의 추정치. 예전에는 오픈·아이소가
                    # 상대 정보를 전혀 안 받았다 — 뒤 스택은 넘어가는데
                    # 뒤 사람의 성향은 안 넘어갔다.
                    behind_est=(self._reads_for(s, _behind_seats, ax)
                                if aggressor is None else None),
                    limper_est=(self._reads_for(s, limpers, ax)
                                if aggressor is None and limpers else None),
                    payout_flat=getattr(h, 'payout_flat', 0.0),
                    reentry=getattr(h, 'reentry', False),
                    progress=getattr(h, 'progress', 0.0),
                    opp_est=_opp_est_pf,
                    money_open=(_mj_obs.get('unopened_modifiers')
                                if _mj_obs else None),
                    can_check=(tc <= 0),
                    can_raise=rnd.can_raise(s),
                    pot_bb=((rnd.contestable_contrib(s) + ante_pot) / max(1, h.bb)),
                    to_call_bb=(tc / max(1, h.bb)),
                    prior_pf=((getattr(h, 'pf_seed', {}) or {}).get(s)))
                h.pf_seed = getattr(h, 'pf_seed', {})
                h.pf_seed[s] = _merge_pf_seed(h.pf_seed.get(s), _seed)
                _seed = h.pf_seed[s]
                if a == 'fold':
                    rnd.apply(s, 'fold' if tc > 0 else 'check')
                elif a == 'check':
                    rnd.apply(s, 'check')
                elif a == 'limp':
                    rnd.apply(s, 'call')
                elif a == 'call':
                    rnd.apply(s, 'call')
                elif a == 'shove':
                    rnd.apply(s, 'allin')
                else:
                    rnd.apply(s, 'raise',
                              max(RU.shape_size(h.bb*sz, ax['type'], h.rng),
                                  rnd.current + rnd.min_raise))
            except ValueError:
                rnd.apply(s, 'call' if tc > 0 else 'check')
            aggressor, callers, limpers = _update_pf_state_after_apply(
                rnd, s, aggressor, callers, limpers)
            _money_jump_attach_action(_mj_obs, rnd)

        _pf_uncalled = rnd.settle_uncalled()
        if _pf_uncalled:
            h.uncalled_returns = getattr(h, 'uncalled_returns', [])
            h.uncalled_returns.append(dict(_pf_uncalled, street='preflop'))

        self.full_log = [('preflop', x, a, amt) for (x, a, amt) in rnd.log]
        # 프리플랍 관찰 기록
        _pid = self._pid
        seats_all = [x for x in rnd.order]
        acted = {}
        for (x, a_, _) in rnd.log:
            acted.setdefault(x, []).append(a_)
        obs_ids = [_pid(x) for x in seats_all]
        # 림프 판정: 로그를 순서대로 훑어 '아직 레이즈가 없던 시점'을 표시한다.
        # 기회를 따로 세지 않으면 얼리에서 늘 폴드하는 사람이
        # '림프 안 하는 사람'으로 잡힌다 — 그건 성향이 아니라 좁은 레인지다.
        _limped, _limp_chance = set(), set()
        _limp_idx = {}
        _seen_raise = False
        for _idx, m in enumerate(rnd.action_meta):
            x, a_ = m.get('seat'), m.get('action')
            if not _seen_raise and x not in _limp_chance:
                _limp_chance.add(x)
                if a_ == 'call' and not m.get('raised'):
                    _limped.add(x)
                    _limp_idx.setdefault(x, _idx)
            # all-in call은 unopened 상태를 끝내지 않는다. 실제 가격 상승만 본다.
            if m.get('raised'):
                _seen_raise = True
        for x in seats_all:
            acts = acted.get(x, [])
            _mx = [m for m in rnd.action_meta if m.get('seat') == x]
            vpip = any((m.get('action') == 'call') or m.get('raised')
                       or m.get('allin_call') for m in _mx)
            pfr = any(m.get('raised') for m in _mx)
            # 림프 = 무저항 상태에서 콜. 기회(무저항으로 돌아온 자리)도 같이 센다.
            _limp = (x in _limped)
            _lchance = (x in _limp_chance)
            # 그 자리의 기준 오픈 폭도 같이 넘긴다. 관찰을 기준 대비로 만든다.
            _rexp = _GTO.rfi(h.pos.get(x, 'HJ'), len(h.seats), h.bbs(x),
                             getattr(h, 'ante', h.bb) > 0) if _lchance else None
            h.book.observe_preflop(obs_ids, _pid(x), vpip, pfr, _limp, _lchance, _rexp)

            # 림프 후 **첫 레이즈 하나만** 돌아온 경우의 반응.
            # 두 번째 레이즈까지 들어오면 이미 squeeze/3bet 대응이라
            # 아이소 폴드 성향 표본에 섞지 않는다.
            _faced_lr = _folded_lr = False
            _li = _limp_idx.get(x)
            if _li is not None:
                _rb_lr = 0
                for m in rnd.action_meta[_li+1:]:
                    if m.get('seat') == x:
                        if _rb_lr == 1:
                            _faced_lr = True
                            _folded_lr = (m.get('action') == 'fold')
                        break
                    if m.get('full_raise'):
                        _rb_lr += 1
            h.book.observe_limp_raise(obs_ids, _pid(x), _faced_lr, _folded_lr)

            # 역할을 섞지 않는다:
            # opener의 fold-to-3bet / 4bet과 caller의 squeeze 대응은 별개다.
            _pfobs = _pf_observation_flags(rnd.action_meta, x)
            h.book.observe_3bet(
                obs_ids, _pid(x),
                _pfobs['threebet_chance'], _pfobs['did_threebet'],
                _pfobs['faced_threebet_as_opener'],
                _pfobs['folded_to_threebet_as_opener'])
            h.book.observe_4bet(
                obs_ids, _pid(x),
                _pfobs['fourbet_chance_as_opener'],
                _pfobs['did_fourbet_as_opener'],
                _pfobs['faced_fourbet_as_threebettor'],
                _pfobs['folded_to_fourbet_as_threebettor'])
            h.book.observe_backraise(
                obs_ids, _pid(x),
                _pfobs['backraise_chance_as_caller'],
                _pfobs['did_backraise'],
                _pfobs['folded_to_squeeze_after_call'])
        contrib = dict(rnd.contrib)
        if bb_s: contrib[bb_s] = contrib.get(bb_s, 0)          # 안테는 별도
        for k in rnd.stacks: h.stacks[k] = rnd.stacks[k]
        folded = set(rnd.folded)
        live = [x for x in rnd.order if x not in folded]
        dead = ante_pot

        if len(live) <= 1:
            self.result = self._finish(contrib, dead, folded, live, [], 'preflop')
            return

        prev = []
        for street, nc in [('flop', 3), ('turn', 4), ('river', 5)]:
            board = h.board[:nc]
            active = [x for x in live if h.stacks[x] > 0]
            if len(active) < 2: break
            order = [h.seat_of[p] for p in h.POST if p in h.seat_of and h.seat_of[p] in active]
            r2 = RU.Round(None, order, h.stacks, h.bb)
            street_aggr = aggressor          # 이 스트리트에 들어올 때의 공격자(루프 중 갱신되므로 스냅샷)
            pot_now = sum(contrib.values()) + dead
            self._pot_at[street] = pot_now      # 사이즈 비율 계산 기준
            while True:
                if len(r2.live()) <= 1: break     # 한 명만 남으면 그 스트리트는 끝
                s = r2.needs_action()
                if s is None: break
                tc = r2.to_call(s)
                # F8-D1: 판단 시점 pot geometry를 전략과 분리해 기록한다.
                # 이전 street 누적 + 현재 street 기여를 합치므로, 이전 street
                # all-in의 main-pot eligibility와 현재 side-pot 상태가 동시에 보인다.
                _pot_layers = _decision_pot_layers(
                    contrib, r2.contrib, folded | set(r2.folded), r2.stacks,
                    hero=s, dead=dead)
                if s == h.hero:
                    act = yield {'stage': street, 'board': board, 'hole': h.hole[s],
                                 'stacks': dict(r2.stacks), 'contrib': dict(r2.contrib),
                                 'pot': pot_now + r2.contestable_contrib(s), 'tocall': tc,
                                 'stack': r2.stacks[s], 'min_raise': r2.current+r2.min_raise,
                                 'can_raise': r2.can_raise(s), 'log': list(r2.log),
                                 'prior_log': list(getattr(self, 'full_log', [])),
                                 'live': r2.live(), 'contrib': dict(r2.contrib),
                                 'allin': list(r2.allin),
                                 'pot_layers': _pot_layers, 'hash': h.hash}
                    try: r2.apply(s, act[0], act[1])
                    except ValueError as e:
                        act = yield {'stage': street, 'error': str(e), 'board': board,
                                     'hole': h.hole[s], 'pot': pot_now+r2.contestable_contrib(s),
                                     'tocall': tc, 'stack': r2.stacks[s],
                                     'min_raise': r2.current+r2.min_raise,
                                     'can_raise': r2.can_raise(s), 'log': list(r2.log),
                                     'live': r2.live(), 'hash': h.hash}
                        r2.apply(s, act[0], act[1])
                    # allin 문자열은 call일 수도 있다. 실제 가격을 올린 사건만
                    # 새 aggressor가 된다.
                    if r2.action_meta and r2.action_meta[-1].get('raised'):
                        aggressor = s
                    continue
                ax, _ = h.axes(s)
                _ck = _cache_key(street, s, len(r2.log))
                _forced = next((d for d in self.REPLAY if d[0] == _ck), None)
                # 예전에는 여기서 바로 apply 하고 continue 했다. 그러면 계획 수립을
                # 통째로 건너뛰어서 **액션은 실행되는데 그 근거가 없었다.**
                # plan=None 기록이 그래서 나왔고, 계획-집행 일치 검사의
                # 사각지대가 됐다(포스트플랍 기록의 13%).
                # 이제는 계획을 정상적으로 계산하고, 확정된 액션만 캐시 값으로
                # 덮어쓴다. 재현성은 그대로고 기록은 완전해진다.
                behind = len([x for x in order if x not in r2.acted and x != s and x not in r2.folded])
                n_opp = len(r2.live())-1
                # 포지션은 '이 스트리트 액션 순서에서 누구 뒤인가'다.
                # 소비처마다 기준이 다르다:
                #   cbet_freq(plan.py:1194,1197) 는 필드 전체(= last to act 인가)
                #   blockbet(442) / donk(904) 는 **어그레서 한 명** 기준
                _oop_f = oop_field(order, s, r2.folded, r2.allin)
                _oop_a = (oop_vs(order, s, aggressor)
                          if (aggressor is not None and aggressor != s
                              and aggressor in order
                              and aggressor not in r2.folded
                              and aggressor not in r2.allin)
                          else None)
                # 어그레서가 없으면 442/904 의 의미가 정해지지 않는다.
                # 그 경우에만 쓰는 legacy 절대식 — _oop_a 에는 넣지 않는다.
                _oop_legacy = (h.POST.index(h.pos[s]) < 3)
                _seats, _ante = len(h.seats), (getattr(h, 'ante', h.bb) > 0)
                # **프리플랍 역할과 포스트플랍 공격자는 다른 개념이다.**
                # 예전에는 'open' if s == aggressor 로 포스트플랍 공격자에게
                # 프리플랍 오픈 레인지를 매겼다. BB 가 플랍에서 베팅하면
                # role='open' 이 되는데, BB 는 프리플랍에 오픈한 적이 없다.
                # 그 결과 BB/open 호출 70회가 **전부 빈 레인지**를 반환했고,
                # nut_adv/range_adv 가 0 으로 죽고 opp_r 폴백까지 오염됐다.
                # 프리플랍 역할은 이미 pf_seed 에 저장돼 있다 — 추정하지 않는다.
                _pfr = (getattr(h, 'pf_seed', {}) or {}).get(s) or {}
                _role = self._pf_range_action(s, aggressor)
                _pf_vs = _pfr.get('pf_vs') or h.pos.get(aggressor)
                my_r = R.preflop_range(
                    ax, h.pos[s], _role, h.bbs(s), set(board),
                    n_callers=int(_pfr.get('pf_n_callers', 0) or 0),
                    opener_pos=_pf_vs,
                    open_bb=float(_pfr.get('pf_open_bb', 2.5) or 2.5),
                    seats=_seats, ante=_ante,
                    raise_level=int(_pfr.get('pf_level', 1) or 1))
                my_r = sorted(set(my_r))      # 순서 확정 (판단이 순서에 의존하면 안 된다)
                opp_r = []
                opp_ranges = {}
                for o in r2.live():
                    if o == s: continue
                    # 상대의 실제 persona/tilt 는 관찰자가 알 수 없다.
                    # 공개 행동에서 만든 perceived_profile 만으로 프리플랍 레인지를 만든다.
                    _pfo = (getattr(h, 'pf_seed', {}) or {}).get(o) or {}
                    _act_o = self._pf_range_action(o, aggressor)
                    _pol = 0.0
                    _oe = RD.perceived_profile(
                        h.book, self._pid(s), self._pid(o), ax,
                        random.Random(self._dseed(s, street, 'polar', o)))
                    _opp_view = RD.range_profile(_oe)
                    if _oe:
                        _rdp = PS.read_opponent(ax, _oe)
                        _pol = _rdp.get('tb_polar', 0.0)
                        if _rdp.get('w', 0) > 0 and self._was_3bettor(o):
                            _act_o = '3bet'
                    _pf_vs_o = _pfo.get('pf_vs') or h.pos.get(aggressor)
                    orange = R.preflop_range(
                        _opp_view, h.pos[o], _act_o,
                        h.bbs(o), set(board),
                        n_callers=int(_pfo.get('pf_n_callers', 0) or 0),
                        opener_pos=_pf_vs_o,
                        open_bb=float(_pfo.get('pf_open_bb', 2.5) or 2.5),
                        seats=_seats, ante=_ante, polar=_pol,
                        raise_level=int(_pfo.get('pf_level', 1) or 1))
                    # 관측된 포스트플랍 액션으로 레인지를 좁힌다.
                    # 이걸 빼면 상대가 무슨 행동을 했든 매 스트리트 프리플랍 레인지가 된다.
                    # 상대 레인지는 '이 사람이 인식하는 만큼'만 좁혀진다 (range_read).
                    # 인자가 둘이다. ax 는 **관찰자(나)**, _rdp 는 **행위자(상대)** 읽기.
                    # 예전에는 ax 하나만 넘겨서 자기 블러프 성향으로
                    # 상대 레인지를 좁혔다 — 자기 투사였다.
                    orange = R.perceived_range(
                        orange, board,
                        self._acts_of(
                            o, current_street=street, current_log=r2.log,
                            current_meta=r2.action_meta),
                        ax, actor_read=_rdp if _oe else None)
                    # 쇼다운 이력이 예상보다 넓/좁았다면 추가 보정
                    orange, _note = RU.adjust_range_by_history(
                        orange, h.dyn, self._pid(o), board,
                        dead=set(h.hole[s])|set(board))
                    orange = sorted(set(orange))
                    opp_ranges[o] = orange
                    opp_r.extend(orange)

                # F8-D2: 이전 street에서 이미 올인해 현재 Round에서 빠진 상대도
                # pot layer에는 남아 있다. 그 공개 range를 별도 map으로 복원한다.
                # 아직 opp_r/opp_ranges에는 합치지 않는다 — D3까지 전략 무영향.
                locked_opp_ranges = {}
                locked_opp_range_meta = {}
                _locked_opps = sorted({
                    o
                    for layer in (_pot_layers or [])
                    for o in (layer.get('locked_allin_opponents') or [])
                    if o != s
                }, key=lambda x: str(x))
                for o in _locked_opps:
                    _lr, _lm = self._locked_postflop_range(
                        s, o, ax, board, street, r2, aggressor, _seats, _ante)
                    locked_opp_ranges[o] = _lr
                    locked_opp_range_meta[o] = _lm

                # F8-D3: main/side layer별 equity를 진단값으로만 계산한다.
                # locked opponent가 없는 일반 팟에서는 비용조차 추가하지 않는다.
                # 이 결과는 아래 intent에만 기록되고 전략 함수에는 전달되지 않는다.
                layer_equities = (
                    _diagnostic_layer_equities(
                        h.hole[s], board, _pot_layers,
                        opp_ranges, locked_opp_ranges, sims=600)
                    if locked_opp_ranges else [])

                # 레인지는 집합이지 수열이 아니다. 상류(축소·이력보정)에서 순서가
                # 흔들려도 판단이 바뀌면 안 되므로 여기서 순서를 확정한다.
                # 이걸 빼면 같은 시드가 재현되지 않는다 (rng.choice 가 순서에 의존).
                opp_r = sorted(set(opp_r))
                if not opp_r: opp_r = sorted(set(my_r))
                key = s
                if key in h.plans and street != h.plans[key].get('street_made'):
                    h.plans[key].setdefault('streets', []).append(street)
                # 주 상대를 정한다: 공격자가 있으면 그 사람, 없으면 스택이 가장 깊은 상대.
                # 계획 수립·갱신·실행이 모두 같은 상대를 봐야 하므로 분기 밖에서 만든다.
                _others = [x for x in r2.live() if x != s]
                _main = aggressor if (aggressor is not None and aggressor != s
                                      and aggressor in _others) else (
                        max(_others, key=lambda x: r2.stacks.get(x, 0)) if _others else None)
                _est = (RD.perceived_profile(h.book, _pid(s), _pid(_main), ax,
                                             random.Random(self._dseed(s, street, 'est', _main)))
                        if _main is not None else None)
                _ostk = (r2.stacks.get(_main, 0)/h.bb) if _main is not None else None

                # F2/probe context. 이전 스트리트의 알려진 공격자가 실제로
                # 체크했고 그 스트리트가 베팅 없이 끝났는지를 **현재 intent를
                # 만들기 전에** 계산한다.
                _prev_street = {'turn': 'flop', 'river': 'turn'}.get(street)
                _opp_checked_prev = None
                if (_prev_street and aggressor is not None and aggressor != s):
                    _pr = [x for x in (getattr(self, 'full_log', []) or [])
                           if x[0] == _prev_street]
                    _pm = [m for m in (getattr(self, 'full_action_meta', []) or [])
                           if m.get('street') == _prev_street]
                    _prev_any_bet = (any(m.get('raised') for m in _pm)
                                     if _pm else
                                     any(x[2] in ('bet', 'raise') for x in _pr))
                    _aggr_checked = any(
                        x[1] == aggressor and x[2] == 'check' for x in _pr)
                    _opp_checked_prev = bool(_pr) and _aggr_checked and not _prev_any_bet

                # 계획 갱신은 update_plan 하나로 들어간다.
                # (예전에는 make/revise/refresh/river_fix/_allowed/attach 를
                #  여기서 직접 순서대로 불렀고, 그 순서 의존이 이력 유실을 만들었다)
                h.plans[key] = PL.update_plan(
                    h.plans.get(key), h.hole[s], board, my_r, opp_r, ax,
                    pot_now, r2.stacks[s], street,
                    self._dseed(s, street, 'plan', len(r2.log)),
                    n_opp, behind, prev,
                    _oop_f, s == aggressor,
                    opp_est=_est, opp_stack_bb=_ostk, tilt=h.axes(s)[1],
                    oop_vs_aggr=_oop_a, oop_legacy_abs=_oop_legacy,
                    first=(key not in h.plans or street == 'flop'),
                    pf_seed=getattr(h, 'pf_seed', {}).get(s),
                    bb_chips=h.bb, opp_ranges=opp_ranges,
                    opp_checked_prev=_opp_checked_prev)
                # 실제 팟은 스트리트 시작 팟 + 이번 스트리트에 들어온 칩이다.
                # pot_now 만 넘기면 봇이 팟을 실제보다 작게 보고 팟오즈를 과대 요구한다
                # (= 모든 스트리트에서 체계적 과잉 폴드). 히어로 화면(208행)은 이미 이 값을 쓴다.
                pot_live = pot_now + r2.contestable_contrib(s)
                _resp_ctx = _postflop_response_context(r2, s)
                _mj_obs = _money_jump_observe(
                    h, s, r2, street, ax, tc, pot_live,
                    facing_seat=(aggressor if tc > 0 else None),
                    decision_context={'kind': _resp_ctx['kind']},
                    facing_read=(_est if tc > 0 and aggressor == _main else None))
                _pl = h.plans[key]
                h.intents = getattr(h, 'intents', [])
                # 액션 전 관측. 순번을 붙여 매 액션마다 남긴다 —
                # 한 스트리트에서 여러 번 액션하면 그 사이 판단도 각각 달라진다.
                _oidx = sum(1 for i in h.intents
                            if i['street'] == street and i['seat'] == s)
                if True:
                    # 리뷰가 코드를 고칠 수 있으려면 '무엇을 했나'가 아니라
                    # **'그 시점에 무엇을 봤나'**가 남아야 한다.
                    # 오늘 디버깅에서 매번 없어서 막혔던 값들이다.
                    h.intents.append({
                        'street': street, 'seat': s, 'idx': _oidx,
                        'type': ax.get('type'),
                        'plan': _pl.get('plan'), 'why': _pl.get('why'),
                        'rel': _pl.get('rel'), 'eq': _pl.get('eq'),
                        'outs': _pl.get('outs'), 'made': _pl.get('made'),
                        # 기록 전용 provenance. 판단에는 안 쓰인다.
                        # eq 가 현재 강도인지 미래 개선분인지 사후 복원용.
                        'eq_current': _pl.get('eq_current'),
                        'eq_delta': _pl.get('eq_delta'),
                        'eq_sims': _pl.get('eq_sims'), 'eq_seed': _pl.get('eq_seed'),
                        'outs_true': _pl.get('outs_true'),
                        'my_range_n': _pl.get('my_range_n'),
                        'my_range_sig': _pl.get('my_range_sig'),
                        'opp_range_n': _pl.get('opp_range_n'),
                        'opp_range_sig': _pl.get('opp_range_sig'),
                        'opp_ranges_n': _pl.get('opp_ranges_n'),
                        'opp_ranges_sig': _pl.get('opp_ranges_sig'),
                        # F8-D2 provenance only; active strategy pools remain unchanged.
                        'locked_opp_ranges_n': {
                            str(k): len(v) for k, v in locked_opp_ranges.items()},
                        'locked_opp_ranges_sig': {
                            str(k): PL._range_sig(v)
                            for k, v in locked_opp_ranges.items()},
                        'locked_opp_range_stack_bb': {
                            str(k): locked_opp_range_meta[k].get('stack_bb')
                            for k in locked_opp_ranges},
                        # F8-D3 provenance only. Layer equity is not a strategy input.
                        'layer_equities': layer_equities,
                        'blocker': _pl.get('blocker'),
                        'blocker_net': _pl.get('blocker_net'),
                        'nut_adv': _pl.get('nut_adv'), 'range_adv': _pl.get('range_adv'),
                        'spr': _pl.get('spr'), 'danger': _pl.get('danger'),
                        # 계획이 언제 세워졌고 어느 스트리트에서 갱신됐나.
                        # 'refresh 가 안 돌아서 낡은 rel 로 판단'을 잡으려면 필요하다.
                        'street_made': _pl.get('street_made'),
                        'refreshed': list(_pl.get('refreshed') or []),
                        'deviations': list(_pl.get('deviations') or []),
                        # 상황 문맥. 같은 판단이 버블에서 달라지는지 본다.
                        'bf': round(h.bf(s), 3), 'tilt': h.axes(s)[1],
                        # 소비처별로 기준이 달라 하나로 못 적는다.
                        # oop_vs_aggr 은 어그레서가 없으면 None 이다.
                        'oop_field': _oop_f,
                        'oop_vs_aggr': _oop_a,
                        'oop_legacy_abs': _oop_legacy,
                        'init': RU.has_initiative(s, aggressor),
                        'n_opp': n_opp, 'behind': behind,
                        'response_kind': _resp_ctx.get('kind'),
                        'facing_kind': _resp_ctx.get('facing_kind'),
                        'prior_action': _resp_ctx.get('prior_action'),
                        'prior_facing_kind': _resp_ctx.get('prior_facing_kind'),
                        'raise_depth_full': _resp_ctx.get('raise_depth_full'),
                        'facing_full_raise': _resp_ctx.get('facing_full_raise'),
                        'facing_incomplete_raise': _resp_ctx.get('facing_incomplete_raise'),
                        'hero_contrib': _resp_ctx.get('hero_contrib'),
                        # F8-D1 provenance only. update_plan/act_with_plan에는 넘기지 않는다.
                        'pot_layers': _pot_layers,
                    })
                # --- 배팅라인 리딩: 진짜 프로필이 아니라 '내가 관찰한 추정치'로 ---
                read_val = None
                est = None
                _facing_ctx = (_facing_wager_context(r2, aggressor, pot_now)
                               if tc > 0 else None)
                if tc > 0 and aggressor is not None and aggressor != s:
                    est = RD.perceived_profile(h.book, _pid(s), _pid(aggressor), ax,
                                               random.Random(self._dseed(s, street, 'est2', aggressor)))
                    # 배럴 수는 액션 문자열 개수가 아니라 **공격한 스트리트 수**다.
                    # 현재 스트리트 액션도 full_log 에 아직 안 들어갔으므로 포함한다.
                    n_barrels = _barrel_count(
                        getattr(self, 'full_action_meta', []),
                        r2.action_meta, aggressor, street)
                    sz_frac = ((_facing_ctx or {}).get('size_frac')
                               if _facing_ctx else None)
                    if sz_frac is None:
                        sz_frac = tc/max(1, pot_live)
                    # '어그레서가 **나보다 먼저** 액션하는 자리에서 리드했는가'다.
                    # 절대 인덱스로 재면 상대가 누구든 같은 값이 나온다.
                    read_val = PL.line_bluff_prior(est, street, n_barrels, sz_frac, board,
                                                  oop_vs(order, aggressor, s))
                    h.reads_log = getattr(h, 'reads_log', [])
                    h.reads_log.append({'street': street, 'observer': s, 'target': aggressor,
                                        'est_bluff': round(est['bluff'],1),
                                        'confidence': est['confidence'], 'n': est['n'],
                                        'barrels': n_barrels, 'read': round(read_val,2)})
                # 체크레이즈 라우팅 감사용: 판단에는 쓰지 않는 provenance.
                # generic facing-bet response가 checkraise 전용 gate보다 먼저 raise를
                # 만들어내는지 확인하려면 act_with_plan 호출 전에 체크 이력이 필요하다.
                _already_checked = bool(
                    tc > 0 and any(x == s and act == 'check' for (x, act, _) in r2.log))
                a2, eq, need = PL.act_with_plan(
                    h.hole[s], board, ax, h.plans[key], pot_live, tc,
                    r2.stacks[s], street,
                    initiative=RU.has_initiative(s, aggressor),
                    opp_range=opp_r, opp_ranges=opp_ranges, facing_seat=aggressor,
                    bf=h.bf(s), seed=self._dseed(s, street, 'act', len(r2.log)),
                    n_opp=n_opp, to_act_behind=behind, read=read_val,
                    opp_est=(est if tc > 0 and aggressor is not None
                             and aggressor != s else None),
                    checked_before=_already_checked,
                    can_raise=r2.can_raise(s),
                    checkraise_seed=self._dseed(s, street, 'ckr', len(r2.log)),
                    checkraise_size_seed=self._dseed(
                        s, street, 'ckrsz', len(r2.log)),
                    facing_size_frac=(
                        (_facing_ctx or {}).get('size_frac')
                        if _facing_ctx else None),
                    hero_contrib=r2.contrib.get(s, 0),
                    response_kind=_resp_ctx.get('kind'),
                    response_context=_resp_ctx)
                _tr = (h.plans.get(key) or {}).get('trace')
                if _tr:
                    for _i in h.intents:
                        if _i['street'] == street and _i['seat'] == s and 'trace' not in _i:
                            _i['trace'] = [x for x in _tr if x.get('street') == street]
                            break
                a, amt = a2
                if _forced:
                    # 이미 확정된 결정은 그대로 재생한다. 계획은 위에서 정상적으로
                    # 계산됐으므로 기록에는 근거가 남고, 실행만 고정된다.
                    a, amt = _forced[1], _forced[2]
                # 어느 스트리트에서 실제로 공격했는지 기록한다 (지연 씨벳 판단에 필요).
                if a in ('bet', 'raise', 'allin'):
                    h.plans[key].setdefault('bet_streets', [])
                    if street not in h.plans[key]['bet_streets']:
                        h.plans[key]['bet_streets'].append(street)
                # 체크레이즈는 act_with_plan 내부의 response-plan 단계에서만
                # 결정된다. session 은 더 이상 액션을 사후에 덮어쓰지 않고
                # provenance 만 기록한다.
                if _already_checked:
                    _ckr_source = ('forced_replay' if _forced else
                                   (h.plans.get(key) or {}).get(
                                       '_last_response_source', 'unknown'))
                    h.checkraise_audit = getattr(h, 'checkraise_audit', [])
                    h.checkraise_audit.append({
                        'street': street,
                        'seat': s,
                        'plan': (h.plans.get(key) or {}).get('plan'),
                        'source': _ckr_source,
                        'response_act': a2[0],
                        'final_act': a,
                        'gate_called': (not _forced),
                        'gate_taken': (_ckr_source == 'checkraise_gate'),
                        'checkraise_skill': PS.sk(
                            ax, PS.street_concept('checkraise', street))
                            if ax.get('concepts') else None,
                        'reraise_skill': PS.sk(ax, 'reraise') if ax.get('concepts') else None,
                        'bluff_skill': PS.sk(ax, 'bluff') if ax.get('concepts') else None,
                        'semibluff_skill': PS.sk(ax, 'semibluff') if ax.get('concepts') else None,
                        'rel': (h.plans.get(key) or {}).get('rel'),
                        'outs': (h.plans.get(key) or {}).get('outs'),
                    })
                try:
                    # 이 액션에 **적용된** 제약을 apply 이전에 잡는다.
                    # apply 는 self.min_raise/current 를 갱신하므로, 사후에 읽으면
                    # 다음 사람에게 적용될 값을 보게 된다(무저항 벳 X → 기록 2X).
                    _cur0 = r2.current
                    _mr0 = r2.min_raise
                    # near-all-in 분석용 provenance. 판단에는 쓰지 않는다.
                    # target은 이번 street 총 기여액 좌표이므로 actor/opp 모두
                    # (remaining stack + current contribution)으로 맞춘다.
                    _contrib_before = r2.contrib.get(s, 0)
                    _actor_cap = r2.stacks[s] + _contrib_before
                    _opp_caps = [
                        r2.stacks[x] + r2.contrib.get(x, 0)
                        for x in r2.live() if x != s
                    ]
                    # multiway에는 상대별 effective stack이 따로 있지만,
                    # 여기서는 "적어도 한 명이 끝까지 contest할 수 있는 최대치"를
                    # diagnostic scalar로 쓴다.
                    _opp_cap_max = max(_opp_caps) if _opp_caps else _actor_cap
                    _effective_cap = min(_actor_cap, _opp_cap_max)
                    # 재생값을 **다시 shape 하지 않는다.** _forced[2] 는 아래
                    # 587줄이 r2.log 에서 꺼내 기록한 집행값이라 이미 shape 를
                    # 거쳤다. 두 번 먹이면 같은 상황을 재생했는데 다른 금액이
                    # 나온다(실측: river bet 3100 → 재생 3200). shape_size 는
                    # rng.uniform 지터를 곱하므로 멱등이 아니다.
                    # 그러면 이후 tocall 이 어긋나 히어로의 기록된 액션이 불법이
                    # 되고, 그 핸드가 영구히 막힌다.
                    # amt 가 아직 재생값 그대로일 때만 건너뛴다 — 위 체크레이즈
                    # 분기가 amt 를 새로 계산했다면 그건 라이브와 같은 경로이므로
                    # 라이브처럼 shape 를 먹여야 한다.
                    _replayed = bool(_forced) and a == _forced[1] and amt == _forced[2]
                    if a in ('bet', 'raise') and not _replayed:
                        # 판단층이 이미 정확히 올인을 선택했다면 타입별 sizing jitter가
                        # 그 결정을 다시 줄여 작은 잔여 스택을 만들면 안 된다.
                        # target은 이번 스트리트 총 기여액 기준이므로 현재 contrib까지
                        # 포함한 최대 target과 비교한다.
                        _max_target = r2.stacks[s] + r2.contrib.get(s, 0)
                        if amt < _max_target:
                            amt = RU.shape_size(
                                amt, ax['type'],
                                random.Random(self._dseed(s, street, 'size', len(r2.log))),
                                pot=pot_live)
                        else:
                            amt = _max_target
                    if a in ('bet', 'raise'):
                        # 클램프 이후의 final legal target을 먼저 만든다.
                        _sent = max(amt, r2.current+r2.min_raise) if r2.current else amt
                        _pre_effective_target = _sent
                        _ea = RU.effective_allin_v1(
                            _sent, _actor_cap, _opp_cap_max,
                            _contrib_before, pot_live)
                        _ea_applied = bool(_ea['effective'] and not _replayed)
                        _allin_execution_mode = (
                            'shove' if _ea_applied else
                            'replay' if _replayed else
                            'none')
                        # v1 실행 모드는 shove 하나뿐이다. 미래의 intentional
                        # leave-behind는 이 **분류 이후** 별도 실행 모드로 들어온다.
                        if _ea_applied:
                            _sent = _actor_cap

                        _target_capped = min(_actor_cap, _sent)
                        _increment = max(0, _target_capped - _contrib_before)
                        _pot_after = pot_live + _increment
                        _own_residual_post = max(0, _actor_cap - _target_capped)
                        _effective_gap = max(
                            0, _effective_cap - min(_effective_cap, _sent))
                        _post_spr_own = (
                            _own_residual_post / max(1.0, _pot_after))
                        _post_spr_effective = (
                            _effective_gap / max(1.0, _pot_after))
                        r2.apply(s, a, _sent)
                        _exec_amt = _sent
                    else:
                        r2.apply(s, a, amt)
                        _exec_amt = amt
                except ValueError as _ve:
                    # 사이즈가 규칙에 안 맞아 거부됐다. 폴백하되 그 사실을 남긴다.
                    # 기록이 없으면 '의도는 벳인데 체크가 실행됨'이 원인 불명으로 남는다.
                    _fb = 'call' if tc > 0 else 'check'
                    h.plans[key].setdefault('deviations', []).append(
                        {'street': street, 'planned': a, 'executed': _fb,
                         'why': '사이즈 거부(%s)' % _ve})
                    a = _fb
                    r2.apply(s, a)
                    _exec_amt = 0
                if r2.action_meta and r2.action_meta[-1].get('raised'):
                    aggressor = s
                if r2.log: self.recorded.append((_ck, r2.log[-1][1], r2.log[-1][2]))

                # 실제 실행 이력. delayed-cbet/probe 같은 다음 스트리트 판단은
                # 계획했던 행동이 아니라 테이블에서 실제로 일어난 행동을 봐야 한다.
                _ea_hist = h.plans[key].setdefault('executed_actions', {})
                _ea_hist.setdefault(street, []).append(a)

                _money_jump_attach_action(_mj_obs, r2)
                # 액션이 끝난 뒤 계획을 다시 손대지 않는다.
                # _allowed(개념 보유 검사)는 update_plan 안에서 이미 적용됐고,
                # 여기서 또 돌리면 '실행 후 계획 변경' = 사후 수정이 된다.
                _pl2 = h.plans[key]
                # 대응 사유는 계획의 trace 에 kind='response' 로 남아 있다.
                _rsrc = None
                for _t in reversed(_pl2.get('trace') or []):
                    if _t.get('kind') == 'response' and _t.get('street') == street:
                        _rsrc = _t.get('why')
                        break
                # 의도와 실행을 **나란히** 남긴다. 예전에는 실행된 action 만 남아서
                # '계획대로 집행됐는가'를 사후에 검증할 방법이 아예 없었다
                # (계획이 옳은지와 별개로, 배선이 끊겨도 알 수가 없었다).
                _it = (_pl2.get('intents') or {}).get(street) or {}
                _dev = [d for d in (_pl2.get('deviations') or []) if d.get('street') == street]
                h.intents = getattr(h, 'intents', [])
                # **한 스트리트에 한 좌석이 여러 번 액션한다.** 벳 → 3벳 → 재대응이
                # 그렇다. 예전에는 (스트리트, 좌석) 하나로 덮어써서 마지막 것만
                # 남았고, 그 사이의 판단이 통째로 사라졌다.
                # 액션 전 관측 기록(위에서 append)에 실행 결과를 **합친다**.
                # 따로 append 하면 한 액션이 두 줄이 되어 리뷰가 꼬인다.
                _slot = None
                for _i in reversed(h.intents):
                    if (_i['street'] == street and _i['seat'] == s
                            and 'action' not in _i):
                        _slot = _i
                        break
                if _slot is None:
                    _slot = {'street': street, 'seat': s,
                             'idx': sum(1 for i in h.intents
                                        if i['street'] == street and i['seat'] == s)}
                    h.intents.append(_slot)
                _slot.update({'type': ax.get('type'),
                              'action': a, 'amt': _exec_amt, 'pre_clamp': amt,
                                  'plan': _pl2.get('plan'), 'why': _pl2.get('why'),
                                  'intent_act': _it.get('act'), 'intent_size': _it.get('size'),
                                  'intent_src': _it.get('src'), 'dev': _dev,
                                  # 저항이 있으면 decide_response 가 별도로
                                  # 판단한다. **intent_act 를 덮어쓰지 않고**
                                  # 대응 행동을 따로 남긴다 — 그래야 로그에서
                                  # '원래 계획은 check 였고, 상대가 쳐서 call 로
                                  # 대응했다'가 보존된다. 덮어쓰면 최초 의도가
                                  # 사라지고, 그대로 두면 의도와 실행이 어긋나
                                  # 보인다(실측 32건).
                                  'plan_goal': _pl2.get('plan_goal'),
                                  'plan_mode': _pl2.get('plan_mode'),
                                  'response_act': (a if tc > 0 else None),
                                  'response_src': (_rsrc if tc > 0 else None),
                                  'response_kind': (_resp_ctx.get('kind')
                                                    if tc > 0 else None),
                                  'facing_kind': (_resp_ctx.get('facing_kind')
                                                  if tc > 0 else None),
                                  # 기록 전용: near-all-in / effective-stack 분석.
                                  'contrib_before': (_contrib_before
                                                     if a in ('bet', 'raise') else None),
                                  'actor_cap': (_actor_cap
                                                if a in ('bet', 'raise') else None),
                                  'opp_cap_max': (_opp_cap_max
                                                  if a in ('bet', 'raise') else None),
                                  'effective_cap': (_effective_cap
                                                    if a in ('bet', 'raise') else None),
                                  'increment': (_increment
                                                if a in ('bet', 'raise') else None),
                                  'pot_after': (_pot_after
                                                if a in ('bet', 'raise') else None),
                                  'own_residual_post': (_own_residual_post
                                                        if a in ('bet', 'raise') else None),
                                  'effective_gap': (_effective_gap
                                                    if a in ('bet', 'raise') else None),
                                  'post_spr_own': (_post_spr_own
                                                   if a in ('bet', 'raise') else None),
                                  'post_spr_effective': (_post_spr_effective
                                                         if a in ('bet', 'raise') else None),
                                  # effective-all-in v1 provenance.
                                  'pre_effective_target': (_pre_effective_target
                                                           if a in ('bet', 'raise') else None),
                                  'effective_allin_candidate': (
                                      _ea.get('effective')
                                      if a in ('bet', 'raise') else None),
                                  'effective_allin_actor': (
                                      _ea.get('actor_effective')
                                      if a in ('bet', 'raise') else None),
                                  'effective_allin_commit': (
                                      _ea.get('commit_frac')
                                      if a in ('bet', 'raise') else None),
                                  'effective_allin_post_spr': (
                                      _ea.get('post_spr')
                                      if a in ('bet', 'raise') else None),
                                  'effective_allin_applied': (
                                      _ea_applied if a in ('bet', 'raise') else None),
                                  'allin_execution_mode': (
                                      _allin_execution_mode
                                      if a in ('bet', 'raise') else None),
                                  'why_by_street': (_pl2.get('why_by_street') or {}
                                                    ).get(street),
                                  'tocall': tc, 'pot': pot_live,
                                  'stack': r2.stacks[s] + r2.contrib.get(s, 0),
                                  'min_raise': (_cur0 + _mr0) if _cur0 else max(h.bb, _mr0),
                                  'rel': _pl2.get('rel'), 'eq': _pl2.get('eq'),
                                  'outs': _pl2.get('outs'), 'blocker': _pl2.get('blocker')})
            _st_uncalled = r2.settle_uncalled()
            if _st_uncalled:
                h.uncalled_returns = getattr(h, 'uncalled_returns', [])
                h.uncalled_returns.append(dict(_st_uncalled, street=street))

            # POST-F: no-raise closure / caller composition을 명시적으로 보존한다.
            # 다음 스트리트 전략은 여전히 원본 공개 액션에서 재판단하며,
            # 이 요약은 상황 클래스가 소실되지 않았는지 검증하는 provenance다.
            h.street_outcomes = getattr(h, 'street_outcomes', {})
            h.street_outcomes[street] = _postflop_street_outcome(r2.action_meta)

            _any_bet = any(m.get('raised') for m in r2.action_meta)
            if not _any_bet:
                for k, v in list(h.plans.items()):
                    if v.get('plan') == 'trap':
                        h.plans[k] = PL.mark_no_bite(v)
            # 포스트플랍 관찰 기록.
            # 씨벳/배럴 '기회'는 직전 스트리트의 공격자가 이번 스트리트에서
            # 처음 액션하는 시점이고, 그때까지 아무도 베팅하지 않았어야 한다.
            # (예전엔 로그의 첫 항목인지로 판정했는데, 공격자는 보통 포지션이 있어
            #  마지막에 액션하므로 기회가 거의 잡히지 않았다 — 60핸드에 0.3회.)
            # 관찰자는 '그 핸드에 참여한 사람'이 아니라 '테이블에 앉아 있는 사람' 전원이다.
            # 폴드했어도 상대 플레이는 다 보고 있다. 생존자만 관찰자로 세면
            # 표본이 몇 배로 줄어 리딩이 성립하지 않는다.
            _ord = [_pid(x) for x in h.seats]
            _acted_once = set()
            _bet_seen = False
            _prev_st = {'turn': 'flop', 'river': 'turn'}.get(street)
            _prev_rows = [z for z in (getattr(self, 'full_log', []) or [])
                          if _prev_st and z[0] == _prev_st]
            _prev_meta = [m for m in (getattr(self, 'full_action_meta', []) or [])
                          if _prev_st and m.get('street') == _prev_st]
            _prev_aggr_bet = (
                street_aggr is not None and (
                    any(m.get('seat') == street_aggr and m.get('raised')
                        for m in _prev_meta)
                    if _prev_meta else
                    any(z[1] == street_aggr and z[2] in ('bet', 'raise')
                        for z in _prev_rows)))
            _prev_checked_through = bool(_prev_rows) and not (
                any(m.get('raised') for m in _prev_meta)
                if _prev_meta else
                any(z[2] in ('bet', 'raise') for z in _prev_rows))

            _pot_before_action = float(self._pot_at.get(street, 0) or 0)
            _facing_seq = _postflop_facing_contexts(r2.action_meta)
            for _obs_i, m in enumerate(r2.action_meta):
                x = m.get('seat')
                a_ = m.get('action')
                opp_spot = (x == street_aggr and x not in _acted_once and not _bet_seen)
                is_cbet = (street == 'flop' and opp_spot)
                # barrel = 직전 스트리트에도 공격했던 사람이 다시 치는 것.
                is_barrel = (street in ('turn', 'river') and opp_spot and _prev_aggr_bet)
                # delayed cbet = 플랍이 체크스루된 뒤 프리플랍 공격자가 턴에 다시
                # 첫 베팅 기회를 얻는 것. barrel 표본과 섞지 않는다.
                is_delayed = (street == 'turn' and opp_spot and _prev_checked_through
                              and not _prev_aggr_bet)
                # 관측 의미는 UI 문자열이 아니라 규칙 사건이다.
                # allin call은 call, allin raise는 raise로 학습해야 한다.
                _obs_action = _observed_postflop_action(m)
                _fk = _facing_seq[_obs_i] if _obs_i < len(_facing_seq) else None
                h.book.observe_postflop(
                    _ord, _pid(x), _obs_action, is_cbet, is_barrel,
                    facing_bet=(_fk == 'bet'),
                    facing_raise=(_fk == 'raise'),
                    street=street,
                    is_delayed_cbet_spot=is_delayed)
                # sizing tell은 target/street-start-pot이 아니라
                # **이번 액션에 새로 낸 칩 / 액션 직전 팟**을 본다.
                if m.get('raised'):
                    _inc = float(m.get('increment', 0) or 0)
                    h.book.observe_size(
                        _ord, _pid(x),
                        _inc/max(1.0, _pot_before_action), street)
                _acted_once.add(x)
                if m.get('raised'):
                    _bet_seen = True
                _pot_before_action += float(m.get('increment', 0) or 0)

            self.full_log.extend(('%s' % street, x, a, amt) for (x, a, amt) in r2.log)
            self.full_action_meta = getattr(self, 'full_action_meta', [])
            self.full_action_meta.extend(
                dict(m, street=street) for m in r2.action_meta)
            for k, v in r2.contrib.items():
                contrib[k] = contrib.get(k, 0)+v
            for k in r2.stacks: h.stacks[k] = r2.stacks[k]
            folded |= set(r2.folded)
            # 이전 스트리트에서 올인한 사람도 쇼다운 자격이 있다
            allin_prev = [x for x in h.seats
                          if x not in folded and h.stacks.get(x, 0) <= 0]
            live = sorted(set(r2.live()) | set(allin_prev))
            prev = board
            if len(live) <= 1:
                # 폴드로 끝났다. **여기서 보드를 더 깔면 레빗헌트다.**
                # 예전에는 h.board(5장 전부)를 넘겨서, 턴에서 끝난 판에도
                # 리버 카드가 결과에 찍혔다.
                _r = self._finish(contrib, dead, folded, live, board, 'showdown')
                # 화면에는 그 시점 보드까지만(레빗헌트 금지).
                # 남은 카드는 리뷰용으로 별도 키에 담는다 —
                # '리버가 뭐였으면 이겼나'는 사후 분석에 필요하다.
                if len(h.board) > len(board):
                    _r['runout'] = list(h.board)
                self.result = _r
                return

        # 전원이 올인이든 리버까지 왔든, 여기까지 오면 보드가 다 깔린다.
        self.result = self._finish(contrib, dead, folded, live, h.board, 'showdown')
        return

    def _was_3bettor(self, seat):
        """이 좌석이 프리플랍에서 리레이즈(3벳 이상)를 쳤나."""
        n = 0
        for row in (getattr(self, 'full_log', []) or []):
            if row[0] != 'preflop':
                continue
            if row[2] in ('raise', 'allin'):
                n += 1
                if n >= 2 and row[1] == seat:
                    return True
        return False

    def _reads_for(self, me, seats, ax):
        """여러 좌석에 대한 추정치 목록. 관찰이 없으면 중립값이 나온다."""
        h = self.h
        out = []
        for x in (seats or []):
            if x == me:
                continue
            out.append(RD.perceived_profile(
                h.book, self._pid(me), self._pid(x), ax,
                random.Random(self._dseed(me, 'preflop', 'behind', x))))
        return out or None

    def _tilt_update(self, contrib, folded, live):
        """핸드 결과를 틸트에 반영. try/except 로 감싸지 않는다 —
        예전에는 감싸져 있어서 h.dyn 이 없어도 조용히 실패했다."""
        h = self.h
        t = getattr(h, 'dyn', None)
        if t is None or not hasattr(t, 'on_pot'):
            return
        bb = max(1, h.bb)
        # 자발적 참가(VPIP)를 따로 센다. contrib 만 보면 블라인드를 낸 것도
        # '참가'가 되어, 폴드만 하는 좌석의 연속패가 무한히 늘어난다
        # (실제로 66연패까지 갔다). 폴드는 지는 것이 아니다.
        vpip = set()
        for row in (getattr(self, 'full_log', []) or []):
            if row[0] == 'preflop' and row[2] in ('call', 'raise', 'allin'):
                vpip.add(row[1])
        # 틸트 상태의 키는 좌석이 아니라 사람이다. 좌석 번호는 테이블마다
        # 겹쳐서, 그대로 쓰면 다른 테이블의 다른 사람과 상태를 공유하게 된다.
        #
        # decay_all 은 상태에 있는 **모든** pid 를 훑는다. 이 핸드가 아는
        # 프로필은 테이블 8명분뿐이라 나머지는 기본 temper 로 감쇠했다.
        # 대회 전체 맵(context.pid_prof)을 바닥에 깔고, 그게 없는 단일 테이블
        # 드라이버에서는 이 테이블 것만 남아 예전과 똑같이 돈다.
        # 문맥의 맵은 읽기 전용이라 복사해서 쓴다.
        _pp = dict(getattr(h, 'pid_prof', None) or {})
        for k in h.seats:
            prof = h.prof.get(str(k)) or {}
            pid = self._pid(k)
            _pp.setdefault(str(pid), prof)
            before = self._before.get(k, h.stacks.get(k, 0))
            d = (h.stacks.get(k, 0) - before) / bb
            st0 = before / bb
            if abs(d) >= 0.5:
                t.on_pot(pid, prof, d, st0)
            # 넣고 접은 팟은 별도로 센다. 같은 크기라도 자책이 붙는다.
            if k in folded and contrib.get(k, 0) > 0:
                t.on_fold_after_investing(pid, prof, contrib[k]/bb, st0)
            t.on_result(pid, prof, won=(d > 0), played=(k in vpip),
                        contested=(k in vpip), showdown=(k in live))
        # decay_all 은 상태에 있는 모든 키를 훑는다. 프로필도 같은 키로 준다.
        t.decay_all(_pp)

    def _finish(self, contrib, dead, folded, live, board, how):
        h = self.h
        # 장부 저장은 소유자(드라이버)의 책임. 여기서 전역 파일에 쓰지 않는다.
        self._before = getattr(self, '_before', dict(h.stacks))
        pot_total = sum(contrib.values())+dead
        if not any(v > 0 for v in contrib.values()) and dead == 0:
            return {'how': 'void', 'winners': [], 'pot': 0, 'showdown': False,
                    'board': board, 'stacks': dict(h.stacks), 'hash': h.hash,
                    'note': '유효 참가자 부족으로 무효'}
        if len(live) <= 1:
            w = live[0] if live else max(contrib, key=contrib.get)
            h.stacks[w] += pot_total
            self._tilt_update(contrib, folded, live)
            return {'how': 'fold', 'winners': [w], 'pot': pot_total, 'showdown': False,
                    'board': board, 'stacks': dict(h.stacks), 'hash': h.hash,
                    'hero_hole': list(h.hole.get(h.hero, [])) if h.hero is not None else [],
                    'full_log': getattr(self, 'full_log', []),
                    'pos': {k: v for k, v in h.pos.items()}}
        c2 = dict(contrib)          # 기여분은 그대로 둔다 (안테는 award_pots 에서 처리)
        # 쇼다운 관찰: 깐 패의 강도와 공격 여부
        try:
            import preflop as _pf
            # postflop 공격성은 raw action 문자열이 아니라 규칙 사건으로 본다.
            # all-in raise는 공격이고 all-in call은 공격이 아니다.
            aggr_seats = {
                m.get('seat') for m in (getattr(self, 'full_action_meta', []) or [])
                if m.get('raised')
            }
            # preflop meta는 아직 별도 보존하지 않으므로 기존 공개 raise만 합친다.
            aggr_seats |= {
                x for (stt, x, a_, _) in (getattr(self, 'full_log', []) or [])
                if stt == 'preflop' and a_ == 'raise'
            }
            _all = [self._pid(x) for x in h.seats]
            for sd in live:
                RD_pct = _pf.PCT[_pf.cls(h.hole[sd])]
                h.book.observe_showdown(_all, self._pid(sd), RD_pct, sd in aggr_seats)
                # 깐 패는 틸트 객체에도 남긴다. runner.adjust_range_by_history 가
                # 이걸 읽어 '이 사람이 예상보다 넓게 깠다'를 판단한다. 키는 pid 다.
                if hasattr(h, 'dyn') and hasattr(h.dyn, 'note_showdown'):
                    h.dyn.note_showdown(self._pid(sd), list(h.hole[sd]))
        except Exception as _e:
            # 관찰 실패를 조용히 삼키면 장부가 안 쌓이고 리딩이 통째로 죽는다.
            h.book_errors = getattr(h, 'book_errors', [])
            h.book_errors.append('showdown: %r' % (_e,))
        # 정산 전 0스택은 올인 쇼다운이므로 공개 의무가 있다.
        allin_show = {s for s in live if h.stacks.get(s, 0) <= 0}
        won, detail = award_pots(c2, h.hole, h.board, folded, h.stacks, dead,
                                 unit=getattr(h, 'sb', 0) or 1)
        if not detail:
            return {'how': 'void', 'winners': [], 'pot': 0, 'showdown': False,
                    'board': board, 'stacks': dict(h.stacks), 'hash': h.hash}
        # dead 는 award_pots 가 메인팟에 얹어 이미 분배했다.
        # 여기서 또 주면 안테가 두 번 지급되어 칩이 늘어난다.
        self._tilt_update(contrib, folded, live)
        all_w = sorted({w for d in detail for w in d['winners']})

        # UI에 공개할 패와 공개 순서를 결정한다.
        #
        # 일반 쇼다운:
        #   마지막 betting street의 공격자(콜 받은 사람)는 반드시 먼저 SHOW.
        #   뒤 플레이어는 현재 공개된 최고 패보다 지고, 어떤 팟의 승자도 아니면 MUCK.
        #
        # 마지막 street에 bet/raise가 없으면 버튼 왼쪽부터 공개한다.
        #
        # 올인 쇼다운:
        #   생존자 전원 SHOW. MUCK 없음.
        full_log = list(getattr(self, 'full_log', []) or [])
        live_set = set(live)

        def _left_of_button_order():
            ring = list(h.seats or [])
            if not ring:
                return list(live)

            btn = getattr(h, 'button', None)
            if btn in ring:
                i = ring.index(btn)
                ring = ring[i + 1:] + ring[:i + 1]

            return [s for s in ring if s in live_set]

        def _rotate_to(seats_, first_):
            seats_ = list(seats_)
            if first_ not in seats_:
                return seats_

            i = seats_.index(first_)
            return seats_[i:] + seats_[:i]

        base_order = _left_of_button_order()

        last_street = (
            full_log[-1][0]
            if full_log
            else None
        )

        _last_meta = [
            m for m in (getattr(self, 'full_action_meta', []) or [])
            if m.get('street') == last_street
        ]
        if _last_meta:
            last_aggr = next(
                (m.get('seat') for m in reversed(_last_meta)
                 if m.get('seat') in live_set and m.get('raised')),
                None)
        else:
            # 구형/프리플랍-only 폴백. postflop은 action_meta가 정본이다.
            last_aggr = next(
                (
                    x
                    for (stt, x, a_, _) in reversed(full_log)
                    if stt == last_street
                    and x in live_set
                    and a_ in ('bet', 'raise', 'allin')
                ),
                None
            )

        if last_aggr is not None:
            show_order = _rotate_to(
                base_order,
                last_aggr
            )
        else:
            show_order = base_order

        # 혹시 ring 정보가 빠졌어도 생존자를 누락하지 않는다.
        for s in live:
            if s not in show_order:
                show_order.append(s)

        if allin_show:
            shown_seats = set(live)
            mucked = []

        else:
            ranks = {}

            for s in live:
                ranks[s] = max(
                    (
                        best5(list(cs))
                        for cs in itertools.combinations(
                            h.hole[s] + h.board,
                            5
                        )
                    )
                )

            shown_seats = set()
            mucked = []
            best_seen = None

            for s in show_order:
                rnk = ranks[s]

                # 첫 공개자는 무조건 SHOW.
                # 이후에는 팟 승자이거나 현재 공개 최고패 이상이면 SHOW.
                must_show = (
                    not shown_seats
                    or s in all_w
                    or best_seen is None
                    or rnk >= best_seen
                )

                if must_show:
                    shown_seats.add(s)

                    if best_seen is None or rnk > best_seen:
                        best_seen = rnk
                else:
                    mucked.append(s)

        best_five = {}
        for s in all_w:
            combos = itertools.combinations(h.hole[s] + h.board, 5)
            best_five[s] = list(max(combos, key=lambda cs: best5(list(cs))))

        return {'how': 'showdown', 'winners': all_w,
                'main_winners': detail[0]['winners'], 'pot': pot_total,
                'showdown': True, 'board': h.board, 'pots': detail,
                'hole': {s: h.hole[s] for s in live},
                'shown_hole': {s: h.hole[s] for s in shown_seats},
                'show_order': list(show_order),
                'mucked': list(mucked),
                'allin_show': bool(allin_show),
                'hero_hole': list(h.hole.get(h.hero, [])) if h.hero is not None else [],
                'best_five': best_five,
                'stacks': dict(h.stacks),
                'hash': h.hash, 'full_log': getattr(self, 'full_log', []),
                'pos': {k: v for k, v in h.pos.items()}}


# showdown() 은 제거했다. award_pots 가 같은 랭킹을 내부에서 계산하고
# 사이드팟까지 처리한다. 호출부가 없었다.