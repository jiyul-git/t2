#!/usr/bin/env python3
"""F7-B blocker representation audit.

Diagnostic only.

Question:
Does the perceived opponent range preserve hero-blocked combos long enough for
blocker_score/blocker_effect to measure the counterfactual removal, while equity
still excludes impossible combos itself?

Current special case:
runner.adjust_range_by_history() filters hero hole cards only when it widens a
range from showdown history.  Most other perceived-range paths preserve those
combos.  That makes blocker semantics depend on range provenance.

This tool:
1) proves equity_vs_combos removes hero-overlapping combos itself;
2) fixed fixture reproduces history-widening blocker loss;
3) live wrapper counts how often history adjustment widens ranges and how much
   blocker signal differs from a board-only-dead counterfactual widening.
"""
import argparse
import json
import os
import statistics
import sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

import bot
import preflop as pf
import ranges as R
import runner as RU
import tourney as T


def _parse_seeds(s):
    out=[]
    for p in str(s).split(','):
        p=p.strip()
        if not p: continue
        if '-' in p:
            a,b=p.split('-',1); out.extend(range(int(a),int(b)+1))
        else:
            out.append(int(p))
    return out


class _Dyn:
    def __init__(self, shown):
        self._shown=shown
    def shown(self,pid):
        return list(self._shown)


def _weak_shown():
    # Pick two actually weak preflop combos by percentile, not hard-coded rank names.
    weak=[c for c in R._SORTED if pf.PCT[pf.cls(list(c))] > 0.60]
    assert len(weak)>=2
    return [list(weak[-1]),list(weak[-2])]


def _expanded_board_only(base,dyn,pid,board,dead=None):
    """Mirror only the med>0.55 branch, but preserve hero-blocked combos.

    Board cards are impossible for everyone and must be removed.
    Hero cards stay in the *counterfactual perceived range* so blocker metrics
    can measure what hero blocks; equity consumers filter them later.
    """
    shown=dyn.shown(pid) if hasattr(dyn,'shown') else []
    if len(shown)<2 or not base:
        return list(base),None
    import statistics as _st
    pcts=[pf.PCT[pf.cls(h)] for h in shown[-6:] if isinstance(h,list)]
    if not pcts:
        return list(base),None
    med=_st.median(pcts)
    if med<=0.55:
        return list(base),None
    cap=min(0.9,max(pf.PCT[pf.cls(list(c))] for c in base)*1.5)
    seen=set(board or [])
    wider=[c for c in R._SORTED
           if pf.PCT[pf.cls(list(c))] <= cap
           and c[0] not in seen and c[1] not in seen]
    return wider,'wide'


def fixed_checks():
    hero=['As','Kd']
    board=['2c','7d','Jh']
    # Base range deliberately board-only dead, matching normal postflop construction.
    base=R.preflop_range(
        'TAG','BTN','open',50,set(board),seats=9,ante=True)
    dyn=_Dyn(_weak_shown())

    current,note=RU.adjust_range_by_history(
        base,dyn,'villain',board,dead=set(hero)|set(board))
    alt,_=_expanded_board_only(
        base,dyn,'villain',board,dead=set(hero)|set(board))

    assert note and '확대' in note,note
    assert all(c[0] not in hero and c[1] not in hero for c in current)
    assert any(c[0] in hero or c[1] in hero for c in alt)

    # Equity implementation independently rejects hero overlaps.
    e_current=bot.equity_vs_combos(hero,board,[current],sims=1200,seed=17)
    e_alt=bot.equity_vs_combos(hero,board,[alt],sims=1200,seed=17)

    # With same compatible pool contents, impossible blocked combos do not alter equity.
    clean_alt=sorted(c for c in alt
                     if c[0] not in set(hero)|set(board)
                     and c[1] not in set(hero)|set(board))
    assert clean_alt==sorted(current),(len(clean_alt),len(current))
    assert abs(e_current-e_alt)<1e-12,(e_current,e_alt)

    bs_cur=R.blocker_score(hero,current,board)
    bs_alt=R.blocker_score(hero,alt,board)
    be_cur=R.blocker_effect(hero,current,board,'flop',0.60,False)
    be_alt=R.blocker_effect(hero,alt,board,'flop',0.60,False)

    assert bs_cur==0.0,bs_cur
    assert be_cur==0.0,be_cur
    assert bs_alt!=0.0 or be_alt!=0.0,(bs_alt,be_alt)

    return {
        'history_widened':True,
        'current_n':len(current),
        'counterfactual_n':len(alt),
        'equity_identical':True,
        'current_blocker_score':round(bs_cur,6),
        'counterfactual_blocker_score':round(bs_alt,6),
        'current_blocker_effect':round(be_cur,6),
        'counterfactual_blocker_effect':round(be_alt,6),
        'provenance_changes_blocker_semantics':True,
    }


def run(seeds,hands):
    orig=RU.adjust_range_by_history
    rows=[]
    counts={
        'adjust_calls':0,
        'history_widen_calls':0,
        'widen_with_hero_dead':0,
        'widen_blocker_signal_lost':0,
    }

    def wrapped(base_range,dyn,pid,board,dead=None):
        counts['adjust_calls']+=1
        out,note=orig(base_range,dyn,pid,board,dead=dead)
        if note and '확대' in note:
            counts['history_widen_calls']+=1
            hero_only=set(dead or [])-set(board or [])
            if hero_only:
                counts['widen_with_hero_dead']+=1
                alt,_=_expanded_board_only(
                    base_range,dyn,pid,board,dead=dead)
                hero=sorted(hero_only)
                if len(hero)==2:
                    cur_s=R.blocker_score(hero,out,board)
                    alt_s=R.blocker_score(hero,alt,board)
                    cur_e=R.blocker_effect(
                        hero,out,board,
                        'river' if len(board)>=5 else
                        ('turn' if len(board)==4 else 'flop'),
                        0.75 if len(board)>=5 else (0.70 if len(board)==4 else 0.60),
                        False)
                    alt_e=R.blocker_effect(
                        hero,alt,board,
                        'river' if len(board)>=5 else
                        ('turn' if len(board)==4 else 'flop'),
                        0.75 if len(board)>=5 else (0.70 if len(board)==4 else 0.60),
                        False)
                    if abs(cur_s-alt_s)>1e-12 or abs(cur_e-alt_e)>1e-12:
                        counts['widen_blocker_signal_lost']+=1
                    rows.append({
                        'board_len':len(board),
                        'base_n':len(base_range or []),
                        'current_n':len(out or []),
                        'counterfactual_n':len(alt or []),
                        'current_score':cur_s,
                        'counterfactual_score':alt_s,
                        'current_effect':cur_e,
                        'counterfactual_effect':alt_e,
                    })
        return out,note

    RU.adjust_range_by_history=wrapped
    try:
        for sd in seeds:
            t=T.Tournament(entries=100,start_stack=30000,hero_seat=7,
                           seed=sd,hands_per_level=200)
            for _ in range(hands):
                if sum(1 for s in t.seats if t.stacks[s]>0)<3:
                    break
                st=t.next_hand(); guard=0
                while st and not st.get('done') and guard<200:
                    st=t.submit('fold'); guard+=1
                t.finish_hand()
    finally:
        RU.adjust_range_by_history=orig

    return {
        'seeds':seeds,
        'hands_per_seed':hands,
        'counts':counts,
        'rows':rows[:20],
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='3000-3005')
    ap.add_argument('--hands',type=int,default=30)
    a=ap.parse_args()

    print('PASS F7-B blocker representation fixed fixture',fixed_checks())
    print(json.dumps(run(_parse_seeds(a.seeds),a.hands),indent=2,sort_keys=True))
    print()
    print('PASS F7-B blocker representation live audit completed')
    print('NOTE: production behavior unchanged.')


if __name__=='__main__':
    main()
