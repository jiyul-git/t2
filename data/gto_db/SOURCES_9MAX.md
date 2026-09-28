# 9-max GTO source registry

This registry separates **data we may store** from **data we may only inspect/cross-check**.

| Source | 9-max MTT | Stack coverage | Ante model | Frequencies | Local storage | Role |
|---|---|---|---|---|---|---|
| HoldemMath `holdemmath-data` | yes | 4/6/8/10/12/15/20bb | no ante + 0.1bb/player | push/fold shove + calls | **yes**, CC BY 4.0 | Tier-2 short-stack seed |
| PokerData tournament packs | yes | methodology states 10–100bb | **big-blind ante** | full preflop packs | not fetched without authorized data access | exact-target validation candidate |
| PreflopRanges / public chart viewer | yes | public 10–40bb MTT views | chart-specific MTT ante | mixed strategy | **no bulk extraction** | manual aggregate/boundary cross-check only |
| GTO Academy public charts | yes | public selector includes mid/deep stacks | chart-specific | chart view | do not vendor unless rights are explicit | manual cross-check |
| T2 vendored GTOpen | configurable to 9 seats | configurable | legacy uniform ante; BBA only approximated by equal total dead money | generated strategy | our generated outputs only | fill gaps after public search |
| Existing Matthiola source | **8-max** | 3–100bb | unspecified MTT ante | RFI/vs-open mixed frequencies | yes, MIT | auxiliary methodology / sensitivity only |
| davidvayn/pokersolver curated full-ring | 9-max | 100bb | cash baseline | hard curated ranges | source code MIT | low-confidence auxiliary only |

## Retrieval rule

For every desired canonical spot:
1. search for a legally reusable exact 9-max MTT/BBA source;
2. if no reusable source exists, inspect a small number of public-viewer values for validation only;
3. generate the missing spot with the solver;
4. mark solver assumptions and convergence;
5. do not call a non-BBA or restricted-tree output `exact`.

## T2 target

T2 tournament ante stage is 1BB **big-blind ante**. The current GTOpen preflop engine has a uniform per-seat dead-ante parameter and equal live-stack cap. Using 1/9bb per seat reproduces 1BB total dead money but not the BB-specific stack deduction. Such outputs are tagged `near/limited`, with BB defense receiving extra scrutiny.
