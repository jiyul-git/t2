#!/usr/bin/env python3
"""행동 지문. 엔진 변경이 봇의 행동을 바꿨는지 한 숫자로 대조한다.

  python3 tools/fingerprint.py --seed 3000            # 한 시드
  python3 tools/fingerprint.py --seeds 3000-3005      # 합본 지문

**반드시 격리 폴더에서 돌린다** (ui/tools/setup_run_dir.sh). new_game 이
진행 중인 게임 상태를 덮어쓴다.

레시피 — 이걸 바꾸면 과거 지문과 대조가 끊긴다
  entries          100
  start_stack      30000
  hands_per_level  12
  핸드 수          시드당 30
  히어로 정책      콜 비용이 없으면 check, 있으면 fold. 그 외 없음
  서명 대상        히어로 테이블 아카이브(hand_archive2.jsonl) 레코드 최상위의
                   full_log 를
                   핸드 순서대로 이어붙인 것. 봇 테이블은 넣지 않는다
                   (T2_BOT_LOG 설정에 따라 달라지면 안 되므로)
  해시             시드별로 SHA-256, 합본은 "seed:sha256" 줄들의 SHA-256
  히어로 탈락      탈락하면 그 시드는 거기서 멈춘다 (탈락 후 step() 은 크래시).
                   per_seed 의 hands 로 드러난다

왜 히어로 테이블만인가
  봇 테이블 기록은 BOT_LOG 수준에 따라 내용이 달라진다. 지문은 실행 옵션에
  의존하면 안 된다.

주의
  INSTRUMENTATION_BASELINE.md 의 옛 지문(8f02a035...)은 이 도구로 만든 것이
  아니다. 그 레시피는 기록되지 않았다. 값끼리 비교하지 말 것.
"""
import argparse, hashlib, json, os, subprocess, sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RUNNER = r'''
import sys, os, json
sys.path.insert(0, os.getcwd())
os.environ.pop('T2_LIVE_STATE', None)
import live2 as L
seed = %r
n = %d
L.new_game(entries=100, start_stack=30000, seed=seed, hands_per_level=12)
r = L.step()
done = 0
while done < n:
    if r.get('done'):
        done += 1
        if r.get('busted') or done >= n:   # 탈락 후 step() 은 크래시한다
            break
        r = L.step()
        continue
    # view 가 아니라 raw 를 본다. view 모듈을 무엇으로 갈아끼워도
    # 지문이 달라지지 않아야 한다.
    raw = r.get('raw')
    if not isinstance(raw, dict) or 'tocall' not in raw:
        break
    r = L.step('check' if raw['tocall'] == 0 else 'fold')
print('__RUNNER_OK__')
'''


def one(seed, hands, workdir):
    src = os.path.join(workdir, '_fp_runner.py')
    with open(src, 'w') as fp:
        fp.write(RUNNER % (seed, hands))
    env = dict(os.environ)
    env['T2_BOT_LOG'] = '0'
    env.pop('T2_LIVE_STATE', None)
    for fn in ('hand_archive2.jsonl', 'bot_hands.jsonl',
               'live2_state.json', 'live2_state.json.bak'):
        p = os.path.join(workdir, fn)
        if os.path.exists(p):
            os.remove(p)
    out = subprocess.run([sys.executable, src], cwd=workdir, env=env,
                         capture_output=True, text=True)
    if '__RUNNER_OK__' not in out.stdout:
        raise RuntimeError('시드 %s 실행 실패:\n%s\n%s'
                           % (seed, out.stdout[-2000:], out.stderr[-2000:]))
    arch = os.path.join(workdir, 'hand_archive2.jsonl')
    logs, nh = [], 0
    with open(arch) as fp:
        for line in fp:
            if not line.strip():
                continue
            rec = json.loads(line)
            # full_log 는 레코드 **최상위**에 있다. rec['result'] 안에 있는 줄
            # 알고 result.full_log 를 읽었다가 전 시드가 같은 지문이 나왔다.
            logs.append(json.dumps(rec.get('full_log') or [],
                                   ensure_ascii=False, sort_keys=True))
            nh += 1
    blob = '\n'.join(logs)
    return {'seed': seed, 'hands': nh,
            'sha256': hashlib.sha256(blob.encode()).hexdigest()}, blob


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='3000-3005')
    ap.add_argument('--hands', type=int, default=30)
    a = ap.parse_args()
    if not os.path.exists(os.path.join(os.getcwd(), 'UI_SERVER_DIR')):
        sys.exit('중단: 격리 실행 폴더에서 돌리세요 (new_game 이 게임을 덮어씁니다).')
    if '-' in a.seeds:
        lo, hi = a.seeds.split('-'); seeds = list(range(int(lo), int(hi)+1))
    else:
        seeds = [int(x) for x in a.seeds.split(',')]

    per, blobs = [], []
    for s in seeds:
        # 같은 폴더에서 순서대로 돈다. one() 이 매번 아카이브·상태를 지운다.
        r, blob = one(s, a.hands, os.getcwd())
        per.append(r); blobs.append(blob)
        print(json.dumps(r, ensure_ascii=False), flush=True)
    # 합본은 **시드별 해시의 해시**다. 블롭을 이어붙이지 않는 이유: 시드 하나를
    # 다시 돌렸을 때 나머지를 재실행하지 않고 합칠 수 있어야 한다.
    total = hashlib.sha256('\n'.join('%d:%s' % (r['seed'], r['sha256'])
                                     for r in per).encode()).hexdigest()
    print(json.dumps({'seeds': a.seeds, 'hands_each': a.hands,
                      'per_seed': per, 'fingerprint': total},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
