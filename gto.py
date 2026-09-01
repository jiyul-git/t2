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
# 뒤에 남은 인원 → RFI 비율. 기준점은 40bb 안테 있음.
#
# 출처: 솔버 근사 공개 차트 (40bb 1bb안테 8맥스)
#   UTG 17 / UTG+1 19 / LJ 23 / HJ 28 / CO 36 / BTN 51 / SB 35
# '뒤에 남은 인원' 색인은 이 자료로 검증된다 —
# 9맥스 UTG(뒤 8명) 14~17%, 6맥스 첫 자리(뒤 5명) 22~26% 로
# 8맥스 LJ(뒤 5명, 23%)와 겹친다.
RFI_BY_BEHIND = {
    8: 0.15,      # 9맥스 UTG
    7: 0.17,      # 8맥스 UTG
    6: 0.19,
    5: 0.23,      # 9맥스 LJ / 6맥스 UTG
    4: 0.28,
    3: 0.36,      # CO
    2: 0.51,      # BTN
}
RFI_SB = 0.35     # SB 는 별도. 콜 옵션 없이 레이즈/폴드

# ---------- 스택 깊이 ----------
# 40bb 대비 배수. **단조가 아니다.**
# 40bb 가 정점이고 깊어도 좁아지고 얕아져도 좁아진다.
#   UTG   100bb 13% / 50bb 15% / 40bb 17% / 30bb 14% / 20bb 12%
#   CO    100bb 24% / 50bb 33% / 40bb 36% / 30bb 31% / 20bb 32%
#   BTN   100bb 42% / 50bb 46% / 40bb 51% / 30bb 46% / 20bb 50%
# 예전 DEPTH_OPEN_MULT(micro 2.40 ~ deep 0.95)은 '얕을수록 넓다'는
# 단조 증가였다. 방향부터 틀렸다.
#
# 그리고 곡선 모양이 포지션마다 다르다. 얕아질 때 얼리는 급격히 좁아지고
# 레이트는 거의 안 좁아진다(안테 때문에 스틸이 계속 남는다).
# 그래서 배수를 하나로 둘 수 없고 얼리/레이트 두 곡선을 섞는다.
_DEPTH_EARLY = [(5, 1.53), (10, 1.00), (15, 0.80), (20, 0.71), (30, 0.85),
                (40, 1.00), (50, 0.90), (75, 0.80), (100, 0.76), (250, 0.72)]
_DEPTH_LATE  = [(5, 0.92), (10, 0.76), (15, 0.85), (20, 0.98), (30, 0.90),
                (40, 1.00), (50, 0.90), (75, 0.85), (100, 0.82), (250, 0.78)]


def _interp(tbl, x):
    if x <= tbl[0][0]: return tbl[0][1]
    if x >= tbl[-1][0]: return tbl[-1][1]
    for (x0, y0), (x1, y1) in zip(tbl, tbl[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return y0 + t*(y1 - y0)
    return 1.0


def depth_mult(bb, behind):
    """스택 깊이 배수. 뒤에 남은 인원에 따라 얼리/레이트 곡선을 섞는다."""
    w = max(0.0, min(1.0, (behind - 2) / 5.0))     # 2(BTN)=레이트, 7+=얼리
    return _interp(_DEPTH_LATE, bb)*(1.0 - w) + _interp(_DEPTH_EARLY, bb)*w


# ---------- 안테 ----------
# 안테가 있으면 팟이 커져 스틸 이득이 크다. 기준표가 '안테 있음'이므로
# 없을 때를 줄인다. 공개 자료는 포지션당 2~4%p 정도 좁히라고 한다.
ANTE_MULT = {True: 1.00, False: 0.90}


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
    """기준 오픈 폭. 성향은 들어가지 않는다."""
    b = behind_of(pos, seats)
    if b == 0:
        return 0.0                        # BB 는 RFI 개념이 없다
    base = RFI_SB if b < 0 else RFI_BY_BEHIND.get(min(8, max(2, b)), 0.20)
    eff_behind = 1 if b < 0 else b        # SB 는 레이트 곡선 쪽
    return max(0.0, min(0.95,
        base * depth_mult(float(bb), eff_behind) * ANTE_MULT[bool(ante)]))


def avg_rfi(seats=8, bb=100.0, ante=True):
    """그 좌석수의 포지션 평균 RFI. 포지션 인식이 낮은 사람이 눌리는 지점."""
    _, pre, _ = _TB.orders(seats)
    vs = [rfi(p, seats, bb, ante) for p in pre if p != 'BB']
    return sum(vs)/max(1, len(vs))


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


# ---------- 디펜스 기준 ----------
# 별도 표를 두지 않는다. **디펜스 폭은 상대 오픈 폭의 함수다.**
# 공개 자료(9맥스, 3x 오픈 대면 BB):
#   BTN 오픈 51% -> 디펜스 56% / CO 36% -> 48% / HJ 28% -> 40% / UTG 15% -> 30%
# 이 네 점이 defend = 0.22 + 0.68 x rfi 에 거의 정확히 맞는다.
# 표를 따로 만들면 rfi 표와 어긋날 수 있고, 좌석수·깊이·안테 보정을
# 두 곳에서 따로 해야 한다.
DEF_A, DEF_B = 0.22, 0.68

# SB 오픈만 예외. 오픈 폭은 좁은데 디펜스는 가장 넓다(60%) —
# 블라인드 대 블라인드라 우리가 액션을 닫고 포스트플랍 포지션을 갖는다.
DEF_VS_SB = 0.60

# MDF — 오픈 사이즈가 정하는 하한. 위 표는 3x 기준이므로 그 비율로 조정한다.
_MDF = [(2.0, 0.72), (2.5, 0.62), (3.0, 0.56), (4.0, 0.48), (6.0, 0.38)]


def mdf(open_bb):
    return _interp(_MDF, max(1.5, float(open_bb or 3.0)))


# 디펜딩 포지션. BB 가 기준 1.0 — 이미 1bb 를 넣었고 액션을 닫는다.
DEF_SEAT = {'BB': 1.00, 'SB': 0.62, 'BTN': 0.46, 'CO': 0.34, 'HJ': 0.26,
            'LJ': 0.21, 'UTG+2': 0.18, 'UTG+1': 0.16, 'UTG': 0.14}

# 3벳이 디펜스에서 차지하는 몫. BB 대 BTN 에서 밸류 8~12%.
TB_SHARE = 0.18


def defend_pct(def_pos, opener_pos, seats=8, bb=100.0, ante=True, open_bb=2.5):
    """디펜스 기준 폭. 성향은 들어가지 않는다."""
    if opener_pos == 'SB':
        base = DEF_VS_SB
    else:
        base = DEF_A + DEF_B * rfi(opener_pos, seats, bb, ante)
    base *= mdf(open_bb) / mdf(3.0)
    base *= DEF_SEAT.get(def_pos, 0.20)
    return max(0.02, min(0.92, base))


def threebet_pct(def_pos, opener_pos, seats=8, bb=100.0, ante=True, open_bb=2.5):
    """디펜스 중 3벳 구간의 기준 폭."""
    return defend_pct(def_pos, opener_pos, seats, bb, ante, open_bb) * TB_SHARE
