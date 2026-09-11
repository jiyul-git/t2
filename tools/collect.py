#!/usr/bin/env python3
"""히어로 없이 봇끼리만 돌려서 계획(intent) 데이터를 모은다.

  python tools/collect.py 300          # 300핸드
  python tools/collect.py 300 out.jsonl

판단 로직은 건드리지 않는다. tourney 의 핸드 루프를 그대로 돌리고
h.intents 를 파일로 떨굴 뿐이다. live2 의 hand_archive2_alt.jsonl 과
같은 스키마의 부분집합을 쓴다 (intents 분석에 필요한 필드만).

히어로 좌석은 형식상 지정하지만 봇이 대신 판단하므로 사람이 개입하지
않는다. 히어로가 파산하면 새 토너먼트를 시작해 목표 핸드 수를 채운다.
"""
import os, sys, json, time, random

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)

import tourney as T


def run_one(seed, entries=40, start_stack=30000, hands_per_level=12,
            max_hands=10**9):
    """토너먼트 하나를 히어로 파산 또는 max_hands 까지 돌린다."""
    # 히어로 좌석을 비우면 finish_hand 가 매 핸드 파산으로 보고 토너를 끝낸다.
    # 실제 좌석을 주고, 그 좌석은 아래 루프에서 항상 체크/폴드로 넘긴다.
    # 히어로는 계획을 세우지 않으므로 intent 수집에는 영향이 없다.
    t = T.Tournament(entries=entries, start_stack=start_stack,
                     hero_seat=7, seats=8, seed=seed,
                     hands_per_level=hands_per_level)
    out = []
    n = 0
    while n < max_hands:
        try:
            st = t.next_hand()
        except Exception:
            break
        # 히어로가 없으므로 yield 없이 끝까지 돈다.
        guard = 0
        while isinstance(st, dict) and not st.get('done'):
            guard += 1
            if guard > 400:
                break
            # 'fold' 는 콜 비용이 0 이면 runner 가 체크로 바꿔준다.
            st = t.submit('fold', 0)
        h = t.hand
        rec = {
            'hand_no': t.hand_no,
            'hash': getattr(h, 'hash', None),
            'level': t.level,
            'board': list(getattr(h, 'board', []) or []),
            'pos': {str(k): v for k, v in getattr(h, 'pos', {}).items()},
            'hole': {str(k): v for k, v in getattr(h, 'hole', {}).items()},
            'intents': getattr(h, 'intents', []),
            'profiles': {str(s): h.prof.get(str(s), {}) for s in h.seats},
            # 응답(콜/폴드) 분석용. 판단 로직과 무관한 기록 필드다.
            'full_log': list(getattr(t.run, 'full_log', []) or []),
            'blinds': list(t.blinds()),
            'stacks_before': dict(getattr(h, '_start_stacks', {}) or {}),
            # 정산 직후 스택. **finish_hand 뒤의 t.stacks 를 쓰면 안 된다** —
            # 거기서 테이블 재조정이 빈 자리에 새 플레이어를 앉히므로
            # 그 좌석의 won 이 신규 스택만큼 튄다(실측: 40핸드 중 1건에서 +33150).
            # h.stacks 는 그 핸드의 정산 결과 그대로다.
            'stacks_after': dict(getattr(h, 'stacks', {}) or {}),
            'won': {str(k): (getattr(h, 'stacks', {}) or {}).get(k, 0) - v
                    for k, v in (getattr(h, '_start_stacks', {}) or {}).items()},
            'seats': list(h.seats),
        }
        out.append(rec)
        n += 1
        try:
            t.finish_hand()
        except Exception:
            break
        # 정산 후 스택. EV 비교(showdown / non-showdown)에 필요하다.
        # 기록 전용 필드이고 판단 로직과 무관하다.
        # 키 타입을 맞춘다. stacks_before 는 int 키(_start_stacks)이고
        # t.stacks 도 int 키다. 한쪽만 문자열화하면 won 이 전부 0 이 된다.
        _before = getattr(h, '_start_stacks', {}) or {}
        rec['stacks_after'] = {str(k): v for k, v in t.stacks.items()}
        rec['won'] = {str(k): t.stacks.get(k, 0) - _before.get(k, 0)
                      for k in _before if k in t.stacks}
        if getattr(t, 'busted_hero', False):
            break
        if sum(1 for s in t.seats if t.stacks[s] > 0) < 2:
            break
    return out


def main():
    """python3 tools/collect.py <핸드수> [출력파일] [--seed0 N]

    --seed0 을 주면 토너먼트 시드를 N, N+1, N+2 ... 로 **결정적으로** 쓴다.
    A/B 짝지은 비교(paired comparison)에는 반드시 이걸 써야 한다 —
    기본값은 매 실행 무작위라 두 실행이 다른 게임을 돌게 된다.
    """
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    seed0 = None
    for a in sys.argv[1:]:
        if a.startswith('--seed0'):
            seed0 = int(a.split('=', 1)[1]) if '=' in a else None
    if seed0 is None and '--seed0' in sys.argv:
        seed0 = int(sys.argv[sys.argv.index('--seed0') + 1])
    target = int(args[0]) if args else 300
    path = args[1] if len(args) > 1 else os.path.join(D, 'collected.jsonl')

    rng = random.Random()
    _k = [0]
    total = 0
    t0 = time.time()
    with open(path, 'w') as fp:
        while total < target:
            if seed0 is None:
                seed = rng.randrange(10**9)
            else:
                seed = seed0 + _k[0]
                _k[0] += 1
            recs = run_one(seed, max_hands=target - total)
            if not recs:
                continue
            for r in recs:
                fp.write(json.dumps(r, ensure_ascii=False, default=str) + '\n')
            total += len(recs)
            fp.flush()
            el = time.time() - t0
            n_it = sum(len(r['intents']) for r in recs)
            print('  +%3d핸드  누적 %4d/%d  (%.0fs)' % (len(recs), total, target, el),
                  flush=True)

    # 요약
    tgt = 0
    inst = 0
    with open(path) as f:
        for l in f:
            r = json.loads(l)
            for i in r.get('intents', []):
                if i.get('eq_current') is None:
                    continue
                inst += 1
                if i.get('made') == 0 and i.get('outs', 0) >= 4 and i.get('street') == 'flop':
                    tgt += 1
    print()
    print('완료: %d핸드  계측 intent %d건  목표스팟 %d건  (%.0fs)'
          % (total, inst, tgt, time.time() - t0))
    print('파일: %s' % path)


if __name__ == '__main__':
    main()
