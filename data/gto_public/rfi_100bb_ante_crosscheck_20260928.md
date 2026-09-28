# 100bb 8-max RFI ante cross-check

- MTT-ante public source vs 100bb no-rake/no-ante GTO Wizard extraction.
- Non-SB positions only; SB is excluded because its strategy contains substantial limping.
- Mean MTT-ante / no-ante RFI ratio: **1.3121x**.
- Equivalent no-ante / ante ratio: **0.7623**.
- Current T2 uses `ANTE_MULT={True:1.00, False:0.90}`, only **1.111x** separation.
- This is a **provisional 100bb anchor**, not a production constant yet.
- Combined with the multi-stack MTT audit, evidence points first to recalibrating ante/depth coefficients, then re-auditing the hard cutoff and `pf_rank`.
