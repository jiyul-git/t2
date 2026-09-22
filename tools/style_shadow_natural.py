#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STYLE_MODEL_V1 자연상태 안정성/예측력 측정.

production 판단은 수정하지 않는다.
fieldsim의 실제 다테이블 진행을 쓰되 모든 Hand가 같은 Book을 공유하게 해서
pid 기준 관찰 장부가 핸드를 넘어 누적되게 한다.

측정:
- 10/20/30/40 field-round 시점 posterior certainty/entropy/top1
- 연속 구간 top1 flip
- 20라운드 belief -> 21~40라운드 실제 행동 L/A/X 예측
  * style compression
  * population prior (5,5,1)
  * direct current L/A/X
"""
from __future__ import print_function

import argparse
import copy
import json
import math
import os
import random
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import play
import reads as RD
import session as SE

CUTS = (10, 20, 30, 40)
SCALES = (1.7, 1.7, 2.2)
POP = (5.0, 5.0, 1.0)


class MeasuredField(FS.Field):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.shared_book = RD.Book()

    def _play_table(self, tb, fast=True):
        alive = tb.alive()
        if len(alive) < 2:
            return None
        seats = list(range(1, len(alive)+1))
        profs = {str(i+1): alive[i]['prof'] for i in range(len(alive))}
        stacks = {i+1: alive[i]['stack'] for i in range(len(alive))}
        btn = seats[tb.button % len(seats)]
        sb, bb = self.blinds()
        try:
            h = play.Hand(seats, profs, stacks, btn, sb, bb, hero=None,
                          seed=self.rng.randrange(10**9), book=self.shared_book)
            h.seat_pid = {i+1: alive[i]['pid'] for i in range(len(alive))}
            h.table_id = tb.id
            self.stamp(h)
            run = SE.HandRun(h)
            run.start()
            for i in range(len(alive)):
                alive[i]['stack'] = int(h.stacks.get(i+1, alive[i]['stack']))
        except Exception as e:
            self.errors.append('%s: %s (table %s round %d)'
                               % (type(e).__name__, e, tb.id, self.hand_no))
            if FS.STRICT:
                raise
            return None
        tb.button = (tb.button + 1) % max(1, len(alive))
        tb.hands += 1
        return True


def _rate(r, num, den, prior):
    d = r.get(den, 0) or 0
    return (float(r.get(num, 0)) / d) if d else float(prior)


def raw_est(r):
    """Book counter 구간 하나를 observer noise/shrink 없이 est 형태로 변환."""
    hands = int(r.get('hands', 0) or 0)
    hn = float(max(1, hands))
    vpip = float(r.get('vpip', 0)) / hn
    pfr = float(r.get('pfr', 0)) / hn
    cbet = _rate(r, 'cbet', 'cbet_opp', RD.PRIOR['cbet'])
    barrel = _rate(r, 'barrel', 'barrel_opp', RD.PRIOR['barrel'])
    ftb = _rate(r, 'fold_to_bet', 'facing_bet', RD.PRIOR['fold_to_bet'])
    tb = _rate(r, 'pf_3bet', 'pf_3bet_opp', RD.PRIOR['pf_3bet'])
    fb = _rate(r, 'pf_4bet', 'pf_4bet_opp', RD.PRIOR['pf_4bet'])
    lmp = _rate(r, 'limp', 'limp_opp', RD.PRIOR['pf_limp'])
    rfi_rel = (float(r.get('rfi_did', 0)) / float(r.get('rfi_exp', 0.0))
               if float(r.get('rfi_exp', 0.0) or 0.0) > 0.02 else 1.0)
    aa = float(r.get('agg_actions', 0))
    pa = float(r.get('passive_actions', 0))
    agg_raw = aa / max(1.0, aa + pa)
    aggr_axis = max(1.0, min(10.0, 1.0 + 9.0 * agg_raw))

    sn = int(r.get('sz_n', 0) or 0)
    if sn >= 2:
        sm = float(r.get('sz_sum', 0.0)) / sn
        var = max(0.0, float(r.get('sz_sq', 0.0))/sn - sm*sm)
        ssd = var ** 0.5
    else:
        sm, ssd = RD.PRIOR['sz_mean'], RD.PRIOR['sz_sd']
    sbig = _rate(r, 'sz_big', 'sz_n', 0.15)

    return {
        'vpip': vpip, 'pfr': pfr, 'rfi_rel': rfi_rel, 'pf_limp': lmp,
        'pf_3bet': tb, 'pf_4bet': fb, 'aggr': aggr_axis,
        'cbet': cbet, 'barrel': barrel, 'ftb': ftb, 'bluff': RD.PRIOR['bluff'],
        'sz_mean': sm, 'sz_sd': ssd, 'sz_big': sbig,
        'confidence': 1.0 if hands else 0.0, 'n': hands,
    }


def delta_rec(a, b):
    """누적 counter b-a. 음수 불가, rate용 sum/count 전부 유지."""
    keys = set(a or {}) | set(b or {})
    out = {}
    for k in keys:
        va = (a or {}).get(k, 0)
        vb = (b or {}).get(k, 0)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            out[k] = vb - va
    return out


def entropy(probs):
    return -sum(p * math.log(max(p, 1e-300)) for p in probs.values())


def observer_profile(field, observer):
    try:
        return field.players[int(observer)]['prof']
    except Exception:
        return None


def style_for_pair(field, book_d, key, seed, cut):
    r = book_d.get(key)
    if not r or int(r.get('hands', 0) or 0) <= 0:
        return None
    obs, tgt = key.split('>')
    prof = observer_profile(field, obs)
    if prof is None:
        return None

    bk = RD.Book()
    bk.d = {key: copy.deepcopy(r)}
    rr = random.Random((int(seed) * 1000003 + int(obs) * 1009 + int(tgt) * 9176 + cut) & 0xffffffff)
    est = RD.perceived_profile(bk, obs, tgt, prof, rr)
    sh = RD.style_shadow(est)
    sh['_entropy'] = entropy(sh['probs'])
    return sh


def weighted_center(probs):
    L = A = X = 0.0
    for name, p in probs.items():
        lc, ac, xc = RD.STYLE_V1_CENTERS[name]
        L += p * lc
        A += p * ac
        X += p * xc
    return (L, A, X)


def sqerr(pred, actual):
    return sum(((pred[i] - actual[i]) / SCALES[i]) ** 2 for i in range(3)) / 3.0


def snapshot(field):
    return copy.deepcopy(field.shared_book.d)


def run(seed, rounds, entries):
    old = getattr(FS.Field, 'BOT_LOG', None)
    FS.Field.BOT_LOG = 0
    f = MeasuredField(entries=entries, seed=seed, fmt='standard')
    snaps = {}
    try:
        for rnd in range(1, rounds+1):
            if f.remaining() <= 8:
                break
            f.hand_no += 1
            f.advance_level()
            for tb in list(f.tables.values()):
                if tb.n() >= 2:
                    f._play_table(tb)
            f._collect_busts()
            f._balance()
            f.notes = []
            if rnd in CUTS:
                snaps[rnd] = snapshot(f)
    finally:
        if old is not None:
            FS.Field.BOT_LOG = old

    out = {
        'seed': seed,
        'rounds_done': max(snaps) if snaps else 0,
        'remaining': f.remaining(),
        'engine_errors': len(f.errors),
        'cuts': {},
        'flips': {},
        'prediction': {},
    }

    style_maps = {}
    for cut in CUTS:
        d = snaps.get(cut)
        if d is None:
            continue
        vals = {}
        tops = Counter()
        certs = []
        ents = []
        for key, rec in d.items():
            # 너무 적은 공동관찰은 안정성 통계에서 제외.
            if int(rec.get('hands', 0) or 0) < 4:
                continue
            sh = style_for_pair(f, d, key, seed, cut)
            if sh is None:
                continue
            vals[key] = sh
            tops[sh['top']] += 1
            certs.append(sh['certainty'])
            ents.append(sh['_entropy'])
        style_maps[cut] = vals
        out['cuts'][str(cut)] = {
            'pairs': len(vals),
            'mean_certainty': (sum(certs)/len(certs) if certs else 0.0),
            'mean_entropy': (sum(ents)/len(ents) if ents else 0.0),
            'top_counts': dict(tops),
        }

    for a, b in ((10,20),(20,30),(30,40)):
        aa, bb = style_maps.get(a, {}), style_maps.get(b, {})
        keys = sorted(set(aa) & set(bb))
        # 양쪽 모두 최소 4hand인 pair만 이미 style_maps에 존재.
        flips = sum(1 for k in keys if aa[k]['top'] != bb[k]['top'])
        out['flips']['%d-%d' % (a,b)] = {
            'pairs': len(keys),
            'flips': flips,
            'rate': flips/float(max(1, len(keys))),
            'mean_cert_delta': (
                sum(bb[k]['certainty'] - aa[k]['certainty'] for k in keys)/len(keys)
                if keys else 0.0),
            'mean_entropy_delta': (
                sum(bb[k]['_entropy'] - aa[k]['_entropy'] for k in keys)/len(keys)
                if keys else 0.0),
        }

    # 20라운드 belief -> 21~40 raw future L/A/X
    d20, d40 = snaps.get(20, {}), snaps.get(40, {})
    ss_style = ss_pop = ss_direct = 0.0
    n_pred = 0
    top_future = Counter()
    for key, sh20 in style_maps.get(20, {}).items():
        if key not in d40 or key not in d20:
            continue
        future = delta_rec(d20[key], d40[key])
        if int(future.get('hands', 0) or 0) < 6:
            continue
        actual_sh = RD.style_shadow(raw_est(future))
        actual = (actual_sh['L'], actual_sh['A'], actual_sh['X'])
        pred_style = weighted_center(sh20['probs'])
        pred_direct = (sh20['L'], sh20['A'], sh20['X'])
        ss_style += sqerr(pred_style, actual)
        ss_pop += sqerr(POP, actual)
        ss_direct += sqerr(pred_direct, actual)
        n_pred += 1
        top_future[actual_sh['top']] += 1

    rm_style = math.sqrt(ss_style/max(1,n_pred))
    rm_pop = math.sqrt(ss_pop/max(1,n_pred))
    rm_direct = math.sqrt(ss_direct/max(1,n_pred))
    out['prediction'] = {
        'pairs': n_pred,
        'rmse_style': rm_style,
        'rmse_population': rm_pop,
        'rmse_direct': rm_direct,
        'style_over_population': (rm_style/rm_pop if rm_pop else None),
        'style_over_direct': (rm_style/rm_direct if rm_direct else None),
        'pass_vs_population_0p90': bool(n_pred and rm_style <= 0.90*rm_pop),
        'pass_vs_direct_1p10': bool(n_pred and rm_style <= 1.10*rm_direct),
        'future_top_counts': dict(top_future),
        # pooled aggregate용 raw sums
        'ss_style': ss_style,
        'ss_population': ss_pop,
        'ss_direct': ss_direct,
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--rounds', type=int, default=40)
    ap.add_argument('--entries', type=int, default=100)
    a = ap.parse_args()
    out = run(a.seed, a.rounds, a.entries)
    print('STYLE_NATURAL_JSON=' + json.dumps(out, ensure_ascii=False, sort_keys=True))
    return 0 if out['engine_errors'] == 0 else 2


if __name__ == '__main__':
    raise SystemExit(main())
