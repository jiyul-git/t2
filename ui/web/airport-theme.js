/* Local-clock airport illumination; does not affect poker game or server. */
(function(root){
  'use strict';
  const dawnStart=5.5, dawnEnd=8.5, duskStart=16.5, duskEnd=20;
  const clamp=x=>Math.max(0,Math.min(1,x));
  const smooth=t=>{t=clamp(t);return t*t*(3-2*t);};
  function dayWeight(h){
    if(h<dawnStart||h>=duskEnd)return 0;
    if(h<dawnEnd)return smooth((h-dawnStart)/(dawnEnd-dawnStart));
    if(h<duskStart)return 1;
    return 1-smooth((h-duskStart)/(duskEnd-duskStart));
  }
  const rgb=(a,b,w)=>'rgb('+a.map((v,i)=>Math.round(v+(b[i]-v)*w)).join(',')+')';
  const localHour=d=>d.getHours()+d.getMinutes()/60+d.getSeconds()/3600;
  function currentHour(){
    // Hidden screenshot QA override only, e.g. ?airport_preview=18:30
    try{
      const m=/^([01]?\d|2[0-3]):([0-5]\d)$/.exec(new URLSearchParams(root.location.search).get('airport_preview')||'');
      if(m)return Number(m[1])+Number(m[2])/60;
    }catch(_){}
    return localHour(new Date());
  }
  function apply(){
    const w=dayWeight(currentHour()),el=document.documentElement;
    el.style.setProperty('--airport-day-alpha',w.toFixed(5));
    el.style.setProperty('--airport-surface-top',rgb([18,46,50],[60,103,98],w));
    el.style.setProperty('--airport-surface-mid',rgb([6,27,31],[17,60,60],w));
    el.style.setProperty('--airport-surface-bottom',rgb([8,31,34],[15,43,48],w));
    el.dataset.airportLighting='automatic';
    root.T2AirportLighting={dayWeight:dayWeight,localHour:localHour,weight:w};
  }
  apply();
  root.addEventListener('focus',apply);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)apply();});
  root.setInterval(()=>{if(!document.hidden)apply();},30000);
})(window);
