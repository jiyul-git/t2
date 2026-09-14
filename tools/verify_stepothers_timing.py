#!/usr/bin/env python3
"""step_others 를 언제 돌리느냐가 결과를 바꾸는지 잰다.

  T2_BOT_LOG=0 python3 tools/verify_stepothers_timing.py --mode defer    [--entries 100] [--hands 12]
  T2_BOT_LOG=0 python3 tools/verify_stepothers_timing.py --mode prefetch

  **별도 실행 폴더에서 돌릴 것** (ui/tools/setup_run_dir.sh). new_game 을 부른다.

두 후보를 실제 live2 경로에서 현재 동작과 대조한다.

  prefetch  핸드가 딜된 직후의 덤프로 다른 테이블을 미리 돌린다.
            순서가 바뀐다 — 히어로 핸드가 tilt 을 쓰기 **전** 값으로 봇이 판단한다.
  defer     히어로 핸드까지 끝난 상태를 덤프로 저장했다가 다시 읽어 돌린다.
            순서는 그대로다. 저장·복원이 충실한지만 본다.

왜 순서가 문제가 되는가
  dynamics.py:70 의 Tilt 는 좌석 번호로만 키를 잡는다(str(seat)). 좌석 번호는
  테이블마다 1..8 로 겹치므로 **모든 테이블이 같은 틸트 슬롯을 공유한다.**
  히어로 핸드가 먼저 쓰고 다른 테이블 봇이 그 값을 읽으므로, 다른 테이블은
  히어로와 독립적이지 않다. 게임 규칙 때문이 아니라 키 설계 때문이다.
"""
import argparse, copy, json, os, sys

sys.path.insert(0, os.getcwd())


def run(mode, entries, hands, seed):
    import ui_view
    sys.modules['view'] = ui_view
    import fieldsim as FS, live2 as L

    snap = {'field': None, 'hand_no': None}
    rows = []
    _orig = FS.Field.step_others

    def patched(self, settle=True):
        cand = None
        if mode == 'defer':
            mid = L._dump(self)                       # 히어로 핸드까지 끝난 상태
            f2 = L._load_field(copy.deepcopy(mid)); f2.notes = list(self.notes)
            _orig(f2, settle)
            cand = L._dump(f2)
        elif snap['field'] is not None and snap['hand_no'] == self.hand_no:
            f2 = L._load_field(copy.deepcopy(snap['field'])); f2.notes = []
            _orig(f2, settle=False)                   # 핸드 딜 직후 상태에서
            cand = L._dump(f2)
        r = _orig(self, settle)
        if cand is not None:
            real = L._dump(self)
            c = {'hand': self.hand_no, 'stack': 0, 'prof': 0, 'tables': 0,
                 'tilt': 0, 'busted': 0}
            base = snap['field'] or real
            ht = base['players'][str(base['hero_pid'])]['table']
            for p in real['players']:
                if mode == 'prefetch' and base['players'][p]['table'] == ht:
                    continue                          # 프리페치는 다른 테이블만 담당
                a, b = cand['players'][p], real['players'][p]
                if a['stack'] != b['stack']: c['stack'] += 1
                if a['prof'] != b['prof']: c['prof'] += 1
            for t in real['tables']:
                if mode == 'prefetch' and int(t) == ht: continue
                if cand['tables'].get(t) != real['tables'][t]: c['tables'] += 1
            if cand.get('tilt') != real.get('tilt'): c['tilt'] = 1
            if cand.get('busted_order') != real.get('busted_order'): c['busted'] = 1
            rows.append(c)
        return r

    FS.Field.step_others = patched
    L.new_game(entries=entries, start_stack=30000, seed=seed)
    r = L.step(); n = 0
    while n < hands:
        v = r.get('view') or {}
        if r.get('done'):
            n += 1
            if n >= hands: break
            snap['field'] = None
            r = L.step()
            st = L.load()
            snap['field'] = copy.deepcopy(st['field'])
            snap['hand_no'] = st['field']['hand_no']
            continue
        if v.get('type') != 'decision': break
        if snap['field'] is None:
            st = L.load()
            snap['field'] = copy.deepcopy(st['field'])
            snap['hand_no'] = st['field']['hand_no']
        lg = v['legal']; me = [s for s in v['seats'] if s['hero']][0]
        a = ('check' if lg['check'] else
             ('call' if lg['call'] is not None and lg['call'] <= 0.25 * me['stack']
              else 'fold'))
        r = L.step(a, 0)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('defer', 'prefetch'), required=True)
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--hands', type=int, default=12)
    ap.add_argument('--seed', type=int, default=777)
    a = ap.parse_args()
    if not os.path.exists('UI_SERVER_DIR'):
        sys.exit('중단: 별도 실행 폴더에서 돌리세요 (ui/tools/setup_run_dir.sh). '
                 'new_game 이 진행 중인 게임을 덮어씁니다.')
    rows = run(a.mode, a.entries, a.hands, a.seed)
    tot = {k: sum(x[k] for x in rows) for k in ('stack', 'prof', 'tables', 'tilt', 'busted')}
    print('%s — entries %d, seed %d, %d핸드' % (a.mode, a.entries, a.seed, len(rows)))
    print('  스택 불일치         %d' % tot['stack'])
    print('  프로필 불일치       %d' % tot['prof'])
    print('  테이블 불일치       %d' % tot['tables'])
    print('  tilt 불일치 핸드    %d / %d' % (tot['tilt'], len(rows)))
    print('  busted_order 불일치 %d' % tot['busted'])
    bad = [x['hand'] for x in rows if x['stack']]
    if bad: print('  스택이 갈린 핸드: %s' % bad)
    print('\n판정: %s' % ('완전 일치 — 동작 보존' if sum(tot.values()) == 0
                        else '불일치 — 동작이 달라진다'))
    return 0 if sum(tot.values()) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
