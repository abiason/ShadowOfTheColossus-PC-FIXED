#!/usr/bin/env python3
"""Fetch checksum-pinned build dependencies into the workspace, never system paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request


def reject_symlinks(path):
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError(f'Refusing symlink: {component}')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def download(url):
    if not url.startswith('https://'):
        raise ValueError('Dependency downloads require HTTPS')
    with urllib.request.urlopen(url, timeout=60) as response:
        if not response.geturl().startswith('https://'):
            raise ValueError('Dependency download redirected outside HTTPS')
        return response.read()


def atomic_write(path, data):
    reject_symlinks(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name + '.',
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        reject_symlinks(path)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def prepare(root, output=None):
    root = Path(root).absolute()
    output = Path(output) if output is not None else root / 'out/dependencies/vma'
    if not output.is_absolute():
        output = root / output
    reject_symlinks(root)
    reject_symlinks(output)
    manifest = root / 'packaging/linux/dependencies.json'
    reject_symlinks(manifest)
    dependency = json.loads(manifest.read_text(encoding='utf-8'))['vma']
    record_path = output / 'dependency-record.json'
    reject_symlinks(record_path)
    pending = []
    for entry in dependency['files']:
        name = entry['name']
        if name not in ('vk_mem_alloc.h', 'LICENSE.txt'):
            raise ValueError(f'Unexpected dependency filename: {name}')
        target = output / name
        reject_symlinks(target)
        if target.is_file() and sha256(target.read_bytes()) == entry['sha256']:
            continue
        data = download(entry['url'])
        if sha256(data) != entry['sha256']:
            raise ValueError(f'SHA-256 mismatch: {entry["url"]}')
        pending.append((target, data))
    # Validate every download before changing any dependency file.
    reject_symlinks(output)
    output.mkdir(parents=True, exist_ok=True)
    for target, data in pending:
        atomic_write(target, data)
    atomic_write(record_path, (json.dumps({'vma': dependency}, indent=2) + '\n').encode())
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        output = prepare(args.root, args.output)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f'Dependency preparation failed: {error}\n')
    print(output)


if __name__ == '__main__':
    main()
