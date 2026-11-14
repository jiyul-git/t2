#!/usr/bin/env python3
"""60bb 전체 트리 시범 — 보드 세션 실행기 (docs/GTO_FULLTREE_PILOT_60BB.md 9장 규약).

  python3 tools/gto_fulltree/ft_board.py <bundle_id> [<bundle_id> ...]

묶음 하나 = (단계 k 의 헤즈업 끝점 하나, 패널 A 또는 B) 72보드. 묶음 목록 = data/ft60/step<k>/bundles.tsv(모으는 세션이 만든다).
묶음마다:
  1) 입력 해시 확인: 끝점 파일·패널 파일 sha256 == bundles.tsv (다르면 멈춤 — 옛 단계 입력으로 풀지 않는다).
  2) 12보드 덩어리마다: solve_panel.py(quick·precision 과 같은 솔버 목표, 3벳 이상 팟은 행렬 모드, 전략 저장 T2_EXPORT_STRATEGY=1)
     → 그 덩어리에서 못 맞춘 플랍은 바로 CFR+ 1회 재시도(개정 11(a), spot_loop.retry_flops 와 같은 명령·같은 목표)
     → 덩어리 결과를 요약해 브랜치에 커밋·푸시. 요약은 모으는 세션의 계산(precision_loop 의 stratified·matrix_from)에 필요한 것 그대로:
        values.json.gz  보드별 두 자리 gross_eps(169) + 솔버 정확도·반복·수렴
        matrix_sums.npz 행렬 끝점만: 자리별 Σ_b w_b·(c_b⊗c_b)·M_b 와 Σ_b w_b·(c_b⊗c_b) (float64, w_b = 층 확률/층 보드 수, c_b = 보드 호환 몫)
                        — A∪B 는 (num_A+num_B)/(den_A+den_B) 로 precision_loop.matrix_from(A∪B) 와 같은 값(층마다 보드 수가 같아서).
        strategy_<i>.tgz 그 덩어리 보드들의 전략 파일 + 실행 기록
     보드 원본(보드당 행렬 약 1MB)은 올리지 않는다(단계당 수 GB). 컨테이너가 죽으면 끝난 덩어리는 건너뛰고 나머지만 다시 푼다.
  3) 72보드가 끝나면 done.json.
값 판정(A∪B, D/U, 복제)은 하지 않는다 — 모으는 세션 몫. 런타임 연결 없음. 브랜치가 claude/ft60_board_<n> 이 아니면 거부.
환경: FT_CALC(기본 /home/user/calc), FT_WORK(기본 /home/user/gto_ckpt/ft60_board), SPOT_PANEL_WORKERS(기본 4), FT_SESSION(세션 id).
시험용: FT_NO_PUSH=1(커밋·푸시 안 함, 브랜치 검사 안 함), FT_TEST_BOARDS=N(앞 N 보드만).
"""
import csv
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import time

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CALC = os.environ.get('FT_CALC', '/home/user/calc')
STACK = os.environ.get('FT_STACK', '60')          # 공용 도구: 데이터 data/ft<STACK>, 브랜치 claude/ft<STACK>_board_<n>
WORK = os.environ.get('FT_WORK', '/home/user/gto_ckpt/ft%s_board' % STACK)
WORKERS = os.environ.get('SPOT_PANEL_WORKERS', '4')
CHUNK = 12
SOURCE_COMMIT = 'census79a9aca6+strategy_patch+ft60'   # 모든 보드 세션이 같은 값(출처키에 들어간다)
BIN = os.path.join(CALC, 'vendor/gtopen/target/release/examples')
MENU = os.path.join(CALC, 'data/gto_hu_continuation/menu_m2_single_v1.json')
sys.path.insert(0, os.path.join(CALC, 'tools/gto_hu_continuation'))
PANEL_PATH = [None]


def sh(*a):
    return subprocess.run(list(a), check=True, capture_output=True, text=True, cwd=REPO).stdout.strip()


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def branch():
    return sh('git', 'rev-parse', '--abbrev-ref', 'HEAD')


def push(msg):
    if os.environ.get('FT_NO_PUSH') == '1':
        return
    sh('git', 'add', 'data/ft%s/results' % STACK)
    if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=REPO).returncode == 0:
        return
    sh('git', 'commit', '-q', '-m', msg + '\n\nClaude-Session: https://claude.ai/code/' + os.environ.get('FT_SESSION', 'unknown'))
    for wait in (0, 2, 4, 8, 16):
        time.sleep(wait)
        if subprocess.run(['git', 'push', '-q', '-u', 'origin', branch()], cwd=REPO).returncode == 0:
            return
    raise SystemExit('push failed 5 times')


def bundles():
    rows = {}
    base = os.path.join(REPO, 'data/ft' + STACK)
    for f in sorted(os.listdir(base)):
        p = os.path.join(base, f, 'bundles.tsv')
        if f.startswith('step') and os.path.exists(p):
            for r in csv.DictReader(open(p), delimiter='\t'):
                rows[r['bundle']] = r
    return rows


def ok_board(d):
    """precision_loop.board_values / spot_loop.flop_failures 와 같은 기준"""
    return d['converged'] and d['exploitability_pct_pot'] <= d['provenance_key']['target_exploitability_pct_pot'] <= 0.6


def retry(tf, fd, b, matrix):
    """spot_loop.retry_flops 와 같은 명령(같은 반복 예산·목표, T2_ALGO=cfr+), 보드 하나. 첫 결과는 first_attempt/ 에 둔다."""
    src = os.path.join(fd, b + '.json')
    first = os.path.join(fd, 'first_attempt', b + '.json')
    os.makedirs(os.path.dirname(first), exist_ok=True)
    if not os.path.exists(first):
        os.replace(src, first)
    elif os.path.exists(src):
        # 2026-11-04 (보드 세션 2): 재시작 뒤 같은 보드를 1차(DCFR)로 다시 푼 결과가 있고 first_attempt/ 에는 예전 1차 결과가 이미 있다.
        # 지금 결과를 그대로 두면 CFR+ 재시도가 출처키(algo) 차이로 덮어쓰기를 거부한다(rc=1). 1차 결과는 예전 것을 기록으로 두고,
        # 다시 푼 1차 결과는 dup_first/<시각>/ 로 옮긴다(지우지 않음). 같은 입력·같은 설정이라 두 1차 결과는 같은 절차의 결과다.
        dup = os.path.join(fd, 'dup_first', time.strftime('%Y%m%dT%H%M%S'))
        os.makedirs(dup, exist_ok=True)
        for suf in ('.json', '.strategy.json'):
            if os.path.exists(os.path.join(fd, b + suf)):
                os.replace(os.path.join(fd, b + suf), os.path.join(dup, b + suf))
    d0 = json.load(open(first))
    env = dict(os.environ, T2_PANEL_BOARDS=b, RAYON_NUM_THREADS='1', T2_ALGO='cfr+', T2_SOURCE_COMMIT=SOURCE_COMMIT, T2_EXPORT_STRATEGY='1')
    if matrix:
        env['T2_PANEL_MATRIX'] = '1'
    os.makedirs(os.path.join(fd, 'logs'), exist_ok=True)
    return subprocess.Popen([os.path.join(BIN, 't2_cont_panel'), tf, MENU, PANEL_PATH[0], fd, str(d0['iterations']),
                             str(d0['provenance_key']['target_exploitability_pct_pot']), '25'], env=env,
                            stdout=open(os.path.join(fd, 'logs', b + '.retry.log'), 'w'), stderr=subprocess.STDOUT)


def run_bundle(b, r):
    import a4c_run as C
    k = int(r['step'])
    tf, pf = os.path.join(REPO, r['term_file']), os.path.join(REPO, r['panel_file'])
    if sha(tf) != r['term_sha256'] or sha(pf) != r['panel_sha256']:
        raise SystemExit('%s: input sha256 differs from bundles.tsv — stop (do not solve stale inputs)' % b)
    PANEL_PATH[0] = pf
    res = os.path.join(REPO, 'data/ft%s/results/step%d/%s' % (STACK, k, b))
    os.makedirs(res, exist_ok=True)
    if os.path.exists(os.path.join(res, 'done.json')):
        print('%s: already done' % b, flush=True)
        return
    pj = json.load(open(pf))
    boards = [f['board'] for f in pj['panel']]
    if os.environ.get('FT_TEST_BOARDS'):
        boards = boards[:int(os.environ['FT_TEST_BOARDS'])]
    draws = {}
    for f in pj['panel']:
        draws.setdefault(f['stratum'], []).append(f['board'])
    wb = {x: pj['strata'][s]['probability'] / len(bs) for s, bs in draws.items() for x in bs}
    cp = C.compat_of(boards)
    matrix = r['matrix'] == 'True'
    fd = os.path.join(WORK, b, 'flops')
    os.makedirs(fd, exist_ok=True)
    stf = os.path.join(res, 'state.json')
    st = json.load(open(stf)) if os.path.exists(stf) else {'bundle': b, 'chunks_done': [], 'boards_done': []}
    vf = os.path.join(res, 'values.json.gz')
    vals = json.load(gzip.open(vf, 'rt')) if os.path.exists(vf) else {}
    mf = os.path.join(res, 'matrix_sums.npz')
    num, den = {}, {}
    if matrix and os.path.exists(mf):
        z = np.load(mf)
        for key in z.files:
            kind, pos = key.split('__')
            (num if kind == 'num' else den)[pos] = z[key]
    env = dict(os.environ, T2_BIN_DIR=BIN, T2_EXPORT_STRATEGY='1', T2_SOURCE_COMMIT=SOURCE_COMMIT)
    if matrix:
        env['T2_PANEL_MATRIX'] = '1'
    t0 = time.time()
    for i in range(0, len(boards), CHUNK):
        if i in st['chunks_done']:
            continue
        chunk = boards[i:i + CHUNK]
        # 2026-11-04 (보드 세션 2): 이미 CFR+ 재시도까지 끝난 보드(first_attempt/ 에 첫 결과, 지금 결과는 algo=cfr+)는 출처키의 algo 가
        # 달라 solve_panel(기본 DCFR)이 재사용을 거부한다(rc=1, 정상 동작). 그 보드는 다시 풀지 않고 재시도 결과로 받는다.
        def _retried_already(x):
            f, f0 = os.path.join(fd, x + '.json'), os.path.join(fd, 'first_attempt', x + '.json')
            if not (os.path.exists(f) and os.path.exists(f0)):
                return False
            try:
                return json.load(open(f))['provenance_key'].get('algo') == 'cfr+'
            except (ValueError, KeyError):
                return False
        to_solve = [x for x in chunk if not _retried_already(x)]
        cmd = [sys.executable, os.path.join(CALC, 'tools/gto_hu_continuation/solve_panel.py'), tf, MENU, pf, fd,
               '--workers', WORKERS, '--threads', '1', '--boards', ','.join(to_solve)]
        if to_solve and subprocess.run(cmd, env=env, stdout=open(os.path.join(WORK, b, 'solve.log'), 'a'), stderr=subprocess.STDOUT).returncode != 0:
            # 2026-11-04: 컨테이너가 멈출 때 쓰다 만 보드 결과물은 솔버가 재사용 검증에서 바로(rc=1) 거부한다. 아직 올리지 않은 덩어리의
            # 보드이므로 그 결과물을 bad_<시각>/ 로 옮기고(지우지 않음) 덩어리를 한 번 더 푼다. 두 번째도 실패하면 멈춘다.
            bad_dir = os.path.join(fd, 'bad_' + time.strftime('%Y%m%dT%H%M%S'))
            moved = []
            for x in to_solve:
                f = os.path.join(fd, x + '.json')
                okf = False
                if os.path.exists(f):
                    try:
                        okf = 'provenance_key' in json.load(open(f))
                    except ValueError:
                        okf = False
                led = [json.loads(l) for l in open(os.path.join(fd, 'run_ledger.jsonl'))] if os.path.exists(os.path.join(fd, 'run_ledger.jsonl')) else []
                last = [e for e in led if e.get('board') == x]
                refused = bool(last) and last[-1].get('status') == 'failed'
                if os.path.exists(f) and (refused or not okf):
                    os.makedirs(bad_dir, exist_ok=True)
                    for suf in ('.json', '.strategy.json'):
                        if os.path.exists(os.path.join(fd, x + suf)):
                            os.replace(os.path.join(fd, x + suf), os.path.join(bad_dir, x + suf))
                    moved.append(x)
            print(json.dumps({'bundle': b, 'solve_panel_failed': True, 'moved_aside': moved, 'to': bad_dir}), flush=True)
            subprocess.run(cmd, check=True, env=env, stdout=open(os.path.join(WORK, b, 'solve.log'), 'a'), stderr=subprocess.STDOUT)
        bad = [x for x in to_solve if not ok_board(json.load(open(os.path.join(fd, x + '.json'))))]
        retried = {}
        for x in chunk:
            if x not in to_solve:   # 재시도가 이미 끝난 보드(위 설명)
                d1 = json.load(open(os.path.join(fd, 'first_attempt', x + '.json')))
                d2 = json.load(open(os.path.join(fd, x + '.json')))
                retried[x] = {'first_pct_pot': d1['exploitability_pct_pot'], 'retry_pct_pot': d2['exploitability_pct_pot'],
                              'ok_after_retry': ok_board(d2), 'retried_before_restart': True}
        if bad:   # amendment 11 (a): one CFR+ retry at the same budget and target, in parallel (one thread each)
            ps = [retry(tf, fd, x, matrix) for x in bad]
            for x, p_ in zip(bad, ps):
                if p_.wait() != 0:
                    tail = open(os.path.join(fd, 'logs', x + '.retry.log')).read()[-2000:]
                    print(json.dumps({'bundle': b, 'retry_failed': x, 'retry_log_tail': tail}), flush=True)
                    raise subprocess.CalledProcessError(p_.returncode, p_.args)
            for x in bad:
                d1 = json.load(open(os.path.join(fd, 'first_attempt', x + '.json')))
                d2 = json.load(open(os.path.join(fd, x + '.json')))
                retried[x] = {'first_pct_pot': d1['exploitability_pct_pot'], 'retry_pct_pot': d2['exploitability_pct_pot'],
                              'ok_after_retry': ok_board(d2)}
        names = []
        for x in chunk:
            d = json.load(open(os.path.join(fd, x + '.json')))
            vals[x] = {'players': {pl['position']: pl['gross_eps'] for pl in d['players']},
                       'converged': d['converged'], 'pct_pot': d['exploitability_pct_pot'], 'iterations': d['iterations'],
                       'target_pct_pot': d['provenance_key']['target_exploitability_pct_pot'], 'ok': ok_board(d),
                       'retry': retried.get(x), 'stratum': next(s for s, bs in draws.items() if x in bs),
                       'provenance_key_sha256': hashlib.sha256(json.dumps(d['provenance_key'], sort_keys=True).encode()).hexdigest()}
            if matrix:
                c = np.array(cp[x])
                cc = np.outer(c, c) * wb[x]
                for pl in d['matrix']['players']:
                    pos = pl['position']
                    m = np.array([[np.nan if v is None else v for v in row] for row in pl['matrix']], dtype=float)
                    okm = ~np.isnan(m)
                    num.setdefault(pos, np.zeros((169, 169)))
                    den.setdefault(pos, np.zeros((169, 169)))
                    num[pos][okm] += (cc * np.where(okm, m, 0))[okm]
                    den[pos][okm] += cc[okm]
            if os.path.exists(os.path.join(fd, x + '.strategy.json')):
                names.append(x + '.strategy.json')
        buf = os.path.join(res, 'strategy_%02d.tgz' % (i // CHUNK))
        with tarfile.open(buf + '.tmp', 'w:gz') as t:
            for f in names:
                t.add(os.path.join(fd, f), arcname=f)
            if os.path.exists(os.path.join(fd, 'run_ledger.jsonl')):
                t.add(os.path.join(fd, 'run_ledger.jsonl'), arcname='run_ledger.jsonl')
        os.replace(buf + '.tmp', buf)
        with gzip.open(vf + '.tmp', 'wt') as g:
            json.dump(vals, g)
        os.replace(vf + '.tmp', vf)
        if matrix:
            np.savez_compressed(mf + '.tmp.npz', **{('num__' + p): v for p, v in num.items()}, **{('den__' + p): v for p, v in den.items()})
            os.replace(mf + '.tmp.npz', mf)
        st['chunks_done'].append(i)
        st['boards_done'] = sorted(vals)
        json.dump(st, open(stf, 'w'), indent=1)
        push('ft%s %s: %d/%d boards' % (STACK, b, len(vals), len(boards)))
        print(json.dumps({'bundle': b, 'boards_done': len(vals), 'retried': len(retried), 'min': round((time.time() - t0) / 60, 1)}), flush=True)
    failed = [x for x in boards if not vals[x]['ok']]
    done = {'bundle': b, 'step': k, 'term_sha256': r['term_sha256'], 'panel_sha256': r['panel_sha256'], 'matrix': matrix,
            'boards': len(boards), 'flop_failures_after_retry': failed, 'retried': {x: v['retry'] for x, v in vals.items() if v['retry']},
            'max_pct_pot': max(v['pct_pot'] for v in vals.values()), 'mean_pct_pot': sum(v['pct_pot'] for v in vals.values()) / len(vals),
            'values_sha256': sha(vf), 'matrix_sums_sha256': sha(mf) if matrix else None,
            'session': os.environ.get('FT_SESSION', 'unknown'), 'branch': branch(), 'wall_min_this_run': round((time.time() - t0) / 60, 1)}
    json.dump(done, open(os.path.join(res, 'done.json'), 'w'), indent=1)
    push('ft%s %s: done (%d boards, %d failed after retry)' % (STACK, b, len(boards), len(failed)))
    print(json.dumps({'bundle': b, 'done': True, 'failed_after_retry': len(failed)}), flush=True)


def main():
    if not re.match(r'^claude/ft%s_board_\d+$' % STACK, branch()) and os.environ.get('FT_NO_PUSH') != '1':
        raise SystemExit('checkout claude/ft%s_board_<n> first (now %s)' % (STACK, branch()))
    rows = bundles()
    for b in sys.argv[1:]:
        if b not in rows:
            raise SystemExit('unknown bundle %s' % b)
        run_bundle(b, rows[b])
    print('FT_BOARD_ALL_DONE', flush=True)


if __name__ == '__main__':
    main()
