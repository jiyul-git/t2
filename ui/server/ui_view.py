"""그래픽 UI용 view 대체 모듈.

ui_server 가 sys.modules['view'] 로 주입한다. live2 는 view.build → view.render,
view.render_result 를 부르므로, 여기서 render 계열이 텍스트 대신 dict 를 돌려주면
엔진 파일을 건드리지 않고 step()/finish() 의 'view' 가 UI 상태가 된다.

원칙
- 원본 view.build() 를 그대로 호출한다 (표시 규칙의 단일 출처 유지).
- 화이트리스트로만 내보낸다. 봇 홀카드·plan·eq·profile 은 애초에 넣지 않는다.
- 원본의 한글 문자열(log/options)은 쓰지 않고 raw 의 구조화 값으로 대체한다.
"""
import importlib.util, os

_D = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('view_text', os.path.join(_D, 'view.py'))
_V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_V)

SCHEMA = 1
N_SLOTS = 8          # fieldsim.MAXSEAT. live2 경로의 테이블은 8 슬롯 고정


def _log(entries):
    return [{'seat': s, 'action': a, 'amount': amt} for (s, a, amt) in (entries or [])]


def _legal(raw, hero_inv, stage, street_log):
    """runner.Round.apply 규칙과 같은 조건으로 합법 액션을 만든다.
    금액은 전부 '이번 스트리트 총 투입 목표(raise-to)' 단위."""
    tc = raw['tocall']; st = raw['stack']
    mn = raw.get('min_raise', 0)
    max_to = hero_inv + st                         # 올인 시 총 투입액
    opened = stage == 'preflop' or any(a in ('bet', 'raise', 'allin')
                                       for (_, a, _) in (street_log or []))
    out = {'fold': tc > 0,
           'check': tc == 0,
           'call': min(tc, st) if tc > 0 else None,
           'call_is_allin': tc >= st > 0,
           'raise': None}
    if tc >= st or not raw.get('can_raise', True):
        return out
    kind = 'raise' if opened else 'bet'
    if mn >= max_to:                               # 최소 레이즈가 스택 이상 → 올인만
        out['raise'] = {'kind': kind, 'min_to': max_to, 'max_to': max_to, 'allin_only': True}
    else:
        out['raise'] = {'kind': kind, 'min_to': mn, 'max_to': max_to, 'allin_only': False}
    return out


def build(raw, hand, field=None, level=None, blinds=None, hand_no=None, notes=None,
          start_stack=30000):
    v = _V.build(raw, hand, field, level, blinds, hand_no, notes, start_stack)
    inv = raw.get('contrib') or {}
    cur = raw.get('stacks')                        # 오류 응답에는 없다
    seats = []
    for r in v['seats']:
        s = r['seat']
        bet = inv.get(s, 0)
        # 원본 view 의 stack 은 hand.stacks(스트리트 시작값)라 투입분이 빠지지 않았다
        stack_now = cur[s] if cur and s in cur else r['stack'] - bet
        # pid 는 좌석과 달리 사람을 따라간다. 테이블 밸런싱으로 좌석 번호는
        # 주인이 바뀌므로, UI 메모 같은 걸 좌석에 묶으면 엉뚱한 사람에게 붙는다.
        # live2.build_hand 가 h.seat_pid 를 만들어 둔다.
        seats.append({'seat': s, 'pid': (getattr(hand, 'seat_pid', None) or {}).get(s),
                      'pos': r['pos'], 'stack': stack_now, 'bet': bet,
                      'in_hand': r['live'], 'allin': r['allin'], 'hero': r['hero']})
    # 헤즈업은 BTN과 SB가 같은 자리라 pos 문자열만 보고 버튼을 찾으면 안 된다.
    btn = getattr(hand, 'button', None)
    hero_inv = inv.get(hand.hero, 0)
    pot = raw['pot']
    out = {'schema': SCHEMA, 'type': 'decision',
           'hand_no': hand_no, 'stage': raw['stage'], 'hash': raw['hash'],
           'n_slots': N_SLOTS, 'hero_seat': hand.hero, 'button_seat': btn,
           'hero_hole': list(raw['hole']), 'board': list(raw.get('board') or []),
           'seats': seats,
           'pot_total': pot, 'pot_center': pot - sum(inv.values()),
           'to_call': raw['tocall'],
           'legal': _legal(raw, hero_inv, raw['stage'], raw.get('log')),
           'log': _log(raw.get('log')),
           'prior_log': [{'street': e[0], 'seat': e[1], 'action': e[2], 'amount': e[3]}
                         for e in (raw.get('prior_log') or [])],
           'level': v.get('level'),
           'field': {k: v['field'][k] for k in ('entries', 'remaining', 'itm', 'to_itm',
                                                'bubble', 'avg_bb', 'rank', 'tables')
                     if k in v.get('field', {})},
           'notes': list(v.get('notes') or [])}
    if raw.get('error'):
        out['error'] = raw['error']
        out['state_partial'] = cur is None         # 오류 응답은 스택 정보가 불완전
    return out


def render(v):
    return v


def render_result(res, hero=None, hand_no=None, notes=None, bb=None):
    hero = res.get('hero_seat', hero)
    shown = {}
    if res.get('showdown'):
        src = res.get('shown_hole') or res.get('hole') or {}
        shown = {str(s): list(hl) for s, hl in src.items()}
    return {'schema': SCHEMA, 'type': 'result', 'hand_no': hand_no,
            'hero_seat': hero, 'how': res.get('how'),
            'board': list(res.get('board') or []), 'pot': res.get('pot', 0),
            'showdown': bool(res.get('showdown')),
            'allin_show': bool(res.get('allin_show')),
            'show_order': list(res.get('show_order') or []),
            'mucked': list(res.get('mucked') or []),
            'winners': list(res.get('winners') or []),
            'main_winners': list(res.get('main_winners') or res.get('winners') or []),
            'pots': [{'amount': p.get('amount'), 'eligible': list(p.get('eligible') or []),
                      'winners': list(p.get('winners') or [])}
                     for p in (res.get('pots') or [])],
            'shown': shown,
            'hero_hole': list(res.get('hero_hole') or []),
            'best_five': {str(k): list(v) for k, v in (res.get('best_five') or {}).items()},
            'stacks': {str(k): v for k, v in (res.get('stacks') or {}).items()},
            'pos': {str(k): v for k, v in (res.get('pos') or {}).items()},
            'log': [{'street': e[0], 'seat': e[1], 'action': e[2], 'amount': e[3]}
                    for e in (res.get('full_log') or [])],
            'hash': res.get('hash'), 'notes': list(notes or [])}
