# 연구실 봇 상태: **warn** — 2026-11-28T01:01:20Z (live)

- 호스트 DESKTOP-FUUG7O5, 가동 6.6시간, 코드 0abdd43f33, CPU 0/6 코어, 메모리 여유 None GB, 디스크 여유 83.6 GB
- 지금 하는 일: 없음 (대기)
- **30bb** 단계 2: boards — 보드 번호 4/20 끝
- **40bb** 단계 6: boards — 보드 번호 0/20 끝
- **60bb** 단계 4: collect — 묶음 전부 끝 → collect
- **100bb** 단계 2: solve — 단계 2 표는 있음, 트리 풀이 없음

## 경고 (status != ok)
- [warn] paused ctl: 원격 명령으로 일시정지 중 (전체) (x1, 처음 2026-11-28T01:01:20Z)

## 원격 명령 처리
- c2 cancel: OK cancel 40|*|board_3 (실행 중 1개 취소)
- c3 cancel: OK cancel 40|*|board_4 (실행 중 1개 취소)
- c4 config: OK loop.coord_idle_hours = 0.25
- c5 stack: OK 스택 60 설정 {'enabled': False}
- c6 pause: OK 새 일 시작 안 함(진행 중인 일은 계속)
