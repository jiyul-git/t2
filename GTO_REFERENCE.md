# GTO reference branch

Purpose: store verified GTO reference material and situation-specific calculations without building a full solver yet.

## Scope
- Hold'em tournament preflop first.
- Table size: 2–9 players.
- Effective stack input: continuous, 1–600 bb.
- Main validation zone: 5–300 bb.
- 300–600 bb is supported but tagged as ultra-deep and validated separately.
- Postflop can be added case-by-case later.

## Rule
Do not tune production constants from a single chart or one mismatched game condition.

For every reference row, preserve:
1. players / positions
2. effective stacks
3. blinds / ante
4. action history
5. allowed sizes
6. source or calculation method
7. raise / call / fold frequencies
8. whether the source conditions exactly match
9. current t2 output
10. discrepancy and decision

## Status labels
- exact: source/calculation conditions match.
- near: small mismatch; comparison only.
- pending: not yet solved/verified.
- rejected: not suitable as a tuning target.

## Current direction
Use GTO as the neutral baseline. Persona, skill, reads, exploit and tournament pressure are applied only after the neutral baseline is validated.

Do not implement CFR yet. When a real hand exposes a questionable preflop node, calculate or source that exact node and append it to `data/gto_scenarios.jsonl`.
