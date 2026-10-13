# p60_btn_vs_bb_b40 — stopped (user decision 2026-10-14: all b40 spots move to the v2b parent)

- Reason: the b40 parent (gap 0.043) blocks G6(a), so b40 spot records cannot reach conditional_verified.
  Kept as parent-sensitivity comparison data only.
- Rule: v3 for step 0, switched to v4 (+ standard amendment 8, 4c1db4e) before any step-1 verdict; state k=1.
- step0: complete (2 terminals x 24 flops), report.json decision "continue (minimum one update)" -> step0.tgz
- step1: term0 24/24 flops done, term1 11/24 flops done, no verdict -> step1_partial.tgz (includes state.json)
- v3_pre_switch.tgz: state.json and step-1 terminal files saved before the v4 switch (cmp-identical to the v4 regeneration)
- Env: Python 3.11.17, numpy 2.4.6, SPOT_PANEL_WORKERS=2 (2-CPU / 8 GB container; workers do not affect values);
  step-0 reproduction matched (term0 addd06e9..., flop AcKc6c a035dc0c...) before the run and after the v4 merge.
- Resume (if ever needed): restore step0/step1/state.json under /home/user/gto_ckpt/spots/p60_btn_vs_bb_b40/ and re-run
  run_plan_a.sh with PLAN_A_IDS=p60_btn_vs_bb_b40; solved flops are reused.
