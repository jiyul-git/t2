const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');
const root = path.resolve(__dirname, '../web/app.js');
const source = fs.readFileSync(fs.existsSync(root) ? root : path.join(__dirname, 'app.js'), 'utf8');
const start = source.indexOf('function noteTournamentClock(');
const end = source.indexOf('function paintTournamentClock()', start);
const context = {S: {}, performance: {now: () => 0}, Math, Number};
vm.createContext(context);
vm.runInContext(source.slice(start, end), context);
const note = context.noteTournamentClock;
const values = context.tournamentClockValues;
note({elapsed_seconds: 10, elapsed_started_ms: 0, server_now_ms: 10250,
      clock_running: true, active_clock_running: true, level_remaining_seconds: 20}, 0);
assert.equal(values(0).elapsed, 10);
assert.equal(values(750).elapsed, 11);
assert.equal(values(1750).elapsed, 12);
assert.equal(values(2750).elapsed, 13); // no HTTP response for three seconds
assert.equal(values(2750).levelRemaining, 18);
note({elapsed_seconds: 9, server_now_ms: 9000}, 3000); // stale response cannot rewind
assert.equal(values(3000).elapsed, 13);
note({elapsed_seconds: 3300, elapsed_started_ms: 0, server_now_ms: 3300000,
      clock_running: true, active_clock_running: false, level_remaining_seconds: 12}, 4000);
assert.equal(values(7000).elapsed, 3303);
assert.equal(values(7000).levelRemaining, 12); // active level pauses in a break
note({elapsed_seconds: 8, level_remaining_seconds: 5}, 8000); // legacy virtual clock
assert.equal(values(12000).elapsed, 8);
assert.equal(values(12000).levelRemaining, 5);
note({elapsed_seconds: null, level_remaining_seconds: null}, 12000);
assert.equal(values(13000).elapsed, null);
assert.equal(values(13000).levelRemaining, null);
console.log('PASS: continuous elapsed without HTTP, level pause, stale snapshot, legacy/null clocks');
