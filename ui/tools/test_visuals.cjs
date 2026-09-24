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

