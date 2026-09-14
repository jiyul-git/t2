#!/usr/bin/env python3
"""틸트 감쇠가 **자기 프로필**을 쓰는지 직접 검증한다 (읽기 전용).

  python3 tools/verify_decay_profile.py --entries 100 --hands 12 --seed 777

방법
  dynamics.Tilt.on_hand_end 을 감싸서 매 호출의 (pid, 넘어온 프로필)을 기록하고,
  필드가 들고 있는 그 pid 의 진짜 프로필과 **객체 동일성**으로 대조한다.
  값 비교가 아니라 `is` 비교다 — 같은 사람의 프로필은 같은 객체여야 한다.

  엔진은 고치지 않는다. 이 파일 안에서만 감싼다.

판정
  default  프로필을 못 찾아 {} 로 감쇠한 호출 (사람마다 다른 회복 속도가 죽는다)
  wrong    다른 사람의 프로필로 감쇠한 호출 (있으면 안 된다)
"""
import argparse, json, os, sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--hands', type=int, default=12)
    ap.add_argument('--seed', type=int, default=777)
    a = ap.parse_args()

    import fieldsim as FS, dynamics as DY
    f = FS.Field(entries=a.entries, start_stack=30000, hero_pid=0, seed=a.seed)
    truth = {str(p['pid']): p['prof'] for p in f.players.values()}

    rec = {'calls': 0, 'default': 0, 'wrong': 0, 'ok': 0,
           'calls_active': 0, 'default_active': 0, 'wrong_active': 0,
           'ok_active': 0,
           'unknown_pid': 0, 'wrong_samples': [], 'default_samples': []}
    orig = DY.Tilt.on_hand_end

    def patched(self, pid, prof):
        rec['calls'] += 1
        # on_hand_end 은 level 이 0 이면 프로필을 보기 전에 돌아간다.
        # 그래서 '프로필이 실제로 쓰인 호출'만 따로 센다 — 이게 행동에
        # 영향을 줄 수 있는 유일한 부분이다.
        active = self._s(pid)['level'] > 0.0
        rec['calls_active'] += active
        t = truth.get(str(pid))
        if t is None:
            rec['unknown_pid'] += 1
        elif not prof:
            rec['default'] += 1
            rec['default_active'] += active
            if len(rec['default_samples']) < 5:
                rec['default_samples'].append(str(pid))
        elif prof is t:
            rec['ok'] += 1
            rec['ok_active'] += active
        else:
            rec['wrong'] += 1
            rec['wrong_active'] += active
            if len(rec['wrong_samples']) < 5:
                owner = next((k for k, v in truth.items() if v is prof), '?')
                rec['wrong_samples'].append({'pid': str(pid), '받은프로필주인': owner})
        return orig(self, pid, prof)

    DY.Tilt.on_hand_end = patched
    try:
        while f.remaining() > 1 and f.hand_no < a.hands:
            f.hand_no += 1
            f.advance_level()
            f.notes = []
            tb = f.tables.get(f.players[f.hero_pid]['table'])
            if tb is not None and tb.n() >= 2:
                f._play_table(tb)
            f.step_others()
    finally:
        DY.Tilt.on_hand_end = orig

    # 회복 속도가 실제로 사람마다 갈리는지도 같이 본다 (전원 기본값이면
    # 위 대조가 통과해도 의미가 없다)
    recs = sorted({round(DY._t(p, 'tilt_recovery'), 2) for p in truth.values()})
    rec['tilt_recovery_분포'] = [recs[0], recs[len(recs)//2], recs[-1]]
    rec['tilt_recovery_고유값수'] = len(recs)
    rec['tilt_상태키수'] = len(f.tilt.state)
    rec['entries'] = a.entries; rec['hands'] = a.hands; rec['seed'] = a.seed
    rec['판정'] = '통과' if (rec['wrong'] == 0 and rec['default'] == 0
                             and rec['unknown_pid'] == 0 and rec['ok'] > 0) else '실패'
    print(json.dumps(rec, ensure_ascii=False))


if __name__ == '__main__':
    main()
