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

legacy `_alt`
-------------
과거 사용자 상태 실행은 전부 `_alt` 에 썼다. 그 데이터는 잃지 않는다.

  읽기  새 namespace 파일이 있으면 **그것만** current
        없고 `_alt` 만 있으면 **읽기 전용** legacy 로 발견
  쓰기  사용자 상태는 **항상** 새 namespace. `_alt` 로 새로 쓰지 않는다
  이동  `_alt` 를 rename/copy/migrate 하지 **않는다**

읽기가 legacy 로 내려가면 호출부가 그 사실을 표시할 수 있게
`resolve_read` 가 출처를 같이 돌려준다.
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


def resolve_read(kind, path=None, env=None):
    """읽을 파일과 그 출처. 없으면 (None, 'missing').

    출처는 'current' / 'legacy_alt' / 'missing'. legacy 로 내려간 사실을
    호출부가 숨기지 못하게 값으로 돌려준다.
    """
    cur = sidecar_path(kind, path, env)
    if os.path.exists(cur):
        return cur, 'current'
    st = _norm(path) if path else state_path(env)
    if not is_default(st):
        leg = legacy_path(kind)
        if os.path.exists(leg):
            return leg, 'legacy_alt'
    return None, 'missing'


def describe(path=None, env=None):
    """진단용 요약. 검증기와 UI 가 같은 문장을 쓰게 한다."""
    st = _norm(path) if path else state_path(env)
    ns = namespace_for_state(st)
    rows = {}
    for kind in sorted(KINDS):
        p, src = resolve_read(kind, st)
        rows[kind] = {'write': sidecar_path(kind, st),
                      'read': p, 'source': src}
    return {'state': st, 'default': is_default(st),
            'namespace': ns or '(없음)', 'kinds': rows}
