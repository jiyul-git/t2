#!/usr/bin/env python3
"""블러프 라인·레인지 일관성. **읽기 전용이다.**

  python3 tools/bluff_coherence.py
  python3 tools/bluff_coherence.py --show 8      # 개별 케이스도 찍는다

묻는 것은 "이 핸드로 블러프가 가능한가"가 아니라
**"이 라인에서 이 핸드가 블러프하기 좋은 핸드인가"** 다.

### GTO 와 비교하지 않는다
먼저 **엔진 자신의 논리적 일관성**을 본다. 관찰자 역할도 엔진 자신의 레인지
기계(`ranges.preflop_range` → `narrow_by_actions`)에 맡긴다. 그래야 결과가
"솔버가 싫어한다"가 아니라 **"엔진이 자기 모델로도 설명하지 못한다"** 가 된다.

### 레인지는 라인을 거슬러 복원한다
블러프 스트리트의 전체 스타팅 레인지를 보면 안 된다.

    스타팅 → 프리플랍 액션 → 플랍 액션 → 턴 액션 → 지금의 후보 레인지

`narrow_by_actions` 는 원래 '상대 레인지를 좁히는' 함수지만 하는 일은
"이 라인을 밟은 사람의 레인지"라 같다. 새로 만들지 않고 그것을 쓴다.

### 판정은 개별이 아니라 **공통 원인별로 묶는다**
이상한 블러프 한둘을 잡아 코드를 고치지 않는다. 여러 핸드에서 반복되는
원인이 확인돼야 수정 후보다.

### 임계값을 지어내지 않는다
"blocker_net <= 0 이면 블로커 무의미" 같은 컷을 두면, 그 값의 중앙이 0 근처일 때
표본의 절반이 자동으로 걸린다. 처음 판에서 실제로 그렇게 해서 "블로커 무의미
72%" 를 만들 뻔했다. 대신 **밸류 벳을 대조군으로 같은 측정을 하고 두 집단의
중앙값을 나란히 놓는다.** 차이가 없으면 그것은 블러프의 문제가 아니다.
"""
import argparse, glob, json, os, sys
from collections import Counter, defaultdict

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)

import bot, plan as PL, ranges as R

ORDER = ['preflop', 'flop', 'turn', 'river']
BLUFF = {'bluff_2street', 'river_bluff', 'semibluff'}
# **대조군.** 임계값을 지어내면 중앙값 근처의 컷 하나로 표본의 절반이 걸린다.
# 처음에 그렇게 해서 '블로커 무의미 72%' 같은 숫자를 만들 뻔했다. 같은 측정을
# 밸류 벳에도 하고 **두 집단을 나란히 놓는다.**
VALUE = {'value_2street', 'value_3street', 'trap', 'thin_river'}
EXEC = {'bet', 'raise'}
NB = {'flop': 3, 'turn': 4, 'river': 5}


def files():
    out = ['review_2.jsonl', 'review_279.jsonl',
           'hand_archive2.jsonl', 'hand_archive2_alt.jsonl']
    out += sorted(glob.glob(os.path.join(D, 'bak_*hand_archive2*.jsonl')))
    seen = []
    for f in out:
        p = f if os.path.isabs(f) else os.path.join(D, f)
        if os.path.exists(p) and p not in seen:
            seen.append(p)
    return seen


def walk_pots(fl, sb, bb):
    """각 액션 직전의 팟과 콜비용. 엔진의 금액은 그 스트리트 누적('to')이다."""
    out = []
    streets = {}
    for row in fl:
        if len(row) < 4 or row[0] not in ORDER:
            continue
        streets.setdefault(row[0], []).append(tuple(row[1:4]))
    prev = 0
    for st in ORDER:
        if st not in streets:
            continue
        contrib = Counter()
        for (s, a, amt) in streets[st]:
            cur = prev + sum(contrib.values())
            if st == 'preflop' and cur == 0:
                cur = sb + bb
            tocall = max(contrib.values() or [0]) - contrib[s]
            out.append(dict(street=st, seat=s, act=a, amt=amt,
                            pot_before=cur, tocall=tocall))
            if a in ('raise', 'bet', 'call', 'allin'):
                contrib[s] = max(contrib[s], float(amt or 0))
        prev += sum(contrib.values())
    return out


def pf_action(rows, seat):
    """그 사람의 프리플랍 행동 분류와 오프너 자리."""
    pre = [x for x in rows if x['street'] == 'preflop']
    opener = None
    raises = 0
    mine = None
    for x in pre:
        if x['act'] == 'raise':
            raises += 1
            if opener is None:
                opener = x['seat']
        if x['seat'] == seat and mine is None and x['act'] != 'fold':
            if x['act'] == 'raise':
                mine = 'open' if raises <= 1 else '3bet'
            elif x['act'] == 'call':
                mine = 'call' if raises >= 1 else 'limp'
    return mine, opener


def line_acts(rows, seat, upto):
    """그 사람의 포스트플랍 라인. **판정 대상 스트리트는 뺀다.**"""
    acts = []
    si = ORDER.index(upto)
    for x in rows:
        if x['street'] == 'preflop' or ORDER.index(x['street']) >= si:
            continue
        if x['seat'] != seat:
            continue
        frac = (float(x['amt'] or 0) / x['pot_before']) if x['pot_before'] else 0.0
        acts.append((x['street'], x['act'], round(frac, 3)))
    return acts


def analyse(rec, it):
    st = it['street']
    seat = it['seat']
    board = (rec.get('board') or [])[:NB[st]]
    hole = (rec.get('hole') or {}).get(str(seat))
    prof = (rec.get('profiles') or {}).get(str(seat))
    if not board or not hole or not prof:
        return None
    sb, bb = (rec.get('blinds') or [0, 0])[:2]
    rows = walk_pots(rec.get('full_log') or [], sb, bb)
    act, opener = pf_action(rows, seat)
    if act is None:
        return None
    pos = (rec.get('pos') or {}).get(str(seat))
    bbs = (rec.get('stacks_before') or {}).get(str(seat), 0) / float(bb or 1)
    try:
        base = R.preflop_range(prof, pos, act, bbs, set(board),
                               opener_pos=(rec.get('pos') or {}).get(str(opener)),
                               seats=len(rec.get('pos') or {}) or 8)
        rng = R.narrow_by_actions(base, board, line_acts(rows, seat, st), None, None)
    except Exception:
        return None
    if not rng:
        return None

    mine = tuple(sorted(hole))
    in_range = any(tuple(sorted(c)) == mine for c in rng)
    strengths = [bot.made_strength(list(c), board) for c in rng]
    my_made = bot.made_strength(hole, board)
    my_outs = PL.draw_strength(hole, board)
    n = len(rng)
    value_n = sum(1 for x in strengths if x >= 2)          # 탑페어 이상
    air_n = sum(1 for c, x in zip(rng, strengths)
                if x == 0 and PL.draw_strength(list(c), board) >= 4)
    # 강도 백분위는 **연속값(eval7)** 으로 낸다. made_strength 버킷으로 세면
    # 에어끼리 전부 동률이라 made==0 인 순간 백분위가 0 으로 고정된다 —
    # '레인지에서 제일 약하다'와 '다른 에어와 같다'가 구분되지 않는다.
    try:
        my_rank = bot.eval7(list(hole) + list(board))
        ranks = [bot.eval7(list(c) + list(board)) for c in rng]
        weaker = sum(1 for x in ranks if x < my_rank)
    except Exception:
        weaker = sum(1 for x in strengths if x < my_made)
    return dict(
        hand=rec.get('hand_no'), street=st, seat=seat, pos=pos,
        plan=it.get('plan'), action=it.get('action'), amt=it.get('amt'),
        hole=hole, board=board, line=line_acts(rows, seat, st), pf=act,
        rng_n=n, in_range=in_range,
        value_pct=100.0*value_n/n, air_draw_pct=100.0*air_n/n,
        my_pctile=100.0*weaker/n,
        made=it.get('made', my_made), rel=it.get('rel'),
        outs_true=it.get('outs_true', my_outs),
        nut_adv=it.get('nut_adv'), range_adv=it.get('range_adv'),
        blocker=it.get('blocker'), blocker_net=it.get('blocker_net'),
        eq=it.get('eq'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--show', type=int, default=0, help='개별 케이스 N건 출력')
    a = ap.parse_args()

    grp = {'블러프': [], '밸류': []}
    hands = 0
    plans = Counter()
    for path in files():
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            hands += 1
            for it in (rec.get('intents') or []):
                plans[it.get('plan')] += 1
                if it.get('action') not in EXEC:
                    continue
                key = ('블러프' if it.get('plan') in BLUFF else
                       '밸류' if it.get('plan') in VALUE else None)
                if key is None:
                    continue
                c = analyse(rec, it)
                if c:
                    grp[key].append(c)
    cases = grp['블러프']

    def med(rows, key):
        v = sorted(x[key] for x in rows if x.get(key) is not None)
        return v[len(v)//2] if v else float('nan')

    print('# 블러프 라인·레인지 일관성')
    print('# 아카이브 %d핸드, intent %d건' % (hands, sum(plans.values())))
    print('# 블러프 실행 %d건 · 밸류 실행 %d건(대조군)\n'
          % (len(cases), len(grp['밸류'])))
    print('참고: `river_bluff` 계획은 아카이브 전체에서 %d건이다.'
          % plans.get('river_bluff', 0))
    print()
    if not cases:
        print('분석 가능한 케이스가 없다.')
        return

    print('## 계획·스트리트별 (블러프)')
    for k, v in Counter('%s / %s' % (c['plan'], c['street'])
                        for c in cases).most_common():
        print('  %-28s %3d' % (k, v))
    print()

    print('## 두 집단 비교 — 중앙값을 나란히. 임계값은 두지 않는다')
    print('  %-28s %10s %10s %10s' % ('', '블러프', '밸류', '차이'))
    M = [('복원 레인지 크기(콤보)', 'rng_n', '%.0f'),
         ('내 핸드 강도 백분위 %', 'my_pctile', '%.0f'),
         ('레인지의 밸류 콤보 %', 'value_pct', '%.0f'),
         ('레인지의 에어+드로우 %', 'air_draw_pct', '%.0f'),
         ('range_adv', 'range_adv', '%+.2f'),
         ('nut_adv', 'nut_adv', '%+.2f'),
         ('blocker_net', 'blocker_net', '%+.3f'),
         ('made', 'made', '%.0f'),
         ('outs_true', 'outs_true', '%.0f'),
         ('eq', 'eq', '%.3f')]
    for label, key, fmt in M:
        x, y = med(cases, key), med(grp['밸류'], key)
        d = x - y
        print('  %-28s %10s %10s %10s'
              % (label, fmt % x, fmt % y, ('%+.3f' % d).rstrip('0').rstrip('.')))
    print()
    ib = 100.0*sum(1 for c in cases if c['in_range'])/max(1, len(cases))
    iv = 100.0*sum(1 for c in grp['밸류'] if c['in_range'])/max(1, len(grp['밸류']))
    print('  %-28s %9.0f%% %9.0f%% %9.0f%%p'
          % ('복원 레인지 안에 있음', ib, iv, ib-iv))

    if a.show:
        print('\n## 개별 케이스 (앞 %d건)' % a.show)
        for c in cases[:a.show]:
            print('\n  h%-5s %-6s seat%-2s %-4s  %s  보드 %s'
                  % (c['hand'], c['street'], c['seat'], c['pos'],
                     ' '.join(c['hole']), ' '.join(c['board'])))
            print('    라인 %s → %s %s' % (c['pf'], c['action'], c['amt']))
            for x in c['line']:
                print('      %s %s %.2f팟' % x)
            print('    레인지 %d콤보 · 내 강도 백분위 %.0f%% · 밸류 %.0f%% · 에어드로우 %.0f%%'
                  % (c['rng_n'], c['my_pctile'], c['value_pct'], c['air_draw_pct']))
            print('    made %s · outs %s · rel %s · range_adv %s · blocker_net %s'
                  % (c['made'], c['outs_true'], c['rel'], c['range_adv'],
                     c['blocker_net']))


if __name__ == '__main__':
    main()
