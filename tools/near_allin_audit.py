#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Near-all-in sizing audit (read-only).

목적:
  계산된 bet/raise가 올인은 아니지만 스택 대부분을 넣고 작은 잔여만 남기는
  사례를 먼저 계측한다. production 행동은 바꾸지 않는다.

예:
  python3 tools/near_allin_audit.py --seeds 6000-6007
  python3 tools/near_allin_audit.py --seeds 6000-6015 --rows /sdcard/Download/near_allin.csv

기록값:
  commit_frac   이 스트리트 시작 가용 스택 중 실제 target으로 커밋한 비율
  residual      액션 뒤 남는 칩
  residual_bb   남는 칩 / 현재 BB
  residual_pot  남는 칩 / 액션 직전 live pot

주의:
- session.HandRun이 이미 남기는 h.intents를 읽기만 한다.
- stack은 액션 뒤 remaining stack + current-street contribution이라,
  같은 스트리트에서 재액션해도 그 스트리트 시작 가용 스택을 복원한다.
- amt는 실행 target이다. Round.apply 내부에서 올인 clamp가 걸릴 수 있으므로
  분석에서는 min(amt, stack)을 실제 커밋액으로 사용한다.
- persona._TILT_VIEW_CACHE의 대회 간 오염이 확인돼 있으므로 각 tournament
  시작 전에 이 캐시만 계측 도구에서 비운다. production 코드는 수정하지 않는다.
- multiprocessing을 쓰지 않는다.
"""
from __future__ import print_function

import argparse
import collections
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import persona as PS

RATIO_THRESHOLDS = (0.80, 0.85, 0.90, 0.95)
BB_LIMITS = (1.0, 2.0, 3.0, 5.0)


def parse_seeds(spec):
    spec = str(spec).strip()
    if ',' in spec:
        return [int(x.strip()) for x in spec.split(',') if x.strip()]
    if '-' in spec:
        lo, hi = spec.split('-', 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(spec)]


def clear_tilt_cache():
    c = getattr(PS, '_TILT_VIEW_CACHE', None)
    if hasattr(c, 'clear'):
        c.clear()
        return True
    return False


def collect_tournament(seed, entries, hpl, start_stack, cap, fmt):
    rows = []
    returns = []
    old_logger = FS.Field._log_bot_hand
    old_bot_log = getattr(FS.Field, 'BOT_LOG', None)

    def capture(field, tb, h, run):
        bb = float(getattr(h, 'bb', 0) or 0)
        pids = getattr(h, 'seat_pid', {}) or {}
        for ur in (getattr(h, 'uncalled_returns', None) or []):
            returns.append({
                'seed': seed,
                'hand_no': int(getattr(field, 'hand_no', 0) or 0),
                'table': getattr(tb, 'id', None),
                'street': ur.get('street'),
                'seat': ur.get('seat'),
                'pid': pids.get(ur.get('seat')),
                'amount': float(ur.get('amount') or 0),
                'from': float(ur.get('from') or 0),
                'to': float(ur.get('to') or 0),
                'bb': bb,
            })
        _mj_groups = collections.defaultdict(list)
        for _ob in (getattr(h, 'money_jump_obs', None) or []):
            _mj_groups[(_ob.get('street'), _ob.get('seat'))].append(_ob)

        for it in (getattr(h, 'intents', None) or []):
            action = it.get('action')
            if action not in ('bet', 'raise', 'allin'):
                continue

            stack = float(it.get('stack') or 0)
            raw_amt = float(it.get('amt') or 0)
            if stack <= 0 or raw_amt <= 0:
                continue

            committed = min(stack, raw_amt)
            residual = max(0.0, stack - committed)
            pot = float(it.get('pot') or 0)
            seat = it.get('seat')
            _idx = int(it.get('idx') or 0)
            _obs_list = _mj_groups.get((it.get('street'), seat), [])
            _mj = _obs_list[_idx] if 0 <= _idx < len(_obs_list) else {}
            _ms = (_mj.get('money_signals') or {}) if _mj else {}
            rows.append({
                'seed': seed,
                'hand_no': int(getattr(field, 'hand_no', 0) or 0),
                'table': getattr(tb, 'id', None),
                'seat': seat,
                'pid': pids.get(seat),
                'street': it.get('street'),
                'action': action,
                'plan': it.get('plan'),
                'plan_goal': it.get('plan_goal'),
                'intent_act': it.get('intent_act'),
                'intent_size': it.get('intent_size'),
                'pot': pot,
                'tocall': float(it.get('tocall') or 0),
                'bb': bb,
                'stack': stack,
                'raw_amt': raw_amt,
                'committed': committed,
                'commit_frac': committed / stack,
                'residual': residual,
                'residual_bb': (residual / bb) if bb > 0 else None,
                'residual_pot': (residual / pot) if pot > 0 else None,
                'pre_clamp': it.get('pre_clamp'),
                'type': it.get('type'),
                'contrib_before': it.get('contrib_before'),
                'actor_cap': it.get('actor_cap'),
                'opp_cap_max': it.get('opp_cap_max'),
                'effective_cap': it.get('effective_cap'),
                'increment': it.get('increment'),
                'pot_after': it.get('pot_after'),
                'own_residual_post': it.get('own_residual_post'),
                'effective_gap': it.get('effective_gap'),
                'post_spr_own': it.get('post_spr_own'),
                'post_spr_effective': it.get('post_spr_effective'),
                'pre_effective_target': it.get('pre_effective_target'),
                'effective_allin_candidate': it.get('effective_allin_candidate'),
                'effective_allin_actor': it.get('effective_allin_actor'),
                'effective_allin_commit': it.get('effective_allin_commit'),
                'effective_allin_post_spr': it.get('effective_allin_post_spr'),
                'effective_allin_applied': it.get('effective_allin_applied'),
                'allin_execution_mode': it.get('allin_execution_mode'),
                # leave-behind 설계용 money-jump provenance. 판단에는 쓰지 않는다.
                'money_decision_kind': _mj.get('decision_kind') if _mj else None,
                'money_bf': _mj.get('bf') if _mj else None,
                'money_remaining': _mj.get('remaining') if _mj else None,
                'money_itm': _mj.get('itm') if _mj else None,
                'money_pos': _mj.get('pos') if _mj else None,
                'money_players_to_jump': _mj.get('players_to_jump') if _mj else None,
                'money_current_prize': _mj.get('current_prize') if _mj else None,
                'money_next_prize': _mj.get('next_prize') if _mj else None,
                'money_jump_frac_next': _mj.get('jump_frac_next') if _mj else None,
                'money_jump_vs_mincash': _mj.get('jump_vs_mincash') if _mj else None,
                'money_distance_frac_itm': _mj.get('distance_frac_itm') if _mj else None,
                'money_distance_frac_remaining': _mj.get('distance_frac_remaining') if _mj else None,
                'money_stack_behind_bb': _mj.get('stack_behind_bb') if _mj else None,
                'money_hands_to_next_bb': _mj.get('hands_to_next_bb') if _mj else None,
                'money_forced_cost_to_next_bb': _mj.get('forced_cost_to_next_bb') if _mj else None,
                'money_forced_cost_share_of_stack': _mj.get('forced_cost_share_of_stack') if _mj else None,
                'money_stack_after_next_bb_if_fold_all': _mj.get('stack_after_next_bb_if_fold_all') if _mj else None,
                'money_n_shorter': _mj.get('n_shorter') if _mj else None,
                'money_median_shorter_ratio': _mj.get('median_shorter_ratio') if _mj else None,
                'money_payout_importance': _ms.get('payout_importance'),
                'money_ladder_buffer': _ms.get('ladder_buffer'),
                'money_waiting_feasibility': _ms.get('waiting_feasibility'),
                'money_self_preservation_objective': _ms.get('self_preservation_objective'),
                'money_self_preservation': _ms.get('self_preservation'),
                'money_urgency_objective': _ms.get('urgency_objective'),
                'money_urgency': _ms.get('urgency'),
                'money_commitment_budget': _ms.get('commitment_budget'),
            })

    clear_tilt_cache()
    FS.Field._log_bot_hand = capture
    if old_bot_log is not None:
        FS.Field.BOT_LOG = 0

    try:
        kw = dict(entries=entries, start_stack=start_stack, hero_pid=0,
                  seed=seed, hands_per_level=hpl)
        if fmt:
            kw['fmt'] = fmt
        f = FS.Field(**kw)

        while f.remaining() > 1 and f.hand_no < cap:
            f.hand_no += 1
            f.advance_level()
            for _tid, tb in list(f.tables.items()):
                if tb.n() >= 2:
                    f._play_table(tb)
            f._collect_busts()
            f._balance()
            f.notes = []

        return rows, returns, list(getattr(f, 'errors', ()) or []), int(f.hand_no)
    finally:
        FS.Field._log_bot_hand = old_logger
        if old_bot_log is not None:
            FS.Field.BOT_LOG = old_bot_log


def pct(n, d):
    return 100.0 * n / d if d else 0.0


def fnum(x):
    if x is None:
        return '-'
    if abs(float(x) - round(float(x))) < 1e-9:
        return str(int(round(float(x))))
    return ('%.2f' % float(x)).rstrip('0').rstrip('.')


def write_rows(path, rows):
    fields = [
        'seed', 'hand_no', 'table', 'seat', 'pid', 'street', 'action',
        'plan', 'plan_goal', 'intent_act', 'intent_size',
        'pot', 'tocall', 'bb', 'stack', 'raw_amt', 'committed',
        'commit_frac', 'residual', 'residual_bb', 'residual_pot',
        'pre_clamp', 'type',
        'contrib_before', 'actor_cap', 'opp_cap_max', 'effective_cap',
        'increment', 'pot_after', 'own_residual_post', 'effective_gap',
        'post_spr_own', 'post_spr_effective',
        'pre_effective_target', 'effective_allin_candidate',
        'effective_allin_actor', 'effective_allin_commit',
        'effective_allin_post_spr', 'effective_allin_applied',
        'allin_execution_mode',
        'money_decision_kind', 'money_bf', 'money_remaining', 'money_itm',
        'money_pos', 'money_players_to_jump', 'money_current_prize',
        'money_next_prize', 'money_jump_frac_next', 'money_jump_vs_mincash',
        'money_distance_frac_itm', 'money_distance_frac_remaining',
        'money_stack_behind_bb', 'money_hands_to_next_bb',
        'money_forced_cost_to_next_bb', 'money_forced_cost_share_of_stack',
        'money_stack_after_next_bb_if_fold_all', 'money_n_shorter',
        'money_median_shorter_ratio', 'money_payout_importance',
        'money_ladder_buffer', 'money_waiting_feasibility',
        'money_self_preservation_objective', 'money_self_preservation',
        'money_urgency_objective', 'money_urgency', 'money_commitment_budget',
    ]
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, 'w', newline='', encoding='utf-8') as fp:
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=24)
    ap.add_argument('--hpl', type=int, default=12)
    ap.add_argument('--stack', type=int, default=30000)
    ap.add_argument('--seeds', default='6000-6007')
    ap.add_argument('--cap', type=int, default=3000)
    ap.add_argument('--fmt', default='standard')
    ap.add_argument('--top', type=int, default=30)
    ap.add_argument('--rows', default='')
    a = ap.parse_args()

    seeds = parse_seeds(a.seeds)
    all_rows = []
    all_returns = []
    errors = []
    hands = 0

    print('# near-all-in sizing audit')
    print('entries=%d hpl=%d start_stack=%d fmt=%s seeds=%s cap=%d'
          % (a.entries, a.hpl, a.stack, a.fmt, a.seeds, a.cap))
    print('single-process / tournament마다 _TILT_VIEW_CACHE clear / production 무수정')
    print()

    for idx, seed in enumerate(seeds, 1):
        rows, rets, errs, hn = collect_tournament(
            seed, a.entries, a.hpl, a.stack, a.cap, a.fmt)
        all_rows.extend(rows)
        all_returns.extend(rets)
        errors.extend((seed, x) for x in errs)
        hands += hn
        print('[%d/%d] seed %d  hands %d  aggressive actions %d  uncalled returns %d  errors %d'
              % (idx, len(seeds), seed, hn, len(rows), len(rets), len(errs)), flush=True)

    print()
    print('## sanity')
    print('tournaments %d  field hands %d  aggressive postflop actions %d  engine errors %d'
          % (len(seeds), hands, len(all_rows), len(errors)))
    if errors:
        print('ENGINE ERRORS — 결과 무효')
        for seed, e in errors[:10]:
            print('  seed %d: %s' % (seed, e))
        return 1

    print()
    print('## uncalled return')
    print('returns %d  total chips %s'
          % (len(all_returns), fnum(sum(r['amount'] for r in all_returns))))
    if all_returns:
        by_street = collections.Counter(r['street'] for r in all_returns)
        print('by street: ' + ' / '.join('%s=%d' % (k, v)
                                         for k, v in sorted(by_street.items())))
        print('largest:')
        for r in sorted(all_returns, key=lambda x: x['amount'], reverse=True)[:10]:
            print('  seed %(seed)s H%(hand)s T%(table)s %(street)s S%(seat)s '
                  'return=%(amount)s from=%(from_)s to=%(to)s (%(bb)sBB)'
                  % {'seed': r['seed'], 'hand': r['hand_no'], 'table': r['table'],
                     'street': r['street'], 'seat': r['seat'],
                     'amount': fnum(r['amount']), 'from_': fnum(r['from']),
                     'to': fnum(r['to']),
                     'bb': fnum(r['amount']/r['bb']) if r['bb'] else '-'})

    actual_allin = [r for r in all_rows if r['commit_frac'] >= 1.0 - 1e-12]
    nonallin = [r for r in all_rows if r['commit_frac'] < 1.0 - 1e-12]

    print()
    print('## 전체')
    print('actual all-in/clamped %d (%.2f%% of aggressive)'
          % (len(actual_allin), pct(len(actual_allin), len(all_rows))))
    print('non-all-in aggressive %d' % len(nonallin))

    print()
    print('## commit 비율 누적 — 최종 기준을 정하지 않고 분포만 본다')
    for t in RATIO_THRESHOLDS:
        q = [r for r in nonallin if r['commit_frac'] >= t]
        print('  >= %2d%%   %6d   %.2f%% of non-all-in / %.2f%% of all aggressive'
              % (int(t * 100), len(q), pct(len(q), len(nonallin)),
                 pct(len(q), len(all_rows))))

    print()
    print('## commit 비율 구간')
    cuts = (0.0,) + RATIO_THRESHOLDS + (1.0,)
    for lo, hi in zip(cuts[:-1], cuts[1:]):
        if lo == 0.0:
            q = [r for r in nonallin if r['commit_frac'] < hi]
            lab = '<%d%%' % int(hi * 100)
        else:
            q = [r for r in nonallin if lo <= r['commit_frac'] < hi]
            lab = '%d-%d%%' % (int(lo * 100), int(hi * 100))
        print('  %-8s %6d' % (lab, len(q)))

    print()
    print('## near-all-in 교차표 — commit 비율 × 남는 BB')
    head = 'commit'.ljust(10) + ''.join(('<=%.0fBB' % b).rjust(10) for b in BB_LIMITS)
    print(head)
    for t in RATIO_THRESHOLDS:
        q = [r for r in nonallin if r['commit_frac'] >= t]
        vals = []
        for b in BB_LIMITS:
            vals.append(sum(1 for r in q
                            if r['residual_bb'] is not None and r['residual_bb'] <= b))
        print(('>=%d%%' % int(t * 100)).ljust(10)
              + ''.join(str(x).rjust(10) for x in vals))

    cand80 = [r for r in nonallin if r['commit_frac'] >= 0.80]
    print()
    print('## 잔여 BB 단독 분포 — commit 비율과 무관하게 본다')
    for b in (0.5, 1.0, 2.0, 3.0, 5.0):
        q = [r for r in nonallin
             if r['residual_bb'] is not None and r['residual_bb'] <= b]
        q80 = sum(1 for r in q if r['commit_frac'] >= 0.80)
        print('  <=%3.1fBB   %6d   (그중 commit>=80%%: %d)'
              % (b, len(q), q80))

    print()
    print('## 잔여/pot 단독 분포')
    for x in (0.02, 0.05, 0.10, 0.20):
        q = [r for r in nonallin
             if r['residual_pot'] is not None and r['residual_pot'] <= x]
        print('  <=%2d%% pot %6d' % (int(x*100), len(q)))

    have_eff = any(r.get('effective_cap') is not None for r in nonallin)
    if have_eff:
        print()
        print('## final legal target 기준 effective-stack 진단')
        for t in (0.90, 0.95, 0.98):
            q = []
            for r in nonallin:
                cap = r.get('effective_cap')
                if cap is None:
                    continue
                cap = float(cap or 0)
                if cap <= 0:
                    continue
                eff_frac = min(float(r['committed']), cap) / cap
                if eff_frac >= t:
                    q.append(r)
            print('  effective commit >=%2d%% : %6d'
                  % (int(t*100), len(q)))
        print('  post-action effective SPR:')
        for x in (0.02, 0.05, 0.10, 0.20):
            n = sum(1 for r in nonallin
                    if r.get('post_spr_effective') is not None
                    and float(r['post_spr_effective']) <= x)
            print('    <= %.2f : %6d' % (x, n))
        print('  own-stack post-action SPR:')
        for x in (0.02, 0.05, 0.10, 0.20):
            n = sum(1 for r in nonallin
                    if r.get('post_spr_own') is not None
                    and float(r['post_spr_own']) <= x)
            print('    <= %.2f : %6d' % (x, n))

    have_caps = any(r.get('opp_cap_max') is not None for r in all_rows)
    if have_caps:
        overs = []
        for r in all_rows:
            opp = r.get('opp_cap_max')
            if opp is None:
                continue
            excess = max(0.0, float(r['committed']) - float(opp))
            if excess > 0:
                overs.append((excess, r))
        print()
        print('## action-time guaranteed unmatchable excess')
        print('actions %d  total lower-bound chips %s'
              % (len(overs), fnum(sum(x[0] for x in overs))))
        print('round-end returned / action-time lower bound: %s / %s'
              % (fnum(sum(r['amount'] for r in all_returns)),
                 fnum(sum(x[0] for x in overs))))

    print()
    print('## >=80%% 사례의 street')
    for k, n in collections.Counter(r['street'] for r in cand80).most_common():
        print('  %-8s %6d' % (str(k), n))

    print()
    print('## >=80%% 사례의 plan')
    for k, n in collections.Counter(r['plan'] for r in cand80).most_common(20):
        print('  %-22s %6d' % (str(k), n))

    print()
    print('## 가장 극단적인 non-all-in 사례')
    ranked = sorted(
        nonallin,
        key=lambda r: (r['commit_frac'],
                       -(r['residual_bb'] if r['residual_bb'] is not None else 1e9)),
        reverse=True)
    for r in ranked[:max(0, a.top)]:
        print(
            '  seed %(seed)s H%(hand_no)s T%(table)s S%(seat)s '
            '%(street)s %(action)s plan=%(plan)s  '
            'stack=%(stack)s amt=%(committed)s remain=%(residual)s '
            'commit=%(commit)s remainBB=%(rbb)s remain/pot=%(rpot)s '
            'pot=%(pot)s tocall=%(tocall)s intent=%(intent)s pre=%(pre)s '
            'effcap=%(effcap)s effgap=%(effgap)s postSPR=%(postspr)s'
            % {
                'seed': r['seed'], 'hand_no': r['hand_no'], 'table': r['table'],
                'seat': r['seat'], 'street': r['street'], 'action': r['action'],
                'plan': r['plan'], 'stack': fnum(r['stack']),
                'committed': fnum(r['committed']), 'residual': fnum(r['residual']),
                'commit': '%.1f%%' % (100 * r['commit_frac']),
                'rbb': fnum(r['residual_bb']), 'rpot': fnum(r['residual_pot']),
                'pot': fnum(r['pot']), 'tocall': fnum(r['tocall']),
                'intent': fnum(r['intent_size']), 'pre': fnum(r['pre_clamp']),
                'effcap': fnum(r.get('effective_cap')),
                'effgap': fnum(r.get('effective_gap')),
                'postspr': fnum(r.get('post_spr_effective')),
            })

    if a.rows:
        write_rows(a.rows, all_rows)
        print()
        print('rows: %s' % a.rows)

    print()
    print('판정은 아직 하지 않는다. 이 출력으로 80/85/90/95%% 구간과')
    print('잔여 1/2/3/5BB가 실제로 얼마나 겹치는지 본 뒤 shove 보정 설계를 잠근다.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
