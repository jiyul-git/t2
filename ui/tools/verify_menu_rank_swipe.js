'use strict';
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const source=fs.readFileSync(require('path').join(__dirname,'../web/app.js'),'utf8');
function between(a,b) {const i=source.indexOf(a),j=source.indexOf(b,i);assert(i>=0&&j>i);return source.slice(i,j);}
const classes=new Set();
const drawer={style:{},classList:{add:x=>classes.add(x),remove:x=>classes.delete(x),
  toggle:(x,on)=>on?classes.add(x):classes.delete(x)},getBoundingClientRect:()=>({width:300})};
const scrim={hidden:true,style:{}};
let now=0, opened=0, closed=0;
const ctx={S:{rankOpen:false,tournament:{}}, performance:{now:()=>now},
  $:s=>s==='#rankDrawer'?drawer:scrim, setTimeout:()=>1, renderRankDrawer:()=>{},
  openRankDrawer:fromMenu=>{assert.equal(fromMenu,true);ctx.S.rankOpen=true;classes.add('open');opened++;},
  closeRankDrawer:()=>{ctx.S.rankOpen=false;classes.delete('open');closed++;}};
vm.createContext(ctx);
vm.runInContext(between('function bindMenuRankSwipe(', 'function showHandDetail('),ctx);
function host() {
  const handlers={};
  return {handlers,classList:{add(){}},addEventListener:(name,fn)=>handlers[name]=fn,
    setPointerCapture(){},releasePointerCapture(id){handlers.lostpointercapture({pointerId:id});}};
}
const sheet=host();ctx.bindMenuRankSwipe(sheet);
function event(x,y=100){return {pointerType:'touch',pointerId:1,clientX:x,clientY:y};}
function start(){sheet.handlers.pointerdown(event(100));}
start();now+=500;sheet.handlers.pointermove(event(200));
assert.equal(drawer.style.transform,'translateX(-206px)', '100px finger move = 100px drawer move');
assert.equal(opened,0,'drawer is not opened until release');
assert(classes.has('dragging') && !scrim.hidden);
now+=500;sheet.handlers.pointermove(event(250));assert.equal(drawer.style.transform,'translateX(-156px)');
sheet.handlers.pointerup(event(250));assert.equal(opened,1);
assert.equal(drawer.style.transform,'');assert(!classes.has('dragging'));
const closer=host();ctx.bindRankDrag(closer,false,()=>ctx.S.rankOpen);
closer.handlers.pointerdown(event(250));now+=500;closer.handlers.pointermove(event(100));
assert.equal(drawer.style.transform,'translateX(-150px)');assert.equal(closed,0);
closer.handlers.pointerup(event(100));assert.equal(closed,1);
// Short slow drag snaps back; fast flick commits; cancellation never commits.
start();now+=500;sheet.handlers.pointermove(event(130));sheet.handlers.pointerup(event(130));assert.equal(opened,1);
start();now+=20;sheet.handlers.pointermove(event(130));sheet.handlers.pointerup(event(130));assert.equal(opened,2);
ctx.S.rankOpen=false;classes.delete('open');
start();now+=500;sheet.handlers.pointermove(event(250));sheet.handlers.pointercancel(event(250));assert.equal(opened,2);
start();now+=100;sheet.handlers.pointermove(event(110,200));sheet.handlers.pointerup(event(250,200));assert.equal(opened,2);
start();now+=100;sheet.handlers.pointermove(event(20));sheet.handlers.pointerup(event(20));assert.equal(opened,2);
sheet.handlers.keydown({key:'ArrowRight',preventDefault(){}});assert.equal(opened,3);
const htmlCtx={fmt:String,esc:String,pct:v=>v+'%',displayHandNo:t=>t.hand_no};
vm.createContext(htmlCtx);
vm.runInContext(between('function tournamentInfoHTML(', 'function renderRankDrawer('),htmlCtx);
const html=htmlCtx.tournamentInfoHTML({format:'터보',hand_no:69,entries:45,remaining:12,
  itm:7,level:11,sb:1500,bb:3000,ante:3000,players_to_jump:5,next_rank:7,next_prize_pct:5.863,
  next_jump_pct:5.863,money_jumps:[]});
assert(!/내 칩순위|내 스택|칩리더|>평균</.test(html));
assert.equal((html.match(/5명/g)||[]).length,1);
assert(!source.includes('id="mRanks"'));
assert(!source.includes('menuSwipeHint'));
assert(!source.includes('왼쪽으로 밀어'));
console.log('PASS: finger-following rightward menu drag, settle/cancel/velocity, reverse close, deduplicated info');
