# Nash push/fold ranges (6-max and 9-max)

Chip-EV Nash push/fold (shove-or-fold) frequencies for all 169 starting-hand classes, every seat that can open-shove in 6-max and 9-max, at stacks from 1 to 25 big blinds. Each row gives the push frequency and a shove/mixed/fold verdict.

This is a mirror of the open dataset published by [RangeMyHand](https://www.rangemyhand.com) at
[www.rangemyhand.com/data/push-fold-ranges.json](https://www.rangemyhand.com/data/push-fold-ranges.json) and
[www.rangemyhand.com/data/push-fold-ranges.csv](https://www.rangemyhand.com/data/push-fold-ranges.csv).
It is regenerated from the same source on every range update. Do not edit it by hand.

- **Version:** 0.2.1 · **ranges last verified:** 2026-09-29
- **Coverage:** 169 hand classes × 225 spots (9 seats × 25 stacks) = 38,025 rows
- **Methodology:** https://www.rangemyhand.com/methodology

## Files

| File | Shape |
| --- | --- |
| `push-fold-ranges.json` | metadata, model parameters, `hands` (the 169 classes in order) and `spots[]`, each with `table`, `seat`, `playersBehind`, `stackBB` and `pushFreq` (169 numbers, same order as `hands`) |
| `push-fold-ranges.csv` | one row per hand per spot: `table,seat,players_behind,stack_bb,hand,push_freq,verdict` |

`push_freq` is the equilibrium shove frequency from 0 to 1. The verdict is `shove` at 95% or more,
`fold` at 5% or less, and `mixed` in between.

## Model

- chip-EV Nash push/fold equilibrium (fictitious play)
- Stack convention: stack in big blinds behind the posted blinds; dead money 1.5BB (the blinds), no antes
- 220 fictitious-play iterations, 6,000 equity samples per matchup, seed 3735928559
- Chip-EV only: no ICM. Near a bubble or a final table the correct range is tighter.

Full write-up, assumptions and verification: https://www.rangemyhand.com/methodology

## Browse the charts

Charts by stack: [5BB](https://www.rangemyhand.com/push-fold/charts/5bb) · [8BB](https://www.rangemyhand.com/push-fold/charts/8bb) · [10BB](https://www.rangemyhand.com/push-fold/charts/10bb) · [12BB](https://www.rangemyhand.com/push-fold/charts/12bb) · [15BB](https://www.rangemyhand.com/push-fold/charts/15bb) · [20BB](https://www.rangemyhand.com/push-fold/charts/20bb)

Every seat (columns are stacks in big blinds):

| Table | Seat | Stack |
| --- | --- | --- |
| 6-Max | Under the Gun | [5](https://www.rangemyhand.com/push-fold/6max/utg/5bb) · [8](https://www.rangemyhand.com/push-fold/6max/utg/8bb) · [10](https://www.rangemyhand.com/push-fold/6max/utg/10bb) · [12](https://www.rangemyhand.com/push-fold/6max/utg/12bb) · [15](https://www.rangemyhand.com/push-fold/6max/utg/15bb) · [20](https://www.rangemyhand.com/push-fold/6max/utg/20bb) |
| 6-Max | Cutoff | [5](https://www.rangemyhand.com/push-fold/6max/co/5bb) · [8](https://www.rangemyhand.com/push-fold/6max/co/8bb) · [10](https://www.rangemyhand.com/push-fold/6max/co/10bb) · [12](https://www.rangemyhand.com/push-fold/6max/co/12bb) · [15](https://www.rangemyhand.com/push-fold/6max/co/15bb) · [20](https://www.rangemyhand.com/push-fold/6max/co/20bb) |
| 6-Max | Button | [5](https://www.rangemyhand.com/push-fold/6max/btn/5bb) · [8](https://www.rangemyhand.com/push-fold/6max/btn/8bb) · [10](https://www.rangemyhand.com/push-fold/6max/btn/10bb) · [12](https://www.rangemyhand.com/push-fold/6max/btn/12bb) · [15](https://www.rangemyhand.com/push-fold/6max/btn/15bb) · [20](https://www.rangemyhand.com/push-fold/6max/btn/20bb) |
| 6-Max | Small Blind | [5](https://www.rangemyhand.com/push-fold/6max/sb/5bb) · [8](https://www.rangemyhand.com/push-fold/6max/sb/8bb) · [10](https://www.rangemyhand.com/push-fold/6max/sb/10bb) · [12](https://www.rangemyhand.com/push-fold/6max/sb/12bb) · [15](https://www.rangemyhand.com/push-fold/6max/sb/15bb) · [20](https://www.rangemyhand.com/push-fold/6max/sb/20bb) |
| 9-Max | Under the Gun | [5](https://www.rangemyhand.com/push-fold/9max/utg/5bb) · [8](https://www.rangemyhand.com/push-fold/9max/utg/8bb) · [10](https://www.rangemyhand.com/push-fold/9max/utg/10bb) · [12](https://www.rangemyhand.com/push-fold/9max/utg/12bb) · [15](https://www.rangemyhand.com/push-fold/9max/utg/15bb) · [20](https://www.rangemyhand.com/push-fold/9max/utg/20bb) |
| 9-Max | Middle Position | [5](https://www.rangemyhand.com/push-fold/9max/mp/5bb) · [8](https://www.rangemyhand.com/push-fold/9max/mp/8bb) · [10](https://www.rangemyhand.com/push-fold/9max/mp/10bb) · [12](https://www.rangemyhand.com/push-fold/9max/mp/12bb) · [15](https://www.rangemyhand.com/push-fold/9max/mp/15bb) · [20](https://www.rangemyhand.com/push-fold/9max/mp/20bb) |
| 9-Max | Cutoff | [5](https://www.rangemyhand.com/push-fold/9max/co/5bb) · [8](https://www.rangemyhand.com/push-fold/9max/co/8bb) · [10](https://www.rangemyhand.com/push-fold/9max/co/10bb) · [12](https://www.rangemyhand.com/push-fold/9max/co/12bb) · [15](https://www.rangemyhand.com/push-fold/9max/co/15bb) · [20](https://www.rangemyhand.com/push-fold/9max/co/20bb) |
| 9-Max | Button | [5](https://www.rangemyhand.com/push-fold/9max/btn/5bb) · [8](https://www.rangemyhand.com/push-fold/9max/btn/8bb) · [10](https://www.rangemyhand.com/push-fold/9max/btn/10bb) · [12](https://www.rangemyhand.com/push-fold/9max/btn/12bb) · [15](https://www.rangemyhand.com/push-fold/9max/btn/15bb) · [20](https://www.rangemyhand.com/push-fold/9max/btn/20bb) |
| 9-Max | Small Blind | [5](https://www.rangemyhand.com/push-fold/9max/sb/5bb) · [8](https://www.rangemyhand.com/push-fold/9max/sb/8bb) · [10](https://www.rangemyhand.com/push-fold/9max/sb/10bb) · [12](https://www.rangemyhand.com/push-fold/9max/sb/12bb) · [15](https://www.rangemyhand.com/push-fold/9max/sb/15bb) · [20](https://www.rangemyhand.com/push-fold/9max/sb/20bb) |

Per-hand pages: [www.rangemyhand.com/push-fold/hands](https://www.rangemyhand.com/push-fold/hands)

## License and attribution

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). You can share and adapt the data, including commercially, as long as you credit it:

> RangeMyHand Nash push/fold ranges (www.rangemyhand.com), CC BY 4.0

## Citation

```bibtex
@misc{rangemyhand_pushfold_2026,
  title        = {Nash push/fold ranges for 6-max and 9-max tournament poker},
  author       = {{RangeMyHand}},
  year         = {2026},
  version      = {0.2.1},
  howpublished = {\url{https://www.rangemyhand.com/data/push-fold-ranges.json}},
  note         = {Mirror: https://github.com/hasuwini77/push-fold-ranges. Methodology: https://www.rangemyhand.com/methodology. License: CC BY 4.0}
}
```

GitHub also reads `CITATION.cff` for its "Cite this repository" button.
