# 라운지 그림 자료

사용자가 Gemini로 만들어 보낸 그림과, 그것을 정리한 결과물. 장면 엔진(`ui/web/lounge/`)에는 아직 연결되지 않았다.

## `sources/` 받은 원본 (WebP로 보관)

| 파일 | 내용 | 상태 |
|---|---|---|
| `chars_sitting_group_gemini.webp` | 4마리 앉은 모습 (호랑이 폰, 토끼 통화, 거북이 티켓, 펭귄 커피), 흰 배경 | 캐릭터 기준 그림 |
| `chars_walking_group_gemini.webp` | 4마리 걷는 모습 (캐리어 포함), 흰 배경 | 캐릭터 기준 그림 |
| `bg_season_grid_gemini.webp` | 계절 4종 × 구도 3종 배경 그리드 | 참고용 (구도가 서로 달라 레이어로는 안 씀) |
| `bg_winter_night_upscaled.webp` | 위 그리드의 겨울 밤 칸을 AI로 4배 키운 것 | 기준 구도로 정한 그림 |
| `bg_interior_night_window_white.webp` | 실내 밤, 창은 흰색 | **사용** (실내 밤 레이어) |
| `bg_interior_day_window_white.webp` | 실내 낮, 램프 꺼짐, 창은 흰색 | **사용** (실내 낮 레이어) |
| `bg_full_golden.webp` | 노을, 창밖 포함 | **사용** (실내·창밖 노을) |
| `bg_full_night.webp` | 밤, 창밖 포함 | **사용** (창밖 밤) |
| `bg_full_day.webp` | 낮, 창밖 포함 (오른쪽 끝에 비행기 일부) | **사용** (창밖 낮) |
| `bg_time_grid_16x9_reference.webp` | 새벽/낮/노을/밤 16:9 그리드 | 참고용 (구도가 달라 겹치지 않음) |
| `plane_facing_right.webp`, `plane_facing_left.webp` | T2 비행기 옆모습 두 방향, 흰 배경 | 비행기 레이어 원본 |

## `lounge_bg/` 정리된 배경 레이어

2490×1728, 서로 정렬됨(선 일치율 98% 이상). 자세한 내용은 `lounge_bg/README.md`.

## `cutouts/` 누끼 딴 것 (투명 PNG)

| 파일 | 비고 |
|---|---|
| `plane_right.png`, `plane_left.png` | 바퀴 아래 옅은 그림자 자국이 조금 남음. 장면에 넣을 때 정리 |
| `sit_<캐릭터>.png` | 단체 그림을 세로로 잘라 나눔. 서로 맞닿은 부분(호랑이 꼬리, 토끼 캐리어)은 잘릴 수 있음 |
| `walk_<캐릭터>.png` | 같은 방식. 캐리어가 옆 캐릭터 쪽으로 넘어간 부분이 섞일 수 있음 |

단체 그림에서 자른 캐릭터는 확인·시험용이다. 실제 장면에는 캐릭터별로 따로 받은 그림(`docs/LOUNGE_ART_PROMPTS.md`)을 쓴다.

## `tools/`

- `cutout_white.py` — 흰 배경 그림의 배경과 바닥 그림자를 투명하게 하고 물체별로 저장한다. `--split N`은 맞닿은 여러 캐릭터를 빈 세로줄 기준으로 나눈다.

배경 정렬·워터마크 제거·AI 업스케일 과정은 `lounge_bg/README.md`에 적었다.
