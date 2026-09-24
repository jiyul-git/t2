#!/usr/bin/env python3
"""S5(make_plan 반환 block) → S6(attach_intent 시점 block) 감소의 귀속. 읽기 전용.

`tools/block_trace.py` 는 S5 를 make_plan 기록에서, S6 를 attach_intent
기록에서 센다. **두 모집단이 다르다** (3506 vs 4612). 그래서 S5 22 vs S6 20
을 "2건이 죽었다"로 읽으면 안 된다 — 같은 사건을 센 것이 아니다.

여기서는 `(hand_no, pid, street)` 로 두 기록을 **조인**해서

  A  S5 인데 같은 (핸드,pid,스트리트) 의 attach_intent 기록이 없다
     → 그 스트리트에서 attach_intent 를 안 탄 것 (저항을 만나 decide_response
       로 갔거나 핸드가 끝났다). block 이 죽은 것이 아니다.
  B  S5 이고 attach_intent 기록이 있는데 plan != 'block'
     → **진짜 이탈.** river_fix(thin_river) / _allowed 로 나눈다.
  C  S6 인데 같은 자리에 S5 가 없다
     → 이전 스트리트에서 정해진 block 이 state 로 이월된 것.

production 무수정. block_trace.py 무수정.
"""
import argparse
import collections
import multiprocessing as mp
import os
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)

BLOCK_MSG = '블락벳으로 가격 통제'


def run_one(args):
    entries, hpl, stack, seed, cap = args
    import fieldsim as FS
    import plan as PL
    FS.Field.BOT_LOG = 0
    f = FS.Field(entries=entries, start_stack=stack, hero_pid=0, seed=seed,
                 hands_per_level=hpl)
    mk, ai = [], []
    cur = {'h': 0, 'i': 0}              # 핸드 번호 + 호출 순번 (단일 스레드)

    _omk, _oai = PL.make_plan, PL.attach_intent

    def wrap_mk(hero, board, my_range, opp_range, profile, pot, stack_, street,
                **kw):
        st = _omk(hero, board, my_range, opp_range, profile, pot, stack_,
                  street, **kw)
        w = ' | '.join(st.get('why') or [])
        cur['i'] += 1
        mk.append({'h': cur['h'], 'i': cur['i'], 'pid': profile.get('id'),
                   'street': street, 'plan': st.get('plan'),
                   'blkmsg': BLOCK_MSG in w})
        return st

    def wrap_ai(st, hero, board, my_range, opp_range, profile, pot, stack_,
                street, rng, n_opp, to_act_behind, oop, initiative,
                opp_est=None, **kw):
        out = _oai(st, hero, board, my_range, opp_range, profile, pot, stack_,
                   street, rng, n_opp, to_act_behind, oop, initiative,
                   opp_est, **kw)
        why = list((out or {}).get('why') or [])
        cur['i'] += 1
        ai.append({
            'h': cur['h'], 'i': cur['i'], 'pid': profile.get('id'),
            'street': street,
            'plan': (out or {}).get('plan'),
            'blk_now': any(BLOCK_MSG in str(x)
                           and str(x).startswith(street + ': ') for x in why),
            'thin_river': any('리버: 얇은 밸류' in str(x) for x in why)})
        return out

    PL.make_plan, PL.attach_intent = wrap_mk, wrap_ai
    try:
        while f.remaining() > 1 and f.hand_no < cap:
            f.hand_no += 1
            cur['h'] = f.hand_no
            f.advance_level()
            for tid, tb in list(f.tables.items()):
                if tb.n() >= 2:
                    f._play_table(tb)
            f._collect_busts()
            f._balance()
            f.notes = []
    finally:
        PL.make_plan, PL.attach_intent = _omk, _oai
    return mk, ai, len(f.errors)


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
    seeds = list(range(int(lo), int(hi) + 1)) if hi else [int(lo)]
    with mp.Pool(a.jobs) as pool:
        out = pool.map(run_one, [(a.entries, a.hpl, a.stack, s, a.cap)
                                 for s in seeds])
    MK, AI, errs = {}, {}, 0
    n_mk = n_ai = 0
    for si, (mk, ai, e) in enumerate(out):
        errs += e
        n_mk += len(mk); n_ai += len(ai)
        for r in mk:
            MK.setdefault((si, r['h'], r['pid'], r['street']), []).append(r)
        for r in ai:
            AI.setdefault((si, r['h'], r['pid'], r['street']), []).append(r)
    print('시드 %d개   make_plan %d   attach_intent %d   오류 %d'
          % (len(seeds), n_mk, n_ai, errs))
    if errs:
        print('ENGINE ERRORS — 결과 무효'); return 1

    # (시드,핸드,pid,스트리트) 는 1:1 이 아니다 — 한 스트리트에서 make_plan 이
    # 여러 번 불린다. 그래서 **호출 순번**으로 짝을 짓는다:
    # 각 make_plan 뒤에 오는 **첫 attach_intent** 가 그 결정의 소비처다.
    for k in AI:
        AI[k].sort(key=lambda r: r['i'])
    per = [len(v) for v in MK.values()]
    print('한 (시드,핸드,pid,스트리트) 당 make_plan 호출: 평균 %.2f  최대 %d'
          % (sum(per) / float(len(per)), max(per)))

    s5 = [(k, r) for k, v in MK.items() for r in v if r['plan'] == 'block']
    s6 = [(k, r) for k, v in AI.items() for r in v if r['plan'] == 'block']
    print('\nS5 make_plan 반환 block   %d' % len(s5))
    print('S6 attach_intent 시점 block %d' % len(s6))

    A, matched, B = [], [], []
    for k, r in s5:
        nxt = next((q for q in AI.get(k, []) if q['i'] > r['i']), None)
        if nxt is None:
            A.append((k, r))
        else:
            matched.append((k, r, nxt))
            if nxt['plan'] != 'block':
                B.append((k, nxt))
    print('\n## S5 의 행방 (호출 순번 페어링)')
    print('  A  뒤따르는 attach_intent 없음 (저항 → decide_response 등)  %d' % len(A))
    print('  matched 뒤따르는 attach_intent 있음                         %d' % len(matched))
    print('     그중 plan 유지 block                                    %d'
          % (len(matched) - len(B)))
    print('     그중 이탈                                               %d' % len(B))
    if B:
        riv = sum(1 for _, r in B if r['thin_river'])
        print('       river_fix(thin_river) %d / _allowed 등 %d   대상 plan %s'
              % (riv, len(B) - riv,
                 dict(collections.Counter(r['plan'] for _, r in B))))
    paired_ai = set()
    for k, r, nxt in matched:
        paired_ai.add((k, nxt['i']))
    C = [(k, r) for k, r in s6 if (k, r['i']) not in paired_ai]
    print('\n## S6 의 출처')
    print('  이번 스트리트 make_plan 이 정한 것                %d' % (len(s6) - len(C)))
    print('  그 외 (이전 스트리트 이월 / 같은 스트리트 재호출)  %d' % len(C))
    if C:
        print('     스트리트 분포 %s'
              % dict(collections.Counter(k[3] for k, _ in C)))
    ok = (len(B) == 0)
    print('\n판정: %s' % ('PASS — 조인된 자리에서 block 이탈 0건'
                        if ok else 'FAIL — 진짜 이탈 %d건' % len(B)))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
