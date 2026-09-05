"""STEP 5-B 경계조건 탐침. **수정 없이 관찰만.**

    python3 tools/edge_probe.py

고쳤지만 실전에서 한 번도 밟지 않은 경로가 있다. 여러 시드를 돌려
각 경로가 실제로 발생하는지 세고, 발생하면 그때의 상태를 남긴다.

  1 plan_since 승계   board_changed → revise_plan → make_plan
  2 _no_bite          트랩을 걸었는데 상대가 안 침 → 모드만 종료
  3 다중 액션          한 스트리트 2회 이상 (known issue B 도 같이 관찰)
  4 예산 소진          budget_left == 0 인데 저항이 옴
  5 board_changed     플러시 완성·페어링
"""
import sys, os, json, collections

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import runner as RU   # noqa: E402
import plan as PL     # noqa: E402
import tourney as T   # noqa: E402

SEEDS = tuple(range(31001, 31013))
HANDS = 45
HIT = collections.Counter()
CASES = collections.defaultdict(list)


def install():
    _rev = RU.revise_plan

    def rev(state, hero, board, my_range, opp_range, profile, pot, stack,
            street, seed, n_opp, behind, prev_board):
        changed = RU.board_changed(prev_board, board)
        st = _rev(state, hero, board, my_range, opp_range, profile, pot, stack,
                  street, seed, n_opp, behind, prev_board)
        if changed:
            HIT['board_changed'] += 1
            keep = st.get('plan_since')
            prev_since = (state or {}).get('plan_since')
            ok = (keep is not None)
            HIT['plan_since_kept' if ok else 'plan_since_LOST'] += 1
            if len(CASES['board_changed']) < 6:
                CASES['board_changed'].append({
                    'street': street, 'board': ''.join(board or []),
                    'prev_board': ''.join(prev_board or []),
                    'plan_before': (state or {}).get('plan'),
                    'plan_after': st.get('plan'),
                    'since_before': prev_since, 'since_after': keep,
                    'goal': st.get('plan_goal'), 'mode': st.get('plan_mode')})
        return st
    RU.revise_plan = rev
    PL._RU = RU


def main():
    install()
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
            ints = getattr(h, 'intents', None) or []
            # 2) _no_bite — 트랩이었다가 모드 종료
            for k, v in (getattr(h, 'plans', {}) or {}).items():
                if v.get('_no_bite'):
                    HIT['no_bite'] += 1
                    if len(CASES['no_bite']) < 6:
                        CASES['no_bite'].append({
                            'plan': v.get('plan'), 'goal': v.get('plan_goal'),
                            'mode': v.get('plan_mode'),
                            'no_bite': v.get('_no_bite')})
            # 3) 다중 액션
            per = collections.Counter()
            for i in ints:
                if i.get('street') != 'preflop':
                    per[(i['seat'], i['street'])] += 1
            for kk, c in per.items():
                if c >= 2:
                    HIT['multi_action'] += 1
                    rows = [i for i in ints
                            if i['seat'] == kk[0] and i['street'] == kk[1]]
                    same = (len({(r.get('nut_adv'), r.get('range_adv'))
                                 for r in rows}) == 1)
                    HIT['multi_metric_same' if same else 'multi_metric_diff'] += 1
                    if len(CASES['multi_action']) < 6:
                        CASES['multi_action'].append({
                            'street': kk[1], 'n': c,
                            'intents': [r.get('intent_act') for r in rows],
                            'resps': [r.get('response_act') for r in rows],
                            'nut': [r.get('nut_adv') for r in rows],
                            'adv': [r.get('range_adv') for r in rows]})
            # 4) 예산 소진 + 저항
            for i in ints:
                if i.get('street') == 'preflop':
                    continue
                pl = i.get('plan') or ''
                if pl in PL.BUDGET and (i.get('tocall') or 0) > 0:
                    st_ = {'plan': pl, 'plan_since': i.get('plan_since'),
                           'bet_streets': []}
                    HIT['budget_response'] += 1

    print('경계조건 발생 횟수 (%d시드 x %d핸드)' % (len(SEEDS), HANDS))
    for k in ('board_changed', 'plan_since_kept', 'plan_since_LOST',
              'no_bite', 'multi_action', 'multi_metric_same',
              'multi_metric_diff', 'budget_response'):
        print('  %-22s %d' % (k, HIT[k]))
    for name in ('board_changed', 'no_bite', 'multi_action'):
        if not CASES[name]:
            continue
        print()
        print('[%s] 사례' % name)
        for c in CASES[name][:4]:
            print('   ' + json.dumps(c, ensure_ascii=False))


if __name__ == '__main__':
    main()
