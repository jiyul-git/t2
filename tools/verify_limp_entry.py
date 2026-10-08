"""Reproduce HAND 19 and guard first-in limp entry without changing RNG count."""
import copy
import json
import pathlib
import random
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import dynamics
import play
import preflop as PF
import reads
import session

rec = json.loads((pathlib.Path(__file__).parent / 'fixtures/hand19_limp.json').read_text())
book = reads.Book(); book.d = copy.deepcopy(rec['book_before'])
tilt = dynamics.Tilt(); tilt.state = copy.deepcopy(rec['tilt_before'])
pos = {int(k): v for k,v in rec['pos'].items()}
pre = [1,2,3,4,5,6,7,8,9]
post = [8,9,1,2,3,4,5,6,7]
h = play.Hand(sorted(pos),copy.deepcopy(rec['profiles']),
    {int(k):v for k,v in rec['stacks_before'].items()},rec['button'],*rec['blinds'],
    hero=rec['hero'],seed=rec['hand_seed'],book=book,dyn=tilt,
    position_map=pos,pre_seats=pre,post_seats=post,sb_seat=8,bb_seat=9)
assert h.hash == rec['hash']
h.seat_pid = {int(k):v for k,v in rec['seat_pid'].items()}
for k,v in rec['field_context'].items():
    setattr(h,{'remaining':'field_remaining','itm':'field_itm','avg_stack':'field_avg_stack'}.get(k,k),v)
run = session.HandRun(h); state = run.start()
while not state.get('done'):
    state = run.send('fold',0)
assert h.pf_seed[5]['pf_origin_act'] == 'fold', h.pf_seed[5]
timing = h.pf_seed[5]['pf_timing']
assert timing['limp_eligible'] is False and timing['limp_p'] == 0
assert not run.preflop_errors

# Forcing a limp draw cannot override entry eligibility. Eligible speculative
# hands can still limp: no personality labels and no extra RNG are introduced.
class LowRoll(random.Random):
    def random(self):
        return 0.0
p = rec['profiles']['5']
assert PF.open_decision(p,'HJ',65,['8c','3h'],LowRoll(1),seats=9)[0] == 'fold'
assert PF.open_decision(p,'HJ',65,['7c','6c'],LowRoll(1),seats=9)[0] == 'limp'
print(json.dumps({'pass':True,'hash':h.hash,'old_action':'limp/call',
                 'new_action':h.pf_seed[5]['pf_origin_act'],'timing':timing},ensure_ascii=False))
