"""이상 행동 스캐너 — 확률 실행 모델을 반영한다. **진단 전용.**

    python3 tools/anomaly_scan.py [아카이브]

이전 스캐너는 `plan=value 인데 action=check` 를 곧바로 이상으로 잡았다.
그런데 실제 실행 로직은 확률이다(plan.attach_intent):

    p_aggr = decide_aggression(...)
    roll   = rng.random()
    if roll < p_aggr:  → 사이즈 계산 → size>0 이면 bet, size==0 이면 check
    else:              → check

따라서 `p=0.77, roll=0.85 → check` 는 **정상적인 확률 결과**다. 이걸 이상으로
잡으면 false positive 만 쌓인다(81핸드에서 6건이 전부 그랬다).

판정 기준
    roll >= p 인데 passive          정상 (확률 결과)
    roll <  p 인데 passive          이상 후보 — 다만 size==0 경로는 따로 분류
    p 없음                          판정 보류
    dev(계획 이탈) 기록 있음        정상 (규율 모델의 의도된 동작)

또한 p 자체가 낮아서 passive 가 예상되는 경우는 잡지 않는다.
"""
import sys, os, json, collections

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGG = ('bet', 'raise', 'allin')


def trace_of(rec, street):
    for t in (rec.get('trace') or []):
        if t.get('street') == street and t.get('kind') == 'aggression':
            return t
    return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        _ROOT, 'hand_archive2_alt.jsonl')
    rows = [json.loads(l) for l in open(path) if l.strip()]
    stat = collections.Counter()
    found = collections.defaultdict(list)

    for r in rows:
        for i in r.get('intents', []):
            if i.get('street') == 'preflop':
                continue
            act = i.get('action')
            if act is None:
                continue
            stat['총결정'] += 1
            tr = trace_of(i, i['street'])
            if not tr or tr.get('p') is None or tr.get('roll') is None:
                stat['판정보류(p/roll 없음)'] += 1
                continue
            p, roll = float(tr['p']), float(tr['roll'])
            # **p/roll 은 '선제로 칠 것인가'만 정한다.** 저항이 있으면(tocall>0)
            # decide_response 가 따로 콜/폴드/레이즈를 정하므로 이 규칙이
            # 적용되지 않는다. intent_act 가 bet 으로 남아 있는 것도 선제 기준
            # 값이라 비교 대상이 아니다. 이걸 놓쳐서 6건이 전부 오탐이었다.
            if (i.get('tocall') or 0) > 0:
                stat['저항 대면(별도 판단)'] += 1
                continue
            passive = act not in AGG
            if i.get('dev'):
                stat['계획이탈(기록됨)'] += 1
                continue
            if not passive:
                stat['공격(정상)'] += 1
                continue
            if roll >= p:
                stat['체크(확률 결과)'] += 1
                continue
            # roll < p 인데 passive — 벳을 시도했으나 안 나갔다
            src = (i.get('intent_src') or '')
            if '사이즈 0' in src or i.get('intent_size') in (0, 0.0):
                stat['체크(사이즈 0 경로)'] += 1
                found['사이즈 0 경로'].append(
                    (r['hand_no'], i['street'], i['seat'], i.get('type'),
                     round(i.get('rel') or 0, 2), p, roll, i.get('plan'), src[:40]))
            else:
                stat['이상(실행 불일치)'] += 1
                found['실행 불일치'].append(
                    (r['hand_no'], i['street'], i['seat'], i.get('type'),
                     round(i.get('rel') or 0, 2), p, roll, i.get('plan'), src[:40]))

    print('아카이브 %s (%d핸드)' % (os.path.basename(path), len(rows)))
    print()
    for k in ('총결정', '공격(정상)', '체크(확률 결과)', '체크(사이즈 0 경로)',
              '저항 대면(별도 판단)', '계획이탈(기록됨)', '이상(실행 불일치)',
              '판정보류(p/roll 없음)'):
        if stat[k]:
            print('  %-22s %d' % (k, stat[k]))
    for kind in ('실행 불일치', '사이즈 0 경로'):
        if not found[kind]:
            continue
        print()
        print('[%s] %d건' % (kind, len(found[kind])))
        print('  %-5s %-6s %-5s %-18s %5s %6s %6s %-14s %s'
              % ('핸드', '스트리트', '좌석', '퍼소나', 'rel', 'p', 'roll', '계획', '사유'))
        for e in found[kind][:20]:
            print('  #%-4d %-6s %-5s %-18s %5.2f %6.3f %6.3f %-14s %s' % e)


if __name__ == '__main__':
    main()
