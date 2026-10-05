#!/usr/bin/env python3
"""Build separate first-install and system-only update ZIPs, without a wallet DB."""
import argparse
from pathlib import Path
import zipfile

from install_game import prepared_system, system_files


def build_packages(output):
    output = Path(output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    launcher = Path(__file__).with_name('install_game.py').read_text(encoding='utf-8')
    paths = []
    with prepared_system() as source:
        for mode in ('install', 'update'):
            path = output / ('T2-' + mode + '.zip')
            with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for rel in system_files(source):
                    archive.write(source / rel, 'T2/system/' + rel.as_posix())
                archive.writestr('T2/' + mode + '.py', launcher)
                if mode == 'install':
                    archive.writestr('T2/personal/README.txt',
                        '이 폴더는 개인 데이터입니다. 최초 install.py 실행 시 지갑을 만듭니다.\n'
                        '업데이트 패키지에는 이 폴더가 포함되지 않습니다. 백업하여 보관하세요.\n')
            paths.append(path)
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('output', help='두 ZIP을 저장할 폴더')
    args = ap.parse_args()
    for path in build_packages(args.output):
        print(path)


if __name__ == '__main__':
    main()
