/* Loads scene.json, background layers and character atlases (docs/LOUNGE_SCENE_DESIGN.md 6).
   A scene or layer that fails to load rejects the whole load so the page can fall back to the
   still illustration; a single character that fails to load is simply left out. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.T2LoungeAssets = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  function browserIO() {
    return {
      json: url => fetch(url, { cache: 'no-cache' }).then(r => {
        if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + url);
        return r.json();
      }),
      image: url => new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error('image failed: ' + url));
        img.src = url;
      }),
    };
  }

  // io = { json(url), image(url) }; isActive(manifest) tells which characters can appear.
  async function loadAssets(base, io, isActive) {
    const at = rel => base + rel;
    const images = new Map();
    const image = rel => {
      if (!images.has(rel)) images.set(rel, io.image(at(rel)));
      return images.get(rel);
    };
    const scene = await io.json(at('scene.json'));
    const layers = await Promise.all(scene.layers.map(async def => {
      const variants = await Promise.all(def.variants.slice().sort((a, b) => a.elev - b.elev)
        .map(async v => ({ elev: v.elev, img: await image(v.file) })));
      return { def, variants, emission: def.emission ? await image(def.emission) : null };
    }));
    const floorLight = scene.floorLight ? await image(scene.floorLight.file) : null;
    const planes = scene.planes ? { right: await image(scene.planes.right), left: await image(scene.planes.left) } : null;
    // weather plates (overcast window pictures): one that fails to load only switches that weather off
    let weather = null;
    if (scene.weather && scene.weather.plates) {
      weather = {};
      await Promise.all(Object.keys(scene.weather.plates).map(async kind => {
        try { weather[kind] = await image(scene.weather.plates[kind]); } catch (e) {
          if (typeof console !== 'undefined') console.warn('lounge: weather plate left out:', kind, e && e.message);
        }
      }));
    }
    const chars = [];
    await Promise.all((scene.characters || []).map(async (name, i) => {
      try {
        const manifest = await io.json(at('chars/' + name + '/manifest.json'));
        if (isActive && !isActive(manifest)) return;
        chars[i] = { manifest, atlas: await image('chars/' + name + '/' + manifest.atlas) };
      } catch (e) {
        if (typeof console !== 'undefined') console.warn('lounge: character left out:', name, e && e.message);
      }
    }));
    return { scene, layers, floorLight, planes, weather, chars: chars.filter(Boolean) };
  }

  return { loadAssets, browserIO };
});
