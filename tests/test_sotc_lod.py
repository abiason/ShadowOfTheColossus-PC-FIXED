"""Compile and exercise the real LOD reports without a GPU or game files."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('c++'), 'C++ compiler required for LOD regression tests')
class LodPressureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.binary = Path(cls.directory.name) / 'test-sotc-lod'
        subprocess.run(['c++', '-std=c++23', '-Wall', '-Wextra', '-Werror',
                        '-I', str(ROOT / 'gpu/shadps4'), str(ROOT / 'tests/test_sotc_lod.cpp'),
                        '-o', str(cls.binary)], check=True, capture_output=True, text=True)

    def run_case(self, mode='pressure', **settings):
        env = {k: v for k, v in os.environ.items() if not k.startswith('SOTC_LOD_')}
        env['SOTC_LOD_LINGER'] = '1'
        env.update(settings)
        result = subprocess.run([str(self.binary), mode], env=env, capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_pressure_hysteresis_and_invalid_pool(self):
        self.run_case()

    def test_pressure_protection_can_be_disabled(self):
        self.run_case('disabled', SOTC_LOD_POOL_LOW='0')

    def test_texture_reports_off_remain_off(self):
        self.run_case('off', SOTC_LOD_LINGER='0')

    def test_coarse_mip_does_not_become_unused_marker(self):
        self.run_case('clamped', SOTC_LOD_LEVEL='14')

    def test_mapping_holes_and_remapped_physical_fragments(self):
        self.run_case('mapping')

    def test_large_sample_counts_saturate_streaming_priority(self):
        self.run_case('priority')
