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
need("$('#fieldline').textContent = ''" in APP, 'top field summary not cleared')
for s in ('ITM', '레벨', '블라인드', '내 칩순위', '다음 머니점프'):
    need(s in info, 'tournament info missing %r' % s)
for s in ('대회 정보', '전체 봇 스택 순위'):
    need(s in menu, 'menu missing %r' % s)

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
need("if (dx >= 80" in APP and 'openRankDrawer()' in APP,
     'right-swipe open wiring missing')
need("if (dx <= -70" in APP and 'closeRankDrawer()' in APP,
     'left-swipe close wiring missing')
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
need('style.css?v=52' in INDEX, 'style cache tag not bumped')
need('app.js?v=66' in INDEX, 'app cache tag not bumped')

print({'checks': checks,
       'menu_clean': True,
       'tournament_info': True,
       'standings_drawer': True,
       'dead_blind_ui': True})
print('PASS UI tournament menu / swipe standings contract')
