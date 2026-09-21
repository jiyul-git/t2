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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logkeys as LK

ORDER = ['preflop', 'flop', 'turn', 'river']
BLUFF = {'bluff_2street', 'river_bluff', 'semibluff'}
# **대조군.** 임계값을 지어내면 중앙값 근처의 컷 하나로 표본의 절반이 걸린다.
# 처음에 그렇게 해서 '블로커 무의미 72%' 같은 숫자를 만들 뻔했다. 같은 측정을
# 밸류 벳에도 하고 **두 집단을 나란히 놓는다.**
VALUE = {'value_2street', 'value_3street', 'trap', 'thin_river'}
# **이탈 블러프는 별도 그룹이다.** `make_plan` 이 "이 핸드로 블러프한다"고
# 판단한 것이 아니라, 포기/쇼다운 계획을 실행 단계가 확률적으로 뒤집은 것이다
# (`decide_aggression:857` 지속벳, `decide_response:800` 블러프 레이즈).
# 계획 블러프와 섞으면 원인 분석이 흐려진다.
# `pot_control` 은 넣지 않는다. SIZING['pot_control'] 이 flop 0.30 / river 0.30
# 이라 **계획대로 치는 것**이지 이탈이 아니다. 처음에 넣었다가 168건이
# 이탈로 잘못 세어졌다.
DEVIATE = {'giveup', 'showdown'}
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
    """(결과, drop 사유) 를 돌려준다.

    예전에는 어느 경우든 `None` 하나였다. 그러면 **표본에서 조용히 사라지고**
    남은 건수만 보고 "그 상황이 없었다"로 읽힌다 — 도달성 판정을 통째로
    뒤집는 오독이다. 사유를 갈라 집계한다.
    """
    st = it['street']
    seat = it['seat']
    board = (rec.get('board') or [])[:NB[st]]
    hole = (rec.get('hole') or {}).get(str(seat))
    prof = (rec.get('profiles') or {}).get(str(seat))
    if not board:
        return None, 'missing_board'
    if not hole:
        return None, 'missing_hole'
    if not prof:
        return None, 'missing_profile'
    sb, bb = (rec.get('blinds') or [0, 0])[:2]
    rows = walk_pots(rec.get('full_log') or [], sb, bb)
    act, opener = pf_action(rows, seat)
    if act is None:
        return None, 'no_preflop_action'
    pos = (rec.get('pos') or {}).get(str(seat))
    bbs = (rec.get('stacks_before') or {}).get(str(seat), 0) / float(bb or 1)
    try:
        base = R.preflop_range(prof, pos, act, bbs, set(board),
                               opener_pos=(rec.get('pos') or {}).get(str(opener)),
                               seats=len(rec.get('pos') or {}) or 8)
        rng = R.narrow_by_actions(base, board, line_acts(rows, seat, st), None, None)
    except Exception as e:
        # 계약 오류와 '이 상황은 분석 불가'를 구분한다. 예외 종류를 남긴다.
        return None, 'range_error:%s' % type(e).__name__
    if not rng:
        return None, 'empty_range'

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
    degraded = None
    try:
        my_rank = bot.eval7(list(hole) + list(board))
        ranks = [bot.eval7(list(c) + list(board)) for c in rng]
        weaker = sum(1 for x in ranks if x < my_rank)
    except Exception as e:
        # 버림이 아니라 **품질 저하**다. 버킷 백분위로 내려간다 —
        # made==0 끼리 동률이 되어 백분위가 0 으로 고정된다.
        degraded = 'eval7_fallback:%s' % type(e).__name__
        weaker = sum(1 for x in strengths if x < my_made)
    return dict(
        _degraded=degraded,
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
        eq=it.get('eq')), None


def _finish(malformed, allow):
    """깨진 줄이 있으면 기본적으로 nonzero 로 끝낸다."""
    if not malformed:
        return 0
    if allow:
        print('NOTE 깨진 줄 %d — --allow-malformed 로 계속했다' % len(malformed))
        return 0
    print('FAIL 깨진 JSON 줄 %d. 분석 표본에서 조용히 빠졌다.' % len(malformed))
    print('  과거 파일에 실제로 깨진 줄이 있어 계속해야 한다면 '
          '--allow-malformed 를 명시할 것')
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--show', type=int, default=0, help='개별 케이스 N건 출력')
    ap.add_argument('--files', nargs='*', default=None,
                    help='아카이브 경로. 없으면 저장소의 기본 목록')
    ap.add_argument('--allow-malformed', action='store_true',
                    help='깨진 JSON 줄이 있어도 분석을 계속하고 rc 0 으로 끝낸다. '
                         '기본은 건수를 보고하고 rc 1 이다')
    a = ap.parse_args()
    paths = a.files if a.files else files()

    grp = {'계획 블러프': [], '밸류(대조)': [], '이탈 블러프': []}
    hands = 0
    plans = Counter()
    seen = set()
    gens = Counter()                 # 세대별 intent 수
    per_file = {}                    # 파일 -> {세대, 핸드, intent, 깨진 줄}
    malformed = []                   # (파일, 줄번호)
    drops = Counter()                # 사유별 탈락
    degraded = Counter()
    for path in paths:
        info = {'gens': Counter(), 'hands': 0, 'intents': 0, 'bad': 0,
                'retired': Counter()}
        per_file[os.path.basename(path)] = info
        for lineno, line in enumerate(open(path, encoding='utf-8'), 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                # **조용히 넘기지 않는다.** 깨진 줄이 표본에서 사라지면
                # 남은 건수만 보고 "그 상황이 없었다"로 읽힌다.
                info['bad'] += 1
                malformed.append((os.path.basename(path), lineno))
                continue
            info['hands'] += 1
            for _it in (rec.get('intents') or []):
                if isinstance(_it, dict):
                    g = LK.archive_generation(_it)
                    gens[g] += 1
                    info['gens'][g] += 1
                    info['intents'] += 1
                    info['retired'].update(LK.retired_in(_it))
            hands += 1
            for it in (rec.get('intents') or []):
                plans[it.get('plan')] += 1
                if it.get('action') not in EXEC:
                    continue
                key = ('계획 블러프' if it.get('plan') in BLUFF else
                       '밸류(대조)' if it.get('plan') in VALUE else
                       '이탈 블러프' if it.get('plan') in DEVIATE else None)
                if key is None:
                    continue
                # 아카이브 파일들이 서로 겹친다. 같은 핸드를 여러 번 세지 않는다.
                uid = (rec.get('hand_no'), it.get('seat'), it.get('street'),
                       tuple(rec.get('board') or []), it.get('amt'))
                if uid in seen:
                    continue
                seen.add(uid)
                c, why = analyse(rec, it)
                if c:
                    grp[key].append(c)
                    if c.get('_degraded'):
                        degraded[c['_degraded']] += 1
                else:
                    drops[why or 'unknown'] += 1
    cases = grp['계획 블러프']

    # ---- 입력의 성질을 먼저 낸다. 결과 숫자보다 위에 온다 ----
    print('=== 입력 파일 · 세대 ===')
    print('%-46s %-22s %7s %8s %6s' % ('file', 'generation', 'hands', 'intents', 'bad'))
    for fn in sorted(per_file):
        i = per_file[fn]
        gs = ' '.join('%s:%d' % (k, v) for k, v in sorted(i['gens'].items())) or '-'
        print('%-46s %-22s %7d %8d %6d' % (fn[:46], gs, i['hands'], i['intents'], i['bad']))
        if i['retired']:
            print('%-46s   retired: %s' % ('', dict(i['retired'])))
    print('-' * 92)
    print('세대 합계: %s  (총 intent %d)'
          % (' '.join('%s=%d' % (k, gens[k]) for k in ('G0', 'G1', 'G2', 'G3')),
             sum(gens.values())))
    print('  G0/G1 에는 포지션이 **기록된 적이 없다**. legacy OOP 세대가 아니다.')
    print()
    print('=== 깨진 JSON 줄 ===')
    if not malformed:
        print('  없음')
    else:
        print('  %d줄' % len(malformed))
        for fn, ln in malformed[:20]:
            print('    %s:%d' % (fn, ln))
        if len(malformed) > 20:
            print('    ... 외 %d줄' % (len(malformed) - 20))
    print()
    print('=== 분석 탈락 사유 (조용히 사라지지 않게) ===')
    if not drops:
        print('  없음')
    for k, v in drops.most_common():
        print('  %-28s %d' % (k, v))
    if degraded:
        print('  -- 품질 저하(버리지 않음) --')
        for k, v in degraded.most_common():
            print('  %-28s %d' % (k, v))
    print()

    def med(rows, key):
        v = sorted(x[key] for x in rows if x.get(key) is not None)
        return v[len(v)//2] if v else float('nan')

    print('# 블러프 라인·레인지 일관성')
    print('# 아카이브 %d핸드, intent %d건' % (hands, sum(plans.values())))
    print('# 계획 블러프 %d건 · 밸류 %d건(대조) · 이탈 블러프 %d건\n'
          % (len(cases), len(grp['밸류(대조)']), len(grp['이탈 블러프'])))
    print('참고: `river_bluff` 계획은 아카이브 전체에서 %d건이다.'
          % plans.get('river_bluff', 0))
    print()
    if not cases:
        print('분석 가능한 케이스가 없다.')
        return

    print('## 집단 × 스트리트')
    for g in ('계획 블러프', '밸류(대조)', '이탈 블러프'):
        cs = Counter(c['street'] for c in grp[g])
        print('  %-12s %s' % (g, '  '.join('%s %d' % kv for kv in
                                           sorted(cs.items()))))
    print()

    print('## 계획·스트리트별 (계획 블러프)')
    for k, v in Counter('%s / %s' % (c['plan'], c['street'])
                        for c in cases).most_common():
        print('  %-28s %3d' % (k, v))
    print()

    print('## 세 집단 비교 — 중앙값을 나란히. 임계값은 두지 않는다')
    print('  %-28s %12s %12s %12s' % ('', '계획 블러프', '밸류(대조)', '이탈 블러프'))
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
        print('  %-28s %12s %12s %12s'
              % (label, fmt % med(cases, key), fmt % med(grp['밸류(대조)'], key),
                 fmt % med(grp['이탈 블러프'], key)))
    def inr(rows):
        return 100.0*sum(1 for c in rows if c['in_range'])/max(1, len(rows))
    print('  %-28s %11.0f%% %11.0f%% %11.0f%%'
          % ('복원 레인지 안에 있음', inr(cases), inr(grp['밸류(대조)']),
             inr(grp['이탈 블러프'])))
    print()

    print('## 분포 (10 / 25 / 50 / 75 / 90 분위) — 임계값 대신 분포를 본다')
    def dec(rows, key):
        v = sorted(x[key] for x in rows if x.get(key) is not None)
        if len(v) < 5:
            return None
        return [v[int(q*(len(v)-1))] for q in (.1, .25, .5, .75, .9)]
    for label, key, fmt in M:
        print('  %s' % label)
        for g in ('계획 블러프', '밸류(대조)', '이탈 블러프'):
            d = dec(grp[g], key)
            if d is None:
                print('    %-12s (표본 부족)' % g)
            else:
                print('    %-12s %s' % (g, '  '.join(fmt % x for x in d)))

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

    return _finish(malformed, a.allow_malformed)


if __name__ == '__main__':
    raise SystemExit(main())
