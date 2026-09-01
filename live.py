"""디스크 상태 기반 실전 진행기. 매 호출마다 상태를 복원해 이어서 진행한다."""
import sys, json, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import play, session as SE, field as F, view, tourney
from table import BLINDS

D = os.path.dirname(os.path.abspath(__file__))
ST = os.path.join(D, 'live_state.json')

def _clear_history():
    """새 토너 시작 시에만 이전 기록을 지운다. 토너 종료 후에는 보존."""
    for f in ('hand_archive.jsonl', 'book.json', 'dynamics.json'):
        p = os.path.join(D, f)
        if os.path.exists(p):
            try: os.remove(p)
            except OSError: pass

def new_game(entries=100, start_stack=30000, hero=7, seed=None, buyin=1.0):
    _clear_history()
    import math as _m
    seed = seed if seed is not None else int.from_bytes(os.urandom(4), 'big')
    rng = random.Random(seed)
    quality = F.field_quality(entries, buyin)
    seats = list(range(1, 9))
    profiles = {}
    for s in seats:
        if s == hero:
            profiles[str(s)] = {'type':'TAG','label':'HERO','aggr':6,'gamble':4,'bluff':5,
                                'icm':6,'value':'mixed','tilt':3,'goal':'accum'}
        else:
            profiles[str(s)] = tourney.mk_profile(quality, rng)
    f = F.Field(entries, seed=rng.randrange(10**6))
    st = {'seed': seed, 'entries': entries, 'start_stack': start_stack, 'hero': hero,
          'seats': seats, 'profiles': profiles,
          'stacks': {str(s): start_stack for s in seats},
          'button': rng.choice(seats), 'hand_no': 0, 'hpl': 12,
          'field': {'remaining': entries, 'itm': f.itm, 'aggression': f.aggression,
                    'structure': f.structure, 'variance': f.variance, 'hand_no': 0,
                    'desc': f.descriptor()},
          'fmt': 'standard', 'field_q': quality,
          'moves': 0, 'actions': [], 'hand_seed': None, 'notes': [], 'busted': False,
          'empty_since': {}, 'decisions': [],
          # 필드 칩 원장: 전체 칩 - 우리 테이블 칩 = 다른 테이블 칩
          'field_pool': entries*start_stack - 8*start_stack}
    json.dump(st, open(ST,'w'))
    return st

def load():
    """손상된 상태 파일이면 백업본으로 복구."""
    for p in (ST, ST + '.bak'):
        try:
            with open(p) as f:
                d = json.load(f)
            if d: return d
        except (OSError, ValueError):
            continue
    raise RuntimeError('상태 파일 복구 실패')

def save(st):
    """원자적 저장 — 임시파일에 쓰고 교체. 직전 상태는 .bak 로 보존."""
    tmp = ST + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(st, f)
        f.flush(); os.fsync(f.fileno())
    if os.path.exists(ST):
        try: os.replace(ST, ST + '.bak')
        except OSError: pass
    os.replace(tmp, ST)

def mkfield(st):
    d = st['field']
    # 핸드마다 다른 시드 — 고정 시드면 매번 같은 난수가 나와 필드가 안 줄어든다
    f = F.Field(st['entries'], seed=hash((st['seed'], st['hand_no'], d['hand_no'])) & 0xffffffff)
    f.remaining = d['remaining']; f.itm = d['itm']
    f.aggression = d['aggression']; f.structure = d['structure']
    f.variance = d['variance']; f.hand_no = d['hand_no']
    return f

def level(st): return min(1 + st['hand_no']//st['hpl'], len(BLINDS))
def blinds(st):
    _, sb, bb = BLINDS[level(st)-1]; return sb, bb

def build_hand(st):
    stacks = {int(k): v for k, v in st['stacks'].items()}
    sb, bb = blinds(st)
    # 리딩 장부는 이 대회 상태 안에 산다 (live2 와 동일한 규칙).
    import reads as _RD2
    _bk = _RD2.Book(); _bk.d = dict(st.get('book') or {})
    h = play.Hand(st['seats'], st['profiles'], stacks, st['button'], sb, bb,
                  hero=st['hero'], seed=st['hand_seed'], book=_bk)
    _stamp_from_state(st, h)
    return h


_LIVE_TILT = {}


def _stamp_from_state(st, h):
    """JSON 상태에서 대회 문맥을 만들어 심는다.

    live 는 Field 객체가 아니라 dict 상태로 돌아서 fieldsim.stamp 를 쓸 수 없다.
    그래도 무엇을 심을지는 context.SPEC 한 곳에서 정한다 — 목록이 갈리면
    이 경로에서만 기능이 죽는다(예전에 실제로 그랬다).
    """
    import context as CTX, formats as FM, dynamics as _DY
    fmt = FM.get(st.get('fmt'))
    itm = st['field']['itm']
    rem = st['field']['remaining']
    entries = st.get('entries', 100)
    start = st.get('start_stack', 30000)
    lvl = level(st)
    key = st.get('seed')
    tilt = _LIVE_TILT.setdefault(key, _DY.Tilt())
    bb = blinds(st)[1]
    CTX.Context(
        field_q=st.get('field_q', 0.6),
        field_remaining=rem,
        field_itm=itm,
        field_avg_stack=entries*start/max(1, rem),
        payouts=FM.payouts(itm, fmt['payout_flat']),
        payout_flat=fmt['payout_flat'],
        ante=(bb if lvl >= fmt['ante_from'] else 0),
        dyn=tilt,
        erosion_per_hand=CTX.erosion(st.get('hpl', 12), fmt['blind_mult']),
        reentry=fmt['reentry'],
        progress=CTX.progress_of(rem, entries),
    ).apply(h, strict=True)
    return h

def step(action=None, amount=0):
    st = load()
    if st['hand_seed'] is None:
        st['hand_no'] += 1
        st['hand_seed'] = random.randrange(10**9)
        st['actions'] = []
        lv_prev = min(1 + max(0, st['hand_no']-2)//st['hpl'], len(BLINDS))
        st['notes'] = []
        if level(st) > lv_prev and st['hand_no'] > 1:
            sb, bb = blinds(st)
            st['notes'].append('⏱ 레벨 %d — %s/%s (%s ante)' % (level(st), f'{sb:,}', f'{bb:,}', f'{bb:,}'))
        save(st)
    h = build_hand(st)
    run = SE.HandRun(h, decisions=st.get('decisions'))
    raw = run.start()
    for (a, amt) in st['actions']:
        if isinstance(raw, dict) and raw.get('done'): break
        raw = run.send(a, amt)
    if action is not None and not (isinstance(raw, dict) and raw.get('done')):
        raw2 = run.send(action, amount)
        if isinstance(raw2, dict) and raw2.get('error'):
            return {'view': view.render(view.build(raw2, h, mkfield(st), level(st),
                    blinds(st), st['hand_no'], st['notes'], st['start_stack'])), 'done': False}
        st['actions'].append([action, amount])
        st['decisions'] = [list(d) for d in run.recorded]
        save(st)
        raw = raw2
    if isinstance(raw, dict) and raw.get('done'):
        return finish(st, h, run)
    f = mkfield(st)
    return {'view': view.render(view.build(raw, h, f, level(st), blinds(st),
            st['hand_no'], st['notes'], st['start_stack'])), 'done': False, 'raw': raw}

def archive_hand(st, h, run, res):
    import json as _j, os as _o
    path = _o.path.join(D, 'hand_archive.jsonl')
    rec = {'tourney': st.get('seed'), 'hand_no': st['hand_no'], 'hash': getattr(h, 'hash', None),
           'level': level(st), 'blinds': list(blinds(st)),
           'button': st['button'], 'hero': st['hero'],
           'pos': {str(k): v for k, v in h.pos.items()},
           'hole': {str(k): v for k, v in h.hole.items()},   # 전 좌석 홀카드
           'board': h.board,
           'stacks_before': {k: v for k, v in st['stacks'].items()},
           'full_log': res.get('full_log', []),
           'intents': getattr(h, 'intents', []),
           'reads': getattr(h, 'reads_log', []),
           'result': {k: v for k, v in res.items() if k not in ('full_log',)},
           'profiles': {k: v.get('type') for k, v in st['profiles'].items()},
           'field': dict(st['field']),
           'table_change': any(('합류' in n or '이동' in n) for n in (st.get('notes') or []))}
    key = (rec.get('tourney'), rec['hand_no'])
    if _o.path.exists(path):
        try:
            for line in open(path):
                if not line.strip(): continue
                d = _j.loads(line)
                if (d.get('tourney'), d.get('hand_no')) == key:
                    return rec          # 이미 기록됨
        except Exception:
            pass
    with open(path, 'a') as f:
        f.write(_j.dumps(rec, ensure_ascii=False, default=str) + '\n')
    return rec

def finish(st, h, run):
    res = run.result or {}
    try:
        import dynamics as _DY
        pass   # 틸트는 대회 객체가 들고 있다. 파일 저장 안 함
    except Exception: pass
    try: archive_hand(st, h, run, res)
    except Exception as e: pass
    st['stacks'] = {str(k): v for k, v in h.stacks.items()}
    f = mkfield(st)
    if st['stacks'].get(str(st['hero']), 0) <= 0:
        st['busted'] = True
        f.remaining = max(1, f.remaining-1)
    else:
        busts = len([s for s in st['seats']
                     if float(st['stacks'].get(str(s), 0)) <= 0
                     and str(s) not in (st.get('empty_since') or {})])
        alive_seats = len([s for s in st['seats'] if float(st['stacks'].get(str(s), 0)) > 0])
        out = f.step(level(st), 1, table_seats=max(2, alive_seats), table_busts=busts)
        if out: st['notes'].append('필드 %d명 탈락 → %d명 생존' % (out, f.remaining))
    # 좌석 재조정
    rng = random.Random(st['hand_seed'])
    tb = F.Tables(f, 8, st['hero'], seed=rng.randrange(10**6))
    sb, bb = blinds(st)
    # 공석 발생 시점 기록
    st.setdefault('empty_since', {})
    for s in st['seats']:
        if st['stacks'].get(str(s), 0) <= 0 and s != st['hero']:
            st['empty_since'].setdefault(str(s), st['hand_no'])
        else:
            st['empty_since'].pop(str(s), None)
    pool = st.get('field_pool', 0)
    nc, moved, notes = tb.reconcile(st['seats'], {int(k):v for k,v in st['stacks'].items()},
                                    st['profiles'], st['start_stack'], bb,
                                    empty_since=st['empty_since'], hand_no=st['hand_no'])
    if moved and not st['busted']:
        st['moves'] += 1
        avg = f.avg_stack_bb(st['start_stack'], bb)
        old_others = sum(float(v) for k, v in st['stacks'].items() if int(k) != st['hero'])
        pool += old_others                      # 두고 온 테이블 칩은 풀로 반환
        for s in st['seats']:
            if s == st['hero']: continue
            p = F.make_player(rng, s, avg)
            want = min(max(bb, int(round(p['stack_bb']*bb))), max(bb, int(pool)))
            pool -= want
            st['stacks'][str(s)] = want
            st['profiles'][str(s)] = {k: v for k, v in p.items() if k != 'stack_bb'}
        st['notes'].append('🔄 테이블 이동 (%d번째) — 상대 전원 교체' % st['moves'])
    else:
        empty = [s for s in st['seats'] if st['stacks'].get(str(s),0) <= 0 and s != st['hero']]
        for p in nc:
            if not empty or pool <= bb: break
            s = empty.pop(0)
            want = max(bb, int(round(p['stack_bb']*bb)))
            want = int(min(want, pool))              # 필드 풀을 초과할 수 없다
            pool -= want
            st['stacks'][str(s)] = want
            st['profiles'][str(s)] = {k: v for k, v in p.items() if k != 'stack_bb'}
            st['notes'].append('%d번 자리에 새 플레이어 합류 (%dbb)' % (s, round(want/bb)))
            st['empty_since'].pop(str(s), None)
    for n in notes:
        if '자리 이동' not in n and '합류' not in n:
            st['notes'].append(n)
    st['field_pool'] = max(0, int(pool))
    alive = [s for s in st['seats'] if st['stacks'].get(str(s),0) > 0]
    if alive:
        b = st['button']
        st['button'] = alive[(alive.index(b)+1) % len(alive)] if b in alive else alive[0]
    st['field'] = {'remaining': f.remaining, 'itm': f.itm, 'aggression': f.aggression,
                   'structure': f.structure, 'variance': f.variance, 'hand_no': f.hand_no,
                   'desc': st['field']['desc']}
    st['book'] = h.book.d                      # 이 대회의 리딩 누적
    st['hand_seed'] = None; st['actions'] = []; st['decisions'] = []
    save(st)
    return {'done': True, 'result': res, 'notes': st['notes'], 'hand_no': st['hand_no'],
            'stacks': st['stacks'], 'busted': st['busted'], 'hero': st['hero']}
