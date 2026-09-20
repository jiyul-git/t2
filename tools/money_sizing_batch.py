#!/usr/bin/env python3
"""Interrupt-safe parallel runner for tools/money_sizing_sweep.py.

This wrapper does not change the preregistered measurement. It runs the
existing sweep one seed at a time in separate processes, preserves each
completed seed, resumes finished seeds, and runs several independent seeds in
parallel. A heartbeat is printed while jobs are running.
"""
import argparse
import concurrent.futures as CF
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import money_sizing_sweep as MS


def paths(workdir, seed):
    stem = os.path.join(workdir, 'seed_%d' % seed)
    return stem + '.jsonl', stem + '.out', stem + '.done.json'


def run_one(seed, args, workdir):
    row, log, done = paths(workdir, seed)
    started = time.time()
    cmd = [
        sys.executable, '-u', os.path.join(TOOLS, 'money_sizing_sweep.py'),
        '--entries', str(args.entries),
        '--rounds', str(args.rounds),
        '--until-remaining', str(args.until_remaining),
        '--fmt', args.fmt,
        '--seed-start', str(seed),
        '--seeds', '1',
        '--out', row,
    ]
    with open(log, 'w', encoding='utf-8') as fp:
        fp.write('COMMAND ' + ' '.join(cmd) + '\n')
        fp.flush()
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=fp, stderr=subprocess.STDOUT)
        rc = p.wait()
    meta = {
        'seed': seed,
        'returncode': rc,
        'elapsed_sec': round(time.time() - started, 1),
        'row_file': row,
        'log_file': log,
        'row_exists': os.path.exists(row),
    }
    tmp = done + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(meta, fp, ensure_ascii=False, sort_keys=True)
        fp.write('\n')
    os.replace(tmp, done)
    return meta


def load_done(workdir, seed):
    row, log, done = paths(workdir, seed)
    try:
        with open(done, encoding='utf-8') as fp:
            meta = json.load(fp)
    except (OSError, ValueError):
        return None
    if meta.get('seed') != seed or not os.path.exists(row):
        return None
    return meta


def load_rows(path):
    out = []
    with open(path, encoding='utf-8') as fp:
        for line in fp:
            if line.strip():
                out.append(json.loads(line))
    return out


def aggregate(seeds, workdir, out_path):
    rows = []
    failed = []
    for seed in seeds:
        meta = load_done(workdir, seed)
        if meta is None:
            raise RuntimeError('seed %d is incomplete' % seed)
        if meta.get('returncode') != 0:
            failed.append((seed, meta.get('returncode')))
        row, _, _ = paths(workdir, seed)
        rows.extend(load_rows(row))

    tmp = out_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        for r in rows:
            fp.write(json.dumps(r, ensure_ascii=False) + '\n')
    os.replace(tmp, out_path)

    violations = []
    skill_strict = skill_equal = 0
    skill_deltas = []
    if not rows:
        violations.append('no near-ladder sizing rows were collected')

    for r in rows:
        b, s, sf, expected = MS.size_values(r)
        ident = 'seed=%s H%s T%s %s %s' % (
            r.get('seed'), r.get('hand_no'), r.get('table'),
            r.get('_sizing_stage'), r.get('pos'))
        if s < 2.0 - 1e-9:
            violations.append('%s shadow<2BB: %.3f' % (ident, s))
        if s > b + 1e-9:
            violations.append('%s shadow>base: %.3f>%.3f' % (ident, s, b))
        if abs(s - expected) > 0.0011:
            violations.append('%s formula mismatch: %.3f != %.3f' % (ident, s, expected))
        lo = MS.skill_counterfactual(r, 1.0)
        hi = MS.skill_counterfactual(r, 9.0)
        if hi > lo + 1e-9:
            violations.append('%s skill monotonic violation: %.3f -> %.3f' % (ident, lo, hi))
        elif hi < lo - 1e-9:
            skill_strict += 1
        else:
            skill_equal += 1
        skill_deltas.append(lo - hi)

    print('\n=== aggregated money sizing promotion check ===')
    print('seeds %d..%d rows=%d child_nonzero=%d' %
          (seeds[0], seeds[-1], len(rows), len(failed)))
    print('\n[by stage]')
    for st in MS.STAGES:
        MS.summarize(st, [r for r in rows if r.get('_sizing_stage') == st])
    print('\n[by position]')
    for pos in MS.POSITIONS:
        x = [r for r in rows if r.get('pos') == pos]
        if x:
            MS.summarize(pos, x)
    print('\n[same-state open_size skill 1 -> 9]')
    print('rows=%d strict_smaller=%d equal=%d delta p50/p90/max=%s/%s/%s' % (
        len(rows), skill_strict, skill_equal,
        MS.fmtq(MS.q(skill_deltas, .5)),
        MS.fmtq(MS.q(skill_deltas, .9)),
        MS.fmtq(max(skill_deltas) if skill_deltas else None)))
    print('\n[structural checks]')
    if failed:
        print('FAIL child process nonzero:', failed)
    elif violations:
        print('FAIL violations=%d' % len(violations))
        for v in violations[:30]:
            print(' -', v)
    else:
        print('PASS no structural violations')
    print('\nWROTE', out_path)
    return 1 if failed or violations else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--rounds', type=int, default=260)
    ap.add_argument('--until-remaining', type=int, default=8)
    ap.add_argument('--fmt', default='standard')
    ap.add_argument('--seed-start', type=int, default=92100)
    ap.add_argument('--seeds', type=int, default=20)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--heartbeat', type=int, default=30)
    ap.add_argument('--workdir', default='money_sizing_seeds')
    ap.add_argument('--out', default='money_sizing_sweep.jsonl')
    args = ap.parse_args()
    if args.seeds < 1 or args.workers < 1:
        ap.error('--seeds and --workers must be >= 1')

    workdir = os.path.abspath(args.workdir)
    os.makedirs(workdir, exist_ok=True)
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    pending = []
    for seed in seeds:
        meta = load_done(workdir, seed)
        if meta is not None:
            print('[resume] seed %d already done rc=%s elapsed=%ss' %
                  (seed, meta.get('returncode'), meta.get('elapsed_sec')), flush=True)
        else:
            pending.append(seed)

    if pending:
        workers = min(args.workers, len(pending))
        print('running %d seed(s), workers=%d; checkpoints=%s' %
              (len(pending), workers, workdir), flush=True)
        with CF.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(run_one, s, args, workdir): s for s in pending}
            unfinished = set(futs)
            while unfinished:
                done, unfinished = CF.wait(
                    unfinished, timeout=max(1, args.heartbeat),
                    return_when=CF.FIRST_COMPLETED)
                for fut in done:
                    meta = fut.result()
                    print('[DONE] seed %d rc=%d elapsed=%.1fs' %
                          (meta['seed'], meta['returncode'], meta['elapsed_sec']), flush=True)
                if unfinished:
                    running = sorted(futs[f] for f in unfinished)
                    print('[heartbeat] still running/pending: %s' %
                          ','.join(map(str, running)), flush=True)

    incomplete = [s for s in seeds if load_done(workdir, s) is None]
    if incomplete:
        print('INCOMPLETE:', ','.join(map(str, incomplete)), flush=True)
        print('rerun the same command; completed seeds will be skipped', flush=True)
        return 2
    return aggregate(seeds, workdir, args.out)


if __name__ == '__main__':
    raise SystemExit(main())
