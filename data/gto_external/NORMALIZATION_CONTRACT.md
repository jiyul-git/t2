# External GTO normalization contract

The operational GTO database is keyed by poker state, action, hand class, and frequency only.
Source/provider/chart provenance is not part of the normalized row schema or lookup path.

Each normalized frequency row must retain:
- game format and table size
- objective: ChipEV / ICM / PKO / unknown
- ante/blind model
- stack model: symmetric/effective/asymmetric-vector
- full per-seat stack vector when available
- hero position and every relevant opponent position
- complete preflop action history and sizes when available
- action being represented (open/call/3bet/4bet/5bet/jam/limp/etc.)
- 169-class hand label
- hand_shape = pair / suited / offsuit
- exact frequency
- conditional/reach semantics
- value_status = exact / derived

Do not store `source_id`, provider, URL, chart id, origin kind, or lookup provenance in operational normalized rows.
A chart/table import must be exploded into the same per-state, per-hand, per-action rows before it becomes queryable.
Solver-computed values use the same schema. Runtime lookup must never route through a chart representation.

Never interpolate a missing stack/position/action node and store it as exact data.
Derived/interpolated values are allowed only when explicitly requested and must be marked `value_status=derived`.
Never merge 8-max into 9-max.
Never merge symmetric and asymmetric-stack solutions into one value.
Identical duplicate rows for the same canonical state/action/hand may collapse.
Conflicting frequencies for the same canonical key must not be silently averaged; resolve the conflict before admitting a single operational value.

License files required by copied open-source code/data remain separate repository/legal artifacts and are not runtime DB provenance.
