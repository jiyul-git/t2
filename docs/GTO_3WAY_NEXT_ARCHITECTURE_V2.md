# 3-way postflop: next-architecture design note (B3 follow-up)

Status: **design only**. No code was changed for this note, and no prototype is started. Any prototype below needs its own pre-registration first.

## 1. What is established

All numbers come from the reduced node-46 game (Kc7d4h; turns 2s/Qh/8c; rivers 3d/Js/6h; M2 menu; exact card removal) unless marked "full".

| item | result | where |
|---|---|---|
| Full node 46, one flop, monolithic storage (f32 regret + strategy sum) | **21.44 GB** | B1, `b1_build_node46_Kc7d4h.json` |
| Same, 3-active trunk only | 9.03 GB | B1 |
| HU frontiers, full | 18 flop / 2 646 turn / 301 056 river instances; 12.4 GB; largest flop frontier 0.91 GB | `b3a_build_frontiers_node46_Kc7d4h.json` |
| 3-player showdown / joint-mass evaluator | exact vs brute force (1.6e-13), O(52N): 0.82 ms/call standalone, 0.10 ms/call in-run (sparser reaches) | `b3a_evalcheck.json`, D |
| HU degeneration of the 3-way engine | PASS | B2-② |
| A: monolithic, alternating updates | 0.84 → 0.22 → 0.016% pot at 50 / 100 / 400; 2.2 s/iteration, 1 thread | B3a |
| A′: monolithic, simultaneous updates | 7.15 → 2.14 → 0.265% at 50 / 100 / 400; A vs A′ passes every B3a criterion | B3a |
| B: trunk + frontiers reset and re-solved (100 inner) every trunk iteration | **FAIL** (sealed): 3.93 → 4.23% from 50 to 100 | `b3a_verdict.json` |
| D: same trunk path, three evaluations | fresh re-solve 3.93 → 4.23 → 4.35%; reach-weighted historical frontier average 4.10 → 3.77 → 3.73% (nearly stalled); inner frontier residual 0.035% pot ≈ 1% | `b3a_D_analysis.json` |
| B3b: factorized trunk fed the monolithic frontier values | **bit-identical to A′ for 50 iterations**; a stale-by-one oracle diverges at iteration 2 | `b3b_verdict.json` |
| Speed of B/D | 33.5 s per trunk iteration on 3 threads (D; B: 74 s on 2 contended threads), 98.4% in the HU re-solves | D |

Consequences:
- The split wiring is correct. B3b shows it exactly.
- The failure is in the **learning dynamics**. The trunk learns against frontier values that are re-solved from scratch against each trunk snapshot, instead of values produced by frontier strategies that learn along with the trunk.
- The accuracy of the inner solve is not the cause (≈ 1%).
- Anything that keeps frontier state between trunk iterations therefore **changes the algorithm**. It is not a cache or a speed-up.
- In particular, "persistent frontier regrets with one inner iteration per trunk iteration" *is* monolithic simultaneous CFR (A′), by B3b.

## 2. Candidates

Speed figures are projections from measured reduced-game costs. River work scales with the river-runout ratio 2352/9 ≈ 261; flop and turn work scale less. A projection is not a measurement.

### 2.1 Persistent / warm-started HU frontiers
- **What.** Keep frontier regrets and strategy sums across trunk iterations. Run k inner iterations per trunk iteration, without resets.
- **Accuracy risk.**
  - k = 1: none. It is A′ (B3b).
  - k > 1: unknown. Frontier players take several steps per trunk step, which is a different game schedule with no guarantee in 3-player. Needs its own A/B against A and A′.
- **Memory.** No saving. Frontier state (12.4 GB) plus the trunk (9.03 GB) is the monolithic 21.44 GB.
- **Speed.** With k = 1 it costs the same as monolithic. With k > 1 it costs about k times the frontier share.
- **Fit with B3a/B3b.** Reproduces A′ at k = 1, so it adds nothing by itself.
- **Validation.** Bit identity with A′ at k = 1 (B3b harness). For k > 1, a pre-registered comparison with A at matched CPU time.

### 2.2 Joint learning of trunk and frontier regrets
- **What.** One CFR over trunk and frontiers together. This is the monolithic solver in another form.
- **Accuracy risk.** None. A and A′ are the reference.
- **Memory.** 21.44 GB unless combined with 2.3 or 2.6.
- **Speed.** A: about 575 s per iteration on 1 thread (projected), about 150 s on 4 threads, so about 4 h per 100 iterations.
- **Fit with B3a/B3b.** This is the reference behaviour.
- **Validation.** Not needed beyond B3a (A).

### 2.3 Monolithic-equivalent decomposition, out of core (recommended first)
- **What.** Keep the trunk (9.03 GB) in memory.
  - Frontier subtrees' regrets and strategy sums live on disk: one file per frontier and runout block.
  - Each traversal streams a frontier in, updates it with the same arithmetic as the monolithic walk, and writes it back.
- **Accuracy risk.** None by construction. It must be bit-identical to the in-memory monolithic run. Alternating updates (A's schedule) are possible: the walk order is unchanged, only where the state lives.
- **Memory.** Trunk 9.03 GB + largest frontier 0.91 GB + I/O buffers ≈ **10–11 GB**, under the 12 GB goal.
- **Speed.** Compute as in 2.2, plus I/O. Reading and writing 12.4 GB per player traversal is about 75 GB per alternating iteration. At about 2 GB/s that is about 35–40 s per iteration: a real but bounded overhead.
  - Traversing all three players per frontier load (three per-player walks while the block is resident) cuts I/O to about 25 GB per iteration.
  - That requires the walk order to change (frontier-major). It is still exact for simultaneous updates. For alternating updates it is exact only if per-player ordering is preserved inside the block, which must be verified.
- **Restart / checkpoint.** Natural: the on-disk state is the checkpoint, and trunk state plus the iteration counter is all that is needed besides it.
- **Fit with B3a/B3b.** B3b already proves that trunk plus exact frontier values reproduces A′. 2.3 supplies the exact frontier values by running the monolithic frontier walk itself.
- **Validation.**
  1. Reduced game: out-of-core vs in-memory A and A′, bit identity over 50 iterations (B3b-style differential, with the stale-oracle negative control).
  2. Kill/resume test mid-iteration.
  3. Full node 46: one measured iteration (time, RSS, I/O volume) before any long run.

### 2.4 Chance / runout batching
- **What.** Evaluate showdowns and joint-mass terms for several runouts or boards in one pass (SIMD now, GPU later).
  - The O(52N) aggregates are per board, but the insert loops vectorize.
  - Batching the 48 rivers of a turn shares the combo order work.
- **Accuracy risk.** None if results match the scalar evaluator bit for bit or within float-order tolerance (≤ 1e-12 relative).
- **Memory.** Small scratch.
- **Speed.** Showdown/den calls are about 87% of CPU in D (13 900 of about 16 000 CPU-s, 3 threads x 5 330 s). A 2–4× evaluator speed-up is a plausible 1.5–2.5× overall.
- **Fit with B3a/B3b.** Orthogonal. Combine with 2.3.
- **Validation.** evalcheck-style comparison against the scalar and brute-force evaluators, then B3b identity.

### 2.5 River-only / on-demand materialization
- **What.** Do not store river regrets. Re-solve river subgames on demand, or keep only river average strategies.
- **Accuracy risk.** **High.**
  - Re-solving a subgame from scratch against each trunk snapshot is the B/D dynamics that failed (the fresh re-solve got worse, the historical average stalled).
  - Keeping only averages drops the regret state CFR needs.
- **Memory.** Saves up to about 13 GB (the river part), which is the largest share.
- **Speed.** Re-solve cost as in B/D (98% of the time).
- **Fit with B3a/B3b.** Contradicted by D unless the re-solve is made safe *and* history-aware, which is a research problem, not an engineering step.
- **Validation.** Would need the full B3a/D protocol again. Not recommended now.

### 2.6 Sparse frontier / instance allocation
- **What.** Allocate state only for frontier or runout instances whose arriving mass is non-negligible, with dynamic promotion when reach grows. This is related to regret-based pruning.
  - In D, 95% of frontier mass sat in 61–66 of 1 332 frontiers.
  - Many river frontiers had mass below 1e-8.
- **Accuracy risk.** Moderate. Unallocated instances need a value.
  - A frozen or static proxy at negligible reach is harmless for values, but not for the strategy there.
  - Promotion rules add non-stationarity.
- **Memory.** Large potential saving, but it depends on the reach distribution. It must be measured on the full game, not assumed.
- **Speed.** Proportional to the allocated share.
- **Fit with B3a/B3b.** Compatible with 2.3. A later memory lever.
- **Validation.**
  1. Reduced game: sparse vs monolithic A under the B3a criteria.
  2. Sensitivity to the allocation threshold, fixed before results.
  3. Mass-coverage report per iteration.

### 2.7 MCCFR / trajectory sampling
- **What.** Sample chance (turn and river cards) or trajectories instead of full enumeration. Public-chance sampling keeps the vector evaluator per board.
- **Accuracy risk.** Moderate. Values are exact only in expectation, and there is sampling variance on the per-class tables. It needs a different stopping and CI protocol.
- **Memory.** No saving by itself: every infoset still gets regrets once touched.
- **Speed.** Per-iteration cost falls roughly by the enumeration factor (up to 49 × 48 at the river). The iteration count to a given exploitability rises.
- **Fit with B3a/B3b.** Orthogonal. Would be compared against A on the reduced game at matched CPU time.
- **Validation.** Pre-registered matched-CPU comparison with A; exploitability measured exactly with the full evaluator.

## 3. Assessment

| candidate | accuracy risk | memory (full node 46) | speed | recommendation |
|---|---|---|---|---|
| 2.3 out-of-core monolithic-equivalent | none (bit identity testable) | ≈ 10–11 GB | monolithic + I/O | **first prototype** |
| 2.4 batching | none (tolerance testable) | ≈ 0 | 1.5–2.5× | together with 2.3 |
| 2.6 sparse allocation | moderate | potentially large, unmeasured | proportional | later, after 2.3 |
| 2.7 MCCFR | moderate (variance) | none by itself | large per iteration | optional speed track |
| 2.1 warm start (k > 1) | unknown (new schedule) | none by itself | ≈ k × frontier | only as a pre-registered A/B |
| 2.2 joint in memory | none | 21.44 GB (> 15 GB) | reference | needs a bigger machine or f16 (both on hold) |
| 2.5 river on demand | high (D) | large | re-solve cost | not now |

## 4. Before any prototype

- **Pre-registration** of the prototype and its acceptance tests:
  - bit identity with A/A′ on the reduced game;
  - resume test;
  - one-iteration full-game measurement with memory and time limits (≤ 12 GB goal, < 15 GB hard);
  - the 100-iteration budget.
- **No production injection** of 3-way values. No node 228. No f16. No new alpha.
- Every speed or memory claim is to be measured on the full node 46 flop, not projected. This note's projections only rank the options.
