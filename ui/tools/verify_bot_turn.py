#!/usr/bin/env python3
"""봇 차례 시작 알림(bot_turn): 순서·시계 값 일치·결과 불변 검증.

사용자 요청: HERO 액션이 끝나면 시계(링)와 봇 판단 계산이 동시에 시작해야 한다.
세션(session.py)이 봇 판단을 계산하기 *전에* {'kind': 'bot_turn'} 을 내보내고, 서버가 시계 값을
붙여 즉시 보낸다. 이 검사는 임시 실행 폴더에서 실제 엔진(live2.step)을 돌려 다음을 확인한다.

  1. 모든 bot_action 바로 앞에 같은 좌석의 bot_turn 이 있다(시계 기본 초·결정 직전 뱅크가 같다).
  2. 그 사이에 판단 계산이 끝난 표시(_timing_decide)가 bot_turn 뒤에 온다 = 판단 전에 보냈다.
  3. _BotSchedule.stamp 가 bot_turn 과 bot_action 에 같은 clock_started/base/bank 를 주고,
     bot_turn 은 커서를 움직이지 않으며 예정표(bot_schedule)에 들어가지 않는다.
  4. 같은 시드의 핸드를 bot_turn 을 끄고/켜고 돌려 전체 행동 기록·결정 기록·시계 기록이 똑같다
     (화면 알림만 추가됐을 뿐 전략·난수·결과에 영향이 없다).
"""
import ast
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = (3, 7, 12)
HERO_DECISIONS = 12


def worker(mode, seeds):
    """임시 실행 폴더(cwd)에서 실행. mode 'on' = 알림 켬, 'off' = 알림을 끈 같은 엔진."""
    sys.path.insert(0, os.getcwd())
    os.environ['T2_LIVE_STATE'] = os.path.join(os.getcwd(), 'verify_bot_turn_state.json')
    import time
    import live2 as L
    import session as SE
    if mode == 'off':
        SE.HandRun._emit_bot_turn = lambda self, street, seat: None
    log = []
    _orig_decide = SE.HandRun._timing_decide

    def _decide(self, seat, *a, **k):
        r = _orig_decide(self, seat, *a, **k)
        if self.on_bot_action is not None:
            log.append({'kind': 'decided', 'seat': seat})
        return r
    SE.HandRun._timing_decide = _decide
    out = {}
    for seed in seeds:
        for p in (L.ST, L.ST + '.bak'):
            if os.path.exists(p):
                os.remove(p)
        log.clear()
        L.new_game(entries=90, seed=seed)
        r = L.step(on_bot_action=log.append)
        decisions, n = [], 0
        while n < HERO_DECISIONS:
            raw = r.get('raw') or {}
            if r.get('done'):
                r = L.step(on_bot_action=log.append)
                continue
            if 'tocall' not in raw or raw.get('error'):
                break
            act = ('check' if raw['tocall'] <= 0 else
                   'call' if n % 3 == 0 else 'fold')
            r = L.step(act, 0, on_bot_action=log.append)
            n += 1
        st = L.load()
        events = [dict(e) for e in log]
        out[str(seed)] = {
            'events': events,
            'game': [(e['kind'], e.get('seat'), e.get('street'), e.get('action'), e.get('amount'))
                     for e in events if e['kind'] in ('bot_action', 'street')],
            'actions': st.get('actions'),
            'decisions': st.get('decisions'),
            'hand_seed': st.get('hand_seed'),
            'banks': (st.get('field') or {}).get('time_banks'),
            'hand_no': st.get('hand_no') or (st.get('field') or {}).get('hand_no'),
        }
    print('RESULT' + json.dumps(out, sort_keys=True, default=str))


def run_worker(td, mode):
    env = dict(os.environ, T2_TIMING_V1='enforce', T2_TELEMETRY='0', T2_UI_DEFER='0',
               T2_SCHEDULE_ENABLED='0')
    env.pop('T2_TIMING_TEST_BASE', None)
    env.pop('T2_TIMING_TEST_BANK', None)
    p = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve()), '--worker', mode,
                        ','.join(map(str, SEEDS))], cwd=td, env=env, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-2000:]
    line = [x for x in p.stdout.splitlines() if x.startswith('RESULT')][-1]
    return json.loads(line[len('RESULT'):])


def load_schedule_class():
    """ui_server.py 를 import 하지 않고(서버가 뜬다) _BotSchedule 만 꺼내 쓴다."""
    tree = ast.parse((ROOT / 'ui/server/ui_server.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_BotSchedule')
    ns = {'STREET_GAP_SECONDS': 2.0}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), 'x', 'exec'), ns)
    return ns['_BotSchedule']


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        return worker(sys.argv[2], [int(x) for x in sys.argv[3].split(',')])
    Sched = load_schedule_class()
    with tempfile.TemporaryDirectory(prefix='t2_bot_turn_', ignore_cleanup_errors=True) as td:
        subprocess.run([sys.executable, str(ROOT / 'ui/tools/setup_run_dir.py'), td],
                       check=True, stdout=subprocess.DEVNULL)
        on = run_worker(td, 'on')
        off = run_worker(td, 'off')

    n_turn = n_action = 0
    for seed, d in on.items():
        ev = d['events']
        # 1·2: 순서 = bot_turn(seat) → decided(seat) → bot_action(seat)
        i = 0
        while i < len(ev):
            e = ev[i]
            if e['kind'] == 'bot_turn':
                n_turn += 1
                assert i + 2 < len(ev), (seed, i)
                dec, act = ev[i + 1], ev[i + 2]
                assert dec['kind'] == 'decided' and dec['seat'] == e['seat'], (seed, ev[i:i + 3])
                assert act['kind'] == 'bot_action' and act['seat'] == e['seat'], (seed, ev[i:i + 3])
                assert act['street'] == e['street'], (seed, e, act)
                assert e['timing']['base'] == act['timing']['base'], (e, act)
                assert e['timing']['bank_before'] == act['timing']['bank_before'], (e, act)
                n_action += 1
                i += 3
                continue
            assert e['kind'] != 'bot_action', ('행동 앞에 bot_turn 이 없다', seed, ev[max(0, i - 2):i + 1])
            assert e['kind'] != 'decided', ('bot_turn 없이 판단', seed, ev[max(0, i - 2):i + 1])
            i += 1
        # 3: 예정표 도장
        sched = Sched(1000.0)
        for e in ev:
            if e['kind'] == 'decided':
                continue
            before = sched.cursor
            n_before = len(sched.events)
            e = dict(e)
            sched.stamp(e)
            if e['kind'] == 'bot_turn':
                assert sched.cursor == before and len(sched.events) == n_before, e
                turn = e
            elif e['kind'] == 'bot_action' and e.get('timing'):
                for k in ('clock_started_ms', 'base_deadline_ms', 'bank_deadline_ms'):
                    assert e[k] == turn[k], (k, turn, e)
                assert e['act_at_ms'] >= turn['clock_started_ms'], (turn, e)
    assert n_turn >= 30 and n_turn == n_action, (n_turn, n_action)
    print('PASS: every bot_action is preceded by bot_turn -> decided -> action (%d pairs, seeds %s)'
          % (n_turn, ','.join(on)))
    print('PASS: bot_turn and bot_action get identical clock_started/base/bank; cursor and schedule untouched')

    # 4: 알림을 끈 엔진과 결과 비교(알림 이벤트만 다르다)
    for seed in on:
        assert not any(e['kind'] == 'bot_turn' for e in off[seed]['events']), 'off 모드에서 알림이 나왔다'
        for k in ('game', 'actions', 'decisions', 'hand_seed', 'banks', 'hand_no'):
            assert on[seed][k] == off[seed][k], (seed, k)
        strip = lambda evs: [e for e in evs if e['kind'] in ('bot_action', 'street')]
        assert strip(on[seed]['events']) == strip(off[seed]['events']), seed
    n_games = sum(len(d['game']) for d in on.values())
    print('PASS: with/without bot_turn the hand actions, saved decisions, banks and bot events are identical '
          '(%d seeds, %d events)' % (len(on), n_games))


if __name__ == '__main__':
    main()
