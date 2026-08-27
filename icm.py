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
