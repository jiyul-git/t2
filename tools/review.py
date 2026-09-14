#!/usr/bin/env python3
"""토너먼트 한 판을 사람이 읽는 형태로 되짚는다. **읽기 전용이다.**

  python3 tools/review.py review_2.jsonl --list
  python3 tools/review.py review_2.jsonl --hand 67
  python3 tools/review.py review_2.jsonl --flags
  python3 tools/review.py review_2.jsonl --pid 28
  python3 tools/review.py review_2.jsonl --memos memos.json --list

대상은 실행 폴더의 hand_archive2.jsonl 이다 (히어로 테이블 전 핸드).
bot_hands.jsonl 은 다른 테이블이라 여기서 읽지 않는다.

**intents 는 포스트플랍만 있다.** 프리플랍 판단은 기록되지 않으므로
프리플랍 줄에는 계획이 붙지 않는다. 이건 계측의 한계이지 버그가 아니다.

--flags 가 붙이는 표시는 전부 **의심**이다. 확정된 오류가 아니다.
근거는 CLAUDE.md 의 '현재 조사' 절에 적힌 것만 쓴다. 새 임계값을
발명하지 않는다 — 여기 쓰인 숫자(0.42, 8아웃, 25bb)는 전부 코드나
CLAUDE.md 에 이미 있던 값이다.
"""
import argparse, json, os, sys
from collections import defaultdict

STREETS = ('preflop', 'flop', 'turn', 'river')
KR = {'preflop': '프리플랍', 'flop': '플랍', 'turn': '턴', 'river': '리버'}
ACT = {'fold': '폴드', 'call': '콜', 'check': '체크', 'bet': '벳',
       'raise': '레이즈', 'allin': '올인'}
SUIT = {'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}


def C(n):
    try: return '{:,}'.format(int(n))
    except Exception: return str(n)


def card(c):
    return c[0].upper() + SUIT.get(c[1:].lower(), c[1:]) if c else '--'


def cards(cs):
    return ' '.join(card(c) for c in (cs or [])) or '--'


def load(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def pid_of(rec, seat):
    return ((rec.get('profiles') or {}).get(str(seat)) or {}).get('id')


def who(rec, seat):
    p = (rec.get('pos') or {}).get(str(seat), '')
    me = ' ←나' if seat == rec.get('hero') else ''
    return '%s번(%s)%s' % (seat, p, me)


# ---------- 팟 재구성 ----------
def street_pots(rec):
    """스트리트별 (시작 팟, [(seat, act, amt, 그 시점 팟)]) 을 만든다.

    audit.py 의 규칙 검사와 같은 방식으로 contribs 를 따라간다.
    여기서는 검사하지 않고 금액만 복원한다."""
    sb, bb = rec['blinds'][0], rec['blinds'][1]
    seat_of = {v: int(k) for k, v in (rec.get('pos') or {}).items()}
    by = defaultdict(list)
    for e in rec.get('full_log') or []:
        by[e[0]].append(e)
    carried = 0.0
    out = []
    for st in STREETS:
        acts = by.get(st) or []
        if not acts:
            continue
        contrib = defaultdict(float)
        if st == 'preflop':
            if 'SB' in seat_of: contrib[seat_of['SB']] = sb
            if 'BB' in seat_of: contrib[seat_of['BB']] = bb
        cur = bb if st == 'preflop' else 0
        rows = []
        for (_, seat, act, amt) in acts:
            tocall = max(0, cur - contrib[seat])
            pot_now = carried + sum(contrib.values())
            if act in ('bet', 'raise') and amt:
                cur = max(cur, amt); contrib[seat] = amt
            elif act == 'call':
                contrib[seat] = cur
            elif act == 'allin':
                if amt: cur = max(cur, amt)
                contrib[seat] = max(contrib[seat], amt or contrib[seat])
            rows.append({'seat': seat, 'act': act, 'amt': amt,
                         'pot_before': pot_now, 'tocall': tocall})
        out.append({'street': st, 'pot_start': carried, 'rows': rows})
        carried += sum(contrib.values())
    return out


# ---------- 의심 표시 ----------
def flags(rec):
    """CLAUDE.md 에 이미 적힌 문제만 표시한다. 전부 '의심'이다."""
    out = []
    board = rec.get('board') or []

    for i in rec.get('intents') or []:
        st, seat = i.get('street'), i.get('seat')
        plan = i.get('plan')
        eq = i.get('eq') or 0
        rel = i.get('rel') or 0
        outs = i.get('outs') or 0
        made = i.get('made') or 0
        tail = 'plan=%s eq=%.3f rel=%.2f outs=%d made=%d' % (plan, eq, rel, outs, made)

        # audit.py:171 과 같은 검사
        if i.get('action') in ('bet', 'raise') and plan in ('giveup', 'showdown'):
            out.append((st, seat, '포기계획인데 벳', tail))
        # CLAUDE.md: A∩B 14건 — 직접 드로우인데 giveup
        if plan == 'giveup' and outs >= 8:
            out.append((st, seat, '드로우인데 포기', tail))
        # CLAUDE.md 핵심 구조 문제: 진입은 eq(미래 포함), 내부는 rel(현재만)
        if eq >= 0.42 and rel <= 0.10:
            out.append((st, seat, 'eq-rel 반대 방향', tail))
        # CLAUDE.md: 세미블러프 선점 → made 0 이 밸류 계획을 받는다
        if str(plan).startswith('value') and made == 0:
            out.append((st, seat, '메이드 없는데 밸류계획', tail))
        # audit.py 데이터 검사
        if st == 'river' and outs > 0:
            out.append((st, seat, '리버 드로우 잔존', tail))

    # 프리플랍 오픈 올인. CLAUDE.md 의 34~37bb 미해명 건과 같은 종류다.
    sb_amt, bb_amt = rec['blinds'][0], rec['blinds'][1]
    stacks0 = {int(k): float(v) for k, v in (rec.get('stacks_before') or {}).items()}
    raised = False
    for (st, seat, act, amt) in rec.get('full_log') or []:
        if st != 'preflop':
            break
        if act == 'allin' and not raised and seat != rec.get('hero'):
            bbs = stacks0.get(seat, 0) / max(1, bb_amt)
            if bbs >= 25:                      # CLAUDE.md 가 쓰던 구분점
                out.append(('preflop', seat, '깊은 스택 오픈 올인',
                            '%.0fbb' % bbs))
        if act in ('raise', 'allin'):
            raised = True

    # 사이즈는 여기서 판정하지 않는다. 무엇이 '큰' 사이즈인지의 기준이
    # 코드에도 CLAUDE.md 에도 없다 — 없는 임계값을 지어내면 h1 의 2.5bb
    # 오픈까지 걸린다 (실제로 그렇게 짰다가 85건이 나왔다).
    # 분포는 --sizes 가 판정 없이 그대로 보여준다.
    return out


def sizes(rows):
    """포스트플랍 벳/레이즈가 팟의 몇 %였는지. **판정하지 않는다.**

    프리플랍은 빼고 센다. 프리플랍 오픈은 관습적으로 bb 로 재지 팟으로
    재지 않는다 — 팟 대비로 재면 표준 오픈이 전부 '과대'로 나온다."""
    vals = []
    for rec in rows:
        for sp in street_pots(rec):
            if sp['street'] == 'preflop':
                continue
            cur = 0
            for r in sp['rows']:
                if r['act'] in ('bet', 'raise', 'allin') and r['amt'] and r['pot_before'] > 0:
                    add = r['amt'] - cur          # 레이즈는 증분이 실제로 얹는 돈
                    if add > 0:
                        vals.append((add / r['pot_before'], rec['hand_no'],
                                     sp['street'], r['seat'], add, r['pot_before'],
                                     r['act']))
                    cur = max(cur, r['amt'])
    return vals


# ---------- 출력 ----------
def show_list(rows, memos, only_pid=None, with_flags=False):
    for rec in rows:
        if only_pid is not None:
            if not any(pid_of(rec, s) == only_pid for s in (rec.get('pos') or {})):
                continue
        res = rec.get('result') or {}
        line = []
        for sp in street_pots(rec):
            tags = []
            for r in sp['rows']:
                t = ACT.get(r['act'], r['act'])
                if r['act'] in ('bet', 'raise') and r['amt']:
                    t += C(r['amt'])
                tags.append('%s%s' % (r['seat'], t))
            line.append('%s %s' % (KR[sp['street']], ' '.join(tags)))
        w = ', '.join(who(rec, s) for s in (res.get('winners') or []))
        fl = flags(rec) if with_flags else []
        print('#%-4s L%-2s %s' % (rec['hand_no'], rec.get('level', '?'),
                                  ' | '.join(line)))
        print('      → %s · 팟 %s · %s%s' % (
            {'fold': '폴드종료', 'showdown': '쇼다운'}.get(res.get('how'), res.get('how')),
            C(res.get('pot')), w, '   ⚑%d' % len(fl) if fl else ''))
        for (st, seat, tag, detail) in fl:
            print('        ⚑ %s %s — %s  %s' % (KR.get(st, st), who(rec, seat), tag, detail))


def show_hand(rec, memos):
    res = rec.get('result') or {}
    f = rec.get('field') or {}
    print('=' * 68)
    print('HAND %s   레벨 %s (%s/%s)   히어로 %s' % (
        rec['hand_no'], rec.get('level'), C(rec['blinds'][0]), C(rec['blinds'][1]),
        who(rec, rec.get('hero'))))
    print('필드 %s/%s 남음 · ITM %s · 평균 %s%s' % (
        f.get('remaining'), f.get('entries'), f.get('itm'), C(f.get('avg') or 0),
        ' · 버블' if f.get('bubble') else ''))
    sb = rec.get('stacks_before') or {}
    print('스택  ' + '  '.join('%s %s' % (who(rec, int(s)).split('(')[0], C(v))
                               for s, v in sorted(sb.items(), key=lambda kv: int(kv[0]))))
    for s, h in sorted((rec.get('hole') or {}).items(), key=lambda kv: int(kv[0])):
        pid = pid_of(rec, int(s))
        note = (memos or {}).get(str(pid))
        prof = (rec.get('profiles') or {}).get(s) or {}
        print('  %-12s %s   [%s pid %s]%s' % (
            who(rec, int(s)), cards(h), prof.get('type', '?'), pid,
            '  메모: ' + note if note else ''))

    # intents 는 (스트리트, 좌석) 안에서 idx 순으로 '그 사람의 n번째 결정'이다.
    # 그래서 액션을 훑으면서 하나씩 꺼내 짝지어야 한다. 통째로 붙이면
    # 체크와 콜 밑에 같은 계획이 두 번씩 찍힌다.
    ints = defaultdict(list)
    for i in sorted(rec.get('intents') or [], key=lambda x: x.get('idx') or 0):
        ints[(i.get('street'), i.get('seat'))].append(i)
    taken = defaultdict(int)

    board = rec.get('board') or []
    upto = {'preflop': 0, 'flop': 3, 'turn': 4, 'river': 5}
    for sp in street_pots(rec):
        st = sp['street']
        print('─' * 68)
        print('%s  %s   (시작 팟 %s)' % (
            KR[st], cards(board[:upto[st]]) if upto[st] else '', C(sp['pot_start'])))
        for r in sp['rows']:
            t = ACT.get(r['act'], r['act'])
            if r['act'] in ('bet', 'raise') and r['amt']:
                t += ' ' + C(r['amt'])
            extra = ''
            if r['act'] in ('call', 'fold') and r['tocall']:
                extra = '  (콜 비용 %s / 팟 %s)' % (C(r['tocall']), C(r['pot_before']))
            print('   %-14s %s%s' % (who(rec, r['seat']), t, extra))
            k = (st, r['seat'])
            lst = ints.get(k) or []
            i = lst[taken[k]] if taken[k] < len(lst) else None
            taken[k] += 1
            if i:
                print('      └ 계획 %-14s rel %.2f  eq %.3f  outs %-2d made %d  spr %s'
                      % (i.get('plan'), i.get('rel') or 0, i.get('eq') or 0,
                         i.get('outs') or 0, i.get('made') or 0, i.get('spr')))
                # 계획이 정한 액션과 실제가 다르면 그게 응답 단계에서 갈린 것이다
                ia, ra = i.get('intent_act'), i.get('response_act')
                if ra and ra != ia:
                    print('        계획은 %s → 실제 %s (상대 벳에 대한 응답)'
                          % (ACT.get(ia, ia), ACT.get(ra, ra)))
                # why 는 스트리트별로 누적된다 — 이 스트리트 것만 거른다
                for w in (i.get('why') or []):
                    if w.startswith(st + ':'):
                        print('        %s' % w)
                if i.get('eq_delta') is not None:
                    print('        eq_current %.3f  eq_delta %+.3f  (기록 전용)'
                          % (i.get('eq_current') or 0, i.get('eq_delta') or 0))
    print('─' * 68)
    print('결과  %s · 팟 %s · 승 %s' % (
        {'fold': '폴드 종료', 'showdown': '쇼다운'}.get(res.get('how'), res.get('how')),
        C(res.get('pot')),
        ', '.join(who(rec, s) for s in (res.get('winners') or []))))
    fl = flags(rec)
    if fl:
        print('의심 표시 (확정 아님)')
        for (st, seat, tag, detail) in fl:
            print('   ⚑ %s %s — %s  %s' % (KR.get(st, st), who(rec, seat), tag, detail))


def show_flags(rows):
    by = defaultdict(list)
    for rec in rows:
        for (st, seat, tag, detail) in flags(rec):
            by[tag].append((rec['hand_no'], st, seat, detail))
    print('핸드 %d개 · 의심 표시는 확정 오류가 아니다' % len(rows))
    for tag, items in sorted(by.items(), key=lambda kv: -len(kv[1])):
        hs = sorted({h for (h, _, _, _) in items})
        print('\n%s  %d건 / %d핸드' % (tag, len(items), len(hs)))
        print('  핸드: %s' % ' '.join('h%s' % h for h in hs[:40]))
        for (h, st, seat, detail) in items[:5]:
            print('    h%-4s %-8s %s번  %s' % (h, KR.get(st, st), seat, detail))
        if len(items) > 5:
            print('    ... 외 %d건' % (len(items) - 5))


def show_sizes(rows):
    vals = sizes(rows)
    if not vals:
        print('포스트플랍 벳/레이즈가 없다'); return
    vals.sort()
    n = len(vals)
    def q(p): return vals[min(n - 1, int(n * p))][0]
    print('포스트플랍 벳/레이즈 %d건 — 팟 대비 (판정 아님, 분포만)' % n)
    print('  최소 %.0f%%   25%% %.0f%%   중앙 %.0f%%   75%% %.0f%%   최대 %.0f%%'
          % (vals[0][0]*100, q(.25)*100, q(.5)*100, q(.75)*100, vals[-1][0]*100))
    band = [('~50%', 0, .5), ('50~75%', .5, .75), ('75~100%', .75, 1.0),
            ('100~150%', 1.0, 1.5), ('150%~', 1.5, 9e9)]
    for name, lo, hi in band:
        k = sum(1 for v in vals if lo <= v[0] < hi)
        print('  %-9s %4d건  %5.1f%%  %s' % (name, k, k / n * 100, '█' * int(k / n * 40)))
    print('\n가장 큰 10건')
    for (r, h, st, seat, add, pot, act) in vals[-10:][::-1]:
        print('  h%-4s %-8s %s번  %-6s %s / 팟 %s = %.0f%%'
              % (h, KR.get(st, st), seat, ACT.get(act, act), C(add), C(pot), r * 100))


def show_pid(rows, pid, memos):
    seen = []
    prof = None
    for rec in rows:
        for s in (rec.get('pos') or {}):
            if pid_of(rec, int(s)) == pid:
                seen.append((rec, int(s)))
                prof = prof or (rec.get('profiles') or {}).get(s)
                break
    if not seen:
        print('pid %s 는 이 아카이브에 없다' % pid); return
    print('pid %s  %s   %d핸드' % (pid, (prof or {}).get('type', '?'), len(seen)))
    note = (memos or {}).get(str(pid))
    if note: print('메모: %s' % note)
    t = (prof or {}).get('temper') or {}
    if t:
        print('성향  ' + '  '.join('%s %.1f' % (k, v) for k, v in sorted(t.items())))
    cnt = defaultdict(int)
    for rec, seat in seen:
        for i in rec.get('intents') or []:
            if i.get('seat') == seat:
                cnt[i.get('plan')] += 1
    if cnt:
        print('포스트플랍 계획  ' +
              '  '.join('%s %d' % (k, v) for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])))
    print('핸드: %s' % ' '.join('h%s' % r['hand_no'] for r, _ in seen))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--hand', type=int)
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--flags', action='store_true')
    ap.add_argument('--pid', type=int)
    ap.add_argument('--sizes', action='store_true')
    ap.add_argument('--memos')
    a = ap.parse_args()
    rows = load(a.file)
    memos = {}
    if a.memos and os.path.exists(a.memos):
        raw = json.load(open(a.memos, encoding='utf-8'))
        # 키가 't2memo:28' 이면 28 로 줄인다
        memos = {k.split(':')[-1]: v for k, v in raw.items()}
    if a.hand is not None:
        cand = [r for r in rows if r['hand_no'] == a.hand]
        if not cand:
            sys.exit('핸드 %d 가 없다 (범위 %s~%s)'
                     % (a.hand, rows[0]['hand_no'], rows[-1]['hand_no']))
        show_hand(cand[-1], memos)
    elif a.pid is not None:
        show_pid(rows, a.pid, memos)
    elif a.sizes:
        show_sizes(rows)
    elif a.flags:
        show_flags(rows)
    else:
        show_list(rows, memos, with_flags=a.list and a.flags)


if __name__ == '__main__':
    main()
