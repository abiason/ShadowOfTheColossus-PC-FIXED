"""Headless checks of launcher profiles, discovery scope and process-group Stop."""
import ast
import copy
import importlib.util
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'launcher'))


def load_launcher():
    spec = importlib.util.spec_from_file_location('sotc_launcher_test', ROOT / 'launcher/sotc_launcher_win.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(os.name == 'nt', 'Linux launcher integration')
class LinuxLauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.environment = mock.patch.dict(os.environ, {
            'HOME': str(self.base), 'XDG_CONFIG_HOME': str(self.base / 'config'),
            'XDG_DATA_HOME': str(self.base / 'data'),
        }, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.launcher = load_launcher()
        self.settings = copy.deepcopy(self.launcher.APP_DEFAULTS)
        self.settings.update(game_dir=str(self.base / 'game'), user_dir=str(self.base / 'user'))

    def test_xdg_settings_and_no_import_side_effects(self):
        expected = self.base / 'config/sotc-launcher/settings.json'
        self.assertEqual(self.launcher.CONFIG_FILE, expected)
        self.assertFalse(expected.parent.exists())
        self.assertNotIn('tkinter', self.launcher.__dict__)

    def test_linux_30_and_60_profiles_override_inherited_unsafe_values(self):
        with mock.patch.dict(os.environ, {'BB_FPS_LIMIT': '120', 'BB_VBLANK_HZ': '120',
                                         'SOTC_EOP_DEFER': '1', 'BB_DIRECT_MEMORY_ACCESS': '1'}):
            for fps60 in (False, True):
                with self.subTest(fps60=fps60):
                    self.settings['fps60'] = fps60
                    env = self.launcher.game_environment(self.settings)
                    for key, value in {'BB_FPS_LIMIT': '60' if fps60 else '30',
                                       'BB_VBLANK_HZ': '60', 'SOTC_EOP_DEFER': '0',
                                       'BB_DIRECT_MEMORY_ACCESS': '0', 'SOTC_RB_ASYNC': '0',
                                       'SOTC_NEO': '1', 'BB_DMEM_MB': '5376'}.items():
                        self.assertEqual(env[key], value, key)
                    self.assertEqual('fps60' in env['SOTC_MODES'].split(','), fps60)

    def test_prepared_paths_with_spaces_and_stale_environment(self):
        keys = {'prepared_boot': 'SOTC_BOOT_IMAGE', 'prepared_content': 'SOTC_CONTENT_PROFILE',
                'prepared_cpu': 'SOTC_CPU_PROFILE'}
        with mock.patch.dict(os.environ, {name: '/stale/value' for name in keys.values()}):
            env = self.launcher.game_environment(self.settings)
            for variable in keys.values():
                self.assertNotIn(variable, env)
            for setting in keys:
                self.settings[setting] = str(self.base / 'prepared files' / setting)
            env = self.launcher.game_environment(self.settings)
            for setting, variable in keys.items():
                self.assertEqual(env[variable], self.settings[setting])

    def test_windows_defaults_and_environment_remain_separate(self):
        tree = ast.parse((ROOT / 'launcher/sotc_launcher_win.py').read_text())
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == 'APP_DEFAULTS'
                                  for target in node.targets))
        defaults = eval(compile(ast.Expression(assignment.value), '<APP_DEFAULTS>', 'eval'),
                        {'PORT_DIR': self.launcher.PORT_DIR, 'GAME_ID': self.launcher.GAME_ID})
        for key, value in {'neo': False, 'perf_dma': True, 'fullscreen': False,
                           'af16': True, 'fps60': False, 'auto_setup': True}.items():
            self.assertEqual(defaults[key], value, key)
        with mock.patch.object(self.launcher, 'IS_WINDOWS', True):
            env = self.launcher.game_environment(defaults)
        self.assertEqual(env['SOTC_NEO'], '0')
        for name in ('BB_DMEM_MB', 'BB_FPS_LIMIT', 'BB_VBLANK_HZ', 'SOTC_EOP_DEFER'):
            self.assertNotIn(name, env)

    def test_discovery_does_not_scan_filesystem_root(self):
        import sotc_discovery
        self.assertEqual(sotc_discovery.local_drives(), [])
        visited = []
        def scandir(path):
            visited.append(Path(path))
            return []
        with mock.patch.object(sotc_discovery.os, 'scandir', side_effect=scandir):
            sotc_discovery.scan(seconds=1)
        self.assertNotIn(Path('/'), visited)
        self.assertIn(self.base, visited)

    def test_invalid_settings_shape_and_legacy_migration(self):
        old = self.base / 'sotc-launcher/settings.json'
        old.parent.mkdir()
        old.write_text('{"fps60": true}')
        self.assertTrue(self.launcher.load_json(self.launcher.CONFIG_FILE, {})['fps60'])
        self.launcher.CONFIG_DIR.mkdir(parents=True)
        for content in ('null', '[]', 'invalid'):
            self.launcher.CONFIG_FILE.write_text(content)
            self.assertEqual(self.launcher.load_json(self.launcher.CONFIG_FILE, {}), {})

    def test_linux_extra_variables_accept_quoted_paths(self):
        self.settings['extra_env'] = 'SOTC_CACHE_DIR="/tmp/cache com espaços" BB_FPS_LIMIT=45'
        env = self.launcher.game_environment(self.settings)
        self.assertEqual(env['SOTC_CACHE_DIR'], '/tmp/cache com espaços')
        self.assertEqual(env['BB_FPS_LIMIT'], '45')

    def test_linux_desktop_shortcut_quotes_arguments(self):
        import types
        desktop = self.base / 'Área de trabalho'
        messages = mock.Mock()
        launcher = types.SimpleNamespace(messagebox=messages)
        result = subprocess.CompletedProcess([], 0, str(desktop) + '\n', '')
        strange_python = str(self.base / 'python $var`test%name')
        with mock.patch.object(self.launcher.subprocess, 'run', return_value=result), \
                mock.patch.object(self.launcher.sys, 'executable', strange_python):
            self.launcher.Launcher.linux_shortcut(launcher)
        text = (desktop / 'Shadow of the Colossus.desktop').read_text()
        self.assertIn('%%name', text)
        self.assertIn('\\$var\\`test', text)
        self.assertIn('Terminal=false', text)
        messages.showinfo.assert_called_once()
        messages.showerror.assert_not_called()

    def test_stop_terminates_parent_and_child_process_group(self):
        marker = self.base / 'child-terminated'
        child = ("import signal,time,pathlib,sys; "
                 "signal.signal(signal.SIGTERM, lambda *a: "
                 "(pathlib.Path(sys.argv[1]).write_text('terminated'),sys.exit(0))); "
                 "print('ready',flush=True); time.sleep(30)")
        parent = ("import subprocess,sys,time; "
                  "p=subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]],"
                  "stdout=subprocess.PIPE,text=True); "
                  "assert p.stdout.readline().strip()=='ready'; "
                  "print(p.pid,flush=True); p.wait()")
        process = subprocess.Popen([sys.executable, '-c', parent, child, str(marker)],
                                   start_new_session=True, stdout=subprocess.PIPE, text=True)
        self.addCleanup(process.stdout.close)
        job = self.launcher.GameJob(process)
        try:
            self.assertTrue(select.select([process.stdout], [], [], 5)[0], 'child startup timeout')
            child_pid = int(process.stdout.readline())
            self.assertEqual(os.getpgid(child_pid), process.pid)
            job.terminate()
            process.wait(timeout=5)
            import time
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(marker.exists(), 'Stop failed to signal the child process')
            self.assertEqual(process.returncode, -signal.SIGTERM)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
            job.close()


if __name__ == '__main__':
    unittest.main()
