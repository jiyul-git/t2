"""필드 전체를 실제로 돌린다. 확률 모델 없이 모든 탈락이 실제 파산에서 나온다."""
import json, os, math, random
import play, session as SE, persona as PS, reads as RD, field as FLD
import formats as FM, context as CTX, dynamics as DY
from table import BLINDS, orders as position_orders

D = os.path.dirname(os.path.abspath(__file__))
MAXSEAT = 8  # legacy fallback; Field instances use fmt['seats']
import storage_paths as _SP
# 상태 경로에서 나온다. live2 가 워커용으로 잠시 덮어쓰므로 모듈 전역이다.
BOT_SUFFIX = _SP.namespace()
# 켜면 핸드 실패를 삼키지 않고 즉시 올린다. 디버깅·검증용.
STRICT = bool(os.environ.get('T2_STRICT'))


class Table:
    """토너먼트 테이블의 고정 좌석 + TDA dead-button blind state.

    핵심은 BTN이 아니라 BB 진행이다. BB는 매 핸드 다음 생존자로 이동하고,
    SB/BTN은 그 진행을 따라간다. 따라서 탈락에 따라 SB나 BTN 마커가 빈 좌석
    (dead small / dead button)에 놓일 수 있다.
    """
    def __init__(self, tid, players, button=None, max_seat=MAXSEAT,
                 button_seat=None, sb_seat=None, bb_seat=None):
        self.id = tid
        self.players = players          # [{'pid','prof','stack'}]
        self.button = int(button or 0)   # 구 저장본 호환용 live-index
        self.button_seat = button_seat   # 물리 BTN 마커. 빈 좌석일 수 있다.
        self.sb_seat = sb_seat           # 물리 SB 마커. 빈 좌석일 수 있다.
        self.bb_seat = bb_seat           # BB는 실제 생존자가 있는 좌석이어야 한다.
        self.hands = 0
        self.max_seat = int(max_seat or MAXSEAT)
        self.seats = [None] * self.max_seat
        for i, p in enumerate(players[:self.max_seat]):
            self.seats[i] = p['pid']
        self.restore_positions(
            self.button, button_seat, sb_seat, bb_seat,
            legacy_dead_hint=False)

    def _marker(self, seat):
        try:
            s = int(seat)
        except (TypeError, ValueError):
            return None
        return s if 1 <= s <= self.max_seat else None

    def _next_slot(self, seat, step=1):
        s = self._marker(seat)
        if s is None:
            s = self.max_seat
        return ((s - 1 + int(step)) % self.max_seat) + 1

    def seat_of(self, pid):
        return self.seats.index(pid) + 1 if pid in self.seats else None

    def player_at(self, seat):
        s = self._marker(seat)
        if s is None:
            return None
        pid = self.seats[s - 1]
        if pid is None:
            return None
        return next((p for p in self.players
                     if p['pid'] == pid and p['stack'] > 0), None)

    def sit(self, p, seat=None):
        """빈 좌석에 앉힌다. seat=None이면 첫 빈 좌석(legacy 호출)."""
        if seat is None:
            candidates = [i + 1 for i, pid in enumerate(self.seats) if pid is None]
            if not candidates:
                raise ValueError('테이블 좌석 초과: max_seat=%d' % self.max_seat)
            seat = candidates[0]
        seat = self._marker(seat)
        if seat is None or self.seats[seat - 1] is not None:
            raise ValueError('앉을 수 없는 좌석: %s' % seat)
        self.seats[seat - 1] = p['pid']
        p['seat'] = seat - 1
        return seat

    def stand(self, pid):
        if pid in self.seats:
            i = self.seats.index(pid)
            self.seats[i] = None
            p = next((x for x in self.players if x['pid'] == pid), None)
            if p is not None:
                p['seat'] = None

    def alive(self):
        return [p for p in self.players if p['stack'] > 0]

    def ordered_alive(self):
        """고정 물리 좌석의 시계방향 순서로 생존자를 반환한다."""
        return sorted(
            (p for p in self.alive() if self.seat_of(p['pid']) is not None),
            key=lambda p: self.seat_of(p['pid'])
        )

    def _live_seats(self):
        return [self.seat_of(p['pid']) for p in self.ordered_alive()]

    def _next_live_after(self, marker, live=None):
        live = set(self._live_seats() if live is None else live)
        if not live:
            return None
        start = self._marker(marker)
        if start is None:
            start = self.max_seat
        for d in range(1, self.max_seat + 1):
            cand = ((start - 1 + d) % self.max_seat) + 1
            if cand in live:
                return cand
        return None

    def _clockwise_live_after(self, marker, live=None):
        live = set(self._live_seats() if live is None else live)
        if not live:
            return []
        start = self._marker(marker)
        if start is None:
            start = self.max_seat
        out = []
        for d in range(1, self.max_seat + 1):
            cand = ((start - 1 + d) % self.max_seat) + 1
            if cand in live:
                out.append(cand)
        return out

    def _between(self, start, end):
        """물리적으로 start 다음부터 end 직전까지의 좌석."""
        a = self._marker(start); b = self._marker(end)
        if a is None or b is None or a == b:
            return []
        out = []
        for d in range(1, self.max_seat):
            cand = ((a - 1 + d) % self.max_seat) + 1
            if cand == b:
                break
            out.append(cand)
        return out

    def _sync_legacy_button(self):
        live = self._live_seats()
        if not live:
            self.button = 0
            return
        if self.button_seat in live:
            self.button = live.index(self.button_seat)
        else:
            nxt = self._next_live_after(self.button_seat, live)
            self.button = live.index(nxt) if nxt in live else 0

    def restore_positions(self, button=None, button_seat=None,
                          sb_seat=None, bb_seat=None,
                          legacy_dead_hint=False):
        """저장 상태를 복원한다.

        구 저장본은 SB/BB 마커가 없다. 그런 경우 현재 BTN 바로 다음 물리 슬롯이
        비어 있으면 '직전 BB 탈락 뒤 dead SB'일 가능성을 보존하는 1회 migration
        힌트를 쓴다. 새 저장본은 세 마커를 모두 명시하므로 추정하지 않는다.
        """
        live = self._live_seats()
        if not live:
            self.button = 0
            self.button_seat = self._marker(button_seat)
            self.sb_seat = self._marker(sb_seat)
            self.bb_seat = self._marker(bb_seat)
            return None

        btn = self._marker(button_seat)
        if btn is None:
            btn = live[int(button or 0) % len(live)]
        self.button_seat = btn

        if len(live) == 1:
            self.sb_seat = None
            self.bb_seat = live[0]
            self._sync_legacy_button()
            return btn

        sb = self._marker(sb_seat)
        bb = self._marker(bb_seat)

        if len(live) == 2:
            if bb not in live:
                bb = self._next_live_after(btn, live)
            sb = next(s for s in live if s != bb)
            self.button_seat = sb
            self.sb_seat = sb
            self.bb_seat = bb
            self._sync_legacy_button()
            return self.button_seat

        if bb not in live:
            if sb is not None:
                bb = self._next_live_after(sb, live)
            elif legacy_dead_hint:
                physical_next = self._next_slot(btn)
                sb = physical_next
                bb = self._next_live_after(sb, live)
            else:
                sb = self._next_live_after(btn, live)
                bb = self._next_live_after(sb, live)

        if sb is None:
            sb = self._next_live_after(btn, live)

        self.sb_seat = sb
        self.bb_seat = bb
        self._sync_legacy_button()
        return self.button_seat

    def restore_button(self, button=None, button_seat=None):
        """구 호출부 호환. 새 코드는 restore_positions를 사용한다."""
        return self.restore_positions(
            button, button_seat, self.sb_seat, self.bb_seat,
            legacy_dead_hint=False)

    def dealer_seat(self):
        """현재 BTN 마커. dead button이면 빈 물리 좌석을 그대로 반환한다."""
        return self.button_seat

    def _maximize_dead_button_for_open_seats(self):
        """TDA 36-B: dead BTN 뒤의 연속 빈 좌석을 최대한 통과시킨다.

        블라인드(SB/BB)는 건드리지 않는다. BTN이 빈 자리이고 BTN->SB 사이에
        추가 빈 자리가 연속돼 있으면 BTN을 SB 직전 빈 자리까지 전진시킨다.
        이렇게 해야 새/브레이크 플레이어가 들어올 수 있는 좌석을 최대화하면서
        누구도 BB를 건너뛰거나 연속으로 내지 않는다.
        """
        live = set(self._live_seats())
        if len(live) < 3 or self.button_seat in live or self.sb_seat is None:
            return self.button_seat

        cur = self._marker(self.button_seat)
        if cur is None:
            return self.button_seat

        while True:
            nxt = self._next_slot(cur)
            if nxt == self.sb_seat:
                break
            if nxt in live:
                break
            cur = nxt

        self.button_seat = cur
        self._sync_legacy_button()
        return self.button_seat

    def reconcile_next_hand(self):
        """좌석 이동/테이블 브레이크 뒤 다음 핸드 마커를 유효하게 만든다.

        BTN/SB의 dead 상태는 보존하고, 반드시 실제 플레이어가 필요한 BB만
        다음 생존자로 넘긴다. HU가 되면 BTN=SB를 강제한다.
        """
        live = self._live_seats()
        if not live:
            self.button = 0
            self.bb_seat = None
            return
        if len(live) == 1:
            self.button_seat = live[0]
            self.sb_seat = None
            self.bb_seat = live[0]
            self._sync_legacy_button()
            return

        if len(live) == 2:
            bb = (
                self.bb_seat
                if self.bb_seat in live
                else self._next_live_after(
                    self.bb_seat or self.button_seat, live)
            )
            sb = next(s for s in live if s != bb)
            self.button_seat = sb
            self.sb_seat = sb
            self.bb_seat = bb
            self._sync_legacy_button()
            return

        if self.button_seat is None:
            self.button_seat = live[0]
        if self.sb_seat is None:
            self.sb_seat = self._next_live_after(self.button_seat, live)
        if self.bb_seat not in live:
            self.bb_seat = self._next_live_after(
                self.bb_seat if self.bb_seat is not None else self.sb_seat,
                live)
        self._maximize_dead_button_for_open_seats()
        self._sync_legacy_button()

    def hand_layout(self):
        """현재 핸드의 TDA 포지션/액션 순서를 한 곳에서 만든다."""
        self.reconcile_next_hand()
        live = self._live_seats()
        n = len(live)
        if n < 2:
            raise ValueError('생존 좌석 부족: %s' % live)

        if n == 2:
            sb = self.sb_seat
            bb = self.bb_seat
            pos = {sb: 'SB', bb: 'BB'}
            return {
                'button': self.button_seat, 'sb': sb, 'bb': bb,
                'pos': pos, 'pre_seats': [sb, bb], 'post_seats': [bb, sb],
                'dead_button': False, 'dead_sb': False,
            }

        btn_live = self.button_seat in live
        sb_live = self.sb_seat in live
        effective_n = n + (0 if btn_live else 1) + (0 if sb_live else 1)
        if effective_n > self.max_seat or effective_n > 9:
            raise ValueError(
                'dead-button 포지션 슬롯 초과: live=%d effective=%d max=%d'
                % (n, effective_n, self.max_seat))

        _seat_order, pre_template, _post_template = position_orders(effective_n)
        labels = [
            p for p in pre_template
            if not (p == 'BTN' and not btn_live)
            and not (p == 'SB' and not sb_live)
        ]
        pre_seats = self._clockwise_live_after(self.bb_seat, live)
        if len(labels) != len(pre_seats):
            raise ValueError(
                '포지션 수 불일치: labels=%s seats=%s' % (labels, pre_seats))
        pos = dict(zip(pre_seats, labels))
        post_seats = self._clockwise_live_after(self.button_seat, live)

        return {
            'button': self.button_seat,
            'sb': self.sb_seat,
            'bb': self.bb_seat,
            'pos': pos,
            'pre_seats': pre_seats,
            'post_seats': post_seats,
            'dead_button': not btn_live,
            'dead_sb': not sb_live,
        }

    def advance_button(self):
        """한 핸드 종료 후 TDA dead-button 방식으로 다음 blind state로 이동.

        기준은 BB다. 다음 BB는 직전 BB 다음 생존자, 다음 SB 마커는 직전 BB
        자리, 다음 BTN 마커는 직전 SB 자리다. 그래서 탈락하면 SB/BTN이
        자연스럽게 dead가 된다. HU는 BTN=SB이며 누구도 BB를 연속으로 내지 않는다.
        """
        # 현재 핸드 마커가 구 상태라면 먼저 정상화한다.
        self.reconcile_next_hand()
        old_sb = self.sb_seat
        old_bb = self.bb_seat
        live = self._live_seats()

        if len(live) < 2:
            if live:
                self.button_seat = live[0]
                self.sb_seat = None
                self.bb_seat = live[0]
            self._sync_legacy_button()
            return self.button_seat

        next_bb = self._next_live_after(old_bb, live)

        if len(live) == 2:
            next_sb = next(s for s in live if s != next_bb)
            self.button_seat = next_sb
            self.sb_seat = next_sb
            self.bb_seat = next_bb
        else:
            # 2026 TDA Rule 36-B: normal blind progression을 보존하면서
            # vacant seats를 최대한 쓸 수 있게 BTN은 새 SB 바로 전 물리 슬롯까지
            # 전진할 수 있다. 따라서 오래된 dead gap에 BTN을 남겨두지 않는다.
            self.sb_seat = old_bb
            self.button_seat = self._next_slot(self.sb_seat, -1)
            self.bb_seat = next_bb
            self._maximize_dead_button_for_open_seats()

        self._sync_legacy_button()
        return self.button_seat

    def player_after_button(self, offset):
        """legacy helper: 현재 BTN 마커 뒤 생존자 offset번째."""
        order = self._clockwise_live_after(self.button_seat)
        if not order:
            return None
        idx = max(0, int(offset) - 1) % len(order)
        return self.player_at(order[idx])

    def next_bb_player(self):
        """다음 핸드에 BB를 낼 플레이어. TDA table-balance 이동 대상."""
        self.reconcile_next_hand()
        return self.player_at(self.bb_seat)

    def broken_open_seats(self):
        """broken-table 유입 가능 좌석. BTN~SB 사이만 금지(Rule 11)."""
        forbidden = set(self._between(self.button_seat, self.sb_seat))
        return [
            i + 1 for i, pid in enumerate(self.seats)
            if pid is None and (i + 1) not in forbidden
        ]

    def worst_open_seat(self):
        """balance 이동의 destination: SB 제외, BB가 가장 빨리 오는 빈자리."""
        self.reconcile_next_hand()
        candidates = [
            i + 1 for i, pid in enumerate(self.seats)
            if pid is None and (i + 1) != self.sb_seat
        ]
        if not candidates:
            return None

        live = set(self._live_seats())

        def score(seat):
            if seat == self.bb_seat:
                return (0, seat)
            passed_live = 0
            start = self._marker(self.bb_seat) or self.max_seat
            for d in range(1, self.max_seat + 1):
                cand = ((start - 1 + d) % self.max_seat) + 1
                if cand == seat:
                    return (1 + passed_live, seat)
                if cand in live:
                    passed_live += 1
            return (self.max_seat + 1, seat)

        return min(candidates, key=score)

    def n(self): return len(self.alive())

    def chips(self): return sum(p['stack'] for p in self.players)


class Field:
    """전 테이블을 실제로 굴리는 필드."""

    def __init__(self, entries=100, start_stack=30000, hero_pid=0, seed=None,
                 hands_per_level=12, itm_frac=0.15, fmt=None):
        self.seed = seed if seed is not None else int.from_bytes(os.urandom(4), 'big')
        self.rng = random.Random(self.seed)
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
        self.errors = []          # 삼킨 예외 기록. 비어 있지 않으면 문제가 있다

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
        ntab = math.ceil(entries / self.max_seat)
        self.tables = {}
        for t in range(ntab):
            chunk = ids[t*self.max_seat:(t+1)*self.max_seat]
            if not chunk: continue
            tb = Table(t, [self.players[p] for p in chunk], button=0,
                       max_seat=self.max_seat)
            self.tables[t] = tb
            for i, p in enumerate(chunk):
                self.players[p]['table'] = t
                self.players[p]['seat'] = i

        # ceil(entries/max_seat) 로 마지막 테이블이 1명만 남을 수 있다
        # (예: 100명 9-max = 9x11 + 1). 첫 핸드 전에 균등화하지 않으면
        # 그 한 명만 블라인드를 내지 않고 한 핸드를 쉬게 된다.
        self._balance(notify=False)

    # ---------- 조회 ----------
    def _init_runtime(self, fmt=None, tilt_state=None):
        """포맷에서 파생되는 실행 상태를 만든다.

        __init__ 과 역직렬화(live2._load_field) 양쪽에서 부른다.
        복원 쪽이 속성을 수동으로 나열하면 새 속성을 추가할 때마다
        한쪽만 고쳐져 그 경로에서 터진다(실제로 그랬다).
        """
        self.fmt = FM.get(fmt)
        self.max_seat = int(self.fmt.get('seats', MAXSEAT))
        if not (2 <= self.max_seat <= FM.MAX_SEATS):
            raise ValueError('잘못된 테이블 좌석 수: %s' % self.max_seat)
        self.payouts = FM.payouts(self.itm, self.fmt['payout_flat'])
        self.field_q = FLD.field_quality(self.entries, self.fmt['buyin_level'])
        self.ctx = CTX.Context()
        self.tilt = DY.Tilt()
        if tilt_state:
            self.tilt.state = dict(tilt_state)
        return self

    def pid_profiles(self):
        """pid → 프로필. **대회 전체**다.

        틸트 감쇠(dynamics.Tilt.decay_all)는 상태에 있는 모든 pid 를 훑는데
        한 핸드가 아는 프로필은 그 테이블 8명분뿐이다. 나머지는 프로필을
        못 찾아 기본 temper 로 감쇠했다 — 사람마다 다른 회복 속도가 죽는다.

        players 의 구성은 대회 중 바뀌지 않고(탈락자도 stack 0 으로 남는다)
        prof 객체도 그대로라 한 번만 만들면 된다. 길이가 달라지면(역직렬화로
        새로 채워진 경우) 다시 만든다.
        """
        m = getattr(self, '_pid_prof', None)
        if m is None or len(m) != len(self.players):
            m = self._pid_prof = {str(p['pid']): p['prof']
                                  for p in self.players.values()}
        return m

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
            field_stacks=tuple(
                p['stack'] for p in self.players.values()
                if p['stack'] > 0),
            payouts=self.payouts,
            payout_flat=self.fmt['payout_flat'],
            ante=(bb if self.level >= self.fmt['ante_from'] else 0),
            dyn=self.tilt,
            pid_prof=self.pid_profiles(),
            erosion_per_hand=CTX.erosion(self.hands_per_level,
                                         self.fmt['blind_mult']),
            reentry=self.fmt['reentry'],
            progress=CTX.progress_of(self.remaining(), self.entries),
            money_jump=CTX.money_jump_context(
                self.remaining(), self.itm, self.payouts),
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
                'leader': self.chip_leader(), 'max_seat': self.max_seat}

    # ---------- 한 핸드 ----------
    # 봇 테이블 기록. 0=끄기, 1=요약, 2=전체
    BOT_LOG = int(os.environ.get('T2_BOT_LOG', '1'))

    def _log_bot_hand(self, tb, h, run):
        """히어로 테이블 밖의 핸드도 남긴다.

        예전에는 히어로가 앉은 테이블만 아카이브했다. 그래서
        '다른 테이블에서 무슨 일이 있었나'와 봇 행동의 통계 검증이
        불가능했다. 다만 400명 x 50테이블이면 양이 크므로 기본은 요약이다.
        """
        if not self.BOT_LOG:
            return
        res = getattr(run, 'result', None) or {}
        rec = {'hand_no': self.hand_no, 'table': tb.id, 'level': self.level,
               'blinds': list(self.blinds()),
               'pids': {str(k): v for k, v in getattr(h, 'seat_pid', {}).items()},
               'pot': res.get('pot'), 'how': res.get('how'),
               'winners': res.get('winners'),
               'board': res.get('board'),
               'stacks': {str(k): v for k, v in h.stacks.items()}}
        if self.BOT_LOG >= 2:
            rec['full_log'] = res.get('full_log', [])
            rec['intents'] = getattr(h, 'intents', [])
            rec['money_jump_obs'] = getattr(h, 'money_jump_obs', [])
            rec['hole'] = {str(k): v for k, v in h.hole.items()}
        try:
            with open(_SP.path_for('bot_log', BOT_SUFFIX, D), 'a',
                      encoding='utf-8') as fp:
                fp.write(json.dumps(rec, ensure_ascii=False) + '\n')
        except OSError:
            pass

    def _play_table(self, tb, fast=True):
        """봇 전용 테이블 한 핸드. TDA 포지션을 그대로 써서 스택을 갱신한다."""
        alive = tb.ordered_alive()
        if len(alive) < 2:
            return None

        layout = tb.hand_layout()
        seats = [tb.seat_of(p['pid']) for p in alive]
        profs = {str(tb.seat_of(p['pid'])): p['prof'] for p in alive}
        stacks = {tb.seat_of(p['pid']): p['stack'] for p in alive}
        sb, bb = self.blinds()

        try:
            h = play.Hand(
                seats, profs, stacks, layout['button'], sb, bb, hero=None,
                seed=self.rng.randrange(10**9),
                position_map=layout['pos'],
                pre_seats=layout['pre_seats'],
                post_seats=layout['post_seats'],
                sb_seat=layout['sb'],
                bb_seat=layout['bb'])
            h.seat_pid = {tb.seat_of(p['pid']): p['pid'] for p in alive}
            h.table_id = tb.id
            h.table_max_seat = tb.max_seat
            self.stamp(h)
            run = SE.HandRun(h)
            run.start()
            for p in alive:
                s = tb.seat_of(p['pid'])
                p['stack'] = int(h.stacks.get(s, p['stack']))
            self._log_bot_hand(tb, h, run)
        except Exception as e:
            # 조용히 넘기지 않는다. 예전에는 return None 뿐이라
            # 봇 로직 버그가 필드 전체에서 핸드를 건너뛰게 하고도 드러나지 않았다.
            self.errors.append('%s: %s (테이블 %s, 핸드 %d)'
                               % (type(e).__name__, e, tb.id, self.hand_no))
            if len(self.errors) <= 3:
                self.notes.append('⚠ 핸드 실패 — %s: %s' % (type(e).__name__, e))
            if STRICT:
                raise
            return None
        tb.advance_button()
        tb.hands += 1
        return True

    def step_others(self, settle=True):
        """히어로 테이블 외 전 테이블을 한 핸드씩(인원 비례로 가감) 돌린다.

        settle=False 면 테이블만 돌리고 탈락 수거·밸런싱은 하지 않는다.
        이 둘은 **히어로 테이블의 최종 결과를 알아야** 한다.
          _collect_busts  busted_order 의 순서가 곧 순위다(rank_of). 다른 테이블
                          탈락을 먼저 넣으면 순위가 바뀐다.
          _balance        히어로를 다른 테이블로 옮길 수 있다. 핸드 진행 중에
                          돌면 그 핸드가 깨진다.
        그래서 '다른 테이블을 미리 돌려두는' 최적화를 하려면 이 둘만 떼어내야 한다.
        기본값은 기존 동작이다. 인자를 안 쓰면 아무것도 바뀌지 않는다.
        """
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
        if settle:
            self._collect_busts()
            self._balance()

    # ---------- 파산·밸런싱 ----------
    def _collect_busts(self):
        for p in self.players.values():
            if p['stack'] <= 0 and p['table'] is not None:
                tb = self.tables.get(p['table'])
                if tb and p in tb.players:
                    # stand가 pid의 물리 seat도 지우므로 players에서 빼기 전에 호출.
                    tb.stand(p['pid'])
                    tb.players.remove(p)
                p['table'] = None
                p['seat'] = None
                self.busted_order.append(p['pid'])

    def _balance(self, notify=True):
        """TDA식 테이블 브레이크/밸런싱.

        - Rule 11: broken-table 플레이어는 BTN/SB/BB도 받을 수 있지만
          SB와 BTN 사이 좌석에는 들어가지 않는다. 소프트웨어에서는
          2-step draw와 같은 편향 없는 결과가 되도록 후보 seat를 RNG로 뽑는다.
        - Rule 12-A: 일반 balance는 '다음 BB 예정자'가 이동하며,
          목적지는 BB가 가장 빨리 오는 worst open seat. SB는 절대 목적지가 아니다.
        """
        act = {t: tb for t, tb in self.tables.items() if tb.n() > 0}
        if not act:
            return

        need_tables = max(1, math.ceil(self.remaining()/self.max_seat))

        # ---------- 테이블 브레이크 ----------
        while len(act) > need_tables:
            small = min(act.values(), key=lambda x: (x.n(), x.id))
            movers = [p for p in small.players if p['stack'] > 0]
            self.rng.shuffle(movers)
            del self.tables[small.id]
            act = {t: tb for t, tb in self.tables.items() if tb.n() > 0}
            if not act:
                break

            for m in movers:
                # 인원수가 가장 적은 테이블들의 '허용된 빈 좌석' 전체가 seat pool.
                mn = min(tb.n() for tb in act.values())
                pool = []
                for tgt in sorted(
                        (tb for tb in act.values() if tb.n() == mn),
                        key=lambda x: x.id):
                    tgt.reconcile_next_hand()
                    seats = tgt.broken_open_seats()
                    if not seats:
                        seats = [i + 1 for i, pid in enumerate(tgt.seats)
                                 if pid is None]
                    pool.extend((tgt, s) for s in seats)

                if not pool:
                    raise RuntimeError('테이블 브레이크 좌석 풀 없음')

                tgt, seat = self.rng.choice(pool)
                small.stand(m['pid'])
                tgt.players.append(m)
                tgt.sit(m, seat)
                m['table'] = tgt.id
                tgt.reconcile_next_hand()

                if notify and m['pid'] == self.hero_pid:
                    self.hero_moves += 1
                    self.notes.append(
                        '🔄 테이블 브레이크 — 너 자리 이동 (%d번째)'
                        % self.hero_moves)

            act = {t: tb for t, tb in self.tables.items() if tb.n() > 0}

        # ---------- 인원 균등화 ----------
        for _ in range(24):
            act = {t: tb for t, tb in self.tables.items() if tb.n() > 0}
            if len(act) < 2:
                break
            big = max(act.values(), key=lambda x: (x.n(), -x.id))
            small = min(act.values(), key=lambda x: (x.n(), x.id))
            if big.n() - small.n() <= 1:
                break

            # Rule 12-A: source는 '다음 BB 예정자'.
            mover = big.next_bb_player()
            if mover is None:
                break

            # destination은 SB가 아닌 worst position.
            seat = small.worst_open_seat()
            if seat is None:
                break

            big.players.remove(mover)
            big.stand(mover['pid'])
            big.reconcile_next_hand()

            small.players.append(mover)
            small.sit(mover, seat)
            mover['table'] = small.id
            small.reconcile_next_hand()

            if notify and mover['pid'] == self.hero_pid:
                self.hero_moves += 1
                self.notes.append(
                    '🔄 테이블 밸런싱 — 너 자리 이동 (%d번째)'
                    % self.hero_moves)

        for tb in self.tables.values():
            if tb.n() > 0:
                tb.reconcile_next_hand()

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
