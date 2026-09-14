#!/usr/bin/env python3
"""엔진 실행 폴더를 만든다. setup_run_dir.sh 와 **같은 일을 한다.**

  python ui/tools/setup_run_dir.py [대상폴더]        기본값 ~/t2_ui_run

윈도우에는 sh 가 없다. Git for Windows 의 bash 를 찾아 쓰게 하는 것보다
파이썬으로 같은 걸 두는 편이 낫다 — 서버를 돌리려면 어차피 파이썬이 필요하다.
목록이 어긋나면 안 되므로 **.sh 를 고치면 여기도 같이 고칠 것.**

허용 목록 방식이다. 제외 목록으로 짜면 저장소에 파일이 하나 늘 때마다 샌다.
live2_state.json·hand_archive2*.jsonl 은 git 에 커밋되어 있어서, 통째로
복사하면 진행 중인 게임이 실행 폴더로 딸려 들어간다.

이미 있는 폴더에 다시 돌려도 된다. 코드만 덮어쓰고 상태·아카이브는 손대지 않는다.
"""
import os, shutil, sys

# live2 가 전이적으로 import 하는 모듈 전부. view.py 는 ui_view 가
# view_text 라는 이름으로 직접 로드하므로 반드시 포함한다.
MODULES = """archetypes bot context depth dynamics field fieldsim formats gto icm
             live2 persona plan play preflop ranges reads runner session table
             texture view""".split()

# 데이터 파일. pf_rank.json 이 없으면 preflop.py import 자체가 실패한다.
DATA = ['pf_rank.json', 'style_sig.json', 'style_prior.json']


def main():
    src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.dirname(src)                       # ui/tools -> 저장소 루트
    dst = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.expanduser('~'), 't2_ui_run')
    dst = os.path.abspath(dst)
    os.makedirs(dst, exist_ok=True)
    if os.path.normcase(dst) == os.path.normcase(src):
        sys.exit('중단: 대상이 엔진 폴더 자신입니다 (%s).' % src)

    for m in MODULES:
        shutil.copy2(os.path.join(src, m + '.py'), os.path.join(dst, m + '.py'))
    for d in DATA:
        shutil.copy2(os.path.join(src, d), os.path.join(dst, d))
    shutil.copy2(os.path.join(src, 'ui', 'server', 'ui_view.py'),
                 os.path.join(dst, 'ui_view.py'))
    shutil.copy2(os.path.join(src, 'ui', 'server', 'ui_server.py'),
                 os.path.join(dst, 'ui_server.py'))

    web_src = os.path.join(src, 'ui', 'web')
    if os.path.isdir(web_src) and os.listdir(web_src):
        web_dst = os.path.join(dst, 'web')
        os.makedirs(web_dst, exist_ok=True)
        for fn in os.listdir(web_src):
            p = os.path.join(web_src, fn)
            if os.path.isfile(p):
                shutil.copy2(p, os.path.join(web_dst, fn))

    # 이 표시 파일이 없으면 ui_server 가 시작을 거부한다.
    open(os.path.join(dst, 'UI_SERVER_DIR'), 'w').close()

    print('실행 폴더: %s' % dst)
    print('  모듈 %d개, 데이터 %d개' % (len(MODULES), len(DATA)))
    print('  실행: cd "%s" && python ui_server.py' % dst)
    print('  주의: T2_LIVE_STATE 를 설정하지 마세요. 설정하면 접미사가 _alt 로')
    print('        고정되어 cli.py 세션과 아카이브를 공유하게 됩니다.')


if __name__ == '__main__':
    main()
