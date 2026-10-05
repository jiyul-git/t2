#!/usr/bin/env python3
"""Exercise actual ZIP installers and wallet preservation across code replacement."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import personal_data as PD
import tournament_store as TS
from build_game_packages import build_packages

SPEC = [dict(fmt='standard', minute=0, buyin=1000, bot_entries=2,
             late_minutes=10, max_reentries=2)]


def file_hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def wallet_rows(root):
    with contextlib.closing(sqlite3.connect(root / PD.DATABASE)) as db:
        return {table: db.execute('SELECT * FROM ' + table + ' ORDER BY rowid').fetchall()
                for table in ('players', 'ledger', 'tournaments', 'entries', 'meta')}


class PersonalInstallationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packages = tempfile.TemporaryDirectory(prefix='t2_package_verify_')
        cls.install_zip, cls.update_zip = build_packages(cls.packages.name)

    @classmethod
    def tearDownClass(cls):
        cls.packages.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='t2_personal_install_')
        self.base = Path(self.tmp.name)
        self.root = self.base / 'T2'
        self.system, self.personal = self.root / 'system', self.root / 'personal'
        self.env = dict(os.environ, T2_INITIAL_CHIPS='10000', T2_TELEMETRY='0')
        self.env.pop('T2_DATA_DIR', None)
        self.env.pop('T2_UI_REF', None)
        with zipfile.ZipFile(self.install_zip) as archive:
            archive.extractall(self.base)
        self.command(self.root / 'install.py')
        self.update_source = self.base / 'update_package'
        with zipfile.ZipFile(self.update_zip) as archive:
            archive.extractall(self.update_source)
        self.updater = self.update_source / 'T2/update.py'

    def tearDown(self):
        self.tmp.cleanup()

    def command(self, script, *args, ok=True, env=None):
        out = subprocess.run([sys.executable, str(script), *map(str, args)],
                             capture_output=True, text=True, env=env or self.env)
        if ok:
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        else:
            self.assertNotEqual(out.returncode, 0, out.stdout + out.stderr)
        return out

    def reserve(self, data=None):
        store = TS.Store(str(data or self.personal), 10000, SPEC)
        store.ensure_schedule(35999)
        store.reserve('standard:36000', now=35999)
        store.set_active('standard:36000')
        return store

    def test_update_zip_contains_system_only(self):
        with zipfile.ZipFile(self.update_zip) as archive:
            names = archive.namelist()
        self.assertTrue(all(n.startswith('T2/system/') or n == 'T2/update.py' for n in names))
        self.assertFalse(any('/personal/' in n or '.sqlite3' in n or '/userdata/' in n for n in names))
        with zipfile.ZipFile(self.install_zip) as archive:
            names = archive.namelist()
        self.assertIn('T2/personal/README.txt', names)
        self.assertFalse(any('.sqlite3' in n for n in names))

    def test_first_install_creates_personal_wallet_outside_system(self):
        data = PD.resolve_data_dir(self.system, env={})
        self.assertEqual(data, self.personal)
        self.assertEqual(wallet_rows(data)['players'], [('hero', 10000)])
        self.assertEqual(len(wallet_rows(data)['ledger']), 1)
        self.assertFalse((self.system / PD.DATABASE).exists())

    def test_repeated_initial_install_never_resets_or_regrants(self):
        self.reserve()
        before = file_hashes(self.personal)
        self.env['T2_INITIAL_CHIPS'] = '777777'
        self.command(self.root / 'install.py')
        self.assertEqual(file_hashes(self.personal), before)
        self.assertEqual(wallet_rows(self.personal)['players'], [('hero', 9000)])

    def test_system_update_preserves_all_personal_file_bytes(self):
        self.reserve()
        (self.personal / 'notes.txt').write_text('개인 기록 유지', encoding='utf-8')
        (self.personal / 'schedule.json').write_text(json.dumps(SPEC), encoding='utf-8')
        before = file_hashes(self.personal)
        (self.system / 'UI_SOURCE').write_text('old code')
        self.env['T2_INITIAL_CHIPS'] = '777777'
        self.command(self.updater, self.root)
        self.assertEqual(file_hashes(self.personal), before)
        self.assertNotEqual((self.system / 'UI_SOURCE').read_text(), 'old code')

    def test_entire_system_folder_can_be_removed_and_rebuilt(self):
        self.reserve()
        before = file_hashes(self.personal)
        shutil.rmtree(self.system)
        self.command(self.updater, self.root)
        self.assertEqual(file_hashes(self.personal), before)
        self.assertEqual(PD.resolve_data_dir(self.system, env={}), self.personal)
        self.assertTrue((self.system / 'ui_server.py').is_file())

    def test_moving_system_and_personal_together_preserves_binding(self):
        self.reserve()
        moved = self.base / 'moved_T2'
        self.root.rename(moved)
        self.command(self.updater, moved)
        data = PD.resolve_data_dir(moved / 'system', env={})
        self.assertEqual(data, moved / 'personal')
        self.assertEqual(wallet_rows(data)['players'], [('hero', 9000)])

    def test_custom_personal_folder_is_kept_on_update(self):
        other, data = self.base / 'other_T2', self.base / 'my_wallet'
        self.command(self.root / 'install.py', other, '--personal-dir', data)
        self.reserve(data)
        before = file_hashes(data)
        self.command(self.updater, other)
        self.assertEqual(file_hashes(data), before)
        self.assertEqual(PD.resolve_data_dir(other / 'system', env={}), data)

    def test_install_and_update_support_spaces_in_folder_names(self):
        other, data = self.base / '게임 시스템 T2', self.base / '개인 지갑'
        self.command(self.root / 'install.py', other, '--personal-dir', data)
        self.reserve(data)
        before = file_hashes(data)
        self.command(self.updater, other)
        self.assertEqual(file_hashes(data), before)

    def test_missing_wallet_blocks_update_and_new_grant(self):
        (self.personal / PD.DATABASE).unlink()
        (self.system / 'UI_SOURCE').write_text('unchanged')
        self.command(self.updater, self.root, ok=False)
        self.assertFalse((self.personal / PD.DATABASE).exists())
        self.assertEqual((self.system / 'UI_SOURCE').read_text(), 'unchanged')
        with self.assertRaises(PD.PersonalDataError):
            PD.resolve_data_dir(self.system, env={})

    def test_missing_binding_blocks_update_and_startup(self):
        (self.personal / PD.MANIFEST).unlink()
        before = file_hashes(self.personal)
        self.command(self.updater, self.root, ok=False)
        with self.assertRaises(PD.PersonalDataError):
            PD.resolve_data_dir(self.system, env={})
        self.assertEqual(file_hashes(self.personal), before)

    def test_missing_binding_cannot_start_a_new_wallet_via_environment(self):
        (self.personal / PD.MANIFEST).unlink()
        wrong = self.base / 'wrong_wallet'
        with self.assertRaises(PD.PersonalDataError):
            PD.resolve_data_dir(self.system, env={'T2_DATA_DIR': str(wrong)})
        self.assertFalse(wrong.exists())

    def test_personal_metadata_cannot_be_linked_into_system(self):
        moved = self.system / 'misplaced_personal'
        self.personal.rename(moved)
        self.personal.symlink_to(moved, target_is_directory=True)
        before = file_hashes(moved)
        self.command(self.updater, self.root, ok=False)
        with self.assertRaises(PD.PersonalDataError):
            PD.resolve_data_dir(self.system, env={})
        self.assertEqual(file_hashes(moved), before)

    def test_corrupt_binding_is_preserved_and_refused(self):
        (self.personal / PD.MANIFEST).write_text('{broken')
        before = file_hashes(self.personal)
        self.command(self.updater, self.root, ok=False)
        self.assertEqual(file_hashes(self.personal), before)

    def test_inconsistent_ledger_is_preserved_and_refused(self):
        with sqlite3.connect(self.personal / PD.DATABASE) as db:
            db.execute('UPDATE players SET balance=12345')
        before = file_hashes(self.personal)
        self.command(self.updater, self.root, ok=False)
        self.assertEqual(file_hashes(self.personal), before)

    def test_existing_wallet_binding_cannot_be_switched_by_environment(self):
        env = dict(self.env, T2_DATA_DIR=str(self.base / 'wrong_wallet'))
        self.command(self.updater, self.root, ok=False, env=env)
        self.assertFalse((self.base / 'wrong_wallet').exists())
        with self.assertRaises(PD.PersonalDataError):
            PD.resolve_data_dir(self.system, env=env)

    def test_update_refuses_wallet_migration_options(self):
        self.command(self.updater, self.root, '--personal-dir', self.base / 'new', ok=False)
        self.command(self.updater, self.root, '--migrate-from', self.personal, ok=False)

    def test_runtime_code_and_personal_data_cannot_contain_each_other(self):
        for data in (self.system, self.system / 'userdata', self.root):
            with self.assertRaises(PD.PersonalDataError):
                PD.outside_system(data, self.system)

    def test_legacy_runtime_wallet_is_never_silently_replaced(self):
        legacy = self.base / 'legacy_run'
        self.reserve(legacy / 'userdata')
        with self.assertRaises(PD.PersonalDataError):
            PD.resolve_data_dir(legacy, env={'HOME': str(self.base / 'home')})
        self.assertEqual(wallet_rows(legacy / 'userdata')['players'], [('hero', 9000)])

    def test_installer_detects_legacy_wallet_before_creating_new_one(self):
        for nested in (False, True):
            legacy = self.base / ('legacy_system' if nested else 'legacy_target')
            old = legacy / 'system/userdata' if nested else legacy / 'userdata'
            self.reserve(old)
            before = file_hashes(old)
            self.command(self.root / 'install.py', legacy, ok=False)
            self.assertEqual(file_hashes(old), before)
            self.assertFalse((legacy / 'personal' / PD.DATABASE).exists())
            self.assertFalse((legacy / 'system/ui_server.py').exists())

    def test_legacy_migration_preserves_wal_receipts_and_leaves_source(self):
        legacy, target = self.base / 'legacy_run', self.base / 'migrated_T2'
        store = self.reserve(legacy / 'userdata')
        (legacy / 'userdata/schedule.json').write_text(json.dumps(SPEC))
        with contextlib.closing(sqlite3.connect(store.path)) as keeper:
            keeper.execute('PRAGMA journal_mode=WAL')
            # Holding a connection keeps the committed WAL available to backup.
            store.request_enter('standard:36000', now=35999)
            before = wallet_rows(legacy / 'userdata')
            self.command(self.root / 'install.py', target, '--migrate-from', legacy)
            self.assertEqual(wallet_rows(target / 'personal'), before)
            self.assertEqual(wallet_rows(legacy / 'userdata'), before)
        self.assertEqual((target / 'personal/schedule.json').read_text(), json.dumps(SPEC))

    def test_migration_never_overwrites_existing_personal_wallet(self):
        before = file_hashes(self.personal)
        self.command(self.root / 'install.py', self.root, '--migrate-from', self.personal, ok=False)
        self.assertEqual(file_hashes(self.personal), before)

    def test_manual_runtime_defaults_to_external_user_folder(self):
        runtime, home = self.base / 'manual_run', self.base / 'home'
        data = PD.resolve_data_dir(runtime, env={'HOME': str(home)})
        self.assertEqual(data, PD.default_data_dir({'HOME': str(home)}))
        self.assertNotIn(runtime, data.parents)
        for platform in ('linux', 'darwin', 'win32'):
            self.assertEqual(PD.default_data_dir({'HOME': str(home)}, platform).name, 'personal')

    def test_both_runtime_helpers_can_copy_a_legacy_ref_without_wallet_modules(self):
        # A hermetic legacy-ref fixture keeps the master copy workflow valid
        # without a network fetch or dependence on repository history depth.
        repo = self.base / 'legacy_source'
        repo.mkdir()
        shutil.copytree(self.system, repo, dirs_exist_ok=True)
        for name in ('personal_data.py', 'tournament_store.py', 'scheduled_runtime.py'):
            (repo / name).unlink()
        (repo / 'ui/server').mkdir(parents=True)
        shutil.copy2(repo / 'ui_server.py', repo / 'ui/server/ui_server.py')
        shutil.copy2(repo / 'ui_view.py', repo / 'ui/server/ui_view.py')
        shutil.copytree(repo / 'web', repo / 'ui/web')
        for args in (['init', '-q'], ['add', '.'],
                     ['-c', 'user.name=Verifier', '-c', 'user.email=verifier@example.invalid',
                      'commit', '-qm', 'legacy fixture']):
            subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
        (repo / 'ui/tools').mkdir()
        for name in ('setup_run_dir.py', 'setup_run_dir.sh'):
            shutil.copy2(ROOT / 'ui/tools' / name, repo / 'ui/tools' / name)
        env = dict(self.env, T2_UI_REF='HEAD')
        for name, executable in (('setup_run_dir.py', sys.executable), ('setup_run_dir.sh', 'sh')):
            target = self.base / ('legacy_' + name)
            out = subprocess.run([executable, str(repo / 'ui/tools' / name), str(target)],
                                 capture_output=True, text=True, env=env)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertTrue((target / 'ui_server.py').is_file())
            self.assertFalse((target / 'personal_data.py').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
