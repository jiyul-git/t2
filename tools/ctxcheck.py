"""드라이버가 핸드에 문맥을 빠짐없이 심는지 검사한다.

    python3 tools/ctxcheck.py

경로가 넷이라(tourney/live/live2/fieldsim) 각자 심는 목록이 어긋나기 쉽고,
빠진 값은 조용히 기본값으로 대체되어 그 경로에서만 기능이 죽는다.
새 문맥 값을 context.SPEC 에 추가한 뒤 이걸 돌리면 어디를 고쳐야 하는지 나온다.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
# **진행 중인 게임을 건드리지 않는다.** live2.new_game 은 상태 파일과
# 아카이브를 지우므로, 검사는 별도 경로에서 돌린다.
os.environ.setdefault('T2_LIVE_STATE',
                      os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   '..', '_ctxcheck_state.json'))
import context as CTX

FAIL = []


def check(name, h):
    miss = [k for k in CTX.REQUIRED if getattr(h, k, None) is None]
    absent = [k for k in CTX.SPEC if not hasattr(h, k)]
    bad = sorted(set(miss) | set(absent))
    print('  %-10s %s' % (name, '누락 없음' if not bad else '누락: ' + ', '.join(bad)))
    if bad:
        FAIL.append(name)


print('문맥 항목 %d개 (필수 %d개)' % (len(CTX.SPEC), len(CTX.REQUIRED)))
print()

import tourney as T
t = T.Tournament(entries=50, seed=1, fmt='standard')
t.next_hand()
check('tourney', t.hand)

import fieldsim as FS
f = FS.Field(entries=40, seed=2, fmt='turbo')
import play
tb = list(f.tables.values())[0]
alive = [p for p in tb.players if p['stack'] > 0][:4]
seats = list(range(1, len(alive)+1))
h = play.Hand(seats, {str(i+1): alive[i]['prof'] for i in range(len(alive))},
              {i+1: alive[i]['stack'] for i in range(len(alive))},
              1, *f.blinds(), hero=None, seed=1)
f.stamp(h)
check('fieldsim', h)

import live
st = live.new_game(entries=40, seed=3)
h2 = live.build_hand(st)
check('live', h2)

import live2
try:
    st2 = live2.new_game(entries=40, seed=4)
    _f, _tb, _al, h3, _hs = live2.build_hand(st2)
    check('live2', h3)
except Exception as e:
    print('  %-10s 구동 실패: %s: %s' % ('live2', type(e).__name__, e))
    FAIL.append('live2')

print()
print('통과' if not FAIL else '실패: ' + ', '.join(FAIL))
sys.exit(1 if FAIL else 0)
