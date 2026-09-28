#!/usr/bin/env python3
"""RFI attribution Phase 2 — ca418d2 의 결정 수준 짝지은 반사실. 읽기 전용.

ca418d2 는 gto.py 의 **데이터 표 네 개**만 바꿨다.
  RFI_BY_BEHIND · _DEPTH_EARLY · _DEPTH_LATE · ANTE_MULT

소비 경로 (grep 전수, tools/ 제외):
  gto.rfi ─┬─ persona.open_pct ─ preflop._open ─┬─ open_decision:298  미오픈 RFI
           │                                    └─ iso_decision:833   림퍼 상대 아이소
           ├─ gto.avg_rfi ─ persona.open_pct (포지션 평탄화 항)
           └─ session.py:1467 ─ book.observe_preflop(rfi_exp)
                └─ reads.estimate:305 rfi_rel = rfi_did/rfi_exp
                   └─ persona.read_opponent:943 open_gap
                      └─ preflop.py:272 table_pressure / :654 수비 / :902 calloff_cap

**같은 상태에서** 표만 옛 값으로 바꿔 결정 함수를 한 번 더 부른다.
rng 는 상태를 스냅샷·복원하므로 게임이 갈라지지 않는다 — 짝지은 비교다.
persona.open_pct 에 rng 가 없음을 확인했다(짝 호출 안전).

production 무수정.
"""
import argparse
import collections
import copy
import json
import os
import random
import subprocess
import sys

TABLES = ('RFI_BY_BEHIND', '_DEPTH_EARLY', '_DEPTH_LATE', 'ANTE_MULT')
OLD_REV = 'e17be45'


def old_tables(repo, rev=OLD_REV):
    """옛 gto.py 원문에서 표 네 개를 꺼낸다. 값을 손으로 옮겨적지 않는다."""
    txt = subprocess.run(['git', 'show', '%s:gto.py' % rev],
                         cwd=repo, capture_output=True, text=True).stdout
    ns = {}
    # 표 정의부만 실행한다 — import 부작용을 피한다.
    import re
    pat = re.compile(r'^(?:%s)\s*=' % '|'.join(TABLES))
    lines, keep, buf = txt.split('\n'), False, []
    for ln in lines:
        if pat.match(ln):      # `_DEPTH_LATE  =` 처럼 공백이 둘인 경우가 있다
            keep = True
        if keep:
            buf.append(ln)
            if ln.rstrip().endswith('}') or ln.rstrip().endswith(']'):
                keep = False
    exec('\n'.join(buf), {}, ns)
    missing = [t for t in TABLES if t not in ns]
    if missing:
        raise SystemExit('옛 표를 못 찾았다: %s' % missing)
    return {t: ns[t] for t in TABLES}


class SwapOld(object):
    """gto 모듈의 표 네 개를 옛 값으로 바꿨다 되돌린다."""

    def __init__(self, gto, old):
        self.g, self.old, self.saved = gto, old, {}

    def __enter__(self):
        for t in TABLES:
            self.saved[t] = getattr(self.g, t)
            setattr(self.g, t, self.old[t])
        return self

    def __exit__(self, *a):
        for t in TABLES:
            setattr(self.g, t, self.saved[t])
        return False


def bb_band(bb):
    for hi in (10, 15, 20, 25, 30, 40, 60, 100):
        if bb < hi:
            return '<%d' % hi
    return '>=100'


def hand_class(pct_):
    for hi, lab in ((0.05, 'top5%'), (0.10, 'top10%'), (0.20, 'top20%'),
                    (0.35, 'top35%'), (0.60, 'top60%')):
        if pct_ <= hi:
            return lab
    return 'rest'


def run(repo, seeds, hands, out_path):
    if repo not in sys.path:
        sys.path.insert(0, repo)
    import gto as G
    import preflop as PF
    import tourney as T
    old = old_tables(repo)
    acc = collections.Counter()
    rows = []
    cur_hand = {'seed': None, 'h': -1}

    def paired(name, orig):
        def wrap(*a, **kw):
            # rng 는 위치/키워드 어느 쪽으로도 올 수 있다. 찾아서 스냅샷한다.
            rng = kw.get('rng')
            if rng is None:
                rng = next((x for x in a if isinstance(x, random.Random)), None)
            st0 = rng.getstate() if rng is not None else None
            new = orig(*a, **kw)
            st1 = rng.getstate() if rng is not None else None
            if st0 is not None:
                rng.setstate(st0)
            # money_open 등 mutable 인자는 복사본으로 넘겨 부작용을 막는다
            kw2 = {k: (copy.deepcopy(v) if isinstance(v, dict) else v)
                   for k, v in kw.items()}
            a2 = tuple(copy.deepcopy(x) if isinstance(x, dict) else x for x in a)
            st_old_end = None
            try:
                with SwapOld(G, old):
                    oldout = orig(*a2, **kw2)
                st_old_end = rng.getstate() if rng is not None else None
            finally:
                if st1 is not None:
                    rng.setstate(st1)
            # 행동이 같아도 rng 소비가 다르면 스트림이 밀린다 — 로그엔 안 보인다
            rng_diff = (st1 is not None and st_old_end is not None
                        and st1 != st_old_end)
            _rec(name, a, kw, new, oldout, rng_diff)
            return new
        return wrap

    def _rec(name, a, kw, new, oldout, rng_diff=False):
        def g(key, idx, dflt=None):
            if key in kw:
                return kw[key]
            return a[idx] if len(a) > idx else dflt
        if name == 'open':
            pos, bb, hand = g('pos', 1), g('bb', 2), g('hand', 3)
        else:
            pos, hand, bb = g('pos', 1), g('hand', 2), g('bb', 4)
        ante = kw.get('ante', True)
        seats = kw.get('seats', 8)
        try:
            hp = PF.pct(hand)
        except Exception:
            hp = None
        na = new[0] if isinstance(new, tuple) else str(new)
        oa = oldout[0] if isinstance(oldout, tuple) else str(oldout)
        acc['%s_n' % name] += 1
        if rng_diff:
            _na = new[0] if isinstance(new, tuple) else new
            _oa = oldout[0] if isinstance(oldout, tuple) else oldout
            rows.append({'kind': 'rng', 'fn': name, 'seed': cur_hand['seed'],
                         'hand': cur_hand['h'], 'old': _oa, 'new': _na})
            acc['%s_rngdiff' % name] += 1
            same_act = ((new[0] if isinstance(new, tuple) else new)
                        == (oldout[0] if isinstance(oldout, tuple) else oldout))
            acc['%s_rngdiff_%s' % (name, 'same_act' if same_act else 'diff_act')] += 1
        acc['%s_new_%s' % (name, na)] += 1
        acc['%s_old_%s' % (name, oa)] += 1
        if na != oa:
            acc['%s_flip' % name] += 1
            acc['%s_flip_%s>%s' % (name, oa, na)] += 1
            acc['%s_flip_pos_%s' % (name, pos)] += 1
            acc['%s_flip_bb_%s' % (name, bb_band(float(bb or 0)))] += 1
            if hp is not None:
                acc['%s_flip_hand_%s' % (name, hand_class(hp))] += 1
            acc['%s_flip_ante_%s' % (name, bool(ante))] += 1
            rows.append({'kind': 'act', 'seed': cur_hand['seed'],
                         'hand_no': cur_hand['h'], 'fn': name, 'pos': pos, 'bb': round(float(bb or 0), 2),
                         'ante': bool(ante), 'seats': seats,
                         'hand': list(hand) if hand else None,
                         'hand_pct': round(hp, 4) if hp is not None else None,
                         'old': oa, 'new': na,
                         'old_amt': (oldout[1] if isinstance(oldout, tuple) else None),
                         'new_amt': (new[1] if isinstance(new, tuple) else None)})
        acc['%s_pos_%s' % (name, pos)] += 1
        acc['%s_bb_%s' % (name, bb_band(float(bb or 0)))] += 1
        acc['%s_ante_%s' % (name, bool(ante))] += 1

    PF.open_decision = paired('open', PF.open_decision)
    PF.iso_decision = paired('iso', PF.iso_decision)

    for sd in seeds:
        t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                         seed=sd, hands_per_level=200)
        cur_hand['seed'] = sd
        for hi_ in range(hands):
            cur_hand['h'] = hi_
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            guard = 0
            while st and not st.get('done') and guard < 200:
                st = t.submit('fold')
                guard += 1
            t.finish_hand()
        print('  seed %d 누적 open %d / iso %d  (행동뒤집힘 %d/%d  rng차이 %d/%d)'
              % (sd, acc['open_n'], acc['iso_n'], acc['open_flip'],
                 acc['iso_flip'], acc['open_rngdiff'], acc['iso_rngdiff']),
              flush=True)
    json.dump({'acc': dict(acc), 'rows': rows},
              open(out_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    return acc, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--seeds', default='3000-3005')
    ap.add_argument('--hands', type=int, default=30)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi) + 1)) if hi else [int(lo)]
    acc, rows = run(a.repo, seeds, a.hands, a.out)
    print('\nwrote %s  (뒤집힘 행 %d)' % (a.out, len(rows)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
