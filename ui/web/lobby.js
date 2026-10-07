'use strict';
const $ = (s) => document.querySelector(s);
let catalog = [], current = null, selected = null, wallet = null, filter = 'all';
let sending = false;
const fmt = n => Number(n || 0).toLocaleString('ko-KR');
const when = t => new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false
}).format(new Date(t * 1000));
const labels = {scheduled:'예정', late_registration:'레이트 등록', closed:'등록 마감', finished:'종료'};
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
async function loadLobby() {
  try {
    const r=await fetch('/api/lobby',{cache:'no-store',headers:headers(false)});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const data=await r.json(); catalog=data.tournaments || []; current=data.current;
    wallet=data.wallet; $('#walletBalance').textContent=fmt(wallet && wallet.balance);
    renderCurrent(); renderCards();
    if(selected) { selected=catalog.find(t=>t.id===selected.id); if(selected) paintJoin(); }
  } catch(e) { toast('로비 정보를 불러오지 못했습니다: '+e.message); }
}
function renderCurrent() {
  const box=$('#current');
  const mine=catalog.find(t=>t.active && t.my_entry);
  if(!mine) { box.hidden=true; return; }
  box.hidden=false;
  box.innerHTML='<div><div class="kicker">MY TOURNAMENT</div><h3>'+escapeHtml(mine.name)+
    '</h3><p>'+when(mine.starts_at)+' · '+(mine.my_entry.rank ? mine.my_entry.rank+'위' : labels[mine.status])+
    '</p></div><button id="resume" type="button">입장 / 결과</button>';
  $('#resume').onclick=()=>enter(mine);
}
function visible(t) {
  if(filter==='mine') return t.my_entry && t.my_entry.status !== 'cancelled';
  if(filter==='scheduled') return t.status==='scheduled';
  if(filter==='running') return ['late_registration','closed'].includes(t.status);
  return t.registration_open || (t.my_entry && t.my_entry.status !== 'cancelled');
}
function renderCards() {
  const items=catalog.filter(visible); const box=$('#tournaments');
  if(!items.length) { box.innerHTML='<div class="emptyState">해당 토너먼트가 없습니다.</div>'; return; }
  box.innerHTML=items.map(t=>'<article class="card" data-id="'+escapeHtml(t.id)+'">'+
    '<span class="tag">'+labels[t.status]+'</span><div class="startTime">'+when(t.starts_at)+
    '</div><h3>'+escapeHtml(t.name)+'</h3><div class="desc">'+
    (t.my_entry && t.my_entry.status!=='cancelled' ? '참가 #'+t.my_entry.entry_no+' · ' : '')+
    '등록 마감 '+when(t.closes_at)+'</div><div class="facts">'+
    '<div class="fact"><b>'+fmt(t.buyin)+' 칩</b><span>바이인</span></div>'+
    '<div class="fact"><b>'+fmt(t.prize_pool)+' 칩</b><span>현재 상금 풀</span></div>'+
    '<div class="fact"><b>'+t.remaining+' / '+t.entries+'명</b><span>잔여 / 엔트리</span></div>'+
    '<div class="fact"><b>9-MAX · '+t.level_minutes+'분</b><span>좌석 / 레벨</span></div>'+
    progressFacts(t)+
    '</div><div class="enter">'+(t.can_reenter ? '리바이인 가능 →' : '토너 정보 보기 →')+'</div></article>').join('');
  box.querySelectorAll('.card').forEach(el=>el.onclick=()=>openJoin(el.dataset.id));
}
function playClock(sec) {
  if(sec==null) return '-';
  const m=Math.floor(sec/60), h=Math.floor(m/60);
  return h ? h+'시간 '+(m%60)+'분' : m+'분';
}
// 진행 중인 대회의 공개 진행 정보(레벨·블라인드·평균 스택·진행 시간). 참가하지 않아도 보인다.
function progressFacts(t) {
  const p=t.progress;
  if(!p || t.status==='scheduled') return '';
  return '<div class="fact"><b>Lv '+p.level+' · '+fmt(p.sb)+'/'+fmt(p.bb)+'</b><span>레벨 / 블라인드</span></div>'+
    '<div class="fact"><b>'+fmt(p.avg_stack)+' ('+p.avg_bb+'bb)</b><span>평균 스택</span></div>'+
    '<div class="fact"><b>'+playClock(p.play_seconds)+'</b><span>진행 시간</span></div>'+
    '<div class="fact"><b>'+fmt(p.leader_stack)+'</b><span>칩 리더</span></div>';
}
function openJoin(id) {
  selected=catalog.find(t=>t.id===id); if(!selected) return;
  $('#joinHint').textContent=''; paintJoin(); $('#joinSheet').hidden=false;
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
  $('#join').textContent=t.can_reenter ? '리바이인 · '+fmt(t.buyin)+' 칩' : entered ?
    (t.status==='scheduled' ? '예약 대기실' : '입장 / 결과 확인') : '바이인 · '+fmt(t.buyin)+' 칩';
  $('#join').disabled=sending || (!entered && !t.registration_open);
  $('#cancelRegistration').hidden=!(e && e.status==='reserved' && t.status==='scheduled');
}
function closeJoin() { $('#joinSheet').hidden=true; selected=null; }
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
    closeJoin(); toast('예약했습니다. '+when(t.starts_at)+'에 대회가 시작됩니다.'); await loadLobby();
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
    $('#walletSheet').hidden=false;
  } catch(e) { toast(e.message); }
}
$('#tabs').querySelectorAll('button').forEach(b=>b.onclick=()=>{
  $('#tabs').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));
  filter=b.dataset.filter; renderCards(); });
$('#sheetClose').onclick=closeJoin;
$('#joinSheet').onclick=e=>{ if(e.target===$('#joinSheet')) closeJoin(); };
$('#join').onclick=join;
$('#cancelRegistration').onclick=cancelRegistration;
$('#walletNav').onclick=openWallet;
$('#walletClose').onclick=()=>$('#walletSheet').hidden=true;
$('#walletSheet').onclick=e=>{ if(e.target===$('#walletSheet')) $('#walletSheet').hidden=true; };
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
  $('#profileSheet').hidden=false;
}
function closeProfile(){ $('#profileSheet').hidden=true; }
function saveProfile(){
  const nick=(($('#nickname').value||'플레이어').trim().slice(0,16)||'플레이어');
  const dk=$('#deckChoices button.active');
  profileSet('nickname',nick);
  profileSet('deck',dk?dk.dataset.deck:'jade');
  const av=$('#avatarChoices button.active');
  profileSet('avatar',av?av.dataset.avatar:'0');
  applyDeckTheme(profileGet('deck','jade'));
  closeProfile();
  toast('프로필을 저장했습니다');
}
$('#profileNav').addEventListener('click',openProfile);
$('#profileClose').addEventListener('click',closeProfile);
$('#profileSheet').addEventListener('click',(e)=>{if(e.target===$('#profileSheet'))closeProfile();});
$('#profileSave').addEventListener('click',saveProfile);
$('#deckChoices').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{
  $('#deckChoices').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));
  applyDeckTheme(b.dataset.deck);
}));
applyDeckTheme(profileGet('deck','jade'));

loadLobby();
