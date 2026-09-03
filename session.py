"""제너레이터 기반 재개형 핸드 진행 + 쇼다운/사이드팟 정산 + 토너 세션."""
import random, json, os, hashlib, itertools, zlib as _zlib
import zlib as _zlib
import bot, preflop as pf, ranges as R, plan as PL, icm, dynamics as DY, runner as RU, reads as RD, gto as _GTO, persona as PS
from play import Hand, POST, PRE

D = os.path.dirname(os.path.abspath(__file__))

def best5(cards): return bot.eval7(cards)

def _cache_key(street, seat, n):
    return '%s|%s|%d' % (street, seat, n)

def award_pots(contrib, hole, board, folded, stacks, dead=0, unit=1):
    """사이드팟별로 승자에게 분배. 반환: {seat: 획득액}, 팟 내역

    dead(안테 등 데드머니)는 **메인팟에만** 얹는다.
    예전에는 각자 기여분(contrib)에 균등 분배했는데,
    100 단위 게임에서 안테를 인원수로 나누면 나눠떨어지지 않아
    스택에 51,370 같은 끝자리가 생겼다. 안테는 개인 기여가 아니라
    팟 전체에 들어가는 돈이므로 기여분을 건드리면 안 된다.
    """
    levels = sorted(set(v for v in contrib.values() if v > 0))
    won = {s: 0 for s in contrib}
    detail = []; prev = 0
    first_pot = True
    for lv in levels:
        elig_all = [s for s, v in contrib.items() if v >= lv]
        amount = (lv - prev) * len(elig_all); prev = lv
        if first_pot:
            amount += int(dead)          # 데드머니는 메인팟에만
            first_pot = False
        elig = [s for s in elig_all if s not in folded]
        if not elig:
            elig = elig_all
        if len(elig) == 1:
            winners = elig
        else:
            ranks = {s: best5(hole[s]+board) for s in elig}
            top = max(ranks.values())
            winners = [s for s in elig if ranks[s] == top]
        # 칩 단위(unit) 아래로는 쪼갤 수 없다. 실제 토너에서 300 을 둘이 나눠
        # 150 씩 갖는 일은 없다 — 나눌 수 없는 칩은 한 명에게 간다.
        u = max(1, int(unit))
        share = (amount // len(winners) // u) * u
        rem = amount - share*len(winners)
        for i, w in enumerate(winners):
            won[w] += share + (rem if i == 0 else 0)
        detail.append({'amount': amount, 'eligible': elig, 'winners': winners})
    for s, v in won.items(): stacks[s] += v
    return won, detail


class HandRun:
    """히어로 차례에 yield하고 send()로 재개하는 핸드 진행기.
       REPLAY: 이미 확정된 봇 결정은 재계산하지 않고 그대로 재생한다."""
    def __init__(self, hand, decisions=None):
        self.h = hand
        self.REPLAY = list(decisions or [])
        self.recorded = []
        self._didx = 0
        self.gen = self._run()
        self.result = None
        self._pot_at = {}          # street -> 스트리트 시작 시점 팟

    def start(self):
        try: return next(self.gen)
        except StopIteration as e: return {'done': True, 'result': self.result}

    def send(self, action, amount=0):
        try: return self.gen.send((action, amount))
        except StopIteration: return {'done': True, 'result': self.result}

    # ---------- 내부 ----------
    def _pid(self, seat):
        """관찰 장부의 키. 좌석 번호가 아니라 사람 식별자여야 테이블 간 오염이 없다.

        _run 안의 지역 람다로 두면 _finish 에서 NameError 가 나고,
        그게 except: pass 에 삼켜져 쇼다운 관찰이 통째로 유실된다. (실제로 그랬다)
        """
        h = self.h
        return h.seat_pid.get(seat, 'T%s_%s' % (getattr(h, 'table_id', 0), seat))

    def _dseed(self, seat, street, tag, extra=0):
        """결정 하나에 쓸 시드. 공유 rng 에서 뽑지 않고 상황에서 유도한다.

        h.rng 를 모든 결정이 공유하면, 어느 한 곳에서 소비 횟수가 한 번만 어긋나도
        이후 모든 결정의 난수가 밀려 같은 시드가 재현되지 않는다.
        (조건부로만 난수를 쓰는 함수가 하나만 있어도 그렇게 된다.)
        상황에서 유도하면 '같은 핸드·같은 좌석·같은 스트리트·같은 시점 = 같은 난수'가
        보장되고, 다른 결정의 소비량과 무관해진다.
        """
        h = self.h
        key = '%s|%s|%s|%s|%s' % (getattr(h, 'hash', ''), seat, street, tag, extra)
        return _zlib.crc32(key.encode())

    def _acts_of(self, seat, upto_street=None):
        """그 좌석의 포스트플랍 관측 액션 [(street, action, size_frac), ...].

        size_frac 은 그 액션 시점의 팟 대비 비율. 팟 추적이 없으면 0.0(모름)으로 둔다.
        프리플랍은 preflop_range 가 이미 반영하므로 제외한다.
        """
        out = []
        for (stt, x, a, amt) in (getattr(self, 'full_log', []) or []):
            if stt == 'preflop' or x != seat:
                continue
            pot = (self._pot_at or {}).get(stt, 0)
            sz = (amt/pot) if (pot and amt) else 0.0
            out.append((stt, a, sz))
        return out

    def _run(self):
        h = self.h
        self._before = dict(h.stacks)
        rnd = RU.Round(None, [h.seat_of[p] for p in h.PRE if p in h.seat_of], h.stacks, h.bb)
        sb_s, bb_s = h.seat_of.get('SB'), h.seat_of.get('BB')
        if sb_s: 
            pay = min(h.sb, rnd.stacks[sb_s]); rnd.stacks[sb_s] -= pay; rnd.contrib[sb_s] = pay
        ante_pot = 0
        # 안테는 포맷이 정한 레벨부터 걷는다.
        # 예전에는 ante_from 이 저장만 되고 무조건 1레벨부터 걷혔다.
        _ante = getattr(h, 'ante', None)
        if _ante is None: _ante = h.bb
        if bb_s:
            pay = min(h.bb, rnd.stacks[bb_s]); rnd.stacks[bb_s] -= pay; rnd.contrib[bb_s] = pay
            if _ante > 0:
                a = min(_ante, rnd.stacks[bb_s]); rnd.stacks[bb_s] -= a; ante_pot = a
        rnd.current = h.bb; rnd.min_raise = h.bb
        aggressor = None; limpers = []; callers = 0

        while True:
            # 살아있는 사람이 하나뿐이면 끝난 핸드다. BB 에게 액션을 물으면 안 된다.
            # (needs_action 은 '아직 액션 안 한 좌석'을 그대로 돌려주므로
            #  전원 폴드된 워크 상황에서도 BB 를 반환한다.)
            if len(rnd.live()) <= 1: break
            s = rnd.needs_action()
            if s is None: break
            pos = h.pos[s]; tc = rnd.to_call(s)
            if s == h.hero:
                act = yield {'stage': 'preflop', 'pos': pos, 'hole': h.hole[s],
                             'stacks': dict(rnd.stacks), 'contrib': dict(rnd.contrib),
                             'pot': sum(rnd.contrib.values())+ante_pot, 'tocall': tc,
                             'stack': rnd.stacks[s], 'min_raise': rnd.current+rnd.min_raise,
                             'can_raise': rnd.can_raise(s), 'log': list(rnd.log),
                             'contrib': dict(rnd.contrib), 'live': list(rnd.live()),
                             'allin': list(rnd.allin), 'hash': h.hash}
                a, amt = act
                try: rnd.apply(s, a, amt)
                except ValueError as e:
                    act = yield {'stage': 'preflop', 'error': str(e), 'pos': pos,
                                 'hole': h.hole[s], 'pot': sum(rnd.contrib.values())+ante_pot,
                                 'tocall': tc, 'stack': rnd.stacks[s],
                                 'min_raise': rnd.current+rnd.min_raise,
                                 'can_raise': rnd.can_raise(s), 'log': list(rnd.log),
                                 'hash': h.hash}
                    rnd.apply(s, act[0], act[1])
                if a in ('raise', 'allin'): aggressor = s; callers = 0
                elif a == 'call' and aggressor: callers += 1
                elif a == 'call': limpers.append(s)
                continue
            ax, _ = h.axes(s); hand = h.hole[s]; bbs = rnd.stacks[s]/h.bb
            _ck = _cache_key('pre', s, len(rnd.log))
            _cached = next((d for d in self.REPLAY if d[0] == _ck), None)
            if _cached:
                try: rnd.apply(s, _cached[1], _cached[2])
                except ValueError: rnd.apply(s, 'call' if tc > 0 else 'check')
                if _cached[1] in ('raise','allin'): aggressor = s; callers = 0
                elif _cached[1] == 'call' and aggressor: callers += 1
                continue
            _pre_len = len(rnd.log)
            try:
                # 프리플랍도 판단 층을 거친다. 액션만 내고 끝내면
                # '왜 이렇게 쳤는가'가 플랍 계획에 이어지지 않는다.
                _behind = [rnd.stacks[x]/h.bb for x in rnd.order
                           if x != s and x not in rnd.folded
                           and rnd.order.index(x) > rnd.order.index(s)] \
                    if (aggressor is None and not limpers) else None
                _obb = (rnd.current/h.bb) if aggressor is not None else 0.0
                _ordr = list(rnd.order)
                _behind_seats = ([x for x in _ordr[_ordr.index(s)+1:] if x in rnd.live()]
                                 if s in _ordr else [])
                _rlevel = max(1, sum(1 for (_, act, _) in rnd.log
                                     if act in ('raise', 'allin')))
                a, sz, _seed = PL.preflop_plan(
                    ax, pos, hand, bbs, h.rng,
                    aggressor_pos=(h.pos[aggressor] if aggressor is not None else None),
                    open_bb=_obb, n_callers=callers, n_limpers=len(limpers),
                    raise_level=_rlevel, behind_stacks=_behind,
                    tilt=h.axes(s)[1], field_q=getattr(h, 'field_q', 0.6),
                    bf=h.bf(s),
                    seats=len(h.seats), ante=(getattr(h, 'ante', h.bb) > 0),
                    field_avg_bb=((getattr(h, 'field_avg_stack', None) or 0)
                                  / max(1, h.bb)) or None,
                    erosion=getattr(h, 'erosion_per_hand', 0.0),
                    bb_chips=h.bb,
                    # 뒤에 남은 사람 / 림퍼의 추정치. 예전에는 오픈·아이소가
                    # 상대 정보를 전혀 안 받았다 — 뒤 스택은 넘어가는데
                    # 뒤 사람의 성향은 안 넘어갔다.
                    behind_est=(self._reads_for(s, _behind_seats, ax)
                                if aggressor is None and not limpers else None),
                    limper_est=(self._reads_for(s, limpers, ax)
                                if aggressor is None and limpers else None),
                    payout_flat=getattr(h, 'payout_flat', 0.0),
                    reentry=getattr(h, 'reentry', False),
                    progress=getattr(h, 'progress', 0.0),
                    opp_est=(RD.perceived_profile(
                        h.book, self._pid(s), self._pid(aggressor), ax,
                        random.Random(self._dseed(s, 'preflop', 'pfest', aggressor)))
                        if aggressor is not None and aggressor != s else None))
                h.pf_seed = getattr(h, 'pf_seed', {})
                h.pf_seed[s] = _seed
                if a == 'fold':
                    rnd.apply(s, 'fold' if tc > 0 else 'check')
                elif a == 'limp':
                    rnd.apply(s, 'call'); limpers.append(s)
                elif a == 'call':
                    rnd.apply(s, 'call'); callers += 1
                elif a == 'shove':
                    rnd.apply(s, 'allin'); aggressor = s
                else:
                    rnd.apply(s, 'raise',
                              max(RU.shape_size(h.bb*sz, ax['type'], h.rng),
                                  rnd.current + rnd.min_raise))
                    aggressor = s
                    if _seed['pf_role'] == 'defend': callers = 0
            except ValueError:
                rnd.apply(s, 'call' if tc > 0 else 'check')

        self.full_log = [('preflop', x, a, amt) for (x, a, amt) in rnd.log]
        # 프리플랍 관찰 기록
        _pid = self._pid
        seats_all = [x for x in rnd.order]
        acted = {}
        for (x, a_, _) in rnd.log:
            acted.setdefault(x, []).append(a_)
        obs_ids = [_pid(x) for x in seats_all]
        # 림프 판정: 로그를 순서대로 훑어 '아직 레이즈가 없던 시점'을 표시한다.
        # 기회를 따로 세지 않으면 얼리에서 늘 폴드하는 사람이
        # '림프 안 하는 사람'으로 잡힌다 — 그건 성향이 아니라 좁은 레인지다.
        _limped, _limp_chance = set(), set()
        _seen_raise = False
        for (x, a_, _amt) in rnd.log:
            if not _seen_raise and x not in _limp_chance:
                _limp_chance.add(x)
                if a_ == 'call':
                    _limped.add(x)
            if a_ in ('raise', 'allin'):
                _seen_raise = True
        for x in seats_all:
            acts = acted.get(x, [])
            vpip = any(a_ in ('call','raise','allin') for a_ in acts)
            pfr = any(a_ in ('raise','allin') for a_ in acts)
            # 림프 = 무저항 상태에서 콜. 기회(무저항으로 돌아온 자리)도 같이 센다.
            _limp = (x in _limped)
            _lchance = (x in _limp_chance)
            # 그 자리의 기준 오픈 폭도 같이 넘긴다. 관찰을 기준 대비로 만든다.
            _rexp = _GTO.rfi(h.pos.get(x, 'HJ'), len(h.seats), h.bbs(x),
                             getattr(h, 'ante', h.bb) > 0) if _lchance else None
            h.book.observe_preflop(obs_ids, _pid(x), vpip, pfr, _limp, _lchance, _rexp)
            # 3벳 기회/실행, 3벳 대면/폴드를 따로 센다.
            # '3벳만 많이 치는 사람'은 포스트플랍 공격형과 다른 대응이 필요하다.
            _seq = [(y, b_) for (y, b_, _) in rnd.log]
            _raises_before = 0
            _chance = _did = _faced = _folded = False
            for (y, b_) in _seq:
                if y == x:
                    if _raises_before == 1:
                        _chance = True
                        if b_ in ('raise', 'allin'): _did = True
                    elif _raises_before >= 2:
                        _faced = True
                        if b_ == 'fold': _folded = True
                if b_ in ('raise', 'allin'):
                    _raises_before += 1
            h.book.observe_3bet(obs_ids, _pid(x), _chance, _did, _faced, _folded)
            # 4벳 이상: 레이즈가 2회 있은 뒤의 액션
            _rb = 0; _c4 = _d4 = _f4 = _fd4 = False
            for (y, b_) in _seq:
                if y == x:
                    if _rb == 2:
                        _c4 = True
                        if b_ in ('raise', 'allin'): _d4 = True
                    elif _rb >= 3:
                        _f4 = True
                        if b_ == 'fold': _fd4 = True
                if b_ in ('raise', 'allin'): _rb += 1
            h.book.observe_4bet(obs_ids, _pid(x), _c4, _d4, _f4, _fd4)
        contrib = dict(rnd.contrib)
        if bb_s: contrib[bb_s] = contrib.get(bb_s, 0)          # 안테는 별도
        for k in rnd.stacks: h.stacks[k] = rnd.stacks[k]
        folded = set(rnd.folded)
        live = [x for x in rnd.order if x not in folded]
        dead = ante_pot

        if len(live) <= 1:
            self.result = self._finish(contrib, dead, folded, live, [], 'preflop')
            return

        prev = []
        for street, nc in [('flop', 3), ('turn', 4), ('river', 5)]:
            board = h.board[:nc]
            active = [x for x in live if h.stacks[x] > 0]
            if len(active) < 2: break
            order = [h.seat_of[p] for p in h.POST if p in h.seat_of and h.seat_of[p] in active]
            r2 = RU.Round(None, order, h.stacks, h.bb)
            street_aggr = aggressor          # 이 스트리트에 들어올 때의 공격자(루프 중 갱신되므로 스냅샷)
            pot_now = sum(contrib.values()) + dead
            self._pot_at[street] = pot_now      # 사이즈 비율 계산 기준
            while True:
                if len(r2.live()) <= 1: break     # 한 명만 남으면 그 스트리트는 끝
                s = r2.needs_action()
                if s is None: break
                tc = r2.to_call(s)
                if s == h.hero:
                    act = yield {'stage': street, 'board': board, 'hole': h.hole[s],
                                 'stacks': dict(r2.stacks), 'contrib': dict(r2.contrib),
                                 'pot': pot_now + sum(r2.contrib.values()), 'tocall': tc,
                                 'stack': r2.stacks[s], 'min_raise': r2.current+r2.min_raise,
                                 'can_raise': r2.can_raise(s), 'log': list(r2.log),
                                 'prior_log': list(getattr(self, 'full_log', [])),
                                 'live': r2.live(), 'contrib': dict(r2.contrib),
                                 'allin': list(r2.allin), 'hash': h.hash}
                    try: r2.apply(s, act[0], act[1])
                    except ValueError as e:
                        act = yield {'stage': street, 'error': str(e), 'board': board,
                                     'hole': h.hole[s], 'pot': pot_now+sum(r2.contrib.values()),
                                     'tocall': tc, 'stack': r2.stacks[s],
                                     'min_raise': r2.current+r2.min_raise,
                                     'can_raise': r2.can_raise(s), 'log': list(r2.log),
                                     'live': r2.live(), 'hash': h.hash}
                        r2.apply(s, act[0], act[1])
                    if act[0] in ('bet', 'raise', 'allin'): aggressor = s
                    continue
                ax, _ = h.axes(s)
                _ck = _cache_key(street, s, len(r2.log))
                _cached = next((d for d in self.REPLAY if d[0] == _ck), None)
                if _cached:
                    try: r2.apply(s, _cached[1], _cached[2])
                    except ValueError: r2.apply(s, 'call' if tc > 0 else 'check')
                    if _cached[1] in ('bet','raise','allin'): aggressor = s
                    continue
                behind = len([x for x in order if x not in r2.acted and x != s and x not in r2.folded])
                n_opp = len(r2.live())-1
                _seats, _ante = len(h.seats), (getattr(h, 'ante', h.bb) > 0)
                my_r = R.preflop_range(ax, h.pos[s], 'open' if s == aggressor else 'call',
                                       h.bbs(s), set(board), opener_pos=h.pos.get(aggressor),
                                       seats=_seats, ante=_ante)
                my_r = sorted(set(my_r))      # 순서 확정 (판단이 순서에 의존하면 안 된다)
                opp_r = []
                for o in r2.live():
                    if o == s: continue
                    oax, _ = h.axes(o)
                    # 3벳을 친 상대라면 폴라라이즈 정도를 반영한다.
                    _act_o = 'open' if o == aggressor else 'call'
                    _pol = 0.0
                    _oe = RD.perceived_profile(
                        h.book, self._pid(s), self._pid(o), ax,
                        random.Random(self._dseed(s, street, 'polar', o)))
                    if _oe:
                        _rdp = PS.read_opponent(ax, _oe)
                        _pol = _rdp.get('tb_polar', 0.0)
                        if _rdp.get('w', 0) > 0 and self._was_3bettor(o):
                            _act_o = '3bet'
                    orange = R.preflop_range(oax, h.pos[o], _act_o,
                                             h.bbs(o), set(board), opener_pos=h.pos.get(aggressor),
                                             seats=_seats, ante=_ante, polar=_pol)
                    # 관측된 포스트플랍 액션으로 레인지를 좁힌다.
                    # 이걸 빼면 상대가 무슨 행동을 했든 매 스트리트 프리플랍 레인지가 된다.
                    # 상대 레인지는 '이 사람이 인식하는 만큼'만 좁혀진다 (range_read).
                    # 인자가 둘이다. ax 는 **관찰자(나)**, _rdp 는 **행위자(상대)** 읽기.
                    # 예전에는 ax 하나만 넘겨서 자기 블러프 성향으로
                    # 상대 레인지를 좁혔다 — 자기 투사였다.
                    orange = R.perceived_range(orange, board, self._acts_of(o), ax,
                                               actor_read=_rdp if _oe else None)
                    # 쇼다운 이력이 예상보다 넓/좁았다면 추가 보정
                    orange, _note = RU.adjust_range_by_history(orange, h.dyn, o, board,
                                                              dead=set(h.hole[s])|set(board))
                    opp_r.extend(orange)
                # 레인지는 집합이지 수열이 아니다. 상류(축소·이력보정)에서 순서가
                # 흔들려도 판단이 바뀌면 안 되므로 여기서 순서를 확정한다.
                # 이걸 빼면 같은 시드가 재현되지 않는다 (rng.choice 가 순서에 의존).
                opp_r = sorted(set(opp_r))
                if not opp_r: opp_r = sorted(set(my_r))
                key = s
                if key in h.plans and street != h.plans[key].get('street_made'):
                    h.plans[key].setdefault('streets', []).append(street)
                # 주 상대를 정한다: 공격자가 있으면 그 사람, 없으면 스택이 가장 깊은 상대.
                # 계획 수립·갱신·실행이 모두 같은 상대를 봐야 하므로 분기 밖에서 만든다.
                _others = [x for x in r2.live() if x != s]
                _main = aggressor if (aggressor is not None and aggressor != s
                                      and aggressor in _others) else (
                        max(_others, key=lambda x: r2.stacks.get(x, 0)) if _others else None)
                _est = (RD.perceived_profile(h.book, _pid(s), _pid(_main), ax,
                                             random.Random(self._dseed(s, street, 'est', _main)))
                        if _main is not None else None)
                _ostk = (r2.stacks.get(_main, 0)/h.bb) if _main is not None else None
                # 계획 갱신은 update_plan 하나로 들어간다.
                # (예전에는 make/revise/refresh/river_fix/_allowed/attach 를
                #  여기서 직접 순서대로 불렀고, 그 순서 의존이 이력 유실을 만들었다)
                h.plans[key] = PL.update_plan(
                    h.plans.get(key), h.hole[s], board, my_r, opp_r, ax,
                    pot_now, r2.stacks[s], street,
                    self._dseed(s, street, 'plan', len(r2.log)),
                    n_opp, behind, prev,
                    h.POST.index(h.pos[s]) < 3, s == aggressor,
                    opp_est=_est, opp_stack_bb=_ostk, tilt=h.axes(s)[1],
                    first=(key not in h.plans or street == 'flop'),
                    pf_seed=getattr(h, 'pf_seed', {}).get(s))
                # 실제 팟은 스트리트 시작 팟 + 이번 스트리트에 들어온 칩이다.
                # pot_now 만 넘기면 봇이 팟을 실제보다 작게 보고 팟오즈를 과대 요구한다
                # (= 모든 스트리트에서 체계적 과잉 폴드). 히어로 화면(208행)은 이미 이 값을 쓴다.
                pot_live = pot_now + sum(r2.contrib.values())
                _pl = h.plans[key]
                h.intents = getattr(h, 'intents', [])
                if not any(i['street'] == street and i['seat'] == s for i in h.intents):
                    # 리뷰가 코드를 고칠 수 있으려면 '무엇을 했나'가 아니라
                    # **'그 시점에 무엇을 봤나'**가 남아야 한다.
                    # 오늘 디버깅에서 매번 없어서 막혔던 값들이다.
                    h.intents.append({
                        'street': street, 'seat': s, 'type': ax.get('type'),
                        'plan': _pl.get('plan'), 'why': _pl.get('why'),
                        'rel': _pl.get('rel'), 'eq': _pl.get('eq'),
                        'outs': _pl.get('outs'), 'made': _pl.get('made'),
                        'blocker': _pl.get('blocker'),
                        'blocker_net': _pl.get('blocker_net'),
                        'nut_adv': _pl.get('nut_adv'), 'range_adv': _pl.get('range_adv'),
                        'spr': _pl.get('spr'), 'danger': _pl.get('danger'),
                        # 계획이 언제 세워졌고 어느 스트리트에서 갱신됐나.
                        # 'refresh 가 안 돌아서 낡은 rel 로 판단'을 잡으려면 필요하다.
                        'street_made': _pl.get('street_made'),
                        'refreshed': list(_pl.get('refreshed') or []),
                        'deviations': list(_pl.get('deviations') or []),
                        # 상황 문맥. 같은 판단이 버블에서 달라지는지 본다.
                        'bf': round(h.bf(s), 3), 'tilt': h.axes(s)[1],
                        'oop': (h.POST.index(h.pos[s]) < 3),
                        'init': RU.has_initiative(s, aggressor),
                        'n_opp': n_opp, 'behind': behind,
                    })
                # --- 배팅라인 리딩: 진짜 프로필이 아니라 '내가 관찰한 추정치'로 ---
                read_val = None
                est = None
                if tc > 0 and aggressor is not None and aggressor != s:
                    est = RD.perceived_profile(h.book, _pid(s), _pid(aggressor), ax,
                                               random.Random(self._dseed(s, street, 'est2', aggressor)))
                    n_barrels = sum(1 for (stt, x, act, _) in getattr(self, 'full_log', [])
                                    if x == aggressor and act in ('bet', 'raise'))
                    n_barrels = max(1, n_barrels)
                    sz_frac = tc/max(1, pot_live)
                    read_val = PL.line_bluff_prior(est, street, n_barrels, sz_frac, board,
                                                  h.POST.index(h.pos[aggressor]) < 3)
                    h.reads_log = getattr(h, 'reads_log', [])
                    h.reads_log.append({'street': street, 'observer': s, 'target': aggressor,
                                        'est_bluff': round(est['bluff'],1),
                                        'confidence': est['confidence'], 'n': est['n'],
                                        'barrels': n_barrels, 'read': round(read_val,2)})
                # 프로브 판정: 직전 스트리트에서 공격권자가 벳하지 않았는가.
                _prev = {'turn': 'flop', 'river': 'turn'}.get(street)
                if _prev and h.plans.get(key) is not None:
                    _rows = [x for x in (getattr(self, 'full_log', []) or [])
                             if x[0] == _prev and x[1] != s]
                    h.plans[key]['opp_checked_prev'] = bool(_rows) and all(
                        x[2] in ('check', 'fold') for x in _rows)
                a2, eq, need = PL.act_with_plan(h.hole[s], board, ax, h.plans[key], pot_live, tc,
                                                r2.stacks[s], street,
                                                initiative=RU.has_initiative(s, aggressor),
                                                oop=(h.POST.index(h.pos[s]) < 3), opp_range=opp_r,
                                                bf=h.bf(s), seed=self._dseed(s, street, 'act', len(r2.log)),
                                                n_opp=n_opp, to_act_behind=behind, read=read_val,
                                                opp_est=est if tc > 0 and aggressor is not None
                                                        and aggressor != s else None)
                _tr = (h.plans.get(key) or {}).get('trace')
                if _tr:
                    for _i in h.intents:
                        if _i['street'] == street and _i['seat'] == s and 'trace' not in _i:
                            _i['trace'] = [x for x in _tr if x.get('street') == street]
                            break
                a, amt = a2
                # 어느 스트리트에서 실제로 공격했는지 기록한다 (지연 씨벳 판단에 필요).
                if a in ('bet', 'raise', 'allin'):
                    h.plans[key].setdefault('bet_streets', [])
                    if street not in h.plans[key]['bet_streets']:
                        h.plans[key]['bet_streets'].append(street)
                # 체크 후 벳을 맞은 상황이면 체크레이즈 판정.
                # r2.acted 는 풀레이즈가 나오면 {레이저} 로 초기화되므로
                # 's in r2.acted' 로 판정하면 이 분기가 절대 성립하지 않는다.
                # 이번 스트리트에 실제로 체크한 기록(r2.log)이 유일하게 옳은 근거다.
                if tc > 0 and a in ('call', 'fold'):
                    already_checked = any(x == s and act == 'check' for (x, act, _) in r2.log)
                    if already_checked and PL.checkraise_decision(
                            h.hole[s], board, ax, h.plans[key], pot_live, tc,
                            r2.stacks[s], street,
                            seed=self._dseed(s, street, 'ckr', len(r2.log)),
                            opp_est=_est):
                        a = 'raise'
                        amt = PL.checkraise_size(ax, pot_live, tc, r2.stacks[s],
                                                 board, street,
                                                 random.Random(self._dseed(s, street, 'ckrsz',
                                                                           len(r2.log))))
                        amt = min(r2.stacks[s] + r2.contrib.get(s, 0), amt + r2.contrib.get(s, 0))
                        h.plans[key].setdefault('acts', []).append('체크레이즈 실행')
                try:
                    if a in ('bet', 'raise'):
                        amt = RU.shape_size(
                            amt, ax['type'],
                            random.Random(self._dseed(s, street, 'size', len(r2.log))),
                            pot=pot_live)
                        r2.apply(s, a, max(amt, r2.current+r2.min_raise) if r2.current else amt)
                        aggressor = s
                    else: r2.apply(s, a, amt)
                except ValueError as _ve:
                    # 사이즈가 규칙에 안 맞아 거부됐다. 폴백하되 그 사실을 남긴다.
                    # 기록이 없으면 '의도는 벳인데 체크가 실행됨'이 원인 불명으로 남는다.
                    _fb = 'call' if tc > 0 else 'check'
                    h.plans[key].setdefault('deviations', []).append(
                        {'street': street, 'planned': a, 'executed': _fb,
                         'why': '사이즈 거부(%s)' % _ve})
                    a = _fb
                    r2.apply(s, a)
                if r2.log: self.recorded.append((_ck, r2.log[-1][1], r2.log[-1][2]))
                # 액션이 끝난 뒤 계획을 다시 손대지 않는다.
                # _allowed(개념 보유 검사)는 update_plan 안에서 이미 적용됐고,
                # 여기서 또 돌리면 '실행 후 계획 변경' = 사후 수정이 된다.
                _pl2 = h.plans[key]
                h.intents = getattr(h, 'intents', [])
                h.intents = [i for i in h.intents if not (i['street'] == street and i['seat'] == s)]
                h.intents.append({'street': street, 'seat': s, 'type': ax.get('type'),
                                  'action': a, 'plan': _pl2.get('plan'), 'why': _pl2.get('why'),
                                  'rel': _pl2.get('rel'), 'eq': _pl2.get('eq'),
                                  'outs': _pl2.get('outs'), 'blocker': _pl2.get('blocker')})
            _any_bet = any(_a in ('bet', 'raise', 'allin') for (_, _a, _) in r2.log)
            if not _any_bet:
                for k, v in list(h.plans.items()):
                    if v.get('plan') == 'trap':
                        h.plans[k] = PL.mark_no_bite(v)
            # 포스트플랍 관찰 기록.
            # 씨벳/배럴 '기회'는 직전 스트리트의 공격자가 이번 스트리트에서
            # 처음 액션하는 시점이고, 그때까지 아무도 베팅하지 않았어야 한다.
            # (예전엔 로그의 첫 항목인지로 판정했는데, 공격자는 보통 포지션이 있어
            #  마지막에 액션하므로 기회가 거의 잡히지 않았다 — 60핸드에 0.3회.)
            # 관찰자는 '그 핸드에 참여한 사람'이 아니라 '테이블에 앉아 있는 사람' 전원이다.
            # 폴드했어도 상대 플레이는 다 보고 있다. 생존자만 관찰자로 세면
            # 표본이 몇 배로 줄어 리딩이 성립하지 않는다.
            _ord = [_pid(x) for x in h.seats]
            _acted_once = set()
            _bet_seen = False
            for (x, a_, amt) in r2.log:
                opp_spot = (x == street_aggr and x not in _acted_once and not _bet_seen)
                is_cbet = (street == 'flop' and opp_spot)
                is_barrel = (street in ('turn', 'river') and opp_spot)
                h.book.observe_postflop(_ord, _pid(x), a_, is_cbet, is_barrel,
                                        facing_bet=_bet_seen, street=street)
                if a_ in ('bet', 'raise', 'allin'):
                    _p0 = self._pot_at.get(street, 0)
                    h.book.observe_size(_ord, _pid(x),
                                        (amt/_p0) if _p0 else 0.0, street)
                _acted_once.add(x)
                if a_ in ('bet', 'raise', 'allin'): _bet_seen = True
            self.full_log.extend(('%s' % street, x, a, amt) for (x, a, amt) in r2.log)
            for k, v in r2.contrib.items():
                contrib[k] = contrib.get(k, 0)+v
            for k in r2.stacks: h.stacks[k] = r2.stacks[k]
            folded |= set(r2.folded)
            # 이전 스트리트에서 올인한 사람도 쇼다운 자격이 있다
            allin_prev = [x for x in h.seats
                          if x not in folded and h.stacks.get(x, 0) <= 0]
            live = sorted(set(r2.live()) | set(allin_prev))
            prev = board
            if len(live) <= 1:
                # 폴드로 끝났다. **여기서 보드를 더 깔면 레빗헌트다.**
                # 예전에는 h.board(5장 전부)를 넘겨서, 턴에서 끝난 판에도
                # 리버 카드가 결과에 찍혔다.
                _r = self._finish(contrib, dead, folded, live, board, 'showdown')
                # 화면에는 그 시점 보드까지만(레빗헌트 금지).
                # 남은 카드는 리뷰용으로 별도 키에 담는다 —
                # '리버가 뭐였으면 이겼나'는 사후 분석에 필요하다.
                if len(h.board) > len(board):
                    _r['runout'] = list(h.board)
                self.result = _r
                return

        # 전원이 올인이든 리버까지 왔든, 여기까지 오면 보드가 다 깔린다.
        self.result = self._finish(contrib, dead, folded, live, h.board, 'showdown')
        return

    def _was_3bettor(self, seat):
        """이 좌석이 프리플랍에서 리레이즈(3벳 이상)를 쳤나."""
        n = 0
        for row in (getattr(self, 'full_log', []) or []):
            if row[0] != 'preflop':
                continue
            if row[2] in ('raise', 'allin'):
                n += 1
                if n >= 2 and row[1] == seat:
                    return True
        return False

    def _reads_for(self, me, seats, ax):
        """여러 좌석에 대한 추정치 목록. 관찰이 없으면 중립값이 나온다."""
        h = self.h
        out = []
        for x in (seats or []):
            if x == me:
                continue
            out.append(RD.perceived_profile(
                h.book, self._pid(me), self._pid(x), ax,
                random.Random(self._dseed(me, 'preflop', 'behind', x))))
        return out or None

    def _tilt_update(self, contrib, folded, live):
        """핸드 결과를 틸트에 반영. try/except 로 감싸지 않는다 —
        예전에는 감싸져 있어서 h.dyn 이 없어도 조용히 실패했다."""
        h = self.h
        t = getattr(h, 'dyn', None)
        if t is None or not hasattr(t, 'on_pot'):
            return
        bb = max(1, h.bb)
        # 자발적 참가(VPIP)를 따로 센다. contrib 만 보면 블라인드를 낸 것도
        # '참가'가 되어, 폴드만 하는 좌석의 연속패가 무한히 늘어난다
        # (실제로 66연패까지 갔다). 폴드는 지는 것이 아니다.
        vpip = set()
        for row in (getattr(self, 'full_log', []) or []):
            if row[0] == 'preflop' and row[2] in ('call', 'raise', 'allin'):
                vpip.add(row[1])
        for k in h.seats:
            prof = h.prof.get(str(k)) or {}
            before = self._before.get(k, h.stacks.get(k, 0))
            d = (h.stacks.get(k, 0) - before) / bb
            st0 = before / bb
            if abs(d) >= 0.5:
                t.on_pot(k, prof, d, st0)
            # 넣고 접은 팟은 별도로 센다. 같은 크기라도 자책이 붙는다.
            if k in folded and contrib.get(k, 0) > 0:
                t.on_fold_after_investing(k, prof, contrib[k]/bb, st0)
            t.on_result(k, prof, won=(d > 0), played=(k in vpip),
                        contested=(k in vpip), showdown=(k in live))
        t.decay_all(h.prof)

    def _finish(self, contrib, dead, folded, live, board, how):
        h = self.h
        # 장부 저장은 소유자(드라이버)의 책임. 여기서 전역 파일에 쓰지 않는다.
        self._before = getattr(self, '_before', dict(h.stacks))
        pot_total = sum(contrib.values())+dead
        if not any(v > 0 for v in contrib.values()) and dead == 0:
            return {'how': 'void', 'winners': [], 'pot': 0, 'showdown': False,
                    'board': board, 'stacks': dict(h.stacks), 'hash': h.hash,
                    'note': '유효 참가자 부족으로 무효'}
        if len(live) <= 1:
            w = live[0] if live else max(contrib, key=contrib.get)
            h.stacks[w] += pot_total
            self._tilt_update(contrib, folded, live)
            return {'how': 'fold', 'winners': [w], 'pot': pot_total, 'showdown': False,
                    'board': board, 'stacks': dict(h.stacks), 'hash': h.hash,
                    'full_log': getattr(self, 'full_log', []),
                    'pos': {k: v for k, v in h.pos.items()}}
        c2 = dict(contrib)          # 기여분은 그대로 둔다 (안테는 award_pots 에서 처리)
        # 쇼다운 관찰: 깐 패의 강도와 공격 여부
        try:
            import preflop as _pf
            aggr_seats = {x for (_, x, a_, _) in getattr(self, 'full_log', [])
                          if a_ in ('bet', 'raise')}
            _all = [self._pid(x) for x in h.seats]
            for sd in live:
                RD_pct = _pf.PCT[_pf.cls(h.hole[sd])]
                h.book.observe_showdown(_all, self._pid(sd), RD_pct, sd in aggr_seats)
                # 깐 패는 틸트 객체에도 남긴다. runner.adjust_range_by_history 가
                # 이걸 읽어 '이 좌석이 예상보다 넓게 깠다'를 판단한다.
                if hasattr(h, 'dyn') and hasattr(h.dyn, 'note_showdown'):
                    h.dyn.note_showdown(sd, list(h.hole[sd]))
        except Exception as _e:
            # 관찰 실패를 조용히 삼키면 장부가 안 쌓이고 리딩이 통째로 죽는다.
            h.book_errors = getattr(h, 'book_errors', [])
            h.book_errors.append('showdown: %r' % (_e,))
        won, detail = award_pots(c2, h.hole, h.board, folded, h.stacks, dead,
                                 unit=getattr(h, 'sb', 0) or 1)
        if not detail:
            return {'how': 'void', 'winners': [], 'pot': 0, 'showdown': False,
                    'board': board, 'stacks': dict(h.stacks), 'hash': h.hash}
        # dead 는 award_pots 가 메인팟에 얹어 이미 분배했다.
        # 여기서 또 주면 안테가 두 번 지급되어 칩이 늘어난다.
        self._tilt_update(contrib, folded, live)
        all_w = sorted({w for d in detail for w in d['winners']})
        return {'how': 'showdown', 'winners': all_w,
                'main_winners': detail[0]['winners'], 'pot': pot_total,
                'showdown': True, 'board': h.board, 'pots': detail,
                'hole': {s: h.hole[s] for s in live}, 'stacks': dict(h.stacks),
                'hash': h.hash, 'full_log': getattr(self, 'full_log', []),
                'pos': {k: v for k, v in h.pos.items()}}


# showdown() 은 제거했다. award_pots 가 같은 랭킹을 내부에서 계산하고
# 사이드팟까지 처리한다. 호출부가 없었다.
