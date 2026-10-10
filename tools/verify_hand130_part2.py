#!/usr/bin/env python3
"""HAND130 part-2 read-only equation audit.

Replays code formulas from the archived *base* profile, with experimental GTO
flags OFF. This is not a replay of the live process (whose tilted profile and
environment variables were not archived). Changes no strategies or RNG.
"""
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.pop("T2_GTO_MEMORY_V2", None)
os.environ.pop("T2_PREFLOP_REASONING_V3", None)

import depth as DP
import gto as G
import icm as ICM
import persona as PS
import preflop as PF

SOURCE = ROOT / "docs/handoff/T2_T3_HANDOFF_20261010.md"


def close(actual, expected, tol=1e-10):
    if not math.isclose(actual, expected, abs_tol=tol, rel_tol=tol):
        raise AssertionError(f"{actual:.15f} != {expected:.15f}")


def archived_hand():
    text = SOURCE.read_text(encoding="utf-8")
    section = text.split("부록 F. 직접 확인한 HAND130 원자료 발췌", 1)[1]
    return json.loads(section.split("```json", 1)[1].split("```", 1)[0])


def audit():
    case = archived_hand()
    prof = case["actor_profile"]
    pf = case["actor_pf_seed"]
    context = case["field_context"]
    pos, vs = pf["pf_pos"], pf["pf_vs"]
    n_seats = len(case["pos"])
    bb = float(pf["pf_stack_bb"])
    facing_bb = float(pf["pf_open_bb"])
    level = int(pf["pf_level"])
    n_callers = int(pf["pf_n_callers"])
    ante = context["ante"] > 0
    objective_bf = float(pf["pf_calloff_compare"]["bubble_factor"])

    assert (case["hand_no"], prof["id"], pos, vs, level) == (130, 37, "LJ", "BB", 2)
    assert pf["pf_can_raise"] is False
    assert pf["pf_facing_allin"] is True
    assert n_seats == 8 and n_callers == 0

    # Exact current-source baseline: BB cannot open RFI.
    base_tot = G.defend_pct(pos, vs, n_seats, bb, ante, facing_bb)
    base_tp = G.threebet_pct(pos, vs, n_seats, bb, ante, facing_bb)
    assert G.rfi(vs, n_seats, bb, ante) == 0.0
    close(base_tot, 0.03135)
    close(base_tp, 0.005643)

    loose = PS.temper(prof, "looseness", 5.0)
    aggr = PS.temper(prof, "aggression", 5.0)
    d_call = PS.preflop_temper_direction(loose)
    d_threebet = PS.preflop_temper_direction(0.45 * loose + 0.55 * aggr)
    confidence = PS.gto_memory_confidence(
        prof, "defend", pos, n_seats, bb, ante,
        opener_pos=vs, open_bb=facing_bb,
    )
    room = PS.chart_deviation_room(confidence)
    raw_tot = base_tot * (1.0 + room * d_call * 0.95)
    raw_tp = base_tp * (1.0 + room * d_threebet * 1.10)
    norm_tp, norm_tot = PF.normalize_defend_prior_widths(
        raw_tp, raw_tot, G._use_mtt8_ante_defense(pos, n_seats, ante))
    caller_tp, caller_tot = PF.adjust_defend_widths_for_callers(
        prof, norm_tp, norm_tot, n_callers)
    short_tp, short_tot = PF.adjust_defend_widths_for_short_stack(
        caller_tp, caller_tot, bb)
    final_tp, final_tot = PF.tighten_defend_widths_for_raise_level(
        short_tp, short_tot, level)
    direct_tp, direct_tot = PF.defend_thresholds(
        prof, pos, vs, bb, facing_bb, n_callers, level, n_seats, ante)
    close(final_tp, direct_tp)
    close(final_tot, direct_tot)

    # Source-recorded depth curve, unvalidated legacy percentile policy.
    depth = DP.base_feel(bb)
    close(depth, 0.1318368)
    multiplier = PF.CALLOFF_TIGHTEN.get(level + 1, 0.07)
    raw_cap = final_tot * multiplier * 2.6 * (1.0 - 0.18 * depth) / max(1.0, objective_bf)
    final_cap = PF.calloff_cap(
        prof, pos, vs, bb, facing_bb, level, bf=objective_bf,
        exploit=None, n_callers=n_callers, seats=n_seats, ante=ante)
    close(final_cap, max(0.005, min(0.85, raw_cap)))
    hand_pct = PF.legacy_preflop_order_percentile(case["hole"]["3"])
    legacy_act, _ = PF.calloff_decision(
        prof, pos, case["hole"]["3"], bb, level, pf["pf_pot_bb"],
        pf["pf_to_call_bb"], objective_bf, vs, facing_bb,
        exploit=None, n_callers=n_callers, seats=n_seats, ante=ante)
    assert legacy_act[0] == "fold"
    close(final_cap, pf["pf_calloff_compare"]["legacy_cap"])

    # Call price is a different, directly derivable quantity.
    cost = float(pf["pf_call_ev_shadow"]["call_cost"])
    after = float(pf["pf_call_ev_shadow"]["contestable_after_call"])
    before = after - cost
    need_chip = cost / after
    need_icm = ICM.required_equity(before, cost, objective_bf)
    close(need_chip, pf["pf_call_ev_shadow"]["breakeven_equity"], 1e-6)
    close(need_icm, pf["pf_calloff_compare"]["icm_required_equity"], 1e-6)
    eq = float(pf["pf_call_ev_shadow"]["effective_equity"])
    gate = float(pf["pf_calloff_consumer"]["pf_defend_gate_p"])
    close(gate, PF.pf_defend_exact_calc_gate(prof), 1e-6)
    assert pf["pf_calloff_consumer"]["gate_pass"] is False
    assert pf["pf_calloff_consumer"]["selected_action"] == "fold"
    assert eq >= need_icm  # Point estimate, NOT confidence-guaranteed.
    assert hand_pct > final_cap

    archived_claimed_w5 = 0.0166578  # A preceding analysis, not raw engine telemetry.
    report = {
        "status": "STATIC_REPLAY_PASS__NO_STRATEGY_CHANGE",
        "code_context": "test3/945758acc, GTO flags OFF, base profile, no tilt",
        "first_rfi_is_BB": G.rfi(vs, n_seats, bb, ante),
        "stages": {
            "baseline_attack": base_tp, "baseline_continue": base_tot,
            "personality_raw_attack": raw_tp, "personality_raw_continue": raw_tot,
            "normalized_attack": norm_tp, "normalized_continue": norm_tot,
            "after_callers_attack": caller_tp, "after_callers_continue": caller_tot,
            "after_short_attack": short_tp, "after_short_continue": short_tot,
            "after_level_attack": final_tp, "after_level_continue": final_tot,
            "raw_calloff_cap": raw_cap, "clamped_calloff_cap": final_cap,
        },
        "archived_reported_w5": archived_claimed_w5,
        "w5_discrepancy": final_tot - archived_claimed_w5,
        "price": {
            "call_cost_chips": cost, "pot_before_chips": before,
            "chip_required_equity": need_chip,
            "objective_icm_required_equity": need_icm,
            "archived_800_sim_equity": eq,
            "icm_margin_point_estimate": eq - need_icm,
        },
        "selection": {
            "rank_percentile": hand_pct, "legacy": legacy_act[0],
            "layer_if_gate_passed": pf["pf_calloff_consumer"]["layer_action"],
            "gate_probability": gate,
            "gate_draw": pf["pf_calloff_consumer"]["pf_defend_gate_roll"],
            "actually_selected": pf["pf_calloff_consumer"]["selected_action"],
        },
        "warning": ("Archived W5 and static source+base-profile W5 differ; "
                    "live tilted view/env unknown; ICM equity 800-sim margin "
                    "must not be called statistically decisive."),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    audit()
