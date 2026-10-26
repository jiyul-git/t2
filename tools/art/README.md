# 그림 정리 도구

## 손·팔 같은 부분만 오려내기 (AI)
- `sam_cut.py`: SAM(vit_l, 점 지시 분리)으로 원하는 부분만 고르고, 흰 배경을 지운 알파와 합쳐 투명 PNG 로 저장한다.
  - 점 파일 `sam_points.json`: 이름마다 `pos`(남길 곳)와 `neg`(버릴 곳) 좌표를 적는다. 예시는 `sam_points.example.json`.
  - 모델은 rembg 릴리스에서 받는다(GitHub release, 약 340MB):
    `sam_vit_l_0b3195.encoder.quant.onnx`, `sam_vit_l_0b3195.decoder.quant.onnx` → `models/`
  - 배경이 흰색이 아닌 그림은 `isnet-anime.onnx`(일러스트용 배경 제거)를 쓴다.
- 필요: `pip install onnxruntime pillow numpy`
- `make_paw.py`: 블렌더(bpy)로 3D 호랑이 앞발 손 모델을 만든다.
