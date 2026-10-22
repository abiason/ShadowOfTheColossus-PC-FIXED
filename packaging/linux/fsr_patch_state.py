"""Read-only verification that FSR changes are exactly patches committed in HEAD."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

FSR = 'gpu/third_party/fsr-vulkan'
PATCHES = 'gpu/patches/fsr-vulkan'


def _git(root, *args, env=None):
    return subprocess.check_output(
        ['git', '-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false',
         '-c', 'core.hooksPath=/dev/null', '-C', str(root), *args], env=env)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_versioned_patches(root):
    """Return provenance evidence, or raise ValueError for any unknown FSR state.

    Patch contents come from superproject HEAD, never the working tree. Temporary
    index AND object database prevent git apply --cached from writing to FSR Git.
    This establishes source equivalence, not existing binary provenance.
    """
    root = Path(root).resolve()
    sub = root / FSR
    try:
        entry = _git(root, 'ls-tree', 'HEAD', '--', FSR).decode().strip().split()
        if len(entry) != 4 or entry[:2] != ['160000', 'commit']:
            raise ValueError('FSR must be a gitlink recorded in HEAD')
        recorded = entry[2]
        head = _git(sub, 'rev-parse', 'HEAD').decode().strip()
        if head != recorded:
            raise ValueError('FSR HEAD differs from recorded parent commit')
        parent_index = _git(root, 'ls-files', '--stage', '--', FSR).decode().strip().split()
        if len(parent_index) != 4 or parent_index[:3] != ['160000', recorded, '0']:
            raise ValueError('FSR gitlink index differs from parent HEAD')
        if _git(sub, 'diff', '--cached', '--name-only', 'HEAD', '--').strip():
            raise ValueError('Staged FSR changes refused')
        for options in (('--others', '--exclude-standard'),
                        ('--others', '--ignored', '--exclude-standard')):
            if _git(sub, 'ls-files', *options, '-z'):
                raise ValueError('Untracked or ignored FSR files refused')
        paths = _git(root, 'ls-tree', '-r', '--name-only', 'HEAD', '--', PATCHES).decode().splitlines()
        paths = sorted(p for p in paths if p.endswith('.patch'))
        if not paths:
            raise ValueError('No versioned FSR patches found')
        patch_data = {}
        for path in paths:
            tree = _git(root, 'ls-tree', 'HEAD', '--', path).decode().split()
            if not tree or tree[0] not in ('100644', '100755'):
                raise ValueError('Patch must be a regular versioned blob')
            patch_data[path] = _git(root, 'show', f'HEAD:{path}')
        flags = ('--no-ext-diff', '--no-textconv', '--binary', '--full-index', '--no-renames')
        actual = _git(sub, 'diff', *flags, 'HEAD', '--')
        with tempfile.TemporaryDirectory(prefix='sotc-fsr-verify-') as temporary:
            temp = Path(temporary)
            objects = temp / 'objects'
            objects.mkdir()
            store = Path(_git(sub, 'rev-parse', '--git-path', 'objects').decode().strip())
            if not store.is_absolute():
                store = (sub / store).resolve()
            env = os.environ.copy()
            env['GIT_INDEX_FILE'] = str(temp / 'index')
            env['GIT_OBJECT_DIRECTORY'] = str(objects)
            env['GIT_ALTERNATE_OBJECT_DIRECTORIES'] = str(store)
            _git(sub, 'read-tree', 'HEAD', env=env)
            for number, data in enumerate(patch_data.values()):
                patch = temp / f'{number}.patch'
                patch.write_bytes(data)
                _git(sub, 'apply', '--cached', str(patch), env=env)
            expected = _git(sub, 'diff', '--cached', *flags, 'HEAD', '--', env=env)
        if actual != expected:
            raise ValueError('FSR worktree is not exactly the versioned patches')
        return {'parent_recorded_commit': recorded, 'fsr_head': head,
                'diff_sha256': _sha(actual),
                'patch_file_sha256': {p: _sha(data) for p, data in patch_data.items()}}
    except subprocess.CalledProcessError as error:
        raise ValueError('Cannot verify versioned FSR patch state') from error
