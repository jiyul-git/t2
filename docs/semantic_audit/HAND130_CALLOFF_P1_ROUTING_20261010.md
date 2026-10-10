HAND130 P1 price/ICM routing — scoped implementation

* Pure calloffs with complete per-layer equity and actual call price now act on
  calloff_layer_judgment. Failed pf_defend knowledge gate remains observable
  but cannot revive an unrelated percentile defense cutoff.
* B37 old fold and new call are replayed from the exact archived profile,
  original decision/gate/noise RNG seeds and stored layer MC outcomes.
* No GTO rates, hand-specific exceptions, new empirical coefficients, or
  changes to generic 3bet/4bet prior or first-in shove reconstruction.
* Synthetic hand-class, price and BF matrix tests exercise direction and
  codepath only: hypothetical equities are not poker equity estimates.
* Known limit: 800 requested MC samples lack accepted-sample count/variance;
  opponent 288-combo weights not archived; objective delta 0.001128 is
  statistically unverified. Shove range reconstruction P2/P6/P7 and 9max
  defense priors remain unresolved; no claim of optimal HAND130 call.
