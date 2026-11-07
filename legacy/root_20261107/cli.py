#!/usr/bin/env python3
"""액션만 입력받아 한 스텝씩 진행하는 대화형 래퍼.

  python cli.py

입력:
  ㅍ / ㅍㄷ / f      폴드
  ㅋ / c            콜
  ㅊ / ㅊㅋ / k      체크
  숫자 (예 2800)     벳/레이즈 — 총 투입 목표액. 콜비용이 있으면 raise, 없으면 bet
  ㅇ / allin / a    올인
  (엔터)            다음 진행 / 다음 핸드 딜
  q                 종료

판단 로직은 건드리지 않는다. live2.step() 을 그대로 호출할 뿐이다.
"""
import os, sys

D = os.path.dirname(os.path.abspath(__file__))
if D not in sys.path:
    sys.path.insert(0, D)

# 상태 파일을 지정하지 않았으면 claude_state.json 을 쓴다.
os.environ.setdefault('T2_LIVE_STATE', os.path.join(D, 'claude_state.json'))

import live2 as L

FOLD  = {'ㅍ', 'ㅍㄷ', 'f', 'fold', 'ㅗ'}
CALL  = {'ㅋ', 'c', 'call', 'ㅊ ', 'ㅁ'}
CHECK = {'ㅊㅋ', 'ㅊ', 'k', 'check', 'x'}
ALLIN = {'ㅇ', 'a', 'allin', 'shove', 'ㅇㄹ', '올인'}
QUIT  = {'q', 'quit', 'exit', 'ㅂ'}


def parse(s, tocall):
    """입력 문자열 -> (action, amount) 또는 None(그냥 진행) 또는 'QUIT'."""
    s = s.strip().lower()
    if s == '':
        return None
    if s in QUIT:
        return 'QUIT'
    if s in FOLD:
        return ('fold', 0)
    if s in CHECK:
        return ('check', 0)
    if s in CALL:
        return ('check', 0) if tocall <= 0 else ('call', 0)
    if s in ALLIN:
        return ('allin', 0)
    n = s.replace(',', '').replace('k', '000') if s.endswith('k') else s.replace(',', '')
    try:
        amt = int(n)
    except ValueError:
        return 'BAD'
    return ('raise', amt) if tocall > 0 else ('bet', amt)


def main():
    tocall = 0
    pending = None          # 다음 step 에 넘길 (action, amount)
    while True:
        try:
            r = L.step(*(pending if pending else (None, 0)))
        except Exception as e:
            print('\n[에러] %s: %s' % (type(e).__name__, e))
            break
        pending = None

        print()
        print(r['view'])

        raw = r.get('raw') or {}
        tocall = raw.get('tocall', 0) or 0

        if r.get('done'):
            # 핸드 종료. 엔터로 다음 핸드.
            try:
                s = input('\n[엔터=다음 핸드 / q=종료] ')
            except (EOFError, KeyboardInterrupt):
                print(); break
            if s.strip().lower() in QUIT:
                break
            continue

        if raw.get('error'):
            print('\n[규칙 위반] %s' % raw['error'])

        try:
            s = input('\n> ')
        except (EOFError, KeyboardInterrupt):
            print(); break

        p = parse(s, tocall)
        if p == 'QUIT':
            break
        if p == 'BAD':
            print('알 수 없는 입력. ㅍ/ㅋ/ㅊㅋ/숫자/ㅇ/엔터/q')
            pending = None
            # 같은 지점을 다시 보여준다
            continue
        pending = p

    print('저장됨: %s' % os.environ['T2_LIVE_STATE'])


if __name__ == '__main__':
    main()
