#!/usr/bin/env python3
"""관찰 기반 필드(test3) — 통계 진행(coarse)을 실제 진행과 비교한다(OBSERVED_FIELD_DESIGN §7).

  python3 tools/coarse_validate.py <fmt> <calib_dir> <lib_days> <test_days> <n_coarse> <out_prefix>
    lib_days / test_days : 쉼표 구분. 라이브러리를 만든 실제 대회와 비교 대상 실제 대회는 겹치지 않는다.

실제 대회는 수집 기록(핸드별 끝 시각의 스택)을 시간순으로 재생해 300초마다 필드 상태를 만들고,
통계 대회는 scheduled_runtime.advance(hybrid)로 진행하며 같은 시각마다 상태를 찍는다.

지표(각 시각): 남은 인원, 생존 스택 지니계수, 칩 리더 비중, 10bb 미만 비율. 대회 단위: 길이, ITM 도달 시각.
판정: 대회 단위 지표는 2표본 KS 검정 p>0.05, 시각별 지표는 통계 진행 중앙값이 실제 대회들의
최소~최대 범위 안에 든 시각 비율 ≥ 90%.
"""
import json
import math
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['T2_BOT_LOG'] = '0'
os.environ['T2_TELEMETRY'] = '0'
os.environ.pop('T2_TIMING_V1', None)

import coarse_sim as CS            # noqa: E402
import formats as FM               # noqa: E402
import live2 as L                  # noqa: E402
import scheduled_runtime as SR     # noqa: E402
import tournament_store as TS      # noqa: E402
from table import BLINDS           # noqa: E402

STEP = 300.0


def _bb_at(t, fmt):
    lv = min(1 + int(t // (60 * FM.level_minutes(fmt))), len(BLINDS))
    return BLINDS[lv - 1][2]


def _metrics(stacks, t, fmt):
    alive = sorted(v for v in stacks if v > 0)
    n = len(alive)
    if not n:
        return {'remaining': 0, 'gini': 0.0, 'leader': 1.0, 'short': 0.0}
    tot = float(sum(alive))
    g = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(alive)) / (n * tot) if n > 1 else 0.0
    bb = _bb_at(t, fmt)
    return {'remaining': n, 'gini': round(g, 4), 'leader': round(alive[-1] / tot, 4),
            'short': round(sum(1 for v in alive if v < 10 * bb) / n, 4)}


def real_timeline(calib, fmt, day):
    spec = next(s for s in TS.LEGACY_SCHEDULE if s['fmt'] == fmt)
    summ = json.load(open(os.path.join(calib, '%s_%d_summary.json' % (fmt, day))))
    players = json.load(open(os.path.join(calib, '%s_%d_players.json' % (fmt, day))))
    start = int(FM.get(fmt)['start_bb']) * int(BLINDS[0][2])
    stacks = {pid: start for pid in players}
    events = []
    with open(os.path.join(calib, '%s_%d_hands.jsonl' % (fmt, day))) as fp:
        for line in fp:
            r = json.loads(line)
            events.append((r['clock'] + r['seconds'], r['after']))
    events.sort(key=lambda e: e[0])
    rows, i, t = [], 0, 0.0
    itm = max(1, int(round(len(players) * FM.get(fmt)['itm_frac'])))
    end = summ['active_end']
    while t < end + STEP:
        t += STEP
        while i < len(events) and events[i][0] <= t:
            stacks.update(events[i][1])
            i += 1
        rows.append(dict(_metrics(list(stacks.values()), t, fmt), t=t))
        if rows[-1]['remaining'] <= 1:
            break
    last_bust = max((e[0] for e in events), default=end)
    itm_t = next((r['t'] for r in rows if r['remaining'] <= itm), None)
    return {'day': day, 'rows': rows, 'end': last_bust, 'itm_t': itm_t, 'spec': spec}


def coarse_timeline(fmt, day):
    os.environ['T2_FIELD_BACKEND'] = 'hybrid'
    spec = next(s for s in TS.LEGACY_SCHEDULE if s['fmt'] == fmt)
    store = TS.Store(tempfile.mkdtemp(), 10000, [dict(spec, minute=0)])
    base = 1790000000 - 1790000000 % 3600 + day * 86400
    store.ensure_schedule(base - 60)
    ev = store.event('%s:%d' % (fmt, base))
    assert ev['rules']['field_backend'] == 'hybrid'
    late = TS.active_seconds(spec['late_minutes'] * 60)
    itm = None
    rows, t, c0, total0, last_rem, end = [], 0.0, time.process_time(), None, None, None
    while True:
        t += STEP
        ev['closed'] = t >= late
        r = SR.advance(ev, t, budget=10 ** 9, parallel=False)
        ev['state'] = r['state']
        f = L._load_field(ev['state']['field'])
        itm = f.itm
        stacks = [p['stack'] for p in f.players.values()]
        tot = sum(stacks)
        total0 = total0 or tot
        if tot != total0:
            raise AssertionError('chip conservation broken: %s != %s' % (tot, total0))
        rows.append(dict(_metrics(stacks, t, fmt), t=t))
        if rows[-1]['remaining'] <= 1 or t > 30 * 3600:
            break
    end = float(ev['state']['field'].get('virtual_play_seconds') or t)
    itm_t = next((r['t'] for r in rows if r['remaining'] <= itm), None)
    return {'day': day, 'rows': rows, 'end': end, 'itm_t': itm_t,
            'cpu': round(time.process_time() - c0, 2), 'errors': list(f.errors)}


def ks(a, b):
    """2표본 KS 통계량과 점근 p값."""
    a, b = sorted(a), sorted(b)
    n, m = len(a), len(b)
    if not n or not m:
        return None, None
    d, i, j = 0.0, 0, 0
    for x in sorted(set(a + b)):
        while i < n and a[i] <= x:
            i += 1
        while j < m and b[j] <= x:
            j += 1
        d = max(d, abs(i / n - j / m))
    en = math.sqrt(n * m / (n + m))
    lam = (en + 0.12 + 0.11 / en) * d
    p = 2 * sum((-1) ** (k - 1) * math.exp(-2 * k * k * lam * lam) for k in range(1, 101))
    return round(d, 4), round(max(0.0, min(1.0, p)), 4)


def _median(xs):
    xs = sorted(xs)
    k = len(xs)
    return (xs[k // 2] if k % 2 else 0.5 * (xs[k // 2 - 1] + xs[k // 2])) if k else None


def compare(real, coarse):
    out = {'tournament': {}, 'checkpoints': {}}
    for key in ('end', 'itm_t'):
        a = [r[key] for r in real if r[key] is not None]
        b = [c[key] for c in coarse if c[key] is not None]
        d, p = ks(a, b)
        out['tournament'][key] = {'real_mean': round(sum(a) / len(a), 1) if a else None,
                                  'coarse_mean': round(sum(b) / len(b), 1) if b else None,
                                  'real_min': min(a) if a else None, 'real_max': max(a) if a else None,
                                  'ks_d': d, 'ks_p': p, 'pass': p is not None and p > 0.05}
    for metric in ('remaining', 'gini', 'leader', 'short'):
        inside, total, curve = 0, 0, []
        horizon = min(max(r['rows'][-1]['t'] for r in real), max(c['rows'][-1]['t'] for c in coarse))
        t = STEP
        while t <= horizon:
            rv = [next((x[metric] for x in r['rows'] if x['t'] == t), None) for r in real]
            cv = [next((x[metric] for x in c['rows'] if x['t'] == t), None) for c in coarse]
            rv = [v for v in rv if v is not None]
            cv = [v for v in cv if v is not None]
            if len(rv) >= 2 and cv:
                med = _median(cv)
                ok = min(rv) <= med <= max(rv)
                inside += ok
                total += 1
                curve.append({'t': t, 'real_min': min(rv), 'real_max': max(rv), 'real_med': _median(rv),
                              'coarse_med': med, 'coarse_min': min(cv), 'coarse_max': max(cv)})
            t += STEP
        frac = inside / total if total else None
        out['checkpoints'][metric] = {'inside_frac': round(frac, 3) if frac is not None else None,
                                      'pass': frac is not None and frac >= 0.9, 'curve': curve}
    out['pass'] = all(v['pass'] for v in out['tournament'].values()) and all(
        v['pass'] for v in out['checkpoints'].values())
    return out


def plot(fmt, cmp, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.2))
    names = {'remaining': '남은 인원', 'gini': '스택 지니', 'leader': '칩 리더 비중', 'short': '10bb 미만 비율'}
    for ax, metric in zip(axes, ('remaining', 'gini', 'leader', 'short')):
        c = cmp['checkpoints'][metric]['curve']
        if not c:
            continue
        ts = [x['t'] / 60 for x in c]
        ax.fill_between(ts, [x['real_min'] for x in c], [x['real_max'] for x in c], color='#9bb7d4', alpha=.5,
                        label='real min~max')
        ax.plot(ts, [x['real_med'] for x in c], color='#1f4e79', lw=1.6, label='real median')
        ax.plot(ts, [x['coarse_med'] for x in c], color='#d9480f', lw=1.6, ls='--', label='coarse median')
        ax.set_title('%s · %s (inside %.0f%%)' % (fmt, metric, 100 * (cmp['checkpoints'][metric]['inside_frac'] or 0)))
        ax.set_xlabel('active minutes')
        ax.grid(alpha=.3)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)


def main():
    fmt, calib, lib_days, test_days, n_coarse, prefix = sys.argv[1:7]
    lib_days = [int(x) for x in lib_days.split(',')]
    test_days = [int(x) for x in test_days.split(',')]
    lib = CS.build_library([os.path.join(calib, '%s_%d_hands.jsonl' % (fmt, d)) for d in lib_days])
    CS._LIB[fmt] = lib
    real = [real_timeline(calib, fmt, d) for d in test_days]
    coarse = [coarse_timeline(fmt, 1000 + k) for k in range(int(n_coarse))]
    cmp = compare(real, coarse)
    cmp.update(fmt=fmt, lib_days=lib_days, test_days=test_days, n_coarse=len(coarse),
               lib_hands=sum(len(v) for v in lib.values()),
               coarse_cpu_mean=round(sum(c['cpu'] for c in coarse) / len(coarse), 2),
               coarse_errors=sum(len(c['errors']) for c in coarse))
    json.dump(cmp, open(prefix + '.json', 'w'), indent=1)
    plot(fmt, cmp, prefix + '.png')
    print(json.dumps({'fmt': fmt, 'pass': cmp['pass'],
                      'tournament': {k: {kk: v[kk] for kk in ('real_mean', 'coarse_mean', 'ks_p', 'pass')}
                                     for k, v in cmp['tournament'].items()},
                      'checkpoints': {k: v['inside_frac'] for k, v in cmp['checkpoints'].items()},
                      'coarse_cpu_mean': cmp['coarse_cpu_mean'], 'coarse_errors': cmp['coarse_errors']},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
