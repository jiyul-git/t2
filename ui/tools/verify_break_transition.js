'use strict';
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const source = fs.readFileSync(require('path').join(__dirname, '../web/app.js'), 'utf8');
function between(a,b) {const i=source.indexOf(a), j=source.indexOf(b,i); assert(i>=0&&j>i); return source.slice(i,j);}
async function main() {
  let shown = 0, resumed = 0;
  const ctx = {S: {epoch: 1, historyHandComplete: false}, renderBreak: () => shown++};
  vm.createContext(ctx);
  vm.runInContext(between('function updateBreakFromReady(', 'function renderBreak('),ctx);
  ctx.updateBreakFromReady({break_remaining: 276});
  assert.equal(shown,0, 'do not cover the last hand mid-replay');
  ctx.S.historyHandComplete=true;
  ctx.updateBreakFromReady({break_remaining: 276});
  assert.equal(shown,1, 'periodic ready poll opens the break sheet');
  const timers=[];
  Object.assign(ctx, {epochAlive: e=>e===ctx.S.epoch, setTimeout: fn=>{timers.push(fn);return 1;},
    readReady: async()=>({break_remaining: 5}), call: ()=>resumed++});
  vm.runInContext(between('function resumeAfterBreak(', '// Both transports'),ctx);
  ctx.resumeAfterBreak({action:null}, 'next');
  await timers.shift()();
  assert.equal(resumed,0);
  ctx.readReady=async()=>({break_remaining:0,working:false});
  await timers.shift()();
  assert.equal(resumed,1);
  assert.equal(timers.length,0);

  let waiting=0;
  Object.assign(ctx,{req:async()=>({status:409,json:{code:'break_active',break_remaining:276}}),
    setBusy: ()=>{}, toast: ()=>{throw Error('normal break must not show an error toast');},
    apply: ()=>{throw Error('must not replay the old result');},
    resumeAfterBreak: ()=>waiting++});
  vm.runInContext(between('async function call(', '/* 재생이 도는 중이면'),ctx);
  await ctx.call('/api/step',{action:null,token:69},'next');
  assert.equal(waiting,1);
  console.log('PASS: break sheet after visible result, boundary race without error toast, one automatic resume');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
