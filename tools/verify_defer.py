#!/usr/bin/env python3
"""안 A(다른 테이블 진행 지연)가 동작을 보존하는지 검증한다.

  T2_BOT_LOG=2 python3 tools/verify_defer.py [--entries 100] [--hands 12]

같은 시드로 세 세션을 각각 **별도 임시 폴더**에서 돌려 비교한다.

  off     지금과 같은 경로 (기준)
  inline  defer_others=True 인데 워커 결과를 안 준다.
          → 다음 step() 이 딜 직전에 직접 돌린다.
          **사용자가 결과를 보자마자 다음 핸드를 눌러버린 최악의 경우**와 같다.
  worker  defer_others=True 이고, 결과 반환 직후 compute_others 를 계산해
          다음 step() 에 넘긴다. → hit 경로.
  http    --http 을 주면 ui_server 를 실제로 띄워 HTTP 로 친다. 별도 프로세스
          워커까지 포함한 진짜 경로다. /api/stats 로 카운터를 읽는다.

대조 항목
  hand_archive2.jsonl / bot_hands.jsonl / 최종 필드 덤프 의 SHA-256

세는 것
  attempt   지연을 건 핸드 수
  hit       넘겨준 결과를 그대로 쓴 횟수
  mismatch  지문이 어긋나 버린 횟수
  fallback  넘겨받은 결과가 없어 직접 돌린 횟수
  worker_exception
  no_defer  히어로가 터져서 지연하지 않은 핸드 (rank 확정이 필요하다)

hit 가 0 이면 통과가 아니다. 최적화가 아예 작동하지 않은 것이다.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SETUP = os.path.join(os.path.dirname(HERE), 'ui', 'tools', 'setup_run_dir.sh')

CHILD = r'''
import sys, os, json, hashlib, copy
sys.path.insert(0, '.')
import ui_view; sys.modules['view'] = ui_view
import live2 as L

MODE = os.environ['MODE']; HANDS = int(os.environ['HANDS'])
ENTRIES = int(os.environ['ENTRIES']); SEED = int(os.environ['SEED'])
C = {'attempt':0,'hit':0,'mismatch':0,'fallback':0,'worker_exception':0,'no_defer':0}

_resume = L.resume_others
def resume(st, others=None):
    how = _resume(st, others)
    if how: C[how] = C.get(how, 0) + 1
    return how
L.resume_others = resume

pend = {'others': None}

def call(action, amount=0):
    kw = {}
    if MODE != 'off':
        kw['defer_others'] = True
        if MODE == 'worker' and pend['others'] is not None:
            kw['others'] = pend['others']
    r = (L.step(action, amount, **kw) if action is not None
         else L.step(None, 0, **kw))
    pend['others'] = None
    if MODE == 'worker':
        st = L.load()
        if st.get('others_pending'):
            try:
                pend['others'] = L.compute_others(st['field'])   # 워커가 할 일
            except Exception:
                C['worker_exception'] += 1
    if r.get('done'):
        C['attempt'] += 1
        if MODE != 'off' and not L.load().get('others_pending'):
            C['no_defer'] += 1
    return r

L.new_game(entries=ENTRIES, start_stack=30000, seed=SEED)
r = call(None); n = 0
BUSTED = {'at': None}
while n < HANDS:
    v = r.get('view') or {}
    if r.get('done'):
        n += 1
        # 히어로가 터지면 여기서 멈춘다. 탈락 후 step() 은 크래시한다
        # (build_hand -> tb 가 None). 엔진의 기존 결함이고 이번 검증 대상이
        # 아니다. 어느 핸드에서 터졌는지는 모드 간 대조 항목으로 남긴다.
        if r.get('busted'):
            BUSTED['at'] = n
            break
        if n >= HANDS: break
        r = call(None); continue
    if v.get('type') != 'decision': break
    lg = v['legal']; me = [s for s in v['seats'] if s['hero']][0]
    a = ('check' if lg['check'] else
         ('call' if lg['call'] is not None and lg['call'] <= 0.25*me['stack'] else 'fold'))
    r = call(a)

# 마지막에 밀린 게 남아 있으면 끝낸다 (세션 종료 시점 정합)
st = L.load()
if st.get('others_pending'):
    L.resume_others(st, pend['others'])

h = lambda p: (hashlib.sha256(open(p,'rb').read()).hexdigest()
               if os.path.exists(p) else 'none')

def integrity(p):
    """줄 수 / 전부 JSON 으로 읽히는가 / 마지막 줄이 잘렸는가 / 중복 줄."""
    if not os.path.exists(p):
        return {'lines': 0, 'bad': 0, 'truncated': None, 'dup': 0}
    raw = open(p, 'rb').read()
    txt = raw.decode('utf-8', 'replace')
    ls = [x for x in txt.split('\n') if x.strip()]
    bad = 0
    for x in ls:
        try: json.loads(x)
        except Exception: bad += 1
    return {'lines': len(ls), 'bad': bad,
            'truncated': not raw.endswith(b'\n') if raw else False,
            'dup': len(ls) - len(set(ls))}

def hero_actions(p):
    """히어로가 실제로 낸 액션 시퀀스. 아카이브의 full_log 에서 히어로 좌석만.
    아카이브 해시에 이미 포함되지만, 어긋났을 때 무엇이 어긋났는지 보려면
    따로 뽑아둬야 한다."""
    out = []
    if not os.path.exists(p):
        return out
    for line in open(p):
        if not line.strip(): continue
        rec = json.loads(line)
        # hero 와 full_log 는 레코드 **최상위**다 (rec['result'] 안이 아니다)
        hs = rec.get('hero')
        for e in (rec.get('full_log') or []):
            if hs is not None and e[1] == hs:
                out.append([rec.get('hand_no'), e[0], e[2], e[3]])
    return out

def survivors(fd):
    """칩이 남은 사람. 좌석이 아니라 pid 기준."""
    return sorted(int(k) for k, v in (fd.get('players') or {}).items()
                  if v.get('stack', 0) > 0)

st = L.load()
print(json.dumps({
  'archive': h('hand_archive2.jsonl'), 'bots': h('bot_hands.jsonl'),
  'hero_actions': hero_actions('hand_archive2.jsonl'),
  'hands_played': n, 'busted_at': BUSTED['at'],
  'survivors': survivors(st['field']),
  'field': hashlib.sha256(json.dumps(st['field'], sort_keys=True).encode()).hexdigest(),
  'rank': st.get('rank'), 'busted': st.get('busted'),
  'busted_order': st['field'].get('busted_order'),
  'arch_int': integrity('hand_archive2.jsonl'),
  'bots_int': integrity('bot_hands.jsonl'),
  'residue': {'others_pending': bool(st.get('others_pending')),
              'pending_archive': bool(st.get('pending_archive')),
              'pending_notes': bool(st.get('pending_notes'))},
  'counters': C}))
'''


def run(mode, entries, hands, seed, keep):
    tmp = tempfile.mkdtemp(prefix='t2_defer_%s_' % mode)
    subprocess.run(['sh', SETUP, tmp], check=True, stdout=subprocess.DEVNULL)
    open(os.path.join(tmp, 'child.py'), 'w').write(CHILD)
    env = dict(os.environ, MODE=mode, HANDS=str(hands), ENTRIES=str(entries),
               SEED=str(seed))
    env.setdefault('T2_BOT_LOG', '2')
    p = subprocess.run([sys.executable, 'child.py'], cwd=tmp, env=env,
                       capture_output=True, text=True)
    if not keep:
        shutil.rmtree(tmp, ignore_errors=True)
    if p.returncode:
        return {'error': p.stderr[-1200:]}
    return json.loads(p.stdout.strip().splitlines()[-1])


HTTP_CLIENT = r"""
import sys, json, time, hashlib, os, subprocess, urllib.request, urllib.error
PORT = int(os.environ['PORT']); HANDS = int(os.environ['HANDS'])
ENTRIES = int(os.environ['ENTRIES']); SEED = int(os.environ['SEED'])
FAST = os.environ.get('FAST') == '1'      # 즉시 클릭 최악의 경우
BASE = 'http://127.0.0.1:%d' % PORT
def call(path, obj=None):
    req = (urllib.request.Request(BASE+path, data=json.dumps(obj).encode(),
                                  headers={'Content-Type':'application/json'})
           if obj is not None else urllib.request.Request(BASE+path))
    try:
        with urllib.request.urlopen(req, timeout=300) as f:
            return f.status, json.load(f)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)
for _ in range(200):
    try: call('/api/state'); break
    except Exception: time.sleep(0.2)
c, r = call('/api/new', {'entries': ENTRIES, 'seed': SEED, 'start_stack': 30000})
n = 0
BUSTED = {'at': None}
while n < HANDS:
    v = r.get('view') or {}
    if r.get('game_over'): break
    if r.get('done'):
        n += 1
        if r.get('busted'):               # 히어로 탈락 — CHILD 와 같은 규칙
            BUSTED['at'] = n
            break
        if n >= HANDS: break
        if not FAST: time.sleep(1.2)      # 결과 화면을 읽는 시간
        c, r = call('/api/step', {'action': None, 'amount': 0, 'token': r['token']})
        continue
    if v.get('type') != 'decision': break
    lg = v['legal']; me = [s for s in v['seats'] if s['hero']][0]
    a = ('check' if lg['check'] else
         ('call' if lg['call'] is not None and lg['call'] <= 0.25*me['stack'] else 'fold'))
    c, r = call('/api/step', {'action': a, 'amount': 0, 'token': r['token']})
    if c != 200: break
c, stats = call('/api/stats')
print(json.dumps({'stats': stats, 'hands': n,
                  'hands_played': n, 'busted_at': BUSTED['at']}))
"""


def _hero_actions(path):
    """히어로 액션 시퀀스. CHILD 안의 hero_actions 와 같은 규칙이다
    (자식은 별도 프로세스라 함수를 공유할 수 없다. 고칠 때 둘 다 고칠 것)."""
    out = []
    if not os.path.exists(path):
        return out
    for line in open(path):
        if not line.strip(): continue
        rec = json.loads(line)
        # hero 와 full_log 는 레코드 **최상위**다 (rec['result'] 안이 아니다)
        hs = rec.get('hero')
        for e in (rec.get('full_log') or []):
            if hs is not None and e[1] == hs:
                out.append([rec.get('hand_no'), e[0], e[2], e[3]])
    return out


def run_http(entries, hands, seed, fast, keep):
    """ui_server 를 실제로 띄우고 HTTP 로 친다. 워커 프로세스까지 포함."""
    import socket, time
    tmp = tempfile.mkdtemp(prefix='t2_defer_http_')
    subprocess.run(['sh', SETUP, tmp], check=True, stdout=subprocess.DEVNULL)
    s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
    env = dict(os.environ, T2_UI_DEFER='1')
    env.setdefault('T2_BOT_LOG', '2')
    srv = subprocess.Popen([sys.executable, 'ui_server.py', '--port', str(port)],
                           cwd=tmp, env=env, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE)
    open(os.path.join(tmp, 'client.py'), 'w').write(HTTP_CLIENT)
    cenv = dict(os.environ, PORT=str(port), HANDS=str(hands), ENTRIES=str(entries),
                SEED=str(seed), FAST='1' if fast else '0')
    p = subprocess.run([sys.executable, 'client.py'], cwd=tmp, env=cenv,
                       capture_output=True, text=True)
    srv.terminate()
    try: srv.wait(timeout=10)
    except Exception: srv.kill()
    # 세션이 끝난 시점에 밀린 정산이 남아 있으면 **다음 접속 때** 처리된다
    # (live2.step 진입부). 비교하려면 그 '다음 접속'을 여기서 대신 해준다.
    # 이걸 안 하면 마지막 한 핸드만큼 적게 진행된 상태와 비교하게 된다.
    subprocess.run([sys.executable, '-c',
                    "import sys; sys.path.insert(0,'.');\n"
                    "import ui_view, live2 as L; sys.modules['view']=ui_view;\n"
                    "st=L.load();\n"
                    "L.resume_others(st) if st.get('others_pending') else None"],
                   cwd=tmp, env=env, capture_output=True)
    out = {}
    if p.returncode == 0 and p.stdout.strip():
        out = json.loads(p.stdout.strip().splitlines()[-1])
    else:
        out = {'error': (p.stderr or '')[-800:] + (srv.stderr.read().decode()[-800:]
                                                   if srv.stderr else '')}
    h = lambda f: (hashlib.sha256(open(os.path.join(tmp, f), 'rb').read()).hexdigest()
                   if os.path.exists(os.path.join(tmp, f)) else 'none')
    if 'error' not in out:
        stf = json.load(open(os.path.join(tmp, 'live2_state.json')))
        def integ(name):
            fp = os.path.join(tmp, name)
            if not os.path.exists(fp):
                return {'lines': 0, 'bad': 0, 'truncated': None, 'dup': 0}
            raw = open(fp, 'rb').read()
            ls = [x for x in raw.decode('utf-8', 'replace').split('\n') if x.strip()]
            bad = 0
            for x in ls:
                try: json.loads(x)
                except Exception: bad += 1
            return {'lines': len(ls), 'bad': bad,
                    'truncated': not raw.endswith(b'\n') if raw else False,
                    'dup': len(ls) - len(set(ls))}
        out.update({'archive': h('hand_archive2.jsonl'), 'bots': h('bot_hands.jsonl'),
                    'field': hashlib.sha256(json.dumps(stf['field'],
                                                       sort_keys=True).encode()).hexdigest(),
                    'rank': stf.get('rank'), 'busted': stf.get('busted'),
                    'busted_order': stf['field'].get('busted_order'),
                    'hero_actions': _hero_actions(os.path.join(tmp, 'hand_archive2.jsonl')),
                    'survivors': sorted(int(k) for k, v
                                        in (stf['field'].get('players') or {}).items()
                                        if v.get('stack', 0) > 0),
                    'arch_int': integ('hand_archive2.jsonl'),
                    'bots_int': integ('bot_hands.jsonl'),
                    'residue': {'others_pending': bool(stf.get('others_pending')),
                                'pending_archive': bool(stf.get('pending_archive')),
                                'pending_notes': bool(stf.get('pending_notes'))}})
    if not keep:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--hands', type=int, default=12)
    ap.add_argument('--seed', type=int, default=777)
    ap.add_argument('--keep', action='store_true')
    ap.add_argument('--http', action='store_true',
                    help='ui_server 를 실제로 띄워 워커 프로세스까지 검증')
    a = ap.parse_args()

    res = {}
    for mode in ('off', 'inline', 'worker'):
        res[mode] = run(mode, a.entries, a.hands, a.seed, a.keep)
        if 'error' in res[mode]:
            print('[%s] 실행 실패\n%s' % (mode, res[mode]['error']))
            return 1

    print('entries %d, seed %d, %d핸드\n' % (a.entries, a.seed, a.hands))
    keys = ('archive', 'bots', 'field', 'rank', 'busted', 'busted_order',
            'hero_actions', 'survivors', 'hands_played', 'busted_at')
    print('%-8s %-18s %-18s %-18s %-6s %s' % ('mode', 'archive', 'bot_hands', 'field', 'rank', 'busted'))
    for m in ('off', 'inline', 'worker'):
        r = res[m]
        print('%-8s %-18s %-18s %-18s %-6s %s'
              % (m, str(r['archive'])[:16], str(r['bots'])[:16],
                 str(r['field'])[:16], r['rank'], r['busted']))
    print()
    ok = True
    for m in ('inline', 'worker'):
        same = all(res[m][k] == res['off'][k] for k in keys)
        print('  off vs %-7s %s' % (m, '완전 일치' if same else '★불일치'))
        if not same:
            ok = False
            for k in keys:
                if res[m][k] != res['off'][k]:
                    print('     [%s] off=%s  %s=%s' % (k, res['off'][k], m, res[m][k]))
    if a.http:
        for fast, label in ((False, 'http'), (True, 'http즉시')):
            hr = run_http(a.entries, a.hands, a.seed, fast, a.keep)
            if 'error' in hr:
                print('  [%s] 실행 실패\n%s' % (label, hr['error'])); ok = False; continue
            same = all(hr[k] == res['off'][k] for k in keys)
            print('  off vs %-7s %s   %s'
                  % (label, '완전 일치' if same else '★불일치', hr['stats']['counters']))
            if not same:
                ok = False
                for k in keys:
                    if hr[k] != res['off'][k]:
                        print('     [%s] off=%s  %s=%s' % (k, res['off'][k], label, hr[k]))
            print('     로그: archive %d줄(깨짐 %d, 중복 %d, 잘림 %s)  bot_hands %d줄(깨짐 %d, 중복 %d, 잘림 %s)  잔여 %s'
                  % (hr['arch_int']['lines'], hr['arch_int']['bad'], hr['arch_int']['dup'],
                     hr['arch_int']['truncated'], hr['bots_int']['lines'], hr['bots_int']['bad'],
                     hr['bots_int']['dup'], hr['bots_int']['truncated'],
                     {k: v for k, v in hr['residue'].items() if v} or '없음'))
            if hr['arch_int']['bad'] or hr['bots_int']['bad'] or hr['arch_int']['truncated'] \
               or hr['bots_int']['truncated'] or any(hr['residue'].values()):
                ok = False
            if hr['stats']['counters'].get('hit', 0) == 0 and not fast:
                print('     ★ hit 가 0 이다 — 워커가 실제로 쓰이지 않았다'); ok = False
    print()
    print('  로그 무결성 / pending 잔여')
    for m in ('off', 'inline', 'worker'):
        r = res[m]
        print('    [%-6s] archive %d줄(깨짐 %d, 중복 %d, 잘림 %s)  bot_hands %d줄(깨짐 %d, 중복 %d, 잘림 %s)  잔여 %s'
              % (m, r['arch_int']['lines'], r['arch_int']['bad'], r['arch_int']['dup'],
                 r['arch_int']['truncated'], r['bots_int']['lines'], r['bots_int']['bad'],
                 r['bots_int']['dup'], r['bots_int']['truncated'],
                 {k: v for k, v in r['residue'].items() if v} or '없음'))
        if r['arch_int']['bad'] or r['bots_int']['bad'] or r['arch_int']['truncated'] \
           or r['bots_int']['truncated'] or any(r['residue'].values()):
            ok = False
    print()
    for m in ('off', 'inline', 'worker'):
        print('  [%s] %s' % (m, res[m]['counters']))
    w = res['worker']['counters']
    if w.get('hit', 0) == 0:
        print('\n★ worker 모드에서 hit 가 0 이다. 일치해도 최적화가 작동하지 않은 것이다.')
        ok = False
    print('\n판정: %s' % ('통과' if ok else '실패'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
