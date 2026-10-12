# P17 isolated final integration — release HOLD

Exact production base: `3c434b28046643ba54c04447951ad148ae6f9c1c`.
Selected PR29: `a2fdc02ab874371b04469ff36d917009542f0ab8`.
Selected PR30: `2c2acdcc10874c0c6efb205f6684423ac37b04e2`.
All original PRs are Draft and unmerged as directly verified on GitHub.
Both patches use PR27 as their common base. Their changed files are disjoint.
`selected_sources.json` records all 21 selected files and exact original blobs.

## Scope
Production changes: plan.py and ui/tools/{setup_run_dir.py,setup_run_dir.sh,predeploy_check.sh} only. Plan matches final P30 exactly. Packaging matches final P29 exactly. No additional strategy, coefficient, hand exception, or None-to-number substitution introduced by integration. bot.py, preflop.py, session.py, range_posterior_v1.py, icm.py, play.py, live2.py, fieldsim.py, field.py and tourney.py are byte-identical to PR27.
P5/P8/P15 standalone audits are imported unchanged from their independently approved commits. Original P9 audit blob is `1538f0c8ea79ebbfd605344f2b10305f2f754171`.

## Actual local checks
- 18 MC/calloff/HAND130/postflop test scripts: 18 success, 0 failed.
- 18 field/BF/provenance/epoch/concurrency test scripts: 18 success, 0 failed.
- Clean installation: 8 real starts, lobby and play HTTP200; 6 ZIP manifests, install62/update61, module bytes identical, original PYTHONPATH removed, update repair and full system rebuild preserve personal bytes.
- Wallet: original 23 tests, OK.
- Installed runtime: original P9 13 cases plus P10 unavailable/provenance scripts pass under isolated Python; source plan.py bytes preserved.
- PR27 vs integration frozen seeds 3000–3005, 30 hands each: actions and fingerprint equal 6/6; no new action difference.
- OFF/ON seed11/12 extended full JSON comparison is reported separately upon completion.

## Remaining actual failure
Unmodified tools/verify_replan_contract.py fails C4 on BOTH exact PR27 and integration. Actual missing kwargs are bb_chips and tilt; its KNOWN_MISSING still lists five older keys. This is an inherited stale expectation, not a new argument-routing change. The failing test has not been edited, skipped or deleted: its separate remote job executes it unchanged and must fail until a separately reviewed resolution. Therefore the full release gate remains HOLD even if all integration-specific jobs succeed.

## Historical frozen differences
All four stored baseline files are unchanged; their historical replay evidence is reused from recovered prior local files. baseline_comparison_matrix.json records exact generating SHAs and hashes, with original frozen replay matching stored 6/6 for each. This does not claim a new historical replay or prior remote publication.
Current versus PR27 already differs for all six seeds. Initial differences: 3000 hand1 preflop call200→fold; 3001 hand2 preflop raise700→600; 3002 hand1 flop bet900→800; 3003 hand1 flop bet1200→check; 3004 hand1 flop bet1100→1000; 3005 hand1 turn bet2000→check.
The same FIRST differences existed on historical test3 `2781cd547128a616424facedf60ef8654f99d775`; their full later fingerprints are not all identical to PR27. The trace matrix explicitly keeps that distinction.
Recovered parent/child attribution identifies earlier weak-first-in limp admission, planned sizing/limp backaction, call-range semantics and flop ownership transitions. The included transition records preserve parent/child SHAs and observed actions. They are local validated brackets, NOT proof of globally earliest transition or of strategic optimality. Integration adds no difference in these six seeds.

## Existing independent CI evidence verified via GitHub jobs
P5 38050738375: 3 success; P8 38050517498: 1 success; P15 38049825000: 1 job / nine gates success; P16 38051999777: 1 success; P10 38055643487: 3 success; P9 38056108477: 3 success.
Previous P17 remote audit branch still points to PR27. Prior local audit SHA and 155-file publication were NOT assumed present remotely. This branch republishes only selected nonpersonal trace metadata and new synthetic integration evidence.

Remote CI is required; its actual run and final HEAD will be reported in the Draft PR and final response. No merge, test3 modification or deployment is authorized here.
