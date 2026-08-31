"""핸드 하나를 끝까지 진행한다. 히어로가 있으면 그 차례에서 멈춘다."""
import random, json, os, hashlib
import bot, preflop as pf, ranges as R, plan as PL, icm, dynamics as DY, runner as RU

import table as _TB
from table import SEAT_ORDER as ORDER
from table import PRE_ORDER as PRE, POST_ORDER as POST   # 단일 출처 재수출 (8맥스 기본)

class Hand:
    def __init__(self, seats, profiles, stacks, button, sb, bb, hero=None,
                 payouts=None, seed=None, dyn=None, book=None):
        self.rng = random.Random(seed if seed is not None else os.urandom(8))
        self.all_seats = list(seats)
        self.stacks = dict(stacks)
        self.busted = [s for s in seats if self.stacks.get(s, 0) <= 0]
        self.seats = [s for s in seats if self.stacks.get(s, 0) > 0]
        if len(self.seats) < 2:
            raise ValueError('생존 좌석 부족: %s' % self.seats)
        self.prof = profiles
        if button not in self.seats:                     # 버튼이 파산했으면 다음 생존자로
            idx = seats.index(button)
            for k in range(1, len(seats)+1):
                cand = seats[(idx+k) % len(seats)]
                if cand in self.seats: button = cand; break
        self.button = button
        self.sb, self.bb = sb, bb; self.hero = hero
        self.payouts = payouts or []
        self.dyn = dyn or {'seats': {}, 'hero_obs': {}}
        self.log = []; self.plans = {}
        import reads as _RD
        # 장부는 호출자가 소유한다. 주지 않으면 이 핸드 한정 빈 장부를 쓴다.
        # 디스크에서 무조건 읽으면 대회·세션이 서로 오염되고 같은 시드가 재현되지 않는다.
        self.book = book if book is not None else _RD.Book()
        n = len(self.seats)
        i = self.seats.index(button)
        # 좌석 수마다 포지션 사다리가 다르다. 8맥스 목록을 잘라 쓰면
        # 9인 테이블에서 인덱스가 넘친다.
        order, self.PRE, self.POST = _TB.orders(n)
        self.pos = {self.seats[(i+k) % n]: order[k] for k in range(n)}
        self.seat_of = {v: k for k, v in self.pos.items()}
        self._start_stacks = dict(self.stacks)
        self.seat_pid = {}          # 좌석번호 → 플레이어 고유 ID (없으면 좌석번호)
        self.deal()

    def deal(self):
        deck = [r+s for r in "23456789TJQKA" for s in "cdhs"]
        self.rng.shuffle(deck)
        self.hole = {}; i = 0
        for s in self.seats:
            self.hole[s] = [deck[i], deck[i+1]]; i += 2
        self.board = deck[i:i+5]
        raw = json.dumps({'hole': {str(k): v for k, v in self.hole.items()},
                          'board': self.board}, sort_keys=True).encode()
        self.sealed = raw
        self.hash = hashlib.sha256(raw).hexdigest()[:12]

    def bbs(self, s): return self.stacks[s]/self.bb
    def ptype(self, s): return self.prof[str(s)]['type']

    def axes(self, s):
        """판단에 넘길 프로필. 개념 벡터(concepts/temper)를 반드시 보존한다.

        예전에는 여기서 aggr/gamble/bluff/value/tilt/icm 6개 스칼라만 추려 넘겼다.
        그러면 persona.py 가 28개 개념으로 사람을 만들어도 포스트플랍은 6개 숫자만 보게 되고,
        하위 코드의 `profile.get('concepts')` 분기가 전부 죽는다
        (calc_noise·sk·call_bias 가 한 번도 실행되지 않았다).
        결과적으로 모든 봇이 같은 문턱으로 수렴해 개성이 사라진다.
        """
        p = self.prof[str(s)]
        base = dict(p)
        base.setdefault('tilt', 3)
        base.setdefault('goal', 'accum')
        tp, t = DY.tilted_profile(base, self.dyn, s, base['tilt'])
        # 틸트는 축 몇 개만 흔든다. 정체성 필드는 원본을 유지한다.
        for k in ('type', 'value', 'goal', 'concepts', 'temper', 'id', 'label'):
            if k in base: tp[k] = base[k]
        return tp, t

    def bf(self, s):
        """좌석 s 의 버블팩터. icm.table_bf 가 유일한 계산 지점.

        예전에는 여기서 필드를 9명 모델로 축약하고 상금표를 임의로 잘랐다.
        그 근사가 버블(61명)을 70명보다 낮게 만들고 9~40명 구간을 평평하게 했다.
        """
        rem = getattr(self, 'field_remaining', None)
        itm = getattr(self, 'field_itm', None)
        if not rem or not itm:
            return 1.0
        live = [x for x in self.seats if self.stacks[x] > 0]
        if len(live) < 2 or s not in live:
            return 1.0
        stacks = [self.stacks[x] for x in live]
        idx = live.index(s)
        pays = getattr(self, 'payouts', None) or [100, 62, 44, 34, 27, 22, 18, 15, 12]
        flat = getattr(self, 'payout_flat', 0.0)
        favg = getattr(self, 'field_avg_stack', None) or (sum(stacks)/len(stacks))
        return icm.table_bf(stacks, idx, rem, itm, pays, flat, favg)

    # ---------- 프리플랍 ----------
