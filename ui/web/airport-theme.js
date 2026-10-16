/* Airport lighting by device-local time. Flip TEST_CLOCK_MODE only for release. */
(function(root){
 'use strict';
 const TEST_CLOCK_MODE=true; // Once approved, change only this flag to false.
 const DAY_MINUTES=1440;
 let testMinutes=null;
 const cap=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
 const ease=x=>{const t=cap(x,0,1);return t*t*(3-2*t)};
 const lerp=(a,b,t)=>a+(b-a)*t;
 const STOPS=[
 // t: local minutes, day: visual image blend, gold: low-angle light,
 // lamp: electric light, blue: blue-hour illumination.
 {t:0,day:0,gold:.04,lamp:1,blue:.43},
 {t:270,day:0,gold:.04,lamp:1,blue:.47},
 {t:330,day:.02,gold:.25,lamp:1,blue:.50},
 {t:375,day:.25,gold:.86,lamp:.89,blue:.32},
 {t:420,day:.63,gold:.95,lamp:.64,blue:.13},
 {t:480,day:.96,gold:.49,lamp:.25,blue:.06},
 {t:540,day:1,gold:.19,lamp:.15,blue:.05},
 {t:660,day:1,gold:.05,lamp:.10,blue:.06},
 {t:780,day:1,gold:.04,lamp:.10,blue:.06},
 {t:900,day:1,gold:.15,lamp:.19,blue:.05},
 {t:990,day:.89,gold:.66,lamp:.28,blue:.07},
 {t:1050,day:.64,gold:.92,lamp:.61,blue:.14},
 {t:1110,day:.31,gold:.86,lamp:.86,blue:.30},
 {t:1170,day:.08,gold:.48,lamp:1,blue:.44},
 {t:1230,day:0,gold:.10,lamp:1,blue:.46},
 {t:1440,day:0,gold:.04,lamp:1,blue:.43}
 ];
 function localMinutes(d){return d.getHours()*60+d.getMinutes()+d.getSeconds()/60;}
 function lighting(mins){
   const m=((Number(mins)%DAY_MINUTES)+DAY_MINUTES)%DAY_MINUTES;
   let i=0;
   while(i<STOPS.length-2&&STOPS[i+1].t<=m)i++;
   const a=STOPS[i],b=STOPS[i+1],q=ease((m-a.t)/(b.t-a.t));
   const blend=k=>lerp(a[k],b[k],q);
   const hour=m/60,day=blend('day'),gold=blend('gold'),lamp=blend('lamp'),blue=blend('blue');
   // Approximate solar path; decorative shadow direction, not an astronomical ephemeris.
   const sun=Math.max(0,Math.sin(Math.PI*(hour-5.5)/14));
   const direction=cap(Math.sin((hour-12)*Math.PI/12),-1,1);
   const shadowLength=1.05+(1-sun)*1.25;
   const shadowOpacity=day*(.11+.29*(1-sun));
   return {mins:m,h:hour,day,gold,lamp,blue,sun,night:1-day,direction,shadowLength,shadowOpacity};
 }
 const rgb=(a,b,w)=>'rgb('+a.map((v,i)=>Math.round(lerp(v,b[i],w))).join(',')+')';
 const fmt=n=>{n=Math.floor(n)%DAY_MINUTES;return String(Math.floor(n/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0')};
 function getMinutes(){return testMinutes===null?localMinutes(new Date()):testMinutes;}
 function apply(){
   const v=lighting(getMinutes()),el=document.documentElement,style=el.style;
   const set=(k,x)=>style.setProperty(k,String(x));
   set('--airport-day-alpha',v.day.toFixed(5));
   set('--airport-surface-top',rgb([18,46,50],[60,103,98],v.day));
   set('--airport-surface-mid',rgb([6,27,31],[17,60,60],v.day));
   set('--airport-surface-bottom',rgb([8,31,34],[15,43,48],v.day));
   set('--airport-shadow-shift',(v.direction*15).toFixed(2)+'%');
   set('--airport-shadow-angle',(v.direction*24).toFixed(2)+'deg');
   set('--airport-shadow-length',v.shadowLength.toFixed(3));
   set('--airport-shadow-opacity',v.shadowOpacity.toFixed(4));
   set('--airport-gold-opacity',(v.gold*.22).toFixed(4));
   set('--airport-lamp-alpha',(v.lamp*.38).toFixed(4));
   set('--airport-blue-alpha',(v.blue*.18).toFixed(4));
   el.dataset.airportLighting=testMinutes===null?'automatic':'preview';
   root.T2AirportLighting=Object.assign({},v,{testMode:TEST_CLOCK_MODE,dayWeight:h=>lighting(h*60).day,localHour:d=>localMinutes(d)/60});
   const slider=document.getElementById('airportTimeSlider');
   if(slider&&testMinutes===null&&document.activeElement!==slider)slider.value=String(Math.floor(getMinutes()));
   const output=document.getElementById('airportTimeValue');
   if(output)output.textContent=fmt(getMinutes());
   const reset=document.getElementById('airportTimeReset');
   if(reset)reset.disabled=testMinutes===null;
   root.dispatchEvent(new CustomEvent('t2-airport-lighting',{detail:v}));
 }
 function init(){
   const panel=document.getElementById('airportTimeTest'),slider=document.getElementById('airportTimeSlider');
   if(!panel||!slider)return;
   panel.hidden=!TEST_CLOCK_MODE;
   if(TEST_CLOCK_MODE){
     slider.value=String(Math.floor(localMinutes(new Date())));
     slider.addEventListener('input',()=>{testMinutes=cap(Number(slider.value)||0,0,1439);apply();});
     const reset=document.getElementById('airportTimeReset');
     if(reset)reset.addEventListener('click',()=>{testMinutes=null;apply();});
   }
   apply();
 }
 root.T2AirportClock={getMinutes,lighting,TEST_CLOCK_MODE,setTestMinutes:m=>{
   if(!TEST_CLOCK_MODE)return;testMinutes=cap(Number(m)||0,0,1439);apply();
 },useRealTime:()=>{testMinutes=null;apply();}};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
 else init();
 apply();
 root.addEventListener('focus',apply);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)apply();});
 root.setInterval(()=>{if(!document.hidden&&testMinutes===null)apply();},15000);
})(window);
