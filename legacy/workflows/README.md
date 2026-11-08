# 보관한 GitHub Actions 설정 (2026-11-08)

`.github/workflows/` 에 있던 설정 45개 중 40개를 옮겼다. 모두 **이미 없어진 브랜치**(옛 `chatgpt/*`, `claude/a5-*`,
`integration/*`, `test`)에 push 될 때만 돌게 되어 있어서 다시는 자동으로 돌지 않는 것들이다(2026-11-08 `git ls-remote` 로 확인).
삭제하지 않았다. 다시 쓰려면 `.github/workflows/` 로 되돌리고 트리거 브랜치를 지금 브랜치로 고친다.

남긴 5개: `android-apk.yml`(앱 빌드), `lounge-scene.yml`(라운지 그림 검사), `hand130-part2-audit.yml`·`p17-test3-integration.yml`·
`timing-familiarity-test3.yml`(test3 push 때 도는 검사).

쓸 만한 검사가 섞여 있다(예: `scheduled-tournaments.yml`, `test-ui-smoke.yml` — 옛 `test` 브랜치용). 지금은 같은 검사를
`tools/t2_handoff/ui_checks.sh` 로 직접 돌린다.
