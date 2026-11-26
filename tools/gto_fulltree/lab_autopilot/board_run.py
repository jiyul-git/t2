#!/usr/bin/env python3
"""보드 실행 래퍼: 현재 폴더(보드 브랜치 작업 폴더)의 ft_board.py 를 그대로 쓰되, CFR+ 재시도 프로세스 수를 제한한다.

ft_board.py 는 한 덩어리(12보드) 중 못 맞춘 보드마다 t2_cont_panel 을 동시에 띄운다(최대 12개). 연구실은 코어 6개만 쓰기로 했으므로
동시에 LAB_RETRY_LIMIT(기본 워커 수)개까지만 띄우게 retry() 를 감싼다. 결과·푸시·묶음 규칙은 ft_board.py 와 같다(수정 없음).
  python3 board_run.py <묶음id> [<묶음id> ...]      # cwd = 보드 브랜치 작업 폴더
"""
import importlib.util
import os
import sys
import time

limit = int(os.environ.get('LAB_RETRY_LIMIT', os.environ.get('SPOT_PANEL_WORKERS', '3')))
path = os.path.join(os.getcwd(), 'tools/gto_fulltree/ft_board.py')
spec = importlib.util.spec_from_file_location('ft_board', path)
fb = importlib.util.module_from_spec(spec)
sys.modules['ft_board'] = fb
bundles = sys.argv[1:]
sys.argv = [path] + bundles
spec.loader.exec_module(fb)

if hasattr(fb, 'retry'):
    orig = fb.retry
    started = []

    def throttled(*a, **k):
        while sum(1 for p in started if p.poll() is None) >= limit:
            time.sleep(2)
        p = orig(*a, **k)
        started.append(p)
        return p
    fb.retry = throttled

fb.main()
