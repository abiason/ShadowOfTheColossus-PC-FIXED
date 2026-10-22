"""Isolated packaging tests; no native binary is executed."""
import hashlib
import importlib.util
import json
from pathlib import Path
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
