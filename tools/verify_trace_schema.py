#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""결정 기록 스키마 계약 검사 (A7). 읽기 전용.

  python3 tools/verify_trace_schema.py
  python3 tools/verify_trace_schema.py --archives '*.jsonl'

production 을 import 하되 **호출하지 않는다.** 아카이브는 **읽기만** 한다 —
migration 하지 않고 원본을 고치지 않는다.

무엇을 검사하는가
-----------------
  A  현재 intent producer 키 집합      session.py 를 AST 로 읽어 고정
  B  plan trace producer 키 집합       plan.py 의 _trace 호출을 AST 로 읽어 고정
  C  logkeys 의미별 접근자 계약        음성 대조 포함
  D  아카이브 세대                     legacy / current 를 구분해서 읽는다
  E  없음 처리                         없는 키가 0/False 로 바뀌지 않는가
  F  레코드 종류별 같은 이름 충돌      기록만 한다 (rename 하지 않는다)

**"신규 키가 없다"를 실패로 보지 않는다.** 과거 기록에 없던 의미를 reader 가
발명하지 않는 것이 목표이지, 과거 기록을 현재 스키마에 맞추는 것이 아니다.

음성 대조가 먼저다
------------------
"위반 0" 이 검출기가 죽어서 나온 0 인지 구분할 수 없으면 이 검사는 아무것도
보증하지 않는다. `tools/reachability.py` 의 selfcheck, `verify_tool_contracts`
의 selftest 와 같은 원칙이다.
"""
import argparse, ast, collections, glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import logkeys as LK

FAILS = []


def ok(name, cond, detail=''):
    print('  %-22s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
    if not cond:
        FAILS.append(name)


# ---------------------------------------------------------------- A · B

# intent 레코드가 만들어지는 곳. 이 줄 번호의 dict 리터럴만 intent 다 —
# 같은 파일의 reads_log·audit 경보는 **다른 레코드**이고 키를 일부 공유한다.
INTENT_SITES = ('h.intents.append', '_slot.update')

# dict 리터럴 밖에서 붙는 키. AST 가 못 잡으므로 여기 적어 둔다.
INTENT_EXTRA = {'trace': 'session.py 가 계획의 trace 중 이 스트리트분만 붙인다'}

# producer 가 있으나 저장소 안에 소비자가 없는 키. 삭제 후보가 아니다.
PROVENANCE_ONLY = {
    'eq_seed':       '몬테카를로 시드. eq 재현용',
    'eq_sims':       '시뮬 횟수. eq 의 분산 해석용',
    'my_range_n':    '내 레인지 콤보 수',
    'my_range_sig':  '내 레인지 서명',
    'opp_range_n':   '상대 레인지 콤보 수',
    'pre_clamp':     '클램프 전 사이즈',
    'response_src':  '대응 판단의 사유. trace 의 why 를 옮겨 담은 것',
}

# 레코드 종류별로 이름이 같고 뜻이 다른 키. **이번 단계에서는 기록만 한다.**
NAME_COLLISIONS = {
    'why': [('plan/intent', 'list[str]  — 스트리트 접두사가 붙은 사유 목록'),
            ('dev/trace',   'str        — 한 줄 사유')],
    'n':   [('reads_log',   '관측 핸드 수'),
            ('estimate',    '추정 표본 수')],
    'oop': [('아카이브 intent', '절대식 (= oop_legacy_abs)'),
            ('harness 상황 dict', 'make_plan 의 입력 필드. 로그 키가 아니다')],
    'street': [('intent', '그 결정이 일어난 스트리트'),
               ('trace',  '그 판단이 일어난 스트리트'),
               ('reads_log', '관측이 일어난 스트리트')],
}


def producer_keys(path, sites):
    """dict 리터럴에서 키를 뽑는다. 호출 표현식 문자열로 자리를 고른다."""
    src = open(os.path.join(ROOT, path), encoding='utf-8').read()
    tree = ast.parse(src)
    out = collections.OrderedDict()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        try:
            label = ast.unparse(node.func)
        except Exception:
            continue
        if label not in sites or not node.args:
            continue
        arg = node.args[0]
        if not isinstance(arg, ast.Dict):
            continue
        for k in arg.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                out.setdefault(k.value, node.lineno)
    return out


def trace_keys(path):
    """plan.py 의 _trace(...) 키워드. kind 별로 모은다."""
    src = open(os.path.join(ROOT, path), encoding='utf-8').read()
    tree = ast.parse(src)
    out = collections.OrderedDict()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == '_trace'):
            continue
        kind = None
        if len(node.args) >= 3 and isinstance(node.args[2], ast.Constant):
            kind = node.args[2].value
        if kind is None:
            continue          # 전달 호출(_trace(st, street, kind, **kw))
        ks = out.setdefault(kind, set())
        ks.update({'street', 'kind'})
        ks.update(k.arg for k in node.keywords if k.arg)
    return out


# ---------------------------------------------------------------- C · E

# 음성 대조. 사용자가 지정한 여섯 가지를 그대로 넣는다.
ACCESSOR_CASES = [
    ('1-빈레코드', {},
     {'field': None, 'vs_aggr': None, 'legacy': None}),
    ('2-legacy True', {'oop': True},
     {'field': None, 'vs_aggr': None, 'legacy': True}),
    ('3-legacy False', {'oop': False},
     {'field': None, 'vs_aggr': None, 'legacy': False}),
    ('4-current 셋', {'oop_field': False, 'oop_vs_aggr': None,
                      'oop_legacy_abs': True},
     {'field': False, 'vs_aggr': None, 'legacy': True}),
    ('5-충돌', {'oop': False, 'oop_legacy_abs': True},
     {'field': None, 'vs_aggr': None, 'legacy': True}),
    ('6-legacy 전용', {'oop': True, 'street': 'flop', 'plan': 'giveup'},
     {'field': None, 'vs_aggr': None, 'legacy': True}),
]


def check_accessors():
    print('=== C/E. logkeys 의미별 접근자 (음성 대조) ===')
    for name, rec, want in ACCESSOR_CASES:
        got = {'field': LK.oop_field_of(rec),
               'vs_aggr': LK.oop_vs_aggr_of(rec),
               'legacy': LK.oop_legacy_abs_of(rec)}
        good = all(got[k] is want[k] for k in want)
        ok(name, good, '%s' % ({k: got[k] for k in ('field', 'vs_aggr', 'legacy')}))
    # False 를 missing 으로 취급하면 안 된다 — 별도 단언
    ok('False≠missing', LK.oop_legacy_abs_of({'oop': False}) is False,
       'legacy False 가 None 으로 접히지 않는다')
    ok('없음→0금지', LK.oop_field_of({'oop': True}) is None,
       'legacy 만 있는 레코드에서 field 를 발명하지 않는다')
    # 충돌 진단
    c = LK.oop_conflict({'oop': False, 'oop_legacy_abs': True})
    ok('충돌 진단', c == (True, False), '%s' % (c,))
    ok('충돌 없음', LK.oop_conflict({'oop': True, 'oop_legacy_abs': True}) is None)
    # 세대 판정
    ok('세대 legacy', LK.generation_of({'oop': True}) == 'legacy')
    ok('세대 current', LK.generation_of({'oop_field': False}) == 'current')
    ok('세대 unknown', LK.generation_of({'plan': 'giveup'}) == 'unknown')
    # deprecated 별칭이 절대식으로 고정됐는가
    ok('deprecated 별칭', LK.oop_of({'oop': True}) is True
       and LK.oop_of({'oop_field': True}) is None,
       'oop_of 는 oop_legacy_abs_of 와 같다')


# 이 둘만 generic 이름을 담아도 된다 — 정의한 쪽과 검사하는 쪽이다.
# 목록으로 두지 않고 두 경로로 못박는다. 넓히면 검사가 의미를 잃는다.
_SELF_EXEMPT = ('tools/logkeys.py', 'tools/verify_trace_schema.py')


def check_no_generic_callers():
    """저장소 안에서 generic 접근자를 부르는 곳이 0 인가.

    generic 이름을 담아도 되는 파일은 둘뿐이다 — 정의하는 `logkeys` 와
    그것을 시험하는 이 파일. 그 둘을 빼고 한 곳이라도 나오면 FAIL 이다.
    """
    import re
    pat = re.compile(r'\b(oop_of|oop_label)\b')
    exempt = {os.path.abspath(os.path.join(ROOT, x)) for x in _SELF_EXEMPT}
    bad = []
    for d, _, fs in os.walk(ROOT):
        if any(x in d for x in ('/.git', '__pycache__')):
            continue
        for f in fs:
            if not f.endswith('.py'):
                continue
            fp = os.path.join(d, f)
            if os.path.abspath(fp) in exempt:
                continue
            try:
                src = open(fp, encoding='utf-8').read()
            except Exception:
                continue
            if pat.search(src):
                bad.append(os.path.relpath(fp, ROOT))
    ok('generic caller 0', not bad,
       (', '.join(bad) if bad else '면제 2개 제외: %s' % ', '.join(_SELF_EXEMPT)))
    # 면제가 조용히 넓어지지 않게, 면제 파일이 실제로 존재하는지도 본다.
    ok('면제 경로 유효', all(os.path.exists(x) for x in exempt))


# ---------------------------------------------------------------- D

NEW_OOP = ('oop_field', 'oop_vs_aggr', 'oop_legacy_abs')


def scan_archives(patterns, limit=4000):
    rows = []
    for pat in patterns:
        for f in sorted(glob.glob(os.path.join(ROOT, pat))):
            if not os.path.getsize(f):
                continue
            gens = collections.Counter()
            keys = set()
            nrec = 0
            invented = 0
            conflicts = 0
            bad_line = 0
            for line in open(f, encoding='utf-8', errors='replace'):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    bad_line += 1
                    continue
                if not isinstance(d, dict):
                    continue
                for r in (d.get('intents') or []):
                    if not isinstance(r, dict):
                        continue
                    nrec += 1
                    keys |= set(r)
                    g = LK.generation_of(r)
                    gens[g] += 1
                    # legacy 레코드에서 새 의미가 만들어지면 FAIL
                    if g == 'legacy':
                        if (LK.oop_field_of(r) is not None
                                or LK.oop_vs_aggr_of(r) is not None):
                            invented += 1
                    if LK.oop_conflict(r):
                        conflicts += 1
                    if nrec >= limit:
                        break
                if nrec >= limit:
                    break
            if nrec:
                rows.append({'file': os.path.relpath(f, ROOT), 'records': nrec,
                             'gens': dict(gens), 'invented': invented,
                             'conflicts': conflicts, 'bad_lines': bad_line,
                             'keys': keys})
    return rows


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description='결정 기록 스키마 계약 검사 (A7)')
    ap.add_argument('--archives', action='append', default=None,
                    help='아카이브 glob. 여러 번 줄 수 있다')
    a = ap.parse_args()
    pats = a.archives or ['*.jsonl']

    check_accessors()
    print()
    print('=== C. 저장소 안의 generic 접근자 ===')
    check_no_generic_callers()

    print()
    print('=== A. intent producer 키 ===')
    ik = producer_keys('session.py', INTENT_SITES)
    for k, v in INTENT_EXTRA.items():
        ik.setdefault(k, 0)
    print('  %d개' % len(ik))
    print('  ' + ' '.join(sorted(ik)))
    ok('새 OOP 3키 존재', all(k in ik for k in NEW_OOP),
       '없는 것: %s' % [k for k in NEW_OOP if k not in ik])
    ok('generic oop 미생산', 'oop' not in ik,
       '현재 producer 는 generic `oop` 를 쓰지 않는다')

    print()
    print('=== B. plan trace producer 키 ===')
    tk = trace_keys('plan.py')
    for kind in sorted(tk):
        print('  %-12s %s' % (kind, ' '.join(sorted(tk[kind]))))
    ok('trace kind 존재', bool(tk), '%d종' % len(tk))

    print()
    print('=== provenance only (소비자 없음 — 삭제 후보 아님) ===')
    for k in sorted(PROVENANCE_ONLY):
        mark = '' if k in ik else '   (producer 없음!)'
        print('  %-14s %s%s' % (k, PROVENANCE_ONLY[k], mark))

    print()
    print('=== F. 레코드 종류별 같은 이름 충돌 (기록만) ===')
    for name in sorted(NAME_COLLISIONS):
        print('  %s' % name)
        for rt, mean in NAME_COLLISIONS[name]:
            print('      %-18s %s' % (rt, mean))

    print()
    print('=== D. 아카이브 세대 ===')
    rows = scan_archives(pats)
    ok('아카이브 발견', bool(rows), '%d파일' % len(rows))
    tot_inv = tot_conf = 0
    for r in rows:
        newk = sorted(k for k in NEW_OOP if k in r['keys'])
        print('  %-44s rec=%-5d %s  new=%s'
              % (r['file'], r['records'], r['gens'], newk or '-'))
        tot_inv += r['invented']
        tot_conf += r['conflicts']
        if r['bad_lines']:
            print('      깨진 줄 %d' % r['bad_lines'])
    ok('legacy 에서 발명 0', tot_inv == 0,
       'legacy 레코드에서 field/vs_aggr 이 만들어진 건 %d' % tot_inv)
    print('  충돌(oop vs oop_legacy_abs) %d건 — 진단만' % tot_conf)
    print('  참고: 신규 3키가 아카이브에 없는 것은 **정상**이다.'
          ' 과거에 기록된 적이 없다')

    print()
    if FAILS:
        print('FAIL %d : %s' % (len(FAILS), ', '.join(FAILS)))
        return 1
    print('PASS 스키마 계약 · 의미별 접근자 · 아카이브 세대')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
