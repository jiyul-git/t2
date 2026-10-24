# 정리된 GTO 계산 브랜치 보관 (2026-10-24)

이 커밋의 부모가 아래 브랜치들의 마지막 커밋이다. 브랜치는 지웠지만 내용(단계별 백업 tar, state.json, quick 기록, 덤프 조각, 문서)은 모두 이 브랜치에서 닿는다.
정밀 검사(P144 등)나 재계산 때 되살리기: `git fetch origin claude/archive-gto-runs-20261024 && git branch <이름> <커밋>` (아래 표의 커밋).
quick 기록 자체는 test3 의 data/gto_records/ 에 사본이 있다(출처표 MANIFEST.tsv).

| 브랜치 | 마지막 커밋 | 마지막 커밋 시각 | 마지막 커밋 메시지 |
|---|---|---|---|
| `claude/p30_3bet_20261022` | `f3f3ba4ada956cc0862a4cfa3581c29b0a8ac758` | 2026-10-22 15:50:19 +0000 | p30v1_utg1_vs_sb_3b40 and p30v1_utg_vs_btn quick records (step cap, mean of steps 1-2) |
| `claude/p40_3bet_20261021` | `7f084884b57551849fb8516cb0e48b487517e484` | 2026-10-22 11:15:01 +0000 | backup p40 3-bet spots: pre-relaunch |
| `claude/p40_3bet_resume_20261023` | `5d7dbfe6c1926960c0b68a02986fcf87557d4acf` | 2026-10-23 06:10:32 +0000 | p40v1_utg_vs_btn quick record: 3-step cap, mean of steps 1-2 |
| `claude/p30_flat_tail_20261021` | `6fbc628124afb8a09a8aeb907377f73d8d05b934` | 2026-10-22 10:55:45 +0000 | p30_flat_tail p30_flat_utg1_vs_bb: backup step1_partial |
| `claude/p30_flat_resume_20261023` | `90fee0bf151bd6d0efb787f191a8628bad44c6f7` | 2026-10-23 15:49:58 +0000 | p30_flat_utg2_vs_bb quick record: step cap (3 steps), mean of steps 1-2 |
| `claude/p40_flat_tail_20261021` | `38ff3585a596dc0cd3c26ea98c6e658e0b6f47b5` | 2026-10-23 07:26:42 +0000 | p40_flat_utg1_vs_bb quick record |
| `claude/p30_sblimp_cfrplus_20261023` | `f59046f6a84150563be3d7eadc059ac74216fd41` | 2026-10-23 10:47:00 +0000 | p30_flat_sb_limp_vs_bb quick record (CFR+ retry): 3-step cap, mean of steps 1-2 |
| `claude/p40_sblimp_cfrplus_20261023` | `83635b02005728e421fa4cf43fa7828836f81684` | 2026-10-23 14:21:01 +0000 | status_note: add step-cap statement |
| `claude/sb_limp_flop_diag_20261022` | `a91e3313cace4a678e58026ec26f5c109eb07478` | 2026-10-22 15:08:53 +0000 | SB-limp flop non-convergence diagnosis report |
| `claude/p60v2b_btn_vs_bb_3b40-resume-20261016` | `5b7c7c58da11cf45a48c52c3566f97757d7206fb` | 2026-10-21 19:12:39 +0000 | backup p60v2b_btn_vs_bb_3b40: 144-board continuation progress |
| `claude/p60v2b_co_vs_sb_3b40-resume-20261016` | `a24cf0f2fbd241772729d6f4ae76c56f4302905f` | 2026-10-21 14:19:13 +0000 | backup p60v2b_co_vs_sb_3b40: final-ish backup: p144 loop step 1, 142 flops (before possible stop) |
| `claude/p60v2b_utg1_vs_sb_3b40-20261016` | `1a7579241e6cff46826dd8e3b2fe6a0434367867` | 2026-10-21 14:22:07 +0000 | plan A backup: p60v2b_utg1_vs_sb_3b40 P144 (inconsistent) + p144s0, records, spots.log |
| `claude/p60v2b_btn_vs_bb_3b40-20261013` | `a6c07c08cd32acf7ec37061ebba2fc35303fe4dd` | 2026-10-19 02:37:07 +0000 | p60v2b_btn_vs_bb_3b40: 24-board record (step 3, provisional; regraded on 9abf2bd: G6(a) fail 0.01293 bb, G6(b) |
| `claude/p60v2b_btn_vs_bb_3b35-20261019` | `ac6fc42d04e6a0db8ff38391c3fc02ef5b68ce8e` | 2026-10-19 03:37:19 +0000 | Withdraw claim p60v2b_btn_vs_bb_3b35 (60 bb starts nothing new, user decision 2026-10-19) |
| `claude/p60v2b_co_vs_sb_3b35-20261019` | `4f515631c2171a38b7f29fd21d0c9240219671ed` | 2026-10-19 03:37:22 +0000 | Withdraw claim p60v2b_co_vs_sb_3b35 (60 bb starts nothing new, user decision 2026-10-19) |
| `ccr-9a10123b-0lyye0` | `c2f62e2842fc441b498d9519b7400e6fb6a69b80` | 2026-10-14 16:38:25 +0000 | Plan A v2b backup: p60v2b_utg_vs_btn step 7 |
| `chatgpt/plan-a-btn-bb-20261013` | `fa7e775004b0a067932c3b62acc15bbc906f931e` | 2026-10-13 19:25:39 +0900 | Record BTN BB six validated flops and worker restart |
