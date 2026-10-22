#!/usr/bin/env python3
"""Build a native CachyOS x86_64 source-checkout package, never a universal image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
FILES = {
    'out/bb-probe': 'bin/bb-probe',
    'out/bb-gpu-capabilities': 'bin/bb-gpu-capabilities',
    'out/gpu/libbbgpu.so': 'bin/gpu/libbbgpu.so',
    **{f'launcher/{n}': f'launcher/{n}' for n in (
        'sotc_launcher.py', 'sotc_launcher_win.py', 'sotc_lang_es.py',
        'sotc_discovery.py', 'button_icons.py')},
    **{f'scripts/{n}.py': f'scripts/{n}.py' for n in (
        'prepare', 'link_libc', 'link_modules', 'content_profile', 'sotc_cpu',
        'sotc_modes', 'sotc_cache')},
    **{n: n for n in ('sotc.py', 'LICENSE', 'CHANGELOG.md')},
}
LICENSES = ('gpu/shadps4/LICENSE', 'gpu/third_party/imgui/LICENSE.txt',
            'gpu/third_party/fsr-vulkan/LICENSE.txt', 'gpu/third_party/fsr-vulkan/NOTICE.md',
            'gpu/third_party/sirit/LICENSE.txt', 'gpu/third_party/miniz/LICENSE',
            'gpu/third_party/half/LICENSE.txt', 'gpu/third_party/fonts/LICENSE-DejaVu.txt',
            'third_party/LibAtrac9/LICENSE', 'gpu/third_party/magic_enum/LICENSE',
            'gpu/third_party/sirit/externals/SPIRV-Headers/LICENSE',
            'gpu/third_party/fsr-vulkan/upstream/ffx-1.1.4/sdk/LICENSE.txt')
OPTIONAL = ('packaging/linux/README.md', 'docs/sotc/README-Linux-CachyOS-RDNA4.md',
            'docs/releases/v0.59.1-linux.2.md', 'launcher/sotc.png', 'launcher/sotc.ico')
WRAPPER = '''#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SOTC_DATA_DIR=${SOTC_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/sotc-pc}
export SOTC_DATA_DIR
exec python3 "$here/launcher/sotc_launcher.py" "$@"
'''
NOTICE = '''Native CachyOS Linux x86_64 package; not an AppImage or universal distribution.
Extract this directory, then run ./SotC.sh (do not start the Python entry directly).
SotC.sh keeps generated data outside the program under the XDG data directory.
See packaging/linux/README.md for setup, dependencies and limitations.
Requires a compatible host: Python 3 with Tkinter, SDL3, FFmpeg libraries,
Vulkan loader and an appropriate GPU Vulkan driver, plus the toolchain runtime
libraries used by the supplied build. Host library ABI compatibility is required;
no host shared libraries are bundled. This build targets GLIBC 2.43,
GLIBCXX 3.4.36 and FFmpeg 63; it requires compatible host versions. Build requirements and configuration are
in the included Linux guide when available. No game, Sony module, save, local
configuration or shader cache is included. Supply your own legally obtained data.
MANIFEST.json records artifact hashes, not a reproducible-build attestation.
'''


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def regular(root, relative):
    path = root / relative
    cursor = path
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError(f'Symlink refused: {relative}')
        cursor = cursor.parent
    if not path.is_file():
        raise ValueError(f'Missing regular file: {relative}')
    return path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def sanitize_binary(path):
    subprocess.run(['patchelf', '--set-rpath', '$ORIGIN/gpu', str(path)], check=True)


def package(root=ROOT, output=None, allow_dirty_fsr=False):
    root = Path(root).absolute()
    if any(parent.is_symlink() for parent in (root, *root.parents)):
        raise ValueError('Symlink checkout root refused')
    head = git(root, 'rev-parse', 'HEAD')
    status = git(root, 'status', '--porcelain', '--untracked-files=no')
    fsr_status = git(root / 'gpu/third_party/fsr-vulkan', 'status', '--porcelain')
    fsr_pointer = git(root / 'gpu/third_party/fsr-vulkan', 'rev-parse', 'HEAD')
    if any(line.endswith('gpu/third_party/fsr-vulkan') for line in status.splitlines()):
        fsr_status = fsr_status or 'submodule differs from recorded checkout state'
    if fsr_status and not allow_dirty_fsr:
        raise ValueError('Dirty FSR refused; --allow-dirty-fsr permits a private preview only')
    selected = dict(FILES)
    for relative in OPTIONAL:
        if (root / relative).exists() or (root / relative).is_symlink():
            selected[relative] = relative
    for relative in LICENSES:
        selected[relative] = 'licenses/' + relative
    sources = {name: regular(root, name) for name in selected}
    for name in ('out/bb-probe', 'out/bb-gpu-capabilities', 'out/gpu/libbbgpu.so'):
        with sources[name].open('rb') as stream:
            header = stream.read(20)
        if len(header) < 20 or header[:6] != b'\x7fELF\x02\x01' or header[18:20] != b'\x3e\x00':
            raise ValueError(f'Expected little-endian x86_64 ELF: {name}')
    output = Path(output).absolute() if output is not None else root / 'dist'
    for parent in (output, *output.parents):
        if parent.is_symlink():
            raise ValueError('Symlink output path refused')
    output.mkdir(parents=True, exist_ok=True)
    name = f'SotC-PC-linux-x86_64-{head[:12]}-{uuid.uuid4().hex[:12]}'
    archive = output / f'{name}.tar.gz'
    warnings = ['Artifact hashes identify existing build outputs; Git state does not prove '
                'which source, dependencies or compiler produced them. No clean-build claim.']
    if status:
        warnings.append('Checkout contains tracked changes; package is not an attested release build.')
    if fsr_status:
        warnings.append('PRIVATE PREVIEW ONLY: dirty FSR was explicitly allowed; do not upload. '
                        'FSR source changes are preserved in checkout and are not copied, but '
                        'their effects may be present in libbbgpu.so.')
    with tempfile.TemporaryDirectory(prefix='sotc-package-') as temporary:
        stage = Path(temporary) / name
        stage.mkdir()
        for source, destination in selected.items():
            target = stage / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sources[source], target)
            target.chmod(0o755 if destination in ('bin/bb-probe', 'bin/bb-gpu-capabilities') else 0o644)
        sanitize_binary(stage / 'bin/bb-probe')
        (stage / 'SotC.sh').write_text(WRAPPER)
        (stage / 'SotC.sh').chmod(0o755)
        (stage / 'README-LINUX-PACKAGE.txt').write_text(NOTICE)
        manifest = {
            'format': 1, 'target': 'CachyOS Linux x86_64 with host dependencies',
            'git_head': head, 'tracked_checkout_dirty': bool(status),
            'fsr_head': fsr_pointer, 'dirty_fsr_preserved': bool(fsr_status),
            'private_preview_only': bool(fsr_status), 'warnings': warnings,
            'binary_transformations': {'bin/bb-probe': 'patchelf --set-rpath $ORIGIN/gpu'},
            'input_artifact_sha256': {n: digest(sources[n]) for n in sources if n.startswith('out/')},
            'artifact_sources': {selected[n]: n for n in sources if n.startswith('out/')},
            'sha256': {str(p.relative_to(stage)): digest(p) for p in sorted(stage.rglob('*')) if p.is_file()},
        }
        (stage / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
        # Exclusive creation: never overwrite an existing artifact, even on name collision.
        with archive.open('xb') as stream:
            with tarfile.open(fileobj=stream, mode='w:gz') as tar:
                tar.add(stage, arcname=name)
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--allow-dirty-fsr', action='store_true', help='Private local preview only; never upload')
    args = parser.parse_args()
    try:
        archive = package(args.root, args.output, args.allow_dirty_fsr)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Package refused: {error}\n')
    print(archive)


if __name__ == '__main__':
    main()
