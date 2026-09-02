from functools import lru_cache

def icm_equity(stacks, payouts):
    """Malmuth-Harville. stacks: list[float], payouts: list[float] (1위부터).
       반환: 각 스택의 기대 상금."""
    n = len(stacks)
    k = min(len(payouts), n)
    total = float(sum(stacks))
    if total <= 0: return [0.0]*n
    res = [0.0]*n

    def rec(remaining_idx, remaining_sum, place, prob, acc):
        if place >= k or prob < 1e-9:
            return
        for i in remaining_idx:
            if remaining_sum > 0:
                p = prob * (stacks[i] / remaining_sum)
            else:
                p = prob / len(remaining_idx)   # 전원 0칩이면 균등 분배
            res[i] += p * payouts[place]
            if place + 1 < k:
                nxt = [j for j in remaining_idx if j != i]
                rec(nxt, remaining_sum - stacks[i], place + 1, p, acc)

    rec(list(range(n)), total, 0, 1.0, None)
    return res

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


# ==================== 필드 규모 ICM 근사 ====================
# ICM 은 O(n!) 이라 400명을 직접 못 돌린다. 그래서 근사가 필요한데,
# 예전 근사(필드를 9명으로 축약 + 상금표를 k=round(9·itm/rem) 로 자름)는
# 잔여 인원과 상금 자릿수의 관계를 깨뜨렸다. 실제 거동:
#   - 181명 -> 180명에서 BF 가 1.00 -> 1.53 으로 튐 (rem > itm*3 계단)
#   - 잔여 180명일 때 상금이 3자리만 남음 (실제로는 60자리)
#   - 버블(61명) BF 2.03 < 70명 BF 2.66 — 정점이 뒤집힘
#   - 9~40명 구간이 전부 2.03 으로 평평 (9명 모델 포화)
#
# 대신 BF 를 두 비율의 함수로 직접 만든다.
#     r = 잔여 / ITM인원        상금까지 얼마나 남았나
#     s = 내 스택 / 평균 스택    나는 어디쯤인가
# 이러면 400명이든 4000명이든 일관되고 계단이 없다.
# 파이널(9명 이하)에서는 실제 스택과 실제 상금표로 정확한 ICM 을 쓴다.

EXACT_MAX_SEATS = 9          # 이하면 정확한 ICM
MAX_PREMIUM = 1.70           # 표준 상금 구조에서 붙는 최대 리스크 프리미엄

# 상금까지의 거리 -> 압박. 버블에서 정점, 터지면 급락, 파이널에서 재상승.
_PROX = [(0.00, 1.00), (0.05, 0.90), (0.15, 0.75), (0.30, 0.55), (0.50, 0.45),
         (0.80, 0.42), (0.98, 0.50),           # <- 버블 터진 직후
         (1.00, 0.98), (1.02, 1.00),           # <- 버블
         (1.20, 0.85), (1.50, 0.55), (2.00, 0.25), (3.00, 0.06), (5.00, 0.00)]

# 내 스택 위치 -> 압박. 평균 근처가 가장 아프다.
# 칩리더는 딸 게 많아서, 숏은 이미 잃을 게 없어서 낮다.
_STACK = [(0.00, 0.15), (0.15, 0.20), (0.30, 0.32), (0.60, 0.75), (1.00, 1.00),
          (1.50, 0.62), (2.50, 0.32), (4.00, 0.20), (10.0, 0.12)]


def _lerp(tbl, x):
    if x <= tbl[0][0]: return tbl[0][1]
    if x >= tbl[-1][0]: return tbl[-1][1]
    for (x0, y0), (x1, y1) in zip(tbl, tbl[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return tbl[-1][1]


def field_bf(my_stack, avg_stack, remaining, itm, payout_flat=0.0,
             stacks=None, payouts=None):
    """필드 규모 버블팩터. 1.0 = 칩EV.

    stacks/payouts 가 주어지고 인원이 EXACT_MAX_SEATS 이하면 정확한 ICM 을 쓴다.
    그 위에서는 두 비율(r, s)로 근사한다.
    """
    if remaining and remaining <= EXACT_MAX_SEATS and stacks and payouts:
        n = len(stacks)
        if n >= 2:
            k = min(len(payouts), n)
            return bubble_factor(list(stacks), list(payouts[:k]), 0)

    if not remaining or not itm or itm <= 0 or avg_stack <= 0:
        return 1.0
    r = float(remaining) / float(itm)
    s = float(my_stack) / float(avg_stack)
    prox = _lerp(_PROX, r)
    stk = _lerp(_STACK, s)
    # 상금이 평탄할수록(위성) 리스크 프리미엄이 커진다.
    flat = 1.0 + 0.80 * max(0.0, min(1.0, float(payout_flat)))
    return max(1.0, min(4.0, 1.0 + MAX_PREMIUM * prox * stk * flat))


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
    """필드 단위 버블팩터 근사. 9명 초과일 때 쓴다."""
    st = stage_pressure(remaining, itm)
    if st <= 1e-6:
        return 1.0
    sp = stack_pressure(stack, field_avg)
    fl = 1.0 + _FLAT_GAIN*max(0.0, min(1.0, float(payout_flat)))
    return max(1.0, min(4.0, 1.0 + _K*st*sp*fl))


def table_bf(stacks, seat_idx, remaining, itm, payouts, payout_flat=0.0,
             field_avg=None):
    """BF 단일 진입점. 인원에 따라 정확 ICM 과 곡선을 나눈다.

    stacks 는 그 테이블의 살아있는 스택. remaining 은 필드 전체 잔여.
    """
    live = [s for s in stacks if s > 0]
    if len(live) < 2:
        return 1.0
    rem = int(remaining or len(live))
    if rem <= EXACT_MAX:
        pays = list(payouts)[:rem] or [100.0]
        return bubble_factor(list(stacks), pays, seat_idx)
    avg = field_avg if field_avg else (sum(live)/len(live))
    return field_bf(stacks[seat_idx], avg, rem, itm, payout_flat)


# is_bubble 은 제거했다. 버블 판정은 field.Field.in_bubble 하나뿐이다
# (예전에 정의가 세 곳에 서로 다른 값으로 있었다).
