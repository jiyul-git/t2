#!/usr/bin/env python3
"""RFI attribution Phase 7 — plan.preflop_plan 전체를 짝지은 반사실. 읽기 전용.

rfi_decision_cf.py 는 open_decision/iso_decision 만 감쌌다. 디펜스
(defend_decision → defend_action_likelihoods → defend_thresholds:530/531)와
3벳 대면(opener back-action)은 빠져 있었다.

프리플랍 결정은 전부 session.py:1357 `PL.preflop_plan(...)` 한 곳을 지난다.
그 호출을 감싸 **같은 상태**에서 gto 표 네 개만 옛 값(e17be45)으로 바꿔
한 번 더 부른다. rng(h.rng)는 스냅샷·복원하고, dict/list 인자는 복사본을
넘긴다. 게임은 새 표(ca418d2) 궤적을 그대로 따라간다.

이 반사실이 잡는 것 = 결정 함수 **안쪽**에서 gto.rfi 를 읽는 채널
  OPEN_DEC (open/iso → _open → open_pct:398/409)
  DEF_DEC  (defend_decision → defend_thresholds:530/531)
잡지 않는 것 = 결정 함수 **바깥**에서 이미 계산돼 인자로 들어오는 것
  PF_RANGE (session._preflop_perceived_range → opp_ranges / call_ev_shadow)
  OBS      (session.py:1467 → book → read → open_gap)
그 둘은 rfi_channel_split.py 녹아웃으로 잰다.

상황 분류 (인자 + 호출 프레임의 rnd.log):
  unopened      aggressor 없음, 림퍼 없음            → open_decision
  vs_limp       aggressor 없음, 림퍼 있음            → iso_decision
  vs_open       aggressor 있음, raise_level == 1     → defend_decision
  opener_back   raise_level >= 2 이고 이 좌석이 이번 핸드에 이미 레이즈했다
  vs_3bet_cold  raise_level >= 2 이고 이 좌석은 아직 레이즈 안 했다

--cf-rev 로 반사실 표의 출처를 바꿀 수 있다. e17be45 worktree 에서
--cf-rev ca418d2 로 돌리면 **옛 궤적 위에서 새 표**를 대 본다(대칭 검사).
행의 키는 그대로 둔다: 'new' = 실제로 실행된 행동, 'old' = --cf-rev 표의 행동.

검증: 감싼 실행의 per-seed 지문이 ca418d2 ladder 지문과 같아야 한다
(짝 호출이 게임에 부작용을 남기지 않았다는 증거).

production 무수정.
"""
import argparse
import collections
import copy
import hashlib
import json
import os
import random
import sys

TABLES = ('RFI_BY_BEHIND', '_DEPTH_EARLY', '_DEPTH_LATE', 'ANTE_MULT')


def bb_band(bb):
    for hi in (10, 15, 20, 25, 30, 40, 60, 100, 150, 200):
        if bb < hi:
            return '<%d' % hi
    return '>=200'


def hand_class(p):
    for hi, lab in ((0.05, 'top5%'), (0.10, 'top10%'), (0.20, 'top20%'),
                    (0.35, 'top35%'), (0.60, 'top60%')):
        if p <= hi:
            return lab
    return 'rest'


def _cp(x):
    if isinstance(x, (dict, list)):
        return copy.deepcopy(x)
    return x


def run(repo, seeds, hands, out_path, cf_rev='e17be45'):
    if repo not in sys.path:
        sys.path.insert(0, repo)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import rfi_decision_cf as M
    import gto as G
    import plan as PL
    import preflop as PF
    import tourney as T
    old = M.old_tables(repo, cf_rev)
    orig = PL.preflop_plan
    rows = []
    # open_decision/iso_decision 안의 _open 값을 짝으로 기록한다 (open_pct 에 rng 없음).
    # ranges.py:228 의 _base_open 은 import 시점 바인딩이라 여기 안 걸린다 — 의도대로.
    opens = {'on': False, 'buf': []}
    o_open = PF._open

    def open_w(prof, pos, seats=8, bb=100.0, ante=True):
        v = o_open(prof, pos, seats, bb, ante)
        if opens['on']:
            saved = {t: getattr(G, t) for t in TABLES}
            try:
                for t in TABLES:
                    setattr(G, t, old[t])
                vo = o_open(prof, pos, seats, bb, ante)
            finally:
                for t in TABLES:
                    setattr(G, t, saved[t])
            opens['buf'].append((round(v, 5), round(vo, 5)))
        return v
    PF._open = open_w
    # 디펜스 역치 (tp, tot) 도 짝으로 기록한다. defend_action_likelihoods 가
    # 모듈 전역으로 부르므로 여기 걸린다. ranges._def_thresholds 경유(레인지 모델)도
    # opens['on'] 이 꺼져 있을 때라 기록되지 않는다.
    o_dt = PF.defend_thresholds

    def dt_w(*a, **kw):
        v = o_dt(*a, **kw)
        if opens['on']:
            saved = {t: getattr(G, t) for t in TABLES}
            try:
                for t in TABLES:
                    setattr(G, t, old[t])
                vo = o_dt(*a, **kw)
            finally:
                for t in TABLES:
                    setattr(G, t, saved[t])
            opens['dbuf'].append((tuple(round(x, 5) for x in v),
                                  tuple(round(x, 5) for x in vo)))
        return v
    PF.defend_thresholds = dt_w
    ctx = {'seed': None, 'h': -1}
    acc = collections.Counter()

    def situation(kw, fr):
        if kw.get('aggressor_pos') is None:
            return 'vs_limp' if (kw.get('n_limpers') or 0) > 0 else 'unopened'
        if int(kw.get('raise_level') or 1) <= 1:
            return 'vs_open'
        rnd, s = fr.f_locals.get('rnd'), fr.f_locals.get('s')
        mine = [x for x in (getattr(rnd, 'log', []) or [])
                if x[0] == s and x[1] in ('raise', 'bet', 'allin')]
        return 'opener_back' if mine else 'vs_3bet_cold'

    def wrap(profile, pos, hand, bb, rng, **kw):
        fr = sys._getframe(1)
        sit = situation(kw, fr)
        _rnd, _s = fr.f_locals.get('rnd'), fr.f_locals.get('s')
        first = not any(x[0] == _s for x in (getattr(_rnd, 'log', []) or []))
        st0 = rng.getstate()
        opens['on'], opens['buf'], opens['dbuf'] = True, [], []
        try:
            new = orig(profile, pos, hand, bb, rng, **kw)
        finally:
            opens['on'] = False
        open_pair = list(opens['buf'])
        def_pair = list(opens['dbuf'])
        st1 = rng.getstate()
        rng.setstate(st0)
        saved = {t: getattr(G, t) for t in TABLES}
        try:
            for t in TABLES:
                setattr(G, t, old[t])
            oldout = orig(_cp(profile), pos, hand, bb, rng,
                          **{k: _cp(v) for k, v in kw.items()})
            st_old = rng.getstate()
        finally:
            for t in TABLES:
                setattr(G, t, saved[t])
            rng.setstate(st1)
        na, nsz = new[0], new[1]
        oa, osz = oldout[0], oldout[1]
        try:
            hp = PF.pct(hand)
        except Exception:
            hp = None
        acc['n'] += 1
        acc['n_%s' % sit] += 1
        r = {'seed': ctx['seed'], 'hand_no': ctx['h'], 'sit': sit,
             'seat': _s, 'first': first,
             'pos': pos, 'bb': round(float(bb), 2),
             'hand': list(hand), 'hand_pct': (round(hp, 4) if hp is not None else None),
             'raise_level': int(kw.get('raise_level') or 1),
             'n_limpers': int(kw.get('n_limpers') or 0),
             'opener_allin': bool(kw.get('opener_allin')),
             'ante': bool(kw.get('ante')), 'seats': kw.get('seats'),
             'new': na, 'old': oa,
             'new_sz': (round(float(nsz), 3) if isinstance(nsz, (int, float)) else nsz),
             'old_sz': (round(float(osz), 3) if isinstance(osz, (int, float)) else osz),
             'rng_diff': st1 != st_old,
             'open_new_old': open_pair,
             'def_new_old': def_pair}
        rows.append(r)
        return new

    PL.preflop_plan = wrap
    per_seed = {}
    for sd in seeds:
        t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                         seed=sd, hands_per_level=200)
        ctx['seed'] = sd
        rec = ['q=%.3f|a=%.2f' % (t.field_q, t.aggr_bias)]
        for hi_ in range(hands):
            ctx['h'] = hi_
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            guard = 0
            while st and not st.get('done') and guard < 200:
                st = t.submit('fold')
                guard += 1
            log = getattr(t.run, 'full_log', []) or []
            rec.append(';'.join('%s:%s:%s:%s' % x for x in log))
            t.finish_hand()
        per_seed[str(sd)] = hashlib.sha256('\n'.join(rec).encode()).hexdigest()[:16]
        print('  seed %d  결정 누적 %d' % (sd, acc['n']), flush=True)
    PL.preflop_plan = orig
    PF._open = o_open
    PF.defend_thresholds = o_dt
    json.dump({'per_seed': per_seed, 'acc': dict(acc), 'rows': rows},
              open(out_path, 'w', encoding='utf-8'), ensure_ascii=False)
    return per_seed, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--seeds', default='3000-3005')
    ap.add_argument('--hands', type=int, default=30)
    ap.add_argument('--out', required=True)
    ap.add_argument('--cf-rev', default='e17be45')
    a = ap.parse_args()
    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi) + 1)) if hi else [int(lo)]
    ps, rows = run(a.repo, seeds, a.hands, a.out, a.cf_rev)
    print('@@RESULT@@' + json.dumps({'per_seed': ps, 'n': len(rows)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
