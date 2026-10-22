"""Real local Git fixtures; no network or workspace Git mutations."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('fsr_state', Path(__file__).resolve().parents[1] / 'packaging/linux/fsr_patch_state.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sub = self.root / mod.FSR
        self.sub.mkdir(parents=True)
        for path in (self.root, self.sub):
            git(path, 'init', '-q')
            git(path, 'config', 'user.name', 'Fixture')
            git(path, 'config', 'user.email', 'fixture@example.invalid')
        (self.sub / 'a.c').write_text('base\n')
        (self.sub / 'b.c').write_text('base\n')
        (self.sub / '.gitignore').write_text('ignored\n')
        git(self.sub, 'add', '.')
        git(self.sub, 'commit', '-qm', 'base')
        self.head = git(self.sub, 'rev-parse', 'HEAD').decode().strip()
        patches = self.root / mod.PATCHES
        patches.mkdir(parents=True)
        for number, name in enumerate(('a.c', 'b.c')):
            (self.sub / name).write_text('base\npatched\n')
            (patches / f'{number:04d}.patch').write_bytes(git(self.sub, 'diff', '--', name))
        git(self.root, 'add', mod.PATCHES)
        git(self.root, 'update-index', '--add', '--cacheinfo', f'160000,{self.head},{mod.FSR}')
        git(self.root, 'commit', '-qm', 'record patches and gitlink')

    def snapshot(self):
        return {str(p.relative_to(self.sub / '.git')): p.read_bytes()
                for p in (self.sub / '.git').rglob('*') if p.is_file()}

    def test_exact_and_no_original_git_writes(self):
        before = self.snapshot()
        report = mod.verify_versioned_patches(self.root)
        self.assertEqual(report['fsr_head'], self.head)
        self.assertEqual(report['parent_recorded_commit'], self.head)
        self.assertEqual(len(report['patch_file_sha256']), 2)
        self.assertEqual(before, self.snapshot())

    def test_patch_worktree_not_trusted(self):
        (self.root / mod.PATCHES / '0000.patch').write_text('invalid local modification')
        self.assertEqual(mod.verify_versioned_patches(self.root)['fsr_head'], self.head)

    def test_extra_change(self):
        (self.sub / 'a.c').write_text('unknown\n')
        with self.assertRaisesRegex(ValueError, 'not exactly'):
            mod.verify_versioned_patches(self.root)

    def test_staged(self):
        git(self.sub, 'add', 'a.c')
        with self.assertRaisesRegex(ValueError, 'Staged'):
            mod.verify_versioned_patches(self.root)

    def test_untracked_and_ignored(self):
        for name in ('extra', 'ignored'):
            with self.subTest(name=name):
                p = self.sub / name
                p.write_text('extra')
                with self.assertRaisesRegex(ValueError, 'Untracked or ignored'):
                    mod.verify_versioned_patches(self.root)
                p.unlink()

    def test_head_mismatch(self):
        git(self.sub, 'add', '.')
        git(self.sub, 'commit', '-qm', 'different head')
        with self.assertRaisesRegex(ValueError, 'HEAD differs'):
            mod.verify_versioned_patches(self.root)

    def test_parent_index_mismatch(self):
        git(self.root, 'update-index', '--cacheinfo', f'160000,{"b" * 40},{mod.FSR}')
        with self.assertRaisesRegex(ValueError, 'gitlink index'):
            mod.verify_versioned_patches(self.root)


if __name__ == '__main__':
    unittest.main()
