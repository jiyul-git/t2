"""Tier 3 — 틸트, 히스토리, 히어로 적응, 테이블 브레이크."""
import json, os, random
D = os.path.dirname(os.path.abspath(__file__))
def P(f): return os.path.join(D, f)

def load(f='dynamics.json'):
    p = P(f)
    return json.load(open(p)) if os.path.exists(p) else {'seats': {}, 'hero_obs': {}}

def save(d, f='dynamics.json'): json.dump(d, open(P(f), 'w'), indent=1)

def init_seat(d, seat):
    d['seats'].setdefault(str(seat), {'tilt': 0.0, 'won': 0, 'lost': 0,
                                      'big_loss_recent': 0, 'showdown_shown': [],
                                      'vs_hero': {'folds': 0, 'calls': 0, 'wins': 0}})

def record_pot(d, seat, delta_bb, showdown=None, vs_hero=False, hero_won=None,
               stack_bb=None):
    init_seat(d, seat); s = d['seats'][str(seat)]
    if delta_bb > 0:
        s['won'] += 1
        s['tilt'] = max(0.0, s['tilt'] - 0.08)          # 이기면 안정
    elif delta_bb < 0:
        s['lost'] += 1
        # 절대 크기 또는 스택 대비 비율로 판정
        rel_loss = abs(delta_bb)/max(1.0, stack_bb or 40)
        if delta_bb < -8 or rel_loss > 0.18:
            s['big_loss_recent'] = 3
            s['tilt'] = min(1.0, s['tilt'] + 0.20 + 0.6*min(0.5, rel_loss))
    if showdown: s['showdown_shown'].append(showdown)
    if vs_hero:
        if hero_won is True:  s['vs_hero']['wins'] += 0
        elif hero_won is False: s['vs_hero']['wins'] += 1

def decay(d):
    for s in d['seats'].values():
        s['tilt'] = max(0.0, s['tilt'] - 0.07)
        s['big_loss_recent'] = max(0, s['big_loss_recent'] - 1)

def tilted_profile(prof, d, seat, tilt_axis):
    """틸트 상태를 성향에 실제로 반영."""
    init_seat(d, seat)
    t = d['seats'][str(seat)]['tilt'] * (tilt_axis/10.0)
    if t <= 0.02: return prof, 0.0
    p = dict(prof)
    p['aggr']   = min(10, prof['aggr'] + 3*t)
    p['bluff']  = min(10, prof['bluff'] + 4*t)
    p['gamble'] = min(10, prof['gamble'] + 3*t)
    p['icm']    = max(1, prof['icm'] - 3*t)
    return p, round(t, 2)

def hero_image(d):
    """히어로가 어떻게 보이는지. 상대의 적응 근거."""
    h = d['hero_obs']
    n = max(1, h.get('hands', 0))
    return {'vpip': h.get('vpip', 0)/n, 'pfr': h.get('pfr', 0)/n,
            'agg': h.get('agg', 0)/max(1, h.get('postflop', 1)),
            'showdowns': h.get('showdowns', 0), 'hands': n}

def observe_hero(d, vpip=0, pfr=0, agg=0, postflop=0, showdown=None):
    h = d['hero_obs']
    for k, v in [('hands',1),('vpip',vpip),('pfr',pfr),('agg',agg),('postflop',postflop)]:
        h[k] = h.get(k, 0) + v
    if showdown:
        h.setdefault('shown', []).append(showdown)
        h['showdowns'] = h.get('showdowns', 0) + 1

def adapt_to_hero(prof, d, awareness):
    """레귤러만 히어로 이미지에 반응한다. awareness 0~1."""
    img = hero_image(d)
    if img['hands'] < 12 or awareness <= 0: return prof, None
    p = dict(prof); note = []
    if img['pfr'] > 0.30:                       # 히어로가 루즈어그로
        p['threebet_adj'] = 1.35; note.append('히어로 오픈 넓다고 판단 → 3벳 확대')
    elif img['pfr'] < 0.12:
        p['threebet_adj'] = 0.70; note.append('히어로 타이트 → 존중')
    if img['agg'] > 0.65:
        p['bluff'] = max(1, prof['bluff'] - 2*awareness); note.append('히어로 어그레시브 → 블러프캐치 늘림')
    return p, (' / '.join(note) if note else None)

# ---------- 테이블 브레이크 ----------
def table_break(alive_at_table, field_remaining, rng):
    """필드가 줄면 테이블이 깨지고 새 플레이어가 합류한다."""
    if len(alive_at_table) >= 7: return None
    if field_remaining <= 9: return None
    n_new = min(8 - len(alive_at_table), 2)
    return [{'type': rng.choice(['TAG','TAG','FISH','STATION','NIT','LAG','MANIAC']),
             'stack_bb': rng.randint(8, 90)} for _ in range(n_new)]
