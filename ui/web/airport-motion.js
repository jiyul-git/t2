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
 uniform float dayWeight,hour,sun,gold,timeSec;
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
   // Moving late afternoon window streak and ambient bounce.
   float lamp=exp(-dot((p-vec2(.66,.43))/vec2(.35,.34),
                       (p-vec2(.66,.43))/vec2(.35,.34))*2.0);
   sceneColor+=vec3(.18,.093,.039)*lamp*gold*.28;
   float floorShape=feather(p,vec2(.50,.965),vec2(.56,.13));
   float shadowStripe=sin((p.x-p.y*.44)*27.0-hour*.14);
   float shadow=max(0.,shadowStripe)*floorShape*sunlight*.025;
   sceneColor*=1.0-shadow;
   // Gentle character contact shadow breathes in sync with each body.
   float foot1=feather(p,vec2(.22,.956),vec2(.140,.060));
   float foot2=feather(p,vec2(.45,.955),vec2(.120,.060));
   float foot3=feather(p,vec2(.69,.960),vec2(.115,.058));
   float foot4=feather(p,vec2(.85,.958),vec2(.09,.05));
   float breathing=(foot1*(wobble1+1.)+foot2*(wobble2+1.)+
                    foot3*(wobble3+1.)+foot4*(wobble4+1.))*.009;
   sceneColor*=1.0-breathing;
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
