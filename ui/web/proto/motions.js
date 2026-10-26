// 1인칭 테이블 손 동작 시제품 (docs/presentation-spec.md 7장).
// 칩 셔플, 칩 내밀기, 카드 정리, 들춰보기, 카드 프로텍터, 폴드.
// 손은 임시 상자다. HandRig 자리만 잡아 두고, 그림·모델이 오면 몸통만 바꾼다.
// 단위는 m. 테이블 윗면 y=0.75, 내 쪽 레일이 z=0, 테이블은 -z 로 뻗는다.
import * as THREE from '../vendor/three-0.160.0.module.min.js';

const Q = new URLSearchParams(location.search);
const SPEED = Math.max(0.05, Number(Q.get('speed') || 1));    // 느리게 돌려 보기
// ?shot=manual 이면 시간이 저절로 흐르지 않고 __t2motion.step(ms) 로만 흐른다(스크린샷용).
const MANUAL = Q.get('shot') === 'manual';
let vt = 0;
const clock = () => MANUAL ? vt : performance.now();
const INK = 0x2a1a10;
const TOP = 0.75;

// ---------- 렌더러 / 장면 ----------
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: !!Q.get('shot') });
renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1d2238);

// 카메라: 사양 2장 — 가슴 높이 1.0m, 가로 시야 55°. '가까이'는 동작 확인용.
const cam = new THREE.PerspectiveCamera(30, 1, 0.01, 30);
const VIEWS = {
  fp:    { pos: [0, 1.0, 0.30],  at: [0, TOP, -0.9],   hfov: 55 },
  close: { pos: [0.02, 1.13, 0.0], at: [0.03, TOP, -0.36], hfov: 55 },
};
let view = 'fp';
function applyView() {
  const v = VIEWS[view], w = canvas.clientWidth || window.innerWidth, h = canvas.clientHeight || window.innerHeight, a = w / h;
  cam.aspect = a;
  cam.fov = 2 * Math.atan(Math.tan(v.hfov / 2 * Math.PI / 180) / a) * 180 / Math.PI;
  cam.position.set(...v.pos);
  cam.lookAt(new THREE.Vector3(...v.at));
  cam.updateProjectionMatrix();
  renderer.setSize(w, h, false);
}
window.addEventListener('resize', applyView);

scene.add(new THREE.HemisphereLight(0xfff1dc, 0x2b3150, 1.1));
const sun = new THREE.DirectionalLight(0xffffff, 1.7);
sun.position.set(0.5, 2.0, 0.6);
sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024);
Object.assign(sun.shadow.camera, { left: -0.7, right: 0.7, top: 0.7, bottom: -0.7, near: 0.5, far: 4 });
sun.shadow.bias = -0.0004;
sun.target.position.set(0, TOP, -0.35);
scene.add(sun, sun.target);

// ---------- 툰 재질 + 외곽선 (그림체 규칙: 굵은 외곽선, 단순한 셰이딩) ----------
const grad = new THREE.DataTexture(new Uint8Array([95, 175, 255]), 3, 1, THREE.RedFormat);
grad.minFilter = grad.magFilter = THREE.NearestFilter;
grad.needsUpdate = true;
const toon = (color, map, extra) => new THREE.MeshToonMaterial(Object.assign(
  { color: map ? 0xffffff : color, map: map || null, gradientMap: grad }, extra || {}));
const outlineMat = new THREE.MeshBasicMaterial({ color: INK, side: THREE.BackSide });

function outlined(geo, mat, k = 1.05, ky) {
  const g = new THREE.Group();
  const m = new THREE.Mesh(geo, mat);
  m.castShadow = true; m.receiveShadow = true;
  const o = new THREE.Mesh(geo, outlineMat);
  o.scale.set(k, ky || k, k);
  g.add(o, m);
  g.userData.body = m; g.userData.line = o;
  return g;
}
function canvasTex(w, h, draw) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  return t;
}

// ---------- 테이블 ----------
const FELT_C = 0x1f5a44;
{
  const felt = new THREE.Mesh(new THREE.CircleGeometry(1, 96), toon(FELT_C));
  felt.rotation.x = -Math.PI / 2; felt.scale.set(1.55, 0.95, 1); felt.position.set(0, TOP, -0.95);
  felt.receiveShadow = true; scene.add(felt);
  const line = new THREE.Mesh(new THREE.RingGeometry(0.60, 0.606, 96),
    new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.18 }));
  line.rotation.x = -Math.PI / 2; line.scale.set(1.55, 0.95, 1); line.position.set(0, TOP + 0.0005, -0.95);
  scene.add(line);
  const rail = outlined(new THREE.TorusGeometry(1, 0.055, 12, 120), toon(0x6b4426), 1.03);
  rail.rotation.x = -Math.PI / 2; rail.scale.set(1.58, 0.98, 1); rail.position.set(0, TOP + 0.01, -0.95);
  scene.add(rail);
  // 맞은편 상대 몸통(임시) — 1인칭 구도에서 위치감만 준다
  [[-0.95, -1.35, 0xc9706a], [-0.35, -1.75, 0xd9cdb0], [0.35, -1.75, 0x8a2f3a], [0.95, -1.35, 0x2f3f66]].forEach(([x, z, c]) => {
    const b = outlined(new THREE.BoxGeometry(0.42, 0.42, 0.18), toon(c), 1.03);
    b.position.set(x, TOP + 0.19, z); b.lookAt(0, TOP + 0.19, 0.3); scene.add(b);
  });
}

// ---------- 카드 ----------
const CW = 0.063, CH = 0.088, CT = 0.0007;
const faceTex = (rank, suit, red) => canvasTex(256, 358, (x, w, h) => {
  x.fillStyle = '#fffaf0'; x.fillRect(0, 0, w, h);
  x.strokeStyle = '#3a2414'; x.lineWidth = 10; x.strokeRect(5, 5, w - 10, h - 10);
  x.fillStyle = red ? '#c8402c' : '#2a1d12';
  x.font = 'bold 92px sans-serif'; x.textBaseline = 'top'; x.fillText(rank, 22, 18);
  x.font = '74px sans-serif'; x.fillText(suit, 26, 116);
  x.font = '150px sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(suit, w * 0.6, h * 0.62);
});
const backTex = canvasTex(256, 358, (x, w, h) => {
  x.fillStyle = '#2b3150'; x.fillRect(0, 0, w, h);
  x.strokeStyle = '#f2b84b'; x.lineWidth = 10; x.strokeRect(18, 18, w - 36, h - 36);
  x.fillStyle = '#f2b84b'; x.font = 'bold 120px sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle';
  x.fillText('♠', w / 2, h / 2 - 10); x.font = 'bold 44px sans-serif'; x.fillText('T2', w / 2, h / 2 + 78);
  x.strokeStyle = '#3a2414'; x.lineWidth = 10; x.strokeRect(5, 5, w - 10, h - 10);
});

// 카드 = root(테이블 위 위치·방향) → hinge(먼 쪽 모서리) → flip(뒤집기) → 몸체
function makeCard(rank, suit, red) {
  const root = new THREE.Group(), hinge = new THREE.Group(), flip = new THREE.Group();
  hinge.position.z = -CH / 2;
  flip.position.z = CH / 2;
  const mats = [];
  const edge = outlined(new THREE.BoxGeometry(CW, CT, CH), (() => { const m = toon(0xfffaf0, null, { transparent: true }); mats.push(m); return m; })(), 1.06, 1.6);
  const back = new THREE.Mesh(new THREE.PlaneGeometry(CW * 0.98, CH * 0.98), toon(0, backTex, { transparent: true }));
  back.rotation.x = -Math.PI / 2; back.position.y = CT / 2 + 0.00005;
  const face = new THREE.Mesh(new THREE.PlaneGeometry(CW * 0.98, CH * 0.98), toon(0, faceTex(rank, suit, red), { transparent: true }));
  face.rotation.x = Math.PI / 2; face.position.y = -CT / 2 - 0.00005;
  mats.push(back.material, face.material, edge.userData.line.material);
  back.castShadow = face.castShadow = true;
  flip.add(edge, back, face); hinge.add(flip); root.add(hinge);
  root.userData = { hinge, flip, mats, faceUp: false };
  scene.add(root);
  return root;
}
const cards = [makeCard('A', '♥', true), makeCard('K', '♠', false)];
// 카드 외곽선 재질은 공유 재질이라 따로 투명도용 복제를 둔다
cards.forEach(c => {
  const line = c.userData.flip.children[0].userData.line;
  line.material = outlineMat.clone(); line.material.transparent = true;
  c.userData.mats[3] = line.material;
});
const CARD_Y = TOP + CT / 2 + 0.0002;
const NEAT = [{ x: -0.009, z: -0.335, ry: 0.07, y: CARD_Y }, { x: 0.010, z: -0.331, ry: -0.05, y: CARD_Y + CT + 0.0002 }];

// ---------- 카드 프로텍터 ----------
const protTop = canvasTex(256, 256, (x, w) => {
  const g = x.createRadialGradient(w * 0.38, w * 0.32, 10, w / 2, w / 2, w / 2);
  g.addColorStop(0, '#fff1c2'); g.addColorStop(0.55, '#f2b84b'); g.addColorStop(1, '#b57b20');
  x.fillStyle = g; x.beginPath(); x.arc(w / 2, w / 2, w / 2, 0, 7); x.fill();
  x.strokeStyle = '#3a2414'; x.lineWidth = 9; x.beginPath(); x.arc(w / 2, w / 2, w / 2 - 22, 0, 7); x.stroke();
  x.fillStyle = '#3a2414'; x.textAlign = 'center'; x.textBaseline = 'middle';
  x.font = 'bold 86px sans-serif'; x.fillText('♠', w / 2, w / 2 - 22); x.font = 'bold 54px sans-serif'; x.fillText('T2', w / 2, w / 2 + 52);
});
const PR = 0.026, PH = 0.008;
const protector = outlined(new THREE.CylinderGeometry(PR, PR * 1.04, PH, 48),
  [toon(0xd99a32), toon(0, protTop), toon(0xb57b20)], 1.07, 1.12);
const PROT_REST = new THREE.Vector3(-0.115, TOP + PH / 2, -0.30);
protector.position.copy(PROT_REST);
scene.add(protector);
let protOn = false;

// ---------- 칩 ----------
const R = 0.0195, CHH = 0.0034;
const chipGeo = new THREE.CylinderGeometry(R, R, CHH, 36);
function chipMats(col) {
  const side = canvasTex(256, 16, (x, w, h) => {
    x.fillStyle = col; x.fillRect(0, 0, w, h); x.fillStyle = '#fbf1dc';
    for (let i = 0; i < 8; i++) x.fillRect(i * w / 8 + 6, 0, w / 16 - 4, h);
  });
  const top = canvasTex(128, 128, (x, w) => {
    x.fillStyle = col; x.beginPath(); x.arc(w / 2, w / 2, w / 2, 0, 7); x.fill();
    x.strokeStyle = '#fbf1dc'; x.lineWidth = 9; x.setLineDash([13, 11]); x.beginPath(); x.arc(w / 2, w / 2, w / 2 - 8, 0, 7); x.stroke();
    x.setLineDash([]); x.lineWidth = 3; x.beginPath(); x.arc(w / 2, w / 2, w * 0.28, 0, 7); x.stroke();
  });
  return [toon(0, side), toon(0, top), toon(0, top)];
}
const MATS = { red: chipMats('#c8402c'), navy: chipMats('#2f3a6b'), gold: chipMats('#d99a32') };
const chips = [];
function makeChip(kind) {
  const c = outlined(chipGeo, MATS[kind], 1.06, 1.12);
  c.userData.kind = kind; scene.add(c); chips.push(c); return c;
}
// 자리: 셔플용 두 더미(빨강·남색), 베팅용 금색 더미
const SLOT = {
  A: new THREE.Vector3(0.150, TOP, -0.300),
  B: new THREE.Vector3(0.191, TOP, -0.300),
  M: new THREE.Vector3(0.1705, TOP, -0.300),
  C: new THREE.Vector3(0.105, TOP, -0.252),
  BET: new THREE.Vector3(0.05, TOP, -0.52),
};
const stackA = [], stackB = [], stackC = [];
for (let i = 0; i < 10; i++) { stackA.push(makeChip('red')); stackB.push(makeChip('navy')); }
for (let i = 0; i < 14; i++) stackC.push(makeChip('gold'));
const chipY = i => TOP + CHH * (i + 0.5) + 0.0002;
function placeStack(list, at) { list.forEach((c, i) => { c.position.set(at.x, chipY(i), at.z); c.rotation.set(0, Math.random() * 6, 0); c.visible = true; }); }
let betPile = [];
function resetChips() {
  stackA.length = stackB.length = stackC.length = 0; betPile = [];
  chips.forEach(c => { (c.userData.kind === 'red' ? stackA : c.userData.kind === 'navy' ? stackB : stackC).push(c); });
  placeStack(stackA, SLOT.A); placeStack(stackB, SLOT.B); placeStack(stackC, SLOT.C);
}
resetChips();

// ---------- 손 (HandRig — 임시 상자) ----------
// 몸체만 바꾸면 그림/3D 모델로 교체된다. 동작은 손 그룹의 위치·회전만 움직인다.
function makeHand(side) {
  const g = new THREE.Group();
  const skin = toon(0x5aa6e8), sleeve = toon(0x2f3f66);
  const palm = outlined(new THREE.BoxGeometry(0.072, 0.022, 0.080), skin, 1.08);
  const fingers = outlined(new THREE.BoxGeometry(0.066, 0.016, 0.040), skin, 1.1);
  fingers.position.set(0, -0.004, -0.058);
  const thumb = outlined(new THREE.BoxGeometry(0.018, 0.014, 0.040), skin, 1.12);
  thumb.position.set(-side * 0.043, -0.004, -0.018); thumb.rotation.y = side * 0.5;
  // 팔뚝은 짧고 낮게 — 손목에서 내 쪽 레일(팔꿈치)로 거의 수평으로 간다. 길면 화면을 가린다.
  const arm = outlined(new THREE.CylinderGeometry(0.025, 0.031, 0.22, 18), sleeve, 1.06);
  arm.rotation.x = Math.PI / 2 - 0.12; arm.position.set(0, 0.012, 0.15);
  g.add(palm, fingers, thumb, arm);
  scene.add(g);
  return g;
}
const RH = makeHand(1), LH = makeHand(-1);
const REST = {
  R: { x: 0.215, y: TOP + 0.045, z: -0.17, ry: -0.35, rx: 0.08, rz: 0 },
  L: { x: -0.215, y: TOP + 0.045, z: -0.17, ry: 0.35, rx: 0.08, rz: 0 },
};
const setPose = (h, p) => { h.position.set(p.x, p.y, p.z); h.rotation.set(p.rx || 0, p.ry || 0, p.rz || 0); };
setPose(RH, REST.R); setPose(LH, REST.L);

// ---------- 트윈 ----------
const ease = {
  io: t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
  out: t => 1 - Math.pow(1 - t, 3),
  back: t => { const c = 1.6; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); },
};
const tweens = new Set();
function tween(ms, fn, e = ease.io) {
  return new Promise(res => tweens.add({ t0: clock(), ms: ms / SPEED, fn, e, res }));
}
const wait = ms => tween(ms, () => {});
const lerp = (a, b, t) => a + (b - a) * t;
function poseOf(h) { return { x: h.position.x, y: h.position.y, z: h.position.z, rx: h.rotation.x, ry: h.rotation.y, rz: h.rotation.z }; }
function moveHand(h, to, ms = 360, e = ease.io) {
  const a = poseOf(h), b = Object.assign({}, a, to);
  return tween(ms, t => setPose(h, { x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t), z: lerp(a.z, b.z, t),
    rx: lerp(a.rx, b.rx, t), ry: lerp(a.ry, b.ry, t), rz: lerp(a.rz, b.rz, t) }), e);
}
function moveObj(o, to, ms = 360, e = ease.io) {
  const p0 = o.position.clone(), r0 = o.rotation.clone();
  return tween(ms, t => {
    if (to.x !== undefined) o.position.x = lerp(p0.x, to.x, t);
    o.position.y = (to.y !== undefined ? lerp(p0.y, to.y, t) : p0.y) + (to.arc ? Math.sin(Math.PI * t) * to.arc : 0);
    if (to.z !== undefined) o.position.z = lerp(p0.z, to.z, t);
    if (to.rx !== undefined) o.rotation.x = lerp(r0.x, to.rx, t);
    if (to.ry !== undefined) o.rotation.y = lerp(r0.y, to.ry, t);
    if (to.rz !== undefined) o.rotation.z = lerp(r0.z, to.rz, t);
  }, e);
}

// 동작은 한 줄로 쌓아 차례대로 재생한다(겹쳐 꼬이지 않게).
let chain = Promise.resolve(), busy = 0;
function run(fn) {
  busy++;
  chain = chain.then(fn).catch(err => console.error(err)).finally(() => { busy--; });
  return chain;
}

// ---------- 동작: 카드 ----------
const protOnCardsPos = () => new THREE.Vector3((NEAT[0].x + NEAT[1].x) / 2, NEAT[1].y + CT / 2 + PH / 2 + 0.0003, -0.342);
let cardsNeat = false, cardsIn = false;

async function deal() {
  if (protOn) await protectorOff(true);
  cardsNeat = false; cardsIn = true;
  const messy = [{ x: -0.032, z: -0.36, ry: 0.32 }, { x: 0.034, z: -0.312, ry: -0.42 }];
  cards.forEach((c, i) => {
    const u = c.userData; u.faceUp = false; u.flip.rotation.x = 0; u.hinge.rotation.x = 0;
    u.mats.forEach(m => { m.opacity = 1; }); c.visible = true;
    c.position.set(0, TOP + 0.002 + i * 0.001, -1.25); c.rotation.set(0, 2.4 + i, 0);
  });
  await Promise.all(cards.map((c, i) => wait(i * 140).then(() =>
    moveObj(c, { x: messy[i].x, y: CARD_Y + i * (CT + 0.0002), z: messy[i].z, ry: messy[i].ry }, 520, ease.out))));
}

// 카드 정리: 왼손이 두 장을 모아 가지런히 놓고 톡 친다
async function tidy() {
  if (!cardsIn) return;
  // 왼손이 카드 왼쪽 옆으로 와서(손가락이 오른쪽을 향함) 두 장을 모은다
  await moveHand(LH, { x: -0.115, y: TOP + 0.022, z: -0.325, ry: -1.3, rx: 0.05 }, 320);
  await Promise.all([
    ...cards.map((c, i) => moveObj(c, { x: NEAT[i].x, z: NEAT[i].z, ry: NEAT[i].ry, y: NEAT[i].y }, 380)),
    moveHand(LH, { x: -0.085 }, 380),
    protOn ? moveObj(protector, { x: protOnCardsPos().x, z: protOnCardsPos().z, y: protOnCardsPos().y }, 380) : null,
  ]);
  // 톡: 손이 살짝 눌렀다 뗀다, 카드가 아주 조금 튄다
  await moveHand(LH, { y: TOP + 0.014 }, 110);
  await Promise.all([moveHand(LH, { y: TOP + 0.026 }, 140),
    ...cards.map(c => moveObj(c, { arc: 0.0018 }, 140))]);
  cardsNeat = true;
  await moveHand(LH, REST.L, 340);
}

// 들춰보기(스퀴즈): 가까운 모서리를 들어 앞면을 본다. 프로텍터는 먼 쪽에 그대로 둔다.
async function peek() {
  if (!cardsIn) return;
  if (!cardsNeat) await tidy();
  if (cards[0].userData.faceUp) return;
  // 왼손을 카드 왼쪽 아래 모서리에 대고, 가까운 모서리를 들어 올린다(먼 쪽 모서리가 경첩)
  await moveHand(LH, { x: -0.095, y: TOP + 0.016, z: -0.30, ry: -1.15, rx: 0.05, rz: 0 }, 300);
  // 카메라가 움직이지 않으므로 실제보다 크게(약 65°) 들어 앞면이 화면에 보이게 한다
  const lift = -1.12;
  // 프로텍터가 올라가 있으면 들리는 카드에 밀려 먼 쪽 테이블로 살짝 미끄러졌다가 돌아온다
  const pBack = protOn ? protector.position.clone() : null;
  if (protOn) moveObj(protector, { z: NEAT[0].z - CH / 2 - PR - 0.004, y: TOP + PH / 2 }, 300);
  await Promise.all([...cards.map((c, i) => tween(340, t => { c.userData.hinge.rotation.x = lift * t * (i ? 0.92 : 1); })),
    moveHand(LH, { y: TOP + 0.07, z: -0.29, rz: -0.6 }, 340)]);
  await wait(900);
  await Promise.all([...cards.map((c, i) => tween(260, t => { c.userData.hinge.rotation.x = lift * (1 - t) * (i ? 0.92 : 1); })),
    moveHand(LH, { y: TOP + 0.016, z: -0.30, rz: 0 }, 260)]);
  if (pBack) await moveObj(protector, { z: pBack.z, y: pBack.y, arc: 0.006 }, 260);
  await moveHand(LH, REST.L, 320);
}

async function flipCards() {
  if (!cardsIn) return;
  if (protOn) await protectorOff();
  const up = !cards[0].userData.faceUp;
  await moveHand(LH, { x: -0.01, y: TOP + 0.03, z: -0.29, rx: 0.3, ry: 0 }, 260);
  await Promise.all([...cards.map((c, i) => wait(i * 90).then(() => tween(380, t => {
    c.userData.flip.rotation.x = (up ? t : 1 - t) * Math.PI;
    c.userData.flip.position.y = Math.sin(Math.PI * t) * 0.035;
  }))), moveHand(LH, { y: TOP + 0.06, z: -0.31 }, 380)]);
  cards.forEach(c => { c.userData.faceUp = up; });
  await moveHand(LH, REST.L, 300);
}

// 카드 프로텍터: 왼손이 집어 카드 위에 살짝 돌리며 올린다
async function protectorOn() {
  if (!cardsIn || protOn) return;
  if (!cardsNeat) await tidy();
  const p = protector.position;
  await moveHand(LH, { x: p.x - 0.062, y: TOP + 0.012, z: p.z + 0.004, ry: -1.35, rx: 0.05 }, 300);
  const to = protOnCardsPos();
  const grab = new THREE.Vector3().subVectors(protector.position, LH.position);
  const follow = () => protector.position.copy(LH.position).add(grab);
  await Promise.all([moveHand(LH, { y: TOP + 0.06 }, 180), tween(180, follow)]);
  await Promise.all([moveHand(LH, { x: to.x - grab.x, z: to.z - grab.z }, 360), tween(360, follow)]);
  await Promise.all([moveHand(LH, { y: to.y - grab.y + 0.002 }, 200, ease.out), tween(200, follow)]);
  const r0 = protector.rotation.y;
  await Promise.all([tween(260, t => { protector.rotation.y = r0 + 0.9 * ease.out(t); protector.position.y = to.y; }),
    moveHand(LH, { ry: -1.55 }, 260)]);
  protOn = true;
  await moveHand(LH, REST.L, 320);
}
async function protectorOff(fast) {
  if (!protOn) return;
  const ms = fast ? 0.6 : 1;
  await moveHand(LH, { x: protector.position.x - 0.062, y: protector.position.y + 0.004, z: protector.position.z + 0.004, ry: -1.35, rx: 0.05 }, 280 * ms);
  const grab = new THREE.Vector3().subVectors(protector.position, LH.position);
  const follow = () => protector.position.copy(LH.position).add(grab);
  await Promise.all([moveHand(LH, { y: TOP + 0.065 }, 160 * ms), tween(160 * ms, follow)]);
  await Promise.all([moveHand(LH, { x: PROT_REST.x - grab.x, z: PROT_REST.z - grab.z }, 320 * ms), tween(320 * ms, follow)]);
  await Promise.all([moveHand(LH, { y: PROT_REST.y - grab.y }, 160 * ms), tween(160 * ms, follow)]);
  protOn = false;
  await moveHand(LH, REST.L, 260 * ms);
}

// 폴드: 프로텍터를 치우고, 두 장을 앞으로 밀어 낸다
async function fold() {
  if (!cardsIn) return;
  if (protOn) await protectorOff(true);
  if (cards[0].userData.faceUp) await flipCards();
  await moveHand(LH, { x: 0, y: TOP + 0.025, z: -0.255, ry: 0, rx: 0.1 }, 260);
  await Promise.all([
    moveHand(LH, { z: -0.40, y: TOP + 0.03 }, 300, ease.out),
    ...cards.map((c, i) => moveObj(c, { z: -0.72 - i * 0.02, x: c.position.x * 0.5 + (i ? 0.03 : -0.02), ry: c.rotation.y + (i ? 0.6 : -0.4), arc: 0.012 }, 520, ease.out)),
  ]);
  await Promise.all([moveHand(LH, REST.L, 320),
    tween(300, t => cards.forEach(c => c.userData.mats.forEach(m => { m.opacity = 1 - t; })))]);
  cards.forEach(c => { c.visible = false; });
  cardsIn = false; cardsNeat = false;
}

// ---------- 동작: 칩 ----------
// 칩 셔플: 두 더미를 나란히 놓고 안쪽을 눌러 엇갈려 끼운 뒤, 색별로 다시 둘로 나눈다
async function shuffle() {
  if (stackA.length < 2 || stackB.length < 2) { await chipReset(); }
  const hand = RH;
  const H0 = TOP + CHH * 10 + 0.012;
  await moveHand(hand, { x: SLOT.B.x + 0.072, y: H0, z: SLOT.M.z + 0.006, ry: 1.35, rx: 0.04 }, 300);
  // 1) 안쪽 가장자리를 눌러 두 더미가 서로 기댄다
  await Promise.all([
    moveHand(hand, { y: H0 - 0.004, x: SLOT.B.x + 0.066 }, 220),
    ...stackA.map((c, i) => moveObj(c, { x: SLOT.A.x + 0.004, rz: -0.20, y: chipY(i) + 0.002 }, 220)),
    ...stackB.map((c, i) => moveObj(c, { x: SLOT.B.x - 0.004, rz: 0.20, y: chipY(i) + 0.002 }, 220)),
  ]);
  // 2) 아래부터 번갈아 한 장씩 가운데 더미로 떨어진다
  const merged = [];
  for (let i = 0; i < Math.max(stackA.length, stackB.length); i++) {
    if (stackA[i]) merged.push(stackA[i]);
    if (stackB[i]) merged.push(stackB[i]);
  }
  await Promise.all([
    ...merged.map((c, k) => wait(k * 22).then(() => moveObj(c, { x: SLOT.M.x, y: chipY(k), z: SLOT.M.z, rz: 0 }, 170, ease.out))),
    moveHand(hand, { y: TOP + CHH * merged.length + 0.012, x: SLOT.M.x + 0.07 }, 22 * merged.length + 170),
  ]);
  // 3) 손가락으로 위를 눌러 가지런히
  await moveHand(hand, { y: TOP + CHH * merged.length + 0.006 }, 90);
  await moveHand(hand, { y: TOP + CHH * merged.length + 0.014 }, 120);
  await wait(160);
  // 4) 다시 둘로 나눈다(색별) — 손이 위 더미를 들어 옆으로
  const reds = merged.filter(c => c.userData.kind === 'red'), navies = merged.filter(c => c.userData.kind === 'navy');
  await Promise.all([
    ...reds.map((c, i) => moveObj(c, { x: SLOT.A.x, y: chipY(i), z: SLOT.A.z, arc: 0.012 }, 300)),
    ...navies.map((c, i) => moveObj(c, { x: SLOT.B.x, y: chipY(i), z: SLOT.B.z, arc: 0.012 }, 300)),
    moveHand(hand, { y: H0 + 0.01, x: SLOT.B.x + 0.075 }, 300),
  ]);
  stackA.length = 0; stackA.push(...reds); stackB.length = 0; stackB.push(...navies);
  await moveHand(hand, REST.R, 340);
}

// 칩 내밀기: 금색 더미 위에서 n개를 손끝으로 밀어 베팅 선 앞에 놓는다
async function pushChips(n = 4) {
  if (stackC.length === 0) await chipReset();
  n = Math.min(n, stackC.length);
  const take = stackC.splice(stackC.length - n, n);
  const at = SLOT.C, to = new THREE.Vector3(SLOT.BET.x + betPile.length * 0.0, TOP, SLOT.BET.z);
  await moveHand(RH, { x: at.x + 0.004, y: TOP + 0.03 + CHH * (stackC.length + n) * 0.5, z: at.z + 0.055, ry: 0, rx: 0.05 }, 300);
  // 집어서 미끄러뜨린다: 칩이 손과 함께 간다
  const base = betPile.length;
  const follow = (t) => take.forEach((c, i) => {
    c.position.copy(RH.position).add(offs[i]);
    c.position.y = lerp(chipY(stackC.length + i), chipY(base + i), t);
  });
  await moveHand(RH, { z: at.z + 0.035, y: TOP + 0.028 }, 140);
  const offs = take.map(c => new THREE.Vector3().subVectors(c.position, RH.position));
  const dx = to.x - at.x, dz = to.z - at.z;
  const h0 = poseOf(RH);
  await tween(480, t => { setPose(RH, Object.assign({}, h0, { x: h0.x + dx * t, z: h0.z + dz * t })); follow(t); }, ease.io);
  betPile.push(...take);
  await moveHand(RH, { y: TOP + 0.05, z: RH.position.z + 0.03 }, 150);
  await moveHand(RH, REST.R, 380);
}

// 올인: 두 손으로 앞의 칩을 모두 감싸 밀어 낸다
async function allIn() {
  const all = [...stackA, ...stackB, ...stackC];
  if (!all.length) return;
  await Promise.all([moveHand(RH, { x: 0.255, y: TOP + 0.03, z: -0.22, ry: 0.45, rx: 0.05 }, 360),
    moveHand(LH, { x: 0.035, y: TOP + 0.03, z: -0.22, ry: -0.45, rx: 0.05 }, 360)]);
  const piles = [];
  all.forEach((c, i) => { const k = i % 4; (piles[k] = piles[k] || []).push(c); });
  const dz = -0.24;
  await Promise.all([
    moveHand(RH, { x: 0.215, z: -0.22 + dz }, 560), moveHand(LH, { x: 0.07, z: -0.22 + dz }, 560),
    ...piles.flatMap((p, k) => p.map((c, i) => moveObj(c, {
      x: 0.085 + k * 0.042, z: -0.53 + (k % 2) * 0.012, y: chipY(i) }, 560))),
  ]);
  stackA.length = stackB.length = stackC.length = 0;
  betPile = all;
  await Promise.all([moveHand(RH, REST.R, 380), moveHand(LH, REST.L, 380)]);
}

async function chipReset() {
  const targets = new Map();
  const a = chips.filter(c => c.userData.kind === 'red'), b = chips.filter(c => c.userData.kind === 'navy'), g = chips.filter(c => c.userData.kind === 'gold');
  a.forEach((c, i) => targets.set(c, [SLOT.A, i])); b.forEach((c, i) => targets.set(c, [SLOT.B, i])); g.forEach((c, i) => targets.set(c, [SLOT.C, i]));
  await Promise.all(chips.map(c => { const [s, i] = targets.get(c); return moveObj(c, { x: s.x, y: chipY(i), z: s.z, rx: 0, rz: 0, arc: 0.02 }, 420); }));
  stackA.length = stackB.length = stackC.length = 0; stackA.push(...a); stackB.push(...b); stackC.push(...g); betPile = [];
}

// 대기 중 셔플: 아무 동작이 없을 때 가끔 칩을 섞는다
let idle = false, idleTimer = 0;
function scheduleIdle() {
  clearTimeout(idleTimer);
  if (!idle) return;
  idleTimer = setTimeout(() => { if (idle && busy === 0) run(shuffle).then(scheduleIdle); else scheduleIdle(); },
    (2500 + Math.random() * 3500) / SPEED);
}

// ---------- 버튼 ----------
const ACTS = {
  deal: () => run(deal), tidy: () => run(tidy), peek: () => run(peek), flip: () => run(flipCards),
  protector: () => run(() => protOn ? protectorOff() : protectorOn()), fold: () => run(fold),
  shuffle: () => run(shuffle), bet: () => run(() => pushChips(4)), allin: () => run(allIn), chipreset: () => run(chipReset),
};
document.querySelectorAll('[data-act]').forEach(b => b.addEventListener('click', () => {
  const a = b.dataset.act;
  if (a === 'idle') { idle = !idle; b.classList.toggle('on', idle); scheduleIdle(); return; }
  ACTS[a]();
}));
document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => {
  view = b.dataset.view; applyView();
  document.querySelectorAll('[data-view]').forEach(x => x.classList.toggle('on', x === b));
}));

// 스크린샷·검사용 손잡이
window.__t2motion = { run: (a) => { ACTS[a](); }, view: (v) => { view = v; applyView(); render(); }, idle: () => busy === 0,
  step: async (ms) => { const n = Math.max(1, Math.round(ms / 16)); for (let i = 0; i < n; i++) { vt += ms / n; tick(); await Promise.resolve(); await Promise.resolve(); } render(); } };

// ---------- 루프 ----------
function tick() {
  const now = clock();
  for (const tw of tweens) {
    const t = Math.min(1, (now - tw.t0) / tw.ms);
    tw.fn(tw.e(t));
    if (t >= 1) { tweens.delete(tw); tw.res(); }
  }
  // 숨쉬기 같은 아주 작은 대기 움직임(손)
  const s = Math.sin(now / 900) * 0.0012;
  if (busy === 0) { RH.position.y = REST.R.y + s; LH.position.y = REST.L.y - s; }
}
function render() { renderer.render(scene, cam); }
function frame() {
  if (!MANUAL) tick();
  render();
  requestAnimationFrame(frame);
}
applyView();
run(deal).then(() => run(tidy));
requestAnimationFrame(frame);
