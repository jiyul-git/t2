# 연구실 봇 상태: **warn** — 2026-11-26T08:02:36Z (live)

- 호스트 DESKTOP-FUUG7O5, 가동 1.1시간, 코드 9559eee644, CPU 6/6 코어, 메모리 여유 None GB, 디스크 여유 88.0 GB
- 지금 하는 일: ft40 단계5 board_3(0/4 묶음), ft40 단계5 board_4(3/4 묶음)
- **30bb** 단계 2: solve — 단계 2 표는 있음, 트리 풀이 없음
- **40bb** 단계 5: boards — 보드 번호 16/20 끝
- **60bb** 단계 4: collect — 묶음 전부 끝 → collect
- **100bb** 단계 2: solve — 단계 2 표는 있음, 트리 풀이 없음

## 경고 (status != ok)
- [warn] process_dead 40|5|board_3: 종료코드 -15, 마지막 줄: {"bundle": "s5_t01_A", "boards_done": 12, "retried": 0, "min": 40.3} (x1, 처음 2026-11-26T08:02:36Z)
- [warn] process_dead 40|5|board_4: 종료코드 -15, 마지막 줄: {"bundle": "s5_t31_B", "boards_done": 12, "retried": 0, "min": 26.6} (x1, 처음 2026-11-26T08:02:36Z)

## 원격 명령 처리
- c1 stack: OK 스택 40 설정 {'enabled': False}
- c2 cancel: OK cancel 40|*|board_3 (실행 중 1개 취소)
- c3 cancel: OK cancel 40|*|board_4 (실행 중 1개 취소)
- c4 config: OK loop.coord_idle_hours = 0.25
