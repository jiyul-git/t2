#!/usr/bin/env python3
"""A5 `else:` 의 행동 영향을 regress 레시피에서 A/B 로 잰다. 읽기 전용.

`regress.py check` 가 전 시드 지문 일치를 냈는데, baseline 동결 rev(60e16d8,
9/21)는 A5 수정(951939e, 9/22)보다 **앞선다**. 그리고 도달성 계측에서
block 선택이 **1건** 있었다(옛 코드가 굴림을 더 쓰던 경우). 경로가 열려
있는데 지문이 같으므로 설명이 필요하다.

옛 커밋 전체(951939e^)를 가져오면 그 뒤 다른 모듈 변경과 안 맞는다.
그래서 **현재 plan.py 에서 A5 diff 만 역적용**한 변형을 만든다 —
`else:` 를 없애고 머징 체인을 4칸 내어쓴다. 두 변형의 유일한 차이가
A5 그 자체가 되도록.

각 변형은 **별도 프로세스**에서 돈다 (대회 간 캐시 이월이 있으므로
같은 프로세스에서 두 번 돌리면 두 번째가 오염된다).

  python3 tools/a5_fingerprint_ab.py            # A/B 실행
  python3 tools/a5_fingerprint_ab.py --variant pre --emit   # 내부용

production 무수정.
"""
import argparse
import collections
import hashlib
import os
import subprocess
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)

HEAD_MARK = "        if sk('blockbet') >= 1 and rng.random() < block_p:"
TAIL_MARK = "    elif outs >= 8 and to_act_behind <= 1"
ELSE_LINE = "        else:\n"
SEEDS = list(range(3000, 3006))
HANDS = 30


def make_pre_a5(src):
    """A5 diff 역적용: else: 제거 + 머징 체인 dedent 4."""
    a = src.index(HEAD_MARK)
    b = src.index(TAIL_MARK, a)
    seg = src[a:b]
    if ELSE_LINE not in seg:
        raise SystemExit('else: 를 못 찾았다 — A5 수정이 적용돼 있지 않다')
    head, rest = seg.split(ELSE_LINE, 1)
    out = []
    for ln in rest.split('\n'):
        if ln.startswith('            '):
            out.append(ln[4:])          # 4칸 내어쓰기
        elif ln.strip() == '':
            out.append('')
        else:
            raise SystemExit('예상 밖 들여쓰기: %r' % ln)
    return src[:a] + head + '\n'.join(out) + src[b:]


def fingerprint():
    """regress.fingerprint() 와 동일한 레시피. 시드별 해시 + block 계측."""
    import tourney as T
    import plan as PL
    cnt = collections.Counter()
    ev = []                    # block 이 걸린 자리의 최종 의도
    _omk = PL.make_plan
    _oai = PL.attach_intent

    def wrap_ai(st, hero, board, my_range, opp_range, profile, pot, stack,
                street, rng, n_opp, to_act_behind, oop, initiative,
                opp_est=None, **kw):
        out = _oai(st, hero, board, my_range, opp_range, profile, pot, stack,
                   street, rng, n_opp, to_act_behind, oop, initiative,
                   opp_est, **kw)
        why = list((out or {}).get('why') or [])
        if any('블락벳으로 가격 통제' in str(x) and str(x).startswith(street + ': ')
               for x in why):
            it = ((out or {}).get('intents') or {}).get(street) or {}
            ev.append({'street': street, 'plan': (out or {}).get('plan'),
                       'act': it.get('act'), 'size': it.get('size'),
                       'pid': profile.get('id')})
        return out

    def wrap(hero, board, my_range, opp_range, profile, pot, stack, street,
             **kw):
        st = _omk(hero, board, my_range, opp_range, profile, pot, stack,
                  street, **kw)
        if '블락벳으로 가격 통제' in ' | '.join(st.get('why') or []):
            cnt['block_msg'] += 1
        if st.get('plan') == 'block':
            cnt['plan_block'] += 1
        return st
    PL.make_plan = wrap
    PL.attach_intent = wrap_ai
    per_seed = {}
    try:
        for sd in SEEDS:
            t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                             seed=sd, hands_per_level=200)
            rows = ['q=%.3f|a=%.2f' % (t.field_q, t.aggr_bias)]
            for _ in range(HANDS):
                if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                    break
                st = t.next_hand()
                guard = 0
                while st and not st.get('done') and guard < 200:
                    st = t.submit('fold')
                    guard += 1
                log = getattr(t.run, 'full_log', []) or []
                rows.append(';'.join('%s:%s:%s:%s' % x for x in log))
                t.finish_hand()
            per_seed[sd] = hashlib.sha256(
                '\n'.join(rows).encode()).hexdigest()[:16]
    finally:
        PL.make_plan = _omk
        PL.attach_intent = _oai
    return per_seed, dict(cnt), ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', choices=('cur', 'pre'), default=None)
    ap.add_argument('--emit', action='store_true')
    a = ap.parse_args()

    if a.variant:                         # 자식 프로세스
        import json
        ps, cnt, ev = fingerprint()
        print('@@RESULT@@' + json.dumps({'seeds': ps, 'cnt': cnt, 'ev': ev}))
        return 0

    import json
    import shutil
    import tempfile
    src = open(os.path.join(D, 'plan.py'), encoding='utf-8').read()
    pre = make_pre_a5(src)
    compile(pre, 'plan_pre_a5.py', 'exec')        # 문법 확인
    tmp = tempfile.mkdtemp(prefix='a5ab_')
    try:
        # pre 변형: 임시 폴더에 plan.py 를 두고 sys.path 최우선으로 올린다
        open(os.path.join(tmp, 'plan.py'), 'w', encoding='utf-8').write(pre)
        out = {}
        for name, extra in (('cur', None), ('pre', tmp)):
            env = dict(os.environ)
            if extra:
                env['PYTHONPATH'] = extra + os.pathsep + env.get('PYTHONPATH', '')
            r = subprocess.run([sys.executable, os.path.abspath(__file__),
                                '--variant', name],
                               capture_output=True, text=True, env=env,
                               cwd=D, timeout=2400)
            line = [x for x in r.stdout.splitlines()
                    if x.startswith('@@RESULT@@')]
            if not line:
                print('%s 실행 실패:\n%s\n%s' % (name, r.stdout[-2000:],
                                              r.stderr[-2000:]))
                return 1
            out[name] = json.loads(line[0][len('@@RESULT@@'):])
        print('# A5 else: 의 행동 영향 — regress 레시피 A/B')
        print('  cur = 현재 plan.py (A5 적용)   pre = A5 diff 역적용\n')
        print('  block 메시지 / plan==block')
        for k in ('cur', 'pre'):
            c = out[k]['cnt']
            print('    %-4s  block_msg %d   plan_block %d'
                  % (k, c.get('block_msg', 0), c.get('plan_block', 0)))
        print('\n  block 이 걸린 자리의 최종 의도')
        for k in ('cur', 'pre'):
            e = out[k].get('ev') or []
            if not e:
                print('    %-4s  (attach_intent 에서 현재 스트리트 block 흔적 없음)' % k)
            for r in e:
                print('    %-4s  pid %s  %s  plan=%s  act=%s  size=%s'
                      % (k, r['pid'], r['street'], r['plan'], r['act'],
                         r['size']))
        print('\n  시드별 지문')
        diff = []
        for sd in map(str, SEEDS):
            x, y = out['cur']['seeds'][sd], out['pre']['seeds'][sd]
            same = (x == y)
            if not same:
                diff.append(sd)
            print('    %s  cur %s  pre %s  %s'
                  % (sd, x, y, '일치' if same else '**불일치**'))
        print()
        if diff:
            print('  A5 는 이 레시피에서 행동을 바꾼다. 불일치 시드: %s'
                  % ', '.join(diff))
        else:
            print('  A5 는 이 레시피에서 행동을 **바꾸지 않는다**.')
            print('  block 이 선택되긴 하지만(위 계측), 그 자리에서 옛 코드의')
            print('  덮어쓰기 결과와 최종 full_log 가 같다는 뜻이다.')
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    raise SystemExit(main())
