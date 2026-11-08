#!/usr/bin/env python3
"""카드별 169 전략 파일을 여러 저장 방식으로 다시 인코딩해 크기와 손실을 잰다 (docs/STRATEGY_PERCARD_MEASURE.md 4장).

  python3 tools/gto_fulltree/strategy_percard_variants.py <measure_run_dir> <board> [panel.json ...]

<measure_run_dir>/R1_percard/<board>.pc169.bin + .pc.meta.json (strategy_percard_measure.py 가 만든 것)을 읽는다. 읽기 전용.
방식 (모두 169 클래스 기준, 크기는 xz -6 으로 압축한 바이트):
  base  : 지금 형식(u16 퍼밀 + f32 도달)
  v1    : 빈도 1바이트(0~255), 도달 f32 / f16        — 손실 최대 0.2%p (1바이트 양자화)
  v2    : 무늬 대칭 — 기록 수 배율을 보드 목록에서 정확히 센다(panel.json 을 주면 그 보드 전부), 지금 보드는 겹치는 기록을 실제로도 센다
  v3    : 자기 도달 < 임계값(1e-4, 1e-3) 인 클래스 생략 — 생략된 도달 몫을 같이 보고
  v4    : 순수 전략(한 행동 퍼밀 1000) 클래스는 행동 번호만
  v5    : 턴·리버 카드를 비슷한 카드끼리 묶기(묶음 수별) — 묶음 안 평균(도달 가중)과의 차이(%p)
  combo : v1(f16)+v3(1e-4)+v4 / 거기에 v5 까지
"""
import itertools
import json
import lzma
import os
import struct
import sys

import numpy as np

NC = 169


def load(d, board):
    meta = json.load(open(os.path.join(d, 'R1_percard', board + '.pc.meta.json')))
    b = open(os.path.join(d, 'R1_percard', board + '.pc169.bin'), 'rb').read()
    lines = {l['id']: l for l in meta['lines']}
    pos, recs = 0, []
    while pos < len(b):
        lid, t, r = struct.unpack_from('<IBB', b, pos)
        pos += 6
        na = len(lines[lid]['actions'])
        reach = np.frombuffer(b, '<f4', NC, pos).astype(np.float64)
        pos += NC * 4
        fr = np.frombuffer(b, '<u2', na * NC, pos).reshape(na, NC)
        pos += na * NC * 2
        recs.append((lid, t, r, reach, fr))
    return meta, lines, recs, len(b)


def xz(b):
    return len(lzma.compress(b, preset=6))


def hdr(lid, t, r):
    return struct.pack('<IBB', lid, t, r)


def encode(recs, q8=False, reach16=False, pure=False, thr=None, noreach=False):
    """recs 를 바이트열 하나로. mask 가 필요한 방식(생략·순수)은 클래스 비트마스크를 붙인다. (바이트열, 통계) 반환"""
    parts, kept_n, tot_n, mass_kept, mass_all = [], 0, 0, 0.0, 0.0
    use_mask = pure or thr is not None or noreach
    if noreach and thr is None:
        thr = 1e-4
    for lid, t, r, reach, fr in recs:
        na = fr.shape[0]
        keep = reach > 0
        if thr is not None:
            keep = reach >= thr
        tot_n += int((reach > 0).sum())
        kept_n += int(keep.sum())
        mass_all += reach.sum()
        mass_kept += reach[keep].sum()
        p = [hdr(lid, t, r)]
        if use_mask:
            p.append(np.packbits(keep).tobytes())
            rr = reach[keep]
        else:
            rr = reach
            keep = np.ones(NC, bool)
        if not noreach:   # 도달 값은 앞 노드 전략에서 다시 계산할 수 있어 뺄 수 있다(마스크만 남김)
            p.append(rr.astype('<f2' if reach16 else '<f4').tobytes())
        f = fr[:, keep].astype(np.int64)
        if pure:
            # 순수 = 어떤 행동이 퍼밀 1000. 코드: 행동 번호, 섞인 클래스는 255
            ispure = (f == 1000).any(axis=0)
            code = np.where(ispure, (f == 1000).argmax(axis=0), 255).astype(np.uint8)
            p.append(code.tobytes())
            f = f[:, ~ispure]
        if q8:
            f = np.round(f * 255 / 1000).astype(np.uint8)
            p.append(f.tobytes())
        else:
            p.append(f.astype('<u2').tobytes())
        parts.append(b''.join(p))
    return b''.join(parts), {'entries_kept': kept_n, 'entries_total': tot_n, 'reach_mass_kept_frac': mass_kept / mass_all if mass_all else 1.0}


# ---- v2: 무늬 대칭 (보드만으로 센다) -------------------------------------------------------------
def parse_board(s):
    R = '23456789TJQKA'
    return [(R.index(s[i]), 'cdhs'.index(s[i + 1])) for i in range(0, len(s), 2)]


def orbit_counts(board):
    """플랍을 집합으로 자기 자신에 보내는 무늬 순열로 턴 카드 궤도 수, (턴, 리버) 순서쌍 궤도 수를 센다"""
    fl = set(parse_board(board))
    perms = [p for p in itertools.permutations(range(4)) if {(r, p[s]) for r, s in fl} == fl]
    cards = [(r, s) for r in range(13) for s in range(4) if (r, s) not in fl]
    ap = lambda c, p: (c[0], p[c[1]])
    orb_t = len({min(ap(c, p) for p in perms) for c in cards})
    pairs = [(a, b) for a in cards for b in cards if a != b]
    orb_p = len({min((ap(a, p), ap(b, p)) for p in perms) for a, b in pairs})
    return len(perms), orb_t, len(cards), orb_p, len(pairs)


# ---- v5: 카드 묶기 --------------------------------------------------------------------------------
def card_rs(c):
    return c >> 2, c & 3


def feats(board_cards, c):
    """보드(카드 번호 목록) 기준으로 새 카드 c 의 모양: (짝, 같은 무늬 수, 오버카드, 연결)"""
    rk = [x >> 2 for x in board_cards]
    sc = sum(1 for x in board_cards if x & 3 == c & 3)
    r = c >> 2
    return (r in rk, min(sc, 3), r > max(rk), min(abs(r - x) for x in rk) <= 2)


def key_of(board_cards, c, level):
    p, sc, ov, cn = feats(board_cards, c)
    if level == 4:      # 짝 / 무늬 맞음(같은 무늬 2장 이상) / 오버카드 / 그 밖
        return 'P' if p else 'F' if sc >= 2 else 'O' if ov else 'B'
    if level == 8:
        return ('P' if p else 'F' if sc >= 2 else 'O' if ov else 'B', cn)
    return (p, sc, ov, cn)      # 최대 16


def group_error(recs, board_cards, level):
    """묶음 키: 턴 줄은 (턴 모양), 리버 줄은 (턴 모양, 리버 모양). 묶음 평균(도달 가중)으로 대체했을 때 오차와 기록 수"""
    groups = {}
    for rec in recs:
        lid, t, r, reach, fr = rec
        if t == 255:
            k = (lid, 'flop')
        elif r == 255:
            k = (lid, key_of(board_cards, t, level))
        else:
            k = (lid, key_of(board_cards, t, level), key_of(board_cards + [t], r, level))
        groups.setdefault(k, []).append(rec)
    num = den = 0.0
    mx = mx_big = 0.0
    out = []
    for k, mem in groups.items():
        na = mem[0][4].shape[0]
        R = np.array([m[3] for m in mem])                       # n x 169
        F = np.array([np.where(m[4] == 65535, 0, m[4]) for m in mem], dtype=np.float64)   # n x na x 169
        w = R.sum(0)
        avg = np.where(w > 0, (R[:, None, :] * F).sum(0) / np.where(w > 0, w, 1), 0)     # na x 169
        d = np.abs(F - avg[None]) / 10.0                        # %p
        wt = R[:, None, :]
        num += float((wt * d).sum() / na)                       # 행동 평균
        den += float(R.sum())
        dm = d.max(axis=1)                                      # n x 169 (행동 중 최대)
        ok = R > 0
        if ok.any():
            mx = max(mx, float(dm[ok].max()))
            big = R >= 0.01
            if big.any():
                mx_big = max(mx_big, float(dm[big].max()))
        m0 = mem[0]
        out.append((m0[0], m0[1] if len(k) == 2 else m0[1], m0[2], w / len(mem), np.round(avg).astype(np.int64)))
    return len(groups), num / den if den else 0.0, mx, mx_big, out


def main():
    d, board = sys.argv[1], sys.argv[2]
    meta, lines, recs, raw = load(d, board)
    bc = [(r << 2) | s for r, s in parse_board(board)]
    res = {'board': board, 'records': len(recs), 'raw_base': raw}
    by_street = {}
    for lid, t, r, reach, fr in recs:
        by_street.setdefault(lines[lid]['street'], [0, 0])
        by_street[lines[lid]['street']][0] += 1
        by_street[lines[lid]['street']][1] += 6 + NC * 4 + fr.size * 2
    res['by_street_records_bytes'] = by_street
    base, _ = encode(recs)
    res['base_xz'] = xz(base)
    res['base_equals_file'] = len(base) == raw
    res['v1'] = {}
    for nm, kw in (('u8_f32', dict(q8=True)), ('u8_f16', dict(q8=True, reach16=True)), ('u16_f16', dict(reach16=True))):
        b, _ = encode(recs, **kw)
        res['v1'][nm] = {'raw': len(b), 'xz': xz(b)}
    allf = np.concatenate([fr[fr != 65535].ravel() for _, _, _, _, fr in recs]).astype(np.float64)
    q = np.round(allf * 255 / 1000) * 1000 / 255
    res['v1']['max_err_pp'] = float(np.abs(q - allf).max() / 10)
    res['v1']['mean_err_pp'] = float(np.abs(q - allf).mean() / 10)
    # v2
    npm, ot, nt, op, npairs = orbit_counts(board)
    st = {s: v[1] for s, v in by_street.items()}
    flop_b, turn_b, riv_b = st.get(0, 0), st.get(1, 0), st.get(2, 0)
    res['v2'] = {'perms': npm, 'turn_orbits': ot, 'turn_cards': nt, 'pair_orbits': op, 'pairs': npairs,
                 'size_factor': (flop_b + turn_b * ot / nt + riv_b * op / npairs) / (flop_b + turn_b + riv_b)}
    seen, dup = {}, 0
    for lid, t, r, reach, fr in recs:
        h = (lid, reach.tobytes(), fr.tobytes())
        dup += h in seen
        seen[h] = 1
    res['v2']['identical_records_in_file'] = dup
    for panel in sys.argv[3:]:
        bs = [f['board'] for f in json.load(open(panel))['panel']]
        fac = []
        for b in bs:
            _, ot_, nt_, op_, np_ = orbit_counts(b)
            fac.append((flop_b + turn_b * ot_ / nt_ + riv_b * op_ / np_) / (flop_b + turn_b + riv_b))
        res['v2'][os.path.basename(panel)] = {'mean_size_factor': float(np.mean(fac)), 'min': float(min(fac)), 'max': float(max(fac))}
    # v3
    res['v3'] = {}
    for thr in (1e-4, 1e-3, 1e-2):
        b, s = encode(recs, thr=thr)
        full = sum(1 for _, _, _, rch, _ in recs if (rch >= thr).sum() == 0)
        res['v3'][str(thr)] = {'raw': len(b), 'xz': xz(b), **s, 'records_fully_dropped': full}
    # v4
    b, _ = encode(recs, pure=True)
    pure_n = tot_n = 0
    for _, _, _, reach, fr in recs:
        ok = reach > 0
        pure_n += int(((fr == 1000).any(axis=0) & ok).sum())
        tot_n += int(ok.sum())
    res['v4'] = {'raw': len(b), 'xz': xz(b), 'pure_entries_frac': pure_n / tot_n}
    # v5
    res['v5'] = {}
    for level in (4, 8, 16):
        n, mean, mx, mxb, out = group_error(recs, bc, level)
        grecs = [(lid, t, r, rch, fr) for lid, t, r, rch, fr in out]
        b, _ = encode(grecs)
        res['v5'][str(level)] = {'groups_records': n, 'records_before': len(recs), 'raw': len(b), 'xz': xz(b),
                                  'mean_diff_pp': mean, 'max_diff_pp': mx, 'max_diff_pp_reach_ge_0.01': mxb}
        if level == 8:
            g8 = grecs
    # 조합
    b, _ = encode(recs, q8=True, reach16=True, pure=True, thr=1e-4)
    res['combo_1_3_4'] = {'raw': len(b), 'xz': xz(b)}
    b, _ = encode(recs, q8=True, noreach=True, pure=True)
    res['combo_1_3_4_noreach'] = {'raw': len(b), 'xz': xz(b)}
    b, _ = encode(recs, q8=True, noreach=True)
    res['q8_mask_noreach_nopure'] = {'raw': len(b), 'xz': xz(b)}
    b, _ = encode(g8, q8=True, reach16=True, pure=True, thr=1e-4)
    res['combo_1_3_4_5level8'] = {'raw': len(b), 'xz': xz(b)}
    json.dump(res, open(os.path.join(d, 'variants_%s.json' % board), 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
