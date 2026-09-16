#!/usr/bin/env python3
"""축의 **데이터 흐름** 소비처 지도 — 직접 읽기 + 파생 경유.

  python3 tools/axis_dataflow.py

**문자열 검색으로 소비처를 세면 안 된다.** 두 번 같은 실수를 했다.

  1차  aggression → persona.open_pct 를 놓쳤다 (CF_RESULT_LEVEL1 0절)
  2차  discipline → persona.bias → perceived_rel → make_plan 을 놓쳤다
       "discipline 은 계획층 소비처가 없다" 고 단정했는데 실측에서
       make_plan 의 rel 이 246건/101건 바뀌었다

축이 `plan.py` 안에서 자기 이름으로 읽히지 않아도, 파생값을 거쳐
계획에 도달할 수 있다.

```
축 → persona.derive   → aggr·bluff·gamble·icm·tilt·tricky·value·goal·tight
축 → persona.bias     → station·bluff_fear·overpair_love·draw_love
                        ·hero_call·sticky
                          ↓
                      plan.perceived_rel (draw_love·overpair_love·sticky)
                          ↓
                      make_plan 의 rel → plan 라벨
```

이 도구는 두 경로를 모두 따라가 **직접 / 간접**을 구분해 낸다.
"""
import os, re, sys, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)

# plan.py 의 계획층 / 실행층 함수
L2F = {'make_plan', 'refresh', 'river_fix', '_allowed', 'revise_plan',
       'line_bluff_prior', 'checkraise_decision', 'trap_judgment',
       'perceived_rel', 'stackoff_plan', 'update_plan'}
L1F = {'decide_aggression', 'decide_response', 'cbet_freq', 'calldown_need',
       'decide_size', 'overbet_frac', 'barrel_size', 'bluff_mode',
       'opp_bet_prob', 'attach_intent', 'act_with_plan'}
# **cf_axis_l2.py 의 D 팔이 실제로 교체하는 집합은 이보다 작다** — 아래 둘이
# 빠진다. 어떤 축이 이 둘에서만 읽히면 D 팔 개입이 그 축에 닿지 않는다.
L1_ONLY_HERE = {'attach_intent', 'act_with_plan'}
L1_D = L1F - L1_ONLY_HERE

# 계획층 안에서 호출되는 실행층 함수 (CF_DESIGN_LEVEL2 5-2).
# 이 함수들에서 읽힌 축은 **계획 구축 중에도** 읽힌다.
L1_IN_L2 = {'barrel_size': 'make_plan:480', 'bluff_mode': 'make_plan:497',
            'opp_bet_prob': 'trap_judgment:224'}


def fn_index(path):
    src = open(path, encoding='utf-8').read().split('\n')
    bounds = []
    for i, l in enumerate(src):
        m = re.match(r'^def (\w+)', l)
        if m: bounds.append((i+1, m.group(1)))
    def of(ln):
        cur = '<module>'
        for s, n in bounds:
            if s <= ln: cur = n
            else: break
        return cur
    return src, of


# persona.street_concept / ALIAS 가 만드는 **간접 이름**.
# plan.py 는 `PS.sk(profile, PS.street_concept('thin_value', street))` 처럼
# 부르므로 'thin_value_turn' 문자열이 소스에 없다. 문자열 검색만 하면
# 이 축들이 통째로 사라진다 — 실측에서 thin_value_turn M=0.2% 가 나온
# 뒤에야 드러났다. **세 번째로 반복된 같은 실수다.**
SC = {
    'cbet':       ('cbet_flop', 'barrel_turn', 'barrel_river'),
    'barrel':     ('barrel_turn', 'barrel_river'),
    'checkraise': ('checkraise_flop', 'checkraise_late'),
    'bluffcatch': ('bluffcatch_early', 'bluffcatch_river'),
    'thin_value': ('thin_value_turn', 'thin_value_river'),
}


def reads(path, names):
    """path 안에서 names 각각을 읽는 함수 집합.

    직접 문자열 + street_concept/ALIAS 경유 간접 이름을 모두 센다.
    """
    src, of = fn_index(path)
    out = collections.defaultdict(collections.Counter)
    rev = {}
    for base, targets in SC.items():
        for t in targets:
            rev.setdefault(t, []).append(base)
    for i, l in enumerate(src):
        if l.strip().startswith('#'): continue
        for nm in names:
            hit = bool(re.search(r"'%s'" % re.escape(nm), l))
            if not hit:
                for base in rev.get(nm, []):
                    if re.search(r"street_concept\(\s*'%s'" % re.escape(base), l) \
                            or re.search(r"ALIAS\b", l) and False:
                        hit = True; break
            if hit:
                out[nm][of(i+1)] += 1
    return out


def main():
    import persona as PS
    P = os.path.join(D, 'persona.py')
    PL = os.path.join(D, 'plan.py')

    # --- persona.derive 가 만드는 필드 ← 어느 축에서 ---
    src, of = fn_index(P)
    dv_start = next(i for i, l in enumerate(src) if l.startswith('def derive'))
    dv = {}
    for l in src[dv_start:dv_start+20]:
        m = re.match(r"\s*'(\w+)':\s*(.*)", l)
        if not m: continue
        fld, expr = m.group(1), m.group(2)
        deps = set(re.findall(r"[ct]\['(\w+)'\]", expr))
        deps |= set(re.findall(r"\bt\['(\w+)'\]", expr))
        if deps: dv[fld] = deps

    # --- persona.bias 가 만드는 파생축 ← 어느 축에서 ---
    b0 = next(i for i, l in enumerate(src) if l.startswith('def bias'))
    b1 = next(i for i in range(b0+1, len(src)) if src[i].startswith('def '))
    bi = {}; cur = None
    for l in src[b0:b1]:
        m = re.search(r"if name == '(\w+)'", l)
        if m: cur = m.group(1); bi[cur] = set()
        if cur:
            bi[cur] |= {'t:'+x for x in re.findall(r"T\('(\w+)'\)", l)}
            bi[cur] |= {'c:'+x for x in re.findall(r"S\('(\w+)'\)", l)}

    # --- plan.py 가 파생값을 읽는 함수 ---
    pl_dv = reads(PL, list(dv) + list(bi))

    # --- 축 목록 ---
    import random
    p = PS.make_player(random.Random(1), 0.78, 1)
    axes = sorted(p['concepts']) + sorted(p['temper'])
    pl_ax = reads(PL, axes)

    print('# 축의 데이터 흐름 소비처 (직접 / 간접)')
    print()
    print('persona.derive 필드 ← 축')
    for f, d in sorted(dv.items()):
        w = pl_dv.get(f, {})
        tag = ('L2:' + ','.join(sorted(k for k in w if k in L2F))) if any(k in L2F for k in w) else ''
        print('   %-8s ← %-28s %s' % (f, ' '.join(sorted(d)), tag))
    print()
    print('persona.bias 파생축 ← 축')
    for f, d in sorted(bi.items()):
        w = pl_dv.get(f, {})
        l2 = sorted(k for k in w if k in L2F)
        print('   %-14s ← %-46s %s' % (f, ' '.join(sorted(d)),
                                       ('L2:'+','.join(l2)) if l2 else ''))
    print()
    hdr = '%-18s %-30s %-34s'
    print(hdr % ('축', '직접 계획층(L2)', '간접 계획층 경로'))
    print('-'*84)
    for ax in axes:
        direct = sorted(k for k in pl_ax.get(ax, {}) if k in L2F)
        ind = []
        for f, d in bi.items():
            if ('t:'+ax in d or 'c:'+ax in d):
                w = pl_dv.get(f, {})
                for k in w:
                    if k in L2F: ind.append('bias:%s→%s' % (f, k))
        for f, d in dv.items():
            if ax in d:
                w = pl_dv.get(f, {})
                for k in w:
                    if k in L2F: ind.append('derive:%s→%s' % (f, k))
        if not direct and not ind: continue
        print(hdr % (ax, ' '.join(direct) or '**없음**',
                     ' '.join(sorted(set(ind))) or '없음'))
    print()
    print('직접·간접 **둘 다 없는** 축만 Level 2 에서 M=0 이 구조적으로 확정된다.')

    # ---------- 실행층(L1) ----------
    print()
    print('=' * 84)
    print()
    print('# 실행층(L1) 함수에서 읽히는 축')
    print()
    print('**이것은 "호출 지점 분류" 이지 "런타임 도달 범위" 가 아니다.** 두 가지')
    print('이유로 이름 기준 분류가 실제 도달과 어긋난다.')
    print()
    print('  5-2  make_plan 이 barrel_size(480)·bluff_mode(497) 를,')
    print('       trap_judgment 가 opp_bet_prob(224) 을 부른다.')
    print('       → 이 셋에서 읽힌 축은 **계획 구축 중에도** 읽힌다')
    print('  5-1  perceived_rel(계획층)이 만든 rel 을 실행층이 읽는다.')
    print('       → 계획층에서만 읽히는 축도 행동에 닿을 수 있다')
    print()
    print('  또 attach_intent·act_with_plan 은 이 표의 L1F 에는 있지만')
    print('  cf_axis_l2.py 의 D 팔 개입 집합에는 **없다**. 그 둘에서만 읽히는')
    print('  축은 D 팔이 건드리지 못한다 — 아래에서 (D팔밖) 으로 표시한다.')
    print()
    print('  **이 표는 호출 그래프가 아니라 읽기 지점 표다.** 실행층 안의 중첩')
    print('  호출은 드러나지 않는다 — cbet_freq 는 decide_aggression:863 안에서,')
    print('  overbet_frac 는 decide_size:1038 안에서, barrel_size 는')
    print('  bluff_mode:1995 안에서 불린다. 그래서 cbet_flop 처럼 cbet_freq 에서만')
    print('  읽히는 축도 decide_aggression 개입에 실제로는 닿는다')
    print('  (L1 POST flip 1.0% 가 그 경우다).')
    print()
    h2 = '%-18s %-34s %-30s'
    print(h2 % ('축', '직접 실행층(L1)', '간접 실행층 경로'))
    print('-' * 84)
    nothing = []
    for ax in axes:
        def mark(k):
            t = k
            if k in L1_IN_L2: t += '(계획층내:%s)' % L1_IN_L2[k].split(':')[0]
            if k in L1_ONLY_HERE: t += '(D팔밖)'
            return t
        direct = sorted(k for k in pl_ax.get(ax, {}) if k in L1F)
        ind = []
        for f, d in bi.items():
            if 't:' + ax in d or 'c:' + ax in d:
                for k in pl_dv.get(f, {}):
                    if k in L1F: ind.append('bias:%s→%s' % (f, mark(k)))
        for f, d in dv.items():
            if ax in d:
                for k in pl_dv.get(f, {}):
                    if k in L1F: ind.append('derive:%s→%s' % (f, mark(k)))
        if not direct and not ind:
            nothing.append(ax); continue
        print(h2 % (ax, ' '.join(mark(k) for k in direct) or '**없음**',
                    ' '.join(sorted(set(ind))) or '없음'))
    print()
    print('실행층 함수에서 전혀 읽히지 않는 축 (%d개)' % len(nothing))
    for i in range(0, len(nothing), 4):
        print('   ' + '  '.join('%-18s' % x for x in nothing[i:i+4]))


if __name__ == '__main__':
    main()
