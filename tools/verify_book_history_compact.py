#!/usr/bin/env python3
"""Compact recency history (L161 prerequisite): exact equivalence with the old
full-snapshot history, legacy-book continuation, and size reduction.

The reference implementation is reads.py at REF (default HEAD~ of the change,
override with REF=<rev>).  Random observation streams with integer and float
counters are applied to both books; _recent_record must match exactly for every
memory 1..125 at every step.
"""
import copy, importlib.util, json, os, random, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import reads as NEW

REF = os.environ.get('REF', '3e64a392')
src = subprocess.run(['git', '-C', ROOT, 'show', '%s:reads.py' % REF], capture_output=True, check=True).stdout
tf = tempfile.NamedTemporaryFile('wb', suffix='.py', delete=False); tf.write(src); tf.close()
spec = importlib.util.spec_from_file_location('reads_old', tf.name)
OLD = importlib.util.module_from_spec(spec); spec.loader.exec_module(OLD)
os.unlink(tf.name)


def step(rng, mods, books, actor='v'):
    vpip = rng.random() < 0.3
    pfr = vpip and rng.random() < 0.5
    for M, b in zip(mods, books):
        b.observe_preflop(['o'], actor, vpip, pfr)
    if rng.random() < 0.5:
        st = rng.choice(['flop', 'turn', 'river'])
        act = rng.choice(['bet', 'check', 'call', 'fold', 'raise'])
        fb = rng.random() < 0.4
        cb = rng.random() < 0.3
        for b in books:
            b.observe_postflop(['o'], actor, act, cb, False, facing_bet=fb, street=st)
        if act in ('bet', 'raise'):
            sz = rng.choice([0.33, 0.5, 0.66, 0.75, 1.0, 1.37])
            for b in books:
                b.observe_size(['o'], actor, sz, st)


def run(seed, n_hands, legacy_prefix=0):
    rng = random.Random(seed)
    old = OLD.Book()
    new = NEW.Book() if not legacy_prefix else OLD.Book()
    mism = 0; checks = 0
    for i in range(n_hands):
        if legacy_prefix and i == legacy_prefix:
            nb = NEW.Book(); nb.d = copy.deepcopy(new.d); new = nb   # old-format book continued by new code
        step(rng, [OLD, NEW], [old, new])
        ro, rn = old.rec('o', 'v'), new.rec('o', 'v')
        for m in range(1, 126):
            a = OLD._recent_record(ro, m); b = NEW._recent_record(rn, m)
            # the history field itself is storage, not an observation (format differs)
            a = {k: v for k, v in a.items() if k != '_hand_hist'}
            b = {k: v for k, v in b.items() if k != '_hand_hist'}
            checks += 1
            if json.dumps(a, sort_keys=True, default=str) != json.dumps(b, sort_keys=True, default=str):
                mism += 1
    so = len(json.dumps(old.d)); sn = len(json.dumps(new.d))
    return mism, checks, so, sn


def main():
    out = {}
    tot = 0; mism = 0
    for seed in range(6):
        m, c, so, sn = run(seed, 260)
        tot += c; mism += m
        out.setdefault('sizes', []).append([so, sn])
    out['E_exact_equivalence'] = {'pass': mism == 0, 'checks': tot, 'mismatch': mism}
    lm = 0; lc = 0
    for seed in range(3):
        m, c, _, _ = run(100 + seed, 220, legacy_prefix=90)
        lm += m; lc += c
    out['L_legacy_book_continuation'] = {'pass': lm == 0, 'checks': lc, 'mismatch': lm}
    so, sn = out['sizes'][0]
    out['S_size_reduction'] = {'pass': sn < so / 4, 'old_bytes': so, 'new_bytes': sn,
                               'ratio': round(sn / so, 3)}
    ok = all(v['pass'] for k, v in out.items() if isinstance(v, dict))
    print(json.dumps({'pass': ok, **{k: v for k, v in out.items() if k != 'sizes'}}, indent=1))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
