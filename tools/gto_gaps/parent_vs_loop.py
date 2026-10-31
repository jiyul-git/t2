#!/usr/bin/env python3
"""부모 트리(간이 플랍 모델) BB 수비 vs 플랫콜 루프 보정 기록 — 같은 짝·같은 스택·같은 오픈 크기에서 클래스별 차이.

  python3 tools/gto_gaps/parent_vs_loop.py <out_json> <chart30_open25.json> <chart40_open25.json>

읽는 것(측정만):
  - 보정 기록: test3 data/gto_records/p{S}_flat_<opener>_vs_bb[_o25].json.gz (루프 뿌리 = BB 첫 응답)
  - 부모: 30·40bb 2.0 오픈 = s30/s40(pushfold_record_v1), 60·100bb 2.5 오픈 = s60/s100(open25 판, test3 사본),
          30·40bb 2.5 오픈 = claude/open_sizes_20261024 의 chart_{30,40}bb_open25_parent.json (vs_open 노드)
행동은 네 묶음으로 합친다: fold / call / r3(일반 3벳 크기 모두) / jam. 클래스 가중치 = 루프 뿌리에 도착하는 BB 콤보(=169 클래스 전부).
차이 지표: 클래스별 TV 거리 0.5·Σ|p−q|, 콤보 가중 평균·최대, 행동별 부호 있는 차이(부모 − 루프)의 콤보 가중 평균,
그리고 전체 빈도(mix) 차이. 핸드군별(페어/수티드 A/수티드 브로드웨이/수티드 커넥터·기타/오프수트 브로드웨이/오프수트 A/오프수트 기타)로도 나눈다.
"""
import gzip
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REC = os.path.join(ROOT, 'data', 'gto_records')
NAME = {'utg': 'UTG', 'utg1': 'UTG+1', 'utg2': 'UTG+2', 'lj': 'LJ', 'hj': 'HJ', 'co': 'CO', 'btn': 'BTN', 'sb': 'SB'}
GROUPS = ('pair', 'Axs', 'suited_broadway', 'suited_other', 'Axo', 'offsuit_broadway', 'offsuit_other')


def load(p):
    return json.load(gzip.open(p) if p.endswith('.gz') else open(p))


def kind(a):
    if a == 'Fold':
        return 'fold'
    if a.startswith('Call'):
        return 'call'
    if a.startswith('All-in'):
        return 'jam'
    if a.startswith('3-bet') or a.startswith('Raise'):
        return 'r3'
    raise ValueError(a)


def group(c):
    hi = 'TJQKA'
    if len(c) == 2:
        return 'pair'
    s = c[2] == 's'
    if c[0] == 'A':
        return 'Axs' if s else 'Axo'
    if c[0] in hi and c[1] in hi:
        return 'suited_broadway' if s else 'offsuit_broadway'
    return 'suited_other' if s else 'offsuit_other'


def agg4(freq):
    out = dict(fold=0.0, call=0.0, r3=0.0, jam=0.0)
    for a, v in freq.items():
        out[kind(a)] += float(v)
    return out


def loop_root(rec):
    n = next(x for x in rec['nodes'] if x['scope'] == '3-bet response' and not x['off_path'])
    return n['actions'], {c: (h['combos'], agg4(h['freq'])) for c, h in n['hands'].items()}


def parent_pushfold(rec, opener):
    labels = rec['class_labels']
    for n in rec['nodes']:
        if n['actor'] != 'BB' or n['situation'] != 'facing_open_or_jam':
            continue
        acts = [x.split(':', 1) for x in n['line'] if not x.endswith(':Fold')]
        if len(acts) == 1 and acts[0][0] == opener and acts[0][1].startswith('Raise'):
            cs = n['class_strategy']
            return n['actions'], {c: agg4({a: cs[a][i] for a in n['actions']}) for i, c in enumerate(labels)}
    return None


def parent_chart(ch, opener, open_bb):
    for n in ch['nodes']:
        if n.get('kind') != 'vs_open' or n['actor'] != 'BB':
            continue
        acts = [x.split(':', 1) for x in n['line'] if not x.endswith(':Fold')]
        if (len(acts) == 1 and acts[0][0] == opener and acts[0][1].startswith('Raise')
                and abs(float(acts[0][1].split()[1]) - open_bb) < 1e-6):      # 차트에 2.0·2.5 오픈이 둘 다 있다
            return n['actions'], {c: agg4(h['freq']) for c, h in n['hands'].items()}
    return None


def compare(lp, pp):
    tot = 0.0
    tv_w = 0.0
    tv_max = (0.0, None)
    signed = defaultdict(float)
    mix_l = defaultdict(float)
    mix_p = defaultdict(float)
    gw = defaultdict(float)
    gtv = defaultdict(float)
    gsig = defaultdict(lambda: defaultdict(float))
    per = []
    for c, (w, fl) in lp.items():
        fp = pp.get(c)
        if fp is None or w <= 0:
            continue
        tv = 0.5 * sum(abs(fp[k] - fl[k]) for k in fl)
        tot += w
        tv_w += w * tv
        if tv > tv_max[0]:
            tv_max = (tv, c)
        g = group(c)
        gw[g] += w
        gtv[g] += w * tv
        for k in fl:
            signed[k] += w * (fp[k] - fl[k])
            mix_l[k] += w * fl[k]
            mix_p[k] += w * fp[k]
            gsig[g][k] += w * (fp[k] - fl[k])
        per.append((c, round(tv, 3), {k: round(fp[k] - fl[k], 3) for k in fl}))
    per.sort(key=lambda x: -x[1])
    r = lambda x: round(x, 4)
    return {
        'combos': tot,
        'tv_mean': r(tv_w / tot), 'tv_max': r(tv_max[0]), 'tv_max_class': tv_max[1],
        'share_classes_tv_gt_10pp': r(sum(lp[c][0] for c, tv, _ in per if tv > 0.10) / tot),
        'signed_parent_minus_loop': {k: r(v / tot) for k, v in signed.items()},
        'mix_loop': {k: r(v / tot) for k, v in mix_l.items()},
        'mix_parent': {k: r(v / tot) for k, v in mix_p.items()},
        'by_group': {g: {'combos': gw[g], 'tv_mean': r(gtv[g] / gw[g]),
                         'signed': {k: r(v / gw[g]) for k, v in gsig[g].items()}} for g in GROUPS if gw[g]},
        'worst_classes': per[:12],
    }


def main():
    out_path, c30, c40 = sys.argv[1], sys.argv[2], sys.argv[3]
    charts = {30: load(c30), 40: load(c40)}
    parents = {S: load(os.path.join(REC, 's%d.json.gz' % S)) for S in (30, 40, 60, 100)}
    res = []
    for f in sorted(os.listdir(REC)):
        if '_flat_' not in f or '_limp_' in f:
            continue
        rid = f.replace('.json.gz', '')
        S, op, o25 = rid.split('_')[0][1:], rid.split('_')[2], rid.endswith('_o25')
        S = int(S)
        opener = NAME[op]
        rec = load(os.path.join(REC, f))
        lacts, lp = loop_root(rec)
        open_bb = float(lacts[1].split()[1])
        if o25 and S in (30, 40):
            p = parent_chart(charts[S], opener, open_bb)
            psrc = 'chart_%dbb_open25_parent' % S
        elif not o25 and S in (30, 40):
            p = parent_pushfold(parents[S], opener)
            psrc = 's%d' % S
        elif o25 and S in (60, 100):
            p = parent_pushfold(parents[S], opener)
            psrc = 's%d(open25)' % S
        else:
            p = None
            psrc = None
        if p is None:
            res.append({'id': rid, 'parent': psrc, 'missing_parent': True})
            continue
        pacts, pp = p
        if [kind(a) for a in pacts] != [kind(a) for a in lacts] or pacts[1] != lacts[1]:
            res.append({'id': rid, 'parent': psrc, 'action_mismatch': [pacts, lacts]})
            continue
        row = {'id': rid, 'stack': S, 'opener': opener, 'open_bb': open_bb, 'parent': psrc,
               'loop_status': rec['method'], 'loop_converged': rec['loop_converged']}
        row.update(compare(lp, pp))
        res.append(row)
    json.dump(res, open(out_path, 'w'), indent=1, ensure_ascii=False)
    for r in res:
        if 'tv_mean' not in r:
            print(r['id'], 'SKIP', {k: v for k, v in r.items() if k != 'id'})
            continue
        s = r['signed_parent_minus_loop']
        print('%-26s %-22s tv %.3f max %.2f(%s) >10pp %.0f%% | call %+.3f fold %+.3f r3 %+.3f jam %+.3f | loop fold %.3f parent fold %.3f' % (
            r['id'], r['parent'], r['tv_mean'], r['tv_max'], r['tv_max_class'], 100 * r['share_classes_tv_gt_10pp'],
            s['call'], s['fold'], s['r3'], s['jam'], r['mix_loop']['fold'], r['mix_parent']['fold']))


if __name__ == '__main__':
    main()
