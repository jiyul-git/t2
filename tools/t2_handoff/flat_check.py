"""플랫콜 연결 확인: 연결 함수(gto_pf.defend_vs_open)가 기록 값을 클래스별로 그대로 내는가.

  python3 tools/t2_handoff/flat_check.py <기록폴더>
기록이 섞인 빈도(예: 콜 60%·폴드 40%)면 pfcmp(클래스당 2회 표본)는 몇 %p 흔들린다. 이 검사가 정확한 확인이다.
"""
import glob, json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import gto_pf as G
name = lambda s: {'utg1': 'UTG+1', 'utg2': 'UTG+2'}.get(s, s.upper())
def hand_of(c):
    return [c[0] + 'h', c[1] + 'd'] if len(c) == 2 else [c[0] + 'h', c[1] + ('h' if c[2] == 's' else 'd')]
bad = 0
for path in sorted(glob.glob(os.path.join(sys.argv[1], 'p[0-9]*_flat_*_vs_*.json'))):
    rec = json.load(open(path)); m = re.match(r'p(\d+)_flat_([a-z0-9]+)_vs_([a-z0-9]+)$', rec['id'])
    if not m or '_limp_' in rec['id']:
        continue
    n = next(x for x in rec['nodes'] if x['scope'] == '3-bet response' and not x['off_path'])
    ob = float(n['actions'][1].split()[1]); worst = 0
    for c, h in n['hands'].items():
        f = h['freq']
        ref = {'fold': f['Fold'], 'call': sum(v for a, v in f.items() if a.startswith('Call')),
               'r3': sum(v for a, v in f.items() if a.startswith('3-bet')), 'jam': sum(v for a, v in f.items() if a.startswith('All-in'))}
        g = G.defend_vs_open(name(m.group(2)), name(m.group(3)), 9, int(m.group(1)), hand_of(c), ob)
        if g is None:
            print('NOT CONNECTED', rec['id']); bad += 1; break
        worst = max(worst, max(abs(g[k] - ref[k]) for k in ref))
    else:
        print('%-26s max |hook - record| = %.4f' % (rec['id'], worst)); bad += worst > 0.002
sys.exit(1 if bad else 0)
