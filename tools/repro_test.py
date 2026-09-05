"""재현성 검증. **이후 모든 A/B 검증의 전제다.**

    python3 tools/repro_test.py

seed 가 유실되면 실험 조건 자체가 깨진다. 실제로 `_load_field` 가 f.seed 를
복원하지 않아, 첫 step 이후 seed 가 None 이 되고
crc32('field|None|hand_no') 로 필드 RNG 가 파생됐다 —
**어떤 시드로 시작하든 두 번째 핸드부터 같은 RNG 를 썼다.**

검증 세 가지
  A. 같은 시드 두 번 → 완전히 같은 핸드 시퀀스
  B. 다른 시드 → 다른 시퀀스
  C. 저장/복원을 끼운 진행 == 처음부터 이어서 진행

각 실행은 **격리 폴더**에서 돌린다. 모듈 디렉터리에 상태·아카이브가 쓰이므로
같은 폴더에서 두 번 돌리면 서로 오염된다.
"""
import sys, os, json, shutil, tempfile, subprocess

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RUNNER = r'''
import sys, json, os
sys.path.insert(0, %r)
os.environ.pop('T2_LIVE_STATE', None)
import live2
seed = %r
n = %d
resume_at = %r
live2.new_game(entries=40, start_stack=30000, seed=seed, hands_per_level=12)
sig = []
done_hands = 0
while done_hands < n:
    r = live2.step()
    if r.get('done'):
        done_hands += 1
        continue
    r = live2.step('fold')
    if r.get('done'):
        done_hands += 1
    if resume_at and done_hands == resume_at:
        # 저장 상태를 그대로 두고 프로세스를 끊는다(= 세션 종료 재현)
        pass
rows = [json.loads(l) for l in open(os.path.join(%r, 'hand_archive2.jsonl'))
        if l.strip()]
for x in rows:
    sig.append('%%d:%%s:%%s' %% (x['hand_no'], x['hash'], ''.join(x['board'])))
st = json.load(open(os.path.join(%r, 'live2_state.json')))
print(json.dumps({'seed_after': st['field'].get('seed'), 'sig': sig}))
'''


def run(seed, hands, tag):
    tmp = tempfile.mkdtemp(prefix='repro_%s_' % tag)
    dst = os.path.join(tmp, 't2')
    shutil.copytree(_ROOT, dst, ignore=shutil.ignore_patterns(
        '.git', '__pycache__', 'hand_archive2*.jsonl', '*state*.json', 'bak_*'))
    code = RUNNER % (dst, seed, hands, None, dst, dst)
    out = subprocess.run([sys.executable, '-c', code], capture_output=True,
                         text=True, timeout=1200, cwd=dst)
    if out.returncode != 0:
        print(out.stderr[-600:])
        shutil.rmtree(tmp, ignore_errors=True)
        return None
    res = json.loads(out.stdout.strip().splitlines()[-1])
    shutil.rmtree(tmp, ignore_errors=True)
    return res


SPLIT = r"""
import sys, json, os
sys.path.insert(0, {root!r})
os.environ.pop('T2_LIVE_STATE', None)
import live2
live2.new_game(entries=40, start_stack=30000, seed={seed}, hands_per_level=12)
n = 0
while n < {first}:
    r = live2.step()
    if r.get('done'):
        n += 1; continue
    r = live2.step('fold')
    if r.get('done'):
        n += 1
print('SPLIT_OK')
"""

RESUME = r"""
import sys, json, os
sys.path.insert(0, {root!r})
os.environ.pop('T2_LIVE_STATE', None)
import live2
n = 0
while n < {more}:
    r = live2.step()
    if r.get('done'):
        n += 1; continue
    r = live2.step('fold')
    if r.get('done'):
        n += 1
rows = [json.loads(l) for l in open(os.path.join({root!r}, 'hand_archive2.jsonl')) if l.strip()]
print(json.dumps([('%d:%s:%s' % (x['hand_no'], x['hash'], ''.join(x['board']))) for x in rows]))
"""


def run_split(seed, first, more):
    """저장/복원을 끼운 진행. 프로세스를 나눠 실제 세션을 재현한다."""
    tmp = tempfile.mkdtemp(prefix='repro_split_')
    dst = os.path.join(tmp, 't2')
    shutil.copytree(_ROOT, dst, ignore=shutil.ignore_patterns(
        '.git', '__pycache__', 'hand_archive2*.jsonl', '*state*.json', 'bak_*'))
    o1 = subprocess.run([sys.executable, '-c',
                         SPLIT.format(root=dst, seed=seed, first=first)],
                        capture_output=True, text=True, timeout=1200, cwd=dst)
    if 'SPLIT_OK' not in o1.stdout:
        print(o1.stderr[-500:]); shutil.rmtree(tmp, ignore_errors=True); return None
    o2 = subprocess.run([sys.executable, '-c',
                         RESUME.format(root=dst, more=more)],
                        capture_output=True, text=True, timeout=1200, cwd=dst)
    if o2.returncode != 0:
        print(o2.stderr[-500:]); shutil.rmtree(tmp, ignore_errors=True); return None
    sig = json.loads(o2.stdout.strip().splitlines()[-1])
    shutil.rmtree(tmp, ignore_errors=True)
    return sig


def main():
    print('재현성 검증 (각 실행은 격리 폴더)')
    print()
    a = run(26001, 6, 'a')
    b = run(26001, 6, 'b')
    c = run(99999, 6, 'c')
    if not (a and b and c):
        print('실행 실패')
        return

    print('A. 시드 유지')
    for tag, r, want in (('seed 26001 (1회)', a, 26001),
                         ('seed 26001 (2회)', b, 26001),
                         ('seed 99999', c, 99999)):
        ok = r['seed_after'] == want
        print('   [%s] %-20s 저장된 seed=%s' %
              ('OK' if ok else '실패', tag, r['seed_after']))

    print()
    print('B. 같은 시드 → 같은 시퀀스')
    same = a['sig'] == b['sig']
    print('   [%s] 핸드 %d개 시그니처 일치' %
          ('OK' if same else '실패', len(a['sig'])))
    if not same:
        for i, (x, y) in enumerate(zip(a['sig'], b['sig'])):
            if x != y:
                print('      첫 불일치 #%d: %s vs %s' % (i, x, y))
                break

    print()
    print('C. 다른 시드 → 다른 시퀀스')
    diff = a['sig'] != c['sig']
    print('   [%s] 26001 vs 99999' % ('OK' if diff else '실패'))
    if a['sig'] and c['sig']:
        print('      26001 첫 핸드: %s' % a['sig'][0])
        print('      99999 첫 핸드: %s' % c['sig'][0])

    print()
    print('D. 저장/복원을 끼운 진행 == 이어서 진행')
    split = run_split(26001, 3, 3)
    if split is None:
        print('   실행 실패')
        return
    ok = split == a['sig']
    print('   [%s] 3핸드 후 프로세스 분리 → 3핸드 더 (총 %d) vs 연속 6핸드'
          % ('OK' if ok else '실패', len(split)))
    if not ok:
        for i, (x, y) in enumerate(zip(a['sig'], split)):
            if x != y:
                print('      첫 불일치 #%d: 연속 %s / 분리 %s' % (i, x, y))
                break


if __name__ == '__main__':
    main()
