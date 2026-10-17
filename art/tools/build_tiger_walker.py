#!/usr/bin/env python3
"""Build the tiger walk loop and pack it into a walker character for the lounge.

    python3 art/tools/build_tiger_walker.py

1. legs: the cells of art/cutouts/tiger_walk_b/left_*.png, plus the "other foot forward" poses made
   by flipping only the legs (mirror_legs.py) - Gemini never drew that foot stepping;
2. one upper body for every frame (lockbody.py), written to art/cutouts/tiger_walk_b/loop/left_*;
3. right-facing copies with the T2 letters kept readable (mirror_logo.py) -> loop/right_*;
4. <out>/{atlas, manifest.json}: walk_r / walk_l with the face patches. The scene does not use this
   directly any more: art/tools/build_character.py builds the whole tiger (walking, sitting) on top
   of it. Run on its own (python3 art/tools/build_tiger_walker.py [--out DIR]) it writes to a
   temporary folder unless --out is given.
Every frame shares one anchor on the upper body, so the body glides level and only the legs move.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import numpy as np
import cv2
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lockbody import hem_rows, navy_mask                                       # noqa: E402
from walk_bob import spread, bob_series, quantize, stretch_legs, bottom_row    # noqa: E402
import face_patch                                                              # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CELLS = ROOT / 'art/cutouts/tiger_walk_b'
SRC = CELLS / 'loop'
TOOLS = Path(__file__).resolve().parent
# leg order: one step, chosen by measuring the feet (art/README.md). The legs look alike, so one
# step repeated reads as left-right-left as long as the planted foot only ever moves backward.
# (as drawn by Gemini, put in pose order). The flipped-legs poses ('m..', mirror_legs.py)
# turned out worse - toes pointing backward, a doubled frame - so they are not used until a proper
# "other foot forward" drawing arrives (docs/LOUNGE_ART_PROMPTS.md).
ORDER = ['22', '30', '03', '10', '12', '21']
# Hand-made in-betweens (stride_tween.py): (insert before loop frame i, made from loop frame i,
# front foot back px, back foot forward px, front foot lift px). Fills the long gap where the
# swinging foot lands, measured from the foot positions.
TWEENS = [(3, 30, 40, 10)]
KEEP_IN_SWAP = {1, 2}     # loop frames (after the in-betweens) with both feet under the body
BASE = '10'               # the upper body every frame shares
SCALE = 0.62          # atlas pixels per source pixel (keeps the atlas small)
FPS, ADVANCE = 10, 26  # frames per second, scene px moved per frame (matches the planted foot, see footslip check)
# walking bob (walk_bob.py): leg ~ hip to sole in source px, pp = peak-to-peak as a share of the figure
BOB_LEG, BOB_PP = 100, 0.01

# Face variants (face_patch.py): coordinates in loop/left_*.png px (the base head, shared by every
# frame); donor boxes in the cells of the face sheet (walking left like the loop, so no flip).
# The base eyes are pupils at (74, 95) and (123.5, 96); the mouth is the small ":3" under the nose.
_EYES = [dict(e=(74, 95.5, 6, 9), skin=(67, 86)), dict(e=(123.5, 96, 6, 9), skin=(122, 83))]
FACES = dict(
    sheet='art/sources/tiger_walk_sheet_faces_gemini.webp', donor_upscale=2,
    preview_box=(40, 60, 160, 145),
    variants={
        # closed eyes, the lids curving down (f_13)
        'blink': dict(cell='13', scale=1.6, erase=_EYES, feats=[
            dict(box=(30, 39, 50, 54), at=(74, 98)), dict(box=(62, 39, 86, 54), at=(124, 98.5))]),
        # closed smiling eyes (f_00)
        'smile': dict(cell='00', scale=1.6, erase=_EYES, feats=[
            dict(box=(31, 42, 48, 55), at=(74, 96)), dict(box=(63, 42, 83, 55), at=(124, 96.5))]),
        # smiling eyes (f_00) and the open laughing mouth (f_31)
        'laugh': dict(cell='00', scale=1.6, erase=_EYES + [(97.5, 126, 25, 8, 0, False)], feats=[
            dict(box=(31, 42, 48, 55), at=(74, 96)), dict(box=(63, 42, 83, 55), at=(124, 96.5)),
            dict(cell='31', box=(37, 56, 70, 76), at=(95, 131.5), scale=1.95, color=True)]),
    },
)


def legs_of(a):
    """(legs mask, hem row) of a finished left-facing loop frame: what hangs under the hoodie hem,
    without the suitcase."""
    hb, hem = hem_rows(a)
    H, W = a.shape[:2]
    yy = np.mgrid[0:H, 0:W][0]
    cand = (a[..., 3] > 20) & (yy > hem - 6) & ~navy_mask(a, 2)
    n, lab, st, _ = cv2.connectedComponentsWithStats(cand.astype(np.uint8))
    if n < 2:
        return np.zeros((H, W), bool), hem
    return lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA])), hem


def bob_frames(seq, tmp):
    """The body a little higher while the legs pass each other (walk_bob.py): returns the frames
    with their legs stretched so the lowest foot ends on the frame's own anchor row, and those anchors
    (atlas px, measured from the top of the head, which every frame shares)."""
    ims = [np.asarray(Image.open(f).convert('RGBA')).astype(np.float32) for f in seq]
    legs = [legs_of(a) for a in ims]
    feet = [bottom_row(m) for m, _ in legs]
    ground = float(np.median(feet))
    s = np.array([spread(m) for m, _ in legs]); s -= s.min()
    bob = quantize(bob_series(s, BOB_LEG, BOB_PP * ground * SCALE))
    ay0 = int(round(ground * SCALE)) - 1
    ays = [ay0 + b for b in bob]
    out = []
    for i, (a, (m, hem)) in enumerate(zip(ims, legs)):
        pad = 16
        a = np.concatenate([a, np.zeros((pad,) + a.shape[1:], np.float32)], 0)
        m = np.concatenate([m, np.zeros((pad, m.shape[1]), bool)], 0)
        res = stretch_legs(a, m, hem + 4, feet[i], (ays[i] + 1) / SCALE)
        res = res[:bottom_row(res[..., 3] > 0) + 1]
        f = tmp / ('bob_%d.png' % i)
        Image.fromarray(res.clip(0, 255).round().astype(np.uint8)).save(f)
        out.append(f)
    info = dict(s=[round(float(v), 1) for v in s], bob=bob, ay=ays, feet_before=feet,
                pp_scene=round((max(bob) - min(bob)) / SCALE, 2))
    return out, ays, info


def anchor_x(im):
    a = np.asarray(im)[..., 3] > 128
    top = int(np.nonzero(a.any(1))[0][0])
    xs = np.nonzero(a[top:top + int(im.height * 0.35)])[1]
    return int(round(xs.mean()))


def run(*args):
    subprocess.run([sys.executable, '-I', *map(str, args)], check=True, stdout=subprocess.DEVNULL)


def _swap(src, dst):
    run(TOOLS / 'swap_legs.py', src, dst)
    return dst


def build_loop():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp); cells, out = tmp / 'cells', tmp / 'loop'
        cells.mkdir()
        for p in CELLS.glob('left_*.png'):
            shutil.copy(p, cells / ('f_' + p.stem[5:] + '.png'))
        for n in {o[1:] for o in ORDER if o.startswith('m')}:
            run(TOOLS / 'mirror_legs.py', cells / ('f_%s.png' % n), cells / ('f_m%s.png' % n))
        run(TOOLS / 'lockbody.py', cells, BASE, out, ','.join(ORDER))
        seq = [out / ('f_%d.png' % i) for i in range(len(ORDER))]
        for k, (at, front, back, lift) in enumerate(sorted(TWEENS, reverse=True)):
            t = tmp / ('tween_%d.png' % k)
            run(TOOLS / 'stride_tween.py', seq[at], t, '--front', front, '--back', back, '--lift', lift, '--right', 300)
            seq.insert(at, t)
        # second step: the same frames with the legs' roles swapped (far leg steps out), so the
        # loop alternates near leg / far leg instead of the near leg kicking out every step
        # (frames with both feet together under the body stay as drawn: the split would cut a foot,
        # and which leg is near hardly shows there)
        seq += [f if i in KEEP_IN_SWAP else _swap(f, tmp / ('swap_%d.png' % i)) for i, f in enumerate(list(seq))]
        seq, ays, info = bob_frames(seq, tmp)
        SRC.mkdir(exist_ok=True)
        for old in SRC.glob('*.png'):
            old.unlink()
        for i, f in enumerate(seq):
            shutil.copy(f, SRC / ('left_%d.png' % i))
            run(TOOLS / 'mirror_logo.py', f, SRC / ('right_%d.png' % i))
    return len(seq), ays, info


def main(out=None, lossless=False, quiet=False):
    """Build into out (a folder; default: a new temporary one). lossless=True writes atlas.png
    (for build_character.py, which re-encodes the whole atlas once). Returns the folder."""
    OUT = Path(out) if out else Path(tempfile.mkdtemp(prefix='tiger_walker_'))
    n, ays, info = build_loop()
    if not quiet:
        print('tiger bob: s %s -> bob %s atlas px (%.1f scene px peak-to-peak)' % (info['s'], info['bob'], info['pp_scene'] * 1.25))
    # same height for all (pad at the bottom, before resizing so every frame is resampled alike and
    # the shared head stays pixel-identical): the frames all start at the top of the shared head
    srcs = [Image.open(SRC / ('%s_%d.png' % (side, i))).convert('RGBA') for side in ('right', 'left') for i in range(n)]
    hs = max(im.height for im in srcs)

    def to_atlas(im):
        pad = Image.new('RGBA', (im.width, hs), (0, 0, 0, 0)); pad.paste(im, (0, 0))
        return pad.resize((round(im.width * SCALE), round(hs * SCALE)), Image.LANCZOS)
    frames_img = [to_atlas(im) for im in srcs]
    # face variants (face_patch.py) made on the left-facing base frame, mirrored for walk_r
    base = np.asarray(srcs[n]).astype(np.float32)
    varied = {k: to_atlas(Image.fromarray(v.clip(0, 255).round().astype(np.uint8)))
              for k, v in face_patch.variants(base, FACES).items()}
    W = sum(im.width for im in frames_img[:n]) + 2 * n + 2
    H = max(im.height for im in frames_img) * 2 + 4
    atlas = Image.new('RGBA', (max(W, sum(im.width for im in frames_img[n:]) + 2 * n + 2), H), (0, 0, 0, 0))
    frames, x, y, rowh = [], 0, 0, max(im.height for im in frames_img) + 2
    # every frame is cropped at the top of the (shared) head; each has its own foot line (the bob)
    for k, im in enumerate(frames_img):
        if k == n: x, y = 0, rowh
        atlas.paste(im, (x, y))
        ax, ay = anchor_x(im), ays[k % n]
        frames.append({'x': x, 'y': y, 'w': im.width, 'h': im.height, 'ax': ax, 'ay': ay})
        x += im.width + 2
    patches = face_patch.direction_patches(frames_img[n], varied, list(range(n)), flip=True) + \
        face_patch.direction_patches(frames_img[n], varied, list(range(n, 2 * n)))
    atlas = face_patch.attach(atlas, frames, patches)
    OUT.mkdir(parents=True, exist_ok=True)
    aname = 'atlas.png' if lossless else 'atlas.webp'
    if lossless:
        atlas.save(OUT / aname)
    else:
        atlas.save(OUT / aname, lossless=False, quality=90, method=6)
    man = {
        'name': 'tiger_walker', 'walker': True, 'pass': 'r', 'atlas': aname,
        'scale': round(1 / SCALE, 4), 'mirrorable': False, 'frames': frames,
        'poses': {'walk_r': 0, 'walk_l': n},
        'clips': {
            'walk_r': {'from': 'walk_r', 'to': 'walk_r', 'loop': True, 'fps': FPS, 'frames': list(range(n)), 'advance': ADVANCE},
            'walk_l': {'from': 'walk_l', 'to': 'walk_l', 'loop': True, 'fps': FPS, 'frames': list(range(n, 2 * n)), 'advance': ADVANCE},
        },
    }
    (OUT / 'manifest.json').write_text(json.dumps(man, separators=(',', ':')))
    if not quiet:
        print('tiger_walker: atlas %dx%d, %d bytes -> %s' % (atlas.width, atlas.height, (OUT / aname).stat().st_size, OUT))
    return OUT


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', help='output folder (default: a new temporary folder)')
    main(ap.parse_args().out)
