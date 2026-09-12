#!/usr/bin/env python3
"""persona.tilted_view 의 캐시가 **다른 사람의 프로필**을 돌려주는지 검출한다.

plan.py 는 읽기만 한다. persona 도 수정하지 않는다 — 래퍼로 감싸서 관찰만 한다.

무엇이 문제인가
---------------
persona.py

    _TILT_VIEW_CACHE = {}
    ...
    pid = prof.get('id')
    key = (pid, round(t, 2)) if pid is not None else None

`prof['id']` 는 **좌석 번호**다 (tourney:199 → F.make_player(self.rng, s, ...)
→ PS.make_player(rng, q, pid=s) → p['id'] = s). 1~8 뿐이다.
그리고 이 캐시는 한 번도 비워지지 않는다.

그래서 서로 다른 토너먼트(또는 같은 토너먼트의 재착석)에서 같은 좌석에 앉은
**다른 사람**이 반올림 tilt 까지 같으면, 먼저 캐시를 채운 사람의 개념 벡터를
그대로 돌려받는다. 판단 층이 남의 머리로 생각하게 된다.

같은 docstring 이 `id(prof)` 를 쓰면 안 되는 이유로
"해제된 객체의 id 가 재사용되면 **다른 사람의 뷰를 돌려준다**" 고 적어두고,
바로 그 실패 양상을 `prof['id']`(좌석 번호)로 다시 만들어냈다.

왜 이걸 찾게 됐나
-----------------
block 복구 A/B 검증에서 접두 동일성 검사가 4,151핸드 중 1건 어긋났다.
그 핸드는 profiles·stacks·블라인드·딜이 A/B 에서 모두 같은데 intent 의
`type` 만 달랐다(TAG_TIGHT_TILTY vs STUDIED_TAG_TIGHT). 패치가 프로세스
이력을 바꿨고, 그 이력이 이 캐시의 선점자를 바꾼 것이다.
즉 **패치가 만든 결함이 아니라, 패치가 드러낸 기존 결함**이다.

사용: python3 tools/tilt_cache_probe.py [핸드수]
"""
import os, sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persona as PS


def main():
    n_per = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    orig = PS.tilted_view
    bad, calls = [], [0]

    def wrapped(prof, tilt):
        out = orig(prof, tilt)
        t = max(0.0, min(1.0, float(tilt or 0.0)))
        if t > 0.02 and prof.get('concepts') and prof.get('id') is not None:
            calls[0] += 1
            if isinstance(out, dict) and out.get('type') != prof.get('type'):
                bad.append(((prof.get('id'), round(t, 2)),
                            prof.get('type'), out.get('type')))
        return out
    PS.tilted_view = wrapped

    import collect as C
    hands = 0
    for k in range(4):
        hands += len(C.run_one(900000 + k, max_hands=n_per))

    print('=' * 78)
    print('persona.tilted_view 캐시 오염 검출')
    print('=' * 78)
    print('   핸드 %d · 캐시가 관여한 tilted_view 호출 %d' % (hands, calls[0]))
    print('   **다른 사람의 프로필을 돌려준 횟수 %d** (%.2f%%)'
          % (len(bad), 100*len(bad)/max(1, calls[0])))
    print()
    for k, want, got in bad[:10]:
        print('   키(좌석, tilt)=%s   요청 %-20s → 반환 %s' % (k, want, got))
    print()
    if bad:
        print('   type 만 비교했으므로 이것은 **하한**이다. 같은 type 의 다른 사람으로')
        print('   바뀐 경우는 여기서 안 잡힌다. 개념 벡터는 그 경우에도 남의 것이다.')
    print()
    print('   영향 범위: tilt > 0.02 인 모든 판단. tilted_view 는 판단 층의')
    print('   단일 진입점이므로 여기서 바뀐 프로필이 계획·사이즈·응답 전부에 흐른다.')


if __name__ == '__main__':
    main()
