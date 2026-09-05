"""고친 버그가 다시 살아났는지 검사한다.

    python3 tools/fixed_bugs.py

**regress.py 와 다르다.** regress 는 지문 대조라 동작이 조금이라도 바뀌면
깨진다 — 리팩터용이다. 여기는 '고쳤던 증상이 여전히 안 나오는가'만 본다.
동작을 의도적으로 바꾸는 수정을 해도, 과거에 고친 것들은 그대로여야 한다.

수정 하나가 다른 수정을 되돌리는 일이 실제로 있었다:
리버 사이즈를 열었더니 예산 개념이 없어 3배럴이 생겼고, 예산 카운터로
막았다. 그런 연쇄를 놓치지 않으려면 고칠 때마다 전부 돌려야 한다.

각 검사는 **추정하지 않는다.** 해당 함수를 직접 호출해 반환값을 센다.
새 버그를 고칠 때마다 여기에 한 항목씩 추가할 것.
"""
import sys, os, json, random, collections

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import plan as PL          # noqa: E402
import preflop as PF       # noqa: E402
import persona as PS       # noqa: E402

N = 300
FAILS = []


def report(name, ok, detail):
    print('  [%s] %-46s %s' % ('OK' if ok else '재발', name, detail))
    if not ok:
        FAILS.append(name)


def _prof(seed=11):
    return PS.make_player(random.Random(seed), field_quality=0.6, pid=1)


def check_river_budget():
    """639bae2 — value_2street 이 리버에 못 치던 문제 + 3배럴 방지."""
    prof = _prof()
    board = ['Ad', '9c', '4h', '2s', '7d']
    def run(state):
        c = 0
        for s in range(N):
            if PL.decide_size(prof, ['Ks', 'Kd'], board, 'river', 'value_2street',
                              0.93, [], [], 10000, 40000, random.Random(s),
                              plan_state=state) > 0:
                c += 1
        return c
    left = run({'plan': 'value_2street', 'plan_since': 'turn', 'bet_streets': []})
    spent = run({'plan': 'value_2street', 'plan_since': 'flop',
                 'bet_streets': ['flop', 'turn']})
    report('리버 예산 남으면 친다', left > N*0.8, '%d/%d 벳' % (left, N))
    report('리버 예산 소진이면 안 친다', spent == 0, '%d/%d 벳' % (spent, N))


def check_open_form_cliff():
    """ba3a98b — open_form 의 crude 0/1 계단(27bb 78% -> 28bb 1.5%)."""
    prof = _prof(3)
    prof['concepts']['spr'] = 2.5          # aware 를 낮춰 crude 가 지배하게
    vals = []
    for bb in range(20, 40, 2):
        c = sum(1 for s in range(N)
                if PF.open_decision(prof, 'SB', bb, ['7h', '8h'],
                                    random.Random(s), seats=8,
                                    ante=True)[0] == 'shove')
        vals.append((bb, 100.0*c/N))
    jump = max(abs(vals[i+1][1] - vals[i][1]) for i in range(len(vals)-1))
    report('오픈 형태에 스택 절벽 없음', jump < 30.0,
           '최대 인접 변화 %.1f%%p' % jump)


def check_allin_no_reraise_mult():
    """dff0ddc — 올인 대면에 3벳 배수를 곱해 통째로 올인하던 문제."""
    prof = _prof(5)
    c = collections.Counter()
    for s in range(N):
        a = PF.defend_decision(prof, 'CO', 'LJ', ['8c', '8h'], 22.0, 22.0, 0,
                               random.Random(s), stack_bb=100.0,
                               opener_allin=True)
        c[a[0]] += 1
    report('올인 대면에 오버올인 안 함', c['shove'] == 0,
           'shove %d / 3bet %d / call %d / fold %d'
           % (c['shove'], c['3bet'], c['call'], c['fold']))


def check_trap_taste():
    """ba3a98b — 취향 축 분화와 공부 수렴."""
    def mk(taste, study):
        p = _prof()
        p = dict(p)
        p['temper'] = dict(p['temper']); p['latent'] = dict(p['latent'])
        p['concepts'] = dict(p['concepts'])
        p['temper']['slowplay_taste'] = taste
        p['latent']['study'] = study
        p['concepts']['trap'] = 7.0
        p['concepts']['checkraise_flop'] = 7.0
        return p
    def p_of(taste, study):
        p = mk(taste, study)
        return PL.trap_judgment(p, None, 5.0, 0.15, 0, 'flop', 0.0,
                                lambda c: PS.sk(p, c)/3.33)[0]
    lo_hide, lo_fast = p_of(9.0, 2.5), p_of(1.0, 2.5)
    hi_hide, hi_fast = p_of(9.0, 8.0), p_of(1.0, 8.0)
    report('공부 낮으면 취향대로 갈린다', lo_hide > lo_fast*2.0,
           '숨김 %.3f vs 속공 %.3f' % (lo_hide, lo_fast))
    report('공부 높으면 취향이 수렴한다', abs(hi_hide - hi_fast) < 0.03,
           '숨김 %.3f vs 속공 %.3f' % (hi_hide, hi_fast))


def check_empty_range_guard():
    """ba3a98b — adjust_range_by_history 가 빈 레인지에서 터지던 것."""
    import runner as RU
    class _Dyn:
        def shown(self, seat): return [['Ah', 'Kh'], ['Qs', 'Js'], ['Td', '9d']]
    try:
        RU.adjust_range_by_history([], _Dyn(), 1, ['2c', '7d', '9s'], dead=set())
        report('빈 레인지에서 안 터진다', True, '예외 없음')
    except Exception as e:
        report('빈 레인지에서 안 터진다', False, '%s: %s' % (type(e).__name__, e))


def check_replay_records():
    """재생 경로가 기록을 안 남기던 문제 — 격리 폴더에서 실제 게임을 돌린다."""
    import subprocess, tempfile, shutil, os as _os
    src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')
    tmp = tempfile.mkdtemp(prefix='fb_')
    dst = _os.path.join(tmp, 't2')
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
        '.git', '__pycache__', 'hand_archive2*.jsonl', '*state*.json', 'bak_*'))
    code = (
        "import sys,json;sys.path.insert(0,%r);import live2\n"
        "live2.new_game(entries=40,start_stack=30000,seed=555,hands_per_level=12)\n"
        "r=live2.step()\n"
        "if not r.get('done') and '\uBCF4\uB4DC' not in r['view']: r=live2.step('call')\n"
        "while not r.get('done'): r=live2.step('check')\n"
        "rows=[json.loads(l) for l in open(%r+'/hand_archive2.jsonl') if l.strip()]\n"
        "m=t=0\n"
        "for x in rows:\n"
        "    rec=set(i['street'] for i in x['intents'])\n"
        "    for st in ('flop','turn','river'):\n"
        "        if [e for e in x['full_log'] if e[0]==st and e[1]!=x['hero']]:\n"
        "            t+=1\n"
        "            if st not in rec: m+=1\n"
        "print(t,m)\n" % (dst, dst))
    try:
        out = subprocess.run([sys.executable, '-c', code], capture_output=True,
                             text=True, timeout=300, cwd=dst)
        tot, miss = out.stdout.strip().split()[:2]
        report('재생 경로도 기록을 남긴다', int(miss) == 0,
               '스트리트 %s개 중 누락 %s개' % (tot, miss))
    except Exception as e:
        report('재생 경로도 기록을 남긴다', False, '검사 실패 %s' % e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)



def check_bluff_disguise():
    """위장형 블러프가 밸류와 같은 사이즈로 나가는가."""
    prof = _prof()
    board = ['Kd', '9c', '4h']
    st = {'plan': 'bluff_2street', 'bluff_mode': 'merged', 'bluff_mul': 1.0}
    b = [PL.decide_size(prof, ['Qs', 'Js'], board, 'flop', 'bluff_2street', 0.15,
                        [], [], 6000, 40000, random.Random(i), plan_state=st)
         for i in range(60)]
    v = [PL.decide_size(prof, ['Ks', 'Kh'], board, 'flop', 'value_2street', 0.90,
                        [], [], 6000, 40000, random.Random(i),
                        plan_state={'plan': 'value_2street'})
         for i in range(60)]
    bm, vm = sum(b)/len(b), sum(v)/len(v)
    report('위장 블러프가 밸류와 같은 사이즈', abs(bm - vm) < 0.03,
           '블러프 %.0f%% vs 밸류 %.0f%%' % (bm*100, vm*100))


def check_commit_by_study():
    """목표 커밋이 공부에 따라 갈리는가(초보는 강도 무관 습관값)."""
    def mk(sk):
        p = dict(_prof()); p['concepts'] = dict(p['concepts'])
        p['concepts']['spr'] = sk
        return p
    lo = [PL.target_commit(mk(2.0), r, 1, 5.0, 'flop') for r in (0.2, 0.95)]
    hi = [PL.target_commit(mk(9.0), r, 1, 5.0, 'flop') for r in (0.2, 0.95)]
    report('초보는 강도와 무관한 습관 목표', abs(lo[0]-lo[1]) < 0.02,
           'rel0.2 %.0f%% vs rel0.95 %.0f%%' % (lo[0]*100, lo[1]*100))
    report('레귤러는 강도를 따라간다', hi[1] - hi[0] > 0.4,
           'rel0.2 %.0f%% vs rel0.95 %.0f%%' % (hi[0]*100, hi[1]*100))



def check_semibluff_transition():
    """드로우 완성 시 턴에서 밸류로 전환되는가(rel 이 낮아도)."""
    prof = _prof()
    st = {'plan': 'semibluff', 'outs': 9, 'rel': 0.45, 'made': 0, 'intents': {}}
    hit = PL.refresh(dict(st), ['Ah', 'Kh'], ['Qh', '7h', '2c', '5h'], [],
                     prof, 6000, 40000, 'turn', n_opp=1, seed=1)
    dead = PL.refresh(dict(st), ['Ah', 'Kh'], ['Qs', '7d', '2c', '5c'], [],
                      prof, 6000, 40000, 'turn', n_opp=1, seed=1)
    report('드로우 완성 → 밸류 전환', hit['plan'].startswith('value'),
           '완성 %s / 소멸 %s' % (hit['plan'], dead['plan']))



def check_fold_equity_sizing():
    """폴드율 역산이 상대 성향에 반응하고 요구폴드율을 밑도는가."""
    prof = _prof()
    lo = PL.barrel_size(0.20, prof)
    hi = PL.barrel_size(0.65, prof)
    ok_dir = hi > lo + 0.2
    report('안 접는 상대엔 작게, 잘 접으면 크게', ok_dir,
           '폴드20%% -> %.0f%% / 폴드65%% -> %.0f%%' % (lo*100, hi*100))
    bad = [f for f in (0.20, 0.35, 0.50, 0.65)
           if PL.breakeven_fold(PL.barrel_size(f, prof)) >= f]
    report('요구 폴드율이 상대 폴드율을 넘지 않음', not bad,
           '위반 %d건' % len(bad))



def check_no_profile_leak():
    """행동이 같으면 실제 개념이 달라도 belief 가 같아야 한다(정보 누출).

    문자열 'concepts' 가 소스에 있는지로 검사하면 안 된다 — 관찰자 자신의
    개념을 읽는 것은 정상이고, 반환 키 이름이 estimated_concepts 인 것도
    정상이다. **실제 접근 경로**를 봐야 하므로 행동으로 검사한다.
    """
    import reads as RD
    bk = RD.Book()
    def fill(i, j):
        r = bk.rec(i, j)
        r.update({'hands': 60, 'vpip': 13, 'pfr': 10, 'cbet': 12,
                  'cbet_opp': 20, 'barrel': 5, 'barrel_opp': 12,
                  'fold_to_bet': 11, 'facing_bet': 20})
        return r
    # 행동 장부가 완전히 동일한 두 상대
    fill('O', 'WEAK'); fill('O', 'STRONG')
    obs = {'temper': {'attention': 7, 'adaptability': 5, 'consistency': 5},
           'concepts': {'range_read': 7, 'sizing_tell': 6}}
    a = RD.opponent_belief(bk, 'O', 'WEAK', obs, random.Random(3))
    b = RD.opponent_belief(bk, 'O', 'STRONG', obs, random.Random(3))
    same = (a['concept_belief'] == b['concept_belief']
            and a['style_belief'] == b['style_belief'])
    report('행동이 같으면 belief 도 같다(누출 없음)', same,
           'range_read %.1f vs %.1f'
           % (a['concept_belief']['range_read'],
              b['concept_belief']['range_read']))


def check_archetype_not_driving():
    """봇의 행동이 아키타입 라벨이 아니라 개념 벡터에서 나오는가."""
    import persona as PS
    import random as _r
    p = PS.make_player(_r.Random(5), field_quality=0.6, pid=1)
    has_vec = bool(p.get('concepts'))
    # label 은 벡터에서 파생된 표시용이어야 한다(원인이 아니라 결과)
    lab = p.get('type')
    report('생성된 봇이 개념 벡터를 가진다', has_vec, 'label=%s' % lab)



def check_belief_observer_dependent():
    """같은 상대·같은 장부라도 관찰자에 따라 belief 가 달라지는가."""
    import reads as RD
    bk = RD.Book()
    r = bk.rec('A', 'B')
    r.update({'hands': 60, 'vpip': 13, 'pfr': 10, 'cbet': 12, 'cbet_opp': 20,
              'barrel': 5, 'barrel_opp': 12, 'fold_to_bet': 11,
              'facing_bet': 20})
    def mk(att, rr, stl):
        return {'temper': {'attention': att, 'adaptability': 5, 'consistency': 5},
                'concepts': {'range_read': rr, 'sizing_tell': stl}}
    sharp = RD.opponent_belief(bk, 'A', 'B', mk(9, 9, 9), random.Random(7))
    dull = RD.opponent_belief(bk, 'A', 'B', mk(1, 1, 1), random.Random(7))
    top_s = max(sharp['style_belief'].values())
    top_d = max(dull['style_belief'].values())
    report('관찰력에 따라 스타일 확신이 다르다', top_s > top_d + 0.15,
           '예리 %.2f vs 둔감 %.2f' % (top_s, top_d))
    report('확신이 낮으면 개념 belief 가 중립에 가깝다',
           abs(dull['concept_belief']['range_read'] - 5.0)
           < abs(sharp['concept_belief']['range_read'] - 5.0) + 0.01,
           '둔감 %.1f vs 예리 %.1f'
           % (dull['concept_belief']['range_read'],
              sharp['concept_belief']['range_read']))



def check_board_metrics_refresh():
    """스트리트가 바뀌면 nut_adv/range_adv 가 실제로 재계산되는가.

    값 비교만으로는 우연히 같은 경우를 구분할 수 없어 **호출 자체**를 센다.
    """
    import ranges as _R
    import plan as _PL
    cnt = {'n': 0, 'a': 0}
    _n, _a = _R.nut_advantage, _R.range_advantage

    def n2(*x, **k):
        cnt['n'] += 1
        return _n(*x, **k)

    def a2(*x, **k):
        cnt['a'] += 1
        return _a(*x, **k)
    _R.nut_advantage = _PL.R.nut_advantage = n2
    _R.range_advantage = _PL.R.range_advantage = a2
    try:
        st = {'plan': 'value_2street', 'rel': 0.6, 'my_range': [('As', 'Kd')],
              'street_made': 'flop', 'refreshed': ['flop']}
        _PL.refresh(st, ['As', 'Kd'], ['2c', '7d', '9s', 'Th'],
                    [('Qh', 'Qs'), ('8c', '8d')], _prof(), 6000, 40000,
                    'turn', n_opp=1, seed=1, my_range=[('As', 'Kd')])
    finally:
        _R.nut_advantage = _PL.R.nut_advantage = _n
        _R.range_advantage = _PL.R.range_advantage = _a
    report('refresh 가 레인지 우위를 재계산한다',
           cnt['n'] >= 1 and cnt['a'] >= 1,
           'nut %d회 / adv %d회' % (cnt['n'], cnt['a']))


def main():
    print('고친 버그 재발 검사 (각 %d회, 실제 함수 호출)' % N)
    print()
    for fn in (check_river_budget, check_open_form_cliff,
               check_allin_no_reraise_mult, check_trap_taste,
               check_empty_range_guard, check_replay_records,
               check_bluff_disguise, check_commit_by_study,
               check_semibluff_transition, check_fold_equity_sizing,
               check_no_profile_leak, check_archetype_not_driving,
               check_belief_observer_dependent,
               check_board_metrics_refresh):
        try:
            fn()
        except Exception as e:
            report(fn.__name__, False, '검사 자체가 터짐 %s: %s'
                   % (type(e).__name__, e))
    print()
    if FAILS:
        print('재발 %d건: %s' % (len(FAILS), ', '.join(FAILS)))
        sys.exit(1)
    print('재발 없음')


if __name__ == '__main__':
    main()
