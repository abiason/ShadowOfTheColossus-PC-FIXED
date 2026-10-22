#!/usr/bin/env python3
"""Smoke-test the actual AppImage via its no-FUSE entry point; never start a game."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_package import sha


def verify(image, gui=False):
    with tempfile.TemporaryDirectory(prefix='sotc appimage check spaces ') as name:
        root = Path(name)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(('SOTC_', 'BB_', 'PYTHON')) and k != 'LD_LIBRARY_PATH'}
        env.update(SOTC_DATA_DIR=str(root / 'data'), XDG_CONFIG_HOME=str(root / 'config'),
                   XDG_CACHE_HOME=str(root / 'cache'))
        command = [str(image.resolve()), '--appimage-extract-and-run', '--sotc-appimage-check']
        if gui:
            command.append('--gui')
        before = sha(image)
        run = subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)
        if run.returncode:
            raise ValueError('AppImage smoke test failed: ' + run.stdout + '\n' + run.stderr)
        result = json.loads(run.stdout.strip().splitlines()[-1])
        if not all(result.get(k) is True for k in ('bundled_python', 'bundled_tk', 'bundled_pillow')):
            raise ValueError('Incomplete bundled runtime')
        if result.get('game_started') is not False or result.get('gui_checked') is not gui:
            raise ValueError('Unexpected smoke test scope')
        if not Path(result['data']).is_relative_to(root):
            raise ValueError('Data directory escaped the test sandbox')
        if before != sha(image):
            raise ValueError('AppImage changed during smoke test')
        result.update(appimage=image.name, sha256=before, image_unchanged=True)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--report', type=Path, default=Path('out/appimage-verification.json'))
    args = parser.parse_args()
    images = list(args.directory.glob('*.AppImage'))
    if len(images) != 1:
        parser.error('Expected exactly one AppImage')
    result = verify(images[0], gui=args.gui)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    files = sorted([*args.directory.glob('*.tar.gz'), *images,
                    args.directory / 'APPIMAGE-BUNDLE.json'])
    if not all(p.is_file() for p in files):
        raise ValueError('Missing distribution report')
    (args.directory / 'SHA256SUMS').write_text(''.join(sha(p) + '  ' + p.name + '\n' for p in files))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
