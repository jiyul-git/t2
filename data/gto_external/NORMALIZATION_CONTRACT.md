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
