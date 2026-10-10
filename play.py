"""핸드 하나를 끝까지 진행한다. 히어로가 있으면 그 차례에서 멈춘다."""
import random, json, os, hashlib
import bot, preflop as pf, ranges as R, plan as PL, icm, dynamics as DY, runner as RU

import table as _TB
import persona as PS
from table import SEAT_ORDER as ORDER
from table import PRE_ORDER as PRE, POST_ORDER as POST   # 단일 출처 재수출 (8맥스 기본)

class Hand:
    def __init__(self, seats, profiles, stacks, button, sb, bb, hero=None,
                 payouts=None, seed=None, dyn=None, book=None,
                 position_map=None, pre_seats=None, post_seats=None,
                 sb_seat=None, bb_seat=None):
        self.rng = random.Random(seed if seed is not None else os.urandom(8))
        self.all_seats = list(seats)
        self.stacks = dict(stacks)
        self.busted = [s for s in seats if self.stacks.get(s, 0) <= 0]
        self.seats = [s for s in seats if self.stacks.get(s, 0) > 0]
        if len(self.seats) < 2:
            raise ValueError('생존 좌석 부족: %s' % self.seats)
        self.prof = profiles
        self.sb, self.bb = sb, bb; self.hero = hero
        self.payouts = payouts or []
        # 예전에는 dict 였고 tourney 가 안 넘겨서 매 핸드 새로 만들어졌다.
        # 그래서 틸트가 핸드를 못 넘겼다(live 경로만 JSON 으로 유지됐다).
        self.dyn = dyn if dyn is not None else DY.Tilt()
        self.log = []; self.plans = {}
        import reads as _RD
        # 장부는 호출자가 소유한다. 주지 않으면 이 핸드 한정 빈 장부를 쓴다.
        # 디스크에서 무조건 읽으면 대회·세션이 서로 오염되고 같은 시드가 재현되지 않는다.
        self.book = book if book is not None else _RD.Book()

        if position_map is not None:
            # 토너먼트 필드 경로. BTN/SB는 dead seat일 수 있으므로
            # '버튼이 반드시 생존자'라는 단일테이블 가정을 쓰지 않는다.
            self.button = button
            self.pos = {int(k): v for k, v in dict(position_map).items()}
            if set(self.pos) != set(self.seats):
                raise ValueError(
                    '포지션 좌석 불일치: pos=%s live=%s'
                    % (sorted(self.pos), sorted(self.seats)))
            self.seat_of = {v: k for k, v in self.pos.items()}
            self.pre_seats = [s for s in list(pre_seats or [])
                              if s in self.pos]
            self.post_seats = [s for s in list(post_seats or [])
                               if s in self.pos]
            if set(self.pre_seats) != set(self.seats):
                raise ValueError('프리플랍 액션 순서 불일치: %s' % self.pre_seats)
            if set(self.post_seats) != set(self.seats):
                raise ValueError('포스트플랍 액션 순서 불일치: %s' % self.post_seats)
            self.PRE = [self.pos[s] for s in self.pre_seats]
            self.POST = [self.pos[s] for s in self.post_seats]
            self.sb_seat = sb_seat
            self.bb_seat = bb_seat
        else:
            # legacy 단일테이블 경로는 기존 moving-button 의미를 그대로 유지한다.
            if button not in self.seats:
                idx = seats.index(button)
                for k in range(1, len(seats)+1):
                    cand = seats[(idx+k) % len(seats)]
                    if cand in self.seats:
                        button = cand
                        break
            self.button = button
            n = len(self.seats)
            i = self.seats.index(button)
            order, self.PRE, self.POST = _TB.orders(n)
            self.pos = {self.seats[(i+k) % n]: order[k] for k in range(n)}
            self.seat_of = {v: k for k, v in self.pos.items()}
            self.pre_seats = [self.seat_of[p] for p in self.PRE if p in self.seat_of]
            self.post_seats = [self.seat_of[p] for p in self.POST if p in self.seat_of]
            self.sb_seat = self.seat_of.get('SB')
            self.bb_seat = self.seat_of.get('BB')

        self._start_stacks = dict(self.stacks)
        self.seat_pid = {}          # 좌석번호 → 플레이어 고유 ID (드라이버가 채운다)
        self.deal()

    def pid_of(self, s):
        """좌석 → 플레이어 식별자. **대회 단위로 유지되는 상태의 유일한 키다.**

        좌석 번호는 테이블마다 1..8 로 겹친다. 그걸 키로 쓰면 서로 다른
        테이블의 다른 사람이 같은 상태를 공유한다 (틸트·쇼다운 기록이 실제로
        그랬다). 리딩 장부는 이미 이 변환을 거치고 있었고 틸트만 빠져 있었다.

        seat_pid 를 안 채우는 단일 테이블 드라이버는 테이블 id 를 섞어
        적어도 테이블끼리는 겹치지 않게 한다.
        """
        return self.seat_pid.get(s, 'T%s_%s' % (getattr(self, 'table_id', 0), s))

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

    def base_profile(self, s):
        """Emotion-free persona view.

        This is the future execution boundary.  It is additive plumbing only:
        production still enters strategy through axes()/planning_profile below.
        """
        p = self.prof[str(s)]
        base = dict(p)
        base.setdefault('tilt', 3)
        base.setdefault('goal', 'accum')
        return base

    def emotion_level(self, s):
        return (self.dyn.level(self.pid_of(s))
                if hasattr(self.dyn, 'level') else 0.0)

    def planning_profile(self, s):
        """Persona view allowed to include current emotion/tilt."""
        base = self.base_profile(s)
        t = self.emotion_level(s)
        return PS.tilted_view(base, t), round(t, 2)

    def execution_profile(self, s):
        """Emotion-free view reserved for pure execution.

        No current action consumer is switched to this method in the plumbing
        phase; doing so would be the F7-C behavior activation.
        """
        return self.base_profile(s)

    def profile_views(self, s):
        """Explicit F7-C boundary bundle for audit/tests."""
        planning, tilt = self.planning_profile(s)
        return {
            'base': self.base_profile(s),
            'planning': planning,
            'execution': self.execution_profile(s),
            'tilt': tilt,
        }

    def axes(self, s):
        """Current production strategy entry point.

        Behavior is intentionally unchanged: axes still returns the same tilted
        planning view as before.  F7-C activation later decides which consumers
        move to execution_profile().
        """
        return self.planning_profile(s)

    def bf_details(self, s):
        """BF and its evidence label; never claim exact ICM for a partial field.

        Full-field chip stacks are stamped by fieldsim from a hand-start
        snapshot; the table alone cannot stand in for a split tournament.
        The 5번 decision layer still consumes the same numeric BF interface.
        """
        rem = getattr(self, 'field_remaining', None)
        itm = getattr(self, 'field_itm', None)
        if not rem or not itm:
            return {'value': 1.0, 'method': 'unavailable_tournament_context',
                    'is_exact': False, 'reason': 'missing_remaining_or_itm'}
        live = [x for x in self.seats if self.stacks[x] > 0]
        if len(live) < 2 or s not in live:
            return {'value': 1.0, 'method': 'not_applicable',
                    'is_exact': False, 'reason': 'seat_not_active_or_no_opponent'}
        stacks = [self.stacks[x] for x in live]
        idx = live.index(s)
        pays = getattr(self, 'payouts', None) or [100, 62, 44, 34, 27, 22, 18, 15, 12]
        flat = getattr(self, 'payout_flat', 0.0)
        favg = getattr(self, 'field_avg_stack', None) or (sum(stacks)/len(stacks))
        start = getattr(self, '_start_stacks', {}) or {}
        # A frozen field-wide snapshot is from hand start. Do not compare
        # changed local stack amounts to a different valuation epoch.
        same_epoch = all(
            float(self.stacks[x]) == float(start.get(x, self.stacks[x]))
            for x in live)
        ids = getattr(self, 'seat_pid', {}) or {}
        local_pids = (
            [ids[x] for x in live] if all(x in ids for x in live)
            else None)
        # The caller must prove freshness of *every* survivor, not only
        # local _start_stacks. Transient Field.owner is the actual live
        # roster in the same process / worker that owns this HandRun.
        owner = getattr(self, '_field_epoch_owner', None)
        expected_id = getattr(self, 'field_snapshot_id', None)
        observed_id = None
        epoch_status = None
        scope = getattr(self, 'field_snapshot_scope', None)
        if owner is not None and expected_id:
            live_pid = {
                p['pid']: p['stack']
                for p in owner.players.values() if p['stack'] > 0}
            epoch_hand = getattr(self, 'field_snapshot_hand_no', None)
            epoch_level = getattr(self, 'field_snapshot_level', None)
            observed_id = icm.field_epoch_id(
                live_pid, epoch_hand, epoch_level)
            same_tournament_clock = (
                getattr(owner, 'hand_no', None) == epoch_hand
                and getattr(owner, 'level', None) == epoch_level)
            if (scope == 'simultaneous_frozen'
                    and getattr(owner, '_frozen_field', None) is not None
                    and getattr(owner, '_frozen_field', None)
                        is getattr(self, '_field_frozen_epoch_ref', None)
                    and getattr(self, '_field_frozen_epoch_ref', {}).get('epoch_id')
                        == expected_id):
                # Always mark a simultaneous common-round snapshot as
                # historical reference, even if this particular worker has
                # not yet received any other table's completed hand. This
                # keeps both sequential and parallel runs truthful and
                # gives the same BF/provenance regardless of execution order.
                epoch_status = 'frozen_epoch_reference'
            elif (same_tournament_clock and observed_id == expected_id
                    and live_pid == getattr(self, 'field_pid_stacks', None)):
                epoch_status = 'current_verified'
            else:
                epoch_status = 'stale_remote'
        details = icm.table_bf(
            stacks, idx, rem, itm, pays, flat, favg,
            field_stacks=getattr(self, 'field_stacks', None),
            field_pid_stacks=getattr(self, 'field_pid_stacks', None),
            table_pids=local_pids, snapshot_is_current=same_epoch,
            field_epoch_status=epoch_status,
            field_snapshot_id=expected_id,
            observed_field_epoch_id=observed_id,
            field_snapshot_scope=scope,
            return_details=True)
        details['snapshot_hand_no'] = getattr(
            self, 'field_snapshot_hand_no', None)
        details['snapshot_level'] = getattr(
            self, 'field_snapshot_level', None)
        return details

    def bf(self, s):
        """Numeric BF compatibility interface for the existing plan layer."""
        return self.bf_details(s)['value']

    # ---------- 프리플랍 ----------
