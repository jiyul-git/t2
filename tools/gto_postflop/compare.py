"""GTO postflop strategy reports vs T2 bot decisions, same heads-up spots (measurement only).

  python3 tools/gto_postflop/compare.py <out.json> <spot>=<gto_reports_dir>:<t2_sim.jsonl.gz> ...

GTO side: per board report (t2_cont_panel T2_REPORT_OUT; lines = report_lines(), pair-mass weighted, turn/river pooled over every
card). T2 side: measure_t2_postflop.py decisions. Boards are pooled with the panel weights (stratum probability / boards per
stratum); inside a board a GTO node counts with its reach (pair mass at the node / at the root), a T2 node with its decision count.
Hand groups (classify.group): tp_plus (top pair or better), mid_pair (second / third / weak pair, underpair), draw (no pair; flush
draw, open-ended, combo), gutshot (no pair), air (no pair, nothing beyond backdoors).
"""
import glob
import gzip
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from classify import MADE, DRAW, group, GROUPS  # noqa: E402

PANEL = {'AcQc2c': 'monotone/A', 'AcKc6c': 'monotone/A', 'Tc9c7c': 'monotone/J_or_lower', 'Jc6c2c': 'monotone/J_or_lower',
         'Qc5c2c': 'monotone/KQ', 'KcQc6c': 'monotone/KQ', 'AdAc9c': 'paired/A', 'AdAcKc': 'paired/A', 'JdJc3c': 'paired/J_or_lower',
         '6d6c3c': 'paired/J_or_lower', 'KcJhJd': 'paired/KQ', 'Kc3d3c': 'paired/KQ', 'Ac4d3h': 'rainbow/A', 'Ac4d2h': 'rainbow/A',
         'Tc9d5h': 'rainbow/J_or_lower', '9c7d4h': 'rainbow/J_or_lower', 'Kc7d4h': 'rainbow/KQ', 'KcTd9h': 'rainbow/KQ',
         'AcQdJc': 'twotone/A', 'AcKd5d': 'twotone/A', '6c4d3d': 'twotone/J_or_lower', '8c4d3d': 'twotone/J_or_lower',
         'Qc9d7d': 'twotone/KQ', 'Qc4d3c': 'twotone/KQ'}
PROB = {'monotone/A': 0.011945701357466063, 'monotone/J_or_lower': 0.02171945701357466, 'monotone/KQ': 0.01809954751131222,
        'paired/A': 0.026244343891402715, 'paired/J_or_lower': 0.09954751131221719, 'paired/KQ': 0.04597285067873303,
        'rainbow/A': 0.07167420814479639, 'rainbow/J_or_lower': 0.13031674208144797, 'rainbow/KQ': 0.1085972850678733,
        'twotone/A': 0.10751131221719457, 'twotone/J_or_lower': 0.19547511312217195, 'twotone/KQ': 0.16289592760180996}
PW = {b: PROB[s] / 2 for b, s in PANEL.items()}
TEXTURES = ['rainbow', 'twotone', 'monotone', 'paired']

# named nodes: (name, key, actor role, Korean label). SRP = single-raised pot (IP = opener, OOP = BB caller).
SRP_NODES = [
    ('flop_oop_lead', '', 'OOP', '플랍 BB 먼저 벳(동크)'),
    ('flop_ip_cbet', 'a0', 'IP', '플랍 컨티뉴에이션 벳(BB 체크 뒤)'),
    ('flop_oop_vs_cbet', 'a0,a1', 'OOP', '플랍 컨벳 받은 BB(폴드/콜/체크레이즈)'),
    ('flop_ip_vs_xr', 'a0,a1,a2', 'IP', '플랍 체크레이즈 받은 오프너'),
    ('flop_ip_vs_lead', 'a1', 'IP', '플랍 동크 받은 오프너'),
    ('turn_ip_barrel', 'a0,a1,a1,c,a0', 'IP', '턴 두 번째 벳(플랍 벳-콜 뒤)'),
    ('turn_oop_vs_barrel', 'a0,a1,a1,c,a0,a1', 'OOP', '턴 벳 받은 BB'),
    ('turn_oop_probe', 'a0,a0,c', 'OOP', '턴 BB 먼저 벳(플랍 체크-체크 뒤)'),
    ('turn_ip_delayed', 'a0,a0,c,a0', 'IP', '턴 늦은 벳(플랍 체크-체크, 턴 BB 체크 뒤)'),
    ('river_ip_3barrel', 'a0,a1,a1,c,a0,a1,a1,c,a0', 'IP', '리버 세 번째 벳(벳-콜, 벳-콜 뒤)'),
    ('river_oop_vs_3barrel', 'a0,a1,a1,c,a0,a1,a1,c,a0,a1', 'OOP', '리버 세 번째 벳 받은 BB'),
]
# 3-bet pot: OOP = SB (3-bettor, preflop aggressor), IP = BTN (caller)
TBP_NODES = [
    ('flop_oop_cbet', '', 'OOP', '플랍 컨벳(3벳한 SB)'),
    ('flop_ip_vs_cbet', 'a1', 'IP', '플랍 컨벳 받은 BTN'),
    ('flop_ip_stab', 'a0', 'IP', '플랍 SB 체크 뒤 BTN 벳'),
    ('flop_oop_vs_stab', 'a0,a1', 'OOP', 'SB 체크 뒤 벳 받은 SB(체크레이즈)'),
    ('turn_oop_barrel', 'a1,a1,c', 'OOP', '턴 두 번째 벳(SB, 플랍 벳-콜 뒤)'),
    ('turn_ip_vs_barrel', 'a1,a1,c,a1', 'IP', '턴 벳 받은 BTN'),
    ('river_oop_3barrel', 'a1,a1,c,a1,a1,c', 'OOP', '리버 세 번째 벳(SB)'),
]


def gto_board(rep):
    roles = {int(k): v for k, v in rep['roles'].items()}
    return rep, roles


def gto_node_stats(reps, key, role):
    """pooled GTO action frequencies at one node: overall, per group, top pair alone, per texture"""
    acc = {}

    def add(slot, w, freqs, acts):
        a = acc.setdefault(slot, {'w': 0.0, 'f': [0.0] * len(acts), 'acts': acts})
        a['w'] += w
        for i, f in enumerate(freqs):
            a['f'][i] += w * f

    for b, rep in reps.items():
        L = rep['lines']
        n = L.get(key)
        if not n or n['kind'] != 'action':
            continue
        actor = n['actor']
        if rep['roles'][str(actor)] != role_pos(rep, role):
            continue
        root_w = L['']['players'][actor]['w']
        pw = PW[b] / root_w
        acts = n['kinds']
        pl = n['players'][actor]
        tex = PANEL[b].split('/')[0]
        add('all', pw * pl['w'], n['freqs'], acts)
        add('tex:' + tex, pw * pl['w'], n['freqs'], acts)
        cats = pl.get('cats')
        if not cats or not cats.get('joint'):
            continue
        for mi, m in enumerate(MADE):
            for di, d in enumerate(DRAW):
                c = cats['joint'][mi * len(DRAW) + di]
                if c['w'] <= 0:
                    continue
                g = group(m, d)
                add('grp:' + g, pw * c['w'], c['freqs'], acts)
                add('grp:%s|tex:%s' % (g, tex), pw * c['w'], c['freqs'], acts)
                if m == 'top_pair':
                    add('top_pair', pw * c['w'], c['freqs'], acts)
                    add('top_pair|tex:' + tex, pw * c['w'], c['freqs'], acts)
    return {k: {'w': v['w'], 'freq': {a: v['f'][i] / v['w'] for i, a in enumerate(v['acts'])}} for k, v in acc.items() if v['w'] > 0}


def role_pos(rep, role):
    return rep['roles']['0'] if role == 'OOP' else rep['roles']['1']


def t2_node_stats(hands, key, role):
    acc = {}

    def add(slot, kind):
        a = acc.setdefault(slot, {'n': 0, 'w': 0.0, 'f': {}})
        a['n'] += 1
        a['w'] += w
        a['f'][kind] = a['f'].get(kind, 0.0) + w

    for h in hands:
        w = PW[h['board']]
        tex = PANEL[h['board']].split('/')[0]
        for d in h['decisions']:
            if d['key'] != key or d['role'] != role:
                continue
            add('all', d['kind'])
            add('tex:' + tex, d['kind'])
            add('grp:' + d['group'], d['kind'])
            add('grp:%s|tex:%s' % (d['group'], tex), d['kind'])
            if d['made'] == 'top_pair':
                add('top_pair', d['kind'])
                add('top_pair|tex:' + tex, d['kind'])
    return {k: {'n': v['n'], 'freq': {a: x / v['w'] for a, x in v['f'].items()}} for k, v in acc.items()}


def pooled_bet_opportunity(reps, hands):
    """per street and role: every decision with no bet to face where the GTO menu allows a bet (no turn/river lead into the
    previous street's aggressor), pooled over lines. Each side keeps its own line distribution."""
    out = {}
    for street_i, street in enumerate(['flop', 'turn', 'river']):
        for role in ('OOP', 'IP'):
            g = {}
            for b, rep in reps.items():
                L = rep['lines']
                pos = role_pos(rep, role)
                actor = 0 if role == 'OOP' else 1
                root_w = L['']['players'][actor]['w']
                scale = {0: 1.0, 1: 49.0, 2: 49.0 * 48.0}[street_i]   # pooled card sums: one card factor per dealt street
                for k, n in L.items():
                    if n['kind'] != 'action' or n['street'] != street_i or n['actor'] != actor or n['kinds'][0] != 'check' or len(n['kinds']) < 2:
                        continue
                    pl = n['players'][actor]
                    cats = pl.get('cats')
                    base = PW[b] / root_w / scale
                    slot = g.setdefault('all', [0.0, 0.0])
                    slot[0] += base * pl['w']
                    slot[1] += base * pl['w'] * n['freqs'][1]
                    if cats and cats.get('joint'):
                        for mi, m in enumerate(MADE):
                            for di, d in enumerate(DRAW):
                                c = cats['joint'][mi * len(DRAW) + di]
                                if c['w'] <= 0:
                                    continue
                                for sl in ('grp:' + group(m, d),) + (('top_pair',) if m == 'top_pair' else ()):
                                    s = g.setdefault(sl, [0.0, 0.0])
                                    s[0] += base * c['w']
                                    s[1] += base * c['w'] * c['freqs'][1]
                    else:
                        g.setdefault('missing_cats_w', [0.0, 0.0])[0] += base * pl['w']
            t = {}
            for h in hands:
                w = PW[h['board']]
                last_aggr = {}
                for d in h['decisions']:
                    if d['kind'] in ('bet', 'raise'):
                        last_aggr[d['street']] = d['role']
                    if d['street'] != street or d['role'] != role or d['facing'] != 'none':
                        continue
                    prev = {'turn': 'flop', 'river': 'turn'}.get(street)
                    first_this_street = not any(x['street'] == street for x in h['decisions'][:h['decisions'].index(d)])
                    if role == 'OOP' and prev and first_this_street and last_aggr.get(prev) == 'IP':
                        continue   # donk into the previous street's aggressor: not on the GTO menu
                    for sl in ('all', 'grp:' + d['group']) + (('top_pair',) if d['made'] == 'top_pair' else ()):
                        s = t.setdefault(sl, [0.0, 0.0, 0])
                        s[0] += w
                        s[1] += w * (d['kind'] == 'bet')
                        s[2] += 1
            out['%s_%s' % (street, role)] = {
                'gto': {k: {'reach': v[0], 'bet': v[1] / v[0] if v[0] else None} for k, v in g.items()},
                't2': {k: {'n': v[2], 'bet': v[1] / v[0]} for k, v in t.items()}}
    return out


def sizes(hands):
    out = {}
    for h in hands:
        for d in h['decisions']:
            if d['kind'] == 'bet':
                out.setdefault('%s_%s' % (d['street'], d['role']), []).append(d['size_pot'])
    res = {}
    for k, v in out.items():
        v.sort()
        res[k] = {'n': len(v), 'median_pot_frac': v[len(v) // 2], 'p25': v[len(v) // 4], 'p75': v[3 * len(v) // 4]}
    return res


def main():
    outp = sys.argv[1]
    res = {}
    for arg in sys.argv[2:]:
        spot, rest = arg.split('=')
        rdir, simf = rest.split(':')
        reps = {}
        for f in sorted(glob.glob(os.path.join(rdir, '*.report.json'))):
            r = json.load(open(f))
            reps[r['board']] = r
        hands = [json.loads(x) for x in gzip.open(simf, 'rt')]
        nodes = TBP_NODES if '3b' in spot else SRP_NODES
        sres = {'boards_gto': len(reps), 'hands_t2': len(hands), 'roles': next(iter(reps.values()))['roles'], 'nodes': {}}
        for name, key, role, label in nodes:
            sres['nodes'][name] = {'key': key, 'role': role, 'label': label, 'gto': gto_node_stats(reps, key, role),
                                   't2': t2_node_stats(hands, key, role)}
        sres['bet_opportunity'] = pooled_bet_opportunity(reps, hands)
        sres['t2_bet_sizes'] = sizes(hands)
        res[spot] = sres
        print(spot, 'boards', len(reps), 'hands', len(hands), flush=True)
    json.dump(res, open(outp, 'w'), indent=1)


if __name__ == '__main__':
    main()
