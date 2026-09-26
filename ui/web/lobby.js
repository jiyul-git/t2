'use strict';

const $ = (s) => document.querySelector(s);
let catalog = [];
let current = null;
let selected = null;
let filter = 'all';

const META = {
  deep:{group:'speed',tag:'DEEP',desc:'깊은 스택으로 오래 싸우는 느린 구조'},
  standard:{group:'speed',tag:'CLASSIC',desc:'9-max 표준 구조. 균형 잡힌 기본 토너'},
  turbo:{group:'speed',tag:'TURBO',desc:'빠른 레벨과 리엔트리로 템포를 높인 구조'},
  hyper:{group:'speed',tag:'HYPER',desc:'짧은 스택과 초고속 레벨의 압축 토너'},
  lowbuyin:{group:'field',tag:'OPEN',desc:'넓은 참가층을 가정한 9-max 필드'},
  main:{group:'field',tag:'MAIN',desc:'딥한 9-max 메인이벤트 구조'},
  highroller:{group:'field',tag:'ELITE',desc:'강한 필드와 촘촘한 상금권의 하이롤러'},
  satellite:{group:'special',tag:'TICKET',desc:'상금 평탄도가 높은 생존 중심 위성전'},
  bounty:{group:'special',tag:'KO',desc:'녹아웃 성격을 반영한 공격적인 구조'}
};

function playKey(){
  try { return localStorage.getItem('t2_play_key') || ''; }
  catch(e){ return ''; }
}
function headers(json){
  const h = {};
  if(json) h['Content-Type']='application/json';
  const k=playKey();
  if(k) h['X-T2-Play-Key']=k;
  if(json) h['X-T2-Client-Mode']='play';
  return h;
}
const pct=(x)=>Math.round(Number(x||0)*100)+'%';
const fmt=(n)=>Number(n||0).toLocaleString('en-US');

function toast(msg){
  const t=$('#toast'); t.textContent=msg; t.hidden=false;
  clearTimeout(toast._t); toast._t=setTimeout(()=>t.hidden=true,2200);
}

async function loadLobby(){
  try{
    const r=await fetch('/api/lobby',{cache:'no-store',headers:headers(false)});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const data=await r.json();
    catalog=Array.isArray(data.tournaments)?data.tournaments:[];
    current=data.current||null;
    renderCurrent();
    renderCards();
    $('#joinHint').dataset.canPlay=data.can_play?'1':'0';
  }catch(e){
    $('#tournaments').innerHTML='<div class="emptyState">로비 정보를 불러오지 못했습니다.<br>'+String(e.message||e)+'</div>';
  }
}

function renderCurrent(){
  const box=$('#current');
  if(!current || current.error){ box.hidden=true; return; }
  box.hidden=false;
  const status=current.busted
    ? ('종료 · '+(current.rank?current.rank+'위':'결과 확인'))
    : ('HAND '+current.hand_no+' · '+current.remaining+'/'+current.entries+'명 · '+fmt(current.stack));
  box.innerHTML='<div><div class="kicker">IN PROGRESS</div><h3>'+escapeHtml(current.name||current.fmt)+'</h3>'+
    '<p>'+status+'</p></div><button id="resume" type="button">계속하기</button>';
  $('#resume').addEventListener('click',()=>location.href='/play');
}

function visible(t){
  if(filter==='all') return true;
  return (META[t.key]||{}).group===filter;
}

function renderCards(){
  const box=$('#tournaments');
  const items=catalog.filter(visible);
  if(!items.length){ box.innerHTML='<div class="emptyState">표시할 토너먼트가 없습니다.</div>'; return; }
  box.innerHTML=items.map((t,i)=>{
    const m=META[t.key]||{tag:'TOURNEY',desc:''};
    const featured=t.key==='main' || (filter==='all' && i===0 && t.key==='standard');
    return '<article class="card '+(featured?'featured':'')+'" data-key="'+escapeHtml(t.key)+'">'+
      '<span class="tag">'+m.tag+'</span><h3>'+escapeHtml(t.name)+'</h3>'+
      '<div class="desc">'+escapeHtml(m.desc)+'</div>'+
      '<div class="facts">'+
        '<div class="fact"><b>'+t.start_bb+' BB</b><span>START</span></div>'+
        '<div class="fact"><b>'+t.seats+'-MAX</b><span>TABLE</span></div>'+
        '<div class="fact"><b>'+t.hands_per_level+' HAND</b><span>LEVEL</span></div>'+
        '<div class="fact"><b>'+pct(t.itm_frac)+'</b><span>ITM</span></div>'+
      '</div><div class="enter">토너 정보 보기 →</div></article>';
  }).join('');
  box.querySelectorAll('.card').forEach(el=>el.addEventListener('click',()=>openJoin(el.dataset.key)));
}

function openJoin(key){
  selected=catalog.find(x=>x.key===key);
  if(!selected) return;
  const m=META[selected.key]||{desc:''};
  $('#joinTitle').innerHTML='<h2>'+escapeHtml(selected.name)+'</h2><p>'+escapeHtml(m.desc)+'</p>';
  $('#joinFacts').innerHTML=[
    selected.start_bb+' BB 시작',
    selected.seats+'-max',
    '레벨당 '+selected.hands_per_level+'핸드',
    'ITM '+pct(selected.itm_frac),
    selected.reentry?'리엔트리':'싱글 엔트리'
  ].map(x=>'<span>'+escapeHtml(x)+'</span>').join('');
  $('#joinHint').textContent='';
  $('#joinSheet').hidden=false;
}

function closeJoin(){ $('#joinSheet').hidden=true; selected=null; }

async function join(){
  if(!selected) return;
  const can=$('#joinHint').dataset.canPlay==='1' || !!playKey();
  if(!can){
    $('#joinHint').textContent='플레이 인증 후 참가할 수 있습니다.';
    return;
  }
  const entries=Math.max(2,Math.min(400,Number($('#entries').value)||100));
  const seedRaw=$('#seed').value.trim();
  const body={fmt:selected.key,entries};
  if(seedRaw!=='' && Number.isFinite(Number(seedRaw))) body.seed=Number(seedRaw);
  const btn=$('#join'); btn.disabled=true; btn.textContent='테이블 준비 중…';
  try{
    const r=await fetch('/api/new',{method:'POST',headers:headers(true),body:JSON.stringify(body)});
    let data=null; try{data=await r.json();}catch(e){}
    if(!r.ok) throw new Error((data&&data.error)||('HTTP '+r.status));
    location.href='/play';
  }catch(e){
    $('#joinHint').textContent=String(e.message||e);
    btn.disabled=false; btn.textContent='이 토너먼트 참가';
  }
}

function escapeHtml(v){
  return String(v==null?'':v).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

$('#tabs').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{
  $('#tabs').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));
  filter=b.dataset.filter; renderCards();
}));
$('#sheetClose').addEventListener('click',closeJoin);
$('#joinSheet').addEventListener('click',(e)=>{if(e.target===$('#joinSheet'))closeJoin();});
$('#join').addEventListener('click',join);
$('#quickEntries').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{
  $('#entries').value=b.dataset.n;
  $('#quickEntries').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));
}));
$('#entries').addEventListener('input',()=>$('#quickEntries').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x.dataset.n===$('#entries').value)));
$('#continueNav').addEventListener('click',()=>location.href='/play');


const PROFILE_KEYS = {
  nickname: 't2profile_nickname',
  deck: 't2profile_deck'
};
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
  $('#profileSpeed').value=storageGet('t2step','1500');
  $('#profileAuto').checked=storageGet('t2auto','1')!=='0';
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
  try {
    localStorage.setItem('t2step',$('#profileSpeed').value);
    localStorage.setItem('t2auto',$('#profileAuto').checked?'1':'0');
  } catch(e){}
  applyDeckTheme(profileGet('deck','jade'));
  closeProfile();
  toast('프로필을 저장했습니다');
}
$('#profileNav').addEventListener('click',openProfile);
$('#profileClose').addEventListener('click',closeProfile);
$('#profileSheet').addEventListener('click',(e)=>{if(e.target===$('#profileSheet'))closeProfile();});
$('#profileSave').addEventListener('click',saveProfile);
$('#profileHistory').addEventListener('click',()=>{location.href='/play#history';});
$('#deckChoices').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{
  $('#deckChoices').querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));
  applyDeckTheme(b.dataset.deck);
}));
applyDeckTheme(profileGet('deck','jade'));

loadLobby();
