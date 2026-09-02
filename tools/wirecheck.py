"""개념이 **있어야 할 자리에** 배선됐는지 점검한다.

    python3 tools/wirecheck.py

'어딘가에서 읽히는가'만 보면 부족하다. 그건 이미 통과하는데도
정작 그 개념이 필요한 판단에는 안 걸려 있을 수 있다.
그래서 개념마다 **읽혀야 할 함수**를 명세로 적고 대조한다.

동적 키(`persona.street_concept`)로 읽히는 개념은 grep 으로 안 보이므로
매핑표를 풀어서 함께 본다. `sk(profile, 'barrel_turn')` 이 아니라
`sk(profile, PS.street_concept('cbet', street))` 형태이기 때문이다.
"""
import re, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import persona as PS

# 개념 -> (읽혀야 할 함수들, 무엇을 정하는가)
SPEC = {
    # ---------- 프리플랍 ----------
    'pf_range':      (['open_pct', 'limp_p'], '오픈 폭 정확도 / 이론적 림프'),
    'positional':    (['open_pct'], '포지션 곡선 평탄화'),
    'pf_defend':     (['defend_thresholds'], '디펜스 폭 정확도'),
    'open_size':     (['open_size_bb'], '오픈 사이즈'),
    'spr':           (['open_form', 'raise_form', 'depth_feel'], '깊이 인식 / 형태 판단'),
    'stack_decay':   (['lookahead_hands'], '블라인드 침식 예측'),
    'icm':           (['icm_aware'], 'ICM 인지도. icm_press(0~1 배수)와 icm_bf(BF 단위)가 공유'),
    'reraise':       (['decide_response'], '리레이즈 성향'),

    # ---------- 상대 읽기 ----------
    'range_read':    (['read_opponent', 'perceived_range'], '레인지 구성 읽기'),
    'sizing_tell':   (['read_opponent', 'size_read', 'calldown_need'], '사이즈 의미 읽기'),

    # ---------- 포스트플랍: 계획 ----------
    'potcontrol':    (['make_plan'], '팟 컨트롤 선택'),
    'trap':          (['make_plan', 'trap_judgment'], '함정 선택'),
    'semibluff':     (['make_plan'], '세미블러프 선택'),
    'bluff':         (['make_plan', 'decide_aggression'], '블러프 선택·실행'),
    'range_merge':   (['make_plan'], '중간강도 → 얇은 밸류'),
    'stackoff':      (['stackoff_plan', 'decide_response'], '3스트리트 커밋'),

    # ---------- 포스트플랍: 실행 ----------
    'cbet_flop':     (['cbet_freq'], '플랍 씨벳 빈도'),
    'barrel_turn':   (['cbet_freq'], '턴 배럴 빈도'),
    'barrel_river':  (['cbet_freq'], '리버 배럴 빈도'),
    'delayed_cbet':  (['decide_aggression'], '플랍 체크백 후 턴'),
    'probe':         (['decide_aggression'], '상대가 체크백한 다음 스트리트 선제'),
    'blockbet':      (['make_plan', 'decide_aggression'], '블락벳 선택·실행'),
    'multiway':      (['cbet_freq', 'decide_aggression'], '다인원 축소'),
    'fold_equity':   (['decide_aggression'], '상대가 접을까'),
    'checkraise_flop': (['checkraise_decision'], '플랍 체크레이즈'),
    'checkraise_late': (['checkraise_decision'], '턴·리버 체크레이즈'),

    # ---------- 포스트플랍: 사이징 ----------
    'overbet':       (['overbet_frac'], '오버벳'),
    'equity_denial': (['decide_size'], '젖은 보드 사이즈 확대'),

    # ---------- 포스트플랍: 대응 ----------
    'bluffcatch_early': (['calldown_need'], '플랍·턴 콜다운 문턱'),
    'bluffcatch_river': (['calldown_need'], '리버 콜다운 문턱'),
    'thin_value_turn':  (['decide_aggression'], '턴 얇은 밸류'),
    'thin_value_river': (['decide_aggression'], '리버 얇은 밸류'),

    # ---------- 인식 재료 ----------
    'board_texture': (['cbet_freq', 'decide_aggression'], '보드 구조 읽기'),
    'blocker':       (['make_plan'], '블로커'),
    'outs':          (['make_plan'], '아웃 계산'),
    'potodds':       (['bias'], '팟오즈 (파생축 재료)'),
}

SRC = {}
for f in os.listdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')):
    if f.endswith('.py') and not f.startswith('legacy'):
        SRC[f] = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', f)).read()


def _dyn_map():
    """street_concept 매핑을 풀어 base -> [구체 개념] 로."""
    m = re.search(r"def street_concept.*?m = \{(.*?)\n    \}", SRC['persona.py'], re.S)
    out = {}
    if m:
        for a, b, c in re.findall(r"\('(\w+)'\s*,\s*'(\w+)'\)\s*:\s*'(\w+)'", m.group(1)):
            out.setdefault(a, set()).add(c)
    return out


DYN = _dyn_map()


def _funcs(src):
    """소스에서 함수별 본문을 뽑는다."""
    out = {}
    for m in re.finditer(r'^def (\w+)\(', src, re.M):
        start = m.start()
        nxt = re.search(r'^def \w+\(', src[m.end():], re.M)
        end = m.end() + (nxt.start() if nxt else len(src))
        out[m.group(1)] = src[start:end]
    return out


BODIES = {}
for f, s in SRC.items():
    for name, body in _funcs(s).items():
        BODIES.setdefault(name, '')
        BODIES[name] += body


def reads(fn_name, concept):
    body = BODIES.get(fn_name, '')
    if not body:
        return None                       # 함수 자체가 없음
    if re.search(r"['\"]%s['\"]" % concept, body):
        return True
    # 동적 키: street_concept('base', ...) 이 이 개념으로 풀리는가
    for base in re.findall(r"street_concept\(\s*'(\w+)'", body):
        if concept in DYN.get(base, ()):
            return True
    return False


# 편향(persona.bias)도 같이 본다. 개념이 아니라 wirecheck 밖에 있었고
# 그래서 다섯 중 셋이 죽어 있어도 통과했다.
BIAS_SPEC = {
    'station':       ['decide_response'],
    'bluff_fear':    ['decide_response'],
    'hero_call':     ['decide_response'],
    'overpair_love': ['perceived_rel'],
    'draw_love':     ['perceived_rel'],
    'sticky':        ['perceived_rel'],
}

miss, nofn, extra = [], [], []
for b, fns in BIAS_SPEC.items():
    for fn in fns:
        r = reads(fn, b)
        if r is None:
            nofn.append((b, fn))
        elif not r:
            miss.append((b, fn))
for b in PS.BIAS_NAMES:
    if b not in BIAS_SPEC:
        extra.append('bias:' + b)
for c in sorted(PS.LOADING):
    if c not in SPEC:
        extra.append(c)
        continue
    want, _ = SPEC[c]
    for fn in want:
        r = reads(fn, c)
        if r is None:
            nofn.append((c, fn))
        elif not r:
            miss.append((c, fn))

print('개념 %d개 / 명세 %d개' % (len(PS.LOADING), len(SPEC)))
print()
if extra:
    print('명세에 없는 개념 (SPEC 에 추가할 것):')
    for c in extra:
        print('   %s' % c)
    print()
if nofn:
    print('명세가 가리키는 함수가 없음 (이름이 바뀌었을 수 있음):')
    for c, fn in nofn:
        print('   %-18s -> %s()' % (c, fn))
    print()
if miss:
    print('배선 누락 — 이 함수가 이 개념을 안 읽는다:')
    for c, fn in miss:
        print('   %-18s -> %s()   (%s)' % (c, fn, SPEC[c][1]))
else:
    print('배선 누락 없음')

sys.exit(1 if (miss or nofn or extra) else 0)
