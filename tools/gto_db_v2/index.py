#!/usr/bin/env python3
"""T2 GTO solution index: legacy DB (read-only) + new append-only DB, both keyed by spot_key(canonical_state).

    python3 tools/gto_db_v2/index.py stats
    python3 tools/gto_db_v2/index.py lookup --state state.json [--hand AKs]
    python3 tools/gto_db_v2/index.py need --state state.json --tier 2 [--expl 0.3]

Rules
  * legacy data/gto_db/preflop_9max_pushfold_v1.jsonl (616 rows) is never modified or moved: it is read in place if present,
    otherwise from its pinned git blob; its bytes must match the pinned sha256.
  * new solver results go to data/gto_db_v2/solutions.jsonl (schema gto_solution_v2), keyed by spot_key only.
  * need_compute(state, target_quality) requires the quality the caller will produce; it is False (skip) when the best
    stored solution is at least as good, True when the spot is empty or the target is strictly better.
  * add_solution() never deletes or rewrites: a solution for an existing spot is appended only if its quality is strictly
    higher; identical content (same solution_id) is never duplicated. lookup() returns the best; all() returns every one.
Quality comparison better(new, old) (a partial order; 'lower is better'):
  1. tier: a lower tier is better.
  2. same tier, at least one exploitability_pct_pot known: compare it (None = worst), strictly lower wins.
  3. same tier, both exploitability_pct_pot None: only if both carry quality.comparable with the SAME family and metric
     (family = one solver + one game abstraction / config, e.g. "gtopen_preflop|config_sha256:<hash>") is the secondary
     convergence metric (e.g. GTOpen gap_total) compared, strictly lower wins. Different solvers / methods / configs are
     incomparable: never better, so no upgrade and no skip-override happen on gap numbers from different families.
  best(spot) = the earliest-added solution that no other stored solution beats.
Seed replicates: storage is append-only and best-only for upgrades. A replicate (same family, other seed) is stored only if it
is strictly better than the current best; equal or worse replicates are skipped, not kept (a replicate study belongs in its
own log, not in this store).
  tier 1  exact game, full tree, converged at the stated target
  tier 2  converged solver solution of an abstracted tree (restricted action menu / bucketing)
  tier 3  solver solution with a known approximation (estimated continuation values, frozen ranges, capped/non-converged)
  tier 4  external reference / approximate model (e.g. the legacy push-fold import)
A 3-way or multiway research approximation is tier 3 at best and is never labelled GTO.
"""
import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spot_key as SK  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEGACY = {
    'path': 'data/gto_db/preflop_9max_pushfold_v1.jsonl',
    'git_blob': '003078a5edc81bc45cbe157c824a66799e15055e',   # origin/chatgpt/gto-reference-20260928
    'sha256': 'bacf94e93cfdab443145e58bcafe2eaa007f662bf3a5fd43f06d47d123616c87',
    'rows': 616,
}
V2 = os.path.join(ROOT, 'data/gto_db_v2/solutions.jsonl')
SCHEMA = 'gto_solution_v2'
TIERS = {1: 'exact_full_tree_converged', 2: 'solver_abstracted_converged', 3: 'solver_approximate', 4: 'external_reference_approximate'}


def quality_key(q):
    """sort / display key (tier, exploitability or inf, comparable value or inf); the decision rule is better()."""
    e = q.get('exploitability_pct_pot')
    c = (q.get('comparable') or {}).get('value')
    return (int(q['tier']), float('inf') if e is None else float(e), float('inf') if c is None else float(c))


def better(q_new, q_old):
    tn, to = int(q_new['tier']), int(q_old['tier'])
    if tn != to:
        return tn < to
    en, eo = q_new.get('exploitability_pct_pot'), q_old.get('exploitability_pct_pot')
    if en is not None or eo is not None:
        return (float('inf') if en is None else float(en)) < (float('inf') if eo is None else float(eo))
    cn, co = q_new.get('comparable') or {}, q_old.get('comparable') or {}
    if cn and co and cn.get('family') == co.get('family') and cn.get('metric') == co.get('metric') \
            and cn.get('value') is not None and co.get('value') is not None:
        return float(cn['value']) < float(co['value'])
    return False   # incomparable (different solver / method / config family, or no metric)


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def legacy_bytes():
    p = os.environ.get('T2_GTO_LEGACY_DB') or os.path.join(ROOT, LEGACY['path'])
    if os.path.exists(p):
        b = open(p, 'rb').read()
        where = p
    else:
        b = subprocess.run(['git', '-C', ROOT, 'cat-file', 'blob', LEGACY['git_blob']], check=True, capture_output=True).stdout
        where = f"git blob {LEGACY['git_blob']}"
    if hashlib.sha256(b).hexdigest() != LEGACY['sha256']:
        raise SystemExit(f'legacy DB at {where} does not match the pinned sha256 (it must never be modified)')
    return b, where


def legacy_state(c):
    """legacy gto_spot_v1 conditions -> raw state for canonical_state."""
    ante = c['ante']
    raw = {'table_players': 9, 'hero': c['hero_position'], 'stacks_bb': c['prehand_stack_bb'], 'blinds_bb': c['blinds_bb'],
           'ante': {'model': ante['model'], 'amount_bb': ante.get('per_player_bb', 0)}, 'format': 'MTT', 'icm': None if not c['icm'] else c['icm'],
           'rake': {'pct': c['rake'], 'cap_bb': 0}}
    t = c['history_template']['type']
    if t == 'unopened':
        raw['history'] = []
    elif t == 'face_shove':
        raw['history'] = [{'pos': c['history_template']['shover_position'], 'act': 'allin'}]
    else:
        raise ValueError(f'legacy history template {t!r}')
    return raw


def legacy_solution(r):
    k, st = SK.key_of(legacy_state(r['conditions']))
    acts = [a for a in r['conditions']['allowed_actions']]
    hands = {h: {'freq': {a: v[a] for a in acts}, 'ev_bb': {'_reported': v.get('action_ev_bb')}} for h, v in r['strategy']['hands'].items()}
    return {'schema': 'legacy_view', 'spot_key': k, 'canonical_state': st, 'solution_id': 'legacy:' + r['sha256'],
            'quality': {'tier': 4, 'exploitability_pct_pot': None, 'method': r['source']['model'], 'status': r['quality']['status'],
                        'notes': r['quality'].get('t2_mismatch', [])},
            'source': {'db': 'legacy', 'legacy_spot_id': r['spot_id'], **r['source']}, 'strategy': {'actions': acts, 'hands': hands},
            'added_at': None, 'legacy': True}


class Index:
    def __init__(self, v2_path=V2, with_legacy=True):
        self.v2_path = v2_path
        self.by_key = {}
        self.ids = set()
        self.legacy_where = None
        if with_legacy:
            b, self.legacy_where = legacy_bytes()
            rows = [json.loads(l) for l in b.decode().splitlines() if l.strip()]
            if len(rows) != LEGACY['rows']:
                raise SystemExit('legacy row count changed')
            for r in rows:
                s = legacy_solution(r)
                if s['spot_key'] in self.by_key:
                    raise SystemExit(f"legacy spot_key collision: {s['spot_key']}")
                self._put(s)
        if os.path.exists(v2_path):
            for line in open(v2_path):
                if line.strip():
                    self._put(self._check(json.loads(line)))

    @staticmethod
    def _check(s):
        if s.get('schema') != SCHEMA:
            raise SystemExit(f"bad schema {s.get('schema')}")
        st = s['canonical_state']
        if SK.spot_key(st) != s['spot_key']:
            raise SystemExit(f"stored spot_key does not match its canonical_state: {s['spot_key']}")
        body = {k: v for k, v in s.items() if k not in ('solution_id', 'added_at')}
        if s['solution_id'] != 'v2:' + _sha(body):
            raise SystemExit(f"solution_id mismatch for {s['spot_key']}")
        return s

    def _put(self, s):
        self.by_key.setdefault(s['spot_key'], []).append(s)
        self.ids.add(s['solution_id'])

    def all(self, key):
        return sorted(self.by_key.get(key, []), key=lambda s: (quality_key(s['quality']), s['added_at'] or ''))

    def best(self, key):
        xs = self.by_key.get(key, [])
        undominated = [s for s in xs if not any(better(o['quality'], s['quality']) for o in xs if o is not s)]
        return min(undominated, key=lambda s: s['added_at'] or '') if undominated else None

    def lookup(self, raw_state):
        k, _ = SK.key_of(raw_state)
        return self.best(k)

    def need_compute(self, raw_state, target_quality):
        """target_quality is REQUIRED (workers must state the quality they will produce): compute only if the spot has no
        solution or the target is strictly better than the best stored one. 'Some solution exists' alone never decides."""
        if not isinstance(target_quality, dict) or int(target_quality.get('tier', 0)) not in TIERS:
            raise ValueError('need_compute requires target_quality {"tier": 1..4, "exploitability_pct_pot": float|None}')
        k, _ = SK.key_of(raw_state)
        b = self.best(k)
        if b is None:
            return True, k, 'no solution for this spot'
        if better(target_quality, b['quality']):
            return True, k, f"target quality {quality_key(target_quality)} beats best stored {quality_key(b['quality'])}"
        return False, k, f"skip: stored {b['solution_id']} quality {quality_key(b['quality'])} is not worse than target {quality_key(target_quality)}"

    def add_solution(self, raw_state, strategy, quality, source):
        """append a new solution; returns (added, spot_key, reason). Never deletes or rewrites."""
        if int(quality['tier']) not in TIERS:
            raise ValueError('quality.tier must be 1..4')
        k, st = SK.key_of(raw_state)
        body = {'schema': SCHEMA, 'spot_key': k, 'canonical_state': st, 'spot_label': SK.label(st), 'quality': quality,
                'source': source, 'strategy': strategy}
        sid = 'v2:' + _sha(body)
        if sid in self.ids:
            return False, k, 'identical solution already stored'
        b = self.best(k)
        if b is not None and not better(quality, b['quality']):
            return False, k, f"skip: not strictly better than stored {b['solution_id']} {quality_key(b['quality'])}"
        rec = {**body, 'solution_id': sid, 'added_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        os.makedirs(os.path.dirname(self.v2_path), exist_ok=True)
        with open(self.v2_path, 'a') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(rec, sort_keys=True, separators=(',', ':')) + '\n')
            f.flush()
            os.fsync(f.fileno())
        self._put(rec)
        return True, k, 'added' if b is None else f"added (supersedes {b['solution_id']} as best; old kept)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['stats', 'lookup', 'need'])
    ap.add_argument('--state')
    ap.add_argument('--hand')
    ap.add_argument('--tier', type=int)
    ap.add_argument('--expl', type=float)
    a = ap.parse_args()
    ix = Index()
    if a.cmd == 'stats':
        n = sum(len(v) for v in ix.by_key.values())
        print(json.dumps({'spots': len(ix.by_key), 'solutions': n, 'legacy_source': ix.legacy_where, 'v2': ix.v2_path}))
        return
    raw = json.load(open(a.state))
    if a.cmd == 'need':
        if not a.tier:
            raise SystemExit('need: --tier (and --expl if known) is required')
        tq = {'tier': a.tier, 'exploitability_pct_pot': a.expl}
        print(json.dumps(dict(zip(('compute', 'spot_key', 'reason'), ix.need_compute(raw, tq)))))
        return
    b = ix.lookup(raw)
    if b is None:
        print(json.dumps({'spot_key': SK.key_of(raw)[0], 'found': False}))
        return
    out = {'spot_key': b['spot_key'], 'found': True, 'solution_id': b['solution_id'], 'quality': b['quality'], 'label': SK.label(b['canonical_state']),
           'alternatives': len(ix.all(b['spot_key'])) - 1}
    if a.hand:
        out['hand'] = b['strategy']['hands'].get(a.hand)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
