# 옛 브랜치 정리 보관 (2026-10-26, 반영된 것으로 확인된 12개)

이 커밋의 부모가 아래 브랜치들의 마지막 커밋이다. 브랜치를 지워도 내용은 이 브랜치에서 닿는다. 되살리기: `git fetch origin claude/archive-old-branches-20261026 && git branch <이름> <커밋>`

| 브랜치 | 마지막 커밋 | 반영 근거 |
|---|---|---|
| `chatgpt/mini-cfr-solver-20260928` | `434abfeba5c309e3cb29f5dafb982133dd79d6fb` | identical in census (735 of 750 files, 0 missing paths; rest = older vendored solver files) |
| `chatgpt/gto-30bb-uniform-pilot-20261003` | `ad0077f161dec8f8b750e9d02fb493f8d6f481c5` | 10289 of 10310 files identical in census; the rest are older vendored solver files and one 4 KB json |
| `test` | `54c7e8aebac0ac600331e08ced86d419692b9e87` | 555 of 590 files identical in master / test3, 0 paths missing (older versions only) |
| `chatgpt/p10-postflop-mc-none-consumer-20261010` | `2c2acdcc10874c0c6efb205f6684423ac37b04e2` | PR #30 (closed); code files identical in test3 / master, plan.py superseded by later versions; only CI workflow unique |
| `chatgpt/p11-replan-c4-20261011` | `b83db843514b37ff5680380f8e81f709ade3c46b` | PR #32 (closed); runner.py, verify scripts identical in test3 / master, plan.py superseded |
| `chatgpt/p9-pr30-final-independent-20261010` | `1aa0bd2a44973718fbd8e7ae696ab01d84c97da9` | audit of PR #30 (closed); tools identical in test3 / master, plan.py superseded; only its CI workflow unique |
| `chatgpt/p9-pr30-mc-independent-audit-20261010` | `5fc6ce2ec49454a2d4f20fc902c0f576f747843e` | audit of PR #30 (closed); tools identical in test3 / master, plan.py superseded; only its CI workflow unique |
| `chatgpt/p8-pr27-independent-epoch-range-audit-20261010` | `e90eede3ce3bb57e7fa271e2f42bfb0673d3e3af` | PR #28 (closed); verify script identical in test3 / master; only its CI workflow unique |
| `chatgpt/p13-pr24-partial-roster-lifecycle-20261010` | `e82f5e978fc4da5c229b01f0cf164a058b15562d` | closed PR chain; play.py identical, icm.py / verify superseded; no unique documents |
| `chatgpt/p13-pr18-preview-20261010` | `81051e5923cc8712e82e3ac35b55c298afbf2b39` | closed PR chain; verify scripts identical, context / fieldsim / icm / play / session superseded; review doc exists in later version |
| `chatgpt/hand130-range-conditional-v1-20261010` | `52b0cf680ac70fc2f5071428d733cd9ee7ba8737` | PR #15 (closed); verify script identical, bot / session / range_posterior superseded by later versions |
| `chatgpt/test3-local-browser-play-20261009` | `509a872048f5dc4919a02fad910c980a3a106283` | one commit: a CI workflow (local-play export), no code |
