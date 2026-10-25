#!/usr/bin/env python3
"""Self-test for the lounge placeholder generator and asset checker (design doc 6.4-6.5, step 5).

The checker must pass the generated placeholders and must reject broken variants,
broken clips and malformed manifests; the generator must be deterministic.
"""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lounge_check_assets as C          # noqa: E402
import lounge_make_placeholders as G     # noqa: E402

checks = 0


def ok(cond, msg):
    global checks
    checks += 1
    if not cond:
        raise AssertionError(msg)


def tree_hash(root):
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob('*')):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def generate(dst):
    G.main(['--out', str(dst)])


def clone(src, dst):
    shutil.copytree(src, dst)
    return Path(dst)


def load_manifest(root, name):
    return json.loads((root / 'chars' / name / 'manifest.json').read_text())


def save_manifest(root, name, m):
    (root / 'chars' / name / 'manifest.json').write_text(json.dumps(m, separators=(',', ':')))


def errors_of(root):
    rep = C.check_assets(root)
    return rep, rep.errors


def expect_error(root, kind, why):
    rep, errs = errors_of(root)
    ok(any(e.startswith(kind + ':') for e in errs), '%s: expected a "%s" error, got %r' % (why, kind, errs[:3]))
    return rep


def main():
    tmp = Path(tempfile.mkdtemp(prefix='lounge_assets_'))
    try:
        base = tmp / 'base'
        generate(base)

        # 1. The generated placeholders satisfy the whole contract.
        rep, errs = errors_of(base)
        ok(not errs, 'placeholders should pass, got %r' % errs)
        ok(rep.chars == {n: 'active' for n in ('penguin', 'rabbit', 'tiger', 'turtle')}, 'all four characters active: %r' % rep.chars)
        ok(C.dir_size(base) <= C.BUDGET_PLACEHOLDER_TOTAL, 'placeholder budget')

        # 2. Deterministic output.
        again = tmp / 'again'
        generate(again)
        ok(tree_hash(base) == tree_hash(again), 'two runs must produce identical bytes')

        # 3. Every clip of the design (6.3) is present for every character, with the documented frame counts.
        expected = {
            'walk_r': 8, 'walk_l': 8, 'turn_r_front': 6, 'turn_l_front': 6, 'turn_front_r': 6, 'turn_front_l': 6,
            'sit_down': 10, 'stand_up': 10, 'sit_idle': 24,
            'phone_in': 8, 'phone_loop': 16, 'phone_out': 8, 'call_in': 8, 'call_loop': 16, 'call_out': 8,
            'eat_in': 8, 'eat_loop': 24, 'eat_out': 8, 'sunglasses': 20, 'fix_clothes': 18,
            'doze_in': 10, 'doze_loop': 24, 'doze_out': 10,
        }
        for side in ('l', 'r'):
            expected.update({'chat_in_' + side: 6, 'chat_talk_' + side: 16, 'chat_listen_' + side: 16, 'chat_out_' + side: 6})
        for name in G.CHARS:
            m = load_manifest(base, name)
            ok({k: len(v['frames']) for k, v in m['clips'].items()} == expected, name + ' clip set or frame counts')
            ok(m['clips']['walk_r']['advance'] == 13 and m['clips']['sit_down']['laneSwitchAt'] == 5, name + ' advance / laneSwitchAt')
            ok(set(m['poses']) == set(G.POSE_ORDER), name + ' poses')
            ok(m['clips']['phone_in']['from'] == 'sit' and m['clips']['phone_in']['to'] == 'phone', name + ' graph edge')

        # 4. A day variant shifted sideways is rejected.
        t = clone(base, tmp / 'shift')
        p = t / 'bg' / 'interior_day.png'
        arr = np.roll(np.asarray(Image.open(p).convert('RGBA')), 12, axis=1)
        Image.fromarray(arr).save(p)
        expect_error(t, 'alignment', 'shifted day variant')

        # 5. Line work moved inside an otherwise aligned variant is rejected (alpha unchanged).
        t = clone(base, tmp / 'lines')
        p = t / 'bg' / 'outside_day.png'
        im = np.asarray(Image.open(p).convert('RGBA')).copy()
        im[:, :, :3] = np.roll(im[:, :, :3], 9, axis=0)
        Image.fromarray(im).save(p)
        expect_error(t, 'alignment', 'moved line work')

        # 6. A clip that ends on the wrong pose is rejected.
        t = clone(base, tmp / 'seam_end')
        m = load_manifest(t, 'rabbit')
        m['clips']['phone_in']['frames'][-1] = m['poses']['eat']
        save_manifest(t, 'rabbit', m)
        rep = expect_error(t, 'seam', 'wrong last frame')
        ok(any('phone_in' in e and 'does not end' in e for e in rep.errors), 'error names the clip')

        # 7. A clip that starts on the wrong pose is rejected.
        t = clone(base, tmp / 'seam_start')
        m = load_manifest(t, 'tiger')
        m['clips']['sit_down']['frames'][0] = m['poses']['doze']
        save_manifest(t, 'tiger', m)
        expect_error(t, 'seam', 'wrong first frame')

        # 8. A loop whose wrap jumps is rejected, while a clean loop is accepted (base passed above).
        t = clone(base, tmp / 'loop')
        m = load_manifest(t, 'turtle')
        fr = m['clips']['sit_idle']['frames']
        fr[-1] = m['poses']['eat']          # last frame is an unrelated pose
        save_manifest(t, 'turtle', m)
        expect_error(t, 'seam', 'broken loop wrap')

        # 9. A missing required clip makes the character inactive: a warning, not an error.
        t = clone(base, tmp / 'inactive')
        m = load_manifest(t, 'penguin')
        del m['clips']['sit_down']
        save_manifest(t, 'penguin', m)
        rep, errs = errors_of(t)
        ok(not errs, 'inactive character is not an error: %r' % errs)
        ok(rep.chars['penguin'] == 'inactive' and rep.chars['tiger'] == 'active', 'penguin inactive only')
        ok(any(w.startswith('inactive:') and 'sit_down' in w for w in rep.warnings), 'warning names the missing clip')

        # 10. An optional clip whose pose cannot be reached breaks the pose graph.
        t = clone(base, tmp / 'graph')
        m = load_manifest(t, 'tiger')
        m['poses']['island'] = m['poses']['doze']
        m['clips']['island_loop'] = {'from': 'island', 'to': 'island', 'loop': True, 'fps': 12, 'frames': [m['poses']['doze']] * 2}
        save_manifest(t, 'tiger', m)
        expect_error(t, 'graph', 'unreachable pose')

        # 11. Missing and malformed files.
        t = clone(base, tmp / 'missing')
        (t / 'bg' / 'props.png').unlink()
        expect_error(t, 'file', 'missing background')
        t = clone(base, tmp / 'bad_size')
        Image.new('RGBA', (100, 100)).save(t / 'bg' / 'bench_back.png')
        expect_error(t, 'schema', 'wrong background size')
        t = clone(base, tmp / 'bad_frame')
        m = load_manifest(t, 'rabbit')
        m['frames'][3]['x'] = 10 ** 6
        save_manifest(t, 'rabbit', m)
        expect_error(t, 'schema', 'frame outside atlas')
        t = clone(base, tmp / 'bad_index')
        m = load_manifest(t, 'rabbit')
        m['clips']['walk_r']['frames'][0] = 99999
        save_manifest(t, 'rabbit', m)
        expect_error(t, 'schema', 'clip frame index out of range')
        t = clone(base, tmp / 'no_advance')
        m = load_manifest(t, 'rabbit')
        del m['clips']['walk_l']['advance']
        save_manifest(t, 'rabbit', m)
        expect_error(t, 'schema', 'walking clip without advance')
        t = clone(base, tmp / 'bad_json')
        (t / 'scene.json').write_text('{ nope')
        expect_error(t, 'schema', 'invalid scene.json')
        t = clone(base, tmp / 'opaque_glass')
        p = t / 'bg' / 'interior_night.png'
        arr = np.asarray(Image.open(p).convert('RGBA')).copy()
        arr[:, :, 3] = 255
        Image.fromarray(arr).save(p)
        expect_error(t, 'schema', 'interior without a window hole')

        # 12. Face variants (frame.v, patch frames with "over"): the real characters pass; broken ones are caught.
        real = HERE.parent / 'web' / 'lounge' / 'assets'
        froot = tmp / 'faces'
        (froot / 'chars').mkdir(parents=True)

        def char_errors(name):
            rep = C.Report()
            C.check_character(froot, name, rep)
            return rep.errors
        real_names = json.loads((real / 'scene.json').read_text())['characters']
        ok({'tiger', 'rabbit', 'turtle'} <= set(real_names), 'the scene has the real tiger, rabbit and turtle: %r' % real_names)
        for name in real_names:
            shutil.copytree(real / 'chars' / name, froot / 'chars' / name)
            m = load_manifest(froot, name)
            ok(not char_errors(name), name + ' with face variants should pass: %r' % char_errors(name)[:3])
            ok('blink' in (m['frames'][m['clips']['walk_r']['frames'][0]].get('v') or {}), name + ' has a blink on walk_r')
            rep = C.Report()
            C.check_character(froot, name, rep)
            # a plain walker (walk clips only: the penguin until its sitting art comes) only passes by
            want = 'walker' if set(m['clips']) == {'walk_r', 'walk_l'} else 'hybrid'
            ok(rep.chars.get(name) == want, name + ' passes by%s (%s): %r' % (' and sits' if want == 'hybrid' else '', want, rep.chars))
        name = 'rabbit'
        orig = load_manifest(froot, name)
        # a hybrid that loses a sitting clip still passes by (walker); its seams are still checked
        m = json.loads(json.dumps(orig))
        for cid in [c for c in m['clips'] if c.split('@')[0] == 'sit_down']:     # every facing's sit_down
            del m['clips'][cid]
        save_manifest(froot, name, m)
        rep = C.Report(); C.check_character(froot, name, rep)
        ok(rep.chars.get(name) == 'walker' and not rep.errors, 'hybrid without sit_down is a plain walker: %r %r' % (rep.chars, rep.errors[:2]))
        m = json.loads(json.dumps(orig)); m['clips']['sit_down']['frames'][-1] = m['poses']['stand_front']; save_manifest(froot, name, m)
        ok(any(e.startswith('seam:') and 'sit_down' in e for e in char_errors(name)), 'a broken sit_down seam is caught on a hybrid')
        save_manifest(froot, name, orig)

        def broken(mutate, why, kind='face'):
            m = json.loads(json.dumps(orig))
            mutate(m)
            save_manifest(froot, name, m)
            errs = char_errors(name)
            ok(any(e.startswith(kind + ':') for e in errs), '%s: expected a "%s" error, got %r' % (why, kind, errs[:3]))
            save_manifest(froot, name, orig)
        f0 = orig['clips']['walk_r']['frames'][0]
        blink = orig['frames'][f0]['v']['blink']
        broken(lambda m: m['frames'][f0]['v'].update(blink=99999), 'v points at a missing frame')
        broken(lambda m: m['frames'][f0]['v'].update(blink=f0), 'v points at itself')
        broken(lambda m: m['frames'][f0]['v'].update(Blink=blink), 'v key is not a lower-case word')
        broken(lambda m: m['frames'][blink].update(ay=m['frames'][blink]['ay'] + 500), 'patch placed outside its frame')
        broken(lambda m: m['frames'][blink].update(over=f0 + 1), 'patch made for another frame')
        broken(lambda m: m['frames'][f0]['v'].update(blink=f0 + 1), 'full variant with another anchor or silhouette')
        broken(lambda m: m['clips']['walk_r']['frames'].__setitem__(0, blink), 'a clip plays a patch frame', 'schema')
        # a frame rectangle stretched into the next picture of the atlas (it would draw a piece of it)
        broken(lambda m: m['frames'][m['poses']['sit']].update(h=m['frames'][m['poses']['sit']]['h'] + 400), 'frame rectangle runs into another picture', 'schema')

        # 13. Budget: the placeholder total is enforced.
        t = clone(base, tmp / 'budget')
        (t / 'chars' / 'tiger' / 'pad.bin').write_bytes(b'\0' * (C.BUDGET_PLACEHOLDER_TOTAL + 1))
        expect_error(t, 'budget', 'oversized placeholder set')

        # 14. Weather plates (design doc 13.2) and taxi lanes (14): a plate that is a copy of the outside plate
        # passes; a shifted one, one with another glass cut, a wrong size and a bad lane are rejected.
        def with_weather(name, mutate_plate=None, mutate_scene=None):
            t = clone(base, tmp / name)
            plate = np.asarray(Image.open(t / 'bg' / 'outside_day.png').convert('RGBA')).copy()
            if mutate_plate:
                plate = mutate_plate(plate)
            Image.fromarray(plate).save(t / 'bg' / 'outside_rain.png')
            sc = json.loads((t / 'scene.json').read_text())
            sc['weather'] = {'plates': {'rain': 'bg/outside_rain.png'}, 'rect': [0, 0, 100, 100], 'mask': 'outside'}
            if mutate_scene:
                mutate_scene(sc)
            (t / 'scene.json').write_text(json.dumps(sc))
            return t
        _, errs = errors_of(with_weather('wx_ok'))
        ok(not errs, 'a weather plate that matches the outside plate should pass, got %r' % errs)
        expect_error(with_weather('wx_shift', lambda a: np.roll(a, 14, axis=1)), 'alignment', 'weather plate shifted 14 px')
        expect_error(with_weather('wx_cut', lambda a: np.concatenate([a[:, :-120], np.zeros_like(a[:, -120:])], axis=1)), 'alignment', 'weather plate with another glass cut')
        expect_error(with_weather('wx_size', lambda a: a[:-40]), 'schema', 'weather plate of the wrong size')
        expect_error(with_weather('wx_noplates', None, lambda sc: sc['weather'].pop('plates')), 'schema', 'weather without plates')
        lane = {'id': 'far', 'y': [592, 606], 'duration': 80}
        def lanes(sc, **over):
            sc['planes'] = {'right': 'bg/plane_right.png', 'left': 'bg/plane_left.png', 'period': 150, 'duration': 80,
                            'horizon': 475, 'ref': {'y': 690, 'h': 300}, 'ground': 0.97, 'lanes': [dict(lane, **over)]}
            Image.new('RGBA', (40, 20)).save(base / 'bg' / 'plane_right.png')
        ok(base.exists(), 'base kept')
        for name, over, good in (('lane_ok', {}, True), ('lane_above_horizon', {'y': [400, 410]}, False), ('lane_no_duration', {'duration': 'x'}, False), ('lane_too_long', {'duration': 999}, False)):
            t = clone(base, tmp / name)
            sc = json.loads((t / 'scene.json').read_text())
            lanes(sc, **over)
            Image.new('RGBA', (40, 20)).save(t / 'bg' / 'plane_right.png'); Image.new('RGBA', (40, 20)).save(t / 'bg' / 'plane_left.png')
            (t / 'scene.json').write_text(json.dumps(sc))
            rep, errs = errors_of(t)
            ok(bool(errs) != good, '%s: expected %s, got %r' % (name, 'no errors' if good else 'a schema error', errs[:2]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('verify_lounge_assets OK (%d checks)' % checks)


if __name__ == '__main__':
    try:
        main()
    except AssertionError as e:
        print('FAILED:', e)
        sys.exit(1)
