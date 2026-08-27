"""히어로가 실제로 보게 되는 화면."""
from table import POST_ORDER as POST
TAG = {'fold':'폴드','check':'체크','call':'콜','bet':'벳','raise':'레이즈','allin':'올인'}

def bbs(x, bb): return round(x/bb, 1)
def C(x): return '{:,}'.format(int(x))

def build(raw, hand, field=None, level=None, blinds=None, hand_no=None, notes=None,
          start_stack=30000):
    bb = hand.bb; hero = hand.hero
    pos_of = hand.pos; seat_of = hand.seat_of
    v = {'stage': raw['stage'], 'hash': raw['hash'], 'hand_no': hand_no,
         'notes': list(notes or [])}
    v['hero'] = {'seat': hero, 'pos': pos_of[hero], 'hole': raw['hole'],
                 'stack': raw['stack'], 'bb': bbs(raw['stack'], bb)}
    v['pot'] = raw['pot']; v['pot_bb'] = bbs(raw['pot'], bb)
    v['tocall'] = raw['tocall']; v['tocall_bb'] = bbs(raw['tocall'], bb)
    if raw.get('board'): v['board'] = raw['board']
    st = raw['stack']; mn = raw.get('min_raise', 0)

    if raw['tocall'] >= st:
        v['options'] = ['ㅍㄷ', '콜(=올인)']
        v['note'] = '콜 비용이 스택 이상 — 콜하면 올인'
    elif not raw.get('can_raise', True):
        v['options'] = ['ㅍㄷ', 'ㅋ']
        v['note'] = '불완전 올인이 개입 — 레이즈 권리 없음'
    elif mn >= st:
        v['options'] = ['ㅍㄷ', 'ㅋ' if raw['tocall'] else 'ㅊㅋ', '올인']
        v['note'] = '최소 레이즈 %s > 스택 — 올릴 거면 올인뿐' % C(mn)
    else:
        v['options'] = ['ㅍㄷ', 'ㅋ' if raw['tocall'] else 'ㅊㅋ',
                        '%s ~ %s' % (C(mn), C(st))]
        v['note'] = None

    live = set(raw.get('live') if raw.get('live') is not None else hand.seats)
    allin = set(raw.get('allin') or [])
    inv = raw.get('contrib', {})
    rows = []
    for s in sorted(hand.seats):
        p = pos_of.get(s)
        if p is None: continue
        sk = hand.stacks.get(s, 0)
        rows.append({'seat': s, 'pos': p, 'stack': sk, 'bb': bbs(sk, bb),
                     'live': (s in live and sk > 0), 'hero': s == hero,
                     'allin': s in allin,
                     'inv': inv.get(s, 0),
                     'eff': bbs(min(sk, raw['stack']), bb) if sk > raw['stack'] else None})
    v['seats'] = rows
    v['n_live'] = sum(1 for r in rows if r['live'])
    def _fmt(s, a, amt):
        who = '너' if s == hero else '%d번(%s)' % (s, pos_of.get(s, '?'))
        return '%s %s%s' % (who, TAG[a], ' ' + C(amt) if a in ('bet','raise') and amt else '')
    v['log'] = [_fmt(s, a, amt) for (s, a, amt) in raw.get('log', [])]
    # 이전 스트리트 기록 (진행 중에도 전체 라인을 볼 수 있게)
    prior = {}
    for e in raw.get('prior_log', []):
        st_, s_, a_, amt_ = e
        prior.setdefault(st_, []).append(_fmt(s_, a_, amt_))
    v['prior'] = prior
    if raw.get('board'): v['spr'] = round(st/max(1, raw['pot']), 1)
    if field:
        s = field.status()
        avg_bb = (s['avg']/bb) if 'avg' in s else field.avg_stack_bb(start_stack, bb)
        v['field'] = dict(s, avg_bb=round(avg_bb, 1))
    if level and blinds: v['level'] = {'n': level, 'sb': blinds[0], 'bb': blinds[1]}
    if raw.get('error'): v['error'] = raw['error']
    return v

def render(v):
    L = []
    for n in v['notes']: L.append(n)
    if v['notes']: L.append('')
    hd = 'HAND %s' % v.get('hand_no', '?')
    if v.get('level'):
        lv = v['level']
        hd += ' | 레벨%d: %s/%s (%s ante)' % (lv['n'], C(lv['sb']), C(lv['bb']), C(lv['bb']))
    hd += ' | 🔒%s' % v['hash']
    L.append(hd)
    if v.get('field'):
        f = v['field']
        tb = ('  %d테이블' % f['tables']) if 'tables' in f else ''
        L.append('필드 %d명 중 %d명 생존%s | ITM %d위 (%d명 남음)%s'
                 % (f['entries'], f['remaining'], tb, f['itm'], f['to_itm'],
                    '  ⚠️버블' if f['bubble'] else ''))
        rk = f.get('rank'); ld = f.get('leader')
        extra = ''
        if rk: extra += '내 순위 %d위/%d명' % (rk, f['remaining'])
        extra += '   평균 %sbb' % f['avg_bb']
        if ld: extra += '   칩리더 %s' % C(ld)
        L.append(extra)
    L.append('')
    for r in v['seats']:
        mark = '← 너' if r['hero'] else ('올인' if r.get('allin') else ('●' if r['live'] else '·'))
        extra = '  ' + ' '.join(v['hero']['hole']) if r['hero'] else ''
        put = ('  투입 %s' % C(r['inv'])) if r.get('inv') else ''
        eff = ''
        L.append(' %-5s %-6s %-16s %s%s%s%s' % ('%d번' % r['seat'], r['pos'],
                 '%s (%sbb)' % (C(r['stack']), r['bb']), mark, extra, eff, put))
    L.append('')
    if v.get('board'): L.append('보드  %s     SPR %s' % ('  '.join(v['board']), v.get('spr')))
    for st_ in ('preflop', 'flop', 'turn'):
        if v.get('prior', {}).get(st_):
            L.append('%-5s %s' % ({'preflop':'프리','flop':'플랍','turn':'턴'}[st_],
                                  ' → '.join(v['prior'][st_])))
    if v['log']: L.append('현재  ' + ' → '.join(v['log']))
    elif v.get('board'): L.append('액션  (체크로 너에게 돌아옴)')
    elif not v['log']: L.append('액션  (앞자리 전원 폴드 — 너부터)')
    if v.get('n_live'): L.append('참여  %d명' % v['n_live'])
    L.append('')
    line = '팟 %s (%sbb)' % (C(v['pot']), v['pot_bb'])
    if v['tocall']: line += '   |   콜 비용 %s (%sbb)' % (C(v['tocall']), v['tocall_bb'])
    L.append(line)
    L.append('가능  ' + ' / '.join(v['options']))
    if v.get('note'): L.append('※ ' + v['note'])
    if v.get('error'): L.append('⚠ ' + v['error'])
    L.append('')
    L.append('액션?')
    return '\n'.join(L)


STREET_KR = {'preflop':'프리플랍','flop':'플랍','turn':'턴','river':'리버'}

def render_result(res, hero=None, hand_no=None, notes=None, bb=None):
    """핸드 종료 후 전체 진행을 보여준다."""
    hero = res.get('hero_seat', hero)
    L = []
    L.append('[HAND %s 결과]' % (hand_no or '?'))
    if res.get('board'):
        L.append('보드  %s' % '  '.join(res['board']))
    cur = None
    for (st, s, a, amt) in res.get('full_log', []):
        if st != cur:
            cur = st; L.append('  · %s' % STREET_KR.get(st, st))
        who = '너' if s == hero else '%s번(%s)' % (s, res.get('pos', {}).get(s, '?'))
        txt = TAG[a] + (' ' + C(amt) if a in ('bet','raise') and amt else '')
        L.append('     %s %s' % (who, txt))
    L.append('팟 %s' % C(res['pot']))
    pots = res.get('pots') or []
    if len(pots) > 1:
        for i, pt in enumerate(pots):
            if len(pt['eligible']) == 1:
                _e = pt['eligible'][0]
                L.append('   (사이드팟 %s → %s 반환)' % (C(pt['amount']),
                         res.get('pos', {}).get(str(_e), _e)))
    if res.get('showdown'):
        for s, hl in res.get('hole', {}).items():
            _mw = [str(x) for x in (res.get('main_winners') or res.get('winners') or [])]
            mark = ' ← 승' if str(s) in _mw else ''
            L.append('  쇼다운  %s번  %s%s' % (s, ' '.join(hl), mark))
    else:
        w = res['winners'][0] if res['winners'] else '?'
        _wp = res.get('pos', {}).get(str(w), res.get('pos', {}).get(w, w))
        L.append('  %s 팟 획득, 쇼다운 없음' % ('너' if w == hero else str(_wp)))
    L.append('🔓 %s' % res['hash'])
    for n in (notes or []): L.append(n)
    return '\n'.join(L)
