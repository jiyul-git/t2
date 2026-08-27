import random, json
# 포지션별 오픈 레인지 % (8-max, 20~40bb대 기준)
POS = ['UTG','UTG+1','LJ','HJ','CO','BTN','SB','BB']

ARCH = {
 'NIT':     {'open':{'UTG':.06,'UTG+1':.07,'LJ':.09,'HJ':.11,'CO':.15,'BTN':.22,'SB':.14},
             'call_vs_open':.08,'3bet':.025,'axes':{'aggr':3,'gamble':2,'bluff':2,'value':'lead','tilt':3,'icm':8,'goal':'survive'}},
 'TAG':     {'open':{'UTG':.11,'UTG+1':.13,'LJ':.16,'HJ':.20,'CO':.27,'BTN':.42,'SB':.28},
             'call_vs_open':.13,'3bet':.06,'axes':{'aggr':6,'gamble':4,'bluff':5,'value':'mixed','tilt':3,'icm':6,'goal':'accum'}},
 'LAG':     {'open':{'UTG':.15,'UTG+1':.18,'LJ':.22,'HJ':.27,'CO':.36,'BTN':.55,'SB':.38},
             'call_vs_open':.14,'3bet':.11,'axes':{'aggr':9,'gamble':7,'bluff':8,'value':'xr','tilt':5,'icm':3,'goal':'accum'}},
 'FISH':    {'open':{'UTG':.20,'UTG+1':.22,'LJ':.24,'HJ':.26,'CO':.30,'BTN':.36,'SB':.30},
             'call_vs_open':.30,'3bet':.02,'axes':{'aggr':3,'gamble':6,'bluff':2,'value':'lead','tilt':6,'icm':2,'goal':'spot'}},
 'STATION': {'open':{'UTG':.10,'UTG+1':.12,'LJ':.14,'HJ':.17,'CO':.20,'BTN':.28,'SB':.22},
             'call_vs_open':.34,'3bet':.015,'axes':{'aggr':2,'gamble':8,'bluff':1,'value':'lead','tilt':4,'icm':1,'goal':'spot'}},
 'MANIAC':  {'open':{'UTG':.22,'UTG+1':.26,'LJ':.30,'HJ':.36,'CO':.45,'BTN':.65,'SB':.50},
             'call_vs_open':.14,'3bet':.16,'axes':{'aggr':9,'gamble':9,'bluff':9,'value':'xr','tilt':7,'icm':1,'goal':'accum'}},
}

def assign(seats, rng):
    # 실제 라이브 MTT 분포에 가깝게
    bag = ['TAG','TAG','FISH','FISH','STATION','NIT','LAG','MANIAC']
    rng.shuffle(bag)
    out={}
    for s,t in zip(seats,bag):
        out[s]={'type':t, **ARCH[t]['axes'],
                'open':ARCH[t]['open'],'call_vs_open':ARCH[t]['call_vs_open'],'3bet':ARCH[t]['3bet']}
    return out

# 디펜스 폭: 오프너 포지션이 늦을수록 넓게, SB는 OOP라 BB보다 좁게
OPENER_MULT = {'UTG':1.4,'UTG+1':1.5,'LJ':1.8,'HJ':2.2,'CO':2.9,'BTN':4.2,'SB':4.6}
DEF_POS_MULT = {'BB':1.0,'SB':0.55,'BTN':0.9,'CO':0.7,'HJ':0.6,'LJ':0.5,'UTG+1':0.45,'UTG':0.4}

def defend_pct(prof, def_pos, opener_pos, kind='call', open_bb=2.5):
    base = prof['call_vs_open'] if kind=='call' else prof['3bet']
    m = OPENER_MULT.get(opener_pos,2.0) * DEF_POS_MULT.get(def_pos,0.7)
    m *= (2.5/max(1.5,open_bb))**0.6      # 작은 오픈일수록 넓게 방어
    return min(0.85, base*m)

def defend_action(prof, def_pos, opener_pos, hand_pct, open_bb=2.5):
    """3벳/콜/폴드를 중첩 없는 연속 구간으로 판정"""
    tp = defend_pct(prof, def_pos, opener_pos, '3bet', open_bb)
    cp = defend_pct(prof, def_pos, opener_pos, 'call', open_bb)
    if hand_pct <= tp: return '3bet', tp, tp+cp
    if hand_pct <= tp+cp: return 'call', tp, tp+cp
    return 'fold', tp, tp+cp
