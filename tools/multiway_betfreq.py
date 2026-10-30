"""멀티웨이 포스트플랍 벳 빈도(봇만, 같은 시드). 판정하지 않고 숫자만 낸다.

    python3 tools/multiway_betfreq.py [핸드수/시드] [시드...] [--json 파일]

기회(그 스트리트에서 아직 벳이 없을 때 그 자리의 첫 행동)마다 벳했는지 센다.
  cbet   : 플랍, 프리플랍 마지막 레이저
  barrel : 턴·리버, 직전 스트리트에 벳/레이즈한 마지막 공격자
  lead   : 공격자가 아직 행동 전(뒤에 살아 있음)인데 먼저 벳
  probe  : 공격자가 이미 체크했거나 없음(폴드·올인)
팟 인원 = 그 스트리트에 행동한 좌석 수(2 / 3 / 4+). 패 강도는 홀카드 기여(bot.made_strength,
draw_strength): 투페어+, 탑페어+(투페어 포함), 드로우(8아웃+, 페어 미만).
range sync 전후 비교용(2026-10-30). 히어로 좌석은 폴드만 한다.
"""
import sys, os, json, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import tourney as T
import bot as B

args = [a for a in sys.argv[1:]]
jout = None
if '--json' in args:
    i = args.index('--json'); jout = args[i + 1]; del args[i:i + 2]
HANDS = int(args[0]) if args else 300
SEEDS = [int(x) for x in args[1:]] or [9100, 9101, 9102, 9103]
FMT = os.environ.get('MW_FMT', 'standard')
AGG = ('bet', 'raise', 'allin')
NB = {'flop': 3, 'turn': 4, 'river': 5}


def bucket(hole, board):
    m = B.made_strength(list(hole), board)
    out = []
    if m >= 2:
        out.append('2p+')
    if m >= 1:
        top = max(B.RV[b[0]] for b in board)
        prs = [B.RV[c[0]] for c in hole if any(c[0] == b[0] for b in board)]
        pocket = hole[0][0] == hole[1][0] and B.RV[hole[0][0]] > top
        if m >= 2 or (prs and max(prs) == top) or pocket:
            out.append('tp+')
    if m < 1 and B.draw_strength(list(hole), board) >= 8:
        out.append('draw')
    return out


def run():
    c = collections.Counter()
    hands = 0
    for sd in SEEDS:
        t = T.Tournament(entries=100, seed=sd, fmt=FMT, hero_seat=7)
        for _ in range(HANDS):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            g = 0
            while st and not st.get('done') and g < 250:
                st = t.submit('fold'); g += 1
            h = t.run.h
            log = getattr(t.run, 'full_log', []) or []
            hands += 1
            pre = [x for x in log if x[0] == 'preflop']
            aggr = None
            for (_s, x, a, _m) in pre:
                if a in AGG:
                    aggr = x
            for stt in ('flop', 'turn', 'river'):
                rows = [x for x in log if x[0] == stt]
                if not rows:
                    break
                board = list(h.board[:NB[stt]])
                seats = []
                for r in rows:
                    if r[1] not in seats:
                        seats.append(r[1])
                n = len(seats)
                nk = '2' if n <= 2 else '3' if n == 3 else '4+'
                bet_seen = False
                acted = set()
                checked = set()
                street_aggr = None
                for (_s, x, a, _m) in rows:
                    if not bet_seen and x not in acted:
                        if x == aggr:
                            role = 'cbet' if stt == 'flop' else 'barrel'
                        elif aggr is None or aggr not in seats or aggr in checked:
                            role = 'probe'
                        else:
                            role = 'lead'
                        b = a in AGG
                        for k in [role] + ['%s|%s' % (role, bk) for bk in bucket(h.hole[x], board)]:
                            c[(stt, nk, k, 'n')] += 1
                            c[(stt, nk, k, 'bet')] += int(b)
                    acted.add(x)
                    if a == 'check':
                        checked.add(x)
                    if a in AGG:
                        bet_seen = True
                        street_aggr = x
                aggr = street_aggr          # 다음 스트리트의 barrel 은 이 스트리트 마지막 공격자
                if aggr is None:
                    aggr = -1               # 모두 체크: 다음 스트리트엔 공격자 없음(전부 probe)
            t.finish_hand()
    return c, hands


c, hands = run()
rows = {}
for (stt, nk, k, f), v in c.items():
    if f == 'n':
        rows['%s %s %s' % (stt, nk, k)] = (v, c[(stt, nk, k, 'bet')])
print('fmt %s hands %d seeds %s' % (FMT, hands, SEEDS))
for key in sorted(rows, key=lambda s: (['flop', 'turn', 'river'].index(s.split()[0]), s)):
    n, b = rows[key]
    print('%-28s n=%5d bet=%5.1f%%' % (key, n, 100.0 * b / max(1, n)))
if jout:
    json.dump({'hands': hands, 'seeds': SEEDS, 'fmt': FMT, 'rows': rows}, open(jout, 'w'), ensure_ascii=False, indent=1)
