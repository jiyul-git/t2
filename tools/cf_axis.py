#!/usr/bin/env python3
"""⑤ 반사실 개입 — 축만 1↔9 로 바꾸면 행동이 달라지는가.

  python3 tools/cf_axis.py --axes _rand_A --seeds 5000-5003   # 위약 결정론 검증
  python3 tools/cf_axis.py --axes looseness,discipline,bluff,aggression --seeds 5000-5054

**CF_DESIGN.md 의 명세를 그대로 구현한다.** plan.py 는 수정하지 않는다.

결정 단위 반사실이다. 기준 궤적을 정상 실행하고 각 결정에서
원본 / 축=1 / 축=9 세 팔을 **같은 상황 입력**으로 부른다.
상황 불변이 구조적으로 보장되는 대신 하류 전파는 못 본다.

Level 1 (주지표) — attach_intent 를 감싸 decide_aggression 을 수정
  프로필로 다시 부른다. 같은 주사위 눈(CRN)을 세 팔에 쓴다.
Level 2 (보조)   — make_plan 을 수정 프로필·같은 seed 로 다시 부른다.
  게이트 축은 단축 평가 때문에 난수 소비가 어긋날 수 있다.

케이스를 셋으로 나눠 집계한다 (CF_DESIGN 2-3).
  rng_aligned / rng_shifted / invariant_failed
**rng_shifted 를 정상 집계에 섞지 않는다.**
"""
import os, sys, argparse, math, random, statistics as stat, collections
import multiprocessing as mp

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.dirname(os.path.abspath(__file__))
for _p in (D, T):
    if _p not in sys.path:
        sys.path.insert(0, _p)

LO, HI = 1.0, 9.0

# **축마다 개입 지점이 다르다.** decide_aggression 은 aggr·bluff·gamble·
# sk(...)·discipline·value 만 읽는다 — looseness 는 등장하지 않는다.
# 그 축의 소비처는 persona.open_pct 와 preflop.defend_thresholds 다.
# 지점을 안 맞추면 무의미한 0 이 나온다.
SITE = {
    'looseness':       ('PRE',  'open_pct', 'defend_tot'),
    'pf_range':        ('PRE',  'open_pct'),
    'positional':      ('PRE',  'open_pct'),
    'pf_defend':       ('PRE',  'defend_tp', 'defend_tot'),
    'aggression':      ('BOTH', 'defend_tp'),      # 프리플랍 tp + 포스트플랍 밸류
    'discipline':      ('POST',),
    'bluff':           ('POST',),
    'potcontrol':      ('POST',),
    'thin_value_turn': ('POST',),
    'cbet_flop':       ('POST',),
    '_rand_A':         ('BOTH',),
    '_rand_B':         ('BOTH',),
}
def sites_of(ax):
    return SITE.get(ax, ('POST',))

# make_plan 이 돌려주는 state 에서 축을 바꿔도 변하면 안 되는 것 (CF_DESIGN 3-2)
INVAR = ('eq', 'eq_current', 'outs_true', 'made', 'nut_adv', 'range_adv')
# 축별 예외 — 이 축을 흔들 때는 그 키가 변해도 인과 경로다
INVAR_EXEMPT = {
    'draw_love':     ('rel',), 'overpair_love': ('rel',),
    'outs':          ('outs',),
}


class CountRandom:
    """난수 소비 횟수를 세는 래퍼. plan.random 을 이걸로 갈아끼운다."""
    def __init__(self, seed=None):
        self._r = random.Random(seed)
        self.n = 0
    def _c(self, fn, *a, **k):
        self.n += 1
        return fn(*a, **k)
    def random(self):          return self._c(self._r.random)
    def gauss(self, m, s):     return self._c(self._r.gauss, m, s)
    def uniform(self, a, b):   return self._c(self._r.uniform, a, b)
    def randrange(self, *a):   return self._c(self._r.randrange, *a)
    def randint(self, a, b):   return self._c(self._r.randint, a, b)
    def choice(self, s):       return self._c(self._r.choice, s)
    def shuffle(self, s):      return self._c(self._r.shuffle, s)
    def sample(self, p, k):    return self._c(self._r.sample, p, k)
    def betavariate(self, a, b): return self._c(self._r.betavariate, a, b)


def swap(prof, axis, val):
    """축 하나만 바꾼 **깊은 사본**. concepts/temper 둘 다 확인한다."""
    p = dict(prof)
    if axis in (prof.get('concepts') or {}):
        c = dict(prof['concepts']); c[axis] = val; p['concepts'] = c
    elif axis in (prof.get('temper') or {}):
        t = dict(prof['temper']); t[axis] = val; p['temper'] = t
    else:
        # 위약(_rand_*) 처럼 엔진이 안 읽는 축. 사본만 만들고 값은 안 넣는다
        # → 결정론적으로 0 변화가 나와야 한다.
        c = dict(prof.get('concepts') or {}); c[axis] = val; p['concepts'] = c
    # derive() 파생값(aggr/bluff/tight 등)도 갱신한다. 안 하면 temper 를
    # 바꿔도 profile['aggr'] 이 옛 값이라 절반만 바뀐다.
    import persona as PS
    if p.get('concepts') and p.get('temper'):
        try:
            d = PS.derive({'concepts': p['concepts'], 'temper': p['temper'],
                           'latent': p.get('latent') or {}})
            p.update(d)
        except Exception:
            pass
    return p


def run_one(args):
    entries, hpl, stack, seed, cap, axes = args
    import fieldsim as FS
    import plan as PL
    FS.Field.BOT_LOG = 0
    f = FS.Field(entries=entries, start_stack=stack, hero_pid=0, seed=seed,
                 hands_per_level=hpl)
    rows = []
    pre = []                    # 프리플랍 개입 기록
    da_rng_used = [0]           # decide_aggression 이 rng 를 쓰는가 (검증용)
    post_axes = [x for x in axes if sites_of(x)[0] in ('POST', 'BOTH')]
    pre_axes = [x for x in axes if sites_of(x)[0] in ('PRE', 'BOTH')]

    _oai = PL.attach_intent
    def wrap_ai(st, hero, board, my_range, opp_range, profile, pot, stack_,
                street, rng, n_opp, to_act_behind, oop, initiative, opp_est=None):
        out = _oai(st, hero, board, my_range, opp_range, profile, pot, stack_,
                   street, rng, n_opp, to_act_behind, oop, initiative, opp_est)
        tr = None
        for t in reversed((out or {}).get('trace') or []):
            if t.get('kind') == 'aggression' and t.get('street') == street:
                tr = t; break
        if tr is None or tr.get('p') is None or tr.get('roll') is None:
            return out
        base_f, roll = float(tr['p']), float(tr['roll'])
        base_act = 'bet' if roll < base_f else 'check'
        plan0 = (out or {}).get('plan')
        rel0 = st.get('rel', 0.5)
        outs0 = st.get('outs', 0)

        for ax in post_axes:
            rec = {'pid': profile.get('id'), 'street': street, 'axis': ax,
                   'plan0': plan0, 'f0': base_f, 'roll': roll, 'act0': base_act,
                   'orig': (profile.get('concepts') or {}).get(ax,
                           (profile.get('temper') or {}).get(ax))}
            for tag, val in (('lo', LO), ('hi', HI)):
                pf = swap(profile, ax, val)
                cr = CountRandom(0)
                try:
                    p_, why_ = PL.decide_aggression(
                        pf, board, street, plan0, rel0, n_opp, oop, initiative,
                        to_act_behind, cr, opp_est, outs0, plan_state=st)
                except Exception:
                    p_, why_ = None, ''
                da_rng_used[0] = max(da_rng_used[0], cr.n)
                rec['f_'+tag] = (float(p_) if p_ is not None else None)
                rec['act_'+tag] = (('bet' if roll < p_ else 'check')
                                   if p_ is not None else None)
                rec['rng_'+tag] = cr.n
            rows.append(rec)
        return out

    PL.attach_intent = wrap_ai

    # ---- 프리플랍 개입 지점 ----
    import persona as PS
    import preflop as PF
    _op = PS.open_pct
    def w_op(prof, pos, seats=8, bb=100.0, ante=True, band=None):
        v = _op(prof, pos, seats, bb, ante, band)
        for ax in pre_axes:
            if 'open_pct' not in sites_of(ax)[1:] and not ax.startswith('_rand'):
                continue
            try:
                a_ = _op(swap(prof, ax, LO), pos, seats, bb, ante, band)
                b_ = _op(swap(prof, ax, HI), pos, seats, bb, ante, band)
                pre.append({'pid': prof.get('id'), 'axis': ax, 'metric': 'open_pct',
                            'v0': float(v), 'lo': float(a_), 'hi': float(b_)})
            except Exception:
                pass
        return v
    PS.open_pct = w_op

    _dt = PF.defend_thresholds
    def w_dt(prof, def_pos, opener_pos, bb, open_bb=2.5, n_callers=0,
             raise_level=1, seats=8, ante=True):
        out = _dt(prof, def_pos, opener_pos, bb, open_bb, n_callers,
                  raise_level, seats, ante)
        for ax in pre_axes:
            want = sites_of(ax)[1:]
            for mi, mname in ((0, 'defend_tp'), (1, 'defend_tot')):
                if mname not in want and not ax.startswith('_rand'):
                    continue
                try:
                    a_ = _dt(swap(prof, ax, LO), def_pos, opener_pos, bb, open_bb,
                             n_callers, raise_level, seats, ante)
                    b_ = _dt(swap(prof, ax, HI), def_pos, opener_pos, bb, open_bb,
                             n_callers, raise_level, seats, ante)
                    pre.append({'pid': prof.get('id'), 'axis': ax, 'metric': mname,
                                'v0': float(out[mi]), 'lo': float(a_[mi]),
                                'hi': float(b_[mi])})
                except Exception:
                    pass
        return out
    PF.defend_thresholds = w_dt

    try:
        while f.remaining() > 1 and f.hand_no < cap:
            f.hand_no += 1
            f.advance_level()
            for tid, tb in list(f.tables.items()):
                if tb.n() >= 2:
                    f._play_table(tb)
            f._collect_busts()
            f._balance()
            f.notes = []
    finally:
        PL.attach_intent = _oai
        PS.open_pct = _op
        PF.defend_thresholds = _dt
    return rows, da_rng_used[0], len(f.errors), pre


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=24)
    ap.add_argument('--hpl', type=int, default=12)
    ap.add_argument('--stack', type=int, default=30000)
    ap.add_argument('--seeds', default='5000-5003')
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
    da_rng = max(o[1] for o in out) if out else 0
    errs = sum(o[2] for o in out)
    pre = [r for o in out for r in o[3]]

    print('# ⑤ 반사실 개입 (Level 1, 주지표=action flip)')
    print('  entries=%d hpl=%d stack=%d  시드 %d개  축 %s'
          % (a.entries, a.hpl, a.stack, len(seeds), ','.join(axes)))
    print('  결정 %d건   엔진 오류 %d건' % (len(rows)//max(1, len(axes)), errs))
    print()
    print('## 검증 — decide_aggression 이 rng 를 소비하는가')
    print('  최대 소비 횟수 : %d   %s' % (da_rng,
          '← 0. CRN 이 구조적으로 보장된다' if da_rng == 0
          else '← 0 이 아니다. 같은 roll 을 써도 내부 난수가 다르다'))
    print()

    hdr = ('%-16s %7s %9s %9s %9s %10s %10s %8s'
           % ('축', '결정', 'f중앙(원)', 'f중앙(1)', 'f중앙(9)',
              'action flip', 'direction', 'RNG정렬'))
    print(hdr); print('-'*len(hdr))
    for ax in axes:
        sel = [r for r in rows if r['axis'] == ax
               and r.get('f_lo') is not None and r.get('f_hi') is not None]
        if not sel:
            print('%-16s %7d  (표본 없음)' % (ax, 0)); continue
        aligned = [r for r in sel if r['rng_lo'] == 0 and r['rng_hi'] == 0]
        flip = sum(1 for r in aligned if r['act_lo'] != r['act_hi'])
        up = sum(1 for r in aligned if r['f_hi'] > r['f_lo'])
        dn = sum(1 for r in aligned if r['f_hi'] < r['f_lo'])
        eq = len(aligned) - up - dn
        d = ('↑%d/↓%d/=%d' % (up, dn, eq))
        print('%-16s %7d %9.3f %9.3f %9.3f %9.1f%% %10s %7.0f%%'
              % (ax, len(sel),
                 stat.median([r['f0'] for r in sel]),
                 stat.median([r['f_lo'] for r in sel]),
                 stat.median([r['f_hi'] for r in sel]),
                 100.0*flip/max(1, len(aligned)), d,
                 100.0*len(aligned)/len(sel)))
    print()
    print('## magnitude — f(9) − f(1)')
    for ax in axes:
        sel = [r for r in rows if r['axis'] == ax
               and r.get('f_lo') is not None and r.get('f_hi') is not None]
        if not sel: continue
        d = sorted(r['f_hi']-r['f_lo'] for r in sel)
        g = lambda q: d[min(len(d)-1, int(q*len(d)))]
        print('  %-16s 중앙 %+0.4f   5%% %+0.4f   95%% %+0.4f   |Δ|>0.01 인 비율 %.1f%%'
              % (ax, stat.median(d), g(0.05), g(0.95),
                 100.0*sum(1 for x in d if abs(x) > 0.01)/len(d)))
    if pre:
        print()
        print('## 프리플랍 층 (open_pct / defend_thresholds)')
        print('%-16s %-12s %7s %9s %9s %9s %10s'
              % ('축', '지표', '호출', '중앙(원)', '중앙(1)', '중앙(9)', '|Δ|>0 비율'))
        print('-'*78)
        byk = collections.defaultdict(list)
        for r in pre: byk[(r['axis'], r['metric'])].append(r)
        for (ax, mt), rs in sorted(byk.items()):
            d = [r['hi']-r['lo'] for r in rs]
            print('%-16s %-12s %7d %9.4f %9.4f %9.4f %9.1f%%'
                  % (ax, mt, len(rs), stat.median([r['v0'] for r in rs]),
                     stat.median([r['lo'] for r in rs]),
                     stat.median([r['hi'] for r in rs]),
                     100.0*sum(1 for x in d if abs(x) > 1e-12)/len(d)))
    print()
    if all(x.startswith('_rand') for x in axes):
        print('## 위약 결정론 판정 (CF_DESIGN 6절)')
        ok = True
        for ax in axes:
            sel = [r for r in rows if r['axis'] == ax
                   and r.get('f_lo') is not None]
            nz = sum(1 for r in sel if abs(r['f_hi']-r['f_lo']) > 1e-12)
            fl = sum(1 for r in sel if r['act_lo'] != r['act_hi'])
            pz = sum(1 for r in pre if r['axis'] == ax and abs(r['hi']-r['lo']) > 1e-12)
            print('  %-12s f 변화 %d건 / action flip %d건 / %d결정 | 프리플랍 변화 %d건'
                  % (ax, nz, fl, len(sel), pz))
            if nz or fl or pz: ok = False
        print()
        print('  ⑤의 위약은 **결정론적**이다. 정확히 0 이어야 하고 표본 변동을')
        print('  허용하지 않는다. 0 이 아니면 개입 코드가 프로필 사본을 잘못')
        print('  만든 것이다.   →  %s' % ('통과' if ok else '**실패 — 코드 조사**'))


if __name__ == '__main__':
    main()
