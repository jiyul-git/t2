#!/usr/bin/env python3
"""Solve a flop panel at one terminal's ranges with independent per-flop processes.

    python3 tools/gto_hu_continuation/solve_panel.py <terminal.json> <menu.json> <panel.json> <out_dir> \
        [--postflop 1000 0.3 25] [--workers auto|N] [--threads T] [--exclude-origin panel_v1]

Each flop is one `t2_cont_panel` process restricted by T2_PANEL_BOARDS, so a crash or OOM
loses only that flop. A finished artifact is never recomputed: the Rust tool reuses it only
if its provenance key matches exactly and refuses otherwise. Before a worker starts, the
driver checks MemAvailable >= reserve + the largest peak RSS seen so far (default 2.6 GB
before the first flop finishes). Every attempt is appended to <out_dir>/run_ledger.jsonl:
board, status (solved / reused / failed), return code, wall time, peak RSS (wait4),
threads, and from the artifact iterations, exploitability, converged, invariant error.
workers=auto: min(cores // threads, floor((MemAvailable - reserve) / peak)).
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.environ.get('T2_BIN_DIR', os.path.join(ROOT, 'vendor/gtopen/target/release/examples'))
GB = 1024 ** 3


def mem_available():
    for line in open('/proc/meminfo'):
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024
    raise RuntimeError('no MemAvailable')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('terminal')
    ap.add_argument('menu')
    ap.add_argument('panel')
    ap.add_argument('out_dir')
    ap.add_argument('--postflop', nargs=3, default=['1000', '0.3', '25'])
    ap.add_argument('--workers', default='auto')
    ap.add_argument('--threads', type=int, default=None)
    ap.add_argument('--reserve-gb', type=float, default=3.0)
    ap.add_argument('--peak-gb', type=float, default=2.6, help='assumed per-flop peak until one is measured')
    ap.add_argument('--exclude-origin', default=None)
    ap.add_argument('--boards', default=None, help='comma list (subset of the panel)')
    a = ap.parse_args()
    panel = json.load(open(a.panel))
    boards = [f['board'] for f in panel['panel'] if a.exclude_origin is None or f.get('origin') != a.exclude_origin]
    if a.boards:
        want = a.boards.split(',')
        assert all(b in boards for b in want), 'board not on the (filtered) panel'
        boards = [b for b in boards if b in want]
    os.makedirs(os.path.join(a.out_dir, 'logs'), exist_ok=True)
    ledger = os.path.join(a.out_dir, 'run_ledger.jsonl')
    commit = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    cores = os.cpu_count()
    peak = a.peak_gb * GB
    if a.workers == 'auto':
        threads = a.threads or 1
        workers = max(1, min(cores // threads, int((mem_available() - a.reserve_gb * GB) // peak)))
    else:
        workers = int(a.workers)
        threads = a.threads or max(1, cores // workers)
    todo = [b for b in boards if not os.path.exists(os.path.join(a.out_dir, b + '.json'))]
    done_before = len(boards) - len(todo)
    print(f'{len(boards)} boards, {done_before} artifacts present (verified by the solver on reuse), '
          f'{len(todo)} to solve; workers {workers} x threads {threads}; MemAvailable {mem_available() / GB:.1f} GB',
          flush=True)
    # present artifacts still go through the solver's provenance check (cheap: no spot is built)
    queue = [b for b in boards if b not in todo] + todo
    running = {}
    failed = []
    measured = 0
    t_start = time.time()
    while queue or running:
        while queue and len(running) < workers:
            b = queue[0]
            present = os.path.exists(os.path.join(a.out_dir, b + '.json'))
            if not present and running and mem_available() < a.reserve_gb * GB + peak:
                break
            queue.pop(0)
            env = {**os.environ, 'T2_PANEL_BOARDS': b, 'T2_SOURCE_COMMIT': commit, 'RAYON_NUM_THREADS': str(threads)}
            log = open(os.path.join(a.out_dir, 'logs', b + '.log'), 'a')
            p = subprocess.Popen([os.path.join(BIN, 't2_cont_panel'), a.terminal, a.menu, a.panel, a.out_dir, *a.postflop],
                                 env=env, stdout=log, stderr=subprocess.STDOUT)
            running[p.pid] = (b, time.time(), present, log)
        if not running:
            time.sleep(5)
            continue
        pid, status, ru = os.wait4(-1, 0)
        if pid not in running:
            continue
        b, t0, present, log = running.pop(pid)
        log.close()
        rc = os.waitstatus_to_exitcode(status)
        rec = {'board': b, 'rc': rc, 'wall_s': round(time.time() - t0, 1), 'peak_rss_kb_wait4': ru.ru_maxrss,
               'threads': threads, 'workers': workers, 'time': time.strftime('%Y-%m-%dT%H:%M:%S')}
        art = os.path.join(a.out_dir, b + '.json')
        if rc == 0 and os.path.exists(art):
            d = json.load(open(art))
            rec.update({'status': 'reused' if present else 'solved', 'iterations': d['iterations'],
                        'exploitability_pct_pot': d['exploitability_pct_pot'],
                        'converged': d['exploitability_pct_pot'] <= d['provenance_key']['target_exploitability_pct_pot'],
                        'invariant_error_bb': d['invariant']['error'], 'solve_s': d['cost']['solve_ms'] / 1e3})
            if not present:
                measured = max(measured, ru.ru_maxrss * 1024)
                peak = measured
        else:
            rec['status'] = 'failed'
            failed.append(b)
        with open(ledger, 'a') as f:
            f.write(json.dumps(rec) + '\n')
        print(json.dumps(rec), flush=True)
    print(f'finished in {(time.time() - t_start) / 60:.1f} min; failed: {failed}', flush=True)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
