"""턴·리버 카드 고르기. balanced: 숫자는 13개에 고르게, 무늬는 4개에 고르게(보드 카드 제외, 턴·리버 겹침 없음). random: 무작위.
사용: runouts.py <board> <n_turns> <n_rivers> <balanced|random> [seed]  → 출력: 'TURNS RIVERS' (쉼표 목록 두 개)"""
import sys, random
R = '23456789TJQKA'; S = 'cdhs'
board, nt, nr, mode = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
seed = int(sys.argv[5]) if len(sys.argv) > 5 else 0
used = {board[i:i + 2] for i in range(0, len(board), 2)}
def pick(n, used, offset):
    # 숫자를 13칸에 고르게 펼치고(offset 으로 턴·리버가 다른 숫자에서 시작), 무늬는 돌아가며
    out = []; k = 0; si = offset % 4
    ranks = [R[int(round((i + offset * 0.5) * 13 / n)) % 13] for i in range(n)]
    for r in ranks:
        for t in range(4):
            c = r + S[(si + t) % 4]
            if c not in used and c not in out:
                out.append(c); si = (si + t + 1) % 4; break
    return out
if mode == 'balanced':
    T = pick(nt, used, 0); Rv = pick(nr, used | set(T), 1)
else:
    rng = random.Random(seed); deck = [r + s for r in R for s in S if r + s not in used]
    rng.shuffle(deck); T = deck[:nt]; Rv = deck[nt:nt + nr]
print(','.join(T), ','.join(Rv))
