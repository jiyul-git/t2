#!/usr/bin/env python3
"""First install creates system/ + personal/; updates replace system files only.

Repository: python ui/tools/install_game.py install|update <T2 folder>
Install ZIP: python install.py [<T2 folder>]
Update ZIP:  python update.py <existing T2 folder>
Stop the game server before updating or migrating an existing wallet.
"""
import argparse
import contextlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile

STATIC_DATA = {'pf_rank.json', 'style_sig.json', 'style_prior.json'}
MARKERS = {'UI_SERVER_DIR', 'UI_SOURCE'}


@contextlib.contextmanager
def prepared_system(script=None):
    script = Path(script or __file__).resolve()
    packaged = script.parent / 'system'
    if (packaged / 'UI_SERVER_DIR').is_file():
        yield packaged
        return
    repo = script.parents[2]
    with tempfile.TemporaryDirectory(prefix='t2_system_package_') as tmp:
        target = Path(tmp) / 'system'
        env = dict(os.environ, T2_TELEMETRY='0')
        subprocess.run([sys.executable, str(repo / 'ui/tools/setup_run_dir.py'), str(target)],
                       check=True, stdout=subprocess.DEVNULL, env=env)
        yield target


def system_files(source):
    """The source was made with setup_run_dir's allowlist; never ship runtime data."""
    source = Path(source)
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('시스템 패키지에 심볼릭 링크를 포함할 수 없습니다.')
        if not path.is_file():
            continue
        rel = path.relative_to(source)
        if len(rel.parts) == 1:
            keep = path.suffix == '.py' or path.name in STATIC_DATA | MARKERS
        elif rel.parts[0] == 'coarse_params':
            keep = len(rel.parts) == 2 and path.suffix == '.json'
        else:
            keep = (rel.parts[0] == 'web' and path.suffix.lower() in
                    {'.js', '.css', '.html', '.svg', '.png', '.jpg', '.jpeg', '.webp',
                     '.ico', '.woff', '.woff2', '.ttf', '.mp4', '.webm'})
        if keep:
            yield rel


def copy_system(source, target):
    source, target = Path(source).resolve(), Path(target)
    if target.is_symlink():
        raise ValueError('시스템 폴더의 심볼릭 링크를 따라 업데이트하지 않습니다.')
    target.mkdir(parents=True, exist_ok=True)
    for rel in system_files(source):
        dest = target / rel
        if any(p.is_symlink() for p in [dest, *dest.parents] if p != target.parent):
            raise ValueError('시스템 파일의 심볼릭 링크를 따라 업데이트하지 않습니다.')
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source / rel != dest.resolve():
            shutil.copy2(source / rel, dest)


def _load_personal_module(source):
    sys.path.insert(0, str(source))
    import personal_data
    return personal_data


def _migrate_wallet(legacy, data, pd):
    legacy = Path(legacy).resolve()
    old = legacy / 'userdata' if (legacy / 'userdata' / pd.DATABASE).is_file() else legacy
    src = pd.require_wallet(old)
    data.mkdir(parents=True, exist_ok=True)
    dest = data / pd.DATABASE
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        with contextlib.closing(sqlite3.connect(src.as_uri() + '?mode=ro', uri=True)) as old_db:
            with contextlib.closing(sqlite3.connect(dest)) as new_db:
                old_db.backup(new_db)
                new_db.commit()
        pd.require_wallet(data)
        config = old / 'schedule.json'
        if config.is_file() and not (data / 'schedule.json').exists():
            shutil.copy2(config, data / 'schedule.json')
    except BaseException:
        dest.unlink(missing_ok=True)
        raise


def install(source, destination, mode='install', personal_dir=None, migrate_from=None):
    source = Path(source).resolve()
    if any(not (source / name).is_file() for name in
           ('personal_data.py', 'tournament_store.py', 'scheduled_runtime.py')):
        raise ValueError('선택한 시스템 버전은 개인 지갑 설치를 지원하지 않습니다.')
    root = Path(destination).expanduser().resolve()
    system, personal = root / 'system', root / 'personal'
    pd = _load_personal_module(source)
    pd.outside_system(personal, system)
    binding = personal / pd.MANIFEST
    exists = binding.is_file()
    if mode == 'update' and not exists:
        raise pd.PersonalDataError('기존 개인 지갑 연결 정보가 없습니다. 시스템 업데이트를 중단합니다.')
    if exists:
        data = pd.outside_system(pd.read_binding(personal), system)
        if os.environ.get('T2_DATA_DIR') and pd.normalized(os.environ['T2_DATA_DIR']) != data:
            raise pd.PersonalDataError('T2_DATA_DIR가 기존 개인 지갑과 다릅니다. 업데이트를 중단합니다.')
        if personal_dir is not None and pd.normalized(personal_dir) != data:
            raise pd.PersonalDataError('재설치로 기존 개인 지갑의 위치를 바꿀 수 없습니다.')
        if migrate_from is not None:
            raise pd.PersonalDataError('기존 지갑에 다른 지갑을 덮어쓰지 않습니다.')
        pd.require_wallet(data)
    else:
        if migrate_from is None and any((old / 'userdata' / pd.DATABASE).exists()
                                        for old in (root, system)):
            raise pd.PersonalDataError('기존 지갑이 발견되었습니다. --migrate-from으로 이전해 주세요. 새 지갑은 만들지 않습니다.')
        data = pd.outside_system(personal_dir or os.environ.get('T2_DATA_DIR') or personal, system)
        if mode != 'install':
            raise ValueError('최초 설치가 필요합니다.')
        if (data / pd.DATABASE).exists():
            if migrate_from is not None:
                raise pd.PersonalDataError('기존 지갑에 이전 파일을 덮어쓰지 않습니다.')
            pd.require_wallet(data)
        elif migrate_from is not None:
            # Validate the source before copying system files or creating a wallet.
            old = Path(migrate_from).expanduser().resolve()
            old = old / 'userdata' if (old / 'userdata' / pd.DATABASE).is_file() else old
            pd.require_wallet(old)
    # Update mode never creates, copies, or mutates anything in personal/.
    copy_system(source, system)
    if not exists:
        if not (data / pd.DATABASE).exists():
            if migrate_from is not None:
                _migrate_wallet(migrate_from, data, pd)
            else:
                data.mkdir(parents=True, exist_ok=True)
                subprocess.run([sys.executable, '-c',
                    'import sys; from tournament_store import Store; Store(root=sys.argv[1])',
                    str(data)], cwd=system, check=True)
        pd.require_wallet(data)
        personal.mkdir(parents=True, exist_ok=True)
        # Relative binding survives moving the entire installation together.
        linked = '.' if data == personal.resolve() else str(data)
        manifest = {'version': 1, 'data_dir': linked}
        temp = personal / (pd.MANIFEST + '.tmp')
        temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(temp, binding)
    return system, data


def main():
    script = Path(__file__).resolve()
    packaged = (script.parent / 'system' / 'UI_SERVER_DIR').is_file()
    ap = argparse.ArgumentParser(description=__doc__)
    if packaged:
        mode = 'update' if script.stem == 'update' else 'install'
        ap.add_argument('destination', nargs=None if mode == 'update' else '?',
                        default=str(script.parent))
    else:
        ap.add_argument('mode', choices=('install', 'update'))
        ap.add_argument('destination', nargs='?', default=str(Path.home() / 'T2'))
    ap.add_argument('--personal-dir', help='최초 설치 시 지정하는 외부 개인 데이터 폴더')
    ap.add_argument('--migrate-from', help='기존 지갑 폴더 또는 기존 실행 폴더 (서버 종료 후 사용)')
    args = ap.parse_args()
    mode = mode if packaged else args.mode
    if mode == 'update' and (args.personal_dir is not None or args.migrate_from is not None):
        ap.error('업데이트는 시스템만 변경합니다. 개인 폴더 지정/이전 옵션은 최초 설치에서 사용하세요.')
    try:
        with prepared_system(script) as source:
            system, data = install(source, args.destination, mode, args.personal_dir, args.migrate_from)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        ap.exit(1, str(exc) + '\n')
    print('시스템: %s' % system)
    print('개인 지갑: %s' % data)
    print('완료: %s' % ('시스템만 업데이트' if mode == 'update' else '시스템 + 개인 지갑 설치'))
    print('실행: cd "%s" 후 python ui_server.py' % system)


if __name__ == '__main__':
    main()
