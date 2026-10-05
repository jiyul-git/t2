#!/usr/bin/env python3
"""타임뱅크 브레이크 충전(사용자 결정 2026-10-05) 검증.

  - 시작 60초(레이트 레지 동일), 브레이크(55분 플레이 → 5분 브레이크 진입)마다 +15초, 60초 초과 저장 안 함
  - 레벨/핸드별 충전 없음(같은 플레이 창 안에서는 그대로)
  - 봇 테이블 worker 와 본 필드가 같은 사람의 뱅크를 따로 써도 브레이크가 두 번 반영되지 않음
  - 실제 핸드 흐름(fieldsim, 시간 규칙 enforce, 기본 1초 테스트 덮어쓰기)에서 브레이크 뒤 첫 결정의
    뱅크가 직전 결정 뒤 뱅크 + 15(상한 60)와 같음
  - 딜 기계 시간 7.5초(timing.DEAL_SECONDS)가 봇 테이블 mechanical 과 사람 테이블 딜에 같이 쓰임
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['T2_TIMING_V1'] = 'enforce'
os.environ['T2_TIMING_TEST_BASE'] = '1'
os.environ['T2_BOT_LOG'] = '0'
import timing as TM
import fieldsim as FS


def main():
    checks = {}
    W = TM.PLAY_SECONDS
    b = {}
    seq = [TM.bank_get(b, 1, 10)]
    TM.bank_put(b, 1, 10.0, 10)
    seq += [TM.bank_get(b, 1, W - 1), TM.bank_get(b, 1, W), TM.bank_get(b, 1, 2 * W), TM.bank_get(b, 1, 9 * W)]
    checks['rule'] = {'pass': seq == [60.0, 10.0, 25.0, 40.0, 60.0], 'seq': seq}
    # 같은 창 안에서는 충전 없음(레벨·핸드 경계 무관)
    TM.bank_put(b, 2, 30.0, W + 5)
    checks['no_level_or_hand_recharge'] = {'pass': TM.bank_get(b, 2, 2 * W - 1) == 30.0}
    # worker 사본과 본 필드가 각각 쓰고 합쳐도 한 번만 반영
    main_b = {}
    TM.bank_put(main_b, 7, 20.0, W - 10)
    worker = dict(main_b)
    TM.bank_put(worker, 7, TM.bank_get(worker, 7, W + 30) - 5.0, W + 30)   # 브레이크 뒤 5초 사용
    main_b.update(worker)                                                  # 이벤트 확정
    after = TM.bank_get(main_b, 7, W + 200)
    checks['no_double_credit'] = {'pass': abs(after - 30.0) < 1e-9, 'bank': after}
    checks['legacy_float_no_retro'] = {'pass': TM.bank_get({3: 12.0}, 3, 5 * W) == 12.0}
    checks['deal_mechanical'] = {'pass': TM.DEAL_SECONDS == 7.5 and TM.mechanical_seconds(1, False) == 7.5,
                                 'deal': TM.DEAL_SECONDS}

    # 실제 핸드 흐름: 필드 시계를 브레이크 너머로 넘긴다
    f = FS.Field(entries=18, start_stack=30000, hero_pid=-1, seed=20261005, hands_per_level=12)
    f.virtual_play_seconds = 0.0
    f.level_minutes = 10
    last_left = {}
    jumps, bad, over_max = 0, [], 0
    clock = 0.0
    for rnd in range(60):
        clock = (rnd + 1) * (W / 20.0)            # 창 하나에 20라운드 → 브레이크 2번 넘김
        f.virtual_play_seconds = clock
        f.advance_level()
        for tid, tb in list(f.tables.items()):
            if tb.n() < 2:
                continue
            res = f._play_table(tb, return_result=True)
            for t in (res or {}).get('timing_log') or []:
                pid = t['pid']
                if t['bank_before'] > TM.BANK_MAX + 1e-9:
                    over_max += 1
                if pid in last_left:
                    prev_left, prev_due = last_left[pid]
                    due = TM.breaks_due(clock)
                    want = min(TM.BANK_MAX, prev_left + TM.BANK_RECHARGE * (due - prev_due)) if due > prev_due else prev_left
                    if abs(t['bank_before'] - want) > 1e-3:
                        bad.append((pid, t['bank_before'], want))
                    if due > prev_due and t['bank_before'] > prev_left + 1e-9:
                        jumps += 1
                last_left[pid] = (t['bank_before'] - t['bank_used'], TM.breaks_due(clock))
        f._collect_busts()
        f._balance(notify=False)
    checks['hand_flow_recharge'] = {'pass': not bad and jumps > 0 and over_max == 0,
                                    'recharged_decisions': jumps, 'mismatch': bad[:5], 'over_max': over_max}
    passed = all(c['pass'] for c in checks.values())
    print(json.dumps({'pass': passed, 'checks': checks}, indent=1, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
