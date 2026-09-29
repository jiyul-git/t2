#!/usr/bin/env python3
"""Verify Human Model v3 opponent-memory recency semantics.

No target poker frequency is fitted here.  The tests establish that the
existing observer memory parameter becomes a real recent-hand window while
legacy/OFF behavior and old saved books remain safe.
"""
import json, pathlib, random, tempfile, os, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import reads as RD


def observe_seq(seq, enabled=True):
    old=RD.READ_RECENCY_V3
    RD.READ_RECENCY_V3=enabled
    try:
        b=RD.Book()
        for vpip in seq:
            b.observe_preflop(['obs'],'vill',bool(vpip),bool(vpip),
                              limp=False,limp_chance=True,rfi_exp=.25)
        return b
    finally:
        RD.READ_RECENCY_V3=old


def observer_profile(att, adp, rr=5.0, st=5.0, cons=5.0):
    return {
        'concepts': {'range_read':rr,'sizing_tell':st},
        'temper': {'attention':float(att),'adaptability':float(adp),
                   'consistency':float(cons)}
    }


def main():
    checks={}

    # R1: OFF is truly inert: no history state is created.
    b0=observe_seq(([0,1]*20), enabled=False)
    r0=b0.rec('obs','vill')
    checks['R1_off_does_not_mutate_book_shape']={
        'pass':'_hand_hist' not in r0,
        'hands':r0['hands'],'vpip':r0['vpip']}

    # R2/R3: 80 tight hands followed by 20 loose hands.
    old=RD.READ_RECENCY_V3
    RD.READ_RECENCY_V3=True
    try:
        b=observe_seq([0]*80+[1]*20, enabled=True)
        r=b.rec('obs','vill')
        v20=RD._recent_record(r,20)
        v100=RD._recent_record(r,100)
        checks['R2_recent_reversal_expires_old_phase']={
            'pass':(v20['hands']==20 and v20['vpip']==20),
            'recent20_hands':v20['hands'],'recent20_vpip':v20['vpip'],
            'lifetime_hands':r['hands'],'lifetime_vpip':r['vpip']}
        checks['R3_memory_length_changes_adaptation']={
            'pass':(v20['vpip']/v20['hands'] > v100['vpip']/v100['hands']),
            'memory20_vpip_rate':round(v20['vpip']/v20['hands'],4),
            'memory100_vpip_rate':round(v100['vpip']/v100['hands'],4)}

        # R4: stationary 50% behavior stays 50% after windowing.
        bs=observe_seq([0,1]*100, enabled=True)
        rs=bs.rec('obs','vill')
        vs=RD._recent_record(rs,20)
        checks['R4_stationary_process_unbiased']={
            'pass':(vs['hands']==20 and vs['vpip']==10),
            'recent20_rate':round(vs['vpip']/max(1,vs['hands']),4)}

        # R5: estimate() must consume recent n, not only cap confidence.
        # memory = 6*attention + 4*adaptability = 20.
        short=observer_profile(2,2)
        est=RD.estimate(b,'obs','vill',short,random.Random(12345))
        checks['R5_estimate_consumes_recent_view']={
            'pass':(est['n']==20 and est['vpip'] > .70),
            'estimated_n':est['n'],'estimated_vpip':round(est['vpip'],4),
            'observer_memory':RD.obs_from_profile(short)['memory']}

        # R6: all cumulative event counters window together, not just VPIP.
        # Add a postflop event each hand to a fresh book, with only the last
        # 10 folding to bets. Snapshots occur at next preflop boundary.
        bx=RD.Book()
        for h in range(40):
            bx.observe_preflop(['obs'],'vill',False,False,
                               limp=False,limp_chance=True,rfi_exp=.25)
            bx.observe_postflop(['obs'],'vill',
                                'fold' if h>=30 else 'call',
                                is_cbet_spot=True,is_barrel_spot=False,
                                facing_bet=True,street='flop')
        rx=bx.rec('obs','vill')
        vx=RD._recent_record(rx,10)
        checks['R6_postflop_counters_share_same_window']={
            'pass':(vx['hands']==10 and vx['facing_bet']==10
                    and vx['fold_to_bet']==10
                    and vx['cbet_opp']==10),
            'recent':{k:vx[k] for k in
                      ('hands','facing_bet','fold_to_bet','cbet_opp','cbet')}}

        # R7: history is bounded by max memory + one baseline.
        checks['R7_history_is_bounded']={
            'pass':len(rs.get('_hand_hist',[])) <= RD._MAX_RECENCY_HISTORY,
            'history_len':len(rs.get('_hand_hist',[])),
            'limit':RD._MAX_RECENCY_HISTORY}

        # R8: JSON save/load preserves snapshots; a legacy book without them
        # loads safely and stays lifetime until enough new history exists.
        with tempfile.TemporaryDirectory() as td:
            p=os.path.join(td,'book.json')
            RD.save_book(b,p)
            bl=RD.load_book(p)
            rl=bl.rec('obs','vill')
            loaded=RD._recent_record(rl,20)

            legacy=RD.Book()
            lr=legacy.rec('obs','vill')
            lr['hands']=100; lr['vpip']=20; lr['pfr']=10
            lp=os.path.join(td,'legacy.json')
            RD.save_book(legacy,lp)
            legacy2=RD.load_book(lp)
            lview=RD._recent_record(legacy2.rec('obs','vill'),20)

        checks['R8_save_load_and_legacy_safe']={
            'pass':(loaded['hands']==20 and loaded['vpip']==20
                    and lview['hands']==100 and lview['vpip']==20),
            'loaded_recent':{'hands':loaded['hands'],'vpip':loaded['vpip']},
            'legacy_fallback':{'hands':lview['hands'],'vpip':lview['vpip']}}

    finally:
        RD.READ_RECENCY_V3=old

    passed=all(v['pass'] for v in checks.values())
    print(json.dumps({'pass':passed,'checks':checks},indent=2,sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':
    main()
