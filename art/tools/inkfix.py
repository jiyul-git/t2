"""Finishing pass for edited legs: one clean silhouette and one even outline, like the drawing.

reink(layer, allow, protect): layer is a premultiplied RGBA float image holding only the legs.
- the silhouette is smoothed (no stair steps, no pinholes, no slivers);
- pixels the smoothing adds are painted from their neighbours;
- the outer ring is redrawn in the line colour, about as thick as the drawing's lines, except
  where `protect` is set (e.g. along the hoodie hem, which covers that edge anyway);
- the outer edge is anti-aliased.
"""
import numpy as np, cv2

LINE = np.array([34, 24, 20], np.float32)
WIDTH = 2.6          # px, the drawing's line width at this size


def reink(layer, allow=None, protect=None):
    a = layer[..., 3] > 40
    if not a.any():
        return layer
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    m = cv2.morphologyEx(a.astype(np.uint8), cv2.MORPH_CLOSE, k5)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    soft = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.3)
    if allow is not None:
        soft = soft * allow
    inside = soft > 0.5
    # colour for pixels the smoothing added: painted in from the neighbours
    rgb = np.zeros(layer.shape[:2] + (3,), np.float32)
    al = layer[..., 3:] / 255.
    rgb[a] = (layer[..., :3][a] / np.maximum(al[a], 1e-3))
    hole = (inside & ~a).astype(np.uint8)
    if hole.any():
        rgb = cv2.inpaint(rgb.clip(0, 255).astype(np.uint8), hole, 3, cv2.INPAINT_TELEA).astype(np.float32)
    # line along the outside edge: distance from the outside, in px
    dist = cv2.distanceTransform(inside.astype(np.uint8), cv2.DIST_L2, 3)
    ring = np.clip((WIDTH + 0.5 - dist), 0, 1)                 # 1 on the edge, fading inward
    if protect is not None:
        ring = ring * (~protect)
    rgb = rgb * (1 - ring[..., None]) + LINE * ring[..., None]
    alpha = np.clip((soft - 0.5) * 3.0 + 0.5, 0, 1)               # anti-aliased outer edge
    alpha[inside & (dist > 1.5)] = 1
    out = np.zeros_like(layer)
    out[..., 3] = alpha * 255
    out[..., :3] = rgb * alpha[..., None]
    return out


def defringe(rgba, width=2):
    """Light, colourless pixels on the outer edge are leftovers of the white sheet: make them line
    colour (straight RGBA in, straight RGBA out)."""
    a = rgba[..., 3] > 0
    solid = rgba[..., 3] > 200
    near_out = ~cv2.erode(a.astype(np.uint8), np.ones((2 * width + 1, 2 * width + 1), np.uint8)).astype(bool) & a
    rgb = rgba[..., :3]
    mn, mx = rgb.min(-1), rgb.max(-1)
    light = (mn > 150) & (mx - mn < 40)
    fix = near_out & light
    out = rgba.copy()
    out[..., :3][fix] = LINE
    out[..., 3][fix & ~solid] = np.minimum(out[..., 3][fix & ~solid], 160)
    return out
