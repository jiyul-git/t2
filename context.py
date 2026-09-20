"""핸드에 실리는 대회 문맥. **무엇을 실을지 정하는 유일한 곳.**

왜 필요한가
-----------
드라이버가 넷이다(tourney / live / live2 / fieldsim). 각자 `h.xxx = ...`
로 직접 심고 있었고, 심는 목록이 서로 달랐다.

    tourney   8개 (전부)
    live      3개
    live2     4개
    fieldsim  2개

빠진 값은 조용히 기본값으로 대체되어 **그 경로에서만 기능이 죽었다.**
같은 유형으로 이미 세 번 걸렸다.

    field_remaining 누락 -> tourney 에서 ICM 이 항상 1.0
    ante_from 미사용     -> 포맷이 3레벨부터라고 해도 1레벨부터 걷힘
    dyn 누락             -> tourney 에서 틸트가 매 핸드 초기화

새 문맥 값을 추가할 때 여기 한 곳만 고치면 되고,
`missing()` 이 어느 드라이버가 무엇을 빠뜨렸는지 알려준다.
"""

# 문맥에 실리는 값과 없을 때의 기본값.
# None 은 '기본값 없음 — 없으면 기능이 죽는다'는 뜻이다.
SPEC = {
    'field_q':          (0.6,  '필드 실력 수준. 분산추구·자각우위가 쓴다'),
    'field_remaining':  (None, '필드 잔여 인원. ICM 전체가 이것에 달렸다'),
    'field_itm':        (None, '인더머니 인원. 같음'),
    'field_avg_stack':  (None, '필드 평균 칩. 테이블 평균이 아니다'),
    'field_stacks':     ((),   '핸드 시작 시 생존자 스택 분포. 머니점프 관측 전용'),
    'payouts':          (None, '상금 구조. 없으면 표준표로 대체된다'),
    'payout_flat':      (0.0,  '상금 평탄도. 위성은 1.0'),
    'ante':             (None, '이번 핸드의 안테 액수. 0 이면 안 걷는다'),
    'dyn':              (None, '틸트 객체. 대회 단위로 유지되어야 한다'),
    'erosion_per_hand': (0.0,  '핸드당 블라인드 침식률. 깊이 인식이 쓴다'),
    'reentry':          (False,'리바인 가능 여부. 축적형 분산의 실패 비용을 낮춘다'),
    'progress':         (0.0,  '대회 진행도 0(시작)~1(끝). 잔여/엔트리로 계산'),
    'money_jump':       ({},   '현재 보장 상금과 다음 상금 점프 문맥. 판단 로직에는 아직 미사용'),
    'pid_prof':         ({},   '대회 전체 pid → 프로필. 틸트 감쇠가 자기 프로필을 '
                               '쓰려면 한 테이블분으로는 모자란다'),
}

# 주의: 기본값 {} 는 SPEC 에 든 **하나의 객체**다. 여기 실리는 맵은
# 읽기 전용으로만 쓴다 (session 은 복사해서 쓴다).

REQUIRED = tuple(k for k, (d, _) in SPEC.items() if d is None)


def progress_of(remaining, entries, itm=None):
    """대회 진행도 0~1. 잔여 인원이 줄수록 1 에 가깝다.

    선형이 아니다. 100명 중 50명 남은 것보다 10명 중 5명 남은 쪽이
    훨씬 후반이다. 로그 축이 실제 감각에 맞다.
    """
    import math
    e = max(2, int(entries or 2))
    r = max(1, min(e, int(remaining or e)))
    return max(0.0, min(1.0, math.log(e / r) / math.log(e)))


def money_jump_context(remaining, itm, payouts):
    """현재 보장 상금과 다음 실제 상금 점프를 계산한다.

    payouts 는 1위부터의 상금 비율(합계 100)이다. 통화 단위가 아니라
    구조만 표현한다. 같은 금액이 여러 등수에 걸쳐 있으면 그 구간을 건너
    실제로 상금이 커지는 다음 순위를 찾는다.

    반환값
      in_money        이미 ITM 인가
      current_rank    현재 생존자 수 기준 보장 등수(ITM 전에는 None)
      current_prize   지금 탈락해도 보장되는 상금 비율
      next_rank       다음으로 상금이 증가하는 생존자 수 / 없으면 None
      next_prize      그때 보장되는 상금 비율
      next_jump       next_prize - current_prize
      players_to_jump 그 점프까지 필요한 추가 탈락자 수
    """
    rem = max(1, int(remaining or 1))
    paid = max(0, int(itm or 0))
    pays = [float(x) for x in (payouts or [])]

    # 상금표 길이와 itm 이 어긋나면 실제 표가 있는 만큼만 신뢰한다.
    paid = min(paid, len(pays)) if pays else 0
    in_money = bool(paid and rem <= paid)

    if not paid:
        return {
            'in_money': False,
            'current_rank': None,
            'current_prize': 0.0,
            'next_rank': None,
            'next_prize': 0.0,
            'next_jump': 0.0,
            'players_to_jump': 0,
        }

    if not in_money:
        nxt_rank = paid
        nxt_prize = pays[paid - 1]
        return {
            'in_money': False,
            'current_rank': None,
            'current_prize': 0.0,
            'next_rank': nxt_rank,
            'next_prize': nxt_prize,
            'next_jump': nxt_prize,
            'players_to_jump': max(0, rem - paid),
        }

    current_rank = rem
    current_prize = pays[current_rank - 1]

    # 바로 위 등수가 같은 상금이면 실제 점프가 있는 곳까지 건너뛴다.
    next_rank = None
    next_prize = current_prize
    for rank in range(current_rank - 1, 0, -1):
        prize = pays[rank - 1]
        if prize > current_prize + 1e-12:
            next_rank = rank
            next_prize = prize
            break

    if next_rank is None:
        players_to_jump = 0
    else:
        players_to_jump = current_rank - next_rank

    return {
        'in_money': True,
        'current_rank': current_rank,
        'current_prize': current_prize,
        'next_rank': next_rank,
        'next_prize': next_prize,
        'next_jump': max(0.0, next_prize - current_prize),
        'players_to_jump': players_to_jump,
    }


def erosion(hands_per_level, blind_mult=1.0, base_growth=1.28):
    """핸드당 블라인드 침식률.

    레벨당 상승률을 핸드 수로 나눠 편다. 하이퍼(hpl 4, mult 1.35)는
    한 오빗에 스택이 절반이 된다.
    """
    hpl = max(1, int(hands_per_level or 1))
    g = 1.0 + (base_growth - 1.0) * max(0.3, float(blind_mult))
    return g ** (1.0 / hpl) - 1.0


class Context:
    """드라이버가 대회마다 하나 만들어 두고, 핸드마다 값만 갱신해 apply 한다."""

    def __init__(self, **kw):
        for k, (default, _) in SPEC.items():
            setattr(self, k, kw.get(k, default))

    def update(self, **kw):
        for k, v in kw.items():
            if k not in SPEC:
                raise KeyError('문맥에 없는 값: %s (context.SPEC 에 먼저 추가할 것)' % k)
            setattr(self, k, v)
        return self

    def missing(self):
        """기본값 없는 항목 중 아직 안 채운 것."""
        return [k for k in REQUIRED if getattr(self, k, None) is None]

    def apply(self, h, strict=False):
        """핸드에 심는다. strict 면 필수값 누락 시 예외."""
        miss = self.missing()
        if miss and strict:
            raise ValueError('문맥 누락: %s' % ', '.join(miss))
        for k in SPEC:
            setattr(h, k, getattr(self, k))
        return miss

    def __repr__(self):
        return '<Context %s>' % ' '.join(
            '%s=%s' % (k, getattr(self, k)) for k in ('field_remaining', 'field_itm',
                                                      'ante', 'field_q'))
