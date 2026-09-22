#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F-9: 두 번째 불법 액션이 session generator 밖으로 ValueError 를 던지는가.

  python3 tools/f9_invalid_retry.py

네 층으로 나눠 본다.
  A  direct HandRun        같은 generator 를 유지하며 send
  B  tourney submit        같은 run 을 계속 쓴다
  C  live2.step            호출마다 HandRun 을 재구성하고 valid action 만 replay
  D  cli / UI              live2 wrapper 인지 코드로 확인

시나리오 셋을 같은 고정 seed 에서 돌린다.
  CONTROL                 legal
  INVALID-LEGAL           invalid -> legal
  INVALID-INVALID-LEGAL   invalid -> invalid -> legal

`HandRun.send` 는 StopIteration 만 잡는다(session.py:386-388). ValueError 는
그대로 올라온다. 문제는 **그 뒤 그 generator 를 다시 쓸 수 있는가** 이고,
추측하지 않고 실제로 send 를 다시 해서 확인한다.

읽기 전용. production 무수정.
"""
from __future__ import print_function

import hashlib
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import tourney as TOURNEY

SEED = 20260922
ILLEGAL = ('raise', 1)          # 최소 레이즈 미달


def rnd_state(run):
    """현재 라운드의 상태 지문. invalid 요청이 오염시켰는지 본다."""
    h = getattr(run, 'h', None)
    snap = {}
    for name in ('_rnd', 'rnd', 'r2'):
        r = getattr(run, name, None)
        if r is not None and hasattr(r, 'log'):
            snap[name] = {'log': list(r.log), 'current': r.current,
                          'min_raise': r.min_raise,
                          'stacks': dict(r.stacks),
                          'contrib': dict(r.contrib)}
    if not snap and h is not None:
        snap['stacks'] = dict(getattr(h, 'stacks', {}) or {})
    return hashlib.sha256(
        json.dumps(snap, sort_keys=True, default=str).encode()).hexdigest()[:12]


def legal_for(raw):
    tc = (raw or {}).get('tocall', 0) or 0
    return ('call', 0) if tc > 0 else ('check', 0)


def probe_generator(label, make, n_invalid):
    """A/B 공통. make() -> (driver, first_raw, send_fn, state_fn)"""
    out = {'label': label, 'n_invalid': n_invalid, 'steps': []}
    try:
        send, raw, state = make()
    except Exception as e:
        out['setup_error'] = '%s: %s' % (type(e).__name__, e)
        return out
    out['state_before'] = state()
    for i in range(n_invalid):
        try:
            raw = send(*ILLEGAL)
            out['steps'].append(
                {'n': i + 1, 'kind': 'invalid', 'escaped': False,
                 'error_frame': bool(isinstance(raw, dict) and raw.get('error')),
                 'state': state()})
        except Exception as e:
            out['steps'].append(
                {'n': i + 1, 'kind': 'invalid', 'escaped': True,
                 'exc': '%s: %s' % (type(e).__name__, str(e)[:60]),
                 'state': state()})
            raw = None
            break
    # 복구 시도 — 예외 뒤에도 실제로 send 해 본다
    try:
        act = legal_for(raw) if isinstance(raw, dict) else ('call', 0)
        raw2 = send(*act)
        out['recover'] = {
            'ok': True,
            'done': bool(isinstance(raw2, dict) and raw2.get('done')),
            'result_none': (isinstance(raw2, dict)
                            and raw2.get('done')
                            and raw2.get('result') is None),
            'stage': (raw2 or {}).get('stage') if isinstance(raw2, dict) else None,
            'error_frame': bool(isinstance(raw2, dict) and raw2.get('error'))}
    except Exception as e:
        out['recover'] = {'ok': False,
                          'exc': '%s: %s' % (type(e).__name__, str(e)[:60])}
    out['state_after'] = state()
    out['state_unchanged_by_invalid'] = (out['state_before'] == out['state_after']
                                         if not out.get('recover', {}).get('ok')
                                         else None)
    return out


# ---------------------------------------------------------------- A / B
def make_tourney(postflop=False):
    t = TOURNEY.Tournament(entries=40, start_stack=30000, hero_seat=7,
                           seed=SEED, hands_per_level=200)
    raw = t.next_hand()
    if postflop:
        # 합법 액션으로 플랍까지 간다
        for _ in range(60):
            if not isinstance(raw, dict) or raw.get('done'):
                break
            if raw.get('stage') in ('flop', 'turn', 'river'):
                break
            raw = t.submit(*legal_for(raw))
    return (lambda a, amt=0: t.submit(a, amt)), raw, (lambda: rnd_state(t.run))


def make_direct(postflop=False):
    """같은 generator 를 직접 쓴다. tourney 가 run 을 그대로 노출하므로
    동일 객체지만, submit 래퍼를 거치지 않고 run.send 를 직접 부른다."""
    t = TOURNEY.Tournament(entries=40, start_stack=30000, hero_seat=7,
                           seed=SEED, hands_per_level=200)
    raw = t.next_hand()
    run = t.run
    if postflop:
        for _ in range(60):
            if not isinstance(raw, dict) or raw.get('done'):
                break
            if raw.get('stage') in ('flop', 'turn', 'river'):
                break
            raw = run.send(*legal_for(raw))
    return (lambda a, amt=0: run.send(a, amt)), raw, (lambda: rnd_state(run))


# ---------------------------------------------------------------- C
def probe_live2(n_invalid):
    tmp = tempfile.mkdtemp(prefix='t2f9_')
    os.environ['T2_LIVE_STATE'] = os.path.join(tmp, 'live2_state.json')
    for m in [k for k in list(sys.modules) if k in ('live2',)]:
        del sys.modules[m]
    import live2 as L
    out = {'label': 'C live2.step', 'n_invalid': n_invalid, 'steps': []}

    def snap():
        st = L.load()
        return {'actions': len(st.get('actions') or []),
                'decisions': len(st.get('decisions') or []),
                'hand_seed': st.get('hand_seed'),
                'hash': hashlib.sha256(
                    json.dumps(st, sort_keys=True, default=str).encode()
                ).hexdigest()[:12]}
    try:
        st = L.new_game(entries=40, start_stack=30000, seed=SEED)
        L.save(st)
        L.step()
        out['state_before'] = snap()
        last = None
        for i in range(n_invalid):
            try:
                r = L.step(*ILLEGAL)
                txt = json.dumps(r, ensure_ascii=False, default=str)
                out['steps'].append(
                    {'n': i + 1, 'escaped': False,
                     'error_frame': ('미달' in txt or '불가' in txt
                                     or 'error' in txt.lower()),
                     'state': snap()})
                last = r
            except Exception as e:
                out['steps'].append(
                    {'n': i + 1, 'escaped': True,
                     'exc': '%s: %s' % (type(e).__name__, str(e)[:60]),
                     'state': snap()})
                break
        try:
            raw = (last or {}).get('raw') if isinstance(last, dict) else None
            act = legal_for(raw) if isinstance(raw, dict) else ('call', 0)
            L.step(*act)
            out['recover'] = {'ok': True}
        except Exception as e:
            out['recover'] = {'ok': False,
                              'exc': '%s: %s' % (type(e).__name__, str(e)[:60])}
        out['state_after'] = snap()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        os.environ.pop('T2_LIVE_STATE', None)
        for m in [k for k in list(sys.modules) if k in ('live2',)]:
            del sys.modules[m]
    return out


def show(r):
    print('  %-24s invalid %d' % (r['label'], r['n_invalid']))
    if r.get('setup_error'):
        print('     setup 실패 %s' % r['setup_error'])
        return
    for s in r['steps']:
        if s['escaped']:
            print('     %d차 invalid  **ValueError 탈출**  %s' % (s['n'], s['exc']))
        else:
            print('     %d차 invalid  error frame %s' % (s['n'], s['error_frame']))
    rec = r.get('recover') or {}
    if not rec.get('ok'):
        print('     복구 legal   예외 %s' % rec.get('exc', ''))
    elif rec.get('done'):
        print('     복구 legal   예외 없음이지만 **done=True 로 즉시 종료**'
              '  (result=None %s, stage %r) — generator 가 죽어 StopIteration 이'
              ' done 으로 둔갑' % (rec.get('result_none'), rec.get('stage')))
    else:
        print('     복구 legal   정상 진행 (stage %r)' % rec.get('stage'))
    if 'state_before' in r:
        same = r['state_before'] == r['state_after']
        print('     상태 지문    before %s  after %s  %s'
              % (r['state_before'], r['state_after'],
                 '동일' if same else '변화'))


def main():
    print('F-9  두 번째 불법 액션의 경계  (seed %d, 불법 요청 %r)'
          % (SEED, ILLEGAL))
    print()
    print('A. direct HandRun (같은 generator)')
    for n in (0, 1, 2):
        show(probe_generator('A preflop', lambda: make_direct(False), n))
    for n in (1, 2):
        show(probe_generator('A postflop', lambda: make_direct(True), n))
    print()
    print('B. tourney.submit (같은 run)')
    for n in (1, 2):
        show(probe_generator('B preflop', lambda: make_tourney(False), n))
    for n in (1, 2):
        show(probe_generator('B postflop', lambda: make_tourney(True), n))
    print()
    print('C. live2.step (호출마다 HandRun 재구성)')
    for n in (1, 2):
        show(probe_live2(n))
    print()
    print('D. cli / UI 코드 경로')
    for f, pat in (('cli.py', 'live2'), ('ui/server/ui_server.py', 'live2')):
        p = os.path.join(ROOT, f)
        if not os.path.exists(p):
            print('  %-28s 없음' % f)
            continue
        src = open(p, encoding='utf-8').read()
        print('  %-28s live2 import %s / HandRun 직접 보유 %s / step 호출 %d회'
              % (f, pat in src, 'HandRun(' in src, src.count('.step(')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
