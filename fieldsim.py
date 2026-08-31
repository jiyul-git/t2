"""필드 전체를 실제로 돌린다. 확률 모델 없이 모든 탈락이 실제 파산에서 나온다."""
import json, os, math, random
import play, session as SE, persona as PS, reads as RD, field as FLD
import formats as FM, context as CTX, dynamics as DY
from table import BLINDS

D = os.path.dirname(os.path.abspath(__file__))
MAXSEAT = 8


class Table:
    def __init__(self, tid, players, button=None):
        self.id = tid
        self.players = players          # [{'pid','prof','stack'}]
        self.button = button if button is not None else 0
        self.hands = 0
        # 고정 좌석 슬롯: 1~8번 자리. 비면 None.
        self.seats = [None]*MAXSEAT
        for i, p in enumerate(players[:MAXSEAT]):
            self.seats[i] = p['pid']

    def seat_of(self, pid):
        return self.seats.index(pid)+1 if pid in self.seats else None

    def sit(self, p):
        """빈 자리에 앉힌다."""
        for i in range(MAXSEAT):
            if self.seats[i] is None:
                self.seats[i] = p['pid']; return i+1
        self.seats.append(p['pid']); return len(self.seats)

    def stand(self, pid):
        if pid in self.seats:
            self.seats[self.seats.index(pid)] = None

    def alive(self):
        return [p for p in self.players if p['stack'] > 0]

    def n(self): return len(self.alive())

    def chips(self): return sum(p['stack'] for p in self.players)


class Field:
    """전 테이블을 실제로 굴리는 필드."""

    def __init__(self, entries=100, start_stack=30000, hero_pid=0, seed=None,
                 hands_per_level=12, itm_frac=0.15, fmt=None):
        self.rng = random.Random(seed if seed is not None else int.from_bytes(os.urandom(4), 'big'))
        self.entries = entries
        self.start_stack = start_stack
        self.hands_per_level = hands_per_level
        self.itm = max(1, int(round(entries*itm_frac)))
        self.hand_no = 0
        self.level = 1
        self.busted_order = []           # 탈락 순서 (뒤에서부터 순위)
        self.hero_pid = hero_pid
        self.hero_moves = 0
        self.notes = []

        self._init_runtime(fmt)
        q = self.field_q
        self.players = {}
        for pid in range(entries):
            prof = (PS.make_player(self.rng, 0.9, pid) if pid == hero_pid
                    else PS.make_player(self.rng, q, pid))
            self.players[pid] = {'pid': pid, 'prof': prof, 'stack': start_stack,
                                 'table': None, 'seat': None}
        # 테이블 배치
        ids = list(self.players)
        self.rng.shuffle(ids)
        ntab = math.ceil(entries / MAXSEAT)
        self.tables = {}
        for t in range(ntab):
            chunk = ids[t*MAXSEAT:(t+1)*MAXSEAT]
            if not chunk: continue
            tb = Table(t, [self.players[p] for p in chunk], button=0)
            self.tables[t] = tb
            for i, p in enumerate(chunk):
                self.players[p]['table'] = t
                self.players[p]['seat'] = i

    # ---------- 조회 ----------
    def _init_runtime(self, fmt=None, tilt_state=None):
        """포맷에서 파생되는 실행 상태를 만든다.

        __init__ 과 역직렬화(live2._load_field) 양쪽에서 부른다.
        복원 쪽이 속성을 수동으로 나열하면 새 속성을 추가할 때마다
        한쪽만 고쳐져 그 경로에서 터진다(실제로 그랬다).
        """
        self.fmt = FM.get(fmt)
        self.payouts = FM.payouts(self.itm, self.fmt['payout_flat'])
        self.field_q = FLD.field_quality(self.entries, self.fmt['buyin_level'])
        self.ctx = CTX.Context()
        self.tilt = DY.Tilt()
        if tilt_state:
            self.tilt.state = dict(tilt_state)
        return self

    def stamp(self, h):
        """핸드에 대회 문맥을 심는다. 드라이버가 직접 h.xxx = 하지 않는다.

        live / live2 / fieldsim 이 각자 심다가 목록이 어긋나서
        경로마다 다른 기능이 죽어 있었다. 여기 하나로 모은다.
        """
        bb = self.blinds()[1]
        self.ctx.update(
            field_q=self.field_q,
            field_remaining=self.remaining(),
            field_itm=self.itm,
            field_avg_stack=(self.entries*self.start_stack
                             / max(1, self.remaining())),
            payouts=self.payouts,
            payout_flat=self.fmt['payout_flat'],
            ante=(bb if self.level >= self.fmt['ante_from'] else 0),
            dyn=self.tilt,
            erosion_per_hand=CTX.erosion(self.hands_per_level,
                                         self.fmt['blind_mult']),
        )
        self.ctx.apply(h, strict=True)
        return h

    def blinds(self):
        lv = min(self.level, len(BLINDS))
        _, sb, bb = BLINDS[lv-1]
        return sb, bb

    def remaining(self):
        return sum(1 for p in self.players.values() if p['stack'] > 0)

    def hero_table(self):
        return self.tables.get(self.players[self.hero_pid]['table'])

    def total_chips(self):
        return sum(p['stack'] for p in self.players.values())

    def avg_stack(self):
        r = self.remaining()
        return self.total_chips()/max(1, r)

    def hero_rank(self):
        """생존자 중 히어로의 칩 순위."""
        alive = sorted((p['stack'] for p in self.players.values() if p['stack'] > 0),
                       reverse=True)
        mine = self.players[self.hero_pid]['stack']
        if mine <= 0: return None
        return alive.index(mine) + 1 if mine in alive else None

    def chip_leader(self):
        alive = [p['stack'] for p in self.players.values() if p['stack'] > 0]
        return max(alive) if alive else 0

    def status(self):
        r = self.remaining()
        return {'entries': self.entries, 'remaining': r, 'itm': self.itm,
                'to_itm': max(0, r - self.itm), 'bubble': self.itm < r <= self.itm*FLD.Field.BUBBLE_HI,
                'avg': self.avg_stack(), 'tables': len(self.tables),
                'level': self.level, 'rank': self.hero_rank(),
                'leader': self.chip_leader()}

    # ---------- 한 핸드 ----------
    def _play_table(self, tb, fast=True):
        """봇 전용 테이블 한 핸드. 실제로 돌려서 스택을 갱신한다."""
        alive = tb.alive()
        if len(alive) < 2: return None
        seats = list(range(1, len(alive)+1))
        profs = {str(i+1): alive[i]['prof'] for i in range(len(alive))}
        stacks = {i+1: alive[i]['stack'] for i in range(len(alive))}
        btn = seats[tb.button % len(seats)]
        sb, bb = self.blinds()
        try:
            h = play.Hand(seats, profs, stacks, btn, sb, bb, hero=None,
                          seed=self.rng.randrange(10**9))
            h.seat_pid = {i+1: alive[i]['pid'] for i in range(len(alive))}
            h.table_id = tb.id
            self.stamp(h)
            run = SE.HandRun(h)
            run.start()
            for i in range(len(alive)):
                alive[i]['stack'] = int(h.stacks.get(i+1, alive[i]['stack']))
        except Exception:
            return None
        tb.button = (tb.button + 1) % max(1, len(alive))
        tb.hands += 1
        return True

    def step_others(self):
        """히어로 테이블 외 전 테이블을 한 핸드씩(인원 비례로 가감) 돌린다."""
        ht = self.players[self.hero_pid]['table']
        for tid, tb in list(self.tables.items()):
            if tid == ht: continue
            n = tb.n()
            if n < 2: continue
            # 인원이 적을수록 핸드가 빨리 돈다
            k = 1
            if n <= 5 and self.rng.random() < 0.45: k = 2
            elif n >= 8 and self.rng.random() < 0.20: k = 0
            for _ in range(k):
                if tb.n() < 2: break
                self._play_table(tb)
        self._collect_busts()
        self._balance()

    # ---------- 파산·밸런싱 ----------
    def _collect_busts(self):
        for p in self.players.values():
            if p['stack'] <= 0 and p['table'] is not None:
                tb = self.tables.get(p['table'])
                if tb and p in tb.players:
                    tb.players.remove(p); tb.stand(p['pid'])
                p['table'] = None
                self.busted_order.append(p['pid'])

    def _balance(self):
        """TDA식 밸런싱: 테이블 간 인원차 1 이하. 필요시 테이블 브레이크."""
        act = {t: tb for t, tb in self.tables.items() if tb.n() > 0}
        if not act: return
        need_tables = max(1, math.ceil(self.remaining()/MAXSEAT))
        # 테이블 브레이크
        while len(act) > need_tables:
            small = min(act.values(), key=lambda x: x.n())
            movers = list(small.players)
            del self.tables[small.id]
            act = {t: tb for t, tb in self.tables.items() if tb.n() > 0}
            if not act: break
            for m in movers:
                tgt = min(act.values(), key=lambda x: x.n())
                small.stand(m['pid'])
                tgt.players.append(m); tgt.sit(m); m['table'] = tgt.id
                if m['pid'] == self.hero_pid:
                    self.hero_moves += 1
                    self.notes.append('🔄 테이블 브레이크 — 너 자리 이동 (%d번째)' % self.hero_moves)
            act = {t: tb for t, tb in self.tables.items() if tb.n() > 0}
        # 인원 균등화
        for _ in range(12):
            act = {t: tb for t, tb in self.tables.items() if tb.n() > 0}
            if len(act) < 2: break
            big = max(act.values(), key=lambda x: x.n())
            small = min(act.values(), key=lambda x: x.n())
            if big.n() - small.n() <= 1: break
            mover = big.players[(big.button + 2) % len(big.players)]
            big.players.remove(mover); big.stand(mover['pid'])
            small.players.append(mover); small.sit(mover); mover['table'] = small.id
            if mover['pid'] == self.hero_pid:
                self.hero_moves += 1
                self.notes.append('🔄 테이블 밸런싱 — 너 자리 이동 (%d번째)' % self.hero_moves)

    def advance_level(self):
        new = min(1 + self.hand_no//self.hands_per_level, len(BLINDS))
        if new != self.level:
            self.level = new
            sb, bb = self.blinds()
            self.notes.append('⏱ 레벨 %d — %s/%s (%s ante)'
                              % (self.level, f'{sb:,}', f'{bb:,}', f'{bb:,}'))

    def rank_of(self, pid):
        """탈락 시 순위."""
        if pid in self.busted_order:
            idx = self.busted_order.index(pid)
            return self.remaining() + (len(self.busted_order) - idx)
        return self.remaining()
