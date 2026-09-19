#!/usr/bin/env python3
"""pcz × made 결합 반사실의 개입 범위 감사.

설계: CF_DESIGN_JOINT_SCOPE.md

기존 cf_joint.py의 Tournament/snapshot/play/arm 구현을 그대로 재사용한다.
plan.py는 수정하지 않는다.

주 질문:
  기준 실행에서 pcz 진입이 정확히 1회이고 그 진입이 465에 도달한 핸드에서,
  P / PM 팔이 기준의 (seat, street) 밖에 새로운 pcz 진입을 만드는가?
"""

import os
import sys
import copy
import json
import argparse
import collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TD = os.path.join(D, 'tools')

if D not in sys.path:
    sys.path.insert(0, D)
if TD not in sys.path:
    sys.path.insert(0, TD)

import cf_joint as J

PL = J.PL
TRACE = []


def hook(fn):
    """cf_joint.hook과 같은 판정 + 각 pcz 진입 위치 보존."""
    def w(*a, **k):
        st = fn(*a, **k)

        try:
            sm = (st or {}).get('street_made')
            ws = [
                x for x in ((st or {}).get('why') or [])
                if x.startswith('%s: ' % sm)
            ]

            if any(J.ENTER in x for x in ws):
                prof = (
                    k.get('profile')
                    or (a[4] if len(a) > 4 else None)
                )

                TRACE.append({
                    'key': id((prof or {}).get('concepts')),
                    'street': sm,
                    'reject': any(J.REJECT in x for x in ws),
                })

        except Exception:
            pass

        return st

    return w


def mapped(trace, pmap):
    out = []
    unmapped = 0

    for x in trace:
        seat = pmap.get(x['key'])

        if seat is None:
            unmapped += 1
            continue

        out.append({
            'seat': int(seat),
            'street': x['street'],
            'reject': bool(x['reject']),
        })

    return out, unmapped


def run(seeds, hands):
    all_arms = J.arms()

    # 설계대로 P-only 2팔 + PM 6팔만.
    V = {
        tag: fn
        for tag, fn in all_arms.items()
        if tag in J.P_ARMS
        or (
            '+' in tag
            and tag.split('+', 1)[0] in J.P_ARMS
        )
    }

    tags = list(V)

    nh = 0
    qualified = 0

    exc = collections.Counter()

    arm_replays = collections.Counter()
    target_present = collections.Counter()
    arm_extra_pairs = collections.Counter()
    arm_extra_entries = collections.Counter()
    arm_max_extra = collections.Counter()

    any_extra_hands = 0
    examples = []
    rows = []

    for sd in seeds:
        if nh >= hands:
            break

        t = J.T.Tournament(
            entries=40,
            start_stack=30000,
            hero_seat=7,
            seats=8,
            seed=sd,
            hands_per_level=12,
        )

        while nh < hands:
            try:
                snap = J.snapshot(t)
            except Exception:
                exc['snapshot 오류'] += 1
                break

            TRACE.clear()
            PL.make_plan = hook(J._ORIG)

            try:
                hh, log, ints, b0, a0, pmap = J.play(t)
            except Exception:
                PL.make_plan = J._ORIG
                exc['기준 실행 오류'] += 1
                break

            hits = list(TRACE)
            nh += 1

            rej = [x for x in hits if x['reject']]

            # 기존 cf_joint와 모집단 정의를 똑같이 유지.
            if len(hits) != 1:
                exc[
                    'pcz 진입 %s회'
                    % ('0' if not hits else '2+')
                ] += 1

            elif len(rej) != 1:
                exc['진입 1회이나 465 미도달'] += 1

            else:
                base_seat = pmap.get(hits[0]['key'])

                if base_seat is None:
                    exc['좌석 식별 실패'] += 1

                else:
                    qualified += 1

                    base_seat = int(base_seat)
                    base_street = hits[0]['street']
                    base_loc = (base_seat, base_street)

                    rec = {
                        'hash': hh,
                        'seed': sd,
                        'seat': base_seat,
                        'street': base_street,
                        'arms': {},
                    }

                    ok = True
                    hand_has_extra = False

                    for tag, fn in V.items():
                        t2 = copy.deepcopy(snap)

                        TRACE.clear()
                        PL.make_plan = hook(fn)

                        try:
                            h2, l2, i2, b2, a2, pmap2 = J.play(t2)
                        except Exception:
                            exc['반사실 실행 오류'] += 1
                            ok = False
                            break

                        if h2 != hh:
                            exc['핸드 hash 불일치'] += 1
                            ok = False
                            break

                        locs, unm = mapped(TRACE, pmap2)

                        if unm:
                            exc['반사실 좌석 식별 실패'] += unm

                        extras = [
                            x for x in locs
                            if (x['seat'], x['street']) != base_loc
                        ]

                        present = any(
                            (x['seat'], x['street']) == base_loc
                            for x in locs
                        )

                        arm_replays[tag] += 1

                        if present:
                            target_present[tag] += 1

                        if extras:
                            hand_has_extra = True
                            arm_extra_pairs[tag] += 1
                            arm_extra_entries[tag] += len(extras)
                            arm_max_extra[tag] = max(
                                arm_max_extra[tag],
                                len(extras),
                            )

                        rec['arms'][tag] = {
                            'entries': locs,
                            'extras': extras,
                            'target_present': present,
                        }

                    if ok:
                        rows.append(rec)

                        if hand_has_extra:
                            any_extra_hands += 1

                            if len(examples) < 12:
                                examples.append(rec)

            PL.make_plan = J._ORIG

            if getattr(t, 'busted_hero', False):
                break

            if sum(
                1 for s in t.seats
                if t.stacks[s] > 0
            ) < 2:
                break

        if (
            sd == seeds[0]
            or sd == seeds[-1]
            or (sd - seeds[0]) % 10 == 0
        ):
            print(
                '  seed %d  누적 핸드 %d  주 모집단 %d'
                % (sd, nh, qualified),
                flush=True,
            )

    PL.make_plan = J._ORIG

    return {
        'hands': nh,
        'qualified': qualified,
        'excluded': dict(exc),
        'tags': tags,
        'arm_replays': dict(arm_replays),
        'target_present': dict(target_present),
        'arm_extra_pairs': dict(arm_extra_pairs),
        'arm_extra_entries': dict(arm_extra_entries),
        'arm_max_extra': dict(arm_max_extra),
        'any_extra_hands': any_extra_hands,
        'examples': examples,
        'rows': rows,
    }


def report(r):
    print()
    print('# pcz × made 결합 반사실 개입 범위 감사')
    print('  설계 CF_DESIGN_JOINT_SCOPE.md')
    print('  핸드 %d   주 모집단 %d'
          % (r['hands'], r['qualified']))
    print('  제외 %s' % r['excluded'])
    print()

    print('## 팔별')
    print(
        '  %-10s %7s %9s %10s %10s %8s'
        % (
            '팔',
            'replay',
            '기준위치',
            '확장pair',
            '확장진입',
            '최대',
        )
    )

    for tag in r['tags']:
        print(
            '  %-10s %7d %9d %10d %10d %8d'
            % (
                tag,
                r['arm_replays'].get(tag, 0),
                r['target_present'].get(tag, 0),
                r['arm_extra_pairs'].get(tag, 0),
                r['arm_extra_entries'].get(tag, 0),
                r['arm_max_extra'].get(tag, 0),
            )
        )

    print()
    print(
        '  다른 seat/street 진입이 하나라도 생긴 주 모집단 핸드: %d / %d'
        % (r['any_extra_hands'], r['qualified'])
    )

    print()
    print('## 예시 — 최대 12핸드')

    if not r['examples']:
        print('  없음')
        return

    for x in r['examples']:
        print(
            '  hash %s  seed %s  기준 seat %s %s'
            % (
                str(x['hash'])[:8],
                x['seed'],
                x['seat'],
                x['street'],
            )
        )

        for tag in r['tags']:
            ex = x['arms'][tag]['extras']

            if ex:
                print(
                    '    %-10s %s'
                    % (tag, ex)
                )


def save_rows(rows, path):
    with open(path, 'w', encoding='utf-8') as fh:
        for r in rows:
            fh.write(
                json.dumps(r, ensure_ascii=False)
                + '\n'
            )

    print()
    print('  원자료 %d행 → %s' % (len(rows), path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='7000-7199')
    ap.add_argument('--hands', type=int, default=10000)
    ap.add_argument('--rows', default=None)
    a = ap.parse_args()

    lo, hi = (a.seeds.split('-') + [None])[:2]

    if hi:
        seeds = list(
            range(int(lo), int(hi) + 1)
        )
    else:
        seeds = [int(lo)]

    r = run(seeds, a.hands)

    if a.rows:
        save_rows(r['rows'], a.rows)

    report(r)


if __name__ == '__main__':
    main()
