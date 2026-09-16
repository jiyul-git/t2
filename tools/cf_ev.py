#!/usr/bin/env python3
"""465 라벨 플립의 칩 효과. 같은 핸드를 스냅샷에서 팔별로 재생한다.

  python3 tools/cf_ev.py --seeds 7000-7019 --hands 1000

설계는 CF_DESIGN_EV.md. 그 설계대로만 낸다. plan.py 는 수정하지 않는다.

페어링
  copy.deepcopy(Tournament) 는 t.run.gen 때문에 실패한다. t.run 을 떼고
  복사하면 next_hand() 가 다시 만든다. 같은 스냅샷 재생이 hash·stacks·
  full_log 까지 동일함을 확인했다.

모집단
  기준 실행에서 465 에 **정확히 1회** 도달한 핸드. 2회 이상은 한 번의 ARM
  실행이 여러 결정을 동시에 뒤집어 귀속이 성립하지 않으므로 제외하고,
  제외 건수를 보고한다. ARM 이 새로 만든 도달은 모집단에 넣지 않는다.

결과변수
  대상 좌석의 핸드 순칩 변화. 분기 전 기여는 두 경로에서 같으므로 차분에서
  소거된다.

금지 (설계 7절)
  팔 간 우열을 가르지 않는다. 플립 건수를 EV 로 읽지 않는다.
  유의성 문턱을 새로 만들지 않는다.
"""
import os, sys, copy, argparse, textwrap, collections, statistics

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)

import plan as PL
import tourney as T

ANCHOR = "            plan = 'showdown' if made >= 1 else 'giveup'\n"
ARMS = {
    'ARM-S': "            plan = 'showdown' if (made >= 1 or eq >= 0.42 + 0.05*mw) else 'giveup'\n",
    'ARM-R': "            plan = 'showdown' if (made >= 1 or rel >= 0.42) else 'giveup'\n",
    'ARM-D': "            plan = 'showdown' if (made >= 1 or outs >= 8) else 'giveup'\n",
}
REJECT = '중간강도이나 상대레인지 열세'


def _func_src(text, name):
    i = text.index('def %s(' % name)
    lines = text[i:].splitlines(True)
    out = [lines[0]]
    for ln in lines[1:]:
        if ln.strip() and not ln[:1].isspace():
            break
        out.append(ln)
    return ''.join(out)


def build(tag, body):
    txt = open(os.path.join(D, 'plan.py'), encoding='utf-8').read()
    src = _func_src(txt, 'make_plan')
    if src.count(ANCHOR) != 1:
        raise SystemExit('plan.py:465 줄을 못 찾았다 — 원문 확인')
    src = src.replace(ANCHOR, body, 1)
    nm = 'make_plan_ev_%s' % tag.replace('-', '_')
    src = src.replace('def make_plan(', 'def %s(' % nm, 1)
    ns = PL.__dict__
    exec(compile(textwrap.dedent(src), '<변종:%s>' % tag, 'exec'), ns)
    return ns[nm]


_ORIG = PL.make_plan
EV = []


def hook(fn):
    def w(*a, **k):
        st = fn(*a, **k)
        try:
            sm = (st or {}).get('street_made')
            hit = any(w2.startswith('%s: ' % sm) and REJECT in w2
                      for w2 in ((st or {}).get('why') or []))
            if hit:
                prof = k.get('profile')
                if prof is None and len(a) > 4:
                    prof = a[4]
                # profile['id'] 는 이 경로에서 None 이고, Hand.axes 는 매번
                # dict(p) 를 새로 만들어 객체 동일성도 안 맞는다. 다만 얕은
                # 복사라 concepts 는 **같은 객체**다. 그것을 좌석 열쇠로 쓴다.
                EV.append({'key': id((prof or {}).get('concepts')), 'street': sm})
        except Exception:
            pass
        return st
    return w


def snapshot(t):
    keep = getattr(t, 'run', None)
    t.run = None
    c = copy.deepcopy(t)
    t.run = keep
    return c


def play(t):
    before = dict(t.stacks)
    st = t.next_hand()
    g = 0
    while isinstance(st, dict) and not st.get('done'):
        g += 1
        if g > 400:
            break
        st = t.submit('fold', 0)
    h = t.hand
    log = list(getattr(t.run, 'full_log', []) or [])
    hh = getattr(h, 'hash', None)
    pmap = {}
    for s, p in (getattr(h, 'prof', {}) or {}).items():
        if isinstance(p, dict) and p.get('concepts') is not None:
            pmap[id(p['concepts'])] = int(s)
    t.finish_hand()
    return hh, log, before, dict(t.stacks), pmap


def acts(log, seat):
    return [(s, a, amt) for (s, x, a, amt) in log if x == seat]


def run(seeds, hands):
    variants = {t: build(t, b) for t, b in ARMS.items()}
    pairs, nh, multi, zero = [], 0, 0, 0
    for sd in seeds:
        if nh >= hands:
            break
        t = T.Tournament(entries=40, start_stack=30000, hero_seat=7, seats=8,
                         seed=sd, hands_per_level=12)
        while nh < hands:
            try:
                snap = snapshot(t)
            except Exception:
                break
            EV.clear()
            PL.make_plan = hook(_ORIG)
            try:
                hh, log, b0, a0, pmap = play(t)
            except Exception:
                break
            hits = list(EV)
            nh += 1
            if len(hits) == 0:
                zero += 1
            elif len(hits) > 1:
                multi += 1
            else:
                seat = pmap.get(hits[0]['key'])
                if seat is not None:
                    rec = {'hash': hh, 'seat': seat, 'street': hits[0]['street'],
                           'base': a0.get(seat, 0) - b0.get(seat, 0),
                           'base_acts': acts(log, seat)}
                    for tag, fn in variants.items():
                        t2 = copy.deepcopy(snap)
                        PL.make_plan = hook(fn)
                        EV.clear()
                        h2, l2, b2, a2, _ = play(t2)
                        if h2 != hh:
                            rec[tag] = None
                            continue
                        rec[tag] = {'d': a2.get(seat, 0) - b2.get(seat, 0),
                                    'acts': acts(l2, seat)}
                    pairs.append(rec)
            PL.make_plan = _ORIG
            if getattr(t, 'busted_hero', False):
                break
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 2:
                break
        print('  seed %d  누적 핸드 %d  페어 %d' % (sd, nh, len(pairs)), flush=True)
    PL.make_plan = _ORIG
    return pairs, nh, multi, zero


def report(pairs, nh, multi, zero):
    print()
    print('# 465 라벨 플립의 칩 효과   설계 CF_DESIGN_EV.md')
    print('  핸드 %d   모집단(465 정확히 1회) %d   제외: 0회 %d · 2회 이상 %d'
          % (nh, len(pairs), zero, multi))
    print('  유의성 문턱을 만들지 않는다. 평균·중앙값·부호·건수를 그대로 낸다')
    print()
    for tag in ARMS:
        sel = [(r, r[tag]) for r in pairs if r.get(tag)]
        if not sel:
            print('  %-6s 페어 없음' % tag); continue
        dv = [x['d'] - r['base'] for r, x in sel]
        same = [(r, x) for r, x in sel if x['acts'] == r['base_acts']]
        diff = [(r, x) for r, x in sel if x['acts'] != r['base_acts']]
        bad = [1 for r, x in same if x['d'] - r['base'] != 0]
        nz = [v for v in dv if v != 0]
        print('  %s   페어 %d' % (tag, len(sel)))
        print('    V1  액션 동일 %d건 중 ΔEV≠0 인 것 %d건  (0 이어야 한다)'
              % (len(same), len(bad)))
        print('    V2  ΔEV≠0 %d건   액션이 달라진 페어 %d건' % (len(nz), len(diff)))
        print('        평균 %+.1f   중앙 %+.1f   양 %d / 음 %d'
              % (statistics.fmean(dv) if dv else 0.0,
                 statistics.median(dv) if dv else 0.0,
                 sum(1 for v in dv if v > 0), sum(1 for v in dv if v < 0)))
        if nz:
            print('        ΔEV≠0 만: 평균 %+.1f   중앙 %+.1f'
                  % (statistics.fmean(nz), statistics.median(nz)))
        tr = collections.Counter()
        for r, x in diff:
            for i, (ba) in enumerate(r['base_acts']):
                if i >= len(x['acts']) or x['acts'][i] != ba:
                    tr[(ba[1], x['acts'][i][1] if i < len(x['acts']) else '—')] += 1
                    break
        if tr:
            print('    V3  첫 갈림 전환  %s'
                  % '  '.join('%s→%s %d' % (a, b, c) for (a, b), c in tr.most_common()))
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='7000-7019')
    ap.add_argument('--hands', type=int, default=1000)
    a = ap.parse_args()
    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi)+1)) if hi else [int(lo)]
    report(*run(seeds, a.hands))


if __name__ == '__main__':
    main()
