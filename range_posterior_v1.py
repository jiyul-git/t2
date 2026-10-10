"""Experimental, evidence-bounded action-conditional preflop posterior.

No new poker coefficients. The likelihood follows the EXISTING actor policy
(PF.open_entry_threshold/open_form, PF.defend_action_likelihoods/raise_form).
It is NOT a validated GTO prior. Only public event geometry and observer-
perceived profiles may be supplied; never the actor's actual hidden cards.
"""
import hashlib
import json
import math
import preflop as PF
import ranges as R


MODEL = 'observer_actor_policy_conditional_v1'


class _CaptureRoll:
    """Capture the Bernoulli threshold used by an existing actor policy."""
    def __init__(self):
        self.probability = None

    def __lt__(self, threshold):
        self.probability = float(threshold)
        return False


class _CaptureRng:
    def __init__(self):
        self.roll = _CaptureRoll()

    def random(self):
        return self.roll


def _form_prob(fn, *args, **kwargs):
    rng = _CaptureRng()
    act, _amount = fn(*args, rng=rng, **kwargs)
    if rng.roll.probability is None:
        return 1.0 if act == 'shove' else 0.0
    if not 0.0 <= rng.roll.probability <= 1.0:
        raise ValueError('actor Bernoulli probability out of bounds')
    return rng.roll.probability


def classify_public_action(action_meta, seat, bb, position,
                           stack_bb=None, seats=8, ante=True,
                           effective_stack_bb=None):
    """Classify the ACTUAL public action, not the response hero is facing.

    Missing monetary fields remain missing; never infer a stack from wager.
    raise_level=previous full raises, so facing an LJ open is level 1.
    """
    rows = list(action_meta or [])
    idxs = [i for i, m in enumerate(rows) if m.get('seat') == seat]
    if not idxs:
        return {'kind': 'unacted', 'source': 'public_action_meta'}
    i = idxs[-1]
    m, before = rows[i], rows[:i]
    full = [x for x in before if x.get('full_raise')]
    previous = full[-1] if full else None
    raised = bool(m.get('raised'))
    allin = bool(m.get('actor_allin_after'))
    if m.get('allin_call') or (m.get('action') == 'call' and allin):
        kind = 'call_allin'
    elif raised and not full:
        kind = 'first_in_shove' if allin else 'open_raise'
    elif raised and all(x.get('actor_allin_after') for x in full):
        kind = 'iso_over_shove'
    elif raised and len(full) == 1:
        kind = 'threebet_shove' if allin else 'threebet_raise'
    else:
        kind = 'other'
    last_idx = max((j for j, x in enumerate(before) if x.get('full_raise')),
                   default=-1)
    n_callers = sum(bool(x.get('allin_call') or
                         (x.get('action') == 'call' and not x.get('raised')))
                    for x in before[last_idx+1:]) if full else 0
    scale = float(bb)
    if scale <= 0:
        raise ValueError('bb must be positive')
    prev_total = (float(m.get('pre_current')) / scale
                  if m.get('pre_current') is not None else None)
    observed_total = (float(m.get('post_current')) / scale
                      if m.get('post_current') is not None else None)
    actor_stack = (float(m['pre_stack']) / scale
                   if m.get('pre_stack') is not None else
                   float(stack_bb) if stack_bb is not None else None)
    return {
        'kind': kind, 'source': 'public_action_meta',
        'actor_seat': seat, 'actor_pos': position,
        'opener_seat': previous.get('seat') if previous else None,
        'raise_level': len(full), 'n_callers': n_callers,
        'open_bb': prev_total, 'observed_total_bb': observed_total,
        'stack_bb': actor_stack,
        'effective_stack_bb': (float(effective_stack_bb)
                               if effective_stack_bb is not None else None),
        'seats': seats, 'ante': bool(ante),
        'actor_allin_after': allin,
        'action_history': [
            {'seat': x.get('seat'), 'action': x.get('action'),
             'raised': bool(x.get('raised')),
             'full_raise': bool(x.get('full_raise')),
             'actor_allin_after': bool(x.get('actor_allin_after')),
             'post_current': x.get('post_current')}
            for x in rows[:i+1]],
    }


def _defend_attack_form_prob(prof, pos, open_bb, n_callers, stack_bb,
                             level, exploit, hot):
    target = open_bb * (
        PF.reraise_mult(1 if hot else level, pos) + n_callers)
    pot = 1.5 + open_bb * (1 + n_callers)
    return _form_prob(
        PF.raise_form, prof, stack_bb, target, pot,
        exploit=exploit, level=(1 if hot else level),
        n_opp=1 + n_callers, facing_bb=open_bb)


def _first_in_likelihood(prof, combo, event, observer_context):
    stack = event['stack_bb']
    p = event['actor_pos']
    context = observer_context
    feel = PF.feel_of(
        prof, stack, context.get('field_avg_bb'), context.get('erosion'),
        context['field_q'], context['bubble_factor'])
    r = PF.legacy_preflop_order_percentile(list(combo))
    traits = PF._tr(prof)
    behind = context['behind_stacks_bb']
    thr = PF.open_entry_threshold(
        prof, p, stack, event['seats'], event['ante'], feel, traits,
        context.get('behind_reads'), behind)
    thr = PF.apply_money_open_threshold(
        thr, r, context.get('money_open'))
    if r > thr:
        return 0.0
    vs = (PF.PS.variance_seek(
        prof, context['tilt'], context['field_q'], stack,
        context['bubble_factor'], context['payout_flat'],
        context['reentry'], context['progress'])
          if prof.get('concepts') else 0.0)
    eff = min(stack, max(behind)) if behind else None
    shove_p = _form_prob(
        PF.open_form, prof, feel, r, stack,
        vs=vs, traits=traits, eff_bb=eff, pos=p)
    return shove_p if event['kind'] == 'first_in_shove' else 1.0-shove_p


def _threebet_likelihood(prof, combo, event, opener_pos, observer_context):
    stack = event['stack_bb']
    level = event['raise_level']
    o = event['open_bb']
    callers = event['n_callers']
    exploit = observer_context.get('opener_read')
    lik = PF.defend_action_likelihoods(
        prof, event['actor_pos'], opener_pos, list(combo),
        stack, o, callers, raise_level=level,
        stack_bb=stack, exploit=exploit,
        seats=event['seats'], ante=event['ante'],
        opener_allin=False, can_raise=True)
    if lik['calloff']:
        raise ValueError('generic 3bet was routed to calloff')
    hot = float(lik['hot_attack'])
    ordinary = float(lik['mixed_attack'])
    p_shove_hot = (
        _defend_attack_form_prob(prof, event['actor_pos'], o, callers,
                                 stack, level, exploit, True)
        if hot > 0 else 0.0)
    p_shove_mix = (
        _defend_attack_form_prob(prof, event['actor_pos'], o, callers,
                                 stack, level, exploit, False)
        if ordinary > 0 else 0.0)
    shove = hot*p_shove_hot + (1.0-hot)*ordinary*p_shove_mix
    nonshove = hot*(1.0-p_shove_hot) + (1.0-hot)*ordinary*(1.0-p_shove_mix)
    return shove if event['kind'] == 'threebet_shove' else nonshove


FIRST_IN_FIELDS = (
    'field_q', 'bubble_factor', 'tilt', 'payout_flat', 'reentry',
    'progress', 'behind_stacks_bb', 'erosion')
THREEBET_FIELDS = ('opener_pos',)


def conditioned_preflop_range(observer_profile, event, dead=(),
                              observer_context=None, prior=None):
    """P(combo | event, previous public history, observer estimates).

    Returns (weighted-posterior, metadata). Missing evidence: (None, meta)
    rather than silently substitute an RFI/normal-3bet/uniform polar range.
    No new weights/minimum floors/cutoffs are added.
    """
    event = dict(event or {})
    context = dict(observer_context or {})
    kind = event.get('kind')
    meta = {'source': MODEL, 'kind': kind, 'complete': False,
            'conditioned_on': ['previous_range', 'public_action_kind',
                               'public_action_history', 'bet_size',
                               'actor_stack', 'effective_stack'],
            'polar_weighting': 'actor_action_likelihood; no independent polar prior',
            'assumptions': ['observer-perceived profile, not hidden actor persona',
                            'actor-policy model is not calibrated GTO',
                            'bet-size density beyond shove/form is unavailable',
                            'effective stack recorded but legacy actor form uses actor stack'],
            'missing': []}
    allowed = ('first_in_shove', 'open_raise',
               'threebet_shove', 'threebet_raise')
    if kind not in allowed:
        meta['missing'] = ['action_class_not_supported']
        return None, meta
    if not isinstance(observer_profile, dict):
        meta['missing'].append('observer_perceived_profile')
    if event.get('stack_bb') is None or event.get('stack_bb', 0) <= 0:
        meta['missing'].append('public_actor_stack_bb')
    if event.get('observed_total_bb') is None:
        meta['missing'].append('observed_total_bb')
    if kind.startswith('threebet'):
        if event.get('raise_level') != 1:
            meta['missing'].append('unsupported_prior_action_depth')
        if event.get('open_bb') is None or event['open_bb'] <= 0:
            meta['missing'].append('previous_open_bb')
        if not context.get('opener_pos'):
            meta['missing'].append('opener_position')
    else:
        meta['missing'].extend(x for x in FIRST_IN_FIELDS if x not in context)
    if meta['missing']:
        return None, meta
    # All-in form corresponds to actor putting in their remaining stack.
    # If source includes both pre/post contribution, the exact relation is
    # checked by upstream action metadata. No additional sizing likelihood.
    full = R.weighted_range(prior if prior is not None else R.ALL)
    dead = set(dead or ())
    filtered = {c: w for c, w in full.items() if not (set(c) & dead)}
    out = {}
    for c, mass in sorted(filtered.items()):
        like = (_first_in_likelihood(observer_profile, c, event, context)
                if kind in ('first_in_shove', 'open_raise')
                else _threebet_likelihood(observer_profile, c, event,
                                          context['opener_pos'], context))
        if not math.isfinite(like) or not 0.0 <= like <= 1.0:
            raise ValueError(('invalid actor likelihood', c, like))
        if like > 0:
            out[c] = mass * like
    if not out:
        meta['missing'].append('zero_posterior_evidence')
        return None, meta
    meta.update({'complete': True, 'prior_support': len(filtered),
                 'prior_mass': sum(filtered.values()),
                 'posterior_support': len(out),
                 'posterior_mass': R.range_mass(out),
                 'range_signature': repr(R.range_signature(out))})
    return out, meta


def replay_record(ranges, metadata, layers=None, event_tag=None):
    """Lossless per-combo masses, metadata and MC provenance (opt-in only).

    Never round weights before serialization, never turn a dict into a list.
    Consumers can reconstruct the exact weighted sampling distribution.
    """
    records = {}
    for seat, pool in sorted((ranges or {}).items(), key=lambda x: str(x[0])):
        items = R.range_items(pool)
        payload = [[a, b, w] for (a, b), w in items]
        canonical = json.dumps(payload, separators=(',', ':'), allow_nan=False)
        records[str(seat)] = {
            'weights': payload, 'support': len(payload),
            'mass': sum(w for _, _, w in payload),
            'sha256': hashlib.sha256(canonical.encode()).hexdigest(),
            'source_metadata': (metadata or {}).get(seat, {}),
        }
    return {'schema': 1, 'event_tag': event_tag,
            'range_model': MODEL, 'opponents': records,
            'layer_sampling': list(layers or [])}
