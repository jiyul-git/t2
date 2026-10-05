# 9-max 30bb step 3a (25 HU 3-bet tables) — state T result, SEALED as capped-tree evidence

**Scope label: continuation correction evidence under `max_raises = 2` (open + 3-bet cap).** In this tree nobody can raise after a
3-bet: the opener facing a 3-bet has only fold / call (verified on all 25 path exports: action lists `Fold, Call 6|8|10`), and a
cold player behind the 3-bet also has only fold / call. `fourbet_mults` in the config is inactive. T therefore says how the preflop
strategy of this capped tree changes when its HU 3-bet pots get solved postflop values; it does not say the 3-bet strategy is
trustworthy. T is not a DB source.

State T: the 8 OL state-2 HU SRP tables + 25 HU 3-bet tables (panel_v1, 24 boards, A4c estimator, at state-2 ranges; 600/600 flops
<= 0.30% pot, max 0.299), one preflop solve (100 it, same config / seeds). Data: `data/gto_validation/pilot9/step3/`
(t3_selection.json, t3_trigger.json, t3_coverage_T.json); checkpoints under `/home/user/gto_ckpt/step3/`.

## Pre-registered joint-OL trigger (fixed in d0881d4 / eaad596 before T existed)
- R = max |M(s2) - M(s1)| = 4.33 pp (n14 BB-vs-SB 3-bettor call); D = max |M(T) - M(s2)| = 22.0 pp (SB jam share of opens 28.7 -> 6.7%).
- 44 of 216 elements move by more than R. Rule outcome: D > R -> "run 33-table joint OL".
- **Not executed (user decision 2026-10-05):** the loop would refine a tree known to lack 4-bets; the action-abstraction audit comes
  first. The trigger result stays on record; the loop is deferred, not cancelled by the rule.

## State 2 -> T (largest moves)
| metric | state 2 | T |
|---|---|---|
| BTN RFI | 38.4% | 50.2% |
| SB RFI | 62.6% | 68.9% |
| jam share of opens BTN / SB | 6.9% / 28.7% | 0.0% / 6.7% |
| SB vs CO open: fold / call / 3-bet / jam | 47.2 / 34.5 / 12.0 / 6.3 | 37.3 / 48.4 / 14.3 / 0.0 |
| IP 3-bettors (21 paths): 3-bet jam frequency | 1.2-6.0% | 0% (3-bet raise frequency +2.6 to +7.3 pp) |
| opener fold vs IP 3-bet (21 paths) | 0.0% | 0.0% |
| opener fold vs SB 3-bet (BTN / CO / HJ / LJ) | 0.0% | 3.6 / 4.2 / 6.7 / 8.1% |

Reading: with solved 3-bet-pot values, raising (and calling 3-bets) gains against jamming, so jam-heavy strategies at BTN / SB and
3-bet jams disappear, and BTN opens much wider. Openers still never fold to IP 3-bets: in this tree a 3-bet can never be 4-bet,
so the opener's range only compares fold with a flop at 3-bet pot odds (needs ~28% of the pot), which every opening hand clears.

## Coverage (census at T; shares of flop reach 0.826)
| | share |
|---|---|
| solved: 8 HU SRP tables | 24.0% |
| solved: 25 HU 3-bet tables | 26.6% (83.2% of HU 3-bet reach; selection still covers > 80% at T) |
| **solved total** | **50.5%** |
| static: HU 3-bet tail | 5.4% |
| static: 3-way+ SRP | 27.2% |
| static: 3-way+ 3-bet | 16.9% |
| **static total** | **49.5%** |

About half of flop reach carries solved postflop values; the calculator is not complete.
