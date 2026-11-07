"""히어로 대국 진행기. 액션 목록을 받아 그 지점까지 재생하고 현재 상태를 출력한다.

제너레이터는 피클할 수 없으므로 상태를 저장하지 않고,
고정 시드 + 액션 로그로 매번 재생한다 (재현성이 확보돼 있어 가능한 방식).
"""
import sys, json
sys.path.insert(0, '/home/claude/t2')
import tourney as T

SEED = 880808
ACTS = '/home/claude/t2/acts.json'

def load():
    try: return json.load(open(ACTS))
    except Exception: return []

def replay(acts):
    t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                     seed=SEED, hands_per_level=12)
    i = 0
    st = t.next_hand()
    while True:
        while st and not st.get('done'):
            if i >= len(acts): return t, st, False
            a = acts[i]; i += 1
            st = t.submit(a[0], a[1] if len(a) > 1 else 0)
        t.finish_hand()
        if sum(1 for s in t.seats if t.stacks[s] > 0) < 2: return t, st, True
        st = t.next_hand()

def fmt(t, st):
    L = []
    L.append('핸드 #%d | 레벨 %d | 남은 %d명' % (t.hand_no, t.level, t.field.remaining))
    bd = st.get('board') or []
    L.append('보드: ' + (' '.join(bd) if bd else '—'))
    pos = st.get('pos') or (t.hand.pos.get(t.hero) if t.hand else None)
    L.append('내 패: %s (%s)' % (' '.join(st.get('hole') or []), pos or '?'))
    L.append('스택: {:,}'.format(st.get('stack', 0)))
    L.append('팟: {:,}  |  콜: {:,}'.format(st.get('pot', 0), st.get('tocall', 0)))
    # 이번 스트리트 로그만 보여주면 '누가 콜했는지'가 안 보인다.
    # 핸드 전체 로그를 스트리트별로 다 보여준다.
    full = list(getattr(t.run, 'full_log', []) or [])
    stage = st.get('stage') or ''
    full += [(stage, x, a, amt) for (x, a, amt) in (st.get('log') or [])]
    seen = set()
    for (stt, x, a, amt) in full:
        k = (stt, x, a, amt)
        if k in seen:
            continue
        seen.add(k)
        pos = t.hand.pos.get(x, '?')
        me = '(나)' if x == t.hero else ''
        body = '%s %s' % (a, '{:,}'.format(amt)) if amt else a
        L.append('  [%s] 좌석%d %s%s  %s' % (stt, x, pos, me, body))
    return '\n'.join(L)

if __name__ == '__main__':
    acts = load()
    if len(sys.argv) > 1:
        for tok in sys.argv[1:]:
            p = tok.split(':')
            acts.append([p[0], int(p[1])] if len(p) > 1 else [p[0]])
        json.dump(acts, open(ACTS, 'w'))
    t, st, over = replay(acts)
    print(fmt(t, st))
    print('HASH', t.hand.hash)
