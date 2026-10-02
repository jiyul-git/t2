# External 9-max MTT preflop harvest

Source: jensbaagaard/poker-practice @ 449993f78d995c77b72d0bcac418a8507dd6f783

Upstream README states the repository is MIT licensed and the range data under `data/openSourcePokerData/` is free to use.

Imported raw GTO-frequency sets: 5bb, 10bb, 20bb, 40bb, 100bb. Each upstream file uses 271 scenario keys covering opens and later preflop responses (where that node exists at the stack depth), with 169 starting-hand classes as the base vocabulary.

Important limitation: these are fixed nominal/effective-stack packs. They do not enumerate arbitrary per-seat stack vectors, ICM payout states, or T2 exact-BBA state. Keep them as external reference evidence, not as a silent replacement for T2-native solves.
