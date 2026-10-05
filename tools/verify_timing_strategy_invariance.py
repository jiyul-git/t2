#!/usr/bin/env python3
"""T3 검증: 시간 규칙은 엔진 결정을 바꾸지 않는다(타임아웃 적용 전 기준).

  1. off vs record — R2 기준(시드 11·12, 60라운드) 다이제스트 동일.
  2. off vs record — realistic 필드 짧은 완주 trace 다이제스트 동일.
  3. enforce — 타임아웃만 행동을 바꾼다:
       타임아웃 행동 = 체크 가능하면 체크, 아니면 폴드; 뱅크 음수 없음;
       첫 타임아웃이 난 핸드 전까지 record 와 핸드 기록이 완전히 같다.

  python tools/verify_timing_strategy_invariance.py [CAP]
"""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def start(args, mode, **extra):
    env = dict(os.environ, T2_TIMING_V1=mode, T2_STRICT='1', **extra)
    return subprocess.Popen([sys.executable] + args, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, env=env)


def finish(p):
    out, _ = p.communicate()
    if p.returncode != 0:
        raise SystemExit('subprocess failed rc=%s' % p.returncode)
    return json.loads(out.strip().splitlines()[-1])


def strip(h):
    h = json.loads(json.dumps(h))
    h.pop('timing', None)
    return json.dumps(h, sort_keys=True)


def main():
    cap = sys.argv[1] if len(sys.argv) > 1 else '40'
    res = {}
    r2 = os.path.join(ROOT, 'tools', 'r2_baseline_sim.py')
    tt = os.path.join(ROOT, 'tools', 'timing_trace.py')
    with tempfile.TemporaryDirectory() as d:
        # 전부 병렬로 띄운다(각자 별도 프로세스, 결과만 비교).
        jobs = {('r2', seed, mode): start([r2, seed, '60'], mode)
                for seed in ('11', '12') for mode in ('off', 'record')}
        # 테스트 전용 덮어쓰기는 시간 규칙이 꺼져 있으면 아무 영향이 없어야 한다.
        jobs[('r2', '11', 'off_testbase')] = start([r2, '11', '60'], 'off', T2_TIMING_TEST_BASE='3')
        files = {mode: os.path.join(d, mode + '.json') for mode in ('off', 'record', 'enforce')}
        for mode in ('off', 'record', 'enforce'):
            jobs[('tt', mode)] = start([tt, '13', 'real', files[mode], cap, '90'], mode)
        # 타임아웃 경로를 실제로 태우는 검증: 기본 시간 3초(테스트 전용 덮어쓰기)
        files['rec3'] = os.path.join(d, 'rec3.json'); files['enf3'] = os.path.join(d, 'enf3.json')
        jobs[('tt', 'rec3')] = start([tt, '13', 'real', files['rec3'], cap, '90'], 'record',
                                     T2_TIMING_TEST_BASE='3')
        jobs[('tt', 'enf3')] = start([tt, '13', 'real', files['enf3'], cap, '90'], 'enforce',
                                     T2_TIMING_TEST_BASE='3')
        out = {k: finish(p) for k, p in jobs.items()}
        for seed in ('11', '12'):
            res['r2_%s_off_eq_record' % seed] = (out[('r2', seed, 'off')]['sha256']
                                                 == out[('r2', seed, 'record')]['sha256'])
        res['testbase_env_off_eq_off'] = (out[('r2', '11', 'off_testbase')]['sha256']
                                          == out[('r2', '11', 'off')]['sha256'])
        res['real_off_eq_record'] = out[('tt', 'off')]['sha256'] == out[('tt', 'record')]['sha256']
        rec = json.load(open(files['record']))['hands']
        enf = json.load(open(files['enforce']))['hands']
        rec3 = json.load(open(files['rec3']))['hands']
        enf3 = json.load(open(files['enf3']))['hands']
        res['base3_off_eq_record_digest'] = None
    n_dec = n_to = 0
    bank_neg = bad_rule = 0
    first_to = None
    for k, h in enumerate(enf):
        for t in h.get('timing') or []:
            n_dec += 1
            if t['bank_before'] - t['bank_used'] < -1e-9:
                bank_neg += 1
            if t['timed_out']:
                n_to += 1
                if first_to is None:
                    first_to = k
    for k, h in enumerate(enf):
        for t in h.get('timing') or []:
            if t['timed_out'] and t.get('engine_act') is None:
                bad_rule += 1
    limit = first_to if first_to is not None else min(len(rec), len(enf))
    prefix_ok = all(strip(rec[i]) == strip(enf[i]) for i in range(min(limit, len(rec), len(enf))))
    res.update({'enforce_decisions': n_dec, 'enforce_timeouts': n_to, 'bank_negative': bank_neg,
                'timeout_without_engine_act': bad_rule, 'first_timeout_hand_index': first_to,
                'prefix_identical_until_first_timeout': prefix_ok})
    # 기본 3초 강제: 타임아웃 규칙 검사
    n3 = to3 = rule_bad3 = 0
    first3 = None
    for k, h in enumerate(enf3):
        for t in h.get('timing') or []:
            n3 += 1
            if t['timed_out']:
                to3 += 1
                first3 = k if first3 is None else first3
                want = 'check' if t.get('can_check') else 'fold'
                if t.get('exec_act') != want or t.get('engine_act') is None:
                    rule_bad3 += 1
    # 첫 타임아웃 핸드: 타임아웃 결정까지 결정별 RNG 지문·좌석·뱅크가 같은가
    dec_ok = None
    if first3 is not None and first3 < len(rec3):
        a = enf3[first3].get('timing') or []
        b = rec3[first3].get('timing') or []
        dec_ok = rec3[first3]['hash'] == enf3[first3]['hash']
        for x, y in zip(a, b):
            dec_ok = dec_ok and (x.get('rng_fp') is not None and x.get('rng_fp') == y.get('rng_fp')
                                 and x['seat'] == y['seat'] and x['street'] == y['street']
                                 and abs(x['bank_before'] - y['bank_before']) < 1e-9)
            if x['timed_out']:
                break
    res['base3_first_timeout_hand_decisions_identical_until_timeout'] = dec_ok
    lim3 = first3 if first3 is not None else min(len(rec3), len(enf3))
    prefix3 = all(strip(rec3[i]) == strip(enf3[i]) for i in range(min(lim3, len(rec3), len(enf3))))
    res.update({'base3_decisions': n3, 'base3_timeouts': to3, 'base3_rule_violations': rule_bad3,
                'base3_first_timeout_hand_index': first3,
                'base3_prefix_identical_until_first_timeout': prefix3})
    res.pop('base3_off_eq_record_digest', None)
    res['pass'] = (to3 > 0 and rule_bad3 == 0 and prefix3 and bool(dec_ok)
                   and res['testbase_env_off_eq_off'] and res['r2_11_off_eq_record'] and res['r2_12_off_eq_record'] and res['real_off_eq_record']
                   and bank_neg == 0 and bad_rule == 0 and prefix_ok and n_dec > 0)
    print(json.dumps(res, indent=1))
    raise SystemExit(0 if res['pass'] else 1)


if __name__ == '__main__':
    main()
