"""고친 버그가 다시 살아났는지 검사한다.

    python3 tools/fixed_bugs.py

**regress.py 와 다르다.** regress 는 지문 대조라 동작이 조금이라도 바뀌면
깨진다 — 리팩터용이다. 여기는 '고쳤던 증상이 여전히 안 나오는가'만 본다.
동작을 의도적으로 바꾸는 수정을 해도, 과거에 고친 것들은 그대로여야 한다.

수정 하나가 다른 수정을 되돌리는 일이 실제로 있었다:
리버 사이즈를 열었더니 예산 개념이 없어 3배럴이 생겼고, 예산 카운터로
막았다. 그런 연쇄를 놓치지 않으려면 고칠 때마다 전부 돌려야 한다.

각 검사는 **추정하지 않는다.** 해당 함수를 직접 호출해 반환값을 센다.
새 버그를 고칠 때마다 여기에 한 항목씩 추가할 것.
"""
import sys, os, json, random, collections

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import plan as PL          # noqa: E402
import preflop as PF       # noqa: E402
import persona as PS       # noqa: E402

N = 300
FAILS = []


def report(name, ok, detail):
    print('  [%s] %-46s %s' % ('OK' if ok else '재발', name, detail))
    if not ok:
        FAILS.append(name)


def _prof(seed=11):
    return PS.make_player(random.Random(seed), field_quality=0.6, pid=1)


def check_river_budget():
    """639bae2 — value_2street 이 리버에 못 치던 문제 + 3배럴 방지."""
    prof = _prof()
    board = ['Ad', '9c', '4h', '2s', '7d']
    def run(state):
        c = 0
        for s in range(N):
            if PL.decide_size(prof, ['Ks', 'Kd'], board, 'river', 'value_2street',
                              0.93, [], [], 10000, 40000, random.Random(s),
                              plan_state=state) > 0:
                c += 1
        return c
    left = run({'plan': 'value_2street', 'plan_since': 'turn', 'bet_streets': []})
    spent = run({'plan': 'value_2street', 'plan_since': 'flop',
                 'bet_streets': ['flop', 'turn']})
    report('리버 예산 남으면 친다', left > N*0.8, '%d/%d 벳' % (left, N))
    report('리버 예산 소진이면 안 친다', spent == 0, '%d/%d 벳' % (spent, N))


def check_open_form_cliff():
    """ba3a98b — open_form 의 crude 0/1 계단(27bb 78% -> 28bb 1.5%)."""
    prof = _prof(3)
    prof['concepts']['spr'] = 2.5          # aware 를 낮춰 crude 가 지배하게
    vals = []
    for bb in range(20, 40, 2):
        c = sum(1 for s in range(N)
                if PF.open_decision(prof, 'SB', bb, ['7h', '8h'],
                                    random.Random(s), seats=8,
                                    ante=True)[0] == 'shove')
        vals.append((bb, 100.0*c/N))
    jump = max(abs(vals[i+1][1] - vals[i][1]) for i in range(len(vals)-1))
    report('오픈 형태에 스택 절벽 없음', jump < 30.0,
           '최대 인접 변화 %.1f%%p' % jump)


def check_allin_no_reraise_mult():
    """dff0ddc — 올인 대면에 3벳 배수를 곱해 통째로 올인하던 문제."""
    prof = _prof(5)
    c = collections.Counter()
    for s in range(N):
        a = PF.defend_decision(prof, 'CO', 'LJ', ['8c', '8h'], 22.0, 22.0, 0,
                               random.Random(s), stack_bb=100.0,
                               opener_allin=True)
        c[a[0]] += 1
    report('올인 대면에 오버올인 안 함', c['shove'] == 0,
           'shove %d / 3bet %d / call %d / fold %d'
           % (c['shove'], c['3bet'], c['call'], c['fold']))


def check_trap_taste():
    """ba3a98b — 취향 축 분화와 공부 수렴."""
    def mk(taste, study):
        p = _prof()
        p = dict(p)
        p['temper'] = dict(p['temper']); p['latent'] = dict(p['latent'])
        p['concepts'] = dict(p['concepts'])
        p['temper']['slowplay_taste'] = taste
        p['latent']['study'] = study
        p['concepts']['trap'] = 7.0
        p['concepts']['checkraise_flop'] = 7.0
        return p
    def p_of(taste, study):
        p = mk(taste, study)
        return PL.trap_judgment(p, None, 5.0, 0.15, 0, 'flop', 0.0,
                                lambda c: PS.sk(p, c)/3.33)[0]
    lo_hide, lo_fast = p_of(9.0, 2.5), p_of(1.0, 2.5)
    hi_hide, hi_fast = p_of(9.0, 8.0), p_of(1.0, 8.0)
    report('공부 낮으면 취향대로 갈린다', lo_hide > lo_fast*2.0,
           '숨김 %.3f vs 속공 %.3f' % (lo_hide, lo_fast))
    report('공부 높으면 취향이 수렴한다', abs(hi_hide - hi_fast) < 0.03,
           '숨김 %.3f vs 속공 %.3f' % (hi_hide, hi_fast))


def check_empty_range_guard():
    """ba3a98b — adjust_range_by_history 가 빈 레인지에서 터지던 것."""
    import runner as RU
    class _Dyn:
        def shown(self, seat): return [['Ah', 'Kh'], ['Qs', 'Js'], ['Td', '9d']]
    try:
        RU.adjust_range_by_history([], _Dyn(), 1, ['2c', '7d', '9s'], dead=set())
        report('빈 레인지에서 안 터진다', True, '예외 없음')
    except Exception as e:
        report('빈 레인지에서 안 터진다', False, '%s: %s' % (type(e).__name__, e))


def main():
    print('고친 버그 재발 검사 (각 %d회, 실제 함수 호출)' % N)
    print()
    for fn in (check_river_budget, check_open_form_cliff,
               check_allin_no_reraise_mult, check_trap_taste,
               check_empty_range_guard):
        try:
            fn()
        except Exception as e:
            report(fn.__name__, False, '검사 자체가 터짐 %s: %s'
                   % (type(e).__name__, e))
    print()
    if FAILS:
        print('재발 %d건: %s' % (len(FAILS), ', '.join(FAILS)))
        sys.exit(1)
    print('재발 없음')


if __name__ == '__main__':
    main()
