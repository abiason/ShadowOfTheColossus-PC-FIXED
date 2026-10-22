#!/usr/bin/env python3
"""Record build inputs and binary hashes; this is not a cryptographic attestation.

CI should generate this after building from a clean checkout. The record reports
observed state; it does not reject or certify an unclean or unknown build.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess

BINARIES = ('out/bb-probe', 'out/bb-gpu-capabilities', 'out/gpu/libbbgpu.so')


def command(root, *args):
    try:
        result = subprocess.run(args, cwd=root, capture_output=True, text=True,
                                errors='replace', timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def os_release(path=Path('/etc/os-release')):
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError:
        return None
    values = {}
    for line in lines:
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            values[key] = value.strip('"\'')
    return values


def binary_hash(path):
    try:
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return {'sha256': digest.hexdigest(), 'size_bytes': path.stat().st_size}
    except OSError:
        return None


def create_record(root):
    root = Path(root).resolve()
    status = command(root, 'git', 'status', '--porcelain=v1', '--untracked-files=no',
                     '--ignore-submodules=none')
    tracked_changes = None if status is None else bool(status)
    # gitlink values describe versioned inputs, rather than silently substituting
    # worktree submodule HEADs for their committed revisions.
    tree = command(root, 'git', 'ls-tree', '-r', 'HEAD')
    submodules = []
    if tree is not None:
        for line in tree.splitlines():
            metadata, separator, path = line.partition('\t')
            parts = metadata.split()
            if separator and len(parts) == 3 and parts[0] == '160000':
                submodules.append({'path': path, 'gitlink_head': parts[2],
                                   'worktree_head': (command(root / path, 'git', 'rev-parse', 'HEAD')
                                                     if (root / path / '.git').exists() else None)})
    versions = {tool: command(root, tool, '--version')
                for tool in ('gcc', 'g++', 'cmake', 'ninja', 'python3')}
    packages = command(root, 'pacman', '-Q')
    run = None
    server, repository, run_id = (os.environ.get(name) for name in
                                  ('GITHUB_SERVER_URL', 'GITHUB_REPOSITORY', 'GITHUB_RUN_ID'))
    if server and repository and run_id:
        run = {'url': f'{server.rstrip("/")}/{repository}/actions/runs/{run_id}',
               'attempt': os.environ.get('GITHUB_RUN_ATTEMPT')}
    dependencies = None
    dependency_file = root / 'out/dependencies/vma/dependency-record.json'
    if dependency_file.is_file():
        dependencies = json.loads(dependency_file.read_text())
    required_abi = {}
    for name in BINARIES:
        version_info = command(root, 'readelf', '--version-info', str(root / name))
        required_abi[name] = (sorted(set(re.findall(r'GLIBC(?:XX)?_[0-9.]+', version_info)))
                              if version_info is not None else None)
    return {
        'schema_version': 1,
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'notice': 'Observed build provenance, not a cryptographic attestation. Generate after a clean CI build.',
        'git': {'head': command(root, 'git', 'rev-parse', 'HEAD'),
                'tracked_changes': tracked_changes,
                'status_known': status is not None,
                'submodules': submodules},
        'pinned_dependencies': dependencies,
        'required_abi': required_abi,
        'runtime': {'system': platform.system(), 'machine': platform.machine(),
                    'os_release': os_release()},
        'tool_versions': versions,
        'packages_pacman': packages.splitlines() if packages is not None else None,
        'build_flags': {name: os.environ.get(name) for name in ('BB_PGO', 'BB_LTO')},
        'binaries': {name: binary_hash(root / name) for name in BINARIES},
        'github_run': run,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, default=Path('out/build-provenance.json'))
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    record = create_record(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
