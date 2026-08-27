"""보드 텍스처 분류와 텍스처별 전략 조정.
   분류 자체는 객관적이지만, 그걸 '인식하고 활용하는 정도'는 board_texture 개념에 비례한다."""
import bot

RV = bot.RV

def classify(board):
    """보드를 특징 벡터로 분해."""
    if len(board) < 3: return {}
    ranks = sorted((RV[c[0]] for c in board), reverse=True)
    suits = [c[1] for c in board]
    su = {}
    for s in suits: su[s] = su.get(s, 0) + 1
    maxsuit = max(su.values())
    uniq = sorted(set(ranks), reverse=True)
    paired = len(uniq) < len(ranks)
    trips = any(ranks.count(r) >= 3 for r in ranks)

    # 연결도
    span = 0
    for i in range(len(uniq)):
        win = [v for v in uniq if uniq[i] - 4 <= v <= uniq[i]]
        span = max(span, len(win))
    gaps = uniq[0] - uniq[-1] if len(uniq) > 1 else 0

    high = ranks[0]
    return {
        'high': high,
        'ace_high': high == 14,
        'broadway': sum(1 for r in ranks if r >= 10),
        'low': high <= 9,
        'paired': paired,
        'trips': trips,
        'monotone': maxsuit >= 3,
        'twotone': maxsuit == 2,
        'rainbow': maxsuit == 1,
        'connected': span >= 3,
        'semi_connected': span == 2 and gaps <= 5,
        'dry': (maxsuit == 1 and span <= 2 and not paired),
        'wet': (maxsuit >= 2 and span >= 2) or maxsuit >= 3,
        'span': span,
        'maxsuit': maxsuit,
    }


def label(board):
    c = classify(board)
    if not c: return '?'
    parts = []
    if c['trips']: parts.append('트립스보드')
    elif c['paired']: parts.append('페어보드')
    if c['ace_high']: parts.append('A하이')
    elif c['broadway'] >= 2: parts.append('브로드웨이')
    elif c['low']: parts.append('로우')
    if c['monotone']: parts.append('모노톤')
    elif c['twotone']: parts.append('투톤')
    else: parts.append('레인보우')
    if c['connected']: parts.append('연결')
    elif c['dry']: parts.append('마름')
    return ' '.join(parts)


# ---------- 텍스처별 기준 조정 (완벽한 플레이어 기준) ----------
def cbet_multiplier(board, ip=True):
    """이 보드에서 씨벳 빈도를 얼마나 조정할지. 1.0 = 기준."""
    c = classify(board)
    if not c: return 1.0
    m = 1.0
    if c['ace_high']:      m *= 1.35      # A하이는 레인지 우위 → 많이 침
    elif c['broadway'] >= 2: m *= 1.12
    elif c['low']:         m *= 0.80      # 로우 보드는 상대 레인지가 히트
    if c['paired']:        m *= 1.18      # 페어 보드는 아무도 못 맞음
    if c['trips']:         m *= 1.25
    if c['monotone']:      m *= 0.62      # 모노톤은 위험
    elif c['twotone']:     m *= 0.86
    if c['connected']:     m *= 0.72
    elif c['dry']:         m *= 1.20
    if not ip:             m *= 0.90
    return max(0.30, min(1.9, m))


def size_fraction(board, plan, street):
    """이 보드에서 적정 벳 사이즈(팟 대비)."""
    c = classify(board)
    if not c: return 0.55
    base = {'flop': 0.55, 'turn': 0.62, 'river': 0.68}.get(street, 0.55)
    if c['dry']:                base *= 0.55      # 마른 보드는 작게
    elif c['connected']:        base *= 1.18      # 연결 보드는 크게
    if c['monotone']:           base *= 1.10
    if c['paired'] and not c['connected']: base *= 0.72
    if c['ace_high'] and c['rainbow']:     base *= 0.65
    if plan in ('bluff_2street',):         base *= 0.92
    if plan in ('value_3street',) and c['wet']: base *= 1.15
    return max(0.22, min(1.35, base))


RANK_HELP = {14: 0.55, 13: 0.42, 12: 0.34, 11: 0.24, 10: 0.12,
             9: 0.00, 8: -0.06, 7: -0.12, 6: -0.18, 5: -0.22,
             4: -0.25, 3: -0.27, 2: -0.28}

def turn_card_effect(flop, turn_card, aggressor_range_high=True):
    """턴/리버 카드가 공격자 레인지를 도왔는가. -1(상대를 도움) ~ +1(나를 도움).
       브릭(아무도 안 도움)은 0 근처가 되어야 한다."""
    v = RV[turn_card[0]]
    fr = [RV[x[0]] for x in flop]
    e = RANK_HELP.get(v, 0.0)

    # 보드를 페어시키는 카드 = 아무 레인지도 크게 안 도움 → 중립~약간 유리
    if v in fr:
        e = 0.10 if v >= 10 else 0.04
        return max(-1.0, min(1.0, e if aggressor_range_high else -e))

    su = {}
    for x in flop: su[x[1]] = su.get(x[1], 0) + 1
    same = su.get(turn_card[1], 0)
    if same >= 2: e -= 0.40          # 플러시 완성/근접
    elif same == 1: e -= 0.05

    # 스트레이트 완성도: 플랍과 붙어서 4연결을 만드는가
    allr = sorted(set(fr + [v]))
    run = 0
    for i in range(len(allr)):
        w = [x for x in allr if allr[i] <= x <= allr[i]+4]
        run = max(run, len(w))
    base_run = 0
    fu = sorted(set(fr))
    for i in range(len(fu)):
        w = [x for x in fu if fu[i] <= x <= fu[i]+4]
        base_run = max(base_run, len(w))
    if run > base_run and run >= 3: e -= 0.22

    if not aggressor_range_high: e = -e
    return max(-1.0, min(1.0, e))


# ---------- 인식 능력 반영 ----------
def perceived(board, skill, rng, fn, *args, **kw):
    """텍스처 개념이 낮으면 조정을 거의 못 하고 1.0(무반응)에 가까워진다."""
    true_val = fn(board, *args, **kw)
    w = min(1.0, max(0.0, (skill - 1.0) / 7.0))      # skill 1 → 0, skill 8 → 1
    neutral = 1.0 if fn is cbet_multiplier else 0.55
    val = neutral + (true_val - neutral) * w
    # 미숙할수록 노이즈
    noise = 0.18 * (1 - w)
    return val * (1 + rng.uniform(-noise, noise))
