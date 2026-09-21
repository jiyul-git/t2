# -*- coding: utf-8 -*-
"""giveup intent 분해 분석. 읽기 전용 — 생산 코드를 수정하지 않는다."""
import json, os, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools'))
from logkeys import oop_of

# hand_archive2.jsonl 은 구형 포맷 — n_opp/made/range_adv/nut_adv 가 없어 제외
FILES = ['hand_archive2_alt.jsonl']
D = os.path.dirname(os.path.abspath(__file__))

rows = []
for f in FILES:
    for ln in open(os.path.join(D, f)):
        r = json.loads(ln)
        profs = r.get('profiles', {})
        for it in r.get('intents', []):
            if it.get('plan') != 'giveup':
                continue
            p = profs.get(str(it['seat']), {})
            mw = max(0, (it.get('n_opp') or 1) - 1)
            eq = it.get('eq') or 0.0
            made = it.get('made') or 0
            blk = it.get('blocker') or 0.0
            blkn = it.get('blocker_net') or 0.0
            nut = it.get('nut_adv') or 0.0
            behind = it.get('behind') or 0
            # 코드와 동일한 정의 (plan.py:440)
            has_sd = (made >= 1) or (eq >= 0.42 + 0.05 * mw)
            # 코드와 동일 (plan.py:297) — read_opponent 보정만 제외
            bo = (p.get('bluff', 5) / 10.0) * (0.5 + 1.8 * blk) \
                 * (0.75 + 0.35 * max(0.0, nut)) * (0.35 ** mw) \
                 * (0.55 ** min(behind, 3))
            bo *= max(0.45, min(1.65, 1.0 + 4.0 * blkn))
            rows.append(dict(
                f=f, hand=r['hand_no'], street=it['street'], seat=it['seat'],
                idx=it.get('idx'), typ=it.get('type'),
                rel=it.get('rel') or 0.0, eq=eq, made=made,
                radv=it.get('range_adv') or 0.0, nadv=nut,
                danger=it.get('danger') or 0.0, outs=it.get('outs') or 0,
                blk=blk, blkn=blkn, spr=it.get('spr'),
                n_opp=it.get('n_opp'), init=bool(it.get('init')),
                oop=oop_of(it), tocall=it.get('tocall') or 0,
                act=it.get('action'), has_sd=has_sd, bluff_ok=bo,
                why=' | '.join(it.get('why') or [])))

# 중복 제거 (완전 동일 레코드만)
seen, R = set(), []
for x in rows:
    k = (x['f'], x['hand'], x['street'], x['seat'], x['idx'], x['act'], x['tocall'])
    if k in seen:
        continue
    seen.add(k); R.append(x)

ACTS = ['check', 'bet', 'call', 'fold', 'raise']


def dist(g):
    c = Counter(x['act'] for x in g)
    return ' '.join('%s %-2d' % (a, c.get(a, 0)) for a in ACTS if c.get(a))


def table(title, keyfn, order=None):
    print('\n### %s' % title)
    g = defaultdict(list)
    for x in R:
        g[keyfn(x)].append(x)
    keys = order or sorted(g)
    print('%-26s %-5s %s' % ('구간', 'n', '행동'))
    for k in keys:
        if k not in g:
            continue
        print('%-26s %-5d %s' % (k, len(g[k]), dist(g[k])))


def band(v, cuts, labels):
    for c, l in zip(cuts, labels):
        if v < c:
            return l
    return labels[-1]


print('giveup intent 총 %d건 (중복 제거 후, 원본 %d)' % (len(R), len(rows)))
print('행동 전체:', dist(R))
print('tocall==0 %d건 / tocall>0 %d건'
      % (sum(1 for x in R if x['tocall'] == 0), sum(1 for x in R if x['tocall'] > 0)))

table('1. rel 구간', lambda x: band(x['rel'], [.15, .30, .45, .55, .70, 9],
      ['rel <.15', 'rel .15~.30', 'rel .30~.45', 'rel .45~.55', 'rel .55~.70', 'rel >=.70']),
      ['rel <.15', 'rel .15~.30', 'rel .30~.45', 'rel .45~.55', 'rel .55~.70', 'rel >=.70'])

table('2. eq 구간', lambda x: band(x['eq'], [.10, .25, .35, .42, .50, 9],
      ['eq <.10', 'eq .10~.25', 'eq .25~.35', 'eq .35~.42', 'eq .42~.50', 'eq >=.50']),
      ['eq <.10', 'eq .10~.25', 'eq .25~.35', 'eq .35~.42', 'eq .42~.50', 'eq >=.50'])

table('3. range_adv', lambda x: band(x['radv'], [-.20, -.05, .05, .20, 9],
      ['radv <-.20', 'radv -.20~-.05', 'radv -.05~+.05', 'radv +.05~+.20', 'radv >=+.20']),
      ['radv <-.20', 'radv -.20~-.05', 'radv -.05~+.05', 'radv +.05~+.20', 'radv >=+.20'])

table('4. nut_adv', lambda x: band(x['nadv'], [-.05, .05, .20, .50, 9],
      ['nadv <-.05', 'nadv -.05~+.05', 'nadv +.05~+.20', 'nadv +.20~+.50', 'nadv >=+.50']),
      ['nadv <-.05', 'nadv -.05~+.05', 'nadv +.05~+.20', 'nadv +.20~+.50', 'nadv >=+.50'])

table('5. made', lambda x: 'made %d' % x['made'])
table('6. showdown value (코드 정의 has_sd)',
      lambda x: 'has_sd True' if x['has_sd'] else 'has_sd False')
table('7. bluff_ok (리딩 보정 제외)',
      lambda x: band(x['bluff_ok'], [.05, .15, .30, .50, 9],
      ['bo <.05', 'bo .05~.15', 'bo .15~.30', 'bo .30~.50', 'bo >=.50']),
      ['bo <.05', 'bo .05~.15', 'bo .15~.30', 'bo .30~.50', 'bo >=.50'])
table('8. n_opp', lambda x: 'n_opp %s' % x['n_opp'])
table('9. initiative', lambda x: 'init %s' % x['init'])
table('10. oop 플래그', lambda x: 'oop %s' % ('없음' if x['oop'] is None else x['oop']))
table('부록. 생성 경로', lambda x: (
    '① eq>=pcz made 폴백' if '중간강도이나' in x['why'] else
    '③ 드로우 소멸/미스' if ('드로우 소멸' in x['why'] or '드로우 미스' in x['why']) else
    '④ 밸류 근거 붕괴' if '하락 →' in x['why'] else
    '② 쇼다운가치 없음' if '쇼다운 가치 없고' in x['why'] else
    '⑤ 분류 불가'))

# ---- 판단 상태 후보 군집 ----
print('\n\n### 판단 상태 후보 군집 (rel × has_sd × radv)')


def cluster(x):
    if x['rel'] < 0.30 and not x['has_sd']:
        return 'A 완전 약함'
    if x['has_sd'] and x['made'] >= 1:
        return 'B 메이드 쇼다운'
    if x['has_sd'] and x['made'] == 0 and x['rel'] >= 0.55:
        return 'C 강한 하이카드'
    if x['has_sd'] and x['made'] == 0:
        return 'D eq는 있으나 rel 낮음'
    return 'E 약하나 rel 있음'


g = defaultdict(list)
for x in R:
    g[cluster(x)].append(x)
print('%-22s %-4s %-9s %-9s %-9s %-9s %s'
      % ('군집', 'n', 'rel평균', 'eq평균', 'radv평균', 'nadv평균', '행동'))
for k in sorted(g):
    v = g[k]
    n = len(v)
    print('%-22s %-4d %-9.2f %-9.3f %-9.2f %-9.2f %s' % (
        k, n, sum(y['rel'] for y in v)/n, sum(y['eq'] for y in v)/n,
        sum(y['radv'] for y in v)/n, sum(y['nadv'] for y in v)/n, dist(v)))

print('\n--- C 군집 전수 ---')
for x in g.get('C 강한 하이카드', []):
    print('  h%-3s %-5s seat%-2s %-12s rel %.2f eq %.3f radv %+.2f nadv %+.2f n_opp %s init %s -> %s'
          % (x['hand'], x['street'], x['seat'], x['typ'], x['rel'], x['eq'],
             x['radv'], x['nadv'], x['n_opp'], x['init'], x['act']))
