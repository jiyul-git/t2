#!/usr/bin/env python3
import json
from pathlib import Path
d=json.load(open('/tmp/t2_jj_ranges.json',encoding='utf-8'))
for name,sizes in [('std',[33.0,75.0]),('wide',[33.0,50.0,75.0,100.0])]:
    ss=', '.join(str(x) for x in sizes)
    cfg='\n'.join([
        'board = "Td Jh 6c"',
        f'oop_range = "{d["oop_range"]}"',
        f'ip_range = "{d["ip_range"]}"',
        f'effective_stack = {d["stack_bb"]:.6f}',
        f'starting_pot = {d["pot_bb"]:.6f}',
        'allin_threshold = 85.0',
        'raise_cap = 2',
        'max_iterations = 700',
        'target_exploitability = 0.5',
        '',
        '[sizings.oop.flop]',
        f'bet = {{ percents = [{ss}] }}',
        'raise = { percents = [60.0] }',
        '[sizings.ip.flop]',
        f'bet = {{ percents = [{ss}] }}',
        'raise = { percents = [60.0] }',
        '[sizings.oop.turn]',
        'bet = { percents = [50.0, 75.0] }',
        'raise = { percents = [60.0] }',
        '[sizings.ip.turn]',
        'bet = { percents = [50.0, 75.0] }',
        'raise = { percents = [60.0] }',
        '[sizings.oop.river]',
        'bet = { percents = [50.0, 75.0], allin = true }',
        '[sizings.ip.river]',
        'bet = { percents = [50.0, 75.0], allin = true }',
        ''
    ])
    Path(f'/tmp/jj_{name}.toml').write_text(cfg,encoding='utf-8')
print(json.dumps({k:v for k,v in d.items() if not k.endswith('_range')},ensure_ascii=False))
