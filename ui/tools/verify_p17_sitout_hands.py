#!/usr/bin/env python3
"""Actual paid registration -> automatic sitout hands -> visible hand history.

Isolated store only. No production data or real wallet is touched.
"""
import os
import pathlib
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ['T2_BOT_LOG'] = '0'
os.environ['T2_TABLE_WORKERS'] = '1'
os.environ['T2_TIMING_V1'] = 'off'

import tournament_store as TS
import scheduled_runtime as SR
import live2 as L

def main():
    with tempfile.TemporaryDirectory(prefix='p17_sitout_') as td:
        store = TS.Store(td, initial_chips=20000, schedule=[dict(
            fmt='standard', minute=0, buyin=1000, bot_entries=3,
            late_minutes=60, max_reentries=1)])
        now = time.time()
        store.ensure_schedule(now)
        event = min((t for t in store.catalog(now)['tournaments']
                     if t['starts_at'] > now), key=lambda x:x['starts_at'])
        tid = event['id']
        start = event['starts_at']
        receipt = store.reserve(tid, now=start-10)
        assert receipt['status'] == 'reserved'
        assert not store.event(tid)['enter_requested'], 'No browser join requested'
        assert store.wallet()['balance'] == 19000, 'buy-in committed once'
        first = SR.advance(store.event(tid), 0.0, budget=4, parallel=False)
        assert first['assignments'] == {1: first['state']['field']['hero_pid']}
        assert store.save_state(tid, first['state'], expected_revision=first['revision'],
                                assignments=first['assignments'], now=start)
        ready = store.event(tid)
        pid = ready['entries'][0]['pid']
        assert pid is not None and ready['entries'][0]['status'] == 'playing'
        assert pid in ready['state']['field']['sitout_pids']
        assert not ready['enter_requested'], 'Paid seat must not force UI join'
        table = ready['state']['field']['players'][str(pid)]['table']
        before = ready['state']['field']['players'][str(pid)]['stack']
        assert ready['state']['field']['tables'][str(table)]['hands'] == 0
        # Advance actual completed hands, not a synthetic blind/ante decrement.
        history = []
        for target in (35, 90, 160, 250):
            tick = SR.advance(store.event(tid), target, budget=16, parallel=False)
            assert store.save_state(tid, tick['state'], expected_revision=tick['revision'],
                                    assignments=tick['assignments'], now=start+target)
            ready = store.event(tid)
            history = ready['state'].get('sitout_hand_history') or []
            if len(history) >= 2:
                break
        assert len(history) >= 2, ('No real hands completed', len(history))
        assert len({(h['hero_pid'], h['table_id'], h['table_hand_no'])
                    for h in history}) == len(history), 'Duplicate hand on retry'
        assert all(h['hero_pid'] == pid and h['hero_seat'] in
                   [int(s) for s in h['seat_pid']] for h in history)
        assert all(len(h['hero_hole']) == 2 and h['kind'] == 'sitout'
                   for h in history), 'Actual dealt hole cards missing'
        assert all('hole' not in h and 'reads' not in h and
                   'decision_cache' not in h for h in history), 'Private other hole/AI leakage'
        assert all(h['stack_before'] is not None and
                   h['stack_after'] >= 0 for h in history)
        assert all(h['table_hand_no'] >= 1 and h.get('log') is not None
                   and h['hash'] for h in history), 'Actual hand trace missing'
        first_hand = history[0]
        assert first_hand['stack_before'] == before
        assert all(h['ended_seconds'] <= target + 1e-6 for h in history)
        assert history == sorted(history, key=lambda h:h['ended_seconds'])
        # The on-table counter is genuine, independent of total field-hand events.
        assert max(h['table_hand_no'] for h in history) <= max(
            t['hands'] for t in ready['state']['field']['tables'].values())
        # No new wallet charge occurred while posted blinds/antes eroded stack.
        assert store.wallet()['balance'] == 19000
        print('PASS: registered without login -> real sitout hands (%d), '
              'own hole/public logs, actual stack settlement, stable hand numbers, '
              'buy-in once' % len(history))


if __name__ == '__main__':
    main()
