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
    v = (prof or {}).get('temper', {}).get(key, default)
    return float(v) if isinstance(v, (int, float)) else default


class Tilt:
    """**플레이어별** 틸트 상태. 대회 하나에 한 개.

    키는 좌석이 아니라 사람(play.Hand.pid_of)이다. 좌석 번호는 테이블마다
    1..8 로 겹치므로, 좌석을 키로 쓰면 서로 다른 테이블의 다른 사람이 같은
    상태를 공유한다. 예전에 그랬고 shown 까지 섞여서, 한 테이블의 쇼다운이
    다른 테이블 봇의 레인지 추정에 들어갔다. 여기로 좌석 번호를 넘기지 말 것.
    """

    def __init__(self):
        self.state = {}

    def _s(self, pid):
        return self.state.setdefault(str(pid), {
            'level': 0.0,        # 현재 틸트 0~1
            'heat': 0.0,         # 반복 가중용. 핸드마다 식는다
            'streak': 0,         # 연속으로 진 핸드 수
            'dry': 0,            # 참가하지 못한 연속 핸드 수
            'shown': [],         # 이 사람이 쇼다운에서 깐 패 (레인지 추정용)
        })

    def level(self, pid):
        return self._s(pid)['level']

    def heat(self, pid):
        return self._s(pid)['heat']

    def on_pot(self, pid, prof, delta_bb, stack_bb=None):
        """핸드 결과 반영.

        delta_bb  그 핸드의 손익(bb)
        stack_bb  **핸드 시작 시점**의 스택. 손익을 이것으로 나눠 상대화한다.
        """
        s = self._s(pid)
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

    # ---------- 큰 손실 외의 원인들 ----------
    # 실제 틸트는 팟 크기 하나로 오지 않는다. 아래는 엔진이 이미 아는 정보로
    # 구현 가능한 것들만 넣었다. 배드빗(에쿼티 우위였는데 짐)이나
    # '내가 폴드한 뒤 상대가 블러프를 보여줌' 같은 것은 정보가 더 필요해 보류.

    STREAK_MIN = 4             # 이 이상 연속으로 져야 쌓이기 시작
    STREAK_STEP = 0.045        # 연속 1회 추가당
    DRY_MIN = 14               # 이 이상 참가 못 하면
    DRY_STEP = 0.012           # 핸드당. 카드가 안 오는 답답함은 약하지만 길다
    SUNK_MIN = 0.12            # 스택의 이만큼 넣고 폴드하면
    SUNK_K = 0.55              # 같은 크기 손실 대비 충격 비율

    LOSS_WEIGHT_SHOWDOWN = 1.0     # 끝까지 가서 진 핸드
    LOSS_WEIGHT_FOLD = 0.6         # 넣었다가 중간에 접은 핸드

    def on_result(self, pid, prof, won, played, contested=None, showdown=False):
        """핸드 하나의 결과 요약. 큰 팟이 아니어도 쌓이는 것들.

        won       그 핸드에서 칩이 늘었나
        played    자발적으로 참가했나(VPIP). 블라인드만 낸 것은 참가가 아니다
        contested 팟을 다퉜나. 연속패는 **다툰 핸드**만 센다 —
                  블라인드만 낸 것은 지는 것이 아니다
        showdown  끝까지 가서 졌나. 중간에 접은 것보다 무겁게 센다
        """
        s = self._s(pid)
        prone = _t(prof, 'tilt_prone') / 10.0
        if contested is None:
            contested = played
        if won:
            s['streak'] = 0.0
        elif not contested:
            pass                      # 안 다툰 핸드는 연속패에 안 들어간다
        else:
            # 무게가 다르다. 쇼다운까지 가서 지는 것과 중간에 접는 것을
            # 같은 1회로 세면 '잘 접었다'고 넘길 수 있는 핸드가
            # 배드빗과 같은 무게를 갖게 된다.
            s['streak'] += self.LOSS_WEIGHT_SHOWDOWN if showdown \
                else self.LOSS_WEIGHT_FOLD
            if s['streak'] >= self.STREAK_MIN:
                over = s['streak'] - self.STREAK_MIN + 1.0
                s['level'] = min(1.0, s['level'] + self.STREAK_STEP*prone*min(4.0, over))
        if played:
            s['dry'] = 0
        else:
            s['dry'] += 1
            if s['dry'] >= self.DRY_MIN:
                s['level'] = min(1.0, s['level'] + self.DRY_STEP*prone)
        return s['level']

    def on_fold_after_investing(self, pid, prof, invested_bb, stack_bb):
        """어려운 팟에서 포기. 같은 크기를 쇼다운에서 잃는 것보다는 덜 아프지만
        '내가 접었다'는 자책이 붙어 무시할 수 없다."""
        if not stack_bb or stack_bb <= 0:
            return self._s(pid)['level']
        rel = float(invested_bb) / float(stack_bb)
        if rel < self.SUNK_MIN:
            return self._s(pid)['level']
        s = self._s(pid)
        size = min(1.0, (rel - self.SUNK_MIN) / (HIT_FULL - self.SUNK_MIN))
        prone = _t(prof, 'tilt_prone') / 10.0
        stack_axis = (_t(prof, 'tilt_stack') - 5.0) / 5.0
        rep = max(REP_CLAMP[0], min(REP_CLAMP[1],
                                    (1.0 + HEAT_GAIN*stack_axis) ** s['heat']))
        s['heat'] += 0.6
        s['level'] = min(1.0, s['level'] + HIT_BASE*self.SUNK_K*prone*size*rep)
        return s['level']

    def note_showdown(self, pid, hand):
        """쇼다운에서 깐 패. 레인지 추정(runner.adjust_range_by_history)이 쓴다.

        pid 기준이다. 좌석으로 넣으면 테이블끼리 섞인다.
        """
        s = self._s(pid)
        s['shown'].append(hand)
        if len(s['shown']) > 12:
            s['shown'] = s['shown'][-12:]

    def shown(self, pid):
        return self._s(pid)['shown']

    def on_hand_end(self, pid, prof):
        """핸드마다 감쇠. 회복 속도는 사람마다 다르다."""
        s = self._s(pid)
        s['heat'] = max(0.0, s['heat'] - HEAT_DECAY)
        if s['level'] <= 0.0:
            return 0.0
        rec = _t(prof, 'tilt_recovery') / 10.0
        s['level'] = max(0.0, s['level'] - DECAY_BASE*(0.4 + 1.2*rec))
        if s['level'] <= 0.02:
            s['level'] = 0.0
        return s['level']

    def decay_all(self, profiles):
        """핸드마다 감쇠. profiles 는 **pid 키**여야 한다 (session 이 그렇게 만든다).

        상태에 있는 모든 키를 훑는다. 이 테이블에 없는 사람은 프로필을 못 찾아
        기본값으로 감쇠한다 — 예전에는 좌석 키라서 남의 프로필을 끌어다 썼다.
        훑는 범위 자체는 이번에 바꾸지 않았다. 이번 변경은 키 하나뿐이다.
        """
        for pid in list(self.state):
            p = profiles.get(str(pid)) or profiles.get(pid) or {}
            self.on_hand_end(pid, p)
