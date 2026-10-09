'use strict';
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const source=fs.readFileSync(require('path').join(__dirname,'../web/app.js'),'utf8');
function between(a,b) {const i=source.indexOf(a),j=source.indexOf(b,i);assert(i>=0&&j>i);return source.slice(i,j);}
let opened=0;
const handlers={}, sheet={classList:{add(){}},addEventListener:(name,fn)=>{handlers[name]=fn;}};
const ctx={openRankDrawer:fromMenu=>{assert.equal(fromMenu,true);opened++;}};
vm.createContext(ctx);
vm.runInContext(between('function bindMenuRankSwipe(', 'function showHandDetail('),ctx);
ctx.bindMenuRankSwipe(sheet);
const start=()=>handlers.pointerdown({pointerType:'touch',pointerId:1,clientX:250,clientY:100});
start();handlers.pointerup({pointerId:1,clientX:100,clientY:110});assert.equal(opened,1);
start();handlers.pointerup({pointerId:1,clientX:100,clientY:300});assert.equal(opened,1);
start();handlers.pointercancel();handlers.pointerup({pointerId:1,clientX:100,clientY:100});assert.equal(opened,1);
start();handlers.pointerup({pointerId:1,clientX:350,clientY:100});assert.equal(opened,1);
handlers.keydown({key:'ArrowLeft',preventDefault(){}});assert.equal(opened,2);
const htmlCtx={fmt:String,esc:String,pct:v=>v+'%',displayHandNo:t=>t.hand_no};
vm.createContext(htmlCtx);
vm.runInContext(between('function tournamentInfoHTML(', 'function renderRankDrawer('),htmlCtx);
const html=htmlCtx.tournamentInfoHTML({format:'터보',hand_no:69,entries:45,remaining:12,
  itm:7,level:11,sb:1500,bb:3000,ante:3000,players_to_jump:5,next_rank:7,next_prize_pct:5.863,
  next_jump_pct:5.863,money_jumps:[]});
assert(!/내 칩순위|내 스택|칩리더|>평균</.test(html));
assert.equal((html.match(/5명/g)||[]).length,1);
assert(!source.includes('id="mRanks"'));
assert(source.includes('(fromMenu ? dx >= 70 : dx <= -70)'));
console.log('PASS: left menu swipe, vertical scroll/cancel exclusion, keyboard access, deduplicated info');
