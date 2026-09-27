# CODE STRUCTURE MAP

## Core flow
runner.py
  Round.apply()
    -> rule truth: action_meta, contrib, stack, raise/all-in legality

action_events.py
  normalized_action()
  postflop_events()
  pending_response_context()
    -> canonical semantic events
    -> facing kind, raise depth, full/incomplete raise, all-in, price/context

session.py
  _acts_of()
  _postflop_response_context()
  _facing_wager_context()
  _run()
    -> rebuild each opponent perceived range from public history
    -> call ranges.perceived_range()
    -> build/update plan via plan.update_plan()
    -> execute action through runner.Round.apply()
    -> write reads / intents / telemetry

ranges.py
  preflop_range()
  perceived_range()
  narrow_by_actions()
  _bet_range()
  _raise_range()
  _call_range()
  _continue_range()
    -> range inference from preflop prior + canonical postflop events

plan.py
  relative_strength()
  joint_relative_strength()
  make_plan()
  refresh()
  river_fix()
  update_plan()
  attach_intent()
  act_with_plan()
  decide_response()
    -> decision layer using perceived ranges, equity, rel, board, plan, response context

reads.py
  Book / perceived_profile / range_profile
    -> observed opponent tendencies only
    -> feeds range inference and exploit adjustments

runner.py
  shape_size()
    -> execution-side human sizing noise
    -> disabled in pure-logic manual audit

## Important ownership rules
- Rule facts are owned by runner.Round.apply().
- Semantic postflop interpretation is owned by action_events.py.
- Opponent range reconstruction is owned by session.py + ranges.py.
- Strategic decision is owned by plan.py.
- Reads describe opponent tendencies; they must not replace public action history.
- Do not reconstruct raise depth / all-in semantics independently in multiple modules.
- rel is computed from the already-updated perceived opponent range; it is not the betting line itself.
- Same-street re-raises are not barrels. Barrel count = distinct aggressive streets.
