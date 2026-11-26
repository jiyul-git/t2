#!/usr/bin/env python3
"""연구실 자동 계산·판단 봇(lab autopilot). 계산·기록만, GTO 결과를 봇 런타임에 연결하지 않는다.

  python3 autopilot.py run [--dry]      # 계속 돈다(무인). --dry 또는 LAB_DRY=1: 풀지 않고 할 일만 기록, FT_NO_PUSH=1: 아무것도 푸시 안 함
  python3 autopilot.py once [--dry]     # 한 번만 보고(깃허브 읽기 → 할 일 계획 출력)
  python3 autopilot.py status           # 마지막 상태 파일 출력
  python3 autopilot.py judge <스택> <단계> [--local <data/ft<스택> 가 있는 폴더>]   # 판정표 출력
  python3 autopilot.py claim <스택> <단계> <단위> [--owner 이름]   # 공용 claim(다른 계정·클라우드 세션용). 단위: board_<n> | coord_<단계이름>
  python3 autopilot.py release <스택> <단계> <단위>

설계·기준 표: docs/LAB_AUTOPILOT.md. 설정: config.json(+ $HOME/t2lab/config.local.json 으로 덮어쓰기).
"""
import copy
import csv
import datetime as dt
import glob
import gzip
import hashlib
import io
import json
import logging
import logging.handlers
import os
import random
import re
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import judge as J  # noqa: E402

EMPTY_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'


# ----------------------------------------------------------------------------- 설정
def deep_merge(a, b):
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            deep_merge(a[k], v)
        else:
            a[k] = v
    return a


def load_config(extra=None):
    cfg = json.load(open(os.path.join(HERE, 'config.json')))
    root = os.path.expanduser(os.path.expandvars(cfg['root']))
    for p in (os.path.join(root, 'config.local.json'), extra or os.environ.get('LAB_CONFIG')):
        if p and os.path.exists(p):
            deep_merge(cfg, json.load(open(p)))
    cfg['root'] = os.path.expanduser(os.path.expandvars(cfg['root']))
    for k in ('repo', 'calc', 'work'):
        cfg[k] = os.path.expanduser(os.path.expandvars(cfg[k]))
    for sc in cfg['stacks'].values():       # 판정 설정: 공통 + 스택별
        sc['judge'] = dict(cfg.get('judge', {}), **sc.get('judge', {}))
    return cfg


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(t=None):
    return (t or now()).strftime('%Y-%m-%dT%H:%M:%SZ')


def age_h(ts):
    """epoch 초 또는 ISO 문자열 → 지금까지 시간(시간)."""
    if isinstance(ts, str):
        ts = dt.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc).timestamp()
    return (time.time() - ts) / 3600.0


log = logging.getLogger('lab')


def setup_log(root):
    os.makedirs(os.path.join(root, 'logs'), exist_ok=True)
    log.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s %(message)s', '%m-%d %H:%M:%S')
    fh = logging.handlers.RotatingFileHandler(os.path.join(root, 'logs', 'autopilot.log'), maxBytes=5_000_000, backupCount=5)
    sh = logging.StreamHandler(sys.stdout)
    for h in (fh, sh):
        h.setFormatter(fmt)
        log.addHandler(h)


# ----------------------------------------------------------------------------- git 도우미
class Git:
    """한 저장소에 대한 git 호출(출력 문자열/바이트). 실패해도 예외 대신 returncode 로."""

    def __init__(self, path, env=None, timeout=600):
        self.path, self.env, self.timeout = path, env or {}, timeout

    def run(self, *a, check=False, raw=False, timeout=None, env=None, input=None):
        e = dict(os.environ, GIT_TERMINAL_PROMPT='0', **self.env, **(env or {}))
        try:
            p = subprocess.run(['git', '-C', self.path, *a], capture_output=True, env=e, timeout=timeout or self.timeout, input=input)
        except subprocess.TimeoutExpired:
            class P:
                returncode, stdout, stderr = 124, b'', b'timeout'
            p = P()
        if check and p.returncode != 0:
            raise RuntimeError('git %s 실패: %s' % (' '.join(a[:3]), p.stderr.decode(errors='replace')[-300:]))
        if raw:
            return p
        p.out = p.stdout.decode(errors='replace').strip()
        p.err = p.stderr.decode(errors='replace').strip()
        return p


def with_retry(fn, tries=4, base=2):
    for i in range(tries):
        r = fn()
        if r.returncode == 0:
            return r
        time.sleep(base ** (i + 1) + random.random())
    return r


# ----------------------------------------------------------------------------- 공용 작업판: 깃허브 읽기(peek) + claim + 상태 브랜치
class Hub:
    """깃허브 쪽 전부. peek = 읽기 전용 얕은·부분 저장소(주 저장소의 얕은 이력 오염 방지), wt = claim/상태 브랜치용 작업 폴더."""

    def __init__(self, cfg, push_enabled):
        self.cfg, self.push = cfg, push_enabled
        self.root = cfg['root']
        self.url = Git(cfg['repo']).run('remote', 'get-url', 'origin').out or cfg.get('origin_url')
        self.peek = Git(os.path.join(self.root, 'peek'))
        self.cr = Git(os.path.join(self.root, 'coordrepo'))       # 조정 브랜치 푸시용(자기 소유 저장소)
        self.lock = threading.RLock()
        self.me = cfg['owner']
        self.claims_br = cfg['branches']['claims']
        self.status_br = cfg['branches']['status']
        self.seen = {}
        self.genv = {'GIT_AUTHOR_NAME': cfg['git_user'], 'GIT_COMMITTER_NAME': cfg['git_user'], 'GIT_AUTHOR_EMAIL': cfg['git_email'], 'GIT_COMMITTER_EMAIL': cfg['git_email']}
        self.cr.env = self.peek.env = self.genv
        self._init_repos()

    def _init_repos(self):
        os.makedirs(self.root, exist_ok=True)
        if not os.path.isdir(os.path.join(self.peek.path, 'objects')):
            os.makedirs(self.peek.path, exist_ok=True)
            self.peek.run('init', '-q', '--bare', check=True)
            self.peek.run('remote', 'add', 'origin', self.url)
        self.peek.run('config', 'remote.origin.promisor', 'true')
        self.peek.run('config', 'remote.origin.partialclonefilter', 'blob:none')
        self.peek.run('config', 'extensions.partialClone', 'origin')
        if not os.path.isdir(os.path.join(self.cr.path, '.git')):
            Git(self.root).run('clone', '-q', '--no-checkout', self.url, self.cr.path)
        if self.cfg.get('partial_fetch', True):     # collect 가 보드 브랜치를 얕게 가져올 때 전략 묶음(strategy_*.tgz, 큼)은 받지 않고 필요한 파일만 그때그때
            self.cr.run('config', 'remote.origin.promisor', 'true')
            self.cr.run('config', 'remote.origin.partialclonefilter', 'blob:none')
            self.cr.run('config', 'extensions.partialClone', 'origin')
        self.cr.run('config', 'user.name', self.cfg['git_user'])
        self.cr.run('config', 'user.email', self.cfg['git_email'])

    # --- 읽기
    def remote_heads(self, patterns):
        r = self.peek.run('ls-remote', 'origin', *patterns, timeout=120)
        if r.returncode != 0:
            raise RuntimeError('ls-remote 실패: ' + r.err[-200:])
        return {l.split()[1].replace('refs/heads/', ''): l.split()[0] for l in r.out.splitlines() if l.strip()}

    def fetch(self, br, force=False):
        """br 를 peek 에 얕게 가져와 origin/<br> 로 둔다(sha 가 같으면 건너뜀). 성공 시 sha."""
        want = self.heads.get(br)
        if want is None:
            return None
        if not force and self.seen.get(br) == want:
            return want
        r = with_retry(lambda: self.peek.run('fetch', '-q', '--depth=1', '--filter=blob:none', 'origin', '+refs/heads/%s:refs/remotes/origin/%s' % (br, br), timeout=300), 3)
        if r.returncode != 0:
            r = with_retry(lambda: self.peek.run('fetch', '-q', '--depth=1', 'origin', '+refs/heads/%s:refs/remotes/origin/%s' % (br, br), timeout=300), 2)
        if r.returncode != 0:
            log.info('가져오기 실패 %s: %s', br, r.err[-150:])
            return None
        self.seen[br] = want
        return want

    def ls(self, br, prefix):
        r = self.peek.run('ls-tree', '-r', '--name-only', 'origin/' + br, prefix)
        return r.out.split('\n') if r.returncode == 0 and r.out else []

    def show(self, br, path):
        r = self.peek.run('show', 'origin/%s:%s' % (br, path), raw=True)
        return r.stdout if r.returncode == 0 else None

    def tip_time(self, br):
        r = self.peek.run('log', '-1', '--format=%ct', 'origin/' + br)
        return int(r.out) if r.returncode == 0 and r.out else None

    def refresh_heads(self, stacks):
        pats = ['refs/heads/' + self.claims_br, 'refs/heads/' + self.status_br]
        for S, sc in stacks.items():
            pats += ['refs/heads/claude/ft%s_board_*' % S, 'refs/heads/' + sc['coord_branch']]
        self.heads = self.remote_heads(pats)
        return self.heads

    # --- 고아 브랜치(claim, 상태)용 작업 폴더. 고아는 plumbing 으로 만든다(git 2.34 에는 worktree add --orphan 이 없음)
    def _sync_branch(self, br, name):
        """고아 브랜치 br 의 로컬 작업 폴더(분리 HEAD)를 원격 끝에 맞춘다. 원격에 없으면 빈 커밋을 만들어 푸시. 작업 폴더 경로."""
        wt = os.path.join(self.root, name)
        g = Git(wt, env=self.genv)
        r = with_retry(lambda: self.cr.run('fetch', '-q', 'origin', '+refs/heads/%s:refs/remotes/origin/%s' % (br, br)), 2)
        have_remote = self.cr.run('rev-parse', '-q', '--verify', 'refs/remotes/origin/' + br).returncode == 0
        if not os.path.isdir(wt):
            if have_remote:
                self.cr.run('worktree', 'add', '-q', '--detach', wt, 'origin/' + br, check=True)
            else:
                c = self.cr.run('commit-tree', EMPTY_TREE, '-m', 'init ' + br, check=True).out
                self.cr.run('worktree', 'add', '-q', '--detach', wt, c, check=True)
                g.run('update-ref', 'refs/lab/' + name, c)
        elif have_remote:
            g.run('reset', '-q', '--hard', 'origin/' + br)
        return wt, g, have_remote

    def _commit_push(self, wt, g, br, msg, have_remote):
        g.run('add', '-A')
        if g.run('diff', '--cached', '--quiet').returncode == 0:
            return True
        g.run('commit', '-q', '-m', msg, check=True)
        if not self.push:
            return True
        r = g.run('push', '-q', 'origin', 'HEAD:refs/heads/' + br, timeout=120)
        return r.returncode == 0

    def mutate(self, br, name, fn, msg, tries=8):
        """원격 끝에서 시작해 fn(작업폴더) 로 파일을 바꾸고 푸시. 거절(다른 쪽이 먼저 푸시)되면 다시 읽고 fn 을 다시 — 원자성."""
        with self.lock:
            for i in range(tries):
                wt, g, have = self._sync_branch(br, name)
                res = fn(wt)
                if res is False:
                    return False
                if not self.push:
                    # 푸시 안 하는 시험 모드: 로컬에만 커밋(다음 동기화 때 되돌려지지 않게 원격 대신 로컬 기록 유지)
                    g.run('add', '-A'); g.run('commit', '-q', '-m', msg)
                    return res if res is not None else True
                if self._commit_push(wt, g, br, msg, have):
                    return res if res is not None else True
                time.sleep(1 + random.random() * 2 * (i + 1))
            return False

    # --- claim
    def claim_path(self, S, k, unit):
        return 'claims/ft%s/step%s/%s.json' % (S, k, unit)

    def read_claims(self):
        """모든 claim 파일 → {(S,k,unit): dict}. peek 로 읽는다."""
        out = {}
        if self.claims_br not in self.heads or not self.fetch(self.claims_br):
            return out
        for p in self.ls(self.claims_br, 'claims'):
            m = re.match(r'claims/ft(\d+)/step(\d+)/(.+)\.json$', p)
            b = self.show(self.claims_br, p) if m else None
            if b:
                try:
                    out[(m.group(1), int(m.group(2)), m.group(3))] = json.loads(b)
                except ValueError:
                    pass
        return out

    def claim(self, S, k, unit, owner=None, note='', ttl_h=3.0):
        """claim 시도. True = 내 것(새로 잡았거나 이미 내 것), False = 남이 잡고 있음(하트비트 ttl 안)."""
        owner = owner or self.me
        path = self.claim_path(S, k, unit)

        def fn(wt):
            f = os.path.join(wt, path)
            if os.path.exists(f):
                cur = json.load(open(f))
                if cur.get('owner') != owner and age_h(cur.get('t_heartbeat', cur.get('t_claim'))) < ttl_h:
                    return False
                if cur.get('owner') != owner:
                    note_ = 'takeover of %s' % cur.get('owner')
                else:
                    note_ = note
            else:
                note_ = note
            os.makedirs(os.path.dirname(f), exist_ok=True)
            json.dump({'owner': owner, 'host': socket.gethostname(), 'stack': S, 'step': k, 'unit': unit, 't_claim': iso(), 't_heartbeat': iso(), 'note': note_},
                      open(f, 'w'), indent=1)
            return True
        r = self.mutate(self.claims_br, 'claims_wt', fn, 'claim ft%s step%s %s by %s' % (S, k, unit, owner))
        return bool(r)

    def heartbeat(self, mine):
        """내 claim 들의 t_heartbeat 를 한 커밋으로 갱신. mine = [(S,k,unit)]"""
        if not mine:
            return

        def fn(wt):
            ch = False
            for S, k, unit in mine:
                f = os.path.join(wt, self.claim_path(S, k, unit))
                if os.path.exists(f):
                    d = json.load(open(f))
                    if d.get('owner') == self.me:
                        d['t_heartbeat'] = iso()
                        json.dump(d, open(f, 'w'), indent=1)
                        ch = True
            return None if ch else False
        self.mutate(self.claims_br, 'claims_wt', fn, 'heartbeat %s' % self.me)

    def release(self, S, k, unit, owner=None):
        owner = owner or self.me

        def fn(wt):
            f = os.path.join(wt, self.claim_path(S, k, unit))
            if os.path.exists(f) and json.load(open(f)).get('owner') == owner:
                os.remove(f)
                return True
            return False
        return self.mutate(self.claims_br, 'claims_wt', fn, 'release ft%s step%s %s by %s' % (S, k, unit, owner))

    # --- 상태 하트비트
    def push_status(self, files):
        def fn(wt):
            for name, data in files.items():
                p = os.path.join(wt, name)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, 'w').write(data)
            return True
        return self.mutate(self.status_br, 'status_wt', fn, 'status %s' % iso())

    # --- 조정 브랜치 푸시(자기 저장소 coordrepo 의 작업 폴더에서). force 없음
    def push_coord(self, wt, br, msg, paths):
        """wt 의 paths 를 커밋하고 br 로 푸시. 거절되면 원격을 병합한 뒤 다시(최대 5번). 충돌이면 False."""
        g = Git(wt, env=self.genv)
        for p in paths:
            g.run('add', '-f', '--', p)
        if g.run('diff', '--cached', '--quiet').returncode != 0:
            g.run('commit', '-q', '-m', msg + '\n\nClaude-Session: https://claude.ai/code/lab-autopilot', check=True)
        if not self.push:
            return True
        for i in range(5):
            r = g.run('push', '-q', 'origin', 'HEAD:refs/heads/' + br, timeout=300)
            if r.returncode == 0:
                return True
            with_retry(lambda: g.run('fetch', '-q', 'origin', '+refs/heads/%s:refs/remotes/origin/%s' % (br, br)), 3)
            m = g.run('merge', '-q', '--no-edit', 'origin/' + br)
            if m.returncode != 0:
                g.run('merge', '--abort')
                log.info('조정 브랜치 병합 충돌 %s: %s', br, m.err[-200:])
                return False
        return False


# ----------------------------------------------------------------------------- 스택 상태 읽기(조정 브랜치)
class Evidence:
    """판정에 필요한 파일을 읽는 얇은 층. read(path)->bytes|None, files = 경로 집합. 조정 브랜치(peek)나 로컬 폴더."""

    def __init__(self, S, read, files):
        self.S, self.read, self.files = str(S), read, set(files)

    def has(self, rel):
        return 'data/ft%s/%s' % (self.S, rel) in self.files

    def js(self, rel):
        b = self.read('data/ft%s/%s' % (self.S, rel))
        return json.loads(b) if b else None

    def tsv(self, rel):
        b = self.read('data/ft%s/%s' % (self.S, rel))
        return list(csv.DictReader(io.StringIO(b.decode()), delimiter='\t')) if b else None

    def steps(self):
        return sorted({int(m.group(1)) for p in self.files for m in [re.match(r'data/ft%s/step(\d+)/' % self.S, p)] if m})


def local_evidence(S, folder):
    base = os.path.join(folder, 'data/ft%s' % S)
    files = [os.path.relpath(os.path.join(d, f), folder) for d, _, fs in os.walk(base) for f in fs] if os.path.isdir(base) else []

    def read(p):
        try:
            return open(os.path.join(folder, p), 'rb').read()
        except OSError:
            return None
    return Evidence(S, read, files)


def evaluate(ev, k, jcfg):
    """step k 판정: 조정 브랜치(또는 로컬)의 파일만으로. collect 보고서가 없으면 None."""
    rep = ev.js('step%d/collect/report.json' % k)
    if not rep:
        return None
    rows = ev.tsv('step%d/bundles.tsv' % k) or []
    node_of = {r['bundle']: int(r['node']) for r in rows}
    dec = ev.js('step%d/flop_failure_decision.json' % k) or {}
    fl = []
    for b, boards in rep.get('flop_failures_after_retry') or []:
        for x in boards:
            d = (dec.get('boards') or {}).get('%s/%s' % (b, x)) or {}
            fl.append({'bundle': b, 'board': x, 'retry_pct_pot': d.get('retry_pct_pot'), 'node': node_of.get(b)})
    solve = None
    fn = ev.read('data/ft%s/step%d/solve/final_n' % (ev.S, k))
    if fn:
        ex = ev.js('step%d/solve/exact_%d.json' % (k, int(fn.decode().strip())))
        solve = {'final_n': int(fn.decode().strip()), 'exact_gap': ex['gap_total'] if ex else None}
    pm = ev.js('step%d/prepare.json' % k) or {}
    prev_rows = ev.tsv('step%d/bundles.tsv' % (k - 1)) if k > 0 else None
    ns = J.new_endpoint_share(rows, prev_rows, pm.get('hu_mass')) if rows else None
    prevs = [r for r in (ev.js('step%d/collect/report.json' % i) for i in range(0, k)) if r]
    root = ev.js('step%d/root_replication.json' % k)
    v = J.judge(rep, step=k, history=ev.js('history.json') or {}, prev_reports=prevs, flop={'failures': fl}, solve=solve, endpoint={'new_share': ns}, root=root, cfg=jcfg)
    return v


class StackView:
    def __init__(self, S):
        self.S, self.K, self.phase, self.why = S, None, 'none', ''
        self.boards = {}      # n -> dict(bundles={b:state}, tip_age_h, sha, status)
        self.verdict = None
        self.last_commit_age_h = None


def read_stack(hub, S, sc, claims):
    sv = StackView(S)
    br = sc['coord_branch']
    if br not in hub.heads or not hub.fetch(br):
        sv.phase, sv.why = 'no_coord', '조정 브랜치를 못 읽음'
        return sv
    files = hub.ls(br, 'data/ft%s' % S)
    ev = Evidence(S, lambda p: hub.show(br, p), files)
    ct = hub.tip_time(br)
    sv.last_commit_age_h = age_h(ct) if ct else None
    sv.ev = ev
    steps = ev.steps()
    if not steps:
        sv.phase, sv.why = 'none', 'data/ft%s 에 단계가 없음' % S
        return sv
    K = sv.K = steps[-1]
    has = ev.has
    if has('step%d/collect/report.json' % K):
        sv.verdict = evaluate(ev, K, sc['judge'])
    if sv.verdict and sv.verdict['status'] != 'wait_boards':
        st = sv.verdict['status']
        if st in ('converged', 'values_pass_pending_root', 'stop_report'):
            sv.phase, sv.why = 'halted', '%s: %s' % (st, '; '.join(sv.verdict['reasons']))
        else:
            sv.phase, sv.why = 'next_tables', '단계 %d 판정 continue → 단계 %d 표 만들기' % (K, K + 1)
        return sv
    if has('step%d/bundles.tsv' % K) and has('step%d/assign.tsv' % K) and has('step%d/prepare.json' % K):
        sv.phase = 'boards'
        assign = ev.tsv('step%d/assign.tsv' % K)
        per = {}
        for r in assign:
            per.setdefault(int(r['session']), []).append(r['bundle'])
        for n, bl in sorted(per.items()):
            bb = 'claude/ft%s_board_%s' % (S, n)
            info = {'branch': bb, 'bundles': {}, 'exists': bb in hub.heads, 'tip_age_h': None, 'sha': hub.heads.get(bb)}
            if info['exists'] and hub.fetch(bb):
                fs = hub.ls(bb, 'data/ft%s/results/step%d' % (S, K))
                t = hub.tip_time(bb)
                info['tip_age_h'] = age_h(t) if t else None
                for b in bl:
                    mine = [p for p in fs if '/%s/' % b in p]
                    info['bundles'][b] = 'done' if any(p.endswith('/%s/done.json' % b) for p in mine) else ('partial' if mine else 'none')
            else:
                info['bundles'] = {b: 'none' for b in bl}
            info['all_done'] = all(s == 'done' for s in info['bundles'].values())
            sv.boards[n] = info
        nd = sum(1 for b in sv.boards.values() if b['all_done'])
        sv.why = '보드 번호 %d/%d 끝' % (nd, len(sv.boards))
        if nd == len(sv.boards):
            sv.phase, sv.why = 'collect', '묶음 전부 끝 → collect'
        return sv
    if has('step%d/solve/final_n' % K) and has('step%d/solve/dump.jsonl.gz' % K):
        sv.phase, sv.why = 'prepare', '단계 %d 풀이는 있음, prepare 없음' % K
    elif has('step%d/tables/manifest.json' % K):
        sv.phase, sv.why = 'solve', '단계 %d 표는 있음, 트리 풀이 없음' % K
    else:
        sv.phase, sv.why = 'none', '단계 %d 입력 없음(표·풀이·prepare 전부 없음)' % K
    return sv


def board_free(hub, cfg, sv, n, claims, local_branches):
    """보드 n 을 연구실이 잡아도 되는가. (가능?, 이유)"""
    b = sv.boards[n]
    L = cfg['loop']
    if b['all_done']:
        return False, '끝남'
    c = claims.get((sv.S, sv.K, 'board_%d' % n))
    if c and c.get('owner') != hub.me and age_h(c.get('t_heartbeat', c['t_claim'])) < L['claim_ttl_hours']:
        return False, '다른 쪽이 claim(%s)' % c.get('owner')
    mine = (c and c.get('owner') == hub.me) or b['branch'] in local_branches
    partial = any(s == 'partial' for s in b['bundles'].values())
    started_other = (partial or any(s == 'done' for s in b['bundles'].values())) and not mine
    tip = b['tip_age_h']
    if not mine and tip is not None and tip < L['active_hours']:
        return False, '그 브랜치에 %.1f시간 전 푸시(다른 쪽 작업 중)' % tip
    if started_other and (tip is None or tip < L['stale_takeover_hours']):
        return False, '다른 쪽이 시작함(부분 푸시, 마지막 %.0f시간 전)' % (tip if tip is not None else -1)
    return True, ('이어서(내 것)' if mine else ('인계(남의 것 %.0f시간 멈춤)' % tip if started_other else '새로'))


# ----------------------------------------------------------------------------- 실행 환경
class Env:
    def __init__(self, cfg):
        self.cfg = cfg
        c = cfg['cpu']
        self.nice = ['nice', '-n', str(c['nice'])]
        # WSL 1 은 ionice 가 'Function not implemented' 로 실패하면 명령을 안 돌린다 → 먼저 시험해서 되는 경우에만 붙인다
        if shutil.which('ionice') and subprocess.run(['ionice', '-c', str(c['ionice_class']), 'true'], capture_output=True).returncode == 0:
            self.nice = ['ionice', '-c', str(c['ionice_class'])] + self.nice
        self.py = cfg['py311'] if os.path.exists(cfg['py311']) else os.path.join(cfg['root'], 'py311/bin/python')
        self.calc = cfg['calc']
        for cand in (self.calc, os.path.expanduser('~/calc'), os.path.join(cfg['root'], 'calc')):
            if os.path.exists(os.path.join(cand, 'vendor/gtopen/target/release/examples/t2_cont_panel')):
                self.calc = cand
                break

    def base(self, S, extra=None, threads=1):
        e = dict(os.environ, FT_STACK=str(S), FT_CALC=self.calc, FT_SESSION='lab', RAYON_NUM_THREADS=str(threads),
                 OMP_NUM_THREADS='1', GIT_AUTHOR_NAME=self.cfg['git_user'], GIT_COMMITTER_NAME=self.cfg['git_user'],
                 GIT_AUTHOR_EMAIL=self.cfg['git_email'], GIT_COMMITTER_EMAIL=self.cfg['git_email'], GIT_TERMINAL_PROMPT='0')
        e.update({k: str(v) for k, v in (extra or {}).items()})
        return e

    def work(self, S, tag=''):
        return os.path.join(self.cfg['work'], 'ft%s%s' % (S, tag))


PGID_DIR = [None]


def runlog(cmd, cwd, env, logfile, timeout=None):
    """로그에 덧붙여 실행. 종료 코드. 프로세스 그룹 번호를 state/pgids/ 에 적어 둔다(봇이 죽어도 다음 시작 때 정리)."""
    os.makedirs(os.path.dirname(logfile), exist_ok=True)
    with open(logfile, 'a') as f:
        f.write('\n=== %s %s\n' % (iso(), ' '.join(cmd)))
        f.flush()
        p = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, start_new_session=True)
        mark = os.path.join(PGID_DIR[0], str(p.pid)) if PGID_DIR[0] else None
        if mark:
            open(mark, 'w').write(' '.join(cmd)[:300])
        try:
            return p.wait(timeout=timeout)
        except BaseException:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except OSError:
                pass
            raise
        finally:
            if mark and os.path.exists(mark):
                os.remove(mark)


def kill_leftovers():
    """이전 봇이 남긴 계산(프로세스 그룹)을 끈다 — 같은 묶음을 두 번 돌리지 않도록. 끝난 덩어리는 이미 푸시돼 있어 이어서 된다."""
    d = PGID_DIR[0]
    for f in glob.glob(os.path.join(d, '*')):
        pid = int(os.path.basename(f))
        try:
            os.killpg(pid, signal.SIGTERM)
            log.info('이전 실행이 남긴 계산 정리: pgid %d', pid)
        except OSError:
            pass
        os.remove(f)


# ----------------------------------------------------------------------------- 일(스레드)
class Job(threading.Thread):
    def __init__(self, ap, kind, S, k, unit, fn, cost):
        super().__init__(daemon=True)
        self.ap, self.kind, self.S, self.k, self.unit, self.fn, self.cost = ap, kind, S, k, unit, fn, cost
        self.key = (str(S), k, unit)
        self.started = iso()
        self.result = None
        self.err = ''
        self.progress = ''

    def run(self):
        try:
            self.result = self.fn(self)
        except Exception as e:      # noqa
            self.result, self.err = 'error', '%s: %s' % (type(e).__name__, e)
            log.exception('일 실패 %s', self.key)


class Autopilot:
    def __init__(self, cfg, dry=False):
        self.cfg = cfg
        self.dry = dry or bool(os.environ.get('LAB_DRY'))
        self.no_push = os.environ.get('FT_NO_PUSH') == '1' or self.dry
        self.root = cfg['root']
        for d in ('logs', 'work', 'state'):
            os.makedirs(os.path.join(self.root, d), exist_ok=True)
        setup_log(self.root)
        PGID_DIR[0] = os.path.join(self.root, 'state/pgids')
        os.makedirs(PGID_DIR[0], exist_ok=True)
        self.hub = Hub(cfg, push_enabled=not self.no_push)
        self.env = Env(cfg)
        self.repo = Git(cfg['repo'], env=self.hub.genv)
        self.jobs = {}
        self.state = self._load_state()
        self.view, self.claims = {}, {}
        self.t_refresh = self.t_status = self.t_hb = 0
        self.errors = []
        self.t0 = time.time()
        self.update_pending_since = None
        self.test_boards = os.environ.get('FT_TEST_BOARDS')
        self.repo_lock = threading.RLock()

    # --- 상태 파일
    def _load_state(self):
        p = os.path.join(self.root, 'state/state.json')
        try:
            return json.load(open(p))
        except (OSError, ValueError):
            return {'fails': {}, 'blocked': {}}

    def _save_state(self):
        p = os.path.join(self.root, 'state/state.json')
        json.dump(self.state, open(p + '.tmp', 'w'), indent=1)
        os.replace(p + '.tmp', p)

    # --- 읽기: 깃허브 → 스택별 보기
    def refresh(self):
        stacks = {S: sc for S, sc in self.cfg['stacks'].items() if sc.get('enabled')}
        self.hub.refresh_heads(stacks)
        self.claims = self.hub.read_claims()
        self.view = {}
        for S, sc in sorted(stacks.items(), key=lambda kv: kv[1]['priority']):
            try:
                self.view[S] = read_stack(self.hub, S, sc, self.claims)
            except Exception as e:      # noqa
                sv = StackView(S)
                sv.phase, sv.why = 'error', '%s: %s' % (type(e).__name__, e)
                self.view[S] = sv
                log.exception('스택 %s 읽기 실패', S)
        self.t_refresh = time.time()

    def local_board_branches(self):
        r = self.repo.run('for-each-ref', '--format=%(refname:short)', 'refs/heads/claude/')
        return set(r.out.split()) if r.returncode == 0 else set()

    # --- 계획
    def candidates(self):
        """연구실이 지금 시작할 수 있는 일 목록(우선순위 순). 각 항목 = (S,k,kind,unit,reason)"""
        out = []
        lb = self.local_board_branches()
        L = self.cfg['loop']
        for S, sv in sorted(self.view.items(), key=lambda kv: self.cfg['stacks'][kv[0]]['priority']):
            sc = self.cfg['stacks'][S]
            if sv.phase in ('none', 'no_coord', 'error', 'halted'):
                continue
            if sv.phase in ('solve', 'prepare', 'collect', 'next_tables'):
                if not sc.get('coord_actions'):
                    continue
                if sv.last_commit_age_h is not None and sv.last_commit_age_h < L['coord_idle_hours']:
                    continue          # 조정 세션이 방금 푸시함 — 작업 중일 수 있어 기다림
                unit = 'coord_%s' % sv.phase
                out.append((S, sv.K, 'coord', unit, sv.why))
            elif sv.phase == 'boards' and sc.get('boards', True):
                for n in sorted(sv.boards):
                    ok, why = board_free(self.hub, self.cfg, sv, n, self.claims, lb)
                    if ok:
                        out.append((S, sv.K, 'board', 'board_%d' % n, why))
        return out

    def running_cost(self):
        return sum(j.cost for j in self.jobs.values() if j.is_alive())

    def blocked(self, key):
        t = self.state['blocked'].get('|'.join(map(str, key)))
        return t and time.time() < t

    def schedule(self):
        c = self.cfg['cpu']
        cap = c['total_cores']
        free_gb = shutil.disk_usage(self.cfg['work']).free / 2**30 if os.path.isdir(self.cfg['work']) else 999
        if free_gb < self.cfg['disk']['min_free_gb']:
            log.info('디스크 여유 %.1fGB < %d — 새 일 시작 안 함(정리 시도)', free_gb, self.cfg['disk']['min_free_gb'])
            self.cleanup(aggressive=True)
            return
        if self.update_pending_since:
            return
        plan = self.candidates()
        started = 0
        nboards = sum(1 for j in self.jobs.values() if j.kind == 'board' and j.is_alive())
        for S, k, kind, unit, why in plan:
            key = (str(S), k, unit)
            if key in self.jobs and self.jobs[key].is_alive():
                continue
            if self.blocked(key):
                continue
            cost = c['workers_per_board'] if kind == 'board' else c['coord_threads']
            if kind == 'board' and nboards >= c['boards_parallel']:
                continue
            if self.running_cost() + cost > cap:
                continue
            if self.dry:
                log.info('(시험) 시작할 일: 스택 %s 단계 %s %s — %s', S, k, unit, why)
                self.jobs[key] = type('D', (), {'is_alive': lambda s: False, 'kind': kind, 'cost': 0})()
                continue
            if not self.hub.claim(S, k, unit, note=why, ttl_h=self.cfg['loop']['claim_ttl_hours']):
                log.info('claim 실패(남이 잡음): %s', key)
                continue
            fn = {'board': self.job_board, 'coord': self.job_coord}[kind]
            j = Job(self, kind, S, k, unit, fn, cost)
            self.jobs[key] = j
            j.start()
            nboards += kind == 'board'
            started += 1
            log.info('시작: 스택 %s 단계 %s %s (%s)', S, k, unit, why)
        return started

    def reap(self):
        for key, j in list(self.jobs.items()):
            if hasattr(j, 'is_alive') and not j.is_alive() and isinstance(j, Job):
                self.hub.release(*key) if not self.no_push else None
                k = '|'.join(map(str, key))
                if j.result == 'ok':
                    self.state['fails'].pop(k, None)
                    if j.kind == 'coord':      # 같은 조정 일을 곧바로 되풀이하지 않는다(결과가 안 바뀌는 경우 무한 반복 방지)
                        self.state['blocked'][k] = time.time() + 6 * 3600
                    log.info('끝: %s', key)
                else:
                    n = self.state['fails'].get(k, 0) + 1
                    self.state['fails'][k] = n
                    wait = [300, 900, 3600, 10800, 43200][min(n - 1, 4)]
                    self.state['blocked'][k] = time.time() + wait
                    self.errors.append({'t': iso(), 'key': k, 'result': j.result, 'err': j.err[-300:], 'fails': n, 'retry_in_min': wait // 60})
                    self.errors = self.errors[-20:]
                    log.info('실패(%d번째) %s: %s %s — %d분 뒤 다시', n, key, j.result, j.err[-120:], wait // 60)
                del self.jobs[key]
                self._save_state()
            elif not isinstance(j, Job):
                del self.jobs[key]

    # --- 보드 일: lab_ft.sh run_board 와 같은 작업 폴더·병합·재시작 규칙 + nice + 재시도 제한 래퍼
    def board_worktree(self, S, n, sc):
        br = 'claude/ft%s_board_%s' % (S, n)
        coord = 'claude/ft%s_coord' % S if not sc else sc['coord_branch']
        R = self.repo
        with self.repo_lock:
            for _ in range(4):
                if with_retry(lambda: R.run('fetch', '-q', 'origin', '+refs/heads/%s:refs/remotes/origin/%s' % (coord, coord)), 1).returncode == 0:
                    break
                time.sleep(3)
            here = None
            r = R.run('worktree', 'list', '--porcelain')
            w = None
            for l in r.out.splitlines():
                if l.startswith('worktree '):
                    w = l[9:]
                if l == 'branch refs/heads/' + br:
                    here = w
            legacy = os.path.join(self.root, 'b%s' % n)       # lab_ft.sh 가 만든 폴더(30bb)
            W = here or (legacy if S == '30' and os.path.isdir(legacy) else os.path.join(self.root, 'b%s_%s' % (S, n)))
            if not os.path.isdir(W):
                if R.run('show-ref', '-q', '--verify', 'refs/heads/' + br).returncode == 0:
                    R.run('worktree', 'add', '-q', W, br, check=True)
                elif br in self.hub.heads:
                    with_retry(lambda: R.run('fetch', '-q', 'origin', '+refs/heads/%s:refs/remotes/origin/%s' % (br, br)), 3)
                    R.run('worktree', 'add', '-q', '-b', br, W, 'origin/' + br, check=True)
                else:
                    R.run('worktree', 'add', '-q', '-b', br, W, 'origin/' + coord, check=True)
        g = Git(W, env=self.hub.genv)
        if g.run('rev-parse', '--abbrev-ref', 'HEAD').out != br:
            raise RuntimeError('%s 가 %s 이 아님' % (W, br))
        if br in self.hub.heads:
            g.run('pull', '-q', '--no-edit', '--no-rebase', 'origin', br)
        m = g.run('merge', '-q', '--no-edit', 'origin/' + coord)
        if m.returncode != 0:
            g.run('merge', '--abort')
            raise RuntimeError('보드 %s: coord 병합 충돌 — 손으로 확인 필요' % n)
        return W, g, br

    def job_board(self, job):
        S, k, n = job.S, job.k, int(job.unit.split('_')[1])
        sc = self.cfg['stacks'][S]
        W, g, br = self.board_worktree(S, n, sc)
        rows = [l.split('\t') for l in open(os.path.join(W, 'data/ft%s/step%d/assign.tsv' % (S, k))).read().splitlines()[1:]]
        B = [r[0] for r in rows if int(r[1]) == n]
        if not B:
            return 'ok'
        res = lambda b: os.path.join(W, 'data/ft%s/results/step%d/%s/done.json' % (S, k, b))
        L = os.path.join(self.root, 'logs', 'board_ft%s_%d.log' % (S, n))
        wrapper = os.path.join(HERE, 'board_run.py')
        env = self.env.base(S, {'SPOT_PANEL_WORKERS': self.cfg['cpu']['workers_per_board'], 'FT_WORK': self.env.work(S, '_b%d' % n),
                                'LAB_RETRY_LIMIT': self.cfg['cpu']['workers_per_board']}, threads=1)
        if self.test_boards:
            env['FT_TEST_BOARDS'] = self.test_boards
        if self.no_push:
            env['FT_NO_PUSH'] = '1'
        fails = 0
        while True:
            left = [b for b in B if not os.path.exists(res(b))]
            job.progress = '%d/%d 묶음' % (len(B) - len(left), len(B))
            if not left:
                self.clean_board_work(S, n, B, W, g, br)
                return 'ok'
            log.info('ft%s 보드 %d: 시작/재개 — 남은 묶음 %s', S, n, left)
            cmd = self.env.nice + [self.env.py, wrapper] + left
            rc = runlog(cmd, W, env, L)
            tail = open(L, errors='replace').read()[-4000:] if os.path.exists(L) else ''
            last = tail.strip().splitlines()[-1] if tail.strip() else ''
            if 'FT_BOARD_ALL_DONE' in last:
                continue
            fails += 1
            if 'input sha256 differs' in tail[-1500:]:
                raise RuntimeError('입력이 바뀜(input sha256 differs) — 조정 쪽 확인 필요')
            if fails >= 5:
                raise RuntimeError('5번 연속 실패, 로그 %s' % L)
            log.info('ft%s 보드 %d: 멈춤(%d번째) 종료코드 %s', S, n, fails, rc)
            time.sleep(60)
            if br in self.hub.heads:
                g.run('pull', '-q', '--no-edit', '--no-rebase', 'origin', br)
            g.run('merge', '-q', '--no-edit', 'origin/claude/ft%s_coord' % S)

    def clean_board_work(self, S, n, B, W, g, br):
        """끝난 묶음의 작업 폴더(보드 원본)를 지운다 — 푸시가 끝난 뒤에만."""
        if not self.no_push and g.run('rev-list', '--count', 'origin/%s..%s' % (br, br)).out not in ('0', ''):
            return
        for b in B:
            shutil.rmtree(os.path.join(self.env.work(S, '_b%d' % n), b), ignore_errors=True)

    # --- 조정 일: collect / next_tables / solve / prepare
    def coord_wt(self, S, sc):
        br = sc['coord_branch']
        cr, root = self.hub.cr, self.root
        with_retry(lambda: cr.run('fetch', '-q', 'origin', '+refs/heads/%s:refs/remotes/origin/%s' % (br, br)), 3)
        W = os.path.join(root, 'coord%s' % S)
        local = 'lab/coord%s' % S
        if not os.path.isdir(W):
            cr.run('worktree', 'prune')
            cr.run('worktree', 'add', '-q', '-B', local, W, 'origin/' + br, check=True)
        g = Git(W, env=self.hub.genv)
        m = g.run('merge', '-q', '--no-edit', 'origin/' + br)
        if m.returncode != 0:
            g.run('merge', '--abort')
            raise RuntimeError('coord 작업 폴더 병합 충돌')
        return W, g

    def tool_env(self, S, W, sc, extra=None, threads=None):
        """도구(ft60.py, ft_solve.sh) 환경 변수. 도구가 구버전(설정 파일 이름)이냐 신버전(절대 경로)이냐에 맞춘다."""
        sh = open(os.path.join(W, 'tools/gto_fulltree/ft_solve.sh')).read() if os.path.exists(os.path.join(W, 'tools/gto_fulltree/ft_solve.sh')) else ''
        cfgname = sc.get('cfg_file')
        cfg_abs = os.path.join(self.env.calc, 'data/gto_spot/plan_a', cfgname)
        e = self.env.base(S, extra, threads=threads or self.cfg['cpu']['coord_threads'])
        e['FT_WORK'] = self.env.work(S)
        e['FT_CFG'] = cfg_abs if 'FT_STOP_GAP' in sh else cfgname
        return e

    def job_coord(self, job):
        S, k, unit = job.S, job.k, job.unit
        sc = self.cfg['stacks'][S]
        stage = unit.split('_', 1)[1]
        W, g = self.coord_wt(S, sc)
        D = os.path.join(W, 'data/ft%s' % S)
        py, nice = self.env.py, self.env.nice
        L = os.path.join(self.root, 'logs', 'coord_ft%s.log' % S)
        T = os.path.join(W, 'tools/gto_fulltree')
        push_br = sc.get('coord_push_branch') or sc['coord_branch']
        paths = []
        if stage == 'collect':
            self.do_collect(S, k, sc, W, g, L, paths)
        elif stage == 'next_tables':
            self.do_next_tables(S, k, sc, W, g, L, paths)
        elif stage == 'solve':
            self.do_solve(S, k, sc, W, g, L, paths)
        elif stage == 'prepare':
            self.do_prepare(S, k, sc, W, g, L, paths)
        if not paths:
            return 'ok'
        ok = self.hub.push_coord(W, push_br, 'ft%s step %s: %s (lab autopilot)' % (S, k, stage), paths)
        if not ok:
            raise RuntimeError('조정 브랜치 푸시 실패')
        return 'ok'

    def _need(self, W, rel):
        return os.path.exists(os.path.join(W, rel))

    def ensure_binaries(self, S, W, L):
        """t2_pf_solve·t2_tree_dump·t2_ft_export 가 있고 도구(패치·소스)가 바뀌지 않았는지 — 아니면 ft_coord_setup.sh 로 다시 빌드(낮은 우선순위)."""
        T = os.path.join(W, 'tools/gto_fulltree')
        cfgf = os.path.join(self.env.calc, 'data/gto_spot/plan_a', self.cfg['stacks'][S].get('cfg_file', ''))
        if not os.path.exists(cfgf):      # ft_board_setup.sh 의 sparse 목록에는 설정 폴더가 없다(풀이·prepare 에는 필요) → 추가
            cg = Git(self.env.calc, env=self.hub.genv)
            cg.run('sparse-checkout', 'add', 'data/gto_spot/plan_a')
            cg.run('checkout', '-q')
            if not os.path.exists(cfgf):
                raise RuntimeError('설정 파일 없음: %s' % cfgf)
        h = hashlib.sha256()
        for f in sorted(glob.glob(os.path.join(T, 't2_*.rs')) + glob.glob(os.path.join(T, '*.patch')) + [os.path.join(T, 'ft_coord_setup.sh')]):
            if os.path.exists(f):
                h.update(open(f, 'rb').read())
        stamp = os.path.join(self.root, 'state/coord_build.stamp')
        ex = os.path.join(self.env.calc, 'vendor/gtopen/target/release/examples')
        have = all(os.path.exists(os.path.join(ex, b)) for b in ('t2_pf_solve', 't2_tree_dump', 't2_ft_export'))
        if have and os.path.exists(stamp) and open(stamp).read() == h.hexdigest():
            return
        log.info('계산기(풀이·덤프·내보내기) 빌드/갱신 — 시간이 걸림')
        env = self.env.base(S, threads=self.cfg['cpu']['coord_threads'])
        env['CARGO_BUILD_JOBS'] = str(self.cfg['cpu']['coord_threads'])
        if runlog(self.env.nice + ['sh', os.path.join(T, 'ft_coord_setup.sh')], W, env, L) != 0:
            raise RuntimeError('ft_coord_setup.sh 실패(로그 %s)' % L)
        open(stamp, 'w').write(h.hexdigest())

    def do_solve(self, S, k, sc, W, g, L, paths):
        self.ensure_binaries(S, W, L)
        env = self.tool_env(S, W, sc, sc.get('solve_env'))
        rc = runlog(self.env.nice + ['sh', os.path.join(W, 'tools/gto_fulltree/ft_solve.sh'), str(k)], W, env, L)
        if rc != 0:
            raise RuntimeError('ft_solve.sh 실패 rc=%s (로그 %s)' % (rc, L))
        sd = os.path.join(W, 'data/ft%s/step%d/solve' % (S, k))
        os.makedirs(sd, exist_ok=True)
        src = os.path.join(self.env.work(S), 'solve_s%d' % k)
        for f in glob.glob(os.path.join(src, 'solve_*.json')) + glob.glob(os.path.join(src, 'exact_*.json')) + [os.path.join(src, 'final_n')]:
            shutil.copy(f, sd)
        with open(os.path.join(src, 'dump.jsonl'), 'rb') as a, gzip.open(os.path.join(sd, 'dump.jsonl.gz'), 'wb', 6) as b:
            shutil.copyfileobj(a, b)
        fn = int(open(os.path.join(src, 'final_n')).read().strip())
        ex = json.load(open(os.path.join(src, 'exact_%d.json' % fn)))['gap_total']
        json.dump({'step': k, 'status': 'exact gap %.5f (%s)' % (ex, '<0.02 사용자 기준' if ex < 0.02 else '>=0.02'), 'final_iterations': fn, 'exact_gap': ex,
                   'start': 'from scratch, lab autopilot', 'by': 'lab autopilot'}, open(os.path.join(W, 'data/ft%s/step%d/convergence.json' % (S, k)), 'w'), indent=1)
        paths += ['data/ft%s/step%d/solve' % (S, k), 'data/ft%s/step%d/convergence.json' % (S, k)]

    def do_prepare(self, S, k, sc, W, g, L, paths):
        self.ensure_binaries(S, W, L)
        src = os.path.join(self.env.work(S), 'solve_s%d' % k)
        if not (os.path.exists(os.path.join(src, 'ck.gtop')) and os.path.exists(os.path.join(src, 'final_n'))):
            log.info('prepare 에 필요한 체크포인트가 연구실에 없음 → 먼저 풀이를 다시 한다(재현 가능, 정확 gap<0.02까지)')
            self.do_solve(S, k, sc, W, g, L, [])        # 이미 조정 브랜치에 있는 solve 파일은 같은 내용이라 다시 올리지 않음
        pe = dict(sc.get('prepare_env') or {})
        hrs = self.step_hours(S, k - 1, W)
        if hrs:
            pe.update(hrs)
        env = self.tool_env(S, W, sc, pe)
        rc = runlog(self.env.nice + [self.env.py, os.path.join(W, 'tools/gto_fulltree/ft60.py'), 'prepare', str(k), os.path.join(src, 'ck.gtop'), os.path.join(src, 'dump.jsonl')], W, env, L)
        if rc != 0:
            raise RuntimeError('ft60.py prepare 실패 rc=%s' % rc)
        sd = os.path.join(W, 'data/ft%s/step%d' % (S, k))
        exp = os.path.join(self.env.work(S), 'step%d_export.jsonl' % k)
        with open(exp, 'rb') as a, gzip.open(os.path.join(sd, 'used_gross.jsonl.gz'), 'wb', 6) as b:
            shutil.copyfileobj(a, b)
        tm = os.path.join(W, 'tools/gto_fulltree/terminal_mass.py')
        tmp = os.path.join(self.env.work(S), 'terminals_mass_%d.json' % k)
        if os.path.exists(tm) and runlog([self.env.py, tm, os.path.join(src, 'dump.jsonl'), tmp], W, env, L) == 0:
            with open(tmp, 'rb') as a, gzip.open(os.path.join(sd, 'terminals_mass.json.gz'), 'wb', 6) as b:
                shutil.copyfileobj(a, b)
        paths += ['data/ft%s/step%d' % (S, k)]
        # collect·next_tables 산출물(tables_*)은 올리지 않는다
        for p in ('collect',):
            pass

    def step_hours(self, S, k, W):
        """직전 단계 실측 시간 → prepare 배분용 환경 변수(도구 신버전은 FT_BOARD_HOURS 파일, 구버전은 FT_H_MATRIX/FT_H_SIMPLE 중앙값)."""
        f = os.path.join(W, 'data/ft%s/step%d_board_hours.json' % (S, k))
        if not os.path.exists(f):
            return None
        d = json.load(open(f))
        if 'FT_BOARD_HOURS' in open(os.path.join(W, 'tools/gto_fulltree/ft60.py')).read():
            return {'FT_BOARD_HOURS': f}
        med = statistics.median(d.values())
        return {'FT_H_MATRIX': round(med, 2), 'FT_H_SIMPLE': round(med, 2)}

    def do_collect(self, S, k, sc, W, g, L, paths):
        env = self.tool_env(S, W, sc)
        rc = runlog(self.env.nice + [self.env.py, os.path.join(W, 'tools/gto_fulltree/ft60.py'), 'collect', str(k)], W, env, L)
        if rc != 0:
            raise RuntimeError('ft60.py collect 실패 rc=%s' % rc)
        sd = os.path.join(W, 'data/ft%s/step%d' % (S, k))
        rep = json.load(open(os.path.join(sd, 'collect/report.json')))
        wk = os.path.join(self.env.work(S), 'collect_s%d' % k)
        # 플랍 실패 재시도 결과(≤0.6% pot) 와 보드 시간 실측
        rows = list(csv.DictReader(open(os.path.join(sd, 'bundles.tsv')), delimiter='\t'))
        node_of = {r['bundle']: int(r['node']) for r in rows}
        dec, hours = {}, {}
        for b, boards in rep.get('flop_failures_after_retry') or []:
            vals = json.load(gzip.open(os.path.join(wk, b, 'values.json.gz'), 'rt'))
            for x in boards:
                rt = (vals.get(x) or {}).get('retry') or {}
                dec['%s/%s' % (b, x)] = {'first_pct_pot': rt.get('first_pct_pot'), 'retry_pct_pot': rt.get('retry_pct_pot'),
                                         'accepted': rt.get('retry_pct_pot') is not None and rt['retry_pct_pot'] <= sc['judge']['flop_accept_pct_pot']}
        for b in node_of:
            dj = os.path.join(wk, b, 'done.json')
            if os.path.exists(dj):
                hours.setdefault(str(node_of[b]), []).append(json.load(open(dj)).get('wall_min_this_run', 0) / 60)
        if hours:
            json.dump({n: round(statistics.median(v), 2) for n, v in hours.items()}, open(os.path.join(W, 'data/ft%s/step%d_board_hours.json' % (S, k)), 'w'), indent=1)
            paths.append('data/ft%s/step%d_board_hours.json' % (S, k))
        if dec:
            json.dump({'rule': 'retry exploitability <=%.1f%% pot accepted (accepted_above_target), else terminal stays static (lab autopilot)' % sc['judge']['flop_accept_pct_pot'],
                       'boards': dec}, open(os.path.join(sd, 'flop_failure_decision.json'), 'w'), indent=1)
            paths.append('data/ft%s/step%d/flop_failure_decision.json' % (S, k))
        ev = local_evidence(S, W)
        v = evaluate(ev, k, sc['judge'])
        if v['static_nodes_add']:
            sn = os.path.join(sd, 'static_nodes.json')
            cur = set(json.load(open(sn))) if os.path.exists(sn) else set()
            json.dump(sorted(cur | set(v['static_nodes_add'])), open(sn, 'w'))
            paths.append('data/ft%s/step%d/static_nodes.json' % (S, k))
        self.write_judge(S, k, sd, v, paths)
        paths.append('data/ft%s/step%d/collect/report.json' % (S, k))

    def write_judge(self, S, k, sd, v, paths):
        json.dump(v, open(os.path.join(sd, 'judge.json'), 'w'), indent=1, ensure_ascii=False)
        open(os.path.join(sd, 'judge.md'), 'w').write('# ft%s 단계 %d 자동 판정 (lab autopilot)\n\n상태: **%s**\n\n%s\n\n%s\n' % (
            S, k, v['status'], '\n'.join('- ' + r for r in v['reasons'] + v['warnings']), J.render_table(v)))
        paths += ['data/ft%s/step%d/judge.json' % (S, k), 'data/ft%s/step%d/judge.md' % (S, k)]

    def do_next_tables(self, S, k, sc, W, g, L, paths):
        sd = os.path.join(W, 'data/ft%s/step%d' % (S, k))
        env = self.tool_env(S, W, sc)
        if not os.path.exists(os.path.join(sd, 'collect/tables_AB/manifest.json')):
            log.info('tables_AB 가 없음 → collect 를 여기서 다시(올리지 않음)')
            rc = runlog(self.env.nice + [self.env.py, os.path.join(W, 'tools/gto_fulltree/ft60.py'), 'collect', str(k)], W, env, L)
            if rc != 0:
                raise RuntimeError('collect(재계산) 실패')
        # history.json 은 next_tables 가 덧붙이므로 실패하면 되돌린다
        hp = os.path.join(W, 'data/ft%s/history.json' % S)
        snap = open(hp).read() if os.path.exists(hp) else None
        nd = os.path.join(W, 'data/ft%s/step%d/tables' % (S, k + 1))
        if os.path.exists(os.path.join(nd, 'manifest.json')):
            return
        rc = runlog(self.env.nice + [self.env.py, os.path.join(W, 'tools/gto_fulltree/ft60.py'), 'next_tables', str(k)], W, env, L)
        if rc != 0:
            shutil.rmtree(nd, ignore_errors=True)
            if snap is not None:
                open(hp, 'w').write(snap)
            raise RuntimeError('next_tables 실패')
        if 'static_nodes' not in open(os.path.join(W, 'tools/gto_fulltree/ft60.py')).read() and os.path.exists(os.path.join(sd, 'static_nodes.json')):
            log.info('주의: 이 도구 버전은 static_nodes.json 을 읽지 않음(NC-3) — 코디네이터 확인 필요')
        paths += ['data/ft%s/step%d/tables' % (S, k + 1), 'data/ft%s/history.json' % S]

    # --- 정리·자체 갱신·상태
    def cleanup(self, aggressive=False):
        keep = self.cfg['disk']['keep_collect_steps']
        for S in self.cfg['stacks']:
            w = self.env.work(S)
            ds = sorted(glob.glob(os.path.join(w, 'collect_s*')), key=lambda p: int(re.search(r'(\d+)$', p).group(1)))
            for d in ds[:-keep] if not aggressive else ds[:-1]:
                shutil.rmtree(d, ignore_errors=True)
            ss = sorted(glob.glob(os.path.join(w, 'solve_s*')), key=lambda p: int(re.search(r'(\d+)$', p).group(1)))
            for d in ss[:-keep]:
                for f in ('ck.gtop', 'ck_exact.gtop', 'dump.jsonl'):
                    try:
                        os.remove(os.path.join(d, f))
                    except OSError:
                        pass
        for d in glob.glob(os.path.join(self.root, 'logs', '*.log')):
            if os.path.getsize(d) > 50_000_000:
                with open(d, 'rb') as f:
                    f.seek(-5_000_000, 2)
                    tail = f.read()
                open(d, 'wb').write(tail)

    def self_update(self):
        if not self.cfg['loop'].get('self_update'):
            return
        wt = os.path.join(self.root, 'autopilot')
        if not os.path.isdir(os.path.join(wt, '.git')) and not os.path.isfile(os.path.join(wt, '.git')):
            return
        if os.path.abspath(HERE) != os.path.abspath(os.path.join(wt, 'tools/gto_fulltree/lab_autopilot')):
            return
        g = Git(wt, env=self.hub.genv)
        br = 'claude/lab_autopilot'
        if with_retry(lambda: g.run('fetch', '-q', 'origin', '+refs/heads/%s:refs/remotes/origin/%s' % (br, br)), 1).returncode != 0:
            return
        if g.run('rev-parse', 'HEAD').out == g.run('rev-parse', 'origin/' + br).out:
            self.update_pending_since = None
            return
        if g.run('merge', '-q', '--ff-only', 'origin/' + br).returncode != 0:
            return
        if not self.update_pending_since:
            log.info('봇 코드 새 버전 받음 — 일이 끝나는 대로 다시 시작')
            self.update_pending_since = time.time()

    def maybe_restart(self):
        if not self.update_pending_since:
            return
        alive = [j for j in self.jobs.values() if isinstance(j, Job) and j.is_alive()]
        if alive and age_h(self.update_pending_since) < self.cfg['loop']['self_update_force_hours']:
            return
        log.info('다시 시작(새 코드)')
        os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])

    def status_doc(self):
        d = {'time': iso(), 'host': socket.gethostname(), 'owner': self.cfg['owner'], 'uptime_h': round((time.time() - self.t0) / 3600, 1),
             'mode': 'dry' if self.dry else ('no_push' if self.no_push else 'live'),
             'code': Git(HERE).run('rev-parse', '--short', 'HEAD').out,
             'cpu': {'budget': self.cfg['cpu']['total_cores'], 'in_use': self.running_cost(), 'load': os.getloadavg()},
             'disk_free_gb': round(shutil.disk_usage(self.cfg['work']).free / 2**30, 1) if os.path.isdir(self.cfg['work']) else None,
             'jobs': [{'stack': j.S, 'step': j.k, 'unit': j.unit, 'started': j.started, 'progress': j.progress} for j in self.jobs.values() if isinstance(j, Job) and j.is_alive()],
             'stacks': {}, 'errors': self.errors[-10:], 'update_pending': bool(self.update_pending_since),
             'questions_for_coordinator': ['NC-1 뿌리 복제(③) 처리', 'NC-2 수렴 문턱·단계 상한', 'NC-3 도구 버전(static_nodes/행렬)', 'NC-4 조정 브랜치 푸시 위치'],
             'blocked': {k: iso(dt.datetime.fromtimestamp(t, dt.timezone.utc)) for k, t in self.state['blocked'].items() if t > time.time()}}
        for S, sv in self.view.items():
            e = {'phase': sv.phase, 'why': sv.why, 'step': sv.K, 'coord_tip_age_h': None if sv.last_commit_age_h is None else round(sv.last_commit_age_h, 1)}
            if sv.boards:
                e['boards'] = {n: {'done': b['all_done'], 'bundles': b['bundles'], 'tip_age_h': None if b['tip_age_h'] is None else round(b['tip_age_h'], 1),
                                   'claim': (self.claims.get((S, sv.K, 'board_%d' % n)) or {}).get('owner')} for n, b in sv.boards.items()}
            if sv.verdict:
                v = sv.verdict
                e['verdict'] = {'step': v['step'], 'status': v['status'], 'reasons': v['reasons'], 'warnings': v['warnings'], 'pass_D_le_U': '%d/%d' % (v['metrics']['pass_D_le_U'], v['metrics']['seats']),
                                'dou_median': v['metrics']['dou_median'], 'dM_vs_prev_median': v['metrics']['dM_vs_prev_median']}
            d['stacks'][S] = e
        return d

    def md_status(self, d):
        l = ['# 연구실 봇 상태 %s (%s)' % (d['time'], d['mode']), '', '- 호스트 %s, 가동 %.1f시간, 코드 %s, CPU %s/%s 코어 사용, 디스크 여유 %s GB' % (
            d['host'], d['uptime_h'], d['code'], d['cpu']['in_use'], d['cpu']['budget'], d['disk_free_gb'])]
        l += ['- 지금 하는 일: ' + (', '.join('ft%s 단계%s %s(%s)' % (j['stack'], j['step'], j['unit'], j['progress']) for j in d['jobs']) or '없음 (대기)')]
        for S, e in d['stacks'].items():
            l.append('- **%sbb** 단계 %s: %s — %s' % (S, e['step'], e['phase'], e['why']))
            if 'verdict' in e:
                v = e['verdict']
                l.append('  - 판정(단계 %s): %s, D≤U %s, D/U 중앙값 %s' % (v['step'], v['status'], v['pass_D_le_U'], None if v['dou_median'] is None else round(v['dou_median'], 2)))
        if d['errors']:
            l += ['', '최근 오류:'] + ['- %s %s %s' % (e['t'], e['key'], e['err'][-100:]) for e in d['errors'][-5:]]
        return '\n'.join(l) + '\n'

    def push_status(self, force=False):
        if not force and time.time() - self.t_status < self.cfg['loop']['status_push_minutes'] * 60:
            return
        d = self.status_doc()
        tail = ''
        lp = os.path.join(self.root, 'logs/autopilot.log')
        if os.path.exists(lp):
            tail = ''.join(open(lp, errors='replace').readlines()[-150:])
        json.dump(d, open(os.path.join(self.root, 'state/status.json'), 'w'), indent=1)
        self.t_status = time.time()
        if self.no_push:
            return
        self.hub.push_status({'status/%s.json' % self.cfg['owner']: json.dumps(d, indent=1, ensure_ascii=False), 'status/%s.md' % self.cfg['owner']: self.md_status(d),
                              'status/%s.log_tail.txt' % self.cfg['owner']: tail})

    def tick(self):
        self.reap()
        if time.time() - self.t_refresh >= self.cfg['loop']['github_refresh_seconds'] or not self.view:
            try:
                self.refresh()
            except Exception as e:      # noqa
                log.info('깃허브 읽기 실패(다음에 다시): %s', str(e)[-200:])
        if time.time() - self.t_hb > self.cfg['loop']['claim_heartbeat_minutes'] * 60 and not self.no_push:
            self.hub.heartbeat([k for k, j in self.jobs.items() if isinstance(j, Job) and j.is_alive()])
            self.t_hb = time.time()
        self.self_update()
        if self.view:
            try:
                self.schedule()
            except Exception:       # noqa
                log.exception('스케줄 오류')
        self.cleanup()
        try:
            self.push_status()
        except Exception as e:      # noqa
            log.info('상태 푸시 실패: %s', str(e)[-150:])
        self.maybe_restart()

    def run_forever(self):
        log.info('lab autopilot 시작 (%s) 코어 %s, 보드 %d×워커 %d, nice %d', 'dry' if self.dry else ('no_push' if self.no_push else 'live'),
                 self.cfg['cpu']['total_cores'], self.cfg['cpu']['boards_parallel'], self.cfg['cpu']['workers_per_board'], self.cfg['cpu']['nice'])
        kill_leftovers()
        stop = []
        signal.signal(signal.SIGTERM, lambda *a: stop.append(1))
        signal.signal(signal.SIGINT, lambda *a: stop.append(1))
        os.nice(0)
        while not stop:
            try:
                self.tick()
            except Exception:       # noqa
                log.exception('루프 오류(계속)')
            idle = not any(isinstance(j, Job) and j.is_alive() for j in self.jobs.values())
            wait = self.cfg['loop']['idle_wait_seconds'] if idle and self.view else self.cfg['loop']['poll_seconds']
            if idle:
                log.info('할 일 없음(모두 끝났거나 다른 쪽이 잡음) — %d분 뒤 다시 확인', wait // 60)
            for _ in range(int(wait)):
                if stop:
                    break
                time.sleep(1)
        log.info('종료 신호 — 계산을 끄고 정리(끝난 덩어리는 푸시돼 있어 이어서 됨)')
        kill_leftovers()
        self.push_status(force=True)


# ----------------------------------------------------------------------------- CLI
def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return
    cmd = a[0]
    dry = '--dry' in a
    cfg = load_config()
    if cmd in ('run', 'once'):
        ap = Autopilot(cfg, dry=dry)
        if cmd == 'once':
            ap.refresh()
            plan = ap.candidates()
            ap.push_status(force=True)
            print(ap.md_status(ap.status_doc()))
            print('할 수 있는 일:' if plan else '지금 연구실이 할 일 없음')
            for S, k, kind, unit, why in plan:
                print('  스택 %s 단계 %s %s — %s' % (S, k, unit, why))
        else:
            os.makedirs(cfg['root'], exist_ok=True)
            ap.run_forever()
    elif cmd == 'status':
        p = os.path.join(cfg['root'], 'state/status.json')
        print(open(p).read() if os.path.exists(p) else '상태 파일 없음')
    elif cmd == 'judge':
        S, k = a[1], int(a[2])
        sc = cfg['stacks'].get(S, {'judge': cfg['judge']})
        if '--local' in a:
            ev = local_evidence(S, a[a.index('--local') + 1])
        else:
            ap = Autopilot(cfg, dry=True)
            ap.hub.refresh_heads({S: sc})
            br = sc['coord_branch']
            ap.hub.fetch(br)
            ev = Evidence(S, lambda p: ap.hub.show(br, p), ap.hub.ls(br, 'data/ft%s' % S))
        v = evaluate(ev, k, sc['judge'])
        if not v:
            print('collect report.json 없음')
            return
        print(J.render_table(v))
        print(json.dumps({x: v[x] for x in ('status', 'reasons', 'warnings', 'static_nodes_add', 'cycling', 'needs_confirmation')}, ensure_ascii=False, indent=1))
    elif cmd in ('claim', 'release'):
        S, k, unit = a[1], int(a[2]), a[3]
        owner = a[a.index('--owner') + 1] if '--owner' in a else cfg['owner']
        hub = Hub(cfg, push_enabled=os.environ.get('FT_NO_PUSH') != '1')
        hub.refresh_heads({})
        if cmd == 'claim':
            ok = hub.claim(S, k, unit, owner=owner, ttl_h=cfg['loop']['claim_ttl_hours'])
            print('CLAIM_OK' if ok else 'CLAIM_TAKEN')
            sys.exit(0 if ok else 3)
        print('RELEASED' if hub.release(S, k, unit, owner=owner) else 'NOT_MINE_OR_MISSING')
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
