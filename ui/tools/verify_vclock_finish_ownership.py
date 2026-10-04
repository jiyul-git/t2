"""A terminal HERO action must not run or settle legacy bot-table rounds."""
import pathlib, subprocess, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[2]
PROBE = r'''
import copy, sys, ui_view
sys.modules['view'] = ui_view
import live2 as L, fieldsim as FS
for entries, deferred in [(100, False), (100, True), (9, False), (9, True)]:
    L.new_game(entries=entries, seed=20261005, fmt='standard')
    r = L.step(vclock_others=True)
    before = L.load()['field']
    hero_tid, others, _ = L._round_owners(before)
    orig_step, orig_collect, orig_balance = FS.Field.step_others, FS.Field._collect_busts, FS.Field._balance
    def forbidden(*a, **kw):
        raise AssertionError('legacy bot round or premature bust/balance called')
    FS.Field.step_others = FS.Field._collect_busts = FS.Field._balance = forbidden
    try:
        for i in range(20):
            if r.get('done'): break
            legal = r['view'].get('legal') or {}
            action = 'check' if legal.get('check') else 'fold'
            r = L.step(action, defer_others=deferred, vclock_others=True)
        assert r.get('done'), r
    finally:
        FS.Field.step_others, FS.Field._collect_busts, FS.Field._balance = orig_step, orig_collect, orig_balance
    st = L.load()
    assert st.get('vclock_settle_pending') and not st.get('others_pending'), st.keys()
    for tid in others:
        key = str(tid)
        assert st['field']['tables'][key] == before['tables'][key]
        for pid in before['tables'][key]['pids']:
            assert st['field']['players'][str(pid)] == before['players'][str(pid)]
    # The clock owner still removes a HERO bust and finalizes rank/archive.
    hero = str(st['field']['hero_pid'])
    st['field']['players'][hero]['stack'] = 0
    L.apply_vclock_events(st, {}, {}, 0)
    fin = L.finalize_vclock_settle(st)
    assert fin['busted'] and fin['rank'] == entries
    assert not st.get('vclock_settle_pending') and not st.get('pending_archive')
    assert st['field']['players'][hero]['table'] is None
    print('PASS: entries=%d defer=%s; clock owns bot tables, bust/rank/archive' % (entries, deferred))
'''
with tempfile.TemporaryDirectory(prefix='t2_finish_owner_') as td:
    subprocess.run(['sh', str(ROOT/'ui/tools/setup_run_dir.sh'), td], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, '-c', PROBE], cwd=td, check=True)
