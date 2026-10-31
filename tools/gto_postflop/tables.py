"""Markdown tables from compare.py output.   python3 tools/gto_postflop/tables.py <compare.json> > tables.md"""
import json
import sys

GRP = [('grp:tp_plus', '탑페어+'), ('top_pair', '(탑페어만)'), ('grp:mid_pair', '중간·약한 페어'), ('grp:draw', '드로우'),
       ('grp:gutshot', '거트샷'), ('grp:air', '에어')]
TEX = ['rainbow', 'twotone', 'monotone', 'paired']
SPOT_TITLE = {'p40_flat_btn_vs_bb': '40bb BTN 2.0 오픈 vs BB 콜 (싱글 레이즈 팟, OOP=BB, IP=BTN)',
              'p60_flat_co_vs_bb_o25': '60bb CO 2.5 오픈 vs BB 콜 (싱글 레이즈 팟, OOP=BB, IP=CO)',
              'p40v1_btn_vs_sb_3b40': '40bb BTN 2.0 오픈, SB 3벳 8bb, BTN 콜 (3벳 팟, OOP=SB 3벳러, IP=BTN)'}
MIN_N = 30


def pct(x):
    return '-' if x is None else '%.0f' % (100 * x)


def main_act(freq, kind):
    if not freq:
        return None
    return freq.get(kind, 0.0)


def cell(node, slot, kind):
    g = node['gto'].get(slot)
    t = node['t2'].get(slot)
    gv = main_act(g['freq'], kind) if g else None
    if t and t['n'] >= MIN_N:
        tv = '%s' % pct(main_act(t['freq'], kind))
    elif t:
        tv = '(%s, n=%d)' % (pct(main_act(t['freq'], kind)), t['n'])
    else:
        tv = '-'
    return '%s / %s' % (pct(gv), tv)


def node_kind(node):
    acts = set(node['gto'].get('all', {}).get('freq', {})) | set(node['t2'].get('all', {}).get('freq', {}))
    return 'bet' if 'bet' in acts or 'check' in acts else 'raise'


def main():
    d = json.load(open(sys.argv[1]))
    out = []
    for spot, s in d.items():
        out.append('### %s\n' % SPOT_TITLE.get(spot, spot))
        out.append('GTO 보드 %d개, T2 %d판(보드당 %d판). 칸 = GTO %% / T2 %%. T2 표본 %d 미만은 괄호.\n' % (
            s['boards_gto'], s['hands_t2'], s['hands_t2'] // 24, MIN_N))
        out.append('**행동별 (첫 행동·체크 뒤 = 벳 %, 벳 받은 뒤 = 레이즈 % · 폴드 %)**\n')
        out.append('| 상황 | 전체 | ' + ' | '.join(l for _, l in GRP) + ' | T2 표본 |')
        out.append('|---|' + '---|' * (len(GRP) + 2))
        for name, node in s['nodes'].items():
            k = node_kind(node)
            n = node['t2'].get('all', {}).get('n', 0)
            row = [node['label'] + (' 벳' if k == 'bet' else ' 레이즈')] + [cell(node, 'all', k)] + [cell(node, sl, k) for sl, _ in GRP]
            out.append('| ' + ' | '.join(row) + ' | %d |' % n)
            if k == 'raise':
                row = [node['label'] + ' 폴드'] + [cell(node, 'all', 'fold')] + [cell(node, sl, 'fold') for sl, _ in GRP]
                out.append('| ' + ' | '.join(row) + ' | |')
        out.append('')
        out.append('**보드 결 별 (벳 %: 전체 / 탑페어만)**\n')
        out.append('| 상황 | ' + ' | '.join(TEX) + ' |')
        out.append('|---|' + '---|' * len(TEX))
        for name, node in s['nodes'].items():
            if node_kind(node) != 'bet':
                continue
            out.append('| %s 전체 | ' % node['label'] + ' | '.join(cell(node, 'tex:' + t, 'bet') for t in TEX) + ' |')
            out.append('| %s 탑페어 | ' % node['label'] + ' | '.join(cell(node, 'top_pair|tex:' + t, 'bet') for t in TEX) + ' |')
        out.append('')
        out.append('**벳할 수 있는 모든 순간을 모은 벳 빈도 (스트리트·자리별, 라인 무관; 계산 메뉴에 없는 턴·리버 동크 제외)**\n')
        out.append('| 스트리트·자리 | 전체 | ' + ' | '.join(l for _, l in GRP) + ' |')
        out.append('|---|' + '---|' * (len(GRP) + 1))
        for k, v in s['bet_opportunity'].items():
            def c(sl):
                g = v['gto'].get(sl, {}).get('bet')
                t = v['t2'].get(sl)
                return '%s / %s' % (pct(g), (pct(t['bet']) if t['n'] >= MIN_N else '(%s, n=%d)' % (pct(t['bet']), t['n'])) if t else '-')
            out.append('| %s | %s | ' % (k, c('all')) + ' | '.join(c(sl) for sl, _ in GRP) + ' |')
        out.append('')
        out.append('**T2 벳 크기 (팟 대비, 중앙값 [25%%–75%%]); GTO 메뉴는 50%% 하나**\n')
        out.append('| 스트리트·자리 | 표본 | 중앙값 | 25–75% |')
        out.append('|---|---|---|---|')
        for k, v in sorted(s['t2_bet_sizes'].items()):
            out.append('| %s | %d | %.2f | %.2f–%.2f |' % (k, v['n'], v['median_pot_frac'], v['p25'], v['p75']))
        out.append('')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
