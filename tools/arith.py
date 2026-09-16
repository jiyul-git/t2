#!/usr/bin/env python3
"""⑩ A5·A6 — DEVIATE 분기의 클램프 발동과 가산 두 축의 S 비.

  python3 tools/arith.py --axes aggression,bluff,discipline,cbet_flop \
      --seeds 5200-5204 --jobs 4

설계는 CF_DESIGN_ARITH.md (사전등록 457a7c3, 범위 축소 e8b092f).
tools/cf_axis_l2.py 를 복사해 D 팔만 남기고 cbet_freq 반환값을 추가로
기록한 것이다. **plan.py 는 수정하지 않고 재구현하지도 않는다.**

  A5  네 축의 클램프 발동률. flop 조건 (설계 4-2)
      판정: 네 값이 전부 같으면 틀린 것으로 적는다. 유의성 기준 없음
  A6  두 축 모두 클램프 미발동인 교집합에서 S(aggression)/S(bluff)
      판정: 1.750 +- 1e-3. 벗어나면 미설명으로 남긴다

클램프 지점
  S8   cbet_freq 반환이 0.03 또는 0.95
  S10  decide_aggression 반환이 0.0 또는 0.9
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
    # 현재 핸드 표시 — 파일 I/O 는 하지 않는다. 진단용 호출 순번(call_seq)에만 쓴다.
    cur = {'hand': 0, 'table': None}
    seqs = collections.Counter()
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
    mark = {'o_logs': 0, 'o_draws': 0, 'arm_draws': None, 'p': None, 'roll': None,
            'attached': False}
    # 진단용 포획. **이름을 cap 으로 쓰면 run_one 의 인자 cap(핸드 상한)을
    # 가린다** — 처음에 그렇게 썼다가 TypeError 로 죽었다.
    # decide_aggression·decide_size 는 attach_intent 안에서
    # 각각 **한 번만** 불린다(plan.py:556·563 — 저장소 전체 호출부가 그 둘뿐).
    # 그래서 호출 하나에 값 하나가 대응하고 모호함이 없다.
    dg = {'p': None, 'size': None}
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
            out = fn(*a, **k)
            if name == 'decide_aggression':
                try: dg['p'] = float(out[0])
                except Exception: pass
            elif name == 'cbet_freq':
                # S8 클램프 판정을 위해 반환값을 그대로 받는다. 재구현이 아니다
                try: dg['cf'] = float(out)
                except Exception: pass
            elif name == 'decide_size':
                try: dg['size'] = float(out)
                except Exception: pass
            return out
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
        # attach_intent 진입 표시. plan.py:1521 의 게이트가 열렸다는 **직접 관측**이다.
        # O 팔 호출 직전에만 리셋하므로, 반사실 팔의 진입은 이 값을 덮지 않는다.
        mark['attached'] = True
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
        mark['attached'] = False          # O 팔에 대해서만 기록한다
        dg['p'] = dg['size'] = dg['cf'] = None
        shim_rng.start_record()
        out0 = _oup(st, hero, board, my_range, opp_range, profile, pot, stack_,
                    street, seed_, n_opp, behind, prev_board, oop, initiative, **kw)
        shim_rng.stop()
        base_logs = shim_rng.logs
        p0 = (out0 or {}).get('plan')
        i0 = ((out0 or {}).get('intents') or {}).get(street) or {}
        a0 = i0.get('act')
        p_0, sz_0, src_0 = dg['p'], dg['size'], i0.get('src')
        inv0 = {k: (out0 or {}).get(k) for k in
                ('eq', 'eq_current', 'outs_true', 'made', 'nut_adv', 'range_adv')}
        _attached = bool(mark.get('attached'))
        # **보조 진단값.** session.py:454 의 idx 를 재구현한 것이 아니다 —
        # harness 가 본 update_plan 호출의 독립적인 순번일 뿐이다.
        # 최초 decision unit 의 기준은 attached_O 하나다.
        _skey = (cur['hand'], cur['table'], profile.get('id'), street)
        _seq = seqs[_skey]; seqs[_skey] += 1

        for ax in axes:
            rec = {'seed': seed, 'hand': cur['hand'], 'table': cur['table'],
                   'pid': profile.get('id'), 'street': street, 'axis': ax,
                   'attached_O': _attached, 'call_seq': _seq,
                   'plan_O': p0, 'act_O': a0,
                   'p_O': p_0, 'size_O': sz_0, 'src_O': src_0}
            for arm in ('D',):          # ⑩ 은 D 팔만 본다 (설계 4-2)
                for tag, val in (('lo', LO), ('hi', HI)):
                    state.update({'axis': ax, 'val': val, 'funcs': ARMS[arm]})
                    shim_rng.logs = base_logs
                    shim_rng.start_replay()
                    mark['arm_draws'] = None; mark['arm_logs'] = None
                    dg['p'] = dg['size'] = dg['cf'] = None
                    try:
                        o = _oup(dict(st) if st else st, hero, board, my_range,
                                 opp_range, profile, pot, stack_, street, seed_,
                                 n_opp, behind, prev_board, oop, initiative, **kw)
                        pl = (o or {}).get('plan')
                        it = ((o or {}).get('intents') or {}).get(street) or {}
                        ac = it.get('act'); _src = it.get('src')
                        inv = {k: (o or {}).get(k) for k in inv0}
                        bad = [k for k in inv0
                               if inv0[k] is not None and inv[k] is not None
                               and abs(float(inv0[k]) - float(inv[k])) > 1e-9]
                    except Exception:
                        pl = ac = _src = None; bad = ['EXC']
                    shim_rng.stop()
                    rec['plan_%s_%s' % (arm, tag)] = pl
                    rec['act_%s_%s' % (arm, tag)] = ac
                    rec['p_%s_%s' % (arm, tag)] = dg['p']
                    rec['cf_%s_%s' % (arm, tag)] = dg['cf']
                    rec['size_%s_%s' % (arm, tag)] = dg['size']
                    rec['src_%s_%s' % (arm, tag)] = _src
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
                    cur['hand'] = f.hand_no; cur['table'] = tid
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
    ap.add_argument('--rows', default=None,
                    help='rec 전체를 JSONL.gz 로 저장할 경로. 집계에는 영향 없다')
    a = ap.parse_args()

    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi)+1)) if hi else [int(lo)]
    axes = [x.strip() for x in a.axes.split(',') if x.strip()]

    with mp.Pool(a.jobs) as pool:
        out = pool.map(run_one, [(a.entries, a.hpl, a.stack, s, a.cap, axes)
                                 for s in seeds])
    rows = [r for o in out for r in o[0]]
    errs = sum(o[1] for o in out)

    # 원자료 저장. **pool.map 이 끝난 뒤에만** 쓴다 — 측정 경로에 I/O 를 끼우지 않는다.
    if a.rows:
        import gzip, json
        _op = gzip.open if a.rows.endswith('.gz') else open
        with _op(a.rows, 'wt', encoding='utf-8') as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n')
        print('  원자료 %d행 → %s' % (len(rows), a.rows))
        _bad = sum(1 for r in rows
                   if bool(r.get('attached_O')) != (r.get('call_seq') == 0))
        print('  attached_O 와 call_seq==0 불일치 %d행' % _bad)

    score(rows, len(seeds), errs, a)


def score(rows, nseed, errs, a):
    import re, collections
    PCT = re.compile(r'\(\d+%\)')
    BR = 'DEVIATE:포기 계획이나 지속벳(N%)'
    AX = ['aggression', 'bluff', 'discipline', 'cbet_flop']

    def aligned(r):
        return all((not r['shift_D_%s' % t]) and r['inv_D_%s' % t]
                   for t in ('lo', 'hi'))

    def eqv(x, v):
        return x is not None and abs(x - v) < 1e-12

    def clamped(r):
        """S8 또는 S10 이 lo·hi 어느 끝점에서든 걸렸는가."""
        for t in ('lo', 'hi'):
            cf = r.get('cf_D_%s' % t); p = r.get('p_D_%s' % t)
            if eqv(cf, 0.03) or eqv(cf, 0.95): return True
            if eqv(p, 0.0) or eqv(p, 0.9):     return True
        return False

    print('# ⑩ A5 · A6   설계 457a7c3 / 축소 e8b092f')
    print('  entries=%d hpl=%d stack=%d  시드 %d개  엔진 오류 %d건'
          % (a.entries, a.hpl, a.stack, nseed, errs))
    print('  D 팔만. 분기 DEVIATE 고정.')
    print('  A1~A4 와 4-1 은 해석적 확정이라 여기서 재지 않는다 (설계 8-1·8-2)')
    print()

    keep = collections.defaultdict(dict)
    for r in rows:
        if not r.get('attached_O'): continue
        if PCT.sub('(N%)', str(r.get('src_O'))) != BR: continue
        if not aligned(r): continue
        k = (r['seed'], r['hand'], r['table'], r['pid'], r['street'])
        keep[k][r['axis']] = r

    print('## A5 — 클램프 발동률 (flop 조건, 설계 4-2)')
    print('  예측: 네 축에서 서로 다르다. 네 값이 전부 같으면 틀린 것으로 적는다')
    print('  크기 순서는 예측하지 않는다. 유의성 기준을 만들지 않는다')
    print()
    rate = {}
    for ax in AX:
        n = c = 0
        for k, d in keep.items():
            if k[4] != 'flop': continue
            r = d.get(ax)
            if r is None: continue
            n += 1; c += 1 if clamped(r) else 0
        rate[ax] = (c, n, (c / n) if n else None)
        print('    %-12s %5d / %5d = %s'
              % (ax, c, n, ('%.4f' % rate[ax][2]) if n else 'n/a'))
    vals = [v[2] for v in rate.values() if v[2] is not None]
    same = (len(vals) == len(AX)
            and len(set('%.12f' % v for v in vals)) == 1)
    print()
    print('    네 값이 전부 같은가: %s   →  A5 %s'
          % ('예' if same else '아니오', '틀림' if same else '충족'))
    print()
    print('  [참고, 채점 아님] 전 스트리트')
    for ax in AX:
        n = c = 0
        for k, d in keep.items():
            r = d.get(ax)
            if r is None: continue
            n += 1; c += 1 if clamped(r) else 0
        print('    %-12s %5d / %5d = %s'
              % (ax, c, n, ('%.4f' % (c / n)) if n else 'n/a'))
    print()

    print('## A6 — 클램프 미발동 교집합에서 S(aggression) / S(bluff)')
    print('  예측: 1.750 +- 1e-3.  벗어나면 미설명으로 남긴다')
    print()

    def S(recs):
        v = [abs(r['p_D_hi'] - r['p_D_lo']) for r in recs
             if r.get('p_D_lo') is not None and r.get('p_D_hi') is not None
             and r['p_D_lo'] != r['p_D_hi']]
        return (sum(v) / len(v), len(v)) if v else (None, 0)

    both = {'aggression': [], 'bluff': []}
    only = {'aggression': [], 'bluff': []}
    for k, d in keep.items():
        ra, rb = d.get('aggression'), d.get('bluff')
        if ra is None or rb is None: continue
        if not clamped(ra) and not clamped(rb):
            both['aggression'].append(ra); both['bluff'].append(rb)
        if not clamped(ra): only['aggression'].append(ra)
        if not clamped(rb): only['bluff'].append(rb)

    sa, na = S(both['aggression']); sb, nb = S(both['bluff'])
    print('    교집합 (채점 대상)')
    print('      aggression  S = %s   n = %d'
          % ('%.9f' % sa if sa is not None else 'n/a', na))
    print('      bluff       S = %s   n = %d'
          % ('%.9f' % sb if sb is not None else 'n/a', nb))
    if sa and sb:
        ratio = sa / sb
        ok = abs(ratio - 1.750) <= 1e-3
        print('      비 = %.9f      →  A6 %s' % (ratio, '충족' if ok else '불충족'))
        if not ok:
            print('      **미설명으로 남긴다. 다른 원인을 사후에 붙이지 않는다**')
    print()
    sa2, na2 = S(only['aggression']); sb2, nb2 = S(only['bluff'])
    print('    [참고, 채점 아님] 축별 부분집합')
    print('      aggression  S = %s   n = %d'
          % ('%.9f' % sa2 if sa2 is not None else 'n/a', na2))
    print('      bluff       S = %s   n = %d'
          % ('%.9f' % sb2 if sb2 is not None else 'n/a', nb2))
    if sa2 and sb2:
        print('      비 = %.9f' % (sa2 / sb2))


if __name__ == '__main__':
    main()
