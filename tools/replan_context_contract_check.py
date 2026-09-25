#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fast post-fix contract check for revise_plan position context.

This does not run tournament simulation. It verifies the two production wiring
links introduced after A5 4-B:

  plan.update_plan -> runner.revise_plan
  runner.revise_plan -> plan.make_plan

Fields:
  oop_vs_aggr
  oop_legacy_abs
  initiative
"""
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import plan as PL
import runner as RU

FIELDS = ('oop_vs_aggr', 'oop_legacy_abs', 'initiative')


def require(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    sig = inspect.signature(RU.revise_plan)
    src_update = inspect.getsource(PL.update_plan)
    src_revise = inspect.getsource(RU.revise_plan)

    for field in FIELDS:
        require(field in sig.parameters,
                'runner.revise_plan signature missing %s' % field)
        require(('%s=%s' % (field, field)) in src_update,
                'plan.update_plan does not forward %s to revise_plan' % field)
        require(('%s=%s' % (field, field)) in src_revise,
                'runner.revise_plan does not forward %s to make_plan' % field)

    require(sig.parameters['oop_vs_aggr'].default is None,
            'oop_vs_aggr default changed')
    require(sig.parameters['oop_legacy_abs'].default is None,
            'oop_legacy_abs default changed')
    require(sig.parameters['initiative'].default is True,
            'initiative default changed')

    print('PASS revise_plan position-context contract')
    print('  plan.update_plan -> runner.revise_plan: '
          'oop_vs_aggr, oop_legacy_abs, initiative')
    print('  runner.revise_plan -> plan.make_plan: '
          'oop_vs_aggr, oop_legacy_abs, initiative')
    print('  defaults preserved: None / None / True')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
