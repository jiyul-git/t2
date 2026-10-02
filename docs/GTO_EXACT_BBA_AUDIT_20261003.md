# Exact T2 1BB BBA audit — 2026-10-03

## Scope

Audit only. This branch does not change the running DB worker or promote any result to exact T2 BBA.

Target state is the canonical DB model used by `tools/gto_db_schema.py`:
- 9-max NLHE MTT
- SB 0.5bb / BB 1bb
- 1bb big-blind ante
- `stack.prehand_bb` is the identity field in the canonical state.

The current worker intentionally solves a near-target model:
- `ante = 1/9 bb` for every seat
- total dead money = 1bb
- quality = `qualified_near_t2_bba`
- `exact_target_match = false`

## Source findings

### 1. The solver supports only one scalar dead ante

`PreflopConfig` currently has:

```rust
pub stack: f64,
pub posts: Vec<f64>,
pub ante: f64,
```

The comment on `stack` says starting stacks must be equal for all seats.
The comment on `ante` says it is a dead ante **per seat**.

The root state is built as:

```rust
invested[i] = posts[i] + ante
```

and legal action accounting subtracts that same scalar ante:

```rust
inv_live = invested[actor] - ante
```

Calls/raises then restore the same scalar ante:

```rust
invested[actor] = to_call + ante
invested[actor] = raise_to + ante
```

Therefore the current data model cannot represent "only BB posts 1bb dead ante".

### 2. Adding only an `antes_by_seat` vector is not enough for exact pre-hand stacks

A mechanical change from scalar `ante` to seat-specific dead antes is feasible and touches a limited set of accounting sites.

However, there is a second semantic issue:

The current solver caps live contribution using the common scalar `stack`, while dead ante is added outside that live amount. For example an all-in is detected by comparing the live TO amount with `cfg.stack`.

If canonical `prehand_bb = 30` means 30bb **before** forced bets, exact BBA produces different chips-behind immediately:
- ordinary seat: live cap remains 30bb total contribution
- BB: 1bb of the same 30bb has already been spent as dead BBA, so only 29bb remains available for live contribution, in addition to the blind accounting.

Using `stack = 30` for every seat plus a 1bb BB-only dead ante would let the BB contribute 31bb total, which is not an exact 30bb pre-hand stack.

The solver explicitly documents equal stacks / no side pots, so exact pre-hand BBA cannot be claimed until this cap issue is resolved.

### 3. Why the existing uniform-ante approximation is internally convenient

With `1/9bb` dead ante on every seat, every seat loses the same amount. The solver can keep one common live-stack cap and preserve symmetry while matching total dead money.

This does **not** make it exact BBA. In particular the BB's price / stack-behind / jam geometry differs from a true BB-only ante.

## Required work for an exact implementation

Before changing production results, preserve the now-confirmed T2 stack convention.

### A. T2 stack identity — confirmed from production runtime

Production `session.py` establishes this unambiguously.

At hand start:

```python
self._before = dict(h.stacks)
rnd = RU.Round(..., h.stacks, h.bb)
```

Then SB and BB are deducted from `rnd.stacks`. After the BB blind is deducted, the BBA is deducted **again from the BB's remaining stack** and put into separate dead money:

```python
pay = min(h.bb, rnd.stacks[bb_s])
rnd.stacks[bb_s] -= pay
rnd.contrib[bb_s] = pay

a = min(_ante, rnd.stacks[bb_s])
rnd.stacks[bb_s] -= a
ante_pot = a
```

T2 therefore treats hand-start stack as chips **before** blinds/BBA are posted. The 1bb BBA is real stack depletion borne only by BB, while it remains dead money for pot/contribution semantics.

This confirms that canonical `prehand_bb` must map to the pre-forced-bet stack, not a post-ante actionable stack.

### B. If it is pre-forced-bet stack, add per-seat live caps

A correct representation needs, at minimum:
- seat-specific dead ante, e.g. `dead_antes: Vec<f64>`
- seat-specific maximum live contribution or equivalent remaining-stack accounting
- all-in detection against the seat-specific cap
- SPR / effective-stack calculations against the seat-specific cap
- terminal payout / side-pot correctness when caps differ.

Because the BB is shorter by the BBA amount after posting, all-in branches can create unequal contributions. Side-pot handling must be proven correct or the supported tree must explicitly exclude branches where the difference matters.

### C. Backward compatibility

Existing saved games and pilots must keep scalar `ante` semantics. A safe schema would preserve `ante` and add an optional per-seat field, rejecting ambiguous simultaneous use unless explicitly defined.

### D. Validation gates

Do not promote exact-BBA results until tests cover:
- root pot = 2.5bb for 9-max 0.5/1 + 1bb BBA
- UTG/SB/BB call prices
- BB check/call/raise live amounts exclude the dead BBA
- 20/25/30/40bb jam caps use the intended pre-hand stack convention
- fold-out payouts conserve chips
- HU and multiway all-in terminals conserve chips
- old uniform-ante fixtures remain byte/behavior compatible when the new field is absent
- canonical DB provenance changes from near-target only after these gates pass.

## Recommendation

Do **not** throw away the current 30/25/40/20 work. Keep it labeled as near-T2 BBA reference data.

Do **not** relabel it exact.

The T2 `prehand_bb` convention is now confirmed. The next engineering step is therefore **not** another semantics probe; it is an exact-BBA solver prototype with per-seat forced dead money and per-seat live caps, plus chip-conservation/side-pot tests. Until that passes, the current worker output must remain near-T2 reference data.
