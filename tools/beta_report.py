#!/usr/bin/env python3
"""Beta A report: layer transitions and poker-logic consistency.

Input: one or more JSON files from tools/beta_trace.py.  No external strategy
numbers are used (R2): every judgment check compares a decision with the bot's
own inputs (price, its own value criterion, hand ordering within one spot).

  python tools/beta_report.py OUT_DIR beta_11.json [beta_12.json ...]

Writes OUT_DIR/BETA_A_REPORT.md and OUT_DIR/beta_a_flags.json.
"""
import collections, json, os, sys

AGGR = {'fold': 0, 'check': 1, 'call': 1, 'limp': 1, 'raise': 2, 'shove': 2}
ENGINE = {'fold': {'fold', 'check'}, 'check': {'check'}, 'limp': {'call', 'check', 'allin'},
          'call': {'call', 'allin', 'check'}, 'shove': {'allin'}, 'raise': {'raise', 'allin'}}
VALUE_PLANS = ('value_3street', 'value_2street', 'value_thin', 'value')


def band(x, cuts):
    for c in cuts:
        if x < c:
            return '<%g' % c
    return '>=%g' % cuts[-1]


def card_str(cs):
    return ' '.join(cs or [])


def ex(hand, it, extra=None):
    d = {'hash': hand['hash'], 'seat': it.get('seat'), 'pos': hand['pos'].get(str(it.get('seat'))),
         'hole': card_str(hand['hole'].get(str(it.get('seat')))), 'board': card_str(hand.get('board')),
         'street': it.get('street'), 'plan': it.get('plan'), 'action': it.get('action'),
         'amt': it.get('amt'), 'tocall': it.get('tocall'), 'pot': it.get('pot'),
         'rel': it.get('rel'), 'rel_true': it.get('rel_true'), 'eq': it.get('eq'),
         'made': it.get('made'), 'outs': it.get('outs'),
         'resp_eq': it.get('resp_eq'), 'resp_need': it.get('resp_need'),
         'resp_src': it.get('resp_src'), 'intent_act': it.get('intent_act'),
         'calc_act': it.get('calculated_act'), 'why': it.get('why')}
    if extra:
        d.update(extra)
    return d


def analyse(files):
    F = collections.defaultdict(list)          # flag name -> examples
    S = collections.Counter()                  # scalar counters
    T = collections.defaultdict(collections.Counter)   # tables
    pf_groups = collections.defaultdict(list)
    for fn in files:
        blob = json.load(open(fn))
        hands = {h['hash']: h for h in blob['hands']}
        S['hands'] += len(hands)
        # ---------------- preflop: plan -> engine ----------------
        pf_by = collections.defaultdict(list)
        for r in blob['pf']:
            pf_by[(r['hash'], r['seat'])].append(r)
        for hsh, hand in hands.items():
            used = collections.Counter()
            for row in (hand.get('full_log') or []):
                st, seat, act, amt = row[0], row[1], row[2], row[3]
                if st != 'preflop':
                    continue
                lst = pf_by.get((hsh, seat)) or []
                i = used[seat]; used[seat] += 1
                if i >= len(lst):
                    S['pf_engine_rows_without_plan'] += 1
                    continue
                r = lst[i]
                S['pf_decisions'] += 1
                T['pf_plan_to_engine'][(r['act'], act)] += 1
                if act not in ENGINE.get(r['act'], {act}):
                    F['X1_pf_plan_engine_mismatch'].append(
                        {'hash': hsh, 'seat': seat, 'pos': r['pos'], 'hand': card_str(r['hand']),
                         'plan_act': r['act'], 'engine_act': act, 'size_bb': r['sz']})
                if r['act'] == 'raise' and act == 'raise' and r['sz']:
                    tgt = float(hand['bb']) * float(r['sz'])
                    if amt and tgt and amt > tgt * 1.05:
                        S['pf_raise_clamped_up'] += 1
                sd = r.get('seed') or {}
                kind = sd.get('pf_decision_kind')
                key = (r['pos'], kind, sd.get('pf_level'),
                       band(float(sd.get('pf_stack_bb') or 0), [12, 20, 30, 50, 80]),
                       band(float(sd.get('pf_to_call_bb') or 0), [1.01, 3, 6, 12, 25]),
                       bool(sd.get('pf_multiway')))
                pct = sd.get('pf_hand_pct')
                if pct is not None:
                    pf_groups[key].append((float(pct), AGGR.get(r['act'], 1), r, hsh))
                T['pf_act_by_kind'][(kind, r['act'])] += 1
            S['pf_plans_unmatched'] += sum(max(0, len(v) - used[k[1]])
                                           for k, v in pf_by.items() if k[0] == hsh)
        # ---------------- postflop ----------------
        for hsh, hand in hands.items():
            for it in hand['intents']:
                if 'action' not in it:
                    S['pf_intent_without_action'] += 1
                    continue
                S['post_decisions'] += 1
                st = it.get('street'); a = it.get('action'); tc = it.get('tocall') or 0
                T['plan_by_street'][(st, it.get('plan'))] += 1
                T['plan_to_action'][(it.get('plan'), 'facing' if tc > 0 else 'free', a)] += 1
                # -- plan layer: stored intent vs calculated act (no resistance)
                if tc <= 0 and it.get('intent_act') and it.get('calculated_act'):
                    ia, ca = it['intent_act'], it['calculated_act']
                    S['free_with_intent'] += 1
                    if ia != ca and not (ia == 'bet' and ca in ('raise', 'allin')):
                        F['P1_intent_vs_calculated'].append(ex(hand, it))
                if it.get('plan') is None:
                    F['P2_action_without_plan'].append(ex(hand, it))
                # -- execution layer
                for dv in (it.get('dev') or []):
                    if str(dv.get('why', '')).startswith('사이즈 거부'):
                        F['E1_execution_fallback'].append(ex(hand, it, {'dev': dv}))
                    elif it.get('plan') == 'showdown' and a in ('bet', 'raise', 'allin'):
                        F['J7_showdown_value_turned_bluff'].append(ex(hand, it, {'dev': dv}))
                    else:
                        S['planned_deviation_%s' % it.get('plan')] += 1
                if it.get('shape_called') and it.get('calculated_target'):
                    S['shaped_bets'] += 1
                    r0 = float(it.get('shaped_target') or 0) / max(1.0, float(it['calculated_target']))
                    if r0 > 1.12 or r0 < 0.88:
                        F['E4_odd_size_habit'].append(ex(hand, it, {'calc_target': it['calculated_target'],
                                                                    'shaped_target': it.get('shaped_target')}))
                ca = it.get('calculated_act')
                if ca and a != ca and not (ca in ('bet', 'raise') and a == 'allin') \
                        and it.get('execution_input_source') != 'forced_replay' \
                        and not any(str(d.get('why', '')).startswith('사이즈 거부') for d in (it.get('dev') or [])):
                    F['E2_calculated_vs_executed'].append(ex(hand, it))
                if a in ('bet', 'raise') and it.get('calculated_target') and it.get('final_target'):
                    ct, ft = float(it['calculated_target']), float(it['final_target'])
                    T['target_transition'][(
                        'shape_changed' if it.get('shape_changed') else 'shape_same',
                        'minraise_clamped' if it.get('min_raise_clamped') else 'no_clamp',
                        'eff_allin' if it.get('effective_allin_applied') else 'no_eff_allin')] += 1
                    r_ = ft / max(1.0, ct)
                    if (r_ > 1.5 or r_ < 0.67) and not it.get('effective_allin_applied') \
                            and not it.get('min_raise_clamped') and not it.get('shape_changed'):
                        F['E3_target_drift'].append(ex(hand, it, {'calc_target': ct, 'final_target': ft}))
                # -- judgment layer (bot's own inputs)
                e, n = it.get('resp_eq'), it.get('resp_need')
                if tc > 0 and e is not None and n is not None:
                    S['facing_priced'] += 1
                    if a == 'call' and e < n - 0.05:
                        F['J1_call_below_price'].append(ex(hand, it, {'gap': round(e - n, 3)}))
                    if a == 'fold' and e > n + 0.10:
                        F['J2_fold_above_price'].append(ex(hand, it, {'gap': round(e - n, 3)}))
                if tc > 0 and a == 'fold' and ((it.get('rel_true') or 0) >= 0.95 or (it.get('made') or 0) >= 6):
                    F['J3_strong_fold'].append(ex(hand, it))
                if tc <= 0 and a in ('bet', 'raise', 'allin') and str(it.get('plan') or '').startswith('value') \
                        and (it.get('rel') if it.get('rel') is not None else 1) < 0.45:
                    F['J4_value_bet_low_rel'].append(ex(hand, it))
                if st == 'river' and tc <= 0 and a == 'check' and (it.get('rel') or 0) >= 0.90:
                    src = str(it.get('intent_src') or '')
                    cause = ('OOP 상대에게 액션 우선' if '액션 우선' in src else
                             '밸류 실행 확률 미달' if src.startswith('밸류 계획 실행') else
                             '사이즈 0' if '사이즈 0' in src else
                             '쇼다운/포기 계획' if it.get('plan') in ('showdown', 'giveup') else 'other')
                    T['river_strong_check_cause'][cause] += 1
                    F['J5_river_check_strong'].append(ex(hand, it, {'cause': cause, 'intent_src': src}))
    # ---------------- preflop ordering inversions ----------------
    inv_groups = []
    for key, rows in pf_groups.items():
        cont = [p for p, ag, _, _ in rows if ag >= 1]
        folds = [(p, r, h) for p, ag, r, h in rows if ag == 0]
        if not cont or not folds:
            continue
        widest = max(cont)
        bad = [(p, r, h) for p, r, h in folds if p < widest]
        S['pf_groups_checked'] += 1
        if bad:
            S['pf_inverted_folds'] += len(bad)
            inv_groups.append({'spot': list(map(str, key)), 'n': len(rows), 'widest_continue_pct': round(widest, 4),
                               'strongest_fold_pct': round(min(p for p, _, _ in bad), 4), 'inverted_folds': len(bad),
                               'examples': [{'hash': h, 'hand': card_str(r['hand']), 'pct': p} for p, r, h in sorted(bad, key=lambda x: x[0])[:3]]})
        for p, r, h in folds:
            if p <= 0.03 and float((r.get('seed') or {}).get('pf_to_call_bb') or 0) < \
                    0.5 * float((r.get('seed') or {}).get('pf_stack_bb') or 1e9):
                F['J6_pf_premium_fold'].append({'hash': h, 'pos': r['pos'], 'hand': card_str(r['hand']), 'pct': p,
                                                'kind': (r.get('seed') or {}).get('pf_decision_kind'),
                                                'to_call_bb': (r.get('seed') or {}).get('pf_to_call_bb'),
                                                'stack_bb': (r.get('seed') or {}).get('pf_stack_bb')})
    inv_groups.sort(key=lambda g: (g['strongest_fold_pct']))
    return F, S, T, inv_groups


DESC = {
    'X1_pf_plan_engine_mismatch': ('실행', '프리플랍 계획 액션과 엔진 적용 액션이 다름'),
    'P1_intent_vs_calculated': ('계획→실행', '저항 없는 상황에서 저장 intent 와 계산 액션이 다름'),
    'P2_action_without_plan': ('계획', '계획 없이 실행된 포스트플랍 액션'),
    'E1_execution_fallback': ('실행', '사이즈 거부로 대체 실행(call/check)'),
    'E2_calculated_vs_executed': ('실행', '계산 액션과 실행 액션이 다름(올인 변환·재생 제외)'),
    'E3_target_drift': ('실행', '사이즈 습관 이후 단계에서 금액이 ×1.5 초과/×0.67 미만으로 바뀜(유효올인·최소레이즈 제외)'),
    'E4_odd_size_habit': ('계획', '사이즈 습관이 계획 금액을 ±12% 넘게 바꿈(odd 사이즈)'),
    'J1_call_below_price': ('판단', '상대 베팅 레인지 대비 eq 가 필요 승률보다 0.05 넘게 낮은데 콜'),
    'J2_fold_above_price': ('판단', '상대 베팅 레인지 대비 eq 가 필요 승률보다 0.10 넘게 높은데 폴드'),
    'J3_strong_fold': ('판단', 'rel_true ≥ 0.95 또는 풀하우스 이상으로 폴드'),
    'J4_value_bet_low_rel': ('판단', '밸류 계획으로 베팅했지만 rel < 0.45'),
    'J5_river_check_strong': ('판단', '리버 무저항 상황에서 rel ≥ 0.90 인데 체크'),
    'J6_pf_premium_fold': ('판단', '프리플랍 상위 3% 손을 콜 비용이 스택의 절반 미만인데 폴드'),
    'J7_showdown_value_turned_bluff': ('판단', '쇼다운 계획 손이 계획 이탈 확률로 베팅(쇼다운 가치를 블러프로 전환)'),
}


def write(out_dir, files, F, S, T, inv):
    os.makedirs(out_dir, exist_ok=True)
    L = ['# 베타 A 보고서 — 최고 숙련 단일 필드', '',
         '조건: 모든 봇 최고 숙련, 중립 기질, 틸트 0, 상대 장부 고정(`tools/r2_baseline_sim.py`). 입력: %s.' % ', '.join(os.path.basename(f) for f in files),
         '판단 검사는 외부 전략 수치를 쓰지 않는다. 봇 자신의 입력(가격, 자기 밸류 기준, 같은 상황 안의 손 순서)과 결정을 비교한다.', '',
         '## 규모', '',
         '| 항목 | 값 |', '|---|---|']
    for k in ('hands', 'pf_decisions', 'post_decisions', 'facing_priced', 'free_with_intent', 'pf_groups_checked',
              'pf_inverted_folds', 'pf_engine_rows_without_plan', 'pf_plans_unmatched', 'pf_raise_clamped_up',
              'pf_intent_without_action'):
        L.append('| %s | %s |' % (k, S.get(k, 0)))
    L += ['', '## 검사 결과', '', '| 검사 | 층 | 내용 | 건수 |', '|---|---|---|---|']
    for k, (layer, d) in DESC.items():
        L.append('| %s | %s | %s | %d |' % (k, layer, d, len(F.get(k, []))))
    L += ['', '## 계획 → 실행 (포스트플랍)', '', '| plan | 상황 | 액션 | 건수 |', '|---|---|---|---|']
    for (p, sit, a), n in sorted(T['plan_to_action'].items(), key=lambda x: (str(x[0][0]), x[0][1], -x[1])):
        L.append('| %s | %s | %s | %d |' % (p, sit, a, n))
    L += ['', '## 리버 강한 손(rel ≥ 0.90) 무저항 체크 원인', '', '| 원인 | 건수 |', '|---|---|']
    for k, n in T['river_strong_check_cause'].most_common():
        L.append('| %s | %d |' % (k, n))
    L += ['', '## 금액 전이 (bet/raise)', '', '| 사이즈 습관 | 최소레이즈 | 유효올인 | 건수 |', '|---|---|---|---|']
    for k, n in sorted(T['target_transition'].items(), key=lambda x: -x[1]):
        L.append('| %s | %s | %s | %d |' % (k + (n,)))
    L += ['', '## 프리플랍 계획 → 엔진', '', '| 계획 | 엔진 | 건수 |', '|---|---|---|']
    for (p, e), n in sorted(T['pf_plan_to_engine'].items(), key=lambda x: -x[1]):
        L.append('| %s | %s | %d |' % (p, e, n))
    L += ['', '## 프리플랍 순서 역전 (같은 상황에서 더 강한 손이 폴드, 더 약한 손이 계속)', '',
          '상황 = (포지션, 종류, 레벨, 스택 구간, 콜 비용 구간, 멀티웨이). pct 는 손 순위 백분위(낮을수록 강함).', '',
          '| 상황 | 결정 수 | 가장 넓게 계속한 pct | 가장 강하게 폴드한 pct | 역전 폴드 | 예시 |', '|---|---|---|---|---|---|']
    for g in inv[:25]:
        L.append('| %s | %d | %s | %s | %d | %s |' % (' / '.join(g['spot']), g['n'], g['widest_continue_pct'],
                                                  g['strongest_fold_pct'], g['inverted_folds'],
                                                  ', '.join('%s(%.3f)' % (e['hand'], e['pct']) for e in g['examples'])))
    L += ['', '## 표시된 결정 예시', '']
    for k in DESC:
        lst = F.get(k, [])
        if not lst:
            continue
        L.append('### %s (%d)' % (k, len(lst)))
        L.append('')
        for e in lst[:6]:
            L.append('- `%s`' % json.dumps(e, ensure_ascii=False))
        L.append('')
    open(os.path.join(out_dir, 'BETA_A_REPORT.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    json.dump({'counts': dict(S), 'flags': F, 'pf_inversions': inv},
              open(os.path.join(out_dir, 'beta_a_flags.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1, default=str)


def main():
    out_dir, files = sys.argv[1], sys.argv[2:]
    F, S, T, inv = analyse(files)
    write(out_dir, files, F, S, T, inv)
    print(json.dumps({k: len(v) for k, v in F.items()}, ensure_ascii=False))
    print(json.dumps(dict(S)))


if __name__ == '__main__':
    main()
