"""토너 필드 전체를 확률적으로 굴린다. 매 대회마다 탈락 곡선이 달라진다."""
import random, math

# ---------- 플레이어 풀 (다양성) ----------
import archetypes as A
import persona as PS

def field_quality(entries=100, buyin_level=1.0):
    """대회 실력 수준 0~1.4. 규모·바이인이 클수록 높다.
       이 공식의 유일한 정의. 다른 곳에서 다시 쓰지 말 것."""
    scale = min(1.0, math.log10(max(10, entries))/3.0)
    return 0.35 + 0.65*scale*buyin_level


FAMILY_BASE = {'reg': 0.30, 'nit': 0.18, 'fish': 0.32, 'maniac': 0.12,
               'tilt': 0.04, 'live': 0.04}

def pool_for(entries, buyin_level=1.0, rng=None):
    q = field_quality(entries, buyin_level)
    fam_w = {'reg': FAMILY_BASE['reg'] + 0.22*q,
             'nit': FAMILY_BASE['nit'] + 0.02*q,
             'fish': max(0.02, FAMILY_BASE['fish'] - 0.16*q),
             'maniac': max(0.01, FAMILY_BASE['maniac'] - 0.075*q),
             'tilt': FAMILY_BASE['tilt'],
             'live': max(0.01, FAMILY_BASE['live'] - 0.01*q)}
    members = {}
    for n in A.all_names():
        members.setdefault(A.ARCHETYPES[n][6], []).append(n)
    out = []
    for fam, w in fam_w.items():
        ms = members.get(fam, [])
        if not ms: continue
        for n in ms: out.append((n, w/len(ms)))
    tot = sum(p for _, p in out)
    return [(n, p/tot) for n, p in out], round(q, 2)

def draw_type(rng, entries=100, buyin_level=1.0):
    pool, _ = pool_for(entries, buyin_level)
    r = rng.random(); acc = 0
    for t, p in pool:
        acc += p
        if r <= acc: return t
    return 'TAG'

def make_player(rng, pid, avg_stack_bb, entries=100, buyin_level=1.0, aggr_bias=0.0, loose_bias=0.0):
    """개념 벡터 기반 개인 생성. 라벨이 아니라 벡터가 동작을 결정한다."""
    q = field_quality(entries, buyin_level)
    p = PS.make_player(rng, q, pid, aggr_bias=aggr_bias, loose_bias=loose_bias)
    # 합류 스택: 평균 중심 절단정규 (우측만 약간 확장). 로그정규는 꼬리가 너무 길다.
    v = rng.gauss(avg_stack_bb, avg_stack_bb*0.32)
    if v > avg_stack_bb: v = avg_stack_bb + (v - avg_stack_bb)*1.10
    p['stack_bb'] = round(max(3.0, min(avg_stack_bb*1.9, v)), 1)
    p['label'] = p['type']
    return p

# ---------- 탈락 곡선 ----------
class Field:
    """대회마다 다른 탈락 속도를 갖는다."""
    def __init__(self, entries, seed=None, itm_frac=0.15):
        self.rng = random.Random(seed)
        self.entries = entries
        self.remaining = entries
        self.itm = max(1, int(round(entries*itm_frac)))
        # 이 대회의 '성격'을 뽑는다 — 매번 다름
        self.aggression = self.rng.uniform(0.6, 1.6)   # 필드가 얼마나 난폭한가
        self.structure  = self.rng.uniform(0.7, 1.4)   # 구조가 얼마나 빠른가(터보~딥스택)
        self.variance   = self.rng.uniform(0.5, 1.8)   # 날마다의 흔들림
        self.hand_no = 0
        self.log = []

    def descriptor(self):
        a = '난폭한' if self.aggression > 1.25 else ('점잖은' if self.aggression < 0.85 else '평범한')
        s = '터보' if self.structure > 1.2 else ('딥스택' if self.structure < 0.85 else '표준')
        return '%s 필드 / %s 구조' % (a, s)

    def _base_rate(self, level):
        """레벨이 오를수록 탈락률 상승. 초반은 완만, 중반 급증, 후반 둔화."""
        x = level
        return 0.075 * (1 - math.exp(-x/2.2)) * (1 + 0.40*math.log1p(x)) + 0.012

    def step(self, level, hands=1, table_seats=8, table_busts=0):
        """핸드가 지나면 필드가 줄어든다.
           table_busts: 우리 테이블에서 실제로 파산한 인원(그만큼은 확정 반영)."""
        out_total = 0
        if table_busts:
            self.remaining = max(1, self.remaining - table_busts)
            out_total += table_busts
        for _ in range(hands):
            self.hand_no += 1
            if self.remaining <= 1: break
            rate = self._base_rate(level) * self.aggression * self.structure
            # 버블 근처에서는 급격히 느려진다
            if self.in_bubble():
                rate *= 0.28
            # 파이널 근처 둔화
            if self.remaining <= 12: rate *= 0.45
            # 우리 테이블 몫(8석)은 실제 플레이로 처리되므로 나머지 테이블만 확률 처리
            other = max(0, self.remaining - table_seats)
            lam = rate * other / 8.0 * self.rng.uniform(0.2, 1.0+self.variance)
            out = 0
            # 포아송 근사
            L = math.exp(-lam); p = 1.0; k = 0
            while p > L and k < 12:
                k += 1; p *= self.rng.random()
            out = max(0, k-1)
            out = min(out, self.remaining-1)
            self.remaining -= out
            out_total += out
            self.log.append((self.hand_no, level, self.remaining))
        return out_total

    # 버블 구간의 정의는 여기 하나뿐이다.
    # 예전에는 field.py 안에서도 1.35 와 1.2 가 따로 쓰였고
    # fieldsim.py 에 세 번째 사본이 있었다.
    BUBBLE_HI = 1.20

    def in_bubble(self, remaining=None):
        r = self.remaining if remaining is None else remaining
        return self.itm < r <= self.itm * self.BUBBLE_HI

    def avg_stack_bb(self, start_stack, bb):
        return (self.entries * start_stack / max(1, self.remaining)) / bb

    def status(self):
        return {'entries': self.entries, 'remaining': self.remaining, 'itm': self.itm,
                'to_itm': max(0, self.remaining - self.itm),
                'bubble': self.in_bubble()}


# ---------- 테이블 관리 ----------
class Tables:
    """필드 인원에 맞춰 테이블 수를 조정하고, 히어로 자리를 옮긴다."""
    def __init__(self, field, max_seats=8, hero_seat=7, seed=None):
        self.f = field; self.max = max_seats
        self.rng = random.Random(seed)
        self.hero_seat = hero_seat
        self.moves = 0
        self.last_tables = None

    def tables_needed(self):
        return max(1, math.ceil(self.f.remaining / self.max))

    def reconcile(self, current_seats, stacks, profiles, start_stack, bb,
                  empty_since=None, hand_no=0):
        """현 테이블 인원을 필드 상태에 맞춘다.
           반환: (신규 참가자 목록, 히어로 이동 여부, 안내문)"""
        notes = []
        alive = [s for s in current_seats if stacks.get(s, 0) > 0]
        need = self.max
        # 필드가 한 테이블 이하로 줄면 파이널
        if self.f.remaining <= self.max:
            need = self.f.remaining
            if len(alive) < need:
                notes.append('파이널 테이블 구성')
        newcomers = []
        empty_since = empty_since or {}
        n_empty = need - len(alive)
        if n_empty > 0 and self.f.remaining > len(alive):
            # 빈 자리가 오래될수록, 빈 자리가 많을수록 밸런싱이 빨리 온다.
            waits = [max(0, hand_no - empty_since.get(str(s), hand_no))
                     for s in current_seats if stacks.get(s, 0) <= 0]
            longest = max(waits) if waits else 0
            p_fill = min(0.55, 0.05 + 0.045*longest + 0.06*(n_empty-1))
            # 테이블 수가 줄어야 하는 시점이면 훨씬 빨라진다
            if self.f.remaining <= self.max * (self.tables_needed()) - self.max*0.5:
                p_fill = min(0.8, p_fill*1.8)
            if self.rng.random() < p_fill:
                n = min(n_empty, self.f.remaining - len(alive))
                # 한 번에 다 채우지 않는다
                n = self.rng.randint(1, max(1, n))
                avg = self.f.avg_stack_bb(start_stack, bb)
                for i in range(n):
                    newcomers.append(make_player(self.rng, 'N%d' % self.rng.randrange(1000,9999), avg))
                notes.append('%d명 합류 (테이블 밸런싱, %d핸드 만)' % (n, longest))
            else:
                notes.append('%d자리 공석 — %d명으로 진행' % (n_empty, len(alive)))
        # 히어로 이동은 '테이블 수가 줄어드는 순간'에만 판정한다
        hero_moved = False
        need_t = self.tables_needed()
        if self.last_tables is None: self.last_tables = need_t
        if need_t < self.last_tables:
            broke = self.last_tables - need_t
            # 깨진 테이블 인원이 재배치됨. 히어로가 뽑힐 확률 = 깨진 테이블 비율
            if self.rng.random() < broke/max(1, self.last_tables):
                hero_moved = True; self.moves += 1
                notes.append('테이블 브레이크로 너 자리 이동 (%d번째, 남은 테이블 %d개)'
                             % (self.moves, need_t))
            else:
                notes.append('테이블 %d개 → %d개' % (self.last_tables, need_t))
            self.last_tables = need_t
        return newcomers, hero_moved, notes

    def seat_newcomers(self, seats, stacks, profiles, newcomers, bb, axes_table):
        """실제로 좌석에 앉힌다. 빈 자리(스택 0)를 재사용."""
        empty = [s for s in seats if stacks.get(s, 0) <= 0]
        seated = []
        for p in newcomers:
            if not empty: break
            s = empty.pop(0)
            stacks[s] = int(round(p['stack_bb']*bb))
            base = p['type']
            ax = axes_table[p['label']] if p['label'] in axes_table else axes_table[base]
            profiles[str(s)] = {'type': base, 'label': p['label'],
                                'aggr': p.get('aggr') or ax[0], 'gamble': p.get('gamble') or ax[1],
                                'bluff': p.get('bluff') or ax[2], 'icm': p.get('icm') or ax[3],
                                'value': p.get('value') or ax[4], 'tilt': p.get('tilt') or 4,
                                'goal': p.get('goal') or 'accum'}
            seated.append((s, p['label'], round(p['stack_bb'])))
        return seated
