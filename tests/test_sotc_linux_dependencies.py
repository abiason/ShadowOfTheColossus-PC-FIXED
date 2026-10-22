"""Dependency preparation checks with fixture downloads; no network or compiler."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_linux_dependencies',
                                             ROOT / 'packaging/linux/prepare_dependencies.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='sotc dependencies ')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.payloads = {'vk_mem_alloc.h': b'header fixture', 'LICENSE.txt': b'license fixture'}
        self.record = {'version': '3.3.0', 'commit': '1d8f600fd424278486eade7ed3e877c99f0846b1',
                       'files': [{'name': name, 'url': 'https://example.test/' + name,
                                  'sha256': hashlib.sha256(data).hexdigest()}
                                 for name, data in self.payloads.items()]}
        manifest = self.root / 'packaging/linux/dependencies.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'vma': self.record}))
        self.output = self.root / 'out/dependencies/vma'

    def fetch(self, url):
        return self.payloads[url.rsplit('/', 1)[1]]

    def test_prepares_spaces_and_records_pin_then_skips_matching_files(self):
        with mock.patch.object(module, 'download', side_effect=self.fetch) as fetch:
            self.assertEqual(module.prepare(self.root), self.output)
            self.assertEqual(fetch.call_count, 2)
        for name, data in self.payloads.items():
            self.assertEqual((self.output / name).read_bytes(), data)
        self.assertEqual(json.loads((self.output / 'dependency-record.json').read_text()),
                         {'vma': self.record})
        with mock.patch.object(module, 'download', side_effect=AssertionError('unexpected download')):
            module.prepare(self.root)

    def test_corrupt_download_rejected_before_writing_any_files(self):
        with mock.patch.object(module, 'download', side_effect=[b'header fixture', b'corrupt']):
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                module.prepare(self.root)
        self.assertFalse(self.output.exists())

    def test_corrupt_existing_file_replaced_only_after_verified_download(self):
        self.output.mkdir(parents=True)
        header = self.output / 'vk_mem_alloc.h'
        header.write_bytes(b'old corrupt data')
        with mock.patch.object(module, 'download', return_value=b'corrupt'):
            with self.assertRaises(ValueError):
                module.prepare(self.root)
        self.assertEqual(header.read_bytes(), b'old corrupt data')
        with mock.patch.object(module, 'download', side_effect=self.fetch):
            module.prepare(self.root)
        self.assertEqual(header.read_bytes(), self.payloads['vk_mem_alloc.h'])

    def test_symlink_output_and_file_rejected(self):
        elsewhere = self.root / 'elsewhere'
        elsewhere.mkdir()
        output = self.root / 'link'
        output.symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            module.prepare(self.root, output)
        self.output.mkdir(parents=True)
        (self.output / 'vk_mem_alloc.h').symlink_to(elsewhere / 'missing')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            module.prepare(self.root)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_relative_custom_output(self):
        with mock.patch.object(module, 'download', side_effect=self.fetch):
            path = module.prepare(self.root, Path('custom output/vma'))
        self.assertEqual(path, self.root / 'custom output/vma')
        self.assertTrue((path / 'LICENSE.txt').is_file())


if __name__ == '__main__':
    unittest.main()
