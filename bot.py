import bisect, random, itertools, zlib as _zlib
RANKS="23456789TJQKA"; SUITS="cdhs"
RV={r:i+2 for i,r in enumerate(RANKS)}
FULLDECK=[r+s for r in RANKS for s in SUITS]

def eval5(cs):
    """5장 평가. 반환 튜플은 바꾸지 않는다 — 비교에 그대로 쓰인다.
    아래는 같은 값을 더 적은 일로 구하는 것뿐이고, 전수 검증으로 확인한다
    (C(52,5)=2,598,960 전 조합을 예전 구현과 대조).

    예전에 하던 낭비
      - 무늬 리스트를 따로 만들고 set 으로 플러시 판정 (그냥 4번 비교하면 된다)
      - sorted(set(vs)) 로 중복 제거 (vs 가 이미 내림차순이라 한 번 훑으면 된다)
      - {v: vs.count(v)} 로 개수 세기 (5장에 O(n^2) + set 생성)
      - sorted(..., key=lambda) 로 그룹 정렬 (람다가 핸드 정산 한 번에 177만번
        불렸다. (개수, 끗수) 튜플을 그냥 내림차순 정렬하면 같은 순서다)
    """
    vs = sorted((RV[c[0]] for c in cs), reverse=True)
    s0 = cs[0][1]
    flush = (cs[1][1] == s0 and cs[2][1] == s0
             and cs[3][1] == s0 and cs[4][1] == s0)
    # vs 가 내림차순이므로 한 번 훑어 (개수, 끗수) 그룹을 만든다.
    # 이 시점의 pairs 는 끗수 내림차순이라 u 를 여기서 뽑는다.
    pairs = []
    prev = None; n = 0
    for v in vs:
        if v == prev:
            n += 1
        else:
            if prev is not None:
                pairs.append((n, prev))
            prev = v; n = 1
    pairs.append((n, prev))
    u = [p[1] for p in pairs]
    straight=0
    if len(u)==5:
        if u[0]-u[4]==4: straight=u[0]
        elif u==[14,5,4,3,2]: straight=5
    # (개수, 끗수) 내림차순 = 예전의 key=(-개수, -끗수) 와 같은 순서
    pairs.sort(reverse=True)
    shape=[p[0] for p in pairs]; ordered=[p[1] for p in pairs]
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


def _straight_high(ranks):
    if len(ranks) < 5:
        return 0
    if 14 in ranks:
        ranks = ranks | {1}
    ordered = sorted(ranks, reverse=True)
    run = 1
    for i in range(1, len(ordered)):
        run = run + 1 if ordered[i-1] - ordered[i] == 1 else 1
        if run == 5:
            return ordered[i] + 4
    return 0


def _eval_best(cs):
    """Exact best-five tuple for a valid 5–7 card set, without 21 subset evaluations."""
    counts = {}
    suits = {}
    for c in cs:
        rank = RV[c[0]]
        counts[rank] = counts.get(rank, 0) + 1
        suits.setdefault(c[1], []).append(rank)
    ranks = sorted(counts, reverse=True)
    flush = next((sorted(v, reverse=True) for v in suits.values() if len(v) >= 5), None)
    if flush:
        straight_flush = _straight_high(set(flush))
        if straight_flush:
            return (8, straight_flush)
    quads = [r for r in ranks if counts[r] == 4]
    if quads:
        return (7, quads[0], next(r for r in ranks if r != quads[0]))
    trips = [r for r in ranks if counts[r] >= 3]
    if trips:
        pairs = [r for r in ranks if r != trips[0] and counts[r] >= 2]
        if pairs:
            return (6, trips[0], pairs[0])
    if flush:
        return (5, *flush[:5])
    straight = _straight_high(set(ranks))
    if straight:
        return (4, straight)
    if trips:
        return (3, trips[0], *[r for r in ranks if r != trips[0]][:2])
    pairs = [r for r in ranks if counts[r] >= 2]
    if len(pairs) >= 2:
        return (2, *pairs[:2], next(r for r in ranks if r not in pairs[:2]))
    if pairs:
        return (1, pairs[0], *[r for r in ranks if r != pairs[0]][:3])
    return (0, *ranks[:5])


def eval7(cs):
    k = tuple(sorted(cs))
    v = _E7.get(k)
    if v is None:
        if len(_E7) >= _E7_MAX:
            _E7.clear()
        # 정렬된 k 로 조합을 만들어도 부분집합의 **집합**은 같다.
        # eval5 는 순서에 의존하지 않으므로 max 값도 같다.
        # Keep the general legacy behavior for unusual tool inputs. Production
        # hands are distinct 5–7 card sets; direct evaluation returns identical tuples.
        v = _E7[k] = (eval5(list(k)) if len(k) == 5 else
                     _eval_best(k) if 6 <= len(k) <= 7 and len(set(k)) == len(k)
                     else max(eval5(list(c)) for c in itertools.combinations(k, 5)))
    return v

def _showdown_share(hero_score, opp_scores):
    """Hero의 showdown pot share.

    heads-up tie = 1/2, 3-way tie = 1/3처럼 공동 1등 인원수로 정확히 나눈다.
    """
    opp_scores = list(opp_scores or [])
    if not opp_scores:
        return 1.0
    best = max(opp_scores)
    if hero_score > best:
        return 1.0
    if hero_score < best:
        return 0.0
    tied_opp = sum(1 for x in opp_scores if x == hero_score)
    return 1.0 / float(1 + tied_opp)


def equity(hero, board, n_opp, sims=500, seed=None):
    rng=random.Random(seed)
    dead=set(hero)|set(board)
    deck=[c for c in FULLDECK if c not in dead]
    need=5-len(board)
    share=0.0
    for _ in range(sims):
        d=rng.sample(deck, need+2*n_opp)
        b=board+d[:need]
        hs=eval7(hero+b)
        opp_scores=[]
        for i in range(n_opp):
            o=d[need+2*i:need+2*i+2]
            opp_scores.append(eval7(o+b))
        share += _showdown_share(hs, opp_scores)
    return share/max(1, sims)

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
    elif span==2: d+=0.18
    # 플랍 2장 동일 수트 = 플러시 드로우 위협
    if len(board)<=4 and m==2: d+=0.20
    return min(1.0,d)

# ---- range-aware equity ----
# 프리플랍 순서표는 하나다: pf_rank.json(preflop.PCT) — 169 클래스의 누적 콤보
# 백분위. 예전에는 레인지를 모를 때의 fallback 만 별도 공식 `_pf_score`
# (2·높은랭크+낮은랭크, 페어/수티드/갭 가점)로 1326 콤보를 줄 세웠다. 같은
# 질문("강한 순 상위 X%")에 순서가 둘이었고, 동률을 덱 순서로 깨서 같은
# 클래스가 수트에 따라 레인지 안팎으로 갈렸다(R2 PREFLOP_ORDERING_DUPLICATION,
# stage9 B1/B2 closeout 에서 PCT 하나로 통합). preflop 을 import 하면 순환이라
# 같은 데이터 파일을 직접 읽는다.
import json as _json, os as _os
_PCT = _json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                     'pf_rank.json'), encoding='utf-8'))


def _pf_class(c1, c2):
    a, b = sorted([c1, c2], key=lambda x: -RV[x[0]])
    if a[0] == b[0]:
        return a[0] + b[0]
    return a[0] + b[0] + ('s' if a[1] == b[1] else 'o')


_ALLCOMBOS=[(x,y) for i,x in enumerate(FULLDECK) for y in FULLDECK[i+1:]]
# 클래스 백분위 순, 같은 클래스 안에서는 덱 나열 순(결정적 순서).
_SCORED=sorted(_ALLCOMBOS, key=lambda t: _PCT[_pf_class(*t)])

def range_combos(pct, dead):
    """레인지를 모를 때의 fallback 레인지: preflop.PCT(pf_rank) 순서 상위 pct.

    관찰 기반 레인지와 같은 순서표를 쓴다. 누적 백분위 ≤ pct 인 클래스를
    통째로 포함한다 — 정확한 상위 pct 가 아니라 **클래스 경계 floor** 다
    (경계 클래스가 pct 를 넘기면 통째로 빠진다. 예: 0.35 → 458콤보 ≈ 34.54%).
    같은 클래스가 수트에 따라 반쪽만 들어가는 분할을 없애기 위한 의도된 계약이다.
    소비처: plan 의 빈 레인지 fallback(range_combos(0.35)),
    equity_vs_betting 의 콜러/벳 레인지.
    """
    p = float(pct)
    return [c for c in _SCORED
            if _PCT[_pf_class(*c)] <= p + 1e-12
            and c[0] not in dead and c[1] not in dead]

def _filter_pool(pool, dead=None, sort_legacy=False):
    """Filter one combo pool without discarding weighted mass.

    Legacy iterable input remains a list. Weighted dict input remains a dict.
    Dict keys are inserted in sorted order so seed/signature construction is stable.
    """
    dead = set(dead or ())
    if isinstance(pool, dict):
        out = {}
        for combo, raw_w in sorted(pool.items(), key=lambda kv: kv[0]):
            if combo[0] in dead or combo[1] in dead:
                continue
            w = float(raw_w)
            if w > 0:
                out[combo] = w
        return out
    vals = [c for c in (pool or [])
            if c[0] not in dead and c[1] not in dead]
    return sorted(vals) if sort_legacy else vals


class PreparedPool:
    """A weighted pool sorted and summed once for repeated sampling.

    Monte Carlo loops draw from the same pool hundreds of times. Sorting and
    summing the dict on every draw dominated bot think time (UI next-hand wait).
    Sampling from a PreparedPool returns exactly what _sample_pool_combo returns
    for the source dict with the same RNG state.
    """
    __slots__ = ('combos', 'uniform', 'total', 'cum')

    def __init__(self, pool):
        items = [(c, float(w)) for c, w in sorted(pool.items(), key=lambda kv: kv[0])
                 if float(w) > 0]
        self.combos = [c for c, _w in items]
        w0 = items[0][1] if items else 0.0
        self.uniform = all(abs(w - w0) <= 1e-12 for _c, w in items[1:])
        self.total = sum(w for _c, w in items)
        cum = []
        acc = 0.0
        for _c, w in items:
            acc += w
            cum.append(acc)
        self.cum = cum

    def sample(self, rng):
        if not self.combos:
            raise IndexError('cannot choose from empty weighted pool')
        if self.uniform:
            return rng.choice(self.combos)
        x = rng.random() * self.total
        i = bisect.bisect_right(self.cum, x)
        return self.combos[i] if i < len(self.combos) else self.combos[-1]


def prepare_pool(pool):
    """Weighted dict -> PreparedPool; legacy lists and prepared pools unchanged."""
    return PreparedPool(pool) if isinstance(pool, dict) else pool


def _sample_pool_combo(rng, pool):
    """Sample one combo from legacy-uniform or weighted pool.

    Legacy lists use rng.choice() exactly as before. Uniform weighted dicts also
    use rng.choice() on stable sorted support, preserving the legacy RNG path for
    an equivalent sorted list. Non-uniform dicts use one cumulative random draw.
    Callers sampling in a loop pass prepare_pool(pool) (same draws, no re-sort).
    """
    if isinstance(pool, PreparedPool):
        return pool.sample(rng)
    if not isinstance(pool, dict):
        return rng.choice(pool)
    return PreparedPool(pool).sample(rng)


def equity_vs_pools(hero, board, pools, sims=500, seed=None, audit=None):
    """Estimate showdown pot share without conflating zero wins and no samples.

    Scalar API is retained for valid estimates; None means unavailable.
    audit['complete'] is true only if every requested draw was accepted.
    Positive but insufficient samples have a diagnostic mean, never a
    decision-grade result. A zero-opponent pot is exact equity 1 (no MC).
    Uses a local RNG exclusively; audit does not consume extra draws.
    """
    pools = list(pools or [])
    requested = int(sims)
    if requested < 0:
        raise ValueError('negative MC simulation count')

    def _record(accepted, share, sum_sq, split_draws, reason):
        mean = share / accepted if accepted else None
        variance = ((sum_sq - accepted * mean * mean) / (accepted - 1)
                    if accepted > 1 else None)
        complete = reason in ('computed', 'no_opponents')
        if audit is not None:
            audit.update({
                'seed': seed, 'requested': requested, 'accepted': accepted,
                'rejected': requested - accepted if pools else 0,
                'split_pot_draws': split_draws,
                'share_sum': share, 'share_sum_sq': sum_sq,
                'sample_variance': max(0.0, variance) if variance is not None else None,
                'mean_share': mean if pools else 1.0,
                'complete': complete, 'reason': reason,
            })
        return (mean if complete and pools else
                1.0 if complete else None)

    if not pools:
        return _record(0, 0.0, 0.0, 0, 'no_opponents')
    # Never silently drop an empty opponent pool. That would turn an
    # unknown two-player showdown into known solo equity.
    if any(not p for p in pools):
        return _record(0, 0.0, 0.0, 0, 'missing_opponent_range')
    if requested == 0:
        return _record(0, 0.0, 0.0, 0, 'no_requested_samples')

    rng = random.Random(seed)
    dead = set(hero) | set(board)
    need = 5 - len(board)
    share = 0.0
    run = 0
    sum_sq = 0.0
    split_draws = 0
    prepped = [prepare_pool(p) for p in pools]
    for _ in range(requested):
        used = set(dead); opps = []; ok = True
        for pool in prepped:
            for _t in range(40):
                c = _sample_pool_combo(rng, pool)
                if c[0] not in used and c[1] not in used:
                    used.add(c[0]); used.add(c[1]); opps.append(list(c)); break
            else:
                ok = False; break
        if not ok: continue
        run += 1
        deck = [c for c in FULLDECK if c not in used]
        bd = board + rng.sample(deck, need)
        hs = eval7(hero + bd)
        opp_scores = [eval7(o + bd) for o in opps]
        result_share = _showdown_share(hs, opp_scores)
        share += result_share
        if audit is not None:
            sum_sq += result_share * result_share
            if 0.0 < result_share < 1.0:
                split_draws += 1
    reason = ('no_valid_mc_samples' if run == 0 else
              'insufficient_valid_samples' if run < requested else 'computed')
    return _record(run, share, sum_sq, split_draws, reason)


def equity_vs_range(hero, board, opp_pcts, sims=500, seed=None):
    """opp_pcts: 상대별 레인지 비율."""
    dead = set(hero) | set(board)
    return equity_vs_pools(hero, board,
                           [range_combos(p, dead) for p in opp_pcts], sims, seed)


def equity_vs_combos(hero, board, opp_ranges, sims=500, seed=None, audit=None):
    """opp_ranges: 상대별 실제 콤보 리스트 (액션으로 좁혀진 레인지).

    비율 근사 대신 추정한 레인지를 그대로 쓸 때 이걸 부른다.

    순서 정규화가 중요하다. rng.choice(pool) 는 리스트 순서에 의존하므로,
    같은 콤보 집합이라도 상류에서 순서가 달라지면 표본이 달라지고 에쿼티가 흔들린다.
    레인지는 '집합'이지 '수열'이 아니므로 정렬해서 순서를 고정한다.
    seed 도 내용에서 유도해 '같은 레인지 = 같은 추정치'를 보장한다.
    """
    dead = set(hero) | set(board)
    pools = [_filter_pool(r, dead, sort_legacy=True)
             for r in (opp_ranges or [])]
    if seed is None:
        seed = _zlib.crc32(repr((sorted(hero), tuple(board), pools, sims)).encode())
    return equity_vs_pools(hero, board, pools, sims, seed, audit=audit)


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
    # 투페어: 두 페어 중 내 카드가 들어간 페어만 내 기여다. 페어 보드에서
    # 한 페어만 보탠 손(K K 5 위 A5)은 원페어 기여이고, 보드 투페어 위 킥커
    # (K K 5 5 위 A2)는 기여 0 이다. 예전에는 7장 등급(투페어)을 그대로 반환해
    # giveup 재진입(made >= 2) 등이 보드 페어를 내 패로 읽었다(ledger L-RA09).
    if full[0] == 2:
        hero_ranks = {RV[c[0]] for c in hero}
        mine = sum(1 for pr in full[1:3] if pr in hero_ranks)
        return {0: 0, 1: 1, 2: 2}[mine]
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
            s += bluff_barrel_continuation(c, board)      # 배럴 지속성(flop/turn)
        s += bluff_nut_blocking(c, wt, mx)                # 넛 블로킹(모든 street)
        return s

    return sorted(cand, key=score, reverse=True)[:n_want]


def bluff_barrel_continuation(combo, board):
    """블러프 후보가 다음 street 로 배럴을 이어갈 근거(드로우). flop/turn 전용.

    리버에는 다음 street 가 없어 이 항을 쓰지 않는다(ledger L089).
    """
    return draw_strength(list(combo), board) * 0.08


def bluff_nut_blocking(combo, top_card_weights, max_weight):
    """블러프 후보가 상대 최상위 콤보의 카드를 얼마나 쥐고 있는가(모든 street)."""
    return sum(top_card_weights.get(x, 0) for x in combo) / (2.0*max_weight)


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
