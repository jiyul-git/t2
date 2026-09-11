#!/usr/bin/env python3
"""최종 has_sd 블록 해부 + 반사실 — plan.py 는 수정하지 않는다.

현재 스트리트에서 실제로 최종 else 블록에 도달해 giveup 이 된 건만 센다.
(why 는 스트리트별로 누적되므로 접두사로 거른다.)
"""
import os, sys, json, collections, statistics as S

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
import persona as PS, archetypes as A


def W(i):
    return i['why'] if isinstance(i['why'], list) else [i['why']]


def this_street(i, frag):
    pre = '%s: ' % i['street']
    return any(x.startswith(pre) and frag in x for x in W(i))


def mk_sk(prof):
    T = prof.get('type')
    if prof.get('concepts'):
        return lambda c: PS.sk(prof, c) / 3.33
    if T in A.ARCHETYPES:
        return lambda c: A.skill(T, c)
    return lambda c: 2


def load(path):
    out = []
    for l in open(path):
        r = json.loads(l)
        for i in r.get('intents', []):
            if i.get('eq_current') is None:
                continue
            i['_h'] = r['hand_no']
            i['_prof'] = r['profiles'].get(str(i['seat']), {})
            out.append(i)
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(D, 'collected.jsonl')
    recs = load(path)
    # 현재 스트리트에서 최종 else giveup 이 된 것
    g = [i for i in recs if this_street(i, '쇼다운 가치 없고')]
    print('전체 계측 intent %d' % len(recs))
    print('현재 스트리트 기준 최종 else giveup: %d건 (%.1f%%)'
          % (len(g), 100*len(g)/len(recs)))
    print()

    def mw(i): return 1 if i.get('n_opp', 1) >= 2 else 0
    def thr(i): return 0.42 + 0.05*mw(i)

    # ---- 검증: 정말 has_sd 가 거짓인가 ----
    bad = [i for i in g if (i['made'] >= 1 or i['eq'] >= thr(i))]
    print('검증: has_sd 가 참인데 giveup 된 건 %d (0이어야 정상)' % len(bad))
    print()

    # ---- 4분할 ----
    print('=' * 66)
    print('A = outs >= 4      B = eq_delta >= 0.20')
    print('=' * 66)
    quad = {
        'A ∩ B': [i for i in g if i['outs'] >= 4 and i['eq_delta'] >= 0.20],
        'A only': [i for i in g if i['outs'] >= 4 and i['eq_delta'] < 0.20],
        'B only': [i for i in g if i['outs'] < 4 and i['eq_delta'] >= 0.20],
        '해당 없음': [i for i in g if i['outs'] < 4 and i['eq_delta'] < 0.20],
    }
    for k, v in quad.items():
        print('  %-10s %3d (%.0f%%)' % (k, len(v), 100*len(v)/len(g)))
    print()

    hdr = '%-10s %5s %7s %7s %7s %7s %7s %6s' % (
        '', 'n', 'eq', 'eq_cur', 'delta', 'outs', 'rel', 'made>0')
    print(hdr)
    print('-' * 66)
    for k, v in quad.items():
        if not v:
            continue
        print('%-10s %5d %7.3f %7.3f %+7.3f %7.1f %7.2f %5.0f%%' % (
            k, len(v), S.median([x['eq'] for x in v]),
            S.median([x['eq_current'] for x in v]),
            S.median([x['eq_delta'] for x in v]),
            S.median([x['outs'] for x in v]),
            S.median([x['rel'] for x in v]),
            100*sum(1 for x in v if x['made'] >= 1)/len(v)))
    print()
    print('(값은 전부 중앙값. made 는 has_sd 실패 조건상 항상 0 이어야 한다)')
    print()

    # ---- street / mw 분포 ----
    print('=' * 66)
    print('스트리트 · 인원')
    print('=' * 66)
    for k, v in quad.items():
        if not v:
            continue
        st = collections.Counter(x['street'] for x in v)
        m = collections.Counter(mw(x) for x in v)
        print('  %-10s street %s   다인원 %d / 헤즈업 %d'
              % (k, dict(st), m.get(1, 0), m.get(0, 0)))
    print()

    # ---- eq 가 문턱에 얼마나 못 미쳤나 ----
    print('=' * 66)
    print('eq 가 has_sd 문턱(0.42 / 0.47)에 못 미친 폭')
    print('=' * 66)
    for k, v in quad.items():
        if not v:
            continue
        gap = [thr(i) - i['eq'] for i in v]
        near = sum(1 for x in gap if x <= 0.05)
        print('  %-10s 부족폭 중앙 %.3f  최소 %.3f   문턱 0.05 이내 %d건'
              % (k, S.median(gap), min(gap), near))
    print()

    # ---- 반사실: has_sd 게이트별 재분류 ----
    print('=' * 66)
    print('반사실 — has_sd 가 참이 됐다면 어디로 가나')
    print('=' * 66)
    print('(has_sd 참 → potcontrol 개념 있으면 pot_control(72%), 아니면 showdown)')
    for k, v in quad.items():
        if not v:
            continue
        pc = sum(1 for i in v if mk_sk(i['_prof'])('potcontrol') >= 1)
        print('  %-10s n=%3d → pot_control 후보 %3d  ·  showdown %3d'
              % (k, len(v), pc, len(v)-pc))
    print()

    # ---- 드로우가 semibluff 에 닿지 못한 이유 ----
    print('=' * 66)
    print('A 계열(outs>=4) 이 semibluff 에 닿지 못한 이유')
    print('=' * 66)
    aa = quad['A ∩ B'] + quad['A only']
    r = collections.Counter()
    for i in aa:
        sk = mk_sk(i['_prof'])
        if i['outs'] < 8:
            r['아웃츠 8 미만 (게이트 자체 미달)'] += 1
        elif i.get('behind', 0) > 1:
            r['뒤 액션자 2명 이상'] += 1
        elif sk('semibluff') < 0.4:
            r['세미블러프 개념 부족'] += 1
        else:
            r['게이트 통과 → 주사위 실패'] += 1
    for k2, v2 in r.most_common():
        print('  %-32s %3d' % (k2, v2))
    print()

    # ---- 대표 사례 ----
    print('=' * 66)
    print('A ∩ B 대표 사례 (delta 큰 순 12건)')
    print('=' * 66)
    print('%-6s %-4s %-6s %6s %6s %7s %5s %6s %7s %7s' % (
        'hand', 'seat', 'st', 'eq', 'cur', 'delta', 'outs', 'rel', 'radv', 'nadv'))
    for i in sorted(quad['A ∩ B'], key=lambda x: -x['eq_delta'])[:12]:
        print('%-6s %-4s %-6s %6.3f %6.3f %+7.3f %5d %6.2f %+7.2f %+7.2f' % (
            'h%d' % i['_h'], i['seat'], i['street'], i['eq'], i['eq_current'],
            i['eq_delta'], i['outs'], i['rel'], i['range_adv'], i['nut_adv']))


if __name__ == '__main__':
    main()
