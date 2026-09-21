"""토너 포맷. 대회 종류를 정의하는 단일 출처.

`tourney.Tournament(fmt='live_deep')` 로 쓴다.
개별 파라미터를 따로 넘기면 포맷값을 덮어쓴다.

축을 나눈 이유:
  구조(스택·레벨·블라인드)와 필드(누가 오는가)와 상금(무엇을 위해 치는가)은
  독립이다. 하이퍼터보 하이롤러도 있고 딥스택 저바이인도 있다.
  하나의 '난이도' 축으로 뭉치면 그 조합이 표현되지 않는다.

  라이브/온라인은 축으로 두지 않는다. 실제로 갈리는 것은 구조(스택·속도)와
  필드 수준이고, 그 둘을 이미 따로 갖고 있다. 플래그를 하나 더 두면
  같은 것을 두 축으로 표현하게 된다.
"""

# start_bb        스타팅 스택 (bb)
# hpl             레벨당 핸드 수. 낮을수록 빠른 구조
# blind_mult      블라인드 상승 배수 (1.0 = 표준 BLINDS 표)
# ante_from       안테 시작 레벨
# buyin_level     필드 실력 수준 (field_quality 입력)
# itm_frac        인더머니 비율
# payout_flat     상금 평탄도 0~1. 1.0 = 전원 동일(위성)
# reentry         리엔트리 가능 여부. 초반 도박성 상승
# seats           테이블 인원 (6~9). 포맷 기본값이며 인자로 덮어쓸 수 있다

FORMATS = {
    # ---------- 구조 ----------
    'deep': dict(
        name='딥스택',
        start_bb=300, hpl=18, blind_mult=0.85, ante_from=3,
        buyin_level=1.0, itm_frac=0.15, payout_flat=0.0,
        reentry=False, seats=8),

    'standard': dict(
        name='표준',
        start_bb=150, hpl=12, blind_mult=1.0, ante_from=2,
        buyin_level=1.0, itm_frac=0.15, payout_flat=0.0,
        reentry=False, seats=9),

    'turbo': dict(
        name='터보',
        start_bb=100, hpl=7, blind_mult=1.15, ante_from=1,
        buyin_level=0.9, itm_frac=0.15, payout_flat=0.0,
        reentry=True, seats=8),

    'hyper': dict(
        name='하이퍼 터보',
        start_bb=50, hpl=4, blind_mult=1.35, ante_from=1,
        buyin_level=0.85, itm_frac=0.15, payout_flat=0.0,
        reentry=True, seats=8),

    # ---------- 필드 수준 ----------
    'lowbuyin': dict(
        name='저바이인',
        start_bb=200, hpl=15, blind_mult=0.9, ante_from=3,
        buyin_level=0.45, itm_frac=0.15, payout_flat=0.0,
        reentry=True, seats=9),

    'main': dict(
        name='메인이벤트',
        start_bb=250, hpl=16, blind_mult=0.9, ante_from=3,
        buyin_level=1.0, itm_frac=0.15, payout_flat=0.0,
        reentry=False, seats=9),

    'highroller': dict(
        name='하이롤러',
        start_bb=200, hpl=14, blind_mult=1.0, ante_from=2,
        buyin_level=2.2, itm_frac=0.12, payout_flat=0.0,
        reentry=True, seats=8),

    # ---------- 상금 구조 ----------
    'satellite': dict(
        name='위성 (평탄 상금)',
        start_bb=150, hpl=12, blind_mult=1.0, ante_from=2,
        buyin_level=1.1, itm_frac=0.10, payout_flat=1.0,
        reentry=False, seats=8),

    'bounty': dict(
        name='바운티 (녹아웃)',
        start_bb=150, hpl=10, blind_mult=1.05, ante_from=1,
        buyin_level=0.85, itm_frac=0.15, payout_flat=0.35,
        reentry=True, seats=8),
}

DEFAULT = 'standard'

# ---------- 한계 ----------
MAX_ENTRIES = 400      # 필드 최대 인원
MAX_SEATS   = 9        # 테이블 최대 인원 (포지션 사다리 상한)
MIN_SEATS   = 6


def get(name=None):
    """포맷 dict 사본. 없는 이름이면 기본값."""
    f = dict(FORMATS.get(name or DEFAULT, FORMATS[DEFAULT]))
    f['key'] = name if name in FORMATS else DEFAULT
    return f


def names():
    return list(FORMATS)


# ---------- 상금 구조 ----------
# 기본 곡선. payout_flat 로 평탄화한다.
BASE_PAYOUT = [100, 62, 44, 34, 27, 22, 18, 15, 12, 10, 9, 8, 7, 6.5, 6, 5.5, 5, 4.5]


def payouts(n_paid, flat=0.0):
    """n_paid 자리까지의 상금 비율. flat 1.0 이면 전원 동일.

    위성은 모든 자리가 같은 상금(티켓)이다. 그러면 ICM 의 bubble_factor 가
    상한(4.0)에 붙고, 칩을 더 따는 것에 가치가 거의 없어진다.
    그 구간을 표현하려면 상금 평탄도가 파라미터여야 한다.
    """
    n = max(1, int(n_paid))
    base = list(BASE_PAYOUT[:n])
    while len(base) < n:
        base.append(base[-1] * 0.92)
    even = sum(base) / n
    f = max(0.0, min(1.0, float(flat)))
    out = [b*(1.0 - f) + even*f for b in base]
    tot = sum(out) or 1.0
    return [round(100.0*x/tot, 3) for x in out]


def _round_blind(x):
    """실제 토너에 있는 액수로 맞춘다. 33,920 같은 끝자리를 만들지 않는다."""
    if x < 200:    step = 25
    elif x < 1000: step = 100
    elif x < 5000: step = 500
    elif x < 20000: step = 1000
    elif x < 100000: step = 5000
    else: step = 25000
    return max(step, int(round(x/step))*step)


BASE_GROWTH = 1.28      # 표준 구조의 레벨당 블라인드 상승률


def blind_schedule(base_blinds, mult=1.0, levels=None):
    """블라인드 표를 상승률로 다시 만든다.

    배수를 기존 표에 곱하면 안 된다. 표가 이미 기하급수라 복리가 두 번 걸린다
    (실제로 x1.35 에서 레벨 15 가 534,300BB 까지 갔다).
    조정하는 것은 액수가 아니라 **레벨당 상승률**이다.

      mult 0.85 → 상승률 1.238  (딥스택, 느린 구조)
      mult 1.00 → 상승률 1.280  (표준)
      mult 1.35 → 상승률 1.378  (하이퍼)
    """
    n = levels or len(base_blinds)
    if not base_blinds:
        return []
    _, sb0, bb0 = base_blinds[0]
    g = 1.0 + (BASE_GROWTH - 1.0) * max(0.3, float(mult))
    out = []
    for i in range(n):
        bb = _round_blind(bb0 * (g ** i))
        sb = _round_blind(bb * (sb0 / max(1.0, bb0)))
        out.append((i+1, max(1, min(sb, bb//1)), bb))
    return out
