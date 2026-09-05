"""STEP 2(기록 계층) 전후 비교. production 코드를 수정하지 않는다.

    python3 tools/log_baseline.py <출력파일>

확인 대상
  intent_src 의 표시 확률이 실제 반환 확률과 일치하는가
  저항 상황에서 최초 의도와 실제 대응이 구분되는가
  why 에 다른 스트리트 사유가 섞이는가
"""
import sys, os, json, re, collections
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import tourney as T   # noqa: E402

SEED, HANDS = 26001, 30
PCT = re.compile(r'\((\d+)%\)')


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'log_before.json'
    rows = []
    t = T.Tournament(entries=40, seed=SEED, fmt='standard', hero_seat=7)
    n = 0
    while n < HANDS:
        if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
            break
        st = t.next_hand()
        g = 0
        while st and not st.get('done') and g < 250:
            st = t.submit('fold')
            g += 1
        n += 1
        h = getattr(t.run, 'h', None)
        for i in (getattr(h, 'intents', None) or []):
            if i.get('street') == 'preflop':
                continue
            tr = [x for x in (i.get('trace') or [])
                  if x.get('kind') == 'aggression' and x.get('street') == i['street']]
            rows.append({
                'hand': n, 'street': i['street'], 'seat': i['seat'],
                'idx': i.get('idx'), 'action': i.get('action'),
                'tocall': i.get('tocall'),
                'intent_act': i.get('intent_act'),
                'response_act': i.get('response_act'),
                'intent_src': i.get('intent_src'),
                'p': (tr[0].get('p') if tr else None),
                'why': list(i.get('why') or []),
                'why_by_street': i.get('why_by_street'),
            })
    json.dump({'seed': SEED, 'rows': rows}, open(out, 'w'),
              ensure_ascii=False, indent=1)

    bad_pct = []
    for r in rows:
        m = PCT.search(r['intent_src'] or '')
        if m and r['p'] is not None:
            shown, real = int(m.group(1)), round(float(r['p']) * 100)
            if abs(shown - real) > 1 or shown > 97:
                bad_pct.append((r['hand'], r['street'], shown, real))
    resp = [r for r in rows if (r['tocall'] or 0) > 0]
    no_resp_field = sum(1 for r in resp if r.get('response_act') is None)
    mixed = 0
    for r in rows:
        pref = {'flop': 'flop:', 'turn': 'turn:', 'river': 'river:'}
        other = [w for w in r['why']
                 if any(w.startswith(p) for k, p in pref.items() if k != r['street'])]
        if other:
            mixed += 1
    print('%s  기록 %d건' % (os.path.basename(out), len(rows)))
    print('  확률 표시 불일치      %d건' % len(bad_pct))
    for b in bad_pct[:5]:
        print('     #%-3d %-6s 표시 %d%% vs 실제 %d%%' % b)
    print('  저항 상황            %d건 / response_act 없음 %d건'
          % (len(resp), no_resp_field))
    print('  why 에 타 스트리트 혼입 %d건' % mixed)
    print('  why_by_street 있음    %d건'
          % sum(1 for r in rows if r.get('why_by_street')))


if __name__ == '__main__':
    main()
