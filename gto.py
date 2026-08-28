"""GTO 기준 레인지. 성향 조정 이전의 1층.

레인지는 세 층으로 만든다.

    GTO 기준  ×  성향 조정  ×  누적 판단  =  실제 레인지
      (여기)      persona      dynamics

1층은 사람과 무관하다. 포지션·좌석수·스택깊이·안테만 본다.
성향은 이 값을 넓히거나 좁힐 뿐, 기준 자체를 만들지 않는다.

---

**포지션 이름이 아니라 '뒤에 남은 인원'으로 색인한다.**

6맥스 UTG 는 뒤에 5명, 9맥스 LJ 도 뒤에 5명이다. 두 자리는 같은 레인지다.
이름으로 색인하면 좌석수마다 표를 따로 만들어야 하고, 그러면 표가
서로 어긋난다. 실제로 예전 표는 좌석수를 아예 안 봤고
9맥스 UTG 와 6맥스 UTG 가 같은 폭이었다.

SB 만 예외다. 뒤에 1명이라는 점은 BTN 다음이지만, 포스트플랍이 항상
아웃오브포지션이고 콜 옵션이 없다(리스틸 대상). 별도 값을 둔다.
"""

import table as _TB

# ---------- 1층: 기준 오픈 폭 ----------
# 뒤에 남은 인원 → RFI 비율.
# 기준점: 40bb 안테 있음. 다른 조건은 아래 배수로 조정한다.
#
# 얼리에서 레이트로 갈수록 넓어지는 곡선은 완만하지 않다.
# BTN 에서 급격히 벌어지는 것이 실제 솔버 출력의 모양이다.
RFI_BY_BEHIND = {
    8: 0.14,      # 9맥스 UTG
    7: 0.16,      # 9맥스 UTG+1 / 8맥스 UTG
    6: 0.18,
    5: 0.21,      # 9맥스 LJ / 6맥스 UTG
    4: 0.25,
    3: 0.31,      # CO
    2: 0.46,      # BTN
}
RFI_SB = 0.42     # SB 는 별도. 콜 옵션 없이 레이즈/폴드

# ---------- 스택 깊이 ----------
# 얕을수록 넓다. 폴드에쿼티가 커지고 포스트플랍 구간이 짧아지기 때문.
# preflop.DEPTH_OPEN_MULT 와 같은 역할이지만 여기가 단일 출처다.
DEPTH_MULT = {'micro': 2.40, 'short': 1.75, 'mid': 1.35,
              'normal': 1.00, 'deep': 0.95}

# ---------- 안테 ----------
# 안테가 있으면 팟이 커져서 스틸 성공 시 이득이 크다. 그래서 넓어진다.
# 기준표가 '안테 있음'이므로 없을 때를 줄인다.
ANTE_MULT = {True: 1.00, False: 0.88}


def behind_of(pos, seats=8):
    """그 포지션 뒤에 몇 명이 남아 있는가. SB 는 -1 로 표시(별도 처리)."""
    if pos == 'SB':
        return -1
    if pos == 'BB':
        return 0
    _, pre, _ = _TB.orders(seats)
    if pos not in pre:
        return 4                      # 모르는 이름이면 중간
    return len(pre) - pre.index(pos) - 1


def rfi(pos, seats=8, bb=100.0, ante=True, band=None):
    """기준 오픈 폭. 성향은 들어가지 않는다.

    band 를 주면 그것을 쓰고, 없으면 bb 로 계산한다.
    """
    b = behind_of(pos, seats)
    if b < 0:
        base = RFI_SB
    elif b == 0:
        base = 0.0                    # BB 는 RFI 개념이 없다
    else:
        base = RFI_BY_BEHIND.get(min(8, max(2, b)), 0.20)
    if band is None:
        import preflop as _pf
        band = _pf.depth_band(bb)
    return max(0.0, min(0.95, base * DEPTH_MULT.get(band, 1.0) * ANTE_MULT[bool(ante)]))


def table(seats=8, bb=100.0, ante=True):
    """그 좌석수의 전 포지션 기준표. 확인·시각화용."""
    _, pre, _ = _TB.orders(seats)
    return {p: round(rfi(p, seats, bb, ante), 4) for p in pre}


# ---------- 3층 자리 ----------
# 누적 판단은 아직 배선하지 않았다. 여기 시그니처만 정해둔다.
#
# 같은 사람이라도 이 대회 이 테이블에서 겪은 것이 레인지를 바꾼다.
#   - 내 오픈이 자주 3벳당했다 → 좁힌다
#   - 뒤에 앉은 사람들이 안 접는다 → 좁힌다
#   - 뒤에 핫존 스택이 있다 → 좁힌다 (preflop.hotzone_pressure, 현재 죽음)
#   - 틸트 → 넓힌다
#
# 이 층은 대장 6(관찰과 기억)에 의존한다. 관찰이 정리된 뒤에 붙인다.
def adapt_mult(prof, memory=None):
    """누적 판단 배수. 미배선 — 항상 1.0."""
    return 1.0
