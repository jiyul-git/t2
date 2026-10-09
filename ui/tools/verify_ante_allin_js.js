'use strict';
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const source = fs.readFileSync(require('path').join(__dirname, '../web/app.js'), 'utf8');
const match = source.match(/^function frameView\(v, bets, folded\) \{[\s\S]*?^\}/m);
assert(match);
const ctx = {}; vm.createContext(ctx); vm.runInContext(match[0], ctx);
function seat(stack, bet, ante, bets, folded={}) {
  return ctx.frameView({seats:[{seat:1,stack,bet,ante}],pot_center:ante}, {1:bets}, folded).seats[0];
}
assert.equal(seat(0,0,166,0).allin, true, 'ante-only all-in needs its badge');
assert.equal(seat(0,1000,0,0).allin, false, 'future shove must not show early');
assert.equal(seat(0,1000,0,1000).allin, true);
assert.equal(seat(0,0,166,0,{1:true}).allin, false);
assert.equal(seat(0,0,0,0).allin, false, 'empty seat is not an all-in');
console.log('PASS: ante all-in and replay timing');
