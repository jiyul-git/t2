# P5 HAND130 B37 implementation and evidence report — 2026-10-10

## Branch / status

Branch: `chatgpt/hand130-calloff-audit-20261010`.
Not merged into `master`, `test`, or `test3`; NOT deployed.

Second-department prerequisites imported verbatim from current test3:
- `docs/semantic_audit/HAND130_PART2_DERIVATION_AUDIT.md`
- `tools/verify_hand130_part2.py`

Key implementation commits:
- `022a6517`: computed pure calloff selected action no longer vetoed by
  failed pf_defend knowledge gate.
- `25f62d32`: exact win/lose/tie/fold payout states in terminal
  all-field heads-up, using actual call cost.
- `874aa76e`: bypass `gto.defend_pct`, percentile cap,
  `defend_decision` entirely for actor pure allin calloff.
- `47bf1d64`: finite-MC decisions explicitly marked
  `mathematically_justified=False` until uncertainty/range certified.
- Additional tests and document commits are on this branch.

## Reproduced fixed input

From archived Appendix F, original HAND130 `6e1ba98ab1a0`.
B37 (LJ, Ac/Kh), 2BB open then B14 (BB) jam to 7.3442BB,
additional cost 53,442, contested 161,884 after call.
Original `legacy_cap=.005`, `hand_pct=.0302`, fold;
layer equity point .631820, original global-BF required .630692,
gate `p=.439355`, roll `.664054` (failed).
Seed 3365551903, noise seed 1495242137, gate seed 588629810.

New B37 actor decision with same archived profile, estimated equity,
pot price, seed and gate: **call**, conditional on those estimates.
No AKo-specific rule, rank floor or empirical coefficient.
The behavior-path call avoids all legacy defensive width computations.
Independent RNG state is exactly preserved by the actor decision.

## ICM review (P13 independent approval pending)

No-tie outcome-specific tournament-payout model, 8 players / 7 places:
- fold 17.700552609563854 payout percentage points
- lose 15.461616393763215
- win 21.487760646031855
- tie 18.515842285449054 (live odd-chip rules, B37=231422 BB=86884)
- exact *win/lose only* break-even probability .3715371093145927
- derived price-specific equivalent BF 1.1996025358246731, compared
  with old whole-stack BF 3.465325.
- observed E=.631820 implies *conditionally estimated*
  fold-relative payout EV from +1.5685022456677338 to
  +1.5988062324692514 percentage points over possible tie rates,
  before opponent-range and MC sampling uncertainties.

This exact spot-BF conversion is restricted to a terminal HU table
containing all remaining players. For all other pot structures the
current legacy general-BF path remains, with known limitations.

## Independent Monte Carlo / range sensitivity

Stored original opponent posterior has 288 combos, no individual weights.
This prevents authentic 800-seed re-run of the original.
Across two independent 800-sample per-layer Monte Carlo estimators,
weighted Hoeffding 95% halfwidth = 0.04127252077624719; original
global-BF equity margin is 0.001128. This is a conservative
*sampling-only* bound, not a claim about true range uncertainty.

Rebuilt T2 **counterfactual** 3bet posterior contexts are distinct
and demonstrate source-model sensitivity (six 800-run independent seeds
each; all use hero Ac/Kh, no new solver rates):

| T2 proxy (NOT original 288) | support | mean sampled equity | min to max | old BF point calls /6 |
|---|---:|---:|---:|---:|
| BB vs LJ 6.3442BB, open 2BB | 298 | 0.619895833 | .593750 to .637500 | 2 |
| BB vs LJ 20BB, open 2BB | 286 | 0.615416667 | .592500 to .631250 | 1 |
| BB vs LJ 40BB, open 2BB | 178 | 0.586458333 | .558125 to .603750 | 0 |
| BB vs BTN 40BB, open 2BB | 193 | 0.596875000 | .564375 to .613750 | 0 |
| BB vs UTG 40BB, open 2BB | 170 | 0.577395833 | .555625 to .606250 | 0 |
| BB vs LJ 40BB, open 4BB | 117 | 0.546354167 | .532500 to .572500 | 0 |

The exact payout no-tie *point* threshold .371537 was below all of
these proxy equity samples, but these counterfactual ranges are **not**
a posterior distribution for the actual B14 and do NOT certify optimal
play. The original 288 combos and their normalized weights must be
recovered for valid exact-range replication.

## Actor vs observer contract (P8 independent approval pending)

Actor terminal pure calloff bypasses general `gto.defend_pct` and
`preflop.defend_thresholds`. These shared producer definitions remain
byte-identical, so regular 3bet/4bet and `ranges.preflop_range` are
not silently retuned.

Unresolved P2 covering-shove future responders, P4 near-allin
nonterminal decisions, P6 first-in jam modeled as open and P7 deep
all-in caller reconstructed as a normal raise-eligible flat call.
No unsourced prior introduced to patch these.

## Skill semantics

`pf_defend` gate probability is logged, not a command to restore a
mathematically unrelated cap; no remembered call-vs-shove chart has
been independently validated to replace it. Actual individual
perception uses existing `icm_bf`, `calc_noise('potodds')`, and
observer range estimation. Skill probe:
- ICM concept 0→10: perceived BF 1.369799→3.465325
- potodds concept 0→10: calc noise .65→.950524
No extreme-ICM AA folding exception implemented.

## Checks / remaining blockers

Passed in GitHub Actions: archived B37 replay, Part2 static
derivation, exact price-specific ICM test and full planner propagation,
7/7 synthetic AA/KK/QQ/AK call-price ICM routing checks,
P1 legacy-producer monkeypatch rejection, pf_defend vs icm/potodds
skills, six-context range/seed sensitivity, P6 5/5.

`verify_preflop_closure.py` still fails for preexisting
weak habitual limp (expected limp, observed fold) on the unmodified
before commit too. No CI full-green claim.

Past paired comparison against `d4f2194`:
seed11: 725/725 actions same; seed12: 719/719 actions same,
0 field engine errors. B37 is not part of that capped sample.
Provenance/diagnostic fingerprints may differ without action changes;
saved `regress current` baseline mismatches in all six seeds on both
pre-change and changed branch, so should not be called a new regression
or an all-clear.

Part2 W5 difference was an audit formula-order error, not a preflop.py source bug. Correct W5=0.016657816839054443; old 0.013483745270 subtracted pre-mutation tp. Original process SHA / tilt still unknown. Since actor now bypasses that producer for
pure all-in, this disagreement no longer controls P1 behavior.

**Release gate:** Do not merge or deploy without recovering complete
observer posterior, independent P8 and P13 review of contracts,
running full canonical gates, identifying prior regression mismatches,
and verifying coverage for future-responder multiway/P2/P4/P7 paths.

## P13 odd-chip / unmatched-overbet fixes and P2 W5 update

P13 found two mathematical bugs: continuous split on tie (must use live award_pots SB unit and odd-chip order), and partial-call spot BF derived from full contributed pot rather than hero-eligible pot. Both regression cases now pass. HAND130 no-tie break-even is preserved (37.1537109315%).

P2's latest test3 contract is at commit 2781cd547128a616424facedf60ef8654f99d775. Correct legacy W5=0.016657816839054443; producer preflop.py not modified. The former 0.013483745270 was an audit sequencing mistake: new tp is used in tot after tp*=lt. The static verifier, hand fixture and corrected Part2 docs are imported unchanged.

Alignment with calloff_evidence_v1: hero-eligible chip pots and incremental cost, conditionally reconstructed opponent combos, layer equity with sims/seed, and objective vs perceived BF are distinct inputs. **Outstanding contract gaps:** original 288 combo weights, action-conditioned range provenance and source SHA, effective Monte Carlo sample count/error, complete field stacks from other tables, and the nonterminal scalar-BF fallback. A necessary legal fallback fold is tagged as insufficient evidence and not an EV-proven fold. Independent P13/P8 signoff and the legacy closure CI failure block merging.
