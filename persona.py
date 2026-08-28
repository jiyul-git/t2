"""플레이어를 '종'으로 뽑지 않는다.
   개념별 숙련도 벡터를 상관구조에 따라 굴려서 개인을 만든다.
   같은 필드에 100명이면 100명이 전부 다르다."""
import random, math

# ---------- 개념 목록 ----------
# 실행 개념: 실제 액션을 만들어내는 능력
EXEC = ['bluff', 'semibluff',
        'cbet_flop', 'barrel_turn', 'barrel_river',          # 스트리트별 공격
        'checkraise_flop', 'checkraise_late',                # 스트리트별 체크레이즈
        'bluffcatch_early', 'bluffcatch_river',              # 스트리트별 캐치
        'thin_value_turn', 'thin_value_river',               # 스트리트별 얇은 밸류
        'blockbet', 'potcontrol', 'trap', 'overbet', 'probe',
        'delayed_cbet', 'equity_denial', 'stackoff', 'reraise']
# 계산 개념: 공부량에 좌우되는 이론 능력
CALC = ['outs', 'potodds', 'spr', 'range_read', 'blocker', 'icm', 'board_texture', 'sizing_tell', 'pf_range', 'positional']
# 기질 축: 능력이 아니라 성격
TEMPER = ['aggression', 'looseness', 'gamble', 'tilt_prone', 'tilt_recovery',
          'discipline', 'adaptability', 'consistency', 'attention']

ALL_CONCEPTS = EXEC + CALC

# ---------- 잠재 요인 ----------
# 각 개념은 몇 개의 잠재 요인(공부량, 공격 성향, 경험)에서 파생된다.
# (study, aggro, exp) 가중치 + 개별 노이즈
LOADING = {
 # concept:            study aggro  exp   base   (스트리트가 깊을수록 base↓ = 더 어렵다)
 'bluff':             (0.35, 0.55, 0.20, 4.2),
 'semibluff':         (0.45, 0.40, 0.25, 4.4),
 'cbet_flop':         (0.35, 0.45, 0.30, 5.4),
 'barrel_turn':       (0.45, 0.60, 0.30, 4.1),
 'barrel_river':      (0.60, 0.55, 0.35, 3.2),
 'checkraise_flop':   (0.45, 0.35, 0.30, 4.2),
 'checkraise_late':   (0.65, 0.35, 0.40, 2.9),
 'bluffcatch_early':  (0.50, 0.10, 0.30, 4.6),
 'bluffcatch_river':  (0.75, 0.05, 0.40, 3.3),
 'thin_value_turn':   (0.60, 0.25, 0.30, 4.1),
 'thin_value_river':  (0.80, 0.20, 0.40, 3.0),
 'blockbet':          (0.60, 0.10, 0.25, 3.6),
 'potcontrol':        (0.55,-0.25, 0.35, 4.5),
 'trap':              (0.25,-0.10, 0.40, 3.8),
 'overbet':           (0.55, 0.45, 0.20, 3.2),
 'probe':             (0.55, 0.35, 0.25, 3.6),
 'delayed_cbet':      (0.60, 0.25, 0.35, 3.4),
 'equity_denial':     (0.70, 0.30, 0.30, 3.5),
 'stackoff':          (0.70, 0.05, 0.40, 3.8),
 'reraise':           (0.55, 0.50, 0.35, 3.4),
 'outs':              (0.75, 0.00, 0.30, 4.5),
 'potodds':           (0.80,-0.05, 0.30, 4.4),
 'spr':               (0.85, 0.05, 0.25, 4.0),
 'range_read':        (0.85, 0.10, 0.35, 4.0),
 'blocker':           (0.90, 0.10, 0.20, 3.5),
 'icm':               (0.80,-0.15, 0.30, 3.8),
 'board_texture':     (0.70, 0.05, 0.35, 4.2),
 'sizing_tell':       (0.65, 0.05, 0.40, 4.0),
 # --- 프리플랍 오픈 레인지 (base/spread 잠정. 개념 일괄 정리 때 재검토) ---
 'pf_range':          (0.90, 0.00, 0.25, 4.6),   # 차트를 아는가. 알려졌지만 안 외운 사람이 많다
 'positional':        (0.55, 0.10, 0.45, 4.4),   # 포지션 가치를 아는가. 경험으로도 붙는다
}

# ---------- 개념별 개인 편차 ----------
# 예전에는 전 개념이 gauss(0, 1.45) 로 같았다. 그건 "모든 개념이 같은 방식으로
# 퍼진다"는 가정인데 사실이 아니다.
#
#   편차 큼(2.0+)  — 알거나 모르거나로 갈리는 것. 차트·표를 외웠나 아닌가.
#                    중간이 드물다. 봉우리가 둘인 분포에 가깝다.
#   편차 작음(1.0) — 치다 보면 누구나 어느 정도는 하게 되는 것.
#                    잘하고 못하고의 차이가 있어도 폭이 좁다.
#
# base 는 '평균이 어디냐', spread 는 '얼마나 흩어지냐'. 다른 축이다.
# 어려운 개념(base↓)이라고 편차가 큰 것도 아니다 —
# 리버 씬밸류는 어렵지만(base 3.0) 거의 전원이 못해서 편차는 작다.
DEFAULT_SPREAD = 1.45
SPREAD = {
    # 외워서 아는 것 — 갈린다
    'blocker':          2.20,
    'icm':              2.10,
    'spr':              2.00,
    'overbet':          1.95,
    'range_read':       1.90,
    'potodds':          1.85,

    # 습관·기질에 얹혀 퍼지는 것 — 중간
    'reraise':          1.70,
    'checkraise_late':  1.65,
    'delayed_cbet':     1.60,
    'probe':            1.55,
    'blockbet':         1.55,
    'equity_denial':    1.55,
    'sizing_tell':      1.50,
    'trap':             1.50,

    # 누구나 어느 정도는 하는 것 — 좁다
    'cbet_flop':        1.05,
    'bluff':            1.15,
    'semibluff':        1.15,
    'outs':             1.20,
    'board_texture':    1.25,
    'checkraise_flop':  1.30,
    'bluffcatch_early': 1.30,
    'barrel_turn':      1.35,
    'potcontrol':       1.35,

    # 거의 전원이 못하는 것 — 어렵지만 편차는 좁다
    'thin_value_river': 1.10,
    'barrel_river':     1.20,
    'bluffcatch_river': 1.25,
    'thin_value_turn':  1.30,
    'stackoff':         1.40,

    # 프리플랍 오픈 (잠정)
    'pf_range':         2.30,   # 외웠나 아닌가로 가장 크게 갈리는 개념
    'positional':       1.60,   # 공부 없이 경험으로도 붙어서 중간
}


def _clamp(x, lo=0.0, hi=10.0): return max(lo, min(hi, x))

def skill_bounds(q):
    """대회 등급(q)에 따른 실력 하한/상한.
       저가 대회는 초짜가 흔하고 엘리트가 드물다. 하이롤러는 반대."""
    lo = max(0.5, -0.6 + 4.2*q)      # q0.4→1.1  q0.8→2.8  q1.3→4.9
    hi = min(10.0, 5.6 + 3.4*q)      # q0.4→7.0  q0.8→8.3  q1.3→10.0
    return lo, hi


def make_player(rng, field_quality=0.6, pid=None, _depth=0, aggr_bias=0.0, loose_bias=0.0):
    """field_quality 0~1.4 — 대회 규모/바이인이 클수록 study·exp 평균이 높다.
       aggr_bias  — 이 대회 필드가 얼마나 난폭한가. 공격 기질 잠재요인을 이동시킨다.
       loose_bias — 이 대회 필드가 얼마나 헐거운가. 참여 성향을 직접 이동시킨다.

       두 축이 따로 필요하다. looseness 는 aggro 를 0.25 배로만 받으므로
       공격성 축 하나로는 필드의 참여율 차이를 만들 수 없다. 그러면 어떤 대회를
       열어도 8명 평균이 같아진다 — 개인차는 있는데 테이블 차이는 없는 상태."""
    # 잠재 요인 (개인별)
    study = rng.gauss(2.6 + 4.2*field_quality, 2.1)      # 공부량
    aggro = rng.gauss(5.0 + aggr_bias, 2.4)              # 공격 기질
    exp   = rng.gauss(3.0 + 3.8*field_quality, 2.2)      # 경험

    c = {}
    for k, (ws, wa, we, base) in LOADING.items():
        v = base + ws*(study-5.0)*1.05 + wa*(aggro-5.0)*0.85 + we*(exp-5.0)*0.85
        v += rng.gauss(0, SPREAD.get(k, DEFAULT_SPREAD))  # 개념별 개인 편차
        c[k] = round(_clamp(v), 1)

    # 기질 축 — 능력과 부분적으로만 상관
    t = {
      'aggression':   round(_clamp(aggro + rng.gauss(0, 0.8)), 1),
      'looseness':    round(_clamp(rng.gauss(5.0 + loose_bias, 2.2) + 0.25*(aggro-4.6) - 0.30*(study-4.5)), 1),
      'gamble':       round(_clamp(rng.gauss(5.0 + 0.6*loose_bias, 2.4) - 0.35*(study-4.5) + 0.25*(aggro-4.6)), 1),
      'tilt_prone':   round(_clamp(rng.gauss(4.8, 2.6) - 0.20*(exp-4.5)), 1),
      'tilt_recovery':round(_clamp(rng.gauss(5.0, 2.2) + 0.25*(exp-4.5)), 1),
      'discipline':   round(_clamp(rng.gauss(5.0, 2.2) + 0.35*(study-4.5) + 0.20*(exp-4.5)), 1),
      'adaptability': round(_clamp(rng.gauss(4.6, 2.3) + 0.30*(exp-4.5)), 1),
      'consistency':  round(_clamp(rng.gauss(5.2, 2.1) + 0.30*(study-4.5) + 0.25*(exp-4.5)), 1),
      'attention':    round(_clamp(rng.gauss(5.0, 2.3) + 0.25*(exp-4.5)), 1),
    }

    p = {'id': pid, 'concepts': c, 'temper': t,
         'latent': {'study': round(study,1), 'aggro': round(aggro,1), 'exp': round(exp,1)}}
    p.update(derive(p))
    # 대회 등급별 실력 하한/상한 — 벗어나면 다시 뽑는다 (최대 6회)
    if _depth < 6:
        lo, hi = skill_bounds(field_quality)
        s = overall_skill(p)
        if s < lo or s > hi:
            return make_player(rng, field_quality, pid, _depth+1, aggr_bias, loose_bias)
    return p


def derive(p):
    """엔진이 쓰는 축으로 환산 (기존 인터페이스 호환)."""
    c, t = p['concepts'], p['temper']
    return {
        'type': label(p),                       # 표시용 라벨(설명일 뿐, 동작은 벡터가 결정)
        'aggr':   t['aggression'],
        'bluff':  c['bluff'],
        'gamble': t['gamble'],
        'icm':    c['icm'],
        'tilt':   t['tilt_prone'],
        'tricky': round((c['checkraise_flop'] + c['trap'] + c['overbet'])/3, 1),
        'value':  'xr' if c['checkraise_flop'] >= 6.5 else ('lead' if t['aggression'] <= 4 else 'mixed'),
        'goal':   'survive' if c['icm'] >= 7 else ('spot' if t['discipline'] <= 3.5 else 'accum'),
        'tight':  round(10 - t['looseness'], 1),
    }


def label(p):
    """사람이 읽기 쉬운 설명 라벨. 동작에는 영향 없음."""
    c, t = p['concepts'], p['temper']
    loose = t['looseness']; aggr = t['aggression']; study = p['latent']['study']
    if loose >= 7 and aggr >= 7:   base = 'MANIAC' if study < 4 else 'LAG'
    elif loose >= 6.5 and aggr < 4.5: base = 'STATION'
    elif loose >= 6:               base = 'FISH' if study < 4 else 'LOOSE_REG'
    elif loose <= 3.5 and aggr < 4: base = 'ROCK'
    elif loose <= 4.5:             base = 'NIT' if study < 4.5 else 'TAG_TIGHT'
    elif aggr >= 6.5:              base = 'TAG_AGGRO'
    else:                          base = 'TAG'
    if study >= 7.5: base = 'STUDIED_' + base
    if t['tilt_prone'] >= 7.5: base += '_TILTY'
    return base


def skill(p, concept):
    """0~10 실수. 기존 has()/skill() 대체."""
    return p['concepts'].get(concept, 3.0)


def has(p, concept, level=3.0):
    return skill(p, concept) >= level


def error_rate(p):
    """일관성이 낮을수록 '말 안 되는 라인'이 나올 확률."""
    cons = p['temper']['consistency']
    att = p['temper']['attention']
    return max(0.01, min(0.28, 0.30 - 0.020*cons - 0.012*att))


def describe(p):
    c, t = p['concepts'], p['temper']
    top = sorted(c.items(), key=lambda x: -x[1])[:3]
    bot = sorted(c.items(), key=lambda x: x[1])[:3]
    return ('%s | 공격 %.0f 루즈 %.0f 규율 %.0f 틸트취약 %.0f 일관성 %.0f\n'
            '  강점 %s\n  약점 %s\n  오류율 %.0f%%'
            % (p['type'], t['aggression'], t['looseness'], t['discipline'],
               t['tilt_prone'], t['consistency'],
               ', '.join('%s %.1f' % x for x in top),
               ', '.join('%s %.1f' % x for x in bot),
               error_rate(p)*100))


# ---------- 엔진 어댑터 ----------
ALIAS = {'cbet':'cbet_flop', 'barrel':'barrel_turn', 'checkraise':'checkraise_flop',
         'bluffcatch':'bluffcatch_early', 'thin_value':'thin_value_turn'}

def street_concept(base, street):
    """스트리트에 맞는 개념 이름으로 변환."""
    m = {
      ('cbet','flop'):'cbet_flop', ('cbet','turn'):'barrel_turn', ('cbet','river'):'barrel_river',
      ('barrel','turn'):'barrel_turn', ('barrel','river'):'barrel_river',
      ('checkraise','flop'):'checkraise_flop', ('checkraise','turn'):'checkraise_late',
      ('checkraise','river'):'checkraise_late',
      ('bluffcatch','flop'):'bluffcatch_early', ('bluffcatch','turn'):'bluffcatch_early',
      ('bluffcatch','river'):'bluffcatch_river',
      ('thin_value','flop'):'thin_value_turn', ('thin_value','turn'):'thin_value_turn',
      ('thin_value','river'):'thin_value_river',
    }
    return m.get((base, street), ALIAS.get(base, base))

def sk(prof, concept, default=4.0):
    """prof 가 persona 벡터든 구형 dict 든 숙련도를 0~10으로 반환."""
    c = prof.get('concepts')
    if c:
        if concept in c: return c[concept]
        alt = ALIAS.get(concept)
        if alt and alt in c: return c[alt]
        return default
    return default

def temper(prof, key, default=5.0):
    t = prof.get('temper')
    if t: return t.get(key, default)
    return prof.get({'aggression':'aggr','looseness':'tight','gamble':'gamble',
                     'tilt_prone':'tilt'}.get(key, key), default)

def err(prof):
    return error_rate(prof) if prof.get('temper') else 0.10

# 개념 숙련도 → 실행 확률 배수 (0에서 0, 5에서 1.0, 10에서 ~1.8)
def gate(prof, concept, floor=0.0):
    s = sk(prof, concept)
    if s <= 0.5: return floor
    return floor + (1-floor) * (s/5.0) ** 0.85

# 계산 개념의 정확도 → 추정치에 노이즈를 얹는다
def calc_noise(prof, concept, rng):
    """숙련도가 낮으면 계산 결과가 부정확해진다. 반환: 곱할 계수."""
    s = sk(prof, concept)
    sigma = max(0.02, 0.70 * (1 - s/10.0) ** 1.1)
    bias = 1.0 + 0.30 * (1 - s/10.0)            # 미숙할수록 과대평가 경향
    return max(0.20, min(3.0, rng.gauss(bias, sigma)))

# 포지션별 탄력성 — 성향 차이가 오픈 폭에 얼마나 크게 반영되는가.
# 얼리에서는 누구나 쓰레기를 접으므로 타입 차이가 작고,
# 레이트로 갈수록 닛과 매니악의 격차가 벌어진다. 이건 실제 통계와 같은 방향이다.
OPEN_ELASTICITY = {'UTG':0.75,'UTG+1':0.80,'UTG+2':0.85,'LJ':0.90,'HJ':1.00,
                   'CO':1.10,'BTN':1.25,'SB':1.20,'BB':1.10}

def open_pct(prof, pos, seats=8, bb=100.0, ante=True, band=None):
    """실제 오픈 폭 = 기준 × (1 + 이탈크기 × 이탈방향).

    기준은 gto.rfi 하나뿐이다. 레귤러 평균이며 사람과 무관하다.

    **크기와 방향을 나눈다.**
      크기 ← 개념(pf_range). 낮을수록 기준에서 멀다
      방향 ← 기질(looseness/aggression). 루즈면 +, 타이트면 −
    하나로 뭉치면 "루즈한데 잘하는 사람"과 "루즈하고 못하는 사람"이
    구분되지 않는다. 전자는 기준 근처의 LAG, 후자는 피시다.

    **포지션 인식은 별도 개념(positional)이다.**
    이게 낮으면 곡선이 평평해진다 — 얼리에서 너무 넓고 버튼에서 너무 좁다.
    리크리에이셔널의 특징은 '전체가 넓다'가 아니라 '포지션 구분이 없다'인데,
    폭 하나만 조절해서는 그 모양이 나오지 않는다.
    두 개념이 독립이라 네 조합이 다 나온다:
      높음/높음 레귤러, 낮음/낮음 전형적 피시,
      낮음/높음 과하게 넓지만 포지션은 아는 LAG 지망생,
      높음/낮음 총량은 맞는데 어디서 넣을지 모르는 사람.
    """
    import gto as _G
    base = _G.rfi(pos, seats, bb, ante, band)
    if base <= 0.0:
        return 0.0

    # --- 포지션 인식: 낮으면 테이블 평균 쪽으로 눌린다 ---
    # 상한 0.90 — 가장 잘하는 사람도 기준과 완전히 같지는 않다.
    # 1.0 을 허용하면 개념 8 이상이 전부 기준과 동일해져서
    # '실력 있는 LAG' 가 표현되지 않는다(방금 실제로 그랬다).
    pos_acc = 0.10 + 0.80 * min(1.0, sk(prof, 'positional') / 8.0)
    flat = (1.0 - pos_acc) * 0.60
    if flat > 1e-6:
        base = base*(1.0 - flat) + _G.avg_rfi(seats, bb, ante)*flat

    # --- 폭: 크기 × 방향 ---
    acc = 0.10 + 0.80 * min(1.0, sk(prof, 'pf_range') / 8.0)
    loose = temper(prof, 'looseness', 5.0)
    aggr  = temper(prof, 'aggression', 5.0)
    direction = max(-1.0, min(1.0, ((0.75*loose + 0.25*aggr) - 5.0) / 4.0))
    v = base * (1.0 + (1.0 - acc) * direction * 0.95) * _G.adapt_mult(prof)
    return max(0.02, min(0.92, v))


def traits_of(prof):
    """preflop.TRAITS 대체."""
    loose = temper(prof,'looseness',5.0); a = temper(prof,'aggression',5.0)
    g = temper(prof,'gamble',5.0); disc = temper(prof,'discipline',5.0)
    return {
      'limp': max(0.0, min(0.6, 0.02 + 0.055*(loose-4) - 0.035*(a-4) - 0.02*(disc-5))),
      'iso':  max(0.03, min(0.95, 0.55*(a/5.0)**1.15)),   # 곱셈형: 소극적인 사람은 이소를 거의 안 한다
      'threebet': max(.005, .009*a + .006*sk(prof,'bluff') + .004*(loose-4)),
      'sqz': 0.4 + 0.13*a,
      'call': max(.02, .022*loose + .018*g - .012*a),
      'shove_add': .008*g,
    }


# ---------- 행동 편향 (일관된 방향성 실수) ----------
# error_rate 는 '가끔 엉뚱한 짓을 한다'를 만든다. 그것만으로는 부족하다.
# 실제 사람의 실수는 무작위가 아니라 편향돼 있다. 드로우를 과대평가하는 사람은
# 플랍에서도 턴에서도 계속 과대평가한다. 블러프를 무서워하는 사람은 항상 같은
# 지점에서 접는다. 아래 편향은 그 사람에게 고정이며 매 결정에 같은 방향으로 작용한다.
#
# 값 범위는 -1(반대 방향) ~ +1(강한 편향), 0 이 중립.

def _z(v, mid=5.0, span=5.0):
    return max(-1.0, min(1.0, (v - mid)/span))


def bias(prof, name):
    """이 사람의 고정된 행동 편향. 랜덤이 아니다 — 같은 사람은 항상 같은 값."""
    if not prof or not prof.get('concepts'):
        return 0.0
    T = lambda k: temper(prof, k, 5.0)
    S = lambda k: sk(prof, k)

    if name == 'station':
        # 콜을 너무 넓게 한다. 루즈하고 도박성 있고 규율이 낮을수록.
        # 팟오즈를 이해할수록 완화된다.
        return _z(0.45*T('looseness') + 0.35*T('gamble')
                  + 0.20*(10 - T('discipline')) - 0.30*(S('potodds') - 5))

    if name == 'bluff_fear':
        # 큰 벳·후반 스트리트에서 과도하게 접는다.
        # 블러프캐치 개념이 약하고 소극적이며 레인지를 못 읽을수록 심하다.
        return _z(0.40*(10 - S('bluffcatch_river')) + 0.30*(10 - T('aggression'))
                  + 0.30*(10 - S('range_read')))

    if name == 'draw_love':
        # 드로우를 과대평가한다. 아웃 계산이 약하고 도박성이 높을수록.
        return _z(0.50*(10 - S('outs')) + 0.35*T('gamble') + 0.15*T('looseness'))

    if name == 'hero_call':
        # 상대를 블러프로 몰아 가볍게 콜한다. 공격적이고 블러프캐치를 좋아할수록.
        # 틸트 성향이 높을수록 "안 믿는다"며 가볍게 콜한다
        return _z(0.45*S('bluffcatch_river') + 0.35*T('aggression')
                  + 0.20*T('tilt_prone'))

    if name == 'sticky':
        # 한 번 들어간 팟을 잘 못 놓는다 (매몰비용). 규율이 낮을수록.
        return _z(0.55*(10 - T('discipline')) + 0.25*T('looseness')
                  + 0.20*T('tilt_prone'))
    return 0.0


def icm_signal(bf):
    """버블팩터(1.0~4.0)를 0~1 신호로 옮긴다.

    규약: 모든 상황 신호는 0~1 로 낸다. 0 = 압박 없음.
    그 신호를 읽는 능력(개념)은 별도 0~1 가중치로 따로 곱한다.
    신호와 능력을 한 값에 섞으면 '신호는 센데 못 읽는 사람'이 표현되지 않는다.
    """
    return max(0.0, min(1.0, (float(bf or 1.0) - 1.0) / 3.0))


def variance_seek(prof, tilt=0.0, field_q=0.6, stack_bb=None, bf=1.0):
    """분산을 일부러 키우려는 성향. 0~1.

    실력 열세를 인정한 사람이 쓰는 실제 전략이다. 프리플랍 올인은
    포스트플랍이라는 스킬 개입 구간을 통째로 없애버리므로,
    상대가 아무리 잘해도 결과가 카드에 수렴한다.
    '못 이기니까 운으로 간다' — 계산된 선택이다.

    같은 행동이 틸트에서도 나오지만 그건 계산이 아니라 감정이다.
    둘을 더해서 쓰되 원인은 구분해 둔다.

    - 자각한 실력 격차: 필드 수준 대비 내 실력. **자각**이 있어야 한다.
      실력도 없고 자각도 없는 사람은 그냥 평범하게 진다.
    - 도박성: 같은 격차라도 gamble 이 높아야 실제로 실행한다.
    - 틸트: 감정 경로. discipline 이 높으면 억제된다.
    - 스택: 짧을수록 어차피 쇼브 게임이라 전략적 의미가 준다.
    """
    if not prof or not prof.get('concepts'):
        return 0.0
    T = lambda k: temper(prof, k, 5.0)
    my = overall_skill(prof) if 'overall_skill' in globals() else 5.0
    # 자각: study·attention 이 있어야 격차를 안다
    aware = min(1.0, (0.6*T('attention') + 0.4*sk(prof, 'range_read'))/10.0)
    gap = max(0.0, (field_q*10.0 - my)/10.0)          # 필드가 나보다 얼마나 센가
    strategic = gap * aware * (0.25 + 0.075*T('gamble'))
    # ICM 압박은 전략 경로만 억제한다.
    # '실력 열세를 자각해서 분산으로 간다'는 계산이므로, 같은 계산을 하는 사람은
    # 버블에서 그 계산이 뒤집힌다는 것도 안다.
    # 틸트는 계산이 아니다. 감정 경로에는 걸지 않는다.
    # 하한 0.15 — icm 개념이 0 이어도 '이번에 죽으면 상금을 못 받는다'는
    # 개념이 아니라 상식이다. 아무도 완전히 무시하지는 않는다.
    icm_p = icm_signal(bf)                              # 상황 신호 0~1
    icm_w = max(0.15, sk(prof, 'icm') / 10.0)           # 읽는 능력 0~1
    strategic *= 1.0 - icm_p * icm_w * 0.90
    emotional = max(0.0, min(1.0, tilt)) * (1.2 - 0.09*T('discipline'))
    v = 0.65*strategic + 0.55*emotional
    if stack_bb is not None and stack_bb < 20:
        v *= 0.45          # 어차피 쇼브 구간이면 '일부러 키울' 여지가 적다
    return round(max(0.0, min(1.0, v)), 3)


def size_read(prof, size_frac):
    """상대 베팅 사이즈를 얼마나 제대로 읽는가. 반환: 인식된 사이즈.

    s/(1+2s) 같은 균형 공식은 '양극화된 균형 베터'를 전제하며
    대략 0.25~2.0팟에서만 유효하다. 팟의 9배는 그 정의역 밖이고,
    균형 레인지의 극단이 아니라 **넛 아니면 명백한 실수**라는 별개 범주다.

    이 구분을 하려면 sizing_tell 이 필요하다.
    개념이 낮은 사람은 정의역 밖에서도 사이즈 비례로 계속 외삽해서
    "크게 쳤으니 블러프도 많겠지"라고 오독한다.
    그 오독은 버그가 아니라 재현해야 할 현상이다.
    """
    s = max(0.0, float(size_frac or 0.0))
    if s <= 2.0:
        return s                                   # 정의역 안: 그대로 읽는다
    st = sk(prof, 'sizing_tell')
    # 개념이 높을수록 '정의역 밖'임을 인식해 2.0 쪽으로 되돌려 해석한다
    # (= 균형 공식을 그만 믿는다). 낮으면 실제 사이즈를 그대로 외삽한다.
    grasp = min(1.0, max(0.0, (st - 2.0)/6.0))
    return s + (2.0 - s)*grasp


def call_bias(prof, street, size_frac, made, outs):
    """콜/폴드 문턱에 곱할 계수. 1.0 이 중립, <1 이면 넓게 콜, >1 이면 과잉 폴드.

    같은 eq·같은 팟오즈라도 사람마다 다른 답을 내게 만든다.
    이것이 없으면 모든 봇이 eq>=need 라는 하나의 문턱으로 수렴해
    '평균적으로는 맞지만 아무도 개성이 없는' 필드가 된다.
    """
    m = 1.0
    m *= 1.0 - 0.22*max(0.0, bias(prof, 'station'))          # 스테이션: 넓게 콜
    # 블러프 공포는 사이즈와 스트리트에 비례해 커진다
    bf = max(0.0, bias(prof, 'bluff_fear'))
    if bf:
        w = {'flop': 0.35, 'turn': 0.75, 'river': 1.0}.get(street, 0.6)
        m *= 1.0 + 0.30*bf*w*min(1.5, max(0.5, size_frac/0.6))
    if outs:                                                  # 드로우 과대평가
        m *= 1.0 - 0.18*max(0.0, bias(prof, 'draw_love'))*min(1.0, outs/9.0)
    if made >= 1:                                             # 매몰비용: 뭔가 잡았을 때만
        m *= 1.0 - 0.12*max(0.0, bias(prof, 'sticky'))
    return max(0.55, min(1.75, m))


def exploit_weight(prof, confidence=0.0, n_hands=0):
    """상대 정보를 얼마나 쓰는가. 0 = 순수 자기 전략, 1 = 최대 익스플로잇.

    두 가지의 곱이다. 어느 하나라도 0 이면 0 이다.

    1) 이 사람이 익스플로잇하는 타입인가 — 개인 고정값.
       어떤 선수는 100핸드를 봐도 자기 패만 보고 친다. 그게 그 사람의 정체성이지
       실수가 아니다. adaptability(적응력)·range_read·attention 이 이걸 만든다.
    2) 데이터가 쌓였는가 — 상황값. reads.estimate 의 confidence.
       1핸드 본 상대와 60핸드 본 상대를 같게 취급하면 안 된다.

    초반에 자동으로 자기 전략이 되는 건 이 구조 때문이다. confidence 가 0 이면
    아무리 적응력이 높아도 조정할 근거가 없다. 별도 분기가 필요 없다.
    """
    if not prof or not prof.get('concepts'):
        return 0.0
    adp = temper(prof, 'adaptability', 5.0)
    att = temper(prof, 'attention', 5.0)
    rr  = sk(prof, 'range_read')
    # 성향 항: 적응력이 주도하고 레인지 리딩·주의력이 보조한다
    trait = (0.50*adp + 0.30*rr + 0.20*att) / 10.0
    trait = max(0.0, min(1.0, (trait - 0.28) / 0.60))    # 하위권은 아예 0
    if trait <= 0.0:
        return 0.0
    # 데이터 항: 표본이 적으면 신뢰도가 높다고 해도 상한을 둔다
    data = min(1.0, float(confidence)) * min(1.0, n_hands/12.0)
    return round(max(0.0, min(0.85, trait * data)), 3)


def read_opponent(prof, opp_est):
    """상대 추정치를 '어떻게 착취할 것인가'로 번역한다. 판단 층의 단일 입구.

    지점마다 exploit_weight 를 곱하는 방식은 세 가지가 문제였다:
      1. ftb(폴드율) 하나만 봤다 — 씬밸류·배럴·체크레이즈 성향은 안 봄
      2. 계획 선택의 뼈대(v3/v2 문턱, bluff_ok, trap_p)에는 안 들어갔다
      3. '정보를 얻는 능력'과 '쓰는 능력'과 '쓸 의지'가 하나로 뭉개졌다

    여기서 한 번 만들어 판단 전체에 흘린다. 반환 dict:
      w          — 익스플로잇 가중치 0~1 (0이면 전부 중립)
      fold_gap   — 상대가 모집단보다 얼마나 잘 접는가 (-0.5~+0.5)
      bluff_gap  — 상대가 얼마나 블러프를 많이 하는가 (-1~+1)
      passive    — 상대가 얼마나 수동적인가 (-1~+1)
      station    — 상대가 얼마나 안 접는가 (= -fold_gap 의 별칭, 가독성용)

    세 능력을 곱으로 분리한다:
      attention   — 관찰 자체를 하는가 (표본을 모으는가)
      range_read  — 관찰을 판단으로 옮길 수 있는가
      adaptability— 알아도 자기 전략을 바꿀 의지가 있는가
    어느 하나라도 낮으면 익스플로잇이 약해진다.
    """
    neutral = {'w': 0.0, 'fold_gap': 0.0, 'bluff_gap': 0.0,
               'passive': 0.0, 'station': 0.0}
    if not prof or not prof.get('concepts') or not opp_est:
        return neutral
    conf = float(opp_est.get('confidence', 0.0) or 0.0)
    n = int(opp_est.get('n', 0) or 0)
    if conf <= 0.0 or n <= 0:
        return neutral                      # 정보가 없다 = 내 전략대로

    att = temper(prof, 'attention', 5.0)
    adp = temper(prof, 'adaptability', 5.0)
    rr  = sk(prof, 'range_read')
    stl = sk(prof, 'sizing_tell')

    # ---------- 축별 독립 게이트 ----------
    # 능력을 하나로 곱해 뭉치면 안 된다.
    # '빈도는 못 세는데 사이즈에서 이상함을 느끼는' 사람이 실제로 있고,
    # 그런 조합이 표현되지 않으면 성향이 죽는다.
    # 각 축은 자기 능력에만 걸리고, 서로 독립이다.
    #
    # 계단식(문턱 넘으면 1, 아니면 0)도 안 된다. 3.9와 4.1 이 완전히
    # 다른 사람이 되어버린다. 하한만 두고 그 위로는 연속 감쇠한다.
    #   2 미만 → 0 (아예 못 봄) / 8 이상 → 1 (완전히 봄) / 사이는 선형
    def _see(v):
        return max(0.0, min(1.0, (v - 2.0) / 6.0))

    see_freq = _see(att)      # 빈도(몇 % 로 치는가/접는가) — 세기만 하면 된다
    see_line = _see(rr)       # 스트리트 구분·블러프 성향 — 레인지와 대조해야 안다
    see_size = _see(stl)      # 사이즈의 의미 — 사이즈에 주목해야 안다

    # 쓸 의지는 별개다. 볼 줄 알아도 자기 전략을 안 바꾸는 사람이 있다.
    use = _see(adp)
    if use <= 0.0:
        return neutral                      # 알아도 안 바꾸는 사람

    data = min(1.0, conf) * min(1.0, n/12.0)
    # w 는 '이 상대에 대해 조정할 여지'의 상한. 축별 게이트가 그 위에 곱해진다.
    w = round(max(0.0, min(0.85, use * data)), 3)
    if w <= 0.0:
        return neutral
    if max(see_freq, see_line, see_size) <= 0.0:
        return neutral                      # 아무 축도 못 보는 사람

    g = lambda k, d: float(opp_est.get(k) if opp_est.get(k) is not None else d)
    ftb = g('ftb', 0.52)
    bl  = g('bluff', 4.5)
    ag  = g('aggr', 5.0)
    # 스트리트별로 나눈다. '플랍은 잘 치는데 턴에서 멈추는' 사람과
    # '리버까지 안 접는' 사람은 완전히 다른 대응이 필요하다.
    fg = lambda v: max(-0.5, min(0.5, v - 0.52))
    return {'w': w,
            'see_freq': round(see_freq, 3), 'see_line': round(see_line, 3),
            'see_size': round(see_size, 3),
            'fold_gap': fg(ftb) * see_freq,            # 전체 평균 (폴백)
            # 스트리트 구분은 레인지 리딩이 있어야 한다.
            # 못 하는 사람은 전체 평균(fold_gap)만 보이고, 그것도 see_freq 만큼만.
            'fold_gap_flop':  fg(g('ftb_flop', ftb)) * see_line
                              + fg(ftb) * see_freq * (1.0 - see_line),
            'fold_gap_turn':  fg(g('ftb_turn', ftb)) * see_line
                              + fg(ftb) * see_freq * (1.0 - see_line),
            'fold_gap_river': fg(g('ftb_river', ftb)) * see_line
                              + fg(ftb) * see_freq * (1.0 - see_line),
            # 프리플랍 공격성 — 빈도만 세면 되므로 see_freq
            'tb_gap':   max(-0.5, min(0.5, g('pf_3bet', 0.07) - 0.07)) * 4.0 * see_freq,
            'f2tb_gap': fg(g('pf_fold_to_3bet', 0.55) + 0.52 - 0.55) * see_freq,
            # 4벳 축. 3벳만 남발하는 사람과 4벳까지 가는 사람은 다르다.
            'fb_gap':   max(-0.5, min(0.5, g('pf_4bet', 0.04) - 0.04)) * 6.0 * see_freq,
            'f2fb_gap': fg(g('pf_fold_to_4bet', 0.60) + 0.52 - 0.60) * see_freq,
            # 사이즈 축.
            #  size_gap : 평균적으로 크게 치는가 (-1~+1)
            #  size_info: 사이즈에서 정보를 얻을 수 있는가 (0~1).
            #             항상 같은 사이즈만 치는 사람은 사이즈가 레인지를 안 나눈다.
            #             표본이 적어도 낮게 잡는다.
            # 사이즈 축은 sizing_tell 에만 걸린다.
            # 빈도를 못 세는 사람이 사이즈에서 이상함을 느끼는 조합이 가능해야 한다.
            'size_gap':  max(-1.0, min(1.0, (g('sz_mean', 0.62) - 0.62)/0.45)) * see_size,
            # 분산 인식은 사이즈 인식의 상위 단계다 (제곱으로 더 가파르게)
            'size_info': (max(0.0, min(1.0, (g('sz_sd', 0.22) - 0.08)/0.35))
                          * min(1.0, g('sz_n', 0)/8.0)) * (see_size ** 2),
            'size_big':  max(0.0, min(1.0, g('sz_big', 0.15))) * see_size,
            'size_river': g('sz_river', g('sz_mean', 0.62)),
            'bluff_gap': max(-1.0, min(1.0, (bl - 4.5)/4.5)) * see_line,
            # passive/station 도 빈도 관찰이다. fold_gap 은 see_freq 로 막아놓고
            # 같은 원천(ftb/aggr)에서 나온 이 둘만 무게이트면 우회로가 된다.
            'passive': max(-1.0, min(1.0, (5.0 - ag)/5.0)) * see_freq,
            'station': max(-0.5, min(0.5, 0.52 - ftb)) * see_freq}


def street_gap(rd, street):
    """그 스트리트의 폴드 성향. 없으면 전체 평균으로 물러난다."""
    return rd.get('fold_gap_' + str(street), rd.get('fold_gap', 0.0))


def blend(baseline, exploit, w):
    """자기 전략과 익스플로잇 조정을 섞는다. 판단 지점마다 이 한 줄만 쓴다."""
    return baseline*(1.0 - w) + exploit*w


# ---------- 종합 실력 등급 ----------
import statistics as _st

def overall_skill(prof):
    """0~10 종합 실력. 계산 42% + 실행 38% + 규율 20%."""
    c = prof.get('concepts')
    if not c: return 5.0
    ex = _st.mean(c[k] for k in EXEC if k in c)
    ca = _st.mean(c[k] for k in CALC if k in c)
    t = prof.get('temper', {})
    disc = (t.get('discipline', 5) + t.get('consistency', 5) + t.get('attention', 5)) / 3
    return round(0.42*ca + 0.38*ex + 0.20*disc, 2)


# 모집단(q=0.78) 기준 백분위 경계 — 500명 표본에서 산출
_PCTL = [(2.6, 5), (3.4, 15), (4.0, 25), (4.6, 40), (5.1, 50),
         (5.6, 60), (6.0, 75), (6.6, 85), (7.5, 95), (8.3, 99)]

def skill_pct(prof):
    """모집단 상위 몇 %인가 (1=최상위)."""
    s = overall_skill(prof)
    for v, p in _PCTL:
        if s <= v: return 100 - p
    return 1

TIERS = [
    (8.3, 'ELITE',   '엘리트'),
    (7.0, 'CRUSHER', '강자'),
    (6.0, 'SOLID',   '견실'),
    (5.0, 'AVERAGE', '평균'),
    (4.0, 'WEAK',    '약체'),
    (2.8, 'FISH',    '피쉬'),
    (0.0, 'WHALE',   '초짜'),
]

def tier(prof):
    s = overall_skill(prof)
    for v, code, ko in TIERS:
        if s >= v: return code, ko
    return 'WHALE', '초짜'


def profile_card(prof):
    """사람이 읽는 한 줄 요약."""
    code, ko = tier(prof)
    return '%s(%s) 실력 %.1f / 상위 %d%%' % (ko, code, overall_skill(prof), skill_pct(prof))
