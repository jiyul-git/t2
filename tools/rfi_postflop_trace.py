#!/usr/bin/env python3
"""RFI attribution Phase 8 — POST_RANGE 채널의 결정 단위 추적. 읽기 전용.

rfi_channel_split.py 에서 행동을 바꾸는 채널은 OPEN_DEC 와 POST_RANGE 둘뿐이었다.
POST_RANGE 는 포스트플랍마다 session._run 이 다시 만드는 프리플랍 레인지다.

  session.py:1607  my_r   = R.preflop_range(ax, pos, role, ...)   (내 레인지)
  session.py:1650  orange = R.preflop_range(opp_view, ...)          (상대 레인지)
  session.py:1172  _locked_postflop_range                          (올인 상대, 진단)
     → ranges.preflop_range:236  _base_open = pf._open (ranges.py:228 바인딩)
       → preflop._open:31 → persona.open_pct:398/409 → gto.rfi
     → ranges.preflop_range:249  _def_thresholds → preflop.defend_thresholds:530/531
  session.py:1806  PL.update_plan(..., my_r, opp_r, ...)             (소비)

arm 하나로 전 시드를 돌리며 update_plan 호출마다 입력 레인지(크기·해시)와
출력 계획 state 의 스칼라 필드를 기록한다. 두 arm(ALL_OLD / ALL_NEW 등)의
덤프를 --diff 로 맞대면 **게임이 갈라지기 전까지** 같은 결정끼리 정렬되므로,
레인지가 먼저 바뀌고 → 계획 필드가 바뀌고 → 행동이 바뀌는 순서를 볼 수 있다.

각 arm 은 별도 프로세스 (persona._TILT_VIEW_CACHE 대회 간 오염).
production 무수정.
"""
import argparse
import hashlib
import json
import os
import sys


def _h(rng):
    return hashlib.sha1(repr(list(rng or [])).encode()).hexdigest()[:10]


def _scal(st):
    out = {}
    for k, v in (st or {}).items():
        if isinstance(v, bool) or v is None or isinstance(v, str):
            out[k] = v
        elif isinstance(v, (int, float)):
            out[k] = round(float(v), 4)
    return out


def dump(repo, arm, seeds, hands, out):
    if repo not in sys.path:
        sys.path.insert(0, repo)
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    import plan as PL
    import tourney as T
    import rfi_channel_split as S
    ctx = {'seed': None, 'h': -1}
    rows = []
    o_init, o_next = T.Tournament.__init__, T.Tournament.next_hand

    def init(self, *a, **kw):
        ctx['seed'], ctx['h'] = kw.get('seed'), -1
        return o_init(self, *a, **kw)

    def nxt(self, *a, **kw):
        ctx['h'] += 1
        return o_next(self, *a, **kw)

    T.Tournament.__init__, T.Tournament.next_hand = init, nxt
    o_up = PL.update_plan

    def up(state, hero, board, my_range, opp_range, profile, pot, stack,
           street, seed, *a, **kw):
        st = o_up(state, hero, board, my_range, opp_range, profile, pot,
                  stack, street, seed, *a, **kw)
        rows.append({'seed': ctx['seed'], 'h': ctx['h'], 'street': street,
                     'hero': list(hero), 'board': list(board),
                     'pot': pot, 'stack': stack,
                     'my_n': len(my_range or []), 'my_h': _h(my_range),
                     'opp_n': len(opp_range or []), 'opp_h': _h(opp_range),
                     'st': _scal(st)})
        return st

    PL.update_plan = up
    per_seed, stats, seen = S.run(repo, arm, seeds, hands)
    json.dump({'arm': arm, 'per_seed': per_seed, 'stats': stats, 'rows': rows},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    print('@@RESULT@@' + json.dumps({'arm': arm, 'per_seed': per_seed,
                                     'n_rows': len(rows)}))


# 프로세스 안에서만 의미가 있는 서명(파이썬 hash 기반). 프로세스 간 비교에서 뺀다.
_NOISE = ('_rsig', '_opps_sig')
_LABEL = ('plan', 'intent')


def diff(pa, pb, show):
    A, B = json.load(open(pa)), json.load(open(pb))
    print('%s  vs  %s' % (A['arm'], B['arm']))
    for sd in sorted({r['seed'] for r in A['rows']}):
        ra = [r for r in A['rows'] if r['seed'] == sd]
        rb = [r for r in B['rows'] if r['seed'] == sd]
        n_rng = n_st = n_lab = 0
        first_rng = first_st = first_lab = None
        for i, (x, y) in enumerate(zip(ra, rb)):
            same_pos = (x['h'], x['street'], x['hero'], x['board']) == \
                       (y['h'], y['street'], y['hero'], y['board'])
            if not same_pos:
                print('  seed %d  정렬 끝: #%d (h%d %s) — 게임이 갈라졌다'
                      % (sd, i, x['h'], x['street']))
                break
            rd = (x['my_h'], x['opp_h']) != (y['my_h'], y['opp_h'])
            sdf = {k for k in set(x['st']) | set(y['st'])
                   if k not in _NOISE and x['st'].get(k) != y['st'].get(k)}
            if (sdf & set(_LABEL)) and first_lab is None:
                first_lab = (i, x, y)
            if sdf & set(_LABEL):
                n_lab += 1
            if rd:
                n_rng += 1
                if first_rng is None:
                    first_rng = (i, x, y)
            if sdf:
                n_st += 1
                if first_st is None:
                    first_st = (i, x, y, sdf)
        print('  seed %d  정렬된 결정 %d 중 레인지 다름 %d / 계획 필드 다름 %d / plan·intent 다름 %d'
              % (sd, min(len(ra), len(rb)), n_rng, n_st, n_lab))
        if first_lab:
            i, x, y = first_lab
            print('    첫 plan/intent 차이 #%d h%d %s hero %s board %s my %d→%d opp %d→%d : %s → %s'
                  % (i, x['h'], x['street'], x['hero'], x['board'], x['my_n'], y['my_n'],
                     x['opp_n'], y['opp_n'],
                     {k: x['st'].get(k) for k in _LABEL}, {k: y['st'].get(k) for k in _LABEL}))
        if first_rng:
            i, x, y = first_rng
            print('    첫 레인지 차이 #%d h%d %s  my %d→%d  opp %d→%d'
                  % (i, x['h'], x['street'], x['my_n'], y['my_n'],
                     x['opp_n'], y['opp_n']))
        if first_st:
            i, x, y, sdf = first_st
            print('    첫 계획 차이   #%d h%d %s  hero %s board %s  my %d→%d  opp %d→%d'
                  % (i, x['h'], x['street'], x['hero'], x['board'],
                     x['my_n'], y['my_n'], x['opp_n'], y['opp_n']))
            for k in sorted(sdf)[:show]:
                print('       %-22s %s → %s' % (k, x['st'].get(k), y['st'].get(k)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo')
    ap.add_argument('--arm')
    ap.add_argument('--seeds', default='3000-3005')
    ap.add_argument('--hands', type=int, default=30)
    ap.add_argument('--out')
    ap.add_argument('--diff', nargs=2)
    ap.add_argument('--show', type=int, default=40)
    a = ap.parse_args()
    if a.diff:
        diff(a.diff[0], a.diff[1], a.show)
        return 0
    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi) + 1)) if hi else [int(lo)]
    dump(a.repo, a.arm, seeds, a.hands, a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
