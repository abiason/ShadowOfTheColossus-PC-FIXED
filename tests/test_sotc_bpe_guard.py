"""Execute the actual scoped renderer guard against synthetic allocator memory."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('c++'), 'C++ compiler required')
class ScopedBpeGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.binaries = {}
        for name in ('test_bpe_heap_guard', 'repro_bpe_nested_ownership'):
            binary = Path(cls.directory.name) / name
            # Compile both real implementations before running the assertions.
            subprocess.run(['c++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(ROOT / 'gpu/shim'), '-I' + str(ROOT / 'gpu/shadps4'),
                            str(ROOT / f'tests/{name}.cpp'),
                            str(ROOT / 'gpu/shadps4/video_core/buffer_cache/bpe_heap_guard.cpp'),
                            '-o', str(binary)], check=True, capture_output=True, text=True)
            cls.binaries[name] = binary
        cls.nested_result = subprocess.run([str(cls.binaries['repro_bpe_nested_ownership'])],
                                           capture_output=True, text=True, timeout=10)

    def test_headers_free_links_refresh_and_invalid_chains(self):
        for profile in ('0', '1'):
            result = subprocess.run([str(self.binaries['test_bpe_heap_guard'])],
                                    capture_output=True, text=True, timeout=10,
                                    env={**os.environ, 'SOTC_HEAP_GUARD_PROFILE': profile})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('BPE scoped readback guard: PASS', result.stdout)

    def test_nested_owner_metadata_survives_parent_first_write(self):
        # Includes both owner orders, partial overlaps, aliases and invalid chains.
        result = self.nested_result
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("BPE combined ownership guard: PASS", result.stdout)
