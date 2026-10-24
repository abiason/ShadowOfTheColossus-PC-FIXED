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
    def test_headers_free_links_refresh_and_invalid_chains(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'bpe-guard'
            subprocess.run(['c++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(ROOT / 'gpu/shim'), '-I' + str(ROOT / 'gpu/shadps4'),
                            str(ROOT / 'tests/test_bpe_heap_guard.cpp'),
                            str(ROOT / 'gpu/shadps4/video_core/buffer_cache/bpe_heap_guard.cpp'),
                            '-o', str(binary)], check=True, capture_output=True, text=True)
            for profile in ('0', '1'):
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10,
                                        env={**os.environ, 'SOTC_HEAP_GUARD_PROFILE': profile})
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('BPE scoped readback guard: PASS', result.stdout)
