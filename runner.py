"""통합 핸드 진행기. 모든 의사결정은 좌석의 타입/축에서 파생된다."""
import json, os, random, hashlib
import bot, preflop as pf, ranges as R, plan as PL, icm, dynamics as DY
from table import Table

D = os.path.dirname(os.path.abspath(__file__))
def P(f): return os.path.join(D, f)

# ---------- 타입별 사이징 시그니처 ----------
import archetypes as A
FAMILY_SIG = {
    'reg':    dict(jitter=0.05, round_to=100, odd=0.02, open_mult=1.00),
    'nit':    dict(jitter=0.03, round_to=100, odd=0.00, open_mult=1.00),
    'fish':   dict(jitter=0.26, round_to=500, odd=0.32, open_mult=1.25),
    'maniac': dict(jitter=0.18, round_to=100, odd=0.15, open_mult=1.25),
    'tilt':   dict(jitter=0.22, round_to=100, odd=0.20, open_mult=1.20),
    'live':   dict(jitter=0.20, round_to=500, odd=0.28, open_mult=1.15),
}
def _sig(t):
    fam = A.ARCHETYPES[t][6] if t in A.ARCHETYPES else 'reg'
    return FAMILY_SIG[fam]
class _SigMap(dict):
    def __getitem__(self, k): return _sig(k)
SIZING_SIG = _SigMap()

def shape_size(amount, ptype, rng, pot=None):
    """타입별 사이징 버릇을 입힌다. 피쉬는 팟 무관 라운드 넘버를 즐겨 쓴다."""
    sig = SIZING_SIG[ptype]
    a = amount * (1 + rng.uniform(-sig['jitter'], sig['jitter']))
    if rng.random() < sig['odd'] and pot:
        a = pot * rng.choice([0.33, 0.5, 1.0, 1.5])      # 감으로 치는 사이즈
    r = sig['round_to']
    return max(r, int(round(a / r)) * r)

# ---------- 베팅 라운드 ----------
class Round:
    """재레이즈·최소레이즈·올인·사이드팟을 처리하는 베팅 라운드."""
    def __init__(self, tbl, order, stacks, bb, current_bet=0, min_raise=None, contrib=None):
        self.t = tbl; self.order = list(order)
        self.stacks = dict(stacks)
        self.bb = bb
        self.current = current_bet
        self.min_raise = min_raise if min_raise is not None else bb
        self.contrib = dict(contrib or {})
        self.acted = set(); self.folded = set(); self.allin = set()
        self.incomplete = set()      # 불완전 올인을 낸 좌석
        self.last_idx = -1           # 마지막으로 액션한 좌석의 인덱스
        self.log = []

    def live(self):
        return [s for s in self.order if s not in self.folded]

    def to_call(self, seat):
        return max(0, self.current - self.contrib.get(seat, 0))

    def needs_action(self):
        """마지막 액션자 다음 자리부터 시계방향으로 훑는다."""
        n = len(self.order)
        for k in range(1, n+1):
            i = (self.last_idx + k) % n
            s = self.order[i]
            if s in self.folded or s in self.allin: continue
            if s not in self.acted: return s
            if self.to_call(s) > 0: return s
        return None

    def _only_incomplete(self, seat):
        """이 좌석이 마지막으로 액션한 뒤 불완전 올인만 있었는가.
           True면 레이즈 권리 없음(콜/폴드만)."""
        return bool(self.incomplete)

    def can_raise(self, seat):
        """불완전 올인만 개입한 경우 이미 액션한 좌석은 레이즈 불가."""
        if seat not in self.acted: return True
        return not self.incomplete

    def apply(self, seat, action, amount=0):
        """action: fold/check/call/bet/raise/allin. 규칙 검증 포함."""
        tc = self.to_call(seat); st = self.stacks[seat]
        if action == 'fold':
            if tc <= 0:
                # 콜 비용이 없으면 폴드할 이유가 없다. 체크로 처리.
                action = 'check'
            else:
                self.folded.add(seat)
        elif action in ('check',):
            if tc > 0: raise ValueError('체크 불가: 콜 비용 %d' % tc)
        elif action == 'call':
            pay = min(tc, st)
            self.stacks[seat] -= pay; self.contrib[seat] = self.contrib.get(seat, 0) + pay
            if self.stacks[seat] == 0: self.allin.add(seat)
        elif action in ('bet', 'raise', 'allin'):
            target = amount if action != 'allin' else self.contrib.get(seat, 0) + st
            total_needed = target - self.contrib.get(seat, 0)
            if action in ('bet','raise') and not self.can_raise(seat):
                raise ValueError('레이즈 불가: 불완전 올인은 액션을 재개시키지 않음 (콜/폴드만)')
            if total_needed >= st:                       # 올인
                target = self.contrib.get(seat, 0) + st
                total_needed = st
                self.allin.add(seat)
            else:
                min_target = self.current + self.min_raise if self.current > 0 else max(self.bb, self.min_raise)
                if target < min_target:
                    raise ValueError('최소 레이즈 미달: %d 이상 필요 (현재 %d, 최소증분 %d)'
                                     % (min_target, self.current, self.min_raise))
            if target > self.current:
                inc = target - self.current
                full = inc >= self.min_raise            # 풀 레이즈인가
                if full:
                    self.min_raise = inc                # 최소증분 갱신은 풀레이즈만
                    self.acted = {seat}                 # 액션 재개도 풀레이즈만
                    self.incomplete.clear()             # 풀레이즈가 나오면 권리 회복
                else:
                    # 불완전 올인: 금액만 오르고 레이즈 권리는 되살아나지 않는다.
                    # 아직 액션하지 않았거나 콜 금액이 남은 사람만 계속 액션한다.
                    self.incomplete.add(seat)
                self.current = target
            self.stacks[seat] -= total_needed
            self.contrib[seat] = self.contrib.get(seat, 0) + total_needed
        self.acted.add(seat)
        self.last_idx = self.order.index(seat)
        rec_amt = amount
        if action == 'allin' or (action in ('bet','raise') and seat in self.allin):
            rec_amt = self.contrib.get(seat, amount)
        elif action == 'call':
            rec_amt = self.contrib.get(seat, 0)
        self.log.append((seat, action, rec_amt))
        return self

    def pot_contrib(self): return dict(self.contrib)

# ---------- 계획 수정 ----------
def board_changed(prev_board, board):
    """턴/리버가 보드 성격을 근본적으로 바꿨는지."""
    if not prev_board: return False
    d0, d1 = bot.board_danger(prev_board), bot.board_danger(board)
    su = {}
    for c in board: su[c[1]] = su.get(c[1], 0) + 1
    flush_now = max(su.values()) >= 3
    su0 = {}
    for c in prev_board: su0[c[1]] = su0.get(c[1], 0) + 1
    flush_before = max(su0.values()) >= 3 if prev_board else False
    return (flush_now and not flush_before) or (d1 - d0) >= 0.30

def revise_plan(state, hero, board, my_range, opp_range, profile, pot, stack, street,
                seed, n_opp, behind, prev_board):
    if board_changed(prev_board, board):
        # 상대 추정치·틸트를 그대로 넘긴다. 예전에는 안 넘겨서
        # 보드가 바뀌는 순간 익스플로잇이 통째로 끊겼다.
        new = PL.make_plan(hero, board, my_range, opp_range, profile, pot, stack, street,
                           seed=seed, n_opp=n_opp, to_act_behind=behind,
                           opp_est=state.get('opp_est'),
                           opp_stack_bb=state.get('opp_stack_bb'))
        new['revised'] = True
        # 이전 스트리트들의 의도·이탈 기록은 계획의 이력이다. 새 계획을 세워도 유지한다.
        # (make_plan 이 새 dict 를 반환하므로 명시적으로 옮기지 않으면 사라진다)
        for k in ('intents', 'deviations', 'streets', 'refreshed', 'bet_streets'):
            if state.get(k) is not None:
                new[k] = state[k]
        return new
    return state

# ---------- 림프 팟 ----------
def has_initiative(seat, aggressor):
    """림프 팟이면 aggressor=None → 아무도 이니셔티브가 없다."""
    return aggressor is not None and seat == aggressor

# ---------- 쇼다운 히스토리 반영 ----------
def adjust_range_by_history(base_range, dyn, seat, board, dead=None):
    """그 좌석이 과거에 깐 패가 예상보다 넓었으면 레인지를 넓힌다."""
    shown = dyn.shown(seat) if hasattr(dyn, 'shown') else []
    if len(shown) < 2: return base_range, None
    # 상류(perceived_range)가 레인지를 통째로 비울 수 있다. 그 경우 아래
    # max() 가 빈 시퀀스로 터진다 — 넓힐 기준 자체가 없으므로 그대로 돌려준다.
    # (잠복 버그였다. 특정 액션 라인에서만 빈 레인지가 나와 드러나지 않았다.)
    if not base_range: return base_range, None
    import statistics
    pcts = [pf.PCT[pf.cls(h)] for h in shown[-6:] if isinstance(h, list)]
    if not pcts: return base_range, None
    med = statistics.median(pcts)
    n = len(base_range)
    if med > 0.55:
        cap = min(0.9, max(pf.PCT[pf.cls(list(c))] for c in base_range) * 1.5)
        # dead(히어로 홀카드 + 보드)를 걸러야 한다. 안 그러면 상대가 내 카드를
        # 들고 있는 콤보가 레인지에 들어가 에쿼티가 왜곡된다.
        # 주의: base_range 의 카드를 dead 로 넣으면 안 된다 — 그건 상대가 가질 수
        # 있는 카드들이지 죽은 카드가 아니다. (그렇게 하면 레인지가 통째로 비어버린다.)
        seen = set(board or []) | set(dead or [])
        wider = [c for c in R._SORTED
                 if pf.PCT[pf.cls(list(c))] <= cap
                 and c[0] not in seen and c[1] not in seen]
        return wider, '쇼다운 이력 중앙값 %.0f%% → 레인지 확대' % (med*100)
    if med < 0.15:
        return R.narrow(base_range, board, 0.6, 'top') if board else base_range[:int(n*0.6)], \
               '쇼다운 이력 중앙값 %.0f%% → 레인지 축소' % (med*100)
    return base_range, None
