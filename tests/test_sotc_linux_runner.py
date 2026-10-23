"""Runner contracts without launching the game or preparation scripts."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

spec = importlib.util.spec_from_file_location('sotc_runner', Path(__file__).resolve().parents[1] / 'sotc.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@unittest.skipUnless(os.name != 'nt', 'Linux runner tests')
class LinuxRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.game = self.root / 'game'
        self.game.mkdir()
        (self.game / 'eboot.bin').touch()
        self.boot = self.root / 'prepared.bin'
        self.content = self.root / 'content.bin'
        self.boot.touch()
        self.content.touch()
        self.env = {'SOTC_GAME_DIR': str(self.game), 'SOTC_BOOT_IMAGE': str(self.boot),
                    'SOTC_CONTENT_PROFILE': str(self.content)}

    def run_prepared(self, loader_args=(), **extra):
        calls = []
        def modes(name, *args):
            calls.append((name, args))
            target = Path(args[args.index('--out') + 1])
            (target / 'cmdline.bin').touch()
            (target / 'patches.bin').touch()
        with patch.dict(os.environ, {**self.env, **extra}, clear=True), \
             patch.object(runner, 'PORT', self.root), patch.object(runner, 'load_ini'), \
             patch.object(runner.os, 'chdir'), patch.object(runner, 'run_script', side_effect=modes), \
             patch.object(runner, 'fingerprint', side_effect=AssertionError('must not fingerprint')), \
             patch.object(runner, 'find_probe', return_value=self.root / 'bb-probe'), \
             patch.object(runner.sys, 'argv', ['sotc.py', *loader_args]), \
             patch.object(runner.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            self.assertEqual(runner.main(), 0)
            return run.call_args.args[0], dict(os.environ), calls

    def test_prepared_skips_preparation_and_keeps_artifacts_separate(self):
        out = self.root / 'out'
        out.mkdir()
        existing = out / 'boot-linked.bin'
        existing.write_bytes(b'preserve')
        command, env, calls = self.run_prepared()
        self.assertEqual([c[0] for c in calls], ['sotc_modes.py'])
        self.assertEqual(calls[0][1][calls[0][1].index('--out') + 1], out / 'launcher-linux')
        self.assertEqual(existing.read_bytes(), b'preserve')
        self.assertNotIn('--sotc-cpu', command)
        self.assertEqual(command[1], str(self.boot))
        self.assertEqual(env['BB_FPS_LIMIT'], '30')
        self.assertEqual(env['BB_VBLANK_HZ'], '60')
        self.assertNotIn('PATH', env)

    def test_launcher_disables_probe_default_ten_second_watchdog(self):
        command, _, _ = self.run_prepared()
        self.assertEqual(command[command.index('--timeout') + 1], '0')

    def test_explicit_timeout_can_override_continuous_default(self):
        command, _, _ = self.run_prepared(loader_args=('--timeout', '600'))
        self.assertEqual(command[-2:], ['--timeout', '600'])
        values = [command[i + 1] for i, arg in enumerate(command) if arg == '--timeout']
        self.assertEqual(values, ['0', '600'])

    def test_fps60_defaults_and_explicit_overrides(self):
        _, env, _ = self.run_prepared(SOTC_MODES='fps60')
        self.assertEqual((env['BB_FPS_LIMIT'], env['BB_VBLANK_HZ']), ('60', '60'))
        _, env, _ = self.run_prepared(SOTC_MODES='fps60', BB_FPS_LIMIT='45', BB_VBLANK_HZ='90')
        self.assertEqual((env['BB_FPS_LIMIT'], env['BB_VBLANK_HZ']), ('45', '90'))

    def test_engine_fps60_defaults_and_explicit_overrides(self):
        _, env, calls = self.run_prepared(SOTC_MODES='fps60game')
        self.assertEqual((env['BB_FPS_LIMIT'], env['BB_VBLANK_HZ']), ('60', '60'))
        self.assertIn('fps60game', calls[0][1])
        _, env, _ = self.run_prepared(SOTC_MODES='fps60game', BB_FPS_LIMIT='45', BB_VBLANK_HZ='90')
        self.assertEqual((env['BB_FPS_LIMIT'], env['BB_VBLANK_HZ']), ('45', '90'))

    def test_automatic_preparation_never_overwrites_manual_images(self):
        out = self.root / 'out'
        out.mkdir()
        existing = out / 'boot-linked.bin'
        existing.write_bytes(b'manual image')
        env = {'SOTC_GAME_DIR': str(self.game)}
        calls = []
        def script(name, *args):
            calls.append((name, args))
        with patch.dict(os.environ, env, clear=True), \
             patch.object(runner, 'PORT', self.root), patch.object(runner, 'load_ini'), \
             patch.object(runner.os, 'chdir'), patch.object(runner, 'run_script', side_effect=script), \
             patch.object(runner, 'fingerprint', return_value='new-fingerprint'), \
             patch.object(runner, 'find_probe', return_value=self.root / 'bb-probe'), \
             patch.object(runner.sys, 'argv', ['sotc.py']), \
             patch.object(runner.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            self.assertEqual(runner.main(), 0)
        prepared = out / 'launcher-linux' / 'prepared'
        self.assertEqual([c[0] for c in calls], ['prepare.py', 'link_modules.py',
                                               'content_profile.py', 'sotc_cpu.py', 'sotc_modes.py'])
        for _, args in calls[:4]:
            self.assertEqual(args[args.index('--out') + 1], prepared)
        self.assertEqual(calls[-1][1][calls[-1][1].index('--out') + 1], out / 'launcher-linux')
        self.assertEqual(run.call_args.args[0][1], str(prepared / 'boot-linked.bin'))
        self.assertEqual((prepared / 'prepared.txt').read_text(), 'new-fingerprint\n')
        self.assertEqual(existing.read_bytes(), b'manual image')

    def test_data_root_keeps_prepared_launch_writes_outside_port(self):
        with tempfile.TemporaryDirectory() as external:
            data = Path(external) / 'external-data'
            before = set(self.root.iterdir())
            self.root.chmod(0o555)
            try:
                command, env, calls = self.run_prepared(SOTC_DATA_DIR=str(data))
            finally:
                self.root.chmod(0o755)
            self.assertEqual(set(self.root.iterdir()), before)
        self.assertEqual(env['BB_CONFIG'], str(data / 'sotc.ini'))
        self.assertEqual(env['BB_GPU_USER_DIR'], str(data / 'user'))
        self.assertEqual(command[command.index('--user') + 1], str(data / 'user'))
        self.assertEqual(calls[0][1][calls[0][1].index('--out') + 1],
                         data / 'out' / 'launcher-linux')
        self.assertFalse((self.root / 'out').exists())

    def test_data_root_automatic_preparation_and_stamp(self):
        data = self.root / 'data'
        before = set(self.root.iterdir())
        calls = []
        def script(name, *args):
            calls.append((name, args))
            self.assertTrue(Path(args[args.index('--out') + 1]).is_relative_to(data))
        with patch.dict(os.environ, {'SOTC_GAME_DIR': str(self.game),
                                     'SOTC_DATA_DIR': str(data)}, clear=True), \
             patch.object(runner, 'PORT', self.root), patch.object(runner, 'load_ini'), \
             patch.object(runner.os, 'chdir'), patch.object(runner, 'run_script', side_effect=script), \
             patch.object(runner, 'fingerprint', return_value='stamp'), \
             patch.object(runner, 'find_probe', return_value=self.root / 'bb-probe'), \
             patch.object(runner.sys, 'argv', ['sotc.py']), \
             patch.object(runner.subprocess, 'run', return_value=Mock(returncode=0)):
            self.assertEqual(runner.main(), 0)
        self.assertEqual(len(calls), 5)
        self.assertEqual((data / 'out/launcher-linux/prepared/prepared.txt').read_text(), 'stamp\n')
        self.assertEqual(set(self.root.iterdir()) - before, {data})

    def test_linux_ini_uses_data_root_and_explicit_config(self):
        data = self.root / 'data'
        data.mkdir()
        (data / 'sotc.ini').write_text('RUNNER_TEST_SETTING=data\n')
        explicit = self.root / 'chosen.ini'
        explicit.write_text('RUNNER_TEST_SETTING=explicit\n')
        with patch.object(runner, 'PORT', self.root):
            with patch.dict(os.environ, {'SOTC_DATA_DIR': str(data)}, clear=True):
                runner.load_ini()
                self.assertEqual(os.environ['RUNNER_TEST_SETTING'], 'data')
            with patch.dict(os.environ, {'SOTC_DATA_DIR': str(data), 'BB_CONFIG': str(explicit)}, clear=True):
                runner.load_ini()
                self.assertEqual(os.environ['RUNNER_TEST_SETTING'], 'explicit')
            with patch.dict(os.environ, {'SOTC_DATA_DIR': str(data)}, clear=True), \
                 patch.object(runner.os, 'name', 'nt'):
                self.assertEqual(runner.data_dir(), self.root)
                self.assertEqual(runner.config_path(), self.root / 'sotc.ini')

    def test_mode_tokens_are_unambiguous(self):
        env = {}
        runner.apply_timing_defaults(env, 'notfps60,fps600')
        self.assertEqual(env['BB_FPS_LIMIT'], '30')
        env = {}
        runner.apply_timing_defaults(env, 'af16, FPS60 ')
        self.assertEqual(env['BB_FPS_LIMIT'], '60')

    def test_windows_timing_preserves_legacy(self):
        with patch.object(runner.os, 'name', 'nt'):
            env = {}
            runner.apply_timing_defaults(env, 'af16, fps60')
            self.assertEqual(env, {'BB_VBLANK_HZ': '120'})
            env = {}
            runner.apply_timing_defaults(env, '')
            self.assertEqual(env, {})

    def test_windows_engine_target_uses_sixty_hz(self):
        with patch.object(runner.os, 'name', 'nt'):
            env = {}
            runner.apply_timing_defaults(env, 'af16, FPS60GAME')
            self.assertEqual(env, {'BB_VBLANK_HZ': '60', 'BB_FPS_LIMIT': '60'})
            runner.apply_timing_defaults(env, 'fps60')
            self.assertEqual(env, {'BB_VBLANK_HZ': '60', 'BB_FPS_LIMIT': '60'})
            env = {'BB_VBLANK_HZ': '90', 'BB_FPS_LIMIT': '45'}
            runner.apply_timing_defaults(env, 'fps60game')
            self.assertEqual(env, {'BB_VBLANK_HZ': '90', 'BB_FPS_LIMIT': '45'})

    def test_optional_cpu_profile(self):
        cpu = self.root / 'cpu.bin'
        cpu.touch()
        command, _, _ = self.run_prepared(SOTC_CPU_PROFILE=str(cpu))
        self.assertEqual(command[command.index('--sotc-cpu') + 1], str(cpu))

    def test_missing_pair_and_missing_files_fail_before_scripts(self):
        for extra in ({'SOTC_CONTENT_PROFILE': ''}, {'SOTC_BOOT_IMAGE': str(self.root / 'missing')},
                      {'SOTC_CPU_PROFILE': str(self.root / 'missing-cpu')},
                      {'SOTC_BOOT_IMAGE': '', 'SOTC_CONTENT_PROFILE': '', 'SOTC_CPU_PROFILE': str(self.boot)}):
            with self.subTest(extra=extra), self.assertRaises(SystemExit):
                self.run_prepared(**extra)

    def test_probe_requires_executable_and_prefers_bin(self):
        (self.root / 'bin').mkdir()
        (self.root / 'out').mkdir()
        first = self.root / 'bin' / 'bb-probe'
        second = self.root / 'out' / 'bb-probe'
        first.touch()
        second.touch()
        second.chmod(0o755)
        with patch.object(runner, 'PORT', self.root):
            self.assertEqual(runner.find_probe(), second)
            first.chmod(0o755)
            self.assertEqual(runner.find_probe(), first)
        self.assertEqual(runner.no_console(), 0)


if __name__ == '__main__':
    unittest.main()
