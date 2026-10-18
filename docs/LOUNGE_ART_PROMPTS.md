# 라운지 그림 주문서 (Gemini용)

## 지금 상황

- 로비 장면 엔진은 완성됐고 지금은 임시 도형 그림으로 돌아간다.
- Gemini로 만든 캐릭터 4마리(앉은 모습, 걷는 모습)가 승인된 그림과 잘 어울리는 것을 확인했다. 흰 배경은 깔끔하게 오려진다.
- 이제 필요한 것은 **움직임을 몇 장의 정지 그림으로 쪼갠 것**이다. 영상이 아니라, 정지 그림 몇 장을 빠르게 넘겨 움직임을 만든다(옛날 애니메이션 방식). 장면에 맞게 자르고 크기를 맞추는 일은 내가 한다.
- 이미지 AI는 같은 그림을 복사하지 못하므로, **기준 그림 한 장을 먼저 만들고 그 그림을 첨부해 "이것만 바꿔"라고 고치게 하는 방식**으로 진행한다.

## 공통 지시문 (모든 요청 끝에 붙인다)

```
[공통 규칙]
- 첨부한 그림의 캐릭터와 똑같은 캐릭터로 그려 줘(얼굴, 옷, 색, 선 굵기, 그림체 그대로).
- 캐릭터 한 마리만, 머리부터 발끝까지 잘리지 않게.
- 배경은 완전히 흰색 단색. 바닥선, 그림자, 글자, 의자, 가방 같은 다른 물건은 그리지 마.
- 세로 3:4 비율. 캐릭터 크기와 카메라 높이·거리는 첨부한 그림과 똑같이.
```

- 의자를 그리지 않는 이유: 의자는 배경에 있고, 캐릭터만 그 위에 얹는다. 앉은 자세는 "보이지 않는 의자에 앉은 것처럼" 그리면 된다.
- 가방(캐리어)은 1차에서는 뺀다. 들고 다니다 앉을 때 어디에 둘지 그림이 더 필요해서다. 손에 드는 물건(폰, 컵, 티켓)은 해당 자세에서만 넣는다.
- 그림자는 엔진이 시간대에 맞춰 직접 그리므로 그림에는 넣지 않는다.

## 진행 순서와 장수

한 번에 한 마리, 한 장씩 요청한다. **토끼 1단계(8장)를 먼저 만들어 보내 주면** 내가 로비에 넣어 미리보기를 만들고, 괜찮으면 나머지를 이어 간다.

| 단계 | 내용 | 캐릭터당 | 4마리 |
|---|---|---|---|
| 1단계 (필수) | 서기, 걷기, 돌기, 앉기, 앉아 가만히 | 7~8장 | 28~32장 |
| 2단계 | 캐릭터별 대표 활동 | 3장 | 12장 |
| 3단계 (선택) | 졸기, 대화, 왼쪽 걷기, 선글라스, 옷매무새 | 최대 12장 | 최대 48장 |

1단계만 있어도 캐릭터가 걸어 들어와 앉고, 눈을 깜빡이다가 나간다. 왼쪽으로 걷기는 처음엔 오른쪽 걷기를 뒤집어 쓴다(이때 옷의 T2 글자가 거꾸로 보인다. 신경 쓰이면 3단계에서 따로 만든다).

---

## 1단계 (캐릭터당 8장)

### ① 기준 그림: 정면 서기 — `토끼_서기`

받아 둔 단체 그림(걷는 모습)을 첨부하고:

```
이 그림에서 토끼만 그려 줘. 정면을 보고 똑바로 서 있는 모습, 두 팔은 자연스럽게 내리고, 손에는 아무것도 들지 않은 상태.
[공통 규칙]
```

이 그림이 나머지 모든 그림의 기준이 된다. 마음에 들 때까지 이것만 다시 뽑는다. 이후 요청은 모두 **이 기준 그림을 첨부**한다.

### ② 걷기 3장 — `토끼_걷기1`, `토끼_걷기2`, `토끼_걷기3`

세 장을 1→2→3→2 순서로 반복하면 걷는 것처럼 보인다. 모두 **오른쪽을 향한 옆모습**이다.

```
이 토끼가 오른쪽을 향해 걷는 옆모습. 카메라 쪽 다리가 앞으로 크게 나가 뒤꿈치가 바닥에 닿았고, 반대쪽 다리는 뒤에서 발끝으로 땅을 밀고 있는 순간. 팔은 다리와 반대로 앞뒤로 흔들어.
[공통 규칙]
```

```
이 토끼가 오른쪽을 향해 걷는 옆모습. 두 다리가 몸 아래에서 거의 모여 있고, 카메라 반대쪽 다리가 살짝 들려 앞으로 지나가는 순간. 몸은 다른 걷는 자세보다 조금 더 높이 떠 있어. 팔은 몸 옆에 거의 붙어 있어.
[공통 규칙]
```

```
이 토끼가 오른쪽을 향해 걷는 옆모습. 카메라 반대쪽 다리가 앞으로 크게 나가 뒤꿈치가 바닥에 닿았고, 카메라 쪽 다리는 뒤에서 발끝으로 땅을 밀고 있는 순간. 팔은 다리와 반대로 앞뒤로 흔들어.
[공통 규칙]
```

### ③ 돌아서기 1장 — `토끼_돌기`

옆모습(걷기)과 정면(서기) 사이를 이어 준다.

```
이 토끼가 서 있는 모습인데, 몸과 얼굴이 오른쪽 옆에서 정면 쪽으로 반쯤 돌아선 3/4 각도. 두 발은 땅에 붙어 있어.
[공통 규칙]
```

### ④ 앉는 중 1장 — `토끼_앉는중`

```
이 토끼가 정면을 보며 의자에 앉으려고 무릎을 굽히고 엉덩이를 뒤로 빼는 중간 자세. 의자는 그리지 마.
[공통 규칙]
```

### ⑤ 앉아 가만히 2장 — `토끼_앉기`, `토끼_앉기_눈감음`

```
이 토끼가 정면을 보고 보이지 않는 의자에 편하게 앉아 있는 모습. 두 손은 무릎 위에, 다리는 앞으로 살짝 내려와 있어. 의자는 그리지 마.
[공통 규칙]
```

두 번째는 **방금 나온 앉은 그림을 첨부**하고:

```
이 그림에서 눈만 감은 모습으로 바꿔 줘(눈 깜빡임용). 나머지는 하나도 바꾸지 마.
[공통 규칙]
```

---

## 2단계: 대표 활동 (캐릭터당 3장)

받아 둔 앉은 단체 그림의 활동을 그대로 쓴다. 모두 **앉은 그림(`앉기`)을 첨부**해서 요청한다.

| 캐릭터 | 1장: 시작하는 중 | 2장: 하는 중 A | 3장: 하는 중 B |
|---|---|---|---|
| 호랑이 | 주머니에서 폰을 꺼내 드는 중 | 두 손으로 폰을 보는 중 | 폰을 보며 살짝 웃음 |
| 토끼 | 폰을 귀로 가져가는 중 | 통화하며 입을 벌리고 웃음 | 통화하며 입을 다물고 듣는 중 |
| 거북이 | 티켓을 꺼내 드는 중 | 티켓을 들여다보는 중 | 티켓을 보며 고개를 갸웃 |
| 펭귄 | 커피 컵을 들어 올리는 중 | 컵을 입에 대고 마시는 중 | 컵을 내리고 만족한 표정 |

요청 예시(호랑이 1장):

```
이 호랑이가 앉은 자세 그대로, 주머니에서 스마트폰을 꺼내 가슴 앞으로 드는 중간 동작으로 바꿔 줘. 앉은 자세와 다리 위치는 그대로.
[공통 규칙]
```

나머지도 같은 틀에 표의 문장만 바꾸면 된다.

---

## 3단계: 선택 (원하는 것만)

모두 앉은 그림 또는 기준 그림을 첨부한다.

| 이름 | 장수 | 내용 |
|---|---|---|
| `졸기1`, `졸기2` | 2 | 앉은 채 눈 감고 고개를 살짝 숙임 / 고개를 꾸벅 깊게 숙임 |
| `대화_말하기`, `대화_듣기` | 2 | 앉은 채 몸과 얼굴을 오른쪽으로 돌려 옆 사람에게 입 벌리고 말함 / 입 다물고 끄덕이며 들음 |
| `대화왼쪽_말하기`, `대화왼쪽_듣기` | 2 | 위와 같은데 왼쪽을 봄 (안 만들면 위 그림을 뒤집어 씀) |
| `왼쪽걷기1~3` | 3 | 걷기 3장과 같은데 왼쪽을 향함 (안 만들면 오른쪽 걷기를 뒤집어 씀) |
| `선글라스1~3` | 3 | 선글라스를 꺼냄 / 쓰는 중 / 쓴 채 앉아 있음 |
| `옷매무새1~2` | 2 | 두 손으로 옷깃을 잡음 / 옷을 아래로 당겨 정리함 |

---

## 배경 (캐릭터와 별도) — 처음 승인한 구도 그대로

구도는 **처음 승인한 일러스트(밤)** 를 그대로 쓴다. 새로 그리게 하지 않고, 그 그림에서 캐릭터만 지우는 **편집**으로 만든다.
원본 파일(더 큰 해상도)이 있으면 그걸, 없으면 저장소의 `ui/web/assets/t2-airport/lobby_hero_night.webp`(648px)를 2배로 키운 PNG를 첨부한다.

### 1. 빈 라운지 (밤)

```
첨부한 그림을 편집해 줘. 새로 그리지 말고, 이 그림을 바탕으로 아래만 바꿔 줘.

[지울 것]
1. 앞쪽 소파에 앉아 있는 캐릭터 네 마리(왼쪽부터 호랑이, 토끼, 거북이, 펭귄)를 완전히 지워 줘. 캐릭터가 들고 있거나 옆에 둔 물건(여권, 커피컵, 티켓, 분홍 캐리어)도 같이 지워.
2. 오른쪽 위 구석의 '낮 / 밤' 버튼을 지우고, 그 자리는 뒤에 있던 유리창과 밤하늘로 자연스럽게 이어지게 채워 줘.
3. 왼쪽 위 출발 안내판 화면 안의 도시 이름, 시간, BOARDING / ON TIME 글자를 지우고 빈 남색 화면으로 만들어 줘. 맨 위의 비행기 아이콘, DEPARTURES 제목, 테두리는 남겨.

[채울 것]
- 캐릭터가 있던 자리는 비어 있는 소파와 쿠션으로 채워 줘. 원래 소파와 같은 색, 같은 모양으로, 앞쪽에 소파 4개가 나란히 보이게.
- 소파 사이 작은 테이블과 과자, 스탠드 조명, 왼쪽의 검은 캐리어, 화분은 원래 자리에 그대로 둬. 캐릭터에 가려졌던 부분은 주변과 이어지게 그려.

[그대로 둘 것]
- 전체 구도, 카메라 각도, 가로세로 비율.
- 그림체(부드러운 일러스트 채색), 색감, 따뜻한 조명과 밤 분위기.
- 유리창, 창밖의 관제탑, T2 비행기, 활주로 불빛, 도시 야경.
- 새로운 물건, 사람, 캐릭터, 글자는 추가하지 마.

해상도는 최대한 높고 선명하게 해 줘.
```

결과가 아쉬우면 처음부터 다시 하지 말고, **나온 그림을 첨부해서 고칠 점만** 말한다.

| 문제 | 이어서 보낼 말 |
|---|---|
| 캐릭터 흔적(귀, 모자, 손)이 남음 | 아직 캐릭터의 ○○이 남아 있어. 그 부분만 소파로 채워 줘. 나머지는 그대로. |
| 구도가 바뀜 | 처음 그림과 구도가 달라졌어. 원본과 똑같은 구도에서 캐릭터만 지운 버전으로 다시 해 줘. (원본을 다시 첨부) |
| 안내판 글자가 남음 | 안내판 화면 안의 글자만 모두 지워서 빈 화면으로 만들어 줘. 나머지는 그대로. |
| 흐리거나 작음 | 그림은 그대로 두고 더 선명하고 높은 해상도로 다시 만들어 줘. |

**낮 버전을 만들기 전에 이 빈 밤 배경을 먼저 보낸다.** 보내기 전에 볼 것:

- 캐릭터와 그 물건이 하나도 남지 않았는지
- 소파 4개가 앞쪽에 비어 있는지
- 안내판 화면이 비어 있는지(조금 남아도 내가 지울 수 있다)
- 오른쪽 위 낮/밤 버튼이 없어졌는지
- 원본과 구도가 같은지(창, 안내판, 비행기 위치)

### 2. 빈 라운지 (낮) — 확인이 끝난 뒤

방금 만든 빈 밤 배경을 첨부한다. 낮 분위기 참고용으로 원래 낮 일러스트를 두 번째로 첨부해도 된다.

```
첫 번째 그림(빈 라운지, 밤)을 편집해 줘. 구도, 소파와 물건의 위치와 모양, 선은 하나도 바꾸지 말고 시간만 맑은 낮으로 바꿔 줘.
- 창밖은 파란 하늘과 흰 구름, 햇빛이 비치는 활주로와 비행기.
- 실내 스탠드 조명과 전구는 꺼진 상태이고, 창으로 들어온 자연광으로 실내가 밝아.
- 출발 안내판 화면은 그대로 빈 화면.
- 그림체와 부드러운 채색은 그대로.
두 번째 그림은 낮 분위기 참고용이야. 구도는 따라 하지 말고 색감과 빛만 참고해.
```

낮 그림이 밤 그림과 겹치지 않으면(물건이 움직이면) 내 검사 도구가 알려 준다. 그때는 다시 뽑는다. 창문 구멍 내기, 소파 앞면 분리 같은 레이어 작업은 내가 한다.

**이 구도에서 캐릭터 그림이 달라지는 점:** 캐릭터가 크게 보이고 하반신은 화면 아래와 소파에 가려진다. 그래서 걷기는 다리가 거의 안 보이므로 3장 대신 **2장**(몸이 올라간 순간, 내려간 순간)이면 충분하다. 그림은 지금처럼 전신으로 받아 두면 내가 잘라 쓴다.

---

### 3. 아래로 늘리기 (소파·바닥을 끊김 없이 연장)

로비에서 그림 아래 토너먼트 목록이 시작되는 곳이 소파 한가운데서 잘려 있다. 그림을 아래로 늘려 소파 아랫부분과 바닥이 이어지게 한다.
보낼 그림: `art/requests/extend_bottom_night.jpg` (밤부터. 결과가 좋으면 `_day`, `_golden`도 같은 문장으로).

```
Extend this illustration DOWNWARD only (outpainting). Make the canvas about 40% taller by adding
new area at the bottom. Do NOT change, redraw, move or recolor anything in the existing image -
every existing pixel must stay exactly where it is.

In the new bottom area, continue what is already there: the lower part of the same sofas (seat
fronts, sofa bases, short legs), then the lounge floor in front of them - the same carpet/floor
colour and lighting as the room, with soft shadows under the sofas. Keep it calm and fairly plain
toward the very bottom (UI cards will sit on top of it), getting slightly darker at the bottom edge.
No new furniture, no people, no animals, no text, no logos, no watermark.

Same art style, same line weight, same lighting and colour palette as the original.
Output the full extended image (original on top, new area below), same width.
```

받으면 원본 위쪽과 픽셀 단위로 맞는지 확인한 뒤(어긋나면 위쪽은 원본을 쓰고 아래 새 부분만 이어 붙인다) 라운지 배경 아래로 붙이고, 토너먼트 목록이 그 위에 올라가게 한다.

### 4. 호랑이 다리 핵심 자세 4장 (걷기 다시 만들기)

지금 시트에는 한쪽 발만 앞으로 나오는 자세뿐이라, 이어 붙이면 같은 발이 앞뒤로 왔다 갔다 한다. 윗몸은 우리가 한 장으로 고정해 쓰므로, **다리만** 제대로 된 4자세가 필요하다.
보낼 그림: `art/requests/tiger_legs_reference.png` (기준 호랑이, 왼쪽으로 걷는 중).

```
Use the attached tiger as the exact character reference (same head, hoodie, phone, tail,
suitcase, colours, line weight). Draw ONE ROW of 4 separate cells on a plain white background,
same size and same position in every cell, a clear white gap between cells, no shadows.

The tiger walks to the LEFT in every cell. Keep the upper body (head, hoodie, arms, phone,
suitcase) IDENTICAL in all 4 cells - copy it from the reference. Change ONLY the legs:

1. CONTACT A: the NEAR leg (closer to the viewer) is stretched forward to the left, heel just
   touching the floor, toes pointing left. The FAR leg is stretched behind to the right, toes on
   the floor, heel lifted.
2. PASSING A: the NEAR leg is straight under the body, foot flat on the floor. The FAR leg is
   bent and lifted, swinging forward past it.
3. CONTACT B: the opposite of 1 - the FAR leg is now stretched forward to the left (heel down,
   toes pointing left) and the NEAR leg is stretched behind (toes down, heel lifted).
4. PASSING B: the opposite of 2 - the FAR leg is straight under the body, foot flat; the NEAR
   leg is bent and lifted, swinging forward.

Toes always point LEFT (the walking direction). Never show the bottom of a foot facing the
viewer. The near leg always overlaps the far leg. No text, no watermark.
```

받으면 4칸을 잘라 다리만 바꿔 넣고(`lockbody.py`), 사이 프레임이 필요하면 1→2, 2→3 사이에 기존 시트의 비슷한 자세를 끼운다.

## 추가로 받으면 좋은 그림 (2026-10-17)

지금 앉기·일어서기는 이미 있는 정지 그림으로 만든 것이다(`art/README.md` "앉기 캐릭터"). 서 있는 그림이 폴짝 뛰어 오르고, 꼭대기에서 앉은 그림으로 한 프레임에 바뀐 뒤 방석에 내려앉는다(2026-10-18부터 크로스페이드 없음). 좌석에는 방향이 있어(왼쪽 소파 정면, 오른쪽 소파 왼쪽 앞을 향한 3/4) 방향마다 맞는 앉은 그림이 필요하다. **꼭대기에서 그림이 바뀌는 순간**과 **방향에 맞는 그림이 없는 자리**(거북이 정면, 호랑이 정면 폰, 토끼 정면 통화)가 가장 약한 부분이다. 아래 그림이 오면 그 2장을 진짜 동작 그림으로 바꿀 수 있다. 호랑이 오르기 시트(`tiger_climb_sit_sheet_a/b`)가 잘 나온 방식 그대로다: **4×4 한 장에 16칸, 번호 순서대로 한 동작, 흰 배경, 칸 사이 흰 여백, 같은 크기**, 그리고 b처럼 **가로선(소파 앞면 윗선)** 을 그려 두면 칸마다 높이를 맞추기 쉽다.

보낼 때 첨부: 그 동물의 기준 그림 2장(걷는 단체 그림 `chars_walking_group_gemini.webp`과 앉은 단체 그림 `chars_sitting_group_gemini.webp`), 그리고 잘 된 예로 `tiger_climb_sit_sheet_b_ledge_gemini.webp`.

### 1. 소파에 올라앉기 16칸 — 토끼, 거북이, 펭귄 (각 1장)

`<동물>`에 rabbit / turtle / penguin, `<옷차림>`에 각자 차림을 넣는다(토끼: pink coat, pink scarf, bow on the ear, boots / 거북이: black beanie, navy jacket with gold pattern, brown shell backpack / 펭귄: brown aviator cap with goggles, mustard scarf).

```
Use the attached <animal> as the exact character reference (same face, <outfit>, colours,
line weight, chibi proportions). The third attachment is a finished example of the SAME kind of
sheet for the tiger: copy its layout exactly.

Draw a 4x4 sheet (16 separate cells, read left to right, top to bottom) on a plain white
background, a clear white gap between cells, every cell the same size and the character the same
size in every cell. No chair, no sofa, no shadow, no text, no watermark. In cells 1-8 draw one thin
straight horizontal black line across the cell at the same height in every cell: it is the top
edge of a sofa seat.

The <animal> climbs onto a sofa and sits down, one step per cell:
1-2. back view, standing below the line, both hands reaching up and holding the line.
3-4. back view, pulling up: one knee lifted over the line, the other foot dangling, a small effort mark.
5-6. lying belly-down across the line (on the seat), legs dangling behind, rolling to the side.
7-8. side view (facing right), sitting on the line, legs stretched forward along it.
9-10. turning toward the viewer while sitting, legs forward.
11. sitting, facing the viewer, legs forward, hands on the lap, eyes OPEN, small calm smile.
12. same as 11 with the eyes closed (a blink).
13. same as 11, wiping the brow ("phew").
14. same as 11, looking left. 15. same as 11, looking right. 16. same as 11, waving.
Keep the body the same size in every cell; only the pose changes.
```

받으면: 1~10칸을 `sit_down` 프레임 목록(`build_character.py`의 `sit_frames`)으로 넣고, 거꾸로 돌려 `stand_up`도 만든다. 가로선 높이로 소파 앞면에 맞춘다.

### 2. 소파에서 일어나 내려오기 16칸 (각 1장, 호랑이 포함)

```
Use the attached <animal> as the exact character reference (same face, outfit, colours, line
weight). 4x4 sheet, 16 separate cells, plain white background, white gaps, same size in every
cell, no shadow, no text. A thin horizontal black line in every cell at the same height = the top
edge of a sofa seat.

The <animal> gets up from the sofa and hops down to the floor in front of it, facing the viewer:
1. sitting on the line, facing the viewer, legs forward, hands on the lap.
2. leaning forward, hands pushing on the line on both sides of the body.
3. sliding forward, bottom at the very front of the line, feet reaching down.
4-5. feet touching the floor below the line, knees bent, body still leaning forward.
6-7. standing up straight in front of the line, facing the viewer.
8. a small hop of joy, both feet just off the floor.
9-16. standing facing the viewer, arms relaxed at the sides, hands empty: neutral, blink (eyes
closed), small smile, looking left, looking right, a slight nod, hands together, a small wave.
```

받으면: 1~8칸이 `stand_up`, 9~16칸이 걷기 전 정면 서기(`stand_front`)와 그 표정이 된다. 지금 쓰는 서기 그림은 물건(커피, 폰)을 들거나 눈이 놀란 모양이라, 손이 빈 평범한 정면 서기가 있으면 돌아서기(종이 넘기기)도 자연스러워진다.

### 3. 눈 뜬 평범한 앉은 정면 4칸 — 토끼, 거북이, 펭귄

지금 토끼는 앉은 눈 뜬 그림이 없어 걷기 그림의 눈을 옮겨 붙였고, 거북이는 잠에서 깬 "어?" 그림의 입을 고쳤고, 펭귄은 커피 든 단체 그림뿐이다.

```
Use the attached <animal> as the exact character reference (same face, outfit, colours, line
weight). One row of 4 separate cells, plain white background, white gaps, same size in every cell,
no chair, no shadow, no text. The <animal> sits on the floor facing the viewer, legs stretched
forward, both hands resting on the lap, nothing in the hands:
1. eyes open, calm small smile (the neutral seated pose).
2. exactly the same pose with the eyes closed (a blink) - nothing else changes.
3. exactly the same pose, looking a little to the left.
4. exactly the same pose, smiling with the eyes closed.
Cells 1-4 must be identical except for the eyes and mouth.
```

### 4. 옆을 보고 이야기하는 앉은 자세 (대화) — 4마리

엔진에는 옆자리끼리 대화하는 동작(`chat_*`)이 이미 있다. 그림만 없어 지금은 빠져 있다.

```
Use the attached <animal> as the exact character reference. 4x4 sheet, 16 separate cells, plain
white background, white gaps, same size, no chair, no shadow, no text. The <animal> sits on the
floor, legs forward, its body turned three-quarters to the RIGHT (talking to someone sitting on
its right):
row 1: turning from facing the viewer to facing right (4 steps).
row 2: talking - mouth open/closed alternately, one hand gesturing (4 cells).
row 3: listening - nodding, a small smile, a blink (4 cells).
row 4: laughing together, then turning back to face the viewer (4 cells).
Body size and position the same in every cell; only head, arms and mouth change.
```

왼쪽을 보는 대화는 이것을 좌우로 뒤집어 쓰고, 옷의 글자만 다시 바로 세운다(`mirror_logo.py`).

### 5. 펭귄 걷기 옆모습 4×4

펭귄은 걷는 그림이 단체 그림 한 장뿐이라 장면에 넣지 않았다(뒤뚱걸음을 한 장으로 흉내 내면 한 발을 들고 미끄러지는 것처럼 보인다).

```
Use the attached penguin as the exact character reference (brown aviator cap with goggles,
mustard scarf, coffee cup in one flipper, colours, line weight). 4x4 sheet, 16 separate cells,
plain white background, white gaps, same size in every cell, no shadow, no text.
The penguin waddles to the RIGHT, side view (three-quarter), the coffee cup always in the same
flipper. One waddle step per row, 4 cells per row:
1. body tilted left, left foot planted, right foot lifted forward.
2. body upright, both feet on the floor (passing).
3. body tilted right, right foot planted, left foot lifted forward.
4. body upright, both feet on the floor.
Rows 2-4: the same 4 poses again with tiny differences (scarf end swinging, a blink in one cell).
Keep the head, cap, scarf and cup identical in all cells; only the feet and the body tilt change.
Feet always point RIGHT.
```

### 6. 방향별 앉은 자세 (소파 방향에 맞추기) — 4마리

라운지의 왼쪽 소파는 정면, 오른쪽 소파는 **왼쪽 앞을 향해 3/4로** 놓여 있다. 지금 있는 앉은 그림은 대부분 바닥에 앉아 다리를 앞으로 뻗은 모습이고 방향이 제각각이라, 거북이는 정면 소파에 못 앉고 호랑이는 정면 소파에서 폰을, 토끼는 정면 소파에서 통화를 못 한다. 한 마리에 한 장씩, 같은 몸 크기로:

```
Use the attached <animal> as the exact character reference (same face, outfit, colours, line
weight, chibi proportions). 4x4 sheet, 16 separate cells, plain white background, white gaps,
the character the same size in every cell, no shadow, no text, no watermark. In EVERY cell draw one
thin straight horizontal black line at the same height: the front edge of a sofa seat. The
<animal> sits ON that edge (its bottom just above the line), legs hanging down in front of it,
feet off the floor.
Row 1: body and face toward the viewer (front view): eyes open calm smile / eyes closed (blink) /
       holding a phone and looking at it / phone at the ear, talking.
Row 2: the same four, but the whole body turned three-quarters to the viewer's LEFT (we see the
       right side of its face and body a little), legs hanging down-left.
Row 3: front view: dozing head tilted, dozing with "zz", yawning, waking up.
Row 4: three-quarters LEFT: dozing head tilted, dozing with "zz", yawning, waking up.
The bottom (where it sits) must touch the line at the same place in every cell of a row.
```

받으면: 1·3행은 정면 좌석(`f`), 2·4행은 3/4 좌석(`l`)의 자세로 넣는다. 가로선이 엉덩이 접촉선이라 따로 잴 필요가 없다. 다리가 방석 앞으로 늘어져 보이게 된다.

## 확인과 보내기

- 한 장씩 볼 때: 기준 그림과 같은 캐릭터인지(얼굴, 옷, 색), 몸 전체가 잘리지 않았는지, 배경이 흰색 단색인지.
- 크기와 발 위치가 조금씩 달라도 괜찮다. 오리고 크기·발 위치를 맞추는 건 내가 한다.
- 다 만든 그림은 **이 채팅에 그대로 올리면 된다.** 올릴 때 위 표의 이름(예: `토끼_걷기2`)을 함께 적어 주면 된다.
- 한도에 걸리면 기다렸다가 이어서 하면 된다. 토끼 1단계 8장만 먼저 보내 줘도 바로 미리보기를 만든다.
