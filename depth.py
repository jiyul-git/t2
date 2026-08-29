"""스택 깊이 인식. 계단(depth_band)을 대체하는 연속값.

    depth_feel(bb, prof, field_avg_bb, erosion) -> 0.0 ~ 1.0

0 = 완전 숏(푸시폴드), 1 = 완전 딥.

---

**왜 계단을 버리는가**

`depth_band` 는 8/15/25/60 을 경계로 다섯 칸이었다.
24.9bb 와 25.1bb 가 완전히 다른 사람이 된다.
3벳 형태(raise_form)에서 같은 문제를 이미 없앴는데 오픈 쪽에는 남아 있었다.

**왜 사람마다 달라야 하는가**

같은 50bb 를 쥐고도 한 사람은 "플레이할 여지가 많다"고 보고
다른 사람은 "얼른 넣어야겠다"고 본다. 그 차이가 행동으로 나온다.
전원 공통 경계로는 그게 표현되지 않는다.

**네 겹**

    기준 곡선        사람과 무관. 공개 자료 + 실전 감각
    × 필드 평균 대비   40bb 라도 평균이 25bb 면 딥이다
    × 예상 침식        블라인드가 곧 오른다. 터보에서 크다
    × 개인 오프셋      크기는 spr 개념, 방향은 자각 우위와 icm
"""

# ---------- 1. 기준 곡선 ----------
# 출처 대조:
#   BeyondGTO       딥 100+ / 미들 40~100 / 숏 20~40 / 푸시폴드 10~20 / 위급 10 미만
#   Preflop Wizard  딥 80~100+ / 미들 40~70 / 숏 20~35 / 푸시폴드 20 미만
#   PokerSkill      25bb 아래로는 포스트플랍 플레이어빌리티를 대부분 잃는다
#   PokerNews       36~50 은 거의 자유, 50 초과는 잔치
# 50bb 를 0.55(경계)로 둔 것은 "한 판에 올인이 날 수 있을까 싶은 지점"이라는
# 실전 감각과 위 자료가 겹치는 곳이기 때문이다.
_CURVE = [(0, 0.00), (10, 0.00), (15, 0.05), (20, 0.12), (25, 0.18),
          (35, 0.30), (40, 0.40), (50, 0.55), (70, 0.75),
          (100, 1.00), (300, 1.00)]


def _interp(tbl, x):
    if x <= tbl[0][0]:
        return tbl[0][1]
    if x >= tbl[-1][0]:
        return tbl[-1][1]
    for (x0, y0), (x1, y1) in zip(tbl, tbl[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return tbl[-1][1]


def base_feel(bb):
    """기준 곡선만. 사람도 상황도 안 본다."""
    return _interp(_CURVE, max(0.0, float(bb or 0.0)))


# ---------- 2. 필드 평균 대비 ----------
FIELD_POW = 0.45          # 40bb·평균25bb -> 체감 약 50bb
FIELD_CLAMP = (0.40, 2.50)


def field_adjusted_bb(bb, field_avg_bb):
    """필드 평균 대비로 체감 스택을 옮긴다.

    40bb 라도 전원이 25bb 면 나는 딥이다. 절대 bb 만 보면 이게 안 나온다.
    비율은 잘라 둔다 — 칩리더가 무한히 딥해지면 안 된다.
    """
    if not field_avg_bb or field_avg_bb <= 0:
        return float(bb)
    r = float(bb) / float(field_avg_bb)
    r = max(FIELD_CLAMP[0], min(FIELD_CLAMP[1], r))
    return float(bb) * (r ** FIELD_POW)


# ---------- 3. 예상 침식 ----------
# 지금 40bb 라도 곧 25bb 가 될 것을 알면 지금부터 짧은 것처럼 쳐야 한다.
# 포맷별 침식 속도 (한 오빗=8핸드 뒤 남는 비율):
#   deep 91% / standard 85% / turbo 73% / hyper 53%
# 하이퍼는 한 오빗에 40bb 가 21bb 가 된다. 무시할 크기가 아니다.
#
# **기준선 자체는 포맷과 무관하다.** 25bb 는 어디서나 25bb 다.
# 달라지는 것은 그 지점에 얼마나 빨리 닿느냐이고, 그것을 미리 보느냐다.
#
# 자료와 실전 감각 모두 "미리 보는 사람은 소수"라고 한다.
# 레귤러도 대부분 블라인드가 오른 뒤에 전략을 다시 짠다.
# 그래서 stack_decay 는 base 가 낮고 spread 가 커야 하는 개념이다.
LOOKAHEAD_MAX = 4.0       # 가장 잘 보는 사람이 내다보는 핸드 수


def lookahead_hands(prof, sk_fn):
    """몇 핸드 앞의 블라인드를 기준으로 볼 것인가. 0 ~ 4."""
    if not prof or not prof.get('concepts'):
        return 0.0
    return LOOKAHEAD_MAX * max(0.0, min(1.0, sk_fn(prof, 'stack_decay') / 9.0))


def eroded_bb(bb, hands_ahead, erosion_per_hand):
    """hands_ahead 핸드 뒤의 체감 bb.

    블라인드가 오르면 같은 칩이 더 적은 bb 가 된다.
    레벨 중반이면 2핸드 앞이나 지금이나 같은 블라인드라 자동으로 0 이 된다 —
    호출부가 '다음 레벨까지 남은 핸드 수'를 반영해 erosion 을 넘기면 된다.
    """
    if hands_ahead <= 0 or erosion_per_hand <= 0:
        return float(bb)
    return float(bb) / ((1.0 + erosion_per_hand) ** hands_ahead)


# ---------- 4. 개인 오프셋 ----------
OFFSET_MAX = 0.22         # 인식이 기준에서 벗어날 수 있는 최대 폭


EDGE_GAIN = 1.8           # edge 는 실측상 ±0.3 을 잘 안 넘는다. 방향축으로 쓰려면 증폭 필요
ICM_GAIN = 0.5


def depth_feel(bb, prof=None, field_avg_bb=None, erosion_per_hand=0.0,
               sk_fn=None, temper_fn=None, edge=0.0, icm_press=0.0):
    """스택 깊이 인식 0~1.

    edge      : 필드 대비 자기 실력 −1~+1 (자각이 걸린 값)
    icm_press : ICM **압박** 0~1 = icm_signal(bf) × 개념 가중치.
                개념 수준만 넘기면 안 된다 — 그러면 버블이 아닐 때도
                항상 양수로 들어가 edge 를 상쇄한다(실제로 그랬다).
                신호 × 개념 규약을 지킬 것.
    """
    b = float(bb or 0.0)
    if field_avg_bb:
        b = field_adjusted_bb(b, field_avg_bb)
    if prof is not None and sk_fn is not None and erosion_per_hand > 0:
        b = eroded_bb(b, lookahead_hands(prof, sk_fn), erosion_per_hand)

    feel = base_feel(b)
    if prof is None or sk_fn is None:
        return round(max(0.0, min(1.0, feel)), 4)

    # 크기 ← spr 개념. 낮을수록 기준에서 멀다. 상한 0.90 —
    # 가장 잘하는 사람도 기준과 완전히 같지는 않다.
    acc = 0.10 + 0.80 * min(1.0, sk_fn(prof, 'spr') / 8.0)

    # 방향 ← 자각 우위와 ICM.
    #  포스트플랍에서 이긴다고 보면 칩을 남겨 그 구간을 쓰고 싶다 -> 깊게 느낀다
    #  진다고 보면 그 구간을 없애고 싶다 -> 짧게 느낀다
    #  ICM 인식이 높으면 커밋을 미루려 하므로 깊게 느낀다
    # gamble 은 쓰지 않는다. 그것은 충동이고 이것은 지각이다. 층이 다르다.
    direction = max(-1.0, min(1.0,
        EDGE_GAIN*edge + ICM_GAIN*max(0.0, icm_press)))

    feel += (1.0 - acc) * direction * OFFSET_MAX
    return round(max(0.0, min(1.0, feel)), 4)


# ---------- 하위 호환 ----------
# 기존 depth_band 소비처를 한 번에 못 바꾸므로 역변환을 둔다.
# 새 코드는 depth_feel 을 직접 쓸 것. 이 함수는 이행용이다.
def band_of(feel):
    if feel < 0.05:  return 'micro'
    if feel < 0.12:  return 'short'
    if feel < 0.20:  return 'mid'
    if feel < 0.75:  return 'normal'
    return 'deep'
