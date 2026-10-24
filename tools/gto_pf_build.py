"""GTO 계산기의 푸시/폴드 기록(pf10/15/20/25, quick) → T2 프리플랍 기준 데이터.

  python3 tools/gto_pf_build.py <pf10.json> <pf15.json> <pf20.json> <pf25.json> <s30.json> <s40.json> <s60.json> \
      [<p30_flat_btn_vs_bb.json> <p40_flat_btn_vs_bb.json> ...]

출처: GTO 브랜치(claude/pushfold-10-25-20261019) data/gto_spot/records/pf*.json, s30.json, s40.json;
s60.json 은 chatgpt/terminal-census-v2-20260930 (60bb v2b 부모, 2026-10-19).
s30/s40/s60 은 Plan A v2b 부모 메뉴(오픈 2.0, SB 림프/3.0, 3벳 3x 또는 올인)라 첫 진입에 림프가 있다.
뽑는 것 (올인 관련만, 사용자 결정 2026-10-19):
  first_in  : 첫 진입 fold / limp / open / jam 클래스별 빈도
  vs_jam    : 앞사람 전원 폴드 뒤 단독 올인에 콜하는 빈도 (올인자, 콜러)
  vs_3bjam  : 오픈 후 3벳 올인을 받은 오프너가 콜하는 빈도 (오프너, 올인자)
  vs_open   : 단독 오픈을 받은 자리의 3벳 올인 / 일반 3벳 빈도 (오프너, 수비자) — 공격만
  vs_3bet   : 오픈 후 일반 3벳을 받은 오프너의 4벳 올인 빈도 (오프너, 3벳터) — 공격만
  vs_open_full : 플랫콜 루프로 보정한 자리(spot_quick_v1, 사용자 결정 2026-10-20)만 —
                 단독 오픈(2.0bb)을 받은 수비자의 폴드 / 콜 / 3벳 / 3벳 올인 전체 빈도
                 (p30_flat_btn/co_vs_bb: claude/p30-flat-20261019, p40_flat_btn/co_vs_bb: census 브랜치)
  vs_3bet_full : 3벳 받은 오프너의 폴드 / 콜 / 작은 4벳 / 올인 전체(서브게임 기록 p<S>v1_*, 2026-10-24 연결)
  vs_limp_full : SB 림프를 받은 BB 의 체크 / 레이즈(p<S>_flat_sb_limp_vs_bb, CFR+ 재시도 기록, 2026-10-24 연결)
뺀 것: 보정 안 된 자리의 플랫 콜·림프(플랍 팟을 간이 모델로 계산 — 신뢰 낮음, 30bb SB 첫 진입 포함), 오버콜,
       공격자 콤보 < 10 인 노드(GTO 가 거의 쓰지 않는 올인, unsupported).
"""
import json, os, sys

AGG_MIN = 10.0
out = {'schema': 't2_gto_pf_v1', 'source': [], 'buckets': [], 'classes': None,
       'first_in': {}, 'vs_jam': {}, 'vs_3bjam': {}, 'vs_open': {}, 'vs_3bet': {}, 'vs_open_full': {},
       'vs_3bet_full': {}, 'vs_limp_full': {},
       'assumptions': {'symmetric_stack': True, 'chip_ev': True, 'ante_total_bb': 1.0,
                       'seats': 9, 'status': 'quick'}}
r3 = lambda v: [round(float(x), 3) for x in v]
def flat(rec):
    """플랫콜 루프 기록 → vs_open_full. 연결은 수비자의 첫 응답 노드만(깊은 노드는 연구용)."""
    import re
    m = re.match(r'p(\d+)_flat_([a-z0-9]+)_vs_([a-z0-9]+)$', rec['id'])
    S = str(int(m.group(1)))
    name = lambda s: {'utg1': 'UTG+1', 'utg2': 'UTG+2'}.get(s, s.upper())
    n = next(x for x in rec['nodes'] if x['scope'] == '3-bet response' and not x['off_path'])
    acts = n['actions']
    assert acts[0] == 'Fold' and acts[1].startswith('Call '), acts
    open_bb = float(acts[1].split()[1])                            # 오픈 크기(BTN·CO·HJ 2.0, SB 3.0)
    get = lambda c, f: sum(v for a, v in n['hands'][c]['freq'].items() if f(a))
    cols = {'fold': lambda a: a == 'Fold', 'call': lambda a: a.startswith('Call'),
            'r3': lambda a: a.startswith('3-bet'), 'jam': lambda a: a.startswith('All-in')}
    ent = {k: r3([get(c, f) for c in out['classes']]) for k, f in cols.items()}
    ent['open_bb'] = open_bb
    out['vs_open_full'].setdefault(S, {})[name(m.group(2)) + '>' + name(m.group(3))] = ent
    _src(rec)


def _src(rec):
    out['source'].append({'id': rec['id'], 'status': rec['status'], 'method': rec['method'],
                          'loop_converged': rec['loop_converged'], 'final_step': rec['final_step'],
                          'stopped_at_step_cap': bool(rec.get('stopped_at_step_cap')),
                          'stop_reason': rec.get('stop_reason'), 'status_note': rec.get('status_note')})


def _root(rec):
    """연결에 쓰는 노드는 서브게임 뿌리(첫 응답) 하나뿐이다. 깊은 노드는 연구용."""
    n = rec['nodes'][0]
    assert n['scope'] == '3-bet response' and not n['off_path'], (rec['id'], n['scope'], n['off_path'])
    return n


_POSN = lambda s: {'utg1': 'UTG+1', 'utg2': 'UTG+2'}.get(s, s.upper())


def threebet(rec):
    """3벳 받은 오프너의 전체 응답(서브게임 기록, 2026-10-22~23) → vs_3bet_full.

    id p<S>v1_<오프너>_vs_<3벳터>[_3b<배수x10>]. 뿌리 노드 행동: Fold / Call <3벳 크기> /
    4-bet <크기> / All-in. 오프너의 폴드·콜·작은 4벳·올인 빈도를 그대로 넣는다.
    """
    import re
    m = re.match(r'p(\d+)v1_([a-z0-9]+)_vs_([a-z0-9]+)(?:_3b\d+)?$', rec['id'])
    S = str(int(m.group(1)))
    n = _root(rec)
    acts = n['actions']
    assert acts[0] == 'Fold' and acts[1].startswith('Call '), acts
    tb_bb = float(acts[1].split()[1])                              # 3벳 크기(합계, bb)
    assert n['actor'] == _POSN(m.group(2)), (n['actor'], rec['id'])
    # 기록에는 그 자리에 실제로 도착하는 클래스(오프너가 오픈하는 패)만 있다. 없는 클래스는
    # null — 조회가 None 을 돌려 기존 판단이 맡는다(값을 지어내지 않는다).
    get = lambda c, f: (round(float(sum(v for a, v in n['hands'][c]['freq'].items() if f(a))), 3)
                        if c in n['hands'] else None)
    cols = {'fold': lambda a: a == 'Fold', 'call': lambda a: a.startswith('Call'),
            'r4': lambda a: a.startswith('4-bet'), 'jam': lambda a: a.startswith('All-in')}
    ent = {k: [get(c, f) for c in out['classes']] for k, f in cols.items()}
    ent['threebet_bb'] = tb_bb
    r4 = next((a for a in acts if a.startswith('4-bet')), None)
    ent['fourbet_bb'] = float(r4.split()[1]) if r4 else None
    out['vs_3bet_full'].setdefault(S, {})[_POSN(m.group(2)) + '>' + _POSN(m.group(3))] = ent
    _src(rec)


def limp(rec):
    """SB 림프를 받은 BB 의 응답(p<S>_flat_sb_limp_vs_bb) → vs_limp_full: check / raise."""
    import re
    m = re.match(r'p(\d+)_flat_sb_limp_vs_bb$', rec['id'])
    S = str(int(m.group(1)))
    n = _root(rec)
    acts = n['actions']
    assert n['actor'] == 'BB' and acts[0] == 'Check' and acts[1].startswith('Raise '), acts
    get = lambda c, f: sum(v for a, v in n['hands'][c]['freq'].items() if f(a))
    ent = {'check': r3([get(c, lambda a: a == 'Check') for c in out['classes']]),
           'raise': r3([get(c, lambda a: a.startswith('Raise')) for c in out['classes']]),
           'raise_bb': float(acts[1].split()[1]),
           # 걸음마다 체크↔레이즈가 뒤집힌 클래스의 콤보 몫(평균값이 50/50 으로 찍힌다). 품질 표시.
           'unstable_share': round(float(n.get('unstable_combos') or 0.0) / max(1e-9, float(n['reach_combos'])), 3)}
    out['vs_limp_full'].setdefault(S, {})['SB>BB'] = ent
    _src(rec)


for path in sys.argv[1:]:
    rec = json.load(open(path))
    if rec.get('schema') == 'spot_quick_v1':
        if rec['id'].endswith('_dcfr_stop'):
            print('skip (superseded DCFR-stop record):', rec['id'])
            continue
        if '_limp_' in rec['id']:
            limp(rec)
        elif 'v1_' in rec['id']:
            threebet(rec)
        else:
            flat(rec)
        continue
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
print(dst, {k: {s: len(v) for s, v in out[k].items()} for k in ('first_in', 'vs_jam', 'vs_3bjam', 'vs_open', 'vs_3bet', 'vs_open_full', 'vs_3bet_full', 'vs_limp_full')})
