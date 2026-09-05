"""STEP 3 전후 비교 — trap 이 어떻게 표현되는가. production 미수정.

    python3 tools/trap_baseline.py <출력>

액션 해시(불변이어야 함)와, trap 이 등장한 핸드의 계획 표현을 함께 남긴다.
"""
import sys, os, json, hashlib
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import tourney as T   # noqa: E402

SEED, HANDS = 26001, 40


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'trap_before.json'
    sigs, traps = [], []
    t = T.Tournament(entries=40, seed=SEED, fmt='standard', hero_seat=7)
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
        sigs.append('%d|%s|%s|%s' % (
            n, ''.join((h.board or []) if h else []),
            ';'.join('%s%s%s' % (a[0][:2], a[1], a[2]) for a in log),
            res.get('pot')))
        seats = set()
        for i in (getattr(h, 'intents', None) or []):
            if i.get('plan') == 'trap' or i.get('plan_mode') == 'trap':
                seats.add(i['seat'])
        for i in (getattr(h, 'intents', None) or []):
            if i['seat'] in seats and i.get('street') != 'preflop':
                traps.append({
                    'hand': n, 'street': i['street'], 'seat': i['seat'],
                    'idx': i.get('idx'), 'plan': i.get('plan'),
                    'goal': i.get('plan_goal'), 'mode': i.get('plan_mode'),
                    'intent_act': i.get('intent_act'),
                    'response_act': i.get('response_act'),
                    'action': i.get('action'), 'tocall': i.get('tocall'),
                    'why_by_street': i.get('why_by_street'),
                })
    ah = hashlib.sha1('\n'.join(sigs).encode()).hexdigest()[:16]
    json.dump({'seed': SEED, 'hands': n, 'action_hash': ah, 'traps': traps},
              open(out, 'w'), ensure_ascii=False, indent=1)
    print('%s  %d핸드' % (os.path.basename(out), n))
    print('  액션 해시   %s' % ah)
    print('  trap 관련 기록 %d건' % len(traps))
    for x in traps[:10]:
        print('    #%-3d %-6s seat%-2s plan=%-14s goal=%-14s mode=%-6s '
              'intent=%-5s resp=%-5s act=%s'
              % (x['hand'], x['street'], x['seat'], x['plan'], x['goal'],
                 x['mode'], x['intent_act'], x['response_act'], x['action']))


if __name__ == '__main__':
    main()
