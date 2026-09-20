"""머니점프/ICM 공개 상태를 연속 전략 신호로 바꾸는 순수 계산기.

이 모듈은 액션을 결정하지 않는다. 가능한 한 새 임계값을 만들지 않고
기존 0~10 개념값과 무차원 토너 상태만 사용한다.
"""


def clamp01(x):
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


def sat(x):
    """0..inf -> 0..1, 별도 문턱 없는 포화."""
    try:
        x = max(0.0, float(x))
    except (TypeError, ValueError):
        return 0.0
    return x / (1.0 + x)


def inv1p(x):
    """0..inf -> 1..0, 별도 문턱 없는 거리 감쇠."""
    try:
        x = max(0.0, float(x))
    except (TypeError, ValueError):
        return 0.0
    return 1.0 / (1.0 + x)


def mean01(*xs):
    vals = [clamp01(x) for x in xs if x is not None]
    return sum(vals) / len(vals) if vals else 0.0


def union01(*xs):
    """0..1 기여를 1-prod(1-x)로 합친다."""
    p = 1.0
    used = False
    for x in xs:
        if x is None:
            continue
        used = True
        p *= 1.0 - clamp01(x)
    return 1.0 - p if used else 0.0


def skill01(v):
    """프로필 개념/기질 0..10 -> 0..1."""
    try:
        return clamp01(float(v) / 10.0)
    except (TypeError, ValueError):
        return 0.5


def payout_importance(state):
    """대회 규모에 독립적인 상금점프 크기 × 거리."""
    size = union01(
        state.get('jump_frac_next', 0.0),
        sat(state.get('jump_vs_mincash', 0.0)),
    )
    # 두 거리 중 하나만 가까워도 높은 값이 되는 평균 대신, 거리 자체를 합쳐
    # 하나의 연속 감쇠로 본다. 별도 버블 문턱은 없다.
    distance = (max(0.0, float(state.get('distance_frac_itm', 0.0) or 0.0))
                + max(0.0, float(state.get('distance_frac_remaining', 0.0) or 0.0)))
    closeness = inv1p(distance)
    return clamp01(size * closeness)


def ladder_buffer(state):
    """S/(S+J): 다음 점프까지 필요한 탈락 대비 내 밑 스택 수."""
    try:
        s = max(0.0, float(state.get('n_shorter', 0.0)))
        j = max(0.0, float(state.get('players_to_jump', 0.0)))
    except (TypeError, ValueError):
        return 0.0
    if j <= 0:
        return 0.0
    return s / (s + j)


def shorter_severity(state):
    """밑 스택이 실제로 얼마나 더 짧은지. 1에 가까울수록 크게 짧다."""
    r = state.get('median_shorter_ratio')
    if r is None:
        return 0.0
    return clamp01(1.0 - float(r))


def waiting_feasibility(state):
    """다음 강제비용까지 버틸 여지. 1=여유, 0=못 버팀."""
    try:
        now = max(0.0, float(state.get('stack_behind_bb', 0.0)))
        after = max(0.0, float(state.get('stack_after_next_bb_if_fold_all', 0.0)))
    except (TypeError, ValueError):
        return 0.0
    return clamp01(after / now) if now > 0 else 0.0


def bf_signal(state):
    """BF 1 초과분을 별도 상한 상수 없이 포화."""
    try:
        return sat(max(0.0, float(state.get('bf', 1.0)) - 1.0))
    except (TypeError, ValueError):
        return 0.0


def objective_self_preservation(state):
    """개인차 전의 탈락 회피 가치."""
    payout = payout_importance(state)
    ladder = ladder_buffer(state) * shorter_severity(state) * waiting_feasibility(state)
    survival = union01(bf_signal(state), ladder)
    return clamp01(payout * survival)


def perceived_self_preservation(state, actor):
    """객관적 회피가치를 이 사람이 얼마나 강하게 받는가."""
    awareness = mean01(
        skill01(actor.get('money_jump')),
        skill01(actor.get('icm')),
        skill01(actor.get('discipline')),
        1.0 - skill01(actor.get('gamble')),
    )
    return clamp01(objective_self_preservation(state) * awareness)


def objective_urgency(state):
    """기다릴 비용. self-preservation과 동시에 높을 수 있다."""
    cost_share = clamp01(state.get('forced_cost_share_of_stack', 0.0))
    no_buffer = 1.0 - ladder_buffer(state)
    shortness = inv1p(state.get('stack_behind_bb', 0.0))
    return union01(cost_share, no_buffer * shortness)


def perceived_urgency(state, actor):
    awareness = mean01(
        skill01(actor.get('stack_decay')),
        skill01(actor.get('money_jump')),
    )
    return clamp01(objective_urgency(state) * awareness)


def cover_strength(hero_stack_bb, target_stack_bb):
    """못 커버하면 0, 커버 격차가 커질수록 연속 증가."""
    try:
        h = max(0.0, float(hero_stack_bb))
        t = max(0.0, float(target_stack_bb))
    except (TypeError, ValueError):
        return 0.0
    if h <= t or h <= 0:
        return 0.0
    return clamp01((h - t) / h)


def topology_safety(state):
    """뒤에 나를 커버하는 사람이 늘수록 압박 실행 여지가 줄어든다."""
    try:
        n = max(0.0, float(state.get('covered_by_yet_to_act', 0.0)))
    except (TypeError, ValueError):
        return 1.0
    return inv1p(n)


def exploit_realization(actor):
    """구조적 압박을 읽고 전략 수정으로 옮길 능력."""
    return mean01(
        skill01(actor.get('money_jump')),
        skill01(actor.get('fold_equity')),
        skill01(actor.get('range_read')),
        skill01(actor.get('attention')),
        skill01(actor.get('adaptability')),
        skill01(actor.get('aggression')),
    )


def structural_pressure(hero_state, target_state):
    """상대가 공개상태상 압박받을 자리인지에 대한 prior."""
    vulnerable = objective_self_preservation(target_state)
    cover = cover_strength(
        hero_state.get('stack_start_bb', 0.0),
        target_state.get('stack_start_bb', 0.0),
    )
    # vulnerability와 cover는 둘 다 필요한 게이트다. 둘을 곱하면 중간값끼리도
    # 제곱처럼 작아져 자연상태에서 신호가 거의 0으로 붕괴했다.
    # 약한 쪽이 병목이라는 의미의 min은 새 계수 없이 두 조건을 동시에 요구한다.
    bottleneck = min(vulnerable, cover)
    return clamp01(bottleneck * topology_safety(hero_state))


def read_adjustment(read, channel='generic'):
    """기존 exploit read가 구조 prior를 위/아래로 보정하는 배수.

    채널별로 이미 존재하는 상대 통계를 쓴다. 새 상대 성향을 만들지 않는다.
    """
    if not read:
        return 1.0
    try:
        w = clamp01(read.get('w', 0.0))
        if channel == 'preflop_3bet':
            gap = float(read.get('f2tb_gap', read.get('fold_gap', 0.0)) or 0.0)
        else:
            gap = float(read.get('fold_gap', 0.0) or 0.0)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, 1.0 + w * gap)


def pressure_opportunity(hero_state, target_state, actor, read=None,
                         read_channel='generic'):
    prior = structural_pressure(hero_state, target_state)
    theory = clamp01(prior * exploit_realization(actor))
    adjust = read_adjustment(read, read_channel)
    final = clamp01(theory * adjust)
    return {
        'structural_pressure': round(prior, 6),
        'theory_pressure': round(theory, 6),
        'read_adjustment': round(adjust, 6),
        'pressure_opportunity': round(final, 6),
    }


def commitment_budget(state, actor):
    """자발적으로 큰 팟을 만들 수 있는 여지.

    압박 빈도와 큰 사이즈는 다른 질문이므로 pressure_opportunity를 여기
    직접 더하지 않는다.
    """
    preserve = perceived_self_preservation(state, actor)
    urgent = perceived_urgency(state, actor)
    return union01(1.0 - preserve, urgent)


def low_commit_pressure(pressure, state, actor):
    """압박 기회는 있으나 큰 팟은 만들고 싶지 않은 영역."""
    return clamp01(float(pressure or 0.0) * (1.0 - commitment_budget(state, actor)))


def unopened_modifiers(state):
    """미오픈 프리플랍의 연속 머니점프 보정.

    range_factor는 실제 오픈 레인지에 연결된다.
    size_factor/limp_pull은 아직 shadow 신호다.

    역할 분리:
    - range pressure: 뒤 상대 전체가 얼마나 압박받는지(평균)
    - range brake: 이번 오픈에서 나를 탈락시킬 수 있는 뒤 상대의 비율
    - pot restraint: 칩을 잃는 비용 자체. sizing/form 단계용 shadow

    새 BB/인원 문턱이나 포지션별 상수는 없다.
    """
    ms = state.get('money_signals') or {}
    preserve = clamp01(ms.get('self_preservation', 0.0))
    urgency = clamp01(ms.get('urgency', 0.0))

    _pressures = [
        clamp01((t.get('pressure') or {}).get('pressure_opportunity', 0.0))
        for t in (state.get('target_signals') or [])
    ]
    pressure = (sum(_pressures) / len(_pressures)) if _pressures else 0.0
    max_pressure = max(_pressures, default=0.0)

    try:
        n_behind = max(0.0, float(state.get('players_yet_to_act', 0.0) or 0.0))
        n_covering = max(
            0.0, float(state.get('covered_by_yet_to_act', 0.0) or 0.0))
    except (TypeError, ValueError):
        n_behind, n_covering = 0.0, 0.0
    danger_frac = clamp01(n_covering / n_behind) if n_behind > 0 else 0.0

    drive = union01(pressure, urgency)
    range_brake = preserve * (1.0 - urgency) * danger_frac
    range_factor = (1.0 + drive) / (1.0 + range_brake)

    # 사이즈/림프는 아직 shadow. 여기서는 '탈락 가능 여부'만이 아니라
    # 칩을 잃는 비용도 여전히 중요하므로 일반 preservation을 유지한다.
    pot_brake = preserve * (1.0 - urgency)
    restraint = union01(pot_brake, pressure) * (1.0 - urgency)
    size_factor = inv1p(restraint)
    limp_pull = clamp01(restraint)

    return {
        'pressure': round(pressure, 6),
        'max_pressure': round(max_pressure, 6),
        'danger_fraction': round(danger_frac, 6),
        'drive': round(drive, 6),
        'brake': round(range_brake, 6),
        'pot_brake_shadow': round(pot_brake, 6),
        'range_factor': round(range_factor, 6),
        'size_factor_shadow': round(size_factor, 6),
        'limp_pull_shadow': round(limp_pull, 6),
    }


def actor_from_profile(profile, sk_fn, temper_fn):
    return {
        'money_jump': sk_fn(profile, 'money_jump'),
        'icm': sk_fn(profile, 'icm'),
        'stack_decay': sk_fn(profile, 'stack_decay'),
        'fold_equity': sk_fn(profile, 'fold_equity'),
        'range_read': sk_fn(profile, 'range_read'),
        'attention': temper_fn(profile, 'attention', 5.0),
        'adaptability': temper_fn(profile, 'adaptability', 5.0),
        'discipline': temper_fn(profile, 'discipline', 5.0),
        'gamble': temper_fn(profile, 'gamble', 5.0),
        'aggression': temper_fn(profile, 'aggression', 5.0),
    }


def signals(state, actor):
    return {
        'payout_importance': round(payout_importance(state), 6),
        'ladder_buffer': round(ladder_buffer(state), 6),
        'waiting_feasibility': round(waiting_feasibility(state), 6),
        'self_preservation_objective': round(objective_self_preservation(state), 6),
        'self_preservation': round(perceived_self_preservation(state, actor), 6),
        'urgency_objective': round(objective_urgency(state), 6),
        'urgency': round(perceived_urgency(state, actor), 6),
        'commitment_budget': round(commitment_budget(state, actor), 6),
    }
