#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

# Isolate this probe from any normal live state.
os.environ['T2_LIVE_STATE']=str(Path('/tmp/assistant_play_state.json'))

import live2 as L

SEED=202609271937
ACTIONS=[('fold', 0)]  # hand 1
HAND2=[('fold', 0)]
HAND3=[('fold', 0)]
HAND4=[('fold', 0)]
HAND5=[('fold', 0)]
HAND6=[('fold', 0)]

L.new_game(entries=9,start_stack=30000,seed=SEED,hands_per_level=12,fmt='standard')
r=L.step()
for a,amt in ACTIONS:
    r=L.step(a,amt)
hand1_result=r.get('view')
hand2_result=None
if r.get('done'):
    r=L.step()
    for a,amt in HAND2:
        r=L.step(a,amt)
    hand2_result=r.get('view')
hand3_result=None
if r.get('done'):
    r=L.step()
    for a,amt in HAND3:
        r=L.step(a,amt)
    hand3_result=r.get('view')
hand4_result=None
if r.get('done'):
    r=L.step()
    for a,amt in HAND4:
        r=L.step(a,amt)
    hand4_result=r.get('view')
hand5_result=None
if r.get('done'):
    r=L.step()
    for a,amt in HAND5:
        r=L.step(a,amt)
    hand5_result=r.get('view')
hand6_result=None
if r.get('done'):
    r=L.step()
    for a,amt in HAND6:
        r=L.step(a,amt)
    hand6_result=r.get('view')
if r.get('done'):
    r=L.step()

out={
    'actions_hand1':ACTIONS,
    'actions_hand2':HAND2,
    'actions_hand3':HAND3,
    'actions_hand4':HAND4,
    'actions_hand5':HAND5,
    'actions_hand6':HAND6,
    'hand1_result':hand1_result,
    'hand2_result':hand2_result,
    'hand3_result':hand3_result,
    'hand4_result':hand4_result,
    'hand5_result':hand5_result,
    'hand6_result':hand6_result,
    'done':r.get('done'),
    'raw':r.get('raw'),
    'view':r.get('view'),
}
print('ASSISTANT_PLAY_STATE')
print(json.dumps(out,ensure_ascii=False,default=str))
