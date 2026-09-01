"""각 플레이어가 각자 관찰한 것만으로 상대 성향을 추정한다.
   진짜 프로필은 절대 참조하지 않는다."""
import math, random

# 모집단 사전분포 — 표본이 적을 때 끌려가는 기준점
PRIOR = {'vpip': 0.26, 'pfr': 0.15, 'cbet': 0.55, 'barrel': 0.42,
         'wtsd': 0.28, 'aggr': 5.0, 'bluff': 4.5, 'tight': 5.0,
         'fold_to_bet': 0.52, 'pf_3bet': 0.07, 'pf_fold_to_3bet': 0.55,
         'pf_limp': 0.06, 'rfi_rel': 1.0, 'rfi_rel': 1.0,
         'pf_4bet': 0.04, 'pf_fold_to_4bet': 0.60,
         'sz_mean': 0.62, 'sz_sd': 0.22}

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
            # 스트리트별 폴드 — '플랍은 잘 치는데 턴에서 멈추는' 사람을 구분한다
            'fb_flop': 0, 'f2b_flop': 0,
            'fb_turn': 0, 'f2b_turn': 0,
            'fb_river': 0, 'f2b_river': 0,
            # 프리플랍 공격성 — 3벳 많이 치는 사람과 포스트플랍 공격형은 다르다
            'pf_3bet_opp': 0, 'pf_3bet': 0,
            # 림프 — 기회 대비 실행. limp_p 의 관찰 쪽 짝이다
            'limp_opp': 0, 'limp': 0,
            # 기준 대비 관찰. 절대 빈도(VPIP 34%)만 세면 포지션을 구분하려고
            # 자리마다 따로 세야 하고 표본이 그만큼 쪼개진다.
            # 그 자리의 기준 오픈 폭을 같이 누적하면 한 축으로 합쳐진다 —
            # BTN 40% 와 UTG 40% 가 같은 값이 아니게 된다.
            'rfi_opp': 0, 'rfi_did': 0, 'rfi_exp': 0.0,
            # 기준 대비 관찰. 절대 빈도(VPIP 34%)만 세면 포지션을 구분하려고
            # 자리마다 따로 세야 하고 표본이 그만큼 쪼개진다.
            # 그 자리의 기준 오픈 폭을 같이 누적해두면 한 축으로 합쳐진다 —
            # BTN 40% 와 UTG 40% 가 같은 값이 아니게 된다.
            'rfi_opp': 0, 'rfi_did': 0, 'rfi_exp': 0.0,
            'pf_faced_3bet': 0, 'pf_fold_to_3bet': 0,
            # 4벳 이상. 3벳만 남발하는 사람과 4벳까지 가는 사람은 다르다.
            'pf_4bet_opp': 0, 'pf_4bet': 0,
            'pf_faced_4bet': 0, 'pf_fold_to_4bet': 0,
            # 베팅 사이즈. 평균만이 아니라 **분산**이 중요하다.
            # 항상 60%만 치는 사람과 30~120% 를 섞는 사람은
            # 같은 60% 벳이라도 레인지 해석이 완전히 달라진다.
            'sz_n': 0, 'sz_sum': 0.0, 'sz_sq': 0.0,
            'sz_big': 0, 'sz_small': 0,          # 100%+ / 40%-
            'szr_n': 0, 'szr_sum': 0.0,          # 리버 사이즈만 따로
            'agg_actions': 0, 'passive_actions': 0})

    def observe_size(self, observers, actor, size_frac, street=None):
        """베팅 사이즈 관측. 평균·분산·극단 빈도를 함께 센다."""
        if not size_frac or size_frac <= 0:
            return
        s = min(3.0, float(size_frac))
        for i in observers:
            if i == actor: continue
            r = self.rec(i, actor)
            r['sz_n'] += 1
            r['sz_sum'] += s
            r['sz_sq'] += s*s
            if s >= 1.0: r['sz_big'] += 1
            elif s <= 0.40: r['sz_small'] += 1
            if street == 'river':
                r['szr_n'] += 1; r['szr_sum'] += s

    def observe_4bet(self, observers, actor, had_chance, did_4bet,
                     faced_4bet=False, folded_to_4bet=False):
        for i in observers:
            if i == actor: continue
            r = self.rec(i, actor)
            if had_chance:
                r['pf_4bet_opp'] += 1
                if did_4bet: r['pf_4bet'] += 1
            if faced_4bet:
                r['pf_faced_4bet'] += 1
                if folded_to_4bet: r['pf_fold_to_4bet'] += 1

    def observe_3bet(self, observers, actor, had_chance, did_3bet,
                     faced_3bet=False, folded_to_3bet=False):
        """프리플랍 공격성은 포스트플랍 공격성과 다른 축이다.
           '3벳만 많이 치는 사람'을 구분하려면 따로 세야 한다."""
        for i in observers:
            if i == actor: continue
            r = self.rec(i, actor)
            if had_chance:
                r['pf_3bet_opp'] += 1
                if did_3bet: r['pf_3bet'] += 1
            if faced_3bet:
                r['pf_faced_3bet'] += 1
                if folded_to_3bet: r['pf_fold_to_3bet'] += 1

    def observe_preflop(self, observers, actor, vpip, pfr, limp=False,
                        limp_chance=False, rfi_exp=None):
        """limp_chance — 무저항으로 액션이 돌아온 자리였나(림프가 가능했나).
        기회를 안 세면 얼리에서 늘 폴드하는 사람이 '림프 안 하는 사람'으로
        잡히는데, 그건 림프 성향이 아니라 레인지가 좁은 것이다."""
        for i in observers:
            if i == actor: continue
            r = self.rec(i, actor)
            r['hands'] += 1
            r['vpip'] += 1 if vpip else 0
            r['pfr'] += 1 if pfr else 0
            if limp_chance:
                r['limp_opp'] += 1
                if limp: r['limp'] += 1
            # 무저항으로 돌아온 자리에서만 오픈 기대치를 센다.
            # 이미 레이즈가 있었으면 그건 오픈이 아니라 디펜스다.
            if limp_chance and rfi_exp is not None:
                r['rfi_opp'] += 1
                r['rfi_exp'] += float(rfi_exp)
                if pfr: r['rfi_did'] += 1
            # 무저항으로 돌아온 자리에서만 오픈 기대치를 센다.
            # 이미 레이즈가 있었으면 그건 오픈이 아니라 디펜스다.
            if limp_chance and rfi_exp is not None:
                r['rfi_opp'] += 1
                r['rfi_exp'] += float(rfi_exp)
                if pfr: r['rfi_did'] += 1

    def observe_postflop(self, observers, actor, action, is_cbet_spot, is_barrel_spot,
                         facing_bet=False, street=None):
        for i in observers:
            if i == actor: continue
            r = self.rec(i, actor)
            if facing_bet:
                r['facing_bet'] += 1
                if action == 'fold': r['fold_to_bet'] += 1
                if street in ('flop', 'turn', 'river'):
                    r['fb_' + street] += 1
                    if action == 'fold': r['f2b_' + street] += 1
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
        # PRIOR 의 키는 'fold_to_bet' 이지만 소비 측은 'ftb' 를 본다.
        # 이름을 맞춰주지 않으면 관찰 기록이 없는 상대에서 KeyError 가 난다.
        est = dict(PRIOR)
        est['ftb'] = PRIOR['fold_to_bet']
        for _k in ('ftb_flop', 'ftb_turn', 'ftb_river'):
            est[_k] = PRIOR['fold_to_bet']
        est['sz_big'] = 0.15; est['sz_river'] = PRIOR['sz_mean']; est['sz_n'] = 0
        est['n'] = 0; est['confidence'] = 0.0
        return est
    n = min(r['hands'], o['memory'])
    vpip = r['vpip']/max(1, r['hands'])
    pfr = r['pfr']/max(1, r['hands'])
    cbet = r['cbet']/max(1, r['cbet_opp']) if r['cbet_opp'] else PRIOR['cbet']
    barrel = r['barrel']/max(1, r['barrel_opp']) if r['barrel_opp'] else PRIOR['barrel']
    agg = r['agg_actions']/max(1, r['agg_actions']+r['passive_actions'])
    ftb = (r['fold_to_bet']/r['facing_bet']) if r.get('facing_bet') else PRIOR['fold_to_bet']
    def _rate(num, den, prior):
        return (r.get(num, 0)/r[den]) if r.get(den) else prior
    ftb_f = _rate('f2b_flop', 'fb_flop', PRIOR['fold_to_bet'])
    ftb_t = _rate('f2b_turn', 'fb_turn', PRIOR['fold_to_bet'])
    ftb_r = _rate('f2b_river', 'fb_river', PRIOR['fold_to_bet'])
    tb    = _rate('pf_3bet', 'pf_3bet_opp', PRIOR['pf_3bet'])
    lmp   = _rate('limp', 'limp_opp', PRIOR['pf_limp'])
    # 기준 대비 오픈 폭. 1.0 = 기준대로, 1.5 = 50% 넓게.
    rfi_rel = (r['rfi_did'] / r['rfi_exp']) if r.get('rfi_exp', 0.0) > 0.02 else 1.0
    # 기준 대비 오픈 폭. 1.0 = 기준대로, 1.5 = 50% 넓게.
    if r.get('rfi_exp', 0.0) > 0.02:
        rfi_rel = r['rfi_did'] / r['rfi_exp']
    else:
        rfi_rel = 1.0
    f2tb  = _rate('pf_fold_to_3bet', 'pf_faced_3bet', PRIOR['pf_fold_to_3bet'])
    fb    = _rate('pf_4bet', 'pf_4bet_opp', PRIOR['pf_4bet'])
    f2fb  = _rate('pf_fold_to_4bet', 'pf_faced_4bet', PRIOR['pf_fold_to_4bet'])
    # 사이즈: 평균과 표준편차. 분산이 낮으면 사이즈에서 정보가 안 나온다.
    _sn = r.get('sz_n', 0)
    if _sn >= 2:
        _m = r['sz_sum']/_sn
        _var = max(0.0, r['sz_sq']/_sn - _m*_m)
        sz_mean, sz_sd = _m, _var ** 0.5
    else:
        sz_mean, sz_sd = PRIOR['sz_mean'], PRIOR['sz_sd']
    sz_big = _rate('sz_big', 'sz_n', 0.15)
    sz_riv = (r['szr_sum']/r['szr_n']) if r.get('szr_n') else sz_mean

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
    _sh = lambda v, d, pr: _shrink(v, min(r.get(d, 0), cap), pr, o['skill'], o['overconf'])
    return {'vpip': vpip_e, 'pfr': pfr_e, 'cbet': cbet_e, 'barrel': bar_e, 'ftb': ftb_e,
            'ftb_flop': _sh(ftb_f, 'fb_flop', PRIOR['fold_to_bet']),
            'ftb_turn': _sh(ftb_t, 'fb_turn', PRIOR['fold_to_bet']),
            'ftb_river': _sh(ftb_r, 'fb_river', PRIOR['fold_to_bet']),
            'pf_3bet': _sh(tb, 'pf_3bet_opp', PRIOR['pf_3bet']),
            'pf_limp': _sh(lmp, 'limp_opp', PRIOR['pf_limp']),
            'rfi_rel': _sh(rfi_rel, 'rfi_opp', 1.0),
            'rfi_n': r.get('rfi_opp', 0),
            'rfi_rel': _sh(rfi_rel, 'rfi_opp', 1.0),
            'rfi_n': r.get('rfi_opp', 0),
            'pf_fold_to_3bet': _sh(f2tb, 'pf_faced_3bet', PRIOR['pf_fold_to_3bet']),
            'pf_4bet': _sh(fb, 'pf_4bet_opp', PRIOR['pf_4bet']),
            'pf_fold_to_4bet': _sh(f2fb, 'pf_faced_4bet', PRIOR['pf_fold_to_4bet']),
            'sz_mean': sz_mean, 'sz_sd': sz_sd,
            'sz_big': sz_big, 'sz_river': sz_riv, 'sz_n': _sn,
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
            'ftb_flop': e.get('ftb_flop'), 'ftb_turn': e.get('ftb_turn'),
            'ftb_river': e.get('ftb_river'),
            'pf_3bet': e.get('pf_3bet'), 'pf_fold_to_3bet': e.get('pf_fold_to_3bet'),
            'pf_4bet': e.get('pf_4bet'), 'pf_fold_to_4bet': e.get('pf_fold_to_4bet'),
            'pf_limp': e.get('pf_limp'),
            'rfi_rel': e.get('rfi_rel'), 'rfi_n': e.get('rfi_n'),
            'sz_mean': e.get('sz_mean'), 'sz_sd': e.get('sz_sd'),
            'sz_big': e.get('sz_big'), 'sz_river': e.get('sz_river'),
            'sz_n': e.get('sz_n'),
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
        except (OSError, ValueError): pass      # 없거나 깨진 파일만 무시
    return bk
