# 맨 위 폴더에서 옮긴 파일 (2026-11-07)

실행(게임 서버·엔진)·검사(regress, ui_checks, GitHub Actions)·도구 어디에서도 쓰지 않는 파일을
맨 위 폴더에서 이리로 옮겼다. 지우지 않았다. 다시 쓰려면 맨 위로 되돌리면 된다.

- 코드: auto.py, game.py(옛 텍스트 자동 진행 — acts.json/auto_acts.json 사용), cli.py(옛 터미널 플레이),
  river_probe.py(+ river_probe.jsonl), tools_*.py 8개(일회성 분석).
- 결과물: *_after*.json, baseline_*.json, *.png 등 예전 비교 실험 결과.

확인 방법: 각 파일 이름이 저장소의 다른 파일(코드·워크플로·문서)에 나오지 않음,
또는 서로만 참조함(game.py ↔ auto.py ↔ acts.json). docs/semantic_audit 의 목록 문서는 기록이라 제외.
