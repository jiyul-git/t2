#!/usr/bin/env python3
"""169 클래스로 합치면 잃는 것: 같은 클래스 안 콤보(무늬)끼리 전략 차이를 1326 파일에서 잰다 (읽기 전용).
  python3 tools/gto_fulltree/strategy_percard_withinclass.py <run_dir> <board> [river_every=10]
도달 가중, 클래스 평균과 콤보 빈도의 절대 차이(%p, 행동 중 최대)의 평균·최대. 턴 기록 전부, 리버 기록은 N개마다 하나."""
import json
import os
import struct
import sys

import numpy as np

d, board = sys.argv[1], sys.argv[2]
every = int(sys.argv[3]) if len(sys.argv) > 3 else 10
meta = json.load(open(os.path.join(d, 'R1_percard', board + '.pc.meta.json')))
b = open(os.path.join(d, 'R1_percard', board + '.pc1326.bin'), 'rb').read()
lines = {l['id']: l for l in meta['lines']}
H = meta['hands_by_player_0_oop_1_ip']
mask = [np.array([(1 << c1) | (1 << c2) for c1, c2, _ in H[p]], dtype=np.uint64) for p in (0, 1)]
cl = [np.array([c for _, _, c in H[p]]) for p in (0, 1)]
pos, n = 0, 0
acc = {1: [0.0, 0.0, 0.0], 2: [0.0, 0.0, 0.0]}   # street -> [sum w*dev, sum w, max dev(reach>=0.1)]
while pos < len(b):
    lid, t, r = struct.unpack_from('<IBB', b, pos)
    pos += 6
    L = lines[lid]
    na, p = len(L['actions']), L['player']
    dealt = np.uint64(0)
    for c in (t, r):
        if c != 255:
            dealt |= np.uint64(1) << np.uint64(c)
    keep = (mask[p] & dealt) == 0
    nhu = int(keep.sum())
    reach = np.frombuffer(b, '<f4', nhu, pos)
    pos += nhu * 4
    fr = np.frombuffer(b, '<u2', na * nhu, pos).reshape(na, nhu)
    pos += na * nhu * 2
    n += 1
    st = L['street']
    if st == 0 or (st == 2 and n % every):
        continue
    c = cl[p][keep]
    w = reach.astype(np.float64)
    f = fr.astype(np.float64) / 10.0
    cw = np.bincount(c, w, 169)
    dev = np.zeros(nhu)
    for a in range(na):
        avg = np.bincount(c, w * f[a], 169) / np.where(cw > 0, cw, 1)
        dev = np.maximum(dev, np.abs(f[a] - avg[c]))
    acc[st][0] += float((w * dev).sum())
    acc[st][1] += float(w.sum())
    big = w >= 0.1
    if big.any():
        acc[st][2] = max(acc[st][2], float(dev[big].max()))
for st, (s, w, mx) in acc.items():
    print(json.dumps({'board': board, 'street': st, 'mean_dev_pp': s / w, 'max_dev_pp_reach_ge_0.1': mx}))
