"""필드 지표 측정 — 우리가 만든 필드가 실제 필드 범위 안에 있는가.

주의: 이건 **우리 시뮬레이터가 만든 필드의 통계**지 실제 필드가 아니다.
이 숫자로 LOADING 을 맞추면 자기 출력으로 자기 입력을 맞추는 순환이 된다.
쓸 수 있는 건 '실제 필드의 대략적 범위를 크게 벗어나는가' 하나뿐이다.

    python3 tools/fieldstats.py [핸드수]
"""
import sys, os, collections

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import tourney as T   # noqa: E402

AGG = ('bet', 'raise', 'allin')


def main():
    want = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    seeds = [11000 + i for i in range(40)]
    per = collections.defaultdict(lambda: collections.Counter())
    c = collections.Counter()
    hands = 0

    for sd in seeds:
        if hands >= want:
            break
        t = T.Tournament(entries=60, seed=sd, fmt='standard', hero_seat=7)
        for _ in range(60):
            if hands >= want:
                break
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            g = 0
            while st and not st.get('done') and g < 250:
                st = t.submit('fold')
                g += 1
            hands += 1
            h = getattr(t.run, 'h', None)
            log = getattr(t.run, 'full_log', []) or []
            if not log:
                continue
            pf = [x for x in log if x[0] == 'preflop']
            seats = set(x[1] for x in pf)
            hero = getattr(h, 'hero', None)
            # seat_pid 는 비어 있고 프로필 id 도 None 이라 개인 추적이 안 된다.
            # 아키타입(type)이 유일한 식별자다. LOADING 검증 목적에는 오히려
            # 이쪽이 맞다 — '유형이 실제 필드처럼 분포하는가'를 보는 것이므로.
            _pf_map = getattr(h, 'prof', {}) or {}
            for s in seats:
                if s == hero:
                    continue                     # 히어로는 자동 폴드라 제외
                _pp = _pf_map.get(str(s)) or _pf_map.get(s) or {}
                key = _pp.get('type') or ('seat', s)
                mine = [x for x in pf if x[1] == s]
                per[key]['hands'] += 1
                if any(x[2] in ('call',) + AGG for x in mine):
                    per[key]['vpip'] += 1
                if any(x[2] in AGG for x in mine):
                    per[key]['pfr'] += 1
            # 포스트플랍 공격 빈도
            for stt in ('flop', 'turn', 'river'):
                rows = [x for x in log if x[0] == stt and x[1] != hero]
                if rows:
                    c['post_' + stt] += len(rows)
                    c['aggr_' + stt] += sum(1 for x in rows if x[2] in AGG)
            res = getattr(t.run, 'result', None) or {}
            if res.get('showdown'):
                c['showdown'] += 1
            c['played'] += 1

    # 플레이어 단위 집계 (표본 20핸드 이상만)
    vp, pr, rows_by_type = [], [], []
    for s, d in per.items():
        if d['hands'] >= 20:
            vp.append(100.0*d['vpip']/d['hands'])
            pr.append(100.0*d['pfr']/d['hands'])
            rows_by_type.append((s, d['hands'], 100.0*d['vpip']/d['hands'],
                                 100.0*d['pfr']/d['hands']))
    vp.sort(); pr.sort()

    def q(a, p):
        if not a:
            return 0.0
        return a[min(len(a)-1, int(len(a)*p))]

    print('핸드 %d / 유형 %d개(20핸드 이상)' % (hands, len(vp)))
    print()
    print('  VPIP  평균 %.1f%%  중앙 %.1f%%  하위10%% %.1f%%  상위10%% %.1f%%'
          % (sum(vp)/max(1, len(vp)), q(vp, 0.5), q(vp, 0.1), q(vp, 0.9)))
    print('  PFR   평균 %.1f%%  중앙 %.1f%%  하위10%% %.1f%%  상위10%% %.1f%%'
          % (sum(pr)/max(1, len(pr)), q(pr, 0.5), q(pr, 0.1), q(pr, 0.9)))
    gap = (sum(vp)/max(1, len(vp))) - (sum(pr)/max(1, len(pr)))
    print('  VPIP-PFR 격차 %.1f  (8 이상이면 림핑 과다로 본다)' % gap)
    print()
    for stt in ('flop', 'turn', 'river'):
        n = c['post_' + stt]
        if n:
            print('  %-6s 공격률 %.1f%%  (n=%d)'
                  % (stt, 100.0*c['aggr_' + stt]/n, n))
    print()
    print('  쇼다운 도달 %.1f%%' % (100.0*c['showdown']/max(1, c['played'])))
    print()
    print('  유형별 (핸드 / VPIP / PFR)')
    for name, n, v, r in sorted(rows_by_type, key=lambda x: -x[2]):
        print('    %-22s %5d  %5.1f%%  %5.1f%%' % (name, n, v, r))


if __name__ == '__main__':
    main()
