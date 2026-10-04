#!/usr/bin/env python3
"""Verify concept difficulty, learning-support and hard-prerequisite caps."""

import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import persona as PS


def main():
    violations = []
    hard_max_gap = {('%s->%s' % e): -999.0 for e in PS.HARD_CONCEPT_PREREQUISITES}
    soft_max_gap = {k: -999.0 for k in PS.LEARNING_PREREQUISITES}
    difficulty_max_over = {k: -999.0 for k in PS.INDEPENDENT_CONCEPT_DIFFICULTY}
    samples = 0

    # 총 생성 수는 1,000명을 넘기지 않는다.
    field_samples = ((0.40, 333), (0.78, 334), (1.20, 333))
    pid_base = 0
    for qi, (fq, count) in enumerate(field_samples):
        rr = random.Random(20261005 + qi * 100003)
        for i in range(count):
            p = PS.make_player(rr, fq, pid=pid_base + i)
            c = p['concepts']
            latent = p['latent']
            capacity = max(0.0, min(10.0,
                0.60*float(latent['study']) + 0.40*float(latent['exp'])))
            samples += 1

            for concept in PS.ADVANCED_MASTERY_CONCEPTS:
                score = float(c[concept])
                difficulty = float(PS.INDEPENDENT_CONCEPT_DIFFICULTY[concept])
                # Reconstruct the maximum allowed post-compression score from
                # the final capacity.  Scores <= floor are always valid.
                readiness = max(0.0, min(1.0,
                    (capacity - (difficulty - PS.ADVANCED_MASTERY_WINDOW))
                    / PS.ADVANCED_MASTERY_WINDOW))
                readiness = readiness ** PS.ADVANCED_MASTERY_CURVE
                # The raw pre-compression score can be at most the general
                # difficulty cap, so this is a conservative final ceiling.
                general_cap = 10.0 - max(0.0, difficulty - capacity)
                mastery_cap = PS.ADVANCED_MASTERY_FLOOR + max(
                    0.0, general_cap - PS.ADVANCED_MASTERY_FLOOR) * readiness
                cap = max(PS.ADVANCED_MASTERY_FLOOR, mastery_cap)
                if score > cap + 0.21:
                    violations.append({
                        'kind': 'advanced_mastery', 'q': fq,
                        'pid': p.get('id'), 'concept': concept,
                        'capacity': capacity, 'score': score, 'cap': cap,
                    })

            for pre, post in PS.HARD_CONCEPT_PREREQUISITES:
                gap = float(c[post]) - float(c[pre])
                key = '%s->%s' % (pre, post)
                hard_max_gap[key] = max(hard_max_gap[key], gap)
                hard_limit = PS.HARD_PREREQ_MARGIN + PS.HARD_PREREQ_TAIL
                if gap > hard_limit + 0.11:
                    violations.append({
                        'kind': 'hard', 'q': fq, 'pid': p.get('id'),
                        'pre': pre, 'post': post, 'gap': gap,
                        'limit': hard_limit,
                    })

            for post, pres in PS.LEARNING_PREREQUISITES.items():
                vals = [float(c[x]) for x in pres]
                base = sum(vals) / len(vals)
                gap = float(c[post]) - base
                soft_max_gap[post] = max(soft_max_gap[post], gap)
                soft_limit = PS.LEARNING_SUPPORT_MARGIN + PS.LEARNING_SUPPORT_TAIL
                if gap > soft_limit + 0.11:
                    violations.append({
                        'kind': 'learning', 'q': fq, 'pid': p.get('id'),
                        'post': post, 'prereq_mean': base, 'gap': gap,
                        'limit': soft_limit,
                    })

            for concept, difficulty in PS.INDEPENDENT_CONCEPT_DIFFICULTY.items():
                cap = 10.0 - max(0.0, float(difficulty) - capacity)
                over = float(c[concept]) - cap
                difficulty_max_over[concept] = max(difficulty_max_over[concept], over)
                if over > 0.11:
                    violations.append({
                        'kind': 'difficulty', 'q': fq, 'pid': p.get('id'),
                        'concept': concept, 'difficulty': difficulty,
                        'capacity': capacity, 'score': c[concept], 'cap': cap,
                    })

            if len(violations) >= 20:
                break
        pid_base += count
        if len(violations) >= 20:
            break

    # Soft-cap helper invariants: unchanged inside margin, never raises a score,
    # monotone in raw downstream score, and no flat pile-up at the free-margin boundary.
    helper_checks = {}
    for name, margin, tail in (
            ('hard', PS.HARD_PREREQ_MARGIN, PS.HARD_PREREQ_TAIL),
            ('learning', PS.LEARNING_SUPPORT_MARGIN, PS.LEARNING_SUPPORT_TAIL)):
        up = 3.0
        raws = [up + margin - 0.5, up + margin,
                up + margin + 0.5, up + margin + 2.0, 10.0]
        outs = [PS._compress_dependency_gap(up, x, margin, tail) for x in raws]
        unchanged = (outs[0] == raws[0] and outs[1] == raws[1])
        never_raises = all(o <= r + 1e-12 for o, r in zip(outs, raws))
        monotone = all(b >= a - 1e-12 for a, b in zip(outs, outs[1:]))
        no_boundary_plateau = outs[2] > up + margin
        below_asymptote = all((o - up) < margin + tail + 1e-9
                              for o in outs[2:])
        helper_checks[name] = {
            'pass': unchanged and never_raises and monotone
                    and no_boundary_plateau and below_asymptote,
            'raws': raws, 'outputs': outs,
        }
        if not helper_checks[name]['pass']:
            violations.append({'kind': 'helper', 'name': name,
                               'detail': helper_checks[name]})

    # Same seed remains deterministic even though population retry paths may differ
    # from the pre-filter build.
    a = PS.make_player(random.Random(424242), 0.78, pid=77)
    b = PS.make_player(random.Random(424242), 0.78, pid=77)
    deterministic = (a == b)

    out = {
        'pass': not violations and deterministic,
        'samples': samples,
        'hard_margin': PS.HARD_PREREQ_MARGIN,
        'hard_tail': PS.HARD_PREREQ_TAIL,
        'learning_margin': PS.LEARNING_SUPPORT_MARGIN,
        'learning_tail': PS.LEARNING_SUPPORT_TAIL,
        'helper_checks': helper_checks,
        'hard_max_gap': hard_max_gap,
        'soft_max_gap': soft_max_gap,
        'difficulty_max_over_cap': difficulty_max_over,
        'violations': violations,
        'same_seed_deterministic': deterministic,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)


if __name__ == '__main__':
    main()
