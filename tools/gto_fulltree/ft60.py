#!/usr/bin/env python3
"""60bb 전체 트리 시범(docs/GTO_FULLTREE_PILOT_60BB.md) — 모으는 세션 도구. 계산·기록만, 런타임 연결 없음.

  python3 tools/gto_fulltree/ft60.py seeds                 # 0단계 표 manifest(BB 보정 씨앗 → 전체 트리 노드 번호)
  python3 tools/gto_fulltree/ft60.py prepare <k> <ck.gtop> <dump.jsonl>   # k단계 끝점 고르기 + 끝점 입력 + 묶음 목록
  python3 tools/gto_fulltree/ft60.py timing <out_dir> <n_terms> <n_boards>   # 3벳 팟 끝점 보드 시간 실측(0단계 전, 부모 덤프 레인지)
  python3 tools/gto_fulltree/ft60.py collect <k>        # 보드 세션 결과 모으기 → step<k>/collect/report.json + tables_{A,B,AB}
  python3 tools/gto_fulltree/ft60.py next_tables <k>    # k+1단계 표(감쇠) manifest

환경: FT_CALC (계산 체크아웃, 기본 /home/user/calc — census 79a9aca6 + 전략 저장 패치 + t2_ft_export), FT_WORK(기본 /home/user/gto_ckpt/ft<스택>).
스택 매개변수(기본 60 = 기존 동작 그대로): FT_STACK=100 → 설정 cfg_p100_o25.json, 데이터 data/ft100/, 작업 폴더 ft100, 보드 브랜치 claude/ft100_board_<n>.
  FT_MIN_REACH=1e-3 (끝점 고르기: 도달 >= 값인 헤즈업 끝점 전부; 없으면 위쪽 N_TERMS=FT_N_TERMS(기본 40)개), FT_SESSIONS(기본 5),
  FT_H_MATRIX / FT_H_SIMPLE (묶음 예상 시간(h) 배분용, 기본 1.9 / 0.8 = 60bb 실측).
"""
import gzip
import hashlib
import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
STACK = os.environ.get('FT_STACK', '60')
TAG = 'ft' + STACK                # ft60 (기본) / ft100 ...
CALC = os.environ.get('FT_CALC', '/home/user/calc')
WORK = os.environ.get('FT_WORK', '/home/user/gto_ckpt/' + TAG)
BIN = os.path.join(CALC, 'vendor/gtopen/target/release/examples')
CFG = os.path.join(CALC, 'data/gto_spot/plan_a/cfg_p%s_o25.json' % STACK)
D = os.path.join(REPO, 'data/' + TAG)
N_TERMS = int(os.environ.get('FT_N_TERMS', '40'))   # 사용자 결정 10-31: 헤즈업 끝점 40개
MIN_REACH = float(os.environ['FT_MIN_REACH']) if os.environ.get('FT_MIN_REACH') else None   # 지정하면 N_TERMS 대신 도달 >= 값인 끝점 전부
H_MATRIX = float(os.environ.get('FT_H_MATRIX', '1.9'))
H_SIMPLE = float(os.environ.get('FT_H_SIMPLE', '0.8'))
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


def export(ck, lines, out, manifest=None):
    jobs = out + '.jobs'
    open(jobs, 'w').write('\n'.join(lines) + '\n')
    env = dict(os.environ)
    env.pop('T2_CONT_FILE', None)
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
           'note': ('step 0 seeds: BB loop final tables (p60 HJ, LJ o25); every other terminal static (docs/GTO_FULLTREE_PILOT_60BB.md 3장)' if STACK == '60' else
                    'step 0 seeds: BB loop final tables (%s); every other terminal static (docs/GTO_FULLTREE_100BB.md)' % ', '.join(sorted(os.listdir(os.path.join(D, 'seed')))))}
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
    if n_raises(line) >= 2:   # rule v3: 3-bet-or-larger pots carry range-reactive matrices
        out['matrix_opp_classes'] = {p['position']: [h for h in range(169) if p['class_keep_fraction'][h] > 0] for p in players}
    return out


def prepare(k, ck, dump, n=N_TERMS, sd=None):
    cfg = json.load(open(CFG))
    sd = sd or os.path.join(D, 'step%d' % k)
    os.makedirs(os.path.join(sd, 'terms'), exist_ok=True)
    hu = hu_terminals(dump)
    tot = sum(w for w, _ in hu)
    pick = hu[:n] if MIN_REACH is None else [x for x in hu if x[0] >= MIN_REACH]
    man = os.path.join(sd, 'tables/manifest.json')
    info = export(ck, [l for _, l in pick], os.path.join(WORK, 'step%d_export.jsonl' % k), man if os.path.exists(man) else None)
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
    # 묶음 → 보드 세션 배분(가장 긴 것부터 가장 덜 찬 세션에): 예상 시간 = 행렬 끝점 H_MATRIX(60bb 실측 1.9h, 9.4절), 그 밖 H_SIMPLE(0.8h)
    n_sess = int(os.environ.get('FT_SESSIONS', '5'))
    load = [0.0] * n_sess
    assign = []
    for r in sorted(rows, key=lambda r: (-(H_MATRIX if r['matrix'] else H_SIMPLE), -r['reach'], r['bundle'])):
        i = min(range(n_sess), key=lambda x: (load[x], x))
        load[i] += H_MATRIX if r['matrix'] else H_SIMPLE
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
    dump = '/home/user/gto_ckpt/plan_a/p%s_o25/dump.jsonl' % STACK
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
    """원격의 claude/ft<스택>_board_* 브랜치에서 step k 결과를 out/<bundle>/ 로 꺼낸다(done.json 이 있는 것만, sha 확인)."""
    refs = [l.split()[1] for l in _git('ls-remote', 'origin', 'refs/heads/claude/%s_board_*' % TAG).stdout.splitlines()]
    got = {}
    for ref in refs:
        br = ref.replace('refs/heads/', '')
        _git('fetch', '-q', '--depth=1', 'origin', '+' + br + ':refs/remotes/origin/' + br)   # '+': 얕은 ref 는 조상 확인이 안 돼 + 없으면 갱신이 거부된다
        ls = _git('ls-tree', '-r', '--name-only', 'origin/' + br, 'data/%s/results/step%d' % (TAG, k)).stdout.split()
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
            ok1 &= p1 or exempt
            ok2v &= p2 or exempt
            for n in ('A', 'B', 'AB'):
                t = tables_raw[n].setdefault(node, {'schema': 't2_hu_continuation_table_v1', 'node': node, 'line': tj['line'],
                                                    'live': tj['terminal_live_mask'], 'pot_bb': tj['pot_bb'], 'value_convention': 'gross_share',
                                                    'seats': [], 'provenance': {'kind': '%s step %d panel %s (raw%s)' % (TAG, k, n, ', matrix x arriving dist' if matrix else '')}})
                t['seats'].append({'seat': pl['seat'], 'position': pos, 'gross': [float(x) for x in V[n]], 'se': raw[n][1][pos]})
        rep['terminals'][str(j)] = {'node': node, 'line': tj['line'], 'matrix': matrix, 'reach': next(float(r['reach']) for r in rows if int(r['term']) == j),
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
    man = {'schema': 't2_hu_continuation_manifest_v1', 'tables': [], 'note': '%s step %d tables from step %d' % (TAG, k + 1, k)}
    ab_dir = os.path.join(sd, 'collect/tables_AB')
    done_nodes = set()
    # 플랍 실패 판정(재시도 뒤 0.6% pot 초과)으로 정적 유지가 정해진 끝점: 새 표를 만들지 않고, 이전 표가 있어도 옮기지 않는다
    fd = os.path.join(sd, 'flop_failure_decision.json')
    static_nodes = {int(v.split()[1]) for v in json.load(open(fd)).get('static_terminals', {}).values()} if os.path.exists(fd) else set()
    for j, tr in rep['terminals'].items():
        node = tr['node']
        if node in static_nodes:
            done_nodes.add(node)
            continue
        h = hist.setdefault(str(node), [])
        h.append(tr['max_D_over_U'])
        cyc = len(h) >= 3 and h[-1] > 1 and (h[-3] - h[-2]) * (h[-2] - h[-1]) < 0
        a = ALPHA_CYCLE if cyc else ALPHA
        tab = json.load(open(os.path.join(ab_dir, 'node%d.json' % node)))
        old = cur.get(node)
        if old is not None:
            og = {s['seat']: s['gross'] for s in old['seats']}
            for s in tab['seats']:
                s['gross'] = [(1 - a) * x + a * y for x, y in zip(og[s['seat']], s['gross'])]
        tab['provenance'] = {'kind': '%s step %d -> %d (alpha %s%s)' % (TAG, k, k + 1, a, ', no previous table: raw A u B' if old is None else ''),
                             'cycling': cyc}
        json.dump(tab, open(os.path.join(nd, 'node%d.json' % node), 'w'))
        man['tables'].append({'file': 'node%d.json' % node, 'line': tab['line'], 'alpha': a if old is not None else 1.0})
        done_nodes.add(node)
    for node, tab in cur.items():
        if node not in done_nodes and node not in static_nodes:
            json.dump(tab, open(os.path.join(nd, 'node%d.json' % node), 'w'))
            man['tables'].append({'file': 'node%d.json' % node, 'line': tab.get('line'), 'carried_over': True})
    json.dump(man, open(os.path.join(nd, 'manifest.json'), 'w'), indent=1)
    json.dump(hist, open(hp, 'w'), indent=1)
    print(json.dumps({'next_step': k + 1, 'tables': len(man['tables'])}))


if __name__ == '__main__' and sys.argv[1] in ('collect', 'next_tables'):
    (collect if sys.argv[1] == 'collect' else next_tables)(int(sys.argv[2]))
