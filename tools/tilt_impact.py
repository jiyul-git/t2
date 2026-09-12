#!/usr/bin/env python3
"""persona.tilted_view 캐시 오염의 영향 범위 측정. 코드는 수정하지 않는다.

    python3 tools/tilt_impact.py AB [핸드/토너]      # A·B 단계
    python3 tools/tilt_impact.py C  <on.jsonl> <off.jsonl>   # C 단계 비교
    python3 tools/tilt_impact.py RUN on|off <out> [핸드/토너]

세 단계
-------
A. 캐시가 **다른 프로필**을 돌려준 횟수
   "type 이 다른 경우"만 세면 하한이다. 같은 type 의 다른 사람으로 바뀐
   경우가 빠진다. 그래서 매 호출마다 캐시를 우회한 **그림자 계산**을 해서
   반환값 전체(concepts·temper·상위필드)를 비교한다.
   tilt_decay / tilt_direction / derive 는 난수를 쓰지 않으므로
   그림자 계산이 시뮬레이션의 rng 스트림을 건드리지 않는다(확인함).

B. 오염된 뷰가 실제 판단까지 갔는가
   tilted_view 호출부는 play.py:81 하나뿐이고 그것이 판단 층의 단일
   진입점이므로 **오염되면 그 판단은 전부 남의 개념 벡터로 내려간다**.
   여기서는 그 좌석이 그 핸드에서 실제로 intent 를 남겼는지까지 센다.

C. 캐시 ON/OFF 반사실
   캐시는 순수 메모가 아니다(같은 키에 다른 사람이 들어온다). 끄면
   '오염 없는' 실행이 된다. 같은 시드로 ON/OFF 를 돌려 어디서 갈라지는지
   본다. rng 소비는 양쪽이 같다 — 캐시는 난수를 쓰지 않는다.

캐시 구조 (persona.py:567~)
    _TILT_VIEW_CACHE 키 = (prof['id'], round(tilt,2))
    prof['id'] 는 **좌석 번호**다 (tourney:199 → F.make_player(rng, s, ...))
    4000개 초과 시 clear 하는데 키 공간이 8 × (tilt 2자리) ≈ 400 이라
    **실제로는 한 번도 비워지지 않는다**.
"""
import os, sys, json, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persona as PS


class NoCache(dict):
    """메모를 끈다. tilted_view 가 쓰는 인터페이스만 흉내낸다."""
    def get(self, k, d=None):
        return None

    def __setitem__(self, k, v):
        pass

    def __len__(self):
        return 0


def fingerprint(v):
    if not isinstance(v, dict):
        return None
    return json.dumps({'c': v.get('concepts'), 't': v.get('temper'),
                       'a': v.get('aggr'), 'b': v.get('bluff'),
                       'i': v.get('icm'), 'g': v.get('gamble')},
                      sort_keys=True, default=str)


def stage_ab(n_per):
    orig = PS.tilted_view
    stat = collections.Counter()
    diffs = []
    seat_tilt = collections.Counter()

    def wrapped(prof, tilt):
        got = orig(prof, tilt)
        t = max(0.0, min(1.0, float(tilt or 0.0)))
        if t <= 0.02 or not prof or not prof.get('concepts') \
                or prof.get('id') is None:
            stat['캐시 비관여'] += 1
            return got
        stat['캐시 관여 호출'] += 1
        save = PS._TILT_VIEW_CACHE
        PS._TILT_VIEW_CACHE = NoCache()
        try:
            fresh = orig(prof, tilt)
        finally:
            PS._TILT_VIEW_CACHE = save
        if fingerprint(got) != fingerprint(fresh):
            stat['**오염된 반환**'] += 1
            seat_tilt[(prof.get('id'), round(t, 2))] += 1
            same_type = (got.get('type') == prof.get('type'))
            stat['  그중 type 은 같음(기존 검출로는 안 잡힘)' if same_type
                 else '  그중 type 도 다름'] += 1
            if len(diffs) < 8:
                ca, cb = got.get('concepts') or {}, fresh.get('concepts') or {}
                mx = max(((abs(ca.get(k, 0) - cb.get(k, 0)), k)
                          for k in set(ca) | set(cb)), default=(0, None))
                diffs.append((prof.get('id'), round(t, 2), prof.get('type'),
                              got.get('type'), mx[1], mx[0]))
        return got

    PS.tilted_view = wrapped
    import collect as C
    hands = 0
    for k in range(4):
        hands += len(C.run_one(900000 + k, max_hands=n_per))
    PS.tilted_view = orig

    print('=' * 88)
    print('A. 캐시가 다른 프로필을 돌려준 횟수  (핸드 %d)' % hands)
    print('=' * 88)
    tot = stat['캐시 관여 호출']
    print('   tilted_view 호출 중 캐시 관여 %d · 비관여(tilt<=0.02 등) %d'
          % (tot, stat['캐시 비관여']))
    bad = stat['**오염된 반환**']
    print('   **오염된 반환 %d  (%.2f%%)**' % (bad, 100*bad/max(1, tot)))
    print('      type 도 다름                  %d' % stat['  그중 type 도 다름'])
    print('      type 은 같고 개념만 다름        %d  ← 기존 검출로는 안 잡히던 것'
          % stat['  그중 type 은 같음(기존 검출로는 안 잡힘)'])
    print()
    if diffs:
        print('   예시 (요청 type → 반환 type, 개념 최대 격차)')
        for pid, t, wt, gt, k, m in diffs:
            print('     좌석 %s tilt %.2f  %-18s → %-18s  %s 차 %.2f'
                  % (pid, t, wt, gt, k, m))
        print()
    if seat_tilt:
        print('   오염이 몰린 (좌석, tilt) 키 상위')
        for (pid, t), n in seat_tilt.most_common(6):
            print('     좌석 %s · tilt %.2f  — %d회' % (pid, t, n))
    print()
    print('   주의 — 이 수치는 **캐시가 관여한 호출 대비** 비율이다.')
    print('   tilt<=0.02 인 호출은 애초에 캐시를 타지 않으므로 분모에서 뺐다.')


def run_arm(mode, out, n_per):
    if mode == 'off':
        PS._TILT_VIEW_CACHE = NoCache()
    import collect as C
    recs = []
    for k in range(4):
        recs.extend(C.run_one(900000 + k, max_hands=n_per))
    with open(out, 'w') as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + '\n')
    print('%s: %d핸드 → %s' % (mode, len(recs), out))


def stage_c(on_p, off_p):
    A = [json.loads(l) for l in open(on_p)]
    B = [json.loads(l) for l in open(off_p)]
    print('=' * 88)
    print('C. 캐시 ON/OFF 반사실 — 어디서 갈라지는가')
    print('=' * 88)
    print('   ON  %d핸드 (현재 코드) · OFF %d핸드 (오염 없음)' % (len(A), len(B)))
    n = min(len(A), len(B))
    first = None
    ndiff = 0
    lvl = collections.Counter()
    for i in range(n):
        a, b = A[i], B[i]
        if json.dumps(a, sort_keys=True, ensure_ascii=False) == \
           json.dumps(b, sort_keys=True, ensure_ascii=False):
            continue
        ndiff += 1
        if first is None:
            first = i
        # 어느 층에서 갈렸는가
        if a.get('board') != b.get('board') or a.get('hole') != b.get('hole'):
            lvl['딜(이미 갈라진 뒤)'] += 1
            continue
        pa = {(i2['seat'], i2['street']): i2.get('plan') for i2 in a.get('intents', [])}
        pb = {(i2['seat'], i2['street']): i2.get('plan') for i2 in b.get('intents', [])}
        aa = {(i2['seat'], i2['street']): i2.get('action') for i2 in a.get('intents', [])}
        ab = {(i2['seat'], i2['street']): i2.get('action') for i2 in b.get('intents', [])}
        if aa != ab:
            lvl['action 이 다름'] += 1
        elif pa != pb:
            lvl['plan 은 다른데 action 은 같음'] += 1
        else:
            lvl['plan·action 같고 수치만 다름'] += 1
    print('   다른 핸드 %d / %d  (%.1f%%)' % (ndiff, n, 100*ndiff/max(1, n)))
    print('   첫 분기 인덱스 %s' % first)
    print()
    for k, v in lvl.most_common():
        print('     %-28s %d' % (k, v))
    print()
    print('   → "딜(이미 갈라진 뒤)"은 분기 이후 게임이 달라진 것이라')
    print('     인과의 증거가 아니다. 인과는 **첫 분기 핸드**와')
    print('     "plan/action 이 다름" 쪽에서 읽어야 한다.')


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    m = sys.argv[1]
    if m == 'AB':
        stage_ab(int(sys.argv[2]) if len(sys.argv) > 2 else 150)
    elif m == 'RUN':
        run_arm(sys.argv[2], sys.argv[3],
                int(sys.argv[4]) if len(sys.argv) > 4 else 150)
    elif m == 'C':
        stage_c(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
