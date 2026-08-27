import sys,json,random,hashlib,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import bot, players

D=os.path.dirname(os.path.abspath(__file__))
SEATS=[1,2,3,4,5,6,7,8]; HERO=7
ORDER=['BTN','SB','BB','UTG','UTG+1','LJ','HJ','CO']
ACTORS=['UTG','UTG+1','LJ','HJ','CO','BTN','SB','BB']

def P(f): return os.path.join(D,f)
def cls(c):
    v=sorted([c[0][0],c[1][0]],key=lambda x:-bot.RV[x])
    if c[0][0]==c[1][0]: return v[0]+v[1]
    return v[0]+v[1]+('s' if c[0][1]==c[1][1] else 'o')

def load(): return json.load(open(P('state.json')))
def save(s): json.dump(s,open(P('state.json'),'w'),indent=1)

def posmap(button):
    idx=SEATS.index(button); return {SEATS[(idx+k)%8]:p for k,p in enumerate(ORDER)}

def deal_next():
    """버튼 회전 → 딜/봉인 → 히어로 차례까지 프리플랍 자동 진행.
       반드시 다음 핸드 상태를 반환한다."""
    s=load(); prof=json.load(open(P('profiles_hidden.json'))); pct=json.load(open(P('pf_rank.json')))
    s['hand_no']+=1
    s['button']=SEATS[(SEATS.index(s['button'])+1)%8]
    pm=posmap(s['button']); inv={v:k for k,v in pm.items()}
    rng=random.Random(os.urandom(16).hex())
    deck=[r+t for r in "23456789TJQKA" for t in "cdhs"]; rng.shuffle(deck)
    hole={}; i=0
    for p in ORDER: hole[p]=[deck[i],deck[i+1]]; i+=2
    board=deck[i:i+5]
    d={'hand_no':s['hand_no'],'level':s['level'],'hero_seat':pm[HERO],'hole':hole,'board':board}
    raw=json.dumps(d,sort_keys=True).encode()
    open(P('hand_%04d.sealed'%s['hand_no']),'wb').write(raw)
    h=hashlib.sha256(raw).hexdigest()[:12]

    sb,bb=s['sb'],s['bb']
    pot=sb+bb+bb   # BB 안테 = 1BB
    log=[]; opened=None; raise_to=bb; live=[]
    for p in ACTORS:
        seat=inv[p]
        if seat==HERO:
            if opened is None: log.append(('HERO_FIRST',None))
            break
        pr=prof[str(seat)]; c=hole[p]; r=pct[cls(c)]
        if opened is None:
            thr=pr['open'].get(p,0)
            if r<=thr:
                raise_to=int(bb*2.5); pot+=raise_to; opened=(seat,p); live=[seat]
                log.append((seat,p,'raise',raise_to))
            else: log.append((seat,p,'fold',0))
        else:
            cp=players.defend_pct(pr,p,opened[1],'call'); tp=players.defend_pct(pr,p,opened[1],'3bet')
            if r<=tp:
                new=int(raise_to*3.5); pot+=new; log.append((seat,p,'3bet',new)); raise_to=new; live.append(seat)
            elif r<=cp:
                pot+=raise_to; log.append((seat,p,'call',raise_to)); live.append(seat)
            else: log.append((seat,p,'fold',0))
    s['pot']=pot; s['raise_to']=raise_to; s['hash']=h; s['await']='hero'
    s['pm']={str(k):v for k,v in pm.items()}; s['prelog']=[list(x) for x in log]
    save(s)
    return {'hand':s['hand_no'],'hash':h,'pos':pm[HERO],'hero':hole[pm[HERO]],
            'pot':pot,'tocall':(0 if opened is None and pm[HERO] not in ('SB','BB')
                 else max(0, raise_to-(bb if pm[HERO]=='BB' else sb if pm[HERO]=='SB' else 0))),
            'log':log,'map':{k:v for k,v in pm.items()},'board':board,'allhole':hole}

# ---- 포스트플랍 액션 순서 (버튼 왼쪽부터, 버튼이 마지막) ----
POST_ORDER = ['SB','BB','UTG','UTG+1','LJ','HJ','CO','BTN']

def street_order(live_positions):
    """살아있는 포지션들을 포스트플랍 정규 순서로 정렬."""
    return [p for p in POST_ORDER if p in live_positions]

def next_actor(live_positions, already_acted):
    o = street_order(live_positions)
    for p in o:
        if p not in already_acted: return p
    return None

def check_order(claimed_sequence, live_positions):
    """서술한 액션 순서가 정규 순서와 일치하는지 검증. 불일치면 예외."""
    correct = street_order(live_positions)
    if list(claimed_sequence) != correct:
        raise ValueError('ACTION ORDER MISMATCH: 서술=%s / 정답=%s' % (claimed_sequence, correct))
    return True
