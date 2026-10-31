"""Hand category of a hole-card pair on a board: a line-by-line port of the vendored GTOpen solver's
crates/solver/src/report.rs classify() (which mirrors web/js/classify.js), so T2 decisions and the GTO strategy report
are bucketed by exactly the same rules. Cards are strings like 'Ah'."""
MADE = ["sf", "quads", "boat", "flush", "straight", "set", "trips", "two_pair", "overpair",
        "top_pair", "underpair", "second_pair", "third_pair", "weak_pair", "ace_high", "king_high", "no_made"]
DRAW = ["combo", "nut_fd", "fd", "oesd", "gutshot", "bdfd2", "bdfd1", "no_draw"]
R = '23456789TJQKA'
S = 'cdhs'


def _rs(c):
    return R.index(c[0]), S.index(c[1])


def has_straight(m):
    m = (m << 1) | ((m >> 12) & 1)
    run = 0
    for i in range(14):
        if m & (1 << i):
            run += 1
            if run >= 5:
                return True
        else:
            run = 0
    return False


def classify(board, c1, c2):
    b = [_rs(c) for c in board]
    h = [_rs(c1), _rs(c2)]
    hr = [h[0][0], h[1][0]]
    hs = [h[0][1], h[1][1]]
    pocket = hr[0] == hr[1]
    allc = b + h
    cnt_all, cnt_board = [0] * 13, [0] * 13
    mask_all = mask_board = 0
    for r, _ in b:
        cnt_board[r] += 1
        mask_board |= 1 << r
    for r, _ in allc:
        cnt_all[r] += 1
        mask_all |= 1 << r
    suit_all = [0] * 4
    for _, s in allc:
        suit_all[s] += 1
    board_top = max(r for r, _ in b)
    board_ranks = sorted({r for r, _ in b}, reverse=True)
    made = None
    flush_suit = -1
    for s in range(4):
        if suit_all[s] >= 5:
            flush_suit = s
    if flush_suit >= 0:
        sfm = 0
        for r, s in allc:
            if s == flush_suit:
                sfm |= 1 << r
        if has_straight(sfm):
            made = 'sf'
    quad = any(n == 4 for n in cnt_all)
    trip_ranks = [r for r in range(12, -1, -1) if cnt_all[r] == 3]
    pair_ranks = [r for r in range(12, -1, -1) if cnt_all[r] == 2]
    if made is None and quad:
        made = 'quads'
    if made is None and trip_ranks and (len(trip_ranks) > 1 or pair_ranks):
        made = 'boat'
    if made is None and flush_suit >= 0:
        made = 'flush'
    if made is None and has_straight(mask_all):
        made = 'straight'
    if made is None and trip_ranks:
        r = trip_ranks[0]
        if cnt_board[r] < 3:
            made = 'set' if (pocket and hr[0] == r) else 'trips'
    if made is None:
        hole_pairs = [r for r in pair_ranks if (hr[0] == r or hr[1] == r) and cnt_board[r] < 2]
        if len(hole_pairs) >= 2:
            made = 'two_pair'
        elif len(hole_pairs) == 1 or (pocket and cnt_board[hr[0]] == 0):
            if pocket:
                made = 'overpair' if hr[0] > board_top else 'underpair'
            else:
                r = hole_pairs[0]
                pos = board_ranks.index(r) if r in board_ranks else None
                made = {0: 'top_pair', 1: 'second_pair', 2: 'third_pair'}.get(pos, 'weak_pair')
    if made is None:
        hi = max(hr)
        made = 'ace_high' if hi == 12 else ('king_high' if hi == 11 else 'no_made')
    draw = 'no_draw'
    if len(board) < 5:
        strong = made in ('sf', 'quads', 'boat', 'flush', 'straight')
        fd_suit = -1
        for s in range(4):
            hole_of = (hs[0] == s) + (hs[1] == s)
            if suit_all[s] == 4 and hole_of >= 1:
                fd_suit = s
        outs = 0
        if not strong and made != 'straight':
            for r in range(13):
                if has_straight(mask_all | (1 << r)) and not has_straight(mask_board | (1 << r)):
                    outs += 1
        nut_fd = False
        if fd_suit >= 0:
            for r in range(12, -1, -1):
                if any(s == fd_suit and rr == r for rr, s in b):
                    continue
                nut_fd = (hs[0] == fd_suit and hr[0] == r) or (hs[1] == fd_suit and hr[1] == r)
                break
        if strong:
            draw = 'no_draw'
        elif fd_suit >= 0 and outs >= 1:
            draw = 'combo'
        elif nut_fd:
            draw = 'nut_fd'
        elif fd_suit >= 0:
            draw = 'fd'
        elif outs >= 2:
            draw = 'oesd'
        elif outs == 1:
            draw = 'gutshot'
        elif len(board) == 3:
            for s in range(4):
                hole_of = (hs[0] == s) + (hs[1] == s)
                if suit_all[s] == 3 and hole_of == 2:
                    draw = 'bdfd2'
                    break
                if suit_all[s] == 3 and hole_of == 1:
                    draw = 'bdfd1'
    return made, draw


STRONG = {'sf', 'quads', 'boat', 'flush', 'straight', 'set', 'trips', 'two_pair', 'overpair', 'top_pair'}
PAIR = {'underpair', 'second_pair', 'third_pair', 'weak_pair'}
DRAWS = {'combo', 'nut_fd', 'fd', 'oesd'}


def group(made, draw):
    """report groups: top pair or better / middle-weak pair / strong draw (no pair; flush draw, open-ended, combo) /
    gutshot (no pair) / air (no pair, no draw beyond backdoors)"""
    if made in STRONG:
        return 'tp_plus'
    if made in PAIR:
        return 'mid_pair'
    if draw in DRAWS:
        return 'draw'
    if draw == 'gutshot':
        return 'gutshot'
    return 'air'


GROUPS = ['tp_plus', 'mid_pair', 'draw', 'gutshot', 'air']
