#!/usr/bin/env python3
"""프리페치 전제 검증: _load_field → step_others(settle=False) → _dump 가
field_dump 만으로 완전히 결정되는가, 그리고 그 결과를 히어로 테이블 결과와
합칠 수 있는가.

  T2_BOT_LOG=0 python3 tools/verify_prefetch_determinism.py [--hands 6]

검사 1  결정성    같은 덤프로 여러 번 돌려 결과가 같은가.
                  같은 프로세스 2회 + 다른 프로세스 2회(PYTHONHASHSEED 다르게).
                  set 순회 순서 같은 숨은 의존이 있으면 프로세스 간에서 갈린다.
검사 2  정규성    _dump(_load_field(D)) == D 인가. 아니면 지문이 쓸데없이
                  달라져 프리페치가 계속 폐기된다.
검사 3  병합 표면 프리페치 쪽과 히어로 테이블 쪽이 각각 덤프의 어느 키를
                  바꾸는가. 교집합이 있으면 단순 합치기로는 한쪽을 잃는다.
"""
import argparse, copy, hashlib, json, os, subprocess, sys

D_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D_ROOT not in sys.path:
    sys.path.insert(0, D_ROOT)

CANON = dict(sort_keys=True, ensure_ascii=False, separators=(',', ':'))
def h(o): return hashlib.sha256(json.dumps(o, **CANON).encode()).hexdigest()


def make_dump(entries, hands, seed):
    """몇 핸드 진행한 필드 덤프를 만든다."""
    import fieldsim as FS, live2 as L
    f = FS.Field(entries=entries, start_stack=30000, hero_pid=0, seed=seed,
                 hands_per_level=12, itm_frac=0.15)
    for _ in range(hands):
        f.hand_no += 1; f.advance_level(); f.notes = []
        tb = f.tables.get(f.players[f.hero_pid]['table'])
        if tb is not None and tb.n() >= 2:
            f._play_table(tb)
        f.step_others()
    return L._dump(f)


def prefetch(dump):
    """프리페치가 할 일 그대로. 파일을 읽지도 쓰지도 않는다.

    **깊은 복사가 필수다.** live2._load_field:57 은 프로필 dict 를 덤프와
    그대로 공유하고(`'prof': v['prof']`), 봇 플레이가 프로필을 제자리에서
    바꾼다. 얕은 복사로 넘기면 넘겨준 덤프가 조용히 변한다.
    """
    import live2 as L
    f = L._load_field(copy.deepcopy(dump))
    f.notes = []
    f.step_others(settle=False)
    return L._dump(f)


def hero_side(dump):
    """히어로 테이블만 진행했을 때 덤프가 어떻게 바뀌는지."""
    import live2 as L
    f = L._load_field(copy.deepcopy(dump))
    f.notes = []
    tb = f.tables.get(f.players[f.hero_pid]['table'])
    if tb is not None and tb.n() >= 2:
        f._play_table(tb)
    return L._dump(f)


def changed_keys(a, b, path=''):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            out += changed_keys(a.get(k), b.get(k), path + '/' + str(k))
    elif a != b:
        out.append(path or '/')
    return out


def top(keys):
    """경로를 덤프 최상위 키 단위로 접는다."""
    s = {}
    for k in keys:
        p = k.strip('/').split('/')
        s.setdefault(p[0], 0)
        s[p[0]] += 1
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--hands', type=int, default=6)
    ap.add_argument('--seed', type=int, default=4242)
    ap.add_argument('--child', action='store_true', help='내부용: 자식 프로세스')
    a = ap.parse_args()

    if a.child:                      # 자식: 덤프를 받아 프리페치만 하고 해시 출력
        dump = json.load(sys.stdin)
        print(h(prefetch(dump)))
        return 0

    dump = make_dump(a.entries, a.hands, a.seed)
    frozen = json.dumps(dump, **CANON)          # 이후 비교의 고정 기준
    print('기준 덤프: entries %d, %d핸드 진행, seed %d' % (a.entries, a.hands, a.seed))
    print('  %s' % h(dump))

    # --- 검사 0 별칭 ---
    import live2 as L0
    probe = json.loads(frozen)
    f0 = L0._load_field(probe)
    pid0 = next(iter(f0.players))
    alias = f0.players[pid0]['prof'] is probe['players'][str(pid0)]['prof']
    before = h(probe)
    f0.notes = []; f0.step_others(settle=False)
    mutated = (h(probe) != before)
    print('\n[검사 0] 별칭  _load_field 가 넘겨받은 덤프를 공유/변경하는가')
    print('  prof dict 를 그대로 공유: %s   (live2.py:57)' % ('예' if alias else '아니오'))
    print('  플레이 후 원본 덤프가 변함: %s' % ('예' if mutated else '아니오'))
    if alias or mutated:
        print('  → 프리페치는 반드시 깊은 복사(또는 별도 프로세스의 JSON 왕복)로 넘겨야 한다.')

    # --- 검사 2 정규성 ---
    import live2 as L
    rt = L._dump(L._load_field(json.loads(frozen)))
    ok2 = (h(rt) == h(dump))
    print('\n[검사 2] 정규성  _dump(_load_field(D)) == D')
    print('  %s' % ('통과' if ok2 else '실패'))
    if not ok2:
        ks = changed_keys(dump, rt)
        print('  달라진 곳: %s' % top(ks))
        print('  예: %s' % ks[:5])

    # --- 검사 1 결정성 ---
    print('\n[검사 1] 결정성  같은 덤프 → 같은 프리페치 결과')
    hs = [h(prefetch(json.loads(frozen))) for _ in range(2)]
    for hashseed in ('0', '12345'):
        env = dict(os.environ, PYTHONHASHSEED=hashseed, T2_BOT_LOG='0')
        p = subprocess.run([sys.executable, os.path.abspath(__file__), '--child'],
                           input=frozen, capture_output=True,
                           text=True, env=env, cwd=D_ROOT)
        if p.returncode:
            print('  자식 실패(PYTHONHASHSEED=%s): %s' % (hashseed, p.stderr[-300:]))
            hs.append('ERROR')
        else:
            hs.append(p.stdout.strip())
    labels = ['같은 프로세스 1', '같은 프로세스 2',
              '다른 프로세스 HASHSEED=0', '다른 프로세스 HASHSEED=12345']
    for lb, x in zip(labels, hs):
        print('  %-26s %s' % (lb, x[:32]))
    ok1 = len(set(hs)) == 1 and 'ERROR' not in hs
    print('  %s' % ('통과 — field_dump 만으로 결정된다' if ok1 else '실패 — 숨은 상태가 있다'))

    # --- 검사 3 병합 표면 ---
    base = json.loads(frozen)
    pf = prefetch(json.loads(frozen))
    hv = hero_side(json.loads(frozen))
    kp = top(changed_keys(base, pf))
    kh = top(changed_keys(base, hv))
    print('\n[검사 3] 병합 표면')
    print('  프리페치가 바꾸는 최상위 키 : %s' % kp)
    print('  히어로 테이블이 바꾸는 키   : %s' % kh)
    both = sorted(set(kp) & set(kh))
    print('  양쪽이 같이 바꾸는 키       : %s' % (both or '없음'))
    if both:
        print('  → 단순히 한쪽 덤프를 기반으로 쓰면 다른 쪽 변경을 잃는다.')
        for k in both:
            pk = set(x for x in changed_keys(base, pf) if x.strip('/').split('/')[0] == k)
            hk = set(x for x in changed_keys(base, hv) if x.strip('/').split('/')[0] == k)
            inter = sorted(pk & hk)
            print('     [%s] 같은 경로까지 겹치는 것 %d개  %s'
                  % (k, len(inter), inter[:4]))
    return 0 if (ok1 and ok2) else 1


if __name__ == '__main__':
    sys.exit(main())
