#!/usr/bin/env python3
"""Behavior-neutral F7-C pre-logic profile boundary gate."""

import random
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

import persona as PS
import play


class FakeDyn:
    def __init__(self, level):
        self._level=float(level)
    def level(self, _pid):
        return self._level


def need(cond,msg):
    if not cond:
        raise AssertionError(msg)


rng=random.Random(20260927)
p1=PS.make_player(rng,1.2,101)
p2=PS.make_player(rng,1.2,102)
profiles={'1':p1,'2':p2}
h=play.Hand(
    [1,2],profiles,{1:30000,2:30000},
    button=1,sb=100,bb=200,hero=1,seed=20260927,
    dyn=FakeDyn(0.65))
h.seat_pid={1:101,2:102}

base=dict(p1)
base.setdefault('tilt',3)
base.setdefault('goal','accum')
old_planning=PS.tilted_view(base,0.65)

axes,tilt=h.axes(1)
views=h.profile_views(1)

need(tilt==0.65,'axes tilt changed')
need(axes==old_planning,'axes no longer matches historical tilted-view entry')
need(views['planning']==old_planning,'planning view mismatch')
need(views['base']==base,'base view changed persona')
need(views['execution']==base,'execution scaffold is not emotion-free base')
need(views['tilt']==0.65,'profile_views tilt mismatch')
need(h.execution_profile(1)==base,'execution_profile mismatch')
need(h.planning_profile(1)[0]==axes,'planning_profile mismatch')
need(views['planning'] is not views['execution'],
     'planning/execution boundary aliases same mutable object')

src=(ROOT/'play.py').read_text(encoding='utf-8')
need('return self.planning_profile(s)' in src,
     'axes is not explicitly pinned to planning_profile')
need('def execution_profile(self, s):' in src,
     'execution profile scaffold missing')

print({
    'tilt':tilt,
    'type':p1.get('type'),
    'concepts':len(p1.get('concepts') or {}),
    'planning_differs_from_execution':views['planning'] != views['execution'],
})
print('PASS F7-C behavior-neutral profile boundary scaffold')
