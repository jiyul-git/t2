#!/usr/bin/env python3
"""수정안 B 반사실 평가기 — plan.py 를 수정하지 않는다.

B: plan.py:402 의 else 에서 plan 을 확정하지 않고,
   아래 semibluff / bluff_2street / 최종 has_sd 체인으로 흘려보냈다면.

기록된 intent 의 상태값과 profiles 로 아래 체인의 조건식을 재평가한다.
확률 분기는 rng 소비 순서를 복원할 수 없으므로 확정하지 않고
확률값 자체를 계산해 기대 분포로 낸다.
"""
import os, sys, json, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)

import persona as PS
import archetypes as A


def W(i):
    return i['why'] if isinstance(i['why'], list) else [i['why']]


def is_402(i):
    pre = '%s: ' % i['street']
    return any(x.startswith(pre) and '상대레인지 열세' in x for x in W(i))


def mk_sk(prof):
    T = prof.get('type')
    if prof.get('concepts'):
        return lambda c: PS.sk(prof, c) / 3.33
    if T in A.ARCHETYPES:
        return lambda c: A.skill(T, c)
    return lambda c: 2


def cf_B(i, prof):
    sk = mk_sk(prof)
    eq = i['eq']; outs = i['outs']; made = i['made']
    behind = i.get('behind', 0)
    mw = 1 if i.get('n_opp', 1) >= 2 else 0

    if outs >= 8 and behind <= 1 and sk('semibluff') >= 0.4:
        p = min(0.95, 0.25 + 0.24 * sk('semibluff'))
        return ('semibluff 게이트', 'semibluff', p)

    if eq < 0.42:
        return ('bluff 게이트', 'bluff_2street', None)

    has_sd = (made >= 1) or (eq >= 0.42 + 0.05 * mw)
    if has_sd:
        if sk('potcontrol') >= 1:
            return ('최종 has_sd', 'pot_control', 0.72)
        return ('최종 has_sd', 'showdown', 1.0)
    return ('최종 has_sd', 'giveup', 1.0)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(D, 'collected.jsonl')
    recs = []
    for l in open(path):
        r = json.loads(l)
        for i in r.get('intents', []):
            if i.get('eq_current') is None:
                continue
            i['_h'] = r['hand_no']
            i['_prof'] = r['profiles'].get(str(i['seat']), {})
            recs.append(i)

    hits = [i for i in recs if is_402(i)]
    print('전체 계측 intent %d  ·  402줄 발동 %d건' % (len(recs), len(hits)))
    print()
    print('=' * 112)
    print('402줄 발동 건별 — 현재 vs B')
    print('=' * 112)
    print('%-6s %-4s %-6s %6s %6s %7s %5s %5s %6s %7s %7s  %-14s %-16s %-16s' %
          ('hand','seat','st','eq','cur','delta','outs','made','rel',
           'radv','nadv','현재','B 분기','B plan'))
    print('-' * 112)
    rows = []
    for i in sorted(hits, key=lambda x: -x['eq_delta']):
        br, pl, p = cf_B(i, i['_prof'])
        rows.append((i, br, pl, p))
        pstr = pl if (p is None or p == 1.0) else '%s(%.0f%%)' % (pl, p*100)
        print('%-6s %-4s %-6s %6.3f %6.3f %+7.3f %5d %5d %6.2f %+7.2f %+7.2f  %-14s %-16s %-16s' % (
            'h%d' % i['_h'], i['seat'], i['street'], i['eq'], i['eq_current'],
            i['eq_delta'], i['outs'], i['made'], i['rel'],
            i['range_adv'], i['nut_adv'], i['plan'], br, pstr))

    print()
    print('=' * 60)
    print('현재 plan → B plan  변화 행렬')
    print('=' * 60)
    mat = collections.Counter((i['plan'], pl) for i, br, pl, p in rows)
    for (a, b), n in sorted(mat.items(), key=lambda x: -x[1]):
        print('  %-15s → %-15s %3d%s' % (a, b, n, '' if a != b else '  (변화 없음)'))

    print()
    print('=' * 60)
    print('집단별')
    print('=' * 60)
    groups = [
        ('A. made==0 & outs>=8',  lambda i: i['made']==0 and i['outs']>=8),
        ('B. made==0 & 4<=outs<8', lambda i: i['made']==0 and 4<=i['outs']<8),
        ('C. made==0 & outs<4',   lambda i: i['made']==0 and i['outs']<4),
        ('D. made>=1',            lambda i: i['made']>=1),
    ]
    for name, f in groups:
        sub = [x for x in rows if f(x[0])]
        if not sub:
            print('%-24s  n=0' % name); continue
        cur = collections.Counter(i['plan'] for i,_,_,_ in sub)
        nw  = collections.Counter(pl for _,_,pl,_ in sub)
        print('%-24s  n=%d' % (name, len(sub)))
        print('    현재: %s' % dict(cur))
        print('    B   : %s' % dict(nw))

    print()
    print('=' * 60)
    print('대표 사례 (아웃츠 15+)')
    print('=' * 60)
    for i, br, pl, p in rows:
        if i['outs'] >= 15:
            print('  h%-4d s%-2d %-6s  eq %.3f cur %.3f d %+.3f outs %d rel %.2f' % (
                i['_h'], i['seat'], i['street'], i['eq'], i['eq_current'],
                i['eq_delta'], i['outs'], i['rel']))
            print('      현재 %s  →  B: %s 에서 %s%s' % (
                i['plan'], br, pl,
                '' if (p is None or p == 1.0) else ' (확률 %.0f%%)' % (p*100)))

    print()
    print('=' * 60)
    print('요약')
    print('=' * 60)
    changed = sum(1 for i,_,pl,_ in rows if pl != i['plan'])
    draws   = sum(1 for i,_,pl,_ in rows if pl in ('semibluff','bluff_2street'))
    stay    = sum(1 for i,_,pl,_ in rows if pl == 'giveup')
    print('  402줄에서 탈출해 다른 plan 으로 재분류   %3d / %d' % (changed, len(rows)))
    print('  그중 드로우 계열(semibluff/bluff)로       %3d' % draws)
    print('  여전히 giveup                            %3d' % stay)


if __name__ == '__main__':
    main()
