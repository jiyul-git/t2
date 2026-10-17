'use strict';
const $ = (s) => document.querySelector(s);
let catalog = [], current = null, selected = null, wallet = null, filter = 'all';
let sending = false;
const fmt = n => Number(n || 0).toLocaleString('ko-KR');
const when = t => new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false
}).format(new Date(t * 1000));
const labels = {scheduled:'시작 전', late_registration:'추가 등록 중', closed:'등록 마감', finished:'종료', retired:'내 대회 종료'};
function escapeHtml(v) { return String(v == null ? '' : v).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function playKey() { try { return localStorage.getItem('t2_play_key') || ''; } catch(e) { return ''; } }
function headers(json) {
  const h = {}; if(json) h['Content-Type'] = 'application/json';
  const k = playKey(); if(k) h['X-T2-Play-Key'] = k;
  if(json) h['X-T2-Client-Mode'] = 'play'; return h;
}
function toast(msg) { const t=$('#toast'); t.textContent=msg; t.hidden=false;
  clearTimeout(toast._t); toast._t=setTimeout(()=>t.hidden=true,3500); }
// Chip balance: count to a new value instead of jumping (skipped for reduced motion and the first fill).
const reduceMotion=window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function setBalance(v){
  const el=$('#walletBalance'), from=setBalance.v;
  setBalance.v=v;
  cancelAnimationFrame(setBalance.raf);
  if(typeof v!=='number' || typeof from!=='number' || from===v || reduceMotion){ el.textContent=fmt(v); return; }
  const t0=performance.now(), dur=650;
  const step=now=>{
    const k=Math.min(1,(now-t0)/dur), e=1-Math.pow(1-k,3);
    el.textContent=fmt(Math.round(from+(v-from)*e));
    if(k<1) setBalance.raf=requestAnimationFrame(step);
  };
  setBalance.raf=requestAnimationFrame(step);
}
// Sheets slide down when they close (the CSS plays .closing), and can be reopened mid-way.
function showSheet(el){ clearTimeout(el._closeT); el.classList.remove('closing'); el.hidden=false; }
function hideSheet(el){
  if(el.hidden) return;
  if(reduceMotion){ el.hidden=true; return; }
  el.classList.add('closing');
  clearTimeout(el._closeT);
  el._closeT=setTimeout(()=>{ el.classList.remove('closing'); el.hidden=true; },220);
}
async function loadLobby() {
  try {
    const r=await fetch('/api/lobby',{cache:'no-store',headers:headers(false)});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const data=await r.json(); catalog=data.tournaments || []; current=data.current;
    wallet=data.wallet; setBalance(wallet && wallet.balance);
    renderCurrent(); renderFeatured(); renderCards();
    window.T2Lounge && T2Lounge.setTournaments(catalog, data.server_now);
    if(selected) { selected=catalog.find(t=>t.id===selected.id); if(selected) paintJoin(); }
  } catch(e) { toast('로비 정보를 불러오지 못했습니다: '+e.message); }
}
function renderCurrent() {
  const box=$('#current');
  const mine=catalog.find(t=>t.active && t.my_entry && !['finished','retired'].includes(t.status));
  if(!mine) { box.hidden=true; return; }
  box.hidden=false;
  box.innerHTML='<div><div class="kicker">참가 중인 대회</div><h3>'+escapeHtml(mine.name)+
    '</h3><p>'+when(mine.starts_at)+' · '+(mine.my_entry.rank ? mine.my_entry.rank+'위' : labels[mine.status])+
    '</p></div><button id="resume" type="button">대회 입장 · 결과</button>';
  $('#resume').onclick=()=>enter(mine);
}
function renderFeatured() {
  const box=$('#featured');
  const list=catalog.filter(t=>!['finished','retired'].includes(t.status));
  const open=list.filter(t=>t.registration_open).sort((a,b)=>a.starts_at-b.starts_at);
  const next=list.filter(t=>t.status==='scheduled').sort((a,b)=>a.starts_at-b.starts_at);
  const t=open[0] || next[0];
  if(!t){ box.hidden=true; return; }
  box.hidden=false;
  $('#featuredLead').textContent=t.registration_open?'참가 가능':'시작 예정';
  $('#featuredStatus').textContent=labels[t.status]||'대회';
  $('#featuredName').textContent=t.name;
  $('#featuredWhen').textContent=when(t.starts_at)+' 시작';
  $('#featuredBuyin').textContent=fmt(t.buyin)+' 칩';
  box.dataset.fmt=eventFormat(t);
  $('#featuredCount').textContent=fmt(t.entries)+'명';
  $('#featuredJoin').textContent=t.registration_open?'참가 신청 ›':'대회 정보 ›';
  $('#featuredJoin').onclick=()=>openJoin(t.id);
}
function eventFormat(t){
  const fromRules=(t.fmt||t.format||(t.rules&&t.rules.fmt)||'').toLowerCase();
  const name=String(t.name||'');
  if(fromRules.includes('deep') || /딥스택/.test(name))return 'deepstack';
  if(fromRules.includes('hyper') || /하이퍼/.test(name))return 'hyper';
  if(fromRules.includes('turbo') || /터보/.test(name))return 'turbo';
  return 'standard';
}
function thumb(t){
  const fmt=eventFormat(t);
  return 'assets/t2-airport/card_'+fmt+'.webp';
}
function visible(t) {
  if(filter==='mine') return t.my_entry && t.my_entry.status!=='cancelled';
  if(['finished','retired'].includes(t.status)) return false;
  if(['standard','turbo','deepstack','hyper'].includes(filter) && eventFormat(t)!==filter)return false;
  return t.registration_open || (t.my_entry && t.my_entry.status!=='cancelled') || t.status==='scheduled';
}
function renderCards() {
  const items=catalog.filter(visible), box=$('#tournaments');
  if(!items.length){
    const empty='<div class="emptyState">조건에 맞는 대회가 없습니다.</div>';
    if(box._html!==empty){ box.innerHTML=empty; box._html=empty; }
    return;
  }
  const html=items.map(t=>'<article class="card" role="button" tabindex="0" data-id="'+escapeHtml(t.id)+
    '" aria-label="'+escapeHtml(t.name)+' 대회 상세보기">'+
    '<div class="card-illustration" aria-hidden="true"><img src="'+thumb(t)+'" alt="" loading="lazy"></div>'+
    '<div class="card-body"><div class="card-title-line"><h3>'+escapeHtml(t.name)+'</h3>'+
    '<span class="tag">'+escapeHtml(labels[t.status]||t.status)+'</span></div>'+
    '<div class="desc">'+(t.my_entry && t.my_entry.status!=='cancelled' ?
      '내 참가 #'+escapeHtml(t.my_entry.entry_no)+' · ' : '')+
    '등록 마감 '+when(t.closes_at)+'</div>'+
    '<div class="facts">'+
    '<div class="fact"><b>'+when(t.starts_at)+'</b><span>시작</span></div>'+
    '<div class="fact"><b>'+fmt(t.buyin)+' 칩</b><span>바이인</span></div>'+
    '<div class="fact"><b>'+fmt(t.entries)+'명</b><span>참가</span></div></div>'+
    '<div class="enter">'+(t.can_reenter?'재참가 가능':'자세히 보기')+' <span aria-hidden="true">›</span></div></div></article>').join('');
  // the lobby polls every few seconds: leave the cards alone unless something on them changed
  if(box._html===html) return;
  const first=box._html===undefined;
  box.innerHTML=html; box._html=html;
  if(first){ box.classList.add('intro'); setTimeout(()=>box.classList.remove('intro'),1200); }
  box.querySelectorAll('.card').forEach(el=>{
    const go=()=>openJoin(el.dataset.id);
    el.onclick=go;
    el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go();}};
  });
}
function playClock(sec) {
  if(sec==null) return '-';
  const m=Math.floor(sec/60), h=Math.floor(m/60);
  return h ? h+'시간 '+(m%60)+'분' : m+'분';
}
// 진행 중인 대회의 공개 진행 정보(레벨·블라인드·평균 스택·진행 시간). 참가하지 않아도 보인다.
function progressFacts(t) {
  const p=t.progress;
  if(!p || ['scheduled','retired'].includes(t.status)) return '';
  if(p.recovering) return '<div class="fact"><b>대회 상태 복구 중</b><span>복구가 끝나면 진행 정보가 표시됩니다</span></div>';
  return '<div class="fact"><b>Lv '+p.level+' · '+fmt(p.sb)+'/'+fmt(p.bb)+'</b><span>레벨 / 블라인드</span></div>'+
    '<div class="fact"><b>'+fmt(p.avg_stack)+' ('+p.avg_bb+'bb)</b><span>평균 스택</span></div>'+
    '<div class="fact"><b>'+playClock(p.play_seconds)+'</b><span>진행 시간</span></div>'+
    '<div class="fact"><b>'+fmt(p.leader_stack)+'</b><span>칩 리더</span></div>';
}
function openJoin(id) {
  selected=catalog.find(t=>t.id===id); if(!selected) return;
  $('#joinHint').textContent=''; paintJoin(); showSheet($('#joinSheet'));
}
function paintJoin() {
  const t=selected, e=t.my_entry;
  $('#joinTitle').innerHTML='<h2>'+escapeHtml(t.name)+'</h2><p>'+when(t.starts_at)+' 시작</p>';
  $('#joinFacts').innerHTML=[fmt(t.start_stack)+' 시작 스택','9-max','레벨 '+t.level_minutes+'분',
    '등록 마감 '+when(t.closes_at),'탈락 후 재참가 최대 '+t.max_reentries+'회',
    t.progress && t.status!=='scheduled' ? 'Lv '+t.progress.level+' · '+fmt(t.progress.sb)+'/'+fmt(t.progress.bb) : '',
    t.progress && t.status!=='scheduled' ? '평균 '+fmt(t.progress.avg_stack)+' ('+t.progress.avg_bb+'bb)' : '',
    t.progress && t.status!=='scheduled' ? '진행 '+playClock(t.progress.play_seconds) : '',
    e && e.rank ? '내 순위 '+e.rank+'위' : '',
    e && e.payout != null ? '지급 상금 '+fmt(e.payout)+' 칩' : ''].filter(Boolean)
    .map(x=>'<span>'+escapeHtml(x)+'</span>').join('');
  $('#joinCost').textContent='바이인 '+fmt(t.buyin)+' 칩 · 보유 '+fmt(wallet && wallet.balance)+' 칩';
  const entered=e && e.status!=='cancelled';
  $('#join').textContent=t.can_reenter ? '재참가 · '+fmt(t.buyin)+' 칩' : entered ?
    (t.status==='scheduled' ? '대회 대기실' : '대회 입장 · 결과 확인') : '참가 신청 · '+fmt(t.buyin)+' 칩';
  $('#join').disabled=sending || (!entered && !t.registration_open);
  $('#cancelRegistration').hidden=!(e && e.status==='reserved' && t.status==='scheduled');
}
function closeJoin() { hideSheet($('#joinSheet')); selected=null; }
async function post(path, body) {
  const r=await fetch(path,{method:'POST',headers:headers(true),body:JSON.stringify(body)});
  const data=await r.json(); if(!r.ok) throw new Error(data.error || 'HTTP '+r.status); return data;
}
async function enter(t) {
  try { await post('/api/enter',{tournament_id:t.id}); location.href='/play'; }
  catch(e) { toast(e.message); }
}
async function join() {
  if(!selected || sending) return;
  const t=selected, entered=t.my_entry && t.my_entry.status!=='cancelled';
  const path=t.can_reenter ? '/api/reenter' : entered ? '/api/enter' : '/api/register';
  sending=true; paintJoin();
  try {
    const r=await post(path,{tournament_id:t.id,entry_no:t.my_entry && t.my_entry.entry_no});
    if(!r.scheduled || path==='/api/enter') { location.href='/play'; return; }
    closeJoin(); toast('참가 신청이 완료됐습니다. 대회 시작: '+when(t.starts_at)); await loadLobby();
  } catch(e) { $('#joinHint').textContent=e.message; }
  finally { sending=false; if(selected) paintJoin(); }
}
async function cancelRegistration() {
  if(!selected || sending) return; sending=true;
  try { await post('/api/unregister',{tournament_id:selected.id,entry_no:selected.my_entry.entry_no});
    closeJoin(); toast('참가비를 환불했습니다.'); await loadLobby(); }
  catch(e) { $('#joinHint').textContent=e.message; } finally { sending=false; }
}
async function openWallet() {
  try {
    const r=await fetch('/api/wallet',{cache:'no-store'}); if(!r.ok) throw new Error('HTTP '+r.status);
    wallet=await r.json();
    const names={initial:'첫 지급',buyin:'바이인',reentry:'리바이인',refund:'예약 취소 환불',prize:'상금'};
    $('#walletDetail').innerHTML='<h3>보유 '+fmt(wallet.balance)+' 칩</h3>'+wallet.transactions.map(x=>
      '<div class="walletRow"><span>'+escapeHtml(names[x.kind] || x.kind)+'<small>'+when(x.created_at)+
      '</small></span><b>'+(x.delta>0?'+':'')+fmt(x.delta)+' 칩</b></div>').join('');
    showSheet($('#walletSheet'));
  } catch(e) { toast(e.message); }
}
function syncFilterTabs(){
  $('#tabs').querySelectorAll('button').forEach(x=>
    x.classList.toggle('active',x.dataset.filter===filter));
}
$('#tabs').querySelectorAll('button').forEach(b=>b.onclick=()=>{
  filter=b.dataset.filter; syncFilterTabs(); renderCards(); });
$('#sheetClose').onclick=closeJoin;
$('#joinSheet').onclick=e=>{ if(e.target===$('#joinSheet')) closeJoin(); };
$('#join').onclick=join;
$('#cancelRegistration').onclick=cancelRegistration;
$('#walletNav').onclick=openWallet;
$('#walletClose').onclick=()=>hideSheet($('#walletSheet'));
$('#walletSheet').onclick=e=>{ if(e.target===$('#walletSheet')) hideSheet($('#walletSheet')); };
setInterval(()=>{if(!document.hidden && !sending) loadLobby();},5000);

const PROFILE_KEYS = {
  nickname: 't2profile_nickname',
  deck: 't2profile_deck',
  avatar: 't2profile_avatar'      // 테이블의 내 캐릭터(visuals.js 가 HERO 자리에 쓴다)
};
const AVATARS = 9;
function avatarImg(i){ return '<img alt="" draggable="false" src="assets/portraits/'+String(i+1).padStart(2,'0')+'.png">'; }
function paintAvatars(sel){
  $('#avatarPreview').innerHTML=avatarImg(sel);
  $('#avatarChoices').innerHTML=Array.from({length:AVATARS},(_,i)=>
    '<button type="button" data-avatar="'+i+'"'+(i===sel?' class="active"':'')+'>'+avatarImg(i)+'</button>').join('');
  $('#avatarChoices').querySelectorAll('button').forEach(b=>b.onclick=()=>paintAvatars(Number(b.dataset.avatar)));
}
const DECKS = ['jade','navy','burgundy','ivory'];

function storageGet(key, fallback){
  try {
    const v=localStorage.getItem(key);
    return v===null ? fallback : v;
  } catch(e){ return fallback; }
}
function profileGet(key, fallback){
  return storageGet(PROFILE_KEYS[key], fallback);
}
function profileSet(key, value){
  try { localStorage.setItem(PROFILE_KEYS[key], String(value)); } catch(e){}
}
function applyDeckTheme(deck){
  document.documentElement.dataset.deck = DECKS.includes(deck) ? deck : 'jade';
}
function openProfile(){
  $('#nickname').value=profileGet('nickname','플레이어');
  const av=Number(profileGet('avatar','0'));
  paintAvatars(Number.isInteger(av) && av>=0 && av<AVATARS ? av : 0);
  const deck=profileGet('deck','jade');
  $('#deckChoices').querySelectorAll('button').forEach(b=>
    b.classList.toggle('active',b.dataset.deck===deck));
  showSheet($('#profileSheet'));
}
function closeProfile(){ hideSheet($('#profileSheet')); }
function saveProfile(){
  const nick=(($('#nickname').value||'플레이어').trim().slice(0,16)||'플레이어');
  const dk=$('#deckChoices button.active');
  profileSet('nickname',nick);
  profileSet('deck',dk?dk.dataset.deck:'jade');
  const av=$('#avatarChoices button.active');
  profileSet('avatar',av?av.dataset.avatar:'0');
  applyDeckTheme(profileGet('deck','jade'));
  closeProfile();
  pushProfile().then(ok=>toast(ok?'프로필을 저장했습니다':'이 기기에만 저장했습니다 (서버 연결 실패)'));
}
// The account's copy lives on the server; localStorage is the fast cache the table pages read.
function localProfile(){
  const av=Number(profileGet('avatar','0'));
  return {nickname:profileGet('nickname','플레이어'), deck:profileGet('deck','jade'),
          avatar:Number.isInteger(av)?av:0};
}
async function pushProfile(){
  try{ await post('/api/profile',{profile:localProfile()}); return true; }catch(e){ return false; }
}
async function syncProfile(){
  let server;
  try{
    const r=await fetch('/api/profile',{cache:'no-store',headers:headers(false)});
    if(!r.ok) return;
    server=(await r.json()).profile||{};
  }catch(e){ return; }
  if(Object.keys(server).length){
    for(const k of ['nickname','deck','avatar']) if(k in server) profileSet(k,server[k]);
    applyDeckTheme(profileGet('deck','jade'));
  }else{
    // first time on this account: keep what this browser already had
    let hasLocal=false;
    try{ hasLocal=['nickname','deck','avatar'].some(k=>localStorage.getItem(PROFILE_KEYS[k])!==null); }catch(e){}
    if(hasLocal) pushProfile();
  }
}
$('#profileNav').addEventListener('click',openProfile);
$('#headerProfileNav').addEventListener('click',openProfile);
$('#lobbyNav').addEventListener('click',()=>{filter='all';syncFilterTabs();renderCards();window.scrollTo({top:0,behavior:'smooth'});});
$('#eventsNav').addEventListener('click',()=>{filter='all';syncFilterTabs();renderCards();document.querySelector('.section').scrollIntoView({behavior:'smooth',block:'start'});});
$('#myEventsNav').addEventListener('click',()=>{filter='mine';syncFilterTabs();renderCards();document.querySelector('.section').scrollIntoView({behavior:'smooth',block:'start'});});
$('#profileClose').addEventListener('click',closeProfile);
$('#profileSheet').addEventListener('click',(e)=>{if(e.target===$('#profileSheet'))closeProfile();});
$('#profileSave').addEventListener('click',saveProfile);
$('#deckChoices').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{
  $('#deckChoices').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));
  applyDeckTheme(b.dataset.deck);
}));
applyDeckTheme(profileGet('deck','jade'));
syncProfile();

// Account block: only behind the online gateway, which answers /auth/me (plain Termux mode has no such endpoint).
async function initAccount(){
  let me;
  try{
    const r=await fetch('/auth/me',{cache:'no-store'});
    if(!r.ok) return;
    me=await r.json();
  }catch(e){ return; }
  if(!me || typeof me.email!=='string') return;
  $('#accountEmail').textContent=me.email;
  $('#accountBlock').hidden=false;
}
async function logout(){
  try{ await fetch('/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); }catch(e){}
  location.href='/login';
}
function openDelete(){
  $('#deleteConfirm').value=''; $('#deleteGo').disabled=true; $('#deleteErr').textContent='';
  closeProfile();
  showSheet($('#deleteSheet'));
}
function closeDelete(){ hideSheet($('#deleteSheet')); }
async function deleteAccount(){
  if($('#deleteConfirm').value.trim()!=='삭제') return;
  $('#deleteGo').disabled=true; $('#deleteErr').textContent='';
  try{
    const r=await fetch('/auth/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:'삭제'})});
    if(!r.ok){ const d=await r.json().catch(()=>({})); throw new Error(d.error||('삭제하지 못했습니다 ('+r.status+')')); }
  }catch(e){ $('#deleteErr').textContent=e.message; $('#deleteGo').disabled=false; return; }
  try{ Object.values(PROFILE_KEYS).forEach(k=>localStorage.removeItem(k)); }catch(e){}
  location.href='/login';
}
$('#logoutBtn').addEventListener('click',logout);
$('#deleteAccountBtn').addEventListener('click',openDelete);
$('#deleteClose').addEventListener('click',closeDelete);
$('#deleteSheet').addEventListener('click',(e)=>{if(e.target===$('#deleteSheet'))closeDelete();});
$('#deleteConfirm').addEventListener('input',()=>{$('#deleteGo').disabled=$('#deleteConfirm').value.trim()!=='삭제';});
$('#deleteGo').addEventListener('click',deleteAccount);
initAccount();

loadLobby();
