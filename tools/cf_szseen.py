#!/usr/bin/env python3
"""`_sz_seen` 덮어쓰기(FIX_PLAN 2-A) 분해. **읽기 전용이다.**

  python3 tools/cf_szseen.py --n 400 --street flop
  python3 tools/cf_szseen.py --n 400 --street river --no-axes

세 변종을 같은 상황·같은 seed 로 비교한다.

  ① 예전(덮어쓰기)   need = 인지팟오즈  ← 통째로 대입 (6574360 의 코드)
  ② 제거             그 블록만 삭제
  ③ 현재(입력 교체)   인지 사이즈를 need_true 의 입력으로 (FIX_PLAN 2-A (나))

**변종을 어디서 가져오는가 — 방향이 뒤집혔다.**
2-A 적용 전에는 현재 소스에서 덮어쓰기를 지워 ②·③ 을 만들었다. 적용 후에는
그 블록이 아예 없으므로 반대로 간다: `git show <BASE>:plan.py` 에서
`calldown_need` 원문을 꺼내 ① 을 복원하고, 거기서 블록을 지워 ② 를 만든다.
문자열 수술이 아니라 **커밋에 박힌 원문**을 쓰므로 표류하지 않는다.
BASE 기본값은 2-A 직전인 `6574360` (1-A 적용, 지문 44da00bf…).

가져온 원문은 `PL.__dict__` 에서 exec 하므로 모듈 전역(PS·bot 등)을 그대로 쓴다.
plan.py 는 건드리지 않는다.

위약: 같은 코드를 두 번 돌려 0.0% 가 나오는지(결정성), 그리고 성향 반사실에서
`tilt_swing`·`tilt_stack`(plan.py 가 읽지 않는 축) 이 0.0% 인지.
**가장 강한 관문은 비발동군 변화 0.0%** — ③ 은 `_sz_seen == _sz_true` 일 때
① 의 `need_true` 와 비트까지 같아야 한다.
"""
import argparse, copy, inspect, os, random, subprocess, sys, textwrap
from collections import Counter, defaultdict

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)

import bot, plan as PL, persona as PS

RANKS = '23456789TJQKA'; SUITS = 'cdhs'
DECK = [r+s for r in RANKS for s in SUITS]
BOARD_N = {'flop': 3, 'turn': 4, 'river': 5}

AXES = ['sizing_tell', 'range_read', 'potodds', 'aggression',
        'looseness', 'discipline', 'reraise']
PLACEBO = ['tilt_swing', 'tilt_stack']

BASE_REV = '6574360'

OVERWRITE = """        if abs(_sz_seen - _sz_true) > 1e-9:
            _p0 = float(pot) - tocall
            need = (_sz_seen*_p0)/max(1.0, _p0 + 2*_sz_seen*_p0)
"""

TAGS = ['① 예전(덮어쓰기)', '② 제거', '③ 현재(입력 교체)']


def _func_src(text, name):
    """모듈 원문에서 함수 하나의 소스를 잘라낸다. 들여쓰기로 끝을 찾는다."""
    head = 'def %s(' % name
    i = text.index(head)
    lines = text[i:].splitlines(True)
    out = [lines[0]]
    for ln in lines[1:]:
        if ln.strip() and not ln[:1].isspace():
            break
        out.append(ln)
    return ''.join(out)


def from_base(name, drop_overwrite=False):
    """BASE_REV 의 calldown_need 를 복원한다. 커밋 원문을 쓴다."""
    txt = subprocess.run(['git', 'show', '%s:plan.py' % BASE_REV],
                         cwd=D, capture_output=True, text=True, check=True).stdout
    src = _func_src(txt, 'calldown_need')
    if OVERWRITE not in src:
        raise SystemExit('%s 의 calldown_need 에 덮어쓰기 블록이 없다 — BASE_REV 확인'
                         % BASE_REV)
    if drop_overwrite:
        src = src.replace(OVERWRITE, '', 1)
    src = src.replace('def calldown_need(', 'def %s(' % name, 1)
    ns = PL.__dict__
    exec(compile(textwrap.dedent(src), '<변종:%s>' % name, 'exec'), ns)
    return ns[name]


def build_all():
    """세 변종. ③ 은 현재 살아 있는 함수 그대로다."""
    cur = PL.calldown_need
    if OVERWRITE in inspect.getsource(cur):
        raise SystemExit('현재 plan.py 에 덮어쓰기가 남아 있다 — 2-A 가 적용됐는지 확인할 것')
    return {TAGS[0]: from_base('cn_old'),
            TAGS[1]: from_base('cn_del', drop_overwrite=True),
            TAGS[2]: cur}


def perturb(prof, axis, val):
    p = {'concepts': dict(prof['concepts']), 'temper': dict(prof['temper']),
         'latent': dict(prof.get('latent') or {}), 'id': prof.get('id')}
    if axis in p['temper']: p['temper'][axis] = float(val)
    elif axis in p['concepts']: p['concepts'][axis] = float(val)
    else: raise KeyError(axis)
    p.update(PS.derive(p))
    return p


def fake_read(rng):
    ftb = rng.uniform(0.30, 0.75)
    return {'confidence': rng.uniform(0.4, 0.9), 'n': rng.randint(15, 60),
            'ftb': ftb, 'fold': ftb, 'bluff': rng.uniform(2, 8),
            'aggr': rng.uniform(2, 8), 'ftb_flop': ftb, 'ftb_turn': ftb,
            'ftb_river': ftb, 'sizing_tell': rng.uniform(1, 9),
            'range_read': rng.uniform(1, 9), 'sz_mean': rng.uniform(0.4, 0.9),
            'type': None}


def situation(rng, street):
    d = DECK[:]; rng.shuffle(d)
    hero = d[:2]; board = d[2:2+BOARD_N[street]]
    dead = hero + board
    pot = rng.choice([600, 1200, 2400, 5000, 9000])
    frac = rng.choice([0.40, 0.55, 0.66, 0.75, 1.0, 1.1])
    tocall = int(pot*frac)
    return dict(hero=hero, board=board,
                my_range=bot.range_combos(rng.uniform(0.15, 0.40), dead),
                opp_range=bot.range_combos(rng.uniform(0.15, 0.45), dead),
                pot=pot+tocall, tocall=tocall,
                stack=int(pot*rng.choice([1.0, 2.0, 3.5, 6.0, 12.0])),
                street=street, to_act_behind=rng.choice([0, 0, 1]),
                oop=rng.random() < 0.5, initiative=rng.random() < 0.5)


def seen_size(prof, sit, est):
    """(sz_true, sz_seen). 계산은 plan.py 의 그 세 줄 그대로."""
    sz_true = sit['tocall']/max(1.0, float(sit['pot']) - sit['tocall'])
    rdz = PS.read_opponent(prof, est) if est else None
    sz_seen = PS.size_read(prof, PS.opp_size_norm(rdz, sz_true, sit['street']))
    return sz_true, sz_seen


def fired(prof, sit, est):
    """이 상황에서 덮어쓰기가 걸리는가. 문턱은 plan.py 그대로 1e-9 다."""
    if not prof.get('concepts') or not sit['board']:
        return False
    sz_true, sz_seen = seen_size(prof, sit, est)
    return abs(sz_seen - sz_true) > 1e-9


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=400)
    ap.add_argument('--street', default='flop', choices=list(BOARD_N))
    ap.add_argument('--bf', type=float, default=1.0)
    ap.add_argument('--no-axes', action='store_true', help='1부만 돌린다')
    ap.add_argument('--seed', type=int, default=20260914)
    a = ap.parse_args()

    fns = build_all()
    cur_fn = PL.calldown_need
    tags = list(TAGS)

    # ---- 상황을 먼저 다 만든다. 변종마다 난수 스트림이 어긋나면 안 된다 ----
    rng = random.Random(a.seed)
    sits = []
    for i in range(a.n):
        sit = situation(rng, a.street)
        prof = PS.make_player(rng, 0.78, i)
        est = fake_read(rng)
        rv = rng.uniform(0.10, 0.70)
        s = rng.randrange(1 << 30)
        sits.append((sit, prof, est, rv, s))

    def run(fn, sit, prof, ps, s, est, rv):
        PL.calldown_need = fn
        try:
            (act, _), _eq, need = PL.act_with_plan(
                sit['hero'], sit['board'], prof, copy.deepcopy(ps),
                sit['pot'], sit['tocall'], sit['stack'], sit['street'],
                initiative=sit['initiative'],
                opp_range=sit['opp_range'], seed=s, n_opp=1, bf=a.bf,
                to_act_behind=sit['to_act_behind'], opp_est=est, read=rv)
        finally:
            PL.calldown_need = cur_fn
        return act, need

    plans = []
    acts = {t: Counter() for t in tags}
    # 발동군/비발동군 분리
    grp_acts = {t: {True: Counter(), False: Counter()} for t in tags}
    grp_n = Counter()
    trans = {t: {True: Counter(), False: Counter()} for t in tags[1:]}
    det = 0; done = 0
    needs = {t: [] for t in tags}
    devs = []

    for (sit, prof, est, rv, s) in sits:
        try:
            ps = PL.make_plan(sit['hero'], sit['board'], sit['my_range'],
                              sit['opp_range'], prof, sit['pot'], sit['stack'],
                              sit['street'], seed=s, n_opp=1,
                              to_act_behind=sit['to_act_behind'],
                              oop_vs_aggr=sit['oop'], initiative=sit['initiative'],
                              opp_est=est)
        except Exception:
            plans.append(None); continue
        plans.append(ps)
        f = fired(prof, sit, est)
        if f:
            _t, _s = seen_size(prof, sit, est)
            devs.append(abs(_s/_t - 1.0) if _t else 0.0)
        try:
            res = {}
            for t in tags:
                res[t] = run(fns[t], sit, prof, ps, s, est, rv)
            det_a, _ = run(fns[tags[0]], sit, prof, ps, s, est, rv)
        except Exception:
            continue
        done += 1; grp_n[f] += 1
        if det_a != res[tags[0]][0]: det += 1
        base = res[tags[0]][0]
        for t in tags:
            acts[t][res[t][0]] += 1
            grp_acts[t][f][res[t][0]] += 1
            if res[t][1] is not None: needs[t].append(res[t][1])
            if t != tags[0] and res[t][0] != base:
                trans[t][f]['%s → %s' % (base, res[t][0])] += 1

    import statistics as ST
    n = max(1, done)
    print('# `_sz_seen` 덮어쓰기 분해 — %s, 상황 %d개, bf=%.1f'
          % (a.street, done, a.bf))
    print('# ①② 는 %s 원문에서 복원. ③ 은 현재 plan.py\n' % BASE_REV)
    print('결정성 확인(같은 코드 두 번): 불일치 %d건  %s'
          % (det, '← 0 이어야 한다' if det == 0 else '← 문제!'))
    print('덮어쓰기 발동 %d / %d = %.1f%%'
          % (grp_n[True], done, 100*grp_n[True]/n))
    print()
    if devs:
        devs.sort()
        print('## 0. 인지한 사이즈가 실제와 얼마나 다른가 (발동군만)')
        print('   |sz_seen/sz_true − 1|   중앙 %.2f%%   90분위 %.2f%%   최대 %.2f%%'
              % (100*devs[len(devs)//2], 100*devs[int(0.9*len(devs))], 100*devs[-1]))
        print('   1%% 미만 %.1f%%   3%% 미만 %.1f%%'
              % (100*sum(1 for d in devs if d < 0.01)/len(devs),
                 100*sum(1 for d in devs if d < 0.03)/len(devs)))
        print('   발동 문턱은 1e-9 다 — 0.2% 를 잘못 봐도 need 가 통째로 덮인다.')
        print()
    print('## 1. 전체 행동 분포')
    print('%-20s %8s %8s %8s %10s' % ('', '폴드', '콜', '레이즈', 'need중앙'))
    for t in tags:
        c = acts[t]; m = max(1, sum(c.values()))
        nd = ST.median(needs[t]) if needs[t] else float('nan')
        print('%-20s %7.1f%% %7.1f%% %7.1f%% %10.3f'
              % (t, 100*c['fold']/m, 100*c['call']/m, 100*c['raise']/m, nd))
    print()
    print('## 2. 발동군 / 비발동군 분리')
    for f in (True, False):
        g = grp_n[f]
        if not g: continue
        print('\n### %s (%d건)' % ('덮어쓰기 발동' if f else '비발동', g))
        print('%-20s %8s %8s %8s' % ('', '폴드', '콜', '레이즈'))
        for t in tags:
            c = grp_acts[t][f]
            print('%-20s %7.1f%% %7.1f%% %7.1f%%'
                  % (t, 100*c['fold']/g, 100*c['call']/g, 100*c['raise']/g))
        for t in tags[1:]:
            tt = trans[t][f]
            tot = sum(tt.values())
            print('   %s 대비 ① : 바뀐 건 %d / %d = %.1f%%  %s'
                  % (t, tot, g, 100*tot/g,
                     '  '.join('%s ×%d' % (k, v) for k, v in tt.most_common())))
    if a.no_axes:
        return

    print()
    print('## 3. 성향 반사실 — 축을 1 ↔ 9 로 (변종마다)')
    axes = AXES + PLACEBO
    flips = {t: Counter() for t in tags}
    for (idx, (sit, prof, est, rv, s)) in enumerate(sits):
        ps = plans[idx]
        if ps is None: continue
        for ax in axes:
            try:
                ppair = [perturb(prof, ax, v) for v in (1, 9)]
            except KeyError:
                continue
            for t in tags:
                try:
                    a1, _ = run(fns[t], sit, ppair[0], ps, s, est, rv)
                    a9, _ = run(fns[t], sit, ppair[1], ps, s, est, rv)
                except Exception:
                    continue
                if a1 != a9: flips[t][ax] += 1
    print('%-16s %14s %14s %14s'
          % ('축', tags[0], tags[1], tags[2]))
    for ax in axes:
        mark = '  (위약)' if ax in PLACEBO else ''
        print('%-16s %13.1f%% %13.1f%% %13.1f%%%s'
              % (ax, 100*flips[tags[0]][ax]/n, 100*flips[tags[1]][ax]/n,
                 100*flips[tags[2]][ax]/n, mark))


if __name__ == '__main__':
    main()
