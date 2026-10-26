"""SAM(vit_b) 으로 점 지시 분리 + isnet-anime 알파로 가장자리. 손·팔만 남긴다."""
import json, sys, numpy as np, onnxruntime as ort
from PIL import Image
src = 'bgcut/src.png'
im = Image.open(src).convert('RGB'); W, H = im.size
IH, IW = 684, 1024
sc = min(IW / W, IH / H)
canvas = np.zeros((IH, IW, 3), np.float32)
rs = np.asarray(im.resize((round(W * sc), round(H * sc)), Image.BILINEAR)).astype(np.float32)
canvas[:rs.shape[0], :rs.shape[1]] = rs
enc = ort.InferenceSession('models/sam_vit_l_0b3195.encoder.quant.onnx', providers=['CPUExecutionProvider'])
emb = enc.run(None, {enc.get_inputs()[0].name: canvas})[0]
dec = ort.InferenceSession('models/sam_vit_l_0b3195.decoder.quant.onnx', providers=['CPUExecutionProvider'])
ai = np.asarray(Image.open('bgcut/out/sheet_transparent.png'))[..., 3].astype(np.float32) / 255   # 흰 배경만 지운 알파
P = json.load(open('sam_points.json'))
for name, pts in P.items():
    pos, neg = pts['pos'], pts['neg']
    c = np.array(pos + neg + [[0, 0]], np.float32) * sc
    l = np.array([1] * len(pos) + [0] * len(neg) + [-1], np.float32)
    out = dec.run(None, {'image_embeddings': emb, 'point_coords': c[None], 'point_labels': l[None],
                         'mask_input': np.zeros((1, 1, 256, 256), np.float32), 'has_mask_input': np.zeros(1, np.float32),
                         'orig_im_size': np.array([IH, IW], np.float32)})
    masks, iou = out[0][0], out[1][0]
    k = int(np.argmax(iou)); lg = masks[k][:round(H * sc), :round(W * sc)]
    logit = np.asarray(Image.fromarray(lg.astype(np.float32), 'F').resize((W, H), Image.BILINEAR))
    np.save('bgcut/logit_%s.npy' % name, logit)
    np.save('bgcut/mask_%s.npy' % name, logit > 0)
    continue
    a = np.minimum(soft, ai) if pts.get('use_ai', True) else soft
    rgba = np.dstack([np.asarray(im), (a * 255).astype(np.uint8)])
    ys, xs = np.where(a > 0.05); y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    Image.fromarray(rgba[y0:y1 + 1, x0:x1 + 1], 'RGBA').save('bgcut/sam_%s.png' % name)
    print(name, 'iou', [round(float(v), 3) for v in iou], 'pick', k, (int(x0), int(y0)))

from PIL import ImageFilter
def load(n): return np.load('bgcut/mask_%s.npy' % n)
def finish(m, name):
    # 작은 섬 제거 + 1px 부드럽게: 4배 키워 흐림→문턱→줄임
    big = Image.fromarray((m * 255).astype(np.uint8)).resize((W * 4, H * 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
    big = big.point(lambda v: 255 if v >= 128 else 0).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))
    soft = np.asarray(big.resize((W, H), Image.BOX)).astype(np.float32) / 255
    a = np.minimum(soft, ai)
    rgba = np.dstack([np.asarray(im), (a * 255).astype(np.uint8)])
    ys, xs = np.where(a > 0.05); y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    Image.fromarray(rgba[y0:y1 + 1, x0:x1 + 1], 'RGBA').save('bgcut/sam_%s.png' % name)
    print('saved', name, (int(x0), int(y0)))
finish(load('L') | load('Lcard'), 'L')
finish(load('R'), 'R')
