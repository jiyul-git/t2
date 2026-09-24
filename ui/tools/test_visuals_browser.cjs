/* Isolated browser smoke test. Serves fixtures; never loads the poker engine. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {chromium} = require('playwright');
const web = path.resolve(__dirname,'../web');
const out = process.env.UI_SCREENSHOT_DIR || path.resolve(__dirname,'../../../ui-checks');
fs.mkdirSync(out,{recursive:true});
const view = {
 schema:1,type:'decision',hand_no:24,stage:'flop',hash:'fixture',n_slots:9,hero_seat:1,button_seat:8,
 hero_hole:['As','Kh'],board:['Ah','7c','2d'],pot_total:2400,pot_center:1800,to_call:300,
 legal:{fold:true,check:false,call:300,raise:{kind:'raise',min_to:600,max_to:18000,allin_only:false}},
 level:{n:3,sb:100,bb:200,ante:200},field:{entries:180,remaining:126,itm:27,rank:42,tables:14},
 notes:[],log:[],prior_log:[],
 seats:Array.from({length:9},(_,i)=>({seat:i+1,pid:i*9,pos:['BB','UTG','UTG+1','MP','LJ','HJ','CO','BTN','SB'][i],stack:18000+i*1250,bet:i===2?600:0,in_hand:true,allin:false,hero:i===0}))
};
const response={token:'fixture-1',view};
const server=http.createServer((req,res)=>{
 const pathname=new URL(req.url,'http://localhost').pathname;
 if(pathname.startsWith('/api/')){
   res.setHeader('Content-Type','application/json');
   return res.end(JSON.stringify(pathname==='/api/memos'?{memos:{}}:response));
 }
 const name=['/','/play','/watch'].includes(pathname)?'index.html':pathname.slice(1);
 const file=path.join(web,name);
 if(!file.startsWith(web+path.sep) || !fs.existsSync(file)){res.statusCode=404;return res.end();}
 res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css','.png':'image/png'})[path.extname(file)]||'text/plain');
 fs.createReadStream(file).pipe(res);
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});
 const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',r=>{if(r.status()>=400)errors.push(r.url()+': '+r.status());});
 try {
 await page.goto('http://127.0.0.1:'+server.address().port+'/play');
 await page.waitForSelector('#bCall',{timeout:30000});
 assert.equal(await page.locator('#seats .pod').count(),8);
 assert.equal(await page.locator('.portrait').count(),9);
 assert.equal(await page.locator('.portrait-pupil').count(),18);
 assert.equal(await page.locator('.portrait').evaluateAll(els=>new Set(els.map(el=>el.dataset.portrait)).size),9,'hero and eight bots must be distinct');
 await page.waitForFunction(()=>[...document.images].every(i=>i.complete && i.naturalWidth>0));
 await page.screenshot({path:path.join(out,'9max-390.png')});
 const gaze = await page.evaluate(()=>{
   const t=document.querySelector('#felt').getBoundingClientRect();
   return [...document.querySelector('.portrait').parentNode.parentNode.parentNode.querySelectorAll('.portrait')].map(el=>{
     const r=el.getBoundingClientRect(),s=getComputedStyle(el);
     return {dx:t.x+t.width/2-r.x-r.width/2,dy:t.y+t.height/2-r.y-r.height/2,x:parseFloat(s.getPropertyValue('--gaze-x')),y:parseFloat(s.getPropertyValue('--gaze-y')),w:r.width};
   });
 });
 for(const p of gaze){assert.equal(Math.sign(p.x),Math.sign(p.dx));assert.equal(Math.sign(p.y),Math.sign(p.dy));assert.ok(Math.hypot(p.x,p.y)<=p.w*.029+.002);}
 const heroCards=await page.locator('#herocards').innerHTML();
 await page.setViewportSize({width:320,height:640});
 await page.waitForTimeout(150);
 assert.equal(await page.locator('#herocards').innerHTML(),heroCards,'resize must not rebuild dealt cards');
 await page.screenshot({path:path.join(out,'9max-320.png')});
 await page.click('#bRaise');
 await page.waitForTimeout(150);
 await page.screenshot({path:path.join(out,'9max-raise-320.png')});
 const confirm=await page.locator('#rok').boundingBox();
 assert.ok(confirm.y+confirm.height<=640,'raise confirmation fits viewport');
 await page.click('#rcancel');
 for(const n of [8,6,9]){
   await page.evaluate(n=>{const v={...S.view,n_slots:n,seats:S.view.seats.filter(s=>s.seat<=n)};renderSeats(v);},n);
   assert.equal(await page.locator('#seats .pod').count(),n-1);
 }
 assert.deepEqual(errors,[]);
 console.log('PASS: 9 seats, images, gaze directions, resize, hero card stability, raise controls, 8/6 compatibility; no browser errors');
 } finally {await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
