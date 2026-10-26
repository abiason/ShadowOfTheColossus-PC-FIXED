"""Real Liverpool scheduling and coroutine progress; no game or GPU required.

Build first: ninja -C out/gpu sotc-cp-wait-test
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BINARY = Path(__file__).resolve().parents[1] / 'out/gpu/sotc-cp-wait-test'


@unittest.skipUnless(sys.platform == 'linux' and BINARY.is_file(), 'Build the Linux CP wait test first')
class CommandProcessorWaitTests(unittest.TestCase):
    def run_case(self, mode, enabled=True, override=None, one_cpu=False):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('SOTC_', 'BB_', 'SHADPS4_'))}
        env.update(SOTC_DRAW_PREP='0', SOTC_DRAW_SCAN='0', BB_COPY_GPU_BUFFERS='0')
        if override is not None:
            env['SOTC_CP_YIELD'] = override
        command = [str(BINARY), mode, 'on' if enabled else 'off']
        if one_cpu:
            command.append('one-cpu')
        # libbbgpu initializes user paths before main. Own an existing root;
        # a fresh CI environment need not have HOME/.local/share available.
        with tempfile.TemporaryDirectory(prefix='sotc-cp-user-') as user_dir:
            env['BB_GPU_USER_DIR'] = user_dir
            env['XDG_DATA_HOME'] = str(Path(user_dir) / 'missing-xdg-parent')
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
        if one_cpu and result.returncode == 77:
            self.skipTest('The environment does not permit selecting one CPU')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('completed; scheduler yields=', result.stdout)

    def test_graphics_wait_yields_by_default_and_services_callback(self):
        self.run_case('gfx')

    def test_compute_wait_with_empty_graphics_queue_yields_and_completes(self):
        self.run_case('compute', override='1')

    def test_explicit_zero_restores_busy_polling_without_losing_callback(self):
        self.run_case('gfx', enabled=False, override='0')

    def test_active_graphics_packets_do_not_request_idle_yields(self):
        self.run_case('active')

    def test_graphics_wait_and_callback_share_one_cpu(self):
        self.run_case('gfx', one_cpu=True)
