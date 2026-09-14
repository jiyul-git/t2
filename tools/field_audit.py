#!/usr/bin/env python3
"""필드 감사 — 성향이 행동에 닿는가, 분포가 의도대로인가. **읽기 전용이다.**

  python3 tools/field_audit.py review_2.jsonl --traits    성향 → 행동 상관
  python3 tools/field_audit.py review_2.jsonl --defend    BB 방어
  python3 tools/field_audit.py review_2.jsonl --stage     단계별(버블·ITM) 변화
  python3 tools/field_audit.py review_2.jsonl --exploit   상대 읽기가 판단을 바꿨나
  python3 tools/field_audit.py review_2.jsonl --plan      계획 ↔ 집행 일치
  python3 tools/field_audit.py --dist                     생성기 분포 (아카이브 불필요)
  python3 tools/field_audit.py --formats                  대회 종류별 필드

주의
- 아카이브는 **히어로 테이블만** 담는다. 필드 전체가 아니다.
- 단계별(--stage)은 버블·ITM 구간의 핸드 수가 작다. 한 대회로는 판단할 수
  없다. 여러 대회를 모아야 한다.
- 타입별 평균은 그 타입에 속한 봇이 1~3명뿐이라 사실상 개인 통계다.
  타입이 아니라 temper 값으로 묶은 쪽(--traits 의 구간표)이 더 믿을 만하다.
"""
import argparse, json, math, os, random, sys
from collections import Counter, defaultdict

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)

STREETS = ('flop', 'turn', 'river')


def load(p):
    with open(p, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def spearman(xs, ys):
    """순위상관. numpy 없이."""
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0]*len(v); i = 0
        while i < len(o):
            j = i
            while j+1 < len(o) and v[o[j+1]] == v[o[i]]: j += 1
            avg = (i+j)/2.0 + 1
            for k in range(i, j+1): r[o[k]] = avg
            i = j+1
        return r
    a, b = rank(xs), rank(ys); n = len(xs)
    ma, mb = sum(a)/n, sum(b)/n
    num = sum((x-ma)*(y-mb) for x, y in zip(a, b))
    da = sum((x-ma)**2 for x in a)**.5
    db = sum((y-mb)**2 for y in b)**.5
    return num/(da*db) if da and db else 0.0


def collect(rows, min_bb=0):
    """pid 별 관측 행동. min_bb 이상 스택일 때만 세면 짧은 스택 효과가 빠진다."""
    prof = {}; st = defaultdict(lambda: defaultdict(float))
    for r in rows:
        hero = r.get('hero'); bb = r['blinds'][1]; pos = r.get('pos') or {}
        s0 = {int(k): float(v) for k, v in (r.get('stacks_before') or {}).items()}
        pid = {int(s): p.get('id') for s, p in (r.get('profiles') or {}).items()}
        for s, p in (r.get('profiles') or {}).items():
            if int(s) != hero: prof.setdefault(p.get('id'), p)
        seen = set(); raises = 0
        for (street, seat, a, amt) in r['full_log']:
            if street != 'preflop': break
            if seat != hero and seat in pid and seat not in seen:
                seen.add(seat)
                d = st[pid[seat]]
                if s0.get(seat, 0)/bb >= min_bb:
                    d['pf_n'] += 1
                    if a in ('call', 'raise', 'allin'): d['vpip'] += 1
                    if a in ('raise', 'allin'): d['pfr'] += 1
                # BB 가 단일 레이즈에 직면한 경우만 방어율로 센다
                if pos.get(str(seat)) == 'BB' and raises == 1:
                    d['bb_face'] += 1
                    if a != 'fold': d['bb_def'] += 1
            if a in ('raise', 'allin'): raises += 1
        for (street, seat, a, amt) in r['full_log']:
            if street not in STREETS or seat == hero or seat not in pid: continue
            d = st[pid[seat]]
            d['post_n'] += 1
            if a in ('bet', 'raise', 'allin'): d['post_aggr'] += 1
            if a == 'fold': d['post_fold'] += 1
    return prof, st


def cmd_traits(rows, min_n=25):
    prof, st = collect(rows, min_bb=15)
    keep = [p for p in st if st[p]['pf_n'] >= min_n and p in prof]
    T = lambda p, k: (prof[p].get('temper') or {}).get(k)
    C = lambda p, k: (prof[p].get('concepts') or {}).get(k)
    tests = [
        ('looseness  → VPIP',       lambda p: T(p, 'looseness'),  lambda p: st[p]['vpip']/st[p]['pf_n']),
        ('aggression → PFR',        lambda p: T(p, 'aggression'), lambda p: st[p]['pfr']/st[p]['pf_n']),
        ('aggression → 포스트 공격', lambda p: T(p, 'aggression'), lambda p: st[p]['post_aggr']/max(1, st[p]['post_n'])),
        ('bluff      → 포스트 공격', lambda p: C(p, 'bluff'),      lambda p: st[p]['post_aggr']/max(1, st[p]['post_n'])),
        ('discipline → 포스트 폴드', lambda p: T(p, 'discipline'), lambda p: st[p]['post_fold']/max(1, st[p]['post_n'])),
        ('pf_defend  → BB 방어율',  lambda p: C(p, 'pf_defend'),  lambda p: st[p]['bb_def']/max(1, st[p]['bb_face'])),
    ]
    print('프리플랍 %d회 이상 본 봇 %d명 (15bb 이상일 때만 집계)\n' % (min_n, len(keep)))
    for name, fx, fy in tests:
        pts = [(fx(p), fy(p)) for p in keep if fx(p) is not None]
        if len(pts) < 8:
            print('%-26s 표본부족 %d' % (name, len(pts))); continue
        rho = spearman([x for x, _ in pts], [y for _, y in pts]); n = len(pts)
        t = rho*math.sqrt((n-2)/max(1e-9, 1-rho*rho))
        mark = '강함' if abs(rho) >= 0.6 else ('있음' if abs(rho) >= 0.35 else
               ('약함' if abs(rho) >= 0.2 else '없음'))
        print('%-26s rho %+.2f  n=%-3d t=%+.2f  %s' % (name, rho, n, t, mark))

    # 봇 하나하나가 아니라 성향 값으로 묶어 본다 (표본이 커진다)
    print('\nlooseness 구간별 VPIP — 봇이 아니라 상황 단위로 센다')
    b = defaultdict(lambda: [0, 0])
    for r in rows:
        hero = r.get('hero'); bb = r['blinds'][1]; seen = set()
        s0 = {int(k): float(v) for k, v in (r.get('stacks_before') or {}).items()}
        for (street, seat, a, amt) in r['full_log']:
            if street != 'preflop': break
            if seat == hero or seat in seen: continue
            seen.add(seat)
            if s0.get(seat, 0)/bb < 15: continue
            lo = ((r.get('profiles') or {}).get(str(seat)) or {}).get('temper', {}).get('looseness')
            if lo is None: continue
            k = '%d~%d' % (int(lo//2)*2, int(lo//2)*2+2)
            b[k][0] += 1
            if a in ('call', 'raise', 'allin'): b[k][1] += 1
    for k in sorted(b, key=lambda x: int(x.split('~')[0])):
        n, v = b[k]
        if n >= 20: print('  looseness %-6s n=%-4d VPIP %.0f%%' % (k, n, 100*v/n))


def cmd_defend(rows):
    face = fold = call = rr = 0
    byc = defaultdict(lambda: [0, 0])
    for r in rows:
        hero = r.get('hero'); pos = r.get('pos') or {}; bb = r['blinds'][1]
        s0 = {int(k): float(v) for k, v in (r.get('stacks_before') or {}).items()}
        raises = 0
        for (street, seat, a, amt) in r['full_log']:
            if street != 'preflop': break
            if pos.get(str(seat)) == 'BB' and raises == 1 and seat != hero:
                face += 1
                if a == 'fold': fold += 1
                elif a == 'call': call += 1
                else: rr += 1
                pd = (((r.get('profiles') or {}).get(str(seat)) or {})
                      .get('concepts') or {}).get('pf_defend')
                if pd is not None and s0.get(seat, 0)/bb >= 15:
                    k = 'pf_defend %d대' % int(pd)
                    byc[k][0] += 1
                    if a != 'fold': byc[k][1] += 1
            if a in ('raise', 'allin'): raises += 1
    if not face: print('BB 방어 표본 없음'); return
    print('BB 가 단일 레이즈에 직면 %d회 (봇만)' % face)
    print('  폴드 %d (%.0f%%)  콜 %d (%.0f%%)  리레이즈 %d (%.0f%%)'
          % (fold, 100*fold/face, call, 100*call/face, rr, 100*rr/face))
    print('  → 방어율 %.0f%%' % (100*(face-fold)/face))
    print('\npf_defend 개념별 (15bb 이상)')
    for k in sorted(byc):
        n, d = byc[k]
        if n >= 6: print('  %-14s n=%-3d 방어율 %.0f%%' % (k, n, 100*d/n))


def cmd_stage(rows):
    def stage(r):
        f = r.get('field') or {}
        rem = f.get('remaining'); itm = f.get('itm') or 15
        if rem is None: return None
        if rem > itm*3: return '1 초반'
        if rem > itm*1.3: return '2 중반'
        if rem > itm: return '3 버블 직전'
        if rem > 9: return '4 인더머니'
        return '5 파이널'
    S = defaultdict(lambda: defaultdict(float))
    for r in rows:
        k = stage(r)
        if not k: continue
        hero = r.get('hero'); bb = r['blinds'][1]; pos = r.get('pos') or {}
        s0 = {int(x): float(v) for x, v in (r.get('stacks_before') or {}).items()}
        d = S[k]; d['hands'] += 1
        seen = set(); raises = 0
        for (street, seat, a, amt) in r['full_log']:
            if street != 'preflop': break
            if seat != hero and seat in s0:
                if seat not in seen:
                    seen.add(seat)
                    if s0[seat]/bb >= 15:
                        d['pf_n'] += 1
                        if a in ('call', 'raise', 'allin'): d['vpip'] += 1
                    if pos.get(str(seat)) == 'BB' and raises == 1:
                        d['bb_face'] += 1
                        if a != 'fold': d['bb_def'] += 1
                d['depth_n'] += 1; d['depth'] += s0[seat]/bb
            if a in ('raise', 'allin'): raises += 1
        for (street, seat, a, amt) in r['full_log']:
            if street not in STREETS or seat == hero: continue
            d['post_n'] += 1
            if a in ('bet', 'raise', 'allin'): d['post_aggr'] += 1
    print('%-14s %5s %8s %7s %12s %10s' % ('단계', '핸드', '평균스택', 'VPIP', 'BB방어', '포스트공격'))
    for k in sorted(S):
        d = S[k]
        print('%-14s %5d %7.0fbb %6.0f%% %7.0f%%(%3d) %9.0f%%' % (
            k, d['hands'], d['depth']/max(1, d['depth_n']),
            100*d['vpip']/max(1, d['pf_n']),
            100*d['bb_def']/max(1, d['bb_face']), d['bb_face'],
            100*d['post_aggr']/max(1, d['post_n'])))
    print('\n버블·ITM 구간은 한 대회에서 핸드가 몇십 개뿐이다. 이 표 하나로')
    print('판단하지 말 것 — 여러 대회를 모아야 한다.')
    # 버블팩터는 직접 계산할 수 있다. 신호가 있는지와 행동이 바뀌는지는 별개다.
    try:
        import icm, statistics as ST
        pays = [100, 62, 44, 34, 27, 22, 18, 15, 12]
        B = defaultdict(list)
        for r in rows:
            k = stage(r)
            f = r.get('field') or {}
            rem = f.get('remaining'); itm = f.get('itm') or 15
            sts = [float(v) for v in (r.get('stacks_before') or {}).values() if float(v) > 0]
            if not k or not rem or len(sts) < 2: continue
            favg = f.get('avg') or (sum(sts)/len(sts))
            B[k].extend(icm.table_bf(sts, i, rem, itm, pays, 0.0, favg)
                        for i in range(len(sts)))
        print('\n같은 스택으로 버블팩터를 직접 계산하면 (신호 자체는 있는가)')
        for k in sorted(B):
            v = sorted(B[k])
            print('  %-14s n=%-4d 중앙 %.2f  (최소 %.2f ~ 최대 %.2f)'
                  % (k, len(v), ST.median(v), v[0], v[-1]))
    except Exception as e:
        print('  (버블팩터 계산 실패: %s)' % e)


def cmd_exploit(rows):
    import re
    rd = [x for r in rows for x in (r.get('reads') or [])]
    print('reads 기록 %d건' % len(rd))
    if rd:
        print('  표본 n>0 인 읽기 %d건  (최대 n=%d)'
              % (sum(1 for x in rd if x['n'] > 0), max(x['n'] for x in rd)))
        print('  확신도  0~.3 %d / .3~.6 %d / .6+ %d' % (
            sum(1 for x in rd if x['confidence'] <= 0.3),
            sum(1 for x in rd if 0.3 < x['confidence'] <= 0.6),
            sum(1 for x in rd if x['confidence'] > 0.6)))
    whys = [w for r in rows for i in (r.get('intents') or []) for w in (i.get('why') or [])]
    print('\nwhy %d줄 중 상대 조정이 실제로 들어간 것' % len(whys))
    c = Counter()
    for w in whys:
        m = re.search(r'상대 폴드성향 ([+-][\d.]+)%p → 포기 문턱 ([\d.]+)', w)
        if m: c[(m.group(1), m.group(2))] += 1
    if c:
        print('  포기 문턱 조정:')
        for k, v in sorted(c.items()): print('    %s%%p → %s   %d건' % (k[0], k[1], v))
        th = sorted(float(k[1]) for k in c)
        print('    문턱이 움직인 폭: %.2f ~ %.2f' % (th[0], th[-1]))
    r1 = r2 = 0
    for w in whys:
        if '사이즈를 안 읽음' in w: r2 += 1
        elif '사이즈를 읽음' in w: r1 += 1
    print('  블러프 사이즈 역산:  상대가 읽는다 %d건 / 안 읽는다 %d건' % (r1, r2))
    sig = Counter(i['opp_range_sig'] for r in rows for i in (r.get('intents') or [])
                  if i.get('opp_range_sig'))
    print('\n상대 레인지 추정이 상황마다 갈리는가')
    print('  intent %d건 → 서로 다른 레인지 지문 %d개' % (sum(sig.values()), len(sig)))


def cmd_plan(rows):
    ints = [i for r in rows for i in (r.get('intents') or [])]
    nores = [i for i in ints if i.get('response_act') is None]
    same = sum(1 for i in nores if i.get('action') == i.get('intent_act'))
    print('포스트플랍 intent %d건' % len(ints))
    print('  무저항(상대 벳 없음) %d건 중 의도대로 집행 %d건 (%.0f%%)'
          % (len(nores), same, 100*same/max(1, len(nores))))
    print('  상대 벳에 직면 %d건 — 응답 단계가 따로 판단한다'
          % (len(ints)-len(nores)))
    dev = [d for r in rows for i in (r.get('intents') or []) for d in (i.get('dev') or [])]
    print('  기록된 계획이탈 %d건' % len(dev))
    for k, v in Counter(d['why'].split('(')[0] for d in dev).most_common():
        print('    %-24s %d' % (k, v))
    # audit.py:169 와 같은 검사
    need = {'bluff_2street': 'bluff', 'semibluff': 'semibluff', 'trap': 'checkraise',
            'block': 'blockbet', 'pot_control': 'potcontrol'}
    tot = bad = 0
    for r in rows:
        for i in r.get('intents') or []:
            k = need.get(i['plan'])
            if not k: continue
            c = ((r.get('profiles') or {}).get(str(i['seat'])) or {}).get('concepts') or {}
            if not c: continue
            tot += 1
            if c.get(k, 5) < 1.5: bad += 1
    print('  개념 문턱이 걸리는 계획 %d건 중 개념 없이 나온 것 %d건' % (tot, bad))
    # 이탈 굴림이 얼마나 자주 터지나
    fired = notf = 0; ps = []
    for r in rows:
        for i in r.get('intents') or []:
            for t in (i.get('trace') or []):
                if t.get('kind') != 'aggression': continue
                if not str(t.get('why', '')).startswith('DEVIATE:'): continue
                ps.append(t['p'])
                if t['roll'] < t['p']: fired += 1
                else: notf += 1
    if ps:
        import statistics as ST
        print('\n포기 계획 + 이니셔티브 %d건' % (fired+notf))
        print('  굴림이 터져 실제로 벳 %d건 (%.0f%%)' % (fired, 100*fired/(fired+notf)))
        print('  확률 p 중앙 %.3f  최대 %.3f' % (ST.median(ps), max(ps)))


def cmd_dist(n=4000, entries=100, buyin=1.0, seed=20260914):
    import field as F, persona as PS
    q = F.field_quality(entries, buyin)
    rng = random.Random(seed)
    ps = [PS.make_player(rng, q, i) for i in range(n)]
    print('생성기 표본 %d명  entries=%d buyin_level=%.2f → q=%.2f' % (n, entries, buyin, q))
    lo, hi = PS.skill_bounds(q)
    print('실력 하한 %.1f / 상한 %.1f\n' % (lo, hi))
    c = Counter(p['type'] for p in ps)
    print('타입 상위 10')
    for k, v in c.most_common(10): print('  %-26s %5.1f%%' % (k, 100*v/n))
    weak = sum(v for k, v in c.items() if any(w in k for w in ('FISH', 'STATION', 'MANIAC')))
    print('  약체(FISH/STATION/MANIAC) 합계  %.1f%%' % (100*weak/n))
    print('\ntemper 분포')
    for k in ('looseness', 'aggression', 'discipline', 'gamble', 'attention'):
        v = sorted((p.get('temper') or {}).get(k, 0) for p in ps)
        print('  %-12s 25%% %4.1f  중앙 %4.1f  75%% %4.1f' % (k, v[n//4], v[n//2], v[3*n//4]))
    print('\n개념 분포')
    for k in ('pf_defend', 'pf_range', 'bluff', 'sizing_tell', 'icm', 'potodds'):
        v = sorted((p.get('concepts') or {}).get(k, 0) for p in ps)
        print('  %-12s 25%% %4.1f  중앙 %4.1f  75%% %4.1f   3 미만 %4.1f%%'
              % (k, v[n//4], v[n//2], v[3*n//4], 100*sum(1 for x in v if x < 3)/n))


def cmd_formats(n=2500, entries=100):
    import field as F, persona as PS, formats as FM
    print('대회 종류별 필드 (entries=%d, 각 %d명 표본)\n' % (entries, n))
    print('%-12s %-14s %6s %7s %10s %10s' % ('키', '이름', 'q', '약체%', 'loose 중앙', 'aggr 중앙'))
    for key in FM.FORMATS:
        f = FM.FORMATS[key]
        q = F.field_quality(entries, f['buyin_level'])
        rng = random.Random(4242)
        ps = [PS.make_player(rng, q, i) for i in range(n)]
        c = Counter(p['type'] for p in ps)
        weak = sum(v for k, v in c.items() if any(w in k for w in ('FISH', 'STATION', 'MANIAC')))
        lo = sorted(p['temper']['looseness'] for p in ps)[n//2]
        ag = sorted(p['temper']['aggression'] for p in ps)[n//2]
        print('%-12s %-14s %6.2f %6.1f%% %10.1f %10.1f' % (key, f['name'], q, 100*weak/n, lo, ag))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file', nargs='?')
    for f in ('traits', 'defend', 'stage', 'exploit', 'plan', 'dist', 'formats'):
        ap.add_argument('--'+f, action='store_true')
    ap.add_argument('--buyin', type=float, default=1.0)
    ap.add_argument('--entries', type=int, default=100)
    a = ap.parse_args()
    if a.dist: return cmd_dist(entries=a.entries, buyin=a.buyin)
    if a.formats: return cmd_formats(entries=a.entries)
    if not a.file: return ap.error('아카이브 파일이 필요하다 (--dist/--formats 는 예외)')
    rows = load(a.file)
    print('# %s — %d핸드 (히어로 테이블만)\n' % (os.path.basename(a.file), len(rows)))
    any_ = False
    for name, fn in (('traits', cmd_traits), ('defend', cmd_defend), ('stage', cmd_stage),
                     ('exploit', cmd_exploit), ('plan', cmd_plan)):
        if getattr(a, name):
            any_ = True
            print('## %s' % name); fn(rows); print()
    if not any_:
        for name, fn in (('traits', cmd_traits), ('defend', cmd_defend), ('stage', cmd_stage),
                         ('exploit', cmd_exploit), ('plan', cmd_plan)):
            print('## %s' % name); fn(rows); print()


if __name__ == '__main__':
    main()
