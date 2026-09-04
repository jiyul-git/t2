"""계획 → 실행 일치 검사.

**계획이 옳은지는 보지 않는다.** 판단 층이 정한 의도(plan['intents'][street])와
집행부가 실제로 낸 액션(full_log)이 일치하는지만 본다.

계획이 틀렸어도 그대로 집행됐으면 배선은 정상이다.
계획이 옳았는데 다른 게 나갔으면 그것이 버그다.

이탈이 `deviations` 에 기록돼 있으면 위반이 아니다 — 의도적 이탈은
규율(discipline) 모델의 정상 동작이고, 기록이 그 증거다.
기록 없이 어긋난 것만 잡는다.

    python3 tools/execcheck.py [아카이브경로]
"""
import sys, os, json, collections

D = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(D, '..', 'hand_archive2.jsonl')

AGGR = ('bet', 'raise', 'allin')


def load(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


def check(rec):
    """한 결정에 대한 위반 사유. 정상이면 None."""
    want = rec.get('intent_act')
    got = rec.get('action')
    if want is None:
        return None                      # 의도 기록 이전 핸드
    if rec.get('dev'):
        return None                      # 기록된 이탈은 정상
    tocall = rec.get('tocall') or 0

    if want == 'bet':
        # 벳하려 했는데 안 나갔다. 저항이 있었으면 콜/폴드가 맞을 수 있으므로
        # 무저항(tocall == 0) 일 때만 위반으로 본다.
        if tocall == 0 and got not in AGGR:
            return '의도 bet → 실행 %s (무저항인데 공격 안 나감)' % got
        return None

    if want == 'check':
        if tocall == 0 and got in AGGR:
            return '의도 check → 실행 %s (기록 없는 공격)' % got
        return None
    return None


def size_gap(rec, tol=0.35):
    """의도한 팟대비 사이즈와 실제로 나간 칩의 괴리."""
    if rec.get('intent_act') != 'bet' or rec.get('action') not in AGGR:
        return None
    frac = rec.get('intent_size')
    pot = rec.get('pot')
    amt = rec.get('amt')
    if not frac or not pot or not amt:
        return None
    want = frac * pot
    if want <= 0:
        return None
    ratio = amt / want
    if ratio > 1 + tol or ratio < 1 - tol:
        return (want, amt, ratio)
    return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    rows = load(path)
    if not rows:
        print('기록 없음: %s' % path)
        return

    # --- 음성 대조군 ---
    # 위반 0건이 '정상'인지 '검사기가 아무것도 못 잡는 것'인지 구분해야 한다.
    # 일부러 어긋난 기록을 넣어 검사기가 잡는지 먼저 확인한다.
    fake = [{'street': 'flop', 'seat': 1, 'type': 'X', 'intent_act': 'bet',
             'action': 'check', 'tocall': 0, 'dev': []},
            {'street': 'flop', 'seat': 1, 'type': 'X', 'intent_act': 'check',
             'action': 'bet', 'tocall': 0, 'dev': []}]
    caught = sum(1 for f in fake if check(f))
    print('검사기 자체 점검: 인위적 위반 %d건 중 %d건 탐지' % (len(fake), caught))
    if caught != len(fake):
        print('  ** 검사기가 고장났다. 아래 결과를 믿지 말 것 **')
    print()

    n = viol = noint = gaps = 0
    by_type = collections.Counter()
    for r in rows:
        for i in (r.get('intents') or []):
            if i.get('street') == 'preflop':
                continue
            if i.get('intent_act') is None:
                noint += 1
                continue
            n += 1
            why = check(i)
            if why:
                viol += 1
                by_type[i.get('type')] += 1
                print('[위반] #%-3d %-6s seat%-2d %-12s %s'
                      % (r.get('hand_no', 0), i['street'], i['seat'],
                         i.get('type'), why))
            g = size_gap(i)
            if g:
                gaps += 1
                if gaps <= 15:
                    print('[사이즈] #%-3d %-6s seat%-2d %-12s 의도 %.0f → 실행 %.0f (%.2fx)'
                          % (r.get('hand_no', 0), i['street'], i['seat'],
                             i.get('type'), g[0], g[1], g[2]))
    print()
    print('검사 대상 %d건 / 액션 위반 %d건 / 사이즈 괴리 %d건' % (n, viol, gaps))
    if noint:
        print('의도 미기록(구버전 핸드) %d건 — 검사 제외' % noint)
    if by_type:
        print('퍼소나별 액션 위반:')
        for k, v in by_type.most_common():
            print('   %-14s %d' % (k, v))


if __name__ == '__main__':
    main()
