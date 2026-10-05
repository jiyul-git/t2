"""시간 규칙 — Timing Model v1 (TIME_SYSTEM_DESIGN §L, TIME_SYSTEM_IMPLEMENTATION_DESIGN).

상태 없는 순수 함수만 둔다. 전략 RNG 를 한 번도 쓰지 않는다. 무작위가 필요한 곳(성향 생성,
지터)은 결정마다 정해진 시드로 만든 **로컬** `random.Random` 인스턴스만 쓴다.

같은 규칙을 사람이 있는 테이블(실제로 기다림)과 봇만 있는 테이블(테이블 시계만 전진)이 함께 쓴다.
"""
import math
import os
import random
import zlib

import formats as FM

# ---------- 사용자 결정 정책 (§J, 구현 설계 §9) ----------
ACTION_SECONDS = {'regular': 18.0, 'turbo': 14.0, 'hyper': 12.0, 'slow': 18.0}
BANK_START = 60.0            # 누적 타임뱅크 시작값(레이트 레지 동일)
BANK_MAX = 60.0              # 저장 상한(초과분은 버린다)
BANK_RECHARGE = 15.0         # 브레이크마다 충전(55분 플레이 → 5분 브레이크 진입). 레벨/핸드별 충전 없음
# 브레이크 주기 = 플레이 창(활성 초). ui_server.PLAY_WINDOW_SECONDS 와 같은 env 를 읽는다.
PLAY_SECONDS = max(60, int(float(os.environ.get('T2_PLAY_WINDOW_SECONDS', '3300'))))
# 기계 시간(사용자 결정 2026-10-05): 딜·블라인드 7.5초(화면 7.0~7.5초), 보드 공개 2초,
# 결과 표시·카드 수거 2.54초(화면 RESULT_HOLD 2.0 + COLLECT 0.54, 사람 테이블에서만 화면이 소비).
DEAL_SECONDS = 7.5
STREET_SECONDS = 2.0

# ---------- Timing Model v1 (§L) ----------
AMP_B = 4.0                  # commit_effect 증폭
AMP_G = 1.0
RANK_W = 2.0                 # 프리플랍 경계 폭 배수(defend 혼합폭 대비)
JITTER_SIGMA = 0.20


def action_seconds(fmt_key):
    """포맷의 기본 액션 시간. deep(slow) 도 18초(§9-F)."""
    return ACTION_SECONDS[FM.FORMAT_SPEED.get(fmt_key, 'regular')]


def _seed(*parts):
    return zlib.crc32('|'.join(str(p) for p in parts).encode())


# ---------- 성향 (§L 분포) ----------
def timing_traits(pid, tour_seed):
    """pid 와 대회 시드로 정해지는 타이밍 성향. 대회 내내 고정."""
    rng = random.Random(_seed('timing_traits', tour_seed, pid))
    pace = math.exp(rng.gauss(math.log(1.5), 0.35))
    tank = 0.2 + 1.8 * rng.betavariate(2.0, 2.5)
    u = rng.random()
    mask = (rng.uniform(0, 0.15) if u < 0.70 else
            rng.uniform(0.3, 0.6) if u < 0.90 else rng.uniform(0.7, 1.0))
    clock = rng.uniform(0.30, 0.75) if rng.random() < 0.15 else 0.0
    return {'pace': pace, 'tank': tank, 'mask': mask, 'clock': clock}


# ---------- 근접도 v3 ----------
def c_final(eq_used, need_used):
    """실제로 비교된 eq/need 의 거리. 폭은 need 에 비례(0.03~0.15)."""
    w = min(0.15, max(0.03, 0.5 * float(need_used)))
    return max(0.0, 1.0 - abs(float(eq_used) - float(need_used)) / w)


def c_rank(r, thr):
    """핸드 백분위 r 과 인간모델 임계값 thr 의 거리. 폭 = RANK_W × defend 혼합폭."""
    w = RANK_W * max(0.015, 0.15 * float(thr))
    return max(0.0, 1.0 - abs(float(r) - float(thr)) / w)


def closeness_preflop(bound):
    """엔진이 남긴 프리플랍 경계(preflop_plan seed 의 pf_timing)."""
    if not bound:
        return 0.0
    if bound.get('eq') is not None and bound.get('need') is not None:
        return c_final(bound['eq'], bound['need'])
    if bound.get('cap') is not None:
        return c_rank(bound['r'], bound['cap'])
    if bound.get('tot') is not None:
        return c_rank(bound['r'], bound['tot'])
    if bound.get('thr') is not None:
        return c_rank(bound['r'], bound['thr'])
    return 0.0


def closeness_postflop(boundary):
    """응답은 decide_response 의 실제 비교값. 벳/체크 선택(boundary 없음)은 0."""
    if not boundary or boundary.get('eq') is None or boundary.get('need') is None:
        return 0.0
    return c_final(boundary['eq'], boundary['need'])


def structure_postflop(street, facing):
    st = {'flop': 0.33, 'turn': 0.67, 'river': 1.0}.get(street, 0.5)
    return min(1.0, 0.6 * st + 0.4) if facing else 0.6 * st


def structure_preflop(raise_level):
    return 0.3 * min(1.0, (int(raise_level or 1) - 1) / 2.0)


def money_pressure(bf):
    return max(0.0, min(1.0, (float(bf or 1.0) - 1.0) / 0.6))


def commit_facing(tocall, stack):
    """응답: 남은 내 스택 중 콜에 거는 비율."""
    return min(1.0, float(tocall or 0.0) / max(1.0, float(stack or 0.0)))


def commit_choice(amount, stack, opp_left):
    """내 벳/레이즈: 유효 스택(min(내 스택, 상대 남은 스택)) 중 거는 비율."""
    eff = float(stack or 0.0)
    if opp_left is not None and float(opp_left) > 0:
        eff = min(eff, float(opp_left))
    return min(1.0, float(amount or 0.0) / max(1.0, eff))


# ---------- 관련 개념 숙련 K (§9-B) ----------
def knowledge(prof, concepts):
    """그 결정에서 실제 조회한 concept 들의 평균 knowledge. 없으면 전체 concept 평균."""
    import persona as PS
    cs = sorted(set(concepts or ()))
    if not prof or not prof.get('concepts'):
        return None
    if not cs:
        cs = sorted(prof['concepts'])
    if not cs:
        return None
    return sum(PS.concept_knowledge(prof, c) for c in cs) / len(cs)


# ---------- 생각 시간 ----------
def jitter(seed):
    return math.exp(random.Random(seed).gauss(0.0, JITTER_SIGMA))


def visible_seconds(traits, c, s, m, K, trivial, commit, jit, base=18.0,
                    B=None, G=None):
    """reasoning / hold / visible. `jit` 은 곱해질 지터(시드에서 만든 값 또는 시뮬 값)."""
    B = AMP_B if B is None else B
    G = AMP_G if G is None else G
    D_c = 0.60 * c * (0.55 + 0.45 * K)
    D_o = K * (0.25 * s + 0.15 * m)
    P = min(1.0, D_c + D_o)
    effect = commit * c
    reasoning = traits['pace'] * (0.6 + 11.0 * traits['tank'] * P ** 1.6) * (1.0 + B * effect ** G)
    hold = max(traits['mask'] * 6.0, traits['clock'] * base)
    if trivial:
        hold *= 0.3
    return {'P': P, 'effect': effect, 'reasoning': reasoning, 'hold': hold,
            'visible': max(reasoning, hold) * jit}


# ---------- 액션 시계 · 타임뱅크 ----------
def settle(visible, base, bank):
    """한 결정의 시계 정산(봇·사람 공통).

    반환: elapsed(실제로 흐른 초), bank_used, bank_left, timed_out.
    visible > base + bank 이면 타임아웃 — 그 시점(base + bank)에 행동이 강제된다.
    """
    visible = max(0.0, float(visible))
    bank = max(0.0, float(bank))
    if visible <= base:
        return {'elapsed': visible, 'bank_used': 0.0, 'bank_left': bank, 'timed_out': False}
    if visible <= base + bank:
        used = visible - base
        return {'elapsed': visible, 'bank_used': used, 'bank_left': bank - used, 'timed_out': False}
    return {'elapsed': base + bank, 'bank_used': bank, 'bank_left': 0.0, 'timed_out': True}


def breaks_due(clock):
    """활성 플레이 초 clock 까지 진입한 브레이크 수."""
    if clock is None:
        return 0
    return int(max(0.0, float(clock)) // PLAY_SECONDS)


def bank_get(banks, pid, clock):
    """pid 의 지금 뱅크. 저장값은 [초, 이미 반영한 브레이크 수].

    마지막 저장 이후 진입한 브레이크마다 +BANK_RECHARGE(상한 BANK_MAX)를 읽을 때 반영한다.
    봇 테이블 worker 와 사람 테이블이 같은 사람의 뱅크를 따로 써도 브레이크가 두 번 반영되지 않는다.
    예전 형식(초만 저장)은 저장 시점의 브레이크로 본다(소급 충전 없음).
    """
    v = banks.get(pid)
    if v is None:
        return BANK_START
    if isinstance(v, (list, tuple)):
        bank, as_of = float(v[0]), (None if v[1] is None else int(v[1]))
    else:
        bank, as_of = float(v), None
    due = breaks_due(clock)
    if as_of is None or due <= as_of:
        return bank
    return min(BANK_MAX, bank + BANK_RECHARGE * (due - as_of))


def bank_put(banks, pid, bank, clock):
    banks[pid] = [round(min(BANK_MAX, max(0.0, float(bank))), 4), breaks_due(clock)]


def timeout_action(can_check):
    """타임아웃 규칙: 체크 가능하면 체크, 아니면 폴드."""
    return 'check' if can_check else 'fold'


# ---------- 기계 시간 ----------
def mechanical_seconds(n_streets, showdown):
    """봇 테이블 핸드의 기계 시간: 딜·블라인드 + 스트리트당 보드 공개 + 쇼다운."""
    return DEAL_SECONDS + STREET_SECONDS * max(0, int(n_streets) - 1) + (3.0 if showdown else 0.0)
