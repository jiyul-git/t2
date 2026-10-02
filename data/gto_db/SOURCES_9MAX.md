# 9-max GTO source registry

This registry separates **data we may store** from **data we may only inspect/cross-check**.

| Source | 9-max MTT | Stack coverage | Ante model | Frequencies | Local storage | Role |
|---|---|---|---|---|---|---|
| HoldemMath `holdemmath-data` | yes | 4/6/8/10/12/15/20bb | no ante + 0.1bb/player | push/fold shove + calls | **yes**, CC BY 4.0 | Tier-2 short-stack seed |
| Jens Baagaard `poker-practice` | yes | **5/10/20/40/100bb** | upstream MTT model; preserve source assumptions | **169-class mixed frequencies; 271 scenarios/stack** | **yes**, MIT, on `chatgpt/gto-external-harvest-20261003` | primary redistributable hand-level 9-max MTT cross-check; **no 30bb pack** |
| PokerData tournament packs | yes | methodology states 10–100bb | **big-blind ante** | full preflop packs | not fetched without authorized data access | exact-target validation candidate |
| PreflopRanges / public chart viewer | yes | public 10–40bb MTT views | chart-specific MTT ante | mixed strategy | **no bulk extraction** | manual aggregate/boundary cross-check only |
| GTO Academy public charts | yes | public selector includes mid/deep stacks | chart-specific | chart view | do not vendor unless rights are explicit | manual cross-check |
| T2 vendored GTOpen | configurable to 9 seats | configurable | legacy uniform ante; BBA only approximated by equal total dead money | generated strategy | our generated outputs only | fill gaps after public search |
| Existing Matthiola source | **8-max** | 3–100bb | unspecified MTT ante | RFI/vs-open mixed frequencies | yes, MIT | auxiliary methodology / sensitivity only |
| haowenzheng-art/poker-gto-trainer generated JSON | nominally 9-max | 100bb/250bb files | unclear | many action tables | **no** | rejected as canonical: sampled files report `solver: fallback`, `accuracy: 0.0`, and include semantically suspect unopened-call mixes |
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

### Rejected bulk source: poker-gto-trainer

The repository contains many 9-player JSON files, but sampled records identify the solver as `fallback` with `accuracy: 0.0`. An unopened UTG record also assigns nonzero `call` frequency, which is not a legal first-in action under the stated scenario. Keep this source out of the canonical GTO DB unless its generation/provenance is independently clarified.


## Hand-level reference locator

When looking for already-collected 9-max MTT hand frequencies, do **not** stop after searching `data/gto_db/` on the older reference branch.

The current redistributable hand-level pack is on:

- branch: `chatgpt/gto-external-harvest-20261003`
- path: `data/gto_external/jensbaagaard_9max_mtt/charts/`
- files: `MTT_5_GTO.charts.json`, `MTT_10_GTO.charts.json`, `MTT_20_GTO.charts.json`, `MTT_40_GTO.charts.json`, `MTT_100_GTO.charts.json`
- index: `data/gto_external/jensbaagaard_9max_mtt/charts/INDEX_9MAX.json`

Inventory: **5 stack packs × 271 scenario tables = 1,355 tables**, each with all **169 hand classes** and mixed action frequencies.

Important: this source has **no 30bb pack**. For a 30bb solver comparison, 20bb/40bb are neighboring-stack evidence, not exact-match truth. Search the rest of the harvested catalog before declaring that no exact 30bb hand-level reference exists.
