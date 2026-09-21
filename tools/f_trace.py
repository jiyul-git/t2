#!/usr/bin/env python3
"""④ 판단층 f 계측 — 축 → f → 실현 행동을 같은 분모 안에서 본다.

  python3 tools/f_trace.py --entries 24 --hpl 12 --seeds 5000-5007
  python3 tools/f_trace.py --entries 24 --hpl 18 --seeds 5000-5007

**f 는 이미 프로덕션에 계측돼 있다.** plan.py:559 의
`_trace(st, street, 'aggression', p=..., roll=..., why=...)` 가 확률과
주사위 눈을 함께 남긴다. 새로 심지 않고 attach_intent 를 감싸 읽는다.
production logic 은 건드리지 않는다 — 원본을 정확히 한 번 부르고
반환값을 그대로 돌려주므로 rng 소비도 동일하다.

`decide_aggression`(plan.py:838)이 계획 라벨로 분기가 갈리므로, 축마다
**자기 분기**를 분모로 쓴다. 전체 벳을 분모로 쓰면 축이 없는 경로가
섞인다 (OBS_AXIS_PLAN 3.2).

  DEVIATE:포기 계획이나 지속벳  → cbet_freq 분기 (cbet_flop/barrel_turn/barrel_river)
  블러프 계획 실행              → bluff
  블락벳 계획                   → blockbet
  팟컨트롤                      → potcontrol
  밸류 계획 실행                → thin_value_{turn|river}, aggression

플레이어 식별은 profile['id'] 다. fieldsim 은 make_player(rng, q, pid) 로
이 필드를 채우고(fieldsim.py:70) tilted_view 가 type/id/label 을 정체성으로
보존한다(persona.py:616). tourney 는 이 필드를 안 채워서 쓸 수 없다.

**객체 동일성(id(profile))으로 잡으면 안 된다** — play.Hand.axes 가
PS.tilted_view 로 매 호출마다 새 dict 를 만든다(play.py:93). 처음에
그렇게 짰다가 관측 0건이 나왔다.
"""
import os, sys, argparse, math, statistics as stat, collections
import multiprocessing as mp

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)

# why 문자열 → 분기 이름. decide_aggression 의 반환 문자열과 1:1 이다.
BRANCH = [
    ('DEVIATE:포기 계획이나 지속벳', 'cbet_dev'),
    ('블러프 계획 실행',             'bluff'),
    ('블락벳 계획',                  'block'),
    ('팟컨트롤',                     'potcontrol'),
    ('밸류 계획 실행',               'value'),
    ('포기 계획 + 이니셔티브 없음',  'giveup_noinit'),
    ('함정 계획',                    'trap'),
    ('뒤에',                         'bluff_abort'),
]

def branch_of(why):
    for pre, name in BRANCH:
        if why.startswith(pre):
            return name
    return 'other'


# 축마다 (분기, 스트리트 조건). None 이면 스트리트 무관.
# (분기, 스트리트, rel 상한). rel 상한은 코드에 이미 있는 값만 쓴다 —
# plan.py:940 `if has_c and rel < 0.85` 가 thin_value 배수의 적용 구간이고,
# plan.py:945 `if rel >= 0.65` 부터 천장 곡선이 f 를 0.97 로 밀어올린다.
AXES = {
    'cbet_flop':        ('cbet_dev', 'flop', None),
    'barrel_turn':      ('cbet_dev', 'turn', None),
    'barrel_river':     ('cbet_dev', 'river', None),
    'bluff':            ('bluff',    None, None),
    'blockbet':         ('block',    None, None),
    'thin_value_turn':  ('value',    ('flop', 'turn'), 0.85),
    'thin_value_turn<65': ('value',  ('flop', 'turn'), 0.65),
    'thin_value_river': ('value',    'river', 0.85),
    'aggression':       ('value',    None, None),
    'discipline':       ('cbet_dev', None, None),
}
# 축 이름이 지표 이름과 다른 경우
AXIS_KEY = {'thin_value_turn<65': 'thin_value_turn'}

# potcontrol 은 분기 안 f 로 재면 안 된다. pot_control 분기의 확률식은
#   rel<0.30 → 0.04,  아니면 0.18 + 0.035*aggr
# 로 **축이 아예 들어가지 않는다** (CLAUDE.md: 확률식 _pc_p 에 축이 없다).
# 축이 하는 일은 그 계획으로 **라우팅**하는 것이므로 라우팅 비율로 잰다.
ROUTING = {'potcontrol': 'pot_control'}


def run_one(args):
    entries, hpl, stack, seed, cap = args
    import fieldsim as FS
    import plan as PL
    FS.Field.BOT_LOG = 0

    f = FS.Field(entries=entries, start_stack=stack, hero_pid=0, seed=seed,
                 hands_per_level=hpl)
    rec = []

    _orig = PL.attach_intent

    def wrapped(st, hero, board, my_range, opp_range, profile, pot, stack_,
                street, rng, n_opp, to_act_behind, oop, initiative, opp_est=None):
        out = _orig(st, hero, board, my_range, opp_range, profile, pot, stack_,
                    street, rng, n_opp, to_act_behind, oop, initiative, opp_est)
        # 반환 state 의 trace 에서 이번 스트리트의 aggression 항목을 뒤에서 찾는다.
        tr = None
        for t in reversed((out or {}).get('trace') or []):
            if t.get('kind') == 'aggression' and t.get('street') == street:
                tr = t; break
        if tr is None:
            return out
        it = ((out.get('intents') or {}).get(street) or {})
        rec.append({
            # play.Hand.axes 가 PS.tilted_view 로 **매번 새 dict** 를 만들므로
            # id(profile) 로는 못 잡는다. fieldsim 은 make_player(rng, q, pid)
            # 로 profile['id'] 를 채우고(fieldsim.py:70) tilted_view 가 id 를
            # 정체성으로 보존한다(persona.py:616). 그것을 키로 쓴다.
            'pid': profile.get('id'),
            'street': street,
            'branch': branch_of(tr.get('why') or ''),
            'plan': tr.get('plan'),
            'f': tr.get('p'),
            'roll': tr.get('roll'),
            'bet': 1 if it.get('act') == 'bet' else 0,
            # 키 이름이 의미다. attach_intent 의 이 인자는 session 이 넘긴
            # oop_field 이고, 아카이브의 `oop`(절대식)와 **다른 값**이다.
            'n_opp': n_opp, 'oop_field': bool(oop), 'init': bool(initiative),
            'rel': tr.get('rel'),
        })
        return out

    PL.attach_intent = wrapped
    try:
        while f.remaining() > 1 and f.hand_no < cap:
            f.hand_no += 1
            f.advance_level()
            for tid, tb in list(f.tables.items()):
                if tb.n() >= 2:
                    f._play_table(tb)
            f._collect_busts()
            f._balance()
            f.notes = []
    finally:
        PL.attach_intent = _orig

    prof = {p['pid']: p['prof'] for p in f.players.values()}
    axv = {}
    for pid, pr in prof.items():
        axv[pid] = dict(pr['concepts'])
        axv[pid].update({k: v for k, v in pr['temper'].items()})
        # 잠재요인. 편상관 통제에 필요하다 (ANALYSIS_PLAN 2절).
        # 접두사를 붙여 축 이름과 충돌하지 않게 한다.
        for _k, _v in (pr.get('latent') or {}).items():
            axv[pid]['_lat_' + _k] = _v
    return rec, axv, len(f.errors)


# ---------- 통계 ----------
def spearman(a, b):
    n = len(a)
    if n < 4: return None
    def rank(x):
        o = sorted(range(n), key=lambda i: x[i]); r = [0.0]*n; i = 0
        while i < n:
            j = i
            while j+1 < n and x[o[j+1]] == x[o[i]]: j += 1
            for k in range(i, j+1): r[o[k]] = (i+j)/2.0 + 1
            i = j+1
        return r
    ra, rb = rank(a), rank(b)
    ma, mb = sum(ra)/n, sum(rb)/n
    num = sum((ra[i]-ma)*(rb[i]-mb) for i in range(n))
    da = math.sqrt(sum((x-ma)**2 for x in ra)); db = math.sqrt(sum((x-mb)**2 for x in rb))
    return num/(da*db) if da and db else None


def iqr(v):
    v = sorted(v); n = len(v)
    return v[min(n-1, int(0.75*n))] - v[min(n-1, int(0.25*n))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=24)
    ap.add_argument('--hpl', type=int, default=12)
    ap.add_argument('--stack', type=int, default=30000)
    ap.add_argument('--seeds', default='5000-5007')
    ap.add_argument('--cap', type=int, default=3000)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--half-min', type=int, default=4,
                    help='split-half 를 낼 최소 기회 수')
    ap.add_argument('--sens', action='store_true',
                    help='최소 기회 기준 2~6 민감도 곡선을 낸다')
    a = ap.parse_args()

    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi)+1)) if hi else [int(lo)]

    with mp.Pool(a.jobs) as pool:
        out = pool.map(run_one, [(a.entries, a.hpl, a.stack, s, a.cap) for s in seeds])

    # (seed, pid) 로 플레이어를 전역 유일하게 만든다.
    rows = []; AX = {}
    errs = 0
    for si, (rec, axv, e) in enumerate(out):
        errs += e
        for r in rec:
            if r['pid'] is None or r['f'] is None: continue
            r = dict(r); r['key'] = (si, r['pid']); rows.append(r)
        for pid, v in axv.items(): AX[(si, pid)] = v

    print('# f 계측   entries=%d  hpl=%d  stack=%d  시드 %d개'
          % (a.entries, a.hpl, a.stack, len(seeds)))
    print('플레이어 %d명   attach_intent 관측 %d건   엔진 오류 %d건'
          % (len(AX), len(rows), errs))
    print()
    bc = collections.Counter(r['branch'] for r in rows)
    print('분기 분포:', dict(bc.most_common()))
    print()

    hdr = ('%-20s %7s %7s %6s %7s %7s | %8s %5s | %8s %5s %8s | %7s %5s'
           % ('축', '총기회', '인당중앙', '0%', 'f중앙', 'fIQR',
              'ρ(전원)', 'n', 'ρ(≥%d)' % a.half_min, 'n', '벳률ρ',
              'split r', 'n'))
    print(hdr); print('-'*len(hdr))

    for ax, (br, stt, relmax) in AXES.items():
        key = AXIS_KEY.get(ax, ax)
        sel = [r for r in rows if r['branch'] == br and
               (stt is None or (r['street'] == stt if isinstance(stt, str)
                                else r['street'] in stt)) and
               (relmax is None or (r['rel'] is not None and r['rel'] < relmax))]
        per = collections.defaultdict(list)
        for r in sel: per[r['key']].append(r)
        counts = [len(per.get(k, [])) for k in AX]
        n0 = 100.0*sum(1 for c in counts if c == 0)/max(1, len(counts))
        med = stat.median(counts) if counts else 0
        if not sel:
            print('%-20s %7d %7.1f %5.0f%% %7s %7s | %8s %5s | %8s %5s %8s | %7s %5s'
                  % (ax, 0, med, n0, '-', '-', '-', '-', '-', '-', '-', '-', '-'))
            continue
        fs = [r['f'] for r in sel]
        ks = [k for k in per if per[k]]
        fmt = lambda v: ('%+.3f' % v) if v is not None else '  -  '

        def rho_on(subset):
            if len(subset) < 4: return None, len(subset)
            x = [AX[k][key] for k in subset]
            y = [stat.mean(z['f'] for z in per[k]) for k in subset]
            return spearman(x, y), len(subset)

        rho_all, n_all = rho_on(ks)
        hk = [k for k in ks if len(per[k]) >= a.half_min]
        rho_h, n_h = rho_on(hk)
        # 벳률은 신뢰도와 같은 집단에서 낸다
        if len(hk) >= 4:
            rb = spearman([AX[k][key] for k in hk],
                          [stat.mean(z['bet'] for z in per[k]) for k in hk])
            h1 = [stat.mean(z['f'] for z in per[k][0::2]) for k in hk]
            h2 = [stat.mean(z['f'] for z in per[k][1::2]) for k in hk]
            rh = spearman(h1, h2)
        else:
            rb = rh = None
        print('%-20s %7d %7.1f %5.0f%% %7.3f %7.3f | %8s %5d | %8s %5d %8s | %7s %5d'
              % (ax, len(sel), med, n0, stat.median(fs), iqr(fs),
                 fmt(rho_all), n_all, fmt(rho_h), n_h, fmt(rb), fmt(rh), len(hk)))

    # ---- 라우팅 축 ----
    print()
    print('## 라우팅 축 — 분기 안 f 가 아니라 "그 계획으로 가는 비율"')
    post = collections.defaultdict(list)
    for r in rows:
        if r['branch'] != 'giveup_noinit':
            post[r['key']].append(r)
        else:
            post[r['key']].append(r)
    for ax, planname in ROUTING.items():
        ks = [k for k in post if len(post[k]) >= a.half_min]
        if len(ks) < 4:
            print('  %-16s 표본 부족' % ax); continue
        x = [AX[k][ax] for k in ks]
        y = [sum(1 for z in post[k] if z['plan'] == planname)/len(post[k]) for k in ks]
        h1 = [sum(1 for z in post[k][0::2] if z['plan'] == planname)/max(1, len(post[k][0::2])) for k in ks]
        h2 = [sum(1 for z in post[k][1::2] if z['plan'] == planname)/max(1, len(post[k][1::2])) for k in ks]
        print('  %-16s 라우팅률 중앙 %.3f   축→라우팅 ρ %+0.3f (n=%d)   split r %s'
              % (ax, stat.median(y), spearman(x, y) or 0.0, len(ks),
                 fmt(spearman(h1, h2))))

    if a.sens:
        print()
        print('## 최소 기회 기준 민감도 — 정보량과 신뢰도의 trade-off')
        print()
        print('split-half 는 **홀/짝 교대**다 (앞/뒤 절반이 아니다). 시간 추세')
        print('(레벨 상승 → 스택 감소)가 두 반쪽에 균등히 들어가게 한 것이다.')
        print('순서는 플레이어별 시간순. 홀수 관측은 불균등하다 (n=3 → 2건/1건).')
        print('**기준을 축마다 다르게 쓰지 않는다** — 전 축에 같은 기준을 걸고')
        print('민감도로 함께 제시한다. 한 축을 살리려고 낮추면 선택 편향이다.')
        print()
        thr = [2, 3, 4, 5, 6]
        h = '%-20s' % '축'
        for t in thr: h += '  %-18s' % ('>=%d' % t)
        print(h)
        print('%-20s' % '' + ''.join('  %5s %5s %6s' % ('n', '관측', 'r') for _ in thr))
        print('-'*(20 + 20*len(thr)))
        for ax, (br, stt, relmax) in AXES.items():
            key = AXIS_KEY.get(ax, ax)
            sel = [r for r in rows if r['branch'] == br and
                   (stt is None or (r['street'] == stt if isinstance(stt, str)
                                    else r['street'] in stt)) and
                   (relmax is None or (r['rel'] is not None and r['rel'] < relmax))]
            per = collections.defaultdict(list)
            for r in sel: per[r['key']].append(r)
            line = '%-20s' % ax
            for t in thr:
                hk = [k for k in per if len(per[k]) >= t]
                if len(hk) < 4:
                    line += '  %5d %5s %6s' % (len(hk), '-', '-')
                    continue
                # 반쪽당 관측 수 중앙값 (작은 쪽)
                ob = stat.median([min(len(per[k][0::2]), len(per[k][1::2])) for k in hk])
                h1 = [stat.mean(z['f'] for z in per[k][0::2]) for k in hk]
                h2 = [stat.mean(z['f'] for z in per[k][1::2]) for k in hk]
                rr = spearman(h1, h2)
                line += '  %5d %5.1f %6s' % (len(hk), ob,
                                             ('%+.3f' % rr) if rr is not None else '-')
            print(line)
        print()
        print('n    : 그 기준을 넘는 플레이어 수   관측 : 반쪽당 관측 수 중앙값(작은 쪽)')
        print('n < 4 이면 r 을 내지 않는다. n < 20 인 r 은 부호가 뒤집힐 수 있다.')

    print()
    print('ρ(전원)  : 기회 >= 1 인 전원. 1건짜리가 많으면 상황 노이즈가 ρ 를 누른다')
    print('ρ(>=%d)  : split-half 와 **같은 집단**. 두 숫자는 이쪽끼리 비교해야 한다' % a.half_min)
    print('split r : 홀/짝 반분 신뢰도. 관측 가능한 ρ 의 상한은 대략 sqrt(r)')


if __name__ == '__main__':
    main()
