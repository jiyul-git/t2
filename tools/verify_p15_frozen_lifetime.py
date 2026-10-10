#!/usr/bin/env python3
"""Independent P15 gate: released or clock-expired reference must not be attested.

This intentionally fails PR24 75c6ee2d. Rerun unchanged on P13's lifetime fix.
"""
import json, pathlib, random, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from tools.verify_p13_field_epoch_freshness import field,stamped

def main():
    rows=[]
    for change in ('release','hand_no','level'):
        f=field();f._frozen_field=f.field_snapshot();h=stamped(f)
        a=h.bf_details(3)
        if change=='release':f._frozen_field=None
        else:setattr(f,change,getattr(f,change)+1)
        before=(random.getstate(),f.rng.getstate())
        b=h.bf_details(3)
        assert before==(random.getstate(),f.rng.getstate())
        # It is legitimate to keep a historical batch numerically stable.
        # After release/clock transition it must cease claiming a live
        # current-batch attestation. This gate accepts an explicitly expired
        # status with historical BF preserved; it does not mandate BF=1.
        ok=b.get('field_epoch_status')!='frozen_epoch_reference'
        rows.append({'change':change,'pass':ok,'before':a,'after':b})
    print(json.dumps({'pass':all(r['pass'] for r in rows),'checks':rows},indent=2))
    raise SystemExit(0 if all(r['pass'] for r in rows) else 1)

if __name__=='__main__':main()
