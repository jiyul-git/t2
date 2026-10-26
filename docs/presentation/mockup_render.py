import math, os
from PIL import Image, ImageDraw, ImageFont
P=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','ui','web','assets','portraits','%02d.png')
FONT='/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
f=lambda s: ImageFont.truetype(FONT,s)
A,B,TH=1.55,0.95,0.75          # table semi-axes (m), table height
B=float(os.environ.get('TB',0.80))  # 테이블 세로 반축(내 쪽↔맞은편). 2026-10-26 사용자: 더 얇게 → 0.68
EYE=1.22; HFOV=80
import os as _o; HFOV=float(_o.environ.get('HFOV',HFOV))
import sys as _s
EYE=float(_s.argv[2]) if len(_s.argv)>2 else EYE
def seat_ang(k): return -60+37.5*(k-1)    # dealer at -90 (far side); seat 5 at +90
def on_ell(deg,s=1.0): t=math.radians(deg); return (A*s*math.cos(t), B*s*math.sin(t))
POS={9:'BTN',1:'SB',2:'BB',3:'UTG',4:'UTG+1',5:'UTG+2',6:'LJ',7:'HJ',8:'CO'}
ACT={8:'2.5bb 레이즈',3:'폴드',7:'폴드',4:'폴드',6:'콜'}
CLOTH={1:'#3e6b4a',2:'#c9706a',3:'#c9a227',4:'#3e6b4a',5:'#5470a0',6:'#c9706a',7:'#d9cdb0',8:'#8a2f3a',9:'#2f3f66'}
CHAR={k:((k-1)%9)+1 for k in range(1,10)}
import sys
W,H=844,390; SC=2
PITCH=float(sys.argv[1]) if len(sys.argv)>1 else -8
def cam(hero):
    x,z=on_ell(seat_ang(hero),1.28); c=(x,EYE,z)
    tgt=(0.0,TH,0.0); fx,fy,fz=[tgt[i]-c[i] for i in range(3)]
    n=math.sqrt(fx*fx+fy*fy+fz*fz); fwd=(fx/n,fy/n,fz/n)
    # tilt further down so the near table edge and hero hands are on screen
    pitch=math.radians(PITCH); 
    hl=math.hypot(fwd[0],fwd[2]); el=math.atan2(fwd[1],hl)+pitch
    fwd=(fwd[0]/hl*math.cos(el), math.sin(el), fwd[2]/hl*math.cos(el))
    r=(-fwd[2],0,fwd[0]); rn=math.hypot(r[0],r[2]); r=(r[0]/rn,0,r[2]/rn)
    u=(r[1]*fwd[2]-r[2]*fwd[1], r[2]*fwd[0]-r[0]*fwd[2], r[0]*fwd[1]-r[1]*fwd[0])
    return c,fwd,r,u
def proj(cm,p):
    c,fw,r,u=cm; d=[p[i]-c[i] for i in range(3)]
    z=sum(d[i]*fw[i] for i in range(3))
    if z<0.05: return None
    k=(W*SC/2)/math.tan(math.radians(HFOV/2))
    return (W*SC/2+sum(d[i]*r[i] for i in range(3))/z*k, H*SC/2-sum(d[i]*u[i] for i in range(3))/z*k, z)
def ellpoly(cm,s,y):
    pts=[proj(cm,(*on_ell(a,s)[:1],y,on_ell(a,s)[1])) for a in range(0,360,3)]
    pts=[(p[0],p[1]) for p in pts if p]; return pts
def portrait(i,eyes=True):
    im=Image.open(P%i).convert('RGBA'); d=ImageDraw.Draw(im)
    return im
def render(hero):
    img=Image.new('RGB',(W*SC,H*SC),'#2a2118'); d=ImageDraw.Draw(img,'RGBA')
    cm=cam(hero)
    # floor / wall gradient
    for yy in range(0,H*SC,8): 
        t=yy/(H*SC); d.rectangle([0,yy,W*SC,yy+8],fill=(int(40+30*t),int(30+22*t),int(24+14*t)))
    d.polygon(ellpoly(cm,1.13,TH-0.02),fill='#5b3a22'); d.polygon(ellpoly(cm,1.10,TH),fill='#7a4e2c')
    d.polygon(ellpoly(cm,1.0,TH),fill='#1f5a44'); d.polygon(ellpoly(cm,0.62,TH),outline=(255,255,255,40))
    # board cards + pot
    for j in range(5):
        x=-0.36+j*0.18; q=[proj(cm,(x+dx,TH,dz)) for dx,dz in ((-.07,-.05),(.07,-.05),(.07,.05),(-.07,.05))]
        if all(q): d.polygon([(a[0],a[1]) for a in q],fill='#f4efe4' if j<3 else (255,255,255,50),outline='#333')
    pc=proj(cm,(0,TH,0.22))
    if pc: d.ellipse([pc[0]-18*SC/ (pc[2]),pc[1]-8*SC/pc[2],pc[0]+18*SC/pc[2],pc[1]+8*SC/pc[2]],fill='#c9a227')
    items=[]
    dx,dz=on_ell(-90,1.30); items.append(('dealer',(dx,dz),None))
    for k in range(1,10):
        if k==hero: continue
        items.append(('seat',on_ell(seat_ang(k),1.28),k))
    vis=[];off=[]
    for kind,(x,z),k in items:
        base=proj(cm,(x,TH-0.05,z)); top=proj(cm,(x,TH+0.62,z))
        if not base or not top or not (-0.15*W*SC< base[0] < 1.15*W*SC): off.append((kind,k,x,z)); continue
        if base[0]<0 or base[0]>W*SC: off.append((kind,k,x,z))
        items_z=base[2]; vis.append((items_z,kind,k,base,top,x,z))
    print('hero',hero,'visible',sorted([(k if k else 'D') for _,kind,k,base,*_ in vis if 0<=base[0]<=W*SC],key=str))
    bubbles=[]
    for zz,kind,k,base,top,x,z in sorted(vis,reverse=True):
        h=base[1]-top[1]
        if kind=='dealer':
            w=h*0.75; d.rounded_rectangle([base[0]-w/2,top[1],base[0]+w/2,base[1]],radius=w*0.2,fill='#3b3b48',outline='#111',width=3)
            d.text((base[0],top[1]+h*0.45),'딜러',font=f(int(max(14,h*0.18))),fill='white',anchor='mm'); continue
        # body: torso box from table level to shoulders (1.12m), head portrait above (1.02~1.42m)
        sh=proj(cm,(x,1.12,z)); hb=proj(cm,(x,1.02,z)); ht=proj(cm,(x,1.42,z))
        col=CLOTH[CHAR[k]]; tw2=(base[1]-sh[1])*0.62
        d.rounded_rectangle([base[0]-tw2,sh[1],base[0]+tw2,base[1]],radius=tw2*0.35,fill=col,outline='#1b120a',width=3)
        d.polygon([(base[0]-tw2*0.35,sh[1]),(base[0],sh[1]+(base[1]-sh[1])*0.35),(base[0]+tw2*0.35,sh[1])],fill='#f3ead6')
        hh=hb[1]-ht[1]; im=portrait(CHAR[k]); s=hh/im.height; im=im.resize((max(1,int(im.width*s)),max(1,int(hh))))
        img.paste(im,(int(base[0]-im.width/2),int(ht[1])),im)
        top=(top[0],max(sh[1],60),top[2])
        # opponent hand placeholder on table in front of character
        hx,hz=on_ell(seat_ang(k),0.9); hp=proj(cm,(hx,TH,hz))
        if hp: r=26*SC/hp[2]*0.35; d.rounded_rectangle([hp[0]-r*1.4,hp[1]-r*0.6,hp[0]+r*1.4,hp[1]+r*0.6],radius=r*0.3,fill=(80,170,255,200),outline='#0b3d6b',width=2)
        if 0<=base[0]<=W*SC: bubbles.append((base[0],top[1],POS[k]+(' · '+ACT[k] if k in ACT else '')))
    placed=[]; fs=24
    for bx,ty,lab in sorted(bubbles):
        tw=d.textlength(lab,font=f(fs)); w2=tw/2+12; bx=min(max(bx,w2+4),W*SC-w2-4); by=max(ty-fs,fs+8)
        while any(abs(bx-px)<w2+pw and abs(by-py)<fs*1.6 for px,py,pw in placed): by-=fs*1.7
        placed.append((bx,by,w2))
        d.line([(bx,by+fs*0.75),(bx,ty)],fill='#6b4a1d',width=2)
        d.rounded_rectangle([bx-w2,by-fs*0.75,bx+w2,by+fs*0.75],radius=12,fill=(255,250,235,240),outline='#6b4a1d',width=2)
        d.text((bx,by),lab,font=f(fs),fill='#2b1d0e',anchor='mm')
    # off-screen indicators
    lft=[];rgt=[]
    for kind,k,x,z in off:
        c,fw,r,u=cm; dxw,dzw=x-c[0],z-c[2]
        side=(dxw*r[0]+dzw*r[2])>0
        (rgt if side else lft).append((kind,k))
    for side,lst in ((0,lft),(1,rgt)):
        for i,(kind,k) in enumerate(lst):
            name='딜러' if kind=='dealer' else POS[k]; act=ACT.get(k,'')
            y=H*SC*0.30+i*56; x0=12 if side==0 else W*SC-12
            txt=('◀ ' if side==0 else '')+name+(' '+act if act else '')+(' ▶' if side==1 else '')
            tw=d.textlength(txt,font=f(24))
            xa=x0 if side==0 else x0-tw-24
            d.rounded_rectangle([xa,y-22,xa+tw+24,y+22],radius=18,fill=(20,16,12,200),outline='#c9a227',width=2)
            d.text((xa+12,y),txt,font=f(24),fill='#f1e3b5',anchor='lm')
    # hero forearms + cards (placeholders)
    for sgn in (-1,1):
        cx=W*SC/2+sgn*W*SC*0.13
        d.polygon([(cx-70,H*SC),(cx+70,H*SC),(cx-sgn*40+45,H*SC*0.74),(cx-sgn*40-45,H*SC*0.74)],fill=(80,170,255,220),outline='#0b3d6b')
    for j,(dxc,rot) in enumerate(((-38,-8),(38,8))):
        card=Image.new('RGBA',(110,150),(0,0,0,0)); cd=ImageDraw.Draw(card)
        cd.rounded_rectangle([0,0,109,149],radius=10,fill='#fbf8f1',outline='#333',width=3)
        cd.text((14,8),'A' if j==0 else 'K',font=f(44),fill='#b3261e' if j==0 else '#111')
        card=card.rotate(-rot,expand=True,resample=Image.BICUBIC)
        img.paste(card,(int(W*SC/2+dxc*SC-card.width/2),int(H*SC*0.80-card.height/2)),card)
    # buttons
    for i,(t,col) in enumerate((('폴드','#7a2b23'),('콜','#2f5d43'),('레이즈','#8a6a1f'))):
        x=W*SC-330+i*110; y=H*SC-70
        d.rounded_rectangle([x-50,y-34,x+50,y+34],radius=14,fill=col,outline='#e6c66b',width=2)
        d.text((x,y),t,font=f(26),fill='white',anchor='mm')
    d.text((24,30),'내 자리 %d번 (%s)'%(hero,POS[hero]),font=f(30),fill='#f1e3b5')
    return img.resize((W,H),Image.LANCZOS)
def topmap():
    S=520; img=Image.new('RGB',(S,S),'#f6f1e6'); d=ImageDraw.Draw(img)
    m=lambda x,z:(S/2+x*130,S/2+z*130)
    pts=[m(*on_ell(a,1.0)) for a in range(0,360,3)]; d.polygon(pts,fill='#1f5a44',outline='#5b3a22',width=8)
    dx,dz=on_ell(-90,1.30); p=m(dx,dz); d.rounded_rectangle([p[0]-30,p[1]-16,p[0]+30,p[1]+16],radius=8,fill='#3b3b48'); d.text(p,'딜러',font=f(18),fill='white',anchor='mm')
    for k in range(1,10):
        p=m(*on_ell(seat_ang(k),1.28)); d.ellipse([p[0]-22,p[1]-22,p[0]+22,p[1]+22],fill='#e8dcc4',outline='#6b4a1d',width=3)
        d.text(p,str(k),font=f(20),fill='#2b1d0e',anchor='mm')
    d.text((S/2,S-26),'구도 종류: 5번 / 4·6번 / 3·7번 / 2·8번 / 1·9번',font=f(18),fill='#2b1d0e',anchor='mm')
    d.text((S/2,22),'딜러 고정 9인 테이블 (위에서 본 모습)',font=f(20),fill='#2b1d0e',anchor='mm')
    return img
views=[render(h) for h in (5,4,3,2,1)]
G=24; cols=3; out=Image.new('RGB',(G+cols*(W+G),90+2*(H+G)+G),'#f6f1e6'); d=ImageDraw.Draw(out)
tm=topmap().resize((H,H))
cells=[tm]+views
for i,v in enumerate(cells):
    r,c=divmod(i,cols); x=G+c*(W+G)+((W-v.width)//2 if v is tm else 0); out.paste(v,(x,90+r*(H+G)))
d.text((G,28),'1인칭 A안 가로 · 가슴 높이 %.2fm · 시야 %d° · %d° 내려다봄 — 상대 몸은 임시 상자, 손은 파란 박스'%(EYE,HFOV,-PITCH),font=f(30),fill='#2b1d0e')
out.save(os.environ.get('OUT','fp_A_chest.png')); print(out.size)
