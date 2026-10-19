"""GTO 계산기의 푸시/폴드 기록(pf10/15/20/25, quick) → T2 프리플랍 기준 데이터.

  python3 tools/gto_pf_build.py <pf10.json> <pf15.json> <pf20.json> <pf25.json>

출처: GTO 브랜치(claude/pushfold-10-25-20261019) data/gto_spot/records/pf*.json.
뽑는 것 (올인 관련만, 사용자 결정 2026-10-19):
  first_in  : 첫 진입 fold / open / jam 클래스별 빈도
  vs_jam    : 앞사람 전원 폴드 뒤 단독 올인에 콜하는 빈도 (올인자, 콜러)
  vs_3bjam  : 오픈 후 3벳 올인을 받은 오프너가 콜하는 빈도 (오프너, 올인자)
뺀 것: 오픈에 대한 플랫 콜(플랍 팟을 간이 모델로 계산 — 신뢰 낮음), 오버콜,
       공격자 콤보 < 10 인 노드(GTO 가 거의 쓰지 않는 올인, unsupported).
"""
import json, os, sys

AGG_MIN = 10.0
out = {'schema': 't2_gto_pf_v1', 'source': [], 'buckets': [], 'classes': None,
       'first_in': {}, 'vs_jam': {}, 'vs_3bjam': {},
       'assumptions': {'symmetric_stack': True, 'chip_ev': True, 'ante_total_bb': 1.0,
                       'seats': 9, 'status': 'quick'}}
r3 = lambda v: [round(float(x), 3) for x in v]
for path in sys.argv[1:]:
    rec = json.load(open(path))
    S = str(int(rec['stack_bb']))
    out['buckets'].append(int(S))
    out['source'].append({'id': rec['id'], 'gap_total_exact_bb': rec['gap_total_exact_bb'],
                          'status': rec['status']})
    if out['classes'] is None:
        out['classes'] = rec['class_labels']
    assert out['classes'] == rec['class_labels']
    for n in rec['nodes']:
        line = [tuple(x.split(':', 1)) for x in n['line']]
        acts = [(p, a) for p, a in line if a != 'Fold']
        cs = n['class_strategy']
        jam = next((a for a in n['actions'] if a.startswith('All-in')), None)
        call = next((a for a in n['actions'] if a.startswith('Call')), None)
        opn = next((a for a in n['actions'] if a.startswith('Raise')), None)
        if n['situation'] == 'first_in':
            out['first_in'].setdefault(S, {})[n['actor']] = {
                'jam': r3(cs[jam]), 'open': r3(cs[opn]) if opn else None}
            continue
        if n['unsupported_low_reach'] or (n['aggressor_action_combos'] or 0) < AGG_MIN:
            continue
        if n['situation'] == 'facing_open_or_jam' and len(acts) == 1 and acts[0][1].startswith('All-in'):
            out['vs_jam'].setdefault(S, {})[acts[0][0] + '>' + n['actor']] = r3(cs[call])
        elif (n['situation'] == 'facing_3bet_jam' and len(acts) == 2
              and acts[0][0] == n['actor'] and acts[0][1].startswith('Raise')
              and acts[1][1].startswith('All-in')):
            out['vs_3bjam'].setdefault(S, {})[n['actor'] + '>' + acts[1][0]] = r3(cs[call])
dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'gto_pf', 'pushfold_v1.json')
json.dump(out, open(dst, 'w'), separators=(',', ':'))
print(dst, {k: {s: len(v) for s, v in out[k].items()} for k in ('first_in', 'vs_jam', 'vs_3bjam')})
