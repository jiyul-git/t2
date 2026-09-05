"""스타일별 개념 사전분포(prior) 캘리브레이션.

    python3 tools/calibrate.py [샘플수]

**게임 중 실제 상대의 concepts 를 읽지 않는다.** 대신 플레이어 생성기를
독립적으로 대량 샘플링해서, 생성 규칙이 만들어내는 라벨별 개념 분포를 구한다.

    생성 규칙 → 독립 플레이어 대량 생성 → vector → label
             → label 별 concept 분포 → STYLE_CONCEPT_PRIOR

이건 '이 필드에서 TAG 는 대체로 이렇더라'는 경험칙이지 특정 상대의 정보가
아니다. 관찰자가 필드 경험으로 알 수 있는 종류의 지식이다.

평균만 저장하지 않고 표준편차와 표본수를 함께 남긴다. 관찰자가 TAG 라고
확신해도 그 라벨 안의 분산이 크면 개념을 단정할 수 없어야 하기 때문이다.

캘리브레이션 시드는 게임 시드와 분리한다.
"""
import sys, os, json, random, statistics, collections

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import persona as PS   # noqa: E402

CALIB_SEED = 20260904          # 게임 시드와 분리
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   '..', 'style_prior.json')

# 관찰자가 머릿속에 갖는 스타일 범주. persona.label 은 STUDIED_ 접두사와
# _TILTY 접미사를 붙이는데, 관찰자는 그렇게까지 세분해서 보지 않는다.
BASE = ('TAG', 'LAG', 'NIT', 'STATION', 'MANIAC', 'FISH',
        'ROCK', 'LOOSE_REG', 'TAG_TIGHT', 'TAG_AGGRO')


def base_style(label):
    if not label:
        return None
    s = label
    if s.startswith('STUDIED_'):
        s = s[len('STUDIED_'):]
    if s.endswith('_TILTY'):
        s = s[:-len('_TILTY')]
    return s if s in BASE else None


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    rng = random.Random(CALIB_SEED)
    buckets = collections.defaultdict(lambda: collections.defaultdict(list))
    made = 0
    for i in range(n):
        # 필드 품질을 넓게 흔들어야 한 종류의 대회에 치우치지 않는다.
        q = 0.30 + 1.00 * rng.random()
        p = PS.make_player(rng, field_quality=q, pid=i)
        st = base_style(p.get('type'))
        if not st:
            continue
        made += 1
        for k, v in (p.get('concepts') or {}).items():
            buckets[st][k].append(v)

    out = {}
    for st, cs in buckets.items():
        rec = {}
        for k, vals in cs.items():
            if len(vals) < 30:
                continue
            rec[k] = {'mean': round(statistics.mean(vals), 2),
                      'sd': round(statistics.pstdev(vals), 2),
                      'n': len(vals)}
        if rec:
            out[st] = rec

    with open(OUT, 'w') as f:
        json.dump({'seed': CALIB_SEED, 'samples': made, 'styles': out}, f,
                  ensure_ascii=False, indent=1)

    print('생성 %d명 중 라벨 분류 %d명 → %s' % (n, made, os.path.basename(OUT)))
    print()
    print('%-12s %6s  %-22s %-22s' % ('스타일', '표본', 'range_read', 'bluff'))
    for st in sorted(out, key=lambda x: -out[x].get('range_read', {}).get('n', 0)):
        r = out[st].get('range_read', {})
        b = out[st].get('bluff', {})
        print('%-12s %6d  mean %.2f sd %.2f      mean %.2f sd %.2f'
              % (st, r.get('n', 0), r.get('mean', 0), r.get('sd', 0),
                 b.get('mean', 0), b.get('sd', 0)))


if __name__ == '__main__':
    main()


# ===================== 행동 서명 캘리브레이션 =====================
# STYLE_SIG(라벨별 '이렇게 행동할 것이다')는 벡터만으로는 안 나온다. 행동은
# 엔진을 통과해야 생기므로 실제로 돌려서 모은다.
#
# **게임 시드와 분리된 캘리브레이션 시드**를 쓴다. 테스트에 쓸 상대를
# 캘리브레이션에 넣으면 그 상대를 미리 본 셈이 된다.
CALIB_GAME_SEEDS = tuple(range(900001, 900001 + 34))
SIG_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..', 'style_sig.json')


def calibrate_behavior(hands_per=42):
    import tourney as T
    import statistics as _st
    rows = collections.defaultdict(lambda: collections.defaultdict(list))
    for sd in CALIB_GAME_SEEDS:
        t = T.Tournament(entries=60, seed=sd, fmt='standard', hero_seat=7)
        for _ in range(hands_per):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            stt = t.next_hand()
            g = 0
            while stt and not stt.get('done') and g < 250:
                stt = t.submit('fold')
                g += 1
        h = getattr(t.run, 'h', None)
        if h is None:
            continue
        lab = {}
        for seat, pr in (h.prof or {}).items():
            if pr.get('concepts'):
                key = 'T%s_%s' % (getattr(h, 'table_id', 0), seat)
                lab[key] = base_style(pr.get('type'))
        seen = {}
        for k, r in h.book.d.items():
            _o, tg = k.split('>')
            if tg in seen or tg not in lab or not lab[tg]:
                continue
            if r.get('hands', 0) < 18:
                continue
            seen[tg] = True
            hn = float(r['hands'])
            sig = {
                'vpip': r['vpip']/hn,
                'pfr': r['pfr']/hn,
                'cbet': (r['cbet']/r['cbet_opp']) if r.get('cbet_opp') else None,
                'ftb': (r['fold_to_bet']/r['facing_bet']) if r.get('facing_bet') else None,
                'aggr': (10.0*r['agg_actions']/max(1, r['agg_actions']+r['passive_actions']))
                        if (r.get('agg_actions') or r.get('passive_actions')) else None,
            }
            for kk, vv in sig.items():
                if vv is not None:
                    rows[lab[tg]][kk].append(vv)
    out = {}
    for st, cs in rows.items():
        rec = {}
        for kk, vals in cs.items():
            if len(vals) < 8:
                continue
            rec[kk] = {'mean': round(_st.mean(vals), 4),
                       'sd': round(max(0.02, _st.pstdev(vals)), 4),
                       'n': len(vals)}
        if rec:
            out[st] = rec
    with open(SIG_OUT, 'w') as f:
        json.dump({'seeds': list(CALIB_GAME_SEEDS), 'styles': out}, f,
                  ensure_ascii=False, indent=1)
    print('행동 서명 → %s' % os.path.basename(SIG_OUT))
    print('%-12s %6s %8s %8s %8s' % ('스타일', 'n', 'vpip', 'pfr', 'aggr'))
    for st in sorted(out, key=lambda x: -out[x].get('vpip', {}).get('n', 0)):
        v = out[st]
        print('%-12s %6d %8.3f %8.3f %8.2f'
              % (st, v.get('vpip', {}).get('n', 0),
                 v.get('vpip', {}).get('mean', 0),
                 v.get('pfr', {}).get('mean', 0),
                 v.get('aggr', {}).get('mean', 0)))
