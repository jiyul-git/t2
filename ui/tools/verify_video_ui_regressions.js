'use strict';
// Regression for 2026-10-09 HAND 89 live-screen review.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const path = require('path');
const ui = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '../web/style.css'), 'utf8');
function between(a,b) {
  const i = ui.indexOf(a), j = ui.indexOf(b, i);
  assert(i >= 0 && j > i, a);
  return ui.slice(i,j);
}
const ctx = {}; vm.createContext(ctx);
vm.runInContext(between('function mergePots(', 'function awardLabelFor('),ctx);
assert.equal(ctx.potAwards({pots:[{amount:2800,eligible:[2,8,9],winners:[2]}],
  winners:[2]})['2'][0].label,'승리');
assert.equal(ctx.potAwards({pots:[],winners:[3]})['3'][0].label,'승리');
const multi = ctx.potAwards({pots:[
  {amount:1000,eligible:[2,3,4],winners:[2]},
  {amount:500,eligible:[2,3],winners:[3]}]});
assert.equal(multi['2'][0].label,'MAIN');
assert.equal(multi['3'][0].label,'SIDE 1');

assert(css.includes('#seats .pod.bubble-front { z-index: 12; }'));
let cls = '', bubble = null;
const pod = {classList:{add:x=>{cls=x}},appendChild:x=>{bubble=x}};
const dom = {querySelector:q=>q.includes('data-slot="2"')?pod:null,
  createElement:()=>({className:'',textContent:''})};
const c2 = {document:dom,actionText:()=> '체크'};
vm.createContext(c2);
vm.runInContext(between('function bubbleAt(', '/* ---------------- 봇 액션 순차'), c2);
c2.bubbleAt(2, {action:'check'});
assert.equal(cls, 'bubble-front');
assert.equal(bubble.textContent,'체크');

assert(ui.includes('const BOT_ACTION_FEEDBACK_MS = 550;'));
assert(ui.includes('}, e.act_at_ms ? BOT_ACTION_FEEDBACK_MS'));
assert(ui.includes('봇 판단 계산 중…'));
console.log('PASS: normal/fold/side-pot labels, bubble stacking, scheduled action visibility and non-fabricated compute status');
