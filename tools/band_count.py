#!/usr/bin/env python3
"""eq >= pcz 진입 띠의 **건수만** 센다. 손익·수정 효과는 재지 않는다.

  python3 tools/band_count.py --seeds 7000-7009 --hands 1000 --out band.jsonl
  python3 tools/band_count.py --in band.jsonl

근거는 TRACE_EQREL.md (커밋 c4ee28e). plan.py 는 수정하지 않는다.

**문턱을 역산하거나 재구성하지 않는다.** 분기 진입은 make_plan 이 직접
남긴 why 문자열로 판정한다 (plan.py:445 · 457 · 460 · 466 은 전부
'중간강도' 를 포함한다).

why 는 스트리트를 넘어 누적된다 (CLAUDE.md 작업 원칙 5).
그래서 **그 기록의 street 접두사가 붙은 줄만** 읽는다.

관측 단위는 (hash, seat, street) 의 idx == 0 기록이다.

tools/collect.py 의 main() 은 random.Random() 을 시드 없이 써서 재현이
안 된다. 여기서는 run_one(seed, ...) 을 고정 시드로 부른다 — 같은
수집기이고 시드만 고정한 것이다.
"""
import os, sys, json, argparse, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.join(D, 'tools'))

ENTER = '중간강도'                       # 445 · 457 · 460 · 466 공통
REJECT = '중간강도이나 상대레인지 열세'    # 466 (= plan.py:465 의 else)
BAND_LO, BAND_HI = 0.50, 0.88            # TRACE_EQREL 3절의 헤즈업·무리딩 유도값


def collect(seeds, hands, out):
    import collect as C
    recs, n = [], 0
    for sd in seeds:
        if n >= hands:
            break
        got = C.run_one(sd, max_hands=hands - n)
        recs.extend(got); n += len(got)
        print('  seed %d  +%d핸드  누적 %d/%d' % (sd, len(got), n, hands), flush=True)
    if out:
        with open(out, 'w') as fp:
            for r in recs:
                fp.write(json.dumps(r, ensure_ascii=False, default=str) + '\n')
        print('  → %s (%d핸드)' % (out, len(recs)))
    return recs


def load(path):
    with open(path) as f:
        return [json.loads(l) for l in f]


def analyse(recs):
    seen = set()
    obs = []
    for r in recs:
        h = r.get('hash')
        for i in r.get('intents', []):
            if i.get('idx') != 0:
                continue
            k = (h, i.get('seat'), i.get('street'))
            if k in seen:
                continue
            seen.add(k)
            obs.append(i)

    pre = lambda i: '%s: ' % i.get('street')
    def lines(i):
        return [w for w in (i.get('why') or []) if w.startswith(pre(i))]

    tot = len(obs)
    enter = [i for i in obs if any(ENTER in w for w in lines(i))]
    band = [i for i in enter
            if i.get('eq') is not None and BAND_LO <= i['eq'] < BAND_HI]
    rej = [i for i in enter if any(REJECT in w for w in lines(i))]
    rej_band = [i for i in band if any(REJECT in w for w in lines(i))]
    gv = [i for i in rej if i.get('plan') == 'giveup']
    gv_band = [i for i in rej_band if i.get('plan') == 'giveup']

    def pct(a, b):
        return ('%.2f%%' % (100.0*a/b)) if b else 'n/a'

    print()
    print('# eq >= pcz 진입 띠 — 건수')
    print('  판정은 why 문자열로만 한다. 문턱을 재구성하지 않았다')
    print('  관측 단위 (hash, seat, street) idx==0')
    print()
    print('  전체 관측                        %6d' % tot)
    print('  ├ pcz 진입 (why "중간강도")       %6d   %s' % (len(enter), pct(len(enter), tot)))
    print('  │  ├ rel 탈락 (466)              %6d   %s' % (len(rej), pct(len(rej), len(enter))))
    print('  │  │   └ 실제 plan == giveup     %6d   %s' % (len(gv), pct(len(gv), len(rej))))
    print('  │  └ rel 비탈락                  %6d   %s'
          % (len(enter)-len(rej), pct(len(enter)-len(rej), len(enter))))
    print('  └ 그 밖                          %6d' % (tot - len(enter)))
    print()
    print('  [참고] eq 를 [%.2f, %.2f) 로 자른 부분집합' % (BAND_LO, BAND_HI))
    print('  이 경계는 헤즈업·무리딩 유도값이다. 실제 pcz·v2 는 mw 와 상대 읽기로')
    print('  움직이므로 **채점용이 아니라 참고값이다**')
    print('    띠 안 pcz 진입                 %6d   %s' % (len(band), pct(len(band), len(enter))))
    print('      └ rel 탈락                   %6d   %s' % (len(rej_band), pct(len(rej_band), len(band))))
    print('          └ plan == giveup         %6d   %s' % (len(gv_band), pct(len(gv_band), len(rej_band))))
    print()

    # --- 추가 내역. 첫 집계를 본 뒤 붙였다. 채점이 아니라 규모 파악용이다 ---
    d8 = [i for i in enter if (i.get('outs') or 0) >= 8]
    d8r = [i for i in d8 if any(REJECT in w for w in lines(i))]
    all8 = [i for i in obs if (i.get('outs') or 0) >= 8]
    sb8 = [i for i in all8 if i.get('plan') == 'semibluff']
    print('  [추가] 드로우(outs>=8) 규모')
    print('    전체 관측 중 outs>=8            %6d' % len(all8))
    print('      ├ plan == semibluff           %6d   %s' % (len(sb8), pct(len(sb8), len(all8))))
    print('      └ pcz 진입 (plan.py:468 도달 불가) %4d   %s' % (len(d8), pct(len(d8), len(all8))))
    print('          └ 465 탈락                %6d' % len(d8r))
    print()
    # 465 의 else 는 rel 과 made 두 조건의 논리곱이 깨진 것이다.
    # made 는 기록돼 있고 458 의 rel 문턱은 max(0.28, 0.52-0.080*_mg) 라
    # _mg(기록 없음)에 따라 [0.28, 0.52] 사이다. 그래서 세 구간으로만 가른다.
    print('  [추가] 465 로 온 %d건을 rel 로 가른다 (made 분포는 아래)' % len(rej))
    for lab, sel in (('rel <  0.28          ', [i for i in rej if i['rel'] < 0.28]),
                     ('0.28 <= rel <  0.52  ', [i for i in rej if 0.28 <= i['rel'] < 0.52]),
                     ('rel >= 0.52          ', [i for i in rej if i['rel'] >= 0.52])):
        print('    %s %6d' % (lab, len(sel)))
    print('    → rel >= 0.52 는 458 의 rel 문턱을 확실히 넘는다.')
    print('      그 건들을 막은 것은 rel 이 아니라 made >= 1 이다')
    print()

    st = collections.Counter(i['street'] for i in rej)
    print('  rel 탈락의 스트리트 분포   %s' % dict(st))
    pl = collections.Counter(i.get('plan') for i in rej)
    print('  rel 탈락의 최종 plan       %s' % dict(pl))
    md = collections.Counter(i.get('made') for i in gv)
    print('  giveup 의 made 분포        %s' % dict(md))
    ot = [i.get('outs') for i in gv if i.get('outs') is not None]
    if ot:
        ot.sort()
        print('  giveup 의 outs  중앙 %d  최대 %d  (outs>=8 인 것 %d건)'
              % (ot[len(ot)//2], ot[-1], sum(1 for x in ot if x >= 8)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='7000-7009')
    ap.add_argument('--hands', type=int, default=1000)
    ap.add_argument('--out', default=None)
    ap.add_argument('--in', dest='inp', default=None)
    a = ap.parse_args()
    if a.inp:
        recs = load(a.inp)
    else:
        lo, hi = (a.seeds.split('-') + [None])[:2]
        seeds = list(range(int(lo), int(hi)+1)) if hi else [int(lo)]
        recs = collect(seeds, a.hands, a.out)
    analyse(recs)


if __name__ == '__main__':
    main()
