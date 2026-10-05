"""Personal storage stays outside replaceable game code; stdlib only."""
import contextlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile

DATABASE = 'tournaments.sqlite3'
MANIFEST = 'installation.json'


class PersonalDataError(ValueError):
    pass


def normalized(path):
    return Path(path).expanduser().resolve()


def outside_system(data, system):
    data, system = normalized(data), normalized(system)
    if data == system or system in data.parents or data in system.parents:
        raise PersonalDataError('개인 데이터와 시스템 폴더는 서로 포함되지 않는 별도 폴더여야 합니다.')
    return data


def default_data_dir(env=None, platform=None):
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    home = Path(env.get('USERPROFILE') or env.get('HOME') or Path.home())
    if platform == 'win32':
        base = Path(env.get('LOCALAPPDATA') or home / 'AppData' / 'Local')
    elif platform == 'darwin':
        base = home / 'Library' / 'Application Support'
    else:
        base = Path(env.get('XDG_DATA_HOME') or home / '.local' / 'share')
    return normalized(base / 'T2' / 'personal')


def read_binding(personal):
    personal = normalized(personal)
    try:
        obj = json.loads((personal / MANIFEST).read_text(encoding='utf-8'))
        if obj['version'] != 1 or not isinstance(obj['data_dir'], str) or not obj['data_dir']:
            raise ValueError('unsupported binding')
        data = normalized(personal / obj['data_dir'])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise PersonalDataError('개인 지갑 연결 정보를 찾거나 읽을 수 없습니다. 개인 폴더를 복원해 주세요.') from exc
    return data


def require_wallet(data):
    """Read-only validation: an update must never create an account or grant."""
    path = normalized(data) / DATABASE
    if not path.is_file():
        raise PersonalDataError('기존 개인 지갑을 찾을 수 없습니다. 새 지갑을 생성하지 않고 중단합니다.')
    try:
        # Even SQLite mode=ro can create/update WAL shared-memory files. Validate
        # a private copy so updating code never writes into personal storage.
        # Installation updates/migration are performed with the server stopped.
        with tempfile.TemporaryDirectory(prefix='t2_wallet_check_') as tmp:
            snapshot = Path(tmp) / DATABASE
            shutil.copyfile(path, snapshot)
            wal = Path(str(path) + '-wal')
            if wal.is_file():
                shutil.copyfile(wal, Path(str(snapshot) + '-wal'))
            with contextlib.closing(sqlite3.connect(snapshot.as_uri() + '?mode=ro', uri=True)) as db:
                db.execute('PRAGMA query_only=ON')
                db.execute('BEGIN')
                if db.execute('PRAGMA user_version').fetchone()[0] != 1:
                    raise ValueError('unsupported wallet schema')
                balance = db.execute("SELECT balance FROM players WHERE id='hero'").fetchone()
                total = db.execute('SELECT COALESCE(SUM(delta),0) FROM ledger').fetchone()[0]
                if balance is None or balance[0] < 0 or balance[0] != total:
                    raise ValueError('invalid wallet ledger')
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise PersonalDataError('개인 지갑을 검증할 수 없습니다. 기존 파일을 보존하고 중단합니다.') from exc
    return path


def resolve_data_dir(system_root, env=None):
    env = os.environ if env is None else env
    system = normalized(system_root)
    personal = system.parent / 'personal'
    installed = system.name == 'system' and (personal / MANIFEST).is_file()
    configured = env.get('T2_DATA_DIR')
    if installed:
        outside_system(personal, system)
        bound = outside_system(read_binding(personal), system)
        if configured and normalized(configured) != bound:
            raise PersonalDataError('이 설치에 연결된 개인 지갑과 T2_DATA_DIR가 다릅니다. 지갑을 바꾸지 않고 중단합니다.')
        require_wallet(bound)
        return bound
    if system.name == 'system':
        raise PersonalDataError('개인 지갑 설치 정보가 없습니다. 최초 설치를 실행하거나 personal 폴더를 복원해 주세요.')
    if (system / 'userdata' / DATABASE).exists():
        raise PersonalDataError('시스템 폴더에 기존 지갑이 있습니다. 설치 도구의 --migrate-from으로 이전해 주세요.')
    return outside_system(configured or default_data_dir(env), system)
