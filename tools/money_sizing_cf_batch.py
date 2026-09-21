#!/usr/bin/env python3
"""Resumable two-worker runner for the preregistered money sizing CF."""
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

import money_sizing_cf as MSCF


def paths(workdir, seed):
    stem = os.path.join(workdir, 'seed_%d' % seed)
    return stem + '.jsonl', stem + '.out', stem + '.done.json'


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


def run_one(seed, args, workdir):
    row, log, done = paths(workdir, seed)
    started = time.time()
    cmd = [
        sys.executable, '-u', os.path.join(TOOLS, 'money_sizing_cf.py'),
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


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8') as fp:
        for line in fp:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def aggregate(seeds, workdir, out_path):
    rows = []
    child_nonzero = []
    engine_errors = []
    harness_errors = []

    for seed in seeds:
        meta = load_done(workdir, seed)
        if meta is None:
            raise RuntimeError('seed %d is incomplete' % seed)
        if meta.get('returncode') != 0:
            child_nonzero.append((seed, meta.get('returncode')))
        row_path, _, _ = paths(workdir, seed)
        rows.extend(load_rows(row_path))
        meta_path = row_path + '.meta.json'
        try:
            with open(meta_path, encoding='utf-8') as fp:
                cm = json.load(fp)
            engine_errors.extend(cm.get('engine_errors') or [])
            harness_errors.extend(cm.get('harness_errors') or [])
        except (OSError, ValueError) as e:
            harness_errors.append('seed=%d missing/bad child meta: %s' % (seed, e))

    tmp = out_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        for r in rows:
            fp.write(json.dumps(r, ensure_ascii=False) + '\n')
    os.replace(tmp, out_path)

    if child_nonzero:
        harness_errors.extend(
            'seed=%d child process returned nonzero rc=%s' % (seed, rc)
            for seed, rc in child_nonzero
        )
    rc = MSCF.summarize(rows, engine_errors, harness_errors)
    if child_nonzero:
        print('\nchild_nonzero:', child_nonzero)
    print('\nWROTE', out_path)
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--rounds', type=int, default=260)
    ap.add_argument('--until-remaining', type=int, default=8)
    ap.add_argument('--fmt', default='standard')
    ap.add_argument('--seed-start', type=int, default=92200)
    ap.add_argument('--seeds', type=int, default=20)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--heartbeat', type=int, default=30)
    ap.add_argument('--workdir', default='money_sizing_cf_seeds')
    ap.add_argument('--out', default='money_sizing_cf_all.jsonl')
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
                  (seed, meta.get('returncode'), meta.get('elapsed_sec')),
                  flush=True)
        else:
            pending.append(seed)

    if pending:
        workers = min(args.workers, len(pending))
        print('running %d seed(s), workers=%d; checkpoints=%s' %
              (len(pending), workers, workdir), flush=True)
        next_i = 0
        with CF.ThreadPoolExecutor(max_workers=workers) as ex:
            active = {}
            while next_i < len(pending) and len(active) < workers:
                s = pending[next_i]
                next_i += 1
                active[ex.submit(run_one, s, args, workdir)] = s

            while active:
                done, _ = CF.wait(
                    set(active), timeout=max(1, args.heartbeat),
                    return_when=CF.FIRST_COMPLETED)
                if not done:
                    print('[heartbeat] active=%s queued=%d' %
                          (','.join(str(active[f]) for f in active),
                           len(pending) - next_i),
                          flush=True)
                    continue

                for fut in done:
                    seed = active.pop(fut)
                    meta = fut.result()
                    print('[DONE] seed %d rc=%d elapsed=%.1fs' %
                          (seed, meta['returncode'], meta['elapsed_sec']),
                          flush=True)
                    if next_i < len(pending):
                        s = pending[next_i]
                        next_i += 1
                        active[ex.submit(run_one, s, args, workdir)] = s

                if active:
                    print('[progress] active=%s queued=%d' %
                          (','.join(str(active[f]) for f in active),
                           len(pending) - next_i),
                          flush=True)

    incomplete = [s for s in seeds if load_done(workdir, s) is None]
    if incomplete:
        print('INCOMPLETE:', ','.join(map(str, incomplete)), flush=True)
        print('rerun the same command; completed seeds will be skipped', flush=True)
        return 2

    return aggregate(seeds, workdir, args.out)


if __name__ == '__main__':
    raise SystemExit(main())
