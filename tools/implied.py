#!/usr/bin/env python3
"""B-only 가 실제로 상대 벳에 직면했을 때의 가격을 잰다.

plan.py 는 수정하지 않는다. full_log 로 팟과 콜 비용을 재구성할 뿐이다.
eq_delta 와 implied odds 는 다른 개념이므로 직접 연결하지 않는다.
여기서는 '즉시 팟오즈로는 폴드인가', '스택은 남아 있는가'만 잰다.
"""
import os, sys, json, statistics as S, collections
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path: sys.path.insert(0, D)


def W(i): return i['why'] if isinstance(i['why'], list) else [i['why']]
def this_street(i, frag):
    pre = '%s: ' % i['street']
    return any(x.startswith(pre) and frag in x for x in W(i))


def price_at(full_log, street, seat, blinds):
    """그 스트리트에서 seat 이 처음 행동할 때의 (팟, 콜비용, 실제액션).

    팟은 이전 스트리트 전체 + 이번 스트리트 seat 차례 직전까지의 투입.
    """
    sb, bb = blinds
    pot = 0
    order = ['preflop', 'flop', 'turn', 'river']
    if street not in order:
        return None
    si = order.index(street)
    # 이전 스트리트 누적
    contrib_prev = collections.Counter()
    for (st, s, a, amt) in full_log:
        if st not in order:
            continue
        if order.index(st) < si:
            contrib_prev[s] = max(contrib_prev[s], amt) if a in ('raise','bet','call','allin') else contrib_prev[s]
    # preflop 블라인드는 full_log 에 없을 수 있으므로 최소 bb 는 깔린다
    pot = sum(contrib_prev.values())
    if si > 0 and pot == 0:
        pot = sb + bb
    # 이번 스트리트
    contrib = collections.Counter()
    acted = False
    for (st, s, a, amt) in full_log:
        if st != street:
            continue
        if s == seat:
            tocall = max(contrib.values(), default=0) - contrib[s]
            return (pot + sum(contrib.values()), max(0, tocall), a, amt)
        if a in ('raise', 'bet', 'call', 'allin'):
            contrib[s] = max(contrib[s], amt)
    return None


def main():
    rows = []
    for l in open(os.path.join(D, 'collected2.jsonl')):
        r = json.loads(l)
        fl = [tuple(x) for x in r.get('full_log', [])]
        for i in r.get('intents', []):
            if i.get('eq_current') is None: continue
            if not this_street(i, '쇼다운 가치 없고'): continue
            hole = r['hole'].get(str(i['seat']))
            if not hole: continue
            n = {'flop':3,'turn':4,'river':5}[i['street']]
            i['_hole']=hole; i['_bd']=list(r['board'])[:n]; i['_h']=r['hand_no']
            i['_pos']=r['pos'].get(str(i['seat']))
            i['_price']=price_at(fl, i['street'], i['seat'], r.get('blinds',[100,200]))
            i['_stack']=(r.get('stacks_before') or {}).get(str(i['seat']))
            rows.append(i)

    def grp(i):
        a = i['outs'] >= 4; b = i['eq_delta'] >= 0.20
        if b and not a: return 'B only'
        if not a and not b: return 'control'
        return 'other'

    bo = [i for i in rows if grp(i)=='B only']
    ct = [i for i in rows if grp(i)=='control' and i['street']=='flop']
    print('최종 else giveup %d건 · B-only %d · 대조군(플랍) %d'
          % (len(rows), len(bo), len(ct)))
    print()

    def faced(sub):
        return [i for i in sub if i['_price'] and i['_price'][1] > 0]

    fb, fc = faced(bo), faced(ct)
    print('=' * 72)
    print('상대 벳에 직면한 비율')
    print('=' * 72)
    print('  B only   %3d / %3d (%.0f%%)' % (len(fb), len(bo), 100*len(fb)/len(bo) if bo else 0))
    print('  control  %3d / %3d (%.0f%%)' % (len(fc), len(ct), 100*len(fc)/len(ct) if ct else 0))
    print()

    if fb:
        print('=' * 104)
        print('B-only — 상대 벳에 직면한 건')
        print('=' * 104)
        print('%-6s %-4s %-7s %-13s %7s %6s %8s %8s %8s %8s %7s %-6s' % (
            'hand','pos','홀','보드','delta','eq','팟','벳','필요승률','스택','SPR','실제'))
        print('-' * 104)
        for i in sorted(fb, key=lambda x: -x['eq_delta']):
            pot, tc, act, amt = i['_price']
            req = tc / (pot + tc) if (pot + tc) else 0
            print('%-6s %-4s %-7s %-13s %+7.3f %6.3f %8s %8s %8.1f%% %8s %7.1f %-6s' % (
                'h%d'%i['_h'], i['_pos'] or '?', ' '.join(i['_hole']),
                ' '.join(i['_bd']), i['eq_delta'], i['eq'],
                '{:,}'.format(pot), '{:,}'.format(tc), 100*req,
                '{:,}'.format(i['_stack']) if i['_stack'] else '?',
                i.get('spr', 0), act))

    print()
    print('=' * 72)
    print('가격 비교 — 상대 벳 직면분')
    print('=' * 72)
    def req_list(sub):
        out=[]
        for i in sub:
            pot, tc, act, amt = i['_price']
            if pot + tc:
                out.append((tc/(pot+tc), i))
        return out
    rb, rc = req_list(fb), req_list(fc)
    print('%-28s %12s %12s' % ('', 'B only', 'control'))
    print('-' * 72)
    for lab, f in (('필요 승률 중앙', lambda v: S.median([x for x,_ in v])),
                   ('eq 중앙', lambda v: S.median([i['eq'] for _,i in v])),
                   ('eq_delta 중앙', lambda v: S.median([i['eq_delta'] for _,i in v])),
                   ('SPR 중앙', lambda v: S.median([i.get('spr',0) for _,i in v]))):
        try:
            print('%-28s %12.3f %12.3f' % (lab, f(rb), f(rc)))
        except Exception:
            print('%-28s %12s %12s' % (lab, '-', '-'))

    print('-' * 72)
    for lab, cond in (
        ('eq >= 필요승률 (즉시 콜)', lambda x, i: i['eq'] >= x),
        ('eq < 필요승률 (즉시 폴드)', lambda x, i: i['eq'] < x),
        ('  그중 SPR >= 4 (딥)', lambda x, i: i['eq'] < x and i.get('spr',0) >= 4),
        ('  그중 필요승률 <= 35%', lambda x, i: i['eq'] < x and x <= 0.35),
    ):
        nb = sum(1 for x,i in rb if cond(x,i))
        nc = sum(1 for x,i in rc if cond(x,i))
        print('%-28s %8d(%2.0f%%) %8d(%2.0f%%)' % (
            lab, nb, 100*nb/len(rb) if rb else 0, nc, 100*nc/len(rc) if rc else 0))

    print()
    print('=' * 72)
    print('실제 액션')
    print('=' * 72)
    for name, sub in (('B only', fb), ('control', fc)):
        c = collections.Counter(i['_price'][2] for i in sub)
        print('  %-9s %s' % (name, dict(c)))


if __name__ == '__main__':
    main()
