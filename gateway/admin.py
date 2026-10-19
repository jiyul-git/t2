#!/usr/bin/env python3
"""T2 online admin: list / disable / enable / delete accounts, and back up the player data.

    python3 gateway/admin.py [--config gateway/gateway.json] list
    python3 gateway/admin.py disable <uid|email>
    python3 gateway/admin.py enable  <uid|email>
    python3 gateway/admin.py delete  <uid|email> [--yes]
    python3 gateway/admin.py backup

Edits accounts.json (a running gateway re-reads it on the next request). Standard library only.
"""
import argparse
import datetime
import json
import os
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gateway as G

KEEP_BACKUPS = 7
WALLET = 'tournaments.sqlite3'


def chips(data_root, uid):
    path = os.path.join(data_root, uid, WALLET)
    if not os.path.exists(path):
        return '-'
    try:
        db = sqlite3.connect('file:%s?mode=ro' % path, uri=True, timeout=5)
        try:
            row = db.execute("SELECT balance FROM players WHERE id='hero'").fetchone()
        finally:
            db.close()
        return '{:,}'.format(row[0]) if row else '-'
    except sqlite3.Error:
        return '?'


def nickname(data_root, uid):
    try:
        with open(os.path.join(data_root, uid, 'profile.json'), encoding='utf-8') as f:
            return str(json.load(f).get('nickname') or '-')
    except (OSError, ValueError, AttributeError):
        return '-'


def cmd_list(cfg, acc, args):
    rows = [('uid', 'email', 'nickname', 'chips', 'status', 'last login')]
    for uid, r in sorted(acc.all().items(), key=lambda kv: kv[1].get('created') or 0):
        ll = r.get('last_login')
        rows.append((uid, r.get('email') or '-', nickname(cfg['data_root'], uid), chips(cfg['data_root'], uid),
                     r.get('status', '?'), time.strftime('%Y-%m-%d %H:%M', time.localtime(ll)) if ll else '-'))
    widths = [max(len(str(r[i])) for r in rows) for i in range(len(rows[0]))]
    for r in rows:
        print('  '.join(str(c).ljust(w) for c, w in zip(r, widths)).rstrip())
    print('%d account(s)' % (len(rows) - 1))
    return 0


def target(acc, args):
    uid = acc.find(args.target)
    if not uid:
        sys.exit('계정을 찾을 수 없습니다: %s' % args.target)
    return uid


def cmd_status(want):
    def run(cfg, acc, args):
        uid = target(acc, args)
        status = want
        if want == 'enable':            # back to what the account was before: signed up or still pending
            status = 'active' if acc.get(uid).get('agreed_at') else 'pending'
        acc.set_status(uid, status)
        print('%s: %s' % (uid, status))
        return 0
    return run


def cmd_delete(cfg, acc, args):
    uid = target(acc, args)
    rec = acc.get(uid)
    if not args.yes:
        ans = input('%s (%s) 계정과 모든 데이터를 삭제합니다. 계속할까요? [y/N] ' % (uid, rec.get('email') or '-'))
        if ans.strip().lower() not in ('y', 'yes'):
            print('취소했습니다')
            return 1
    acc.delete(uid)          # first: a running gateway stops this player's game server on its next request
    G.delete_user_files(cfg, uid)
    print('삭제했습니다: %s' % uid)
    return 0


def cmd_backup(cfg, acc, args):
    bdir = cfg['backup_dir']
    G.mkdir_private(bdir)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M')
    out = os.path.join(bdir, 't2-%s.tar.gz' % stamp)
    with tempfile.TemporaryDirectory(prefix='t2_backup_') as tmp:
        stage = os.path.join(tmp, 't2-' + stamp)
        os.makedirs(os.path.join(stage, 'users'))
        shutil.copy2(acc.path, os.path.join(stage, 'accounts.json'))
        n = 0
        for uid in sorted(os.listdir(cfg['data_root'])) if os.path.isdir(cfg['data_root']) else []:
            src = os.path.join(cfg['data_root'], uid)
            if not os.path.isdir(src):
                continue
            dst = os.path.join(stage, 'users', uid)
            os.makedirs(dst)
            for name in os.listdir(src):
                path = os.path.join(src, name)
                if name.endswith(('-wal', '-shm', '-journal')):
                    continue                               # folded into the backup copy below
                if name.endswith(('.sqlite3', '.db')):
                    # online backup: a consistent copy even while the game server writes
                    s = sqlite3.connect('file:%s?mode=ro' % path, uri=True, timeout=10)
                    d = sqlite3.connect(os.path.join(dst, name))
                    try:
                        s.backup(d)
                    finally:
                        d.close()
                        s.close()
                elif os.path.isdir(path):
                    shutil.copytree(path, os.path.join(dst, name))
                elif os.path.isfile(path):
                    shutil.copy2(path, os.path.join(dst, name))
            n += 1
        fd = os.open(out + '.tmp', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'wb') as raw, tarfile.open(fileobj=raw, mode='w:gz') as tar:
            tar.add(stage, arcname=os.path.basename(stage))
        os.replace(out + '.tmp', out)
    os.chmod(out, 0o600)
    old = sorted(f for f in os.listdir(bdir) if f.startswith('t2-') and f.endswith('.tar.gz'))
    for f in old[:-KEEP_BACKUPS]:
        os.remove(os.path.join(bdir, f))
    print('백업: %s (%d명)' % (out, n))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--config', default=os.path.join(G.HERE, 'gateway.json'))
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list')
    for name in ('disable', 'enable', 'delete'):
        p = sub.add_parser(name)
        p.add_argument('target', help='uid 또는 이메일')
        if name == 'delete':
            p.add_argument('--yes', action='store_true', help='확인 질문 생략')
    sub.add_parser('backup')
    args = ap.parse_args(argv)
    cfg = G.load_config(args.config)
    acc = G.Accounts(cfg['state_dir'])
    fn = {'list': cmd_list, 'disable': cmd_status('disabled'), 'enable': cmd_status('enable'),
          'delete': cmd_delete, 'backup': cmd_backup}[args.cmd]
    return fn(cfg, acc, args)


if __name__ == '__main__':
    sys.exit(main())
