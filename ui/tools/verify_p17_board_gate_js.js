'use strict';
/* Board motion is a hard pre-compute barrier for the next street. */
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync(require('path').join(__dirname, '../web/app.js'), 'utf8');
const from = src.indexOf('function afterBoardMotion(');
const until = src.indexOf('async function callStepStream(', from);
assert(from >= 0 && until > from, 'board motion gate missing');
assert(!src.includes('const computingTimer = setTimeout('),
       'unconditional calculating banner can show before board opens');
assert(src.includes("if (head && head.kind === 'bot_begin')"),
       'bot countdown is not tied to real calculation start');
assert(src.includes("e.kind === 'hand_settle_begin'") &&
       src.includes("e.mode === 'showdown' ? '쇼다운"),
       'terminal river must display showdown, never a bot calculation');
assert(src.includes("e.kind === 'hand_result_ready'") &&
       src.includes("S.earlyShownHash === String(v.hash)"),
       'public result must be streamed early without replaying the final showdown');
assert(src.includes("const preview = Object.assign({}, e") &&
       src.includes("shown: e.shown || {}"),
       'early showdown must only receive expressly shown cards');
let resolutions = [];
const animated = Array.from({length: 2}, () => ({
  getAnimations() {
    return [{finished: new Promise(resolve => resolutions.push(resolve))}];
  }
}));
let raf = [];
const ctx = {
  document: {querySelectorAll: () => animated},
  requestAnimationFrame: cb => raf.push(cb),
  Promise,
  Array
};
vm.createContext(ctx);
vm.runInContext(src.slice(from, until), ctx);
async function flush() {
  await Promise.resolve();
  await Promise.resolve();
  await new Promise(resolve => setImmediate(resolve));
}
(async () => {
  let calls = 0;
  ctx.afterBoardMotion(() => calls++);
  assert.strictEqual(calls, 0);
  resolutions[0]();
  await flush();
  assert.strictEqual(calls, 0, 'board ACK fired before all cards finished');
  resolutions[1]();
  await flush();
  assert.strictEqual(calls, 1, 'board ACK not fired after both card motions');
  ctx.document.querySelectorAll = () => [];
  ctx.afterBoardMotion(() => calls++);
  assert.strictEqual(calls, 1);
  assert.strictEqual(raf.length, 1);
  raf.shift()();
  assert.strictEqual(calls, 1);
  assert.strictEqual(raf.length, 1);
  raf.shift()();
  assert.strictEqual(calls, 2);
  console.log('PASS: board animation ACK barrier, no premature compute banner, reduced-motion paint');
})().catch(e => { console.error(e); process.exit(1); });
