"""관찰되지 않는 봇 테이블의 통계 진행(coarse). 설계: docs/semantic_audit/OBSERVED_FIELD_DESIGN.md

봇 엔진을 import 하지도 부르지도 않는다. 실제 진행에서 기록한 핸드(tools/coarse_calib_collect.py)를
재표본(bootstrap)한다 — 지금 테이블과 포지션 구성·스택 깊이(bb)·버블 거리가 비슷한 실제 핸드를 골라
그 핸드의 포지션별 칩 증감(bb 단위)과 가상 핸드 길이를 그대로 적용한다.

테이블 상태(좌석, 버튼·블라인드 순서, 핸드 수, 테이블 가상 시각)는 실제 진행과 같은 fieldsim.Table
메서드로 갱신하고, 결과는 live2._vclock_table_task 와 같은 이벤트 형식으로 돌려준다. 그래서 시간순 병합,
탈락 처리, 밸런싱, 핸드포핸드는 기존 코드 그대로 쓴다.
"""
import json
import math
import os
import random
import time
import zlib

LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'coarse_params')
# 포지션 라벨의 프리플랍 순서(앞에서 뒤로). 라벨 집합이 같으면 같은 구성이다.
LABEL_ORDER = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
# 핸드포핸드 대기: 통계 핸드 가상 길이 1초당 실제 지연(초), 상한. 40초 핸드 → 2.4초.
H4H_DELAY_PER_SECOND = 0.06
H4H_DELAY_CAP = 3.0
# 테이블이 이 수 이하(파이널 직전)면 통계 진행을 쓰지 않고 실제 엔진·가상시계로 돈다.
COARSE_MIN_TABLES = 3
CANDIDATES = 200         # 한 핸드에서 거리 비교할 후보 수(같은 구성·같은 버블 구간 안에서 무작위)

_LIB = {}


# ---------- 라이브러리 ----------
def bubble_bucket(remaining, itm):
    """0: 머니 안, 1: 버블 근처(남은 인원이 ITM 의 125% 이하), 2: 그 밖."""
    if remaining is None or itm is None:
        return 2
    if remaining <= itm:
        return 0
    return 1 if remaining <= itm * 1.25 else 2


def _key(labels):
    return '|'.join(sorted(labels, key=LABEL_ORDER.index))


def hand_row(rec):
    """수집 기록 한 줄 → 라이브러리 항목. 포지션 라벨별 스택·증감(bb)."""
    bb = float(rec['bb'])
    seat_of = rec['seats']
    pos = rec.get('pos') or {}
    roles = {}
    for pid, seat in seat_of.items():
        label = pos.get(str(seat))
        if label is None:
            return None
        roles[label] = (round(rec['before'][pid] / bb, 3),
                        round((rec['after'][pid] - rec['before'][pid]) / bb, 3))
    key = _key(roles)
    labels = key.split('|')
    return key, [round(float(rec['seconds']), 2),
                 bubble_bucket(rec.get('remaining'), rec.get('itm')),
                 [roles[x][0] for x in labels], [roles[x][1] for x in labels]]


def build_library(paths):
    lib = {}
    for path in paths:
        with open(path) as fp:
            for line in fp:
                row = hand_row(json.loads(line))
                if row is not None:
                    lib.setdefault(row[0], []).append(row[1])
    return lib


def library(fmt):
    if fmt not in _LIB:
        path = os.path.join(LIB_DIR, '%s.json' % fmt)
        _LIB[fmt] = json.load(open(path)) if os.path.exists(path) else None
    return _LIB[fmt]


def available(fmt):
    return bool(library(fmt))


# ---------- 핸드 하나 ----------
def _choose(lib, labels, stacks_bb, bucket, rng):
    key = _key(labels)
    pool = lib.get(key)
    if not pool:
        # 같은 인원의 다른 구성(dead button 등)에서 가장 흔한 것을 순서대로 대응시킨다.
        same_n = [k for k in lib if len(k.split('|')) == len(labels)]
        if not same_n:
            return None, None
        key = max(same_n, key=lambda k: len(lib[k]))
        pool = lib[key]
    order = key.split('|')
    if len(pool) > CANDIDATES:
        pool = [pool[rng.randrange(len(pool))] for _ in range(CANDIDATES)]
    cur = [math.log1p(max(0.0, s)) for s in stacks_bb]

    def dist(row):
        d = sum(abs(a - math.log1p(max(0.0, b))) for a, b in zip(cur, row[2]))
        return d + (0.0 if row[1] == bucket else 1.5)
    pool = sorted(pool, key=dist)[:4]
    return pool[rng.randrange(len(pool))], order


def apply_hand(stacks, bb, row):
    """포지션 순서의 현재 스택(칩)과 실제 핸드의 증감(bb) → 새 스택. 칩 합은 보존한다.

    실제 핸드에서 스택을 다 잃은 포지션은 올인으로 보고, 이긴 쪽이 덮을 수 있는 만큼(현재 스택 기준)
    잃는다. 나머지 진 포지션은 기록된 bb 만큼(현재 스택 한도) 잃는다. 잃은 칩 합은 기록된 승자들에게
    기록된 이득 비율대로 나눈다.
    """
    rec_stacks, rec_delta = row[2], row[3]
    winners = [i for i, d in enumerate(rec_delta) if d > 0]
    if not winners:
        return list(stacks)
    cover = max(stacks[i] for i in winners)
    loss = [0] * len(stacks)
    for i, d in enumerate(rec_delta):
        if d >= 0:
            continue
        if rec_stacks[i] + d <= 0.01:                       # 기록에서 올인으로 다 잃음
            loss[i] = min(stacks[i], cover)
        else:
            loss[i] = min(stacks[i], int(round(-d * bb)))
    total = sum(loss)
    out = [s - l for s, l in zip(stacks, loss)]
    gain_w = sum(rec_delta[i] for i in winners)
    given = 0
    for i in winners:
        g = int(total * rec_delta[i] / gain_w)
        out[i] += g
        given += g
    out[max(winners, key=lambda i: rec_delta[i])] += total - given
    return out


def play_hand(f, tb, rng, lib):
    """테이블 tb 의 한 핸드를 통계로 진행. 반환: 가상 핸드 길이(초) 또는 None(진행 불가)."""
    alive = tb.ordered_alive()
    if len(alive) < 2:
        return None
    layout = tb.hand_layout()
    pos = layout['pos']
    seats = [s for s in pos]
    labels = [pos[s] for s in seats]
    by_seat = {tb.seat_of(p['pid']): p for p in alive}
    sb, bb = f.blinds()
    frozen = getattr(f, '_frozen_field', None) or f.field_snapshot()
    bucket = bubble_bucket(frozen.get('remaining'), getattr(f, 'itm', None))
    row, order = _choose(lib, labels, [by_seat[s]['stack'] / bb for s in seats], bucket, rng)
    if row is None:
        return None
    # 라이브러리 구성 순서로 현재 좌석을 맞춘다(같은 구성이면 라벨로, 아니면 프리플랍 순서로).
    if sorted(labels) == sorted(order):
        seat_by_label = {pos[s]: s for s in seats}
        ordered = [seat_by_label[x] for x in order]
    else:
        ordered = list(layout['pre_seats'])[:len(order)]
    stacks = [by_seat[s]['stack'] for s in ordered]
    new = apply_hand(stacks, bb, row)
    for s, v in zip(ordered, new):
        by_seat[s]['stack'] = int(v)
    tb.advance_button()
    tb.hands += 1
    return float(row[0])


# ---------- 테이블 작업 (live2._vclock_table_task 와 같은 계약) ----------
def coarse_table_task(mini, tid, target_seconds, session_end, frozen,
                      base_suffix, h4h_mode=False, max_hands=None):
    import copy
    import live2 as L
    f = L._load_field(L._copy_field(mini))
    f.notes = []
    tid = int(tid)
    tb = f.tables[tid]
    lib = library(f.fmt.get('key', 'standard'))
    local = float(getattr(tb, 'virtual_seconds', 0.0) or 0.0)
    _start = local
    target_seconds = float(target_seconds)
    session_end = float(session_end)
    f._frozen_field = frozen
    events, errors = [], []
    while local + 1e-9 < target_seconds and tb.n() >= 2:
        f.virtual_play_seconds = local
        f.advance_level()
        rng = random.Random(zlib.crc32(('%s|coarse|%s|%s' % (
            getattr(f, 'seed', None), tid, tb.hands + 1)).encode()))
        secs = play_hand(f, tb, rng, lib)
        if secs is None:
            errors.append('coarse: no library hand for table %s' % tid)
            break
        end = local + secs
        if target_seconds >= session_end - 1e-9 and end >= session_end:
            end = session_end
        tb.virtual_seconds = end
        out = L._dump(f)
        row = out['tables'][str(tid)]
        pids = [str(p) for p in row.get('pids') or []]
        players = {p: copy.deepcopy(out['players'][p]) for p in pids if p in out['players']}
        dead = any(int(r.get('stack', 0) or 0) <= 0 for r in players.values())
        barrier = 'hand_for_hand' if h4h_mode else ('bust' if dead else None)
        events.append({
            'tid': tid, 'end': float(end), 'players': players, 'table': copy.deepcopy(row),
            'tilt': {}, 'book_set': {}, 'book_del': [], 'time_banks': {},
            'notes': [], 'bot_log': '', 'barrier': barrier, 'coarse': True,
        })
        local = float(end)
        if barrier or (max_hands is not None and len(events) >= max_hands):
            break
    _hero = mini.get('hero_pid')
    _watched = (_hero is not None and int(_hero) >= 0
                and str(_hero) not in {str(p) for p in (mini.get('sitout_pids') or [])})
    if h4h_mode and events and _watched and H4H_DELAY_PER_SECOND > 0:
        # 핸드포핸드: 통계 테이블은 계산이 즉시 끝나 HERO 가 기다리는 느낌이 사라진다.
        # 그 테이블 핸드의 가상 길이에 비례해 잠깐 늦게 끝낸다(난수로 꾸미지 않는다).
        _prev = float(events[-2]['end']) if len(events) > 1 else _start
        _hand = max(0.0, float(events[-1]['end']) - _prev)
        time.sleep(min(H4H_DELAY_CAP, H4H_DELAY_PER_SECOND * _hand))
    f._frozen_field = None
    out = L._dump(f)
    row = out['tables'].get(str(tid), {})
    pids = [str(p) for p in row.get('pids') or []]
    return {
        'tid': tid, 'events': events, 'covered_until': float(local),
        'barrier': next((e['barrier'] for e in events if e.get('barrier')), None),
        'barrier_time': next((float(e['end']) for e in events if e.get('barrier')), None),
        'players': {p: copy.deepcopy(out['players'][p]) for p in pids if p in out.get('players', {})},
        'table': copy.deepcopy(row),
        'tilt': {p: copy.deepcopy((out.get('tilt') or {}).get(p))
                 for p in pids if p in (out.get('tilt') or {})},
        'book': L._vclock_book_subset(out.get('book') or {}, pids),
        'time_banks': {p: v for p, v in (out.get('time_banks') or {}).items() if p in pids},
        'notes': [], 'errors': errors,
    }


def use_coarse(mini, tid, frozen=None):
    """이 테이블을 통계로 진행해도 되는가. hybrid 대회이고, 앉아 있는 실제 사람(sitout 포함)이 없고,
    그 포맷의 보정 라이브러리가 있을 때만."""
    rules = mini.get('format_rules') or {}
    if rules.get('field_backend') != 'hybrid':
        return False
    # 워커는 자기 테이블만 받는다(mini). 남은 테이블 수는 대회 전체 문맥(frozen)의 남은 인원으로 본다.
    rem = (frozen or {}).get('remaining')
    seats = int(mini.get('max_seat') or 9)
    if (rem is not None and int(rem) <= (COARSE_MIN_TABLES - 1) * seats
            and not rules.get('unobserved_recovery')):
        return False                  # 파이널 직전(테이블 2개): 실제 엔진·가상시계
    if not available(mini.get('fmt') or 'standard'):
        return False
    row = (mini.get('tables') or {}).get(str(int(tid))) or {}
    pids = {str(p) for p in row.get('pids') or []}
    people = {str(p) for p in (mini.get('sitout_pids') or [])}
    hero = mini.get('hero_pid')
    if hero is not None and int(hero) >= 0:
        people.add(str(hero))
    return not (pids & people)
