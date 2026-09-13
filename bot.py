import random, itertools, zlib as _zlib
RANKS="23456789TJQKA"; SUITS="cdhs"
RV={r:i+2 for i,r in enumerate(RANKS)}
FULLDECK=[r+s for r in RANKS for s in SUITS]

def eval5(cs):
    vs=sorted([RV[c[0]] for c in cs],reverse=True)
    ss=[c[1] for c in cs]
    flush=len(set(ss))==1
    u=sorted(set(vs),reverse=True)
    straight=0
    if len(u)==5:
        if u[0]-u[4]==4: straight=u[0]
        elif u==[14,5,4,3,2]: straight=5
    cnt={v:vs.count(v) for v in set(vs)}
    groups=sorted(cnt.items(), key=lambda kv:(-kv[1],-kv[0]))
    shape=[g[1] for g in groups]; ordered=[g[0] for g in groups]
    if straight and flush: return (8,straight)
    if shape[0]==4: return (7,ordered[0],ordered[1])
    if shape[:2]==[3,2]: return (6,ordered[0],ordered[1])
    if flush: return (5,*vs)
    if straight: return (4,straight)
    if shape[0]==3: return (3,ordered[0],*ordered[1:])
    if shape[:2]==[2,2]: return (2,ordered[0],ordered[1],ordered[2])
    if shape[0]==2: return (1,ordered[0],*ordered[1:])
    return (0,*vs)

# ---------- 핸드 평가 캐시 ----------
# eval7 은 순수 함수다. 같은 카드 집합이면 언제 불러도 같은 튜플을 돌려준다
# (eval5 가 입력을 정렬해서 쓰고, 바깥 상태를 읽지 않는다). 그래서 캐시가
# **결과를 바꿀 수 없다** — 같은 입력에 같은 값을 돌려줄 뿐이다.
# 행동 지문으로 확인할 것: tools/fingerprint.py 값이 달라지면 이 전제가
# 깨진 것이므로 되돌린다.
#
# 왜 필요한가. 한 핸드의 정산에서 eval7 호출의 83~92% 가 **완전히 같은 카드
# 집합**의 반복이다 (실측: step_others 1회에 145,023회 호출 / 고유 24,348개,
# 한 조합이 1,231회 반복). 몬테카를로가 같은 보드에 상대 콤보만 바꿔가며
# 돌고, 레인지 정렬(ranges._ranked)과 넛 점유율(ranges._strong_share)이
# 같은 레인지×보드를 반복해서 훑기 때문이다.
# 실측 효과: 정산 3.3배, 히어로 테이블 7.0배, 값 불일치 0.
_E7 = {}
# 항목 하나가 약 226바이트다(실측). 정산 한 번의 고유 조합이 2.4만개이므로
# 6만이면 한 정산이 중간에 비워지는 일이 거의 없고 메모리는 14MB 안쪽이다.
# 비우는 것은 언제 해도 안전하다 — 순수 함수라 다시 계산하면 같은 값이 나온다.
_E7_MAX = 60000


def eval7(cs):
    k = tuple(sorted(cs))
    v = _E7.get(k)
    if v is None:
        if len(_E7) >= _E7_MAX:
            _E7.clear()
        # 정렬된 k 로 조합을 만들어도 부분집합의 **집합**은 같다.
        # eval5 는 순서에 의존하지 않으므로 max 값도 같다.
        v = _E7[k] = max(eval5(list(c)) for c in itertools.combinations(k, 5))
    return v

def equity(hero, board, n_opp, sims=500, seed=None):
    rng=random.Random(seed)
    dead=set(hero)|set(board)
    deck=[c for c in FULLDECK if c not in dead]
    need=5-len(board)
    win=tie=0
    for _ in range(sims):
        d=rng.sample(deck, need+2*n_opp)
        b=board+d[:need]
        hs=eval7(hero+b)
        best=None; nbest=0
        for i in range(n_opp):
            o=d[need+2*i:need+2*i+2]
            e=eval7(o+b)
            if best is None or e>best: best=e; nbest=1
            elif e==best: nbest+=1
        if hs>best: win+=1
        elif hs==best: tie+=1
    return (win+tie*0.5)/sims

def board_danger(board):
    """0~1. 플러시/스트레이트 완성 위협이 클수록 높다."""
    if len(board)<3: return 0.0
    d=0.0
    su={}
    for c in board: su[c[1]]=su.get(c[1],0)+1
    m=max(su.values())
    if m>=4: d+=0.55
    elif m==3: d+=0.40
    vs=sorted(set(RV[c[0]] for c in board))
    span=0
    for i in range(len(vs)):
        for j in range(i,len(vs)):
            if vs[j]-vs[i]<=4: span=max(span,j-i+1)
    if span>=4: d+=0.50
    elif span==3: d+=0.40
    elif span==2 and max(vs)-min(vs)<=4: d+=0.18
    # 플랍 2장 동일 수트 = 플러시 드로우 위협
    if len(board)<=4 and m==2: d+=0.20
    return min(1.0,d)

# ---- range-aware equity ----
def _pf_score(c1,c2):
    a,b=sorted([RV[c1[0]],RV[c2[0]]],reverse=True)
    s = a*2 + b
    if a==b: s+=22
    if c1[1]==c2[1]: s+=4
    gap=a-b
    if 0<gap<=4: s+=(5-gap)
    return s

_ALLCOMBOS=[(x,y) for i,x in enumerate(FULLDECK) for y in FULLDECK[i+1:]]
_SCORED=sorted(_ALLCOMBOS, key=lambda t:-_pf_score(*t))

def range_combos(pct, dead):
    n=int(len(_SCORED)*pct)
    return [c for c in _SCORED[:n] if c[0] not in dead and c[1] not in dead]

def equity_vs_pools(hero, board, pools, sims=500, seed=None):
    """에쿼티 몬테카를로의 유일한 구현.

    pools — 상대별 콤보 리스트. 어떻게 만들었는지는 호출자가 정한다.
    사본을 만들지 말 것. 아래 3개 진입점이 전부 여기로 온다.
    """
    pools = [p for p in (pools or []) if p]
    if not pools: return 1.0
    rng = random.Random(seed)
    dead = set(hero) | set(board)
    need = 5 - len(board)
    win = tie = run = 0
    for _ in range(sims):
        used = set(dead); opps = []; ok = True
        for pool in pools:
            for _t in range(40):
                c = rng.choice(pool)
                if c[0] not in used and c[1] not in used:
                    used.add(c[0]); used.add(c[1]); opps.append(list(c)); break
            else:
                ok = False; break
        if not ok: continue
        run += 1
        deck = [c for c in FULLDECK if c not in used]
        bd = board + rng.sample(deck, need)
        hs = eval7(hero + bd)
        best = max(eval7(o + bd) for o in opps)
        if hs > best: win += 1
        elif hs == best: tie += 1
    return (win + tie*0.5) / max(1, run)


def equity_vs_range(hero, board, opp_pcts, sims=500, seed=None):
    """opp_pcts: 상대별 레인지 비율."""
    dead = set(hero) | set(board)
    return equity_vs_pools(hero, board,
                           [range_combos(p, dead) for p in opp_pcts], sims, seed)


def equity_vs_combos(hero, board, opp_ranges, sims=500, seed=None):
    """opp_ranges: 상대별 실제 콤보 리스트 (액션으로 좁혀진 레인지).

    비율 근사 대신 추정한 레인지를 그대로 쓸 때 이걸 부른다.

    순서 정규화가 중요하다. rng.choice(pool) 는 리스트 순서에 의존하므로,
    같은 콤보 집합이라도 상류에서 순서가 달라지면 표본이 달라지고 에쿼티가 흔들린다.
    레인지는 '집합'이지 '수열'이 아니므로 정렬해서 순서를 고정한다.
    seed 도 내용에서 유도해 '같은 레인지 = 같은 추정치'를 보장한다.
    """
    dead = set(hero) | set(board)
    pools = [sorted(c for c in r if c[0] not in dead and c[1] not in dead)
             for r in (opp_ranges or [])]
    if seed is None:
        seed = _zlib.crc32(repr((sorted(hero), tuple(board), pools, sims)).encode())
    return equity_vs_pools(hero, board, pools, sims, seed)


def draw_strength(hero, board):
    """내 홀카드가 '실제로 기여하는' 드로우만 센다.
       이미 스트레이트/플러시 이상이 완성됐으면 드로우는 0.
       보드만으로 이미 성립하는 연결/수트는 내 드로우가 아니다."""
    if len(board) >= 5: return 0
    if eval7(hero + board)[0] >= 4: return 0     # 스트레이트 이상 완성
    cards = hero + board

    def flush_count(cs):
        su = {}
        for c in cs: su[c[1]] = su.get(c[1], 0)+1
        return max(su.values()) if su else 0

    def straight_outs(cs):
        """스트레이트까지 필요한 카드 수로 아웃을 센다.

        예전에는 '5칸 창 안의 서로 다른 값 개수'를 세서 갭을 무시했다.
        2-3-4-6 은 6에서 2까지 창 안에 4개가 들어가므로 오픈엔더(8아웃)로
        판정됐지만, 실제로는 5 하나만 필요한 거트샷(4아웃)이다.
        정확히 2배로 부풀려졌고, 그 값이 세미블러프 계획과 need 감산에
        그대로 들어갔다.

        반환: (아웃 장수, 완성에 필요한 최소 카드 수)
        """
        vs = set(RV[c[0]] for c in cs)
        if 14 in vs: vs = vs | {1}
        need_one = set()          # 이 값 하나가 오면 스트레이트 완성
        for lo in range(1, 11):
            win = set(range(lo, lo+5))
            miss = win - vs
            if len(miss) == 1:
                need_one |= miss
        if need_one:
            return 4*len(need_one), 1
        for lo in range(1, 11):
            win = set(range(lo, lo+5))
            if len(win - vs) == 2:
                return 0, 2
        return 0, 3

    def straight_run(cs):
        """하위호환용. 완성까지 필요한 카드 수를 등급으로 환산."""
        _, need = straight_outs(cs)
        return 5 - need

    outs = 0
    # 플러시 드로우: 내 카드를 포함해 4장이고, 보드만으로는 4장이 안 될 때
    if flush_count(cards) >= 4 and flush_count(board) < 4:
        mysuit = max({c[1] for c in cards},
                     key=lambda s: sum(1 for c in cards if c[1] == s))
        if any(c[1] == mysuit for c in hero):
            outs += 9 if flush_count(cards) == 4 else 0
    # 스트레이트 드로우: 내 카드가 런을 실제로 늘려야 한다
    # 내 카드를 넣었을 때 늘어나는 스트레이트 아웃만 센다.
    so_all, _ = straight_outs(cards)
    so_board, _ = straight_outs(board)
    gain = max(0, so_all - so_board)
    if gain:
        outs += gain if outs == 0 else gain//2       # 플러시드로우와 겹치면 절반만
    return outs

def made_strength(hero, board):
    """내 홀카드가 **실제로 기여한** 완성 강도.

    eval7(hero+board)[0] 은 7장 최고 조합이라 보드만으로 성립하는 것도 센다.
    98o 가 6s Ks Kc 보드에서 원페어(=보드의 KK)로 잡혀 '쇼다운 가치 있음'이
    되는 문제가 있었다. draw_strength 는 이미 같은 규칙을 지킨다
    ("보드만으로 성립하는 연결/수트는 내 드로우가 아니다").

    반환: 내 기여가 없으면 0, 있으면 eval7 등급.
    """
    if not board:
        return 0
    full = eval7(list(hero) + list(board))
    # 내 카드를 뺀 조합과 비교한다. 같으면 내 기여가 없다는 뜻이다.
    # 보드가 5장 미만일 땐 5장을 못 만드니, 보드가 만들 수 있는
    # 최고 등급(페어/트립스 등)만 따져서 비교한다.
    if len(board) >= 5:
        board_best = eval7(list(board))
        # 등급(카테고리)이 같으면 내 카드는 킥커로만 얹힌 것이다.
        # 킥커까지 비교하면 98o 가 KK 보드에서 '원페어 보유'로 잡혀
        # 쇼다운 가치가 있다고 오판한다.
        if full[0] <= board_best[0]:
            return 0
        return full[0]
    ranks = [c[0] for c in board]
    cnt = {}
    for r in ranks: cnt[r] = cnt.get(r, 0) + 1
    m = max(cnt.values()) if cnt else 1
    board_cat = {1: 0, 2: 1, 3: 3, 4: 7}.get(m, 0)   # 하이/원페어/트립스/쿼드
    su = {}
    for c in board: su[c[1]] = su.get(c[1], 0) + 1
    if su and max(su.values()) >= 5: board_cat = max(board_cat, 5)
    if full[0] <= board_cat:
        return 0
    return full[0]


def _sd_strength(combo, board):
    """콤보의 '계속 가치'. 완성 강도 + 드로우 지분.

    made 강도만 쓰면 플랍의 강한 드로우가 최하위로 밀려
    레인지를 좁힐 때 통째로 지워진다. 이 함수는 그걸 막는다.
    """
    made = eval7(list(combo) + board)
    if len(board) >= 5 or len(board) == 0:
        return made
    outs = draw_strength(list(combo), board)
    if not outs:
        return made
    # 아웃 1장당 약 2% 지분. 원페어 한 단계(약 1등급) 정도로 환산해 얹는다.
    return (made[0] + min(1.8, outs * 0.11),) + tuple(made[1:])

def bluff_share(size_frac, street, bluff_axis=5.0):
    """베팅 레인지에서 블러프가 차지하는 비율.

    상수로 두면 안 된다. 균형 잡힌 베터의 블러프 비중은 사이즈에서 나온다:
    팟의 s 만큼 베팅하면 상대가 무차별해지는 블러프 지분은 s/(1+2s) 다.
      1/3 팟 → 20%,  1/2 팟 → 25%,  팟 → 33%,  1.5배 오버벳 → 37.5%
    사이즈가 클수록 블러프가 많다. 이게 '사이즈가 레인지를 의미한다'의 핵심이다.

    거기에 개인 성향을 곱한다 (bluff_axis 5 가 균형점).
    리버는 다음 스트리트가 없어 블러프를 줄이고, 플랍은 아직 배럴 여지가 있어 늘린다.
    """
    s = max(0.15, min(2.0, size_frac or 0.6))
    share = s/(1.0 + 2.0*s)                       # 균형점
    share *= max(0.35, min(1.9, bluff_axis/5.0))  # 성향 편차
    share *= {'flop': 1.15, 'turn': 1.0, 'river': 0.85}.get(street, 1.0)
    return max(0.06, min(0.55, share))


def bluff_count(n_value, size_frac, street, bluff_axis=5.0):
    """밸류 콤보 수에 맞춰 블러프 콤보 수를 낸다. share = nb/(nv+nb) 를 만족시킨다."""
    sh = bluff_share(size_frac, street, bluff_axis)
    return int(round(n_value * sh/(1.0 - sh)))


def pick_bluffs(ranked, board, street, n_want):
    """블러프 콤보를 고른다. '제일 약한 핸드'가 기준이 아니다.

    ranked — _sd_strength 내림차순으로 정렬된 콤보 리스트.

    실제로 좋은 블러프는 세 가지를 만족한다:
      1. 쇼다운 가치가 낮다 (체크해서 이길 일이 없으니 잃을 게 없다)
      2. 다음 스트리트에 배럴을 이어갈 근거가 있다 (드로우/백도어)
      3. 상대의 콜 레인지를 막는다 (블로커)

    2와 3을 무시하고 최약체만 고르면, 같은 무승부라도
    A♠5♠ 와 7♦5♣ 가 동등해진다. 실제로는 전혀 다르다.
    """
    n = len(ranked)
    if n_want <= 0 or n == 0: return []
    # 후보: 쇼다운 가치가 낮은 아래쪽 절반. 위쪽은 체크로 이길 수 있으니 제외.
    cand = ranked[max(1, n//2):]
    if len(cand) <= n_want: return cand

    # 블로커 가중치: 상대 최상위(넛) 콤보에 자주 등장하는 카드일수록 높다.
    top = ranked[:max(4, int(n*0.10))]
    wt = {}
    for c in top:
        for card in c:
            wt[card] = wt.get(card, 0) + 1
    mx = max(wt.values()) if wt else 1

    later = street in ('flop', 'turn')

    def score(c):
        s = 0.0
        if later:
            s += draw_strength(list(c), board) * 0.08     # 배럴 지속성
        s += sum(wt.get(x, 0) for x in c) / (2.0*mx)      # 넛 블로킹
        return s

    return sorted(cand, key=score, reverse=True)[:n_want]


def betting_range(board, base_pct, bluff_axis, street, dead):
    """벳/배럴을 낸 플레이어의 양극화된 레인지"""
    pool = range_combos(base_pct, dead)
    if not board: return pool
    ranked = sorted(pool, key=lambda c: _sd_strength(c, board), reverse=True)
    n = len(ranked)
    # 밸류: 스트리트가 갈수록 좁아짐
    vfrac = {'flop':0.35,'turn':0.22,'river':0.15}.get(street,0.30)
    value = ranked[:max(1,int(n*vfrac))]
    # 블러프: 가장 약한 쪽에서, 성향에 비례
    # 사이즈 정보가 없는 경로이므로 표준 사이즈(0.6팟)를 가정한다
    nb = bluff_count(len(value), 0.6, street, bluff_axis)
    return value + pick_bluffs(ranked, board, street, nb)

_EQ_CACHE={}
def _ck(*a): return repr(a)

def equity_vs_betting(hero, board, aggressors, callers, street, sims=600, seed=None):
    """aggressors/callers: [(base_pct, bluff_axis), ...]"""
    # seed 를 키에 넣지 않으면 '어떤 호출이 먼저 캐시를 채웠는가'에 따라 값이 달라지고,
    # 그 캐시가 프로세스 안에서 토너 간에 남아 재현성이 깨진다 (book.json 과 같은 계열).
    key = _ck(sorted(hero), tuple(board), tuple(aggressors), tuple(callers), street, sims)
    if key in _EQ_CACHE: return _EQ_CACHE[key]
    dead = set(hero) | set(board)
    pools = [betting_range(board, p, bl, street, dead) for p, bl in aggressors]
    pools += [range_combos(p, dead) for p, _ in callers]
    # seed 를 호출자에게서 받으면 캐시 적중 여부에 따라 값이 달라진다 —
    # 그 캐시는 프로세스 안에서 대회 간에 남으므로 같은 시드가 재현되지 않는다.
    # 스팟에서 유도한 고정 seed 를 쓰면 '같은 스팟이면 항상 같은 추정치'가 되어
    # 캐시가 있든 없든, 비워지든 말든 결과가 같다.
    # (개인별 추정 오차는 persona.calc_noise 가 따로 넣는다. 여기서 흔들 이유가 없다.)
    out = equity_vs_pools(hero, board, pools, sims, _zlib.crc32(key.encode()))
    if len(_EQ_CACHE) > 200000: _EQ_CACHE.clear()      # 장시간 세션 메모리 상한
    _EQ_CACHE[key] = out
    return out


# act() 는 제거했다. plan.act_with_plan 이 완전히 대체했고 호출부가 없었다.
# 두 벌을 남기면 '어느 쪽이 진짜 봇 행동인가'가 불명확해진다.
