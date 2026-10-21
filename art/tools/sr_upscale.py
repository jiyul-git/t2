#!/usr/bin/env python3
"""4x super-resolution of the low-resolution Gemini sheets (Real-ESRGAN anime 6B, run on the CPU).

Several sheets are only 1024 x 765 px (about 170 px per cell: the doze sheets, the turnaround sheets,
the turtle walk sheet, the climb sheet of the rabbit/turtle/penguin). The atlas draws them at 1.1-1.3x,
so the lines were soft. The builders call `upscale(path)` first, cut the cells out of the 4x picture and
only then shrink to the atlas scale (LANCZOS), which gives crisp lines instead of a stretched picture.

- The network is a standalone re-implementation of basicsr's RRDBNet (no basicsr / realesrgan / torchvision
  needed), loaded with the official weights `RealESRGAN_x4plus_anime_6B.pth`. The weights are NOT in the
  repository: they are downloaded once (17.9 MB) into a cache folder outside the repo,
  `$T2_SR_CACHE` or `~/.cache/t2_sr`, and checked against their SHA-256.
- Deterministic: CPU only, fixed thread count, fixed tiling (tile 96, pad 12), no randomness; the same
  sheet gives the same bytes. The 4x result of a sheet is cached next to the weights, keyed by the
  SHA-256 of the sheet file, so rebuilding the characters does not run the network again.
- If the weights cannot be had (no network and no cache) or torch is missing, `upscale` returns None and
  prints one clear line; the builders then fall back to the old path (plain LANCZOS of the 1x cells).

    python3 art/tools/sr_upscale.py art/sources/all_doze_sheet_gemini.webp out.png    # one sheet, 4x
"""
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

URL = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth'
WEIGHTS_SHA256 = 'f872d837d3c90ed2e05227bed711af5671a6fd1c9f7d7e91c911a61f155e99da'
NAME = 'RealESRGAN_x4plus_anime_6B.pth'
TILE, PAD, SCALE = 96, 12, 4


def cache_dir():
    d = Path(os.environ.get('T2_SR_CACHE') or (Path.home() / '.cache' / 't2_sr'))
    d.mkdir(parents=True, exist_ok=True)
    return d


def weights_path():
    """The weights file (downloaded on first use), or None when it cannot be had."""
    p = cache_dir() / NAME
    if not p.is_file():
        try:
            tmp = p.with_suffix('.part')
            with urllib.request.urlopen(URL, timeout=120) as r, open(tmp, 'wb') as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            tmp.rename(p)
        except Exception as e:      # noqa: BLE001 - any network problem means "no SR"
            print('sr_upscale: cannot download %s (%s); falling back to plain resampling' % (NAME, e), file=sys.stderr)
            return None
    if WEIGHTS_SHA256:
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        if h != WEIGHTS_SHA256:
            print('sr_upscale: %s has the wrong SHA-256 (%s); falling back to plain resampling' % (p, h), file=sys.stderr)
            return None
    return p


_NET = None


def _build_net():
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class RDB(nn.Module):
        def __init__(self, nf=64, gc=32):
            super().__init__()
            self.conv1 = nn.Conv2d(nf, gc, 3, 1, 1)
            self.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1)
            self.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1)
            self.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1)
            self.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1)

        def forward(self, x):
            lr = lambda t: F.leaky_relu(t, 0.2, inplace=True)
            x1 = lr(self.conv1(x))
            x2 = lr(self.conv2(torch.cat((x, x1), 1)))
            x3 = lr(self.conv3(torch.cat((x, x1, x2), 1)))
            x4 = lr(self.conv4(torch.cat((x, x1, x2, x3), 1)))
            x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
            return x5 * 0.2 + x

    class RRDB(nn.Module):
        def __init__(self, nf=64, gc=32):
            super().__init__()
            self.rdb1, self.rdb2, self.rdb3 = RDB(nf, gc), RDB(nf, gc), RDB(nf, gc)

        def forward(self, x):
            return self.rdb3(self.rdb2(self.rdb1(x))) * 0.2 + x

    class RRDBNet(nn.Module):
        def __init__(self, nf=64, nb=6, gc=32):
            super().__init__()
            self.conv_first = nn.Conv2d(3, nf, 3, 1, 1)
            self.body = nn.Sequential(*[RRDB(nf, gc) for _ in range(nb)])
            self.conv_body = nn.Conv2d(nf, nf, 3, 1, 1)
            self.conv_up1 = nn.Conv2d(nf, nf, 3, 1, 1)
            self.conv_up2 = nn.Conv2d(nf, nf, 3, 1, 1)
            self.conv_hr = nn.Conv2d(nf, nf, 3, 1, 1)
            self.conv_last = nn.Conv2d(nf, 3, 3, 1, 1)

        def forward(self, x):
            lr = lambda t: F.leaky_relu(t, 0.2, inplace=True)
            feat = self.conv_first(x)
            feat = feat + self.conv_body(self.body(feat))
            feat = lr(self.conv_up1(F.interpolate(feat, scale_factor=2, mode='nearest')))
            feat = lr(self.conv_up2(F.interpolate(feat, scale_factor=2, mode='nearest')))
            return self.conv_last(lr(self.conv_hr(feat)))

    return RRDBNet()


def _net():
    global _NET
    if _NET is None:
        import torch
        w = weights_path()
        if w is None:
            return None
        torch.set_num_threads(4)
        torch.use_deterministic_algorithms(True)
        net = _build_net()
        sd = torch.load(w, map_location='cpu', weights_only=True)
        net.load_state_dict(sd.get('params_ema', sd.get('params', sd)), strict=True)
        _NET = net.eval()
    return _NET


def sr_rgb(rgb):
    """4x of a uint8 RGB array (H, W, 3) by tiles with overlap; returns uint8 (4H, 4W, 3) or None."""
    import torch
    net = _net()
    if net is None:
        return None
    H, W = rgb.shape[:2]
    x = torch.from_numpy(rgb.astype(np.float32) / 255.).permute(2, 0, 1)[None]
    out = torch.zeros(1, 3, H * SCALE, W * SCALE)
    with torch.no_grad():
        for y0 in range(0, H, TILE):
            for x0 in range(0, W, TILE):
                ya, yb = max(0, y0 - PAD), min(H, y0 + TILE + PAD)
                xa, xb = max(0, x0 - PAD), min(W, x0 + TILE + PAD)
                t = net(x[:, :, ya:yb, xa:xb])
                ys, xs = (y0 - ya) * SCALE, (x0 - xa) * SCALE
                h, w = min(TILE, H - y0) * SCALE, min(TILE, W - x0) * SCALE
                out[:, :, y0 * SCALE:y0 * SCALE + h, x0 * SCALE:x0 * SCALE + w] = t[:, :, ys:ys + h, xs:xs + w]
    return (out[0].permute(1, 2, 0).clamp(0, 1).numpy() * 255).round().astype(np.uint8)


def upscale(path):
    """The 4x RGB image (PIL) of a sheet file, from the cache when it was done before; None when no SR
    is available (the caller falls back to the 1x sheet)."""
    path = Path(path)
    key = hashlib.sha256(path.read_bytes()).hexdigest()[:20]
    cached = cache_dir() / ('sr4_%s_%s.png' % (path.stem, key))
    if cached.is_file():
        return Image.open(cached).convert('RGB')
    try:
        arr = sr_rgb(np.asarray(Image.open(path).convert('RGB')))
    except ImportError as e:
        print('sr_upscale: %s; falling back to plain resampling' % e, file=sys.stderr)
        return None
    if arr is None:
        return None
    im = Image.fromarray(arr)
    im.save(cached, compress_level=1)
    return im


if __name__ == '__main__':
    r = upscale(sys.argv[1])
    if r is None:
        sys.exit('no super-resolution available')
    r.save(sys.argv[2])
    print('wrote', sys.argv[2], r.size)
