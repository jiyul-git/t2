#!/usr/bin/env python3
"""머니점프 문맥 계산의 경계값/동일상금 구간 회귀검사."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import context as CTX
import formats as FM


def close(a, b):
    return abs(float(a) - float(b)) < 1e-9


p = FM.payouts(15, 0.0)

# ITM 전: 현재 보장 0, 다음 점프는 min-cash.
x = CTX.money_jump_context(16, 15, p)
assert x['in_money'] is False, x
assert x['current_prize'] == 0.0, x
assert x['next_rank'] == 15, x
assert close(x['next_prize'], p[14]), x
assert close(x['next_jump'], p[14]), x
assert x['players_to_jump'] == 1, x

# 막 ITM: 15위 보장, 다음 실제 상금 증가까지의 거리를 계산.
x = CTX.money_jump_context(15, 15, p)
assert x['in_money'] is True, x
assert x['current_rank'] == 15, x
assert close(x['current_prize'], p[14]), x
assert x['next_rank'] == 14, x
assert close(x['next_prize'], p[13]), x
assert x['players_to_jump'] == 1, x

# 동일 상금 밴드: 한 등수가 아니라 실제 점프까지 건너뛴다.
band = [40.0, 25.0, 10.0, 10.0, 10.0, 5.0]
x = CTX.money_jump_context(5, 6, band)
assert x['current_rank'] == 5, x
assert close(x['current_prize'], 10.0), x
assert x['next_rank'] == 2, x
assert close(x['next_prize'], 25.0), x
assert x['players_to_jump'] == 3, x
assert close(x['next_jump'], 15.0), x

# 위성처럼 전 등수 동일: ITM 뒤에는 추가 money jump 가 없다.
sat = FM.payouts(10, 1.0)
x = CTX.money_jump_context(7, 10, sat)
assert x['in_money'] is True, x
assert x['next_rank'] is None, x
assert x['players_to_jump'] == 0, x
assert close(x['next_jump'], 0.0), x

print('OK money-jump context boundaries/bands/satellite')
