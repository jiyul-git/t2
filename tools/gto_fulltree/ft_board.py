#!/usr/bin/env python3
"""60bb 전체 트리 시범 — 보드 세션 실행기 (docs/GTO_FULLTREE_PILOT_60BB.md 9장 규약).

  python3 tools/gto_fulltree/ft_board.py <bundle_id> [<bundle_id> ...]

묶음 하나 = (단계 k 의 헤즈업 끝점 하나, 패널 A 또는 B) 72보드. 묶음 목록 = data/ft60/step<k>/bundles.tsv(모으는 세션이 만든다).
하는 일(묶음마다):
  1) 입력 해시 확인: 끝점 파일·패널 파일의 sha256 이 bundles.tsv 와 같아야 한다(다르면 멈춤 — 옛 단계 입력으로 풀지 않는다).
  2) 브랜치에 이미 올린 부분 결과(data/ft60/results/step<k>/<bundle>/flops.tgz)를 작업 폴더에 되살린다(솔버가 출처키로 확인 후 재사용).
  3) 12보드씩 solve_panel.py(quick 과 같은 솔버 목표, 3벳 이상 팟은 행렬 모드, 전략 저장 T2_EXPORT_STRATEGY=1) → 12보드마다 결과를 묶어 커밋·푸시.
  4) 72보드가 끝나면 못 맞춘 플랍은 CFR+ 1회 재시도(개정 11(a), spot_loop.retry_flops 그대로) → done.json(보드별 솔버 정확도, 재시도 뒤 남은 실패) 커밋·푸시.
값 계산(A∪B, D/U, 복제)은 하지 않는다 — 모으는 세션이 한다. 런타임 연결 없음.
지금 브랜치가 claude/ft60_board_<n> 이 아니면 거부한다.
환경: FT_CALC(기본 /home/user/calc), FT_WORK(기본 /home/user/gto_ckpt/ft60_board), SPOT_PANEL_WORKERS(기본 4).
"""
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CALC = os.environ.get('FT_CALC', '/home/user/calc')
WORK = os.environ.get('FT_WORK', '/home/user/gto_ckpt/ft60_board')
WORKERS = os.environ.get('SPOT_PANEL_WORKERS', '4')
CHUNK = 12
SOURCE_COMMIT = 'census79a9aca6+strategy_patch+ft60'   # 모든 보드 세션이 같은 값(출처키에 들어간다)
sys.path.insert(0, os.path.join(CALC, 'tools/gto_spot'))
sys.path.insert(0, os.path.join(CALC, 'tools/gto_validation'))
sys.path.insert(0, os.path.join(CALC, 'tools/gto_hu_continuation'))


def sh(*a, **k):
    return subprocess.run(list(a), check=True, capture_output=True, text=True, cwd=REPO, **k).stdout.strip()


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def branch():
    return sh('git', 'rev-parse', '--abbrev-ref', 'HEAD')


def push(msg):
    if os.environ.get('FT_NO_PUSH') == '1':   # 배관 시험용(로컬만)
        return
    sh('git', 'add', 'data/ft60/results')
    if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=REPO).returncode == 0:
        return
    sess = os.environ.get('FT_SESSION', 'unknown')
    sh('git', 'commit', '-q', '-m', msg + '\n\nClaude-Session: https://claude.ai/code/' + sess)
    for wait in (0, 2, 4, 8, 16):
        time.sleep(wait)
        if subprocess.run(['git', 'push', '-q', '-u', 'origin', branch()], cwd=REPO).returncode == 0:
            return
    raise SystemExit('push failed 5 times')


def bundles():
    rows = {}
    for f in sorted(os.listdir(os.path.join(REPO, 'data/ft60'))):
        p = os.path.join(REPO, 'data/ft60', f, 'bundles.tsv')
        if f.startswith('step') and os.path.exists(p):
            for r in csv.DictReader(open(p), delimiter='\t'):
                rows[r['bundle']] = r
    return rows


def pack(fd, out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + '.tmp'
    with tarfile.open(tmp, 'w:gz') as t:
        for name in sorted(os.listdir(fd)):
            p = os.path.join(fd, name)
            if os.path.isfile(p) and (name.endswith('.json') or name.endswith('.jsonl')):
                t.add(p, arcname=name)
        fa = os.path.join(fd, 'first_attempt')
        if os.path.isdir(fa):
            for name in sorted(os.listdir(fa)):
                t.add(os.path.join(fa, name), arcname='first_attempt/' + name)
    os.replace(tmp, out)


def run_bundle(b, r):
    k = int(r['step'])
    tf, pf = os.path.join(REPO, r['term_file']), os.path.join(REPO, r['panel_file'])
    if sha(tf) != r['term_sha256'] or sha(pf) != r['panel_sha256']:
        raise SystemExit('%s: input sha256 differs from bundles.tsv — stop (do not solve stale inputs)' % b)
    res = os.path.join(REPO, 'data/ft60/results/step%d/%s' % (k, b))
    if os.path.exists(os.path.join(res, 'done.json')):
        print('%s: already done' % b, flush=True)
        return
    fd = os.path.join(WORK, b, 'flops')
    os.makedirs(fd, exist_ok=True)
    tgz = os.path.join(res, 'flops.tgz')
    if os.path.exists(tgz):
        with tarfile.open(tgz) as t:
            t.extractall(fd)
    boards = [f['board'] for f in json.load(open(pf))['panel']]
    if os.environ.get('FT_TEST_BOARDS'):      # 배관 시험용: 앞 N 보드만(결과는 쓰지 말 것)
        boards = boards[:int(os.environ['FT_TEST_BOARDS'])]
    matrix = r['matrix'] == 'True'
    env = dict(os.environ, T2_BIN_DIR=os.path.join(CALC, 'vendor/gtopen/target/release/examples'), T2_EXPORT_STRATEGY='1',
               T2_SOURCE_COMMIT=SOURCE_COMMIT)
    if matrix:
        env['T2_PANEL_MATRIX'] = '1'
    menu = os.path.join(CALC, 'data/gto_hu_continuation/menu_m2_single_v1.json')
    t0 = time.time()
    for i in range(0, len(boards), CHUNK):
        chunk = boards[i:i + CHUNK]
        if all(os.path.exists(os.path.join(fd, x + '.json')) for x in chunk):
            continue
        subprocess.run([sys.executable, os.path.join(CALC, 'tools/gto_hu_continuation/solve_panel.py'), tf, menu, pf, fd,
                        '--workers', WORKERS, '--threads', '1', '--boards', ','.join(chunk)], check=True, env=env,
                       stdout=open(os.path.join(WORK, b, 'solve.log'), 'a'), stderr=subprocess.STDOUT)
        pack(fd, tgz)
        n = sum(os.path.exists(os.path.join(fd, x + '.json')) for x in boards)
        push('ft60 %s: %d/%d boards' % (b, n, len(boards)))
        print(json.dumps({'bundle': b, 'boards_done': n, 'min': round((time.time() - t0) / 60, 1)}), flush=True)
    import spot_loop as L
    L.PANEL = pf
    bad = [] if os.environ.get('FT_TEST_BOARDS') else L.flop_failures(fd)   # flop_failures 는 패널 전체를 본다
    first = list(bad)
    if bad:   # amendment 11 (a): one CFR+ retry at the same budget and target
        env_old = dict(os.environ)
        os.environ.update({k_: v for k_, v in env.items() if k_.startswith('T2_')})
        bad = L.retry_flops(tf, fd, pf, matrix, bad)
        os.environ.clear(); os.environ.update(env_old)
    acc = os.path.join(fd, 'accepted_above_target.json')
    ex = []
    for x in boards:
        d = json.load(open(os.path.join(fd, x + '.json')))
        ex.append({'board': x, 'pct_pot': d['exploitability_pct_pot'], 'converged': d['converged'], 'iterations': d['iterations'],
                   'strategy_file': os.path.exists(os.path.join(fd, x + '.strategy.json'))})
    ledger = [json.loads(l) for l in open(os.path.join(fd, 'run_ledger.jsonl'))] if os.path.exists(os.path.join(fd, 'run_ledger.jsonl')) else []
    walls = [e['wall_s'] for e in ledger if e.get('status') == 'solved' and e.get('wall_s')]
    pack(fd, tgz)
    done = {'bundle': b, 'step': k, 'term_sha256': r['term_sha256'], 'panel_sha256': r['panel_sha256'], 'matrix': matrix,
            'boards': len(boards), 'flop_failures_first': first, 'flop_failures_after_retry': bad,
            'accepted_above_target': json.load(open(acc)) if os.path.exists(acc) else {},
            'max_pct_pot': max(e['pct_pot'] for e in ex), 'mean_pct_pot': sum(e['pct_pot'] for e in ex) / len(ex),
            'strategy_files': sum(e['strategy_file'] for e in ex), 'board_wall_s_mean': (sum(walls) / len(walls)) if walls else None,
            'flops_tgz_sha256': sha(tgz), 'session': os.environ.get('FT_SESSION', 'unknown'), 'branch': branch(), 'boards_detail': ex}
    json.dump(done, open(os.path.join(res, 'done.json'), 'w'), indent=1)
    push('ft60 %s: done (%d boards, %d failed after retry)' % (b, len(boards), len(bad)))
    print(json.dumps({'bundle': b, 'done': True, 'failed_after_retry': len(bad)}), flush=True)


def main():
    if not re.match(r'^claude/ft60_board_\d+$', branch()) and os.environ.get('FT_NO_PUSH') != '1':
        raise SystemExit('checkout claude/ft60_board_<n> first (now %s)' % branch())
    rows = bundles()
    for b in sys.argv[1:]:
        if b not in rows:
            raise SystemExit('unknown bundle %s' % b)
        run_bundle(b, rows[b])
    print('FT_BOARD_ALL_DONE', flush=True)


if __name__ == '__main__':
    main()
