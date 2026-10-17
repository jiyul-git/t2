# 라운지 배경 레이어 (작업 원본)

Gemini로 만든 배경을 정리한 것. 모두 2490×1728이고 서로 겹치도록 정렬돼 있다(선 일치율 98% 이상). 아직 장면 엔진에 연결되지 않은 작업 원본이다.

| 파일 | 내용 |
|---|---|
| `interior_night.webp`, `interior_day.webp`, `interior_golden.webp` | 실내. 유리창 부분은 투명 |
| `outside_night.webp`, `outside_day.webp`, `outside_golden.webp` | 창밖. 유리창 부분만 보이고 나머지는 투명 |

처리한 내용: 작은 원본은 Real-ESRGAN(anime 6B)으로 4배 키운 뒤 2490×1728로 맞춤, 실내 밤 그림 기준으로 위치 정렬(어긋남 0.5px 이하), 오른쪽 아래 Gemini 워터마크 두 개 제거, 실내 밤·낮 그림의 흰 창 영역으로 유리창 마스크 생성.

남은 일: 소파 앞면(앉은 캐릭터를 가리는 부분)과 앞 소품 분리, 좌석 좌표, 장면 크기(`scene.json`) 변경, 비행기 레이어.
