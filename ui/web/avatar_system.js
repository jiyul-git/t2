/* T2 layered avatar engine.
 * Visual target: the approved chibi portrait set in assets/portraits.png /
 * characters-500 style reference: rounded square heads, white rectangular eyes,
 * bold dark outlines, simple Korean-inspired clothing.
 * Cosmetics never consume gameplay RNG.
 */
(function(root){
  'use strict';

  const CATALOG={
    base:[
      {id:'human',label:'사람 (남)'},
      {id:'human_f',label:'사람 (여)'},
      {id:'tiger',label:'호랑이'},
      {id:'rabbit',label:'토끼'},
      {id:'turtle',label:'거북'},
      {id:'fox',label:'여우'},
      {id:'bear',label:'곰'},
      {id:'bird',label:'새'},
      {id:'frog',label:'두꺼비'},
      {id:'dog',label:'개'}
    ],
    tone:[
      {id:'light',label:'밝은 톤'},
      {id:'warm',label:'웜 톤'},
      {id:'tan',label:'탄 톤'},
      {id:'deep',label:'딥 톤'}
    ],
    eyes:[
      {id:'round',label:'기본 눈'},
      {id:'calm',label:'차분한 눈'},
      {id:'sharp',label:'날카로운 눈'},
      {id:'smile',label:'웃는 눈'}
    ],
    hair:[
      {id:'none',label:'없음'},
      {id:'short',label:'짧은 머리'},
      {id:'side',label:'사이드 파트'},
      {id:'bob',label:'단발'},
      {id:'bun',label:'묶은 머리'}
    ],
    hat:[
      {id:'none',label:'없음'},
      {id:'gat',label:'갓'},
      {id:'fedora',label:'페도라'},
      {id:'cap',label:'캡'},
      {id:'beanie',label:'비니'}
    ],
    beard:[
      {id:'none',label:'없음'},
      {id:'moustache',label:'콧수염'},
      {id:'goatee',label:'턱수염'},
      {id:'full',label:'풀 비어드'}
    ],
    outfit:[
      {id:'hanbok_teal',label:'청록 한복',pack:'seoul'},
      {id:'hanbok_burgundy',label:'자주 한복',pack:'seoul'},
      {id:'hanbok_blue',label:'남청 한복',pack:'seoul'},
      {id:'hanbok_cream',label:'백자 한복',pack:'seoul'},
      {id:'suit_navy',label:'네이비 수트',pack:'global'},
      {id:'jacket_cream',label:'크림 재킷',pack:'global'},
      {id:'hoodie_charcoal',label:'차콜 후디',pack:'global'}
    ],
    accessory:[
      {id:'none',label:'없음'},
      {id:'round_glasses',label:'원형 안경'},
      {id:'square_glasses',label:'사각 안경'},
      {id:'sunglasses',label:'선글라스'},
      {id:'flower',label:'꽃 장식'},
      {id:'earring',label:'귀걸이'}
    ]
  };

  const DEFAULT={
    base:'human',tone:'warm',eyes:'round',hair:'short',
    hat:'none',beard:'none',outfit:'hanbok_teal',accessory:'none'
  };

  const SKIN={
    light:{main:'#f7d7b5',shade:'#eebc91',nose:'#df8366'},
    warm:{main:'#efc493',shade:'#dfa877',nose:'#d9785c'},
    tan:{main:'#d39a6d',shade:'#b97c55',nose:'#bd684f'},
    deep:{main:'#93644a',shade:'#744735',nose:'#8e4f43'}
  };
  const FUR={
    tiger:{
      light:['#f4b35f','#ffe3b3','#6b3a22'],warm:['#e99a44','#ffe0ae','#62351f'],
      tan:['#d68437','#f6c993','#59301d'],deep:['#ad6330','#ddb07e','#43281c']
    },
    rabbit:{
      light:['#f8f2e7','#ffffff','#e8a7a0'],warm:['#eee2d0','#fff7eb','#dda19a'],
      tan:['#cdbb9d','#eee2cf','#c88b86'],deep:['#9b846c','#c8b49b','#a36f6a']
    },
    turtle:{
      light:['#a8ad72','#cad09b','#6f7449'],warm:['#919a5f','#b7bf83','#687044'],
      tan:['#77824e','#9eaa6d','#59633a'],deep:['#5f6942','#818c5b','#46502f']
    },
    fox:{
      light:['#ef9651','#fff0d2','#5d3526'],warm:['#df7c3c','#f8e4c5','#593125'],
      tan:['#c86532','#e9cda9','#4b2a20'],deep:['#9e4d2d','#c79f7e','#40241d']
    },
    bear:{
      light:['#a87755','#c99b75','#573b2b'],warm:['#865a3d','#b7855f','#4a3327'],
      tan:['#68462f','#966847','#3e2c22'],deep:['#4c3428','#73513d','#31231d']
    },
    bird:{
      light:['#4b5158','#ffffff','#32363b'],warm:['#383e45','#f5f0e8','#292e34'],
      tan:['#2e343b','#e3ddd4','#22272d'],deep:['#23282d','#cac3b8','#191d21']
    },
    frog:{
      light:['#b4ae72','#d7c994','#777149'],warm:['#9d9860','#c9bc83','#696441'],
      tan:['#817d4f','#aaa06d','#575337'],deep:['#66643f','#8a865a','#45442e']
    },
    dog:{
      light:['#f2dfbc','#fff3dc','#9a7656'],warm:['#d9bc8d','#f1ddbb','#876448'],
      tan:['#b58f65','#ddc299','#6f513b'],deep:['#806149','#b08d70','#563e31']
    }
  };

  const COMPAT={
    human:{hair:['none','short','side','bob','bun'],beard:['none','moustache','goatee','full'],hat:['none','gat','fedora','cap','beanie'],accessory:['none','round_glasses','square_glasses','sunglasses','flower','earring']},
    human_f:{hair:['none','short','side','bob','bun'],beard:['none'],hat:['none','gat','fedora','cap','beanie'],accessory:['none','round_glasses','square_glasses','sunglasses','flower','earring']},
    tiger:{hair:['none'],beard:['none'],hat:['none','fedora','cap','beanie'],accessory:['none','round_glasses','square_glasses','sunglasses','earring']},
    rabbit:{hair:['none'],beard:['none'],hat:['none','cap','beanie'],accessory:['none','round_glasses','square_glasses','sunglasses','flower','earring']},
    turtle:{hair:['none'],beard:['none'],hat:['none','fedora','cap','beanie'],accessory:['none','round_glasses','square_glasses','sunglasses']},
    fox:{hair:['none'],beard:['none'],hat:['none','fedora','cap','beanie'],accessory:['none','round_glasses','square_glasses','sunglasses','earring']},
    bear:{hair:['none'],beard:['none'],hat:['none','fedora','cap','beanie'],accessory:['none','round_glasses','square_glasses','sunglasses','earring']},
    bird:{hair:['none'],beard:['none'],hat:['none','cap','beanie'],accessory:['none','round_glasses','square_glasses','sunglasses']},
    frog:{hair:['none'],beard:['none'],hat:['none','fedora','cap','beanie'],accessory:['none','round_glasses','square_glasses','sunglasses']},
    dog:{hair:['none'],beard:['none'],hat:['none','fedora','cap','beanie'],accessory:['none','round_glasses','square_glasses','sunglasses','flower','earring']}
  };

  const LAYER_LAYOUT={
    human:{hat:{x:0,y:-3,s:1},accessory:{x:0,y:0,s:1}},
    human_f:{hat:{x:0,y:-3,s:1},accessory:{x:0,y:0,s:1}},
    tiger:{hat:{x:0,y:-4,s:.96},accessory:{x:0,y:2,s:1}},
    rabbit:{hat:{x:0,y:-24,s:.88},accessory:{x:0,y:4,s:.98}},
    turtle:{hat:{x:0,y:2,s:.96},accessory:{x:0,y:5,s:.97}},
    fox:{hat:{x:0,y:-8,s:.94},accessory:{x:0,y:2,s:1}},
    bear:{hat:{x:0,y:-4,s:.96},accessory:{x:0,y:3,s:1}},
    bird:{hat:{x:0,y:-4,s:.94},accessory:{x:0,y:4,s:.96}},
    frog:{hat:{x:0,y:0,s:.96},accessory:{x:0,y:5,s:.96}},
    dog:{hat:{x:0,y:-7,s:.94},accessory:{x:0,y:3,s:1}}
  };

  function clone(x){return JSON.parse(JSON.stringify(x));}
  function has(part,id){return (CATALOG[part]||[]).some(x=>x.id===id);}
  function allowed(base,part,id){
    const b=COMPAT[base]||COMPAT.human;
    return !b[part]||b[part].indexOf(id)>=0;
  }
  function optionsFor(base,part){return (CATALOG[part]||[]).filter(x=>allowed(base,part,x.id));}
  function normalize(raw){
    const o=Object.assign({},DEFAULT,raw||{});
    Object.keys(DEFAULT).forEach(k=>{if(!has(k,o[k]))o[k]=DEFAULT[k];});
    ['hair','beard','hat','accessory'].forEach(part=>{
      if(!allowed(o.base,part,o[part])){
        const v=optionsFor(o.base,part)[0]; o[part]=v?v.id:'none';
      }
    });
    return o;
  }
  function label(part,id){const x=(CATALOG[part]||[]).find(v=>v.id===id);return x?x.label:id;}
  function hash32(v){const s=String(v);let h=2166136261>>>0;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return h>>>0;}
  function pick(arr,h,shift){return arr[(h>>>shift)%arr.length].id;}
  function esc(v){return String(v).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
  function skin(c){return SKIN[c.tone]||SKIN.warm;}
  function fur(c){return (FUR[c.base]||FUR.fox)[c.tone]||(FUR[c.base]||FUR.fox).warm;}
  function human(c){return c.base==='human'||c.base==='human_f';}

  function botConfig(pid){
    const h=hash32('bot:'+pid);
    const cfg={
      base:pick(CATALOG.base,h,0),tone:pick(CATALOG.tone,h,4),eyes:pick(CATALOG.eyes,h,6),
      hair:pick(CATALOG.hair,h,8),hat:pick(CATALOG.hat,h,11),beard:pick(CATALOG.beard,h,14),
      outfit:pick(CATALOG.outfit,h,17),accessory:pick(CATALOG.accessory,h,21)
    };
    if(cfg.hat!=='none'&&(h&4)===0)cfg.hair='none';
    return normalize(cfg);
  }

  function legacyPreset(n){
    const p=[
      {base:'human',tone:'warm',eyes:'round',hair:'short',hat:'gat',outfit:'hanbok_teal'},
      {base:'human_f',tone:'light',eyes:'calm',hair:'bun',accessory:'flower',outfit:'hanbok_cream'},
      {base:'human',tone:'tan',eyes:'sharp',hair:'short',beard:'goatee',outfit:'hanbok_blue'},
      {base:'tiger',tone:'warm',eyes:'round',outfit:'hanbok_teal'},
      {base:'rabbit',tone:'light',eyes:'calm',outfit:'hanbok_burgundy'},
      {base:'turtle',tone:'warm',eyes:'round',outfit:'hanbok_blue'},
      {base:'bear',tone:'warm',eyes:'sharp',outfit:'hanbok_teal'},
      {base:'fox',tone:'warm',eyes:'round',outfit:'hanbok_burgundy'},
      {base:'dog',tone:'light',eyes:'round',outfit:'hanbok_blue'}
    ];
    return normalize(p[Math.max(0,Math.min(8,Number(n)||0))]);
  }

  function outfitPalette(id){
    return {
      hanbok_teal:['#557763','#efe4cf','#5a3027'],
      hanbok_burgundy:['#8e493f','#f3e2c8','#682d28'],
      hanbok_blue:['#52657a','#f1e5d1','#313a4b'],
      hanbok_cream:['#d8b576','#fff4df','#5e5c39'],
      suit_navy:['#34465e','#f4f1ea','#713840'],
      jacket_cream:['#d9cdb8','#ffffff','#665a4e'],
      hoodie_charcoal:['#55585c','#6a6e73','#d1d1ce']
    }[id]||['#557763','#efe4cf','#5a3027'];
  }

  function body(c){
    const p=outfitPalette(c.outfit), isHan=c.outfit.indexOf('hanbok_')===0;
    if(isHan){
      return '<path d="M76 178 Q95 164 120 165 Q145 164 164 178 L176 238 Q149 250 120 250 Q91 250 64 238Z" fill="'+p[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<path d="M95 169 L120 194 L145 169 L154 181 L128 207 L112 207 L86 181Z" fill="'+p[1]+'" stroke="#2b2928" stroke-width="3"/>'+
        '<path d="M67 196 Q52 202 55 220 Q58 236 78 226 L83 207Z" fill="'+p[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<path d="M173 196 Q188 202 185 220 Q182 236 162 226 L157 207Z" fill="'+p[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<rect x="78" y="209" width="84" height="11" rx="4" fill="'+p[2]+'" stroke="#252322" stroke-width="3"/>'+
        '<path d="M119 216 L119 251 M125 216 L125 251" stroke="'+p[2]+'" stroke-width="5"/>';
    }
    if(c.outfit==='suit_navy'){
      return '<path d="M70 180 Q94 164 120 164 Q146 164 170 180 L174 244 Q146 252 120 252 Q94 252 66 244Z" fill="'+p[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<path d="M92 169 L120 193 L148 169 L137 214 L103 214Z" fill="'+p[1]+'" stroke="#2b2928" stroke-width="3"/>'+
        '<path d="M116 193 L124 193 L129 224 L120 233 L111 224Z" fill="'+p[2]+'"/>';
    }
    if(c.outfit==='hoodie_charcoal'){
      return '<path d="M66 186 Q86 161 120 161 Q154 161 174 186 L177 245 Q148 253 120 253 Q92 253 63 245Z" fill="'+p[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<path d="M81 182 Q120 213 159 182" fill="none" stroke="'+p[1]+'" stroke-width="10"/>'+
        '<path d="M113 202 L109 233 M127 202 L131 233" stroke="'+p[2]+'" stroke-width="3"/>';
    }
    return '<path d="M68 181 Q92 164 120 164 Q148 164 172 181 L177 245 Q148 253 120 253 Q92 253 63 245Z" fill="'+p[0]+'" stroke="#262525" stroke-width="5"/>'+
      '<path d="M93 170 L120 193 L147 170 L137 211 L103 211Z" fill="'+p[1]+'" stroke="#2b2928" stroke-width="3"/>';
  }

  function limbs(c){
    const col=human(c)?skin(c).main:fur(c)[0];
    return '<ellipse cx="62" cy="221" rx="11" ry="14" fill="'+col+'" stroke="#262525" stroke-width="4"/>'+
      '<ellipse cx="178" cy="221" rx="11" ry="14" fill="'+col+'" stroke="#262525" stroke-width="4"/>'+
      '<ellipse cx="94" cy="252" rx="16" ry="8" fill="'+col+'" stroke="#262525" stroke-width="4"/>'+
      '<ellipse cx="146" cy="252" rx="16" ry="8" fill="'+col+'" stroke="#262525" stroke-width="4"/>';
  }

  function faceBase(c){
    if(human(c)){
      const p=skin(c);
      return limbs(c)+
        '<circle cx="62" cy="116" r="15" fill="'+p.main+'" stroke="#262525" stroke-width="5"/>'+
        '<circle cx="178" cy="116" r="15" fill="'+p.main+'" stroke="#262525" stroke-width="5"/>'+
        '<path d="M61 111 Q63 65 120 58 Q177 65 179 111 L175 137 Q163 164 120 169 Q77 164 65 137Z" fill="'+p.main+'" stroke="#262525" stroke-width="5"/>'+
        '<ellipse cx="120" cy="137" rx="8" ry="6" fill="'+p.nose+'"/>';
    }
    const f=fur(c);
    if(c.base==='tiger'){
      return limbs(c)+
        '<circle cx="74" cy="71" r="23" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/><circle cx="166" cy="71" r="23" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<path d="M55 111 Q58 70 92 58 Q120 47 148 58 Q182 70 185 111 L177 143 Q160 166 120 169 Q80 166 63 143Z" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<path d="M69 125 Q120 162 171 125 Q161 166 120 171 Q79 166 69 125Z" fill="'+f[1]+'"/>'+
        '<path d="M88 63 L99 86 M120 56 L120 84 M152 63 L141 86" stroke="'+f[2]+'" stroke-width="7" stroke-linecap="round"/>'+
        '<path d="M62 105 L84 111 M178 105 L156 111" stroke="'+f[2]+'" stroke-width="7" stroke-linecap="round"/>'+
        '<ellipse cx="120" cy="139" rx="10" ry="7" fill="'+f[2]+'"/>';
    }
    if(c.base==='rabbit'){
      return limbs(c)+
        '<ellipse cx="88" cy="55" rx="17" ry="47" fill="'+f[0]+'" stroke="#262525" stroke-width="5" transform="rotate(-6 88 55)"/>'+
        '<ellipse cx="152" cy="55" rx="17" ry="47" fill="'+f[0]+'" stroke="#262525" stroke-width="5" transform="rotate(6 152 55)"/>'+
        '<ellipse cx="88" cy="55" rx="7" ry="34" fill="'+f[2]+'" transform="rotate(-6 88 55)"/><ellipse cx="152" cy="55" rx="7" ry="34" fill="'+f[2]+'" transform="rotate(6 152 55)"/>'+
        '<path d="M57 111 Q61 70 93 61 Q120 53 147 61 Q179 70 183 111 L176 143 Q157 166 120 169 Q83 166 64 143Z" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<ellipse cx="120" cy="139" rx="7" ry="5" fill="'+f[2]+'"/>';
    }
    if(c.base==='turtle'){
      return limbs(c)+
        '<path d="M51 115 Q54 68 120 57 Q186 68 189 115 L183 143 Q163 166 120 169 Q77 166 57 143Z" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<g fill="'+f[2]+'" opacity=".48"><circle cx="83" cy="78" r="5"/><circle cx="101" cy="67" r="4"/><circle cx="123" cy="66" r="5"/><circle cx="145" cy="72" r="4"/><circle cx="161" cy="83" r="5"/></g>';
    }
    if(c.base==='fox'){
      return limbs(c)+
        '<path d="M61 97 L78 40 L105 70 Q120 62 135 70 L162 40 L179 97" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<path d="M57 111 Q62 72 94 61 Q120 53 146 61 Q178 72 183 111 L174 143 Q158 165 120 169 Q82 165 66 143Z" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<path d="M67 128 Q120 164 173 128 Q159 169 120 172 Q81 169 67 128Z" fill="'+f[1]+'"/>'+
        '<ellipse cx="120" cy="139" rx="10" ry="7" fill="'+f[2]+'"/>'+
        '<path d="M166 224 Q205 210 200 178 Q228 208 204 241 Q186 259 164 247Z" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/><path d="M198 205 Q214 217 202 239 Q191 249 181 246 Q196 230 198 205Z" fill="'+f[1]+'"/>';
    }
    if(c.base==='bear'){
      return limbs(c)+
        '<circle cx="72" cy="74" r="25" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/><circle cx="168" cy="74" r="25" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<path d="M54 111 Q58 68 120 57 Q182 68 186 111 L180 143 Q161 167 120 170 Q79 167 60 143Z" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<ellipse cx="120" cy="140" rx="27" ry="20" fill="'+f[1]+'"/><ellipse cx="120" cy="133" rx="9" ry="7" fill="'+f[2]+'"/>';
    }
    if(c.base==='bird'){
      return limbs(c)+
        '<path d="M56 111 Q60 68 120 57 Q180 68 184 111 L178 143 Q159 166 120 169 Q81 166 62 143Z" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<path d="M60 118 Q83 151 120 158 Q157 151 180 118 Q166 160 120 170 Q74 160 60 118Z" fill="'+f[1]+'"/>'+
        '<path d="M108 137 L120 128 L132 137 L120 145Z" fill="#8e8176" stroke="#262525" stroke-width="4"/>';
    }
    if(c.base==='frog'){
      return limbs(c)+
        '<circle cx="78" cy="76" r="23" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/><circle cx="162" cy="76" r="23" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<path d="M49 113 Q52 78 82 65 Q120 50 158 65 Q188 78 191 113 L183 145 Q158 169 120 171 Q82 169 57 145Z" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/>'+
        '<path d="M69 145 Q120 159 171 145 Q156 171 120 174 Q84 171 69 145Z" fill="'+f[1]+'" opacity=".85"/>';
    }
    // dog
    return limbs(c)+
      '<path d="M63 80 Q42 42 59 32 Q86 45 94 70 M177 80 Q198 42 181 32 Q154 45 146 70" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/>'+
      '<path d="M55 111 Q59 70 93 59 Q120 51 147 59 Q181 70 185 111 L178 143 Q159 167 120 170 Q81 167 62 143Z" fill="'+f[0]+'" stroke="#262525" stroke-width="5"/>'+
      '<ellipse cx="120" cy="141" rx="25" ry="18" fill="'+f[1]+'"/><ellipse cx="120" cy="134" rx="9" ry="7" fill="'+f[2]+'"/>';
  }

  function eyes(c){
    if(c.eyes==='smile'){
      return '<path d="M78 112 Q94 124 108 111 M132 111 Q146 124 162 112" fill="none" stroke="#262525" stroke-width="6" stroke-linecap="round"/>'+
        '<path d="M83 95 Q95 89 106 96 M134 96 Q145 89 157 95" fill="none" stroke="#262525" stroke-width="4" stroke-linecap="round"/>';
    }
    let y=101,h=28;
    if(c.eyes==='calm'){y=105;h=23;}
    const skew=c.eyes==='sharp'?' transform="skewX(-5)"':'';
    return '<g'+skew+'>'+
      '<rect x="73" y="'+y+'" width="42" height="'+h+'" rx="9" fill="#fffdf8" stroke="#262525" stroke-width="5"/>'+
      '<rect x="125" y="'+y+'" width="42" height="'+h+'" rx="9" fill="#fffdf8" stroke="#262525" stroke-width="5"/>'+
      '<circle cx="96" cy="'+(y+h/2+1)+'" r="8" fill="#171717"/><circle cx="144" cy="'+(y+h/2+1)+'" r="8" fill="#171717"/>'+
      '<circle cx="99" cy="'+(y+h/2-2)+'" r="2.3" fill="#fff"/><circle cx="147" cy="'+(y+h/2-2)+'" r="2.3" fill="#fff"/></g>'+
      '<path d="M80 91 Q94 86 106 91 M134 91 Q147 86 160 91" fill="none" stroke="#262525" stroke-width="'+(c.eyes==='sharp'?5:4)+'" stroke-linecap="round"/>';
  }

  function mouth(c){
    if(c.base==='bird')return '';
    if(c.base==='frog')return '<path d="M100 145 Q120 151 140 145" fill="none" stroke="#262525" stroke-width="4" stroke-linecap="round"/>';
    if(human(c))return '<path d="M111 148 Q120 154 129 148" fill="none" stroke="#633b36" stroke-width="3.5" stroke-linecap="round"/>';
    return '<path d="M108 151 Q120 158 132 151" fill="none" stroke="#262525" stroke-width="3.5" stroke-linecap="round"/>';
  }

  function hair(c){
    if(c.hair==='none'||!human(c))return '';
    const col=c.tone==='deep'?'#241d1a':'#352823';
    if(c.hair==='bun')return '<circle cx="157" cy="62" r="25" fill="'+col+'" stroke="#262525" stroke-width="5"/><path d="M58 103 Q60 56 120 50 Q180 56 182 103 Q158 76 120 79 Q82 76 58 103Z" fill="'+col+'" stroke="#262525" stroke-width="5"/><path d="M70 83 Q88 62 105 59" fill="none" stroke="#4f3b33" stroke-width="4"/>';
    if(c.hair==='bob')return '<path d="M54 111 Q55 54 120 49 Q185 54 186 111 L173 151 Q161 132 162 86 Q120 68 78 86 Q79 132 67 151Z" fill="'+col+'" stroke="#262525" stroke-width="5"/>';
    if(c.hair==='side')return '<path d="M58 100 Q63 53 119 49 Q168 49 181 92 Q144 72 113 79 Q86 85 58 100Z" fill="'+col+'" stroke="#262525" stroke-width="5"/>';
    return '<path d="M59 99 Q65 52 120 49 Q175 52 181 99 Q149 76 120 80 Q91 76 59 99Z" fill="'+col+'" stroke="#262525" stroke-width="5"/><path d="M83 74 L89 99 M105 66 L108 91" stroke="#1f1a18" stroke-width="5" stroke-linecap="round"/>';
  }

  function beard(c){
    if(c.beard==='none'||!human(c))return '';
    const col='#352823';
    if(c.beard==='moustache')return '<path d="M117 141 Q104 132 92 142 Q105 152 119 147 Q133 152 148 142 Q136 132 123 141Z" fill="'+col+'"/>';
    if(c.beard==='goatee')return '<path d="M110 148 Q120 154 130 148 L127 173 Q120 181 113 173Z" fill="'+col+'" stroke="#262525" stroke-width="3"/>';
    return '<path d="M77 142 Q83 177 120 181 Q157 177 163 142 Q146 163 120 165 Q94 163 77 142Z" fill="'+col+'" stroke="#262525" stroke-width="3"/>';
  }

  function hat(c){
    if(c.hat==='none')return '';
    if(c.hat==='gat')return '<ellipse cx="120" cy="69" rx="88" ry="16" fill="#272524" stroke="#151515" stroke-width="5"/><path d="M88 66 L94 18 Q120 10 146 18 L152 66Z" fill="#2e2b2a" stroke="#151515" stroke-width="5"/><path d="M101 23 Q120 18 139 23" fill="none" stroke="#4a4542" stroke-width="3"/>';
    if(c.hat==='fedora')return '<ellipse cx="120" cy="67" rx="69" ry="14" fill="#2f2d2c" stroke="#1b1a19" stroke-width="4"/><path d="M82 62 Q87 28 120 27 Q153 28 158 62Z" fill="#3d3937" stroke="#1d1c1b" stroke-width="5"/><rect x="89" y="52" width="62" height="9" rx="3" fill="#252424"/>';
    if(c.hat==='cap')return '<path d="M65 68 Q78 31 121 31 Q158 33 171 68Z" fill="#40546b" stroke="#24292e" stroke-width="5"/><path d="M119 66 Q164 62 187 76 Q149 83 114 76Z" fill="#33465c" stroke="#24292e" stroke-width="4"/>';
    return '<path d="M72 70 Q77 27 120 26 Q163 27 168 70Z" fill="#66605d" stroke="#282625" stroke-width="5"/><rect x="71" y="59" width="98" height="20" rx="8" fill="#514b49" stroke="#282625" stroke-width="4"/>';
  }

  function accessory(c){
    if(c.accessory==='none')return '';
    if(c.accessory==='round_glasses')return '<g fill="none" stroke="#35383c" stroke-width="4"><circle cx="94" cy="116" r="22"/><circle cx="146" cy="116" r="22"/><path d="M116 115 L124 115 M72 112 L58 107 M168 112 L182 107"/></g>';
    if(c.accessory==='square_glasses')return '<g fill="none" stroke="#35383c" stroke-width="4"><rect x="70" y="96" width="47" height="38" rx="9"/><rect x="123" y="96" width="47" height="38" rx="9"/><path d="M117 113 L123 113"/></g>';
    if(c.accessory==='sunglasses')return '<g fill="#1f252c" stroke="#11161a" stroke-width="4"><rect x="69" y="98" width="48" height="34" rx="9"/><rect x="123" y="98" width="48" height="34" rx="9"/></g><path d="M117 110 L123 110" stroke="#11161a" stroke-width="5"/>';
    if(c.accessory==='flower')return '<g transform="translate(171 77)"><circle r="8" fill="#c95c64"/><circle cx="10" r="8" fill="#e07980"/><circle cx="5" cy="-9" r="8" fill="#e99499"/><circle cx="5" cy="8" r="8" fill="#bd4d57"/><circle cx="5" fill="#e7d29a" r="4"/></g>';
    return '<circle cx="181" cy="142" r="6" fill="#d7b25e" stroke="#6b5222" stroke-width="2"/>';
  }

  function layerLayout(base,layer){
    const d={x:0,y:0,s:1},b=LAYER_LAYOUT[base]||{};
    return Object.assign({},d,b[layer]||{});
  }
  function layerTransform(base,layer){
    const a=layerLayout(base,layer),s=Number(a.s||1),x=Number(a.x||0),y=Number(a.y||0);
    return 'translate('+(x+120*(1-s))+' '+(y+140*(1-s))+') scale('+s+')';
  }
  function layerGroup(base,layer,html){return '<g data-layer="'+layer+'" transform="'+layerTransform(base,layer)+'">'+html+'</g>';}

  function render(raw,opts){
    const c=normalize(raw),o=opts||{},title=o.title?'<title>'+esc(o.title)+'</title>':'';
    return '<span class="layer-avatar" data-base="'+esc(c.base)+'">'+
      '<svg viewBox="0 0 240 280" role="img" aria-hidden="'+(o.decorative!==false?'true':'false')+'" preserveAspectRatio="xMidYMid meet">'+title+
      '<g opacity=".12"><ellipse cx="120" cy="258" rx="55" ry="8" fill="#000"/></g>'+
      layerGroup(c.base,'outfit',body(c))+
      layerGroup(c.base,'base',faceBase(c))+
      layerGroup(c.base,'hair',hair(c))+
      layerGroup(c.base,'eyes',eyes(c))+
      layerGroup(c.base,'mouth',mouth(c))+
      layerGroup(c.base,'beard',beard(c))+
      layerGroup(c.base,'hat',hat(c))+
      layerGroup(c.base,'accessory',accessory(c))+
      '</svg></span>';
  }

  const api={CATALOG,DEFAULT,COMPAT,LAYER_LAYOUT,allowed,optionsFor,layerLayout,normalize,label,botConfig,legacyPreset,render,clone};
  root.AvatarSystem=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
