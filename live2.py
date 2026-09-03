"""히어로가 직접 치는 실전 진행기. 필드 전체가 실제로 돌아간다."""
import json, os, random, math
import zlib as _zlib
import fieldsim as FS, play, session as SE, view, persona as PS, reads as RD
from table import BLINDS

D = os.path.dirname(os.path.abspath(__file__))
# 상태 파일 경로. 환경변수로 바꿀 수 있다 —
# 검사 도구가 new_game 을 부르면 **진행 중인 게임이 통째로 날아간다**
# (아카이브까지 지운다). 도구는 별도 경로를 쓰게 한다.
ST = os.environ.get('T2_LIVE_STATE') or os.path.join(D, 'live2_state.json')
_SUFFIX = '_alt' if os.environ.get('T2_LIVE_STATE') else ''



# ---------- 상태 직렬화 ----------
def _dump(f):
    return {
        'entries': f.entries, 'start_stack': f.start_stack, 'hero_pid': f.hero_pid,
        'hand_no': f.hand_no, 'level': f.level, 'itm': f.itm,
        'hands_per_level': f.hands_per_level,
        'busted_order': f.busted_order, 'hero_moves': f.hero_moves,
        'notes': f.notes,
        'fmt': f.fmt.get('key', 'standard'),
        'seed': getattr(f, 'seed', None),
        'tilt': f.tilt.state,
        'players': {str(p['pid']): {'prof': p['prof'], 'stack': p['stack'],
                                    'table': p['table'], 'seat': p['seat']}
                    for p in f.players.values()},
        'tables': {str(t): {'button': tb.button, 'hands': tb.hands,
                            'pids': [p['pid'] for p in tb.players],
                            'seats': list(tb.seats)}
                   for t, tb in f.tables.items()},
    }


def _load_field(d):
    f = FS.Field.__new__(FS.Field)
    # 시드 없이 새로 만들면 매 step 마다 필드 RNG 가 무작위로 초기화된다.
    # 기준 시드와 핸드 번호에서 파생해 복원 시점이 같으면 같은 상태가 되게 한다.
    f.rng = random.Random(_zlib.crc32(
        ('field|%s|%s' % (d.get('seed'), d.get('hand_no', 0))).encode()))
    f.entries = d['entries']; f.start_stack = d['start_stack']
    f.hero_pid = d['hero_pid']; f.hand_no = d['hand_no']; f.level = d['level']
    f.itm = d['itm']; f.hands_per_level = d['hands_per_level']
    f.busted_order = d['busted_order']; f.hero_moves = d['hero_moves']
    f.notes = d.get('notes', []); f.errors = []
    f.players = {}
    f._init_runtime(d.get('fmt'), d.get('tilt'))
    for k, v in d['players'].items():
        f.players[int(k)] = {'pid': int(k), 'prof': v['prof'], 'stack': v['stack'],
                             'table': v['table'], 'seat': v['seat']}
    f.tables = {}
    for k, v in d['tables'].items():
        tb = FS.Table(int(k), [f.players[p] for p in v['pids']], button=v['button'])
        tb.hands = v['hands']
        if v.get('seats'): tb.seats = list(v['seats'])
        f.tables[int(k)] = tb
    return f


def save(st):
    tmp = ST + '.tmp'
    with open(tmp, 'w') as fp:
        json.dump(st, fp)
        fp.flush(); os.fsync(fp.fileno())
    if os.path.exists(ST):
        try: os.replace(ST, ST + '.bak')
        except OSError: pass
    os.replace(tmp, ST)


def load():
    for p in (ST, ST + '.bak'):
        try:
            with open(p) as fp:
                d = json.load(fp)
            if d: return d
        except (OSError, ValueError):
            continue
    raise RuntimeError('상태 파일 없음')


# ---------- 게임 생성 ----------
def new_game(entries=100, start_stack=30000, seed=None, itm_frac=0.15,
             hands_per_level=12, fmt=None):
    for fn in ('hand_archive2%s.jsonl' % _SUFFIX, 'book%s.json' % _SUFFIX,
               'dynamics%s.json' % _SUFFIX):
        p = os.path.join(D, fn)
        if os.path.exists(p):
            try: os.remove(p)
            except OSError: pass
    f = FS.Field(entries=entries, start_stack=start_stack, hero_pid=0,
                 seed=seed, hands_per_level=hands_per_level, itm_frac=itm_frac,
                 fmt=fmt)
    st = {'field': _dump(f), 'actions': [], 'decisions': [], 'hand_seed': None,
          'seed': seed,
          'notes': [], 'busted': False, 'rank': None}
    save(st)
    return st


# ---------- 히어로 테이블 구성 ----------
def _hero_table_setup(f):
    """히어로 테이블을 play.Hand 가 받는 형태로. 좌석 번호는 고정 슬롯을 쓴다."""
    tb = f.hero_table()
    alive = [p for p in tb.alive() if tb.seat_of(p['pid'])]
    alive.sort(key=lambda p: tb.seat_of(p['pid']))
    seats = [tb.seat_of(p['pid']) for p in alive]
    hero_seat = None
    profs = {}; stacks = {}
    for p in alive:
        s = tb.seat_of(p['pid'])
        profs[str(s)] = p['prof']; stacks[s] = p['stack']
        if p['pid'] == f.hero_pid: hero_seat = s
    btn = seats[tb.button % len(seats)]
    return tb, alive, seats, profs, stacks, btn, hero_seat


def build_hand(st):
    f = _load_field(st['field'])
    tb, alive, seats, profs, stacks, btn, hero_seat = _hero_table_setup(f)
    sb, bb = f.blinds()
    # 리딩 장부는 이 대회 상태 안에 산다. 전역 book.json 을 쓰면
    # 대회끼리 관찰이 섞이고 같은 시드가 재현되지 않는다.
    _bk = RD.Book(); _bk.d = dict(st.get('book') or {})
    h = play.Hand(seats, profs, stacks, btn, sb, bb, hero=hero_seat,
                  seed=st['hand_seed'], book=_bk)
    h.seat_pid = {tb.seat_of(p['pid']): p['pid'] for p in alive}
    h.table_id = tb.id
    f.stamp(h)
    return f, tb, alive, h, hero_seat


def level_of(f): return f.level


# ---------- 진행 ----------
def step(action=None, amount=0):
    st = load()
    f = _load_field(st['field'])

    if st['hand_seed'] is None:
        f.hand_no += 1
        prev_level = f.level
        f.advance_level()
        st['notes'] = list(f.notes[-3:]) if f.level != prev_level else []
        f.notes = []
        # 전역 random 을 쓰면 OS 엔트로피로 시드되어 **같은 시드가 재현되지 않는다.**
        # 실제로 같은 seed 로 new_game 을 세 번 하면 매번 다른 핸드가 나왔다.
        # 기준 시드와 핸드 번호에서 결정론적으로 파생한다.
        _base = st.get('seed')
        if _base is None:
            _base = random.randrange(10**9); st['seed'] = _base
        st['hand_seed'] = _zlib.crc32(('%s|%d' % (_base, f.hand_no)).encode()) % (10**9)
        st['actions'] = []; st['decisions'] = []
        st['field'] = _dump(f)
        save(st)

    f, tb, alive, h, hero_seat = build_hand(st)
    run = SE.HandRun(h, decisions=st.get('decisions'))
    raw = run.start()
    for (a, amt) in st['actions']:
        if isinstance(raw, dict) and raw.get('done'): break
        raw = run.send(a, amt)

    if action is not None and not (isinstance(raw, dict) and raw.get('done')):
        raw2 = run.send(action, amount)
        if isinstance(raw2, dict) and raw2.get('error'):
            return {'view': _render(raw2, f, h, st), 'done': False, 'raw': raw2}
        st['actions'].append([action, amount])
        st['decisions'] = [list(d) for d in run.recorded]
        save(st)
        raw = raw2

    if isinstance(raw, dict) and raw.get('done'):
        return finish(st, f, tb, alive, h, run)
    return {'view': _render(raw, f, h, st), 'done': False, 'raw': raw}


def _render(raw, f, h, st):
    sb, bb = f.blinds()
    stt = f.status()

    class _F:
        def status(self_): return stt
        def avg_stack_bb(self_, ss, b): return stt['avg']/b
    v = view.build(raw, h, _F(), f.level, (sb, bb), f.hand_no, st.get('notes'),
                   f.start_stack)
    return view.render(v)


def finish(st, f, tb, alive, h, run):
    res = run.result or {}
    # 히어로 테이블 스택 반영
    for p in alive:
        s = tb.seat_of(p['pid'])
        if s: p['stack'] = int(h.stacks.get(s, p['stack']))
    tb.button = (tb.button + 1) % max(1, len(alive))
    tb.hands += 1

    import dynamics as DY
    try: pass   # 틸트는 대회 객체가 들고 있다
    except Exception: pass

    # 다른 테이블 진행
    f.step_others()
    f._collect_busts(); f._balance()

    notes = list(f.notes); f.notes = []
    hero = f.players[f.hero_pid]
    busted = hero['stack'] <= 0
    rank = None
    if busted:
        # 히어로가 이미 busted_order 에 들어갔으므로 그 위치로 순위를 계산
        if f.hero_pid in f.busted_order:
            after = len(f.busted_order) - f.busted_order.index(f.hero_pid) - 1
            rank = f.remaining() + 1 + after
        else:
            rank = f.remaining() + 1
        itm = ' (ITM!)' if rank <= f.itm else ''
        notes.append('💀 탈락 — %d명 중 %d위%s' % (f.entries, rank, itm))

    st['field'] = _dump(f)
    st['book'] = h.book.d                      # 이 대회의 리딩 누적을 함께 저장
    st['hand_seed'] = None; st['actions'] = []; st['decisions'] = []
    st['notes'] = notes
    st['busted'] = busted; st['rank'] = rank
    save(st)

    _archive(st, f, h, res, notes)
    res['hero_seat'] = h.hero
    return {'done': True, 'result': res, 'notes': notes, 'hand_no': f.hand_no,
            'busted': busted, 'rank': rank, 'status': f.status()}


def _archive(st, f, h, res, notes):
    path = os.path.join(D, 'hand_archive2%s.jsonl' % _SUFFIX)
    rec = {'hand_no': f.hand_no, 'hash': getattr(h, 'hash', None),
           'level': f.level, 'blinds': list(f.blinds()),
           'button': h.button, 'hero': h.hero,
           'pos': {str(k): v for k, v in h.pos.items()},
           'hole': {str(k): v for k, v in h.hole.items()},
           'board': h.board,
           'stacks_before': {str(k): v for k, v in getattr(h, '_start_stacks', {}).items()},
           'full_log': res.get('full_log', []),
           'intents': getattr(h, 'intents', []),
           'reads': getattr(h, 'reads_log', []),
           'result': {k: v for k, v in res.items() if k != 'full_log'},
           'field': f.status(), 'notes': notes,
           'profiles': {str(s): h.prof.get(str(s), {}) for s in h.seats}}
    with open(path, 'a') as fp:
        fp.write(json.dumps(rec, ensure_ascii=False, default=str) + '\n')
