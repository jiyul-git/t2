# Limp entry and admission follow-up, 2026-10-09 KST

## HAND 19: B16 HJ 83o

Replayed archive 7595ca32f61c with its exact cards, profiles, stacks, reads,
tilt and hand seed 633046030. The old first-in habit-limp branch accepted any
hand: 83o's limp probability was 0.0457765 and its draw was 0.03301285.
This was an entry-range bypass, not evidence to impose an aggression floor.

First-in limps now use the same wider entry envelope as existing overlimps:
hand percentile <= min(0.95, positional entry threshold * 2.2). The threshold
already follows depth, personality, knowledge and pressure. This retains
eligible speculative limps and the original random draw count. No archetype
label is used as an action override.

The exact replay now folds B16 first-in: percentile 0.9729, raise threshold
0.290564, limp envelope 0.639241, limp probability 0. The Plan preflop timing
record now includes eligibility, envelope, probability and draw, making the
entry reason directly inspectable. Forced-low-draw checks retain 76s limps.

## Admission performance and UI

The default remains the real field backend. Replace 6/7-card subset enumeration
with direct exact best-five evaluation; retain eval5 for five cards and the
legacy fallback for unusual inputs. Cache keys and random draws are unchanged.
All 2,598,960 five-card sets and 90,000 sampled 5/6/7-card sets match the old
tuple evaluator, including wheel straight flushes, two trips and three pairs.

In isolated serial 44-bot turbo admissions, PYTHONHASHSEED=0 and identical
event/cards/settings produce identical complete state SHA-256 values:

| Workload | Legacy wall / CPU seconds | New wall / CPU seconds |
| --- | --- | --- |
| Entry at 0s; advance to 90s | 15.802 / 15.789 | 11.946 / 11.936 |
| Entry at 90s; advance to 180s | 45.629 / 45.576 | 26.423 / 26.390 |

These are local engine measurements, not end-to-end UI admission latency or
a guarantee on other hardware. Cold catch-up still costs real computation.
The late-entry pair's final state hash is
77456c9c76b37f0997f26b65e0957c278e00d229d58d9b193c3b656ff66954ed.
The first published snapshot also returns earlier (27.858s -> 17.166s).

Admission work now publishes after budget 18 rather than 48. The UI no longer
calls the near-current, hand-boundary wait 'synchronizing 99%, zero seconds';
it explains that the current hand must finish before the seat is prepared.
This does not bypass the completed-hand takeover requirement or fake progress.

Played the actual 9-max UI on two disposable 44-bot turbo runs. Manually folded
95o SB against a 400 open and 53o UTG; observed automatic admission, waiting
sheet dismissal, subsequent bot actions and hero-clock hiding after a fold.
Some other hands expired while inspecting code; this is not an uninterrupted
human-speed frequency sample. Removing all cold synchronization still requires
keeping the real-field scheduler running continuously; a shut-down server
cannot produce missed exact hands instantaneously.

## Validation

- tools/verify_limp_entry.py: exact HAND 19 replay and eligible speculative limp.
- tools/verify_exact_evaluator.py --all-five: exhaustive five-card and 90,000
  sampled comparisons, special categories and paired seven-card timings.
- tools/benchmark_cold_admission.py: real backend, fixed event, serial comparisons;
  use PYTHONHASHSEED=0 for both legacy and optimized runs.
- tools/verify_scheduled_tournaments.py: 38 tests pass.
- tools/verify_review_reasoning.py, verify_limp_iso_split.py,
  verify_preflop_temper_direction_v3.py: pass.
- ui/tools/verify_play_review.py and verify_action_clock_js.js: pass.
- Python compilation and git diff --check: pass.
