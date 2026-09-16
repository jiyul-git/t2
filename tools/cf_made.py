#!/usr/bin/env python3
"""plan.py:465 의 made >= 1 술어를 기존 술어로 바꿨을 때의 라벨 변화.

  python3 tools/cf_made.py --seeds 7000-7019 --hands 1000

설계는 CF_DESIGN_MADE.md. 그 설계대로만 낸다. EV 는 재지 않는다.

**plan.py 는 수정하지 않는다.** 현재 소스에서 make_plan 을 텍스트로 떼어내
한 줄만 치환하고 PL.__dict__ 에서 exec 한다 (cf_szseen · cf_pcz 와 동일).

  ARM-S   made >= 1 or eq >= 0.42 + 0.05*mw      plan.py:503 의 has_sd 식
  ARM-R   made >= 1 or rel >= 0.42               plan.py:1579
  ARM-D   made >= 1 or outs >= 8                 plan.py:468 의 8

세 팔은 서로 독립된 단일 개입이다. 합치지 않고 우열도 가르지 않는다.
458 은 건드리지 않는다.

반환 dict 는 **사본**으로 담는다 — 참조로 담으면 update_plan 의 뒷 단계
(refresh · river_fix · _allowed · attach_intent)가 같은 dict 를 변형해
O 만 파이프라인 통과 후 라벨이 된다 (cf_pcz 에서 실제로 틀렸다).
"""
import os, sys, argparse, textwrap, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.join(D, 'tools'))

import plan as PL

ANCHOR = "            plan = 'showdown' if made >= 1 else 'giveup'\n"

ARMS = {
    'ARM-S': "            plan = 'showdown' if (made >= 1 or eq >= 0.42 + 0.05*mw) else 'giveup'\n",
    'ARM-R': "            plan = 'showdown' if (made >= 1 or rel >= 0.42) else 'giveup'\n",
    'ARM-D': "            plan = 'showdown' if (made >= 1 or outs >= 8) else 'giveup'\n",
}

ENTER = '중간강도'
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
        raise SystemExit('plan.py:465 줄을 못 찾았다 — 원문이 바뀌었는지 확인할 것')
    src = src.replace(ANCHOR, body, 1)
    name = 'make_plan_%s' % tag.replace('-', '_')
    src = src.replace('def make_plan(', 'def %s(' % name, 1)
    ns = PL.__dict__
    exec(compile(textwrap.dedent(src), '<변종:%s>' % tag, 'exec'), ns)
    return ns[name]


def snap(st):
    if st is None:
        return None
    c = dict(st)
    c['why'] = list(st.get('why') or [])
    return c


def run(seeds, hands):
    import collect as C
    variants = {t: build(t, b) for t, b in ARMS.items()}
    _orig = PL.make_plan
    rows, state = [], {'on': None}

    def wrap(*a, **k):
        base = _orig(*a, **k)
        if state['on'] is not None:
            state['on'].append(snap(base))
            for t, fn in variants.items():
                try:
                    state['alt'][t].append(snap(fn(*a, **k)))
                except Exception:
                    state['alt'][t].append(None)
        return base
    PL.make_plan = wrap

    n = 0
    for sd in seeds:
        if n >= hands:
            break
        state['on'] = []
        state['alt'] = {t: [] for t in ARMS}
        got = C.run_one(sd, max_hands=hands - n)
        n += len(got)
        for i, b in enumerate(state['on']):
            rec = {'O': b}
            for t in ARMS:
                rec[t] = state['alt'][t][i]
            rows.append(rec)
        print('  seed %d  +%d핸드  누적 %d/%d  make_plan 호출 %d'
              % (sd, len(got), n, hands, len(rows)), flush=True)
    PL.make_plan = _orig
    return rows


def why_lines(st):
    if not st:
        return []
    sm = st.get('street_made')
    return [w for w in (st.get('why') or []) if w.startswith('%s: ' % sm)]


def has(st, s):
    return any(s in w for w in why_lines(st))


def report(rows):
    print()
    print('# 465 술어 반사실 — 라벨 변화   설계 CF_DESIGN_MADE.md')
    print('  make_plan 호출 %d건. EV 는 재지 않는다' % len(rows))
    print('  비교 단위는 make_plan 반환 시점의 라벨이다')
    print()

    # D1 — 465 미도달 호출의 라벨 동일성
    print('## D1  465 미도달 호출의 라벨 불일치')
    for t in ARMS:
        n = bad = 0
        for r in rows:
            o, a = r['O'], r[t]
            if a is None or has(o, REJECT):
                continue
            n += 1
            if o.get('plan') != a.get('plan'):
                bad += 1
        print('    %-6s  %5d건 중 불일치 %d건' % (t, n, bad))
    print()

    # D2 — 진입·도달 건수
    print('## D2  pcz 진입 / 465 도달 건수')
    for t in ['O'] + list(ARMS):
        sel = [r[t] for r in rows if r[t] is not None]
        print('    %-6s  진입 %5d   465 도달 %5d'
              % (t, sum(1 for s in sel if has(s, ENTER)),
                 sum(1 for s in sel if has(s, REJECT))))
    print()

    # D3 — 라벨 분포 전체
    labs = sorted({s.get('plan') for r in rows for s in r.values() if s})
    print('## D3  라벨 분포 (전체 호출)')
    print('    %-6s %s' % ('팔', ' '.join('%14s' % l for l in labs)))
    base = None
    for t in ['O'] + list(ARMS):
        c = collections.Counter(r[t].get('plan') for r in rows if r[t])
        if t == 'O':
            base = c
        print('    %-6s %s' % (t, ' '.join('%14d' % c.get(l, 0) for l in labs)))
    for t in ARMS:
        c = collections.Counter(r[t].get('plan') for r in rows if r[t])
        dg = c.get('giveup', 0) - base.get('giveup', 0)
        ds = c.get('showdown', 0) - base.get('showdown', 0)
        other = [l for l in labs if l not in ('giveup', 'showdown')
                 and c.get(l, 0) != base.get(l, 0)]
        print('    %-6s  giveup %+d / showdown %+d   그 외 변한 라벨 %s'
              % (t, dg, ds, other or '없음'))
    print()

    # D4~D6 — 465 안에서의 giveup
    print('## D4~D6  465 도달 호출 안에서의 giveup')
    for t in ['O'] + list(ARMS):
        sel = [r[t] for r in rows if r[t] is not None and has(r[t], REJECT)]
        gv = [s for s in sel if s.get('plan') == 'giveup']
        print('    %-6s  465 도달 %5d 중 giveup %5d' % (t, len(sel), len(gv)))
        if t != 'O' and gv:
            rl = sorted(s.get('rel') for s in gv if s.get('rel') is not None)
            ot = sorted(s.get('outs') or 0 for s in gv)
            eq = sorted(s.get('eq') for s in gv if s.get('eq') is not None)
            print('          잔존 건  rel 중앙 %.2f  outs 중앙 %d  eq 중앙 %.3f'
                  % (rl[len(rl)//2], ot[len(ot)//2], eq[len(eq)//2]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='7000-7019')
    ap.add_argument('--hands', type=int, default=1000)
    a = ap.parse_args()
    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi)+1)) if hi else [int(lo)]
    report(run(seeds, a.hands))


if __name__ == '__main__':
    main()
