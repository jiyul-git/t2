#!/usr/bin/env python3
"""성향 축의 **실제 사용처 전수 추적**. 읽기 전용이다.

  python3 tools/axis_sites.py                  # 전체 요약
  python3 tools/axis_sites.py --axis aggression  # 한 축의 모든 줄

`tools/wirecheck.py` 는 "있어야 할 자리에 배선됐는가"를 명세와 대조한다.
이 도구는 반대다 — **실제로 어디서 읽히는가**를 전부 모은다. 명세에 없는
자리에서 읽히는 것도 나와야 한다. 지표를 정의하려면 그게 필요하다.

찾는 형태 (별칭 포함)
  PS.sk(prof, 'X')            개념 숙련도
  PS.temper(prof, 'X')        기질
  PS.bias(prof, 'X')          행동 편향
  PS.gate(prof, 'X')          개념 → 확률 배수
  PS.calc_noise(prof, 'X')    계산 오차
  profile['aggr'] 등          persona.derive 가 만든 별칭
  PS.street_concept('X', st)  스트리트별 동적 키

**별칭을 꼭 같이 봐야 한다.** derive 가
  aggr←aggression, bluff←concepts.bluff, gamble, icm, tilt←tilt_prone,
  tight←10-looseness
를 만들어서, `profile['aggr']` 한 줄이 aggression 의 사용처다.
grep 으로 'aggression' 만 찾으면 대부분을 놓친다.
"""
import argparse, os, re, sys
from collections import OrderedDict, defaultdict

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)
import persona as PS

SKIP = ('legacy', 'tools')
ALIAS = {'aggr': 'aggression', 'tilt': 'tilt_prone', 'tight': 'looseness'}
# bluff/gamble/icm 은 별칭 이름이 원래 이름과 같다
SAME = ('bluff', 'gamble', 'icm')

PATS = [
    (re.compile(r"\bsk\(\s*[A-Za-z_]\w*\s*,\s*'([a-z_]+)'"),        'sk'),
    # plan.py 는 make_plan 안에서 sk = lambda c: PS.sk(profile, c) 를 만든다.
    # 인자 하나짜리 형태를 안 보면 potcontrol·range_merge 를 통째로 놓친다.
    (re.compile(r"(?<![\w.])sk\(\s*'([a-z_]+)'\s*\)"),               'sk(지역)'),
    # depth.py 는 sk_fn 으로 주입받는다. dynamics.py 는 _t 로 기질을 읽는다.
    (re.compile(r"\bsk_fn\(\s*[A-Za-z_]\w*\s*,\s*'([a-z_]+)'"),     'sk_fn'),
    (re.compile(r"\btemper_fn\(\s*[A-Za-z_]\w*\s*,\s*'([a-z_]+)'"), 'temper_fn'),
    (re.compile(r"(?<![\w.])_t\(\s*[A-Za-z_]\w*\s*,\s*'([a-z_]+)'"), '_t'),
    (re.compile(r"\btemper\(\s*[A-Za-z_]\w*\s*,\s*'([a-z_]+)'"),    'temper'),
    (re.compile(r"\bbias\(\s*[A-Za-z_]\w*\s*,\s*'([a-z_]+)'"),      'bias'),
    (re.compile(r"\bgate\(\s*[A-Za-z_]\w*\s*,\s*'([a-z_]+)'"),      'gate'),
    (re.compile(r"\bcalc_noise\(\s*[A-Za-z_]\w*\s*,\s*'([a-z_]+)'"), 'noise'),
    (re.compile(r"\bstreet_concept\(\s*'([a-z_]+)'"),               'street'),
    (re.compile(r"""\[\s*'(aggr|bluff|gamble|icm|tilt|tight)'\s*\]"""), '별칭'),
    (re.compile(r"""\.get\(\s*'(aggr|bluff|gamble|icm|tilt|tight)'"""), '별칭'),
]


def files():
    for f in sorted(os.listdir(D)):
        if f.endswith('.py') and not any(f.startswith(s) for s in SKIP):
            yield f


def enclosing(lines, i):
    """i 번째 줄을 감싸는 최상위 def 이름."""
    for j in range(i, -1, -1):
        m = re.match(r'def (\w+)\(', lines[j])
        if m:
            return m.group(1)
    return '<module>'


def _street_expand():
    """street_concept 의 base -> 구체 개념. wirecheck 와 같은 방식으로 푼다."""
    txt = open(os.path.join(D, 'persona.py'), encoding='utf-8').read()
    m = re.search(r"def street_concept.*?m = \{(.*?)\n    \}", txt, re.S)
    out = {}
    if m:
        for a_, b_, c_ in re.findall(r"\('(\w+)'\s*,\s*'(\w+)'\)\s*:\s*'(\w+)'",
                                     m.group(1)):
            out.setdefault(a_, []).append(c_)
    return out


STREET = _street_expand()


def collect():
    hits = defaultdict(list)          # axis -> [(file, line, func, kind, text)]
    for f in files():
        path = os.path.join(D, f)
        lines = open(path, encoding='utf-8').read().splitlines()
        for i, ln in enumerate(lines):
            s = ln.split('#')[0]
            for pat, kind in PATS:
                for name in pat.findall(s):
                    ax = ALIAS.get(name, name)
                    # street_concept('cbet', st) 는 cbet_flop/barrel_turn/
                    # barrel_river 셋 다의 사용처다. 풀어서 각각에 단다.
                    for real in (STREET.get(ax, [ax]) if kind == 'street' else [ax]):
                        hits[real].append((f, i+1, enclosing(lines, i), kind, ln.strip()))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--axis', default=None)
    ap.add_argument('--min', type=int, default=0, help='이 건수 이상만 요약에 표시')
    a = ap.parse_args()
    hits = collect()

    if a.axis:
        rows = hits.get(a.axis, [])
        print('# %s — 사용처 %d곳\n' % (a.axis, len(rows)))
        cur = None
        for f, ln, fn, kind, txt in rows:
            if (f, fn) != cur:
                cur = (f, fn)
                print('\n%s  %s()' % (f, fn))
            print('  %5d  [%-6s] %s' % (ln, kind, txt[:110]))
        return

    print('# 성향 축 사용처 전수 — 파일:함수 단위\n')
    print('%-20s %5s  %s' % ('축', '건수', '읽히는 함수 (파일)'))
    for ax in sorted(hits, key=lambda k: -len(hits[k])):
        rows = hits[ax]
        if len(rows) < a.min:
            continue
        fns = OrderedDict()
        for f, ln, fn, kind, txt in rows:
            fns.setdefault('%s:%s' % (f.replace('.py', ''), fn), 0)
            fns['%s:%s' % (f.replace('.py', ''), fn)] += 1
        s = '  '.join('%s×%d' % (k, v) if v > 1 else k for k in fns for v in [fns[k]])
        print('%-20s %5d  %s' % (ax, len(rows), s[:150]))


if __name__ == '__main__':
    main()
