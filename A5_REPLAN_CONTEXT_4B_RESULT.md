# A5 4-B joint replan context 결과

기준: `chatgpt/a5-block-context-4a-20260925`  
production 무수정 paired replay  
fixture: entries=100, hands=16, seeds=[5150,9001,4242], fmts=[standard,deep,turbo]

## 1. 건전성

R1 replication / R2 clean 모두:

```
update_plan   4687
revise_path   2547
board_changed  789
engine errors    0
```

R1은 과거 A6와 같은 한 프로세스 순서, R2는 tournament마다 분석 하네스에서
`_TILT_VIEW_CACHE`만 clear했다. production cache는 수정하지 않았다.

## 2. 결과

R1과 R2 aggregate는 모든 arm에서 동일했다.

| arm | effective | gate true | changed | raw chip target changed | final block | block msg |
|---|---:|---:|---:|---:|---:|---:|
| oop_vs_aggr | 503 | 0 | 0 | 0 | 0 | 0 |
| oop_legacy_abs | 789 | 0 | 0 | 0 | 0 | 0 |
| initiative | 544 | 0 | 0 | 0 | 0 | 0 |
| oop_vs + initiative | 544 | 303 | 6 | 3 | 6 | 6 |
| legacy + initiative | 789 | 293 | 7 | 3 | 7 | 7 |
| position3 | 789 | 326 | 7 | 3 | 7 | 7 |

diff kinds:
- `oop_vs + initiative`: plan+size 3, plan 3
- `legacy + initiative`: plan+size 3, plan 4
- `position3`: plan+size 3, plan 4

실제 raw chip target 차이는 세 사건에서 발생했다:
- 800 -> 700
- 1500 -> 1200
- 1500 -> 1200

## 3. 해석

single-field 0건은 무효과가 아니다. block gate가

```python
_oop_a = oop_vs_aggr if oop_vs_aggr is not None else bool(oop_legacy_abs)
if _oop_a and not initiative and ...:
```

의 AND 구조이므로 A6 defaults
`oop_vs_aggr=None, oop_legacy_abs=None, initiative=True`에서 한 필드만 바꿔서는
구조적으로 gate를 열 수 없다.

joint arms에서는 실제로 plan label 6~7건, intent size 3건, raw chip target 3건이
바뀌었다. 따라서 board_changed replan에서 이 위치/initiative 문맥은 행동적으로
도달 가능한 입력이다.

## 4. revise_plan context 계약

세 필드를 모두 전달한다.

- `initiative`: 없으면 default True가 block gate를 직접 닫는다.
- `oop_vs_aggr`: aggressor가 존재할 때 상대 어그레서 기준 OOP 의미를 보존한다.
- `oop_legacy_abs`: aggressor가 없어 `oop_vs_aggr is None`일 때만 쓰는 fallback을 보존한다.

fixture에서 `legacy+initiative`와 `position3`가 같은 7건을 냈다고 해서
`oop_vs_aggr`를 생략하지 않는다. 생략하면 aggressor가 있는 상황에서도 legacy
absolute 의미로 fallback되어 현재 소비처의 의미 우선순위를 깨뜨릴 수 있다.

따라서 production 수정은 `plan.update_plan -> runner.revise_plan -> plan.make_plan`
경로에서 세 값을 그대로 전달하는 최소 배선 변경으로 한정한다.

새 임계값, 확률, block_p 계수, stat_read, aggressor 없는 pot semantics는 건드리지 않는다.
