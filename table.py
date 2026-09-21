import json, os
D = os.path.dirname(os.path.abspath(__file__))
def P(f): return os.path.join(D, f)

BLINDS = [(1,100,200),(2,100,300),(3,200,400),(4,300,500),(5,300,600),(6,400,800),
          (7,500,1000),(8,600,1200),(9,800,1600),(10,1000,2000),(11,1500,3000),
          (12,2000,4000),(13,2500,5000),(14,3000,6000),(15,4000,8000),
          (16,5000,10000),(17,6000,12000),(18,8000,16000),(19,10000,20000),(20,15000,30000)]
HANDS_PER_LEVEL = 12

# ---------- 포지션 순서 (단일 출처) ----------
# 사본을 만들지 말 것. 좌석 수를 바꿀 때 여기만 고치면 되도록 유지한다.
#
# 좌석 수마다 포지션 사다리가 다르다. 라이브는 9맥스가 표준이고
# 온라인은 8맥스, 6맥스도 있다. 8맥스만 가정하면 9인 테이블에서
# 인덱스가 넘쳐 IndexError 가 난다 (실제로 그랬다).
_PRE = {
    2: ['SB','BB'],
    3: ['BTN','SB','BB'],
    4: ['UTG','BTN','SB','BB'],
    5: ['UTG','CO','BTN','SB','BB'],
    6: ['UTG','HJ','CO','BTN','SB','BB'],
    7: ['UTG','LJ','HJ','CO','BTN','SB','BB'],
    8: ['UTG','UTG+1','LJ','HJ','CO','BTN','SB','BB'],
    9: ['UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN','SB','BB'],
}

def orders(n=8):
    """좌석 수 n 의 (SEAT_ORDER, PRE_ORDER, POST_ORDER)."""
    if n == 2:
        # 헤즈업: 버튼 = SB.
        # 프리플랍은 버튼/SB 선액션, 포스트플랍은 BB 선액션.
        return ['SB','BB'], ['SB','BB'], ['BB','SB']
    if n not in _PRE:
        raise ValueError('지원하지 않는 좌석 수: %s (2~9만 가능)' % n)
    pre = _PRE[n]
    post = pre[-2:] + pre[:-2]              # SB, BB 가 먼저
    seat = ['BTN','SB','BB'] + [x for x in pre if x not in ('BTN','SB','BB')]
    return seat, list(pre), post

SEAT_ORDER, PRE_ORDER, POST_ORDER = orders(8)   # 기본값(하위호환)

class Table:
    def __init__(self, path='table_state.json'):
        self.path = P(path)
        self.s = json.load(open(self.path, encoding='utf-8')) if os.path.exists(self.path) else None

    def new(self, seats, hero, start_stack, button, hand_no=1, level=1, field=None):
        self.s = {'seats': list(seats), 'hero': hero,
                  'stacks': {str(x): start_stack for x in seats},
                  'button': button, 'hand_no': hand_no, 'level': level,
                  'pot': 0, 'committed': {}, 'field': field or {},
                  'busted': [], 'history': []}
        self.save(); return self.s

    def save(self): json.dump(self.s, open(self.path, 'w', encoding='utf-8'), indent=1)

    # --- 블라인드 ---
    def blinds(self):
        lv = min(self.s['level'], len(BLINDS))
        _, sb, bb = BLINDS[lv-1]
        return sb, bb, bb          # sb, bb, BB안테(=1BB)

    def level_for_hand(self, n): return min(1 + (n-1)//HANDS_PER_LEVEL, len(BLINDS))

    # --- 포지션 ---
    ORDER = SEAT_ORDER
    POST  = POST_ORDER

    def alive(self): return [x for x in self.s['seats'] if self.s['stacks'][str(x)] > 0]

    def posmap(self):
        a = self.alive(); n = len(a)
        i = a.index(self.s['button'])
        order, _, _ = orders(n)
        return {a[(i+k) % n]: order[k] for k in range(n)}

    def street_order(self, live_positions):
        _, _, post = orders(len(self.alive()))
        return [p for p in post if p in live_positions]

    def rotate_button(self):
        a = self.alive()
        i = a.index(self.s['button']) if self.s['button'] in a else 0
        self.s['button'] = a[(i+1) % len(a)]

    # --- 칩 이동 ---
    def post(self, seat, amt):
        k = str(seat); amt = min(amt, self.s['stacks'][k])
        self.s['stacks'][k] -= amt
        self.s['committed'][k] = self.s['committed'].get(k, 0) + amt
        self.s['pot'] += amt
        return amt

    def reset_committed(self): self.s['committed'] = {}

    def award(self, seat, amt=None):
        amt = self.s['pot'] if amt is None else amt
        self.s['stacks'][str(seat)] += amt
        self.s['pot'] -= amt

    def sidepots(self, contribs):
        """contribs: {seat: total_invested}. -> [(amount, [eligible seats])]"""
        levels = sorted(set(v for v in contribs.values() if v > 0))
        pots = []; prev = 0
        for lv in levels:
            elig = [s for s, v in contribs.items() if v >= lv]
            pots.append(((lv - prev) * len(elig), elig)); prev = lv
        return pots

    def bb(self, seat): 
        _, _, _ = self.blinds()
        return round(self.s['stacks'][str(seat)] / self.blinds()[1], 1)

    def bust_check(self):
        out = [s for s in self.s['seats'] if self.s['stacks'][str(s)] <= 0 and s not in self.s['busted']]
        for s in out: self.s['busted'].append(s)
        return out
