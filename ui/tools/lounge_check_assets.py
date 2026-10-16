#!/usr/bin/env python3
"""Asset contract check for the lobby lounge scene (docs/LOUNGE_SCENE_DESIGN.md 6.4).

    python3 ui/tools/lounge_check_assets.py [--root ui/web/lounge/assets]

Exit status 1 if any error is found. A character that lacks required clips is reported as
inactive (a warning, not an error). Needs Pillow, numpy and opencv-python-headless.
"""
import argparse
import json
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:           # pragma: no cover - reported as an error below
    cv2 = None

SCENE_WIDTH = 1440           # logical width; height follows the artwork (600..1400)
REQUIRED_CLIPS = ['walk_r', 'walk_l', 'turn_r_front', 'turn_l_front', 'turn_front_r', 'turn_front_l',
                  'sit_down', 'stand_up', 'sit_idle']
REQUIRED_POSES = ['walk_r', 'walk_l', 'stand_front', 'sit']
GROUPS = ('far', 'back', 'mid', 'front')
EMISSION_KEYS = ('lamp', 'city')
SEAM_MAX_ERR = 6.0           # mean abs error, 0..255, premultiplied RGBA
LOOP_SEAM_FACTOR = 1.25      # loop wrap may jump at most this much more than the biggest normal step
ALPHA_IOU_MIN = 0.98
EDGE_IOU_MIN = 0.90
BUDGET_BG = 2_500_000
BUDGET_CHAR = 1_500_000
BUDGET_PLACEHOLDER_TOTAL = 1_000_000


class Report:
    def __init__(self):
        self.errors, self.warnings, self.chars = [], [], {}

    def err(self, kind, msg):
        self.errors.append('%s: %s' % (kind, msg))

    def warn(self, kind, msg):
        self.warnings.append('%s: %s' % (kind, msg))

    @property
    def ok(self):
        return not self.errors


def read_json(path, rep, kind):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        rep.err('file', '%s missing (%s)' % (path, kind))
    except (ValueError, OSError) as e:
        rep.err('schema', '%s is not valid JSON: %s' % (path, e))
    return None


def load_rgba(path, rep):
    try:
        with Image.open(path) as im:
            return np.asarray(im.convert('RGBA'), dtype=np.uint8)
    except FileNotFoundError:
        rep.err('file', '%s missing' % path)
    except Exception as e:      # truncated or unreadable image
        rep.err('file', '%s unreadable: %s' % (path, e))
    return None


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ---------------------------------------------------------------------------- scene.json

def edge_maps(rgba, lo, hi):
    """Canny edges of the layer composited over black and over white, plus its alpha outline."""
    a = rgba[..., 3:4].astype(np.float32) / 255.0
    rgb = rgba[..., :3].astype(np.float32)
    maps = [cv2.Canny(rgba[..., 3], lo, hi)]
    for bg in (0.0, 255.0):                       # a faint boundary shows on one of the two backdrops
        comp = (rgb * a + bg * (1 - a)).astype(np.uint8)
        maps.append(cv2.Canny(cv2.cvtColor(comp, cv2.COLOR_RGB2GRAY), lo, hi))
    return np.maximum.reduce(maps) > 0


def edge_agreement(a, b):
    """Share of one variant's clear line work that has a counterpart within 3 px in the other,
    taking the worse direction. Tolerant of colour and lighting changes, not of moved lines."""
    grow = np.ones((3, 3), np.uint8)
    worst = 1.0
    for x, y in ((a, b), (b, a)):
        strong = edge_maps(x, 60, 150)
        weak = cv2.dilate(edge_maps(y, 15, 45).astype(np.uint8), grow, iterations=3) > 0
        n = int(strong.sum())
        if n:
            worst = min(worst, float(np.logical_and(strong, weak).sum()) / n)
    return worst


def iou(a, b):
    u = np.logical_or(a, b).sum()
    return 1.0 if u == 0 else float(np.logical_and(a, b).sum()) / float(u)


def check_scene(root, rep):
    scene = read_json(root / 'scene.json', rep, 'scene')
    if scene is None:
        return None
    size = scene.get('size')
    if not (isinstance(size, list) and len(size) == 2 and size[0] == SCENE_WIDTH and is_int(size[1]) and 600 <= size[1] <= 1400):
        rep.err('schema', 'scene.json size must be [%d, height 600..1400]' % SCENE_WIDTH)
        size = [SCENE_WIDTH, 1040]
    scene_size = tuple(size)
    if 'charScale' in scene and not (is_num(scene['charScale']) and scene['charScale'] > 0):
        rep.err('schema', 'scene.json charScale must be a positive number')
    for key in ('baselineY', 'horizonY', 'windowFacing'):
        if not is_num(scene.get(key)):
            rep.err('schema', 'scene.json %s must be a number' % key)
    for key, fields in (('window', ('x', 'y', 'w', 'h')), ('board', ('x', 'y', 'w', 'h', 'rows'))):
        o = scene.get(key)
        if not isinstance(o, dict) or not all(is_num(o.get(f)) for f in fields):
            rep.err('schema', 'scene.json %s needs numeric %s' % (key, ', '.join(fields)))
    seats = scene.get('seats')
    if not isinstance(seats, list) or not seats or not all(
            isinstance(s, dict) and isinstance(s.get('id'), str) and is_num(s.get('x')) and ('y' not in s or is_num(s['y'])) for s in seats):
        rep.err('schema', 'scene.json seats must be a non-empty list of {id, x}')
    elif len({s['id'] for s in seats}) != len(seats):
        rep.err('schema', 'scene.json seat ids must be unique')
    ent = scene.get('entries')
    if not isinstance(ent, dict) or not (is_num(ent.get('left')) and is_num(ent.get('right')) and ent['left'] < 0 < scene_size[0] < ent['right']):
        rep.err('schema', 'scene.json entries must put left < 0 and right > %d' % scene_size[0])
    chars = scene.get('characters')
    if not isinstance(chars, list) or not chars or not all(isinstance(n, str) for n in chars):
        rep.err('schema', 'scene.json characters must be a non-empty list of folder names')
    else:
        for n in chars:
            if not (root / 'chars' / n / 'manifest.json').is_file():
                rep.err('file', 'scene.json lists character %s but chars/%s/manifest.json is missing' % (n, n))
    lamps = scene.get('lamps')
    if not isinstance(lamps, list) or not all(isinstance(l, dict) and all(is_num(l.get(k)) for k in ('x', 'y', 'r')) for l in lamps):
        rep.err('schema', 'scene.json lamps must be a list of {x, y, r}')

    def need_image(rel, what, size=scene_size):
        arr = load_rgba(root / rel, rep)
        if arr is not None and size is not None and (arr.shape[1], arr.shape[0]) != tuple(size):
            rep.err('schema', '%s %s must be %dx%d, got %dx%d' % (what, rel, size[0], size[1], arr.shape[1], arr.shape[0]))
            return None
        return arr

    fl = scene.get('floorLight')
    if fl is None:
        pass                                          # no visible floor in this artwork
    elif not isinstance(fl, dict) or not isinstance(fl.get('file'), str) or not (
            isinstance(fl.get('anchor'), list) and len(fl['anchor']) == 2 and all(is_num(v) for v in fl['anchor'])):
        rep.err('schema', 'scene.json floorLight needs file and anchor [x, y]')
    else:
        need_image(fl['file'], 'floorLight', None)

    planes = scene.get('planes')
    if planes is not None:
        if not (isinstance(planes, dict) and all(isinstance(planes.get(k), str) for k in ('right', 'left'))
                and all(is_num(planes.get(k)) for k in ('y', 'height', 'from', 'to', 'period', 'duration'))
                and 0 < planes['duration'] <= planes['period']):
            rep.err('schema', 'scene.json planes needs right/left files and numeric y, height, from, to, period >= duration > 0')
        else:
            for k in ('right', 'left'):
                need_image(planes[k], 'plane', None)
    layers = scene.get('layers')
    if not isinstance(layers, list) or not layers:
        rep.err('schema', 'scene.json layers must be a non-empty list')
        return scene
    seen = set()
    for layer in layers:
        lid = layer.get('id') if isinstance(layer, dict) else None
        if not isinstance(lid, str) or lid in seen:
            rep.err('schema', 'layer id missing or duplicated: %r' % (lid,))
            continue
        seen.add(lid)
        if layer.get('group') not in GROUPS:
            rep.err('schema', 'layer %s: group must be one of %s' % (lid, '/'.join(GROUPS)))
        if not isinstance(layer.get('tint'), bool):
            rep.err('schema', 'layer %s: tint must be true or false' % lid)
        variants = layer.get('variants')
        if not isinstance(variants, list) or not variants or not all(
                isinstance(v, dict) and is_num(v.get('elev')) and isinstance(v.get('file'), str) for v in variants):
            rep.err('schema', 'layer %s: variants must be a non-empty list of {elev, file}' % lid)
            continue
        if 'emission' in layer:
            if layer.get('emissionKey') not in EMISSION_KEYS:
                rep.err('schema', 'layer %s: emissionKey must be one of %s' % (lid, '/'.join(EMISSION_KEYS)))
            need_image(layer['emission'], 'emission')
        loaded = []
        for v in sorted(variants, key=lambda v: v['elev']):
            arr = need_image(v['file'], 'layer %s variant' % lid)
            loaded.append((v, arr))
        if lid == 'interior':
            w = scene.get('window') or {}
            for v, arr in loaded:
                if arr is not None and all(is_num(w.get(k)) for k in ('x', 'y', 'w', 'h')):
                    win = arr[int(w['y']):int(w['y'] + w['h']), int(w['x']):int(w['x'] + w['w']), 3]
                    if win.size and (win < 16).mean() < 0.3:
                        rep.err('schema', 'interior %s must be transparent where the window glass is (only %.0f%% of the window area is)' % (v['file'], 100 * (win < 16).mean()))
        for (va, a), (vb, b) in zip(loaded, loaded[1:]):
            if a is None or b is None:
                continue
            ai = iou(a[..., 3] > 127, b[..., 3] > 127)
            if ai < ALPHA_IOU_MIN:
                rep.err('alignment', 'layer %s: alpha outlines of %s and %s differ (IoU %.3f < %.2f)' % (lid, va['file'], vb['file'], ai, ALPHA_IOU_MIN))
            if layer.get('cutFrom'):
                continue                              # cut with one mask from an already-checked layer
            if cv2 is None:
                rep.err('env', 'opencv-python-headless is required for the edge alignment check')
            else:
                ei = edge_agreement(a, b)
                if ei < EDGE_IOU_MIN:
                    rep.err('alignment', 'layer %s: line work of %s and %s differs (edge agreement %.3f < %.2f)' % (lid, va['file'], vb['file'], ei, EDGE_IOU_MIN))
    return scene


# ---------------------------------------------------------------------------- characters

def aligned(atlas, fa, fb):
    ox, oy = max(fa['ax'], fb['ax']), max(fa['ay'], fb['ay'])
    wc = ox + max(fa['w'] - fa['ax'], fb['w'] - fb['ax'])
    hc = oy + max(fa['h'] - fa['ay'], fb['h'] - fb['ay'])
    out = []
    for f in (fa, fb):
        c = np.zeros((hc, wc, 4), np.uint8)
        c[oy - f['ay']:oy - f['ay'] + f['h'], ox - f['ax']:ox - f['ax'] + f['w']] = \
            atlas[f['y']:f['y'] + f['h'], f['x']:f['x'] + f['w']]
        out.append(c)
    return out


def frame_error(atlas, fa, fb):
    a, b = aligned(atlas, fa, fb)
    pa = np.concatenate([a[..., :3].astype(np.float32) * a[..., 3:4] / 255.0, a[..., 3:4].astype(np.float32)], axis=2)
    pb = np.concatenate([b[..., :3].astype(np.float32) * b[..., 3:4] / 255.0, b[..., 3:4].astype(np.float32)], axis=2)
    return float(np.abs(pa - pb).mean())


def check_character(root, name, rep):
    cdir = root / 'chars' / name
    man = read_json(cdir / 'manifest.json', rep, 'character manifest')
    if man is None:
        return
    tag = 'char %s' % name
    if man.get('name') != name:
        rep.err('schema', '%s: manifest name %r does not match its folder' % (tag, man.get('name')))
    if not is_num(man.get('scale')) or man['scale'] <= 0:
        rep.err('schema', '%s: scale must be a positive number' % tag)
    if not isinstance(man.get('mirrorable'), bool):
        rep.err('schema', '%s: mirrorable must be true or false' % tag)
    atlas = load_rgba(cdir / str(man.get('atlas', 'atlas.png')), rep)
    frames, poses, clips = man.get('frames'), man.get('poses'), man.get('clips')
    if not isinstance(frames, list) or not frames or not isinstance(poses, dict) or not isinstance(clips, dict):
        rep.err('schema', '%s: frames (list), poses (object) and clips (object) are required' % tag)
        return
    good = True
    for i, f in enumerate(frames):
        if not (isinstance(f, dict) and all(is_int(f.get(k)) for k in ('x', 'y', 'w', 'h', 'ax', 'ay'))):
            rep.err('schema', '%s: frame %d needs integer x, y, w, h, ax, ay' % (tag, i))
            good = False
            continue
        if f['w'] <= 0 or f['h'] <= 0 or not (0 <= f['ax'] <= f['w'] and 0 <= f['ay'] <= f['h']):
            rep.err('schema', '%s: frame %d has an empty rectangle or an anchor outside it' % (tag, i))
            good = False
        elif atlas is not None and (f['x'] < 0 or f['y'] < 0 or f['x'] + f['w'] > atlas.shape[1] or f['y'] + f['h'] > atlas.shape[0]):
            rep.err('schema', '%s: frame %d lies outside the atlas' % (tag, i))
            good = False
    for pname, idx in poses.items():
        if not is_int(idx) or not 0 <= idx < len(frames):
            rep.err('schema', '%s: pose %s points at a missing frame' % (tag, pname))
            good = False
    clip_ok = {}
    for cid, c in clips.items():
        ok = isinstance(c, dict) and isinstance(c.get('loop'), bool) and is_num(c.get('fps')) and c['fps'] > 0 \
            and isinstance(c.get('frames'), list) and len(c['frames']) >= 1 \
            and all(is_int(i) and 0 <= i < len(frames) for i in c['frames']) \
            and c.get('from') in poses and c.get('to') in poses
        if not ok:
            rep.err('schema', '%s: clip %s is malformed (needs from/to poses, loop, fps > 0, valid frame indices)' % (tag, cid))
            clip_ok[cid] = False
            continue
        if cid.startswith('walk') and not (is_num(c.get('advance')) and c['advance'] > 0):
            rep.err('schema', '%s: walking clip %s needs advance > 0' % (tag, cid))
        if 'laneSwitchAt' in c and not (is_int(c['laneSwitchAt']) and 0 <= c['laneSwitchAt'] < len(c['frames'])):
            rep.err('schema', '%s: clip %s laneSwitchAt is outside the clip' % (tag, cid))
        clip_ok[cid] = True
    if not good or atlas is None:
        return

    missing = [c for c in REQUIRED_CLIPS if c not in clips] + ['pose:' + p for p in REQUIRED_POSES if p not in poses]
    active = not missing
    rep.chars[name] = 'active' if active else 'inactive'
    if not active:
        rep.warn('inactive', '%s lacks %s; it will not appear in the scene' % (tag, ', '.join(missing)))

    for cid, c in clips.items():
        if not clip_ok.get(cid):
            continue
        fr = [frames[i] for i in c['frames']]
        first_err = frame_error(atlas, fr[0], frames[poses[c['from']]])
        if first_err > SEAM_MAX_ERR:
            rep.err('seam', '%s: clip %s does not start on pose %s (error %.1f > %.0f)' % (tag, cid, c['from'], first_err, SEAM_MAX_ERR))
        if c['loop']:
            steps = [frame_error(atlas, fr[i], fr[i + 1]) for i in range(len(fr) - 1)]
            wrap = frame_error(atlas, fr[-1], fr[0])
            # the last step is judged against the others so a bad final frame cannot raise its own limit
            normal = steps[:-1] if len(steps) > 1 else []
            limit = max(SEAM_MAX_ERR, LOOP_SEAM_FACTOR * max(normal, default=0.0))
            for what, e in (('wraps', wrap), ('ends', steps[-1] if len(steps) > 1 else 0.0)):
                if e > limit:
                    rep.err('seam', '%s: loop %s jumps when it %s (error %.1f > %.1f)' % (tag, cid, what, e, limit))
        else:
            last_err = frame_error(atlas, fr[-1], frames[poses[c['to']]])
            if last_err > SEAM_MAX_ERR:
                rep.err('seam', '%s: clip %s does not end on pose %s (error %.1f > %.0f)' % (tag, cid, c['to'], last_err, SEAM_MAX_ERR))

    if active:
        fwd, back = {}, {}
        for cid, c in clips.items():
            if clip_ok.get(cid):
                fwd.setdefault(c['from'], set()).add(c['to'])
                back.setdefault(c['to'], set()).add(c['from'])

        def reach(graph, start):
            seen, q = {start}, deque([start])
            while q:
                n = q.popleft()
                for m in graph.get(n, ()):
                    if m not in seen:
                        seen.add(m)
                        q.append(m)
            return seen
        out_of = reach(fwd, 'walk_r')
        into = reach(back, 'walk_r')
        used = set(fwd) | set(back)
        for node in sorted(used):
            if node not in out_of:
                rep.err('graph', '%s: pose %s cannot be reached from walk_r' % (tag, node))
            if node not in into:
                rep.err('graph', '%s: pose %s has no way back to walk_r' % (tag, node))
    size = sum(p.stat().st_size for p in cdir.iterdir() if p.is_file())
    if size > BUDGET_CHAR:
        rep.err('budget', '%s: %d bytes exceeds %d' % (tag, size, BUDGET_CHAR))


def dir_size(path):
    return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file())


def check_assets(root):
    root = Path(root)
    rep = Report()
    scene = check_scene(root, rep)
    cdir = root / 'chars'
    names = sorted(p.name for p in cdir.iterdir() if p.is_dir()) if cdir.is_dir() else []
    if not names:
        rep.err('file', 'no character folders under %s' % cdir)
    for name in names:
        check_character(root, name, rep)
    if scene is not None:
        bg = root / 'bg'
        if bg.is_dir() and dir_size(bg) > BUDGET_BG and not scene.get('placeholder'):
            rep.err('budget', 'backgrounds are %d bytes, limit %d' % (dir_size(bg), BUDGET_BG))
        if scene.get('placeholder') and dir_size(root) > BUDGET_PLACEHOLDER_TOTAL:
            rep.err('budget', 'placeholder art is %d bytes, limit %d' % (dir_size(root), BUDGET_PLACEHOLDER_TOTAL))
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default='ui/web/lounge/assets')
    args = ap.parse_args(argv)
    rep = check_assets(args.root)
    for name, state in sorted(rep.chars.items()):
        print('%-8s %s' % (name, state))
    for w in rep.warnings:
        print('WARN  ' + w)
    for e in rep.errors:
        print('ERROR ' + e)
    print('lounge assets: %s (%d errors, %d warnings)' % ('OK' if rep.ok else 'FAILED', len(rep.errors), len(rep.warnings)))
    return 0 if rep.ok else 1


if __name__ == '__main__':
    sys.exit(main())
