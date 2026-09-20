#!/usr/bin/env python3
"""머니점프 자연상태 관측.

행동 로직은 바꾸지 않고 Field를 실제로 진행하면서 session이 남긴
money_jump_obs만 수집한다.

예:
  python3 tools/money_jump_observe.py --entries 100 --rounds 120 --seed 92020 \
      --out money_jump_obs.jsonl
"""
import argparse, collections, json, os, statistics, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS


def q(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    i = min(len(xs)-1, max(0, int((len(xs)-1)*p)))
    return xs[i]


def stage_key(r):
    rem = r.get('remaining')
    itm = r.get('itm')
    if not rem or not itm:
        return 'unknown'
    if rem <= 9:
        return 'final9'
    x = rem / itm
    if x > 1.50:
        return 'pre_1.5x+'
    if x > 1.20:
        return 'approach_1.2-1.5x'
    if x > 1.00:
        return 'bubble_1.0-1.2x'
    return 'itm'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--rounds', type=int, default=120,
                    help='필드 전체가 한 번씩 도는 라운드 수')
    ap.add_argument('--seed', type=int, default=92020)
    ap.add_argument('--fmt', default='standard')
    ap.add_argument('--out', default='money_jump_obs.jsonl')
    args = ap.parse_args()

    f = FS.Field(entries=args.entries, seed=args.seed, fmt=args.fmt)
    rows = []

    def capture(tb, h, run):
        for x in getattr(h, 'money_jump_obs', []) or []:
            y = dict(x)
            y['hand_no'] = f.hand_no
            y['table'] = tb.id
            rows.append(y)

    # 디스크 bot_hands 기록 대신 메모리로 관측만 모은다.
    f._log_bot_hand = capture

    for _ in range(args.rounds):
        if f.remaining() <= 1:
            break
        f.hand_no += 1
        f.advance_level()

        for tb in list(f.tables.values()):
            if tb.n() >= 2:
                f._play_table(tb)

        f._collect_busts()
        f._balance()

    with open(args.out, 'w', encoding='utf-8') as fp:
        for r in rows:
            fp.write(json.dumps(r, ensure_ascii=False) + '\n')

    print('=== money-jump natural-state observation ===')
    print('entries', args.entries, 'seed', args.seed,
          'rounds', f.hand_no, 'remaining', f.remaining())
    print('observations', len(rows), 'errors', len(f.errors))
    if f.errors:
        for e in f.errors[:5]:
            print('ERROR', e)

    by_stage = collections.Counter(stage_key(r) for r in rows)
    print('\n[stage counts]')
    for k in ('pre_1.5x+', 'approach_1.2-1.5x',
              'bubble_1.0-1.2x', 'itm', 'final9', 'unknown'):
        if by_stage[k]:
            print(' ', k, by_stage[k])

    vals = {
        'money_jump_skill': [r['money_jump_skill'] for r in rows],
        'stack_start_bb': [r['stack_start_bb'] for r in rows],
        'shorter_frac': [r['shorter_frac'] for r in rows],
        'players_yet_to_act': [r['players_yet_to_act'] for r in rows],
        'covers_yet_to_act': [r['covers_yet_to_act'] for r in rows],
        'covered_by_yet_to_act': [r['covered_by_yet_to_act'] for r in rows],
    }
    print('\n[quantiles p10 / p50 / p90]')
    for k, xs in vals.items():
        if xs:
            print(' %-24s %s / %s / %s' %
                  (k, q(xs, .10), q(xs, .50), q(xs, .90)))

    # 머니점프가 실제로 존재하는 관측만 대표 상황을 뽑는다.
    jump = [r for r in rows if (r.get('next_jump') or 0) > 0]
    print('\n[jump observations]', len(jump))
    if jump:
        close = sorted(
            jump,
            key=lambda r: (
                r.get('players_to_jump', 999),
                -r.get('shorter_frac', 0),
                r.get('stack_start_bb', 9999)
            )
        )[:12]
        for r in close:
            print(
                ' H%(hand_no)s T%(table)s %(street)s %(pos)s'
                ' rem=%(remaining)s/%(itm)s jump=%(next_jump)s'
                ' J=%(players_to_jump)s below=%(n_shorter)s'
                ' frac=%(shorter_frac)s stack=%(stack_start_bb)sbb'
                ' behind=%(players_yet_to_act)s'
                ' cover=%(covers_yet_to_act)s/%(covered_by_yet_to_act)s'
                ' skill=%(money_jump_skill)s act=%(action)s' % r
            )

    print('\nWROTE', args.out)
    return 1 if f.errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
