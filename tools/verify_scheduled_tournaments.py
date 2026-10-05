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

    def test_late_registration_requires_real_progress(self):
        self.start(False)
        with self.assertRaises(TS.TournamentError) as err:
            self.s.reserve(TID, now=START + 30)
        self.assertEqual(err.exception.code, 'synchronizing')
        self.assertEqual(self.s.wallet()['balance'], 10000)

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
        st = SR.advance(s.event(TID), 0)['state']
        self.assertEqual(len(st['field']['players']), 1000)
        self.assertEqual(len(st['field']['tables']), 112)
        self.assertEqual(sum(p['stack'] for p in st['field']['players'].values()), 30000000)
        self.assertTrue(all(len(tb['seats']) == 9 and len(tb['pids']) in (8, 9)
                            for tb in st['field']['tables'].values()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
