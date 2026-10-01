"""균일 성향(전원 동일 퍼소나) 필드 시뮬레이션 + 판단 지표 측정. production 무변경.

  python3 tools/measure_uniform_playtest.py OUT.pkl 11,12,13 60   # 시뮬
  python3 tools/measure_uniform_playtest.py --analyze OUT.pkl      # 지표

퍼소나: latent study/aggro/exp = 5.0, 노이즈 없음 → 개념 = LOADING base,
기질 = 생성식 평균값. 성향 차이를 지우고 판단 로직 자체만 보기 위한 조건이다.
2026-10-01 계수 점검(DIAGNOSTICS_HISTORY.md)에 쓰였다.
"""
import os, sys, json, pickle
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['T2_BOT_LOG'] = '0'
import persona as PS
def uniform_player(rng=None, field_quality=0.6, pid=None, *a, **k):
    study = aggro = exp = 5.0
    c = {}
    for key, (ws, wa, we, base) in PS.LOADING.items():
        c[key] = round(PS._clamp(base), 1)
    c['money_jump'] = 3.6
    t = {'aggression': 5.0, 'looseness': 5.0, 'gamble': 5.0, 'tilt_prone': 4.8,
         'tilt_recovery': 5.0, 'discipline': 5.0, 'adaptability': 4.6,
         'consistency': 5.2, 'attention': 5.0, 'slowplay_taste': 5.0,
         'tilt_swing': 5.0, 'tilt_stack': 5.0}
    p = {'id': pid, 'concepts': c, 'temper': t,
         'latent': {'study': study, 'aggro': aggro, 'exp': exp}}
    p.update(PS.derive(p))
    if rng is not None:
        rng.random()  # keep rng stream advancing
    return p
PS.make_player = uniform_player
import plan as PL, fieldsim as FS
PF = []
_orig = PL.preflop_plan
def pf_wrap(ax, pos, hand, bbs, rng, **kw):
    r = _orig(ax, pos, hand, bbs, rng, **kw)
    fr = sys._getframe(1); h = fr.f_locals.get('h'); rnd = fr.f_locals.get('rnd')
    PF.append({'tid': getattr(h, 'table_id', None), 'hash': h.hash, 'seat': fr.f_locals.get('s'), 'pos': pos,
               'hand': list(hand), 'bbs': bbs, 'aggr_pos': kw.get('aggressor_pos'), 'open_bb': kw.get('open_bb'),
               'callers': kw.get('n_callers'), 'limpers': kw.get('n_limpers'), 'rlevel': kw.get('raise_level'),
               'tc': kw.get('to_call_bb'), 'pot': kw.get('pot_bb'), 'act': r[0], 'sz': r[1],
               'seed': {k: v for k, v in (r[2] or {}).items() if isinstance(v, (int, float, str, bool, type(None)))}})
    return r
PL.preflop_plan = pf_wrap
HANDS = []
def grab(self, tb, h, run):
    res = getattr(run, 'result', None) or {}
    HANDS.append({'hand_no': self.hand_no, 'tid': tb.id, 'hash': h.hash, 'bb': h.bb,
                  'full_log': res.get('full_log'), 'intents': getattr(h, 'intents', []),
                  'hole': {str(k): v for k, v in h.hole.items()}, 'board': res.get('board'),
                  'pos': {str(k): v for k, v in h.pos.items()}, 'start': {str(k): v for k, v in h._start_stacks.items()},
                  'end': {str(k): v for k, v in h.stacks.items()}, 'winners': res.get('winners'), 'how': res.get('how')})
FS.Field._log_bot_hand = grab
def run(seed, entries=90, cap=60):
    f = FS.Field(entries=entries, start_stack=30000, hero_pid=-1, seed=seed, hands_per_level=12)
    while f.remaining() > 1 and f.hand_no < cap:
        f.hand_no += 1; f.advance_level()
        for tid, tb in list(f.tables.items()):
            if tb.n() >= 2: f._play_table(tb)
        f._collect_busts(); f._balance(notify=False); f.notes = []
    return f
def analyze(path):
    import collections, statistics as S
    import preflop as P
    d = pickle.load(open(path, 'rb'))
    pf, hands = d['pf'], d['hands']
    print('hands', len(hands), 'pf decisions', len(pf))
    # 1. limp by hand band (unopened)
    un = [r for r in pf if r['seed'].get('pf_decision_kind') == 'unopened' and r['pos'] not in ('SB', 'BB')]
    band = collections.defaultdict(lambda: [0, 0])
    for r in un:
        p = P.pct(r['hand']); b = '<.25' if p < .25 else '.25-.5' if p < .5 else '>.5'
        band[b][0] += r['act'] == 'limp'; band[b][1] += 1
    print('1 LIMP rate by band:', {k: '%.3f (n=%d)' % (v[0]/v[1], v[1]) for k, v in band.items()})
    print('  open(raise) rate unopened non-blind: %.3f' % (sum(r['act'] in ('raise', 'shove') for r in un)/len(un)))
    # 2. defend fold of strong hands vs single open
    fo = [r for r in pf if r['seed'].get('pf_decision_kind') == 'face_first_open' and (r['callers'] or 0) == 0 and r['bbs'] > 40]
    for lo, hi in ((0, .03), (.03, .06), (.06, .10)):
        g = [r for r in fo if lo <= P.pct(r['hand']) < hi]
        if g: print('2 face open pct[%.2f,%.2f) n=%d fold=%.3f call=%.3f 3b=%.3f' % (lo, hi, len(g),
              sum(r['act'] == 'fold' for r in g)/len(g), sum(r['act'] == 'call' for r in g)/len(g), sum(r['act'] in ('3bet', 'shove') for r in g)/len(g)))
    # postflop
    I = [i for h in hands for i in (h['intents'] or [])]
    # 3. need vs true pot odds
    rat = []
    for i in I:
        tr = [t for t in (i.get('trace') or []) if t.get('street') == i['street'] and t.get('kind') == 'response']
        if not tr: continue
        t = tr[-1]
        if not t.get('tocall') or t.get('need') is None: continue
        true = t['tocall']/(t['pot']+t['tocall'])
        rat.append(t['need']/true)
    rat.sort()
    print('3 need/true n=%d  p10=%.2f p25=%.2f med=%.2f p75=%.2f p90=%.2f  frac<0.75=%.2f' % (len(rat), rat[len(rat)//10], rat[len(rat)//4], rat[len(rat)//2], rat[3*len(rat)//4], rat[9*len(rat)//10], sum(x < .75 for x in rat)/len(rat)))
    # 4. raises facing bets: made/rel
    rz = [i for i in I if i.get('response_kind') and i.get('action') in ('raise', 'allin') ]
    print('4 postflop raises facing bet n=%d' % len(rz))
    c = collections.Counter()
    for i in rz:
        tr = [t for t in (i.get('trace') or []) if t.get('street') == i['street'] and t.get('kind') == 'response']
        w = (tr[-1].get('why') or '')[:6] if tr else '?'
        c[(w, 'm%s' % i.get('made'), 'rel<.7' if (i.get('rel') or 0) < .7 else 'rel>=.7')] += 1
    for k, v in c.most_common(15): print('   ', k, v)
    # re-raise of a raise (backaction raise)
    rr = [i for i in rz if i.get('response_kind') == 'aggressor_backaction']
    print('   re-raises after being raised: n=%d, rel<.7: %d' % (len(rr), sum((i.get('rel') or 0) < .7 for i in rr)))
    # 5. calls facing a raise/check-raise with weak hands
    cr = [i for i in I if i.get('response_kind') in ('aggressor_backaction',) and i.get('action') == 'call']
    print('5 calls vs raise after own bet n=%d  m0=%d m1=%d rel<.4=%d  mean eq=%.2f' % (len(cr), sum(i.get('made') == 0 for i in cr), sum(i.get('made') == 1 for i in cr), sum((i.get('rel') or 0) < .4 for i in cr), S.mean([i.get('eq') or 0 for i in cr]) if cr else 0))
    # 6. pot_control bet rate
    pc = [i for i in I if i.get('plan') == 'pot_control' and not i.get('response_kind')]
    print('6 pot_control unopposed n=%d bet=%.3f' % (len(pc), sum(i.get('action') in ('bet',) for i in pc)/max(1, len(pc))))
    # 7. size shaping changed
    sh = [i for i in I if i.get('shape_changed') and i.get('calculated_target') and i.get('shaped_target')]
    big = [i for i in sh if i['shaped_target'] > 1.4*i['calculated_target'] or i['shaped_target'] < 0.7*i['calculated_target']]
    print('7 shaped n=%d, changed >40%%: %d' % (len(sh), len(big)))
    # 8. raise size relative to pot
    ms = []
    for i in rz:
        tr = [t for t in (i.get('trace') or []) if t.get('street') == i['street'] and t.get('kind') == 'response']
        if tr and tr[-1].get('pot'):
            t = tr[-1]; ms.append((i['amt'] - (i.get('hero_contrib') or 0) - t['tocall'])/(t['pot']+t['tocall']))
    if ms: ms.sort(); print('8 raise increment over call / pot-after-call: med=%.2f p90=%.2f' % (ms[len(ms)//2], ms[9*len(ms)//10]))
    # 9. showdown pot results: how often all-in with one pair

if __name__ == '__main__':
    if sys.argv[1] == '--analyze':
        analyze(sys.argv[2]); sys.exit(0)
    out = sys.argv[1]; seeds = [int(x) for x in sys.argv[2].split(',')]
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    for sd in seeds:
        f = run(sd, cap=cap)
        print('seed', sd, 'hands', len(HANDS), 'errors', len(f.errors), f.errors[:2])
    pickle.dump({'pf': PF, 'hands': HANDS}, open(out, 'wb'))
