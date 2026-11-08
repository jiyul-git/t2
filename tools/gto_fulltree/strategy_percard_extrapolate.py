#!/usr/bin/env python3
"""측정 결과(measure.json, variants_<board>.json)로 묶음·단계·4개 스택 용량을 추정해 마크다운 표로 낸다.

  python3 tools/gto_fulltree/strategy_percard_extrapolate.py <t01_dir> <t04_dir> <t10_dir>   (순서: 싱글레이즈, 림프, 3벳)
보드당 값 = 세 팟 종류를 step1 묶음 수 비율로 가중 평균. 묶음 = 72보드. 스택별 묶음 수 30/40/60/100bb = 58/74/80/98 (단계당).
"""
import csv
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
BOARD = 'JcTd5h'
STACKS = {'30bb': 58, '40bb': 74, '60bb': 80, '100bb': 98}
STAGES = 4   # 계획서의 최대 단계 수(문서 GTO_FULLTREE_PILOT_60BB.md 0장)
MB = 1e6


def mix():
    c = {'single': 0, 'limp': 0, '3bet+': 0}
    for r in csv.DictReader(open(os.path.join(REPO, 'data/ft60/step1/bundles.tsv')), delimiter='\t'):
        c['3bet+' if r['matrix'] == 'True' else 'limp' if 'Limp' in r['line'] else 'single'] += 1
    t = sum(c.values())
    return {k: v / t for k, v in c.items()}, c


def main():
    dirs = dict(zip(['single', 'limp', '3bet+'], sys.argv[1:4]))
    w, cnt = mix()
    M = {k: json.load(open(os.path.join(d, 'measure.json'))) for k, d in dirs.items()}
    V = {k: json.load(open(os.path.join(d, 'variants_%s.json' % BOARD))) for k, d in dirs.items()}
    f2 = V['single']['v2']['panel_prec_A72.json']['mean_size_factor']
    rows = {
        '지금(카드 평균, JSON)': lambda k: M[k]['size_bytes']['current_avg']['xz6'],
        '카드별 169, 지금 형식(u16+f32), xz': lambda k: M[k]['size_bytes']['percard_169']['xz6'],
        '카드별 1326 콤보, xz': lambda k: M[k]['size_bytes']['percard_1326']['xz6'],
        '(1) 169, 빈도 1바이트+도달 f16, xz [손실 ≤0.2%p]': lambda k: V[k]['v1']['u8_f16']['xz'],
        '(2) 무늬 대칭 (지금 형식 xz × 보드 평균 %.3f)' % f2: lambda k: M[k]['size_bytes']['percard_169']['xz6'] * f2,
        '(3) 도달<1e-4 클래스 생략 (u16+f32, xz)': lambda k: V[k]['v3']['0.0001']['xz'],
        '(4) 순수 클래스 행동번호만 (u16+f32, xz)': lambda k: V[k]['v4']['xz'],
        '(1)+(3)+(4) (도달 f16 유지)': lambda k: V[k]['combo_1_3_4']['xz'],
        '(1)+(3)+(4), 도달 값 생략(마스크만)': lambda k: V[k]['combo_1_3_4_noreach']['xz'],
        '(1)+(2)+(3)+(4), 도달 생략': lambda k: V[k]['combo_1_3_4_noreach']['xz'] * f2,
        '(5) 카드 묶기 8묶음류 + (1)(3)(4) [손실 큼]': lambda k: V[k]['combo_1_3_4_5level8']['xz'],
    }
    print('묶음 비율(step1): ' + ', '.join('%s %d개(%.0f%%)' % (k, cnt[k], 100 * w[k]) for k in w))
    print('\n| 방식 (보드당 xz 압축) | 보드 MB | 묶음 72보드 MB | 60bb 한 단계 80묶음 GB | 4스택 한 단계 310묶음 GB | 4스택 마지막 단계만·패널 A만 GB | 4스택 %d단계 전부·A·B GB |' % STAGES)
    print('|---|---|---|---|---|---|---|')
    out = {}
    for name, fn in rows.items():
        b = sum(w[k] * fn(k) for k in w) / MB
        bun = b * 72
        out[name] = b
        print('| %s | %.2f | %.0f | %.1f | %.1f | %.1f | %.1f |' % (name, b, bun, bun * 80 / 1e3, bun * sum(STACKS.values()) / 1e3,
                                                          bun * sum(STACKS.values()) / 1e3 / 2, bun * sum(STACKS.values()) / 1e3 * STAGES))
    json.dump(out, open('/tmp/claude-0/extrapolate.json', 'w'), indent=1) if os.path.isdir('/tmp/claude-0') else None


if __name__ == '__main__':
    main()
