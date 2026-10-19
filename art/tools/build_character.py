#!/usr/bin/env python3
"""Build a whole lounge character (walk across, walk to a sofa seat, sit, seated life, stand up,
walk away) from the still Gemini art (art/README.md, docs/LOUNGE_SCENE_DESIGN.md).

    python3 art/tools/build_character.py [tiger rabbit turtle penguin]   # default: all in CHARS
    python3 art/tools/build_character.py tiger --walk-cache DIR          # reuse walker builds in DIR
    python3 art/tools/build_character.py tiger --dump DIR                # also save every new frame

Writes ui/web/lounge/assets/chars/<name>/{atlas.webp, manifest.json}: one manifest that can both pass
by (walker: true, walk_r / walk_l) and sit (the full clip set of 6.3). The output is deterministic
(same input, same bytes).

Where each piece comes from:
- walk_r / walk_l: the walker builders (build_tiger_walker.py, build_walker.py) build into a temporary
  folder; their whole atlas (frames, bob anchors, face patches) is copied in unchanged, and every new
  frame is added below it, in the same atlas px (manifest scale stays the walker's).
- one pose set per seat FACING (scene.json seats[].facing: 'f' front, 'l' three-quarters left; see
  CHARS below and docs/LOUNGE_SCENE_DESIGN.md 7.8); clips and poses for a facing other than 'f' are
  named '<id>@<facing>'. A facing without convincing art is simply not built for that character.
- standing at the seat: 'f' one standing front cell; 'l' the walker's own walk_l frame (it already
  faces three-quarters left). Seated poses: seated cells, mirrored where they face the other way.
  Every still is scaled into the walker's atlas px by its head width (cfg 'f' = walker head width /
  cell head width), so the head keeps its size from pose to pose; one factor per sheet.
- seated stills are placed by their BUTT CONTACT point (cfg 'seat') on the seat's contact point
  (scene.json seats[].cx/cy, measured on the sofa cushions), not by their lowest foot.
- turns (walk <-> standing at the seat): a "paper flip": the side view squeezes to a sliver around its
  anchor, the other view grows out of it (feet fixed). The renderer slides the foot line from the aisle
  to the seat's floor point meanwhile (renderer.js place()).
- sit_down / stand_up: crouch, hop backwards up onto the cushion; at the top of the hop the standing
  picture is replaced by the seated one (both stretched, so the cut reads as motion), which drops onto
  the cushion and squashes. No cross-fade: two pictures are never shown at once. stand_up is the same
  backwards. Seated people are drawn over the sofa front (scene.json seatedInFront), so their legs
  show; the sofa's arm (layer group 'arms') covers them where it is nearer. A facing can give its
  own frame indices instead (fcfg 'sit_frames' / 'stand_frames', e.g. a real climb).
- sit_idle: the seated pose breathing (baked +0.6 % / +1.2 % vertical stretch about the seat) with
  blink patches (frame.v, face_patch.py) where the art has a closed-eye donor.
- activities: doze (2-3 doze cells, nodding by hard cuts behind a small squash, a slow breathing
  lift), phone / call (a seated cell holding the prop; in and out by a squash and a stretch).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import face_patch   # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
CHARS_DIR = ROOT / 'ui/web/lounge/assets/chars'
SCENE_CHAR_SCALE = 1.25        # scene.json charScale
SCENE = json.loads((ROOT / 'ui/web/lounge/assets/scene.json').read_text())
# per facing, from a seat's floor point (seats[].x, y: where the character stands before it hops on) to
# its butt contact point on the cushion (seats[].cx, cy), in scene px at seat scale 1: 'rest' up, 'dx'
# right (scene.json seatFacings; art/tools/build_lounge_scene.py derives x, y from the measured cx, cy)
FACINGS = SCENE['seatFacings']
SUFFIX = {'f': ''}                 # clip / pose names per facing: 'f' plain, others '@<facing>'
sfx = lambda facing: SUFFIX.get(facing, '@' + facing)
S = 'art/sources/'
RABBIT_WALK = S + 'rabbit_walk_sheet_4x4_gemini.webp'
STAND_A = S + 'stand_poses_tiger_turtle_penguin_a_gemini.webp'
CLIMB_A = S + 'tiger_climb_sit_sheet_a_gemini.webp'
TIGER_DOZE = S + 'tiger_doze_sheet_gemini.webp'
ALL_DOZE = S + 'all_doze_sheet_gemini.webp'
RABBIT_POSE = S + 'rabbit_pose_sheet_4x4_gemini.webp'
GROUP_SIT = S + 'chars_sitting_group_gemini.webp'
GROUP_WALK = S + 'chars_walking_group_gemini.webp'
GROUP_ORDER = ['tiger', 'rabbit', 'turtle', 'penguin']

# A still: (sheet, cell) of a 4x4 sheet (cut_sheet.py names, f_<row><col>), (group sheet, animal), or
# (group sheet, 'region', polygon) cut by hand.
# f: atlas px per source px (walker head width / the cell's head width, rows.py-style measurements:
#    the widest opaque run across the cheeks; one factor per sheet).
# x: stand_front only: the column between the feet (measured when not given).
# seat: seated stills only: (x, y) of the BUTT CONTACT - the middle of the bottom of the hips, where the
#    figure touches the seat (not the lowest foot) - in px of the finished still (after 'mirror').
#    It is placed on the seat's contact point (scene.json seats[].cx/cy) at every seat of that facing.
# mirror: flip left-right after cutting and after the face fixes (whose coordinates are in the
#    unflipped still); 'logo' also turns the gold T2 letters back (mirror_logo.py).
# keep: 'largest' drops separate pieces (a backpack on the floor, the 'zz' of a dozing cell).
# cut / fill / ink: polygons (source px) to erase / repaint with the cloth colour / outline.
#
# FACINGS (docs/LOUNGE_SCENE_DESIGN.md 7.8): every seat has a facing - 'f' (the left sofa, seen from
# the front) or 'l' (the right sofa, turned three-quarters toward the front-left). A character has one
# set of seated stills per facing it can use, chosen from cells drawn facing that way (or mirrored
# from cells facing the other way); a facing with no convincing art is left out, and the director
# never seats the character there. For 'l' the standing pose is the walker's own walk_l frame (a
# three-quarter view facing left): the character stops, already facing the way the seat faces, and
# hops backwards onto it.
CHARS = {
    'tiger': dict(walker='tiger', facings={
        'f': dict(
            # surprised "o" mouth -> the small smile of the seated cell (same sheet family, 1.13x bigger there)
            stand=dict(src=(STAND_A, '02'), f=0.479, face=dict(sheet=CLIMB_A, fix=dict(
                cell='23', scale=1.13, erase=[(132, 177, 14, 17)], feats=[dict(box=(90, 128, 148, 152), at=(127, 163))]))),
            # facing front; blink: the closed eyes of the climb sheet's cheek-on-hand cell, one on each pupil
            sit=dict(src=(CLIMB_A, '23'), f=0.542, seat=(175, 330), face=dict(sheet=CLIMB_A, variants={'blink': dict(
                cell='32', scale=0.85, erase=[dict(e=(91.7, 106.7, 7, 10), skin=(80, 108)), dict(e=(153.3, 106, 7, 10), skin=(165, 110))],
                feats=[dict(box=(40, 100, 76, 122), at=(91.7, 110)), dict(box=(112, 100, 154, 126), at=(153.3, 110))])})),
            # the most frontal cells of the tiger doze sheet
            doze=[dict(src=(TIGER_DOZE, '21'), f=1.139, seat=(85, 160)), dict(src=(TIGER_DOZE, '11'), f=1.139, seat=(85, 160)),
                  dict(src=(TIGER_DOZE, '13'), f=1.139, seat=(85, 160))],
        ),
        'l': dict(
            stand='walk',
            # the climb sheet's "sitting on the ledge" cell: three-quarters left, one leg over the edge
            sit=dict(src=(CLIMB_A, '22'), f=0.542, seat=(240, 320), face=dict(sheet=CLIMB_A, variants={'blink': dict(
                cell='32', scale=0.85, erase=[dict(e=(152, 126, 7, 10), skin=(140, 128)), dict(e=(208, 126, 7, 10), skin=(220, 130))],
                feats=[dict(box=(40, 100, 76, 122), at=(152, 129)), dict(box=(112, 100, 154, 126), at=(208, 129))])})),
            # cut by hand from the group picture (three-quarters left): the automatic split cut off the
            # right paw where it overlaps the rabbit's suitcase (sheet px; the suitcase is left out)
            phone=dict(src=(GROUP_SIT, 'region', [(0, 250), (340, 250), (340, 575), (347, 580), (347, 621), (360, 628),
                                                   (371, 642), (375, 665), (370, 690), (330, 712), (0, 712)]), f=0.523, seat=(190, 345)),
            doze=[dict(src=(TIGER_DOZE, '10'), f=1.139, seat=(85, 160)), dict(src=(TIGER_DOZE, '02'), f=1.139, seat=(85, 160)),
                  dict(src=(TIGER_DOZE, '00'), f=1.139, seat=(85, 160))],
        ),
    }),
    'rabbit': dict(walker='rabbit', facings={
        'f': dict(
            # the boots of the cell above poke into this one, touching the left ear tip: cut away
            stand=dict(src=(RABBIT_POSE, '31'), f=0.528,
                       cut=[[(48, 0), (112, 0), (112, 52), (99, 52), (93, 40), (84, 26), (74, 17), (62, 12), (48, 8)], [(100, 0), (186, 0), (186, 35), (172, 43), (160, 49), (100, 54)]]),
            # no open-eyed seated rabbit exists: the eyes are opened with the walk sheet's eyes (base cell
            # f_03, 0.53x), and the drawn closed smiling eyes are the blink
            sit=dict(src=(ALL_DOZE, '12'), f=1.167, seat=(75, 160), face=dict(sheet=RABBIT_WALK, fix=dict(
                cell='03', scale=0.53, erase=[(70.5, 86.5, 11, 6.5), (107, 77, 9, 5.5)],
                feats=[dict(box=(184, 139, 214, 169), at=(70.5, 85)), dict(box=(246, 136, 272, 164), at=(107, 75.5))]),
                variants={'blink': 'orig'})),
            # the only frontal sleeping rabbit is this same cell with its own closed eyes
            doze=[dict(src=(ALL_DOZE, '12'), f=1.167, seat=(75, 160))],
        ),
        'l': dict(
            stand='walk',
            # three-quarters left, eyes closed in the cell: opened with the walk sheet's eyes; blink = as drawn
            sit=dict(src=(ALL_DOZE, '10'), f=1.167, seat=(65, 160), face=dict(sheet=RABBIT_WALK, fix=dict(
                cell='03', scale=0.5, erase=[(27, 84, 10, 5.5), (61, 84, 11, 5.5)],
                feats=[dict(box=(184, 139, 214, 169), at=(27, 82)), dict(box=(246, 136, 272, 164), at=(61, 81.5))]),
                variants={'blink': 'orig'})),
            # the group picture's call faces right: mirrored. The suitcase and the bag beside her are cut
            # away; the sleeve they covered is repainted
            call=dict(src=(GROUP_SIT, 'rabbit'), f=0.55, mirror=True, seat=(185, 335),
                      cut=[[(0, 178), (60, 178), (80, 200), (77, 225), (75, 255), (77, 290), (84, 325), (98, 343), (118, 350),
                            (134, 352), (134, 407), (0, 407)]],
                      fill=[([(76, 222), (134, 222), (134, 350), (118, 350), (98, 343), (84, 325), (77, 290), (75, 255)], (130, 240, 150, 300))],
                      ink=[[(80, 200), (77, 225), (75, 255), (77, 290), (84, 325), (98, 343), (118, 350), (138, 351)]]),
            # f_13 faces right: mirrored, its 'zz' dropped (mirrored letters)
            doze=[dict(src=(ALL_DOZE, '11'), f=1.167, seat=(100, 150)),
                  dict(src=(ALL_DOZE, '13'), f=1.167, mirror=True, keep='largest', seat=(80, 150))],
        ),
    }),
    # no frontal seated turtle exists (every cell is three-quarters): it only takes the right sofa
    'turtle': dict(walker='turtle', facings={
        'l': dict(
            stand='walk',
            # the waking-up cell (faces right, mirrored): its surprised "o" mouth becomes the sleeping
            # cell's small smile; blink from the same sleeping cell (same sheet, same size)
            sit=dict(src=(ALL_DOZE, '22'), f=1.3, mirror=True, seat=(75, 150), face=dict(sheet=ALL_DOZE, fix=dict(
                cell='20', scale=1.0, erase=[(95, 68, 9, 6.5)], feats=[dict(box=(96, 73, 120, 86), at=(95, 67))]),
                variants={'blink': dict(cell='20', scale=1.0, erase=[(75, 51, 11, 11), (108, 49, 8, 10)],
                                        feats=[dict(box=(80, 55, 104, 70), at=(75, 53)), dict(box=(116, 66, 131, 77), at=(108, 51))])})),
            # the group picture's turtle already faces left (ticket = 'phone'); not mirrored (T2 on the ticket)
            phone=dict(src=(GROUP_SIT, 'turtle'), f=0.6, seat=(180, 300)),
            doze=[dict(src=(ALL_DOZE, '20'), f=1.3, mirror=True, seat=(80, 150)), dict(src=(ALL_DOZE, '21'), f=1.3, mirror=True, seat=(80, 150)),
                  dict(src=(ALL_DOZE, '23'), f=1.3, mirror=True, keep='largest', seat=(80, 150))],
        ),
    }),
}


# ---------------------------------------------------------------- images (straight RGBA float32)
def to_pil(a):
    return Image.fromarray(np.asarray(a).clip(0, 255).round().astype(np.uint8))


def from_pil(im):
    return np.asarray(im.convert('RGBA')).astype(np.float32)


def resize(a, w, h):
    """LANCZOS on premultiplied colour (no dark fringe), back to straight RGBA."""
    im = to_pil(a).convert('RGBa').resize((max(1, int(round(w))), max(1, int(round(h)))), Image.LANCZOS)
    return from_pil(im.convert('RGBA'))


def premul(a):
    p = a.copy(); p[..., :3] *= p[..., 3:] / 255.; return p


def unpremul(p):
    out = p.copy(); al = p[..., 3:]
    out[..., :3] = np.where(al > 0, p[..., :3] * 255. / np.maximum(al, 1e-3), 0)
    return out


class Pic:
    """A frame picture in atlas px with its anchor (ax, ay): the point the renderer puts on the foot
    line (for seated pictures: a point below the figure, on the seat's line)."""
    def __init__(self, arr, ax, ay, tag='', faces=None):
        self.arr, self.ax, self.ay, self.tag = arr, float(ax), float(ay), tag
        self.faces = faces or {}          # face name -> the same picture with that face (frame.v)

    @property
    def w(self):
        return self.arr.shape[1]

    @property
    def h(self):
        return self.arr.shape[0]

    def moved(self, dy=0.0, dx=0.0):
        """The same picture drawn dy atlas px higher (dx to the right): only the anchor changes."""
        return Pic(self.arr, self.ax - dx, self.ay + dy, self.tag, self.faces)

    def squeezed(self, sx, shade=0.0):
        """Narrowed to sx of its width around the anchor column (a paper flip), a little darker."""
        w = max(2, int(round(self.w * sx)))
        a = resize(self.arr, w, self.h)
        if shade:
            a[..., :3] *= 1 - shade
        return Pic(a, self.ax * w / self.w, self.ay, self.tag + '~%.2f' % sx)

    def stretched(self, sy, pivot=None):
        """Scaled vertically by sy about the row `pivot` (default: the anchor row), which stays put."""
        pivot = self.ay if pivot is None else pivot
        h = int(round(self.h * sy))
        a = resize(self.arr, self.w, h)
        k = h / self.h
        faces = {n: resize(v, self.w, h) for n, v in self.faces.items()}
        # the pivot row moves from pivot to pivot * k: shift the anchor by the same amount
        return Pic(a, self.ax, self.ay + (pivot * k - pivot), self.tag + '^%.3f' % sy, faces)


def blend(a, b, t, tag=''):
    """Cross-fade: (1 - t) a + t b in premultiplied colour, both placed by their anchors."""
    left = max(a.ax, b.ax); top = max(a.ay, b.ay)
    W = int(np.ceil(left + max(a.w - a.ax, b.w - b.ax))) + 2
    H = int(np.ceil(top + max(a.h - a.ay, b.h - b.ay))) + 2
    acc = np.zeros((H, W, 4), np.float32)
    for p, wgt in ((a, 1 - t), (b, t)):
        ox, oy = left - p.ax, top - p.ay
        M = np.float32([[1, 0, ox], [0, 1, oy]])
        acc += wgt * cv2.warpAffine(premul(p.arr), M, (W, H), flags=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return Pic(unpremul(acc), left, top, tag)


def trimmed(p, box=False):
    """Crop to the opaque box, padded so the anchor lies inside (the manifest wants 0 <= ax <= w).
    box=True also returns a function that crops another picture of the same size the same way."""
    al = p.arr[..., 3] > 0.5
    ys, xs = np.nonzero(al)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    ax, ay = int(round(p.ax)), int(round(p.ay))
    x0, x1 = min(x0, ax), max(x1, ax + 1)
    y0, y1 = min(y0, ay), max(y1, ay + 1)
    H, W = p.h, p.w
    pad = [max(0, -y0), max(0, y1 - H), max(0, -x0), max(0, x1 - W)]
    arr = np.pad(p.arr, ((pad[0], pad[1]), (pad[2], pad[3]), (0, 0)))
    x0 += pad[2]; x1 += pad[2]; y0 += pad[0]; y1 += pad[0]
    out = arr[y0:y1, x0:x1]
    out[out[..., 3] < 0.5] = 0

    def same(other):
        o = np.pad(other, ((pad[0], pad[1]), (pad[2], pad[3]), (0, 0)))[y0:y1, x0:x1].copy()
        o[o[..., 3] < 0.5] = 0
        return o
    if box:
        return out, ax + pad[2] - x0, ay + pad[0] - y0, same
    return out, ax + pad[2] - x0, ay + pad[0] - y0


# ---------------------------------------------------------------- sources
class Sources:
    def __init__(self, tmp):
        self.tmp, self.cache = Path(tmp), {}

    def cells(self, sheet):
        if sheet not in self.cache:
            out = self.tmp / ('cells_%d' % len(self.cache))
            subprocess.run([sys.executable, '-I', str(TOOLS / 'cut_sheet.py'), str(ROOT / sheet), str(out), '4', '4'],
                           check=True, stdout=subprocess.DEVNULL)
            self.cache[sheet] = out
        return self.cache[sheet]

    def group(self, sheet):
        if sheet not in self.cache:
            out = self.tmp / ('group_%d' % len(self.cache))
            out.mkdir()
            subprocess.run([sys.executable, '-I', str(TOOLS / 'cutout_white.py'), str(ROOT / sheet), str(out / 'g'),
                            '--split', '4', '--names', ','.join(GROUP_ORDER)], check=True, stdout=subprocess.DEVNULL)
            self.cache[sheet] = out
        return self.cache[sheet]

    def region(self, sheet, poly):
        """A figure cut from a group sheet by hand: the non-background pixels (cutout_white's mask)
        inside a polygon in sheet px, cropped to its box. For a figure that touches a neighbour's prop,
        where the automatic split would cut through it."""
        sys.path.insert(0, str(TOOLS))
        from cutout_white import background_mask
        rgb = np.asarray(Image.open(ROOT / sheet).convert('RGB'))
        m = np.zeros(rgb.shape[:2], np.uint8)
        cv2.fillPoly(m, [np.int32(poly)], 1)
        fg = (~background_mask(rgb, False)) & (m > 0)
        fg = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
        fg = lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        alpha = cv2.GaussianBlur(fg.astype(np.float32) * 255, (0, 0), 0.7)
        alpha[~cv2.dilate(fg.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)] = 0
        ys, xs = np.nonzero(fg)
        x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        return np.dstack([rgb, alpha]).astype(np.float32)[y0:y1, x0:x1].copy()

    def still(self, spec):
        """The source cell (straight RGBA float, source px), cleaned as the spec says."""
        sheet, cell = spec['src'][:2]
        if cell == 'region':
            a = self.region(sheet, spec['src'][2])
        elif cell in GROUP_ORDER:
            a = from_pil(Image.open(self.group(sheet) / ('g_%s.png' % cell)))
        else:
            a = from_pil(Image.open(self.cells(sheet) / ('f_%s.png' % cell)))
        if spec.get('keep') == 'largest':
            m = (a[..., 3] > 40).astype(np.uint8)
            n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
            big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
            a[~cv2.dilate((lab == big).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)] = 0
        for poly in spec.get('cut', []):
            m = np.zeros(a.shape[:2], np.uint8)
            cv2.fillPoly(m, [np.int32(poly)], 1)
            a[m > 0] = 0
        for poly, box in spec.get('fill', []):   # repaint what a prop covered with the cloth colour beside it
            m = np.zeros(a.shape[:2], np.uint8)
            cv2.fillPoly(m, [np.int32(poly)], 1)
            x0, y0, x1, y1 = box
            sample = a[y0:y1, x0:x1].reshape(-1, 4)
            col = np.median(sample[sample[:, 3] > 250, :3], 0)
            k = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.2)[..., None]
            a[..., :3] = a[..., :3] * (1 - k) + col * k
            a[..., 3] = np.where(m > 0, 255, a[..., 3])
        for line in spec.get('ink', []):         # an outline where a cut edge runs (polyline, source px)
            m = np.zeros(a.shape[:2], np.uint8)
            cv2.polylines(m, [np.int32(np.array(line) * 4)], False, 255, 10, cv2.LINE_AA, 2)
            k = (m.astype(np.float32) / 255)[..., None] * (a[..., 3:] > 0)
            a[..., :3] = a[..., :3] * (1 - k) + face_patch.LINE * k
        # empty rows and columns left at the bottom / right by the cleaning go (top-left stays, so the
        # source coordinates in CHARS stay valid)
        ys, xs = np.nonzero(a[..., 3] > 0)
        return a[:ys.max() + 1, :xs.max() + 1]


def torso_x(a, lo=0.5, hi=0.7):
    """Middle of the figure in its torso band (median opaque column), source px."""
    H = a.shape[0]
    ys, xs = np.nonzero(a[int(H * lo):int(H * hi), :, 3] > 128)
    return float(np.median(xs))


def feet_x(a, band=0.06):
    H = a.shape[0]
    ys, xs = np.nonzero(a[int(H * (1 - band)):, :, 3] > 128)
    return float((xs.min() + xs.max()) / 2)


def with_faces(a, spec):
    """(the still with its face fixed, {face name: the still with that face}) from spec['face']
    (face_patch.py, source px of the still): 'fix' changes the still itself (e.g. a surprised mouth
    made a small smile, eyes opened from another drawing of the same animal), each variant is a
    face_patch spec or 'orig' (the still as drawn, before the fix)."""
    fc = spec.get('face')
    if not fc:
        return a, {}
    every = dict(fc.get('variants', {}))
    if fc.get('fix'):
        every['__fix'] = fc['fix']
    cfg = dict(fc, variants={k: v for k, v in every.items() if isinstance(v, dict)})
    donors = face_patch.load_donors(cfg)
    up = fc.get('donor_upscale', 1)
    base = face_patch.apply(a, fc['fix'], donors, up) if fc.get('fix') else a
    out = {}
    for name, v in fc.get('variants', {}).items():
        out[name] = a if v == 'orig' else face_patch.apply(base, v, donors, up)
    return base, out


def scaled(a, faces, f):
    r = resize(a, a.shape[1] * f, a.shape[0] * f)
    return r, {n: resize(v, a.shape[1] * f, a.shape[0] * f) for n, v in faces.items()}


def standing(src, spec):
    """stand_front: anchored on the floor between the feet. Separate scraps (a pale floor shadow
    left by the cut-out) are dropped unless the spec says otherwise."""
    spec = dict(spec, keep=spec.get('keep', 'largest'))
    a = src.still(spec)
    x = spec.get('x', feet_x(a))
    a, faces = with_faces(a, spec)
    r, faces = scaled(a, faces, spec['f'])
    return Pic(r, x * r.shape[1] / a.shape[1], r.shape[0] - 1, 'stand', faces)


def mirrored(a, logo=False):
    """Left-right flip; logo=True turns the gold T2 letters back so they read (mirror_logo.py)."""
    if not logo:
        return a[:, ::-1].copy()
    with tempfile.TemporaryDirectory() as tmp:
        i, o = Path(tmp) / 'in.png', Path(tmp) / 'out.png'
        to_pil(a).save(i)
        subprocess.run([sys.executable, '-I', str(TOOLS / 'mirror_logo.py'), str(i), str(o)], check=True)
        return from_pil(Image.open(o))


def seated_still(src, spec):
    """(finished still, faces) in source px: cut, faces fixed, mirrored when the spec says so."""
    a = src.still(spec)
    a, faces = with_faces(a, spec)
    if spec.get('mirror'):
        logo = spec['mirror'] == 'logo'
        a, faces = mirrored(a, logo), {n: mirrored(v, logo) for n, v in faces.items()}
    return a, faces


def seated(src, spec, facing, k1):
    """A seated still anchored on the seat's floor point: its butt contact (spec 'seat', still px) lands
    FACINGS[facing] (rest up, dx right; scene px at seat scale 1, k1 scene px per atlas px) from it."""
    a, faces = seated_still(src, spec)
    r, faces = scaled(a, faces, spec['f'])
    k = r.shape[1] / a.shape[1]
    bx, by = spec['seat']
    fc = FACINGS[facing]
    return Pic(r, bx * k - fc['dx'] / k1, by * k + fc['rest'] / k1, 'sit', faces)


# ---------------------------------------------------------------- walker part
def walker_build(cfg, cache):
    """(atlas PIL, manifest dict) of the walker, built into cache (or a temporary folder)."""
    name = cfg['walker']
    d = Path(cache) / (name + '_walker')
    if not (d / 'manifest.json').is_file():
        d.parent.mkdir(parents=True, exist_ok=True)
        if name == 'tiger':
            import build_tiger_walker as T
            T.main(out=d, lossless=True, quiet=True)
        else:
            import build_walker as Wk
            frames, ays, bx, fig_h, _bob, faces = Wk.build(name, Wk.CHARS[name])
            Wk.pack(name, Wk.CHARS[name], frames, ays, bx, fig_h, faces, out_dir=d.parent, lossless=True, quiet=True)
    man = json.loads((d / 'manifest.json').read_text())
    return Image.open(d / man['atlas']).convert('RGBA'), man


def frame_pic(atlas, f):
    a = from_pil(atlas.crop((f['x'], f['y'], f['x'] + f['w'], f['y'] + f['h'])))
    return Pic(a, f['ax'], f['ay'], 'walk')


# ---------------------------------------------------------------- the character
class Builder:
    def __init__(self, name, cfg, walk_atlas, walk_man, src):
        self.name, self.cfg, self.src = name, cfg, src
        self.walk_atlas, self.walk_man = walk_atlas, walk_man
        self.frames = [dict(f) for f in walk_man['frames']]      # walker frames keep their indices
        self.pics = []                                            # new pictures (atlas placement later)
        self.entries = []                                         # (frame index, pic index, ax, ay)
        self.scale = walk_man['scale']
        self.clips, self.poses = {}, {}

    def add(self, pic):
        """A new frame (manifest index) showing pic; the same picture at another anchor reuses its pixels."""
        for i, p in enumerate(self.pics):
            if p is pic or (p.arr is pic.arr):
                break
        else:
            self.pics.append(pic)
            i = len(self.pics) - 1
        base = self.pics[i]
        idx = len(self.frames)
        self.frames.append(None)
        self.entries.append((idx, i, pic.ax - base.ax, pic.ay - base.ay))
        return idx

    def build(self):
        cfg, wm = self.cfg, self.walk_man
        add = self.add
        W_r = wm['clips']['walk_r']['frames'][0]
        W_l = wm['clips']['walk_l']['frames'][0]
        wr, wl = frame_pic(self.walk_atlas, wm['frames'][W_r]), frame_pic(self.walk_atlas, wm['frames'][W_l])
        self.poses['walk_r'], self.poses['walk_l'] = W_r, W_l      # the walker's own first loop frames
        shrink = {side: [add(w.squeezed(s, 0.12 * (1 - s))) for s in (0.7, 0.4, 0.12)] for side, w in (('r', wr), ('l', wl))}
        self.info = {}
        for facing, fcfg in cfg['facings'].items():
            self.build_facing(facing, fcfg, wr, wl, W_r, W_l, shrink)
        self.facings = sorted(cfg['facings'])
        return self

    def build_facing(self, facing, fcfg, wr, wl, W_r, W_l, shrink):
        add, x = self.add, sfx(facing)
        k1 = self.scale * SCENE_CHAR_SCALE                     # scene px per atlas px at seat scale 1
        fc = FACINGS[facing]
        rise, slide = fc['rest'] / k1, fc['dx'] / k1           # floor point -> butt contact, atlas px
        arc = 0.22 * rise
        self.info[facing] = dict(rest=fc['rest'], dx=fc['dx'])
        P = lambda n: n + x                                     # pose / clip name at this facing

        # ---- standing at the seat: the stand_front still, or ('walk') the walker's walk_l frame
        if fcfg['stand'] == 'walk':
            st, S0 = wl, W_l
            self.poses[P('stand')] = S0
            stand_pose = P('stand')
            grow = [add(wl.squeezed(s, 0.12 * (1 - s))) for s in (0.4, 0.75)]
            flip_r = [W_r] + shrink['r'] + grow + [S0]          # paper flip: facing right -> facing left
            self.clips[P('turn_r_front')] = dict(frm='walk_r', to=stand_pose, fps=12, frames=flip_r)
            self.clips[P('turn_front_r')] = dict(frm=stand_pose, to='walk_r', fps=12, frames=flip_r[::-1])
            self.clips[P('turn_l_front')] = dict(frm='walk_l', to=stand_pose, fps=12, frames=[S0])   # already facing left
            self.clips[P('turn_front_l')] = dict(frm=stand_pose, to='walk_l', fps=12, frames=[S0])
        else:
            st = standing(self.src, fcfg['stand'])
            S0 = add(st)
            stand_pose = 'stand_front' if facing == 'f' else P('stand')
            self.poses[stand_pose] = S0
            grow = [add(st.squeezed(s, 0.12 * (1 - s))) for s in (0.4, 0.75)]
            for side, W0 in (('r', W_r), ('l', W_l)):           # paper flip: side view -> front view
                seq = [W0] + shrink[side] + grow + [S0]
                self.clips[P('turn_%s_front' % side)] = dict(frm='walk_' + side, to=stand_pose, fps=12, frames=seq)
                self.clips[P('turn_front_%s' % side)] = dict(frm=stand_pose, to='walk_' + side, fps=12, frames=seq[::-1])

        # ---- sit_down / stand_up: a hop backwards up onto the cushion. No cross-fade: the standing
        # picture rises (stretched) to the top of the hop and is replaced there by the seated picture,
        # still in the air and stretched, which drops onto the cushion and squashes. Two different
        # pictures are never shown at once.
        sp = fcfg['sit']
        sit = seated(self.src, sp, facing, k1)
        T0 = add(sit)
        sit_pose = P('sit')
        self.poses[sit_pose] = T0
        piv = sit.ay - rise                                    # the butt row stays put when it squashes
        st_c = st.stretched(0.93)                              # crouch, feet fixed
        st_s = st.stretched(1.05)                              # take-off stretch
        C = add(st_c)
        U1 = add(st_s.moved(rise * 0.45, slide * 0.4))
        A = add(st_s.moved(rise + arc, slide * 0.85))          # the top of the hop
        Z1 = add(sit.stretched(1.05, pivot=piv).moved(arc * 0.7))   # cut: the seated picture, still up in the air
        Z2 = add(sit.moved(arc * 0.2))
        Q = add(sit.stretched(0.95, pivot=piv))                # landing squash
        self.clips[P('sit_down')] = dict(frm=stand_pose, to=sit_pose, fps=12, frames=fcfg.get('sit_frames') or [S0, C, U1, A, Z1, Z2, Q, T0], laneSwitchAt=4)
        D1 = add(st_s.moved(rise * 0.5, slide * 0.5))
        D2 = add(st.moved(rise * 0.1, slide * 0.1))
        self.clips[P('stand_up')] = dict(frm=sit_pose, to=stand_pose, fps=12, frames=fcfg.get('stand_frames') or [T0, Q, Z1, A, D1, D2, C, S0], laneSwitchAt=4)

        # ---- sit_idle: breathing (baked vertical stretch about the seat) with blinks
        b1, b2 = sit.stretched(1.006, pivot=piv), sit.stretched(1.012, pivot=piv)
        B1, B2 = add(b1), add(b2)
        self.clips[P('sit_idle')] = dict(frm=sit_pose, to=sit_pose, fps=8, loop=True,
                                         frames=[T0] * 8 + [B1] * 3 + [B2] * 7 + [B1] * 3)

        # ---- activities: hard cuts hidden by a squash (out of the old pose) and a stretch (into the new)
        def hold(i, n, lift=(0, 0, 0, 1, 1, 1, 1, 0)):
            p = self.entry_pic(i)
            return [i if lift[k % len(lift)] == 0 else self.add(p.moved(lift[k % len(lift)])) for k in range(n)]

        def cut(a, b, ia, ib):
            """frames from picture a to picture b: a squashed, b stretched (about the seat), b"""
            return [ia, add(a.stretched(0.96, pivot=piv)), add(b.stretched(1.03, pivot=piv)), ib]

        for kind in ('phone', 'call', 'eat'):
            if kind in fcfg:
                p = seated(self.src, fcfg[kind], facing, k1)
                Pi = add(p)
                self.poses[P(kind)] = Pi
                self.clips[P(kind + '_in')] = dict(frm=sit_pose, to=P(kind), fps=8, frames=cut(sit, p, T0, Pi))
                self.clips[P(kind + '_out')] = dict(frm=P(kind), to=sit_pose, fps=8, frames=cut(p, sit, Pi, T0))
                self.clips[P(kind + '_loop')] = dict(frm=P(kind), to=P(kind), fps=8, loop=True, frames=hold(Pi, 24))
        if fcfg.get('doze'):
            dz = [seated(self.src, d, facing, k1) for d in fcfg['doze']]
            D = [add(p) for p in dz]
            self.poses[P('doze')] = D[0]
            self.clips[P('doze_in')] = dict(frm=sit_pose, to=P('doze'), fps=6, frames=cut(sit, dz[0], T0, D[0]))
            self.clips[P('doze_out')] = dict(frm=P('doze'), to=sit_pose, fps=6, frames=cut(dz[0], sit, D[0], T0))
            loop = hold(D[0], 16)                       # one wrap ~9 s: a leave waits at most that long
            for p, i in zip(dz[1:], D[1:]):            # nod into each other doze pose and back: hard cuts
                loop += [add(p.stretched(0.97, pivot=piv))] + hold(i, 12) + [add(dz[0].stretched(0.97, pivot=piv))] + hold(D[0], 12)
            self.clips[P('doze_loop')] = dict(frm=P('doze'), to=P('doze'), fps=6, loop=True, frames=loop)

    def entry_pic(self, idx):
        for i, pi, dx, dy in self.entries:
            if i == idx:
                p = self.pics[pi]
                return Pic(p.arr, p.ax + dx, p.ay + dy, p.tag, p.faces)
        raise KeyError(idx)

    # ---------------------------------------------------------------- atlas + manifest
    def pack(self, out_dir, dump=None):
        wa = self.walk_atlas
        trims = [trimmed(p, box=True) for p in self.pics]
        # a frame that shows its picture lifted (anchor moved down) needs the rectangle to reach the
        # anchor: pad the picture itself with transparent rows, so the rectangle never takes in the
        # neighbouring picture of the atlas (that once showed a stray head under a hop)
        for pi, (arr, ax, ay, same) in enumerate(trims):
            dys = [dy for _, pj, _, dy in self.entries if pj == pi]
            bottom = int(np.ceil(max(ay + d for d in dys))) + 1 - arr.shape[0]
            top = int(np.ceil(max(0, -min(ay + d for d in dys))))
            if bottom > 0 or top > 0:
                arr2 = np.pad(arr, ((top, max(0, bottom)), (0, 0), (0, 0)))
                trims[pi] = (arr2, ax, ay + top,
                             (lambda f, t=top, b=max(0, bottom): (lambda o: np.pad(f(o), ((t, b), (0, 0), (0, 0)))))(same))
        # shelf packing under the walker's atlas, rows no wider than the atlas (or 2048)
        Wmax = max(wa.width, 2048)
        x = y = row_h = 0
        y0 = wa.height + 2
        places = []
        for arr, ax, ay, _ in trims:
            h, w = arr.shape[:2]
            if x + w > Wmax:
                x, y, row_h = 0, y + row_h + 2, 0
            places.append((x, y0 + y))
            x += w + 2
            row_h = max(row_h, h)
        H = y0 + y + row_h
        atlas = Image.new('RGBA', (Wmax, H), (0, 0, 0, 0))
        atlas.paste(wa, (0, 0))
        for (arr, ax, ay, _), (px, py) in zip(trims, places):
            atlas.paste(to_pil(arr), (px, py))
        for idx, pi, dx, dy in self.entries:
            arr, ax, ay, _ = trims[pi]
            px, py = places[pi]
            self.frames[idx] = {'x': px, 'y': py, 'w': arr.shape[1], 'h': arr.shape[0],
                                'ax': int(round(ax + dx)), 'ay': int(round(ay + dy))}
        for idx, pi, dx, dy in self.entries:
            f = self.frames[idx]
            if not (0 <= f['ay'] <= f['h'] and 0 <= f['ax'] <= f['w']):
                raise ValueError('anchor outside frame %d' % idx)
        H = max(H, max(f['y'] + f['h'] for f in self.frames if f))
        if atlas.height < H:
            big = Image.new('RGBA', (atlas.width, H), (0, 0, 0, 0)); big.paste(atlas, (0, 0)); atlas = big
        # face patches (frame.v): only the pixels that change, once per picture, placed on every frame
        # that shows the picture (each with its own anchor)
        patches = []
        for pi, p in enumerate(self.pics):
            arr, _, _, same = trims[pi]
            idxs = [idx for idx, pj, _, _ in self.entries if pj == pi]
            for name in sorted(p.faces):
                got = face_patch.patch_of(to_pil(arr), to_pil(same(p.faces[name])))
                if got:
                    patches.append((name, got[0], got[1], got[2], idxs))
        atlas = face_patch.attach(atlas, self.frames, patches)
        clips = {}
        wm = self.walk_man
        for cid in ('walk_r', 'walk_l'):
            clips[cid] = wm['clips'][cid]
        for cid, c in self.clips.items():
            d = {'from': c['frm'], 'to': c['to'], 'loop': bool(c.get('loop')), 'fps': c['fps'], 'frames': c['frames']}
            if 'laneSwitchAt' in c:
                d['laneSwitchAt'] = c['laneSwitchAt']
            clips[cid] = d
        man = {'name': self.name, 'walker': True, 'pass': wm.get('pass', 'r'), 'atlas': 'atlas.webp',
               'facings': self.facings, 'scale': self.scale, 'mirrorable': False, 'frames': self.frames, 'poses': self.poses, 'clips': clips}
        out_dir.mkdir(parents=True, exist_ok=True)
        atlas.save(out_dir / 'atlas.webp', lossless=False, quality=90, method=6)
        (out_dir / 'manifest.json').write_text(json.dumps(man, separators=(',', ':')))
        if dump:
            d = Path(dump) / self.name; d.mkdir(parents=True, exist_ok=True)
            atlas.save(d / 'atlas.png')
        return man, atlas


def build(name, cache, src, dump=None):
    cfg = CHARS[name]
    wa, wm = walker_build(cfg, cache)
    b = Builder(name, cfg, wa, wm, src).build()
    man, atlas = b.pack(CHARS_DIR / name, dump)
    size = (CHARS_DIR / name / 'atlas.webp').stat().st_size
    print('%s: %d frames (%d new pictures), atlas %dx%d, %d bytes, %s' % (name, len(man['frames']), len(b.pics), atlas.width, atlas.height, size, b.info))
    return man


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('names', nargs='*')
    ap.add_argument('--walk-cache', help='folder for the walker builds (kept between runs)')
    ap.add_argument('--dump')
    ap.add_argument('--stills', help='only save every finished seated still (source px) here, to measure seat points')
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        src = Sources(tmp)
        if a.stills:
            out = Path(a.stills); out.mkdir(parents=True, exist_ok=True)
            for name in a.names or list(CHARS):
                for facing, fc in CHARS[name]['facings'].items():
                    specs = [('sit', fc['sit'])] + [(k, fc[k]) for k in ('phone', 'call', 'eat') if k in fc] + \
                        [('doze%d' % i, d) for i, d in enumerate(fc.get('doze', []))]
                    for tag, spec in specs:
                        im, _ = seated_still(src, spec)
                        to_pil(im).save(out / ('%s_%s_%s.png' % (name, facing, tag)))
            return
        cache = a.walk_cache or str(Path(tmp) / 'walkers')
        for name in a.names or list(CHARS):
            build(name, cache, src, a.dump)


if __name__ == '__main__':
    main()
