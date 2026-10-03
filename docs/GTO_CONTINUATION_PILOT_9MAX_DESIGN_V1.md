# 9-max 30bb continuation-model correction pilot — design v1 (no solve started)

Input: audit `data/gto_validation/30bb_solver_reference_audit_v1.{json,md}`. The audit's strongest internal evidence: the flop-terminal
payoff `pot x equity x r` (r identical for every hand class) over-values passive continues (BB folds ~1%, SB flats 32-37%), which makes
openers tight; replacing that payoff with solved flop values at two HU terminals in the 4-handed game moved BTN RFI 37.6 -> 41.4% and
BB vs BTN fold 0 -> 6.5%.

## Rules
- No tuning of the static realization coefficients. The correction is structural: selected terminals get solved postflop continuation
  values (the existing `t2_cont` injection, gross-share tables per class and seat).
- HU terminals first, by reach. Multiway terminals stay on the static payoff in this pilot and are reported as the remaining unsolved share.
- A4c (4-handed, nodes 6 / 28) is mechanism evidence only: no A4c number is used as a target, coefficient or prior.
- References remain near-references; success is a move in the expected direction plus internal consistency, never "matches GTO".
- The pilot keeps the audit's solver config (same tree, stack semantics, seeds) so the measured change isolates the continuation model.
  The exact uniform-ante stack (`cfg.stack = S - 1/9`) is applied only after the model question is settled.
- E1 stays paused; Termux 20/25/30/40bb stay on hold (provenance only).

## Steps
| step | what | cost (wall, 4 cores) |
|---|---|---|
| C0 | 9-max census of flop-reaching terminals at the 100-iteration reproduction state (`t2_cont_census`, same config): exact node ids, reach, HU vs multiway share | about 1 h |
| C1 | injection identity check in the 9-max tree: inject tables equal to the static payoff at the selected nodes -> preflop solve must reproduce the un-injected solve | about 1 h |
| C2 | flop panels at the selected HU terminals at the C0 ranges: one 24-board stratified panel (same boards for every terminal) | 24 boards x ~0.15 CPU-h per terminal |
| C3 | one outer step: inject the C2 tables, preflop solve (100 iterations), measure; optional second step (damped, alpha 0.5 on tables, raw-residual check) only if C3 moves the metrics | about 1 h per preflop solve |

Terminal set (approximate reach from the pilot artifact, independence approximation; C0 replaces these numbers):

| terminal (all others fold) | approx. reach |
|---|---|
| SB open, BB call | 0.046 |
| BTN open, BB call | 0.043 |
| CO open, BB call | 0.037 |
| HJ open, BB call | 0.036 |
| LJ open, BB call | 0.030 |
| UTG+1 open, BB call | 0.029 |
| UTG open, BB call | 0.021 |
| UTG+2 open, BB call | 0.020 |

- Option S (small): the 4 largest (SB, BTN, CO, HJ vs BB): 96 flop solves, about 14 CPU-h (about 3.6 h wall) + C0 / C1 / C3 about 3 h -> about 7 h.
- Option F (full HU set): all 8: 192 flop solves, about 29 CPU-h (about 7.2 h wall) + about 3 h -> about 10 h.
Panel size 24 is a direction-of-movement pilot: its panel error is several times the A4c 232/218-board level and is reported with
the result; it is not a production panel.

## Measurements (static reproduction 100 it vs pilot)
- UTG..BTN RFI (combo-weighted), opener jam share per position
- BB vs CO / BTN fold; SB flat vs EP / MP / CO / BTN opens; BTN cold-call
- action EV ordering and frequencies for A5s, K9s, KQo, 55, 98s, 22, AKo at UTG / HJ / CO / BTN (and BB vs BTN)
- modal != best-EV share and mean class regret (convergence)
- remaining static share: reach of terminals still on the pot-share payoff (multiway first)
- expected direction if the mechanism holds: BB / SB fold more and flat less, openers loosen (most at positions whose terminals were
  replaced), opener jam share falls, A5s / K9s / 98s-type hands move toward raise. A move against this direction, or no move, falsifies
  the mechanism for 9-max and is reported as such.

## Decision after the pilot
- mechanism confirmed in 9-max -> design the full HU replacement (larger panels, outer loop with the E1 raw-residual rule) and a
  separate multiway plan; only then decide whether to restart E1 and on which config.
- not confirmed -> back to the audit list (multiway payoff, action abstraction, reference conditions).

## Decision (2026-10-03): Option S, terminals chosen from C0
- Option S, conditional on the 100-iteration audit check not overturning the audit (expected pattern: aggregate RFI unchanged, hand-level
  regret down -> convergence ruled out as the main cause).
- The 4 terminals are NOT fixed in advance: C0 gives exact HU flop-terminal reach at the 100-iteration state; selection then maximises
  diagnostic value: BTN->BB and CO->BB included, plus at least 2 of HJ / LJ / UTG-family -> BB, so early / middle / late openers are covered.
- SB->BB may be left out of the core 4 even with high reach (2.5 bb / no-limp SB tree is far from every reference); it is included only
  with an explicit C0-based reason.
- Order C1 identity -> C2 24-board panel -> C3 one outer step.
- Expand to F / full HU only if S moves clearly in the expected direction; no move or the wrong direction -> stop, no automatic F, back to
  the hypothesis list.
- E1 stays paused at 24/450; Termux DB on hold; no solver-logic change or DB promotion.

## Analysis states (fixed 2026-10-03, before C3 results)
- O = original dynamic static payoff (100 it); F = C1b frozen static tables at the 4 nodes (100 it); S = C3 frozen solved tables (100 it).
- F - O = table-freezing effect; S - F = solved-continuation content effect = the pilot's main estimate; S - O is reported as total change only
  and is never called the continuation effect.
- If F's selected-node reach / ranges differ strongly from O, the size is recorded; C2 stays outer step 1 at O's endpoint ranges (no re-solve).
- Expected direction judged on S - F per node / position: selected opener RFI up; that BB fold up / passive call down; opener jam share down;
  playability hands (A5s / K9s / 98s ...) move from fold / jam toward raise. Opposite moves are reported per node, never averaged away.
- After C3: stop. No automatic outer step 2, no expansion to F (full HU).
