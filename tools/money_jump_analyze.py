#!/usr/bin/env python3
"""이미 수집한 money_jump_obs.jsonl을 단계/스택/자리/커버관계로 해부한다.

관측값만 읽는다. 전략 임계값을 만들거나 행동을 바꾸지 않는다.
"""
import argparse, collections, json, math, statistics


def load(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(x) for x in f if x.strip()]


def pct(x):
    return '%.1f%%' % (100*x)


def quant(xs, p):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    i = min(len(xs)-1, max(0, int((len(xs)-1)*p)))
    return xs[i]


def sig(r, key):
    return (r.get('money_signals') or {}).get(key)


def stage(r):
    rem, itm = r.get('remaining'), r.get('itm')
    if not rem or not itm:
        return 'unknown'
    if rem <= 9:
        return 'final9'
    x = rem / itm
    if x > 1.50:
        return 'pre'
    if x > 1.20:
        return 'approach'
    if x > 1.00:
        return 'bubble'
    return 'itm'


def stack_bucket(r):
    """분석용 서술적 분위. 행동 임계값이 아니다."""
    f = r.get('shorter_frac')
    if f is None:
        return 'unknown'
    if f >= .80:
        return 'top20%'
    if f >= .50:
        return 'upper-mid'
    if f >= .20:
        return 'lower-mid'
    return 'bottom20%'


def buf_bucket(r):
    q = r.get('shorter_to_needed_ratio')
    if q is None:
        return 'no-next-jump'
    if q >= 1.5:
        return 'S>>J'
    if q >= 1.0:
        return 'S>=J'
    if q >= .5:
        return 'S<J'
    return 'S<<J'


def action_class(a):
    if a in ('bet', 'raise', 'allin'):
        return 'aggr'
    if a in ('call', 'check'):
        return 'passive'
    if a == 'fold':
        return 'fold'
    return 'other'


def summarize(rows, title):
    if not rows:
        return
    a = collections.Counter(action_class(r.get('action')) for r in rows)
    cover = sum(1 for r in rows if (r.get('covers_yet_to_act') or 0) > 0)
    danger = sum(1 for r in rows if (r.get('covered_by_yet_to_act') or 0) > 0)
    face = sum(1 for r in rows if r.get('facing_target'))
    print('%-30s n=%-5d fold=%5s aggr=%5s coverBehind=%5s coveredBehind=%5s facing=%5s' %
          (title, len(rows), pct(a['fold']/len(rows)), pct(a['aggr']/len(rows)),
           pct(cover/len(rows)), pct(danger/len(rows)), pct(face/len(rows))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    args = ap.parse_args()
    rows = load(args.path)

    print('rows', len(rows))

    if any(r.get('money_signals') for r in rows):
        print('\n[money-pressure signal quantiles p10 / p50 / p90]')
        for k in ('payout_importance', 'ladder_buffer', 'waiting_feasibility',
                  'self_preservation_objective', 'self_preservation',
                  'urgency_objective', 'urgency', 'commitment_budget'):
            xs=[sig(r,k) for r in rows if sig(r,k) is not None]
            if xs:
                print(' %-30s %.3f / %.3f / %.3f' %
                      (k, quant(xs,.10), quant(xs,.50), quant(xs,.90)))

        print('\n[signals by stage: means]')
        for st in ('pre','approach','bubble','itm','final9'):
            rr=[r for r in rows if stage(r)==st and r.get('money_signals')]
            if not rr:
                continue
            def avg(k):
                xs=[sig(r,k) for r in rr if sig(r,k) is not None]
                return sum(xs)/len(xs) if xs else 0.0
            print(' %-10s n=%-5d preserve=%.3f urgency=%.3f commit=%.3f' %
                  (st, len(rr), avg('self_preservation'),
                   avg('urgency'), avg('commitment_budget')))

        face=[r for r in rows if r.get('facing_pressure')]
        if face:
            print('\n[facing pressure quantiles]')
            for k in ('structural_pressure','theory_pressure',
                      'read_adjustment','pressure_opportunity'):
                xs=[r['facing_pressure'].get(k) for r in face
                    if r['facing_pressure'].get(k) is not None]
                if xs:
                    print(' %-30s %.3f / %.3f / %.3f' %
                          (k, quant(xs,.10), quant(xs,.50), quant(xs,.90)))
            adj=[r['facing_pressure'].get('read_adjustment',1.0) for r in face]
            non=sum(1 for x in adj if abs(float(x)-1.0) > 1e-9)
            print(' read-adjustment nonneutral   %d/%d  min=%.4f max=%.4f' %
                  (non, len(adj), min(adj), max(adj)))

        lcp=[r.get('low_commit_pressure') for r in rows
             if r.get('low_commit_pressure') is not None]
        if lcp:
            print('\n[low-commit pressure]')
            print(' p10/p50/p90 %.3f / %.3f / %.3f' %
                  (quant(lcp,.10), quant(lcp,.50), quant(lcp,.90)))

    print('\n[stage x stack percentile]')
    for st in ('approach', 'bubble', 'itm', 'final9'):
        for sb in ('top20%', 'upper-mid', 'lower-mid', 'bottom20%'):
            summarize([r for r in rows if stage(r)==st and stack_bucket(r)==sb],
                      '%s / %s' % (st, sb))

    print('\n[near ladder: buffer S/J]')
    near = [r for r in rows if stage(r) in ('approach','bubble','itm','final9')
            and r.get('shorter_to_needed_ratio') is not None]
    for b in ('S>>J','S>=J','S<J','S<<J'):
        summarize([r for r in near if buf_bucket(r)==b], b)

    print('\n[position]')
    for pos in ('UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN','SB','BB'):
        rr=[r for r in near if r.get('pos')==pos]
        if rr:
            summarize(rr, pos)

    print('\n[decision class]')
    for kind in ('unopened','vs_limp','vs_raise','free_action','facing_bet'):
        rr=[r for r in near if r.get('decision_kind')==kind]
        if rr:
            summarize(rr, kind)

    print('\n[preflop unopened x position]')
    pf_open=[r for r in near
             if r.get('street')=='preflop' and r.get('decision_kind')=='unopened']
    for pos in ('UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN','SB','BB'):
        rr=[r for r in pf_open if r.get('pos')==pos]
        if rr:
            summarize(rr, pos)

    print('\n[preflop vs raise: cover relation]')
    pf_raise=[r for r in near
              if r.get('street')=='preflop' and r.get('decision_kind')=='vs_raise']
    summarize([r for r in pf_raise if r.get('facing_target') and
               r['facing_target'].get('covers_me')],
              'vs covering raiser')
    summarize([r for r in pf_raise if r.get('facing_target') and
               r['facing_target'].get('i_cover')],
              'vs covered raiser')

    print('\n[waiting-cost diagnostics]')
    wc=[r for r in near if r.get('forced_cost_share_of_stack') is not None]
    if wc:
        vals=sorted(r['forced_cost_share_of_stack'] for r in wc)
        def qq(p):
            return vals[min(len(vals)-1, int((len(vals)-1)*p))]
        print(' forced_cost_share_of_stack p10/p50/p90 = %.3f / %.3f / %.3f' %
              (qq(.10), qq(.50), qq(.90)))
        stranded=[r for r in wc if (r.get('stack_after_next_bb_if_fold_all') or 0) <= 0]
        summarize(stranded, 'cannot survive to next BB')
        for r in sorted(stranded,
                        key=lambda x:(x.get('stack_behind_bb',9999),
                                      x.get('hands_to_next_bb',9999)))[:10]:
            print('   H%s %s %s rem=%s/%s stack=%sbb afterNextBB=%s handsToBB=%s S/J=%s kind=%s act=%s' %
                  (r.get('hand_no'), r.get('street'), r.get('pos'),
                   r.get('remaining'), r.get('itm'), r.get('stack_behind_bb'),
                   r.get('stack_after_next_bb_if_fold_all'),
                   r.get('hands_to_next_bb'), r.get('shorter_to_needed_ratio'),
                   r.get('decision_kind'), r.get('action')))

    print('\n[target topology]')
    summarize([r for r in near if (r.get('covered_by_yet_to_act') or 0)>0],
              'covering stack still behind')
    summarize([r for r in near if (r.get('covers_yet_to_act') or 0)>0],
              'hero covers someone behind')
    summarize([r for r in near if r.get('facing_target') and
               r['facing_target'].get('covers_me')],
              'facing covering aggressor')
    summarize([r for r in near if r.get('facing_target') and
               r['facing_target'].get('i_cover')],
              'facing covered aggressor')

    print('\n[extreme examples: protected vs unprotected]')
    for name, filt in (
        ('protected', lambda r: (r.get('shorter_to_needed_ratio') or -1) >= 1.5),
        ('unprotected', lambda r: r.get('shorter_to_needed_ratio') is not None
                                 and r.get('shorter_to_needed_ratio') < .5),
    ):
        xs=[r for r in near if filt(r)]
        xs=sorted(xs, key=lambda r:(r.get('stack_start_bb',9999),
                                    r.get('players_yet_to_act',9999)))[:8]
        print(' ', name)
        for r in xs:
            ft=r.get('facing_target') or {}
            print('   H%s %s %s rem=%s/%s stack=%sbb S/J=%s behind=%s cover=%s/%s facing=%s:%s act=%s' %
                  (r.get('hand_no'), r.get('street'), r.get('pos'),
                   r.get('remaining'), r.get('itm'), r.get('stack_start_bb'),
                   r.get('shorter_to_needed_ratio'), r.get('players_yet_to_act'),
                   r.get('covers_yet_to_act'), r.get('covered_by_yet_to_act'),
                   ft.get('pos'), ('covers' if ft.get('covers_me') else
                                   'covered' if ft.get('i_cover') else '-'),
                   r.get('action')))


if __name__ == '__main__':
    main()
