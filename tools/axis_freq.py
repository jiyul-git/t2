#!/usr/bin/env python3
"""성향 축 검증 ② — **빈도 축**이 층별로 무엇을 바꾸는가. 읽기 전용이다.

  python3 tools/axis_freq.py --axis aggression --n 250
  python3 tools/axis_freq.py --list

지표·경로·고정축의 근거는 `AXIS_FREQ_PLAN.md` 에 있다. 이 도구는 그 표를
그대로 실행한다. 원칙 셋:

  1. **층별로 따로 잰다.** 한 축을 평균 내서 "정상"이라 하지 않는다.
     aggression 은 결정 지점이 13곳, 층이 다섯이다.
  2. **교락 축을 고정한다.** 고정하지 않으면 ①의 pf_range 처럼 단조성이 깨진다.
  3. **중간값도 같이 기록한다.** 최종 빈도만 보면
       "축이 안 움직임" 과 "축은 움직이는데 clamp 가 막음" 을 구분할 수 없다.
     bias 층은 날것(raw)과 `max(0, ·)` 후를 **둘 다** 낸다.

스케일 주의 — `make_plan` 안의 `sk()` 는 0~3 이다 (`plan.py:398` PS.sk/3.33).
그래서 `sk('potcontrol') >= 1` 은 실제로 **PS.sk >= 3.33** 이다. 게이트가
의심되는 축은 그 근처를 촘촘히 훑는다(GATE_LEVELS).

`multiway`·`fold_equity` 는 여기서 재지 않는다. 정의역 조건(n_opp>=2,
opp_est 존재)이 측정 설계의 일부라 별도 harness 가 필요하다 — 4단계.
"""
import argparse, copy, os, random, statistics as ST, sys
from collections import Counter, OrderedDict

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)

import bot, gto, persona as PS, plan as PL, preflop as pf

RANKS = '23456789TJQKA'; SUITS = 'cdhs'
DECK = [r+s for r in RANKS for s in SUITS]
LEVELS = [1, 3, 5, 7, 9]
# 게이트가 의심되는 축은 문턱 근처를 촘촘히. make_plan 의 sk() 가 0~3 이므로
# `sk >= 1` 은 PS.sk 3.33, `sk >= 0.4` 는 PS.sk 1.33 이다.
GATE_LEVELS = {'potcontrol': [2.8, 3.2, 3.3, 3.4, 3.6, 4.2],
               'bluff':      [2.8, 3.2, 3.3, 3.4, 3.6, 4.2],
               'semibluff':  [1.0, 1.2, 1.3, 1.4, 1.6, 2.0]}
PLACEBO = ['tilt_swing', 'tilt_stack']
POS = ['UTG', 'LJ', 'HJ', 'CO', 'BTN']


# ---------------------------------------------------------------- 프로필
def build(base, axis, v, hold):
    p = {'concepts': dict(base['concepts']), 'temper': dict(base['temper']),
         'latent': dict(base.get('latent') or {}), 'id': base.get('id')}
    for k, kv in list(hold.items()) + [(axis, v)]:
        if k in p['concepts']: p['concepts'][k] = float(kv)
        elif k in p['temper']: p['temper'][k] = float(kv)
        else: raise KeyError(k)
    p.update(PS.derive(p))
    return p


def fake_est(rng):
    ftb = rng.uniform(0.30, 0.75)
    return {'confidence': rng.uniform(0.4, 0.9), 'n': rng.randint(15, 60),
            'ftb': ftb, 'fold': ftb, 'bluff': rng.uniform(2, 8),
            'aggr': rng.uniform(2, 8), 'ftb_flop': ftb, 'ftb_turn': ftb,
            'ftb_river': ftb, 'sizing_tell': rng.uniform(1, 9),
            'range_read': rng.uniform(1, 9), 'sz_mean': rng.uniform(0.4, 0.9),
            'sz_sd': rng.uniform(.10, .35), 'sz_n': rng.randint(4, 20),
            'sz_big': rng.uniform(0, .4), 'type': None}


def post_sit(rng, street='flop'):
    nb = {'flop': 3, 'turn': 4, 'river': 5}[street]
    d = DECK[:]; rng.shuffle(d)
    hero, board = d[:2], d[2:2+nb]
    pot = rng.choice([600, 1200, 2400, 5000, 9000])
    tocall = int(pot*rng.choice([0.40, 0.55, 0.66, 0.75, 1.0]))
    return dict(hero=hero, board=board, street=street,
                my_range=bot.range_combos(rng.uniform(.15, .40), board),
                opp_range=bot.range_combos(rng.uniform(.15, .45), board),
                pot=pot+tocall, tocall=tocall,
                stack=int(pot*rng.choice([1.0, 2.0, 3.5, 6.0, 12.0])),
                to_act_behind=rng.choice([0, 0, 1]),
                oop=rng.random() < .5, initiative=rng.random() < .5,
                est=fake_est(rng), read=rng.uniform(.10, .70),
                seed=rng.randrange(1 << 30))


# ---------------------------------------------------------------- 층
def L_open(sits, prof):
    v = [PS.open_pct(prof, s['pos'], seats=s['seats']) for s in sits]
    return {'오픈 %': 100*ST.median(v)}


def L_defend(sits, prof):
    """**tp 와 tot 를 둘 다 낸다.** tot(참가 구간)만 보면 aggression 이
    무반응으로 보인다 — 그 축은 tp(3벳 구간)에 걸려 있다."""
    tp, tot = [], []
    for s in sits:
        try:
            _tp, _tot = pf.defend_thresholds(prof, s['def_pos'], s['pos'],
                                             s['bb'], open_bb=s['open_bb'],
                                             seats=s['seats'])
            tp.append(_tp); tot.append(_tot)
        except Exception:
            pass
    return {'3벳 구간 tp': ST.median(tp) if tp else float('nan'),
            '참가 구간 tot': ST.median(tot) if tot else float('nan')}


def L_traits(sits, prof):
    t = PS.traits_of(prof)
    return {'림프 %': 100*t['limp'], '콜 %': 100*t['call'],
            '3벳 %': 100*t['threebet'], '이소 %': 100*t['iso']}


def L_bias(sits, prof):
    """중간값을 날것과 clamp 후로 나눠 낸다 — 이게 이 층의 존재 이유다."""
    out = {}
    for nm in ('station', 'draw_love', 'overpair_love'):
        raw = PS.bias(prof, nm)
        out['%s 날것' % nm] = raw
        out['%s clamp후' % nm] = max(0.0, raw)
    return out


def L_plan(sits, prof):
    lab = Counter(); pcs = []; eqs = []
    for s in sits:
        try:
            ps = PL.make_plan(s['hero'], s['board'], s['my_range'], s['opp_range'],
                              prof, s['pot'], s['stack'], s['street'],
                              seed=s['seed'], n_opp=1,
                              to_act_behind=s['to_act_behind'], oop=s['oop'],
                              initiative=s['initiative'], opp_est=s['est'])
        except Exception:
            continue
        lab[ps['plan']] += 1
        if ps.get('pc') is not None: pcs.append(ps['pc'])
        if ps.get('eq') is not None: eqs.append(ps['eq'])
    n = max(1, sum(lab.values()))
    out = {'%s %%' % k: 100*lab[k]/n for k in
           ('pot_control', 'value_2street', 'value_3street', 'bluff_2street',
            'semibluff', 'trap', 'showdown', 'giveup', 'river_bluff', 'block')
           if lab[k]}
    out['pc 중간값'] = ST.median(pcs) if pcs else float('nan')
    return out


def _exec(sits, prof, resist):
    """계획 라벨은 고정, 실행 판단만 그 프로필로 다시 돌린다.

    무저항 경로는 `act_with_plan` 이 판단을 하지 않는다 — 의도를 칩으로
    환산만 한다(`plan.py:1315`). 의도는 `attach_intent`(→`decide_aggression`
    →`decide_size`)가 붙인다. 그래서 여기서 **의도를 지우고 그 프로필로
    다시 붙인다.** 안 그러면 전부 체크가 나온다 (처음에 그렇게 나왔다).
    `update_plan` 을 통째로 부르지 않는 이유: 그건 `_allowed`·`river_fix`
    까지 다시 돌려 **계획 라벨을 바꿀 수 있다.** 그러면 실행 층만 격리한 게
    아니게 된다.
    """
    acts = Counter(); sizes = []
    for s in sits:
        ps = s['plan_fixed']
        if ps is None: continue
        if not resist:
            ps = copy.deepcopy(ps)
            ps.pop('intents', None)
            try:
                ps = PL.attach_intent(ps, s['hero'], s['board'], s['my_range'],
                                      s['opp_range'], prof, s['pot'], s['stack'],
                                      s['street'], random.Random(s['seed']),
                                      1, s['to_act_behind'], s['oop'],
                                      s['initiative'], s['est'])
            except Exception:
                continue
        try:
            (a, amt), _eq, _nd = PL.act_with_plan(
                s['hero'], s['board'], prof, copy.deepcopy(ps),
                s['pot'], s['tocall'] if resist else 0, s['stack'], s['street'],
                initiative=s['initiative'], oop=s['oop'],
                opp_range=s['opp_range'], seed=s['seed'], n_opp=1, bf=1.0,
                to_act_behind=s['to_act_behind'], opp_est=s['est'],
                read=s['read'])
        except Exception:
            continue
        acts[a] += 1
        if a in ('bet', 'raise') and amt: sizes.append(amt/float(s['pot']))
    n = max(1, sum(acts.values()))
    return acts, n, sizes


def L_noresist(sits, prof):
    acts, n, sizes = _exec(sits, prof, False)
    return {'벳 %': 100*acts['bet']/n, '체크 %': 100*acts['check']/n,
            '벳 사이즈(팟배수) 중앙': ST.median(sizes) if sizes else float('nan')}


def L_resist(sits, prof):
    acts, n, sizes = _exec(sits, prof, True)
    return {'폴드 %': 100*acts['fold']/n, '콜 %': 100*acts['call']/n,
            '레이즈 %': 100*acts['raise']/n}


def L_bias_resp(sits, prof):
    """decide_response:827-832 가 읽는 편향 셋. 날것과 clamp 후를 둘 다.

    **이 셋은 직접 설정할 수 없는 파생 축이다.** persona.bias 가 기질·개념에서
    계산한다. 특히 bluff_fear 와 hero_call 은 bluffcatch_river·aggression 을
    **반대 부호로** 공유해서 서로 독립적으로 흔들 수 없다 — 하나를 올리면
    다른 하나가 내려간다. 그래서 '축'이 아니라 **중간값**으로 기록한다.
    """
    out = {}
    for nm in ('station', 'bluff_fear', 'hero_call'):
        raw = PS.bias(prof, nm)
        out['%s 날것' % nm] = raw
        out['%s clamp후' % nm] = max(0.0, raw)
    return out


def L_resist_flip(sits, prof):
    """저항 대응 — 분포와 **행동 질량이 어디로 옮겨갔는지**를 같이 낸다.

    폴드율 하나만 보면 해석이 갈린다. range_read 를 올려 폴드가 늘었을 때
    그게 '상대를 세게 읽어 접었다'인지 '레이즈·콜이 줄어든 결과'인지
    전환표 없이는 구분할 수 없다. 기준은 레벨 5 다.
    """
    acts = Counter(); flips = Counter(); n = 0; needs = []
    for s in sits:
        ps = s['plan_fixed']
        if ps is None or s.get('base_act') is None: continue
        try:
            (a_, _amt), _eq, _nd = PL.act_with_plan(
                s['hero'], s['board'], prof, copy.deepcopy(ps),
                s['pot'], s['tocall'], s['stack'], s['street'],
                initiative=s['initiative'], oop=s['oop'],
                opp_range=s['opp_range'], seed=s['seed'], n_opp=1, bf=1.0,
                to_act_behind=s['to_act_behind'], opp_est=s['est'],
                read=s['read'])
        except Exception:
            continue
        n += 1; acts[a_] += 1
        # 체감 need 를 같이 낸다. 행동이 안 바뀌어도 문턱은 움직일 수 있다 —
        # 그 둘을 구분해야 '축이 죽었다'와 '계수가 작다'가 갈린다.
        if _nd is not None: needs.append(_nd)
        if a_ != s['base_act']:
            flips['%s→%s' % (s['base_act'], a_)] += 1
    n = max(1, n)
    out = {'폴드 %': 100*acts['fold']/n, '콜 %': 100*acts['call']/n,
           '레이즈 %': 100*acts['raise']/n,
           '체감 need 중앙': ST.median(needs) if needs else float('nan'),
           # 중앙값만 보면 분산 변화를 놓친다. calc_noise 의 σ 는 개념이
           # 낮을수록 크므로, 중앙이 같아도 양끝으로 퍼져 행동이 갈릴 수 있다.
           '체감 need 사분위폭': ((sorted(needs)[int(.75*len(needs))]
                              - sorted(needs)[int(.25*len(needs))])
                             if len(needs) > 4 else float('nan'))}
    for k in ('fold→call', 'fold→raise', 'call→fold', 'call→raise',
              'raise→fold', 'raise→call'):
        out['  ' + k] = flips[k]
    return out


LAYER = OrderedDict([
    ('open',     (L_open,     '프리플랍 오픈 폭')),
    ('defend',   (L_defend,   '프리플랍 방어 구간')),
    ('traits',   (L_traits,   '프리플랍 성향표 (림프·콜·3벳·이소)')),
    ('bias',     (L_bias,     '행동 편향 중간값 (날것 / clamp 후)')),
    ('plan',     (L_plan,     '계획 라벨 분포 + pc 중간값')),
    ('noresist', (L_noresist, '무저항 실행 (계획 고정)')),
    ('resist',   (L_resist,   '저항 대응 (계획 고정)')),
    ('bias_resp', (L_bias_resp, '응답 편향 중간값 (날것 / clamp 후)')),
    ('resist_flip', (L_resist_flip, '저항 대응 + 전환표 (기준 = 레벨 5)')),
])

# AXIS_FREQ_PLAN.md 2-1/2-2 의 표를 그대로 옮긴 것이다. 고정축을 바꾸려면
# 먼저 그 문서를 고칠 것 — 두 곳이 갈리면 근거를 잃는다.
AXES = OrderedDict([
    ('aggression', dict(
        layers=['open', 'defend', 'traits', 'plan', 'noresist', 'resist'],
        hold={'looseness': 5, 'pf_range': 5, 'positional': 5, 'bluff': 5,
              'icm': 5, 'gamble': 5, 'range_merge': 5, 'reraise': 5,
              'stackoff': 5, 'semibluff': 5, 'cbet_flop': 5, 'barrel_turn': 5,
              'barrel_river': 5, 'board_texture': 5, 'equity_denial': 5,
              'pf_defend': 5, 'discipline': 5})),
    ('looseness', dict(
        layers=['open', 'defend', 'traits', 'bias', 'resist'],
        hold={'aggression': 5, 'pf_range': 5, 'positional': 5, 'pf_defend': 5,
              'gamble': 5, 'discipline': 5, 'potodds': 5, 'outs': 5,
              'range_read': 5})),
    ('discipline', dict(
        layers=['traits', 'bias', 'noresist', 'resist'],
        hold={'looseness': 5, 'aggression': 5, 'gamble': 5, 'potodds': 5,
              'range_read': 5, 'outs': 5})),
    ('bluff', dict(
        layers=['traits', 'plan', 'noresist'],
        hold={'aggression': 5, 'gamble': 5, 'blocker': 5, 'reraise': 5,
              'cbet_flop': 5, 'barrel_turn': 5, 'barrel_river': 5,
              'fold_equity': 5, 'looseness': 5})),
    ('semibluff', dict(
        layers=['plan', 'resist'],
        hold={'outs': 5, 'aggression': 5, 'reraise': 5, 'bluff': 5})),
    ('potcontrol', dict(
        layers=['plan'],
        hold={'icm': 5, 'gamble': 5, 'aggression': 5, 'range_merge': 5,
              'multiway': 5})),
    ('trap', dict(
        layers=['plan'],
        hold={'checkraise_flop': 5, 'checkraise_late': 5, 'slowplay_taste': 5,
              'overbet': 5})),
    # ---- 3단계: 응답 축 ----
    # station·bluff_fear·hero_call 은 여기 없다. 파생 축이라 직접 못 흔든다.
    # bias_resp 층이 중간값으로 기록한다.
    ('reraise', dict(
        layers=['resist_flip'],
        hold={'aggression': 5, 'bluff': 5, 'stackoff': 5, 'semibluff': 5,
              'gamble': 5, 'discipline': 5})),
    ('potodds', dict(
        layers=['bias_resp', 'resist_flip'],
        hold={'looseness': 5, 'gamble': 5, 'discipline': 5, 'outs': 5,
              'range_read': 5, 'reraise': 5})),
    ('range_read', dict(
        layers=['bias_resp', 'resist_flip'],
        hold={'sizing_tell': 5, 'attention': 5, 'adaptability': 5,
              'bluffcatch_river': 5, 'bluffcatch_early': 5, 'aggression': 5,
              'discipline': 5, 'potodds': 5, 'reraise': 5})),
    ('bluffcatch_early', dict(
        layers=['bias_resp', 'resist_flip'],
        hold={'bluffcatch_river': 5, 'range_read': 5, 'aggression': 5,
              'potodds': 5, 'reraise': 5})),
    ('bluffcatch_river', dict(
        layers=['bias_resp', 'resist_flip'],
        hold={'bluffcatch_early': 5, 'range_read': 5, 'aggression': 5,
              'tilt_prone': 5, 'potodds': 5, 'reraise': 5})),
    # trap 의 짝. trap_judgment:218 은 tool = 0.07*trap + 0.12*checkraise 라
    # 실행 쪽 무게가 1.7배다. trap 만 흔들어 작게 나온 것이 '층이 죽어서'가
    # 아님을 보이려면 이쪽을 같이 재야 한다.
    ('checkraise_flop', dict(
        layers=['plan'],
        hold={'trap': 5, 'checkraise_late': 5, 'slowplay_taste': 5,
              'overbet': 5})),
])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--axis', default=None)
    ap.add_argument('--n', type=int, default=250)
    ap.add_argument('--street', default='flop', choices=['flop', 'turn', 'river'])
    ap.add_argument('--seed', type=int, default=20260915)
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    if a.list:
        for k, v in AXES.items():
            print('%-12s %s' % (k, '  '.join(v['layers'])))
        return
    if not a.axis or a.axis not in AXES:
        raise SystemExit('--axis 를 %s 중에서 고르세요' % '/'.join(AXES))

    spec = AXES[a.axis]
    base = PS.make_player(random.Random(a.seed), 0.78, 0)
    levels = sorted(set(LEVELS + GATE_LEVELS.get(a.axis, [])))

    # 상황은 **한 번만** 만든다. 레벨마다 다시 뽑으면 스트림이 어긋난다.
    rng = random.Random(a.seed)
    sits = []
    for _ in range(a.n):
        s = post_sit(rng, a.street)
        s['pos'] = rng.choice(POS); s['seats'] = rng.choice([6, 8, 9])
        s['def_pos'] = rng.choice(['BB', 'SB', 'BTN'])
        s['bb'] = rng.uniform(15, 60); s['open_bb'] = rng.choice([2.0, 2.5, 3.0])
        sits.append(s)

    # 실행 층은 **계획을 고정**한다 (기준 프로필로 한 번만 만든다).
    need_exec = any(l in spec['layers']
                    for l in ('noresist', 'resist', 'resist_flip'))
    if need_exec:
        p0 = build(base, a.axis, 5, spec['hold'])
        for s in sits:
            try:
                s['plan_fixed'] = PL.make_plan(
                    s['hero'], s['board'], s['my_range'], s['opp_range'], p0,
                    s['pot'], s['stack'], s['street'], seed=s['seed'], n_opp=1,
                    to_act_behind=s['to_act_behind'], oop=s['oop'],
                    initiative=s['initiative'], opp_est=s['est'])
            except Exception:
                s['plan_fixed'] = None
        # 전환표의 기준선. 레벨 5 의 행동을 상황마다 박아 둔다.
        if 'resist_flip' in spec['layers']:
            for s in sits:
                s['base_act'] = None
                if s['plan_fixed'] is None: continue
                try:
                    (a_, _m), _e, _n = PL.act_with_plan(
                        s['hero'], s['board'], p0, copy.deepcopy(s['plan_fixed']),
                        s['pot'], s['tocall'], s['stack'], s['street'],
                        initiative=s['initiative'], oop=s['oop'],
                        opp_range=s['opp_range'], seed=s['seed'], n_opp=1, bf=1.0,
                        to_act_behind=s['to_act_behind'], opp_est=s['est'],
                        read=s['read'])
                    s['base_act'] = a_
                except Exception:
                    pass

    print('# %s — 층별 빈도. n=%d, %s' % (a.axis, len(sits), a.street))
    print('# 고정: %s' % ', '.join('%s=%g' % kv for kv in sorted(spec['hold'].items())))
    print('# 레벨: %s%s\n' % (levels,
          '   (게이트 의심 → 문턱 근처 촘촘히)' if a.axis in GATE_LEVELS else ''))

    for lname in spec['layers']:
        fn, desc = LAYER[lname]
        cols = []
        for v in levels:
            cols.append(fn(sits, build(base, a.axis, v, spec['hold'])))
        # **모든 레벨의 키를 합집합으로 모은다.** 첫 열에서만 뽑으면
        # 레벨 1 에서 0건인 라벨의 행이 통째로 사라진다 — bluff 축의
        # bluff_2street 행과 semibluff 축의 semibluff 행이 실제로 사라졌다.
        keys = []
        for c in cols:
            for k in c:
                if k not in keys:
                    keys.append(k)
        print('## %s — %s' % (lname, desc))
        print('  %-26s %s' % ('', '  '.join('%7g' % v for v in levels)))
        for k in keys:
            vals = [c.get(k, 0.0) if k.endswith('%') else c.get(k, float('nan'))
                    for c in cols]
            print('  %-26s %s' % (k, '  '.join('%7.2f' % x for x in vals)))
        print()

    # 위약 — plan.py 가 읽지 않는 축. 층 전부에서 0 변화여야 한다.
    print('## 위약 (%s) — 전부 변화 0 이어야 한다' % '·'.join(PLACEBO))
    for pl in PLACEBO:
        diffs = []
        for lname in spec['layers']:
            fn, _ = LAYER[lname]
            lo = fn(sits, build(base, pl, 1, spec['hold']))
            hi = fn(sits, build(base, pl, 9, spec['hold']))
            for k in lo:
                if lo[k] == lo[k] and hi[k] == hi[k]:
                    diffs.append(abs(hi[k] - lo[k]))
        print('  %-14s 최대 변화 %.4f  %s'
              % (pl, max(diffs) if diffs else 0.0,
                 '← 0 이어야 한다' if max(diffs or [0]) < 1e-9 else '← 문제!'))


if __name__ == '__main__':
    main()
