"""각 플레이어가 각자 관찰한 것만으로 상대 성향을 추정한다.
   진짜 프로필은 절대 참조하지 않는다."""
import math, random

# 모집단 사전분포 — 표본이 적을 때 끌려가는 기준점
PRIOR = {'vpip': 0.26, 'pfr': 0.15, 'cbet': 0.55, 'barrel': 0.42,
         'wtsd': 0.28, 'aggr': 5.0, 'bluff': 4.5, 'tight': 5.0,
         'fold_to_bet': 0.52}

# 관찰력: 표본을 얼마나 잘 반영하는가 / 과신 정도 / 노이즈
import archetypes as A
FAMILY_OBS = {
    'reg':    dict(skill=0.88, overconf=1.0, noise=0.07, memory=80),
    'nit':    dict(skill=0.62, overconf=0.9, noise=0.11, memory=60),
    'fish':   dict(skill=0.10, overconf=0.75,noise=0.29, memory=13),
    'maniac': dict(skill=0.52, overconf=2.0, noise=0.19, memory=25),
    'tilt':   dict(skill=0.45, overconf=1.6, noise=0.22, memory=20),
    'live':   dict(skill=0.35, overconf=1.1, noise=0.20, memory=30),
}
def obs_from_profile(prof):
    """개인 벡터에서 관찰력을 파생."""
    t = prof.get('temper')
    if not t: return None
    att = t['attention']; adp = t['adaptability']; cons = t['consistency']
    rr = prof['concepts'].get('range_read', 4); st = prof['concepts'].get('sizing_tell', 4)
    return dict(skill=max(0.03, min(0.98, (att*0.5 + rr*0.3 + st*0.2)/10.0)),
                overconf=max(0.6, min(2.4, 1.8 - 0.09*cons)),
                noise=max(0.03, min(0.35, 0.34 - 0.028*att)),
                memory=int(max(8, min(120, 6*att + 4*adp))))

class _ObsMap(dict):
    def __getitem__(self, k):
        if isinstance(k, dict):
            o = obs_from_profile(k)
            if o: return o
            k = k.get('type', 'TAG')
        fam = A.ARCHETYPES[k][6] if k in A.ARCHETYPES else 'reg'
        return FAMILY_OBS[fam]
    def get(self, k, d=None):
        try: return self[k]
        except Exception: return d
OBSERVER = _ObsMap()
DEFAULT_OBS = dict(skill=0.5, overconf=1.0, noise=0.15, memory=40)


class Book:
    """관찰자 i가 상대 j에 대해 쌓은 장부."""
    def __init__(self):
        self.d = {}          # (i, j) -> counters

    def _k(self, i, j): return '%s>%s' % (i, j)

    def rec(self, i, j):
        return self.d.setdefault(self._k(i, j), {
            'hands': 0, 'vpip': 0, 'pfr': 0,
            'cbet_opp': 0, 'cbet': 0,
            'barrel_opp': 0, 'barrel': 0,
            'showdowns': 0, 'sd_strong': 0, 'sd_weak': 0,
            'facing_bet': 0, 'fold_to_bet': 0,
            'agg_actions': 0, 'passive_actions': 0})

    def observe_preflop(self, observers, actor, vpip, pfr):
        for i in observers:
            if i == actor: continue
            r = self.rec(i, actor)
            r['hands'] += 1
            r['vpip'] += 1 if vpip else 0
            r['pfr'] += 1 if pfr else 0

    def observe_postflop(self, observers, actor, action, is_cbet_spot, is_barrel_spot,
                         facing_bet=False):
        for i in observers:
            if i == actor: continue
            r = self.rec(i, actor)
            if facing_bet:
                r['facing_bet'] += 1
                if action == 'fold': r['fold_to_bet'] += 1
            if is_cbet_spot:
                r['cbet_opp'] += 1
                if action in ('bet', 'raise'): r['cbet'] += 1
            if is_barrel_spot:
                r['barrel_opp'] += 1
                if action in ('bet', 'raise'): r['barrel'] += 1
            if action in ('bet', 'raise'): r['agg_actions'] += 1
            elif action in ('check', 'call'): r['passive_actions'] += 1

    def observe_showdown(self, observers, actor, hand_pct, was_aggressor):
        """깐 패가 약한데 공격적이었다면 블러프 성향의 증거."""
        for i in observers:
            if i == actor: continue
            r = self.rec(i, actor)
            r['showdowns'] += 1
            if hand_pct > 0.45 and was_aggressor: r['sd_weak'] += 1
            elif hand_pct < 0.20: r['sd_strong'] += 1


def _shrink(obs_val, n, prior, skill, overconf):
    """표본이 적으면 사전분포로 수축. 과신형은 표본을 실제보다 크게 취급."""
    eff_n = n * skill * overconf
    w = eff_n / (eff_n + 12.0)
    return prior*(1-w) + obs_val*w


def estimate(book, observer, target, observer_type, rng=None):
    """관찰자 관점에서 본 target의 추정 성향. 진짜 값은 안 봄."""
    # 전역 random 폴백을 두지 않는다. 전역 RNG 는 OS 엔트로피로 시드되므로
    # 폴백이 한 번이라도 타면 같은 시드가 재현되지 않는다.
    # 추정 노이즈는 '이 관찰자가 이 상대를 어떻게 보는가'의 일부이므로
    # 호출자의 결정론적 rng 를 반드시 받아야 한다.
    if rng is None:
        raise ValueError('reads.estimate: rng 는 필수입니다 (전역 RNG 사용 금지)')
    o = OBSERVER.get(observer_type, DEFAULT_OBS)
    r = book.d.get(book._k(observer, target))
    if not r or r['hands'] == 0:
        est = dict(PRIOR); est['n'] = 0; est['confidence'] = 0.0
        return est
    n = min(r['hands'], o['memory'])
    vpip = r['vpip']/max(1, r['hands'])
    pfr = r['pfr']/max(1, r['hands'])
    cbet = r['cbet']/max(1, r['cbet_opp']) if r['cbet_opp'] else PRIOR['cbet']
    barrel = r['barrel']/max(1, r['barrel_opp']) if r['barrel_opp'] else PRIOR['barrel']
    agg = r['agg_actions']/max(1, r['agg_actions']+r['passive_actions'])
    ftb = (r['fold_to_bet']/r['facing_bet']) if r.get('facing_bet') else PRIOR['fold_to_bet']

    cap = o['memory']                      # 기억 한계는 기회 횟수에도 적용
    n_cb = min(r['cbet_opp'], cap)
    n_br = min(r['barrel_opp'], cap)
    vpip_e = _shrink(vpip, n, PRIOR['vpip'], o['skill'], o['overconf'])
    pfr_e  = _shrink(pfr,  n, PRIOR['pfr'],  o['skill'], o['overconf'])
    cbet_e = _shrink(cbet, n_cb, PRIOR['cbet'], o['skill'], o['overconf'])
    bar_e  = _shrink(barrel, n_br, PRIOR['barrel'], o['skill'], o['overconf'])
    agg_e  = _shrink(agg, n, 0.35, o['skill'], o['overconf'])
    ftb_e  = _shrink(ftb, min(r.get('facing_bet', 0), cap), PRIOR['fold_to_bet'],
                     o['skill'], o['overconf'])

    # 축 역산 — 모집단 평균으로부터의 '편차'로 계산한다
    aggr_axis = 1 + 9*agg_e
    bluff_axis = (4.5
                  + 7.0*(bar_e - PRIOR['barrel'])      # 배럴 빈도가 가장 강한 신호
                  + 3.0*(cbet_e - PRIOR['cbet'])
                  + 2.0*(vpip_e - PRIOR['vpip']))      # 루즈할수록 약패 비중↑
    if r['showdowns'] >= 2:
        weak_rate = r['sd_weak']/r['showdowns']        # 약패로 공격했다 깐 비율
        strong_rate = r['sd_strong']/r['showdowns']
        seen = min(1.0, r['showdowns']/8.0) * o['skill']
        bluff_axis += seen * (7.0*weak_rate - 3.5*strong_rate)
    bluff_axis = max(1.0, min(10.0, bluff_axis))
    aggr_axis  = max(1.0, min(10.0, aggr_axis))
    tight_axis = max(1.0, min(10.0, 10 - 9*min(1.0, vpip_e/0.55)))

    # 오독 노이즈
    ns = o['noise'] * (1.0 - min(0.7, n/60.0))
    jitter = lambda x: max(1.0, min(10.0, x*(1 + rng.uniform(-ns, ns))))
    conf = min(1.0, (n*o['skill'])/25.0)
    return {'vpip': vpip_e, 'pfr': pfr_e, 'cbet': cbet_e, 'barrel': bar_e, 'ftb': ftb_e,
            'aggr': jitter(aggr_axis), 'bluff': jitter(bluff_axis),
            'tight': jitter(tight_axis), 'n': r['hands'], 'confidence': round(conf, 2)}


def perceived_profile(book, observer, target, observer_type, rng=None):
    """'내가 관찰한 상대'. 진짜 프로필이 아니다 — 이걸 넘겨야 정보 누출이 없다.

    익스플로잇에 필요한 축을 전부 싣는다.
    예전에는 bluff/aggr 만 반환하고 vpip·cbet·barrel·tight 를 버렸는데,
    상대를 착취하려면 '얼마나 씨벳하는가', '큰 벳에 접는가'가 오히려 더 중요하다.
    """
    e = estimate(book, observer, target, observer_type, rng)
    return {'bluff': e['bluff'], 'aggr': e['aggr'], 'tight': e['tight'],
            'vpip': e['vpip'], 'pfr': e['pfr'],
            'cbet': e['cbet'], 'barrel': e['barrel'], 'ftb': e['ftb'],
            'type': None, 'confidence': e['confidence'], 'n': e['n']}


import json as _json, os as _os

# 전역 기본 경로는 두지 않는다.
# 예전에는 book.json 하나를 모두가 공유해서 (1) 대회끼리 리딩이 섞이고
# (2) 같은 시드가 디스크 상태에 따라 다르게 재생됐다.
# 장부는 그것을 소유한 대회 상태에 저장한다. 경로를 쓰려면 반드시 명시할 것.

def save_book(bk, path):
    _json.dump(bk.d, open(path, 'w'))

def load_book(path):
    bk = Book()
    p = path
    if _os.path.exists(p):
        try: bk.d = _json.load(open(p))
        except Exception: pass
    return bk
