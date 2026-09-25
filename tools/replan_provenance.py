#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A6 replan input/provenance characterization.

Production 코드를 바꾸지 않고, board_changed -> revise_plan -> make_plan 경로가
현재 decision context 대신 기본값/옛 plan snapshot을 쓰는 문제를 측정한다.

측정 대상 7개:
  oop_vs_aggr
  oop_legacy_abs
  initiative
  tilt
  bb_chips
  opp_est
  opp_stack_bb

두 질문을 분리한다.

1) provenance mismatch
   현재 update_plan 입력과 revise_plan이 실제 make_plan에 쓰는 값이 몇 번 다른가?

2) behavioral impact
   그 필드 하나만 현재값으로 교체했을 때 최종 update_plan 반환의
   plan / intent act / intent size가 몇 번 달라지는가?

모든 반사실은 live run이 끝난 뒤 deep-copy한 입력을 재생한다.
live 엔진 RNG 스트림을 건드리지 않는다.

고정 fixture:
  seeds 5150,9001,4242
  fmt standard,deep,turbo
  각 16 global hands
  entries=100

과거 조사에서 이 fixture는 board_changed 재계획 make_plan 810건을 냈다.
이 도구는 그 수를 먼저 출력하지만, 숫자를 맞추기 위해 production을
바꾸지 않는다.

실행:
  python3 tools/replan_provenance.py
  python3 tools/replan_provenance.py --json

------------------------------------------------------------------ 최적화

fixture·arm·측정 정의는 바꾸지 않았다. 줄인 것은 **중복 재생**뿐이다.

  naive 18,581 재생 → 13,267 (-28.6%).  810 events 기준.

근거가 되는 항등식 두 개.

  (1) replay(ev, S) == replay(ev, S ∩ dev(ev))
      dev(ev) = current 값이 baseline 과 실제로 다른 필드.
      누락 5필드는 선택하지 않으면 make_plan 기본값이 쓰이는데
      BASELINE_DEFAULT 가 정확히 그 기본값이다(_assert_defaults 가
      실행 시 확인한다). snapshot 2필드의 baseline 은 state.get(...)
      그 자체다. 따라서 값이 같은 필드는 arm 에 들어 있어도 결과를
      바꿀 수 없다.
  (2) S ∩ dev(ev) 가 비면 production baseline 재생과 같다.

여기서 자동으로 합쳐지는 것들:
  * all_current 와 interaction_arms['all7'] 은 같은 arm 이다(원본은
    두 번 돌렸다).
  * tilt 는 이 fixture 에서 한 번도 다르지 않다 → leave-one-out 의
    '-tilt' 는 all7 과 같은 재생이다.
  * dev(ev) 가 작은 event 에서 여러 arm 이 같은 effective set 으로 모인다.

즉 arm 을 지운 것이 아니라, 같은 입력으로 귀결되는 재생을 한 번만 한다.
subset old-vs-new exact equivalence 는 --equiv N 으로 확인한다
(analyze_reference 가 원본 구현 그대로 남아 있다).

  --equiv N          앞 N event 로 원본과 결과 dict 완전 일치 확인
  --estimate-only    capture 와 계량만 하고 arm 재생 전에 멈춘다
  --checkpoint PATH  재생 서명 저장. --resume 으로 이어서 실행
  --heartbeat SEC    진행 표시 간격(기본 10초). 무출력 구간을 만들지 않는다
  --max-events N     subset 실행. **고정 fixture 결과가 아니다**

--resume 은 tool revision, production code digest, fixture 정의,
event 수, event digest, arm 명세 digest 가 **전부** 일치할 때만 서명을
되살린다. 하나라도 어긋나면 종료코드 3 으로 거부한다 — 낡은 서명을
새 코드의 결과로 섞지 않는다.
"""
from __future__ import print_function

import argparse
import copy
import hashlib
import inspect
import json
import os
import sys
import time
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import plan as PL
import runner as RU


SEEDS = (5150, 9001, 4242)
FMTS = ('standard', 'deep', 'turbo')
HANDS = 16
ENTRIES = 100

FIELDS = (
    'oop_vs_aggr',
    'oop_legacy_abs',
    'initiative',
    'tilt',
    'bb_chips',
    'opp_est',
    'opp_stack_bb',
)

# revise_plan 현재 production 의미.
# opp_* 둘은 state snapshot, 나머지 다섯은 make_plan 기본값.
BASELINE_DEFAULT = {
    'oop_vs_aggr': None,
    'oop_legacy_abs': None,
    'initiative': True,
    'tilt': 0.0,
    'bb_chips': None,
}


def _same(a, b):
    """provenance equality. float은 이 경로에서 계산식이 단순하므로 exact 비교."""
    return a == b


def _intent_sig(st, street):
    it = PL.intent_of(st, street) or {}
    return {
        'plan': (st or {}).get('plan'),
        'act': it.get('act'),
        'size': round(it.get('size', 0) or 0, 6),
    }


def _diff_kind(a, b):
    out = []
    for k in ('plan', 'act', 'size'):
        if a.get(k) != b.get(k):
            out.append(k)
    return tuple(out)


def _capture_events(hb=None, max_events=None):
    """live run에서는 입력만 저장. 반사실 재생은 끝난 뒤 한다.

    hb         진행 표시용 Heartbeat. 측정에는 영향이 없다.
    max_events None 이면 고정 fixture 전체. 정수면 그 수만큼 모은 뒤
               현재 핸드를 끝내고 멈춘다 — subset 동치성 시험 전용이고
               events 는 전체 실행의 앞부분과 같은 prefix 다.
    """
    orig_update = PL.update_plan
    sig_update = inspect.signature(orig_update)
    events = []
    counts = Counter()

    def wrapped(*a, **k):
        b = sig_update.bind_partial(*a, **k)
        b.apply_defaults()

        state = b.arguments.get('state')
        first = bool(b.arguments.get('first'))
        prev_board = b.arguments.get('prev_board')
        board = b.arguments.get('board')

        counts['update_plan'] += 1
        if state is not None and not first:
            counts['revise_path'] += 1
            if RU.board_changed(prev_board, board):
                counts['board_changed'] += 1
                # update_plan의 완전한 호출 입력을 보존한다.
                # 이후 replay에서 원본 호출과 current-context arm을 동일 입력으로 비교한다.
                events.append({
                    'args': copy.deepcopy(a),
                    'kwargs': copy.deepcopy(k),
                    'current': {
                        'oop_vs_aggr': copy.deepcopy(b.arguments.get('oop_vs_aggr')),
                        'oop_legacy_abs': copy.deepcopy(b.arguments.get('oop_legacy_abs')),
                        'initiative': copy.deepcopy(b.arguments.get('initiative')),
                        'tilt': copy.deepcopy(b.arguments.get('tilt')),
                        'bb_chips': copy.deepcopy(b.arguments.get('bb_chips')),
                        'opp_est': copy.deepcopy(b.arguments.get('opp_est')),
                        'opp_stack_bb': copy.deepcopy(b.arguments.get('opp_stack_bb')),
                    },
                    'snapshot': {
                        'opp_est': copy.deepcopy((state or {}).get('opp_est')),
                        'opp_stack_bb': copy.deepcopy((state or {}).get('opp_stack_bb')),
                    },
                    'street': b.arguments.get('street'),
                })
        return orig_update(*a, **k)

    PL.update_plan = wrapped
    old_bot_log = getattr(FS.Field, 'BOT_LOG', None)
    errors = []
    try:
        if hasattr(FS.Field, 'BOT_LOG'):
            FS.Field.BOT_LOG = 0

        stop = False
        for fmt in FMTS:
            if stop:
                break
            for seed in SEEDS:
                if stop:
                    break
                f = FS.Field(entries=ENTRIES, seed=seed, fmt=fmt)
                for _ in range(HANDS):
                    if f.remaining() <= 8:
                        break
                    f.hand_no += 1
                    f.advance_level()
                    for tb in list(f.tables.values()):
                        if tb.n() >= 2:
                            f._play_table(tb)
                        if hb is not None:
                            hb.tick(len(events),
                                    'capture %s/%d hand %d' % (fmt, seed, f.hand_no))
                    f._collect_busts()
                    f._balance()
                    if max_events is not None and len(events) >= max_events:
                        stop = True
                        break
                errors.extend(getattr(f, 'errors', ()) or ())
                if stop:
                    break
    finally:
        PL.update_plan = orig_update
        if old_bot_log is not None:
            FS.Field.BOT_LOG = old_bot_log

    counts['engine_errors'] = len(errors)
    return events, counts, errors


def _effective_baseline(event, field):
    if field in ('opp_est', 'opp_stack_bb'):
        return event['snapshot'][field]
    return BASELINE_DEFAULT[field]


def _candidate_revise_factory(current, selected):
    """선택한 필드만 current context를 쓰는 revise_plan."""
    def candidate(state, hero, board, my_range, opp_range, profile, pot, stack, street,
                  seed, n_opp, behind, prev_board,
                  oop_vs_aggr=None, oop_legacy_abs=None, initiative=True):
        # Post-A5 production revise_plan now accepts the three position-context
        # kwargs.  The counterfactual candidate intentionally ignores the
        # call-time values here and reconstructs the requested arm from the
        # captured event/current context below.
        if not RU.board_changed(prev_board, board):
            return state

        kw = {
            'seed': seed,
            'n_opp': n_opp,
            'to_act_behind': behind,
            # production baseline은 snapshot을 쓴다.
            'opp_est': state.get('opp_est'),
            'opp_stack_bb': state.get('opp_stack_bb'),
        }

        # 누락 5개는 선택되지 않으면 아예 넘기지 않아 make_plan 기본값을 유지한다.
        if 'oop_vs_aggr' in selected:
            kw['oop_vs_aggr'] = current.get('oop_vs_aggr')
        if 'oop_legacy_abs' in selected:
            kw['oop_legacy_abs'] = current.get('oop_legacy_abs')
        if 'initiative' in selected:
            kw['initiative'] = current.get('initiative')
        if 'tilt' in selected:
            kw['tilt'] = current.get('tilt')
        if 'bb_chips' in selected:
            kw['bb_chips'] = current.get('bb_chips')

        # snapshot 두 필드는 선택되면 current로 교체한다.
        if 'opp_est' in selected:
            kw['opp_est'] = current.get('opp_est')
        if 'opp_stack_bb' in selected:
            kw['opp_stack_bb'] = current.get('opp_stack_bb')

        new = PL.make_plan(
            hero, board, my_range, opp_range, profile, pot, stack, street, **kw)
        new['revised'] = True
        for key in ('intents', 'deviations', 'streets', 'refreshed', 'bet_streets',
                    'plan_since', '_rsig'):
            if state.get(key) is not None:
                new[key] = state[key]
        return new
    return candidate


def _replay(event, selected=()):
    """한 event를 production arm 또는 selected-current arm으로 재생."""
    orig_revise = RU.revise_plan
    try:
        if selected:
            RU.revise_plan = _candidate_revise_factory(
                event['current'], set(selected))
        args = copy.deepcopy(event['args'])
        kwargs = copy.deepcopy(event['kwargs'])
        return PL.update_plan(*args, **kwargs)
    finally:
        RU.revise_plan = orig_revise


def _sample_value(v):
    if isinstance(v, dict):
        # 큰 opponent estimate 전체를 출력하지 않는다.
        keys = ('type', 'n', 'confidence', 'vpip', 'pfr', 'ftb', 'aggr', 'bluff')
        return {k: v.get(k) for k in keys if k in v}
    return v


# ---------------------------------------------------------------- arm 정의
# 측정 정의다. 순서·구성은 바꾸지 않는다. 최적화는 이 목록을 줄이지 않고
# "같은 effective 입력으로 귀결되는 재생"만 합친다.
INTERACTION_ARMS = OrderedDict([
    ('bb+opp_est', ('bb_chips', 'opp_est')),
    ('bb+opp_stack', ('bb_chips', 'opp_stack_bb')),
    ('opp_est+opp_stack', ('opp_est', 'opp_stack_bb')),
    ('context_core3', ('bb_chips', 'opp_est', 'opp_stack_bb')),
    ('core+initiative', ('bb_chips', 'opp_est', 'initiative')),
    ('core+oop_vs', ('bb_chips', 'opp_est', 'oop_vs_aggr')),
    ('core+oop_legacy', ('bb_chips', 'opp_est', 'oop_legacy_abs')),
    ('core+position', ('bb_chips', 'opp_est', 'oop_vs_aggr',
                       'oop_legacy_abs', 'initiative')),
    ('all7', FIELDS),
])
LOO_ARMS = OrderedDict(
    (f, tuple(x for x in FIELDS if x != f)) for f in FIELDS)


def arm_spec_digest():
    """arm 구성이 바뀌면 checkpoint 를 재사용하면 안 된다."""
    spec = {
        'fields': list(FIELDS),
        'singles': list(FIELDS),
        'all_current': list(FIELDS),
        'interaction': {k: list(v) for k, v in INTERACTION_ARMS.items()},
        'loo': {k: list(v) for k, v in LOO_ARMS.items()},
        'baseline_default': {k: BASELINE_DEFAULT[k] for k in BASELINE_DEFAULT},
    }
    return hashlib.sha256(
        json.dumps(spec, sort_keys=True).encode('utf-8')).hexdigest()


def _file_sha(path):
    try:
        with open(path, 'rb') as fp:
            return hashlib.sha256(fp.read()).hexdigest()
    except OSError:
        return None


def tool_revision():
    return _file_sha(os.path.abspath(__file__))


def code_digest():
    """재생 결과를 좌우하는 production 파일. 바뀌면 checkpoint 는 무효다."""
    h = hashlib.sha256()
    for name in ('plan.py', 'runner.py', 'fieldsim.py', 'session.py',
                 'persona.py', 'preflop.py'):
        h.update(name.encode('utf-8'))
        h.update((_file_sha(os.path.join(ROOT, name)) or '-').encode('utf-8'))
    return h.hexdigest()


def fixture_spec(max_events=None):
    return {'entries': ENTRIES, 'hands': HANDS, 'seeds': list(SEEDS),
            'fmts': list(FMTS), 'max_events': max_events}


def events_digest(events, devs):
    """capture 결과가 같은지 확인한다. 전체 입력을 다시 저장하지 않는다."""
    h = hashlib.sha256()
    for i, ev in enumerate(events):
        h.update(('%d|%s|%s\n' % (i, ev['street'],
                                  ','.join(sorted(devs[i])))).encode('utf-8'))
    return h.hexdigest()


# ---------------------------------------------------------------- heartbeat
class Heartbeat(object):
    """30초 이상 무출력 금지. stderr 로만 쓴다 — --json 출력과 섞이지 않는다."""

    def __init__(self, every=10.0, stream=None, enabled=True):
        self.every = float(every)
        self.stream = stream or sys.stderr
        self.enabled = enabled
        self.t0 = time.time()
        self.last = 0.0
        self.label = ''

    def phase(self, label):
        self.label = label
        if not self.enabled:
            return
        self._emit('시작')

    def tick(self, done=None, extra='', force=False):
        if not self.enabled:
            return
        now = time.time()
        if not force and (now - self.last) < self.every:
            return
        self._emit(('%s' % extra) if done is None
                   else ('%d  %s' % (done, extra)))

    def _emit(self, msg):
        self.last = time.time()
        self.stream.write('[%7.1fs] %-22s %s\n'
                          % (self.last - self.t0, self.label, msg))
        self.stream.flush()


# ---------------------------------------------------------------- checkpoint
CKPT_VERSION = 2


class Checkpoint(object):
    """재생 서명만 저장한다. capture 는 결정적이므로 resume 시 다시 돈다.

    저장 내용: tool revision, production code digest, fixture 정의,
    event 수와 event digest, arm 명세 digest, 그리고 (event, effective set)
    별 서명. 하나라도 어긋나면 resume 을 거부한다 — 낡은 서명을 새 코드의
    결과로 섞지 않는다.
    """

    def __init__(self, path, hb=None):
        self.path = path
        self.hb = hb
        self.meta = None
        self.base_sig = {}
        self.sig = {}
        self.dirty = 0
        self.last_save = time.time()

    # --- key 직렬화 ------------------------------------------------
    @staticmethod
    def _k(i, eff):
        return '%d|%s' % (i, ','.join(sorted(eff)))

    @staticmethod
    def _unk(s):
        i, _, rest = s.partition('|')
        return int(i), frozenset(x for x in rest.split(',') if x)

    def load(self, meta):
        """meta 와 완전히 일치할 때만 서명을 되살린다. 반환: (ok, reason)"""
        if not self.path or not os.path.exists(self.path):
            return False, 'checkpoint 없음'
        try:
            with open(self.path, encoding='utf-8') as fp:
                raw = json.load(fp)
        except (OSError, ValueError) as e:
            return False, 'checkpoint 읽기 실패: %s' % e
        if raw.get('version') != CKPT_VERSION:
            return False, 'checkpoint version %r != %d' % (raw.get('version'),
                                                           CKPT_VERSION)
        old = raw.get('meta') or {}
        for k in ('tool_revision', 'code_digest', 'fixture', 'event_count',
                  'events_digest', 'arm_spec_digest'):
            if old.get(k) != meta.get(k):
                return False, '%s 불일치 (checkpoint %r != 현재 %r)' % (
                    k, old.get(k), meta.get(k))
        self.meta = meta
        self.base_sig = {int(k): v for k, v in (raw.get('base_sig') or {}).items()}
        self.sig = {self._unk(k): v for k, v in (raw.get('sig') or {}).items()}
        return True, 'resume: baseline %d, arm 서명 %d' % (len(self.base_sig),
                                                          len(self.sig))

    def bind(self, meta):
        self.meta = meta

    def touch(self, every=30.0):
        self.dirty += 1
        if self.path and (time.time() - self.last_save) >= every:
            self.save()

    def save(self):
        if not self.path:
            return
        tmp = self.path + '.tmp'
        payload = {
            'version': CKPT_VERSION,
            'meta': self.meta,
            'base_sig': {str(k): v for k, v in self.base_sig.items()},
            'sig': {self._k(i, eff): v for (i, eff), v in self.sig.items()},
        }
        with open(tmp, 'w', encoding='utf-8') as fp:
            json.dump(payload, fp, ensure_ascii=False, sort_keys=True)
        os.replace(tmp, self.path)
        self.last_save = time.time()
        self.dirty = 0
        if self.hb is not None:
            self.hb.tick(None, 'checkpoint 저장 (arm 서명 %d)' % len(self.sig),
                         force=True)


# ---------------------------------------------------------------- 재생 엔진
def dev_set(event):
    """이 event 에서 실제로 값이 다른 필드. arm 의 effective 입력을 정한다."""
    return frozenset(f for f in FIELDS
                     if not _same(event['current'][f],
                                  _effective_baseline(event, f)))


class ReplayEngine(object):
    """(event, effective field set) 단위 memoization.

    근거 — arm 이 지정한 필드 중 current 값이 baseline 과 같은 것은
    재생 결과에 영향을 줄 수 없다.
      * 누락 5필드(oop_vs_aggr/oop_legacy_abs/initiative/tilt/bb_chips):
        선택하지 않으면 make_plan 기본값이 쓰인다. BASELINE_DEFAULT 가
        그 기본값과 같음을 _assert_defaults() 로 실행 시 확인한다.
      * snapshot 2필드(opp_est/opp_stack_bb): 선택하지 않으면
        state.get(...) 이고 그것이 곧 _effective_baseline 이다.
    따라서 replay(ev, S) == replay(ev, S ∩ dev(ev)) 이고,
    S ∩ dev(ev) 가 비면 production baseline 재생과 같다.
    """

    def __init__(self, events, hb=None, ckpt=None):
        self.events = events
        self.hb = hb
        self.ckpt = ckpt
        self.devs = [dev_set(ev) for ev in events]
        self.base_sig = {}
        self.sig = {}
        if ckpt is not None:
            self.base_sig.update(ckpt.base_sig)
            self.sig.update(ckpt.sig)
        # checkpoint 에서 되살린 서명 수. 재사용량과 구분한다.
        self.loaded = len(self.base_sig) + len(self.sig)
        self.stats = Counter()
        self.replay_time = 0.0

    # --- baseline 서명 캐시 (한 event 당 한 번) ---------------------
    def baseline_sig(self, i):
        s = self.base_sig.get(i)
        if s is not None:
            self.stats['base_hit'] += 1
            return s
        t0 = time.time()
        st = _replay(self.events[i], ())
        self.replay_time += time.time() - t0
        s = _intent_sig(st, self.events[i]['street'])
        self.base_sig[i] = s
        self.stats['base_replay'] += 1
        if self.ckpt is not None:
            self.ckpt.base_sig[i] = s
            self.ckpt.touch()
        return s

    # --- arm 서명 --------------------------------------------------
    def arm_sig(self, i, selected):
        eff = frozenset(selected) & self.devs[i]
        if not eff:
            # 유효 입력이 하나도 안 바뀐다 → baseline 과 동일하다.
            self.stats['skipped_empty'] += 1
            return self.baseline_sig(i)
        key = (i, eff)
        s = self.sig.get(key)
        if s is not None:
            self.stats['cache_hit'] += 1
            return s
        t0 = time.time()
        st = _replay(self.events[i], tuple(sorted(eff)))
        self.replay_time += time.time() - t0
        s = _intent_sig(st, self.events[i]['street'])
        self.sig[key] = s
        self.stats['arm_replay'] += 1
        if self.ckpt is not None:
            self.ckpt.sig[key] = s
            self.ckpt.touch()
        return s

    # --- 계획된 총량 -----------------------------------------------
    def planned(self):
        """naive(원본) vs 최적화 재생 수를 event 별로 정확히 센다."""
        naive = len(self.events)          # baseline pass
        keys = set()
        for i, dev in enumerate(self.devs):
            for f in FIELDS:              # single-field arm
                if f in dev:              # 원본도 여기서만 재생한다
                    naive += 1
                    keys.add((i, frozenset((f,))))
            for selected in ([FIELDS] + list(INTERACTION_ARMS.values())
                             + list(LOO_ARMS.values())):
                naive += 1
                eff = frozenset(selected) & dev
                if eff:
                    keys.add((i, eff))
        return {'events': len(self.events),
                'naive_replays': naive,
                'optimized_replays': len(self.events) + len(keys),
                'distinct_arm_keys': len(keys)}


def _assert_defaults():
    """BASELINE_DEFAULT 가 make_plan 의 실제 기본값과 같은지 확인한다.

    memoization 의 전제다. 어긋나면 조용히 틀리는 대신 멈춘다.
    """
    sig = inspect.signature(PL.make_plan)
    bad = []
    for f, want in BASELINE_DEFAULT.items():
        p = sig.parameters.get(f)
        if p is None or p.default is inspect.Parameter.empty:
            bad.append('%s: make_plan 에 기본값 없음' % f)
        elif p.default != want or type(p.default) is not type(want):
            bad.append('%s: make_plan 기본값 %r != BASELINE_DEFAULT %r'
                       % (f, p.default, want))
    # production revise_plan 이 이 5개를 실제로 안 넘기는지도 본다.
    src = inspect.getsource(RU.revise_plan)
    for f in ('oop_vs_aggr', 'oop_legacy_abs', 'initiative', 'tilt', 'bb_chips'):
        if (f + '=') in src:
            bad.append('%s: revise_plan 이 이미 넘기고 있다 — baseline 정의 재확인'
                       % f)
    return bad


def analyze_reference(events):
    """최적화 전 원본 구현. 측정 정의의 기준이며 수정하지 않는다."""
    prov = OrderedDict()
    for field in FIELDS:
        diff = 0
        samples = []
        for i, ev in enumerate(events):
            cur = ev['current'][field]
            base = _effective_baseline(ev, field)
            if not _same(cur, base):
                diff += 1
                if len(samples) < 4:
                    samples.append({
                        'event': i,
                        'street': ev['street'],
                        'baseline': _sample_value(base),
                        'current': _sample_value(cur),
                    })
        prov[field] = {
            'different': diff,
            'total': len(events),
            'samples': samples,
        }

    # baseline output은 event마다 한 번만 계산한다.
    base_out = []
    for ev in events:
        base_out.append(_replay(ev, ()))

    impact = OrderedDict()
    for field in FIELDS:
        changed = 0
        kinds = Counter()
        samples = []
        for i, ev in enumerate(events):
            # 값이 동일한 event는 재생할 필요가 없다.
            if _same(ev['current'][field], _effective_baseline(ev, field)):
                continue
            alt = _replay(ev, (field,))
            a = _intent_sig(base_out[i], ev['street'])
            b = _intent_sig(alt, ev['street'])
            dk = _diff_kind(a, b)
            if dk:
                changed += 1
                kinds['+'.join(dk)] += 1
                if len(samples) < 4:
                    samples.append({
                        'event': i,
                        'street': ev['street'],
                        'baseline_context': _sample_value(
                            _effective_baseline(ev, field)),
                        'current_context': _sample_value(ev['current'][field]),
                        'baseline_output': a,
                        'current_output': b,
                        'diff': list(dk),
                    })
        impact[field] = {
            'changed': changed,
            'different_input': prov[field]['different'],
            'diff_kinds': dict(kinds),
            'samples': samples,
        }

    # 전체 7개를 한 번에 current로 넘긴 경우.
    all_changed = 0
    all_kinds = Counter()
    all_samples = []
    for i, ev in enumerate(events):
        alt = _replay(ev, FIELDS)
        a = _intent_sig(base_out[i], ev['street'])
        b = _intent_sig(alt, ev['street'])
        dk = _diff_kind(a, b)
        if dk:
            all_changed += 1
            all_kinds['+'.join(dk)] += 1
            if len(all_samples) < 6:
                all_samples.append({
                    'event': i,
                    'street': ev['street'],
                    'baseline_output': a,
                    'all_current_output': b,
                    'diff': list(dk),
                })

    # interaction attribution. 단독 합보다 all-current가 크면 어떤 조합에서
    # 새 divergence가 생기는지 arm별 event set으로 분해한다.
    arms = OrderedDict([
        ('bb+opp_est', ('bb_chips', 'opp_est')),
        ('bb+opp_stack', ('bb_chips', 'opp_stack_bb')),
        ('opp_est+opp_stack', ('opp_est', 'opp_stack_bb')),
        ('context_core3', ('bb_chips', 'opp_est', 'opp_stack_bb')),
        ('core+initiative', ('bb_chips', 'opp_est', 'initiative')),
        ('core+oop_vs', ('bb_chips', 'opp_est', 'oop_vs_aggr')),
        ('core+oop_legacy', ('bb_chips', 'opp_est', 'oop_legacy_abs')),
        ('core+position', ('bb_chips', 'opp_est', 'oop_vs_aggr',
                           'oop_legacy_abs', 'initiative')),
        ('all7', FIELDS),
    ])
    arm_out = OrderedDict()
    arm_sets = {}
    for name, selected in arms.items():
        changed_idx = []
        kinds = Counter()
        for i, ev in enumerate(events):
            alt = _replay(ev, selected)
            a = _intent_sig(base_out[i], ev['street'])
            b = _intent_sig(alt, ev['street'])
            dk = _diff_kind(a, b)
            if dk:
                changed_idx.append(i)
                kinds['+'.join(dk)] += 1
        arm_sets[name] = set(changed_idx)
        arm_out[name] = {
            'fields': list(selected),
            'changed': len(changed_idx),
            'event_ids': changed_idx,
            'diff_kinds': dict(kinds),
        }

    # leave-one-out from all7. all7에서 한 필드를 빼서 변화 수/사건이 줄면
    # 그 필드는 단독 효과가 0이어도 interaction에는 기여한다.
    loo = OrderedDict()
    allset = arm_sets['all7']
    for field in FIELDS:
        selected = tuple(x for x in FIELDS if x != field)
        changed_idx = []
        kinds = Counter()
        for i, ev in enumerate(events):
            alt = _replay(ev, selected)
            a = _intent_sig(base_out[i], ev['street'])
            b = _intent_sig(alt, ev['street'])
            dk = _diff_kind(a, b)
            if dk:
                changed_idx.append(i)
                kinds['+'.join(dk)] += 1
        aset = set(changed_idx)
        loo[field] = {
            'all_without_changed': len(changed_idx),
            'removed_from_all': len(allset - aset),
            'added_vs_all': len(aset - allset),
            'removed_event_ids': sorted(allset - aset),
            'added_event_ids': sorted(aset - allset),
            'diff_kinds': dict(kinds),
        }

    return {
        'provenance': prov,
        'impact': impact,
        'all_current': {
            'changed': all_changed,
            'total': len(events),
            'diff_kinds': dict(all_kinds),
            'samples': all_samples,
        },
        'interaction_arms': arm_out,
        'leave_one_out': loo,
    }


def analyze(events, hb=None, ckpt=None, perf=None, engine=None):
    """analyze_reference 와 **같은 결과**를 내되 재생 횟수를 줄인다.

    줄이는 방법은 두 가지뿐이고 둘 다 측정 정의를 건드리지 않는다.
      (1) arm 이 지정한 필드 중 실제로 값이 다른 것만 남긴다
          (effective set). 비면 baseline 재생 결과를 그대로 쓴다.
      (2) 같은 (event, effective set) 은 한 번만 재생한다.
          all_current 와 interaction_arms['all7'] 이 같은 것,
          leave-one-out 에서 값이 한 번도 다르지 않은 필드를 빼도
          all7 과 같아지는 것이 여기서 자동으로 합쳐진다.
    arm 목록·필드·baseline 정의는 원본 그대로다.
    """
    hb = hb if hb is not None else Heartbeat(enabled=False)
    eng = engine if engine is not None else ReplayEngine(events, hb=hb, ckpt=ckpt)

    # ---------------- 1. provenance mismatch (재생 없음) -------------
    prov = OrderedDict()
    for field in FIELDS:
        diff = 0
        samples = []
        for i, ev in enumerate(events):
            cur = ev['current'][field]
            base = _effective_baseline(ev, field)
            if not _same(cur, base):
                diff += 1
                if len(samples) < 4:
                    samples.append({
                        'event': i,
                        'street': ev['street'],
                        'baseline': _sample_value(base),
                        'current': _sample_value(cur),
                    })
        prov[field] = {
            'different': diff,
            'total': len(events),
            'samples': samples,
        }

    # ---------------- 2. baseline 서명 (event 당 한 번) ---------------
    hb.phase('baseline')
    for i in range(len(events)):
        eng.baseline_sig(i)
        hb.tick(i + 1, 'baseline 재생 %d/%d' % (i + 1, len(events)))
    hb.tick(len(events), 'baseline 완료 %d' % len(events), force=True)
    if ckpt is not None:
        ckpt.save()

    # ---------------- 3. 단일 필드 반사실 ----------------------------
    hb.phase('single-field')
    impact = OrderedDict()
    for field in FIELDS:
        changed = 0
        kinds = Counter()
        samples = []
        for i, ev in enumerate(events):
            if _same(ev['current'][field], _effective_baseline(ev, field)):
                continue
            a = eng.baseline_sig(i)
            b = eng.arm_sig(i, (field,))
            dk = _diff_kind(a, b)
            if dk:
                changed += 1
                kinds['+'.join(dk)] += 1
                if len(samples) < 4:
                    samples.append({
                        'event': i,
                        'street': ev['street'],
                        'baseline_context': _sample_value(
                            _effective_baseline(ev, field)),
                        'current_context': _sample_value(ev['current'][field]),
                        'baseline_output': a,
                        'current_output': b,
                        'diff': list(dk),
                    })
            hb.tick(eng.stats['arm_replay'], 'single %s %d/%d'
                    % (field, i + 1, len(events)))
        impact[field] = {
            'changed': changed,
            'different_input': prov[field]['different'],
            'diff_kinds': dict(kinds),
            'samples': samples,
        }
    if ckpt is not None:
        ckpt.save()

    # ---------------- 4. interaction arms ---------------------------
    # all_current 는 interaction_arms['all7'] 과 같은 arm 이다. 원본은 두
    # 번 재생했다. 여기서는 한 번 재생하고 양쪽 출력에 모두 쓴다.
    hb.phase('interaction arms')
    arm_out = OrderedDict()
    arm_sets = {}
    for name, selected in INTERACTION_ARMS.items():
        changed_idx = []
        kinds = Counter()
        for i, ev in enumerate(events):
            a = eng.baseline_sig(i)
            b = eng.arm_sig(i, selected)
            dk = _diff_kind(a, b)
            if dk:
                changed_idx.append(i)
                kinds['+'.join(dk)] += 1
            hb.tick(eng.stats['arm_replay'], 'arm %s %d/%d'
                    % (name, i + 1, len(events)))
        arm_sets[name] = set(changed_idx)
        arm_out[name] = {
            'fields': list(selected),
            'changed': len(changed_idx),
            'event_ids': changed_idx,
            'diff_kinds': dict(kinds),
        }
    if ckpt is not None:
        ckpt.save()

    # all seven current together — all7 arm 의 재계산 없는 재구성.
    all_changed = 0
    all_kinds = Counter()
    all_samples = []
    for i, ev in enumerate(events):
        a = eng.baseline_sig(i)
        b = eng.arm_sig(i, FIELDS)
        dk = _diff_kind(a, b)
        if dk:
            all_changed += 1
            all_kinds['+'.join(dk)] += 1
            if len(all_samples) < 6:
                all_samples.append({
                    'event': i,
                    'street': ev['street'],
                    'baseline_output': a,
                    'all_current_output': b,
                    'diff': list(dk),
                })

    # ---------------- 5. leave-one-out ------------------------------
    hb.phase('leave-one-out')
    loo = OrderedDict()
    allset = arm_sets['all7']
    for field in FIELDS:
        selected = LOO_ARMS[field]
        changed_idx = []
        kinds = Counter()
        for i, ev in enumerate(events):
            a = eng.baseline_sig(i)
            b = eng.arm_sig(i, selected)
            dk = _diff_kind(a, b)
            if dk:
                changed_idx.append(i)
                kinds['+'.join(dk)] += 1
            hb.tick(eng.stats['arm_replay'], 'loo -%s %d/%d'
                    % (field, i + 1, len(events)))
        aset = set(changed_idx)
        loo[field] = {
            'all_without_changed': len(changed_idx),
            'removed_from_all': len(allset - aset),
            'added_vs_all': len(aset - allset),
            'removed_event_ids': sorted(allset - aset),
            'added_event_ids': sorted(aset - allset),
            'diff_kinds': dict(kinds),
        }
    if ckpt is not None:
        ckpt.save()

    if perf is not None:
        perf.update(eng.planned())
        perf['actual_baseline_replays'] = eng.stats['base_replay']
        perf['actual_arm_replays'] = eng.stats['arm_replay']
        perf['cache_hits'] = eng.stats['cache_hit']
        perf['baseline_sig_hits'] = eng.stats['base_hit']
        perf['skipped_empty_effective'] = eng.stats['skipped_empty']
        perf['loaded_from_checkpoint'] = eng.loaded
        perf['replay_seconds'] = round(eng.replay_time, 3)

    return {
        'provenance': prov,
        'impact': impact,
        'all_current': {
            'changed': all_changed,
            'total': len(events),
            'diff_kinds': dict(all_kinds),
            'samples': all_samples,
        },
        'interaction_arms': arm_out,
        'leave_one_out': loo,
    }


def human(events, counts, result):
    print('A6 replan provenance characterization')
    print('fixture: entries=%d, hands=%d, seeds=%s, fmts=%s'
          % (ENTRIES, HANDS, ','.join(map(str, SEEDS)), ','.join(FMTS)))
    print()
    print('update_plan=%d  revise_path=%d  board_changed/replan=%d  engine_errors=%d'
          % (counts['update_plan'], counts['revise_path'],
             counts['board_changed'], counts['engine_errors']))
    print()

    print('## 1. provenance mismatch')
    print('  %-18s %10s %10s %8s' % ('field', 'different', 'total', 'rate'))
    for field in FIELDS:
        r = result['provenance'][field]
        rate = 100.0 * r['different'] / max(1, r['total'])
        print('  %-18s %10d %10d %7.1f%%'
              % (field, r['different'], r['total'], rate))
    print()

    print('## 2. one-field current-context counterfactual')
    print('  %-18s %12s %10s %12s' %
          ('field', 'input differs', 'changed', 'changed/diff'))
    for field in FIELDS:
        r = result['impact'][field]
        pct = 100.0 * r['changed'] / max(1, r['different_input'])
        print('  %-18s %12d %10d %11.2f%%  %s'
              % (field, r['different_input'], r['changed'], pct,
                 r['diff_kinds']))
    print()

    a = result['all_current']
    print('## 3. all seven current together')
    print('  changed %d / %d = %.3f%%   %s'
          % (a['changed'], a['total'],
             100.0*a['changed']/max(1, a['total']), a['diff_kinds']))
    print()

    print('## 4. interaction arms')
    for name, r in result['interaction_arms'].items():
        print('  %-20s changed=%3d  events=%s'
              % (name, r['changed'], r['event_ids']))
    print()

    print('## 5. leave-one-out from all7')
    print('  %-18s %12s %12s %10s'
          % ('field', 'without', 'removed', 'added'))
    for field, r in result['leave_one_out'].items():
        print('  %-18s %12d %12d %10d'
              % (field, r['all_without_changed'],
                 r['removed_from_all'], r['added_vs_all']))
        if r['removed_event_ids'] or r['added_event_ids']:
            print('    removed=%s added=%s'
                  % (r['removed_event_ids'], r['added_event_ids']))
    print()

    # 행동이 실제로 바뀐 샘플만 짧게.
    any_sample = False
    for field in FIELDS:
        ss = result['impact'][field]['samples']
        if not ss:
            continue
        any_sample = True
        print('## sample: %s' % field)
        for x in ss:
            print('  event %(event)d %(street)s  %(baseline_context)r -> '
                  '%(current_context)r' % x)
            print('    %(baseline_output)r -> %(current_output)r  diff=%(diff)s' % x)
        print()
    if not any_sample:
        print('행동 변화 샘플 없음')


def _print_estimate(plan, cal, out=sys.stderr):
    red = 100.0 * (plan['naive_replays'] - plan['optimized_replays']) \
        / max(1, plan['naive_replays'])
    out.write('\n## 0. 실행 전 예상량\n')
    out.write('  events                    %8d\n' % plan['events'])
    out.write('  naive replays (원본)       %8d\n' % plan['naive_replays'])
    out.write('  optimized replays         %8d   (-%.1f%%)\n'
              % (plan['optimized_replays'], red))
    out.write('  distinct arm keys         %8d\n' % plan['distinct_arm_keys'])
    if cal:
        out.write('  측정 baseline 재생        %8.4f s/회 (n=%d)\n'
                  % (cal['base_s'], cal['base_n']))
        out.write('  측정 arm 재생             %8.4f s/회 (n=%d)\n'
                  % (cal['arm_s'], cal['arm_n']))
        rem = max(0, plan['optimized_replays'] - cal['base_n'] - cal['arm_n'])
        out.write('  남은 재생                 %8d\n' % rem)
        out.write('  예상 재생 시간            %8.0f s   (원본 기준 %.0f s)\n'
                  % (rem * cal['arm_s'],
                     (plan['naive_replays'] - plan['events']) * cal['arm_s']
                     + plan['events'] * cal['base_s']))
    out.write('\n')
    out.flush()


def _equivalence(n_events, hb):
    """앞 n_events 개로 원본 analyze_reference 와 최적화 analyze 를 대조한다.

    fixture 정의는 그대로 두고 capture 만 앞부분에서 끊는다. events 는
    전체 실행의 prefix 와 같다.
    """
    hb.phase('equiv capture')
    events, counts, errors = _capture_events(hb=hb, max_events=n_events)
    events = events[:n_events]
    print('subset 동치성 시험: events=%d (capture 중 %d 건 수집)'
          % (len(events), counts['board_changed']))
    if errors:
        print('ENGINE ERRORS %d — 중단' % len(errors))
        return 1

    hb.phase('equiv reference')
    t0 = time.time()
    ref = analyze_reference(events)
    t_ref = time.time() - t0

    hb.phase('equiv optimized')
    perf = {}
    t0 = time.time()
    new = analyze(events, hb=hb, perf=perf)
    t_new = time.time() - t0

    a = json.dumps(ref, ensure_ascii=False, sort_keys=True)
    b = json.dumps(new, ensure_ascii=False, sort_keys=True)
    same = (a == b)
    print()
    print('reference  %.1fs' % t_ref)
    print('optimized  %.1fs   (baseline %d + arm %d 재생, cache hit %d)'
          % (t_new, perf['actual_baseline_replays'], perf['actual_arm_replays'],
             perf['cache_hits'] + perf['baseline_sig_hits']))
    print('naive %d -> optimized %d  (-%.1f%%)'
          % (perf['naive_replays'], perf['optimized_replays'],
             100.0 * (perf['naive_replays'] - perf['optimized_replays'])
             / max(1, perf['naive_replays'])))
    print()
    if same:
        print('EXACT EQUIVALENCE: PASS  (결과 dict 완전 일치)')
        return 0
    print('EXACT EQUIVALENCE: FAIL')
    for section in ('provenance', 'impact', 'all_current',
                    'interaction_arms', 'leave_one_out'):
        sa = json.dumps(ref.get(section), ensure_ascii=False, sort_keys=True)
        sb = json.dumps(new.get(section), ensure_ascii=False, sort_keys=True)
        if sa != sb:
            print('  다른 section: %s' % section)
            print('    ref %s' % sa[:400])
            print('    new %s' % sb[:400])
    return 1


def main():
    ap = argparse.ArgumentParser(description='replan current-vs-snapshot provenance')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--estimate-only', action='store_true',
                    help='capture 와 계량만 하고 arm 재생 전에 멈춘다')
    ap.add_argument('--equiv', type=int, metavar='N', default=0,
                    help='앞 N event 로 원본 구현과 결과가 완전히 같은지 대조')
    ap.add_argument('--max-events', type=int, default=None,
                    help='subset 실행. 고정 fixture 결과가 아니다')
    ap.add_argument('--checkpoint', metavar='PATH', default=None,
                    help='재생 서명을 저장/재사용할 파일')
    ap.add_argument('--resume', action='store_true',
                    help='--checkpoint 파일이 현재 코드/fixture/arm 과 완전히 '
                         '일치할 때만 이어서 한다')
    ap.add_argument('--heartbeat', type=float, default=10.0,
                    help='진행 표시 간격(초). 0 이면 끈다')
    a = ap.parse_args()

    hb = Heartbeat(every=a.heartbeat or 10.0, enabled=bool(a.heartbeat))

    bad = _assert_defaults()
    if bad:
        print('BASELINE 정의 전제 위반 — memoization 을 쓸 수 없다:')
        for x in bad:
            print('  ' + x)
        return 2

    if a.equiv:
        return _equivalence(a.equiv, hb)

    if a.max_events is not None:
        sys.stderr.write('*** subset 실행 (max_events=%d). 고정 fixture 결과가 '
                         '아니다. ***\n' % a.max_events)

    hb.phase('capture')
    t_cap = time.time()
    events, counts, errors = _capture_events(hb=hb, max_events=a.max_events)
    if a.max_events is not None:
        events = events[:a.max_events]
    hb.tick(len(events), 'capture 완료 %d events (%.1fs)'
            % (len(events), time.time() - t_cap), force=True)

    ckpt = None
    engine = None
    if a.checkpoint:
        devs = [dev_set(ev) for ev in events]
        meta = {
            'tool_revision': tool_revision(),
            'code_digest': code_digest(),
            'fixture': fixture_spec(a.max_events),
            'event_count': len(events),
            'events_digest': events_digest(events, devs),
            'arm_spec_digest': arm_spec_digest(),
        }
        ckpt = Checkpoint(a.checkpoint, hb=hb)
        if a.resume:
            ok, why = ckpt.load(meta)
            sys.stderr.write('checkpoint: %s\n' % why)
            if not ok and os.path.exists(a.checkpoint):
                sys.stderr.write('checkpoint 를 이어 쓸 수 없다. 파일을 지우거나 '
                                 '--resume 없이 처음부터 실행할 것.\n')
                return 3
        ckpt.bind(meta)
        engine = ReplayEngine(events, hb=hb, ckpt=ckpt)

    if engine is None:
        engine = ReplayEngine(events, hb=hb, ckpt=ckpt)

    plan = engine.planned()

    # calibration — 여기서 도는 재생은 전부 본 작업이고 캐시에 남는다.
    hb.phase('calibration')
    cal = None
    if events:
        kb = min(20, len(events))
        t0 = time.time()
        for i in range(kb):
            engine.baseline_sig(i)
        t_base = time.time() - t0
        ka = min(20, len(events))
        t0 = time.time()
        for i in range(ka):
            engine.arm_sig(i, FIELDS)
        t_arm = time.time() - t0
        cal = {'base_s': t_base / max(1, kb), 'base_n': kb,
               'arm_s': t_arm / max(1, ka), 'arm_n': ka}
    _print_estimate(plan, cal)

    if a.estimate_only:
        if ckpt is not None:
            ckpt.save()
        return 0

    perf = {}
    result = analyze(events, hb=hb, ckpt=ckpt, perf=perf, engine=engine)
    if ckpt is not None:
        ckpt.save()
    hb.tick(None, '완료', force=True)

    payload = {
        'fixture': {
            'entries': ENTRIES,
            'hands': HANDS,
            'seeds': list(SEEDS),
            'fmts': list(FMTS),
        },
        'counts': dict(counts),
        'result': result,
        'perf': perf,
        'engine_error_samples': list(errors[:5]),
    }
    if a.max_events is not None:
        payload['fixture']['max_events'] = a.max_events

    if a.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        human(events, counts, result)
        print()
        print('## perf')
        print('  naive replays      %d' % perf['naive_replays'])
        print('  optimized replays  %d  (-%.1f%%)'
              % (perf['optimized_replays'],
                 100.0 * (perf['naive_replays'] - perf['optimized_replays'])
                 / max(1, perf['naive_replays'])))
        print('  실제 재생          baseline %d + arm %d'
              % (perf['actual_baseline_replays'], perf['actual_arm_replays']))
        print('  cache hit          %d (arm) + %d (baseline 서명)'
              % (perf['cache_hits'], perf['baseline_sig_hits']))
        print('  effective 공집합    %d' % perf['skipped_empty_effective'])
        print('  재생 시간          %.1fs' % perf['replay_seconds'])
        if errors:
            print()
            print('ENGINE ERRORS — 결과 해석 중단')
            for e in errors[:5]:
                print('  ' + str(e))
            return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
