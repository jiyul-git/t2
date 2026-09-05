"""STEP 6 전후 비교 — my_range 역할 매핑. production 미수정.

    python3 tools/role_baseline.py <출력>

A 레인지 생성   pf_role / 사용된 role / my·opp 길이
B 판단 입력     nut_adv / range_adv / rel / eq
C 최종 행동     action / amt / plan / goal / mode  (액션 해시 포함)
"""
import sys, os, json, hashlib, collections

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import ranges as R      # noqa: E402
import session as SE    # noqa: E402
import tourney as T     # noqa: E402

SEEDS = tuple(range(41001, 41009))
HANDS = 40
RANGE_ROWS = []


SIZES = {}


def install():
    _pr = R.preflop_range
    import plan as PL
    _up = PL.update_plan

    def pr(prof_type, pos, action, bb, dead, **k):
        out = _pr(prof_type, pos, action, bb, dead, **k)
        RANGE_ROWS.append({'pos': pos, 'role': action, 'n': len(out)})
        return out

    def up(state, hero, board, my_range, opp_range, profile, pot, stack,
           street, *a, **k):
        SIZES[(street, ''.join(board or []))] = (len(my_range or []),
                                                 len(opp_range or []))
        return _up(state, hero, board, my_range, opp_range, profile, pot,
                   stack, street, *a, **k)
    R.preflop_range = SE.R.preflop_range = pr
    PL.update_plan = up


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'role_before.json'
    install()
    sigs, rows = [], []
    empties = collections.Counter()
    for sd in SEEDS:
        t = T.Tournament(entries=40, seed=sd, fmt='standard', hero_seat=7)
        n = 0
        while n < HANDS:
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            g = 0
            while st and not st.get('done') and g < 250:
                st = t.submit('fold')
                g += 1
            n += 1
            h = getattr(t.run, 'h', None)
            res = getattr(t.run, 'result', None) or {}
            log = getattr(t.run, 'full_log', []) or []
            sigs.append('%d|%d|%s|%s|%s' % (
                sd, n, ''.join((h.board or []) if h else []),
                ';'.join('%s%s%s' % (a[0][:2], a[1], a[2]) for a in log),
                res.get('pot')))
            pf = getattr(h, 'pf_seed', {}) or {}
            for i in (getattr(h, 'intents', None) or []):
                if i.get('street') == 'preflop':
                    continue
                rows.append({
                    'seed': sd, 'hand': n, 'street': i['street'],
                    'seat': i['seat'], 'idx': i.get('idx'),
                    'pos': (h.pos or {}).get(i['seat']),
                    'pf_role': (pf.get(i['seat']) or {}).get('pf_role'),
                    'pf_act': (pf.get(i['seat']) or {}).get('pf_act'),
                    'nut_adv': i.get('nut_adv'), 'range_adv': i.get('range_adv'),
                    'rel': i.get('rel'), 'eq': i.get('eq'),
                    'action': i.get('action'), 'amt': i.get('amt'),
                    'plan': i.get('plan'), 'goal': i.get('plan_goal'),
                    'mode': i.get('plan_mode'),
                    'my_n': SIZES.get((i['street'],
                                       ''.join(h.board[:{'flop': 3, 'turn': 4,
                                                         'river': 5}[i['street']]]
                                               if h.board else [])), (None, None))[0],
                    'opp_n': SIZES.get((i['street'],
                                        ''.join(h.board[:{'flop': 3, 'turn': 4,
                                                          'river': 5}[i['street']]]
                                                if h.board else [])), (None, None))[1],
                })
    for r in RANGE_ROWS:
        if r['n'] == 0:
            empties[(r['pos'], r['role'])] += 1
    ah = hashlib.sha1('\n'.join(sigs).encode()).hexdigest()[:16]
    json.dump({'seeds': list(SEEDS), 'action_hash': ah, 'rows': rows,
               'range_calls': len(RANGE_ROWS),
               'empty': {'%s/%s' % k: v for k, v in empties.items()}},
              open(out, 'w'), ensure_ascii=False, indent=1)
    print('%s  %d시드 / 기록 %d건' % (os.path.basename(out), len(SEEDS), len(rows)))
    print('  액션 해시        %s' % ah)
    print('  preflop_range 호출 %d회' % len(RANGE_ROWS))
    print('  빈 레인지 반환    %s' % (dict(
        ('%s/%s' % k, v) for k, v in empties.items()) or '없음'))
    byrole = collections.Counter((r['pos'], r['role']) for r in RANGE_ROWS)
    print('  BB 관련 role 분포:')
    for k, v in sorted(byrole.items()):
        if k[0] == 'BB':
            print('     %s / %-6s %d회' % (k[0], k[1], v))


if __name__ == '__main__':
    main()
