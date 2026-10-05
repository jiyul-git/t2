#!/usr/bin/env python3
"""Decision trace for the bot-timing design, with tournament stage per hand.

Same per-decision provenance as tools/beta_trace.py (preflop_plan inputs and
act_with_plan response equity), plus a stage map hash -> {remaining, itm, bb}
so late-stage (20-30bb, bubble / ITM) decisions can be measured directly.

  python tools/timing_trace.py SEED FIELD OUT.json [CAP]
    FIELD = uniform  r2 baseline field (max skill, neutral, frozen reads)
            real     generated population (persona.make_player), emotion and
                     read book restored
    CAP   = round cap (default: play to the end)

Design tool only.  No production behaviour changes.
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import persona as PS
import play as PLY
import reads as RD
_ORIG = (PS.make_player, PLY.Hand.emotion_level, RD.Book.rec)

import beta_trace as BT          # noqa: E402  (applies r2 baseline patches)
import fieldsim as FS            # noqa: E402

STAGE = {}
_grab = FS.Field._log_bot_hand


def grab(self, tb, h, run):
    STAGE[h.hash] = {'remaining': self.remaining(), 'itm': self.itm, 'bb': h.bb,
                     'entries': self.entries}
    _grab(self, tb, h, run)


FS.Field._log_bot_hand = grab


def main():
    seed, field, out = sys.argv[1], sys.argv[2], sys.argv[3]
    cap = sys.argv[4] if len(sys.argv) > 4 else '100000'
    if field == 'real':
        PS.make_player, PLY.Hand.emotion_level, RD.Book.rec = _ORIG
    elif field != 'uniform':
        raise SystemExit('FIELD must be uniform or real')
    sys.argv = ['x', seed, cap]
    BT.SIM.main()
    json.dump({'seed': int(seed), 'field': field, 'cap': int(cap), 'pf': BT.SIM.PF,
               'hands': BT.HANDS, 'stage': STAGE}, open(out, 'w'), default=str)


if __name__ == '__main__':
    main()
