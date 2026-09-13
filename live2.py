"""히어로가 직접 치는 실전 진행기. 필드 전체가 실제로 돌아간다."""
import copy, json, os, random, math, time
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
        # 틸트 키가 좌석에서 사람(pid)으로 바뀌었다. 이 표시가 없는 저장본은
        # 좌석 키('1'..'8')라서 pid 1..8 과 그대로 충돌한다 — 3번 자리의
        # 누적 틸트가 pid 3 인 사람에게 붙는다. 그런 상태는 버린다.
        'tilt_key': 'pid',
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
    # **시드를 객체에 되돌려 놓아야 한다.** 예전에는 d 에서 읽어 RNG 파생에만
    # 쓰고 f.seed 를 복원하지 않았다. 그러면 다음 save() 에서 _dump 의
    # getattr(f,'seed',None) 이 None 을 저장하고, 그 뒤로 영구히 None 이 된다.
    # 결과: (1) 실험 재현 불가 (2) crc32('field|None|n') 로 파생되어
    # **어떤 시드로 시작하든 두 번째 핸드부터 같은 필드 RNG 를 쓴다.**
    f.seed = d.get('seed')
    f.entries = d['entries']; f.start_stack = d['start_stack']
    f.hero_pid = d['hero_pid']; f.hand_no = d['hand_no']; f.level = d['level']
    f.itm = d['itm']; f.hands_per_level = d['hands_per_level']
    f.busted_order = d['busted_order']; f.hero_moves = d['hero_moves']
    f.notes = d.get('notes', []); f.errors = []
    f.players = {}
    f._init_runtime(d.get('fmt'),
                    d.get('tilt') if d.get('tilt_key') == 'pid' else None)
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
    # 지우지 말고 옮긴다. 예전에는 os.remove 였는데, T2_LIVE_STATE 로 상태
    # 파일을 다른 경로에 두어도 **아카이브는 여전히 모듈 폴더(D)에 _SUFFIX
    # 이름으로 쓰인다.** 그래서 격리한 줄 알고 테스트를 돌렸다가 진행 중이던
    # 세션의 37핸드 기록을 통째로 날렸다. 되돌릴 방법이 없었다.
    _stamp = time.strftime('%Y%m%d_%H%M%S')
    for fn in ('hand_archive2%s.jsonl' % _SUFFIX, 'book%s.json' % _SUFFIX,
               'dynamics%s.json' % _SUFFIX, 'bot_hands%s.jsonl' % _SUFFIX):
        p = os.path.join(D, fn)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            try: os.rename(p, os.path.join(D, 'bak_%s_%s' % (_stamp, fn)))
            except OSError:
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
    # **깊은 복사여야 한다.** dict() 는 겉 매핑만 복사하고 Book.rec() 가
    # 돌려주는 안쪽 카운터 dict 는 st['book'] 과 그대로 공유된다.
    # 그러면 핸드를 진행하는 동안 쌓인 관측이 st 에 그대로 새고,
    # step() 의 save(st) 가 그걸 **핸드 도중에** 파일에 박는다.
    # 결과: (1) 다음 요청이 재생할 때 장부가 이미 이번 핸드 관측을 품고 있어
    # 봇의 프리플랍 판단이 라이브와 달라지고(= 기록된 히어로 액션이 불법이 됨),
    # (2) 요청마다 같은 관측이 다시 누적돼 리딩이 몇 배로 부풀려진다.
    _bk = RD.Book(); _bk.d = copy.deepcopy(st.get('book') or {})
    h = play.Hand(seats, profs, stacks, btn, sb, bb, hero=hero_seat,
                  seed=st['hand_seed'], book=_bk)
    h.seat_pid = {tb.seat_of(p['pid']): p['pid'] for p in alive}
    h.table_id = tb.id
    f.stamp(h)
    return f, tb, alive, h, hero_seat


def level_of(f): return f.level


# ---------- 밀린 '다른 테이블 진행' ----------
# finish 가 defer_others=True 로 불리면 step_others 를 건너뛰고 상태에
# others_pending 표시만 남긴다. 실제 계산은 밖에서(워커 프로세스) 하고,
# 결과를 다음 step() 에 넘겨준다. 넘겨받지 못했으면 여기서 직접 돌린다.
#
# **워커는 상태 파일을 쓰지 않는다.** compute_others 는 필드 덤프를 받아
# 필드 덤프를 돌려줄 뿐이고, 파일 쓰기는 전부 기존 메인 경로(resume_others →
# save)가 한다. 그래야 쓰기가 한 곳으로 직렬화된다.
def compute_others(field_dump):
    """다른 테이블을 진행시킨다. 순수 함수 — 파일을 읽지도 쓰지도 않는다.

    finish 의 원래 순서를 그대로 재현한다. step_others() 가 끝에서
    _collect_busts/_balance 를 부르고, finish 가 그 뒤에 한 번 더 부른다.
    호출 횟수까지 같아야 결과가 같다(tools/verify_settle_split.py 로 확인함).

    _load_field 는 프로필 dict 를 넘겨받은 덤프와 그대로 공유하므로
    (live2.py 의 _load_field 참고) 반드시 깊은 복사로 넘긴다.
    """
    f = _load_field(copy.deepcopy(field_dump))
    f.notes = []
    # 봇 핸드 기록은 fieldsim._log_bot_hand 가 모듈 폴더에 직접 append 한다.
    # 워커에서 그대로 두면 (1) 결과를 버리고 다시 계산할 때 줄이 중복되고
    # (2) 워커가 쓰기 도중 죽으면 줄이 잘린다. 실제로 둘 다 관측했다.
    # 그래서 워커에서는 임시 접미사로 빼두고, 파일에 붙이는 일은
    # resume_others(= 메인 경로) 가 한다. 쓰기는 한 곳으로 모은다.
    _suf = FS.BOT_SUFFIX
    _tmp = '%s_pending_%d' % (_suf, os.getpid())
    FS.BOT_SUFFIX = _tmp
    try:
        f.step_others()
        f._collect_busts(); f._balance()
    finally:
        FS.BOT_SUFFIX = _suf
    _p = os.path.join(D, 'bot_hands%s.jsonl' % _tmp)
    _bot_log = ''
    if os.path.exists(_p):
        with open(_p) as fp:
            _bot_log = fp.read()
        try: os.remove(_p)
        except OSError: pass
    return {'field': _dump(f), 'notes': list(f.notes), 'bot_log': _bot_log,
            'key': _others_key(field_dump)}


def _others_key(field_dump):
    """어느 시점의 필드로 계산했는지 못박는 지문."""
    return _zlib.crc32(json.dumps(field_dump, sort_keys=True,
                                  separators=(',', ':')).encode())


def resume_others(st, others=None):
    """밀린 다른 테이블 진행을 마무리하고 상태에 반영한다.

    others 가 주어지고 지문이 맞으면 그 결과를 쓰고(hit), 아니면 여기서
    직접 계산한다(fallback). 지문이 어긋나면 **버린다.** 성능 때문에
    상태의 정확성을 희생하지 않는다.
    """
    if not st.get('others_pending'):
        return None
    want = _others_key(st['field'])
    how = 'hit'
    if others is None:
        how = 'fallback'
    elif others.get('key') != want:
        how = 'mismatch'
    if how != 'hit':
        others = compute_others(st['field'])
    st['field'] = others['field']
    if others.get('bot_log'):          # 워커가 모아둔 봇 핸드 기록을 여기서 붙인다
        with open(os.path.join(D, 'bot_hands%s.jsonl' % FS.BOT_SUFFIX), 'a') as fp:
            fp.write(others['bot_log'])
    _new_notes = list(others.get('notes') or [])
    if _new_notes:
        st['pending_notes'] = list(st.get('pending_notes') or []) + _new_notes
    rec = st.pop('pending_archive', None)
    if rec is not None:
        # 정산이 끝났으니 비워둔 자리를 채운다. 키 순서는 그대로다.
        rec['field'] = _load_field(copy.deepcopy(others['field'])).status()
        rec['notes'] = list(rec.get('notes') or []) + _new_notes
        _archive_write(rec)
    st.pop('others_pending', None)
    save(st)
    return how


# ---------- 진행 ----------
def step(action=None, amount=0, defer_others=False, others=None):
    st = load()
    # 밀린 진행이 있으면 **다음 핸드를 딜하기 전에** 반드시 끝낸다.
    # 서버가 죽어도 상태 파일의 others_pending 이 남아 여기서 복구된다.
    if st.get('others_pending'):
        resume_others(st, others)
    f = _load_field(st['field'])

    if st['hand_seed'] is None:
        # 미뤄둔 진행이 남긴 알림(테이블 브레이크·자리 이동)을 여기서 붙인다.
        # defer 를 안 쓰면 pending_notes 가 아예 없어 기존과 동일하다.
        _pending_notes = list(st.pop('pending_notes', None) or [])
        f.hand_no += 1
        prev_level = f.level
        f.advance_level()
        st['notes'] = _pending_notes + (list(f.notes[-3:]) if f.level != prev_level else [])
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
        if isinstance(raw, dict) and (raw.get('done') or raw.get('error')): break
        raw = run.send(a, amt)

    # 재생 중 기록된 액션이 불법이 됐으면 여기서 멈추고 정상 오류 응답으로 돌려준다.
    # 예전에는 오류 프레임에 **다음 기록 액션**을 그대로 먹였다. session 의
    # 히어로 재적용(프리플랍 157 · 포스트플랍 337)은 try 밖이라 ValueError 가
    # 서버까지 올라가 500 이 됐고, 상태가 저장되지 않아 다시 눌러도 같은 벽이었다
    # (= 그 핸드 영구 차단). 원인(재생 재지터)은 session 쪽에서 없앴지만
    # 안전망으로 남긴다.
    if isinstance(raw, dict) and raw.get('error'):
        return {'view': _render(raw, f, h, st), 'done': False, 'raw': raw}

    if action is not None and not (isinstance(raw, dict) and raw.get('done')):
        raw2 = run.send(action, amount)
        if isinstance(raw2, dict) and raw2.get('error'):
            return {'view': _render(raw2, f, h, st), 'done': False, 'raw': raw2}
        st['actions'].append([action, amount])
        st['decisions'] = [list(d) for d in run.recorded]
        save(st)
        raw = raw2

    if isinstance(raw, dict) and raw.get('done'):
        return finish(st, f, tb, alive, h, run, defer_others=defer_others)
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


def finish(st, f, tb, alive, h, run, defer_others=False):
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

    # 다른 테이블 진행.
    # defer_others 면 여기서 건너뛰고 표시만 남긴다. 다음 step() 이 딜 전에
    # 반드시 처리한다. 단 **히어로가 터진 핸드는 미루지 않는다** — rank 가
    # f.remaining() 과 busted_order 에 달려 있어 전부 정산돼야 확정된다.
    _hero_busted_now = f.players[f.hero_pid]['stack'] <= 0
    if defer_others and not _hero_busted_now:
        st['others_pending'] = True
    else:
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

    _archive(st, f, h, res, notes, defer=bool(st.get('others_pending')))
    if st.get('pending_archive'):
        # _archive 는 save() 뒤에 불린다. 미뤄둔 기록은 따로 한 번 더 저장해야
        # 다음 step() 이 디스크에서 읽을 수 있다.
        save(st)
    res['hero_seat'] = h.hero
    res.setdefault('pos', {str(k): v for k, v in h.pos.items()})
    # 결과도 화면으로 렌더한다. 예전에는 raw dict 만 돌려줘서
    # 무슨 일이 있었는지 읽을 수 없었다(다음 판이 바로 시작됐다).
    try:
        view_txt = view.render_result(res, hero=h.hero, hand_no=f.hand_no,
                                      notes=notes, bb=f.blinds()[1])
    except Exception as e:
        view_txt = '결과 렌더 실패: %s: %s' % (type(e).__name__, e)
    return {'done': True, 'view': view_txt, 'result': res, 'notes': notes,
            'hand_no': f.hand_no, 'busted': busted, 'rank': rank,
            'status': f.status()}


def _archive_write(rec):
    path = os.path.join(D, 'hand_archive2%s.jsonl' % _SUFFIX)
    with open(path, 'a') as fp:
        fp.write(json.dumps(rec, ensure_ascii=False, default=str) + '\n')


def _archive(st, f, h, res, notes, defer=False):
    """핸드 기록. defer 면 파일에 쓰지 않고 상태에 넣어둔다.

    기록의 'field'(f.status())와 'notes' 는 다른 테이블까지 정산돼야 확정된다.
    그래서 지연 중에는 자리만 비워 두고, resume_others 가 채워서 쓴다.
    자리를 **미리 만들어 두는 것**이 중요하다 — 나중에 키를 새로 추가하면
    JSON 키 순서가 달라져 기존 파일과 바이트가 안 맞는다.
    """
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
           'field': (None if defer else f.status()), 'notes': list(notes),
           'profiles': {str(s): h.prof.get(str(s), {}) for s in h.seats}}
    if defer:
        # save() 는 default=str 를 안 쓰므로 여기서 미리 JSON 안전하게 만든다.
        st['pending_archive'] = json.loads(
            json.dumps(rec, ensure_ascii=False, default=str))
        return
    _archive_write(rec)
