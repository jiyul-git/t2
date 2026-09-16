#!/usr/bin/env python3
"""M 팔의 plan=&act≠ 가 어디서 오는지 — 반환 state 의 필드 차이를 본다.

  python3 tools/diag_mleak.py --axes discipline,looseness --seeds 5000-5001

읽기 전용 진단. plan.py 는 수정하지 않는다.

M 팔은 L2_FUNCS 에서만 프로필을 갈아끼운다. AST 전수 확인 결과 L2 함수가
L1 함수 안에서 호출되는 자리는 없다. 그러면 plan 라벨이 같은데 행동이
달라지는 경로는 **반환 state 의 plan 아닌 필드**밖에 남지 않는다.
그 필드가 무엇인지 건별로 찍는다.
"""
import os, sys, argparse, collections
import multiprocessing as mp

D_ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T_ = os.path.dirname(os.path.abspath(__file__))
for _p in (D_, T_):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from cf_axis import swap, LO, HI
from cf_axis_l2 import RandomShim, L2_FUNCS, L1_FUNCS

# cf_axis_l2.run_one 안의 지역 변수라 import 되지 않는다. 같은 표를 쓴다.
POS = {'make_plan': 4, 'refresh': 5, 'river_fix': 2, '_allowed': 0,
       'line_bluff_prior': 0, 'checkraise_decision': 0, 'trap_judgment': 0,
       'perceived_rel': 0, 'stackoff_plan': 0,
       'decide_aggression': 0, 'decide_response': 0, 'cbet_freq': 0,
       'calldown_need': 0, 'decide_size': 0, 'overbet_frac': 0,
       'barrel_size': 1, 'bluff_mode': 0, 'opp_bet_prob': 0}


def run_one(args):
    entries, hpl, stack, seed, cap, axes = args
    import fieldsim as FS
    import plan as PL
    import runner as RU
    FS.Field.BOT_LOG = 0
    f = FS.Field(entries=entries, start_stack=stack, hero_pid=0, seed=seed,
                 hands_per_level=hpl)
    hits = []                      # plan=,act≠ 건들
    keydiff = collections.Counter()
    state = {'axis': None, 'val': None, 'funcs': ()}
    orig = {}

    def make_shim(mod, name, pos):
        fn = getattr(mod, name, None)
        if fn is None: return
        orig[(id(mod), name)] = (mod, name, fn)
        def shim(*a, **k):
            if state['axis'] and name in state['funcs']:
                a = list(a)
                if len(a) > pos and isinstance(a[pos], dict):
                    a[pos] = swap(a[pos], state['axis'], state['val'])
                elif 'profile' in k and isinstance(k['profile'], dict):
                    k['profile'] = swap(k['profile'], state['axis'], state['val'])
                elif 'prof' in k and isinstance(k['prof'], dict):
                    k['prof'] = swap(k['prof'], state['axis'], state['val'])
                a = tuple(a)
            return fn(*a, **k)
        setattr(mod, name, shim)

    for nm, ps in POS.items():
        make_shim(PL, nm, ps)

    mark = {'o_logs': 0, 'o_draws': 0, 'arm_draws': None, 'arm_logs': None}
    _oai0 = PL.attach_intent
    def mark_ai(*a, **k):
        if shim_rng.mode == 'record':
            mark['o_logs'] = len(shim_rng.logs)
            mark['o_draws'] = sum(len(l) for l in shim_rng.logs)
        elif shim_rng.mode == 'replay':
            mark['arm_draws'] = shim_rng.consumed()
            mark['arm_logs'] = shim_rng.idx
        return _oai0(*a, **k)
    PL.attach_intent = mark_ai

    shim_rng = RandomShim(PL.random)
    PL.random = shim_rng
    RU.random = shim_rng

    def flat(d, street):
        """비교용 평탄화. intents 는 해당 스트리트만 본다."""
        out = {}
        for k, v in (d or {}).items():
            if k == 'intents':
                for kk, vv in ((v or {}).get(street) or {}).items():
                    out['intents.%s' % kk] = vv
                continue
            try:
                hash(v); out[k] = v
            except TypeError:
                out[k] = repr(v)
        return out

    _oup = PL.update_plan
    def wrap_up(st, hero, board, my_range, opp_range, profile, pot, stack_,
                street, seed_, n_opp, behind, prev_board, oop, initiative, **kw):
        state.update({'axis': None, 'val': None, 'funcs': ()})
        mark.update({'o_draws': 0, 'o_logs': 0, 'arm_draws': None, 'arm_logs': None})
        shim_rng.start_record()
        out0 = _oup(st, hero, board, my_range, opp_range, profile, pot, stack_,
                    street, seed_, n_opp, behind, prev_board, oop, initiative, **kw)
        shim_rng.stop()
        base_logs = shim_rng.logs
        p0 = (out0 or {}).get('plan')
        i0 = ((out0 or {}).get('intents') or {}).get(street) or {}
        a0 = i0.get('act')
        f0 = flat(out0, street)

        for ax in axes:
            for tag, val in (('lo', LO), ('hi', HI)):
                state.update({'axis': ax, 'val': val, 'funcs': L2_FUNCS})
                shim_rng.logs = base_logs
                shim_rng.start_replay()
                mark['arm_draws'] = None; mark['arm_logs'] = None
                try:
                    o = _oup(dict(st) if st else st, hero, board, my_range,
                             opp_range, profile, pot, stack_, street, seed_,
                             n_opp, behind, prev_board, oop, initiative, **kw)
                    pl = (o or {}).get('plan')
                    it = ((o or {}).get('intents') or {}).get(street) or {}
                    ac = it.get('act')
                except Exception:
                    shim_rng.stop(); continue
                shim_rng.stop()
                if mark['arm_draws'] is None:
                    shifted = shim_rng.misaligned()
                else:
                    shifted = (mark['arm_draws'] != mark['o_draws']
                               or mark['arm_logs'] != mark['o_logs'])
                if shifted: continue
                if pl == p0 and ac != a0:
                    f1 = flat(o, street)
                    ks = sorted(set(f0) | set(f1))
                    diff = [k for k in ks if f0.get(k) != f1.get(k)]
                    for k in diff: keydiff[k] += 1
                    hits.append({'axis': ax, 'tag': tag, 'street': street,
                                 'plan': p0, 'act_O': a0, 'act_M': ac,
                                 'diff': {k: (f0.get(k), f1.get(k))
                                          for k in diff}})
        state.update({'axis': None, 'val': None, 'funcs': ()})
        return out0
    PL.update_plan = wrap_up

    try:
        while f.remaining() > 1 and f.hand_no < cap:
            f.hand_no += 1
            f.advance_level()
            for tid, tb in list(f.tables.items()):
                if tb.n() >= 2:
                    f._play_table(tb)
            f._collect_busts(); f._balance(); f.notes = []
    finally:
        PL.update_plan = _oup
        PL.attach_intent = _oai0
        for (mod, name, fn) in orig.values():
            setattr(mod, name, fn)
        PL.random = shim_rng._base
        RU.random = shim_rng._base
    return hits, keydiff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=24)
    ap.add_argument('--hpl', type=int, default=12)
    ap.add_argument('--stack', type=int, default=30000)
    ap.add_argument('--seeds', default='5000-5001')
    ap.add_argument('--cap', type=int, default=3000)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--axes', default='discipline,looseness')
    ap.add_argument('--show', type=int, default=12)
    a = ap.parse_args()
    lo, _, hi = a.seeds.partition('-')
    seeds = list(range(int(lo), int(hi) + 1)) if hi else [int(lo)]
    axes = [x for x in a.axes.split(',') if x]

    with mp.Pool(a.jobs) as pool:
        out = pool.map(run_one, [(a.entries, a.hpl, a.stack, s, a.cap, axes)
                                 for s in seeds])
    hits = [h for o in out for h in o[0]]
    kd = collections.Counter()
    for o in out: kd.update(o[1])

    print('# M 팔 plan=&act≠ 진단   시드 %d개  축 %s' % (len(seeds), ','.join(axes)))
    print('  해당 건수 %d' % len(hits))
    print()
    if not hits:
        print('  (해당 없음)'); return
    print('## 반환 state 에서 달라진 필드 (건수)')
    for k, n in kd.most_common():
        print('  %-28s %5d' % (k, n))
    print()
    print('## 축별 / 스트리트별')
    c2 = collections.Counter((h['axis'], h['street']) for h in hits)
    for (ax, stt), n in sorted(c2.items()):
        print('  %-14s %-6s %4d' % (ax, stt, n))
    print()
    print('## 개별 사례 (최대 %d건)' % a.show)
    for h in hits[:a.show]:
        print('  %s/%s %s  plan=%s  act %s -> %s' %
              (h['axis'], h['tag'], h['street'], h['plan'], h['act_O'], h['act_M']))
        for k, (v0, v1) in sorted(h['diff'].items()):
            print('      %-26s %r -> %r' % (k, v0, v1))


if __name__ == '__main__':
    main()
