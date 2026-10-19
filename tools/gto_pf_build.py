"""GTO 계산기의 푸시/폴드 기록(pf10/15/20/25, quick) → T2 프리플랍 기준 데이터.

  python3 tools/gto_pf_build.py <pf10.json> <pf15.json> <pf20.json> <pf25.json> <s30.json> <s40.json>

출처: GTO 브랜치(claude/pushfold-10-25-20261019) data/gto_spot/records/pf*.json, s30.json, s40.json.
s30/s40 은 Plan A v2b 부모 메뉴(오픈 2.0, SB 림프/3.0, 3벳 3x 또는 올인)라 첫 진입에 림프가 있다.
뽑는 것 (올인 관련만, 사용자 결정 2026-10-19):
  first_in  : 첫 진입 fold / limp / open / jam 클래스별 빈도
  vs_jam    : 앞사람 전원 폴드 뒤 단독 올인에 콜하는 빈도 (올인자, 콜러)
  vs_3bjam  : 오픈 후 3벳 올인을 받은 오프너가 콜하는 빈도 (오프너, 올인자)
  vs_open   : 단독 오픈을 받은 자리의 3벳 올인 / 일반 3벳 빈도 (오프너, 수비자) — 공격만
  vs_3bet   : 오픈 후 일반 3벳을 받은 오프너의 4벳 올인 빈도 (오프너, 3벳터) — 공격만
뺀 것: 플랫 콜·림프(플랍 팟을 간이 모델로 계산 — 신뢰 낮음, 30bb SB 첫 진입 포함), 오버콜,
       공격자 콤보 < 10 인 노드(GTO 가 거의 쓰지 않는 올인, unsupported).
"""
import json, os, sys

AGG_MIN = 10.0
out = {'schema': 't2_gto_pf_v1', 'source': [], 'buckets': [], 'classes': None,
       'first_in': {}, 'vs_jam': {}, 'vs_3bjam': {}, 'vs_open': {}, 'vs_3bet': {},
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
        lmp = next((a for a in n['actions'] if a.startswith('Limp')), None)
        if n['situation'] == 'first_in':
            # SB 의 림프/오픈은 플랍 팟을 간이 모델로 매긴 값에 좌우된다(30bb 에서
            # 림프 80%·폴드 0%). 교정 전까지 SB 첫 진입은 림프가 있는 버킷에서 뺀다.
            if n['actor'] == 'SB' and lmp:
                continue
            out['first_in'].setdefault(S, {})[n['actor']] = {
                'jam': r3(cs[jam]) if jam else None, 'open': r3(cs[opn]) if opn else None,
                'limp': r3(cs[lmp]) if lmp else None}
            continue
        if n['unsupported_low_reach'] or (n['aggressor_action_combos'] or 0) < AGG_MIN:
            continue
        r3s = [a for a in n['actions'] if a.startswith('3-bet')]
        if n['situation'] == 'facing_open_or_jam' and len(acts) == 1 and acts[0][1].startswith('Raise'):
            # 오픈을 받은 자리의 공격(3벳/3벳 올인) 빈도만. 콜/폴드는 플랍 모델 의존이라 뺀다.
            r3sum = [sum(cs[a][i] for a in r3s) for i in range(len(rec['class_labels']))]
            out['vs_open'].setdefault(S, {})[acts[0][0] + '>' + n['actor']] = {
                'jam': r3(cs[jam]) if jam else None, 'r3': r3(r3sum)}
        elif (n['situation'] == 'facing_3bet' and len(acts) == 2
              and acts[0][0] == n['actor'] and acts[0][1].startswith('Raise')
              and acts[1][1].startswith('3-bet')):
            # 오프너가 일반 3벳을 받음: 4벳(이 트리에선 올인만) 빈도만.
            out['vs_3bet'].setdefault(S, {})[n['actor'] + '>' + acts[1][0]] = {
                'jam': r3(cs[jam]) if jam else None}
        elif n['situation'] == 'facing_open_or_jam' and len(acts) == 1 and acts[0][1].startswith('All-in'):
            out['vs_jam'].setdefault(S, {})[acts[0][0] + '>' + n['actor']] = r3(cs[call])
        elif (n['situation'] in ('facing_3bet_jam', 'facing_3bet') and len(acts) == 2
              and acts[0][0] == n['actor'] and acts[0][1].startswith('Raise')
              and acts[1][1].startswith('All-in')):
            out['vs_3bjam'].setdefault(S, {})[n['actor'] + '>' + acts[1][0]] = r3(cs[call])
dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'gto_pf_data.json')
json.dump(out, open(dst, 'w'), separators=(',', ':'))
print(dst, {k: {s: len(v) for s, v in out[k].items()} for k in ('first_in', 'vs_jam', 'vs_3bjam', 'vs_open', 'vs_3bet')})
