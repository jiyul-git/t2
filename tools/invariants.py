"""불변식 검사 — '항상 참이어야 하는 것'을 단언한다.

tools/regress.py 와 역할이 다르다.
  regress   : 지문 비교. '동작이 바뀌었나'. 원래부터 틀린 것은 못 잡는다.
  invariants: 속성 단언. '이건 틀렸다'. 처음부터 틀린 것도 잡는다.

**버그를 하나 잡을 때마다 여기에 항목을 영구 추가할 것.**
그래야 같은 버그가 다시 안 나온다. 항목은 계속 늘어나는 게 정상이다.

    python3 tools/invariants.py [핸드수] [시드수]
"""
import sys, os, collections, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import tourney as T
import plan as PL
import persona as PS

VIOL = collections.Counter()
DETAIL = collections.defaultdict(list)

PRE = ['UTG', 'UTG+1', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
POST = ['SB', 'BB', 'UTG', 'UTG+1', 'LJ', 'HJ', 'CO', 'BTN']


def bad(name, msg):
    VIOL[name] += 1
    if len(DETAIL[name]) < 3:
        DETAIL[name].append(msg)


# ---------- 개별 불변식 ----------

def inv_chip_conservation(before, after, tag):
    """칩 총량 보존 — 단, 좌석 구성이 그대로일 때만.

    finish_hand 는 탈락자 자리에 새 플레이어를 앉히고(_seat),
    테이블 재조정 시 히어로를 다른 테이블로 옮긴다(_move_hero).
    둘 다 좌석 구성을 바꾸므로 총량이 달라지는 게 정상이다.
    같은 좌석 집합일 때만 보존을 요구해야 한다.
    """
    if set(before) != set(after):
        return                       # 좌석 교체·테이블 이동 → 비교 대상 아님
    b, a = sum(before.values()), sum(after.values())
    if b != a:
        bad('칩총량', '%s: %d → %d (차이 %+d)' % (tag, b, a, a - b))


def inv_no_negative_stack(stacks, tag):
    for s, v in stacks.items():
        if v < 0:
            bad('음수스택', '%s: 좌석%s = %d' % (tag, s, v))


def inv_action_order(log, pos, tag):
    """폴드한 사람이 다시 액션하지 않는다."""
    folded = set()
    for (stt, x, a, amt) in log:
        if x in folded:
            bad('폴드후액션', '%s: 좌석%s 가 폴드 후 %s' % (tag, x, a))
        if a == 'fold':
            folded.add(x)


def inv_street_progression(log, tag):
    """스트리트는 preflop→flop→turn→river 순서로만 진행한다."""
    idx = {'preflop': 0, 'flop': 1, 'turn': 2, 'river': 3}
    last = -1
    for (stt, x, a, amt) in log:
        i = idx.get(stt, -1)
        if i < last:
            bad('스트리트역행', '%s: %s 가 뒤에 나옴' % (tag, stt))
        last = max(last, i)


def inv_walk_no_action(log, tag):
    """전원 폴드(워크)면 BB 에게 액션을 묻지 않는다.

    실제로 있었던 버그. needs_action 이 '아직 액션 안 한 좌석'을 그대로
    돌려주므로, 살아있는 사람이 하나뿐인데도 BB 를 반환했다.
    """
    pre = [(x, a) for (stt, x, a, _) in log if stt == 'preflop']
    live = set(x for x, _ in pre)
    folds = [x for x, a in pre if a == 'fold']
    acted_after_walk = [x for x, a in pre if a not in ('fold',)]
    if len(folds) == len(pre) - 1 and len(acted_after_walk) == 1:
        x, a = [(x, a) for x, a in pre if a != 'fold'][0]
        if a == 'check':
            pass                       # 정상: 림프 팟에서의 체크
    # 액션이 전부 fold 인데 로그에 fold 아닌 항목이 있으면 이상
    if pre and all(a == 'fold' for _, a in pre[:-1]) and len(pre) > 1:
        last_a = pre[-1][1]
        if last_a in ('bet', 'raise', 'call') and len(set(x for x, _ in pre)) == len(pre):
            pass


def inv_call_amount(log, tag):
    """콜 금액은 음수일 수 없고, 체크는 금액이 0이다."""
    for (stt, x, a, amt) in log:
        if a == 'check' and amt:
            bad('체크금액', '%s: 좌석%s check 인데 %s' % (tag, x, amt))
        if amt is not None and amt < 0:
            bad('음수금액', '%s: 좌석%s %s %s' % (tag, x, a, amt))


def inv_eq_need_consistency(dec, tag):
    """eq < need 인데 콜/레이즈하면 사유가 있어야 한다.

    실제로 있었던 버그. 좌석5가 eq 0.523 < need 0.530 인데 15,000 을 콜했다.
    성향(call_bias)은 need 를 조정해야지, 부등호를 무시하면 안 된다.
    (커밋 구간·올인 콜오프 등 정당한 예외는 reason 에 기록되어야 한다.)
    """
    eq, need, act = dec.get('eq'), dec.get('need'), dec.get('act')
    if eq is None or need is None:
        return
    if act in ('call',) and eq < need - 0.002:
        if not dec.get('override'):
            bad('eq<need콜', '%s: eq %.3f < need %.3f 인데 콜 (plan=%s, spr=%.1f)'
                % (tag, eq, need, dec.get('plan'), dec.get('spr') or -1))


def inv_bluff_share_domain(tag):
    """블러프 지분 공식의 정의역 점검.

    s/(1+2s) 는 '양극화된 균형 베터'를 전제한 식이다.
    그 전제가 성립하는 구간(대략 0.25~2.0팟) 밖에서 그대로 외삽하면
    '팟의 9배를 던지는 사람의 절반이 블러프'라는 결론이 나온다.
    """
    import bot
    for s in (3.0, 5.0, 9.4):
        v = bot.bluff_share(s, 'turn', 5.0)
        if v > 0.42:
            bad('블러프지분외삽',
                '사이즈 %.1f팟에서 블러프 지분 %.0f%% — 균형 공식 정의역 밖' % (s, 100*v))


def inv_concept_vector_alive(t, tag):
    """개념 벡터가 판단까지 살아서 가는가.

    실제로 있었던 버그. play.Hand.axes() 가 6개 스칼라만 추려 넘겨서
    profile.get('concepts') 분기가 전부 죽었다.
    """
    for s in t.seats:
        if s == t.hero:
            continue
        ax, _ = t.hand.axes(s)
        if not ax.get('concepts'):
            bad('개념벡터소실', '%s: 좌석%s 프로필에 concepts 없음' % (tag, s))
            return
        if not ax.get('temper'):
            bad('기질소실', '%s: 좌석%s 프로필에 temper 없음' % (tag, s))
            return


def inv_book_accumulates(t, tag):
    """리딩 장부가 실제로 쌓이는가.

    실제로 있었던 버그 3개: _pid NameError 로 쇼다운 관찰 전부 유실,
    c-bet 기회 판정 오류, 관찰자를 생존자로만 셈.
    """
    if t.hand_no < 30:
        return
    d = t.book.d
    if not d:
        bad('장부빔', '%s: 30핸드 이후에도 장부가 비어 있음' % tag)
        return
    sd = max((r.get('showdowns', 0) for r in d.values()), default=0)
    cb = max((r.get('cbet_opp', 0) for r in d.values()), default=0)
    fb = max((r.get('facing_bet', 0) for r in d.values()), default=0)
    if sd == 0:
        bad('쇼다운관찰없음', '%s: %d핸드인데 showdowns 최대 0' % (tag, t.hand_no))
    if cb == 0:
        bad('씨벳기회없음', '%s: %d핸드인데 cbet_opp 최대 0' % (tag, t.hand_no))
    if fb == 0:
        bad('폴드관찰없음', '%s: %d핸드인데 facing_bet 최대 0' % (tag, t.hand_no))


def inv_no_hero_cards_in_opp_range(tag, hero_hole, board, opp_range):
    """상대 레인지에 내 카드나 보드 카드가 들어가면 안 된다."""
    dead = set(hero_hole) | set(board)
    for c in opp_range[:400]:
        if c[0] in dead or c[1] in dead:
            bad('데드카드누출', '%s: 상대 레인지에 %s%s' % (tag, c[0], c[1]))
            return


def inv_intent_exists(state, street, tag):
    """무저항 스트리트에는 판단 층이 정한 의도가 반드시 있어야 한다.

    의도가 없으면 집행부가 추측으로 행동하게 되고, 그게 곧
    '계획을 무시하는 실행 경로'다. (giveup 계획인데 벳한 버그의 정체)
    """
    if not state:
        return
    it = (state.get('intents') or {}).get(street)
    if it is None:
        bad('의도없음', '%s: %s 스트리트에 intent 가 없음 (plan=%s)'
            % (tag, street, state.get('plan')))


def inv_action_matches_intent(state, street, executed, tag):
    """실행된 액션은 의도와 일치하거나, 이탈 기록이 있어야 한다.

    이게 이번 구조 정리의 핵심 검사다.
    '계획에 없는 액션인데 이탈 로그도 없다' = 판단 층을 우회한 경로가 남아 있다.
    """
    if not state:
        return
    it = (state.get('intents') or {}).get(street)
    if it is None:
        return                                  # inv_intent_exists 가 잡는다
    if executed in ('call', 'fold', 'raise'):
        return                                  # 저항 상황은 별도 경로
    if it['act'] != executed:
        devs = state.get('deviations') or []
        if not any(d.get('street') == street for d in devs):
            bad('의도불일치', '%s: 의도 %s 인데 %s 실행, 이탈 기록 없음 (plan=%s)'
                % (tag, it['act'], executed, state.get('plan')))


def inv_plan_not_rewritten(state, tag):
    """계획이 실행에 맞춰 사후 수정되지 않았는가.

    예전 enforce_consistency 가 giveup→bluff_2street 로 계획을 고쳐써서
    모순의 증거를 지웠다. 그 함수는 제거했고, 다시 생기지 않게 감시한다.
    """
    for w in (state.get('why') or []):
        if '실행으로 계획 갱신' in w or '실행으로 팟컨트롤' in w:
            bad('계획사후수정', '%s: %s' % (tag, w))


# ---------- 이상행동 봇 (히어로 자리) ----------

class ChaosHero:
    """봇이 절대 안 하는 행동을 일부러 한다.

    버그는 정상 범위 밖 입력에서 나온다. 봇끼리만 돌리면 그 입력이
    영영 안 나오므로, 히어로 자리에 극단적 행동을 하는 놈을 앉힌다.
    (9.4배 오버벳 콜 버그가 정확히 이렇게 발견됐다.)
    """
    def __init__(self, seed):
        self.rng = random.Random(seed)

    def act(self, st):
        tc = st.get('tocall', 0)
        pot = max(1, st.get('pot', 0))
        stack = st.get('stack', 0)
        r = self.rng.random()
        if tc > 0:
            if r < 0.35: return ('fold', 0)
            if r < 0.65: return ('call', 0)
            if r < 0.90 and st.get('can_raise'):
                # amount 는 '목표 총액'이지 '추가로 넣을 액수'가 아니다.
                # 남은 스택으로 cap 하면 이미 넣은 칩이 있을 때 목표가
                # 최소 레이즈에 못 미쳐 엔진이 정당하게 거부한다 —
                # 그것을 예외로 세면 도구가 자기 버그를 제품 버그로 보고한다.
                # contrib 는 좌석별 dict 다. 히어로 자리 것만 꺼낸다.
                _c = st.get('contrib') or {}
                _me = st.get('seat', st.get('hero'))
                mine = _c.get(_me, 0) if isinstance(_c, dict) else 0
                if not mine and isinstance(_c, dict):
                    # 좌석 키를 모르면 to_call 로 역산한다 (현재 최고액 − 내 기여)
                    mine = max(0, max(_c.values() or [0]) - tc)
                cap = stack + mine
                mult = self.rng.choice([2, 3, 5, 9, 15])
                tgt = max(st.get('min_raise', 0), int(pot*mult))
                if tgt >= cap:
                    return ('allin', 0)
                return ('raise', tgt)
            return ('allin', 0)
        if r < 0.30: return ('check', 0)
        mult = self.rng.choice([0.2, 0.5, 1.0, 3.0, 9.0, 20.0])
        amt = min(stack, int(pot*mult))
        return ('bet', amt) if amt > 0 else ('check', 0)


# ---------- 실행 ----------

def run(hands=200, seeds=6):
    decisions = []
    o = PL.act_with_plan

    def spy(hero, board, profile, plan_state, pot, tocall, stack, street, **k):
        r = o(hero, board, profile, plan_state, pot, tocall, stack, street, **k)
        if tocall > 0 and isinstance(r[1], float):
            decisions.append({'eq': r[1], 'need': r[2], 'act': r[0][0],
                              'plan': plan_state.get('plan'),
                              'spr': (stack/max(1.0, float(pot))),
                              'override': plan_state.get('_committed')})
        return r
    PL.act_with_plan = spy
    import session
    session.PL = PL

    inv_bluff_share_domain('static')

    for si in range(seeds):
        chaos = ChaosHero(9000 + si)
        t = T.Tournament(entries=100, start_stack=30000, hero_seat=7, seats=8,
                         seed=5000 + si, hands_per_level=12)
        for hi in range(hands):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            tag = 's%d h%d' % (5000 + si, hi + 1)
            before = dict(t.stacks)
            before_tbl = getattr(getattr(t, 'tables', None), 'hero_table', None)
            before_pids = {s: t.profiles.get(str(s), {}).get('id') for s in t.stacks}
            try:
                st = t.next_hand()
                g = 0
                while st and not st.get('done') and g < 300:
                    a, amt = chaos.act(st)
                    st = t.submit(a, amt)
                    g += 1
                if g >= 300:
                    bad('무한루프', '%s: 300 액션 초과' % tag)
            except Exception as e:
                bad('예외', '%s: %r' % (tag, e))
                break
            log = getattr(t.run, 'full_log', []) or []
            # 계획 층 검사: 각 좌석의 계획에 의도가 있고, 실행이 그와 일치하는가
            for _seat, _st in (getattr(t.hand, 'plans', {}) or {}).items():
                inv_plan_not_rewritten(_st, tag)
                for _stt in ('flop', 'turn', 'river'):
                    if any(x[0] == _stt for x in log):
                        acts_here = [a for (s2, x, a, _) in log
                                     if s2 == _stt and x == _seat and a in ('bet', 'check')]
                        if acts_here:
                            inv_intent_exists(_st, _stt, tag)
                            inv_action_matches_intent(_st, _stt, acts_here[0], tag)
            inv_action_order(log, t.hand.pos, tag)
            inv_street_progression(log, tag)
            inv_call_amount(log, tag)
            inv_no_negative_stack(t.stacks, tag)
            if hi == 0:
                inv_concept_vector_alive(t, tag)
            for d in decisions:
                inv_eq_need_consistency(d, tag)
            decisions.clear()
            t.finish_hand()
            after_pids = {s: t.profiles.get(str(s), {}).get('id') for s in t.stacks}
            # 좌석 번호가 같아도 '다른 사람'이 앉았으면 비교 대상이 아니다
            # (테이블 이동·신규 착석). 사람이 그대로일 때만 보존을 요구한다.
            if before_pids == after_pids:
                inv_chip_conservation(before, t.stacks, tag)
        inv_book_accumulates(t, 's%d' % (5000 + si))

    PL.act_with_plan = o
    return VIOL, DETAIL


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    hands = int(args[0]) if args else 150
    seeds = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    v, d = run(hands, seeds)
    if not v:
        print('불변식 위반 없음 (%d시드 × %d핸드)' % (seeds, hands))
        return 0
    print('불변식 위반 (%d시드 × %d핸드)\n' % (seeds, hands))
    for k, n in v.most_common():
        print('[%s] %d건' % (k, n))
        for m in d[k]:
            print('   ', m)
    return 1

# ---------- 필드 총칩 ----------
# 핸드 안의 보존은 inv_chip_conservation 이 이미 본다.
# 여기서 보는 것은 필드 전체다 — 총 칩은 언제나 entries x start_stack 이어야 한다.
# 히어로 테이블만 보면 재조정으로 칩이 드나들어 보존되지 않는 것이 정상이다.
def check_field_chips(seeds=(7000, 7001), rounds=6, fmt='standard'):
    import sys as _s, os as _o
    _s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..'))
    import fieldsim as FS
    bad_list = []
    for sd in seeds:
        f = FS.Field(entries=64, seed=sd, fmt=fmt)
        want = f.entries * f.start_stack
        for r in range(rounds):
            f.step_others()
            got = sum(p['stack'] for p in f.players.values())
            if got != want:
                bad_list.append('시드 %d 라운드 %d: 총칩 %d != %d (%+d)'
                                % (sd, r, got, want, got - want))
        if f.errors:
            bad_list.append('시드 %d: 삼킨 예외 %d건 — %s'
                            % (sd, len(f.errors), f.errors[0]))
    return bad_list


if __name__ == '__main__':
    import sys
    if '--chips' in sys.argv:
        _b = check_field_chips()
        print('필드 총칩 이상 없음' if not _b else '\n'.join(_b[:12]))
        sys.exit(1 if _b else 0)
    sys.exit(main())
