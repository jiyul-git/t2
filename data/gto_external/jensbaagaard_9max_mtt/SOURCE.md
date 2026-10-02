# External 9-max MTT preflop harvest

Source: jensbaagaard/poker-practice @ 449993f78d995c77b72d0bcac418a8507dd6f783

Upstream README states the repository is MIT licensed and the range data under `data/openSourcePokerData/` is free to use.

Imported raw GTO-frequency sets: 5bb, 10bb, 20bb, 40bb, 100bb. Each upstream file uses 271 scenario keys covering opens and later preflop responses (where that node exists at the stack depth), with 169 starting-hand classes as the base vocabulary.

Important limitation: these are fixed nominal/effective-stack packs. They do not enumerate arbitrary per-seat stack vectors, ICM payout states, or T2 exact-BBA state. Keep them as external reference evidence, not as a silent replacement for T2-native solves.


## T2 locator and coverage

Canonical locator for this harvested pack in T2:

- branch: `chatgpt/gto-external-harvest-20261003`
- raw packs: `data/gto_external/jensbaagaard_9max_mtt/MTT_{5,10,20,40,100}_GTO.json`
- generated hand-level chart packs: `data/gto_external/jensbaagaard_9max_mtt/charts/MTT_*_GTO.charts.json`
- inventory index: `data/gto_external/jensbaagaard_9max_mtt/charts/INDEX_9MAX.json`

Coverage is **5 stacks × 271 scenarios = 1,355 scenario tables**, with all **169 starting-hand classes** represented per table.

There is **no 30bb pack** in this source. For 30bb validation, 20bb and 40bb are neighboring-stack evidence only and must not be relabeled as an exact 30bb reference. Search other harvested/public crosscheck sources before concluding that no exact 30bb hand-level reference exists.
