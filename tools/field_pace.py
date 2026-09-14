#!/usr/bin/env python3
"""엔트리 수가 대회 **구조**를 바꾸는지 재는 읽기 전용 측정 드라이버.

  python3 tools/field_pace.py --entries 45 --seed 1 [--cap 400] [--out x.json]

왜 필요한가
  블라인드 레벨은 히어로 핸드 수로만 오른다 (fieldsim.py:295,
  `1 + hand_no // hands_per_level`). 엔트리와 무관하다.
  반면 탈락 속도는 테이블 수에 좌우되는데, step_others 가 테이블 인원에 따라
  0/1/2 핸드를 돌리므로 (fieldsim.py:241-246) 단순히 entries/8 에 비례하지 않는다.
  그래서 '엔트리를 줄이면 같은 구조가 유지되는가'는 코드만 봐서는 못 정한다.

무엇을 재는가
  생존 75% / 50% / 25% / ITM / 최종 1명 에 도달한 **히어로 핸드 수와 그때의 레벨**.
  50% 와 ITM 이 핵심이다.

주의
  - 엔진을 수정하지 않는다. fieldsim 을 밖에서 호출만 한다.
  - 히어로도 봇으로 친다. 실제 게임의 히어로는 사람이지만, 여기서 보려는 것은
    필드가 줄어드는 속도와 레벨의 관계이지 히어로의 성적이 아니다.
  - live2 를 쓰지 않는다. 상태 파일·아카이브를 건드리지 않기 위해서다.
  - T2_BOT_LOG=0 으로 띄울 것. 봇 핸드 jsonl 기록이 꺼진다.
"""
import argparse, json, os, sys, time

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)


def run(entries, seed, cap, start_stack=30000, hands_per_level=12,
        itm_frac=0.15, fmt=None, max_secs=None, progress=None):
    import fieldsim as FS
    f = FS.Field(entries=entries, start_stack=start_stack, hero_pid=0, seed=seed,
                 hands_per_level=hands_per_level, itm_frac=itm_frac, fmt=fmt)
    # 생존 비율 기준점. ITM 은 인원수 기준이라 따로 둔다.
    frac_marks = [('75%', 0.75), ('50%', 0.50), ('25%', 0.25)]
    todo = [(n, max(1, int(round(entries * p)))) for n, p in frac_marks]
    todo.append(('ITM', f.itm))
    todo.append(('최종1명', 1))
    todo.sort(key=lambda x: -x[1])

    hit = {}
    hero_out = None
    t0 = time.time()
    tables_seen = []
    while f.remaining() > 1 and f.hand_no < cap:
        if max_secs and time.time() - t0 > max_secs:
            break
        f.hand_no += 1
        f.advance_level()
        f.notes = []
        tables_seen.append(len(f.tables))
        # 히어로 테이블도 한 핸드 돌린다. live2 에서는 사람이 치는 자리다.
        tb = f.tables.get(f.players[f.hero_pid]['table'])
        if tb is not None and tb.n() >= 2:
            f._play_table(tb)
        f.step_others()                      # 내부에서 _collect_busts + _balance
        rem = f.remaining()
        if hero_out is None and f.players[f.hero_pid]['stack'] <= 0:
            hero_out = {'hand': f.hand_no, 'level': f.level,
                        'rank': f.rank_of(f.hero_pid)}
        for name, thr in todo:
            if name not in hit and rem <= thr:
                hit[name] = {'hand': f.hand_no, 'level': f.level, 'remaining': rem}
        if progress and f.hand_no % 20 == 0:
            with open(progress, 'w') as fp:
                fp.write(json.dumps({'entries': entries, 'seed': seed,
                                     'hand': f.hand_no, 'remaining': rem,
                                     'level': f.level, 'marks': sorted(hit),
                                     'secs': round(time.time() - t0)},
                                    ensure_ascii=False))
    return {'entries': entries, 'seed': seed, 'itm': f.itm,
            'hands_per_level': hands_per_level,
            'marks': hit, 'hero_out': hero_out,
            'end_hand': f.hand_no, 'end_remaining': f.remaining(),
            'capped': f.hand_no >= cap,
            'timed_out': bool(max_secs and time.time() - t0 > max_secs),
            'avg_tables': round(sum(tables_seen) / max(1, len(tables_seen)), 2),
            'errors': len(f.errors), 'secs': round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, required=True)
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--cap', type=int, default=400)
    ap.add_argument('--hpl', type=int, default=12)
    ap.add_argument('--start-stack', type=int, default=30000)
    ap.add_argument('--out')
    ap.add_argument('--progress')
    ap.add_argument('--max-secs', type=int)
    a = ap.parse_args()
    r = run(a.entries, a.seed, a.cap, a.start_stack, a.hpl,
            max_secs=a.max_secs, progress=a.progress)
    s = json.dumps(r, ensure_ascii=False)
    if a.out:
        with open(a.out, 'w') as fp:
            fp.write(s + '\n')
    print(s)


if __name__ == '__main__':
    main()
