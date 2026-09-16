#!/usr/bin/env python3
"""pcz 에 rel 페널티를 넣었을 때의 라벨 전이. **EV 는 재지 않는다.**

  python3 tools/cf_pcz.py --seeds 7000-7019 --hands 1000

설계는 CF_DESIGN_PCZ.md (커밋 0fec146). 그 설계대로만 낸다.

**plan.py 는 수정하지 않는다.** 현재 소스에서 make_plan 을 텍스트로
떼어내 한 줄을 끼우고 PL.__dict__ 에서 exec 한다 — tools/cf_szseen.py 와
같은 방식이다. 본문을 베껴 쓰지 않는다.

  O       현재 코드
  ARM-A   pcz += 0.22*_pen  /  0.08*_pen      v2 의 쌍
  ARM-B   pcz += 0.30*_pen  /  0.10*_pen      v3 의 쌍

계수를 고르지 않는다. 두 팔을 나란히 내고 우열을 가르지 않는다.
"""
import os, sys, argparse, textwrap, collections, random

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.join(D, 'tools'))

import plan as PL

# 삽입 기준점 — plan.py:390-394 의 블록. 원문과 한 글자라도 다르면 멈춘다.
ANCHOR = """    if _pen >= 0:
        v3 += 0.30 * _pen
        v2 += 0.22 * _pen
    else:
        v3 += 0.10 * _pen
        v2 += 0.08 * _pen
"""

ARMS = {
    'ARM-A': ("""    if _pen >= 0:
        v3 += 0.30 * _pen
        v2 += 0.22 * _pen
        pcz += 0.22 * _pen
    else:
        v3 += 0.10 * _pen
        v2 += 0.08 * _pen
        pcz += 0.08 * _pen
"""),
    'ARM-B': ("""    if _pen >= 0:
        v3 += 0.30 * _pen
        v2 += 0.22 * _pen
        pcz += 0.30 * _pen
    else:
        v3 += 0.10 * _pen
        v2 += 0.08 * _pen
        pcz += 0.10 * _pen
"""),
}

ENTER = '중간강도'
REJECT = '중간강도이나 상대레인지 열세'


def _func_src(text, name):
    """모듈 원문에서 함수 하나의 소스를 잘라낸다 (cf_szseen 과 같은 방식)."""
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
        raise SystemExit('plan.py:390-394 블록을 못 찾았다 — 원문이 바뀌었는지 확인할 것')
    src = src.replace(ANCHOR, body, 1)
    name = 'make_plan_%s' % tag.replace('-', '_')
    src = src.replace('def make_plan(', 'def %s(' % name, 1)
    ns = PL.__dict__
    exec(compile(textwrap.dedent(src), '<변종:%s>' % tag, 'exec'), ns)
    return ns[name]


def run(seeds, hands):
    import collect as C
    variants = {t: build(t, b) for t, b in ARMS.items()}
    _orig = PL.make_plan
    rows = []
    state = {'on': None}

    def wrap(*a, **k):
        base = _orig(*a, **k)
        if state['on'] is not None:
            state['on'].append(base)
            for t, fn in variants.items():
                try:
                    state['alt'][t].append(fn(*a, **k))
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


def report(rows):
    def pct(a, b):
        return ('%.2f%%' % (100.0*a/b)) if b else 'n/a'

    print()
    print('# pcz 반사실 — 라벨 전이   설계 0fec146')
    print('  make_plan 호출 %d건. EV 는 재지 않는다' % len(rows))
    print()

    # 건전성 (설계 4절)
    for t in ARMS:
        same_br = bad = 0
        for r in rows:
            o, a = r['O'], r[t]
            if a is None:
                continue
            eo = any(ENTER in w for w in why_lines(o))
            ea = any(ENTER in w for w in why_lines(a))
            if eo == ea:
                same_br += 1
                if o.get('plan') != a.get('plan'):
                    bad += 1
        print('  건전성 %s  분기 동일 %d건 중 라벨 불일치 %d건' % (t, same_br, bad))
    print('    분기가 안 갈렸는데 라벨이 다르면 패치가 의도 밖을 건드린 것이다')
    print()

    hdr = '%-8s %8s %8s %8s %8s %8s' % ('팔', 'pcz진입', '465탈락', 'giveup', 'semiblf', 'bluff2')
    print(hdr); print('  ' + '-'*len(hdr))
    for t in ['O'] + list(ARMS):
        sel = [r[t] for r in rows if r[t] is not None]
        en = [s for s in sel if any(ENTER in w for w in why_lines(s))]
        rj = [s for s in sel if any(REJECT in w for w in why_lines(s))]
        gv = [s for s in sel if s.get('plan') == 'giveup']
        sb = [s for s in sel if s.get('plan') == 'semibluff']
        b2 = [s for s in sel if s.get('plan') == 'bluff_2street']
        print('  %-8s %8d %8d %8d %8d %8d'
              % (t, len(en), len(rj), len(gv), len(sb), len(b2)))
    print()

    # 전이 행렬 — O 에서 pcz 로 진입했던 호출만
    for t in ARMS:
        mv = collections.Counter()
        out = 0
        for r in rows:
            o, a = r['O'], r[t]
            if a is None:
                continue
            if not any(ENTER in w for w in why_lines(o)):
                continue
            if any(ENTER in w for w in why_lines(a)):
                continue          # 여전히 pcz 안. 빠져나오지 않았다
            out += 1
            mv[(o.get('plan'), a.get('plan'))] += 1
        print('  %s — O 에서 pcz 진입했다가 빠져나온 %d건의 라벨 전이' % (t, out))
        for (x, y), c in mv.most_common():
            print('      %-14s → %-14s %5d' % (x, y, c))
        print()

    # 드로우
    for t in ARMS:
        n8 = nsb = 0
        for r in rows:
            o, a = r['O'], r[t]
            if a is None:
                continue
            if not any(ENTER in w for w in why_lines(o)):
                continue
            if (o.get('outs') or 0) < 8:
                continue
            n8 += 1
            if a.get('plan') == 'semibluff':
                nsb += 1
        print('  %s — O 에서 pcz 진입한 outs>=8 %d건 중 semibluff 로 간 것 %d건 (%s)'
              % (t, n8, nsb, pct(nsb, n8)))


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
