/* Pixel-space idle breathing and position-aware shadow/reflections.
   The supplied artwork is a single composite, not an independent sprite sheet:
   character motion is limited to feathered local deformation (no detached limbs).
   WebGL is optional; static CSS crossfade remains the fallback. */
(function(root){
 'use strict';
 const canvas=document.getElementById('airportSceneMotion');
 const scene=canvas&&canvas.closest('.airport-scene');
 if(!canvas||!scene||!root.WebGLRenderingContext||
    (root.matchMedia&&root.matchMedia('(prefers-reduced-motion: reduce)').matches))return;
 const gl=canvas.getContext('webgl',{alpha:false,premultipliedAlpha:false,antialias:false,depth:false});
 if(!gl)return;
 const vertex=`
 attribute vec2 position;
 varying vec2 uv;
 void main(){uv=position*0.5+0.5;gl_Position=vec4(position,0.0,1.0);}
 `;
 const fragment=`
 precision mediump float;
 varying vec2 uv;
 uniform sampler2D texNight,texDay;
 uniform float dayWeight,hour,sun,gold,timeSec,shadowDirection,shadowLength,shadowOpacity,lamps,blue;
 float feather(vec2 p,vec2 center,vec2 radius){
   float d=length((p-center)/radius);
   return 1.0-smoothstep(0.58,1.0,d);
 }
 void main(){
   vec2 p=vec2(uv.x,1.0-uv.y);
   float tiger=feather(p,vec2(.202,.730),vec2(.167,.280));
   float bunny=feather(p,vec2(.427,.735),vec2(.143,.260));
   float turtle=feather(p,vec2(.653,.803),vec2(.139,.237));
   float penguin=feather(p,vec2(.856,.864),vec2(.105,.167));
   float wobble1=sin(timeSec*1.05+.40);
   float wobble2=sin(timeSec*1.28+2.25);
   float wobble3=sin(timeSec*.91+4.06);
   float wobble4=sin(timeSec*1.34+6.16);
   // Softly shift internal artwork pixels, zero displacement at mask boundaries.
   p.y+=.0030*(tiger*wobble1+bunny*wobble2+turtle*wobble3+penguin*wobble4);
   p.x+=.0012*(tiger*cos(timeSec*.70)+bunny*cos(timeSec*.84+1.0)
               +turtle*cos(timeSec*.63+3.0)+penguin*cos(timeSec*.93+4.1));
   vec2 sampleUV=vec2(clamp(p.x,0.,1.),1.-clamp(p.y,0.,1.));
   vec3 sceneColor=mix(texture2D(texNight,sampleUV).rgb,
                       texture2D(texDay,sampleUV).rgb,dayWeight);
   float sunlight=max(0.,sun);
   // Separate morning/evening color bleed and cool-blue-hour bounce.
   float lowAngle=exp(-dot((p-vec2(.67,.31))/vec2(.44,.38),
                           (p-vec2(.67,.31))/vec2(.44,.38))*1.5);
   sceneColor+=vec3(.15,.087,.035)*lowAngle*gold*.30;
   sceneColor+=vec3(.010,.024,.045)*blue*max(.0,1.0-sun)*.36;
   float lampsGlow=feather(p,vec2(.94,.58),vec2(.15,.23))
                  +feather(p,vec2(.055,.58),vec2(.12,.26));
   sceneColor+=vec3(.022,.015,.006)*lampsGlow*lamps*.22;

   // Moving perspective window-frame shadows follow the simulated sun azimuth.
   // Mask out upper terminal/signs; ground contact is always diffuse.
   float ground=smoothstep(.74,.97,p.y);
   float shift=shadowDirection*.085*shadowLength;
   float slats=pow(max(0.0,sin((p.x+shift-p.y*.16)*34.0)),5.0);
   sceneColor*=1.0-(ground*slats*shadowOpacity*.13);

   // The four cast shadows change length, direction and softness per minute.
   float castShadow=0.0;
   castShadow+=feather(p,vec2(.20+shift,.950),vec2(.14+shadowLength*.027,.07))*0.78;
   castShadow+=feather(p,vec2(.44+shift,.968),vec2(.12+shadowLength*.024,.065))*0.65;
   castShadow+=feather(p,vec2(.67+shift,.972),vec2(.12+shadowLength*.026,.06))*0.72;
   castShadow+=feather(p,vec2(.88+shift,.971),vec2(.084+shadowLength*.023,.054))*0.54;
   sceneColor*=1.0-ground*min(1.,castShadow)*shadowOpacity*.16;

   // Character silhouettes breathe subtly, while their contact shadows
   // shift with them. Existing artwork (including the eyes) remains intact.
   float contact=feather(p,vec2(.20,.97),vec2(.12,.05))*(wobble1+1.0)
                +feather(p,vec2(.44,.97),vec2(.12,.05))*(wobble2+1.0)
                +feather(p,vec2(.67,.97),vec2(.10,.05))*(wobble3+1.0)
                +feather(p,vec2(.88,.97),vec2(.08,.05))*(wobble4+1.0);
   sceneColor*=1.0-contact*.006;
   gl_FragColor=vec4(clamp(sceneColor,0.,1.),1.0);
 }
 `;
 function compile(type,source){
   const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);
   if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)){
     console.warn('공항 애니메이션 셰이더 비활성화:',gl.getShaderInfoLog(shader));gl.deleteShader(shader);return null;
   }
   return shader;
 }
 const vs=compile(gl.VERTEX_SHADER,vertex),fs=compile(gl.FRAGMENT_SHADER,fragment);
 if(!vs||!fs)return;
 const program=gl.createProgram();gl.attachShader(program,vs);gl.attachShader(program,fs);
 gl.linkProgram(program);
 if(!gl.getProgramParameter(program,gl.LINK_STATUS))return;
 gl.useProgram(program);
 const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
 gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
 const loc=gl.getAttribLocation(program,'position');
 gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,2,gl.FLOAT,false,0,0);
 function load(src){return new Promise((resolve,reject)=>{
   const image=new Image();image.onload=()=>resolve(image);image.onerror=reject;image.src=src;});}
 function texture(image,unit){
   const tex=gl.createTexture();gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_2D,tex);
   gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);
   gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);
   gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);
   gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
   gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);
   gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
   gl.uniform1i(gl.getUniformLocation(program,unit?'texDay':'texNight'),unit);
 }
 function setFloat(name,v){gl.uniform1f(gl.getUniformLocation(program,name),v);}
 let stopped=false,lastFrame=0;
 function frame(t){
   if(stopped)return;
   root.requestAnimationFrame(frame);
   if(document.hidden||t-lastFrame<42)return; // max 24 fps for mobile batteries
   lastFrame=t;
   const w=Math.min(root.devicePixelRatio||1,1.5),width=Math.round(canvas.clientWidth*w);
   const height=Math.round(canvas.clientHeight*w);
   if(width<1||height<1)return;
   if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;gl.viewport(0,0,width,height);}
   const s=root.T2AirportLighting||{};
   setFloat('dayWeight',Number(s.day)||0);
   setFloat('hour',Number(s.h)||0);
   setFloat('sun',Number(s.sun)||0);
   setFloat('gold',Number(s.gold)||0);
   setFloat('shadowDirection',Number(s.direction)||0);
   setFloat('shadowLength',Number(s.shadowLength)||1);
   setFloat('shadowOpacity',Number(s.shadowOpacity)||0);
   setFloat('lamps',Number(s.lamp)||0);
   setFloat('blue',Number(s.blue)||0);
   setFloat('timeSec',t*.001);
   gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
 }
 root.addEventListener('pagehide',()=>{stopped=true;});
 Promise.all([
   load('assets/t2-airport/lobby_hero_night.webp'),
   load('assets/t2-airport/lobby_hero_day.webp')
 ]).then(images=>{
   gl.useProgram(program);
   texture(images[0],0);texture(images[1],1);
   scene.classList.add('airport-motion-ready');
   root.requestAnimationFrame(frame);
 }).catch(e=>console.warn('공항 정적 이미지로 전환:',e));
})(window);
