#!/usr/bin/env python3
"""⑤ Level 2 반사실 — 축이 계획을 바꿔서 행동을 바꾸는가.

  python3 tools/cf_axis_l2.py --axes _rand_A --seeds 5000-5001   # 위약 결정론
  python3 tools/cf_axis_l2.py --axes potcontrol --seeds 5000-5054

**CF_DESIGN_LEVEL2.md 명세 그대로.** plan.py 는 수정하지 않는다.

네 팔:
  O  원본
  D  축을 **실행층** 함수에서만 바꾼다 (= Level 1)
  M  축을 **계획층** 함수에서만 바꾼다, 실행층은 원래 값
  T  모든 지점

판정은 해석 규칙이지 검정식이 아니다. T=D+M 가산성을 가정하지 않는다 —
계획이 바뀌면 이후 실행 경로와 난수 소비량이 달라진다.

핵심 출력 3칸:
  plan= & action≠   직접 효과
  plan≠ & action=   전달 실패 (실행층이 흡수)
  plan≠ & action≠   둘이 섞여 있다. **인과 분해하지 않는다**
"""
import os, sys, argparse, random, statistics as stat, collections
import multiprocessing as mp

D_ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T_ = os.path.dirname(os.path.abspath(__file__))
for _p in (D_, T_):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from cf_axis import swap, RecordRandom, ReplayRandom, LO, HI

# CF_DESIGN_LEVEL2 2절. plan.py 를 함수 단위로 전수 확인해 만든 표다.
L2_FUNCS = ('make_plan', 'refresh', 'river_fix', '_allowed',
            'line_bluff_prior', 'checkraise_decision', 'trap_judgment',
            'perceived_rel', 'stackoff_plan')
L1_FUNCS = ('decide_aggression', 'decide_response', 'cbet_freq',
            'calldown_need', 'decide_size', 'overbet_frac', 'barrel_size',
            'bluff_mode', 'opp_bet_prob')

# 팔 → 어느 집합에서 축을 바꾸는가
ARMS = {'O': (), 'D': L1_FUNCS, 'M': L2_FUNCS, 'T': L1_FUNCS + L2_FUNCS}


class RandomShim:
    """plan/runner 의 random 모듈을 대신한다.

    update_plan(plan.py:1461)과 make_plan(plan.py:265)이 각자
    random.Random(seed) 를 만든다. 밖에서 래퍼를 못 끼우므로 모듈을
    통째로 갈아끼워 생성 시점을 가로챈다.

    O 팔에서는 각 생성마다 RecordRandom 을 주고 난수열을 기록한다.
    다른 팔에서는 생성 **순서대로** 같은 기록을 ReplayRandom 으로 먹인다.
    """
    def __init__(self, base):
        self._base = base
        self.mode = 'pass'       # 'record' | 'replay' | 'pass'
        self.logs = []
        self.idx = 0
        self.shifted = False
        self._made = []
    def start_record(self):
        self.mode = 'record'; self.logs = []; self.idx = 0; self.shifted = False
    def start_replay(self):
        self.mode = 'replay'; self.idx = 0; self.shifted = False
        self._made = []          # 이번 팔에서 만든 ReplayRandom 들
    def consumed(self):
        """지금까지 뽑은 총 난수 개수 (재생 팔 기준)."""
        return sum(rp.n for rp, _ in getattr(self, '_made', []))
    def recorded_upto(self, k):
        """기록 팔에서 처음 k 개 로그의 길이 합."""
        return sum(len(l) for l in self.logs[:k])
    def misaligned(self):
        """난수 소비가 원본과 어긋났는가.

        **객체 생성 개수가 아니라 객체 **안의** 소비 횟수를 봐야 한다.**
        게이트 단축 평가(plan.py:447·456·468)는 한 Random 객체 안에서
        뽑는 횟수를 바꾼다. 처음에 `idx != len(logs)` 로 검출하려다
        영원히 0 이 나왔다 — 그건 Random() 이 몇 개 만들어졌는지를 센다.
        """
        if self.idx != len(self.logs):
            return True
        for rp, log in getattr(self, '_made', []):
            if rp.overrun or rp.n != len(log):
                return True
        return False
    def stop(self):
        self.mode = 'pass'
    def Random(self, seed=None):
        if self.mode == 'record':
            r = RecordRandom(self._base.Random(seed))
            self.logs.append(r.log)
            return r
        if self.mode == 'replay':
            log = self.logs[self.idx] if self.idx < len(self.logs) else []
            self.idx += 1
            rp = ReplayRandom(log, spare_seed=(seed or 0))
            self._made.append((rp, log))
            return rp
        return self._base.Random(seed)
    def __getattr__(self, k):
        return getattr(self._base, k)


def run_one(args):
    entries, hpl, stack, seed, cap, axes = args
    import fieldsim as FS
    import plan as PL
    import runner as RU
    FS.Field.BOT_LOG = 0
    f = FS.Field(entries=entries, start_stack=stack, hero_pid=0, seed=seed,
                 hands_per_level=hpl)
    rows = []
    state = {'axis': None, 'val': None, 'funcs': ()}   # 현재 팔

    # ---- 함수별 프로필 치환 shim ----
    # 각 함수를 감싸 "현재 팔이 이 함수에서 축을 바꾸라고 했으면" 프로필을
    # 갈아끼운다. 그래야 M 팔에서 계획층만, D 팔에서 실행층만 바뀐다.
    # attach_intent 진입 시점의 난수 소비량을 표시한다.
    #
    # **정렬 검사를 계획 구축 구간으로 한정해야 한다.**
    # plan.py:562 `if _roll < p_aggr: decide_size(... rng ...)` 때문에
    # **행동이 flip 하면 반드시 난수 소비가 달라진다.** 그래서 처음
    # 구현처럼 update_plan 전체로 정렬을 재면 rng_shifted 와 "행동이
    # 바뀜" 이 구조적으로 교락돼, 제외 규칙이 재려던 케이스를 전부 지운다.
    # Level 1 은 attach_intent 를 재호출하지 않고 기록된 roll 과 반사실 p
    # 로 직접 행동을 계산해서 이 문제가 없었다.
    mark = {'o_logs': 0, 'o_draws': 0, 'arm_draws': None, 'p': None, 'roll': None}
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

    # profile 인자 위치 (plan.py 시그니처 기준)
    POS = {'make_plan': 4, 'refresh': 5, 'river_fix': 2, '_allowed': 0,
           'line_bluff_prior': 0, 'checkraise_decision': 0, 'trap_judgment': 0,
           'perceived_rel': 0, 'stackoff_plan': 0,
           'decide_aggression': 0, 'decide_response': 0, 'cbet_freq': 0,
           'calldown_need': 0, 'decide_size': 0, 'overbet_frac': 0,
           'barrel_size': 1, 'bluff_mode': 0, 'opp_bet_prob': 0}
    for nm, ps in POS.items():
        make_shim(PL, nm, ps)

    # attach_intent 진입 순간을 표시하는 래퍼
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

    _oup = PL.update_plan
    def wrap_up(st, hero, board, my_range, opp_range, profile, pot, stack_,
                street, seed_, n_opp, behind, prev_board, oop, initiative,
                **kw):
        # --- O 팔: 난수 기록 ---
        state.update({'axis': None, 'val': None, 'funcs': ()})
        mark['o_draws'] = 0; mark['o_logs'] = 0; mark['arm_draws'] = None
        shim_rng.start_record()
        out0 = _oup(st, hero, board, my_range, opp_range, profile, pot, stack_,
                    street, seed_, n_opp, behind, prev_board, oop, initiative, **kw)
        shim_rng.stop()
        base_logs = shim_rng.logs
        p0 = (out0 or {}).get('plan')
        i0 = ((out0 or {}).get('intents') or {}).get(street) or {}
        a0 = i0.get('act')
        inv0 = {k: (out0 or {}).get(k) for k in
                ('eq', 'eq_current', 'outs_true', 'made', 'nut_adv', 'range_adv')}

        for ax in axes:
            rec = {'pid': profile.get('id'), 'street': street, 'axis': ax,
                   'plan_O': p0, 'act_O': a0}
            for arm in ('D', 'M', 'T'):
                for tag, val in (('lo', LO), ('hi', HI)):
                    state.update({'axis': ax, 'val': val, 'funcs': ARMS[arm]})
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
                        inv = {k: (o or {}).get(k) for k in inv0}
                        bad = [k for k in inv0
                               if inv0[k] is not None and inv[k] is not None
                               and abs(float(inv0[k]) - float(inv[k])) > 1e-9]
                    except Exception:
                        pl = ac = None; bad = ['EXC']
                    shim_rng.stop()
                    rec['plan_%s_%s' % (arm, tag)] = pl
                    rec['act_%s_%s' % (arm, tag)] = ac
                    rec['inv_%s_%s' % (arm, tag)] = (len(bad) == 0)
                    # 계획 구축 구간만 비교한다 (attach_intent 진입 전까지)
                    if mark['arm_draws'] is None:
                        shifted = shim_rng.misaligned()
                    else:
                        shifted = (mark['arm_draws'] != mark['o_draws']
                                   or mark.get('arm_logs') != mark['o_logs'])
                    rec['shift_%s_%s' % (arm, tag)] = shifted
            rows.append(rec)
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
    return rows, len(f.errors)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=24)
    ap.add_argument('--hpl', type=int, default=12)
    ap.add_argument('--stack', type=int, default=30000)
    ap.add_argument('--seeds', default='5000-5001')
    ap.add_argument('--cap', type=int, default=3000)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--axes', default='_rand_A')
    a = ap.parse_args()

    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi)+1)) if hi else [int(lo)]
    axes = [x.strip() for x in a.axes.split(',') if x.strip()]

    with mp.Pool(a.jobs) as pool:
        out = pool.map(run_one, [(a.entries, a.hpl, a.stack, s, a.cap, axes)
                                 for s in seeds])
    rows = [r for o in out for r in o[0]]
    errs = sum(o[1] for o in out)

    print('# ⑤ Level 2 반사실 (네 팔: O / D=실행층 / M=계획층 / T=전체)')
    print('  entries=%d hpl=%d stack=%d  시드 %d개  축 %s'
          % (a.entries, a.hpl, a.stack, len(seeds), ','.join(axes)))
    print('  update_plan 호출 %d건   엔진 오류 %d건'
          % (len(rows)//max(1, len(axes)), errs))
    print()
    print('  T=D+M 가산성을 가정하지 않는다. 네 팔을 독립적으로 재고 경로를 비교한다.')
    print()

    hdr = ('%-16s %-4s %7s %8s %9s %10s %11s %11s %11s'
           % ('축', '팔', 'total', 'aligned', 'shifted', 'align%',
              'plan=,act≠', 'plan≠,act=', 'plan≠,act≠'))
    print(hdr); print('-'*len(hdr))
    for ax in axes:
        sel = [r for r in rows if r['axis'] == ax]
        if not sel:
            print('%-16s  (표본 없음)' % ax); continue
        for arm in ('D', 'M', 'T'):
            tot = al = sh = 0
            c_pa = c_pA = c_PA = 0
            invbad = 0
            for r in sel:
                for tag in ('lo', 'hi'):
                    pl = r.get('plan_%s_%s' % (arm, tag))
                    ac = r.get('act_%s_%s' % (arm, tag))
                    if pl is None and ac is None: continue
                    tot += 1
                    if r.get('shift_%s_%s' % (arm, tag)): sh += 1; continue
                    if not r.get('inv_%s_%s' % (arm, tag)): invbad += 1; continue
                    al += 1
                    pf_ = (pl != r['plan_O']); af = (ac != r['act_O'])
                    if not pf_ and af: c_pa += 1
                    elif pf_ and not af: c_pA += 1
                    elif pf_ and af: c_PA += 1
            pct = lambda n: (100.0*n/al) if al else 0.0
            print('%-16s %-4s %7d %8d %9d %9.0f%% %10.1f%% %10.1f%% %10.1f%%'
                  % (ax if arm == 'D' else '', arm, tot, al, sh,
                     100.0*al/max(1, tot), pct(c_pa), pct(c_pA), pct(c_PA)))
            if invbad:
                print('%-16s %-4s   ** 불변량 위반 %d건 — 해석 금지 **'
                      % ('', '', invbad))
    print()
    print('  plan=,act≠ : 계획은 같은데 행동이 바뀌었다  → 직접 효과')
    print('  plan≠,act= : 계획은 바뀌었는데 실행층이 흡수했다 → 전달 실패')
    print('  plan≠,act≠ : 둘이 섞여 있다. **인과 분해하지 않는다**')
    print('  shifted    : 난수 소비가 어긋난 쌍. 효과가 아니라 **측정 가능성 문제**다')
    print()

    if all(x.startswith('_rand') for x in axes):
        print('## 위약 결정론 판정 (CF_DESIGN_LEVEL2 6절)')
        ok = True
        for ax in axes:
            sel = [r for r in rows if r['axis'] == ax]
            fl = sh = iv = 0
            for r in sel:
                for arm in ('D', 'M', 'T'):
                    for tag in ('lo', 'hi'):
                        if r.get('plan_%s_%s' % (arm, tag)) != r['plan_O']: fl += 1
                        if r.get('act_%s_%s' % (arm, tag)) != r['act_O']: fl += 1
                        if r.get('shift_%s_%s' % (arm, tag)): sh += 1
                        if not r.get('inv_%s_%s' % (arm, tag)): iv += 1
            print('  %-12s flip %d / shifted %d / 불변량위반 %d  (%d 호출)'
                  % (ax, fl, sh, iv, len(sel)))
            if fl or sh or iv: ok = False
        print()
        print('  Level 2 위약은 **rng_shifted 0 까지** 요구한다 — 위약은 게이트를')
        print('  넘나들지 않으므로 난수 소비가 같아야 한다.')
        print('  →  %s' % ('통과' if ok else '**실패 — 코드 조사**'))


if __name__ == '__main__':
    main()
