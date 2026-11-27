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

HERE = os.path.dirname(os.path.realpath(__file__))
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
    root = os.path.expanduser(os.path.expandvars(os.environ.get('LAB_ROOT') or cfg['root']))
    cfg['root'] = root
    for p in (os.path.join(root, 'config.local.json'), extra or os.environ.get('LAB_CONFIG')):
        if p and os.path.exists(p):
            deep_merge(cfg, json.load(open(p)))
    cfg['root'] = os.path.expanduser(os.path.expandvars(os.environ.get('LAB_ROOT') or cfg['root']))
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


class JobFail(Exception):
    """일 실패. code = 경고 분류(solver_rc, input_changed, push_failed, merge_conflict, no_progress, job_error ...), logfile = 경고에 붙일 로그."""

    def __init__(self, code, msg, logfile=None):
        super().__init__(msg)
        self.code, self.logfile = code, logfile


def tail_lines(path, n=200):
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2)
            sz = f.tell()
            f.seek(max(0, sz - 200_000))
            return f.read().decode(errors='replace').splitlines()[-n:]
    except OSError:
        return []


def proc_ticks(pgid):
    """프로세스 그룹 pgid 에 속한 모든 프로세스의 CPU 시간(clock tick 합, utime+stime). 실제 계산 프로세스(t2_cont_panel 등)가 일하는지 보려는 것."""
    tot = 0
    for d in glob.glob('/proc/[0-9]*'):
        try:
            st = open(d + '/stat').read()
            f = st[st.rindex(')') + 2:].split()      # f[0]=state f[1]=ppid f[2]=pgrp ... f[11]=utime f[12]=stime
            if int(f[2]) == pgid:
                tot += int(f[11]) + int(f[12])
        except (OSError, ValueError, IndexError):
            continue
    return tot


def mem_avail_gb():
    try:
        for l in open('/proc/meminfo'):
            if l.startswith('MemAvailable:'):
                return int(l.split()[1]) / 1048576.0
    except OSError:
        pass
    return None


def newest_mtime(path, depth=3):
    best = 0.0
    try:
        for e in os.scandir(path):
            try:
                if e.is_dir(follow_symlinks=False) and depth > 0:
                    best = max(best, newest_mtime(e.path, depth - 1))
                else:
                    best = max(best, e.stat(follow_symlinks=False).st_mtime)
            except OSError:
                continue
    except OSError:
        pass
    return best


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
            # 전체 이력의 큰 파일(blob)은 받지 않는 부분 복제(처음 한 번도 빠르게). 필요한 파일은 체크아웃·git show 때 그때그때 받는다
            r = Git(self.root).run('clone', '-q', '--no-checkout', '--filter=blob:none', self.url, self.cr.path, timeout=1800)
            if r.returncode != 0:
                shutil.rmtree(self.cr.path, ignore_errors=True)
                Git(self.root).run('clone', '-q', '--no-checkout', self.url, self.cr.path, check=True, timeout=3600)
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

    def fetch(self, br, force=False, depth=1):
        """br 를 peek 에 얕게 가져와 origin/<br> 로 둔다(sha 가 같으면 건너뜀). 성공 시 sha."""
        want = self.heads.get(br)
        if want is None:
            return None
        if not force and self.seen.get(br) == want:
            return want
        r = with_retry(lambda: self.peek.run('fetch', '-q', '--depth=%d' % depth, '--filter=blob:none', 'origin', '+refs/heads/%s:refs/remotes/origin/%s' % (br, br), timeout=300), 3)
        if r.returncode != 0:
            r = with_retry(lambda: self.peek.run('fetch', '-q', '--depth=%d' % depth, 'origin', '+refs/heads/%s:refs/remotes/origin/%s' % (br, br), timeout=300), 2)
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

    def tip_time_foreign(self, br):
        """봇 자신(git 이름 = owner 설정의 git_user)이 쓴 커밋을 뺀 가장 최근 커밋 시각. 가져온 이력(얕게 30개) 안에 없으면 None."""
        name = re.escape(self.cfg['git_user'])
        r = self.peek.run('log', '-1', '--format=%ct', '--perl-regexp', '--author=^(?!%s <)' % name, 'origin/' + br)
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
    if br not in hub.heads or not hub.fetch(br, depth=30):
        sv.phase, sv.why = 'no_coord', '조정 브랜치를 못 읽음'
        return sv
    files = hub.ls(br, 'data/ft%s' % S)
    ev = Evidence(S, lambda p: hub.show(br, p), files)
    ct = hub.tip_time_foreign(br)          # 봇 자신의 푸시는 '조정 세션이 작업 중' 판단에서 뺀다
    sv.last_commit_age_h = age_h(ct) if ct else 9999.0
    sv.ev = ev
    steps = ev.steps()
    if not steps:
        sv.phase, sv.why = 'none', 'data/ft%s 에 단계가 없음' % S
        return sv
    K = sv.K = steps[-1]
    has = ev.has
    sv.stall_streak = 0
    if has('step%d/collect/report.json' % K):
        sv.verdict = evaluate(ev, K, sc['judge'])
    top = K if sv.verdict else K - 1       # 정체 경고 연속 횟수: 가장 최근 판정된 단계부터 거꾸로, 정체 경고가 이어진 단계 수
    for kk in range(top, max(top - 4, -1), -1):
        v = sv.verdict if kk == K else evaluate(ev, kk, sc['judge'])
        if v and v.get('stall'):
            sv.stall_streak += 1
        else:
            break
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
        # 묶음이 어느 보드 브랜치에서 돌든(보드 번호 재배정·'4b' 같은 이름 포함) 모든 claude/ft<S>_board_* 에서 그 묶음의 결과·최근 푸시를 본다(collect 와 같은 방식)
        holders = {}          # bundle -> {branch: (done?, tip_age_h)}
        tips = {}
        for bb in sorted(x for x in hub.heads if re.match(r'claude/ft%s_board_' % re.escape(S), x)):
            if not hub.fetch(bb):
                continue
            fs = hub.ls(bb, 'data/ft%s/results/step%d' % (S, K))
            t = hub.tip_time(bb)
            tips[bb] = age_h(t) if t else None
            for p in fs:
                m = re.search(r'/results/step\d+/([^/]+)/', p)
                if m:
                    d = holders.setdefault(m.group(1), {})
                    prev = d.get(bb, (False, tips[bb]))
                    d[bb] = (prev[0] or p.endswith('/done.json'), tips[bb])
        for n, bl in sorted(per.items()):
            bb = 'claude/ft%s_board_%s' % (S, n)
            info = {'branch': bb, 'bundles': {}, 'exists': bb in hub.heads, 'tip_age_h': tips.get(bb), 'sha': hub.heads.get(bb), 'holders': {}, 'done_on_own': False}
            for b in bl:
                h = holders.get(b, {})
                info['bundles'][b] = 'done' if any(v[0] for v in h.values()) else ('partial' if h else 'none')
                info['holders'][b] = [(x, v[1]) for x, v in h.items() if not v[0]]
                info['done_on_own'] |= bool(h.get(bb, (False,))[0])
            info['all_done'] = all(st == 'done' for st in info['bundles'].values())
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
    """보드 번호 n 을 연구실이 잡아도 되는가. (가능?, 이유). 판단은 **묶음 단위**: 묶음이 다른 보드 브랜치로 옮겨져 끝났거나 진행 중이면 그 묶음은 남의 일."""
    b = sv.boards[n]
    L = cfg['loop']
    if b['all_done']:
        return False, '끝남'
    c = claims.get((sv.S, sv.K, 'board_%d' % n))
    if c and c.get('owner') != hub.me and age_h(c.get('t_heartbeat', c['t_claim'])) < L['claim_ttl_hours']:
        return False, '다른 쪽이 claim(%s)' % c.get('owner')
    own = b['branch']
    mine = (c and c.get('owner') == hub.me) or own in local_branches
    started_other = bool(b.get('done_on_own')) and not mine      # 이 번호 브랜치에 남이 끝낸 묶음이 있음 = 남이 시작함
    for bundle, st in b['bundles'].items():
        if st == 'done':
            continue
        for hb, age in b['holders'].get(bundle, []):
            if hb in local_branches or (hb == own and mine):
                continue
            if age is not None and age >= L['stale_takeover_hours']:
                started_other |= hb == own    # 오래 멈춘 남의 부분 결과: 내 보드 브랜치면 인계, 다른 브랜치면 무시
                continue
            if age is None or age < L['active_hours']:
                return False, '묶음 %s 를 %s 가 %.1f시간 전에 푸시(진행 중)' % (bundle, hb, -1 if age is None else age)
            if hb != own:
                return False, '묶음 %s 는 다른 브랜치 %s 에서 시작됨(%.0f시간 전)' % (bundle, hb, age)
            started_other = True
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
        cur = threading.current_thread()
        if hasattr(cur, 'pids'):          # 감시(진행 없음 판단)와 취소를 위해 이 일이 띄운 프로세스 그룹을 알려 둔다
            cur.pids.add(p.pid)
            cur.log = logfile
        try:
            return p.wait(timeout=timeout)
        except BaseException:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except OSError:
                pass
            raise
        finally:
            if hasattr(cur, 'pids'):
                cur.pids.discard(p.pid)
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
        self.pids = set()
        self.log = None
        self.workdir = None
        self.cancelled = False
        self.exc = None
        self.t_cpu = self.t_file = time.time()
        self.last_ticks = None
        self.no_progress_h = 3.0

    def run(self):
        try:
            self.result = self.fn(self)
        except Exception as e:      # noqa
            self.exc = e
            self.result, self.err = 'cancelled' if self.cancelled else 'error', '%s: %s' % (type(e).__name__, e)
            log.exception('일 실패 %s', self.key)

    def cancel(self):
        self.cancelled = True
        for pg in list(self.pids):
            try:
                os.killpg(pg, signal.SIGTERM)
            except OSError:
                pass


class Autopilot:
    def __init__(self, cfg, dry=False):
        self.cfg = cfg
        self.dry = dry or bool(os.environ.get('LAB_DRY'))
        self.no_push = os.environ.get('FT_NO_PUSH') == '1' or self.dry
        self.root = cfg['root']
        for d in ('logs', 'work', 'state', 'releases'):
            os.makedirs(os.path.join(self.root, d), exist_ok=True)
        setup_log(self.root)
        PGID_DIR[0] = os.path.join(self.root, 'state/pgids')
        os.makedirs(PGID_DIR[0], exist_ok=True)
        self.hub = Hub(cfg, push_enabled=not self.no_push)
        self.env = Env(cfg)
        self.repo = Git(cfg['repo'], env=self.hub.genv)
        self.jobs = {}
        self.state = self._load_state()
        self.state.setdefault('ctl', {'paused': False, 'paused_stacks': [], 'priority': None, 'skip': [], 'stack': {}, 'cfg': {}, 'applied': {}})
        self.state['ctl'].setdefault('special', [])       # 특별 작업 대기열(원격 명령 enqueue): 스택 일보다 먼저, 컴퓨터를 혼자 쓰며 차례로
        self.state.setdefault('special_done', [])
        self.view, self.claims = {}, {}
        self.t_refresh = self.t_status = self.t_hb = self.t_control = self.t_watch = self.t_update = 0
        self.errors = []
        self.alerts = {}
        self.pushed_sig, self.t_pushed, self.push_fail = None, 0, 0
        self.refresh_fail = 0
        self.t0 = time.time()
        self.update_pending_since = None
        self.test_boards = os.environ.get('FT_TEST_BOARDS')
        self.repo_lock = threading.RLock()
        self.restart_requested = False
        rel = os.path.abspath(os.path.join(HERE, '../../..'))
        self.release = os.path.basename(rel) if os.path.dirname(rel) == os.path.join(self.root, 'releases') else None
        if self.state.get('pending_release'):
            self.update_pending_since = time.time()
        self.state['starts'] = [t for t in self.state.get('starts', []) if time.time() - t < 3600] + [time.time()]

    # --- 설정(원격 명령으로 바꾼 값 반영)
    def cget(self, path):
        ov = self.state['ctl']['cfg']
        if path in ov:
            return ov[path]
        v = self.cfg
        for p in path.split('.'):
            v = v[p]
        return v

    def stack_on(self, S, what='enabled'):
        ov = self.state['ctl']['stack'].get(S, {})
        if what in ov:
            return bool(ov[what])
        sc = self.cfg['stacks'][S]
        return bool(sc.get(what, what == 'boards'))

    def prio(self, S):
        order = self.state['ctl'].get('priority')
        if order and S in order:
            return order.index(S) - 1000
        return self.cfg['stacks'][S]['priority']

    # --- 경고(오류 보고용). 같은 (코드, 키)는 하나로 합쳐 횟수만 센다
    def alert(self, code, key, sev, msg, log=None, ttl_h=None, **ctx):
        k = (code, '|'.join(map(str, key)) if isinstance(key, tuple) else str(key))
        a = self.alerts.get(k)
        if a:
            a.update(severity=sev, msg=msg, last=iso(), log=log or a.get('log'), ctx=ctx)
            a['count'] += 1
        else:
            self.alerts[k] = {'code': code, 'key': k[1], 'severity': sev, 'msg': msg, 'since': iso(), 'last': iso(), 'count': 1, 'log': log, 'ctx': ctx}
        if ttl_h:
            self.alerts[k]['expire'] = time.time() + ttl_h * 3600

    def clear(self, code, key=None):
        kk = None if key is None else ('|'.join(map(str, key)) if isinstance(key, tuple) else str(key))
        for k in [k for k in self.alerts if k[0] == code and (kk is None or k[1] == kk)]:
            del self.alerts[k]

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
        ctl = self.state['ctl']
        if ctl['paused']:
            return out
        lb = self.local_board_branches()
        L = self.cfg['loop']
        for S, sv in sorted(self.view.items(), key=lambda kv: self.prio(kv[0])):
            if not self.stack_on(S, 'enabled') or S in ctl['paused_stacks']:
                continue
            if sv.phase in ('none', 'no_coord', 'error', 'halted'):
                continue
            if sv.phase in ('solve', 'prepare', 'collect', 'next_tables'):
                if not self.stack_on(S, 'coord_actions'):
                    continue
                if sv.last_commit_age_h is not None and sv.last_commit_age_h < L['coord_idle_hours']:
                    continue          # 조정 세션이 방금 푸시함 — 작업 중일 수 있어 기다림
                unit = 'coord_%s' % sv.phase
                if not self.skipped(S, sv.K, unit):
                    out.append((S, sv.K, 'coord', unit, sv.why))
            elif sv.phase == 'boards' and self.stack_on(S, 'boards'):
                for n in sorted(sv.boards):
                    ok, why = board_free(self.hub, self.cfg, sv, n, self.claims, lb)
                    if ok and not self.skipped(S, sv.K, 'board_%d' % n):
                        out.append((S, sv.K, 'board', 'board_%d' % n, why))
        return out

    def skipped(self, S, k, unit):
        return ('%s|%s|%s' % (S, k, unit) in self.state['ctl']['skip']) or ('%s|*|%s' % (S, unit) in self.state['ctl']['skip'])

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
        mem = mem_avail_gb()
        if mem is not None and mem < self.cfg['loop'].get('min_free_mem_gb', 3):
            log.info('메모리 여유 %.1fGB — 새 일 시작 안 함', mem)
            return
        if self.update_pending_since or self.restart_requested:
            return
        q = self.special_pending()
        if q:            # 특별 작업이 있으면 새 스택 일은 시작하지 않고, 돌고 있는 일이 묶음 경계에서 끝나기를 기다렸다가 혼자 돌린다
            if any(isinstance(j, Job) and j.is_alive() for j in self.jobs.values()):
                return 0
            it = q[0]
            if mem is not None and mem < float(it.get('min_mem_gb', 28)):
                self.alert('special_low_mem', ('special', 0, it['id']), 'warn', '특별 작업 %s 에 메모리 %.0fGB 필요, 여유 %.1fGB — 기다림' % (it['id'], float(it.get('min_mem_gb', 28)), mem), ttl_h=6)
                return 0
            self.clear('special_low_mem')
            key = ('special', 0, it['id'])
            if self.blocked(key):
                return 0
            if self.dry:
                log.info('(시험) 특별 작업 시작: %s', it)
                return 0
            j = Job(self, 'special', 'special', 0, it['id'], self.job_special, cap)
            j.item = it
            j.no_progress_h = 4.0
            self.jobs[key] = j
            j.start()
            log.info('특별 작업 시작: %s', it)
            return 1
        plan = self.candidates()
        started = 0
        nboards = sum(1 for j in self.jobs.values() if j.kind == 'board' and j.is_alive())
        wpb = self.cget('cpu.workers_per_board')
        for S, k, kind, unit, why in plan:
            key = (str(S), k, unit)
            if key in self.jobs and self.jobs[key].is_alive():
                continue
            if self.blocked(key):
                continue
            cost = wpb if kind == 'board' else self.cget('cpu.coord_threads')
            if kind == 'board' and nboards >= self.cget('cpu.boards_parallel'):
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
                self.hub.release(*key) if not self.no_push and j.kind != 'special' else None
                k = '|'.join(map(str, key))
                if j.result == 'ok':
                    self.state['fails'].pop(k, None)
                    for code in ('job_error', 'solver_rc', 'process_dead', 'push_failed', 'input_changed', 'merge_conflict', 'no_progress', 'coord_failed'):
                        self.clear(code, key)
                    if j.kind == 'coord':      # 같은 조정 일을 곧바로 되풀이하지 않는다(결과가 안 바뀌는 경우 무한 반복 방지)
                        self.state['blocked'][k] = time.time() + 6 * 3600
                    log.info('끝: %s', key)
                elif j.result == 'cancelled':
                    log.info('취소됨(원격 명령): %s', key)
                else:
                    n = self.state['fails'].get(k, 0) + 1
                    self.state['fails'][k] = n
                    wait = [300, 900, 3600, 10800, 43200][min(n - 1, 4)]
                    self.state['blocked'][k] = time.time() + wait
                    code = getattr(j.exc, 'code', 'coord_failed' if j.kind == 'coord' else 'job_error')
                    self.errors.append({'t': iso(), 'key': k, 'result': j.result, 'err': j.err[-300:], 'fails': n, 'retry_in_min': wait // 60})
                    self.errors = self.errors[-20:]
                    self.alert(code, key, 'error' if n >= 3 else 'warn', '%s (실패 %d번째, %d분 뒤 다시): %s' % (code, n, wait // 60, j.err[-200:]),
                               log=getattr(j.exc, 'logfile', None) or j.log, ttl_h=48, retry_in_min=wait // 60)
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
        wd = self.env.work(S, '_b%d' % n)
        job.workdir = wd
        # 진행 없음 기준 = 묶음 덩어리(12보드) 예상 시간 × 2 (예상: 직전 단계 실측 묶음 시간 중앙값/6, 없으면 5시간/6)
        est = 5.0
        hf = os.path.join(W, 'data/ft%s/step%d_board_hours.json' % (S, k - 1))
        if os.path.exists(hf):
            v = list(json.load(open(hf)).values())
            est = statistics.median(v) if v else est
        job.no_progress_h = max(float(self.cfg['loop'].get('no_progress_min_hours', 2.0)), 2 * est / 6 * 72 / 72)
        env = self.env.base(S, {'SPOT_PANEL_WORKERS': self.cget('cpu.workers_per_board'), 'FT_WORK': wd,
                                'LAB_RETRY_LIMIT': self.cget('cpu.workers_per_board')}, threads=1)
        if self.test_boards:
            env['FT_TEST_BOARDS'] = self.test_boards
        if self.no_push:
            env['FT_NO_PUSH'] = '1'
        fails = 0
        while True:
            left = [b for b in B if not os.path.exists(res(b)) and not self.bundle_taken(S, n, b)]
            job.progress = '%d/%d 묶음' % (len(B) - len(left), len(B))
            if job.cancelled:
                raise JobFail('cancelled', '원격 명령으로 취소')
            if not left:
                self.clean_board_work(S, n, B, W, g, br)
                return 'ok'
            if self.update_pending_since and len(left) < len(B) and False:
                return 'ok'
            log.info('ft%s 보드 %d: 시작/재개 — 남은 묶음 %s', S, n, left)
            job.t_cpu = job.t_file = time.time()
            rc = runlog(self.env.nice + [self.env.py, wrapper, left[0]], W, env, L)     # 묶음 하나씩: 묶음 경계에서 봇 코드 교체·일 바꾸기가 가능
            tail = '\n'.join(tail_lines(L, 40))
            last = tail.strip().splitlines()[-1] if tail.strip() else ''
            if 'FT_BOARD_ALL_DONE' in last:
                job.err_alert_clear = True
                self.clear('solver_rc', job.key); self.clear('process_dead', job.key); self.clear('push_failed', job.key)
                self.after_bundle(S, k, left[0], res(left[0]))
                if (self.update_pending_since or self.special_pending()) and any(not os.path.exists(res(b)) for b in B):
                    return 'ok'        # 묶음 경계: 새 봇 코드 교체 또는 특별 작업에 자리 내줌(claim 은 풀리고 나중에 이어서)
                continue
            if 'input sha256 differs' in tail:
                raise JobFail('input_changed', '입력이 바뀜(input sha256 differs) — 조정 쪽 확인 필요', L)
            fails += 1
            code = 'push_failed' if 'push failed 5 times' in tail else ('process_dead' if rc is not None and rc < 0 else 'solver_rc')
            self.alert(code, job.key, 'warn' if fails < 3 else 'error', '종료코드 %s, 마지막 줄: %s' % (rc, last[:200]), log=L, ttl_h=24)
            if fails >= 5:
                raise JobFail(code, '5번 연속 실패(종료코드 %s)' % rc, L)
            log.info('ft%s 보드 %d: 멈춤(%d번째) 종료코드 %s', S, n, fails, rc)
            time.sleep(60)
            if br in self.hub.heads:
                g.run('pull', '-q', '--no-edit', '--no-rebase', 'origin', br)
            g.run('merge', '-q', '--no-edit', 'origin/claude/ft%s_coord' % S)

    # --- 특별 작업(원격 명령 enqueue). 지금은 kind='3way_full' 하나: 세 명 플랍 전체(턴·리버 전부) 풀이 = lab_3way.sh 와 같은 계산
    SPECIAL_BR = 'claude/lab_3way_results'       # 결과 브랜치(작은 고아 브랜치). data/gto_3way_probe/<board>_full.{json,log}

    def special_pending(self):
        done = set(self.state.get('special_done', []))
        return [it for it in self.state['ctl'].get('special', []) if it['id'] not in done]

    def job_special(self, job):
        it = job.item
        if it.get('kind') != '3way_full':
            raise JobFail('special_bad', '모르는 특별 작업 %s' % it.get('kind'))
        board, iters = it['board'], int(it.get('iters', 300))
        L = os.path.join(self.root, 'logs', '3way_%s.log' % board)
        job.log = L
        src = it.get('term_branch', 'claude/ft3way_lab_1')
        self.hub.heads.update(self.hub.remote_heads(['refs/heads/' + src, 'refs/heads/' + self.SPECIAL_BR]))
        for br in (src, self.SPECIAL_BR):
            if br in self.hub.heads:
                self.hub.fetch(br, force=True)
        for br in (self.SPECIAL_BR, src):          # 이미 누가 올렸으면 끝
            if br in self.hub.heads and self.hub.show(br, 'data/gto_3way_probe/%s_full.json' % board):
                self.state.setdefault('special_done', []).append(it['id'])
                log.info('특별 작업 %s: 결과가 이미 %s 에 있음 — 건너뜀', it['id'], br)
                return 'ok'
        term = self.hub.show(src, it.get('term', 'tools/gto_3way_probe/term3_btn_sb_bb.json'))
        if not term:
            raise JobFail('special_bad', '끝점 파일을 %s 에서 못 읽음' % src)
        ex = os.path.join(self.env.calc, 'vendor/gtopen')
        if not os.path.exists(os.path.join(ex, 'crates/solver/examples/t2_3way.rs')):
            raise JobFail('special_bad', 't2_3way.rs 없음(%s)' % ex)
        env = self.env.base('special', threads=self.cfg['cpu']['total_cores'])
        if runlog(self.env.nice + ['cargo', 'build', '--release', '--example', 't2_3way'], ex, env, L) != 0:
            raise JobFail('solver_rc', 't2_3way 빌드 실패', L)
        wd = self.env.work('_3way')
        os.makedirs(wd, exist_ok=True)
        job.workdir = wd
        tf = os.path.join(wd, 'term.json')
        open(tf, 'wb').write(term)
        out = os.path.join(wd, '%s_full.json' % board)
        job.progress = '%s 반복 최대 %d' % (board, iters)
        rc = runlog(self.env.nice + [os.path.join(ex, 'target/release/examples/t2_3way'), 'solve', tf, board, str(iters), out, '--every', '25', '--target', '0.1'], wd, env, L)
        if job.cancelled:
            raise JobFail('cancelled', '원격 명령으로 취소')
        if rc != 0 or not os.path.exists(out):
            raise JobFail('solver_rc', 't2_3way 종료코드 %s' % rc, L)

        def fn(wt):
            d = os.path.join(wt, 'data/gto_3way_probe')
            os.makedirs(d, exist_ok=True)
            shutil.copy(out, d)
            if os.path.exists(out + '.partial'):
                shutil.copy(out + '.partial', d)
            open(os.path.join(d, '%s_full.log' % board), 'w').write('\n'.join(tail_lines(L, 400)) + '\n')
            return True
        if not self.hub.mutate(self.SPECIAL_BR, 'lab3way_wt', fn, '3way lab full flop: %s (autopilot)' % board):
            raise JobFail('push_failed', '결과 푸시 실패(%s)' % self.SPECIAL_BR, L)
        self.state.setdefault('special_done', []).append(it['id'])
        return 'ok'

    def bundle_taken(self, S, n, b):
        """이 묶음을 다른 브랜치가 이미 끝냈거나(done) 최근에 푸시 중이면 True — 최신 깃허브 읽기(view) 기준."""
        sv = self.view.get(S)
        info = sv.boards.get(n) if sv else None
        if not info:
            return False
        if info['bundles'].get(b) == 'done':
            return True
        lb = self.local_board_branches()
        for hb, age in info['holders'].get(b, []):
            if hb in lb:
                continue
            if age is None or age < self.cfg['loop']['active_hours']:
                return True
        return False

    def after_bundle(self, S, k, bundle, donef):
        """묶음이 끝났을 때: 재시도 뒤에도 안 풀린 플랍이 0.6% pot 을 넘으면 경고(판정은 collect 때 다시 한다)."""
        try:
            d = json.load(open(donef))
        except (OSError, ValueError):
            return
        lim = self.cfg['judge']['flop_accept_pct_pot']
        over = {x: (d.get('retried') or {}).get(x, {}).get('retry_pct_pot') for x in d.get('flop_failures_after_retry') or []}
        over = {x: v for x, v in over.items() if v is None or v > lim}
        if over:
            self.alert('flop_over_limit', (S, k, bundle), 'warn', '재시도 뒤에도 %.1f%% pot 초과 플랍: %s (collect 가 그 끝점을 정적 유지로 처리)' % (lim, over), ttl_h=72)

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

    def tool_env(self, S, W, sc, extra=None, threads=None, step=None):
        """도구(ft60.py, ft_solve.sh) 환경 변수. 도구가 구버전(설정 파일 이름)이냐 신버전(절대 경로)이냐에 맞춘다."""
        shp = os.path.join(W, 'tools/gto_fulltree/ft_solve.sh')
        sh = open(shp).read() if os.path.exists(shp) else ''
        fp = os.path.join(W, 'tools/gto_fulltree/ft60.py')
        ft = open(fp).read() if os.path.exists(fp) else ''
        cfgname = sc.get('cfg_file')
        cfg_abs = os.path.join(self.env.calc, 'data/gto_spot/plan_a', cfgname)
        e = self.env.base(S, extra, threads=threads or self.cget('cpu.coord_threads'))
        e['FT_WORK'] = self.env.work(S)
        e['FT_CFG'] = cfg_abs if 'FT_STOP_GAP' in sh else cfgname
        # 균형 패널(bal): 코디네이터 결정 — 이 단계부터. 이전 단계(prec)를 다시 모을 때는 prec
        ps = sc.get('panel_set_from_step')
        if ps is not None and 'FT_PANEL_SET' in ft and step is not None:
            e['FT_PANEL_SET'] = 'bal' if step >= ps else 'prec'
        return e

    def job_coord(self, job):
        S, k, unit = job.S, job.k, job.unit
        sc = self.cfg['stacks'][S]
        stage = unit.split('_', 1)[1]
        W, g = self.coord_wt(S, sc)
        L = os.path.join(self.root, 'logs', 'coord_ft%s.log' % S)
        job.workdir = self.env.work(S)
        job.no_progress_h = float(self.cfg['loop'].get('no_progress_coord_hours', 4.0))
        job.kill_on_hang = stage in ('solve', 'prepare')
        push_br = sc.get('coord_push_branch') or sc['coord_branch']
        paths = []
        self.sync_tools(S, k, sc, W, g, paths)
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
            raise JobFail('push_failed', '조정 브랜치 푸시 실패(병합 충돌 포함)', L)
        return 'ok'

    def sync_tools(self, S, k, sc, W, g, paths):
        """코디네이터 지시(11-26): 최신 도구(claude/ft60_3way_s5 의 행렬 끝점·FT_PANEL_SET·FT_REPLACE)를 기준으로, 스택 조정 브랜치 tools 가 더 새로우면 그것을 따른다.
        기준: 조정 브랜치의 ft60.py 에 필요한 기능 표시(tools_markers)가 다 있으면 그대로. 하나라도 없으면 tools_ref 의 tools/gto_fulltree 를 덮어쓰고(+ FT_MIN_REACH 3줄, ft100_coord 방식)
        균형 패널 파일을 복사해 같은 푸시에 넣는다. 세 명 끝점 표(ft60_add3way.py)는 쓰지 않는다(설정 three_way_tables=false, 사용자 승인 뒤 켜기)."""
        ref = sc.get('tools_ref')
        if not ref:
            return
        fp = os.path.join(W, 'tools/gto_fulltree/ft60.py')
        cur = open(fp).read() if os.path.exists(fp) else ''
        if all(m in cur for m in sc.get('tools_markers', [])):
            return
        cr = self.hub.cr
        with_retry(lambda: cr.run('fetch', '-q', '--depth=1', 'origin', '+refs/heads/%s:refs/remotes/origin/%s' % (ref, ref)), 3)
        files = cr.run('ls-tree', '-r', '--name-only', 'origin/' + ref, 'tools/gto_fulltree').out.split('\n')
        if not files or not files[0]:
            raise JobFail('tools_sync', '도구 기준 브랜치 %s 를 못 읽음' % ref)
        for f in files:
            if f.endswith(('.py', '.sh', '.rs', '.patch')) or '/diag/' in f:
                b = cr.run('show', 'origin/%s:%s' % (ref, f), raw=True).stdout
                dst = os.path.join(W, f)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                open(dst, 'wb').write(b)
        t = open(fp).read()
        if 'FT_MIN_REACH' not in t:       # ft100_coord 의 3줄(도달 >= 값인 끝점 전부)
            a1 = "N_TERMS = 40"
            a2 = "    pick = hu[:n]\n"
            assert a1 in t and a2 in t, 'FT_MIN_REACH 패치 위치를 못 찾음'
            t = t.replace(a1, "MIN_REACH = float(os.environ['FT_MIN_REACH']) if os.environ.get('FT_MIN_REACH') else None\nN_TERMS = 40", 1)
            t = t.replace(a2, "    pick = hu[:n] if MIN_REACH is None else [x for x in hu if x[0] >= MIN_REACH]\n", 1)
            open(fp, 'w').write(t)
        paths.append('tools/gto_fulltree')
        cp = sc.get('copy_panels')
        if cp:
            for f in cp['files']:
                b = cr.run('show', 'origin/%s:%s' % (cp['ref'], f), raw=True)
                if b.returncode != 0:
                    raise JobFail('tools_sync', '패널 파일을 못 읽음: %s' % f)
                dst = os.path.join(W, cp['to'], os.path.basename(f))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if not os.path.exists(dst):
                    open(dst, 'wb').write(b.stdout)
            paths.append(cp['to'])
        log.info('ft%s: 도구를 %s 기준으로 갱신(행렬 끝점·균형 패널·FT_MIN_REACH) — 조정 브랜치에 같이 올림', S, ref)

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
        env = self.tool_env(S, W, sc, sc.get('solve_env'), step=k)
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
        env = self.tool_env(S, W, sc, pe, step=k)
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
        env = self.tool_env(S, W, sc, step=k)
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
        env = self.tool_env(S, W, sc, step=k)
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
        """claude/lab_autopilot 새 커밋 → (1) 별도 릴리스 폴더에 받기 (2) 자체 점검(문법·판정 시험·드라이런) 통과할 때만 교체 예약 (3) 진행 중 일은 묶음 경계에서 교체.
        실패하면 이전 버전을 유지하고 '업데이트 실패'를 status 에 보고한다."""
        if not self.cfg['loop'].get('self_update') or not self.release or self.state.get('pending_release'):
            return
        R, br = self.repo, 'claude/lab_autopilot'
        if with_retry(lambda: R.run('fetch', '-q', 'origin', '+refs/heads/%s:refs/remotes/origin/%s' % (br, br)), 1).returncode != 0:
            return
        sha = R.run('rev-parse', 'origin/' + br).out
        if not sha or sha[:10] == self.release or sha in self.state.get('update_failed', []):
            return
        rd = os.path.join(self.root, 'releases', sha[:10])
        try:
            if not os.path.isdir(rd):
                with self.repo_lock:
                    R.run('worktree', 'add', '-q', '--detach', rd, sha, check=True)
            r = subprocess.run([sys.executable, os.path.join(rd, 'tools/gto_fulltree/lab_autopilot/autopilot.py'), 'selfcheck'], capture_output=True, text=True, timeout=900,
                               env=dict(os.environ, LAB_DRY='1', FT_NO_PUSH='1'))
            if r.returncode != 0:
                raise RuntimeError((r.stdout + r.stderr)[-600:])
        except Exception as e:      # noqa
            self.state.setdefault('update_failed', []).append(sha)
            self.state['update_failed_info'] = {'sha': sha, 't': iso(), 'err': str(e)[-600:]}
            self._save_state()
            shutil.rmtree(rd, ignore_errors=True)
            R.run('worktree', 'prune')
            log.info('업데이트 실패(%s) — 이전 버전 유지: %s', sha[:10], str(e)[-200:])
            return
        self.state['pending_release'] = sha
        self.state.pop('update_failed_info', None)
        self._save_state()
        self.update_pending_since = time.time()
        log.info('새 봇 코드 %s 자체 점검 통과 — 진행 중인 묶음이 끝나는 대로 교체', sha[:10])

    def maybe_restart(self):
        sha = self.state.get('pending_release')
        if not sha and not self.restart_requested:
            return
        alive = [j for j in self.jobs.values() if isinstance(j, Job) and j.is_alive()]
        if alive and not (sha and age_h(self.update_pending_since or time.time()) >= self.cfg['loop']['self_update_force_hours']):
            return
        if sha:
            rd = os.path.join(self.root, 'releases', sha[:10])
            tmp = os.path.join(self.root, 'current.tmp')
            if os.path.lexists(tmp):
                os.remove(tmp)
            os.symlink(rd, tmp)
            os.replace(tmp, os.path.join(self.root, 'current'))
            old = self.release
            self.state['release'] = sha[:10]
            self.state.pop('pending_release', None)
            for d in glob.glob(os.path.join(self.root, 'releases', '*')):
                if os.path.basename(d) not in (sha[:10], old):
                    self.repo.run('worktree', 'remove', '--force', d)
                    shutil.rmtree(d, ignore_errors=True)
            self.repo.run('worktree', 'prune')
        self._save_state()
        log.info('봇을 다시 시작합니다(%s)', '새 코드 ' + sha[:10] if sha else '원격 명령 restart')
        kill_leftovers()
        self.push_status(force=True)
        raise SystemExit(75)

    # --- 감시: 진행 없음(실제 계산 프로세스 CPU 와 결과 파일을 본다)
    def watchdog(self):
        if time.time() - self.t_watch < 120:
            return
        self.t_watch = now_ = time.time()
        clk = os.sysconf('SC_CLK_TCK')
        for key, j in list(self.jobs.items()):
            if not isinstance(j, Job) or not j.is_alive():
                continue
            if j.pids:
                t = sum(proc_ticks(pg) for pg in list(j.pids))
                if j.last_ticks is None or t - j.last_ticks >= clk * 5:        # 2분 사이 CPU 5초 이상 = 일하는 중
                    j.t_cpu = now_
                j.last_ticks = t
            else:
                j.t_cpu = now_                 # 지금 계산 프로세스 없음(git·대기 중)
            if j.workdir:
                j.t_file = max(j.t_file, newest_mtime(j.workdir))
            N = j.no_progress_h * 3600
            if j.pids and now_ - j.t_cpu > N:
                self.alert('no_progress', key, 'error', '계산 프로세스가 %.1f시간 동안 CPU 를 거의 안 씀(멈춘 것으로 판단) — 프로세스를 끄고 다시 시작' % ((now_ - j.t_cpu) / 3600), log=j.log, ttl_h=24)
                for pg in list(j.pids):
                    try:
                        os.killpg(pg, signal.SIGKILL)
                    except OSError:
                        pass
                j.t_cpu = now_
            elif j.pids and now_ - j.t_file > N and now_ - j.t_cpu < N:
                self.alert('no_progress', key, 'warn', '계산은 하는데 결과 파일이 %.1f시간 동안 안 늘어남' % ((now_ - j.t_file) / 3600), log=j.log, ttl_h=24)
            else:
                self.clear('no_progress', key)

    def derive_alerts(self):
        """상태에서 매 틱 다시 계산하는 경고(사라지면 해소)."""
        for code in ('disk_low', 'mem_low', 'stall_streak', 'needs_confirmation', 'fetch_failed', 'update_failed', 'paused', 'bot_restart_loop', 'push_failed_status'):
            self.clear(code)
        for k in [k for k, a in self.alerts.items() if a.get('expire') and a['expire'] < time.time()]:
            del self.alerts[k]
        free = shutil.disk_usage(self.cfg['work']).free / 2**30 if os.path.isdir(self.cfg['work']) else None
        if free is not None and free < self.cfg['disk']['min_free_gb']:
            self.alert('disk_low', 'disk', 'error', '디스크 여유 %.1f GB < %d GB — 새 일 중지, 정리 중' % (free, self.cfg['disk']['min_free_gb']))
        mem = mem_avail_gb()
        if mem is not None and mem < self.cfg['loop'].get('min_free_mem_gb', 3):
            self.alert('mem_low', 'mem', 'error', '메모리 여유 %.1f GB — 새 일 중지' % mem)
        for S, sv in self.view.items():
            v = sv.verdict
            if v and v['status'] in ('values_pass_pending_root', 'stop_report'):
                self.alert('needs_confirmation', S, 'warn', '%sbb 단계 %s: %s — %s' % (S, v['step'], v['status'], '; '.join(v['reasons'])))
            if getattr(sv, 'stall_streak', 0) >= 3:
                self.alert('stall_streak', S, 'warn', '%sbb 정체 경고 %d단계 연속(진행은 계속) — 코디네이터 확인' % (S, sv.stall_streak))
        if self.refresh_fail >= 3:
            self.alert('fetch_failed', 'github', 'warn', '깃허브 읽기 %d번 연속 실패' % self.refresh_fail)
        if self.push_fail >= 3:
            self.alert('push_failed_status', 'github', 'warn', '상태 푸시 %d번 연속 실패' % self.push_fail)
        if self.state.get('update_failed_info'):
            u = self.state['update_failed_info']
            self.alert('update_failed', u['sha'][:10], 'error', '봇 코드 업데이트 실패(이전 버전 유지): %s' % u['err'][-300:])
        if self.state['ctl']['paused'] or self.state['ctl']['paused_stacks']:
            self.alert('paused', 'ctl', 'warn', '원격 명령으로 일시정지 중 (%s)' % (self.state['ctl']['paused_stacks'] or '전체'))
        if len(self.state.get('starts', [])) > 3:
            self.alert('bot_restart_loop', 'bot', 'error', '봇이 1시간에 %d번 다시 시작됨(죽었다 살아남을 반복)' % len(self.state['starts']))

    # --- 원격 명령: claude/lab_status 의 control.json (코디네이터가 씀). 봇은 이 파일을 쓰지 않는다
    CONTROL_CFG_KEYS = ('cpu.boards_parallel', 'cpu.workers_per_board', 'cpu.coord_threads', 'loop.no_progress_min_hours', 'loop.no_progress_coord_hours',
                        'loop.active_hours', 'loop.stale_takeover_hours', 'loop.coord_idle_hours', 'loop.heartbeat_hours')

    def poll_control(self):
        if time.time() - self.t_control < self.cfg['loop'].get('control_poll_seconds', 300):
            return
        self.t_control = time.time()
        br = self.cfg['branches']['status']
        try:
            h = self.hub.remote_heads(['refs/heads/' + br])
            self.hub.heads.update(h) if hasattr(self.hub, 'heads') else setattr(self.hub, 'heads', h)
            if br not in h or not self.hub.fetch(br):
                return
            raw = self.hub.show(br, 'control.json')
        except Exception as e:      # noqa
            log.info('control.json 읽기 실패: %s', str(e)[-120:])
            return
        if not raw:
            return
        try:
            doc = json.loads(raw)
        except ValueError as e:
            self.alert('control_invalid', 'control.json', 'warn', 'control.json 이 JSON 이 아님: %s' % e, ttl_h=24)
            return
        self.clear('control_invalid')
        applied = self.state['ctl']['applied']
        seq = doc.get('seq', 0)
        for i, c in enumerate(doc.get('commands', [])):
            cid = str(c.get('id') or '%s:%d' % (seq, i))
            if cid in applied:
                continue
            try:
                ok, msg = self.apply_command(c)
            except Exception as e:      # noqa
                ok, msg = False, '%s: %s' % (type(e).__name__, e)
            applied[cid] = {'t': iso(), 'cmd': c.get('cmd'), 'ok': ok, 'msg': msg}
            log.info('원격 명령 %s %s → %s %s', cid, c.get('cmd'), 'OK' if ok else '실패', msg)
        if len(applied) > 60:
            for k in list(applied)[:-40]:
                del applied[k]
        self._save_state()

    def apply_command(self, c):
        ctl = self.state['ctl']
        cmd, S = c.get('cmd'), (str(c['stack']) if c.get('stack') is not None else None)
        if S is not None and S not in self.cfg['stacks']:
            return False, '모르는 스택 %s' % S
        if cmd == 'pause':
            if S:
                ctl['paused_stacks'] = sorted(set(ctl['paused_stacks']) | {S})
            else:
                ctl['paused'] = True
            return True, '새 일 시작 안 함(진행 중인 일은 계속)'
        if cmd == 'resume':
            if S:
                ctl['paused_stacks'] = [x for x in ctl['paused_stacks'] if x != S]
            else:
                ctl['paused'] = False
                ctl['paused_stacks'] = []
            return True, '다시 시작'
        if cmd in ('skip', 'cancel'):
            unit = c.get('unit')
            if not S or not unit:
                return False, 'stack 과 unit 필요'
            key = '%s|%s|%s' % (S, c.get('step', '*'), unit)
            if cmd == 'skip' and key not in ctl['skip']:
                ctl['skip'].append(key)
            n = 0
            for jk, j in self.jobs.items():
                if isinstance(j, Job) and j.is_alive() and jk[0] == S and jk[2] == unit and c.get('step') in (None, jk[1]):
                    j.cancel()
                    n += 1
            return True, '%s %s (실행 중 %d개 취소)' % (cmd, key, n)
        if cmd == 'retry':
            unit = c.get('unit')
            n = 0
            for d in (self.state['fails'], self.state['blocked']):
                for k in [k for k in d if (S is None or k.split('|')[0] == S) and (unit is None or k.split('|')[2] == unit)]:
                    del d[k]
                    n += 1
            ctl['skip'] = [k for k in ctl['skip'] if not ((S is None or k.split('|')[0] == S) and (unit is None or k.split('|')[2] == unit))]
            for k in [k for k in self.alerts if S is None or k[1].startswith(S + '|')]:
                if k[0] in ('job_error', 'solver_rc', 'process_dead', 'push_failed', 'input_changed', 'merge_conflict', 'no_progress', 'coord_failed', 'flop_over_limit'):
                    del self.alerts[k]
            return True, '실패·대기·건너뜀 기록 %d개 지움 — 다음 틱에 다시 시도' % n
        if cmd == 'priority':
            order = [str(x) for x in c.get('order', [])]
            if not order or any(x not in self.cfg['stacks'] for x in order):
                return False, 'order 는 스택 번호 목록'
            ctl['priority'] = order
            return True, '우선순위 %s' % order
        if cmd == 'stack':
            if not S:
                return False, 'stack 필요'
            ov = ctl['stack'].setdefault(S, {})
            for kx in ('enabled', 'boards', 'coord_actions'):
                if kx in c:
                    ov[kx] = bool(c[kx])
            return True, '스택 %s 설정 %s' % (S, ov)
        if cmd == 'config':
            path = c.get('path')
            if path not in self.CONTROL_CFG_KEYS:
                return False, '허용되지 않은 설정(%s)' % path
            ctl['cfg'][path] = c.get('value')
            return True, '%s = %s' % (path, c.get('value'))
        if cmd == 'enqueue':          # {"id":"x1","cmd":"enqueue","kind":"3way_full","board":"9c8d2c","iters":300}
            if c.get('kind') != '3way_full':
                return False, 'kind 는 3way_full 만'
            b = str(c.get('board', ''))
            if not re.fullmatch(r'([2-9TJQKA][cdhs]){3}', b):
                return False, '보드 형식 오류 %s' % b
            sid = str(c.get('item_id') or '3way_' + b)
            if any(x['id'] == sid for x in ctl['special']):
                return True, '이미 대기열에 있음 %s' % sid
            it = {'id': sid, 'kind': '3way_full', 'board': b, 'iters': int(c.get('iters', 300))}
            for kx in ('term', 'term_branch', 'min_mem_gb'):
                if kx in c:
                    it[kx] = c[kx]
            ctl['special'].append(it)
            return True, '특별 작업 대기열 추가 %s (대기 %d개) — 돌고 있는 묶음이 끝나면 시작' % (sid, len(self.special_pending()))
        if cmd == 'dequeue':
            sid = str(c.get('item_id') or '3way_' + str(c.get('board', '')))
            n0 = len(ctl['special'])
            ctl['special'] = [x for x in ctl['special'] if x['id'] != sid]
            for jk, j in self.jobs.items():
                if isinstance(j, Job) and j.is_alive() and j.kind == 'special' and jk[2] == sid:
                    j.cancel()
            return True, '대기열에서 뺌 %s (%d개)' % (sid, n0 - len(ctl['special']))
        if cmd == 'restart':
            self.restart_requested = True
            return True, '일이 끝나면 봇을 다시 시작'
        return False, '모르는 명령 %s' % cmd

    def status_doc(self):
        """claude/lab_status 의 status.json. 코디네이터 규칙: status != "ok" 이면 alerts 를 읽고 조치(오류 있음). 형식은 docs/LAB_AUTOPILOT.md 7장."""
        al = []
        for a in sorted(self.alerts.values(), key=lambda a: (a['severity'] != 'error', a['since'])):
            x = {k: a[k] for k in ('code', 'severity', 'key', 'msg', 'since', 'last', 'count')}
            x['ctx'] = a.get('ctx') or {}
            if a.get('log'):
                x['log_file'] = os.path.basename(a['log'])
                x['log_tail'] = tail_lines(a['log'], 200)
            al.append(x)
        status = 'error' if any(a['severity'] == 'error' for a in al) else ('warn' if al else 'ok')
        d = {'schema': 'lab_status_v1', 'status': status, 'time': iso(), 'host': socket.gethostname(), 'owner': self.cfg['owner'],
             'uptime_h': round((time.time() - self.t0) / 3600, 1), 'mode': 'dry' if self.dry else ('no_push' if self.no_push else 'live'),
             'code_release': self.release, 'code_sha': Git(HERE).run('rev-parse', '--short', 'HEAD').out,
             'update': {'pending': (self.state.get('pending_release') or '')[:10] or None, 'failed': self.state.get('update_failed_info')},
             'cpu': {'budget': self.cfg['cpu']['total_cores'], 'in_use': self.running_cost(), 'load': os.getloadavg()},
             'mem_avail_gb': None if mem_avail_gb() is None else round(mem_avail_gb(), 1),
             'disk_free_gb': round(shutil.disk_usage(self.cfg['work']).free / 2**30, 1) if os.path.isdir(self.cfg['work']) else None,
             'paused': {'all': self.state['ctl']['paused'], 'stacks': self.state['ctl']['paused_stacks']},
             'jobs': [{'stack': j.S, 'step': j.k, 'unit': j.unit, 'started': j.started, 'progress': j.progress,
                       'cpu_idle_min': round((time.time() - j.t_cpu) / 60), 'file_idle_min': round((time.time() - j.t_file) / 60)}
                      for j in self.jobs.values() if isinstance(j, Job) and j.is_alive()],
             'stacks': {}, 'alerts': al, 'recent_errors': self.errors[-10:],
             'control': {'applied': dict(list(self.state['ctl']['applied'].items())[-15:]), 'skip': self.state['ctl']['skip'], 'priority': self.state['ctl']['priority'],
                         'cfg_overrides': self.state['ctl']['cfg'], 'stack_overrides': self.state['ctl']['stack']},
             'special': {'queue': [x['id'] for x in self.special_pending()], 'done': self.state.get('special_done', [])[-10:]},
             'blocked': {k: iso(dt.datetime.fromtimestamp(t, dt.timezone.utc)) for k, t in self.state['blocked'].items() if t > time.time()}}
        for S, sv in self.view.items():
            e = {'phase': sv.phase, 'why': sv.why, 'step': sv.K, 'coord_tip_age_h': None if sv.last_commit_age_h is None else round(sv.last_commit_age_h, 1),
                 'stall_streak': getattr(sv, 'stall_streak', 0)}
            if sv.boards:
                e['boards'] = {n: {'done': b['all_done'], 'bundles': b['bundles'], 'tip_age_h': None if b['tip_age_h'] is None else round(b['tip_age_h'], 1),
                                   'claim': (self.claims.get((S, sv.K, 'board_%d' % n)) or {}).get('owner')} for n, b in sv.boards.items()}
            if sv.verdict:
                v = sv.verdict
                e['verdict'] = {'step': v['step'], 'status': v['status'], 'reasons': v['reasons'], 'warnings': v['warnings'], 'pass_D_le_U': '%d/%d' % (v['metrics']['pass_D_le_U'], v['metrics']['seats']),
                                'dou_median': v['metrics']['dou_median'], 'dM_vs_prev_median': v['metrics']['dM_vs_prev_median'], 'needs_confirmation': v['needs_confirmation']}
            d['stacks'][S] = e
        return d

    def md_status(self, d):
        l = ['# 연구실 봇 상태: **%s** — %s (%s)' % (d['status'], d['time'], d['mode']), '', '- 호스트 %s, 가동 %.1f시간, 코드 %s, CPU %s/%s 코어, 메모리 여유 %s GB, 디스크 여유 %s GB' % (
            d['host'], d['uptime_h'], d['code_release'] or d['code_sha'], d['cpu']['in_use'], d['cpu']['budget'], d['mem_avail_gb'], d['disk_free_gb'])]
        if d.get('special', {}).get('queue'):
            l += ['- 특별 작업 대기열(먼저 함): ' + ', '.join(d['special']['queue'])]
        l += ['- 지금 하는 일: ' + (', '.join('ft%s 단계%s %s(%s)' % (j['stack'], j['step'], j['unit'], j['progress']) for j in d['jobs']) or '없음 (대기)')]
        for S, e in d['stacks'].items():
            l.append('- **%sbb** 단계 %s: %s — %s' % (S, e['step'], e['phase'], e['why']))
            if 'verdict' in e:
                v = e['verdict']
                l.append('  - 판정(단계 %s): %s, D≤U %s, D/U 중앙값 %s' % (v['step'], v['status'], v['pass_D_le_U'], None if v['dou_median'] is None else round(v['dou_median'], 2)))
        if d['alerts']:
            l += ['', '## 경고 (status != ok)'] + ['- [%s] %s %s: %s (x%d, 처음 %s)' % (a['severity'], a['code'], a['key'], a['msg'][:250], a['count'], a['since']) for a in d['alerts']]
        if d['control']['applied']:
            l += ['', '## 원격 명령 처리'] + ['- %s %s: %s %s' % (k, v['cmd'], 'OK' if v['ok'] else '실패', v['msg']) for k, v in list(d['control']['applied'].items())[-5:]]
        return '\n'.join(l) + '\n'

    def push_status(self, force=False):
        """푸시 규칙: 경고 구성이 바뀌었거나 원격 명령을 새로 처리했으면 바로(최소 5분 간격), 아니면 heartbeat_hours(기본 6시간)마다 한 번. 같은 오류가 계속돼도 6시간마다만 다시 올린다."""
        d = self.status_doc()
        json.dump(d, open(os.path.join(self.root, 'state/status.json'), 'w'), indent=1, ensure_ascii=False)
        sig = hashlib.sha256(json.dumps([[a['code'], a['key'], a['severity']] for a in d['alerts']] + [sorted(d['control']['applied'])] + [d['status']]).encode()).hexdigest()
        due = force or sig != self.pushed_sig or time.time() - self.t_pushed >= self.cget('loop.heartbeat_hours') * 3600
        if not due or (not force and time.time() - self.t_pushed < 300):
            return
        tail = '\n'.join(tail_lines(os.path.join(self.root, 'logs/autopilot.log'), 200))
        self.t_pushed, self.pushed_sig = time.time(), sig
        if self.no_push:
            return
        ok = self.hub.push_status({'status.json': json.dumps(d, indent=1, ensure_ascii=False), 'status.md': self.md_status(d), 'log_tail.txt': tail + '\n'})
        self.push_fail = 0 if ok else self.push_fail + 1
        if not ok:
            self.pushed_sig = None

    def tick(self):
        self.reap()
        if time.time() - self.t_refresh >= self.cfg['loop']['github_refresh_seconds'] or not self.view:
            try:
                self.refresh()
                self.refresh_fail = 0
            except Exception as e:      # noqa
                self.refresh_fail += 1
                log.info('깃허브 읽기 실패(%d번째, 다음에 다시): %s', self.refresh_fail, str(e)[-200:])
                self.t_refresh = time.time() - self.cfg['loop']['github_refresh_seconds'] + 60
        if time.time() - self.t_hb > self.cfg['loop']['claim_heartbeat_minutes'] * 60 and not self.no_push:
            self.hub.heartbeat([k for k, j in self.jobs.items() if isinstance(j, Job) and j.is_alive()])
            self.t_hb = time.time()
        if time.time() - self.t_update > 300:
            self.t_update = time.time()
            self.self_update()
        self.poll_control()
        self.watchdog()
        if self.view:
            try:
                self.schedule()
            except Exception:       # noqa
                log.exception('스케줄 오류')
        self.cleanup()
        self.derive_alerts()
        try:
            self.push_status()
        except Exception as e:      # noqa
            self.push_fail += 1
            log.info('상태 푸시 실패: %s', str(e)[-150:])
        self.maybe_restart()

    def run_forever(self):
        log.info('lab autopilot 시작 (%s) 코어 %s, 보드 %d×워커 %d, nice %d, 코드 %s', 'dry' if self.dry else ('no_push' if self.no_push else 'live'),
                 self.cfg['cpu']['total_cores'], self.cfg['cpu']['boards_parallel'], self.cfg['cpu']['workers_per_board'], self.cfg['cpu']['nice'], self.release or 'dev')
        kill_leftovers()
        if self.state.get('running'):       # 지난 실행이 정상 종료 표시 없이 끝났다 = 죽었다 살아난 것
            self.alert('bot_restarted', 'bot', 'warn', '봇이 비정상 종료 후 다시 시작됨(이전 실행이 끝났다는 기록 없음) — 로그 확인', log=os.path.join(self.root, 'logs/main.log'), ttl_h=24)
        self.state['running'] = True
        self._save_state()
        stop = []
        signal.signal(signal.SIGTERM, lambda *a: stop.append(1))
        signal.signal(signal.SIGINT, lambda *a: stop.append(1))
        self.push_status(force=True)
        try:
            while not stop:
                try:
                    self.tick()
                except SystemExit:
                    raise
                except Exception:       # noqa
                    log.exception('루프 오류(계속)')
                idle = not any(isinstance(j, Job) and j.is_alive() for j in self.jobs.values())
                wait = self.cfg['loop']['idle_wait_seconds'] if idle and self.view and not self.state.get('pending_release') else self.cfg['loop']['poll_seconds']
                if idle:
                    log.info('할 일 없음(모두 끝났거나 다른 쪽이 잡음) — %d분 뒤 다시 확인', wait // 60)
                for _ in range(int(wait)):
                    if stop:
                        break
                    time.sleep(1)
            log.info('종료 신호 — 계산을 끄고 정리(끝난 덩어리는 푸시돼 있어 이어서 됨)')
            kill_leftovers()
            self.state['running'] = False
            self._save_state()
            self.push_status(force=True)
        except SystemExit:
            self.state['running'] = False
            self._save_state()
            raise

# ----------------------------------------------------------------------------- 자체 점검(새 버전 교체 전)
def selfcheck(cfg):
    """새 코드를 쓰기 전 점검: (1) 문법 (2) 판정 함수가 저장소의 실제 보고서와 문서 숫자를 재현 (3) 드라이런(깃허브 읽기 → 계획). 하나라도 실패하면 1."""
    try:
        for f in glob.glob(os.path.join(HERE, '*.py')):
            compile(open(f).read(), f, 'exec')
        subprocess.run(['bash', '-n', os.path.join(HERE, 'lab_autopilot.sh')], check=True)
        repo = os.path.abspath(os.path.join(HERE, '../../..'))
        rp = os.path.join(repo, 'data/ft30/step1/collect/report.json')
        if os.path.exists(rp):
            m = J.summarize(json.load(open(rp)))
            assert (m['pass_D_le_U'], m['seats']) == (5, 50) and abs(m['dou_median'] - 3.13) < 0.01, '판정 함수가 ft30 1단계 숫자를 못 재현: %s' % m
        assert J.cycling([5, 8, 3]) and not J.cycling([5, 4, 3])
        json.dumps(cfg)
        ap = Autopilot(cfg, dry=True)
        try:
            ap.refresh()
        except Exception as e:      # noqa  (네트워크 일시 오류는 점검 실패로 안 침)
            print('드라이런: 깃허브 읽기 건너뜀(%s)' % str(e)[-100:])
        else:
            plan = ap.candidates()
            ap.status_doc()
            print('드라이런 OK: 지금 할 수 있는 일 %d개' % len(plan))
        print('SELFCHECK_OK')
        return 0
    except Exception as e:      # noqa
        print('SELFCHECK_FAIL', type(e).__name__, str(e)[-500:])
        return 1


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
    elif cmd == 'selfcheck':
        sys.exit(selfcheck(cfg))
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
