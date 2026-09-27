#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['T2_LIVE_STATE']=str(Path('/tmp/assistant_play_state.json'))

import live2 as L

# Interactive assistant-play fixture: decisions are chosen from printed state.
SEED=202609271937
HANDS=[
    [('fold',0)],
    [('fold',0)],
    [('fold',0)],
    [('fold',0)],
    [('fold',0)],
    [('fold',0)],
    [('raise',500),('check',0),('check',0),('check',0)],
    [('call',0),('bet',300),('bet',700),('check',0)],
    [],
]

L.new_game(entries=9,start_stack=30000,seed=SEED,hands_per_level=12,fmt='standard')
r=L.step()
history=[]

for idx, actions in enumerate(HANDS, start=1):
    before={'hand':idx,'raw':r.get('raw'),'view':r.get('view'),'done':r.get('done')}
    if r.get('done'):
        raise RuntimeError('hand %d started from done state' % idx)
    for a,amt in actions:
        r=L.step(a,amt)
    history.append({
        'hand':idx,
        'actions':actions,
        'before':before,
        'after':{'raw':r.get('raw'),'view':r.get('view'),'done':r.get('done')},
    })
    if idx < len(HANDS):
        if not r.get('done'):
            raise RuntimeError('hand %d did not finish after scripted actions' % idx)
        r=L.step()

print('ASSISTANT_PLAY_STATE')
print(json.dumps({'history':history,'current':history[-1]['after']},
                 ensure_ascii=False,default=str))
