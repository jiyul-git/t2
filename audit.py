"""핸드별 전수 감사. 6개 범주."""
import json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preflop as pf, bot

D = os.path.dirname(os.path.abspath(__file__))
import table as _TB

# 9맥스 사다리가 8맥스 사다리의 상위집합이다 (UTG+2 만 끼어든다).
# 구 아카이브처럼 현재 사다리와 라벨 집합이 다른 기록은 이 상위집합에서
# 추려야 예전과 같은 순서가 나온다.
_CANON_PRE, _CANON_POST = _TB.orders(9)[1], _TB.orders(9)[2]


def orders_for_labels(labels):
    """그 핸드에 실제로 있었던 포지션 집합의 (PRE, POST).

    8맥스 상수를 고정으로 쓰면 9인 핸드의 UTG+2 가 기대 순서에서 빠져
    정상 핸드에 거짓 '순서' 경보가 난다. 좌석 수가 매 핸드 달라지므로
    사다리도 그 핸드에서 도출해야 한다.

    1) 그 인원수의 orders(n) 라벨 집합이 기록과 같으면 그것을 쓴다.
       헤즈업 포스트플랍([BB, SB])처럼 규칙이 다른 경우까지 여기서 걸린다.
    2) 다르면(구 아카이브) 9맥스 상위집합에서 추린다 — 예전 8맥스 상수로
       추린 것과 같은 결과가 나온다.
    3) 둘 다 아니면 모르는 규약이다. **억지로 정렬하지 않는다.**
    """
    labs = set(labels)
    try:
        _, pre, post = _TB.orders(len(labs))
        if set(pre) == labs:
            return list(pre), list(post)
    except ValueError:
        pass
    pre = [p for p in _CANON_PRE if p in labs]
    post = [p for p in _CANON_POST if p in labs]
    if set(pre) == labs:
        return pre, post
    return None, None

# 어느 파일·어느 상태에서 읽었는지. 감사 결과에 같이 찍는다 —
# current 가 깨져서 stale 로 내려갔는데 정상 감사처럼 보이면 안 된다.
import storage_paths as _SP

SOURCES = []


def _note(kind, detail):
    SOURCES.append('%s: %s' % (kind, detail))


def _load():
    """핸드 아카이브. 어느 파일을 썼는지 SOURCES 에 남긴다.

    `hand_archive.jsonl` 은 `live.py` 시절의 **구형 포맷**이다. 그쪽으로
    내려갔다면 그 사실을 숨기지 않는다.
    """
    del SOURCES[:]
    # 이 상태의 namespace 아카이브를 먼저 본다. 접미사 없는 이름을 고정으로
    # 읽으면 T2_LIVE_STATE 세션에서 **다른 상태의 아카이브**를 감사하게 된다.
    cands = []
    _cur, _src = _SP.resolve_read('archive')
    if _cur:
        cands.append((_cur, 'legacy _alt' if _src == 'legacy_alt' else ''))
    cands.append((os.path.join(D, 'hand_archive.jsonl'), 'legacy 포맷'))
    for p, kind in cands:
        fn = os.path.basename(p)
        if not os.path.exists(p):
            continue
        rows, bad = [], []
        for i, l in enumerate(open(p, encoding='utf-8'), 1):
            if not l.strip():
                continue
            try:
                rows.append(json.loads(l))
            except Exception as e:
                bad.append((i, type(e).__name__))
        _note('archive', '%s%s — %d핸드'
              % (fn, (' (%s)' % kind) if kind else '', len(rows)))
        if bad:
            _note('archive-error',
                  '%s 깨진 줄 %d (%s)' % (fn, len(bad),
                                         ', '.join('%d:%s' % b for b in bad[:5])))
        if kind:
            _note('archive-fallback',
                  '%s 로 내려갔다 — 이 상태의 아카이브(%s)가 없다'
                  % (kind, os.path.basename(_SP.sidecar_path('archive'))))
        return rows
    _note('archive', '없음 — %s / hand_archive.jsonl 둘 다 없다'
          % os.path.basename(_SP.sidecar_path('archive')))
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
        except Exception as e:
            d = None
            _note('state-error',
                  'live2_state.json 파싱 실패 (%s) — 프로필 없이 간다'
                  % type(e).__name__)
        if d is not None:
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
            if st['profiles']:
                _note('profiles', 'live2_state.json')
            else:
                _note('profiles-miss',
                      'live2_state.json 에서 이 핸드의 테이블을 찾지 못했다')
    if not st['profiles']:
        sp = os.path.join(D, 'live_state.json')
        if os.path.exists(sp):
            try:
                st = json.load(open(sp))
                _note('profiles', 'live_state.json (stale fallback)')
            except Exception as e:
                _note('state-error',
                      'live_state.json 파싱 실패 (%s)' % type(e).__name__)
    if st.get('profiles') and not any(x.startswith('profiles:') for x in SOURCES):
        _note('profiles', '아카이브 레코드 자체')
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
    # 사다리는 핸드마다 한 번만 도출한다. 스트리트마다 부르면 모르는 규약일 때
    # 같은 생략 기록이 네 번 쌓인다.
    _pre_o, _post_o = orders_for_labels(pos.values())
    if _pre_o is None:
        # 모르는 포지션 규약이다. 임의 사다리로 정렬하면 거짓 경보가 된다.
        flag('생략', '순서검사 생략 — 알 수 없는 포지션 집합 %s'
             % sorted(set(pos.values())))
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
        if _pre_o is not None:
            order = _pre_o if stt == 'preflop' else _post_o
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
    # 출처를 결과에 실어 보낸다. 깨진 상태 때문에 다른 상태로 내려갔는데
    # 정상 감사처럼 보이는 것을 막는다.
    for src in SOURCES:
        kind = src.split(':', 1)[0]
        if kind.endswith('error'):
            flag('출처오류', src)
        elif kind.endswith('fallback') or kind.endswith('miss'):
            flag('출처경고', src)
    return out


def sources():
    """직전 `_load()` 가 무엇을 읽었는지. 비어 있으면 아직 안 읽었다."""
    return list(SOURCES)


def sweep(verbose=True):
    recs=_load(); total=0; bycat=defaultdict(int)
    if verbose:
        print('출처:')
        for x in (SOURCES or ['(없음)']):
            print('   ', x)
    for r in recs:
        iss=check(r['hand_no'])
        for x in iss: bycat[x.split(']')[0][1:]]+=1
        if iss and verbose:
            print('#%d'%r['hand_no'])
            for x in iss: print('   ',x)
        total+=len(iss)
    return len(recs), total, dict(bycat)
