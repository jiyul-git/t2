"""토너먼트 전체를 굴리는 드라이버."""
import random, math
import play, session as SE, field as F, view as V
from table import BLINDS, HANDS_PER_LEVEL
import formats as FM
import dynamics as DY

import archetypes as A

import persona as PS

def mk_profile(label_or_q, rng, quality=0.78, aggr_bias=0.0, loose_bias=0.0):
    """개념 벡터 개인을 만든다. label 인자는 하위호환용으로 무시.
       q(필드 실력)와 aggr_bias(필드 난폭도)가 이 대회의 성향 분포를 결정한다."""
    q = label_or_q if isinstance(label_or_q, (int, float)) else quality
    p = PS.make_player(rng, q, aggr_bias=aggr_bias, loose_bias=loose_bias)
    p['label'] = p['type']
    return p

class Tournament:
    def __init__(self, entries=100, start_stack=None, hero_seat=7, seats=None,
                 seed=None, itm_frac=None, hands_per_level=None,
                 buyin_level=None, fmt=None):
        # 포맷이 기본값을 정하고, 명시적으로 넘긴 인자가 그것을 덮어쓴다.
        f = FM.get(fmt)
        self.fmt = f
        self.blinds_tbl = FM.blind_schedule(BLINDS, f['blind_mult'], len(BLINDS))
        _bb0 = self.blinds_tbl[0][2]
        if start_stack is None:     start_stack = f['start_bb'] * _bb0
        if seats is None:           seats = f['seats']
        # 한계는 formats.py 한 곳에서만 정한다.
        # 좌석 상한은 포지션 사다리(table.orders)가 9까지만 정의되어 있기 때문이고,
        # 엔트리 상한은 합의된 운영 범위다. 넘기면 조용히 자르지 않고 막는다.
        if not (FM.MIN_SEATS <= seats <= FM.MAX_SEATS):
            raise ValueError('좌석은 %d~%d (받은 값 %s)' % (FM.MIN_SEATS, FM.MAX_SEATS, seats))
        if not (2 <= entries <= FM.MAX_ENTRIES):
            raise ValueError('엔트리는 2~%d (받은 값 %s)' % (FM.MAX_ENTRIES, entries))
        if itm_frac is None:        itm_frac = f['itm_frac']
        if hands_per_level is None: hands_per_level = f['hpl']
        if buyin_level is None:     buyin_level = f['buyin_level']
        self.rng = random.Random(seed)
        self.seats = list(range(1, seats+1))
        self.hero = hero_seat
        self.start_stack = start_stack
        self.hpl = hands_per_level
        self.hand_no = 0
        self.entries = entries
        self.buyin_level = buyin_level
        self.field = F.Field(entries, seed=self.rng.randrange(10**6), itm_frac=itm_frac)
        self.tables = F.Tables(self.field, seats, hero_seat, seed=self.rng.randrange(10**6))
        # ---- 이 대회의 성격 → 좌석 성향 분포 ----
        # 규모·바이인이 실력 수준을, Field.aggression 이 난폭도를 결정한다.
        base_q = F.field_quality(entries, buyin_level)
        # 지터가 좁으면 어떤 대회를 열어도 '보통 필드'만 나온다.
        self.field_q = round(max(0.10, min(1.35, base_q * self.rng.uniform(0.62, 1.42))), 3)
        # 난폭도와 헐거움은 별개 축이다. 난폭한 필드가 반드시 헐겁지는 않다
        # (공격적인 레귤러 필드 vs 소극적인 콜링 스테이션 필드는 전혀 다르다).
        self.aggr_bias  = round((self.field.aggression - 1.1) * 2.4, 2)
        self.loose_bias = round(max(-1.8, min(1.8,
                             (self.field.variance - 1.15) * 1.9
                             + (self.field.aggression - 1.1) * 0.5)), 2)
        # 상금 구조. 위성처럼 평탄하면 ICM 이 완전히 달라진다.
        self.payouts = FM.payouts(self.field.itm, f['payout_flat'])
        self.ante_from = f['ante_from']
        # 틸트는 대회 하나 동안 유지된다. 핸드마다 새로 만들면 안 쌓인다.
        self.tilt = DY.Tilt()
        self.stacks = {s: start_stack for s in self.seats}
        self.profiles = {}
        for s in self.seats:
            if s == hero_seat: continue
            self.profiles[str(s)] = self._new_profile()
        self.profiles[str(hero_seat)] = {'type':'TAG','label':'HERO','aggr':6,'gamble':4,
                                         'bluff':5,'icm':6,'value':'mixed','tilt':3,'goal':'accum'}
        self.button = self.rng.choice(self.seats)
        self.busted_hero = False
        self.notes = []
        # 리딩 장부는 이 대회에만 속한다 (대회 간 오염·재현성 붕괴 방지)
        import reads as _RD
        self.book = _RD.Book()

    def _new_profile(self):
        """이 대회의 필드 특성을 반영한 좌석 하나."""
        return mk_profile(self.field_q, self.rng, aggr_bias=self.aggr_bias,
                          loose_bias=self.loose_bias)

    def field_descriptor(self):
        q = self.field_q
        lv = '하드' if q >= 0.95 else ('소프트' if q <= 0.60 else '보통')
        a  = '난폭' if self.aggr_bias >= 0.5 else ('점잖음' if self.aggr_bias <= -0.5 else '평범')
        l  = '헐거움' if self.loose_bias >= 0.5 else ('빡빡함' if self.loose_bias <= -0.5 else '보통')
        return '%s 필드 / %s / %s (q=%.2f, aggr%+.2f, loose%+.2f)' % (
            lv, a, l, q, self.aggr_bias, self.loose_bias)

    # ---------- 레벨 ----------
    @property
    def level(self): return min(1 + self.hand_no//self.hpl, len(self.blinds_tbl))
    def blinds(self):
        _, sb, bb = self.blinds_tbl[self.level-1]; return sb, bb
    def prev_level(self):
        return min(1 + max(0, self.hand_no-1)//self.hpl, len(self.blinds_tbl))

    # ---------- 핸드 ----------
    def next_hand(self):
        self.notes = []
        lvl_before = self.prev_level()
        self.hand_no += 1
        if self.level > lvl_before:
            sb, bb = self.blinds()
            self.notes.append('⏱ 레벨 %d — %s/%s (%s ante)'
                              % (self.level, f'{sb:,}', f'{bb:,}', f'{bb:,}'))
        sb, bb = self.blinds()
        alive = [s for s in self.seats if self.stacks[s] > 0]
        if self.button not in alive:
            i = self.seats.index(self.button)
            for k in range(1, len(self.seats)+1):
                c = self.seats[(i+k) % len(self.seats)]
                if c in alive: self.button = c; break
        h = play.Hand(self.seats, self.profiles, self.stacks, self.button, sb, bb,
                      hero=self.hero, seed=self.rng.randrange(10**9), book=self.book)
        h.dyn = self.tilt
        h.field_q = self.field_q          # 분산 추구 판단에 필요 (내 실력 vs 필드)
        # ICM 은 필드 상태를 봐야 한다. 이 두 줄이 없으면 play.Hand.bf() 가
        # 항상 1.0(칩EV)을 반환해서 버블·머니점프가 어떤 판단에도 안 들어간다.
        # live.py 경로에는 있었고 여기만 빠져 있었다.
        # 안테 액수. 포맷의 ante_from 레벨부터 1BB 안테.
        h.ante = bb if self.level >= self.ante_from else 0
        h.field_remaining = self.field.remaining
        h.field_itm = self.field.itm
        h.payouts = self.payouts
        h.payout_flat = self.fmt['payout_flat']
        # 필드 평균 칩 = 전체 칩 / 잔여. 테이블 평균이 아니다 —
        # 내 테이블만 보면 필드 전체에서 내 위치를 알 수 없다.
        h.field_avg_stack = (self.entries * self.start_stack
                             / max(1, self.field.remaining))
        self.hand = h
        self.run = SE.HandRun(h)
        return self.run.start()

    def submit(self, action, amount=0):
        return self.run.send(action, amount)

    def finish_hand(self):
        h = self.hand
        self.stacks = dict(h.stacks)
        if self.stacks.get(self.hero, 0) <= 0:
            self.busted_hero = True
            self.field.remaining = max(1, self.field.remaining-1)
            return
        # 필드 진행
        out = self.field.step(self.level, 1)
        if out: self.notes.append('필드 %d명 탈락 → %d명 생존'
                                  % (out, self.field.remaining))
        # 테이블 재조정
        nc, moved, notes = self.tables.reconcile(self.seats, self.stacks, self.profiles,
                                                 self.start_stack, self.blinds()[1])
        if moved:
            self._move_hero()
        else:
            seated = self._seat(nc)
            for s, lab, bbv in seated:
                self.notes.append('%d번 자리에 새 플레이어 (%dbb)' % (s, bbv))
        self.notes.extend(n for n in notes if '자리 이동' not in n)
        alive = [s for s in self.seats if self.stacks[s] > 0]
        self.button = alive[(alive.index(self.button)+1) % len(alive)] \
            if self.button in alive else alive[0]

    def _seat(self, newcomers):
        """히어로 좌석은 절대 재배정하지 않는다."""
        bb = self.blinds()[1]
        empty = [s for s in self.seats if self.stacks.get(s, 0) <= 0 and s != self.hero]
        out = []
        for p in newcomers:
            if not empty: break
            s = empty.pop(0)
            # 칩 단위(sb)로 반올림한다. 실수 bb 를 그대로 환산하면
            # 33,920 같은 끝자리가 생겨 실제 토너에 없는 액수가 나온다.
            _unit = max(1, self.blinds()[0])
            self.stacks[s] = max(bb, int(round(p['stack_bb']*bb/_unit))*_unit)
            # p 는 이미 완성된 개념 벡터 개인이다. 버리고 다시 뽑지 않는다.
            p.setdefault('label', p.get('type', 'TAG'))
            self.profiles[str(s)] = p
            out.append((s, p['label'], round(p['stack_bb'])))
        return out

    def _move_hero(self):
        """새 테이블로 이동 — 히어로 스택만 유지하고 상대는 전원 교체."""
        bb = self.blinds()[1]
        avg = self.field.avg_stack_bb(self.start_stack, bb)
        n_others = min(len(self.seats)-1, max(1, self.field.remaining-1))
        for s in self.seats:
            if s == self.hero: continue
            self.stacks[s] = 0
        picked = [x for x in self.seats if x != self.hero][:n_others]
        for s in picked:
            p = F.make_player(self.rng, s, avg, entries=self.entries,
                              buyin_level=self.buyin_level, aggr_bias=self.aggr_bias)
            # 칩 단위(sb)로 반올림한다. 실수 bb 를 그대로 환산하면
            # 33,920 같은 끝자리가 생겨 실제 토너에 없는 액수가 나온다.
            _unit = max(1, self.blinds()[0])
            self.stacks[s] = max(bb, int(round(p['stack_bb']*bb/_unit))*_unit)
            p.setdefault('label', p.get('type', 'TAG'))
            self.profiles[str(s)] = p
        self.notes.append('🔄 테이블 이동 — 상대 전원 교체 (%d명 착석)' % n_others)

    # ---------- 문맥 ----------
    def ctx(self, view):
        sb, bb = self.blinds()
        st = self.field.status()
        return {'bb': bb, 'sb': sb, 'hand_no': self.hand_no, 'level': self.level,
                'hero': self.hero, 'seat_order': self.seats, 'pos_of': self.hand.pos,
                'stacks': view.get('stacks', self.stacks),
                'remaining': st['remaining'], 'entries': st['entries'],
                'itm': st['itm'], 'bubble': st['bubble']}
