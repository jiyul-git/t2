# HAND130 B37: terminal heads-up prize ICM at actual call price

The original eight seated stacks, seven-place payout table, antes, blind and
full log are in `docs/handoff/T2_T3_HANDOFF_20261010.md` Appendix F.

* B37 folds: 17.700552609563854% prize share.
* B37 calls and loses: 15.461616393763215%.
* B37 calls and wins: 21.487760646031855%.
* B37 calls and ties the 161884-chip pot evenly: 18.733849424660832%.
* For **win/lose only**, the exact price-conditional break-even probability
  is 0.3715371093145927, not the old blanket BF-based 0.630692.
* The equivalent BF at actual price 53442 and fold pot 108442 is
  1.1996025358246731. The old blanket risk BF was 3.465325.
* Using the archived sampled **equity share** e=0.631820, possible
  unmeasured tie frequencies imply ICM EV relative to fold between
  +1.5685022456677338 and +1.7593379694992386 percentage points of
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
