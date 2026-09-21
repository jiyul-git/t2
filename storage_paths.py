# -*- coding: utf-8 -*-
"""live 상태 파일의 sidecar 경로. **I/O 헬퍼이고 판단 로직이 아니다.**

원칙: **state 파일 하나 = sidecar namespace 하나.**

예전에는 `T2_LIVE_STATE` 가 **설정돼 있기만 하면** 경로와 무관하게 접미사가
`_alt` 하나였다. 그래서 서로 다른 상태 파일을 쓰는 두 실행이 같은 모듈
폴더의 아카이브·봇로그를 **섞어 썼다**. `live2.new_game` 이 그 파일들을
백업하며 진행 중이던 37핸드를 날린 사고가 이것 때문이다
(`live2.py` 의 주석에 남아 있다).

  기본 상태  <모듈>/live2_state.json   -> 접미사 **없음** (기존 파일 그대로)
  사용자 상태 T2_LIVE_STATE=<경로>      -> `_s_<sha256(realpath)[:12]>`

기본 상태의 접미사를 그대로 두는 것이 중요하다. 바꾸면 기존
`hand_archive2.jsonl` 을 갑자기 못 찾는다.

해시는 **stable** 해야 한다 — `hash()` 는 `PYTHONHASHSEED` 를 타므로
프로세스마다 이름이 달라진다. sha256 을 쓴다.

legacy `_alt` 는 **주인을 알 수 없다**
-------------------------------------
과거에는 사용자 상태가 **무엇이든** 전부 같은 `_alt` 에 썼다. 그래서
`/tmp/a/state.json` 과 `/tmp/b/state.json` 의 기록이 한 파일에 섞여 있다.

따라서 A 에 hashed 파일이 없다는 이유만으로 `_alt` 를 A 의 과거 기록이라고
읽으면 **B 의 기록을 A 의 것으로 제시**하게 된다. 그것이 조용히 일어나면
분석도 감사도 틀린 대상을 본다.

  읽기  새 namespace 파일이 있으면 **그것만** current
        없고 `_alt` 만 있으면 **발견은 하되 주인을 단정하지 않는다** —
        출처가 `legacy_alt_ambiguous` 이고, 명시적 opt-in 없이는
        **쓸 수 있는 경로를 돌려주지 않는다**
  쓰기  사용자 상태는 **항상** 새 namespace. `_alt` 로 새로 쓰지 않는다
  이동  `_alt` 를 rename/copy/migrate 하지 **않는다**

`resolve_read` 는 경로만 주지 않고 출처 분류를 함께 준다. 호출부가 출처를
무시하고 경로만 쓰는 형태가 되지 않게, 반환은 매핑이다.
"""
import hashlib, os

D = os.path.dirname(os.path.abspath(__file__))

ENV = 'T2_LIVE_STATE'
DEFAULT_STATE = os.path.join(D, 'live2_state.json')
LEGACY_SUFFIX = '_alt'
NS_PREFIX = '_s_'
NS_HEX = 12

# sidecar 종류 -> (기본이름, 확장자)
#
# book·dynamics 는 **현재 producer 가 없다** — 리딩 장부는 상태 안에 산다
# (`live2.build_hand` 주석). `new_game` 의 백업 목록에 남아 있어서 옛 파일을
# 치울 때만 쓰인다. 목록에서 빼면 그 파일들이 영원히 남는다.
KINDS = {
    'archive':  ('hand_archive2', '.jsonl'),
    'bot_log':  ('bot_hands', '.jsonl'),
    'book':     ('book', '.json'),
    'dynamics': ('dynamics', '.json'),
}

# `new_game` 이 백업 대상으로 삼는 순서. 목록을 두 곳에 적지 않는다.
BACKUP_KINDS = ('archive', 'book', 'dynamics', 'bot_log')


def _norm(path):
    """realpath 로 정규화. `/tmp/a/../a/s.json` 과 `/tmp/a/s.json` 이 같아야 한다."""
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def state_path(env=None):
    """이 프로세스가 쓰는 상태 파일의 정규화 경로."""
    env = os.environ if env is None else env
    return _norm(env.get(ENV) or DEFAULT_STATE)


def is_default(path=None):
    return _norm(path or state_path()) == _norm(DEFAULT_STATE)


def namespace_for_state(path):
    """상태 경로 -> sidecar 접미사. 기본 상태면 ''.

    같은 realpath 는 항상 같은 값이고, 디렉터리가 다르면 basename 이 같아도
    다른 값이다.
    """
    p = _norm(path)
    if _norm(DEFAULT_STATE) == p:
        return ''
    h = hashlib.sha256(p.encode('utf-8')).hexdigest()[:NS_HEX]
    return NS_PREFIX + h


def namespace(env=None):
    """이 프로세스의 접미사."""
    return namespace_for_state(state_path(env))


def _name(kind, suffix):
    base, ext = KINDS[kind]
    return '%s%s%s' % (base, suffix, ext)


def sidecar_path(kind, path=None, env=None):
    """**쓰기용** 경로. 사용자 상태는 언제나 새 namespace 다."""
    st = _norm(path) if path else state_path(env)
    return os.path.join(D, _name(kind, namespace_for_state(st)))


def name_for(kind, suffix):
    """접미사를 직접 아는 쪽을 위한 이름 조립. 규칙을 두 곳에 적지 않는다.

    `fieldsim.BOT_SUFFIX` 는 live2 가 워커용으로 **잠시 덮어쓰는** 모듈
    전역이라 경로를 미리 굳힐 수 없다. 그래서 이름 규칙만 빌려 준다.
    """
    return _name(kind, suffix)


def path_for(kind, suffix, root=None):
    return os.path.join(root or D, _name(kind, suffix))


def pending_suffix(suffix, pid):
    """워커가 쓰는 임시 접미사. 메인 경로가 나중에 본 파일에 붙인다.

    워커에서 바로 append 하면 (1) 결과를 버리고 다시 계산할 때 줄이 중복되고
    (2) 워커가 쓰다 죽으면 줄이 잘린다 — 둘 다 실제로 관측됐다
    (`live2.compute_others` 주석).
    """
    return '%s_pending_%d' % (suffix, pid)


def legacy_path(kind):
    """옛 `_alt` 경로. **읽기 전용**이다."""
    return os.path.join(D, _name(kind, LEGACY_SUFFIX))


SRC_CURRENT = 'current'
SRC_DEFAULT = 'default'
SRC_LEGACY_AMBIGUOUS = 'legacy_alt_ambiguous'
SRC_MISSING = 'missing'

AMBIGUOUS_NOTE = ('옛 공유 아카이브가 있으나 어느 상태의 기록인지 알 수 없다 '
                  '— 과거에는 모든 custom state 가 이 한 파일에 썼다')


def resolve_read(kind, path=None, env=None, allow_legacy_alt=False):
    """읽을 파일과 **출처 분류**. 반환은 매핑이다.

      path         쓸 수 있는 경로. 모호한 legacy 는 opt-in 없이는 None
      source       current / default / legacy_alt_ambiguous / missing
      legacy_path  옛 공유 파일의 위치 (존재를 알리기 위해)
      usable       path 를 그대로 읽어도 되는가
      note         모호할 때의 설명

    `legacy_alt_ambiguous` 에서 `path` 를 비워 두는 것이 요점이다. 출처를
    무시하고 경로만 쓰는 호출부가 **남의 기록을 자기 것으로** 읽는 일을
    구조적으로 막는다.
    """
    st = _norm(path) if path else state_path(env)
    cur = sidecar_path(kind, st)
    if os.path.exists(cur):
        return {'path': cur,
                'source': SRC_DEFAULT if is_default(st) else SRC_CURRENT,
                'legacy_path': None, 'usable': True, 'note': None}
    if not is_default(st):
        leg = legacy_path(kind)
        if os.path.exists(leg):
            return {'path': leg if allow_legacy_alt else None,
                    'source': SRC_LEGACY_AMBIGUOUS,
                    'legacy_path': leg,
                    'usable': bool(allow_legacy_alt),
                    'note': AMBIGUOUS_NOTE}
    return {'path': None, 'source': SRC_MISSING,
            'legacy_path': None, 'usable': False, 'note': None}


def read_path(kind, path=None, env=None, allow_legacy_alt=False):
    """쓸 수 있는 경로만. 모호한 legacy 는 opt-in 없이는 None 이다."""
    return resolve_read(kind, path, env, allow_legacy_alt)['path']


def describe(path=None, env=None):
    """진단용 요약. 검증기와 UI 가 같은 문장을 쓰게 한다."""
    st = _norm(path) if path else state_path(env)
    ns = namespace_for_state(st)
    rows = {}
    for kind in sorted(KINDS):
        r = resolve_read(kind, st)
        rows[kind] = {'write': sidecar_path(kind, st),
                      'read': r['path'], 'source': r['source'],
                      'legacy_path': r['legacy_path']}
    return {'state': st, 'default': is_default(st),
            'namespace': ns or '(없음)', 'kinds': rows}
