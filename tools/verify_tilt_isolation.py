#!/usr/bin/env python3
"""Tilt 상태의 소유 단위를 좌석에서 사람(pid)으로 바꾼 변경의 검증.

  **별도 실행 폴더에서** (ui/tools/setup_run_dir.sh)
  T2_BOT_LOG=2 python3 <경로>/tools/verify_tilt_isolation.py --mode <검사>

검사
  single   단일 테이블 동일성. 테이블이 하나면 좌석과 사람이 1:1 이므로
           격리 수정이 동작을 바꾸면 안 된다. 아카이브 해시를 찍는다.
  repeat   같은 시드로 두 번 돌려 재현되는지.
  leak     **격리 본검사.** 각 pid 의 shown 에 들어 있는 패가 정말 그 사람이
           쇼다운에서 깐 것인지 봇 핸드 기록과 대조한다. 좌석 키였을 때는
           다른 테이블 같은 좌석의 패가 섞여 들어간다.
  struct   tilt.state 의 키 형태와 개수.

각 모드는 JSON 한 줄을 찍는다. 바깥에서 옛 엔진과 대조하는 용도다.
"""
import argparse, hashlib, json, os, sys

sys.path.insert(0, os.getcwd())


def play(entries, hands, seed):
    import ui_view
    sys.modules['view'] = ui_view
    import live2 as L
    L.new_game(entries=entries, start_stack=30000, seed=seed)
    r = L.step(); n = 0
    while n < hands:
        v = r.get('view') or {}
        if r.get('done'):
            n += 1
            if n >= hands: break
            r = L.step(); continue
        if v.get('type') != 'decision': break
        lg = v['legal']
        me = [s for s in v['seats'] if s['hero']][0]
        a = ('check' if lg['check'] else
             ('call' if lg['call'] is not None and lg['call'] <= 0.25 * me['stack']
              else 'fold'))
        r = L.step(a, 0)
    return L.load()


def h(path):
    return (hashlib.sha256(open(path, 'rb').read()).hexdigest()
            if os.path.exists(path) else 'none')


def leak_check(st):
    """각 키의 shown 이 정말 그 사람의 패인가.

    봇 핸드 기록(bot_hands.jsonl, T2_BOT_LOG=2)에 좌석별 hole 과 seat->pid 가
    같이 남는다(fieldsim._log_bot_hand).

    히어로 테이블은 hand_archive2.jsonl 에 남는데 **seat->pid 매핑이 없다.**
    그래서 히어로 테이블 쇼다운에서 나온 패는 주인을 확정할 수 없다 —
    '남의 패'로 세면 안 되고 대조불가로 빼야 한다. (이걸 안 빼서 멀쩡한
    변경이 1건 누출로 잘못 나왔다.)
    """
    owned = {}          # pid -> 그 사람이 실제로 들고 있던 패들
    if os.path.exists('bot_hands.jsonl'):
        for line in open('bot_hands.jsonl'):
            if not line.strip(): continue
            rec = json.loads(line)
            pids = rec.get('pids') or {}
            for seat, hole in (rec.get('hole') or {}).items():
                pid = pids.get(str(seat))
                if pid is None: continue
                owned.setdefault(str(pid), []).append(tuple(hole))
    # 히어로 테이블 쇼다운에 나온 패 — 주인을 확정할 수 없다
    hero_shown = set()
    if os.path.exists('hand_archive2.jsonl'):
        for line in open('hand_archive2.jsonl'):
            if not line.strip(): continue
            rec = json.loads(line)
            res = rec.get('result') or {}
            if not res.get('showdown'): continue
            for hole in (res.get('hole') or {}).values():
                hero_shown.add(tuple(sorted(hole)))

    bad, checked, unknown = [], 0, 0
    for key, s in (st['field'].get('tilt') or {}).items():
        for hand in (s.get('shown') or []):
            if key not in owned or tuple(sorted(hand)) in hero_shown:
                unknown += 1              # 주인을 확정할 수 없는 것
                continue
            checked += 1
            if tuple(hand) not in owned[key]:
                bad.append({'key': key, 'hand': hand})
    return {'checked': checked, 'mismatch': len(bad), 'unverifiable': unknown,
            'samples': bad[:5]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('single', 'repeat', 'leak', 'struct'),
                    required=True)
    ap.add_argument('--entries', type=int, default=8)
    ap.add_argument('--hands', type=int, default=10)
    ap.add_argument('--seed', type=int, default=777)
    a = ap.parse_args()
    if not os.path.exists('UI_SERVER_DIR'):
        sys.exit('중단: 별도 실행 폴더에서 돌리세요. new_game 이 게임을 덮어씁니다.')

    st = play(a.entries, a.hands, a.seed)
    tilt = st['field'].get('tilt') or {}
    out = {'mode': a.mode, 'entries': a.entries, 'hands': a.hands, 'seed': a.seed,
           'archive': h('hand_archive2.jsonl'), 'bots': h('bot_hands.jsonl'),
           'field': hashlib.sha256(
               json.dumps(st['field'], sort_keys=True).encode()).hexdigest(),
           'tilt_keys': sorted(tilt)[:12], 'tilt_n': len(tilt),
           'tilt_key_mark': st['field'].get('tilt_key')}
    if a.mode == 'leak':
        out['leak'] = leak_check(st)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
