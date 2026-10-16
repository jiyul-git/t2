/* Sun and moon position for the lobby lounge scene (docs/LOUNGE_SCENE_DESIGN.md 5.1-5.2).
   Pure functions: no DOM, no network. NOAA Solar Calculator (Meeus) equations. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.T2LoungeSun = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const RAD = Math.PI / 180, DEG = 180 / Math.PI;
  const DAY_MS = 86400000;
  const SYNODIC_DAYS = 29.530588853;
  const NEW_MOON_MS = Date.UTC(2000, 0, 6, 18, 14);
  const norm = (v, m) => ((v % m) + m) % m;

  // elevation: degrees above the horizon, no refraction. azimuth: degrees, north=0, clockwise.
  function sunPosition(date, lat, lon) {
    const ms = date instanceof Date ? date.getTime() : Number(date);
    const jd = ms / DAY_MS + 2440587.5;
    const T = (jd - 2451545) / 36525;
    const L0 = norm(280.46646 + T * (36000.76983 + T * 0.0003032), 360);
    const M = 357.52911 + T * (35999.05029 - 0.0001537 * T);
    const e = 0.016708634 - T * (0.000042037 + 0.0000001267 * T);
    const Mr = M * RAD;
    const C = Math.sin(Mr) * (1.914602 - T * (0.004817 + 0.000014 * T)) +
      Math.sin(2 * Mr) * (0.019993 - 0.000101 * T) + Math.sin(3 * Mr) * 0.000289;
    const trueLong = L0 + C;
    const omega = 125.04 - 1934.136 * T;
    const lambda = trueLong - 0.00569 - 0.00478 * Math.sin(omega * RAD);
    const eps0 = 23 + (26 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60) / 60;
    const eps = eps0 + 0.00256 * Math.cos(omega * RAD);
    const dec = Math.asin(Math.sin(eps * RAD) * Math.sin(lambda * RAD));
    const y = Math.tan(eps * RAD / 2) ** 2;
    const L0r = L0 * RAD;
    const eot = 4 * DEG * (y * Math.sin(2 * L0r) - 2 * e * Math.sin(Mr) +
      4 * e * y * Math.sin(Mr) * Math.cos(2 * L0r) - 0.5 * y * y * Math.sin(4 * L0r) -
      1.25 * e * e * Math.sin(2 * Mr));
    const utcMin = norm(ms, DAY_MS) / 60000;
    const solarMin = norm(utcMin + eot + 4 * lon, 1440);
    const H = (solarMin / 4 - 180) * RAD;
    const phi = lat * RAD;
    const cosZenith = Math.sin(phi) * Math.sin(dec) + Math.cos(phi) * Math.cos(dec) * Math.cos(H);
    const elevation = 90 - Math.acos(Math.max(-1, Math.min(1, cosZenith))) * DEG;
    const azimuth = norm(Math.atan2(Math.sin(H), Math.cos(H) * Math.sin(phi) - Math.tan(dec) * Math.cos(phi)) * DEG + 180, 360);
    return { elevation, azimuth };
  }

  // 0 = new moon, 0.5 = full moon. Decorative accuracy only.
  function moonPhase(date) {
    const ms = date instanceof Date ? date.getTime() : Number(date);
    return norm((ms - NEW_MOON_MS) / DAY_MS / SYNODIC_DAYS, 1);
  }

  // Approximation: the moon trails the sun by `phase` days.
  function moonPosition(date, lat, lon) {
    const ms = date instanceof Date ? date.getTime() : Number(date);
    return sunPosition(new Date(ms - moonPhase(ms) * DAY_MS), lat, lon);
  }

  return { sunPosition, moonPhase, moonPosition };
});
