#!/usr/bin/env python3
"""T2 airport approved scene: extract four real transparency sprites and fill behind.
Build-time only. Does not touch game, server or player data. Requires cv2, numpy, PIL."""
from pathlib import Path
import json
import cv2
import numpy as np
from PIL import Image

POLYS={
'tiger':[(63,429),(55,404),(63,367),(70,326),(93,294),(104,257),(118,239),(124,217),(145,210),(157,214),(176,203),(194,214),(220,220),(236,237),(254,262),(269,293),(272,316),(287,353),(303,382),(297,429)],
'rabbit':[(273,429),(274,406),(280,389),(281,362),(291,348),(294,313),(302,290),(283,276),(279,247),(290,221),(305,205),(320,211),(329,219),(339,247),(360,238),(368,213),(388,202),(407,209),(433,234),(442,259),(432,279),(432,302),(448,321),(455,351),(467,394),(477,429)],
'turtle':[(470,429),(471,405),(483,380),(490,354),(506,337),(513,323),(512,299),(519,280),(543,262),(552,255),(569,244),(590,245),(610,242),(638,253),(659,275),(656,297),(669,309),(667,327),(684,353),(688,382),(703,415),(709,429)],
'penguin':[(667,429),(674,408),(687,384),(695,366),(710,351),(725,342),(747,334),(762,327),(782,324),(796,328),(817,344),(831,359),(839,381),(847,407),(847,429)]
}
SEEDS={
'tiger':[(168,278,30,36),(137,356,36,34),(217,378,22,27)],
'rabbit':[(365,290,31,33),(358,386,31,29),(415,374,13,20)],
'turtle':[(577,315,34,34),(596,385,31,29),(544,377,16,15)],
'penguin':[(770,380,32,26),(744,414,25,16)]
}
def build(src,dst):
    dst.mkdir(parents=True,exist_ok=True)
    orig=np.array(Image.open(src).convert('RGB'))
    h,w=orig.shape[:2]
    assert (w,h)==(648,323), 'Artwork geometry changed; do not guess masks'
    sx,sy=w/864,h/430
    allmask=np.zeros((h,w),np.uint8)
    sprites=[]
    for name,points in POLYS.items():
        mask=np.zeros((h,w),np.uint8)
        pts=np.rint(np.array(points)*[sx,sy]).astype('int32')
        cv2.fillPoly(mask,[pts],cv2.GC_PR_FGD)
        for x,y,rx,ry in SEEDS[name]:
            cv2.ellipse(mask,(round(x*sx),round(y*sy)),
                        (round(rx*sx),round(ry*sy)),0,0,360,cv2.GC_FGD,-1)
        cv2.grabCut(orig[:,:,::-1].copy(),mask,None,np.zeros((1,65),np.float64),
                    np.zeros((1,65),np.float64),5,cv2.GC_INIT_WITH_MASK)
        fg=np.uint8((mask==cv2.GC_FGD)|(mask==cv2.GC_PR_FGD))*255
        fg=cv2.GaussianBlur(fg,(3,3),.65)
        ys,xs=np.where(fg>8)
        x0,y0,x1,y1=int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1
        output='character_'+name+'.webp'
        Image.fromarray(np.dstack([orig,fg])[y0:y1,x0:x1].copy(),'RGBA').save(
            dst/output,'WEBP',quality=79,method=6)
        sprites.append(dict(name=name,x=x0,y=y0,w=x1-x0,h=y1-y0,file=output))
        allmask=np.maximum(allmask,fg)
    hole=cv2.dilate(np.uint8(allmask>64)*255,np.ones((5,5),np.uint8),iterations=1)
    back=cv2.inpaint(orig[:,:,::-1].copy(),hole,13,cv2.INPAINT_TELEA)[:,:,::-1]
    Image.fromarray(back,'RGB').save(dst/'airport_background.webp','WEBP',quality=70,method=6)
    manifest=dict(size=[w,h],source=src.name,characters=sprites,
                  generated_by='ui/tools/build_airport_layers.py')
    (dst/'layers.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    reconstructed=Image.fromarray(back,'RGB').convert('RGBA')
    for o in sprites: reconstructed.alpha_composite(
        Image.open(dst/o['file']).convert('RGBA'),(o['x'],o['y']))
    arr=np.array(reconstructed.convert('RGB')).astype(float)
    err=float(np.mean(np.abs(arr-orig)))
    other=(allmask<=8)
    outside=float(np.mean(np.abs(arr[other]-orig[other])))
    if err>=9 or outside>=5:
        raise RuntimeError('Layer verification failed: mean_abs=%.4f unchanged=%.4f' % (err,outside))
    print('PASS scene sprite compositor, mean_abs_error=%.4f unmasked_error=%.4f' % (err,outside))
if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser()
    a.add_argument('--source',default='ui/web/assets/t2-airport/lobby_hero_night.webp')
    a.add_argument('--out',default='ui/web/assets/t2-airport/layers')
    args=a.parse_args()
    build(Path(args.source),Path(args.out))
