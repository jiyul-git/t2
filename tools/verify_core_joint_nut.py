#!/usr/bin/env python3
"""Verify seat-keyed multiway nut-advantage semantics."""
import json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import ranges as R

BOARD=['2c','7d','Jh']
HERO_RANGE=[
 ('Jc','Js'),('7c','7s'),('2d','2s'),('Jc','7c'),('Jd','7h'),
 ('As','Ah'),('Ks','Kh'),('Qs','Qh'),('Ad','Kd'),('Ac','Qc')]
OPP=[
 ('Jd','Js'),('7c','7s'),('2d','2s'),('Jc','7c'),('Js','7h'),
 ('As','Ks'),('Qd','Td'),('9c','8c'),('Ac','5c'),('Kd','Qd'),
 ('Ts','9s'),('8h','6h'),('Ad','4d'),('Kc','Tc')]
def main():
    hu=R.nut_advantage(HERO_RANGE,OPP,BOARD)
    j1=R.joint_nut_advantage(
        HERO_RANGE,{'v1':OPP},BOARD,n_opp=1,sims=3000,seed=41)
    j2a=R.joint_nut_advantage(
        HERO_RANGE,{'v1':OPP,'v2':OPP},BOARD,n_opp=2,sims=6000,seed=42)
    j2b=R.joint_nut_advantage(
        HERO_RANGE,{'v1':OPP,'v2':OPP},BOARD,n_opp=2,sims=6000,seed=42)
    missing=R.joint_nut_advantage(
        HERO_RANGE,{'v1':OPP},BOARD,n_opp=2,sims=100,seed=1)
    checks={
      'heads_up_exact_legacy': j1==hu,
      'multiway_deterministic': j2a==j2b,
      'second_opponent_does_not_create_fake_hero_nut_edge': j2a <= hu + 1e-12,
      'incomplete_seat_map_is_unknown': missing is None,
      'bounded': -1.0 <= j2a <= 1.0,
    }
    out={'pass':all(checks.values()),'checks':checks,
         'hu':hu,'joint2':j2a,'missing':missing}
    print(json.dumps(out,indent=2,sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)
if __name__=='__main__': main()
