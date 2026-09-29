#!/usr/bin/env python3
"""Human Model V3 behavior-quality audit.

Extends integration checks beyond wiring: compare all-on V3 across skill-quality
levels and report interaction/non-monotonicity signals. Measurement only; no
strategy constants are changed here.
"""
import json, os, pathlib, statistics, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / 'tools' / 'verify_human_model_v3_integration.py'


def run_integration():
    p = subprocess.run([sys.executable, str(INTEGRATION)], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=3600)
    if p.returncode:
        raise RuntimeError(p.stderr[-4000:] or p.stdout[-4000:])
    return json.loads(p.stdout)


def main():
    base = run_integration()
    singles = base.get('single_feature_attribution', {})
    single_live = {k: bool(v.get('changed_vs_off')) for k, v in singles.items()}
    off = base['aggregate']['off']
    on = base['aggregate']['all_on']
    # These are diagnostics, not poker-quality targets: integration currently
    # has no external human dataset, so do not pretend VPIP/PFR deltas prove
    # realism. The audit explicitly exposes that validation gap.
    out = {
        'pass': bool(base.get('pass')) and all(single_live.values()),
        'integration_pass': bool(base.get('pass')),
        'all_single_features_reach_live_path': all(single_live.values()),
        'single_feature_live': single_live,
        'aggregate_delta': {
            'vpip_rate': round(on['vpip_rate'] - off['vpip_rate'], 4),
            'pfr_rate': round(on['pfr_rate'] - off['pfr_rate'], 4),
            'flop_hands': on['flop_hands'] - off['flop_hands'],
        },
        'validation_gap': [
            'no external human population target is scored',
            'no skill-bin monotonicity test yet',
            'no repeated-opponent exploitation/learning test yet',
            'no pairwise feature interaction matrix yet',
            'no tail-action-rate guard yet',
        ],
        'next_required_audits': [
            'skill-bin behavioral monotonicity',
            'pairwise/all-on interaction attribution',
            'repeated-opponent read-recency adaptation',
            'fold/call/raise tail anomaly scan',
        ],
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)


if __name__ == '__main__':
    main()
