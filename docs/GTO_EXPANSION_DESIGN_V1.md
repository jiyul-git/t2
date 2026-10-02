# GTO expansion design v1 (after A4c)

Status: design only. No large solve is started by this document. Inputs: A4c sealed as research evidence
(`data/gto_terminal_expansion/a4c/SEALED.json`, report `docs/GTO_TERMINAL_A4C_REPORT_V2.md`), sk1 DB (`tools/gto_db_v2`).

What A4c established and what this design takes from it:
- panel error at 232/218 boards is now the same size as the outer-loop proxy (L_ext / proxy: BTN 0.89, SB 0.69, BB 0.99), so adding
  boards alone is no longer the default lever;
- EVs are usable at about 0.2 bb/100 per seat; class-level action frequencies at BB vs BTN, BB vs SB and SB first-in are not
  (about 11-12% of frequency mass moves between bootstrap replicates);
- part of the frequency movement is near-indifference (J2s SB first-in moved raise 0.39 / jam 0.61 -> 0.63 / 0.37 with a 5.7e-6 bb regret change).

## 1. DB frequency policy

### 1.1 Storage rules
- Action identities are never merged in stored data. Each hand record keeps every action of the solver's menu.
- Each (spot, hand) record stores raw `action_freq` and `action_ev` (bb, net of the hand's investment, conditional on reaching the node),
  plus the uncertainty and status fields below. EV is the primary trust quantity; frequency carries status and provenance.
- An unstable exact mix is stored as a provisional frequency, never as "the GTO frequency".
- Near-indifferent action groups exist only in the lookup / execution layer, computed from stored fields; the raw rows stay unmerged.

### 1.2 Uncertainty, measured not assumed
For hand h at a node, let the actions be sorted by EV and gap_h = EV(best) - EV(second).
- u_panel(h): bootstrap spread of gap_h over the panel replicates (each replicate's point solve exports `path_nodes[].ev_bb` and
  `class_strategy`, so this needs no new solve where a bootstrap exists).
- u_outer(h): |gap_h(step k) - gap_h(step k-1)| from the last outer step (section 2), at a fixed panel.
- u_solver: the node's own-strategy residual (stored own_gap / regret floor of the point solve), as a floor.
- u(h) = sqrt(u_panel^2 + u_outer^2) + u_solver.
- freq spread: q05-q95 interval of each action's frequency over the bootstrap replicates; policy-argmax agreement = share of
  replicates whose most-frequent action equals the point solution's.

### 1.3 Status (per spot, hand)
| status | rule | meaning for lookup |
|---|---|---|
| `stable` | gap_h > z * u(h) and policy-argmax agreement >= a | action identity reliable; frequency usable |
| `near_indifferent` | gap_h <= z * u(h) (top actions EV-indistinguishable) | group = actions with EV within z * u(h) of the best; mix stored as provisional with its interval |
| `unstable` | gap_h > z * u(h) but policy-argmax agreement < a, or frequency interval of the best action wider than its own gap is distinguishable | solver / panel does not reproduce the choice; frequency not usable; EV still reported with u(h) |
| `unassessed` | no bootstrap / no outer step available (legacy 616, Termux single solves, any single point solve) | raw data only; never promoted |

z and a are pre-registered design parameters (proposal: z = 2, a = 0.95), fixed before any data are classified; they are not frequency thresholds.

Equilibrium note: a genuinely mixed class is EV-indifferent among its mixed actions by construction, so `near_indifferent` is the normal label
for mixed hands. Its mix is pinned by the opponent's indifference, not by its own EV gap, so its precision is read from the replicate
frequency interval, which is stored alongside.

### 1.4 Schema change (gto_solution_v2, additive)
- new strategy format `hand_records_v1`: `{actions:[...], hands:{h:{freq:{a:p}, ev:{a:x}, gap, u:{panel,outer,solver,total}, freq_q05_q95:{a:[lo,hi]},
  argmax_agreement, status, near_indifferent_group:[a...]}}}`;
- solution-level `frequency_assessment`: method, replicate count, z, a, panel id, outer step id;
- existing formats (`legacy_view`, `termux_v1_policy`) are unchanged and read as status `unassessed`. Migration semantics do not change.

### 1.5 A4c
Sealed: BB vs BTN, BB vs SB and SB first-in are `frequency_unstable` at node level (SEALED.json); BTN first-in and SB vs BTN are
`unassessed_class_level`. A class-level assessment of the 5 A4c nodes can be computed from the 60 stored replicates without any solve
(proposed first small task, D1). A4c stays research evidence and is not exported as a production solution.

## 2. Outer-loop (self-consistency) policy

### 2.1 Loop
State k = (preflop strategy sigma_k, terminal ranges R_k, terminal value tables V_k), panel P fixed.
1. panel solve: postflop solves on P at ranges R_k (same boards every step: common random numbers, so the step change is not
   panel-resampling noise);
2. value update: V_{k+1} = panel estimate; preflop solve g(V_{k+1}) -> sigma_{k+1}, R_{k+1};
3. re-evaluate affected states: seat-swap dEV of sigma_k in G_{k+1} (per seat), class-regret excess at the formal nodes, strategy L1,
   per-hand gap change (feeds u_outer);
4. compare outer change Delta_k (per seat and node) with the panel uncertainty U of P (bootstrap loss L at that panel, measured once per
   panel; A4c's L_ext is the current U for nodes 6/28);
5. stop when Delta_k <= U for every seat and formal node. Also stop and report (no silent continuation) when Delta grows for two
   consecutive steps or a step budget is reached.
No fixed iteration count. Damping is allowed only as a pre-registered choice with its value recorded.

### 2.2 Wording
Delta_k is a consecutive-outer-state change, not the fixed-point residual. The empirical contraction ratio Delta_k / Delta_{k-1} is
reported; a residual estimate Delta_k * rho / (1 - rho) may be shown only as an estimate under a contraction assumption.
The A3 k13 -> k14 numbers stay labelled "frozen-range / outer-step proxy".

### 2.3 Panel-only work
Adding boards without an outer step is not the default; it is used only when Delta_k <= U is already met and U is the binding term.

## 3. Expansion stages (each stage pre-registered before its solves)

| stage | what | cost estimate | output |
|---|---|---|---|
| D1 | A4c class-level frequency assessment from stored replicates; hand_records_v1 schema + lookup-layer groups (no solve) | minutes | status per class at 5 nodes; schema tests |
| E1 | outer-loop pilot on nodes 6 + 28 at the 232 / 218 panel, starting from the A4c Gext state | per step 450 postflop solves, about 68 CPU-h (about 17 h wall on 4 workers) + 1 preflop solve; expected 1-3 steps | Delta_k vs U, stop decision, u_outer per hand |
| E2 | add node 228 (CO open, BB call; 14.5% of flop-reaching reach): 144-board panel + bootstrap U first, then joint outer loop with 6 / 28 | 144 solves (about 22 CPU-h) + 60 bootstrap replicate solves; each joint outer step about 90 CPU-h | 3 HU SRP terminals self-consistent |
| E3 | 3-way SRP terminals (41.6% of flop-reaching reach) in the 3-way research game | design separately (B-series prototype) | research only; never labelled GTO |
| E4 | postflop strategy export (flop -> turn -> river) for the DB | prerequisite measurement below | postflop spots in the DB |

Remaining HU 3-bet terminals (node 1371: 1.0%, all other 3-bet / 4-bet HU < 0.02% each) stay on the legacy payoff until E1-E2 are done;
their order is by reach x value sensitivity, not reach alone. Other stack depths (20 / 25 / 40bb) follow the same stages after 30bb.

### 3.1 E4 prerequisites (flop -> turn -> river)
- Each flop solve already solves the full flop-turn-river tree of the `m2_single_v1` menu, but the artifact stores only root class values
  (`gross_eps`), not strategies. A strategy export is new solver-side code; first measure the exported size of one board (all streets,
  1326 combos or 169 classes x node count) before choosing storage.
- Postflop spot key (sk2): preflop line + canonical board (suit isomorphism) + postflop action history + hero. The ranges are not part
  of the key: they come from the preflop solution, so every postflop solution links to its parent preflop solution_id. When the outer loop
  changes the ranges, the new postflop solutions are appended and supersede through the quality rules; nothing is deleted.
- Coverage: the panel covers 232 / 218 of 1,755 canonical flops; a lookup for an unsolved flop needs either full coverage (about 0.15 CPU-h
  per flop, about 263 CPU-h per terminal per outer state) or a declared nearest-panel fallback with status `unassessed`. Decision deferred
  to E4's design review.

## 4. Decisions requested
1. z and a for the frequency status (proposal z = 2, a = 0.95).
2. E1 step budget (proposal: at most 3 steps, then report) and whether damping is used.
3. Order after E1: E2 (node 228) before E4 (postflop export), or measure E4's export size in parallel (small, no large solve).

## 5. Decisions fixed (2026-10-03)
- Frequency status: Z = 2, A = 0.95 (60 bootstrap replicates: modal action in >= 57 / 60). Statuses stable / near_indifferent /
  unstable / unassessed. Each hand also stores bootstrap frequency q05/q50/q95, modal-action consistency and L1 dispersion.
  near_indifferent is not frequency precision; no frequency-precision hard threshold is defined yet. Implemented in
  `tools/gto_db_v2/hand_records.py` (format `hand_records_v1`, tests `test_hand_records.py`).
- E1: at most 3 outer steps; damping alpha = 0.5 for the update x_{k+1} = x_k + 0.5 (F(x_k) - x_k). Convergence is judged on the
  undamped raw residual F(x_k) - x_k, never on the damped step: early stop when raw residual <= panel uncertainty U for every
  formal seat / node; stop and report if the raw residual grows two steps in a row; after 3 steps without meeting the rule, report
  "not yet converged" and stop (no automatic 4th / 5th step).
- Order: D1 and the E4 single-board export-size measurement now (no large solve); then E1; E2 (node 228) only after E1's result; the
  E4 turn / river exporter after the size measurement is reviewed.
- sk2: ranges are not part of the key, but every postflop solution stores `parent_preflop_solution_id` and `input_range_hashes`;
  lookup selects only solutions whose parent matches the requesting preflop solution; solutions with different parent ranges are
  never mixed because they share a spot.
