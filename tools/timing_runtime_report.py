#!/usr/bin/env python3
"""T4 측정: 시간 규칙(T2_TIMING_V1=enforce)으로 돌린 완주 trace 의 실제 분포.

목표값을 정하지 않는다(사용자 결정 §9-C). 지금 고정비용 모델과 v2 를 같은 핸드에서 비교만 한다.

  python tools/timing_runtime_report.py OUT.json TRACE...   (timing_trace.py 를 enforce 로 돌린 결과)
"""
import json, os, statistics as st, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import timing as TM
import live2 as L
import bot_timing_design_sim as SIM

q = lambda a, x: round(sorted(a)[int(x * (len(a) - 1))], 2) if a else None
mean = lambda a: round(st.mean(a), 2) if a else None


def dist(a):
    return {'n': len(a), 'mean': mean(a), 'p50': q(a, .5), 'p90': q(a, .9)}


def main():
    out_path, paths = sys.argv[1], sys.argv[2:]
    old_s, new_s, by_phase = [], [], {}
    dec = []
    seen_pid = {}
    for pth in paths:
        tr = json.load(open(pth))
        tseed = tr['seed']
        stage = tr.get('stage') or {}
        for h in tr['hands']:
            tl = h.get('timing')
            if tl is None:
                continue
            res = {'full_log': h.get('full_log') or [],
                   'showdown': h.get('how') not in ('fold', 'void', None)}
            o = L._vclock_hand_seconds(res)
            n = L._vclock_hand_seconds_v2(dict(res, timing_log=tl))
            old_s.append(o); new_s.append(n)
            ph = SIM._phase(stage.get(h['hash']))
            by_phase.setdefault(ph, {'old': [], 'new': []})
            by_phase[ph]['old'].append(o); by_phase[ph]['new'].append(n)
            for t in tl:
                key = (tseed, t['pid'])
                if key not in seen_pid:
                    seen_pid[key] = SIM.kind(TM.timing_traits(t['pid'], tseed))
                dec.append(dict(t, kind=seen_pid[key], phase=ph, tseed=tseed))
    hph = lambda a: round(3600.0 / st.mean(a), 1) if a else None
    report = {
        'traces': paths, 'hands': len(new_s), 'decisions': len(dec),
        'hand_seconds_old': dist(old_s), 'hand_seconds_v2': dist(new_s),
        'hands_per_hour_old': hph(old_s), 'hands_per_hour_v2': hph(new_s),
        'by_phase': {k: {'hands': len(v['new']), 'hph_old': hph(v['old']), 'hph_v2': hph(v['new'])}
                     for k, v in sorted(by_phase.items())},
    }
    # K(실제 concept) 분포 — v1 검증은 U(0.3, 0.95)
    report['K'] = dist([d['K'] for d in dec])
    report['concepts_per_decision'] = dist([d['n_concepts'] for d in dec])
    # 타임아웃
    to = [d for d in dec if d['timed_out']]
    report['timeouts'] = {
        'n': len(to), 'per_1000_decisions': round(1000.0 * len(to) / max(1, len(dec)), 2),
        'bank_empty_before': sum(1 for d in to if d['bank_before'] <= 1e-9),
        'engine_act': {a: sum(1 for d in to if d.get('engine_act') == a)
                       for a in sorted({d.get('engine_act') for d in to}, key=str)},
        'by_kind': {k: sum(1 for d in to if d['kind'] == k) for k in sorted({d['kind'] for d in dec})},
        'by_phase': {k: sum(1 for d in to if d['phase'] == k) for k in sorted({d['phase'] for d in dec})},
    }
    # 타입별 생각 시간 · 뱅크
    kinds = {}
    for k in sorted({d['kind'] for d in dec}):
        ds = [d for d in dec if d['kind'] == k]
        hard = [d['visible'] for d in ds if d['c'] >= 0.7 and d['commit'] >= 0.5]
        obv = [d['visible'] for d in ds if d['c'] <= 0.1 and d['commit'] >= 0.5]
        n_hours = len(ds) / float(SIM.HOUR_DECISIONS)
        kinds[k] = {
            'decisions': len(ds),
            'visible': dist([d['visible'] for d in ds]),
            'hard_allin': dist(hard), 'obvious_allin': dist(obv),
            'bank_used_per_hour': round(sum(d['bank_used'] for d in ds) / max(1e-9, n_hours), 2),
            'timeouts_per_1000': round(1000.0 * sum(1 for d in ds if d['timed_out']) / max(1, len(ds)), 2),
        }
    report['by_kind'] = kinds
    # 뱅크 소진: 결정 시점 뱅크가 0 인 결정 비율
    report['decisions_with_empty_bank_pct'] = round(
        100.0 * sum(1 for d in dec if d['bank_before'] <= 1e-9) / max(1, len(dec)), 2)
    json.dump(report, open(out_path, 'w'), indent=1, ensure_ascii=False)
    print(json.dumps({k: report[k] for k in ('hands', 'decisions', 'hands_per_hour_old',
                                             'hands_per_hour_v2', 'K', 'timeouts')},
                     indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
