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


def fake_est(rng, kind='mixed'):
    """상대 추정치. kind 로 **폴드 성향**을 가른다.

    `fold_equity` 는 `_fg = street_gap(rd, street)` 의 **부호**에 따라 방향이
    뒤집힌다(`plan.py:892`). 잘 접는 상대와 안 접는 상대를 섞어 재면
    두 방향이 서로 지워져 '무반응'으로 보인다.
    """
    ftb = {'folder': rng.uniform(0.72, 0.88),
           'station': rng.uniform(0.22, 0.38)}.get(kind, rng.uniform(0.30, 0.75))
    return {'confidence': rng.uniform(0.4, 0.9), 'n': rng.randint(15, 60),
            'ftb': ftb, 'fold': ftb, 'bluff': rng.uniform(2, 8),
            'aggr': rng.uniform(2, 8), 'ftb_flop': ftb, 'ftb_turn': ftb,
            'ftb_river': ftb, 'sizing_tell': rng.uniform(1, 9),
            'range_read': rng.uniform(1, 9), 'sz_mean': rng.uniform(0.4, 0.9),
            'sz_sd': rng.uniform(.10, .35), 'sz_n': rng.randint(4, 20),
            'sz_big': rng.uniform(0, .4), 'type': None}


def post_sit(rng, street='flop', n_opp=1, est_kind='mixed'):
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
                est=fake_est(rng, est_kind), read=rng.uniform(.10, .70),
                n_opp=n_opp, seed=rng.randrange(1 << 30))


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
    """계획 라벨 분포 + **기준(레벨 5) 대비 뒤집힘 수.**

    집계 %만 보면 0 으로 보이는데 상황별로는 뒤집히는 경우가 있다 —
    한쪽으로 간 건수와 반대쪽으로 온 건수가 우연히 맞으면 표가 안 움직인다.
    실제로 `stackoff` 에서 그랬다. `resist_flip` 과 같은 이유로 전환을 센다.
    """
    lab = Counter(); pcs = []; eqs = []; flip = 0
    for s in sits:
        try:
            ps = PL.make_plan(s['hero'], s['board'], s['my_range'], s['opp_range'],
                              prof, s['pot'], s['stack'], s['street'],
                              seed=s['seed'], n_opp=s['n_opp'],
                              to_act_behind=s['to_act_behind'], oop=s['oop'],
                              initiative=s['initiative'], opp_est=s['est'])
        except Exception:
            continue
        lab[ps['plan']] += 1
        if s.get('base_plan') is not None and ps['plan'] != s['base_plan']:
            flip += 1
        if ps.get('pc') is not None: pcs.append(ps['pc'])
        if ps.get('eq') is not None: eqs.append(ps['eq'])
    n = max(1, sum(lab.values()))
    out = {'%s %%' % k: 100*lab[k]/n for k in
           ('pot_control', 'value_2street', 'value_3street', 'bluff_2street',
            'semibluff', 'trap', 'showdown', 'giveup', 'river_bluff', 'block')
           if lab[k]}
    out['pc 중간값'] = ST.median(pcs) if pcs else float('nan')
    out['라벨 뒤집힘 (vs lv5)'] = flip
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
                                      s['n_opp'], s['to_act_behind'], s['oop'],
                                      s['initiative'], s['est'])
            except Exception:
                continue
        try:
            (a, amt), _eq, _nd = PL.act_with_plan(
                s['hero'], s['board'], prof, copy.deepcopy(ps),
                s['pot'], s['tocall'] if resist else 0, s['stack'], s['street'],
                initiative=s['initiative'], oop=s['oop'],
                opp_range=s['opp_range'], seed=s['seed'], n_opp=s['n_opp'], bf=1.0,
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
                opp_range=s['opp_range'], seed=s['seed'], n_opp=s['n_opp'], bf=1.0,
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


def L_noresist_size(sits, prof):
    """무저항 실행 — **빈도와 크기를 분리해서 낸다.**

    '벳을 더 자주 치는가'와 '칠 때 더 크게 치는가'는 다른 질문이다.
    한 숫자로 뭉치면 `overbet` 처럼 빈도가 아니라 크기만 바꾸는 축을
    '약한 축'으로 오독한다.
    """
    acts = Counter(); sizes = []
    for s in sits:
        ps = s['plan_fixed']
        if ps is None: continue
        ps = copy.deepcopy(ps); ps.pop('intents', None)
        try:
            ps = PL.attach_intent(ps, s['hero'], s['board'], s['my_range'],
                                  s['opp_range'], prof, s['pot'], s['stack'],
                                  s['street'], random.Random(s['seed']),
                                  s['n_opp'], s['to_act_behind'], s['oop'],
                                  s['initiative'], s['est'])
            (a_, amt), _e, _n = PL.act_with_plan(
                s['hero'], s['board'], prof, copy.deepcopy(ps),
                s['pot'], 0, s['stack'], s['street'],
                initiative=s['initiative'], oop=s['oop'],
                opp_range=s['opp_range'], seed=s['seed'], n_opp=s['n_opp'], bf=1.0,
                to_act_behind=s['to_act_behind'], opp_est=s['est'],
                read=s['read'])
        except Exception:
            continue
        acts[a_] += 1
        if a_ == 'bet' and amt:
            sizes.append(amt/float(s['pot']))
    n = max(1, sum(acts.values()))
    nb = max(1, len(sizes))
    ob = [x for x in sizes if x > 1.0]
    return {'벳 %': 100*acts['bet']/n,
            '벳 사이즈 중앙(팟배수)': ST.median(sizes) if sizes else float('nan'),
            '벳 중 오버벳(>1팟) %': 100*len(ob)/nb,
            '오버벳 사이즈 중앙': ST.median(ob) if ob else float('nan')}


def L_stackoff_path(sits, prof):
    """커밋 구간(SPR<1.2)의 저항 대응 + **어느 경로에서 나왔는가.**

    `decide_response` 가 돌려주는 why 문자열로 분류한다. 빈도만 세면
    '밸류 레이즈로 커밋'과 '팟오즈로 콜'이 한 칸에 들어간다.
    """
    acts = Counter(); path = Counter(); n = 0
    for s in sits:
        ps = s['plan_fixed']
        if ps is None: continue
        ps = copy.deepcopy(ps)
        try:
            (a_, _amt), _e, _nd = PL.act_with_plan(
                s['hero'], s['board'], prof, ps,
                s['pot'], s['tocall'], s['stack_commit'], s['street'],
                initiative=s['initiative'], oop=s['oop'],
                opp_range=s['opp_range'], seed=s['seed'], n_opp=s['n_opp'], bf=1.0,
                to_act_behind=s['to_act_behind'], opp_est=s['est'],
                read=s['read'])
        except Exception:
            continue
        n += 1; acts[a_] += 1
        for w in (ps.get('acts') or [])[-1:]:
            k = ('넛급' if '넛급' in w else
                 '밸류' if '밸류' in w else
                 '세미블러프' if '세미블러프' in w else
                 '이탈' if 'DEVIATE' in w else
                 '포기/블러프계획' if '포기' in w or '블러프 계획' in w else
                 '팟오즈 산수')
            path['  경로:' + k] += 1
    n = max(1, n)
    out = {'폴드 %': 100*acts['fold']/n, '콜 %': 100*acts['call']/n,
           '레이즈 %': 100*acts['raise']/n}
    for k, v in path.most_common():
        out[k] = 100.0*v/n
    return out


def L_overbet(sits, prof, _K=20):
    """`overbet` 은 실현 빈도로 재면 안 된다 — 게이트가 곱으로 셋이다.

    `plan.py:1120` 이 `if street == 'flop': return None` 이라 **플랍은 도메인
    밖**이고, 리버에서도 `p = 0.16*개념 × (0.25+1.9*넛우위) × 양극화 × 공격성`
    이 전부 곱이라 실현 발동이 100건에 2건 수준이다. 그 표본으로 축을 재면
    분산이 효과보다 크다.

    그래서 상황마다 rng 를 `_K` 번 바꿔 **발동 확률 자체**를 추정한다.
    병목이 어느 게이트인지도 같이 낸다 (실측: 넛 우위가 병목, 중앙 0.005).
    """
    QUAL = ('value_3street', 'trap', 'bluff_2street', 'semibluff', 'river_bluff')
    qual = 0; nut_pos = 0; hits = 0; trials = 0; szs = []
    for s in sits:
        ps = s['plan_fixed']
        if ps is None or ps.get('plan') not in QUAL: continue
        qual += 1
        if (ps.get('nut_adv') or 0) > 0: nut_pos += 1
        for k in range(_K):
            try:
                ob = PL.overbet_frac(prof, s['hero'], s['board'], s['opp_range'],
                                     s['my_range'], s['street'], ps['plan'],
                                     ps.get('rel', 0.5), random.Random(s['seed'] + k),
                                     s['est'])
            except Exception:
                continue
            trials += 1
            if ob: hits += 1; szs.append(ob)
    n = max(1, len(sits))
    return {'계획 자격 %': 100*qual/n,
            '  그중 넛우위>0 %': 100*nut_pos/max(1, qual),
            '발동 확률 %%, 반복 %d회' % _K: 100*hits/max(1, trials),
            '발동 시 사이즈 중앙': ST.median(szs) if szs else float('nan')}


def L_read_w(sits, prof):
    """`fold_equity` 게이트의 재료. 축이 아니라 **도메인 기록**이다.

    `plan.py:889-892` 는 `opp_est` 가 있고 `read_opponent` 의 `w > 0` 일 때만
    걸리고, 그 뒤 `_fg`(폴드 성향 갭)의 **부호로 방향이 뒤집힌다.**
    표본이 이 조건을 만족하는지 먼저 보여야 판정이 가능하다.
    """
    ws, fgs = [], []
    for s in sits:
        rd = PS.read_opponent(prof, s['est'])
        ws.append(rd.get('w', 0.0))
        fgs.append(PS.street_gap(rd, s['street']))
    n = max(1, len(ws))
    return {'exploit w 중앙': ST.median(ws),
            '  w > 0 비율 %': 100*sum(1 for x in ws if x > 0)/n,
            'fold_gap 중앙': ST.median(fgs),
            '  fold_gap > 0 비율 %': 100*sum(1 for x in fgs if x > 0)/n}


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
    ('noresist_size', (L_noresist_size, '무저항 실행 — 빈도와 크기를 분리')),
    ('stackoff_path', (L_stackoff_path, '커밋 구간(SPR<1.2) 저항 + 경로')),
    ('overbet', (L_overbet, '오버벳 — 실현 빈도가 아니라 발동 확률')),
    ('read_w', (L_read_w, 'fold_equity 게이트 재료 (w · fold_gap)')),
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
    # ---- 4단계: 실행 축 ----
    # 스트리트 축은 --street 를 그 스트리트로 줘야 한다. cbet_flop 을 턴에서
    # 재면 street_concept 가 barrel_turn 을 읽어 다른 축을 재게 된다.
    ('cbet_flop', dict(
        layers=['noresist_size'],
        hold={'aggression': 5, 'bluff': 5, 'board_texture': 5, 'multiway': 5,
              'barrel_turn': 5, 'barrel_river': 5, 'equity_denial': 5})),
    ('barrel_turn', dict(
        layers=['noresist_size'],
        hold={'aggression': 5, 'bluff': 5, 'board_texture': 5, 'multiway': 5,
              'cbet_flop': 5, 'barrel_river': 5, 'equity_denial': 5})),
    ('barrel_river', dict(
        layers=['noresist_size'],
        hold={'aggression': 5, 'bluff': 5, 'board_texture': 5, 'multiway': 5,
              'cbet_flop': 5, 'barrel_turn': 5, 'equity_denial': 5})),
    ('overbet', dict(
        layers=['overbet', 'noresist_size'],
        hold={'aggression': 5, 'bluff': 5, 'board_texture': 5,
              'equity_denial': 5, 'blocker': 5, 'checkraise_flop': 5})),
    ('equity_denial', dict(
        layers=['noresist_size'],
        hold={'aggression': 5, 'board_texture': 5, 'overbet': 5, 'bluff': 5})),
    ('probe', dict(
        layers=['noresist_size'],
        hold={'aggression': 5, 'bluff': 5, 'delayed_cbet': 5, 'outs': 5})),
    ('delayed_cbet', dict(
        layers=['noresist_size'],
        hold={'aggression': 5, 'bluff': 5, 'probe': 5, 'cbet_flop': 5})),
    ('thin_value_turn', dict(
        layers=['plan', 'noresist_size'],
        hold={'stackoff': 5, 'aggression': 5, 'range_merge': 5,
              'thin_value_river': 5})),
    ('stackoff', dict(
        layers=['plan', 'stackoff_path'],
        hold={'thin_value_turn': 5, 'thin_value_river': 5, 'reraise': 5,
              'aggression': 5, 'gamble': 5})),
    # ---- 조건부 축: 정의역 조건이 측정 설계의 일부다 ----
    # multiway  → --nopp 로 n_opp 를 준다. HU(1) 를 대조군으로 같이 돌릴 것.
    # fold_equity → --esttype folder / station 으로 상대 유형을 갈라야 한다.
    #               섞으면 두 방향이 서로 지워진다.
    ('multiway', dict(
        layers=['noresist_size'],
        hold={'aggression': 5, 'bluff': 5, 'cbet_flop': 5, 'board_texture': 5,
              'fold_equity': 5, 'probe': 5})),
    ('fold_equity', dict(
        layers=['read_w', 'noresist_size'],
        hold={'aggression': 5, 'bluff': 5, 'board_texture': 5, 'multiway': 5,
              'attention': 5, 'adaptability': 5, 'range_read': 5,
              'cbet_flop': 5, 'probe': 5})),
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
    ap.add_argument('--nopp', type=int, default=1,
                    help='상대 수. multiway 는 >=2 라야 계수가 0 이 아니다')
    ap.add_argument('--esttype', default='mixed',
                    choices=['mixed', 'folder', 'station'],
                    help='상대 폴드 성향. fold_equity 는 이걸 갈라야 한다')
    ap.add_argument('--line', default='none',
                    choices=['none', 'flop_checked', 'opp_checked', 'both'],
                    help='라인 이력을 심는다. probe·delayed_cbet 전용')
    ap.add_argument('--force', default='',
                    help="포지션 강제. 'oop_nonitiative' 면 probe 경로 조건")
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
        s = post_sit(rng, a.street, n_opp=a.nopp, est_kind=a.esttype)
        s['pos'] = rng.choice(POS); s['seats'] = rng.choice([6, 8, 9])
        s['def_pos'] = rng.choice(['BB', 'SB', 'BTN'])
        s['bb'] = rng.uniform(15, 60); s['open_bb'] = rng.choice([2.0, 2.5, 3.0])
        # 커밋 구간용 스택. spr(stack, pot) < 1.2 라야 committed 가 켜진다.
        s['stack_commit'] = int(s['pot']*rng.uniform(0.4, 1.1))
        # 라인 이력 강제. **엔진이 세우는 것과 같은 값이다** —
        #   flop_checked      plan.py:1681  내 플랍 의도가 check/None 이었는가
        #   opp_checked_prev  session.py:513 직전 스트리트에 상대가 벳 안 했는가
        # 둘 다 관측 가능한 라인 사실에서 나오는 불리언이라, 여기서 심는 것은
        # 값을 지어내는 것이 아니라 그 라인을 재현하는 것이다.
        if a.force == 'oop_noninitiative':
            s['oop'] = True; s['initiative'] = False
        sits.append(s)

    # 실행 층은 **계획을 고정**한다 (기준 프로필로 한 번만 만든다).
    if 'plan' in spec['layers']:
        _p5 = build(base, a.axis, 5, spec['hold'])
        for s in sits:
            try:
                s['base_plan'] = PL.make_plan(
                    s['hero'], s['board'], s['my_range'], s['opp_range'], _p5,
                    s['pot'], s['stack'], s['street'], seed=s['seed'],
                    n_opp=s['n_opp'],
                    to_act_behind=s['to_act_behind'], oop=s['oop'],
                    initiative=s['initiative'], opp_est=s['est'])['plan']
            except Exception:
                s['base_plan'] = None
    need_exec = any(l in spec['layers']
                    for l in ('noresist', 'resist', 'resist_flip',
                              'noresist_size', 'stackoff_path'))
    if need_exec:
        p0 = build(base, a.axis, 5, spec['hold'])
        for s in sits:
            try:
                s['plan_fixed'] = PL.make_plan(
                    s['hero'], s['board'], s['my_range'], s['opp_range'], p0,
                    s['pot'], s['stack'], s['street'], seed=s['seed'],
                    n_opp=s['n_opp'],
                    to_act_behind=s['to_act_behind'], oop=s['oop'],
                    initiative=s['initiative'], opp_est=s['est'])
            except Exception:
                s['plan_fixed'] = None
            if s['plan_fixed'] is not None and a.line != 'none':
                if a.line in ('flop_checked', 'both'):
                    s['plan_fixed']['flop_checked'] = True
                if a.line in ('opp_checked', 'both'):
                    s['plan_fixed']['opp_checked_prev'] = True
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
                        opp_range=s['opp_range'], seed=s['seed'], n_opp=s['n_opp'], bf=1.0,
                        to_act_behind=s['to_act_behind'], opp_est=s['est'],
                        read=s['read'])
                    s['base_act'] = a_
                except Exception:
                    pass

    print('# %s — 층별 빈도. n=%d, %s, n_opp=%d, 상대=%s%s%s'
          % (a.axis, len(sits), a.street, a.nopp, a.esttype,
             ', 라인=%s' % a.line if a.line != 'none' else '',
             ', 강제=%s' % a.force if a.force else ''))
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
