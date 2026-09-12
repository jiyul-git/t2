#!/usr/bin/env python3
"""Tilt pid 격리 수정의 divergence 측정 드라이버 (읽기 전용).

  T2_BOT_LOG=2 python3 tools/verify_tilt_divergence.py run --entries 100 --seed 777 --cap 60 --out r.json
  python3 tools/verify_tilt_divergence.py cmp --old A.json --new B.json --old-bots a.jsonl --new-bots b.jsonl

왜 fieldsim 을 직접 부르는가
  live2 는 상태 파일과 아카이브를 건드린다. 여기서 보려는 것은 필드 전체의
  전개이지 히어로 세션이 아니다. field_pace.py 와 같은 방식으로 밖에서
  호출만 한다. 엔진은 수정하지 않는다.

히어로 자리도 봇이 친다. 두 엔진을 같은 조건으로 놓기 위한 것이고,
_play_table 은 히어로 테이블도 _log_bot_hand 를 거치므로 전 테이블의
full_log·intents·stacks 가 bot_hands.jsonl 에 남는다.
"""
import argparse, json, os, sys, time

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)


def run(entries, seed, cap, start_stack=30000, hands_per_level=12, progress=None):
    import fieldsim as FS
    f = FS.Field(entries=entries, start_stack=start_stack, hero_pid=0, seed=seed,
                 hands_per_level=hands_per_level)
    marks = {}
    todo = [('75%', max(1, int(round(entries*0.75)))), ('50%', max(1, int(round(entries*0.50)))),
            ('25%', max(1, int(round(entries*0.25)))), ('ITM', f.itm), ('최종1명', 1)]
    pace = []
    t0 = time.time()
    while f.remaining() > 1 and f.hand_no < cap:
        f.hand_no += 1
        f.advance_level()
        f.notes = []
        tb = f.tables.get(f.players[f.hero_pid]['table'])
        if tb is not None and tb.n() >= 2:
            f._play_table(tb)
        f.step_others()
        rem = f.remaining()
        pace.append([f.hand_no, f.level, rem, len(f.tables)])
        for name, thr in todo:
            if name not in marks and rem <= thr:
                marks[name] = {'hand': f.hand_no, 'level': f.level, 'remaining': rem}
        if progress and f.hand_no % 20 == 0:
            open(progress, 'w').write(json.dumps(
                {'hand': f.hand_no, 'remaining': rem, 'secs': round(time.time()-t0)}))
    alive = [p['pid'] for p in f.players.values() if p['stack'] > 0]
    return {'entries': entries, 'seed': seed, 'cap': cap,
            'end_hand': f.hand_no, 'end_remaining': f.remaining(),
            'level': f.level, 'itm': f.itm, 'marks': marks,
            'busted_order': list(f.busted_order),
            'alive': sorted(alive),
            'final_stacks': {str(p['pid']): p['stack'] for p in f.players.values()},
            'errors': len(f.errors), 'secs': round(time.time()-t0, 1),
            'pace': pace}


def load_bots(path):
    """hand_no -> table -> 레코드."""
    out = {}
    for line in open(path):
        if not line.strip(): continue
        r = json.loads(line)
        out.setdefault(r['hand_no'], {})[r['table']] = r
    return out


def _plans(rec):
    """intents 에서 계획 라벨만. intents 는 (스트리트, 좌석, 계획, ...) 형태의
    기록이라 구조를 가정하지 않고 통째로 문자열화해 비교한다."""
    return json.dumps(rec.get('intents') or [], ensure_ascii=False, sort_keys=True)


def cmp(old, new, ob, nb):
    a, b = json.load(open(old)), json.load(open(new))
    A, B = load_bots(ob), load_bots(nb)
    hands = sorted(set(A) | set(B))
    first = None
    n_div = n_plan = n_act = n_chip = 0
    per = []
    for hn in hands:
        ta, tb_ = A.get(hn, {}), B.get(hn, {})
        div_plan = div_act = div_chip = False
        for t in sorted(set(ta) | set(tb_)):
            ra, rb = ta.get(t), tb_.get(t)
            if ra is None or rb is None:
                div_plan = div_act = div_chip = True; continue
            if _plans(ra) != _plans(rb): div_plan = True
            if (ra.get('full_log') or []) != (rb.get('full_log') or []): div_act = True
            if ra.get('stacks') != rb.get('stacks') or ra.get('pot') != rb.get('pot'):
                div_chip = True
        if div_plan or div_act or div_chip:
            if first is None: first = hn
            n_div += 1
        n_plan += div_plan; n_act += div_act; n_chip += div_chip
        per.append([hn, int(div_plan), int(div_act), int(div_chip)])
    # 탈락 순서
    boa, bob = a['busted_order'], b['busted_order']
    first_bust_div = None
    for i in range(max(len(boa), len(bob))):
        x = boa[i] if i < len(boa) else None
        y = bob[i] if i < len(bob) else None
        if x != y:
            first_bust_div = {'idx': i, 'old': x, 'new': y}; break
    return {'hands': len(hands), 'first_divergence_hand': first,
            'divergent_hands': n_div,
            'divergence_ratio': round(n_div/max(1, len(hands)), 3),
            'plan_divergent_hands': n_plan, 'action_divergent_hands': n_act,
            'chip_divergent_hands': n_chip,
            'bust_count': [len(boa), len(bob)],
            'bust_order_first_diff': first_bust_div,
            'bust_order_identical': boa == bob,
            'end_remaining': [a['end_remaining'], b['end_remaining']],
            'alive_same': a['alive'] == b['alive'],
            'alive_old': a['alive'][:20], 'alive_new': b['alive'][:20],
            'marks_old': a['marks'], 'marks_new': b['marks'],
            'end_hand': [a['end_hand'], b['end_hand']],
            'per_hand': per[:200]}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--entries', type=int, default=100)
    r.add_argument('--seed', type=int, default=777)
    r.add_argument('--cap', type=int, default=60)
    r.add_argument('--hpl', type=int, default=12)
    r.add_argument('--out', required=True)
    r.add_argument('--progress')
    c = sub.add_parser('cmp')
    c.add_argument('--old', required=True); c.add_argument('--new', required=True)
    c.add_argument('--old-bots', required=True); c.add_argument('--new-bots', required=True)
    a = ap.parse_args()
    if a.cmd == 'run':
        out = run(a.entries, a.seed, a.cap, hands_per_level=a.hpl, progress=a.progress)
        open(a.out, 'w').write(json.dumps(out, ensure_ascii=False) + '\n')
        s = dict(out); s.pop('pace'); s.pop('final_stacks'); s['busted_order'] = len(out['busted_order'])
        print(json.dumps(s, ensure_ascii=False))
    else:
        print(json.dumps(cmp(a.old, a.new, a.old_bots, a.new_bots), ensure_ascii=False))


if __name__ == '__main__':
    main()
