"""30종 아키타입. 각 타입은 축(axes)만 정의하고,
   오픈 레인지·디펜스·사이징은 축에서 파생시킨다."""

# name: (tight, aggr, bluff, gamble, icm, tricky, family, 설명)
#   tight 1(루즈)~10(타이트) / aggr 1~10 / bluff 1~10 / gamble 1~10 / icm 1~10 / tricky 1~10
ARCHETYPES = {
 # --- 레귤러 계열 ---
 'TAG':        (7, 6, 5, 4, 6, 5, 'reg',     '표준 타이트어그로'),
 'TAG_SOLID':  (8, 6, 4, 3, 7, 4, 'reg',     '견고한 레귤러, 라인 단순'),
 'TAG_TRICKY': (7, 6, 6, 4, 5, 8, 'reg',     '체크레이즈·트랩 많은 레귤러'),
 'GTO_ISH':    (6, 7, 6, 5, 5, 6, 'reg',     '균형 지향, 빈도 섞음'),
 'LAG':        (4, 9, 8, 7, 3, 7, 'reg',     '루즈어그로'),
 'LAG_WILD':   (3, 9, 9, 8, 2, 6, 'reg',     '거친 LAG, 배럴 과다'),
 'CREG':       (6, 7, 5, 4, 4, 6, 'reg',     '온라인 그라인더, 사이징 정형'),
 'PRO_SHORT':  (7, 7, 5, 5, 4, 5, 'reg',     '숏스택 전문, 푸시폴드 정확'),
 'ICM_MASTER': (8, 6, 4, 2, 9, 5, 'reg',     '버블·파이널 압박 활용'),

 # --- 타이트 계열 ---
 'NIT':        (9, 3, 2, 2, 8, 2, 'nit',     '극도로 타이트'),
 'ROCK':       (10,2, 1, 1, 9, 1, 'nit',     '바위, 프리미엄만'),
 'NIT_PASSIVE':(9, 2, 1, 2, 8, 2, 'nit',     '타이트 패시브'),
 'WEAK_TIGHT': (8, 3, 2, 3, 7, 2, 'nit',     '약한 타이트, 압박에 폴드'),
 'SURVIVOR':   (9, 4, 2, 1, 10,3, 'nit',     'ITM 생존만 목표'),

 # --- 루즈 패시브 계열 ---
 'FISH':       (3, 3, 2, 6, 2, 2, 'fish',    '루즈 패시브'),
 'STATION':    (4, 2, 1, 8, 1, 1, 'fish',    '콜링스테이션'),
 'WHALE':      (2, 4, 3, 9, 1, 2, 'fish',    '고래, 아무거나 콜'),
 'DRAWCHASER': (3, 3, 2, 8, 2, 2, 'fish',    '드로우 무조건 추격'),
 'LIMPER':     (4, 2, 1, 6, 3, 2, 'fish',    '림프 위주'),
 'CALLDOWN':   (5, 2, 1, 7, 2, 3, 'fish',    '리버까지 콜다운'),

 # --- 공격 과잉 계열 ---
 'MANIAC':     (2, 9, 9, 9, 1, 4, 'maniac',  '매니악'),
 'BLUFFER':    (5, 8, 10,7, 2, 7, 'maniac',  '블러프 과다'),
 'SPEWY':      (3, 8, 8, 9, 1, 3, 'maniac',  '칩 흘림, 규율 없음'),
 'HYPER_3BET': (5, 9, 8, 6, 3, 6, 'maniac',  '3벳 남발'),
 'SHOVER':     (5, 9, 6, 8, 2, 2, 'maniac',  '올인 남발'),

 # --- 특이 계열 ---
 'TILTER':     (5, 7, 7, 7, 3, 3, 'tilt',    '틸트 취약, 기복 큼'),
 'OLDSCHOOL':  (7, 4, 3, 4, 6, 3, 'live',    '라이브 올드스쿨, 슬로우플레이'),
 'TOURIST':    (4, 4, 3, 6, 4, 2, 'live',    '가끔 치는 관광객'),
 'TRAPPER':    (7, 4, 4, 4, 5, 9, 'live',    '항상 함정, 체크레이즈'),
 'SATELLITE':  (8, 5, 3, 2, 10,4, 'nit',     '새틀라이트 멘탈, 극단적 ICM'),
}

FAMILY_LIMP = {'reg': 0.01, 'nit': 0.02, 'fish': 0.45, 'maniac': 0.04,
               'tilt': 0.05, 'live': 0.25}
FAMILY_ISO  = {'reg': 0.80, 'nit': 0.35, 'fish': 0.15, 'maniac': 0.90,
               'tilt': 0.70, 'live': 0.45}

POS_BASE = {'UTG':.10,'UTG+1':.12,'LJ':.15,'HJ':.19,'CO':.26,'BTN':.42,'SB':.30}

def axes(name):
    t, a, b, g, i, k, fam, desc = ARCHETYPES[name]
    return {'type': name, 'family': fam, 'desc': desc,
            'tight': t, 'aggr': a, 'bluff': b, 'gamble': g, 'icm': i, 'tricky': k,
            'value': 'xr' if k >= 7 else ('lead' if a <= 4 else 'mixed'),
            'tilt': 8 if name == 'TILTER' else (7 if fam == 'fish' else 4),
            'goal': 'survive' if i >= 8 else ('spot' if fam == 'fish' else 'accum')}

def open_range(name):
    t = ARCHETYPES[name][0]
    # tight 10 → 0.55배, tight 1 → 2.2배
    mult = 2.2 - 0.183*(t-1)
    return {p: max(0.03, min(0.85, v*mult)) for p, v in POS_BASE.items()}

def traits(name):
    t, a, b, g, i, k, fam, _ = ARCHETYPES[name]
    return {'limp': FAMILY_LIMP[fam] * (1.4 - 0.06*t),
            'iso': FAMILY_ISO[fam],
            'threebet': max(.01, .012*a + .004*b - .004*t + .02*(name=='HYPER_3BET')),
            'sqz': 0.4 + 0.13*a,
            'call': max(.03, .035*(11-t)*0.35 + .02*g - .01*a),
            'shove_add': .01*g + .02*(name in ('SHOVER','PRO_SHORT'))}

def all_names(): return list(ARCHETYPES.keys())


# 개념별 보유 여부와 숙련도 (0=개념 없음, 1=알지만 미숙, 2=능숙, 3=주무기)
CONCEPTS = {
 # family 기본값
 'reg':    dict(bluff=2, semibluff=2, cbet=3, barrel=2, checkraise=2, blockbet=2,
                potcontrol=2, bluffcatch=2, thin_value=2, icm=2, range_read=2, sizing_tell=2),
 'nit':    dict(bluff=1, semibluff=1, cbet=2, barrel=1, checkraise=1, blockbet=1,
                potcontrol=3, bluffcatch=1, thin_value=1, icm=3, range_read=1, sizing_tell=1),
 'fish':   dict(bluff=0, semibluff=0, cbet=1, barrel=0, checkraise=0, blockbet=0,
                potcontrol=0, bluffcatch=0, thin_value=0, icm=0, range_read=0, sizing_tell=0),
 'maniac': dict(bluff=3, semibluff=2, cbet=3, barrel=3, checkraise=2, blockbet=0,
                potcontrol=0, bluffcatch=1, thin_value=1, icm=0, range_read=1, sizing_tell=1),
 'tilt':   dict(bluff=2, semibluff=1, cbet=2, barrel=2, checkraise=1, blockbet=0,
                potcontrol=1, bluffcatch=1, thin_value=1, icm=1, range_read=1, sizing_tell=1),
 'live':   dict(bluff=1, semibluff=1, cbet=1, barrel=1, checkraise=2, blockbet=1,
                potcontrol=2, bluffcatch=1, thin_value=1, icm=1, range_read=1, sizing_tell=1),
}
# 타입별 개별 덮어쓰기
OVERRIDE = {
 'GTO_ISH':    dict(bluff=3, blockbet=3, thin_value=3, range_read=3, sizing_tell=3),
 'TAG_TRICKY': dict(checkraise=3, bluff=3),
 'TRAPPER':    dict(checkraise=3, bluff=1, barrel=0, potcontrol=1),
 'BLUFFER':    dict(bluff=3, barrel=3, bluffcatch=0, thin_value=0),
 'ICM_MASTER': dict(icm=3, potcontrol=3, bluffcatch=3),
 'SATELLITE':  dict(icm=3, bluff=0, barrel=0, potcontrol=3),
 'PRO_SHORT':  dict(icm=3, cbet=3, potcontrol=2),
 'STATION':    dict(bluffcatch=1),
 'CALLDOWN':   dict(bluffcatch=1, potcontrol=0),
 'WHALE':      dict(bluff=0, cbet=0),
 'DRAWCHASER': dict(semibluff=1),
 'SHOVER':     dict(bluff=2, barrel=1, potcontrol=0, sizing_tell=0),
 'SPEWY':      dict(bluff=2, potcontrol=0, bluffcatch=0),
 'OLDSCHOOL':  dict(checkraise=2, bluff=1, thin_value=0),
 'ROCK':       dict(bluff=0, barrel=0, semibluff=0),
 'NIT_PASSIVE':dict(cbet=1, barrel=0),
 'WEAK_TIGHT': dict(bluffcatch=0, potcontrol=1),
 'SURVIVOR':   dict(icm=3, bluff=0, barrel=0),
 'HYPER_3BET': dict(bluff=3, barrel=2, bluffcatch=1),
 'LAG_WILD':   dict(barrel=3, potcontrol=0),
 'CREG':       dict(sizing_tell=3, range_read=3),
 'TAG_SOLID':  dict(bluff=1, checkraise=1, thin_value=2),
 'TOURIST':    dict(bluff=1, cbet=1),
 'LIMPER':     dict(cbet=0, bluff=0),
 'TILTER':     dict(bluff=2),
}

def concepts(name):
    fam = ARCHETYPES[name][6]
    c = dict(CONCEPTS[fam])
    c.update(OVERRIDE.get(name, {}))
    return c

def has(name, concept, level=1):
    """그 타입이 해당 개념을 최소 level 이상으로 갖고 있는가."""
    return concepts(name).get(concept, 0) >= level

def skill(name, concept):
    return concepts(name).get(concept, 0)
