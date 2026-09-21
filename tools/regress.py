"""리팩터 안전망.

같은 시드로 토너를 돌려 모든 액션을 이어붙인 뒤 SHA-256 지문을 낸다.
리팩터가 동작을 바꾸지 않았다면 지문이 완전히 같아야 한다.

  python3 tools/regress.py check                        # 현재 기준선과 대조
  python3 tools/regress.py check --baseline historical   # 과거 기준선과 대조
  python3 tools/regress.py check --baseline <파일경로>
  python3 tools/regress.py save                          # 현재 기준선 갱신
  python3 tools/regress.py list                          # 기준선 목록

기준선이 둘인 이유
------------------
`baseline_9max.json` 은 `7e40ba0` 에 동결된 **역사적** 기준이고, 봉인된
money-sizing Phase C(`024ab5b`, INCONCLUSIVE)가 서 있던 행동이다.
그 뒤 `0d202c5` 가 포스트플랍 포지션 술어를 **의도적으로** 고쳐 행동이
바뀌었다(시드 3003·3004). 즉 지금의 불일치는 결함이 아니라 의도된 변경이고,
낡은 것은 엔진이 아니라 기준선이다.

그래서 역사적 기준선을 덮어쓰지 않고 **분리**한다. 덮어썼다면 Phase C 가
어느 행동 위에서 나온 결과인지 가리키는 유일한 표식이 사라진다.
`save` 는 `historical` 을 **거부**한다 — 조용히 과거 기준을 잃지 않기 위해서다.

  baseline_9max.json           pre-OOP / Phase-C historical  (7e40ba0, 고정)
  baseline_9max_post_oop.json  post-OOP current behaviour    (0d202c5 이후)
"""
import sys, os, json, hashlib, collections, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import tourney as T

_D = os.path.dirname(os.path.abspath(__file__))

# 이름 -> (파일, 설명, 쓰기 가능한가)
BASELINES = collections.OrderedDict((
    ('current', (os.path.join(_D, 'baseline_9max_post_oop.json'),
                 'post-OOP 현재 행동 (0d202c5 이후)', True)),
    ('historical', (os.path.join(_D, 'baseline_9max.json'),
                    'pre-OOP / Phase-C 역사 기준 (7e40ba0 동결) — 덮어쓰기 금지', False)),
))
DEFAULT = 'current'

# 하위호환. 과거 코드가 이 이름을 참조한다.
BASE = BASELINES['historical'][0]

SEEDS = list(range(3000, 3006))
HANDS = 30


def resolve(name):
    """이름 또는 파일 경로 -> (경로, 설명, 쓰기 가능)."""
    if name in BASELINES:
        return BASELINES[name]
    return (name, '명시 경로', True)


def fingerprint():
    per_seed, stats = {}, collections.Counter()
    for sd in SEEDS:
        t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                         seed=sd, hands_per_level=200)
        rows = ['q=%.3f|a=%.2f' % (t.field_q, t.aggr_bias)]
        for _ in range(HANDS):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            guard = 0
            while st and not st.get('done') and guard < 200:
                st = t.submit('fold')
                guard += 1
            log = getattr(t.run, 'full_log', []) or []
            rows.append(';'.join('%s:%s:%s:%s' % x for x in log))
            seen = set()
            for (stt, x, a, _) in log:
                if stt != 'preflop' or x == t.hero or x in seen:
                    continue
                seen.add(x)
                stats['n'] += 1
                if a in ('bet', 'raise', 'allin'):
                    stats['vpip'] += 1
                    stats['pfr'] += 1
                elif a == 'call':
                    stats['vpip'] += 1
            stats['hands'] += 1
            if any(s == 'flop' for (s, _, _, _) in log):
                stats['flop'] += 1
            t.finish_hand()
        per_seed[sd] = hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:16]
    return per_seed, dict(stats)


def summarize(stats):
    n = max(1, stats.get('n', 0))
    h = max(1, stats.get('hands', 0))
    return ('VPIP %.1f%%  PFR %.1f%%  flop %.1f%%'
            % (100*stats.get('vpip', 0)/n, 100*stats.get('pfr', 0)/n,
               100*stats.get('flop', 0)/h))


def head_rev():
    """기록용. git 이 없거나 저장소가 아니면 None."""
    import subprocess
    try:
        out = subprocess.run(['git', '-C', _D, 'rev-parse', '--short', 'HEAD'],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except Exception:
        return None


def show_list():
    print('기준선')
    for name, (path, desc, writable) in BASELINES.items():
        mark = ' ' if writable else '*'
        exists = '있음' if os.path.exists(path) else '없음'
        print('  %s%-11s %-30s %-4s %s'
              % (mark, name, os.path.basename(path), exists, desc))
    print('  * = save 로 덮어쓸 수 없다')
    return 0


def main():
    ap = argparse.ArgumentParser(description='행동 지문 회귀 검사')
    ap.add_argument('cmd', nargs='?', default='check',
                    choices=['check', 'save', 'list'])
    ap.add_argument('--baseline', default=DEFAULT,
                    help="'current' / 'historical' / 파일 경로 (기본 current)")
    ap.add_argument('--note', default=None, help='save 에 남길 한 줄 메모')
    a = ap.parse_args()

    if a.cmd == 'list':
        return show_list()

    path, desc, writable = resolve(a.baseline)
    print('기준선 : %s  (%s)' % (os.path.basename(path), desc))

    if a.cmd == 'save':
        if not writable:
            print('거부 — 이 기준선은 덮어쓸 수 없다.')
            print('  %s 은 봉인된 Phase C(024ab5b)가 서 있던 행동이다.' % os.path.basename(path))
            print('  덮어쓰면 그 결과가 어느 코드에 대한 것이었는지 알 수 없게 된다.')
            print('  현재 행동을 갱신하려면: tools/regress.py save --baseline current')
            return 2
        fp, stats = fingerprint()
        rev = head_rev()
        json.dump({'fp': fp, 'stats': stats,
                   'rev': rev, 'note': a.note, 'seeds': SEEDS, 'hands': HANDS},
                  open(path, 'w'), indent=1)
        print('저장: %s  (rev %s)' % (path, rev or '-'))
        print(summarize(stats))
        return 0

    if not os.path.exists(path):
        print('기준선 파일이 없다: %s' % path)
        print('  먼저 실행: tools/regress.py save --baseline %s' % a.baseline)
        return 2
    old = json.load(open(path))
    fp, stats = fingerprint()
    bad = [s for s in fp if old['fp'].get(str(s)) != fp[s]]
    if old.get('rev'):
        print('  동결 rev %s%s' % (old['rev'],
                                   ('  — ' + old['note']) if old.get('note') else ''))
    print('기준선 : %s' % summarize(old['stats']))
    print('현재   : %s  (rev %s)' % (summarize(stats), head_rev() or '-'))
    if bad:
        print('불일치 시드: %s  → 동작이 바뀌었습니다.' % bad)
        if a.baseline == 'historical':
            print('  historical 대조에서의 불일치는 **예상된 것**이다 —')
            print('  0d202c5 가 포스트플랍 포지션 술어를 의도적으로 고쳤다.')
            print('  회귀 판정에는 --baseline current 를 쓸 것.')
        return 1
    print('전 시드 지문 일치 — 동작 보존 확인.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
