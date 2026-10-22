"""Build recording contracts with fake tools and fixture binaries."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('record_build', Path(__file__).resolve().parents[1] / 'packaging/linux/record_build.py')
record_build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(record_build)


class BuildRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in record_build.BINARIES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture-' + name.encode())
        submodule = self.root / 'gpu/third_party/fsr-vulkan'
        submodule.mkdir(parents=True)
        (submodule / '.git').write_text('gitdir: fixture')

    def fake_command(self, root, *args):
        if args[:2] == ('git', 'status'):
            return ''
        if args == ('git', 'ls-tree', '-r', 'HEAD'):
            return '160000 commit vendor-head\tgpu/third_party/fsr-vulkan\n100644 blob ignored\tREADME.md'
        if args == ('git', 'rev-parse', 'HEAD'):
            return 'repo-head' if root == self.root else 'vendor-worktree-head'
        if args == ('pacman', '-Q'):
            return 'gcc 1.0\ncmake 2.0'
        return args[0] + ' fixture version'

    def record(self, env=None, command=None):
        with patch.dict(os.environ, env or {}, clear=True), \
             patch.object(record_build, 'command', side_effect=command or self.fake_command), \
             patch.object(record_build, 'os_release', return_value={'ID': 'fixture-linux'}):
            return record_build.create_record(self.root)

    def test_records_hashes_inputs_and_selective_flags(self):
        record = self.record({'BB_PGO': 'off', 'BB_LTO': 'OFF', 'PRIVATE_TOKEN': 'never-record-me',
                              'GITHUB_SERVER_URL': 'https://github.com', 'GITHUB_REPOSITORY': 'owner/repo',
                              'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '2'})
        self.assertEqual(record['git']['head'], 'repo-head')
        self.assertFalse(record['git']['tracked_changes'])
        self.assertEqual(record['git']['submodules'][0], {
            'path': 'gpu/third_party/fsr-vulkan', 'gitlink_head': 'vendor-head',
            'worktree_head': 'vendor-worktree-head'})
        for name in record_build.BINARIES:
            self.assertEqual(record['binaries'][name]['sha256'],
                             hashlib.sha256((self.root / name).read_bytes()).hexdigest())
        self.assertEqual(record['build_flags'], {'BB_PGO': 'off', 'BB_LTO': 'OFF'})
        self.assertEqual(record['github_run'], {'url': 'https://github.com/owner/repo/actions/runs/123', 'attempt': '2'})
        self.assertNotIn('never-record-me', json.dumps(record))
        self.assertEqual(record['packages_pacman'], ['gcc 1.0', 'cmake 2.0'])

    def test_unknown_is_not_clean_and_missing_binary_is_explicit(self):
        (self.root / record_build.BINARIES[0]).unlink()
        record = self.record(command=lambda *args: None)
        self.assertIsNone(record['git']['tracked_changes'])
        self.assertFalse(record['git']['status_known'])
        self.assertIsNone(record['binaries'][record_build.BINARIES[0]])
        self.assertEqual(record['build_flags'], {'BB_PGO': None, 'BB_LTO': None})
        self.assertIsNone(record['github_run'])
        self.assertIsNone(record['packages_pacman'])

    def test_dirty_fsr_is_reported_not_certified_or_rejected(self):
        def dirty(root, *args):
            if args[:2] == ('git', 'status'):
                return ' m gpu/third_party/fsr-vulkan'
            return self.fake_command(root, *args)
        self.assertTrue(self.record(command=dirty)['git']['tracked_changes'])

    def test_uninitialized_submodule_does_not_inherit_parent_head(self):
        (self.root / 'gpu/third_party/fsr-vulkan/.git').unlink()
        self.assertIsNone(self.record()['git']['submodules'][0]['worktree_head'])

    def test_cli_output_relative_to_root(self):
        with patch.object(record_build, 'create_record', return_value={'fixture': True}) as create:
            self.assertEqual(record_build.main(['--root', str(self.root)]), 0)
        create.assert_called_once_with(self.root)
        self.assertEqual(json.loads((self.root / 'out/build-provenance.json').read_text()), {'fixture': True})


if __name__ == '__main__':
    unittest.main()
