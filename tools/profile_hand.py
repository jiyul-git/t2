#!/usr/bin/env python3
"""핸드 1회 처리의 실제 시간 구간을 잰다. 엔진을 수정하지 않고 monkeypatch 로만 건다.

  **별도 실행 폴더에서** (ui/tools/setup_run_dir.sh)
  T2_BOT_LOG=0 python3 <경로>/tools/profile_hand.py --entries 100 --hands 12

live2 의 한 요청은 이렇게 쪼개진다 (live2.py:152-256).

  step(action)
    load + _load_field          상태 로드
    build_hand                  play.Hand 재구성 + stamp
    run.start + run.send xN     **이번 핸드의 이전 액션을 매번 처음부터 재생한다**
    finish()                    마지막 액션에서만
      히어로 테이블 스택 반영     (측정 대상 아님, 거의 0)
      step_others               ★ 안 A 가 뒤로 미룰 수 있는 유일한 구간
      _collect_busts + _balance
      _dump + save
      _archive
      render_result

요청 종류
  deal  step(None)       다음 핸드를 딜한다
  mid   step(액션)        핸드가 안 끝난 액션
  end   step(액션)        핸드를 끝낸 액션 (finish 가 여기 들어 있다)
"""
import argparse, json, os, statistics as st, sys, time

sys.path.insert(0, os.getcwd())

ACC = {}
DEPTH = {}
def _acc(name, dt):
    a = ACC.setdefault(name, [0.0, 0]); a[0] += dt; a[1] += 1

def wrap(obj, name, label):
    """바깥쪽 호출만 센다.

    step_others 안의 _play_table 이 SE.HandRun.start 를 다시 부르므로,
    재진입을 막지 않으면 봇 테이블 시간이 run_start 로도 잡혀 이중 계상된다.
    """
    orig = getattr(obj, name)
    def w(*a, **k):
        if DEPTH.get(label):                 # 중첩 호출은 바깥 것에 이미 포함
            return orig(*a, **k)
        DEPTH[label] = 1
        t = time.perf_counter()
        try: return orig(*a, **k)
        finally:
            DEPTH[label] = 0
            _acc(label, time.perf_counter() - t)
    setattr(obj, name, w)
    return orig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--hands', type=int, default=12)
    ap.add_argument('--seed', type=int, default=777)
    ap.add_argument('--json')
    a = ap.parse_args()
    if not os.path.exists('UI_SERVER_DIR'):
        sys.exit('중단: 별도 실행 폴더에서 돌리세요. new_game 이 진행 중인 게임을 덮어씁니다.')

    import ui_view
    sys.modules['view'] = ui_view
    import fieldsim as FS, live2 as L, session as SE

    wrap(FS.Field, 'step_others', 'step_others')
    wrap(FS.Field, '_collect_busts', 'collect_busts')
    wrap(FS.Field, '_balance', 'balance')
    wrap(L, '_dump', 'dump')
    wrap(L, 'save', 'save')
    wrap(L, '_archive', 'archive')
    wrap(L, 'load', 'load')
    wrap(L, '_load_field', 'load_field')
    wrap(L, 'build_hand', 'build_hand')
    wrap(SE.HandRun, 'start', 'run_start')
    wrap(SE.HandRun, 'send', 'run_send')
    wrap(ui_view, 'render_result', 'render_result')

    recs = []
    def call(action, amount=0):
        ACC.clear(); DEPTH.clear()
        t = time.perf_counter()
        r = L.step(action, amount) if action is not None else L.step()
        tot = time.perf_counter() - t
        kind = 'deal' if action is None else ('end' if r.get('done') else 'mid')
        rec = {'kind': kind, 'total': tot,
               'sends': ACC.get('run_send', [0, 0])[1]}
        for k, (s, n) in ACC.items():
            rec[k] = s
        recs.append(rec)
        return r

    L.new_game(entries=a.entries, start_stack=30000, seed=a.seed)
    r = call(None)
    n = 0
    while n < a.hands:
        v = r.get('view') or {}
        if r.get('done'):
            n += 1
            if n >= a.hands: break
            r = call(None); continue
        if v.get('type') != 'decision': break
        lg = v['legal']; me = [s for s in v['seats'] if s['hero']][0]
        act = ('check' if lg['check'] else
               ('call' if lg['call'] is not None and lg['call'] <= 0.25 * me['stack']
                else 'fold'))
        r = call(act)

    if a.json:
        json.dump(recs, open(a.json, 'w'), ensure_ascii=False)

    def med(xs): return st.median(xs) if xs else 0.0
    print('entries %d, seed %d, %d핸드 — 요청 %d건\n' % (a.entries, a.seed, n, len(recs)))
    PHASES = ['load', 'load_field', 'build_hand', 'run_start', 'run_send',
              'step_others', 'collect_busts', 'balance', 'dump', 'save',
              'archive', 'render_result']
    for kind in ('deal', 'mid', 'end'):
        g = [x for x in recs if x['kind'] == kind]
        if not g: continue
        print('[%s] %d건   요청 전체 중앙 %.2f초  최대 %.2f초'
              % (kind, len(g), med([x['total'] for x in g]),
                 max(x['total'] for x in g)))
        for p in PHASES:
            vs = [x.get(p, 0.0) for x in g]
            if max(vs) < 0.002: continue
            print('      %-14s 중앙 %6.3f초   최대 %6.3f초   (요청의 %4.1f%%)'
                  % (p, med(vs), max(vs),
                     100 * med(vs) / max(1e-9, med([x['total'] for x in g]))))
        print('      %-14s 중앙 %d회' % ('run_send 횟수', med([x['sends'] for x in g])))
        print()

    end = [x for x in recs if x['kind'] == 'end']
    deal = [x for x in recs if x['kind'] == 'deal']
    if end:
        so = med([x.get('step_others', 0.0) for x in end])
        tot = med([x['total'] for x in end])
        print('안 A 로 미룰 수 있는 구간 = step_others')
        print('  핸드 종료 요청 중앙 %.2f초 중 %.2f초 (%.0f%%)' % (tot, so, 100*so/max(1e-9, tot)))
        print('  미룬 뒤 남는 임계 경로: 종료 요청 %.2f초 + 다음 딜 %.2f초 = %.2f초'
              % (tot - so, med([x['total'] for x in deal]), tot - so + med([x['total'] for x in deal])))
        print('  숨길 수 있는 시간의 상한 = 결과 화면 표시부터 다음 핸드 클릭까지의 시간')
    return 0


if __name__ == '__main__':
    sys.exit(main())
