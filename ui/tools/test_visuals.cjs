const assert = require('node:assert/strict');
const {gazeOffset, portraitIndex, avatarHTML} = require('../web/visuals.js');
for (const [dx,dy] of [[-200,-400],[200,-400],[-200,400],[200,400],[0,600],[600,0]]) {
  const p=gazeOffset(dx,dy,2);
  assert.equal(Math.sign(p.x),Math.sign(dx));
  assert.equal(Math.sign(p.y),Math.sign(dy));
  assert.ok(Math.hypot(p.x,p.y)<=2.000001);
}
assert.deepEqual(gazeOffset(0,0,2),{x:0,y:0});
assert.deepEqual(gazeOffset(NaN,2,2),{x:0,y:0});
assert.ok(Math.hypot(...Object.values(gazeOffset(1,1,2)))<.1);
for(let id=0;id<500;id++){
  assert.equal(portraitIndex(id),portraitIndex(id));
  assert.ok(portraitIndex(id)>=0 && portraitIndex(id)<9);
  assert.equal((avatarHTML(id).match(/portrait-pupil/g)||[]).length,2);
}
assert.equal(portraitIndex(-1),8);
assert.equal(portraitIndex('?'),0);
assert.ok(!avatarHTML('<script>').includes('<script>'));
console.log('PASS: bounded gaze, all directions, coincident centers, stable portrait mapping, safe markup');
const {createTableAllocator} = require('../web/visuals.js');
const assign = createTableAllocator();
const roster = Array.from({length:9},(_,i)=>({seat:i+1,pid:i*9,hero:i===0}));
const first = assign(roster);
assert.equal(new Set(first.values()).size,9,'colliding pids including hero must have nine distinct portraits');
assert.deepEqual(assign([...roster].reverse()),first,'render order does not change portraits');
const moved = roster.map(s=>({...s,seat:s.seat%9+1}));
const afterMove = assign(moved);
for(let i=0;i<9;i++) assert.equal(afterMove.get(moved[i].seat),first.get(roster[i].seat));
const replacement = moved.map((s,i)=>i===4?{...s,pid:999}:s);
const afterReplacement = assign(replacement);
assert.equal(new Set(afterReplacement.values()).size,9);
for(let i=0;i<9;i++) if(i!==4) assert.equal(afterReplacement.get(moved[i].seat),afterMove.get(moved[i].seat));
for(const n of [8,6,9]) {
  const seats=Array.from({length:n},(_,i)=>({seat:i+1,pid:null,hero:i===0}));
  assert.equal(new Set(assign(seats).values()).size,n,'unknown pids are unique too');
}
console.log('PASS: unique table portraits, hero included, seat moves, replacements, missing ids and 6/8/9 tables');
