# HAND130 B37: terminal heads-up prize ICM at actual call price

The original eight seated stacks, seven-place payout table, antes, blind and
full log are in `docs/handoff/T2_T3_HANDOFF_20261010.md` Appendix F.

* B37 folds: 17.700552609563854% prize share.
* B37 calls and loses: 15.461616393763215%.
* B37 calls and wins: 21.487760646031855%.
* B37 calls and ties the 161884-chip pot under the actual SB=5000 / BTN-left odd-chip priority: 18.515842285449054% (B37 final 231422, BB 86884).
* For **win/lose only**, the exact price-conditional break-even probability
  is 0.3715371093145927, not the old blanket BF-based 0.630692.
* The equivalent BF at actual price 53442 and fold pot 108442 is
  1.1996025358246731. The old blanket risk BF was 3.465325.
* Using the archived sampled **equity share** e=0.631820, possible
  unmeasured tie frequencies imply ICM EV relative to fold between
  +1.5685022456677338 and +1.5988062324692514 percentage points of
  the payout pool (BEFORE Monte Carlo and range-estimation error).

This conditional model is applied only when every remaining tournament player
is at this table (<=9), exactly hero and one opponent are not folded, and that
opponent is all-in. It refuses other scenarios instead of guessing side-pot
prize impact. The model currently uses the existing actor-perceived BF and
pot-odds noise layers with the **derived price-specific** objective BF.

**Unresolved:** The 288-combo weighted prior and 800 Monte Carlo draws are not
in the archived hand excerpt. Exact equity precision and model specification
remain uncertain. Equities are not recomputed from the original opponent
range. General 3bet/4bet prior, first-in shove posterior, multiway and future
responders remain separate tasks. A sampled equity share is not a direct
win-frequency estimate because ties may occur.

No hand-specific call override or new numerical experience coefficient.

## P13 mathematical review corrections (2026-10-10)

Previously continuous 50/50 tie distribution and 18.733849% ICM was WRONG. Live award_pots per-layer SB-unit and BTN-left odd-chip rule now shared via _split_pot_winnings. Correct tied outcome: hero receives 75000, BB 86884; hero ends at 231422, BB 86884; prize share 18.515842285449054%. Conditional tie-frequency payout EV range with saved E=.631820: +1.5685022456677338 to +1.5988062324692514 points above fold (without MC/range model uncertainty). Win/lose only break-even equity unchanged at 0.3715371093145927.

For opponent uncalled excess, the derived spot BF numerator must use hero-contestable pot BEFORE CALL, not total contributed pot. The P13 synthetic test checks 40.2587519026% versus obsolete 45.7216940363% and chip conservation. See verify_hand130_exact_icm.py and verify_hand130_partial_call_icm.py. No deployment or P13 independent signoff yet.
