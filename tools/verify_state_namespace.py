#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""상태별 sidecar namespace 격리 검증 (A9-W). 읽기 전용.

  python3 tools/verify_state_namespace.py

**저장소의 sidecar 파일을 만들거나 고치지 않는다.** 실제 실행이 필요한
검사는 `storage_paths.D` 를 임시 디렉터리로 돌려놓고 그 안에서만 한다.

검사 목록 (지시한 A~J)

  A  기본 상태는 기존 접미사 없는 이름 그대로
  B  같은 realpath 는 항상 같은 namespace
  C  다른 상태는 다른 namespace
  D  A/B 를 각각 돌렸을 때 archive·book·dynamics·bot_hands 가 안 섞인다
  E  A 에서 new_game 해도 B 의 파일을 rename/delete 하지 않는다
  F  워커 bot log 가 원래 namespace 에만 붙는다
  G  UI 가 상태 A 를 볼 때 A 의 아카이브만 읽는다
  H  hashed 파일이 없고 `_alt` 만 있으면 읽기 전용 legacy 로 발견,
     새 쓰기는 hashed 쪽
  I  기본 namespace 의 기존 파일을 자동 migrate/delete/rename 하지 않는다
  J  basename 은 같고 디렉터리가 다른 두 경로는 namespace 가 다르다
"""
import hashlib, importlib, json, os, shutil, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import storage_paths as SP

FAILS = []


def ok(name, cond, detail=''):
    print('  %-26s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
    if not cond:
        FAILS.append(name)


def _env(state=None):
    e = dict(os.environ)
    e.pop(SP.ENV, None)
    if state:
        e[SP.ENV] = state
    return e


def _base(path):
    return os.path.basename(path)


# ---------------------------------------------------------------- A·B·C·J

def check_rules():
    print('=== A. 기본 상태 = 접미사 없음 ===')
    e = _env()
    ok('기본 namespace 빈값', SP.namespace(e) == '', repr(SP.namespace(e)))
    for kind, want in (('archive', 'hand_archive2.jsonl'),
                       ('bot_log', 'bot_hands.jsonl'),
                       ('book', 'book.json'),
                       ('dynamics', 'dynamics.json')):
        ok('기본 %s' % kind, _base(SP.sidecar_path(kind, env=e)) == want,
           _base(SP.sidecar_path(kind, env=e)))

    print('=== B. 결정론 ===')
    a1 = SP.namespace_for_state('/tmp/ns_a/state.json')
    a2 = SP.namespace_for_state('/tmp/ns_a/state.json')
    a3 = SP.namespace_for_state('/tmp/ns_a/../ns_a/state.json')
    ok('같은 경로 = 같은 ns', a1 == a2 == a3, a1)
    ok('stable hash', a1 == SP.NS_PREFIX + hashlib.sha256(
        os.path.realpath('/tmp/ns_a/state.json').encode()).hexdigest()[:SP.NS_HEX],
       'sha256 기반 — PYTHONHASHSEED 무관')

    print('=== C·J. 경로 격리 ===')
    b = SP.namespace_for_state('/tmp/ns_b/state.json')
    ok('A≠B', a1 != b, '%s vs %s' % (a1, b))
    j1 = SP.namespace_for_state('/tmp/j_a/state.json')
    j2 = SP.namespace_for_state('/tmp/j_b/state.json')
    ok('basename 같아도 분리', j1 != j2, '%s vs %s' % (j1, j2))
    ok('_alt 를 새로 쓰지 않음',
       SP.LEGACY_SUFFIX not in SP.sidecar_path('archive', '/tmp/ns_a/state.json'),
       _base(SP.sidecar_path('archive', '/tmp/ns_a/state.json')))


# ---------------------------------------------------------------- 실행 격리

def _run_in(tmp, state_name, hands=3, seed=880001):
    """임시 폴더를 모듈 폴더로 삼고 짧게 돌린다. 저장소를 건드리지 않는다."""
    st = os.path.join(tmp, state_name)
    old_d, old_env = SP.D, os.environ.get(SP.ENV)
    SP.D = tmp
    SP.DEFAULT_STATE = os.path.join(tmp, 'live2_state.json')
    os.environ[SP.ENV] = st
    try:
        import live2 as L
        importlib.reload(L)
        L.D = tmp
        L.ST = st
        L._SUFFIX = SP.namespace()
        import fieldsim as FS
        FS.D = tmp
        FS.BOT_SUFFIX = SP.namespace()
        st0 = L.new_game(entries=12, start_stack=20000, seed=seed,
                         hands_per_level=6)
        L.save(st0)
        # step() 은 상태를 **파일에서** 읽는다. 인자로 넘기지 않는다.
        errs = []
        for _ in range(hands * 40):
            try:
                r = L.step('fold')
            except Exception as ex:
                errs.append('%s: %s' % (type(ex).__name__, ex))
                break
            if not isinstance(r, dict):
                break
            if r.get('done'):
                if L.load().get('rank'):
                    break
                L.step()        # 다음 핸드 딜
        if errs:
            print('      실행 오류: %s' % errs[0])
        return sorted(os.listdir(tmp))
    finally:
        SP.D, SP.DEFAULT_STATE = old_d, os.path.join(old_d, 'live2_state.json')
        if old_env is None:
            os.environ.pop(SP.ENV, None)
        else:
            os.environ[SP.ENV] = old_env


def check_isolation():
    print('=== D·E·F. 두 상태 동시 격리 ===')
    tmp = tempfile.mkdtemp(prefix='t2_ns_')
    try:
        os.makedirs(os.path.join(tmp, 'A'), exist_ok=True)
        os.makedirs(os.path.join(tmp, 'B'), exist_ok=True)
        ns_a = SP.namespace_for_state(os.path.join(tmp, 'A', 'state.json'))
        ns_b = SP.namespace_for_state(os.path.join(tmp, 'B', 'state.json'))
        ok('ns 분리', ns_a != ns_b, '%s / %s' % (ns_a, ns_b))

        files_a = _run_in(tmp, os.path.join('A', 'state.json'), seed=880001)
        mid = set(files_a)
        files_b = _run_in(tmp, os.path.join('B', 'state.json'), seed=880002)
        after = set(files_b)

        own_a = sorted(f for f in mid if ns_a in f)
        own_b = sorted(f for f in after if ns_b in f)
        ok('A 파일 생성', bool(own_a), ' '.join(own_a) or '(없음)')
        ok('B 파일 생성', bool(own_b), ' '.join(own_b) or '(없음)')
        ok('교집합 없음', not (set(own_a) & set(own_b)))
        ok('A 파일 보존', set(own_a) <= after,
           '없어진 것 %s' % sorted(set(own_a) - after))
        # E: B 의 new_game 이 A 의 파일을 백업(rename)하지 않았는가
        moved = [f for f in after if f.startswith('bak_') and ns_a in f]
        ok('E: A 를 백업 안 함', not moved, ' '.join(moved))
        # F: 워커 임시 접미사가 남아 있지 않은가
        pend = [f for f in after if '_pending_' in f]
        ok('F: 워커 임시파일 없음', not pend, ' '.join(pend))
        bl = [f for f in after if f.startswith('bot_hands')]
        ok('F: bot log namespace', all(ns_a in f or ns_b in f for f in bl),
           ' '.join(bl) or '(없음)')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- G·H·I

def check_ui_and_legacy():
    print('=== G. UI 가 엔진 namespace 를 따르는가 ===')
    src = open(os.path.join(ROOT, 'ui', 'server', 'ui_server.py'),
               encoding='utf-8').read()
    ok('UI 하드코딩 없음', "os.path.join(D, 'hand_archive2.jsonl')" not in src)
    ok('UI resolver 사용', "_SP.resolve_read('archive')" in src)

    print('=== H. legacy _alt 발견 (읽기 전용) ===')
    tmp = tempfile.mkdtemp(prefix='t2_leg_')
    old_d = SP.D
    try:
        SP.D = tmp
        st = os.path.join(tmp, 'custom', 'state.json')
        leg = SP.legacy_path('archive')
        open(leg, 'w').write('{}\n')
        before = os.path.getsize(leg), os.path.getmtime(leg)
        p, src_kind = SP.resolve_read('archive', st)
        ok('legacy 발견', p == leg and src_kind == 'legacy_alt',
           '%s / %s' % (_base(p or ''), src_kind))
        w = SP.sidecar_path('archive', st)
        ok('쓰기는 hashed', SP.LEGACY_SUFFIX not in _base(w), _base(w))
        # hashed 가 생기면 그쪽이 current
        open(w, 'w').write('{}\n')
        p2, k2 = SP.resolve_read('archive', st)
        ok('hashed 우선', p2 == w and k2 == 'current', k2)
        ok('legacy 불변', (os.path.getsize(leg), os.path.getmtime(leg)) == before,
           'rename/copy/migrate 하지 않는다')

        print('=== I. 기본 namespace 기존 파일 안전 ===')
        SP.DEFAULT_STATE = os.path.join(tmp, 'live2_state.json')
        d_arch = SP.sidecar_path('archive', SP.DEFAULT_STATE)
        open(d_arch, 'w').write('{"hand_no": 1}\n')
        snap = os.path.getsize(d_arch), open(d_arch).read()
        SP.resolve_read('archive', st)          # 사용자 상태 조회
        SP.sidecar_path('archive', st)
        ok('기본 파일 불변',
           (os.path.getsize(d_arch), open(d_arch).read()) == snap,
           _base(d_arch))
    finally:
        SP.D = old_d
        SP.DEFAULT_STATE = os.path.join(old_d, 'live2_state.json')
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    repo_before = _repo_sidecars()
    check_rules()
    print()
    check_isolation()
    print()
    check_ui_and_legacy()
    print()
    after = _repo_sidecars()
    moved = sorted(set(repo_before) ^ set(after)) + \
        sorted(k for k in set(repo_before) & set(after)
               if repo_before[k] != after[k])
    ok('저장소 sidecar 불변', not moved,
       ('%d파일' % len(repo_before)) if not moved else
       ('바뀐 것: %s — 다른 프로세스가 같은 폴더에 쓰고 있지 않은지 볼 것'
        % ', '.join(moved[:6])))
    print()
    if FAILS:
        print('FAIL %d : %s' % (len(FAILS), ', '.join(FAILS)))
        return 1
    print('PASS 상태별 sidecar namespace 격리')
    return 0


def _repo_sidecars():
    out = {}
    for f in sorted(os.listdir(ROOT)):
        if f.endswith(('.jsonl', '.json')):
            p = os.path.join(ROOT, f)
            if os.path.isfile(p):
                out[f] = os.path.getsize(p)
    return out


if __name__ == '__main__':
    raise SystemExit(main())
