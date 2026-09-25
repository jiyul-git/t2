"""각 플레이어가 각자 관찰한 것만으로 상대 성향을 추정한다.
   진짜 프로필은 절대 참조하지 않는다."""
import math, random
import json as _json_mod, os.path as _os_path

# 모집단 사전분포 — 표본이 적을 때 끌려가는 기준점
PRIOR = {'vpip': 0.26, 'pfr': 0.15, 'cbet': 0.55, 'barrel': 0.42,
         'wtsd': 0.28, 'aggr': 5.0, 'bluff': 4.5, 'tight': 5.0,
         'fold_to_bet': 0.52, 'pf_3bet': 0.07, 'pf_fold_to_3bet': 0.55,
         'pf_limp': 0.06, 'rfi_rel': 1.0,
         'pf_fold_after_limp_raise': 0.48,
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
        defaults = {
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
            # 림프 후 첫 레이즈를 다시 마주했을 때의 반응.
            # 포스트플랍 fold_to_bet 과 섞으면 안 된다.
            'pf_faced_limp_raise': 0, 'pf_fold_after_limp_raise': 0,
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
            'agg_actions': 0, 'passive_actions': 0,
            # 콜 후 squeeze를 맞은 상태는 opener의 fold-to-3bet/4bet과 다르다.
            'pf_backraise_opp': 0, 'pf_backraise': 0,
            'pf_call_faced_squeeze': 0, 'pf_fold_after_call_squeeze': 0,
        }
        key = self._k(i, j)
        r = self.d.setdefault(key, {})
        # 과거 저장 장부에도 새 필드를 안전하게 채운다.
        for k, v in defaults.items():
            r.setdefault(k, v)
        return r

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

    def observe_backraise(self, observers, actor, had_chance, did_backraise,
                          folded_to_squeeze=False):
        """첫 오픈을 콜한 뒤 squeeze/3bet이 돌아왔을 때의 반응.

        opener의 fold-to-3bet / 4bet 빈도와 섞지 않는다.
        """
        if not had_chance:
            return
        for i in observers:
            if i == actor: continue
            r = self.rec(i, actor)
            r['pf_backraise_opp'] += 1
            if did_backraise:
                r['pf_backraise'] += 1
            r['pf_call_faced_squeeze'] += 1
            if folded_to_squeeze:
                r['pf_fold_after_call_squeeze'] += 1

    def observe_limp_raise(self, observers, actor, faced, folded):
        """림프한 뒤 첫 레이즈가 돌아왔을 때의 반응을 센다.

        이 축은 포스트플랍 fold_to_bet 과 다르다. 아이소 판단에서
        '이 림퍼가 레이즈에 실제로 접는가'를 보려면 전용 관측이 필요하다.
        """
        if not faced:
            return
        for i in observers:
            if i == actor: continue
            r = self.rec(i, actor)
            r['pf_faced_limp_raise'] += 1
            if folded:
                r['pf_fold_after_limp_raise'] += 1

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
    flr   = _rate('pf_fold_after_limp_raise', 'pf_faced_limp_raise',
                  PRIOR['pf_fold_after_limp_raise'])
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
    backr = _rate('pf_backraise', 'pf_backraise_opp', 0.0)
    fcsq  = _rate('pf_fold_after_call_squeeze', 'pf_call_faced_squeeze', 0.0)
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
            'pf_fold_after_limp_raise': _sh(
                flr, 'pf_faced_limp_raise', PRIOR['pf_fold_after_limp_raise']),
            'pf_limp_raise_n': r.get('pf_faced_limp_raise', 0),
            'rfi_rel': _sh(rfi_rel, 'rfi_opp', 1.0),
            'rfi_n': r.get('rfi_opp', 0),
            'pf_fold_to_3bet': _sh(f2tb, 'pf_faced_3bet', PRIOR['pf_fold_to_3bet']),
            'pf_4bet': _sh(fb, 'pf_4bet_opp', PRIOR['pf_4bet']),
            'pf_fold_to_4bet': _sh(f2fb, 'pf_faced_4bet', PRIOR['pf_fold_to_4bet']),
            # backraise/fold-to-squeeze는 아직 전략 소비 전 SHADOW 관측이다.
            'pf_backraise': backr,
            'pf_backraise_n': r.get('pf_backraise_opp', 0),
            'pf_fold_after_call_squeeze': fcsq,
            'pf_call_faced_squeeze_n': r.get('pf_call_faced_squeeze', 0),
            'sz_mean': sz_mean, 'sz_sd': sz_sd,
            'sz_big': sz_big, 'sz_river': sz_riv, 'sz_n': _sn,
            'aggr': jitter(aggr_axis), 'bluff': jitter(bluff_axis),
            'tight': jitter(tight_axis), 'n': r['hands'], 'confidence': round(conf, 2)}


def infer_latent(est):
    """관찰 가능한 행동 빈도에서 **잠재요인을 추정**한다. (study, aggro, exp)

    관찰자는 상대의 개념 벡터를 볼 수 없다. 볼 수 있는 건 행동뿐이다.
    그래서 먼저 '이 사람이 어떤 부류로 보이는가'를 잡고, 거기서 개념을
    역으로 예상한다 — 사람이 실제로 하는 추론 순서다.

    근거로 쓰는 건 전부 관찰 가능한 것이다.
      림핑 격차(vpip-pfr) — 크면 공부가 덜 된 신호
      c벳/배럴 빈도       — 공격 기질
      사이즈 편차(sz_sd)  — 작으면 정형화된 레귤러
      3벳/4벳 빈도        — 레인지 개념의 대리 지표
    """
    vpip = est.get('vpip', PRIOR['vpip'])
    pfr = est.get('pfr', PRIOR['pfr'])
    gap = max(0.0, vpip - pfr)
    sz_sd = est.get('sz_sd') or PRIOR['sz_sd']
    tb = est.get('pf_3bet') or PRIOR['pf_3bet']
    cbet = est.get('cbet') or PRIOR['cbet']
    barrel = est.get('barrel') or PRIOR['barrel']

    # 공부량: 림핑이 적고, 사이즈가 정형화돼 있고, 3벳을 쓸수록 높게 본다.
    study = 5.0
    study += -9.0*(gap - 0.10)          # 격차 0.10 을 기준
    study += -6.0*(sz_sd - 0.22)        # 편차가 작을수록 공부한 티
    study += 22.0*(tb - 0.07)
    # 공격 기질: c벳·배럴·PFR 비중
    aggro = 5.0 + 6.0*(cbet - 0.55) + 5.0*(barrel - 0.42)
    aggro += 8.0*(pfr - 0.15)
    # 경험: 공부와 공격의 중간쯤에 두되, 극단은 완화한다.
    exp = 5.0 + 0.45*(study - 5.0) + 0.20*(aggro - 5.0)
    _c = lambda v: max(0.0, min(10.0, v))
    return _c(study), _c(aggro), _c(exp)


def estimate_concepts(est, observer_type='TAG', rng=None, keys=None):
    """추정한 잠재요인으로 **상대의 개념을 예상**한다. {개념: 값} + 불확실성.

    생성에 쓴 것과 같은 LOADING 을 관찰자가 역으로 돌린다. 관찰자는 필드에
    사람이 어떻게 분포하는지 경험으로 알기 때문에, '레귤러로 보이면 팟오즈는
    알 테고 블로커는 반반이겠다'는 추론이 가능하다.

    **실제 개념 벡터는 보지 않는다.** est 는 행동 빈도만 담고 있다.
    표본이 적으면 사전분포(중앙값 5.0) 쪽으로 끌어당긴다 — 모르면 평균으로
    보는 것이 맞고, 그래야 초반에 과신하지 않는다.
    """
    import persona as PS
    study, aggro, exp = infer_latent(est)
    n = est.get('n', 0) or 0
    conf = est.get('confidence', 0.0) or 0.0
    o = OBSERVER.get(observer_type, DEFAULT_OBS)
    # 표본이 쌓일수록 추정을 믿는다. 관찰력이 낮으면 덜 믿는다.
    w = max(0.0, min(0.85, (n / (n + 12.0)) * (0.45 + 0.6*o['skill']) * (0.5 + 0.5*conf)))
    out, unc = {}, {}
    for k, (ws, wa, we, base) in PS.LOADING.items():
        if keys and k not in keys:
            continue
        v = base + ws*(study-5.0)*1.05 + wa*(aggro-5.0)*0.85 + we*(exp-5.0)*0.85
        v = 5.0 + (v - 5.0)*w                    # 표본이 없으면 평균으로 수렴
        if rng is not None and o['noise']:
            v += rng.gauss(0, o['noise']*3.0*(1.0 - w))
        out[k] = round(max(0.0, min(10.0, v)), 1)
        # 불확실성: 표본이 적을수록, 개념 분산이 클수록 크다.
        unc[k] = round((1.0 - w) * PS.SPREAD.get(k, PS.DEFAULT_SPREAD), 2)
    return {'concepts': out, 'uncertainty': unc,
            'latent': {'study': round(study, 1), 'aggro': round(aggro, 1),
                       'exp': round(exp, 1)},
            'weight': round(w, 2), 'n': n}


def perceived_profile(book, observer, target, observer_type, rng=None):
    """'내가 관찰한 상대'. 진짜 프로필이 아니다 — 이걸 넘겨야 정보 누출이 없다.

    익스플로잇에 필요한 축을 전부 싣는다.
    예전에는 bluff/aggr 만 반환하고 vpip·cbet·barrel·tight 를 버렸는데,
    상대를 착취하려면 '얼마나 씨벳하는가', '큰 벳에 접는가'가 오히려 더 중요하다.
    """
    e = estimate(book, observer, target, observer_type, rng)
    _ec = estimate_concepts(e, observer_type, rng)
    return {'bluff': e['bluff'], 'aggr': e['aggr'], 'tight': e['tight'],
            'vpip': e['vpip'], 'pfr': e['pfr'],
            'cbet': e['cbet'], 'barrel': e['barrel'], 'ftb': e['ftb'],
            'ftb_flop': e.get('ftb_flop'), 'ftb_turn': e.get('ftb_turn'),
            'ftb_river': e.get('ftb_river'),
            'pf_3bet': e.get('pf_3bet'), 'pf_fold_to_3bet': e.get('pf_fold_to_3bet'),
            'pf_4bet': e.get('pf_4bet'), 'pf_fold_to_4bet': e.get('pf_fold_to_4bet'),
            'pf_backraise': e.get('pf_backraise'),
            'pf_backraise_n': e.get('pf_backraise_n'),
            'pf_fold_after_call_squeeze': e.get('pf_fold_after_call_squeeze'),
            'pf_call_faced_squeeze_n': e.get('pf_call_faced_squeeze_n'),
            'pf_limp': e.get('pf_limp'),
            'pf_fold_after_limp_raise': e.get('pf_fold_after_limp_raise'),
            'pf_limp_raise_n': e.get('pf_limp_raise_n'),
            'rfi_rel': e.get('rfi_rel'), 'rfi_n': e.get('rfi_n'),
            'sz_mean': e.get('sz_mean'), 'sz_sd': e.get('sz_sd'),
            'sz_big': e.get('sz_big'), 'sz_river': e.get('sz_river'),
            'sz_n': e.get('sz_n'),
            'type': None, 'confidence': e['confidence'], 'n': e['n'],
            # 관찰된 행동에서 **예상한** 상대 개념. 실제 벡터가 아니다.
            # 이게 없으면 소비 측(bluff_mode 의 sizing_tell 등)이 늘 기본값
            # 0.5 로 떨어져 '상대가 사이즈를 읽는가'가 항상 반반이 됐다.
            'est_concepts': _ec['concepts'], 'est_uncertainty': _ec['uncertainty'],
            'est_latent': _ec['latent'], 'est_weight': _ec['weight'],
            'sizing_tell': _ec['concepts'].get('sizing_tell'),
            'range_read': _ec['concepts'].get('range_read'),
            'fold': e.get('ftb')}


def range_profile(perceived):
    """공개 관측만으로 만든 상대 프리플랍 레인지용 profile.

    상대의 실제 persona/temper 를 읽으면 관찰자가 알 수 없는 정보를
    레인지 추정에 섞게 된다. perceived_profile 의 행동 기반 추정치만
    persona 인터페이스 모양으로 바꾼다.

    직접 관측하기 어려운 기질은 모집단 중립값 5로 둔다.
    """
    p = perceived or {}
    c = dict(p.get('est_concepts') or {})
    # estimate_concepts 가 비어 있는 외부/구형 호출도 평균값으로 안전하게.
    if not c:
        try:
            import persona as _PS
            c = {k: 5.0 for k in _PS.ALL_CONCEPTS}
        except Exception:
            c = {}
    ag = max(0.0, min(10.0, float(p.get('aggr', 5.0) or 5.0)))
    tight = max(0.0, min(10.0, float(p.get('tight', 5.0) or 5.0)))
    return {
        'type': 'PERCEIVED',
        'concepts': c,
        'temper': {
            'aggression': ag,
            'looseness': 10.0 - tight,
            'gamble': 5.0,
            'discipline': 5.0,
            'adaptability': 5.0,
            'consistency': 5.0,
            'attention': 5.0,
            'slowplay_taste': 5.0,
        },
    }


import json as _json, os as _os

# 전역 기본 경로는 두지 않는다.
# 예전에는 book.json 하나를 모두가 공유해서 (1) 대회끼리 리딩이 섞이고
# (2) 같은 시드가 디스크 상태에 따라 다르게 재생됐다.
# 장부는 그것을 소유한 대회 상태에 저장한다. 경로를 쓰려면 반드시 명시할 것.

def save_book(bk, path):
    _json.dump(bk.d, open(path, 'w', encoding='utf-8'))

def load_book(path):
    bk = Book()
    p = path
    if _os.path.exists(p):
        try: bk.d = _json.load(open(p, encoding='utf-8'))
        except (OSError, ValueError): pass      # 없거나 깨진 파일만 무시
    return bk


# ===================== OpponentBelief =====================
# 관찰자는 상대의 개념 벡터를 **볼 수 없다.** 볼 수 있는 것은 행동 빈도뿐이다.
# 그래서 순서가 이렇게 되어야 한다.
#
#   관찰 장부 → 행동 성향 추정 → "저 사람은 TAG처럼 보인다"(가설)
#            → "그러면 range_read 는 높을 가능성이 있다"(개념 belief)
#
# 라벨을 확정하고 `if style == 'TAG': range_read = 7` 로 쓰면 그 순간 다시
# 라벨이 개념의 원인이 된다. 그래서 스타일은 **단일 라벨이 아니라 분포**로 두고,
# 개념 belief 는 그 분포로 가중 혼합한다. 관찰자마다 표본과 관찰력이 다르므로
# 같은 상대를 봐도 서로 다른 belief 를 갖는다.

# 스타일별 '이렇게 행동할 것이다'라는 관찰자의 기대치(행동 서명).
# 개념이 아니라 **관찰 가능한 지표만** 쓴다.
# 라벨별 행동 서명도 **실측**에서 읽는다(tools/calibrate.calibrate_behavior).
# 손으로 적은 값은 실제와 크게 달랐다: TAG 를 vpip 0.22/pfr 0.17/aggr 6.0 으로
# 적었으나 실측은 0.213/0.117/3.25 였다. 스타일 판정 기준이 틀리면 스타일을
# 못 맞히고, 그 위에 정확한 개념 prior 를 얹어도 소용이 없다.
# 파일이 없으면 스타일 경로가 죽고 직접 경로만 쓰인다 — 추측값보다 낫다.
_SIG_PATH = _os_path.join(_os_path.dirname(_os_path.abspath(__file__)),
                          'style_sig.json')
STYLE_SIG = {}
STYLE_SIG_SD = {}
try:
    with open(_SIG_PATH, encoding='utf-8') as _f:
        _cs = _json_mod.load(_f)
    for _st, _d in (_cs.get('styles') or {}).items():
        STYLE_SIG[_st] = {k: v['mean'] for k, v in _d.items()}
        STYLE_SIG_SD[_st] = {k: v['sd'] for k, v in _d.items()}
except Exception:
    pass


# 스타일 가설별 개념 prior 는 **캘리브레이션 파일에서 읽는다.**
# 손으로 적은 값은 실제 생성 분포와 달랐다(MANIAC range_read 를 4.0 으로
# 적었으나 실측 2.37, TAG 6.8 -> 5.08). 확신이 높은 관찰자일수록 그 오차를
# 그대로 받으므로, 추측값을 두면 belief 가 확신할수록 더 틀린다.
#
# tools/calibrate.py 가 **생성기를 독립 샘플링**해 만든다 — 게임 중 실제
# 상대의 개념을 읽지 않는다. '이 필드에서 TAG 는 대체로 이렇더라'는
# 경험칙이고, 관찰자가 필드 경험으로 알 수 있는 종류의 지식이다.
# 평균만이 아니라 sd 를 함께 쓴다: 라벨 안의 분산이 크면 스타일을 확신해도
# 개념은 단정할 수 없어야 한다.
_PRIOR_PATH = _os_path.join(_os_path.dirname(_os_path.abspath(__file__)),
                            'style_prior.json')
STYLE_CONCEPT_PRIOR = {}
STYLE_CONCEPT_SD = {}
try:
    with open(_PRIOR_PATH, encoding='utf-8') as _f:
        _cal = _json_mod.load(_f)
    for _st, _cs in (_cal.get('styles') or {}).items():
        STYLE_CONCEPT_PRIOR[_st] = {k: v['mean'] for k, v in _cs.items()}
        STYLE_CONCEPT_SD[_st] = {k: v['sd'] for k, v in _cs.items()}
except Exception:
    # 캘리브레이션 전이면 비워둔다. 스타일 경로가 죽고 직접 경로만 쓰인다 —
    # 추측값으로 채우는 것보다 낫다.
    pass


# 거리 척도도 실측 sd 를 쓴다. 고정 척도면 지표마다 실제 분산이 달라
# 어떤 지표는 과대, 어떤 지표는 과소 반영된다.
_SIG_SCALE = {'vpip': 0.06, 'pfr': 0.05, 'aggr': 0.9, 'cbet': 0.14, 'ftb': 0.14}
def _sig_scale(style, key):
    sd = STYLE_SIG_SD.get(style, {}).get(key)
    return max(0.02, sd) if sd else _SIG_SCALE.get(key, 0.15)


def style_hypotheses(est, sharpness=1.0):
    """관찰된 행동에서 스타일 **분포**를 만든다. 단일 라벨로 확정하지 않는다.

    각 스타일의 행동 서명과 관찰값의 거리로 가능도를 매기고 정규화한다.
    표본이 적거나 관찰력이 낮으면 sharpness 가 낮아 분포가 평평해진다 —
    '잘 모르겠다'가 그대로 표현된다.
    """
    out = {}
    for name, sig in STYLE_SIG.items():
        d = 0.0
        for k, v in sig.items():
            obs = est.get(k)
            if obs is None:
                continue
            d += ((float(obs) - v) / _sig_scale(name, k)) ** 2
        out[name] = math.exp(-0.5 * d * max(0.05, sharpness))
    tot = sum(out.values()) or 1.0
    return {k: v / tot for k, v in sorted(out.items(), key=lambda x: -x[1])}


def prior_spread(styles, key):
    """스타일 혼합에서 그 개념의 분산. 크면 prior 를 덜 믿어야 한다."""
    v = 0.0
    for st, p in styles.items():
        v += p * (STYLE_CONCEPT_SD.get(st, {}).get(key, 2.5) ** 2)
    return math.sqrt(max(0.01, v))


def concept_belief(styles, confidence):
    """스타일 가설 분포를 가중 혼합해 개념 belief 를 만든다.

    확신이 낮으면 중립값(5.0) 쪽으로 끌어당긴다 — 표본이 없는데 개념을
    단정하면 그것도 정보 누출과 같은 효과가 난다.
    """
    keys = set()
    for pri in STYLE_CONCEPT_PRIOR.values():
        keys |= set(pri.keys())
    w = max(0.0, min(1.0, float(confidence)))
    out = {}
    for k in sorted(keys):
        v = sum(p * STYLE_CONCEPT_PRIOR[s].get(k, 5.0) for s, p in styles.items())
        out[k] = round(5.0 + (v - 5.0) * (0.25 + 0.75 * w), 2)
    return out


def style_certainty(styles):
    """스타일 가설이 얼마나 뾰족한가. 평평하면 0(모르겠다), 하나로 쏠리면 1."""
    if not styles:
        return 0.0
    n = len(styles)
    top = max(styles.values())
    flat = 1.0 / n
    return max(0.0, min(1.0, (top - flat) / max(1e-9, 1.0 - flat)))


def opponent_belief(book, observer, target, observer_type, rng=None):
    """관찰자의 내부 상태. **실제 프로필의 복사본이 아니다.**

    두 갈래의 증거를 결합한다. 어느 쪽도 정답이 아니고 **둘 다 관찰에서
    나온 추정**이므로, 고정 비율이 아니라 각자의 확신도로 가중한다.

      직접 경로  행동 → 잠재요인(study/aggro/exp) → 개념 (estimate_concepts)
                 연속적이고 정밀하다.
      스타일 경로 행동 → "TAG 같다"는 가설 분포 → 그 스타일의 개념 prior
                 사람이 실제로 하는 중간 추론이다.

    둘 다 약하면 중립(5.0)으로 끌린다 — 모르면 평균으로 보는 것이 맞다.
    """
    est = perceived_profile(book, observer, target, observer_type, rng)
    o = OBSERVER.get(observer_type, DEFAULT_OBS)
    n = est.get('n') or 0
    conf = est.get('confidence') or 0.0

    # 스타일 가설 — 표본과 관찰력이 분포의 날카로움을 정한다.
    sharp = max(0.03, (0.15 + 1.20 * conf) * (0.15 + 1.9 * o['skill']) ** 2)
    styles = style_hypotheses(est, sharp)
    s_cert = style_certainty(styles)

    # 직접 경로 — 기존 층을 그대로 쓴다(대체하지 않는다).
    ec = estimate_concepts(est, observer_type, rng)
    direct, unc, w_direct = ec['concepts'], ec['uncertainty'], ec['weight']

    # 스타일 경로의 개념 prior
    prior = concept_belief(styles, conf)

    w_style = s_cert * (0.30 + 0.70 * o['skill'])
    merged, parts = {}, {}
    for k in sorted(set(direct) | set(prior)):
        d = direct.get(k)
        pr = prior.get(k)
        wd = w_direct if d is not None else 0.0
        # 라벨 안의 분산이 크면 스타일 prior 를 덜 믿는다. 실측 sd 가 2.4
        # 안팎이라 'TAG 라고 확신해도 range_read 는 단정 못 한다'가 맞다.
        ws = 0.0
        if pr is not None:
            _sd = prior_spread(styles, k)
            ws = w_style * (2.0 / (2.0 + _sd))
        # 둘 다 약하면 중립이 지배한다. 표본 없이 개념을 단정하면
        # 그 자체가 정보 누출과 같은 효과를 낸다.
        wn = max(0.15, 1.0 - wd - ws)
        tot = wd + ws + wn
        v = (wd * (d if d is not None else 5.0)
             + ws * (pr if pr is not None else 5.0)
             + wn * 5.0) / tot
        merged[k] = round(v, 2)
        parts[k] = {'direct': d, 'style_prior': pr,
                    'w_direct': round(wd, 2), 'w_style': round(ws, 2),
                    'w_neutral': round(wn, 2)}

    return {'observed_behavior': est,
            'style_belief': styles,
            'style_top': next(iter(styles)) if styles else None,
            'style_certainty': round(s_cert, 3),
            'latent_belief': ec.get('latent'),
            'concept_belief': merged,
            'concept_parts': parts,
            'concept_uncertainty': unc,
            'confidence': round(conf, 3),
            'samples': n}
