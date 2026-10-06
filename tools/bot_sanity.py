#!/usr/bin/env python3
"""봇 행동 점검 — 관찰되지 않는 봇 테이블(실제 진행)이 정상적으로 치는가. 읽기 전용(측정 래퍼만).

  python3 tools/bot_sanity.py <fmt> <seed_day> <out_json> [max_active_seconds]

실제 서비스 오프스크린 경로(scheduled_runtime.advance, 시간 규칙 기본)로 봇 전용 예약 대회를 진행하며
계산된 모든 봇 핸드의 액션 로그로 통계를 낸다.

지표
  핸드: 플랍 본 인원, 쇼다운 비율, 워크(전원 폴드 → BB), 평균 팟(bb), 프리플랍 올인 비율, 핸드 길이(가상 초)
  좌석: VPIP, PFR, 3벳(기회 대비), 림프(블라인드 제외), 스틸(CO·BTN·SB, 폴드로 넘어온 기회 대비),
        스틸에 BB 폴드, 플랍 본 뒤 쇼다운까지 간 비율(WTSD)
  단계별(초반·중반·버블·ITM)과 스택 깊이별(<10, 10~25, 25~50, 50+ bb)
  선수별 VPIP·PFR 분포와 성향(looseness·aggression)과의 순위상관
  결정 타임아웃 비율, 엔진 오류
"""
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['T2_BOT_LOG'] = '0'
os.environ['T2_TELEMETRY'] = '0'
os.environ.pop('T2_TIMING_V1', None)

import fieldsim as FS                  # noqa: E402
import live2 as L                      # noqa: E402
import scheduled_runtime as SR         # noqa: E402
import tournament_store as TS          # noqa: E402

VOL = ('call', 'raise', 'bet', 'allin')
STEAL_POS = ('CO', 'BTN', 'SB')
_orig = FS.Field._play_table
HANDS = []


def _stage(rem, itm):
    if rem is None or itm is None:
        return 'unknown'
    if rem <= itm:
        return 'itm'
    if rem <= itm * 1.25:
        return 'bubble'
    return 'early' if rem > itm * 3 else 'mid'


def _wrap(self, tb, fast=True, seed=None, return_result=False):
    alive = tb.ordered_alive()
    layout = tb.hand_layout() if len(alive) >= 2 else {}
    self.advance_level()
    sb, bb = self.blinds()
    frozen = getattr(self, '_frozen_field', None) or self.field_snapshot()
    stacks = {tb.seat_of(p['pid']): p['stack'] for p in alive}
    pids = {tb.seat_of(p['pid']): p['pid'] for p in alive}
    res = _orig(self, tb, fast=fast, seed=seed, return_result=True)
    if isinstance(res, dict):
        HANDS.append({'pos': dict(layout.get('pos') or {}), 'bb': bb, 'stacks': stacks, 'pids': pids,
                      'log': [tuple(a) for a in res.get('full_log') or []], 'pot': res.get('pot'),
                      'showdown': bool(res.get('showdown')), 'winners': res.get('winners'),
                      'seconds': L._vclock_hand_seconds(res),
                      'timeouts': sum(1 for t in res.get('timing_log') or [] if t.get('timed_out')),
                      'decisions': len(res.get('timing_log') or []),
                      'stage': _stage(frozen.get('remaining'), getattr(self, 'itm', None))})
    if return_result:
        return res
    return True if res is not None else None


def _depth(bbs):
    return '<10' if bbs < 10 else '10-25' if bbs < 25 else '25-50' if bbs < 50 else '50+'


def analyse(hands):
    seat = defaultdict(Counter)          # 그룹 → 카운터
    hand = defaultdict(Counter)
    player = defaultdict(Counter)
    for h in hands:
        pos = h['pos']
        pre = [a for a in h['log'] if a[0] == 'preflop']
        groups_h = ('all', 'stage:' + h['stage'])
        raises = 0
        acted = set()
        steal_seat = None
        folded_pre = set()
        first_vol = {}
        for _st, s, act, _amt in pre:
            p = pos.get(s)
            depth = _depth(h['stacks'].get(s, 0) / max(1, h['bb']))
            groups = ('all', 'stage:' + h['stage'], 'depth:' + depth)
            if s not in acted:
                acted.add(s)
                for g in groups:
                    seat[g]['seat_hands'] += 1
                player[h['pids'].get(s)]['hands'] += 1
                if raises == 1:
                    for g in groups:
                        seat[g]['3bet_opp'] += 1
                if raises == 0 and p in STEAL_POS and all(a[2] == 'fold' for a in pre[:pre.index((_st, s, act, _amt))]):
                    for g in groups:
                        seat[g]['steal_opp'] += 1
                    if act in ('raise', 'allin'):
                        for g in groups:
                            seat[g]['steal'] += 1
                        steal_seat = s
                if act in VOL:
                    first_vol[s] = act
                    for g in groups:
                        seat[g]['vpip'] += 1
                    player[h['pids'].get(s)]['vpip'] += 1
                    if raises == 0 and act == 'call' and p not in ('BB',):
                        for g in groups:
                            seat[g]['limp'] += 1
                if act == 'allin':
                    for g in groups:
                        seat[g]['allin'] += 1
                if act in ('raise', 'allin'):
                    for g in groups:
                        seat[g]['pfr'] += 1
                    player[h['pids'].get(s)]['pfr'] += 1
                    if raises == 1:
                        for g in groups:
                            seat[g]['3bet'] += 1
                if steal_seat is not None and s != steal_seat and p == 'BB':
                    for g in groups:
                        seat[g]['bb_vs_steal'] += 1
                        seat[g]['bb_fold_vs_steal'] += act == 'fold'
            if act in ('raise', 'allin'):
                raises += 1
            if act == 'fold':
                folded_pre.add(s)
        seen = [s for s in pos if s not in folded_pre]
        saw_flop = any(a[0] == 'flop' for a in h['log'])
        walk = not saw_flop and len(seen) == 1 and pos.get(seen[0]) == 'BB' and raises == 0
        for g in groups_h:
            hand[g]['hands'] += 1
            hand[g]['flop_players'] += len(seen) if saw_flop else 0
            hand[g]['saw_flop'] += saw_flop
            hand[g]['showdown'] += h['showdown']
            hand[g]['walk'] += walk
            hand[g]['pot_bb'] += (h['pot'] or 0) / max(1, h['bb'])
            hand[g]['pre_allin'] += any(a[2] == 'allin' for a in pre)
            hand[g]['seconds'] += h['seconds']
            hand[g]['timeouts'] += h['timeouts']
            hand[g]['decisions'] += h['decisions']
            if saw_flop:
                hand[g]['flop_seat'] += len(seen)
                folded_any = {a[1] for a in h['log'] if a[2] == 'fold'}
                hand[g]['wtsd_seat'] += sum(1 for s in seen if s not in folded_any) if h['showdown'] else 0
    out = {'hands': {}, 'seats': {}}
    for g, c in sorted(hand.items()):
        n = max(1, c['hands'])
        out['hands'][g] = {'hands': c['hands'], 'saw_flop': round(c['saw_flop'] / n, 3),
                           'avg_flop_players': round(c['flop_players'] / max(1, c['saw_flop']), 2),
                           'showdown': round(c['showdown'] / n, 3), 'walk': round(c['walk'] / n, 3),
                           'avg_pot_bb': round(c['pot_bb'] / n, 1), 'pre_allin': round(c['pre_allin'] / n, 3),
                           'avg_seconds': round(c['seconds'] / n, 1),
                           'timeout_rate': round(c['timeouts'] / max(1, c['decisions']), 4),
                           'wtsd': round(c['wtsd_seat'] / max(1, c['flop_seat']), 3)}
    for g, c in sorted(seat.items()):
        n = max(1, c['seat_hands'])
        out['seats'][g] = {'seat_hands': c['seat_hands'], 'vpip': round(c['vpip'] / n, 3),
                           'pfr': round(c['pfr'] / n, 3), 'limp': round(c['limp'] / n, 3),
                           'first_action_allin': round(c['allin'] / n, 4),
                           '3bet': round(c['3bet'] / max(1, c['3bet_opp']), 3),
                           'steal': round(c['steal'] / max(1, c['steal_opp']), 3),
                           'bb_fold_vs_steal': round(c['bb_fold_vs_steal'] / max(1, c['bb_vs_steal']), 3)}
    return out, player


def spearman(xs, ys):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for k, i in enumerate(o):
            r[i] = k
        return r
    a, b = rank(xs), rank(ys)
    n = len(a)
    if n < 3:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a) ** .5
    vb = sum((y - mb) ** 2 for y in b) ** .5
    return round(cov / (va * vb), 3) if va and vb else None


def main():
    fmt, day, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    limit = float(sys.argv[4]) if len(sys.argv) > 4 else 30 * 3600
    FS.Field._play_table = _wrap
    spec = next(s for s in TS.LEGACY_SCHEDULE if s['fmt'] == fmt)
    store = TS.Store(tempfile.mkdtemp(), 10000, [dict(spec, minute=0)])
    base = 1790000000 - 1790000000 % 3600 + day * 86400
    store.ensure_schedule(base - 60)
    ev = store.event('%s:%d' % (fmt, base))
    late = TS.active_seconds(spec['late_minutes'] * 60)
    t, errors = 0.0, []
    while True:
        t += 300
        ev['closed'] = t >= late
        r = SR.advance(ev, t, budget=10 ** 9, parallel=False)
        ev['state'] = r['state']
        f = L._load_field(ev['state']['field'])
        errors += list(f.errors)
        if f.remaining() <= 1 or t >= limit:
            break
    stats, player = analyse(HANDS)
    profs = {p['pid']: (p.get('prof') or {}).get('temper') or {} for p in f.players.values()}
    rows = [(c['vpip'] / c['hands'], c['pfr'] / c['hands'], profs.get(pid, {}))
            for pid, c in player.items() if pid is not None and c['hands'] >= 30]
    stats['players'] = {
        'n': len(rows),
        'vpip_min_med_max': [round(x, 3) for x in (min(r[0] for r in rows), sorted(r[0] for r in rows)[len(rows) // 2],
                                                   max(r[0] for r in rows))] if rows else None,
        'pfr_min_med_max': [round(x, 3) for x in (min(r[1] for r in rows), sorted(r[1] for r in rows)[len(rows) // 2],
                                                  max(r[1] for r in rows))] if rows else None,
        'spearman_vpip_looseness': spearman([r[0] for r in rows], [r[2].get('looseness', 0) for r in rows]),
        'spearman_pfr_aggression': spearman([r[1] for r in rows], [r[2].get('aggression', 0) for r in rows]),
    }
    stats.update(fmt=fmt, day=day, active_seconds=t, computed_hands=len(HANDS), engine_errors=errors[:20],
                 engine_error_count=len(errors))
    json.dump(stats, open(out, 'w'), indent=1, ensure_ascii=False)
    a = stats['seats']['all']
    hh = stats['hands']['all']
    print(json.dumps({'fmt': fmt, 'hands': hh['hands'], 'vpip': a['vpip'], 'pfr': a['pfr'], '3bet': a['3bet'],
                      'limp': a['limp'], 'steal': a['steal'], 'bb_fold_vs_steal': a['bb_fold_vs_steal'],
                      'saw_flop': hh['saw_flop'], 'avg_flop_players': hh['avg_flop_players'],
                      'wtsd': hh['wtsd'], 'walk': hh['walk'], 'pre_allin': hh['pre_allin'],
                      'avg_pot_bb': hh['avg_pot_bb'], 'timeout_rate': hh['timeout_rate'],
                      'errors': len(errors), 'players': stats['players']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
