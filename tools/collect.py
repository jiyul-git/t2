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
                     hero_seat=7, seed=seed,
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
            'seats': list(h.seats),
            # 손익 분석용. session.Run.result 가 핸드 결과다 (live2 도 같은 것을
            # 읽는다: live2.py:324). stacks_before 와 합치면 좌석별 칩 증감이 나온다.
            # **기록 전용이다** — 판단 로직과 무관하다.
            'result': getattr(t.run, 'result', None),
        }
        out.append(rec)
        n += 1
        try:
            t.finish_hand()
        except Exception:
            break
        if getattr(t, 'busted_hero', False):
            break
        if sum(1 for s in t.seats if t.stacks[s] > 0) < 2:
            break
    return out


def main():
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(D, 'collected.jsonl')

    rng = random.Random()
    total = 0
    t0 = time.time()
    with open(path, 'w') as fp:
        while total < target:
            seed = rng.randrange(10**9)
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
