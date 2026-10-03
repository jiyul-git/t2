#!/usr/bin/env python3
"""Beta A #5: same-state attribution of the value_2street promotion fix.

At every plan.refresh call in the max-skill baseline sim, the retired refresh
(plan.py at OLD_REV, loaded as a separate module) is evaluated on deep copies of
the identical inputs.  refresh draws no shared RNG (only random.Random(seed)), so
the printed digest must equal the plain sim digest of the current tree.

Changes covered:
  * promotion after budget exhaustion compares made with the made level when the
    plan was adopted (plan_made), not the previous street;
  * stored (2-decimal) previous rel is compared at the same precision.

  OLD_REV=1ac21231 OUT=attr.json python tools/fix5_attribution.py SEED [CAP]
"""
import collections, copy, importlib.util, json, os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import r2_baseline_sim as SIM
import plan as PL

rev = os.environ.get('OLD_REV', '1ac21231')
src = subprocess.run(['git', '-C', ROOT, 'show', '%s:plan.py' % rev], capture_output=True, check=True).stdout
tmp = tempfile.NamedTemporaryFile('wb', suffix='.py', delete=False)
tmp.write(src); tmp.close()
spec = importlib.util.spec_from_file_location('plan_old', tmp.name)
OLD = importlib.util.module_from_spec(spec); spec.loader.exec_module(OLD)

C = collections.Counter()
EX = []
_ref = PL.refresh


def refresh(state, *a, **k):
    st_in = copy.deepcopy(state)
    a_in = copy.deepcopy(a); k_in = copy.deepcopy(k)
    new = _ref(state, *a, **k)
    old = OLD.refresh(st_in, *a_in, **k_in)
    C['calls'] += 1
    if old.get('plan') != new.get('plan'):
        C['plan_diff'] += 1
        C['%s->%s|%s' % (old.get('plan'), new.get('plan'), a_in[6] if len(a_in) > 6 else '?')] += 1
        if len(EX) < 20:
            EX.append({'street': a_in[6] if len(a_in) > 6 else None, 'hero': a_in[0], 'board': a_in[1],
                       'prev_plan': st_in.get('plan'), 'old': old.get('plan'), 'new': new.get('plan'),
                       'made': new.get('made'), 'plan_made': st_in.get('plan_made'),
                       'rel': new.get('rel'), 'prev_rel': st_in.get('rel'),
                       'why_new': (new.get('why') or [])[-1:]})
    return new


PL.refresh = refresh
sys.argv = ['x', sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '60']
try:
    SIM.main()
finally:
    os.unlink(tmp.name)
    if os.environ.get('OUT'):
        json.dump({'counts': dict(C), 'examples': EX}, open(os.environ['OUT'], 'w'), indent=1, default=str)
    print(json.dumps(dict(C), sort_keys=True))
