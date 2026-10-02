#!/usr/bin/env python3
"""R2-A: does the pf_rank ordering reproduce each decision family's reference action set?

Read-only.  For every reference chart node and action family, the chart's action
mass m (combo-weighted, 0..1 of the relevant population) is compared with the
equal-mass slice that the code would take from an ordering:

  open / continue / allin / 3bet : top-m slice                 (how the code slices them)
  call                           : slice (m_3bet, m_3bet+m_call] (the code's (tp, tot] slice)

agreement = chart mass that falls inside the ordering's slice / m   (1.0 = same set)

Two orderings are measured so that "the ordering is fine but the quantity is
wrong" can be told apart from "the ordering itself is wrong":
  pf_rank   current production table (preflop.PCT)
  eq_random HU all-in equity vs a uniformly random hand (Monte Carlo, fixed seed)

The vs-3bet nodes are conditioned on the opener's own RFI chart (population =
hands the opener actually opened).  The reference set is the 8-max chart set
described in tools/r2_reference_charts.py; its conditions are partly unknown, so
these numbers measure ordering *shape*, not 9-max frequencies.

Usage: python tools/r2_ordering_fidelity.py <chart_root> [out.json]
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import preflop as PF, bot as B, ranges as R  # noqa: E402

N = lambda k: 6 if len(k) == 2 else (4 if k.endswith('s') else 12)
CLASSES = sorted(PF.PCT)


def eq_random_order(sims=6000):
    cache = os.path.join(ROOT, 'docs', 'semantic_audit', 'r2', 'eq_vs_random_169.json')
    if os.path.exists(cache):
        return json.load(open(cache))
    allc = [list(c) for c in R._SORTED]
    rep = {}
    for c in R._SORTED:
        rep.setdefault(PF.cls(list(c)), list(c))
    eq = {k: round(B.equity_vs_combos(h, [], [allc], sims=sims, seed=20261002), 4)
          for k, h in rep.items()}
    json.dump(eq, open(cache, 'w'), indent=0, sort_keys=True)
    return eq


def slice_weights(order, lo, hi, pop):
    """Per-class fraction inside the [lo, hi) mass slice of `order` over population pop."""
    tot = sum(N(k) * pop.get(k, 0.0) for k in CLASSES)
    if tot <= 0:
        return {}
    acc = 0.0
    out = {}
    for k in order:
        m = N(k) * pop.get(k, 0.0) / tot
        if m <= 0:
            continue
        a, b = acc, acc + m
        ov = max(0.0, min(b, hi) - max(a, lo))
        if ov > 0:
            out[k] = ov / m
        acc = b
    return out


def agreement(order, chart_w, pop, lo_mass=0.0):
    """chart_w: per-class action prob within pop.  Returns (m, agreement)."""
    tot = sum(N(k) * pop.get(k, 0.0) for k in CLASSES)
    m = sum(N(k) * pop.get(k, 0.0) * chart_w.get(k, 0.0) for k in CLASSES) / tot
    if m <= 1e-9:
        return 0.0, None
    sw = slice_weights(order, lo_mass, lo_mass + m, pop)
    inside = sum(N(k) * pop.get(k, 0.0) * chart_w.get(k, 0.0) * sw.get(k, 0.0)
                 for k in CLASSES) / tot
    return round(m, 4), round(inside / m, 4)


def acts(path):
    return json.load(open(path)).get('actions') or {}


def fam(a):
    r = {k: float(v.get('raise', 0)) for k, v in a.items()}
    al = {k: float(v.get('allin', 0)) for k, v in a.items()}
    c = {k: float(v.get('call', 0)) for k, v in a.items()}
    return {'continue': {k: r.get(k, 0) + al.get(k, 0) + c.get(k, 0) for k in a},
            '3bet': {k: r.get(k, 0) + al.get(k, 0) for k in a},
            'allin': al, 'call': c}


def main():
    root = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    eqr = eq_random_order()
    orders = {'pf_rank': sorted(CLASSES, key=lambda k: (PF.PCT[k], k)),
              'eq_random': sorted(CLASSES, key=lambda k: (-eqr[k], k))}
    uniform = {k: 1.0 for k in CLASSES}
    rows = []
    for st in sorted((s for s in os.listdir(root) if s.endswith('bb')), key=lambda s: int(s[:-2])):
        rfi = {}
        rd = os.path.join(root, st, 'rfi')
        if os.path.isdir(rd):
            for fn in sorted(os.listdir(rd)):
                a = acts(os.path.join(rd, fn))
                rfi[fn[:-5]] = fam(a)['continue']
                if fn[:-5] == 'SB':
                    w = {k: float(v.get('raise', 0)) + float(v.get('allin', 0)) for k, v in a.items()}
                    fams = {'open_raise': w}
                else:
                    fams = {'open': rfi[fn[:-5]]}
                for f, w in fams.items():
                    row = {'stack': st, 'node': 'rfi_' + fn[:-5], 'family': f}
                    for on, o in orders.items():
                        row['mass'], row[on] = agreement(o, w, uniform)
                    rows.append(row)
        vd = os.path.join(root, st, 'vs-open')
        if not os.path.isdir(vd):
            continue
        for fn in sorted(os.listdir(vd)):
            name = fn[:-5]
            if 'limp' in name:
                continue
            f = fam(acts(os.path.join(vd, fn)))
            pop = uniform
            if 'open-vs-' in name:
                op = name.split('open-vs-')[0]
                key = {'EP': 'UTG1', 'MP': 'LJ'}.get(op, op)
                if key not in rfi:
                    continue
                pop = rfi[key]
                kind = 'vs3bet'
            elif name.startswith('cold-'):
                kind = 'cold'
            else:
                kind = 'vs_open'
            for fam_name in ('continue', '3bet', 'allin'):
                row = {'stack': st, 'node': name, 'kind': kind, 'family': fam_name}
                for on, o in orders.items():
                    row['mass'], row[on] = agreement(o, f[fam_name], pop)
                if row['mass']:
                    rows.append(row)
            m3 = agreement(orders['pf_rank'], f['3bet'], pop)[0]
            row = {'stack': st, 'node': name, 'kind': kind, 'family': 'call'}
            for on, o in orders.items():
                row['mass'], row[on] = agreement(o, f['call'], pop, lo_mass=m3)
            if row['mass']:
                rows.append(row)
    res = {'orderings': list(orders), 'rows': rows,
           'note': 'vs3bet population = opener RFI chart (EP->UTG1, MP->LJ assumed)'}
    if out:
        open(out, 'w').write(json.dumps(res, indent=0) + '\n')
    for r in rows:
        print(r)


if __name__ == '__main__':
    main()
