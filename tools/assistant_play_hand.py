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
NEXT_HAND=True

L.new_game(entries=9,start_stack=30000,seed=SEED,hands_per_level=12,fmt='standard')
r=L.step()
for a,amt in ACTIONS:
    r=L.step(a,amt)
hand1_result=r.get('view')
if NEXT_HAND and r.get('done'):
    r=L.step()

out={
    'actions_hand1':ACTIONS,
    'hand1_result':hand1_result,
    'done':r.get('done'),
    'raw':r.get('raw'),
    'view':r.get('view'),
}
print('ASSISTANT_PLAY_STATE')
print(json.dumps(out,ensure_ascii=False,default=str))
