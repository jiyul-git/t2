#!/usr/bin/env python3
"""eq_delta 의 몬테카를로 분산을 측정한다. plan.py 는 수정하지 않는다.

아카이브에 opp_range 콤보가 없어 기록된 eq 를 그대로 재현할 수는 없다.
실제 홀카드/보드를 쓰되 레인지는 표준 35% 로 고정해 분산의 스케일만 잰다.
독립 스트림(현재 계측 방식)과 페어드(같은 스트림)를 나란히 잰다.
"""
import os, sys, json, random, statistics as S, collections
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path: sys.path.insert(0, D)
import bot


def eq_pair(hero, board, pool, n_opp, sims, seed, paired):
    """(eq_runout, eq_current). paired=True 면 같은 상대 표본을 공유한다."""
    dead = set(hero) | set(board)
    cand = [c for c in pool if c[0] not in dead and c[1] not in dead]
    rng = random.Random(seed)
    deck0 = [c for c in bot.FULLDECK if c not in dead]
    need = 5 - len(board)
    hs_cur = bot.eval7(hero + board)
    w1 = t1 = r1 = 0
    w2 = t2 = r2 = 0
    rng2 = rng if paired else random.Random(seed ^ 0x5bf03635)
    for _ in range(sims):
        used = set(dead); opps = []
        ok = True
        for _k in range(max(1, n_opp)):
            for _t in range(40):
                c = rng.choice(cand)
                if c[0] not in used and c[1] not in used:
                    used.add(c[0]); used.add(c[1]); opps.append(list(c)); break
            else:
                ok = False; break
        if not ok: continue
        # 현재 (보드 안 돌림)
        best = max(bot.eval7(o + board) for o in opps)
        r2 += 1
        if hs_cur > best: w2 += 1
        elif hs_cur == best: t2 += 1
        # 런아웃
        if paired:
            deck = [c for c in deck0 if c not in used]
            extra = rng.sample(deck, need) if need else []
        else:
            used2 = set(dead); opps2 = []
            bad = False
            for _k in range(max(1, n_opp)):
                for _t in range(40):
                    c = rng2.choice(cand)
                    if c[0] not in used2 and c[1] not in used2:
                        used2.add(c[0]); used2.add(c[1]); opps2.append(list(c)); break
                else:
                    bad = True; break
            if bad: continue
            deck = [c for c in deck0 if c not in used2]
            extra = rng2.sample(deck, need) if need else []
            opps = opps2
        full = board + extra
        hs = bot.eval7(hero + full)
        bst = max(bot.eval7(o + full) for o in opps)
        r1 += 1
        if hs > bst: w1 += 1
        elif hs == bst: t1 += 1
    e1 = (w1 + 0.5*t1)/r1 if r1 else 0.0
    e2 = (w2 + 0.5*t2)/r2 if r2 else 0.0
    return e1, e2


def W(i): return i['why'] if isinstance(i['why'], list) else [i['why']]
def this_street(i, frag):
    pre = '%s: ' % i['street']
    return any(x.startswith(pre) and frag in x for x in W(i))


def main():
    path = os.path.join(D, 'collected.jsonl')
    rows = []
    for l in open(path):
        r = json.loads(l)
        for i in r.get('intents', []):
            if i.get('eq_current') is None: continue
            if not this_street(i, '쇼다운 가치 없고'): continue
            hole = r['hole'].get(str(i['seat']))
            if not hole: continue
            n = {'flop':3,'turn':4,'river':5}[i['street']]
            bd = list(r['board'])[:n]
            if len(bd) < 3: continue
            i['_hole']=hole; i['_bd']=bd; i['_h']=r['hand_no']
            rows.append(i)

    def grp(i):
        a = i['outs'] >= 4; b = i['eq_delta'] >= 0.20
        return 'B only' if (b and not a) else ('control' if (not a and not b) else 'other')

    bo = [i for i in rows if grp(i)=='B only']
    ct = [i for i in rows if grp(i)=='control' and i['street']=='flop']
    random.Random(7).shuffle(ct); ct = ct[:24]
    print('B only %d건 · 대조군 %d건 (플랍만)' % (len(bo), len(ct)))
    print()

    SEEDS = 12
    for mode, paired in (('독립 스트림 (현재 계측 방식)', False), ('페어드 (같은 표본)', True)):
        print('=' * 74)
        print(mode)
        print('=' * 74)
        print('%-10s %6s %8s %8s %8s %9s' % ('group','n','mean Δ','sd Δ','sd(단건)','95% 폭'))
        print('-' * 74)
        for name, sub in (('B only', bo), ('control', ct)):
            per_sd = []; means = []
            for i in sub:
                pool = bot.range_combos(0.35, set(i['_hole'])|set(i['_bd']))
                ds = []
                for k in range(SEEDS):
                    e1, e2 = eq_pair(i['_hole'], i['_bd'], pool,
                                     max(1, i.get('n_opp',1)), 400, 1000+k*7919, paired)
                    ds.append(e1 - e2)
                per_sd.append(S.stdev(ds))
                means.append(S.mean(ds))
            gm = S.mean(means); gsd = S.stdev(means)
            msd = S.mean(per_sd)
            print('%-10s %6d %8.3f %8.3f %8.3f %9.3f' % (
                name, len(sub), gm, gsd, msd, 1.96*msd))
        print()

    print('=' * 74)
    print('참고 — 기록된 값 (실제 opp_range 기준)')
    print('=' * 74)
    print('  B only  기록 delta 중앙 %+.3f' % S.median([i['eq_delta'] for i in bo]))
    print('  control 기록 delta 중앙 %+.3f' % S.median([i['eq_delta'] for i in ct]))


if __name__ == '__main__':
    main()
