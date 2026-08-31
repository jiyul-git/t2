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

BIG_LOSS_BB = 8.0          # 절대 손실 기준
BIG_LOSS_REL = 0.18        # 스택 대비 손실 기준
HIT_BASE = 0.30            # 큰 손실 한 번의 기본 충격
WIN_RELIEF = 0.10          # 팟을 이기면 즉시 완화
DECAY_BASE = 0.055         # 핸드당 자연 감쇠


def _t(prof, key, default=5.0):
    try:
        return float((prof or {}).get('temper', {}).get(key, default))
    except Exception:
        return default


class Tilt:
    """좌석별 틸트 상태. 대회 하나에 한 개."""

    def __init__(self):
        self.state = {}     # seat -> {'level': 0~1, 'episodes': n}

    def _s(self, seat):
        return self.state.setdefault(str(seat), {'level': 0.0, 'episodes': 0})

    def level(self, seat):
        return self._s(seat)['level']

    def on_pot(self, seat, prof, delta_bb, stack_bb=None):
        """핸드 결과 반영. delta_bb 는 그 핸드의 손익(bb)."""
        s = self._s(seat)
        if delta_bb is None:
            return s['level']
        if delta_bb > 0:
            s['level'] = max(0.0, s['level'] - WIN_RELIEF*min(2.0, delta_bb/8.0))
            return s['level']
        if delta_bb >= 0:
            return s['level']

        rel = abs(delta_bb) / max(1.0, float(stack_bb or 40.0))
        if abs(delta_bb) < BIG_LOSS_BB and rel < BIG_LOSS_REL:
            return s['level']                       # 작은 손실은 안 쌓인다

        prone = _t(prof, 'tilt_prone') / 10.0
        size = min(1.0, 0.5*rel/BIG_LOSS_REL + 0.5*abs(delta_bb)/(BIG_LOSS_BB*2))

        # 반복 가중. tilt_stack 이 높으면 누적되고 낮으면 감쇠한다.
        stack_axis = (_t(prof, 'tilt_stack') - 5.0) / 5.0        # -1 ~ +1
        rep = max(0.35, min(2.6, (1.0 + 0.35*stack_axis) ** s['episodes']))

        s['episodes'] += 1
        s['level'] = min(1.0, s['level'] + HIT_BASE*prone*size*rep)
        return s['level']

    def on_hand_end(self, seat, prof):
        """핸드마다 자연 감쇠. 회복 속도는 사람마다 다르다."""
        s = self._s(seat)
        if s['level'] <= 0.0:
            return 0.0
        rec = _t(prof, 'tilt_recovery') / 10.0
        s['level'] = max(0.0, s['level'] - DECAY_BASE*(0.4 + 1.2*rec))
        if s['level'] <= 0.02:
            s['level'] = 0.0
            # 완전히 풀리면 기억도 옅어진다. 아주 사라지지는 않는다.
            s['episodes'] = max(0, s['episodes'] - 1)
        return s['level']

    def decay_all(self, profiles):
        for seat in list(self.state):
            p = profiles.get(str(seat)) or profiles.get(seat) or {}
            self.on_hand_end(seat, p)
