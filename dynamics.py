"""틸트 상태. 핸드를 가로지르는 유일한 상태다.

예전 dynamics.py 는 네 가지를 담당했고 **전부 호출되지 않았다.**
  - 틸트           -> 여기 남긴다
  - 히어로 이미지  -> reads.Book 과 중복. 대장 6 으로 흡수
  - 히어로 적응    -> 같음
  - 테이블 브레이크 -> tables.reconcile 과 중복. 삭제
구 파일은 legacy_dynamics.py 에 남겨둔다.

파일(JSON)에 저장하지 않는다. 컨테이너가 세션마다 초기화되고
틸트는 한 대회 안에서만 의미가 있다.

---

**틸트를 어떻게 모델링하는가**

성향값을 밀어넣지 않는다(예전에는 aggr+3t, bluff+4t, gamble+3t 였다).
틸트는 개념을 **잊는 것이 아니라 안 쓰는 것**이므로 개념 가중치를 깎는다
(`persona.tilt_decay`). 그러면 레인지가 흐트러지고, ICM 을 무시하고,
포지션 구분이 사라지는 것이 따로 코딩하지 않아도 나온다.
계산이 필요한 개념부터 무너지고 몸에 밴 것은 남는다.

크기와 방향을 나눈다.
  크기 <- 손실 규모 x tilt_prone
  방향 <- aggression x tilt_swing  (`persona.tilt_direction`)
방향을 성향 하나로 정하면 '공격적인 사람은 난폭해진다'만 나오고
'얻어맞고 위축되는 사람'이 표현되지 않는다.

반복은 tilt_stack 이 정한다. 누적되는 사람과 감쇠하는 사람이 다르다.
회복은 시간이 아니라 결과도 푼다 — 팟을 이기면 즉시 완화된다.
"""

# ---------- 손실·이득은 절대 bb 가 아니라 스택 대비로 잰다 ----------
# 15bb 를 잃는 것이 150bb 스택에서는 아무것도 아니고 20bb 스택에서는 치명적이다.
# 절대 기준(예전 BIG_LOSS_BB = 8)을 두면 딥스택 초반에 사소한 팟마다 틸트가 쌓인다.
HIT_MIN = 0.15             # 스택의 15% 미만 손실은 안 쌓인다
HIT_FULL = 0.55            # 스택의 55% 를 잃으면 충격 최대
HIT_BASE = 0.55            # 최대 충격 한 번의 크기. 0.34 로는 스택 55%%를 잃어도
                           # 0.34 에 그쳐 심한 배드빗이 표현되지 않았다

# 결과가 푸는 기준도 상대값이다. 대략 더블업(스택 대비 +0.8) 이상이라야
# 실제로 기분이 풀린다. 작은 팟을 이기는 것으로는 거의 안 풀린다.
RELIEF_MIN = 0.20          # 이 아래는 거의 효과 없음
RELIEF_FULL = 0.80         # 더블업 근처에서 최대
RELIEF_MAX = 0.55          # 한 번에 풀 수 있는 최대치

DECAY_BASE = 0.055         # 핸드당 자연 감쇠

# ---------- 반복 가중 ----------
# 횟수를 세지 않고 '열기'를 쓴다. 큰 손실마다 1 오르고 핸드마다 식는다.
# 횟수만 세면 대회 초반의 한 번과 방금 전의 한 번이 같은 무게가 되는데,
# 실제로는 연달아 맞는 것과 한참 만에 다시 맞는 것이 전혀 다르다.
HEAT_DECAY = 0.085         # 한 번의 사건이 잊히는 데 약 12핸드
HEAT_GAIN = 0.32           # tilt_stack 이 이 폭으로 반복을 증폭/감쇠시킨다
REP_CLAMP = (0.35, 2.60)


def _t(prof, key, default=5.0):
    try:
        return float((prof or {}).get('temper', {}).get(key, default))
    except Exception:
        return default


class Tilt:
    """좌석별 틸트 상태. 대회 하나에 한 개."""

    def __init__(self):
        self.state = {}     # seat -> {'level': 0~1, 'heat': float}

    def _s(self, seat):
        return self.state.setdefault(str(seat), {'level': 0.0, 'heat': 0.0})

    def level(self, seat):
        return self._s(seat)['level']

    def heat(self, seat):
        return self._s(seat)['heat']

    def on_pot(self, seat, prof, delta_bb, stack_bb=None):
        """핸드 결과 반영.

        delta_bb  그 핸드의 손익(bb)
        stack_bb  **핸드 시작 시점**의 스택. 손익을 이것으로 나눠 상대화한다.
        """
        s = self._s(seat)
        if delta_bb is None or not stack_bb or stack_bb <= 0:
            return s['level']
        rel = float(delta_bb) / float(stack_bb)

        if rel > 0:
            # 결과가 푼다. 더블업 근처라야 확실히 풀린다.
            if rel < RELIEF_MIN:
                return s['level']
            g = min(1.0, (rel - RELIEF_MIN) / (RELIEF_FULL - RELIEF_MIN))
            s['level'] = max(0.0, s['level'] - RELIEF_MAX*g)
            s['heat'] = max(0.0, s['heat'] - 1.2*g)
            return s['level']

        loss = -rel
        if loss < HIT_MIN:
            return s['level']                       # 작은 손실은 안 쌓인다
        size = min(1.0, (loss - HIT_MIN) / (HIT_FULL - HIT_MIN))

        prone = _t(prof, 'tilt_prone') / 10.0
        stack_axis = (_t(prof, 'tilt_stack') - 5.0) / 5.0        # -1(감쇠) ~ +1(누적)
        rep = max(REP_CLAMP[0], min(REP_CLAMP[1],
                                    (1.0 + HEAT_GAIN*stack_axis) ** s['heat']))

        s['heat'] += 1.0
        s['level'] = min(1.0, s['level'] + HIT_BASE*prone*size*rep)
        return s['level']

    def on_hand_end(self, seat, prof):
        """핸드마다 감쇠. 회복 속도는 사람마다 다르다."""
        s = self._s(seat)
        s['heat'] = max(0.0, s['heat'] - HEAT_DECAY)
        if s['level'] <= 0.0:
            return 0.0
        rec = _t(prof, 'tilt_recovery') / 10.0
        s['level'] = max(0.0, s['level'] - DECAY_BASE*(0.4 + 1.2*rec))
        if s['level'] <= 0.02:
            s['level'] = 0.0
        return s['level']

    def decay_all(self, profiles):
        for seat in list(self.state):
            p = profiles.get(str(seat)) or profiles.get(seat) or {}
            self.on_hand_end(seat, p)
