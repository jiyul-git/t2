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
- turns (walk <-> standing at the seat): real in-between angles from the turnaround sheet (cfg 'turn':
  3/4 right, front, 3/4 left), scaled to the walker's height, edge-finished (finish_edges) and anchored
  between the feet; the body keeps its thickness (no squeeze). The renderer slides the foot line from the aisle
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
import head_lead as head_lead_mod   # noqa: E402
import props as props_mod   # noqa: E402
import color_match   # noqa: E402
import sr_upscale   # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
CHARS_DIR = ROOT / 'ui/web/lounge/assets/chars'
ATLAS_K = float(os.environ.get('T2_ATLAS_K', '1.25'))   # atlas resolution multiplier (art/README.md): default 1.25 = 0.775 atlas px per working px; T2_ATLAS_K=1 gives the old 0.62
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
CLIMB2 = S + 'climb_sit_sheet_rabbit_turtle_penguin_gemini.webp'
TURN_RABBIT = S + 'turnaround_rabbit_gemini.webp'
TURN_TIGER = S + 'turnaround_tiger_gemini.webp'
TURN_TURTLE = S + 'turnaround_turtle_gemini.webp'
GROUP_WALK = S + 'chars_walking_group_gemini.webp'
GROUP_ORDER = ['tiger', 'rabbit', 'turtle', 'penguin']
BREATH_S = 4.0                      # one breath, seconds (idle, activities, doze)
BREATH_AMPS = (0, 0.006, 0.012)     # stretch levels of a breath
DOZE_FPS = 6

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
# facing (per still, of the FINISHED picture, i.e. after 'mirror'): what head, torso and legs really face,
# read off the drawing (art/README.md has the table): 'F' front, 'Fl' / 'Fr' front turned slightly (under
# ~25 degrees) to the viewer's left / right, 'L' / 'R' three-quarters (about 45 degrees) to the viewer's left /
# right. A seat facing 'f' takes F / Fl / Fr everywhere, a seat facing 'l' takes L / Fl; the builder refuses
# anything else, so a pose can no longer look the other way from its sofa. eyes: 'open' (blinks, see
# 'blink' in face) or 'closed' (asleep, or drawn as closed smiling eyes).
SEAT_OK = {'f': {'F', 'Fl', 'Fr'}, 'l': {'L', 'Fl'}}
#
# FACINGS (docs/LOUNGE_SCENE_DESIGN.md 7.8): every seat has a facing - 'f' (the left sofa, seen from
# the front) or 'l' (the right sofa, turned three-quarters toward the front-left). A character has one
# set of seated stills per facing it can use, chosen from cells drawn facing that way (or mirrored
# from cells facing the other way); a facing with no convincing art is left out, and the director
# never seats the character there. For 'l' the standing pose is the walker's own walk_l frame (a
# three-quarter view facing left): the character stops, already facing the way the seat faces, and
# hops backwards onto it.
RABBIT_EYE = (72, 28, 25)          # the dark brown of the rabbit's eyes (turnaround sheet)


def EYE_FRONT(x, y, k=1.0, angle=0.0, wx=1.0):
    """A rabbit eye seen from the front (turnaround cell 00: 10 x 13 px with a big highlight top left), scaled by k."""
    return dict(c=(x, y), r=(4.4 * k * wx, 5.6 * k), angle=angle, color=RABBIT_EYE, hl=[(-0.35, -0.4, 1.5 * k, 1.0), (0.3, 0.45, 0.8 * k, 0.55)])


def F(head, torso, legs):
    return dict(head=head, torso=torso, legs=legs)


CHARS = {
    # turn in-betweens (art/README.md "돌아서기"): turnaround cells 3/4 right, front, 3/4 left; 'step': the stepping-turn
    # sheet (2 x 4, walking right -> facing front) that replaces them when it is in art/sources; 'props': the walk_r
    # frame's props (polygon in walk_r frame px, degrees that stand it upright, the hand: 'l'/'r' as seen) and the
    # paw points of each view (px of its trimmed picture, read off 8x grids), see with_props
    'tiger': dict(walker='tiger', turn=dict(sheet=TURN_TIGER, step=S + 'tiger_turn_step_sheet_2x4_gemini.webp', step_mirror='logo', emblem=dict(qr=(140, 138, 170, 156)), props=dict(pieces=dict(case=([(0, 255), (22, 188), (58, 180), (70, 182), (88, 200), (88, 262), (0, 268)], 30, 'l'),
                                                            phone=([(218, 113), (265, 110), (265, 168), (228, 168), (216, 150)], (240, 162), 'r')),
                                               hands=dict(qr=dict(l=(57, 214), r=(185, 210)), front=dict(l=(22, 214), r=(183, 211), paws=dict(l=(17, 192), r=(167, 192))), ql=dict(l=(8, 214), r=(148, 220)))), qr=dict(cell='32'), front=dict(cell='00'), ql=dict(cell='10')), facings={
        'f': dict(
            # standing at the seat: the turnaround front view carrying the walk frame's suitcase and phone (the stand
            # sheet's f_02 held the phone in the other paw and had no suitcase)
            stand='turn',
            # sitting, legs forward, soles to the viewer; head turned a little to the viewer's left; blink: the
            # closed eyes of the climb sheet's cheek-on-hand cell, one on each pupil
            sit=dict(src=(CLIMB_A, '23'), f=0.542, seat=(175, 330), facing=F('Fl', 'F', 'F'), face=dict(sheet=CLIMB_A, variants={'blink': dict(
                cell='32', scale=0.85, erase=[dict(e=(91.7, 106.7, 7, 10), skin=(80, 108)), dict(e=(153.3, 106, 7, 10), skin=(165, 110))],
                feats=[dict(box=(40, 100, 76, 122), at=(91.7, 110)), dict(box=(112, 100, 154, 126), at=(153.3, 110))])})),
            # the most frontal cells of the tiger doze sheet (tail on the right, soles to the viewer)
            doze=[dict(src=(TIGER_DOZE, '21'), f=1.139, seat=(85, 160), facing=F('Fl', 'F', 'F')),
                  dict(src=(TIGER_DOZE, '11'), f=1.139, seat=(85, 160), facing=F('F', 'F', 'F')),
                  dict(src=(TIGER_DOZE, '13'), f=1.139, seat=(85, 160), facing=F('F', 'F', 'F'))],
        ),
        'l': dict(
            stand='walk',
            # the climb sheet's "sitting on the edge" cell: body and the outstretched leg turn three-quarters to the
            # viewer's left, the head faces front, a little to the left (nose left of centre, pupils looking left)
            sit=dict(src=(CLIMB_A, '22'), f=0.542, seat=(240, 320), facing=F('Fl', 'L', 'L'), face=dict(sheet=CLIMB_A, variants={'blink': dict(
                erase=[dict(e=(129, 103, 6, 11), skin=(122, 96)), dict(e=(183, 107, 7, 12), skin=(200, 112))],
                lids=[dict(c=(129, 105), w=19, sag=4.0, t=3.6, angle=-4), dict(c=(183, 109), w=27, sag=5.0, t=4.2, angle=-4)])})),
            # the group picture's tiger looks down at his phone toward the viewer's right (tail on the left):
            # mirrored so he faces the sofa's way; the T2 on the sleeve is turned back (mirror_logo.py). Cut by
            # hand: the automatic split cut off the right paw where it overlaps the rabbit's suitcase.
            phone=dict(src=(GROUP_SIT, 'region', [(0, 250), (340, 250), (340, 575), (347, 580), (347, 621), (360, 628),
                                                   (371, 642), (375, 665), (370, 690), (330, 712), (0, 712)]), f=0.523, mirror='logo',
                       seat=(150, 343), seat_pre=True, facing=F('Fl', 'L', 'L'),
                       face=dict(sheet=GROUP_SIT, variants={'blink': dict(      # coordinates before the flip
                           erase=[(168, 121, 8, 11.5), (224, 132, 6.5, 9.8)],
                           lids=[dict(c=(168, 123), w=19, sag=4.2, t=3.8, angle=8), dict(c=(224, 134), w=15, sag=3.6, t=3.4, angle=8)])}),
                       cut=[[(321, 356), (340, 356), (340, 392), (321, 392)]]),
            doze=[dict(src=(TIGER_DOZE, '10'), f=1.139, seat=(85, 160), facing=F('L', 'L', 'L')),
                  dict(src=(TIGER_DOZE, '30'), f=1.139, seat=(85, 160), facing=F('L', 'L', 'L')),
                  dict(src=(TIGER_DOZE, '00'), f=1.139, seat=(85, 160), facing=F('L', 'L', 'L'))],
        ),
    }),
    # the only 3/4 cell with both arms down faces right (f_33); mirrored for the left, like walk_l is the mirrored walk_r
    'rabbit': dict(walker='rabbit', turn=dict(sheet=TURN_RABBIT, step=S + 'rabbit_turn_step_sheet_2x4_gemini.webp', props=dict(pieces=dict(case=([(0, 265), (25, 222), (55, 215), (68, 200), (85, 205), (85, 230), (80, 302), (0, 302)], 30, 'l'),
                                                             phone=([(222, 138), (256, 138), (256, 190), (222, 190)], (237, 184), 'r')),
                                                hands=dict(qr=dict(l=(10, 226), r=(162, 224)), front=dict(l=(15, 215), r=(66, 210), clasped=(69, 194)), ql=dict(l=(12, 222), r=(165, 226)))), qr=dict(cell='33'), front=dict(cell='00'), ql=dict(cell='33', mirror=True)), facings={
        'f': dict(
            # standing at the seat: the turnaround front view carrying the walk frame's suitcase and phone (the pose
            # sheet's coffee-cup cell f_31 changed the prop in the middle of the turn)
            stand='turn',
            # hands on the cheeks, facing the viewer. The drawing has happy closed eyes: they are opened
            # with a pair of drawn round eyes (same size, same highlights, like the front view of the
            # turnaround sheet) and the drawn closed eyes are the blink
            sit=dict(src=(ALL_DOZE, '12'), f=1.167, seat=(75, 160), facing=F('Fr', 'F', 'F'), face=dict(sheet=TURN_RABBIT, fix=dict(
                erase=[(70, 86, 10.5, 5, -10), (106, 76.5, 8.5, 5, -20)], eyes=[EYE_FRONT(70, 87.5, 1.1, -12), EYE_FRONT(106, 78, 1.1, -12)]),
                variants={'blink': 'orig'})),
            # the sitting cell with its own closed eyes, and the frontal sleeper (head nodding forward, hands in her lap)
            doze=[dict(src=(ALL_DOZE, '12'), f=1.167, seat=(75, 160), facing=F('Fr', 'F', 'F')),
                  dict(src=(ALL_DOZE, '10'), f=1.167, seat=(68, 160), facing=F('Fl', 'F', 'F'))],
        ),
        'l': dict(
            stand='walk',
            # sitting three-quarters left (head, body and boots), drawn with closed eyes: opened with a pair of drawn
            # round eyes foreshortened for the view (the far, left eye 0.85 as wide as the near one; both as tall as
            # the front view's, measured on the turnaround sheet's 3/4 faces), the drawn closed eyes are the blink
            sit=dict(src=(CLIMB2, '03'), keep='largest', f=1.215, seat=(82, 166), facing=F('L', 'L', 'L'), face=dict(sheet=TURN_RABBIT, fix=dict(
                erase=[(34.5, 87.2, 8.8, 3.0, 20), (67, 90.2, 10.5, 3.4, 8)],
                eyes=[EYE_FRONT(35.5, 88.5, 1.08, 4, wx=0.84), EYE_FRONT(68, 90, 1.08, 4)]), variants={'blink': 'orig'})),
            # the group picture's call faces right: mirrored. The suitcase and the bag beside her are cut
            # away; the sleeve they covered is repainted
            call=dict(src=(GROUP_SIT, 'rabbit'), f=0.55, mirror=True, seat=(185, 335), facing=F('L', 'L', 'L'),
                      # laughing on the phone with happy closed eyes: opened with the same drawn eyes (3/4 right before the flip: the far,
                      # right eye is narrower), the drawn happy eyes are the blink
                      face=dict(sheet=TURN_RABBIT, fix=dict(erase=[(139.5, 159.5, 21.5, 5, -6), (203, 155.5, 14.5, 4.8, -8)],
                                                            eyes=[EYE_FRONT(138, 157, 1.85, -8), EYE_FRONT(203.5, 153.5, 1.85, -8, wx=0.84)]), variants={'blink': 'orig'}),
                      cut=[[(0, 178), (60, 178), (80, 200), (84, 217), (84, 235), (88, 255), (92, 290), (96, 326), (104, 344), (118, 351),
                            (134, 352), (134, 407), (0, 407)]],
                      # the cut leaves the jacket's side missing: rebuilt by paint_sleeve (art/README.md): the jacket's colour carried
                      # over from the cut edge, a sleeve with its lit stripe, fold lines and a ribbed knit cuff with the paw
                      sleeve=dict(zone=[(84, 217), (134, 217), (134, 352), (118, 351), (104, 344), (96, 326), (92, 290), (88, 255), (84, 235)],
                                  zone_x0=84, edge_x=135, left_shade=0.9,
                                  lit_bands=[([(96, 228), (97, 255), (100, 285)], 9, (240, 150, 140), 0.55)],
                                  lines=[[(106, 224), (112, 238), (113, 258)], [(98, 262), (104, 276), (110, 282)], [(112, 300), (118, 312), (120, 326)]],
                                  sil=[[(84, 232), (88, 255), (92, 290), (96, 326), (104, 344), (118, 351), (136, 352)]],
                                  cuff=dict(quad=[(90, 292), (122, 296), (124, 307), (93, 304)], ribs=8)),
                      ),
            # f_13 faces right: mirrored, its 'zz' dropped (mirrored letters)
            doze=[dict(src=(CLIMB2, '03'), keep='largest', f=1.215, seat=(82, 166), facing=F('L', 'L', 'L')),
                  dict(src=(ALL_DOZE, '11'), f=1.167, seat=(100, 150), facing=F('L', 'L', 'L')),
                  dict(src=(ALL_DOZE, '13'), f=1.167, mirror=True, keep='largest', seat=(80, 150), facing=F('L', 'L', 'L'))],
        ),
    }),
    # no frontal seated turtle exists (every cell is three-quarters): it only takes the right sofa
    'turtle': dict(walker='turtle', turn=dict(sheet=TURN_TURTLE, step=S + 'turtle_turn_step_sheet_2x4_gemini.webp', props=dict(pieces=dict(ticket=([(186, 120), (225, 120), (225, 182), (186, 182)], (205, 178), 'r')),
                                                hands=dict(qr=dict(l=(32, 210), r=(160, 198)), front=dict(l=(10, 205), r=(158, 213), paws=dict(l=(13, 206), r=(148, 206))), ql=dict(l=(8, 210), r=(130, 212)))), qr=dict(cell='32'), front=dict(cell='00'), ql=dict(cell='02')), facings={
        'l': dict(
            stand='walk',
            # the waking-up cell (faces right, mirrored): its surprised "o" mouth becomes the sleeping
            # cell's small smile; blink from the same sleeping cell (same sheet, same size)
            sit=dict(src=(ALL_DOZE, '22'), f=1.3, mirror=True, seat=(75, 150), facing=F('L', 'L', 'L'), face=dict(sheet=ALL_DOZE, fix=dict(
                cell='20', scale=1.0, erase=[(95, 68, 9, 6.5)], feats=[dict(box=(96, 73, 120, 86), at=(95, 67))]),
                variants={'blink': dict(cell='20', scale=1.0, erase=[(75, 51, 11, 11), (108, 49, 8, 10)],
                                        feats=[dict(box=(80, 55, 104, 70), at=(75, 53)), dict(box=(116, 66, 131, 77), at=(108, 51))])})),
            # the group picture's turtle already faces left (ticket = 'phone'); not mirrored (T2 on the ticket)
            phone=dict(src=(GROUP_SIT, 'turtle'), f=0.6, seat=(180, 300), facing=F('L', 'L', 'L'), face=dict(sheet=GROUP_SIT, variants={'blink': dict(
                erase=[(78, 102, 14.5, 23), (159, 116, 25, 27)],
                lids=[dict(c=(78, 108), w=22, sag=5.5, t=4.0, angle=-3), dict(c=(158, 120), w=42, sag=8.0, t=5.5, angle=-3)])})),
            doze=[dict(src=(ALL_DOZE, '20'), f=1.3, mirror=True, seat=(80, 150), facing=F('L', 'L', 'L')),
                  dict(src=(ALL_DOZE, '21'), f=1.3, mirror=True, seat=(80, 150), facing=F('L', 'L', 'L')),
                  dict(src=(ALL_DOZE, '23'), f=1.3, mirror=True, keep='largest', seat=(80, 150), facing=F('L', 'L', 'L'))],
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
def _aa_mask(shape, draw, k, ss=3):
    big = np.zeros((shape[0] * ss, shape[1] * ss), np.uint8)
    draw(big, k * ss)
    return cv2.resize(big, (shape[1], shape[0]), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.


def paint_sleeve(a, c, k):
    """Rebuild what a prop (a suitcase) hid: the jacket's side and an arm with a knit cuff, drawn with the colours
    and line weight of the same drawing (art/README.md, rabbit call pose). All c coordinates are source px.
    1. body: the jacket's own colour at the cut edge is carried leftwards row by row (so its shading and
       folds continue) and darkens towards the silhouette like the rest of the jacket;
    2. arm: a sleeve outline (ink), a lit stripe along it, two fold lines, a seam;
    3. cuff: a ribbed knit cuff (rib lines, like the other sleeve's cuff) and the paw below it.
    c = dict(zone=poly, edge_x=x of the cut edge, left_shade=0.85, arm=poly of the sleeve, cuff=(cx, cy, w, h, angle), ...)"""
    H, W = a.shape[:2]
    INK = np.float32([58, 24, 26])
    zone = _aa_mask(a.shape[:2], lambda m, s: cv2.fillPoly(m, [np.int32(np.array(c['zone']) * s)], 255), k)
    ex = int(c['edge_x'] * k)
    out = a.copy()
    # 1. the body: per row the mean colour of a few columns right of the cut edge, darkened towards the left
    ys = np.arange(H)
    win = a[:, ex:ex + 8 * k, :3]
    lum = win @ np.float32([0.3, 0.59, 0.11])
    good = (lum > 105) & (a[:, ex:ex + 8 * k, 3] > 250)               # not the ink lines
    cnt = good.sum(1)
    ref = np.where(cnt[:, None] > 0, (win * good[..., None]).sum(1) / np.maximum(cnt, 1)[:, None], np.nan)
    rows = np.arange(H)
    for ch in range(3):                                               # fill the rows without cloth, then smooth along y
        v = ref[:, ch]; ok_ = ~np.isnan(v)
        v = np.interp(rows, rows[ok_], v[ok_])
        v = np.convolve(np.pad(v, 7 * k, mode='edge'), np.ones(14 * k + 1) / (14 * k + 1), 'valid')
        ref[:, ch] = v
    x = np.arange(W)[None, :]
    x0 = c['zone_x0'] * k
    t = np.clip((ex - x) / max(ex - x0, 1), 0, 1)             # 0 at the cut edge, 1 at the silhouette
    shade = 1 - (1 - c.get('left_shade', 0.86)) * t ** 1.3
    body = ref[:, None, :] * shade[..., None]
    fe = np.clip((ex + 4 * k - x) / (8.0 * k), 0, 1)            # feather into the real picture over 8 px at the cut edge
    z = (zone * fe)[..., None]
    out[..., :3] = out[..., :3] * (1 - z) + body * z
    out[..., 3] = np.where(zone > 0.02, 255, out[..., 3])
    # 2. the sleeve's modelling: a soft lit band along its outer side, fold lines and the silhouette's ink line
    def stroke(pts, w, closed=False):
        def d(m, s): cv2.polylines(m, [np.int32(np.round(np.array(pts) * s))], closed, 255, max(1, int(round(w * s))), cv2.LINE_AA)
        return _aa_mask(a.shape[:2], d, k)
    for band in c.get('lit_bands', []):          # (polyline, width, colour, strength): a lit stripe like the other sleeve's
        m = cv2.GaussianBlur(stroke(band[0], band[1]), (0, 0), 1.6 * k)
        out[..., :3] = out[..., :3] * (1 - band[3] * m[..., None] * (zone > 0.5)[..., None]) + np.float32(band[2]) * (band[3] * m[..., None] * (zone > 0.5)[..., None])
    extra = []
    if c.get('cuff'):                             # a ribbed knit cuff: quad (top-left, top-right, bottom-right, bottom-left), n ribs
        q = np.array(c['cuff']['quad'], np.float32)
        cm = _aa_mask(a.shape[:2], lambda m, s: cv2.fillPoly(m, [np.int32(np.round(q * s))], 255), k)
        col = np.float32(c['cuff'].get('col', (226, 132, 124)))
        out[..., :3] = out[..., :3] * (1 - cm[..., None]) + col * cm[..., None]
        out[..., 3] = np.maximum(out[..., 3], 255 * cm)
        n = c['cuff'].get('ribs', 7)
        for i in range(1, n):
            f = i / n
            top = q[0] * (1 - f) + q[1] * f; bot = q[3] * (1 - f) + q[2] * f
            extra.append(stroke([tuple(top), tuple(bot)], 0.8) * 0.7)
        extra.append(stroke([tuple(v) for v in q], 1.3, True))
    sil = [stroke(l, c.get('line', 1.8)) for l in c.get('sil', [])] + extra
    inner = [stroke(l, c.get('inner', 1.1)) for l in c.get('lines', [])]
    ink = np.maximum.reduce(sil + inner)
    out[..., :3] = out[..., :3] * (1 - ink[..., None]) + INK * ink[..., None]
    out[..., 3] = np.maximum(out[..., 3], 255 * np.maximum(ink, 0))
    return out


class Sources:
    """Cut cells out of the sheets. A low-resolution sheet (under 1500 px wide: about 170 px per cell) is
    first super-resolved 4x (sr_upscale.py) and its cells are cut 4x ('up' = 4); a 2400 px sheet is used as is
    ('up' = 1). All coordinates in the specs are px of the ORIGINAL sheet; they are multiplied by up(sheet)
    where a picture is touched. SR can be switched off (--no-sr, or no weights): everything is 1x then."""
    def __init__(self, tmp, sr=True):
        self.tmp, self.cache, self.sr, self.srs = Path(tmp), {}, sr, {}

    def sr_png(self, sheet):
        """Path of the 4x sheet (PNG in the temp folder), or None when it is not needed / not available."""
        if sheet not in self.srs:
            self.srs[sheet] = None
            if self.sr and Image.open(ROOT / sheet).width < 1500:
                im = sr_upscale.upscale(ROOT / sheet)
                if im is not None:
                    p = self.tmp / ('sr_%d.png' % len(self.srs))
                    im.save(p, compress_level=1)
                    self.srs[sheet] = p
        return self.srs[sheet]

    def up(self, sheet):
        return 4 if self.sr_png(sheet) else 1

    def cells(self, sheet, grid=(4, 4)):
        if sheet not in self.cache:
            out = self.tmp / ('cells_%d' % len(self.cache))
            sr = self.sr_png(sheet)
            subprocess.run([sys.executable, '-I', str(TOOLS / 'cut_sheet.py'), str(ROOT / sheet), str(out), str(grid[0]), str(grid[1])] + ([str(sr)] if sr else []),
                           check=True, stdout=subprocess.DEVNULL)
            self.cache[sheet] = out
        return self.cache[sheet]

    def group(self, sheet):
        if sheet not in self.cache:
            out = self.tmp / ('group_%d' % len(self.cache))
            out.mkdir()
            sr = self.sr_png(sheet)
            subprocess.run([sys.executable, '-I', str(TOOLS / 'cutout_white.py'), str(ROOT / sheet), str(out / 'g'),
                            '--split', '4', '--names', ','.join(GROUP_ORDER)] + (['--sr', str(sr)] if sr else []),
                           check=True, stdout=subprocess.DEVNULL)
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
        sr = self.sr_png(sheet)
        if sr:
            up = 4
            a4 = cv2.resize(alpha[y0:y1, x0:x1] / 255, ((x1 - x0) * up, (y1 - y0) * up), interpolation=cv2.INTER_CUBIC)
            a4 = np.clip((a4 - 0.5) * 2.5 + 0.5, 0, 1) * 255
            col = np.asarray(Image.open(sr).convert('RGB'))[y0 * up:y1 * up, x0 * up:x1 * up]
            return np.dstack([col, a4]).astype(np.float32)
        return np.dstack([rgb, alpha]).astype(np.float32)[y0:y1, x0:x1].copy()

    def still(self, spec):
        """The source cell (straight RGBA float, working px = up x source px), cleaned as the spec says."""
        sheet, cell = spec['src'][:2]
        k = self.up(sheet)
        if cell == 'region':
            a = self.region(sheet, spec['src'][2])
        elif cell in GROUP_ORDER:
            a = from_pil(Image.open(self.group(sheet) / ('g_%s.png' % cell)))
        else:
            a = from_pil(Image.open(self.cells(sheet, spec.get('grid', (4, 4))) / ('f_%s.png' % cell)))
        if spec.get('keep') == 'largest':
            m = (a[..., 3] > 40).astype(np.uint8)
            n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
            big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
            a[~cv2.dilate((lab == big).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)] = 0
        for poly in spec.get('cut', []):
            m = np.zeros(a.shape[:2], np.uint8)
            cv2.fillPoly(m, [np.int32(np.array(poly) * k)], 1)
            a[m > 0] = 0
        for poly, box in spec.get('fill', []):   # repaint what a prop covered with the cloth colour beside it
            m = np.zeros(a.shape[:2], np.uint8)
            cv2.fillPoly(m, [np.int32(np.array(poly) * k)], 1)
            x0, y0, x1, y1 = [int(v * k) for v in box]
            sample = a[y0:y1, x0:x1].reshape(-1, 4)
            col = np.median(sample[sample[:, 3] > 250, :3], 0)
            kf = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.2 * k)[..., None]
            a[..., :3] = a[..., :3] * (1 - kf) + col * kf
            a[..., 3] = np.where(m > 0, 255, a[..., 3])
        for line in spec.get('ink', []):         # an outline where a cut edge runs (polyline, source px)
            m = np.zeros(a.shape[:2], np.uint8)
            cv2.polylines(m, [np.int32(np.array(line) * 4 * k)], False, 255, 10 * k, cv2.LINE_AA, 2)
            kf = (m.astype(np.float32) / 255)[..., None] * (a[..., 3:] > 0)
            a[..., :3] = a[..., :3] * (1 - kf) + face_patch.LINE * kf
        if spec.get('sleeve'):
            a = paint_sleeve(a, spec['sleeve'], k)
        # empty rows and columns left at the bottom / right by the cleaning go (top-left stays, so the
        # source coordinates in CHARS stay valid)
        ys, xs = np.nonzero(a[..., 3] > 0)
        return a[:ys.max() + 1, :xs.max() + 1]


def feet_x(a, band=0.06):
    H = a.shape[0]
    ys, xs = np.nonzero(a[int(H * (1 - band)):, :, 3] > 128)
    return float((xs.min() + xs.max()) / 2)


def with_faces(src, a, spec):
    """(the still with its face fixed, {face name: the still with that face}) from spec['face']
    (face_patch.py; coordinates in source px of the still's sheet, converted here): 'fix' changes the
    still itself (e.g. a surprised mouth made a small smile, eyes opened from another drawing of the same
    animal), each variant is a face_patch spec or 'orig' (the still as drawn, before the fix). Donor
    cells come from Sources (super-resolved when their sheet is small)."""
    fc = spec.get('face')
    if not fc:
        return a, {}
    ku = src.up(spec['src'][0])

    def apply(base, v):
        sheet = v.get('sheet') or fc['sheet']             # the donor sheet of this variant
        d = {}
        for feat in v.get('feats', []):
            cell = feat.get('cell', v.get('cell'))
            if (v.get('sheet'), cell) not in d:
                im = Image.open(src.cells(sheet) / ('f_%s.png' % cell)).convert('RGBA')
                if v.get('flip'):
                    im = im.transpose(Image.FLIP_LEFT_RIGHT)
                d[(v.get('sheet'), cell)] = np.asarray(im).astype(np.float32)
        return face_patch.apply(base, v, d, src.up(sheet), ku)
    base = apply(a, fc['fix']) if fc.get('fix') else a
    out = {}
    for name, v in fc.get('variants', {}).items():
        out[name] = a if v == 'orig' else apply(base, v)
    return base, out


def scaled(a, faces, f, ku=1):
    """Resize to the atlas: f atlas px per source px, the picture is ku x the source."""
    k = f / ku
    r = resize(a, a.shape[1] * k, a.shape[0] * k)
    return r, {n: resize(v, a.shape[1] * k, a.shape[0] * k) for n, v in faces.items()}


def standing(src, spec):
    """stand_front: anchored on the floor between the feet. Separate scraps (a pale floor shadow
    left by the cut-out) are dropped unless the spec says otherwise."""
    spec = dict(spec, keep=spec.get('keep', 'largest'))
    ku = src.up(spec['src'][0])
    a = src.still(spec)
    x = spec['x'] * ku if 'x' in spec else feet_x(a)
    a, faces = with_faces(src, a, spec)
    r, faces = scaled(a, faces, spec['f'] * ATLAS_K, ku)
    # the turns land on this picture: the same edge finishing as their in-betweens (no white fringe next to them)
    r, faces = finish_edges(r)[0], {n: finish_edges(v)[0] for n, v in faces.items()}
    return Pic(r, x * r.shape[1] / a.shape[1], r.shape[0] - 1, 'stand', faces)


def finish_edges(a, min_piece=30):
    """Pixel finishing of a turn in-between at atlas size (straight RGBA float in and out), the same on every
    frame so the line weight stays even:
    1. faint alpha (< 20) goes, and separate scraps under min_piece px (stray pixels) are deleted;
    2. pinholes in the silhouette (a transparent px with 3+ solid 4-neighbours) are closed with line colour;
    3. every edge px (semi-transparent, or solid with a transparent 4-neighbour) is re-inked in the drawing's
       own line colour (the median of the darkest 40 % of the outline just inside the edge): no white or
       grey fringe, no halo, no soft outline;
    4. light, colourless px within 2 px of the edge (sheet white left by the cut) become line colour too."""
    a = a.copy()
    al = a[..., 3]
    al[al < 20] = 0
    solid = al > 0
    n, lab, st, _ = cv2.connectedComponentsWithStats(solid.astype(np.uint8), connectivity=8)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] < min_piece:
            a[lab == i] = 0
    inner = cv2.erode((al > 250).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    band = inner & ~cv2.erode(inner.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    px = a[band][:, :3]
    lum = px.mean(1)
    line = np.median(px[lum <= np.percentile(lum, 40)], 0)
    for _ in range(3):
        op = np.pad((al > 128).astype(np.uint8), 1)
        nb = op[:-2, 1:-1] + op[2:, 1:-1] + op[1:-1, :-2] + op[1:-1, 2:]
        hole = (al < 128) & (nb >= 3)
        a[hole, :3] = line
        al[hole] = 255
    clear = np.pad(al == 0, 1, constant_values=True)
    edge_nb = clear[:-2, 1:-1] | clear[2:, 1:-1] | clear[1:-1, :-2] | clear[1:-1, 2:]
    edge = (al > 0) & ((al < 255) | edge_nb)
    a[edge, :3] = line
    near = (al > 0) & ~cv2.erode((al > 0).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    mn, mx = a[..., :3].min(-1), a[..., :3].max(-1)
    a[near & (mn > 150) & (mx - mn < 40), :3] = line
    return a, line


def outline(a):
    """(mean width in px, colour) of the outer outline of a picture: the dark run (lum < 75) that touches
    the silhouette's edge, within 6 px of it; its area over the edge length is the width, its middle the colour."""
    m = (a[..., 3] > 128).astype(np.uint8)
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    dark = (a[..., :3].mean(-1) < 75) & (m > 0)
    n, lab = cv2.connectedComponents(dark.astype(np.uint8), connectivity=8)
    edge = list(set(np.unique(lab[(dist <= 1.5) & dark])) - {0})
    band = np.isin(lab, edge) & (dist <= 6)
    width = band.sum() / max(1, ((dist > 0) & (dist <= 1.5)).sum())
    return width, np.median(a[band & (dist >= 1) & (dist <= 2.5)][:, :3], 0)


def turn_cell(src, spec):
    """a turn cell (spec: sheet, cell, grid, mirror) in working px, cropped to the figure"""
    a = src.still(dict(src=(spec['sheet'], spec['cell']), grid=spec.get('grid', (4, 4)), keep='largest'))
    ku = src.up(spec['sheet'])
    if spec.get('mirror'):
        a = mirrored(a, spec['mirror'] == 'logo', ku)
    ys, xs = np.nonzero(a[..., 3] > 128)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def turn_view(src, spec, h, like, ref_h=None):
    """A turnaround cell for a turn in-between (spec: cell, mirror), scaled to h atlas px from the crown to
    the soles (the turnaround rows are drawn at different sizes, so each cell is scaled to its own height;
    ref_h: scale so that a figure ref_h working px tall is h instead - one factor for a whole step sheet),
    finished (finish_edges) and anchored on the floor between the feet like the walk and stand frames.
    The turnaround sheet is inked heavier and nearly black: the outer outline is thinned to the width of
    `like` (the walk frame beside it; eroded at the 4x size, before shrinking) and every ink px takes its
    line colour, so the line weight and colour do not change from frame to frame."""
    a = turn_cell(src, spec)
    k = h / (ref_h or a.shape[0])
    w_like, c_like = outline(like.arr)

    def make(e):
        """e: atlas px to take off the outside of the outline"""
        b = a
        if e > 0:
            d = cv2.distanceTransform((a[..., 3] > 128).astype(np.uint8), cv2.DIST_L2, 5)
            b = a.copy()
            b[..., 3] = np.minimum(b[..., 3], np.clip(d - e / k + 0.5, 0, 1) * 255)
        r = resize(b, b.shape[1] * k, b.shape[0] * k)
        return finish_edges(r)
    r, line = make(0)
    e = 0.0
    for _ in range(4):                     # the edge re-ink adds back a little: measure again and take more
        d = outline(r)[0] - w_like
        if d <= 0.08:
            break
        e += d
        r, line = make(e)
    # ink to the walk frame's line colour: a px as dark as the line moves all the way, lighter ones less
    lum, l0 = r[..., :3].mean(-1), float(line.mean())
    t = np.clip((90 - lum) / max(1.0, 90 - l0), 0, 1)[..., None]
    r[..., :3] = np.clip(r[..., :3] + (c_like - line) * t, 0, 255)
    r = np.pad(r, ((1, 1), (1, 1), (0, 0)))
    ys, xs = np.nonzero(r[..., 3] > 128)
    return Pic(r, feet_x(r) + spec.get('dx', 0), ys.max(), 'turn' + spec['cell'])


def head_lead(body, head_from, kind, cuts=None):
    """the next view's head on this view's body (head_lead.py), edge-finished around the neck and head only
    (the rest of the body stays exactly as it was); anchored like the body. cuts: (body, head) head_mask limits"""
    a, dx, dy, zone = head_lead_mod.transplant(body.arr, head_from.arr, kind, *(cuts or (None, None)))
    f, _ = finish_edges(a)
    a = np.where(zone[..., None], f, a)
    if kind == 'tiger':          # the body's gold T2 marks come back over the new collar (it must not swallow them)
        m = cv2.dilate(props_mod.logo_mask(body.arr, head_lead_mod.cloth).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        ys, xs = np.nonzero(m)
        a[ys + int(dy), xs + int(dx)] = body.arr[ys, xs]
    return Pic(a, body.ax + dx, body.ay + dy, 'head')


def with_props(view, pieces, assign, hp, kind, f=1.0, bare=None):
    """the view with the walk frame's props (props.py). assign 'R': as in walk_r (pieces as cut), 'L': as in walk_l
    (walk_l is walk_r mirrored: pieces mirrored, hands swapped), 'C1' / 'C2' / 'C3': the hand-over at the front, from
    the walk_r hands to the walk_l hands - C1 the hand-held prop raised to the middle in its paw, C2 both paws meet
    with it between them (the suitcase stands on the floor), C3 it is in the other paw. The figure's own paw that is
    in the middle is taken off its side (props.erase_paw). hp: paw points (bottom of the paw) in px of the view's
    trimmed picture before its head scaling f. Returns (Pic, metrics)."""
    ys, xs = np.nonzero(view.arr[..., 3] > 0)
    paws = hp.get('paws', {})                       # the view's own paw centres, in px of the (scaled) view itself
    hp = {k: (x * f + xs.min(), y * f + ys.min()) for k, (x, y) in hp.items() if k != 'paws'}
    arr = view.arr
    lst = []
    mirror = lambda p: p[:, ::-1].copy()
    if 'clasped' in hp and assign != 'L':
        # a front view drawn with both paws clasped in the middle (the rabbit): the hand-held prop alone (bare, without
        # the walk frame's paw) sits in the clasped paws; the hand-over slides it from one side of them to the other
        dx = {'R': 0, 'C1': 4, 'C2': 0, 'C3': -4}[assign]
        cx, cy = hp['clasped']
        for name, (p, info, side) in pieces.items():
            if name == 'case':
                if assign in ('R', 'C1'):
                    lst.append((name, side, p, info))
                elif assign == 'C2':
                    hp['floor'] = (cx, cy)
                    lst.append((name, 'floor', p, info))
                else:
                    lst.append((name, {'l': 'r', 'r': 'l'}[side], mirror(p), -info))
                continue
            q = bare[name] if assign in ('R', 'C1') else mirror(bare[name])
            hp['cl'] = (cx + dx, cy)
            lst.append((name, 'cl', q, (q.shape[1] / 2, q.shape[0] * 0.6)))
    elif assign in ('R', 'L'):
        for name, (p, info, side) in pieces.items():
            if assign == 'L':
                p = mirror(p)
                info = -info if name == 'case' else (p.shape[1] - 1 - info[0], info[1])
                side = {'l': 'r', 'r': 'l'}[side]
            lst.append((name, side, p, info))
    else:
        (lx, ly), (rx, ry) = hp['l'], hp['r']   # noqa: E501 - the paws at the sides: they come to the middle
        cx, cy = (lx + rx) / 2, (ly + ry) / 2 + 0.03 * figure_h(view)   # at the belly: under the chest mark
        off = 0.14 * abs(rx - lx)
        stage = int(assign[1])
        for name, (p, info, side) in pieces.items():
            other = {'l': 'r', 'r': 'l'}[side]
            if name == 'case':
                if stage == 1:
                    lst.append((name, side, p, info))
                elif stage == 2:
                    hp['floor'] = (cx, cy)
                    lst.append((name, 'floor', p, info))
                else:
                    lst.append((name, other, mirror(p), -info))
                continue
            mp, mg = mirror(p), (p.shape[1] - 1 - info[0], info[1])
            sgn = 1 if side == 'r' else -1                  # the walk_r hand's side of the middle
            if stage in (1, 2):
                hp[name + '1'] = (cx + sgn * off * (1 if stage == 1 else 0.5), cy)
                lst.append((name, name + '1', p, info))
                arr = props_mod.erase_paw(arr, paws[side], kind)
            if stage == 2:
                hp[name + '2'] = (cx - sgn * off * 0.5, cy + 2)
                lst.append((name + '_paw', name + '2', props_mod.paw_only(mp, kind), mg))
            if stage in (2, 3):
                arr = props_mod.erase_paw(arr, paws[other], kind)
            if stage == 3:
                hp[name + '3'] = (cx - sgn * off, cy)
                lst.append((name, name + '3', mp, mg))
    a, ax, ay, zone, metrics = props_mod.carry(arr, view.ax, view.ay, hp, lst, kind)
    metrics.pop('phone_paw', None); metrics.pop('ticket_paw', None)
    if 'clasped' in hp and assign != 'L':
        # the clasped paws drawn again over the prop: it is held between them
        sk = props_mod.skin(arr[..., :3], kind) & (arr[..., 3] > 128)
        n, lab = cv2.connectedComponents(sk.astype(np.uint8), connectivity=8)
        yy, xx = np.mgrid[:arr.shape[0], :arr.shape[1]]
        cx, cy = hp['clasped']
        hit = set(np.unique(lab[sk & ((xx - cx) ** 2 + (yy - cy) ** 2 < 24 ** 2)])) - {0}
        m = np.isin(lab, list(hit))
        m |= cv2.dilate(m.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & (arr[..., :3].mean(-1) < 90)
        X0, Y0 = int(round(view.ax - ax)), int(round(view.ay - ay))
        ys_, xs_ = np.nonzero(m)
        a[ys_ - Y0, xs_ - X0] = arr[ys_, xs_]
        metrics = {k: (0.0, v[1]) for k, v in metrics.items()}   # held between the paws
    f_, _ = finish_edges(a)
    return Pic(f_, ax, ay, view.tag + '+props'), metrics


def head_scaled(v, like, kind):
    """v scaled so its face (head_lead.face_size: sqrt of the area) is as big as the walk frame's beside it; feet stay on the floor"""
    f = head_lead_mod.face_size(like.arr, kind)[0] / head_lead_mod.face_size(v.arr, kind)[0]
    a = resize(v.arr, v.w * f, v.h * f)
    ys = np.nonzero((a[..., 3] > 128).any(1))[0]
    return Pic(a, v.ax * a.shape[1] / v.w, ys.max(), v.tag), f


def figure_h(p):
    """crown-to-sole height of a picture (opaque rows)"""
    ys = np.nonzero((p.arr[..., 3] > 128).any(1))[0]
    return ys.max() - ys.min()


def mirrored(a, logo=False, k=1):
    """Left-right flip; logo=True turns the gold T2 letters back so they read (mirror_logo.py)."""
    if not logo:
        return a[:, ::-1].copy()
    with tempfile.TemporaryDirectory() as tmp:
        i, o = Path(tmp) / 'in.png', Path(tmp) / 'out.png'
        to_pil(a).save(i)
        subprocess.run([sys.executable, '-I', str(TOOLS / 'mirror_logo.py'), str(i), str(o), str(k)], check=True)
        return from_pil(Image.open(o))


def seated_still(src, spec):
    """(finished still, faces) in working px: cut, faces fixed, mirrored when the spec says so."""
    a = src.still(spec)
    a, faces = with_faces(src, a, spec)
    if spec.get('mirror'):
        logo = spec['mirror'] == 'logo'
        ku = src.up(spec['src'][0])
        a, faces = mirrored(a, logo, ku), {n: mirrored(v, logo, ku) for n, v in faces.items()}
    return a, faces


def seated(src, spec, facing, k1):
    """A seated still anchored on the seat's floor point: its butt contact (spec 'seat', source px of the
    finished still) lands FACINGS[facing] (rest up, dx right; scene px at seat scale 1, k1 scene px per
    atlas px) from it."""
    ku = src.up(spec['src'][0])
    a, faces = seated_still(src, spec)
    r, faces = scaled(a, faces, spec['f'] * ATLAS_K, ku)
    bx, by = spec['seat']
    if spec.get('seat_pre') and spec.get('mirror'):      # the seat point was measured before the flip
        bx = a.shape[1] / ku - bx
    fc = FACINGS[facing]
    return Pic(r, bx * spec['f'] * ATLAS_K - fc['dx'] / k1, by * spec['f'] * ATLAS_K + fc['rest'] / k1, 'sit', faces)


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
            wcfg, _ = Wk.resolve(Wk.CHARS[name])            # super-resolved sheet when the weights are there
            frames, ays, bx, fig_h, _bob, faces = Wk.build(name, wcfg)
            Wk.pack(name, wcfg, frames, ays, bx, fig_h, faces, out_dir=d.parent, lossless=True, quiet=True)
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
        self.clips, self.poses, self.poseinfo = {}, {}, {}

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
        # turn in-betweens: real three-quarter and front views from the turnaround sheet (cfg 'turn'), each scaled
        # to the walker's crown-to-sole height, so the body keeps its thickness through the turn
        tc = cfg['turn']
        hw = (figure_h(wr) + figure_h(wl)) / 2
        like = {'qr': wr, 'front': wr, 'ql': wl}            # the walk frame each view sits next to
        views = {key: turn_view(self.src, dict(tc[key], sheet=tc['sheet']), hw, like[key]) for key in ('qr', 'front', 'ql')}
        # colour / value: each region (fur, clothes, outline) moved to the Lab mean and spread of the walk frame beside it
        for key in ('qr', 'front', 'ql'):
            v = views[key]
            views[key] = Pic(color_match.match(v.arr, like[key].arr, cfg['walker']), v.ax, v.ay, v.tag)
        # head size: each view scaled so its head matches the walk frame's (the turnaround rows draw heads bigger or
        # smaller than the walk sheet; the body follows the head)
        hf = {}
        for key in ('qr', 'front', 'ql'):
            views[key], hf[key] = head_scaled(views[key], like[key], cfg['walker'])
        # chest marks the turnaround cell drew differently: the walk frame's letters instead (cfg 'emblem': view -> box
        # of the letters in walk_r px)
        for key, box in tc.get('emblem', {}).items():
            v = views[key]
            src = wr.arr if key != 'ql' else wl.arr
            views[key] = Pic(props_mod.emblem(v.arr, src, box, head_lead_mod.cloth, cfg['walker']), v.ax, v.ay, v.tag)
        # the walk frame's props (suitcase, phone, ticket) on the views, in the same hands
        pc = tc.get('props')
        self.metrics = {}
        views['hand'] = None
        views['bare'] = {}
        if pc:
            pieces, bare_p = {}, {}
            for k, (poly, info, side) in pc['pieces'].items():
                held = k != 'case'                       # hand-held: cut with its paw, grip in piece px
                p, (ox, oy) = props_mod.piece(wr.arr, poly, cfg['walker'], head_lead_mod.cloth if held else None, paw=held)
                pieces[k] = (p, (info[0] - ox, info[1] - oy) if held else info, side)
                if held:                                 # the prop alone, for a front view with clasped paws
                    bare_p[k] = props_mod.piece(wr.arr, poly, cfg['walker'], head_lead_mod.cloth)[0]
            bare = dict(views)
            if os.environ.get('T2_DUMP_VIEWS'):          # the plain views, to read paw points off a grid
                for k_ in ('qr', 'front', 'ql'):
                    to_pil(bare[k_].arr).save(Path(os.environ['T2_DUMP_VIEWS']) / ('%s_%s.png' % (cfg['walker'], k_)))
            views['bare'] = bare                         # head-first frames take the head from the view without props
            bare['stand'] = bare['front']               # the front stand is the front view ('turn')
            for key, assign in (('qr', 'R'), ('front', 'R'), ('ql', 'L')):
                views[key], self.metrics[key] = with_props(bare[key], pieces, assign, pc['hands'][key], cfg['walker'], hf[key], bare_p)
            # the hand-over: front view, both props passed between the paws (the walk_l side holds them in the other hand)
            views['hand'] = []
            for st_ in ('C1', 'C2', 'C3'):
                v_, self.metrics['hand' + st_[1]] = with_props(bare['front'], pieces, st_, pc['hands']['front'], cfg['walker'], hf['front'], bare_p)
                views['hand'].append(v_)
        views['walk_r'], views['walk_l'] = wr, wl
        # a stepping-turn sheet (2 x 4, walking right -> facing the viewer, art/README.md), when it has come:
        # cells 2-7 replace the turnaround views; mirrored for the turn from walking left. One scale for the
        # sheet (its cells share a foot line and size): the last cell, standing, is the walker's height.
        views['step_r'] = views['step_l'] = None
        if tc.get('step') and (ROOT / tc['step']).is_file():
            cells = ['%d%d' % (i // 4, i % 4) for i in range(8)]
            ref = turn_cell(self.src, dict(sheet=tc['step'], cell=cells[-1], grid=(2, 4))).shape[0]
            for side, w in (('r', wr), ('l', wl)):
                mir = False if side == 'r' else tc.get('step_mirror', True)
                views['step_' + side] = [turn_view(self.src, dict(sheet=tc['step'], cell=c, grid=(2, 4), mirror=mir), hw, w, ref)
                                         for c in cells[1:7]]
        self.kind = cfg['walker']
        self.cut = tc.get('head_cut', {})
        self.info = {}
        for facing, fcfg in cfg['facings'].items():
            self.build_facing(facing, fcfg, wr, wl, W_r, W_l, views)
        self.facings = sorted(cfg['facings'])
        return self

    def build_facing(self, facing, fcfg, wr, wl, W_r, W_l, views):
        add, x = self.add, sfx(facing)
        k1 = self.scale * SCENE_CHAR_SCALE                     # scene px per atlas px at seat scale 1
        fc = FACINGS[facing]
        rise, slide = fc['rest'] / k1, fc['dx'] / k1           # floor point -> butt contact, atlas px
        arc = 0.22 * rise
        self.info[facing] = dict(rest=fc['rest'], dx=fc['dx'])
        P = lambda n: n + x                                     # pose / clip name at this facing

        def note(name, spec):
            """record what the pose faces and refuse a pose that does not match the seat's facing"""
            f = dict(spec['facing'], eyes=spec.get('eyes', 'open'))
            for part in ('head', 'torso', 'legs'):
                if f[part] not in SEAT_OK[facing]:
                    raise ValueError('%s%s: %s faces %s, but the seat faces %s' % (self.name, x, part, f[part], facing))
            self.poseinfo[P(name)] = f

        # ---- standing at the seat: the stand_front still, or ('walk') the walker's walk_l frame
        if fcfg['stand'] == 'walk':
            st, S0 = wl, W_l
            self.poseinfo[P('stand')] = dict(head='L', torso='L', legs='L', eyes='open')   # the walker's own 3/4-left picture
            self.poses[P('stand')] = S0
            stand_pose = P('stand')
            # facing right -> facing left through the front. The head leads: each view first shows the next
            # view's head on its own body (head_lead), then the body follows
            V = views
            hl = lambda b, h: add(head_lead(V[b], V['bare'].get(h, V[h]), self.kind, (self.cut.get(b), self.cut.get(h))))
            if V['step_r']:
                seq = [W_r] + [add(p) for p in V['step_r']] + [hl('front', 'ql'), add(V['ql']), S0]
            else:
                # the props change hands at the front (the walk_r side holds them in one hand, walk_l in the other)
                ho = [add(h) for h in V['hand']] if V['hand'] else [hl('front', 'ql')]
                # head-first frames (head_lead.py) are no longer used out of the walk either: the join left a stair step
                # and a straight seam at the collar (2026-10-29 review). (a front head on the 3/4 body is not used: the turnaround's front head is bigger and lower and tore up
                # the collar, drawstring and chest mark; the head leads only out of the walk)
                seq = [W_r, add(V['qr']), add(V['qr']), add(V['front'])] + ho + [add(V['ql']), S0]
            self.clips[P('turn_r_front')] = dict(frm='walk_r', to=stand_pose, fps=12, frames=seq)
            self.clips[P('turn_front_r')] = dict(frm=stand_pose, to='walk_r', fps=12, frames=seq[::-1])
            self.clips[P('turn_l_front')] = dict(frm='walk_l', to=stand_pose, fps=12, frames=[S0])   # already facing left
            self.clips[P('turn_front_l')] = dict(frm=stand_pose, to='walk_l', fps=12, frames=[S0])
        else:
            if fcfg['stand'] == 'turn':          # the turnaround front view, carrying the walk frame's props
                st = views['front']
                self.poseinfo['stand_front'] = dict(head='F', torso='F', legs='F', eyes='open')
            else:
                st = standing(self.src, fcfg['stand'])
                note('stand_front' if facing == 'f' else 'stand', fcfg['stand'])
            S0 = add(st)
            stand_pose = 'stand_front' if facing == 'f' else P('stand')
            self.poses[stand_pose] = S0
            # walk (3/4) -> [3/4 head on the walking body] -> turnaround 3/4 (nearer the front) -> [the stand's head on
            # the 3/4 body] -> stand: the head leads, the body follows. The turnaround's own front view is not shown
            # here: it is a second front drawing next to the stand (the tiger's head 8 % wider) and pops
            V = dict(views, stand=st)
            hl = lambda b, h: add(head_lead(V[b], V['bare'].get(h, V[h]), self.kind, (self.cut.get(b), self.cut.get(h))))
            for side, W0 in (('r', W_r), ('l', W_l)):
                if V['step_' + side]:
                    seq = [W0] + [add(p) for p in V['step_' + side]] + [S0]
                else:
                    q = 'q' + side
                    if side == 'l' and V['hand']:        # coming from walk_l: the props change hands before the stand
                        seq = [W0, add(V[q]), add(V[q])] + [add(h) for h in V['hand'][::-1]] + [S0]
                    else:
                        seq = [W0, add(V[q]), add(V[q]), add(V[q]), add(V[q]), S0, S0]
                self.clips[P('turn_%s_front' % side)] = dict(frm='walk_' + side, to=stand_pose, fps=12, frames=seq)
                self.clips[P('turn_front_%s' % side)] = dict(frm=stand_pose, to='walk_' + side, fps=12, frames=seq[::-1])

        # ---- sit_down / stand_up: a hop backwards up onto the cushion. No cross-fade: the standing
        # picture rises (stretched) to the top of the hop and is replaced there by the seated picture,
        # still in the air and stretched, which drops onto the cushion and squashes. Two different
        # pictures are never shown at once.
        sp = fcfg['sit']
        sit = seated(self.src, sp, facing, k1)
        note('sit', sp)
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

        cache = {}

        def STR(p, a_):
            """p stretched by a_ about the seat row (cached: the same picture twice is stored once)"""
            key = (id(p), round(a_, 4))
            if key not in cache:
                cache[key] = p.stretched(a_, pivot=piv)
            return cache[key]

        # ---- slow breathing: a baked vertical stretch about the seat (the butt row stays put). The period is
        # BREATH_S seconds (a calm breath, not a flutter); levels are 0 / 0.6 % / 1.2 % of the picture's height
        def breathe(p, base, fps, cycles=1, amps=BREATH_AMPS):
            """frame indices of `cycles` breaths of p (period BREATH_S): a raised cosine over the stretch levels"""
            idx = [base] + [self.add(STR(p, 1 + a_)) for a_ in amps[1:]]      # base: the pose's own frame index
            n = int(round(BREATH_S * fps))
            out = []
            for i in range(n * cycles):
                x = (1 - np.cos(2 * np.pi * i / n)) / 2
                out.append(idx[int(round(x * (len(idx) - 1)))])
            return out

        def settle(p, fps, n=2):
            """into a pose: a stretch that relaxes back to the plain picture over 1.2 s (n frames per step); the
            levels are the breath's own, so no extra pictures are stored except the first overshoot"""
            return [i for a_ in (1.025, 1.012, 1.006) for i in [self.add(STR(p, a_))] * n]

        # ---- sit_idle: breathing with blinks (every frame carries the blink patch, see Pic.faces)
        self.clips[P('sit_idle')] = dict(frm=sit_pose, to=sit_pose, fps=8, loop=True, frames=breathe(sit, T0, 8))

        # ---- activities: hard cuts hidden by a squash (out of the old pose) and a stretch (into the new)
        def cut(a, b, ia, ib):
            """frames from picture a to picture b: a squashed, b stretched (about the seat), b"""
            return [ia, add(STR(a, 0.98)), add(STR(b, 1.025)), ib]

        for kind in ('phone', 'call', 'eat'):
            if kind in fcfg:
                p = seated(self.src, fcfg[kind], facing, k1)
                note(kind, fcfg[kind])
                Pi = add(p)
                self.poses[P(kind)] = Pi
                self.clips[P(kind + '_in')] = dict(frm=sit_pose, to=P(kind), fps=8, frames=cut(sit, p, T0, Pi))
                self.clips[P(kind + '_out')] = dict(frm=P(kind), to=sit_pose, fps=8, frames=cut(p, sit, Pi, T0))
                self.clips[P(kind + '_loop')] = dict(frm=P(kind), to=P(kind), fps=8, loop=True, frames=breathe(p, Pi, 8))
        if fcfg.get('doze'):
            dz = [seated(self.src, d, facing, k1) for d in fcfg['doze']]
            D = [add(p) for p in dz]
            self.poses[P('doze')] = D[0]
            for tag, d in zip(['doze', 'doze_b', 'doze_c'], fcfg['doze']):
                note(tag, dict(d, eyes='closed'))
            fps = DOZE_FPS
            sq = lambda p: add(STR(p, 0.98))
            # settle into sleep: the sitting picture sinks (squash), the dozing one is stretched and relaxes (2 s)
            self.clips[P('doze_in')] = dict(frm=sit_pose, to=P('doze'), fps=fps, frames=[T0] * 3 + [sq(sit)] + settle(dz[0], fps) + [D[0]] * 2)
            self.clips[P('doze_out')] = dict(frm=P('doze'), to=sit_pose, fps=fps, frames=[D[0]] * 3 + [sq(dz[0])] + settle(sit, fps) + [T0] * 2)
            # one hold = two slow breaths (8 s); the director repeats it
            self.clips[P('doze_loop')] = dict(frm=P('doze'), to=P('doze'), fps=fps, loop=True, frames=breathe(dz[0], D[0], fps, 2))
            # other dozing poses: an occasional slow nod (about 1 s, squash and stretch) into one, a hold, and back
            for tag, p, i in zip('bc', dz[1:], D[1:]):
                self.poses[P('doze_' + tag)] = i
                self.clips[P('doze_nod_' + tag)] = dict(frm=P('doze'), to=P('doze_' + tag), fps=fps, frames=[D[0], sq(dz[0])] + settle(p, fps, 1) + [i])
                self.clips[P('doze_back_' + tag)] = dict(frm=P('doze_' + tag), to=P('doze'), fps=fps, frames=[i, sq(p)] + settle(dz[0], fps, 1) + [D[0]])
                self.clips[P('doze_loop_' + tag)] = dict(frm=P('doze_' + tag), to=P('doze_' + tag), fps=fps, loop=True, frames=breathe(p, i, fps, 2))

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
               'facings': self.facings, 'scale': self.scale, 'mirrorable': False, 'frames': self.frames, 'poses': self.poses, 'poseInfo': self.poseinfo, 'clips': clips}
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
    if getattr(b, 'metrics', None):           # prop gap / pieces per turn view, for the turn table (turn_preview.py)
        d = ROOT / 'art/cutouts/turns'; d.mkdir(parents=True, exist_ok=True)
        (d / ('%s_props.json' % name)).write_text(json.dumps({k: {n: [round(g, 2), c] for n, (g, c) in v.items()} for k, v in b.metrics.items()}, sort_keys=True))
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
