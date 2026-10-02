#!/usr/bin/env python3
"""Canonical preflop state -> spot_key (the ONLY lookup key for T2 GTO results).

File paths, solver run ids, legacy spot_id strings and other arbitrary ids are never lookup keys. Every stored solution
(legacy or new) is keyed by spot_key(canonical_state(...)).

canonical_state(raw) normalises a game state description:
  - positions: canonical names by distance from the button (aliases mapped), table order
  - numbers: decimal strings, rounded to 1e-4 bb, no trailing zeros ("30", "2.5")
  - history: every preflop action before the hero's decision in table order; skipped players are inserted as folds
    (preflop nobody can pass without acting, so a skipped live player has folded); a raise to the full stack is "allin";
    a call / check carries no amount (it is determined by the state)
  - the hero must be the next player to act after the history
spot_key = "sk1:" + first 32 hex of sha256(canonical JSON, sorted keys, no spaces).
The key describes the game state only. Solver tree / action menu / abstraction / convergence belong to the solution
record (quality), so several solutions of one spot can coexist.
"""
import hashlib
import json
from decimal import ROUND_HALF_EVEN, Decimal

KEY_VERSION = 'sk1'
STATE_VERSION = 1
# canonical position names, table order, for N players (N = 2..9); BB-relative so 4-handed = CO BTN SB BB
_ORDER_FROM_BB = ['BB', 'SB', 'BTN', 'CO', 'HJ', 'LJ', 'MP', 'UTG1', 'UTG']
ALIASES = {'UTG+1': 'UTG1', 'UTG+2': 'MP', 'EP': 'UTG', 'EP1': 'UTG', 'EP2': 'UTG1', 'MP1': 'MP', 'MP2': 'LJ', 'MP3': 'HJ',
           'BU': 'BTN', 'BUTTON': 'BTN', 'D': 'BTN', 'SMALL_BLIND': 'SB', 'BIG_BLIND': 'BB'}
ACTIONS = {'fold', 'check', 'call', 'raise', 'allin'}
ANTE_MODELS = {'none', 'per_player', 'bb_ante', 'uniform_total'}   # uniform_total: total amount_bb split equally over hand_start_players


def positions(n):
    if not 2 <= n <= 9:
        raise ValueError(f'table players {n} not supported')
    if n == 2:
        return ['SB', 'BB']   # heads-up: SB is the button and acts first preflop
    return list(reversed(_ORDER_FROM_BB[:n]))


def num(x):
    d = Decimal(str(x)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_EVEN).normalize()
    s = format(d, 'f')
    return '0' if s in ('-0', '') else s


def pos_name(p, table):
    q = ALIASES.get(str(p).upper().replace(' ', ''), str(p).upper())
    if q not in table:
        raise ValueError(f'position {p!r} not at a {len(table)}-handed table {table}')
    return q


def canonical_state(raw):
    """raw: {'table_players', 'hero', 'stacks_bb' (number or {pos: number}), 'blinds_bb' {'sb','bb'}, 'ante' {'model','amount_bb'},
    'history' [{'pos','act','to_bb'?}], 'format' ('MTT'|'cash'), 'icm' (None|'none'|{...}), 'rake' {'pct','cap_bb'}, 'variant', 'street'}"""
    # table_players IS hand_start_players: the seats dealt in at the start of the hand. A 4-seat continuation of a 9-max
    # hand is a 9-player state whose history holds the 5 folds; it never shares a key with a 4-max hand.
    if 'hand_start_players' in raw and 'table_players' in raw and int(raw['hand_start_players']) != int(raw['table_players']):
        raise ValueError('hand_start_players and table_players disagree')
    n = int(raw.get('hand_start_players', raw.get('table_players')))
    table = positions(n)
    if raw.get('street', 'preflop') != 'preflop':
        raise ValueError('only preflop states are defined in state version 1')
    blinds = raw.get('blinds_bb', {'sb': 0.5, 'bb': 1.0})
    sb, bb = Decimal(num(blinds['sb'])), Decimal(num(blinds['bb']))
    if bb != 1:
        raise ValueError('amounts must be in big blinds (bb = 1)')
    ante = raw.get('ante') or {'model': 'none'}
    model = ante.get('model', 'none')
    if model not in ANTE_MODELS:
        raise ValueError(f'ante model {model!r}')
    amt = Decimal(num(ante.get('amount_bb', 0) or 0))
    if model == 'none':
        amt = Decimal(0)
    elif amt <= 0:
        raise ValueError('ante amount must be > 0 unless model is none')
    st = raw['stacks_bb']
    stacks = {p: Decimal(num(st)) for p in table} if not isinstance(st, dict) else {pos_name(p, table): Decimal(num(v)) for p, v in st.items()}
    if set(stacks) != set(table):
        raise ValueError('stacks_bb must cover every seat')
    hero = pos_name(raw['hero'], table)
    hist = _normalise_history(raw.get('history', []), table, stacks, sb, bb, hero)
    icm = raw.get('icm')
    icm = {'model': 'none'} if icm in (None, False, 'none', {}) else icm
    rake = raw.get('rake') or {}
    state = {
        'v': STATE_VERSION,
        'game': {'variant': raw.get('variant', 'NLHE'), 'format': raw.get('format', 'MTT'), 'street': 'preflop'},
        'table_players': n,
        'blinds_bb': {'sb': num(sb), 'bb': num(bb)},
        'ante': {'model': model, 'amount_bb': num(amt)},
        'stacks_bb': [[p, num(stacks[p])] for p in table],
        'icm': _canon_obj(icm),
        'rake': {'pct': num(rake.get('pct', 0)), 'cap_bb': num(rake.get('cap_bb', 0))},
        'history': hist,
        'hero': hero,
    }
    return state


def _canon_obj(o):
    if isinstance(o, dict):
        return {str(k): _canon_obj(v) for k, v in sorted(o.items())}
    if isinstance(o, (list, tuple)):
        return [_canon_obj(v) for v in o]
    if isinstance(o, bool) or o is None or isinstance(o, str):
        return o
    if isinstance(o, (int, float, Decimal)):
        return num(o)
    raise ValueError(f'unsupported value {o!r}')


def _normalise_history(history, table, stacks, sb, bb, hero):
    """replay preflop; insert folds for skipped live players; validate; return explicit canonical list."""
    n = len(table)
    put = {p: Decimal(0) for p in table}
    put[table[-2] if n > 2 else 'SB'] = min(sb, stacks[table[-2] if n > 2 else 'SB'])
    put['BB'] = min(bb, stacks['BB'])
    live = {p: True for p in table}
    allin = {p: put[p] >= stacks[p] for p in table}
    acted = {p: False for p in table}
    cur = max(put.values())
    min_raise = bb
    i = 0   # preflop: first to act is table[0] (UTG.. / SB heads-up)
    out = []

    def to_act(i):
        for k in range(n):
            p = table[(i + k) % n]
            if live[p] and not allin[p] and (not acted[p] or put[p] < cur):
                return (i + k) % n
        return None

    def take(idx, a):
        nonlocal cur, min_raise
        p = table[idx]
        act = a['act']
        if act == 'fold':
            live[p] = False
            out.append({'pos': p, 'act': 'fold'})
        elif act == 'check':
            if put[p] != cur:
                raise ValueError(f'{p} cannot check facing {cur}')
            out.append({'pos': p, 'act': 'check'})
        elif act == 'call':
            if put[p] >= cur:
                raise ValueError(f'{p} has nothing to call')
            put[p] = min(cur, stacks[p])
            allin[p] = put[p] >= stacks[p]
            out.append({'pos': p, 'act': 'allin' if allin[p] else 'call', **({'to_bb': num(put[p])} if allin[p] else {})})
        elif act in ('raise', 'allin'):
            to = stacks[p] if act == 'allin' else Decimal(num(a['to_bb']))
            if to > stacks[p]:
                raise ValueError(f'{p} raises to {to} above stack {stacks[p]}')
            if to <= cur and to < stacks[p]:
                raise ValueError(f'{p} raise to {to} not above current bet {cur}')
            full = to >= stacks[p]
            if to > cur:
                if to - cur >= min_raise:
                    min_raise = to - cur
                    for q in table:
                        if q != p:
                            acted[q] = acted[q] and put[q] >= to   # re-open action
                elif not full:
                    raise ValueError(f'{p} raise to {to} below the minimum raise')
                cur = to
            put[p] = to
            allin[p] = full
            out.append({'pos': p, 'act': 'allin' if full else 'raise', 'to_bb': num(to)})
        else:
            raise ValueError(f'unknown action {act!r}')
        acted[p] = True

    for a in history:
        a = dict(a)
        a['act'] = str(a['act']).lower()
        if a['act'] not in ACTIONS:
            raise ValueError(f"unknown action {a['act']!r}")
        p = pos_name(a['pos'], table)
        while True:
            j = to_act(i)
            if j is None:
                raise ValueError(f'{p} acts after the betting round is closed')
            if table[j] == p:
                break
            take(j, {'act': 'fold'})   # skipped live player folded
            i = (j + 1) % n
        take(j, a)
        i = (j + 1) % n
    while True:
        j = to_act(i)
        if j is None:
            raise ValueError('no decision left: betting round closed before the hero')
        if table[j] == hero:
            break
        take(j, {'act': 'fold'})
        i = (j + 1) % n
    if sum(1 for p in table if live[p]) < 2:
        raise ValueError('hand is over before the hero acts')
    return out


def canonical_json(state):
    return json.dumps(state, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def spot_key(state):
    """state must already be canonical (output of canonical_state); re-canonicalisation is checked."""
    return f'{KEY_VERSION}:' + hashlib.sha256(canonical_json(state).encode()).hexdigest()[:32]


def key_of(raw):
    st = canonical_state(raw)
    return spot_key(st), st


def label(state):
    """human-readable description; NOT a key."""
    h = ' '.join(f"{a['pos']}:{a['act']}{'@' + a['to_bb'] if 'to_bb' in a else ''}" for a in state['history'] if a['act'] != 'fold') or 'unopened'
    stacks = sorted({s for _, s in state['stacks_bb']})
    return (f"{state['game']['format']} {state['table_players']}-max {'/'.join(stacks)}bb ante={state['ante']['model']}:{state['ante']['amount_bb']} "
            f"| {h} | hero {state['hero']}")
