#!/usr/bin/env python3
"""A/B 짝지은 비교용 지표. plan.py 는 읽기만 한다.

collect.py 를 `--seed0 N` 으로 돌리면 토너먼트 시드가 결정적이라
같은 시드 목록으로 두 코드 상태를 돌려 **paired comparison** 을 할 수 있다.
(검증: 같은 --seed0 로 두 번 돌리면 파일이 바이트 단위로 같다)

    python3 tools/collect.py 6000 A.jsonl --seed0 900000    # 대조군
    (코드 변경)
    python3 tools/collect.py 6000 B.jsonl --seed0 900000    # 실험군
    python3 tools/ab_metrics.py A.jsonl                     # 단독
    python3 tools/ab_metrics.py A.jsonl B.jsonl             # 비교

주의 — 코드를 바꾸면 rng 소비 순서가 달라져 **같은 시드라도 게임 전개가
갈라진다**. 시드 고정은 초기 조건(딜·좌석·프로필)을 맞출 뿐 완전한 짝짓기가
아니다. 그래도 무작위 시드보다 분산이 크게 준다. 이 한계를 결과에 적는다.
"""
import os, sys, json, math, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def street_why(i):
    pre = '%s: ' % i['street']
    return [x[len(pre):] for x in
            (i['why'] if isinstance(i['why'], list) else [i['why']])
            if x.startswith(pre)]


def load_raw(path):
    return [json.loads(l) for l in open(path)]


def metrics(path):
    recs = load_raw(path)
    m = collections.OrderedDict()
    m['핸드'] = len(recs)

    plans = collections.Counter()
    acts = collections.Counter()
    nblock_fire = nblock_live = 0
    intents = 0
    for r in recs:
        for i in r.get('intents', []):
            intents += 1
            plans[i.get('plan')] += 1
            if i.get('action'):
                acts[i['action']] += 1
            # **발화와 생존은 같은 분모에서 세야 한다.** block 은 플랍에서만
            # 태어나는데 살아남으면 턴·리버 intent 에도 같은 라벨로 남는다.
            # 전 스트리트에서 세면 생존이 발화보다 커져 생존율이 1 을 넘는다
            # (실측 36 발화 vs 48 생존).
            if i.get('street') != 'flop':
                continue
            if any('블락벳으로 가격 통제' in x for x in street_why(i)):
                nblock_fire += 1
            if i.get('plan') == 'block':
                nblock_live += 1
    m['intent'] = intents
    m['block 발화(플랍)'] = nblock_fire
    m['block 생존(플랍)'] = nblock_live
    m['block 생존율'] = (nblock_live / nblock_fire) if nblock_fire else float('nan')
    for k in ('value_3street', 'value_2street', 'pot_control', 'block',
              'semibluff', 'bluff_2street', 'showdown', 'giveup', 'trap',
              'thin_river', 'river_bluff'):
        m['plan:' + k] = plans.get(k, 0)
    for k in ('bet', 'raise', 'call', 'check', 'fold'):
        m['act:' + k] = acts.get(k, 0)
    ag = acts['bet'] + acts['raise']
    m['공격률(bet+raise)/전체'] = ag / max(1, sum(acts.values()))
    m['AF (bet+raise)/call'] = ag / max(1, acts['call'])

    # 프리플랍 지표 — full_log 로 센다
    vpip = pfr = opp = 0
    pots = []
    byplan = collections.defaultdict(lambda: [0, 0])   # 플랍 계획 → [손익합, 좌석수]
    nsd = collections.Counter()                        # 쇼다운 도달 핸드 수
    skipped = 0
    for r in recs:
        fl = [tuple(x) for x in (r.get('full_log') or [])]
        seats = [int(s) for s in (r.get('seats') or [])]
        pre = [x for x in fl if x[0] == 'preflop']
        acted = set(x[1] for x in pre)
        for s in seats:
            if s not in acted:
                continue
            opp += 1
            mine = [x for x in pre if x[1] == s]
            if any(x[2] in ('call', 'raise', 'bet', 'allin') for x in mine):
                vpip += 1
            if any(x[2] in ('raise', 'allin') for x in mine):
                pfr += 1
        contrib = collections.Counter()
        for (st, s, a, amt) in fl:
            if a in ('raise', 'bet', 'call', 'allin'):
                contrib[(st, s)] = max(contrib[(st, s)], amt)
        pots.append(sum(contrib.values()))

        # ---- 손익. **제로섬 검산을 통과한 핸드만 쓴다** ----
        # 이 토너먼트 하네스는 finish_hand 에서 빈 자리에 새 플레이어를 앉히고
        # 테이블을 재조정한다. 그 과정이 스택에 칩을 주입해서 델타가 깨진다.
        # 실측: 200핸드 중 참가 좌석으로 제한해도 4건(2%)이 합계가 0이 아니다.
        # 그런 핸드를 섞으면 EV 비교가 통째로 오염되므로 제외하고 건수를 적는다.
        before = r.get('stacks_before') or {}
        after = r.get('stacks_after') or {}
        ks = [str(s) for s in seats]
        delta = {k: after.get(k, 0) - before.get(k, 0) for k in ks}
        if sum(delta.values()) != 0:
            skipped += 1
            continue
        # 쇼다운/비쇼다운 **전체 합**은 닫힌 테이블에서 구조적으로 0 이라
        # 지표가 되지 못한다(실측 확인). 의미 있는 것은 **계획별 좌석 손익** 이다 —
        # "그 계획을 세운 자리가 돈을 버는가".
        # 좌석당 한 번만 센다. 기준은 **플랍 계획** 이다(block 은 플랍에서만 태어난다).
        flopplan = {}
        for i in r.get('intents', []):
            if i.get('street') == 'flop' and i.get('seat') is not None:
                flopplan.setdefault(int(i['seat']), i.get('plan'))
        folded = set(s for (st, s, a, amt) in fl if a == 'fold')
        alive = [s for s in seats if s not in folded]
        sd = len(alive) >= 2 and any(x[0] == 'river' for x in fl)
        nsd[sd] += 1
        for s, pl in flopplan.items():
            if str(s) not in delta:
                continue
            byplan[pl][0] += delta[str(s)]
            byplan[pl][1] += 1
    m['VPIP'] = vpip / max(1, opp)
    m['PFR'] = pfr / max(1, opp)
    m['평균 팟'] = sum(pots) / max(1, len(pots))
    m['EV 제외 핸드(칩 주입)'] = skipped
    m['쇼다운 도달 핸드'] = nsd[True]
    m['쇼다운 도달률'] = nsd[True] / max(1, nsd[True] + nsd[False])
    for k in ('value_3street', 'value_2street', 'pot_control', 'block',
              'semibluff', 'bluff_2street', 'showdown', 'giveup'):
        w, n = byplan.get(k, [0, 0])
        m['EV/좌석 ' + k] = (w / n) if n else float('nan')
        m['n ' + k] = n
    return m


def main():
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        return
    A = metrics(paths[0])
    if len(paths) == 1:
        print('=' * 74)
        print('단독 — %s' % os.path.basename(paths[0]))
        print('=' * 74)
        for k, v in A.items():
            print('   %-24s %s' % (k, ('%.4f' % v) if isinstance(v, float) else v))
        return
    B = metrics(paths[1])
    print('=' * 90)
    print('A/B 비교   A=%s   B=%s'
          % (os.path.basename(paths[0]), os.path.basename(paths[1])))
    print('=' * 90)
    print('%-26s %14s %14s %14s' % ('지표', 'A(대조)', 'B(실험)', '차이'))
    print('-' * 90)
    for k in A:
        a, b = A[k], B.get(k, 0)
        if isinstance(a, float) or isinstance(b, float):
            d = (b - a) if not (isinstance(a, float) and math.isnan(a)) else float('nan')
            print('%-26s %14.4f %14.4f %+14.4f' % (k, a, b, d))
        else:
            print('%-26s %14d %14d %+14d' % (k, a, b, b - a))
    print()
    print('주의 — 코드를 바꾸면 rng 소비 순서가 달라져 같은 시드라도 게임 전개가')
    print('갈라진다. 시드 고정은 초기 조건만 맞춘다. 완전한 짝짓기가 아니다.')


if __name__ == '__main__':
    main()
