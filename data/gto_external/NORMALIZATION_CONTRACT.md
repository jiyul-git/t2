# External GTO normalization contract

Raw source files are immutable evidence. Normalization never overwrites them.

Each normalized frequency row must retain:
- source_id and source version/commit
- game format and table size
- objective: ChipEV / ICM / PKO / unknown
- ante/blind model
- stack model: symmetric/effective/asymmetric-vector
- full per-seat stack vector when the source provides it
- hero position and every relevant opponent position
- complete preflop action history and sizes when available
- action being represented (open/call/3bet/4bet/5bet/jam/limp/etc.)
- 169-class hand label
- hand_shape = pair / suited / offsuit
- exact source frequency
- conditional/reach semantics
- direct/derived flag and confidence
- source URL/license/restrictions

Never interpolate a missing stack/position/action node and store it as observed data.
Never merge 8-max into 9-max.
Never merge symmetric and asymmetric-stack solutions into one value.
Multiple sources for the same canonical state remain separate observations until cross-validation.

## Lookup provenance and chart separation

Every lookup must distinguish the representation that actually supplied the value.

Required provenance fields:
- `origin_kind`: `individual_frequency` / `chart_cell` / `derived` / `crosscheck_only`
- `origin_id`: raw range key, chart id, or derivation id
- `chart_available`: whether an independently addressable chart exists for the same canonical state
- `individual_frequency_available`: whether direct hand/action frequency data exists for the same canonical state
- `lookup_used`: which representation supplied the returned value

Lookup priority:
1. exact individual hand/action frequency from immutable raw source data
2. exact chart cell only when no individual frequency exists
3. derived/interpolated value only when explicitly requested, never silently

A chart generated from the same raw table is a derived presentation view, not an independent observation. Do not route an individual-frequency query through a chart when the raw hand/action frequency is available. When both exist, return the individual value and report the chart only as additional coverage/provenance.
