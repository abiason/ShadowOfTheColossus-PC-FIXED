"""Linux heap diagnostics: real C scanner and safe backing reads, without a game/GPU."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name != 'nt' and shutil.which('cc'), 'Linux C compiler required')
class HeapWatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.binary = Path(cls.directory.name) / 'test-heap-watch'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-pthread',
                        str(ROOT / 'tests/test_sotc_heap_watch.c'), '-o', str(cls.binary)],
                       check=True, capture_output=True, text=True)

    def run_case(self, name):
        result = subprocess.run([str(self.binary), name], capture_output=True, text=True, timeout=10)
        if name == 'kernel' and result.returncode == 77:
            self.skipTest(result.stderr.strip())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_valid_inventory_and_read_only_snapshot(self):
        self.run_case('valid')

    def test_padding_bits_and_u32_bitmap_word_count(self):
        self.run_case('padding')

    def test_invalid_shapes_and_unreadable_objects(self):
        self.run_case('invalid')

    def test_chunked_bitmap_read_cannot_report_partial_counts(self):
        self.run_case('chunks')

    def test_capacity_and_address_bounds(self):
        self.run_case('bounds')

    def test_separate_backings_mapping_holes_and_invalid_host_addresses(self):
        self.run_case('backing')

    def test_page_allocator_root_and_descriptor_stride(self):
        self.run_case('pools')

    def test_bpe_class_requires_matching_vtable_and_both_functions(self):
        self.run_case('class')

    def test_kernel_reader_integration_when_permitted(self):
        self.run_case('kernel')
