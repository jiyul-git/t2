"""핸드별 전수 감사. 6개 범주."""
import json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preflop as pf, bot

D = os.path.dirname(os.path.abspath(__file__))
from table import PRE_ORDER, POST_ORDER

def _load():
    for fn in ('hand_archive2.jsonl', 'hand_archive.jsonl'):
        p = os.path.join(D, fn)
        if os.path.exists(p):
            return [json.loads(l) for l in open(p) if l.strip()]
    return []

def check(hand_no):
    recs = _load()
    cand = [x for x in recs if x['hand_no'] == hand_no]
    if not cand: return []
    rec = cand[-1]
    tid = rec.get('tourney')
    prev = [x for x in recs if x['hand_no'] == hand_no - 1 and x.get('tourney') == tid]
    st = {'profiles': rec.get('profiles') or {}}
    p2 = os.path.join(D, 'live2_state.json')
    if not st['profiles'] and os.path.exists(p2):
        try:
            d = json.load(open(p2))
            # pid 기반 → 좌석 기반 매핑
            fl = d.get('field', {})
            hero_pid = fl.get('hero_pid', 0)
            tb = None
            for tid, t in fl.get('tables', {}).items():
                if hero_pid in t['pids']: tb = t; break
            if tb:
                seats = tb.get('seats')
                if seats:
                    st['profiles'] = {str(i+1): fl['players'][str(pid)]['prof']
                                      for i, pid in enumerate(seats) if pid is not None}
                else:
                    alive = [pid for pid in tb['pids']
                             if fl['players'][str(pid)]['stack'] > 0]
                    st['profiles'] = {str(i+1): fl['players'][str(pid)]['prof']
                                      for i, pid in enumerate(alive)}
        except Exception: pass
    if not st['profiles']:
        sp = os.path.join(D, 'live_state.json')
        if os.path.exists(sp):
            try: st = json.load(open(sp))
            except Exception: pass
    out = []
    def flag(cat, msg): out.append('[%s] %s' % (cat, msg))

    pos = rec['pos']; hole = rec['hole']; board = rec['board']
    hero = rec['hero']; bb = rec['blinds'][1]; sb_amt = rec['blinds'][0]
    seat_of = {v: int(k) for k, v in pos.items()}

    # A. 카드
    seen = {}
    for s, h in hole.items():
        for c in h:
            if c in seen: flag('카드', '%s 중복: %s번 & %s번' % (c, s, seen[c]))
            seen[c] = s
    for c in board:
        if c in seen: flag('카드', '보드 %s 가 %s번 홀카드와 중복' % (c, seen[c]))
        seen.setdefault(c, 'board')
    if len(set(board)) != len(board): flag('카드', '보드 내 중복')

    # B. 규칙
    streets = defaultdict(list)
    for e in rec['full_log']: streets[e[0]].append((e[1], e[2], e[3]))
    stacks0 = {int(k): float(v) for k, v in (rec.get('stacks_before') or {}).items()}
    folded_g = set(); allin_g = set()
    spent = defaultdict(float)      # 이전 스트리트까지 누적 투입
    for stt in ('preflop','flop','turn','river'):
        acts = streets.get(stt, [])
        if not acts: continue
        cur = bb if stt == 'preflop' else 0
        minr = bb
        contrib = defaultdict(float)
        if stt == 'preflop':
            if 'SB' in seat_of: contrib[seat_of['SB']] = sb_amt
            if 'BB' in seat_of: contrib[seat_of['BB']] = bb
        acted = []
        for seat, act, amt in acts:
            tc = cur - contrib[seat]
            if seat in folded_g: flag('규칙', '%s번 폴드 후 재액션 (%s)' % (seat, stt))
            if seat in allin_g: flag('규칙', '%s번 올인 후 재액션 (%s)' % (seat, stt))
            if act == 'fold' and tc <= 0: flag('규칙', '%s번 콜비용0인데 폴드 (%s)' % (seat, stt))
            if act == 'check' and tc > 0: flag('규칙', '%s번 콜비용%d인데 체크 (%s)' % (seat, tc, stt))
            if act in ('bet','raise') and amt:
                if amt <= cur: flag('규칙', '%s번 레이즈%d ≤ 현재벳%d (%s)' % (seat, amt, cur, stt))
                elif amt - cur < minr - 1:
                    # 올인이면 최소레이즈 면제. 이전 스트리트 투입분을 빼고 판단.
                    # 이 스트리트에서 낼 수 있는 최대 = 시작스택 - 이전스트리트 투입
                    cap = stacks0.get(seat, 1e9) - spent.get(seat, 0)
                    is_allin = amt >= cap - 2
                    if not is_allin:
                        flag('규칙','%s번 최소레이즈 미달 증분%d<%d (%s)'%(seat,amt-cur,minr,stt))
                if stacks0.get(seat) and amt > stacks0[seat] + contrib[seat] + 1:
                    flag('규칙', '%s번 스택초과 %d>%d (%s)' % (seat, amt, stacks0[seat], stt))
                minr = max(minr, amt-cur); cur = amt; contrib[seat] = amt
            elif act == 'call': contrib[seat] = cur
            elif act == 'allin':
                allin_g.add(seat)
                if amt and amt > cur:
                    minr = max(minr, amt-cur); cur = amt
                contrib[seat] = max(contrib[seat], amt or contrib[seat])
            elif act == 'fold': folded_g.add(seat)
            acted.append(seat)
        for k, v in contrib.items(): spent[k] += v
        order = PRE_ORDER if stt == 'preflop' else POST_ORDER
        expect = [seat_of[p] for p in order if p in seat_of]
        first = []
        for s_ in acted:
            if s_ in first: break
            first.append(s_)
        sub = [s_ for s_ in expect if s_ in first]
        if first != sub: flag('순서', '%s 순서 %s / 정규 %s' % (stt, first, sub))

    # C. 정산
    res = rec['result']
    if res.get('pots'):
        tot = sum(p['amount'] for p in res['pots'])
        if abs(tot - res['pot']) > 2: flag('정산','사이드팟합%d≠팟%d'%(tot,res['pot']))
    if res.get('showdown'):
        pots = res.get('pots') or []
        for idx, pt in enumerate(pots):
            elig = [s for s in pt['eligible'] if str(s) in hole]
            if not elig: continue
            best=None; who=[]
            for s in elig:
                v = bot.eval7(hole[str(s)]+board)
                if best is None or v>best: best=v; who=[s]
                elif v==best: who.append(s)
            # 폴드한 사람은 제외 대상이라 단독 자격이면 검사 생략
            if len(pt['eligible'])>1 and set(who)!=set(pt['winners']):
                folded_any = any(str(s) not in (res.get('hole') or {}) for s in pt['eligible'])
                if not folded_any:
                    flag('정산','팟%d 승자오류 실제%s/기록%s'%(idx,who,pt['winners']))
    elif res.get('hole'): flag('정산','쇼다운 아닌데 패 공개')
    # 올인자가 살아있는데 쇼다운이 안 열렸는가
    _allin = [x for (_, x, a_, _) in rec['full_log'] if a_ == 'allin']
    _folded = {x for (_, x, a_, _) in rec['full_log'] if a_ == 'fold'}
    _still = [int(k) for k in pos if int(k) not in _folded]
    if [x for x in _allin if x not in _folded] and len(_still) >= 2 \
       and not res.get('showdown'):
        flag('정산', '올인자 있는데 쇼다운 누락 (남은 %s)' % _still)
    for s,v in (res.get('stacks') or {}).items():
        if float(v)<0: flag('정산','%s번 스택 음수'%s)
    # 테이블 칩 총량은 밸런싱·이동으로 정상적으로 변한다 → 핸드 내부 보존만 검사(위에서 처리)

    # D. 성향
    for s,h in hole.items():
        if int(s)==hero: continue
        pr=st['profiles'].get(s,{}); t=pr.get('temper',{})
        if not t: continue
        r_=pf.PCT[pf.cls(h)]; loose=t.get('looseness',5)
        for e in rec['full_log']:
            if e[1]!=int(s): continue
            if e[0]=='preflop' and e[2] in ('raise','allin'):
                cap=min(0.92,0.30*(0.42+0.125*loose)*2.6)
                if r_>cap*2.0:
                    flag('성향','%s번 레인지밖 %s(상위%.0f%%) loose%.0f'%(s,''.join(h),r_*100,loose))
    for i in rec.get('intents',[]):
        s=str(i['seat']); c=st['profiles'].get(s,{}).get('concepts',{})
        need={'bluff_2street':'bluff','semibluff':'semibluff','trap':'checkraise',
              'block':'blockbet','pot_control':'potcontrol'}
        if i['plan'] in need and c and c.get(need[i['plan']],5)<1.5:
            flag('성향','%s번 개념없이 %s'%(s,i['plan']))
        if i.get('action') in ('bet','raise') and i['plan'] in ('giveup','showdown'):
            flag('성향','%s번 포기계획인데 벳(%s)'%(s,i['street']))

    # E. 데이터
    seen_i=set()
    for i in rec.get('intents',[]):
        k=(i['street'],i['seat'])
        if k in seen_i: flag('데이터','의도중복 %s'%(k,))
        seen_i.add(k)
        if i['street']=='river' and (i.get('outs') or 0)>0:
            flag('데이터','%s번 리버 드로우 잔존'%i['seat'])
    by=defaultdict(list)
    for i in rec.get('intents',[]): by[i['seat']].append(i)
    for s,its in by.items():
        vals={round(x['rel'] or 0,2) for x in its}
        # rel 0.00/1.00 고정은 정상(완패/넛 유지). 중간값 고정만 갱신 누락 의심.
        streets_seen = {x['street'] for x in its}
        if len(its)>=3 and len(vals)==1 and 0.05 < list(vals)[0] < 0.95 and len(streets_seen)>=3:
            flag('데이터','%s번 rel 고정 %.2f (갱신 누락 의심)'%(s,list(vals)[0]))
        eqs={round(x['eq'] or 0,2) for x in its}
        if len(its)>=3 and len(eqs)==1:
            flag('데이터','%s번 eq 고정 %.2f'%(s,list(eqs)[0]))
    for rd in rec.get('reads',[]):
        if rd['n']==0 and abs(rd['est_bluff']-4.5)>0.6:
            flag('데이터','표본0 추정편향 %.1f'%rd['est_bluff'])
        if not (0<=rd['confidence']<=1): flag('데이터','확신도 이탈 %.2f'%rd['confidence'])

    # F. 구조
    if prev and prev[0]['button']==rec['button']:
        flag('구조','버튼 미회전 %s'%rec['button'])
    for s,v in (rec.get('stacks_before') or {}).items():
        if float(v)<=0 and s in pos: flag('구조','%s번 스택0인데 참여'%s)
    if len(set(pos.values()))!=len(pos): flag('구조','포지션 중복')
    return out

def sweep(verbose=True):
    recs=_load(); total=0; bycat=defaultdict(int)
    for r in recs:
        iss=check(r['hand_no'])
        for x in iss: bycat[x.split(']')[0][1:]]+=1
        if iss and verbose:
            print('#%d'%r['hand_no'])
            for x in iss: print('   ',x)
        total+=len(iss)
    return len(recs), total, dict(bycat)
