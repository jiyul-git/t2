"""세션 후 복기용 — 아카이브 조회."""
import json, os
D = os.path.dirname(os.path.abspath(__file__))
# live2 가 쓰는 파일과 같은 이름이어야 한다. 예전에는 'hand_archive.jsonl'
# 을 읽었는데 live2 는 'hand_archive2.jsonl' 에 쓴다 — 그래서 load() 가
# 늘 빈 리스트를 반환했고, **리뷰 도구가 통째로 죽어 있었다.**
# T2_LIVE_STATE 를 쓰면 live2 가 _alt 접미사를 붙이므로 그것도 맞춘다.
import storage_paths as _SP
_SUFFIX = _SP.namespace()
# 쓰기 경로. 읽을 때는 아래 resolve() 로 legacy 를 찾을 수 있다.
PATH = _SP.sidecar_path('archive')


def resolve(allow_legacy_alt=False):
    """읽을 경로와 출처 분류 (`storage_paths.resolve_read` 그대로).

    출처가 `legacy_alt_ambiguous` 면 `path` 는 **None** 이다 — 옛 공유
    `_alt` 는 어느 상태의 기록인지 알 수 없어서, 이 상태의 기록인 것처럼
    읽지 않는다. 정말 읽어야 하면 `allow_legacy_alt=True` 로 명시한다.
    """
    return _SP.resolve_read('archive', allow_legacy_alt=allow_legacy_alt)

def status(allow_legacy_alt=False):
    """아카이브 상태를 사람이 읽을 한 줄로. `없음`과 `모호`를 **가른다**."""
    r = resolve(allow_legacy_alt)
    if r['source'] == _SP.SRC_LEGACY_AMBIGUOUS and not r['path']:
        return ('옛 공유 아카이브(%s)가 있으나 이 상태의 기록인지 증명할 수 '
                '없어 사용하지 않았습니다. 정말 읽으려면 allow_legacy_alt=True.'
                % os.path.basename(r['legacy_path']))
    if r['source'] == _SP.SRC_MISSING:
        return '아카이브 파일이 없습니다 (%s).' % os.path.basename(PATH)
    return None


def load(allow_legacy_alt=False):
    """아카이브 레코드. **resolver 를 거친다** — PATH 를 직접 읽지 않는다.

    모호한 legacy 는 opt-in 없이는 읽지 않으므로 빈 리스트가 나온다.
    그 '빈 리스트'가 '기록 없음'과 다르다는 것은 `status()` 가 말해 준다.
    """
    r = resolve(allow_legacy_alt)
    if not r['path']:
        return []
    return [json.loads(l) for l in open(r['path'], encoding='utf-8')
            if l.strip()]

def hand(n, allow_legacy_alt=False):
    for r in load(allow_legacy_alt):
        if r['hand_no'] == n: return r
    return None

STREET_KR = {'preflop':'프리플랍','flop':'플랍','turn':'턴','river':'리버'}
TAG = {'fold':'폴드','check':'체크','call':'콜','bet':'벳','raise':'레이즈','allin':'올인'}

def show(n, reveal=True, allow_legacy_alt=False):
    r = hand(n, allow_legacy_alt)
    if not r:
        st = status(allow_legacy_alt)
        return 'HAND %s 기록 없음%s' % (n, ('\n  ' + st) if st else '')
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

def summary(allow_legacy_alt=False):
    rs = load(allow_legacy_alt)
    if not rs:
        st = status(allow_legacy_alt)
        return st or '기록 없음'
    L = ['총 %d핸드 기록' % len(rs)]
    for r in rs:
        res = r['result']; hero = r['hero']
        won = hero in (res.get('winners') or [])
        L.append(' #%-3d %-6s 팟 %8s %s' % (r['hand_no'], r['pos'].get(str(hero), '?'),
                 '{:,}'.format(int(res.get('pot', 0))), '승' if won else ''))
    return '\n'.join(L)

def history(limit=None, hero=7, allow_legacy_alt=False):
    """토너 종료 후 남는 핸드 히스토리 요약."""
    rs = load(allow_legacy_alt)
    if not rs:
        st = status(allow_legacy_alt)
        return st or '기록 없음'
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
