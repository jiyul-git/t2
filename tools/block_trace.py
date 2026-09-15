#!/usr/bin/env python3
"""`block` 계획 파이프라인 계측 — 0건이 구조인가 표본인가.

  python3 tools/block_trace.py --seeds 5000-5007

`river_bluff` 0건을 구조 신호로 읽었다가 **세 번 틀렸다**
(TRACE_BLUFF.md 1절). 기대 빈도가 0.45건이었다. 같은 실수를 반복하지
않으려면 진입 확률 × 상황 발생률을 분리해서 재야 한다.

`plan.py:439-467` 의 구조:

    elif eq >= pcz:
        block_p = 0.0
        if oop and not initiative and 0.25 <= rel <= 0.80:
            block_p = 0.12 + 0.05*aggr - 0.03*bluff
            block_p *= (1 + 0.4*dang);  fish 면 ×0.25;  [0, 0.42] clamp
        if sk('blockbet') >= 1 and rng.random() < block_p:
            plan = 'block'
        # ← elif 가 아니다. 아래 if/elif 가 plan 을 **덮어쓴다**
        if sk('potcontrol') >= 1 and rng.random() < _pc_p:
            plan = 'pot_control'
        elif rel >= max(0.28, 0.52 - 0.080*_mg) and made >= 1:
            plan = 'value_2street'
        else:
            plan = 'showdown' if made >= 1 else 'giveup'

그래서 깔때기를 단계별로 센다. `why` 에 블락벳 메시지가 남았는데 최종
plan 이 `block` 이 아니면 **덮어쓰기**다.

  S0 포스트플랍 make_plan
  S1 block_p > 0 조건 (oop · 이니셔티브 없음 · 0.25<=rel<=0.80)
  S2 eq >= pcz 분기 진입 ('중간강도' 메시지)
  S3 S1 ∩ S2                      ← block opportunity
  S4 블락벳 메시지 (굴림 통과)
  S5 make_plan 반환 plan == 'block'  (덮어쓰기 생존)
  S6 attach_intent 시점 plan == 'block'  (_allowed 생존)
  S7 block 분기의 f
  S8 실제 벳

읽기 전용. make_plan 과 attach_intent 를 감싸 원본을 정확히 한 번 부르고
반환값을 그대로 돌려준다 — rng 소비가 동일하다.
"""
import os, sys, argparse, statistics as stat, collections
import multiprocessing as mp

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)

BLOCK_MSG = '블락벳으로 가격 통제'
MID_MSG = '중간강도'


def run_one(args):
    entries, hpl, stack, seed, cap = args
    import fieldsim as FS
    import plan as PL
    import persona as PS
    FS.Field.BOT_LOG = 0

    f = FS.Field(entries=entries, start_stack=stack, hero_pid=0, seed=seed,
                 hands_per_level=hpl)
    mk, ai = [], []

    _omk = PL.make_plan
    def wrap_mk(hero, board, my_range, opp_range, profile, pot, stack_, street,
                seed=None, n_opp=1, to_act_behind=0, oop=False, initiative=True,
                opp_est=None, opp_stack_bb=None, tilt=0.0, bb_chips=None):
        st = _omk(hero, board, my_range, opp_range, profile, pot, stack_, street,
                  seed=seed, n_opp=n_opp, to_act_behind=to_act_behind,
                  oop=oop, initiative=initiative, opp_est=opp_est,
                  opp_stack_bb=opp_stack_bb, tilt=tilt, bb_chips=bb_chips)
        w = ' | '.join(st.get('why') or [])
        rel = st.get('rel')
        mk.append({
            'pid': profile.get('id'), 'street': street,
            'oop': bool(oop), 'init': bool(initiative),
            'rel': rel, 'made': st.get('made'),
            'plan': st.get('plan'),
            'blk_sk': PS.sk(profile, 'blockbet'),
            'mg': PS.sk(profile, 'range_merge')/3.33,
            'pc_sk': PS.sk(profile, 'potcontrol'),
            'mid': MID_MSG in w,
            'blkmsg': BLOCK_MSG in w,
            'cond': bool(oop) and not bool(initiative)
                    and rel is not None and 0.25 <= rel <= 0.80,
        })
        return st

    _oai = PL.attach_intent
    def wrap_ai(st, hero, board, my_range, opp_range, profile, pot, stack_,
                street, rng, n_opp, to_act_behind, oop, initiative, opp_est=None):
        out = _oai(st, hero, board, my_range, opp_range, profile, pot, stack_,
                   street, rng, n_opp, to_act_behind, oop, initiative, opp_est)
        tr = None
        for t in reversed((out or {}).get('trace') or []):
            if t.get('kind') == 'aggression' and t.get('street') == street:
                tr = t; break
        it = ((out or {}).get('intents') or {}).get(street) or {}
        ai.append({'pid': profile.get('id'), 'street': street,
                   'plan': (out or {}).get('plan'),
                   'f': (tr or {}).get('p'),
                   'bet': 1 if it.get('act') == 'bet' else 0})
        return out

    PL.make_plan = wrap_mk
    PL.attach_intent = wrap_ai
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
        PL.make_plan = _omk
        PL.attach_intent = _oai

    blk = {p['pid']: p['prof']['concepts']['blockbet'] for p in f.players.values()}
    return mk, ai, blk, len(f.errors)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=24)
    ap.add_argument('--hpl', type=int, default=12)
    ap.add_argument('--stack', type=int, default=30000)
    ap.add_argument('--seeds', default='5000-5007')
    ap.add_argument('--cap', type=int, default=3000)
    ap.add_argument('--jobs', type=int, default=4)
    a = ap.parse_args()

    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi)+1)) if hi else [int(lo)]
    with mp.Pool(a.jobs) as pool:
        out = pool.map(run_one, [(a.entries, a.hpl, a.stack, s, a.cap) for s in seeds])

    MK, AI, BLK = [], [], {}
    errs = 0
    for si, (mk, ai, blk, e) in enumerate(out):
        errs += e
        for r in mk: r['key'] = (si, r['pid']); MK.append(r)
        for r in ai: r['key'] = (si, r['pid']); AI.append(r)
        for pid, v in blk.items(): BLK[(si, pid)] = v

    print('# block 계획 파이프라인   entries=%d hpl=%d 시드 %d개'
          % (a.entries, a.hpl, len(seeds)))
    print('플레이어 %d명   make_plan %d건   attach_intent %d건   오류 %d건'
          % (len(BLK), len(MK), len(AI), errs))
    print()

    v = sorted(BLK.values())
    print('blockbet 축   평균 %.2f  sd %.2f  중앙 %.1f' % (
        stat.mean(v), stat.pstdev(v), stat.median(v)))
    print('  make_plan 게이트 sk>=1 (0~3 스케일) = PS.sk >= 3.33 → %.1f%% 통과'
          % (100*sum(1 for x in v if x >= 3.33)/len(v)))
    print('  _allowed 강등역 PS.sk < 1.5 → %.1f%% (make_plan 게이트가 이미 막는다)'
          % (100*sum(1 for x in v if x < 1.5)/len(v)))
    print()

    n0 = len(MK)
    s1 = [r for r in MK if r['cond']]
    s2 = [r for r in MK if r['mid']]
    s3 = [r for r in MK if r['cond'] and r['mid']]
    s4 = [r for r in MK if r['blkmsg']]
    s5 = [r for r in MK if r['plan'] == 'block']
    s6 = [r for r in AI if r['plan'] == 'block']
    pc = lambda n, d: (100.0*n/d) if d else 0.0
    print('## 깔때기')
    print('  S0 포스트플랍 make_plan                 %6d' % n0)
    print('  S1 block_p>0 조건 (oop·무이니·rel대)    %6d  (%.1f%% of S0)' % (len(s1), pc(len(s1), n0)))
    print('  S2 eq>=pcz 분기 진입                    %6d  (%.1f%% of S0)' % (len(s2), pc(len(s2), n0)))
    print('  S3 S1 ∩ S2   ← block opportunity       %6d  (%.1f%% of S0)' % (len(s3), pc(len(s3), n0)))
    print('  S4 블락벳 메시지 (게이트+굴림 통과)      %6d  (%.1f%% of S3)' % (len(s4), pc(len(s4), len(s3))))
    print('  S5 make_plan 반환 plan==block           %6d  (%.1f%% of S4)' % (len(s5), pc(len(s5), len(s4))))
    print('  S6 attach_intent 시점 plan==block       %6d  (%.1f%% of S5)' % (len(s6), pc(len(s6), len(s5))))
    if s6:
        fs = [r['f'] for r in s6 if r['f'] is not None]
        if fs:
            print('  S7 block 분기 f  중앙 %.3f' % stat.median(fs))
        print('  S8 실제 벳                              %6d  (%.1f%% of S6)'
              % (sum(r['bet'] for r in s6), pc(sum(r['bet'] for r in s6), len(s6))))
    print()

    if s4 and not s5:
        print('  ** S4 → S5 에서 전부 사라진다 = 덮어쓰기다.')
        ow = collections.Counter(r['plan'] for r in s4)
        print('     블락벳 메시지가 남은 %d건의 최종 plan:' % len(s4), dict(ow.most_common()))
    elif s4:
        ow = collections.Counter(r['plan'] for r in s4)
        print('  블락벳 메시지가 남은 %d건의 make_plan 반환 plan:' % len(s4), dict(ow.most_common()))
    print()

    # block 이 덮어쓰기에서 살아남을 수 있는 자리인가
    # 생존 조건: pot_control 미발동 AND NOT(rel >= max(0.28, 0.52-0.080*_mg) and made>=1)
    if s3:
        surv = [r for r in s3
                if r['rel'] is not None and
                (r['made'] == 0 or r['rel'] < max(0.28, 0.52 - 0.080*(r['mg'] or 0)))]
        print('## 덮어쓰기 생존 가능 자리')
        print('  block opportunity %d건 중 value_2street 를 피할 수 있는 자리 %d건 (%.1f%%)'
              % (len(s3), len(surv), pc(len(surv), len(s3))))
        print('  (rel < max(0.28, 0.52-0.080*range_merge) 이거나 made==0)')
        print('  그 위에 pot_control 미발동까지 필요하다 — potcontrol 게이트 통과자 %.1f%%'
              % (100*sum(1 for r in s3 if r['pc_sk'] >= 3.33)/len(s3)))
        print()

    # 인당 opportunity 분포
    per = collections.Counter()
    for r in s3: per[r['key']] += 1
    counts = [per.get(k, 0) for k in BLK]
    print('## 인당 block opportunity (S3)')
    print('  중앙 %.1f   평균 %.2f   최대 %d   0건 %.0f%%   >=4건 %d명'
          % (stat.median(counts), sum(counts)/len(counts), max(counts),
             100*sum(1 for c in counts if c == 0)/len(counts),
             sum(1 for c in counts if c >= 4)))
    print()
    # 기대 빈도
    if s3:
        print('## 기대 빈도 추정')
        print('  S3 %d건 × S4/S3 %.3f = 블락벳 굴림 통과 기대 %.1f건'
              % (len(s3), len(s4)/len(s3), len(s3)*len(s4)/len(s3)))
        if s4:
            print('  그중 덮어쓰기 생존율 %.3f → 최종 기대 %.1f건'
                  % (len(s5)/len(s4), len(s5)))


if __name__ == '__main__':
    main()
