const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');
const source = fs.readFileSync(process.argv[2] || path.join(__dirname,'..','web','app.js'), 'utf8');
const between = (a, b) => source.slice(source.indexOf(a), source.indexOf(b, source.indexOf(a)));
let now = 1000, frames = [], effects = [], tasks = [];
const sandbox = {
  S: {timers: [], sched: {}, streetSchedule: {}},
  BOARD_AT: {preflop:0, flop:3, turn:4, river:5},
  serverNow: () => now,
  setTimeout: (fn, delay) => {tasks.push({fn, at:now+delay}); return tasks.length;},
  renderSeats: v => frames.push(JSON.parse(JSON.stringify(v))),
  renderChips: () => {}, renderBoard: () => {}, renderPot: () => {}, renderHero: () => {},
  finalFrame: v => effects.push(['final',v.hand_no]),
  bubbleAt: (seat,e) => effects.push(['bubble',seat,e.action]),
  markFold: seat => effects.push(['fold',seat]),
  schedWait: (e,retry) => {
    const t = sandbox.S.sched[e.street+'|'+e.seat+'|'+e.action+'|'+Number(e.amount||0)];
    if (t && t.act_at_ms > now+20) {sandbox.setTimeout(retry,t.act_at_ms-now); return true;}
    return false;
  },
  schedPace: () => 0, paceMs: () => 1500, terminalFold: () => false,
  STREET: {}, $: () => ({innerHTML:''}),
};
vm.createContext(sandbox);
vm.runInContext(
  between('const schedKeys =', '// 예정 시각 전이면') +
  between('function seekActionTail(', '/* 재접속:') +
  between('function fullActionLog(', 'function actualLastStreet(') +
  between('function actionIdentity(', 'function playDecisionTail(') +
  between('function applyEntry(', 'function heroRequestEntry(') +
  between('function playDecisionTail(', 'function playSequence('), sandbox);
const opening = {type:'decision', hand_no:61, hero_seat:1, stage:'preflop', board:[],
  pot_center:200, seats:[{seat:1,stack:9800,bet:200,in_hand:true},
  {seat:2,stack:9800,bet:200,in_hand:true},{seat:3,stack:10000,bet:0,in_hand:true}],log:[]};
const log = [
  {street:'preflop',seat:3,action:'fold',amount:0},
  {street:'preflop',seat:2,action:'check',amount:0},
  {street:'flop',seat:2,action:'bet',amount:500},
  {street:'turn',seat:2,action:'bet',amount:900}];
const view = {...opening,stage:'turn',board:['Js','6h','Tc','3h'],prior_log:log.slice(0,3),log:log.slice(3)};
log.forEach((e,i) => sandbox.S.sched[e.street+'|'+e.seat+'|'+e.action+'|'+e.amount]={...e,act_at_ms:[500,600,1500,2500][i]});
sandbox.S.streetSchedule={flop:1200,turn:2200};
sandbox.playDecisionTail(opening,view,now);
assert.strictEqual(frames[0].stage,'preflop');
assert.strictEqual(frames[0].board.length,0);
assert.strictEqual(frames[0].seats[2].in_hand,false);
assert.strictEqual(frames[0].seats[1].stack,9800);
assert.deepStrictEqual(effects,[]); // No replay of the elapsed fold/check.
while(tasks.length){tasks.sort((a,b)=>a.at-b.at);const t=tasks.shift();now=t.at;t.fn();}
assert.deepStrictEqual(effects,[['bubble',2,'bet'],['bubble',2,'bet'],['final',61]]);
assert.strictEqual(now,2500); // Absolute event times, no restarted pacing.
assert.strictEqual(frames.at(-1).board.length,4);
assert.strictEqual(frames.at(-1).seats[1].stack,8400);
// Fully elapsed snapshot: one immediate frame, no bubbles or waiting.
now=3000;frames=[];effects=[];tasks=[];
sandbox.playDecisionTail(opening,view,now);
assert.strictEqual(frames[0].stage,'turn');
assert.strictEqual(frames[0].board.length,4);
assert.deepStrictEqual(effects,[['final',61]]);
assert.strictEqual(tasks.length,0);
console.log('resume timeline: PASS (elapsed actions, pending streets, stacks, absolute timing)');
