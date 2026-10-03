#!/usr/bin/env python3
"""Pre-beta bug fixes: showdown visibility, 3bettor role, two-pair contribution.

S1  session.HandRun._finish observes showdown hands only after show/muck is
    decided, and only for shown seats (L163/L194 information leak).
T1  _was_3bettor counts full-raise events: an all-in call or a short (non-full)
    all-in after an open is not a 3bet; a full re-raise is (L049).
M1  bot.made_strength two pair = hero-involved pairs only (L-RA09):
    board pair + hero pair -> 1, board two pair + hero kicker -> 0,
    two hero pairs -> 2, pocket pair over board two pair -> 1.
"""
import inspect, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bot as BOT
import session as SE


def check_s1():
    src = inspect.getsource(SE.HandRun._finish)
    i_obs = src.index('observe_showdown(')
    i_shown = src.index('shown_seats = set()')
    loop = src[src.rfind('for sd in', 0, i_obs):i_obs]
    return {'pass': i_obs > i_shown and 'shown_seats' in loop and 'for sd in live' not in loop}


class _H:
    def __init__(self, metas):
        self.preflop_action_meta = metas


def check_t1():
    opn = {'seat': 1, 'action': 'raise', 'full_raise': True}
    cases = [
        ([opn, {'seat': 2, 'action': 'allin', 'full_raise': False, 'allin_call': True}], 2, False),
        ([opn, {'seat': 2, 'action': 'allin', 'full_raise': False}], 2, False),
        ([opn, {'seat': 2, 'action': 'raise', 'full_raise': True}], 2, True),
        ([opn, {'seat': 2, 'action': 'allin', 'full_raise': True}], 2, True),
        ([opn, {'seat': 2, 'action': 'raise', 'full_raise': True}], 1, False),
        ([opn, {'seat': 2, 'action': 'raise', 'full_raise': True},
          {'seat': 1, 'action': 'raise', 'full_raise': True}], 1, True),
        ([{'seat': 3, 'action': 'call'}, opn], 1, False),
    ]
    got = [SE.HandRun._was_3bettor(_H(m), s) for m, s, _ in cases]
    return {'pass': got == [e for _, _, e in cases], 'got': got}


def check_m1():
    cases = [
        (['Ah', '5d'], ['Kc', 'Ks', '5c'], 1),
        (['9h', '9d'], ['Kc', 'Ks', '5c'], 1),
        (['Ah', '2d'], ['Kc', 'Ks', '5c', '5h'], 0),
        (['Ah', '2d'], ['Kc', 'Ks', '5c', '5h', '3d'], 0),
        (['Ah', 'Ad'], ['Kc', 'Ks', '5c', '5h', '2d'], 1),
        (['Kh', '5d'], ['Kc', '7s', '5c'], 2),
        (['Kh', 'Qd'], ['Kc', '7s', '2c'], 1),
        (['9h', '8d'], ['6s', 'Ks', 'Kc'], 0),
        (['Kh', 'Kd'], ['Kc', '7s', '2c'], 3),
    ]
    got = [BOT.made_strength(h, b) for h, b, _ in cases]
    return {'pass': got == [e for _, _, e in cases], 'got': got}


def main():
    checks = {'S1_showdown_observes_shown_only': check_s1(),
              'T1_threebettor_full_raise_events': check_t1(),
              'M1_two_pair_hero_contribution': check_m1()}
    ok = all(v['pass'] for v in checks.values())
    print(json.dumps({'pass': ok, 'checks': checks}, indent=1))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
