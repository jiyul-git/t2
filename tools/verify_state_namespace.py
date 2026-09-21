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
        r = SP.resolve_read('archive', st)
        ok('legacy 발견', r['legacy_path'] == leg
           and r['source'] == SP.SRC_LEGACY_AMBIGUOUS, r['source'])
        ok('opt-in 없이 path 없음', r['path'] is None and not r['usable'],
           '주인을 단정하지 않는다')
        r_in = SP.resolve_read('archive', st, allow_legacy_alt=True)
        ok('opt-in 시 읽기 허용', r_in['path'] == leg and r_in['usable'])
        w = SP.sidecar_path('archive', st)
        ok('쓰기는 hashed', SP.LEGACY_SUFFIX not in _base(w), _base(w))
        # hashed 가 생기면 그쪽이 current
        open(w, 'w').write('{}\n')
        r2 = SP.resolve_read('archive', st)
        ok('hashed 우선', r2['path'] == w and r2['source'] == SP.SRC_CURRENT,
           r2['source'])
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


def check_ambiguous_ownership():
    """K·L·M. 옛 공유 `_alt` 는 **주인을 알 수 없다.**

    과거에는 custom state 가 무엇이든 전부 같은 `_alt` 에 썼다. A 에
    hashed 가 없다는 이유로 그 파일을 A 의 과거 기록으로 읽으면 **B 의
    기록을 A 의 것으로** 제시하게 된다.
    """
    print('=== K·L·M. 공유 legacy 의 소유권 모호성 ===')
    tmp = tempfile.mkdtemp(prefix='t2_amb_')
    old_d, old_def = SP.D, SP.DEFAULT_STATE
    try:
        SP.D = tmp
        SP.DEFAULT_STATE = os.path.join(tmp, 'live2_state.json')
        a = os.path.join(tmp, 'A', 'state.json')
        b = os.path.join(tmp, 'B', 'state.json')
        leg = SP.legacy_path('archive')
        open(leg, 'w').write('{"hand_no": 1}\n')
        snap = (os.path.getsize(leg), os.path.getmtime(leg))

        # K — 둘 다 모호로 분류되고, 둘 다 자동으로 읽지 않는다
        ra, rb = SP.resolve_read('archive', a), SP.resolve_read('archive', b)
        ok('K: A 모호', ra['source'] == SP.SRC_LEGACY_AMBIGUOUS, ra['source'])
        ok('K: B 모호', rb['source'] == SP.SRC_LEGACY_AMBIGUOUS, rb['source'])
        ok('K: 자동 소비 없음', ra['path'] is None and rb['path'] is None)
        ok('K: 존재는 노출', ra['legacy_path'] == leg == rb['legacy_path'])
        ok('K: 설명 있음', bool(ra['note']))

        # L — opt-in 을 명시해야만 읽힌다
        ia = SP.resolve_read('archive', a, allow_legacy_alt=True)
        ok('L: opt-in 허용', ia['path'] == leg and ia['usable'])
        ok('L: 기본은 불가', SP.read_path('archive', a) is None)
        ok('L: legacy 불변',
           (os.path.getsize(leg), os.path.getmtime(leg)) == snap)

        # M — A 만 hashed 를 만들면 B 는 여전히 모호하고 A 것을 못 읽는다
        wa = SP.sidecar_path('archive', a)
        open(wa, 'w').write('{"hand_no": 9}\n')
        ra2, rb2 = SP.resolve_read('archive', a), SP.resolve_read('archive', b)
        ok('M: A 는 current', ra2['path'] == wa
           and ra2['source'] == SP.SRC_CURRENT, ra2['source'])
        ok('M: B 는 여전히 모호', rb2['source'] == SP.SRC_LEGACY_AMBIGUOUS,
           rb2['source'])
        ok('M: B 가 A 를 안 읽음', rb2['path'] != wa
           and SP.resolve_read('archive', b, allow_legacy_alt=True)['path'] != wa)
    finally:
        SP.D, SP.DEFAULT_STATE = old_d, old_def
        shutil.rmtree(tmp, ignore_errors=True)


# `resolve_read` 결과에서 출처를 보지 않고 경로만 쓰는 호출부가 없어야 한다.
READERS = ('review.py', 'audit.py', os.path.join('ui', 'server', 'ui_server.py'))


def check_callers_read_source():
    print('=== 호출부가 출처를 보는가 ===')
    import re
    for rel in READERS:
        src = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        calls = re.findall(r'resolve_read\([^)]*\)', src)
        if not calls:
            ok(_base(rel), True, '호출 없음')
            continue
        # 튜플 언패킹(`a, b = resolve_read(...)`)은 옛 API 다
        bad = re.search(r'\w+\s*,\s*\w+\s*=\s*_?SP\.resolve_read', src)
        ok(_base(rel), not bad,
           '매핑을 받는다' if not bad else '옛 튜플 언패킹이 남아 있다')
    # ui 는 ambiguous 를 소비하지 않아야 한다
    ui = open(os.path.join(ROOT, 'ui', 'server', 'ui_server.py'),
              encoding='utf-8').read()
    ok('UI opt-in 안 함', 'allow_legacy_alt=True' not in ui,
       'UI 는 모호한 legacy 를 현재 기록에 섞지 않는다')
    au = open(os.path.join(ROOT, 'audit.py'), encoding='utf-8').read()
    ok('audit 기본 False', 'ALLOW_LEGACY_ALT = False' in au)


def _load_ui_server(run_dir):
    """지원되는 레이아웃에서 `ui_server` 를 적재한다.

    `ui_server.py` 는 모듈 폴더에 `UI_SERVER_DIR` 표시 파일이 없으면
    `sys.exit` 한다 — cli 세션과 파일을 공유하는 사고를 막는 의도적 가드다.
    저장소에 그 파일을 만들면 가드가 무의미해지므로, `setup_run_dir.sh` 로
    **실제 실행 폴더**를 임시로 만들어 그 안에서 읽는다. 가드를 우회하지
    않고 충족시킨다.

    실패하면 (None, 사유) 를 돌려준다. 조용히 건너뛰지 않는다.
    """
    import subprocess
    sh = os.path.join(ROOT, 'ui', 'tools', 'setup_run_dir.sh')
    r = subprocess.run(['sh', sh, run_dir], capture_output=True, text=True,
                       timeout=180)
    if r.returncode != 0:
        return None, 'setup_run_dir.sh rc=%d %s' % (r.returncode,
                                                    (r.stderr or '')[:120])
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'ui_server_probe', os.path.join(run_dir, 'ui_server.py'))
    mod = importlib.util.module_from_spec(spec)
    old_path = list(sys.path)
    sys.path.insert(0, run_dir)
    try:
        spec.loader.exec_module(mod)
    except BaseException as e:
        return None, '%s: %s' % (type(e).__name__, e)
    finally:
        sys.path[:] = old_path
    return mod, None


def check_visibility():
    """N·O. '없음'과 '모호'가 사용자 쪽에서 구분되는가.

    빈 목록 하나로 접으면 "기록이 없다"와 "옛 공유 기록이 있는데 이 세션
    것인지 증명할 수 없어 안 쓴다"를 구분할 수 없다. 두 번째는 데이터가
    어딘가에 있다는 뜻이라 대응이 완전히 다르다.
    """
    print('=== N·O. ambiguous vs missing 가시성 ===')
    sys.path.insert(0, os.path.join(ROOT, 'ui', 'server'))
    import review as RV
    tmp = tempfile.mkdtemp(prefix='t2_vis_')
    old_d, old_def, old_env = SP.D, SP.DEFAULT_STATE, os.environ.get(SP.ENV)
    try:
        SP.D = tmp
        SP.DEFAULT_STATE = os.path.join(tmp, 'live2_state.json')
        a = os.path.join(tmp, 'A', 'state.json')
        b = os.path.join(tmp, 'B', 'state.json')
        os.environ[SP.ENV] = a
        RV.PATH = SP.sidecar_path('archive', a)

        # --- case 1: 아무것도 없다 ---
        r1 = SP.resolve_read('archive', a)
        ok('N1 source=missing', r1['source'] == SP.SRC_MISSING, r1['source'])
        s1 = RV.status()
        ok('N1 review 문구', s1 and '없습니다' in s1, (s1 or '')[:40])

        # --- case 2: 공유 _alt 만 있다 ---
        leg = SP.legacy_path('archive')
        open(leg, 'w', encoding='utf-8').write(
            json.dumps({'hand_no': 777, 'hero': 7, 'board': ['As'],
                        'pos': {}, 'hole': {}, 'profiles': {},
                        'full_log': [], 'result': {}, 'level': 1,
                        'blinds': [1, 2], 'hash': 'x'}) + '\n')
        r2 = SP.resolve_read('archive', a)
        ok('N2 source=ambiguous', r2['source'] == SP.SRC_LEGACY_AMBIGUOUS,
           r2['source'])
        s2 = RV.status()
        ok('N2 review 문구', s2 and '모호' not in (s1 or '') and s2 != s1,
           (s2 or '')[:52])
        ok('N: 두 문구가 다르다', s1 != s2)
        ok('N2 review 비어 있음', RV.load() == [], '자동으로 읽지 않는다')
        ok('N2 summary 가 설명', RV.summary() == s2)
        ok('N2 history 가 설명', RV.history() == s2)

        # --- case 3: opt-in ---
        rows = RV.load(allow_legacy_alt=True)
        ok('N3 opt-in 읽힘', len(rows) == 1 and rows[0]['hand_no'] == 777,
           '%d행' % len(rows))
        ok('N3 opt-in 시 status 없음', RV.status(allow_legacy_alt=True) is None)

        # --- O: UI 가 공유 아카이브 내용을 반환하지 않는가 ---
        run_dir = os.path.join(tmp, 'uirun')
        UI, why = _load_ui_server(run_dir)
        ok('O UI 적재', UI is not None, why or '')
        if UI is None:
            return
        # 실행 폴더가 모듈 폴더이므로 sidecar 도 거기서 찾게 맞춘다.
        UI._SP.D = tmp
        UI._SP.DEFAULT_STATE = os.path.join(tmp, 'live2_state.json')
        leaked = []
        for st in (a, b):
            os.environ[SP.ENV] = st
            meta = UI._archive_status()
            hands = UI._public_history()
            ok('O UI(%s) 목록 비어 있음' % os.path.basename(os.path.dirname(st)),
               hands == [], '%d건' % len(hands))
            ok('O UI(%s) 출처 노출' % os.path.basename(os.path.dirname(st)),
               meta['archive_source'] == SP.SRC_LEGACY_AMBIGUOUS
               and bool(meta['archive_warning'])
               and meta['legacy_archive'] == os.path.basename(leg),
               meta['archive_source'])
            leaked += [h for h in hands if h.get('hand_no') == 777]
        ok('O: 유출 없음', not leaked)
        # missing 일 때는 경고가 없어야 한다 (두 상태를 구분)
        os.remove(leg)
        os.environ[SP.ENV] = a
        m0 = UI._archive_status()
        ok('O: missing 은 경고 없음',
           m0['archive_source'] == SP.SRC_MISSING
           and m0['archive_warning'] is None, m0['archive_source'])
    finally:
        SP.D, SP.DEFAULT_STATE = old_d, old_def
        if old_env is None:
            os.environ.pop(SP.ENV, None)
        else:
            os.environ[SP.ENV] = old_env
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    repo_before = _repo_sidecars()
    check_rules()
    print()
    check_isolation()
    print()
    check_ui_and_legacy()
    print()
    check_ambiguous_ownership()
    print()
    check_callers_read_source()
    print()
    check_visibility()
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
