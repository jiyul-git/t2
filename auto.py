"""Claude 가 히어로로 직접 플레이. 액션은 CLI 로 받고 상태를 보여준다."""
import sys, json
sys.path.insert(0, '/home/claude/t2')
import tourney as T

SEED = 555001
ACTS = '/home/claude/t2/auto_acts.json'

def load():
    try: return json.load(open(ACTS))
    except Exception: return []

def replay(acts):
    t = T.Tournament(entries=100, start_stack=30000, hero_seat=7, seats=8,
                     seed=SEED, hands_per_level=12)
    i = 0; st = t.next_hand()
    while True:
        while st and not st.get('done'):
            if i >= len(acts): return t, st, False
            a = acts[i]; i += 1
            st = t.submit(a[0], a[1] if len(a) > 1 else 0)
        t.finish_hand()
        if sum(1 for s in t.seats if t.stacks[s] > 0) < 2: return t, st, True
        st = t.next_hand()

def fmt(t, st):
    L = ['핸드 #%d | 레벨 %d | 남은 %d명' % (t.hand_no, t.level, t.field.remaining)]
    bd = st.get('board') or []
    L.append('보드: ' + (' '.join(bd) if bd else '—'))
    pos = st.get('pos') or (t.hand.pos.get(t.hero) if t.hand else '?')
    L.append('내 패: %s (%s)' % (' '.join(st.get('hole') or []), pos))
    L.append('스택: {:,}  |  팟: {:,}  |  콜: {:,}'.format(
        st.get('stack', 0), st.get('pot', 0), st.get('tocall', 0)))
    for (x, a, amt) in (st.get('log') or []):
        L.append('  좌석%d %s %s' % (x, a, '{:,}'.format(amt) if amt else ''))
    L.append('상대 스택: ' + '  '.join(
        '좌석%d %s' % (s, '{:,}'.format(t.stacks[s])) for s in sorted(t.seats)
        if s != t.hero and t.stacks[s] > 0))
    return '\n'.join(L)

if __name__ == '__main__':
    acts = load()
    if len(sys.argv) > 1 and sys.argv[1] == 'reset':
        json.dump([], open(ACTS, 'w')); acts = []
    elif len(sys.argv) > 1:
        for tok in sys.argv[1:]:
            p = tok.split(':')
            acts.append([p[0], int(p[1])] if len(p) > 1 else [p[0]])
        json.dump(acts, open(ACTS, 'w'))
    t, st, over = replay(acts)
    print(fmt(t, st)); print('HASH', t.hand.hash)
