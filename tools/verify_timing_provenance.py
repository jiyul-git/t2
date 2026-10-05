#!/usr/bin/env python3
"""T2 검증: 엔진이 직접 남긴 시간 모델용 결정 경계가 외부 hook 계측과 결정마다 같은가.

  프리플랍: preflop_plan seed 의 pf_timing  ==  timing_trace 의 pf_bound(hook 재계산)
  포스트플랍 응답: plan_state['_last_response_boundary']  ==  decide_response hook 의 eq/need

  python tools/verify_timing_provenance.py [SEED] [CAP] [ENTRIES]
"""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def close(a, b):
    # hook 기록은 반올림돼 있다(dr_* 4자리, multiway audit 6자리). 엔진 값은 원값.
    return a is not None and b is not None and abs(float(a) - float(b)) <= 5.1e-5


def main():
    seed = sys.argv[1] if len(sys.argv) > 1 else '11'
    cap = sys.argv[2] if len(sys.argv) > 2 else '40'
    n = sys.argv[3] if len(sys.argv) > 3 else '90'
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 't.json')
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'timing_trace.py'),
                        seed, 'real', out, cap, n], check=True, stdout=subprocess.DEVNULL,
                       env=dict(os.environ, T2_STRICT='1'))
        tr = json.load(open(out))
    pf_bad, pf_n, layer_n = [], 0, 0
    for p in tr['pf']:
        pb = p['pf_bound']
        eng = pb.get('engine') or {}
        pf_n += 1
        if pb.get('calloff_layer'):
            layer_n += 1
            ok = (eng.get('kind') == 'calloff_layer'
                  and close(eng.get('eq'), pb['calloff_layer']['eq'])
                  and close(eng.get('need'), pb['calloff_layer']['need']))
        else:
            b = pb['bounds'][-1]
            ok = close(eng.get('r'), b['r'])
            # multiway 증거 완비면 eq/need 가 경계(tot 는 hook 이 참고로만 남김).
            keys = (('eq', 'need') if b.get('eq') is not None else ('thr', 'tot', 'cap'))
            for k in keys:
                if b.get(k) is not None:
                    ok = ok and close(eng.get(k), b[k])
        if not ok:
            pf_bad.append({'hand': p.get('hash'), 'engine': eng, 'hook': pb})
    post_bad, post_n = [], 0
    for h in tr['hands']:
        for i in h['intents']:
            if i.get('dr_eq_used') is None:
                continue
            post_n += 1
            e = i.get('engine_boundary') or {}
            if not (close(e.get('eq'), i['dr_eq_used']) and close(e.get('need'), i['dr_need_used'])):
                post_bad.append({'hand': h['hash'], 'engine': e,
                                 'hook': [i['dr_eq_used'], i['dr_need_used']]})
    res = {'preflop_decisions': pf_n, 'calloff_layer': layer_n, 'preflop_mismatch': len(pf_bad),
           'postflop_responses': post_n, 'postflop_mismatch': len(post_bad),
           'examples': (pf_bad + post_bad)[:5]}
    res['pass'] = not pf_bad and not post_bad and pf_n > 0 and post_n > 0
    print(json.dumps(res, indent=1, default=str))
    raise SystemExit(0 if res['pass'] else 1)


if __name__ == '__main__':
    main()
