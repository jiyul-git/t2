#!/usr/bin/env python3
"""60bb 전체 트리 시범(docs/GTO_FULLTREE_PILOT_60BB.md) — 모으는 세션 도구. 계산·기록만, 런타임 연결 없음.

  python3 tools/gto_fulltree/ft60.py seeds                 # 0단계 표 manifest(BB 보정 씨앗 → 전체 트리 노드 번호)
  python3 tools/gto_fulltree/ft60.py prepare <k> <ck.gtop> <dump.jsonl>   # k단계 끝점 고르기 + 끝점 입력 + 묶음 목록
  python3 tools/gto_fulltree/ft60.py timing <out_dir> <n_terms> <n_boards>   # 3벳 팟 끝점 보드 시간 실측(0단계 전, 부모 덤프 레인지)
  python3 tools/gto_fulltree/ft60.py collect <k>        # 보드 세션 결과 모으기 → step<k>/collect/report.json + tables_{A,B,AB}
  python3 tools/gto_fulltree/ft60.py next_tables <k>    # k+1단계 표(감쇠) manifest

환경: FT_CALC (계산 체크아웃, 기본 /home/user/calc — census 79a9aca6 + 전략 저장 패치 + t2_ft_export), FT_WORK(기본 /home/user/gto_ckpt/ft60).
"""
import gzip
import hashlib
import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CALC = os.environ.get('FT_CALC', '/home/user/calc')
STACK = os.environ.get('FT_STACK', '60')            # 공용 도구: FT_STACK=40|60|100 ... (데이터 폴더 data/ft<STACK>, 브랜치 claude/ft<STACK>_board_<n>)
WORK = os.environ.get('FT_WORK', '/home/user/gto_ckpt/ft' + STACK)
BIN = os.path.join(CALC, 'vendor/gtopen/target/release/examples')
CFG = os.environ.get('FT_CFG', os.path.join(CALC, 'data/gto_spot/plan_a/cfg_p%s_o25.json' % STACK))
D = os.path.join(REPO, 'data/ft' + STACK)
MATRIX_ALL = os.environ.get('FT_MATRIX_ALL', '1') == '1'   # 모든 헤즈업 끝점이 손패×손패 행렬(matrix_sums)을 갖는다(0·1단계 재현은 FT_MATRIX_ALL=0)
N_TERMS = 40                      # 사용자 결정 10-31: 헤즈업 끝점 40개
PANELS = {'A': os.path.join(D, 'panels/panel_prec_A72.json'), 'B': os.path.join(D, 'panels/panel_prec_B72.json')}
POS = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
RANKS = '23456789TJQKA'


def labels():
    out = []
    for i in range(13):
        for j in range(13):
            hi, lo = max(i, j), min(i, j)
            out.append(RANKS[i] * 2 if i == j else RANKS[hi] + RANKS[lo] + ('o' if j > i else 's'))
    return out


LAB = labels()
PRIOR = [(6 if len(c) == 2 else 4 if c[2] == 's' else 12) / 1326 for c in LAB]


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def export(ck, lines, out, manifest=None, static_matrix=False):
    jobs = out + '.jobs'
    open(jobs, 'w').write('\n'.join(lines) + '\n')
    env = dict(os.environ)
    env.pop('T2_CONT_FILE', None)
    env.pop('T2_EXPORT_STATIC_MATRIX', None)
    if static_matrix:
        env['T2_EXPORT_STATIC_MATRIX'] = '1'
    if manifest:
        env['T2_CONT_FILE'] = manifest
    env.setdefault('PREFLOP_EQ_SEED', '202'); env.setdefault('PREFLOP_MULTIWAY_SEED', '202'); env.setdefault('PREFLOP_EQ_SAMPLES', '1200')
    subprocess.run([os.path.join(BIN, 't2_ft_export'), CFG, ck, jobs, out], check=True, env=env)
    return [json.loads(x) for x in open(out)]


def n_raises(line):
    return sum(1 for it in line.split('|') if any(k in it for k in ('Raise', '3-bet', '4-bet', 'All-in', ':raise', ':jam')))


def seeds():
    """BB 보정 루프의 마지막 표(state.json) → 전체 트리 노드 번호를 붙인 t2_hu_continuation_table_v1 + manifest."""
    out = os.path.join(D, 'step0/tables')
    os.makedirs(out, exist_ok=True)
    rows, lines = [], []
    for f in sorted(os.listdir(os.path.join(D, 'seed'))):
        st = json.load(open(os.path.join(D, 'seed', f)))
        for line, t in sorted(st['tables'].items()):
            rows.append((f, line, t))
            lines.append(line)
    os.makedirs(WORK, exist_ok=True)
    info = export('-', lines, os.path.join(WORK, 'seed_nodes.jsonl'))
    man = {'schema': 't2_hu_continuation_manifest_v1', 'tables': [],
           'note': 'step 0 seeds: BB loop final tables (p60 HJ, LJ o25); every other terminal static (docs/GTO_FULLTREE_PILOT_60BB.md 3장)'}
    for (f, line, t), e in zip(rows, info):
        assert e['kind'] == 'pot_share' and int(e['live']) == int(t['live']) and abs(e['pot_bb'] - float(t['pot_bb'])) < 1e-9, (line, e)
        tab = dict(t)
        tab['node'] = e['node']
        tab['live'] = int(t['live'])
        tab['pot_bb'] = float(t['pot_bb'])
        tab['provenance'] = dict(t.get('provenance') or {}, seed_file=f, seed_sha256=sha(os.path.join(D, 'seed', f)))
        name = 'node%d.json' % e['node']
        json.dump(tab, open(os.path.join(out, name), 'w'))
        man['tables'].append({'file': name, 'line': line, 'seed': f})
    json.dump(man, open(os.path.join(out, 'manifest.json'), 'w'), indent=1)
    print(json.dumps({'tables': len(man['tables']), 'dir': out}))


def hu_terminals(dump):
    """terminal_mass.py 와 같은 규칙: 헤즈업 플랍 끝점과 도달 확률(덤프의 행동 표기 줄)."""
    nodes = {}
    for l in (gzip.open(dump, 'rt') if dump.endswith('.gz') else open(dump)):
        d = json.loads(l)
        nodes[tuple(d['line'])] = d
    rows = []
    for line, d in nodes.items():
        ar = d['actor_reach']
        s = sum(ar)
        if s <= 0:
            continue
        for ai, a in enumerate(d['actions']):
            ch = line + (d['actor'] + ':' + a,)
            if ch in nodes:
                continue
            w = d['reach_prob'] * sum(x * y for x, y in zip(ar, d['sigma'][ai])) / s
            folded = {x.split(':')[0] for x in ch if x.endswith(':Fold')}
            live = [q for q in POS if q not in folded]
            if len(live) != 2 or w <= 0 or any('All-in' in x for x in ch):
                continue
            rows.append((w, '|'.join(ch)))
    rows.sort(reverse=True)
    return rows


def term_json(e, line, stack, ante):
    players = []
    for s in e['seats']:
        keep = [r / p for r, p in zip(s['reach'], PRIOR)]
        players.append({'seat': s['seat'], 'position': s['position'], 'class_keep_fraction': keep, 'invested_bb': e['invested'][s['seat']]})
    hsh = hashlib.sha256(json.dumps([p['class_keep_fraction'] for p in players]).encode()).hexdigest()[:16]
    to = max(e['invested'][s['seat']] for s in e['seats']) - ante
    aggr = None
    for it in line.split('|'):
        if any(k in it for k in ('Raise', '3-bet', '4-bet')):
            aggr = it.split(':')[0]
    out = {'schema': 'spot_terminal_v1', 'line': line, 'players': players, 'pot_bb': e['pot_bb'], 'effective_behind_bb': stack - to,
           'path_spec': line, 'aggressor': aggr, 'ranges_hash_fnv1a64': hsh, 'terminal_live_mask': e['live'], 'node': e['node'],
           'reach_probability': float(sum(players[0]['class_keep_fraction'][h] * PRIOR[h] for h in range(169))
                                      * sum(players[1]['class_keep_fraction'][h] * PRIOR[h] for h in range(169)))}
    if MATRIX_ALL or n_raises(line) >= 2:   # rule v3: 3-bet-or-larger pots carry range-reactive matrices; 행렬 끝점 엔진 지원 이후 모든 헤즈업 끝점
        out['matrix_opp_classes'] = {p['position']: [h for h in range(169) if p['class_keep_fraction'][h] > 0] for p in players}
    return out


def prepare(k, ck, dump, n=N_TERMS, sd=None):
    cfg = json.load(open(CFG))
    sd = sd or os.path.join(D, 'step%d' % k)
    os.makedirs(os.path.join(sd, 'terms'), exist_ok=True)
    hu = hu_terminals(dump)
    tot = sum(w for w, _ in hu)
    pick = hu[:n]
    man = os.path.join(sd, 'tables/manifest.json')
    info = export(ck, [l for _, l in pick], os.path.join(WORK, 'step%d_export.jsonl' % k), man if os.path.exists(man) else None, static_matrix=True)
    import numpy as np
    np.savez_compressed(os.path.join(sd, 'static_matrix.npz'), **{'%d__%s' % (e['node'], x['position']): np.array(x['static_matrix'], dtype=np.float32).reshape(169, 169)
                                                                     for e in info for x in e['seats'] if x.get('static_matrix')})
    rows = []
    for j, ((w, line), e) in enumerate(zip(pick, info)):
        assert e['kind'] == 'pot_share', line
        tj = term_json(e, line, cfg['stack'], cfg['ante'])
        tf = os.path.join(sd, 'terms', 'term%02d.json' % j)
        json.dump(tj, open(tf, 'w'))
        for p in 'AB':
            rows.append({'bundle': 's%d_t%02d_%s' % (k, j, p), 'step': k, 'term': j, 'panel': p, 'matrix': 'matrix_opp_classes' in tj,
                         'reach': w, 'node': e['node'], 'line': line, 'term_file': os.path.relpath(tf, REPO), 'term_sha256': sha(tf),
                         'panel_file': os.path.relpath(PANELS[p], REPO), 'panel_sha256': sha(PANELS[p])})
    with open(os.path.join(sd, 'bundles.tsv'), 'w') as f:
        cols = ['bundle', 'step', 'term', 'panel', 'matrix', 'reach', 'node', 'term_file', 'term_sha256', 'panel_file', 'panel_sha256', 'line']
        f.write('\t'.join(cols) + '\n')
        for r in rows:
            f.write('\t'.join(str(r[c]) for c in cols) + '\n')
    # 묶음 → 보드 세션 배분(가장 긴 것부터 가장 덜 찬 세션에): 예상 시간 = 행렬 끝점 1.9h(실측 9.4절), 그 밖 0.8h(추정, 0단계 결과로 고침)
    n_sess = int(os.environ.get('FT_SESSIONS', '5'))
    load = [0.0] * n_sess
    assign = []
    meas = {}
    mf = os.environ.get('FT_BOARD_HOURS')   # 이전 단계 실측(노드 번호 → 시간, wall_min_this_run 중앙값); 없는 노드는 중앙값
    if mf and os.path.exists(mf):
        meas = json.load(open(mf))
    med = sorted(meas.values())[len(meas) // 2] if meas else None
    def est_h(r):
        if meas:
            return float(meas.get(str(r['node']), med))
        return est_h0(r)
    def est_h0(r):   # 실측: 3벳 행렬 1.9h / 단일 레이즈 행렬 2.6h(보드 4장 529~569초 ×18) / 단일 레이즈 비행렬 1.4h(279~303초 ×18)
        return 1.9 if (r['matrix'] and n_raises(r['line']) >= 2) else 2.6 if r['matrix'] else 1.4
    for r in sorted(rows, key=lambda r: (-est_h(r), -r['reach'], r['bundle'])):
        i = min(range(n_sess), key=lambda x: (load[x], x))
        load[i] += est_h(r)
        assign.append((r['bundle'], i + 1))
    with open(os.path.join(sd, 'assign.tsv'), 'w') as f:
        f.write('bundle\tsession\n')
        for bnd, i in sorted(assign, key=lambda x: (x[1], x[0])):
            f.write('%s\t%d\n' % (bnd, i))
    summ = {'step': k, 'hu_terminals': len(hu), 'session_load_h': [round(x, 1) for x in load], 'picked': len(pick), 'picked_share_of_hu_mass': sum(w for w, _ in pick) / tot,
            'hu_mass': tot, 'bundles': len(rows), 'matrix_terms': sum(1 for r in rows if r['matrix']) // 2,
            'ck_sha256': sha(ck), 'dump_sha256': sha(dump)}
    json.dump(summ, open(os.path.join(sd, 'prepare.json'), 'w'), indent=1)
    print(json.dumps(summ))


def timing(out, n_terms, n_boards):
    """0단계 전 보드 시간 실측: 부모 덤프 레인지로 3벳 팟 끝점 n_terms 개 × 패널 A 앞 n_boards 장(행렬 모드, 전략 저장 켬)."""
    dump = os.environ.get('FT_PARENT_DUMP', '/home/user/gto_ckpt/plan_a/p60_o25/dump.jsonl')
    hu = hu_terminals(dump)
    pick = [(w, l) for w, l in hu if n_raises(l) >= 2][:n_terms]
    # 부모 덤프에는 체크포인트가 없다 → 레인지는 덤프에서 직접 계산(행동 노드의 actor_reach × σ)
    nodes = {}
    for l in open(dump):
        d = json.loads(l)
        nodes[tuple(d['line'])] = d
    cfg = json.load(open(CFG))
    info = export('-', [l for _, l in pick], os.path.join(out, 'timing_nodes.jsonl'))
    os.makedirs(out, exist_ok=True)
    pj = json.load(open(PANELS['A']))
    boards = [f['board'] for f in pj['panel']][:n_boards]
    for j, ((w, line), e) in enumerate(zip(pick, info)):
        items = line.split('|')
        seats = []
        for s in e['seats']:
            pos = s['position']
            last = max(i for i, it in enumerate(items) if it.split(':')[0] == pos)
            nd = nodes[tuple(items[:last])]
            ai = nd['actions'].index(items[last].split(':', 1)[1])
            seats.append({'seat': s['seat'], 'position': pos, 'reach': [r * sg for r, sg in zip(nd['actor_reach'], nd['sigma'][ai])]})
        e = dict(e, seats=seats)
        tj = term_json(e, line, cfg['stack'], cfg['ante'])
        tf = os.path.join(out, 'term%d.json' % j)
        json.dump(tj, open(tf, 'w'))
        env = dict(os.environ, T2_PANEL_MATRIX='1', T2_BIN_DIR=BIN, T2_EXPORT_STRATEGY='1')
        fd = os.path.join(out, 'term%d_A' % j)
        r = subprocess.run([sys.executable, os.path.join(CALC, 'tools/gto_hu_continuation/solve_panel.py'), tf,
                            os.path.join(CALC, 'data/gto_hu_continuation/menu_m2_single_v1.json'), PANELS['A'], fd,
                            '--workers', '4', '--threads', '1', '--boards', ','.join(boards)],
                           stdout=open(os.path.join(out, 'term%d.log' % j), 'w'), stderr=subprocess.STDOUT, env=env)
        print(json.dumps({'term': j, 'line': [x for x in items if not x.endswith(':Fold')], 'reach': w, 'rc': r.returncode}), flush=True)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'seeds':
        seeds()
    elif cmd == 'prepare':
        prepare(int(sys.argv[2]), sys.argv[3], sys.argv[4])
    elif cmd == 'timing':
        timing(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    elif cmd not in ('collect', 'next_tables'):
        raise SystemExit(__doc__)


# ======================= collect (모으는 세션: 보드 결과 → A·B·A∪B 값, D/U, 복제, 다음 표) =======================
# 식은 tools/gto_precision/precision_loop.py(claude/precision_runner_20261031) 와 같다:
#   stratified(층 확률 가중 평균, 보드 호환 몫 c_b, RHO), 행렬 끝점은 M = Σw(c⊗c)M / Σw(c⊗c) 를 상대 도착 분포로 곱한 값,
#   D = Σ_h w_h |V_A∪B − V_사용| / W, U = Σ w_h se_h / W (w = 클래스 콤보 × 도착 몫), 복제 |V_A − V_B| ≤ 2√(U_A²+U_B²),
#   개정 8: 상대가 1콤보 미만으로 오는 자리 면제. 0단계는 통과로 치지 않는다(최소 1회 갱신).
ALPHA, ALPHA_CYCLE = 0.5, 0.25
COMBOS = [6 if len(c) == 2 else 4 if c[2] == 's' else 12 for c in LAB]


def _git(*a):
    return subprocess.run(['git', '-C', REPO, *a], capture_output=True, text=True)


def fetch_results(k, out):
    """원격의 claude/ft60_board_* 브랜치에서 step k 결과를 out/<bundle>/ 로 꺼낸다(done.json 이 있는 것만, sha 확인)."""
    refs = [l.split()[1] for l in _git('ls-remote', 'origin', 'refs/heads/claude/ft%s_board_*' % STACK).stdout.splitlines()]
    got = {}
    for ref in refs:
        br = ref.replace('refs/heads/', '')
        _git('fetch', '-q', '--depth=1', 'origin', '+' + br + ':refs/remotes/origin/' + br)   # '+': 얕은 ref 는 조상 확인이 안 돼 + 없으면 갱신이 거부된다
        ls = _git('ls-tree', '-r', '--name-only', 'origin/' + br, 'data/ft%s/results/step%d' % (STACK, k)).stdout.split()
        for p in ls:
            if not p.endswith('/done.json'):
                continue
            b = p.split('/')[-2]
            d = os.path.join(out, b)
            os.makedirs(d, exist_ok=True)
            for f in ('done.json', 'values.json.gz', 'matrix_sums.npz'):
                src = os.path.dirname(p) + '/' + f
                r = subprocess.run(['git', '-C', REPO, 'show', 'origin/%s:%s' % (br, src)], capture_output=True)
                if r.returncode == 0:
                    open(os.path.join(d, f), 'wb').write(r.stdout)
            done = json.load(open(os.path.join(d, 'done.json')))
            assert sha(os.path.join(d, 'values.json.gz')) == done['values_sha256'], b
            if done['matrix']:
                assert sha(os.path.join(d, 'matrix_sums.npz')) == done['matrix_sums_sha256'], b
            got[b] = dict(done, _branch=br)
    return got


def _panel(names):
    owner, draws, prob = {}, {}, None
    for n in names:
        pj = json.load(open(PANELS[n]))
        prob = {s: v['probability'] for s, v in pj['strata'].items()}
        for f in pj['panel']:
            owner[f['board']] = n
            draws.setdefault(f['stratum'], []).append(f['board'])
    return owner, draws, prob


def _stratified(vals, names):
    sys.path.insert(0, os.path.join(CALC, 'tools/gto_hu_continuation'))
    import math
    import a4c_run as C
    owner, draws, p = _panel(names)
    cp = C.compat_of(list(owner))
    ptot = sum(p.values())
    est, se = {}, {}
    for pos in vals[next(iter(owner))]:
        e, u = [], []
        for h in range(169):
            tot, v2 = 0.0, 0.0
            for s, bs in draws.items():
                y = [cp[b][h] * vals[b][pos][h] for b in bs]
                m = sum(y) / len(y)
                tot += p[s] * m
                v2 += (p[s] / (ptot * C.RHO)) ** 2 * sum((x - m) ** 2 for x in y) / (len(y) - 1) / len(y)
            e.append(tot / ptot / C.RHO)
            u.append(math.sqrt(v2))
        est[pos], se[pos] = e, u
    return est, se


def static_mat(sd, node, pos):
    """정적(표 없음) 손패×손패 행렬(prepare 가 t2_ft_export 로 만든 static_matrix.npz). 없으면 None."""
    import numpy as np
    p = os.path.join(sd, 'static_matrix.npz')
    if not os.path.exists(p):
        return None
    z = np.load(p)
    key = '%d__%s' % (node, pos)
    return z[key].astype(float) if key in z.files else None


def used_matrix(sd, node, pos, tj, Sm):
    """이 단계 트리가 쓴 표를 행렬로: 행렬 표면 그 행렬, 벡터 표면 열이 모두 같은 행렬(엔진이 레인지에 반응 안 한 것과 같은 뜻), 표가 없으면 정적 행렬."""
    import numpy as np
    mp = os.path.join(sd, 'tables/manifest.json')
    if os.path.exists(mp):
        tp = os.path.join(sd, 'tables/node%d.json' % node)
        if os.path.exists(tp):
            for x in json.load(open(tp))['seats']:
                if x['position'] == pos:
                    if 'matrix' in x and x['matrix'] is not None:
                        return np.array(x['matrix'], dtype=float).reshape(169, 169)
                    return np.tile(np.array(x['gross'], dtype=float)[:, None], (1, 169))
    return Sm if Sm is not None else np.zeros((169, 169))


def collect(k):
    import math
    import numpy as np
    sd = os.path.join(D, 'step%d' % k)
    rows = list(__import__('csv').DictReader(open(os.path.join(sd, 'bundles.tsv')), delimiter='\t'))
    out = os.path.join(WORK, 'collect_s%d' % k)
    got = fetch_results(k, out)
    used = {e['node']: e for e in (json.loads(l) for l in gzip.open(os.path.join(sd, 'used_gross.jsonl.gz'), 'rt'))}
    terms = sorted({int(r['term']) for r in rows})
    missing = [r['bundle'] for r in rows if r['bundle'] not in got]
    rep = {'step': k, 'bundles_done': len(got), 'bundles_missing': missing, 'terminals': {}}
    for r in rows:
        if r['bundle'] in got:
            g = got[r['bundle']]
            assert g['term_sha256'] == r['term_sha256'] and g['panel_sha256'] == r['panel_sha256'], ('stale result', r['bundle'])
    failed = [(b, g['flop_failures_after_retry']) for b, g in got.items() if g['flop_failures_after_retry']]
    rep['flop_failures_after_retry'] = failed
    tables_raw = {'A': {}, 'B': {}, 'AB': {}}
    ok1 = ok2v = True
    for j in terms:
        bA, bB = 's%d_t%02d_A' % (k, j), 's%d_t%02d_B' % (k, j)
        if bA not in got or bB not in got:
            continue
        tj = json.load(open(os.path.join(sd, 'terms/term%02d.json' % j)))
        node = tj['node']
        vals = {}
        for b in (bA, bB):
            for x, v in json.load(gzip.open(os.path.join(out, b, 'values.json.gz'), 'rt')).items():
                vals[x] = {pos: [0.0 if y is None else y for y in g] for pos, g in v['players'].items()}
        raw = {n: _stratified(vals, names) for n, names in (('A', ['A']), ('B', ['B']), ('AB', ['A', 'B']))}
        matrix = got[bA]['matrix']
        if matrix:
            zA, zB = np.load(os.path.join(out, bA, 'matrix_sums.npz')), np.load(os.path.join(out, bB, 'matrix_sums.npz'))
            M = {}
            for pos in {x.split('__')[1] for x in zA.files}:
                nA, dA, nB, dB = zA['num__' + pos], zA['den__' + pos], zB['num__' + pos], zB['den__' + pos]
                M[pos] = {'A': np.where(dA > 0, nA / np.where(dA > 0, dA, 1), np.nan), 'B': np.where(dB > 0, nB / np.where(dB > 0, dB, 1), np.nan),
                          'AB': np.where(dA + dB > 0, (nA + nB) / np.where(dA + dB > 0, dA + dB, 1), np.nan)}
        seats = {}
        mats_by_pos = {}
        u_seat = {s['seat']: s for s in used[node]['seats']}
        for pl in tj['players']:
            pos = pl['position']
            opp = next(q for q in tj['players'] if q['position'] != pos)
            w = np.array(COMBOS) * np.array(pl['class_keep_fraction'])
            W = w.sum()
            dist = np.array(opp['class_keep_fraction']) * np.array(PRIOR)
            opp_mass = float(dist.sum() * 1326)
            dist = dist / dist.sum()
            use = dist > 0
            if matrix:
                V = {n: np.nan_to_num(M[pos][n][:, use], nan=0.0) @ dist[use] for n in ('A', 'B', 'AB')}
            else:
                V = {n: np.array(raw[n][0][pos]) for n in ('A', 'B', 'AB')}
            g_used = np.array(u_seat[pl['seat']]['used_gross'])
            mat_ab = None
            if matrix:
                # 행렬 그대로 저장(A∪B): 보드 풀이 밖 칸(den=0)은 정적 행렬로 채운다. 채운 비율을 기록한다.
                Mr = M[pos]['AB']
                Sm = static_mat(sd, node, pos)
                fin = np.isfinite(Mr)
                Mf = np.where(fin, Mr, Sm if Sm is not None else 0.0)
                wn = w / W
                fill_cells = float(1 - fin.mean())
                fill_mass = float((wn[:, None] * dist[None, :] * (~fin)).sum())      # 이 끝점 레인지(own x opp)에서 채운 칸의 질량
                # 직전 단계 표(사용한 표) 대비 행렬 차이: 행렬판 D (레인지 가중 L1)
                Tm = used_matrix(sd, node, pos, tj, Sm)
                Dm = float((wn[:, None] * dist[None, :] * np.abs(Mf - Tm)).sum())
                mat_ab = {'matrix': Mf, 'fill_cells': fill_cells, 'fill_mass': fill_mass, 'Dm': Dm, 'fin': fin}
            U = {n: float((w * np.array(raw[n][1][pos])).sum() / W) for n in ('A', 'B', 'AB')}
            Dv = float((w * np.abs(V['AB'] - g_used)).sum() / W)
            sg = float((w * (V['AB'] - g_used)).sum() / W)
            Drep = float((w * np.abs(V['A'] - V['B'])).sum() / W)
            bound = 2 * math.sqrt(U['A'] ** 2 + U['B'] ** 2)
            exempt = opp_mass < 1.0
            p1, p2 = Dv <= U['AB'], Drep <= bound
            seats[pos] = {'D': Dv, 'signed': sg, 'U144': U['AB'], 'U_A': U['A'], 'U_B': U['B'], 'D_over_U': Dv / U['AB'] if U['AB'] > 0 else None,
                          'rep_diff': Drep, 'rep_bound': bound, 'pass_D_le_U': p1 or exempt, 'pass_D_le_U_strict': p1,
                          'pass_rep_value': p2 or exempt, 'pass_rep_value_strict': p2, 'opp_arriving_combos': opp_mass, 'exempt': exempt,
                          'used_was_table': u_seat[pl['seat']]['used_gross'] != u_seat[pl['seat']]['static_gross']}
            if mat_ab is not None:
                seats[pos].update({'matrix_fill_cells': mat_ab['fill_cells'], 'matrix_fill_mass': mat_ab['fill_mass'], 'Dm': mat_ab['Dm'],
                                   'Dm_over_U': mat_ab['Dm'] / U['AB'] if U['AB'] > 0 else None})
                mats_by_pos[pos] = mat_ab
            ok1 &= p1 or exempt
            ok2v &= p2 or exempt
            for n in ('A', 'B', 'AB'):
                t = tables_raw[n].setdefault(node, {'schema': 't2_hu_continuation_table_v1', 'node': node, 'line': tj['line'],
                                                    'live': tj['terminal_live_mask'], 'pot_bb': tj['pot_bb'], 'value_convention': 'gross_share',
                                                    'seats': [], 'provenance': {'kind': 'ft60 step %d panel %s (raw%s)' % (k, n, ', matrix x arriving dist' if matrix else '')}})
                ts = {'seat': pl['seat'], 'position': pos, 'gross': [float(x) for x in V[n]], 'se': raw[n][1][pos]}
                if n == 'AB' and pos in mats_by_pos:
                    ts['matrix'] = [round(float(x), 6) for x in mats_by_pos[pos]['matrix'].ravel()]
                t['seats'].append(ts)
        sumchk = None
        if matrix and len(mats_by_pos) == 2:
            pa, pb = list(mats_by_pos)
            fa, fb = mats_by_pos[pa]['fin'], mats_by_pos[pb]['fin'].T
            both = fa & fb
            r_raw = (mats_by_pos[pa]['matrix'] + mats_by_pos[pb]['matrix'].T - tj['pot_bb'])
            r_fin = np.abs(r_raw[both]) if both.any() else np.zeros(1)
            sumchk = {'pot': tj['pot_bb'], 'cells_both_measured': float(both.mean()), 'max_abs_pair_sum_minus_pot_measured': float(r_fin.max()),
                      'max_abs_pair_sum_minus_pot_all_cells': float(np.abs(r_raw).max()),
                      'static_filled_cells_mean_abs_residual': float(np.abs(r_raw[~both]).mean()) if (~both).any() else 0.0}
        dM_prev = None
        pm = os.path.join(D, 'step%d/collect/tables_AB/node%d.json' % (k - 1, node)) if k > 0 else None
        if matrix and pm and os.path.exists(pm):
            try:
                prev = {x['position']: x for x in json.load(open(pm))['seats']}
                dM_prev = {}
                for pos_, mm in mats_by_pos.items():
                    if 'matrix' in prev.get(pos_, {}):
                        pl_ = next(q for q in tj['players'] if q['position'] == pos_)
                        op_ = next(q for q in tj['players'] if q['position'] != pos_)
                        wn_ = np.array(COMBOS) * np.array(pl_['class_keep_fraction']); wn_ = wn_ / wn_.sum()
                        dd_ = np.array(op_['class_keep_fraction']) * np.array(PRIOR); dd_ = dd_ / dd_.sum()
                        Mp = np.array(prev[pos_]['matrix']).reshape(169, 169)
                        dM_prev[pos_] = float((wn_[:, None] * dd_[None, :] * np.abs(mm['matrix'] - Mp)).sum())
            except (ValueError, KeyError):
                dM_prev = None
        rep['terminals'][str(j)] = {'node': node, 'line': tj['line'], 'matrix': matrix, 'sum_check': sumchk, 'dM_vs_prev_step': dM_prev, 'reach': next(float(r['reach']) for r in rows if int(r['term']) == j),
                                    'seats': seats, 'max_D_over_U': max((s['D_over_U'] or 0) for s in seats.values())}
    complete = not missing
    rep.update({'complete': complete, 'pass_D_le_U144': ok1, 'pass_rep_values': ok2v})
    rep['decision'] = ('incomplete: %d bundles missing' % len(missing) if not complete else
                       'flop failure after CFR+ retry -> stop rule 7장 (report)' if failed else
                       'step 0 never counts as a pass (minimum one update); next = (1-a) T_k + a V_AuB' if k == 0 else
                       'values pass (1)(2); root replication (3) needs the A-only / B-only full-tree solves' if ok1 and ok2v else
                       'continue: next tables = (1-a) T_k + a V_AuB')
    cd = os.path.join(sd, 'collect')
    os.makedirs(cd, exist_ok=True)
    json.dump(rep, open(os.path.join(cd, 'report.json'), 'w'), indent=1)
    if complete:
        for n, tabs in tables_raw.items():
            td = os.path.join(cd, 'tables_' + n)
            os.makedirs(td, exist_ok=True)
            man = {'schema': 't2_hu_continuation_manifest_v1', 'tables': []}
            for node, t in sorted(tabs.items()):
                json.dump(t, open(os.path.join(td, 'node%d.json' % node), 'w'))
                man['tables'].append({'file': 'node%d.json' % node, 'line': t['line']})
            json.dump(man, open(os.path.join(td, 'manifest.json'), 'w'), indent=1)
    print(json.dumps({'step': k, 'done': len(got), 'missing': len(missing), 'failed_boards': failed, 'pass1': ok1, 'pass2v': ok2v,
                      'worst': sorted(((t['max_D_over_U'], j) for j, t in rep['terminals'].items()), reverse=True)[:5]}))


def next_tables(k):
    """k단계 결과 → k+1단계 manifest: 고른 끝점 = (1-a)·T_k + a·V_A∪B (표가 없던 끝점은 V_A∪B 그대로, D/U 순환 끝점 a=0.25),
    고르지 않았지만 표가 있던 끝점(씨앗 등)은 그대로 옮긴다."""
    sd = os.path.join(D, 'step%d' % k)
    rep = json.load(open(os.path.join(sd, 'collect/report.json')))
    assert rep['complete'], 'collect incomplete'
    nd = os.path.join(D, 'step%d/tables' % (k + 1))
    os.makedirs(nd, exist_ok=True)
    cur_dir = os.path.join(sd, 'tables')
    cur = {}
    if os.path.exists(os.path.join(cur_dir, 'manifest.json')):
        for t in json.load(open(os.path.join(cur_dir, 'manifest.json')))['tables']:
            tab = json.load(open(os.path.join(cur_dir, t['file'])))
            cur[tab['node']] = tab
    hist = {}
    hp = os.path.join(D, 'history.json')
    if os.path.exists(hp):
        hist = json.load(open(hp))
    man = {'schema': 't2_hu_continuation_manifest_v1', 'tables': [], 'note': 'ft60 step %d tables from step %d' % (k + 1, k)}
    import numpy as np
    ab_dir = os.path.join(sd, 'collect/tables_AB')
    sn = os.path.join(sd, 'static_nodes.json')
    static_nodes = set(json.load(open(sn))) if os.path.exists(sn) else set()
    done_nodes = set()
    for j, tr in rep['terminals'].items():
        node = tr['node']
        h = hist.setdefault(str(node), [])
        h.append(tr['max_D_over_U'])
        cyc = len(h) >= 3 and h[-1] > 1 and (h[-3] - h[-2]) * (h[-2] - h[-1]) < 0
        a = ALPHA_CYCLE if cyc else ALPHA
        if node in static_nodes:      # 플랍 실패(재시도 후 > 0.6% pot 등)로 정적 유지로 정한 끝점: 표를 만들지 않는다
            done_nodes.add(node)
            continue
        tab = json.load(open(os.path.join(ab_dir, 'node%d.json' % node)))
        old = cur.get(node)
        has_m = any('matrix' in s_ for s_ in tab['seats'])
        if has_m:
            # 행렬 단위 섞기: new = (1-a)·old + a·M_new, old = 표의 행렬 | 벡터 표의 열 복제 | (표 없음) 정적 행렬. 처음 생기는 끝점도 a 로 섞는다(정적 행렬이 있을 때).
            tjn = json.load(open(os.path.join(sd, 'terms/term%02d.json' % int(j))))
            pot = tab['pot_bb']
            mix, kind, legacy_old = {}, 'matrix', False
            for s_ in tab['seats']:
                pos_ = s_['position']
                Mn = np.array(s_['matrix']).reshape(169, 169)
                Sm = static_mat(sd, node, pos_)
                if old is not None:
                    so = next(x for x in old['seats'] if x['seat'] == s_['seat'])
                    if so.get('matrix'):
                        Mo = np.array(so['matrix']).reshape(169, 169)
                    elif Sm is not None:
                        Mo = Sm        # 이전 표가 벡터뿐(행렬 이전 단계): 열 복제 벡터는 칸 단위로 합=팟이 안 되므로 정적 행렬을 이전 값으로 본다(기록: legacy_vector_old)
                        legacy_old = True
                    else:
                        Mo = np.tile(np.array(so['gross'])[:, None], (1, 169))
                    a_use = a
                elif Sm is not None:
                    Mo, a_use = Sm, a
                else:
                    Mo, a_use = Mn, 1.0
                mix[pos_] = (1 - a_use) * Mo + a_use * Mn
            if len(mix) == 2:       # 쌍마다 합 = 팟 으로 투영(칸 단위, 행렬 모양 유지)
                pa, pb = list(mix)
                r = mix[pa] + mix[pb].T - pot
                rep_pj = {'max_abs_residual_before': float(np.abs(r).max()), 'mean_abs_residual_before': float(np.abs(r).mean())}
                mix[pa] = mix[pa] - r / 2
                mix[pb] = mix[pb] - r.T / 2
                rep_pj['max_abs_residual_after'] = float(np.abs(mix[pa] + mix[pb].T - pot).max())
            else:
                rep_pj = None
            for s_ in tab['seats']:
                pos_ = s_['position']
                pl_ = next(q for q in tjn['players'] if q['position'] == pos_)
                op_ = next(q for q in tjn['players'] if q['position'] != pos_)
                dd_ = np.array(op_['class_keep_fraction']) * np.array(PRIOR); dd_ = dd_ / dd_.sum()
                s_['matrix'] = [round(float(x), 6) for x in mix[pos_].ravel()]
                s_['gross'] = [float(x) for x in mix[pos_] @ dd_]          # 진단용 접힌 벡터(엔진은 matrix 가 있으면 matrix 를 쓴다)
            tab['provenance'] = {'kind': 'ft60 step %d -> %d matrix mix (alpha %s%s)' % (k, k + 1, a, '' if old is not None else ', old = static matrix'), 'cycling': cyc,
                                 'pair_sum_projection': rep_pj, 'legacy_vector_old_replaced_by_static': legacy_old}
            man['tables'].append({'file': 'node%d.json' % node, 'line': tab['line'], 'alpha': a, 'matrix': True})
        else:
            if old is not None:
                og = {s['seat']: s['gross'] for s in old['seats']}
                for s in tab['seats']:
                    s['gross'] = [(1 - a) * x + a * y for x, y in zip(og[s['seat']], s['gross'])]
            tab['provenance'] = {'kind': 'ft60 step %d -> %d (alpha %s%s)' % (k, k + 1, a, ', no previous table: raw A u B' if old is None else ''),
                                 'cycling': cyc}
            man['tables'].append({'file': 'node%d.json' % node, 'line': tab['line'], 'alpha': a if old is not None else 1.0})
        json.dump(tab, open(os.path.join(nd, 'node%d.json' % node), 'w'))
        done_nodes.add(node)
    for node, tab in cur.items():
        if node not in done_nodes:
            json.dump(tab, open(os.path.join(nd, 'node%d.json' % node), 'w'))
            man['tables'].append({'file': 'node%d.json' % node, 'line': tab.get('line'), 'carried_over': True})
    json.dump(man, open(os.path.join(nd, 'manifest.json'), 'w'), indent=1)
    json.dump(hist, open(hp, 'w'), indent=1)
    print(json.dumps({'next_step': k + 1, 'tables': len(man['tables'])}))


if __name__ == '__main__' and sys.argv[1] in ('collect', 'next_tables'):
    (collect if sys.argv[1] == 'collect' else next_tables)(int(sys.argv[2]))
