/* T2 lobby airport lighting: device-local time or one switchable test clock. */
(function(root){
  'use strict';
  const TEST_CLOCK_MODE = true; // Production: change ONLY this to false.
  let testMinutes = null;
  const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
  const smooth=t=>{t=clamp(t,0,1);return t*t*(3-2*t);};
  const pulse=(t,center,radius)=>Math.max(0,1-Math.abs(t-center)/radius);
  function localMinutes(date){return date.getHours()*60+date.getMinutes()+date.getSeconds()/60;}
  function dayBlend(mins){
    const h=mins/60;
    if(h<5.3||h>=20.4)return 0;
    if(h<8.4)return smooth((h-5.3)/(8.4-5.3));
    if(h<16.4)return 1;
    return 1-smooth((h-16.4)/(20.4-16.4));
  }
  function lighting(mins){
    const h=mins/60,day=dayBlend(mins),gold=Math.max(pulse(h,6.7,2.1),pulse(h,18.1,2.1));
    const sun=Math.max(0,Math.sin(Math.PI*(h-5.3)/(20.4-5.3)));
    return {mins,h,day,gold,sun,night:1-day, direction:clamp((h-12)/7,-1,1)};
  }
  const rgb=(a,b,w)=>'rgb('+a.map((v,i)=>Math.round(v+(b[i]-v)*w)).join(',')+')';
  const fmt=n=>{n=Math.round(n)%1440;return String(Math.floor(n/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0');};
  function getMinutes(){return TEST_CLOCK_MODE&&testMinutes!==null?testMinutes:localMinutes(new Date());}
  function apply(){
    const info=lighting(getMinutes()), el=document.documentElement;
    el.style.setProperty('--airport-day-alpha',info.day.toFixed(5));
    el.style.setProperty('--airport-surface-top',rgb([18,46,50],[60,103,98],info.day));
    el.style.setProperty('--airport-surface-mid',rgb([6,27,31],[17,60,60],info.day));
    el.style.setProperty('--airport-surface-bottom',rgb([8,31,34],[15,43,48],info.day));
    el.style.setProperty('--airport-shadow-shift',(info.direction*20).toFixed(2)+'%');
    el.style.setProperty('--airport-shadow-opacity',(info.sun*info.day*0.23).toFixed(4));
    el.style.setProperty('--airport-gold-opacity',(info.gold*0.14).toFixed(4));
    el.dataset.airportLighting=TEST_CLOCK_MODE?'test':'automatic';
    root.T2AirportLighting=Object.assign({},info,{testMode:TEST_CLOCK_MODE, dayWeight:hour=>dayBlend(hour*60), localHour:d=>localMinutes(d)/60});
    root.dispatchEvent(new CustomEvent('t2-airport-lighting',{detail:info}));
    const output=document.getElementById('airportTimeValue');
    if(output)output.textContent=fmt(getMinutes());
  }
  function init(){
    const panel=document.getElementById('airportTimeTest'),slider=document.getElementById('airportTimeSlider');
    if(!panel||!slider)return;
    panel.hidden=!TEST_CLOCK_MODE;
    if(TEST_CLOCK_MODE){
      testMinutes=Math.floor(localMinutes(new Date()));
      slider.value=String(testMinutes);
      slider.addEventListener('input',()=>{
        testMinutes=clamp(Number(slider.value)||0,0,1439);
        apply();
      });
    }
    apply();
  }
  root.T2AirportClock={getMinutes,lighting,dayBlend,TEST_CLOCK_MODE};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
  apply();
  root.addEventListener('focus',apply);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)apply();});
  root.setInterval(()=>{if(!document.hidden&&(!TEST_CLOCK_MODE||testMinutes===null))apply();},15000);
})(window);
