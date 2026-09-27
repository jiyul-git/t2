#!/usr/bin/env python3
import json
from pathlib import Path
d=json.load(open('/tmp/t2_jj_ranges.json',encoding='utf-8'))
cfg='\n'.join([
'board = "Td Jh 6c"',
f'oop_range = "{d["oop_range"]}"',
f'ip_range = "{d["ip_range"]}"',
f'effective_stack = {d["stack_bb"]:.6f}',
f'starting_pot = {d["pot_bb"]:.6f}',
'allin_threshold = 85.0',
'raise_cap = 1',
'max_iterations = 120',
'target_exploitability = 2.0',
'',
'[sizings.oop.flop]',
'bet = { percents = [50.0] }',
'raise = { percents = [60.0] }',
'[sizings.ip.flop]',
'bet = { percents = [50.0] }',
'raise = { percents = [60.0] }',
'[sizings.oop.turn]',
'bet = { percents = [75.0] }',
'[sizings.ip.turn]',
'bet = { percents = [75.0] }',
'[sizings.oop.river]',
'bet = { percents = [75.0], allin = true }',
'[sizings.ip.river]',
'bet = { percents = [75.0], allin = true }',''])
Path('/tmp/jj_fast.toml').write_text(cfg,encoding='utf-8')
