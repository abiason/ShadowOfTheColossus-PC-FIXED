"""Isolated packaging tests; no native binary is executed."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('sotc_package', Path(__file__).resolve().parents[1] / 'packaging/linux/package_sotc.py')
pkg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pkg)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sotc fixture ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'checkout space'
        self.root.mkdir()
        for name in (*pkg.FILES, *pkg.LICENSES):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture')
        elf = bytearray(20)
        elf[:6] = b'\x7fELF\x02\x01'
        elf[18:20] = b'\x3e\x00'
        for name in pkg.FILES:
            if name.startswith('out/'):
                (self.root / name).write_bytes(elf)
        sanitize = patch.object(pkg, 'sanitize_binary')
        self.sanitizer = sanitize.start()
        self.addCleanup(sanitize.stop)
        self.dirty = ''
        def fake_git(root, *args):
            if args == ('rev-parse', 'HEAD'):
                return 'a' * 40
            if 'fsr-vulkan' in str(root):
                return self.dirty
            return ''
        self.mock = patch.object(pkg, 'git', side_effect=fake_git)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def test_allowlist_hashes_modes_and_spaces(self):
        for name in ('sotc.ini', 'user/save.bin', 'cache/shader.bin', 'game/eboot.bin', 'modules/libSceNgs2.sprx', 'gpu/third_party/fsr-vulkan/local.c'):
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('excluded')
        archive = pkg.package(self.root, self.root / 'new output space')
        with tarfile.open(archive) as tar:
            prefix = tar.getnames()[0] + '/'
            files = {m.name[len(prefix):]: m for m in tar.getmembers() if m.isfile()}
            expected = set(pkg.FILES.values()) | {'licenses/' + n for n in pkg.LICENSES} | {'SotC.sh', 'README-LINUX-PACKAGE.txt', 'MANIFEST.json'}
            self.assertEqual(set(files), expected)
            manifest = json.load(tar.extractfile(files['MANIFEST.json']))
            for name, checksum in manifest['sha256'].items():
                self.assertEqual(hashlib.sha256(tar.extractfile(files[name]).read()).hexdigest(), checksum)
            self.assertEqual(files['SotC.sh'].mode, 0o755)
            self.assertEqual(files['bin/bb-probe'].mode, 0o755)
            self.assertEqual(files['bin/gpu/libbbgpu.so'].mode, 0o644)
            wrapper = tar.extractfile(files['SotC.sh']).read().decode()
            self.assertIn('XDG_DATA_HOME', wrapper)
            self.assertIn('export SOTC_DATA_DIR', wrapper)
            self.assertFalse(manifest['private_preview_only'])
        self.assertNotEqual(archive, pkg.package(self.root, archive.parent))
        self.assertTrue(archive.is_file())

    def test_current_versioned_release_notes_are_included_but_untracked_notes_are_not(self):
        tracked = 'docs/releases/v9.99-linux.99.md'
        untracked = 'docs/releases/local-private.md'
        for name in (tracked, untracked):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('release fixture')
        original = pkg.git.side_effect
        def git_with_notes(root, *args):
            if args == ('ls-files', '--', 'docs/releases/*.md'):
                return tracked
            return original(root, *args)
        pkg.git.side_effect = git_with_notes
        archive = pkg.package(self.root)
        with tarfile.open(archive) as tar:
            names = tar.getnames()
            self.assertTrue(any(name.endswith('/' + tracked) for name in names))
            self.assertFalse(any(name.endswith('/' + untracked) for name in names))
            manifest = json.load(tar.extractfile(next(name for name in names if name.endswith('/MANIFEST.json'))))
            self.assertIn(tracked, manifest['sha256'])

    def test_packaged_launcher_imports_its_event_module_without_checkout_paths(self):
        names = ('sotc_launcher.py', 'sotc_launcher_win.py', 'sotc_events.py')
        source = Path(__file__).resolve().parents[1] / 'launcher'
        for name in names:
            (self.root / 'launcher' / name).write_bytes((source / name).read_bytes())
        archive = pkg.package(self.root)
        extracted = self.root / 'extracted-launcher'
        extracted.mkdir()
        with tarfile.open(archive) as tar:
            for name in names:
                member = next(m for m in tar.getmembers() if m.name.endswith('/launcher/' + name))
                (extracted / name).write_bytes(tar.extractfile(member).read())
        result = subprocess.run([sys.executable, '-I', '-c',
                                 'import sys; sys.path.insert(0, sys.argv[1]); '
                                 'import sotc_launcher; from sotc_launcher_win import SessionEvents; '
                                 'print(SessionEvents.__module__)', str(extracted)],
                                env={**os.environ, 'HOME': str(self.root)}, capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), 'sotc_events')

    def test_dirty_fsr_explicit_preview(self):
        self.dirty = ' M src/fsr.c'
        with self.assertRaisesRegex(ValueError, 'Dirty FSR'):
            pkg.package(self.root)
        archive = pkg.package(self.root, allow_dirty_fsr=True)
        with tarfile.open(archive) as tar:
            member = next(m for m in tar.getmembers() if m.name.endswith('/MANIFEST.json'))
            manifest = json.load(tar.extractfile(member))
            self.assertTrue(manifest['dirty_fsr_preserved'])
            self.assertTrue(manifest['private_preview_only'])
            self.assertTrue(any('do not upload' in w for w in manifest['warnings']))

    def make_record(self):
        record = {'git': {'head': 'a' * 40}, 'binaries': {
            name: {'sha256': pkg.digest(self.root / name)}
            for name in ('out/bb-probe', 'out/bb-gpu-capabilities', 'out/gpu/libbbgpu.so')}}
        path = self.root / 'out/build-provenance.json'
        path.write_text(json.dumps(record))
        return path

    def test_verified_patches_and_matching_record_allow_public_manifest(self):
        self.dirty = ' M src/fsr.c'
        record = self.make_record()
        with patch.object(pkg, 'verify_versioned_patches', return_value={'diff_sha256': 'known'}):
            archive = pkg.package(self.root, allow_versioned_fsr_patches=True, build_record=record)
        with tarfile.open(archive) as tar:
            member = next(m for m in tar.getmembers() if m.name.endswith('/MANIFEST.json'))
            manifest = json.load(tar.extractfile(member))
            self.assertFalse(manifest['private_preview_only'])
            self.assertEqual(manifest['versioned_fsr_patch_state']['diff_sha256'], 'known')
            self.assertIn('BUILD-PROVENANCE.json', manifest['sha256'])

    def test_modified_binary_and_missing_record_are_refused(self):
        self.dirty = ' M src/fsr.c'
        with patch.object(pkg, 'verify_versioned_patches', return_value={'diff_sha256': 'known'}):
            with self.assertRaisesRegex(ValueError, 'requires --build-record'):
                pkg.package(self.root, allow_versioned_fsr_patches=True)
            record = self.make_record()
            (self.root / 'out/bb-probe').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                pkg.package(self.root, allow_versioned_fsr_patches=True, build_record=record)

    def test_symlink_source_and_parent_refused(self):
        source = self.root / 'sotc.py'
        source.unlink()
        source.symlink_to(self.root / 'LICENSE')
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            pkg.package(self.root)
        source.unlink()
        source.write_text('fixture')
        (self.root / 'output-link').symlink_to(self.root / 'out', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            pkg.package(self.root, self.root / 'output-link' / 'nested')

    def test_missing_and_invalid_binary_refused(self):
        binary = self.root / 'out/bb-probe'
        binary.write_bytes(b'not an ELF')
        with self.assertRaisesRegex(ValueError, 'x86_64 ELF'):
            pkg.package(self.root)
        binary.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing regular'):
            pkg.package(self.root)


if __name__ == '__main__':
    unittest.main()
