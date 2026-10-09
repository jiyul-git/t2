/* Exercise the real stream caller with a proxy that never releases headers. */
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const path = require('path');
const source = fs.readFileSync(process.argv[2] || path.join(__dirname, '../web/app.js'), 'utf8');
const extract = (a, b) => source.slice(source.indexOf(a), source.indexOf(b, source.indexOf(a)));
const realTimeout = setTimeout;
async function run(blocked) {
  let posts = 0, polls = 0, applied = [], frames = [], aborted = false;
  const view = {type:'decision', hand_no:87, hero_seat:1, stage:'river',
    seats:[{seat:1,stack:94448,bet:0},{seat:3,stack:28626,bet:0}],
    pot_center:2400, board:['8s','4h','5s','Kd','7h'], log:[]};
  const messages = [
    {type:'stream_start',stream_id:'stream1',server_now_ms:1},
    {type:'bot_action',seq:1,event:{kind:'bot_action',street:'river',seat:3,
      action:'bet',amount:600,clock_started_ms:8000,act_at_ms:9000}},
    {type:'final',payload:{token:2,view:{...view,type:'result'}}}
  ];
  const sandbox = {
    S:{busy:false,view,view0:view,timers:[],clockOffset:123},
    crypto:{randomUUID:()=> '12345678-1234-1234-1234-123456789abc'},
    Date, Promise, Set, AbortController, TextDecoder, TextEncoder,
    setTimeout:(fn,ms)=>realTimeout(fn, Math.min(ms, 5)), clearTimeout,
    HERO_ACTION_PAUSE:0, serverNow:()=>10000,
    heroRequestEntry:()=>null, fullActionLog:()=>[],
    applyEntry:(ss,e)=>{const s=ss.seats.find(x=>x.seat===e.seat);s.stack-=e.amount;s.bet=e.amount;},
    apply:p=>applied.push(p),
    setBusy:on=>{sandbox.S.busy=on;},
    noteSchedule:()=>{}, terminalFold:()=>false, paceMs:()=>0,
    clearSeatClock:()=>{}, SEAT_CLOCKS:{}, seatClock:()=>{},
    renderSeats:v=>frames.push(JSON.parse(JSON.stringify(v))),
    renderChips:()=>{},renderBoard:()=>{},renderPot:()=>{},renderHero:()=>{},
    bubbleAt:()=>{},markFold:()=>{},STREET:{river:'리버'},
    $:()=>({innerHTML:''}), toast:msg=>{throw Error(msg);},
    fetch:async (url,init)=>{
      if(url==='/api/step-stream') {
        posts++;
        if(source.includes('function stepEventReceiver(')) assert(JSON.parse(init.body).request_id);
        if(init.signal) init.signal.addEventListener('abort',()=>{aborted=true;});
        if(blocked) return new Promise(()=>{});
        let i=0;
        return {ok:true,body:{getReader:()=>({read:async()=>{
          if(i===messages.length) return {done:true};
          return {done:false,value:new TextEncoder().encode(JSON.stringify(messages[i++])+'\n')};
        }})}};
      }
      assert(url.startsWith('/api/step-progress?'));
      polls++;
      return {ok:true,json:async()=>({messages,cursor:3,server_now_ms:Date.now()+123})};
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(extract(source.includes('function stepEventReceiver(')
    ? 'function stepEventReceiver(' : 'async function callStepStream(', 'async function call(path,'), sandbox);
  const result = await Promise.race([
    sandbox.callStepStream({action:'fold',amount:0,token:1},'진행 중…'),
    new Promise((_,reject)=>realTimeout(()=>reject(Error('stream remained blocked')),500))
  ]);
  assert.equal(result.token,2);
  assert.equal(posts,1,'never resubmit the HERO action');
  assert.equal(applied.length,1);
  assert.equal(frames.length,1);
  assert.equal(frames[0].seats[1].stack,28026);
  assert.equal(sandbox.S.busy,false);
  assert(aborted);
  if(blocked) assert(polls>0);
  else assert.equal(sandbox.S.clockOffset,123,'old stream_start cannot rewind time');
}
async function main() {
  await run(true);
  await run(false);
  const sandbox={Set};vm.createContext(sandbox);
  vm.runInContext(extract('function stepEventReceiver(', 'async function callStepStream('),sandbox);
  const seen=[];
  const receive=sandbox.stepEventReceiver(()=>seen.push('start'),o=>seen.push(o.seq),()=>seen.push('final'),()=>seen.push('error'));
  receive({type:'stream_start'});
  receive({type:'bot_action',seq:1}); // stream
  receive({type:'stream_start'});    // polling catches up
  receive({type:'bot_action',seq:1});
  receive({type:'bot_action',seq:2});
  receive({type:'bot_action',seq:2}); // buffered stream catches up
  receive({type:'final',payload:{}});
  receive({type:'final',payload:{}});
  assert.deepEqual(seen,['start',1,2,'final']);
  console.log('PASS: blocked headers recover via progress; one action POST; no duplicate bets/final; delayed timestamp never rewinds clock');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
