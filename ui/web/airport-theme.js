/* Presentation-only airport theme, shared by lobby and playing table. */
(function(root){
  'use strict';
  const KEY='t2_airport_theme_mode', modes=['auto','day','night'];
  function mode(){
    try { const x=localStorage.getItem(KEY); return modes.includes(x)?x:'night'; }
    catch (_) { return 'auto'; }
  }
  function nowInKorea(){
    const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Seoul',hour:'2-digit',hourCycle:'h23'}).format(new Date());
    const hour=Number(parts.slice(0,2));
    return hour>=6 && hour<18?'day':'night';
  }
  function apply(){
    const selected=mode(), resolved=selected==='auto'?nowInKorea():selected;
    document.documentElement.dataset.airportTheme=resolved;
    document.documentElement.dataset.airportMode=selected;
    root.dispatchEvent(new Event('t2-airport-theme'));
  }
  function setMode(value){
    if(!modes.includes(value)) return;
    try { localStorage.setItem(KEY,value); } catch (_) {}
    apply();
  }
  root.T2AirportTheme={getMode:mode,setMode,apply};
  root.addEventListener('storage',e=>{if(e.key===KEY)apply();});
  root.addEventListener('focus',apply);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)apply();});
  apply();
  setInterval(()=>{if(mode()==='auto'&&!document.hidden)apply();},60000);
})(window);
