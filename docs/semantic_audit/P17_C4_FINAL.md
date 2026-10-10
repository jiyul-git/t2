# P17 C4 final integration review

Base PR31: 3f30cc82540dc6d69fbf22295f49da20194626a4
Selected exact PR32: b83db843514b37ff5680380f8e81f709ade3c46b

Production only plan.py/runner.py, exact PR32 blobs. PR31 three installer/predeploy sources and all other root engines unchanged. Original P9 audit and frozen baselines preserved. PR31/PR32 branches preserved.

The original six P17 jobs and six P11 jobs run again on this isolated HEAD. The old P17 source guard expected old plan/runner blobs and is replaced by a strict exact PR32 + protected PR31 byte guard, not disabled. Original MC/field/install/parity/frozen tests remain unchanged. The repaired C1-C7 test is copied byte-for-byte from reviewed PR32. No success assertions removed.

Independent value-boundary test uses nonzero tilt and non-default BB, preserving global RNG. Independent A6 review requires849 events, tilt-only0 decision changes, BB-only1 size/0 plan/0 act,21 stackoff changes,event143 river bet0.656 to0.615 and final stacks/RNG/bust order unchanged. Historic810-event A6 is separate.

HOLD until exact remote HEAD completes both complete suites and independent result review. Final run URLs and GO/HOLD are recorded in the Draft PR. No merge/test3/deployment/default-flag changes.
