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
PENGUIN_WALK = S + 'penguin_walk_sheet_4x4_gemini.webp'
HOPSIT = S + 'penguin_hop_sit_sheet_4x4_gemini.webp'
# sheets with full-width guide lines drawn across each row (the sofa lines Gemini was asked for): painted
# out before cutting (unline()); never super-resolved (the SR copy would still have them)
LINED = {HOPSIT}
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
    'tiger': dict(walker='tiger', facings={
        'f': dict(
            # surprised "o" mouth -> the small smile of the seated cell (same sheet family, 1.13x bigger there)
            stand=dict(src=(STAND_A, '02'), f=0.479, facing=F('F', 'F', 'F'), face=dict(sheet=CLIMB_A, fix=dict(
                cell='23', scale=1.13, erase=[(132, 177, 14, 17)], feats=[dict(box=(90, 128, 148, 152), at=(127, 163))]))),
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
    'rabbit': dict(walker='rabbit', facings={
        'f': dict(
            # the boots of the cell above poke into this one, touching the left ear tip: cut away
            stand=dict(src=(RABBIT_POSE, '31'), f=0.528, facing=F('F', 'F', 'F'),
                       cut=[[(48, 0), (112, 0), (112, 52), (99, 52), (93, 40), (84, 26), (74, 17), (62, 12), (48, 8)], [(100, 0), (186, 0), (186, 35), (172, 43), (160, 49), (100, 54)]]),
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
    'turtle': dict(walker='turtle', facings={
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
    # the penguin (art/README.md): walker from art/tools/build_penguin_walk.py (whole cells of the waddle sheet,
    # with a hop); everything seated from the hop-and-sit sheet (HOPSIT, whole cells only). f: the hop-sit heads
    # are 1/1.09 of the waddle's (template match on the head), the walk sheet's row 4 1/1.13 of its row 1.
    # Seat points: the middle between the two feet, on the body's bottom outline there (measured).
    # sit_down is a real hop drawn cell by cell ('hop': crouch, jump, in the air, land, plop down, turn), stand_up
    # the same backwards; the eat pose holds the cup and the drawn sip ('sip', eyes shut) plays going in and out;
    # 'wave' is a one-shot clip. finish: build_penguin_walk.finish() on every picture (outline ring, fringe).
    'penguin': dict(walker='penguin', finish=True, facings={
        'f': dict(
            # mirrored: the cup goes to the same flipper as in every other frame (front view, no text: safe)
            stand=dict(src=(PENGUIN_WALK, '30'), f=1.422, mirror=True, facing=F('F', 'F', 'F')),
            # turned a little to the viewer's right all over (head, scarf, feet); blink: the calm closed eyes of f_20,
            # smile: the happy closed eyes of f_13 (both front cells of the same sheet), the far eye narrower; the far eye sits
            # by the dark side of the head, so its hole is filled from a white spot of the face (`skin`, picked by face_white)
            sit=dict(src=(HOPSIT, '23'), f=1.352, seat=(80, 159), facing=F('Fr', 'Fr', 'Fr'), face=dict(sheet=HOPSIT, variants={
                'blink': dict(cell='20', scale=1.0, erase=[(65.2, 57.7, 6.5, 7.5), dict(e=(95.7, 56.3, 4.5, 6.5), skin=(89.7, 56.3))],
                              feats=[dict(box=(23, 57, 41, 67), at=(65.2, 59)), dict(box=(62, 56, 80, 66), at=(95.7, 57.5), scale=0.75)]),
                'smile': dict(cell='13', scale=1.0, erase=[(65.2, 57.7, 6.5, 7.5), dict(e=(95.7, 56.3, 4.5, 6.5), skin=(89.7, 56.3))],
                              feats=[dict(box=(23, 55, 40, 65), at=(65.2, 57.5)), dict(box=(63, 55, 81, 64), at=(95.7, 56), scale=0.75)])})),
            eat=dict(src=(HOPSIT, '22'), f=1.352, seat=(79, 160), facing=F('Fr', 'Fr', 'Fr'), face=dict(sheet=HOPSIT, variants={
                'blink': dict(cell='20', scale=1.0, erase=[(64.9, 58.2, 6.5, 7.5), dict(e=(95.4, 55.9, 4.5, 6.5), skin=(89.4, 55.9))],
                              feats=[dict(box=(23, 57, 41, 67), at=(64.9, 59.5)), dict(box=(62, 56, 80, 66), at=(95.4, 57), scale=0.75)])})),
            sip=dict(src=(HOPSIT, '21'), f=1.352, seat=(80, 158)),
            wave=dict(src=(HOPSIT, '33'), f=1.352, seat=(81, 162)),
            doze=[dict(src=(HOPSIT, '32'), keep='largest', f=1.352, seat=(81, 157), facing=F('Fr', 'Fr', 'Fr')),
                  dict(src=(HOPSIT, '20'), f=1.352, seat=(54, 156), facing=F('F', 'F', 'F'))],
            hop=[dict(src=(HOPSIT, '01'), f=1.352, lift=0, slide=0, hold=2),         # crouch
                 dict(src=(HOPSIT, '02'), f=1.352, lift=0.35, slide=0.3),            # take-off
                 dict(src=(HOPSIT, '03'), f=1.352, lift=1, slide=0.85, arc=True, lane=True),   # in the air: now in front of the sofa
                 dict(src=(HOPSIT, '10'), f=1.352, lift=1, slide=1, cut=[[(110, 82), (132, 82), (132, 89), (110, 89)]]),   # lands on the cushion (cut: sofa-line stubs over the lid)
                 dict(src=(HOPSIT, '11'), f=1.352, seat=(83, 150), hold=2, keep='largest', transplant=[dict(cell='00', box=(108, 74, 139, 98), key=(111, 87, 135, 104), search=(100, 80, 140, 118))]),   # plops down (lid: the sofa line took it)
                 dict(src=(HOPSIT, '12'), f=1.352, seat=(85, 152), keep='largest', transplant=[dict(cell='00', box=(108, 74, 139, 98), key=(111, 87, 135, 104), search=(104, 82, 144, 120))])],   # turns to the front
        ),
        'l': dict(
            stand='walk',
            # the three-quarter-right cells mirrored (no text on the penguin; the cup changes flipper)
            sit=dict(src=(HOPSIT, '30'), f=1.352, mirror=True, seat=(142 - 85, 159), facing=F('L', 'L', 'L'), face=dict(sheet=HOPSIT, variants={
                'blink': dict(cell='31', scale=1.0, erase=[(69.6, 57.8, 6.5, 7.5), dict(e=(99.9, 55.9, 4.5, 6.5), skin=(93.9, 55.9))],      # coordinates before the flip
                              feats=[dict(box=(57, 56, 74, 64), at=(69.6, 59.5)), dict(box=(91, 53, 103, 61), at=(99.9, 57.5))])})),
            eat=dict(src=(HOPSIT, '22'), f=1.352, mirror=True, seat=(118 - 79, 160), facing=F('Fl', 'Fl', 'Fl'), face=dict(sheet=HOPSIT, variants={
                'blink': dict(cell='20', scale=1.0, erase=[(64.9, 58.2, 6.5, 7.5), dict(e=(95.4, 55.9, 4.5, 6.5), skin=(89.4, 55.9))],
                              feats=[dict(box=(23, 57, 41, 67), at=(64.9, 59.5)), dict(box=(62, 56, 80, 66), at=(95.4, 57), scale=0.75)])})),
            sip=dict(src=(HOPSIT, '21'), f=1.352, mirror=True, seat=(119 - 80, 158)),
            wave=dict(src=(HOPSIT, '33'), f=1.352, mirror=True, seat=(134 - 81, 162)),
            doze=[dict(src=(HOPSIT, '32'), keep='largest', f=1.352, mirror=True, seat=(133 - 81, 157), facing=F('Fl', 'Fl', 'Fl')),
                  dict(src=(HOPSIT, '31'), f=1.352, mirror=True, seat=(120 - 81, 160), facing=F('L', 'L', 'L'))],
            hop=[dict(src=(HOPSIT, '01'), f=1.352, mirror=True, lift=0, slide=0, hold=2),
                 dict(src=(HOPSIT, '02'), f=1.352, mirror=True, lift=0.35, slide=0.3),
                 dict(src=(HOPSIT, '03'), f=1.352, mirror=True, lift=1, slide=0.85, arc=True, lane=True),
                 dict(src=(HOPSIT, '10'), f=1.352, mirror=True, lift=1, slide=1, cut=[[(110, 82), (132, 82), (132, 89), (110, 89)]]),
                 dict(src=(HOPSIT, '11'), f=1.352, mirror=True, seat=(140 - 83, 150), hold=2, keep='largest', transplant=[dict(cell='00', box=(108, 74, 139, 98), key=(111, 87, 135, 104), search=(100, 80, 140, 118))])],
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
            if self.sr and sheet not in LINED and Image.open(ROOT / sheet).width < 1500:
                im = sr_upscale.upscale(ROOT / sheet)
                if im is not None:
                    p = self.tmp / ('sr_%d.png' % len(self.srs))
                    im.save(p, compress_level=1)
                    self.srs[sheet] = p
        return self.srs[sheet]

    def up(self, sheet):
        return 4 if self.sr_png(sheet) else 1

    def cells(self, sheet):
        if sheet not in self.cache:
            out = self.tmp / ('cells_%d' % len(self.cache))
            sr = self.sr_png(sheet)
            path = ROOT / sheet
            if sheet in LINED:
                path = self.tmp / ('unlined_%d.png' % len(self.cache))
                Image.fromarray(unline(np.asarray(Image.open(ROOT / sheet).convert('RGB')))).save(path)
            subprocess.run([sys.executable, '-I', str(TOOLS / 'cut_sheet.py'), str(path), str(out), '4', '4'] + ([str(sr)] if sr else []),
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
            a = from_pil(Image.open(self.cells(sheet) / ('f_%s.png' % cell)))
        for tp in spec.get('transplant', []):
            a = transplant(a, from_pil(Image.open(self.cells(sheet) / ('f_%s.png' % tp['cell']))), tp, k)
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


def transplant(a, donor, tp, k=1):
    """Put a small piece of another cell of the same sheet onto this one (a detail the cell lost or drew
    differently): tp = dict(cell, box=(x0, y0, x1, y1) of the piece in the donor, key=(x0, y0, x1, y1) a part of
    it that is intact in this cell too (registers it), search=(x0, y0, x1, y1) where to look here; source px).
    The key is found by template matching over scales 0.75-1.25 (grey with alpha); the piece is scaled the same
    and laid over this cell by its own alpha (the cell's own pixels under the piece are replaced)."""
    def gray(x):
        g = x[..., :3] @ np.float32([0.3, 0.59, 0.11])
        return g * (x[..., 3] / 255) + 128 * (1 - x[..., 3] / 255)
    bx0, by0, bx1, by1 = [int(v * k) for v in tp['box']]
    kx0, ky0, kx1, ky1 = [int(v * k) for v in tp['key']]
    sx0, sy0, sx1, sy1 = [int(v * k) for v in tp['search']]
    key = gray(donor)[ky0:ky1, kx0:kx1]
    win = np.pad(gray(a), 4, constant_values=128)[sy0:sy1 + 8, sx0:sx1 + 8]
    best = None
    for s_ in np.arange(0.75, 1.26, 0.025):
        t = cv2.resize(key, None, fx=s_, fy=s_, interpolation=cv2.INTER_AREA)
        if t.shape[0] > win.shape[0] or t.shape[1] > win.shape[1]:
            continue
        r = cv2.matchTemplate(win.astype(np.float32), t.astype(np.float32), cv2.TM_CCOEFF_NORMED)
        _, mv, _, ml = cv2.minMaxLoc(r)
        if best is None or mv > best[0]:
            best = (mv, s_, sx0 - 4 + ml[0], sy0 - 4 + ml[1])
    _, s_, kx, ky = best                                  # where the key's top-left lands, at scale s_
    piece = resize(donor[by0:by1, bx0:bx1], (bx1 - bx0) * s_, (by1 - by0) * s_)
    px, py = int(round(kx - (kx0 - bx0) * s_)), int(round(ky - (ky0 - by0) * s_))
    out = a.copy()
    h, w = piece.shape[:2]
    y0, x0 = max(py, 0), max(px, 0)
    y1, x1 = min(py + h, a.shape[0]), min(px + w, a.shape[1])
    pc = piece[y0 - py:y1 - py, x0 - px:x1 - px]
    al = pc[..., 3:] / 255.
    reg = out[y0:y1, x0:x1]
    reg[..., :3] = pc[..., :3] * al + reg[..., :3] * (1 - al)
    reg[..., 3] = np.maximum(reg[..., 3], pc[..., 3])
    return out


def unline(rgb, reach=5):
    """Paint out the full-width guide lines of a sheet (the sofa lines Gemini drew across each row of the
    penguin's hop-and-sit sheet): a dark grey pixel on a line row takes the mean of the pixels `reach` rows
    above and below when those two agree (the line ran over the background or over one colour); where
    they differ (an outline crosses it) the pixel stays. The lines run behind the figures.
    (Where a line ran along an outline - the cup lids of f_10-f_12 - it took the outline with it: those
    lids are transplanted from an intact cell, spec 'transplant'.)"""
    a = rgb.astype(np.float32)
    rows = np.nonzero((a.max(-1) < 90).mean(1) > 0.5)[0]
    out = a.copy()
    H = a.shape[0]
    for y in rows:
        up, dn = a[max(0, y - reach)], a[min(H - 1, y + reach)]
        same = np.abs(up - dn).max(-1) < 40
        for yy in range(max(0, y - 3), min(H, y + 4)):
            t = (yy - (y - reach)) / (2.0 * reach)              # blend row by row (a flat fill showed as streaks)
            fill = up * (1 - t) + dn * t
            px = a[yy]
            line = (px.max(-1) < 230) & (px.max(-1) - px.min(-1) < 35) & (np.abs(px - fill).max(-1) > 12)
            m = line & same
            out[yy][m] = fill[m]
    return out.clip(0, 255).astype(np.uint8)


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
    if spec.get('mirror'):                  # (no face spec with a mirrored standing still yet)
        a = mirrored(a)
    x = spec['x'] * ku if 'x' in spec else feet_x(a)
    a, faces = with_faces(src, a, spec)
    r, faces = scaled(a, faces, spec['f'] * ATLAS_K, ku)
    return Pic(r, x * r.shape[1] / a.shape[1], r.shape[0] - 1, 'stand', faces)


def hop_pic(src, spec):
    """A whole cell of a hop (crouch, take-off, in the air, landing), anchored on the floor between its feet like
    standing(), mirrored when the spec says so (lift / slide are applied by the caller)."""
    spec = dict(spec, keep=spec.get('keep', 'largest'))
    ku = src.up(spec['src'][0])
    a = src.still(spec)
    if spec.get('mirror'):
        a = mirrored(a)
    x = feet_x(a)
    r, _ = scaled(a, {}, spec['f'] * ATLAS_K, ku)
    return Pic(r, x * r.shape[1] / a.shape[1], r.shape[0] - 1, 'hop')


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
        elif name == 'penguin':
            import build_penguin_walk as P
            walk, blinks, hop, step = P.frames()
            P.pack(walk, blinks, hop, step, d, lossless=True)
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
            grow = [add(wl.squeezed(s, 0.12 * (1 - s))) for s in (0.4, 0.75)]
            flip_r = [W_r] + shrink['r'] + grow + [S0]          # paper flip: facing right -> facing left
            self.clips[P('turn_r_front')] = dict(frm='walk_r', to=stand_pose, fps=12, frames=flip_r)
            self.clips[P('turn_front_r')] = dict(frm=stand_pose, to='walk_r', fps=12, frames=flip_r[::-1])
            self.clips[P('turn_l_front')] = dict(frm='walk_l', to=stand_pose, fps=12, frames=[S0])   # already facing left
            self.clips[P('turn_front_l')] = dict(frm=stand_pose, to='walk_l', fps=12, frames=[S0])
        else:
            st = standing(self.src, fcfg['stand'])
            note('stand_front' if facing == 'f' else 'stand', fcfg['stand'])
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
        if fcfg.get('hop'):
            # a hop drawn cell by cell (the penguin): each cell placed on the floor point raised by lift x rise and moved
            # slide x slide (feet cells), or on the seat by its butt contact (seated cells); 'hold' repeats a cell.
            # stand_up is the same hop backwards (a hop down off the sofa).
            seq, lane_at = [S0], None
            for h in fcfg['hop']:
                if 'seat' in h:
                    p_ = seated(self.src, h, facing, k1)
                else:
                    p_ = hop_pic(self.src, h).moved(rise * h['lift'] + (arc if h.get('arc') else 0), slide * h['slide'])
                if h.get('lane'):
                    lane_at = len(seq)
                seq += [add(p_)] * h.get('hold', 1)
            seq.append(T0)
            self.clips[P('sit_down')] = dict(frm=stand_pose, to=sit_pose, fps=12, frames=seq, laneSwitchAt=lane_at)
            self.clips[P('stand_up')] = dict(frm=sit_pose, to=stand_pose, fps=12, frames=seq[::-1], laneSwitchAt=len(seq) - lane_at)

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
                if kind == 'eat' and fcfg.get('sip'):
                    # a drawn sip (eyes shut, cup at the beak) on the way into and out of holding the cup (half a second)
                    sp_ = seated(self.src, fcfg['sip'], facing, k1)
                    Si = add(sp_)
                    sip = [add(STR(sp_, 1.025))] + [Si] * 4 + [add(STR(sp_, 0.98))]
                    self.clips[P('eat_in')] = dict(frm=sit_pose, to=P(kind), fps=8, frames=[T0, add(STR(sit, 0.98))] + sip + [add(STR(p, 1.025)), Pi])
                    self.clips[P('eat_out')] = dict(frm=P(kind), to=sit_pose, fps=8, frames=[Pi, add(STR(p, 0.98))] + sip + [add(STR(sit, 1.025)), T0])
        if fcfg.get('wave'):
            # a one-shot wave from the seat (the director's 'wave' activity): out of the sitting picture by a squash,
            # the waving cell held a second, back
            wv = seated(self.src, fcfg['wave'], facing, k1)
            Wi = add(wv)
            self.clips[P('wave')] = dict(frm=sit_pose, to=sit_pose, fps=8,
                                         frames=[T0, add(STR(sit, 0.98)), add(STR(wv, 1.025))] + [Wi] * 9 + [add(STR(wv, 0.98)), add(STR(sit, 1.025)), T0])
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
        if self.cfg.get('finish'):
            # the penguin's pixel finishing pass (build_penguin_walk.finish): the outline ring in the drawing's
            # line colour, no fringe, halo, specks or pinholes; on every new picture and its faces
            import build_penguin_walk as PW
            line = PW.line_colour(PW.load(PW.REF))
            for p in self.pics:
                p.arr = PW.finish(p.arr, line, pockets=False)
                p.faces = {n: PW.finish(v, line, pockets=False) for n, v in p.faces.items()}
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
        for cid in wm['clips']:                      # walk_r / walk_l, and the penguin's hop_r / hop_l
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
