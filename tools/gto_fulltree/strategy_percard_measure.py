#!/usr/bin/env python3
"""턴·리버 전략을 카드별로 저장하는 비용 측정 (docs/STRATEGY_PERCARD_MEASURE.md).

  python3 tools/gto_fulltree/strategy_percard_measure.py <bundle> <board> <out_dir> [--no-old]

보드 하나를 ft_board.py 재시도 명령과 같은 설정(CFR+, 반복 1000, 목표 0.3% 팟, 25회마다 확인, 스레드 1, 같은 출처키 값)으로 두 번 푼다.
  R0 : 지금 내보내기만(옛 바이너리 t2_old, T2_EXPORT_STRATEGY=1)
  R1 : 새 패치 바이너리(t2_new), T2_EXPORT_STRATEGY=1 + T2_EXPORT_PERCARD=169,1326
두 결과 파일(cost 칸 제외)이 한 글자도 다르면 안 된다 → 'identical' 표시. 그다음 크기(원본·gzip·zstd)·시간·메모리를 모아 measure.json 에 쓴다.
검증: 카드별 169 파일을 다시 카드 평균으로 합쳐 옛 strategy.json 의 턴 노드·리버 첫 행동과 비교한다(허용 오차 2 퍼밀).
환경: FT_CALC(/home/user/calc), FT_BIN_OLD/FT_BIN_NEW(바이너리 경로), 저장소 루트에서 실행.
"""
import gzip
import json
import lzma
import os
import resource
import struct
import subprocess
import sys
import time

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CALC = os.environ.get('FT_CALC', '/home/user/calc')
BIN_OLD = os.environ.get('FT_BIN_OLD', '/home/user/gto_ckpt/bin/t2_old')
BIN_NEW = os.environ.get('FT_BIN_NEW', '/home/user/gto_ckpt/bin/t2_new')
MENU = os.path.join(CALC, 'data/gto_hu_continuation/menu_m2_single_v1.json')
SOURCE_COMMIT = 'census79a9aca6+strategy_patch+ft60'   # ft_board.py 와 같은 값(출처키)


def run(binary, tf, pf, out, board, matrix, extra):
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, T2_PANEL_BOARDS=board, RAYON_NUM_THREADS='1', T2_ALGO='cfr+', T2_SOURCE_COMMIT=SOURCE_COMMIT, **extra)
    if matrix:
        env['T2_PANEL_MATRIX'] = '1'
    t0 = time.time()
    p = subprocess.Popen([binary, tf, MENU, pf, out, '1000', '0.3', '25'], env=env,
                         stdout=open(os.path.join(out, 'run.log'), 'w'), stderr=subprocess.STDOUT)
    _, status, ru = os.wait4(p.pid, 0)
    if os.waitstatus_to_exitcode(status) != 0:
        raise SystemExit('solver failed, see %s/run.log' % out)
    return {'wall_s': time.time() - t0, 'max_rss_mb': ru.ru_maxrss / 1024}


def comp(path):
    """gzip -6 와 zstd -19 크기(zstd 가 없으면 None)"""
    raw = open(path, 'rb').read()
    out = {'raw': len(raw), 'gzip': len(gzip.compress(raw, 6))}
    out['xz6'] = len(lzma.compress(raw, preset=6))   # zstd 가 컨테이너에 없어 xz 로 잰다
    return out


def decode_169(binp, meta):
    """카드별 169 파일 → {(line, turn, river): (reach[169], freq[na][169])}"""
    lines = {l['id']: l for l in meta['lines']}
    b = open(binp, 'rb').read()
    pos, recs = 0, {}
    while pos < len(b):
        lid, t, r = struct.unpack_from('<IBB', b, pos)
        pos += 6
        na = len(lines[lid]['actions'])
        reach = np.frombuffer(b, '<f4', 169, pos)
        pos += 169 * 4
        fr = np.frombuffer(b, '<u2', na * 169, pos).reshape(na, 169)
        pos += na * 169 * 2
        recs[(lid, t, r)] = (reach, fr)
    return recs, lines


def verify(binp, meta, strat):
    """턴 노드(카드 평균)·리버 첫 행동(카드쌍 평균)을 카드별 파일에서 다시 만들어 옛 파일과 비교. 최대 차이(퍼밀) 반환"""
    recs, lines = decode_169(binp, meta)
    by_line = {}
    for (lid, t, r), (reach, fr) in recs.items():
        by_line.setdefault(lines[lid]['line'], []).append((reach.astype(np.float64), fr.astype(np.float64)))
    worst, checked = 0.0, 0
    for nd in strat['nodes']:
        if nd['street'] == 0:
            continue
        got = by_line.get(nd['line'])
        if not got:
            continue
        if nd['street'] == 2 and not nd['line'].endswith('|'):
            continue
        den = sum(g[0] for g in got)
        for a in range(len(nd['actions'])):
            num = sum(g[0] * np.where(g[1][a] == 65535, 0, g[1][a]) for g in got)
            old = np.array(nd['freq_permille'][a], dtype=float)
            ok = den > 0
            new = np.where(ok, num / np.where(ok, den, 1), -1)
            both = ok & (old >= 0)
            if both.any():
                worst = max(worst, float(np.abs(new - old)[both].max()))
            if ((old >= 0) != ok).any():
                worst = max(worst, 1000.0)   # 도달 여부 불일치
        checked += 1
    return {'max_diff_permille': worst, 'nodes_checked': checked}


def main():
    bundle, board, out = sys.argv[1], sys.argv[2], os.path.abspath(sys.argv[3])
    rows = {}
    import csv
    for step in os.listdir(os.path.join(REPO, 'data/ft60')):
        p = os.path.join(REPO, 'data/ft60', step, 'bundles.tsv')
        if step.startswith('step') and os.path.exists(p):
            for r in csv.DictReader(open(p), delimiter='\t'):
                rows[r['bundle']] = r
    r = rows[bundle]
    tf, pf = os.path.join(REPO, r['term_file']), os.path.join(REPO, r['panel_file'])
    matrix = r['matrix'] == 'True'
    res = {'bundle': bundle, 'board': board, 'matrix': matrix, 'line': r['line'], 'step': int(r['step'])}
    d0, d1 = os.path.join(out, 'R0_old'), os.path.join(out, 'R1_percard')
    reuse = os.path.exists(os.path.join(d0, board + '.strategy.json'))   # 이미 끝난 R0 가 있으면 다시 풀지 않는다(재시작 뒤 이어하기)
    if '--no-old' not in sys.argv and not reuse:
        res['R0'] = run(BIN_OLD, tf, pf, d0, board, matrix, {'T2_EXPORT_STRATEGY': '1'})
    res['R1'] = run(BIN_NEW, tf, pf, d1, board, matrix, {'T2_EXPORT_STRATEGY': '1', 'T2_EXPORT_PERCARD': '169,1326'})
    a1 = json.load(open(os.path.join(d1, board + '.json')))
    s1 = json.load(open(os.path.join(d1, board + '.strategy.json')))
    meta = json.load(open(os.path.join(d1, board + '.pc.meta.json')))
    res['solve'] = {'iterations': a1['iterations'], 'pct_pot': a1['exploitability_pct_pot'], 'converged': a1['converged'],
                    'solve_s': a1['cost']['solve_ms'] / 1e3, 'build_s': a1['cost']['build_ms'] / 1e3, 'tree_nodes': a1['cost']['tree_nodes'],
                    'arena_mb': a1['cost']['arena_bytes'] / 2**20, 'rss_after_solve_mb': a1['cost']['peak_rss_kb'] / 1024}
    if '--no-old' not in sys.argv:
        a0 = json.load(open(os.path.join(d0, board + '.json')))
        s0 = json.load(open(os.path.join(d0, board + '.strategy.json')))
        for k in ('cost',):
            a0.pop(k), a1.pop(k)
        e0, e1 = s0.pop('export_s'), s1.pop('export_s')
        res['identical'] = {'artifact_without_cost': a0 == a1, 'strategy_json_without_export_s': s0 == s1}
        res['current_export_s'] = e0
        res['R0_reused'] = reuse
        res['R0_solve_s'] = json.load(open(os.path.join(d0, board + '.json')))['cost']['solve_ms'] / 1e3
    else:
        res['current_export_s'] = s1['export_s']
    res['export_s'] = {'current_avg': res['current_export_s'], 'percard_169': meta['modes']['169']['export_s'], 'percard_1326': meta['modes']['1326']['export_s']}
    res['records'] = {'169': meta['modes']['169']['records'], '1326': meta['modes']['1326']['records']}
    res['size_bytes'] = {'current_avg': comp(os.path.join(d1, board + '.strategy.json')),
                         'percard_169': comp(os.path.join(d1, board + '.pc169.bin')),
                         'percard_1326': comp(os.path.join(d1, board + '.pc1326.bin'))}
    res['verify_169_vs_current'] = verify(os.path.join(d1, board + '.pc169.bin'), meta, json.load(open(os.path.join(d1, board + '.strategy.json'))))
    json.dump(res, open(os.path.join(out, 'measure.json'), 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
