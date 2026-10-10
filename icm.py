from functools import lru_cache

_ICM_PRUNE = 1e-9


def _icm_equity_reference(stacks, payouts):
    """Historical recursive Malmuth-Harville implementation.

    Kept as a compatibility fallback and as the oracle for verification.
    """
    n = len(stacks)
    k = min(len(payouts), n)
    total = float(sum(stacks))
    if total <= 0:
        return [0.0] * n
    res = [0.0] * n

    def rec(remaining_idx, remaining_sum, place, prob, acc):
        if place >= k or prob < _ICM_PRUNE:
            return
        for i in remaining_idx:
            if remaining_sum > 0:
                p = prob * (stacks[i] / remaining_sum)
            else:
                p = prob / len(remaining_idx)
            res[i] += p * payouts[place]
            if place + 1 < k:
                nxt = [j for j in remaining_idx if j != i]
                rec(nxt, remaining_sum - stacks[i], place + 1, p, acc)

    rec(list(range(n)), total, 0, 1.0, None)
    return res


def _subset_path_prune_safe(stacks, k):
    """True when the historical 1e-9 path prune cannot remove a positive path.

    Subset DP combines different finishing orders that reach the same subset.
    That is equivalent to the historical recursion only when no positive path
    would have been individually pruned.  Zero-probability paths are harmless.
    """
    n = len(stacks)
    total = float(sum(stacks))
    if total <= 0 or k <= 1:
        return True

    size = 1 << n
    sums = [0.0] * size
    for mask in range(1, size):
        bit = mask & -mask
        i = bit.bit_length() - 1
        sums[mask] = sums[mask ^ bit] + float(stacks[i])

    mins = {0: 1.0}
    for place in range(min(k - 1, n - 1)):
        nxt = {}
        for mask, prob in mins.items():
            remaining_sum = total - sums[mask]
            remaining_count = n - mask.bit_count()
            for i, w in enumerate(stacks):
                if mask & (1 << i):
                    continue
                if remaining_sum > 0:
                    p = prob * (float(w) / remaining_sum)
                else:
                    p = prob / remaining_count
                if p == 0.0:
                    continue
                if p < _ICM_PRUNE:
                    return False
                nm = mask | (1 << i)
                old = nxt.get(nm)
                if old is None or p < old:
                    nxt[nm] = p
        mins = nxt
        if not mins:
            break
    return True


def _icm_equity_subset(stacks, payouts):
    """Exact subset-DP form of Malmuth-Harville: O(n * 2^n)."""
    n = len(stacks)
    k = min(len(payouts), n)
    total = float(sum(stacks))
    if total <= 0:
        return [0.0] * n
    res = [0.0] * n

    size = 1 << n
    sums = [0.0] * size
    for mask in range(1, size):
        bit = mask & -mask
        i = bit.bit_length() - 1
        sums[mask] = sums[mask ^ bit] + float(stacks[i])

    probs = {0: 1.0}
    for place in range(k):
        nxt = {}
        for mask, prob in probs.items():
            remaining_sum = total - sums[mask]
            remaining_count = n - mask.bit_count()
            for i, w in enumerate(stacks):
                if mask & (1 << i):
                    continue
                if remaining_sum > 0:
                    p = prob * (float(w) / remaining_sum)
                else:
                    p = prob / remaining_count
                res[i] += p * payouts[place]
                if place + 1 < k and p:
                    nm = mask | (1 << i)
                    nxt[nm] = nxt.get(nm, 0.0) + p
        probs = nxt
    return res


def icm_equity(stacks, payouts):
    """Malmuth-Harville expected prize.

    Final-table exact ICM (2..9 players) uses subset DP whenever it is provably
    equivalent to the historical path-pruned recursion.  The old code enabled
    this only at exactly 9 players, so 9 -> 8 players caused a severe latency
    cliff: every bot decision fell back to factorial recursion.

    If any positive historical path could be pruned, keep the historical
    recursion unchanged.  Strategy semantics therefore do not change.
    """
    n = len(stacks)
    k = min(len(payouts), n)
    if 2 <= n <= EXACT_MAX and _subset_path_prune_safe(stacks, k):
        return _icm_equity_subset(stacks, payouts)
    return _icm_equity_reference(stacks, payouts)

def icm_pressure(stacks, payouts, seat_idx):
    """0~1. 높을수록 그 스택은 리스크 회피(생존 가치)가 커야 한다.
       칩 1개당 상금 가치의 한계 하락폭으로 측정."""
    base = icm_equity(stacks, payouts)[seat_idx]
    s = list(stacks); d = max(1.0, sum(stacks)*0.05)
    up = list(s); up[seat_idx] += d
    dn = list(s); dn[seat_idx] = max(0.0, dn[seat_idx] - d)
    gain = icm_equity(up, payouts)[seat_idx] - base
    loss = base - icm_equity(dn, payouts)[seat_idx]
    if loss <= 0: return 0.0
    ratio = gain / loss                  # <1 이면 잃는 쪽이 더 아프다
    return max(0.0, min(1.0, 1.0 - ratio))

def bubble_factor(stacks, payouts, seat_idx, risk=None):
    """리스크 프리미엄. 1.0=칩EV. risk 미지정 시 min(내 스택, 최대 상대 스택).
       BF = (잃을 때 ICM 손실) / (딸 때 ICM 이득)."""
    n = len(stacks)
    own = stacks[seat_idx]
    others = [stacks[i] for i in range(n) if i != seat_idx] or [0]
    r = risk if risk is not None else min(own, max(others))
    if r <= 0: return 1.0
    base = icm_equity(stacks, payouts)[seat_idx]
    up = list(stacks); up[seat_idx] = own + r
    dn = list(stacks); dn[seat_idx] = max(0.0, own - r)
    gain = icm_equity(up, payouts)[seat_idx] - base
    loss = base - icm_equity(dn, payouts)[seat_idx]
    if gain <= 1e-9 and loss <= 1e-9: return 1.0     # 상금 평탄 = 칩EV
    if gain <= 1e-9: return 4.0
    return max(1.0, min(4.0, loss / gain))

def required_equity(pot, tocall, bf):
    """BF를 반영한 콜 필요 승률."""
    return (tocall * bf) / (pot + tocall * (1 + bf) - tocall) if pot > 0 else 0.5


def players_behind_required_equity_premium(base_need, players_behind):
    """뒤에 아직 행동할 플레이어가 있을 때 필요 승률에 더하는 위험 몫.

    남은 지분(1 - base_need)에 인원당 6%p, 최대 18%p를 곱한다. 포스트플랍
    콜 문턱(plan.calldown_need)과 프리플랍 다인원 재레이즈 판단
    (preflop.multiway_reraise_decision)이 같은 질문에 같은 식을 각자 들고
    있던 것을 한 곳으로 모았다(semantic audit re-audit, 행동 불변).
    """
    return (1.0 - base_need) * min(0.18, 0.06*players_behind)


# =====================================================================
# 필드 단위 BF — 정확 ICM 은 9명이 한계다 (10명 2.9초, 11명 30초).
# 그 위는 곡선으로 근사한다.
#
# 예전 근사(play.Hand.bf)는 필드를 9명 모델로 축약하고 상금표를
# k = round(9·itm/rem) 자리로 잘랐다. 그 축약에는 근거가 없었고
# 결과가 이랬다:
#   - rem>itm*3 컷오프가 계단 (181명 1.00 -> 180명 1.53)
#   - 60자리 상금 대회를 잔여 180명 시점에 '3자리'로 계산
#   - BF 곡선이 뒤집힘 (70명 2.66 > 61명 2.03). 버블이 정점이어야 하는데
#   - 9~40명 구간이 전부 2.03 으로 평평 (9명 모델 포화)
#
# 곡선은 두 비율만 본다. 그래야 400명이든 4000명이든 일관된다.
#   x = 잔여 / ITM인원      단계 압박
#   r = 내 스택 / 필드 평균  스택 위치
# =====================================================================

import math as _math

_SIGMA_STAGE = 0.55       # 버블 봉우리 폭 (로그 스케일)
_SIGMA_HI = 0.63          # 빅스택 쪽 감쇠. 딸 것이 많아 리스크가 싸다
_SIGMA_LO = 0.89          # 숏스택 쪽 감쇠. 이미 잃을 것이 적다
_LADDER_W = 0.95          # 인더머니 사다리 가중
_LADDER_P = 1.60          # 사다리 지수. 낮으면 버블 직후에 정점이 생긴다
_K = 1.50                 # 정점 크기. 버블·평균스택·표준상금에서 BF 2.5 가 되도록
_FLAT_GAIN = 0.95         # 상금 평탄도. 위성은 BF 가 크게 오른다
EXACT_MAX = 9             # 이 인원 이하는 정확 ICM


def _lognorm(v, sigma):
    if v <= 0:
        return 0.0
    z = _math.log(v)
    return _math.exp(-(z*z) / (2.0*sigma*sigma))


def stage_pressure(remaining, itm):
    """단계 압박. 버블에서 정점, 인더머니에서 사다리로 다시 오른다.

    계단이 없다. 예전의 rem > itm*3 컷오프는 한 명 탈락에 인식이 튀었다.
    """
    if not itm or itm <= 0 or not remaining or remaining <= 0:
        return 0.0
    x = float(remaining) / float(itm)
    bubble = _lognorm(x, _SIGMA_STAGE)                 # x=1 에서 1.0
    # 지수를 낮게 잡으면 버블 직후(x≈0.8)에 정점이 생긴다. 실제로는
    # 버블이 터지면 압박이 떨어지고 파이널이 가까워질 때 다시 오른다.
    ladder = max(0.0, 1.0 - x) ** _LADDER_P
    return min(1.30, bubble + _LADDER_W*ladder)


def stack_pressure(stack, field_avg):
    """스택 위치. 중간 스택이 가장 아프다.

    빅스택은 딸 것이 많아 리스크가 싸고, 숏스택은 이미 잃을 것이 적다.
    양쪽 감쇠 폭이 다르다 — 숏 쪽이 압박을 더 오래 유지한다.
    """
    if not field_avg or field_avg <= 0 or not stack or stack <= 0:
        return 1.0
    r = float(stack) / float(field_avg)
    return _lognorm(r, _SIGMA_HI if r >= 1.0 else _SIGMA_LO)


def field_bf(stack, field_avg, remaining, itm, payout_flat=0.0):
    """Field-level EMPIRICAL approximation, never exact prize ICM.

    The pre-existing log-normal stage/stack curves and coefficients are
    designer heuristics, not inferred outcome-specific payout probabilities.
    Keep the legacy constants unchanged; callers must report approximation
    provenance, including for <=9 surviving players with incomplete stacks.
    """
    st = stage_pressure(remaining, itm)
    if st <= 1e-6:
        return 1.0
    sp = stack_pressure(stack, field_avg)
    fl = 1.0 + _FLAT_GAIN*max(0.0, min(1.0, float(payout_flat)))
    return max(1.0, min(4.0, 1.0 + _K*st*sp*fl))


def field_epoch_id(pid_stacks, hand_no=None, level=None):
    """Deterministic field-epoch identity: PID/chips + tournament hand/level.

    This is audit evidence, not RNG, an elapsed-time guess, or a promise
    that a cached snapshot represents later completed tables.
    """
    import hashlib
    import json
    cells = sorted(
        ((type(pid).__name__, str(pid), float(chips))
         for pid, chips in dict(pid_stacks or {}).items()))
    blob = json.dumps(
        {'hand_no': hand_no, 'level': level, 'players': cells},
        sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def table_bf(stacks, seat_idx, remaining, itm, payouts, payout_flat=0.0,
             field_avg=None, field_stacks=None, return_details=False,
             field_pid_stacks=None, table_pids=None, snapshot_is_current=True,
             field_epoch_status=None, field_snapshot_id=None,
             observed_field_epoch_id=None, field_snapshot_scope=None):
    """Price-independent BF with explicit full-field completeness contract.

    `stacks` indexes CURRENT-TABLE players (seat_idx is local to this list).
    `remaining` counts the ENTIRE surviving tournament field. Optional
    `field_stacks` is a complete hand-start snapshot of all surviving stacks.
    It is exact for a split table only with a matching `field_pid_stacks`
    identity map, matching `table_pids`, and `snapshot_is_current=True`.
    Equal chip counts alone do not prove player/epoch identity. The BF is
    computed from exact generic field ICM, NOT a price-specific call payout EV.

    For <=EXACT_MAX: exact ICM requires the entire field at this table OR a
    validated full-field snapshot with an independently checked epoch. Otherwise use the PRE-EXISTING field_bf
    heuristic with explicit `method='field_bf_empirical_approximation'`.
    For >EXACT_MAX: use the same heuristic regardless of snapshot availability.
    No new coefficient, BF=1 shortcut, or unverified exactness label.
    """
    table = list(stacks)
    if not 0 <= seat_idx < len(table):
        raise IndexError('BF seat_idx outside current table')
    live = [float(v) for v in table if v > 0]
    rem = int(remaining) if remaining is not None else 0
    if remaining is not None and (rem != remaining or rem < 0):
        raise ValueError('remaining must be a nonnegative integer field count')
    snapshot = list(field_stacks or ())
    details = {
        'method': 'field_bf_empirical_approximation',
        'is_exact': False,
        'remaining': rem or None,
        'table_alive': len(live),
        'snapshot_alive': len(snapshot),
        'field_completeness': 'unknown',
        'reason': None,
        'bf_kind': 'generic_default_risk_not_spot_call_prize_ev',
        'price_specific': False,
        'snapshot_current': bool(snapshot_is_current and
                                 field_epoch_status == 'current_verified'),
        'field_epoch_status': field_epoch_status or 'unverified',
        'field_snapshot_scope': field_snapshot_scope or 'unknown',
        'field_snapshot_id': field_snapshot_id,
        'observed_field_epoch_id': observed_field_epoch_id,
        'observed_epoch_diverged': bool(
            field_snapshot_id and observed_field_epoch_id
            and field_snapshot_id != observed_field_epoch_id),
        'snapshot_epoch_exact': False,
    }

    def emit(value):
        details['value'] = value
        return details if return_details else value

    if len(live) < 2 or table[seat_idx] <= 0:
        details.update(method='not_applicable', reason='seat_not_active_or_no_opponent')
        return emit(1.0)

    if 2 <= rem <= EXACT_MAX:
        if len(live) == rem and (
                (snapshot and len(snapshot) != rem)
                or (field_pid_stacks and len(field_pid_stacks) != rem)):
            # A contradictory field snapshot means 'remaining' is not a
            # reliable complete-table certificate. Fail the exactness claim.
            details.update(field_completeness='contradictory_field_count',
                           reason='field_snapshot_conflicts_with_table_field_count')
        elif len(live) == rem:
            # The live table IS the entire field; no external chip snapshot
            # is required. Omit dead/zero-stack seats from the prize ranks.
            live_idx = sum(1 for v in table[:seat_idx] if v > 0)
            details.update(method='exact_full_field_icm',
                           is_exact=True, snapshot_epoch_exact=True,
                           snapshot_current=True,
                           field_completeness='complete_table',
                           reason='remaining_matches_all_live_table_seats')
            return emit(bubble_factor(live, list(payouts)[:rem] or [100.0],
                                      live_idx))

        elif not snapshot_is_current:
            details.update(field_completeness='stale_field_snapshot',
                           reason='table_stacks_changed_after_field_snapshot')
        elif field_epoch_status not in (
                'current_verified', 'frozen_epoch_reference'):
            details.update(
                field_completeness='unverified_or_stale_field_epoch',
                reason=('remote_field_changed_after_snapshot'
                        if field_epoch_status == 'stale_remote'
                        else 'missing_verified_field_epoch'))
        elif snapshot and len(snapshot) == rem:
            # Player IDs and epoch-matched stacks, not chip counts alone,
            # establish that the whole field is represented at this decision.
            from collections import Counter
            field_ids = dict(field_pid_stacks or {})
            local_ids = list(table_pids or ())
            valid_values = (
                all(_math.isfinite(float(v)) and float(v) > 0 for v in snapshot)
                and not (Counter(live) -
                         Counter(float(v) for v in snapshot)))
            valid_ids = (
                len(field_ids) == rem
                and len(local_ids) == len(table)
                and len(set(local_ids)) == len(local_ids)
                and all(pid in field_ids and
                        float(field_ids[pid]) == float(table[j])
                        for j, pid in enumerate(local_ids))
                and all(_math.isfinite(float(v)) and float(v) > 0
                        for v in field_ids.values())
                and Counter(float(v) for v in field_ids.values()) ==
                    Counter(float(v) for v in snapshot))
            if valid_values and valid_ids:
                own = float(table[seat_idx])
                full = [float(v) for v in snapshot]
                full_idx = full.index(own)
                if field_epoch_status == 'frozen_epoch_reference':
                    # Exact distribution *at the certified common batch epoch*,
                    # NOT a current-field calculation after another table
                    # has advanced. Preserve the frozen policy's numeric BF.
                    details.update(
                        method='frozen_epoch_reference_icm',
                        is_exact=False,
                        snapshot_epoch_exact=True,
                        snapshot_current=False,
                        field_completeness='verified_frozen_epoch_not_current',
                        reason='frozen_common_round_epoch_not_decision_current')
                else:
                    details.update(
                        method='exact_full_field_icm', is_exact=True,
                        snapshot_epoch_exact=True,
                        snapshot_current=True,
                        field_completeness='verified_player_id_field_snapshot',
                        reason='all_table_pids_match_snapshot_and_live_epoch')
                return emit(bubble_factor(full, list(payouts)[:rem] or [100.0],
                                          full_idx))
            details.update(
                field_completeness='invalid_field_snapshot',
                reason=('mismatched_table_stack_multiset' if not valid_values
                        else 'missing_or_mismatched_player_id_snapshot'))
        else:
            details.update(
                field_completeness='incomplete_field_snapshot',
                reason=('missing_full_field_stacks' if not snapshot
                        else 'snapshot_size_differs_from_remaining'))
    elif rem > EXACT_MAX:
        details.update(field_completeness='not_used_for_large_field',
                       reason='more_than_exact_max_survivors')
    else:
        details.update(field_completeness='unknown_field_count',
                       reason='remaining_unavailable_for_exact_icm')

    avg = field_avg if field_avg else (sum(live) / len(live))
    details['field_average_source'] = ('whole_field_context' if field_avg
                                       else 'local_table_fallback_not_field_average')
    return emit(field_bf(table[seat_idx], avg, rem, itm, payout_flat))


# is_bubble 은 제거했다. 버블 판정은 field.Field.in_bubble 하나뿐이다
# (예전에 정의가 세 곳에 서로 다른 값으로 있었다).
