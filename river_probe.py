"""리버 판단 계측. live2 를 감싸서 봇의 리버 결정을 전부 남긴다.

아카이브가 사라져 원인 확정이 안 됐던 '플러시로 리버 체크' 건을 추적한다.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plan as PL

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'river_probe.jsonl')
_orig_agg = PL.decide_aggression
_orig_ref = PL.refresh


def _agg(profile, board, street, plan, rel, n_opp, oop, initiative,
         to_act_behind, rng, opp_est=None, outs=0, plan_state=None):
    p, why = _orig_agg(profile, board, street, plan, rel, n_opp, oop, initiative,
                       to_act_behind, rng, opp_est, outs, plan_state)
    if street == 'river':
        with open(LOG, 'a') as f:
            f.write(json.dumps({
                'type': profile.get('type'), 'aggr': profile.get('aggr'),
                'plan': plan, 'rel': round(rel, 3),
                'made': (plan_state or {}).get('made'),
                'eq': (plan_state or {}).get('eq'),
                'refreshed': (plan_state or {}).get('refreshed'),
                'street_made': (plan_state or {}).get('street_made'),
                'p_bet': round(p, 3), 'why': why,
                'board': board, 'oop': oop, 'init': initiative,
            }, ensure_ascii=False) + '\n')
    return p, why


def _ref(state, hero, board, opp_range, profile, pot, stack, street, n_opp=1,
         seed=None, opp_est=None):
    st = _orig_ref(state, hero, board, opp_range, profile, pot, stack, street,
                   n_opp, seed, opp_est)
    if street == 'river':
        with open(LOG, 'a') as f:
            f.write(json.dumps({
                'ev': 'refresh', 'plan_in': state.get('plan'),
                'plan_out': st.get('plan'),
                'rel_in': state.get('rel'), 'rel_out': st.get('rel'),
                'hero': hero, 'board': board,
            }, ensure_ascii=False) + '\n')
    return st


PL.decide_aggression = _agg
PL.refresh = _ref
