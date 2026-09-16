#!/usr/bin/env python3
"""L2 원자료에서 L1 과 **같은 정의**로 flip 을 다시 센다.

  python3 tools/l2_recount.py rows55.jsonl.gz

읽기 전용. 새 시뮬레이션을 하지 않는다 — cf_axis_l2.py --rows 가 남긴
레코드만 읽는다.

**두 harness 의 flip 정의가 다르다.**

  L1  tools/cf_axis.py:354   act_lo != act_hi      결정당 비교 1회
  L2  tools/cf_axis_l2.py:303  각 tag 를 O 와 비교   결정당 비교 2회

같은 행동 변화를 다르게 센다. 예로 O=fold, lo=call, hi=call 이면
L2 는 flip 2건, L1 은 0건이다. 그래서 두 수를 직접 비교할 수 없었다.

여기서는 같은 원자료에 두 정의를 모두 적용한다.
  (a) 기존 L2 정의 재현 — 파싱이 맞는지 자체 검사
  (b) L1 정의(act_lo != act_hi)
  (c) 두 정의를 ① 전체 / ② attached_O 두 분모에서 각각

**attached_O** 는 plan.py:1521 의 `intent_of(st, street) is None` 게이트가
열렸다는 직접 관측이다 (= 그 (좌석, 스트리트)의 최초 update_plan).
"""
import sys, gzip, json, collections

ARMS = ('D', 'M', 'T')
SIZE0 = '사이즈 0 → 체크'   # plan.py:575 의 사유 문자열


def load(path):
    op = gzip.open if path.endswith('.gz') else open
    for line in op(path, 'rt', encoding='utf-8'):
        line = line.strip()
        if line:
            yield json.loads(line)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'rows55.jsonl.gz'
    # [axis][arm][scope] -> 카운터
    C = collections.defaultdict(lambda: collections.defaultdict(
        lambda: collections.defaultdict(collections.Counter)))
    # (c)(d) 용. ② (attached_O) 안에서만, 양쪽 tag 가 정렬된 쌍만 센다.
    G = collections.defaultdict(lambda: collections.defaultdict(
        lambda: {'pairs': 0, 'l1eq_flip': 0, 'l2_flip': 0,
                 'size0_lo': 0, 'size0_hi': 0, 'cross_ne': 0, 'pdiff': []}))
    HAVE_DG = None
    axes = []
    n = 0
    for r in load(path):
        n += 1
        if HAVE_DG is None:
            HAVE_DG = ('p_D_lo' in r)
        ax = r['axis']
        if ax not in axes: axes.append(ax)
        scopes = ('all', 'att') if r.get('attached_O') else ('all',)
        for arm in ARMS:
            ok = {}
            for tag in ('lo', 'hi'):
                ok[tag] = (not r.get('shift_%s_%s' % (arm, tag))
                           and r.get('inv_%s_%s' % (arm, tag)))
            pair_ok = ok['lo'] and ok['hi']
            for sc in scopes:
                c = C[ax][arm][sc]
                c['rows'] += 1
                # (a) 기존 L2 정의 — tag 단위
                for tag in ('lo', 'hi'):
                    c['tag_tot'] += 1
                    if not ok[tag]:
                        c['tag_drop'] += 1; continue
                    c['tag_al'] += 1
                    pf = (r['plan_%s_%s' % (arm, tag)] != r['plan_O'])
                    af = (r['act_%s_%s' % (arm, tag)] != r['act_O'])
                    if not pf and af: c['tag_pa'] += 1
                    elif pf and not af: c['tag_pA'] += 1
                    elif pf and af: c['tag_PA'] += 1
                # (b) L1 정의 — 쌍 단위
                if pair_ok:
                    c['pair_al'] += 1
                    if r['act_%s_lo' % arm] != r['act_%s_hi' % arm]:
                        c['pair_flip'] += 1
                    if r['plan_%s_lo' % arm] != r['plan_%s_hi' % arm]:
                        c['pair_planflip'] += 1
                if r.get('act_%s_lo' % arm) is None or r.get('act_%s_hi' % arm) is None:
                    c['act_none'] += 1
        # --- (c)(d): ② 안에서, 양쪽 tag 정렬된 쌍만 ---
        if HAVE_DG and r.get('attached_O'):
            for arm in ARMS:
                ok = all(not r.get('shift_%s_%s' % (arm, t))
                         and r.get('inv_%s_%s' % (arm, t)) for t in ('lo', 'hi'))
                if not ok: continue
                p_lo, p_hi = r.get('p_%s_lo' % arm), r.get('p_%s_hi' % arm)
                if p_lo is None or p_hi is None: continue
                g = G[r['axis']][arm]
                g['pairs'] += 1
                g['pdiff'].append(abs(float(p_hi) - float(p_lo)))
                cr = {}
                for t in ('lo', 'hi'):
                    a = r.get('act_%s_%s' % (arm, t))
                    sc = r.get('src_%s_%s' % (arm, t))
                    cr[t] = (a == 'bet') or (sc == SIZE0)
                    if sc == SIZE0: g['size0_' + t] += 1
                if cr['lo'] != cr['hi']:
                    g['cross_ne'] += 1
                    g['l1eq_flip'] += 1
                if r.get('act_%s_lo' % arm) != r.get('act_%s_hi' % arm):
                    g['l2_flip'] += 1

    print('# L2 원자료 재집계 — %s' % path)
    print('  레코드 %d행   축 %d개' % (n, len(axes)))
    print()
    print('  ① 전체        모든 update_plan 호출')
    print('  ② attached    attach_intent 가 실행된 호출 (= 최초 decision unit)')
    print()

    print('## (a) 기존 L2 정의 재현 — tag 를 O 와 비교. 발표값과 같아야 한다')
    h = ('%-16s %-3s %8s %8s %8s   %13s %13s %13s'
         % ('축', '팔', 'tag_tot', 'aligned', 'shifted', 'plan=,act≠', 'plan≠,act=', 'plan≠,act≠'))
    print(h); print('-'*len(h))
    for ax in axes:
        for arm in ARMS:
            c = C[ax][arm]['all']
            al = c['tag_al']
            f = lambda k: '%5d/%6.3f%%' % (c[k], 100.0*c[k]/al if al else 0.0)
            print('%-16s %-3s %8d %8d %8d   %13s %13s %13s'
                  % (ax if arm == 'D' else '', arm, c['tag_tot'], al, c['tag_drop'],
                     f('tag_pa'), f('tag_pA'), f('tag_PA')))
    print()

    print('## (b) L1 과 같은 정의 — act_lo != act_hi. 결정당 비교 1회')
    h = ('%-16s %-3s   %8s %8s %9s   %8s %8s %9s'
         % ('축', '팔', '①쌍', '①flip', '①flip%', '②쌍', '②flip', '②flip%'))
    print(h); print('-'*len(h))
    for ax in axes:
        for arm in ARMS:
            a, b = C[ax][arm]['all'], C[ax][arm]['att']
            r1 = 100.0*a['pair_flip']/a['pair_al'] if a['pair_al'] else 0.0
            r2 = 100.0*b['pair_flip']/b['pair_al'] if b['pair_al'] else 0.0
            print('%-16s %-3s   %8d %8d %8.3f%%   %8d %8d %8.3f%%'
                  % (ax if arm == 'D' else '', arm,
                     a['pair_al'], a['pair_flip'], r1,
                     b['pair_al'], b['pair_flip'], r2))
    print()
    print('  ①쌍/②쌍 : 양쪽 tag 가 모두 정렬·불변량 통과한 결정 수 (L1 의 aligned 에 대응)')
    print('  act 가 None 인 쌍은 위 집계에 포함돼 있다 — 아래에 건수를 따로 적는다')
    print()
    nz = [(ax, arm, C[ax][arm]['all']['act_none']) for ax in axes for arm in ARMS
          if C[ax][arm]['all']['act_none']]
    print('  act None 포함 쌍: %s' % (', '.join('%s/%s %d' % x for x in nz) if nz else '없음'))

    if not HAVE_DG:
        print()
        print('  (p/size/src 진단 필드가 없는 원자료다 — 아래 분해는 건너뛴다)')
        return
    print()
    print('## (c) size 게이트 분해 — L1 등가 act 를 같은 실행 안에서 재구성')
    print()
    print('  crossed      roll < p 였는가.  src 로 복원한다')
    print('                 act == "bet"            → True  (size > 0)')
    print('                 src == "사이즈 0 → 체크"  → True  (size == 0)')
    print('                 그 외                    → False')
    print('  L1등가_act   "bet" if crossed else "check"   ← size 게이트 무시')
    print('  L2실제_act   act                              ← size 게이트 적용')
    print()
    h = ('%-16s %-3s %8s %9s %9s %8s   %9s %9s'
         % ('축', '팔', '②쌍', 'L1등가flip', 'L2실제flip', '차', 'size0_lo', 'size0_hi'))
    print(h); print('-'*len(h))
    for ax in axes:
        for arm in ARMS:
            g = G[ax][arm]
            n = g['pairs']
            if not n:
                print('%-16s %-3s %8d   (표본 없음)' % (ax if arm == 'D' else '', arm, 0))
                continue
            d = g['l1eq_flip'] - g['l2_flip']
            print('%-16s %-3s %8d %9d %9d %+8d   %9d %9d'
                  % (ax if arm == 'D' else '', arm, n,
                     g['l1eq_flip'], g['l2_flip'], d,
                     g['size0_lo'], g['size0_hi']))
    print()
    print('  차 = L1등가flip − L2실제flip. 양수면 size 게이트가 flip 을 지운 것이다')
    print('  size0_* : 그 tag 에서 crossed 인데 size == 0 이라 체크가 된 건수')
    print()
    print('## (d) p 판정 자체가 갈린 건수 — crossed_lo != crossed_hi')
    h = ('%-16s %-3s %8s %10s %11s %11s'
         % ('축', '팔', '②쌍', 'crossed≠', 'p차 중앙', 'p차 95%'))
    print(h); print('-'*len(h))
    for ax in axes:
        for arm in ARMS:
            g = G[ax][arm]
            n = g['pairs']
            ds = sorted(g['pdiff'])
            if not n or not ds:
                print('%-16s %-3s %8d   (표본 없음)' % (ax if arm == 'D' else '', arm, n)); continue
            med = ds[len(ds)//2]
            p95 = ds[min(len(ds)-1, int(0.95*len(ds)))]
            print('%-16s %-3s %8d %10d %11.4f %11.4f'
                  % (ax if arm == 'D' else '', arm, n, g['cross_ne'], med, p95))
    print()
    print('  crossed≠ 는 L1 등가 정의의 flip 과 정확히 같은 사건이다')
    print('  p차 = |p_hi − p_lo|. 개입이 확률을 얼마나 움직였는가')


if __name__ == '__main__':
    main()
