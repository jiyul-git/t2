"""포스트플랍 지표를 스트리트별로 잰다.

    python3 tools/postmetrics.py [핸드수] [포맷...]

구조를 고친 뒤 값이 실제로 어떻게 나오는지 보기 위한 도구다.
목표치가 정해지지 않았으므로 **판정하지 않고 숫자만 낸다.**
"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import tourney as T

HANDS = int(sys.argv[1]) if len(sys.argv) > 1 else 60
FMTS = sys.argv[2:] or ['lowbuyin', 'standard', 'highroller']
SEEDS = (9100, 9101)


def run(fmt):
    c = collections.Counter()
    for sd in SEEDS:
        t = T.Tournament(entries=100, seed=sd, fmt=fmt, hero_seat=7)
        for _ in range(HANDS):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            g = 0
            while st and not st.get('done') and g < 250:
                st = t.submit('fold')
                g += 1
            log = getattr(t.run, 'full_log', []) or []
            seen_streets = set(x[0] for x in log)
            for stt in ('flop', 'turn', 'river'):
                rows = [x for x in log if x[0] == stt]
                if not rows:
                    continue
                c[stt + '_reach'] += 1
                # 첫 액션이 벳이면 선제
                c[stt + '_n'] += 1
                if rows[0][2] in ('bet', 'raise', 'allin'):
                    c[stt + '_bet'] += 1
                for (_s, x, a, amt) in rows:
                    if a in ('bet', 'raise', 'allin'):
                        c[stt + '_agg'] += 1
                    if a == 'raise':
                        c[stt + '_xr'] += 1
                    if a in ('bet', 'raise', 'call', 'check', 'fold', 'allin'):
                        c[stt + '_act'] += 1
                    if a == 'fold':
                        c[stt + '_fold'] += 1
            c['hands'] += 1
            if 'river' in seen_streets:
                c['wtsd'] += 1
            t.finish_hand()
    return c


print('핸드 %d x 시드 %d' % (HANDS, len(SEEDS)))
print()
print('%-11s %7s %7s %7s   %7s %7s %7s   %6s' %
      ('포맷', '플랍%', '턴%', '리버%', '플랍벳', '턴벳', '리버벳', 'WTSD'))
for fmt in FMTS:
    c = run(fmt)
    h = max(1, c['hands'])
    row = [100*c['%s_reach' % s]/h for s in ('flop', 'turn', 'river')]
    bet = [100*c['%s_bet' % s]/max(1, c['%s_n' % s]) for s in ('flop', 'turn', 'river')]
    print('%-11s %6.0f%% %6.0f%% %6.0f%%   %6.0f%% %6.0f%% %6.0f%%   %5.0f%%' %
          (fmt, row[0], row[1], row[2], bet[0], bet[1], bet[2], 100*c['wtsd']/h))

print()
print('%-11s %8s %8s %8s' % ('포맷', '플랍폴드', '턴폴드', '리버폴드'))
for fmt in FMTS:
    c = run(fmt)
    f = [100*c['%s_fold' % s]/max(1, c['%s_act' % s]) for s in ('flop', 'turn', 'river')]
    print('%-11s %7.0f%% %7.0f%% %7.0f%%' % (fmt, f[0], f[1], f[2]))
