'use strict';
// Development tool (not run in CI): serves ui/web with a fake lobby API, opens the lobby in headless
// Chromium at phone size, pins the scene to chosen moments, and writes screenshots plus frame timings.
//
//   node ui/tools/lounge_screens.js [outDir]      default outDir: docs/lounge
//   PLAYWRIGHT_MODULE=/path/to/playwright CHROMIUM=/path/to/chrome node ui/tools/lounge_screens.js
const fs = require('fs');
const http = require('http');
const path = require('path');

const WEB = process.env.LOUNGE_WEB ? path.resolve(process.env.LOUNGE_WEB) : path.join(__dirname, '../web');
const OUT = path.resolve(process.argv[2] || path.join(__dirname, '../../docs/lounge'));
const PW = process.env.PLAYWRIGHT_MODULE || '/opt/node-tools/node_modules/playwright';
const CHROMIUM = process.env.CHROMIUM || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.svg': 'image/svg+xml' };
const KST = 9 * 3600e3;
const MOMENTS = [['0300', 2026, 3, 20, 3, 0], ['0640', 2026, 3, 20, 6, 40], ['1200', 2026, 3, 20, 12, 0], ['1840', 2026, 3, 20, 18, 40], ['2100', 2026, 3, 20, 21, 0]];

function lobbyPayload() {
  const now = Math.floor(Date.now() / 1000);
  const mk = (id, key, name, mins, status, open, mine) => ({
    id, key, name, starts_at: now + mins * 60, closes_at: now + (mins + 60) * 60, status, registration_open: open,
    buyin: 1000, prize_pool: 9000, entries: 12, remaining: 12, level_minutes: 10, active: false, can_reenter: false,
    my_entry: mine ? { status: 'reserved', entry_no: 1 } : null, progress: null,
  });
  return {
    tournaments: [mk('t1', 'standard', '표준 토너먼트', 20, 'scheduled', true, true), mk('t2', 'turbo', '터보 토너먼트', 80, 'scheduled', true, false),
      mk('t3', 'deep', '딥스택 토너먼트', 140, 'scheduled', false, false)],
    wallet: { balance: 25000 }, server_now: now, can_play: true, active_tournament: null, current: null,
  };
}

function serve() {
  return new Promise(resolve => {
    const srv = http.createServer((req, res) => {
      const url = decodeURIComponent(req.url.split('?')[0]);
      if (url === '/api/lobby') { res.setHeader('Content-Type', 'application/json'); return res.end(JSON.stringify(lobbyPayload())); }
      if (url.startsWith('/api/')) { res.statusCode = 404; return res.end('{}'); }
      const file = path.join(WEB, url === '/' ? 'lobby.html' : url);
      if (!file.startsWith(WEB) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.statusCode = 404; return res.end('not found'); }
      res.setHeader('Content-Type', MIME[path.extname(file)] || 'application/octet-stream');
      res.setHeader('Cache-Control', 'no-store');
      res.end(fs.readFileSync(file));
    }).listen(0, '127.0.0.1', () => resolve(srv));
  });
}

(async () => {
  const { chromium } = require(PW);
  fs.mkdirSync(OUT, { recursive: true });
  const srv = await serve();
  const base = 'http://127.0.0.1:' + srv.address().port + '/';
  const browser = await chromium.launch({ executablePath: CHROMIUM, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 393, height: 852 }, deviceScaleFactor: 2.75, locale: 'ko-KR', timezoneId: 'Asia/Seoul' });
  const page = await ctx.newPage();
  const problems = [];
  page.on('pageerror', e => problems.push('pageerror: ' + e.message));
  page.on('console', m => { if (['error', 'warning'].includes(m.type())) problems.push(m.type() + ': ' + m.text()); });
  await page.goto(base + '?lounge_debug=1');
  await page.waitForSelector('#lounge.lounge-ready', { timeout: 15000 });
  const scene = page.locator('#lounge');
  const report = [];
  for (const [label, y, m, d, hh, mm] of MOMENTS) {
    const ms = Date.UTC(y, m - 1, d, hh, mm) - KST;
    await page.evaluate(ms => { const h = T2Lounge.debugHandle(); h.setPlace(37.5665, 126.978); h.setClock(ms); h.reseed(4); }, ms);
    await page.waitForTimeout(9000);                        // let people walk in and sit down
    const info = await page.evaluate(() => { const i = T2Lounge.debugHandle().info(); return { elev: i.sun.elevation, az: i.sun.azimuth, people: i.people }; });
    await scene.screenshot({ path: path.join(OUT, 'lounge_' + label + '.png') });
    report.push(label + ' KST: sun ' + info.elev.toFixed(1) + ' deg, azimuth ' + info.az.toFixed(0) + ', ' + info.people + ' people');
  }
  await page.evaluate(() => { const h = T2Lounge.debugHandle(); h.setClock(null); });
  await page.waitForTimeout(8000);
  const stats = await page.evaluate(() => T2Lounge.debugHandle().stats());
  await page.screenshot({ path: path.join(OUT, 'lobby_full.png') });
  console.log(report.join('\n'));
  console.log('frame cost over %d frames: avg %s ms, p95 %s ms (target avg <= 6, p95 <= 12)', stats.n, stats.avg.toFixed(2), stats.p95.toFixed(2));
  if (problems.length) console.log('page problems:\n  ' + problems.join('\n  '));
  await browser.close(); srv.close();
  process.exit(problems.some(p => !/lounge\/debug\.js|404/.test(p)) ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
