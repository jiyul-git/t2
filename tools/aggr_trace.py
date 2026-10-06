#!/usr/bin/env python3
"""공격성 추적 — 모집단 봇의 포스트플랍 소극성이 판단·계획·실행 중 어디서, 어떤 숙련·성향에서 생기는가.

  python3 tools/aggr_trace.py run <fmt> <seed_day> <out_prefix> [max_active_seconds]
  python3 tools/aggr_trace.py report <out_prefix> [<out_prefix> ...]

run: 실제 서비스 오프스크린 경로(scheduled_runtime.advance, 시간 규칙 기본)로 봇 전용 예약 대회를 진행하며
상세 봇 로그(T2_BOT_LOG=2: 홀카드, 보드, 액션 로그, 결정별 intent — 계획·핸드 상대강도·에퀴티)를 모은다.
측정 래퍼만 씌우고 엔진은 바꾸지 않는다.

report: 포스트플랍 결정마다 (계획, 상대강도 rel, 실제 액션, 그 봇의 숙련·성향)을 묶어
  1) 계획 분포와 계획별 실제 공격 비율(계획 → 실행 손실)
  2) 상대강도 구간별 공격 비율(판단: 강한 핸드인데 체크하는가)
  3) 공격성·관련 숙련 구간별 공격 비율(성향·숙련이 공격으로 이어지는가)
"""
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

AGGR = ('bet', 'raise', 'allin')


def run(fmt, day, prefix, limit):
    os.environ['T2_BOT_LOG'] = '2'
    os.environ['T2_TELEMETRY'] = '0'
    os.environ.pop('T2_TIMING_V1', None)
    import live2 as L
    import scheduled_runtime as SR
    import tournament_store as TS
    recs = []
    orig = L._vclock_table_task

    def wrap(*a, **k):
        out = orig(*a, **k)
        for e in out.get('events') or []:
            for line in (e.get('bot_log') or '').splitlines():
                if line.strip():
                    recs.append(line)
        return out
    L._vclock_table_task = wrap
    spec = next(s for s in TS.LEGACY_SCHEDULE if s['fmt'] == fmt)
    store = TS.Store(tempfile.mkdtemp(), 10000, [dict(spec, minute=0)])
    base = 1790000000 - 1790000000 % 3600 + day * 86400
    store.ensure_schedule(base - 60)
    ev = store.event('%s:%d' % (fmt, base))
    late = TS.active_seconds(spec['late_minutes'] * 60)
    t = 0.0
    while True:
        t += 300
        ev['closed'] = t >= late
        r = SR.advance(ev, t, budget=10 ** 9, parallel=False)
        ev['state'] = r['state']
        f = L._load_field(ev['state']['field'])
        if f.remaining() <= 1 or t >= limit:
            break
    with open(prefix + '_hands.jsonl', 'w') as fp:
        fp.write('\n'.join(recs) + '\n')
    players = {}
    for pid, p in f.players.items():
        prof = p.get('prof') or {}
        players[str(pid)] = {'concepts': prof.get('concepts') or {}, 'temper': prof.get('temper') or {}}
    json.dump(players, open(prefix + '_players.json', 'w'))
    print('hands', len(recs))


def _band(x, cuts):
    for c in cuts:
        if x < c:
            return '<%g' % c
    return '>=%g' % cuts[-1]


def report(prefixes):
    plan_n, plan_aggr = Counter(), Counter()
    rel_n, rel_aggr = Counter(), Counter()
    aggr_n, aggr_aggr = Counter(), Counter()
    skill_n, skill_aggr = Counter(), Counter()
    first_n, first_aggr = Counter(), Counter()
    for prefix in prefixes:
        players = json.load(open(prefix + '_players.json'))
        for line in open(prefix + '_hands.jsonl'):
            if not line.strip():
                continue
            h = json.loads(line)
            pids = h.get('pids') or {}
            log = h.get('full_log') or []
            # 같은 스트리트·좌석의 k번째 액션과 intent 를 맞춘다
            acts = defaultdict(list)
            for a in log:
                if a[0] != 'preflop':
                    acts[(a[0], str(a[1]))].append(a)
            for it in h.get('intents') or []:
                st, seat, idx = it.get('street'), str(it.get('seat')), it.get('idx', 0)
                lst = acts.get((st, seat)) or []
                if idx >= len(lst):
                    continue
                act = lst[idx][2]
                prior = [a for a in log if a[0] == st]
                prior = prior[:prior.index(lst[idx])]
                facing = any(a[2] in AGGR for a in prior)
                if facing:
                    continue                      # 공격 기회(체크된 상태에서 첫 공격)만 본다
                is_aggr = act in AGGR
                plan = it.get('plan') or 'none'
                plan_n[plan] += 1
                plan_aggr[plan] += is_aggr
                rel = it.get('rel')
                if rel is not None:
                    b = _band(float(rel), (0.3, 0.5, 0.7, 0.85))
                    rel_n[(st, b)] += 1
                    rel_aggr[(st, b)] += is_aggr
                prof = players.get(str(pids.get(seat))) or {}
                t = prof.get('temper') or {}
                c = prof.get('concepts') or {}
                if t:
                    b = _band(t.get('aggression', 5), (3, 5, 7))
                    aggr_n[b] += 1
                    aggr_aggr[b] += is_aggr
                key = {'flop': 'cbet_flop', 'turn': 'barrel_turn', 'river': 'thin_value_river'}.get(st)
                if c and key in c:
                    b = _band(c[key], (3, 5, 7))
                    skill_n[(st, key, b)] += 1
                    skill_aggr[(st, key, b)] += is_aggr
                first_n[st] += 1
                first_aggr[st] += is_aggr

    def table(n, k):
        return {str(x): {'n': n[x], 'aggr': round(k[x] / n[x], 3)} for x in sorted(n, key=str)}
    out = {'first_to_act_aggr_by_street': table(first_n, first_aggr),
           'by_plan': table(plan_n, plan_aggr),
           'by_rel': table(rel_n, rel_aggr),
           'by_aggression_temper': table(aggr_n, aggr_aggr),
           'by_street_skill': table(skill_n, skill_aggr)}
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(sys.argv[2], int(sys.argv[3]), sys.argv[4], float(sys.argv[5]) if len(sys.argv) > 5 else 30 * 3600)
    else:
        report(sys.argv[2:])
