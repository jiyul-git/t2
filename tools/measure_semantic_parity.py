import argparse,sys,pathlib,random,hashlib,json,struct,collections,os
ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('output');ap.add_argument('--seed',type=int,default=3000);ap.add_argument('--mode',choices=['regress','live'],default='regress');ap.add_argument('--hands',type=int,default=30);a=ap.parse_args()
root=pathlib.Path(a.root).resolve();sys.path.insert(0,str(root));os.chdir(root)
assert not (root/'telemetry_config.json').exists(), 'isolated audit requires telemetry disabled'
Orig=random.Random;counts=collections.Counter();digest=hashlib.sha256();streams=[]
class TracedRandom(Orig):
 def __init__(self,x=None):
  self.audit_id=len(streams);streams.append(self);counts['instances']+=1
  if x is None: counts['unseeded_instances']+=1
  digest.update(('seed:%s:%r\n'%(self.audit_id,x)).encode());super().__init__(x)
 def random(self):
  v=super().random();counts['random']+=1;digest.update(b'R'+struct.pack('!Id',self.audit_id,v));return v
 def getrandbits(self,k):
  v=super().getrandbits(k);counts['getrandbits']+=1;digest.update(b'B'+struct.pack('!II',self.audit_id,k)+v.to_bytes((k+7)//8,'big'));return v
random.Random=TracedRandom
random.seed(a.seed)
# Patch module singleton methods too; no caller stack/line is hashed, so function extraction is allowed.
module_rng=TracedRandom(a.seed)
for name in ('random','getrandbits','randrange','randint','choice','choices','shuffle','sample','uniform','gauss','normalvariate','triangular','betavariate','expovariate'):
 setattr(random,name,getattr(module_rng,name))
if a.mode=='regress':
 import importlib.util
 spec=importlib.util.spec_from_file_location('audit_regress',root/'tools/regress.py');reg=importlib.util.module_from_spec(spec);spec.loader.exec_module(reg)
 reg.SEEDS=[a.seed];reg.HANDS=a.hands
 fp,stats=reg.fingerprint(); result={'actions':fp,'stats':stats}
else:
 os.environ['T2_LIVE_STATE']=str(root/('audit_state_%s.json'%a.seed));os.environ['T2_BOT_LOG']='2';os.environ['T2_STRICT']='1'
 import live2 as L,session as SE
 rows=[];original_finish=SE.HandRun._finish
 def capture(self,*args,**kw):
  res=original_finish(self,*args,**kw)
  rows.append({'log':self.full_log,'action_meta':getattr(self,'full_action_meta',[]),'stacks':self.h.stacks,'book':self.h.book.d,'board':self.h.board,'hole':self.h.hole,'result':res})
  return res
 SE.HandRun._finish=capture
 L.new_game(entries=18,start_stack=30000,seed=a.seed,hands_per_level=4)
 completed=0;steps=0
 while completed<a.hands and steps<3000:
  r=L.step();steps+=1
  while not r.get('done') and steps<3000:
   raw=r.get('raw') or {};r=L.step('call' if raw.get('tocall',0)>0 else 'check');steps+=1
  if r.get('game_over'):break
  completed+=1
 final=L.load(); result={'actions':hashlib.sha256(json.dumps(rows,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest(),'hands':completed,'records':len(rows),'field':hashlib.sha256(json.dumps(final['field'],sort_keys=True,separators=(',',':')).encode()).hexdigest()}
result['rng_counts']=dict(counts);result['rng_draw_digest']=digest.hexdigest();result['rng_final_state_digest']=hashlib.sha256(repr([r.getstate() for r in streams]).encode()).hexdigest();result['seed']=a.seed;result['mode']=a.mode;result['hands_requested']=a.hands
pathlib.Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result))
