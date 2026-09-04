"""세션 후 복기용 — 아카이브 조회."""
import json, os
D = os.path.dirname(os.path.abspath(__file__))
# live2 가 쓰는 파일과 같은 이름이어야 한다. 예전에는 'hand_archive.jsonl'
# 을 읽었는데 live2 는 'hand_archive2.jsonl' 에 쓴다 — 그래서 load() 가
# 늘 빈 리스트를 반환했고, **리뷰 도구가 통째로 죽어 있었다.**
# T2_LIVE_STATE 를 쓰면 live2 가 _alt 접미사를 붙이므로 그것도 맞춘다.
_SUFFIX = '_alt' if os.environ.get('T2_LIVE_STATE') else ''
PATH = os.path.join(D, 'hand_archive2%s.jsonl' % _SUFFIX)

def load():
    if not os.path.exists(PATH): return []
    return [json.loads(l) for l in open(PATH) if l.strip()]

def hand(n):
    for r in load():
        if r['hand_no'] == n: return r
    return None

STREET_KR = {'preflop':'프리플랍','flop':'플랍','turn':'턴','river':'리버'}
TAG = {'fold':'폴드','check':'체크','call':'콜','bet':'벳','raise':'레이즈','allin':'올인'}

def show(n, reveal=True):
    r = hand(n)
    if not r: return 'HAND %s 기록 없음' % n
    L = ['HAND %d | 레벨%d %s/%s | 🔒%s' % (r['hand_no'], r['level'],
         '{:,}'.format(r['blinds'][0]), '{:,}'.format(r['blinds'][1]), r['hash'])]
    L.append('보드  %s' % '  '.join(r['board']))
    if reveal:
        L.append('전 좌석 패:')
        for s, p in sorted(r['pos'].items(), key=lambda x: x[0]):
            mark = ' ← 너' if int(s) == r['hero'] else ''
            L.append('   %s번(%s) %s  [%s]%s' % (s, p, ' '.join(r['hole'][s]),
                                                 r['profiles'].get(s, '?'), mark))
    cur = None
    for e in r['full_log']:
        st, seat, a, amt = e
        if st != cur: cur = st; L.append(' · %s' % STREET_KR.get(st, st))
        who = '너' if seat == r['hero'] else '%d번(%s)' % (seat, r['pos'].get(str(seat), '?'))
        L.append('    %s %s%s' % (who, TAG.get(a, a),
                 ' ' + '{:,}'.format(int(amt)) if a in ('bet','raise') and amt else ''))
    res = r['result']
    L.append('팟 %s | 승자 %s | %s' % ('{:,}'.format(int(res.get('pot', 0))),
             res.get('winners'), '쇼다운' if res.get('showdown') else '쇼다운 없음'))
    return '\n'.join(L)

def summary():
    rs = load()
    if not rs: return '기록 없음'
    L = ['총 %d핸드 기록' % len(rs)]
    for r in rs:
        res = r['result']; hero = r['hero']
        won = hero in (res.get('winners') or [])
        L.append(' #%-3d %-6s 팟 %8s %s' % (r['hand_no'], r['pos'].get(str(hero), '?'),
                 '{:,}'.format(int(res.get('pot', 0))), '승' if won else ''))
    return '\n'.join(L)

def history(limit=None, hero=7):
    """토너 종료 후 남는 핸드 히스토리 요약."""
    rs = load()
    if not rs: return '기록 없음'
    L = ['핸드 히스토리 (%d핸드)' % len(rs), '']
    for r in (rs[-limit:] if limit else rs):
        res = r['result']
        won = hero in (res.get('winners') or [])
        pos = r['pos'].get(str(hero), '?')
        hole = ' '.join(r['hole'].get(str(hero), []))
        board = ' '.join(r['board']) if r.get('board') else '-'
        L.append('#%-3d %-5s %-6s | 보드 %-15s | 팟 %8s %s'
                 % (r['hand_no'], pos, hole, board,
                    '{:,}'.format(int(res.get('pot', 0))), '승' if won else ''))
    return '\n'.join(L)
