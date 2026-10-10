#!/usr/bin/env python3
"""HAND130 B37 deterministic decision-layer replay from the archived original.

This is a read-only baseline: exact original actor profile, preflop plan seed,
pot sizes, and stored 800-request equity results. The archive excerpt does NOT
contain the 288 weighted opponent combos or the original MC trace; therefore
this verifies decision and gate replay, not a full equity Monte Carlo rerun.

Source: docs/handoff/T2_T3_HANDOFF_20261010.md appendix F.
"""
import json
import os
import random
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import preflop as PF
import plan as PL


def original():
    p = os.path.join(ROOT, "docs", "handoff", "T2_T3_HANDOFF_20261010.md")
    with open(p, encoding="utf-8") as f:
        text = f.read()
    appendix = text.split("# 부록 F. 직접 확인한 HAND130 원자료 발췌", 1)[1]
    block = appendix.split("```json", 1)[1].split("```", 1)[0]
    return json.loads(block)


def eq(actual, expected, key, tol=0.00000051):
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        assert abs(float(actual) - float(expected)) <= tol, (key, actual, expected)
    else:
        assert actual == expected, (key, actual, expected)


def main():
    hand = original()
    assert hand["hand_no"] == 130 and hand["hash"] == "6e1ba98ab1a0"
    assert hand["seat_pid"]["3"] == 37
    assert set(hand["hole"]["3"]) == {"Ac", "Kh"}
    pf = hand["actor_pf_seed"]
    profile = hand["actor_profile"]
    shadow = pf["pf_call_ev_shadow"]
    saved = pf["pf_calloff_consumer"]
    assert shadow["pure_calloff"] and shadow["complete"]
    assert pf["pf_level"] == 2 and not pf["pf_can_raise"]
    assert pf["pf_facing_allin"] and pf["pf_to_call_bb"] == 5.3442

    # _dseed in session.py uses the hand hash, seat, street, label, and log length.
    assert len(hand["full_log"]) == 9
    decision_seed = zlib.crc32(
        ("%s|%s|preflop|f8_d6d2|8" % (hand["hash"], 3)).encode())
    assert decision_seed == 3365551903
    assert zlib.crc32(("%s|potodds" % decision_seed).encode()) == saved["noise_seed"]
    assert zlib.crc32(("%s|pf_defend_gate" % decision_seed).encode()) == saved["gate_seed"]

    bf = saved["objective_bubble_factor"]
    price = shadow["call_cost"]
    contestable = shadow["contestable_after_call"]
    assert price == 53442 and contestable == 161884
    assert round(price / contestable, 6) == shadow["breakeven_equity"]

    legacy, cap = PF.calloff_decision(
        profile, "LJ", ["Kh", "Ac"], pf["pf_stack_bb"],
        pf["pf_level"], pf["pf_pot_bb"], pf["pf_to_call_bb"], bf,
        "BB", pf["pf_open_bb"], None, pf["pf_n_callers"], 8, True)
    eq(cap, pf["pf_calloff_compare"]["legacy_cap"], "legacy_cap")
    assert legacy[0] == "fold"
    layer = PF.calloff_layer_judgment(
        profile, shadow, bubble_factor=bf, seed=decision_seed)
    for key in ("layer_effective_equity", "objective_bubble_factor",
                "perceived_bubble_factor", "icm_required_equity_before_calc_error",
                "potodds_noise", "perceived_required_equity", "layer_action",
                "pf_defend_gate_p", "pf_defend_gate_roll", "gate_pass",
                "noise_seed", "gate_seed"):
        eq(layer[key], saved[key], key)

    rng = random.Random(919)
    state = rng.getstate()
    action, size, info = PL.preflop_plan(
        profile, "LJ", ["Kh", "Ac"], pf["pf_stack_bb"], rng,
        aggressor_pos="BB", open_bb=pf["pf_open_bb"],
        n_callers=0, n_limpers=0, raise_level=2,
        bf=bf, seats=8, ante=True, bb_chips=10000,
        opener_allin=True, can_raise=False,
        pot_bb=pf["pf_pot_bb"], to_call_bb=pf["pf_to_call_bb"],
        prior_pf={"pf_act": "raise", "pf_role": "open"},
        call_ev_shadow=shadow, calloff_decision_seed=decision_seed,
        cold_context=pf["pf_cold_context"])
    assert rng.getstate() == state, "Pure calloff consumed shared decision RNG"
    assert pf["pf_act"] == "fold"  # archived original is not rewritten
    assert action == "call" and size == pf["pf_to_call_bb"]
    consumer = info["pf_calloff_consumer"]
    assert consumer
    for key in ("layer_action", "legacy_action", "gate_pass"):
        eq(consumer[key], saved[key], key)
    assert consumer["selected_action"] == "call"
    assert consumer["strategy_consumer"] is True
    assert consumer["gate_role"] == "diagnostic_only"
    assert consumer["changed"] is True

    print(json.dumps({
        "fixture": "HAND130/B37",
        "hash": hand["hash"], "decision_seed": decision_seed,
        "gate_seed": saved["gate_seed"], "noise_seed": saved["noise_seed"],
        "legacy_cap": cap, "hand_pct": PF.pct(["Kh", "Ac"]),
        "layer_equity": layer["layer_effective_equity"],
        "objective_required": pf["pf_calloff_compare"]["icm_required_equity"],
        "perceived_required": layer["perceived_required_equity"],
        "gate_roll": layer["pf_defend_gate_roll"],
        "gate_pass": layer["gate_pass"], "selected_action": action,
        "mc_recomputed": False,
        "rng_preserved": True,
        "legacy_action": pf["pf_act"],
        "decision_quantity": consumer["decision_quantity"],
    }, sort_keys=True))
    print("PASS HAND130 B37 full-price decision routing on archived inputs")


if __name__ == "__main__":
    main()
