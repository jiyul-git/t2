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
  syncModalLock();
}

function closeJoin(){
  $('#joinSheet').hidden=true;
  selected=null;
  syncModalLock();
}

async function join(){
  if(!selected){
    toast('먼저 참가할 토너먼트를 선택하세요');
    return;
  }
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
  avatarLegacy: 't2profile_avatar',
  avatarV2: 't2profile_avatar_v2',
  deck: 't2profile_deck',
  timeTheme: 't2profile_airport_theme'
};

const DECKS = {
  jade: {label:'비취'},
  navy: {label:'남청'},
  burgundy: {label:'자주'},
  ivory: {label:'백자'}
};
const SPEEDS = {
  '1000':'빠르게 · 1.0초',
  '1500':'보통 · 1.5초',
  '2000':'천천히 · 2.0초',
  '2600':'매우 천천히 · 2.6초'
};
const AVATAR_PARTS = [
  ['base','기본 캐릭터'],
  ['tone','피부·털 톤'],
  ['eyes','눈'],
  ['hair','헤어'],
  ['hat','모자'],
  ['beard','수염'],
  ['outfit','의상'],
  ['accessory','액세서리']
];

let profileDraft = null;
let pickerBackHandler = null;

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
function readAvatarProfile(){
  try {
    const raw=localStorage.getItem(PROFILE_KEYS.avatarV2);
    if(raw) return AvatarSystem.normalize(JSON.parse(raw));
  } catch(e){}
  // One-time migration from the old fixed 0..8 portrait selection.
  const legacy=Number(storageGet(PROFILE_KEYS.avatarLegacy,'0'))||0;
  return AvatarSystem.legacyPreset(legacy);
}
function storedProfile(){
  return {
    nickname: profileGet('nickname','플레이어'),
    avatar: readAvatarProfile(),
    deck: DECKS[profileGet('deck','jade')] ? profileGet('deck','jade') : 'jade',
    timeTheme: profileGet('timeTheme','night') === 'day' ? 'day' : 'night',
    speed: SPEEDS[storageGet('t2step','1500')] ? storageGet('t2step','1500') : '1500',
    auto: storageGet('t2auto','1') !== '0'
  };
}
function applyDeckTheme(deck){
  document.documentElement.dataset.deck = DECKS[deck] ? deck : 'jade';
}
function applyAirportTheme(theme){
  const v = theme === 'day' ? 'day' : 'night';
  document.documentElement.dataset.airportTheme = v;
  const meta = document.querySelector('meta[name="theme-color"]');
  if(meta) meta.setAttribute('content', v === 'day' ? '#edf1f4' : '#090e15');
}
function syncModalLock(){
  const open = Array.from(document.querySelectorAll('.sheetWrap'))
    .some((x)=>!x.hidden);
  document.documentElement.classList.toggle('modal-open',open);
  document.body.classList.toggle('modal-open',open);
}
function deckSample(deck, cls){
  return '<span class="'+(cls||'deckSample')+' '+escapeHtml(deck)+'"></span>';
}
function renderProfileSummary(){
  if(!profileDraft) return;
  $('#profilePreview').innerHTML=AvatarSystem.render(profileDraft.avatar);
  $('#avatarMini').innerHTML=AvatarSystem.render(profileDraft.avatar);
  $('#avatarValue').textContent=
    AvatarSystem.label('base',profileDraft.avatar.base)+' · 꾸미기';
  $('#themeValue').textContent=profileDraft.timeTheme==='day'?'낮':'밤';
  $('#deckValue').textContent=DECKS[profileDraft.deck].label;
  const dm=$('#deckMini');
  dm.className='deckMini '+profileDraft.deck;
  $('#speedValue').textContent=SPEEDS[profileDraft.speed];
  $('#profileAuto').checked=!!profileDraft.auto;
}
function openProfile(){
  profileDraft=storedProfile();
  $('#nickname').value=profileDraft.nickname;
  renderProfileSummary();
  $('#profileSheet').hidden=false;
  syncModalLock();
}
function closeProfile(){
  $('#profileSheet').hidden=true;
  $('#pickerSheet').hidden=true;
  profileDraft=null;
  const saved=storedProfile();
  applyAirportTheme(saved.timeTheme);
  applyDeckTheme(saved.deck);
  pickerBackHandler=null;
  syncModalLock();
}
function saveProfile(){
  if(!profileDraft) return;
  profileDraft.nickname=(($('#nickname').value||'플레이어').trim().slice(0,16)||'플레이어');
  profileDraft.auto=!!$('#profileAuto').checked;
  profileSet('nickname',profileDraft.nickname);
  try {
    localStorage.setItem(PROFILE_KEYS.avatarV2,JSON.stringify(AvatarSystem.normalize(profileDraft.avatar)));
  } catch(e){}
  profileSet('deck',profileDraft.deck);
  profileSet('timeTheme',profileDraft.timeTheme);
  try {
    localStorage.setItem('t2step',profileDraft.speed);
    localStorage.setItem('t2auto',profileDraft.auto?'1':'0');
  } catch(e){}
  applyAirportTheme(profileDraft.timeTheme);
  applyDeckTheme(profileDraft.deck);
  $('#profileSheet').hidden=true;
  $('#pickerSheet').hidden=true;
  profileDraft=null;
  pickerBackHandler=null;
  syncModalLock();
  toast('프로필을 저장했습니다');
}

function pickerOpen(title, html, backHandler){
  $('#pickerTitle').textContent=title;
  $('#pickerBody').innerHTML=html;
  pickerBackHandler=backHandler||null;
  $('#pickerSheet').hidden=false;
  syncModalLock();
}
function pickerClose(){
  $('#pickerSheet').hidden=true;
  pickerBackHandler=null;
  syncModalLock();
}
function avatarEditorHTML(){
  const a=profileDraft.avatar;
  const rows=AVATAR_PARTS.map(([part,title])=>
    '<button type="button" class="avatar-part-row" data-avatar-part="'+part+'">'+
    '<b>'+title+'</b><span>'+escapeHtml(AvatarSystem.label(part,a[part]))+' &nbsp;›</span></button>'
  ).join('');
  return '<div class="avatar-editor-preview">'+AvatarSystem.render(a)+'</div>'+
    '<div class="avatar-editor-list">'+rows+'</div>';
}
function openAvatarEditor(){
  pickerOpen('캐릭터 꾸미기',avatarEditorHTML(),null);
  $('#pickerBody').querySelectorAll('[data-avatar-part]').forEach(b=>
    b.addEventListener('click',()=>openAvatarPart(b.dataset.avatarPart))
  );
}
function openAvatarPart(part){
  const items=AvatarSystem.CATALOG[part]||[];
  const current=profileDraft.avatar[part];
  const html='<div class="part-grid">'+items.map(item=>{
    const cfg=AvatarSystem.normalize(Object.assign({},profileDraft.avatar,{[part]:item.id}));
    return '<button type="button" class="part-option '+(current===item.id?'active':'')+'" data-part-value="'+escapeHtml(item.id)+'">'+
      '<span class="part-avatar">'+AvatarSystem.render(cfg)+'</span><b>'+escapeHtml(item.label)+'</b></button>';
  }).join('')+'</div>';
  pickerOpen(AVATAR_PARTS.find(x=>x[0]===part)?.[1]||'캐릭터',html,openAvatarEditor);
  $('#pickerBody').querySelectorAll('[data-part-value]').forEach(b=>b.addEventListener('click',()=>{
    profileDraft.avatar=AvatarSystem.normalize(Object.assign({},profileDraft.avatar,{[part]:b.dataset.partValue}));
    renderProfileSummary();
    openAvatarEditor();
  }));
}
function themePreviewHTML(kind){
  return '<span class="themePreview '+kind+'"><i></i></span>';
}
function pickTheme(){
  const html='<div class="themePickerGrid">'+
    '<button type="button" class="themePickerOption '+(profileDraft.timeTheme==='day'?'active':'')+'" data-theme="day">'+
      themePreviewHTML('day')+'<b>낮</b><small>DAY TERMINAL · 자연광</small></button>'+
    '<button type="button" class="themePickerOption '+(profileDraft.timeTheme==='night'?'active':'')+'" data-theme="night">'+
      themePreviewHTML('night')+'<b>밤</b><small>NIGHT TERMINAL · 야간 조명</small></button>'+
    '</div>';
  pickerOpen('공항 테마',html,null);
  $('#pickerBody').querySelectorAll('[data-theme]').forEach(b=>b.addEventListener('click',()=>{
    profileDraft.timeTheme=b.dataset.theme;
    applyAirportTheme(profileDraft.timeTheme);
    renderProfileSummary();
    pickerClose();
  }));
}
function pickDeck(){
  const html='<div class="deckPickerGrid">'+
    Object.keys(DECKS).map(k=>
      '<button type="button" class="deckPickerOption '+(profileDraft.deck===k?'active':'')+'" data-deck="'+k+'">'+
      deckSample(k,'deckSample')+'<b>'+DECKS[k].label+'</b></button>'
    ).join('')+'</div>';
  pickerOpen('카드 뒷면',html,null);
  $('#pickerBody').querySelectorAll('[data-deck]').forEach(b=>b.addEventListener('click',()=>{
    profileDraft.deck=b.dataset.deck;
    applyDeckTheme(profileDraft.deck);
    renderProfileSummary();
    pickerClose();
  }));
}
function pickSpeed(){
  const html='<div class="pickerList">'+Object.keys(SPEEDS).map(k=>
    '<button type="button" class="pickerOption '+(profileDraft.speed===k?'active':'')+'" data-speed="'+k+'">'+
    '<span><b>'+SPEEDS[k]+'</b><small>봇 액션과 딜링 표시 간격</small></span><span class="check">✓</span></button>'
  ).join('')+'</div>';
  pickerOpen('게임 진행 속도',html,null);
  $('#pickerBody').querySelectorAll('[data-speed]').forEach(b=>b.addEventListener('click',()=>{
    profileDraft.speed=b.dataset.speed;
    renderProfileSummary();
    pickerClose();
  }));
}

$('#profileNav').addEventListener('click',openProfile);
$('#profileClose').addEventListener('click',closeProfile);
$('#profileSheet').addEventListener('click',(e)=>{if(e.target===$('#profileSheet'))closeProfile();});
$('#profileSave').addEventListener('click',saveProfile);
$('#profileAuto').addEventListener('change',()=>{if(profileDraft)profileDraft.auto=$('#profileAuto').checked;});
$('#profileHistory').addEventListener('click',()=>{location.href='/play#history';});
$('#pickAvatar').addEventListener('click',openAvatarEditor);
$('#pickTheme').addEventListener('click',pickTheme);
$('#pickDeck').addEventListener('click',pickDeck);
$('#pickSpeed').addEventListener('click',pickSpeed);
$('#pickerBack').addEventListener('click',()=>{
  if(pickerBackHandler){
    const fn=pickerBackHandler;
    pickerBackHandler=null;
    fn();
  } else {
    pickerClose();
  }
});
$('#pickerClose').addEventListener('click',pickerClose);
$('#pickerSheet').addEventListener('click',(e)=>{if(e.target===$('#pickerSheet'))pickerClose();});

const initialProfile=storedProfile();
applyDeckTheme(initialProfile.deck);
applyAirportTheme(initialProfile.timeTheme);

loadLobby();
