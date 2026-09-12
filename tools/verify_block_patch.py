#!/usr/bin/env python3
"""block 복구 패치의 정적·동적 검증. 네 가지를 따로 확인한다.

  1. _blocked=True 인 경로에서 make_plan 이 정말 plan='block' 을 반환하는가
     (반환 이후 _allowed 가 강등하는 것은 별개 층이므로 나눠서 센다)
  2. _blocked=False 인 경우 기존 plan 분포가 정확히 동일한가
  3. rng.random() 호출 순서가 기존과 동일한가
  4. block 외 계획(semibluff/showdown/pot_control/value_*)에 변화가 없는가

2·4 는 A/B 수집물로 확인한다. 핵심 검정은 **접두 동일성**이다 —
한 토너먼트 안에서 block 이 처음 발화하기 전까지의 모든 핸드 기록이
A 와 B 에서 완전히 같아야 한다. 하나라도 다르면 패치가 block 과 무관한
곳을 건드렸다는 뜻이다.

3 은 원본과 패치본을 **서로 다른 모듈로 동시에 적재**해서 같은 인자로
make_plan 을 부르고, random() 호출 열을 그대로 비교한다.

사용:
    python3 tools/verify_block_patch.py <patched_plan.py> A0,A1,.. B0,B1,..
"""
import os, sys, json, random, importlib.util, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class LogRandom(random.Random):
    """random() 호출을 기록하는 Random. 값 자체는 시드대로 나온다."""

    def __init__(self, seed=None):
        super().__init__(seed)
        self.calls = []

    def random(self):
        v = super().random()
        self.calls.append(('random', round(v, 12)))
        return v

    def uniform(self, a, b):
        v = super().uniform(a, b)
        self.calls.append(('uniform', round(v, 12)))
        return v

    def gauss(self, mu, sigma):
        v = super().gauss(mu, sigma)
        self.calls.append(('gauss', round(v, 12)))
        return v

    def choice(self, seq):
        v = super().choice(seq)
        self.calls.append(('choice', str(v)))
        return v


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def street_why(i):
    pre = '%s: ' % i['street']
    return [x[len(pre):] for x in
            (i['why'] if isinstance(i['why'], list) else [i['why']])
            if x.startswith(pre)]


def block_fired(i):
    return any('블락벳으로 가격 통제' in x for x in street_why(i))


def load_paired(paths):
    out = {}
    for p in paths:
        suf = os.path.basename(p).split('_')[-1]
        tno, prev = 0, None
        for l in open(p):
            r = json.loads(l)
            hn = r['hand_no']
            if prev is not None and hn <= prev:
                tno += 1
            prev = hn
            out[(suf, tno, hn)] = r
    return out


def check_1_and_4(B):
    print('=' * 96)
    print('1. _blocked=True 경로가 실제로 block 을 만드는가  (실험군 기록)')
    print('=' * 96)
    fired = [i for r in B.values() for i in r.get('intents', [])
             if i.get('street') == 'flop' and block_fired(i)]
    live = [i for i in fired if i.get('plan') == 'block']
    lost = [i for i in fired if i.get('plan') != 'block']
    print('   플랍 block 발화 %d · plan=="block" %d · 그 외 %d'
          % (len(fired), len(live), len(lost)))
    if lost:
        import persona as PS
        print('   plan 이 block 이 아닌 건 — _allowed(1491) 강등인지 확인')
        print('     _allowed: blockbet 원개념 s<1.5 무조건 / 1.5<=s<3.5 확률 (s-1.5)/2')
        for i in lost:
            print('       plan=%-14s (강등 대상은 value_2street)' % i.get('plan'))
        ok = all(i.get('plan') == 'value_2street' for i in lost)
        print('   전부 value_2street 인가: %s  → %s'
              % (ok, '_allowed 강등으로 설명된다' if ok else '**설명되지 않는다**'))
    print()


def check_prefix(A, B):
    print('=' * 96)
    print('2·4. 접두 동일성 — block 이 발화하기 전까지 A 와 B 가 완전히 같은가')
    print('=' * 96)
    print('   토너먼트마다 block 이 처음 발화한 핸드를 찾고, 그 **이전** 핸드들의')
    print('   기록 전체(JSON)가 A·B 에서 같은지 본다. 하나라도 다르면 패치가')
    print('   block 과 무관한 곳을 건드린 것이다.')
    print()
    # 토너먼트별로 묶기
    tours = collections.defaultdict(list)
    for (suf, tno, hn) in set(A) | set(B):
        tours[(suf, tno)].append(hn)
    n_t = n_pref = n_bad = 0
    bad_ex = []
    for t, hns in tours.items():
        n_t += 1
        for hn in sorted(hns):
            k = (t[0], t[1], hn)
            ra, rb = A.get(k), B.get(k)
            if ra is None or rb is None:
                break
            fa = any(block_fired(i) for i in ra.get('intents', []))
            fb = any(block_fired(i) for i in rb.get('intents', []))
            if fa or fb:
                break                       # 여기서부터는 달라도 정상
            n_pref += 1
            if json.dumps(ra, sort_keys=True, ensure_ascii=False) != \
               json.dumps(rb, sort_keys=True, ensure_ascii=False):
                n_bad += 1
                if len(bad_ex) < 3:
                    bad_ex.append(k)
    print('   토너먼트 %d개 · 검사한 접두 핸드 %d개' % (n_t, n_pref))
    print('   기록이 다른 핸드 %d개' % n_bad)
    for k in bad_ex:
        print('      %s' % (k,))
    print('   → %s' % ('깨끗하다. block 발화 전까지 A·B 가 완전히 동일하다.'
                       if n_bad == 0 else '**패치가 block 과 무관한 곳을 바꿨다.**'))
    print()
    return n_bad == 0


def check_rng(patched_path):
    print('=' * 96)
    print('3. rng.random() 호출 순서가 동일한가 — 원본과 패치본을 동시 적재')
    print('=' * 96)
    import plan as P0
    P1 = load_module(patched_path, 'plan_patched')
    import persona as PS

    # eq>=pcz 분기로 들어가고 block 진입 조건(oop·not init·rel 밴드)을 만족하는
    # 인자를 만든다. 시드를 여러 개 돌려 _blocked 가 True/False 인 경우를 모두 본다.
    rows = []
    same = diff = 0
    blocked_seen = 0
    n_block_orig = n_block_patch = 0
    # **block 이 실제로 발화하는 인자여야 검정이 의미가 있다.**
    # 앞선 탐색에서 찾은 조합: oop=True · initiative=False 에서
    # 아래 보드/홀 조합이 rel 0.65~0.68, eq 0.61~0.68 로 eq>=pcz 를 통과하고
    # block 진입 밴드(0.25~0.80)에도 들어간다.
    cases = [(['Ac', '8s'], ['Ts', '8d', '3c']),
             (['Th', '9h'], ['Kh', '9c', '4d']),
             (['Ah', 'Qd'], ['7h', '5s', '2c']),
             (['Qh', 'Jc'], ['Jd', '7c', '3s'])]
    for seed in range(150):
        prof = PS.make_player(random.Random(seed), 0.78, 1)
        for hero, board in cases:
            if set(hero) & set(board):
                continue
            args = dict(hero=hero, board=board, my_range=None, opp_range=None,
                        profile=prof, pot=1000, stack=20000, street='flop',
                        n_opp=1, to_act_behind=0, oop=True, initiative=False)
            r0, r1 = LogRandom(seed), LogRandom(seed)

            def run(mod, lr):
                orig = mod.random.Random
                mod.random.Random = lambda *a, **k: lr
                try:
                    return mod.make_plan(seed=seed, **args)
                finally:
                    mod.random.Random = orig
            try:
                s0 = run(P0, r0)
                s1 = run(P1, r1)
            except Exception:
                continue
            fired = any('블락벳' in x for x in (s1.get('why') or []))
            if fired:
                blocked_seen += 1
                if s0.get('plan') == 'block':
                    n_block_orig += 1
                if s1.get('plan') == 'block':
                    n_block_patch += 1
            if r0.calls == r1.calls:
                same += 1
            else:
                diff += 1
                if len(rows) < 3:
                    for j, (a, b) in enumerate(zip(r0.calls, r1.calls)):
                        if a != b:
                            rows.append((seed, j, a, b)); break
                    else:
                        rows.append((seed, min(len(r0.calls), len(r1.calls)),
                                     len(r0.calls), len(r1.calls)))
    print('   block 이 발화한 호출 %d — 그중 plan=="block" 원본 %d / 패치 %d'
          % (blocked_seen, n_block_orig, n_block_patch))
    if blocked_seen == 0:
        print('   **경고: block 이 한 번도 발화하지 않았다. 이 검정은 공허하다.**')
    print('   비교한 make_plan 호출 %d  (그중 패치본에서 plan=block 이 된 건 %d)'
          % (same + diff, blocked_seen))
    print('   호출 열이 동일 %d · 다름 %d' % (same, diff))
    for s, j, a, b in rows:
        print('      seed %d: %d번째 호출부터 다름  원본 %s / 패치 %s' % (s, j, a, b))
    print('   → %s' % ('rng 소비 순서가 완전히 같다.' if diff == 0
                       else '**rng 소비가 달라졌다.**'))
    print()
    return diff == 0


def main():
    if len(sys.argv) < 4:
        print(__doc__); return
    patched = sys.argv[1]
    A = load_paired(sys.argv[2].split(','))
    B = load_paired(sys.argv[3].split(','))
    check_1_and_4(B)
    ok2 = check_prefix(A, B)
    ok3 = check_rng(patched)
    print('=' * 96)
    print('종합')
    print('=' * 96)
    print('   2·4 접두 동일성 %s' % ('OK' if ok2 else '실패'))
    print('   3  rng 순서      %s' % ('OK' if ok3 else '실패'))


if __name__ == '__main__':
    main()
