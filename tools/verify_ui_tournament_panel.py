#!/usr/bin/env python3
"""UI tournament-info / standings drawer wiring checks.

Static only: no runtime state or sidecar is read/written.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'ui/web/app.js').read_text(encoding='utf-8')
INDEX = (ROOT / 'ui/web/index.html').read_text(encoding='utf-8')
CSS = (ROOT / 'ui/web/style.css').read_text(encoding='utf-8')
SERVER = (ROOT / 'ui/server/ui_server.py').read_text(encoding='utf-8')
VIEW = (ROOT / 'ui/server/ui_view.py').read_text(encoding='utf-8')

checks = 0

def need(cond, msg):
    global checks
    if not cond:
        raise AssertionError(msg)
    checks += 1

# Requested settings are gone, not merely hidden behind old localStorage.
need('STEP_CHOICES' not in APP, 'bot-action interval choices still present')
need("const AUTO_KEY" not in APP, 'result auto preference still present')
menu = APP[APP.index('async function showMenu()'):APP.index('function showHandDetail')]
info = APP[APP.index('function tournamentInfoHTML'):APP.index('function renderRankDrawer')]
need('mStep' not in menu and '봇 액션 간격' not in menu,
     'bot action interval control still in menu')
need('mAuto' not in menu and '자동 진행 끄기' not in menu
     and '자동 진행 켜기' not in menu
     and '결과 화면' not in menu,
     'result/auto-progress control still in menu')

# Field summary moved out of top bar into tournament info/menu.
# Since the virtual-clock work the top line shows only the elapsed play time (or the legacy label),
# never the field summary (ITM / players / levels), which lives in the tournament info and menu.
fieldline = APP[APP.index("if ($('#fieldline'))"):]
fieldline = fieldline[:fieldline.index('\n  }\n') + 5]
need('경과' in fieldline and '기존 대회' in fieldline, 'top line is not the elapsed-time line')
need('ITM' not in fieldline and '남은' not in fieldline and 'rank' not in fieldline,
     'top bar still carries the field summary')
for s in ('ITM', '레벨', '블라인드', '다음 머니점프'):
    need(s in info, 'tournament info missing %r' % s)
# Own chip rank moved from the info panel to the standings drawer summary (102556c9).
_d0 = APP.index('function renderRankDrawer')
drawer = APP[_d0:APP.index('\nfunction ', _d0 + 10)]
need('내 칩순위' in drawer, 'standings drawer summary missing own chip rank')
need('대회 정보' in menu, "menu missing '대회 정보'")
# 102556c9: the standings button left the menu on purpose; the drawer opens by swipe only (checked below).
need('mRanks' not in menu and '전체 봇 스택 순위' not in menu, 'menu still has the removed standings button')

# Standings endpoint returns only public tournament/stack/seat data.
need("if path == '/api/tournament':" in SERVER,
     '/api/tournament route missing')
need('def _tournament_payload():' in SERVER,
     'tournament payload helper missing')
for s in ("'standings': rows", "'hero_rank':", "'money_jumps':",
          "'current_prize_pct':", "'next_rank':"):
    need(s in SERVER, 'tournament payload missing %r' % s)

# Right swipe opens a distinct drawer; left swipe/close/scrim closes it.
for s in ('id="rankDrawer"', 'id="rankScrim"', 'id="rankSummary"',
          'id="rankList"'):
    need(s in INDEX, 'drawer shell missing %r' % s)
# The fixed-threshold swipe (dx >= 80 / dx <= -70) became a drag-follow drawer (bindRankDrag):
# opening binds the table and hero areas at the screen edge, closing binds the drawer itself.
need("bindRankDrag($('#tablewrap'), true" in APP and "bindRankDrag($('#hero'), true" in APP
     and 'if (opening) openRankDrawer(fromMenu);' in APP and 'RANK_EDGE_PX' in APP,
     'right-drag open wiring missing')
need("bindRankDrag($('#rankDrawer'), false" in APP and 'else closeRankDrawer();' in APP
     and "$('#rankScrim').addEventListener('click', closeRankDrawer)" in APP,
     'left-drag/scrim close wiring missing')
need('#rankDrawer' in CSS and '.rankrow.hero' in CSS,
     'standings drawer styling missing')

# Dead BTN/SB UI provenance.
need("'sb_seat': getattr(hand, 'sb_seat', None)" in VIEW,
     'server view does not expose SB marker')
need("'bb_seat': getattr(hand, 'bb_seat', None)" in VIEW,
     'server view does not expose BB marker')
need("SB · DEAD" in APP, 'dead SB is not rendered')
need("deadBTN" in APP, 'dead button marker is not rendered on empty seat')

# Hero action controls rise without reflowing the table/background.
need('position: absolute;' in CSS[CSS.index('#actionbar {'):CSS.index('#mainrow')],
     'hero action dock is not out of flex flow')
need('padding-bottom: calc(68px + env(safe-area-inset-bottom))' in CSS,
     'fixed action dock space is not reserved')
need('#actionbar.turn-open #mainrow' in CSS and 'heroactionup' in CSS,
     'hero action rise animation missing')
need("bar.classList.add('turn-open')" in APP,
     'hero turn does not trigger action rise')
need("actionBar.classList.remove('turn-open')" in APP,
     'submitted hero action does not clear turn animation state')

# Cache tags must point to this build.
# The exact numbers (52 / 66) were frozen at the time this check was written; every later web change
# bumps them again. The contract is that the tags exist and never go below those first values.
import re
_css = re.search(r'style\.css\?v=(\d+)', INDEX)
_app = re.search(r'app\.js\?v=(\d+)', INDEX)
need(_css and int(_css.group(1)) >= 52, 'style cache tag missing or below 52')
need(_app and int(_app.group(1)) >= 66, 'app cache tag missing or below 66')

print({'checks': checks,
       'menu_clean': True,
       'tournament_info': True,
       'standings_drawer': True,
       'dead_blind_ui': True})
print('PASS UI tournament menu / swipe standings contract')
