'use strict';
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const source = fs.readFileSync(require('path').join(__dirname, '../web/app.js'), 'utf8');
let now = 1000, submitted = 0;
const clock = {hidden:false, textContent:'', classList:{add(){},toggle(){}},style:{setProperty(){}}};
const S = {token:1, actionToken:1, actionDeadlineMs:31000, actionStartMs:13000,
  actionBaseMs:31000, timingOn:true, view:{type:'decision'}};
const ctx = {S, $:()=>clock, serverNow:()=>now, closeRaise(){},send(){submitted++;}};
vm.createContext(ctx);
vm.runInContext(source.slice(source.indexOf('function paintActionClock()'), source.indexOf('function noteTiming(')), ctx);
ctx.paintActionClock(); assert(clock.hidden); assert.equal(submitted,0);
now=13000;ctx.paintActionClock();assert(!clock.hidden);assert.equal(clock.textContent,'18초');
now=31001;ctx.paintActionClock();ctx.paintActionClock();assert.equal(submitted,1);
console.log('PASS: bot wait hides hero clock; server time starts 18s; expiry submits once');

let dismissed = 0, waitingNode = true, shown = 0;
const overlay = {hidden:false}, mainrow = {}, hero = {};
const applyCtx = {S:{}, $: id => id === '#waitingLobby' ? (waitingNode ? {} : null)
  : ({'#overlay':overlay,'#mainrow':mainrow,'#hero':hero}[id] || {}),
  clearTimeout(){},setTimeout(){return 1;},sync(){},closeRaise(){},esc:x=>x,
  showOverlayPersistent(){shown++;waitingNode=true;},
  stopActionClock(){},hideOverlay(){dismissed++;}};
vm.createContext(applyCtx);
vm.runInContext(source.slice(source.indexOf('function apply(resp)'), source.indexOf('  if (resp.no_game)', source.indexOf('function apply(resp)'))) + '}', applyCtx);
applyCtx.S.waitingOpen=true;applyCtx.apply({token:2});assert.equal(dismissed,1);
applyCtx.apply({token:2});assert.equal(dismissed,1);
applyCtx.S.waitingOpen=true;waitingNode=false;applyCtx.apply({token:3});assert.equal(dismissed,1);
console.log('PASS: admission closes its waiting sheet once, preserves other sheets');
applyCtx.apply({waiting:true,message:'sync'});assert.equal(shown,0);
overlay.hidden=true;applyCtx.apply({waiting:true,message:'sync'});assert.equal(shown,1);
console.log('PASS: waiting polls preserve an open review sheet and reopen when closed');
