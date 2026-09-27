"""Canonical public postflop action-event interpretation.

Round.action_meta is the rule-engine source of truth.  This module turns that
raw metadata into one semantic event stream consumed by range inference,
response classification, sizing reads and audits.  Do not reconstruct these
facts independently in downstream code.
"""


def normalized_action(meta):
    """Return rule-semantic action: bet/raise/call/check/fold."""
    m = meta or {}
    if m.get('raised'):
        return 'raise' if float(m.get('pre_current', 0) or 0) > 0 else 'bet'
    if m.get('allin_call') or m.get('action') == 'call':
        return 'call'
    return m.get('action')


def _response_kind(facing_kind, prior_event):
    prior_action = (prior_event or {}).get('action_kind')
    if facing_kind == 'raise' and prior_action in ('bet', 'raise'):
        return 'aggressor_backaction'
    if facing_kind == 'raise' and prior_action == 'call':
        return 'caller_backaction'
    if facing_kind == 'raise':
        return 'cold_facing_raise'
    if facing_kind == 'bet' and prior_action == 'check':
        return 'check_then_face_bet'
    if facing_kind == 'bet':
        return 'face_bet'
    return 'free_action'


def postflop_events(action_meta, street=None, pot_start=0.0):
    """Build canonical events from one street's Round.action_meta.

    The stream is depth-agnostic: bet -> raise -> re-raise -> ... is represented
    by monotonically increasing raise_depth_* values until stacks/rules stop it.
    Full and incomplete all-ins remain distinct.
    """
    rows = list(action_meta or [])
    out = []
    actor_last = {}
    latest_wager = None
    added = 0.0
    any_raise_depth = 0

    for idx, m0 in enumerate(rows):
        m = dict(m0 or {})
        seat = m.get('seat')
        inc = float(m.get('increment', 0) or 0)
        pot_before = float(pot_start or 0) + added
        action_kind = normalized_action(m)
        raised = bool(m.get('raised'))

        facing_kind = (
            latest_wager.get('action_kind')
            if latest_wager is not None else None)
        if facing_kind not in ('bet', 'raise'):
            facing_kind = None

        prior_event = actor_last.get(seat)
        full = bool(m.get('full_raise'))
        incomplete = bool(m.get('incomplete_raise'))
        full_after = int(m.get('full_raise_count', 0) or 0)
        full_before = max(0, full_after - (1 if full else 0))
        any_before = any_raise_depth
        any_after = any_before + (1 if raised else 0)

        actor_allin_after = bool(m.get('actor_allin_after'))
        allin_call = bool(m.get('allin_call'))
        allin_raise = bool(
            m.get('allin_raise')
            or (raised and actor_allin_after))

        event = {
            'idx': idx,
            'street': street or m.get('street'),
            'seat': seat,
            'input_action': m.get('input_action'),
            'action_kind': action_kind,
            'raised': raised,
            'full_raise': full,
            'incomplete_raise': incomplete,
            'allin': bool(actor_allin_after or allin_call or allin_raise),
            'allin_call': allin_call,
            'allin_raise': allin_raise,
            'actor_allin_after': actor_allin_after,
            'can_raise_before': m.get('can_raise_before'),
            'to_call_before': m.get('to_call_before'),
            'pre_stack': m.get('pre_stack'),
            'post_stack': m.get('post_stack'),
            'pre_contrib': float(m.get('pre_contrib', 0) or 0),
            'post_contrib': float(m.get('post_contrib', 0) or 0),
            'target': float(m.get('post_contrib', m.get('amount', 0)) or 0),
            'increment': inc,
            'pre_current': float(m.get('pre_current', 0) or 0),
            'post_current': float(m.get('post_current', 0) or 0),
            'pre_min_raise': float(m.get('pre_min_raise', 0) or 0),
            'pot_before': pot_before,
            'size_frac': inc / max(1.0, pot_before) if inc > 0 else 0.0,
            'facing_kind': facing_kind,
            # 두 값은 다르다.
            # facing_size_frac: 상대가 낸 공격 크기 / 그 공격 직전 팟.
            # facing_price_frac: 내가 지금 더 내야 하는 가격 / 내 액션 직전 팟.
            # 레인지의 continue 조건은 후자를 써야 한다.
            'facing_size_frac': (
                latest_wager.get('size_frac')
                if latest_wager is not None else None),
            'facing_price_frac': (
                float(m.get('to_call_before', 0) or 0) / max(1.0, pot_before)
                if facing_kind in ('bet', 'raise') else None),
            'facing_increment': (
                latest_wager.get('increment')
                if latest_wager is not None else None),
            'facing_target': (
                latest_wager.get('target')
                if latest_wager is not None else None),
            'facing_full_raise': bool(
                latest_wager and latest_wager.get('full_raise')),
            'facing_incomplete_raise': bool(
                latest_wager and latest_wager.get('incomplete_raise')),
            'facing_allin': bool(
                latest_wager and latest_wager.get('allin')),
            'raise_depth_full_before': full_before,
            'raise_depth_full_after': full_after,
            'raise_depth_any_before': any_before,
            'raise_depth_any_after': any_after,
            'prior_action': (
                prior_event.get('action_kind') if prior_event else None),
            'prior_facing_kind': (
                prior_event.get('facing_kind') if prior_event else None),
        }
        event['response_kind'] = _response_kind(
            facing_kind, prior_event)

        out.append(event)
        actor_last[seat] = event
        if raised:
            latest_wager = event
            any_raise_depth = any_after
        added += inc

    return out


def pending_response_context(action_meta, seat):
    """Classify the *next* decision for seat from current-street public history."""
    events = postflop_events(action_meta)
    prior = next((e for e in reversed(events) if e.get('seat') == seat), None)
    latest = next(
        (e for e in reversed(events)
         if e.get('action_kind') in ('bet', 'raise')),
        None)

    facing_kind = (
        latest.get('action_kind')
        if latest is not None and latest.get('seat') != seat else None)
    if facing_kind not in ('bet', 'raise'):
        facing_kind = None

    return {
        'kind': _response_kind(facing_kind, prior),
        'facing_kind': facing_kind,
        'prior_action': prior.get('action_kind') if prior else None,
        'prior_aggressive': bool(
            prior and prior.get('action_kind') in ('bet', 'raise')),
        'prior_facing_kind': prior.get('facing_kind') if prior else None,
        'raise_depth_full': (
            max((e.get('raise_depth_full_after', 0) for e in events), default=0)),
        'raise_depth_any': (
            max((e.get('raise_depth_any_after', 0) for e in events), default=0)),
        'facing_full_raise': bool(latest and latest.get('full_raise')),
        'facing_incomplete_raise': bool(
            latest and latest.get('incomplete_raise')),
        'facing_allin': bool(latest and latest.get('allin')),
        'facing_allin_raise': bool(latest and latest.get('allin_raise')),
        'facing_size_frac': (
            latest.get('size_frac') if latest is not None else None),
        # pending decision의 정확한 call-price fraction은 Round의 현재
        # contrib/pot이 필요하므로 여기서 추측하지 않는다.
        'facing_price_frac': None,
        'facing_increment': (
            latest.get('increment') if latest is not None else None),
        'facing_target': (
            latest.get('target') if latest is not None else None),
    }
