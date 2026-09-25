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


def effective_allin_v1(target, actor_cap, opp_cap_max, contrib_before, pot_before):
    """final legal target이 actor 기준 사실상 올인인지 분류한다.

    **분류만** 한다. shove / leave-behind 같은 실행 방식은 호출부가 고른다.
    opponent-effective(상대가 더 짧은) 상황은 actor shove 판정에서 제외한다.

    v1 잠금:
      actor-effective
      commit >= 90%
      action 후 own SPR <= 0.05
    """
    actor_cap = max(0.0, float(actor_cap or 0))
    opp_cap_max = max(0.0, float(opp_cap_max or 0))
    contrib_before = max(0.0, float(contrib_before or 0))
    pot_before = max(0.0, float(pot_before or 0))
    target = max(0.0, float(target or 0))

    capped = min(actor_cap, target) if actor_cap > 0 else 0.0
    increment = max(0.0, capped - contrib_before)
    pot_after = pot_before + increment
    residual = max(0.0, actor_cap - capped)
    commit_frac = (capped / actor_cap) if actor_cap > 0 else 0.0
    post_spr = residual / max(1.0, pot_after)
    actor_effective = (actor_cap > 0 and opp_cap_max > 0
                       and actor_cap <= opp_cap_max + 1e-9)
    effective = (actor_effective
                 and commit_frac >= 0.90 - 1e-12
                 and post_spr <= 0.05 + 1e-12)

    return {
        'effective': bool(effective),
        'actor_effective': bool(actor_effective),
        'target_capped': capped,
        'increment': increment,
        'pot_after': pot_after,
        'residual': residual,
        'commit_frac': commit_frac,
        'post_spr': post_spr,
    }


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
        # 전략층이 문자열 'allin'을 raise로 오인하지 않도록 규칙 판정 메타를
        # 별도로 보존한다. all-in call과 full/incomplete raise는 다른 사건이다.
        self.full_raise_count = 0
        self.action_meta = []

    def live(self):
        return [s for s in self.order if s not in self.folded]

    def to_call(self, seat):
        """이 좌석이 실제로 더 낼 수 있는 콜 금액.

        current 가 상대의 스택을 초과해도 숏스택은 자기 남은 스택까지만
        콜할 수 있다. 판단층에 '낼 수도 없는 금액'을 넘기지 않는다.
        """
        raw = max(0, self.current - self.contrib.get(seat, 0))
        return min(raw, max(0, self.stacks.get(seat, 0)))

    def contestable_contrib(self, seat):
        """현재 street contrib 중 seat가 실제로 이길 수 있는 부분의 합.

        각 상대 기여분은 이 좌석의 현재 street 최대 도달 target
        (이미 낸 칩 + 남은 스택)까지만 side-pot eligibility가 있다.
        prior-street pot은 호출부가 별도로 더한다.
        """
        cap = self.contrib.get(seat, 0) + max(0, self.stacks.get(seat, 0))
        return sum(min(v, cap) for v in self.contrib.values())

    def settle_uncalled(self):
        """베팅 라운드 종료 후 유일한 최고 기여자의 미콜 초과분을 반환한다.

        folded 좌석의 이미 들어간 칩도 '상대가 실제로 낸 금액'이므로
        second-highest 계산에 포함한다. 반환된 칩 때문에 더는 물리적
        올인이 아니면 allin 표식도 해제한다.

        반환값: {'seat','amount','from','to'} 또는 None.
        """
        if not self.contrib:
            return None
        top = max(self.contrib.values())
        leaders = [s for s, v in self.contrib.items() if v == top]
        if len(leaders) != 1:
            return None
        s = leaders[0]
        others = [v for x, v in self.contrib.items() if x != s]
        matched = max(others) if others else 0
        refund = top - matched
        if refund <= 0:
            return None
        self.contrib[s] = matched
        self.stacks[s] = self.stacks.get(s, 0) + refund
        if self.stacks[s] > 0:
            self.allin.discard(s)
        self.current = max(self.contrib.values()) if self.contrib else 0
        return {'seat': s, 'amount': refund, 'from': top, 'to': matched}

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
        """이 좌석의 레이즈에 실제로 응답할 수 있는 상대가 있고 권리가 열려 있는가."""
        # 나머지 live 좌석이 전부 올인이면 추가 레이즈는 누구에게도
        # 콜될 수 없다. HU에서 상대 shove 뒤 covering stack이 더 얹는
        # 'dead raise'를 허용하면 로그/리딩/난수 경로만 오염된다.
        responder = any(
            x != seat
            and x not in self.folded
            and x not in self.allin
            and self.stacks.get(x, 0) > 0
            for x in self.order
        )
        if not responder:
            return False
        if seat not in self.acted:
            return True
        return not self.incomplete

    def apply(self, seat, action, amount=0):
        """action: fold/check/call/bet/raise/allin. 규칙 검증 포함."""
        tc = self.to_call(seat); st = self.stacks[seat]
        _pre_current = self.current
        _pre_min_raise = self.min_raise
        _pre_contrib = self.contrib.get(seat, 0)
        _input_action = action
        _raised = False
        _full_raise = False
        _incomplete_raise = False
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
            # allin도 current를 넘으면 규칙상 'raise'다. 반대로 숏스택의
            # all-in call(target <= current)은 raise 권리가 없어도 허용해야 한다.
            if target > self.current and not self.can_raise(seat):
                raise ValueError(
                    '레이즈 불가: 응답 가능한 상대가 없거나 불완전 올인으로 권리가 닫힘 '
                    '(콜/폴드만)')
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
                _raised = True
                _full_raise = bool(full)
                _incomplete_raise = not full
                if full:
                    self.full_raise_count += 1
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
        self.action_meta.append({
            'seat': seat,
            'input_action': _input_action,
            'action': action,
            'amount': rec_amt,
            'pre_contrib': _pre_contrib,
            'post_contrib': self.contrib.get(seat, 0),
            'increment': max(0, self.contrib.get(seat, 0) - _pre_contrib),
            'pre_current': _pre_current,
            'post_current': self.current,
            'pre_min_raise': _pre_min_raise,
            'raised': bool(_raised),
            'full_raise': bool(_full_raise),
            'incomplete_raise': bool(_incomplete_raise),
            # 'call' 자체가 남은 스택을 전부 소모해도 all-in call 이다.
            # 입력 문자열이 allin 인 경우만 세면 봇의 call-off가 누락된다.
            'allin_call': bool(
                not _raised and action in ('call', 'allin') and seat in self.allin),
            'full_raise_count': self.full_raise_count,
        })
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
                seed, n_opp, behind, prev_board,
                oop_vs_aggr=None, oop_legacy_abs=None, initiative=True,
                opp_ranges=None):
    if board_changed(prev_board, board):
        # 보드 변화로 계획을 다시 세워도 **현재 의사결정 문맥**을 잃으면 안 된다.
        # opp_* 는 이전 계획 snapshot에서 이어지고, 위치/initiative 세 값은
        # 현재 액션 순서에서 계산된 값을 호출자가 넘긴다.
        # blockbet은 (_oop_a and not initiative) AND gate라 둘 중 하나만 빠져도
        # 재계획 시 경로가 닫힌다 (A5 4-B paired replay에서 실제 영향 확인).
        new = PL.make_plan(hero, board, my_range, opp_range, profile, pot, stack, street,
                           seed=seed, n_opp=n_opp, to_act_behind=behind,
                           opp_est=state.get('opp_est'),
                           opp_stack_bb=state.get('opp_stack_bb'),
                           oop_vs_aggr=oop_vs_aggr,
                           oop_legacy_abs=oop_legacy_abs,
                           initiative=initiative, opp_ranges=opp_ranges)
        new['revised'] = True
        # 이전 스트리트들의 의도·이탈 기록은 계획의 이력이다. 새 계획을 세워도 유지한다.
        # (make_plan 이 새 dict 를 반환하므로 명시적으로 옮기지 않으면 사라진다)
        # plan_since 가 빠져 있었다. 보드가 크게 바뀌어 make_plan 이 재호출되면
        # 계획 시작 시점이 사라져 **예산(budget_left) 기준점이 리셋**된다.
        # update_plan 의 승계 목록과 동일하게 유지한다.
        for k in ('intents', 'deviations', 'streets', 'refreshed', 'bet_streets',
                  'executed_actions', 'plan_since', '_rsig', '_opps_sig'):
            if state.get(k) is not None:
                new[k] = state[k]
        return new
    return state

# ---------- 림프 팟 ----------
def has_initiative(seat, aggressor):
    """림프 팟이면 aggressor=None → 아무도 이니셔티브가 없다."""
    return aggressor is not None and seat == aggressor

# ---------- 쇼다운 히스토리 반영 ----------
def adjust_range_by_history(base_range, dyn, pid, board, dead=None):
    """그 **사람**이 과거에 깐 패가 예상보다 넓었으면 레인지를 넓힌다.

    키는 좌석이 아니라 플레이어 식별자다(play.Hand.pid_of). 좌석 번호는
    테이블마다 겹쳐서, 그걸로 조회하면 다른 테이블에서 깐 패를 자기가 본
    것처럼 쓰게 된다.
    """
    shown = dyn.shown(pid) if hasattr(dyn, 'shown') else []
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
