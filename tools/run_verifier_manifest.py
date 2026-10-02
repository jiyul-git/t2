#!/usr/bin/env python3
"""Run verifier scripts and record status (used to build CANONICAL_VERIFIER_MANIFEST).

usage: python tools/run_verifier_manifest.py [--root DIR] [--tier gate|suite40|all|NAME,...]
                                             [--timeout SEC] [--jobs N] [--out FILE]
Tiers come from docs/semantic_audit/CANONICAL_VERIFIER_MANIFEST.json when it exists;
'all' runs every tools/verify_*.py found under --root.
"""
import argparse, concurrent.futures as cf, glob, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def names_for(tier, root):
    allv = sorted(os.path.basename(p)[len('verify_'):-3]
                  for p in glob.glob(os.path.join(root, 'tools', 'verify_*.py')))
    if tier == 'all':
        return allv
    man = os.path.join(HERE, 'docs', 'semantic_audit', 'CANONICAL_VERIFIER_MANIFEST.json')
    if tier in ('gate', 'suite40', 'gate23', 'fast', 'release') and os.path.exists(man):
        rows = json.load(open(man, encoding='utf-8'))['verifiers']
        key = {'gate': 'in_gate23', 'gate23': 'in_gate23', 'suite40': 'in_suite40'}.get(tier)
        if key:
            return [r['name'] for r in rows if r.get(key)]
        return [r['name'] for r in rows if tier in (r.get('tiers') or [])]
    return [x.strip() for x in tier.split(',') if x.strip()]


def run_one(root, name, timeout):
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, 'tools/verify_%s.py' % name], cwd=root,
                           capture_output=True, text=True, timeout=timeout)
        rc = r.returncode
        tail = (r.stdout + r.stderr).strip().split('\n')[-1][:200]
    except subprocess.TimeoutExpired:
        rc, tail = 'TIMEOUT', ''
    return {'name': name, 'rc': rc, 'status': ('PASS' if rc == 0 else
                                               'TIMEOUT' if rc == 'TIMEOUT' else 'FAIL'),
            'seconds': round(time.time() - t0, 1), 'tail': tail}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=HERE)
    ap.add_argument('--tier', default='gate')
    ap.add_argument('--timeout', type=float, default=900)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--out')
    a = ap.parse_args()
    names = names_for(a.tier, a.root)
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        res = list(ex.map(lambda n: run_one(a.root, n, a.timeout), names))
    for r in res:
        print('%-36s %-7s %7.1fs  %s' % (r['name'], r['status'], r['seconds'], r['tail'][:90]))
    summ = {k: sum(1 for r in res if r['status'] == k) for k in ('PASS', 'FAIL', 'TIMEOUT')}
    print(json.dumps(summ))
    if a.out:
        json.dump({'root': a.root, 'tier': a.tier, 'results': res, 'summary': summ},
                  open(a.out, 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
