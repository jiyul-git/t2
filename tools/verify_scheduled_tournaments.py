#!/usr/bin/env python3
"""Isolated transaction, real-engine, cutoff, recovery and replay checks."""
import copy
import concurrent.futures
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import live2 as L
import scheduled_runtime as SR
import tournament_store as TS

SPEC = [dict(fmt='standard', minute=0, buyin=1000, bot_entries=2,
             late_minutes=10, max_reentries=2)]
START = 36000
TID = 'standard:36000'


class EconomyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = TS.Store(self.tmp.name, 10000, SPEC)
        self.s.ensure_schedule(START - 1)

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, reserve=True):
        if reserve:
            self.s.reserve(TID, now=START - 1)
            self.s.request_enter(TID, now=START - 1)
        r = SR.advance(self.s.event(TID), 0)
        self.assertTrue(self.s.save_state(TID, r['state'], r['revision'], r['assignments'], now=START))
        return self.s.event(TID)['state']

    def bust(self, st, now=START + 10):
        f = L._load_field(st['field'])
        p = f.players[f.hero_pid]
        winner = next(x for x in f.players.values() if x['pid'] != f.hero_pid and x['stack'] > 0)
        winner['stack'] += p['stack']
        p['stack'] = 0
        f._collect_busts()
        f._balance()
        st['field'] = L._dump(f)
        st['background_pending'] = {}
        st['background_seconds'] = TS.active_seconds(now - START)
        self.s.save_state(TID, st, now=now)
        return self.s.event(TID)['state']

    def test_wallet_survives_restart_and_changed_initial_setting(self):
        self.s.reserve(TID, now=START - 1)
        other = TS.Store(self.tmp.name, 999999, SPEC)
        self.assertEqual(other.wallet()['balance'], 9000)
        self.assertEqual(len(other.wallet()['transactions']), 2)

    def test_lobby_reports_recovery_without_mixing_clock_and_stacks(self):
        self.start()
        before = self.s.event(TID)['state']
        rows = self.s.catalog(START + 3720)['tournaments']
        event = next(row for row in rows if row['id'] == TID)
        self.assertEqual(event['progress']['play_seconds'], 0)
        self.assertEqual(event['progress']['target_seconds'], 3420)
        self.assertTrue(event['progress']['recovering'])
        self.assertEqual(event['progress']['simulated_seconds'], 0)
        self.assertEqual(self.s.event(TID)['state'], before)

    def test_finished_lobby_clock_keeps_final_duration(self):
        self.start()
        with self.s._db() as db:
            db.execute('UPDATE tournaments SET finished=1 WHERE id=?', (TID,))
        event = next(row for row in self.s.catalog(START + 3720)['tournaments']
                     if row['id'] == TID)
        self.assertEqual(event['progress']['play_seconds'], 0)

    def test_reservation_preserves_full_stack_until_first_admission(self):
        s = TS.Store(self.tmp.name + '/first', 10000, [dict(SPEC[0], bot_entries=18)])
        s.ensure_schedule(START - 1)
        s.reserve(TID, now=START - 1)
        r = SR.advance(s.event(TID), 60, budget=64, parallel=False)
        self.assertEqual(r['assignments'], {})
        s.save_state(TID, r['state'], r['revision'], r['assignments'], now=START + 60)
        self.assertIsNone(s.event(TID)['entries'][0]['pid'])
        s.set_active(TID)
        s.request_enter(TID, now=START + 60)
        r = SR.advance(s.event(TID), 120, budget=64, parallel=False)
        pid = r['assignments'][1]
        self.assertEqual(r['state']['field']['players'][str(pid)]['stack'],
                         s.event(TID)['rules']['start_stack'])
        self.assertTrue(r['state']['hero_ready'])

    def test_restart_migrates_real_background_without_changing_wallet_or_chips(self):
        st = self.start()
        with self.s._db() as db:
            ev = self.s._event(db, TID)
            ev['rules']['field_backend'] = 'real'
            st['field']['format_rules']['field_backend'] = 'real'
            db.execute('UPDATE tournaments SET rules=?,state=? WHERE id=?',
                       (json.dumps(ev['rules']), json.dumps(st), TID))
        chips = {pid: p['stack'] for pid, p in st['field']['players'].items()}
        wallet = self.s.wallet()
        self.s.prepare_recovery(START + 100)
        ev = self.s.event(TID)
        self.assertEqual(ev['rules']['field_backend'], 'hybrid')
        self.assertEqual(ev['state']['field']['format_rules']['field_backend'], 'hybrid')
        self.assertEqual({pid: p['stack'] for pid, p in ev['state']['field']['players'].items()}, chips)
        self.assertEqual(self.s.wallet(), wallet)

    def test_small_budget_publishes_generated_window(self):
        s = TS.Store(self.tmp.name + '/budget', 10000, [dict(SPEC[0], bot_entries=27)])
        s.ensure_schedule(START - 1)
        r = SR.advance(s.event(TID), 300, budget=1, parallel=False)
        self.assertGreater(r['state']['field']['virtual_play_seconds'], 0)

    def test_future_hand_boundary_survives_break_and_worker_cache(self):
        st = self.start(False)
        # At the 55-minute pause the current hands cannot yet be merged. Their
        # future boundary must remain visible even with worker-only queues.
        st['background_seconds'] = 3290.0
        st['background_pending'] = {tid: [{'end': 3330.0}]
                                    for tid in st['field']['tables']}
        ev = self.s.event(TID)
        ev['state'] = st
        for _ in range(2):
            out = SR.advance(ev, 3300, parallel=False)
            self.assertEqual(out['work'], 0)
            self.assertEqual(out['state']['background_seconds'], 3300)
            self.assertEqual(out['state']['background_resume_at'], 3330)
            self.assertTrue(out['state']['background_pending_key'])
            self.assertEqual(out['state']['background_pending'], {})
            ev['state'] = out['state']

    def test_removed_format_retires_only_settled_personal_results(self):
        self.bust(self.start())
        self.s.uses_default_schedule = True
        with self.s._db() as db:
            ev = self.s._event(db, TID)
            ev['rules']['fmt'] = 'deep'
            db.execute('UPDATE tournaments SET rules=? WHERE id=?', (json.dumps(ev['rules']), TID))
        before = self.s.event(TID)
        wallet = self.s.wallet()
        self.s.prepare_recovery(START + 10000)
        after = self.s.event(TID)
        self.assertTrue(after['rules']['retired'])
        self.assertEqual(after['entries'], before['entries'])
        self.assertEqual(after['state']['field'], before['state']['field'])
        self.assertEqual(self.s.wallet(), wallet)
        self.assertNotIn(TID, {ev['id'] for ev in self.s.jobs(START + 10000)})

    def test_removed_format_does_not_retire_an_unsettled_live_seat(self):
        self.start()
        self.s.uses_default_schedule = True
        with self.s._db() as db:
            ev = self.s._event(db, TID)
            ev['rules']['fmt'] = 'deep'
            db.execute('UPDATE tournaments SET rules=? WHERE id=?', (json.dumps(ev['rules']), TID))
        self.s.prepare_recovery(START + 10000)
        self.assertFalse(self.s.event(TID)['rules'].get('retired'))

    def test_long_history_keeps_upcoming_catalog_and_active_result(self):
        rules = json.dumps(self.s.event(TID)['rules'])
        with self.s._db() as db:
            for i in range(100):
                tid = 'old:%d' % i
                at = START - (200 - i) * 3600
                db.execute('INSERT INTO tournaments(id,starts_at,closes_at,rules,finished) '
                           'VALUES (?,?,?,?,1)', (tid, at, at + 600, rules))
                db.execute('INSERT INTO entries VALUES (?,?,?,?,?,?,?)',
                           (tid, 1, at, 2, 'busted', 3, 0))
        self.s.set_active('old:0')
        catalog = self.s.catalog(now=START - 1)['tournaments']
        self.assertIn(TID, {t['id'] for t in catalog})
        self.assertTrue(next(t for t in catalog if t['id'] == 'old:0')['active'])

    def test_concurrent_first_account_creation_grants_once(self):
        root = self.tmp.name + '/bootstrap'
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            stores = list(pool.map(lambda _: TS.Store(root, 10000, SPEC), range(4)))
        self.assertEqual(stores[0].wallet()['balance'], 10000)
        self.assertEqual(len(stores[0].wallet()['transactions']), 1)

    def test_duplicate_and_concurrent_buyin_charges_once(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            entries = list(pool.map(lambda _: self.s.reserve(TID, now=START - 1), range(20)))
        self.assertEqual({r['entry_no'] for r in entries}, {1})
        self.assertEqual(self.s.wallet()['balance'], 9000)
        self.assertEqual(len(self.s.event(TID)['entries']), 1)

    def test_failed_entry_insert_rolls_back_wallet(self):
        with self.s._db() as db:
            db.execute("CREATE TRIGGER fail_entry BEFORE INSERT ON entries BEGIN SELECT RAISE(ABORT,'crash'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.s.reserve(TID, now=START - 1)
        self.assertEqual(self.s.wallet()['balance'], 10000)
        self.assertEqual(self.s.event(TID)['entries'], [])

    def test_insufficient_balance_has_no_entry_or_debit(self):
        with self.s._db() as db:
            db.execute('UPDATE players SET balance=999')
        with self.assertRaises(TS.TournamentError):
            self.s.reserve(TID, now=START - 1)
        self.assertEqual(self.s.event(TID)['entries'], [])
        self.assertEqual(self.s.wallet()['balance'], 999)

    def test_registration_closes_exactly_at_deadline(self):
        self.start(False)
        with self.assertRaises(TS.TournamentError):
            self.s.reserve(TID, now=START + 600)
        self.assertEqual(self.s.wallet()['balance'], 10000)

    def test_future_cancel_refunds_exactly_once(self):
        self.s.reserve(TID, now=START - 1)
        for _ in range(3):
            self.s.cancel(TID, 1, now=START - .5)
        self.assertEqual(self.s.wallet()['balance'], 10000)
        self.assertEqual(len(self.s.wallet()['transactions']), 3)
        self.s.reserve(TID, now=START - .1)
        self.assertEqual(self.s.wallet()['balance'], 9000)

    def test_cancel_removes_active_waiting_room(self):
        self.s.reserve(TID, now=START - 1)
        self.s.set_active(TID)
        self.s.request_enter(TID, now=START - .9)
        self.s.cancel(TID, 1, now=START - .5)
        self.assertIsNone(self.s.active_id())
        self.assertEqual(self.s.wallet()['balance'], 10000)
        self.assertFalse(self.s.event(TID)['enter_requested'])

    def test_refunded_reservation_does_not_consume_reentry_limit(self):
        ev = self.s.event(TID)
        ev['entries'] = [{'status': 'cancelled', 'entry_no': 1},
                         {'status': 'busted', 'entry_no': 2},
                         {'status': 'busted', 'entry_no': 3}]
        self.assertTrue(TS.can_reenter(ev, now=START + 1))
        ev['entries'].append({'status': 'busted', 'entry_no': 4})
        self.assertFalse(TS.can_reenter(ev, now=START + 1))

    def test_fractional_buyin_configuration_rejected(self):
        with self.assertRaises(ValueError):
            TS.Store(self.tmp.name + '/fraction', 10000, [dict(SPEC[0], buyin=1.5)])

    def test_cancel_at_start_rejected(self):
        self.s.reserve(TID, now=START - 1)
        with self.assertRaises(TS.TournamentError):
            self.s.cancel(TID, 1, now=START)
        self.assertEqual(self.s.wallet()['balance'], 9000)

    def test_late_registration_is_queued_until_real_request_time(self):
        self.start(False)
        for _ in range(3):
            receipt = self.s.reserve(TID, now=START + 90)
        self.assertEqual(receipt['status'], 'waiting')
        self.assertEqual(self.s.wallet()['balance'], 9000)
        out = SR.advance(self.s.event(TID), 60, budget=30, parallel=False)
        self.s.save_state(TID, out['state'], out['revision'], out['assignments'], now=START + 90)
        self.assertEqual(out['assignments'], {})
        self.assertIsNone(self.s.event(TID)['entries'][0]['pid'])
        self.assertEqual(len(out['state']['field']['players']), 2)

    def test_late_registration_without_snapshot_preserves_admission_time_on_restart(self):
        self.s.reserve(TID, now=START + 90)
        restarted = TS.Store(self.tmp.name, 99999, SPEC)
        out = SR.advance(restarted.event(TID), 0, parallel=False)
        self.assertEqual(out['assignments'], {})
        self.assertEqual(len(out['state']['field']['players']), 2)
        self.assertEqual(restarted.event(TID)['entries'][0]['created_at'], START + 90)
        self.assertEqual(restarted.wallet()['balance'], 9000)

    def test_catchup_closing_registration_refunds_unseated_entry_once(self):
        st = self.start(False)
        self.s.reserve(TID, now=START + 90)
        self.s.request_enter(TID, now=START + 90)
        f = L._load_field(st['field'])
        winner, loser = list(f.players.values())
        winner['stack'] += loser['stack']
        loser['stack'] = 0
        f._collect_busts()
        f._balance()
        st.update(field=L._dump(f), background_pending={}, background_seconds=60)
        self.s.save_state(TID, st, now=START + 90)
        out = SR.advance(self.s.event(TID), 90, parallel=False)
        for _ in range(3):
            self.s.save_state(TID, out['state'], now=START + 90)
        ev = self.s.event(TID)
        self.assertEqual(ev['entries'][0]['status'], 'cancelled')
        self.assertTrue(ev['finished'])
        self.assertFalse(ev['enter_requested'])
        self.assertEqual(len(ev['state']['field']['players']), 2)
        self.assertEqual(self.s.wallet()['balance'], 10000)
        self.assertEqual(sum(t['kind'] == 'refund' for t in self.s.wallet()['transactions']), 1)

    def test_pending_admission_and_paid_fields_are_prioritized_fairly(self):
        def job(tid, entries, enter=False):
            return ({'id': tid, 'entries': entries, 'enter_requested': enter}, 100)
        empty = job('unowned', [])
        paid1 = job('paid1', [{'status': 'playing'}])
        paid2 = job('paid2', [{'status': 'playing'}])
        pending = job('waiting', [{'status': 'waiting'}])
        active = job('selected', [{'status': 'playing'}], True)
        jobs = [empty, paid1, paid2, pending, active]
        self.assertEqual(SR.choose_job(jobs, 0, 'selected'), active)
        self.assertEqual(SR.choose_job(jobs[:-1], 0, None), pending)
        self.assertEqual(SR.choose_job(jobs[:3], 0, None), paid1)
        self.assertEqual(SR.choose_job(jobs[:3], 1, None), paid2)

    def test_waiting_refund_and_state_rollback_together_on_failure(self):
        st = self.start(False)
        self.s.reserve(TID, now=START + 90)
        st['refunded_entries'] = [1]
        with self.s._db() as db:
            db.execute("CREATE TRIGGER fail_refund BEFORE UPDATE ON entries WHEN NEW.status='cancelled' "
                       "BEGIN SELECT RAISE(ABORT,'crash'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.s.save_state(TID, st, now=START + 90)
        self.assertEqual(self.s.wallet()['balance'], 9000)
        self.assertEqual(self.s.event(TID)['entries'][0]['status'], 'waiting')
        self.assertNotIn('refunded_entries', self.s.event(TID)['state'])

    def test_refund_after_wall_clock_cutoff_rebuilds_unpaid_prize_pool(self):
        st = self.start(False)
        self.s.reserve(TID, now=START + 599)
        self.s.save_state(TID, st, now=START + 610)
        self.assertEqual(sum(json.loads(self.s.event(TID)['prize_table'])), 3000)
        f = L._load_field(st['field'])
        winner, loser = list(f.players.values())
        winner['stack'] += loser['stack']
        loser['stack'] = 0
        f._collect_busts()
        f._balance()
        st.update(field=L._dump(f), background_pending={}, background_seconds=120)
        self.s.save_state(TID, st, now=START + 610)
        out = SR.advance(self.s.event(TID), 610, parallel=False)
        self.s.save_state(TID, out['state'], out['revision'], out['assignments'], now=START + 610)
        self.assertEqual(self.s.wallet()['balance'], 10000)
        self.assertEqual(sum(json.loads(self.s.event(TID)['prize_table'])), 2000)
        self.assertEqual(self.s.event(TID)['state']['prize_pool'], 2000)

    def test_expired_unowned_events_do_not_crowd_scheduler_after_restart(self):
        past = 'standard:%d' % (START - 3600)
        self.s.ensure_schedule(START - 3601)
        jobs = self.s.jobs(START + 1)
        self.assertNotIn(past, {j['id'] for j in jobs})
        self.s.reserve(past, now=START - 3601)
        self.assertIn(past, {j['id'] for j in self.s.jobs(START + 1)})

    def test_late_entry_joins_existing_stacks_and_next_hand(self):
        self.start(False)
        out = SR.advance(self.s.event(TID), 30, budget=20)
        self.s.save_state(TID, out['state'], out['revision'], out['assignments'], now=START + 30)
        old = copy.deepcopy(self.s.event(TID)['state']['field'])
        self.s.reserve(TID, now=START + 30)
        self.s.request_enter(TID, now=START + 30)
        out = SR.advance(self.s.event(TID), 120, budget=30)
        self.s.save_state(TID, out['state'], out['revision'], out['assignments'], now=START + 120)
        ev = self.s.event(TID)
        self.assertEqual(ev['entries'][0]['status'], 'playing')
        self.assertTrue(ev['state']['hero_ready'])
        self.assertGreaterEqual(ev['state']['field']['hand_no'], old['hand_no'])
        self.assertEqual(len(ev['state']['field']['players']), 3)
        self.assertEqual(sum(p['stack'] for p in ev['state']['field']['players'].values()), 90000)
        self.assertEqual(self.s.wallet()['balance'], 9000)

    def test_capacity_includes_reentries_without_debit(self):
        with self.s._db() as db:
            rules = json.loads(
                db.execute('SELECT rules FROM tournaments WHERE id=?', (TID,)).fetchone()[0])
            rules['max_entries'] = 3
            db.execute('UPDATE tournaments SET rules=? WHERE id=?', (json.dumps(rules), TID))
        self.bust(self.start())
        with self.assertRaises(TS.TournamentError):
            self.s.reserve(TID, True, 1, now=START + 10)
        self.assertEqual(self.s.wallet()['balance'], 9000)

    def test_offscreen_hero_checks_or_folds_and_chips_conserved(self):
        st = self.start()
        before = sum(p['stack'] for p in st['field']['players'].values())
        f = L._load_field(st['field'])
        tb = f.hero_table()
        hero_seat = tb.seat_of(f.hero_pid)
        res = f._play_table(tb, seed=819, return_result=True)
        actions = [row[2] for row in res['full_log'] if row[1] == hero_seat]
        self.assertTrue(actions)
        self.assertTrue(set(actions) <= {'fold', 'check'})
        self.assertEqual(sum(p['stack'] for p in f.players.values()), before)

    def test_vclock_worker_recovers_after_hero_seat_removed(self):
        st = self.bust(self.start())
        owner, others, _ = L._round_owners(st['field'])
        self.assertEqual(owner, -1)
        self.assertEqual(set(others), {int(tid) for tid in st['field']['tables']})
        out = L.compute_vclock_ahead(st['field'], 60, 3300)
        self.assertTrue(out['tables'])
        self.assertTrue(any(row['events'] for row in out['tables'].values()))

    def test_reentry_preserves_field_and_cannot_recharge_on_replay(self):
        st = self.bust(self.start())
        self.assertEqual(self.s.event(TID)['entries'][0]['status'], 'busted')
        original = copy.deepcopy(st['field'])
        r = self.s.reserve(TID, True, 1, now=START + 10)
        r2 = self.s.reserve(TID, True, 1, now=START + 11)
        self.assertEqual((r['entry_no'], r2['entry_no']), (2, 2))
        self.assertEqual(self.s.wallet()['balance'], 8000)
        self.assertEqual(self.s.event(TID)['state']['field'], original)
        out = SR.advance(self.s.event(TID), 100, budget=20)
        self.s.save_state(TID, out['state'], out['revision'], out['assignments'], now=START + 100)
        ev = self.s.event(TID)
        self.assertIsNotNone(ev['entries'][1]['pid'])
        self.assertNotEqual(ev['entries'][0]['pid'], ev['entries'][1]['pid'])
        self.assertEqual(ev['state']['field']['entries'], 4)
        self.assertEqual(sum(p['stack'] for p in ev['state']['field']['players'].values()),
                         4 * ev['rules']['start_stack'])

    def test_reentry_while_alive_rejected(self):
        self.start()
        with self.assertRaises(TS.TournamentError):
            self.s.reserve(TID, True, 1, now=START + 1)

    def test_refunded_active_reentry_can_release_admission(self):
        st = self.bust(self.start())
        self.s.set_active(TID)
        self.s.reserve(TID, True, 1, now=START + 10)
        st['refunded_entries'] = [2]
        self.s.save_state(TID, st, now=START + 11)
        self.assertEqual(self.s.active_id(), TID)
        self.assertEqual(self.s.event(TID)['entries'][-1]['status'], 'cancelled')
        wallet = self.s.wallet()
        field = copy.deepcopy(self.s.event(TID)['state']['field'])
        self.s.request_enter(TID, False, now=START + 12)
        ev = self.s.event(TID)
        self.assertFalse(ev['enter_requested'])
        self.assertFalse(ev['state']['hero_ready'])
        self.assertEqual(ev['state']['field'], field)
        self.assertEqual(self.s.wallet(), wallet)
        with self.assertRaises(TS.TournamentError):
            self.s.request_enter(TID, True, now=START + 12)
        self.assertEqual(self.s.wallet()['balance'], 9000)

    def test_stale_worker_does_not_overwrite_paid_reservation(self):
        ev = self.s.event(TID)
        result = SR.advance(ev, 0)
        self.s.reserve(TID, now=START - 1)
        self.assertFalse(self.s.save_state(TID, result['state'], result['revision'], now=START))
        self.assertIsNone(self.s.event(TID)['state'])
        self.assertEqual(self.s.wallet()['balance'], 9000)

    def test_prize_and_finish_state_committed_once(self):
        st = self.start()
        f = L._load_field(st['field'])
        hero = f.players[f.hero_pid]
        for p in f.players.values():
            if p is not hero:
                hero['stack'] += p['stack']
                p['stack'] = 0
        f._collect_busts()
        st['field'] = L._dump(f)
        for _ in range(5):
            self.s.save_state(TID, st, now=START + 600)
        self.assertEqual(self.s.wallet()['balance'], 12000)
        self.assertEqual(self.s.event(TID)['entries'][0]['payout'], 3000)
        self.assertEqual(sum(x['kind'] == 'prize' for x in self.s.wallet()['transactions']), 1)
        self.assertEqual(TS.Store(self.tmp.name, 0, SPEC).wallet()['balance'], 12000)

    def test_payout_rounding_conserves_pool(self):
        for pool in (1, 7, 1001, 3000001):
            for n in (1, 3, 15, 150):
                for flat in (0, .35, 1):
                    table = TS.prizes(pool, n, flat)
                    self.assertEqual(sum(table), pool)
                    self.assertTrue(all(isinstance(x, int) and x >= 0 for x in table))
                    self.assertEqual(table, sorted(table, reverse=True))

    def test_schedule_rules_are_frozen_across_code_updates(self):
        ev = self.s.event(TID)
        changed = [dict(SPEC[0], buyin=9000, late_minutes=5)]
        TS.Store(self.tmp.name, 10000, changed).ensure_schedule(START - 1)
        current = self.s.event(TID)
        self.assertEqual(current['rules'], ev['rules'])
        self.assertEqual(current['closes_at'], ev['closes_at'])

    def test_all_scheduled_formats_use_nine_seats_and_cap_1000(self):
        defaults = TS.Store(self.tmp.name + '/defaults')
        rows = defaults.catalog(START)['tournaments']
        self.assertTrue(rows)
        self.assertTrue(all(r['seats'] == 9 and r['max_entries'] == 1000 for r in rows))

    def test_default_schedule_has_one_event_every_hour_in_seoul(self):
        # 2026-10-07: 매시 정각, 테스트 기간엔 딥 없이 turbo/standard 교대, 17:00 KST 는 standard.
        defaults = TS.Store(self.tmp.name + '/spaced')
        midnight = 54000  # 1970-01-02 00:00 Asia/Seoul
        rows = defaults.catalog(midnight - 1)['tournaments']
        # 일정은 지금부터 24시간 앞까지 만든다 — 자정 1초 전 기준이면 23:00 슬롯은 아직 없다.
        starts = [r['starts_at'] for r in rows if midnight <= r['starts_at'] < midnight + 23 * 3600]
        self.assertEqual(starts, list(range(midnight, midnight + 23 * 3600, 3600)))
        fmts = [r['fmt'] for r in rows if r['starts_at'] in starts]
        self.assertEqual(fmts, (['turbo', 'standard'] * 12)[:23])
        self.assertEqual(fmts[17], 'standard')

    def test_default_hourly_update_retires_empty_two_hour_slots(self):
        root = self.tmp.name + '/two_hour'
        midnight = 54000
        old = [dict(spec, minute=0, interval_hours=6, hour_offset=o)
               for spec, o in zip(TS.LEGACY_SCHEDULE, (3, 5, 1))]
        TS.Store(root, 10000, old).ensure_schedule(midnight - 1)
        rows = TS.Store(root, 10000).catalog(midnight - 1)['tournaments']
        self.assertTrue(all(r.get('interval_hours') == 2 and r['fmt'] != 'deep' for r in rows
                            if r['starts_at'] >= midnight))

    def test_default_update_retires_empty_legacy_slots_and_preserves_receipts(self):
        root = self.tmp.name + '/legacy'
        midnight = 54000
        legacy = TS.Store(root, 10000, TS.LEGACY_SCHEDULE)
        legacy.ensure_schedule(midnight - 1)
        paid = 'turbo:%d' % (midnight + 1200)
        cancelled = 'deep:%d' % (midnight + 2400)
        obsolete = 'standard:%d' % (midnight + 7200)   # 홀수 UTC 시 = 이제 터보 자리
        result = SR.advance(legacy.event(obsolete), 0, parallel=False)
        legacy.reserve(paid, now=midnight - 1)
        legacy.reserve(cancelled, now=midnight - 1)
        legacy.cancel(cancelled, 1, now=midnight - 1)
        previous = legacy.event(paid)
        wallet = legacy.wallet()
        updated = TS.Store(root, 999999)
        updated.ensure_schedule(midnight - 1)
        self.assertEqual(updated.wallet(), wallet)
        self.assertEqual(updated.event(paid), previous)
        self.assertEqual(updated.event(cancelled)['entries'][0]['status'], 'cancelled')
        with self.assertRaises(TS.TournamentError):
            updated.event(obsolete)
        self.assertFalse(updated.save_state(obsolete, result['state'], result['revision']))

    def test_explicit_personal_schedule_keeps_hourly_slots_on_update(self):
        root = Path(self.tmp.name) / 'custom'
        root.mkdir()
        (root / 'schedule.json').write_text(json.dumps(TS.LEGACY_SCHEDULE))
        custom = TS.Store(root)
        custom.ensure_schedule(53999)
        self.assertIsNotNone(custom.event('turbo:55200'))
        self.assertEqual([r['starts_at'] for r in custom.catalog(53999)['tournaments']
                          if 54000 <= r['starts_at'] < 54000 + 23 * 3600],
                         list(range(54000, 54000 + 23 * 3600, 1200)))

    def test_invalid_schedule_interval_and_offset_are_rejected(self):
        for options in ({'interval_hours': 0}, {'interval_hours': True},
                        {'interval_hours': 1.5}, {'interval_hours': 25},
                        {'interval_hours': 6, 'hour_offset': 6}, {'hour_offset': -1},
                        {'hour_offset': False}):
            with self.assertRaises(ValueError):
                TS.Store(self.tmp.name + '/invalid', schedule=[dict(SPEC[0], **options)])

    def test_break_and_level_clock_is_independent_of_refresh(self):
        for elapsed, expected in ((0, 0), (3299, 3299), (3300, 3300),
                                  (3599, 3300), (3600, 3300), (3900, 3600), (7200, 6600)):
            self.assertEqual(TS.active_seconds(elapsed), expected)

    def test_parallel_and_serial_offscreen_have_identical_field(self):
        spec = [dict(SPEC[0], bot_entries=18)]
        s = TS.Store(self.tmp.name + '/parallel', 10000, spec)
        s.ensure_schedule(START - 1)
        ev = s.event(TID)
        serial = SR.advance(ev, 90, budget=24, parallel=False)
        parallel = SR.advance(ev, 90, budget=24, parallel=True)
        self.assertEqual(serial['state']['field'], parallel['state']['field'])
        self.assertEqual(serial['state']['background_seconds'], parallel['state']['background_seconds'])

    def test_1000_entry_initialization_keeps_nine_seats_and_total_chips(self):
        spec = [dict(SPEC[0], bot_entries=999)]
        s = TS.Store(self.tmp.name + '/large', 10000, spec)
        s.ensure_schedule(START - 1)
        s.reserve(TID, now=START - 1)
        s.request_enter(TID, now=START - 1)
        st = SR.advance(s.event(TID), 0)['state']
        self.assertEqual(len(st['field']['players']), 1000)
        self.assertEqual(len(st['field']['tables']), 112)
        self.assertEqual(sum(p['stack'] for p in st['field']['players'].values()), 30000000)
        self.assertTrue(all(len(tb['seats']) == 9 and len(tb['pids']) in (8, 9)
                            for tb in st['field']['tables'].values()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
