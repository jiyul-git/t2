# -*- coding: utf-8 -*-
"""STEP 2-A counterfactual — 719 조기 return 을 giveup 에 대해서만 우회했을 때.

생산 코드는 건드리지 않는다. plan.py 의 need_seen 블록을 그대로 복제해
아카이브에 기록된 need_raw / eq 에 적용하고 결정을 다시 낸다.

바꾸는 것은 딱 하나 — "giveup 도 편향 블록을 통과하는가".
need_seen 계산식 자체는 plan.py:727~737 과 동일하다.
bluff_2street / river_bluff 는 대상이 아니다.
"""
import sys, json, os, statistics as stt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persona as PS

ARCH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'hand_archive2_alt.jsonl')
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'live2_state.json')


def need_seen(profile, need, pot, tocall, street):
    """plan.py:727~737 과 동일. 식은 절대 바꾸지 않는다."""
    if not profile.get('concepts'):
        return need
    ns = need
    sz = tocall / max(1.0, float(pot) - tocall)
    ns *= max(0.55, 1.0 - 0.22 * max(0.0, PS.bias(profile, 'station')))
    _bf_w = min(1.0, sz / 0.9) * (1.0 if street == 'river' else 0.65)
    ns *= 1.0 + 0.30 * max(0.0, PS.bias(profile, 'bluff_fear')) * _bf_w
    ns *= max(0.60, 1.0 - 0.18 * max(0.0, PS.bias(profile, 'hero_call')) * _bf_w)
    return max(0.02, min(0.97, ns))


# ---------- 대상 스팟 수집 ----------
spots = []
for ln in open(ARCH):
    r = json.loads(ln)
    for it in r.get('intents', []):
        if it.get('plan') != 'giveup':
            continue
        for t in (it.get('trace') or []):
            if t.get('kind') != 'response':
                continue
            if t.get('act') == 'raise':
                continue          # 707 이 719 앞에서 처리 — 대상 아님
            spots.append(dict(
                hand=r['hand_no'], street=it['street'], seat=it['seat'],
                typ=it.get('type'), eq=t['eq'], need_raw=t['need_raw'],
                pot=t['pot'], tocall=t['tocall'], cur=t['act'],
                prof=r['profiles'].get(str(it['seat']), {})))

print('=' * 96)
print('1. giveup 저항 스팟 총 N = %d  (raise 이탈 1건 제외)' % len(spots))
cur = {}
for s in spots:
    cur[s['cur']] = cur.get(s['cur'], 0) + 1
print('2. 현재 코드 행동 :', dict(cur))

flip = 0
cf = {}
print()
print('%-4s %-6s %-4s %-13s %-8s %-9s %-9s %-6s %-7s %-7s %s'
      % ('h', 'street', 'st', 'type', 'eq', 'need_raw', 'need_seen',
         '비율', '현재', '반사실', ''))
for s in spots:
    ns = need_seen(s['prof'], s['need_raw'], s['pot'], s['tocall'], s['street'])
    hyp = 'call' if s['eq'] >= ns else 'fold'
    cf[hyp] = cf.get(hyp, 0) + 1
    mark = ' ★뒤집힘' if hyp != s['cur'] else ''
    if hyp != s['cur']:
        flip += 1
    print('%-4s %-6s %-4s %-13s %-8.3f %-9.3f %-9.3f %-6.3f %-7s %-7s%s'
          % (s['hand'], s['street'], s['seat'], s['typ'], s['eq'],
             s['need_raw'], ns, ns / s['need_raw'], s['cur'], hyp, mark))

print()
print('3. counterfactual 행동 :', dict(cf))
print('4. 뒤집힌 건수 : %d / %d  (%.1f%%)' % (flip, len(spots), 100.0*flip/len(spots)))

# ---------- 민감도: 같은 스팟에 필드 40명을 대입 ----------
# eq / need_raw / pot / tocall / street 를 고정하고 '누가 그 자리에 앉았는가'만
# 바꾼다. 시뮬레이션이 아니라 편향 블록 하나의 민감도 측정이다.
field = [v['prof'] for v in json.load(open(STATE))['field']['players'].values()
         if isinstance(v, dict) and v.get('prof', {}).get('concepts')]
print()
print('=' * 96)
print('민감도 — 같은 18개 스팟에 필드 %d명을 각각 대입 (eq/need_raw 고정)' % len(field))
tot = fl = 0
per_spot = []
for s in spots:
    n = 0
    for p in field:
        ns = need_seen(p, s['need_raw'], s['pot'], s['tocall'], s['street'])
        hyp = 'call' if s['eq'] >= ns else 'fold'
        base = 'call' if s['eq'] >= s['need_raw'] else 'fold'
        tot += 1
        if hyp != base:
            fl += 1; n += 1
    per_spot.append((s, n))
print('전체 조합 %d, 결정이 바뀌는 조합 %d (%.1f%%)' % (tot, fl, 100.0*fl/tot))
print()
print('%-4s %-6s %-8s %-9s %-9s %s' % ('h', 'street', 'eq', 'need_raw', '여유', '40명 중 바뀌는 인원'))
for s, n in sorted(per_spot, key=lambda x: -x[1]):
    print('%-4s %-6s %-8.3f %-9.3f %+-9.3f %d' % (
        s['hand'], s['street'], s['eq'], s['need_raw'],
        s['eq'] - s['need_raw'], n))
