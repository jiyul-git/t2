#!/usr/bin/env python3
"""B-only 18건의 행동 맥락을 대조군과 비교한다. plan.py 는 수정하지 않는다.

코드가 실제로 쓰는 변수만 쓴다. 새 지표를 만들지 않는다.
  oop_field / behind / n_opp / spr / init / blocker / blocker_net / nut_adv
  range_adv / danger / bf / tilt / type
"""
import os, sys, json, statistics as S, collections
from logkeys import oop_field_of, oop_field_label
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path: sys.path.insert(0, D)


def W(i): return i['why'] if isinstance(i['why'], list) else [i['why']]
def this_street(i, frag):
    pre = '%s: ' % i['street']
    return any(x.startswith(pre) and frag in x for x in W(i))


def main():
    rows = []
    for l in open(os.path.join(D, 'collected.jsonl')):
        r = json.loads(l)
        for i in r.get('intents', []):
            if i.get('eq_current') is None: continue
            if not this_street(i, '쇼다운 가치 없고'): continue
            hole = r['hole'].get(str(i['seat']))
            if not hole: continue
            n = {'flop':3,'turn':4,'river':5}[i['street']]
            i['_hole']=hole; i['_bd']=list(r['board'])[:n]; i['_h']=r['hand_no']
            i['_pos']=r['pos'].get(str(i['seat']))
            rows.append(i)

    def grp(i):
        a = i['outs'] >= 4; b = i['eq_delta'] >= 0.20
        if b and not a: return 'B only'
        if not a and not b: return 'control'
        return 'other'

    bo = [i for i in rows if grp(i)=='B only']
    ct = [i for i in rows if grp(i)=='control' and i['street']=='flop']

    print('B only %d건 · 대조군(플랍) %d건' % (len(bo), len(ct)))
    print()
    print('=' * 104)
    print('B-only 18건 — 행동 맥락')
    print('=' * 104)
    print('%-6s %-4s %-7s %-13s %7s %5s %5s %6s %5s %6s %7s %7s %6s' % (
        'hand','pos','홀','보드','delta','oop','뒤','SPR','선제','위험','radv','nadv','blk'))
    print('-' * 104)
    for i in sorted(bo, key=lambda x: -x['eq_delta']):
        print('%-6s %-4s %-7s %-13s %+7.3f %5s %5d %6.1f %5s %6.2f %+7.2f %+7.2f %6.2f' % (
            'h%d'%i['_h'], i['_pos'] or '?', ' '.join(i['_hole']), ' '.join(i['_bd']),
            i['eq_delta'], oop_field_label(i), i.get('behind',0),
            i.get('spr',0), '있음' if i.get('init') else '-',
            i.get('danger',0), i['range_adv'], i['nut_adv'], i.get('blocker',0)))

    print()
    print('=' * 78)
    print('집단 비교 (중앙값 / 비율)')
    print('=' * 78)
    def stat(sub, key):
        v=[i.get(key) for i in sub if isinstance(i.get(key),(int,float))]
        return S.median(v) if v else float('nan')
    def frac(sub, f):
        return 100*sum(1 for i in sub if f(i))/len(sub) if sub else 0

    def frac_opt(sub, f):
        """None 은 **모집단에서 뺀다**. 없는 값을 False 로 세면 비율이 낮아진다."""
        v = [f(i) for i in sub]
        v = [x for x in v if x is not None]
        return (100*sum(1 for x in v if x)/len(v)) if v else float('nan'), len(v)

    print('%-22s %12s %12s' % ('', 'B only', 'control'))
    print('-' * 78)
    for label, key in (('eq_delta','eq_delta'), ('eq','eq'), ('eq_current','eq_current'),
                       ('rel','rel'), ('SPR','spr'), ('보드 위험','danger'),
                       ('range_adv','range_adv'), ('nut_adv','nut_adv'),
                       ('blocker','blocker'), ('blocker_net','blocker_net'),
                       ('bf','bf'), ('뒤 액션자','behind')):
        print('%-22s %12.3f %12.3f' % (label, stat(bo,key), stat(ct,key)))
    print('-' * 78)
    _bo_p, _bo_n = frac_opt(bo, oop_field_of)
    _ct_p, _ct_n = frac_opt(ct, oop_field_of)
    print('%-22s %11.0f%% %11.0f%%   (n=%d/%d, 기록 없는 건 제외)'
          % ('OOP 비율(field)', _bo_p, _ct_p, _bo_n, _ct_n))
    print('%-22s %11.0f%% %11.0f%%' % ('선제권 보유', frac(bo,lambda i:i.get('init')), frac(ct,lambda i:i.get('init'))))
    print('%-22s %11.0f%% %11.0f%%' % ('헤즈업', frac(bo,lambda i:i.get('n_opp',1)<2), frac(ct,lambda i:i.get('n_opp',1)<2)))
    print('%-22s %11.0f%% %11.0f%%' % ('뒤 액션자 0명', frac(bo,lambda i:i.get('behind',0)==0), frac(ct,lambda i:i.get('behind',0)==0)))

    print()
    print('=' * 78)
    print('블러프 게이트 통과 가능성 (eq < 0.42 AND (made==0 or rel<0.30))')
    print('=' * 78)
    def bg(i):
        mw = 1 if i.get('n_opp',1)>=2 else 0
        return i['eq'] < 0.42 and (i['made']==0 or i['rel']<0.30)
    print('  B only  %d / %d (%.0f%%)' % (sum(1 for i in bo if bg(i)), len(bo), frac(bo,bg)))
    print('  control %d / %d (%.0f%%)' % (sum(1 for i in ct if bg(i)), len(ct), frac(ct,bg)))
    print()
    print('  → 이 조건을 통과해도 bluff_ok 확률 롤이 남는다.')
    print('     즉 B-only 는 이미 bluff_2street 후보 자격은 있었고, 주사위에서 떨어졌다.')

    print()
    print('=' * 78)
    print('봇 유형 분포')
    print('=' * 78)
    cb=collections.Counter(i.get('type') for i in bo)
    cc=collections.Counter(i.get('type') for i in ct)
    for t in sorted(set(cb)|set(cc)):
        print('  %-16s B only %2d (%3.0f%%)   control %3d (%3.0f%%)' % (
            t, cb.get(t,0), 100*cb.get(t,0)/len(bo), cc.get(t,0), 100*cc.get(t,0)/len(ct)))


if __name__ == '__main__':
    main()
