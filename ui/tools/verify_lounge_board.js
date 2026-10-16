'use strict';
// docs/LOUNGE_SCENE_DESIGN.md 9
const assert = require('assert');
const path = require('path');
const B = require(path.join(__dirname, '../web/lounge/board.js'));
let checks = 0;
const ok = (c, m) => { checks++; assert(c, m); };
const eq = (a, b, m) => { checks++; assert.deepStrictEqual(a, b, m); };

const kst = (d, hh, mm) => Date.UTC(2026, 9, d, hh - 9, mm) / 1000;     // October 2026, KST wall clock
const NOW = kst(16, 20, 40);                                           // 20:40 KST
const t = (id, key, starts, status, extra = {}) => Object.assign({ id, key, starts_at: starts, status, registration_open: false }, extra);

// Independent FNV-1a check against known vectors.
eq(B.fnv1a(''), 0x811c9dc5, 'fnv1a empty'); eq(B.fnv1a('a'), 0xe40c292c, 'fnv1a a'); eq(B.fnv1a('foobar'), 0xbf9cf968, 'fnv1a foobar');

// Status mapping.
const base = t('x', 'standard', NOW + 600, 'scheduled', { registration_open: true });
eq(B.statusFor(base, NOW), 'BOARDING', 'scheduled, open, 10 min away');
eq(B.statusFor(t('x', 'standard', NOW + 1800, 'scheduled', { registration_open: true }), NOW), 'BOARDING', 'exactly 30 min');
eq(B.statusFor(t('x', 'standard', NOW + 1801, 'scheduled', { registration_open: true }), NOW), 'ON TIME', '30 min + 1 s');
eq(B.statusFor(t('x', 'standard', NOW + 600, 'scheduled', { registration_open: false }), NOW), 'ON TIME', 'scheduled but registration closed');
eq(B.statusFor(t('x', 'standard', NOW - 60, 'late_registration', { registration_open: true }), NOW), 'LAST CALL', 'late registration');
eq(B.statusFor(t('x', 'standard', NOW - 3600, 'closed'), NOW), 'DEPARTED', 'closed');

// Real rows: order, destination mapping, time in KST, flight number, mine flag.
const catalog = [
  t('t-c', 'deep', kst(17, 9, 5), 'scheduled'),
  t('t-a', 'turbo', kst(16, 21, 0), 'scheduled', { registration_open: true, my_entry: { status: 'reserved', entry_no: 1 } }),
  t('t-fin', 'standard', kst(16, 10, 0), 'finished'),
  t('t-ret', 'standard', kst(16, 11, 0), 'retired'),
  t('t-b', 'standard', kst(16, 19, 0), 'late_registration', { registration_open: true, my_entry: { status: 'cancelled' } }),
  t('t-old', 'hyper', kst(16, 15, 0), 'closed'),
  t('t-z', 'weird', kst(18, 0, 30), 'scheduled'),
  t('t-bad', 'standard', undefined, 'scheduled'),
  null,
];
const nowMs = NOW * 1000;
const rows = B.boardRows(catalog, NOW, nowMs);
eq(rows.length, 5, 'always five rows');
eq(rows.map(r => r.time), ['15:00', '19:00', '21:00', '09:05', '00:30'], 'sorted by start, KST HH:MM');
eq(rows.map(r => r.dest), ['SINGAPORE', 'SEOUL', 'TOKYO', 'NEW YORK', 'T2 CITY'], 'destinations by format');
eq(rows.map(r => r.status), ['DEPARTED', 'LAST CALL', 'BOARDING', 'ON TIME', 'ON TIME'], 'statuses');
eq(rows.map(r => r.mine), [false, false, true, false, false], 'cancelled entry is not mine');
ok(rows.every(r => !r.virtual), 'all real');
eq(rows[2].flight, 'T2 ' + (B.fnv1a('t-a') % 900 + 100), 'flight number is derived from the id');
ok(rows.every(r => /^T2 [1-9]\d\d$/.test(r.flight)), 'flight format');
eq(B.boardRows(catalog, NOW, nowMs), rows, 'same input, same rows');

// More than five real tournaments: the five earliest unfinished ones.
{
  const many = []; for (let i = 0; i < 9; i++) many.push(t('m' + i, 'standard', kst(16, 22, 0) + i * 3600, 'scheduled'));
  const r = B.boardRows(many.reverse(), NOW, nowMs);
  eq(r.map(x => x.time), ['22:00', '23:00', '00:00', '01:00', '02:00'], 'earliest five');
}

// Filling: fewer than five real tournaments.
{
  const two = [t('a', 'standard', kst(16, 21, 0), 'scheduled'), t('b', 'turbo', kst(16, 22, 0), 'scheduled')];
  const r = B.boardRows(two, NOW, nowMs);
  eq(r.slice(0, 2).map(x => x.virtual), [false, false], 'real first');
  eq(r.slice(2).map(x => x.virtual), [true, true, true], 'virtual after');
  eq(r.slice(2).map(x => x.time), ['22:25', '22:50', '23:15'], '25-minute steps from the last real row, rounded up to 5');
  ok(r.slice(2).every(x => x.status === 'ON TIME' && !x.mine && /^TT [1-9]\d\d$/.test(x.flight)), 'virtual rows');
  ok(r.slice(2).every(x => B.FAKE_CITIES.includes(x.dest)), 'virtual destinations');
  eq(new Set(r.map(x => x.dest)).size, 5, 'no repeated destination');
  // Rounding up: last real row at 22:03 -> 22:28 -> 22:30.
  const odd = B.boardRows([t('a', 'standard', kst(16, 22, 3), 'scheduled')], NOW, nowMs);
  eq(odd[1].time, '22:30', 'rounded up to a multiple of 5');
  // Past midnight.
  const late = B.boardRows([t('a', 'standard', kst(16, 23, 50), 'scheduled')], NOW, nowMs);
  eq(late.slice(1).map(x => x.time), ['00:15', '00:40', '01:05', '01:30'], 'wraps past midnight');
}

// Nothing real: starts from the current time and stays stable for the day, changes the next day.
{
  const e1 = B.boardRows([], NOW, nowMs);
  eq(e1.map(x => x.time), ['21:05', '21:30', '21:55', '22:20', '22:45'], 'from the current time (20:40)');
  ok(e1.every(x => x.virtual), 'all virtual');
  const sameDayLater = B.boardRows([], NOW + 3 * 3600, nowMs + 3 * 3600 * 1000);
  eq(sameDayLater.map(x => x.flight + x.dest), e1.map(x => x.flight + x.dest), 'flights and cities fixed for the day');
  const nextDay = B.boardRows([], NOW + 86400, nowMs + 86400 * 1000);
  ok(nextDay.map(x => x.flight + x.dest).join() !== e1.map(x => x.flight + x.dest).join(), 'a new day gets new flights');
  // The Korean day changes at 00:00 KST (15:00 UTC), not at UTC midnight.
  const before = B.boardRows([], kst(16, 23, 59), kst(16, 23, 59) * 1000);
  const after = B.boardRows([], kst(17, 0, 1), kst(17, 0, 1) * 1000);
  ok(before.map(x => x.flight).join() !== after.map(x => x.flight).join(), 'KST midnight rollover');
}

// Bad input.
eq(B.boardRows(undefined, NaN, nowMs).length, 5, 'undefined catalog');
eq(B.boardRows('nope', undefined, nowMs).length, 5, 'non-array catalog');
ok(B.boardRows(catalog, undefined, nowMs).length === 5, 'missing server time falls back to the client clock');

// Draw constants used by the renderer.
ok(Math.abs(B.COLUMN_RATIOS.reduce((a, b) => a + b, 0) - 1) < 1e-9, 'column ratios sum to 1');
eq(Object.keys(B.STATUS_COLORS).sort(), ['BOARDING', 'DEPARTED', 'LAST CALL', 'ON TIME', 'time'], 'status color keys');

console.log(`verify_lounge_board OK (${checks} checks)`);
