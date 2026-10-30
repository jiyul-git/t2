"""멀티웨이 벳 빈도 보정 측정(재실행용). 프리플랍 GTO 표가 바뀔 때마다 다시 돌린다.

    python3 tools/multiway_calibration.py [--hands 300] [--seeds 9100,9101,9102,9103] [--old] [--jobs 4]

1) 같은 시드로 봇만 시뮬: multiway_betfreq.py(스트리트 × 팟 인원 × 패 강도 벳 표)와
   multiway_passivity_diag.py(탑페어·오버페어 결정 기록)를 시드별 병렬로 돌린다.
2) 벳 표와 탑페어/오버페어 '막은 항목' 건수, 밸류 사다리 구간과 반사실을 출력.
3) data/calibration/multiway_<커밋>_<gto sha 앞 8자>[_old].json 에 스냅샷(git 커밋, gto_pf_data.json sha256).

fit 절: 보정에 쓸 값은 여기서 **현재 레인지 기록으로 계산**한다(손으로 넣은 상수 금지).
지금은 진단만 — 계산값을 기록할 뿐 plan.py 에 적용하지 않는다(docs/MULTIWAY_PASSIVITY_DIAG_20261030.md).
"""
import sys, os, json, subprocess, hashlib, collections, argparse, tempfile
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, ROOT)
import plan as P

ap = argparse.ArgumentParser()
ap.add_argument('--hands', type=int, default=300)
ap.add_argument('--seeds', default='9100,9101,9102,9103')
ap.add_argument('--old', action='store_true', help='상대 레인지를 GTO 동기화 이전 경로로')
ap.add_argument('--jobs', type=int, default=4)
a = ap.parse_args()
SEEDS = [int(s) for s in a.seeds.split(',')]
ST = {3: 'flop', 4: 'turn', 5: 'river'}
CLS = ('tp_weak', 'tp_gk', 'overpair')


def sh(cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout.strip()


tmp = tempfile.mkdtemp(prefix='mwcal_')
procs, outs = [], []
for sd in SEEDS:
    j = os.path.join(tmp, 'diag_%d.jsonl' % sd); b = os.path.join(tmp, 'bf_%d.json' % sd)
    outs.append((j, b))
    procs.append(['python3', 'tools/multiway_passivity_diag.py', str(a.hands), str(sd), '--jsonl', j]
                 + (['--old'] if a.old else []))
    if not a.old:   # betfreq 는 현재 레인지 경로만 안다
        procs.append(['python3', 'tools/multiway_betfreq.py', str(a.hands), str(sd), '--json', b])
running = []
for cmd in procs:
    while len(running) >= a.jobs:
        running.pop(0).wait()
    running.append(subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
for p in running:
    p.wait()

rows = [json.loads(l) for j, _ in outs if os.path.exists(j) for l in open(j)]
bet = collections.Counter()
for _, b in outs:
    if os.path.exists(b):
        for k, (n, nb) in json.load(open(b))['rows'].items():
            bet[(k, 'n')] += n; bet[(k, 'bet')] += nb
bet_table = {k: {'n': bet[(k, 'n')], 'bet_pct': round(100.0 * bet[(k, 'bet')] / max(1, bet[(k, 'n')]), 1)}
             for (k, f) in bet if f == 'n'}


def term(r):
    w, p = r['why_bet'], r['plan']
    if p == 'pot_control':
        return 'pot_control'
    if p in ('showdown', 'giveup'):
        return p + ('(no-init)' if '이니셔티브 없음' in w else '(river)' if '리버' in w else '(cbet-freq)')
    if '상대에게 액션 우선' in w or '라인은 상대 것' in w:
        return 'line_owner'
    return 'value(p<1)' if p.startswith('value') else p


def band(eq, rel, n, mw0=False):
    _, v3, v2, pcz = P.multiway_value_thresholds(1 if mw0 else n, 0, 0)
    v3, v2 = P.relative_strength_value_threshold_shift(v3, v2, rel)
    return 'value' if eq >= v2 else 'mid' if eq >= pcz else 'weak'


def pct(c, n):
    return {k: round(100.0 * v / max(1, n), 1) for k, v in c.items()}


per = {}
for s in (3, 4, 5):
    for cls in CLS + ('tp',):
        g = [r for r in rows if r['street'] == s and (r['cls'] == cls or (cls == 'tp' and r['cls'] in CLS[:2]))]
        if not g:
            continue
        ok = [r for r in g if r['eq'] is not None and r['rel'] is not None]
        per['%s %s' % (ST[s], cls)] = {
            'n': len(g), 'bet_pct': round(100.0 * sum(r['bet'] for r in g) / len(g), 1),
            'mean_eq': round(sum(r['eq'] for r in ok) / max(1, len(ok)), 3),
            'blocking': dict(collections.Counter(term(r) for r in g if not r['bet']).most_common()),
            'band_now': pct(collections.Counter(band(r['eq'], r['rel'], r['n_opp']) for r in ok), len(ok)),
            'band_hu_equiv': pct(collections.Counter(
                band(r['eq'] ** (1.0 / r['n_opp']), r['rel_union'] or r['rel'], r['n_opp'], True) for r in ok), len(ok))}

# ---- fit: 현재 기록에서 계산(적용 안 함) ----
# 헤즈업 단위 기준 문턱(plan.multiway_value_thresholds(1)) 을 '전원 대비' 단위로 옮긴 값.
# 근사: 상대 N 명을 모두 이길 확률 ≈ (한 명 기준)^N. 여기서 N 은 기록된 팟 인원별로 둔다.
_, b3, b2, bz = P.multiway_value_thresholds(1, 0, 0)
fit = {}
for n in sorted({r['n_opp'] for r in rows}):
    g = [r for r in rows if r['n_opp'] == n and r['eq'] is not None and r['cls'] in CLS[:2]]
    fit['n_opp=%d' % n] = {
        'samples_tp': len(g), 'fair_share': round(1.0 / (n + 1), 3),
        'current_v3_v2_pcz': [round(x, 3) for x in P.multiway_value_thresholds(n, 0, 0)[1:]],
        'joint_unit_v3_v2_pcz': [round(b3 ** n, 3), round(b2 ** n, 3), round(bz ** n, 3)],
        'tp_mean_eq': round(sum(r['eq'] for r in g) / max(1, len(g)), 3)}

gto = os.path.join(ROOT, 'gto_pf_data.json')
snap = {'commit': sh(['git', 'rev-parse', 'HEAD']),
        'gto_pf_data_sha256': hashlib.sha256(open(gto, 'rb').read()).hexdigest(),
        'ranges': 'old_pre_sync' if a.old else 'current',
        'hands_per_seed': a.hands, 'seeds': SEEDS, 'fmt': os.environ.get('MW_FMT', 'standard'),
        'decision_rows': len(rows), 'bet_table': bet_table, 'top_pair_overpair': per, 'fit': fit,
        'applied': False}
od = os.path.join(ROOT, 'data', 'calibration'); os.makedirs(od, exist_ok=True)
fn = os.path.join(od, 'multiway_%s_%s%s.json' % (snap['commit'][:8], snap['gto_pf_data_sha256'][:8],
                                                  '_old' if a.old else ''))
json.dump(snap, open(fn, 'w'), ensure_ascii=False, indent=1)

print('commit %s gto %s ranges %s rows %d' % (snap['commit'][:8], snap['gto_pf_data_sha256'][:8], snap['ranges'], len(rows)))
for k in sorted(bet_table, key=lambda s: (['flop', 'turn', 'river'].index(s.split()[0]), s)):
    if k.split()[1] != '2':
        print('  %-26s n=%5d bet=%5.1f%%' % (k, bet_table[k]['n'], bet_table[k]['bet_pct']))
for k, v in per.items():
    print('  %-16s n=%3d bet=%5.1f%% eq=%.2f band %s -> hu-equiv %s\n      blocking %s'
          % (k, v['n'], v['bet_pct'], v['mean_eq'], v['band_now'], v['band_hu_equiv'], v['blocking']))
for k, v in fit.items():
    print('  fit %s %s' % (k, v))
print('snapshot', os.path.relpath(fn, ROOT))
