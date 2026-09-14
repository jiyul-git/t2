#!/usr/bin/env python3
"""step_others(settle=False) 분리가 동작을 보존하는지 검증한다.

  T2_BOT_LOG=0 python3 tools/verify_settle_split.py --entries 100 --hands 25

live2.finish 는 이미 step_others() 뒤에 _collect_busts(); _balance() 를 한 번 더
부른다 (live2.py:220-221). 그래서 비교 대상은 다음 둘이다.

  현재:  step_others()              → _collect_busts() → _balance()
         (수거·밸런싱이 step_others 안에서 한 번, 밖에서 또 한 번)
  분할:  step_others(settle=False)  → _collect_busts() → _balance()
         (한 번만)

두 번 부르는 쪽이 두 번째 호출에서 사실상 no-op 이 되리라는 것은 코드를 읽으면
그럴듯하지만, 읽어서 정하지 않는다. 같은 시드로 핸드마다 필드 상태 서명을
만들어 대조한다. 서명에는 순위를 좌우하는 busted_order 가 순서 그대로 들어간다.

난수: 두 변형 모두 같은 시드로 Field 를 새로 만들고 같은 순서로 호출하므로
f.rng 소비가 같아야 한다. 어긋나면 서명이 즉시 갈린다.
"""
import argparse, hashlib, json, os, sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)


def sig(f):
    """필드 상태의 결정론적 서명. 순위를 좌우하는 busted_order 는 순서 그대로."""
    return {
        'hand_no': f.hand_no, 'level': f.level,
        'players': [[p['pid'], p['stack'], p['table']]
                    for p in sorted(f.players.values(), key=lambda x: x['pid'])],
        'busted_order': list(f.busted_order),
        'tables': [[t, tb.button, tb.hands,
                    [p['pid'] for p in tb.players], list(tb.seats)]
                   for t, tb in sorted(f.tables.items())],
        'hero_moves': f.hero_moves,
    }


def play(entries, hands, seed, split):
    import fieldsim as FS
    f = FS.Field(entries=entries, start_stack=30000, hero_pid=0, seed=seed,
                 hands_per_level=12, itm_frac=0.15)
    out = []
    for _ in range(hands):
        if f.remaining() <= 1:
            break
        f.hand_no += 1
        f.advance_level()
        f.notes = []
        # live2 는 히어로 테이블을 먼저 끝내고 스택을 반영한 뒤 step_others 를 부른다.
        tb = f.tables.get(f.players[f.hero_pid]['table'])
        if tb is not None and tb.n() >= 2:
            f._play_table(tb)
        if split:
            f.step_others(settle=False)
        else:
            f.step_others()
        # live2.finish:220-221 이 항상 부르는 부분
        f._collect_busts()
        f._balance()
        out.append(sig(f))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--hands', type=int, default=25)
    ap.add_argument('--seed', type=int, default=4242)
    a = ap.parse_args()

    cur = play(a.entries, a.hands, a.seed, split=False)
    spl = play(a.entries, a.hands, a.seed, split=True)

    hc = hashlib.sha256(json.dumps(cur, sort_keys=True).encode()).hexdigest()
    hs = hashlib.sha256(json.dumps(spl, sort_keys=True).encode()).hexdigest()
    print('entries %d, %d핸드, seed %d' % (a.entries, len(cur), a.seed))
    print('  현재 경로  %s' % hc)
    print('  분할 경로  %s' % hs)
    if hc == hs:
        print('\n동일 — settle 분리는 동작을 보존한다')
        return 0
    for i, (c, s) in enumerate(zip(cur, spl)):
        if c != s:
            print('\n핸드 %d 에서 처음 갈림' % (i + 1))
            for k in c:
                if c[k] != s[k]:
                    print('  [%s]\n    현재: %s\n    분할: %s'
                          % (k, str(c[k])[:300], str(s[k])[:300]))
            break
    return 1


if __name__ == '__main__':
    sys.exit(main())
