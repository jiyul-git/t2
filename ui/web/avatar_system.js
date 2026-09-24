/* Layered avatar engine shared by hero profile and bots.
 * One config -> one SVG. No gameplay RNG is touched.
 * New country/city packs extend CATALOG; renderer contract stays the same.
 */
(function(root){
  'use strict';

  const CATALOG = {
    base: [
      {id:'human', label:'사람'},
      {id:'fox', label:'여우'},
      {id:'rabbit', label:'토끼'},
      {id:'bear', label:'곰'},
      {id:'turtle', label:'거북'}
    ],
    tone: [
      {id:'light', label:'밝은 톤'},
      {id:'warm', label:'웜 톤'},
      {id:'tan', label:'탄 톤'},
      {id:'deep', label:'딥 톤'}
    ],
    eyes: [
      {id:'round', label:'동그란 눈'},
      {id:'calm', label:'차분한 눈'},
      {id:'sharp', label:'날카로운 눈'},
      {id:'smile', label:'웃는 눈'}
    ],
    hair: [
      {id:'none', label:'없음'},
      {id:'short', label:'짧은 머리'},
      {id:'side', label:'사이드 파트'},
      {id:'bob', label:'단발'},
      {id:'bun', label:'묶은 머리'}
    ],
    hat: [
      {id:'none', label:'없음'},
      {id:'gat', label:'갓'},
      {id:'fedora', label:'페도라'},
      {id:'cap', label:'캡'},
      {id:'beanie', label:'비니'}
    ],
    beard: [
      {id:'none', label:'없음'},
      {id:'moustache', label:'콧수염'},
      {id:'goatee', label:'턱수염'},
      {id:'full', label:'풀 비어드'}
    ],
    outfit: [
      {id:'hanbok_teal', label:'청록 한복', pack:'seoul'},
      {id:'hanbok_burgundy', label:'자주 한복', pack:'seoul'},
      {id:'suit_navy', label:'네이비 수트', pack:'global'},
      {id:'jacket_cream', label:'크림 재킷', pack:'global'},
      {id:'hoodie_charcoal', label:'차콜 후디', pack:'global'}
    ],
    accessory: [
      {id:'none', label:'없음'},
      {id:'round_glasses', label:'원형 안경'},
      {id:'square_glasses', label:'사각 안경'},
      {id:'sunglasses', label:'선글라스'},
      {id:'flower', label:'꽃 장식'},
      {id:'earring', label:'귀걸이'}
    ]
  };

  const DEFAULT = {
    base:'human', tone:'warm', eyes:'round', hair:'short',
    hat:'none', beard:'none', outfit:'hanbok_teal', accessory:'none'
  };

  const PALETTE = {
    light:{skin:'#f6d8bf', shadow:'#e7b99a'},
    warm:{skin:'#eec3a2', shadow:'#d89b78'},
    tan:{skin:'#c9926f', shadow:'#a86f52'},
    deep:{skin:'#865b46', shadow:'#67402f'}
  };


  /* Per-base calibration matrix.
   * Every layer stays in the shared 240x260 canvas, but species have different
   * head/ear geometry. Fine placement belongs here instead of inside art data.
   * Values are SVG transforms and can be tuned without changing configs.
   */
  const LAYER_LAYOUT = {
    human: {
      outfit:{x:0,y:0,s:1},
      base:{x:0,y:0,s:1},
      hair:{x:0,y:0,s:1},
      eyes:{x:0,y:0,s:1},
      mouth:{x:0,y:0,s:1},
      beard:{x:0,y:0,s:1},
      hat:{x:0,y:0,s:1},
      accessory:{x:0,y:0,s:1}
    },
    fox: {
      outfit:{x:0,y:0,s:1},
      base:{x:0,y:0,s:1},
      hair:{x:0,y:-7,s:.96},
      eyes:{x:0,y:1,s:1},
      mouth:{x:0,y:0,s:1},
      beard:{x:0,y:-2,s:.96},
      hat:{x:0,y:-11,s:.92},
      accessory:{x:0,y:0,s:.98}
    },
    rabbit: {
      outfit:{x:0,y:0,s:1},
      base:{x:0,y:0,s:1},
      hair:{x:0,y:-15,s:.92},
      eyes:{x:0,y:3,s:.98},
      mouth:{x:0,y:2,s:1},
      beard:{x:0,y:-1,s:.94},
      hat:{x:0,y:-22,s:.88},
      accessory:{x:0,y:2,s:.98}
    },
    bear: {
      outfit:{x:0,y:1,s:1.02},
      base:{x:0,y:0,s:1},
      hair:{x:0,y:-5,s:.98},
      eyes:{x:0,y:1,s:1},
      mouth:{x:0,y:0,s:1},
      beard:{x:0,y:0,s:1},
      hat:{x:0,y:-7,s:.95},
      accessory:{x:0,y:1,s:1}
    },
    turtle: {
      outfit:{x:0,y:3,s:1.04},
      base:{x:0,y:0,s:1},
      hair:{x:0,y:-2,s:.96},
      eyes:{x:0,y:4,s:.96},
      mouth:{x:0,y:3,s:1},
      beard:{x:0,y:3,s:.95},
      hat:{x:0,y:-2,s:.96},
      accessory:{x:0,y:4,s:.96}
    }
  };

  function layerLayout(base,layer){
    const b=LAYER_LAYOUT[base]||LAYER_LAYOUT.human;
    return b[layer]||{x:0,y:0,s:1};
  }
  function layerTransform(base,layer){
    const a=layerLayout(base,layer);
    const s=Number(a.s||1), x=Number(a.x||0), y=Number(a.y||0);
    // Scale around the canvas center so offsets remain intuitive.
    const ox=120*(1-s), oy=130*(1-s);
    return 'translate('+(x+ox)+' '+(y+oy)+') scale('+s+')';
  }
  function layerGroup(base,layer,html){
    return '<g data-layer="'+layer+'" transform="'+layerTransform(base,layer)+'">'+html+'</g>';
  }

  function clone(x){ return JSON.parse(JSON.stringify(x)); }
  function has(part,id){ return (CATALOG[part]||[]).some(x=>x.id===id); }
  function normalize(raw){
    const o=Object.assign({},DEFAULT,raw||{});
    Object.keys(DEFAULT).forEach(k=>{ if(!has(k,o[k])) o[k]=DEFAULT[k]; });
    return o;
  }
  function label(part,id){
    const x=(CATALOG[part]||[]).find(v=>v.id===id);
    return x?x.label:id;
  }
  function hash32(v){
    const s=String(v); let h=2166136261>>>0;
    for(let i=0;i<s.length;i++){ h^=s.charCodeAt(i); h=Math.imul(h,16777619); }
    return h>>>0;
  }
  function pick(arr,h,shift){ return arr[(h>>>shift)%arr.length].id; }

  function botConfig(pid){
    const h=hash32('bot:'+pid);
    const cfg={
      base:pick(CATALOG.base,h,0),
      tone:pick(CATALOG.tone,h,3),
      eyes:pick(CATALOG.eyes,h,5),
      hair:pick(CATALOG.hair,h,7),
      hat:pick(CATALOG.hat,h,10),
      beard:pick(CATALOG.beard,h,13),
      outfit:pick(CATALOG.outfit,h,16),
      accessory:pick(CATALOG.accessory,h,19)
    };
    // Keep impossible-looking collisions uncommon without removing variety.
    if(cfg.base!=='human'){
      if((h&1)===0) cfg.hair='none';
      if((h&2)===0) cfg.beard='none';
    }
    if(cfg.hat!=='none' && (h&4)===0) cfg.hair='none';
    return normalize(cfg);
  }

  function legacyPreset(n){
    const presets=[
      {base:'human',tone:'warm',eyes:'round',hair:'short',hat:'gat',beard:'none',outfit:'hanbok_teal',accessory:'none'},
      {base:'human',tone:'light',eyes:'calm',hair:'bun',hat:'none',beard:'none',outfit:'jacket_cream',accessory:'flower'},
      {base:'human',tone:'tan',eyes:'sharp',hair:'short',hat:'none',beard:'none',outfit:'hanbok_burgundy',accessory:'none'},
      {base:'bear',tone:'warm',eyes:'round',hair:'none',hat:'none',beard:'none',outfit:'jacket_cream',accessory:'none'},
      {base:'rabbit',tone:'light',eyes:'calm',hair:'none',hat:'none',beard:'none',outfit:'suit_navy',accessory:'round_glasses'},
      {base:'rabbit',tone:'light',eyes:'round',hair:'none',hat:'none',beard:'none',outfit:'hanbok_burgundy',accessory:'none'},
      {base:'bear',tone:'deep',eyes:'sharp',hair:'none',hat:'none',beard:'none',outfit:'jacket_cream',accessory:'square_glasses'},
      {base:'fox',tone:'warm',eyes:'round',hair:'none',hat:'none',beard:'none',outfit:'hanbok_burgundy',accessory:'none'},
      {base:'turtle',tone:'tan',eyes:'round',hair:'none',hat:'none',beard:'none',outfit:'hanbok_teal',accessory:'none'}
    ];
    return normalize(presets[Math.max(0,Math.min(8,Number(n)||0))]);
  }

  function esc(v){ return String(v).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

  function faceBase(c){
    const p=PALETTE[c.tone]||PALETTE.warm;
    if(c.base==='fox') return `
      <path d="M55 95 L78 35 L108 76 Q120 68 132 76 L162 35 L185 95" fill="#db7638" stroke="#2b2623" stroke-width="7"/>
      <ellipse cx="120" cy="119" rx="67" ry="63" fill="#dc7a3e" stroke="#2b2623" stroke-width="7"/>
      <path d="M72 126 Q120 174 168 126 Q157 181 120 184 Q83 181 72 126" fill="#f7e6c7"/>
      <ellipse cx="120" cy="145" rx="13" ry="9" fill="#2f2c2a"/>`;
    if(c.base==='rabbit') return `
      <ellipse cx="89" cy="54" rx="20" ry="55" fill="#f0e8d8" stroke="#2b2623" stroke-width="7" transform="rotate(-7 89 54)"/>
      <ellipse cx="151" cy="54" rx="20" ry="55" fill="#f0e8d8" stroke="#2b2623" stroke-width="7" transform="rotate(7 151 54)"/>
      <ellipse cx="89" cy="54" rx="8" ry="39" fill="#e7a39b" transform="rotate(-7 89 54)"/>
      <ellipse cx="151" cy="54" rx="8" ry="39" fill="#e7a39b" transform="rotate(7 151 54)"/>
      <ellipse cx="120" cy="123" rx="67" ry="65" fill="#f4eddf" stroke="#2b2623" stroke-width="7"/>
      <ellipse cx="120" cy="147" rx="9" ry="7" fill="#d9968f"/>`;
    if(c.base==='bear') return `
      <circle cx="69" cy="72" r="27" fill="#855638" stroke="#2b2623" stroke-width="7"/>
      <circle cx="171" cy="72" r="27" fill="#855638" stroke="#2b2623" stroke-width="7"/>
      <ellipse cx="120" cy="120" rx="69" ry="66" fill="#865a3d" stroke="#2b2623" stroke-width="7"/>
      <ellipse cx="120" cy="144" rx="31" ry="24" fill="#b98660"/>
      <ellipse cx="120" cy="135" rx="11" ry="8" fill="#2f2c2a"/>`;
    if(c.base==='turtle') return `
      <ellipse cx="120" cy="118" rx="70" ry="65" fill="#88955c" stroke="#2b2623" stroke-width="7"/>
      <g fill="#6f7d49" opacity=".65">
        <circle cx="86" cy="76" r="5"/><circle cx="103" cy="68" r="4"/><circle cx="125" cy="70" r="5"/>
        <circle cx="147" cy="72" r="4"/><circle cx="160" cy="84" r="5"/>
      </g>`;
    return `
      <circle cx="62" cy="122" r="15" fill="${p.skin}" stroke="#2b2623" stroke-width="6"/>
      <circle cx="178" cy="122" r="15" fill="${p.skin}" stroke="#2b2623" stroke-width="6"/>
      <ellipse cx="120" cy="116" rx="65" ry="67" fill="${p.skin}" stroke="#2b2623" stroke-width="7"/>
      <path d="M88 154 Q120 174 152 154" fill="none" stroke="${p.shadow}" stroke-width="3" opacity=".45"/>`;
  }

  function eyes(c){
    if(c.eyes==='smile') return '<path d="M83 119 Q95 130 107 119 M133 119 Q145 130 157 119" fill="none" stroke="#292827" stroke-width="6" stroke-linecap="round"/>';
    const y=118;
    const eyeShape=c.eyes==='sharp'
      ? '<path d="M80 116 Q94 107 108 117 Q94 126 80 116 M132 117 Q146 107 160 116 Q146 126 132 117" fill="#fff" stroke="#292827" stroke-width="5"/>'
      : c.eyes==='calm'
      ? '<rect x="80" y="109" width="29" height="19" rx="8" fill="#fff" stroke="#292827" stroke-width="5"/><rect x="131" y="109" width="29" height="19" rx="8" fill="#fff" stroke="#292827" stroke-width="5"/>'
      : '<ellipse cx="95" cy="'+y+'" rx="15" ry="13" fill="#fff" stroke="#292827" stroke-width="5"/><ellipse cx="145" cy="'+y+'" rx="15" ry="13" fill="#fff" stroke="#292827" stroke-width="5"/>';
    return eyeShape+'<circle cx="96" cy="119" r="5" fill="#252525"/><circle cx="144" cy="119" r="5" fill="#252525"/>';
  }

  function hair(c){
    if(c.hair==='none') return '';
    if(c.hair==='bun') return '<circle cx="155" cy="58" r="27" fill="#3a2923" stroke="#2b2623" stroke-width="6"/><path d="M61 101 Q68 50 119 48 Q168 48 180 101 Q152 78 121 79 Q90 77 61 101" fill="#3a2923"/>';
    if(c.hair==='bob') return '<path d="M55 111 Q57 47 120 45 Q183 48 185 111 L170 153 Q159 132 160 87 Q120 69 80 87 Q81 132 70 153Z" fill="#3c2a24" stroke="#2b2623" stroke-width="6"/>';
    if(c.hair==='side') return '<path d="M58 103 Q65 48 121 47 Q172 48 181 96 Q137 75 98 88 Q80 94 58 103Z" fill="#302522" stroke="#2b2623" stroke-width="6"/>';
    return '<path d="M60 102 Q67 48 120 48 Q173 48 180 102 Q151 78 120 80 Q90 78 60 102Z" fill="#302522" stroke="#2b2623" stroke-width="6"/>';
  }

  function beard(c){
    if(c.beard==='none') return '';
    const col=c.base==='human'?'#3a2a24':'#4a372c';
    if(c.beard==='moustache') return '<path d="M117 151 Q104 140 91 150 Q102 160 119 155 Q136 160 149 150 Q136 140 123 151Z" fill="'+col+'"/>';
    if(c.beard==='goatee') return '<path d="M108 151 Q120 160 132 151 L128 177 Q120 186 112 177Z" fill="'+col+'"/>';
    return '<path d="M76 145 Q83 190 120 196 Q157 190 164 145 Q145 169 120 170 Q95 169 76 145Z" fill="'+col+'" opacity=".95"/>';
  }

  function hat(c){
    if(c.hat==='none') return '';
    if(c.hat==='gat') return '<ellipse cx="120" cy="68" rx="83" ry="17" fill="#252322" stroke="#171615" stroke-width="5"/><path d="M88 66 L94 25 Q120 16 146 25 L152 66Z" fill="#262423" stroke="#171615" stroke-width="6"/>';
    if(c.hat==='fedora') return '<ellipse cx="120" cy="67" rx="69" ry="15" fill="#34302f"/><path d="M83 62 Q89 31 120 29 Q151 31 157 62Z" fill="#403a38" stroke="#292625" stroke-width="5"/>';
    if(c.hat==='cap') return '<path d="M67 67 Q81 31 122 34 Q158 37 169 67Z" fill="#344c69" stroke="#262d35" stroke-width="5"/><path d="M119 66 Q161 63 183 75 Q148 80 115 75Z" fill="#2d425b"/>';
    return '<path d="M73 69 Q78 31 120 29 Q162 31 167 69Z" fill="#655b58" stroke="#2b2827" stroke-width="5"/><rect x="72" y="61" width="96" height="18" rx="8" fill="#554c49"/>';
  }

  function outfit(c){
    const common='stroke="#2b2a29" stroke-width="7"';
    if(c.outfit==='hanbok_burgundy') return '<path d="M50 260 Q54 191 89 177 L120 198 L151 177 Q186 191 190 260Z" fill="#7b3745" '+common+'/><path d="M91 177 L120 199 L103 223 L75 188Z" fill="#efe4d3"/><path d="M149 177 L120 199 L137 223 L165 188Z" fill="#e9d8c5"/>';
    if(c.outfit==='suit_navy') return '<path d="M49 260 Q55 190 91 178 L120 194 L149 178 Q185 190 191 260Z" fill="#293b55" '+common+'/><path d="M93 178 L120 195 L103 226 L78 187Z" fill="#eef1f2"/><path d="M147 178 L120 195 L137 226 L162 187Z" fill="#eef1f2"/><path d="M114 195 L126 195 L129 236 L111 236Z" fill="#5b2d35"/>';
    if(c.outfit==='jacket_cream') return '<path d="M48 260 Q54 191 90 178 L120 196 L150 178 Q186 191 192 260Z" fill="#ded2bc" '+common+'/><path d="M93 179 L120 197 L105 221Z" fill="#ffffff"/><path d="M147 179 L120 197 L135 221Z" fill="#ffffff"/>';
    if(c.outfit==='hoodie_charcoal') return '<path d="M49 260 Q55 190 89 179 Q120 194 151 179 Q185 190 191 260Z" fill="#41464c" '+common+'/><path d="M82 185 Q120 215 158 185" fill="none" stroke="#666c72" stroke-width="8"/><path d="M112 201 L108 242 M128 201 L132 242" stroke="#c1c4c6" stroke-width="3"/>';
    return '<path d="M50 260 Q54 191 89 177 L120 198 L151 177 Q186 191 190 260Z" fill="#397067" '+common+'/><path d="M91 177 L120 199 L103 223 L75 188Z" fill="#f0e3cf"/><path d="M149 177 L120 199 L137 223 L165 188Z" fill="#e7d6bf"/>';
  }

  function accessory(c){
    if(c.accessory==='none') return '';
    if(c.accessory==='round_glasses') return '<g fill="none" stroke="#3b3d40" stroke-width="5"><circle cx="94" cy="118" r="20"/><circle cx="146" cy="118" r="20"/><path d="M114 117 L126 117 M74 113 L59 108 M166 113 L181 108"/></g>';
    if(c.accessory==='square_glasses') return '<g fill="none" stroke="#33383e" stroke-width="5"><rect x="74" y="99" width="41" height="35" rx="8"/><rect x="125" y="99" width="41" height="35" rx="8"/><path d="M115 115 L125 115"/></g>';
    if(c.accessory==='sunglasses') return '<g fill="#1f252c" stroke="#11161a" stroke-width="4"><path d="M73 102 L113 103 L109 130 Q91 138 78 126Z"/><path d="M127 103 L167 102 L162 126 Q149 138 131 130Z"/></g><path d="M111 109 L129 109" stroke="#11161a" stroke-width="5"/>';
    if(c.accessory==='flower') return '<g transform="translate(168 78)"><circle r="8" fill="#d35b66"/><circle cx="11" cy="0" r="8" fill="#e27a83"/><circle cx="5" cy="-10" r="8" fill="#ef929a"/><circle cx="5" cy="8" r="8" fill="#cf4f5c"/></g>';
    return '<circle cx="178" cy="139" r="6" fill="#d8b45e" stroke="#6b5222" stroke-width="2"/>';
  }

  function mouth(c){
    if(c.base==='fox'||c.base==='rabbit'||c.base==='bear') return '<path d="M108 155 Q120 164 132 155" fill="none" stroke="#312e2c" stroke-width="4" stroke-linecap="round"/>';
    return '<path d="M106 154 Q120 163 134 154" fill="none" stroke="#8b554c" stroke-width="4" stroke-linecap="round"/>';
  }

  function render(raw,opts){
    const c=normalize(raw), o=opts||{};
    const title=o.title?'<title>'+esc(o.title)+'</title>':'';
    return '<span class="layer-avatar" data-base="'+esc(c.base)+'">'+
      '<svg viewBox="0 0 240 260" role="img" aria-hidden="'+(o.decorative!==false?'true':'false')+'">'+title+
      layerGroup(c.base,'outfit',outfit(c))+
      layerGroup(c.base,'base',faceBase(c))+
      layerGroup(c.base,'hair',hair(c))+
      layerGroup(c.base,'eyes',eyes(c))+
      layerGroup(c.base,'mouth',mouth(c))+
      layerGroup(c.base,'beard',beard(c))+
      layerGroup(c.base,'hat',hat(c))+
      layerGroup(c.base,'accessory',accessory(c))+
      '</svg></span>';
  }

  const api={CATALOG,DEFAULT,LAYER_LAYOUT,layerLayout,normalize,label,botConfig,legacyPreset,render,clone};
  root.AvatarSystem=api;
  if(typeof module!=='undefined'&&module.exports) module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
