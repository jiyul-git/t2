#!/usr/bin/env python3
"""계획 이탈 공격이 **나쁜 공격인가**. 읽기 전용이다.

  python3 tools/deviate_ev.py --files /tmp/bl2/collected.jsonl

`TRACE_BLUFF.md` ③-2 에서 봇이 치는 블러프성 공격의 53%가 계획 이탈
(`giveup`/`showdown` 인데 bet/raise)임을 확인했다. 빈도가 높다는 것만으로는
"나쁜 공격"이라고 할 수 없다. 여기서 질을 잰다.

### 절대 EV 를 쓰지 않는다 — 필요 폴드율과 실측 폴드율을 비교한다

절대 EV 는 "체크했으면 어땠을까"를 모르면 못 낸다. 그걸 알려면 핸드를 다시
돌려야 하고, 그러면 이후 전개가 통째로 달라진다.

대신 **양쪽 다 측정값인 두 숫자**를 비교한다.

  필요 폴드율 f*   그 벳이 체크보다 나아지려면 상대가 얼마나 접어야 하는가.
                   기록된 pot·bet·eq 로 케이스마다 계산한다
  실측 폴드율      그 집단에서 실제로 즉시 접은 비율

    EV(체크) = eq·P
    EV(벳)   = f·P + (1-f)·[eq·(P+2B) - B]
    두 식을 같게 놓으면
                    B(1-2eq)
        f* = ─────────────────────────
             P(1-eq) + B(1-2eq)

  eq > 0.5 면 분자가 음수라 f* < 0 — 벳이 무조건 낫다(밸류 벳이다).

**가정은 세 개다. 두 집단에 똑같이 적용되므로 집단 간 비교는 유효하다.**
  1. `eq` 는 올인 에쿼티라 리버까지 가는 것으로 본다
  2. 체크한 뒤 상대가 벳할 가능성을 무시한다
  3. 벳한 뒤 레이즈당할 가능성을 무시한다
"""
import argparse, glob, json, os, sys
from collections import Counter

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)

ORDER = ['preflop', 'flop', 'turn', 'river']
BLUFF = {'bluff_2street', 'river_bluff', 'semibluff'}
DEVIATE = {'giveup', 'showdown'}
VALUE = {'value_2street', 'value_3street', 'trap', 'thin_river'}
EXEC = {'bet', 'raise'}


def need_fold(pot, bet, eq):
    """f* — 이 벳이 체크보다 나아지려면 필요한 상대 폴드율."""
    P, B = float(pot), float(bet)
    if P <= 0 or B <= 0:
        return None
    num = B*(1.0 - 2.0*eq)
    den = P*(1.0 - eq) + num
    if abs(den) < 1e-9:
        return None
    return num/den


def immediate_fold(fl, street, seat, amt):
    """이 벳이 **그 자리에서** 팟을 가져갔는가.

    내 행동 줄 뒤로 같은 스트리트에 폴드만 남고, 이후 스트리트가 없어야 한다.
    나중 스트리트에서 상대가 접은 것은 이 벳의 즉시 효과가 아니다.
    """
    idx = None
    for i, row in enumerate(fl):
        if len(row) >= 4 and row[0] == street and row[1] == seat \
           and row[2] in EXEC and float(row[3] or 0) == float(amt or 0):
            idx = i
    if idx is None:
        return None
    for row in fl[idx+1:]:
        if row[0] != street:
            return False           # 다음 스트리트가 있다 = 콜당했다
        if row[2] != 'fold':
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--files', nargs='+', required=True)
    a = ap.parse_args()

    grp = {'계획 블러프': [], '이탈 블러프': [], '밸류(대조)': []}
    seen = set()
    hands = 0
    for path in a.files:
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            hands += 1
            fl = rec.get('full_log') or []
            res = rec.get('result') or {}
            sb = rec.get('stacks_before') or {}
            for it in (rec.get('intents') or []):
                if it.get('action') not in EXEC:
                    continue
                pl = it.get('plan')
                key = ('계획 블러프' if pl in BLUFF else
                       '이탈 블러프' if pl in DEVIATE else
                       '밸류(대조)' if pl in VALUE else None)
                if key is None:
                    continue
                uid = (rec.get('hand_no'), it.get('seat'), it.get('street'),
                       it.get('amt'))
                if uid in seen:
                    continue
                seen.add(uid)
                seat = it['seat']
                pot = it.get('pot')          # 벳 전 팟 (기록 필드)
                bet = it.get('amt')
                eq = it.get('eq')
                if pot is None or not bet or eq is None:
                    continue
                d = res.get('stacks', {}).get(str(seat))
                b0 = sb.get(str(seat))
                grp[key].append(dict(
                    f_need=need_fold(pot, bet, eq),
                    folded=immediate_fold(fl, it['street'], seat, bet),
                    eq=eq, pot=pot, bet=bet, street=it['street'],
                    sz=float(bet)/float(pot) if pot else None,
                    outs=it.get('outs_true'), made=it.get('made'),
                    delta=(float(d) - float(b0)) if (d is not None and b0 is not None) else None,
                    show=bool(res.get('showdown')),
                    won=(seat in (res.get('winners') or [])),
                ))

    def med(rows, k):
        v = sorted(x[k] for x in rows if x.get(k) is not None)
        return v[len(v)//2] if v else float('nan')

    def dec(rows, k):
        v = sorted(x[k] for x in rows if x.get(k) is not None)
        if len(v) < 5:
            return None
        return [v[int(q*(len(v)-1))] for q in (.1, .25, .5, .75, .9)]

    print('# 계획 이탈 공격의 질 — %d핸드\n' % hands)
    print('%-14s %6s %10s %12s %12s %10s' %
          ('', 'n', '실측 폴드%', '필요 폴드% f*', '여유(실측-f*)', 'eq 중앙'))
    for g in ('계획 블러프', '이탈 블러프', '밸류(대조)'):
        rows = grp[g]
        if not rows:
            continue
        fr = [r for r in rows if r['folded'] is not None]
        f_meas = 100.0*sum(1 for r in fr if r['folded'])/max(1, len(fr))
        fn = med(rows, 'f_need')*100
        print('%-14s %6d %9.1f%% %11.1f%% %11.1f%%p %10.3f'
              % (g, len(rows), f_meas, fn, f_meas - fn, med(rows, 'eq')))
    print()
    print('  실측 폴드율 = 그 벳이 그 자리에서 팟을 가져간 비율')
    print('  f* 는 케이스마다 계산한 중앙값. 음수면 벳이 무조건 낫다는 뜻이다')
    print()

    print('## 필요 폴드율 f* 분포 (10/25/50/75/90 분위, %)')
    for g in ('계획 블러프', '이탈 블러프', '밸류(대조)'):
        d = dec(grp[g], 'f_need')
        print('  %-12s %s' % (g, '  '.join('%6.1f' % (x*100) for x in d)
                              if d else '(표본 부족)'))
    print()

    print('## 벳 사이즈(팟 배수) 분포')
    for g in ('계획 블러프', '이탈 블러프', '밸류(대조)'):
        d = dec(grp[g], 'sz')
        print('  %-12s %s' % (g, '  '.join('%6.2f' % x for x in d)
                              if d else '(표본 부족)'))
    print()

    print('## 핸드 최종 칩 증감 (그 핸드 전체, 벳 하나의 EV 가 아니다)')
    for g in ('계획 블러프', '이탈 블러프', '밸류(대조)'):
        rows = [r for r in grp[g] if r['delta'] is not None]
        if not rows:
            continue
        pos = sum(1 for r in rows if r['delta'] > 0)
        print('  %-12s n=%4d  중앙 %+8.0f  평균 %+8.0f  플러스 비율 %.0f%%'
              % (g, len(rows), med(rows, 'delta'),
                 sum(r['delta'] for r in rows)/len(rows), 100.0*pos/len(rows)))
    print()

    print('## 스트리트별 (이탈 블러프)')
    for st in ('flop', 'turn', 'river'):
        rows = [r for r in grp['이탈 블러프'] if r['street'] == st]
        if not rows:
            continue
        fr = [r for r in rows if r['folded'] is not None]
        print('  %-6s n=%4d  실측폴드 %5.1f%%  f* 중앙 %5.1f%%  eq 중앙 %.3f'
              % (st, len(rows),
                 100.0*sum(1 for r in fr if r['folded'])/max(1, len(fr)),
                 med(rows, 'f_need')*100, med(rows, 'eq')))


if __name__ == '__main__':
    main()
