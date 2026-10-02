#!/usr/bin/env python3
"""R2-B: compare current defend-derived values only against completed 9-max GTO DB spots.

Read-only.  Sources are read straight from the GTO DB branch with `git show`
(nothing is vendored into this branch):

  data/gto_db/preflop_9max_pushfold_v1.jsonl   HoldemMath 9-max push/fold (CC BY 4.0),
      completed call-vs-shove spots, 4-20bb, variant ante 0.1bb/player (0.9bb total)
  data/gto_db/external_rfi_crosscheck_9max.json  PreflopRanges public 9-max MTT RFI aggregates
      (manual aggregate cross-check, 20/25/30/40bb)

What is compared:
  1. call vs first-in shove: current legacy calloff width
       preflop.calloff_cap = defend_thresholds(tot) x CALLOFF_TIGHTEN x 2.6 x (1-0.18 feel) / bf
     (the defend prior's only consumer for facing a jam) vs the DB call frequency,
     plus set agreement of the pf_rank top-cap slice with the DB call set.
  2. the defend prior's input gto.rfi(opener) for 9-max vs the RFI cross-check.

Non-all-in vs-open defense, vs-3bet and 4bet have no completed 9-max DB spot:
they are reported as MISSING_KNOWLEDGE, not compared with any solver output.
The project's own GTOpen / mini-CFR solver outputs are NOT used.

Usage: python tools/r2_gto_db_compare.py [GTO_DB_REF] [out.json]
       (default ref origin/chatgpt/gto-reference-20260928)
"""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import preflop as PF, gto as G  # noqa: E402
from r2_freeze_defend_baseline import maxskill, CLASSES, N_COMBO  # noqa: E402

POS = {'utg': 'UTG', 'utg1': 'UTG+1', 'mp': 'UTG+2', 'lj': 'LJ', 'hj': 'HJ', 'co': 'CO',
       'btn': 'BTN', 'sb': 'SB', 'bb': 'BB'}


def show(ref, path):
    return subprocess.check_output(['git', '-C', ROOT, 'show', '%s:%s' % (ref, path)], text=True)


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else 'origin/chatgpt/gto-reference-20260928'
    out = sys.argv[2] if len(sys.argv) > 2 else None
    ref_sha = subprocess.check_output(['git', '-C', ROOT, 'rev-parse', ref], text=True).strip()
    prof = maxskill()
    order = sorted(CLASSES, key=lambda k: (PF.PCT[k], k))
    rows = []
    for line in show(ref, 'data/gto_db/preflop_9max_pushfold_v1.jsonl').splitlines():
        r = json.loads(line)
        c = r['conditions']
        if c.get('scenario') != 'call_vs_shove' or c['ante']['model'] != 'per_player':
            continue
        bb = int(c['prehand_stack_bb'])
        if bb < 10:
            continue
        hero, sh = POS[c['hero_position'].lower()], POS[c['shover_position'].lower()]
        hands = r['strategy']['hands']
        db_call = sum(N_COMBO[k] * float(hands.get(k, {}).get('call', 0)) for k in CLASSES) / 1326
        cap = PF.calloff_cap(prof, hero, sh, float(bb), float(bb), 1, bf=1.0, exploit=None,
                             n_callers=0, seats=9, ante=True)
        # agreement: DB call mass inside the code's top-cap slice (the code calls r <= cap)
        inside = sum(N_COMBO[k] * float(hands.get(k, {}).get('call', 0))
                     for k in CLASSES if PF.PCT[k] <= cap) / 1326
        rows.append({'spot_id': r['spot_id'], 'stack_bb': bb, 'shover': sh, 'caller': hero,
                     'db_call': round(db_call, 4), 'code_calloff_cap': round(cap, 4),
                     'diff': round(cap - db_call, 4),
                     'set_agreement': round(inside / db_call, 4) if db_call else None,
                     'db_status': r['quality']['status'], 'db_sha256': r['sha256']})
    xc = json.loads(show(ref, 'data/gto_db/external_rfi_crosscheck_9max.json'))
    rfi_rows = []
    for st, v in xc['stacks'].items():
        for pos, w in v['rfi'].items():
            rfi_rows.append({'stack_bb': int(st), 'pos': pos, 'public_rfi': w,
                             'code_rfi': round(G.rfi(pos, 9, float(st), True), 4),
                             'diff': round(G.rfi(pos, 9, float(st), True) - w, 4),
                             'public_open_to_bb': v['open_to_bb'][pos]})
    res = {'gto_db_ref': ref, 'gto_db_commit': ref_sha,
           'calloff_vs_db': rows, 'rfi_vs_public_crosscheck': rfi_rows,
           'missing_knowledge': ['9-max non-all-in vs-open defend (call/3bet/fold), all stacks',
                                 '9-max opener vs 3bet', '9-max 4bet / cold 4bet / squeeze',
                                 '9-max reshove over a non-all-in open']}
    if out:
        open(out, 'w').write(json.dumps(res, indent=1) + '\n')
    return res


if __name__ == '__main__':
    res = main()
    import statistics as S
    for bb in (10, 12, 15, 20):
        rr = [r for r in res['calloff_vs_db'] if r['stack_bb'] == bb]
        print(bb, 'n', len(rr), 'mean db_call %.3f code_cap %.3f mean|diff| %.3f agreement %.3f' % (
            S.mean(r['db_call'] for r in rr), S.mean(r['code_calloff_cap'] for r in rr),
            S.mean(abs(r['diff']) for r in rr), S.mean(r['set_agreement'] for r in rr if r['set_agreement'])))
    for r in res['calloff_vs_db']:
        if r['caller'] in ('BB', 'SB') and r['shover'] in ('BTN', 'CO', 'UTG', 'SB'):
            print(r['stack_bb'], r['shover'], '->', r['caller'], r['db_call'], r['code_calloff_cap'], r['set_agreement'])
    for r in res['rfi_vs_public_crosscheck']:
        print('rfi', r['stack_bb'], r['pos'], r['public_rfi'], r['code_rfi'], r['diff'])
