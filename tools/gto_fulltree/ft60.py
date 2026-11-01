#!/usr/bin/env python3
"""60bb 전체 트리 시범(docs/GTO_FULLTREE_PILOT_60BB.md) — 모으는 세션 도구. 계산·기록만, 런타임 연결 없음.

  python3 tools/gto_fulltree/ft60.py seeds                 # 0단계 표 manifest(BB 보정 씨앗 → 전체 트리 노드 번호)
  python3 tools/gto_fulltree/ft60.py prepare <k> <ck.gtop> <dump.jsonl>   # k단계 끝점 고르기 + 끝점 입력 + 묶음 목록
  python3 tools/gto_fulltree/ft60.py timing <out_dir> <n_terms> <n_boards>   # 3벳 팟 끝점 보드 시간 실측(0단계 전, 부모 덤프 레인지)

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
WORK = os.environ.get('FT_WORK', '/home/user/gto_ckpt/ft60')
BIN = os.path.join(CALC, 'vendor/gtopen/target/release/examples')
CFG = os.path.join(CALC, 'data/gto_spot/plan_a/cfg_p60_o25.json')
D = os.path.join(REPO, 'data/ft60')
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
    if n_raises(line) >= 2:   # rule v3: 3-bet-or-larger pots carry range-reactive matrices
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
    # 묶음 → 보드 세션 배분(가장 긴 것부터 가장 덜 찬 세션에): 예상 시간 = 행렬 끝점 1.9h(실측 9.4절), 그 밖 0.8h(추정, 0단계 결과로 고침)
    n_sess = int(os.environ.get('FT_SESSIONS', '5'))
    load = [0.0] * n_sess
    assign = []
    for r in sorted(rows, key=lambda r: (-(1.9 if r['matrix'] else 0.8), -r['reach'], r['bundle'])):
        i = min(range(n_sess), key=lambda x: (load[x], x))
        load[i] += 1.9 if r['matrix'] else 0.8
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
    dump = '/home/user/gto_ckpt/plan_a/p60_o25/dump.jsonl'
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
    else:
        raise SystemExit(__doc__)
