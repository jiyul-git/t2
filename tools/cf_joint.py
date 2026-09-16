#!/usr/bin/env python3
"""pcz x made 결합 반사실 — 12팔 교차 EV. 설계 CF_DESIGN_JOINT_EV.md

  python3 tools/cf_joint.py --seeds 7000-7099 --hands 10000

plan.py 는 수정하지 않는다. make_plan 을 텍스트로 떼어내 두 앵커를 치환하고
PL.__dict__ 에서 exec 한다 (cf_szseen · cf_pcz · cf_made 와 동일).

팔  O · P-A · P-B · M-S · M-R · M-D · PM 6조합  = 12
    계수는 전부 기존 코드 행에서 옮긴 것이다 (설계 1-1 숫자 감사)

주 모집단  기준 실행에서 pcz 진입이 **정확히 1회**이고 그 진입이 465 에
           도달한 핸드. refresh 승격은 선정 조건이 아니라 사후 관측이다

1패스로 간다 — 핸드마다 스냅샷을 뜨고 자격 핸드에서만 11팔을 재생한다
(설계 7-1: deepcopy 는 핸드당 0.007s 로 2패스보다 싸다)
"""
import os, sys, copy, argparse, textwrap, collections, statistics, itertools

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
import plan as PL
import tourney as T

A_PCZ = """    if _pen >= 0:
        v3 += 0.30 * _pen
        v2 += 0.22 * _pen
    else:
        v3 += 0.10 * _pen
        v2 += 0.08 * _pen
"""
P_ARMS = {
    'P-A': """    if _pen >= 0:
        v3 += 0.30 * _pen
        v2 += 0.22 * _pen
        pcz += 0.22 * _pen
    else:
        v3 += 0.10 * _pen
        v2 += 0.08 * _pen
        pcz += 0.08 * _pen
""",
    'P-B': """    if _pen >= 0:
        v3 += 0.30 * _pen
        v2 += 0.22 * _pen
        pcz += 0.30 * _pen
    else:
        v3 += 0.10 * _pen
        v2 += 0.08 * _pen
        pcz += 0.10 * _pen
""",
}
A_MADE = "            plan = 'showdown' if made >= 1 else 'giveup'\n"
M_ARMS = {
    'M-S': "            plan = 'showdown' if (made >= 1 or eq >= 0.42 + 0.05*mw) else 'giveup'\n",
    'M-R': "            plan = 'showdown' if (made >= 1 or rel >= 0.42) else 'giveup'\n",
    'M-D': "            plan = 'showdown' if (made >= 1 or outs >= 8) else 'giveup'\n",
}
ENTER = '중간강도'
REJECT = '중간강도이나 상대레인지 열세'
PROMO = '강도 상승'


def _func_src(text, name):
    i = text.index('def %s(' % name)
    lines = text[i:].splitlines(True)
    out = [lines[0]]
    for ln in lines[1:]:
        if ln.strip() and not ln[:1].isspace():
            break
        out.append(ln)
    return ''.join(out)


def build(tag, patches):
    txt = open(os.path.join(D, 'plan.py'), encoding='utf-8').read()
    src = _func_src(txt, 'make_plan')
    for anchor, body in patches:
        if src.count(anchor) != 1:
            raise SystemExit('앵커를 못 찾았다 (%s) — plan.py 원문 확인' % tag)
        src = src.replace(anchor, body, 1)
    nm = 'mp_%s' % tag.replace('-', '_').replace('+', '__')
    src = src.replace('def make_plan(', 'def %s(' % nm, 1)
    exec(compile(textwrap.dedent(src), '<변종:%s>' % tag, 'exec'), PL.__dict__)
    return PL.__dict__[nm]


def arms():
    out = {}
    for p, pb in P_ARMS.items():
        out[p] = [(A_PCZ, pb)]
    for m, mb in M_ARMS.items():
        out[m] = [(A_MADE, mb)]
    for (p, pb), (m, mb) in itertools.product(P_ARMS.items(), M_ARMS.items()):
        out['%s+%s' % (p, m)] = [(A_PCZ, pb), (A_MADE, mb)]
    return {k: build(k, v) for k, v in out.items()}


_ORIG = PL.make_plan
EV = []


def hook(fn):
    def w(*a, **k):
        st = fn(*a, **k)
        try:
            sm = (st or {}).get('street_made')
            ws = [x for x in ((st or {}).get('why') or [])
                  if x.startswith('%s: ' % sm)]
            if any(ENTER in x for x in ws):
                prof = k.get('profile') or (a[4] if len(a) > 4 else None)
                EV.append({'key': id((prof or {}).get('concepts')),
                           'street': sm,
                           'reject': any(REJECT in x for x in ws)})
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
    ints = list(getattr(h, 'intents', []) or [])
    hh = getattr(h, 'hash', None)
    pmap = {id(p['concepts']): int(s)
            for s, p in (getattr(h, 'prof', {}) or {}).items()
            if isinstance(p, dict) and p.get('concepts') is not None}
    t.finish_hand()
    return hh, log, ints, before, dict(t.stacks), pmap


def seat_trace(ints, seat):
    """그 좌석의 스트리트별 라벨과 refresh 승격 줄을 **따로** 낸다.

    라벨 차이는 개입 그 자체라 늘 생긴다. 승격 경로가 갈렸는지는 그것과
    분리해서 봐야 한다 — 섞으면 설계 5절의 A 가 B 에 전부 흡수된다.
    """
    lab, pro = [], []
    for i in ints:
        if i.get('seat') != seat or i.get('idx') != 0:
            continue
        lab.append((i.get('street'), i.get('plan')))
        for w in (i.get('why') or []):
            if PROMO in w:
                pro.append(w)
    return {'lab': tuple(lab), 'pro': tuple(sorted(set(pro)))}


def run(seeds, hands):
    V = arms()
    pairs, nh = [], 0
    exc = collections.Counter()
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
                hh, log, ints, b0, a0, pmap = play(t)
            except Exception:
                PL.make_plan = _ORIG
                break
            hits = list(EV)
            nh += 1
            rej = [x for x in hits if x['reject']]
            if len(hits) != 1:
                exc['pcz 진입 %s회' % ('0' if not hits else '2+')] += 1
            elif len(rej) != 1:
                exc['진입 1회이나 465 미도달'] += 1
            else:
                seat = pmap.get(hits[0]['key'])
                if seat is None:
                    exc['좌석 식별 실패'] += 1
                else:
                    rec = {'hash': hh, 'seat': seat, 'street': hits[0]['street'],
                           'O': {'d': a0.get(seat, 0) - b0.get(seat, 0),
                                 'acts': [(s, a, m) for (s, x, a, m) in log if x == seat],
                                 'tr': seat_trace(ints, seat)}}
                    ok = True
                    for tag, fn in V.items():
                        t2 = copy.deepcopy(snap)
                        PL.make_plan = hook(fn)
                        EV.clear()
                        h2, l2, i2, b2, a2, _ = play(t2)
                        if h2 != hh:
                            ok = False
                            break
                        rec[tag] = {'d': a2.get(seat, 0) - b2.get(seat, 0),
                                    'acts': [(s, a, m) for (s, x, a, m) in l2 if x == seat],
                                    'tr': seat_trace(i2, seat)}
                    if ok:
                        pairs.append(rec)
                    else:
                        exc['핸드 hash 불일치'] += 1
            PL.make_plan = _ORIG
            if getattr(t, 'busted_hero', False):
                break
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 2:
                break
        print('  seed %d  누적 핸드 %d  주 모집단 %d' % (sd, nh, len(pairs)), flush=True)
    PL.make_plan = _ORIG
    return pairs, nh, exc, list(V)


def report(pairs, nh, exc, tags):
    print()
    print('# pcz x made 결합 반사실   설계 CF_DESIGN_JOINT_EV.md')
    print('  핸드 %d   주 모집단 %d' % (nh, len(pairs)))
    print('  제외: %s' % dict(exc))
    print('  우열을 가르지 않는다. 부호를 사전등록하지 않았다')
    print()
    if not pairs:
        print('  주 모집단 0 — 보고할 것이 없다'); return

    print('## 3  팔별 집계   **평균은 소수의 pair 가 좌우한다. 분포를 같이 본다**')
    print('    %-10s %6s %7s %7s %6s %9s %7s %11s %9s %9s' %
          ('팔', 'pair', 'act동일', 'act상이', 'ΔEV≠0', 'ΔEV평균', '중앙',
           '≠0만 평균', '최소', '최대'))
    D_ = {}
    for tag in tags:
        dv = [r[tag]['d'] - r['O']['d'] for r in pairs]
        D_[tag] = dv
        nz = [v for v in dv if v != 0]
        same = sum(1 for r in pairs if r[tag]['acts'] == r['O']['acts'])
        print('    %-10s %6d %7d %7d %6d %9.1f %7.1f %11s %9d %9d'
              % (tag, len(pairs), same, len(pairs)-same, len(nz),
                 statistics.fmean(dv), statistics.median(dv),
                 ('%.1f' % statistics.fmean(nz)) if nz else '-',
                 min(dv), max(dv)))
    print()
    print('    부호 분포 (ΔEV≠0 만)')
    for tag in tags:
        nz = [v for v in D_[tag] if v != 0]
        print('    %-10s 양 %3d / 음 %3d' % (tag, sum(1 for v in nz if v > 0),
                                             sum(1 for v in nz if v < 0)))
    print()

    print('## 3-1  PM 이 P 와 같은가 — pair 단위 확인')
    for p_ in P_ARMS:
        for m_ in M_ARMS:
            k = '%s+%s' % (p_, m_)
            ne = sum(1 for i in range(len(pairs)) if D_[k][i] != D_[p_][i])
            print('    %-10s ΔEV_PM != ΔEV_P 인 pair %d건' % (k, ne))
    print()

    print('## 4  상호작용   Interaction = ΔEV_PM - ΔEV_P - ΔEV_M')
    for p in P_ARMS:
        for m in M_ARMS:
            k = '%s+%s' % (p, m)
            inter = [D_[k][i] - D_[p][i] - D_[m][i] for i in range(len(pairs))]
            print('    %-10s 평균 %+.1f   중앙 %+.1f   ≠0 %d건'
                  % (k, statistics.fmean(inter), statistics.median(inter),
                     sum(1 for v in inter if v != 0)))
    print()

    print('## 5  ΔEV = 0 의 분해   (설계 5절)')
    print('    A 라벨만 다름(승격 줄 동일·액션 동일)  B 승격 경로 다름·액션 동일  C 액션 상이')
    for tag in tags:
        a = b = c = 0
        for r in pairs:
            if r[tag]['acts'] != r['O']['acts']:
                c += 1
            elif r[tag]['tr']['pro'] != r['O']['tr']['pro']:
                b += 1
            else:
                a += 1
        print('    %-10s A %4d   B %4d   C %4d' % (tag, a, b, c))
    print()

    print('## 5-1  refresh 승격이 갈린 pair — **pair 당 한 번만** 찍는다')
    shown = 0
    for r in pairs:
        dif = [t for t in tags if r[t]['tr']['pro'] != r['O']['tr']['pro']]
        if not dif:
            continue
        shown += 1
        if shown > 8:
            break
        print('    hash %s seat %s %s   갈린 팔 %s'
              % (str(r['hash'])[:8], r['seat'], r['street'], ','.join(dif)))
        print('        O    라벨 %s' % (r['O']['tr']['lab'],))
        print('             승격 %s' % (r['O']['tr']['pro'] or '없음',))
        for t in dif:
            print('        %-8s 라벨 %s  ΔEV %+d'
                  % (t, r[t]['tr']['lab'], r[t]['d'] - r['O']['d']))
            print('             승격 %s' % (r[t]['tr']['pro'] or '없음',))
    print()

    print('## 6  사전등록 판정')
    v1 = sum(1 for r in pairs for tag in tags
             if r[tag]['acts'] == r['O']['acts'] and r[tag]['d'] != r['O']['d'])
    v2 = sum(1 for r in pairs for tag in tags if r[tag]['acts'] != r['O']['acts'])
    v3 = sum(1 for r in pairs for tag in tags
             if r[tag]['tr']['pro'] != r['O']['tr']['pro'])
    vlab = sum(1 for r in pairs for tag in tags
               if r[tag]['tr']['lab'] != r['O']['tr']['lab'])
    print('    V1  액션 동일인데 ΔEV≠0 인 (pair,팔) %d건' % v1)
    print('    V2  액션이 달라진 (pair,팔) %d건' % v2)
    print('    V3  refresh 승격 줄이 갈린 (pair,팔) %d건' % v3)
    print('        [참고] 스트리트 라벨이 갈린 (pair,팔) %d건 — 개입 그 자체다' % vlab)
    print('    V4  부호·우열은 사전등록하지 않았다')


def save(pairs, tags, path):
    import json, gzip
    op = gzip.open if path.endswith('.gz') else open
    with op(path, 'wt', encoding='utf-8') as fh:
        for r in pairs:
            row = {'hash': r['hash'], 'seat': r['seat'], 'street': r['street'],
                   'O': r['O']['d']}
            for t in tags:
                row[t] = r[t]['d']
                row[t + '_act'] = (r[t]['acts'] != r['O']['acts'])
                row[t + '_pro'] = (r[t]['tr']['pro'] != r['O']['tr']['pro'])
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    print('  원자료 %d행 → %s' % (len(pairs), path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='7000-7099')
    ap.add_argument('--hands', type=int, default=10000)
    ap.add_argument('--rows', default=None, help='pair 원자료 저장 경로')
    a = ap.parse_args()
    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi)+1)) if hi else [int(lo)]
    pairs, nh, exc, tags = run(seeds, a.hands)
    if a.rows:
        save(pairs, tags, a.rows)
    report(pairs, nh, exc, tags)


if __name__ == '__main__':
    main()
