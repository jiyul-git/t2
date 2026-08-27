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

def eval7(cs):
    return max(eval5(list(c)) for c in itertools.combinations(cs,5))

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

def act(hero, board, profile, pot, tocall, stack, street, n_opp=1, seed=None,
        aggr_range=None, initiative=True, oop=False):
    """returns ('fold'|'check'|'call'|'bet'|'raise', amount)
       tocall>0 이면 공격자의 양극화된 벳팅 레인지 상대로 에쿼티 산출"""
    rng=random.Random(seed)
    if tocall>0 and board:
        ar = aggr_range or (0.20, profile.get('bluff',5))
        callers=[(0.30,5)]*(n_opp-1)
        eq=equity_vs_betting(hero, board, [ar], callers, street, sims=600, seed=seed)
    elif board:
        eq=equity_vs_range(hero, board, [0.30]*n_opp, sims=500, seed=seed)
    else:
        eq=equity(hero, board, n_opp, sims=300, seed=seed)
    g=profile['gamble']; a=profile['aggr']; bl=profile['bluff']; icm=profile['icm']
    # 팟 컨트롤 성향: 규율 있고 ICM 민감하며 도박성 낮을수록 높다 (0~1)
    pc = max(0.0, min(1.0, (icm + (10-g) + (10-a)) / 30.0))
    mid = 0.42 <= eq < 0.62          # 중간 강도 = 팟 컨트롤 대상 구간
    # ICM / goal tightening
    tighten = 0.02*(icm-5)/4 + (0.03 if profile['goal']=='survive' else -0.01 if profile['goal']=='accum' else 0)
    slack = 0.04*(g-5)/4
    if tocall>0:
        need = tocall/(pot+tocall)
        thr = need + tighten - slack
        if mid and rng.random() < pc:
            return ('call', tocall) if eq >= need + tighten - slack else ('fold', 0)
        if eq >= need + 0.22 and a>=6 and rng.random() < (0.35+0.05*a)*(1-0.7*pc):
            amt=min(stack, int(round((pot+2*tocall)*rng.choice([0.9,1.1,1.3])/100.0))*100)
            return ('raise', max(amt, tocall*2))
        if eq >= thr: return ('call', tocall)
        # bluff-raise only with real bluff tendency and low equity
        if eq < 0.25 and bl>=7 and rng.random()<0.10:
            return ('raise', min(stack, int((pot+2*tocall)*1.0)))
        return ('fold',0)
    else:
        if eq >= 0.62:
            dang = board_danger(board)
            # 얇은 밸류 + 위험 보드 + 팟컨트롤 성향 → 체크백
            if eq < 0.75 and street!='river' and rng.random() < pc*(0.30+0.45*dang):
                return ('check',0)
            frac = 0.55 if profile['value']=='lead' else rng.choice([0.4,0.6,0.75])
            if eq < 0.75: frac *= (1-0.35*pc)
            if profile['value']=='xr' and street!='river' and rng.random()<0.22: return ('check',0)
            return ('bet', min(stack, int(round(pot*frac/100.0))*100))
        if mid and initiative and rng.random() < (0.45 if a>=7 else 0.20)*(1-0.85*pc):
            return ('bet', min(stack, int(round(pot*0.33/100.0))*100))
        # 블러프: 이니셔티브 없으면(=프리플랍 어그레서가 아니면) 대폭 축소.
        # OOP에서 어그레서에게 리드하는 동크벳은 더 드물다.
        bluff_freq = bl/24.0
        if not initiative: bluff_freq *= 0.30
        if oop: bluff_freq *= 0.45
        if n_opp >= 2: bluff_freq *= 0.55
        if eq<0.35 and rng.random() < bluff_freq:
            return ('bet', min(stack, int(round(pot*rng.choice([0.4,0.6])/100.0))*100))
        return ('check',0)

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
