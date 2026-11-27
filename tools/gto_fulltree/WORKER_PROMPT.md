# 보드 세션 지시문(최소 토큰). <N>, <묶음들> 만 바꿔 create_session 의 prompt 로 쓴다. 모델은 가벼운 것(Haiku).

계산 실행만 하는 세션입니다. 아래 명령 하나만 반복합니다. 로그 읽기·분석·설명·다른 명령은 하지 않습니다.

명령(저장소 t2 에서, Bash 도구 run_in_background=true, timeout=7100000):
git fetch -q origin claude/ft60_3way_s5 && git show FETCH_HEAD:tools/gto_fulltree/ft_worker.sh > /tmp/ftw.sh && bash /tmp/ftw.sh <N> <묶음들>

알림이 올 때마다(시간 제한·컨테이너 재시작 포함) 출력 마지막 줄만 봅니다.
- WORKER_ALL_DONE → "끝" 한 단어로 답하고 멈춤.
- WORKER_FAIL … → 그 줄만 그대로 답하고 멈춤.
- 그 밖(WORKER_RUNNING, 출력 없음, killed) → 같은 명령을 그대로 다시 실행하고, 답은 쓰지 않음.
