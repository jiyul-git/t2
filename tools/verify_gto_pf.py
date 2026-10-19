"""GTO 프리플랍 기준(10~40bb) 연결 검사.

  python3 tools/verify_gto_pf.py

1) 데이터 조회: 버킷 값 그대로, 버킷 사이 보간, 범위 밖 None.
2) 좌석 변환: 8/6맥스 → 뒤 인원이 같은 9맥스 자리.
3) 첫 진입: 범위 안이면 GTO 행동, ICM 압력·노안테·범위 밖이면 None(RNG 미사용).
4) 올인 콜: 단독 올인/오픈 후 3벳 올인만, 콜러가 낀 팟과 행동 여부 불명은 None.
"""
import os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import gto_pf as G
import preflop as P

ok = 0
def check(name, cond):
    global ok
    assert cond, name
    ok += 1
    print('PASS', name)

d = G._load()
check('buckets 10..40', d['buckets'] == [10, 15, 20, 25, 30, 40])
i = d['classes'].index('A2o')
check('SB 10bb A2o jam = record', abs(G.first_in('SB', 9, 10, ['Ah', '2c'])['jam']
                                       - d['first_in']['10']['SB']['jam'][i]) < 1e-9)
a = G.first_in('UTG', 9, 15, ['Kd', 'Qs'])['jam']
b = G.first_in('UTG', 9, 20, ['Kd', 'Qs'])['jam']
m = G.first_in('UTG', 9, 17.5, ['Kd', 'Qs'])['jam']
check('interpolation midpoint', abs(m - (a + b) / 2) < 1e-9)
check('out of range low/high', G.first_in('UTG', 9, 9.0, ['Ah', 'Ah'.replace('h', 'd')]) is None
      and G.first_in('UTG', 9, 41.0, ['Ah', 'Ad']) is None)
check('30bb SB first-in left to existing path (limp is flop-model dependent)',
      G.first_in('SB', 9, 30, ['Kh', '7c']) is None and G.first_in('SB', 9, 25, ['Kh', '7c']) is not None)
check('30bb BTN first-in has no jam', G.first_in('BTN', 9, 30, ['Kh', '7c'])['jam'] == 0.0)
v = G.aggr_vs_open('BTN', 'BB', 9, 30, ['Ah', 'Kc'])
check('BB vs BTN open 30bb: AKo aggression from record',
      abs(v['jam'] - d['vs_open']['30']['BTN>BB']['jam'][d['classes'].index('AKo')]) < 1e-9)
check('vs_open below 15bb not covered', G.aggr_vs_open('BTN', 'BB', 9, 12, ['Ah', 'Kc']) is None)
check('no ante -> None', G.first_in('UTG', 9, 15, ['Ah', 'Ad'], ante=False) is None)
check('8-max UTG = 9-max UTG+1', G.pos9('UTG', 8) == 'UTG+1')
check('6-max UTG = 9-max LJ', G.pos9('UTG', 6) == 'LJ')
check('5-handed not covered', G.pos9('UTG', 5) is None)

prof = {}
class Spy(random.Random):
    n = 0
    def random(self):
        Spy.n += 1
        return super().random()
r = Spy(1)
check('first-in SB 10bb A2o jams', P.gto_pf_first_in_choice(prof, 'SB', 9.39, ['Ah', '2c'], r,
                                                             [8.89], 1.0, 9, True) == 'jam')
Spy.n = 0
check('ICM pressure -> None, no RNG',
      P.gto_pf_first_in_choice(prof, 'SB', 9.39, ['Ah', '2c'], r, [8.89], 1.3, 9, True) is None
      and Spy.n == 0)
check('money pressure -> None',
      P.gto_pf_first_in_choice(prof, 'SB', 9.39, ['Ah', '2c'], r, [8.89], 1.0, 9, True,
                               {'pressure': 0.2, 'range_factor': 0.9}) is None)
check('money drive only -> covered',
      P.gto_pf_first_in_choice(prof, 'SB', 9.39, ['Ah', '2c'], r, [8.89], 1.0, 9, True,
                               {'pressure': 0.0, 'range_factor': 1.29}) == 'jam')
check('deep stack -> None', P.gto_pf_first_in_choice(prof, 'SB', 60, ['Ah', '2c'], r,
                                                      [60], 1.0, 9, True) is None)
# BB vs SB jam 10bb: K5o always calls in the record
check('BB calls SB jam K5o 10bb',
      P.gto_pf_call_choice(prof, 'SB', 'BB', ['Kh', '5c'], r, 8.89, 9.89, 8.89, 1,
                           other_live_actors=0, actor_acted=False) == 'call')
check('caller in pot -> None',
      P.gto_pf_call_choice(prof, 'SB', 'BB', ['Kh', '5c'], r, 8.89, 9.89, 8.89, 1,
                           other_live_actors=1, actor_acted=False) is None)
check('unknown context -> None',
      P.gto_pf_call_choice(prof, 'SB', 'BB', ['Kh', '5c'], r, 8.89, 9.89, 8.89, 1) is None)
# UTG opened, BB 3-bet jams 25bb: KJo folds in the record (opener facing 3-bet jam)
check('UTG folds KJo vs BB 3-bet jam 25bb',
      P.gto_pf_call_choice(prof, 'BB', 'UTG', ['Kh', 'Jc'], r, 22.9, 24.9, 22.9, 2,
                           other_live_actors=0, actor_acted=True) == 'fold')
check('raise level 2 without own action -> None',
      P.gto_pf_call_choice(prof, 'BB', 'UTG', ['Kh', 'Jc'], r, 22.9, 24.9, 22.9, 2,
                           other_live_actors=0, actor_acted=False) is None)
check('aggr: caller in pot -> None',
      P.gto_pf_aggr_choice(prof, 'BTN', 'BB', ['Ah', 'Kc'], r, 29.0, 2.0, 1.0, 1,
                           other_live_actors=1, actor_acted=False) is None)
check('aggr: unknown own action -> None',
      P.gto_pf_aggr_choice(prof, 'BTN', 'BB', ['Ah', 'Kc'], r, 29.0, 2.0, 1.0, 1,
                           other_live_actors=0) is None)
check('aggr: 72o vs BTN open passes',
      P.gto_pf_aggr_choice(prof, 'BTN', 'BB', ['7h', '2c'], r, 29.0, 2.0, 1.0, 1,
                           other_live_actors=0, actor_acted=False,
                           aggressor_total_bb=30.0) == 'pass')
# --- packaging: the run folder (gateway / installer) must carry the module and its data ---
import subprocess, tempfile
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
for kind, exe in (('sh', 'sh'), ('py', sys.executable)):
    with tempfile.TemporaryDirectory(prefix='t2_gtopf_') as td:
        subprocess.run([exe, os.path.join(ROOT, 'ui/tools/setup_run_dir.' + kind), td], check=True,
                       stdout=subprocess.DEVNULL, env=dict(os.environ, T2_TELEMETRY='0'))
        check('run dir (%s) has gto_pf.py + data' % kind,
              os.path.isfile(os.path.join(td, 'gto_pf.py')) and os.path.isfile(os.path.join(td, 'gto_pf_data.json')))
        probe = ("import preflop as P, gto_pf as G; m = P._gto_pf_mod(); "
                 "assert m is not None and G.first_in('UTG', 9, 15, ['Ah','Ad']) is not None; print('ok')")
        r = subprocess.run([sys.executable, '-c', probe], cwd=td, capture_output=True, text=True)
        check('run dir (%s) loads the reference' % kind, r.returncode == 0 and 'ok' in r.stdout)
# --- a missing module / data must never break a hand ---
with tempfile.TemporaryDirectory(prefix='t2_gtopf_missing_') as td:
    subprocess.run(['sh', os.path.join(ROOT, 'ui/tools/setup_run_dir.sh'), td], check=True,
                   stdout=subprocess.DEVNULL, env=dict(os.environ, T2_TELEMETRY='0'))
    os.remove(os.path.join(td, 'gto_pf.py'))
    probe = ("import random, preflop as P; r = random.Random(1); "
             "assert P.gto_pf_first_in_choice({}, 'SB', 9.39, ['Ah','2c'], r, [8.89], 1.0, 9, True) is None; "
             "assert P.gto_pf_call_choice({}, 'SB', 'BB', ['Kh','5c'], r, 8.89, 9.89, 8.89, 1, other_live_actors=0, actor_acted=False) is None; "
             "assert P.gto_pf_aggr_choice({}, 'BTN', 'BB', ['Ah','Kc'], r, 29.0, 2.0, 1.0, 1, other_live_actors=0, actor_acted=False) is None; print('ok')")
    r = subprocess.run([sys.executable, '-c', probe], cwd=td, capture_output=True, text=True)
    check('missing gto_pf.py -> existing path, no exception', r.returncode == 0 and 'ok' in r.stdout)
print('%d gto_pf checks passed' % ok)
