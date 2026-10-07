#!/usr/bin/env python3
"""관찰 기반 필드(test3) — 통계 진행 보정용 실제 진행 데이터 수집.

실제 서비스의 오프스크린 경로(scheduled_runtime.advance, 시간 규칙 기본)로 봇 전용 예약 대회 하나를
끝까지 진행하면서 핸드마다 한 줄씩 기록한다. 봇 엔진·전략은 바꾸지 않는다(측정 래퍼만 씌운다).

  python3 tools/coarse_calib_collect.py <fmt> <seed_day> <out_dir>

출력
  <out_dir>/<fmt>_<day>_hands.jsonl  핸드별: 대회 시각, 테이블, 인원, 블라인드·앤티, 버튼,
                                     좌석별 pid·핸드 전후 스택, 팟, 결과 방식, 승자, 도달 스트리트,
                                     올인 여부, 가상 핸드 길이(초), 그 시점의 남은 인원·ITM·엔트리
  <out_dir>/<fmt>_<day>_players.json 선수별 성향 요약(개념 숙련 평균, 공격성, 루즈함, 갬블)
  <out_dir>/<fmt>_<day>_summary.json 대회 길이·CPU·최종 레벨·탈락 순서
"""
import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['T2_BOT_LOG'] = '0'
os.environ['T2_TELEMETRY'] = '0'
os.environ.pop('T2_TIMING_V1', None)          # 실제 게임 기본(시간 규칙 켬)

import fieldsim as FS                          # noqa: E402
import live2 as L                              # noqa: E402
import scheduled_runtime as SR                 # noqa: E402
import tournament_store as TS                  # noqa: E402

STEP = 300.0
_OUT = None
_orig_play = FS.Field._play_table
_orig_apply = L.apply_vclock_events
# 선계산했다가 탈락 무효화로 버려진 핸드는 실제 대회에 없다. 계산한 핸드는 (테이블, 끝 시각)으로
# 잡아 두고, apply_vclock_events 가 실제로 확정한 이벤트만 기록한다.
_PENDING = {}


def _key(tid, end):
    return (int(tid), round(float(end), 3))


def _apply_and_record(st, events_by_table, cursors, target_seconds, **kw):
    out = _orig_apply(st, events_by_table, cursors, target_seconds, **kw)
    if _OUT is not None:
        cutoff = float(target_seconds)
        for tid, arr in (events_by_table or {}).items():
            for e in arr:
                if float(e['end']) <= cutoff + 1e-9:
                    rec = _PENDING.pop(_key(tid, e['end']), None)
                    if rec is not None:
                        _OUT.write(json.dumps(rec, separators=(',', ':')) + '\n')
    return out


def _streets(res):
    return sorted({a[0] for a in (res.get('full_log') or [])
                   if isinstance(a, (list, tuple)) and len(a) >= 3})


def _play_and_record(self, tb, fast=True, seed=None, return_result=False):
    alive = tb.ordered_alive()
    before = {str(p['pid']): int(p['stack']) for p in alive}
    seats = {str(p['pid']): tb.seat_of(p['pid']) for p in alive}
    clock = float(getattr(self, 'virtual_play_seconds', 0.0) or 0.0)
    self.advance_level()
    sb, bb = self.blinds()
    level = self.level
    frozen = getattr(self, '_frozen_field', None) or self.field_snapshot()
    layout = tb.hand_layout() if len(alive) >= 2 else {}
    button = layout.get('button')
    pos = {str(k): v for k, v in (layout.get('pos') or {}).items()}
    res = _orig_play(self, tb, fast=fast, seed=seed, return_result=True)
    if _OUT is not None and isinstance(res, dict):
        log = res.get('full_log') or []
        secs = float(L._vclock_hand_seconds(res))
        rec = {
            'clock': round(clock, 3), 'table': tb.id, 'n': len(alive), 'level': level,
            'sb': sb, 'bb': bb, 'ante': bb if level >= self.fmt['ante_from'] else 0,
            'button': button, 'pos': pos, 'seats': seats, 'before': before,
            'after': {pid: int(next(p['stack'] for p in alive if str(p['pid']) == pid))
                      for pid in before},
            'pot': res.get('pot'), 'how': res.get('how'), 'winners': res.get('winners'),
            'showdown': bool(res.get('showdown')), 'streets': _streets(res),
            'allin': any(isinstance(a, (list, tuple)) and len(a) >= 3 and a[2] == 'allin'
                         for a in log),
            'seconds': round(secs, 3),
            'remaining': frozen.get('remaining'), 'avg_stack': frozen.get('avg_stack'),
            'itm': self.itm, 'entries': self.entries,
        }
        _PENDING[_key(tb.id, clock + secs)] = rec
    if return_result:
        return res
    return True if res is not None else None


def _player_row(p):
    prof = p.get('prof') or {}
    conc = prof.get('concepts') or {}
    temp = prof.get('temper') or prof.get('t') or {}
    return {'skill': round(sum(conc.values()) / max(1, len(conc)), 3) if conc else None,
            'aggression': temp.get('aggression'), 'looseness': temp.get('looseness'),
            'gamble': temp.get('gamble')}


def main():
    global _OUT
    fmt, day, out_dir = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)
    FS.Field._play_table = _play_and_record
    L.apply_vclock_events = _apply_and_record
    spec = next(s for s in TS.LEGACY_SCHEDULE if s['fmt'] == fmt)
    store = TS.Store(tempfile.mkdtemp(), 10000, [dict(spec, minute=0)])
    base = 1790000000 - 1790000000 % 3600 + day * 86400
    store.ensure_schedule(base - 60)
    ev = store.event('%s:%d' % (fmt, base))
    late_active = TS.active_seconds(spec['late_minutes'] * 60)
    stem = os.path.join(out_dir, '%s_%d' % (fmt, day))
    cpu0, wall0, target = time.process_time(), time.time(), 0.0
    # 이어하기: 컨테이너가 재시작되면 긴 대회(딥 ~3.5시간)가 처음부터 다시 돈다. 단계마다 대회 상태와
    # 핸드 기록 위치를 저장하고, 있으면 거기서 잇는다. 선계산 캐시는 메모리에만 있어 다시 계산되지만
    # 시드가 같아 같은 핸드가 나온다(아직 확정 안 된 기록은 버리고 확정될 때 다시 쓴다).
    ckpt = stem + '_ckpt.json'
    mode, offset = 'w', 0
    if os.path.exists(ckpt) and os.path.exists(stem + '_hands.jsonl'):
        c = json.load(open(ckpt))
        ev['state'], ev['closed'], target = c['state'], c['closed'], float(c['target'])
        mode, offset = 'r+', int(c['offset'])
        cpu0 -= float(c.get('cpu', 0.0))
        wall0 -= float(c.get('wall', 0.0))
    with open(stem + '_hands.jsonl', mode) as fp:
        if mode == 'r+':
            fp.seek(offset)
            fp.truncate()
        _OUT = fp
        _PENDING.clear()
        while True:
            target += STEP
            ev['closed'] = target >= late_active
            r = SR.advance(ev, target, budget=10 ** 9, parallel=False)
            ev['state'] = r['state']
            f = L._load_field(ev['state']['field'])
            if f.remaining() <= 1 or target > 30 * 3600:
                break
            fp.flush()
            tmp = ckpt + '.tmp'
            json.dump({'state': ev['state'], 'closed': ev['closed'], 'target': target,
                       'offset': fp.tell(), 'cpu': time.process_time() - cpu0,
                       'wall': time.time() - wall0}, open(tmp, 'w'))
            os.replace(tmp, ckpt)
    _OUT = None
    if os.path.exists(ckpt):
        os.remove(ckpt)
    f = L._load_field(ev['state']['field'])
    json.dump({str(pid): _player_row(p) for pid, p in f.players.items()},
              open(stem + '_players.json', 'w'))
    cyc, ph = divmod(target, 3300.0)
    json.dump({'fmt': fmt, 'day': day, 'seed': ev['rules']['seed'], 'entries': f.entries,
               'active_end': target, 'elapsed_end': cyc * 3600 + ph,
               'cpu': round(time.process_time() - cpu0, 1), 'wall': round(time.time() - wall0, 1),
               'busted_order': [int(x) for x in getattr(f, 'busted_order', [])]},
              open(stem + '_summary.json', 'w'))
    print('DONE', fmt, day, round(time.process_time() - cpu0, 1))


if __name__ == '__main__':
    main()
